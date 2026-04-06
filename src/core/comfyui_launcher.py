"""ComfyUI process launcher and lifecycle manager."""
import configparser
import json
import logging
import requests
from pathlib import Path

from src.utils import git_ops, pip_ops, process_manager

logger = logging.getLogger(__name__)

DEFAULT_MANAGER_URL = "https://github.com/Comfy-Org/ComfyUI-Manager.git"
MANAGER_SECURITY_LEVEL = "normal-"


class ComfyUILauncher:
    def __init__(self, config: dict):
        self.config = config
        self.environments_dir = Path(config["environments_dir"])

    @staticmethod
    def _normalize_package_name(name: str) -> str:
        """Normalize package names so hyphen/underscore variants compare equal."""
        return name.strip().lower().replace("_", "-")

    def _has_package(self, installed: dict, package_name: str) -> bool:
        target = self._normalize_package_name(package_name)
        return any(self._normalize_package_name(pkg) == target for pkg in installed)

    def start(self, env_name: str, port: int = 8188, extra_args: list = None,
              auto_open: bool = True) -> dict:
        """Start ComfyUI in the specified environment."""
        env_dir = self.environments_dir / env_name
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment '{env_name}' not found")

        # Prevent duplicate launches in the same environment (sqlite lock/confusing state).
        status = self.get_status(env_name)
        if status.get("status") == "running":
            raise RuntimeError(
                f"Environment '{env_name}' is already running "
                f"(pid={status.get('pid')}, port={status.get('port')})."
            )

        # Ensure comfyui-manager is installed and security level is manager-compatible.
        self._ensure_manager_ready(env_dir)

        # Find available port
        port = process_manager.find_available_port(port)

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
        proc = process_manager.start_process(
            cmd, cwd=str(env_dir / "ComfyUI"), log_file=log_file
        )

        # Save PID
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": proc.pid, "port": port}))

        # Auto-open browser after a short delay
        if auto_open and self.config.get("auto_open_browser", True):
            import threading
            def _open_browser():
                import time
                import webbrowser
                # Wait for ComfyUI to start (check health every 2 seconds, up to 60 seconds)
                for _ in range(30):
                    time.sleep(2)
                    if not process_manager.is_process_running(proc.pid):
                        return  # Process died, don't open browser
                    if self.health_check(port, timeout=2):
                        webbrowser.open(f"http://localhost:{port}")
                        return
            threading.Thread(target=_open_browser, daemon=True).start()

        return {"pid": proc.pid, "port": port, "env_name": env_name}

    def _ensure_manager_ready(self, env_dir: Path) -> None:
        """Ensure manager repo exists and security_level is permissive for local launcher use."""
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

        manager_config = comfyui_dir / "user" / "__manager" / "config.ini"
        self._write_manager_security_config(manager_config)

        # Keep backward compatibility for existing legacy config files.
        legacy_config = comfyui_dir / "user" / "default" / "ComfyUI-Manager" / "config.ini"
        if legacy_config.exists():
            self._write_manager_security_config(legacy_config)

    def _write_manager_security_config(self, config_path: Path) -> None:
        """Write manager security policy without creating legacy folders unnecessarily."""
        config = configparser.ConfigParser()
        if config_path.exists():
            config.read(str(config_path), encoding="utf-8")

        if "default" not in config:
            config["default"] = {}

        config["default"]["security_level"] = MANAGER_SECURITY_LEVEL

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
        data = json.loads(pid_file.read_text())

        stopped = False
        # Try stopping by PID first
        if process_manager.is_process_running(data["pid"]):
            stopped = process_manager.stop_process(data["pid"])

        # Fallback: kill process occupying the port
        if not stopped and "port" in data:
            stopped = process_manager.stop_process_on_port(data["port"])

        pid_file.unlink()

    def health_check(self, port: int, timeout: int = 5) -> bool:
        """Return True if ComfyUI is responding on the given port."""
        try:
            resp = requests.get(f"http://localhost:{port}/", timeout=timeout)
            return resp.status_code == 200
        except requests.ConnectionError:
            return False

    def get_status(self, env_name: str) -> dict:
        """Return status dict for an environment."""
        env_dir = self.environments_dir / env_name
        pid_file = env_dir / ".comfyui.pid"
        if not pid_file.exists():
            return {"status": "stopped", "env_name": env_name}
        data = json.loads(pid_file.read_text())
        running = process_manager.is_process_running(data["pid"])
        if not running and "port" in data:
            running = process_manager.is_port_in_use(data["port"])

        # If process died, clean up pid file
        if not running:
            pid_file.unlink(missing_ok=True)

        result = {"status": "running" if running else "stopped", "env_name": env_name, **data}

        # Include last log lines for debugging
        log_path = env_dir / "comfyui.log"
        if log_path.exists():
            try:
                lines = log_path.read_text(encoding='utf-8', errors='replace').strip().split('\n')
                result["last_log"] = '\n'.join(lines[-10:])  # Last 10 lines
            except Exception:
                pass

        return result

    def list_running(self) -> list:
        """Return list of all running ComfyUI instances."""
        running = []
        if not self.environments_dir.exists():
            return running
        for entry in self.environments_dir.iterdir():
            pid_file = entry / ".comfyui.pid"
            if pid_file.exists():
                data = json.loads(pid_file.read_text())
                # Check by PID first, fallback to port check
                is_running = process_manager.is_process_running(data["pid"])
                if not is_running and "port" in data:
                    is_running = process_manager.is_port_in_use(data["port"])
                if is_running:
                    info = {"env_name": entry.name, **data}
                    # Read version info from env_meta.json
                    meta_file = entry / "env_meta.json"
                    if meta_file.exists():
                        try:
                            meta = json.loads(meta_file.read_text())
                            info["branch"] = meta.get("comfyui_branch", "")
                            info["commit"] = meta.get("comfyui_commit", "")
                        except Exception:
                            info["branch"] = ""
                            info["commit"] = ""
                    else:
                        info["branch"] = ""
                        info["commit"] = ""
                    running.append(info)
        return running
