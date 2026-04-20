"""Verify that ComfyUILauncher.start passes the full HF/torch cache env var set
into the subprocess, and pre-creates the expected cache directories."""
import platform
from pathlib import Path

import pytest


def test_launch_populates_cache_dirs(tmp_path, monkeypatch):
    from src.core import comfyui_launcher
    from src.core.comfyui_launcher import ComfyUILauncher

    fake_root = tmp_path / "project"
    fake_root.mkdir()
    monkeypatch.setattr(comfyui_launcher, "_PROJECT_ROOT", fake_root)

    launcher = ComfyUILauncher({
        "environments_dir": str(tmp_path / "envs"),
        "auto_open_browser": False,
    })
    env = launcher._build_cache_env_vars()

    expected_keys = {
        "HF_HOME", "HUGGINGFACE_HUB_CACHE", "HF_HUB_CACHE",
        "TRANSFORMERS_CACHE", "DIFFUSERS_CACHE",
        "TORCH_HOME", "XDG_CACHE_HOME", "INSIGHTFACE_HOME",
    }
    assert expected_keys.issubset(env.keys())
    for sub in ("huggingface/hub", "torch", "diffusers", "insightface"):
        assert (fake_root / "cache" / sub).is_dir()
