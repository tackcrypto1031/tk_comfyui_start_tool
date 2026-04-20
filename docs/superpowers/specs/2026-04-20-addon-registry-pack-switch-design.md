# Addon Registry + One-Click Pack Switch (v0.5.0) — Design

**Date:** 2026-04-20
**Status:** Approved (brainstorming)
**Target version:** 0.5.0

## Problem

Today (v0.4.0), add-ons have a `compatible_packs` allow-list. When a user's env is on a non-matching Torch-Pack, the Trellis 2.0 option (and any other pack-restricted add-on) is silently hidden or rejected. The upstream inspiration — Tavris1/ComfyUI-Easy-Install — instead lets the user switch the env's Torch+CUDA combo from the Torch-Pack page, then install the add-on. We want that workflow, plus the ability to edit the add-on↔pack mapping over time (new wheels, new packs, URL corrections) without releasing a new tool version.

## Goals

1. **One-click switch-and-install.** When a user picks an add-on that's incompatible with their current Pack, the UI surfaces "Install (requires switching to Pack X)"; confirmation shows side-effects (snapshot, removed pack-pinned add-ons, ETA); the tool performs both steps.
2. **Post-switch reinstall prompt.** After a Pack switch removes other pack-pinned add-ons, prompt the user to re-install those that remain compatible on the new Pack.
3. **Editable registry (Settings UI).** A Settings tab "Addon Registry" lets users edit `compatible_packs` and `wheels_by_pack` per add-on. Edits persist as an override that survives tool upgrades.
4. **Remote-refreshable registry.** Like `torch_packs.json`, the shipped JSON can be refreshed from a remote URL so hot-fixing wheel URLs doesn't require a tool release.

## Non-goals

- Full CRUD for add-ons in the GUI (add / delete / edit non-mapping fields). File-level edits still possible via direct `data/addons.json` edits.
- Import/export/share of override sets.
- Per-field three-way merge between shipped, remote, override (we use simple override-beats-remote-beats-shipped).
- E2E Playwright tests for the new UI. Manual QA checklist only.
- Retroactive rollback of partial failures (the user is given a recover-from-snapshot option instead).

## Architecture

### Data model

Add-on definitions move from `src/core/addons.py` (Python `ADDONS` list) to `data/addons.json` (shipped), with a three-layer lookup:

```
override (tools/addons_override.json, per-addon partial fields)
    ▼
remote  (tools/addons_remote.json, whole file fetched from remote_url)
    ▼
shipped (data/addons.json, committed to repo)
```

**Shipped / remote format** (`data/addons.json`):

```json
{
  "schema_version": 1,
  "last_updated": "2026-04-20",
  "remote_url": "https://raw.githubusercontent.com/tackcrypto1031/tk_comfyui_start_tool/master/data/addons.json",
  "addons": [
    {
      "id": "trellis2",
      "label": "Trellis 2.0",
      "description": "3D generation nodes",
      "kind": "custom_node",
      "compatible_packs": ["torch-2.8.0-cu128"],
      "source_repo": "https://github.com/microsoft/TRELLIS.2.git",
      "source_ref": "main",
      "source_post_install": ["pip", "install", "-r", "requirements.txt"],
      "requires_compile": true,
      "pack_pinned": true,
      "risk_note": "..."
    },
    {
      "id": "sage-attention",
      "label": "SageAttention v2.2.0",
      "description": "Attention acceleration — larger batch, lower VRAM",
      "kind": "pip",
      "compatible_packs": ["torch-2.9.1-cu130", "torch-2.8.0-cu128", "torch-2.7.1-cu128"],
      "wheels_by_pack": {
        "torch-2.9.1-cu130": "https://.../cu130torch2.9.0...whl",
        "torch-2.8.0-cu128": "https://.../cu128torch2.8.0...whl",
        "torch-2.7.1-cu128": "https://.../cu128torch2.7.1...whl"
      },
      "pip_project_name": "sageattention",
      "pack_pinned": true,
      "risk_note": "..."
    }
  ]
}
```

**Override format** (`tools/addons_override.json`) — partial fields per addon id, merged field-by-field:

```json
{
  "schema_version": 1,
  "overrides": {
    "trellis2": {
      "compatible_packs": ["torch-2.8.0-cu128", "torch-2.9.1-cu130"]
    },
    "sage-attention": {
      "wheels_by_pack": {
        "torch-2.9.1-cu130": "https://my-mirror/sage...whl"
      }
    }
  }
}
```

Field-level merge rules:
- `compatible_packs`: override replaces shipped entirely (list semantics).
- `wheels_by_pack`: override is a partial dict; override keys replace shipped keys, other shipped keys preserved.
- Other fields (label, description, source_repo, etc.) not editable in v0.5.0 GUI and not written into override.

### New module: `src/core/addon_registry.py`

```python
class AddonRegistry:
    def __init__(
        self,
        shipped_path: Path,
        remote_path: Path,
        override_path: Path,
    ): ...

    def list_addons(self) -> list[Addon]: ...        # all, merged
    def find(self, addon_id: str) -> Optional[Addon]  # merged, or None
    def get_remote_url(self) -> str
    def refresh_remote(self, timeout: int = 15) -> dict  # {ok, error}

    def has_override(self, addon_id: str) -> bool
    def get_shipped_and_override(self, addon_id: str) -> dict:
        # {"shipped": {...}, "override": {...}, "effective": {...}}
    def save_override(self, addon_id: str, partial_fields: dict) -> None
    def clear_override(self, addon_id: Optional[str] = None) -> None
    # clear_override(None) → wipes entire overrides map; per-id otherwise.
```

Caching: memoize the merged load; invalidate in `save_override`, `clear_override`, `refresh_remote`.

Orphan tolerance (Q4):
- `find(id)` returning `None` is a normal outcome. All callers must handle.
- `list_addons()` does NOT include orphan `installed_addons` entries — those are reconciled in the UI layer against `env.installed_addons`.

### Changes to `src/core/addons.py`

- Delete module-level `ADDONS: list[Addon]` constant.
- Keep `@dataclass Addon` definition (now used by `AddonRegistry` to materialize entries).
- `find_addon(addon_id)` → shim that builds a registry with defaults and queries it, OR remove and have callers pass a registry. Prefer:
  - `install_addon`, `uninstall_addon` gain `registry: AddonRegistry` parameter (DI-clean), OR accept `config: dict` and build their own registry internally. We choose **the latter** for minimal caller-site churn (callers already have config).
- `IncompatiblePackError` unchanged.

### Changes to `src/core/torch_pack.py`

- `switch_pack()` currently imports `find_addon` from `src.core.addons`. Rewire to instantiate `AddonRegistry` and call `registry.find(...)`. Return shape unchanged.
- Orphan tolerance: if `env.installed_addons` contains an id that `registry.find()` returns `None` for, skip it (don't treat as pack-pinned; the underlying dir / package may or may not exist, user can clean up via UI).

### Changes to `src/core/migrations.py`

- Replace `from src.core.addons import ADDONS` with registry-based lookup (or inline the set of known ids — this file's purpose is 0.4.0 backfill, gated by marker, and won't re-run).
- **No new migration** for 0.5.0: the shipped `data/addons.json` is committed into the repo (Q3 decision A), so fresh installs and upgrades both see the JSON from disk.

### Bridge (`src/gui/bridge.py`) — new slots

| Slot | Signature | Purpose |
|---|---|---|
| `list_addons_with_override_status` | `() -> str` (JSON) | For Addon Registry tab: returns `[{id, label, kind, pack_pinned, has_override, effective: {...}}, ...]` |
| `get_addon_for_edit` | `(str addon_id) -> str` (JSON) | Editor opens: returns `{shipped, override, effective}` for form init |
| `save_addon_override` | `(str addon_id, str fields_json) -> str` (JSON) | Writes partial override; returns `{ok, error}` |
| `clear_addon_override` | `(str addon_id_or_empty) -> str` (JSON) | Empty string → wipe all overrides; returns `{ok, error}` |
| `refresh_addons_remote` | `() -> str` (JSON) | Pulls remote addons.json; returns `{ok, error}` |
| `switch_pack_and_install_addon` | `(str env_name, str target_pack_id, str addon_id) -> str` (JSON) | Combined 3-stage flow; returns `{ok, removed_addons, installed_addon, error, failed_at}` where `failed_at ∈ {"switch", "install"}` |
| `reinstall_addons` | `(str env_name, QVariantList addon_ids) -> str` (JSON) | Post-switch batch; returns `{results: [{id, ok, error}]}` |

### Frontend (`src/gui/web/js/pages/environments.js`)

**Addon card states** (computed per card given `env.torch_pack`):

| State | Condition | Button |
|---|---|---|
| Installed | `id in env.installed_addons[*].id` | "Uninstall" |
| Compatible | `current_pack ∈ addon.compatible_packs` | "Install" |
| Needs-switch | `current_pack ∉ addon.compatible_packs` AND `addon.compatible_packs` non-empty | "Install (requires switching to **{recommended Pack label}**)" |
| Incompatible | `addon.compatible_packs` empty | Disabled "Not compatible" |

**Recommended Pack selection** (Q6):
1. Read cached GPU info from bridge (already exposed).
2. Call `select_pack_for_gpu(gpu_info)` semantics **restricted to `addon.compatible_packs`** — find packs whose `min_driver ≤ driver` and prefer `recommended=true`, then lower `min_driver`.
3. If GPU-scoped selection fails, fall back to first entry in `compatible_packs`.

**Needs-switch click flow:**

```
click → AddonSwitchInstallDialog
  ├─ header: env name, current Pack, target Pack
  ├─ bullet list of side-effects:
  │   • Auto-snapshot
  │   • Reinstall PyTorch trio
  │   • Re-apply global pinned deps
  │   • Remove pack-pinned add-ons: {list}
  │   • Install {target addon}
  ├─ ETA text (15-30 min baseline, +20 min for requires_compile add-ons)
  ├─ risk_note(s) shown as warning box
  └─ [Cancel] [Start switch and install]
       ↓
  bridge.switch_pack_and_install_addon(env, pack, addon)
  progress bar: single bar, 2 labeled stages (0-60% switch, 60-100% install)
       ↓
  result:
    ok=true → AddonReinstallDialog (if eligible removed_addons)
    ok=false, failed_at="switch" → error dialog, no recovery needed (switch atomic enough)
    ok=false, failed_at="install" → error dialog with:
         [Restore from snapshot] [Retry install] [Keep current state]
```

**AddonReinstallDialog:**

Shown when `switch_pack_and_install_addon` succeeds AND:
```
eligible = removed_addons.filter(id =>
  id !== justInstalledAddonId AND
  registry.find(id)?.compatible_packs.includes(newPackId)
)
```
Lists eligible add-ons as checkboxes (default checked), with label + description.
`[Skip]` / `[Reinstall checked (N)]` → `bridge.reinstall_addons(env, ids)` → toast summary.

**Progress reporting** (Q5):
- Bridge emits `progress(step, pct, detail)` already (from `torch_pack.switch_pack`).
- Wrap in `switch_pack_and_install_addon`:
  - Stage 1 (switch): pass raw pct through, scaled to 0-60%.
  - Stage 2 (install): bridge emits `progress("install", 60, "Installing ...")` on start, then whatever the addon install callback produces, bumped to 60-100%.
- UI progress bar shows "Stage 1/2: Switching Pack" / "Stage 2/2: Installing {addon}" label above the bar.

### Settings page (`src/gui/web/js/pages/settings.js`) — new tab "Addon Registry"

**Tab layout:**

- Top bar: `[Restore official defaults]` button (wipes all overrides after confirm).
- Add-on list: one row per add-on, showing `label (kind, [pack-pinned])`, `●` marker if has_override, `[Edit]` button.
- Footer info: "Editing here creates local overrides. To add new add-ons, edit `data/addons.json` directly."

**Editor dialog (per add-on):**

- Header: `{label}`
- **Compatible Packs** section: checkbox list generated from `torch_packs.json`'s pack list.
  - Packs in effective `compatible_packs` are checked.
  - Packs present in `compatible_packs` but NOT in `torch_packs.json` show as checked + greyed with "(unknown Pack)" — can be unchecked, cannot re-check.
- **Wheel URLs** section (`kind=pip` only): one input per checked Pack.
  - Current value from effective `wheels_by_pack[pack_id]` (empty if missing).
  - Inline warning `⚠ No URL — will fall back to PyPI (pip_spec)` when empty.
  - Format validation: if non-empty, must match `^https?://`.
- **Buttons:** `[Cancel] [Restore this add-on's defaults] [Save]`

**Save validation (Q6):**

| Condition | Action |
|---|---|
| URL non-empty but not `^https?://` | Block save, inline red error |
| Empty compatible_packs | Confirm dialog "This add-on will be uninstallable. Continue?" |
| Any pip pack without URL | Confirm dialog "The following Packs will fall back to PyPI: [...]. Continue?" |

**Save builds the partial override:**
- Only persist fields that differ from shipped.
- If no differences remain after edit, delete this add-on's entry from override (equivalent to per-addon restore).

### File layout

```
data/
  torch_packs.json      (existing)
  addons.json           (NEW — shipped addon registry, ~5 entries)
tools/
  torch_packs_remote.json   (existing, optional)
  addons_remote.json        (NEW, optional, fetched on refresh)
  addons_override.json      (NEW, optional, user overrides)
src/core/
  addons.py             (modified: drop ADDONS constant, use registry)
  addon_registry.py     (NEW)
  torch_pack.py         (modified: use registry, not direct find_addon import)
  migrations.py         (modified: drop ADDONS import)
src/gui/
  bridge.py             (modified: add 7 new slots)
  web/js/pages/
    environments.js     (modified: needs-switch state, 2 new dialogs, progress stages)
    settings.js         (modified: Addon Registry tab)
  web/js/i18n.js        (modified: addonRegistry.* keys, addonSwitch.* keys)
  web/css/tack-industrial.css (modified: needs-switch button style, editor layout)
tests/test_core/
  test_addon_registry.py    (NEW)
  test_addons.py            (extended)
  test_torch_pack.py        (extended)
  test_migrations.py        (adjust if import changes)
tests/test_gui/
  test_bridge.py            (extended)
VERSION.json             (0.4.0 → 0.5.0)
```

### VERSION.json bump

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

## Partial failure handling (Q1)

`switch_pack_and_install_addon` returns `failed_at` so the UI can react:

| `failed_at` | Env state | UX |
|---|---|---|
| `"switch"` | Still on old Pack (switch didn't commit env_meta changes) | Simple error toast, no recovery needed |
| `"install"` | On new Pack, original pack-pinned add-ons removed, target add-on not installed | Error dialog: `[Restore from snapshot] [Retry install] [Keep current]` |

`[Restore from snapshot]` → calls existing `SnapshotManager.restore_snapshot` with the latest pre-switch snapshot. This reverts the env_meta, venv, and custom_nodes.

`[Retry install]` → calls `bridge.install_addon(env, addon_id)` directly (no pack switch needed — we're already on the target Pack). If still fails, same dialog reappears.

`[Keep current]` → closes dialog. Env stays on new Pack without target add-on. Post-switch reinstall prompt still appears for removed_addons (since switch itself succeeded).

## Orphan handling (Q4)

| Case | Behavior |
|---|---|
| Addon's `compatible_packs` contains a pack id not in `torch_packs.json` | Registry tab: checkbox shown greyed as `(unknown Pack)`, uncheckable only. Install flow: filtered out when computing recommended Pack. |
| `env.torch_pack` not in `torch_packs.json` | Versions page / env detail: show raw id with `(not in registry)` suffix. Install flow: treat every addon as incompatible (no compatible pack matches unknown id), all cards show `needs-switch` state targeting the best Pack for the GPU. |
| `env.installed_addons[*].id` not in registry | Addon card: renders as `? Unknown add-on (id=...)`, only action is "Uninstall" which performs generic cleanup: `rm -rf ComfyUI/custom_nodes/<id>` + remove meta entry. No pip uninstall (pip_project_name unknown). |

## Testing strategy (Q7)

### `tests/test_core/test_addon_registry.py` (new)

- `test_load_shipped_only` — no remote, no override; `list_addons` returns shipped entries.
- `test_remote_overrides_shipped` — remote file present, schema matches; remote entries win.
- `test_remote_schema_mismatch_falls_back_to_shipped` — schema_version wrong → shipped used, warning logged.
- `test_override_merges_compatible_packs` — override replaces field entirely.
- `test_override_merges_wheels_by_pack_partial` — override adds one URL, shipped URLs for other packs preserved.
- `test_save_override_writes_json_and_invalidates_cache`
- `test_clear_override_single_id`
- `test_clear_override_all`
- `test_find_returns_none_for_unknown_id`
- `test_has_override_false_when_addon_absent_from_override_map`
- `test_refresh_remote_bad_schema_returns_error_does_not_write_file`
- `test_get_shipped_and_override_returns_three_views`

### `tests/test_core/test_addons.py` (extend)

- `test_install_addon_uses_registry_for_lookup` — patch registry, verify `find` called.
- `test_install_addon_unknown_id_raises_value_error` — returns None from registry.
- `test_install_addon_incompatible_pack_raises` — existing, re-check with override-based compatible_packs.

### `tests/test_core/test_torch_pack.py` (extend)

- `test_switch_pack_uses_registry_for_pack_pinned_detection`
- `test_switch_pack_orphan_installed_addon_skipped` — env has id not in registry → not treated as compiled, not blocked.

### `tests/test_gui/test_bridge.py` (extend)

- `test_switch_pack_and_install_addon_calls_both_in_order` (mock core).
- `test_switch_pack_and_install_addon_failed_switch_returns_failed_at_switch`.
- `test_switch_pack_and_install_addon_failed_install_returns_failed_at_install` — switch result still reported (removed_addons).
- `test_reinstall_addons_partial_failure` — mixed success/failure per id.
- `test_save_addon_override_validates_schema`.

### Manual QA checklist (tracked in PLAN.md)

- [ ] Create fresh env on cu130; try to install Trellis 2.0 → switch dialog appears, target Pack label shows "PyTorch 2.8.0 + CUDA 12.8".
- [ ] Confirm dialog → progress bar runs both stages → reinstall prompt shown for removed sage/nunchaku.
- [ ] Edit sage-attention in Addon Registry: uncheck cu130 → install button on cu130 env now shows "needs switch".
- [ ] Click "Restore this add-on's defaults" → cu130 checkbox back, reflects in env list.
- [ ] Click top-level "Restore official defaults" → all overrides wiped, `tools/addons_override.json` empty or deleted.
- [ ] Corrupt `tools/addons_override.json` manually → tool launches with warning, falls back to shipped.
- [ ] Simulate install failure (invalid wheel URL in override) → error dialog shows Restore / Retry / Keep buttons.
- [ ] Fresh install on new machine (no `tools/` dir) → addons load from shipped.
- [ ] Trigger "Refresh add-on registry" (menu in Settings tab) → remote cache file written, entries update without relaunch.

## Out-of-scope / deferred

- Add-on CRUD in GUI.
- Import/export of override sets (deferred — could come in 0.6.x if community-share is desired).
- Auto-detection of orphan Pack references on startup (user is informed only when they interact).
- Progress percentage inside individual addon install (only stage label shown for now).
- Undo for override edits (user can hit "Restore defaults" but no per-edit history).
