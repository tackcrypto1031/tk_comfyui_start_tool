"""ComfyUI process launcher and lifecycle manager."""
import configparser
import json
import logging
import os
import threading
import time
import requests
from pathlib import Path

from src.utils import git_ops, pip_ops, process_manager
from src.utils.net_ops import get_local_lan_ip

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

logger = logging.getLogger(__name__)


def _is_loopback_ip(ip: str) -> bool:
    """Return True if ip is a loopback address (no LAN reachability)."""
    if not ip:
        return False
    return ip in ("127.0.0.1", "localhost", "::1") or ip.startswith("127.")


DEFAULT_MANAGER_URL = "https://github.com/Comfy-Org/ComfyUI-Manager.git"
# Security level written to Manager's config.ini before each launch.
# "normal-" is accepted by Manager's 'middle+' / 'middle' gates when either
#   - is_local_mode=True  (ComfyUI listens on loopback), OR
#   - is_personal_cloud=True  (network_mode=personal_cloud in config.ini)
# We therefore always write "normal-" and additionally write
# network_mode=personal_cloud when ComfyUI is in LAN listen mode so that
# node installs from non-loopback clients are permitted.  Downgrading
# security_level further (e.g. "weak") is not required for normal listed
# custom nodes and would unnecessarily weaken the launcher's defaults.
MANAGER_SECURITY_LEVEL = "normal-"
# Manager's network_mode value that permits remote (non-loopback) installs.
# See comfyui_manager/glob/utils/security_utils.py — the 'middle+' / 'high+'
# gates require either is_local_mode=True OR network_mode == 'personal_cloud'.
MANAGER_NETWORK_MODE_LAN = "personal_cloud"

# How long (in seconds) a pid file with state="starting" is allowed to exist
# before get_status() considers the launch failed.  ComfyUI first-time startup
# can take 30-60s (loading torch, custom nodes, etc), so we give it 120s.
STARTING_STATE_TIMEOUT_SEC = 120

# How long after subprocess.Popen to check that the child is still alive.
# If it crashed within this window, we treat the launch as an immediate
# failure (e.g. port bind conflict).
POST_SPAWN_SANITY_DELAY_SEC = 0.5


class ComfyUILauncher:
    def __init__(self, config: dict):
        self.config = config
        self.environments_dir = Path(config["environments_dir"])
        # Serialize the port-pick-and-reserve phase of start() so two
        # concurrent launches within the same process cannot race between
        # find_available_port and writing the reservation pid file.
        self._start_lock = threading.Lock()

    def _build_cache_env_vars(self) -> dict:
        """Return a copy of os.environ with HF/torch/insightface cache vars
        redirected to <project>/cache/*.

        This solves the 'D' problem: huggingface_hub.snapshot_download,
        torch.hub.load, insightface etc. normally write to ~/.cache, one
        copy per user account. We redirect them to a project-scoped cache
        so all environments share and the project is portable.
        """
        cache_root = (_PROJECT_ROOT / "cache").resolve()
        env = os.environ.copy()
        hf_hub = cache_root / "huggingface" / "hub"
        env["HF_HOME"] = str(cache_root / "huggingface")
        env["HUGGINGFACE_HUB_CACHE"] = str(hf_hub)
        env["HF_HUB_CACHE"] = str(hf_hub)
        env["TRANSFORMERS_CACHE"] = str(hf_hub)
        env["DIFFUSERS_CACHE"] = str(cache_root / "diffusers")
        env["TORCH_HOME"] = str(cache_root / "torch")
        env["XDG_CACHE_HOME"] = str(cache_root)
        env["INSIGHTFACE_HOME"] = str(cache_root / "insightface")
        for sub in ("huggingface/hub", "torch", "diffusers", "insightface"):
            (cache_root / sub).mkdir(parents=True, exist_ok=True)
        return env

    def _pre_launch_shared_model_check(self, env_dir: Path) -> None:
        """Run sync_shared_model_subdirs + bridge.verify before launching ComfyUI."""
        from src.core.env_manager import EnvManager
        from src.core.shared_model_bridge import SharedModelBridge
        mgr = EnvManager(self.config)
        try:
            mgr.sync_shared_model_subdirs()
        except Exception as exc:
            logger.warning("sync_shared_model_subdirs failed: %s", exc)
        bridge = SharedModelBridge(self.config, mgr._resolve_model_path)
        try:
            report = bridge.verify(env_dir)
            if report.problems:
                logger.warning("Shared-model verify problems: %s", report.problems)
        except Exception as exc:
            logger.warning("bridge.verify failed: %s", exc)

    def _claimed_ports(self, exclude_env: Path = None) -> set:
        """Return the set of ports currently claimed by any env's pid file.

        This includes ports whose env is fully running AND ports whose env
        is in the "starting" state (reserved but not yet bound).  Without
        this, two envs launched in rapid succession would both be assigned
        the default port because neither has bound the socket yet.

        The ``exclude_env`` path is skipped so a restarting env doesn't
        exclude its own previous port.
        """
        claimed = set()
        if not self.environments_dir.exists():
            return claimed
        exclude_resolved = str(exclude_env.resolve()).lower() if exclude_env else None
        for entry in self.environments_dir.iterdir():
            if exclude_resolved and str(entry.resolve()).lower() == exclude_resolved:
                continue
            pid_file = entry / ".comfyui.pid"
            if not pid_file.exists():
                continue
            try:
                data = json.loads(pid_file.read_text())
            except Exception:
                continue
            port = data.get("port")
            if isinstance(port, int):
                # Starting state: always hold the reservation (even if nothing
                # is bound yet).  Running state: hold it unless we can prove
                # the pid is dead AND the port is actually free.
                if data.get("status") == "starting":
                    # Time out stale starting reservations so a crashed
                    # launcher doesn't permanently hog a port.
                    started_at = data.get("started_at", 0)
                    if time.time() - started_at < STARTING_STATE_TIMEOUT_SEC:
                        claimed.add(port)
                    continue
                pid = data.get("pid")
                if pid and process_manager.is_process_running(pid):
                    claimed.add(port)
                elif process_manager.is_port_in_use(port):
                    # Somebody is listening on the port even though our
                    # recorded pid is dead — assume it's this env and keep
                    # the reservation rather than handing the port out.
                    claimed.add(port)
        return claimed

    @staticmethod
    def _normalize_package_name(name: str) -> str:
        """Normalize package names so hyphen/underscore variants compare equal."""
        return name.strip().lower().replace("_", "-")

    def _has_package(self, installed: dict, package_name: str) -> bool:
        target = self._normalize_package_name(package_name)
        return any(self._normalize_package_name(pkg) == target for pkg in installed)

    @staticmethod
    def _tail_log(log_path: Path, line_count: int = 10, chunk_size: int = 4096) -> str:
        """Read only the last N lines from a log file to avoid full-file scans."""
        if line_count <= 0:
            return ""

        try:
            with open(log_path, "rb") as fh:
                fh.seek(0, 2)
                file_size = fh.tell()
                if file_size == 0:
                    return ""

                remaining = file_size
                buffer = b""
                while remaining > 0 and buffer.count(b"\n") <= line_count:
                    read_size = min(chunk_size, remaining)
                    remaining -= read_size
                    fh.seek(remaining)
                    buffer = fh.read(read_size) + buffer

                lines = buffer.decode("utf-8", errors="replace").splitlines()
                return "\n".join(lines[-line_count:])
        except Exception:
            return ""

    def start(self, env_name: str, port: int = 8188, extra_args: list = None,
              auto_open: bool = True) -> dict:
        """Start ComfyUI in the specified environment."""
        env_dir = self.environments_dir / env_name
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment '{env_name}' not found")

        # Prevent duplicate launches in the same environment (sqlite lock/confusing state).
        status = self.get_status(env_name)
        if status.get("status") in ("running", "starting"):
            raise RuntimeError(
                f"Environment '{env_name}' is already running "
                f"(pid={status.get('pid')}, port={status.get('port')})."
            )

        # Ensure comfyui-manager is installed and security level is manager-compatible.
        # Pass the listen IP so the correct security level is written: 'weak' for
        # non-loopback (LAN) mode, 'normal-' for loopback/default mode.
        listen_ip_for_manager = None
        if extra_args:
            try:
                idx = extra_args.index("--listen")
                listen_ip_for_manager = extra_args[idx + 1]
            except (ValueError, IndexError):
                pass
        self._ensure_manager_ready(env_dir, listen_ip=listen_ip_for_manager)

        pid_file = env_dir / ".comfyui.pid"

        # CRITICAL: pick a port AND write the reservation pid file under a
        # process-wide lock.  Without this, two concurrent start() calls
        # would both call find_available_port() before either had written a
        # reservation, and both would be handed the same default port.
        #
        # The reservation pid file has status="starting", pid=None, and the
        # claimed port.  Concurrent starts see it via _claimed_ports() and
        # skip the reserved port.
        with self._start_lock:
            claimed = self._claimed_ports(exclude_env=env_dir)
            port = process_manager.find_available_port(port, exclude=claimed)
            pid_file.write_text(json.dumps({
                "pid": None,
                "port": port,
                "status": "starting",
                "started_at": time.time(),
            }))

        # Build command (always enable manager for custom node support).
        # Use loopback listen mode by default so Manager can allow normal- actions safely.
        python = pip_ops.get_venv_python(str(env_dir / "venv"))
        listen_args = []
        if not extra_args or "--listen" not in extra_args:
            listen_args = ["--listen", "127.0.0.1"]

        cmd = [python, "main.py", *listen_args, "--port", str(port), "--enable-manager"]
        if extra_args:
            cmd.extend(extra_args)

        # Start process with log file so we can debug ComfyUI output
        log_file = str(env_dir / "comfyui.log")
        try:
            proc = process_manager.start_process(
                cmd, cwd=str(env_dir / "ComfyUI"), log_file=log_file
            )
        except Exception:
            # Popen itself failed — clean up the reservation.
            pid_file.unlink(missing_ok=True)
            raise

        # Post-spawn sanity: if the child died within a few hundred ms, the
        # launch is already a failure (e.g. the port race handed us a port
        # that turned out to be occupied, or python.exe itself crashed).
        # Clean up the reservation so the user isn't left with a ghost
        # "starting" env.
        sanity_delay = getattr(self, "_post_spawn_sanity_delay",
                               POST_SPAWN_SANITY_DELAY_SEC)
        if sanity_delay > 0:
            time.sleep(sanity_delay)
        try:
            exited = proc.poll() is not None
        except Exception:
            exited = False
        if exited:
            try:
                exit_code = proc.returncode
            except Exception:
                exit_code = "unknown"
            pid_file.unlink(missing_ok=True)
            last_log = ""
            try:
                if Path(log_file).exists():
                    last_log = self._tail_log(Path(log_file), line_count=20)
            except Exception:
                pass
            raise RuntimeError(
                f"ComfyUI process for '{env_name}' exited immediately "
                f"(exit={exit_code}). This usually means the port {port} "
                f"was taken by another process after allocation. "
                f"Last log:\n{last_log}"
            )

        # Compute listen_ip and lan_url before writing the pid file so they
        # can be persisted alongside pid/port.
        listen_ip = None
        if extra_args:
            try:
                idx = extra_args.index("--listen")
                listen_ip = extra_args[idx + 1]
            except (ValueError, IndexError):
                listen_ip = None
        lan_url = None
        if listen_ip and not _is_loopback_ip(listen_ip):
            lan_url = f"http://{get_local_lan_ip()}:{port}"

        # Save PID (still in "starting" state — get_status() promotes it to
        # "running" once the process has actually bound the socket).
        pid_payload = {
            "pid": proc.pid,
            "port": port,
            "status": "starting",
            "started_at": time.time(),
        }
        if lan_url:
            pid_payload["lan_url"] = lan_url
        pid_file.write_text(json.dumps(pid_payload))

        # Auto-open browser after a short delay
        if auto_open and self.config.get("auto_open_browser", True):
            import threading
            open_target = lan_url or f"http://localhost:{port}"
            def _open_browser():
                import time
                import webbrowser
                # Wait for ComfyUI to start (check health every 2 seconds, up to 60 seconds)
                for _ in range(30):
                    time.sleep(2)
                    if not process_manager.is_process_running(proc.pid):
                        return  # Process died, don't open browser
                    if self.health_check(port, timeout=2):
                        webbrowser.open(open_target)
                        return
            threading.Thread(target=_open_browser, daemon=True).start()

        result = {"pid": proc.pid, "port": port, "env_name": env_name}
        if lan_url:
            result["lan_url"] = lan_url
        return result

    def _ensure_manager_ready(self, env_dir: Path, listen_ip: str = None) -> None:
        """Ensure manager repo exists and Manager's config.ini is permissive.

        Args:
            listen_ip: The --listen IP address that will be passed to ComfyUI.  When
                this is a non-loopback address (0.0.0.0, LAN IP, etc.) ComfyUI Manager
                sets ``is_local_mode=False``; in that state the 'middle+' / 'high+'
                security gates also require ``network_mode=personal_cloud`` before
                they accept ``security_level=normal-``.  When listen_ip is loopback
                (or unset) we leave network_mode alone (Manager's default 'public'
                is fine because is_local_mode=True bypasses the gate).
        """
        comfyui_dir = env_dir / "ComfyUI"
        manager_repo_dir = comfyui_dir / "custom_nodes" / "ComfyUI-Manager"

        # Manager is a ComfyUI custom-node repo, not a pip package.
        if not manager_repo_dir.exists():
            logger.info("ComfyUI-Manager repo missing; cloning into custom_nodes...")
            manager_repo_dir.parent.mkdir(parents=True, exist_ok=True)
            try:
                git_ops.clone_repo(DEFAULT_MANAGER_URL, str(manager_repo_dir), branch="main")
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to install ComfyUI-Manager repository: {exc}"
                ) from exc

        self._ensure_manager_python_package(env_dir)

        # Always write the same security_level; the LAN-specific gate is opened
        # via network_mode=personal_cloud instead (see MANAGER_NETWORK_MODE_LAN
        # docstring).
        is_lan = bool(listen_ip) and not _is_loopback_ip(listen_ip)
        security_level = MANAGER_SECURITY_LEVEL
        network_mode = MANAGER_NETWORK_MODE_LAN if is_lan else None
        if is_lan:
            logger.info(
                "LAN listen mode detected (%s); writing security_level=%s and "
                "network_mode=%s to Manager config so node installs are permitted "
                "from non-loopback clients.",
                listen_ip, security_level, network_mode,
            )

        manager_config = comfyui_dir / "user" / "__manager" / "config.ini"
        self._write_manager_security_config(manager_config, security_level, network_mode)

        # Also write to the Manager repo's own config.ini — this is the path that
        # ComfyUI Manager reads at runtime (custom_nodes/ComfyUI-Manager/config.ini).
        # The user/__manager path is the new canonical location but Manager still
        # falls back to (or reads exclusively from) its repo-local config depending
        # on the installed version.  Writing to both guarantees the policy takes
        # effect regardless of Manager version.
        repo_config = manager_repo_dir / "config.ini"
        self._write_manager_security_config(repo_config, security_level, network_mode)

        # Keep backward compatibility for existing legacy config files.
        legacy_config = comfyui_dir / "user" / "default" / "ComfyUI-Manager" / "config.ini"
        if legacy_config.exists():
            self._write_manager_security_config(legacy_config, security_level, network_mode)

    def _write_manager_security_config(self, config_path: Path,
                                       security_level: str = MANAGER_SECURITY_LEVEL,
                                       network_mode: str = None) -> None:
        """Write manager security policy without creating legacy folders unnecessarily.

        When ``network_mode`` is None we do NOT touch the network_mode key (preserves
        any pre-existing value / Manager's default).  When ``network_mode`` is a
        string we write it to config['default']['network_mode'] — used in LAN
        listen mode to set ``personal_cloud`` so Manager's non-loopback install
        gates open.
        """
        config = configparser.ConfigParser()
        if config_path.exists():
            config.read(str(config_path), encoding="utf-8")

        if "default" not in config:
            config["default"] = {}

        config["default"]["security_level"] = security_level
        if network_mode is not None:
            config["default"]["network_mode"] = network_mode

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(config_path), "w", encoding="utf-8") as f:
            config.write(f)

    def _ensure_manager_python_package(self, env_dir: Path) -> None:
        """Install comfyui-manager package required by --enable-manager."""
        venv_path = str(env_dir / "venv")
        comfyui_dir = env_dir / "ComfyUI"
        installed = pip_ops.freeze(venv_path)

        if self._has_package(installed, "comfyui-manager"):
            return

        manager_requirements = comfyui_dir / "manager_requirements.txt"
        install_attempts = []
        if manager_requirements.exists():
            install_attempts.append(["install", "-r", str(manager_requirements)])
        install_attempts.append(["install", "-U", "--pre", "comfyui-manager"])

        errors = []
        for args in install_attempts:
            result = pip_ops.run_pip(venv_path, args)
            if result.returncode == 0:
                installed = pip_ops.freeze(venv_path)
                if self._has_package(installed, "comfyui-manager"):
                    return
                errors.append(
                    f"pip {' '.join(args)} completed but comfyui-manager is still missing"
                )
                continue

            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout or "unknown pip error"
            errors.append(f"pip {' '.join(args)} failed: {detail}")

        raise RuntimeError(
            "Failed to install comfyui-manager package required by --enable-manager. "
            + " | ".join(errors)
        )

    def stop(self, env_name: str) -> None:
        """Stop a running ComfyUI instance."""
        env_dir = self.environments_dir / env_name
        pid_file = env_dir / ".comfyui.pid"
        if not pid_file.exists():
            raise RuntimeError(f"No running instance found for '{env_name}'")
        try:
            data = json.loads(pid_file.read_text())
        except Exception:
            pid_file.unlink(missing_ok=True)
            return

        pid = data.get("pid")
        # CRITICAL: verify the pid in the file actually belongs to this env
        # before killing it.  Without this check, a pid file that was stale
        # or poisoned (e.g. a cloned env that inherited a pid file, or a
        # prior buggy version of get_status that overwrote env2's pid file
        # with env1's pid) will cause stop() to kill the wrong process --
        # producing the "close one closes both" symptom.
        #
        # Note: pid may be None when the pid file is a "starting" reservation
        # written before subprocess.Popen returned.  In that case there is
        # nothing to kill -- just clear the reservation below.
        if pid and process_manager.is_process_running(pid):
            if self._pid_belongs_to_env(pid, env_dir):
                process_manager.stop_process(pid)
            else:
                logger.warning(
                    "Refusing to kill pid %d for env '%s': process does not "
                    "belong to this environment (stale/poisoned pid file).",
                    pid, env_name,
                )

        # Do NOT fall back to killing whoever is listening on the port:
        # that would kill another env's ComfyUI that happens to be on the
        # same port.  If the pid is dead the env is effectively stopped.
        pid_file.unlink(missing_ok=True)

    def health_check(self, port: int, timeout: int = 5) -> bool:
        """Return True if ComfyUI is responding on the given port."""
        try:
            resp = requests.get(f"http://localhost:{port}/", timeout=timeout)
            return resp.status_code == 200
        except requests.ConnectionError:
            return False

    # Max consecutive poll failures before cleaning up pid file.
    # With 5s polling interval, 24 failures = ~120s grace period — long enough
    # to survive a ComfyUI Manager "install node + restart" cycle (python/torch
    # re-import + custom node re-scan can easily take 30-90s on Windows).
    # Matches STARTING_STATE_TIMEOUT_SEC so startup and restart tolerate the
    # same worst-case boot time.
    _MAX_FAIL_COUNT = 24

    def _pid_belongs_to_env(self, pid: int, env_dir: Path) -> bool:
        """Return True if the process with *pid* is the ComfyUI process for
        THIS specific environment.  We match by cwd() which is set to
        env_dir/ComfyUI at launch time -- this is the single most reliable
        signal and is immune to PATH games, shebang rewriting, or argv spoofing.
        Falls back to cmdline/exe path matching if cwd() isn't accessible.

        Returns False (not True) on error so that ownership cannot be falsely
        asserted: treating an unverifiable process as "not ours" forces the
        launcher to spawn its own, which is strictly safer than hijacking
        another env's process.
        """
        try:
            import psutil
            proc = psutil.Process(pid)
        except Exception:
            return False

        env_dir_resolved = str(Path(env_dir).resolve()).replace("\\", "/").lower()
        expected_cwd = str((Path(env_dir) / "ComfyUI").resolve()).replace("\\", "/").lower()

        # 1. Most reliable: working directory (set by subprocess.Popen cwd=)
        try:
            proc_cwd = str(Path(proc.cwd()).resolve()).replace("\\", "/").lower()
            if proc_cwd == expected_cwd:
                return True
            # Different cwd → definitely not ours (even if some other signal matches)
            if proc_cwd and env_dir_resolved not in proc_cwd:
                return False
        except Exception:
            pass  # fall through to exe/cmdline check

        # 2. Python executable path: start() uses env_dir/venv/Scripts/python.exe
        try:
            exe = proc.exe()
            if exe:
                exe_norm = str(Path(exe).resolve()).replace("\\", "/").lower()
                if env_dir_resolved in exe_norm:
                    return True
        except Exception:
            pass

        # 3. Last resort: cmdline contains env dir path
        try:
            cmdline = " ".join(proc.cmdline()).replace("\\", "/").lower()
            if env_dir_resolved in cmdline:
                return True
        except Exception:
            pass

        return False

    # Backward-compatible alias (earlier fix used this name; tests patch it).
    _is_pid_for_env = _pid_belongs_to_env

    def _with_last_log(self, env_dir: Path, result: dict) -> dict:
        """Attach last_log lines to a status result if the log file exists."""
        log_path = env_dir / "comfyui.log"
        if log_path.exists():
            last_log = self._tail_log(log_path, line_count=10)
            if last_log:
                result["last_log"] = last_log
        return result

    def get_status(self, env_name: str) -> dict:
        """Return status dict for an environment."""
        env_dir = self.environments_dir / env_name
        pid_file = env_dir / ".comfyui.pid"
        if not pid_file.exists():
            return {"status": "stopped", "env_name": env_name}
        try:
            data = json.loads(pid_file.read_text())
        except Exception:
            pid_file.unlink(missing_ok=True)
            return {"status": "stopped", "env_name": env_name}

        # ── "starting" state handling ─────────────────────────────────────
        # Reservation pid file was written before subprocess.Popen returned,
        # OR it's a subprocess that's still booting.  Resolve it to one of:
        #   - running: port is bound and the owner matches this env
        #   - starting: still within the timeout window, not yet bound
        #   - stopped: the starting timeout expired OR the pid died without
        #              ever binding -> clean up the reservation so the port
        #              becomes available again.
        if data.get("status") == "starting":
            started_at = data.get("started_at", 0)
            age = time.time() - started_at
            pid = data.get("pid")

            # If the starting pid exists and has died, the launch failed.
            if pid and not process_manager.is_process_running(pid):
                logger.info(
                    "Starting reservation for '%s' cleared: pid %s is dead.",
                    env_name, pid,
                )
                pid_file.unlink(missing_ok=True)
                return {"status": "stopped", "env_name": env_name}

            # If the process is now listening on the claimed port AND it
            # belongs to this env, promote it to "running".
            port = data.get("port")
            if port and process_manager.is_port_in_use(port):
                port_pid = process_manager.find_pid_on_port(port)
                if port_pid and self._pid_belongs_to_env(port_pid, env_dir):
                    data["pid"] = port_pid
                    data["status"] = "running"
                    data.pop("started_at", None)
                    pid_file.write_text(json.dumps(data))
                    result = {"status": "running", "env_name": env_name, **data}
                    return self._with_last_log(env_dir, result)

            # Still booting, but within the timeout window.
            if age < STARTING_STATE_TIMEOUT_SEC:
                result = {"status": "starting", "env_name": env_name, **data}
                return self._with_last_log(env_dir, result)

            # Timeout expired without binding — drop the reservation.
            logger.warning(
                "Starting reservation for '%s' expired after %ds (port %s "
                "never became ready). Clearing pid file.",
                env_name, int(age), data.get("port"),
            )
            # If the pid is still alive but hasn't bound, kill it to reclaim
            # the port reservation (only if it really belongs to this env).
            if pid and process_manager.is_process_running(pid) \
                    and self._pid_belongs_to_env(pid, env_dir):
                try:
                    process_manager.stop_process(pid)
                except Exception:
                    pass
            pid_file.unlink(missing_ok=True)
            return {"status": "stopped", "env_name": env_name}
        # ──────────────────────────────────────────────────────────────────

        pid = data.get("pid")
        running = bool(pid) and process_manager.is_process_running(pid)

        # Guard against stale pid files inherited from a cloned environment or
        # poisoned by the "pid-changed-after-restart" branch below: if the
        # process is alive but does not belong to this env, drop the pid file.
        if running and not self._pid_belongs_to_env(pid, env_dir):
            logger.info(
                "Removing stale pid file for '%s': pid %d belongs to a different "
                "environment.", env_name, pid,
            )
            pid_file.unlink(missing_ok=True)
            return {"status": "stopped", "env_name": env_name}

        if not running and "port" in data:
            # The original pid is dead.  DO NOT fall back to a "whoever is
            # listening on the port is us" check: if env1 is listening on
            # 8188 and env2 had a stale pid file also pointing to 8188,
            # the naive fallback would hijack env1's pid and write it into
            # env2's pid file -- then stopping env2 would kill env1
            # ("close one closes both").  Only accept the port-owner as
            # "this env's new pid" if _pid_belongs_to_env confirms it.
            port_pid = process_manager.find_pid_on_port(data["port"])
            if port_pid and self._pid_belongs_to_env(port_pid, env_dir):
                running = True
                if port_pid != pid:
                    data["pid"] = port_pid
                    data.pop("_fail_count", None)
                    pid_file.write_text(json.dumps(data))

        if not running:
            # Grace period: only delete pid file after consecutive failures
            # to survive brief restart gaps (e.g. ComfyUI Manager node install)
            fail_count = data.get("_fail_count", 0) + 1
            if fail_count >= self._MAX_FAIL_COUNT:
                pid_file.unlink(missing_ok=True)
            else:
                data["_fail_count"] = fail_count
                pid_file.write_text(json.dumps(data))
        else:
            # Reset fail count on success
            if "_fail_count" in data:
                del data["_fail_count"]
                pid_file.write_text(json.dumps(data))

        result = {"status": "running" if running else "stopped", "env_name": env_name, **data}

        # Include last log lines for debugging
        log_path = env_dir / "comfyui.log"
        if log_path.exists():
            last_log = self._tail_log(log_path, line_count=10)
            if last_log:
                result["last_log"] = last_log

        return result

    def list_running(self) -> list:
        """Return list of all running ComfyUI instances."""
        running = []
        if not self.environments_dir.exists():
            return running
        for entry in self.environments_dir.iterdir():
            pid_file = entry / ".comfyui.pid"
            if not pid_file.exists():
                continue
            try:
                data = json.loads(pid_file.read_text())
            except Exception:
                continue

            # Starting-state reservations: include only while still within
            # the timeout window (keeps the Running tab up to date with
            # envs that are booting) AND mark status explicitly.
            if data.get("status") == "starting":
                started_at = data.get("started_at", 0)
                age = time.time() - started_at
                if age >= STARTING_STATE_TIMEOUT_SEC:
                    continue  # expired; get_status() will clean it up
                port = data.get("port")
                if port and process_manager.is_port_in_use(port):
                    port_pid = process_manager.find_pid_on_port(port)
                    if port_pid and self._pid_belongs_to_env(port_pid, entry):
                        # Already bound; show as running.
                        info = {"env_name": entry.name, "pid": port_pid,
                                "port": port, "status": "running"}
                        running.append(self._attach_meta(entry, info))
                        continue
                info = {"env_name": entry.name, "status": "starting",
                        **{k: v for k, v in data.items() if k != "_fail_count"}}
                running.append(self._attach_meta(entry, info))
                continue

            # Normal case: verify the pid actually belongs to THIS env.
            # A pid file that survived from a cloned env -- or was poisoned
            # by an older build -- may point at another env's live process.
            # Treating such a file as "running" would mis-attribute the
            # other env's pid to this one in the UI, and stop actions
            # would then kill the wrong process.
            pid = data.get("pid")
            is_running = bool(
                pid
                and process_manager.is_process_running(pid)
                and self._pid_belongs_to_env(pid, entry)
            )
            if not is_running:
                # If the pid is dead but the pid file claims a port is
                # in use, only accept that as "running" if the process
                # currently holding the port belongs to this env.
                port = data.get("port")
                if port:
                    port_pid = process_manager.find_pid_on_port(port)
                    if port_pid and self._pid_belongs_to_env(port_pid, entry):
                        is_running = True
                        data["pid"] = port_pid
            # Include environments still within grace period (may be restarting)
            in_grace = not is_running and data.get("_fail_count", 0) < self._MAX_FAIL_COUNT
            if is_running or in_grace:
                info = {"env_name": entry.name, **data}
                info.pop("_fail_count", None)  # Don't expose internal field
                if in_grace:
                    info["status"] = "restarting"
                running.append(self._attach_meta(entry, info))
        return running

    @staticmethod
    def _attach_meta(env_dir: Path, info: dict) -> dict:
        """Read env_meta.json and attach branch/commit to a running-list entry."""
        meta_file = env_dir / "env_meta.json"
        info.setdefault("branch", "")
        info.setdefault("commit", "")
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                info["branch"] = meta.get("comfyui_branch", "")
                info["commit"] = meta.get("comfyui_commit", "")
            except Exception:
                pass
        return info
