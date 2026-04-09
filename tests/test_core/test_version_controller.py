"""Tests for VersionController core module."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import pytest

from src.core.version_controller import VersionController


def _create_mock_env(envs_dir, name, comfyui_commit="abc1234"):
    """Helper to create a mock environment with required structure."""
    env_dir = Path(envs_dir) / name
    env_dir.mkdir(parents=True, exist_ok=True)
    comfyui_dir = env_dir / "ComfyUI"
    comfyui_dir.mkdir(exist_ok=True)
    venv_dir = env_dir / "venv"
    venv_dir.mkdir(exist_ok=True)
    meta = {
        "name": name,
        "created_at": "2026-04-04T10:00:00+08:00",
        "comfyui_commit": comfyui_commit,
        "comfyui_branch": "master",
        "python_version": "3.11.9",
        "pip_freeze": {"torch": "2.3.1"},
        "custom_nodes": [],
        "snapshots": [],
        "parent_env": None,
        "merge_history": [],
    }
    (env_dir / "env_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    return env_dir


class TestVersionControllerInit:
    def test_init(self, sample_config):
        vc = VersionController(sample_config)
        assert vc.config == sample_config
        assert vc.environments_dir == Path(sample_config["environments_dir"])


class TestListCommits:
    @patch("src.core.version_controller.git_ops")
    def test_list_commits_calls_get_log(self, mock_git, sample_config):
        env_dir = _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_log.return_value = [
            {"hash": "abc1234", "message": "Initial commit", "author": "Alice", "date": "2026-04-04"}
        ]

        vc = VersionController(sample_config)
        result = vc.list_commits("main", count=10)

        expected_path = str(env_dir / "ComfyUI")
        mock_git.get_log.assert_called_once_with(expected_path, count=10)
        assert len(result) == 1
        assert result[0]["hash"] == "abc1234"

    @patch("src.core.version_controller.git_ops")
    def test_list_commits_default_count(self, mock_git, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_log.return_value = []

        vc = VersionController(sample_config)
        vc.list_commits("main")

        mock_git.get_log.assert_called_once_with(
            str(Path(sample_config["environments_dir"]) / "main" / "ComfyUI"),
            count=20,
        )


class TestListBranches:
    @patch("src.core.version_controller.git_ops")
    def test_list_branches_calls_get_branches(self, mock_git, sample_config):
        env_dir = _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.get_branches.return_value = ["master", "dev"]

        vc = VersionController(sample_config)
        result = vc.list_branches("main")

        expected_path = str(env_dir / "ComfyUI")
        mock_git.get_branches.assert_called_once_with(expected_path)
        assert result == ["master", "dev"]


class TestSwitchVersion:
    @patch("src.core.version_controller.pip_ops")
    @patch("src.core.version_controller.git_ops")
    @patch("src.core.version_controller.SnapshotManager")
    def test_switch_creates_snapshot_first(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_snap = MagicMock()
        mock_snap_cls.return_value = mock_snap
        mock_git.get_current_commit.return_value = "newcommit"
        mock_pip.freeze.return_value = {}

        vc = VersionController(sample_config)
        vc.switch_version("main", "v1.0.0")

        mock_snap.create_snapshot.assert_called_once_with("main", trigger="version_switch")

    @patch("src.core.version_controller.pip_ops")
    @patch("src.core.version_controller.git_ops")
    @patch("src.core.version_controller.SnapshotManager")
    def test_switch_calls_git_checkout(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        env_dir = _create_mock_env(sample_config["environments_dir"], "main")
        mock_snap_cls.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "newcommit"
        mock_pip.freeze.return_value = {}

        vc = VersionController(sample_config)
        vc.switch_version("main", "v1.0.0")

        expected_path = str(env_dir / "ComfyUI")
        mock_git.checkout.assert_called_once_with(expected_path, "v1.0.0")

    @patch("src.core.version_controller.pip_ops")
    @patch("src.core.version_controller.git_ops")
    @patch("src.core.version_controller.SnapshotManager")
    def test_switch_reinstalls_requirements_for_comfyui(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        env_dir = _create_mock_env(sample_config["environments_dir"], "main")
        # Create requirements.txt so reinstall is triggered
        (env_dir / "ComfyUI" / "requirements.txt").write_text("torch", encoding="utf-8")
        mock_snap_cls.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "newcommit"
        mock_pip.freeze.return_value = {}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)

        vc = VersionController(sample_config)
        vc.switch_version("main", "v1.0.0")

        mock_pip.run_pip.assert_called_once()
        args = mock_pip.run_pip.call_args[0]
        assert "install" in args[1]
        assert "-r" in args[1]

    @patch("src.core.version_controller.pip_ops")
    @patch("src.core.version_controller.git_ops")
    @patch("src.core.version_controller.SnapshotManager")
    def test_switch_updates_env_meta(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        env_dir = _create_mock_env(sample_config["environments_dir"], "main")
        mock_snap_cls.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "newcommit123"
        mock_pip.freeze.return_value = {"torch": "2.4.0"}

        vc = VersionController(sample_config)
        vc.switch_version("main", "v1.0.0")

        env_meta = json.loads(
            (env_dir / "env_meta.json").read_text(encoding="utf-8")
        )
        assert env_meta["comfyui_commit"] == "newcommit123"
        assert env_meta["pip_freeze"] == {"torch": "2.4.0"}


class TestUpdateComfyui:
    @patch("src.core.version_controller.pip_ops")
    @patch("src.core.version_controller.git_ops")
    @patch("src.core.version_controller.SnapshotManager")
    def test_update_creates_snapshot(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_snap = MagicMock()
        mock_snap_cls.return_value = mock_snap
        mock_git.get_current_commit.return_value = "latestcommit"
        mock_pip.freeze.return_value = {}

        vc = VersionController(sample_config)
        vc.update_comfyui("main")

        mock_snap.create_snapshot.assert_called_once_with("main", trigger="update")

    @patch("src.core.version_controller.pip_ops")
    @patch("src.core.version_controller.git_ops")
    @patch("src.core.version_controller.SnapshotManager")
    def test_update_calls_git_pull(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        env_dir = _create_mock_env(sample_config["environments_dir"], "main")
        mock_snap_cls.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "latestcommit"
        mock_pip.freeze.return_value = {}

        vc = VersionController(sample_config)
        vc.update_comfyui("main")

        expected_path = str(env_dir / "ComfyUI")
        mock_git.pull.assert_called_once_with(expected_path)

    @patch("src.core.version_controller.pip_ops")
    @patch("src.core.version_controller.git_ops")
    @patch("src.core.version_controller.SnapshotManager")
    def test_update_updates_env_meta(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        env_dir = _create_mock_env(sample_config["environments_dir"], "main")
        mock_snap_cls.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "latestcommit"
        mock_pip.freeze.return_value = {"torch": "2.5.0"}

        vc = VersionController(sample_config)
        vc.update_comfyui("main")

        env_meta = json.loads(
            (env_dir / "env_meta.json").read_text(encoding="utf-8")
        )
        assert env_meta["comfyui_commit"] == "latestcommit"
        assert env_meta["pip_freeze"] == {"torch": "2.5.0"}


class TestListRemoteVersions:
    @patch("src.utils.git_ops.list_remote_tags", return_value=[{"name": "v0.1.0", "hash": "abc1234"}])
    @patch("src.utils.git_ops.list_remote_branches", return_value=["main", "develop"])
    def test_list_remote_versions(self, mock_branches, mock_tags, sample_config):
        controller = VersionController(sample_config)
        result = controller.list_remote_versions()
        assert "tags" in result
        assert "branches" in result
        assert len(result["tags"]) == 1
        assert result["branches"] == ["main", "develop"]


class TestErrorCases:
    @patch("src.core.version_controller.git_ops")
    def test_list_commits_env_not_found(self, mock_git, sample_config):
        vc = VersionController(sample_config)
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            vc.list_commits("nonexistent")

    @patch("src.core.version_controller.git_ops")
    def test_list_branches_env_not_found(self, mock_git, sample_config):
        vc = VersionController(sample_config)
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            vc.list_branches("nonexistent")

    @patch("src.core.version_controller.pip_ops")
    @patch("src.core.version_controller.git_ops")
    @patch("src.core.version_controller.SnapshotManager")
    def test_switch_env_not_found(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        mock_snap_cls.return_value = MagicMock()
        vc = VersionController(sample_config)
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            vc.switch_version("nonexistent", "v1.0.0")
