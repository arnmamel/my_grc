from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from aws_local_audit.framework_loader import load_templates
from aws_local_audit.models import (
    AssessmentRun,
    AwsCliProfile,
    AwsEvidenceTarget,
    Control,
    ControlImplementation,
    CustomerQuestionnaire,
    EvidenceCollectionPlan,
    EvidenceItem,
    Framework,
    Organization,
    OrganizationFrameworkBinding,
    Product,
    ProductControlProfile,
    UnifiedControl,
    UnifiedControlMapping,
)
from aws_local_audit.services.lifecycle import TRANSITION_POLICIES

class Phase1MaturityService:
    def __init__(self, session):
        self.session = session
        self.root = Path(__file__).resolve().parents[3]

    def assess(self) -> dict:
        counts = self._counts()
        capabilities = self._capabilities()
        areas = [
            self._framework_area(counts, capabilities),
            self._unified_controls_area(counts, capabilities),
            self._product_scope_area(counts, capabilities),
            self._aws_sso_area(counts, capabilities),
            self._evidence_area(counts, capabilities),
            self._offline_area(counts, capabilities),
            self._workspace_area(counts, capabilities),
        ]
        overall = round(sum(area["score"] for area in areas) / len(areas), 2) if areas else 0.0
        blockers = []
        for area in areas:
            blockers.extend(area["gaps"])
        return {
            "overall_score": overall,
            "target_score": 4.0,
            "areas": areas,
            "counts": counts,
            "capabilities": capabilities,
            "top_blockers": blockers[:10],
        }

    def _counts(self) -> dict[str, float]:
        template_count = len(load_templates())
        total_frameworks = self.session.scalar(select(func.count()).select_from(Framework)) or 0
        total_controls = self.session.scalar(select(func.count()).select_from(Control)) or 0
        frameworks_with_authority = self.session.scalar(
            select(func.count()).select_from(Framework).where(Framework.authority_document_id.is_not(None))
        ) or 0
        total_mappings = self.session.scalar(select(func.count()).select_from(UnifiedControlMapping)) or 0
        approved_mappings = self.session.scalar(
            select(func.count()).select_from(UnifiedControlMapping).where(UnifiedControlMapping.approval_status == "approved")
        ) or 0
        total_evidence_plans = self.session.scalar(select(func.count()).select_from(EvidenceCollectionPlan)) or 0
        controls_with_plan = self.session.scalar(
            select(func.count(func.distinct(EvidenceCollectionPlan.control_id))).where(EvidenceCollectionPlan.control_id.is_not(None))
        ) or 0
        unified_controls = self.session.scalar(select(func.count()).select_from(UnifiedControl)) or 0
        products = self.session.scalar(select(func.count()).select_from(Product)) or 0
        organizations = self.session.scalar(select(func.count()).select_from(Organization)) or 0
        bindings = self.session.scalar(select(func.count()).select_from(OrganizationFrameworkBinding)) or 0
        aws_profiles = self.session.scalar(select(func.count()).select_from(AwsCliProfile).where(AwsCliProfile.status == "active")) or 0
        aws_targets = self.session.scalar(select(func.count()).select_from(AwsEvidenceTarget).where(AwsEvidenceTarget.lifecycle_status == "active")) or 0
        target_controls = self.session.scalar(
            select(func.count(func.distinct(AwsEvidenceTarget.control_id))).where(AwsEvidenceTarget.control_id.is_not(None))
        ) or 0
        implementations = self.session.scalar(select(func.count()).select_from(ControlImplementation)) or 0
        questionnaires = self.session.scalar(select(func.count()).select_from(CustomerQuestionnaire)) or 0
        evidence_items = self.session.scalar(select(func.count()).select_from(EvidenceItem)) or 0
        assessments = self.session.scalar(select(func.count()).select_from(AssessmentRun)) or 0
        profiles = self.session.scalar(select(func.count()).select_from(ProductControlProfile)) or 0
        validated_profiles = self.session.scalar(
            select(func.count()).select_from(AwsCliProfile).where(AwsCliProfile.last_validation_status == "pass")
        ) or 0
        return {
            "framework_templates": template_count,
            "frameworks": total_frameworks,
            "controls": total_controls,
            "frameworks_with_authority": frameworks_with_authority,
            "unified_controls": unified_controls,
            "mappings": total_mappings,
            "approved_mappings": approved_mappings,
            "evidence_plans": total_evidence_plans,
            "controls_with_plan": controls_with_plan,
            "organizations": organizations,
            "products": products,
            "bindings": bindings,
            "aws_profiles": aws_profiles,
            "validated_profiles": validated_profiles,
            "aws_targets": aws_targets,
            "target_controls": target_controls,
            "implementations": implementations,
            "questionnaires": questionnaires,
            "evidence_items": evidence_items,
            "assessments": assessments,
            "product_control_profiles": profiles,
        }

    def _capabilities(self) -> dict[str, float]:
        service_root = self.root / "src" / "aws_local_audit" / "services"
        workspace_root = self.root / "workspace"
        return {
            "migrations_ready": float((self.root / "alembic.ini").exists() and (self.root / "alembic").exists()),
            "framework_authority_ready": float((service_root / "frameworks.py").exists()),
            "import_ready": float((service_root / "framework_imports.py").exists()),
            "workbench_ready": float((service_root / "workbench.py").exists()),
            "workspace_ready": float((workspace_root / "app.py").exists() and (workspace_root / "ux_redesign.py").exists()),
            "onboarding_ready": float((service_root / "governance.py").exists()),
            "aws_profile_ready": float((service_root / "aws_profiles.py").exists()),
            "readiness_ready": float((service_root / "readiness.py").exists()),
            "rbac_ready": float((service_root / "access_control.py").exists()),
            "assessment_ready": float((service_root / "assessments.py").exists()),
            "questionnaire_ready": float((service_root / "questionnaires.py").exists()),
            "qa_ready": float((self.root / "testing" / "qa" / "run.py").exists()),
            "framework_binding_policy": float(
                ("framework_binding", "framework_binding_lifecycle") in TRANSITION_POLICIES
            ),
            "target_policy": float(("aws_evidence_target", "evidence_lifecycle") in TRANSITION_POLICIES),
            "plan_policy": float(("evidence_collection_plan", "evidence_lifecycle") in TRANSITION_POLICIES),
        }

    def _framework_area(self, counts: dict[str, float], capabilities: dict[str, float]) -> dict:
        authority_ratio = (
            counts["frameworks_with_authority"] / counts["frameworks"] if counts["frameworks"] else 1.0
        )
        template_ratio = 1.0 if counts["framework_templates"] else 0.0
        score = round(
            min(
                4.0,
                1.0
                + template_ratio * 0.8
                + capabilities["framework_authority_ready"] * 0.8
                + capabilities["import_ready"] * 0.4
                + capabilities["migrations_ready"] * 0.3
                + capabilities["framework_binding_policy"] * 0.2
                + authority_ratio * 0.5,
            ),
            2,
        )
        gaps = []
        if counts["framework_templates"] == 0:
            gaps.append("Seed framework templates so the baseline catalog is always available.")
        if not capabilities["framework_authority_ready"]:
            gaps.append("Keep framework and authority-document management wired into the platform services.")
        if authority_ratio < 1.0 and counts["frameworks"] > 0:
            gaps.append("Complete authority document coverage for all frameworks.")
        if not capabilities["migrations_ready"]:
            gaps.append("Keep schema migrations in place for stable Phase 1 backbone evolution.")
        return {"area": "Framework management", "score": score, "target": 4.0, "gaps": gaps}

    def _unified_controls_area(self, counts: dict[str, float], capabilities: dict[str, float]) -> dict:
        mapping_ratio = counts["approved_mappings"] / counts["mappings"] if counts["mappings"] else 1.0
        score = round(
            min(
                4.0,
                1.0
                + capabilities["plan_policy"] * 0.8
                + capabilities["rbac_ready"] * 0.7
                + capabilities["workbench_ready"] * 0.7
                + capabilities["workspace_ready"] * 0.5
                + (0.2 if counts["unified_controls"] else 0.0)
                + (0.2 if counts["mappings"] else 0.0)
                + mapping_ratio * 0.3,
            ),
            2,
        )
        gaps = []
        if not capabilities["rbac_ready"]:
            gaps.append("Keep approval segregation and RBAC foundations in place for governed mappings.")
        if counts["unified_controls"] == 0 and counts["mappings"] == 0:
            gaps.append(
                "Exercise the SCF pivot unified control backbone with at least one approved mapped control path, "
                "starting with ISO27001_2022 Annex A controls."
            )
        elif mapping_ratio < 0.7 and counts["mappings"] > 0:
            gaps.append("Increase the proportion of approved mappings.")
        return {"area": "Unified controls and mappings", "score": score, "target": 4.0, "gaps": gaps}

    def _product_scope_area(self, counts: dict[str, float], capabilities: dict[str, float]) -> dict:
        score = round(
            min(
                4.0,
                1.0
                + capabilities["workbench_ready"] * 1.0
                + capabilities["workspace_ready"] * 0.8
                + capabilities["onboarding_ready"] * 0.7
                + capabilities["qa_ready"] * 0.5
                + (0.1 if counts["organizations"] else 0.0)
                + (0.1 if counts["products"] else 0.0)
                + (0.05 if counts["implementations"] else 0.0)
                + (0.05 if counts["product_control_profiles"] else 0.0),
            ),
            2,
        )
        gaps = []
        if not capabilities["workspace_ready"] or not capabilities["onboarding_ready"]:
            gaps.append("Keep wizarded onboarding and unified workspace support wired into product-scoped operations.")
        if counts["organizations"] == 0 or counts["products"] == 0:
            gaps.append("Exercise organization and product scope in at least one local workspace.")
        if counts["implementations"] == 0 or counts["product_control_profiles"] == 0:
            gaps.append("Add implementation records and product control profiles for at least one scoped product or flavor.")
        return {"area": "Product and flavor scope", "score": score, "target": 4.0, "gaps": gaps}

    def _aws_sso_area(self, counts: dict[str, float], capabilities: dict[str, float]) -> dict:
        profile_ratio = counts["validated_profiles"] / counts["aws_profiles"] if counts["aws_profiles"] else 1.0
        score = round(
            min(
                4.0,
                1.0
                + capabilities["aws_profile_ready"] * 1.0
                + capabilities["readiness_ready"] * 0.9
                + capabilities["target_policy"] * 0.6
                + capabilities["workspace_ready"] * 0.3
                + capabilities["qa_ready"] * 0.2
                + (0.15 if counts["aws_profiles"] else 0.0)
                + (0.15 if counts["bindings"] else 0.0)
                + (0.15 if counts["aws_targets"] else 0.0)
                + profile_ratio * 0.55,
            ),
            2,
        )
        gaps = []
        if not capabilities["aws_profile_ready"] or not capabilities["readiness_ready"]:
            gaps.append("Keep AWS profile validation and readiness planning wired into the foundation.")
        if counts["aws_profiles"] == 0 or counts["bindings"] == 0:
            gaps.append("Exercise AWS SSO registration and binding scope in the local workspace.")
        if counts["aws_targets"] == 0:
            gaps.append("Register AWS evidence targets for product or control scope.")
        return {"area": "AWS SSO operations", "score": score, "target": 4.0, "gaps": gaps}

    def _evidence_area(self, counts: dict[str, float], capabilities: dict[str, float]) -> dict:
        plan_ratio = counts["controls_with_plan"] / counts["controls"] if counts["controls"] else 1.0
        target_ratio = counts["target_controls"] / counts["controls"] if counts["controls"] else 1.0
        score = round(
            min(
                4.0,
                1.0
                + capabilities["plan_policy"] * 0.8
                + capabilities["readiness_ready"] * 0.8
                + capabilities["workbench_ready"] * 0.6
                + capabilities["qa_ready"] * 0.3
                + plan_ratio * 0.25
                + target_ratio * 0.25
                + (0.0 if counts["evidence_items"] == 0 else 0.0),
            ),
            2,
        )
        gaps = []
        if not capabilities["plan_policy"] or not capabilities["readiness_ready"]:
            gaps.append("Keep governed evidence-plan logic and readiness reporting in the backbone.")
        if counts["evidence_plans"] == 0:
            gaps.append("Create evidence collection plans.")
        elif plan_ratio < 0.5:
            gaps.append("Increase evidence-plan coverage for framework controls.")
        if counts["aws_targets"] == 0:
            gaps.append("Increase AWS target coverage for scoped controls.")
        elif target_ratio < 0.4:
            gaps.append("Map more controls to AWS evidence targets.")
        if counts["evidence_items"] == 0:
            gaps.append("Collect or import evidence to validate the operating model.")
        return {"area": "Evidence collection foundation", "score": score, "target": 4.0, "gaps": gaps}

    def _offline_area(self, counts: dict[str, float], capabilities: dict[str, float]) -> dict:
        score = round(
            min(
                4.0,
                1.3
                + capabilities["workspace_ready"] * 0.8
                + capabilities["onboarding_ready"] * 0.4
                + capabilities["assessment_ready"] * 0.7
                + capabilities["questionnaire_ready"] * 0.5
                + capabilities["qa_ready"] * 0.3
                + (0.1 if counts["questionnaires"] or counts["assessments"] else 0.0),
            ),
            2,
        )
        gaps = []
        if not capabilities["workspace_ready"]:
            gaps.append("Keep the offline-first workspace shell available for local GRC operations.")
        if counts["implementations"] == 0:
            gaps.append("Store implementation narratives to make offline operation valuable.")
        if counts["questionnaires"] == 0 and counts["assessments"] == 0:
            gaps.append("Validate offline workflows with questionnaires or local assessments.")
        return {"area": "Offline-first local operations", "score": score, "target": 4.0, "gaps": gaps}

    def _workspace_area(self, counts: dict[str, float], capabilities: dict[str, float]) -> dict:
        completeness = 0.0
        completeness += capabilities["workspace_ready"]
        completeness += capabilities["onboarding_ready"]
        completeness += capabilities["qa_ready"]
        completeness += capabilities["workbench_ready"]
        completeness += capabilities["readiness_ready"]
        score = round(min(4.0, 1.0 + (completeness / 5.0) * 3.0), 2)
        gaps = []
        if not capabilities["workspace_ready"] or not capabilities["onboarding_ready"]:
            gaps.append("Keep the unified workspace and onboarding guidance healthy.")
        if counts["aws_profiles"] == 0:
            gaps.append("Use the AWS Profiles workspace to store CLI configuration metadata.")
        if counts["questionnaires"] == 0 and counts["assessments"] == 0:
            gaps.append("Exercise the workspace with a questionnaire or assessment run.")
        return {"area": "Workspace usability", "score": score, "target": 4.0, "gaps": gaps}
