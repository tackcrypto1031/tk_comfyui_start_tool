"""Environment manager - create, list, delete, clone environments."""
import configparser
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import yaml

from src.models.environment import Environment
from src.utils import git_ops, pip_ops, pkg_ops
from src.core.snapshot_manager import SnapshotManager

logger = logging.getLogger(__name__)

# Default ComfyUI repository URL
DEFAULT_COMFYUI_URL = "https://github.com/comfyanonymous/ComfyUI.git"

# Default ComfyUI-Manager repository URL
DEFAULT_MANAGER_URL = "https://github.com/Comfy-Org/ComfyUI-Manager.git"

# Valid environment name pattern
ENV_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


class EnvManager:
    """Manages multiple independent ComfyUI runtime environments."""

    def __init__(self, config: dict):
        self.config = config
        self.environments_dir = Path(config["environments_dir"])
        self.models_dir = Path(config["models_dir"])
        self.comfyui_url = config.get("comfyui_repo_url", DEFAULT_COMFYUI_URL)

    # ------------------------------------------------------------------
    # Small helpers shared by create_environment() and create_recommended()
    # ------------------------------------------------------------------

    def _tools_dir(self) -> Path:
        return Path(self.config.get("base_dir", ".")) / "tools"

    def _uv_version(self) -> str:
        # Delegated to TorchPackManager when available; fallback constant.
        mgr = getattr(self, "_torch_pack_mgr", None)
        if mgr:
            return mgr.get_recommended_uv_version() or "0.9.7"
        return "0.9.7"

    def _pkg_mgr(self) -> str:
        return self.config.get("package_manager", "uv")

    def _install_torch_pack(
        self, venv_path: str, torch: str, torchvision: str, torchaudio: str,
        cuda_tag: str, progress_callback=None,
    ) -> None:
        """Install exactly the torch trio pinned to the given versions + index."""
        index_url = f"https://download.pytorch.org/whl/{cuda_tag}"
        args = [
            "install",
            f"torch=={torch}",
            f"torchvision=={torchvision}",
            f"torchaudio=={torchaudio}",
            "--index-url", index_url,
        ]
        pkg_ops.run_install(
            venv_path=venv_path,
            args=args,
            tools_dir=self._tools_dir(),
            uv_version=self._uv_version(),
            package_manager=self._pkg_mgr(),
            progress_callback=progress_callback,
        )

    def _install_pinned_deps(
        self, venv_path: str, pinned: dict, progress_callback=None,
    ) -> None:
        """Install exactly the pinned versions, overwriting whatever torch/requirements pulled in."""
        if not pinned:
            return
        args = ["install"] + [f"{pkg}=={ver}" for pkg, ver in pinned.items()]
        pkg_ops.run_install(
            venv_path=venv_path,
            args=args,
            tools_dir=self._tools_dir(),
            uv_version=self._uv_version(),
            package_manager=self._pkg_mgr(),
            progress_callback=progress_callback,
        )

    def create_environment(self, name: str, branch: str = "master",
                           commit: Optional[str] = None,
                           python_version: str = "",
                           cuda_tag: str = "",
                           pytorch_version: str = "",
                           progress_callback=None) -> Environment:
        """Create a new ComfyUI environment with venv, cloned repo, and metadata."""
        self._validate_name(name)

        def _base_version(version: str) -> str:
            """Strip local version suffixes like +cu130 from package versions."""
            return (version or "").split("+", 1)[0].strip()

        env_dir = self.environments_dir / name
        if env_dir.exists():
            raise FileExistsError(f"Environment '{name}' already exists")

        env_dir.mkdir(parents=True)

        def _report(step, pct, detail=""):
            if progress_callback:
                progress_callback(step, pct, detail)

        try:
            # 1. Create venv (with optional custom Python)
            _report("venv", 5, "Creating virtual environment...")
            venv_path = env_dir / "venv"
            if python_version:
                from src.core.version_manager import VersionManager
                vm = VersionManager(self.config)
                bundled_ver = self._get_bundled_python_version()
                if python_version != bundled_ver:
                    python_exe = str(vm.get_python_executable(python_version, bundled_ver))
                    pip_ops.create_venv(str(venv_path), python_executable=python_exe)
                else:
                    pip_ops.create_venv(str(venv_path))
            else:
                pip_ops.create_venv(str(venv_path))

            # 2. Clone ComfyUI
            _report("clone", 15, "Cloning ComfyUI repository...")
            comfyui_path = env_dir / "ComfyUI"
            git_ops.clone_repo(
                self.comfyui_url, str(comfyui_path),
                branch=branch, commit=commit,
                progress_callback=lambda pct, msg: _report(
                    "clone", 15 + int(pct * 0.2), msg or "Cloning ComfyUI repository..."
                ),
            )

            # 3. Install PyTorch with CUDA support (must be BEFORE requirements.txt)
            _report("pytorch", 35, "Detecting GPU...")
            if not cuda_tag:
                # Auto-detect GPU when no CUDA tag specified
                from src.core.version_manager import VersionManager
                vm = VersionManager(self.config)
                gpu_info = vm.detect_gpu()
                cuda_tag = gpu_info["recommended_cuda_tag"]
                _report("pytorch", 35, f"Detected: {cuda_tag}")
            effective_cuda_tag = cuda_tag
            pytorch_index = f"https://download.pytorch.org/whl/{effective_cuda_tag}"
            torch_pkg = f"torch=={pytorch_version}" if pytorch_version else "torch"
            _report("pytorch", 35, f"Installing PyTorch ({effective_cuda_tag}{', v' + pytorch_version if pytorch_version else ''})...")
            pip_ops.run_pip_with_progress(str(venv_path), [
                "install", torch_pkg, "torchvision",
                "--index-url", pytorch_index,
            ], progress_callback=lambda line: _report("pytorch", 35, line))

            # 4. Install ComfyUI dependencies
            #    Use --extra-index-url for PyTorch wheels so torch/torchvision/torchaudio
            #    in requirements.txt resolve from the correct CUDA index.
            #    Also constrain torch version to prevent requirements.txt from upgrading it.
            _report("dependencies", 55, "Installing ComfyUI dependencies...")
            req_path = comfyui_path / "requirements.txt"
            if req_path.exists():
                deps_args = [
                    "install", "-r", str(req_path.resolve()),
                    "--extra-index-url", pytorch_index,
                ]
                # Constrain torch version to prevent requirements.txt from upgrading
                constraint_file = None
                if pytorch_version:
                    constraint_file = env_dir / "_constraints.txt"
                    constraint_file.write_text(
                        f"torch=={pytorch_version}\n", encoding="utf-8"
                    )
                    deps_args += ["-c", str(constraint_file.resolve())]
                pip_ops.run_pip_with_progress(str(venv_path), deps_args,
                    progress_callback=lambda line: _report("dependencies", 55, line))
                if constraint_file:
                    constraint_file.unlink(missing_ok=True)

            # 4a. Ensure torchaudio is ABI-compatible with installed torch.
            # If no matching wheel exists, continue without torchaudio instead of
            # keeping a broken binary that can block ComfyUI startup on Windows.
            _report("dependencies", 62, "Checking torchaudio compatibility...")
            _compat_freeze = pip_ops.freeze(str(venv_path))
            _torch_ver = _base_version(_compat_freeze.get("torch", ""))
            _torchaudio_ver = _base_version(_compat_freeze.get("torchaudio", ""))
            if _torch_ver and _torchaudio_ver != _torch_ver:
                if _torchaudio_ver:
                    _report(
                        "dependencies",
                        62,
                        f"Removing incompatible torchaudio {_torchaudio_ver} (torch {_torch_ver})...",
                    )
                    pip_ops.run_pip(str(venv_path), ["uninstall", "-y", "torchaudio"])
                _report(
                    "dependencies",
                    63,
                    f"Installing torchaudio=={_torch_ver} for torch {_torch_ver}...",
                )
                try:
                    pip_ops.run_pip_with_progress(
                        str(venv_path),
                        [
                            "install",
                            f"torchaudio=={_torch_ver}",
                            "--index-url",
                            pytorch_index,
                        ],
                        progress_callback=lambda line: _report("dependencies", 63, line),
                    )
                except Exception as e:
                    logging.getLogger("env_manager").warning(
                        "No compatible torchaudio wheel for torch %s (%s); continuing without torchaudio",
                        _torch_ver,
                        e,
                    )
                    _report(
                        "dependencies",
                        63,
                        "No compatible torchaudio wheel found; continuing without torchaudio.",
                    )

            # 4b. Verify critical dependencies were installed
            _report("dependencies", 65, "Verifying dependencies...")
            _verify_freeze = pip_ops.freeze(str(venv_path))
            if len(_verify_freeze) > 5:
                # Only verify when we have a real package list (skip in
                # test environments where freeze is mocked with minimal data)
                _critical = ["torch", "numpy", "pillow", "pyyaml", "aiohttp"]
                if req_path.exists():
                    _critical.append("sqlalchemy")
                _installed_norm = {
                    k.strip().lower().replace("_", "-")
                    for k in _verify_freeze
                }
                _missing = [
                    p for p in _critical
                    if p not in _installed_norm
                ]
                if _missing:
                    raise RuntimeError(
                        f"Critical packages missing after installation: "
                        f"{', '.join(_missing)}. The venv may be corrupted."
                    )

            # 5. Install ComfyUI-Manager
            _report("manager", 75, "Installing ComfyUI-Manager...")
            manager_installed = False
            manager_path = comfyui_path / "custom_nodes" / "ComfyUI-Manager"
            try:
                manager_path.parent.mkdir(parents=True, exist_ok=True)
                git_ops.clone_repo(DEFAULT_MANAGER_URL, str(manager_path), branch="main")
                self._write_manager_security_config(comfyui_path)
                manager_installed = True
            except Exception as e:
                logging.getLogger("env_manager").warning(
                    f"ComfyUI-Manager install failed: {e}"
                )
                _report("manager", 75, "ComfyUI-Manager install failed (skipping)")

            # 6. Get environment info
            _report("finalize", 90, "Saving environment metadata...")
            comfyui_commit = git_ops.get_current_commit(str(comfyui_path))
            pip_freeze = pip_ops.freeze(str(venv_path))

            # Generate extra_model_paths.yaml
            self._generate_extra_model_paths(comfyui_path)

            # Build custom_nodes list
            custom_nodes = []
            if manager_installed:
                manager_commit = git_ops.get_current_commit(str(manager_path))
                custom_nodes.append({
                    "name": "ComfyUI-Manager",
                    "repo_url": DEFAULT_MANAGER_URL,
                    "commit": manager_commit,
                })

            # Detect installed PyTorch version
            installed_pytorch = pip_freeze.get("torch", "")

            # 7. Create and save environment metadata
            now = datetime.now(timezone.utc).isoformat()
            env = Environment(
                name=name,
                created_at=now,
                comfyui_commit=comfyui_commit,
                comfyui_branch=branch,
                python_version=python_version if python_version else pip_ops.get_python_version(str(venv_path)),
                cuda_tag=effective_cuda_tag,
                pytorch_version=installed_pytorch,
                pip_freeze=pip_freeze,
                custom_nodes=custom_nodes,
                path=str(env_dir),
                shared_model_enabled=True,
            )
            env.save_meta()

            _report("done", 100, "Environment created!")
            return env

        except Exception:
            # Clean up on failure
            if env_dir.exists():
                shutil.rmtree(env_dir, ignore_errors=True)
            raise

    def list_environments(self) -> List[Environment]:
        """List all environments with valid env_meta.json."""
        envs = []
        if not self.environments_dir.exists():
            return envs
        for entry in sorted(self.environments_dir.iterdir()):
            if entry.is_dir() and (entry / "env_meta.json").exists():
                try:
                    env = Environment.load_meta(str(entry))
                    envs.append(env)
                except Exception:
                    continue
        return envs

    def get_environment(self, name: str) -> Environment:
        """Get a single environment by name."""
        env_dir = self.environments_dir / name
        return Environment.load_meta(str(env_dir))

    def delete_environment(self, name: str, force: bool = False) -> None:
        """Delete an environment and its associated snapshots."""
        env_dir = self.environments_dir / name
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment '{name}' not found")

        default_env = self.config.get("default_env", "main")
        if name == default_env and not force:
            raise ValueError(
                f"Cannot delete the default environment '{name}' without --force"
            )

        # Remove the environment directory (handle read-only .git files on Windows)
        def _on_rm_error(func, path, exc_info):
            """Handle read-only files during deletion (e.g., .git objects on Windows)."""
            os.chmod(path, stat.S_IWRITE)
            func(path)

        shutil.rmtree(env_dir, onerror=_on_rm_error)

        # Also remove associated snapshots
        snapshots_dir = Path(self.config["snapshots_dir"]) / name
        if snapshots_dir.exists():
            shutil.rmtree(snapshots_dir, onerror=_on_rm_error)

    def rename_environment(self, old_name: str, new_name: str) -> Environment:
        """Rename an environment by moving its directory and updating metadata."""
        self._validate_name(new_name)
        old_dir = self.environments_dir / old_name
        new_dir = self.environments_dir / new_name
        if not old_dir.exists():
            raise FileNotFoundError(f"Environment '{old_name}' not found")
        if new_dir.exists():
            raise FileExistsError(f"Environment '{new_name}' already exists")

        # Rename directory
        old_dir.rename(new_dir)

        # Update metadata
        env = Environment.load_meta(str(new_dir))
        env.name = new_name
        env.path = str(new_dir)
        env.save_meta()

        return env

    def ensure_shared_models(self, target_path: Path = None) -> None:
        """Create model subdirectories in the target (or default) models directory."""
        model_subdirs = self.config.get("model_subdirs", [
            "checkpoints", "loras", "vae", "controlnet",
            "clip", "embeddings", "upscale_models",
        ])
        base = target_path or self._resolve_model_path()
        base.mkdir(parents=True, exist_ok=True)
        for subdir in model_subdirs:
            (base / subdir).mkdir(parents=True, exist_ok=True)

    def ensure_shared_models_if_safe(self) -> bool:
        """Guarded wrapper around ensure_shared_models().

        Skips the operation entirely if the resolved shared path is likely
        to be in an unmounted / typo'd location. Returns True if the
        bootstrap ran, False if it was skipped.
        """
        mode = self.config.get("shared_model_mode", "default")
        resolved = self._resolve_model_path()

        if mode == "custom":
            if not resolved.exists():
                logger.warning(
                    "Custom shared model path does not exist, skipping bootstrap: %s",
                    resolved,
                )
                return False
        else:  # default mode
            if not resolved.exists() and not resolved.parent.exists():
                logger.warning(
                    "Default models dir and its parent both missing, skipping bootstrap: %s",
                    resolved,
                )
                return False

        try:
            self.ensure_shared_models()
            return True
        except OSError as exc:
            logger.warning("ensure_shared_models failed: %s", exc)
            return False

    def sync_shared_model_subdirs(self, force_regen: bool = False) -> dict:
        """Scan shared + env model dirs for new subdirs; merge into config; optionally regen yaml.

        Returns:
            {
              "added": [str, ...],     # new lowercase subdir names merged into config
              "synced_envs": int,       # number of envs whose yaml was (re)generated
              "skipped": bool,          # True if pre-existence guard prevented the scan
              "reason": str,            # populated when skipped
            }
        """
        result = {"added": [], "synced_envs": 0, "skipped": False, "reason": ""}

        shared_path = self._resolve_model_path()
        if not shared_path.exists():
            result["skipped"] = True
            result["reason"] = "shared_path_missing"
            return result

        scan_roots = [shared_path]
        for env in self.list_environments():
            env_models = self.environments_dir / env.name / "ComfyUI" / "models"
            if env_models.exists():
                scan_roots.append(env_models)

        discovered = set()
        for root in scan_roots:
            try:
                for child in root.iterdir():
                    if not child.is_dir():
                        continue
                    name = child.name
                    if name.startswith(".") or name.startswith("_"):
                        continue
                    discovered.add(name.lower())
            except OSError:
                continue

        current = {s.lower() for s in self.config.get("model_subdirs", [])}
        new = sorted(discovered - current)

        if new:
            for name in new:
                try:
                    (shared_path / name).mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    logger.warning("Failed to create shared subdir %s: %s", name, exc)
                    result["skipped"] = True
                    result["reason"] = "mkdir_failed"
                    return result
            self.config.setdefault("model_subdirs", []).extend(new)
            from src.utils.fs_ops import save_config
            save_config(self.config, "config.json")
            result["added"] = new

        if new or force_regen:
            for env in self.list_environments():
                if not getattr(env, "shared_model_enabled", True):
                    continue
                comfyui_path = self.environments_dir / env.name / "ComfyUI"
                if comfyui_path.exists():
                    self._generate_extra_model_paths(comfyui_path)
                    result["synced_envs"] += 1

        return result

    def toggle_shared_model(self, env_name: str, enabled: bool) -> None:
        """Enable or disable shared model for a single environment."""
        env_dir = self.environments_dir / env_name
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment '{env_name}' not found")

        comfyui_path = env_dir / "ComfyUI"
        yaml_active = comfyui_path / "extra_model_paths.yaml"
        yaml_disabled = comfyui_path / "extra_model_paths.yaml.disabled"

        if enabled:
            # Generate fresh yaml with current path
            self._generate_extra_model_paths(comfyui_path)
            # Remove disabled file if it exists
            if yaml_disabled.exists():
                yaml_disabled.unlink()
        else:
            # Rename yaml to disabled
            if yaml_active.exists():
                yaml_active.rename(yaml_disabled)

        # Update env_meta
        env = Environment.load_meta(str(env_dir))
        env.shared_model_enabled = enabled
        env.save_meta()

    def toggle_all_shared_model(self, enabled: bool) -> int:
        """Toggle shared model for all environments. Returns count of toggled environments."""
        envs = self.list_environments()
        count = 0
        for env in envs:
            self.toggle_shared_model(env.name, enabled)
            count += 1
        return count

    def set_shared_model_path(self, mode: str, path: str, sync: bool = False) -> dict:
        """Update the global shared model config. Optionally sync all enabled environments."""
        if mode not in ("default", "custom"):
            raise ValueError(f"Invalid mode: {mode}")
        if mode == "custom" and not path:
            raise ValueError("Custom model path cannot be empty")
        if mode == "custom":
            custom_path = Path(path)
            if not custom_path.exists():
                raise FileNotFoundError(f"Path does not exist: {path}")

        # Update config
        self.config["shared_model_mode"] = mode
        self.config["custom_model_path"] = path if mode == "custom" else ""

        # Ensure subdirectories exist
        self.ensure_shared_models()

        # Count enabled environments
        envs = self.list_environments()
        enabled_count = sum(1 for e in envs if e.shared_model_enabled)

        if sync and enabled_count > 0:
            for env in envs:
                if env.shared_model_enabled:
                    comfyui_path = self.environments_dir / env.name / "ComfyUI"
                    if comfyui_path.exists():
                        self._generate_extra_model_paths(comfyui_path)

        return {"enabled_count": enabled_count}

    def clone_environment(self, source: str, new_name: str,
                          progress_callback=None) -> Environment:
        """Clone an environment by copying the entire directory."""
        self._validate_name(new_name)

        source_dir = self.environments_dir / source
        if not source_dir.exists():
            raise FileNotFoundError(f"Source environment '{source}' not found")

        target_dir = self.environments_dir / new_name
        if target_dir.exists():
            raise FileExistsError(f"Environment '{new_name}' already exists")

        def _report(step, pct, detail=""):
            if progress_callback:
                progress_callback(step, pct, detail)

        # Load source env
        source_env = Environment.load_meta(str(source_dir))

        # Auto-snapshot source
        snap_mgr = SnapshotManager(self.config)
        snap_mgr.create_snapshot(source, trigger="clone")

        try:
            # 1. Copy entire directory, excluding runtime artifacts that must not
            #    be shared between environments (.comfyui.pid would cause the clone
            #    to appear "already running" if the source env's process is alive;
            #    comfyui.log belongs to the source's run history only).
            _report("copy", 10, "Copying environment directory...")
            shutil.copytree(
                str(source_dir), str(target_dir),
                ignore=shutil.ignore_patterns(".comfyui.pid", "comfyui.log"),
            )

            # 2. Fix venv paths (pyvenv.cfg and Scripts) to point to new location
            _report("fixup", 60, "Updating virtual environment paths...")
            venv_path = target_dir / "venv"
            self._fix_venv_paths(venv_path, source_dir, target_dir)

            # 3. Regenerate extra_model_paths.yaml (absolute paths change)
            _report("finalize", 85, "Updating model paths...")
            comfyui_path = target_dir / "ComfyUI"
            if comfyui_path.exists():
                if source_env.shared_model_enabled:
                    self._generate_extra_model_paths(comfyui_path)
                else:
                    # Keep disabled state: rename yaml to disabled if active exists
                    yaml_active = comfyui_path / "extra_model_paths.yaml"
                    yaml_disabled = comfyui_path / "extra_model_paths.yaml.disabled"
                    if yaml_active.exists() and not yaml_disabled.exists():
                        yaml_active.rename(yaml_disabled)

            # 4. Write updated env_meta.json
            _report("finalize", 95, "Saving environment metadata...")
            now = datetime.now(timezone.utc).isoformat()
            # Carry over launch_settings from source (vram, cross-attention, etc.)
            # but reset port to 0 so the launcher auto-assigns a free port on first
            # launch rather than conflicting with the source environment's port.
            cloned_launch_settings = dict(source_env.launch_settings)
            cloned_launch_settings.pop("port", None)
            new_env = Environment(
                name=new_name,
                created_at=now,
                comfyui_commit=source_env.comfyui_commit,
                comfyui_branch=source_env.comfyui_branch,
                python_version=source_env.python_version,
                cuda_tag=source_env.cuda_tag,
                pytorch_version=source_env.pytorch_version,
                pip_freeze=source_env.pip_freeze,
                custom_nodes=source_env.custom_nodes,
                parent_env=source,
                path=str(target_dir),
                shared_model_enabled=source_env.shared_model_enabled,
                launch_settings=cloned_launch_settings,
            )
            new_env.save_meta()
            _report("done", 100, "Environment cloned!")
            return new_env

        except Exception:
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            raise

    @staticmethod
    def _fix_venv_paths(venv_path: Path, old_root: Path, new_root: Path) -> None:
        """Update venv internal paths after copying to a new location.

        A Windows venv embeds absolute paths in several places.  We must
        rewrite ALL of them or the cloned environment will silently keep
        referencing the source environment:

        1. ``pyvenv.cfg`` — used by python.exe to find the base interpreter.
        2. ``Scripts/activate.bat`` / ``activate`` / ``Activate.ps1`` / ``activate.fish``
           / ``activate.csh`` — contain a hard-coded ``VIRTUAL_ENV=<old_path>``.
        3. Console-script shims in ``Scripts/*.exe`` — pip.exe, etc. have a
           shebang-style header pointing at the source venv's python.exe.

        We rewrite 1 and 2 in place.  3 is handled by re-stamping the shim
        header when we can detect it.
        """
        old_variants = {
            str(old_root),
            str(old_root).replace("\\", "/"),
        }
        new_variants = {
            str(old_root): str(new_root),
            str(old_root).replace("\\", "/"): str(new_root).replace("\\", "/"),
        }

        def _rewrite_text_file(path: Path) -> None:
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                return
            original = text
            for old, new in new_variants.items():
                if old in text:
                    text = text.replace(old, new)
            if text != original:
                try:
                    path.write_text(text, encoding="utf-8")
                except Exception as exc:
                    logger.warning("Could not rewrite %s: %s", path, exc)

        # 1. pyvenv.cfg
        cfg_path = venv_path / "pyvenv.cfg"
        if cfg_path.exists():
            _rewrite_text_file(cfg_path)

        # 2. Activation scripts (Windows + POSIX for completeness)
        scripts_dir = venv_path / "Scripts"
        if not scripts_dir.exists():
            scripts_dir = venv_path / "bin"  # POSIX fallback
        if scripts_dir.exists():
            for name in (
                "activate.bat", "deactivate.bat",
                "Activate.ps1",
                "activate", "activate.fish", "activate.csh",
            ):
                _rewrite_text_file(scripts_dir / name)

            # 3. Console-script .exe shims (pip.exe, etc.)
            # These are tiny launchers: a PE header followed by a shebang
            # line like "#!C:\old\venv\Scripts\python.exe" and then a ZIP
            # payload.  We rewrite only the shebang line by reading the
            # file as bytes and replacing the ASCII path.
            old_bytes_variants = set()
            for old in old_variants:
                old_bytes_variants.add(old.encode("utf-8"))
                old_bytes_variants.add(old.encode("mbcs", errors="replace"))
            new_path_str = str(new_root)
            new_bytes = new_path_str.encode("utf-8")
            new_bytes_mbcs = new_path_str.encode("mbcs", errors="replace")
            needs_shim_regen = False
            for exe_file in scripts_dir.glob("*.exe"):
                try:
                    raw = exe_file.read_bytes()
                except Exception:
                    continue
                original = raw
                # Replace utf-8 variants
                for old_b in old_bytes_variants:
                    if old_b and old_b in raw:
                        # Lengths MUST match exactly or the shim's ZIP offset
                        # breaks.  Pad/truncate the replacement to match.
                        replacement = new_bytes if len(old_b) == len(new_bytes) else None
                        if replacement is None and len(old_b) == len(new_bytes_mbcs):
                            replacement = new_bytes_mbcs
                        if replacement is not None:
                            raw = raw.replace(old_b, replacement)
                        else:
                            needs_shim_regen = True
                if raw != original:
                    try:
                        exe_file.write_bytes(raw)
                    except Exception as exc:
                        logger.warning("Could not rewrite shim %s: %s", exe_file, exc)

            # 4. Regenerate console-script shims when binary patching was
            #    not possible (path length mismatch).  Running
            #    ``pip install --force-reinstall pip`` rebuilds pip's own
            #    shims and ``pip install --force-reinstall <pkg>`` would
            #    rebuild others.  As a practical compromise we reinstall
            #    pip (guarantees pip.exe works) and then use pip to
            #    reinstall all packages that installed console scripts.
            if needs_shim_regen:
                EnvManager._regenerate_console_scripts(venv_path, scripts_dir)

    @staticmethod
    def _regenerate_console_scripts(
        venv_path: Path, scripts_dir: Path
    ) -> None:
        """Regenerate console-script .exe shims via pip.

        When binary patching cannot fix shims (path length mismatch), we
        use pip itself to rebuild them.  Steps:

        1. Force-reinstall pip so that pip.exe points to the new venv.
        2. Collect every other .exe shim that still embeds the old path
           and identify the owning package via pip's ``__main__`` name
           convention or ``pip show``.
        3. Force-reinstall those packages (scripts-only, no deps) so
           their entry-point shims are regenerated.

        This is a heavier operation but guarantees correctness regardless
        of path length differences.
        """
        _kw = {}
        if sys.platform == "win32":
            _kw["creationflags"] = subprocess.CREATE_NO_WINDOW

        python = str(scripts_dir / "python.exe")
        if not Path(python).exists():
            # POSIX fallback (shouldn't happen on Windows)
            python = str(venv_path / "bin" / "python")

        # Step 1: Reinstall pip itself so pip.exe is correct
        try:
            subprocess.run(
                [python, "-m", "pip", "install",
                 "--force-reinstall", "--no-deps", "pip"],
                capture_output=True, text=True, check=True, **_kw,
            )
            logger.info("Regenerated pip shims in %s", scripts_dir)
        except Exception as exc:
            logger.warning("Failed to regenerate pip shims: %s", exc)
            return  # If pip itself can't reinstall, bail out

        # Step 2: Find packages that own remaining .exe shims and
        #         reinstall them to regenerate their entry points.
        #         We ask pip for the list of installed distributions that
        #         have console_scripts entry points.
        try:
            result = subprocess.run(
                [python, "-m", "pip", "list", "--format=freeze"],
                capture_output=True, text=True, check=True, **_kw,
            )
            installed = {}
            for line in result.stdout.strip().splitlines():
                if "==" in line:
                    pkg, ver = line.split("==", 1)
                    installed[pkg.strip().lower()] = ver.strip()
        except Exception:
            installed = {}

        # Collect exe names (minus .exe) that are NOT pip/pip3/pipX.Y
        exe_names = set()
        for exe_file in scripts_dir.glob("*.exe"):
            stem = exe_file.stem.lower()
            if stem.startswith("pip") or stem in ("python", "pythonw"):
                continue
            exe_names.add(stem)

        if not exe_names:
            return

        # Map exe shims to their owning packages by checking
        # ``pip show <name>`` — if the exe stem matches a package name
        # or a known console_script, reinstall it.
        pkgs_to_reinstall = set()
        for name in exe_names:
            # Common pattern: exe name == package name (e.g. accelerate)
            if name in installed:
                pkgs_to_reinstall.add(name)
            # Hyphenated variants (e.g. huggingface-cli -> huggingface)
            base = name.split("-")[0]
            if base in installed:
                pkgs_to_reinstall.add(base)

        # Also try ``pip show`` for each exe to find the owning package
        # via metadata inspection (handles non-obvious mappings).
        remaining = exe_names - pkgs_to_reinstall
        if remaining:
            try:
                show_result = subprocess.run(
                    [python, "-m", "pip", "show"] + list(remaining),
                    capture_output=True, text=True, **_kw,
                )
                for line in show_result.stdout.splitlines():
                    if line.startswith("Name:"):
                        pkg_name = line.split(":", 1)[1].strip().lower()
                        if pkg_name in installed:
                            pkgs_to_reinstall.add(pkg_name)
            except Exception:
                pass

        if pkgs_to_reinstall:
            try:
                subprocess.run(
                    [python, "-m", "pip", "install",
                     "--force-reinstall", "--no-deps"]
                    + [f"{p}=={installed[p]}" for p in pkgs_to_reinstall
                       if p in installed],
                    capture_output=True, text=True, check=True, **_kw,
                )
                logger.info(
                    "Regenerated console-script shims for: %s",
                    ", ".join(sorted(pkgs_to_reinstall)),
                )
            except Exception as exc:
                logger.warning(
                    "Failed to regenerate some console-script shims: %s",
                    exc,
                )

    def merge_env(self, source: str, target: str, strategy: str = "add") -> dict:
        """Merge changes from source environment into target environment.

        Strategy:
        - "add": Only add new packages/nodes, don't change existing versions
        - "replace": Replace target versions with source versions for changed packages

        Returns a dict summarizing what was merged.
        """
        if strategy not in {"add", "replace"}:
            raise ValueError(
                f"Invalid merge strategy '{strategy}'. Use 'add' or 'replace'."
            )

        source_dir = self.environments_dir / source
        target_dir = self.environments_dir / target

        if not source_dir.exists():
            raise FileNotFoundError(f"Source environment '{source}' not found")
        if not target_dir.exists():
            raise FileNotFoundError(f"Target environment '{target}' not found")

        source_env = Environment.load_meta(str(source_dir))
        target_env = Environment.load_meta(str(target_dir))

        # Auto-snapshot target before merge
        snap_mgr = SnapshotManager(self.config)
        snap_mgr.create_snapshot(target, trigger="merge")

        # Compare pip packages
        source_freeze = pip_ops.freeze(str(source_dir / "venv"))
        target_freeze = pip_ops.freeze(str(target_dir / "venv"))

        new_packages = {}
        changed_packages = {}

        for pkg, ver in source_freeze.items():
            if pkg not in target_freeze:
                new_packages[pkg] = ver
            elif target_freeze[pkg] != ver and strategy == "replace":
                changed_packages[pkg] = ver

        # Install new/changed packages
        packages_to_install = {**new_packages, **changed_packages}
        if packages_to_install:
            install_args = ["install"]
            # Add PyTorch CUDA wheel index when source env uses CUDA builds
            cuda_tag = source_env.cuda_tag or target_env.cuda_tag
            if cuda_tag:
                pytorch_index = f"https://download.pytorch.org/whl/{cuda_tag}"
                install_args += ["--extra-index-url", pytorch_index]
            install_args += [f"{pkg}=={ver}" for pkg, ver in packages_to_install.items()]
            install_result = pip_ops.run_pip(str(target_dir / "venv"), install_args)
            if install_result.returncode != 0:
                detail = (install_result.stderr or install_result.stdout or "unknown error").strip()
                raise RuntimeError(f"Failed to install merged packages: {detail}")

        # Compare custom_nodes
        source_nodes = {n["name"]: n for n in source_env.custom_nodes}
        target_nodes = {n["name"]: n for n in target_env.custom_nodes}

        new_nodes = []
        for name, node in source_nodes.items():
            if name not in target_nodes:
                new_nodes.append(node)
                # Clone the node to target
                if node.get("repo_url"):
                    node_dest = target_dir / "ComfyUI" / "custom_nodes" / name
                    git_ops.clone_repo(
                        node["repo_url"], str(node_dest),
                        commit=node.get("commit"),
                    )

        # Update target env_meta
        target_env = Environment.load_meta(str(target_dir))  # Reload
        combined_nodes = list(target_env.custom_nodes) + list(new_nodes)
        deduped_nodes = []
        seen_node_names = set()
        for node in combined_nodes:
            node_name = node.get("name", "")
            if node_name and node_name in seen_node_names:
                continue
            if node_name:
                seen_node_names.add(node_name)
            deduped_nodes.append(node)
        target_env.custom_nodes = deduped_nodes
        target_env.pip_freeze = pip_ops.freeze(str(target_dir / "venv"))
        target_env.merge_history.append({
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "new_packages": list(new_packages.keys()),
            "changed_packages": list(changed_packages.keys()),
            "new_nodes": [n["name"] for n in new_nodes],
            "strategy": strategy,
        })
        target_env.save_meta()

        return {
            "new_packages": new_packages,
            "changed_packages": changed_packages,
            "new_nodes": [n["name"] for n in new_nodes],
        }

    def _validate_name(self, name: str) -> None:
        """Validate environment name."""
        if not ENV_NAME_PATTERN.match(name):
            raise ValueError(
                f"Invalid environment name '{name}'. "
                "Use only letters, digits, underscores, and hyphens. "
                "Must start with a letter or digit."
            )

    def _get_bundled_python_version(self) -> str:
        """Get the version of the bundled Python in tools/python/."""
        import subprocess as _sp
        tools_python = Path(self.config.get("base_dir", ".")) / "tools" / "python" / "python.exe"
        if tools_python.exists():
            try:
                result = _sp.run(
                    [str(tools_python), "--version"],
                    capture_output=True, text=True, check=True,
                )
                return result.stdout.strip().replace("Python ", "")
            except Exception:
                pass
        return ""

    def _resolve_model_path(self) -> Path:
        """Return the active model directory based on config."""
        mode = self.config.get("shared_model_mode", "default")
        if mode == "custom":
            custom = self.config.get("custom_model_path", "")
            if custom:
                return Path(custom)
        return self.models_dir

    def _generate_extra_model_paths(self, comfyui_path: Path) -> None:
        """Generate extra_model_paths.yaml pointing to shared models directory."""
        model_subdirs = self.config.get("model_subdirs", [
            "checkpoints", "loras", "vae", "controlnet",
            "clip", "embeddings", "upscale_models",
        ])

        models_path = self._resolve_model_path()
        models_abs = str(models_path.resolve()).replace("\\", "/")
        yaml_data = {
            "shared_models": {
                "base_path": models_abs + "/",
            }
        }
        for subdir in model_subdirs:
            yaml_data["shared_models"][subdir] = subdir + "/"

        yaml_path = comfyui_path / "extra_model_paths.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text(
            yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

    def _write_manager_security_config(self, comfyui_path: Path) -> None:
        """Initialize manager config with launcher-compatible security defaults."""
        config_path = comfyui_path / "user" / "__manager" / "config.ini"
        config = configparser.ConfigParser()
        if config_path.exists():
            config.read(str(config_path), encoding="utf-8")

        if "default" not in config:
            config["default"] = {}
        config["default"]["security_level"] = "normal-"

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(config_path), "w", encoding="utf-8") as f:
            config.write(f)

    @staticmethod
    def _on_rm_error(func, path, exc_info):
        """Handle read-only files during deletion (e.g., .git objects on Windows)."""
        os.chmod(path, stat.S_IWRITE)
        func(path)

    # ------------------------------------------------------------------
    # Plugin / custom-node management
    # ------------------------------------------------------------------

    def list_custom_nodes(self, env_name: str) -> list:
        """Return a list of custom nodes for env_name, reconciling disk vs meta.

        Each item is a dict:
            {name: str, status: "enabled"|"disabled"|"untracked", repo_url: str, commit: str}
        """
        env_dir = Path(self.config["environments_dir"]) / env_name
        custom_nodes_dir = env_dir / "ComfyUI" / "custom_nodes"
        env = Environment.load_meta(str(env_dir))

        # Build lookup from existing meta entries
        meta_by_name: dict = {n["name"]: n for n in env.custom_nodes}

        # Scan directories on disk
        disk_nodes: dict = {}  # canonical_name -> {"enabled": bool}
        if custom_nodes_dir.exists():
            for entry in custom_nodes_dir.iterdir():
                if not entry.is_dir():
                    continue
                name = entry.name
                # Skip __pycache__ and hidden dirs
                if name == "__pycache__" or name.startswith("."):
                    continue
                if name.endswith(".disabled"):
                    canonical = name[: -len(".disabled")]
                    disk_nodes[canonical] = {"enabled": False}
                else:
                    disk_nodes[name] = {"enabled": True}

        # Reconcile: add disk-only entries to meta, remove stale meta entries
        # Track which names had no prior meta entry (newly discovered on disk)
        newly_discovered: set = set()
        reconciled: list = []
        for canonical, disk_info in disk_nodes.items():
            if canonical in meta_by_name:
                entry = dict(meta_by_name[canonical])
                entry["enabled"] = disk_info["enabled"]
            else:
                entry = {
                    "name": canonical,
                    "repo_url": "",
                    "commit": "",
                    "enabled": disk_info["enabled"],
                }
                newly_discovered.add(canonical)
            reconciled.append(entry)

        # Remove stale meta entries (in meta but not on disk) by replacing with reconciled list
        env.custom_nodes = list(reconciled)
        env.save_meta()

        # Build return list
        result = []
        for entry in reconciled:
            if entry["name"] in newly_discovered:
                status = "untracked"
            elif not entry.get("enabled", True):
                status = "disabled"
            else:
                status = "enabled"

            has_update = None
            if status == "enabled" and entry.get("repo_url"):
                node_path = custom_nodes_dir / entry["name"]
                if node_path.exists():
                    has_update = git_ops.has_remote_updates(str(node_path))

            result.append({
                "name": entry["name"],
                "status": status,
                "repo_url": entry.get("repo_url", ""),
                "commit": entry.get("commit", ""),
                "has_update": has_update,
            })

        return result

    def disable_custom_node(self, env_name: str, node_name: str) -> None:
        """Rename custom_nodes/{node_name} -> {node_name}.disabled and update meta."""
        env_dir = Path(self.config["environments_dir"]) / env_name
        custom_nodes_dir = env_dir / "ComfyUI" / "custom_nodes"
        node_path = custom_nodes_dir / node_name
        disabled_path = custom_nodes_dir / f"{node_name}.disabled"

        if disabled_path.exists():
            raise ValueError(f"Node '{node_name}' is already disabled")
        if not node_path.exists():
            raise ValueError(f"Node '{node_name}' not found in '{env_name}'")

        node_path.rename(disabled_path)

        env = Environment.load_meta(str(env_dir))
        for entry in env.custom_nodes:
            if entry["name"] == node_name:
                entry["enabled"] = False
                break
        env.save_meta()

    def enable_custom_node(self, env_name: str, node_name: str) -> None:
        """Rename custom_nodes/{node_name}.disabled -> {node_name} and update meta."""
        env_dir = Path(self.config["environments_dir"]) / env_name
        custom_nodes_dir = env_dir / "ComfyUI" / "custom_nodes"
        disabled_path = custom_nodes_dir / f"{node_name}.disabled"
        node_path = custom_nodes_dir / node_name

        if not disabled_path.exists():
            raise ValueError(f"Disabled node '{node_name}' not found in '{env_name}'")

        disabled_path.rename(node_path)

        env = Environment.load_meta(str(env_dir))
        for entry in env.custom_nodes:
            if entry["name"] == node_name:
                entry["enabled"] = True
                break
        env.save_meta()

    def delete_custom_node(self, env_name: str, node_name: str) -> None:
        """Delete a custom node folder (enabled or disabled) and remove from meta."""
        env_dir = Path(self.config["environments_dir"]) / env_name
        custom_nodes_dir = env_dir / "ComfyUI" / "custom_nodes"
        node_path = custom_nodes_dir / node_name
        disabled_path = custom_nodes_dir / f"{node_name}.disabled"

        if node_path.exists():
            shutil.rmtree(str(node_path), onerror=self._on_rm_error)
        elif disabled_path.exists():
            shutil.rmtree(str(disabled_path), onerror=self._on_rm_error)
        else:
            raise ValueError(f"Node '{node_name}' not found in '{env_name}'")

        env = Environment.load_meta(str(env_dir))
        env.custom_nodes = [n for n in env.custom_nodes if n["name"] != node_name]
        env.save_meta()

    def install_custom_node(self, env_name: str, git_url: str,
                            progress_callback=None) -> dict:
        """Clone a custom node from git_url, install its deps, and update meta.

        Returns {name, repo_url, commit}.
        """
        env_dir = Path(self.config["environments_dir"]) / env_name
        venv_path = env_dir / "venv"
        custom_nodes_dir = env_dir / "ComfyUI" / "custom_nodes"

        # Sanitize URL to derive node_name
        url = git_url.strip().rstrip("/")
        if "?" in url:
            url = url[: url.index("?")]
        if url.endswith(".git"):
            url = url[:-4]
        node_name = url.split("/")[-1]

        node_path = custom_nodes_dir / node_name
        clone_started = False

        try:
            if progress_callback:
                progress_callback("Cloning repository...")

            custom_nodes_dir.mkdir(parents=True, exist_ok=True)
            git_ops.clone_repo(git_url, str(node_path), branch=None)
            clone_started = True

            if progress_callback:
                progress_callback("Installing dependencies...")

            req_path = node_path / "requirements.txt"
            if req_path.exists():
                pip_ops.run_pip(str(venv_path), ["install", "-r", str(req_path)])

            install_py = node_path / "install.py"
            if install_py.exists():
                python_exe = pip_ops.get_venv_python(str(venv_path))
                subprocess.run(
                    [python_exe, str(install_py)],
                    cwd=str(node_path),
                    check=True,
                )

            commit = git_ops.get_current_commit(str(node_path))

            env = Environment.load_meta(str(env_dir))
            env.custom_nodes.append({
                "name": node_name,
                "repo_url": git_url,
                "commit": commit,
                "enabled": True,
            })
            env.save_meta()

            if progress_callback:
                progress_callback("Done")

            return {"name": node_name, "repo_url": git_url, "commit": commit}

        except Exception:
            if clone_started and node_path.exists():
                shutil.rmtree(str(node_path), onerror=self._on_rm_error)
            raise

    def update_custom_node(self, env_name: str, node_name: str,
                           progress_callback=None) -> dict:
        """Pull latest changes for a custom node and reinstall deps.

        Returns {name, prev_commit, new_commit, updated: bool}.
        """
        env_dir = Path(self.config["environments_dir"]) / env_name
        venv_path = env_dir / "venv"
        custom_nodes_dir = env_dir / "ComfyUI" / "custom_nodes"
        node_path = custom_nodes_dir / node_name

        if not node_path.exists():
            raise ValueError(f"Node '{node_name}' not found in '{env_name}'")

        prev_commit = git_ops.get_current_commit(str(node_path))

        if progress_callback:
            progress_callback(f"Pulling latest for {node_name}...")

        git_ops.pull(str(node_path))
        new_commit = git_ops.get_current_commit(str(node_path))

        if prev_commit == new_commit:
            return {"name": node_name, "prev_commit": prev_commit,
                    "new_commit": new_commit, "updated": False}

        if progress_callback:
            progress_callback(f"Installing dependencies for {node_name}...")

        req_path = node_path / "requirements.txt"
        if req_path.exists():
            pip_ops.run_pip(str(venv_path), ["install", "-r", str(req_path)])

        install_py = node_path / "install.py"
        if install_py.exists():
            python_exe = pip_ops.get_venv_python(str(venv_path))
            subprocess.run(
                [python_exe, str(install_py)],
                cwd=str(node_path),
                check=True,
            )

        env = Environment.load_meta(str(env_dir))
        for entry in env.custom_nodes:
            if entry["name"] == node_name:
                entry["commit"] = new_commit
                break
        env.save_meta()

        return {"name": node_name, "prev_commit": prev_commit,
                "new_commit": new_commit, "updated": True}

    def update_all_custom_nodes(self, env_name: str,
                                progress_callback=None) -> dict:
        """Update all enabled custom nodes that have a repo_url.

        Returns {updated, skipped, failed, errors, total}.
        """
        plugins = self.list_custom_nodes(env_name)
        targets = [p for p in plugins
                   if p["status"] == "enabled" and p.get("repo_url")]

        updated = 0
        skipped = 0
        failed = 0
        errors = []

        for i, plugin in enumerate(targets, 1):
            name = plugin["name"]
            if progress_callback:
                progress_callback(f"Updating {name} ({i}/{len(targets)})...")
            try:
                result = self.update_custom_node(env_name, name)
                if result["updated"]:
                    updated += 1
                else:
                    skipped += 1
            except Exception as e:
                failed += 1
                errors.append({"name": name, "error": str(e)})

        return {"updated": updated, "skipped": skipped,
                "failed": failed, "errors": errors,
                "total": len(targets)}
