"""QWebChannel bridge — exposes Python backend to JS frontend."""
import json
import logging
import traceback
from pathlib import Path
from PySide6.QtCore import QObject, Slot, Signal, QThread
from src.utils.fs_ops import save_config

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

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._workers = []  # prevent GC
        self._result_queue = {}  # request_id → result JSON string
        self._progress_queue = {}  # request_id → [message, message, ...]

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
        from src.models.environment import Environment, LAUNCH_SETTINGS_DEFAULTS
        from src.core.launch_config import build_launch_args, extract_launch_params

        try:
            env = Environment.load_meta(str(self.environments_dir / env_name))
            settings = {**LAUNCH_SETTINGS_DEFAULTS, **env.launch_settings}
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
        """Open browser to localhost:<port>."""
        import webbrowser
        try:
            webbrowser.open(f"http://localhost:{port}")
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
