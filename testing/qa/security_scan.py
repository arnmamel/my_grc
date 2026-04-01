from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path


SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".qa_venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
}


@dataclass(frozen=True, slots=True)
class SecurityIssue:
    rule_id: str
    severity: str
    path: str
    line: int
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


class SecurityVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.issues: list[SecurityIssue] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = self._call_name(node.func)
        keyword_names = {item.arg: item.value for item in node.keywords if item.arg}
        if name in {"eval", "exec"}:
            self._issue("AST001", "high", node, f"Use of `{name}` can execute untrusted code.")
        if name == "os.system":
            self._issue("AST002", "high", node, "Use of `os.system` is risky and should be replaced with safer subprocess patterns.")
        if name.startswith("subprocess.") and "shell" in keyword_names and self._literal_true(keyword_names["shell"]):
            self._issue("AST003", "high", node, "Subprocess call enables `shell=True`.")
        if name.startswith("requests.") and "verify" in keyword_names and self._literal_false(keyword_names["verify"]):
            self._issue("AST004", "high", node, "Requests call disables TLS certificate verification.")
        if name == "yaml.load":
            self._issue("AST005", "medium", node, "Use `yaml.safe_load` unless a trusted loader is explicitly required.")
        if name in {"pickle.load", "pickle.loads", "marshal.load", "marshal.loads"}:
            self._issue("AST006", "high", node, f"Use of `{name}` can deserialize unsafe input.")
        if name == "tempfile.mktemp":
            self._issue("AST007", "medium", node, "Use `NamedTemporaryFile` or `mkstemp` instead of `mktemp`.")
        self.generic_visit(node)

    def _issue(self, rule_id: str, severity: str, node: ast.AST, message: str) -> None:
        self.issues.append(
            SecurityIssue(
                rule_id=rule_id,
                severity=severity,
                path=str(self.path),
                line=getattr(node, "lineno", 0),
                message=message,
            )
        )

    @staticmethod
    def _call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = SecurityVisitor._call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    @staticmethod
    def _literal_true(node: ast.AST) -> bool:
        return isinstance(node, ast.Constant) and node.value is True

    @staticmethod
    def _literal_false(node: ast.AST) -> bool:
        return isinstance(node, ast.Constant) and node.value is False


def scan_project(root: Path) -> dict:
    issues: list[SecurityIssue] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if "qa" in path.parts and path.name.endswith(".py") and path.parent.name == "reports":
            continue
        try:
            source = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            issues.append(
                SecurityIssue(
                    rule_id="AST000",
                    severity="high",
                    path=str(path),
                    line=exc.lineno or 0,
                    message=f"Syntax error while parsing file: {exc.msg}",
                )
            )
            continue
        visitor = SecurityVisitor(path.relative_to(root))
        visitor.visit(tree)
        issues.extend(visitor.issues)
    issues.sort(key=lambda item: (-SEVERITY_ORDER[item.severity], item.path, item.line, item.rule_id))
    return {
        "status": "pass" if not issues else ("fail" if any(item.severity == "high" for item in issues) else "warn"),
        "issues": [item.to_dict() for item in issues],
        "summary": {
            "total": len(issues),
            "high": sum(1 for item in issues if item.severity == "high"),
            "medium": sum(1 for item in issues if item.severity == "medium"),
            "low": sum(1 for item in issues if item.severity == "low"),
        },
    }
