import json
import shutil
from pathlib import Path

import pytest

from src.core.torch_pack import TorchPackManager, switch_pack
from src.models.environment import Environment


def _setup(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy("data/addons.json", data_dir / "addons.json")
    (data_dir / "torch_packs.json").write_text(json.dumps({
        "schema_version": 1, "last_updated": "2026-04-19", "remote_url": "",
        "recommended_python": "3.12.10", "recommended_uv_version": "0.9.7",
        "packs": [
            {"id": "p-new", "label": "New", "torch": "2.9.1",
             "torchvision": "0.24.1", "torchaudio": "2.9.1",
             "cuda_tag": "cu130", "min_driver": 13.0, "recommended": True},
            {"id": "p-mid", "label": "Mid", "torch": "2.8.0",
             "torchvision": "0.23.0", "torchaudio": "2.8.0",
             "cuda_tag": "cu128", "min_driver": 12.8, "recommended": False},
        ],
        "pinned_deps": {"av": "16.0.1"},
    }), encoding="utf-8")
    env_dir = tmp_path / "envs" / "main"
    (env_dir / "ComfyUI" / "custom_nodes").mkdir(parents=True)
    (env_dir / "venv").mkdir()
    env = Environment(
        name="main", created_at="2026-04-19T00:00:00Z",
        path=str(env_dir), torch_pack="p-mid",
    )
    env.save_meta()
    config = {
        "environments_dir": str(tmp_path / "envs"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
        "snapshots_dir": str(tmp_path / "snaps"),
        "max_snapshots": 5,
    }
    return config, env_dir


def test_switch_pack_reinstalls_torch_and_pinned(tmp_path, monkeypatch):
    config, env_dir = _setup(tmp_path)
    calls = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(tuple(args))

    monkeypatch.setattr("src.core.torch_pack.pkg_ops.run_install", _fake_install)
    monkeypatch.setattr(
        "src.core.torch_pack.pkg_ops.freeze",
        lambda **kw: {"torch": "2.9.1+cu130"},
    )
    monkeypatch.setattr(
        "src.core.torch_pack.SnapshotManager.create_snapshot",
        lambda self, name, trigger=None: None,
    )

    result = switch_pack(
        config=config, env_name="main", target_pack_id="p-new",
        confirm_addon_removal=True,
    )
    assert result["ok"] is True
    # Expect: uninstall torch trio, install new torch trio, install pinned
    assert any(c[0] == "uninstall" and "torch" in c for c in calls)
    assert any(c[0] == "install" and "torch==2.9.1" in c for c in calls)
    assert any(c[0] == "install" and "av==16.0.1" in c for c in calls)

    env = Environment.load_meta(str(env_dir))
    assert env.torch_pack == "p-new"


def test_switch_pack_blocks_without_confirmation_when_compiled_addons_present(
    tmp_path, monkeypatch,
):
    config, env_dir = _setup(tmp_path)
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "sage-attention",
        "installed_at": "2026-04-19T00:00:00Z",
        "torch_pack_at_install": "p-mid",
    })
    env.save_meta()
    (env_dir / "ComfyUI" / "custom_nodes" / "sage-attention").mkdir()

    result = switch_pack(
        config=config, env_name="main", target_pack_id="p-new",
        confirm_addon_removal=False,
    )
    assert result["ok"] is False
    assert "addon" in result["error"].lower() or "confirm" in result["error"].lower()
    env = Environment.load_meta(str(env_dir))
    assert env.torch_pack == "p-mid"
    assert any(a["id"] == "sage-attention" for a in env.installed_addons)


def test_switch_pack_removes_compiled_addons_when_confirmed(
    tmp_path, monkeypatch,
):
    config, env_dir = _setup(tmp_path)
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "sage-attention",
        "installed_at": "2026-04-19T00:00:00Z",
        "torch_pack_at_install": "p-mid",
    })
    env.save_meta()
    node_dir = env_dir / "ComfyUI" / "custom_nodes" / "sage-attention"
    node_dir.mkdir()
    (node_dir / "x.py").write_text("x")

    monkeypatch.setattr(
        "src.core.torch_pack.pkg_ops.run_install", lambda **kw: None,
    )
    monkeypatch.setattr(
        "src.core.torch_pack.pkg_ops.freeze",
        lambda **kw: {"torch": "2.9.1+cu130"},
    )
    monkeypatch.setattr(
        "src.core.torch_pack.SnapshotManager.create_snapshot",
        lambda self, name, trigger=None: None,
    )
    result = switch_pack(
        config=config, env_name="main", target_pack_id="p-new",
        confirm_addon_removal=True,
    )
    assert result["ok"] is True
    assert result["removed_addons"] == ["sage-attention"]
    assert not node_dir.exists()


def test_switch_pack_noop_when_target_equals_current(tmp_path, monkeypatch):
    config, env_dir = _setup(tmp_path)
    result = switch_pack(
        config=config, env_name="main", target_pack_id="p-mid",
        confirm_addon_removal=True,
    )
    assert result["ok"] is True
    assert result["noop"] is True
