from pathlib import Path

import pytest

from src.utils import uv_ops


def test_ensure_uv_reports_already_present(tmp_path, monkeypatch):
    bin_dir = tmp_path / "tools" / "uv"
    bin_dir.mkdir(parents=True)
    (bin_dir / "uv.exe").write_bytes(b"fake")

    called = {"downloaded": False}

    def _download(*a, **kw):
        called["downloaded"] = True

    monkeypatch.setattr(uv_ops, "_download_uv_binary", _download)
    result = uv_ops.ensure_uv(tools_dir=tmp_path / "tools", version="0.9.7")
    assert result.exists()
    assert called["downloaded"] is False


def test_ensure_uv_downloads_when_missing(tmp_path, monkeypatch):
    called = {"download_args": None}

    def _download(dest, version):
        called["download_args"] = (dest, version)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"downloaded")

    monkeypatch.setattr(uv_ops, "_download_uv_binary", _download)
    result = uv_ops.ensure_uv(tools_dir=tmp_path / "tools", version="0.9.7")
    assert result.exists()
    assert called["download_args"][0] == tmp_path / "tools" / "uv" / "uv.exe"
    assert called["download_args"][1] == "0.9.7"
