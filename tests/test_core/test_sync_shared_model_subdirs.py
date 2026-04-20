"""Tests for EnvManager.sync_shared_model_subdirs."""
import json
from pathlib import Path

import pytest

from src.core.env_manager import EnvManager


@pytest.fixture
def manager_with_shared_dir(sample_config, tmp_project):
    """EnvManager with an existing shared models dir containing every configured subdir."""
    shared = Path(sample_config["models_dir"])
    for name in sample_config["model_subdirs"]:
        (shared / name).mkdir(parents=True, exist_ok=True)
    return EnvManager(sample_config)


class TestSyncSharedModelSubdirsEmpty:
    def test_returns_empty_when_nothing_new(self, manager_with_shared_dir):
        result = manager_with_shared_dir.sync_shared_model_subdirs(force_regen=False)
        assert result["added"] == []
        assert result["synced_envs"] == 0
        assert result["skipped"] is False
        assert result["reason"] == ""

    def test_no_config_write_when_nothing_new(self, manager_with_shared_dir, tmp_project):
        config_path = tmp_project / "config.json"
        config_path.write_text(json.dumps(manager_with_shared_dir.config), encoding="utf-8")
        mtime_before = config_path.stat().st_mtime_ns

        manager_with_shared_dir.sync_shared_model_subdirs(force_regen=False)

        assert config_path.stat().st_mtime_ns == mtime_before, "config.json should not be rewritten"


class TestSyncDiscovery:
    def _make_env(self, tmp_project, env_name, extra_subdirs, enabled=True):
        env_dir = tmp_project / "environments" / env_name
        (env_dir / "ComfyUI" / "models").mkdir(parents=True)
        for name in extra_subdirs:
            (env_dir / "ComfyUI" / "models" / name).mkdir()
        meta = {
            "name": env_name,
            "created_at": "2026-04-10T00:00:00+08:00",
            "comfyui_commit": "abc1234",
            "comfyui_branch": "master",
            "python_version": "3.11.9",
            "pip_freeze": {},
            "custom_nodes": [],
            "snapshots": [],
            "parent_env": None,
            "merge_history": [],
            "shared_model_enabled": enabled,
        }
        (env_dir / "env_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        return env_dir

    def test_discovers_new_subdir_from_env_local_models(
        self, sample_config, tmp_project, monkeypatch
    ):
        # Seed shared dir with the configured subdirs (so only the env-only one is "new")
        shared = Path(sample_config["models_dir"])
        for name in sample_config["model_subdirs"]:
            (shared / name).mkdir(parents=True, exist_ok=True)
        self._make_env(tmp_project, "envA", extra_subdirs=["wanvideo"])

        # Stub save_config so the test doesn't touch the real working directory
        written = {}
        def fake_save(cfg, path):
            written["path"] = path
            written["config"] = dict(cfg)
        monkeypatch.setattr("src.utils.fs_ops.save_config", fake_save)

        manager = EnvManager(sample_config)
        result = manager.sync_shared_model_subdirs(force_regen=False)

        assert result["added"] == ["wanvideo"]
        assert (shared / "wanvideo").is_dir()
        assert "wanvideo" in manager.config["model_subdirs"]
        assert written["path"] == "config.json"
        assert "wanvideo" in written["config"]["model_subdirs"]

    def test_regenerates_yaml_only_for_enabled_envs(
        self, sample_config, tmp_project, monkeypatch
    ):
        shared = Path(sample_config["models_dir"])
        for name in sample_config["model_subdirs"]:
            (shared / name).mkdir(parents=True, exist_ok=True)
        self._make_env(tmp_project, "enabled_env", ["wanvideo"], enabled=True)
        self._make_env(tmp_project, "disabled_env", ["ipadapter"], enabled=False)

        monkeypatch.setattr("src.utils.fs_ops.save_config", lambda *a, **k: None)

        manager = EnvManager(sample_config)
        result = manager.sync_shared_model_subdirs(force_regen=False)

        assert set(result["added"]) == {"wanvideo", "ipadapter"}
        assert result["synced_envs"] == 1  # only enabled_env
        enabled_yaml = tmp_project / "environments" / "enabled_env" / "ComfyUI" / "extra_model_paths.yaml"
        disabled_yaml = tmp_project / "environments" / "disabled_env" / "ComfyUI" / "extra_model_paths.yaml"
        assert enabled_yaml.exists()
        assert not disabled_yaml.exists()


class TestSyncNormalization:
    def _make_bare_env(self, tmp_project, name, subdirs):
        env_dir = tmp_project / "environments" / name
        (env_dir / "ComfyUI" / "models").mkdir(parents=True)
        for s in subdirs:
            (env_dir / "ComfyUI" / "models" / s).mkdir()
        (env_dir / "env_meta.json").write_text(
            json.dumps({
                "name": name, "created_at": "2026-04-10T00:00:00+08:00",
                "comfyui_commit": "abc", "comfyui_branch": "master",
                "python_version": "3.11", "pip_freeze": {}, "custom_nodes": [],
                "snapshots": [], "parent_env": None, "merge_history": [],
                "shared_model_enabled": True,
            }, ensure_ascii=False), encoding="utf-8",
        )

    def test_lowercases_discovered_names(self, sample_config, tmp_project, monkeypatch):
        Path(sample_config["models_dir"]).mkdir(parents=True, exist_ok=True)
        for name in sample_config["model_subdirs"]:
            (Path(sample_config["models_dir"]) / name).mkdir(exist_ok=True)
        self._make_bare_env(tmp_project, "env1", ["IPAdapter"])
        monkeypatch.setattr("src.utils.fs_ops.save_config", lambda *a, **k: None)

        manager = EnvManager(sample_config)
        result = manager.sync_shared_model_subdirs(force_regen=False)

        assert "ipadapter" in result["added"]
        assert "IPAdapter" not in result["added"]
        assert (Path(sample_config["models_dir"]) / "ipadapter").is_dir()

    def test_skips_dotfile_and_underscore_names(self, sample_config, tmp_project, monkeypatch):
        Path(sample_config["models_dir"]).mkdir(parents=True, exist_ok=True)
        for name in sample_config["model_subdirs"]:
            (Path(sample_config["models_dir"]) / name).mkdir(exist_ok=True)
        self._make_bare_env(tmp_project, "env1", [".git", "__pycache__", "realone"])
        monkeypatch.setattr("src.utils.fs_ops.save_config", lambda *a, **k: None)

        manager = EnvManager(sample_config)
        result = manager.sync_shared_model_subdirs(force_regen=False)

        assert result["added"] == ["realone"]

    def test_skips_files_at_scan_root(self, sample_config, tmp_project, monkeypatch):
        shared = Path(sample_config["models_dir"])
        shared.mkdir(parents=True, exist_ok=True)
        for name in sample_config["model_subdirs"]:
            (shared / name).mkdir(exist_ok=True)
        (shared / "readme.txt").write_text("hello", encoding="utf-8")
        monkeypatch.setattr("src.utils.fs_ops.save_config", lambda *a, **k: None)

        manager = EnvManager(sample_config)
        result = manager.sync_shared_model_subdirs(force_regen=False)

        assert result["added"] == []


class TestSyncForceRegen:
    def _make_bare_env(self, tmp_project, name, enabled=True):
        env_dir = tmp_project / "environments" / name
        (env_dir / "ComfyUI" / "models").mkdir(parents=True)
        (env_dir / "env_meta.json").write_text(
            json.dumps({
                "name": name, "created_at": "2026-04-10T00:00:00+08:00",
                "comfyui_commit": "abc", "comfyui_branch": "master",
                "python_version": "3.11", "pip_freeze": {}, "custom_nodes": [],
                "snapshots": [], "parent_env": None, "merge_history": [],
                "shared_model_enabled": enabled,
            }, ensure_ascii=False), encoding="utf-8",
        )

    def test_force_regen_rewrites_yaml_with_empty_added(
        self, sample_config, tmp_project, monkeypatch
    ):
        shared = Path(sample_config["models_dir"])
        shared.mkdir(parents=True, exist_ok=True)
        for name in sample_config["model_subdirs"]:
            (shared / name).mkdir(exist_ok=True)
        self._make_bare_env(tmp_project, "env1", enabled=True)
        self._make_bare_env(tmp_project, "env2", enabled=True)
        self._make_bare_env(tmp_project, "env3", enabled=False)
        monkeypatch.setattr("src.utils.fs_ops.save_config", lambda *a, **k: None)

        manager = EnvManager(sample_config)
        result = manager.sync_shared_model_subdirs(force_regen=True)

        assert result["added"] == []
        assert result["synced_envs"] == 2  # env1 + env2, not env3
        assert (tmp_project / "environments" / "env1" / "ComfyUI" / "extra_model_paths.yaml").exists()
        assert (tmp_project / "environments" / "env2" / "ComfyUI" / "extra_model_paths.yaml").exists()
        assert not (tmp_project / "environments" / "env3" / "ComfyUI" / "extra_model_paths.yaml").exists()

    def test_non_force_does_not_regen_with_empty_added(
        self, sample_config, tmp_project, monkeypatch
    ):
        shared = Path(sample_config["models_dir"])
        shared.mkdir(parents=True, exist_ok=True)
        for name in sample_config["model_subdirs"]:
            (shared / name).mkdir(exist_ok=True)
        self._make_bare_env(tmp_project, "env1", enabled=True)
        monkeypatch.setattr("src.utils.fs_ops.save_config", lambda *a, **k: None)

        manager = EnvManager(sample_config)
        result = manager.sync_shared_model_subdirs(force_regen=False)

        assert result["added"] == []
        assert result["synced_envs"] == 0
        assert not (tmp_project / "environments" / "env1" / "ComfyUI" / "extra_model_paths.yaml").exists()


class TestEnsureSharedModelsIfSafe:
    def test_default_mode_existing_models_dir_creates_subdirs(
        self, sample_config, tmp_project
    ):
        # sample_config default mode; models dir already created by tmp_project fixture
        manager = EnvManager(sample_config)
        assert manager.ensure_shared_models_if_safe() is True
        shared = Path(sample_config["models_dir"])
        for name in sample_config["model_subdirs"]:
            assert (shared / name).is_dir()

    def test_default_mode_missing_parent_skips(self, sample_config, tmp_project):
        # Point models_dir at a path whose parent does not exist
        sample_config["models_dir"] = str(tmp_project / "ghost" / "deeper" / "models")
        manager = EnvManager(sample_config)
        assert manager.ensure_shared_models_if_safe() is False
        assert not Path(sample_config["models_dir"]).exists()

    def test_custom_mode_missing_custom_path_skips(self, sample_config, tmp_project):
        sample_config["shared_model_mode"] = "custom"
        sample_config["custom_model_path"] = str(tmp_project / "not_plugged_in" / "models")
        manager = EnvManager(sample_config)
        assert manager.ensure_shared_models_if_safe() is False
        assert not Path(sample_config["custom_model_path"]).exists()

    def test_custom_mode_existing_custom_path_creates_subdirs(
        self, sample_config, tmp_project
    ):
        custom = tmp_project / "external_models"
        custom.mkdir()
        sample_config["shared_model_mode"] = "custom"
        sample_config["custom_model_path"] = str(custom)
        manager = EnvManager(sample_config)
        assert manager.ensure_shared_models_if_safe() is True
        for name in sample_config["model_subdirs"]:
            assert (custom / name).is_dir()


class TestEnvManagerInitHasNoSideEffects:
    def test_init_does_not_call_sync(self, sample_config, tmp_project, monkeypatch):
        called = {"sync": False, "ensure_if_safe": False}

        original_sync = EnvManager.sync_shared_model_subdirs
        original_guard = EnvManager.ensure_shared_models_if_safe

        def fake_sync(self, *a, **k):
            called["sync"] = True
            return original_sync(self, *a, **k)

        def fake_guard(self, *a, **k):
            called["ensure_if_safe"] = True
            return original_guard(self, *a, **k)

        monkeypatch.setattr(EnvManager, "sync_shared_model_subdirs", fake_sync)
        monkeypatch.setattr(EnvManager, "ensure_shared_models_if_safe", fake_guard)

        EnvManager(sample_config)

        assert called["sync"] is False
        assert called["ensure_if_safe"] is False


import platform


@pytest.mark.skipif(platform.system() != "Windows", reason="junction test")
def test_sync_attaches_new_subdir_as_junction(tmp_path):
    from src.core.env_manager import EnvManager
    config = {
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "shared"),
        "snapshots_dir": str(tmp_path / "snapshots"),
        "shared_model_mode": "default",
        "custom_model_path": "",
        "model_subdirs": ["checkpoints"],
        "shared_model_subdirs_excluded": ["configs"],
    }
    mgr = EnvManager(config)
    env_dir = tmp_path / "envs/x"
    (env_dir / "ComfyUI/models/checkpoints").mkdir(parents=True)
    (env_dir / "env_meta.json").write_text(
        '{"name":"x","created_at":"2026-04-20T00:00:00","shared_model_enabled":false}',
        encoding="utf-8",
    )
    mgr.toggle_shared_model("x", True)

    (env_dir / "ComfyUI/models/insightface").mkdir()
    (env_dir / "ComfyUI/models/insightface/det.onnx").write_bytes(b"O" * 5)

    result = mgr.sync_shared_model_subdirs()
    assert "insightface" in result["added"]

    from src.utils import fs_ops
    assert fs_ops.is_junction(env_dir / "ComfyUI/models/insightface")
    assert (tmp_path / "shared/insightface/det.onnx").read_bytes() == b"O" * 5
