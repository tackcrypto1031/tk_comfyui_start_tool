"""Environment diagnostics: dependency checks, conflict detection, duplicate node scanning."""
import ast
import json
import logging
import os
import re
from pathlib import Path

from src.utils import pip_ops

logger = logging.getLogger(__name__)


class DiagnosticsManager:
    """Health checks for ComfyUI environments."""

    def __init__(self, config: dict):
        self.config = config
        self.environments_dir = Path(config["environments_dir"])

    # ── Dependency Check ──

    def check_dependencies(self, env_name: str) -> dict:
        """Check installed packages against ComfyUI requirements.txt."""
        env_dir = self.environments_dir / env_name
        venv_path = str(env_dir / "venv")
        req_file = env_dir / "ComfyUI" / "requirements.txt"

        items = []
        status = "ok"

        # Get installed packages
        installed = pip_ops.freeze(venv_path)
        installed_lower = {k.lower().replace("_", "-"): v for k, v in installed.items()}

        # Parse requirements.txt
        if req_file.exists():
            for line in req_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                # Parse package name and version spec
                match = re.match(r"([a-zA-Z0-9_-]+)\s*(.*)", line)
                if not match:
                    continue
                pkg_name = match.group(1).lower().replace("_", "-")
                version_spec = match.group(2).strip()

                if pkg_name in installed_lower:
                    items.append({
                        "package": pkg_name,
                        "status": "ok",
                        "required": version_spec or "any",
                        "installed": installed_lower[pkg_name],
                    })
                else:
                    items.append({
                        "package": pkg_name,
                        "status": "missing",
                        "required": version_spec or "any",
                        "installed": "",
                    })
                    status = "error"

        # Also run pip check for dependency conflicts
        result = pip_ops.run_pip(venv_path, ["check"])
        if result.returncode != 0:
            if status == "ok":
                status = "warning"
            pip_output = (result.stdout or "") + (result.stderr or "")
            for conflict_line in pip_output.strip().splitlines():
                if conflict_line.strip():
                    items.append({
                        "package": "",
                        "status": "pip_check_issue",
                        "required": "",
                        "installed": conflict_line.strip(),
                    })

        return {"status": status, "items": items}

    def install_missing_packages(self, env_name: str, packages: list) -> dict:
        """Install only the specified missing packages (no -r requirements.txt)."""
        env_dir = self.environments_dir / env_name
        venv_path = str(env_dir / "venv")

        if not packages:
            return {"status": "ok", "installed": []}

        result = pip_ops.run_pip(venv_path, ["install"] + list(packages))
        if result.returncode == 0:
            return {"status": "ok", "installed": packages}
        else:
            detail = (result.stderr or result.stdout or "unknown error").strip()
            return {"status": "error", "error": detail}

    # ── Conflict Detection ──

    # Known conflict rules: (pkg_a, pkg_b, description, suggestion)
    _KNOWN_CONFLICTS = [
        {
            "check": lambda inst: (
                "torch" in inst and "xformers" in inst
                and inst.get("torch", "").startswith("2.7")
                and not inst.get("xformers", "").startswith("0.0.30")
            ),
            "description": "torch 2.7.x requires xformers 0.0.30",
            "suggestion": "pip install xformers==0.0.30",
        },
        {
            "check": lambda inst: (
                "torch" in inst and "xformers" in inst
                and inst.get("torch", "").startswith("2.5")
                and not inst.get("xformers", "").startswith("0.0.28")
            ),
            "description": "torch 2.5.x requires xformers 0.0.28",
            "suggestion": "pip install xformers==0.0.28",
        },
        {
            "check": lambda inst: (
                "numpy" in inst and inst.get("numpy", "").startswith("2.")
                and "onnxruntime" in inst
            ),
            "description": "numpy 2.x may conflict with onnxruntime",
            "suggestion": "pip install numpy<2.0",
        },
    ]

    def check_conflicts(self, env_name: str) -> dict:
        """Run pip check + known conflict rules."""
        env_dir = self.environments_dir / env_name
        venv_path = str(env_dir / "venv")

        conflicts = []
        status = "ok"

        # pip check
        result = pip_ops.run_pip(venv_path, ["check"])
        if result.returncode != 0:
            status = "warning"
            pip_output = (result.stdout or "") + (result.stderr or "")
            for line in pip_output.strip().splitlines():
                line = line.strip()
                if line:
                    conflicts.append({
                        "description": line,
                        "suggestion": "Review package versions",
                    })

        # Known conflict rules
        installed = pip_ops.freeze(venv_path)
        installed_lower = {k.lower().replace("_", "-"): v for k, v in installed.items()}

        for rule in self._KNOWN_CONFLICTS:
            try:
                if rule["check"](installed_lower):
                    status = "warning"
                    conflicts.append({
                        "description": rule["description"],
                        "suggestion": rule["suggestion"],
                    })
            except Exception:
                pass

        return {"status": status, "conflicts": conflicts}

    # ── Duplicate Node Detection ──

    def check_duplicate_nodes(self, env_name: str) -> dict:
        """Scan custom_nodes for duplicate NODE_CLASS_MAPPINGS keys."""
        env_dir = self.environments_dir / env_name
        custom_nodes_dir = env_dir / "ComfyUI" / "custom_nodes"

        if not custom_nodes_dir.exists():
            return {"status": "ok", "duplicates": [], "unscannable": []}

        node_registry = {}  # {node_name: [package_name, ...]}
        unscannable = []

        for package in os.listdir(str(custom_nodes_dir)):
            package_path = custom_nodes_dir / package
            if package.endswith(".disabled") or package == "__pycache__":
                continue

            init_file = None
            if package_path.is_dir():
                init_file = package_path / "__init__.py"
            elif str(package_path).endswith(".py"):
                init_file = package_path

            if init_file and init_file.exists():
                names = self._extract_node_names(str(init_file))
                if names is None:
                    unscannable.append(package)
                else:
                    for name in names:
                        node_registry.setdefault(name, []).append(package)

        duplicates = [
            {"node_name": name, "packages": pkgs}
            for name, pkgs in node_registry.items()
            if len(pkgs) > 1
        ]

        status = "warning" if duplicates else "ok"
        return {"status": status, "duplicates": duplicates, "unscannable": unscannable}

    @staticmethod
    def _extract_node_names(filepath: str) -> list:
        """Extract NODE_CLASS_MAPPINGS dict keys using AST, regex fallback.
        Returns list of key strings, or None if unscannable.
        """
        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        if "NODE_CLASS_MAPPINGS" not in content:
            return []

        # Try AST first
        names = _extract_via_ast(content)
        if names is not None:
            return names

        # Fallback: regex
        names = _extract_via_regex(content)
        if names is not None:
            return names

        return None


def _extract_via_ast(content: str) -> list:
    """Use ast.parse to find NODE_CLASS_MAPPINGS = {...} and extract string keys."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    names = []
    for node in ast.walk(tree):
        # Match: NODE_CLASS_MAPPINGS = { "key": value, ... }
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "NODE_CLASS_MAPPINGS":
                    if isinstance(node.value, ast.Dict):
                        for key in node.value.keys:
                            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                names.append(key.value)
                            elif isinstance(key, ast.Str):  # Python 3.7 compat
                                names.append(key.s)
                    else:
                        # Dict comprehension or function call — can't extract statically
                        return None

    return names if names else []


def _extract_via_regex(content: str) -> list:
    """Fallback regex extraction for NODE_CLASS_MAPPINGS dict keys."""
    pattern = r'NODE_CLASS_MAPPINGS\s*=\s*\{([^}]+)\}'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        # Try multi-line: find NODE_CLASS_MAPPINGS = { and read until balanced }
        start = content.find("NODE_CLASS_MAPPINGS")
        if start == -1:
            return None
        brace_start = content.find("{", start)
        if brace_start == -1:
            return None
        depth = 0
        end = brace_start
        for i in range(brace_start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        dict_content = content[brace_start + 1:end - 1]
    else:
        dict_content = match.group(1)

    keys = re.findall(r'["\']([^"\']+)["\']', dict_content)
    # Filter: only keys that look like node names (before a colon)
    # Pattern: "NodeName": SomeClass or 'NodeName': SomeClass
    node_keys = []
    for m in re.finditer(r'["\']([^"\']+)["\']\s*:', dict_content):
        node_keys.append(m.group(1))

    return node_keys if node_keys else (keys[:len(keys) // 2] if keys else [])
