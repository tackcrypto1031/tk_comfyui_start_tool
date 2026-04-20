import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.shared_model_bridge import SharedModelBridge


pytestmark = pytest.mark.skipif(
    platform.system() != "Windows",
    reason="shared_model_bridge is Windows-specific.",
)


def make_bridge(shared_path: Path, excluded=None):
    config = {
        "model_subdirs": ["checkpoints", "loras", "configs"],
        "shared_model_subdirs_excluded": excluded or ["configs"],
    }
    resolver = lambda: shared_path
    return SharedModelBridge(config, resolver)


def test_detect_capability_same_volume_returns_junction(tmp_path):
    env_path = tmp_path / "env"
    env_path.mkdir()
    shared = tmp_path / "shared"
    shared.mkdir()
    bridge = make_bridge(shared)

    assert bridge.detect_capability(shared, env_path) == "junction"


def test_detect_capability_cross_volume_falls_back_to_yaml(tmp_path, monkeypatch):
    env_path = tmp_path / "env"
    env_path.mkdir()
    shared = tmp_path / "shared"
    shared.mkdir()
    bridge = make_bridge(shared)
    monkeypatch.setattr("src.core.shared_model_bridge.fs_ops.same_volume", lambda a, b: False)
    monkeypatch.setattr("src.core.shared_model_bridge.fs_ops.create_symlink_dir",
                        lambda a, b: (_ for _ in ()).throw(OSError("no Dev Mode")))

    assert bridge.detect_capability(shared, env_path) == "yaml_only"


def test_migrate_files_moves_when_shared_empty(tmp_path):
    bridge = make_bridge(tmp_path / "shared")
    env_sub = tmp_path / "env/models/checkpoints"
    shared_sub = tmp_path / "shared/checkpoints"
    env_sub.mkdir(parents=True)
    shared_sub.mkdir(parents=True)
    (env_sub / "model.safetensors").write_bytes(b"A" * 100)

    result = bridge.migrate_files(env_sub, shared_sub)

    assert (shared_sub / "model.safetensors").read_bytes() == b"A" * 100
    assert not (env_sub / "model.safetensors").exists()
    assert result["migrated"] == 1


def test_migrate_files_skips_identical_size_mtime(tmp_path):
    bridge = make_bridge(tmp_path / "shared")
    env_sub = tmp_path / "env/models/loras"
    shared_sub = tmp_path / "shared/loras"
    env_sub.mkdir(parents=True)
    shared_sub.mkdir(parents=True)
    data = b"L" * 50
    (env_sub / "lora.safetensors").write_bytes(data)
    (shared_sub / "lora.safetensors").write_bytes(data)
    import os
    mtime = (shared_sub / "lora.safetensors").stat().st_mtime
    os.utime(env_sub / "lora.safetensors", (mtime, mtime))

    result = bridge.migrate_files(env_sub, shared_sub)

    assert not (env_sub / "lora.safetensors").exists()
    assert result["skipped_identical"] == 1


def test_migrate_files_different_size_renames_env_copy(tmp_path):
    bridge = make_bridge(tmp_path / "shared")
    env_sub = tmp_path / "env/models/vae"
    shared_sub = tmp_path / "shared/vae"
    env_sub.mkdir(parents=True)
    shared_sub.mkdir(parents=True)
    (env_sub / "vae.safetensors").write_bytes(b"X" * 50)
    (shared_sub / "vae.safetensors").write_bytes(b"Y" * 30)

    result = bridge.migrate_files(env_sub, shared_sub)

    assert (shared_sub / "vae.safetensors").read_bytes() == b"Y" * 30
    assert (shared_sub / "vae.envlocal.safetensors").read_bytes() == b"X" * 50
    assert not (env_sub / "vae.safetensors").exists()
    assert result["renamed"] == 1


def test_migrate_files_same_size_different_hash_renames(tmp_path):
    bridge = make_bridge(tmp_path / "shared")
    env_sub = tmp_path / "env/models/controlnet"
    shared_sub = tmp_path / "shared/controlnet"
    env_sub.mkdir(parents=True)
    shared_sub.mkdir(parents=True)
    (env_sub / "cn.safetensors").write_bytes(b"AB" * 50)
    (shared_sub / "cn.safetensors").write_bytes(b"CD" * 50)
    import os, time
    now = time.time()
    os.utime(shared_sub / "cn.safetensors", (now - 100, now - 100))
    os.utime(env_sub / "cn.safetensors", (now, now))

    result = bridge.migrate_files(env_sub, shared_sub)

    assert (shared_sub / "cn.envlocal.safetensors").read_bytes() == b"AB" * 50
    assert result["renamed"] == 1


def test_migrate_files_deletes_put_here_placeholder(tmp_path):
    bridge = make_bridge(tmp_path / "shared")
    env_sub = tmp_path / "env/models/checkpoints"
    shared_sub = tmp_path / "shared/checkpoints"
    env_sub.mkdir(parents=True)
    shared_sub.mkdir(parents=True)
    (env_sub / "put_checkpoints_here").write_text("", encoding="utf-8")

    bridge.migrate_files(env_sub, shared_sub)

    assert not (env_sub / "put_checkpoints_here").exists()
    assert not (shared_sub / "put_checkpoints_here").exists()
