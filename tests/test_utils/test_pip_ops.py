"""Tests for pip_ops utility functions."""
import subprocess
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest

from src.utils.pip_ops import create_venv, get_python_version, run_pip, freeze, get_venv_python


class TestGetVenvPython:
    """Test venv python path resolution."""

    def test_windows_path(self, tmp_path):
        with patch("src.utils.pip_ops.sys") as mock_sys:
            mock_sys.platform = "win32"
            result = get_venv_python(str(tmp_path))
            assert "Scripts" in result
            assert result.endswith("python.exe")

    def test_unix_path(self, tmp_path):
        with patch("src.utils.pip_ops.sys") as mock_sys:
            mock_sys.platform = "linux"
            result = get_venv_python(str(tmp_path))
            assert "bin" in result
            assert result.endswith("python")


class TestCreateVenv:
    """Test venv creation."""

    @patch("src.utils.pip_ops.subprocess.run")
    def test_create_venv(self, mock_run, tmp_path):
        venv_path = tmp_path / "venv"
        create_venv(str(venv_path))

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "venv" in args or "-m" in args
        assert str(venv_path) in args

    @patch("src.utils.pip_ops.subprocess.run")
    def test_create_venv_failure(self, mock_run, tmp_path):
        mock_run.side_effect = subprocess.CalledProcessError(1, "python")
        venv_path = tmp_path / "venv"

        with pytest.raises(subprocess.CalledProcessError):
            create_venv(str(venv_path))


class TestGetPythonVersion:
    """Test python version detection."""

    @patch("src.utils.pip_ops.subprocess.run")
    def test_get_version(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            stdout="Python 3.11.9\n", returncode=0
        )

        result = get_python_version(str(tmp_path))

        assert result == "3.11.9"

    @patch("src.utils.pip_ops.subprocess.run")
    def test_get_version_strips_prefix(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            stdout="Python 3.10.12\n", returncode=0
        )

        result = get_python_version(str(tmp_path))

        assert result == "3.10.12"


class TestRunPip:
    """Test pip command execution."""

    @patch("src.utils.pip_ops.subprocess.run")
    def test_run_pip_install(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(stdout="success", returncode=0)

        result = run_pip(str(tmp_path), ["install", "-r", "requirements.txt"])

        mock_run.assert_called_once()
        assert result.returncode == 0

    @patch("src.utils.pip_ops.subprocess.run")
    def test_run_pip_uses_venv_python(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(stdout="", returncode=0)

        run_pip(str(tmp_path), ["install", "click"])

        call_args = mock_run.call_args[0][0]
        assert "-m" in call_args
        assert "pip" in call_args


class TestFreeze:
    """Test pip freeze output parsing."""

    @patch("src.utils.pip_ops.subprocess.run")
    def test_freeze(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            stdout="click==8.1.7\nrich==13.7.0\ntorch==2.3.1\n",
            returncode=0,
        )

        result = freeze(str(tmp_path))

        assert isinstance(result, dict)
        assert result["click"] == "8.1.7"
        assert result["rich"] == "13.7.0"
        assert result["torch"] == "2.3.1"

    @patch("src.utils.pip_ops.subprocess.run")
    def test_freeze_empty(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(stdout="", returncode=0)

        result = freeze(str(tmp_path))

        assert result == {}

    @patch("src.utils.pip_ops.subprocess.run")
    def test_freeze_skips_editable(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            stdout="-e git+https://github.com/foo/bar@abc#egg=bar\nclick==8.1.7\n",
            returncode=0,
        )

        result = freeze(str(tmp_path))

        assert "bar" not in result
        assert result["click"] == "8.1.7"
