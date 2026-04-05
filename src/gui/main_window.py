"""Main application window."""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QStackedWidget, QLabel, QComboBox,
)

from src.gui.i18n import t, set_language, get_language


class MainWindow(QMainWindow):
    """Main window with sidebar navigation and stacked panel area."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

        # Set language from config before building UI
        lang = config.get("language", "en")
        set_language(lang)

        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(1100, 750)

        # Central widget
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar: language switcher
        top_bar = QWidget()
        top_bar.setStyleSheet(f"background-color: #131313; border-bottom: 1px solid #191919;")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(8, 4, 8, 4)
        top_bar_layout.addStretch()
        self.lbl_language = QLabel()
        top_bar_layout.addWidget(self.lbl_language)
        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumWidth(120)
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("繁體中文", "zh-TW")
        # Set combo to current language
        idx = self.lang_combo.findData(get_language())
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        top_bar_layout.addWidget(self.lang_combo)
        main_layout.addWidget(top_bar)

        # Content area: sidebar + panels
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Left sidebar
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.currentRowChanged.connect(self._on_tab_changed)
        content_layout.addWidget(self.sidebar)

        # Right panel area (stacked)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)

        main_layout.addWidget(content)

        # Status bar
        self.statusBar().showMessage(t("ready"))

        # Add panels
        self._panels = []
        self._setup_panels()

        # Apply initial translations to top bar
        self.lbl_language.setText(t("language") + ":")

    def _setup_panels(self):
        """Add all panels. Import here to avoid circular imports."""
        from src.gui.panels.env_panel import EnvPanel
        from src.gui.panels.launcher_panel import LauncherPanel

        self._add_panel("sidebar_environments", EnvPanel(self.config))
        self._add_panel("sidebar_launch", LauncherPanel(self.config))

        try:
            from src.gui.panels.plugin_panel import PluginPanel
            self._add_panel("sidebar_plugins", PluginPanel(self.config))
        except ImportError:
            self._add_panel("sidebar_plugins", QLabel("Plugin panel (coming soon)"))

        try:
            from src.gui.panels.version_panel import VersionPanel
            self._add_panel("sidebar_versions", VersionPanel(self.config))
        except ImportError:
            self._add_panel("sidebar_versions", QLabel("Version panel (coming soon)"))

        try:
            from src.gui.panels.snapshot_panel import SnapshotPanel
            self._add_panel("sidebar_snapshots", SnapshotPanel(self.config))
        except ImportError:
            self._add_panel("sidebar_snapshots", QLabel("Snapshot panel (coming soon)"))

        self.sidebar.setCurrentRow(0)

    def _add_panel(self, sidebar_key: str, widget: QWidget):
        self.sidebar.addItem(t(sidebar_key))
        self.stack.addWidget(widget)
        self._panels.append((sidebar_key, widget))

    def _on_tab_changed(self, index: int):
        self.stack.setCurrentIndex(index)

    def _on_language_changed(self, index: int):
        lang = self.lang_combo.itemData(index)
        if not lang:
            return
        set_language(lang)

        # Update window title and status bar
        self.setWindowTitle(t("app_title"))
        self.statusBar().showMessage(t("ready"))
        self.lbl_language.setText(t("language") + ":")

        # Update sidebar items
        for i, (key, _) in enumerate(self._panels):
            self.sidebar.item(i).setText(t(key))

        # Retranslate each panel that supports it
        for _, widget in self._panels:
            if hasattr(widget, "retranslate"):
                widget.retranslate()

        # Optionally save language preference to config
        self.config["language"] = lang

    def update_status(self, message: str):
        self.statusBar().showMessage(message)
