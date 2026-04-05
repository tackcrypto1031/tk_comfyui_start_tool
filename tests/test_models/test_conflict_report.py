"""Tests for ConflictReport data model."""
import pytest

from src.models.conflict_report import ConflictReport, RiskLevel, Conflict


class TestRiskLevel:
    """Test RiskLevel enum."""

    def test_values(self):
        assert RiskLevel.GREEN.value == "GREEN"
        assert RiskLevel.YELLOW.value == "YELLOW"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.CRITICAL.value == "CRITICAL"

    def test_ordering(self):
        assert RiskLevel.GREEN < RiskLevel.YELLOW
        assert RiskLevel.YELLOW < RiskLevel.HIGH
        assert RiskLevel.HIGH < RiskLevel.CRITICAL


class TestConflict:
    """Test Conflict dataclass."""

    def test_create(self):
        c = Conflict(
            package="torch",
            current_version="2.3.1",
            required_version=">=2.4.0",
            resolved_version="2.4.1",
            change_type="UPGRADE",
            is_critical=True,
            risk_level=RiskLevel.CRITICAL,
        )
        assert c.package == "torch"
        assert c.is_critical is True

    def test_to_dict(self):
        c = Conflict(
            package="numpy",
            current_version="1.26.4",
            required_version=">=2.0",
            resolved_version="2.0.0",
            change_type="UPGRADE",
            is_critical=True,
            risk_level=RiskLevel.HIGH,
        )
        d = c.to_dict()
        assert d["package"] == "numpy"
        assert d["risk_level"] == "HIGH"


class TestConflictReport:
    """Test ConflictReport dataclass."""

    def test_create_empty(self):
        report = ConflictReport(
            plugin_name="test-plugin",
            plugin_repo="https://github.com/test/test",
            analysis_time="2026-04-04T10:30:00+08:00",
        )
        assert report.risk_level == RiskLevel.GREEN
        assert report.conflicts == []
        assert report.recommendations == []

    def test_create_with_conflicts(self):
        conflict = Conflict(
            package="torch",
            current_version="2.3.1",
            required_version=">=2.4.0",
            resolved_version="2.4.1",
            change_type="UPGRADE",
            is_critical=True,
            risk_level=RiskLevel.CRITICAL,
        )
        report = ConflictReport(
            plugin_name="AnimateDiff",
            plugin_repo="https://github.com/test/animatediff",
            analysis_time="2026-04-04T10:30:00+08:00",
            risk_level=RiskLevel.CRITICAL,
            conflicts=[conflict],
            recommendations=["建議先克隆環境到沙箱中測試"],
        )
        assert report.risk_level == RiskLevel.CRITICAL
        assert len(report.conflicts) == 1

    def test_to_dict(self):
        report = ConflictReport(
            plugin_name="test-plugin",
            plugin_repo="https://github.com/test/test",
            analysis_time="2026-04-04T10:30:00+08:00",
        )
        d = report.to_dict()
        assert d["plugin_name"] == "test-plugin"
        assert d["risk_level"] == "GREEN"

    def test_from_dict(self):
        data = {
            "plugin_name": "test-plugin",
            "plugin_repo": "https://github.com/test/test",
            "analysis_time": "2026-04-04T10:30:00+08:00",
            "risk_level": "HIGH",
            "conflicts": [],
            "recommendations": ["use sandbox"],
            "summary": "some conflict",
            "dry_run_output": "",
            "compatible_comfyui_versions": [],
        }
        report = ConflictReport.from_dict(data)
        assert report.risk_level == RiskLevel.HIGH
        assert report.recommendations == ["use sandbox"]

    def test_round_trip(self):
        report = ConflictReport(
            plugin_name="test-plugin",
            plugin_repo="https://github.com/test/test",
            analysis_time="2026-04-04T10:30:00+08:00",
            risk_level=RiskLevel.YELLOW,
            summary="minor version bump",
        )
        d = report.to_dict()
        report2 = ConflictReport.from_dict(d)
        assert report.plugin_name == report2.plugin_name
        assert report.risk_level == report2.risk_level
