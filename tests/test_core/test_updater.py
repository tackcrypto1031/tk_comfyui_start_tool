"""Tests for updater safety behavior."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core import updater


def _ok_result():
    return MagicMock(returncode=0, stdout="", stderr="")


class TestDoUpdateNoGitPath:
    @patch("src.core.updater._find_python", return_value="python")
    @patch("src.core.updater._find_git", return_value="git")
    @patch("src.core.updater.subprocess.run")
    def test_no_git_path_uses_checkout_not_reset(
        self, mock_run, _mock_find_git, _mock_find_python, tmp_path
    ):
        mock_run.side_effect = [_ok_result(), _ok_result(), _ok_result(), _ok_result()]

        with patch.object(updater, "_ROOT", Path(tmp_path)):
            result = updater.do_update()

        assert result["success"] is True

        commands = [c.args[0] for c in mock_run.call_args_list]
        assert ["git", "checkout", "-B", "master", "origin/master"] in commands
        assert not any(cmd[:2] == ["git", "reset"] for cmd in commands)

    @patch("src.core.updater._find_python", return_value="python")
    @patch("src.core.updater._find_git", return_value="git")
    @patch("src.core.updater.subprocess.run")
    def test_no_git_path_checkout_conflict_gives_clear_error(
        self, mock_run, _mock_find_git, _mock_find_python, tmp_path
    ):
        conflict = MagicMock(
            returncode=1,
            stdout="",
            stderr="error: The following untracked working tree files would be overwritten by checkout:",
        )
        mock_run.side_effect = [_ok_result(), _ok_result(), _ok_result(), conflict]

        with patch.object(updater, "_ROOT", Path(tmp_path)):
            with pytest.raises(RuntimeError, match="local file conflicts"):
                updater.do_update()

    @patch("src.core.updater._find_python", return_value="python")
    @patch("src.core.updater._find_git", return_value="git")
    @patch("src.core.updater.subprocess.run")
    def test_no_git_path_checkout_generic_error_bubbles(
        self, mock_run, _mock_find_git, _mock_find_python, tmp_path
    ):
        failure = MagicMock(returncode=1, stdout="", stderr="fatal: checkout failed")
        mock_run.side_effect = [_ok_result(), _ok_result(), _ok_result(), failure]

        with patch.object(updater, "_ROOT", Path(tmp_path)):
            with pytest.raises(RuntimeError, match="git checkout failed: fatal: checkout failed"):
                updater.do_update()
