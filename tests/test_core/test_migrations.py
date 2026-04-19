import json
from datetime import datetime, timezone
from pathlib import Path

from src.core.migrations import migrate_env_meta_0_4_0
from src.models.environment import Environment


def _shipped_packs(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "torch_packs.json").write_text(json.dumps({
        "schema_version": 1, "last_updated": "2026-04-19", "remote_url": "",
        "recommended_python": "3.12.10", "recommended_uv_version": "0.9.7",
        "packs": [
            {"id": "p-new", "label": "L", "torch": "2.9.1",
             "torchvision": "0.24.1", "torchaudio": "2.9.1",
             "cuda_tag": "cu130", "min_driver": 13.0, "recommended": True},
        ],
        "pinned_deps": {},
    }), encoding="utf-8")


def _write_legacy_env(envs_dir, name, cuda_tag, pytorch_version, addons_on_disk=()):
    env_dir = envs_dir / name
    env_dir.mkdir(parents=True)
    (env_dir / "ComfyUI" / "custom_nodes").mkdir(parents=True)
    for addon_name in addons_on_disk:
        (env_dir / "ComfyUI" / "custom_nodes" / addon_name).mkdir()
    env = Environment(
        name=name,
        created_at="2026-01-01T00:00:00Z",
        cuda_tag=cuda_tag,
        pytorch_version=pytorch_version,
        path=str(env_dir),
    )
    env.save_meta()
    return env_dir


def test_backfill_matches_known_pack(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(envs_dir, "e1", "cu130", "2.9.1+cu130")
    config = {
        "environments_dir": str(envs_dir),
        "base_dir": str(tmp_path),
    }
    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e1"))
    assert env.torch_pack == "p-new"


def test_backfill_unknown_version_stays_none(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(envs_dir, "e2", "cu124", "2.5.1+cu124")
    config = {"environments_dir": str(envs_dir), "base_dir": str(tmp_path)}
    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e2"))
    assert env.torch_pack is None


def test_backfill_strips_cuda_suffix(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(envs_dir, "e3", "cu130", "2.9.1")  # no +cu suffix
    config = {"environments_dir": str(envs_dir), "base_dir": str(tmp_path)}
    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e3"))
    assert env.torch_pack == "p-new"


def test_backfill_discovers_addons_on_disk(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(
        envs_dir, "e4", "cu130", "2.9.1",
        addons_on_disk=("sage-attention", "some-random-node"),
    )
    config = {"environments_dir": str(envs_dir), "base_dir": str(tmp_path)}
    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e4"))
    ids = {a["id"] for a in env.installed_addons}
    assert "sage-attention" in ids
    # Unknown dir names are ignored
    assert "some-random-node" not in ids


def test_migration_marker_makes_it_idempotent(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(envs_dir, "e5", "cu130", "2.9.1")
    config = {"environments_dir": str(envs_dir), "base_dir": str(tmp_path)}
    migrate_env_meta_0_4_0(config)

    # Modify env_meta after migration; second run must not touch it
    env = Environment.load_meta(str(envs_dir / "e5"))
    env.torch_pack = "hand-edited"
    env.save_meta()

    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e5"))
    assert env.torch_pack == "hand-edited"
