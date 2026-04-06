# Codebase Structure

**Analysis Date:** 2026-04-06

## Directory Layout

```
tk_comfyui_starter2/
├── cli.py                          # CLI entry point (Click commands)
├── launcher.py                     # GUI/CLI launcher (PySide6)
├── config.json                     # Application configuration
├── src/                            # Main source code
│   ├── __init__.py
│   ├── core/                       # Business logic services
│   │   ├── __init__.py
│   │   ├── env_manager.py          # Environment lifecycle management
│   │   ├── snapshot_manager.py     # Snapshot creation/restore/cleanup
│   │   ├── version_controller.py   # Git version control
│   │   ├── comfyui_launcher.py     # Process management (start/stop)
│   │   └── conflict_analyzer.py    # Dependency conflict detection
│   ├── gui/                        # Desktop GUI (PySide6)
│   │   ├── __init__.py
│   │   ├── main_window.py          # Main Qt window with sidebar
│   │   ├── bridge.py               # QWebChannel bridge (Python↔JS)
│   │   ├── workers.py              # Qt worker threads
│   │   ├── i18n.py                 # Internationalization (en, zh-TW)
│   │   ├── theme.py                # Qt styling
│   │   ├── panels/                 # UI panels (one per feature area)
│   │   │   ├── __init__.py
│   │   │   ├── env_panel.py        # Environment management UI
│   │   │   ├── launcher_panel.py   # ComfyUI launcher UI
│   │   │   ├── snapshot_panel.py   # Snapshot management UI
│   │   │   ├── version_panel.py    # Version control UI
│   │   │   └── plugin_panel.py     # Plugin/conflict analysis UI
│   │   └── web/                    # Web SPA frontend (HTML/CSS/JS)
│   │       └── index.html
│   ├── models/                     # Data models (dataclasses)
│   │   ├── __init__.py
│   │   ├── environment.py          # Environment metadata model
│   │   ├── snapshot.py             # Snapshot metadata model
│   │   └── conflict_report.py      # Conflict analysis report model
│   └── utils/                      # System operation wrappers
│       ├── __init__.py
│       ├── fs_ops.py               # Filesystem and config ops
│       ├── git_ops.py              # Git operations (GitPython wrapper)
│       ├── pip_ops.py              # Pip operations (venv, install, freeze)
│       └── process_manager.py      # Process lifecycle, port management
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── test_core/                  # Core service tests
│   │   ├── test_env_manager.py
│   │   ├── test_snapshot_manager.py
│   │   ├── test_version_controller.py
│   │   ├── test_comfyui_launcher.py
│   │   └── test_conflict_analyzer.py
│   ├── test_gui/                   # GUI tests
│   │   └── test_bridge.py
│   ├── test_models/                # Model serialization tests
│   │   ├── test_environment.py
│   │   └── test_snapshot.py
│   └── test_utils/                 # Utility function tests
│       ├── test_fs_ops.py
│       ├── test_git_ops.py
│       ├── test_pip_ops.py
│       └── test_process_manager.py
├── environments/                   # Runtime environments (generated)
│   ├── main/
│   │   ├── ComfyUI/                # ComfyUI clone
│   │   ├── venv/                   # Python virtual environment
│   │   ├── env_meta.json           # Environment metadata
│   │   ├── .comfyui.pid            # Running process ID (when active)
│   │   └── comfyui.log             # ComfyUI process output log
│   ├── test5/
│   └── test6/
├── snapshots/                      # Snapshots (generated)
│   ├── main/
│   │   ├── snap-20260406-153000-123456/
│   │   │   ├── snapshot_meta.json  # Snapshot metadata
│   │   │   ├── freeze.txt          # pip freeze output
│   │   │   ├── configs/            # Backed-up config files
│   │   │   └── custom_nodes_state.json
│   │   └── snap-20260406-140000-654321/
│   └── test5/
├── models/                         # ComfyUI model files (user data)
│   ├── checkpoints/
│   ├── loras/
│   ├── vae/
│   ├── controlnet/
│   ├── clip/
│   ├── embeddings/
│   └── upscale_models/
├── docs/                           # Documentation
│   └── design/
├── .planning/                      # GSD planning artifacts
│   └── codebase/                   # Codebase analysis documents
│       ├── ARCHITECTURE.md
│       └── STRUCTURE.md
└── .omc/                           # Oh-My-ClaudeCode orchestration state
    ├── state/
    ├── sessions/
    └── specs/
```

## Directory Purposes

**`cli.py`:**
- Purpose: Command-line interface entry point
- Contains: Click command groups (env, snapshot, version, launch) with handlers
- Key functions: `cli()` (main group), `env_*()`, `snapshot_*()`, `version_*()`, `launch_*()`
- Rich console output with tables

**`launcher.py`:**
- Purpose: Application entry point (CLI or GUI selector)
- Contains: Qt application initialization, web view setup, QWebChannel bridge connection
- Loads `src/gui/web/index.html` into QWebEngineView
- Detects CLI args vs. GUI mode

**`src/core/`:**
- Purpose: Core business logic services
- Contains: 5 manager classes responsible for environment, snapshot, version, launcher, and conflict analysis operations
- Imports: Models, utilities, config
- No Qt/Click dependencies—pure Python

**`src/gui/`:**
- Purpose: Desktop GUI (PySide6)
- Contains: Main window, panels, bridge, theming, i18n
- `bridge.py`: Exposes core services to JS via QWebChannel; manages async workers
- `panels/*.py`: Legacy PyQt/PySide widgets (or placeholder for web-based UI)
- `web/`: Web SPA frontend (JavaScript/CSS)

**`src/models/`:**
- Purpose: Data contracts between layers
- Contains: Dataclasses with serialization (to_dict, from_dict, save_meta, load_meta)
- No dependencies on core or GUI; only standard library

**`src/utils/`:**
- Purpose: Wrappers around external system operations
- Contains: Git, pip, process, and filesystem operations
- No direct imports from core or models; utilities are reusable building blocks

**`tests/`:**
- Purpose: Unit and integration tests
- Structure mirrors `src/` (test_core, test_gui, test_models, test_utils)
- Contains: pytest fixtures, mocks, test cases for all services

**`environments/`:**
- Purpose: Runtime data (generated at runtime)
- Structure: `{env_name}/{venv, ComfyUI, env_meta.json, .comfyui.pid}`
- Committed: No (gitignored)
- Managed by: `EnvManager`

**`snapshots/`:**
- Purpose: Point-in-time backups of environment state (generated)
- Structure: `{env_name}/{snapshot_id}/{freeze.txt, snapshot_meta.json, configs/}`
- Committed: No (gitignored)
- Managed by: `SnapshotManager`

**`models/`:**
- Purpose: ComfyUI model files (user data)
- Contains: checkpoints, LoRAs, VAE, ControlNet, CLIP, embeddings, upscale models
- Committed: No (large binary files, gitignored)
- Managed by: User and ComfyUI

**`docs/`:**
- Purpose: Project documentation
- Contains: Design documents, guides, API specs
- Committed: Yes

**`.planning/`:**
- Purpose: GSD (Generalist Software Development) planning artifacts
- Contains: Codebase analysis (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Committed: Yes
- Used by: `/gsd` commands for context during planning and execution

## Key File Locations

**Entry Points:**
- `cli.py`: CLI execution (`python cli.py [command]`)
- `launcher.py`: GUI or CLI launcher (`python launcher.py` for GUI, `python launcher.py [cmd]` for CLI)
- `config.json`: Configuration file (loaded at startup)

**Configuration:**
- `config.json`: Application settings (default env, paths, PyTorch index URL, conflict analyzer rules)
- `environments/{env_name}/env_meta.json`: Environment metadata (branch, commit, Python version, custom nodes)
- `snapshots/{env_name}/{snapshot_id}/snapshot_meta.json`: Snapshot metadata

**Core Logic:**
- `src/core/env_manager.py`: Environment creation, cloning, merging, deletion
- `src/core/snapshot_manager.py`: Snapshot creation, restore, cleanup, max snapshot enforcement
- `src/core/version_controller.py`: Git version switching, updates, remote tag/branch listing
- `src/core/comfyui_launcher.py`: Process start/stop, health checks, browser auto-open
- `src/core/conflict_analyzer.py`: 6-step dependency conflict detection pipeline

**Data Models:**
- `src/models/environment.py`: Environment dataclass with metadata persistence
- `src/models/snapshot.py`: Snapshot dataclass
- `src/models/conflict_report.py`: ConflictReport, Conflict, RiskLevel enums

**Utilities:**
- `src/utils/git_ops.py`: Clone, checkout, pull, log, branches, tags
- `src/utils/pip_ops.py`: Venv creation, pip install, freeze, Python version detection
- `src/utils/process_manager.py`: Process start/stop, PID tracking, port availability
- `src/utils/fs_ops.py`: Config loading/saving, default config

**GUI:**
- `src/gui/bridge.py`: QWebChannel bridge exposing services to web frontend
- `src/gui/main_window.py`: Qt main window with sidebar and stacked panels
- `src/gui/panels/`: Individual UI panels (env_panel, launcher_panel, snapshot_panel, version_panel, plugin_panel)
- `src/gui/web/index.html`: Web SPA frontend

**Testing:**
- `tests/test_core/`: Service tests
- `tests/test_models/`: Serialization tests
- `tests/test_utils/`: Utility function tests

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `env_manager.py`, `conflict_analyzer.py`)
- Test files: `test_*.py` or `*_test.py` (e.g., `test_env_manager.py`)
- Configuration: `config.json` (lowercase with .json extension)
- Entry points: `cli.py`, `launcher.py` (root level)

**Directories:**
- Package directories: `snake_case` (e.g., `src/core`, `src/gui`, `src/models`, `src/utils`)
- Feature areas: Named by domain (e.g., `panels/`, `test_core/`)
- Runtime data: Lowercase descriptive names (`environments/`, `snapshots/`, `models/`)

**Classes:**
- Service classes: `*Manager` or `*Controller` (e.g., `EnvManager`, `VersionController`, `ConflictAnalyzer`)
- Data models: Domain name (e.g., `Environment`, `Snapshot`, `ConflictReport`)
- Qt classes: Widget type suffix (e.g., `MainWindow`, `EnvPanel`)

**Functions:**
- Python functions: `snake_case()` (e.g., `create_environment()`, `load_config()`)
- Public methods: `action_object()` (e.g., `create_snapshot()`, `switch_version()`)
- Private methods: `_internal_method()` prefix (e.g., `_validate_name()`, `_reinstall_requirements()`)
- Utility wrappers: Domain + action (e.g., `git_ops.clone_repo()`, `pip_ops.run_pip()`)

## Where to Add New Code

**New Feature (e.g., New Manager Service):**
- Primary code: `src/core/{feature_name}.py`
- Tests: `tests/test_core/test_{feature_name}.py`
- Models (if needed): `src/models/{feature_name}.py`
- Example: For a new "config backup manager," create `src/core/config_backup_manager.py` and test it in `tests/test_core/test_config_backup_manager.py`

**New CLI Command:**
- Add command group and commands to `cli.py`
- Follow Click decorator pattern: `@cli.group()` for groups, `@group.command()` for commands
- Import required managers from `src/core/`
- Format output with Rich console tables

**New GUI Panel:**
- Create `src/gui/panels/{feature_name}_panel.py`
- Implement panel widget class (inherits from Qt widget)
- Add to `MainWindow` sidebar in `src/gui/main_window.py`
- Expose backend methods in `src/gui/bridge.py` as QObject slots

**New Utility Function:**
- Add to `src/utils/{domain}_ops.py` (e.g., git_ops, pip_ops, process_manager, fs_ops)
- Wrap external library calls
- Keep functions pure and testable

**New Data Model:**
- Create dataclass in `src/models/{model_name}.py`
- Implement `to_dict()`, `from_dict()` serialization
- For persistent models, add `save_meta()` and `load_meta()` methods
- Keep no dependencies on core or GUI

## Special Directories

**`environments/{env_name}/`:**
- Purpose: Isolated ComfyUI runtime environments
- Generated: Yes (created by `EnvManager.create_environment()`)
- Committed: No (gitignored)
- Contains: `venv/` (Python environment), `ComfyUI/` (repo clone), `env_meta.json` (metadata), `.comfyui.pid` (running process)
- Cleanup: `EnvManager.delete_environment()` removes entire directory

**`snapshots/{env_name}/{snapshot_id}/`:**
- Purpose: Point-in-time backups
- Generated: Yes (created by `SnapshotManager.create_snapshot()`)
- Committed: No (gitignored)
- Contains: `freeze.txt` (pip packages), `snapshot_meta.json` (metadata), `configs/` (backed-up YAML files), `custom_nodes_state.json`
- Max snapshots: Configured in `config.json` (default 20)
- Cleanup: Oldest snapshots deleted when max reached

**`models/`:**
- Purpose: ComfyUI model storage (user data)
- Generated: Yes (created by ComfyUI at runtime)
- Committed: No (binary files, gitignored)
- Contains: `checkpoints/`, `loras/`, `vae/`, `controlnet/`, `clip/`, `embeddings/`, `upscale_models/`
- Shared: Can be linked across environments via `extra_model_paths.yaml`

**`.planning/codebase/`:**
- Purpose: Codebase analysis documents (ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md)
- Generated: By GSD agents (not hand-written)
- Committed: Yes
- Used by: `/gsd` commands for context during planning and execution phases

---

*Structure analysis: 2026-04-06*
