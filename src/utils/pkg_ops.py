"""Package-manager dispatch: route to uv_ops or pip_ops based on config."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from src.utils import pip_ops, uv_ops


def run_install(
    venv_path: str,
    args: list,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Run a package install command via uv or pip."""
    if package_manager == "uv":
        uv_binary = uv_ops.ensure_uv(tools_dir, uv_version)
        venv_python = pip_ops.get_venv_python(venv_path)
        uv_ops.run_uv_pip(
            uv_binary=uv_binary,
            venv_python=venv_python,
            args=args,
            progress_callback=progress_callback,
        )
        return
    pip_ops.run_pip_with_progress(
        venv_path, args, progress_callback=progress_callback,
    )


def freeze(
    venv_path: str,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
) -> dict:
    if package_manager == "uv":
        uv_binary = uv_ops.ensure_uv(tools_dir, uv_version)
        venv_python = pip_ops.get_venv_python(venv_path)
        return uv_ops.uv_freeze(uv_binary, venv_python)
    return pip_ops.freeze(venv_path)
