"""Tests for CLI interface."""
import pytest
from click.testing import CliRunner

from cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLIMain:
    """Test main CLI group."""

    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "tack_comfyui_start_tool" in result.output.lower() or "comfyui" in result.output.lower()

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestEnvGroup:
    """Test env command group."""

    def test_env_help(self, runner):
        result = runner.invoke(cli, ["env", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output
        assert "delete" in result.output
        assert "clone" in result.output
        assert "info" in result.output

    def test_env_list_help(self, runner):
        result = runner.invoke(cli, ["env", "list", "--help"])
        assert result.exit_code == 0

    def test_env_create_help(self, runner):
        result = runner.invoke(cli, ["env", "create", "--help"])
        assert result.exit_code == 0
        assert "--branch" in result.output

    def test_env_delete_help(self, runner):
        result = runner.invoke(cli, ["env", "delete", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output

    def test_env_clone_help(self, runner):
        result = runner.invoke(cli, ["env", "clone", "--help"])
        assert result.exit_code == 0

    def test_env_info_help(self, runner):
        result = runner.invoke(cli, ["env", "info", "--help"])
        assert result.exit_code == 0

    def test_env_merge_help(self, runner):
        result = runner.invoke(cli, ["env", "merge", "--help"])
        assert result.exit_code == 0
        assert "--strategy" in result.output


class TestSnapshotGroup:
    """Test snapshot command group."""

    def test_snapshot_help(self, runner):
        result = runner.invoke(cli, ["snapshot", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "list" in result.output
        assert "restore" in result.output


class TestVersionGroup:
    """Test version command group."""

    def test_version_help(self, runner):
        result = runner.invoke(cli, ["version", "--help"])
        assert result.exit_code == 0
        assert "list-commits" in result.output
        assert "switch" in result.output
        assert "update" in result.output


class TestLaunchGroup:
    """Test launch command group."""

    def test_launch_help(self, runner):
        result = runner.invoke(cli, ["launch", "--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "stop" in result.output
        assert "status" in result.output
