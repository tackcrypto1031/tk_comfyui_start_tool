"""Snapshot manager - create, list, restore, delete snapshots."""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from src.models.environment import Environment
from src.models.snapshot import Snapshot
from src.utils import git_ops, pip_ops


class SnapshotManager:
    """Manages environment snapshots for safe rollback."""

    def __init__(self, config: dict):
        self.config = config
        self.environments_dir = Path(config["environments_dir"])
        self.snapshots_dir = Path(config["snapshots_dir"])

    def create_snapshot(self, env_name: str, trigger: str = "manual") -> Snapshot:
        """Create a snapshot of an environment's current state."""
        env_dir = self.environments_dir / env_name
        if not env_dir.exists() or not (env_dir / "env_meta.json").exists():
            raise FileNotFoundError(f"Environment '{env_name}' not found")

        env = Environment.load_meta(str(env_dir))

        # Generate snapshot ID
        now = datetime.now(timezone.utc)
        snapshot_id = f"snap-{now.strftime('%Y%m%d-%H%M%S-%f')}"

        # Create snapshot directory
        snap_dir = self.snapshots_dir / env_name / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)

        # 1. Export pip freeze
        venv_path = env_dir / "venv"
        freeze_data = pip_ops.freeze(str(venv_path))
        freeze_path = snap_dir / "freeze.txt"
        freeze_lines = [f"{pkg}=={ver}" for pkg, ver in sorted(freeze_data.items())]
        freeze_path.write_text("\n".join(freeze_lines), encoding="utf-8")

        # 2. Get ComfyUI commit
        comfyui_path = env_dir / "ComfyUI"
        comfyui_commit = git_ops.get_current_commit(str(comfyui_path))

        # 2b. Get Python version from venv
        try:
            python_version = pip_ops.get_python_version(str(venv_path))
        except Exception:
            python_version = ""

        # 2c. Get CUDA version from PyTorch
        try:
            python_exe = pip_ops.get_venv_python(str(venv_path))
            result = subprocess.run(
                [python_exe, "-c", "import torch; print(torch.version.cuda or '')"],
                capture_output=True, text=True, timeout=10,
                **pip_ops._SUBPROCESS_KWARGS,
            )
            cuda_version = result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            cuda_version = ""

        # 2d. Get cuda_tag from env meta
        cuda_tag = getattr(env, "cuda_tag", "") or ""

        # 3. Record custom_nodes state
        custom_nodes_state = []
        for node in env.custom_nodes:
            custom_nodes_state.append({
                "name": node.get("name", ""),
                "commit": node.get("commit", ""),
                "repo_url": node.get("repo_url", ""),
            })

        # 4. Backup config files
        configs_dir = snap_dir / "configs"
        configs_dir.mkdir(exist_ok=True)
        extra_yaml = comfyui_path / "extra_model_paths.yaml"
        if extra_yaml.exists():
            shutil.copy2(str(extra_yaml), str(configs_dir / "extra_model_paths.yaml"))

        # 5. Create snapshot object and save metadata
        snap = Snapshot(
            id=snapshot_id,
            env_name=env_name,
            created_at=now.isoformat(),
            trigger=trigger,
            comfyui_commit=comfyui_commit,
            python_version=python_version,
            cuda_version=cuda_version,
            cuda_tag=cuda_tag,
            custom_nodes_state=custom_nodes_state,
            pip_freeze_path=str(freeze_path),
            config_backup_path=str(configs_dir),
        )

        meta_path = snap_dir / "snapshot_meta.json"
        meta_path.write_text(
            json.dumps(snap.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 6. Update env_meta.json
        if snapshot_id not in env.snapshots:
            env.snapshots.append(snapshot_id)
            env.save_meta()

        return snap

    def list_snapshots(self, env_name: str) -> List[Snapshot]:
        """List all snapshots for an environment."""
        snap_env_dir = self.snapshots_dir / env_name
        if not snap_env_dir.exists():
            return []

        snapshots = []
        for entry in sorted(snap_env_dir.iterdir()):
            meta_path = entry / "snapshot_meta.json"
            if entry.is_dir() and meta_path.exists():
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                snapshots.append(Snapshot.from_dict(data))
        return snapshots

    def restore_snapshot(self, env_name: str, snapshot_id: str,
                         progress_callback=None) -> None:
        """Restore an environment from a snapshot.

        Restores: ComfyUI commit, custom nodes, CUDA/PyTorch version,
        pip packages, and config files.
        """
        snap_dir = self.snapshots_dir / env_name / snapshot_id
        meta_path = snap_dir / "snapshot_meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Snapshot '{snapshot_id}' not found for '{env_name}'")

        data = json.loads(meta_path.read_text(encoding="utf-8"))
        snap = Snapshot.from_dict(data)

        env_dir = self.environments_dir / env_name
        comfyui_path = env_dir / "ComfyUI"
        custom_nodes_dir = comfyui_path / "custom_nodes"
        venv_path = env_dir / "venv"

        def _progress(step: str, pct: int, msg: str) -> None:
            if progress_callback:
                progress_callback(step, pct, msg)

        # 1. Checkout ComfyUI to snapshot commit
        _progress("comfyui", 10, "Restoring ComfyUI version...")
        git_ops.checkout(str(comfyui_path), snap.comfyui_commit)

        # 2. Restore custom nodes
        _progress("nodes", 20, "Restoring custom nodes...")
        snap_nodes = {n["name"]: n for n in snap.custom_nodes_state}

        # 2a. Identify current custom nodes on disk
        current_nodes = set()
        if custom_nodes_dir.exists():
            for entry in custom_nodes_dir.iterdir():
                if entry.is_dir() and entry.name != "__pycache__":
                    current_nodes.add(entry.name)

        # 2b. Remove nodes that are not in the snapshot
        for node_name in current_nodes - set(snap_nodes.keys()):
            node_path = custom_nodes_dir / node_name
            shutil.rmtree(node_path, ignore_errors=True)

        # 2c. Clone missing nodes and checkout correct commits
        for node_name, node_info in snap_nodes.items():
            node_path = custom_nodes_dir / node_name
            repo_url = node_info.get("repo_url", "")
            target_commit = node_info.get("commit", "")

            if not repo_url:
                continue

            if not node_path.exists():
                # Clone the missing node
                git_ops.clone_repo(repo_url, str(node_path), commit=target_commit)
            elif target_commit:
                # Node exists — checkout the snapshot commit
                try:
                    git_ops.checkout(str(node_path), target_commit)
                except Exception:
                    # If commit not found locally, re-clone
                    shutil.rmtree(node_path, ignore_errors=True)
                    git_ops.clone_repo(repo_url, str(node_path), commit=target_commit)

        # 3. Restore CUDA/PyTorch if cuda_tag changed
        snap_cuda_tag = getattr(snap, "cuda_tag", "") or ""
        if snap_cuda_tag:
            env = Environment.load_meta(str(env_dir))
            current_cuda_tag = getattr(env, "cuda_tag", "") or ""
            if current_cuda_tag != snap_cuda_tag:
                _progress("pytorch", 40, f"Reinstalling PyTorch ({snap_cuda_tag})...")
                pip_ops.run_pip(str(venv_path), [
                    "uninstall", "torch", "torchvision", "torchaudio", "-y",
                ])
                pip_ops.run_pip(str(venv_path), [
                    "install", "torch", "torchvision", "torchaudio",
                    "--index-url", f"https://download.pytorch.org/whl/{snap_cuda_tag}",
                ])

        # 4. Reinstall remaining packages from freeze.txt
        _progress("packages", 60, "Restoring pip packages...")
        freeze_path = snap_dir / "freeze.txt"
        if freeze_path.exists():
            pip_ops.run_pip(str(venv_path), [
                "install", "--force-reinstall", "-r", str(freeze_path),
            ])

        # 5. Restore config backups
        _progress("configs", 80, "Restoring config files...")
        configs_dir = snap_dir / "configs"
        if configs_dir.exists():
            for cfg_file in configs_dir.iterdir():
                dest = comfyui_path / cfg_file.name
                shutil.copy2(str(cfg_file), str(dest))

        # 6. Update env_meta.json to match snapshot state
        _progress("metadata", 90, "Updating environment metadata...")
        env = Environment.load_meta(str(env_dir))
        env.comfyui_commit = snap.comfyui_commit
        env.custom_nodes = snap.custom_nodes_state
        if snap_cuda_tag:
            env.cuda_tag = snap_cuda_tag
        env.pip_freeze = pip_ops.freeze(str(venv_path))
        env.save_meta()

        _progress("done", 100, "Snapshot restored!")

    def delete_snapshot(self, env_name: str, snapshot_id: str) -> None:
        """Delete a single snapshot."""
        snap_dir = self.snapshots_dir / env_name / snapshot_id
        if not snap_dir.exists():
            raise FileNotFoundError(f"Snapshot '{snapshot_id}' not found")
        shutil.rmtree(snap_dir)
