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


def test_run_uv_pip_builds_correct_command(tmp_path, monkeypatch):
    uv_bin = tmp_path / "tools" / "uv" / "uv.exe"
    uv_bin.parent.mkdir(parents=True)
    uv_bin.write_bytes(b"fake")
    venv_py = tmp_path / "venv" / "Scripts" / "python.exe"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_bytes(b"fake")

    captured = {}

    class _FakeProc:
        returncode = 0
        stdout = iter([b"ok\n"])
        def wait(self): return 0

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc()

    monkeypatch.setattr("src.utils.uv_ops.subprocess.Popen", _fake_popen)
    uv_ops.run_uv_pip(
        uv_binary=uv_bin,
        venv_python=str(venv_py),
        args=["install", "torch==2.9.1"],
    )
    assert captured["cmd"][0] == str(uv_bin)
    assert captured["cmd"][1:3] == ["pip", "install"]
    assert "--python" in captured["cmd"]
    idx = captured["cmd"].index("--python")
    assert captured["cmd"][idx + 1] == str(venv_py)
    assert "torch==2.9.1" in captured["cmd"]


def test_run_uv_pip_raises_on_nonzero(tmp_path, monkeypatch):
    uv_bin = tmp_path / "tools" / "uv" / "uv.exe"
    uv_bin.parent.mkdir(parents=True)
    uv_bin.write_bytes(b"fake")

    class _FakeProc:
        returncode = 2
        stdout = iter([b"error: boom\n"])
        def wait(self): return 2

    monkeypatch.setattr(
        "src.utils.uv_ops.subprocess.Popen",
        lambda cmd, **kw: _FakeProc(),
    )
    with pytest.raises(RuntimeError, match="uv pip failed"):
        uv_ops.run_uv_pip(
            uv_binary=uv_bin, venv_python="py", args=["install", "x"]
        )
