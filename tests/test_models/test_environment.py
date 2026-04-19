"""Tests for Environment data model."""
import json
import pytest
from pathlib import Path

from src.models.environment import Environment


class TestEnvironmentConstruction:
    """Test Environment dataclass creation."""

    def test_create_with_required_fields(self):
        env = Environment(name="main", created_at="2026-04-04T10:00:00+08:00")
        assert env.name == "main"
        assert env.created_at == "2026-04-04T10:00:00+08:00"

    def test_default_values(self):
        env = Environment(name="test", created_at="2026-04-04T10:00:00+08:00")
        assert env.comfyui_commit == ""
        assert env.comfyui_branch == "master"
        assert env.python_version == ""
        assert env.pip_freeze == {}
        assert env.custom_nodes == []
        assert env.snapshots == []
        assert env.parent_env is None
        assert env.path == ""
        assert env.merge_history == []

    def test_create_with_parent_env(self):
        env = Environment(
            name="clone-20260404",
            created_at="2026-04-04T10:00:00+08:00",
            parent_env="main",
        )
        assert env.parent_env == "main"

    def test_create_with_all_fields(self, sample_env_meta):
        env = Environment(**sample_env_meta)
        assert env.name == "main"
        assert env.pip_freeze == {"torch": "2.3.1", "numpy": "1.26.4"}


class TestEnvironmentSerialization:
    """Test to_dict / from_dict round-trip."""

    def test_to_dict(self):
        env = Environment(name="main", created_at="2026-04-04T10:00:00+08:00")
        d = env.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "main"
        assert "merge_history" in d

    def test_from_dict(self, sample_env_meta):
        env = Environment.from_dict(sample_env_meta)
        assert env.name == "main"
        assert env.comfyui_commit == "abc1234"

    def test_round_trip(self, sample_env_meta):
        env = Environment.from_dict(sample_env_meta)
        d = env.to_dict()
        env2 = Environment.from_dict(d)
        assert env == env2

    def test_from_dict_missing_optional_fields(self):
        minimal = {"name": "test", "created_at": "2026-04-04T10:00:00+08:00"}
        env = Environment.from_dict(minimal)
        assert env.name == "test"
        assert env.merge_history == []


class TestEnvironmentPersistence:
    """Test save_meta / load_meta."""

    def test_save_meta(self, tmp_path):
        env = Environment(
            name="main",
            created_at="2026-04-04T10:00:00+08:00",
            path=str(tmp_path / "main"),
        )
        (tmp_path / "main").mkdir()
        env.save_meta()
        meta_path = tmp_path / "main" / "env_meta.json"
        assert meta_path.exists()
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        assert data["name"] == "main"

    def test_load_meta(self, tmp_path):
        env_dir = tmp_path / "main"
        env_dir.mkdir()
        meta = {
            "name": "main",
            "created_at": "2026-04-04T10:00:00+08:00",
            "comfyui_commit": "abc1234",
            "comfyui_branch": "master",
            "python_version": "3.11.9",
            "pip_freeze": {},
            "custom_nodes": [],
            "snapshots": [],
            "parent_env": None,
            "merge_history": [],
        }
        (env_dir / "env_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        env = Environment.load_meta(str(env_dir))
        assert env.name == "main"
        assert env.comfyui_commit == "abc1234"
        assert env.path == str(env_dir)

    def test_load_meta_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Environment.load_meta(str(tmp_path / "nonexistent"))


class TestListenEnabledMigration:
    """Tests for listen_enabled field in LAUNCH_SETTINGS_DEFAULTS and migration."""

    def test_listen_enabled_default_false(self):
        from src.models.environment import LAUNCH_SETTINGS_DEFAULTS
        assert LAUNCH_SETTINGS_DEFAULTS["listen_enabled"] is False

    def test_from_dict_migrates_old_listen_string_to_enabled(self):
        from src.models.environment import Environment, LAUNCH_SETTINGS_DEFAULTS
        data = {
            "name": "legacy",
            "created_at": "2026-04-04T10:00:00+08:00",
            "comfyui_commit": "abc",
            "python_version": "3.10",
            "cuda_version": "12.1",
            "launch_settings": {"listen": "0.0.0.0"},
        }
        env = Environment.from_dict(data)
        effective = env.get_effective_launch_settings()
        assert effective["listen_enabled"] is True
        assert effective["listen"] == "0.0.0.0"

    def test_from_dict_loopback_listen_string_does_not_enable(self):
        from src.models.environment import Environment, LAUNCH_SETTINGS_DEFAULTS
        data = {
            "name": "legacy",
            "created_at": "2026-04-04T10:00:00+08:00",
            "comfyui_commit": "abc",
            "python_version": "3.10",
            "cuda_version": "12.1",
            "launch_settings": {"listen": "127.0.0.1"},
        }
        env = Environment.from_dict(data)
        effective = env.get_effective_launch_settings()
        assert effective["listen_enabled"] is False
        assert effective["listen"] == ""


class TestNewFields:
    """Tests for torch_pack and installed_addons fields."""

    def test_environment_new_fields_default_values(self):
        env = Environment(name="e1", created_at="2026-04-19T00:00:00Z")
        assert env.torch_pack is None
        assert env.installed_addons == []

    def test_environment_roundtrip_preserves_new_fields(self, tmp_path):
        env_dir = tmp_path / "e1"
        env_dir.mkdir()
        env = Environment(
            name="e1",
            created_at="2026-04-19T00:00:00Z",
            path=str(env_dir),
            torch_pack="torch-2.9.1-cu130",
            installed_addons=[
                {
                    "id": "sage-attention",
                    "installed_at": "2026-04-19T00:00:00Z",
                    "torch_pack_at_install": "torch-2.9.1-cu130",
                }
            ],
        )
        env.save_meta()
        reloaded = Environment.load_meta(str(env_dir))
        assert reloaded.torch_pack == "torch-2.9.1-cu130"
        assert reloaded.installed_addons == env.installed_addons

    def test_environment_loads_legacy_meta_without_new_fields(self, tmp_path):
        env_dir = tmp_path / "legacy"
        env_dir.mkdir()
        meta = env_dir / "env_meta.json"
        meta.write_text(
            '{"name":"legacy","created_at":"2026-01-01T00:00:00Z"}',
            encoding="utf-8",
        )
        env = Environment.load_meta(str(env_dir))
        assert env.torch_pack is None
        assert env.installed_addons == []
