"""Version manager - GPU detection, Python/CUDA version lists, and cache."""
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("version_manager")

DEFAULT_PYTHON_VERSIONS = [
    {"version": "3.10", "display": "Python 3.10"},
    {"version": "3.11", "display": "Python 3.11"},
    {"version": "3.12", "display": "Python 3.12"},
    {"version": "3.13", "display": "Python 3.13"},
]

DEFAULT_CUDA_TAGS = ["cpu", "cu118", "cu121", "cu124", "cu126", "cu128"]

CUDA_TAG_VERSIONS = {
    "cu118": 11.8,
    "cu121": 12.1,
    "cu124": 12.4,
    "cu126": 12.6,
    "cu128": 12.8,
    "cu130": 13.0,
}

_CREATE_NO_WINDOW = 0x08000000


class VersionManager:
    """Manages Python and CUDA version lists with GPU detection and local cache."""

    def __init__(self, config: dict):
        self.config = config
        self.base_dir = Path(config["base_dir"])
        self._cache_path = self.base_dir / "tools" / "version_cache.json"

    def detect_gpu(self) -> dict:
        """Detect GPU via nvidia-smi and return driver CUDA version + recommended tag."""
        try:
            kwargs = {"capture_output": True, "text": True, "timeout": 10}
            import sys
            if sys.platform == "win32":
                kwargs["creationflags"] = _CREATE_NO_WINDOW
            result = subprocess.run(["nvidia-smi"], **kwargs)
            output = result.stdout
        except FileNotFoundError:
            logger.debug("nvidia-smi not found — no GPU")
            return {"has_gpu": False, "cuda_driver_version": "", "recommended_cuda_tag": "cpu"}
        except subprocess.TimeoutExpired:
            logger.warning("nvidia-smi timed out")
            return {"has_gpu": False, "cuda_driver_version": "", "recommended_cuda_tag": "cpu"}

        # Parse "CUDA Version: XX.Y" from output
        import re
        match = re.search(r"CUDA Version:\s*(\d+\.\d+)", output)
        if not match:
            logger.debug("nvidia-smi ran but no CUDA Version found")
            return {"has_gpu": False, "cuda_driver_version": "", "recommended_cuda_tag": "cpu"}

        driver_version = match.group(1)
        driver_float = float(driver_version)
        recommended = self._map_cuda_tag(driver_float)

        return {
            "has_gpu": True,
            "cuda_driver_version": driver_version,
            "recommended_cuda_tag": recommended,
        }

    def _map_cuda_tag(self, driver_version: float) -> str:
        """Return highest CUDA tag whose version is <= driver_version."""
        best_tag = "cpu"
        best_ver = 0.0
        for tag, ver in CUDA_TAG_VERSIONS.items():
            if ver <= driver_version and ver > best_ver:
                best_tag = tag
                best_ver = ver
        return best_tag

    def get_python_versions(self) -> list:
        """Return Python version list from cache if available, else defaults."""
        cache = self._load_cache()
        if cache and "python" in cache:
            return cache["python"]
        return DEFAULT_PYTHON_VERSIONS

    def get_cuda_tags(self) -> list:
        """Return CUDA tag list from cache if available, else defaults."""
        cache = self._load_cache()
        if cache and "cuda_tags" in cache:
            return cache["cuda_tags"]
        return DEFAULT_CUDA_TAGS

    def get_cache_info(self) -> dict | None:
        """Return the full cache dict or None if no cache exists."""
        return self._load_cache()

    def _load_cache(self) -> dict | None:
        """Load version cache from disk. Returns None if not found or invalid."""
        if not self._cache_path.exists():
            return None
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load version cache: %s", e)
            return None

    def _save_cache(self, data: dict) -> None:
        """Save version cache to disk."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("Failed to save version cache: %s", e)
