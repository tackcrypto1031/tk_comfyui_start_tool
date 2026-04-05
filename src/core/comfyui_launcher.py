"""ComfyUI process launcher and lifecycle manager."""
import json
import requests
from pathlib import Path

from src.utils import pip_ops, process_manager


class ComfyUILauncher:
    def __init__(self, config: dict):
        self.config = config
        self.environments_dir = Path(config["environments_dir"])

    def start(self, env_name: str, port: int = 8188, extra_args: list = None,
              auto_open: bool = True) -> dict:
        """Start ComfyUI in the specified environment."""
        env_dir = self.environments_dir / env_name
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment '{env_name}' not found")

        # Find available port
        port = process_manager.find_available_port(port)

        # Build command
        python = pip_ops.get_venv_python(str(env_dir / "venv"))
        cmd = [python, "main.py", "--listen", "--port", str(port)]
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

    def stop(self, env_name: str) -> None:
        """Stop a running ComfyUI instance."""
        env_dir = self.environments_dir / env_name
        pid_file = env_dir / ".comfyui.pid"
        if not pid_file.exists():
            raise RuntimeError(f"No running instance found for '{env_name}'")
        data = json.loads(pid_file.read_text())
        process_manager.stop_process(data["pid"])
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
                if process_manager.is_process_running(data["pid"]):
                    running.append({"env_name": entry.name, **data})
        return running
