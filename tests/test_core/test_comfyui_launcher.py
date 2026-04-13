"""Tests for ComfyUILauncher core module."""
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from src.core.comfyui_launcher import ComfyUILauncher


@pytest.fixture
def launcher(sample_config):
    inst = ComfyUILauncher(sample_config)
    # Disable the post-spawn sanity delay in tests so start() doesn't
    # sleep 0.5s and so MagicMock process objects (whose poll() returns
    # a MagicMock, which is truthy != None) behave correctly under test
    # control via mock_proc.poll.return_value = None.
    inst._post_spawn_sanity_delay = 0
    return inst


@pytest.fixture
def env_dir(sample_config):
    """Create a fake environment directory structure."""
    envs = Path(sample_config["environments_dir"])
    env = envs / "main"
    env.mkdir(parents=True, exist_ok=True)
    (env / "venv").mkdir(exist_ok=True)
    (env / "ComfyUI").mkdir(exist_ok=True)
    (env / "ComfyUI" / "custom_nodes" / "ComfyUI-Manager").mkdir(parents=True, exist_ok=True)
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
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process is alive
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
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process is alive
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
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8190  # auto-incremented
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process is alive
        mock_proc.pid = 999
        mock_pm.start_process.return_value = mock_proc

        result = launcher.start("main", port=8188)

        # find_available_port is now called with an explicit exclude= kwarg
        # listing ports already claimed by other envs' pid files.
        mock_pm.find_available_port.assert_called_once_with(8188, exclude=set())
        assert result["port"] == 8190

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_with_extra_args(self, mock_pip, mock_pm, launcher, env_dir):
        mock_pip.get_venv_python.return_value = "/venv/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process is alive
        mock_proc.pid = 42
        mock_pm.start_process.return_value = mock_proc

        launcher.start("main", port=8188, extra_args=["--highvram"])

        cmd = mock_pm.start_process.call_args[0][0]
        assert "--highvram" in cmd
        assert "--enable-manager" in cmd
        assert "--listen" in cmd
        assert "127.0.0.1" in cmd

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_does_not_override_custom_listen(self, mock_pip, mock_pm, launcher, env_dir):
        mock_pip.get_venv_python.return_value = "/venv/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process is alive
        mock_proc.pid = 777
        mock_pm.start_process.return_value = mock_proc

        launcher.start("main", port=8188, extra_args=["--listen", "0.0.0.0"])

        cmd = mock_pm.start_process.call_args[0][0]
        assert cmd.count("--listen") == 1
        assert "127.0.0.1" not in cmd

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_raises_if_env_already_running(self, mock_pip, mock_pm, launcher, env_dir):
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        (env_dir / ".comfyui.pid").write_text(json.dumps({"pid": 9999, "port": 8188}))
        mock_pm.is_process_running.return_value = True

        # _pid_belongs_to_env uses psutil; patch it to confirm this pid is ours
        with patch.object(launcher, "_pid_belongs_to_env", return_value=True):
            with pytest.raises(RuntimeError, match="already running"):
                launcher.start("main", port=8188)

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_cleans_up_reservation_on_immediate_crash(
        self, mock_pip, mock_pm, launcher, env_dir
    ):
        """If the subprocess dies within the sanity window, the reservation
        pid file must be deleted so the port doesn't stay claimed."""
        mock_pip.get_venv_python.return_value = "/path/to/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # exited immediately with code 1
        mock_proc.returncode = 1
        mock_proc.pid = 4242
        mock_pm.start_process.return_value = mock_proc

        with pytest.raises(RuntimeError, match="exited immediately"):
            launcher.start("main", port=8188)

        assert not (env_dir / ".comfyui.pid").exists(), \
            "reservation pid file must be cleaned up after an immediate crash"

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_excludes_ports_claimed_by_other_envs(
        self, mock_pip, mock_pm, launcher, env_dir, sample_config
    ):
        """A second env launched while env1 is still starting must be handed
        a different port even if env1 has not yet bound the socket."""
        # Set up a SECOND env directory with a "starting" reservation for
        # port 8188 — simulating env1 that has just called start() and is
        # still booting (has not yet bound the socket).
        import time as _time
        other_env = Path(sample_config["environments_dir"]) / "other"
        other_env.mkdir(parents=True)
        (other_env / "venv").mkdir()
        (other_env / "ComfyUI").mkdir()
        (other_env / ".comfyui.pid").write_text(json.dumps({
            "pid": None, "port": 8188, "status": "starting",
            "started_at": _time.time(),
        }))

        mock_pip.get_venv_python.return_value = "/path/to/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        # Simulate what find_available_port would really do with exclude.
        mock_pm.find_available_port.side_effect = (
            lambda start_port, exclude=None: (
                8189 if exclude and 8188 in exclude else 8188
            )
        )
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 5555
        mock_pm.start_process.return_value = mock_proc

        result = launcher.start("main", port=8188)

        # Verify find_available_port received 8188 in the exclude set.
        call_args = mock_pm.find_available_port.call_args
        assert 8188 in call_args.kwargs["exclude"], \
            "start() must pass the other env's reserved port in exclude="
        # And verify we actually got port 8189 as the result.
        assert result["port"] == 8189

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_writes_starting_state_reservation(
        self, mock_pip, mock_pm, launcher, env_dir
    ):
        """After start() returns, the pid file should be in 'starting' state
        so get_status() and _claimed_ports() recognize the reservation."""
        mock_pip.get_venv_python.return_value = "/path/to/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 7777
        mock_pm.start_process.return_value = mock_proc

        launcher.start("main", port=8188)

        data = json.loads((env_dir / ".comfyui.pid").read_text())
        assert data["status"] == "starting"
        assert data["pid"] == 7777
        assert data["port"] == 8188
        assert "started_at" in data


class TestStartLanUrl:
    @patch("src.core.comfyui_launcher.get_local_lan_ip")
    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_returns_lan_url_when_listening_on_all_interfaces(
        self, mock_pip, mock_pm, mock_lan_ip, launcher, env_dir
    ):
        mock_pip.get_venv_python.return_value = "/venv/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 42
        mock_pm.start_process.return_value = mock_proc
        mock_lan_ip.return_value = "192.168.1.42"

        result = launcher.start("main", port=8188, extra_args=["--listen", "0.0.0.0"])

        assert result["lan_url"] == f"http://192.168.1.42:{result['port']}"

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_no_lan_url_without_listen_arg(
        self, mock_pip, mock_pm, launcher, env_dir
    ):
        mock_pip.get_venv_python.return_value = "/venv/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 42
        mock_pm.start_process.return_value = mock_proc

        result = launcher.start("main", port=8188, extra_args=None)

        assert "lan_url" not in result

    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_no_lan_url_when_listening_on_loopback(
        self, mock_pip, mock_pm, launcher, env_dir
    ):
        mock_pip.get_venv_python.return_value = "/venv/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 42
        mock_pm.start_process.return_value = mock_proc

        result = launcher.start("main", port=8188, extra_args=["--listen", "127.0.0.1"])

        assert "lan_url" not in result


class TestLanUrlPidFile:
    @patch("src.core.comfyui_launcher.get_local_lan_ip")
    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_writes_lan_url_to_pid_file_when_listen_non_loopback(
        self, mock_pip, mock_pm, mock_lan_ip, launcher, env_dir
    ):
        mock_pip.get_venv_python.return_value = "/venv/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_pm.is_port_in_use.return_value = False
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 4242
        mock_pm.start_process.return_value = mock_proc
        mock_lan_ip.return_value = "192.168.1.23"

        with patch.object(launcher, "_ensure_manager_ready"):
            result = launcher.start(
                "main", port=8188, extra_args=["--listen", "0.0.0.0"], auto_open=False
            )

        assert result["lan_url"] == "http://192.168.1.23:8188"

        pid_file = env_dir / ".comfyui.pid"
        assert pid_file.exists()
        pid_data = json.loads(pid_file.read_text())
        assert pid_data["lan_url"] == "http://192.168.1.23:8188"

    @patch("src.core.comfyui_launcher.get_local_lan_ip")
    @patch("src.core.comfyui_launcher.process_manager")
    @patch("src.core.comfyui_launcher.pip_ops")
    def test_start_omits_lan_url_when_listen_loopback(
        self, mock_pip, mock_pm, mock_lan_ip, launcher, env_dir
    ):
        mock_pip.get_venv_python.return_value = "/venv/python"
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}
        mock_pm.find_available_port.return_value = 8188
        mock_pm.is_port_in_use.return_value = False
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 4242
        mock_pm.start_process.return_value = mock_proc
        mock_lan_ip.return_value = "192.168.1.23"

        with patch.object(launcher, "_ensure_manager_ready"):
            result = launcher.start(
                "main", port=8188, extra_args=["--listen", "127.0.0.1"], auto_open=False
            )

        assert "lan_url" not in result

        pid_file = env_dir / ".comfyui.pid"
        assert pid_file.exists()
        pid_data = json.loads(pid_file.read_text())
        assert "lan_url" not in pid_data


class TestStop:
    def test_stop_raises_if_no_pid_file(self, launcher, env_dir):
        with pytest.raises(RuntimeError, match="No running instance"):
            launcher.stop("main")

    @patch("src.core.comfyui_launcher.process_manager")
    def test_stop_calls_stop_process(self, mock_pm, launcher, env_dir):
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": 1234, "port": 8188}))

        # The pid-ownership guard uses psutil; in tests assume the pid is ours.
        with patch.object(launcher, "_pid_belongs_to_env", return_value=True):
            launcher.stop("main")

        mock_pm.stop_process.assert_called_once_with(1234)
        assert not pid_file.exists()

    @patch("src.core.comfyui_launcher.process_manager")
    def test_stop_refuses_to_kill_foreign_pid(self, mock_pm, launcher, env_dir):
        """A pid file whose pid belongs to a different env must not be killed."""
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": 4321, "port": 8188}))
        mock_pm.is_process_running.return_value = True

        with patch.object(launcher, "_pid_belongs_to_env", return_value=False):
            launcher.stop("main")

        mock_pm.stop_process.assert_not_called()
        # pid file is still removed so user isn't permanently stuck
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


class TestEnsureManagerReady:
    @patch("src.core.comfyui_launcher.pip_ops")
    @patch("src.core.comfyui_launcher.git_ops")
    def test_installs_manager_when_missing(self, mock_git, mock_pip, launcher, env_dir):
        shutil.rmtree(env_dir / "ComfyUI" / "custom_nodes" / "ComfyUI-Manager")
        mock_pip.freeze.return_value = {"comfyui-manager": "4.2b1"}

        launcher._ensure_manager_ready(env_dir)

        mock_git.clone_repo.assert_called_once()
        mock_pip.run_pip.assert_not_called()
        config_path = env_dir / "ComfyUI" / "user" / "__manager" / "config.ini"
        assert config_path.exists()
        assert "security_level = normal-" in config_path.read_text(encoding="utf-8")

    @patch("src.core.comfyui_launcher.pip_ops")
    @patch("src.core.comfyui_launcher.git_ops")
    def test_installs_manager_package_from_requirements(self, mock_git, mock_pip, launcher, env_dir):
        mock_pip.freeze.side_effect = [{}, {"comfyui_manager": "4.1"}]
        ok = MagicMock()
        ok.returncode = 0
        ok.stdout = ""
        ok.stderr = ""
        mock_pip.run_pip.return_value = ok

        req = env_dir / "ComfyUI" / "manager_requirements.txt"
        req.write_text("comfyui_manager==4.1\n", encoding="utf-8")

        launcher._ensure_manager_ready(env_dir)

        assert mock_pip.run_pip.call_args[0][1][:2] == ["install", "-r"]

    @patch("src.core.comfyui_launcher.pip_ops")
    @patch("src.core.comfyui_launcher.git_ops")
    def test_raises_when_manager_package_install_fails(self, mock_git, mock_pip, launcher, env_dir):
        mock_pip.freeze.return_value = {}
        failed = MagicMock()
        failed.returncode = 1
        failed.stdout = ""
        failed.stderr = "network error"
        mock_pip.run_pip.return_value = failed

        with pytest.raises(RuntimeError, match="Failed to install comfyui-manager package"):
            launcher._ensure_manager_ready(env_dir)

    @patch("src.core.comfyui_launcher.git_ops")
    def test_raises_when_manager_install_fails(self, mock_git, launcher, env_dir):
        shutil.rmtree(env_dir / "ComfyUI" / "custom_nodes" / "ComfyUI-Manager")
        mock_git.clone_repo.side_effect = RuntimeError("network error")

        with pytest.raises(RuntimeError, match="Failed to install ComfyUI-Manager repository"):
            launcher._ensure_manager_ready(env_dir)

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

        with patch.object(launcher, "_pid_belongs_to_env", return_value=True):
            result = launcher.get_status("main")

        assert result["status"] == "running"
        assert result["pid"] == 1234

    @patch("src.core.comfyui_launcher.process_manager")
    def test_status_drops_foreign_pid_file(self, mock_pm, launcher, env_dir):
        """A pid file pointing at another env's live process is treated as stopped."""
        mock_pm.is_process_running.return_value = True
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": 1234, "port": 8188}))

        with patch.object(launcher, "_pid_belongs_to_env", return_value=False):
            result = launcher.get_status("main")

        assert result["status"] == "stopped"
        assert not pid_file.exists()

    @patch("src.core.comfyui_launcher.process_manager")
    def test_status_stopped_stale_pid(self, mock_pm, launcher, env_dir):
        mock_pm.is_process_running.return_value = False
        mock_pm.is_port_in_use.return_value = False
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

        with patch.object(launcher, "_pid_belongs_to_env", return_value=True):
            result = launcher.list_running()

        assert len(result) == 1
        assert result[0]["env_name"] == "main"
        assert result[0]["pid"] == 1234

    @patch("src.core.comfyui_launcher.process_manager")
    def test_list_running_excludes_foreign_pid(self, mock_pm, launcher, env_dir):
        """A pid file pointing at another env's live process must NOT appear
        as 'running' for this env — that would mis-attribute the other env's
        pid and cause stop actions to kill the wrong process."""
        mock_pm.is_process_running.return_value = True
        mock_pm.find_pid_on_port.return_value = None
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({
            "pid": 1234, "port": 8188,
            "_fail_count": launcher._MAX_FAIL_COUNT,
        }))

        with patch.object(launcher, "_pid_belongs_to_env", return_value=False):
            result = launcher.list_running()

        assert result == []

    @patch("src.core.comfyui_launcher.process_manager")
    def test_list_running_excludes_dead(self, mock_pm, launcher, env_dir):
        """Dead process beyond grace period should be excluded."""
        mock_pm.is_process_running.return_value = False
        mock_pm.is_port_in_use.return_value = False
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({
            "pid": 9999, "port": 8188,
            "_fail_count": launcher._MAX_FAIL_COUNT,
        }))

        result = launcher.list_running()

        assert result == []

    @patch("src.core.comfyui_launcher.process_manager")
    def test_list_running_grace_period_keeps_restarting(self, mock_pm, launcher, env_dir):
        """Dead process within grace period should appear with 'restarting' status."""
        mock_pm.is_process_running.return_value = False
        mock_pm.is_port_in_use.return_value = False
        pid_file = env_dir / ".comfyui.pid"
        pid_file.write_text(json.dumps({"pid": 9999, "port": 8188}))

        result = launcher.list_running()

        assert len(result) == 1
        assert result[0]["env_name"] == "main"
        assert result[0]["status"] == "restarting"
