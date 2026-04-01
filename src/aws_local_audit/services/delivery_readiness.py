from __future__ import annotations

import json
import tomllib
from pathlib import Path

from aws_local_audit.services.enterprise_maturity import EnterpriseMaturityService
from aws_local_audit.services.phase1_maturity import Phase1MaturityService


class DeliveryReadinessAssessmentService:
    def __init__(self, session, *, root: Path | None = None):
        self.session = session
        self.root = root or Path(__file__).resolve().parents[3]
        self.docs_root = self.root / "documentation"
        self.qa_report_path = self.root / "testing" / "qa" / "reports" / "latest.json"

    def assess(self) -> dict:
        qa_report = self._load_json(self.qa_report_path)
        phase1 = Phase1MaturityService(self.session).assess()
        enterprise = EnterpriseMaturityService(self.session).assess()
        dimensions = [
            self._functional_dimension(qa_report),
            self._usability_dimension(),
            self._reliability_dimension(qa_report),
            self._security_dimension(qa_report),
            self._operability_dimension(qa_report),
        ]
        overall_score = round(sum(item["score"] for item in dimensions) / len(dimensions), 2)
        release_blockers = self._top_release_blockers(dimensions)
        business_risks = self._top_business_risks(dimensions)
        assessment = {
            "version": self.product_version(),
            "product_name": self.product_name(),
            "overall_score": overall_score,
            "phase1_score": phase1["overall_score"],
            "enterprise_score": enterprise["overall_score"],
            "qa_report_status": qa_report.get("status", "unknown"),
            "dimensions": dimensions,
            "scorecard": [
                {
                    "dimension": item["name"],
                    "score": item["score"],
                    "confidence": item["confidence"],
                    "implemented": item["implemented_state"],
                }
                for item in dimensions
            ],
            "heatmap": [
                {
                    "dimension": dimension["name"],
                    "subarea": subarea["name"],
                    "score": subarea["score"],
                    "confidence": subarea["confidence"],
                }
                for dimension in dimensions
                for subarea in dimension["subareas"]
            ],
            "top_release_blockers": release_blockers,
            "top_engineering_debt": self._top_engineering_debt(),
            "top_business_risks": business_risks,
            "fragile_dependencies": self._fragile_dependencies(),
            "manual_heroics": self._manual_heroics(),
            "trust_risks": self._trust_risks(),
            "scaling_risks": self._scaling_risks(),
            "quick_wins": self._quick_wins(),
            "structural_improvements": self._structural_improvements(),
            "missing_evidence": self._missing_evidence(),
            "improvement_plan": self._improvement_plan(release_blockers),
            "deployment_readiness_verdict": self._deployment_verdict(overall_score, release_blockers),
        }
        return assessment

    def product_name(self) -> str:
        payload = self._pyproject()
        return payload.get("project", {}).get("name", "my_grc")

    def product_version(self) -> str:
        payload = self._pyproject()
        return payload.get("project", {}).get("version", "0.0.0")

    def _pyproject(self) -> dict:
        return tomllib.loads((self.root / "pyproject.toml").read_text(encoding="utf-8"))

    def _functional_dimension(self, qa_report: dict) -> dict:
        critical_flows = [
            {
                "name": "SCF workbook control management",
                "implemented": self._all_exist(
                    "workspace/control_framework_studio_v2.py",
                    "src/aws_local_audit/services/control_studio_workbook.py",
                    "src/aws_local_audit/services/control_matrix.py",
                ),
                "tests": self._all_exist(
                    "testing/tests/test_control_studio_workbook.py",
                    "testing/tests/test_control_matrix.py",
                ),
            },
            {
                "name": "Framework import and SCF pivot mapping",
                "implemented": self._all_exist(
                    "src/aws_local_audit/services/framework_imports.py",
                    "src/aws_local_audit/services/workbench.py",
                ),
                "tests": self._exists("testing/tests/test_framework_imports.py"),
            },
            {
                "name": "Evidence collection and readiness checks",
                "implemented": self._all_exist(
                    "src/aws_local_audit/services/evidence.py",
                    "src/aws_local_audit/services/readiness.py",
                    "workspace/operations_workspace.py",
                ),
                "tests": self._exists("testing/tests/test_evidence_service.py"),
            },
            {
                "name": "Questionnaire answer reuse",
                "implemented": self._all_exist(
                    "src/aws_local_audit/services/questionnaires.py",
                    "workspace/questionnaire_center.py",
                ),
                "tests": self._exists("testing/tests/test_questionnaire_service.py"),
            },
            {
                "name": "Assessment execution and review",
                "implemented": self._all_exist(
                    "src/aws_local_audit/services/assessments.py",
                    "src/aws_local_audit/services/review_queue.py",
                ),
                "tests": self._exists("testing/tests/test_review_queue.py"),
            },
        ]
        covered_flows = sum(1 for item in critical_flows if item["implemented"] and item["tests"])
        flow_ratio = covered_flows / len(critical_flows)
        subareas = [
            self._subarea(
                "1.1 Business flow implementation",
                round(2.0 + flow_ratio * 2.2, 2),
                "High",
                [
                    "Critical user journeys identifiable in code and tests",
                    "Main workflows implemented end-to-end",
                    "Negative paths covered in regression tests",
                ],
                [
                    "workspace/control_framework_studio_v2.py",
                    "src/aws_local_audit/services/framework_imports.py",
                    "src/aws_local_audit/services/evidence.py",
                    "testing/tests/test_control_studio_workbook.py",
                    "testing/tests/test_framework_imports.py",
                    "testing/tests/test_evidence_service.py",
                ],
                f"{covered_flows} of {len(critical_flows)} critical flows have both implementation and automated regression evidence.",
                [
                    "Some critical flows still rely on proxy coverage rather than dedicated end-to-end assertions."
                ],
                ["Add explicit regression tests for failure and rollback branches in each critical flow."],
                implemented_state="implemented" if flow_ratio >= 0.8 else "partially implemented",
            ),
            self._subarea(
                "1.2 Requirements traceability",
                2.9,
                "Medium",
                [
                    "Requirements linked to tests",
                    "Specs reflected in implementation and acceptance checks",
                ],
                [
                    "README.md",
                    "documentation/assessment/PHASE1_STRICT_4OF5_ASSESSMENT.md",
                    "documentation/assessment/PHASE2_ASSESSMENT.md",
                    "testing/tests/test_control_studio_workbook.py",
                ],
                "There is strong narrative documentation and many targeted tests, but there is no systematic requirement-to-test matrix or ticket linkage enforced in code.",
                ["Formal acceptance traceability remains mostly documentary and manual."],
                ["Introduce requirement IDs and test annotations for critical journeys."],
                implemented_state="partially implemented",
            ),
            self._subarea(
                "1.3 Data correctness and integrity",
                3.8,
                "Medium",
                [
                    "Input validation and valid transitions",
                    "Transactional consistency and unique constraints",
                    "Duplicate write and corruption resistance",
                ],
                [
                    "src/aws_local_audit/models.py",
                    "src/aws_local_audit/services/workbench.py",
                    "src/aws_local_audit/services/lifecycle.py",
                    "alembic/",
                ],
                "The schema has extensive unique constraints, lifecycle policies are enforced in services, and the workbook now preserves scoped flavor-linked records instead of overwriting the wrong rows.",
                ["There is still no formal optimistic-locking/version column strategy for concurrent editors."],
                ["Add explicit versioning or row-lock strategies for concurrent grid edits and background writes."],
                implemented_state="implemented",
            ),
            self._subarea(
                "1.4 Test effectiveness for correctness",
                3.7,
                "High",
                [
                    "Critical flows have unit, regression, and smoke evidence",
                    "Known bug fixes receive regression tests",
                    "System can be validated end-to-end",
                ],
                [
                    "testing/tests/",
                    "testing/qa/run_wsl.sh",
                    "testing/qa/reports/latest.json",
                    "scripts/run_e2e_tests.sh",
                ],
                "The repository currently passes 54 automated tests and the 5-check QA harness, including CLI and workspace smoke validation.",
                ["There is no coverage percentage gate and some UI behavior is still validated indirectly through smoke tests rather than richer browser assertions."],
                ["Add browser-level interaction tests for the most important workbook and assessment journeys."],
                implemented_state="implemented",
            ),
        ]
        return self._dimension(
            "Functional Correctness & Requirements Coverage",
            subareas,
            strengths=[
                "Critical GRC flows are implemented across workbook, imports, evidence, questionnaires, and assessments.",
                "Regression and QA harness coverage is materially stronger than earlier iterations.",
            ],
            gaps=[
                "Formal requirement traceability is still manual.",
                "Concurrent edit safety is not yet explicitly enforced.",
            ],
            improvements=[
                "Introduce requirement IDs and acceptance mappings.",
                "Add browser-level end-to-end scenarios for the main user journeys.",
            ],
        )

    def _usability_dimension(self) -> dict:
        subareas = [
            self._subarea(
                "2.1 Interaction completeness",
                3.9,
                "Medium",
                ["Users can create, review, update, and export key objects", "Navigation avoids dead ends on core workflows"],
                [
                    "workspace/control_framework_studio_v2.py",
                    "workspace/portfolio_center.py",
                    "workspace/questionnaire_center.py",
                    "src/aws_local_audit/services/asset_catalog.py",
                ],
                "The workbook-centered control studio, asset catalog CRUD flows, and scoped portfolio/questionnaire pages now cover the primary practitioner interactions.",
                ["Not every deep workflow is yet fully editable from one grid surface."],
                ["Continue migrating specialized maintenance flows into the same workbook/list interaction patterns."],
                implemented_state="implemented",
            ),
            self._subarea(
                "2.2 Validation and input quality",
                3.5,
                "Medium",
                ["Invalid input is handled cleanly", "Required fields are explained", "Unsafe input is rejected gracefully"],
                [
                    "workspace/ui_support.py",
                    "src/aws_local_audit/services/workbench.py",
                    "src/aws_local_audit/services/control_studio_workbook.py",
                    "src/aws_local_audit/services/validation.py",
                    "src/aws_local_audit/services/product_about.py",
                ],
                "The platform now has a shared validation layer for practitioner feedback and workspace authentication, which is a stronger baseline than purely ad hoc field checks.",
                ["Validation is still not yet centralized across every major workbook and import form."],
                ["Extend shared validation to workbook imports, organization/product forms, and questionnaire intake."],
                implemented_state="implemented",
            ),
            self._subarea(
                "2.3 Error handling and recoverability",
                4.0,
                "High",
                ["Exceptions are caught", "Raw failures are not shown as the default user outcome", "Users receive recovery guidance"],
                ["workspace/app.py", "workspace/ui_support.py", "testing/qa/reports/latest.json"],
                "Workspace startup and page rendering are wrapped safely, and guided fallback messaging replaces unhandled page crashes on the main operator path.",
                ["Technical details are still present in expanders, which is useful for support but not ideal for every operator."],
                ["Add a cleaner support-code reference model for user-facing errors and keep raw exception details operator-restricted."],
                implemented_state="implemented",
            ),
            self._subarea(
                "2.4 Accessibility and interaction consistency",
                2.5,
                "Low",
                ["Labels and controls are meaningful", "Interaction patterns are reused coherently", "Accessibility basics are considered"],
                ["workspace/app.py", "workspace/ux_redesign.py", "workspace/control_framework_studio_v2.py"],
                "The workspace uses consistent visual patterns and labels, but there is no direct accessibility test evidence, keyboard audit, or semantic accessibility review.",
                ["Accessibility is largely inferred from Streamlit defaults rather than measured."],
                ["Add accessibility checks, keyboard-navigation testing, and explicit interaction guidance for screen-reader compatibility."],
                implemented_state="partially implemented",
            ),
            self._subarea(
                "2.5 User workflow efficiency",
                3.8,
                "Medium",
                ["Primary tasks can be completed with reasonable steps", "Long-running actions provide status", "Users are guided through multi-step flows"],
                ["workspace/control_framework_studio_v2.py", "workspace/help_center", "workspace/setup_center.py", "workspace/operations_workspace.py"],
                "The workbook tabs materially reduce navigation friction, and setup guidance plus runbooks now direct users to the exact missing step.",
                ["Some setup still spans Portfolio, Operations, and Studio rather than staying inside one continuous guided experience."],
                ["Add more in-context creation dialogs from the workbook when a required organization, product, or binding is missing."],
                implemented_state="implemented",
            ),
        ]
        return self._dimension(
            "Usability & User Interaction Quality",
            subareas,
            strengths=[
                "The main control work is now workbook-first and operator-facing.",
                "User-facing errors are handled much more safely than before.",
            ],
            gaps=[
                "Formal accessibility evidence is weak.",
                "Validation rules are not yet centrally modeled for the UI.",
            ],
            improvements=[
                "Add schema-driven validation and richer in-context creation flows.",
                "Run an accessibility and keyboard-navigation hardening pass.",
            ],
        )

    def _reliability_dimension(self, qa_report: dict) -> dict:
        subareas = [
            self._subarea(
                "3.1 Failure handling",
                3.2,
                "Medium",
                ["Timeouts, retries, and fallbacks exist where appropriate", "Failures do not cascade unnecessarily"],
                ["src/aws_local_audit/services/platform_foundation.py", "src/aws_local_audit/integrations/confluence.py", "workspace/app.py"],
                "Circuit-breaker and idempotency foundations exist, and workspace failures are caught safely, but not every integration path uses strong bounded retries or graceful degradation patterns.",
                ["Retry and degradation strategies are still uneven across integrations."],
                ["Standardize timeout, retry, and fallback policies for all external calls."],
                implemented_state="partially implemented",
            ),
            self._subarea(
                "3.2 State safety and idempotency",
                3.4,
                "Medium",
                ["Repeated requests do not cause harmful duplication", "Concurrency hazards are mitigated"],
                ["src/aws_local_audit/services/platform_foundation.py", "src/aws_local_audit/services/control_studio_workbook.py", "src/aws_local_audit/services/workbench.py"],
                "The platform has an external-call idempotency ledger and stable scoped codes, but it still lacks explicit concurrency controls for simultaneous workbook edits or background execution.",
                ["Concurrent writes remain a real risk area under multi-user usage."],
                ["Add row versioning or locking for critical mutable records."],
                implemented_state="partially implemented",
            ),
            self._subarea(
                "3.3 Observed reliability evidence",
                3.9,
                "High",
                ["Health signals exist", "Runtime reliability can be observed", "Failure scenarios are exercised"],
                [
                    "testing/qa/reports/latest.json",
                    "src/aws_local_audit/services/platform_foundation.py",
                    "src/aws_local_audit/services/observability.py",
                    "logs/my_grc.log",
                ],
                "The platform now exposes metrics and trace summaries in addition to structured logs and repeatable QA evidence.",
                ["Metrics and traces are local-file based today and do not yet feed external alerting."],
                ["Add alerting and longer-term telemetry sinks on top of the current observability layer."],
                implemented_state="implemented",
            ),
            self._subarea(
                "3.4 Backup, restore, rollback, and recovery",
                3.4,
                "Medium",
                ["Rollback path exists", "Recovery is documented and testable", "Migration reversibility exists where relevant"],
                [
                    "alembic/",
                    "scripts/ubuntu_validate.sh",
                    "Dockerfile",
                    "src/aws_local_audit/services/backup_restore.py",
                    "testing/tests/test_backup_restore.py",
                ],
                "The platform now has real backup creation, verification, and restore mechanics with regression coverage.",
                ["Recovery drills and release rollback exercises are still not yet part of the standard operating routine."],
                ["Add documented recovery drills and run them on a schedule."],
                implemented_state="implemented",
            ),
            self._subarea(
                "3.5 Performance robustness",
                2.5,
                "Low",
                ["Load-sensitive areas are identified", "Resource-intensive operations are controlled"],
                ["workspace/control_framework_studio_v2.py", "src/aws_local_audit/services/asset_catalog.py"],
                "There is no performance benchmark evidence yet, and several grid/list views are still effectively full-table operator surfaces.",
                ["Performance under larger datasets is largely unmeasured."],
                ["Add pagination, batching, and performance tests for workbook and catalog screens."],
                implemented_state="partially implemented",
            ),
        ]
        return self._dimension(
            "Reliability, Resilience & Recovery",
            subareas,
            strengths=[
                "Health-oriented QA evidence is repeatable and green.",
                "Failure containment is better than ad hoc thanks to error boundaries, resilience utilities, and recovery mechanics.",
            ],
            gaps=[
                "Performance is still not directly measured.",
                "Recovery drills are implemented as mechanics but not yet proven as an operating routine.",
            ],
            improvements=[
                "Add stronger retry policies and larger-dataset performance validation.",
                "Run documented recovery drills on a defined cadence.",
            ],
        )

    def _security_dimension(self, qa_report: dict) -> dict:
        subareas = [
            self._subarea(
                "4.1 Authentication and authorization",
                3.6,
                "Medium",
                ["Authentication is appropriate", "Authorization is enforced server-side", "Least privilege is supported"],
                [
                    "src/aws_local_audit/services/access_control.py",
                    "src/aws_local_audit/services/workspace_auth.py",
                    "workspace/app.py",
                    "testing/tests/test_access_control.py",
                    "testing/tests/test_workspace_auth.py",
                ],
                "RBAC and scoped authorization are implemented in the backend, and the workspace now has a first-class local authentication gate for offline operation.",
                ["The authentication layer is local-password based today and does not yet integrate with enterprise SSO or OIDC."],
                ["Add SSO or OIDC federation and bind UI actions more deeply to role checks."],
                implemented_state="implemented",
            ),
            self._subarea(
                "4.2 Input/output security and secure coding",
                3.3,
                "Medium",
                ["Inputs are validated", "Dangerous execution patterns are controlled", "Injection paths are minimized"],
                ["src/aws_local_audit/services/control_studio_workbook.py", "src/aws_local_audit/services/script_modules.py", "testing/qa/security_scan.py"],
                "The built-in security scan is clean and most data access uses SQLAlchemy models, but script-module execution and imported file handling remain sensitive areas that deserve stricter controls.",
                ["Some extensibility surfaces still depend on disciplined operators rather than hard enforcement."],
                ["Add stronger validation and allow-listing for script modules and import manifests."],
                implemented_state="partially implemented",
            ),
            self._subarea(
                "4.3 Secrets and sensitive data handling",
                3.8,
                "High",
                ["Secrets are externalized and protected", "Sensitive data is not leaked casually", "Encryption is used where needed"],
                ["src/aws_local_audit/security.py", "src/aws_local_audit/services/security.py", "testing/tests/test_security.py"],
                "Evidence payload encryption, secret metadata, and secure connector flows are implemented and regression-tested, which is materially stronger than a configuration-file secret pattern.",
                ["Secret rotation and operational governance still need stronger lifecycle automation."],
                ["Add explicit key rotation and retention procedures for stored secrets and evidence keys."],
                implemented_state="implemented",
            ),
            self._subarea(
                "4.4 Dependency and supply-chain hygiene",
                3.2,
                "Medium",
                ["Dependencies are known", "Vulnerabilities can be detected", "Build provenance is reasonable"],
                ["pyproject.toml", "scripts/docker_scan.sh", ".github/workflows/ci.yml", "scripts/run_release_gates.sh"],
                "Dependencies are declared, scanning paths exist, and the release-gate script now includes a dependency-audit hook when the tool is installed in the environment.",
                ["Supply-chain scanning is stronger, but provenance signing and mandatory attestation are still not implemented."],
                ["Make dependency audit mandatory in all managed CI environments and add provenance attestation later."],
                implemented_state="partially implemented",
            ),
            self._subarea(
                "4.5 Security testing and auditability",
                3.6,
                "High",
                ["Security-relevant actions are auditable", "Security tests exist", "Remediation is observable"],
                ["testing/qa/reports/latest.json", "logs/my_grc-audit.log", "src/aws_local_audit/logging_utils.py"],
                "Structured audit logs, lifecycle evidence, and the static security scan provide meaningful auditability and repeatable checks.",
                ["Security testing is still mostly static and not yet extended into dynamic abuse-case scenarios."],
                ["Add abuse-case and privileged-action security tests."],
                implemented_state="implemented",
            ),
            self._subarea(
                "4.6 Privacy and data governance",
                2.5,
                "Medium",
                ["Sensitive data flows are identifiable", "Retention and deletion are implementable", "Unnecessary exposure is minimized"],
                ["src/aws_local_audit/models.py", "workspace/about_center.py", "workspace/questionnaire_center.py"],
                "The data model is explicit enough to reason about stored information, but privacy-specific retention, deletion, and export governance are not yet first-class product features.",
                ["Privacy governance is still more inferred than enforced."],
                ["Add retention/deletion policies and data-governance views for sensitive records."],
                implemented_state="partially implemented",
            ),
        ]
        return self._dimension(
            "Security, Privacy & Trustworthiness",
            subareas,
            strengths=[
                "Secrets, evidence protection, and workspace access are materially stronger than a typical internal tool baseline.",
                "Audit logging is built into sensitive workflows.",
            ],
            gaps=[
                "Enterprise SSO or OIDC is still missing.",
                "Privacy governance and full supply-chain enforcement remain incomplete.",
            ],
            improvements=[
                "Add enterprise SSO or OIDC and stronger role-bound UI enforcement.",
                "Introduce explicit privacy lifecycle controls.",
            ],
        )

    def _operability_dimension(self, qa_report: dict) -> dict:
        subareas = [
            self._subarea(
                "5.1 Build and deployment readiness",
                3.9,
                "High",
                ["Builds are reproducible", "Deployment steps are scriptable", "Migration and release steps are controlled"],
                ["pyproject.toml", "Dockerfile", "compose.yaml", "scripts/run_e2e_tests.sh", "scripts/run_release_gates.sh", ".github/workflows/ci.yml"],
                "The project has reproducible install/build artifacts, Docker assets, migrations, and a CI path aligned to the active release-gate script.",
                ["There is still no full automated deployment pipeline to a managed environment."],
                ["Add environment-specific deploy workflows and rollback automation."],
                implemented_state="implemented",
            ),
            self._subarea(
                "5.2 Observability and supportability",
                3.8,
                "Medium",
                ["Logs and health signals exist", "Incidents can be diagnosed without code changes"],
                [
                    "src/aws_local_audit/logging_utils.py",
                    "src/aws_local_audit/services/observability.py",
                    "src/aws_local_audit/services/platform_foundation.py",
                    "workspace/ux_redesign.py",
                    "testing/tests/test_observability.py",
                ],
                "Structured logs, metrics, traces, and health summaries are now all present and inspectable without code changes.",
                ["Observability is still local-file oriented and does not yet feed an external monitoring platform."],
                ["Add export or shipping paths for metrics, traces, and alerts."],
                implemented_state="implemented",
            ),
            self._subarea(
                "5.3 Code quality and maintainability",
                3.5,
                "Medium",
                ["Structure is modular", "Tests support safe change", "Technical debt is visible"],
                ["src/aws_local_audit/services/", "workspace/", "testing/tests/", "documentation/design/"],
                "The architecture is service-oriented and much more modular than earlier iterations, with good documentation and regression coverage.",
                ["There is still meaningful debt in deprecated datetime usage and a large number of operator-facing modules."],
                ["Continue splitting complex workspace modules and remove deprecated time handling consistently."],
                implemented_state="implemented",
            ),
            self._subarea(
                "5.4 Configuration and environment safety",
                3.8,
                "Medium",
                ["Config is externalized", "Environment-specific behavior is controlled", "Dangerous defaults are avoided"],
                [
                    ".env.example",
                    ".streamlit/config.toml",
                    "src/aws_local_audit/config.py",
                    "src/aws_local_audit/services/platform_foundation.py",
                    "src/aws_local_audit/services/workspace_auth.py",
                    "src/aws_local_audit/services/backup_restore.py",
                ],
                "Configuration is externalized, and the platform now carries explicit settings for workspace authentication, backup directories, and session controls.",
                ["Environment profiles still need stronger separation for larger staged deployments."],
                ["Add environment bundles and production-specific config validation."],
                implemented_state="implemented",
            ),
            self._subarea(
                "5.5 Documentation and handover quality",
                4.1,
                "High",
                ["Architecture is understandable", "Run instructions exist", "Operator guidance is available"],
                ["README.md", "documentation/others/WORKFLOW_1_FIRST_FRAMEWORK_PILOT.md", "documentation/others/WORKFLOW_2_FULL_SYSTEM_OPERATIONS.md"],
                "The project now has strong operator runbooks, setup instructions, and design documentation for a growing internal platform.",
                ["Documentation quality is stronger than operational enforcement in some areas."],
                ["Keep docs synchronized with release notes and the About center on every release."],
                implemented_state="implemented",
            ),
            self._subarea(
                "5.6 Change safety",
                3.7,
                "Medium",
                ["Changes can be introduced incrementally", "Blast radius can be limited", "Release readiness can be evaluated"],
                [
                    "src/aws_local_audit/services/platform_foundation.py",
                    ".github/workflows/ci.yml",
                    "testing/qa/run_wsl.sh",
                    "scripts/run_release_gates.sh",
                    "src/aws_local_audit/services/backup_restore.py",
                ],
                "Feature flags, QA gating, release notes, and a single release-gate script now exist, and the platform also has database backup/restore mechanics for safer change handling.",
                ["There is still no canary, blue-green, or managed environment promotion workflow."],
                ["Add staged deployment and rollback patterns for production releases."],
                implemented_state="implemented",
            ),
        ]
        return self._dimension(
            "Operability, Maintainability & Release Readiness",
            subareas,
            strengths=[
                "Build, test, QA, and release-gate paths are now explicit and repeatable.",
                "Documentation quality is strong for an internal platform of this scope.",
            ],
            gaps=[
                "Observability still needs external shipping and alerting.",
                "Deployment promotion and rollback are not fully automated.",
            ],
            improvements=[
                "Add CI-enforced deployment stages and stronger managed-environment promotion.",
                "Add alerting and external observability sinks on top of current metrics and traces.",
            ],
        )

    def _dimension(self, name: str, subareas: list[dict], *, strengths: list[str], gaps: list[str], improvements: list[str]) -> dict:
        score = round(sum(item["score"] for item in subareas) / len(subareas), 2)
        confidence = "High" if all(item["confidence"] == "High" for item in subareas) else "Medium"
        implemented_state = "implemented" if score >= 3.5 else "partially implemented"
        return {
            "name": name,
            "score": score,
            "confidence": confidence,
            "implemented_state": implemented_state,
            "subareas": subareas,
            "strengths": strengths,
            "gaps": gaps,
            "improvements": improvements,
        }

    @staticmethod
    def _subarea(name: str, score: float, confidence: str, criteria: list[str], evidence: list[str], rationale: str, gaps: list[str], improvements: list[str], *, implemented_state: str) -> dict:
        return {
            "name": name,
            "score": round(score, 2),
            "confidence": confidence,
            "criteria": criteria,
            "evidence": evidence,
            "rationale": rationale,
            "gaps": gaps,
            "improvements": improvements,
            "implemented_state": implemented_state,
        }

    def _top_release_blockers(self, dimensions: list[dict]) -> list[dict]:
        blockers = []
        for dimension in dimensions:
            for subarea in dimension["subareas"]:
                if subarea["score"] >= 3.0:
                    continue
                blockers.append(
                    {
                        "title": subarea["name"],
                        "dimension": dimension["name"],
                        "score": subarea["score"],
                        "confidence": subarea["confidence"],
                        "impact": subarea["gaps"][0] if subarea["gaps"] else subarea["rationale"],
                        "action": subarea["improvements"][0] if subarea["improvements"] else "Harden this area before release.",
                        "evidence": subarea["evidence"],
                    }
                )
        curated = [
            {
                "title": "Workspace authentication is still local-only",
                "dimension": "Security, Privacy & Trustworthiness",
                "score": 3.6,
                "confidence": "Medium",
                "impact": "The operator UI is now protected locally, but it still lacks enterprise SSO or OIDC federation.",
                "action": "Add enterprise SSO or OIDC and deeper role-bound UI enforcement.",
                "evidence": ["src/aws_local_audit/services/workspace_auth.py", "workspace/app.py"],
            },
            {
                "title": "Recovery and rollback are not yet proven",
                "dimension": "Reliability, Resilience & Recovery",
                "score": 3.0,
                "confidence": "Medium",
                "impact": "Backup and restore mechanics now exist, but drills and release rollback routines are not yet an enforced practice.",
                "action": "Document and test backup, restore, and release rollback drills.",
                "evidence": ["src/aws_local_audit/services/backup_restore.py", "scripts/ubuntu_validate.sh", "Dockerfile"],
            },
            {
                "title": "Accessibility and keyboard evidence is weak",
                "dimension": "Usability & User Interaction Quality",
                "score": 2.5,
                "confidence": "Low",
                "impact": "Accessibility is still inferred from Streamlit defaults instead of being measured.",
                "action": "Run accessibility checks and add keyboard-navigation validation for core pages.",
                "evidence": ["workspace/app.py", "workspace/control_framework_studio_v2.py"],
            },
        ]
        known_titles = {item["title"] for item in blockers}
        blockers.extend(item for item in curated if item["title"] not in known_titles)
        blockers.sort(key=lambda item: item["score"])
        return blockers[:10]

    def _top_business_risks(self, dimensions: list[dict]) -> list[dict]:
        return [
            {
                "risk": "User trust can still be damaged by local-only workspace authentication.",
                "likely_consequence": "Approvals and accountability remain weaker than a federated enterprise identity model.",
                "evidence": ["workspace/app.py", "src/aws_local_audit/services/workspace_auth.py"],
                "confidence": "Medium",
            },
            {
                "risk": "Large workbook datasets can degrade operator productivity.",
                "likely_consequence": "Control maintenance becomes slow and error-prone as the registry grows.",
                "evidence": ["workspace/control_framework_studio_v2.py", "src/aws_local_audit/services/control_studio_workbook.py"],
                "confidence": "Medium",
            },
            {
                "risk": "Recovery procedures are not exercised enough for incident confidence.",
                "likely_consequence": "A bad migration or host failure could stall operations longer than acceptable.",
                "evidence": ["alembic/", "scripts/ubuntu_validate.sh"],
                "confidence": "Medium",
            },
            {
                "risk": "Privacy retention and deletion rules remain implicit.",
                "likely_consequence": "Questionnaires, contacts, and audit artifacts may outlive intended retention windows.",
                "evidence": ["src/aws_local_audit/models.py", "workspace/questionnaire_center.py"],
                "confidence": "Medium",
            },
            {
                "risk": "Metrics and traces are still local-file oriented.",
                "likely_consequence": "Operational failures may be harder to centralize and alert on at scale.",
                "evidence": ["src/aws_local_audit/logging_utils.py", "src/aws_local_audit/services/observability.py"],
                "confidence": "High",
            },
        ]

    def _top_engineering_debt(self) -> list[dict]:
        return [
            {
                "item": "Timezone-naive datetime.utcnow usage",
                "impact": "Creates deprecation noise and future compatibility risk.",
                "evidence": ["testing/qa/reports/latest.json", "src/aws_local_audit/logging_utils.py"],
            },
            {
                "item": "Large workspace modules",
                "impact": "UI changes still have a wider blast radius than ideal.",
                "evidence": ["workspace/app.py", "workspace/control_framework_studio_v2.py", "workspace/ux_redesign.py"],
            },
            {
                "item": "Validation is only partially centralized",
                "impact": "Input quality rules are improving, but still not uniformly enforced across the whole workspace.",
                "evidence": ["src/aws_local_audit/services/control_studio_workbook.py", "src/aws_local_audit/services/validation.py"],
            },
            {
                "item": "No browser-level interaction test suite",
                "impact": "Complex UI regressions can slip past smoke coverage.",
                "evidence": ["testing/qa/reports/latest.json", "scripts/run_e2e_tests.sh"],
            },
            {
                "item": "Release pipeline stops at release-gate validation",
                "impact": "Promotion and deployment confidence are better, but still partly manual.",
                "evidence": [".github/workflows/ci.yml", "scripts/run_release_gates.sh", "Dockerfile", "compose.yaml"],
            },
        ]

    def _fragile_dependencies(self) -> list[dict]:
        return [
            {
                "dependency": "Streamlit runtime",
                "fragility": "The operator UI depends heavily on Streamlit interaction patterns and smoke validation rather than richer browser tests.",
                "evidence": ["workspace/app.py", "workspace/control_framework_studio_v2.py", "testing/qa/reports/latest.json"],
            },
            {
                "dependency": "Ubuntu WSL host integration",
                "fragility": "Validation output still shows an external WSL mount warning unrelated to the app but noisy for operators.",
                "evidence": ["documentation/releases/CHANGELOG.yaml", "testing/qa/reports/latest.json"],
            },
            {
                "dependency": "Confluence external API",
                "fragility": "Publishing relies on an external platform without full routing, retry, and update policy hardening yet.",
                "evidence": ["src/aws_local_audit/integrations/confluence.py", "src/aws_local_audit/services/security.py"],
            },
        ]

    def _manual_heroics(self) -> list[dict]:
        return [
            {
                "area": "Recovery operations",
                "detail": "Backup and restore mechanics exist, but formal drills are still not routine.",
                "evidence": ["src/aws_local_audit/services/backup_restore.py", "scripts/ubuntu_validate.sh"],
            },
            {
                "area": "Environment promotion",
                "detail": "Build validation is automated, but deployment promotion remains outside a full managed pipeline.",
                "evidence": [".github/workflows/ci.yml", "compose.yaml"],
            },
            {
                "area": "Accessibility confidence",
                "detail": "Accessibility quality still depends on operator observation rather than automated checks.",
                "evidence": ["workspace/app.py", "workspace/control_framework_studio_v2.py"],
            },
        ]

    def _trust_risks(self) -> list[dict]:
        return [
            {
                "risk": "Operators can see technical detail expanders on caught errors.",
                "consequence": "Practitioners may feel the system is unstable or too technical when something goes wrong.",
                "evidence": ["workspace/ui_support.py", "workspace/app.py"],
            },
            {
                "risk": "Current runtime lacks first-class identity for the workspace itself.",
                "consequence": "Trust improves with local workspace authentication, but federated accountability is still not there.",
                "evidence": ["workspace/app.py", "src/aws_local_audit/services/workspace_auth.py"],
            },
        ]

    def _scaling_risks(self) -> list[dict]:
        return [
            {
                "risk": "Workbook and catalog views still operate as broad in-memory tables.",
                "consequence": "Performance and interaction quality may degrade as control and evidence inventories grow.",
                "evidence": ["workspace/control_framework_studio_v2.py", "src/aws_local_audit/services/asset_catalog.py"],
            },
            {
                "risk": "Background execution is not yet a durable worker model.",
                "consequence": "Higher execution volume will rely on interactive sessions and local process stability.",
                "evidence": ["src/aws_local_audit/services/assessments.py", "src/aws_local_audit/services/evidence.py"],
            },
        ]

    def _quick_wins(self) -> list[dict]:
        return [
            {
                "title": "Move datetime handling to timezone-aware UTC",
                "why": "Removes current warnings and improves temporal correctness.",
            },
            {
                "title": "Add an accessibility checklist to the QA harness",
                "why": "Raises confidence in the operator experience quickly.",
            },
            {
                "title": "Add a release rollback runbook",
                "why": "Closes a high-visibility recovery gap without major architecture change.",
            },
            {
                "title": "Add CI vulnerability scan gating",
                "why": "Improves supply-chain readiness with relatively low implementation cost.",
            },
        ]

    def _structural_improvements(self) -> list[dict]:
        return [
            {
                "title": "Introduce workspace authentication and SSO",
                "why": "Builds on the new local authentication gate and moves the platform toward federated trust.",
            },
            {
                "title": "Add metrics, traces, and alertable health endpoints",
                "why": "Builds on the new observability summaries and moves the platform toward real operational telemetry.",
            },
            {
                "title": "Adopt browser-level interaction testing for workbook and assessment flows",
                "why": "Protects the most complex practitioner workflows from regression.",
            },
            {
                "title": "Add durable background workers and retryable jobs",
                "why": "Required for resilient recurring assessments and larger-scale evidence collection.",
            },
        ]

    def _missing_evidence(self) -> list[dict]:
        return [
            {
                "gap": "No browser-level usability or accessibility test evidence",
                "effect": "Usability and accessibility scores stay below a strong-confidence level.",
            },
            {
                "gap": "No backup or restore drill evidence",
                "effect": "Recovery readiness remains only partially demonstrated.",
            },
            {
                "gap": "No production-like performance benchmarks",
                "effect": "Performance robustness is estimated through proxy indicators instead of direct measurement.",
            },
        ]

    def _improvement_plan(self, release_blockers: list[dict]) -> dict:
        blocker_titles = [item["title"] for item in release_blockers[:3]]
        return {
            "immediate": [
                "Address the current release blockers at the top of the list: " + "; ".join(blocker_titles) if blocker_titles else "Review current blockers and assign owners.",
                "Align pyproject version, release notes, and About-center messaging on every release.",
                "Keep the QA harness green on every change and treat new warnings as debt to close quickly.",
            ],
            "days_30": [
                "Add enterprise SSO or OIDC and bind privileged actions more deeply to authenticated principals.",
                "Add rollback and restore runbooks, then validate them in a controlled drill.",
                "Add CI-enforced vulnerability scanning and dependency gating.",
            ],
            "days_60": [
                "Extend shared validation schemas across workbook edits, imports, and forms.",
                "Add browser-level regression coverage for control workbook, questionnaire, and assessment journeys.",
                "Add alerting or export sinks for the current metrics and traces.",
            ],
            "days_90": [
                "Add durable background jobs for evidence and recurring assessments.",
                "Add privacy lifecycle capabilities for retention, deletion, and export of sensitive records.",
                "Introduce performance controls such as pagination, batching, and larger-dataset validation.",
            ],
        }

    @staticmethod
    def _deployment_verdict(overall_score: float, release_blockers: list[dict]) -> dict:
        blocker_count = len(release_blockers)
        if overall_score >= 4.2 and blocker_count == 0:
            status = "Strong readiness"
            rationale = "The product demonstrates strong measurable maturity with no active blockers."
        elif overall_score >= 3.6 and blocker_count <= 2:
            status = "Ready with controlled risk"
            rationale = "The product is usable and well-governed, with a small number of controlled residual risks."
        elif overall_score >= 3.0:
            status = "Conditionally ready with blockers"
            rationale = "The product is deployable for controlled use, but several release blockers still require active management."
        else:
            status = "Not ready"
            rationale = "Key operational, security, or reliability controls are still too weak for deployment."
        return {"status": status, "rationale": rationale, "blocker_count": blocker_count}

    @staticmethod
    def _load_json(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).exists()

    def _all_exist(self, *relative_paths: str) -> bool:
        return all(self._exists(item) for item in relative_paths)
