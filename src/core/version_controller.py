"""Version controller - manage ComfyUI and custom node versions."""
import time
import threading
from pathlib import Path
from typing import List

from src.models.environment import Environment
from src.core.snapshot_manager import SnapshotManager
from src.utils import git_ops, pip_ops

# Cache TTL in seconds
_CACHE_TTL = 300  # 5 minutes


class VersionController:
    """Controls versioning of ComfyUI and custom nodes."""

    def __init__(self, config: dict):
        self.config = config
        self.environments_dir = Path(config["environments_dir"])
        self.snapshot_manager = SnapshotManager(config)
        self._versions_cache = None   # cached {tags, branches}
        self._cache_time = 0          # timestamp of last cache
        self._cache_lock = threading.Lock()

    def list_commits(self, env_name: str, target: str = "comfyui", count: int = 20) -> List[dict]:
        """List recent commits for ComfyUI or a custom node."""
        repo_path = self._get_repo_path(env_name, target)
        return git_ops.get_log(str(repo_path), count=count)

    def list_branches(self, env_name: str, target: str = "comfyui") -> List[str]:
        """List branches for ComfyUI or a custom node."""
        repo_path = self._get_repo_path(env_name, target)
        return git_ops.get_branches(str(repo_path))

    def switch_version(self, env_name: str, ref: str, target: str = "comfyui") -> None:
        """Switch version with auto-snapshot protection."""
        self.snapshot_manager.create_snapshot(env_name, trigger="version_switch")
        repo_path = self._get_repo_path(env_name, target)
        git_ops.checkout(str(repo_path), ref)
        if target == "comfyui":
            self._reinstall_requirements(env_name)
        self._update_env_meta(env_name)

    def update_comfyui(self, env_name: str) -> None:
        """Pull latest and reinstall."""
        self.snapshot_manager.create_snapshot(env_name, trigger="update")
        repo_path = self._get_repo_path(env_name, "comfyui")
        git_ops.pull(str(repo_path))
        self._reinstall_requirements(env_name)
        self._update_env_meta(env_name)

    def list_remote_versions(self, repo_url: str = None) -> dict:
        """Fetch available tags and branches.
        Returns cached data if available and fresh; refreshes in background if stale."""
        with self._cache_lock:
            now = time.time()
            if self._versions_cache and (now - self._cache_time) < _CACHE_TTL:
                return self._versions_cache

        # No cache or expired — fetch synchronously (first call only blocks)
        result = self._fetch_remote_versions(repo_url)
        with self._cache_lock:
            self._versions_cache = result
            self._cache_time = time.time()
        return result

    def _fetch_remote_versions(self, repo_url: str = None) -> dict:
        """Actually fetch tags and branches from remote."""
        url = repo_url or self.config.get("comfyui_repo_url", "https://github.com/comfyanonymous/ComfyUI.git")

        # Try to use a local clone for tag dates
        tags = self._get_tags_with_dates()
        if not tags:
            # Fallback: ls-remote (no dates) — normalize shape to include both date and hash
            raw_tags = git_ops.list_remote_tags(url)
            tags = [{"name": t["name"], "date": "", "hash": t["hash"]} for t in raw_tags]

        branches = git_ops.list_remote_branches(url)
        return {"tags": tags, "branches": branches}

    def refresh_versions_cache(self, repo_url: str = None) -> None:
        """Refresh the versions cache in background thread."""
        def _refresh():
            try:
                result = self._fetch_remote_versions(repo_url)
                with self._cache_lock:
                    self._versions_cache = result
                    self._cache_time = time.time()
            except Exception:
                pass  # silent fail — stale cache is better than no cache
        threading.Thread(target=_refresh, daemon=True).start()

    def _get_tags_with_dates(self) -> list:
        """Try to get tags with dates from any local ComfyUI clone."""
        if not self.environments_dir.exists():
            return []
        for env_dir in self.environments_dir.iterdir():
            comfyui_path = env_dir / "ComfyUI"
            if comfyui_path.exists() and (comfyui_path / ".git").exists():
                try:
                    import git as gitmodule
                    repo = gitmodule.Repo(str(comfyui_path))
                    repo.remotes.origin.fetch(tags=True)
                    return git_ops.list_tags_with_dates(str(comfyui_path))
                except Exception:
                    continue
        return []

    def list_local_tags(self, env_name: str, target: str = "comfyui") -> list:
        """List tags available in a local repo."""
        repo_path = self._get_repo_path(env_name, target)
        return git_ops.list_tags(str(repo_path))

    def _get_repo_path(self, env_name: str, target: str) -> Path:
        """Resolve the repository path for a given target."""
        env_dir = self.environments_dir / env_name
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment '{env_name}' not found")
        if target == "comfyui":
            return env_dir / "ComfyUI"
        return env_dir / "ComfyUI" / "custom_nodes" / target

    def _reinstall_requirements(self, env_name: str) -> None:
        """Reinstall requirements.txt if it exists."""
        env_dir = self.environments_dir / env_name
        req_path = env_dir / "ComfyUI" / "requirements.txt"
        if req_path.exists():
            pip_ops.run_pip(str(env_dir / "venv"), ["install", "-r", str(req_path)])

    def _update_env_meta(self, env_name: str) -> None:
        """Update env_meta.json with current commit and pip freeze."""
        env_dir = self.environments_dir / env_name
        env = Environment.load_meta(str(env_dir))
        env.comfyui_commit = git_ops.get_current_commit(str(env_dir / "ComfyUI"))
        env.pip_freeze = pip_ops.freeze(str(env_dir / "venv"))
        env.save_meta()
