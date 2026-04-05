"""GUI panel instantiation tests for Phase 3B panels."""
import pytest
from unittest.mock import MagicMock, patch

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


@pytest.fixture
def mock_config(sample_config):
    return sample_config


# ---------------------------------------------------------------------------
# PluginPanel tests
# ---------------------------------------------------------------------------

class TestPluginPanel:
    def test_plugin_panel_instantiates(self, mock_config):
        with patch("src.gui.panels.plugin_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.plugin_panel.ConflictAnalyzer"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.plugin_panel import PluginPanel
            panel = PluginPanel(mock_config)
            assert panel is not None
            panel.close()

    def test_plugin_panel_has_env_combo(self, mock_config):
        with patch("src.gui.panels.plugin_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.plugin_panel.ConflictAnalyzer"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.plugin_panel import PluginPanel
            panel = PluginPanel(mock_config)
            assert panel.env_combo is not None
            panel.close()

    def test_plugin_panel_has_conflict_table(self, mock_config):
        with patch("src.gui.panels.plugin_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.plugin_panel.ConflictAnalyzer"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.plugin_panel import PluginPanel
            panel = PluginPanel(mock_config)
            assert panel.conflict_table is not None
            assert panel.conflict_table.columnCount() == 5
            panel.close()

    def test_plugin_panel_has_analyze_button(self, mock_config):
        with patch("src.gui.panels.plugin_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.plugin_panel.ConflictAnalyzer"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.plugin_panel import PluginPanel
            panel = PluginPanel(mock_config)
            assert panel.btn_analyze is not None
            assert panel.url_input is not None
            panel.close()

    def test_plugin_panel_refresh_envs_callable(self, mock_config):
        with patch("src.gui.panels.plugin_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.plugin_panel.ConflictAnalyzer"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.plugin_panel import PluginPanel
            panel = PluginPanel(mock_config)
            # Should not raise
            panel._refresh_envs()
            panel.close()


# ---------------------------------------------------------------------------
# VersionPanel tests
# ---------------------------------------------------------------------------

class TestVersionPanel:
    def test_version_panel_instantiates(self, mock_config):
        with patch("src.gui.panels.version_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.version_panel.VersionController"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.version_panel import VersionPanel
            panel = VersionPanel(mock_config)
            assert panel is not None
            panel.close()

    def test_version_panel_has_env_combo(self, mock_config):
        with patch("src.gui.panels.version_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.version_panel.VersionController"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.version_panel import VersionPanel
            panel = VersionPanel(mock_config)
            assert panel.env_combo is not None
            panel.close()

    def test_version_panel_has_commits_table(self, mock_config):
        with patch("src.gui.panels.version_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.version_panel.VersionController"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.version_panel import VersionPanel
            panel = VersionPanel(mock_config)
            assert panel.commits_table is not None
            assert panel.commits_table.columnCount() == 4
            panel.close()

    def test_version_panel_has_action_buttons(self, mock_config):
        with patch("src.gui.panels.version_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.version_panel.VersionController"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.version_panel import VersionPanel
            panel = VersionPanel(mock_config)
            assert panel.btn_load_commits is not None
            assert panel.btn_switch is not None
            assert panel.btn_update is not None
            panel.close()


# ---------------------------------------------------------------------------
# SnapshotPanel tests
# ---------------------------------------------------------------------------

class TestSnapshotPanel:
    def test_snapshot_panel_instantiates(self, mock_config):
        with patch("src.gui.panels.snapshot_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.snapshot_panel.SnapshotManager"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.snapshot_panel import SnapshotPanel
            panel = SnapshotPanel(mock_config)
            assert panel is not None
            panel.close()

    def test_snapshot_panel_has_env_combo(self, mock_config):
        with patch("src.gui.panels.snapshot_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.snapshot_panel.SnapshotManager"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.snapshot_panel import SnapshotPanel
            panel = SnapshotPanel(mock_config)
            assert panel.env_combo is not None
            panel.close()

    def test_snapshot_panel_has_snapshot_table(self, mock_config):
        with patch("src.gui.panels.snapshot_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.snapshot_panel.SnapshotManager"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.snapshot_panel import SnapshotPanel
            panel = SnapshotPanel(mock_config)
            assert panel.snapshot_table is not None
            assert panel.snapshot_table.columnCount() == 4
            panel.close()

    def test_snapshot_panel_has_action_buttons(self, mock_config):
        with patch("src.gui.panels.snapshot_panel.EnvManager") as MockMgr, \
             patch("src.gui.panels.snapshot_panel.SnapshotManager"):
            MockMgr.return_value.list_environments.return_value = []
            from src.gui.panels.snapshot_panel import SnapshotPanel
            panel = SnapshotPanel(mock_config)
            assert panel.btn_create is not None
            assert panel.btn_restore is not None
            assert panel.btn_delete is not None
            assert panel.btn_load is not None
            panel.close()
