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

    def enable(self, env_path: Path, progress_cb: Optional[Callable[[dict], bool]] = None) -> EnableResult:
        """Enable file-system-layer shared models for an env.

        Idempotent. Resumable: if migration_state == 'migrating' from a prior
        run, simply continues (each subdir is independently checked).
        """
        env_path = Path(env_path)
        shared = self._resolve_shared()
        models_dir = self._models_dir(env_path)
        models_dir.mkdir(parents=True, exist_ok=True)
        shared.mkdir(parents=True, exist_ok=True)

        env_meta = Environment.load_meta(str(env_path))
        env_meta.path = str(env_path)

        mechanism = self.detect_capability(shared, env_path)
        if mechanism == "yaml_only":
            env_meta.shared_model_mechanism = "yaml_only"
            env_meta.shared_model_migration_state = "done"
            env_meta.save_meta()
            return EnableResult(mechanism="yaml_only")

        lock_path = shared / ".shared_lock"
        with fs_ops.acquire_shared_lock(lock_path, timeout=30):
            env_meta.shared_model_migration_state = "migrating"
            env_meta.save_meta()

            totals = {"migrated": 0, "renamed": 0, "skipped_identical": 0, "placeholders_removed": 0}
            renamed_list: list[str] = []

            for subdir in self._active_subdirs():
                env_sub = models_dir / subdir
                shared_sub = shared / subdir
                shared_sub.mkdir(parents=True, exist_ok=True)

                if not env_sub.exists():
                    self._create_link(env_sub, shared_sub, mechanism)
                    continue

                if fs_ops.is_junction(env_sub) or env_sub.is_symlink():
                    # Already linked — idempotent, skip
                    continue

                stats = self.migrate_files(env_sub, shared_sub, progress_cb)
                if stats.get("cancelled"):
                    env_meta.shared_model_migration_state = "migrating"
                    env_meta.save_meta()
                    return EnableResult(mechanism=mechanism, migrated_count=totals["migrated"],
                                        renamed_files=renamed_list)
                for k in totals:
                    totals[k] += stats.get(k, 0)

                try:
                    shutil.rmtree(str(env_sub))
                except OSError as exc:
                    logger.warning("Failed to remove %s after migration: %s", env_sub, exc)
                    continue
                self._create_link(env_sub, shared_sub, mechanism)

            env_meta.shared_model_enabled = True
            env_meta.shared_model_mechanism = mechanism
            env_meta.shared_model_migration_state = "done"
            env_meta.save_meta()

        return EnableResult(
            mechanism=mechanism,
            migrated_count=totals["migrated"],
            renamed_files=renamed_list,
        )

    def _create_link(self, link: Path, target: Path, mechanism: str) -> None:
        if mechanism == "junction":
            fs_ops.create_junction(link, target)
        elif mechanism == "symlink":
            fs_ops.create_symlink_dir(link, target)
        else:
            raise ValueError(f"Unsupported link mechanism: {mechanism}")

    def attach_subdir(self, env_path: Path, subdir: str,
                      progress_cb: Optional[Callable[[dict], bool]] = None) -> None:
        """Enable a single subdir (used for newly discovered dirs)."""
        if subdir in self._excluded_subdirs():
            return
        env_path = Path(env_path)
        shared = self._resolve_shared()
        env_meta = Environment.load_meta(str(env_path))
        env_meta.path = str(env_path)
        mechanism = env_meta.shared_model_mechanism or self.detect_capability(shared, env_path)
        if mechanism == "yaml_only":
            return  # Nothing FS-layer to do

        env_sub = self._models_dir(env_path) / subdir
        shared_sub = shared / subdir
        shared_sub.mkdir(parents=True, exist_ok=True)

        with fs_ops.acquire_shared_lock(shared / ".shared_lock", timeout=30):
            if fs_ops.is_junction(env_sub) or env_sub.is_symlink():
                return  # already linked
            if env_sub.exists():
                self.migrate_files(env_sub, shared_sub, progress_cb)
                try:
                    shutil.rmtree(str(env_sub))
                except OSError as exc:
                    logger.warning("attach_subdir rmtree failed for %s: %s", env_sub, exc)
                    return
            self._create_link(env_sub, shared_sub, mechanism)

    def verify(self, env_path: Path) -> VerifyReport:
        """Check all managed subdirs. Repair dangling junctions when possible."""
        env_path = Path(env_path)
        shared = self._resolve_shared()
        models_dir = self._models_dir(env_path)
        if not models_dir.exists():
            return VerifyReport(ok=True)

        try:
            env_meta = Environment.load_meta(str(env_path))
        except FileNotFoundError:
            return VerifyReport(ok=True)
        mechanism = env_meta.shared_model_mechanism
        if mechanism not in ("junction", "symlink"):
            return VerifyReport(ok=True)

        repaired: list[str] = []
        problems: list[str] = []

        for subdir in self._active_subdirs():
            link = models_dir / subdir
            target = shared / subdir
            if fs_ops.is_junction(link) or link.is_symlink():
                if not target.exists():
                    try:
                        if fs_ops.is_junction(link):
                            fs_ops.remove_junction(link)
                        else:
                            link.unlink()
                        target.mkdir(parents=True, exist_ok=True)
                        self._create_link(link, target, mechanism)
                        repaired.append(f"rebuilt {subdir}")
                    except Exception as exc:
                        problems.append(f"{subdir}: {exc}")
            elif link.exists() and link.is_dir():
                problems.append(f"{subdir}: expected junction, found real directory")
            else:
                try:
                    target.mkdir(parents=True, exist_ok=True)
                    self._create_link(link, target, mechanism)
                    repaired.append(f"created {subdir}")
                except Exception as exc:
                    problems.append(f"{subdir}: {exc}")

        return VerifyReport(ok=(not problems), repaired=repaired, problems=problems)

    def safe_remove_env(self, env_path: Path) -> None:
        """Remove every junction under env before shutil.rmtree'ing env_path."""
        env_path = Path(env_path)
        models_dir = self._models_dir(env_path)
        if models_dir.exists():
            for child in list(models_dir.iterdir()):
                if fs_ops.is_junction(child):
                    try:
                        fs_ops.remove_junction(child)
                    except Exception as exc:
                        logger.warning("safe_remove_env: failed to remove junction %s: %s",
                                       child, exc)
                elif child.is_symlink():
                    try:
                        child.unlink()
                    except Exception as exc:
                        logger.warning("safe_remove_env: failed to remove symlink %s: %s",
                                       child, exc)
        shutil.rmtree(str(env_path), ignore_errors=False)

    def disable(self, env_path: Path) -> DisableResult:
        """Remove all junctions under env/ComfyUI/models/ (shared files untouched)."""
        env_path = Path(env_path)
        models_dir = self._models_dir(env_path)
        shared = self._resolve_shared()
        lock_path = shared / ".shared_lock"
        removed = 0
        errors: list[str] = []

        with fs_ops.acquire_shared_lock(lock_path, timeout=30):
            if models_dir.exists():
                for child in list(models_dir.iterdir()):
                    if fs_ops.is_junction(child) or child.is_symlink():
                        try:
                            if fs_ops.is_junction(child):
                                fs_ops.remove_junction(child)
                            else:
                                child.unlink()
                            child.mkdir(parents=True, exist_ok=True)
                            removed += 1
                        except Exception as exc:
                            errors.append(f"{child.name}: {exc}")

            # Rename extra_model_paths.yaml to .disabled (preserve legacy behavior)
            comfy = env_path / "ComfyUI"
            yaml_active = comfy / "extra_model_paths.yaml"
            yaml_disabled = comfy / "extra_model_paths.yaml.disabled"
            if yaml_active.exists():
                if yaml_disabled.exists():
                    yaml_disabled.unlink()
                yaml_active.rename(yaml_disabled)

            try:
                env_meta = Environment.load_meta(str(env_path))
                env_meta.path = str(env_path)
                env_meta.shared_model_enabled = False
                env_meta.shared_model_mechanism = "none"
                env_meta.save_meta()
            except FileNotFoundError:
                pass

        return DisableResult(junctions_removed=removed, errors=errors)
