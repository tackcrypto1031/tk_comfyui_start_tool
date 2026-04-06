"""Launcher — GUI (QWebEngineView) or CLI mode selector."""
import sys
import ctypes
from pathlib import Path

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
        window.setWindowTitle("tack_comfyui_start_tool")
        window.setWindowIcon(app_icon)
        window.setMinimumSize(1200, 800)

        # Web view with channel
        view = QWebEngineView()

        # Enable remote content loading (CDN for Tailwind, Fonts)
        settings = view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        channel = QWebChannel()
        bridge = Bridge(config)
        channel.registerObject("bridge", bridge)
        view.page().setWebChannel(channel)

        # Load the SPA
        html_path = Path(__file__).parent / "src" / "gui" / "web" / "index.html"
        view.load(QUrl.fromLocalFile(str(html_path.resolve())))

        window.setCentralWidget(view)
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
