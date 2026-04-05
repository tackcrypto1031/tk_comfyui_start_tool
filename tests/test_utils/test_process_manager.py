"""Tests for process_manager utility functions."""
import socket
import subprocess
from unittest.mock import patch, MagicMock, call
import pytest

from src.utils.process_manager import (
    start_process,
    stop_process,
    is_process_running,
    is_port_in_use,
    find_available_port,
)


class TestStartProcess:
    """Test subprocess launch."""

    @patch("src.utils.process_manager.subprocess.Popen")
    def test_start_process_returns_popen(self, mock_popen):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        result = start_process(["python", "main.py"])

        assert result is mock_proc
        mock_popen.assert_called_once()

    @patch("src.utils.process_manager.subprocess.Popen")
    def test_start_process_passes_cmd_cwd_env(self, mock_popen):
        mock_popen.return_value = MagicMock()

        start_process(["python", "main.py"], cwd="/some/dir", env={"FOO": "bar"})

        call_kwargs = mock_popen.call_args
        assert call_kwargs[0][0] == ["python", "main.py"]
        assert call_kwargs[1]["cwd"] == "/some/dir"
        assert call_kwargs[1]["env"] == {"FOO": "bar"}

    @patch("src.utils.process_manager.subprocess.Popen")
    def test_start_process_uses_devnull_by_default(self, mock_popen):
        mock_popen.return_value = MagicMock()

        start_process(["python", "--version"])

        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs["stdout"] == subprocess.DEVNULL
        assert call_kwargs["stderr"] == subprocess.DEVNULL
        assert call_kwargs["text"] is True

    @patch("src.utils.process_manager.subprocess.Popen")
    def test_start_process_uses_pipe_when_capture_output(self, mock_popen):
        mock_popen.return_value = MagicMock()

        start_process(["python", "--version"], capture_output=True)

        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs["stdout"] == subprocess.PIPE
        assert call_kwargs["stderr"] == subprocess.PIPE
        assert call_kwargs["text"] is True


class TestStopProcess:
    """Test process termination."""

    @patch("src.utils.process_manager.psutil.Process")
    def test_stop_process_graceful(self, mock_process_cls):
        mock_proc = MagicMock()
        mock_process_cls.return_value = mock_proc

        result = stop_process(1234)

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()
        assert result is True

    @patch("src.utils.process_manager.psutil.Process")
    def test_stop_process_force_kill_on_timeout(self, mock_process_cls):
        import psutil
        mock_proc = MagicMock()
        mock_proc.wait.side_effect = psutil.TimeoutExpired(1234, 5)
        mock_process_cls.return_value = mock_proc

        result = stop_process(1234, graceful_timeout=5)

        mock_proc.kill.assert_called_once()
        assert result is True

    @patch("src.utils.process_manager.psutil.Process")
    def test_stop_process_no_such_process(self, mock_process_cls):
        import psutil
        mock_process_cls.side_effect = psutil.NoSuchProcess(9999)

        result = stop_process(9999)

        assert result is False


class TestIsProcessRunning:
    """Test process existence check."""

    @patch("src.utils.process_manager.psutil.pid_exists")
    def test_is_running_true(self, mock_pid_exists):
        mock_pid_exists.return_value = True

        assert is_process_running(1234) is True
        mock_pid_exists.assert_called_once_with(1234)

    @patch("src.utils.process_manager.psutil.pid_exists")
    def test_is_running_false(self, mock_pid_exists):
        mock_pid_exists.return_value = False

        assert is_process_running(9999) is False


class TestIsPortInUse:
    """Test port availability check."""

    @patch("src.utils.process_manager.socket.socket")
    def test_port_in_use_returns_true(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_cls.return_value.__enter__ = lambda s: mock_sock
        mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)

        assert is_port_in_use(8188) is True

    @patch("src.utils.process_manager.socket.socket")
    def test_port_not_in_use_returns_false(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111  # connection refused
        mock_socket_cls.return_value.__enter__ = lambda s: mock_sock
        mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)

        assert is_port_in_use(8188) is False


class TestFindAvailablePort:
    """Test port scanning."""

    @patch("src.utils.process_manager.is_port_in_use")
    def test_first_port_free(self, mock_in_use):
        mock_in_use.return_value = False

        result = find_available_port(8188)

        assert result == 8188

    @patch("src.utils.process_manager.is_port_in_use")
    def test_increments_when_occupied(self, mock_in_use):
        # first two occupied, third free
        mock_in_use.side_effect = [True, True, False]

        result = find_available_port(8188)

        assert result == 8190

    @patch("src.utils.process_manager.is_port_in_use")
    def test_raises_when_all_occupied(self, mock_in_use):
        mock_in_use.return_value = True

        with pytest.raises(RuntimeError, match="No available port"):
            find_available_port(8188, max_tries=3)
