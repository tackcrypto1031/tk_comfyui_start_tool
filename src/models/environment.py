"""Environment data model."""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


LAUNCH_SETTINGS_DEFAULTS = {
    "cross_attention": "auto",
    "vram_mode": "normal",
    "reserve_vram": None,
    "async_offload": "auto",
    "smart_memory": True,
    "listen": "",
    "port": 8188,
    "auto_launch": True,
    "cors_origin": "",
    "tls_keyfile": "",
    "tls_certfile": "",
    "custom_args": "",
    "auto_diagnostics": False,
}


@dataclass
class Environment:
    """Represents a ComfyUI runtime environment."""

    name: str
    created_at: str
    comfyui_commit: str = ""
    comfyui_branch: str = "master"
    python_version: str = ""
    cuda_tag: str = ""
    pytorch_version: str = ""
    pip_freeze: dict = field(default_factory=dict)
    # Each entry: {name, repo_url, commit, enabled (default True)}
    # The 'enabled' field is optional for backward compatibility.
    custom_nodes: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)
    parent_env: Optional[str] = None
    path: str = ""
    merge_history: list = field(default_factory=list)
    launch_settings: dict = field(default_factory=dict)
    shared_model_enabled: bool = True

    def get_launch_settings(self) -> dict:
        """Return launch_settings merged with defaults (lazy fallback)."""
        return {**LAUNCH_SETTINGS_DEFAULTS, **self.launch_settings}

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Environment":
        """Deserialize from dictionary, filling defaults for missing keys."""
        defaults = cls.__dataclass_fields__
        cleaned = {}
        for f_name, f_def in defaults.items():
            if f_name in data:
                cleaned[f_name] = data[f_name]
            elif f_def.default is not f_def.default_factory:
                if f_def.default is not dataclass_sentinel():
                    cleaned[f_name] = f_def.default
            # else: default_factory will handle it
        return cls(**cleaned)

    def save_meta(self) -> None:
        """Write env_meta.json to the environment directory."""
        if not self.path:
            raise ValueError("Environment path is not set")
        meta_path = Path(self.path) / "env_meta.json"
        data = self.to_dict()
        data.pop("path", None)  # Don't persist the path itself
        meta_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load_meta(cls, env_path: str) -> "Environment":
        """Load env_meta.json from an environment directory."""
        meta_path = Path(env_path) / "env_meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"env_meta.json not found in {env_path}")
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        data["path"] = str(env_path)
        return cls.from_dict(data)


def dataclass_sentinel():
    """Return the MISSING sentinel from dataclasses."""
    from dataclasses import MISSING
    return MISSING
