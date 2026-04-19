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
