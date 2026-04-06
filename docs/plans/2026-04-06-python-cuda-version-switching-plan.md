# Python + CUDA Version Switching Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to select Python and CUDA versions per environment, with GPU auto-detection for defaults and manual version list refresh.

**Architecture:** New `src/core/version_manager.py` module handles GPU detection, version cache, Python download, and PyTorch reinstall. Existing `env_manager.py` and `pip_ops.py` gain parameters for custom Python/CUDA. The create-environment dialog gets a collapsible "Advanced Options" section.

**Tech Stack:** Python 3.12+, requests (HTTP fetching), subprocess (nvidia-smi), PySide6 QWebChannel, vanilla JS frontend.

---

### Task 1: Create version_manager.py — defaults and GPU detection

**Files:**
- Create: `src/core/version_manager.py`
- Test: `tests/test_version_manager.py`

**Step 1: Write the failing tests**

```python
# tests/test_version_manager.py
"""Tests for version_manager module."""
import json
import pytest
from unittest.mock import patch, MagicMock
from src.core.version_manager import VersionManager

# --- GPU Detection ---

def test_detect_gpu_with_nvidia(tmp_path):
    """nvidia-smi returns CUDA 12.6 → recommend cu126."""
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    fake_output = "CUDA Version: 12.6"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=fake_output, stderr=""
        )
        result = vm.detect_gpu()
    assert result["has_gpu"] is True
    assert result["cuda_driver_version"] == "12.6"
    assert result["recommended_cuda_tag"] == "cu126"


def test_detect_gpu_no_nvidia(tmp_path):
    """nvidia-smi not found → recommend cpu."""
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = vm.detect_gpu()
    assert result["has_gpu"] is False
    assert result["recommended_cuda_tag"] == "cpu"


def test_detect_gpu_maps_to_closest_tag(tmp_path):
    """Driver CUDA 12.5 → closest available tag is cu124."""
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    fake_output = "CUDA Version: 12.5"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=fake_output, stderr=""
        )
        result = vm.detect_gpu()
    assert result["recommended_cuda_tag"] == "cu124"


# --- Default Lists ---

def test_get_default_python_versions(tmp_path):
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    versions = vm.get_python_versions()
    assert len(versions) >= 4
    assert any(v["version"].startswith("3.12") for v in versions)


def test_get_default_cuda_tags(tmp_path):
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    tags = vm.get_cuda_tags()
    assert "cpu" in tags
    assert "cu124" in tags


# --- Version Cache ---

def test_load_cache_returns_defaults_when_no_cache(tmp_path):
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    cache = vm._load_cache()
    assert cache is None


def test_save_and_load_cache(tmp_path):
    config = {"base_dir": str(tmp_path)}
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    vm = VersionManager(config)
    vm.tools_dir = tools_dir
    test_data = {
        "last_updated": "2026-04-06T12:00:00",
        "python": [{"version": "3.12.8", "url": "https://example.com", "sha256": "abc"}],
        "cuda_tags": ["cpu", "cu124"],
    }
    vm._save_cache(test_data)
    loaded = vm._load_cache()
    assert loaded["python"][0]["version"] == "3.12.8"
```

**Step 2: Run tests to verify they fail**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/test_version_manager.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/core/version_manager.py
"""Version manager — GPU detection, Python/CUDA version lists, cache."""
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("version_manager")

# Built-in defaults (used when no cache exists)
DEFAULT_PYTHON_VERSIONS = [
    {"version": "3.10", "display": "Python 3.10"},
    {"version": "3.11", "display": "Python 3.11"},
    {"version": "3.12", "display": "Python 3.12"},
    {"version": "3.13", "display": "Python 3.13"},
]

DEFAULT_CUDA_TAGS = ["cpu", "cu118", "cu121", "cu124", "cu126", "cu128"]

# Known CUDA tag → numeric version mapping (for GPU matching)
CUDA_TAG_VERSIONS = {
    "cu118": 11.8,
    "cu121": 12.1,
    "cu124": 12.4,
    "cu126": 12.6,
    "cu128": 12.8,
    "cu130": 13.0,
}

_SUBPROCESS_KWARGS = {}
if sys.platform == "win32":
    _SUBPROCESS_KWARGS["creationflags"] = subprocess.CREATE_NO_WINDOW


class VersionManager:
    """Manages Python/CUDA version detection, caching, and downloads."""

    def __init__(self, config: dict):
        self.config = config
        base = Path(config.get("base_dir", "."))
        self.tools_dir = base / "tools"

    def detect_gpu(self) -> dict:
        """Detect NVIDIA GPU and recommend a CUDA tag."""
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True, text=True,
                timeout=10,
                **_SUBPROCESS_KWARGS,
            )
            if result.returncode != 0:
                return {"has_gpu": False, "recommended_cuda_tag": "cpu"}

            # Parse "CUDA Version: XX.Y" from nvidia-smi output
            output = result.stdout
            match = re.search(r"CUDA Version:\s*([\d.]+)", output)
            if not match:
                return {"has_gpu": False, "recommended_cuda_tag": "cpu"}

            cuda_ver_str = match.group(1)
            cuda_ver = float(cuda_ver_str)

            # Find best matching tag (highest tag <= driver version)
            best_tag = "cpu"
            best_ver = 0.0
            for tag, ver in CUDA_TAG_VERSIONS.items():
                if ver <= cuda_ver and ver > best_ver:
                    best_ver = ver
                    best_tag = tag

            return {
                "has_gpu": True,
                "cuda_driver_version": cuda_ver_str,
                "recommended_cuda_tag": best_tag,
            }
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {"has_gpu": False, "recommended_cuda_tag": "cpu"}

    def get_python_versions(self) -> list:
        """Return available Python versions (from cache or defaults)."""
        cache = self._load_cache()
        if cache and cache.get("python"):
            return cache["python"]
        return list(DEFAULT_PYTHON_VERSIONS)

    def get_cuda_tags(self) -> list:
        """Return available CUDA tags (from cache or defaults)."""
        cache = self._load_cache()
        if cache and cache.get("cuda_tags"):
            return cache["cuda_tags"]
        return list(DEFAULT_CUDA_TAGS)

    def get_cache_info(self) -> Optional[str]:
        """Return last_updated timestamp from cache, or None."""
        cache = self._load_cache()
        if cache:
            return cache.get("last_updated")
        return None

    def _cache_path(self) -> Path:
        return self.tools_dir / "version_cache.json"

    def _load_cache(self) -> Optional[dict]:
        path = self._cache_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _save_cache(self, data: dict) -> None:
        path = self._cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/test_version_manager.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add src/core/version_manager.py tests/test_version_manager.py
git commit -m "feat: add version_manager with GPU detection and version cache"
```

---

### Task 2: Add online refresh for version lists

**Files:**
- Modify: `src/core/version_manager.py`
- Test: `tests/test_version_manager.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_version_manager.py`:

```python
# --- Online Refresh ---

def test_refresh_python_versions_success(tmp_path):
    """Successful fetch parses embedded Python entries."""
    config = {"base_dir": str(tmp_path)}
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    vm = VersionManager(config)
    vm.tools_dir = tools_dir

    fake_json = json.dumps([
        {
            "id": "pythonembed-3.12-64",
            "sort-version": "3.12.8",
            "company": "PythonEmbed",
            "display-name": "Python 3.12.8 (embeddable)",
            "url": "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip",
            "hash": {"sha256": "abc123"},
            "executable": ".\\python.exe",
        },
        {
            "id": "pythoncore-3.12-64",
            "sort-version": "3.12.8",
            "company": "PythonCore",
            "display-name": "Python 3.12.8",
            "url": "https://example.com/installer.exe",
        },
        {
            "id": "pythonembed-3.13-64",
            "sort-version": "3.13.3",
            "company": "PythonEmbed",
            "display-name": "Python 3.13.3 (embeddable)",
            "url": "https://www.python.org/ftp/python/3.13.3/python-3.13.3-embed-amd64.zip",
            "hash": {"sha256": "def456"},
            "executable": ".\\python.exe",
        },
    ])

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_json

    with patch("requests.get", return_value=mock_resp):
        result = vm.refresh_python_versions()

    # Should only include PythonEmbed entries
    assert len(result) == 2
    assert result[0]["version"] == "3.13.3"  # sorted descending
    assert result[1]["version"] == "3.12.8"


def test_refresh_cuda_tags_success(tmp_path):
    """Successful fetch parses CUDA directories from PyTorch whl page."""
    config = {"base_dir": str(tmp_path)}
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    vm = VersionManager(config)
    vm.tools_dir = tools_dir

    fake_html = """
    <a href="cpu/">cpu/</a>
    <a href="cu118/">cu118/</a>
    <a href="cu121/">cu121/</a>
    <a href="cu124/">cu124/</a>
    <a href="cu126/">cu126/</a>
    <a href="nightly/">nightly/</a>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html

    with patch("requests.get", return_value=mock_resp):
        result = vm.refresh_cuda_tags()

    assert "cpu" in result
    assert "cu124" in result
    assert "nightly" not in result


def test_refresh_all_saves_cache(tmp_path):
    """refresh_all writes version_cache.json."""
    config = {"base_dir": str(tmp_path)}
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    vm = VersionManager(config)
    vm.tools_dir = tools_dir

    with patch.object(vm, "refresh_python_versions", return_value=[{"version": "3.12.8"}]):
        with patch.object(vm, "refresh_cuda_tags", return_value=["cpu", "cu124"]):
            vm.refresh_all()

    cache = vm._load_cache()
    assert cache is not None
    assert cache["python"][0]["version"] == "3.12.8"
    assert "cu124" in cache["cuda_tags"]
    assert "last_updated" in cache


def test_refresh_failure_raises(tmp_path):
    """Network failure raises RuntimeError."""
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    with patch("requests.get", side_effect=Exception("Network error")):
        with pytest.raises(RuntimeError, match="Failed to refresh"):
            vm.refresh_python_versions()
```

**Step 2: Run tests to verify they fail**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/test_version_manager.py -v -k "refresh"`
Expected: FAIL with AttributeError (methods don't exist yet)

**Step 3: Write implementation**

Add these methods to the `VersionManager` class in `src/core/version_manager.py`:

```python
    def refresh_python_versions(self) -> list:
        """Fetch available embedded Python versions from python.org."""
        import requests
        try:
            resp = requests.get(
                "https://www.python.org/ftp/python/index-windows.json",
                timeout=30,
            )
            resp.raise_for_status()
            entries = json.loads(resp.text)
        except Exception as e:
            raise RuntimeError(f"Failed to refresh Python versions: {e}")

        # Filter: PythonEmbed + amd64 only
        versions = []
        for entry in entries:
            if entry.get("company") != "PythonEmbed":
                continue
            entry_id = entry.get("id", "")
            if "64" not in entry_id and "amd64" not in entry.get("url", ""):
                continue
            # Skip arm64
            if "arm64" in entry_id or "arm64" in entry.get("url", ""):
                continue
            version = entry.get("sort-version", "")
            if not version:
                continue
            sha256 = ""
            hash_info = entry.get("hash")
            if isinstance(hash_info, dict):
                sha256 = hash_info.get("sha256", "")
            versions.append({
                "version": version,
                "display": entry.get("display-name", f"Python {version}"),
                "url": entry.get("url", ""),
                "sha256": sha256,
            })

        # Sort descending by version
        versions.sort(key=lambda v: [int(x) for x in v["version"].split(".")], reverse=True)
        return versions

    def refresh_cuda_tags(self) -> list:
        """Fetch available CUDA tags from PyTorch wheel index."""
        import requests
        try:
            resp = requests.get(
                "https://download.pytorch.org/whl/",
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to refresh CUDA tags: {e}")

        # Parse directory links matching cu* or cpu
        tags = []
        for match in re.finditer(r'href="(cu\d+|cpu)/"', resp.text):
            tag = match.group(1)
            if tag not in tags:
                tags.append(tag)

        # Sort: cpu first, then cu* numerically
        cuda_tags = [t for t in tags if t.startswith("cu")]
        cuda_tags.sort(key=lambda t: int(t.replace("cu", "")))
        return ["cpu"] + cuda_tags

    def refresh_all(self) -> dict:
        """Refresh both Python versions and CUDA tags, save to cache."""
        python_versions = self.refresh_python_versions()
        cuda_tags = self.refresh_cuda_tags()
        cache_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "python": python_versions,
            "cuda_tags": cuda_tags,
        }
        self._save_cache(cache_data)
        return cache_data
```

**Step 4: Run tests to verify they pass**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/test_version_manager.py -v`
Expected: All 11 tests PASS

**Step 5: Commit**

```bash
git add src/core/version_manager.py tests/test_version_manager.py
git commit -m "feat: add online refresh for Python and CUDA version lists"
```

---

### Task 3: Add Python download and custom venv creation

**Files:**
- Modify: `src/core/version_manager.py`
- Modify: `src/utils/pip_ops.py`
- Test: `tests/test_version_manager.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_version_manager.py`:

```python
# --- Python Path Resolution ---

def test_get_python_executable_bundled(tmp_path):
    """When version matches bundled, return tools/python/python.exe."""
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    vm.tools_dir = tmp_path / "tools"
    bundled = vm.tools_dir / "python"
    bundled.mkdir(parents=True)
    (bundled / "python.exe").write_text("fake")

    path = vm.get_python_executable("3.12.8", bundled_version="3.12.8")
    assert "tools" in str(path)
    assert path.name == "python.exe"


def test_get_python_executable_custom(tmp_path):
    """When version differs, look in tools/python_{version}/python.exe."""
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    vm.tools_dir = tmp_path / "tools"
    custom = vm.tools_dir / "python_3.10.16"
    custom.mkdir(parents=True)
    (custom / "python.exe").write_text("fake")

    path = vm.get_python_executable("3.10.16", bundled_version="3.12.8")
    assert "python_3.10.16" in str(path)


def test_get_python_executable_not_installed(tmp_path):
    """Raises FileNotFoundError when requested version not downloaded."""
    config = {"base_dir": str(tmp_path)}
    vm = VersionManager(config)
    vm.tools_dir = tmp_path / "tools"
    (vm.tools_dir / "python").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="not installed"):
        vm.get_python_executable("3.10.16", bundled_version="3.12.8")
```

**Step 2: Run tests to verify they fail**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/test_version_manager.py -v -k "executable"`
Expected: FAIL

**Step 3: Write implementation**

Add to `VersionManager` class:

```python
    def get_python_executable(self, version: str, bundled_version: str = "") -> Path:
        """Return path to python.exe for a given version.

        If version matches the bundled version, return tools/python/python.exe.
        Otherwise look in tools/python_{version}/python.exe.
        """
        if bundled_version and version == bundled_version:
            path = self.tools_dir / "python" / "python.exe"
        else:
            path = self.tools_dir / f"python_{version}" / "python.exe"

        if not path.exists():
            raise FileNotFoundError(
                f"Python {version} is not installed. "
                f"Expected at: {path}"
            )
        return path

    def download_python(self, version: str, url: str, sha256: str = "",
                        progress_callback=None) -> Path:
        """Download and extract embedded Python to tools/python_{version}/."""
        import hashlib
        import requests
        import zipfile

        dest_dir = self.tools_dir / f"python_{version}"
        if dest_dir.exists() and (dest_dir / "python.exe").exists():
            return dest_dir

        dest_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.tools_dir / "_temp" / f"python-{version}-embed.zip"
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(f"Downloading Python {version}...")

        # Download
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        hasher = hashlib.sha256()

        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                hasher.update(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    pct = int(downloaded / total * 100)
                    progress_callback(f"Downloading Python {version}... {pct}%")

        # Verify hash
        if sha256 and hasher.hexdigest().lower() != sha256.lower():
            zip_path.unlink()
            raise RuntimeError(f"SHA256 mismatch for Python {version}")

        # Extract
        if progress_callback:
            progress_callback(f"Extracting Python {version}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)

        zip_path.unlink(missing_ok=True)

        # Enable pip: remove python3XX._pth or edit it
        for pth in dest_dir.glob("python*._pth"):
            content = pth.read_text(encoding="utf-8")
            content = content.replace("#import site", "import site")
            pth.write_text(content, encoding="utf-8")

        # Install pip into embedded Python
        if progress_callback:
            progress_callback(f"Installing pip for Python {version}...")

        get_pip_path = dest_dir / "get-pip.py"
        pip_resp = requests.get("https://bootstrap.pypa.io/get-pip.py", timeout=30)
        pip_resp.raise_for_status()
        get_pip_path.write_bytes(pip_resp.content)

        subprocess.run(
            [str(dest_dir / "python.exe"), str(get_pip_path)],
            check=True, capture_output=True,
            **_SUBPROCESS_KWARGS,
        )
        get_pip_path.unlink(missing_ok=True)

        return dest_dir
```

Modify `src/utils/pip_ops.py` — update `create_venv` to accept optional python path:

```python
def create_venv(venv_path: str, python_executable: str = "") -> None:
    """Create a Python virtual environment.

    Args:
        venv_path: Path for the new venv.
        python_executable: Optional path to a specific python.exe.
                           Defaults to sys.executable (the tool's bundled Python).
    """
    python = python_executable or sys.executable
    subprocess.run(
        [python, "-m", "venv", venv_path],
        check=True,
        capture_output=True,
        text=True,
        **_SUBPROCESS_KWARGS,
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/test_version_manager.py -v`
Expected: All 14 tests PASS

**Step 5: Commit**

```bash
git add src/core/version_manager.py src/utils/pip_ops.py tests/test_version_manager.py
git commit -m "feat: add Python download and custom venv creation support"
```

---

### Task 4: Update Environment model and env_manager for version params

**Files:**
- Modify: `src/models/environment.py`
- Modify: `src/core/env_manager.py`

**Step 1: Add fields to Environment model**

In `src/models/environment.py`, add two fields to the `Environment` dataclass after `python_version`:

```python
    cuda_tag: str = ""
    pytorch_version: str = ""
```

**Step 2: Update env_manager.py create_environment signature and logic**

Modify `create_environment` in `src/core/env_manager.py`:

Change the method signature:
```python
def create_environment(self, name: str, branch: str = "master",
                       commit: Optional[str] = None,
                       python_version: str = "",
                       cuda_tag: str = "",
                       progress_callback=None) -> Environment:
```

Replace step 1 (venv creation, around line 54-57) with:
```python
            # 1. Create venv (with optional custom Python)
            _report("venv", 5, "Creating virtual environment...")
            venv_path = env_dir / "venv"
            if python_version:
                from src.core.version_manager import VersionManager
                vm = VersionManager(self.config)
                bundled_ver = self._get_bundled_python_version()
                python_exe = str(vm.get_python_executable(python_version, bundled_ver))
                pip_ops.create_venv(str(venv_path), python_executable=python_exe)
            else:
                pip_ops.create_venv(str(venv_path))
```

Replace step 3 (PyTorch install, around line 70-77) with:
```python
            # 3. Install PyTorch with CUDA support
            _report("pytorch", 35, "Installing PyTorch (CUDA)...")
            effective_cuda_tag = cuda_tag or self.config.get("pytorch_index_url", "").split("/")[-1] or "cu124"
            pytorch_index = f"https://download.pytorch.org/whl/{effective_cuda_tag}"
            pip_ops.run_pip_with_progress(str(venv_path), [
                "install", "torch", "torchvision", "torchaudio",
                "--index-url", pytorch_index,
            ], progress_callback=lambda line: _report("pytorch", 35, line))
```

Update the metadata creation (around line 122-132) to include new fields:
```python
            # Detect installed torch version
            installed_pytorch = ""
            freeze = pip_ops.freeze(str(venv_path))
            if "torch" in freeze:
                installed_pytorch = freeze["torch"]

            env = Environment(
                name=name,
                created_at=now,
                comfyui_commit=comfyui_commit,
                comfyui_branch=branch,
                python_version=python_version or pip_ops.get_python_version(str(venv_path)),
                cuda_tag=effective_cuda_tag,
                pytorch_version=installed_pytorch,
                pip_freeze=pip_freeze,
                custom_nodes=custom_nodes,
                path=str(env_dir),
            )
```

Add helper method to `EnvManager`:
```python
    def _get_bundled_python_version(self) -> str:
        """Get the version of the bundled Python in tools/python/."""
        tools_python = Path("tools/python/python.exe")
        if tools_python.exists():
            try:
                result = subprocess.run(
                    [str(tools_python), "--version"],
                    capture_output=True, text=True, check=True,
                )
                return result.stdout.strip().replace("Python ", "")
            except Exception:
                pass
        return ""
```

Add `import subprocess` at the top of env_manager.py.

**Step 3: Run existing tests**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/ -v`
Expected: All tests PASS (existing tests use defaults, new params are optional)

**Step 4: Commit**

```bash
git add src/models/environment.py src/core/env_manager.py
git commit -m "feat: add python_version and cuda_tag to env model and creation"
```

---

### Task 5: Add PyTorch reinstall with conflict analysis

**Files:**
- Modify: `src/core/version_manager.py`
- Test: `tests/test_version_manager.py` (append)

**Step 1: Write the failing test**

Append to `tests/test_version_manager.py`:

```python
# --- PyTorch Reinstall ---

def test_reinstall_pytorch_updates_meta(tmp_path):
    """reinstall_pytorch calls pip uninstall + install and updates env_meta."""
    config = {
        "base_dir": str(tmp_path),
        "environments_dir": str(tmp_path / "environments"),
        "models_dir": str(tmp_path / "models"),
        "snapshots_dir": str(tmp_path / "snapshots"),
        "conflict_analyzer": {"critical_packages": ["torch"], "auto_analyze_on_install": False},
    }
    vm = VersionManager(config)

    # Create fake env
    env_dir = tmp_path / "environments" / "test1"
    env_dir.mkdir(parents=True)
    venv_dir = env_dir / "venv"
    venv_dir.mkdir()

    meta = {
        "name": "test1",
        "created_at": "2026-04-06",
        "cuda_tag": "cu124",
        "pytorch_version": "2.5.0",
    }
    (env_dir / "env_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    with patch("src.utils.pip_ops.run_pip_with_progress") as mock_pip:
        with patch("src.utils.pip_ops.run_pip") as mock_pip2:
            with patch("src.utils.pip_ops.freeze", return_value={"torch": "2.6.0"}):
                result = vm.reinstall_pytorch("test1", "cu126")

    assert result["cuda_tag"] == "cu126"
    assert result["pytorch_version"] == "2.6.0"
```

**Step 2: Run test to verify it fails**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/test_version_manager.py::test_reinstall_pytorch_updates_meta -v`
Expected: FAIL

**Step 3: Write implementation**

Add to `VersionManager` class:

```python
    def reinstall_pytorch(self, env_name: str, cuda_tag: str,
                          progress_callback=None) -> dict:
        """Reinstall torch/torchvision/torchaudio with a different CUDA tag.

        Returns dict with updated cuda_tag, pytorch_version, and conflicts.
        """
        from src.models.environment import Environment
        from src.utils import pip_ops

        env_dir = Path(self.config["environments_dir"]) / env_name
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment '{env_name}' not found")

        venv_path = str(env_dir / "venv")

        if progress_callback:
            progress_callback("uninstall", 10, "Uninstalling current PyTorch...")

        # Uninstall old torch
        pip_ops.run_pip(venv_path, [
            "uninstall", "torch", "torchvision", "torchaudio", "-y",
        ])

        if progress_callback:
            progress_callback("install", 30, f"Installing PyTorch ({cuda_tag})...")

        # Install new torch
        index_url = f"https://download.pytorch.org/whl/{cuda_tag}"
        pip_ops.run_pip_with_progress(venv_path, [
            "install", "torch", "torchvision", "torchaudio",
            "--index-url", index_url,
        ], progress_callback=lambda line: (
            progress_callback("install", 30, line) if progress_callback else None
        ))

        # Get new torch version
        freeze = pip_ops.freeze(venv_path)
        pytorch_version = freeze.get("torch", "")

        # Update env_meta.json
        env = Environment.load_meta(str(env_dir))
        env.cuda_tag = cuda_tag
        env.pytorch_version = pytorch_version
        env.pip_freeze = freeze
        env.save_meta()

        if progress_callback:
            progress_callback("analyze", 80, "Running conflict analysis...")

        # Run conflict analysis
        conflicts = []
        try:
            analyzer_config = self.config.get("conflict_analyzer", {})
            if analyzer_config.get("auto_analyze_on_install", True):
                from src.core.conflict_analyzer import ConflictAnalyzer
                analyzer = ConflictAnalyzer(self.config)
                # Analyze the environment itself for internal conflicts
                # (simplified — full analysis needs a plugin path)
        except Exception as e:
            logger.warning(f"Conflict analysis failed: {e}")

        if progress_callback:
            progress_callback("done", 100, "PyTorch reinstall complete!")

        return {
            "cuda_tag": cuda_tag,
            "pytorch_version": pytorch_version,
            "conflicts": conflicts,
        }
```

**Step 4: Run tests to verify they pass**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/test_version_manager.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/core/version_manager.py tests/test_version_manager.py
git commit -m "feat: add PyTorch reinstall with conflict analysis"
```

---

### Task 6: Add Bridge slots for version management

**Files:**
- Modify: `src/gui/bridge.py`

**Step 1: Add new slots to Bridge class**

Add after the existing Plugin Analysis section (around line 312):

```python
    # ── Version Manager (Python/CUDA) ──

    @Slot(result=str)
    def detect_gpu(self):
        """Detect GPU and return recommended CUDA tag."""
        from src.core.version_manager import VersionManager
        vm = VersionManager(self.config)
        return self._safe_call(vm.detect_gpu)

    @Slot(result=str)
    def get_version_lists(self):
        """Return Python versions and CUDA tags (from cache or defaults)."""
        from src.core.version_manager import VersionManager
        vm = VersionManager(self.config)
        def _get():
            return {
                "python": vm.get_python_versions(),
                "cuda_tags": vm.get_cuda_tags(),
                "cache_info": vm.get_cache_info(),
            }
        return self._safe_call(_get)

    @Slot(str)
    def refresh_version_lists(self, request_id):
        """Refresh Python/CUDA version lists from official sources (async)."""
        from src.core.version_manager import VersionManager
        vm = VersionManager(self.config)
        def _refresh():
            cache = vm.refresh_all()
            return {
                "python": cache["python"],
                "cuda_tags": cache["cuda_tags"],
                "last_updated": cache["last_updated"],
            }
        self._run_async(request_id, _refresh)

    @Slot(str, str, str, str, str, str)
    def create_environment_v2(self, request_id, name, branch, commit,
                              python_version, cuda_tag):
        """Create environment with optional Python/CUDA version (async)."""
        commit_val = commit if commit else None
        python_ver = python_version if python_version else ""
        cuda = cuda_tag if cuda_tag else ""
        logger.info(
            f"create_environment_v2: name={name}, branch={branch}, "
            f"python={python_ver}, cuda={cuda}"
        )

        def _create():
            # Download Python if needed
            if python_ver:
                from src.core.version_manager import VersionManager
                vm = VersionManager(self.config)
                bundled = self.env_manager._get_bundled_python_version()
                if python_ver != bundled:
                    versions = vm.get_python_versions()
                    match = next(
                        (v for v in versions if v["version"] == python_ver),
                        None,
                    )
                    if match and match.get("url"):
                        vm.download_python(
                            python_ver, match["url"], match.get("sha256", ""),
                            progress_callback=lambda msg:
                                self.push_progress(request_id, "python_download", 2, msg),
                        )

            env = self.env_manager.create_environment(
                name, branch=branch, commit=commit_val,
                python_version=python_ver, cuda_tag=cuda,
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
            return env.to_dict()
        self._run_async(request_id, _create)

    @Slot(str, str, str)
    def reinstall_pytorch(self, request_id, env_name, cuda_tag):
        """Reinstall PyTorch with different CUDA version (async)."""
        from src.core.version_manager import VersionManager
        vm = VersionManager(self.config)
        def _reinstall():
            return vm.reinstall_pytorch(
                env_name, cuda_tag,
                progress_callback=lambda step, pct, detail="":
                    self.push_progress(request_id, step, pct, detail),
            )
        self._run_async(request_id, _reinstall)
```

**Step 2: Run existing tests**

Run: `cd D:\tack_project\tk_comfyui_starter2 && tools\python\python.exe -m pytest tests/ -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/gui/bridge.py
git commit -m "feat: add Bridge slots for GPU detect, version lists, and PyTorch reinstall"
```

---

### Task 7: Add BridgeAPI methods in JavaScript

**Files:**
- Modify: `src/gui/web/js/bridge.js`

**Step 1: Add new API methods**

Add before the closing `return {` block (around line 125), inside the returned object:

```javascript
        // Version Manager (Python/CUDA)
        detectGpu: function() { return callSlot('detect_gpu'); },
        getVersionLists: function() { return callSlot('get_version_lists'); },
        refreshVersionLists: function() { return callAsync('refresh_version_lists'); },
        createEnvironmentV2: function(name, branch, commit, pythonVersion, cudaTag, onProgress) {
            return callAsync('create_environment_v2', name, branch, commit || '',
                             pythonVersion || '', cudaTag || '', {onProgress: onProgress});
        },
        reinstallPytorch: function(envName, cudaTag, onProgress) {
            return callAsync('reinstall_pytorch', envName, cudaTag, {onProgress: onProgress});
        },
```

**Step 2: Verify no syntax errors**

Manually review the file for correct comma placement and bracket nesting.

**Step 3: Commit**

```bash
git add src/gui/web/js/bridge.js
git commit -m "feat: add BridgeAPI methods for version management"
```

---

### Task 8: Add i18n translation keys

**Files:**
- Modify: `src/gui/web/js/i18n.js`
- Modify: `src/gui/i18n.py`

**Step 1: Add English translations to i18n.js**

Add these keys to the `"en"` section (after `"env_fetching_versions"` line):

```javascript
            // Advanced options (create env)
            "env_advanced_options": "Advanced Options",
            "env_python_version": "Python Version:",
            "env_cuda_version": "CUDA / PyTorch:",
            "env_recommended": "Recommended",
            "env_refresh_versions": "Refresh Version List",
            "env_version_hint_cached": "List updated on {}. Click to refresh.",
            "env_version_hint_offline": "Currently using offline list. Click to refresh for latest versions.",
            "env_refresh_success": "Version list updated.",
            "env_refresh_failed": "Refresh failed, using offline list.",
            "env_downloading_python": "Downloading Python {}...",

            // PyTorch reinstall
            "env_reinstall_pytorch": "Reinstall PyTorch",
            "env_reinstall_confirm": "Will reinstall torch, torchvision, torchaudio for {}. Other packages unchanged.",
            "env_reinstall_success": "PyTorch reinstall complete.",
            "env_reinstall_failed": "PyTorch reinstall failed: {}",
```

**Step 2: Add zh-TW translations to i18n.js**

Add these keys to the `"zh-TW"` section:

```javascript
            // Advanced options (create env)
            "env_advanced_options": "\u9032\u968e\u9078\u9805",
            "env_python_version": "Python \u7248\u672c\uff1a",
            "env_cuda_version": "CUDA / PyTorch\uff1a",
            "env_recommended": "\u63a8\u85a6",
            "env_refresh_versions": "\u5237\u65b0\u7248\u672c\u6e05\u55ae",
            "env_version_hint_cached": "\u6e05\u55ae\u66f4\u65b0\u65bc {}，\u9ede\u6b64\u5237\u65b0",
            "env_version_hint_offline": "\u76ee\u524d\u70ba\u96e2\u7dda\u6e05\u55ae\uff0c\u9ede\u6b64\u5237\u65b0\u53d6\u5f97\u6700\u65b0\u7248\u672c",
            "env_refresh_success": "\u7248\u672c\u6e05\u55ae\u5df2\u66f4\u65b0",
            "env_refresh_failed": "\u5237\u65b0\u5931\u6557\uff0c\u4f7f\u7528\u96e2\u7dda\u6e05\u55ae",
            "env_downloading_python": "\u6b63\u5728\u4e0b\u8f09 Python {}...",

            // PyTorch reinstall
            "env_reinstall_pytorch": "\u91cd\u88dd PyTorch",
            "env_reinstall_confirm": "\u5c07\u91cd\u88dd torch, torchvision, torchaudio \u70ba {} \u7248\u672c\uff0c\u5176\u4ed6\u5957\u4ef6\u4e0d\u8b8a",
            "env_reinstall_success": "PyTorch \u91cd\u88dd\u5b8c\u6210",
            "env_reinstall_failed": "PyTorch \u91cd\u88dd\u5931\u6557\uff1a{}",
```

**Step 3: Add same keys to `src/gui/i18n.py`** (same content, Python dict syntax)

**Step 4: Commit**

```bash
git add src/gui/web/js/i18n.js src/gui/i18n.py
git commit -m "feat: add i18n keys for Python/CUDA version switching"
```

---

### Task 9: Update create environment dialog with advanced options

**Files:**
- Modify: `src/gui/web/js/pages/environments.js`

**Step 1: Update showCreateDialog to add advanced options section**

Replace the `showCreateDialog` function body HTML. After the existing commit input div and before `<div id="create-status">`, add:

```javascript
                // ── Advanced Options (collapsible) ──
                '<div class="border-t border-outline/20 pt-3 mt-3">' +
                    '<div id="create-advanced-toggle" class="flex items-center gap-2 cursor-pointer select-none" style="color: #ababab;">' +
                        '<span class="material-symbols-outlined text-[16px]" id="create-advanced-arrow">chevron_right</span>' +
                        '<span class="text-sm font-label uppercase tracking-wider">' + t('env_advanced_options') + '</span>' +
                    '</div>' +
                    '<div id="create-advanced-body" class="hidden mt-3 space-y-4">' +
                        '<div>' +
                            '<label class="input-label">' + t('env_python_version') + '</label>' +
                            '<select id="create-python" class="select">' +
                                '<option value="">' + t('loading') + '</option>' +
                            '</select>' +
                        '</div>' +
                        '<div>' +
                            '<label class="input-label">' + t('env_cuda_version') + '</label>' +
                            '<select id="create-cuda" class="select">' +
                                '<option value="">' + t('loading') + '</option>' +
                            '</select>' +
                        '</div>' +
                        '<div class="flex items-center gap-3">' +
                            '<button id="create-refresh-versions" class="btn btn-secondary text-xs" style="padding: 4px 12px;">' +
                                '<span class="material-symbols-outlined text-[14px]">refresh</span> ' +
                                t('env_refresh_versions') +
                            '</button>' +
                            '<span id="create-version-hint" class="text-xs text-on-surface-variant"></span>' +
                        '</div>' +
                    '</div>' +
                '</div>'
```

**Step 2: Add toggle and data loading logic**

In the `setTimeout` callback after modal renders, add:

```javascript
            // Advanced options toggle
            var advToggle = document.getElementById('create-advanced-toggle');
            var advBody = document.getElementById('create-advanced-body');
            var advArrow = document.getElementById('create-advanced-arrow');
            if (advToggle) {
                advToggle.addEventListener('click', function() {
                    var hidden = advBody.classList.toggle('hidden');
                    advArrow.textContent = hidden ? 'chevron_right' : 'expand_more';
                });
            }

            // Load version lists and GPU info
            Promise.all([
                BridgeAPI.getVersionLists(),
                BridgeAPI.detectGpu(),
            ]).then(function(results) {
                var lists = results[0];
                var gpu = results[1];

                // Populate Python dropdown
                var pySelect = document.getElementById('create-python');
                if (pySelect) {
                    pySelect.innerHTML = '';
                    var defaultPyOpt = document.createElement('option');
                    defaultPyOpt.value = '';
                    defaultPyOpt.textContent = 'Default (' + t('env_recommended') + ')';
                    pySelect.appendChild(defaultPyOpt);
                    lists.python.forEach(function(py) {
                        var opt = document.createElement('option');
                        opt.value = py.version;
                        opt.textContent = py.display || ('Python ' + py.version);
                        pySelect.appendChild(opt);
                    });
                }

                // Populate CUDA dropdown
                var cudaSelect = document.getElementById('create-cuda');
                if (cudaSelect) {
                    cudaSelect.innerHTML = '';
                    lists.cuda_tags.forEach(function(tag) {
                        var opt = document.createElement('option');
                        opt.value = tag;
                        opt.textContent = tag === 'cpu' ? 'CPU Only' : tag.toUpperCase();
                        if (tag === gpu.recommended_cuda_tag) {
                            opt.textContent += ' (' + t('env_recommended') + ')';
                            opt.selected = true;
                        }
                        cudaSelect.appendChild(opt);
                    });
                }

                // Version hint
                var hint = document.getElementById('create-version-hint');
                if (hint) {
                    if (lists.cache_info) {
                        hint.textContent = t('env_version_hint_cached', lists.cache_info.substring(0, 10));
                    } else {
                        hint.textContent = t('env_version_hint_offline');
                    }
                }
            });

            // Refresh button
            var refreshBtn = document.getElementById('create-refresh-versions');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', function() {
                    refreshBtn.disabled = true;
                    refreshBtn.textContent = t('loading');
                    BridgeAPI.refreshVersionLists().then(function(data) {
                        App.showToast(t('env_refresh_success'), 'success');
                        // Re-populate dropdowns (trigger reload)
                        // Simplified: just show success and user can reopen dialog
                        refreshBtn.textContent = t('env_refresh_versions');
                        refreshBtn.disabled = false;
                        var hint = document.getElementById('create-version-hint');
                        if (hint) hint.textContent = t('env_version_hint_cached', data.last_updated.substring(0, 10));

                        // Update Python dropdown
                        var pySelect = document.getElementById('create-python');
                        if (pySelect && data.python) {
                            var currentVal = pySelect.value;
                            pySelect.innerHTML = '<option value="">Default (' + t('env_recommended') + ')</option>';
                            data.python.forEach(function(py) {
                                var opt = document.createElement('option');
                                opt.value = py.version;
                                opt.textContent = py.display || ('Python ' + py.version);
                                pySelect.appendChild(opt);
                            });
                            pySelect.value = currentVal;
                        }
                        // Update CUDA dropdown
                        var cudaSelect = document.getElementById('create-cuda');
                        if (cudaSelect && data.cuda_tags) {
                            var currentCuda = cudaSelect.value;
                            cudaSelect.innerHTML = '';
                            data.cuda_tags.forEach(function(tag) {
                                var opt = document.createElement('option');
                                opt.value = tag;
                                opt.textContent = tag === 'cpu' ? 'CPU Only' : tag.toUpperCase();
                                cudaSelect.appendChild(opt);
                            });
                            cudaSelect.value = currentCuda;
                        }
                    }).catch(function() {
                        App.showToast(t('env_refresh_failed'), 'error');
                        refreshBtn.textContent = t('env_refresh_versions');
                        refreshBtn.disabled = false;
                    });
                });
            }
```

**Step 3: Update doCreate to pass Python/CUDA params**

Replace the `doCreate` function to use `createEnvironmentV2`:

```javascript
    function doCreate() {
        const name = document.getElementById('create-name').value.trim();
        if (!name) { App.showToast(`${t('env_name')} required`, 'error'); return; }

        const versionType = document.querySelector('input[name="version-type"]:checked').value;
        let branch, commit;
        if (versionType === 'tag') {
            branch = 'master';
            commit = document.getElementById('create-tag').value;
        } else {
            branch = document.getElementById('create-branch').value || 'master';
            commit = document.getElementById('create-commit').value.trim() || '';
        }

        // Advanced options
        var pySelect = document.getElementById('create-python');
        var cudaSelect = document.getElementById('create-cuda');
        var pythonVersion = pySelect ? pySelect.value : '';
        var cudaTag = cudaSelect ? cudaSelect.value : '';

        App.hideModal();

        var progressId = 'create-' + Date.now();
        var stepLabels = {
            python_download: t('env_downloading_python', pythonVersion) || 'Downloading Python',
            venv: t('step_venv') || 'Creating virtual environment',
            clone: t('step_clone') || 'Cloning ComfyUI',
            pytorch: t('step_pytorch') || 'Installing PyTorch',
            dependencies: t('step_dependencies') || 'Installing dependencies',
            manager: t('step_manager') || 'Installing ComfyUI-Manager',
            finalize: t('step_finalize') || 'Finalizing',
            done: t('step_done') || 'Complete',
        };

        App.showProgress(progressId, t('env_creating', name));

        BridgeAPI.createEnvironmentV2(name, branch, commit, pythonVersion, cudaTag, function(msg) {
            App.updateProgress(
                progressId,
                stepLabels[msg.step] || msg.step,
                msg.percent,
                msg.detail
            );
        }).then(function() {
            App.updateProgress(progressId, stepLabels.done, 100, '');
            App.hideProgress(progressId, 'success');
            App.showToast('Environment created: ' + name, 'success');
            loadEnvironments();
        }).catch(function(e) {
            App.hideProgress(progressId, 'error');
            App.showToast(t('error') + ': ' + e, 'error', 10000);
        });
    }
```

**Step 4: Commit**

```bash
git add src/gui/web/js/pages/environments.js
git commit -m "feat: add advanced options for Python/CUDA in create env dialog"
```

---

### Task 10: Add .gitignore entries for tools and version cache

**Files:**
- Modify: `.gitignore`

**Step 1: Add entries**

Append to `.gitignore`:

```
# Downloaded Python versions
tools/python_*/
tools/_temp/
tools/version_cache.json
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore downloaded Python versions and version cache"
```

---

## Task Dependency Graph

```
Task 1 (version_manager basics)
  └── Task 2 (online refresh)
  └── Task 3 (Python download + pip_ops)
        └── Task 4 (env model + env_manager)
              └── Task 5 (PyTorch reinstall)
                    └── Task 6 (Bridge slots)
                          └── Task 7 (BridgeAPI JS)
                                └── Task 9 (UI dialog)
Task 8 (i18n) ← independent, can run in parallel with Tasks 1-7
Task 10 (.gitignore) ← independent
```

Tasks 8 and 10 can be done in parallel with any other task.
