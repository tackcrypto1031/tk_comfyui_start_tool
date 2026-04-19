"""uv (Astral) binary management and invocation wrappers."""
from __future__ import annotations

import io
import logging
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_SUBPROCESS_KWARGS = {}
if sys.platform == "win32":
    _SUBPROCESS_KWARGS["creationflags"] = subprocess.CREATE_NO_WINDOW

_WINDOWS_ASSET = "uv-x86_64-pc-windows-msvc.zip"


def uv_path(tools_dir: Path) -> Path:
    """Return the expected uv.exe path under tools_dir."""
    exe = "uv.exe" if sys.platform == "win32" else "uv"
    return Path(tools_dir) / "uv" / exe


def ensure_uv(tools_dir: Path, version: str) -> Path:
    """Ensure tools/uv/uv.exe exists; download if missing. Return the path."""
    dest = uv_path(tools_dir)
    if dest.exists():
        return dest
    _download_uv_binary(dest, version)
    if not dest.exists():
        raise RuntimeError(f"uv binary not found at {dest} after download")
    return dest


def _download_uv_binary(dest: Path, version: str) -> None:
    """Download the Windows zip from Astral releases and extract uv.exe."""
    if sys.platform != "win32":
        raise NotImplementedError("Non-Windows uv download not implemented")
    url = (
        f"https://github.com/astral-sh/uv/releases/download/"
        f"{version}/{_WINDOWS_ASSET}"
    )
    logger.info("Downloading uv %s from %s", version, url)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for member in zf.namelist():
            if member.endswith("uv.exe"):
                with zf.open(member) as src, open(dest, "wb") as out:
                    out.write(src.read())
                return
    raise RuntimeError("uv.exe not found in downloaded zip")
