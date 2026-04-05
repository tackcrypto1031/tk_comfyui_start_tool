"""Conflict analysis engine — 6-step plugin dependency conflict detection."""
import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from packaging.version import Version, InvalidVersion

from src.models.conflict_report import ConflictReport, Conflict, RiskLevel
from src.utils import pip_ops


class ConflictAnalyzer:
    """Analyzes plugin dependencies for conflicts before installation."""

    def __init__(self, config: dict):
        self.config = config
        self.environments_dir = Path(config["environments_dir"])
        self.critical_packages = config.get("conflict_analyzer", {}).get(
            "critical_packages", []
        )

    def analyze(self, env_name: str, node_path: str) -> ConflictReport:
        """Full 6-step analysis pipeline. node_path is a local path to the plugin."""
        plugin_name = Path(node_path).name

        # Step 1: Extract dependencies
        all_deps = self.extract_all_dependencies(node_path)

        # Step 2: Dry run
        env_dir = self.environments_dir / env_name
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment '{env_name}' not found")
        venv_path = str(env_dir / "venv")
        dry_run_output = self.dry_run(venv_path, all_deps)

        # Step 3: Compare versions
        current_freeze = pip_ops.freeze(venv_path)
        conflicts = self.compare_versions(current_freeze, dry_run_output)

        # Step 4: Detect critical
        conflicts = self.detect_critical_conflicts(conflicts)

        # Step 5: Determine overall risk
        risk_level = self.classify_risk(conflicts)

        # Step 6: Generate recommendations
        recommendations = self.generate_recommendations(conflicts, risk_level)

        return ConflictReport(
            plugin_name=plugin_name,
            plugin_repo=node_path,
            analysis_time=datetime.now(timezone.utc).isoformat(),
            risk_level=risk_level,
            conflicts=conflicts,
            recommendations=recommendations,
            summary=self._generate_summary(conflicts, risk_level),
            dry_run_output=str(dry_run_output),
        )

    # --- Step 1: Dependency Extraction ---

    def extract_all_dependencies(self, node_path: str) -> List[str]:
        """Extract all dependencies from a plugin directory."""
        deps = []
        node = Path(node_path)

        # requirements.txt
        deps.extend(self.extract_requirements(node))

        # install.py AST analysis
        install_py = node / "install.py"
        if install_py.exists():
            deps.extend(self.extract_install_py_deps(str(install_py)))

        # Deduplicate while preserving order
        return list(dict.fromkeys(deps))

    def extract_requirements(self, node_path: Path) -> List[str]:
        """Parse requirements.txt if it exists."""
        req_file = node_path / "requirements.txt"
        if not req_file.exists():
            return []
        deps = []
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                deps.append(line)
        return deps

    def extract_install_py_deps(self, install_py_path: str) -> List[str]:
        """AST-parse install.py to extract pip install commands."""
        source = Path(install_py_path).read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        deps = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                deps.extend(self._extract_from_call(node))
                deps.extend(self._extract_from_os_system(node))
        return deps

    def _extract_from_call(self, node: ast.Call) -> List[str]:
        """Extract packages from subprocess.run/call/check_call calls."""
        func_name = self._get_func_name(node)
        if func_name not in ("subprocess.run", "subprocess.call", "subprocess.check_call"):
            return []

        if not node.args:
            return []

        first_arg = node.args[0]
        if not isinstance(first_arg, ast.List):
            return []

        str_elements = []
        for elt in first_arg.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                str_elements.append(elt.value)
            else:
                str_elements.append(None)  # placeholder for dynamic values

        # Find "pip" and "install" in the list
        try:
            pip_idx = next(
                i for i, s in enumerate(str_elements) if s is not None and s.endswith("pip")
            )
        except StopIteration:
            return []

        if pip_idx + 1 >= len(str_elements) or str_elements[pip_idx + 1] != "install":
            return []

        deps = []
        for pkg in str_elements[pip_idx + 2:]:
            if pkg is None:
                continue
            if not pkg.startswith("-"):
                deps.append(pkg)
        return deps

    def _extract_from_os_system(self, node: ast.Call) -> List[str]:
        """Extract packages from os.system("pip install ...") calls."""
        func_name = self._get_func_name(node)
        if func_name != "os.system":
            return []

        if not node.args:
            return []

        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return self._parse_pip_command_string(arg.value)
        if isinstance(arg, ast.JoinedStr):  # f-string
            parts = []
            for val in arg.values:
                if isinstance(val, ast.Constant):
                    parts.append(str(val.value))
                else:
                    parts.append("DYNAMIC")
            return self._parse_pip_command_string("".join(parts))
        return []

    def _parse_pip_command_string(self, cmd: str) -> List[str]:
        """Parse a pip install command string for package names."""
        match = re.search(r"pip\s+install\s+(.+)", cmd)
        if not match:
            return []
        rest = match.group(1).strip()
        deps = []
        for token in rest.split():
            if token.startswith("-") or "DYNAMIC" in token:
                continue
            deps.append(token)
        return deps

    def _get_func_name(self, node: ast.Call) -> str:
        """Get the dotted function name from an AST Call node."""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return f"{node.func.value.id}.{node.func.attr}"
            if isinstance(node.func.value, ast.Attribute):
                if isinstance(node.func.value.value, ast.Name):
                    return (
                        f"{node.func.value.value.id}"
                        f".{node.func.value.attr}"
                        f".{node.func.attr}"
                    )
        if isinstance(node.func, ast.Name):
            return node.func.id
        return ""

    # --- Step 2: Dry Run ---

    def dry_run(self, venv_path: str, requirements: List[str]) -> dict:
        """Run pip install --dry-run and return parsed results."""
        if not requirements:
            return {}

        result = pip_ops.run_pip(
            venv_path,
            ["install", "--dry-run", "--report", "-"] + requirements,
        )

        try:
            report = json.loads(result.stdout)
            changes = {}
            for item in report.get("install", []):
                meta = item.get("metadata", {})
                name = meta.get("name", "")
                version = meta.get("version", "")
                if name:
                    changes[name.lower()] = version
            return changes
        except (json.JSONDecodeError, KeyError):
            return {}

    # --- Step 3: Compare Versions ---

    def compare_versions(self, current_freeze: dict, dry_run_results: dict) -> List[Conflict]:
        """Compare current environment with dry-run results."""
        conflicts = []
        current = {k.lower(): v for k, v in current_freeze.items()}

        for pkg, new_ver in dry_run_results.items():
            pkg_lower = pkg.lower()
            if pkg_lower in current:
                cur_ver = current[pkg_lower]
                if cur_ver != new_ver:
                    change_type = self._determine_change_type(cur_ver, new_ver)
                    conflicts.append(Conflict(
                        package=pkg,
                        current_version=cur_ver,
                        required_version="",
                        resolved_version=new_ver,
                        change_type=change_type,
                        is_critical=False,
                        risk_level=RiskLevel.GREEN,
                    ))
            else:
                conflicts.append(Conflict(
                    package=pkg,
                    current_version="",
                    required_version="",
                    resolved_version=new_ver,
                    change_type="NEW",
                    is_critical=False,
                    risk_level=RiskLevel.GREEN,
                ))
        return conflicts

    def _determine_change_type(self, current: str, new: str) -> str:
        try:
            return "UPGRADE" if Version(new) > Version(current) else "DOWNGRADE"
        except InvalidVersion:
            return "UPGRADE"

    # --- Step 4: Critical Package Detection ---

    def detect_critical_conflicts(self, conflicts: List[Conflict]) -> List[Conflict]:
        """Mark conflicts involving critical packages."""
        critical_lower = {p.lower() for p in self.critical_packages}
        for conflict in conflicts:
            if conflict.package.lower() in critical_lower:
                conflict.is_critical = True
        return conflicts

    # --- Step 5: Risk Classification ---

    def classify_risk(self, conflicts: List[Conflict]) -> RiskLevel:
        """Determine overall risk level based on conflicts."""
        if not conflicts:
            return RiskLevel.GREEN

        max_risk = RiskLevel.GREEN
        for c in conflicts:
            risk = self._single_conflict_risk(c)
            c.risk_level = risk
            if risk > max_risk:
                max_risk = risk
        return max_risk

    def _single_conflict_risk(self, c: Conflict) -> RiskLevel:
        """Classify risk for a single conflict."""
        if c.change_type == "NEW":
            return RiskLevel.GREEN

        try:
            cur = Version(c.current_version) if c.current_version else None
            new = Version(c.resolved_version) if c.resolved_version else None
        except InvalidVersion:
            return RiskLevel.YELLOW

        if cur is None or new is None:
            return RiskLevel.YELLOW

        major_change = cur.major != new.major
        minor_change = cur.minor != new.minor

        if c.is_critical:
            if major_change:
                return RiskLevel.CRITICAL
            if minor_change:
                return RiskLevel.HIGH
            return RiskLevel.YELLOW
        else:
            if major_change:
                return RiskLevel.HIGH
            if minor_change:
                return RiskLevel.YELLOW
            return RiskLevel.GREEN

    # --- Step 6: Recommendations ---

    def generate_recommendations(self, conflicts: List[Conflict], risk: RiskLevel) -> List[str]:
        """Generate user-facing recommendations based on analysis."""
        recs = []
        if risk == RiskLevel.GREEN:
            recs.append("安全，可直接安裝")
        elif risk == RiskLevel.YELLOW:
            recs.append("有小版本變動，建議注意安裝後的環境狀態")
        elif risk == RiskLevel.HIGH:
            recs.append("建議先克隆環境到沙箱中測試")
            critical = [c for c in conflicts if c.is_critical]
            for c in critical:
                recs.append(
                    f"核心套件 {c.package} 將從 {c.current_version} 變更為 {c.resolved_version}"
                )
        elif risk == RiskLevel.CRITICAL:
            recs.append("強烈建議使用沙箱環境安裝")
            recs.append("此插件可能導致現有環境無法正常運作")
        return recs

    def _generate_summary(self, conflicts: List[Conflict], risk: RiskLevel) -> str:
        if not conflicts:
            return "無衝突"
        critical = [c for c in conflicts if c.is_critical]
        if critical:
            names = ", ".join(c.package for c in critical)
            return f"涉及核心套件變更: {names}"
        return f"共 {len(conflicts)} 個套件變更"
