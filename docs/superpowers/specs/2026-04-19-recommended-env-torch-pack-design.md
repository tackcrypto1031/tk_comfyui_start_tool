# Recommended Environment Creation + Torch-Pack Switcher

**Date:** 2026-04-19
**Branch:** `claude/objective-turing-73d67e` (worktree)
**Target version:** 0.4.0
**Scope:** Environment creation flow, PyTorch version switcher, optional curated add-ons, uv migration.

---

## 1. Motivation

The current environment creation flow exposes too many choices (Python version, CUDA tag, PyTorch version) to the user and has produced brittle installs because dependency resolution is not constrained tightly. [ComfyUI-Easy-Install](https://github.com/Tavris1/ComfyUI-Easy-Install) has demonstrated a more stable approach: fixed tested combinations of Python + PyTorch + CUDA ("Torch-Packs"), `uv` for fast strict installs, inline pinning of a few fragile dependencies, and a curated set of optional compiled add-ons.

This spec adopts that approach as the default recommended creation flow while preserving the existing advanced flow intact.

## 2. Goals

1. A recommended creation flow with near-zero decisions (name + optional add-on checkboxes).
2. A Torch-Pack mechanism for post-install switching between tested PyTorch combinations.
3. A curated "Add-on" registry for compiled nodes that boost ComfyUI capability (SageAttention, FlashAttention, InsightFace, Nunchaku, Trellis 2).
4. Migration of `pip` → `uv` for all package operations.
5. Backwards compatibility with existing environments — they continue to run, and get backfilled `torch_pack` metadata where possible.

## 3. Non-Goals

- No removal or deprecation of the existing advanced creation flow.
- No automatic rebuild of compiled add-ons across Pack switches (we uninstall + prompt to reinstall).
- No batch Torch-Pack switch across multiple environments (single-env only in this release).
- No install-time choice of which Torch-Pack to use (recommended mode auto-selects from GPU).
- No changes to snapshot, version controller (ComfyUI git switching), conflict analyzer, or launcher beyond what's needed to wire new data in.

## 4. High-Level Architecture

### New modules

| File | Responsibility |
|---|---|
| `src/core/torch_pack.py` | `TorchPackManager` — load `torch_packs.json`, GPU → Pack mapping, remote refresh, switch Pack on an env |
| `src/core/addons.py` | `AddonRegistry` — curated list, install/uninstall individual add-on, determine `requires_compile` |
| `src/utils/uv_ops.py` | uv binary management (download, invoke) and uv-equivalents of pip operations |
| `data/torch_packs.json` | Shipped defaults for Packs + global `pinned_deps` + remote URL |

### Modified modules

| File | Change |
|---|---|
| `src/core/env_manager.py` | New `create_recommended(name, selected_addon_ids, progress_callback)`; existing `create_environment()` retained for advanced; extract shared low-level helpers (`_install_torch_pack`, `_install_pinned_deps`, `_install_addons`) |
| `src/core/version_manager.py` | `reinstall_pytorch()` becomes a thin wrapper around the new `torch_pack.switch_pack()` path for Pack-matched targets; free-form reinstall path retained for advanced use |
| `src/models/environment.py` | Add `torch_pack: Optional[str]`, `installed_addons: list[dict]` |
| `src/utils/pip_ops.py` | Keep pip helpers; wrap with package-manager dispatch so callers go through `uv_ops` by default |
| `src/gui/bridge.py` | Add `create_recommended_env`, `list_torch_packs`, `refresh_torch_packs`, `switch_torch_pack`, `list_addons`, `install_addon`, `uninstall_addon`, `detect_gpu_for_recommended` |
| `src/gui/web/js/pages/env.js` | Redesigned create dialog: recommended card (name + add-on checklist + create) with collapsible advanced section |
| `src/gui/web/js/pages/versions.js` | New "PyTorch" sub-tab with Pack switcher |
| `config.json` | Add `package_manager: "uv" \| "pip"` (default `"uv"`) |
| `VERSION.json` | Bump to `0.4.0` with changelog entries |
| `install.bat` | Unchanged by this spec (bundled Python 3.12.8 stays); recommended mode downloads 3.12.10 on demand |

### Untouched modules

- `src/core/snapshot_manager.py` (auto-snapshots still happen before clone/merge/switch)
- `src/core/conflict_analyzer.py`
- `src/core/comfyui_launcher.py`
- `src/core/version_controller.py` (ComfyUI git tag/branch switching)

## 5. Data Model

### `data/torch_packs.json` (shipped)

```json
{
  "schema_version": 1,
  "last_updated": "2026-04-19",
  "remote_url": "https://raw.githubusercontent.com/tackcrypto1031/tk_comfyui_start_tool/master/data/torch_packs.json",
  "recommended_python": "3.12.10",
  "recommended_uv_version": "0.9.7",
  "packs": [
    {
      "id": "torch-2.9.1-cu130",
      "label": "PyTorch 2.9.1 + CUDA 13.0 (Latest)",
      "torch": "2.9.1",
      "torchvision": "0.24.1",
      "torchaudio": "2.9.1",
      "cuda_tag": "cu130",
      "min_driver": 13.0,
      "recommended": true
    },
    {
      "id": "torch-2.8.0-cu128",
      "label": "PyTorch 2.8.0 + CUDA 12.8 (Stable Fallback)",
      "torch": "2.8.0",
      "torchvision": "0.23.0",
      "torchaudio": "2.8.0",
      "cuda_tag": "cu128",
      "min_driver": 12.8,
      "recommended": false
    },
    {
      "id": "torch-2.7.1-cu128",
      "label": "PyTorch 2.7.1 + CUDA 12.8 (Compat)",
      "torch": "2.7.1",
      "torchvision": "0.22.1",
      "torchaudio": "2.7.1",
      "cuda_tag": "cu128",
      "min_driver": 12.8,
      "recommended": false
    }
  ],
  "pinned_deps": {
    "av": "16.0.1",
    "transformers": "4.57.6",
    "stringzilla": "3.12.6"
  }
}
```

### Remote refresh

- Refresh pulls JSON from `remote_url` and writes to `tools/torch_packs_remote.json` (never overwrites shipped `data/torch_packs.json`).
- Read precedence at runtime: `tools/torch_packs_remote.json` → `data/torch_packs.json`.
- Remote refresh failures are non-fatal; user sees a banner error and falls back to shipped defaults.
- `schema_version` mismatch → ignore remote and use shipped.

### `env_meta.json` new fields

```python
@dataclass
class Environment:
    # ... existing fields ...
    torch_pack: Optional[str] = None          # Pack id, or None if advanced/custom build
    installed_addons: list[dict] = field(default_factory=list)
    # Each entry: {
    #   "id": "sage-attention",
    #   "installed_at": "2026-04-19T10:00:00Z",
    #   "torch_pack_at_install": "torch-2.9.1-cu130"  # Pack at install time
    # }
```

### `config.json` additions

```json
{
  "package_manager": "uv"
}
```

When set to `"pip"` the tool uses legacy pip paths throughout.

## 6. Torch-Pack Logic

### GPU → Pack selection (recommended mode)

```python
def select_pack_for_gpu(packs, gpu_info) -> Optional[Pack]:
    if not gpu_info["has_gpu"]:
        return None
    try:
        driver = float(gpu_info["cuda_driver_version"])
    except (ValueError, KeyError):
        return None
    # Prefer packs marked recommended; within that, prefer higher min_driver
    candidates = sorted(
        packs,
        key=lambda p: (not p.recommended, -p.min_driver),
    )
    for p in candidates:
        if driver >= p.min_driver:
            return p
    return None
```

**Behavior:**
- driver ≥ 13.0 → `torch-2.9.1-cu130`
- 12.8 ≤ driver < 13.0 → `torch-2.8.0-cu128`
- driver < 12.8 or no GPU or detection failure → returns `None`; recommended mode blocks and directs to advanced
- `torch-2.7.1-cu128` is never auto-selected; it is available only via Advanced / manual switch

### Pack switch flow

```
1. Auto-snapshot target env (existing snapshot_manager call)
2. Identify compiled add-ons in env (via installed_addons + Registry lookup)
3. If any compiled add-ons:
     Show modal: "Switching Pack will uninstall the following compiled add-ons:
                  [SageAttention, FlashAttention]
                  After the switch you can reinstall them.
                  [Cancel] [Continue]"
     On Continue:
       - uv pip uninstall <addon packages>
       - rmtree custom_nodes/<addon_dir>
       - Remove from env.installed_addons
4. uv pip uninstall torch torchvision torchaudio
5. uv pip install torch==X torchvision==Y torchaudio==Z --index-url {cuda_tag}
6. Re-apply pinned_deps: uv pip install av==... transformers==... stringzilla==...
7. Update env_meta: torch_pack = new_pack_id
8. On success, show modal: "Pack switched. Reinstall these add-ons now? [Later] [Install]"
9. On Install: run install_addon() for each uninstalled add-on
```

Failure mid-flow (steps 4–6): snapshot is available for rollback. Env is left in whatever state it reached; UI shows error with snapshot id and a restore button.

## 7. Add-on Registry

### Data

`src/core/addons.py` defines hardcoded registry:

```python
@dataclass(frozen=True)
class Addon:
    id: str
    label: str
    description: str
    install_method: Literal["pip_package", "git_clone"]
    pip_package: Optional[str] = None        # for pip_package
    repo: Optional[str] = None               # for git_clone
    post_install_cmd: Optional[list[str]] = None
    requires_cuda: bool = False
    requires_compile: bool = False
    risk_note: Optional[str] = None

ADDONS = [
    Addon(
        id="sage-attention",
        label="SageAttention v2",
        description="注意力加速 — 支援更大 batch、更低 VRAM",
        install_method="git_clone",
        repo="https://github.com/thu-ml/SageAttention.git",
        post_install_cmd=["pip", "install", "-e", "."],
        requires_cuda=True,
        requires_compile=True,
        risk_note="需要 CUDA toolkit(nvcc),初次安裝編譯較久",
    ),
    Addon(
        id="flash-attention",
        label="FlashAttention",
        description="快速注意力實作",
        install_method="git_clone",
        repo="https://github.com/Dao-AILab/flash-attention.git",
        post_install_cmd=["pip", "install", "-e", ".", "--no-build-isolation"],
        requires_cuda=True,
        requires_compile=True,
    ),
    Addon(
        id="insightface",
        label="InsightFace",
        description="人臉辨識節點(IPAdapter FaceID、ReActor)",
        install_method="pip_package",
        pip_package="insightface",
        requires_cuda=False,
        requires_compile=False,
    ),
    Addon(
        id="nunchaku",
        label="Nunchaku",
        description="量化推理加速(4-bit FLUX 等)",
        install_method="git_clone",
        repo="https://github.com/mit-han-lab/nunchaku.git",
        post_install_cmd=["pip", "install", "-e", "."],
        requires_cuda=True,
        requires_compile=True,
    ),
    Addon(
        id="trellis2",
        label="Trellis 2.0",
        description="3D 模型生成節點",
        install_method="git_clone",
        repo="https://github.com/microsoft/TRELLIS.git",
        post_install_cmd=["pip", "install", "-r", "requirements.txt"],
        requires_cuda=True,
        requires_compile=True,
    ),
]
```

### Install sequence (per add-on)

```
git_clone method:
  1. git clone <repo> custom_nodes/<addon_id>
  2. uv pip install -r custom_nodes/<addon_id>/requirements.txt (if exists)
  3. If post_install_cmd is set: run post_install_cmd (skip install.py — conflict avoidance)
     Else if install.py exists: run install.py (legacy custom-node pattern)
  4. Append to env.installed_addons

pip_package method:
  1. uv pip install <pip_package>
  2. Append to env.installed_addons (no custom_nodes/ entry)
```

**Note on `post_install_cmd` format:** the first element may be literal `"pip"`; at execution time the registry translates this to `tools/uv/uv.exe pip --python <venv_python>` when `package_manager == "uv"`, or keeps pip invocation via the venv's `pip.exe` when `package_manager == "pip"`. Registry entries store `"pip"` as a portable token, not a literal command path.

**Ordering note:** when an add-on has both `install.py` (legacy) and `post_install_cmd` (registry-specified), the registry's command wins and `install.py` is skipped. This prevents double installs (e.g., SageAttention's `install.py` calls `pip install -e .` which would duplicate our post_install_cmd).

Add-on install failure during **create_recommended** does NOT roll back the main environment; the failing add-on is skipped, logged, and reported in the final summary dialog. This is a deliberate tradeoff — the main env takes ~5 minutes to build, and forcing rollback for a compile failure would be brutal.

## 8. Recommended Install Flow

`EnvManager.create_recommended(name, selected_addon_ids, progress_callback)`:

```
Progress  Step                                                         Can-fail-skip
---------------------------------------------------------------
  5%      Resolve bundled Python 3.12.10                                 (download if absent to tools/python_3.12.10/)
 10%      Detect GPU → pick Pack (abort with clear error if None)
 15%      Resolve ComfyUI latest release tag via version_controller
 20%      Create venv (using Python 3.12.10)
 25%      Ensure tools/uv/uv.exe exists (download if absent)
 30%      git clone ComfyUI at selected tag
 45%      uv pip install torch==X torchvision==Y torchaudio==Z
              --index-url https://download.pytorch.org/whl/{cuda_tag}
 60%      uv pip install -r ComfyUI/requirements.txt
              --extra-index-url {cuda_tag} -c _constraints.txt
              (_constraints.txt pins all 3 torch packages)
 68%      uv pip install <pinned_deps>
 72%      Verify critical packages (torch, numpy, pillow, pyyaml, aiohttp)
              — FATAL if missing
 78%      git clone ComfyUI-Manager → custom_nodes/ComfyUI-Manager
              Write manager security config
 82-95%   For each selected add-on (in order):                           YES — per-addon
              install via registry
              append to env.installed_addons
 96%      Generate extra_model_paths.yaml
 98%      Write env_meta.json (with torch_pack, installed_addons)
100%      Done
```

**On fatal failure (steps 5–78)**: delete env directory (existing behavior preserved). Show error with step where it failed.

**On add-on failure (steps 82–95)**: skip that add-on, continue. Collect failures and show them in the completion dialog.

## 9. UV Integration

### Binary location
- `tools/uv/uv.exe` (Windows standalone binary, ~30 MB)
- Downloaded on demand from Astral's GitHub release on first use
- Pin version per `recommended_uv_version` in `torch_packs.json` (default `0.9.7`)

### Invocation
- All pip-equivalent operations route through `uv_ops`:
  - `uv pip install …` → `tools/uv/uv.exe pip install --python <venv_python> …`
  - `uv pip uninstall …` → `tools/uv/uv.exe pip uninstall --python <venv_python> …`
- Progress callback parses uv's output format (different line prefixes than pip)

### Fallback policy
- **No automatic fallback.** If uv fails:
  - Error surfaces with the raw uv stderr
  - User can set `config.json.package_manager = "pip"` to switch tool-wide back to pip
- Ops in pip mode use the existing `pip_ops` path unchanged
- Rationale: silent fallback masks real problems and makes issues hard to reproduce

### Dependencies
- `pip_ops.create_venv` still creates venvs via stdlib `venv` / `virtualenv`. uv is only used for install/uninstall/freeze after the venv exists.
- `pip_ops.freeze` kept; `uv_ops.freeze` added; dispatch picks based on config

## 10. GUI Changes

### Create Environment dialog (env.js)

```
┌─ Create New Environment ─────────────────────────┐
│ [RECOMMENDED]                                     │
│                                                   │
│ Name:     [_____________________]                │
│                                                   │
│ [If GPU pre-flight failed, red banner here]      │
│                                                   │
│ ── Optional Add-ons ─────────────────────────    │
│   ☐ SageAttention v2     [needs CUDA, compiles]  │
│   ☐ FlashAttention       [needs CUDA, compiles]  │
│   ☐ InsightFace                                   │
│   ☐ Nunchaku             [needs CUDA, compiles]  │
│   ☐ Trellis 2.0          [needs CUDA, compiles]  │
│                                                   │
│ ▶ Advanced mode (manual Python/CUDA/Torch)       │
│                                                   │
│          [Cancel]         [Create (Recommended)] │
└───────────────────────────────────────────────────┘
```

### GPU pre-flight (open-time)
- Dialog calls `bridge.detect_gpu_for_recommended()` on open
- If no suitable Pack available:
  - Red banner: "未偵測到 CUDA ≥ 12.8 的 GPU。推薦模式不可用。若您確實有 GPU,請檢查驅動或使用進階模式手動選版本。"
  - Recommended button disabled
  - Advanced section auto-expanded
- Pre-flight result cached for the app session; user can refresh via "重新偵測"
- Detection failure (timeout, malformed output) treated as no GPU

### Advanced mode
- Collapsible section below recommended
- Contains current creation form (Python, CUDA, PyTorch dropdowns)
- When expanded, primary button switches to "Create (Advanced)"
- Advanced flow always writes `torch_pack = null` (even if selected versions coincidentally match a Pack)

### PyTorch sub-tab (versions.js)

Versions page top-level tabs become:
```
[ ComfyUI Version | PyTorch Engine ]
```

**PyTorch Engine tab contents:**
```
Target environment: [main         ▼]

Current Pack: PyTorch 2.8.0 + CUDA 12.8  ✅
   (or)      Custom version (torch 2.5.1+cu124)  ⚠️

── Available Packs ──
◉ PyTorch 2.9.1 + CUDA 13.0  [Recommended]  (your driver supports)
○ PyTorch 2.8.0 + CUDA 12.8  [Current]
○ PyTorch 2.7.1 + CUDA 12.8  [Compat mode]

Compiled add-ons in this env:
   • SageAttention v2  — will be uninstalled, you can reinstall after switch
   • FlashAttention     — same

                [Refresh List]    [Switch]
```

"⚠️ Custom version" appears when `env.torch_pack` is null; switching from custom to a Pack is allowed but has an extra confirm modal warning the change is not reversible without snapshot restore.

## 11. Migration

`migrate_env_meta()` runs once on app start when the new version is first launched:

```python
def backfill_torch_pack(envs, packs):
    for env in envs:
        if env.torch_pack is not None:
            continue
        if not env.pytorch_version:
            continue
        ver_base = env.pytorch_version.split("+")[0].strip()
        for p in packs:
            if p.torch == ver_base and p.cuda_tag == env.cuda_tag:
                env.torch_pack = p.id
                env.save_meta()
                break
        # otherwise leaves torch_pack as None (shown as "Custom version")

def backfill_installed_addons(envs, addon_registry):
    for env in envs:
        if env.installed_addons:
            continue
        custom_nodes_dir = Path(env.path) / "ComfyUI" / "custom_nodes"
        if not custom_nodes_dir.exists():
            continue
        for addon in addon_registry:
            if addon.install_method != "git_clone":
                continue
            if (custom_nodes_dir / addon.id).exists():
                env.installed_addons.append({
                    "id": addon.id,
                    "installed_at": env.created_at,      # best effort
                    "torch_pack_at_install": env.torch_pack,  # may be None
                })
        env.save_meta()
```

Migration is pure-read + write-back to env_meta. No packages are touched. Runs once per version bump (tracked via a marker file `tools/migration_0.4.0.done`).

## 12. Testing

| Test file | Coverage |
|---|---|
| `tests/test_core/test_torch_pack.py` | `select_pack_for_gpu()` for all driver ranges; remote refresh success/failure/schema-mismatch; Pack JSON schema validation |
| `tests/test_core/test_addons.py` | Registry loading; `install_addon()` dispatches to pip_package vs git_clone paths; uninstall reverses correctly |
| `tests/test_core/test_env_manager_recommended.py` | `create_recommended()` integration (git/uv/network mocked); GPU pre-flight blocks; add-on failure doesn't delete env; rollback on fatal step |
| `tests/test_core/test_migration.py` | backfill maps known versions; leaves unknown as null; does not touch other fields; idempotent |
| `tests/test_utils/test_uv_ops.py` | uv invocation happy path; download binary; failure surfaces stderr; config flag switches to pip_ops |
| `tests/test_core/test_torch_pack_switch.py` | Switch flow: snapshot created, addons uninstalled, torch reinstalled, pinned_deps reapplied, env_meta updated |

Existing tests (`test_env_manager.py` etc.) must remain green. Expected changes there are limited to updating the `create_environment()` call sites to assert `torch_pack is None` for advanced-mode-created envs.

## 13. Risks & Edge Cases

1. **uv with embedded Python** — uv standalone binary is independent of Python, but it creates/inspects venvs built with the embedded Python. Known-good path: `uv pip install --python <venv/Scripts/python.exe>`. Verified on uv 0.9.x. Mitigation: keep pip fallback via config flag.

2. **Compiled add-on failures are common** — nvcc toolchain drift means SageAttention/FlashAttention/Nunchaku commonly fail to build. Mitigation: UI explicit warnings, per-addon isolation, main env never rolled back due to add-on failure.

3. **Remote `torch_packs.json` schema drift** — `schema_version` gate prevents newer-than-expected JSON from breaking parsing. Remote JSON that can't be parsed is ignored silently (with log).

4. **Advanced mode coexistence** — the two flows share `_install_torch_pack()` and `_install_pinned_deps()` low-level helpers; advanced skips pack lookup + add-on steps. Unit tests must cover both paths calling the same helpers to prevent drift.

5. **Version string edge cases** — `env.pytorch_version` in legacy envs may be `2.5.1+cu124` (PyTorch CUDA suffix), `2.5.1` (base), or empty. Migration always `.split("+")[0].strip()` before matching.

6. **`tools/python_3.12.10` already exists but is different build** — check python version via `--version`; if present but wrong version, skip download and warn.

7. **uv download failure / offline** — recommended mode aborts with clear error and instruction to enable `package_manager: "pip"` in config.

8. **ComfyUI-Manager on recommended-tag ComfyUI** — some Manager versions have compat gates with Comfy versions. We continue cloning `main` of Manager (current behavior). If this becomes a problem, add a `recommended_manager_commit` to `torch_packs.json` in a future revision.

9. **GPU detection hanging** — existing `detect_gpu()` has 10s timeout; pre-flight inherits this. Timeout treated as "no GPU".

10. **Switch Pack to same Pack** — no-op short-circuit: if target Pack id equals current `torch_pack`, show "Already on this Pack" and do nothing.

## 14. Version Bump

- `VERSION.json` → `0.4.0`
- `release_notes`: 推薦模式建環境 + Torch-Pack 切換 + uv 遷移
- `changes` (zh-TW):
  - 新增推薦模式:建環境時自動依 GPU 選擇 PyTorch/CUDA 組合,無需手動選版本
  - 新增 Torch-Pack 引擎切換(版本頁 → PyTorch 引擎分頁)
  - 新增可選擴充:SageAttention / FlashAttention / InsightFace / Nunchaku / Trellis 2
  - 套件安裝改用 uv(顯著加快環境建置)
  - env_meta.json 新增 `torch_pack` 與 `installed_addons` 欄位
- `changes` (en):
  - Added Recommended mode: environment creation auto-selects PyTorch/CUDA combo based on GPU — no more manual version picking
  - Added Torch-Pack engine switcher (Versions page → PyTorch Engine tab)
  - Added optional curated add-ons: SageAttention / FlashAttention / InsightFace / Nunchaku / Trellis 2
  - Package operations now use uv (significantly faster env creation)
  - `env_meta.json` gains `torch_pack` and `installed_addons` fields

## 15. Decision Log

| # | Decision | Source |
|---|---|---|
| 1 | Version UI: recommended primary, advanced collapsed, both preserved | Q1 |
| 2 | Torch-Pack: hardcoded defaults + remote refresh | Q2 |
| 3 | Add-ons: curated node list only (5 items), checkbox during create | Q3 |
| 4 | Full uv migration, not partial | Q4 |
| 5 | GPU → Pack: 2-tier auto (cu130/cu128); no-GPU blocks recommended | Q5 |
| 6 | env_meta new `torch_pack` field for tracking | Q6 |
| 7 | Torch-Pack switcher lives in Versions page sub-tab | Q7 |
| 8 | Pack switch + compiled add-on: auto-uninstall + prompt to reinstall | G1 |
| 9 | Recommended Python 3.12.10, downloaded on demand | G2 |
| 10 | Recommended mode clones latest release tag, not master | G3 |
| 11 | `installed_addons` tracks id + installed_at + torch_pack_at_install | G4 |
| 12 | pinned_deps re-applied on every Pack switch (global, not per-Pack) | G5 |
| 13 | No-GPU pre-flight blocks dialog with banner + auto-expand advanced | G6 |
| 14 | uv: standalone binary in `tools/uv/`, pinned 0.9.7, no auto-fallback | G7 |
| 15 | Single-env Pack switch only (no batch) for MVP | G8 |
| 16 | Advanced mode always writes `torch_pack=null`; migration reverses via version match | G9 |
