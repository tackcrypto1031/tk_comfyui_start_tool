"""File-system layer bridge for shared models.

Implements per-subdir NTFS junctions (with symlink/yaml_only fallback)
so nodes that download to hard-coded ComfyUI/models/<subdir>/ paths
land in the shared models directory.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from src.models.environment import Environment
from src.utils import fs_ops

logger = logging.getLogger(__name__)


@dataclass
class EnableResult:
    mechanism: str
    migrated_count: int = 0
    renamed_files: list = field(default_factory=list)
    skipped_files: list = field(default_factory=list)


@dataclass
class DisableResult:
    junctions_removed: int = 0
    errors: list = field(default_factory=list)


@dataclass
class VerifyReport:
    ok: bool
    repaired: list = field(default_factory=list)
    problems: list = field(default_factory=list)


class SharedModelBridge:
    """Owns the file-system layer of shared models."""

    def __init__(self, config: dict, shared_path_resolver: Callable[[], Path]):
        self.config = config
        self._resolve_shared = shared_path_resolver

    def _excluded_subdirs(self) -> set[str]:
        return set(self.config.get("shared_model_subdirs_excluded", ["configs"]))

    def _active_subdirs(self) -> list[str]:
        excluded = self._excluded_subdirs()
        return [s for s in self.config.get("model_subdirs", []) if s not in excluded]

    def _models_dir(self, env_path: Path) -> Path:
        return Path(env_path) / "ComfyUI" / "models"

    def detect_capability(self, shared_path: Path, env_path: Path) -> str:
        """Return 'junction' | 'symlink' | 'yaml_only'."""
        shared_path = Path(shared_path)
        env_models = self._models_dir(env_path)
        shared_path.mkdir(parents=True, exist_ok=True)
        env_models.mkdir(parents=True, exist_ok=True)

        if fs_ops.same_volume(shared_path, env_models):
            return "junction"

        # Cross-volume: probe whether symlinks are allowed
        probe_target = shared_path / ".__probe_target__"
        probe_link = env_models / ".__probe_link__"
        probe_target.mkdir(exist_ok=True)
        try:
            fs_ops.create_symlink_dir(probe_link, probe_target)
        except OSError:
            return "yaml_only"
        finally:
            try:
                if probe_link.is_symlink() or probe_link.exists():
                    probe_link.unlink()
            except Exception:
                pass
            try:
                probe_target.rmdir()
            except Exception:
                pass
        return "symlink"
