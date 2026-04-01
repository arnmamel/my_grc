from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from aws_local_audit.models import (
    AISuggestion,
    AssessmentRun,
    AssessmentSchedule,
    AccessRole,
    AwsCliProfile,
    CircuitBreakerState,
    ConfluenceConnection,
    CustomerQuestionnaireItem,
    EvidenceCollectionPlan,
    EvidenceItem,
    IdentityPrincipal,
    RoleAssignment,
    UnifiedControlMapping,
)
from aws_local_audit.services.access_control import AccessControlService


class ReviewQueueService:
    def __init__(self, session):
        self.session = session
        self.root = Path(__file__).resolve().parents[3]

    def summary(self) -> dict:
        items = self.items()
        categories: dict[str, int] = {}
        priorities: dict[str, int] = {}
        for item in items:
            categories[item["category"]] = categories.get(item["category"], 0) + 1
            priorities[item["priority"]] = priorities.get(item["priority"], 0) + 1
        return {
            "total": len(items),
            "categories": categories,
            "priorities": priorities,
            "top_items": items[:10],
        }

    def items(self) -> list[dict]:
        rows = []
        rows.extend(self._mapping_items())
        rows.extend(self._evidence_plan_items())
        rows.extend(self._questionnaire_items())
        rows.extend(self._evidence_items())
        rows.extend(self._assessment_items())
        rows.extend(self._schedule_items())
        rows.extend(self._aws_profile_items())
        rows.extend(self._confluence_items())
        rows.extend(self._circuit_breaker_items())
        rows.extend(self._rbac_items())
        rows.extend(self._ai_items())
        rows.extend(self._platform_items())
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(
            rows,
            key=lambda item: (priority_order.get(item["priority"], 99), item["category"], item["title"]),
        )

    def _mapping_items(self) -> list[dict]:
        rows = []
        mappings = self.session.scalars(
            select(UnifiedControlMapping).where(UnifiedControlMapping.approval_status != "approved")
        ).all()
        for item in mappings:
            rows.append(
                {
                    "category": "mapping_review",
                    "priority": "high" if item.approval_status == "rejected" else "medium",
                    "status": item.approval_status,
                    "title": f"{item.framework.code} {item.control.control_id} -> {item.unified_control.code}",
                    "reference": str(item.id),
                    "detail": item.rationale or item.approval_notes or "Mapping awaits human review.",
                }
            )
        return rows

    def _evidence_plan_items(self) -> list[dict]:
        rows = []
        plans = self.session.scalars(
            select(EvidenceCollectionPlan).where(EvidenceCollectionPlan.lifecycle_status.not_in(["approved", "active", "ready", "published"]))
        ).all()
        for item in plans:
            scope = item.control.control_id if item.control else (item.unified_control.code if item.unified_control else item.name)
            rows.append(
                {
                    "category": "evidence_plan_review",
                    "priority": "medium",
                    "status": item.lifecycle_status,
                    "title": f"{item.plan_code} ({scope})",
                    "reference": item.plan_code,
                    "detail": item.instructions[:180] if item.instructions else "Evidence plan lifecycle requires review.",
                }
            )
        return rows

    def _questionnaire_items(self) -> list[dict]:
        rows = []
        items = self.session.scalars(
            select(CustomerQuestionnaireItem).where(CustomerQuestionnaireItem.review_status != "approved")
        ).all()
        for item in items:
            rows.append(
                {
                    "category": "questionnaire_review",
                    "priority": "medium",
                    "status": item.review_status,
                    "title": f"{item.questionnaire.name}: {item.question_text[:80]}",
                    "reference": str(item.id),
                    "detail": f"Confidence {item.confidence:.2f}. {item.rationale[:140]}",
                }
            )
        return rows

    def _evidence_items(self) -> list[dict]:
        rows = []
        evidence_items = self.session.scalars(
            select(EvidenceItem).where(
                EvidenceItem.lifecycle_status.in_(
                    ["awaiting_collection", "pending_review", "collection_error", "collector_missing"]
                )
            )
        ).all()
        for item in evidence_items:
            priority = (
                "high"
                if item.lifecycle_status in {"collection_error", "collector_missing"}
                or item.status in {"plan_missing", "plan_pending_review"}
                else "medium"
            )
            rows.append(
                {
                    "category": "evidence_review",
                    "priority": priority,
                    "status": item.lifecycle_status,
                    "title": f"{item.control.framework.code} {item.control.control_id}",
                    "reference": str(item.id),
                    "detail": item.summary[:180],
                }
            )
        return rows

    def _assessment_items(self) -> list[dict]:
        rows = []
        runs = self.session.scalars(select(AssessmentRun).where(AssessmentRun.review_status != "approved")).all()
        for item in runs:
            rows.append(
                {
                    "category": "assessment_review",
                    "priority": "high" if item.status != "completed" or item.assurance_status == "needs_evidence" else "medium",
                    "status": item.review_status,
                    "title": f"{item.framework.code} assessment {item.started_at:%Y-%m-%d %H:%M}",
                    "reference": str(item.id),
                    "detail": f"Score {item.score}%. Assurance status: {item.assurance_status}.",
                }
            )
        return rows

    def _schedule_items(self) -> list[dict]:
        rows = []
        schedules = self.session.scalars(
            select(AssessmentSchedule).where(AssessmentSchedule.last_run_status.in_(["error"]))
        ).all()
        for item in schedules:
            rows.append(
                {
                    "category": "schedule_failure",
                    "priority": "critical",
                    "status": item.last_run_status,
                    "title": item.name,
                    "reference": str(item.id),
                    "detail": item.last_run_message or "Scheduled run failed and needs operator attention.",
                }
            )
        return rows

    def _aws_profile_items(self) -> list[dict]:
        rows = []
        profiles = self.session.scalars(
            select(AwsCliProfile).where(AwsCliProfile.status == "active")
        ).all()
        for item in profiles:
            if item.last_validation_status == "pass":
                continue
            priority = "high" if item.last_validation_status == "error" else "medium"
            rows.append(
                {
                    "category": "aws_profile_validation",
                    "priority": priority,
                    "status": item.last_validation_status or "unknown",
                    "title": item.profile_name,
                    "reference": item.profile_name,
                    "detail": item.last_validation_message or "Profile should be validated before live evidence runs.",
                }
            )
        return rows

    def _confluence_items(self) -> list[dict]:
        rows = []
        connections = self.session.scalars(
            select(ConfluenceConnection).where(ConfluenceConnection.status == "active")
        ).all()
        for item in connections:
            if item.last_test_status == "pass":
                continue
            priority = "high" if item.last_test_status == "error" else "medium"
            rows.append(
                {
                    "category": "confluence_health",
                    "priority": priority,
                    "status": item.last_test_status or "untested",
                    "title": item.name,
                    "reference": item.name,
                    "detail": item.last_test_message or "Connection should be tested before evidence or assessment publishing.",
                }
            )
        return rows

    def _ai_items(self) -> list[dict]:
        rows = []
        suggestions = self.session.scalars(select(AISuggestion).where(AISuggestion.accepted.is_(False))).all()
        for item in suggestions:
            rows.append(
                {
                    "category": "ai_suggestion_review",
                    "priority": "low",
                    "status": "pending",
                    "title": f"{item.suggestion_type} suggestion {item.id}",
                    "reference": str(item.id),
                    "detail": f"Provider {item.provider or 'unknown'} model {item.model_name or 'unknown'} awaits governance review.",
                }
            )
        return rows

    def _circuit_breaker_items(self) -> list[dict]:
        rows = []
        circuits = self.session.scalars(select(CircuitBreakerState).where(CircuitBreakerState.state == "open")).all()
        for item in circuits:
            rows.append(
                {
                    "category": "integration_resilience",
                    "priority": "high",
                    "status": item.state,
                    "title": item.integration_key,
                    "reference": str(item.id),
                    "detail": item.last_error or "Integration circuit breaker is open and needs operator recovery.",
                }
            )
        return rows

    def _rbac_items(self) -> list[dict]:
        rows = []
        pending = self.session.scalars(
            select(RoleAssignment).where(RoleAssignment.approval_status != "approved")
        ).all()
        for item in pending:
            rows.append(
                {
                    "category": "rbac_review",
                    "priority": "high",
                    "status": item.approval_status,
                    "title": f"{item.principal.display_name} -> {item.role.name}",
                    "reference": str(item.id),
                    "detail": item.rationale or "Privileged role assignment awaits approval.",
                }
            )
        for conflict in AccessControlService(self.session).segregation_conflicts():
            rows.append(
                {
                    "category": "rbac_conflict",
                    "priority": "critical",
                    "status": "conflict",
                    "title": conflict["principal_key"],
                    "reference": ",".join(conflict["roles"]),
                    "detail": conflict["detail"],
                }
            )
        return rows

    def _platform_items(self) -> list[dict]:
        rows = []
        if not (self.root / "alembic.ini").exists():
            rows.append(
                {
                    "category": "platform_hardening",
                    "priority": "high",
                    "status": "missing",
                    "title": "Migration framework",
                    "reference": "alembic.ini",
                    "detail": "Schema migrations are not configured yet.",
                }
            )
        if not (self.root / "testing" / "tests").exists():
            rows.append(
                {
                    "category": "platform_hardening",
                    "priority": "medium",
                    "status": "missing",
                    "title": "Automated test suite",
                    "reference": "testing/tests/",
                    "detail": "Automated regression tests are missing.",
                }
            )
        if not (self.root / ".github" / "workflows" / "ci.yml").exists():
            rows.append(
                {
                    "category": "platform_hardening",
                    "priority": "medium",
                    "status": "missing",
                    "title": "CI workflow",
                    "reference": ".github/workflows/ci.yml",
                    "detail": "Add a CI workflow so build and test are the default path.",
                }
            )
        if not (self.root / "scripts" / "docker_scan.sh").exists():
            rows.append(
                {
                    "category": "platform_hardening",
                    "priority": "medium",
                    "status": "missing",
                    "title": "Container scan script",
                    "reference": "scripts/docker_scan.sh",
                    "detail": "Add an image vulnerability scan step before deployment.",
                }
            )
        role_count = self.session.scalar(select(func.count()).select_from(AccessRole)) or 0
        principal_count = self.session.scalar(select(func.count()).select_from(IdentityPrincipal)) or 0
        assignment_count = self.session.scalar(select(func.count()).select_from(RoleAssignment)) or 0
        if role_count == 0 or principal_count == 0 or assignment_count == 0:
            rows.append(
                {
                    "category": "platform_hardening",
                    "priority": "high",
                    "status": "incomplete",
                    "title": "RBAC bootstrap",
                    "reference": "identity_principals/access_roles/role_assignments",
                    "detail": "Seed roles, register principals, and approve scoped assignments to reduce phase-one access governance risk.",
                }
            )
        return rows
