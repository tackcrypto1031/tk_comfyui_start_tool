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


_MULTI = {
    **_BASE,
    "packs": [
        {"id": "p-new", "label": "New", "torch": "2.9.1", "torchvision": "0.24.1",
         "torchaudio": "2.9.1", "cuda_tag": "cu130", "min_driver": 13.0,
         "recommended": True},
        {"id": "p-mid", "label": "Mid", "torch": "2.8.0", "torchvision": "0.23.0",
         "torchaudio": "2.8.0", "cuda_tag": "cu128", "min_driver": 12.8,
         "recommended": False},
        {"id": "p-old", "label": "Old", "torch": "2.7.1", "torchvision": "0.22.1",
         "torchaudio": "2.7.1", "cuda_tag": "cu128", "min_driver": 12.8,
         "recommended": False},
    ],
}


def _mgr_with(tmp_path, data):
    shipped = tmp_path / "data" / "torch_packs.json"
    _write_json(shipped, data)
    return TorchPackManager(shipped_path=shipped, remote_path=tmp_path / "no.json")


def test_select_no_gpu(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    assert mgr.select_pack_for_gpu({"has_gpu": False}) is None


def test_select_driver_too_old(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    assert mgr.select_pack_for_gpu(
        {"has_gpu": True, "cuda_driver_version": "11.8"}
    ) is None


def test_select_driver_matches_fallback(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    # Driver 12.8: only p-mid qualifies (p-new needs 13.0)
    assert mgr.select_pack_for_gpu(
        {"has_gpu": True, "cuda_driver_version": "12.8"}
    ).id == "p-mid"


def test_select_driver_matches_recommended(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    # Driver 13.0: p-new is recommended + meets min_driver
    assert mgr.select_pack_for_gpu(
        {"has_gpu": True, "cuda_driver_version": "13.0"}
    ).id == "p-new"


def test_select_malformed_driver_version(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    assert mgr.select_pack_for_gpu(
        {"has_gpu": True, "cuda_driver_version": "not-a-number"}
    ) is None


def test_select_missing_driver_field(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    assert mgr.select_pack_for_gpu({"has_gpu": True}) is None


def test_refresh_writes_remote_file(tmp_path, monkeypatch):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)

    new_payload = {**_BASE, "last_updated": "2026-05-01"}

    class _FakeResp:
        status_code = 200
        def json(self): return new_payload
        def raise_for_status(self): pass

    def _fake_get(url, timeout):
        assert "x.json" in url
        return _FakeResp()

    monkeypatch.setattr("src.core.torch_pack.requests.get", _fake_get)
    result = mgr.refresh_remote()
    assert result["ok"] is True
    assert remote.exists()
    assert json.loads(remote.read_text(encoding="utf-8"))["last_updated"] == "2026-05-01"


def test_refresh_network_failure_is_non_fatal(tmp_path, monkeypatch):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)

    def _boom(url, timeout):
        raise ConnectionError("offline")

    monkeypatch.setattr("src.core.torch_pack.requests.get", _boom)
    result = mgr.refresh_remote()
    assert result["ok"] is False
    assert "offline" in result["error"]
    assert not remote.exists()


def test_refresh_schema_mismatch_does_not_write(tmp_path, monkeypatch):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)

    class _FakeResp:
        status_code = 200
        def json(self): return {"schema_version": 999}
        def raise_for_status(self): pass

    monkeypatch.setattr("src.core.torch_pack.requests.get", lambda url, timeout: _FakeResp())
    result = mgr.refresh_remote()
    assert result["ok"] is False
    assert "schema" in result["error"].lower()
    assert not remote.exists()
