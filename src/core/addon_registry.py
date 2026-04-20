"""Add-on registry — loads shipped JSON, applies remote + override layers."""
from __future__ import annotations

import json
import logging
import requests
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Addon:
    id: str
    label: str
    description: str
    kind: Literal["pip", "custom_node"]
    compatible_packs: tuple[str, ...]
    wheels_by_pack: Optional[dict] = None
    pip_spec: Optional[str] = None
    pip_project_name: Optional[str] = None
    source_repo: Optional[str] = None
    source_ref: Optional[str] = None
    source_post_install: Optional[list] = None
    requires_compile: bool = False
    pack_pinned: bool = False
    risk_note: Optional[str] = None


class AddonRegistry:
    def __init__(
        self,
        shipped_path: Path,
        remote_path: Path,
        override_path: Path,
    ):
        self.shipped_path = Path(shipped_path)
        self.remote_path = Path(remote_path)
        self.override_path = Path(override_path)
        self._cache: Optional[list[Addon]] = None

    def list_addons(self) -> list[Addon]:
        if self._cache is not None:
            return self._cache
        raw = self._pick_source()
        overrides = self._load_overrides()
        merged = [
            self._entry_to_addon(self._apply_override(e, overrides.get(e["id"], {})))
            for e in raw.get("addons", [])
        ]
        self._cache = merged
        return self._cache

    def find(self, addon_id: str) -> Optional[Addon]:
        for a in self.list_addons():
            if a.id == addon_id:
                return a
        return None

    def has_override(self, addon_id: str) -> bool:
        return addon_id in self._load_overrides()

    def save_override(self, addon_id: str, partial_fields: dict) -> None:
        raw = self._read_json(self.override_path) or {
            "schema_version": SCHEMA_VERSION, "overrides": {}
        }
        if raw.get("schema_version") != SCHEMA_VERSION:
            raw = {"schema_version": SCHEMA_VERSION, "overrides": {}}
        raw.setdefault("overrides", {})[addon_id] = partial_fields
        self.override_path.parent.mkdir(parents=True, exist_ok=True)
        self.override_path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._cache = None

    def clear_override(self, addon_id: Optional[str] = None) -> None:
        raw = self._read_json(self.override_path)
        if not raw:
            return
        if addon_id is None:
            raw["overrides"] = {}
        else:
            raw.setdefault("overrides", {}).pop(addon_id, None)
        self.override_path.parent.mkdir(parents=True, exist_ok=True)
        self.override_path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._cache = None

    def get_shipped_and_override(self, addon_id: str) -> Optional[dict]:
        shipped_raw = self._read_json(self.shipped_path) or {}
        shipped_entry = next(
            (e for e in shipped_raw.get("addons", []) if e["id"] == addon_id), None
        )
        if shipped_entry is None:
            return None
        override = self._load_overrides().get(addon_id, {})
        effective = self._apply_override(shipped_entry, override)
        return {
            "shipped": shipped_entry,
            "override": override,
            "effective": effective,
        }

    def get_remote_url(self) -> str:
        shipped = self._read_json(self.shipped_path) or {}
        return shipped.get("remote_url", "")

    def refresh_remote(self, timeout: int = 15) -> dict:
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
        self._cache = None
        return {"ok": True, "error": ""}

    def _pick_source(self) -> dict:
        remote = self._read_json(self.remote_path)
        if remote and remote.get("schema_version") == SCHEMA_VERSION:
            return remote
        if remote is not None:
            logger.warning(
                "Remote addons.json schema mismatch (got %s, expected %s); using shipped",
                remote.get("schema_version"), SCHEMA_VERSION,
            )
        return self._read_json(self.shipped_path) or {}

    def _load_overrides(self) -> dict:
        raw = self._read_json(self.override_path)
        if not raw:
            return {}
        if raw.get("schema_version") != SCHEMA_VERSION:
            logger.warning(
                "addons_override.json schema mismatch (got %s, expected %s); ignoring",
                raw.get("schema_version"), SCHEMA_VERSION,
            )
            return {}
        return raw.get("overrides") or {}

    @staticmethod
    def _apply_override(entry: dict, override: dict) -> dict:
        if not override:
            return entry
        merged = dict(entry)
        for key, value in override.items():
            if key == "wheels_by_pack" and isinstance(value, dict):
                base = dict(entry.get("wheels_by_pack") or {})
                base.update(value)
                merged[key] = base
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _entry_to_addon(entry: dict) -> Addon:
        return Addon(
            id=entry["id"],
            label=entry["label"],
            description=entry["description"],
            kind=entry["kind"],
            compatible_packs=tuple(entry.get("compatible_packs") or ()),
            wheels_by_pack=entry.get("wheels_by_pack"),
            pip_spec=entry.get("pip_spec"),
            pip_project_name=entry.get("pip_project_name"),
            source_repo=entry.get("source_repo"),
            source_ref=entry.get("source_ref"),
            source_post_install=entry.get("source_post_install"),
            requires_compile=bool(entry.get("requires_compile", False)),
            pack_pinned=bool(entry.get("pack_pinned", False)),
            risk_note=entry.get("risk_note"),
        )

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None
