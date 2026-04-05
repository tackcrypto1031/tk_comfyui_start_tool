"""Tests for Snapshot data model."""
import json
import pytest
from pathlib import Path

from src.models.snapshot import Snapshot


class TestSnapshotConstruction:
    """Test Snapshot dataclass creation."""

    def test_create_with_required_fields(self):
        snap = Snapshot(
            id="snap-20260404-100000",
            env_name="main",
            created_at="2026-04-04T10:00:00+08:00",
        )
        assert snap.id == "snap-20260404-100000"
        assert snap.env_name == "main"

    def test_default_values(self):
        snap = Snapshot(
            id="snap-20260404-100000",
            env_name="main",
            created_at="2026-04-04T10:00:00+08:00",
        )
        assert snap.trigger == "manual"
        assert snap.comfyui_commit == ""
        assert snap.custom_nodes_state == []
        assert snap.pip_freeze_path == ""
        assert snap.config_backup_path == ""

    def test_create_auto_snapshot(self):
        snap = Snapshot(
            id="snap-20260404-100000",
            env_name="main",
            created_at="2026-04-04T10:00:00+08:00",
            trigger="version_switch",
            comfyui_commit="abc1234",
        )
        assert snap.trigger == "version_switch"
        assert snap.comfyui_commit == "abc1234"


class TestSnapshotSerialization:
    """Test to_dict / from_dict round-trip."""

    def test_to_dict(self):
        snap = Snapshot(
            id="snap-20260404-100000",
            env_name="main",
            created_at="2026-04-04T10:00:00+08:00",
        )
        d = snap.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "snap-20260404-100000"

    def test_from_dict(self):
        data = {
            "id": "snap-20260404-100000",
            "env_name": "main",
            "created_at": "2026-04-04T10:00:00+08:00",
            "trigger": "clone",
            "comfyui_commit": "abc1234",
            "custom_nodes_state": [{"name": "ComfyUI-Manager", "commit": "def5678"}],
            "pip_freeze_path": "/path/to/freeze.txt",
            "config_backup_path": "/path/to/configs/",
        }
        snap = Snapshot.from_dict(data)
        assert snap.trigger == "clone"
        assert len(snap.custom_nodes_state) == 1

    def test_round_trip(self):
        snap = Snapshot(
            id="snap-20260404-100000",
            env_name="main",
            created_at="2026-04-04T10:00:00+08:00",
            trigger="plugin_install",
            comfyui_commit="abc1234",
        )
        d = snap.to_dict()
        snap2 = Snapshot.from_dict(d)
        assert snap == snap2

    def test_from_dict_missing_optional_fields(self):
        minimal = {
            "id": "snap-20260404-100000",
            "env_name": "main",
            "created_at": "2026-04-04T10:00:00+08:00",
        }
        snap = Snapshot.from_dict(minimal)
        assert snap.trigger == "manual"
