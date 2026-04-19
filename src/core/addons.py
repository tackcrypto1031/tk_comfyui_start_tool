"""Curated add-on registry for the recommended creation flow."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class Addon:
    id: str
    label: str
    description: str
    install_method: Literal["pip_package", "git_clone"]
    pip_package: Optional[str] = None
    repo: Optional[str] = None
    post_install_cmd: Optional[list] = None
    requires_cuda: bool = False
    requires_compile: bool = False
    risk_note: Optional[str] = None


ADDONS: list[Addon] = [
    Addon(
        id="sage-attention",
        label="SageAttention v2",
        description="Attention acceleration — larger batch, lower VRAM",
        install_method="git_clone",
        repo="https://github.com/thu-ml/SageAttention.git",
        post_install_cmd=["pip", "install", "-e", "."],
        requires_cuda=True,
        requires_compile=True,
        risk_note="Requires CUDA toolkit (nvcc); first install compiles",
    ),
    Addon(
        id="flash-attention",
        label="FlashAttention",
        description="Fast attention implementation",
        install_method="git_clone",
        repo="https://github.com/Dao-AILab/flash-attention.git",
        post_install_cmd=["pip", "install", "-e", ".", "--no-build-isolation"],
        requires_cuda=True,
        requires_compile=True,
    ),
    Addon(
        id="insightface",
        label="InsightFace",
        description="Face nodes (IPAdapter FaceID, ReActor)",
        install_method="pip_package",
        pip_package="insightface",
        requires_cuda=False,
        requires_compile=False,
    ),
    Addon(
        id="nunchaku",
        label="Nunchaku",
        description="Quantized inference (4-bit FLUX)",
        install_method="git_clone",
        repo="https://github.com/mit-han-lab/nunchaku.git",
        post_install_cmd=["pip", "install", "-e", "."],
        requires_cuda=True,
        requires_compile=True,
    ),
    Addon(
        id="trellis2",
        label="Trellis 2.0",
        description="3D generation nodes",
        install_method="git_clone",
        repo="https://github.com/microsoft/TRELLIS.git",
        post_install_cmd=["pip", "install", "-r", "requirements.txt"],
        requires_cuda=True,
        requires_compile=True,
    ),
]


def find_addon(addon_id: str) -> Optional[Addon]:
    for a in ADDONS:
        if a.id == addon_id:
            return a
    return None
