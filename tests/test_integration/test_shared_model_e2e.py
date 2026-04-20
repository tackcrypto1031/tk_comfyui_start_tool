"""E2E: simulate node-initiated hardcoded-path downloads and verify
the file actually lands in the shared models folder via junction."""
import platform
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    platform.system() != "Windows",
    reason="Junctions are Windows-only.",
)


def _make_env(root: Path, name: str) -> Path:
    env_dir = root / "envs" / name
    (env_dir / "ComfyUI/models").mkdir(parents=True)
    for sub in ("checkpoints", "loras", "configs"):
        (env_dir / "ComfyUI/models" / sub).mkdir()
    (env_dir / "env_meta.json").write_text(
        f'{{"name":"{name}","created_at":"2026-04-20T00:00:00","shared_model_enabled":false}}',
        encoding="utf-8",
    )
    return env_dir


def _make_mgr(root: Path):
    from src.core.env_manager import EnvManager
    return EnvManager({
        "environments_dir": str(root / "envs"),
        "models_dir": str(root / "shared"),
        "snapshots_dir": str(root / "snapshots"),
        "shared_model_mode": "default",
        "custom_model_path": "",
        "model_subdirs": ["checkpoints", "loras", "configs"],
        "shared_model_subdirs_excluded": ["configs"],
    })


def test_hardcoded_write_in_env_a_visible_from_env_b(tmp_path):
    mgr = _make_mgr(tmp_path)
    env_a = _make_env(tmp_path, "a")
    env_b = _make_env(tmp_path, "b")

    mgr.toggle_shared_model("a", True)
    mgr.toggle_shared_model("b", True)

    # Simulate node hardcoding `ComfyUI/models/checkpoints/foo.safetensors`
    (env_a / "ComfyUI/models/checkpoints/foo.safetensors").write_bytes(b"Z" * 200)

    assert (env_b / "ComfyUI/models/checkpoints/foo.safetensors").read_bytes() == b"Z" * 200


def test_configs_is_not_shared_between_envs(tmp_path):
    mgr = _make_mgr(tmp_path)
    env_a = _make_env(tmp_path, "a")
    env_b = _make_env(tmp_path, "b")
    mgr.toggle_shared_model("a", True)
    mgr.toggle_shared_model("b", True)

    (env_a / "ComfyUI/models/configs/a_only.yaml").write_text("A", encoding="utf-8")
    assert not (env_b / "ComfyUI/models/configs/a_only.yaml").exists()


def test_disable_does_not_delete_shared_files(tmp_path):
    mgr = _make_mgr(tmp_path)
    env_a = _make_env(tmp_path, "a")
    env_b = _make_env(tmp_path, "b")
    mgr.toggle_shared_model("a", True)
    mgr.toggle_shared_model("b", True)
    (env_a / "ComfyUI/models/checkpoints/shared.safetensors").write_bytes(b"S" * 50)

    mgr.toggle_shared_model("a", False)

    assert (tmp_path / "shared/checkpoints/shared.safetensors").exists()
    assert (env_b / "ComfyUI/models/checkpoints/shared.safetensors").exists()


def test_remove_env_preserves_shared(tmp_path):
    mgr = _make_mgr(tmp_path)
    env_a = _make_env(tmp_path, "a")
    mgr.toggle_shared_model("a", True)
    (env_a / "ComfyUI/models/checkpoints/keep.safetensors").write_bytes(b"K" * 50)

    mgr.delete_environment("a", force=True)

    assert not env_a.exists()
    assert (tmp_path / "shared/checkpoints/keep.safetensors").exists()
