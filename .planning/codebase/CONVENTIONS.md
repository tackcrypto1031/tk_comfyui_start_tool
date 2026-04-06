# Coding Conventions

**Analysis Date:** 2026-04-06

## Naming Patterns

**Files:**
- Module files use `snake_case`: `env_manager.py`, `conflict_analyzer.py`, `git_ops.py`
- Test files follow pattern `test_*.py` and match module structure: `test_env_manager.py`
- GUI component files use `snake_case`: `main_window.py`, `env_panel.py`, `launcher_panel.py`
- Utility files grouped in `src/utils/` directory: `fs_ops.py`, `pip_ops.py`, `process_manager.py`

**Functions:**
- All functions use `snake_case`: `create_environment()`, `clone_repo()`, `get_current_commit()`, `is_port_in_use()`
- Private functions use leading underscore: `_validate_name()`, `_report()`, `_on_worker_done()`, `_handle_remove_readonly()`
- Callback functions end with suffix: `progress_callback`, `result_callback`

**Variables:**
- Instance variables use `snake_case`: `self.config`, `self.environments_dir`, `self.models_dir`
- Private instance variables use leading underscore: `self._workers`, `self._result_queue`, `self._progress_queue`
- Constants use `UPPER_SNAKE_CASE`: `DEFAULT_COMFYUI_URL`, `DEFAULT_MANAGER_URL`, `ENV_NAME_PATTERN`
- Loop/temporary variables are concise: `env`, `snap`, `pkg`, `d` (in dicts)

**Types:**
- Classes use `PascalCase`: `Environment`, `Snapshot`, `EnvManager`, `SnapshotManager`, `ConflictAnalyzer`
- Enum classes use `PascalCase`: `RiskLevel`
- Dialog classes use `PascalCase` with suffix: `CreateEnvDialog`, `CloneEnvDialog`

## Code Style

**Formatting:**
- No explicit formatter configuration found (no `.prettierrc` or similar)
- Code appears to follow PEP 8 standard Python style
- Line length appears reasonable (90-100 character range observed)
- Import statements consistently formatted with blank lines separating groups

**Linting:**
- Pytest is primary test runner (`pytest.ini` configured)
- No explicit linter config (eslint/ruff/flake8 config not found)
- Code structure suggests implicit adherence to PEP 8

## Import Organization

**Order:**
1. Standard library imports: `import json`, `import logging`, `import os`, `from pathlib import Path`
2. Third-party library imports: `import yaml`, `import click`, `from rich.console import Console`
3. Local application imports: `from src.models.environment import Environment`, `from src.utils import git_ops`
4. Type imports at function signature level using `Optional`, `List` from `typing`

**Path Aliases:**
- Imports use absolute paths from project root: `from src.core.env_manager import EnvManager`
- No path aliases configured (imports always use `src.*` prefix)
- GUI imports use Qt imports: `from PySide6.QtCore import QObject, Slot, Signal`

## Error Handling

**Patterns:**
- Specific exception types raised: `FileExistsError()`, `FileNotFoundError()`, `ValueError()`, `RuntimeError()`
- Error messages are descriptive with context: `f"Environment '{name}' already exists"`, `f"Snapshot '{snapshot_id}' not found for '{env_name}'"`
- No exception wrapping observed; exceptions propagate to caller
- Try-except used selectively for recovery: `try: python_version = pip_ops.get_python_version() except Exception: python_version = ""`

**Example from `src/core/env_manager.py`:**
```python
def _validate_name(self, name: str) -> None:
    if not ENV_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid environment name '{name}'. "
            "Must start with letter/digit, contain only alphanumeric, dash, underscore."
        )
```

## Logging

**Framework:** `logging` module from Python standard library

**Patterns:**
- Logger created at module level: `logger = logging.getLogger("bridge")`
- File-based logging configured in `src/gui/bridge.py`: logs to `debug.log`
- Logging levels: `logger.debug()`, `logger.info()`, `logger.error()`, `logger.warning()`
- Logging used for debugging and error tracking, not verbose business logic

**Example from `src/gui/bridge.py`:**
```python
logging.basicConfig(
    filename=str(_log_path),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bridge")
```

## Comments

**When to Comment:**
- Module docstrings explain overall purpose and scope
- Class docstrings describe the class's role and responsibilities
- Function docstrings explain inputs, behavior, and side effects
- Inline comments rare; code is generally self-documenting through clear names

**JSDoc/TSDoc:**
- Python project uses docstrings (not JSDoc)
- Format: triple-quoted strings immediately after definition
- Multi-line docstrings used for complex functions

**Example:**
```python
def create_environment(self, name: str, branch: str = "master",
                       commit: Optional[str] = None,
                       progress_callback=None) -> Environment:
    """Create a new ComfyUI environment with venv, cloned repo, and metadata."""
```

## Function Design

**Size:** 
- Functions are concise and focused (10-50 lines typical)
- Long operations broken into smaller functions with progress callbacks
- Helper functions created for repeated patterns: `_create_mock_env()`, `_report()`

**Parameters:**
- Type hints used consistently: `def get_python_version(venv_path: str) -> str:`
- Optional parameters use `Optional[]` type hint: `commit: Optional[str] = None`
- Callback parameters follow pattern: `progress_callback=None` with `if progress_callback: callback(...)`
- Reasonable parameter count (2-5 typical, max ~8 observed)

**Return Values:**
- Functions return typed objects when appropriate: `-> Environment`, `-> list`, `-> dict`
- None returned implicitly when function performs side effects
- Multiple return values avoided; uses dataclasses instead

**Example:**
```python
def clone_repo(url: str, dest: str, branch: str = "master",
               commit: Optional[str] = None,
               progress_callback=None) -> None:
    """Clone a git repository. Optionally checkout a specific commit."""
```

## Module Design

**Exports:**
- Modules export public classes and functions; private items prefixed with underscore
- No explicit `__all__` lists observed
- Imports use specific names: `from src.core.env_manager import EnvManager`

**Barrel Files:**
- GUI panels consolidated in `src/gui/panels/__init__.py`
- Core modules in `src/core/` with `__init__.py`
- Models in `src/models/` with `__init__.py`
- Utilities in `src/utils/` with `__init__.py`
- No barrel re-exports observed; imports are explicit

---

*Convention analysis: 2026-04-06*
