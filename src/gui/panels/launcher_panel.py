"""Launcher panel — start/stop ComfyUI and display logs."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSpinBox, QComboBox, QPlainTextEdit, QGroupBox,
)
from PySide6.QtCore import Qt, QTimer

from src.core.env_manager import EnvManager
from src.core.comfyui_launcher import ComfyUILauncher
from src.gui.workers import Worker
from src.gui.i18n import t


class LauncherPanel(QWidget):
    """Panel for launching, stopping, and monitoring ComfyUI instances."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.env_manager = EnvManager(config)
        self.launcher = ComfyUILauncher(config)
        self._workers = []  # Keep references to prevent GC

        layout = QVBoxLayout(self)

        # Environment selection group
        self.env_group = QGroupBox()
        env_layout = QHBoxLayout(self.env_group)
        self.env_combo = QComboBox()
        self.env_combo.setMinimumWidth(200)
        self.btn_refresh_envs = QPushButton()
        self.btn_refresh_envs.clicked.connect(self._load_environments)
        self.lbl_environment = QLabel()
        env_layout.addWidget(self.lbl_environment)
        env_layout.addWidget(self.env_combo)
        env_layout.addWidget(self.btn_refresh_envs)
        env_layout.addStretch()
        layout.addWidget(self.env_group)

        # Launch controls group
        self.controls_group = QGroupBox("Controls")
        controls_layout = QHBoxLayout(self.controls_group)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(config.get("default_port", 8188))
        self.btn_start = QPushButton()
        self.btn_start.setProperty("cssClass", "primary")
        self.btn_stop = QPushButton()
        self.btn_stop.setProperty("cssClass", "danger")
        self.btn_stop.setEnabled(False)
        self.lbl_port = QLabel()
        controls_layout.addWidget(self.lbl_port)
        controls_layout.addWidget(self.port_spin)
        controls_layout.addWidget(self.btn_start)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addStretch()
        layout.addWidget(self.controls_group)

        # Status display
        self.status_label = QLabel()
        self.status_label.setProperty("cssClass", "status")
        layout.addWidget(self.status_label)

        # Log output
        self.log_group = QGroupBox()
        log_layout = QVBoxLayout(self.log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000)
        log_layout.addWidget(self.log_view)
        layout.addWidget(self.log_group)

        # Connect signals
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)

        # Status poller (every 5 seconds)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(5000)
        self._poll_timer.timeout.connect(self._poll_status)
        self._poll_timer.start()

        # Apply translations then load
        self.retranslate()
        self._load_environments()

    def retranslate(self):
        """Update all visible text to the current language."""
        self.env_group.setTitle(t("launch_environment").rstrip(":").rstrip("："))
        self.lbl_environment.setText(t("launch_environment"))
        self.btn_refresh_envs.setText(t("launch_refresh"))
        self.lbl_port.setText(t("launch_port"))
        self.btn_start.setText(t("launch_start"))
        self.btn_stop.setText(t("launch_stop"))
        self.log_group.setTitle(t("launch_log"))
        # Update status label only if it currently shows the stopped text
        current = self.status_label.text()
        # Re-render stopped state using current language
        if not current or "running" not in current.lower() and "運行" not in current:
            self.status_label.setText(f"{t('launch_status')} {t('launch_status_stopped')}")

    def _load_environments(self):
        worker = Worker(self.env_manager.list_environments)
        worker.finished.connect(self._on_envs_loaded)
        worker.error.connect(lambda e: self._append_log(f"{t('error')}: {e}"))
        self._workers.append(worker)
        worker.start()

    def _on_envs_loaded(self, envs):
        current = self.env_combo.currentText()
        self.env_combo.clear()
        for env in envs:
            self.env_combo.addItem(env.name)
        # Restore previous selection if still present
        idx = self.env_combo.findText(current)
        if idx >= 0:
            self.env_combo.setCurrentIndex(idx)

    def _on_start(self):
        env_name = self.env_combo.currentText()
        if not env_name:
            self._append_log(t("launch_select_env"))
            return
        port = self.port_spin.value()
        self.btn_start.setEnabled(False)
        self._append_log(f"{t('launch_starting')} ({env_name}:{port})")

        worker = Worker(self.launcher.start, env_name, port)
        worker.finished.connect(self._on_started)
        worker.error.connect(self._on_start_error)
        self._workers.append(worker)
        worker.start()

    def _on_started(self, info: dict):
        pid = info['pid']
        port = info['port']
        self._append_log(
            f"Started: env={info['env_name']}  pid={pid}  port={port}"
        )
        self.status_label.setText(
            f"{t('launch_status')} {t('launch_status_running').format(pid, port)}"
        )
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _on_start_error(self, message: str):
        self._append_log(f"Start failed: {message}")
        self.btn_start.setEnabled(True)

    def _on_stop(self):
        env_name = self.env_combo.currentText()
        if not env_name:
            return
        self.btn_stop.setEnabled(False)
        self._append_log(t("launch_stopping"))

        worker = Worker(self.launcher.stop, env_name)
        worker.finished.connect(self._on_stopped)
        worker.error.connect(self._on_stop_error)
        self._workers.append(worker)
        worker.start()

    def _on_stopped(self, _):
        self._append_log(t("launch_stopped"))
        self.status_label.setText(f"{t('launch_status')} {t('launch_status_stopped')}")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _on_stop_error(self, message: str):
        self._append_log(f"Stop failed: {message}")
        self.btn_stop.setEnabled(True)

    def _poll_status(self):
        env_name = self.env_combo.currentText()
        if not env_name:
            return
        worker = Worker(self.launcher.get_status, env_name)
        worker.finished.connect(self._on_status_polled)
        worker.error.connect(lambda _: None)  # Silently ignore poll errors
        self._workers.append(worker)
        worker.start()

    def _on_status_polled(self, status: dict):
        state = status.get("status", "stopped")
        if state == "running":
            port = status.get("port", "?")
            pid = status.get("pid", "?")
            self.status_label.setText(
                f"{t('launch_status')} {t('launch_status_running').format(pid, port)}"
            )
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
        else:
            self.status_label.setText(f"{t('launch_status')} {t('launch_status_stopped')}")
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def _append_log(self, message: str):
        self.log_view.appendPlainText(message)
