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


def run_uv_pip(uv_binary: Path, venv_python: str, args: list,
               progress_callback=None) -> None:
    """Invoke `uv pip <args>` against the given venv python. Streams output.

    Raises RuntimeError with parsed stderr tail on non-zero exit.
    """
    cmd = [str(uv_binary), "pip"] + list(args) + ["--python", str(venv_python)]
    # Move --python to come right after the subcommand name for clarity
    # (uv accepts it anywhere, but this order matches docs).
    sub = args[0] if args else ""
    if sub in ("install", "uninstall", "freeze", "list", "show", "sync"):
        cmd = [str(uv_binary), "pip", sub, "--python", str(venv_python)] + list(args[1:])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **_SUBPROCESS_KWARGS,
    )

    tail: list[str] = []
    for raw in proc.stdout:
        try:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        except AttributeError:
            line = raw.rstrip("\r\n")
        if line:
            tail.append(line)
            if len(tail) > 40:
                tail.pop(0)
            if progress_callback:
                progress_callback(line)
    rc = proc.wait()
    if rc != 0:
        detail = " | ".join(tail[-5:]) if tail else "no output"
        raise RuntimeError(f"uv pip failed (exit {rc}): {detail}")


def uv_freeze(uv_binary: Path, venv_python: str) -> dict:
    """Return `uv pip freeze` as {package: version}."""
    cmd = [str(uv_binary), "pip", "freeze", "--python", str(venv_python)]
    result = subprocess.run(
        cmd, capture_output=True, text=True, **_SUBPROCESS_KWARGS,
    )
    if result.returncode != 0:
        raise RuntimeError(f"uv pip freeze failed: {result.stderr.strip()}")
    packages = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("-e ") or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            packages[name.strip()] = version.strip()
    return packages
