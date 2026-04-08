"""Tests for fs_ops utility functions."""
import json
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
