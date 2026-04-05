"""The Obsidian Edge — QSS theme engine for the Monolith Protocol design system."""
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase, QPalette, QColor
from PySide6.QtCore import Qt
from pathlib import Path


# ── Color Tokens ──────────────────────────────────────────────
COLORS = {
    # Backgrounds
    "base": "#000000",
    "surface": "#0e0e0e",
    "surface_dim": "#0a0a0a",
    "surface_container_low": "#131313",
    "surface_container": "#191919",
    "surface_container_high": "#1f1f1f",
    "surface_container_highest": "#262626",

    # Primary
    "primary": "#cc97ff",
    "primary_dim": "#9c48ea",
    "primary_container": "#2d1a4e",
    "on_primary": "#1a0030",

    # Text
    "on_surface": "#ffffff",
    "on_surface_variant": "#ababab",
    "on_surface_dim": "#6b6b6b",

    # Outline
    "outline": "#484848",
    "outline_variant": "rgba(72, 72, 72, 0.2)",

    # Semantic
    "error": "#ff6e84",
    "success": "#4ade80",
    "warning": "#fbbf24",
}


def get_font_family(role: str = "body") -> str:
    """Get font family string for a role: 'headline', 'label', or 'body'."""
    if role in ("headline", "label"):
        return "'Space Grotesk', 'Segoe UI', 'Arial', sans-serif"
    return "'Inter', 'Segoe UI', 'Arial', sans-serif"


def _build_stylesheet() -> str:
    """Build the complete QSS stylesheet."""
    c = COLORS
    return f"""
    /* ── Global Reset ───────────────────────────────── */
    * {{
        font-family: 'Inter', 'Segoe UI', 'Arial', sans-serif;
        font-size: 13px;
        color: {c["on_surface"]};
        border: none;
        outline: none;
    }}

    /* ── Main Window ────────────────────────────────── */
    QMainWindow {{
        background-color: {c["surface"]};
    }}

    QWidget {{
        background-color: transparent;
    }}

    QWidget#centralWidget {{
        background-color: {c["surface"]};
    }}

    /* ── Sidebar (QListWidget) ──────────────────────── */
    QListWidget {{
        background-color: {c["surface_dim"]};
        border: none;
        border-right: 1px solid {c["surface_container"]};
        padding: 8px 0;
        font-family: {get_font_family("label")};
        font-size: 12px;
        outline: none;
    }}

    QListWidget::item {{
        color: {c["on_surface_variant"]};
        padding: 12px 16px 12px 20px;
        border: none;
        border-left: 3px solid transparent;
        margin: 0;
    }}

    QListWidget::item:selected {{
        background-color: {c["surface_container_low"]};
        color: {c["primary"]};
        border-left: 3px solid {c["primary"]};
    }}

    QListWidget::item:hover:!selected {{
        background-color: {c["surface_container_low"]};
        color: {c["on_surface"]};
    }}

    /* ── Buttons ────────────────────────────────────── */
    QPushButton {{
        background-color: {c["surface_container"]};
        color: {c["on_surface"]};
        border: 1px solid {c["outline"]};
        padding: 8px 20px;
        font-family: {get_font_family("label")};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        min-height: 18px;
    }}

    QPushButton:hover {{
        background-color: {c["surface_container_high"]};
        border-color: {c["primary"]};
        color: {c["primary"]};
    }}

    QPushButton:pressed {{
        background-color: {c["surface_container_highest"]};
    }}

    QPushButton:disabled {{
        background-color: {c["surface_container_low"]};
        color: {c["on_surface_dim"]};
        border-color: {c["surface_container"]};
    }}

    /* Primary button variant */
    QPushButton[cssClass="primary"] {{
        background-color: {c["primary"]};
        color: {c["on_primary"]};
        border: none;
        font-weight: 700;
    }}

    QPushButton[cssClass="primary"]:hover {{
        background-color: {c["primary_dim"]};
        color: {c["on_primary"]};
    }}

    QPushButton[cssClass="primary"]:pressed {{
        background-color: #8a3ed4;
    }}

    QPushButton[cssClass="primary"]:disabled {{
        background-color: {c["primary_container"]};
        color: {c["on_surface_dim"]};
    }}

    /* Danger button variant */
    QPushButton[cssClass="danger"] {{
        background-color: transparent;
        color: {c["error"]};
        border: 1px solid {c["error"]};
    }}

    QPushButton[cssClass="danger"]:hover {{
        background-color: rgba(255, 110, 132, 0.1);
    }}

    /* ── Inputs ─────────────────────────────────────── */
    QLineEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {c["base"]};
        color: {c["on_surface"]};
        border: 1px solid {c["outline"]};
        padding: 8px 12px;
        font-size: 13px;
        selection-background-color: {c["primary"]};
        selection-color: {c["on_primary"]};
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {c["primary"]};
    }}

    QLineEdit:disabled, QSpinBox:disabled {{
        background-color: {c["surface_container_low"]};
        color: {c["on_surface_dim"]};
    }}

    QLineEdit::placeholder {{
        color: {c["on_surface_dim"]};
    }}

    /* ── ComboBox ───────────────────────────────────── */
    QComboBox {{
        background-color: {c["base"]};
        color: {c["on_surface"]};
        border: 1px solid {c["outline"]};
        padding: 8px 12px;
        padding-right: 30px;
        font-size: 13px;
    }}

    QComboBox:focus, QComboBox:on {{
        border-color: {c["primary"]};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 30px;
        background-color: transparent;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {c["on_surface_variant"]};
        margin-right: 10px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {c["surface_container_highest"]};
        color: {c["on_surface"]};
        border: 1px solid {c["outline"]};
        selection-background-color: {c["primary_container"]};
        selection-color: {c["primary"]};
        padding: 4px;
        outline: none;
    }}

    /* ── Tables ─────────────────────────────────────── */
    QTableWidget {{
        background-color: {c["surface"]};
        color: {c["on_surface"]};
        gridline-color: {c["surface_container"]};
        border: 1px solid {c["surface_container"]};
        selection-background-color: {c["primary_container"]};
        selection-color: {c["primary"]};
        alternate-background-color: {c["surface_container_low"]};
        outline: none;
    }}

    QTableWidget::item {{
        padding: 6px 12px;
        border: none;
    }}

    QTableWidget::item:selected {{
        background-color: {c["primary_container"]};
        color: {c["primary"]};
    }}

    QHeaderView::section {{
        background-color: {c["surface_container"]};
        color: {c["on_surface_variant"]};
        border: none;
        border-bottom: 1px solid {c["outline"]};
        border-right: 1px solid {c["surface_container_high"]};
        padding: 8px 12px;
        font-family: {get_font_family("label")};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    /* ── GroupBox ────────────────────────────────────── */
    QGroupBox {{
        background-color: {c["surface_container_low"]};
        border: 1px solid {c["surface_container"]};
        margin-top: 16px;
        padding: 20px 16px 12px 16px;
        font-family: {get_font_family("label")};
        font-size: 11px;
        font-weight: 600;
        color: {c["on_surface_variant"]};
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 12px;
        background-color: {c["surface_container_low"]};
        color: {c["primary"]};
    }}

    /* ── Labels ─────────────────────────────────────── */
    QLabel {{
        color: {c["on_surface_variant"]};
        font-size: 13px;
        background-color: transparent;
    }}

    QLabel[cssClass="heading"] {{
        color: {c["on_surface"]};
        font-family: {get_font_family("headline")};
        font-size: 18px;
        font-weight: 700;
    }}

    QLabel[cssClass="status"] {{
        color: {c["on_surface_dim"]};
        font-size: 12px;
    }}

    /* ── PlainTextEdit (Log area) ───────────────────── */
    QPlainTextEdit {{
        background-color: {c["base"]};
        color: {c["on_surface_variant"]};
        border: 1px solid {c["surface_container"]};
        font-family: 'Consolas', 'Cascadia Code', 'Courier New', monospace;
        font-size: 12px;
        padding: 8px;
        selection-background-color: {c["primary_container"]};
        selection-color: {c["primary"]};
    }}

    /* ── Dialogs ────────────────────────────────────── */
    QDialog {{
        background-color: {c["surface_container_high"]};
    }}

    QDialogButtonBox QPushButton {{
        min-width: 80px;
    }}

    /* ── StatusBar ───────────────────────────────────── */
    QStatusBar {{
        background-color: {c["surface_container_low"]};
        color: {c["on_surface_dim"]};
        border-top: 1px solid {c["surface_container"]};
        font-size: 11px;
        padding: 2px 8px;
    }}

    QStatusBar::item {{
        border: none;
    }}

    /* ── ScrollBars ──────────────────────────────────── */
    QScrollBar:vertical {{
        background-color: {c["surface"]};
        width: 8px;
        border: none;
    }}

    QScrollBar::handle:vertical {{
        background-color: {c["surface_container_highest"]};
        min-height: 30px;
        border: none;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {c["outline"]};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
        border: none;
    }}

    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background-color: transparent;
    }}

    QScrollBar:horizontal {{
        background-color: {c["surface"]};
        height: 8px;
        border: none;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {c["surface_container_highest"]};
        min-width: 30px;
        border: none;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {c["outline"]};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
        border: none;
    }}

    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background-color: transparent;
    }}

    /* ── MessageBox ──────────────────────────────────── */
    QMessageBox {{
        background-color: {c["surface_container_high"]};
    }}

    QMessageBox QLabel {{
        color: {c["on_surface"]};
        font-size: 13px;
    }}

    /* ── ToolTip ─────────────────────────────────────── */
    QToolTip {{
        background-color: {c["surface_container_highest"]};
        color: {c["on_surface"]};
        border: 1px solid {c["outline"]};
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* ── Radio & Checkbox ────────────────────────────── */
    QRadioButton, QCheckBox {{
        color: {c["on_surface"]};
        spacing: 8px;
        font-size: 13px;
    }}

    QRadioButton::indicator, QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {c["outline"]};
        background-color: {c["base"]};
    }}

    QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
        background-color: {c["primary"]};
        border-color: {c["primary"]};
    }}

    /* ── FormLayout Labels ───────────────────────────── */
    QFormLayout QLabel {{
        font-family: {get_font_family("label")};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: {c["on_surface_variant"]};
    }}

    /* ── Tab Widget ──────────────────────────────────── */
    QTabWidget::pane {{
        border: 1px solid {c["surface_container"]};
        background-color: {c["surface"]};
    }}

    QTabBar::tab {{
        background-color: {c["surface_container_low"]};
        color: {c["on_surface_variant"]};
        padding: 8px 20px;
        border: none;
        border-bottom: 2px solid transparent;
        font-family: {get_font_family("label")};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }}

    QTabBar::tab:selected {{
        color: {c["primary"]};
        border-bottom: 2px solid {c["primary"]};
        background-color: {c["surface"]};
    }}

    QTabBar::tab:hover:!selected {{
        color: {c["on_surface"]};
        background-color: {c["surface_container"]};
    }}
    """


def apply_theme(app: QApplication) -> None:
    """Apply The Obsidian Edge theme to the application."""
    # Try to load fonts
    _load_fonts()

    # Set application-wide stylesheet
    app.setStyleSheet(_build_stylesheet())

    # Set palette for native dialogs
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["on_surface"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["base"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["surface_container_low"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["on_surface"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["surface_container"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["on_surface"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["primary"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS["on_primary"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["surface_container_highest"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["on_surface"]))
    app.setPalette(palette)


def _load_fonts():
    """Attempt to load custom fonts from assets/fonts/ directory."""
    fonts_dir = Path(__file__).parent.parent.parent / "assets" / "fonts"
    if not fonts_dir.exists():
        return
    for font_file in fonts_dir.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font_file))
    for font_file in fonts_dir.glob("*.otf"):
        QFontDatabase.addApplicationFont(str(font_file))
