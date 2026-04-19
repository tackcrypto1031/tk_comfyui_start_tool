import json
from pathlib import Path

import pytest

from src.core.torch_pack import TorchPackManager, Pack


_BASE = {
    "schema_version": 1,
    "last_updated": "2026-04-19",
    "remote_url": "http://example/x.json",
    "recommended_python": "3.12.10",
    "recommended_uv_version": "0.9.7",
    "packs": [
        {"id": "p1", "label": "P1", "torch": "2.9.1", "torchvision": "0.24.1",
         "torchaudio": "2.9.1", "cuda_tag": "cu130", "min_driver": 13.0,
         "recommended": True}
    ],
    "pinned_deps": {"av": "16.0.1"}
}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_from_shipped(tmp_path):
    shipped = tmp_path / "data" / "torch_packs.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=tmp_path / "no.json")
    data = mgr.load()
    assert data["schema_version"] == 1
    assert len(mgr.list_packs()) == 1
    assert mgr.list_packs()[0].id == "p1"


def test_remote_overrides_shipped(tmp_path):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    remote_payload = {**_BASE, "packs": [
        {**_BASE["packs"][0], "id": "p2"}
    ]}
    _write_json(remote, remote_payload)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)
    assert mgr.list_packs()[0].id == "p2"


def test_schema_version_mismatch_ignores_remote(tmp_path):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    _write_json(remote, {**_BASE, "schema_version": 999, "packs": []})
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)
    # falls back to shipped
    assert [p.id for p in mgr.list_packs()] == ["p1"]


def test_find_pack_by_id(tmp_path):
    shipped = tmp_path / "data" / "torch_packs.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=tmp_path / "no.json")
    assert mgr.find("p1").id == "p1"
    assert mgr.find("ghost") is None
