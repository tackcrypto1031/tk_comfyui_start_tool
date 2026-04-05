"""Snapshot management panel."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem,
    QComboBox, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt

from src.core.env_manager import EnvManager
from src.core.snapshot_manager import SnapshotManager
from src.gui.workers import Worker
from src.gui.i18n import t


class SnapshotPanel(QWidget):
    """Snapshot management panel for creating and restoring environment snapshots."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.manager = EnvManager(config)
        self.snapshot_manager = SnapshotManager(config)
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

        # Snapshot table
        self.snapshot_table = QTableWidget()
        self.snapshot_table.setColumnCount(4)
        self.snapshot_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.snapshot_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.snapshot_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.snapshot_table.setAlternatingRowColors(True)
        layout.addWidget(self.snapshot_table)

        # Action buttons
        btn_row = QHBoxLayout()
        self.btn_load = QPushButton()
        self.btn_create = QPushButton()
        self.btn_create.setProperty("cssClass", "primary")
        self.btn_restore = QPushButton()
        self.btn_delete = QPushButton()
        self.btn_delete.setProperty("cssClass", "danger")
        for btn in [self.btn_load, self.btn_create, self.btn_restore, self.btn_delete]:
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Status
        self.status_label = QLabel("")
        self.status_label.setProperty("cssClass", "status")
        layout.addWidget(self.status_label)

        # Signals
        self.btn_refresh_envs.clicked.connect(self._refresh_envs)
        self.btn_load.clicked.connect(self._on_load_snapshots)
        self.btn_create.clicked.connect(self._on_create)
        self.btn_restore.clicked.connect(self._on_restore)
        self.btn_delete.clicked.connect(self._on_delete)

        self.retranslate()
        self._refresh_envs()

    def retranslate(self):
        """Update all visible text to the current language."""
        self.lbl_environment.setText(t("snapshot_environment"))
        self.btn_refresh_envs.setText(t("snapshot_refresh"))
        self.btn_load.setText(t("loading").replace("...", ""))
        self.btn_create.setText(t("snapshot_create"))
        self.btn_restore.setText(t("snapshot_restore"))
        self.btn_delete.setText(t("snapshot_delete"))
        self.snapshot_table.setHorizontalHeaderLabels([
            t("snapshot_col_id"),
            t("snapshot_col_trigger"),
            t("snapshot_col_commit"),
            t("snapshot_col_created"),
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

    def _on_load_snapshots(self):
        env_name = self.env_combo.currentText()
        if not env_name:
            QMessageBox.information(self, t("info"), t("launch_select_env"))
            return
        self.status_label.setText(t("loading"))
        self.btn_load.setEnabled(False)
        worker = Worker(self.snapshot_manager.list_snapshots, env_name)
        worker.finished.connect(self._on_snapshots_loaded)
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_load.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()

    def _on_snapshots_loaded(self, snapshots):
        self.btn_load.setEnabled(True)
        self.snapshot_table.setRowCount(len(snapshots))
        for i, snap in enumerate(snapshots):
            self.snapshot_table.setItem(i, 0, QTableWidgetItem(snap.id))
            self.snapshot_table.setItem(i, 1, QTableWidgetItem(snap.trigger))
            commit_short = snap.comfyui_commit[:7] if snap.comfyui_commit else ""
            self.snapshot_table.setItem(i, 2, QTableWidgetItem(commit_short))
            created_short = snap.created_at[:19] if snap.created_at else ""
            self.snapshot_table.setItem(i, 3, QTableWidgetItem(created_short))
        self.status_label.setText(t("snapshot_count").format(len(snapshots)))

    def _on_create(self):
        env_name = self.env_combo.currentText()
        if not env_name:
            QMessageBox.information(self, t("info"), t("launch_select_env"))
            return
        self.status_label.setText(t("snapshot_creating"))
        self.btn_create.setEnabled(False)
        worker = Worker(self.snapshot_manager.create_snapshot, env_name, "manual")
        worker.finished.connect(lambda snap: (
            self.status_label.setText(t("snapshot_created").format(snap.id if hasattr(snap, 'id') else '')),
            self.btn_create.setEnabled(True),
            self._on_load_snapshots(),
        ))
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_create.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()

    def _on_restore(self):
        env_name = self.env_combo.currentText()
        row = self.snapshot_table.currentRow()
        if not env_name:
            QMessageBox.information(self, t("info"), t("launch_select_env"))
            return
        if row < 0:
            QMessageBox.information(self, t("info"), t("snapshot_select_to_restore"))
            return
        snap_id = self.snapshot_table.item(row, 0).text()
        reply = QMessageBox.question(
            self, t("confirm"), t("snapshot_confirm_restore").format(snap_id)
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(t("snapshot_restoring"))
        self.btn_restore.setEnabled(False)
        worker = Worker(self.snapshot_manager.restore_snapshot, env_name, snap_id)
        worker.finished.connect(lambda _: (
            self.status_label.setText(t("snapshot_restored").format(snap_id)),
            self.btn_restore.setEnabled(True),
        ))
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_restore.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()

    def _on_delete(self):
        env_name = self.env_combo.currentText()
        row = self.snapshot_table.currentRow()
        if not env_name:
            QMessageBox.information(self, t("info"), t("launch_select_env"))
            return
        if row < 0:
            QMessageBox.information(self, t("info"), t("snapshot_select_to_delete"))
            return
        snap_id = self.snapshot_table.item(row, 0).text()
        reply = QMessageBox.question(self, t("confirm"), t("snapshot_confirm_delete").format(snap_id))
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(t("snapshot_deleted"))
        self.btn_delete.setEnabled(False)
        worker = Worker(self.snapshot_manager.delete_snapshot, env_name, snap_id)
        worker.finished.connect(lambda _: (
            self.status_label.setText(t("snapshot_deleted")),
            self.btn_delete.setEnabled(True),
            self._on_load_snapshots(),
        ))
        worker.error.connect(lambda e: (
            self.status_label.setText(f"{t('error')}: {e}"),
            self.btn_delete.setEnabled(True),
        ))
        self._workers.append(worker)
        worker.start()
