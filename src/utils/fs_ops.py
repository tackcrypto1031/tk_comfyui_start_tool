"""File system operations and config management."""
import ctypes
import json
import os
import platform
import subprocess
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


# ---------------------------------------------------------------------------
# NTFS junction primitives (Windows-only)
# ---------------------------------------------------------------------------

IS_WINDOWS = platform.system() == "Windows"

_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_SUBPROCESS_CREATE_NO_WINDOW = 0x08000000


def create_junction(link: Path, target: Path) -> None:
    """Create an NTFS junction at `link` pointing to directory `target`.

    Uses `mklink /J` via cmd.exe — no admin required, same-volume NTFS only.
    Raises OSError on failure; callers should fall back to create_symlink_dir.
    """
    if not IS_WINDOWS:
        raise OSError("Junctions are only supported on Windows")
    link = Path(link)
    target = Path(target)
    if link.exists() or is_junction(link):
        raise FileExistsError(f"Link path already exists: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target.resolve())],
        capture_output=True,
        text=True,
        creationflags=_SUBPROCESS_CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise OSError(
            f"mklink /J failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )


def is_junction(path: Path) -> bool:
    """Return True if path is an NTFS junction (directory reparse point)."""
    if not IS_WINDOWS:
        return False
    p = Path(path)
    if not p.exists() and not p.is_symlink():
        return False
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))
    except Exception:
        return False
    if attrs == 0xFFFFFFFF:
        return False
    return bool(attrs & _FILE_ATTRIBUTE_REPARSE_POINT)


def remove_junction(path: Path) -> None:
    """Remove a junction WITHOUT deleting target contents.

    On Windows, Path.rmdir() on a reparse point only removes the link.
    shutil.rmtree would follow the reparse point and delete target contents.
    """
    p = Path(path)
    if not is_junction(p):
        raise ValueError(f"Not a junction: {p}")
    os.rmdir(str(p))


# ---------------------------------------------------------------------------
# Symlink primitives and volume helpers
# ---------------------------------------------------------------------------

def same_volume(a: Path, b: Path) -> bool:
    """Return True if both paths reside on the same Windows volume (drive)."""
    if not IS_WINDOWS:
        return True  # Non-Windows: treat as same volume (moot — we won't junction)
    try:
        da = Path(a).resolve().drive.upper()
        db = Path(b).resolve().drive.upper()
    except Exception:
        return False
    return bool(da and da == db)


def create_symlink_dir(link: Path, target: Path) -> None:
    """Create a directory symlink (needs Developer Mode or admin on Windows).

    Raises OSError on failure so callers can fall back to yaml_only mode.
    """
    link = Path(link)
    target = Path(target)
    if link.exists() or link.is_symlink():
        raise FileExistsError(f"Link path already exists: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(str(target.resolve()), str(link), target_is_directory=True)
