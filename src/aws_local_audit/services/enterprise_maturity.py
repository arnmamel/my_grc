from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from aws_local_audit.models import (
    AISuggestion,
    AccessRole,
    AssessmentRun,
    AssessmentSchedule,
    AssessmentScriptBinding,
    AssessmentScriptModule,
    AwsCliProfile,
    ActionItem,
    Asset,
    BusinessUnit,
    CircuitBreakerState,
    ConfluenceConnection,
    Control,
    CustomerQuestionnaire,
    CustomerQuestionnaireItem,
    EvidenceCollectionPlan,
    EvidenceItem,
    FeatureFlag,
    Finding,
    Framework,
    FrameworkImportBatch,
    IdentityPrincipal,
    LifecycleEvent,
    OrganizationFrameworkBinding,
    RoleAssignment,
    Risk,
    SecretMetadata,
    UnifiedControlMapping,
)
from aws_local_audit.services.phase1_maturity import Phase1MaturityService
from aws_local_audit.services.review_queue import ReviewQueueService


class EnterpriseMaturityService:
    def __init__(self, session):
        self.session = session
        self.root = Path(__file__).resolve().parents[3]
        self.docs_root = self.root / "documentation"

    def assess(self) -> dict:
        counts = self._counts()
        phase1 = self._phase1_area()
        phase2 = self._phase2_area(counts)
        phase3 = self._phase3_area(counts)
        qualities = [
            self._security_area(counts),
            self._quality_area(counts),
            self._reliability_area(counts),
            self._integrability_area(counts),
            self._ux_area(counts),
            self._deployment_area(counts),
        ]
        phase_areas = [phase1, phase2, phase3]
        overall = round((sum(item["score"] for item in phase_areas + qualities) / (len(phase_areas) + len(qualities))), 2)
        blockers = []
        for item in phase_areas + qualities:
            blockers.extend(item["gaps"])
        return {
            "overall_score": overall,
            "target_score": 4.0,
            "phases": phase_areas,
            "qualities": qualities,
            "counts": counts,
            "top_blockers": blockers[:12],
        }

    def _counts(self) -> dict[str, float]:
        review_summary = ReviewQueueService(self.session).summary()
        path_flags = {
            "alembic_ini": (self.root / "alembic.ini").exists(),
            "alembic_dir": (self.root / "alembic").exists(),
            "dockerfile": (self.root / "Dockerfile").exists(),
            "compose": (self.root / "compose.yaml").exists() or (self.root / "docker-compose.yml").exists(),
            "streamlit_config": (self.root / ".streamlit" / "config.toml").exists(),
            "ux_redesign": (self.root / "workspace" / "ux_redesign.py").exists(),
            "asset_catalog": (self.root / "src" / "aws_local_audit" / "services" / "asset_catalog.py").exists(),
            "workspace_guidance": (self.root / "src" / "aws_local_audit" / "services" / "workspace_guidance.py").exists(),
            "platform_foundation": (self.root / "src" / "aws_local_audit" / "services" / "platform_foundation.py").exists(),
            "architecture_doc": (self.docs_root / "design" / "ARCHITECTURE_BOUNDARIES.md").exists(),
            "engineering_doc": (self.docs_root / "design" / "ENGINEERING_WORKFLOW.md").exists(),
            "operations_doc": (self.docs_root / "design" / "OPERATIONS_EXCELLENCE_BASELINE.md").exists(),
            "access_governance_doc": (self.docs_root / "design" / "ACCESS_GOVERNANCE_MODEL.md").exists(),
            "ci_workflow": (self.root / ".github" / "workflows" / "ci.yml").exists(),
            "ubuntu_script": (self.root / "scripts" / "ubuntu_bootstrap.sh").exists(),
            "ubuntu_validate": (self.root / "scripts" / "ubuntu_validate.sh").exists(),
            "docker_entrypoint": (self.root / "scripts" / "docker-entrypoint.sh").exists(),
            "docker_scan": (self.root / "scripts" / "docker_scan.sh").exists(),
            "docker_smoke": (self.root / "scripts" / "docker_smoke.sh").exists(),
            "tests": (self.root / "testing" / "tests").exists(),
        }
        total_profiles = self.session.scalar(select(func.count()).select_from(AwsCliProfile)) or 0
        validated_profiles = self.session.scalar(
            select(func.count()).select_from(AwsCliProfile).where(AwsCliProfile.last_validation_status == "pass")
        ) or 0
        total_connections = self.session.scalar(select(func.count()).select_from(ConfluenceConnection)) or 0
        healthy_connections = self.session.scalar(
            select(func.count()).select_from(ConfluenceConnection).where(ConfluenceConnection.last_test_status == "pass")
        ) or 0
        approved_mappings = self.session.scalar(
            select(func.count()).select_from(UnifiedControlMapping).where(UnifiedControlMapping.approval_status == "approved")
        ) or 0
        mappings = self.session.scalar(select(func.count()).select_from(UnifiedControlMapping)) or 0
        approved_questionnaire_items = self.session.scalar(
            select(func.count()).select_from(CustomerQuestionnaireItem).where(CustomerQuestionnaireItem.review_status == "approved")
        ) or 0
        questionnaire_items = self.session.scalar(select(func.count()).select_from(CustomerQuestionnaireItem)) or 0
        reviewed_assessments = self.session.scalar(
            select(func.count()).select_from(AssessmentRun).where(AssessmentRun.review_status == "approved")
        ) or 0
        assessments = self.session.scalar(select(func.count()).select_from(AssessmentRun)) or 0
        active_plans = self.session.scalar(
            select(func.count()).select_from(EvidenceCollectionPlan).where(
                EvidenceCollectionPlan.lifecycle_status.in_(["approved", "active", "ready", "published"])
            )
        ) or 0
        plans = self.session.scalar(select(func.count()).select_from(EvidenceCollectionPlan)) or 0
        scoped_schedules = self.session.scalar(
            select(func.count()).select_from(AssessmentSchedule).where(AssessmentSchedule.framework_binding_id.is_not(None))
        ) or 0
        schedules = self.session.scalar(select(func.count()).select_from(AssessmentSchedule)) or 0
        schedule_failures = self.session.scalar(
            select(func.count()).select_from(AssessmentSchedule).where(AssessmentSchedule.last_run_status == "error")
        ) or 0
        open_circuits = self.session.scalar(
            select(func.count()).select_from(CircuitBreakerState).where(CircuitBreakerState.state == "open")
        ) or 0
        principals = self.session.scalar(select(func.count()).select_from(IdentityPrincipal)) or 0
        roles = self.session.scalar(select(func.count()).select_from(AccessRole)) or 0
        assignments = self.session.scalar(select(func.count()).select_from(RoleAssignment)) or 0
        approved_assignments = self.session.scalar(
            select(func.count()).select_from(RoleAssignment).where(RoleAssignment.approval_status == "approved")
        ) or 0
        return {
            "frameworks": self.session.scalar(select(func.count()).select_from(Framework)) or 0,
            "controls": self.session.scalar(select(func.count()).select_from(Control)) or 0,
            "mappings": mappings,
            "approved_mappings": approved_mappings,
            "plans": plans,
            "active_plans": active_plans,
            "profiles": total_profiles,
            "validated_profiles": validated_profiles,
            "connections": total_connections,
            "healthy_connections": healthy_connections,
            "import_batches": self.session.scalar(select(func.count()).select_from(FrameworkImportBatch)) or 0,
            "script_modules": self.session.scalar(select(func.count()).select_from(AssessmentScriptModule)) or 0,
            "script_bindings": self.session.scalar(select(func.count()).select_from(AssessmentScriptBinding)) or 0,
            "evidence_items": self.session.scalar(select(func.count()).select_from(EvidenceItem)) or 0,
            "assessments": assessments,
            "reviewed_assessments": reviewed_assessments,
            "schedules": schedules,
            "scoped_schedules": scoped_schedules,
            "schedule_failures": schedule_failures,
            "questionnaires": self.session.scalar(select(func.count()).select_from(CustomerQuestionnaire)) or 0,
            "questionnaire_items": questionnaire_items,
            "approved_questionnaire_items": approved_questionnaire_items,
            "business_units": self.session.scalar(select(func.count()).select_from(BusinessUnit)) or 0,
            "assets": self.session.scalar(select(func.count()).select_from(Asset)) or 0,
            "risks": self.session.scalar(select(func.count()).select_from(Risk)) or 0,
            "findings": self.session.scalar(select(func.count()).select_from(Finding)) or 0,
            "actions": self.session.scalar(select(func.count()).select_from(ActionItem)) or 0,
            "feature_flags": self.session.scalar(select(func.count()).select_from(FeatureFlag)) or 0,
            "principals": principals,
            "roles": roles,
            "assignments": assignments,
            "approved_assignments": approved_assignments,
            "open_circuits": open_circuits,
            "bindings": self.session.scalar(select(func.count()).select_from(OrganizationFrameworkBinding)) or 0,
            "lifecycle_events": self.session.scalar(select(func.count()).select_from(LifecycleEvent)) or 0,
            "secrets": self.session.scalar(select(func.count()).select_from(SecretMetadata)) or 0,
            "ai_suggestions": self.session.scalar(select(func.count()).select_from(AISuggestion)) or 0,
            "review_total": review_summary["total"],
            "review_critical": review_summary["priorities"].get("critical", 0),
            "review_high": review_summary["priorities"].get("high", 0),
            **path_flags,
        }

    def _phase1_area(self) -> dict:
        phase1 = Phase1MaturityService(self.session).assess()
        return {
            "area": "Phase 1 Foundation",
            "score": round(min(4.0, phase1["overall_score"]), 2),
            "target": 4.0,
            "gaps": phase1["top_blockers"][:6],
        }

    def _phase2_area(self, counts: dict[str, float]) -> dict:
        score = (
            self._ratio(counts["validated_profiles"], counts["profiles"]) * 0.8
            + self._ratio(counts["healthy_connections"], counts["connections"]) * 0.6
            + self._ratio(counts["active_plans"], counts["plans"]) * 0.8
            + self._ratio(counts["reviewed_assessments"], counts["assessments"]) * 0.8
            + self._ratio(counts["approved_questionnaire_items"], counts["questionnaire_items"]) * 0.6
            + self._ratio(counts["scoped_schedules"], counts["schedules"]) * 0.4
        )
        gaps = []
        if self._ratio(counts["validated_profiles"], counts["profiles"]) < 0.7:
            gaps.append("Validate a higher proportion of AWS profiles before live evidence operations.")
        if self._ratio(counts["healthy_connections"], counts["connections"]) < 0.7:
            gaps.append("Health-check Confluence connections and fix failing destinations.")
        if self._ratio(counts["active_plans"], counts["plans"]) < 0.7:
            gaps.append("Approve more evidence plans so execution is guided by governed collection logic.")
        if self._ratio(counts["reviewed_assessments"], counts["assessments"]) < 0.6:
            gaps.append("Close assessment review loops instead of leaving runs in pending review.")
        if self._ratio(counts["approved_questionnaire_items"], counts["questionnaire_items"]) < 0.6:
            gaps.append("Increase reviewed questionnaire coverage for customer-facing assurance responses.")
        return {"area": "Phase 2 Operations", "score": round(min(4.0, 1.0 + score), 2), "target": 4.0, "gaps": gaps}

    def _phase3_area(self, counts: dict[str, float]) -> dict:
        score = (
            (1.0 if counts["lifecycle_events"] else 0.0)
            + (0.5 if counts["ai_suggestions"] else 0.0)
            + (0.8 if counts["review_total"] > 0 else 0.0)
            + (0.7 if counts["schedule_failures"] == 0 and counts["schedules"] else 0.0)
            + (0.5 if counts["compose"] and counts["dockerfile"] else 0.0)
            + (0.4 if counts["import_batches"] else 0.0)
            + (0.4 if counts["script_modules"] and counts["script_bindings"] else 0.0)
            + (0.5 if counts["feature_flags"] or counts["platform_foundation"] else 0.0)
            + (0.5 if counts["roles"] and counts["assignments"] else 0.0)
        )
        gaps = []
        if counts["review_total"] > 0:
            gaps.append("Reduce pending review load and enforce stronger governance closure.")
        if counts["ai_suggestions"] == 0:
            gaps.append("Expand governed AI suggestion capture to support enterprise autonomy workflows.")
        if counts["import_batches"] == 0:
            gaps.append("Exercise the external framework import path and prove source-to-control traceability.")
        if counts["script_modules"] == 0 or counts["script_bindings"] == 0:
            gaps.append("Register external assessment modules and bind them into evidence plans for reusable execution.")
        if counts["schedule_failures"] > 0:
            gaps.append("Eliminate recurring schedule failures before claiming enterprise reliability.")
        if not counts["compose"]:
            gaps.append("Add compose-level deployment assets for repeatable operational rollout.")
        if not counts["feature_flags"]:
            gaps.append("Introduce feature flags for safer dark launches and controlled rollout of new capabilities.")
        if counts["roles"] == 0 or counts["assignments"] == 0:
            gaps.append("Bootstrap RBAC roles, principals, and scoped assignments to enforce separation of duties.")
        return {"area": "Phase 3 Enterprise Readiness", "score": round(min(4.0, 1.2 + score * 0.5), 2), "target": 4.0, "gaps": gaps}

    def _security_area(self, counts: dict[str, float]) -> dict:
        score = 1.5 + (0.8 if counts["secrets"] else 0.0) + (0.8 if counts["healthy_connections"] else 0.0) + (0.6 if counts["validated_profiles"] else 0.0) + (0.3 if counts["open_circuits"] == 0 and counts["platform_foundation"] else 0.0) + (0.6 if counts["roles"] and counts["approved_assignments"] else 0.0)
        gaps = []
        if not counts["secrets"]:
            gaps.append("Establish secure secret metadata and bootstrap the evidence encryption backend.")
        if self._ratio(counts["healthy_connections"], counts["connections"]) < 0.7:
            gaps.append("Stabilize secure Confluence connectivity and secret handling paths.")
        if counts["roles"] == 0 or counts["approved_assignments"] == 0:
            gaps.append("Configure RBAC assignments and approval segregation for privileged workflows.")
        return {"area": "Security", "score": round(min(4.0, score), 2), "target": 4.0, "gaps": gaps}

    def _quality_area(self, counts: dict[str, float]) -> dict:
        score = (
            1.0
            + (0.8 if counts["alembic_ini"] and counts["alembic_dir"] else 0.0)
            + (0.8 if counts["tests"] else 0.0)
            + (0.7 if counts["dockerfile"] else 0.0)
            + (0.4 if counts["streamlit_config"] else 0.0)
            + (0.3 if counts["docker_scan"] else 0.0)
            + (0.4 if counts["ci_workflow"] else 0.0)
            + (0.3 if counts["engineering_doc"] else 0.0)
            + (0.2 if counts["access_governance_doc"] else 0.0)
        )
        gaps = []
        if not (counts["alembic_ini"] and counts["alembic_dir"]):
            gaps.append("Introduce a migration framework to replace direct schema creation.")
        if not counts["tests"]:
            gaps.append("Add automated tests to protect the maturity model, review queue, and deployment behavior.")
        if not counts["ci_workflow"]:
            gaps.append("Make CI/CD the default path with an automated build and test workflow.")
        return {"area": "Quality", "score": round(min(4.0, score), 2), "target": 4.0, "gaps": gaps}

    def _reliability_area(self, counts: dict[str, float]) -> dict:
        score = (
            1.0
            + (0.7 if counts["schedules"] else 0.0)
            + (0.7 if counts["scoped_schedules"] else 0.0)
            + (0.6 if counts["schedule_failures"] == 0 else 0.0)
            + (0.4 if counts["docker_smoke"] else 0.0)
            + (0.3 if counts["ubuntu_validate"] else 0.0)
            + (0.4 if counts["platform_foundation"] else 0.0)
            + (0.3 if counts["roles"] else 0.0)
        )
        gaps = []
        if counts["schedule_failures"] > 0:
            gaps.append("Resolve schedule execution failures and add retry-oriented operator workflows.")
        gaps.append("Add durable background jobs and concurrency controls for enterprise workloads.")
        if counts["open_circuits"] > 0:
            gaps.append("Close or recover open circuit breakers before claiming reliable external integrations.")
        return {"area": "Reliability", "score": round(min(4.0, score), 2), "target": 4.0, "gaps": gaps}

    def _integrability_area(self, counts: dict[str, float]) -> dict:
        score = (
            1.4
            + (0.7 if counts["validated_profiles"] else 0.0)
            + (0.7 if counts["healthy_connections"] else 0.0)
            + (0.6 if counts["docker_entrypoint"] else 0.0)
            + (0.3 if counts["import_batches"] else 0.0)
            + (0.3 if counts["script_modules"] and counts["script_bindings"] else 0.0)
            + (0.4 if counts["platform_foundation"] else 0.0)
            + (0.2 if counts["roles"] and counts["approved_assignments"] else 0.0)
        )
        gaps = [
            "Add external APIs and event hooks for enterprise integrations.",
            "Expand beyond AWS and Confluence with normalized connector patterns.",
        ]
        return {"area": "Integrability", "score": round(min(4.0, score), 2), "target": 4.0, "gaps": gaps}

    def _ux_area(self, counts: dict[str, float]) -> dict:
        score = (
            1.2
            + (0.8 if counts["review_total"] else 0.0)
            + (0.5 if counts["streamlit_config"] else 0.0)
            + (0.5 if counts["validated_profiles"] or counts["healthy_connections"] else 0.0)
            + (0.4 if counts["ux_redesign"] else 0.0)
            + (0.3 if counts["asset_catalog"] else 0.0)
            + (0.3 if counts["workspace_guidance"] else 0.0)
            + (0.2 if counts["feature_flags"] else 0.0)
            + (0.2 if counts["roles"] else 0.0)
        )
        gaps = []
        gaps.append("Continue reducing cognitive load by migrating more deep workflows into the unified workspace.")
        if not counts["ux_redesign"]:
            gaps.append("Introduce a modular workspace shell instead of relying only on specialist pages.")
        if not counts["asset_catalog"]:
            gaps.append("Provide a universal asset catalog with CRUD across the data model.")
        if counts["review_critical"] > 0:
            gaps.append("Drive critical queue items to zero so the UI highlights action rather than unresolved instability.")
        return {"area": "UI and UX", "score": round(min(4.0, score), 2), "target": 4.0, "gaps": gaps}

    def _deployment_area(self, counts: dict[str, float]) -> dict:
        score = 1.0
        score += 0.7 if counts["dockerfile"] else 0.0
        score += 0.7 if counts["compose"] else 0.0
        score += 0.5 if counts["ubuntu_script"] else 0.0
        score += 0.5 if counts["docker_entrypoint"] else 0.0
        score += 0.3 if counts["docker_scan"] else 0.0
        score += 0.3 if counts["docker_smoke"] else 0.0
        score += 0.4 if counts["ci_workflow"] else 0.0
        gaps = []
        if not counts["compose"]:
            gaps.append("Add compose-based deployment for Ubuntu operators.")
        if not counts["ubuntu_script"]:
            gaps.append("Add a one-command Ubuntu bootstrap path.")
        if not counts["docker_scan"]:
            gaps.append("Add image scanning to the container promotion path.")
        return {"area": "Deployment", "score": round(min(4.0, score), 2), "target": 4.0, "gaps": gaps}

    @staticmethod
    def _ratio(numerator: float, denominator: float) -> float:
        if not denominator:
            return 0.0
        return numerator / denominator
