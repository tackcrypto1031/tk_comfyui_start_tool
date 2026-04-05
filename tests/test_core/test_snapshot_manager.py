"""Tests for SnapshotManager core module."""
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest

from src.core.snapshot_manager import SnapshotManager
from src.models.snapshot import Snapshot


def _create_mock_env(envs_dir, name, comfyui_commit="abc1234"):
    """Helper to create a mock environment."""
    env_dir = Path(envs_dir) / name
    env_dir.mkdir(parents=True, exist_ok=True)
    comfyui_dir = env_dir / "ComfyUI"
    comfyui_dir.mkdir(exist_ok=True)
    venv_dir = env_dir / "venv"
    venv_dir.mkdir(exist_ok=True)
    # Write extra_model_paths.yaml
    (comfyui_dir / "extra_model_paths.yaml").write_text("shared: true", encoding="utf-8")
    meta = {
        "name": name,
        "created_at": "2026-04-04T10:00:00+08:00",
        "comfyui_commit": comfyui_commit,
        "comfyui_branch": "master",
        "python_version": "3.11.9",
        "pip_freeze": {"torch": "2.3.1"},
        "custom_nodes": [
            {"name": "ComfyUI-Manager", "repo_url": "https://github.com/test", "commit": "node123"}
        ],
        "snapshots": [],
        "is_sandbox": False,
        "parent_env": None,
        "merge_history": [],
    }
    (env_dir / "env_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    return env_dir


class TestSnapshotManagerInit:
    def test_init(self, sample_config):
        mgr = SnapshotManager(sample_config)
        assert mgr.config == sample_config


class TestCreateSnapshot:
    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_create_basic(self, mock_pip, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.freeze.return_value = {"torch": "2.3.1"}

        mgr = SnapshotManager(sample_config)
        snap = mgr.create_snapshot("main", trigger="manual")

        assert snap.env_name == "main"
        assert snap.trigger == "manual"
        assert snap.comfyui_commit == "abc1234"
        assert snap.id.startswith("snap-")

    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_create_saves_freeze_file(self, mock_pip, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.freeze.return_value = {"torch": "2.3.1", "numpy": "1.26.4"}

        mgr = SnapshotManager(sample_config)
        snap = mgr.create_snapshot("main")

        freeze_path = Path(snap.pip_freeze_path)
        assert freeze_path.exists()
        content = freeze_path.read_text(encoding="utf-8")
        assert "torch==2.3.1" in content

    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_create_saves_meta(self, mock_pip, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.freeze.return_value = {}

        mgr = SnapshotManager(sample_config)
        snap = mgr.create_snapshot("main")

        snap_dir = Path(sample_config["snapshots_dir"]) / "main" / snap.id
        meta_path = snap_dir / "snapshot_meta.json"
        assert meta_path.exists()
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        assert data["env_name"] == "main"

    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_create_backs_up_configs(self, mock_pip, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.freeze.return_value = {}

        mgr = SnapshotManager(sample_config)
        snap = mgr.create_snapshot("main")

        configs_dir = Path(snap.config_backup_path)
        assert configs_dir.exists()
        assert (configs_dir / "extra_model_paths.yaml").exists()

    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_create_records_custom_nodes(self, mock_pip, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.freeze.return_value = {}

        mgr = SnapshotManager(sample_config)
        snap = mgr.create_snapshot("main")

        assert len(snap.custom_nodes_state) == 1
        assert snap.custom_nodes_state[0]["name"] == "ComfyUI-Manager"

    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_create_updates_env_meta(self, mock_pip, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.freeze.return_value = {}

        mgr = SnapshotManager(sample_config)
        snap = mgr.create_snapshot("main")

        # Re-read env_meta.json
        env_meta = json.loads(
            (Path(sample_config["environments_dir"]) / "main" / "env_meta.json")
            .read_text(encoding="utf-8")
        )
        assert snap.id in env_meta["snapshots"]

    def test_create_env_not_found(self, sample_config):
        mgr = SnapshotManager(sample_config)
        with pytest.raises(FileNotFoundError):
            mgr.create_snapshot("nonexistent")


class TestListSnapshots:
    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_list_empty(self, mock_pip, mock_git, sample_config):
        mgr = SnapshotManager(sample_config)
        result = mgr.list_snapshots("main")
        assert result == []

    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_list_after_create(self, mock_pip, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.freeze.return_value = {}

        mgr = SnapshotManager(sample_config)
        mgr.create_snapshot("main", trigger="test1")
        mgr.create_snapshot("main", trigger="test2")

        result = mgr.list_snapshots("main")
        assert len(result) == 2


class TestRestoreSnapshot:
    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_restore(self, mock_pip, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.freeze.return_value = {"torch": "2.3.1"}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)

        mgr = SnapshotManager(sample_config)
        snap = mgr.create_snapshot("main")

        # Restore
        mgr.restore_snapshot("main", snap.id)

        mock_git.checkout.assert_called_once_with(
            str(Path(sample_config["environments_dir"]) / "main" / "ComfyUI"),
            "abc1234",
        )
        mock_pip.run_pip.assert_called_once()

    def test_restore_nonexistent_snapshot(self, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mgr = SnapshotManager(sample_config)
        with pytest.raises(FileNotFoundError, match="Snapshot"):
            mgr.restore_snapshot("main", "snap-nonexistent")


class TestDeleteSnapshot:
    @patch("src.core.snapshot_manager.git_ops")
    @patch("src.core.snapshot_manager.pip_ops")
    def test_delete(self, mock_pip, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.freeze.return_value = {}

        mgr = SnapshotManager(sample_config)
        snap = mgr.create_snapshot("main")
        snap_dir = Path(sample_config["snapshots_dir"]) / "main" / snap.id

        assert snap_dir.exists()
        mgr.delete_snapshot("main", snap.id)
        assert not snap_dir.exists()

    def test_delete_nonexistent(self, sample_config):
        mgr = SnapshotManager(sample_config)
        with pytest.raises(FileNotFoundError):
            mgr.delete_snapshot("main", "snap-nope")
