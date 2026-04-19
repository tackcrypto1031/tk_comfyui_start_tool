from pathlib import Path

import pytest

from src.utils import pkg_ops


def test_dispatch_uv_mode_calls_uv_ops(monkeypatch, tmp_path):
    called = {"uv": False, "pip": False}

    def _uv(uv_binary, venv_python, args, progress_callback=None):
        called["uv"] = True

    def _pip(venv_path, args, progress_callback=None):
        called["pip"] = True

    monkeypatch.setattr("src.utils.pkg_ops.uv_ops.run_uv_pip", _uv)
    monkeypatch.setattr("src.utils.pkg_ops.pip_ops.run_pip_with_progress", _pip)
    monkeypatch.setattr(
        "src.utils.pkg_ops.uv_ops.ensure_uv",
        lambda tools_dir, version: tools_dir / "uv" / "uv.exe",
    )
    monkeypatch.setattr(
        "src.utils.pkg_ops.pip_ops.get_venv_python", lambda p: "fakepy",
    )
    pkg_ops.run_install(
        venv_path=str(tmp_path / "venv"),
        args=["install", "torch"],
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="uv",
    )
    assert called["uv"] and not called["pip"]


def test_dispatch_pip_mode_calls_pip_ops(monkeypatch, tmp_path):
    called = {"uv": False, "pip": False}

    def _pip(venv_path, args, progress_callback=None):
        called["pip"] = True

    monkeypatch.setattr(
        "src.utils.pkg_ops.pip_ops.run_pip_with_progress", _pip,
    )
    pkg_ops.run_install(
        venv_path=str(tmp_path / "venv"),
        args=["install", "torch"],
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="pip",
    )
    assert called["pip"] and not called["uv"]
