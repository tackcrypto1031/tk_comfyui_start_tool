"""One-shot migrations triggered on app startup."""
from __future__ import annotations

import logging
from pathlib import Path

from src.core.torch_pack import TorchPackManager
from src.models.environment import Environment

logger = logging.getLogger(__name__)

_MARKER_NAME = "migration_0.4.0.done"


def migrate_env_meta_0_4_0(config: dict) -> None:
    """Backfill torch_pack + installed_addons on all existing environments.

    Safe to call repeatedly: short-circuits after a marker file is created.
    """
    base_dir = Path(config.get("base_dir", "."))
    marker = base_dir / "tools" / _MARKER_NAME
    if marker.exists():
        return

    envs_dir = Path(config["environments_dir"])
    if not envs_dir.exists():
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("done", encoding="utf-8")
        return

    mgr = TorchPackManager(
        shipped_path=base_dir / "data" / "torch_packs.json",
        remote_path=base_dir / "tools" / "torch_packs_remote.json",
    )
    packs = mgr.list_packs()
    # Pre-0.4.0 registry was 5 ids; use a static set since the dynamic
    # registry now requires config and this migration is post-marker anyway.
    known_addon_ids = {"sage-attention", "flash-attention", "insightface", "nunchaku", "trellis2"}

    for entry in envs_dir.iterdir():
        meta = entry / "env_meta.json"
        if not meta.exists():
            continue
        try:
            env = Environment.load_meta(str(entry))
        except Exception as exc:
            logger.warning("Skipping unreadable env %s: %s", entry.name, exc)
            continue

        changed = False
        # Backfill torch_pack
        if env.torch_pack is None and env.pytorch_version:
            ver_base = env.pytorch_version.split("+")[0].strip()
            for p in packs:
                if p.torch == ver_base and p.cuda_tag == env.cuda_tag:
                    env.torch_pack = p.id
                    changed = True
                    break

        # Backfill installed_addons via disk scan
        if not env.installed_addons:
            custom_nodes_dir = entry / "ComfyUI" / "custom_nodes"
            if custom_nodes_dir.exists():
                for child in custom_nodes_dir.iterdir():
                    if child.is_dir() and child.name in known_addon_ids:
                        env.installed_addons.append({
                            "id": child.name,
                            "installed_at": env.created_at,
                            "torch_pack_at_install": env.torch_pack,
                        })
                        changed = True

        if changed:
            env.save_meta()

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("done", encoding="utf-8")
