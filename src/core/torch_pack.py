"""Torch-Pack definitions, GPU-driven selection, remote refresh, and Pack switching."""
from __future__ import annotations

import json
import logging
import requests
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
        """Return all defined Packs as Pack objects."""
        data = self.load()
        return [Pack(**p) for p in data.get("packs", [])]

    def find(self, pack_id: str) -> Optional[Pack]:
        """Return the Pack with the given id, or None if unknown."""
        for p in self.list_packs():
            if p.id == pack_id:
                return p
        return None

    def get_pinned_deps(self) -> dict:
        """Return the global pinned_deps map ({package: version})."""
        return self.load().get("pinned_deps", {})

    def get_recommended_python(self) -> str:
        """Return the Python version recommended for fresh env creation."""
        return self.load().get("recommended_python", "")

    def get_recommended_uv_version(self) -> str:
        """Return the uv binary version to ensure in tools/uv/."""
        return self.load().get("recommended_uv_version", "")

    def get_remote_url(self) -> str:
        """Return the URL used by refresh_remote() to pull updated Pack data."""
        return self.load().get("remote_url", "")

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

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None
