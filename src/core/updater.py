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


def check_update() -> dict:
    """Check for updates by fetching remote VERSION.json.

    Returns dict with keys:
        has_update (bool), local_version, remote_version,
        codename, changes, release_notes, git_available (bool)
    """
    local = _load_local_version()
    local_ver = local.get("version", "0.0.0")

    result = {
        "has_update": False,
        "local_version": local_ver,
        "local_codename": local.get("codename", ""),
        "remote_version": None,
        "codename": None,
        "changes": [],
        "release_notes": None,
        "git_available": _find_git() is not None,
    }

    try:
        resp = requests.get(REMOTE_VERSION_URL, timeout=10)
        resp.raise_for_status()
        remote = resp.json()
    except Exception as e:
        logger.warning(f"Failed to check remote version: {e}")
        return result

    remote_ver = remote.get("version", "0.0.0")
    result["remote_version"] = remote_ver
    result["codename"] = remote.get("codename", "")
    result["changes"] = remote.get("changes", [])
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

    env = os.environ.copy()
    # Ensure tools/git is in PATH for git operations
    tools_git_dir = _ROOT / "tools" / "git" / "cmd"
    if tools_git_dir.exists():
        env["PATH"] = str(tools_git_dir) + os.pathsep + env.get("PATH", "")

    if has_git_dir:
        # Normal git pull
        proc = subprocess.run(
            [git, "pull", "origin", "master"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git pull failed: {proc.stderr.strip()}")
    else:
        # Convert zip directory to git repo
        subprocess.run(
            [git, "init"],
            cwd=str(_ROOT), capture_output=True, text=True, env=env, timeout=30,
        )
        subprocess.run(
            [git, "remote", "add", "origin",
             "https://github.com/tackcrypto1031/tk_comfyui_start_tool.git"],
            cwd=str(_ROOT), capture_output=True, text=True, env=env, timeout=10,
        )
        proc = subprocess.run(
            [git, "fetch", "origin", "master"],
            cwd=str(_ROOT), capture_output=True, text=True, env=env, timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git fetch failed: {proc.stderr.strip()}")
        proc = subprocess.run(
            [git, "checkout", "-B", "master", "origin/master"],
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
