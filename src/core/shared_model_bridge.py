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

    _PLACEHOLDER_PREFIX = "put_"
    _PLACEHOLDER_SUFFIX = "_here"

    def _is_placeholder(self, name: str) -> bool:
        return name.startswith(self._PLACEHOLDER_PREFIX) and name.endswith(self._PLACEHOLDER_SUFFIX)

    def _unique_rename_target(self, base: Path) -> Path:
        """Return a non-existent path shaped like <stem>.envlocal[.N]<suffix>."""
        stem = base.stem
        suffix = base.suffix
        parent = base.parent
        candidate = parent / f"{stem}.envlocal{suffix}"
        counter = 1
        while candidate.exists():
            candidate = parent / f"{stem}.envlocal.{counter}{suffix}"
            counter += 1
        return candidate

    def migrate_files(self, env_sub: Path, shared_sub: Path,
                      progress_cb: Optional[Callable[[dict], bool]] = None) -> dict:
        """Move files from env_sub into shared_sub using size+mtime+hash conflict rules.

        Returns dict with counters. If progress_cb returns False, stops early
        (leaving env_sub partially populated — next call will resume).
        """
        env_sub = Path(env_sub)
        shared_sub = Path(shared_sub)
        shared_sub.mkdir(parents=True, exist_ok=True)
        stats = {"migrated": 0, "renamed": 0, "skipped_identical": 0, "placeholders_removed": 0}

        files = [p for p in env_sub.rglob("*") if p.is_file()]
        total = len(files)
        for idx, src in enumerate(files):
            rel = src.relative_to(env_sub)
            if self._is_placeholder(src.name):
                src.unlink()
                stats["placeholders_removed"] += 1
                continue
            dest = shared_sub / rel
            dest.parent.mkdir(parents=True, exist_ok=True)

            if not dest.exists():
                shutil.move(str(src), str(dest))
                stats["migrated"] += 1
            else:
                src_size, src_mtime = fs_ops.size_mtime(src)
                dest_size, dest_mtime = fs_ops.size_mtime(dest)
                if src_size != dest_size:
                    renamed_dest = self._unique_rename_target(dest)
                    shutil.move(str(src), str(renamed_dest))
                    stats["renamed"] += 1
                elif abs(src_mtime - dest_mtime) < 1.0:
                    src.unlink()
                    stats["skipped_identical"] += 1
                else:
                    if fs_ops.hash_file(src) == fs_ops.hash_file(dest):
                        src.unlink()
                        stats["skipped_identical"] += 1
                    else:
                        renamed_dest = self._unique_rename_target(dest)
                        shutil.move(str(src), str(renamed_dest))
                        stats["renamed"] += 1

            if progress_cb is not None:
                pct = int((idx + 1) / max(total, 1) * 100)
                cont = progress_cb({
                    "file": str(rel),
                    "done": idx + 1,
                    "total": total,
                    "pct": pct,
                })
                if cont is False:
                    stats["cancelled"] = True
                    break
        return stats
