"""Plugin management and conflict analysis panel."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QTableWidget, QTableWidgetItem,
    QComboBox, QTextEdit, QGroupBox, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

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
        self._last_report = None

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

        # ── TOP SECTION: Analyze + Install ──────────────────────────────────
        # Plugin URL input + Analyze + Install buttons
        input_row = QHBoxLayout()
        self.url_input = QLineEdit()
        input_row.addWidget(self.url_input)
        self.btn_analyze = QPushButton()
        self.btn_analyze.setProperty("cssClass", "primary")
        input_row.addWidget(self.btn_analyze)
        self.btn_install = QPushButton()
        self.btn_install.setProperty("cssClass", "primary")
        self.btn_install.setEnabled(False)
        input_row.addWidget(self.btn_install)
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

        # ── BOTTOM SECTION: Installed Plugin List ──────────────────────────
        self.installed_group = QGroupBox()
        installed_layout = QVBoxLayout(self.installed_group)

        installed_header = QHBoxLayout()
        installed_header.addStretch()
        self.btn_refresh_plugins = QPushButton()
        installed_header.addWidget(self.btn_refresh_plugins)
        installed_layout.addLayout(installed_header)

        self.plugin_table = QTableWidget()
        self.plugin_table.setColumnCount(3)
        header = self.plugin_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.plugin_table.setColumnWidth(1, 90)
        self.plugin_table.setColumnWidth(2, 180)
        self.plugin_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.plugin_table.setAlternatingRowColors(True)
        installed_layout.addWidget(self.plugin_table)

        layout.addWidget(self.installed_group)

        # Status
        self.status_label = QLabel("")
        self.status_label.setProperty("cssClass", "status")
        layout.addWidget(self.status_label)

        # Signals
        self.btn_refresh_envs.clicked.connect(self._refresh_envs)
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_install.clicked.connect(self._on_install)
        self.btn_refresh_plugins.clicked.connect(self._refresh_plugins)
        self.url_input.textChanged.connect(self._on_url_changed)
        self.env_combo.currentTextChanged.connect(self._refresh_plugins)

        self.retranslate()
        self._refresh_envs()

    def retranslate(self):
        """Update all visible text to the current language."""
        self.lbl_environment.setText(t("plugin_environment"))
        self.btn_refresh_envs.setText(t("env_refresh"))
        self.installed_group.setTitle(t("plugin_installed_title"))
        self.btn_refresh_plugins.setText(t("env_refresh"))
        self.plugin_table.setHorizontalHeaderLabels([
            t("plugin_col_name"),
            t("plugin_col_status"),
            t("plugin_col_actions"),
        ])
        self.url_input.setPlaceholderText(t("plugin_url_placeholder"))
        self.btn_analyze.setText(t("plugin_analyze"))
        self.btn_install.setText(t("plugin_install"))
        self.report_group.setTitle(t("plugin_conflict_report"))
        self.risk_label.setText(f"{t('plugin_risk_level')} —")
        self.conflict_table.setHorizontalHeaderLabels([
            t("plugin_col_package"),
            t("plugin_col_current"),
            t("plugin_col_new"),
            t("plugin_col_type"),
            t("plugin_col_risk"),
        ])

    # ── Environment helpers ─────────────────────────────────────────────────

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

    # ── Installed plugin list ───────────────────────────────────────────────

    def _refresh_plugins(self):
        env_name = self.env_combo.currentText()
        if not env_name:
            return
        worker = Worker(self.manager.list_custom_nodes, env_name)
        worker.finished.connect(self._populate_plugin_table)
        worker.error.connect(lambda e: self.status_label.setText(f"{t('error')}: {e}"))
        self._workers.append(worker)
        worker.start()

    def _populate_plugin_table(self, plugins):
        self.plugin_table.setRowCount(0)
        if not plugins:
            self.status_label.setText(t("plugin_no_plugins"))
            return
        self.plugin_table.setRowCount(len(plugins))
        for row, plugin in enumerate(plugins):
            name = plugin.get("name", "")
            status = plugin.get("status", "untracked")

            name_item = QTableWidgetItem(name)
            self.plugin_table.setItem(row, 0, name_item)

            status_display, status_color = self._status_display(status)
            status_item = QTableWidgetItem(status_display)
            status_item.setForeground(QColor(status_color))
            self.plugin_table.setItem(row, 1, status_item)

            action_widget = self._make_action_widget(name, status)
            self.plugin_table.setCellWidget(row, 2, action_widget)

    def _status_display(self, status: str):
        if status == "enabled":
            return t("plugin_status_enabled"), "green"
        if status == "disabled":
            return t("plugin_status_disabled"), "#F39C12"
        return t("plugin_status_untracked"), "#888888"

    def _make_action_widget(self, node_name: str, status: str) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(2, 2, 2, 2)

        if status == "enabled":
            toggle_btn = QPushButton(t("plugin_disable"))
            toggle_btn.clicked.connect(lambda: self._on_disable(node_name))
        else:
            toggle_btn = QPushButton(t("plugin_enable"))
            toggle_btn.clicked.connect(lambda: self._on_enable(node_name))
        h.addWidget(toggle_btn)

        delete_btn = QPushButton(t("plugin_delete"))
        delete_btn.setProperty("cssClass", "danger")
        delete_btn.clicked.connect(lambda: self._on_delete(node_name))
        h.addWidget(delete_btn)

        return container

    # ── Plugin actions ──────────────────────────────────────────────────────

    def _on_disable(self, node_name: str):
        if node_name == "ComfyUI-Manager":
            result = QMessageBox.warning(
                self,
                t("warning"),
                t("plugin_confirm_manager_disable"),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if result != QMessageBox.StandardButton.Ok:
                return
        env_name = self.env_combo.currentText()
        worker = Worker(self.manager.disable_custom_node, env_name, node_name)
        worker.finished.connect(lambda _: (
            self.status_label.setText(t("plugin_restart_hint")),
            self._refresh_plugins(),
        ))
        worker.error.connect(lambda e: self.status_label.setText(f"{t('error')}: {e}"))
        self._workers.append(worker)
        worker.start()

    def _on_enable(self, node_name: str):
        env_name = self.env_combo.currentText()
        worker = Worker(self.manager.enable_custom_node, env_name, node_name)
        worker.finished.connect(lambda _: (
            self.status_label.setText(t("plugin_restart_hint")),
            self._refresh_plugins(),
        ))
        worker.error.connect(lambda e: self.status_label.setText(f"{t('error')}: {e}"))
        self._workers.append(worker)
        worker.start()

    def _on_delete(self, node_name: str):
        result = QMessageBox.question(
            self,
            t("confirm"),
            t("plugin_confirm_delete").replace("{}", node_name),
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        if node_name == "ComfyUI-Manager":
            result2 = QMessageBox.warning(
                self,
                t("warning"),
                t("plugin_confirm_manager_delete"),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if result2 != QMessageBox.StandardButton.Ok:
                return
        env_name = self.env_combo.currentText()
        worker = Worker(self.manager.delete_custom_node, env_name, node_name)
        worker.finished.connect(lambda _: (
            self.status_label.setText(t("plugin_restart_hint")),
            self._refresh_plugins(),
        ))
        worker.error.connect(lambda e: self.status_label.setText(f"{t('error')}: {e}"))
        self._workers.append(worker)
        worker.start()

    # ── Analyze + Install ───────────────────────────────────────────────────

    def _on_url_changed(self):
        self.btn_install.setEnabled(False)
        self._last_report = None

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

        self._last_report = report
        url = self.url_input.text().strip()
        if url.startswith("http") or url.startswith("git@"):
            self.btn_install.setEnabled(True)

    def _on_install(self):
        env_name = self.env_combo.currentText()
        git_url = self.url_input.text().strip()
        if self._last_report is not None:
            risk_level = self._last_report.risk_level.value
            if risk_level in ("HIGH", "CRITICAL"):
                result = QMessageBox.warning(
                    self,
                    t("warning"),
                    t("plugin_confirm_high_risk").replace("{}", risk_level),
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                )
                if result != QMessageBox.StandardButton.Ok:
                    return
        self.btn_install.setEnabled(False)
        self.status_label.setText(t("plugin_cloning"))

        def progress_callback(msg: str):
            self.status_label.setText(msg)

        worker = Worker(self.manager.install_custom_node, env_name, git_url, progress_callback)
        worker.finished.connect(self._on_install_done)
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_install.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()

    def _on_install_done(self, _):
        self.status_label.setText(t("plugin_install_done"))
        self.status_label.setText(t("plugin_restart_hint"))
        self._refresh_plugins()
        self.btn_install.setEnabled(False)
