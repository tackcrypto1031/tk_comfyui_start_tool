"""Shared test fixtures for tack_comfyui_start_tool."""
import json
import pytest
from pathlib import Path


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with standard structure."""
    envs_dir = tmp_path / "environments"
    models_dir = tmp_path / "models"
    snapshots_dir = tmp_path / "snapshots"
    envs_dir.mkdir()
    models_dir.mkdir()
    snapshots_dir.mkdir()
    return tmp_path


@pytest.fixture
def sample_config(tmp_project):
    """Return a sample config dict pointing to tmp_project."""
    return {
        "version": "0.1.0",
        "default_env": "main",
        "python_path": None,
        "comfyui_repo_url": "https://github.com/comfyanonymous/ComfyUI.git",
        "base_dir": str(tmp_project),
        "environments_dir": str(tmp_project / "environments"),
        "models_dir": str(tmp_project / "models"),
        "snapshots_dir": str(tmp_project / "snapshots"),
        "max_snapshots": 20,
        "auto_snapshot": True,
        "auto_open_browser": True,
        "default_port": 8188,
        "theme": "dark",
        "language": "zh-TW",
        "log_level": "INFO",
        "model_subdirs": [
            "checkpoints", "loras", "vae", "controlnet",
            "clip", "embeddings", "upscale_models"
        ],
        "conflict_analyzer": {
            "critical_packages": [
                "torch", "torchvision", "torchaudio",
                "numpy", "scipy", "transformers",
                "safetensors", "Pillow", "xformers",
                "opencv-python", "opencv-python-headless",
                "accelerate", "onnxruntime", "onnxruntime-gpu"
            ],
            "auto_analyze_on_install": True
        }
    }


@pytest.fixture
def sample_env_meta():
    """Return a sample env_meta dict."""
    return {
        "name": "main",
        "created_at": "2026-04-04T10:00:00+08:00",
        "comfyui_commit": "abc1234",
        "comfyui_branch": "master",
        "python_version": "3.11.9",
        "pip_freeze": {"torch": "2.3.1", "numpy": "1.26.4"},
        "custom_nodes": [],
        "snapshots": [],
        "parent_env": None,
        "merge_history": []
    }
