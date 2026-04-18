"""Launcher — GUI (QWebEngineView) or CLI mode selector."""
import os
import sys
import ctypes
from pathlib import Path

# Set up embedded tools paths (must be before any gitpython import)
_root = Path(__file__).parent
_tools_git = _root / "tools" / "git" / "cmd" / "git.exe"
if _tools_git.exists():
    os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = str(_tools_git)

# Set AppUserModelID so Windows shows our icon on the taskbar
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("tack.comfyui.starter")


def main():
    if len(sys.argv) > 1:
        from cli import cli
        cli()
    else:
        from PySide6.QtWidgets import QApplication, QMainWindow
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
        from PySide6.QtWebChannel import QWebChannel
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QIcon
        from src.utils.fs_ops import load_config
        from src.gui.bridge import Bridge

        app = QApplication(sys.argv)
        config = load_config("config.json")

        # App icon (title bar + taskbar)
        icon_path = Path(__file__).parent / "assets" / "icon.ico"
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

        # Main window
        window = QMainWindow()
        window.setWindowTitle("塔克ComfyUI啟動器")
        window.setWindowIcon(app_icon)
        # Fixed window size per design spec — disables user resizing so the
        # embedded HTML SPA can rely on a known viewport (no layout jumps).
        window.setFixedSize(1500, 930)

        # Web view with JS console logging
        view = QWebEngineView()

        # Capture JS console messages to debug.log
        import logging as _logging
        _js_logger = _logging.getLogger("js_console")
        _js_logger.setLevel(_logging.DEBUG)
        _log_path = Path(__file__).parent / "debug.log"
        _fh = _logging.FileHandler(str(_log_path), encoding="utf-8")
        _fh.setFormatter(_logging.Formatter("%(asctime)s [JS] %(message)s"))
        _js_logger.addHandler(_fh)

        class LoggingPage(QWebEnginePage):
            def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
                _js_logger.info(f"L{level} {sourceID}:{lineNumber} {message}")

        page = LoggingPage(view)
        view.setPage(page)

        # Enable remote content loading (CDN for Tailwind, Fonts)
        # Must be AFTER setPage so settings apply to the active page
        settings = view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        # Run shared-model bootstrap + auto-grow scan before bridge construction
        from src.core.env_manager import EnvManager as _EnvManager
        _rescan_result = None
        try:
            _startup_mgr = _EnvManager(config)
            _startup_mgr.ensure_shared_models_if_safe()
            _rescan_result = _startup_mgr.sync_shared_model_subdirs(force_regen=False)
        except Exception as _e:  # pragma: no cover
            import logging as _logging
            _logging.getLogger("launcher").warning(
                "Startup shared-model scan failed: %s", _e, exc_info=True,
            )
            _rescan_result = None

        channel = QWebChannel()
        bridge = Bridge(config, last_rescan_result=_rescan_result)
        channel.registerObject("bridge", bridge)
        page.setWebChannel(channel)

        # Load the SPA
        html_path = Path(__file__).parent / "src" / "gui" / "web" / "index.html"
        view.load(QUrl.fromLocalFile(str(html_path.resolve())))

        window.setCentralWidget(view)
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
