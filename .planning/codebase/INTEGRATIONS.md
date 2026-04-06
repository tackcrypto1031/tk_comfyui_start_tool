# External Integrations

**Analysis Date:** 2026-04-06

## APIs & External Services

**GitHub:**
- ComfyUI Repository - Main AI image generation framework
  - URL: `https://github.com/comfyanonymous/ComfyUI.git`
  - SDK/Client: GitPython
  - Auth: None (public repo, cloning via HTTPS)
  - Location in code: `src/core/env_manager.py` (DEFAULT_COMFYUI_URL)

- ComfyUI-Manager Repository - Plugin/extension management
  - URL: `https://github.com/Comfy-Org/ComfyUI-Manager.git`
  - SDK/Client: GitPython
  - Auth: None (public repo)
  - Location in code: `src/core/env_manager.py` (DEFAULT_MANAGER_URL)

**ComfyUI Local HTTP Server:**
- Health checks via HTTP GET to `http://localhost:{port}/`
- SDK/Client: `requests` library
- Auth: None (local loopback connection)
- Location in code: `src/core/comfyui_launcher.py` (`health_check()` method)
- Purpose: Verify ComfyUI startup before opening browser

## Data Storage

**Databases:**
- None (no remote database)

**File Storage:**
- Local filesystem only
  - ComfyUI environments: `./environments/{env_name}/ComfyUI/`
  - Models directory: `./models/`
  - Snapshots: `./snapshots/`
  - Virtual environments: `./environments/{env_name}/venv/`
  - Configuration: `./config.json`
  - Environment metadata: `./environments/{env_name}/environment.json`

**Caching:**
- None (uses pip cache for package installation)

## Authentication & Identity

**Auth Provider:**
- None (local desktop application)
- All operations are local user-scoped
- No user accounts or login required

## Monitoring & Observability

**Error Tracking:**
- None (no remote error tracking)

**Logs:**
- File-based logging: `debug.log` in project root
- Configured in: `src/gui/bridge.py` (logging setup)
- Level: Configurable via `config.json` (`log_level` field, default "INFO")
- ComfyUI process logs: `./environments/{env_name}/comfyui.log`

## CI/CD & Deployment

**Hosting:**
- Local desktop application (no cloud hosting)
- Can be packaged as standalone executable (PyInstaller possible)

**CI Pipeline:**
- None (no remote CI configured)
- Local testing via pytest

## Environment Configuration

**Required env vars:**
- `GIT_TERMINAL_PROMPT` (Windows) - Set to "0" to prevent interactive git prompts

**Secrets location:**
- None required (no API keys, passwords, or secrets)
- All configuration in `config.json` (no sensitive data)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Remote Content Access

**Allowed CDN Resources:**
- Google Fonts (Space Grotesk, Inter)
- Material Symbols (icon font)
- PyTorch wheel index (for CUDA-specific wheel downloads)

**Enable Remote Content in QWebEngine:**
- Setting: `LocalContentCanAccessRemoteUrls = True`
- Location: `launcher.py` (QWebEngineSettings configuration)
- Purpose: Allow HTML to load external fonts and stylesheets

## Browser Launch Integration

**Browser Automation:**
- Uses Python `webbrowser` module (standard library)
- Opens `http://localhost:{port}` after ComfyUI starts
- Configurable via `config.json` (`auto_open_browser` field)
- Location in code: `src/core/comfyui_launcher.py` (`start()` method, background thread)

## Process Management

**External Process Handling:**
- Launches ComfyUI as subprocess via `subprocess.Popen()`
- Monitors with `psutil` for process existence
- Manages via PID files: `./environments/{env_name}/.comfyui.pid`
- Location in code: `src/utils/process_manager.py`

## Version Control Integration

**Git Operations:**
- Clone repositories with branch/commit checkout
- Handles progress callbacks during clone
- Version tracking via `git.Repo` (GitPython)
- Windows-specific: Disables interactive prompts for subprocess safety
- Location in code: `src/utils/git_ops.py`

---

*Integration audit: 2026-04-06*
