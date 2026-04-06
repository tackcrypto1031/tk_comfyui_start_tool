"""Environment manager - create, list, delete, clone environments."""
import logging
import os
import re
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import yaml

from src.models.environment import Environment
from src.utils import git_ops, pip_ops
from src.core.snapshot_manager import SnapshotManager


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

    def create_environment(self, name: str, branch: str = "master",
                           commit: Optional[str] = None,
                           python_version: str = "",
                           cuda_tag: str = "",
                           progress_callback=None) -> Environment:
        """Create a new ComfyUI environment with venv, cloned repo, and metadata."""
        self._validate_name(name)

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
            _report("pytorch", 35, "Installing PyTorch (CUDA)...")
            if cuda_tag:
                pytorch_index = f"https://download.pytorch.org/whl/{cuda_tag}"
            else:
                pytorch_index = self.config.get("pytorch_index_url", "https://download.pytorch.org/whl/cu124")
            effective_cuda_tag = cuda_tag or pytorch_index.rstrip("/").split("/")[-1]
            pip_ops.run_pip_with_progress(str(venv_path), [
                "install", "torch", "torchvision", "torchaudio",
                "--index-url", pytorch_index,
            ], progress_callback=lambda line: _report("pytorch", 35, line))

            # 4. Install ComfyUI dependencies
            _report("dependencies", 55, "Installing ComfyUI dependencies...")
            req_path = comfyui_path / "requirements.txt"
            if req_path.exists():
                pip_ops.run_pip_with_progress(str(venv_path), [
                    "install", "-r", str(req_path),
                ], progress_callback=lambda line: _report("dependencies", 55, line))

            # 5. Install ComfyUI-Manager
            _report("manager", 75, "Installing ComfyUI-Manager...")
            manager_installed = False
            manager_path = comfyui_path / "custom_nodes" / "ComfyUI-Manager"
            try:
                manager_path.parent.mkdir(parents=True, exist_ok=True)
                git_ops.clone_repo(DEFAULT_MANAGER_URL, str(manager_path), branch="main")
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

    def ensure_shared_models(self) -> None:
        """Create shared models directory with configured subdirectories."""
        model_subdirs = self.config.get("model_subdirs", [
            "checkpoints", "loras", "vae", "controlnet",
            "clip", "embeddings", "upscale_models",
        ])
        for subdir in model_subdirs:
            (self.models_dir / subdir).mkdir(parents=True, exist_ok=True)

    def clone_environment(self, source: str, new_name: str, as_sandbox: bool = True,
                          progress_callback=None) -> Environment:
        """Clone an environment using new venv + pip install freeze.txt strategy."""
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

        target_dir.mkdir(parents=True)
        try:
            # 1. Create new venv
            _report("venv", 5, "Creating virtual environment...")
            venv_path = target_dir / "venv"
            pip_ops.create_venv(str(venv_path))

            # 2. Export source freeze and install
            _report("dependencies", 15, "Installing packages from freeze...")
            source_freeze = pip_ops.freeze(str(source_dir / "venv"))
            if source_freeze:
                freeze_file = target_dir / "freeze.txt"
                lines = [f"{pkg}=={ver}" for pkg, ver in source_freeze.items()]
                freeze_file.write_text("\n".join(lines), encoding="utf-8")
                pip_ops.run_pip_with_progress(
                    str(venv_path), ["install", "-r", str(freeze_file)],
                    progress_callback=lambda line: _report("dependencies", 15, line),
                )

            # 3. Clone ComfyUI to same commit
            _report("clone", 55, "Cloning ComfyUI repository...")
            comfyui_path = target_dir / "ComfyUI"
            git_ops.clone_repo(
                self.comfyui_url, str(comfyui_path),
                branch=source_env.comfyui_branch,
                commit=source_env.comfyui_commit,
                progress_callback=lambda pct, msg: _report(
                    "clone", 55 + int(pct * 0.2), msg or "Cloning ComfyUI repository..."
                ),
            )

            # 4. Clone custom_nodes to same commits
            _report("manager", 75, "Cloning custom nodes...")
            for node in source_env.custom_nodes:
                if node.get("repo_url"):
                    node_dest = comfyui_path / "custom_nodes" / node["name"]
                    git_ops.clone_repo(
                        node["repo_url"], str(node_dest),
                        commit=node.get("commit"),
                    )

            # 5. Generate extra_model_paths.yaml
            _report("finalize", 90, "Saving environment metadata...")
            self._generate_extra_model_paths(comfyui_path)

            # 6. Write env_meta.json
            now = datetime.now(timezone.utc).isoformat()
            new_env = Environment(
                name=new_name,
                created_at=now,
                comfyui_commit=source_env.comfyui_commit,
                comfyui_branch=source_env.comfyui_branch,
                python_version=pip_ops.get_python_version(str(venv_path)),
                pip_freeze=pip_ops.freeze(str(venv_path)),
                custom_nodes=source_env.custom_nodes,
                is_sandbox=as_sandbox,
                parent_env=source,
                path=str(target_dir),
            )
            new_env.save_meta()
            _report("done", 100, "Environment cloned!")
            return new_env

        except Exception:
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            raise

    def merge_env(self, source: str, target: str, strategy: str = "add") -> dict:
        """Merge changes from source environment into target environment.

        Strategy:
        - "add": Only add new packages/nodes, don't change existing versions
        - "replace": Replace target versions with source versions for changed packages

        Returns a dict summarizing what was merged.
        """
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
            install_args = [f"{pkg}=={ver}" for pkg, ver in packages_to_install.items()]
            pip_ops.run_pip(str(target_dir / "venv"), ["install"] + install_args)

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
        target_env.custom_nodes.extend(new_nodes)
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

    def _generate_extra_model_paths(self, comfyui_path: Path) -> None:
        """Generate extra_model_paths.yaml pointing to shared models directory."""
        model_subdirs = self.config.get("model_subdirs", [
            "checkpoints", "loras", "vae", "controlnet",
            "clip", "embeddings", "upscale_models",
        ])

        models_abs = str(self.models_dir.resolve()).replace("\\", "/")
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
