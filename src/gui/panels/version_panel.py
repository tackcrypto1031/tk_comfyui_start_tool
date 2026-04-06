"""Version control panel for ComfyUI and custom nodes."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem,
    QComboBox, QHeaderView, QMessageBox,
)

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
        self._selected_ref = None

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

        # ── Remote Tags Section ──
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
        layout.addLayout(tags_header)

        self.tags_table = QTableWidget()
        self.tags_table.setColumnCount(2)
        self.tags_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tags_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tags_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tags_table.setAlternatingRowColors(True)
        layout.addWidget(self.tags_table)

        # ── Action Buttons ──
        btn_row = QHBoxLayout()
        self.btn_switch = QPushButton()
        self.btn_switch.setProperty("cssClass", "primary")
        self.btn_update = QPushButton()
        btn_row.addWidget(self.btn_switch)
        btn_row.addWidget(self.btn_update)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Status
        self.status_label = QLabel("")
        self.status_label.setProperty("cssClass", "status")
        layout.addWidget(self.status_label)

        # ── Signals ──
        self.btn_refresh_envs.clicked.connect(self._refresh_envs)
        self.btn_fetch_tags.clicked.connect(self._fetch_remote_tags)
        self.btn_switch.clicked.connect(self._on_switch)
        self.btn_update.clicked.connect(self._on_update)
        self.tags_table.currentCellChanged.connect(self._on_tag_selected)

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
        self.btn_switch.setText(t("version_switch"))
        self.btn_update.setText(t("version_update"))

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

    def _on_tag_selected(self, row, _col, _prev_row, _prev_col):
        """When a tag row is selected, update the selection."""
        if row >= 0:
            item = self.tags_table.item(row, 0)
            if item:
                self._selected_ref = item.text()

    # ── Environment ──

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

    # ── Actions ──

    def _on_switch(self):
        env_name = self.env_combo.currentText()
        target = self.target_combo.currentText()
        if not env_name:
            QMessageBox.information(self, t("info"), t("launch_select_env"))
            return
        if not self._selected_ref:
            QMessageBox.information(self, t("info"), t("version_select_commit"))
            return
        ref = self._selected_ref
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
