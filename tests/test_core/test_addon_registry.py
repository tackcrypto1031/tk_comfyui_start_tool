# tests/test_core/test_addon_registry.py
import json
from pathlib import Path

from src.core.addon_registry import AddonRegistry, Addon


SHIPPED = {
    "schema_version": 1,
    "last_updated": "2026-04-20",
    "remote_url": "https://example.com/addons.json",
    "addons": [
        {
            "id": "sage",
            "label": "Sage",
            "description": "attn",
            "kind": "pip",
            "compatible_packs": ["torch-2.8.0-cu128"],
            "wheels_by_pack": {"torch-2.8.0-cu128": "https://w/sage.whl"},
            "pip_spec": None,
            "pip_project_name": "sageattention",
            "source_repo": None,
            "source_ref": None,
            "source_post_install": None,
            "requires_compile": False,
            "pack_pinned": True,
            "risk_note": None,
        }
    ],
}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_load_shipped_only_returns_addons(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    remote = tmp_path / "tools" / "addons_remote.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)

    reg = AddonRegistry(shipped_path=shipped, remote_path=remote, override_path=override)
    addons = reg.list_addons()

    assert len(addons) == 1
    a = addons[0]
    assert isinstance(a, Addon)
    assert a.id == "sage"
    assert a.kind == "pip"
    assert a.compatible_packs == ("torch-2.8.0-cu128",)
    assert a.wheels_by_pack == {"torch-2.8.0-cu128": "https://w/sage.whl"}
    assert a.pack_pinned is True


# Task 2b: find() + unknown id -> None

def test_find_returns_addon_for_known_id(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    _write(shipped, SHIPPED)
    reg = AddonRegistry(shipped, tmp_path / "r.json", tmp_path / "o.json")

    assert reg.find("sage").id == "sage"


def test_find_returns_none_for_unknown_id(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    _write(shipped, SHIPPED)
    reg = AddonRegistry(shipped, tmp_path / "r.json", tmp_path / "o.json")

    assert reg.find("ghost") is None


# Task 2c: Remote file overrides shipped (schema-gated)

def test_remote_overrides_shipped_when_schema_matches(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    remote = tmp_path / "tools" / "addons_remote.json"
    _write(shipped, SHIPPED)
    remote_data = json.loads(json.dumps(SHIPPED))  # deep copy
    remote_data["addons"][0]["label"] = "Sage (remote)"
    _write(remote, remote_data)

    reg = AddonRegistry(shipped, remote, tmp_path / "o.json")

    assert reg.find("sage").label == "Sage (remote)"


def test_remote_schema_mismatch_falls_back_to_shipped(tmp_path, caplog):
    shipped = tmp_path / "data" / "addons.json"
    remote = tmp_path / "tools" / "addons_remote.json"
    _write(shipped, SHIPPED)
    bad = {"schema_version": 99, "addons": [
        {"id": "ghost", "label": "x", "description": "y", "kind": "pip",
         "compatible_packs": [], "pack_pinned": False}
    ]}
    _write(remote, bad)

    reg = AddonRegistry(shipped, remote, tmp_path / "o.json")

    assert reg.find("ghost") is None
    assert reg.find("sage") is not None


# Task 2d: Override file merges partial fields

def test_override_replaces_compatible_packs_entirely(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)
    _write(override, {
        "schema_version": 1,
        "overrides": {
            "sage": {"compatible_packs": ["torch-2.9.1-cu130", "torch-2.8.0-cu128"]}
        },
    })

    reg = AddonRegistry(shipped, tmp_path / "r.json", override)
    sage = reg.find("sage")

    assert sage.compatible_packs == ("torch-2.9.1-cu130", "torch-2.8.0-cu128")
    # Untouched field preserved from shipped
    assert sage.pip_project_name == "sageattention"


def test_override_wheels_by_pack_shallow_merges_dict(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)
    _write(override, {
        "schema_version": 1,
        "overrides": {
            "sage": {"wheels_by_pack": {"torch-2.9.1-cu130": "https://mirror/sage.whl"}}
        },
    })

    reg = AddonRegistry(shipped, tmp_path / "r.json", override)
    sage = reg.find("sage")

    # New key added from override, existing cu128 key preserved
    assert sage.wheels_by_pack == {
        "torch-2.8.0-cu128": "https://w/sage.whl",
        "torch-2.9.1-cu130": "https://mirror/sage.whl",
    }


def test_override_absent_id_does_not_affect_others(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)
    _write(override, {"schema_version": 1, "overrides": {}})

    reg = AddonRegistry(shipped, tmp_path / "r.json", override)
    assert reg.find("sage").compatible_packs == ("torch-2.8.0-cu128",)


# Task 2e: save_override + clear_override + has_override + cache invalidation

def test_save_override_writes_and_invalidates_cache(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)
    reg = AddonRegistry(shipped, tmp_path / "r.json", override)

    reg.list_addons()  # populate cache
    reg.save_override("sage", {"compatible_packs": ["torch-2.9.1-cu130"]})

    assert override.exists()
    data = json.loads(override.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["overrides"]["sage"]["compatible_packs"] == ["torch-2.9.1-cu130"]

    # cache invalidated — new read reflects override
    assert reg.find("sage").compatible_packs == ("torch-2.9.1-cu130",)


def test_save_override_replaces_existing_entry(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)
    _write(override, {"schema_version": 1, "overrides": {"sage": {"compatible_packs": ["X"]}}})
    reg = AddonRegistry(shipped, tmp_path / "r.json", override)

    reg.save_override("sage", {"compatible_packs": ["torch-2.8.0-cu128"]})

    data = json.loads(override.read_text(encoding="utf-8"))
    assert data["overrides"]["sage"]["compatible_packs"] == ["torch-2.8.0-cu128"]


def test_clear_override_single_id(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)
    _write(override, {"schema_version": 1, "overrides": {
        "sage": {"compatible_packs": ["X"]},
        "other": {"compatible_packs": ["Y"]},
    }})
    reg = AddonRegistry(shipped, tmp_path / "r.json", override)

    reg.clear_override("sage")

    data = json.loads(override.read_text(encoding="utf-8"))
    assert "sage" not in data["overrides"]
    assert "other" in data["overrides"]


def test_clear_override_all_wipes_file_contents(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)
    _write(override, {"schema_version": 1, "overrides": {"sage": {"compatible_packs": ["X"]}}})
    reg = AddonRegistry(shipped, tmp_path / "r.json", override)

    reg.clear_override(None)

    data = json.loads(override.read_text(encoding="utf-8"))
    assert data["overrides"] == {}


def test_has_override_true_only_when_id_present(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)
    _write(override, {"schema_version": 1, "overrides": {"sage": {"compatible_packs": ["X"]}}})
    reg = AddonRegistry(shipped, tmp_path / "r.json", override)

    assert reg.has_override("sage") is True
    assert reg.has_override("other") is False


# Task 2f: get_shipped_and_override + get_remote_url + refresh_remote

def test_get_shipped_and_override_returns_three_views(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    override = tmp_path / "tools" / "addons_override.json"
    _write(shipped, SHIPPED)
    _write(override, {"schema_version": 1, "overrides": {"sage": {
        "compatible_packs": ["torch-2.9.1-cu130"]
    }}})
    reg = AddonRegistry(shipped, tmp_path / "r.json", override)

    view = reg.get_shipped_and_override("sage")

    assert view["shipped"]["compatible_packs"] == ["torch-2.8.0-cu128"]
    assert view["override"] == {"compatible_packs": ["torch-2.9.1-cu130"]}
    assert view["effective"]["compatible_packs"] == ["torch-2.9.1-cu130"]
    # Untouched fields pulled from shipped
    assert view["effective"]["pip_project_name"] == "sageattention"


def test_get_shipped_and_override_returns_none_for_unknown_id(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    _write(shipped, SHIPPED)
    reg = AddonRegistry(shipped, tmp_path / "r.json", tmp_path / "o.json")

    assert reg.get_shipped_and_override("ghost") is None


def test_get_remote_url_reads_from_shipped(tmp_path):
    shipped = tmp_path / "data" / "addons.json"
    _write(shipped, SHIPPED)
    reg = AddonRegistry(shipped, tmp_path / "r.json", tmp_path / "o.json")

    assert reg.get_remote_url() == "https://example.com/addons.json"


def test_refresh_remote_bad_schema_returns_error_does_not_write(tmp_path, monkeypatch):
    shipped = tmp_path / "data" / "addons.json"
    remote = tmp_path / "tools" / "addons_remote.json"
    _write(shipped, SHIPPED)

    class Resp:
        def raise_for_status(self): pass
        def json(self): return {"schema_version": 99, "addons": []}

    import src.core.addon_registry as mod
    monkeypatch.setattr(mod.requests, "get", lambda *a, **kw: Resp())

    reg = AddonRegistry(shipped, remote, tmp_path / "o.json")
    result = reg.refresh_remote()

    assert result["ok"] is False
    assert "schema_version" in result["error"]
    assert not remote.exists()


def test_refresh_remote_success_writes_and_invalidates_cache(tmp_path, monkeypatch):
    shipped = tmp_path / "data" / "addons.json"
    remote = tmp_path / "tools" / "addons_remote.json"
    _write(shipped, SHIPPED)

    new_data = json.loads(json.dumps(SHIPPED))
    new_data["addons"][0]["label"] = "Sage (from remote)"

    class Resp:
        def raise_for_status(self): pass
        def json(self): return new_data

    import src.core.addon_registry as mod
    monkeypatch.setattr(mod.requests, "get", lambda *a, **kw: Resp())

    reg = AddonRegistry(shipped, remote, tmp_path / "o.json")
    reg.list_addons()  # populate cache with shipped
    result = reg.refresh_remote()

    assert result["ok"] is True
    assert remote.exists()
    # Cache was invalidated; new list reflects remote override
    assert reg.find("sage").label == "Sage (from remote)"
