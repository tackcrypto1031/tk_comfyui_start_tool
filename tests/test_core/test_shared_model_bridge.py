import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.shared_model_bridge import SharedModelBridge


pytestmark = pytest.mark.skipif(
    platform.system() != "Windows",
    reason="shared_model_bridge is Windows-specific.",
)


def make_bridge(shared_path: Path, excluded=None):
    config = {
        "model_subdirs": ["checkpoints", "loras", "configs"],
        "shared_model_subdirs_excluded": excluded or ["configs"],
    }
    resolver = lambda: shared_path
    return SharedModelBridge(config, resolver)


def test_detect_capability_same_volume_returns_junction(tmp_path):
    env_path = tmp_path / "env"
    env_path.mkdir()
    shared = tmp_path / "shared"
    shared.mkdir()
    bridge = make_bridge(shared)

    assert bridge.detect_capability(shared, env_path) == "junction"


def test_detect_capability_cross_volume_falls_back_to_yaml(tmp_path, monkeypatch):
    env_path = tmp_path / "env"
    env_path.mkdir()
    shared = tmp_path / "shared"
    shared.mkdir()
    bridge = make_bridge(shared)
    monkeypatch.setattr("src.core.shared_model_bridge.fs_ops.same_volume", lambda a, b: False)
    monkeypatch.setattr("src.core.shared_model_bridge.fs_ops.create_symlink_dir",
                        lambda a, b: (_ for _ in ()).throw(OSError("no Dev Mode")))

    assert bridge.detect_capability(shared, env_path) == "yaml_only"
