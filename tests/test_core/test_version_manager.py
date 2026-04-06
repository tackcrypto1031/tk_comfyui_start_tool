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
