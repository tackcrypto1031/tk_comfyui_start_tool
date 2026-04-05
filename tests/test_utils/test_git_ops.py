"""Tests for git_ops utility functions."""
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from src.utils.git_ops import clone_repo, get_current_commit, get_branches, get_log, checkout, pull
import src.utils.git_ops as git_ops


COMFYUI_URL = "https://github.com/comfyanonymous/ComfyUI.git"


class TestCloneRepo:
    """Test git clone operations."""

    @patch("src.utils.git_ops.git.Repo.clone_from")
    def test_clone_basic(self, mock_clone, tmp_path):
        mock_repo = MagicMock()
        mock_clone.return_value = mock_repo
        dest = tmp_path / "ComfyUI"

        result = clone_repo(COMFYUI_URL, str(dest))

        mock_clone.assert_called_once_with(COMFYUI_URL, str(dest), branch="master")
        assert result == mock_repo

    @patch("src.utils.git_ops.git.Repo.clone_from")
    def test_clone_with_branch(self, mock_clone, tmp_path):
        mock_repo = MagicMock()
        mock_clone.return_value = mock_repo
        dest = tmp_path / "ComfyUI"

        clone_repo(COMFYUI_URL, str(dest), branch="develop")

        mock_clone.assert_called_once_with(COMFYUI_URL, str(dest), branch="develop")

    @patch("src.utils.git_ops.git.Repo.clone_from")
    def test_clone_with_commit(self, mock_clone, tmp_path):
        mock_repo = MagicMock()
        mock_clone.return_value = mock_repo
        dest = tmp_path / "ComfyUI"

        clone_repo(COMFYUI_URL, str(dest), commit="abc1234")

        mock_clone.assert_called_once()
        mock_repo.git.checkout.assert_called_once_with("abc1234")

    @patch("src.utils.git_ops.git.Repo.clone_from")
    def test_clone_failure_raises(self, mock_clone, tmp_path):
        mock_clone.side_effect = Exception("Network error")
        dest = tmp_path / "ComfyUI"

        with pytest.raises(Exception, match="Network error"):
            clone_repo(COMFYUI_URL, str(dest))


class TestGetCurrentCommit:
    """Test getting current commit hash."""

    @patch("src.utils.git_ops.git.Repo")
    def test_get_commit(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc1234def5678"
        mock_repo_cls.return_value = mock_repo

        result = get_current_commit("/path/to/repo")

        assert result == "abc1234def5678"

    @patch("src.utils.git_ops.git.Repo")
    def test_get_commit_short(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc1234def5678901234567890"
        mock_repo_cls.return_value = mock_repo

        result = get_current_commit("/path/to/repo", short=True)

        assert result == "abc1234"


class TestGetBranches:
    """Test listing branches."""

    @patch("src.utils.git_ops.git.Repo")
    def test_get_branches(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_ref1 = MagicMock()
        mock_ref1.remote_head = "master"
        mock_ref2 = MagicMock()
        mock_ref2.remote_head = "develop"
        mock_repo.remotes.origin.refs = [mock_ref1, mock_ref2]
        mock_repo_cls.return_value = mock_repo

        result = get_branches("/path/to/repo")

        assert "master" in result
        assert "develop" in result


class TestGetLog:
    """Test getting git log."""

    @patch("src.utils.git_ops.git.Repo")
    def test_get_log(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc1234"
        mock_commit.message = "Initial commit"
        mock_commit.author.name = "Tack"
        mock_commit.committed_datetime.isoformat.return_value = "2026-04-04T10:00:00"
        mock_repo.iter_commits.return_value = [mock_commit]
        mock_repo_cls.return_value = mock_repo

        result = get_log("/path/to/repo", count=5)

        assert len(result) == 1
        assert result[0]["hash"] == "abc1234"
        assert result[0]["message"] == "Initial commit"


class TestCheckout:
    """Test git checkout."""

    @patch("src.utils.git_ops.git.Repo")
    def test_checkout(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo

        checkout("/path/to/repo", "abc1234")

        mock_repo.git.checkout.assert_called_once_with("abc1234")


class TestPull:
    """Test git pull."""

    @patch("src.utils.git_ops.git.Repo")
    def test_pull(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo

        pull("/path/to/repo")

        mock_repo.remotes.origin.pull.assert_called_once()


def test_list_remote_tags_parses_output():
    mock_output = "abc1234567890\trefs/tags/v0.1.0\nabc1234567890\trefs/tags/v0.1.0^{}\ndef4567890123\trefs/tags/v0.2.0\n"
    with patch("src.utils.git_ops.git.cmd.Git") as mock_git_cls:
        mock_git_cls.return_value.ls_remote.return_value = mock_output
        result = git_ops.list_remote_tags("https://example.com/repo.git")
    assert len(result) == 2
    assert result[0]["name"] == "v0.2.0"  # Newest first
    assert result[1]["name"] == "v0.1.0"
    assert "^{}" not in str(result)


def test_list_remote_branches_parses_output():
    mock_output = "abc123\trefs/heads/main\ndef456\trefs/heads/develop\n"
    with patch("src.utils.git_ops.git.cmd.Git") as mock_git_cls:
        mock_git_cls.return_value.ls_remote.return_value = mock_output
        result = git_ops.list_remote_branches("https://example.com/repo.git")
    assert result == ["develop", "main"]


def test_list_remote_tags_empty_output():
    with patch("src.utils.git_ops.git.cmd.Git") as mock_git_cls:
        mock_git_cls.return_value.ls_remote.return_value = ""
        result = git_ops.list_remote_tags("https://example.com/repo.git")
    assert result == []
