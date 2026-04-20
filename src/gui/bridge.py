"""QWebChannel bridge — exposes Python backend to JS frontend."""
import json
import logging
import traceback
from pathlib import Path
from PySide6.QtCore import QObject, Slot, Signal, QThread
from src.utils.fs_ops import save_config
from src.core.torch_pack import TorchPackManager, switch_pack as _switch_pack
from src.core.addons import install_addon as _install_addon, uninstall_addon as _uninstall_addon
from src.core.addon_registry import AddonRegistry

# Set up file logging for debugging
_log_path = Path(__file__).parent.parent.parent / "debug.log"
logging.basicConfig(
    filename=str(_log_path),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bridge")


class AsyncWorker(QThread):
    """Run a function in a background thread."""
    finished = Signal(str, str)  # (request_id, json_result)

    def __init__(self, request_id: str, fn, *args, **kwargs):
        super().__init__()
        self.request_id = request_id
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished.emit(
                self.request_id,
                json.dumps({"success": True, "data": result}, default=str, ensure_ascii=False),
            )
        except Exception as e:
            logger.error(f"AsyncWorker error [{self.request_id}]: {e}\n{traceback.format_exc()}")
            self.finished.emit(
                self.request_id,
                json.dumps({"error": str(e)}, ensure_ascii=False),
            )


class Bridge(QObject):
    """Bridge between Python backend and JS frontend via QWebChannel."""

    def __init__(self, config: dict, last_rescan_result: dict = None):
        super().__init__()
        self.config = config
        self._workers = []  # prevent GC
        self._result_queue = {}  # request_id → result JSON string
        self._progress_queue = {}  # request_id → [message, message, ...]
        self._last_rescan_result = last_rescan_result  # one-shot, popped on first read

        from src.core.env_manager import EnvManager
        from src.core.comfyui_launcher import ComfyUILauncher
        from src.core.version_controller import VersionController
        from src.core.snapshot_manager import SnapshotManager
        from src.core.diagnostics import DiagnosticsManager

        self.environments_dir = Path(config["environments_dir"])
        self.env_manager = EnvManager(config)
        self.launcher = ComfyUILauncher(config)
        self.version_controller = VersionController(config)
        self.snapshot_manager = SnapshotManager(config)
        self.diagnostics = DiagnosticsManager(config)

    def _run_async(self, request_id: str, fn, *args, **kwargs):
        """Run function in background thread, store result in queue."""
        worker = AsyncWorker(request_id, fn, *args, **kwargs)
        worker.finished.connect(self._on_worker_done)
        self._workers.append(worker)
        worker.start()

    def _on_worker_done(self, request_id: str, result: str):
        logger.debug(f"Worker done [{request_id}]: {result[:200]}")
        self._result_queue[request_id] = result
        self._workers = [w for w in self._workers if w.isRunning()]

    def push_progress(self, request_id: str, step: str, percent: int, detail: str = ""):
        """Push a progress message into the queue for the given request."""
        if request_id not in self._progress_queue:
            self._progress_queue[request_id] = []
        self._progress_queue[request_id].append({
            "step": step, "percent": percent, "detail": detail
        })

    @Slot(str, result=str)
    def poll_progress(self, request_id):
        """Poll for progress messages. Returns JSON array of progress updates."""
        messages = self._progress_queue.pop(request_id, [])
        return json.dumps(messages, ensure_ascii=False)

    @Slot(str, result=str)
    def poll_result(self, request_id):
        """Poll for async operation result. Returns result JSON or {"pending": true}."""
        if request_id in self._result_queue:
            result = self._result_queue.pop(request_id)
            return result
        return json.dumps({"pending": True})

    def _safe_call(self, fn, *args, **kwargs):
        """Wrap synchronous calls with error handling."""
        try:
            result = fn(*args, **kwargs)
            return json.dumps({"success": True, "data": result}, default=str, ensure_ascii=False)
        except Exception as e:
            logger.error(f"_safe_call error: {e}\n{traceback.format_exc()}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── Clipboard ──

    @Slot(str, result=str)
    def copy_to_clipboard(self, text):
        """Copy text to system clipboard."""
        try:
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"copy_to_clipboard error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── Config ──

    @Slot(result=str)
    def get_config(self):
        """Return current config as JSON."""
        return json.dumps(self.config, ensure_ascii=False)

    @Slot(str, str, result=str)
    def set_config(self, key, value):
        """Update a single config key and save to disk."""
        try:
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                parsed = value
            self.config[key] = parsed
            save_config(self.config, "config.json")
            return json.dumps({"data": True}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"set_config error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── Shared Model Config ──

    @Slot(result=str)
    def get_shared_model_config(self):
        """Return shared model configuration."""
        return self._safe_call(lambda: {
            "mode": self.config.get("shared_model_mode", "default"),
            "path": self.config.get("custom_model_path", ""),
            "default_path": str(Path(self.config["models_dir"]).resolve()),
        })

    @Slot(str, str, str, result=str)
    def set_shared_model_config(self, mode, path, sync_environments):
        """Update shared model path config. sync_environments: 'true' or 'false'."""
        def _set():
            sync = sync_environments == 'true'
            result = self.env_manager.set_shared_model_path(mode, path, sync)
            save_config(self.config, "config.json")
            return result
        return self._safe_call(_set)

    @Slot(str, str, result=str)
    def toggle_shared_model(self, env_name, enabled):
        """Toggle shared model for a single environment. enabled: 'true' or 'false'."""
        def _toggle():
            self.env_manager.toggle_shared_model(env_name, enabled == 'true')
            return {"success": True}
        return self._safe_call(_toggle)

    @Slot(str, result=str)
    def toggle_all_shared_model(self, enabled):
        """Toggle shared model for all environments. enabled: 'true' or 'false'."""
        def _toggle():
            count = self.env_manager.toggle_all_shared_model(enabled == 'true')
            return {"count": count}
        return self._safe_call(_toggle)

    @Slot(result=str)
    def rescan_shared_model_subdirs(self):
        """Run a forced rescan + yaml regeneration for all enabled envs."""
        def _rescan():
            self.env_manager.ensure_shared_models_if_safe()
            return self.env_manager.sync_shared_model_subdirs(force_regen=True)
        return self._safe_call(_rescan)

    @Slot(result=str)
    def get_last_rescan_result(self):
        """One-shot consumer of the startup rescan result. Returns {} after first read."""
        if self._last_rescan_result is None:
            return json.dumps({})
        result = self._last_rescan_result
        self._last_rescan_result = None
        return json.dumps(result, ensure_ascii=False)

    @Slot(str, result=str)
    def get_ui_flag(self, key: str) -> str:
        """Return a UI flag value as JSON. Returns 'null' if unset."""
        flags = self.config.get("ui_flags") or {}
        return json.dumps(flags.get(key))

    @Slot(str, str)
    def set_ui_flag(self, key: str, json_value: str) -> None:
        """Set a UI flag (JSON-encoded value) and persist config.json."""
        try:
            value = json.loads(json_value)
        except json.JSONDecodeError:
            value = json_value
        if "ui_flags" not in self.config or not isinstance(self.config.get("ui_flags"), dict):
            self.config["ui_flags"] = {}
        self.config["ui_flags"][key] = value
        save_config(self.config, "config.json")

    @Slot(result=str)
    def browse_folder(self):
        """Open native folder selection dialog."""
        try:
            from PySide6.QtWidgets import QFileDialog, QApplication
            parent = QApplication.activeWindow()
            folder = QFileDialog.getExistingDirectory(parent, "Select Model Directory")
            return json.dumps({"success": True, "data": folder or ""}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"browse_folder error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @Slot(result=str)
    def debug_info(self):
        """Return diagnostic information."""
        import os
        env_dir = Path(self.config["environments_dir"])
        return json.dumps({
            "cwd": os.getcwd(),
            "environments_dir": str(env_dir),
            "environments_dir_abs": str(env_dir.resolve()),
            "environments_dir_exists": env_dir.exists(),
            "models_dir": str(Path(self.config["models_dir"]).resolve()),
            "config_keys": list(self.config.keys()),
        }, ensure_ascii=False)

    # ── Environments (sync: list/get, async: create/delete/clone) ──

    @Slot(result=str)
    def list_environments(self):
        """List all environments. Returns JSON array of env dicts."""
        def _list():
            envs = self.env_manager.list_environments()
            return [e.to_dict() for e in envs]
        return self._safe_call(_list)

    @Slot(str, str, str, str)
    def create_environment(self, request_id, name, branch, commit):
        """Create environment async."""
        commit_val = commit if commit else None
        logger.info(f"create_environment: name={name}, branch={branch}, commit={commit_val}")
        def _create():
            env = self.env_manager.create_environment(
                name, branch=branch, commit=commit_val,
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
            return env.to_dict()
        self._run_async(request_id, _create)

    @Slot(str, str, str)
    def delete_environment(self, request_id, name, force):
        """Delete environment async."""
        def _delete():
            self.env_manager.delete_environment(name, force=(force == "true"))
            return {"deleted": name}
        self._run_async(request_id, _delete)

    @Slot(str, str, str)
    def rename_environment(self, request_id, old_name, new_name):
        """Rename environment async."""
        def _rename():
            env = self.env_manager.rename_environment(old_name, new_name)
            return env.to_dict()
        self._run_async(request_id, _rename)

    @Slot(str, str, str)
    def clone_environment(self, request_id, source, new_name):
        """Clone environment async."""
        def _clone():
            env = self.env_manager.clone_environment(
                source, new_name,
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
            return env.to_dict()
        self._run_async(request_id, _clone)

    # ── Versions ──

    @Slot(str)
    def list_remote_versions(self, request_id):
        """Fetch remote tags and branches (async). Returns via poll_result."""
        self._run_async(request_id, self.version_controller.list_remote_versions)

    @Slot(str, result=str)
    def list_commits(self, env_name):
        """List recent commits for env. Returns JSON array."""
        return self._safe_call(self.version_controller.list_commits, env_name)

    @Slot(str, str, str)
    def switch_version(self, request_id, env_name, ref):
        """Switch version async."""
        def _switch():
            self.version_controller.switch_version(env_name, ref)
            return {"switched": ref}
        self._run_async(request_id, _switch)

    @Slot(str, str)
    def update_comfyui(self, request_id, env_name):
        """Update ComfyUI async."""
        def _update():
            self.version_controller.update_comfyui(env_name)
            return {"updated": env_name}
        self._run_async(request_id, _update)

    # ── Launcher ──

    @Slot(str, int, result=str)
    def start_comfyui(self, env_name, port):
        """Start ComfyUI with launch_settings applied as CLI args."""
        from src.models.environment import Environment
        from src.core.launch_config import build_launch_args, extract_launch_params

        try:
            env = Environment.load_meta(str(self.environments_dir / env_name))
            # Use get_effective_launch_settings() so that legacy env_meta.json files
            # that have a raw "listen" IP but no "listen_enabled" key are migrated
            # correctly (listen_enabled is derived from the listen string).  A plain
            # {**LAUNCH_SETTINGS_DEFAULTS, **env.launch_settings} merge would return
            # listen_enabled=False for those envs, silently falling back to localhost.
            settings = env.get_effective_launch_settings()
            extra_args = build_launch_args(settings)
            params = extract_launch_params(settings)

            # Port: UI input takes precedence; fall back to settings if UI sends 0
            effective_port = int(port) if int(port) != 0 else params["port"]
            auto_open = params["auto_open"]

            return self._safe_call(
                self.launcher.start, env_name, effective_port, extra_args, auto_open
            )
        except FileNotFoundError:
            # Fallback: no env_meta.json — launch with defaults
            return self._safe_call(self.launcher.start, env_name, int(port))

    @Slot(str, result=str)
    def stop_comfyui(self, env_name):
        """Stop ComfyUI."""
        return self._safe_call(self.launcher.stop, env_name)

    @Slot(str, result=str)
    def get_launch_status(self, env_name):
        """Get launch status. Returns JSON {status, pid, port}."""
        return self._safe_call(self.launcher.get_status, env_name)

    @Slot(result=str)
    def list_running(self):
        """List all running ComfyUI instances."""
        return self._safe_call(self.launcher.list_running)

    # ── Launch Settings ──

    @Slot(str, result=str)
    def get_launch_settings(self, env_name):
        """Get merged launch_settings for an environment (defaults + stored)."""
        from src.models.environment import Environment, LAUNCH_SETTINGS_DEFAULTS
        try:
            env = Environment.load_meta(str(self.environments_dir / env_name))
            settings = {**LAUNCH_SETTINGS_DEFAULTS, **env.launch_settings}
            return json.dumps({"data": settings}, ensure_ascii=False)
        except FileNotFoundError:
            return json.dumps({"data": dict(LAUNCH_SETTINGS_DEFAULTS)}, ensure_ascii=False)

    @Slot(str, str, result=str)
    def save_launch_settings(self, env_name, settings_json):
        """Save launch_settings to env_meta.json."""
        from src.models.environment import Environment
        try:
            settings = json.loads(settings_json)
            env = Environment.load_meta(str(self.environments_dir / env_name))
            env.launch_settings = settings
            env.save_meta()
            return json.dumps({"data": {"saved": True}}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"save_launch_settings error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── Diagnostics ──

    @Slot(str, str)
    def check_dependencies(self, request_id, env_name):
        """Check environment dependency health (async)."""
        self._run_async(request_id, self.diagnostics.check_dependencies, env_name)

    @Slot(str, str)
    def check_conflicts(self, request_id, env_name):
        """Check for package conflicts (async)."""
        self._run_async(request_id, self.diagnostics.check_conflicts, env_name)

    @Slot(str, str)
    def check_duplicate_nodes(self, request_id, env_name):
        """Scan for duplicate NODE_CLASS_MAPPINGS (async)."""
        self._run_async(request_id, self.diagnostics.check_duplicate_nodes, env_name)

    @Slot(str, str, str)
    def fix_missing_dependencies(self, request_id, env_name, packages_json):
        """Install missing packages (async)."""
        packages = json.loads(packages_json)
        self._run_async(request_id, self.diagnostics.install_missing_packages, env_name, packages)

    @Slot(int, result=str)
    def open_browser(self, port):
        """Open browser to the running env's URL.

        If the running env was started with --listen on a non-loopback IP,
        list_running() reports a lan_url — we open that so the address bar
        shows an IP another machine can reach. Otherwise fall back to
        localhost.
        """
        import webbrowser
        try:
            target = f"http://localhost:{port}"
            try:
                for entry in self.launcher.list_running() or []:
                    if entry.get("port") == port and entry.get("lan_url"):
                        target = entry["lan_url"]
                        break
            except Exception:
                pass  # any lookup error → keep localhost fallback
            webbrowser.open(target)
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ── Snapshots ──

    @Slot(str, result=str)
    def list_snapshots(self, env_name):
        """List snapshots for environment."""
        def _list():
            snaps = self.snapshot_manager.list_snapshots(env_name)
            return [
                {
                    "id": s.id,
                    "env_name": s.env_name,
                    "created_at": s.created_at,
                    "trigger": s.trigger,
                    "comfyui_commit": s.comfyui_commit,
                    "python_version": s.python_version,
                    "cuda_version": s.cuda_version,
                }
                for s in snaps
            ]
        return self._safe_call(_list)

    @Slot(str, str, result=str)
    def create_snapshot(self, env_name, trigger):
        """Create snapshot. Returns snapshot info."""
        def _create():
            snap = self.snapshot_manager.create_snapshot(
                env_name, trigger=trigger or "manual"
            )
            return {"id": snap.id, "env_name": snap.env_name, "created_at": snap.created_at}
        return self._safe_call(_create)

    @Slot(str, str, str)
    def restore_snapshot(self, request_id, env_name, snapshot_id):
        """Restore snapshot async (reinstalls packages)."""
        def _restore():
            self.snapshot_manager.restore_snapshot(
                env_name, snapshot_id,
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
            return {"restored": snapshot_id}
        self._run_async(request_id, _restore)

    @Slot(str, str, result=str)
    def delete_snapshot(self, env_name, snapshot_id):
        """Delete a snapshot."""
        return self._safe_call(self.snapshot_manager.delete_snapshot, env_name, snapshot_id)

    # ── Plugin Analysis ──

    @Slot(str, str, str)
    def analyze_plugin(self, request_id, env_name, plugin_path):
        """Analyze plugin conflicts async."""
        from src.core.conflict_analyzer import ConflictAnalyzer
        analyzer = ConflictAnalyzer(self.config)

        def _analyze():
            report = analyzer.analyze(env_name, plugin_path)
            return {
                "plugin_name": report.plugin_name,
                "risk_level": report.risk_level.value,
                "summary": report.summary,
                "recommendations": report.recommendations,
                "conflicts": [
                    {
                        "package": c.package,
                        "current_version": c.current_version,
                        "required_version": c.required_version,
                        "change_type": c.change_type,
                        "risk_level": c.risk_level.value,
                        "is_critical": c.is_critical,
                    }
                    for c in report.conflicts
                ],
            }
        self._run_async(request_id, _analyze)

    @Slot(str, result=str)
    def list_plugins(self, env_name):
        """List custom nodes for an environment. Returns JSON array."""
        return self._safe_call(self.env_manager.list_custom_nodes, env_name)

    @Slot(str, str, str)
    def install_plugin(self, request_id, env_name, git_url):
        """Install a custom node from a git URL async."""
        def _install():
            return self.env_manager.install_custom_node(
                env_name, git_url,
                progress_callback=lambda step, detail="":
                    self.push_progress(request_id, step, 0, detail),
            )
        self._run_async(request_id, _install)

    @Slot(str, str, str)
    def disable_plugin(self, request_id, env_name, node_name):
        """Disable a custom node async. Raises if ComfyUI is running for this env."""
        def _disable():
            status = self.launcher.get_status(env_name)
            if isinstance(status, dict) and status.get("status") == "running":
                raise RuntimeError(
                    f"ComfyUI is running for environment '{env_name}'. Stop it before disabling plugins."
                )
            return self.env_manager.disable_custom_node(env_name, node_name)
        self._run_async(request_id, _disable)

    @Slot(str, str, str)
    def enable_plugin(self, request_id, env_name, node_name):
        """Enable a custom node async."""
        def _enable():
            return self.env_manager.enable_custom_node(env_name, node_name)
        self._run_async(request_id, _enable)

    @Slot(str, str, str)
    def delete_plugin(self, request_id, env_name, node_name):
        """Delete a custom node async."""
        def _delete():
            return self.env_manager.delete_custom_node(env_name, node_name)
        self._run_async(request_id, _delete)

    @Slot(str, str, str)
    def update_plugin(self, request_id, env_name, node_name):
        """Update a single custom node async."""
        def _update():
            return self.env_manager.update_custom_node(
                env_name, node_name,
                progress_callback=lambda msg:
                    self.push_progress(request_id, msg, 0, ""),
            )
        self._run_async(request_id, _update)

    @Slot(str, str)
    def update_all_plugins(self, request_id, env_name):
        """Update all enabled custom nodes with repo_url async."""
        def _update_all():
            return self.env_manager.update_all_custom_nodes(
                env_name,
                progress_callback=lambda msg:
                    self.push_progress(request_id, msg, 0, ""),
            )
        self._run_async(request_id, _update_all)

    # ── Version Manager (Python/CUDA) ──

    @Slot(result=str)
    def detect_gpu(self):
        """Detect GPU and return recommended CUDA tag."""
        from src.core.version_manager import VersionManager
        logger.info("detect_gpu called")
        vm = VersionManager(self.config)
        result = self._safe_call(vm.detect_gpu)
        logger.info(f"detect_gpu result: {result[:200]}")
        return result

    @Slot(result=str)
    def get_version_lists(self):
        """Return Python versions, CUDA tags, and recommended preset."""
        from src.core.version_manager import VersionManager
        logger.info("get_version_lists called")
        vm = VersionManager(self.config)
        def _get():
            return {
                "python": vm.get_python_versions(),
                "cuda_tags": vm.get_cuda_tags(),
                "cache_info": vm.get_cache_info(),
                "recommended_preset": vm.get_recommended_preset(),
            }
        result = self._safe_call(_get)
        logger.info(f"get_version_lists result: {result[:200]}")
        return result

    @Slot(str)
    def refresh_version_lists(self, request_id):
        """Refresh version lists from official sources (async)."""
        from src.core.version_manager import VersionManager
        vm = VersionManager(self.config)
        def _refresh():
            cache = vm.refresh_all()
            return {
                "python": cache["python"],
                "cuda_tags": cache["cuda_tags"],
                "last_updated": cache["last_updated"],
                "recommended_preset": vm.get_recommended_preset(),
            }
        self._run_async(request_id, _refresh)

    @Slot(str, str, result=str)
    def get_pytorch_versions(self, cuda_tag, python_version):
        """Return available PyTorch versions for a CUDA tag + Python version."""
        from src.core.version_manager import VersionManager
        logger.info(f"get_pytorch_versions: cuda={cuda_tag}, python={python_version}")
        vm = VersionManager(self.config)
        def _get():
            return vm.get_pytorch_versions(cuda_tag, python_version or "")
        result = self._safe_call(_get)
        logger.info(f"get_pytorch_versions result: {result[:200]}")
        return result

    @Slot(str, str, str, str, str, str, str)
    def create_environment_v2(self, request_id, name, branch, commit,
                              python_version, cuda_tag, pytorch_version):
        """Create environment with optional Python/CUDA/PyTorch version (async)."""
        commit_val = commit if commit else None
        python_ver = python_version if python_version else ""
        cuda = cuda_tag if cuda_tag else ""
        pytorch_ver = pytorch_version if pytorch_version else ""

        # Expand recommended preset sentinel
        if python_ver == "__recommended__":
            from src.core.version_manager import VersionManager
            preset = VersionManager(self.config).get_recommended_preset()
            python_ver = preset["python_version"]
            cuda = preset["cuda_tag"]
            pytorch_ver = preset["pytorch_version"]

        logger.info(
            f"create_environment_v2: name={name}, branch={branch}, "
            f"python={python_ver}, cuda={cuda}, pytorch={pytorch_ver}"
        )
        def _create():
            # Download custom Python if needed
            if python_ver:
                from src.core.version_manager import VersionManager
                vm = VersionManager(self.config)
                bundled = self.env_manager._get_bundled_python_version()
                if python_ver != bundled:
                    versions = vm.get_python_versions()
                    match = next(
                        (v for v in versions if v["version"] == python_ver),
                        None,
                    )
                    if match and match.get("url"):
                        vm.download_python(
                            python_ver, match["url"], match.get("sha256", ""),
                            progress_callback=lambda msg:
                                self.push_progress(request_id, "python_download", 2, msg),
                        )
            env = self.env_manager.create_environment(
                name, branch=branch, commit=commit_val,
                python_version=python_ver, cuda_tag=cuda,
                pytorch_version=pytorch_ver,
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
            return env.to_dict()
        self._run_async(request_id, _create)

    @Slot(str, str, str)
    def reinstall_pytorch(self, request_id, env_name, cuda_tag):
        """Reinstall PyTorch with different CUDA version (async)."""
        from src.core.version_manager import VersionManager
        vm = VersionManager(self.config)
        def _reinstall():
            return vm.reinstall_pytorch(
                env_name, cuda_tag,
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
        self._run_async(request_id, _reinstall)

    # ── Log Export ──

    @Slot(str, result=str)
    def export_log(self, env_name):
        """Export comfyui.log for the given environment via a save-file dialog."""
        import shutil
        from datetime import datetime
        from PySide6.QtWidgets import QFileDialog, QApplication

        def _export():
            envs = self.env_manager.list_environments()
            env = next((e for e in envs if e.name == env_name), None)
            if not env:
                raise ValueError(f"Environment not found: {env_name}")

            log_path = Path(env.path) / "comfyui.log"
            if not log_path.exists():
                raise FileNotFoundError("no_log")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"comfyui_log_{env_name}_{timestamp}.log"

            parent = QApplication.activeWindow()
            save_path, _ = QFileDialog.getSaveFileName(
                parent, "Export Log", default_name, "Log Files (*.log);;All Files (*)"
            )
            if not save_path:
                return {"cancelled": True}

            shutil.copy2(str(log_path), save_path)
            return {"exported": save_path}

        return self._safe_call(_export)

    # ── Updater ──

    @Slot(result=str)
    def check_update(self):
        """Check for available updates. Returns JSON with version info."""
        from src.core.updater import check_update
        return self._safe_call(check_update)

    @Slot(str)
    def do_update(self, request_id):
        """Execute update (git pull + pip install) async."""
        from src.core.updater import do_update
        def _update():
            return do_update(
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
        self._run_async(request_id, _update)

    @Slot(result=str)
    def restart_app(self):
        """Restart the application via start.bat."""
        from src.core.updater import restart_app
        try:
            restart_app()
            return json.dumps({"success": True})
        except Exception as e:
            logger.error(f"restart_app error: {e}")
            return json.dumps({"error": str(e)})

    # ── Utility ──

    ALLOWED_SUBFOLDERS = {"output", "models", "custom_nodes", ""}

    @Slot(str, str, result=str)
    def open_folder(self, env_name, subfolder):
        """Open a subfolder of a ComfyUI environment in the system file manager."""
        import os, platform
        def _open():
            if subfolder not in self.ALLOWED_SUBFOLDERS:
                raise ValueError(f"Subfolder not allowed: {subfolder}")
            envs = self.env_manager.list_environments()
            env = next((e for e in envs if e.name == env_name), None)
            if not env:
                raise ValueError(f"Environment not found: {env_name}")
            # When opening the models folder and this environment has shared models
            # enabled, redirect to the active shared model path (default or custom).
            if subfolder == "models" and env.shared_model_enabled:
                resolved = self.env_manager._resolve_model_path().resolve()
            else:
                target = Path(env.path) / "ComfyUI" / subfolder if subfolder else Path(env.path) / "ComfyUI"
                resolved = target.resolve()
                env_root = Path(env.path).resolve()
                if not resolved.is_relative_to(env_root):
                    raise ValueError("Path escapes environment boundary")
            if not resolved.exists():
                raise FileNotFoundError(f"Folder '{subfolder or 'root'}' not found in environment '{env_name}'")
            if not resolved.is_dir():
                raise ValueError(f"Path '{subfolder or 'root'}' is not a directory in environment '{env_name}'")
            if platform.system() == "Windows":
                os.startfile(str(resolved))
            elif platform.system() == "Darwin":
                import subprocess
                subprocess.Popen(["open", str(resolved)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(resolved)])
            return {"opened": str(resolved)}
        return self._safe_call(_open)

    @Slot(str, result=str)
    def open_url(self, url):
        """Open a URL in the default browser. Only http/https allowed."""
        import webbrowser
        def _open():
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Only http/https URLs are allowed: {url}")
            webbrowser.open(url)
            return {"opened": url}
        return self._safe_call(_open)

    # ── Torch-Pack / Addons / Recommended-Env ──

    def _torch_pack_mgr(self) -> TorchPackManager:
        base = Path(self.config.get("base_dir", "."))
        return TorchPackManager(
            shipped_path=base / "data" / "torch_packs.json",
            remote_path=base / "tools" / "torch_packs_remote.json",
        )

    def _addon_registry(self) -> AddonRegistry:
        base_dir = Path(self.config.get("base_dir", "."))
        return AddonRegistry(
            shipped_path=base_dir / "data" / "addons.json",
            remote_path=base_dir / "tools" / "addons_remote.json",
            override_path=base_dir / "tools" / "addons_override.json",
        )

    @Slot(result=str)
    def list_torch_packs(self) -> str:
        """Return all Torch-Packs from shipped (or remote-override) list."""
        try:
            mgr = self._torch_pack_mgr()
            packs = [
                {
                    "id": p.id, "label": p.label, "torch": p.torch,
                    "torchvision": p.torchvision, "torchaudio": p.torchaudio,
                    "cuda_tag": p.cuda_tag, "min_driver": p.min_driver,
                    "recommended": p.recommended,
                }
                for p in mgr.list_packs()
            ]
            return json.dumps({"ok": True, "packs": packs})
        except Exception as exc:
            logger.error(f"list_torch_packs error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(result=str)
    def refresh_torch_packs(self) -> str:
        """Fetch remote torch_packs.json and write to tools/torch_packs_remote.json."""
        try:
            return json.dumps(self._torch_pack_mgr().refresh_remote())
        except Exception as exc:
            logger.error(f"refresh_torch_packs error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str, str)
    def switch_torch_pack(
        self, request_id: str, env_name: str, target_pack_id: str,
    ) -> None:
        """Switch an environment to a different Torch-Pack (async).

        confirm_addon_removal is always True via this bridge entry-point;
        the frontend must confirm before calling.
        Uses the async request_id pattern — poll via poll_result().
        """
        def _switch():
            return _switch_pack(
                config=self.config,
                env_name=env_name,
                target_pack_id=target_pack_id,
                confirm_addon_removal=True,
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
        self._run_async(request_id, _switch)

    @Slot(str, str, str, str)
    def switch_pack_and_install_addon(
        self, request_id: str, env_name: str,
        target_pack_id: str, addon_id: str,
    ) -> None:
        """Two-stage: switch Pack, then install addon. Async.

        Progress 0-60% is the switch; 60-100% is the install.
        """
        def _do():
            base_dir = Path(self.config.get("base_dir", "."))
            mgr = self._torch_pack_mgr()
            uv_version = mgr.get_recommended_uv_version() or "0.9.7"
            pkg_mgr = self.config.get("package_manager", "uv")
            env_dir = self.environments_dir / env_name

            # Stage 1: switch (0-60%)
            def _stage1(step, pct, detail=""):
                scaled = int(pct * 0.6)
                self.push_progress(request_id, f"switch:{step}", scaled, detail)

            switch_result = _switch_pack(
                config=self.config, env_name=env_name,
                target_pack_id=target_pack_id,
                confirm_addon_removal=True,
                progress_callback=_stage1,
            )
            if not switch_result.get("ok"):
                return {
                    "ok": False, "noop": False,
                    "removed_addons": switch_result.get("removed_addons", []),
                    "installed_addon": None,
                    "failed_at": "switch",
                    "error": switch_result.get("error", ""),
                }

            # Stage 2: install addon (60-100%)
            self.push_progress(request_id, "install:start", 60,
                               f"Installing {addon_id}...")

            def _stage2(msg):
                text = msg if isinstance(msg, str) else str(msg)
                self.push_progress(request_id, "install:progress", 80, text)

            try:
                _install_addon(
                    self.config, addon_id, env_dir,
                    base_dir / "tools", uv_version, pkg_mgr,
                    progress_callback=_stage2,
                )
            except Exception as exc:
                return {
                    "ok": False, "noop": False,
                    "removed_addons": switch_result.get("removed_addons", []),
                    "installed_addon": None,
                    "failed_at": "install",
                    "error": str(exc),
                }

            self.push_progress(request_id, "done", 100, "Switch + install complete.")
            return {
                "ok": True, "noop": switch_result.get("noop", False),
                "removed_addons": switch_result.get("removed_addons", []),
                "installed_addon": addon_id,
                "failed_at": "",
                "error": "",
            }

        self._run_async(request_id, _do)

    @Slot(str, str, "QVariantList")
    def reinstall_addons(
        self, request_id: str, env_name: str, addon_ids,
    ) -> None:
        """Reinstall a batch of add-ons. Per-id success reported; does not abort on failure."""
        def _do():
            base_dir = Path(self.config.get("base_dir", "."))
            mgr = self._torch_pack_mgr()
            uv_version = mgr.get_recommended_uv_version() or "0.9.7"
            pkg_mgr = self.config.get("package_manager", "uv")
            env_dir = self.environments_dir / env_name
            total = max(len(addon_ids), 1)
            results = []
            for idx, aid in enumerate(addon_ids):
                pct = int((idx / total) * 100)
                self.push_progress(request_id, "reinstall", pct, f"Installing {aid}...")
                try:
                    _install_addon(
                        self.config, str(aid), env_dir,
                        base_dir / "tools", uv_version, pkg_mgr,
                    )
                    results.append({"id": str(aid), "ok": True, "error": ""})
                except Exception as exc:
                    results.append({"id": str(aid), "ok": False, "error": str(exc)})
            self.push_progress(request_id, "done", 100, f"Reinstalled {len(addon_ids)} add-ons.")
            return {"results": results}
        self._run_async(request_id, _do)

    @Slot(result=str)
    def list_addons(self) -> str:
        """Return the effective add-on registry (shipped + remote + override merged)."""
        try:
            items = []
            for a in self._addon_registry().list_addons():
                items.append({
                    "id": a.id, "label": a.label, "description": a.description,
                    "kind": a.kind,
                    "compatible_packs": list(a.compatible_packs),
                    "wheels_by_pack": dict(a.wheels_by_pack) if a.wheels_by_pack else None,
                    "requires_compile": a.requires_compile,
                    "pack_pinned": a.pack_pinned,
                    "risk_note": a.risk_note,
                })
            return json.dumps({"ok": True, "addons": items}, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"list_addons error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str, str)
    def install_addon(self, request_id: str, env_name: str, addon_id: str) -> None:
        """Install an add-on into an env (async)."""
        def _do():
            env_dir = self.environments_dir / env_name
            base_dir = Path(self.config.get("base_dir", "."))
            mgr = self._torch_pack_mgr()
            uv_version = mgr.get_recommended_uv_version() or "0.9.7"
            pkg_mgr = self.config.get("package_manager", "uv")
            return _install_addon(
                self.config, addon_id, env_dir, base_dir / "tools",
                uv_version, pkg_mgr,
                progress_callback=lambda msg: self.push_progress(
                    request_id, "install", 60, msg if isinstance(msg, str) else str(msg)
                ),
            )
        self._run_async(request_id, _do)

    @Slot(str, str, str)
    def uninstall_addon(self, request_id: str, env_name: str, addon_id: str) -> None:
        """Uninstall an add-on from an env (async)."""
        def _do():
            env_dir = self.environments_dir / env_name
            base_dir = Path(self.config.get("base_dir", "."))
            mgr = self._torch_pack_mgr()
            uv_version = mgr.get_recommended_uv_version() or "0.9.7"
            pkg_mgr = self.config.get("package_manager", "uv")
            _uninstall_addon(
                self.config, addon_id, env_dir, base_dir / "tools",
                uv_version, pkg_mgr,
            )
            return {"ok": True, "id": addon_id}
        self._run_async(request_id, _do)

    @Slot(result=str)
    def detect_gpu_for_recommended(self) -> str:
        """Pre-flight GPU check used by the Create Recommended dialog."""
        try:
            from src.core.version_manager import VersionManager
            gpu = VersionManager(self.config).detect_gpu()
            mgr = self._torch_pack_mgr()
            pack = mgr.select_pack_for_gpu(gpu)
            return json.dumps({
                "ok": True,
                "has_gpu": gpu.get("has_gpu", False),
                "driver_version": gpu.get("cuda_driver_version", ""),
                "recommended_pack_id": pack.id if pack else None,
                "recommended_pack_label": pack.label if pack else None,
            })
        except Exception as exc:
            logger.error(f"detect_gpu_for_recommended error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str, str)
    def create_recommended_env(
        self, request_id: str, name: str, selected_addon_ids_json: str,
    ) -> None:
        """Create a recommended environment with GPU-selected Torch-Pack (async).

        selected_addon_ids_json: JSON-encoded list of add-on ids to install.
        Uses the async request_id pattern — poll via poll_result().
        # TODO(async): already wired into the request_id pattern used by create_environment.
        """
        def _create():
            addon_ids = json.loads(selected_addon_ids_json or "[]")
            from src.core.env_manager import EnvManager
            env = EnvManager(self.config).create_recommended(
                name=name,
                selected_addon_ids=addon_ids,
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
            return {
                "ok": True,
                "name": env.name,
                "torch_pack": env.torch_pack,
                "failed_addons": getattr(env, "failed_addons", []),
            }
        self._run_async(request_id, _create)
