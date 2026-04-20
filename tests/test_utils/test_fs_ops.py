"""Tests for fs_ops utility functions."""
import json
import os
import pytest
from pathlib import Path

from src.utils.fs_ops import load_config, save_config, ensure_dirs, get_default_config


class TestLoadConfig:
    """Test config loading."""

    def test_load_existing_config(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_data = {"version": "0.1.0", "default_env": "main"}
        config_path.write_text(json.dumps(config_data), encoding="utf-8")
        result = load_config(str(config_path))
        assert result["version"] == "0.1.0"
        assert result["default_env"] == "main"

    def test_load_missing_config_creates_default(self, tmp_path):
        config_path = tmp_path / "config.json"
        result = load_config(str(config_path))
        assert result["default_env"] == "main"
        assert config_path.exists()

    def test_load_config_fills_missing_keys(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
        result = load_config(str(config_path))
        assert "default_env" in result
        assert "default_port" in result

    def test_load_config_preserves_custom_values(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_data = {"version": "0.1.0", "default_port": 9999}
        config_path.write_text(json.dumps(config_data), encoding="utf-8")
        result = load_config(str(config_path))
        assert result["default_port"] == 9999


class TestSaveConfig:
    """Test config saving."""

    def test_save_config(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_data = {"version": "0.1.0", "default_env": "main"}
        save_config(config_data, str(config_path))
        assert config_path.exists()
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
        assert loaded["version"] == "0.1.0"

    def test_save_config_overwrites(self, tmp_path):
        config_path = tmp_path / "config.json"
        save_config({"version": "0.1.0"}, str(config_path))
        save_config({"version": "0.2.0"}, str(config_path))
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
        assert loaded["version"] == "0.2.0"


class TestEnsureDirs:
    """Test directory creation."""

    def test_ensure_dirs_creates_all(self, tmp_path):
        config = {
            "base_dir": str(tmp_path),
            "environments_dir": str(tmp_path / "environments"),
            "models_dir": str(tmp_path / "models"),
            "snapshots_dir": str(tmp_path / "snapshots"),
            "model_subdirs": ["checkpoints", "loras", "vae"],
        }
        ensure_dirs(config)
        assert (tmp_path / "environments").is_dir()
        assert (tmp_path / "models").is_dir()
        assert (tmp_path / "snapshots").is_dir()
        assert (tmp_path / "models" / "checkpoints").is_dir()
        assert (tmp_path / "models" / "loras").is_dir()
        assert (tmp_path / "models" / "vae").is_dir()

    def test_ensure_dirs_idempotent(self, tmp_path):
        config = {
            "base_dir": str(tmp_path),
            "environments_dir": str(tmp_path / "environments"),
            "models_dir": str(tmp_path / "models"),
            "snapshots_dir": str(tmp_path / "snapshots"),
            "model_subdirs": ["checkpoints"],
        }
        ensure_dirs(config)
        ensure_dirs(config)  # Should not raise
        assert (tmp_path / "environments").is_dir()


class TestGetDefaultConfig:
    """Test default config generation."""

    def test_default_config_has_required_keys(self):
        config = get_default_config()
        assert "default_env" in config
        assert "comfyui_repo_url" in config
        assert "model_subdirs" in config
        assert "conflict_analyzer" in config

    def test_default_config_values(self):
        config = get_default_config()
        assert config["default_port"] == 8188
        assert config["comfyui_repo_url"] == "https://github.com/comfyanonymous/ComfyUI.git"

    def test_default_model_subdirs_has_stock_comfyui_set(self):
        config = get_default_config()
        subdirs = set(config["model_subdirs"])
        expected = {
            "audio_encoders", "checkpoints", "clip", "clip_vision", "configs",
            "controlnet", "diffusers", "diffusion_models", "embeddings", "gligen",
            "hypernetworks", "latent_upscale_models", "loras", "model_patches",
            "photomaker", "style_models", "text_encoders", "unet",
            "upscale_models", "vae", "vae_approx",
        }
        assert subdirs == expected
        assert len(config["model_subdirs"]) == 21

    def test_default_model_subdirs_all_lowercase(self):
        config = get_default_config()
        for name in config["model_subdirs"]:
            assert name == name.lower(), f"Non-lowercase default subdir: {name}"


def test_default_config_has_ui_flags():
    cfg = get_default_config()
    assert "ui_flags" in cfg
    assert cfg["ui_flags"] == {}


import platform

from src.utils import fs_ops

_skip_non_windows = pytest.mark.skipif(
    platform.system() != "Windows",
    reason="Junction primitives are Windows-specific (NTFS reparse points).",
)


@_skip_non_windows
def test_create_junction_and_detect(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    (target / "hello.txt").write_text("hi", encoding="utf-8")

    link = tmp_path / "link"
    fs_ops.create_junction(link, target)

    assert fs_ops.is_junction(link) is True
    assert (link / "hello.txt").read_text(encoding="utf-8") == "hi"


@_skip_non_windows
def test_remove_junction_preserves_target(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    (target / "keep.txt").write_text("k", encoding="utf-8")

    link = tmp_path / "link"
    fs_ops.create_junction(link, target)
    fs_ops.remove_junction(link)

    assert not link.exists()
    assert (target / "keep.txt").read_text(encoding="utf-8") == "k"


@_skip_non_windows
def test_is_junction_false_for_real_dir(tmp_path):
    d = tmp_path / "real"
    d.mkdir()
    assert fs_ops.is_junction(d) is False


def test_same_volume_same_drive(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert fs_ops.same_volume(a, b) is True


def test_same_volume_different_drive():
    c = Path("C:/")
    d = Path("D:/")
    if not d.exists():
        pytest.skip("D:/ not available on this runner")
    assert fs_ops.same_volume(c, d) is False


def test_create_symlink_dir_falls_back_when_unsupported(tmp_path, monkeypatch):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"

    def _raise(*_args, **_kwargs):
        raise OSError(1314, "A required privilege is not held by the client")

    monkeypatch.setattr(os, "symlink", _raise)
    with pytest.raises(OSError):
        fs_ops.create_symlink_dir(link, target)
