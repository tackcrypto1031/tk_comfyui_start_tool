# Python + CUDA Version Switching Design

Date: 2026-04-06

## Summary

Allow users to select Python and CUDA/PyTorch versions per ComfyUI environment. Python version is chosen at environment creation time (immutable after), CUDA/PyTorch can be reinstalled later. Version lists come from built-in defaults with manual online refresh.

## Key Decisions

| Decision | Choice |
|----------|--------|
| Isolation level | Default unified Python, advanced option to pick version (Option C) |
| Version list source | Auto-fetch from Python/PyTorch official + manual refresh button |
| Version change timing | Python fixed at creation, CUDA changeable after (Option B) |
| Post-reinstall handling | Reinstall torch trio + auto conflict analysis (Option B) |
| UI location | Advanced options collapsible section in create dialog (Option A) |
| Default values | Auto-detect GPU via nvidia-smi to recommend CUDA; Python defaults to tool-bundled version (Option B) |

## Architecture

### Environment Metadata

`env_meta.json` gains three fields:

```json
{
  "python_version": "3.12.8",
  "cuda_tag": "cu124",
  "pytorch_version": "2.6.0"
}
```

- `python_version`: set at creation, immutable
- `cuda_tag`: mutable via PyTorch reinstall
- `pytorch_version`: updated on reinstall

### Downloaded Python Storage

```
tools/
├── python/              # Tool-bundled 3.12.8 (runs launcher.py)
├── python_3.10.16/      # User-installed, for env venvs
├── python_3.13.3/       # User-installed, for env venvs
└── version_cache.json   # Cached version lists
```

Tool itself always runs from `tools/python/`, unaffected by environment versions.

### Version Cache

`tools/version_cache.json`:

```json
{
  "last_updated": "2026-04-06T12:00:00",
  "python": [
    {"version": "3.13.3", "url": "https://...", "sha256": "..."},
    {"version": "3.12.8", "url": "https://...", "sha256": "..."}
  ],
  "cuda_tags": ["cpu", "cu118", "cu121", "cu124", "cu126", "cu128", "cu130"]
}
```

### Built-in Defaults (Hardcoded)

```python
DEFAULT_PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]
DEFAULT_CUDA_TAGS = ["cpu", "cu118", "cu121", "cu124", "cu126", "cu128"]
```

## Environment Creation Flow

1. User enters environment name, selects branch
2. Background: run `nvidia-smi` to detect GPU, determine default CUDA tag
3. Dialog shows collapsible "Advanced Options" section at bottom
4. Default: create with tool-bundled Python + detected CUDA version
5. If user expands advanced options:
   - **Python version** dropdown (default = tool-bundled, labeled "Recommended")
   - **CUDA version** dropdown (default = GPU detection result, labeled "Recommended")
   - "Refresh version list" button + hint: "List is offline cache, click to refresh for latest versions"
6. If different Python selected: download embedded Python to `tools/python_{version}/`, use it to create venv

## GPU Auto-Detection

- Run `nvidia-smi` and parse driver-supported max CUDA version
- Map to closest PyTorch CUDA tag (e.g., driver supports 12.6 -> recommend cu126)
- No NVIDIA GPU detected -> default to CPU-only
- Python defaults to tool-bundled version (currently 3.12.8)

## Version List Refresh

### Sources

- **Python**: fetch `https://www.python.org/ftp/python/index-windows.json`, filter `company == "PythonEmbed"` + amd64
- **CUDA**: fetch `https://download.pytorch.org/whl/` directory page, parse all `cu*` and `cpu` links

### Behavior

- Success: write to `version_cache.json`, update dropdowns
- Failure: show "Refresh failed, using offline list", fall back to built-in defaults

### UI Hints

- Has cache: "List updated on 2026-04-06. Click to refresh."
- No cache: "Currently using offline list. Click to refresh for latest versions."

## CUDA/PyTorch Reinstall Flow

1. User selects target CUDA version from dropdown (with refresh button)
2. Confirmation prompt: "Will reinstall torch, torchvision, torchaudio for {cuda_tag}. Other packages unchanged."
3. Execute:
   ```
   pip uninstall torch torchvision torchaudio -y
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/{cuda_tag}
   ```
4. Update `env_meta.json` cuda_tag and pytorch_version
5. Auto-run `conflict_analyzer` 6-step analysis
6. Conflicts found: show conflict report, user decides
7. No conflicts: show "Reinstall complete"

### Not in Scope

- No auto-rollback (user can use existing snapshot feature manually)
- No specific PyTorch version selection (only CUDA tag, pip resolves latest compatible)
