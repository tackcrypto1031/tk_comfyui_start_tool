"""Tests for ConflictAnalyzer — 6-step conflict analysis engine."""
import ast
import json
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.conflict_analyzer import ConflictAnalyzer
from src.models.conflict_report import Conflict, ConflictReport, RiskLevel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def analyzer(sample_config):
    return ConflictAnalyzer(sample_config)


@pytest.fixture
def plugin_dir(tmp_path):
    """Return a temp directory representing a plugin."""
    d = tmp_path / "my_plugin"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# TestExtractRequirements
# ---------------------------------------------------------------------------

class TestExtractRequirements:
    def test_returns_empty_when_no_file(self, analyzer, plugin_dir):
        assert analyzer.extract_requirements(plugin_dir) == []

    def test_parses_simple_requirements(self, analyzer, plugin_dir):
        (plugin_dir / "requirements.txt").write_text("torch==2.3.1\nnumpy>=1.24\n")
        result = analyzer.extract_requirements(plugin_dir)
        assert "torch==2.3.1" in result
        assert "numpy>=1.24" in result

    def test_skips_comments(self, analyzer, plugin_dir):
        (plugin_dir / "requirements.txt").write_text("# comment\ntorch==2.3.1\n")
        result = analyzer.extract_requirements(plugin_dir)
        assert len(result) == 1
        assert result[0] == "torch==2.3.1"

    def test_skips_dash_lines(self, analyzer, plugin_dir):
        (plugin_dir / "requirements.txt").write_text("-r base.txt\ntorch==2.3.1\n")
        result = analyzer.extract_requirements(plugin_dir)
        assert result == ["torch==2.3.1"]

    def test_skips_blank_lines(self, analyzer, plugin_dir):
        (plugin_dir / "requirements.txt").write_text("\ntorch==2.3.1\n\nnumpy\n")
        result = analyzer.extract_requirements(plugin_dir)
        assert result == ["torch==2.3.1", "numpy"]


# ---------------------------------------------------------------------------
# TestExtractInstallPyDeps
# ---------------------------------------------------------------------------

class TestExtractInstallPyDeps:
    def _write_install(self, plugin_dir, code):
        p = plugin_dir / "install.py"
        p.write_text(textwrap.dedent(code))
        return str(p)

    def test_subprocess_run_pip_install(self, analyzer, plugin_dir):
        path = self._write_install(plugin_dir, """
            import subprocess
            subprocess.run(["pip", "install", "package==1.0"])
        """)
        result = analyzer.extract_install_py_deps(path)
        assert "package==1.0" in result

    def test_subprocess_check_call_pip_install(self, analyzer, plugin_dir):
        path = self._write_install(plugin_dir, """
            import subprocess
            subprocess.check_call(["pip", "install", "some_lib>=2.0"])
        """)
        result = analyzer.extract_install_py_deps(path)
        assert "some_lib>=2.0" in result

    def test_os_system_pip_install(self, analyzer, plugin_dir):
        path = self._write_install(plugin_dir, """
            import os
            os.system("pip install mypackage==3.5")
        """)
        result = analyzer.extract_install_py_deps(path)
        assert "mypackage==3.5" in result

    def test_subprocess_run_with_flag_skipped(self, analyzer, plugin_dir):
        path = self._write_install(plugin_dir, """
            import subprocess
            subprocess.run(["pip", "install", "-r", "requirements.txt"])
        """)
        result = analyzer.extract_install_py_deps(path)
        # -r flag token skipped; requirements.txt is not a package name we'd collect
        # but the parser should not crash
        assert isinstance(result, list)

    def test_multiple_packages_in_subprocess(self, analyzer, plugin_dir):
        path = self._write_install(plugin_dir, """
            import subprocess
            subprocess.run(["pip", "install", "pkgA==1.0", "pkgB==2.0"])
        """)
        result = analyzer.extract_install_py_deps(path)
        assert "pkgA==1.0" in result
        assert "pkgB==2.0" in result

    def test_dynamic_pattern_returns_no_crash(self, analyzer, plugin_dir):
        path = self._write_install(plugin_dir, """
            import subprocess
            packages = ["torch", "numpy"]
            for pkg in packages:
                subprocess.run(["pip", "install", pkg])
        """)
        # dynamic variable — should not crash; may return partial or empty
        result = analyzer.extract_install_py_deps(path)
        assert isinstance(result, list)

    def test_syntax_error_returns_empty(self, analyzer, plugin_dir):
        p = plugin_dir / "install.py"
        p.write_text("def broken(:\n    pass\n")
        result = analyzer.extract_install_py_deps(str(p))
        assert result == []

    def test_os_system_no_match_returns_empty(self, analyzer, plugin_dir):
        path = self._write_install(plugin_dir, """
            import os
            os.system("echo hello")
        """)
        result = analyzer.extract_install_py_deps(path)
        assert result == []


# ---------------------------------------------------------------------------
# TestScanImports (extract_all_dependencies integration)
# ---------------------------------------------------------------------------

class TestExtractAllDependencies:
    def test_combines_requirements_and_install_py(self, analyzer, plugin_dir):
        (plugin_dir / "requirements.txt").write_text("torch==2.3.1\n")
        install = plugin_dir / "install.py"
        install.write_text('import subprocess\nsubprocess.run(["pip","install","numpy==1.26"])\n')
        result = analyzer.extract_all_dependencies(str(plugin_dir))
        assert "torch==2.3.1" in result
        assert "numpy==1.26" in result

    def test_deduplicates_entries(self, analyzer, plugin_dir):
        (plugin_dir / "requirements.txt").write_text("torch==2.3.1\ntorch==2.3.1\n")
        result = analyzer.extract_all_dependencies(str(plugin_dir))
        assert result.count("torch==2.3.1") == 1

    def test_no_install_py_only_requirements(self, analyzer, plugin_dir):
        (plugin_dir / "requirements.txt").write_text("safetensors==0.4.0\n")
        result = analyzer.extract_all_dependencies(str(plugin_dir))
        assert result == ["safetensors==0.4.0"]

    def test_empty_plugin_dir_returns_empty(self, analyzer, plugin_dir):
        result = analyzer.extract_all_dependencies(str(plugin_dir))
        assert result == []


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------

class TestDryRun:
    def _make_report(self, packages: dict) -> str:
        install_items = [
            {"metadata": {"name": k, "version": v}} for k, v in packages.items()
        ]
        return json.dumps({"install": install_items})

    def test_parses_dry_run_output(self, analyzer):
        report_json = self._make_report({"torch": "2.4.0", "numpy": "1.26.4"})
        mock_result = MagicMock()
        mock_result.stdout = report_json
        with patch("src.core.conflict_analyzer.pip_ops.run_pip", return_value=mock_result):
            result = analyzer.dry_run("/fake/venv", ["torch==2.4.0"])
        assert result.get("torch") == "2.4.0"
        assert result.get("numpy") == "1.26.4"

    def test_empty_requirements_returns_empty(self, analyzer):
        result = analyzer.dry_run("/fake/venv", [])
        assert result == {}

    def test_invalid_json_returns_empty(self, analyzer):
        mock_result = MagicMock()
        mock_result.stdout = "not json"
        with patch("src.core.conflict_analyzer.pip_ops.run_pip", return_value=mock_result):
            with pytest.raises(RuntimeError, match="Failed to parse pip dry-run report JSON"):
                analyzer.dry_run("/fake/venv", ["torch"])

    def test_nonzero_returncode_raises(self, analyzer):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "pip failed"
        with patch("src.core.conflict_analyzer.pip_ops.run_pip", return_value=mock_result):
            with pytest.raises(RuntimeError, match="pip dry-run failed"):
                analyzer.dry_run("/fake/venv", ["torch"])

    def test_keys_normalized_to_lowercase(self, analyzer):
        report_json = self._make_report({"Torch": "2.4.0"})
        mock_result = MagicMock()
        mock_result.stdout = report_json
        with patch("src.core.conflict_analyzer.pip_ops.run_pip", return_value=mock_result):
            result = analyzer.dry_run("/fake/venv", ["Torch"])
        assert "torch" in result


# ---------------------------------------------------------------------------
# TestCompareVersions
# ---------------------------------------------------------------------------

class TestCompareVersions:
    def test_detects_upgrade(self, analyzer):
        freeze = {"torch": "2.3.1"}
        dry = {"torch": "2.4.0"}
        conflicts = analyzer.compare_versions(freeze, dry)
        assert len(conflicts) == 1
        assert conflicts[0].change_type == "UPGRADE"
        assert conflicts[0].current_version == "2.3.1"
        assert conflicts[0].resolved_version == "2.4.0"

    def test_detects_downgrade(self, analyzer):
        freeze = {"torch": "2.4.0"}
        dry = {"torch": "2.3.1"}
        conflicts = analyzer.compare_versions(freeze, dry)
        assert conflicts[0].change_type == "DOWNGRADE"

    def test_detects_new_package(self, analyzer):
        freeze = {}
        dry = {"new_pkg": "1.0.0"}
        conflicts = analyzer.compare_versions(freeze, dry)
        assert conflicts[0].change_type == "NEW"
        assert conflicts[0].current_version == ""

    def test_no_conflict_when_versions_match(self, analyzer):
        freeze = {"torch": "2.3.1"}
        dry = {"torch": "2.3.1"}
        conflicts = analyzer.compare_versions(freeze, dry)
        assert conflicts == []

    def test_case_insensitive_matching(self, analyzer):
        freeze = {"Torch": "2.3.1"}
        dry = {"torch": "2.4.0"}
        conflicts = analyzer.compare_versions(freeze, dry)
        assert len(conflicts) == 1


# ---------------------------------------------------------------------------
# TestDetectCriticalConflicts
# ---------------------------------------------------------------------------

class TestDetectCriticalConflicts:
    def test_marks_torch_as_critical(self, analyzer):
        conflicts = [
            Conflict("torch", "2.3.1", "", "2.4.0", "UPGRADE", False, RiskLevel.GREEN)
        ]
        result = analyzer.detect_critical_conflicts(conflicts)
        assert result[0].is_critical is True

    def test_non_critical_package_not_marked(self, analyzer):
        conflicts = [
            Conflict("some_lib", "1.0", "", "2.0", "UPGRADE", False, RiskLevel.GREEN)
        ]
        result = analyzer.detect_critical_conflicts(conflicts)
        assert result[0].is_critical is False

    def test_numpy_is_critical(self, analyzer):
        conflicts = [
            Conflict("numpy", "1.24.0", "", "2.0.0", "UPGRADE", False, RiskLevel.GREEN)
        ]
        result = analyzer.detect_critical_conflicts(conflicts)
        assert result[0].is_critical is True

    def test_case_insensitive_critical_check(self, analyzer):
        conflicts = [
            Conflict("Torch", "2.3.1", "", "2.4.0", "UPGRADE", False, RiskLevel.GREEN)
        ]
        result = analyzer.detect_critical_conflicts(conflicts)
        assert result[0].is_critical is True


# ---------------------------------------------------------------------------
# TestRiskClassification
# ---------------------------------------------------------------------------

class TestRiskClassification:
    def test_no_conflicts_is_green(self, analyzer):
        assert analyzer.classify_risk([]) == RiskLevel.GREEN

    def test_new_package_is_green(self, analyzer):
        conflicts = [
            Conflict("new_pkg", "", "", "1.0.0", "NEW", False, RiskLevel.GREEN)
        ]
        result = analyzer.classify_risk(conflicts)
        assert result == RiskLevel.GREEN

    def test_non_critical_major_upgrade_is_high(self, analyzer):
        conflicts = [
            Conflict("some_lib", "1.5.0", "", "2.0.0", "UPGRADE", False, RiskLevel.GREEN)
        ]
        result = analyzer.classify_risk(conflicts)
        assert result == RiskLevel.HIGH

    def test_non_critical_minor_upgrade_is_yellow(self, analyzer):
        conflicts = [
            Conflict("some_lib", "1.4.0", "", "1.5.0", "UPGRADE", False, RiskLevel.GREEN)
        ]
        result = analyzer.classify_risk(conflicts)
        assert result == RiskLevel.YELLOW

    def test_critical_major_upgrade_is_critical(self, analyzer):
        conflicts = [
            Conflict("torch", "1.13.0", "", "2.0.0", "UPGRADE", True, RiskLevel.GREEN)
        ]
        result = analyzer.classify_risk(conflicts)
        assert result == RiskLevel.CRITICAL

    def test_critical_minor_upgrade_is_high(self, analyzer):
        conflicts = [
            Conflict("torch", "2.3.0", "", "2.4.0", "UPGRADE", True, RiskLevel.GREEN)
        ]
        result = analyzer.classify_risk(conflicts)
        assert result == RiskLevel.HIGH

    def test_critical_patch_upgrade_is_yellow(self, analyzer):
        conflicts = [
            Conflict("torch", "2.3.0", "", "2.3.1", "UPGRADE", True, RiskLevel.GREEN)
        ]
        result = analyzer.classify_risk(conflicts)
        assert result == RiskLevel.YELLOW

    def test_overall_risk_is_max_of_conflicts(self, analyzer):
        conflicts = [
            Conflict("pkg_a", "1.0.0", "", "1.1.0", "UPGRADE", False, RiskLevel.GREEN),
            Conflict("torch", "1.13.0", "", "2.0.0", "UPGRADE", True, RiskLevel.GREEN),
        ]
        result = analyzer.classify_risk(conflicts)
        assert result == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# TestSuggestCompatibleVersion
# ---------------------------------------------------------------------------

class TestSuggestCompatibleVersion:
    def test_analyze_returns_report_with_no_git_history(self, analyzer, plugin_dir, tmp_path):
        """analyze() should succeed even without git history."""
        # Setup env dir with venv
        env_dir = tmp_path / "environments" / "myenv"
        (env_dir / "venv").mkdir(parents=True)
        analyzer.environments_dir = tmp_path / "environments"

        (plugin_dir / "requirements.txt").write_text("torch==2.4.0\n")

        dry_report = json.dumps({"install": [{"metadata": {"name": "torch", "version": "2.4.0"}}]})
        mock_run = MagicMock()
        mock_run.stdout = dry_report
        mock_freeze = {"torch": "2.3.1", "numpy": "1.26.4"}

        with patch("src.core.conflict_analyzer.pip_ops.run_pip", return_value=mock_run), \
             patch("src.core.conflict_analyzer.pip_ops.freeze", return_value=mock_freeze):
            report = analyzer.analyze("myenv", str(plugin_dir))

        assert isinstance(report, ConflictReport)
        assert report.risk_level is not None


# ---------------------------------------------------------------------------
# TestGenerateReport
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_generate_recommendations_green(self, analyzer):
        recs = analyzer.generate_recommendations([], RiskLevel.GREEN)
        assert len(recs) >= 1
        assert any("安全" in r for r in recs)

    def test_generate_recommendations_yellow(self, analyzer):
        recs = analyzer.generate_recommendations([], RiskLevel.YELLOW)
        assert len(recs) >= 1

    def test_generate_recommendations_high_mentions_sandbox(self, analyzer):
        conflicts = [
            Conflict("torch", "2.3.1", "", "2.4.0", "UPGRADE", True, RiskLevel.HIGH)
        ]
        recs = analyzer.generate_recommendations(conflicts, RiskLevel.HIGH)
        combined = " ".join(recs)
        assert "沙箱" in combined or "sandbox" in combined.lower()

    def test_generate_recommendations_critical(self, analyzer):
        recs = analyzer.generate_recommendations([], RiskLevel.CRITICAL)
        combined = " ".join(recs)
        assert "沙箱" in combined or "sandbox" in combined.lower()

    def test_summary_no_conflicts(self, analyzer):
        s = analyzer._generate_summary([], RiskLevel.GREEN)
        assert "衝突" in s or s == "無衝突"

    def test_summary_with_critical_package(self, analyzer):
        conflicts = [
            Conflict("torch", "2.3.1", "", "2.4.0", "UPGRADE", True, RiskLevel.CRITICAL)
        ]
        s = analyzer._generate_summary(conflicts, RiskLevel.CRITICAL)
        assert "torch" in s

    def test_summary_non_critical_shows_count(self, analyzer):
        conflicts = [
            Conflict("pkg_a", "1.0", "", "2.0", "UPGRADE", False, RiskLevel.HIGH),
            Conflict("pkg_b", "1.0", "", "2.0", "UPGRADE", False, RiskLevel.HIGH),
        ]
        s = analyzer._generate_summary(conflicts, RiskLevel.HIGH)
        assert "2" in s


# ---------------------------------------------------------------------------
# TestAnalyze (full pipeline)
# ---------------------------------------------------------------------------

class TestAnalyze:
    def _setup_env(self, analyzer, tmp_path, env_name="testenv"):
        env_dir = tmp_path / "environments" / env_name
        (env_dir / "venv").mkdir(parents=True)
        analyzer.environments_dir = tmp_path / "environments"
        return env_dir

    def test_analyze_returns_conflict_report(self, analyzer, plugin_dir, tmp_path):
        self._setup_env(analyzer, tmp_path)
        (plugin_dir / "requirements.txt").write_text("numpy==2.0.0\n")

        dry_json = json.dumps({"install": [{"metadata": {"name": "numpy", "version": "2.0.0"}}]})
        mock_run = MagicMock(stdout=dry_json)
        mock_freeze = {"numpy": "1.26.4"}

        with patch("src.core.conflict_analyzer.pip_ops.run_pip", return_value=mock_run), \
             patch("src.core.conflict_analyzer.pip_ops.freeze", return_value=mock_freeze):
            report = analyzer.analyze("testenv", str(plugin_dir))

        assert isinstance(report, ConflictReport)
        assert report.plugin_name == plugin_dir.name
        assert report.plugin_repo == str(plugin_dir)

    def test_analyze_raises_when_env_not_found(self, analyzer, plugin_dir, tmp_path):
        analyzer.environments_dir = tmp_path / "environments"
        (tmp_path / "environments").mkdir(parents=True, exist_ok=True)
        with pytest.raises(FileNotFoundError):
            analyzer.analyze("nonexistent_env", str(plugin_dir))

    def test_analyze_green_when_no_changes(self, analyzer, plugin_dir, tmp_path):
        self._setup_env(analyzer, tmp_path)
        (plugin_dir / "requirements.txt").write_text("torch==2.3.1\n")

        dry_json = json.dumps({"install": [{"metadata": {"name": "torch", "version": "2.3.1"}}]})
        mock_run = MagicMock(stdout=dry_json)
        mock_freeze = {"torch": "2.3.1"}

        with patch("src.core.conflict_analyzer.pip_ops.run_pip", return_value=mock_run), \
             patch("src.core.conflict_analyzer.pip_ops.freeze", return_value=mock_freeze):
            report = analyzer.analyze("testenv", str(plugin_dir))

        assert report.risk_level == RiskLevel.GREEN
        assert report.conflicts == []

    def test_analyze_critical_for_major_critical_package_change(self, analyzer, plugin_dir, tmp_path):
        self._setup_env(analyzer, tmp_path)
        (plugin_dir / "requirements.txt").write_text("torch==2.0.0\n")

        dry_json = json.dumps({"install": [{"metadata": {"name": "torch", "version": "2.0.0"}}]})
        mock_run = MagicMock(stdout=dry_json)
        mock_freeze = {"torch": "1.13.0"}

        with patch("src.core.conflict_analyzer.pip_ops.run_pip", return_value=mock_run), \
             patch("src.core.conflict_analyzer.pip_ops.freeze", return_value=mock_freeze):
            report = analyzer.analyze("testenv", str(plugin_dir))

        assert report.risk_level == RiskLevel.CRITICAL
        assert len(report.conflicts) == 1
        assert report.conflicts[0].is_critical is True

    def test_analyze_report_is_serializable(self, analyzer, plugin_dir, tmp_path):
        self._setup_env(analyzer, tmp_path)
        (plugin_dir / "requirements.txt").write_text("numpy==2.0.0\n")

        dry_json = json.dumps({"install": [{"metadata": {"name": "numpy", "version": "2.0.0"}}]})
        mock_run = MagicMock(stdout=dry_json)
        mock_freeze = {"numpy": "1.26.4"}

        with patch("src.core.conflict_analyzer.pip_ops.run_pip", return_value=mock_run), \
             patch("src.core.conflict_analyzer.pip_ops.freeze", return_value=mock_freeze):
            report = analyzer.analyze("testenv", str(plugin_dir))

        d = report.to_dict()
        assert d["risk_level"] in ("GREEN", "YELLOW", "HIGH", "CRITICAL")
        restored = ConflictReport.from_dict(d)
        assert restored.risk_level == report.risk_level
