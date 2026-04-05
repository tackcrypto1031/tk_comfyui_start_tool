"""Plugin management and conflict analysis panel."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QTableWidget, QTableWidgetItem,
    QComboBox, QTextEdit, QGroupBox, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt

from src.core.env_manager import EnvManager
from src.core.conflict_analyzer import ConflictAnalyzer
from src.gui.workers import Worker
from src.gui.i18n import t


class PluginPanel(QWidget):
    """Plugin management and conflict analysis panel."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.manager = EnvManager(config)
        self.analyzer = ConflictAnalyzer(config)
        self._workers = []

        layout = QVBoxLayout(self)

        # Environment selector
        env_row = QHBoxLayout()
        self.lbl_environment = QLabel()
        env_row.addWidget(self.lbl_environment)
        self.env_combo = QComboBox()
        env_row.addWidget(self.env_combo)
        self.btn_refresh_envs = QPushButton()
        env_row.addWidget(self.btn_refresh_envs)
        layout.addLayout(env_row)

        # Plugin URL input + Analyze button
        input_row = QHBoxLayout()
        self.url_input = QLineEdit()
        input_row.addWidget(self.url_input)
        self.btn_analyze = QPushButton()
        self.btn_analyze.setProperty("cssClass", "primary")
        input_row.addWidget(self.btn_analyze)
        layout.addLayout(input_row)

        # Conflict report area
        self.report_group = QGroupBox()
        report_layout = QVBoxLayout(self.report_group)

        self.risk_label = QLabel()
        self.risk_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        report_layout.addWidget(self.risk_label)

        self.summary_label = QLabel("")
        report_layout.addWidget(self.summary_label)

        self.conflict_table = QTableWidget()
        self.conflict_table.setColumnCount(5)
        self.conflict_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.conflict_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.conflict_table.setAlternatingRowColors(True)
        report_layout.addWidget(self.conflict_table)

        self.recommendations_text = QTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setMaximumHeight(100)
        report_layout.addWidget(self.recommendations_text)

        layout.addWidget(self.report_group)

        # Status
        self.status_label = QLabel("")
        self.status_label.setProperty("cssClass", "status")
        layout.addWidget(self.status_label)

        # Signals
        self.btn_refresh_envs.clicked.connect(self._refresh_envs)
        self.btn_analyze.clicked.connect(self._on_analyze)

        self.retranslate()
        self._refresh_envs()

    def retranslate(self):
        """Update all visible text to the current language."""
        self.lbl_environment.setText(t("plugin_environment"))
        self.btn_refresh_envs.setText(t("env_refresh"))
        self.url_input.setPlaceholderText(t("plugin_url_placeholder"))
        self.btn_analyze.setText(t("plugin_analyze"))
        self.report_group.setTitle(t("plugin_conflict_report"))
        self.risk_label.setText(f"{t('plugin_risk_level')} —")
        self.conflict_table.setHorizontalHeaderLabels([
            t("plugin_col_package"),
            t("plugin_col_current"),
            t("plugin_col_new"),
            t("plugin_col_type"),
            t("plugin_col_risk"),
        ])

    def _refresh_envs(self):
        worker = Worker(self.manager.list_environments)
        worker.finished.connect(self._on_envs_loaded)
        worker.error.connect(lambda e: self.status_label.setText(f"{t('error')}: {e}"))
        self._workers.append(worker)
        worker.start()

    def _on_envs_loaded(self, envs):
        self.env_combo.clear()
        for env in envs:
            self.env_combo.addItem(env.name)

    def _on_analyze(self):
        env_name = self.env_combo.currentText()
        node_path = self.url_input.text().strip()
        if not env_name or not node_path:
            QMessageBox.information(self, t("info"), t("plugin_select_env_and_path"))
            return
        self.status_label.setText(t("plugin_analyzing"))
        self.btn_analyze.setEnabled(False)
        worker = Worker(self.analyzer.analyze, env_name, node_path)
        worker.finished.connect(self._on_report_ready)
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_analyze.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()

    def _on_report_ready(self, report):
        self.btn_analyze.setEnabled(True)
        risk_colors = {
            "GREEN": "green",
            "YELLOW": "#F39C12",
            "HIGH": "red",
            "CRITICAL": "purple",
        }
        color = risk_colors.get(report.risk_level.value, "white")
        self.risk_label.setText(f"{t('plugin_risk_level')} {report.risk_level.value}")
        self.risk_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {color};"
        )
        self.summary_label.setText(report.summary)

        self.conflict_table.setRowCount(len(report.conflicts))
        for i, c in enumerate(report.conflicts):
            self.conflict_table.setItem(i, 0, QTableWidgetItem(c.package))
            self.conflict_table.setItem(i, 1, QTableWidgetItem(c.current_version))
            self.conflict_table.setItem(i, 2, QTableWidgetItem(c.resolved_version))
            self.conflict_table.setItem(i, 3, QTableWidgetItem(c.change_type))
            self.conflict_table.setItem(i, 4, QTableWidgetItem(c.risk_level.value))

        self.recommendations_text.setPlainText("\n".join(report.recommendations))
        self.status_label.setText(t("plugin_analysis_complete"))
