"""Tests for Bridge torch_pack / addons / recommended-env methods."""
import json

import pytest

# Bridge needs Qt; skip if PySide6 not installed in test env
pytest.importorskip("PySide6")

from src.gui.bridge import Bridge


@pytest.fixture
def bridge_config(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "torch_packs.json").write_text(json.dumps({
        "schema_version": 1, "last_updated": "2026-04-19", "remote_url": "",
        "recommended_python": "3.12.10", "recommended_uv_version": "0.9.7",
        "packs": [
            {"id": "p-new", "label": "New", "torch": "2.9.1",
             "torchvision": "0.24.1", "torchaudio": "2.9.1",
             "cuda_tag": "cu130", "min_driver": 13.0, "recommended": True},
        ],
        "pinned_deps": {},
    }), encoding="utf-8")
    (data_dir / "addons.json").write_text(json.dumps({
        "schema_version": 1, "last_updated": "2026-04-20", "remote_url": "",
        "addons": [
            {
                "id": "sage-attention",
                "label": "SageAttention v2.2.0",
                "description": "Attention acceleration",
                "kind": "pip",
                "compatible_packs": ["torch-2.9.1-cu130"],
                "wheels_by_pack": {
                    "torch-2.9.1-cu130": "https://example.com/sage.whl"
                },
                "install_requires": [],
            },
        ],
    }), encoding="utf-8")
    return {
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "models"),
        "snapshots_dir": str(tmp_path / "snapshots"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
    }


def test_list_torch_packs_returns_shipped(bridge_config):
    b = Bridge(bridge_config)
    result = json.loads(b.list_torch_packs())
    assert result["ok"] is True
    assert result["packs"][0]["id"] == "p-new"


def test_list_addons_returns_curated_list(bridge_config):
    b = Bridge(bridge_config)
    result = json.loads(b.list_addons())
    assert result["ok"] is True
    ids = {a["id"] for a in result["addons"]}
    assert "sage-attention" in ids


def _inline_async_bridge(b):
    """Run AsyncWorker functions inline so detect_gpu_for_recommended can be
    driven synchronously from tests (mirrors test_bridge_open_browser)."""

    def _inline_run_async(request_id, fn, *args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            b._result_queue[request_id] = json.dumps(
                {"success": True, "data": result}, default=str, ensure_ascii=False
            )
        except Exception as e:  # pragma: no cover
            b._result_queue[request_id] = json.dumps({"error": str(e)})

    b._run_async = _inline_run_async
    return b


def _call_detect_gpu(bridge, request_id="test-req"):
    bridge.detect_gpu_for_recommended(request_id)
    raw = bridge._result_queue.get(request_id)
    assert raw is not None, "async worker did not produce a result"
    outer = json.loads(raw)
    return outer.get("data", outer)


def test_detect_gpu_for_recommended_happy(bridge_config, monkeypatch):
    b = _inline_async_bridge(Bridge(bridge_config))
    monkeypatch.setattr(
        "src.core.version_manager.VersionManager.detect_gpu",
        lambda self: {"has_gpu": True, "cuda_driver_version": "13.0"},
    )
    result = _call_detect_gpu(b)
    assert result["ok"] is True
    assert result["has_gpu"] is True
    assert result["recommended_pack_id"] == "p-new"
    assert result["recommended_pack_label"] == "New"


def test_detect_gpu_for_recommended_no_gpu(bridge_config, monkeypatch):
    b = _inline_async_bridge(Bridge(bridge_config))
    monkeypatch.setattr(
        "src.core.version_manager.VersionManager.detect_gpu",
        lambda self: {"has_gpu": False},
    )
    result = _call_detect_gpu(b)
    assert result["ok"] is True
    assert result["has_gpu"] is False
    assert result["recommended_pack_id"] is None
