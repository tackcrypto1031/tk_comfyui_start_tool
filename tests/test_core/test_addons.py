from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.addons import (
    IncompatiblePackError,
    install_addon,
    uninstall_addon,
)
from src.core.addon_registry import AddonRegistry, Addon
from src.models.environment import Environment


def _seed_shipped(base_dir: Path) -> None:
    """Write a minimal data/addons.json matching the real shipped file."""
    shipped = base_dir / "data" / "addons.json"
    shipped.parent.mkdir(parents=True, exist_ok=True)
    shipped.write_text(Path("data/addons.json").read_text(encoding="utf-8"), encoding="utf-8")


def _config(tmp_path: Path) -> dict:
    _seed_shipped(tmp_path)
    return {"base_dir": str(tmp_path), "environments_dir": str(tmp_path / "envs")}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_env(tmp_path, torch_pack="torch-2.9.1-cu130"):
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
# Install — pip kind (wheel primary, pip_spec fallback)
# ---------------------------------------------------------------------------

def test_install_pip_addon_uses_wheel_for_current_pack(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path, torch_pack="torch-2.8.0-cu128")
    captured = {"args": None}

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        captured["args"] = args

    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    result = install_addon(
        _config(tmp_path),
        addon_id="sage-attention",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="uv",
    )
    assert result == {"id": "sage-attention", "kind": "pip"}
    # Installed via the pack-matched wheel URL.
    assert captured["args"][0] == "install"
    assert "cu128torch2.8.0" in captured["args"][1]

    env = Environment.load_meta(str(env_dir))
    assert any(a["id"] == "sage-attention" for a in env.installed_addons)
    assert env.installed_addons[0]["torch_pack_at_install"] == "torch-2.8.0-cu128"


def test_install_pip_addon_falls_back_to_pip_spec(tmp_path, monkeypatch):
    """When wheels_by_pack lacks the current pack but pip_spec exists,
    installer should fall back to PyPI spec."""
    env_dir = _make_env(tmp_path, torch_pack="torch-2.9.1-cu130")
    captured = {"args": None}

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        captured["args"] = args

    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    # Patch the registry to return a stub addon with no wheel for current pack
    stub = Addon(
        id="insightface", label="InsightFace", description="face",
        kind="pip",
        compatible_packs=("torch-2.9.1-cu130",),
        wheels_by_pack={},  # no wheel for current pack
        pip_spec="insightface==0.7.3",
        pip_project_name="insightface",
    )

    class _StubRegistry:
        def find(self, addon_id):
            return stub if addon_id == "insightface" else None

    monkeypatch.setattr("src.core.addons._registry", lambda config: _StubRegistry())

    install_addon(
        _config(tmp_path),
        addon_id="insightface",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
    )
    assert captured["args"] == ["install", "insightface==0.7.3"]


# ---------------------------------------------------------------------------
# Install — custom_node kind (git clone + post_install_cmd)
# ---------------------------------------------------------------------------

def test_install_custom_node_addon(tmp_path, monkeypatch):
    # Trellis only works on cu128 pack.
    env_dir = _make_env(tmp_path, torch_pack="torch-2.8.0-cu128")
    calls = []

    def _fake_clone(url, dest, branch=None, commit=None, progress_callback=None):
        calls.append(("clone", url, dest, branch))
        Path(dest).mkdir(parents=True)
        (Path(dest) / "requirements.txt").write_text("numpy\n")

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(("install", tuple(args)))

    monkeypatch.setattr("src.core.addons.git_ops.clone_repo", _fake_clone)
    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    install_addon(
        _config(tmp_path),
        addon_id="trellis2",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
    )

    assert calls[0][0] == "clone"
    assert calls[0][1] == "https://github.com/microsoft/TRELLIS.2.git"
    # Cloned at the pinned source_ref, not floating master.
    assert calls[0][3] == "main"

    install_calls = [c for c in calls if c[0] == "install"]
    # First install = requirements.txt from the cloned repo.
    assert "-r" in install_calls[0][1]
    # Second install = translated post_install_cmd.
    assert install_calls[1][1][0] == "install"
    assert "-r" in install_calls[1][1]  # "pip install -r requirements.txt"


# ---------------------------------------------------------------------------
# Compatibility gating
# ---------------------------------------------------------------------------

def test_incompatible_pack_raises(tmp_path, monkeypatch):
    # Trellis on cu130 env should be rejected pre-flight.
    env_dir = _make_env(tmp_path, torch_pack="torch-2.9.1-cu130")
    monkeypatch.setattr(
        "src.core.addons.pkg_ops.run_install",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not install")),
    )

    with pytest.raises(IncompatiblePackError):
        install_addon(
            _config(tmp_path),
            addon_id="trellis2",
            env_dir=env_dir,
            tools_dir=tmp_path / "tools",
            uv_version="0.9.7",
        )

    env = Environment.load_meta(str(env_dir))
    assert env.installed_addons == []  # not recorded on failure


def test_unknown_addon_raises(tmp_path):
    env_dir = _make_env(tmp_path)
    with pytest.raises(ValueError):
        install_addon(
            _config(tmp_path),
            addon_id="ghost",
            env_dir=env_dir,
            tools_dir=tmp_path / "tools",
            uv_version="0.9.7",
        )


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

def test_uninstall_pip_addon(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path)
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "insightface",
        "installed_at": "2026-04-19T00:00:00Z",
        "torch_pack_at_install": "torch-2.9.1-cu130",
    })
    env.save_meta()

    calls = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(tuple(args))

    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    uninstall_addon(
        _config(tmp_path),
        addon_id="insightface",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
    )
    # pip uninstall uses pip_project_name (not pip_spec with version pin).
    assert calls == [("uninstall", "-y", "insightface")]
    env = Environment.load_meta(str(env_dir))
    assert env.installed_addons == []


def test_uninstall_custom_node_addon(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path, torch_pack="torch-2.8.0-cu128")
    node_dir = env_dir / "ComfyUI" / "custom_nodes" / "trellis2"
    node_dir.mkdir(parents=True)
    (node_dir / "junk.py").write_text("x")
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "trellis2",
        "installed_at": "2026-04-19T00:00:00Z",
        "torch_pack_at_install": "torch-2.8.0-cu128",
    })
    env.save_meta()

    calls = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(args)

    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    uninstall_addon(
        _config(tmp_path),
        addon_id="trellis2",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
    )
    assert not node_dir.exists()
    # custom_node uninstall is tree-removal only, no pip call.
    assert calls == []
    env = Environment.load_meta(str(env_dir))
    assert env.installed_addons == []


def test_install_custom_node_addon_installs_wheel_before_clone(tmp_path, monkeypatch):
    """Nunchaku-style: kind='custom_node' with wheels_by_pack must pip-install
    the pack-matched wheel BEFORE the git clone, so the node repo's
    __init__.py can import the runtime at ComfyUI load time.
    """
    env_dir = _make_env(tmp_path, torch_pack="torch-2.9.1-cu130")
    calls = []

    def _fake_clone(url, dest, branch=None, commit=None, progress_callback=None):
        calls.append(("clone", url, dest, branch))
        Path(dest).mkdir(parents=True)
        (Path(dest) / "requirements.txt").write_text("diffusers\n")

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(("install", tuple(args)))

    monkeypatch.setattr("src.core.addons.git_ops.clone_repo", _fake_clone)
    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    install_addon(
        _config(tmp_path),
        addon_id="nunchaku",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
    )

    # Ordering contract: wheel install MUST come before clone.
    assert calls[0][0] == "install"
    assert "nunchaku-1.2.1+cu13.0torch2.9" in calls[0][1][1]
    assert calls[1][0] == "clone"
    assert calls[1][1] == "https://github.com/nunchaku-ai/ComfyUI-nunchaku.git"
    assert calls[1][3] == "v1.2.1"

    # Then requirements.txt and the post_install `pip install -r requirements.txt`.
    later_installs = [c for c in calls[2:] if c[0] == "install"]
    assert any("-r" in c[1] for c in later_installs)

    env = Environment.load_meta(str(env_dir))
    assert any(a["id"] == "nunchaku" for a in env.installed_addons)


def test_uninstall_custom_node_with_pip_project_name_also_pip_uninstalls(
    tmp_path, monkeypatch,
):
    """Nunchaku-style uninstall must remove BOTH the node dir and the pip
    runtime (pip_project_name)."""
    env_dir = _make_env(tmp_path, torch_pack="torch-2.9.1-cu130")
    node_dir = env_dir / "ComfyUI" / "custom_nodes" / "nunchaku"
    node_dir.mkdir(parents=True)
    (node_dir / "__init__.py").write_text("x")
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "nunchaku",
        "installed_at": "2026-04-22T00:00:00Z",
        "torch_pack_at_install": "torch-2.9.1-cu130",
    })
    env.save_meta()

    calls = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(tuple(args))

    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    uninstall_addon(
        _config(tmp_path),
        addon_id="nunchaku",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
    )

    assert not node_dir.exists()
    assert calls == [("uninstall", "-y", "nunchaku")]
    env = Environment.load_meta(str(env_dir))
    assert env.installed_addons == []


def test_uninstall_orphan_addon_generic_cleanup(tmp_path, monkeypatch):
    """Uninstalling an id not in registry removes the dir + meta entry."""
    env_dir = _make_env(tmp_path)
    node_dir = env_dir / "ComfyUI" / "custom_nodes" / "orphan-addon"
    node_dir.mkdir(parents=True)
    (node_dir / "file.py").write_text("x")
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "orphan-addon",
        "installed_at": "2026-04-19T00:00:00Z",
        "torch_pack_at_install": None,
    })
    env.save_meta()

    calls = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(args)

    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    uninstall_addon(
        _config(tmp_path),
        addon_id="orphan-addon",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
    )
    assert not node_dir.exists()
    assert calls == []  # no pip call for orphan
    env = Environment.load_meta(str(env_dir))
    assert env.installed_addons == []
