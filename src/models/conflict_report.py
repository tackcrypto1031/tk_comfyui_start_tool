"""Conflict report data model."""
from dataclasses import dataclass, field, asdict
from enum import Enum


class RiskLevel(Enum):
    """Risk level for plugin installation."""

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    def __lt__(self, other):
        if not isinstance(other, RiskLevel):
            return NotImplemented
        order = [RiskLevel.GREEN, RiskLevel.YELLOW, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return order.index(self) < order.index(other)

    def __le__(self, other):
        return self == other or self.__lt__(other)

    def __gt__(self, other):
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return not self.__le__(other)

    def __ge__(self, other):
        return self == other or self.__gt__(other)


@dataclass
class Conflict:
    """Represents a single package conflict."""

    package: str
    current_version: str
    required_version: str
    resolved_version: str
    change_type: str  # "UPGRADE", "DOWNGRADE", "NEW", "REMOVE"
    is_critical: bool
    risk_level: RiskLevel

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Conflict":
        """Deserialize from dictionary."""
        data = dict(data)
        if isinstance(data.get("risk_level"), str):
            data["risk_level"] = RiskLevel(data["risk_level"])
        return cls(**data)


@dataclass
class ConflictReport:
    """Represents the full conflict analysis report for a plugin."""

    plugin_name: str
    plugin_repo: str
    analysis_time: str
    risk_level: RiskLevel = RiskLevel.GREEN
    conflicts: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    summary: str = ""
    dry_run_output: str = ""
    compatible_comfyui_versions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        d = {
            "plugin_name": self.plugin_name,
            "plugin_repo": self.plugin_repo,
            "analysis_time": self.analysis_time,
            "risk_level": self.risk_level.value,
            "conflicts": [c.to_dict() if isinstance(c, Conflict) else c for c in self.conflicts],
            "recommendations": self.recommendations,
            "summary": self.summary,
            "dry_run_output": self.dry_run_output,
            "compatible_comfyui_versions": self.compatible_comfyui_versions,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ConflictReport":
        """Deserialize from dictionary."""
        data = dict(data)
        if isinstance(data.get("risk_level"), str):
            data["risk_level"] = RiskLevel(data["risk_level"])
        conflicts = data.get("conflicts", [])
        data["conflicts"] = [
            Conflict.from_dict(c) if isinstance(c, dict) else c for c in conflicts
        ]
        return cls(**data)
