"""Auto-update: version check, git pull, pip install, restart."""
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from packaging.version import Version

logger = logging.getLogger("updater")

# Project root (two levels up from src/core/)
_ROOT = Path(__file__).parent.parent.parent

REMOTE_VERSION_URL = (
    "https://raw.githubusercontent.com/"
    "tackcrypto1031/tk_comfyui_start_tool/master/VERSION.json"
)
REMOTE_REPO_URL = "https://github.com/tackcrypto1031/tk_comfyui_start_tool.git"
REMOTE_REF = "master"


def _load_local_version() -> dict:
    """Load local VERSION.json."""
    path = _ROOT / "VERSION.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"version": "0.0.0"}


def _find_git() -> str | None:
    """Find git executable. Prefer tools/git, then system git."""
    tools_git = _ROOT / "tools" / "git" / "cmd" / "git.exe"
    if tools_git.exists():
        return str(tools_git)
    # Try system git
    if shutil.which("git"):
        return "git"
    return None


def _find_python() -> str:
    """Find the embedded Python for pip install."""
    tools_python = _ROOT / "tools" / "python" / "python.exe"
    if tools_python.exists():
        return str(tools_python)
    return sys.executable


def _build_git_env() -> dict:
    """Build environment with bundled git path prepended when available."""
    env = os.environ.copy()
    tools_git_dir = _ROOT / "tools" / "git" / "cmd"
    if tools_git_dir.exists():
        env["PATH"] = str(tools_git_dir) + os.pathsep + env.get("PATH", "")
    return env


def _load_remote_version_via_git(git: str) -> dict | None:
    """Fallback loader: fetch origin/master and read VERSION.json from remote ref."""
    env = _build_git_env()
    has_git_dir = (_ROOT / ".git").exists()
    if has_git_dir:
        fetch_proc = subprocess.run(
            [git, "fetch", "origin", REMOTE_REF, "--quiet"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        if fetch_proc.returncode != 0:
            logger.warning("git fetch for update check failed: %s", (fetch_proc.stderr or "").strip())
            return None

        show_proc = subprocess.run(
            [git, "show", f"origin/{REMOTE_REF}:VERSION.json"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
    else:
        temp_repo = _ROOT / "tools" / "_temp" / "update_check_repo"
        if temp_repo.exists():
            shutil.rmtree(temp_repo, ignore_errors=True)
        temp_repo.mkdir(parents=True, exist_ok=True)

        init_proc = subprocess.run(
            [git, "init"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        if init_proc.returncode != 0:
            logger.warning("git init for update check failed: %s", (init_proc.stderr or "").strip())
            return None

        remote_proc = subprocess.run(
            [git, "remote", "add", "origin", REMOTE_REPO_URL],
            cwd=str(temp_repo),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        if remote_proc.returncode != 0:
            logger.warning("git remote add for update check failed: %s", (remote_proc.stderr or "").strip())
            return None

        fetch_proc = subprocess.run(
            [git, "fetch", "--depth", "1", "origin", REMOTE_REF, "--quiet"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True,
            env=env,
            timeout=45,
        )
        if fetch_proc.returncode != 0:
            logger.warning("git fetch for temp update check failed: %s", (fetch_proc.stderr or "").strip())
            return None

        show_proc = subprocess.run(
            [git, "show", "FETCH_HEAD:VERSION.json"],
            cwd=str(temp_repo),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

    if show_proc.returncode != 0:
        logger.warning("git show remote VERSION.json failed: %s", (show_proc.stderr or "").strip())
        return None

    try:
        remote = json.loads(show_proc.stdout or "{}")
        if remote.get("version"):
            return remote
    except json.JSONDecodeError:
        logger.warning("remote VERSION.json from git is invalid JSON")

    return None


def check_update() -> dict:
    """Check for updates by fetching remote VERSION.json.

    Returns dict with keys:
        has_update (bool), local_version, remote_version,
        changes, release_notes, git_available (bool)
    """
    local = _load_local_version()
    local_ver = local.get("version", "0.0.0")

    git = _find_git()
    result = {
        "has_update": False,
        "local_version": local_ver,
        "remote_version": None,
        "changes": [],
        "release_notes": None,
        "git_available": git is not None,
    }

    remote = None
    try:
        resp = requests.get(REMOTE_VERSION_URL, timeout=10)
        resp.raise_for_status()
        remote = resp.json()
    except Exception as e:
        logger.warning(f"Failed to check remote version: {e}")
        if git:
            remote = _load_remote_version_via_git(git)
            if remote:
                logger.info("Update check fallback succeeded via git remote VERSION.json")

    if not remote:
        return result

    remote_ver = remote.get("version", "0.0.0")
    result["remote_version"] = remote_ver
    result["changes"] = remote.get("changes", [])
    result["changes_i18n"] = remote.get("changes_i18n", None)
    result["release_notes"] = remote.get("release_notes", "")

    try:
        if Version(remote_ver) > Version(local_ver):
            result["has_update"] = True
    except Exception:
        pass

    return result


def do_update(progress_callback=None) -> dict:
    """Execute the update: git pull (or init), pip install.

    Args:
        progress_callback: fn(step: str, percent: int, detail: str)

    Returns dict with success/error info.
    """
    def _progress(step, pct, detail=""):
        if progress_callback:
            progress_callback(step, pct, detail)

    git = _find_git()
    if not git:
        raise RuntimeError("Git not found. Please run install.bat first.")

    has_git_dir = (_ROOT / ".git").exists()

    # Step 1: Pull code
    _progress("pull", 10, "Pulling latest code...")

    env = _build_git_env()

    # Preserve the user's config.json across the pull. Older versions tracked
    # it in git, which caused "local changes would be overwritten" aborts
    # whenever upstream edited config.json. We back it up, discard any tracked
    # dirty state so git pull can proceed, then restore the user's file after.
    config_path = _ROOT / "config.json"
    config_backup: bytes | None = None
    if config_path.exists():
        try:
            config_backup = config_path.read_bytes()
        except OSError as e:
            logger.warning("failed to back up config.json before update: %s", e)

    if has_git_dir and config_backup is not None:
        ls_proc = subprocess.run(
            [git, "ls-files", "--error-unmatch", "config.json"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        if ls_proc.returncode == 0:
            # Tracked upstream — reset to index so pull won't conflict.
            subprocess.run(
                [git, "checkout", "--", "config.json"],
                cwd=str(_ROOT),
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )

    if has_git_dir:
        # Normal git pull
        proc = subprocess.run(
            [git, "pull", "origin", REMOTE_REF],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        if proc.returncode != 0:
            # Restore backup before raising so the user isn't left with
            # upstream defaults overwriting their settings.
            if config_backup is not None:
                try:
                    config_path.write_bytes(config_backup)
                except OSError:
                    pass
            raise RuntimeError(f"git pull failed: {proc.stderr.strip()}")
    else:
        # Convert zip directory to git repo
        subprocess.run(
            [git, "init"],
            cwd=str(_ROOT), capture_output=True, text=True, env=env, timeout=30,
        )
        subprocess.run(
            [git, "remote", "add", "origin",
             REMOTE_REPO_URL],
            cwd=str(_ROOT), capture_output=True, text=True, env=env, timeout=10,
        )
        proc = subprocess.run(
            [git, "fetch", "origin", REMOTE_REF],
            cwd=str(_ROOT), capture_output=True, text=True, env=env, timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git fetch failed: {proc.stderr.strip()}")
        proc = subprocess.run(
            [git, "checkout", "-B", REMOTE_REF, f"origin/{REMOTE_REF}"],
            cwd=str(_ROOT), capture_output=True, text=True, env=env, timeout=30,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            if "would be overwritten by checkout" in stderr.lower():
                raise RuntimeError(
                    "git checkout failed due to local file conflicts. "
                    "Please back up local files and retry update."
                )
            raise RuntimeError(f"git checkout failed: {stderr}")

    # Restore user's config.json after the pull. fs_ops.load_config will fill
    # any new keys from config.default.json on next launch.
    if config_backup is not None:
        try:
            config_path.write_bytes(config_backup)
        except OSError as e:
            logger.warning("failed to restore config.json after update: %s", e)

    _progress("pull", 40, "Code updated.")

    # Step 2: Install dependencies
    _progress("deps", 50, "Installing dependencies...")
    python = _find_python()
    req_path = _ROOT / "requirements.txt"

    if req_path.exists():
        proc = subprocess.run(
            [python, "-m", "pip", "install", "-r", str(req_path), "--quiet"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            logger.warning(f"pip install warnings: {proc.stderr.strip()}")

    _progress("deps", 90, "Dependencies installed.")

    return {"success": True}


def restart_app():
    """Restart the application via start.bat."""
    bat_path = _ROOT / "start.bat"
    if not bat_path.exists():
        raise FileNotFoundError("start.bat not found. Please restart manually.")

    # Launch start.bat as a detached process
    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        cwd=str(_ROOT),
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )

    # Quit the current application
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        app.quit()
