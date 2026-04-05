"""Environment management panel."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QLineEdit,
    QLabel, QFormLayout, QDialogButtonBox, QMessageBox,
    QHeaderView, QComboBox, QRadioButton,
)
from PySide6.QtCore import Qt

from src.core.env_manager import EnvManager
from src.gui.workers import Worker
from src.gui.i18n import t


class CreateEnvDialog(QDialog):
    """Dialog for creating a new environment with version selection."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle(t("env_create_title"))
        self.setMinimumWidth(500)
        self._versions_cache = None
        self._workers = []

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Form section
        form = QFormLayout()
        form.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. production, dev-test")
        form.addRow(t("env_name"), self.name_input)

        # Version type selector (Branch vs Tag)
        version_type_layout = QHBoxLayout()
        self.radio_branch = QRadioButton(t("version_type_branch"))
        self.radio_tag = QRadioButton(t("version_type_tag"))
        self.radio_branch.setChecked(True)
        version_type_layout.addWidget(self.radio_branch)
        version_type_layout.addWidget(self.radio_tag)
        version_type_layout.addStretch()
        form.addRow(t("version_type"), version_type_layout)

        # Branch selector (shown when Branch is selected)
        self.branch_combo = QComboBox()
        self.branch_combo.setEditable(True)
        self.branch_combo.setEditText("master")
        self.branch_combo.setMinimumWidth(300)
        form.addRow(t("env_branch"), self.branch_combo)

        # Tag selector (shown when Tag is selected, hidden initially)
        self.tag_combo = QComboBox()
        self.tag_combo.setMinimumWidth(300)
        self.tag_label = QLabel(t("version_tag"))
        form.addRow(self.tag_label, self.tag_combo)
        self.tag_label.hide()
        self.tag_combo.hide()

        # Commit override (optional)
        self.commit_input = QLineEdit()
        self.commit_input.setPlaceholderText(t("env_commit_placeholder"))
        form.addRow(t("env_commit"), self.commit_input)

        layout.addLayout(form)

        # Fetch versions button + status
        fetch_row = QHBoxLayout()
        self.btn_fetch = QPushButton(t("env_fetch_versions"))
        self.btn_fetch.setProperty("cssClass", "primary")
        self.btn_fetch.style().unpolish(self.btn_fetch)
        self.btn_fetch.style().polish(self.btn_fetch)
        self.fetch_status = QLabel("")
        self.fetch_status.setProperty("cssClass", "status")
        fetch_row.addWidget(self.btn_fetch)
        fetch_row.addWidget(self.fetch_status)
        fetch_row.addStretch()
        layout.addLayout(fetch_row)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Signals
        self.radio_branch.toggled.connect(self._on_version_type_changed)
        self.radio_tag.toggled.connect(self._on_version_type_changed)
        self.btn_fetch.clicked.connect(self._fetch_versions)

        # Auto-fetch on open
        self._fetch_versions()

    def _on_version_type_changed(self):
        is_branch = self.radio_branch.isChecked()
        self.branch_combo.setVisible(is_branch)
        self.tag_combo.setVisible(not is_branch)
        self.tag_label.setVisible(not is_branch)
        # Find branch label in form layout parent
        parent_layout = self.branch_combo.parent().layout()
        if parent_layout:
            for i in range(parent_layout.rowCount()):
                label_item = parent_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                field_item = parent_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                if field_item and field_item.widget() == self.branch_combo:
                    if label_item and label_item.widget():
                        label_item.widget().setVisible(is_branch)
                    break

    def _fetch_versions(self):
        from src.core.version_controller import VersionController
        self.btn_fetch.setEnabled(False)
        self.fetch_status.setText(t("version_fetching"))
        controller = VersionController(self.config)

        worker = Worker(controller.list_remote_versions)
        worker.finished.connect(self._on_versions_fetched)
        worker.error.connect(self._on_fetch_error)
        self._workers.append(worker)
        worker.start()

    def _on_versions_fetched(self, versions):
        self._versions_cache = versions
        self.btn_fetch.setEnabled(True)

        # Populate branches
        self.branch_combo.clear()
        for branch in versions.get("branches", []):
            self.branch_combo.addItem(branch)
        # Select master/main as default
        for default in ["master", "main"]:
            idx = self.branch_combo.findText(default)
            if idx >= 0:
                self.branch_combo.setCurrentIndex(idx)
                break

        # Populate tags
        self.tag_combo.clear()
        tags = versions.get("tags", [])
        for tag in tags:
            self.tag_combo.addItem(f"{tag['name']}  ({tag['hash']})", tag["name"])

        count_info = t("version_branch_count").format(len(versions.get("branches", [])))
        count_info += " / " + t("version_tag_count").format(len(tags))
        self.fetch_status.setText(count_info)

    def _on_fetch_error(self, error_msg):
        self.btn_fetch.setEnabled(True)
        self.fetch_status.setText(t("version_fetch_failed").format(error_msg))

    def get_values(self):
        """Return (name, branch, commit) based on user selection."""
        name = self.name_input.text().strip()
        commit = self.commit_input.text().strip() or None

        if self.radio_tag.isChecked():
            # Tag mode: use selected tag as the commit ref
            tag_name = self.tag_combo.currentData()
            if tag_name:
                branch = "master"  # Clone master first, then checkout tag
                commit = tag_name
            else:
                branch = "master"
        else:
            # Branch mode
            branch = self.branch_combo.currentText().strip() or "master"

        return name, branch, commit


class CloneEnvDialog(QDialog):
    """Dialog for cloning an environment."""

    def __init__(self, source_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("env_clone_title"))
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        self.source_label = QLabel(source_name)
        self.name_input = QLineEdit(f"{source_name}-sandbox")

        layout.addRow(t("env_source"), self.source_label)
        layout.addRow(t("env_new_name"), self.name_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class EnvPanel(QWidget):
    """Environment management panel."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.manager = EnvManager(config)
        self._workers = []  # Keep references to prevent GC

        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_create = QPushButton()
        self.btn_clone = QPushButton()
        self.btn_delete = QPushButton()
        self.btn_refresh = QPushButton()
        self.btn_create.setProperty("cssClass", "primary")
        self.btn_delete.setProperty("cssClass", "danger")
        for btn in [self.btn_create, self.btn_clone, self.btn_delete, self.btn_refresh]:
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Environment table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Connect signals
        self.btn_create.clicked.connect(self._on_create)
        self.btn_clone.clicked.connect(self._on_clone)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(self.refresh_list)

        # Apply translations then load
        self.retranslate()
        self.refresh_list()

    def retranslate(self):
        """Update all visible text to the current language."""
        self.btn_create.setText(t("env_create"))
        self.btn_clone.setText(t("env_clone"))
        self.btn_delete.setText(t("env_delete"))
        self.btn_refresh.setText(t("env_refresh"))
        self.table.setHorizontalHeaderLabels([
            t("env_col_name"),
            t("env_col_branch"),
            t("env_col_commit"),
            t("env_col_sandbox"),
            t("env_col_created"),
        ])

    def refresh_list(self):
        self.status_label.setText(t("loading"))
        worker = Worker(self.manager.list_environments)
        worker.finished.connect(self._on_list_loaded)
        worker.error.connect(lambda e: self.status_label.setText(f"{t('error')}: {e}"))
        self._workers.append(worker)
        worker.start()

    def _on_list_loaded(self, envs):
        self.table.setRowCount(len(envs))
        for i, env in enumerate(envs):
            commit_short = env.comfyui_commit[:7] if env.comfyui_commit else ""
            created_short = env.created_at[:10] if env.created_at else ""
            self.table.setItem(i, 0, QTableWidgetItem(env.name))
            self.table.setItem(i, 1, QTableWidgetItem(env.comfyui_branch))
            self.table.setItem(i, 2, QTableWidgetItem(commit_short))
            self.table.setItem(i, 3, QTableWidgetItem(t("yes") if env.is_sandbox else ""))
            self.table.setItem(i, 4, QTableWidgetItem(created_short))
        self.status_label.setText(t("env_count").format(len(envs)))

    def _on_create(self):
        dialog = CreateEnvDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, branch, commit = dialog.get_values()
            if not name:
                return
            self.status_label.setText(t("env_creating").format(name))
            self.btn_create.setEnabled(False)
            worker = Worker(self.manager.create_environment, name, branch=branch, commit=commit)
            worker.finished.connect(
                lambda _: (self.refresh_list(), self.btn_create.setEnabled(True))
            )
            worker.error.connect(
                lambda e: (
                    QMessageBox.warning(self, t("error"), str(e)),
                    self.btn_create.setEnabled(True),
                )
            )
            self._workers.append(worker)
            worker.start()

    def _on_clone(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, t("info"), t("env_select_to_clone"))
            return
        source = self.table.item(row, 0).text()
        dialog = CloneEnvDialog(source, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.name_input.text().strip()
            if not new_name:
                return
            self.status_label.setText(t("env_cloning").format(source, new_name))
            worker = Worker(self.manager.clone_environment, source, new_name)
            worker.finished.connect(lambda _: self.refresh_list())
            worker.error.connect(lambda e: QMessageBox.warning(self, t("error"), str(e)))
            self._workers.append(worker)
            worker.start()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, t("info"), t("env_select_to_delete"))
            return
        name = self.table.item(row, 0).text()
        reply = QMessageBox.question(self, t("confirm"), t("env_confirm_delete").format(name))
        if reply == QMessageBox.StandardButton.Yes:
            self.status_label.setText(t("env_deleting").format(name))
            worker = Worker(self.manager.delete_environment, name, force=True)
            worker.finished.connect(lambda _: self.refresh_list())
            worker.error.connect(lambda e: QMessageBox.warning(self, t("error"), str(e)))
            self._workers.append(worker)
            worker.start()
