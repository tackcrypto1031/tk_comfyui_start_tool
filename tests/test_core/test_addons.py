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


# ---------------------------------------------------------------------------
# Task 10: install_addon — git_clone path
# ---------------------------------------------------------------------------

def test_install_git_clone_addon(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path)
    calls = []

    def _fake_clone(url, dest, branch=None, commit=None, progress_callback=None):
        calls.append(("clone", url, dest))
        Path(dest).mkdir(parents=True)
        # Simulate a requirements.txt in the cloned repo
        (Path(dest) / "requirements.txt").write_text("numpy\n")

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(("install", tuple(args)))

    monkeypatch.setattr("src.core.addons.git_ops.clone_repo", _fake_clone)
    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)
    # Editable install goes through venv python -m pip — stub it to record call
    def _fake_editable(args, cwd, env_dir, tools_dir, uv_version,
                       package_manager, progress_callback):
        calls.append(("install", tuple(args)))
    monkeypatch.setattr(
        "src.core.addons._run_editable_via_pkg_ops", _fake_editable,
    )

    install_addon(
        addon_id="sage-attention",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="uv",
    )

    # Expect: clone, install -r requirements.txt, then post_install (pip install -e .)
    assert calls[0][0] == "clone"
    assert calls[0][1] == "https://github.com/thu-ml/SageAttention.git"

    install_calls = [c for c in calls if c[0] == "install"]
    # First install = requirements.txt
    assert install_calls[0][1][0] == "install"
    assert "-r" in install_calls[0][1]
    # Second install = post_install (translated "pip" → "install -e .")
    assert install_calls[1][1] == ("install", "-e", ".")


def test_install_py_skipped_when_post_install_cmd_present(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path)
    called_install_py = {"ran": False}

    def _fake_clone(url, dest, **kw):
        Path(dest).mkdir(parents=True)
        # Add an install.py which would normally be auto-run
        (Path(dest) / "install.py").write_text("raise SystemExit(0)")

    def _fake_install(*a, **kw): pass

    def _fake_run_install_py(*a, **kw):
        called_install_py["ran"] = True

    def _fake_editable(*a, **kw): pass

    monkeypatch.setattr("src.core.addons.git_ops.clone_repo", _fake_clone)
    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)
    monkeypatch.setattr("src.core.addons._run_install_py", _fake_run_install_py)
    monkeypatch.setattr("src.core.addons._run_editable_via_pkg_ops", _fake_editable)

    install_addon(
        addon_id="sage-attention",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
    )
    assert called_install_py["ran"] is False
