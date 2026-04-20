"""File system operations and config management."""
import json
from pathlib import Path

_HARDCODED_DEFAULTS = {
    "default_env": "main",
    "python_path": None,
    "comfyui_repo_url": "https://github.com/comfyanonymous/ComfyUI.git",
    "base_dir": ".",
    "environments_dir": "./environments",
    "models_dir": "./models",
    "shared_model_mode": "default",
    "custom_model_path": "",
    "snapshots_dir": "./snapshots",
    "max_snapshots": 20,
    "auto_snapshot": True,
    "auto_open_browser": True,
    "default_port": 8188,
    "theme": "dark",
    "language": "zh-TW",
    "color_scheme": "tack-industrial",
    "log_level": "INFO",
    "model_subdirs": [
        "audio_encoders", "checkpoints", "clip", "clip_vision", "configs",
        "controlnet", "diffusers", "diffusion_models", "embeddings", "gligen",
        "hypernetworks", "latent_upscale_models", "loras", "model_patches",
        "photomaker", "style_models", "text_encoders", "unet",
        "upscale_models", "vae", "vae_approx",
    ],
    "conflict_analyzer": {
        "critical_packages": [
            "torch", "torchvision", "torchaudio",
            "numpy", "scipy", "transformers",
            "safetensors", "Pillow", "xformers",
            "opencv-python", "opencv-python-headless",
            "accelerate", "onnxruntime", "onnxruntime-gpu",
        ],
        "auto_analyze_on_install": True,
    },
    "ui_flags": {},
}


def _default_template_path(user_config_path: Path) -> Path:
    """Resolve config.default.json next to the user's config.json."""
    return user_config_path.parent / "config.default.json"


def get_default_config(user_config_path: str | Path | None = None) -> dict:
    """Return default configuration.

    Prefers config.default.json (shipped with repo) when available so
    repo-tuned defaults (expanded model_subdirs, pytorch_index_url, etc.)
    flow through to users seeding a fresh config.
    """
    if user_config_path is not None:
        template = _default_template_path(Path(user_config_path))
        if template.exists():
            try:
                return json.loads(template.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    return dict(_HARDCODED_DEFAULTS)


def load_config(path: str) -> dict:
    """Load config from JSON file. Creates default if missing, fills missing keys."""
    config_path = Path(path)
    defaults = get_default_config(config_path)

    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        # Fill missing keys from defaults
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
        return data

    # Seed user config from defaults on first run
    save_config(defaults, path)
    return defaults


def save_config(config: dict, path: str) -> None:
    """Save config to JSON file."""
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ensure_dirs(config: dict) -> None:
    """Ensure all required directories exist."""
    for key in ("environments_dir", "models_dir", "snapshots_dir"):
        Path(config[key]).mkdir(parents=True, exist_ok=True)

    # Create model subdirectories
    models_dir = Path(config["models_dir"])
    for subdir in config.get("model_subdirs", []):
        (models_dir / subdir).mkdir(parents=True, exist_ok=True)
