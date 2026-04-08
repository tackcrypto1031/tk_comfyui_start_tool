"""Tests for EnvManager core module."""
import json
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import pytest

from src.core.env_manager import EnvManager


class TestEnvManagerInit:
    """Test EnvManager initialization."""

    def test_init(self, sample_config):
        manager = EnvManager(sample_config)
        assert manager.config == sample_config


class TestCreateEnvironment:
    """Test environment creation."""

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    def test_create_basic(self, mock_git, mock_pip, sample_config):
        mock_git.clone_repo.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.freeze.return_value = {"pip": "24.0"}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)

        manager = EnvManager(sample_config)
        env = manager.create_environment("test-env")

        assert env.name == "test-env"
        assert env.comfyui_commit == "abc1234"
        assert env.python_version == "3.11.9"
        assert env.is_sandbox is False

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    def test_create_with_branch(self, mock_git, mock_pip, sample_config):
        mock_git.clone_repo.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.freeze.return_value = {}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)

        manager = EnvManager(sample_config)
        env = manager.create_environment("dev", branch="develop")

        assert env.comfyui_branch == "develop"
        assert mock_git.clone_repo.call_count >= 1
        comfy_clone_call = mock_git.clone_repo.call_args_list[0]
        assert comfy_clone_call[1].get("branch") == "develop"

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    def test_create_with_commit(self, mock_git, mock_pip, sample_config):
        mock_git.clone_repo.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "specific123"
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.freeze.return_value = {}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)

        manager = EnvManager(sample_config)
        env = manager.create_environment("pinned", commit="specific123")

        assert env.comfyui_commit == "specific123"

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    def test_create_writes_env_meta(self, mock_git, mock_pip, sample_config):
        mock_git.clone_repo.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.freeze.return_value = {}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)

        manager = EnvManager(sample_config)
        env = manager.create_environment("test-env")

        meta_path = Path(sample_config["environments_dir"]) / "test-env" / "env_meta.json"
        assert meta_path.exists()
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        assert data["name"] == "test-env"

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    def test_create_generates_extra_model_paths(self, mock_git, mock_pip, sample_config):
        mock_git.clone_repo.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.freeze.return_value = {}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)

        manager = EnvManager(sample_config)
        env = manager.create_environment("test-env")

        yaml_path = Path(sample_config["environments_dir"]) / "test-env" / "ComfyUI" / "extra_model_paths.yaml"
        assert yaml_path.exists()
        content = yaml_path.read_text(encoding="utf-8")
        assert "checkpoints" in content

    def test_create_invalid_name(self, sample_config):
        manager = EnvManager(sample_config)

        with pytest.raises(ValueError, match="Invalid environment name"):
            manager.create_environment("bad name with spaces")

    def test_create_invalid_name_special_chars(self, sample_config):
        manager = EnvManager(sample_config)

        with pytest.raises(ValueError, match="Invalid environment name"):
            manager.create_environment("env/../../etc")

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    def test_create_duplicate_name(self, mock_git, mock_pip, sample_config):
        # Pre-create the environment directory
        env_dir = Path(sample_config["environments_dir"]) / "existing"
        env_dir.mkdir(parents=True)

        manager = EnvManager(sample_config)

        with pytest.raises(FileExistsError, match="already exists"):
            manager.create_environment("existing")

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    def test_create_calls_venv_then_clone(self, mock_git, mock_pip, sample_config):
        """Verify the creation order: venv -> clone -> freeze."""
        mock_git.clone_repo.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.run_pip.return_value = MagicMock(returncode=0)

        call_order = []
        mock_pip.create_venv.side_effect = lambda *a, **kw: call_order.append("venv")
        mock_git.clone_repo.side_effect = lambda *a, **kw: (call_order.append("clone"), MagicMock())[1]
        mock_pip.freeze.side_effect = lambda *a, **kw: (call_order.append("freeze"), {})[1]

        manager = EnvManager(sample_config)
        manager.create_environment("test-env")

        assert call_order.index("venv") < call_order.index("clone")
        assert call_order.index("clone") < call_order.index("freeze")

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    def test_create_reconciles_torchaudio_mismatch(self, mock_git, mock_pip, sample_config):
        """When torchaudio mismatches torch, env creation reinstalls matching torchaudio."""
        mock_git.clone_repo.return_value = MagicMock()
        mock_git.get_current_commit.return_value = "abc1234"
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        # freeze is called for compatibility check, verification, and final metadata
        mock_pip.freeze.side_effect = [
            {"torch": "2.9.1+cu130", "torchaudio": "2.11.0+cu130"},
            {
                "torch": "2.9.1+cu130",
                "torchaudio": "2.9.1+cu130",
                "numpy": "2.0.0",
                "pillow": "11.0.0",
                "pyyaml": "6.0.0",
                "aiohttp": "3.11.0",
            },
            {
                "torch": "2.9.1+cu130",
                "torchaudio": "2.9.1+cu130",
            },
        ]

        manager = EnvManager(sample_config)
        manager.create_environment("test-env", cuda_tag="cu130", pytorch_version="2.9.1")

        uninstall_calls = [
            c for c in mock_pip.run_pip.call_args_list
            if c[0][1][:3] == ["uninstall", "-y", "torchaudio"]
        ]
        assert len(uninstall_calls) == 1
        reinstall_calls = [
            c for c in mock_pip.run_pip_with_progress.call_args_list
            if "torchaudio==2.9.1" in c[0][1]
        ]
        assert len(reinstall_calls) == 1


def _create_mock_env(envs_dir, name, is_sandbox=False, parent_env=None):
    """Helper to create a mock environment directory with env_meta.json."""
    env_dir = Path(envs_dir) / name
    env_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "name": name,
        "created_at": "2026-04-04T10:00:00+08:00",
        "comfyui_commit": "abc1234",
        "comfyui_branch": "master",
        "python_version": "3.11.9",
        "pip_freeze": {},
        "custom_nodes": [],
        "snapshots": [],
        "is_sandbox": is_sandbox,
        "parent_env": parent_env,
        "merge_history": [],
    }
    (env_dir / "env_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    return env_dir


class TestListEnvironments:
    """Test listing environments."""

    def test_list_empty(self, sample_config):
        manager = EnvManager(sample_config)
        result = manager.list_environments()
        assert result == []

    def test_list_single(self, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        manager = EnvManager(sample_config)
        result = manager.list_environments()
        assert len(result) == 1
        assert result[0].name == "main"

    def test_list_multiple(self, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        _create_mock_env(sample_config["environments_dir"], "dev")
        _create_mock_env(sample_config["environments_dir"], "sandbox-1", is_sandbox=True, parent_env="main")
        manager = EnvManager(sample_config)
        result = manager.list_environments()
        assert len(result) == 3
        names = {e.name for e in result}
        assert names == {"main", "dev", "sandbox-1"}

    def test_list_ignores_dirs_without_meta(self, sample_config):
        _create_mock_env(sample_config["environments_dir"], "valid")
        # Create a dir without env_meta.json
        stray = Path(sample_config["environments_dir"]) / "stray"
        stray.mkdir()
        manager = EnvManager(sample_config)
        result = manager.list_environments()
        assert len(result) == 1
        assert result[0].name == "valid"


class TestGetEnvironment:
    """Test getting a single environment."""

    def test_get_existing(self, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        manager = EnvManager(sample_config)
        env = manager.get_environment("main")
        assert env.name == "main"
        assert env.comfyui_commit == "abc1234"

    def test_get_nonexistent(self, sample_config):
        manager = EnvManager(sample_config)
        with pytest.raises(FileNotFoundError):
            manager.get_environment("nope")


class TestDeleteEnvironment:
    """Test deleting environments."""

    def test_delete_existing(self, sample_config):
        env_dir = _create_mock_env(sample_config["environments_dir"], "to-delete")
        manager = EnvManager(sample_config)
        manager.delete_environment("to-delete", force=True)
        assert not env_dir.exists()

    def test_delete_nonexistent(self, sample_config):
        manager = EnvManager(sample_config)
        with pytest.raises(FileNotFoundError):
            manager.delete_environment("nope", force=True)

    def test_delete_protected_main_without_force(self, sample_config):
        _create_mock_env(sample_config["environments_dir"], "main")
        sample_config["default_env"] = "main"
        manager = EnvManager(sample_config)
        with pytest.raises(ValueError, match="default environment"):
            manager.delete_environment("main", force=False)

    def test_delete_protected_main_with_force(self, sample_config):
        env_dir = _create_mock_env(sample_config["environments_dir"], "main")
        sample_config["default_env"] = "main"
        manager = EnvManager(sample_config)
        manager.delete_environment("main", force=True)
        assert not env_dir.exists()

    def test_delete_also_removes_snapshots(self, sample_config):
        _create_mock_env(sample_config["environments_dir"], "env1")
        snap_dir = Path(sample_config["snapshots_dir"]) / "env1"
        snap_dir.mkdir(parents=True)
        (snap_dir / "snap-1").mkdir()
        manager = EnvManager(sample_config)
        manager.delete_environment("env1", force=True)
        assert not snap_dir.exists()


class TestEnsureSharedModels:
    """Test shared models directory setup."""

    def test_ensure_creates_subdirs(self, sample_config):
        manager = EnvManager(sample_config)
        manager.ensure_shared_models()
        models_dir = Path(sample_config["models_dir"])
        for subdir in sample_config["model_subdirs"]:
            assert (models_dir / subdir).is_dir()

    def test_ensure_idempotent(self, sample_config):
        manager = EnvManager(sample_config)
        manager.ensure_shared_models()
        manager.ensure_shared_models()  # Should not raise
        models_dir = Path(sample_config["models_dir"])
        assert (models_dir / "checkpoints").is_dir()


class TestCloneEnvironment:
    """Test environment cloning."""

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_clone_basic(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """Cloned env has is_sandbox=True and parent_env=source."""
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.clone_repo.return_value = MagicMock()
        mock_pip.freeze.return_value = {"torch": "2.3.1"}
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_pip.create_venv.return_value = None
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        env = manager.clone_environment("main", "main-sandbox")

        assert env.name == "main-sandbox"
        assert env.is_sandbox is True
        assert env.parent_env == "main"

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_clone_creates_new_venv(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """Clone creates a fresh venv rather than copying."""
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.clone_repo.return_value = MagicMock()
        mock_pip.freeze.return_value = {}
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        manager.clone_environment("main", "main-sandbox")

        target_venv = str(Path(sample_config["environments_dir"]) / "main-sandbox" / "venv")
        mock_pip.create_venv.assert_called_once_with(target_venv)

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_clone_installs_from_freeze(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """Clone runs pip install -r freeze.txt from source freeze."""
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.clone_repo.return_value = MagicMock()
        mock_pip.freeze.return_value = {"torch": "2.3.1", "numpy": "1.26.4"}
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        manager.clone_environment("main", "main-sandbox")

        # Verify pip install -r was called with a freeze file
        install_calls = [
            c for c in mock_pip.run_pip_with_progress.call_args_list
            if "install" in c[0][1] and "-r" in c[0][1]
        ]
        assert len(install_calls) >= 1

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_clone_comfyui_same_commit(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """Cloned env has same ComfyUI commit as source."""
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.clone_repo.return_value = MagicMock()
        mock_pip.freeze.return_value = {}
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        env = manager.clone_environment("main", "main-sandbox")

        # Source env has comfyui_commit "abc1234" from _create_mock_env
        assert env.comfyui_commit == "abc1234"
        # git clone_repo was called with commit="abc1234"
        clone_call_kwargs = mock_git.clone_repo.call_args
        assert clone_call_kwargs[1].get("commit") == "abc1234"

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_clone_auto_snapshot_source(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """A snapshot is created on the source environment before cloning."""
        _create_mock_env(sample_config["environments_dir"], "main")
        mock_git.clone_repo.return_value = MagicMock()
        mock_pip.freeze.return_value = {}
        mock_pip.get_python_version.return_value = "3.11.9"
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_instance = mock_snap_cls.return_value
        mock_snap_instance.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        manager.clone_environment("main", "main-sandbox")

        mock_snap_instance.create_snapshot.assert_called_once_with("main", trigger="clone")

    def test_clone_source_not_found(self, sample_config):
        """Raises FileNotFoundError when source env does not exist."""
        manager = EnvManager(sample_config)
        with pytest.raises(FileNotFoundError, match="Source environment"):
            manager.clone_environment("nonexistent", "new-env")

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_clone_target_exists(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """Raises FileExistsError when target env already exists."""
        _create_mock_env(sample_config["environments_dir"], "main")
        _create_mock_env(sample_config["environments_dir"], "main-sandbox")

        manager = EnvManager(sample_config)
        with pytest.raises(FileExistsError, match="already exists"):
            manager.clone_environment("main", "main-sandbox")


class TestMergeEnvironment:
    """Test environment merge functionality."""

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_merge_basic(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """Merges sandbox changes back to parent, returns summary dict."""
        _create_mock_env(sample_config["environments_dir"], "main")
        _create_mock_env(sample_config["environments_dir"], "sandbox-1", is_sandbox=True, parent_env="main")
        mock_pip.freeze.return_value = {"torch": "2.3.1"}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        result = manager.merge_env("sandbox-1", "main")

        assert isinstance(result, dict)
        assert "new_packages" in result
        assert "changed_packages" in result
        assert "new_nodes" in result

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_merge_creates_snapshot_on_target(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """Auto-snapshot is created on target before merge."""
        _create_mock_env(sample_config["environments_dir"], "main")
        _create_mock_env(sample_config["environments_dir"], "sandbox-1", is_sandbox=True, parent_env="main")
        mock_pip.freeze.return_value = {}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_instance = mock_snap_cls.return_value
        mock_snap_instance.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        manager.merge_env("sandbox-1", "main")

        mock_snap_instance.create_snapshot.assert_called_once_with("main", trigger="merge")

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_merge_installs_new_packages(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """New packages in source are installed into target."""
        _create_mock_env(sample_config["environments_dir"], "main")
        _create_mock_env(sample_config["environments_dir"], "sandbox-1", is_sandbox=True, parent_env="main")
        # source has extra package "newpkg==1.0"
        mock_pip.freeze.side_effect = [
            {"torch": "2.3.1", "newpkg": "1.0"},  # source freeze
            {"torch": "2.3.1"},                    # target freeze
            {"torch": "2.3.1", "newpkg": "1.0"},  # final freeze after install
        ]
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        result = manager.merge_env("sandbox-1", "main")

        assert "newpkg" in result["new_packages"]
        # pip install should have been called with newpkg==1.0
        install_calls = [
            c for c in mock_pip.run_pip.call_args_list
            if "install" in c[0][1]
        ]
        assert len(install_calls) >= 1

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_merge_copies_new_custom_nodes(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """New custom nodes in source are cloned into target."""
        source_dir = _create_mock_env(sample_config["environments_dir"], "sandbox-1", is_sandbox=True, parent_env="main")
        _create_mock_env(sample_config["environments_dir"], "main")
        # Add custom node to sandbox meta
        meta_path = source_dir / "env_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["custom_nodes"] = [{"name": "awesome-node", "repo_url": "https://github.com/example/awesome-node.git", "commit": "def5678"}]
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        mock_pip.freeze.return_value = {}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_git.clone_repo.return_value = MagicMock()
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        result = manager.merge_env("sandbox-1", "main")

        assert "awesome-node" in result["new_nodes"]
        mock_git.clone_repo.assert_called_once()

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_merge_records_history(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """merge_history is updated on target after merge."""
        _create_mock_env(sample_config["environments_dir"], "main")
        _create_mock_env(sample_config["environments_dir"], "sandbox-1", is_sandbox=True, parent_env="main")
        mock_pip.freeze.return_value = {}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        manager.merge_env("sandbox-1", "main")

        # Read target meta to verify history recorded
        target_meta_path = Path(sample_config["environments_dir"]) / "main" / "env_meta.json"
        target_meta = json.loads(target_meta_path.read_text(encoding="utf-8"))
        assert len(target_meta["merge_history"]) == 1
        assert target_meta["merge_history"][0]["source"] == "sandbox-1"

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_merge_deduplicates_custom_nodes_by_name(
        self, mock_snap_cls, mock_git, mock_pip, sample_config
    ):
        """Target custom_nodes should be deduplicated by name after merge."""
        source_dir = _create_mock_env(
            sample_config["environments_dir"], "sandbox-1", is_sandbox=True, parent_env="main"
        )
        target_dir = _create_mock_env(sample_config["environments_dir"], "main")

        source_meta_path = source_dir / "env_meta.json"
        source_meta = json.loads(source_meta_path.read_text(encoding="utf-8"))
        source_meta["custom_nodes"] = [
            {"name": "dup-node", "repo_url": "https://github.com/example/dup-node.git", "commit": "src-dup"},
            {"name": "new-node", "repo_url": "https://github.com/example/new-node.git", "commit": "src-new"},
        ]
        source_meta_path.write_text(json.dumps(source_meta), encoding="utf-8")

        target_meta_path = target_dir / "env_meta.json"
        target_meta = json.loads(target_meta_path.read_text(encoding="utf-8"))
        target_meta["custom_nodes"] = [
            {"name": "dup-node", "repo_url": "https://github.com/example/dup-node.git", "commit": "target-1"},
            {"name": "dup-node", "repo_url": "https://github.com/example/dup-node.git", "commit": "target-2"},
        ]
        target_meta_path.write_text(json.dumps(target_meta), encoding="utf-8")

        mock_pip.freeze.return_value = {}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()
        mock_git.clone_repo.return_value = MagicMock()

        manager = EnvManager(sample_config)
        result = manager.merge_env("sandbox-1", "main")

        assert "new-node" in result["new_nodes"]

        merged_target_meta = json.loads(target_meta_path.read_text(encoding="utf-8"))
        names = [node["name"] for node in merged_target_meta["custom_nodes"]]
        assert names.count("dup-node") == 1
        assert names.count("new-node") == 1

    def test_merge_source_not_found(self, sample_config):
        """Raises FileNotFoundError when source environment does not exist."""
        _create_mock_env(sample_config["environments_dir"], "main")
        manager = EnvManager(sample_config)
        with pytest.raises(FileNotFoundError, match="Source environment"):
            manager.merge_env("nonexistent", "main")

    def test_merge_target_not_found(self, sample_config):
        """Raises FileNotFoundError when target environment does not exist."""
        _create_mock_env(sample_config["environments_dir"], "sandbox-1", is_sandbox=True, parent_env="main")
        manager = EnvManager(sample_config)
        with pytest.raises(FileNotFoundError, match="Target environment"):
            manager.merge_env("sandbox-1", "nonexistent")

    @patch("src.core.env_manager.pip_ops")
    @patch("src.core.env_manager.git_ops")
    @patch("src.core.env_manager.SnapshotManager")
    def test_merge_non_sandbox(self, mock_snap_cls, mock_git, mock_pip, sample_config):
        """merge_env works for any env pair, not just sandboxes."""
        _create_mock_env(sample_config["environments_dir"], "env-a")
        _create_mock_env(sample_config["environments_dir"], "env-b")
        mock_pip.freeze.return_value = {"requests": "2.31.0"}
        mock_pip.run_pip.return_value = MagicMock(returncode=0)
        mock_snap_cls.return_value.create_snapshot.return_value = MagicMock()

        manager = EnvManager(sample_config)
        result = manager.merge_env("env-a", "env-b")

        assert isinstance(result, dict)
        assert "new_packages" in result
