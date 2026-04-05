"""Tests for ComfyUILauncher core module."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from src.core.comfyui_launcher import ComfyUILauncher


@pytest.fixture
def launcher(sample_config):
    return ComfyUILauncher(sample_config)


@pytest.fixture
def env_dir(sample_config):
    """Create a fake environment directory structure."""
    envs = Path(sample_config["environments_dir"])
    env = envs / "main"
    env.mkdir(parents=True, exist_ok=True)
    (env / "venv").mkdir(exist_ok=True)
    (env / "ComfyUI").mkdir(exist_ok=True)
    return env


class TestComfyUILauncherInit:
    def test_init(self, sample_config):
        launcher = ComfyUILauncher(sample_config)
        assert launcher.config == sample_config
        assert str(launcher.environments_dir) == sample_config["environments_dir"]


class TestStart:
    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_returns_pid_port(self, mock_pip, mock_pm, launcher, env_dir):
        mock_pip.get_venv_python.return_value = "/path/to/python"
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_pm.start_process.return_value = mock_proc

        result = launcher.start("main", port=8188)

        assert result["pid"] == 1234
        assert result["port"] == 8188
        assert result["env_name"] == "main"

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_writes_pid_file(self, mock_pip, mock_pm, launcher, env_dir):
        mock_pip.get_venv_python.return_value = "/path/to/python"
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.pid = 5678
        mock_pm.start_process.return_value = mock_proc

        launcher.start("main", port=8188)

        pid_file = env_dir / ".comfyui.pid"
        assert pid_file.exists()
        data = json.loads(pid_file.read_text())
        assert data["pid"] == 5678
        assert data["port"] == 8188

    def test_start_raises_if_env_not_found(self, launcher):
        with pytest.raises(FileNotFoundError, match="not found"):
            launcher.start("nonexistent")

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_uses_available_port(self, mock_pip, mock_pm, launcher, env_dir):
        mock_pip.get_venv_python.return_value = "/path/to/python"
        mock_pm.find_available_port.return_value = 8190  # auto-incremented
        mock_proc = MagicMock()
        mock_proc.pid = 999
        mock_pm.start_process.return_value = mock_proc

        result = launcher.start("main", port=8188)

        mock_pm.find_available_port.assert_called_once_with(8188)
        assert result["port"] == 8190

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_with_extra_args(self, mock_pip, mock_pm, launcher, env_dir):
        mock_pip.get_venv_python.return_value = "/venv/python"
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_pm.start_process.return_value = mock_proc

        launcher.start("main", port=8188, extra_args=["--highvram"])

        cmd = mock_pm.start_process.call_args[0][0]
        assert "--highvram" in cmd


class TestStop:
    def test_stop_raises_if_no_pid_file(self, launcher, env_dir):
        with pytest.raises(RuntimeError, match="No running instance"):
            launcher.stop("main")

    @patch("src.core.comfyui_launcher.process_manager")
    def test_stop_calls_stop_process(self, mock_pm, launcher, env_dir):
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": 1234, "port": 8188}))

        launcher.stop("main")

        mock_pm.stop_process.assert_called_once_with(1234)
        assert not pid_file.exists()


class TestHealthCheck:
    @patch("src.core.comfyui_launcher.requests.get")
    def test_health_check_ok(self, mock_get, launcher):
        mock_get.return_value = MagicMock(status_code=200)

        assert launcher.health_check(8188) is True

    @patch("src.core.comfyui_launcher.requests.get")
    def test_health_check_connection_error(self, mock_get, launcher):
        import requests
        mock_get.side_effect = requests.ConnectionError

        assert launcher.health_check(8188) is False

    @patch("src.core.comfyui_launcher.requests.get")
    def test_health_check_non_200(self, mock_get, launcher):
        mock_get.return_value = MagicMock(status_code=500)

        assert launcher.health_check(8188) is False


class TestGetStatus:
    def test_status_stopped_no_pid_file(self, launcher, env_dir):
        result = launcher.get_status("main")
        assert result["status"] == "stopped"
        assert result["env_name"] == "main"

    @patch("src.core.comfyui_launcher.process_manager")
    def test_status_running(self, mock_pm, launcher, env_dir):
        mock_pm.is_process_running.return_value = True
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": 1234, "port": 8188}))

        result = launcher.get_status("main")

        assert result["status"] == "running"
        assert result["pid"] == 1234

    @patch("src.core.comfyui_launcher.process_manager")
    def test_status_stopped_stale_pid(self, mock_pm, launcher, env_dir):
        mock_pm.is_process_running.return_value = False
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": 9999, "port": 8188}))

        result = launcher.get_status("main")

        assert result["status"] == "stopped"


class TestListRunning:
    def test_list_running_empty(self, launcher):
        result = launcher.list_running()
        assert result == []

    @patch("src.core.comfyui_launcher.process_manager")
    def test_list_running_returns_active(self, mock_pm, launcher, env_dir):
        mock_pm.is_process_running.return_value = True
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": 1234, "port": 8188}))

        result = launcher.list_running()

        assert len(result) == 1
        assert result[0]["env_name"] == "main"
        assert result[0]["pid"] == 1234

    @patch("src.core.comfyui_launcher.process_manager")
    def test_list_running_excludes_dead(self, mock_pm, launcher, env_dir):
        mock_pm.is_process_running.return_value = False
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": 9999, "port": 8188}))

        result = launcher.list_running()

        assert result == []
