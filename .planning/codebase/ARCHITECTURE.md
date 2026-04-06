# Architecture

**Analysis Date:** 2026-04-06

## Pattern Overview

**Overall:** Layered architecture with clear separation between CLI/GUI interfaces, business logic (core), data models, and system utilities.

**Key Characteristics:**
- Dual-mode application: CLI (`cli.py`) or desktop GUI (`launcher.py`)
- Modular core services for distinct concerns (environment, snapshot, version, launcher, conflict analysis)
- Data models define contracts between layers
- Utilities abstract system operations (git, pip, process management, filesystem)
- Configuration-driven setup via `config.json`

## Layers

**Presentation (UI):**
- Purpose: Interact with users via CLI or GUI
- Location: `cli.py` (CLI entry point), `src/gui/` (PySide6 desktop)
- Contains: Click CLI commands, Qt widgets, web bridge
- Depends on: Core services, configuration, models
- Used by: End users

**Application/Bridge Layer:**
- Purpose: Expose backend to frontend (GUI); coordinate CLI commands
- Location: `src/gui/bridge.py` (QWebChannel bridge for GUI), `cli.py` (Click groups for CLI)
- Contains: Async workers, request/response handling, command handlers
- Depends on: Core services
- Used by: Presentation layer

**Core Services:**
- Purpose: Business logic for managing ComfyUI environments
- Location: `src/core/`
- Contains:
  - `env_manager.py` - Create, list, delete, clone, merge environments
  - `snapshot_manager.py` - Snapshot creation, restore, cleanup
  - `version_controller.py` - Git version control for ComfyUI and custom nodes
  - `comfyui_launcher.py` - Process lifecycle (start, stop, health check)
  - `conflict_analyzer.py` - Dependency conflict detection (6-step analysis)
- Depends on: Models, utilities, configuration
- Used by: Bridge layer, CLI

**Models (Data Contracts):**
- Purpose: Define data structures for serialization/deserialization
- Location: `src/models/`
- Contains:
  - `environment.py` - Environment metadata with save/load to `env_meta.json`
  - `snapshot.py` - Snapshot metadata
  - `conflict_report.py` - Conflict analysis results with risk levels
- Depends on: Standard library only
- Used by: Core services, presentation

**Utilities:**
- Purpose: Wrap external operations (git, pip, process, filesystem)
- Location: `src/utils/`
- Contains:
  - `git_ops.py` - GitPython wrapper (clone, checkout, pull, log, branches, tags)
  - `pip_ops.py` - Pip wrapper (install, freeze, venv management)
  - `process_manager.py` - Process lifecycle and port management
  - `fs_ops.py` - Config loading/saving, filesystem helpers
- Depends on: External libraries (GitPython, requests, Pillow, PyYAML)
- Used by: Core services

## Data Flow

**Environment Creation Flow:**

1. CLI/GUI → `EnvManager.create_environment(name, branch, commit)`
2. `env_manager.py` calls utilities in sequence:
   - `pip_ops.create_venv()` - Create Python venv
   - `git_ops.clone_repo()` - Clone ComfyUI repo
   - `pip_ops.run_pip_with_progress()` - Install PyTorch and dependencies
   - `git_ops.clone_repo()` - Clone ComfyUI-Manager
3. Collect metadata (Python version, commit hash, custom nodes list)
4. `Environment.save_meta()` writes `env_meta.json` to environment directory
5. Return `Environment` object to presentation layer

**Snapshot Creation Flow:**

1. CLI/GUI → `SnapshotManager.create_snapshot(env_name, trigger)`
2. Load `Environment` metadata from `env_meta.json`
3. Collect current state:
   - `pip_ops.freeze()` - Export installed packages
   - `git_ops.get_current_commit()` - Get ComfyUI commit
   - `pip_ops.get_python_version()` - Get Python version
   - Parse `torch.version.cuda` for CUDA info
4. Create snapshot directory: `snapshots/{env_name}/{snapshot_id}/`
5. Write `freeze.txt`, `snapshot_meta.json`, and config backups
6. Update environment metadata with snapshot reference
7. Return `Snapshot` object

**Conflict Analysis Flow:**

1. CLI/GUI → `ConflictAnalyzer.analyze(env_name, node_path)` (6-step pipeline)
2. **Step 1:** Extract dependencies from plugin:
   - Parse `requirements.txt`
   - AST-analyze `install.py` for pip/git calls
3. **Step 2:** Dry-run analysis:
   - `pip install --dry-run` the plugin's dependencies
4. **Step 3:** Version comparison:
   - Current environment (`pip_ops.freeze()`)
   - vs. dry-run output
3. **Step 4:** Detect critical packages (from config)
4. **Step 5:** Classify overall risk (GREEN → YELLOW → HIGH → CRITICAL)
5. **Step 6:** Generate recommendations
6. Return `ConflictReport` with risk level and recommendations

**Launcher Flow:**

1. CLI/GUI → `ComfyUILauncher.start(env_name, port)`
2. Find available port via `process_manager.find_available_port()`
3. Build command: `python main.py --listen --port {port}`
4. `process_manager.start_process()` spawns ComfyUI
5. Save PID and port to `.comfyui.pid` (JSON)
6. Auto-open browser after health check succeeds
7. Return `{pid, port, env_name}`

**State Management:**

- **Environments:** Persisted in `environments/{env_name}/env_meta.json`
- **Snapshots:** Persisted in `snapshots/{env_name}/{snapshot_id}/`
- **Running processes:** Tracked in `environments/{env_name}/.comfyui.pid`
- **Config:** Persisted in `config.json` at project root
- **GUI state:** QWebChannel bridge maintains request queues (results, progress)

## Key Abstractions

**EnvManager:**
- Purpose: Manages lifecycle of isolated ComfyUI runtime environments
- Examples: `src/core/env_manager.py` - 350+ lines
- Pattern: Factory + lifecycle manager; each environment is self-contained in `environments/{name}/`

**SnapshotManager:**
- Purpose: Point-in-time capture of environment state for safe rollback
- Examples: `src/core/snapshot_manager.py` - 250+ lines
- Pattern: Snapshot aggregate; stores freeze, git state, configs in `snapshots/{env}/{id}/`

**ConflictAnalyzer:**
- Purpose: Pre-install risk assessment for plugins
- Examples: `src/core/conflict_analyzer.py` - 400+ lines
- Pattern: 6-step analysis pipeline; validates before installation

**Bridge (GUI):**
- Purpose: Bidirectional communication between Qt backend and web frontend
- Examples: `src/gui/bridge.py` - QWebChannel slots expose services
- Pattern: Async workers (QThread) for long operations; result/progress queues

**Environment (Data Model):**
- Purpose: Serializable contract for environment metadata
- Examples: `src/models/environment.py` - @dataclass with save_meta/load_meta
- Pattern: Save to `env_meta.json`; loaded on startup and when accessing env

## Entry Points

**CLI Entry Point:**
- Location: `cli.py`
- Triggers: `python cli.py [command] [options]`
- Responsibilities: Parse Click commands, instantiate managers, call core logic, format output with Rich tables

**GUI Entry Point:**
- Location: `launcher.py` (no args) or `launcher.py [args]` for CLI
- Triggers: `python launcher.py` (GUI) or `python launcher.py [cmd]` (CLI delegation)
- Responsibilities: Initialize Qt application, load web SPA, establish QWebChannel bridge, manage window lifecycle

**Web SPA (GUI Frontend):**
- Location: `src/gui/web/index.html` and related JS/CSS (not detailed in Python codebase)
- Triggers: Loaded by QWebEngineView in `launcher.py`
- Responsibilities: UI panels (env, launcher, snapshot, version, plugin), API calls via bridge

## Error Handling

**Strategy:** Try-catch at service layer; return meaningful error messages to presentation; CLI uses `SystemExit(1)`

**Patterns:**
- `FileNotFoundError` - Environment/environment not found; caught and printed as `[red]Error: ...[/red]` (Rich formatting)
- `FileExistsError` - Duplicate environment name; caught and printed
- `ValueError` - Invalid input (bad env name pattern, etc.)
- `Exception` (generic) - Logged and rethrown as message to user
- Bridge workers catch all exceptions and return `{error: string}` JSON

## Cross-Cutting Concerns

**Logging:**
- Debug logs to `/debug.log` (Bridge layer)
- Rich console output with color coding (CLI)
- Subprocess logs captured to `environments/{env_name}/comfyui.log`

**Validation:**
- Environment name pattern: `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` (regex in `env_manager.py`)
- Config keys filled from defaults (in `fs_ops.load_config()`)
- Snapshot directory structure validated on restore

**Configuration:**
- Central `config.json` with defaults applied on missing keys
- Settings: ComfyUI repo URL, PyTorch index URL, model subdirectories, conflict analyzer critical packages
- Loaded once at startup, passed to all services

**Internationalization:**
- GUI supports English (en) and Traditional Chinese (zh-TW)
- Strings defined in `src/gui/i18n.py`
- Language selectable at runtime via dropdown in top bar

---

*Architecture analysis: 2026-04-06*
