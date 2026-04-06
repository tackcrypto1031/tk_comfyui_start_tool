"""Tests for VersionManager core module."""
import json
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest

from src.core.version_manager import (
    VersionManager,
    DEFAULT_PYTHON_VERSIONS,
    DEFAULT_CUDA_TAGS,
)


@pytest.fixture
def sample_config(tmp_path):
    return {"base_dir": str(tmp_path)}


class TestDetectGpu:
    """Test GPU detection via nvidia-smi."""

    def test_detect_gpu_with_nvidia(self, sample_config):
        mock_result = MagicMock()
        mock_result.stdout = "NVIDIA-SMI 550.90.07  Driver Version: 550.90.07  CUDA Version: 12.6\n"
        with patch("subprocess.run", return_value=mock_result):
            manager = VersionManager(sample_config)
            info = manager.detect_gpu()
        assert info["has_gpu"] is True
        assert info["cuda_driver_version"] == "12.6"
        assert info["recommended_cuda_tag"] == "cu126"

    def test_detect_gpu_no_nvidia(self, sample_config):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            manager = VersionManager(sample_config)
            info = manager.detect_gpu()
        assert info["has_gpu"] is False
        assert info["recommended_cuda_tag"] == "cpu"

    def test_detect_gpu_timeout(self, sample_config):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 10)):
            manager = VersionManager(sample_config)
            info = manager.detect_gpu()
        assert info["has_gpu"] is False
        assert info["recommended_cuda_tag"] == "cpu"

    def test_detect_gpu_maps_to_closest_tag(self, sample_config):
        mock_result = MagicMock()
        mock_result.stdout = "CUDA Version: 12.5\n"
        with patch("subprocess.run", return_value=mock_result):
            manager = VersionManager(sample_config)
            info = manager.detect_gpu()
        assert info["has_gpu"] is True
        assert info["cuda_driver_version"] == "12.5"
        # 12.5 is between cu124 (12.4) and cu126 (12.6) — should map to cu124
        assert info["recommended_cuda_tag"] == "cu124"


class TestGetVersionLists:
    """Test version list getters."""

    def test_get_default_python_versions(self, sample_config):
        manager = VersionManager(sample_config)
        versions = manager.get_python_versions()
        assert len(versions) >= 4
        version_strings = [v["version"] for v in versions]
        assert "3.12" in version_strings

    def test_get_default_cuda_tags(self, sample_config):
        manager = VersionManager(sample_config)
        tags = manager.get_cuda_tags()
        assert "cpu" in tags
        assert "cu124" in tags


class TestCache:
    """Test cache load/save behavior."""

    def test_load_cache_returns_none_when_no_cache(self, sample_config):
        manager = VersionManager(sample_config)
        result = manager._load_cache()
        assert result is None

    def test_save_and_load_cache(self, sample_config, tmp_path):
        manager = VersionManager(sample_config)
        data = {
            "last_updated": "2024-01-01T00:00:00",
            "python": [{"version": "3.12", "display": "Python 3.12"}],
            "cuda_tags": ["cpu", "cu124"],
        }
        manager._save_cache(data)
        loaded = manager._load_cache()
        assert loaded is not None
        assert loaded["python"] == data["python"]
        assert loaded["cuda_tags"] == data["cuda_tags"]
        assert loaded["last_updated"] == data["last_updated"]

    def test_get_python_versions_from_cache(self, sample_config):
        manager = VersionManager(sample_config)
        cached_data = {
            "last_updated": "2024-01-01T00:00:00",
            "python": [{"version": "3.9", "display": "Python 3.9"}],
            "cuda_tags": ["cpu"],
        }
        manager._save_cache(cached_data)
        versions = manager.get_python_versions()
        assert versions == cached_data["python"]

    def test_get_cache_info_no_cache(self, sample_config):
        manager = VersionManager(sample_config)
        info = manager.get_cache_info()
        assert info is None


class TestRefresh:
    """Test online refresh methods."""

    PYTHON_JSON = [
        {
            "company": "PythonEmbed",
            "sort-version": "3.12.0",
            "display-name": "Python 3.12.0",
            "url": "https://example.com/python-3.12.0-embed-amd64.zip",
            "hash": {"sha256": "abc123"},
        },
        {
            "company": "PythonEmbed",
            "sort-version": "3.11.0",
            "display-name": "Python 3.11.0",
            "url": "https://example.com/python-3.11.0-embed-amd64.zip",
            "hash": {"sha256": "def456"},
        },
        {
            "company": "PythonCore",
            "sort-version": "3.10.0",
            "display-name": "Python 3.10.0",
            "url": "https://example.com/python-3.10.0.exe",
            "hash": {"sha256": "ghi789"},
        },
    ]

    CUDA_HTML = """
    <html><body>
    <a href="cpu/">cpu/</a>
    <a href="cu118/">cu118/</a>
    <a href="cu121/">cu121/</a>
    <a href="cu124/">cu124/</a>
    <a href="cu126/">cu126/</a>
    <a href="nightly/">nightly/</a>
    </body></html>
    """

    def test_refresh_python_versions_success(self, sample_config):
        mock_response = MagicMock()
        mock_response.json.return_value = self.PYTHON_JSON
        with patch("requests.get", return_value=mock_response):
            manager = VersionManager(sample_config)
            result = manager.refresh_python_versions()
        # Only PythonEmbed entries returned
        assert len(result) == 2
        # Sorted descending by version
        assert result[0]["version"] == "3.12.0"
        assert result[1]["version"] == "3.11.0"
        # Fields present
        assert result[0]["display"] == "Python 3.12.0"
        assert "url" in result[0]
        assert "sha256" in result[0]

    def test_refresh_cuda_tags_success(self, sample_config):
        mock_response = MagicMock()
        mock_response.text = self.CUDA_HTML
        with patch("requests.get", return_value=mock_response):
            manager = VersionManager(sample_config)
            result = manager.refresh_cuda_tags()
        # nightly excluded
        assert "nightly" not in result
        # cpu first
        assert result[0] == "cpu"
        # cu tags sorted numerically after cpu
        assert result == ["cpu", "cu118", "cu121", "cu124", "cu126"]

    def test_refresh_all_saves_cache(self, sample_config):
        manager = VersionManager(sample_config)
        py_versions = [{"version": "3.12.0", "display": "Python 3.12.0", "url": "", "sha256": ""}]
        cuda_tags = ["cpu", "cu124"]
        with patch.object(manager, "refresh_python_versions", return_value=py_versions), \
             patch.object(manager, "refresh_cuda_tags", return_value=cuda_tags):
            result = manager.refresh_all()
        # Cache file written
        assert manager._cache_path.exists()
        loaded = manager._load_cache()
        assert loaded is not None
        assert loaded["python"] == py_versions
        assert loaded["cuda_tags"] == cuda_tags
        assert "last_updated" in loaded
        # Return value matches cache
        assert result["python"] == py_versions
        assert result["cuda_tags"] == cuda_tags

    def test_refresh_failure_raises(self, sample_config):
        with patch("requests.get", side_effect=Exception("network error")):
            manager = VersionManager(sample_config)
            with pytest.raises(RuntimeError, match="Failed to refresh Python versions"):
                manager.refresh_python_versions()
        with patch("requests.get", side_effect=Exception("network error")):
            manager = VersionManager(sample_config)
            with pytest.raises(RuntimeError, match="Failed to refresh CUDA tags"):
                manager.refresh_cuda_tags()


class TestGetPythonExecutable:
    """Test get_python_executable path resolution."""

    def test_get_python_executable_bundled(self, sample_config, tmp_path):
        manager = VersionManager(sample_config)
        # Create fake bundled python
        bundled_path = manager.tools_dir / "python" / "python.exe"
        bundled_path.parent.mkdir(parents=True, exist_ok=True)
        bundled_path.touch()
        result = manager.get_python_executable("3.11.9", bundled_version="3.11.9")
        assert result == bundled_path

    def test_get_python_executable_custom(self, sample_config, tmp_path):
        manager = VersionManager(sample_config)
        # Create fake custom python
        custom_path = manager.tools_dir / "python_3.10.16" / "python.exe"
        custom_path.parent.mkdir(parents=True, exist_ok=True)
        custom_path.touch()
        result = manager.get_python_executable("3.10.16", bundled_version="3.11.9")
        assert result == custom_path

    def test_get_python_executable_not_installed(self, sample_config):
        manager = VersionManager(sample_config)
        with pytest.raises(FileNotFoundError, match="not installed"):
            manager.get_python_executable("3.10.16")


class TestReinstallPytorch:
    def test_reinstall_pytorch_updates_meta(self, tmp_path):
        """reinstall_pytorch calls pip uninstall + install and updates env_meta."""
        config = {
            "base_dir": str(tmp_path),
            "environments_dir": str(tmp_path / "environments"),
        }
        vm = VersionManager(config)

        # Create fake env with meta
        env_dir = tmp_path / "environments" / "test1"
        env_dir.mkdir(parents=True)
        (env_dir / "venv").mkdir()
        meta = {
            "name": "test1",
            "created_at": "2026-04-06",
            "cuda_tag": "cu124",
            "pytorch_version": "2.5.0",
        }
        (env_dir / "env_meta.json").write_text(json.dumps(meta), encoding="utf-8")

        with patch("src.utils.pip_ops.run_pip") as mock_uninstall:
            with patch("src.utils.pip_ops.run_pip_with_progress") as mock_install:
                with patch("src.utils.pip_ops.freeze", return_value={"torch": "2.6.0"}):
                    result = vm.reinstall_pytorch("test1", "cu126")

        assert result["cuda_tag"] == "cu126"
        assert result["pytorch_version"] == "2.6.0"
        # Verify pip uninstall was called
        mock_uninstall.assert_called_once()
        assert "uninstall" in mock_uninstall.call_args[0][1]
        # Verify pip install was called with new index
        mock_install.assert_called_once()
        assert "cu126" in str(mock_install.call_args)

    def test_reinstall_pytorch_env_not_found(self, tmp_path):
        config = {
            "base_dir": str(tmp_path),
            "environments_dir": str(tmp_path / "environments"),
        }
        vm = VersionManager(config)
        with pytest.raises(FileNotFoundError):
            vm.reinstall_pytorch("nonexistent", "cu126")
