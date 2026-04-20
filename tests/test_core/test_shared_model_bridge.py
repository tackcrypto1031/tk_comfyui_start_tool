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


def _make_env(tmp_path, name="env"):
    env = tmp_path / name
    comfy = env / "ComfyUI"
    models = comfy / "models"
    models.mkdir(parents=True)
    # configs/ to ensure exclusion
    (models / "configs").mkdir()
    (models / "configs" / "v1.yaml").write_text("x", encoding="utf-8")
    (env / "env_meta.json").write_text(
        '{"name":"' + name + '","created_at":"2026-04-20T00:00:00","path":"","shared_model_enabled":true}',
        encoding="utf-8",
    )
    return env


def test_enable_creates_junctions_for_active_subdirs(tmp_path):
    shared = tmp_path / "shared"
    bridge = make_bridge(shared)
    env = _make_env(tmp_path)
    (env / "ComfyUI/models/checkpoints").mkdir()
    (env / "ComfyUI/models/checkpoints/a.safetensors").write_bytes(b"A" * 10)

    result = bridge.enable(env)

    assert result.mechanism == "junction"
    assert (shared / "checkpoints/a.safetensors").read_bytes() == b"A" * 10

    from src.utils import fs_ops
    assert fs_ops.is_junction(env / "ComfyUI/models/checkpoints")
    # configs/ must remain a real directory
    assert not fs_ops.is_junction(env / "ComfyUI/models/configs")
    assert (env / "ComfyUI/models/configs/v1.yaml").read_text(encoding="utf-8") == "x"


def test_enable_is_idempotent(tmp_path):
    shared = tmp_path / "shared"
    bridge = make_bridge(shared)
    env = _make_env(tmp_path)
    bridge.enable(env)
    result = bridge.enable(env)
    assert result.mechanism == "junction"


def test_enable_resumes_from_migrating_state(tmp_path):
    shared = tmp_path / "shared"
    bridge = make_bridge(shared)
    env = _make_env(tmp_path)
    from src.models.environment import Environment
    e = Environment.load_meta(str(env))
    e.path = str(env)
    e.shared_model_migration_state = "migrating"
    e.save_meta()

    result = bridge.enable(env)
    assert result.mechanism == "junction"

    e2 = Environment.load_meta(str(env))
    assert e2.shared_model_migration_state == "done"


def test_disable_removes_junctions_and_keeps_shared(tmp_path):
    shared = tmp_path / "shared"
    bridge = make_bridge(shared)
    env = _make_env(tmp_path)
    (env / "ComfyUI/models/checkpoints").mkdir()
    (env / "ComfyUI/models/checkpoints/a.safetensors").write_bytes(b"A" * 10)
    bridge.enable(env)

    result = bridge.disable(env)
    assert result.junctions_removed >= 1
    assert (env / "ComfyUI/models/checkpoints").is_dir()
    from src.utils import fs_ops
    assert not fs_ops.is_junction(env / "ComfyUI/models/checkpoints")
    assert (shared / "checkpoints/a.safetensors").read_bytes() == b"A" * 10


def test_attach_subdir_migrates_and_links(tmp_path):
    shared = tmp_path / "shared"
    bridge = make_bridge(shared)
    env = _make_env(tmp_path)
    bridge.enable(env)  # baseline junctions for config subdirs

    # Node created a new subdir not yet in config
    new_sub = env / "ComfyUI/models/insightface"
    new_sub.mkdir()
    (new_sub / "det.onnx").write_bytes(b"O" * 5)

    bridge.attach_subdir(env, "insightface")

    from src.utils import fs_ops
    assert fs_ops.is_junction(new_sub)
    assert (shared / "insightface/det.onnx").read_bytes() == b"O" * 5


def test_verify_repairs_dangling_junction(tmp_path):
    shared = tmp_path / "shared"
    bridge = make_bridge(shared)
    env = _make_env(tmp_path)
    bridge.enable(env)

    from src.utils import fs_ops
    link = env / "ComfyUI/models/checkpoints"
    fs_ops.remove_junction(link)

    report = bridge.verify(env)
    assert fs_ops.is_junction(link)
    assert any("checkpoints" in r for r in report.repaired)


def test_safe_remove_env_removes_junctions_only(tmp_path):
    """safe_remove_env unlinks junctions/symlinks under models/; the caller
    does the actual rmtree so it can supply an onerror handler for Windows
    read-only .git objects."""
    shared = tmp_path / "shared"
    bridge = make_bridge(shared)
    env = _make_env(tmp_path)
    (env / "ComfyUI/models/checkpoints").mkdir()
    (env / "ComfyUI/models/checkpoints/a.safetensors").write_bytes(b"A" * 10)
    bridge.enable(env)

    bridge.safe_remove_env(env)

    # env dir still exists (caller does rmtree); junctions are gone
    assert env.exists()
    from src.utils import fs_ops
    assert not fs_ops.is_junction(env / "ComfyUI/models/checkpoints")
    # Shared content preserved
    assert (shared / "checkpoints/a.safetensors").read_bytes() == b"A" * 10
