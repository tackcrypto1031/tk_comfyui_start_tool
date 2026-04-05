"""Snapshot data model."""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Snapshot:
    """Represents a point-in-time snapshot of an environment."""

    id: str
    env_name: str
    created_at: str
    trigger: str = "manual"
    comfyui_commit: str = ""
    python_version: str = ""
    cuda_version: str = ""
    custom_nodes_state: list = field(default_factory=list)
    pip_freeze_path: str = ""
    config_backup_path: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        """Deserialize from dictionary, filling defaults for missing keys."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in data.items() if k in known_fields}
        return cls(**cleaned)
