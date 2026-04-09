"""Version manager - GPU detection, Python/CUDA version lists, and cache."""
import hashlib
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.models.environment import Environment
from src.utils import pip_ops

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

RECOMMENDED_PRESET = {
    "python_version": "3.13.11",
    "cuda_tag": "cu130",
    "pytorch_version": "2.9.1",
    "label_en": "Python 3.13.11 + CUDA 13.0 + PyTorch 2.9.1",
    "label_zh": "Python 3.13.11 + CUDA 13.0 + PyTorch 2.9.1",
}

_CREATE_NO_WINDOW = 0x08000000


class VersionManager:
    """Manages Python and CUDA version lists with GPU detection and local cache."""

    def __init__(self, config: dict):
        self.config = config
        self.base_dir = Path(config["base_dir"])
        self.tools_dir = self.base_dir / "tools"
        self._cache_path = self.tools_dir / "version_cache.json"

    def detect_gpu(self) -> dict:
        """Detect GPU via nvidia-smi and return driver CUDA version + recommended tag."""
        try:
            kwargs = {"capture_output": True, "text": True, "timeout": 10}
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

    def get_cache_info(self):
        """Return last_updated timestamp from cache, or None."""
        cache = self._load_cache()
        if cache:
            return cache.get("last_updated")
        return None

    @staticmethod
    def _base_version(version: str) -> str:
        """Strip local version suffixes like +cu130 from package versions."""
        return (version or "").split("+", 1)[0].strip()

    def get_recommended_preset(self) -> dict:
        """Return the recommended preset, preferring bundled Python when available."""
        preset = dict(RECOMMENDED_PRESET)
        bundled_version = self._get_bundled_python_version()
        if bundled_version:
            preset["python_version"] = bundled_version
            preset["label_en"] = (
                f"Python {bundled_version} + CUDA 13.0 + PyTorch {preset['pytorch_version']}"
            )
            preset["label_zh"] = (
                f"Python {bundled_version} + CUDA 13.0 + PyTorch {preset['pytorch_version']}"
            )
        return preset

    def _get_bundled_python_version(self) -> str:
        """Return bundled tools/python/python.exe version, or empty string if unavailable."""
        tools_python = self.tools_dir / "python" / "python.exe"
        if not tools_python.exists():
            return ""

        kwargs = {"capture_output": True, "text": True, "check": True}
        if sys.platform == "win32":
            kwargs["creationflags"] = _CREATE_NO_WINDOW

        try:
            result = subprocess.run([str(tools_python), "--version"], **kwargs)
            output = (result.stdout or result.stderr or "").strip()
            if output.startswith("Python "):
                return output.replace("Python ", "", 1).strip()
        except Exception:
            logger.debug("Failed to detect bundled python version", exc_info=True)
        return ""

    def get_pytorch_versions(self, cuda_tag: str, python_version: str = "") -> list:
        """Return PyTorch versions for given CUDA tag + Python version from cache or fetch.

        Returns a list of version strings sorted descending (e.g. ["2.6.0", "2.5.1", ...]).
        """
        cache = self._load_cache()
        cache_key = f"pytorch_{cuda_tag}"
        if cache and cache_key in cache:
            versions = cache[cache_key]
            if python_version:
                py_tag = self._python_version_to_cp_tag(python_version)
                if py_tag:
                    versions = [v for v in versions if py_tag in v.get("cp_tags", [])]
            return [v["version"] for v in versions]
        # Not cached — fetch live
        return self.fetch_pytorch_versions(cuda_tag, python_version)

    def fetch_pytorch_versions(self, cuda_tag: str, python_version: str = "") -> list:
        """Fetch available torch versions from PyTorch wheel index for a CUDA tag.

        Parses wheel filenames like: torch-2.6.0+cu130-cp313-cp313-win_amd64.whl
        Returns list of version strings sorted descending.
        """
        url = f"https://download.pytorch.org/whl/{cuda_tag}/torch/"
        try:
            response = requests.get(url, timeout=30)
            html = response.text
        except Exception as e:
            logger.warning("Failed to fetch PyTorch versions for %s: %s", cuda_tag, e)
            return []

        # Parse wheel filenames: torch-{ver}+{tag}-{cpXY}-{cpXY}-{platform}.whl
        pattern = re.compile(
            r'torch-(\d+\.\d+\.\d+)\+' + re.escape(cuda_tag)
            + r'-cp(\d+)-cp\d+-win_amd64\.whl'
        )
        # Collect versions with their supported Python cp tags
        version_cp: dict[str, set[str]] = {}
        for match in pattern.finditer(html):
            ver, cp = match.group(1), f"cp{match.group(2)}"
            version_cp.setdefault(ver, set()).add(cp)

        # Build structured list for caching
        structured = [
            {"version": ver, "cp_tags": sorted(cps)}
            for ver, cps in version_cp.items()
        ]
        structured.sort(
            key=lambda v: [int(x) for x in v["version"].split(".")],
            reverse=True,
        )

        # Save to cache under cuda_tag key
        cache = self._load_cache() or {}
        cache_key = f"pytorch_{cuda_tag}"
        cache[cache_key] = structured
        self._save_cache(cache)

        # Filter by python_version if provided
        if python_version:
            py_tag = self._python_version_to_cp_tag(python_version)
            if py_tag:
                structured = [v for v in structured if py_tag in v["cp_tags"]]

        return [v["version"] for v in structured]

    @staticmethod
    def _python_version_to_cp_tag(python_version: str) -> str:
        """Convert a Python version string like '3.13.11' or '3.13' to cp tag like 'cp313'."""
        parts = python_version.split(".")
        if len(parts) >= 2:
            return f"cp{parts[0]}{parts[1]}"
        return ""

    def refresh_python_versions(self) -> list:
        """Fetch Python embeddable versions from python.org and return sorted list."""
        try:
            response = requests.get("https://www.python.org/ftp/python/index-windows.json", timeout=15)
            entries = response.json()  # flat list of entries, not a dict
            if isinstance(entries, dict):
                entries = entries.get("versions", [])
        except Exception as e:
            raise RuntimeError(f"Failed to refresh Python versions: {e}") from e

        result = []
        for entry in entries:
            if entry.get("company") != "PythonEmbed":
                continue
            url = entry.get("url", "")
            if "64" not in url or "arm64" in url:
                continue
            result.append({
                "version": entry["sort-version"],
                "display": entry["display-name"],
                "url": url,
                "sha256": entry.get("hash", {}).get("sha256", ""),
            })

        # Filter out alpha/beta/rc versions and sort stable versions descending
        result = [v for v in result if re.fullmatch(r"\d+\.\d+\.\d+", v["version"])]
        result.sort(key=lambda v: [int(x) for x in v["version"].split(".")], reverse=True)
        return result

    def refresh_cuda_tags(self) -> list:
        """Fetch CUDA wheel tags from PyTorch download index and return sorted list."""
        try:
            response = requests.get("https://download.pytorch.org/whl/", timeout=15)
            html = response.text
        except Exception as e:
            raise RuntimeError(f"Failed to refresh CUDA tags: {e}") from e

        tags = re.findall(r'href="(cu\d+|cpu)/"', html)
        cpu_tags = [t for t in tags if t == "cpu"]
        cu_tags = sorted(set(t for t in tags if t.startswith("cu")), key=lambda t: int(t[2:]))
        return cpu_tags + cu_tags

    def refresh_all(self) -> dict:
        """Refresh all version lists, save to cache, and return cache data."""
        python_versions = self.refresh_python_versions()
        cuda_tags = self.refresh_cuda_tags()
        data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "python": python_versions,
            "cuda_tags": cuda_tags,
        }
        self._save_cache(data)

        # Fetch PyTorch versions for the recommended CUDA tag
        recommended_tag = RECOMMENDED_PRESET["cuda_tag"]
        self.fetch_pytorch_versions(recommended_tag)

        return data

    def get_python_executable(self, version: str, bundled_version: str = "") -> Path:
        """Return path to python.exe for the given version.

        If version matches bundled_version (and bundled_version is not empty),
        returns tools/python/python.exe. Otherwise returns tools/python_{version}/python.exe.
        Raises FileNotFoundError if the executable does not exist.
        """
        if bundled_version and version == bundled_version:
            path = self.tools_dir / "python" / "python.exe"
        else:
            path = self.tools_dir / f"python_{version}" / "python.exe"
        path = path.resolve()
        if not path.exists():
            raise FileNotFoundError(f"Python {version} is not installed. Expected at: {path}")
        return path

    def download_python(self, version: str, url: str, sha256: str = "",
                        progress_callback=None) -> Path:
        """Download and install an embedded Python build.

        Downloads the zip from *url* to tools/_temp/, verifies SHA256 if provided,
        extracts to tools/python_{version}/, enables pip via ._pth patch, runs
        get-pip.py, and cleans up. Returns the destination directory Path.
        Skips download if python.exe already exists in the destination.
        """
        dest = self.tools_dir / f"python_{version}"
        if (dest / "python.exe").exists():
            logger.debug("Python %s already installed at %s — skipping download", version, dest)
            return dest

        temp_dir = self.tools_dir / "_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = temp_dir / f"python-{version}-embed.zip"

        # Download zip
        if progress_callback:
            progress_callback(f"Downloading Python {version}...")
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                f.write(chunk)

        # Verify SHA256
        if sha256:
            if progress_callback:
                progress_callback("Verifying SHA256...")
            digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            if digest.lower() != sha256.lower():
                zip_path.unlink(missing_ok=True)
                raise ValueError(f"SHA256 mismatch for Python {version}: expected {sha256}, got {digest}")

        # Extract
        if progress_callback:
            progress_callback(f"Extracting Python {version}...")
        import zipfile
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)

        # Enable pip: replace #import site with import site in ._pth files
        for pth_file in dest.glob("python*._pth"):
            text = pth_file.read_text(encoding="utf-8")
            patched = text.replace("#import site", "import site")
            pth_file.write_text(patched, encoding="utf-8")

        # Download and run get-pip.py
        if progress_callback:
            progress_callback("Installing pip...")
        get_pip_path = temp_dir / "get-pip.py"
        pip_response = requests.get("https://bootstrap.pypa.io/get-pip.py", timeout=30)
        pip_response.raise_for_status()
        get_pip_path.write_bytes(pip_response.content)

        python_exe = dest / "python.exe"
        kwargs = {"capture_output": True, "text": True, "check": True}
        if sys.platform == "win32":
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        subprocess.run([str(python_exe), str(get_pip_path)], **kwargs)

        # Install virtualenv — embeddable Python lacks the built-in venv module
        if progress_callback:
            progress_callback("Installing virtualenv...")
        subprocess.run(
            [str(python_exe), "-m", "pip", "install", "virtualenv"],
            **kwargs,
        )

        # Cleanup
        zip_path.unlink(missing_ok=True)
        get_pip_path.unlink(missing_ok=True)

        if progress_callback:
            progress_callback(f"Python {version} installed.")
        return dest

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

    def reinstall_pytorch(self, env_name: str, cuda_tag: str,
                          progress_callback=None) -> dict:
        """Uninstall current PyTorch and install the version matching cuda_tag.

        Updates env_meta.json with the new cuda_tag, pytorch_version, and
        pip_freeze. Returns a dict with cuda_tag, pytorch_version, conflicts.
        """
        env_dir = Path(self.config["environments_dir"]) / env_name
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment not found: {env_dir}")

        venv_path = str(env_dir / "venv")

        def _progress(step: str, pct: int, msg: str) -> None:
            if progress_callback:
                progress_callback(step, pct, msg)

        _progress("uninstall", 10, "Uninstalling current PyTorch...")
        pip_ops.run_pip(venv_path, ["uninstall", "torch", "torchvision", "torchaudio", "-y"])

        _progress("install", 30, f"Installing PyTorch ({cuda_tag})...")
        pip_ops.run_pip_with_progress(
            venv_path,
            ["install", "torch", "torchvision",
             "--index-url", f"https://download.pytorch.org/whl/{cuda_tag}"],
            progress_callback=progress_callback,
        )

        freeze_data = pip_ops.freeze(venv_path)
        torch_version_base = self._base_version(freeze_data.get("torch", ""))
        torchaudio_version_base = self._base_version(freeze_data.get("torchaudio", ""))
        if torch_version_base and torchaudio_version_base != torch_version_base:
            if torchaudio_version_base:
                _progress("install", 55, "Removing incompatible torchaudio...")
                pip_ops.run_pip(venv_path, ["uninstall", "torchaudio", "-y"])
            _progress("install", 60, f"Installing torchaudio {torch_version_base}...")
            try:
                pip_ops.run_pip_with_progress(
                    venv_path,
                    [
                        "install",
                        f"torchaudio=={torch_version_base}",
                        "--index-url",
                        f"https://download.pytorch.org/whl/{cuda_tag}",
                    ],
                    progress_callback=progress_callback,
                )
            except Exception as e:
                logger.warning(
                    "No compatible torchaudio wheel for torch %s during reinstall (%s); continuing without torchaudio",
                    torch_version_base,
                    e,
                )

        freeze_data = pip_ops.freeze(venv_path)
        pytorch_version = freeze_data.get("torch", "")

        env = Environment.load_meta(str(env_dir))
        env.cuda_tag = cuda_tag
        env.pytorch_version = pytorch_version
        env.pip_freeze = freeze_data
        env.save_meta()

        _progress("analyze", 80, "Running conflict analysis...")
        try:
            pass  # ConflictAnalyzer requires a plugin path not available here
        except Exception as e:
            logger.warning("Conflict analysis skipped: %s", e)

        _progress("done", 100, "PyTorch reinstall complete!")
        return {"cuda_tag": cuda_tag, "pytorch_version": pytorch_version, "conflicts": []}
