"""Tests for src/core/diagnostics.py"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.core.diagnostics import DiagnosticsManager, _extract_via_ast, _extract_via_regex


@pytest.fixture
def diag_manager(tmp_path):
    """Create a DiagnosticsManager with a temp environments directory."""
    config = {"environments_dir": str(tmp_path / "environments")}
    (tmp_path / "environments").mkdir()
    return DiagnosticsManager(config)


@pytest.fixture
def env_dir(tmp_path):
    """Create a minimal environment directory structure."""
    env = tmp_path / "environments" / "test_env"
    env.mkdir(parents=True)
    (env / "venv").mkdir()
    comfyui = env / "ComfyUI"
    comfyui.mkdir()
    (comfyui / "custom_nodes").mkdir()
    return env


class TestExtractViaAst:
    """Test AST-based NODE_CLASS_MAPPINGS extraction."""

    def test_simple_dict(self):
        code = '''
NODE_CLASS_MAPPINGS = {
    "MyNode": MyNodeClass,
    "OtherNode": OtherClass,
}
'''
        assert _extract_via_ast(code) == ["MyNode", "OtherNode"]

    def test_empty_dict(self):
        code = 'NODE_CLASS_MAPPINGS = {}'
        assert _extract_via_ast(code) == []

    def test_no_mapping(self):
        code = 'x = 1'
        assert _extract_via_ast(code) == []

    def test_dict_comprehension_returns_none(self):
        code = 'NODE_CLASS_MAPPINGS = {k: v for k, v in items}'
        assert _extract_via_ast(code) is None

    def test_syntax_error_returns_none(self):
        code = 'def broken(:'
        assert _extract_via_ast(code) is None

    def test_multiline_dict(self):
        code = '''
NODE_CLASS_MAPPINGS = {
    "NodeA": ClassA,
    "NodeB": ClassB,
    "NodeC": ClassC,
    "NodeD": ClassD,
}
'''
        result = _extract_via_ast(code)
        assert result == ["NodeA", "NodeB", "NodeC", "NodeD"]


class TestExtractViaRegex:
    """Test regex-based fallback extraction."""

    def test_simple_dict(self):
        code = '''NODE_CLASS_MAPPINGS = {"MyNode": MyClass, "Other": OtherClass}'''
        result = _extract_via_regex(code)
        assert "MyNode" in result
        assert "Other" in result

    def test_single_quotes(self):
        code = "NODE_CLASS_MAPPINGS = {'MyNode': MyClass}"
        result = _extract_via_regex(code)
        assert "MyNode" in result


class TestCheckDuplicateNodes:
    """Test duplicate node detection."""

    def test_no_duplicates(self, diag_manager, env_dir):
        # Create two packages with different node names
        pkg_a = env_dir / "ComfyUI" / "custom_nodes" / "pkg_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text(
            'NODE_CLASS_MAPPINGS = {"NodeA": ClassA}', encoding="utf-8"
        )
        pkg_b = env_dir / "ComfyUI" / "custom_nodes" / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text(
            'NODE_CLASS_MAPPINGS = {"NodeB": ClassB}', encoding="utf-8"
        )

        result = diag_manager.check_duplicate_nodes("test_env")
        assert result["status"] == "ok"
        assert result["duplicates"] == []

    def test_detects_duplicates(self, diag_manager, env_dir):
        # Create two packages with the same node name
        pkg_a = env_dir / "ComfyUI" / "custom_nodes" / "pkg_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text(
            'NODE_CLASS_MAPPINGS = {"DupeNode": ClassA}', encoding="utf-8"
        )
        pkg_b = env_dir / "ComfyUI" / "custom_nodes" / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text(
            'NODE_CLASS_MAPPINGS = {"DupeNode": ClassB}', encoding="utf-8"
        )

        result = diag_manager.check_duplicate_nodes("test_env")
        assert result["status"] == "warning"
        assert len(result["duplicates"]) == 1
        assert result["duplicates"][0]["node_name"] == "DupeNode"
        assert set(result["duplicates"][0]["packages"]) == {"pkg_a", "pkg_b"}

    def test_skips_disabled_packages(self, diag_manager, env_dir):
        pkg = env_dir / "ComfyUI" / "custom_nodes" / "pkg.disabled"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            'NODE_CLASS_MAPPINGS = {"Node": Class}', encoding="utf-8"
        )

        result = diag_manager.check_duplicate_nodes("test_env")
        assert result["status"] == "ok"
        assert result["duplicates"] == []

    def test_no_custom_nodes_dir(self, diag_manager, tmp_path):
        # Env with no custom_nodes directory
        env = tmp_path / "environments" / "empty_env"
        env.mkdir(parents=True)
        (env / "ComfyUI").mkdir()

        result = diag_manager.check_duplicate_nodes("empty_env")
        assert result["status"] == "ok"


class TestCheckDependencies:
    """Test dependency checking with mocked pip operations."""

    @patch("src.core.diagnostics.pip_ops")
    def test_all_deps_present(self, mock_pip, diag_manager, env_dir):
        mock_pip.freeze.return_value = {"torch": "2.7.0", "numpy": "1.26.0"}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_pip.run_pip.return_value = mock_result

        req_file = env_dir / "ComfyUI" / "requirements.txt"
        req_file.write_text("torch\nnumpy\n", encoding="utf-8")

        result = diag_manager.check_dependencies("test_env")
        assert result["status"] == "ok"

    @patch("src.core.diagnostics.pip_ops")
    def test_missing_dep(self, mock_pip, diag_manager, env_dir):
        mock_pip.freeze.return_value = {"torch": "2.7.0"}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_pip.run_pip.return_value = mock_result

        req_file = env_dir / "ComfyUI" / "requirements.txt"
        req_file.write_text("torch\nnumpy\n", encoding="utf-8")

        result = diag_manager.check_dependencies("test_env")
        assert result["status"] == "error"
        missing = [i for i in result["items"] if i["status"] == "missing"]
        assert len(missing) == 1
        assert missing[0]["package"] == "numpy"


class TestCheckConflicts:
    """Test conflict detection with mocked pip operations."""

    @patch("src.core.diagnostics.pip_ops")
    def test_no_conflicts(self, mock_pip, diag_manager, env_dir):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_pip.run_pip.return_value = mock_result
        mock_pip.freeze.return_value = {"torch": "2.7.0"}

        result = diag_manager.check_conflicts("test_env")
        assert result["status"] == "ok"
        assert result["conflicts"] == []

    @patch("src.core.diagnostics.pip_ops")
    def test_pip_check_finds_conflict(self, mock_pip, diag_manager, env_dir):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "pkg-a 1.0 requires pkg-b>=2.0, but you have pkg-b 1.5."
        mock_result.stderr = ""
        mock_pip.run_pip.return_value = mock_result
        mock_pip.freeze.return_value = {}

        result = diag_manager.check_conflicts("test_env")
        assert result["status"] == "warning"
        assert len(result["conflicts"]) >= 1

    @patch("src.core.diagnostics.pip_ops")
    def test_known_torch_xformers_conflict(self, mock_pip, diag_manager, env_dir):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_pip.run_pip.return_value = mock_result
        mock_pip.freeze.return_value = {
            "torch": "2.7.0+cu126",
            "xformers": "0.0.28",  # Wrong: 2.7.x needs 0.0.30
        }

        result = diag_manager.check_conflicts("test_env")
        assert result["status"] == "warning"
        torch_conflict = [c for c in result["conflicts"] if "xformers" in c["description"]]
        assert len(torch_conflict) == 1
