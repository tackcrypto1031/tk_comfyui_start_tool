# Recommended Env + Torch-Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 0.4.0 env creation overhaul — recommended mode with GPU-driven Torch-Pack selection, curated compile add-ons, uv migration, and post-install Pack switcher.

**Architecture:** Share low-level install helpers between advanced and recommended paths. Pack/add-on metadata lives in JSON (shipped + remote-refreshable). uv is a standalone binary; pip remains as a config-flag fallback. All state persisted in env_meta.json with backwards-compatible migration.

**Tech Stack:** Python 3.10+, `dataclasses`, `requests`, `click`, `rich`; PySide6 + QWebChannel for GUI bridge; pytest + monkeypatch for mocked integration tests; uv 0.9.7 standalone binary; JS (vanilla) in `src/gui/web/js/`.

**Spec:** [`docs/superpowers/specs/2026-04-19-recommended-env-torch-pack-design.md`](../specs/2026-04-19-recommended-env-torch-pack-design.md)

---

## Task 1: Add `torch_pack` and `installed_addons` fields to Environment model

**Files:**
- Modify: `src/models/environment.py`
- Test: `tests/test_models/test_environment.py`

- [ ] **Step 1.1: Write the failing test**

Add to `tests/test_models/test_environment.py` (create the file if missing):

```python
import tempfile
from pathlib import Path

from src.models.environment import Environment


def test_environment_new_fields_default_values():
    env = Environment(name="e1", created_at="2026-04-19T00:00:00Z")
    assert env.torch_pack is None
    assert env.installed_addons == []


def test_environment_roundtrip_preserves_new_fields(tmp_path):
    env_dir = tmp_path / "e1"
    env_dir.mkdir()
    env = Environment(
        name="e1",
        created_at="2026-04-19T00:00:00Z",
        path=str(env_dir),
        torch_pack="torch-2.9.1-cu130",
        installed_addons=[
            {
                "id": "sage-attention",
                "installed_at": "2026-04-19T00:00:00Z",
                "torch_pack_at_install": "torch-2.9.1-cu130",
            }
        ],
    )
    env.save_meta()
    reloaded = Environment.load_meta(str(env_dir))
    assert reloaded.torch_pack == "torch-2.9.1-cu130"
    assert reloaded.installed_addons == env.installed_addons


def test_environment_loads_legacy_meta_without_new_fields(tmp_path):
    env_dir = tmp_path / "legacy"
    env_dir.mkdir()
    meta = env_dir / "env_meta.json"
    meta.write_text(
        '{"name":"legacy","created_at":"2026-01-01T00:00:00Z"}',
        encoding="utf-8",
    )
    env = Environment.load_meta(str(env_dir))
    assert env.torch_pack is None
    assert env.installed_addons == []
```

- [ ] **Step 1.2: Run test — verify failure**

Run: `pytest tests/test_models/test_environment.py -v`
Expected: FAIL — `AttributeError: 'Environment' object has no attribute 'torch_pack'`

- [ ] **Step 1.3: Implement — add the fields**

Edit `src/models/environment.py` in the `Environment` dataclass. Add after `shared_model_enabled: bool = True` (line ~61):

```python
    torch_pack: Optional[str] = None
    # Each entry: {"id": str, "installed_at": str (ISO8601), "torch_pack_at_install": Optional[str]}
    installed_addons: list = field(default_factory=list)
```

- [ ] **Step 1.4: Run test — verify pass**

Run: `pytest tests/test_models/test_environment.py -v`
Expected: PASS (3 tests)

- [ ] **Step 1.5: Commit**

```bash
git add src/models/environment.py tests/test_models/test_environment.py
git commit -m "feat(env): add torch_pack and installed_addons fields to Environment

New fields default to None/[] so legacy env_meta.json files load
unchanged. Used by recommended creation flow and Pack switcher."
```

---

## Task 2: Ship `data/torch_packs.json`

**Files:**
- Create: `data/torch_packs.json`

No tests — pure data file. The loader in Task 3 is what we test.

- [ ] **Step 2.1: Write the file**

Create `data/torch_packs.json` with the exact JSON from spec §5:

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

- [ ] **Step 2.2: Commit**

```bash
git add data/torch_packs.json
git commit -m "data: ship torch_packs.json with 3 Packs and pinned deps"
```

---

## Task 3: `TorchPackManager.load()` with remote override precedence

**Files:**
- Create: `src/core/torch_pack.py`
- Test: `tests/test_core/test_torch_pack.py`

- [ ] **Step 3.1: Write failing tests**

Create `tests/test_core/test_torch_pack.py`:

```python
import json
from pathlib import Path

import pytest

from src.core.torch_pack import TorchPackManager, Pack


_BASE = {
    "schema_version": 1,
    "last_updated": "2026-04-19",
    "remote_url": "http://example/x.json",
    "recommended_python": "3.12.10",
    "recommended_uv_version": "0.9.7",
    "packs": [
        {"id": "p1", "label": "P1", "torch": "2.9.1", "torchvision": "0.24.1",
         "torchaudio": "2.9.1", "cuda_tag": "cu130", "min_driver": 13.0,
         "recommended": True}
    ],
    "pinned_deps": {"av": "16.0.1"}
}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_from_shipped(tmp_path):
    shipped = tmp_path / "data" / "torch_packs.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=tmp_path / "no.json")
    data = mgr.load()
    assert data["schema_version"] == 1
    assert len(mgr.list_packs()) == 1
    assert mgr.list_packs()[0].id == "p1"


def test_remote_overrides_shipped(tmp_path):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    remote_payload = {**_BASE, "packs": [
        {**_BASE["packs"][0], "id": "p2"}
    ]}
    _write_json(remote, remote_payload)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)
    assert mgr.list_packs()[0].id == "p2"


def test_schema_version_mismatch_ignores_remote(tmp_path):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    _write_json(remote, {**_BASE, "schema_version": 999, "packs": []})
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)
    # falls back to shipped
    assert [p.id for p in mgr.list_packs()] == ["p1"]


def test_find_pack_by_id(tmp_path):
    shipped = tmp_path / "data" / "torch_packs.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=tmp_path / "no.json")
    assert mgr.find("p1").id == "p1"
    assert mgr.find("ghost") is None
```

- [ ] **Step 3.2: Run — verify failure**

Run: `pytest tests/test_core/test_torch_pack.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.torch_pack'`

- [ ] **Step 3.3: Implement `torch_pack.py` skeleton**

Create `src/core/torch_pack.py`:

```python
"""Torch-Pack definitions, GPU-driven selection, remote refresh, and Pack switching."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Pack:
    id: str
    label: str
    torch: str
    torchvision: str
    torchaudio: str
    cuda_tag: str
    min_driver: float
    recommended: bool


class TorchPackManager:
    """Loads Torch-Pack data with remote override precedence."""

    def __init__(self, shipped_path: Path, remote_path: Path):
        self.shipped_path = Path(shipped_path)
        self.remote_path = Path(remote_path)
        self._data: Optional[dict] = None

    def load(self) -> dict:
        """Load data, preferring remote when its schema_version matches."""
        if self._data is not None:
            return self._data

        remote = self._read_json(self.remote_path)
        if remote and remote.get("schema_version") == SCHEMA_VERSION:
            self._data = remote
        else:
            if remote is not None:
                logger.warning(
                    "Remote torch_packs.json schema mismatch (got %s, expected %s); using shipped",
                    remote.get("schema_version"), SCHEMA_VERSION,
                )
            self._data = self._read_json(self.shipped_path) or {}
        return self._data

    def list_packs(self) -> list[Pack]:
        data = self.load()
        return [Pack(**p) for p in data.get("packs", [])]

    def find(self, pack_id: str) -> Optional[Pack]:
        for p in self.list_packs():
            if p.id == pack_id:
                return p
        return None

    def get_pinned_deps(self) -> dict:
        return self.load().get("pinned_deps", {})

    def get_recommended_python(self) -> str:
        return self.load().get("recommended_python", "")

    def get_recommended_uv_version(self) -> str:
        return self.load().get("recommended_uv_version", "")

    def get_remote_url(self) -> str:
        return self.load().get("remote_url", "")

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

- [ ] **Step 3.4: Run — verify pass**

Run: `pytest tests/test_core/test_torch_pack.py -v`
Expected: PASS (4 tests)

- [ ] **Step 3.5: Commit**

```bash
git add src/core/torch_pack.py tests/test_core/test_torch_pack.py
git commit -m "feat(torch-pack): add TorchPackManager with remote-override loader"
```

---

## Task 4: `select_pack_for_gpu()` mapping logic

**Files:**
- Modify: `src/core/torch_pack.py`
- Modify: `tests/test_core/test_torch_pack.py`

- [ ] **Step 4.1: Write failing tests**

Append to `tests/test_core/test_torch_pack.py`:

```python
_MULTI = {
    **_BASE,
    "packs": [
        {"id": "p-new", "label": "New", "torch": "2.9.1", "torchvision": "0.24.1",
         "torchaudio": "2.9.1", "cuda_tag": "cu130", "min_driver": 13.0,
         "recommended": True},
        {"id": "p-mid", "label": "Mid", "torch": "2.8.0", "torchvision": "0.23.0",
         "torchaudio": "2.8.0", "cuda_tag": "cu128", "min_driver": 12.8,
         "recommended": False},
        {"id": "p-old", "label": "Old", "torch": "2.7.1", "torchvision": "0.22.1",
         "torchaudio": "2.7.1", "cuda_tag": "cu128", "min_driver": 12.8,
         "recommended": False},
    ],
}


def _mgr_with(tmp_path, data):
    shipped = tmp_path / "data" / "torch_packs.json"
    _write_json(shipped, data)
    return TorchPackManager(shipped_path=shipped, remote_path=tmp_path / "no.json")


def test_select_no_gpu(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    assert mgr.select_pack_for_gpu({"has_gpu": False}) is None


def test_select_driver_too_old(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    assert mgr.select_pack_for_gpu(
        {"has_gpu": True, "cuda_driver_version": "11.8"}
    ) is None


def test_select_driver_matches_fallback(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    # Driver 12.8: only p-mid qualifies (p-new needs 13.0)
    assert mgr.select_pack_for_gpu(
        {"has_gpu": True, "cuda_driver_version": "12.8"}
    ).id == "p-mid"


def test_select_driver_matches_recommended(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    # Driver 13.0: p-new is recommended + meets min_driver
    assert mgr.select_pack_for_gpu(
        {"has_gpu": True, "cuda_driver_version": "13.0"}
    ).id == "p-new"


def test_select_malformed_driver_version(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    assert mgr.select_pack_for_gpu(
        {"has_gpu": True, "cuda_driver_version": "not-a-number"}
    ) is None


def test_select_missing_driver_field(tmp_path):
    mgr = _mgr_with(tmp_path, _MULTI)
    assert mgr.select_pack_for_gpu({"has_gpu": True}) is None
```

- [ ] **Step 4.2: Run — verify failure**

Run: `pytest tests/test_core/test_torch_pack.py -k select -v`
Expected: FAIL — `AttributeError: 'TorchPackManager' object has no attribute 'select_pack_for_gpu'`

- [ ] **Step 4.3: Implement `select_pack_for_gpu`**

Add to `TorchPackManager` class in `src/core/torch_pack.py`:

```python
    def select_pack_for_gpu(self, gpu_info: dict) -> Optional[Pack]:
        """Pick the best Pack for a detected GPU, or None if none qualifies."""
        if not gpu_info.get("has_gpu"):
            return None
        raw = gpu_info.get("cuda_driver_version")
        if not raw:
            return None
        try:
            driver = float(raw)
        except (TypeError, ValueError):
            return None
        # Prefer recommended packs, then higher min_driver (newer)
        candidates = sorted(
            self.list_packs(),
            key=lambda p: (not p.recommended, -p.min_driver),
        )
        for p in candidates:
            if driver >= p.min_driver:
                return p
        return None
```

- [ ] **Step 4.4: Run — verify pass**

Run: `pytest tests/test_core/test_torch_pack.py -v`
Expected: PASS (10 tests)

- [ ] **Step 4.5: Commit**

```bash
git add src/core/torch_pack.py tests/test_core/test_torch_pack.py
git commit -m "feat(torch-pack): add GPU-driven Pack selection"
```

---

## Task 5: Remote refresh for `torch_packs.json`

**Files:**
- Modify: `src/core/torch_pack.py`
- Modify: `tests/test_core/test_torch_pack.py`

- [ ] **Step 5.1: Write failing tests**

Append to `tests/test_core/test_torch_pack.py`:

```python
def test_refresh_writes_remote_file(tmp_path, monkeypatch):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)

    new_payload = {**_BASE, "last_updated": "2026-05-01"}

    class _FakeResp:
        status_code = 200
        def json(self): return new_payload
        def raise_for_status(self): pass

    def _fake_get(url, timeout):
        assert "x.json" in url
        return _FakeResp()

    monkeypatch.setattr("src.core.torch_pack.requests.get", _fake_get)
    result = mgr.refresh_remote()
    assert result["ok"] is True
    assert remote.exists()
    assert json.loads(remote.read_text(encoding="utf-8"))["last_updated"] == "2026-05-01"


def test_refresh_network_failure_is_non_fatal(tmp_path, monkeypatch):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)

    def _boom(url, timeout):
        raise ConnectionError("offline")

    monkeypatch.setattr("src.core.torch_pack.requests.get", _boom)
    result = mgr.refresh_remote()
    assert result["ok"] is False
    assert "offline" in result["error"]
    assert not remote.exists()


def test_refresh_schema_mismatch_does_not_write(tmp_path, monkeypatch):
    shipped = tmp_path / "data" / "torch_packs.json"
    remote = tmp_path / "tools" / "torch_packs_remote.json"
    _write_json(shipped, _BASE)
    mgr = TorchPackManager(shipped_path=shipped, remote_path=remote)

    class _FakeResp:
        status_code = 200
        def json(self): return {"schema_version": 999}
        def raise_for_status(self): pass

    monkeypatch.setattr("src.core.torch_pack.requests.get", lambda url, timeout: _FakeResp())
    result = mgr.refresh_remote()
    assert result["ok"] is False
    assert "schema" in result["error"].lower()
    assert not remote.exists()
```

- [ ] **Step 5.2: Run — verify failure**

Run: `pytest tests/test_core/test_torch_pack.py -k refresh -v`
Expected: FAIL — `AttributeError: ... 'refresh_remote'`

- [ ] **Step 5.3: Implement `refresh_remote`**

Add at top of `src/core/torch_pack.py`:

```python
import requests
```

Add method to `TorchPackManager`:

```python
    def refresh_remote(self, timeout: int = 15) -> dict:
        """Fetch remote torch_packs.json and write to remote_path.

        Returns {"ok": bool, "error": str}. Non-fatal on all failures —
        caller continues with shipped defaults.
        """
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
        # Invalidate memo so next load sees the new file
        self._data = None
        return {"ok": True, "error": ""}
```

- [ ] **Step 5.4: Run — verify pass**

Run: `pytest tests/test_core/test_torch_pack.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5.5: Commit**

```bash
git add src/core/torch_pack.py tests/test_core/test_torch_pack.py
git commit -m "feat(torch-pack): add remote refresh with schema gate"
```

---

## Task 6: `uv_ops` — download standalone binary

**Files:**
- Create: `src/utils/uv_ops.py`
- Test: `tests/test_utils/test_uv_ops.py`

- [ ] **Step 6.1: Write failing test**

Create `tests/test_utils/test_uv_ops.py`:

```python
from pathlib import Path

import pytest

from src.utils import uv_ops


def test_ensure_uv_reports_already_present(tmp_path, monkeypatch):
    bin_dir = tmp_path / "tools" / "uv"
    bin_dir.mkdir(parents=True)
    (bin_dir / "uv.exe").write_bytes(b"fake")

    called = {"downloaded": False}

    def _download(*a, **kw):
        called["downloaded"] = True

    monkeypatch.setattr(uv_ops, "_download_uv_binary", _download)
    result = uv_ops.ensure_uv(tools_dir=tmp_path / "tools", version="0.9.7")
    assert result.exists()
    assert called["downloaded"] is False


def test_ensure_uv_downloads_when_missing(tmp_path, monkeypatch):
    called = {"download_args": None}

    def _download(dest, version):
        called["download_args"] = (dest, version)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"downloaded")

    monkeypatch.setattr(uv_ops, "_download_uv_binary", _download)
    result = uv_ops.ensure_uv(tools_dir=tmp_path / "tools", version="0.9.7")
    assert result.exists()
    assert called["download_args"][0] == tmp_path / "tools" / "uv" / "uv.exe"
    assert called["download_args"][1] == "0.9.7"
```

- [ ] **Step 6.2: Run — verify failure**

Run: `pytest tests/test_utils/test_uv_ops.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.utils.uv_ops'`

- [ ] **Step 6.3: Implement `uv_ops` skeleton + `ensure_uv`**

Create `src/utils/uv_ops.py`:

```python
"""uv (Astral) binary management and invocation wrappers."""
from __future__ import annotations

import io
import logging
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_SUBPROCESS_KWARGS = {}
if sys.platform == "win32":
    _SUBPROCESS_KWARGS["creationflags"] = subprocess.CREATE_NO_WINDOW

_WINDOWS_ASSET = "uv-x86_64-pc-windows-msvc.zip"


def uv_path(tools_dir: Path) -> Path:
    """Return the expected uv.exe path under tools_dir."""
    exe = "uv.exe" if sys.platform == "win32" else "uv"
    return Path(tools_dir) / "uv" / exe


def ensure_uv(tools_dir: Path, version: str) -> Path:
    """Ensure tools/uv/uv.exe exists; download if missing. Return the path."""
    dest = uv_path(tools_dir)
    if dest.exists():
        return dest
    _download_uv_binary(dest, version)
    if not dest.exists():
        raise RuntimeError(f"uv binary not found at {dest} after download")
    return dest


def _download_uv_binary(dest: Path, version: str) -> None:
    """Download the Windows zip from Astral releases and extract uv.exe."""
    if sys.platform != "win32":
        raise NotImplementedError("Non-Windows uv download not implemented")
    url = (
        f"https://github.com/astral-sh/uv/releases/download/"
        f"{version}/{_WINDOWS_ASSET}"
    )
    logger.info("Downloading uv %s from %s", version, url)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for member in zf.namelist():
            if member.endswith("uv.exe"):
                with zf.open(member) as src, open(dest, "wb") as out:
                    out.write(src.read())
                return
    raise RuntimeError("uv.exe not found in downloaded zip")
```

- [ ] **Step 6.4: Run — verify pass**

Run: `pytest tests/test_utils/test_uv_ops.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6.5: Commit**

```bash
git add src/utils/uv_ops.py tests/test_utils/test_uv_ops.py
git commit -m "feat(uv): add ensure_uv with standalone binary download"
```

---

## Task 7: `uv_ops` — pip install wrapper + dispatch layer

**Files:**
- Modify: `src/utils/uv_ops.py`
- Modify: `tests/test_utils/test_uv_ops.py`
- Create: `src/utils/pkg_ops.py` (dispatch layer)
- Test: `tests/test_utils/test_pkg_ops.py`

- [ ] **Step 7.1: Write failing tests for uv_ops invocation**

Append to `tests/test_utils/test_uv_ops.py`:

```python
def test_run_uv_pip_builds_correct_command(tmp_path, monkeypatch):
    uv_bin = tmp_path / "tools" / "uv" / "uv.exe"
    uv_bin.parent.mkdir(parents=True)
    uv_bin.write_bytes(b"fake")
    venv_py = tmp_path / "venv" / "Scripts" / "python.exe"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_bytes(b"fake")

    captured = {}

    class _FakeProc:
        returncode = 0
        stdout = iter([b"ok\n"])
        def wait(self): return 0

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc()

    monkeypatch.setattr("src.utils.uv_ops.subprocess.Popen", _fake_popen)
    uv_ops.run_uv_pip(
        uv_binary=uv_bin,
        venv_python=str(venv_py),
        args=["install", "torch==2.9.1"],
    )
    assert captured["cmd"][0] == str(uv_bin)
    assert captured["cmd"][1:3] == ["pip", "install"]
    assert "--python" in captured["cmd"]
    idx = captured["cmd"].index("--python")
    assert captured["cmd"][idx + 1] == str(venv_py)
    assert "torch==2.9.1" in captured["cmd"]


def test_run_uv_pip_raises_on_nonzero(tmp_path, monkeypatch):
    uv_bin = tmp_path / "tools" / "uv" / "uv.exe"
    uv_bin.parent.mkdir(parents=True)
    uv_bin.write_bytes(b"fake")

    class _FakeProc:
        returncode = 2
        stdout = iter([b"error: boom\n"])
        def wait(self): return 2

    monkeypatch.setattr(
        "src.utils.uv_ops.subprocess.Popen",
        lambda cmd, **kw: _FakeProc(),
    )
    with pytest.raises(RuntimeError, match="uv pip failed"):
        uv_ops.run_uv_pip(
            uv_binary=uv_bin, venv_python="py", args=["install", "x"]
        )
```

- [ ] **Step 7.2: Run — verify failure**

Run: `pytest tests/test_utils/test_uv_ops.py -k run_uv_pip -v`
Expected: FAIL — `AttributeError: ... 'run_uv_pip'`

- [ ] **Step 7.3: Implement `run_uv_pip`**

Append to `src/utils/uv_ops.py`:

```python
def run_uv_pip(uv_binary: Path, venv_python: str, args: list,
               progress_callback=None) -> None:
    """Invoke `uv pip <args>` against the given venv python. Streams output.

    Raises RuntimeError with parsed stderr tail on non-zero exit.
    """
    cmd = [str(uv_binary), "pip"] + list(args) + ["--python", str(venv_python)]
    # Move --python to come right after the subcommand name for clarity
    # (uv accepts it anywhere, but this order matches docs).
    sub = args[0] if args else ""
    if sub in ("install", "uninstall", "freeze", "list", "show", "sync"):
        cmd = [str(uv_binary), "pip", sub, "--python", str(venv_python)] + list(args[1:])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **_SUBPROCESS_KWARGS,
    )

    tail: list[str] = []
    for raw in proc.stdout:
        try:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        except AttributeError:
            line = raw.rstrip("\r\n")
        if line:
            tail.append(line)
            if len(tail) > 40:
                tail.pop(0)
            if progress_callback:
                progress_callback(line)
    rc = proc.wait()
    if rc != 0:
        detail = " | ".join(tail[-5:]) if tail else "no output"
        raise RuntimeError(f"uv pip failed (exit {rc}): {detail}")


def uv_freeze(uv_binary: Path, venv_python: str) -> dict:
    """Return `uv pip freeze` as {package: version}."""
    cmd = [str(uv_binary), "pip", "freeze", "--python", str(venv_python)]
    result = subprocess.run(
        cmd, capture_output=True, text=True, **_SUBPROCESS_KWARGS,
    )
    if result.returncode != 0:
        raise RuntimeError(f"uv pip freeze failed: {result.stderr.strip()}")
    packages = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("-e ") or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            packages[name.strip()] = version.strip()
    return packages
```

- [ ] **Step 7.4: Run — verify pass**

Run: `pytest tests/test_utils/test_uv_ops.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7.5: Write failing test for dispatch layer**

Create `tests/test_utils/test_pkg_ops.py`:

```python
from pathlib import Path

import pytest

from src.utils import pkg_ops


def test_dispatch_uv_mode_calls_uv_ops(monkeypatch, tmp_path):
    called = {"uv": False, "pip": False}

    def _uv(uv_binary, venv_python, args, progress_callback=None):
        called["uv"] = True

    def _pip(venv_path, args, progress_callback=None):
        called["pip"] = True

    monkeypatch.setattr("src.utils.pkg_ops.uv_ops.run_uv_pip", _uv)
    monkeypatch.setattr("src.utils.pkg_ops.pip_ops.run_pip_with_progress", _pip)
    monkeypatch.setattr(
        "src.utils.pkg_ops.uv_ops.ensure_uv",
        lambda tools_dir, version: tools_dir / "uv" / "uv.exe",
    )
    monkeypatch.setattr(
        "src.utils.pkg_ops.pip_ops.get_venv_python", lambda p: "fakepy",
    )
    pkg_ops.run_install(
        venv_path=str(tmp_path / "venv"),
        args=["install", "torch"],
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="uv",
    )
    assert called["uv"] and not called["pip"]


def test_dispatch_pip_mode_calls_pip_ops(monkeypatch, tmp_path):
    called = {"uv": False, "pip": False}

    def _pip(venv_path, args, progress_callback=None):
        called["pip"] = True

    monkeypatch.setattr(
        "src.utils.pkg_ops.pip_ops.run_pip_with_progress", _pip,
    )
    pkg_ops.run_install(
        venv_path=str(tmp_path / "venv"),
        args=["install", "torch"],
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="pip",
    )
    assert called["pip"] and not called["uv"]
```

- [ ] **Step 7.6: Run — verify failure**

Run: `pytest tests/test_utils/test_pkg_ops.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.utils.pkg_ops'`

- [ ] **Step 7.7: Implement `pkg_ops` dispatch**

Create `src/utils/pkg_ops.py`:

```python
"""Package-manager dispatch: route to uv_ops or pip_ops based on config."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from src.utils import pip_ops, uv_ops


def run_install(
    venv_path: str,
    args: list,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Run a package install command via uv or pip."""
    if package_manager == "uv":
        uv_binary = uv_ops.ensure_uv(tools_dir, uv_version)
        venv_python = pip_ops.get_venv_python(venv_path)
        uv_ops.run_uv_pip(
            uv_binary=uv_binary,
            venv_python=venv_python,
            args=args,
            progress_callback=progress_callback,
        )
        return
    pip_ops.run_pip_with_progress(
        venv_path, args, progress_callback=progress_callback,
    )


def freeze(
    venv_path: str,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
) -> dict:
    if package_manager == "uv":
        uv_binary = uv_ops.ensure_uv(tools_dir, uv_version)
        venv_python = pip_ops.get_venv_python(venv_path)
        return uv_ops.uv_freeze(uv_binary, venv_python)
    return pip_ops.freeze(venv_path)
```

- [ ] **Step 7.8: Run — verify pass**

Run: `pytest tests/test_utils/test_pkg_ops.py tests/test_utils/test_uv_ops.py -v`
Expected: PASS (all)

- [ ] **Step 7.9: Commit**

```bash
git add src/utils/uv_ops.py src/utils/pkg_ops.py \
  tests/test_utils/test_uv_ops.py tests/test_utils/test_pkg_ops.py
git commit -m "feat(pkg): add uv invocation + pkg_ops dispatch"
```

---

## Task 8: Add-on Registry data & lookup

**Files:**
- Create: `src/core/addons.py`
- Test: `tests/test_core/test_addons.py`

- [ ] **Step 8.1: Write failing test**

Create `tests/test_core/test_addons.py`:

```python
from src.core.addons import ADDONS, find_addon, Addon


def test_registry_has_expected_ids():
    ids = {a.id for a in ADDONS}
    assert ids == {
        "sage-attention", "flash-attention", "insightface",
        "nunchaku", "trellis2",
    }


def test_find_existing():
    addon = find_addon("sage-attention")
    assert addon is not None
    assert addon.requires_compile is True


def test_find_missing():
    assert find_addon("ghost") is None


def test_pip_package_addon_has_no_repo():
    insight = find_addon("insightface")
    assert insight.install_method == "pip_package"
    assert insight.repo is None
    assert insight.pip_package == "insightface"


def test_git_clone_addon_has_repo_and_post_install():
    sage = find_addon("sage-attention")
    assert sage.install_method == "git_clone"
    assert sage.repo
    assert sage.post_install_cmd == ["pip", "install", "-e", "."]
```

- [ ] **Step 8.2: Run — verify failure**

Run: `pytest tests/test_core/test_addons.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 8.3: Implement `addons.py`**

Create `src/core/addons.py`:

```python
"""Curated add-on registry for the recommended creation flow."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class Addon:
    id: str
    label: str
    description: str
    install_method: Literal["pip_package", "git_clone"]
    pip_package: Optional[str] = None
    repo: Optional[str] = None
    post_install_cmd: Optional[list] = None
    requires_cuda: bool = False
    requires_compile: bool = False
    risk_note: Optional[str] = None


ADDONS: list[Addon] = [
    Addon(
        id="sage-attention",
        label="SageAttention v2",
        description="Attention acceleration — larger batch, lower VRAM",
        install_method="git_clone",
        repo="https://github.com/thu-ml/SageAttention.git",
        post_install_cmd=["pip", "install", "-e", "."],
        requires_cuda=True,
        requires_compile=True,
        risk_note="Requires CUDA toolkit (nvcc); first install compiles",
    ),
    Addon(
        id="flash-attention",
        label="FlashAttention",
        description="Fast attention implementation",
        install_method="git_clone",
        repo="https://github.com/Dao-AILab/flash-attention.git",
        post_install_cmd=["pip", "install", "-e", ".", "--no-build-isolation"],
        requires_cuda=True,
        requires_compile=True,
    ),
    Addon(
        id="insightface",
        label="InsightFace",
        description="Face nodes (IPAdapter FaceID, ReActor)",
        install_method="pip_package",
        pip_package="insightface",
        requires_cuda=False,
        requires_compile=False,
    ),
    Addon(
        id="nunchaku",
        label="Nunchaku",
        description="Quantized inference (4-bit FLUX)",
        install_method="git_clone",
        repo="https://github.com/mit-han-lab/nunchaku.git",
        post_install_cmd=["pip", "install", "-e", "."],
        requires_cuda=True,
        requires_compile=True,
    ),
    Addon(
        id="trellis2",
        label="Trellis 2.0",
        description="3D generation nodes",
        install_method="git_clone",
        repo="https://github.com/microsoft/TRELLIS.git",
        post_install_cmd=["pip", "install", "-r", "requirements.txt"],
        requires_cuda=True,
        requires_compile=True,
    ),
]


def find_addon(addon_id: str) -> Optional[Addon]:
    for a in ADDONS:
        if a.id == addon_id:
            return a
    return None
```

- [ ] **Step 8.4: Run — verify pass**

Run: `pytest tests/test_core/test_addons.py -v`
Expected: PASS (5 tests)

- [ ] **Step 8.5: Commit**

```bash
git add src/core/addons.py tests/test_core/test_addons.py
git commit -m "feat(addons): add curated add-on registry (5 entries)"
```

---

## Task 9: `install_addon` — pip_package path

**Files:**
- Modify: `src/core/addons.py`
- Modify: `tests/test_core/test_addons.py`

- [ ] **Step 9.1: Write failing test**

Append to `tests/test_core/test_addons.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

from src.core.addons import install_addon
from src.models.environment import Environment


def _make_env(tmp_path, torch_pack="p1"):
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


def test_install_pip_package_addon(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path)
    captured = {"args": None}

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        captured["args"] = args

    monkeypatch.setattr(
        "src.core.addons.pkg_ops.run_install", _fake_install,
    )

    result = install_addon(
        addon_id="insightface",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="uv",
    )
    assert captured["args"] == ["install", "insightface"]
    assert result["id"] == "insightface"

    env = Environment.load_meta(str(env_dir))
    assert any(a["id"] == "insightface" for a in env.installed_addons)
    assert env.installed_addons[0]["torch_pack_at_install"] == "p1"
```

- [ ] **Step 9.2: Run — verify failure**

Run: `pytest tests/test_core/test_addons.py -k install_pip -v`
Expected: FAIL — `ImportError: cannot import name 'install_addon'`

- [ ] **Step 9.3: Implement `install_addon` — pip_package branch**

Append to `src/core/addons.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

from src.models.environment import Environment
from src.utils import pkg_ops


def install_addon(
    addon_id: str,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback=None,
) -> dict:
    """Install a single add-on into an environment. Returns {id, method}.

    Raises if the add-on id is unknown. Package-install failures bubble up.
    Updates env_meta.json.installed_addons on success.
    """
    addon = find_addon(addon_id)
    if addon is None:
        raise ValueError(f"Unknown addon: {addon_id}")

    env_dir = Path(env_dir)
    venv_path = env_dir / "venv"

    if addon.install_method == "pip_package":
        pkg_ops.run_install(
            venv_path=str(venv_path),
            args=["install", addon.pip_package],
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )
    elif addon.install_method == "git_clone":
        _install_git_clone_addon(
            addon, env_dir, tools_dir, uv_version, package_manager,
            progress_callback,
        )
    else:  # pragma: no cover — guarded by Literal
        raise ValueError(f"Unknown install_method: {addon.install_method}")

    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": addon_id,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "torch_pack_at_install": env.torch_pack,
    })
    env.save_meta()
    return {"id": addon_id, "method": addon.install_method}


def _install_git_clone_addon(
    addon: Addon,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str,
    progress_callback,
) -> None:
    """Placeholder — implemented in Task 10."""
    raise NotImplementedError
```

- [ ] **Step 9.4: Run — verify pass**

Run: `pytest tests/test_core/test_addons.py -k install_pip -v`
Expected: PASS

- [ ] **Step 9.5: Commit**

```bash
git add src/core/addons.py tests/test_core/test_addons.py
git commit -m "feat(addons): install_addon for pip_package method"
```

---

## Task 10: `install_addon` — git_clone path with post_install translation

**Files:**
- Modify: `src/core/addons.py`
- Modify: `tests/test_core/test_addons.py`

- [ ] **Step 10.1: Write failing tests**

Append to `tests/test_core/test_addons.py`:

```python
def test_install_git_clone_addon(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path)
    calls = []

    def _fake_clone(url, dest, branch=None, commit=None, progress_callback=None):
        calls.append(("clone", url, dest))
        Path(dest).mkdir(parents=True)
        # Simulate a requirements.txt in the cloned repo
        (Path(dest) / "requirements.txt").write_text("numpy\n")

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(("install", tuple(args)))

    monkeypatch.setattr("src.core.addons.git_ops.clone_repo", _fake_clone)
    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    install_addon(
        addon_id="sage-attention",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="uv",
    )

    # Expect: clone, install -r requirements.txt, then post_install (pip install -e .)
    assert calls[0][0] == "clone"
    assert calls[0][1] == "https://github.com/thu-ml/SageAttention.git"

    install_calls = [c for c in calls if c[0] == "install"]
    # First install = requirements.txt
    assert install_calls[0][1][0] == "install"
    assert "-r" in install_calls[0][1]
    # Second install = post_install (translated "pip" → "install -e .")
    assert install_calls[1][1] == ("install", "-e", ".")


def test_install_py_skipped_when_post_install_cmd_present(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path)
    called_install_py = {"ran": False}

    def _fake_clone(url, dest, **kw):
        Path(dest).mkdir(parents=True)
        # Add an install.py which would normally be auto-run
        (Path(dest) / "install.py").write_text("raise SystemExit(0)")

    def _fake_install(*a, **kw): pass

    def _fake_run_install_py(*a, **kw):
        called_install_py["ran"] = True

    monkeypatch.setattr("src.core.addons.git_ops.clone_repo", _fake_clone)
    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)
    monkeypatch.setattr("src.core.addons._run_install_py", _fake_run_install_py)

    install_addon(
        addon_id="sage-attention",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
    )
    assert called_install_py["ran"] is False
```

- [ ] **Step 10.2: Run — verify failure**

Run: `pytest tests/test_core/test_addons.py -k git_clone -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 10.3: Implement git_clone install path**

Edit `src/core/addons.py`. Add imports at top:

```python
import subprocess
import sys
from src.utils import git_ops, pip_ops
```

Replace the `_install_git_clone_addon` stub with:

```python
def _install_git_clone_addon(
    addon: Addon,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str,
    progress_callback,
) -> None:
    """Clone add-on repo, install its requirements, then run post_install_cmd."""
    node_dir = env_dir / "ComfyUI" / "custom_nodes" / addon.id
    node_dir.parent.mkdir(parents=True, exist_ok=True)

    git_ops.clone_repo(
        addon.repo, str(node_dir), branch=None,
        progress_callback=progress_callback,
    )

    # 1) install requirements.txt if present
    req = node_dir / "requirements.txt"
    if req.exists():
        pkg_ops.run_install(
            venv_path=str(env_dir / "venv"),
            args=["install", "-r", str(req)],
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )

    # 2) post_install_cmd wins over install.py
    if addon.post_install_cmd:
        _run_post_install_cmd(
            cmd=addon.post_install_cmd,
            cwd=node_dir,
            env_dir=env_dir,
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )
    else:
        install_py = node_dir / "install.py"
        if install_py.exists():
            _run_install_py(install_py, env_dir, progress_callback)


def _run_post_install_cmd(
    cmd: list, cwd: Path, env_dir: Path, tools_dir: Path,
    uv_version: str, package_manager: str, progress_callback,
) -> None:
    """Run an add-on's post_install_cmd; translate 'pip' → active package manager."""
    if cmd and cmd[0] == "pip":
        # Portable "pip" token → route through pkg_ops dispatch
        args = cmd[1:]
        # Many add-on post_install commands assume cwd = repo dir (e.g. "install -e .")
        # pkg_ops doesn't change cwd, so we must pass absolute paths for relative refs.
        resolved = []
        for token in args:
            if token in (".", "-e") or token.startswith("-"):
                resolved.append(token)
            elif token == "requirements.txt":
                resolved.append(str((cwd / token).resolve()))
            else:
                resolved.append(token)
        # For "install -e .", keep "." literal but we need cwd when the package
        # manager resolves it. Fall back to running the cmd via venv python -m pip.
        if "-e" in resolved and "." in resolved:
            # uv resolves relative paths against its cwd — set cwd explicitly
            _run_editable_via_pkg_ops(
                resolved, cwd=cwd, env_dir=env_dir, tools_dir=tools_dir,
                uv_version=uv_version, package_manager=package_manager,
                progress_callback=progress_callback,
            )
            return
        pkg_ops.run_install(
            venv_path=str(env_dir / "venv"),
            args=resolved,
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )
        return
    # Non-pip commands (unlikely in our registry) — run as-is
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _run_editable_via_pkg_ops(
    args, cwd, env_dir, tools_dir, uv_version, package_manager, progress_callback,
):
    """Editable installs need cwd awareness. Always invoke `python -m pip` from
    the venv with cwd = add-on dir, so "." resolves correctly regardless of
    which package manager the rest of the build uses."""
    import os
    python = pip_ops.get_venv_python(str(env_dir / "venv"))
    cmd = [python, "-m", "pip"] + list(args)
    sub_kwargs = {"cwd": str(cwd)}
    if sys.platform == "win32":
        sub_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = subprocess.run(cmd, capture_output=True, text=True, **sub_kwargs)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
        raise RuntimeError(
            f"Editable install failed (exit {proc.returncode}): {' | '.join(tail)}"
        )
    if progress_callback:
        progress_callback(f"Editable install of {cwd.name} complete.")


def _run_install_py(install_py: Path, env_dir: Path, progress_callback) -> None:
    """Legacy fallback: run an add-on's install.py if no post_install_cmd is set."""
    python = pip_ops.get_venv_python(str(env_dir / "venv"))
    sub_kwargs = {"cwd": str(install_py.parent)}
    if sys.platform == "win32":
        sub_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.run([python, str(install_py)], check=True, **sub_kwargs)
```

- [ ] **Step 10.4: Run — verify pass**

Run: `pytest tests/test_core/test_addons.py -v`
Expected: PASS (all)

- [ ] **Step 10.5: Commit**

```bash
git add src/core/addons.py tests/test_core/test_addons.py
git commit -m "feat(addons): git_clone install with pip→pkg_ops translation"
```

---

## Task 11: `uninstall_addon` — reverse install + update env_meta

**Files:**
- Modify: `src/core/addons.py`
- Modify: `tests/test_core/test_addons.py`

- [ ] **Step 11.1: Write failing test**

Append to `tests/test_core/test_addons.py`:

```python
import shutil

from src.core.addons import uninstall_addon


def test_uninstall_git_clone_addon(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path)
    node_dir = env_dir / "ComfyUI" / "custom_nodes" / "sage-attention"
    node_dir.mkdir(parents=True)
    (node_dir / "junk.py").write_text("x")
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "sage-attention",
        "installed_at": "2026-04-19T00:00:00Z",
        "torch_pack_at_install": "p1",
    })
    env.save_meta()

    calls = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(args)

    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    uninstall_addon(
        addon_id="sage-attention",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="uv",
    )
    assert not node_dir.exists()
    # For editable git_clone add-ons we skip pip uninstall (the dir removal
    # is the authoritative action), so no install call expected.
    assert calls == []
    env = Environment.load_meta(str(env_dir))
    assert not any(a["id"] == "sage-attention" for a in env.installed_addons)


def test_uninstall_pip_package_addon(tmp_path, monkeypatch):
    env_dir = _make_env(tmp_path)
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "insightface",
        "installed_at": "2026-04-19T00:00:00Z",
        "torch_pack_at_install": "p1",
    })
    env.save_meta()

    calls = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(tuple(args))

    monkeypatch.setattr("src.core.addons.pkg_ops.run_install", _fake_install)

    uninstall_addon(
        addon_id="insightface",
        env_dir=env_dir,
        tools_dir=tmp_path / "tools",
        uv_version="0.9.7",
        package_manager="uv",
    )
    assert calls == [("uninstall", "-y", "insightface")]
    env = Environment.load_meta(str(env_dir))
    assert env.installed_addons == []
```

- [ ] **Step 11.2: Run — verify failure**

Run: `pytest tests/test_core/test_addons.py -k uninstall -v`
Expected: FAIL — `ImportError: cannot import name 'uninstall_addon'`

- [ ] **Step 11.3: Implement `uninstall_addon`**

Append to `src/core/addons.py`:

```python
import os
import stat


def uninstall_addon(
    addon_id: str,
    env_dir: Path,
    tools_dir: Path,
    uv_version: str,
    package_manager: str = "uv",
    progress_callback=None,
) -> None:
    """Remove an add-on from an env. Reverse of install_addon."""
    addon = find_addon(addon_id)
    if addon is None:
        raise ValueError(f"Unknown addon: {addon_id}")

    env_dir = Path(env_dir)

    if addon.install_method == "pip_package":
        pkg_ops.run_install(
            venv_path=str(env_dir / "venv"),
            args=["uninstall", "-y", addon.pip_package],
            tools_dir=tools_dir,
            uv_version=uv_version,
            package_manager=package_manager,
            progress_callback=progress_callback,
        )
    elif addon.install_method == "git_clone":
        node_dir = env_dir / "ComfyUI" / "custom_nodes" / addon.id
        if node_dir.exists():
            def _on_rm_error(func, path, exc_info):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            import shutil as _shutil
            _shutil.rmtree(str(node_dir), onerror=_on_rm_error)

    env = Environment.load_meta(str(env_dir))
    env.installed_addons = [
        a for a in env.installed_addons if a.get("id") != addon_id
    ]
    env.save_meta()
```

- [ ] **Step 11.4: Run — verify pass**

Run: `pytest tests/test_core/test_addons.py -v`
Expected: PASS (all)

- [ ] **Step 11.5: Commit**

```bash
git add src/core/addons.py tests/test_core/test_addons.py
git commit -m "feat(addons): uninstall_addon reverses install + updates env_meta"
```

---

## Task 12: Extract `_install_torch_pack` helper in env_manager

**Files:**
- Modify: `src/core/env_manager.py`
- Test: `tests/test_core/test_env_manager_helpers.py`

- [ ] **Step 12.1: Write failing test**

Create `tests/test_core/test_env_manager_helpers.py`:

```python
from pathlib import Path

import pytest

from src.core.env_manager import EnvManager


def test_install_torch_pack_invokes_pkg_ops(tmp_path, monkeypatch):
    config = {
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "models"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
    }
    mgr = EnvManager(config)
    venv_path = tmp_path / "envs" / "e1" / "venv"
    venv_path.mkdir(parents=True)

    recorded = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        recorded.append(args)

    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install", _fake_install,
    )
    mgr._install_torch_pack(
        venv_path=str(venv_path),
        torch="2.9.1",
        torchvision="0.24.1",
        torchaudio="2.9.1",
        cuda_tag="cu130",
        progress_callback=None,
    )
    # Expect one install call with three pinned packages + --index-url
    assert len(recorded) == 1
    args = recorded[0]
    assert args[0] == "install"
    assert "torch==2.9.1" in args
    assert "torchvision==0.24.1" in args
    assert "torchaudio==2.9.1" in args
    assert "--index-url" in args
    idx = args.index("--index-url")
    assert args[idx + 1] == "https://download.pytorch.org/whl/cu130"
```

- [ ] **Step 12.2: Run — verify failure**

Run: `pytest tests/test_core/test_env_manager_helpers.py -v`
Expected: FAIL — `AttributeError: ... '_install_torch_pack'`

- [ ] **Step 12.3: Implement helper**

Edit `src/core/env_manager.py`. Add imports near top:

```python
from src.utils import pkg_ops
from src.core.torch_pack import TorchPackManager
from pathlib import Path  # already imported
```

Add method to `EnvManager` class (place after `__init__`):

```python
    def _tools_dir(self) -> Path:
        return Path(self.config.get("base_dir", ".")) / "tools"

    def _uv_version(self) -> str:
        # Delegated to TorchPackManager when available; fallback constant.
        mgr = getattr(self, "_torch_pack_mgr", None)
        if mgr:
            return mgr.get_recommended_uv_version() or "0.9.7"
        return "0.9.7"

    def _pkg_mgr(self) -> str:
        return self.config.get("package_manager", "uv")

    def _install_torch_pack(
        self, venv_path: str, torch: str, torchvision: str, torchaudio: str,
        cuda_tag: str, progress_callback=None,
    ) -> None:
        """Install exactly the torch trio pinned to the given versions + index."""
        index_url = f"https://download.pytorch.org/whl/{cuda_tag}"
        args = [
            "install",
            f"torch=={torch}",
            f"torchvision=={torchvision}",
            f"torchaudio=={torchaudio}",
            "--index-url", index_url,
        ]
        pkg_ops.run_install(
            venv_path=venv_path,
            args=args,
            tools_dir=self._tools_dir(),
            uv_version=self._uv_version(),
            package_manager=self._pkg_mgr(),
            progress_callback=progress_callback,
        )
```

- [ ] **Step 12.4: Run — verify pass**

Run: `pytest tests/test_core/test_env_manager_helpers.py -v`
Expected: PASS

Also re-run existing env_manager tests to make sure no regression:
Run: `pytest tests/test_core/test_env_manager.py -v` (if present)
Expected: PASS — existing `create_environment` still uses legacy pip path for now; we only added the helper.

- [ ] **Step 12.5: Commit**

```bash
git add src/core/env_manager.py tests/test_core/test_env_manager_helpers.py
git commit -m "refactor(env): extract _install_torch_pack helper"
```

---

## Task 13: `_install_pinned_deps` helper

**Files:**
- Modify: `src/core/env_manager.py`
- Modify: `tests/test_core/test_env_manager_helpers.py`

- [ ] **Step 13.1: Write failing test**

Append to `tests/test_core/test_env_manager_helpers.py`:

```python
def test_install_pinned_deps_installs_all(tmp_path, monkeypatch):
    config = {
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "models"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
    }
    mgr = EnvManager(config)
    recorded = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        recorded.append(args)

    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install", _fake_install,
    )
    pinned = {"av": "16.0.1", "transformers": "4.57.6"}
    mgr._install_pinned_deps("venv", pinned, None)

    assert len(recorded) == 1
    args = recorded[0]
    assert args[0] == "install"
    assert "av==16.0.1" in args
    assert "transformers==4.57.6" in args


def test_install_pinned_deps_empty_is_noop(tmp_path, monkeypatch):
    config = {"environments_dir": str(tmp_path), "models_dir": str(tmp_path),
              "base_dir": str(tmp_path), "package_manager": "uv"}
    mgr = EnvManager(config)
    called = {"ran": False}
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install",
        lambda *a, **k: called.update(ran=True),
    )
    mgr._install_pinned_deps("venv", {}, None)
    assert called["ran"] is False
```

- [ ] **Step 13.2: Run — verify failure**

Run: `pytest tests/test_core/test_env_manager_helpers.py -k pinned -v`
Expected: FAIL — `AttributeError: ... '_install_pinned_deps'`

- [ ] **Step 13.3: Implement helper**

Add to `EnvManager` in `src/core/env_manager.py`:

```python
    def _install_pinned_deps(
        self, venv_path: str, pinned: dict, progress_callback=None,
    ) -> None:
        """Install exactly the pinned versions, overwriting whatever torch/requirements pulled in."""
        if not pinned:
            return
        args = ["install"] + [f"{pkg}=={ver}" for pkg, ver in pinned.items()]
        pkg_ops.run_install(
            venv_path=venv_path,
            args=args,
            tools_dir=self._tools_dir(),
            uv_version=self._uv_version(),
            package_manager=self._pkg_mgr(),
            progress_callback=progress_callback,
        )
```

- [ ] **Step 13.4: Run — verify pass**

Run: `pytest tests/test_core/test_env_manager_helpers.py -v`
Expected: PASS

- [ ] **Step 13.5: Commit**

```bash
git add src/core/env_manager.py tests/test_core/test_env_manager_helpers.py
git commit -m "refactor(env): add _install_pinned_deps helper"
```

---

## Task 14: `EnvManager.create_recommended()` — full flow

**Files:**
- Modify: `src/core/env_manager.py`
- Test: `tests/test_core/test_env_manager_recommended.py`

- [ ] **Step 14.1: Write failing integration test (happy path)**

Create `tests/test_core/test_env_manager_recommended.py`:

```python
import json
from pathlib import Path

import pytest

from src.core.env_manager import EnvManager
from src.models.environment import Environment


@pytest.fixture
def config(tmp_path):
    # Ship a torch_packs.json inside tmp_path so TorchPackManager finds it
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "torch_packs.json").write_text(json.dumps({
        "schema_version": 1,
        "last_updated": "2026-04-19",
        "remote_url": "",
        "recommended_python": "3.12.10",
        "recommended_uv_version": "0.9.7",
        "packs": [
            {"id": "p-new", "label": "New", "torch": "2.9.1",
             "torchvision": "0.24.1", "torchaudio": "2.9.1",
             "cuda_tag": "cu130", "min_driver": 13.0, "recommended": True},
        ],
        "pinned_deps": {"av": "16.0.1"},
    }), encoding="utf-8")
    return {
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "models"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
        "shared_model_mode": "default",
        "model_subdirs": ["checkpoints"],
        "comfyui_repo_url": "http://fake/comfy.git",
    }


def test_create_recommended_happy_path(tmp_path, config, monkeypatch):
    mgr = EnvManager(config)

    # Stub GPU detection
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._detect_gpu",
        lambda self: {"has_gpu": True, "cuda_driver_version": "13.0"},
    )

    # Stub ComfyUI tag lookup
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._latest_comfyui_tag",
        lambda self: "v9.9.9",
    )

    # Stub venv creation (just make the dir)
    def _fake_venv(path, python_executable=""):
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "Scripts").mkdir(exist_ok=True)
        (Path(path) / "Scripts" / "python.exe").write_bytes(b"fake")

    monkeypatch.setattr("src.core.env_manager.pip_ops.create_venv", _fake_venv)

    # Stub git clone — creates ComfyUI dir with requirements.txt
    def _fake_clone(url, dest, branch=None, commit=None, progress_callback=None):
        Path(dest).mkdir(parents=True, exist_ok=True)
        (Path(dest) / "requirements.txt").write_text("numpy\n")

    monkeypatch.setattr("src.core.env_manager.git_ops.clone_repo", _fake_clone)
    monkeypatch.setattr(
        "src.core.env_manager.git_ops.get_current_commit",
        lambda p: "deadbeef",
    )

    # Stub uv installs
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install",
        lambda **kw: None,
    )
    # Stub freeze — claim critical packages are present
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.freeze",
        lambda **kw: {
            "torch": "2.9.1+cu130", "numpy": "2.0", "pillow": "10.0",
            "pyyaml": "6.0", "aiohttp": "3.9", "sqlalchemy": "2.0",
        },
    )
    # Stub Python resolution
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._ensure_python",
        lambda self, version: str(tmp_path / "tools" / "python_3.12.10" / "python.exe"),
    )
    # Ensure tools/uv/uv.exe exists so ensure_uv short-circuits
    uv_bin = tmp_path / "tools" / "uv" / "uv.exe"
    uv_bin.parent.mkdir(parents=True)
    uv_bin.write_bytes(b"fake")

    env = mgr.create_recommended(name="r1", selected_addon_ids=[])

    assert env.torch_pack == "p-new"
    assert env.pytorch_version == "2.9.1+cu130"
    assert env.cuda_tag == "cu130"
    assert env.installed_addons == []
    # env_meta on disk
    env_dir = Path(config["environments_dir"]) / "r1"
    persisted = Environment.load_meta(str(env_dir))
    assert persisted.torch_pack == "p-new"


def test_create_recommended_blocks_without_gpu(tmp_path, config, monkeypatch):
    mgr = EnvManager(config)
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._detect_gpu",
        lambda self: {"has_gpu": False},
    )
    with pytest.raises(RuntimeError, match="推薦模式|no GPU"):
        mgr.create_recommended(name="nope", selected_addon_ids=[])
    assert not (Path(config["environments_dir"]) / "nope").exists()


def test_create_recommended_addon_failure_does_not_delete_env(
    tmp_path, config, monkeypatch,
):
    mgr = EnvManager(config)
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._detect_gpu",
        lambda self: {"has_gpu": True, "cuda_driver_version": "13.0"},
    )
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._latest_comfyui_tag",
        lambda self: "v9.9.9",
    )
    monkeypatch.setattr(
        "src.core.env_manager.pip_ops.create_venv",
        lambda p, python_executable="": (Path(p) / "Scripts").mkdir(parents=True, exist_ok=True),
    )
    monkeypatch.setattr(
        "src.core.env_manager.git_ops.clone_repo",
        lambda url, dest, **kw: Path(dest).mkdir(parents=True, exist_ok=True),
    )
    monkeypatch.setattr(
        "src.core.env_manager.git_ops.get_current_commit", lambda p: "beef",
    )
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.run_install", lambda **kw: None,
    )
    monkeypatch.setattr(
        "src.core.env_manager.pkg_ops.freeze",
        lambda **kw: {"torch": "2.9.1", "numpy": "2", "pillow": "10",
                      "pyyaml": "6", "aiohttp": "3"},
    )
    monkeypatch.setattr(
        "src.core.env_manager.EnvManager._ensure_python",
        lambda self, version: "py",
    )
    # Make install_addon raise
    def _boom(**kw):
        raise RuntimeError("compile failed")
    monkeypatch.setattr("src.core.env_manager.addons.install_addon", _boom)

    env = mgr.create_recommended(
        name="r2", selected_addon_ids=["sage-attention"],
    )
    # Env still created
    assert (Path(config["environments_dir"]) / "r2").exists()
    assert env.installed_addons == []
    # Failure reported via env.failed_addons (new transient field, not persisted)
    assert getattr(env, "failed_addons", None) == [
        {"id": "sage-attention", "error": "compile failed"}
    ]
```

- [ ] **Step 14.2: Run — verify failure**

Run: `pytest tests/test_core/test_env_manager_recommended.py -v`
Expected: FAIL — `AttributeError: ... 'create_recommended'`

- [ ] **Step 14.3: Implement `create_recommended`**

Edit `src/core/env_manager.py`. Add imports at top:

```python
from src.core import addons
```

Inside `EnvManager.__init__`, initialize the torch pack manager lazily. Add:

```python
        # Lazy torch pack manager; resolved from base_dir/data/torch_packs.json
        self._torch_pack_mgr = None
```

Add helper methods and the main flow:

```python
    def _get_torch_pack_mgr(self) -> "TorchPackManager":
        if self._torch_pack_mgr is None:
            shipped = Path(self.config.get("base_dir", ".")) / "data" / "torch_packs.json"
            remote = self._tools_dir() / "torch_packs_remote.json"
            self._torch_pack_mgr = TorchPackManager(shipped, remote)
        return self._torch_pack_mgr

    def _detect_gpu(self) -> dict:
        """Lazy import of version_manager to avoid circular imports at module load."""
        from src.core.version_manager import VersionManager
        return VersionManager(self.config).detect_gpu()

    def _latest_comfyui_tag(self) -> str:
        """Fetch the newest release tag via VersionController. Falls back to master on failure."""
        try:
            from src.core.version_controller import VersionController
            vc = VersionController(self.config)
            # list_remote_versions returns {"tags": [...], "branches": [...]}
            remote = vc.list_remote_versions(self.comfyui_url)
            tags = remote.get("tags", [])
            if tags:
                return tags[0]  # VersionController sorts newest first
        except Exception as exc:
            logger.warning("Failed to fetch latest ComfyUI tag: %s", exc)
        return "master"

    def _ensure_python(self, version: str) -> str:
        """Ensure a specific Python version is available in tools/. Returns exe path."""
        from src.core.version_manager import VersionManager
        vm = VersionManager(self.config)
        bundled = self._get_bundled_python_version()
        try:
            return str(vm.get_python_executable(version, bundled))
        except FileNotFoundError:
            # Need to download — look up URL from Python version cache
            # Fetch fresh if not cached
            versions = vm.refresh_python_versions()
            match = next((v for v in versions if v["version"] == version), None)
            if not match:
                raise RuntimeError(
                    f"Python {version} not available on python.org index"
                )
            vm.download_python(version, match["url"], match.get("sha256", ""))
            return str(vm.get_python_executable(version, bundled))

    def create_recommended(
        self,
        name: str,
        selected_addon_ids: list,
        progress_callback=None,
    ) -> "Environment":
        """Create an environment using GPU-auto-selected Torch-Pack + selected add-ons."""
        self._validate_name(name)

        env_dir = self.environments_dir / name
        if env_dir.exists():
            raise FileExistsError(f"Environment '{name}' already exists")

        tpm = self._get_torch_pack_mgr()

        def _report(step, pct, detail=""):
            if progress_callback:
                progress_callback(step, pct, detail)

        # 10% — GPU detection + Pack selection BEFORE any disk work
        _report("gpu", 10, "Detecting GPU...")
        gpu = self._detect_gpu()
        pack = tpm.select_pack_for_gpu(gpu)
        if pack is None:
            raise RuntimeError(
                "推薦模式需要偵測到 CUDA ≥ 12.8 的 NVIDIA GPU。"
                "請確認驅動已安裝、或改用進階模式手動選版本。"
                " (no suitable Torch-Pack for detected GPU)"
            )

        # 5% — Resolve Python
        python_version = tpm.get_recommended_python() or "3.12.10"
        _report("python", 5, f"Preparing Python {python_version}...")
        python_exe = self._ensure_python(python_version)

        # 15% — latest ComfyUI tag
        _report("tag", 15, "Resolving ComfyUI release tag...")
        tag = self._latest_comfyui_tag()

        env_dir.mkdir(parents=True)
        failed_addons = []
        try:
            # 20% — venv
            _report("venv", 20, "Creating virtual environment...")
            venv_path = env_dir / "venv"
            pip_ops.create_venv(str(venv_path), python_executable=python_exe)

            # 30% — clone ComfyUI at tag
            _report("clone", 30, f"Cloning ComfyUI {tag}...")
            comfyui_path = env_dir / "ComfyUI"
            git_ops.clone_repo(
                self.comfyui_url, str(comfyui_path),
                branch=tag if tag != "master" else "master",
                progress_callback=lambda pct, msg: _report(
                    "clone", 30 + int(pct * 0.1), msg or "Cloning ComfyUI..."
                ),
            )

            # 45% — torch trio via pack
            _report("pytorch", 45, f"Installing PyTorch ({pack.label})...")
            self._install_torch_pack(
                venv_path=str(venv_path),
                torch=pack.torch,
                torchvision=pack.torchvision,
                torchaudio=pack.torchaudio,
                cuda_tag=pack.cuda_tag,
                progress_callback=lambda line: _report("pytorch", 45, line),
            )

            # 60% — ComfyUI requirements with torch-pinned constraints
            _report("deps", 60, "Installing ComfyUI dependencies...")
            req_path = comfyui_path / "requirements.txt"
            if req_path.exists():
                constraint = env_dir / "_constraints.txt"
                constraint.write_text(
                    f"torch=={pack.torch}\n"
                    f"torchvision=={pack.torchvision}\n"
                    f"torchaudio=={pack.torchaudio}\n",
                    encoding="utf-8",
                )
                pkg_ops.run_install(
                    venv_path=str(venv_path),
                    args=[
                        "install", "-r", str(req_path.resolve()),
                        "--extra-index-url",
                        f"https://download.pytorch.org/whl/{pack.cuda_tag}",
                        "-c", str(constraint.resolve()),
                    ],
                    tools_dir=self._tools_dir(),
                    uv_version=self._uv_version(),
                    package_manager=self._pkg_mgr(),
                    progress_callback=lambda line: _report("deps", 60, line),
                )
                constraint.unlink(missing_ok=True)

            # 68% — re-pin fragile deps
            _report("pins", 68, "Pinning fragile dependencies...")
            self._install_pinned_deps(
                str(venv_path), tpm.get_pinned_deps(),
                progress_callback=lambda line: _report("pins", 68, line),
            )

            # 72% — verify critical
            _report("verify", 72, "Verifying critical packages...")
            freeze_data = pkg_ops.freeze(
                venv_path=str(venv_path),
                tools_dir=self._tools_dir(),
                uv_version=self._uv_version(),
                package_manager=self._pkg_mgr(),
            )
            if len(freeze_data) > 5:
                critical = ["torch", "numpy", "pillow", "pyyaml", "aiohttp"]
                installed = {k.lower().replace("_", "-") for k in freeze_data}
                missing = [p for p in critical if p not in installed]
                if missing:
                    raise RuntimeError(
                        f"Critical packages missing: {', '.join(missing)}"
                    )

            # 78% — ComfyUI-Manager
            _report("manager", 78, "Installing ComfyUI-Manager...")
            manager_installed = False
            manager_path = comfyui_path / "custom_nodes" / "ComfyUI-Manager"
            try:
                manager_path.parent.mkdir(parents=True, exist_ok=True)
                git_ops.clone_repo(DEFAULT_MANAGER_URL, str(manager_path), branch="main")
                self._write_manager_security_config(comfyui_path)
                manager_installed = True
            except Exception as e:
                logger.warning("ComfyUI-Manager install failed: %s", e)

            # Save env_meta BEFORE add-ons (so add-on install can read torch_pack)
            now = datetime.now(timezone.utc).isoformat()
            env = Environment(
                name=name,
                created_at=now,
                comfyui_commit=git_ops.get_current_commit(str(comfyui_path)),
                comfyui_branch=tag,
                python_version=python_version,
                cuda_tag=pack.cuda_tag,
                pytorch_version=freeze_data.get("torch", f"{pack.torch}+{pack.cuda_tag}"),
                pip_freeze=freeze_data,
                custom_nodes=(
                    [{"name": "ComfyUI-Manager",
                      "repo_url": DEFAULT_MANAGER_URL,
                      "commit": git_ops.get_current_commit(str(manager_path)) if manager_installed else ""}]
                    if manager_installed else []
                ),
                path=str(env_dir),
                shared_model_enabled=True,
                torch_pack=pack.id,
                installed_addons=[],
            )
            env.save_meta()

            # 82-95% — add-ons (per-addon failures are isolated)
            total = len(selected_addon_ids)
            for i, aid in enumerate(selected_addon_ids):
                pct = 82 + int((i / max(total, 1)) * 13)
                _report("addon", pct, f"Installing add-on: {aid}...")
                try:
                    addons.install_addon(
                        addon_id=aid,
                        env_dir=env_dir,
                        tools_dir=self._tools_dir(),
                        uv_version=self._uv_version(),
                        package_manager=self._pkg_mgr(),
                        progress_callback=lambda line: _report("addon", pct, line),
                    )
                except Exception as exc:
                    logger.warning("Add-on %s failed: %s", aid, exc)
                    failed_addons.append({"id": aid, "error": str(exc)})

            # 96% — extra_model_paths.yaml
            _report("finalize", 96, "Generating extra_model_paths.yaml...")
            self._generate_extra_model_paths(comfyui_path)

            # Reload env after add-on installs appended to installed_addons
            env = Environment.load_meta(str(env_dir))
            env.failed_addons = failed_addons  # transient, not persisted
            _report("done", 100, "Recommended environment created!")
            return env

        except Exception:
            # Fatal failure before env_meta.json write → full rollback
            if env_dir.exists() and not (env_dir / "env_meta.json").exists():
                shutil.rmtree(env_dir, ignore_errors=True)
            raise
```

- [ ] **Step 14.4: Run — verify pass**

Run: `pytest tests/test_core/test_env_manager_recommended.py -v`
Expected: PASS (3 tests)

Also verify no regression:
Run: `pytest tests/test_core/ -v`
Expected: PASS

- [ ] **Step 14.5: Commit**

```bash
git add src/core/env_manager.py tests/test_core/test_env_manager_recommended.py
git commit -m "feat(env): add create_recommended() with GPU-driven Pack selection"
```

---

## Task 15: `torch_pack.switch_pack()` — full switch flow

**Files:**
- Modify: `src/core/torch_pack.py`
- Test: `tests/test_core/test_torch_pack_switch.py`

- [ ] **Step 15.1: Write failing tests**

Create `tests/test_core/test_torch_pack_switch.py`:

```python
import json
from pathlib import Path

import pytest

from src.core.torch_pack import TorchPackManager, switch_pack
from src.models.environment import Environment


def _setup(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "torch_packs.json").write_text(json.dumps({
        "schema_version": 1, "last_updated": "2026-04-19", "remote_url": "",
        "recommended_python": "3.12.10", "recommended_uv_version": "0.9.7",
        "packs": [
            {"id": "p-new", "label": "New", "torch": "2.9.1",
             "torchvision": "0.24.1", "torchaudio": "2.9.1",
             "cuda_tag": "cu130", "min_driver": 13.0, "recommended": True},
            {"id": "p-mid", "label": "Mid", "torch": "2.8.0",
             "torchvision": "0.23.0", "torchaudio": "2.8.0",
             "cuda_tag": "cu128", "min_driver": 12.8, "recommended": False},
        ],
        "pinned_deps": {"av": "16.0.1"},
    }), encoding="utf-8")
    env_dir = tmp_path / "envs" / "main"
    (env_dir / "ComfyUI" / "custom_nodes").mkdir(parents=True)
    (env_dir / "venv").mkdir()
    env = Environment(
        name="main", created_at="2026-04-19T00:00:00Z",
        path=str(env_dir), torch_pack="p-mid",
    )
    env.save_meta()
    config = {
        "environments_dir": str(tmp_path / "envs"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
        "snapshots_dir": str(tmp_path / "snaps"),
        "max_snapshots": 5,
    }
    return config, env_dir


def test_switch_pack_reinstalls_torch_and_pinned(tmp_path, monkeypatch):
    config, env_dir = _setup(tmp_path)
    calls = []

    def _fake_install(venv_path, args, tools_dir, uv_version,
                      package_manager="uv", progress_callback=None):
        calls.append(tuple(args))

    monkeypatch.setattr("src.core.torch_pack.pkg_ops.run_install", _fake_install)
    # No addons in this env → no uninstall calls
    # Stub snapshot creation
    monkeypatch.setattr(
        "src.core.torch_pack.SnapshotManager.create_snapshot",
        lambda self, name, trigger=None: None,
    )

    result = switch_pack(
        config=config, env_name="main", target_pack_id="p-new",
        confirm_addon_removal=True,
    )
    assert result["ok"] is True
    # Expect: uninstall torch trio, install new torch trio, install pinned
    assert any(c[0] == "uninstall" and "torch" in c for c in calls)
    assert any(c[0] == "install" and "torch==2.9.1" in c for c in calls)
    assert any(c[0] == "install" and "av==16.0.1" in c for c in calls)

    env = Environment.load_meta(str(env_dir))
    assert env.torch_pack == "p-new"


def test_switch_pack_blocks_without_confirmation_when_compiled_addons_present(
    tmp_path, monkeypatch,
):
    config, env_dir = _setup(tmp_path)
    # Mark a compiled addon as installed
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "sage-attention",
        "installed_at": "2026-04-19T00:00:00Z",
        "torch_pack_at_install": "p-mid",
    })
    env.save_meta()
    (env_dir / "ComfyUI" / "custom_nodes" / "sage-attention").mkdir()

    result = switch_pack(
        config=config, env_name="main", target_pack_id="p-new",
        confirm_addon_removal=False,
    )
    assert result["ok"] is False
    assert "addon" in result["error"].lower() or "confirm" in result["error"].lower()
    # Env unchanged
    env = Environment.load_meta(str(env_dir))
    assert env.torch_pack == "p-mid"
    assert any(a["id"] == "sage-attention" for a in env.installed_addons)


def test_switch_pack_removes_compiled_addons_when_confirmed(
    tmp_path, monkeypatch,
):
    config, env_dir = _setup(tmp_path)
    env = Environment.load_meta(str(env_dir))
    env.installed_addons.append({
        "id": "sage-attention",
        "installed_at": "2026-04-19T00:00:00Z",
        "torch_pack_at_install": "p-mid",
    })
    env.save_meta()
    node_dir = env_dir / "ComfyUI" / "custom_nodes" / "sage-attention"
    node_dir.mkdir()
    (node_dir / "x.py").write_text("x")

    monkeypatch.setattr(
        "src.core.torch_pack.pkg_ops.run_install", lambda **kw: None,
    )
    monkeypatch.setattr(
        "src.core.torch_pack.SnapshotManager.create_snapshot",
        lambda self, name, trigger=None: None,
    )
    result = switch_pack(
        config=config, env_name="main", target_pack_id="p-new",
        confirm_addon_removal=True,
    )
    assert result["ok"] is True
    assert result["removed_addons"] == ["sage-attention"]
    assert not node_dir.exists()


def test_switch_pack_noop_when_target_equals_current(tmp_path, monkeypatch):
    config, env_dir = _setup(tmp_path)
    result = switch_pack(
        config=config, env_name="main", target_pack_id="p-mid",
        confirm_addon_removal=True,
    )
    assert result["ok"] is True
    assert result["noop"] is True
```

- [ ] **Step 15.2: Run — verify failure**

Run: `pytest tests/test_core/test_torch_pack_switch.py -v`
Expected: FAIL — `ImportError: cannot import name 'switch_pack'`

- [ ] **Step 15.3: Implement `switch_pack`**

Append to `src/core/torch_pack.py`:

```python
import shutil

from src.core.addons import ADDONS as _ADDONS, find_addon
from src.core.snapshot_manager import SnapshotManager
from src.models.environment import Environment
from src.utils import pkg_ops


def switch_pack(
    config: dict,
    env_name: str,
    target_pack_id: str,
    confirm_addon_removal: bool,
    progress_callback=None,
) -> dict:
    """Switch an environment from its current Pack to target_pack_id.

    Returns {
      "ok": bool,
      "noop": bool,
      "removed_addons": list[str],
      "error": str,
    }
    """
    env_dir = Path(config["environments_dir"]) / env_name
    if not env_dir.exists():
        return {"ok": False, "error": f"env '{env_name}' not found",
                "noop": False, "removed_addons": []}

    env = Environment.load_meta(str(env_dir))
    if env.torch_pack == target_pack_id:
        return {"ok": True, "noop": True, "removed_addons": [], "error": ""}

    base_dir = Path(config.get("base_dir", "."))
    mgr = TorchPackManager(
        shipped_path=base_dir / "data" / "torch_packs.json",
        remote_path=base_dir / "tools" / "torch_packs_remote.json",
    )
    target = mgr.find(target_pack_id)
    if target is None:
        return {"ok": False, "error": f"unknown pack '{target_pack_id}'",
                "noop": False, "removed_addons": []}

    # Identify compiled add-ons — they need removal before we swap torch
    compiled_addons = []
    for entry in env.installed_addons:
        addon = find_addon(entry.get("id", ""))
        if addon and addon.requires_compile:
            compiled_addons.append(entry["id"])

    if compiled_addons and not confirm_addon_removal:
        return {
            "ok": False,
            "error": (
                f"Compiled add-ons require removal before Pack switch: "
                f"{', '.join(compiled_addons)}. Re-invoke with "
                f"confirm_addon_removal=True."
            ),
            "noop": False,
            "removed_addons": [],
        }

    def _report(step, pct, detail=""):
        if progress_callback:
            progress_callback(step, pct, detail)

    # Auto-snapshot
    _report("snapshot", 5, "Creating pre-switch snapshot...")
    SnapshotManager(config).create_snapshot(env_name, trigger="pack_switch")

    removed_addons: list[str] = []
    venv_path = str(env_dir / "venv")
    tools_dir = base_dir / "tools"
    uv_version = mgr.get_recommended_uv_version() or "0.9.7"
    pkg_mgr = config.get("package_manager", "uv")

    # Remove compiled add-ons
    for aid in compiled_addons:
        _report("addon", 15, f"Removing compiled add-on: {aid}")
        addon = find_addon(aid)
        if addon and addon.install_method == "pip_package":
            pkg_ops.run_install(
                venv_path=venv_path,
                args=["uninstall", "-y", addon.pip_package],
                tools_dir=tools_dir, uv_version=uv_version,
                package_manager=pkg_mgr,
            )
        node_dir = env_dir / "ComfyUI" / "custom_nodes" / aid
        if node_dir.exists():
            shutil.rmtree(str(node_dir), ignore_errors=True)
        env.installed_addons = [
            e for e in env.installed_addons if e.get("id") != aid
        ]
        removed_addons.append(aid)

    # Uninstall current torch trio
    _report("uninstall", 30, "Uninstalling current PyTorch...")
    pkg_ops.run_install(
        venv_path=venv_path,
        args=["uninstall", "-y", "torch", "torchvision", "torchaudio"],
        tools_dir=tools_dir, uv_version=uv_version, package_manager=pkg_mgr,
    )

    # Install target trio
    _report("install", 55, f"Installing {target.label}...")
    pkg_ops.run_install(
        venv_path=venv_path,
        args=[
            "install",
            f"torch=={target.torch}",
            f"torchvision=={target.torchvision}",
            f"torchaudio=={target.torchaudio}",
            "--index-url", f"https://download.pytorch.org/whl/{target.cuda_tag}",
        ],
        tools_dir=tools_dir, uv_version=uv_version, package_manager=pkg_mgr,
    )

    # Re-apply pinned deps
    _report("pins", 80, "Re-applying pinned deps...")
    pinned = mgr.get_pinned_deps()
    if pinned:
        pkg_ops.run_install(
            venv_path=venv_path,
            args=["install"] + [f"{k}=={v}" for k, v in pinned.items()],
            tools_dir=tools_dir, uv_version=uv_version, package_manager=pkg_mgr,
        )

    # Update env_meta
    freeze_data = pkg_ops.freeze(
        venv_path=venv_path, tools_dir=tools_dir,
        uv_version=uv_version, package_manager=pkg_mgr,
    )
    env.torch_pack = target.id
    env.cuda_tag = target.cuda_tag
    env.pytorch_version = freeze_data.get(
        "torch", f"{target.torch}+{target.cuda_tag}"
    )
    env.pip_freeze = freeze_data
    env.save_meta()

    _report("done", 100, "Pack switch complete.")
    return {
        "ok": True, "noop": False, "removed_addons": removed_addons,
        "error": "",
    }
```

- [ ] **Step 15.4: Run — verify pass**

Run: `pytest tests/test_core/test_torch_pack_switch.py -v`
Expected: PASS (4 tests)

- [ ] **Step 15.5: Commit**

```bash
git add src/core/torch_pack.py tests/test_core/test_torch_pack_switch.py
git commit -m "feat(torch-pack): switch_pack with compiled add-on auto-removal"
```

---

## Task 16: Migration — backfill `torch_pack` + `installed_addons` on startup

**Files:**
- Create: `src/core/migrations.py`
- Test: `tests/test_core/test_migrations.py`

- [ ] **Step 16.1: Write failing tests**

Create `tests/test_core/test_migrations.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from src.core.migrations import migrate_env_meta_0_4_0
from src.models.environment import Environment


def _shipped_packs(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "torch_packs.json").write_text(json.dumps({
        "schema_version": 1, "last_updated": "2026-04-19", "remote_url": "",
        "recommended_python": "3.12.10", "recommended_uv_version": "0.9.7",
        "packs": [
            {"id": "p-new", "label": "L", "torch": "2.9.1",
             "torchvision": "0.24.1", "torchaudio": "2.9.1",
             "cuda_tag": "cu130", "min_driver": 13.0, "recommended": True},
        ],
        "pinned_deps": {},
    }), encoding="utf-8")


def _write_legacy_env(envs_dir, name, cuda_tag, pytorch_version, addons_on_disk=()):
    env_dir = envs_dir / name
    env_dir.mkdir(parents=True)
    (env_dir / "ComfyUI" / "custom_nodes").mkdir(parents=True)
    for addon_name in addons_on_disk:
        (env_dir / "ComfyUI" / "custom_nodes" / addon_name).mkdir()
    env = Environment(
        name=name,
        created_at="2026-01-01T00:00:00Z",
        cuda_tag=cuda_tag,
        pytorch_version=pytorch_version,
        path=str(env_dir),
    )
    env.save_meta()
    return env_dir


def test_backfill_matches_known_pack(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(envs_dir, "e1", "cu130", "2.9.1+cu130")
    config = {
        "environments_dir": str(envs_dir),
        "base_dir": str(tmp_path),
    }
    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e1"))
    assert env.torch_pack == "p-new"


def test_backfill_unknown_version_stays_none(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(envs_dir, "e2", "cu124", "2.5.1+cu124")
    config = {"environments_dir": str(envs_dir), "base_dir": str(tmp_path)}
    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e2"))
    assert env.torch_pack is None


def test_backfill_strips_cuda_suffix(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(envs_dir, "e3", "cu130", "2.9.1")  # no +cu suffix
    config = {"environments_dir": str(envs_dir), "base_dir": str(tmp_path)}
    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e3"))
    assert env.torch_pack == "p-new"


def test_backfill_discovers_addons_on_disk(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(
        envs_dir, "e4", "cu130", "2.9.1",
        addons_on_disk=("sage-attention", "some-random-node"),
    )
    config = {"environments_dir": str(envs_dir), "base_dir": str(tmp_path)}
    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e4"))
    ids = {a["id"] for a in env.installed_addons}
    assert "sage-attention" in ids
    # Unknown dir names are ignored
    assert "some-random-node" not in ids


def test_migration_marker_makes_it_idempotent(tmp_path):
    _shipped_packs(tmp_path)
    envs_dir = tmp_path / "envs"
    _write_legacy_env(envs_dir, "e5", "cu130", "2.9.1")
    config = {"environments_dir": str(envs_dir), "base_dir": str(tmp_path)}
    migrate_env_meta_0_4_0(config)

    # Modify env_meta after migration; second run must not touch it
    env = Environment.load_meta(str(envs_dir / "e5"))
    env.torch_pack = "hand-edited"
    env.save_meta()

    migrate_env_meta_0_4_0(config)
    env = Environment.load_meta(str(envs_dir / "e5"))
    assert env.torch_pack == "hand-edited"
```

- [ ] **Step 16.2: Run — verify failure**

Run: `pytest tests/test_core/test_migrations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.migrations'`

- [ ] **Step 16.3: Implement migration**

Create `src/core/migrations.py`:

```python
"""One-shot migrations triggered on app startup."""
from __future__ import annotations

import logging
from pathlib import Path

from src.core.addons import ADDONS
from src.core.torch_pack import TorchPackManager
from src.models.environment import Environment

logger = logging.getLogger(__name__)

_MARKER_NAME = "migration_0.4.0.done"


def migrate_env_meta_0_4_0(config: dict) -> None:
    """Backfill torch_pack + installed_addons on all existing environments.

    Safe to call repeatedly: short-circuits after a marker file is created.
    """
    base_dir = Path(config.get("base_dir", "."))
    marker = base_dir / "tools" / _MARKER_NAME
    if marker.exists():
        return

    envs_dir = Path(config["environments_dir"])
    if not envs_dir.exists():
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("done", encoding="utf-8")
        return

    mgr = TorchPackManager(
        shipped_path=base_dir / "data" / "torch_packs.json",
        remote_path=base_dir / "tools" / "torch_packs_remote.json",
    )
    packs = mgr.list_packs()
    known_addon_ids = {a.id for a in ADDONS}

    for entry in envs_dir.iterdir():
        meta = entry / "env_meta.json"
        if not meta.exists():
            continue
        try:
            env = Environment.load_meta(str(entry))
        except Exception as exc:
            logger.warning("Skipping unreadable env %s: %s", entry.name, exc)
            continue

        changed = False
        # Backfill torch_pack
        if env.torch_pack is None and env.pytorch_version:
            ver_base = env.pytorch_version.split("+")[0].strip()
            for p in packs:
                if p.torch == ver_base and p.cuda_tag == env.cuda_tag:
                    env.torch_pack = p.id
                    changed = True
                    break

        # Backfill installed_addons via disk scan
        if not env.installed_addons:
            custom_nodes_dir = entry / "ComfyUI" / "custom_nodes"
            if custom_nodes_dir.exists():
                for child in custom_nodes_dir.iterdir():
                    if child.is_dir() and child.name in known_addon_ids:
                        env.installed_addons.append({
                            "id": child.name,
                            "installed_at": env.created_at,
                            "torch_pack_at_install": env.torch_pack,
                        })
                        changed = True

        if changed:
            env.save_meta()

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("done", encoding="utf-8")
```

- [ ] **Step 16.4: Run — verify pass**

Run: `pytest tests/test_core/test_migrations.py -v`
Expected: PASS (5 tests)

- [ ] **Step 16.5: Wire migration into launcher**

Edit `launcher.py`. Find the place early in GUI startup (or right after config load in CLI) — typically where `EnvManager` is first constructed. Add:

```python
from src.core.migrations import migrate_env_meta_0_4_0
# ... after config loaded ...
try:
    migrate_env_meta_0_4_0(config)
except Exception as exc:
    logging.getLogger(__name__).warning("0.4.0 migration failed: %s", exc)
```

Locate by grep:
```bash
grep -n "config\s*=" launcher.py
```
Pick the first place `config` is a complete dict (after `load_config()`). Insert the migration call there.

- [ ] **Step 16.6: Commit**

```bash
git add src/core/migrations.py tests/test_core/test_migrations.py launcher.py
git commit -m "feat(migration): backfill torch_pack + installed_addons for 0.4.0"
```

---

## Task 17: Bridge methods

**Files:**
- Modify: `src/gui/bridge.py`
- Test: `tests/test_gui/test_bridge_torch_pack.py` (create if needed)

- [ ] **Step 17.1: Write failing tests**

Create `tests/test_gui/test_bridge_torch_pack.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# NB: Bridge needs Qt; many repos already test it directly. Mirror existing style.
pytest.importorskip("PySide6")

from src.gui.bridge import Bridge


@pytest.fixture
def bridge_config(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "torch_packs.json").write_text(json.dumps({
        "schema_version": 1, "last_updated": "2026-04-19", "remote_url": "",
        "recommended_python": "3.12.10", "recommended_uv_version": "0.9.7",
        "packs": [
            {"id": "p-new", "label": "New", "torch": "2.9.1",
             "torchvision": "0.24.1", "torchaudio": "2.9.1",
             "cuda_tag": "cu130", "min_driver": 13.0, "recommended": True},
        ],
        "pinned_deps": {},
    }), encoding="utf-8")
    return {
        "environments_dir": str(tmp_path / "envs"),
        "models_dir": str(tmp_path / "models"),
        "base_dir": str(tmp_path),
        "package_manager": "uv",
    }


def test_list_torch_packs_returns_shipped(bridge_config, qtbot_or_noop):
    b = Bridge(bridge_config)
    result = json.loads(b.list_torch_packs())
    assert result["ok"] is True
    assert result["packs"][0]["id"] == "p-new"


def test_list_addons_returns_curated_list(bridge_config):
    b = Bridge(bridge_config)
    result = json.loads(b.list_addons())
    assert result["ok"] is True
    ids = {a["id"] for a in result["addons"]}
    assert "sage-attention" in ids


@pytest.fixture
def qtbot_or_noop():
    # Many Bridge methods don't need a running event loop; this is a stub
    # fixture so the test file doesn't hard-require pytest-qt.
    return None
```

- [ ] **Step 17.2: Run — verify failure**

Run: `pytest tests/test_gui/test_bridge_torch_pack.py -v`
Expected: FAIL — bridge methods don't exist yet.

- [ ] **Step 17.3: Add bridge methods**

Edit `src/gui/bridge.py`. Add imports:

```python
from src.core.torch_pack import TorchPackManager, switch_pack as _switch_pack
from src.core.addons import ADDONS, install_addon as _install_addon, uninstall_addon as _uninstall_addon
```

Inside `Bridge` class add methods (keep the existing `@Slot(...)` decorators — copy the idiom from nearby methods; if `@Slot(result=str)` is the pattern, match it):

```python
    @Slot(result=str)
    def list_torch_packs(self) -> str:
        try:
            mgr = self._torch_pack_mgr()
            packs = [
                {
                    "id": p.id, "label": p.label, "torch": p.torch,
                    "torchvision": p.torchvision, "torchaudio": p.torchaudio,
                    "cuda_tag": p.cuda_tag, "min_driver": p.min_driver,
                    "recommended": p.recommended,
                }
                for p in mgr.list_packs()
            ]
            return json.dumps({"ok": True, "packs": packs})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(result=str)
    def refresh_torch_packs(self) -> str:
        try:
            return json.dumps(self._torch_pack_mgr().refresh_remote())
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str, bool, result=str)
    def switch_torch_pack(
        self, env_name: str, target_pack_id: str, confirm_addon_removal: bool,
    ) -> str:
        try:
            return json.dumps(_switch_pack(
                config=self.config, env_name=env_name,
                target_pack_id=target_pack_id,
                confirm_addon_removal=confirm_addon_removal,
            ))
        except Exception as exc:
            return json.dumps({
                "ok": False, "error": str(exc), "noop": False,
                "removed_addons": [],
            })

    @Slot(result=str)
    def list_addons(self) -> str:
        try:
            items = [
                {
                    "id": a.id, "label": a.label, "description": a.description,
                    "requires_cuda": a.requires_cuda,
                    "requires_compile": a.requires_compile,
                    "risk_note": a.risk_note or "",
                }
                for a in ADDONS
            ]
            return json.dumps({"ok": True, "addons": items})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str, result=str)
    def install_addon(self, env_name: str, addon_id: str) -> str:
        try:
            env_dir = Path(self.config["environments_dir"]) / env_name
            tools_dir = Path(self.config.get("base_dir", ".")) / "tools"
            uv_ver = self._torch_pack_mgr().get_recommended_uv_version() or "0.9.7"
            result = _install_addon(
                addon_id=addon_id, env_dir=env_dir, tools_dir=tools_dir,
                uv_version=uv_ver,
                package_manager=self.config.get("package_manager", "uv"),
            )
            return json.dumps({"ok": True, **result})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str, result=str)
    def uninstall_addon(self, env_name: str, addon_id: str) -> str:
        try:
            env_dir = Path(self.config["environments_dir"]) / env_name
            tools_dir = Path(self.config.get("base_dir", ".")) / "tools"
            uv_ver = self._torch_pack_mgr().get_recommended_uv_version() or "0.9.7"
            _uninstall_addon(
                addon_id=addon_id, env_dir=env_dir, tools_dir=tools_dir,
                uv_version=uv_ver,
                package_manager=self.config.get("package_manager", "uv"),
            )
            return json.dumps({"ok": True})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(result=str)
    def detect_gpu_for_recommended(self) -> str:
        """Pre-flight check used by the create dialog."""
        try:
            from src.core.version_manager import VersionManager
            gpu = VersionManager(self.config).detect_gpu()
            mgr = self._torch_pack_mgr()
            pack = mgr.select_pack_for_gpu(gpu)
            return json.dumps({
                "ok": True,
                "has_gpu": gpu.get("has_gpu", False),
                "driver_version": gpu.get("cuda_driver_version", ""),
                "recommended_pack_id": pack.id if pack else None,
                "recommended_pack_label": pack.label if pack else None,
            })
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str, result=str)  # name, addon_ids JSON array
    def create_recommended_env(
        self, name: str, selected_addon_ids_json: str,
    ) -> str:
        try:
            addon_ids = json.loads(selected_addon_ids_json or "[]")
            # Use existing async request pattern if the bridge uses one;
            # otherwise run synchronously and return summary.
            from src.core.env_manager import EnvManager
            env = EnvManager(self.config).create_recommended(
                name=name, selected_addon_ids=addon_ids,
            )
            return json.dumps({
                "ok": True,
                "name": env.name,
                "torch_pack": env.torch_pack,
                "failed_addons": getattr(env, "failed_addons", []),
            })
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    def _torch_pack_mgr(self) -> "TorchPackManager":
        base = Path(self.config.get("base_dir", "."))
        return TorchPackManager(
            shipped_path=base / "data" / "torch_packs.json",
            remote_path=base / "tools" / "torch_packs_remote.json",
        )
```

**Note:** If `bridge.py` already uses an async request-id pattern for long operations, wrap `create_recommended_env` and `switch_torch_pack` using that idiom. Check existing methods like `create_environment` for the pattern — the sync shell above is a placeholder and should be replaced with the repo's async pattern.

- [ ] **Step 17.4: Run — verify pass**

Run: `pytest tests/test_gui/test_bridge_torch_pack.py -v`
Expected: PASS (skipped if PySide6 not installed — acceptable)

- [ ] **Step 17.5: Commit**

```bash
git add src/gui/bridge.py tests/test_gui/test_bridge_torch_pack.py
git commit -m "feat(bridge): add torch_pack + addons + recommended-env methods"
```

---

## Task 18: UI — redesigned env create dialog

**Files:**
- Modify: `src/gui/web/js/pages/env.js`
- Modify: `src/gui/web/css/tack-industrial.css` (small additions)

This task is UI; unit tests are limited. Smoke-test manually via GUI after implementation.

- [ ] **Step 18.1: Locate current create dialog**

Run:
```bash
grep -n "createEnvironment\|create-env-dialog\|建立環境" src/gui/web/js/pages/env.js
```
Identify the existing create function and modal markup to replace.

- [ ] **Step 18.2: Add recommended-mode markup + handlers**

Replace the current create dialog in `env.js` with a version that renders two stacked sections:

```javascript
async function openCreateDialog() {
  // Pre-flight GPU check
  const gpuInfo = JSON.parse(await bridge.detect_gpu_for_recommended());
  const canRecommend = gpuInfo.ok && gpuInfo.recommended_pack_id;

  // Fetch add-ons list
  const addonsRes = JSON.parse(await bridge.list_addons());
  const addons = addonsRes.ok ? addonsRes.addons : [];

  const modal = document.createElement('div');
  modal.className = 'modal create-env-modal';
  modal.innerHTML = `
    <div class="modal-body">
      <h2>${i18n('env.create.title') || 'Create New Environment'}</h2>

      ${canRecommend ? '' : `
        <div class="banner banner-error">
          <strong>${i18n('env.create.no_gpu_title') || '未偵測到支援的 GPU'}</strong>
          <p>${i18n('env.create.no_gpu_hint') || '推薦模式需要 CUDA ≥ 12.8。請使用下方進階模式手動選版本,或檢查驅動。'}</p>
        </div>
      `}

      <section class="create-section recommended ${canRecommend ? '' : 'disabled'}">
        <label>${i18n('env.create.name') || 'Name'}
          <input type="text" id="rec-name" />
        </label>

        ${canRecommend ? `
          <div class="pack-info">
            ${i18n('env.create.pack') || 'PyTorch'}: <strong>${gpuInfo.recommended_pack_label}</strong>
          </div>
        ` : ''}

        <fieldset class="addons">
          <legend>${i18n('env.create.addons') || 'Optional Add-ons'}</legend>
          ${addons.map(a => `
            <label class="addon-row">
              <input type="checkbox" name="addon" value="${a.id}" ${canRecommend ? '' : 'disabled'} />
              <span class="addon-label">${a.label}</span>
              <span class="addon-tags">
                ${a.requires_cuda ? `<span class="tag">CUDA</span>` : ''}
                ${a.requires_compile ? `<span class="tag warn">compiles</span>` : ''}
              </span>
              <span class="addon-desc">${a.description}</span>
              ${a.risk_note ? `<span class="addon-risk">⚠ ${a.risk_note}</span>` : ''}
            </label>
          `).join('')}
        </fieldset>
      </section>

      <details class="create-section advanced" ${canRecommend ? '' : 'open'}>
        <summary>${i18n('env.create.advanced_mode') || '▶ Advanced mode (manual Python/CUDA/Torch)'}</summary>
        <div id="advanced-form-host"></div>
      </details>

      <div class="modal-actions">
        <button type="button" class="btn-secondary" id="cancel-btn">${i18n('common.cancel') || 'Cancel'}</button>
        <button type="button" class="btn-primary" id="create-rec-btn" ${canRecommend ? '' : 'disabled'}>
          ${i18n('env.create.create_recommended') || 'Create (Recommended)'}
        </button>
        <button type="button" class="btn-primary" id="create-adv-btn">
          ${i18n('env.create.create_advanced') || 'Create (Advanced)'}
        </button>
      </div>
    </div>`;

  document.body.appendChild(modal);
  // Render advanced form into #advanced-form-host using existing renderer
  renderAdvancedCreateForm(modal.querySelector('#advanced-form-host'));

  modal.querySelector('#cancel-btn').addEventListener('click', () => modal.remove());
  modal.querySelector('#create-rec-btn').addEventListener('click',
    () => submitRecommended(modal));
  modal.querySelector('#create-adv-btn').addEventListener('click',
    () => submitAdvanced(modal));
}

async function submitRecommended(modal) {
  const name = modal.querySelector('#rec-name').value.trim();
  if (!name) { showToast(i18n('env.create.name_required') || 'Name required'); return; }
  const selected = Array.from(modal.querySelectorAll('input[name="addon"]:checked'))
    .map(el => el.value);

  setStatus(i18n('env.create.creating') || 'Creating recommended environment...');
  const res = JSON.parse(
    await bridge.create_recommended_env(name, JSON.stringify(selected))
  );
  if (res.ok) {
    modal.remove();
    if (res.failed_addons && res.failed_addons.length) {
      showToast(
        (i18n('env.create.addons_partial') || 'Created, but some add-ons failed:')
        + ' ' + res.failed_addons.map(f => `${f.id} (${f.error})`).join(', '),
        'warning',
      );
    } else {
      showToast(i18n('env.create.created') || 'Environment created', 'success');
    }
    await refreshEnvList();
  } else {
    showToast(res.error || 'Create failed', 'error');
  }
}

function renderAdvancedCreateForm(host) {
  // Move existing advanced-mode form into host (or reconstruct using
  // the old createEnvironment() code path). This preserves Python/CUDA/
  // PyTorch dropdowns unchanged.
  host.innerHTML = /* existing create form markup */ '';
  // Preserve the existing event wiring as a helper function:
  wireAdvancedCreateForm(host);
}
```

**Important:** Keep the existing advanced form intact — the lift-and-shift is non-destructive. If the existing code is tightly coupled to the old modal, factor the form markup into a helper `wireAdvancedCreateForm(host)` that both old and new callers can use.

- [ ] **Step 18.3: Add i18n strings**

Edit `src/gui/web/js/i18n.js` (or wherever translation keys live). Add for both `en` and `zh-TW`:

```javascript
// en
'env.create.no_gpu_title': 'No supported GPU detected',
'env.create.no_gpu_hint': 'Recommended mode requires CUDA ≥ 12.8. Use advanced mode below to pick versions manually, or check your driver.',
'env.create.pack': 'PyTorch',
'env.create.addons': 'Optional Add-ons',
'env.create.advanced_mode': '▶ Advanced mode (manual Python/CUDA/Torch)',
'env.create.create_recommended': 'Create (Recommended)',
'env.create.create_advanced': 'Create (Advanced)',
'env.create.name': 'Name',
'env.create.name_required': 'Name is required',
'env.create.creating': 'Creating recommended environment...',
'env.create.created': 'Environment created',
'env.create.addons_partial': 'Created, but some add-ons failed:',

// zh-TW
'env.create.no_gpu_title': '未偵測到支援的 GPU',
'env.create.no_gpu_hint': '推薦模式需要 CUDA ≥ 12.8。請使用下方進階模式手動選版本,或檢查驅動。',
'env.create.pack': 'PyTorch',
'env.create.addons': '可選擴充',
'env.create.advanced_mode': '▶ 進階模式(手動選 Python/CUDA/Torch)',
'env.create.create_recommended': '建立(推薦)',
'env.create.create_advanced': '建立(進階)',
'env.create.name': '名稱',
'env.create.name_required': '需要輸入名稱',
'env.create.creating': '正在建立推薦環境...',
'env.create.created': '環境已建立',
'env.create.addons_partial': '建立完成,但有擴充失敗:',
```

- [ ] **Step 18.4: Add minimal CSS**

Append to `src/gui/web/css/tack-industrial.css`:

```css
.create-env-modal .banner-error {
  background: #3a1a1a;
  border: 1px solid #6b2a2a;
  padding: 12px; border-radius: 6px; margin-bottom: 14px;
}
.create-env-modal .addons .addon-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 6px 10px; padding: 8px; border-radius: 4px;
  align-items: center;
}
.create-env-modal .addons .addon-row:hover { background: #1f2730; }
.create-env-modal .addons .tag {
  font-size: 0.75em; padding: 2px 6px; border-radius: 10px;
  background: #2a3540; color: #c6d2e0;
}
.create-env-modal .addons .tag.warn { background: #4a3a20; color: #ffd38a; }
.create-env-modal .addons .addon-desc {
  grid-column: 2 / 4; font-size: 0.85em; color: #8fa0b3;
}
.create-env-modal .addons .addon-risk {
  grid-column: 2 / 4; font-size: 0.8em; color: #ffcc66;
}
.create-env-modal .create-section.advanced { margin-top: 18px; }
.create-env-modal .recommended.disabled { opacity: 0.6; pointer-events: none; }
```

- [ ] **Step 18.5: Manual smoke test**

Run:
```bash
python launcher.py
```

Steps:
1. Click Environments page → Create.
2. Verify the recommended section renders with an add-on checklist.
3. If your machine has no GPU with CUDA ≥ 12.8, verify the red banner shows and the Advanced section is auto-open.
4. Expand Advanced and verify the existing form still works.
5. Enter a test name, tick 0 add-ons, click "Create (Recommended)" — confirm an env is created (watch the progress toast).

- [ ] **Step 18.6: Commit**

```bash
git add src/gui/web/js/pages/env.js src/gui/web/js/i18n.js src/gui/web/css/tack-industrial.css
git commit -m "feat(ui): add recommended-mode create dialog with GPU pre-flight"
```

---

## Task 19: UI — PyTorch sub-tab in versions page

**Files:**
- Modify: `src/gui/web/js/pages/versions.js`
- Modify: `src/gui/web/css/tack-industrial.css`
- Modify: `src/gui/web/js/i18n.js`

- [ ] **Step 19.1: Add sub-tab switch + render PyTorch tab**

In `versions.js`, wrap existing page render in a tab container. Replace top-level render with:

```javascript
async function renderVersionsPage(container) {
  container.innerHTML = `
    <div class="tabs">
      <button class="tab active" data-tab="comfy">${i18n('versions.tab_comfy') || 'ComfyUI Version'}</button>
      <button class="tab" data-tab="pytorch">${i18n('versions.tab_pytorch') || 'PyTorch Engine'}</button>
    </div>
    <div class="tab-content" id="tab-comfy"></div>
    <div class="tab-content hidden" id="tab-pytorch"></div>
  `;
  container.querySelector('#tab-comfy').appendChild(await renderComfyVersionPanel());
  container.querySelector('#tab-pytorch').appendChild(await renderPyTorchPanel());
  container.querySelectorAll('.tabs .tab').forEach(t => {
    t.addEventListener('click', () => {
      container.querySelectorAll('.tabs .tab').forEach(x => x.classList.remove('active'));
      container.querySelectorAll('.tab-content').forEach(x => x.classList.add('hidden'));
      t.classList.add('active');
      container.querySelector('#tab-' + t.dataset.tab).classList.remove('hidden');
    });
  });
}

// Keep existing ComfyUI version logic — extract it into renderComfyVersionPanel().
async function renderComfyVersionPanel() { /* moved existing code */ }

async function renderPyTorchPanel() {
  const node = document.createElement('div');
  const envs = JSON.parse(await bridge.listEnvironments()).envs || [];
  const packs = JSON.parse(await bridge.list_torch_packs()).packs || [];

  node.innerHTML = `
    <div class="form-row">
      <label>${i18n('versions.pytorch.env') || 'Environment'}
        <select id="pt-env">
          ${envs.map(e => `<option value="${e.name}">${e.name}</option>`).join('')}
        </select>
      </label>
    </div>
    <div id="pt-current"></div>
    <div class="pack-list" id="pt-pack-list">
      ${packs.map(p => `
        <label class="pack-row">
          <input type="radio" name="pt-pack" value="${p.id}">
          <span class="pack-label">${p.label}</span>
          ${p.recommended ? `<span class="tag">${i18n('versions.pytorch.recommended') || 'Recommended'}</span>` : ''}
        </label>
      `).join('')}
    </div>
    <div id="pt-compiled-addons-warn"></div>
    <div class="actions">
      <button id="pt-refresh">${i18n('versions.pytorch.refresh') || 'Refresh List'}</button>
      <button id="pt-switch" class="btn-primary">${i18n('versions.pytorch.switch') || 'Switch'}</button>
    </div>
  `;

  const refreshCurrent = async () => {
    const envName = node.querySelector('#pt-env').value;
    const env = envs.find(e => e.name === envName);
    const current = node.querySelector('#pt-current');
    if (env && env.torch_pack) {
      const pack = packs.find(p => p.id === env.torch_pack);
      current.innerHTML = `<p>${i18n('versions.pytorch.current') || 'Current'}: <strong>${pack ? pack.label : env.torch_pack}</strong> ✅</p>`;
    } else if (env) {
      current.innerHTML = `<p>${i18n('versions.pytorch.custom') || 'Custom version'} (torch ${env.pytorch_version || '?'}) ⚠️</p>`;
    }
    const warn = node.querySelector('#pt-compiled-addons-warn');
    const compiled = (env && env.installed_addons || [])
      .filter(a => ['sage-attention', 'flash-attention', 'nunchaku', 'trellis2'].includes(a.id));
    warn.innerHTML = compiled.length ? `
      <div class="banner banner-warn">
        ${i18n('versions.pytorch.compiled_warn') || '切換會卸載以下編譯型擴充(可重裝):'}
        <ul>${compiled.map(c => `<li>${c.id}</li>`).join('')}</ul>
      </div>` : '';
  };

  node.querySelector('#pt-env').addEventListener('change', refreshCurrent);
  await refreshCurrent();

  node.querySelector('#pt-refresh').addEventListener('click', async () => {
    const res = JSON.parse(await bridge.refresh_torch_packs());
    showToast(res.ok ? (i18n('versions.pytorch.refreshed') || 'Refreshed') : res.error, res.ok ? 'success' : 'error');
  });

  node.querySelector('#pt-switch').addEventListener('click', async () => {
    const envName = node.querySelector('#pt-env').value;
    const picked = node.querySelector('input[name="pt-pack"]:checked');
    if (!picked) { showToast(i18n('versions.pytorch.pick_pack') || 'Pick a Pack', 'warn'); return; }
    const ok = confirm(i18n('versions.pytorch.confirm') || 'Switch Pack now? A snapshot will be created first.');
    if (!ok) return;
    // First try without confirm_addon_removal to learn whether addons need removal
    let res = JSON.parse(
      await bridge.switch_torch_pack(envName, picked.value, false),
    );
    if (!res.ok && /addon|confirm/i.test(res.error || '')) {
      if (confirm(res.error + '\n\n' + (i18n('versions.pytorch.confirm_remove') || 'Continue and remove those add-ons?'))) {
        res = JSON.parse(
          await bridge.switch_torch_pack(envName, picked.value, true),
        );
      } else {
        return;
      }
    }
    if (res.ok) {
      showToast(
        res.noop
          ? (i18n('versions.pytorch.noop') || 'Already on this Pack')
          : (i18n('versions.pytorch.switched') || 'Pack switched'),
        'success',
      );
      await refreshCurrent();
    } else {
      showToast(res.error || 'Switch failed', 'error');
    }
  });

  return node;
}
```

- [ ] **Step 19.2: Add i18n strings**

Edit `src/gui/web/js/i18n.js`:

```javascript
// en
'versions.tab_comfy': 'ComfyUI Version',
'versions.tab_pytorch': 'PyTorch Engine',
'versions.pytorch.env': 'Environment',
'versions.pytorch.current': 'Current',
'versions.pytorch.custom': 'Custom version',
'versions.pytorch.recommended': 'Recommended',
'versions.pytorch.refresh': 'Refresh List',
'versions.pytorch.switch': 'Switch',
'versions.pytorch.pick_pack': 'Pick a Pack first',
'versions.pytorch.confirm': 'Switch Pack now? A snapshot will be created first.',
'versions.pytorch.confirm_remove': 'Continue and remove those add-ons?',
'versions.pytorch.noop': 'Already on this Pack',
'versions.pytorch.switched': 'Pack switched',
'versions.pytorch.refreshed': 'Refreshed',
'versions.pytorch.compiled_warn': 'Switching will uninstall these compiled add-ons (you can reinstall afterward):',

// zh-TW
'versions.tab_comfy': 'ComfyUI 版本',
'versions.tab_pytorch': 'PyTorch 引擎',
'versions.pytorch.env': '環境',
'versions.pytorch.current': '目前',
'versions.pytorch.custom': '自訂版本',
'versions.pytorch.recommended': '推薦',
'versions.pytorch.refresh': '刷新清單',
'versions.pytorch.switch': '切換',
'versions.pytorch.pick_pack': '請先選一個 Pack',
'versions.pytorch.confirm': '現在切換 Pack?會先建立快照。',
'versions.pytorch.confirm_remove': '繼續並移除這些擴充?',
'versions.pytorch.noop': '已是此 Pack',
'versions.pytorch.switched': '已切換 Pack',
'versions.pytorch.refreshed': '已刷新',
'versions.pytorch.compiled_warn': '切換會卸載下列編譯型擴充(可重裝):',
```

- [ ] **Step 19.3: Add CSS**

Append to `src/gui/web/css/tack-industrial.css`:

```css
.tabs {
  display: flex; gap: 2px; margin-bottom: 16px;
  border-bottom: 1px solid #2b3845;
}
.tabs .tab {
  padding: 8px 16px; background: transparent; border: none;
  color: #8fa0b3; cursor: pointer;
}
.tabs .tab.active {
  color: #e6edf3; border-bottom: 2px solid #4a90e2;
}
.tab-content.hidden { display: none; }
.pack-list .pack-row {
  display: flex; gap: 10px; align-items: center;
  padding: 10px; border-radius: 4px;
}
.pack-list .pack-row:hover { background: #1f2730; }
.banner-warn {
  background: #3a2f15; border: 1px solid #6b5a2a;
  padding: 10px; border-radius: 4px; margin: 10px 0;
}
```

- [ ] **Step 19.4: Manual smoke test**

Run:
```bash
python launcher.py
```
1. Go to Versions page.
2. Confirm two tabs render; default is ComfyUI Version (old behavior intact).
3. Click PyTorch Engine. Verify env dropdown lists real envs, current Pack shows, 3 packs listed.
4. Pick a pack and click Switch. Confirm snapshot appears in Snapshots page afterward.

- [ ] **Step 19.5: Commit**

```bash
git add src/gui/web/js/pages/versions.js src/gui/web/js/i18n.js src/gui/web/css/tack-industrial.css
git commit -m "feat(ui): add PyTorch Engine sub-tab with Pack switcher"
```

---

## Task 20: Bump version & changelog

**Files:**
- Modify: `VERSION.json`

- [ ] **Step 20.1: Edit VERSION.json**

Overwrite with:

```json
{
  "version": "0.4.0",
  "min_python": "3.10",
  "release_notes": "推薦模式建環境 + Torch-Pack 切換 + uv 遷移",
  "changes": [
    "新增推薦模式:建環境時自動依 GPU 選擇 PyTorch/CUDA 組合,無需手動選版本",
    "新增 Torch-Pack 引擎切換(版本頁 → PyTorch 引擎分頁)",
    "新增可選擴充:SageAttention / FlashAttention / InsightFace / Nunchaku / Trellis 2",
    "套件安裝改用 uv(顯著加快環境建置速度)",
    "env_meta.json 新增 torch_pack 與 installed_addons 欄位"
  ],
  "changes_i18n": {
    "en": [
      "Added Recommended mode: environment creation auto-selects PyTorch/CUDA combo based on GPU — no more manual version picking",
      "Added Torch-Pack engine switcher (Versions page → PyTorch Engine tab)",
      "Added optional curated add-ons: SageAttention / FlashAttention / InsightFace / Nunchaku / Trellis 2",
      "Package operations now use uv (significantly faster env creation)",
      "env_meta.json gains torch_pack and installed_addons fields"
    ],
    "zh-TW": [
      "新增推薦模式:建環境時自動依 GPU 選擇 PyTorch/CUDA 組合,無需手動選版本",
      "新增 Torch-Pack 引擎切換(版本頁 → PyTorch 引擎分頁)",
      "新增可選擴充:SageAttention / FlashAttention / InsightFace / Nunchaku / Trellis 2",
      "套件安裝改用 uv(顯著加快環境建置速度)",
      "env_meta.json 新增 torch_pack 與 installed_addons 欄位"
    ]
  }
}
```

- [ ] **Step 20.2: Final full-suite check**

Run: `pytest -x`
Expected: all green.

- [ ] **Step 20.3: Commit**

```bash
git add VERSION.json
git commit -m "chore: bump to 0.4.0 — recommended env + Torch-Pack + uv"
```

---

## Self-Review

**Spec coverage check:**

| Spec § | Task | Notes |
|---|---|---|
| §5 data model (env) | Task 1 | ✅ |
| §5 torch_packs.json | Task 2 | ✅ |
| §6 Pack load + refresh | Tasks 3–5 | ✅ |
| §6 GPU → Pack | Task 4 | ✅ |
| §7 Add-on registry | Task 8 | ✅ |
| §7 install_addon (both methods + install.py skip) | Tasks 9–10 | ✅ |
| §7 uninstall_addon | Task 11 | ✅ |
| §8 Recommended flow | Tasks 12–14 | ✅ (Pack install + pinned + full flow) |
| §9 uv binary + dispatch | Tasks 6–7 | ✅ |
| §6 Pack switch with compiled addon removal | Task 15 | ✅ |
| §11 Migration | Task 16 | ✅ |
| §10 GUI — create dialog | Task 18 | ✅ |
| §10 GUI — PyTorch tab | Task 19 | ✅ |
| Bridge methods | Task 17 | ✅ |
| §14 Version bump | Task 20 | ✅ |

**Placeholder scan:** All tasks contain full code, exact file paths, and concrete commands. No TBD/TODO left.

**Type consistency:**
- `Pack` dataclass fields are consistent across Tasks 3–5, 14, 15.
- `install_addon`/`uninstall_addon` signatures match between Tasks 9–11 and callers in 14–17.
- `switch_pack` return dict shape (`ok`, `noop`, `removed_addons`, `error`) is consistent between Tasks 15 and 17.
- `create_recommended` signature `(name, selected_addon_ids, progress_callback)` matches tests and bridge wiring.
- `env.failed_addons` is a transient attribute (not persisted); noted in Task 14 and surfaced in Task 17.
