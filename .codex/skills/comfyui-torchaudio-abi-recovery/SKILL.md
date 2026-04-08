---
name: comfyui-torchaudio-abi-recovery
description: Diagnose and fix ComfyUI startup failures caused by torch/torchaudio binary ABI mismatch on Windows. Use when errors mention `python.exe 無法找到輸入點`, `lib_torchaudio.pyd`, `WinError 127`, or ComfyUI logs show `torchaudio missing`.
---

# ComfyUI Torchaudio ABI Recovery

Use this workflow when an environment is created successfully but ComfyUI fails during startup because `torchaudio` cannot be loaded.

## 1) Confirm the symptom

Run in target venv:

```powershell
<venv>\Scripts\python.exe -c "import torch; print('torch', torch.__version__); import torchaudio; print('torchaudio', torchaudio.__version__)"
```

If this throws `WinError 127` / `_torchaudio.pyd` load error, continue.

## 2) Collect version evidence

```powershell
<venv>\Scripts\python.exe -m pip show torch torchvision torchaudio
```

Normalize versions by removing local suffixes (e.g. `2.9.1+cu130` -> `2.9.1`).

If `torch` base version differs from `torchaudio` base version, treat as ABI mismatch.

## 3) Fix the environment safely

1. Ensure no process is using the venv (ComfyUI, Python REPL, IDE background task).
2. Remove incompatible `torchaudio`.
3. Install `torchaudio==<torch_base_version>` from the same CUDA index.
4. If matching wheel does not exist, keep environment without `torchaudio` instead of leaving broken binaries.

Example:

```powershell
<venv>\Scripts\python.exe -m pip uninstall -y torchaudio
<venv>\Scripts\python.exe -m pip install torchaudio==2.9.1 --index-url https://download.pytorch.org/whl/cu130
```

## 4) Verify recovery

```powershell
<venv>\Scripts\python.exe -c "import torch; import torchaudio; print(torch.__version__, torchaudio.__version__)"
```

Success criteria:

- Import works without OSError.
- `torch` and `torchaudio` base versions match.
- ComfyUI startup log no longer prints `torchaudio missing` due to load failure.

## 5) Prevent regression in launcher code

When implementing environment creation/reinstall logic:

1. Do not rely on pip to infer `torchaudio` compatibility.
2. After install, read `pip freeze`.
3. Reconcile `torchaudio` to match installed `torch` base version.
4. Fail soft: if matching wheel is unavailable, continue without `torchaudio` and log warning.
5. Add regression tests for mismatch reconciliation.
