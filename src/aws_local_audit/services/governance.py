from __future__ import annotations

from sqlalchemy import func, select

from aws_local_audit.models import (
    AwsEvidenceTarget,
    AwsCliProfile,
    ConfluenceConnection,
    CustomerQuestionnaire,
    EvidenceCollectionPlan,
    Framework,
    Organization,
    OrganizationFrameworkBinding,
    Product,
    SystemSetting,
    UnifiedControl,
)


class GovernanceService:
    def __init__(self, session):
        self.session = session

    def get_setting(self, key: str, default: str = "") -> str:
        record = self.session.scalar(select(SystemSetting).where(SystemSetting.setting_key == key))
        if record is None:
            return default
        return record.setting_value

    def set_setting(self, key: str, value: str, description: str = "") -> SystemSetting:
        record = self.session.scalar(select(SystemSetting).where(SystemSetting.setting_key == key))
        if record is None:
            record = SystemSetting(setting_key=key)
            self.session.add(record)
        record.setting_value = value
        if description:
            record.description = description
        self.session.flush()
        return record

    def onboarding_status(self) -> dict:
        counts = {
            "frameworks": self.session.scalar(select(func.count()).select_from(Framework)) or 0,
            "organizations": self.session.scalar(select(func.count()).select_from(Organization)) or 0,
            "products": self.session.scalar(select(func.count()).select_from(Product)) or 0,
            "bindings": self.session.scalar(select(func.count()).select_from(OrganizationFrameworkBinding)) or 0,
            "unified_controls": self.session.scalar(select(func.count()).select_from(UnifiedControl)) or 0,
            "evidence_plans": self.session.scalar(select(func.count()).select_from(EvidenceCollectionPlan)) or 0,
            "connections": self.session.scalar(select(func.count()).select_from(ConfluenceConnection)) or 0,
            "questionnaires": self.session.scalar(select(func.count()).select_from(CustomerQuestionnaire)) or 0,
            "aws_targets": self.session.scalar(select(func.count()).select_from(AwsEvidenceTarget)) or 0,
            "aws_profiles": self.session.scalar(select(func.count()).select_from(AwsCliProfile)) or 0,
        }
        steps = [
            {
                "key": "seed_frameworks",
                "label": "Seed the framework catalog",
                "completed": counts["frameworks"] > 0,
                "detail": "Load baseline templates and authority documents.",
            },
            {
                "key": "create_organization",
                "label": "Create an organization",
                "completed": counts["organizations"] > 0,
                "detail": "Establish the enterprise boundary for products and assessments.",
            },
            {
                "key": "create_product",
                "label": "Register a product",
                "completed": counts["products"] > 0,
                "detail": "Add at least one product or service to scope control implementations.",
            },
            {
                "key": "register_aws_profiles",
                "label": "Register AWS CLI profile metadata",
                "completed": counts["aws_profiles"] > 0,
                "detail": "Store local AWS CLI SSO profile definitions for later login and collection planning.",
            },
            {
                "key": "bind_framework",
                "label": "Bind AWS scope",
                "completed": counts["bindings"] > 0,
                "detail": "Connect a framework to an AWS profile and region.",
            },
            {
                "key": "create_unified_control",
                "label": "Create a unified control",
                "completed": counts["unified_controls"] > 0,
                "detail": "Start the common control backbone and reusable mappings.",
            },
            {
                "key": "create_evidence_plan",
                "label": "Create an evidence plan",
                "completed": counts["evidence_plans"] > 0,
                "detail": "Define how evidence should be collected and reviewed.",
            },
            {
                "key": "register_aws_targets",
                "label": "Register AWS evidence targets",
                "completed": counts["aws_targets"] > 0,
                "detail": "Map product and control scope to AWS accounts, regions, and SSO profiles.",
            },
            {
                "key": "connect_confluence",
                "label": "Secure a Confluence connection",
                "completed": counts["connections"] > 0,
                "detail": "Prepare a governed destination for reports and evidence artifacts.",
            },
            {
                "key": "load_questionnaire",
                "label": "Load a questionnaire",
                "completed": counts["questionnaires"] > 0,
                "detail": "Validate that implementation-driven answers can be produced.",
            },
        ]
        completed_steps = sum(1 for step in steps if step["completed"])
        return {
            "counts": counts,
            "steps": steps,
            "completed_steps": completed_steps,
            "total_steps": len(steps),
            "progress": completed_steps / len(steps) if steps else 0.0,
            "first_run_needed": completed_steps < len(steps),
        }

    def default_workspace_section(self) -> str:
        override = self.get_setting("workspace.default_section")
        if override:
            return override
        return "Wizards" if self.onboarding_status()["first_run_needed"] else "Overview"

    def pivot_framework_code(self) -> str:
        return self.get_setting("control_mapping.pivot_framework_code", "")

    def set_pivot_framework_code(self, framework_code: str, description: str = "") -> SystemSetting:
        return self.set_setting(
            "control_mapping.pivot_framework_code",
            framework_code.strip().upper(),
            description
            or "Framework code used as the pivot baseline for converged control mapping and traceability.",
        )

    def offline_mode_enabled(self) -> bool:
        return self.get_setting("runtime.offline_mode", "false").strip().lower() in {"1", "true", "yes", "on"}

    def set_offline_mode(self, enabled: bool) -> SystemSetting:
        return self.set_setting(
            "runtime.offline_mode",
            "true" if enabled else "false",
            "When enabled, AWS evidence collection is deferred and the workspace operates in offline-first mode.",
        )
