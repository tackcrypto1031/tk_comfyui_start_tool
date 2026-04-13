"""Tests for git_ops utility functions."""
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from src.utils.git_ops import (
    clone_repo, get_current_commit, get_branches, get_log, checkout, pull,
    get_remote_head_for_current_branch, has_remote_updates,
)
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

        mock_clone.assert_called_once_with(
            COMFYUI_URL, str(dest), branch="master", progress=None
        )
        assert result == mock_repo

    @patch("src.utils.git_ops.git.Repo.clone_from")
    def test_clone_with_branch(self, mock_clone, tmp_path):
        mock_repo = MagicMock()
        mock_clone.return_value = mock_repo
        dest = tmp_path / "ComfyUI"

        clone_repo(COMFYUI_URL, str(dest), branch="develop")

        mock_clone.assert_called_once_with(
            COMFYUI_URL, str(dest), branch="develop", progress=None
        )

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


@patch("src.utils.git_ops.git.Repo")
def test_get_remote_head_for_current_branch_prefers_active_branch(mock_repo_cls):
    mock_repo = MagicMock()
    mock_repo.head.is_detached = False
    mock_repo.active_branch.name = "main"
    mock_repo.git.ls_remote.return_value = "abc123\trefs/heads/main\n"
    mock_repo_cls.return_value = mock_repo

    result = get_remote_head_for_current_branch("/path/to/repo")

    assert result == "abc123"
    mock_repo.git.ls_remote.assert_called_once_with("--heads", "origin", "refs/heads/main")


@patch("src.utils.git_ops.git.Repo")
def test_get_remote_head_for_current_branch_ignores_partial_branch_matches(mock_repo_cls):
    mock_repo = MagicMock()
    mock_repo.head.is_detached = False
    mock_repo.active_branch.name = "main"
    mock_repo.git.ls_remote.return_value = (
        "bad111\trefs/heads/user/main\n"
        "good222\trefs/heads/main\n"
    )
    mock_repo_cls.return_value = mock_repo

    result = get_remote_head_for_current_branch("/path/to/repo")

    assert result == "good222"


@patch("src.utils.git_ops.git.Repo")
def test_get_remote_head_for_current_branch_falls_back_to_origin_head(mock_repo_cls):
    mock_repo = MagicMock()
    mock_repo.head.is_detached = False
    mock_repo.active_branch.name = "main"
    mock_repo.git.ls_remote.side_effect = [
        "",
        "def456\tHEAD\n",
    ]
    mock_repo_cls.return_value = mock_repo

    result = get_remote_head_for_current_branch("/path/to/repo")

    assert result == "def456"
    assert mock_repo.git.ls_remote.call_count == 2


@patch("src.utils.git_ops.get_remote_head_for_current_branch")
@patch("src.utils.git_ops.get_current_commit")
def test_has_remote_updates_true(mock_get_current_commit, mock_get_remote):
    mock_get_current_commit.return_value = "abc123"
    mock_get_remote.return_value = "def456"
    assert has_remote_updates("/path/to/repo") is True


@patch("src.utils.git_ops.get_remote_head_for_current_branch")
@patch("src.utils.git_ops.get_current_commit")
def test_has_remote_updates_false(mock_get_current_commit, mock_get_remote):
    mock_get_current_commit.return_value = "abc123"
    mock_get_remote.return_value = "abc123"
    assert has_remote_updates("/path/to/repo") is False


@patch("src.utils.git_ops.get_remote_head_for_current_branch")
@patch("src.utils.git_ops.get_current_commit")
def test_has_remote_updates_unknown_when_remote_unresolved(mock_get_current_commit, mock_get_remote):
    mock_get_current_commit.return_value = "abc123"
    mock_get_remote.return_value = None
    assert has_remote_updates("/path/to/repo") is None


def test_list_branches_with_dates(tmp_path):
    import git
    from src.utils import git_ops
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = git.Repo.init(repo_path)
    (repo_path / "README.md").write_text("hi")
    repo.index.add(["README.md"])
    repo.index.commit("init", author=git.Actor("a", "a@x"), committer=git.Actor("a", "a@x"))
    repo.create_head("feature")
    repo.heads["feature"].checkout()
    (repo_path / "f.txt").write_text("x")
    repo.index.add(["f.txt"])
    repo.index.commit("feat", author=git.Actor("a", "a@x"), committer=git.Actor("a", "a@x"))
    origin = repo.create_remote("origin", str(repo_path))
    origin.fetch()

    result = git_ops.list_branches_with_dates(str(repo_path))
    names = [b["name"] for b in result]
    assert "feature" in names
    assert "master" in names or "main" in names
    for b in result:
        assert "date" in b and b["date"]
    assert names.index("feature") < names.index("master" if "master" in names else "main")
