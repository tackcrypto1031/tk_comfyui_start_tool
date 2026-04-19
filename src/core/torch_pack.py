"""Torch-Pack definitions, GPU-driven selection, remote refresh, and Pack switching."""
from __future__ import annotations

import json
import logging
import requests
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Pack:
    id: str
    label: str
    torch: str
    torchvision: str
    torchaudio: str
    cuda_tag: str
    min_driver: float
    recommended: bool


class TorchPackManager:
    """Loads Torch-Pack data with remote override precedence."""

    def __init__(self, shipped_path: Path, remote_path: Path):
        self.shipped_path = Path(shipped_path)
        self.remote_path = Path(remote_path)
        self._data: Optional[dict] = None

    def load(self) -> dict:
        """Load data, preferring remote when its schema_version matches."""
        if self._data is not None:
            return self._data

        remote = self._read_json(self.remote_path)
        if remote and remote.get("schema_version") == SCHEMA_VERSION:
            self._data = remote
        else:
            if remote is not None:
                logger.warning(
                    "Remote torch_packs.json schema mismatch (got %s, expected %s); using shipped",
                    remote.get("schema_version"), SCHEMA_VERSION,
                )
            self._data = self._read_json(self.shipped_path) or {}
        return self._data

    def list_packs(self) -> list[Pack]:
        """Return all defined Packs as Pack objects."""
        data = self.load()
        return [Pack(**p) for p in data.get("packs", [])]

    def find(self, pack_id: str) -> Optional[Pack]:
        """Return the Pack with the given id, or None if unknown."""
        for p in self.list_packs():
            if p.id == pack_id:
                return p
        return None

    def get_pinned_deps(self) -> dict:
        """Return the global pinned_deps map ({package: version})."""
        return self.load().get("pinned_deps", {})

    def get_recommended_python(self) -> str:
        """Return the Python version recommended for fresh env creation."""
        return self.load().get("recommended_python", "")

    def get_recommended_uv_version(self) -> str:
        """Return the uv binary version to ensure in tools/uv/."""
        return self.load().get("recommended_uv_version", "")

    def get_remote_url(self) -> str:
        """Return the URL used by refresh_remote() to pull updated Pack data."""
        return self.load().get("remote_url", "")

    def select_pack_for_gpu(self, gpu_info: dict) -> Optional[Pack]:
        """Pick the best Pack for a detected GPU, or None if none qualifies."""
        if not gpu_info.get("has_gpu"):
            return None
        raw = gpu_info.get("cuda_driver_version")
        if not raw:
            return None
        try:
            driver = float(raw)
        except (TypeError, ValueError):
            return None
        # Prefer recommended packs, then higher min_driver (newer)
        candidates = sorted(
            self.list_packs(),
            key=lambda p: (not p.recommended, -p.min_driver),
        )
        for p in candidates:
            if driver >= p.min_driver:
                return p
        return None

    def refresh_remote(self, timeout: int = 15) -> dict:
        """Fetch remote torch_packs.json and write to remote_path.

        Returns {"ok": bool, "error": str}. Non-fatal on all failures —
        caller continues with shipped defaults.
        """
        url = self.get_remote_url()
        if not url:
            return {"ok": False, "error": "no remote_url configured"}
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        if payload.get("schema_version") != SCHEMA_VERSION:
            return {
                "ok": False,
                "error": f"schema_version mismatch (got {payload.get('schema_version')})",
            }

        self.remote_path.parent.mkdir(parents=True, exist_ok=True)
        self.remote_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # Invalidate memo so next load sees the new file
        self._data = None
        return {"ok": True, "error": ""}

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None


# ---------------------------------------------------------------------------
# Module-level switch_pack
# ---------------------------------------------------------------------------

import shutil  # noqa: E402 — stdlib, safe to import here

from src.core.addons import find_addon  # noqa: E402
from src.core.snapshot_manager import SnapshotManager  # noqa: E402
from src.models.environment import Environment  # noqa: E402
from src.utils import pkg_ops  # noqa: E402


def switch_pack(
    config: dict,
    env_name: str,
    target_pack_id: str,
    confirm_addon_removal: bool,
    progress_callback=None,
) -> dict:
    """Switch an environment from its current Pack to target_pack_id.

    Returns {
      "ok": bool,
      "noop": bool,
      "removed_addons": list[str],
      "error": str,
    }
    """
    env_dir = Path(config["environments_dir"]) / env_name
    if not env_dir.exists():
        return {"ok": False, "error": f"env '{env_name}' not found",
                "noop": False, "removed_addons": []}

    env = Environment.load_meta(str(env_dir))
    if env.torch_pack == target_pack_id:
        return {"ok": True, "noop": True, "removed_addons": [], "error": ""}

    base_dir = Path(config.get("base_dir", "."))
    mgr = TorchPackManager(
        shipped_path=base_dir / "data" / "torch_packs.json",
        remote_path=base_dir / "tools" / "torch_packs_remote.json",
    )
    target = mgr.find(target_pack_id)
    if target is None:
        return {"ok": False, "error": f"unknown pack '{target_pack_id}'",
                "noop": False, "removed_addons": []}

    # Identify pack-pinned add-ons — wheel/source is bound to the current
    # torch version, so we must uninstall before swapping torch.
    compiled_addons = []
    for entry in env.installed_addons:
        addon = find_addon(entry.get("id", ""))
        if addon and addon.pack_pinned:
            compiled_addons.append(entry["id"])

    if compiled_addons and not confirm_addon_removal:
        return {
            "ok": False,
            "error": (
                f"Pack-pinned add-ons require removal before Pack switch: "
                f"{', '.join(compiled_addons)}. Re-invoke with "
                f"confirm_addon_removal=True."
            ),
            "noop": False,
            "removed_addons": [],
        }

    def _report(step, pct, detail=""):
        if progress_callback:
            progress_callback(step, pct, detail)

    # Auto-snapshot
    _report("snapshot", 5, "Creating pre-switch snapshot...")
    SnapshotManager(config).create_snapshot(env_name, trigger="pack_switch")

    removed_addons: list = []
    venv_path = str(env_dir / "venv")
    tools_dir = base_dir / "tools"
    uv_version = mgr.get_recommended_uv_version() or "0.9.7"
    pkg_mgr = config.get("package_manager", "uv")

    # Remove compiled add-ons
    for aid in compiled_addons:
        _report("addon", 15, f"Removing compiled add-on: {aid}")
        addon = find_addon(aid)
        if addon and addon.kind == "pip" and addon.pip_project_name:
            pkg_ops.run_install(
                venv_path=venv_path,
                args=["uninstall", "-y", addon.pip_project_name],
                tools_dir=tools_dir,
                uv_version=uv_version,
                package_manager=pkg_mgr,
            )
        node_dir = env_dir / "ComfyUI" / "custom_nodes" / aid
        if node_dir.exists():
            shutil.rmtree(str(node_dir), ignore_errors=True)
        env.installed_addons = [
            e for e in env.installed_addons if e.get("id") != aid
        ]
        removed_addons.append(aid)

    # Uninstall current torch trio
    _report("uninstall", 30, "Uninstalling current PyTorch...")
    pkg_ops.run_install(
        venv_path=venv_path,
        args=["uninstall", "-y", "torch", "torchvision", "torchaudio"],
        tools_dir=tools_dir,
        uv_version=uv_version,
        package_manager=pkg_mgr,
    )

    # Install target trio
    _report("install", 55, f"Installing {target.label}...")
    pkg_ops.run_install(
        venv_path=venv_path,
        args=[
            "install",
            f"torch=={target.torch}",
            f"torchvision=={target.torchvision}",
            f"torchaudio=={target.torchaudio}",
            "--index-url", f"https://download.pytorch.org/whl/{target.cuda_tag}",
        ],
        tools_dir=tools_dir,
        uv_version=uv_version,
        package_manager=pkg_mgr,
    )

    # Re-apply pinned deps
    _report("pins", 80, "Re-applying pinned deps...")
    pinned = mgr.get_pinned_deps()
    if pinned:
        pkg_ops.run_install(
            venv_path=venv_path,
            args=["install"] + [f"{k}=={v}" for k, v in pinned.items()],
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=pkg_mgr,
        )

    # Update env_meta
    freeze_data = pkg_ops.freeze(
        venv_path=venv_path,
        tools_dir=tools_dir,
        uv_version=uv_version,
        package_manager=pkg_mgr,
    )
    env.torch_pack = target.id
    env.cuda_tag = target.cuda_tag
    env.pytorch_version = freeze_data.get(
        "torch", f"{target.torch}+{target.cuda_tag}"
    )
    env.pip_freeze = freeze_data
    env.save_meta()

    _report("done", 100, "Pack switch complete.")
    return {
        "ok": True, "noop": False, "removed_addons": removed_addons,
        "error": "",
    }
