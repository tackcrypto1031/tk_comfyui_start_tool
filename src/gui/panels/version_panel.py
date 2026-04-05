"""Version control panel for ComfyUI and custom nodes."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem,
    QComboBox, QHeaderView, QMessageBox, QGroupBox,
    QSplitter,
)
from PySide6.QtCore import Qt

from src.core.env_manager import EnvManager
from src.core.version_controller import VersionController
from src.gui.workers import Worker
from src.gui.i18n import t


class VersionPanel(QWidget):
    """Version control panel with remote version browsing."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.manager = EnvManager(config)
        self.controller = VersionController(config)
        self._workers = []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Environment + Target Selectors ──
        selector_row = QHBoxLayout()
        self.lbl_environment = QLabel()
        selector_row.addWidget(self.lbl_environment)
        self.env_combo = QComboBox()
        self.env_combo.setMinimumWidth(200)
        selector_row.addWidget(self.env_combo)
        self.lbl_target = QLabel()
        selector_row.addWidget(self.lbl_target)
        self.target_combo = QComboBox()
        self.target_combo.addItem("comfyui")
        selector_row.addWidget(self.target_combo)
        self.btn_refresh_envs = QPushButton()
        selector_row.addWidget(self.btn_refresh_envs)
        selector_row.addStretch()
        layout.addLayout(selector_row)

        # ── Splitter: Remote Tags (top) / Local Commits (bottom) ──
        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Remote Tags Section ──
        tags_widget = QWidget()
        tags_layout = QVBoxLayout(tags_widget)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setSpacing(8)

        tags_header = QHBoxLayout()
        self.lbl_tags_title = QLabel()
        self.lbl_tags_title.setProperty("cssClass", "heading")
        tags_header.addWidget(self.lbl_tags_title)
        tags_header.addStretch()
        self.btn_fetch_tags = QPushButton()
        self.btn_fetch_tags.setProperty("cssClass", "primary")
        tags_header.addWidget(self.btn_fetch_tags)
        self.tags_status = QLabel("")
        self.tags_status.setProperty("cssClass", "status")
        tags_header.addWidget(self.tags_status)
        tags_layout.addLayout(tags_header)

        self.tags_table = QTableWidget()
        self.tags_table.setColumnCount(2)
        self.tags_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tags_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tags_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tags_table.setAlternatingRowColors(True)
        tags_layout.addWidget(self.tags_table)

        tags_btn_row = QHBoxLayout()
        self.btn_install_tag = QPushButton()
        tags_btn_row.addWidget(self.btn_install_tag)
        tags_btn_row.addStretch()
        tags_layout.addLayout(tags_btn_row)

        splitter.addWidget(tags_widget)

        # ── Local Commits Section ──
        commits_widget = QWidget()
        commits_layout = QVBoxLayout(commits_widget)
        commits_layout.setContentsMargins(0, 0, 0, 0)
        commits_layout.setSpacing(8)

        commits_header = QHBoxLayout()
        self.lbl_commits_title = QLabel("GIT HISTORY")
        self.lbl_commits_title.setProperty("cssClass", "heading")
        commits_header.addWidget(self.lbl_commits_title)
        commits_header.addStretch()
        commits_layout.addLayout(commits_header)

        self.commits_table = QTableWidget()
        self.commits_table.setColumnCount(4)
        self.commits_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.commits_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.commits_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.commits_table.setAlternatingRowColors(True)
        commits_layout.addWidget(self.commits_table)

        btn_row = QHBoxLayout()
        self.btn_load_commits = QPushButton()
        self.btn_switch = QPushButton()
        self.btn_switch.setProperty("cssClass", "primary")
        self.btn_update = QPushButton()
        for btn in [self.btn_load_commits, self.btn_switch, self.btn_update]:
            btn_row.addWidget(btn)
        btn_row.addStretch()
        commits_layout.addLayout(btn_row)

        splitter.addWidget(commits_widget)

        # Set initial splitter sizes (40% tags, 60% commits)
        splitter.setSizes([300, 450])
        layout.addWidget(splitter)

        # Status
        self.status_label = QLabel("")
        self.status_label.setProperty("cssClass", "status")
        layout.addWidget(self.status_label)

        # ── Signals ──
        self.btn_refresh_envs.clicked.connect(self._refresh_envs)
        self.btn_fetch_tags.clicked.connect(self._fetch_remote_tags)
        self.btn_install_tag.clicked.connect(self._on_install_tag)
        self.btn_load_commits.clicked.connect(self._on_load_commits)
        self.btn_switch.clicked.connect(self._on_switch)
        self.btn_update.clicked.connect(self._on_update)

        self.retranslate()
        self._refresh_envs()

    def retranslate(self):
        """Update all visible text to the current language."""
        self.lbl_environment.setText(t("version_environment"))
        self.lbl_target.setText(t("version_target"))
        self.btn_refresh_envs.setText(t("env_refresh"))
        self.lbl_tags_title.setText(t("version_available_tags"))
        self.btn_fetch_tags.setText(t("version_refresh_versions"))
        self.tags_table.setHorizontalHeaderLabels([
            t("version_tag").rstrip(":").rstrip("："),
            t("version_col_hash"),
        ])
        self.btn_install_tag.setText(t("version_install_tag"))
        self.btn_load_commits.setText(t("version_load"))
        self.btn_switch.setText(t("version_switch"))
        self.btn_update.setText(t("version_update"))
        self.commits_table.setHorizontalHeaderLabels([
            t("version_col_hash"),
            t("version_col_message"),
            t("version_col_author"),
            t("version_col_date"),
        ])

    # ── Remote Tags ──

    def _fetch_remote_tags(self):
        self.btn_fetch_tags.setEnabled(False)
        self.tags_status.setText(t("version_fetching"))
        worker = Worker(self.controller.list_remote_versions)
        worker.finished.connect(self._on_tags_fetched)
        worker.error.connect(lambda e: (
            self.tags_status.setText(t("version_fetch_failed").format(e)),
            self.btn_fetch_tags.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()

    def _on_tags_fetched(self, versions):
        self.btn_fetch_tags.setEnabled(True)
        tags = versions.get("tags", [])
        self.tags_table.setRowCount(len(tags))
        for i, tag in enumerate(tags):
            self.tags_table.setItem(i, 0, QTableWidgetItem(tag["name"]))
            self.tags_table.setItem(i, 1, QTableWidgetItem(tag["hash"]))
        self.tags_status.setText(t("version_tag_count").format(len(tags)))

    def _on_install_tag(self):
        """Switch the current environment's ComfyUI to the selected tag."""
        env_name = self.env_combo.currentText()
        if not env_name:
            QMessageBox.information(self, t("info"), t("launch_select_env"))
            return
        row = self.tags_table.currentRow()
        if row < 0:
            QMessageBox.information(self, t("info"), t("version_select_commit"))
            return
        tag_name = self.tags_table.item(row, 0).text()
        reply = QMessageBox.question(
            self, t("confirm"), t("version_confirm_switch").format(tag_name)
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(t("version_switching"))
        self.btn_install_tag.setEnabled(False)
        target = self.target_combo.currentText()
        worker = Worker(self.controller.switch_version, env_name, tag_name, target)
        worker.finished.connect(lambda _: (
            self.status_label.setText(t("version_switched")),
            self.btn_install_tag.setEnabled(True),
        ))
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_install_tag.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()

    # ── Local Commits (keep existing logic) ──

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

    def _on_load_commits(self):
        env_name = self.env_combo.currentText()
        target = self.target_combo.currentText()
        if not env_name:
            QMessageBox.information(self, t("info"), t("launch_select_env"))
            return
        self.status_label.setText(t("version_loading"))
        self.btn_load_commits.setEnabled(False)
        worker = Worker(self.controller.list_commits, env_name, target)
        worker.finished.connect(self._on_commits_loaded)
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_load_commits.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()

    def _on_commits_loaded(self, commits):
        self.btn_load_commits.setEnabled(True)
        self.commits_table.setRowCount(len(commits))
        for i, c in enumerate(commits):
            self.commits_table.setItem(i, 0, QTableWidgetItem(c.get("hash", "")[:7]))
            self.commits_table.setItem(i, 1, QTableWidgetItem(c.get("message", "")))
            self.commits_table.setItem(i, 2, QTableWidgetItem(c.get("author", "")))
            self.commits_table.setItem(i, 3, QTableWidgetItem(c.get("date", "")))
        self.status_label.setText(f"{len(commits)} commit(s) loaded.")

    def _on_switch(self):
        env_name = self.env_combo.currentText()
        target = self.target_combo.currentText()
        row = self.commits_table.currentRow()
        if not env_name:
            QMessageBox.information(self, t("info"), t("launch_select_env"))
            return
        if row < 0:
            QMessageBox.information(self, t("info"), t("version_select_commit"))
            return
        ref = self.commits_table.item(row, 0).text()
        reply = QMessageBox.question(
            self, t("confirm"), t("version_confirm_switch").format(ref)
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(t("version_switching"))
        self.btn_switch.setEnabled(False)
        worker = Worker(self.controller.switch_version, env_name, ref, target)
        worker.finished.connect(lambda _: (
            self.status_label.setText(t("version_switched")),
            self.btn_switch.setEnabled(True),
        ))
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_switch.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()

    def _on_update(self):
        env_name = self.env_combo.currentText()
        if not env_name:
            QMessageBox.information(self, t("info"), t("launch_select_env"))
            return
        reply = QMessageBox.question(
            self, t("confirm"), t("version_confirm_update")
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(t("version_updating"))
        self.btn_update.setEnabled(False)
        worker = Worker(self.controller.update_comfyui, env_name)
        worker.finished.connect(lambda _: (
            self.status_label.setText(t("version_updated")),
            self.btn_update.setEnabled(True),
        ))
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_update.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()
