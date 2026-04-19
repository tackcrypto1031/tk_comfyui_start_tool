from pathlib import Path

import pytest

from src.core.env_manager import EnvManager


def test_install_torch_pack_invokes_pkg_ops(tmp_path, monkeypatch):
    config = {
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "models"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
    }
    mgr = EnvManager(config)
    venv_path = tmp_path / "envs" / "e1" / "venv"
    venv_path.mkdir(parents=True)

    recorded = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        recorded.append(args)

    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install", _fake_install,
    )
    mgr._install_torch_pack(
        venv_path=str(venv_path),
        torch="2.9.1",
        torchvision="0.24.1",
        torchaudio="2.9.1",
        cuda_tag="cu130",
        progress_callback=None,
    )
    # Expect one install call with three pinned packages + --index-url
    assert len(recorded) == 1
    args = recorded[0]
    assert args[0] == "install"
    assert "torch==2.9.1" in args
    assert "torchvision==0.24.1" in args
    assert "torchaudio==2.9.1" in args
    assert "--index-url" in args
    idx = args.index("--index-url")
    assert args[idx + 1] == "https://download.pytorch.org/whl/cu130"


def test_install_pinned_deps_installs_all(tmp_path, monkeypatch):
    config = {
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "models"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
    }
    mgr = EnvManager(config)
    recorded = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        recorded.append(args)

    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install", _fake_install,
    )
    pinned = {"av": "16.0.1", "transformers": "4.57.6"}
    mgr._install_pinned_deps("venv", pinned, None)

    assert len(recorded) == 1
    args = recorded[0]
    assert args[0] == "install"
    assert "av==16.0.1" in args
    assert "transformers==4.57.6" in args


def test_install_pinned_deps_empty_is_noop(tmp_path, monkeypatch):
    config = {"environments_dir": str(tmp_path), "models_dir": str(tmp_path),
              "base_dir": str(tmp_path), "package_manager": "uv"}
    mgr = EnvManager(config)
    called = {"ran": False}
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install",
        lambda *a, **k: called.update(ran=True),
    )
    mgr._install_pinned_deps("venv", {}, None)
    assert called["ran"] is False
