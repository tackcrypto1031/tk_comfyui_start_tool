"""Basic GUI widget instantiation tests for Phase 3A."""
import pytest
import sys
from unittest.mock import MagicMock, patch

# Attempt to import PySide6; skip entire module if unavailable
try:
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    PYSIDE6_AVAILABLE = True
except Exception:
    PYSIDE6_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PYSIDE6_AVAILABLE,
    reason="PySide6 not available",
)


# ---------------------------------------------------------------------------
# Worker tests (no display required for QThread)
# ---------------------------------------------------------------------------

class TestWorker:
    def test_worker_can_be_created(self):
        from src.gui.workers import Worker
        fn = lambda: 42
        w = Worker(fn)
        assert w is not None

    def test_worker_has_finished_signal(self):
        from src.gui.workers import Worker
        w = Worker(lambda: None)
        assert hasattr(w, "finished")

    def test_worker_has_error_signal(self):
        from src.gui.workers import Worker
        w = Worker(lambda: None)
        assert hasattr(w, "error")

    def test_worker_has_progress_signal(self):
        from src.gui.workers import Worker
        w = Worker(lambda: None)
        assert hasattr(w, "progress")

    def test_worker_stores_fn_and_args(self):
        from src.gui.workers import Worker
        fn = lambda x, y: x + y
        w = Worker(fn, 1, 2)
        assert w.fn is fn
        assert w.args == (1, 2)


# ---------------------------------------------------------------------------
# Dialog tests
# ---------------------------------------------------------------------------

class TestCreateEnvDialog:
    def _make_config(self):
        return {
            "comfyui_repo_url": "https://github.com/comfyanonymous/ComfyUI.git",
            "environments_dir": "./environments",
            "models_dir": "./models",
            "snapshots_dir": "./snapshots",
        }

    @patch("src.gui.panels.env_panel.Worker")
    def test_create_env_dialog_instantiates(self, mock_worker):
        from src.gui.panels.env_panel import CreateEnvDialog
        dlg = CreateEnvDialog(self._make_config())
        assert dlg is not None
        dlg.close()

    @patch("src.gui.panels.env_panel.Worker")
    def test_create_env_dialog_has_inputs(self, mock_worker):
        from src.gui.panels.env_panel import CreateEnvDialog
        dlg = CreateEnvDialog(self._make_config())
        assert dlg.name_input is not None
        assert dlg.branch_combo is not None
        assert dlg.commit_input is not None
        dlg.close()

    @patch("src.gui.panels.env_panel.Worker")
    def test_create_env_dialog_default_branch(self, mock_worker):
        from src.gui.panels.env_panel import CreateEnvDialog
        dlg = CreateEnvDialog(self._make_config())
        assert dlg.branch_combo.currentText() == "master"
        dlg.close()


class TestCloneEnvDialog:
    def test_clone_env_dialog_instantiates(self):
        from src.gui.panels.env_panel import CloneEnvDialog
        dlg = CloneEnvDialog("myenv")
        assert dlg is not None
        dlg.close()

    def test_clone_env_dialog_prepopulates_name(self):
        from src.gui.panels.env_panel import CloneEnvDialog
        dlg = CloneEnvDialog("myenv")
        assert dlg.name_input.text() == "myenv-sandbox"
        dlg.close()

    def test_clone_env_dialog_shows_source(self):
        from src.gui.panels.env_panel import CloneEnvDialog
        dlg = CloneEnvDialog("prod")
        assert dlg.source_label.text() == "prod"
        dlg.close()


# ---------------------------------------------------------------------------
# Panel tests (mock core operations so no real environments needed)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config(sample_config):
    return sample_config


class TestEnvPanel:
    def test_env_panel_instantiates(self, mock_config):
        with patch("src.gui.panels.env_panel.EnvManager") as MockMgr:
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.env_panel import EnvPanel
            panel = EnvPanel(mock_config)
            assert panel is not None
            panel.close()

    def test_env_panel_has_table(self, mock_config):
        with patch("src.gui.panels.env_panel.EnvManager") as MockMgr:
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.env_panel import EnvPanel
            panel = EnvPanel(mock_config)
            assert panel.table is not None
            assert panel.table.columnCount() == 5
            panel.close()

    def test_env_panel_has_buttons(self, mock_config):
        with patch("src.gui.panels.env_panel.EnvManager") as MockMgr:
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.env_panel import EnvPanel
            panel = EnvPanel(mock_config)
            assert panel.btn_create is not None
            assert panel.btn_clone is not None
            assert panel.btn_delete is not None
            assert panel.btn_refresh is not None
            panel.close()


class TestLauncherPanel:
    def test_launcher_panel_instantiates(self, mock_config):
        with patch("src.gui.panels.launcher_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.launcher_panel.ComfyUILauncher"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.launcher_panel import LauncherPanel
            panel = LauncherPanel(mock_config)
            assert panel is not None
            panel._poll_timer.stop()
            panel.close()

    def test_launcher_panel_has_controls(self, mock_config):
        with patch("src.gui.panels.launcher_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.launcher_panel.ComfyUILauncher"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.launcher_panel import LauncherPanel
            panel = LauncherPanel(mock_config)
            assert panel.btn_start is not None
            assert panel.btn_stop is not None
            assert panel.env_combo is not None
            assert panel.port_spin is not None
            panel._poll_timer.stop()
            panel.close()

    def test_launcher_panel_default_port(self, mock_config):
        with patch("src.gui.panels.launcher_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.launcher_panel.ComfyUILauncher"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.launcher_panel import LauncherPanel
            panel = LauncherPanel(mock_config)
            assert panel.port_spin.value() == mock_config.get("default_port", 8188)
            panel._poll_timer.stop()
            panel.close()

    def test_launcher_panel_has_log_view(self, mock_config):
        with patch("src.gui.panels.launcher_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.launcher_panel.ComfyUILauncher"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.launcher_panel import LauncherPanel
            panel = LauncherPanel(mock_config)
            assert panel.log_view is not None
            assert panel.log_view.isReadOnly()
            panel._poll_timer.stop()
            panel.close()


class TestMainWindow:
    def test_main_window_instantiates(self, mock_config):
        with patch("src.gui.panels.env_panel.EnvManager") as MockEnvMgr, \
             patch("src.gui.panels.launcher_panel.EnvManager") as MockLaunchMgr, \
             patch("src.gui.panels.launcher_panel.ComfyUILauncher"):
            MockEnvMgr.return_value.list_environments.return_value = []
            MockLaunchMgr.return_value.list_environments.return_value = []
            from src.gui.main_window import MainWindow
            win = MainWindow(mock_config)
            assert win is not None
            win.close()

    def test_main_window_title(self, mock_config):
        with patch("src.gui.panels.env_panel.EnvManager") as MockEnvMgr, \
             patch("src.gui.panels.launcher_panel.EnvManager") as MockLaunchMgr, \
             patch("src.gui.panels.launcher_panel.ComfyUILauncher"):
            MockEnvMgr.return_value.list_environments.return_value = []
            MockLaunchMgr.return_value.list_environments.return_value = []
            from src.gui.main_window import MainWindow
            win = MainWindow(mock_config)
            assert win.windowTitle() == "塔克ComfyUI啟動器"
            win.close()

    def test_main_window_has_sidebar_and_stack(self, mock_config):
        with patch("src.gui.panels.env_panel.EnvManager") as MockEnvMgr, \
             patch("src.gui.panels.launcher_panel.EnvManager") as MockLaunchMgr, \
             patch("src.gui.panels.launcher_panel.ComfyUILauncher"):
            MockEnvMgr.return_value.list_environments.return_value = []
            MockLaunchMgr.return_value.list_environments.return_value = []
            from src.gui.main_window import MainWindow
            win = MainWindow(mock_config)
            assert win.sidebar is not None
            assert win.stack is not None
            win.close()

    def test_main_window_update_status(self, mock_config):
        with patch("src.gui.panels.env_panel.EnvManager") as MockEnvMgr, \
             patch("src.gui.panels.launcher_panel.EnvManager") as MockLaunchMgr, \
             patch("src.gui.panels.launcher_panel.ComfyUILauncher"):
            MockEnvMgr.return_value.list_environments.return_value = []
            MockLaunchMgr.return_value.list_environments.return_value = []
            from src.gui.main_window import MainWindow
            win = MainWindow(mock_config)
            win.update_status("Test message")
            assert win.statusBar().currentMessage() == "Test message"
            win.close()
