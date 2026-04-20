"""Tests for Bridge addon registry editor slots."""
import json
import shutil

import pytest

# Bridge needs Qt; skip if PySide6 not installed in test env
pytest.importorskip("PySide6")

from src.gui.bridge import Bridge


@pytest.fixture
def bridge(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Seed shipped addons.json + torch_packs.json from repo copies
    shutil.copy("data/addons.json", data_dir / "addons.json")
    shutil.copy("data/torch_packs.json", data_dir / "torch_packs.json")
    (tmp_path / "envs").mkdir()
    config = {
        "base_dir": str(tmp_path),
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "models"),
        "snapshots_dir": str(tmp_path / "snapshots"),
        "package_manager": "uv",
    }
    return Bridge(config)


def test_list_addons_with_override_status_reports_false_when_no_override(bridge):
    payload = json.loads(bridge.list_addons_with_override_status())
    assert payload["ok"] is True
    ids = [a["id"] for a in payload["addons"]]
    assert "sage-attention" in ids
    assert all(a["has_override"] is False for a in payload["addons"])


def test_save_addon_override_then_has_override_true(bridge):
    result = json.loads(bridge.save_addon_override(
        "sage-attention",
        json.dumps({"compatible_packs": ["torch-2.9.1-cu130"]}),
    ))
    assert result["ok"] is True
    after = json.loads(bridge.list_addons_with_override_status())
    sage = next(a for a in after["addons"] if a["id"] == "sage-attention")
    assert sage["has_override"] is True


def test_clear_addon_override_by_id(bridge):
    bridge.save_addon_override("sage-attention",
                               json.dumps({"compatible_packs": ["X"]}))
    r = json.loads(bridge.clear_addon_override("sage-attention"))
    assert r["ok"] is True
    after = json.loads(bridge.list_addons_with_override_status())
    sage = next(a for a in after["addons"] if a["id"] == "sage-attention")
    assert sage["has_override"] is False


def test_get_addon_for_edit_returns_three_views(bridge):
    bridge.save_addon_override("sage-attention",
                               json.dumps({"compatible_packs": ["torch-2.9.1-cu130"]}))
    payload = json.loads(bridge.get_addon_for_edit("sage-attention"))
    assert payload["ok"] is True
    assert "shipped" in payload and "override" in payload and "effective" in payload
    assert payload["effective"]["compatible_packs"] == ["torch-2.9.1-cu130"]


def test_get_addon_for_edit_unknown_id_returns_error(bridge):
    payload = json.loads(bridge.get_addon_for_edit("ghost"))
    assert payload["ok"] is False


def test_save_addon_override_invalid_json_returns_error(bridge):
    payload = json.loads(bridge.save_addon_override("sage-attention", "not json"))
    assert payload["ok"] is False
