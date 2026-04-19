"""Curated add-on registry for the recommended creation flow."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from src.models.environment import Environment
from src.utils import git_ops, pip_ops, pkg_ops


@dataclass(frozen=True)
class Addon:
    id: str
    label: str
    description: str
    install_method: Literal["pip_package", "git_clone"]
    pip_package: Optional[str] = None
    repo: Optional[str] = None
    post_install_cmd: Optional[list] = None
    requires_cuda: bool = False
    requires_compile: bool = False
    risk_note: Optional[str] = None


ADDONS: list[Addon] = [
    Addon(
        id="sage-attention",
        label="SageAttention v2",
        description="Attention acceleration — larger batch, lower VRAM",
        install_method="git_clone",
        repo="https://github.com/thu-ml/SageAttention.git",
        post_install_cmd=["pip", "install", "-e", "."],
        requires_cuda=True,
        requires_compile=True,
        risk_note="Requires CUDA toolkit (nvcc); first install compiles",
    ),
    Addon(
        id="flash-attention",
        label="FlashAttention",
        description="Fast attention implementation",
        install_method="git_clone",
        repo="https://github.com/Dao-AILab/flash-attention.git",
        post_install_cmd=["pip", "install", "-e", ".", "--no-build-isolation"],
        requires_cuda=True,
        requires_compile=True,
    ),
    Addon(
        id="insightface",
        label="InsightFace",
        description="Face nodes (IPAdapter FaceID, ReActor)",
        install_method="pip_package",
        pip_package="insightface",
        requires_cuda=False,
        requires_compile=False,
    ),
    Addon(
        id="nunchaku",
        label="Nunchaku",
        description="Quantized inference (4-bit FLUX)",
        install_method="git_clone",
        repo="https://github.com/mit-han-lab/nunchaku.git",
        post_install_cmd=["pip", "install", "-e", "."],
        requires_cuda=True,
        requires_compile=True,
    ),
    Addon(
        id="trellis2",
        label="Trellis 2.0",
        description="3D generation nodes",
        install_method="git_clone",
        repo="https://github.com/microsoft/TRELLIS.git",
        post_install_cmd=["pip", "install", "-r", "requirements.txt"],
        requires_cuda=True,
        requires_compile=True,
    ),
]


def find_addon(addon_id: str) -> Optional[Addon]:
    for a in ADDONS:
        if a.id == addon_id:
            return a
    return None


# ---------------------------------------------------------------------------
# Install / Uninstall
# ---------------------------------------------------------------------------


def install_addon(
    addon_id: str,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback=None,
) -> dict:
    """Install a single add-on into an environment. Returns {id, method}.

    Raises if the add-on id is unknown. Package-install failures bubble up.
    Updates env_meta.json.installed_addons on success.
    """
    addon = find_addon(addon_id)
    if addon is None:
        raise ValueError(f"Unknown addon: {addon_id}")

    env_dir = Path(env_dir)
    venv_path = env_dir / "venv"

    if addon.install_method == "pip_package":
        pkg_ops.run_install(
            venv_path=str(venv_path),
            args=["install", addon.pip_package],
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )
    elif addon.install_method == "git_clone":
        _install_git_clone_addon(
            addon, env_dir, tools_dir, uv_version, package_manager,
            progress_callback,
        )
    else:  # pragma: no cover — guarded by Literal
        raise ValueError(f"Unknown install_method: {addon.install_method}")

    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": addon_id,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "torch_pack_at_install": env.torch_pack,
    })
    env.save_meta()
    return {"id": addon_id, "method": addon.install_method}


def _install_git_clone_addon(
    addon: Addon,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str,
    progress_callback,
) -> None:
    """Clone add-on repo, install its requirements, then run post_install_cmd."""
    node_dir = env_dir / "ComfyUI" / "custom_nodes" / addon.id
    node_dir.parent.mkdir(parents=True, exist_ok=True)

    git_ops.clone_repo(
        addon.repo, str(node_dir), branch=None,
        progress_callback=progress_callback,
    )

    # 1) install requirements.txt if present
    req = node_dir / "requirements.txt"
    if req.exists():
        pkg_ops.run_install(
            venv_path=str(env_dir / "venv"),
            args=["install", "-r", str(req)],
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )

    # 2) post_install_cmd wins over install.py
    if addon.post_install_cmd:
        _run_post_install_cmd(
            cmd=addon.post_install_cmd,
            cwd=node_dir,
            env_dir=env_dir,
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )
    else:
        install_py = node_dir / "install.py"
        if install_py.exists():
            _run_install_py(install_py, env_dir, progress_callback)


def _run_post_install_cmd(
    cmd: list, cwd: Path, env_dir: Path, tools_dir: Path,
    uv_version: str, package_manager: str, progress_callback,
) -> None:
    """Run an add-on's post_install_cmd; translate 'pip' → active package manager."""
    if cmd and cmd[0] == "pip":
        # Portable "pip" token → route through pkg_ops dispatch
        args = cmd[1:]
        resolved = []
        for token in args:
            if token in (".", "-e") or token.startswith("-"):
                resolved.append(token)
            elif token == "requirements.txt":
                resolved.append(str((cwd / token).resolve()))
            else:
                resolved.append(token)
        # Editable installs need cwd awareness
        if "-e" in resolved and "." in resolved:
            _run_editable_via_pkg_ops(
                resolved, cwd=cwd, env_dir=env_dir, tools_dir=tools_dir,
                uv_version=uv_version, package_manager=package_manager,
                progress_callback=progress_callback,
            )
            return
        pkg_ops.run_install(
            venv_path=str(env_dir / "venv"),
            args=resolved,
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )
        return
    # Registry only ships "pip"-prefixed post_install_cmds today. If this
    # constraint ever relaxes, add a branch here (and a test) — do not
    # silently shell out.
    raise ValueError(
        f"post_install_cmd must start with the 'pip' token; got {cmd!r}"
    )


def _run_editable_via_pkg_ops(
    args, cwd, env_dir, tools_dir, uv_version, package_manager, progress_callback,
):
    """Editable installs need cwd awareness. Always invoke `python -m pip` from
    the venv with cwd = add-on dir, so "." resolves correctly regardless of
    which package manager the rest of the build uses."""
    python = pip_ops.get_venv_python(str(env_dir / "venv"))
    cmd = [python, "-m", "pip"] + list(args)
    sub_kwargs = {"cwd": str(cwd)}
    if sys.platform == "win32":
        sub_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = subprocess.run(cmd, capture_output=True, text=True, **sub_kwargs)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
        raise RuntimeError(
            f"Editable install failed (exit {proc.returncode}): {' | '.join(tail)}"
        )
    if progress_callback:
        progress_callback(f"Editable install of {cwd.name} complete.")


def _run_install_py(install_py: Path, env_dir: Path, progress_callback) -> None:
    """Legacy fallback: run an add-on's install.py if no post_install_cmd is set."""
    python = pip_ops.get_venv_python(str(env_dir / "venv"))
    sub_kwargs = {"cwd": str(install_py.parent)}
    if sys.platform == "win32":
        sub_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.run([python, str(install_py)], check=True, **sub_kwargs)


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def uninstall_addon(
    addon_id: str,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback=None,
) -> None:
    """Remove an add-on from an env. Reverse of install_addon."""
    addon = find_addon(addon_id)
    if addon is None:
        raise ValueError(f"Unknown addon: {addon_id}")

    env_dir = Path(env_dir)

    if addon.install_method == "pip_package":
        pkg_ops.run_install(
            venv_path=str(env_dir / "venv"),
            args=["uninstall", "-y", addon.pip_package],
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )
    elif addon.install_method == "git_clone":
        node_dir = env_dir / "ComfyUI" / "custom_nodes" / addon.id
        if node_dir.exists():
            def _on_rm_error(func, path, exc_info):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(str(node_dir), onerror=_on_rm_error)

    env = Environment.load_meta(str(env_dir))
    env.installed_addons = [
        a for a in env.installed_addons if a.get("id") != addon_id
    ]
    env.save_meta()
