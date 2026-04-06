# Testing Patterns

**Analysis Date:** 2026-04-06

## Test Framework

**Runner:**
- pytest 7.0+
- Config: `pytest.ini`
- Configured with: `testpaths = tests`, `python_files = test_*.py`, `python_classes = Test*`, `python_functions = test_*`
- Verbosity flags: `-v --tb=short`

**Assertion Library:**
- Built-in Python `assert` statements
- No custom assertion library

**Run Commands:**
```bash
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest --tb=short              # Short traceback format (configured)
pytest tests/test_core/        # Run specific test directory
pytest -k test_create          # Run tests matching pattern
```

**Coverage:**
- pytest-cov 4.0+ available (in requirements)
- Coverage file present (`.coverage`)
- No minimum coverage requirement enforced

## Test File Organization

**Location:**
- Test files co-located in parallel `tests/` directory structure
- Mirrors source structure: `tests/test_core/`, `tests/test_models/`, `tests/test_utils/`, `tests/test_gui/`
- Test discovery follows pytest convention

**Naming:**
- Test files: `test_*.py` (e.g., `test_env_manager.py`, `test_cli.py`)
- Test classes: `Test*` (e.g., `TestEnvManager`, `TestCreateEnvironment`)
- Test functions: `test_*` (e.g., `test_create_basic`, `test_init`)

**Structure:**
```
tests/
├── conftest.py              # Shared fixtures
├── test_cli.py              # CLI tests
├── test_core/               # Core module tests
│   ├── __init__.py
│   ├── test_env_manager.py
│   ├── test_snapshot_manager.py
│   ├── test_conflict_analyzer.py
│   └── ...
├── test_models/             # Model tests
│   ├── test_environment.py
│   ├── test_snapshot.py
│   └── ...
├── test_utils/              # Utility tests
│   ├── test_fs_ops.py
│   ├── test_git_ops.py
│   └── ...
└── test_gui/                # GUI tests
    └── test_gui_basic.py
```

## Test Structure

**Suite Organization:**
```python
class TestEnvManagerInit:
    """Test EnvManager initialization."""

    def test_init(self, sample_config):
        manager = EnvManager(sample_config)
        assert manager.config == sample_config
```

**Patterns:**
- Test classes group related tests by behavior/scenario
- Descriptive class names indicate what's being tested: `TestCreateEnvironment`, `TestStart`, `TestStop`
- Setup via fixtures (no explicit setup/teardown methods)
- Teardown handled automatically by pytest fixtures (tmp_path cleanup)

## Mocking

**Framework:** `unittest.mock` from Python standard library

**Patterns:**
```python
from unittest.mock import patch, MagicMock, call

@patch("src.core.env_manager.pip_ops")
@patch("src.core.env_manager.git_ops")
def test_create_basic(self, mock_git, mock_pip, sample_config):
    mock_git.clone_repo.return_value = MagicMock()
    mock_git.get_current_commit.return_value = "abc1234"
    mock_pip.get_python_version.return_value = "3.11.9"
    mock_pip.freeze.return_value = {"pip": "24.0"}
    
    manager = EnvManager(sample_config)
    env = manager.create_environment("test-env")
    
    assert env.name == "test-env"
    mock_git.clone_repo.assert_called_once()
```

**What to Mock:**
- External subprocess calls: `git_ops`, `pip_ops`
- File I/O that requires side effects
- Process management: `process_manager.subprocess.Popen`, `psutil.Process`
- HTTP requests: `requests.get` when testing network operations
- Qt/GUI components: `QThread`, socket connections

**What NOT to Mock:**
- Core business logic (dataclasses, validation)
- File path operations (use `tmp_path` fixture instead)
- Core models: `Environment`, `Snapshot`, `ConflictReport`
- Pure functions without side effects

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
def sample_config(tmp_project):
    """Return a sample config dict pointing to tmp_project."""
    return {
        "version": "0.1.0",
        "default_env": "main",
        "python_path": None,
        "comfyui_repo_url": "https://github.com/comfyanonymous/ComfyUI.git",
        "base_dir": str(tmp_project),
        "environments_dir": str(tmp_project / "environments"),
        "models_dir": str(tmp_project / "models"),
        "snapshots_dir": str(tmp_project / "snapshots"),
        # ... more config
    }

@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with standard structure."""
    envs_dir = tmp_path / "environments"
    models_dir = tmp_path / "models"
    snapshots_dir = tmp_path / "snapshots"
    envs_dir.mkdir()
    models_dir.mkdir()
    snapshots_dir.mkdir()
    return tmp_path
```

**Location:**
- Fixtures defined in `tests/conftest.py` for sharing across test modules
- Module-specific fixtures defined in test files
- Helper functions (non-fixtures) prefixed with underscore: `_create_mock_env()`

**Example Helper:**
```python
def _create_mock_env(envs_dir, name, comfyui_commit="abc1234"):
    """Helper to create a mock environment."""
    env_dir = Path(envs_dir) / name
    env_dir.mkdir(parents=True, exist_ok=True)
    # ... setup files
    return env_dir
```

## Coverage

**Requirements:** No explicit minimum enforced (but `.coverage` file present)

**View Coverage:**
```bash
pytest --cov=src --cov-report=html    # Generate HTML report
pytest --cov=src --cov-report=term    # Terminal report
```

## Test Types

**Unit Tests:**
- Scope: Individual functions and class methods
- Approach: Mock external dependencies, test behavior in isolation
- Location: `tests/test_core/test_*.py`, `tests/test_models/test_*.py`, `tests/test_utils/test_*.py`
- Example: Testing `EnvManager.create_environment()` with mocked `git_ops` and `pip_ops`

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Use real `tmp_path` fixtures, minimal mocking
- Location: `tests/test_core/test_*.py` with fewer mocks
- Example: Testing environment creation through full pipeline with temporary filesystem

**E2E Tests:**
- Status: Not automated; manual testing via CLI/GUI
- Location: CLI tested via `click.testing.CliRunner` in `tests/test_cli.py`
- Example: Testing `cli` commands with CliRunner to verify help output and argument parsing

**CLI Tests:**
```python
@pytest.fixture
def runner():
    return CliRunner()

class TestCLIMain:
    """Test main CLI group."""

    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "tack_comfyui_start_tool" in result.output.lower()
```

## Common Patterns

**Async Testing:**
- GUI components use Qt threading (`QThread`)
- Tested via mocking thread-related operations
- No explicit async/await testing patterns

**Error Testing:**
```python
def test_create_with_invalid_name(self, sample_config):
    manager = EnvManager(sample_config)
    with pytest.raises(ValueError) as exc_info:
        manager.create_environment("invalid name!")
    assert "Invalid environment name" in str(exc_info.value)
```

**File Assertion:**
```python
@patch("src.core.env_manager.pip_ops")
@patch("src.core.env_manager.git_ops")
def test_create_writes_env_meta(self, mock_git, mock_pip, sample_config):
    # ... setup mocks
    manager = EnvManager(sample_config)
    env = manager.create_environment("test-env")
    
    # Assert file was written
    meta_path = Path(sample_config["environments_dir"]) / "test-env" / "env_meta.json"
    assert meta_path.exists()
    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta_data["name"] == "test-env"
```

**Parameterized Tests:**
- Not heavily used; individual test methods preferred
- Can use `pytest.mark.parametrize` if needed but not observed in codebase

---

*Testing analysis: 2026-04-06*
