# Addon Registry + One-Click Pack Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users install add-ons that are incompatible with their env's current Torch-Pack via a one-click switch-and-install flow, and give them a Settings editor to customize `compatible_packs` + `wheels_by_pack` per add-on with override support.

**Architecture:** Move add-on definitions from a Python constant (`src/core/addons.py::ADDONS`) to a shipped JSON (`data/addons.json`) with three-layer precedence (override > remote > shipped), mirroring the existing `TorchPackManager` pattern. Add a new `AddonRegistry` core module, new bridge slots, a combined `switch_pack_and_install_addon` flow, and a Settings-page editor tab.

**Tech Stack:** Python 3.10+, PySide6 + QWebChannel bridge, Plain JS frontend (`src/gui/web/js/`), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-20-addon-registry-pack-switch-design.md`

---

## File Structure

**New files:**
- `data/addons.json` — shipped add-on registry (committed; ~5 entries)
- `src/core/addon_registry.py` — `AddonRegistry` class + `Addon` dataclass moved here
- `tests/test_core/test_addon_registry.py` — unit tests for the registry
- `docs/superpowers/plans/2026-04-20-addon-registry-pack-switch.md` — this file

**Modified:**
- `src/core/addons.py` — drop `ADDONS` const and `Addon` dataclass (now in registry), drop module-level `find_addon`; accept `config` parameter in install/uninstall
- `src/core/torch_pack.py` — drop `from src.core.addons import find_addon`; use registry
- `src/core/migrations.py` — drop `from src.core.addons import ADDONS`; use registry
- `src/gui/bridge.py` — drop `ADDONS` import; add 7 new slots
- `src/gui/web/js/pages/environments.js` — addon card needs-switch state, 2 new dialogs, progress stages
- `src/gui/web/js/pages/settings.js` — new "Addon Registry" tab
- `src/gui/web/js/i18n.js` — `addonRegistry.*` and `addonSwitch.*` keys (en + zh-TW)
- `src/gui/web/css/tack-industrial.css` — new classes for needs-switch button, editor layout
- `tests/test_core/test_addons.py` — adapt to registry-based lookup
- `tests/test_core/test_torch_pack.py` — adapt to registry-based lookup
- `tests/test_gui/test_bridge.py` — new slot tests (extend if exists, create if not)
- `VERSION.json` — bump to 0.5.0, update `changes` + `changes_i18n.en` + `changes_i18n.zh-TW`

---

## Setup Note

All paths below are **relative to the worktree root** `D:\tack_project\tk_comfyui_starter2\.claude\worktrees\objective-turing-73d67e` (git branch `claude/objective-turing-73d67e`). Run all `pytest` / `git` commands from that directory.

---

### Task 1: Ship `data/addons.json` (serialize current ADDONS)

Replicate every field of the current `ADDONS` constant into JSON form. This file becomes the source of truth.

**Files:**
- Create: `data/addons.json`

- [ ] **Step 1: Write the file**

```json
{
  "schema_version": 1,
  "last_updated": "2026-04-20",
  "remote_url": "https://raw.githubusercontent.com/tackcrypto1031/tk_comfyui_start_tool/master/data/addons.json",
  "addons": [
    {
      "id": "sage-attention",
      "label": "SageAttention v2.2.0",
      "description": "Attention acceleration — larger batch, lower VRAM",
      "kind": "pip",
      "compatible_packs": [
        "torch-2.9.1-cu130",
        "torch-2.8.0-cu128",
        "torch-2.7.1-cu128"
      ],
      "wheels_by_pack": {
        "torch-2.9.1-cu130": "https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu130torch2.9.0.post3-cp39-abi3-win_amd64.whl",
        "torch-2.8.0-cu128": "https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu128torch2.8.0.post3-cp39-abi3-win_amd64.whl",
        "torch-2.7.1-cu128": "https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0+cu128torch2.7.1.post3-cp39-abi3-win_amd64.whl"
      },
      "pip_spec": null,
      "pip_project_name": "sageattention",
      "source_repo": null,
      "source_ref": null,
      "source_post_install": null,
      "requires_compile": false,
      "pack_pinned": true,
      "risk_note": "Prebuilt Windows wheel (woct0rdho fork), matched to your Torch-Pack."
    },
    {
      "id": "insightface",
      "label": "InsightFace 0.7.3",
      "description": "Face nodes (IPAdapter FaceID, ReActor)",
      "kind": "pip",
      "compatible_packs": [
        "torch-2.9.1-cu130",
        "torch-2.8.0-cu128",
        "torch-2.7.1-cu128"
      ],
      "wheels_by_pack": {
        "torch-2.9.1-cu130": "https://github.com/Gourieff/Assets/raw/main/Insightface/insightface-0.7.3-cp312-cp312-win_amd64.whl",
        "torch-2.8.0-cu128": "https://github.com/Gourieff/Assets/raw/main/Insightface/insightface-0.7.3-cp312-cp312-win_amd64.whl",
        "torch-2.7.1-cu128": "https://github.com/Gourieff/Assets/raw/main/Insightface/insightface-0.7.3-cp312-cp312-win_amd64.whl"
      },
      "pip_spec": "insightface==0.7.3",
      "pip_project_name": "insightface",
      "source_repo": null,
      "source_ref": null,
      "source_post_install": null,
      "requires_compile": false,
      "pack_pinned": false,
      "risk_note": null
    },
    {
      "id": "nunchaku",
      "label": "Nunchaku v1.2.1",
      "description": "Quantized inference (4-bit FLUX)",
      "kind": "pip",
      "compatible_packs": [
        "torch-2.9.1-cu130",
        "torch-2.8.0-cu128"
      ],
      "wheels_by_pack": {
        "torch-2.9.1-cu130": "https://github.com/nunchaku-ai/nunchaku/releases/download/v1.2.1/nunchaku-1.2.1+cu13.0torch2.9-cp312-cp312-win_amd64.whl",
        "torch-2.8.0-cu128": "https://github.com/nunchaku-ai/nunchaku/releases/download/v1.2.1/nunchaku-1.2.1+cu12.8torch2.8-cp312-cp312-win_amd64.whl"
      },
      "pip_spec": null,
      "pip_project_name": "nunchaku",
      "source_repo": null,
      "source_ref": null,
      "source_post_install": null,
      "requires_compile": false,
      "pack_pinned": true,
      "risk_note": null
    },
    {
      "id": "trellis2",
      "label": "Trellis 2.0",
      "description": "3D generation nodes",
      "kind": "custom_node",
      "compatible_packs": [
        "torch-2.8.0-cu128"
      ],
      "wheels_by_pack": null,
      "pip_spec": null,
      "pip_project_name": null,
      "source_repo": "https://github.com/microsoft/TRELLIS.2.git",
      "source_ref": "main",
      "source_post_install": ["pip", "install", "-r", "requirements.txt"],
      "requires_compile": true,
      "pack_pinned": true,
      "risk_note": "Only works on the Torch 2.8.0 + CUDA 12.8 Pack. First install compiles CUDA ops (~20 min) and downloads ~4B weights."
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add -f data/addons.json
git commit -m "data: ship addons.json seeded from ADDONS constant"
```

---

### Task 2: Create `AddonRegistry` — load (shipped only)

Test-first: build the minimum that loads shipped file.

**Files:**
- Create: `src/core/addon_registry.py`
- Create: `tests/test_core/test_addon_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_core/test_addon_registry.py
import json
from pathlib import Path

import pytest

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core/test_addon_registry.py::test_load_shipped_only_returns_addons -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.addon_registry'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/addon_registry.py
"""Add-on registry — loads shipped JSON, applies remote + override layers."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Addon:
    id: str
    label: str
    description: str
    kind: Literal["pip", "custom_node"]
    compatible_packs: tuple[str, ...]
    wheels_by_pack: Optional[dict] = None
    pip_spec: Optional[str] = None
    pip_project_name: Optional[str] = None
    source_repo: Optional[str] = None
    source_ref: Optional[str] = None
    source_post_install: Optional[list] = None
    requires_compile: bool = False
    pack_pinned: bool = False
    risk_note: Optional[str] = None


class AddonRegistry:
    def __init__(
        self,
        shipped_path: Path,
        remote_path: Path,
        override_path: Path,
    ):
        self.shipped_path = Path(shipped_path)
        self.remote_path = Path(remote_path)
        self.override_path = Path(override_path)
        self._cache: Optional[list[Addon]] = None

    def list_addons(self) -> list[Addon]:
        if self._cache is not None:
            return self._cache
        raw = self._read_json(self.shipped_path) or {}
        entries = raw.get("addons", [])
        self._cache = [self._entry_to_addon(e) for e in entries]
        return self._cache

    @staticmethod
    def _entry_to_addon(entry: dict) -> Addon:
        return Addon(
            id=entry["id"],
            label=entry["label"],
            description=entry["description"],
            kind=entry["kind"],
            compatible_packs=tuple(entry.get("compatible_packs") or ()),
            wheels_by_pack=entry.get("wheels_by_pack"),
            pip_spec=entry.get("pip_spec"),
            pip_project_name=entry.get("pip_project_name"),
            source_repo=entry.get("source_repo"),
            source_ref=entry.get("source_ref"),
            source_post_install=entry.get("source_post_install"),
            requires_compile=bool(entry.get("requires_compile", False)),
            pack_pinned=bool(entry.get("pack_pinned", False)),
            risk_note=entry.get("risk_note"),
        )

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_core/test_addon_registry.py::test_load_shipped_only_returns_addons -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/addon_registry.py tests/test_core/test_addon_registry.py
git commit -m "feat(registry): AddonRegistry.list_addons loads shipped JSON"
```

---

### Task 2b: `find()` + unknown id → None

**Files:**
- Modify: `src/core/addon_registry.py`
- Modify: `tests/test_core/test_addon_registry.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_core/test_addon_registry.py`:

```python
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
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 2 FAILs — `AttributeError: ... has no attribute 'find'`

- [ ] **Step 3: Add `find` method**

Add to `AddonRegistry` class in `src/core/addon_registry.py`:

```python
    def find(self, addon_id: str) -> Optional[Addon]:
        for a in self.list_addons():
            if a.id == addon_id:
                return a
        return None
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/addon_registry.py tests/test_core/test_addon_registry.py
git commit -m "feat(registry): AddonRegistry.find returns addon or None"
```

---

### Task 2c: Remote file overrides shipped (schema-gated)

**Files:**
- Modify: `src/core/addon_registry.py`
- Modify: `tests/test_core/test_addon_registry.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_core/test_addon_registry.py`:

```python
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
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 2 new FAILs (remote ignored, shipped still served)

- [ ] **Step 3: Update `list_addons` to consult remote first**

Replace `list_addons` in `src/core/addon_registry.py`:

```python
    def list_addons(self) -> list[Addon]:
        if self._cache is not None:
            return self._cache
        raw = self._pick_source()
        entries = raw.get("addons", [])
        self._cache = [self._entry_to_addon(e) for e in entries]
        return self._cache

    def _pick_source(self) -> dict:
        remote = self._read_json(self.remote_path)
        if remote and remote.get("schema_version") == SCHEMA_VERSION:
            return remote
        if remote is not None:
            logger.warning(
                "Remote addons.json schema mismatch (got %s, expected %s); using shipped",
                remote.get("schema_version"), SCHEMA_VERSION,
            )
        return self._read_json(self.shipped_path) or {}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/addon_registry.py tests/test_core/test_addon_registry.py
git commit -m "feat(registry): remote addons.json overrides shipped (schema-gated)"
```

---

### Task 2d: Override file merges partial fields

Override format: `{"schema_version": 1, "overrides": {"<id>": {"field": value, ...}}}`. Fields are shallow-merged over the shipped/remote entry; for `wheels_by_pack`, dicts are shallow-merged (override keys replace shipped keys, others preserved).

**Files:**
- Modify: `src/core/addon_registry.py`
- Modify: `tests/test_core/test_addon_registry.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_core/test_addon_registry.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 3 new FAILs (overrides not applied)

- [ ] **Step 3: Implement override merge**

Replace `list_addons` in `src/core/addon_registry.py`:

```python
    def list_addons(self) -> list[Addon]:
        if self._cache is not None:
            return self._cache
        raw = self._pick_source()
        overrides = self._load_overrides()
        merged = [
            self._entry_to_addon(self._apply_override(e, overrides.get(e["id"], {})))
            for e in raw.get("addons", [])
        ]
        self._cache = merged
        return self._cache

    def _load_overrides(self) -> dict:
        raw = self._read_json(self.override_path)
        if not raw:
            return {}
        if raw.get("schema_version") != SCHEMA_VERSION:
            logger.warning(
                "addons_override.json schema mismatch (got %s, expected %s); ignoring",
                raw.get("schema_version"), SCHEMA_VERSION,
            )
            return {}
        return raw.get("overrides") or {}

    @staticmethod
    def _apply_override(entry: dict, override: dict) -> dict:
        if not override:
            return entry
        merged = dict(entry)
        for key, value in override.items():
            if key == "wheels_by_pack" and isinstance(value, dict):
                base = dict(entry.get("wheels_by_pack") or {})
                base.update(value)
                merged[key] = base
            else:
                merged[key] = value
        return merged
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/addon_registry.py tests/test_core/test_addon_registry.py
git commit -m "feat(registry): override file merges partial fields over shipped"
```

---

### Task 2e: `save_override` + `clear_override` + `has_override` + cache invalidation

**Files:**
- Modify: `src/core/addon_registry.py`
- Modify: `tests/test_core/test_addon_registry.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_core/test_addon_registry.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify fail**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 5 new FAILs — AttributeErrors.

- [ ] **Step 3: Add mutation methods**

Append to `AddonRegistry` class in `src/core/addon_registry.py`:

```python
    def has_override(self, addon_id: str) -> bool:
        return addon_id in self._load_overrides()

    def save_override(self, addon_id: str, partial_fields: dict) -> None:
        raw = self._read_json(self.override_path) or {
            "schema_version": SCHEMA_VERSION, "overrides": {}
        }
        if raw.get("schema_version") != SCHEMA_VERSION:
            raw = {"schema_version": SCHEMA_VERSION, "overrides": {}}
        raw.setdefault("overrides", {})[addon_id] = partial_fields
        self.override_path.parent.mkdir(parents=True, exist_ok=True)
        self.override_path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._cache = None

    def clear_override(self, addon_id: Optional[str] = None) -> None:
        raw = self._read_json(self.override_path)
        if not raw:
            return
        if addon_id is None:
            raw["overrides"] = {}
        else:
            raw.setdefault("overrides", {}).pop(addon_id, None)
        self.override_path.parent.mkdir(parents=True, exist_ok=True)
        self.override_path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._cache = None
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 13 PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/addon_registry.py tests/test_core/test_addon_registry.py
git commit -m "feat(registry): save/clear override + has_override with cache invalidation"
```

---

### Task 2f: `get_shipped_and_override` + `get_remote_url` + `refresh_remote`

**Files:**
- Modify: `src/core/addon_registry.py`
- Modify: `tests/test_core/test_addon_registry.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_core/test_addon_registry.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify fail**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 4 new FAILs

- [ ] **Step 3: Add methods + requests import**

At the top of `src/core/addon_registry.py`, add after `import json`:

```python
import requests  # noqa: F401 — used by refresh_remote; imported at module top for monkeypatch
```

Append to `AddonRegistry` class:

```python
    def get_shipped_and_override(self, addon_id: str) -> Optional[dict]:
        shipped_raw = self._read_json(self.shipped_path) or {}
        shipped_entry = next(
            (e for e in shipped_raw.get("addons", []) if e["id"] == addon_id), None
        )
        if shipped_entry is None:
            return None
        override = self._load_overrides().get(addon_id, {})
        effective = self._apply_override(shipped_entry, override)
        return {
            "shipped": shipped_entry,
            "override": override,
            "effective": effective,
        }

    def get_remote_url(self) -> str:
        shipped = self._read_json(self.shipped_path) or {}
        return shipped.get("remote_url", "")

    def refresh_remote(self, timeout: int = 15) -> dict:
        url = self.get_remote_url()
        if not url:
            return {"ok": False, "error": "no remote_url configured"}
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        if payload.get("schema_version") != SCHEMA_VERSION:
            return {
                "ok": False,
                "error": f"schema_version mismatch (got {payload.get('schema_version')})",
            }

        self.remote_path.parent.mkdir(parents=True, exist_ok=True)
        self.remote_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._cache = None
        return {"ok": True, "error": ""}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_core/test_addon_registry.py -v`
Expected: 17 PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/addon_registry.py tests/test_core/test_addon_registry.py
git commit -m "feat(registry): shipped/override/effective views + remote refresh"
```

---

### Task 3: Refactor `src/core/addons.py` to use registry

Drop the `ADDONS` constant, drop the module-level `find_addon` (tests will use registry directly). `Addon` class moves to `addon_registry.py`. Install/uninstall gain a `config` parameter to build the registry.

**Files:**
- Modify: `src/core/addons.py`
- Modify: `tests/test_core/test_addons.py`

- [ ] **Step 1: Update `src/core/addons.py`**

Replace the file header imports block (lines 1–22) with:

```python
"""Add-on install / uninstall, driven by AddonRegistry."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.core.addon_registry import Addon, AddonRegistry
from src.models.environment import Environment
from src.utils import git_ops, pip_ops, pkg_ops
```

Delete the `@dataclass(frozen=True) class Addon` block and the `ADDONS: list[Addon] = [...]` literal (roughly lines 25–123).

Delete the module-level `find_addon` function (lines 126–130).

Add a helper at the top of the module (after imports):

```python
def _registry(config: dict) -> AddonRegistry:
    base_dir = Path(config.get("base_dir", "."))
    return AddonRegistry(
        shipped_path=base_dir / "data" / "addons.json",
        remote_path=base_dir / "tools" / "addons_remote.json",
        override_path=base_dir / "tools" / "addons_override.json",
    )
```

Change `install_addon` signature to accept `config` as first arg:

```python
def install_addon(
    config: dict,
    addon_id: str,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback=None,
) -> dict:
    """Install a single add-on into an environment. Returns {id, kind}.

    Raises IncompatiblePackError if the env's current Torch-Pack is not in
    the add-on's compatible_packs. Raises ValueError on unknown id.
    """
    addon = _registry(config).find(addon_id)
    if addon is None:
        raise ValueError(f"Unknown addon: {addon_id}")

    env_dir = Path(env_dir)
    env = Environment.load_meta(str(env_dir))
    current_pack = env.torch_pack or ""

    if current_pack not in addon.compatible_packs:
        raise IncompatiblePackError(
            f"Add-on '{addon_id}' does not support Torch-Pack "
            f"'{current_pack}'. Compatible packs: "
            f"{', '.join(addon.compatible_packs) or '(none)'}"
        )
    # ... rest identical (unchanged)
```

Change `uninstall_addon` signature similarly:

```python
def uninstall_addon(
    config: dict,
    addon_id: str,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback=None,
) -> None:
    """Remove an add-on from an env. Reverse of install_addon."""
    addon = _registry(config).find(addon_id)
    # Orphan case: unknown id — generic cleanup
    if addon is None:
        env = Environment.load_meta(str(env_dir))
        node_dir = Path(env_dir) / "ComfyUI" / "custom_nodes" / addon_id
        if node_dir.exists():
            def _on_rm_error(func, path, exc_info):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(str(node_dir), onerror=_on_rm_error)
        env.installed_addons = [
            a for a in env.installed_addons if a.get("id") != addon_id
        ]
        env.save_meta()
        return
    # ... rest of existing function body unchanged from here
```

- [ ] **Step 2: Update `tests/test_core/test_addons.py` — imports + helper**

Replace top of `tests/test_core/test_addons.py` (lines 1–14) with:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.addons import (
    IncompatiblePackError,
    install_addon,
    uninstall_addon,
)
from src.core.addon_registry import AddonRegistry
from src.models.environment import Environment


def _seed_shipped(base_dir: Path) -> None:
    """Write a minimal data/addons.json matching the real shipped file."""
    shipped = base_dir / "data" / "addons.json"
    shipped.parent.mkdir(parents=True, exist_ok=True)
    shipped.write_text(Path("data/addons.json").read_text(encoding="utf-8"), encoding="utf-8")


def _config(tmp_path: Path) -> dict:
    _seed_shipped(tmp_path)
    return {"base_dir": str(tmp_path), "environments_dir": str(tmp_path / "envs")}
```

Delete old registry-shape tests (`test_registry_has_expected_ids`, `test_find_existing`, `test_find_missing`, `test_pip_addon_has_wheels_and_project_name`, `test_custom_node_addon_has_source_ref`, `test_trellis_gated_to_cu128_pack`, `test_sage_attention_has_per_pack_wheels`, `test_nunchaku_not_compatible_with_torch_2_7`). These are redundant with `test_addon_registry.py`.

For install/uninstall tests that call `install_addon(...)` or `uninstall_addon(...)`, prepend `_config(tmp_path)` as the first positional arg. For example:

```python
# before
install_addon("sage-attention", env_dir, tmp_path, "0.9.7")
# after
install_addon(_config(tmp_path), "sage-attention", env_dir, tmp_path, "0.9.7")
```

Apply this substitution throughout the file.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_core/test_addons.py -v`
Expected: All tests pass. Any failing import or signature mismatch → fix in `addons.py` per steps above.

- [ ] **Step 4: Commit**

```bash
git add src/core/addons.py tests/test_core/test_addons.py
git commit -m "refactor(addons): drop ADDONS constant; drive install/uninstall via AddonRegistry"
```

---

### Task 4: Refactor `switch_pack` to use registry

**Files:**
- Modify: `src/core/torch_pack.py`
- Modify: `tests/test_core/test_torch_pack.py`

- [ ] **Step 1: Update `src/core/torch_pack.py`**

Replace the bottom import block (currently):

```python
from src.core.addons import find_addon  # noqa: E402
```

with:

```python
from src.core.addon_registry import AddonRegistry  # noqa: E402
```

Inside `switch_pack()`, replace the block that uses `find_addon`:

```python
    # Identify pack-pinned add-ons — wheel/source is bound to the current
    # torch version, so we must uninstall before swapping torch.
    compiled_addons = []
    for entry in env.installed_addons:
        addon = find_addon(entry.get("id", ""))
        if addon and addon.pack_pinned:
            compiled_addons.append(entry["id"])
```

with:

```python
    addon_registry = AddonRegistry(
        shipped_path=base_dir / "data" / "addons.json",
        remote_path=base_dir / "tools" / "addons_remote.json",
        override_path=base_dir / "tools" / "addons_override.json",
    )
    # Identify pack-pinned add-ons — orphan ids (not in registry) are skipped.
    compiled_addons = []
    for entry in env.installed_addons:
        addon = addon_registry.find(entry.get("id", ""))
        if addon and addon.pack_pinned:
            compiled_addons.append(entry["id"])
```

And later, inside the `for aid in compiled_addons:` loop, replace:

```python
        addon = find_addon(aid)
```

with:

```python
        addon = addon_registry.find(aid)
```

- [ ] **Step 2: Write an orphan-tolerance test**

Append to `tests/test_core/test_torch_pack.py`:

```python
def test_switch_pack_skips_orphan_installed_addon(tmp_path, monkeypatch):
    """switch_pack should not fail when installed_addons contains an unknown id."""
    from src.core import torch_pack as tp
    from src.core.torch_pack import switch_pack
    from src.models.environment import Environment

    # Seed shipped torch_packs.json + addons.json in tmp_path
    import shutil
    (tmp_path / "data").mkdir()
    shutil.copy("data/torch_packs.json", tmp_path / "data" / "torch_packs.json")
    shutil.copy("data/addons.json", tmp_path / "data" / "addons.json")

    env_dir = tmp_path / "envs" / "main"
    (env_dir / "ComfyUI" / "custom_nodes").mkdir(parents=True)
    (env_dir / "venv").mkdir()

    env = Environment(
        name="main", path=str(env_dir),
        python_version="3.12", pytorch_version="2.9.1+cu130", cuda_tag="cu130",
        comfyui_version="v0.3.0",
        torch_pack="torch-2.9.1-cu130",
        installed_addons=[{"id": "ghost-unknown", "installed_at": "x", "torch_pack_at_install": None}],
    )
    env.save_meta()

    # Mock pkg_ops + SnapshotManager to avoid touching venv / network
    monkeypatch.setattr(tp.pkg_ops, "run_install", lambda **kw: None)
    monkeypatch.setattr(tp.pkg_ops, "freeze", lambda **kw: {})
    monkeypatch.setattr(tp.SnapshotManager, "create_snapshot", lambda self, n, trigger="": None)

    config = {"base_dir": str(tmp_path), "environments_dir": str(tmp_path / "envs")}
    result = switch_pack(config, "main", "torch-2.8.0-cu128",
                         confirm_addon_removal=False)

    # Orphan id should NOT be treated as pack-pinned; switch proceeds.
    assert result["ok"] is True
    assert result["removed_addons"] == []
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_core/test_torch_pack.py -v`
Expected: All pass (existing + new).

- [ ] **Step 4: Commit**

```bash
git add src/core/torch_pack.py tests/test_core/test_torch_pack.py
git commit -m "refactor(torch-pack): use AddonRegistry; skip orphan installed_addons"
```

---

### Task 5: Update `migrations.py` to drop `ADDONS` import

The 0.4.0 migration is gated by a marker file and won't re-run. We only need to satisfy the import.

**Files:**
- Modify: `src/core/migrations.py`

- [ ] **Step 1: Rewrite `migrate_env_meta_0_4_0` imports + known_addon_ids**

Replace line 7 of `src/core/migrations.py`:

```python
from src.core.addons import ADDONS
```

with nothing (delete line). Replace the `known_addon_ids = {a.id for a in ADDONS}` line with:

```python
    # Pre-0.4.0 registry was 5 ids; use a static set since the dynamic
    # registry now requires config and this migration is post-marker anyway.
    known_addon_ids = {"sage-attention", "flash-attention", "insightface", "nunchaku", "trellis2"}
```

- [ ] **Step 2: Run migrations tests**

Run: `pytest tests/test_core/test_migrations.py -v` (if the file exists)

If no `test_migrations.py` exists, run a smoke test:

```bash
python -c "from src.core.migrations import migrate_env_meta_0_4_0; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add src/core/migrations.py
git commit -m "refactor(migrations): drop ADDONS import; inline id list"
```

---

### Task 6: Bridge — update `list_addons` + `install_addon` + `uninstall_addon` slots for new addons.py signatures

**Files:**
- Modify: `src/gui/bridge.py`

- [ ] **Step 1: Update imports**

Change line 9 of `src/gui/bridge.py`:

```python
from src.core.addons import ADDONS, install_addon as _install_addon, uninstall_addon as _uninstall_addon
```

to:

```python
from src.core.addons import install_addon as _install_addon, uninstall_addon as _uninstall_addon
from src.core.addon_registry import AddonRegistry
```

- [ ] **Step 2: Add `_addon_registry` helper**

Inside the `Bridge` class (after existing `_torch_pack_mgr` method, around line 820 — find it with `grep -n "_torch_pack_mgr" src/gui/bridge.py`), add:

```python
    def _addon_registry(self) -> AddonRegistry:
        base_dir = Path(self.config.get("base_dir", "."))
        return AddonRegistry(
            shipped_path=base_dir / "data" / "addons.json",
            remote_path=base_dir / "tools" / "addons_remote.json",
            override_path=base_dir / "tools" / "addons_override.json",
        )
```

- [ ] **Step 3: Rewrite `list_addons` slot**

Replace the existing `list_addons` slot body (around lines 880–898) with:

```python
    @Slot(result=str)
    def list_addons(self) -> str:
        """Return the effective add-on registry (shipped + remote + override merged)."""
        try:
            items = []
            for a in self._addon_registry().list_addons():
                items.append({
                    "id": a.id, "label": a.label, "description": a.description,
                    "kind": a.kind,
                    "compatible_packs": list(a.compatible_packs),
                    "wheels_by_pack": a.wheels_by_pack,
                    "requires_compile": a.requires_compile,
                    "pack_pinned": a.pack_pinned,
                    "risk_note": a.risk_note,
                })
            return json.dumps({"ok": True, "addons": items}, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"list_addons error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})
```

- [ ] **Step 4: Rewrite `install_addon` + `uninstall_addon` slots to pass config**

Find existing slots (around lines 900–940). Replace their bodies:

```python
    @Slot(str, str, str)
    def install_addon(self, request_id: str, env_name: str, addon_id: str) -> None:
        """Install an add-on into an env (async)."""
        def _do():
            env_dir = self.environments_dir / env_name
            base_dir = Path(self.config.get("base_dir", "."))
            mgr = self._torch_pack_mgr()
            uv_version = mgr.get_recommended_uv_version() or "0.9.7"
            pkg_mgr = self.config.get("package_manager", "uv")
            return _install_addon(
                self.config, addon_id, env_dir, base_dir / "tools",
                uv_version, pkg_mgr,
                progress_callback=lambda msg: self.push_progress(
                    request_id, "install", 60, msg if isinstance(msg, str) else str(msg)
                ),
            )
        self._run_async(request_id, _do)

    @Slot(str, str, str)
    def uninstall_addon(self, request_id: str, env_name: str, addon_id: str) -> None:
        """Uninstall an add-on from an env (async)."""
        def _do():
            env_dir = self.environments_dir / env_name
            base_dir = Path(self.config.get("base_dir", "."))
            mgr = self._torch_pack_mgr()
            uv_version = mgr.get_recommended_uv_version() or "0.9.7"
            pkg_mgr = self.config.get("package_manager", "uv")
            _uninstall_addon(
                self.config, addon_id, env_dir, base_dir / "tools",
                uv_version, pkg_mgr,
            )
            return {"ok": True, "id": addon_id}
        self._run_async(request_id, _do)
```

- [ ] **Step 5: Smoke test**

Run: `python -c "from src.gui.bridge import Bridge; print('import ok')"`
Expected: `import ok`

- [ ] **Step 6: Commit**

```bash
git add src/gui/bridge.py
git commit -m "refactor(bridge): addons use registry; pass config to install/uninstall"
```

---

### Task 7: Bridge — `switch_pack_and_install_addon` combined flow

This is the core new flow. Returns `{ok, noop, removed_addons, installed_addon, failed_at, error}` where `failed_at ∈ {"switch", "install", ""}`.

**Files:**
- Modify: `src/gui/bridge.py`

- [ ] **Step 1: Add the slot**

In `src/gui/bridge.py`, after the `switch_torch_pack` slot (around line 878), add:

```python
    @Slot(str, str, str, str)
    def switch_pack_and_install_addon(
        self, request_id: str, env_name: str,
        target_pack_id: str, addon_id: str,
    ) -> None:
        """Two-stage: switch Pack, then install addon. Async.

        Progress 0-60% is the switch; 60-100% is the install.
        """
        def _do():
            base_dir = Path(self.config.get("base_dir", "."))
            mgr = self._torch_pack_mgr()
            uv_version = mgr.get_recommended_uv_version() or "0.9.7"
            pkg_mgr = self.config.get("package_manager", "uv")
            env_dir = self.environments_dir / env_name

            # Stage 1: switch (0-60%)
            def _stage1(step, pct, detail=""):
                scaled = int(pct * 0.6)
                self.push_progress(request_id, f"switch:{step}", scaled, detail)

            switch_result = _switch_pack(
                config=self.config, env_name=env_name,
                target_pack_id=target_pack_id,
                confirm_addon_removal=True,
                progress_callback=_stage1,
            )
            if not switch_result.get("ok"):
                return {
                    "ok": False, "noop": False,
                    "removed_addons": switch_result.get("removed_addons", []),
                    "installed_addon": None,
                    "failed_at": "switch",
                    "error": switch_result.get("error", ""),
                }

            # Stage 2: install addon (60-100%)
            self.push_progress(request_id, "install:start", 60,
                               f"Installing {addon_id}...")

            def _stage2(msg):
                # We don't have granular % from install_addon — report 80 as heartbeat.
                text = msg if isinstance(msg, str) else str(msg)
                self.push_progress(request_id, "install:progress", 80, text)

            try:
                _install_addon(
                    self.config, addon_id, env_dir,
                    base_dir / "tools", uv_version, pkg_mgr,
                    progress_callback=_stage2,
                )
            except Exception as exc:
                return {
                    "ok": False, "noop": False,
                    "removed_addons": switch_result.get("removed_addons", []),
                    "installed_addon": None,
                    "failed_at": "install",
                    "error": str(exc),
                }

            self.push_progress(request_id, "done", 100, "Switch + install complete.")
            return {
                "ok": True, "noop": switch_result.get("noop", False),
                "removed_addons": switch_result.get("removed_addons", []),
                "installed_addon": addon_id,
                "failed_at": "",
                "error": "",
            }

        self._run_async(request_id, _do)
```

- [ ] **Step 2: Smoke-test import**

Run: `python -c "from src.gui.bridge import Bridge; print('import ok')"`
Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add src/gui/bridge.py
git commit -m "feat(bridge): switch_pack_and_install_addon combined flow with staged progress"
```

---

### Task 8: Bridge — `reinstall_addons` batch

**Files:**
- Modify: `src/gui/bridge.py`

- [ ] **Step 1: Add slot**

After `switch_pack_and_install_addon`, add:

```python
    @Slot(str, str, "QVariantList")
    def reinstall_addons(
        self, request_id: str, env_name: str, addon_ids,
    ) -> None:
        """Reinstall a batch of add-ons. Per-id success reported; does not abort on failure."""
        def _do():
            base_dir = Path(self.config.get("base_dir", "."))
            mgr = self._torch_pack_mgr()
            uv_version = mgr.get_recommended_uv_version() or "0.9.7"
            pkg_mgr = self.config.get("package_manager", "uv")
            env_dir = self.environments_dir / env_name
            total = max(len(addon_ids), 1)
            results = []
            for idx, aid in enumerate(addon_ids):
                pct = int((idx / total) * 100)
                self.push_progress(request_id, "reinstall", pct, f"Installing {aid}...")
                try:
                    _install_addon(
                        self.config, str(aid), env_dir,
                        base_dir / "tools", uv_version, pkg_mgr,
                    )
                    results.append({"id": str(aid), "ok": True, "error": ""})
                except Exception as exc:
                    results.append({"id": str(aid), "ok": False, "error": str(exc)})
            self.push_progress(request_id, "done", 100, f"Reinstalled {len(addon_ids)} add-ons.")
            return {"results": results}
        self._run_async(request_id, _do)
```

- [ ] **Step 2: Smoke test**

Run: `python -c "from src.gui.bridge import Bridge; print('import ok')"`
Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add src/gui/bridge.py
git commit -m "feat(bridge): reinstall_addons batch with per-id result reporting"
```

---

### Task 9: Bridge — Addon Registry editor slots

Five slots: `list_addons_with_override_status`, `get_addon_for_edit`, `save_addon_override`, `clear_addon_override`, `refresh_addons_remote`.

**Files:**
- Modify: `src/gui/bridge.py`

- [ ] **Step 1: Add slots**

After `reinstall_addons`, add:

```python
    @Slot(result=str)
    def list_addons_with_override_status(self) -> str:
        """Registry tab: list all addons with has_override flag."""
        try:
            reg = self._addon_registry()
            items = []
            for a in reg.list_addons():
                items.append({
                    "id": a.id, "label": a.label, "kind": a.kind,
                    "pack_pinned": a.pack_pinned,
                    "has_override": reg.has_override(a.id),
                })
            return json.dumps({"ok": True, "addons": items}, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"list_addons_with_override_status error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, result=str)
    def get_addon_for_edit(self, addon_id: str) -> str:
        """Return {shipped, override, effective} view for editor init."""
        try:
            view = self._addon_registry().get_shipped_and_override(addon_id)
            if view is None:
                return json.dumps({"ok": False, "error": f"unknown addon: {addon_id}"})
            return json.dumps({"ok": True, **view}, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"get_addon_for_edit error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str, result=str)
    def save_addon_override(self, addon_id: str, fields_json: str) -> str:
        """Write a partial override for addon_id. Returns {ok, error}."""
        try:
            fields = json.loads(fields_json)
            if not isinstance(fields, dict):
                raise ValueError("fields must be a JSON object")
            self._addon_registry().save_override(addon_id, fields)
            return json.dumps({"ok": True, "error": ""})
        except Exception as exc:
            logger.error(f"save_addon_override error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, result=str)
    def clear_addon_override(self, addon_id: str) -> str:
        """Empty string → wipe all; non-empty → wipe single id. Returns {ok, error}."""
        try:
            target = addon_id if addon_id else None
            self._addon_registry().clear_override(target)
            return json.dumps({"ok": True, "error": ""})
        except Exception as exc:
            logger.error(f"clear_addon_override error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(result=str)
    def refresh_addons_remote(self) -> str:
        """Pull remote addons.json; returns {ok, error}."""
        try:
            return json.dumps(self._addon_registry().refresh_remote())
        except Exception as exc:
            logger.error(f"refresh_addons_remote error: {exc}")
            return json.dumps({"ok": False, "error": str(exc)})
```

- [ ] **Step 2: Smoke test**

Run: `python -c "from src.gui.bridge import Bridge; print('import ok')"`
Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add src/gui/bridge.py
git commit -m "feat(bridge): addon registry editor slots (list/get/save/clear/refresh)"
```

---

### Task 10: Bridge unit tests (happy path + failure reporting)

Light coverage — mock the core modules.

**Files:**
- Create or modify: `tests/test_gui/test_bridge.py`

- [ ] **Step 1: Check if file exists**

```bash
ls tests/test_gui/test_bridge.py 2>&1
```

If missing, create `tests/test_gui/__init__.py` (empty) and a new test file.

- [ ] **Step 2: Write tests**

Create `tests/test_gui/test_bridge.py` with:

```python
import json
from unittest.mock import MagicMock, patch

import pytest

from src.gui.bridge import Bridge


@pytest.fixture
def bridge(tmp_path):
    (tmp_path / "envs").mkdir()
    (tmp_path / "data").mkdir()
    # Seed shipped addons.json + torch_packs.json from repo copies
    import shutil
    shutil.copy("data/addons.json", tmp_path / "data" / "addons.json")
    shutil.copy("data/torch_packs.json", tmp_path / "data" / "torch_packs.json")
    config = {
        "base_dir": str(tmp_path),
        "environments_dir": str(tmp_path / "envs"),
        "package_manager": "uv",
    }
    b = Bridge(config)
    yield b


def test_list_addons_with_override_status_reports_false_when_no_override(bridge):
    payload = json.loads(bridge.list_addons_with_override_status())
    assert payload["ok"] is True
    ids = [a["id"] for a in payload["addons"]]
    assert "sage-attention" in ids
    assert all(a["has_override"] is False for a in payload["addons"])


def test_save_addon_override_then_has_override_true(bridge):
    result = json.loads(bridge.save_addon_override(
        "sage-attention",
        json.dumps({"compatible_packs": ["torch-2.9.1-cu130"]}),
    ))
    assert result["ok"] is True
    after = json.loads(bridge.list_addons_with_override_status())
    sage = next(a for a in after["addons"] if a["id"] == "sage-attention")
    assert sage["has_override"] is True


def test_clear_addon_override_by_id(bridge):
    bridge.save_addon_override("sage-attention",
                               json.dumps({"compatible_packs": ["X"]}))
    r = json.loads(bridge.clear_addon_override("sage-attention"))
    assert r["ok"] is True
    after = json.loads(bridge.list_addons_with_override_status())
    sage = next(a for a in after["addons"] if a["id"] == "sage-attention")
    assert sage["has_override"] is False


def test_get_addon_for_edit_returns_three_views(bridge):
    bridge.save_addon_override("sage-attention",
                               json.dumps({"compatible_packs": ["torch-2.9.1-cu130"]}))
    payload = json.loads(bridge.get_addon_for_edit("sage-attention"))
    assert payload["ok"] is True
    assert "shipped" in payload and "override" in payload and "effective" in payload
    assert payload["effective"]["compatible_packs"] == ["torch-2.9.1-cu130"]


def test_get_addon_for_edit_unknown_id_returns_error(bridge):
    payload = json.loads(bridge.get_addon_for_edit("ghost"))
    assert payload["ok"] is False


def test_save_addon_override_invalid_json_returns_error(bridge):
    payload = json.loads(bridge.save_addon_override("sage-attention", "not json"))
    assert payload["ok"] is False
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_gui/test_bridge.py -v`
Expected: 6 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_gui/test_bridge.py tests/test_gui/__init__.py
git commit -m "test(bridge): registry editor slots happy-path + failure reporting"
```

---

### Task 11: i18n keys

**Files:**
- Modify: `src/gui/web/js/i18n.js`

- [ ] **Step 1: Find the language dictionary shape**

```bash
grep -n "addons\." src/gui/web/js/i18n.js | head -20
```

Note the structure (likely `{ en: { ... }, 'zh-TW': { ... } }`).

- [ ] **Step 2: Add keys under both `en` and `zh-TW`**

For EACH language block in `src/gui/web/js/i18n.js`, add keys. Example (English):

```js
// --- Addon switch-and-install dialog ---
'addonSwitch.title': 'Install {addon}',
'addonSwitch.currentEnv': 'Current env: {env} ({pack})',
'addonSwitch.targetPack': 'Switch to: {pack}',
'addonSwitch.sideEffectsHeader': 'This switch will:',
'addonSwitch.snapshot': '• Create a pre-switch snapshot (automatic)',
'addonSwitch.reinstallTorch': '• Reinstall the PyTorch trio',
'addonSwitch.reapplyPinned': '• Re-apply global pinned packages',
'addonSwitch.removePinned': '• Remove pack-pinned add-ons: {list}',
'addonSwitch.installTarget': '• Install {addon}',
'addonSwitch.etaHeader': 'Estimated time: 15–30 minutes (longer if the add-on compiles CUDA ops)',
'addonSwitch.riskNote': 'Note:',
'addonSwitch.cancel': 'Cancel',
'addonSwitch.confirm': 'Start switch and install',
'addonSwitch.stage1': 'Stage 1 of 2: Switching Pack',
'addonSwitch.stage2': 'Stage 2 of 2: Installing {addon}',
'addonSwitch.failedSwitchTitle': 'Pack switch failed',
'addonSwitch.failedInstallTitle': 'Add-on install failed — Pack was switched',
'addonSwitch.failedInstallMessage': 'The env is now on {pack}, but {addon} failed to install: {error}',
'addonSwitch.restoreSnapshot': 'Restore from snapshot',
'addonSwitch.retryInstall': 'Retry install',
'addonSwitch.keepCurrent': 'Keep current state',

// --- Addon reinstall dialog ---
'addonReinstall.title': 'Previously installed add-ons detected',
'addonReinstall.body': 'You just switched Torch-Pack. These add-ons were removed during the switch but are still compatible with the new Pack ({pack}). Reinstall them?',
'addonReinstall.skip': 'Skip',
'addonReinstall.confirm': 'Reinstall selected ({n})',
'addonReinstall.toastSuccess': 'Reinstalled {done}/{total}',
'addonReinstall.toastPartial': 'Reinstalled {done}/{total} (see details for failures)',

// --- Addon Registry tab (Settings) ---
'addonRegistry.tabTitle': 'Add-on Registry',
'addonRegistry.restoreAllDefaults': 'Restore official defaults',
'addonRegistry.hasOverride': 'Customized',
'addonRegistry.edit': 'Edit',
'addonRegistry.packPinned': 'pack-pinned',
'addonRegistry.footerInfo': 'Edits here create local overrides. To add new add-ons, edit data/addons.json directly.',
'addonRegistry.refreshRemote': 'Check for add-on updates',
'addonRegistry.refreshSuccess': 'Add-on registry updated from remote.',
'addonRegistry.refreshFailed': 'Remote refresh failed: {error}',

// --- Editor dialog ---
'addonRegistry.editorTitle': 'Edit: {label}',
'addonRegistry.compatiblePacksHeader': 'Compatible Torch-Packs',
'addonRegistry.wheelsHeader': 'Wheel URLs (kind=pip)',
'addonRegistry.unknownPack': '(unknown Pack)',
'addonRegistry.noWheelWarning': 'No URL — will fall back to PyPI (pip_spec)',
'addonRegistry.save': 'Save',
'addonRegistry.cancel': 'Cancel',
'addonRegistry.restoreAddonDefaults': 'Restore this add-on\u2019s defaults',
'addonRegistry.confirmEmptyPacks': 'This add-on will be uninstallable. Continue?',
'addonRegistry.confirmPyPIFallback': 'The following Packs will fall back to PyPI: {list}. Continue?',
'addonRegistry.confirmRestoreAll': 'This will remove all add-on customizations. Continue?',
'addonRegistry.invalidUrlError': 'URL must start with http:// or https://',

// --- Addon card needs-switch state ---
'addonCard.installNeedsSwitch': 'Install (requires switching to {pack})',
'addonCard.notCompatible': 'Not compatible',
'addonCard.unknownAddon': '? Unknown add-on (id={id})',
'addonCard.uninstall': 'Uninstall',
```

For zh-TW, the same keys with values:

```js
'addonSwitch.title': '安裝 {addon}',
'addonSwitch.currentEnv': '目前環境:{env}({pack})',
'addonSwitch.targetPack': '需切換到:{pack}',
'addonSwitch.sideEffectsHeader': '此切換將會:',
'addonSwitch.snapshot': '• 建立切換前快照(自動)',
'addonSwitch.reinstallTorch': '• 重新安裝 PyTorch trio',
'addonSwitch.reapplyPinned': '• 重新套用全域 pinned 套件',
'addonSwitch.removePinned': '• 移除 pack-pinned add-ons:{list}',
'addonSwitch.installTarget': '• 安裝 {addon}',
'addonSwitch.etaHeader': '預估時間:約 15-30 分鐘(若 add-on 需編譯 CUDA 可能更久)',
'addonSwitch.riskNote': '注意:',
'addonSwitch.cancel': '取消',
'addonSwitch.confirm': '開始切換並安裝',
'addonSwitch.stage1': '階段 1/2:切換 Pack',
'addonSwitch.stage2': '階段 2/2:安裝 {addon}',
'addonSwitch.failedSwitchTitle': 'Pack 切換失敗',
'addonSwitch.failedInstallTitle': 'Add-on 安裝失敗 — Pack 已切換',
'addonSwitch.failedInstallMessage': '環境已切換到 {pack},但 {addon} 安裝失敗:{error}',
'addonSwitch.restoreSnapshot': '從快照回復',
'addonSwitch.retryInstall': '重試安裝',
'addonSwitch.keepCurrent': '保留現狀',

'addonReinstall.title': '偵測到先前安裝的 Add-ons',
'addonReinstall.body': '你剛才切換了 Torch-Pack。以下 add-ons 在切換時被移除,但在新 Pack ({pack}) 上仍然相容。要重新安裝嗎?',
'addonReinstall.skip': '跳過',
'addonReinstall.confirm': '重裝勾選的 ({n})',
'addonReinstall.toastSuccess': '已重裝 {done}/{total}',
'addonReinstall.toastPartial': '已重裝 {done}/{total}(詳情見失敗項目)',

'addonRegistry.tabTitle': 'Add-on Registry',
'addonRegistry.restoreAllDefaults': '回復官方預設',
'addonRegistry.hasOverride': '已自訂',
'addonRegistry.edit': '編輯',
'addonRegistry.packPinned': 'pack-pinned',
'addonRegistry.footerInfo': '此處編輯會建立本地覆寫。要新增 add-on 請直接編輯 data/addons.json。',
'addonRegistry.refreshRemote': '檢查 add-on 更新',
'addonRegistry.refreshSuccess': 'Add-on Registry 已從遠端更新。',
'addonRegistry.refreshFailed': '遠端更新失敗:{error}',

'addonRegistry.editorTitle': '編輯:{label}',
'addonRegistry.compatiblePacksHeader': '相容的 Torch-Packs',
'addonRegistry.wheelsHeader': 'Wheel URLs (kind=pip)',
'addonRegistry.unknownPack': '(未知 Pack)',
'addonRegistry.noWheelWarning': '無 URL,將 fallback 到 PyPI (pip_spec)',
'addonRegistry.save': '儲存',
'addonRegistry.cancel': '取消',
'addonRegistry.restoreAddonDefaults': '回復此 add-on 的官方預設',
'addonRegistry.confirmEmptyPacks': '此 add-on 將變為不可安裝。確定?',
'addonRegistry.confirmPyPIFallback': '以下 Packs 將 fallback 到 PyPI:{list}。確定?',
'addonRegistry.confirmRestoreAll': '將移除所有 add-on 自訂覆寫。確定?',
'addonRegistry.invalidUrlError': 'URL 必須以 http:// 或 https:// 開頭',

'addonCard.installNeedsSwitch': '安裝(需切換到 {pack})',
'addonCard.notCompatible': '不相容',
'addonCard.unknownAddon': '? 不明 add-on (id={id})',
'addonCard.uninstall': '解除安裝',
```

- [ ] **Step 2: Commit**

```bash
git add src/gui/web/js/i18n.js
git commit -m "i18n: add keys for addon switch/reinstall dialogs and registry editor"
```

---

### Task 12: Frontend — addon card needs-switch state

**Files:**
- Modify: `src/gui/web/js/pages/environments.js`

- [ ] **Step 1: Locate the addon card render function**

```bash
grep -n "addon\|list_addons\|installed_addons\|custom_nodes" src/gui/web/js/pages/environments.js | head -30
```

Find the function that renders an addon card (likely named `renderAddon(addon, env)` or similar). Open the file to confirm.

- [ ] **Step 2: Add pack-recommendation helper**

Near the top of `src/gui/web/js/pages/environments.js` (after existing helpers), add:

```js
/**
 * Given an addon and the env's current GPU info + pack list,
 * return the recommended target Pack id + label for "needs switch" state,
 * or null if no compatible pack exists.
 */
function recommendTargetPackForAddon(addon, allPacks, gpuInfo) {
  const compatible = allPacks.filter(p => addon.compatible_packs.includes(p.id));
  if (compatible.length === 0) return null;

  const driver = parseFloat(gpuInfo && gpuInfo.cuda_driver_version || '0');
  if (driver > 0) {
    // Prefer recommended=true, then lower min_driver (most compatible)
    const usable = compatible
      .filter(p => driver >= p.min_driver)
      .sort((a, b) => (b.recommended - a.recommended) || (a.min_driver - b.min_driver));
    if (usable.length > 0) return usable[0];
  }
  // Fall back: pack with lowest min_driver (most likely to run on older GPUs)
  return [...compatible].sort((a, b) => a.min_driver - b.min_driver)[0];
}
```

- [ ] **Step 3: Update the addon card renderer**

Inside the card-render function, replace the install-button logic with state-machine:

```js
// Compute card state
const installed = (env.installed_addons || []).some(a => a.id === addon.id);
const currentPack = env.torch_pack;
const isCompatible = addon.compatible_packs.includes(currentPack);

let button;
if (installed) {
  button = `<button class="btn-uninstall" data-addon="${addon.id}">${t('addonCard.uninstall')}</button>`;
} else if (isCompatible) {
  button = `<button class="btn-install" data-addon="${addon.id}">${t('addons.install')}</button>`;
} else {
  const target = recommendTargetPackForAddon(addon, allPacks, gpuInfo);
  if (!target) {
    button = `<button class="btn-install" disabled>${t('addonCard.notCompatible')}</button>`;
  } else {
    button = `<button class="btn-install btn-needs-switch" data-addon="${addon.id}" data-target-pack="${target.id}">${t('addonCard.installNeedsSwitch', { pack: target.label })}</button>`;
  }
}
```

Adapt wiring to the existing `t()` helper's signature (some i18n files use `t('key', { pack: 'X' })`, others use `t('key').replace('{pack}', 'X')`). Match the existing pattern from lines 7b2eaa8 or earlier.

- [ ] **Step 4: Wire the `btn-needs-switch` click to open the switch-install dialog (stub, real dialog in Task 13)**

```js
container.addEventListener('click', (e) => {
  if (e.target.classList.contains('btn-needs-switch')) {
    const addonId = e.target.dataset.addon;
    const targetPackId = e.target.dataset.targetPack;
    openAddonSwitchInstallDialog(env, addonId, targetPackId);
  }
});
```

Declare placeholder:

```js
function openAddonSwitchInstallDialog(env, addonId, targetPackId) {
  console.warn('openAddonSwitchInstallDialog not yet implemented', env, addonId, targetPackId);
}
```

- [ ] **Step 5: Manual smoke**

Launch the app once, open env page, confirm the Trellis 2.0 button now says `安裝(需切換到 PyTorch 2.8.0 + CUDA 12.8)` on a cu130 env.

- [ ] **Step 6: Commit**

```bash
git add src/gui/web/js/pages/environments.js
git commit -m "feat(ui): addon card shows needs-switch state with target Pack label"
```

---

### Task 13: Frontend — `AddonSwitchInstallDialog`

**Files:**
- Modify: `src/gui/web/js/pages/environments.js`
- Modify: `src/gui/web/css/tack-industrial.css`

- [ ] **Step 1: Replace the `openAddonSwitchInstallDialog` stub**

Replace the stub in `environments.js`:

```js
async function openAddonSwitchInstallDialog(env, addonId, targetPackId) {
  const addon = addonById(addonId);
  const targetPack = packById(targetPackId);
  const currentPack = packById(env.torch_pack);

  // Compute side effects — pack-pinned addons currently installed
  const removedPinned = (env.installed_addons || [])
    .map(e => addonById(e.id))
    .filter(a => a && a.pack_pinned && a.id !== addonId)
    .map(a => a.label);

  const etaExtra = addon.requires_compile ? ' (+20 min compile)' : '';
  const riskNote = addon.risk_note || '';

  const bodyHtml = `
    <div class="switch-install-body">
      <div>${t('addonSwitch.currentEnv', { env: env.name, pack: currentPack.label })}</div>
      <div>${t('addonSwitch.targetPack', { pack: targetPack.label })}</div>
      <div class="section-header">${t('addonSwitch.sideEffectsHeader')}</div>
      <div>${t('addonSwitch.snapshot')}</div>
      <div>${t('addonSwitch.reinstallTorch')}</div>
      <div>${t('addonSwitch.reapplyPinned')}</div>
      ${removedPinned.length ? `<div>${t('addonSwitch.removePinned', { list: removedPinned.join(', ') })}</div>` : ''}
      <div>${t('addonSwitch.installTarget', { addon: addon.label })}</div>
      <div class="eta">${t('addonSwitch.etaHeader')}${etaExtra}</div>
      ${riskNote ? `<div class="risk-note">${t('addonSwitch.riskNote')} ${riskNote}</div>` : ''}
    </div>
  `;

  const confirmed = await showConfirmDialog({
    title: t('addonSwitch.title', { addon: addon.label }),
    bodyHtml,
    cancelLabel: t('addonSwitch.cancel'),
    confirmLabel: t('addonSwitch.confirm'),
  });
  if (!confirmed) return;

  await runAddonSwitchInstall(env, addonId, targetPackId);
}

async function runAddonSwitchInstall(env, addonId, targetPackId) {
  const requestId = newRequestId();
  const addon = addonById(addonId);

  openProgressDialog({
    title: t('addonSwitch.title', { addon: addon.label }),
    stages: [
      t('addonSwitch.stage1'),
      t('addonSwitch.stage2', { addon: addon.label }),
    ],
    onProgress: (msg) => {
      // msg.step is "switch:*" (0-60%) or "install:*" (60-100%)
      const stageIdx = msg.step.startsWith('install') ? 1 : 0;
      setProgressStage(stageIdx);
      setProgressBar(msg.percent, msg.detail);
    },
  });

  bridge.switch_pack_and_install_addon(requestId, env.name, targetPackId, addonId);
  const result = await pollRequest(requestId);
  closeProgressDialog();

  if (!result.ok) {
    if (result.failed_at === 'switch') {
      showErrorToast(t('addonSwitch.failedSwitchTitle') + ': ' + result.error);
      return;
    }
    // failed_at === 'install': switch succeeded, install failed
    const choice = await showThreeButtonDialog({
      title: t('addonSwitch.failedInstallTitle'),
      body: t('addonSwitch.failedInstallMessage', {
        pack: packById(targetPackId).label, addon: addon.label, error: result.error
      }),
      buttons: [
        { id: 'restore', label: t('addonSwitch.restoreSnapshot') },
        { id: 'retry', label: t('addonSwitch.retryInstall') },
        { id: 'keep', label: t('addonSwitch.keepCurrent') },
      ],
    });
    if (choice === 'restore') {
      await restoreLatestSnapshot(env.name);
    } else if (choice === 'retry') {
      await installAddonOnly(env, addonId);
    }
    // On 'keep' or restore/retry success, still consider reinstall prompt
  }

  // Post-switch reinstall prompt (only if removed_addons non-empty)
  await maybeShowReinstallDialog(env, result.removed_addons || [], targetPackId, addonId);
  // Reload env view
  await reloadEnvironments();
}
```

- [ ] **Step 2: Add helpers referenced above (if missing)**

At the end of `environments.js` add (skip any that already exist):

```js
function addonById(id) {
  return (window._addonRegistryCache || []).find(a => a.id === id);
}

function packById(id) {
  return (window._torchPackCache || []).find(p => p.id === id);
}

async function installAddonOnly(env, addonId) {
  const requestId = newRequestId();
  bridge.install_addon(requestId, env.name, addonId);
  await pollRequest(requestId);
}

async function restoreLatestSnapshot(envName) {
  // reuse existing snapshot restore; find the most recent pre-switch snapshot
  // via bridge.list_snapshots and call bridge.restore_snapshot
  const list = JSON.parse(bridge.list_snapshots(envName));
  const preSwitch = (list.snapshots || []).find(s => (s.trigger || '') === 'pack_switch');
  if (!preSwitch) {
    showErrorToast('No pre-switch snapshot found');
    return;
  }
  const rid = newRequestId();
  bridge.restore_snapshot(rid, envName, preSwitch.id);
  await pollRequest(rid);
}
```

- [ ] **Step 3: CSS**

Append to `src/gui/web/css/tack-industrial.css`:

```css
.btn-needs-switch {
  background: var(--warning-bg, #5a4a1a);
  color: var(--warning-fg, #f0d060);
  font-size: 0.9em;
}
.switch-install-body { line-height: 1.5; }
.switch-install-body .section-header {
  margin-top: 0.8em; font-weight: 600;
}
.switch-install-body .eta {
  margin-top: 0.6em; color: var(--muted-fg, #aaa);
}
.switch-install-body .risk-note {
  margin-top: 0.6em; padding: 0.5em;
  background: var(--warning-bg, #3a2a10);
  border-left: 3px solid var(--warning-border, #c09040);
}
```

- [ ] **Step 4: Manual smoke**

Run the app; click the Trellis 2.0 "需切換" button on a cu130 env; confirm dialog shows all 6 side-effect bullets + risk note.

- [ ] **Step 5: Commit**

```bash
git add src/gui/web/js/pages/environments.js src/gui/web/css/tack-industrial.css
git commit -m "feat(ui): AddonSwitchInstallDialog with staged progress + failure recovery"
```

---

### Task 14: Frontend — `AddonReinstallDialog`

**Files:**
- Modify: `src/gui/web/js/pages/environments.js`

- [ ] **Step 1: Implement the dialog**

Append to `environments.js`:

```js
async function maybeShowReinstallDialog(env, removedAddonIds, newPackId, justInstalledId) {
  const registry = window._addonRegistryCache || [];
  const eligible = removedAddonIds
    .map(id => registry.find(a => a.id === id))
    .filter(a => a && a.id !== justInstalledId && a.compatible_packs.includes(newPackId));
  if (eligible.length === 0) return;

  const bodyHtml = `
    <div>${t('addonReinstall.body', { pack: packById(newPackId).label })}</div>
    <div class="reinstall-list">
      ${eligible.map(a => `
        <label class="reinstall-row">
          <input type="checkbox" value="${a.id}" checked />
          <span class="name">${a.label}</span>
          <span class="desc">${a.description}</span>
        </label>
      `).join('')}
    </div>
  `;

  const picked = await showCheckboxDialog({
    title: t('addonReinstall.title'),
    bodyHtml,
    cancelLabel: t('addonReinstall.skip'),
    confirmLabelTemplate: (n) => t('addonReinstall.confirm', { n }),
  });
  if (!picked || picked.length === 0) return;

  const rid = newRequestId();
  openProgressDialog({ title: t('addonReinstall.title'), stages: [], onProgress: m => setProgressBar(m.percent, m.detail) });
  bridge.reinstall_addons(rid, env.name, picked);
  const res = await pollRequest(rid);
  closeProgressDialog();

  const ok = (res.results || []).filter(r => r.ok).length;
  const total = (res.results || []).length;
  if (ok === total) {
    showInfoToast(t('addonReinstall.toastSuccess', { done: ok, total }));
  } else {
    showInfoToast(t('addonReinstall.toastPartial', { done: ok, total }));
  }
}
```

- [ ] **Step 2: Add `showCheckboxDialog` helper (if missing)**

If no checkbox-dialog helper exists, add to the shared `src/gui/web/js/dialogs.js` (or wherever other dialogs live — find with `grep -n "showConfirmDialog" src/gui/web/js/`):

```js
export async function showCheckboxDialog({ title, bodyHtml, cancelLabel, confirmLabelTemplate }) {
  return new Promise((resolve) => {
    const dialog = document.createElement('div');
    dialog.className = 'modal-backdrop';
    dialog.innerHTML = `
      <div class="modal">
        <h2>${title}</h2>
        <div class="modal-body">${bodyHtml}</div>
        <div class="modal-footer">
          <button class="btn-cancel">${cancelLabel}</button>
          <button class="btn-confirm">${confirmLabelTemplate(0)}</button>
        </div>
      </div>
    `;
    document.body.appendChild(dialog);
    const confirm = dialog.querySelector('.btn-confirm');
    const checkboxes = () => Array.from(dialog.querySelectorAll('input[type=checkbox]'));
    const update = () => {
      const checked = checkboxes().filter(c => c.checked).map(c => c.value);
      confirm.textContent = confirmLabelTemplate(checked.length);
    };
    dialog.addEventListener('change', update);
    update();
    dialog.querySelector('.btn-cancel').onclick = () => { dialog.remove(); resolve(null); };
    confirm.onclick = () => {
      const picked = checkboxes().filter(c => c.checked).map(c => c.value);
      dialog.remove();
      resolve(picked);
    };
  });
}
```

- [ ] **Step 3: Manual smoke**

Flow: on cu130 env, click Trellis2 needs-switch, confirm. After switch + install, the Reinstall dialog shows sage-attention (cu130 compatible) and nunchaku (cu130 compatible) as checked.

- [ ] **Step 4: Commit**

```bash
git add src/gui/web/js/pages/environments.js src/gui/web/js/dialogs.js
git commit -m "feat(ui): AddonReinstallDialog for removed-then-eligible addons post-switch"
```

---

### Task 15: Settings page — "Addon Registry" tab (list view)

**Files:**
- Modify: `src/gui/web/js/pages/settings.js`
- Modify: `src/gui/web/css/tack-industrial.css`

- [ ] **Step 1: Find the tab system**

```bash
grep -n "tab\|subtab\|panel" src/gui/web/js/pages/settings.js | head -30
```

Identify how existing Settings tabs are registered.

- [ ] **Step 2: Register new tab "Addon Registry"**

Add a new tab definition following the existing pattern. The tab template:

```html
<section id="addon-registry-tab" class="settings-tab">
  <div class="registry-toolbar">
    <button class="btn-secondary" id="refresh-addons-remote">${t('addonRegistry.refreshRemote')}</button>
    <button class="btn-danger" id="restore-all-addons">${t('addonRegistry.restoreAllDefaults')}</button>
  </div>
  <div id="addon-registry-list" class="registry-list"></div>
  <div class="registry-footer muted">${t('addonRegistry.footerInfo')}</div>
</section>
```

- [ ] **Step 3: Render the list**

Inside the tab's activate/render function:

```js
async function renderAddonRegistryTab() {
  const payload = JSON.parse(bridge.list_addons_with_override_status());
  if (!payload.ok) {
    document.getElementById('addon-registry-list').textContent = payload.error || 'Error';
    return;
  }
  const html = payload.addons.map(a => `
    <div class="registry-row">
      <div class="meta">
        <span class="label">${a.label}</span>
        <span class="chip">${a.kind}</span>
        ${a.pack_pinned ? `<span class="chip pinned">${t('addonRegistry.packPinned')}</span>` : ''}
        ${a.has_override ? `<span class="dot-override" title="${t('addonRegistry.hasOverride')}">●</span>` : ''}
      </div>
      <button class="btn-edit-addon" data-addon="${a.id}">${t('addonRegistry.edit')}</button>
    </div>
  `).join('');
  document.getElementById('addon-registry-list').innerHTML = html;

  document.querySelectorAll('.btn-edit-addon').forEach(btn => {
    btn.onclick = () => openAddonEditor(btn.dataset.addon);
  });
  document.getElementById('refresh-addons-remote').onclick = async () => {
    const r = JSON.parse(bridge.refresh_addons_remote());
    if (r.ok) showInfoToast(t('addonRegistry.refreshSuccess'));
    else showErrorToast(t('addonRegistry.refreshFailed', { error: r.error }));
    await renderAddonRegistryTab();
  };
  document.getElementById('restore-all-addons').onclick = async () => {
    const ok = await showConfirmDialog({
      title: t('addonRegistry.restoreAllDefaults'),
      bodyHtml: t('addonRegistry.confirmRestoreAll'),
    });
    if (!ok) return;
    bridge.clear_addon_override('');
    await renderAddonRegistryTab();
  };
}

function openAddonEditor(addonId) {
  console.warn('openAddonEditor stub', addonId); // implemented in Task 16
}
```

- [ ] **Step 4: CSS**

Append to `tack-industrial.css`:

```css
.registry-toolbar { display: flex; gap: 0.5em; margin-bottom: 1em; }
.registry-list { display: flex; flex-direction: column; gap: 0.3em; }
.registry-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.5em; background: var(--panel-bg); border-radius: 4px;
}
.registry-row .meta { display: flex; align-items: center; gap: 0.6em; }
.registry-row .chip {
  font-size: 0.8em; padding: 0.1em 0.5em; border-radius: 3px;
  background: var(--chip-bg, #2a2a2a); color: var(--chip-fg, #ccc);
}
.registry-row .chip.pinned { background: #4a3a1a; color: #f0d060; }
.registry-row .dot-override { color: var(--accent, #40a0f0); }
.registry-footer { font-size: 0.85em; color: var(--muted-fg); margin-top: 1em; }
```

- [ ] **Step 5: Manual smoke**

Open Settings → Addon Registry tab. Expect 4 rows (sage-attention, insightface, nunchaku, trellis2) with kind chips and pack-pinned chips where applicable.

- [ ] **Step 6: Commit**

```bash
git add src/gui/web/js/pages/settings.js src/gui/web/css/tack-industrial.css
git commit -m "feat(ui): Settings 'Addon Registry' tab with list + refresh + restore-all"
```

---

### Task 16: Settings page — Addon editor dialog

**Files:**
- Modify: `src/gui/web/js/pages/settings.js`

- [ ] **Step 1: Replace `openAddonEditor` stub**

```js
async function openAddonEditor(addonId) {
  const viewResp = JSON.parse(bridge.get_addon_for_edit(addonId));
  if (!viewResp.ok) { showErrorToast(viewResp.error); return; }
  const allPacks = JSON.parse(bridge.list_torch_packs()).packs || [];
  const { shipped, override, effective } = viewResp;

  const effectiveCompat = effective.compatible_packs || [];
  const effectiveWheels = effective.wheels_by_pack || {};

  const isPip = shipped.kind === 'pip';

  const packRowsHtml = allPacks.map(p => `
    <label class="pack-row">
      <input type="checkbox" data-pack="${p.id}" ${effectiveCompat.includes(p.id) ? 'checked' : ''} />
      ${p.label}
    </label>
  `).join('');

  const unknownPacks = effectiveCompat.filter(id => !allPacks.some(p => p.id === id));
  const unknownHtml = unknownPacks.map(id => `
    <label class="pack-row unknown">
      <input type="checkbox" data-pack="${id}" checked disabled />
      ${id} <span class="muted">${t('addonRegistry.unknownPack')}</span>
    </label>
  `).join('');

  const dialog = document.createElement('div');
  dialog.className = 'modal-backdrop';
  dialog.innerHTML = `
    <div class="modal">
      <h2>${t('addonRegistry.editorTitle', { label: shipped.label })}</h2>
      <div class="modal-body">
        <div class="section-header">${t('addonRegistry.compatiblePacksHeader')}</div>
        <div class="pack-list">${packRowsHtml}${unknownHtml}</div>
        ${isPip ? `
          <div class="section-header">${t('addonRegistry.wheelsHeader')}</div>
          <div class="wheel-list" id="wheel-list"></div>
        ` : ''}
      </div>
      <div class="modal-footer">
        <button class="btn-cancel">${t('addonRegistry.cancel')}</button>
        <button class="btn-restore">${t('addonRegistry.restoreAddonDefaults')}</button>
        <button class="btn-save">${t('addonRegistry.save')}</button>
      </div>
    </div>
  `;
  document.body.appendChild(dialog);

  function renderWheelInputs() {
    if (!isPip) return;
    const container = dialog.querySelector('#wheel-list');
    const checked = Array.from(dialog.querySelectorAll('input[type=checkbox][data-pack]:checked'))
      .map(c => c.dataset.pack);
    container.innerHTML = checked.map(pid => {
      const label = (allPacks.find(p => p.id === pid) || { label: pid }).label;
      const url = effectiveWheels[pid] || '';
      const warn = url === '' ? `<span class="wheel-warn">⚠ ${t('addonRegistry.noWheelWarning')}</span>` : '';
      return `
        <div class="wheel-row">
          <div class="wheel-label">${label}</div>
          <input type="text" data-pack="${pid}" value="${url.replace(/"/g, '&quot;')}" placeholder="https://..." />
          ${warn}
        </div>
      `;
    }).join('');
    // Re-bind validate-on-input
    container.querySelectorAll('input[type=text]').forEach(inp => {
      inp.oninput = () => validateInline(inp);
    });
  }

  function validateInline(inp) {
    const v = inp.value.trim();
    inp.classList.toggle('error', v !== '' && !/^https?:\/\//.test(v));
  }

  renderWheelInputs();
  dialog.querySelectorAll('input[type=checkbox][data-pack]:not([disabled])').forEach(cb => {
    cb.onchange = renderWheelInputs;
  });

  dialog.querySelector('.btn-cancel').onclick = () => dialog.remove();

  dialog.querySelector('.btn-restore').onclick = async () => {
    bridge.clear_addon_override(addonId);
    dialog.remove();
    await renderAddonRegistryTab();
  };

  dialog.querySelector('.btn-save').onclick = async () => {
    // Collect
    const checked = Array.from(dialog.querySelectorAll('input[type=checkbox][data-pack]:checked'))
      .map(c => c.dataset.pack);
    const wheelInputs = Array.from(dialog.querySelectorAll('.wheel-row input[type=text]'));

    // Validate URL format
    for (const inp of wheelInputs) {
      const v = inp.value.trim();
      if (v !== '' && !/^https?:\/\//.test(v)) {
        showErrorToast(t('addonRegistry.invalidUrlError'));
        return;
      }
    }

    // Confirm empty packs
    if (checked.length === 0) {
      const ok = await showConfirmDialog({ title: '', bodyHtml: t('addonRegistry.confirmEmptyPacks') });
      if (!ok) return;
    }

    // Confirm PyPI fallback
    if (isPip) {
      const emptyUrls = wheelInputs.filter(i => i.value.trim() === '').map(i => {
        return (allPacks.find(p => p.id === i.dataset.pack) || { label: i.dataset.pack }).label;
      });
      if (emptyUrls.length > 0) {
        const ok = await showConfirmDialog({
          title: '', bodyHtml: t('addonRegistry.confirmPyPIFallback', { list: emptyUrls.join(', ') }),
        });
        if (!ok) return;
      }
    }

    // Build partial override: only changed fields
    const shippedCompat = shipped.compatible_packs || [];
    const shippedWheels = shipped.wheels_by_pack || {};
    const partial = {};
    if (!arrayEq(shippedCompat, checked)) {
      partial.compatible_packs = checked;
    }
    if (isPip) {
      const currentWheels = {};
      for (const inp of wheelInputs) {
        const v = inp.value.trim();
        if (v !== '') currentWheels[inp.dataset.pack] = v;
      }
      // Only persist wheels that differ from shipped
      const diff = {};
      for (const [k, v] of Object.entries(currentWheels)) {
        if (shippedWheels[k] !== v) diff[k] = v;
      }
      if (Object.keys(diff).length > 0) partial.wheels_by_pack = diff;
    }

    if (Object.keys(partial).length === 0) {
      // No diff — clear this addon's override
      bridge.clear_addon_override(addonId);
    } else {
      const r = JSON.parse(bridge.save_addon_override(addonId, JSON.stringify(partial)));
      if (!r.ok) { showErrorToast(r.error); return; }
    }
    dialog.remove();
    await renderAddonRegistryTab();
  };
}

function arrayEq(a, b) {
  if (a.length !== b.length) return false;
  const sa = [...a].sort(), sb = [...b].sort();
  return sa.every((x, i) => x === sb[i]);
}
```

- [ ] **Step 2: CSS**

Append to `tack-industrial.css`:

```css
.pack-list { display: flex; flex-direction: column; gap: 0.3em; margin-bottom: 1em; }
.pack-row { display: flex; gap: 0.5em; align-items: center; }
.pack-row.unknown { color: var(--muted-fg); }
.wheel-list { display: flex; flex-direction: column; gap: 0.5em; }
.wheel-row { display: flex; flex-direction: column; gap: 0.2em; }
.wheel-row .wheel-label { font-size: 0.9em; color: var(--muted-fg); }
.wheel-row input[type=text] {
  padding: 0.4em; font-family: monospace; font-size: 0.9em;
  background: var(--input-bg); border: 1px solid var(--border); color: var(--fg);
}
.wheel-row input.error { border-color: #e05050; }
.wheel-warn { color: #e0b040; font-size: 0.85em; }
```

- [ ] **Step 3: Manual smoke**

Click "Edit" on sage-attention: all 3 Packs checked; 3 wheel URL inputs filled. Uncheck cu130 → its URL input disappears. Save → dot badge appears on sage row.

- [ ] **Step 4: Commit**

```bash
git add src/gui/web/js/pages/settings.js src/gui/web/css/tack-industrial.css
git commit -m "feat(ui): Addon Registry editor dialog with compat/wheels and validation"
```

---

### Task 17: Version bump + changelog

**Files:**
- Modify: `VERSION.json`

- [ ] **Step 1: Replace VERSION.json contents**

```json
{
  "version": "0.5.0",
  "min_python": "3.10",
  "release_notes": "Add-on registry editor + one-click Pack switch for incompatible add-ons",
  "changes": [
    "新增 Add-on 不相容時「一鍵切換 Pack 並安裝」流程",
    "新增切換 Pack 後 add-on 重裝提示",
    "新增 Add-on Registry 編輯器(Settings 頁)——可自訂相容 Pack 與 wheel URL",
    "Add-on 定義改存 data/addons.json,支援遠端熱更新與使用者本地 override"
  ],
  "changes_i18n": {
    "en": [
      "Added one-click 'switch Pack and install' flow for add-ons incompatible with current env",
      "Added post-switch reinstall prompt for removed pack-pinned add-ons",
      "Added Add-on Registry editor (Settings page) — edit compatible packs and wheel URLs per add-on",
      "Add-on definitions moved to data/addons.json with remote refresh and local override support"
    ],
    "zh-TW": [
      "新增 Add-on 不相容時「一鍵切換 Pack 並安裝」流程",
      "新增切換 Pack 後 add-on 重裝提示",
      "新增 Add-on Registry 編輯器(Settings 頁)——可自訂相容 Pack 與 wheel URL",
      "Add-on 定義改存 data/addons.json,支援遠端熱更新與使用者本地 override"
    ]
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add VERSION.json
git commit -m "chore: bump to 0.5.0 — addon registry + one-click Pack switch"
```

---

### Task 18: Full regression — run whole test suite

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: all green (including existing + newly added).

- [ ] **Step 2: If any fail, fix inline**

If tests fail due to missed call-site refactors (e.g., tests instantiating `Addon` directly from `src.core.addons`), update the test imports to pull from `src.core.addon_registry` and rerun. Do not weaken assertions.

- [ ] **Step 3: Commit any fixes**

```bash
git add <fixed files>
git commit -m "test: fix call-sites after addons → addon_registry refactor"
```

---

### Task 19: Manual QA pass

- [ ] **Step 1: Launch app on a test env (cu130)**

```bash
python -m src.main
```

- [ ] **Step 2: Run through QA checklist** (see spec, section "Manual QA checklist")

Tick each box manually in a scratch doc. If any fails, open an issue or fix before release.

Items:
- [ ] Fresh cu130 env → Trellis 2.0 shows "Install (requires switching to PyTorch 2.8.0 + CUDA 12.8)"
- [ ] Click → side-effects dialog lists sage/nunchaku removal, ~15-30 min ETA + 20 min compile for trellis
- [ ] Confirm → single progress bar, label switches from "Stage 1/2: Switching Pack" to "Stage 2/2: Installing Trellis 2.0"
- [ ] After install, reinstall dialog appears listing sage + nunchaku (both cu128-compat), checked by default
- [ ] Uncheck nunchaku → button text updates to "Reinstall selected (1)"
- [ ] Skip → reinstall dialog closes, env returns to normal
- [ ] Open Settings → Addon Registry: see 4 rows with correct chips
- [ ] Edit sage-attention → uncheck cu130 → save → dot badge shows, cu130 env now shows sage as needs-switch
- [ ] Per-addon restore → badge disappears, cu130 compatibility back
- [ ] Top-level "Restore official defaults" → all customizations removed
- [ ] Corrupt `tools/addons_override.json` (paste garbage) → relaunch: tool loads without crash, shipped data served
- [ ] Set an invalid wheel URL in sage cu130 → attempt install on cu130 env → install fails; dialog offers Restore / Retry / Keep
- [ ] Click "Check for add-on updates" in registry tab → writes `tools/addons_remote.json` (verify file exists)

---

## Self-Review Notes (completed by author)

**Spec coverage:** All 4 Goals covered — Task 12-13 (one-click flow), Task 14 (reinstall prompt), Task 15-16 (editor), Task 2c + 2f (remote refresh). Partial-failure handling covered in Task 13. Orphan handling covered in Task 3 (unknown id branch in uninstall_addon) + Task 4 (orphan skip in switch_pack). VERSION.json bump in Task 17.

**Placeholder scan:** No "TBD" / "implement later" / "similar to Task N" — every task body contains concrete code/commands.

**Type consistency:** Addon dataclass lives in `src.core.addon_registry` after Task 2; all imports in Tasks 3, 4, 6 point there. Method names consistent: `list_addons`, `find`, `save_override`, `clear_override`, `has_override`, `get_shipped_and_override`, `get_remote_url`, `refresh_remote`. Bridge slot names match frontend call sites: `switch_pack_and_install_addon`, `reinstall_addons`, `list_addons_with_override_status`, `get_addon_for_edit`, `save_addon_override`, `clear_addon_override`, `refresh_addons_remote`.

**Gaps:** None identified. Frontend helper functions (`showConfirmDialog`, `showThreeButtonDialog`, `pollRequest`, `newRequestId`, etc.) are referenced assuming they exist in the current codebase from v0.4.0 work — if any are missing, worker must stub them from existing confirm-dialog patterns.
