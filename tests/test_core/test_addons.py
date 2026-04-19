from datetime import datetime, timezone
from pathlib import Path

from src.core.addons import ADDONS, find_addon, Addon, install_addon
from src.models.environment import Environment


def test_registry_has_expected_ids():
    ids = {a.id for a in ADDONS}
    assert ids == {
        "sage-attention", "flash-attention", "insightface",
        "nunchaku", "trellis2",
    }


def test_find_existing():
    addon = find_addon("sage-attention")
    assert addon is not None
    assert addon.requires_compile is True


def test_find_missing():
    assert find_addon("ghost") is None


def test_pip_package_addon_has_no_repo():
    insight = find_addon("insightface")
    assert insight.install_method == "pip_package"
    assert insight.repo is None
    assert insight.pip_package == "insightface"


def test_git_clone_addon_has_repo_and_post_install():
    sage = find_addon("sage-attention")
    assert sage.install_method == "git_clone"
    assert sage.repo
    assert sage.post_install_cmd == ["pip", "install", "-e", "."]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_env(tmp_path, torch_pack="p1"):
    env_dir = tmp_path / "main"
    (env_dir / "ComfyUI" / "custom_nodes").mkdir(parents=True)
    (env_dir / "venv").mkdir()
    env = Environment(
        name="main",
        created_at=datetime.now(timezone.utc).isoformat(),
        path=str(env_dir),
        torch_pack=torch_pack,
    )
    env.save_meta()
    return env_dir


# ---------------------------------------------------------------------------
# Task 9: install_addon — pip_package path
# ---------------------------------------------------------------------------

def test_install_pip_package_addon(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path)
    captured = {"args": None}

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        captured["args"] = args

    monkeypatch.setattr(
        "src.core.addons.pkg_ops.run_install", _fake_install,
    )

    result = install_addon(
        addon_id="insightface",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="uv",
    )
    assert captured["args"] == ["install", "insightface"]
    assert result["id"] == "insightface"

    env = Environment.load_meta(str(env_dir))
    assert any(a["id"] == "insightface" for a in env.installed_addons)
    assert env.installed_addons[0]["torch_pack_at_install"] == "p1"
