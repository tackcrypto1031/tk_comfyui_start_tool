"""Add-on install / uninstall, driven by AddonRegistry."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.core.addon_registry import Addon, AddonRegistry
from src.models.environment import Environment
from src.utils import git_ops, pip_ops, pkg_ops


def _registry(config: dict) -> AddonRegistry:
    base_dir = Path(config.get("base_dir", "."))
    return AddonRegistry(
        shipped_path=base_dir / "data" / "addons.json",
        remote_path=base_dir / "tools" / "addons_remote.json",
        override_path=base_dir / "tools" / "addons_override.json",
    )


class IncompatiblePackError(RuntimeError):
    """Raised when an add-on is installed against a Torch-Pack it doesn't support."""


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def install_addon(
    config: dict,
    addon_id: str,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback=None,
) -> dict:
    """Install a single add-on into an environment. Returns {id, kind}.

    Raises IncompatiblePackError if the env's current Torch-Pack is not in
    the add-on's compatible_packs. Raises ValueError on unknown id.
    Package-install failures bubble up. Updates env_meta.json on success.
    """
    addon = _registry(config).find(addon_id)
    if addon is None:
        raise ValueError(f"Unknown addon: {addon_id}")

    env_dir = Path(env_dir)
    env = Environment.load_meta(str(env_dir))
    current_pack = env.torch_pack or ""

    if current_pack not in addon.compatible_packs:
        raise IncompatiblePackError(
            f"Add-on '{addon_id}' does not support Torch-Pack "
            f"'{current_pack}'. Compatible packs: "
            f"{', '.join(addon.compatible_packs) or '(none)'}"
        )

    if addon.kind == "pip":
        _install_pip_addon(
            addon, current_pack, env_dir, tools_dir, uv_version,
            package_manager, progress_callback,
        )
    elif addon.kind == "custom_node":
        _install_custom_node_addon(
            addon, env_dir, tools_dir, uv_version,
            package_manager, progress_callback,
        )
    else:  # pragma: no cover — guarded by Literal
        raise ValueError(f"Unknown addon kind: {addon.kind}")

    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": addon_id,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "torch_pack_at_install": env.torch_pack,
    })
    env.save_meta()
    return {"id": addon_id, "kind": addon.kind}


def _install_pip_addon(
    addon: Addon, pack_id: str, env_dir: Path, tools_dir: Path,
    uv_version: str, package_manager: str, progress_callback,
) -> None:
    """Prefer a pack-matched wheel URL; fall back to PyPI pip_spec."""
    target = (addon.wheels_by_pack or {}).get(pack_id) or addon.pip_spec
    if not target:
        raise RuntimeError(
            f"Add-on '{addon.id}' has no install target for pack '{pack_id}'"
        )
    pkg_ops.run_install(
        venv_path=str(env_dir / "venv"),
        args=["install", target],
        tools_dir=tools_dir,
        uv_version=uv_version,
        package_manager=package_manager,
        progress_callback=progress_callback,
    )


def _install_custom_node_addon(
    addon: Addon, env_dir: Path, tools_dir: Path,
    uv_version: str, package_manager: str, progress_callback,
) -> None:
    """Clone the add-on's repo at source_ref, install its requirements,
    then run source_post_install."""
    node_dir = env_dir / "ComfyUI" / "custom_nodes" / addon.id
    node_dir.parent.mkdir(parents=True, exist_ok=True)

    git_ops.clone_repo(
        addon.source_repo, str(node_dir),
        branch=addon.source_ref,
        progress_callback=progress_callback,
    )

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

    if addon.source_post_install:
        _run_post_install_cmd(
            cmd=list(addon.source_post_install),
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
        args = cmd[1:]
        resolved = []
        for token in args:
            if token in (".", "-e") or token.startswith("-"):
                resolved.append(token)
            elif token == "requirements.txt":
                resolved.append(str((cwd / token).resolve()))
            else:
                resolved.append(token)
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
    config: dict,
    addon_id: str,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback=None,
) -> None:
    """Remove an add-on from an env. Reverse of install_addon."""
    addon = _registry(config).find(addon_id)
    # Orphan case: unknown id — generic cleanup (remove dir + meta entry)
    if addon is None:
        env = Environment.load_meta(str(env_dir))
        node_dir = Path(env_dir) / "ComfyUI" / "custom_nodes" / addon_id
        if node_dir.exists():
            def _on_rm_error(func, path, exc_info):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(str(node_dir), onerror=_on_rm_error)
        env.installed_addons = [
            a for a in env.installed_addons if a.get("id") != addon_id
        ]
        env.save_meta()
        return

    env_dir = Path(env_dir)

    if addon.kind == "pip" and addon.pip_project_name:
        pkg_ops.run_install(
            venv_path=str(env_dir / "venv"),
            args=["uninstall", "-y", addon.pip_project_name],
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )
    elif addon.kind == "custom_node":
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
