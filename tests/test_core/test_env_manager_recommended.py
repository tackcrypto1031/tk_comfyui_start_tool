import json
from pathlib import Path

import pytest

from src.core.env_manager import EnvManager
from src.models.environment import Environment


@pytest.fixture
def config(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "torch_packs.json").write_text(json.dumps({
        "schema_version": 1,
        "last_updated": "2026-04-19",
        "remote_url": "",
        "recommended_python": "3.12.10",
        "recommended_uv_version": "0.9.7",
        "packs": [
            {"id": "p-new", "label": "New", "torch": "2.9.1",
             "torchvision": "0.24.1", "torchaudio": "2.9.1",
             "cuda_tag": "cu130", "min_driver": 13.0, "recommended": True},
        ],
        "pinned_deps": {"av": "16.0.1"},
    }), encoding="utf-8")
    return {
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "models"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
        "shared_model_mode": "default",
        "model_subdirs": ["checkpoints"],
        "comfyui_repo_url": "http://fake/comfy.git",
    }


def test_create_recommended_happy_path(tmp_path, config, monkeypatch):
    mgr = EnvManager(config)

    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._detect_gpu",
        lambda self: {"has_gpu": True, "cuda_driver_version": "13.0"},
    )
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._latest_comfyui_tag",
        lambda self: "v9.9.9",
    )

    def _fake_venv(path, python_executable=""):
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "Scripts").mkdir(exist_ok=True)
        (Path(path) / "Scripts" / "python.exe").write_bytes(b"fake")

    monkeypatch.setattr("src.core.env_manager.pip_ops.create_venv", _fake_venv)

    def _fake_clone(url, dest, branch=None, commit=None, progress_callback=None):
        Path(dest).mkdir(parents=True, exist_ok=True)
        (Path(dest) / "requirements.txt").write_text("numpy\n")

    monkeypatch.setattr("src.core.env_manager.git_ops.clone_repo", _fake_clone)
    monkeypatch.setattr(
        "src.core.env_manager.git_ops.get_current_commit",
        lambda p: "deadbeef",
    )
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install",
        lambda **kw: None,
    )
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.freeze",
        lambda **kw: {
            "torch": "2.9.1+cu130", "numpy": "2.0", "pillow": "10.0",
            "pyyaml": "6.0", "aiohttp": "3.9", "sqlalchemy": "2.0",
        },
    )
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._ensure_python",
        lambda self, version: str(tmp_path / "tools" / "python_3.12.10" / "python.exe"),
    )
    uv_bin = tmp_path / "tools" / "uv" / "uv.exe"
    uv_bin.parent.mkdir(parents=True)
    uv_bin.write_bytes(b"fake")

    env = mgr.create_recommended(name="r1", selected_addon_ids=[])

    assert env.torch_pack == "p-new"
    assert env.pytorch_version == "2.9.1+cu130"
    assert env.cuda_tag == "cu130"
    assert env.installed_addons == []
    env_dir = Path(config["environments_dir"]) / "r1"
    persisted = Environment.load_meta(str(env_dir))
    assert persisted.torch_pack == "p-new"


def test_create_recommended_blocks_without_gpu(tmp_path, config, monkeypatch):
    mgr = EnvManager(config)
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._detect_gpu",
        lambda self: {"has_gpu": False},
    )
    with pytest.raises(RuntimeError, match="推薦模式|no GPU"):
        mgr.create_recommended(name="nope", selected_addon_ids=[])
    assert not (Path(config["environments_dir"]) / "nope").exists()


def test_create_recommended_addon_failure_does_not_delete_env(
    tmp_path, config, monkeypatch,
):
    mgr = EnvManager(config)
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._detect_gpu",
        lambda self: {"has_gpu": True, "cuda_driver_version": "13.0"},
    )
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._latest_comfyui_tag",
        lambda self: "v9.9.9",
    )
    monkeypatch.setattr(
        "src.core.env_manager.pip_ops.create_venv",
        lambda p, python_executable="": (Path(p) / "Scripts").mkdir(parents=True, exist_ok=True),
    )
    monkeypatch.setattr(
        "src.core.env_manager.git_ops.clone_repo",
        lambda url, dest, **kw: Path(dest).mkdir(parents=True, exist_ok=True),
    )
    monkeypatch.setattr(
        "src.core.env_manager.git_ops.get_current_commit", lambda p: "beef",
    )
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install", lambda **kw: None,
    )
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.freeze",
        lambda **kw: {"torch": "2.9.1", "numpy": "2", "pillow": "10",
                      "pyyaml": "6", "aiohttp": "3"},
    )
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._ensure_python",
        lambda self, version: "py",
    )
    def _boom(*args, **kw):
        raise RuntimeError("compile failed")
    monkeypatch.setattr("src.core.env_manager.addons.install_addon", _boom)

    env = mgr.create_recommended(
        name="r2", selected_addon_ids=["sage-attention"],
    )
    assert (Path(config["environments_dir"]) / "r2").exists()
    assert env.installed_addons == []
    assert getattr(env, "failed_addons", None) == [
        {"id": "sage-attention", "error": "compile failed"}
    ]
