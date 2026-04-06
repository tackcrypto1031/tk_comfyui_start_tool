# Technology Stack

**Analysis Date:** 2026-04-06

## Languages

**Primary:**
- Python 3.x - Backend application, CLI, environment management
- JavaScript (ES6+) - Frontend SPA in web UI
- HTML5 - Web interface structure
- CSS3 - Styling with Tailwind CSS

**Secondary:**
- Batch/Shell - Windows launcher script (`start.bat`)
- YAML - Configuration for environment metadata

## Runtime

**Environment:**
- Python (version managed per ComfyUI environment, typically 3.10+)
- PySide6 - Qt-based desktop GUI runtime
- QWebEngine - Chromium-based web rendering for UI

**Package Manager:**
- pip - Primary Python package manager
- venv - Virtual environment creation and management
- Lockfile: `requirements.txt` (present)

## Frameworks

**Core:**
- Click 8.1+ - CLI framework for command-line interface
- PySide6 6.5+ - Desktop GUI framework (Qt bindings)
- PySide6-WebEngine 6.5+ - Qt WebEngine for web UI

**Frontend:**
- Tailwind CSS - Utility-first CSS framework (pre-compiled)
- Material Symbols - Google Material Design icons
- Custom SPA router (`app.js`) - Page navigation and state management

**Testing:**
- pytest 7.0+ - Test runner and framework
- pytest-cov 4.0+ - Code coverage reporting

**Build/Dev:**
- GitPython 3.1+ - Git repository operations
- PyYAML 6.0+ - YAML parsing for environment metadata

## Key Dependencies

**Critical:**
- GitPython 3.1+ - Git cloning, branch/commit management for ComfyUI environments
- PySide6 6.5+ - Desktop application framework
- PySide6-WebEngine 6.5+ - Web-based UI rendering
- requests 2.31+ - HTTP client for health checks and remote content loading
- packaging 23.0+ - Version parsing and comparison for conflict detection
- psutil 5.9+ - Process monitoring and management

**Infrastructure:**
- Click 8.1+ - Structured CLI command handling
- rich 13.0+ - Terminal output formatting and tables
- PyYAML 6.0+ - Configuration file parsing
- pytest 7.0+ - Unit testing framework
- pytest-cov 4.0+ - Test coverage measurement

## Configuration

**Environment:**
- Configured via `config.json` in project root
- Can override config path via CLI: `--config path/to/config.json`
- Key configs: environments directory, models directory, snapshots directory, PyTorch index URL, default port, theme, language, log level

**Build:**
- Tailwind CSS configuration: `src/gui/web/tailwind.config.js` (customized dark theme with Material 3 colors)
- pytest configuration: `pytest.ini` (test discovery in `tests/` directory, verbose output)
- Custom CSS: `src/gui/web/css/custom.css`

**Environment Variables:**
- `GIT_TERMINAL_PROMPT=0` (Windows) - Prevents interactive git prompts in subprocess

## Platform Requirements

**Development:**
- Windows (primary target - `start.bat` launcher)
- macOS/Linux support (cross-platform Python framework)
- Python 3.10+ recommended (for ComfyUI compatibility)

**Production:**
- Local desktop application (standalone executable possible via PyInstaller)
- Manages local ComfyUI environments in `./environments/` directory
- Requires disk space for virtual environments and model files

**Client Connectivity:**
- Local HTTP health checks on `localhost:{port}` (configurable, default 8188)
- Browser for web UI access (via QWebEngine)

## External URLs & Resources

**Fonts & Icons:**
- Google Fonts: Space Grotesk, Inter fonts (CDN)
- Material Symbols (Google Material Design icons - CDN)

**Dependencies Download:**
- PyTorch index URL (configurable): Default `https://download.pytorch.org/whl/cu124` (CUDA 12.4)

---

*Stack analysis: 2026-04-06*
