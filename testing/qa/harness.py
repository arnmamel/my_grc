from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from testing.qa.security_scan import scan_project


ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "testing" / "qa" / "reports"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class CheckResult:
    name: str
    category: str
    status: str
    duration_seconds: float
    summary: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class QaHarnessConfig:
    python_bin: str
    keep_run_dir: bool = False
    fail_fast: bool = False
    selected_checks: list[str] | None = None
    output_json: Path | None = REPORTS_DIR / "latest.json"
    output_md: Path | None = REPORTS_DIR / "latest.md"


class QaHarness:
    def __init__(self, config: QaHarnessConfig) -> None:
        self.config = config
        self.root = ROOT
        self.report_dir = REPORTS_DIR
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.checks: list[tuple[str, Callable[[Path, dict[str, str]], CheckResult]]] = [
            ("security", self.check_security),
            ("database", self.check_database_schema),
            ("unit", self.check_unit_tests),
            ("cli", self.check_cli_smoke),
            ("workspace", self.check_workspace_smoke),
        ]

    def run(self) -> dict:
        started = _utc_now()
        run_dir = Path(tempfile.mkdtemp(prefix="my_grc_qa_"))
        env = self._isolated_env(run_dir)
        results: list[CheckResult] = []
        overall = "pass"
        try:
            for check_name, func in self.checks:
                if self.config.selected_checks and check_name not in self.config.selected_checks:
                    continue
                result = func(run_dir, env)
                results.append(result)
                if result.status == "fail":
                    overall = "fail"
                    if self.config.fail_fast:
                        break
                elif result.status == "warn" and overall != "fail":
                    overall = "warn"
        finally:
            finished = _utc_now()
            report = {
                "status": overall,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "duration_seconds": round((finished - started).total_seconds(), 3),
                "run_dir": str(run_dir),
                "kept_run_dir": self.config.keep_run_dir,
                "python_bin": self.config.python_bin,
                "checks": [item.to_dict() for item in results],
                "summary": {
                    "total": len(results),
                    "passed": sum(1 for item in results if item.status == "pass"),
                    "warnings": sum(1 for item in results if item.status == "warn"),
                    "failed": sum(1 for item in results if item.status == "fail"),
                },
            }
            if self.config.output_json:
                self.config.output_json.parent.mkdir(parents=True, exist_ok=True)
                self.config.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
            if self.config.output_md:
                self.config.output_md.parent.mkdir(parents=True, exist_ok=True)
                self.config.output_md.write_text(self._markdown_report(report), encoding="utf-8")
            if not self.config.keep_run_dir:
                shutil.rmtree(run_dir, ignore_errors=True)
                report["run_dir"] = ""
            return report

    def check_security(self, run_dir: Path, env: dict[str, str]) -> CheckResult:
        start = time.monotonic()
        scan = scan_project(self.root)
        status = scan["status"]
        summary = f"{scan['summary']['total']} security issue(s) detected"
        if status == "pass":
            summary = "No static security findings detected by the built-in scanner."
        return CheckResult(
            name="Static Security Scan",
            category="security",
            status=status,
            duration_seconds=round(time.monotonic() - start, 3),
            summary=summary,
            details=scan,
        )

    def check_database_schema(self, run_dir: Path, env: dict[str, str]) -> CheckResult:
        start = time.monotonic()
        code = textwrap.dedent(
            """
            import json
            from sqlalchemy import inspect, func, select

            from aws_local_audit.db import init_database, session_scope
            from aws_local_audit.models import AccessRole, FeatureFlag, Framework
            from aws_local_audit.services.frameworks import FrameworkService

            init_database()
            with session_scope() as session:
                seeded = FrameworkService(session).seed_templates()
                inspector = inspect(session.get_bind())
                tables = sorted(inspector.get_table_names())
                required_tables = [
                    "frameworks",
                    "controls",
                    "organizations",
                    "evidence_items",
                    "assessment_runs",
                    "lifecycle_events",
                    "identity_principals",
                    "access_roles",
                    "role_assignments",
                ]
                missing = [name for name in required_tables if name not in tables]
                print(
                    json.dumps(
                        {
                            "tables": tables,
                            "missing_tables": missing,
                            "frameworks": session.scalar(select(func.count()).select_from(Framework)) or 0,
                            "roles": session.scalar(select(func.count()).select_from(AccessRole)) or 0,
                            "feature_flags": session.scalar(select(func.count()).select_from(FeatureFlag)) or 0,
                            "seeded_frameworks": len(seeded),
                        }
                    )
                )
            """
        )
        result = self._run_subprocess(
            [self.config.python_bin, "-c", code],
            env=env,
            name="database-schema",
            timeout=300,
        )
        payload = self._json_from_output(result)
        status = "pass"
        summary = f"Database initialized with {payload.get('frameworks', 0)} framework(s)."
        if payload.get("missing_tables"):
            status = "fail"
            summary = f"Missing required tables: {', '.join(payload['missing_tables'])}"
        elif payload.get("roles", 0) == 0 or payload.get("feature_flags", 0) == 0:
            status = "warn"
            summary = "Database bootstrapped, but RBAC or feature flags were not seeded."
        return CheckResult(
            name="Database And Schema Smoke",
            category="database",
            status=status,
            duration_seconds=round(time.monotonic() - start, 3),
            summary=summary,
            details=payload,
        )

    def check_unit_tests(self, run_dir: Path, env: dict[str, str]) -> CheckResult:
        start = time.monotonic()
        result = self._run_subprocess(
            [self.config.python_bin, "-m", "unittest", "discover", "-s", "testing/tests", "-p", "test_*.py", "-v"],
            env=env,
            name="unit-tests",
            timeout=900,
        )
        status = "pass" if result["returncode"] == 0 else "fail"
        output = result["stdout"]
        summary = "All discovered unit and regression tests passed." if status == "pass" else "Unit/regression test discovery failed."
        return CheckResult(
            name="Unit And Regression Suite",
            category="unit",
            status=status,
            duration_seconds=round(time.monotonic() - start, 3),
            summary=summary,
            details={
                "command": result["command"],
                "returncode": result["returncode"],
                "output_tail": output.splitlines()[-40:],
            },
        )

    def check_cli_smoke(self, run_dir: Path, env: dict[str, str]) -> CheckResult:
        start = time.monotonic()
        commands = [
            [self.config.python_bin, "src/aws_local_audit/cli.py", "init-db"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "security", "bootstrap"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "framework", "seed"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "org", "create", "QA Organization", "--code", "QAORG"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "rbac", "seed-roles"],
            [
                self.config.python_bin,
                "src/aws_local_audit/cli.py",
                "rbac",
                "upsert-principal",
                "qa.lead",
                "--display-name",
                "QA Lead",
                "--organization-id",
                "1",
                "--email",
                "qa@example.com",
            ],
            [
                self.config.python_bin,
                "src/aws_local_audit/cli.py",
                "rbac",
                "assign",
                "qa.lead",
                "org_admin",
                "--organization-id",
                "1",
                "--actor",
                "qa-harness",
            ],
            [
                self.config.python_bin,
                "src/aws_local_audit/cli.py",
                "rbac",
                "approve",
                "1",
                "--approver",
                "qa.approver",
            ],
            [
                self.config.python_bin,
                "src/aws_local_audit/cli.py",
                "ucf",
                "create",
                "QA.UCF.1",
                "--name",
                "QA Unified Control",
            ],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "copilot", "seed"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "copilot", "list"],
            [
                self.config.python_bin,
                "src/aws_local_audit/cli.py",
                "ucf",
                "map",
                "--unified-control",
                "QA.UCF.1",
                "--framework",
                "ISO27001_2022",
                "--control-id",
                "A.5.1",
            ],
            [
                self.config.python_bin,
                "src/aws_local_audit/cli.py",
                "copilot",
                "draft",
                "--pack",
                "SCF_ISO27001_ANNEX_A",
                "--task",
                "mapping_rationale",
                "--framework",
                "ISO27001_2022",
                "--control-id",
                "A.5.1",
                "--unified-control",
                "QA.UCF.1",
            ],
            [
                self.config.python_bin,
                "src/aws_local_audit/cli.py",
                "implementation",
                "upsert",
                "--org",
                "QAORG",
                "--framework",
                "ISO27001_2022",
                "--control-id",
                "A.5.1",
                "--title",
                "QA Control Implementation",
            ],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "assessment", "run", "--framework", "ISO27001_2022"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "assessment", "list"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "platform", "health"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "platform", "recovery-drill"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "privacy", "report"],
            [self.config.python_bin, "src/aws_local_audit/cli.py", "maturity", "enterprise-score"],
        ]
        outputs = []
        failing_command = None
        status = "pass"
        for command in commands:
            result = self._run_subprocess(command, env=env, name="cli-smoke", timeout=300, check=False)
            outputs.append(
                {
                    "command": result["command"],
                    "returncode": result["returncode"],
                    "output_tail": result["stdout"].splitlines()[-20:],
                }
            )
            if result["returncode"] != 0:
                status = "fail"
                failing_command = result["command"]
                break
        summary = "Offline CLI smoke workflow completed successfully."
        if status == "fail":
            summary = f"CLI smoke workflow failed on: {failing_command}"
        return CheckResult(
            name="Offline CLI Smoke Workflow",
            category="cli",
            status=status,
            duration_seconds=round(time.monotonic() - start, 3),
            summary=summary,
            details={"steps": outputs},
        )

    def check_workspace_smoke(self, run_dir: Path, env: dict[str, str]) -> CheckResult:
        start = time.monotonic()
        port = self._free_port()
        log_path = run_dir / "streamlit-smoke.log"
        command = [
            self.config.python_bin,
            "-m",
            "streamlit",
            "run",
            "workspace/app.py",
            "--server.headless=true",
            f"--server.port={port}",
            "--browser.gatherUsageStats=false",
        ]
        process = None
        status = "fail"
        summary = "Workspace smoke test did not start."
        health_url = f"http://127.0.0.1:{port}/_stcore/health"
        try:
            with log_path.open("w", encoding="utf-8") as handle:
                process = subprocess.Popen(
                    command,
                    cwd=self.root,
                    env=env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                deadline = time.time() + 90
                while time.time() < deadline:
                    if process.poll() is not None:
                        break
                    try:
                        with urllib.request.urlopen(health_url, timeout=2) as response:
                            body = response.read().decode("utf-8", errors="replace").strip()
                        if body.lower() == "ok":
                            status = "pass"
                            summary = "Streamlit workspace started and responded to the health endpoint."
                            break
                    except urllib.error.URLError:
                        time.sleep(1)
                if status != "pass" and process.poll() is None:
                    summary = "Streamlit workspace did not become healthy before timeout."
        finally:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        log_tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-60:] if log_path.exists() else []
        return CheckResult(
            name="Workspace Smoke Test",
            category="workspace",
            status=status,
            duration_seconds=round(time.monotonic() - start, 3),
            summary=summary,
            details={
                "command": " ".join(command),
                "port": port,
                "health_url": health_url,
                "log_tail": log_tail,
            },
        )

    def _isolated_env(self, run_dir: Path) -> dict[str, str]:
        env = os.environ.copy()
        home = run_dir / "home"
        env.update(
            {
                "ALA_DATABASE_URL": f"sqlite:///{(run_dir / 'qa.db').as_posix()}",
                "ALA_SECRET_NAMESPACE": f"my_grc_qa_{int(time.time())}",
                "ALA_SECRET_FILES_DIR": str(run_dir / "secrets"),
                "ALA_EXTERNAL_MODULES_DIR": str(run_dir / "external_modules"),
                "ALA_LOG_DIR": str(run_dir / "logs"),
                "ALA_LOG_LEVEL": "INFO",
                "ALA_APP_LOG_FILE": "app.log",
                "ALA_AUDIT_LOG_FILE": "audit.log",
                "ALA_METRICS_LOG_FILE": "metrics.log",
                "ALA_TRACE_LOG_FILE": "traces.log",
                "ALA_OFFLINE_MODE": "true",
                "ALA_ALLOW_INSECURE_ENV_SECRETS": "false",
                "ALA_CONFLUENCE_BASE_URL": "",
                "ALA_CONFLUENCE_SPACE_KEY": "",
                "ALA_CONFLUENCE_PARENT_PAGE_ID": "",
                "ALA_CONFLUENCE_AUTH_MODE": "bearer",
                "ALA_CONFLUENCE_USERNAME": "",
                "ALA_CONFLUENCE_API_TOKEN": "",
                "ALA_CONFLUENCE_BEARER_TOKEN": "",
                "ALA_DEFAULT_AWS_REGION": "eu-west-1",
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "XDG_DATA_HOME": str(home / ".local" / "share"),
                "PYTHONUNBUFFERED": "1",
                "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
                "PYTHONPATH": str(self.root / "src"),
            }
        )
        for path in [
            run_dir / "secrets",
            run_dir / "external_modules",
            run_dir / "logs",
            home / ".config",
            home / ".cache",
            home / ".local" / "share",
        ]:
            path.mkdir(parents=True, exist_ok=True)
        return env

    def _run_subprocess(
        self,
        command: list[str],
        *,
        env: dict[str, str],
        name: str,
        timeout: int,
        check: bool = True,
    ) -> dict:
        completed = subprocess.run(
            command,
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        combined = "\n".join(item for item in [completed.stdout, completed.stderr] if item).strip()
        result = {
            "name": name,
            "command": " ".join(command),
            "returncode": completed.returncode,
            "stdout": combined,
        }
        if check and completed.returncode != 0:
            raise RuntimeError(f"{name} failed: {result['command']}\n{combined}")
        return result

    @staticmethod
    def _json_from_output(result: dict) -> dict:
        lines = [item.strip() for item in result["stdout"].splitlines() if item.strip()]
        for line in reversed(lines):
            if line.startswith("{") and line.endswith("}"):
                return json.loads(line)
        raise ValueError(f"Unable to parse JSON payload from command output: {result['stdout']}")

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
            handle.bind(("127.0.0.1", 0))
            return int(handle.getsockname()[1])

    @staticmethod
    def _markdown_report(report: dict) -> str:
        lines = [
            "# my_grc QA Report",
            "",
            f"- Status: `{report['status']}`",
            f"- Started: `{report['started_at']}`",
            f"- Finished: `{report['finished_at']}`",
            f"- Duration: `{report['duration_seconds']}` seconds",
            "",
            "## Summary",
            "",
            f"- Checks: `{report['summary']['total']}`",
            f"- Passed: `{report['summary']['passed']}`",
            f"- Warnings: `{report['summary']['warnings']}`",
            f"- Failed: `{report['summary']['failed']}`",
            "",
            "## Checks",
            "",
        ]
        for item in report["checks"]:
            lines.extend(
                [
                    f"### {item['name']}",
                    "",
                    f"- Category: `{item['category']}`",
                    f"- Status: `{item['status']}`",
                    f"- Duration: `{item['duration_seconds']}` seconds",
                    f"- Summary: {item['summary']}",
                    "",
                ]
            )
        return "\n".join(lines) + "\n"


def print_report(report: dict) -> None:
    print(f"QA overall status: {report['status']}")
    print(
        "Checks: {passed} passed, {warnings} warnings, {failed} failed".format(
            passed=report["summary"]["passed"],
            warnings=report["summary"]["warnings"],
            failed=report["summary"]["failed"],
        )
    )
    for item in report["checks"]:
        print(f"- [{item['status']}] {item['name']}: {item['summary']}")


def default_python() -> str:
    return sys.executable
