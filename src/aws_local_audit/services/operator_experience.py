from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from aws_local_audit.config import settings
from aws_local_audit.logging_utils import project_root
from aws_local_audit.models import (
    AssessmentRun,
    AwsCliProfile,
    AwsEvidenceTarget,
    ConfluenceConnection,
    Control,
    EvidenceItem,
    Framework,
    LifecycleEvent,
    OrganizationFrameworkBinding,
    Product,
)
from aws_local_audit.services.governance import GovernanceService


class OperatorExperienceService:
    def __init__(self, session):
        self.session = session
        self.governance = GovernanceService(session)

    def pilot_checklist(self) -> list[dict]:
        counts = {
            "frameworks": self.session.scalar(select(func.count()).select_from(Framework)) or 0,
            "enabled_frameworks": self.session.scalar(
                select(func.count()).select_from(Framework).where(Framework.active.is_(True))
            ) or 0,
            "products": self.session.scalar(select(func.count()).select_from(Product)) or 0,
            "bindings": self.session.scalar(select(func.count()).select_from(OrganizationFrameworkBinding)) or 0,
            "profiles": self.session.scalar(select(func.count()).select_from(AwsCliProfile)) or 0,
            "validated_profiles": self.session.scalar(
                select(func.count()).select_from(AwsCliProfile).where(AwsCliProfile.last_validation_status == "pass")
            ) or 0,
            "targets": self.session.scalar(select(func.count()).select_from(AwsEvidenceTarget)) or 0,
            "evidence_items": self.session.scalar(select(func.count()).select_from(EvidenceItem)) or 0,
            "assessment_runs": self.session.scalar(select(func.count()).select_from(AssessmentRun)) or 0,
            "healthy_connections": self.session.scalar(
                select(func.count()).select_from(ConfluenceConnection).where(ConfluenceConnection.last_test_status == "pass")
            ) or 0,
        }
        return [
            {
                "step": "Seed the framework catalog",
                "complete": counts["frameworks"] > 0,
                "detail": "Load baseline frameworks and controls before starting any pilot.",
                "best_place": "Wizards or framework seed CLI",
            },
            {
                "step": "Enable at least one framework",
                "complete": counts["enabled_frameworks"] > 0,
                "detail": "A framework must be active before evidence collection and assessments make sense.",
                "best_place": "Standards or framework enable CLI",
            },
            {
                "step": "Register a product",
                "complete": counts["products"] > 0,
                "detail": "Products or services define where controls are implemented.",
                "best_place": "Portfolio or Asset Catalog",
            },
            {
                "step": "Register AWS CLI SSO profiles",
                "complete": counts["profiles"] > 0,
                "detail": "The app stores profile metadata locally and uses aws sso login only at collection time.",
                "best_place": "AWS Profiles or aws-profile upsert CLI",
            },
            {
                "step": "Validate at least one AWS profile",
                "complete": counts["validated_profiles"] > 0,
                "detail": "Live evidence collection is safer once at least one profile validates successfully.",
                "best_place": "AWS Profiles or aws-profile validate CLI",
            },
            {
                "step": "Bind a framework to the organization scope",
                "complete": counts["bindings"] > 0,
                "detail": "Bindings connect organizations, frameworks, profiles, and regions.",
                "best_place": "Portfolio or org bind-framework CLI",
            },
            {
                "step": "Add AWS evidence targets",
                "complete": counts["targets"] > 0,
                "detail": "Targets link controls and products to accounts, regions, and CLI profiles.",
                "best_place": "Portfolio or org add-aws-target CLI",
            },
            {
                "step": "Collect or upload evidence",
                "complete": counts["evidence_items"] > 0,
                "detail": "Use automated collection or manual uploads to start building the evidence base.",
                "best_place": "Operations, Artifact Explorer, or evidence CLI",
            },
            {
                "step": "Run an assessment",
                "complete": counts["assessment_runs"] > 0,
                "detail": "A pilot becomes real once at least one assessment has executed and can be reviewed later.",
                "best_place": "Operations or assessment run/list CLI",
            },
            {
                "step": "Test Confluence when publication matters",
                "complete": counts["healthy_connections"] > 0,
                "detail": "Optional for a first pilot, but recommended before publishing evidence or reports externally.",
                "best_place": "Settings & Integrations or confluence test CLI",
            },
        ]

    def environment_summary(self) -> dict:
        log_dir = self._resolve_path(settings.log_dir)
        app_log = log_dir / settings.app_log_file
        audit_log = log_dir / settings.audit_log_file
        return {
            "offline_mode": self.governance.offline_mode_enabled(),
            "database_url": settings.database_url,
            "log_dir": str(log_dir),
            "app_log_path": str(app_log),
            "audit_log_path": str(audit_log),
            "app_log_exists": app_log.exists(),
            "audit_log_exists": audit_log.exists(),
            "frameworks": self.session.scalar(select(func.count()).select_from(Framework)) or 0,
            "products": self.session.scalar(select(func.count()).select_from(Product)) or 0,
            "bindings": self.session.scalar(select(func.count()).select_from(OrganizationFrameworkBinding)) or 0,
            "profiles": self.session.scalar(select(func.count()).select_from(AwsCliProfile)) or 0,
            "validated_profiles": self.session.scalar(
                select(func.count()).select_from(AwsCliProfile).where(AwsCliProfile.last_validation_status == "pass")
            ) or 0,
        }

    def recent_assessments(self, limit: int = 12) -> list[dict]:
        runs = self.session.scalars(
            select(AssessmentRun)
            .options(
                selectinload(AssessmentRun.framework),
                selectinload(AssessmentRun.organization),
                selectinload(AssessmentRun.product),
                selectinload(AssessmentRun.product_flavor),
            )
            .order_by(AssessmentRun.started_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": item.id,
                "framework": item.framework.code if item.framework else "",
                "organization": item.organization.code if item.organization else "",
                "product": item.product.code if item.product else "",
                "flavor": item.product_flavor.code if item.product_flavor else "",
                "started_at": item.started_at,
                "status": item.status,
                "review_status": item.review_status,
                "assurance_status": item.assurance_status,
                "score": item.score,
            }
            for item in runs
        ]

    def recent_evidence(self, limit: int = 12) -> list[dict]:
        rows = self.session.scalars(
            select(EvidenceItem)
            .options(
                selectinload(EvidenceItem.control).selectinload(Control.framework),
                selectinload(EvidenceItem.product),
                selectinload(EvidenceItem.product_flavor),
            )
            .order_by(EvidenceItem.collected_at.desc())
            .limit(limit)
        ).all()
        rendered = []
        for item in rows:
            rendered.append(
                {
                    "id": item.id,
                    "framework": item.control.framework.code if item.control and item.control.framework else "",
                    "control_id": item.control.control_id if item.control else "",
                    "product": item.product.code if item.product else "",
                    "flavor": item.product_flavor.code if item.product_flavor else "",
                    "status": item.status,
                    "lifecycle_status": item.lifecycle_status,
                    "collected_at": item.collected_at,
                    "summary": item.summary,
                }
            )
        return rendered

    def recent_lifecycle_events(self, limit: int = 12) -> list[dict]:
        rows = self.session.scalars(
            select(LifecycleEvent).order_by(LifecycleEvent.created_at.desc()).limit(limit)
        ).all()
        return [
            {
                "created_at": item.created_at,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "lifecycle_name": item.lifecycle_name,
                "from_state": item.from_state,
                "to_state": item.to_state,
                "actor": item.actor,
            }
            for item in rows
        ]

    def recent_audit_activity(self, limit: int = 20) -> list[dict]:
        path = self._resolve_path(settings.log_dir) / settings.audit_log_file
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        except OSError:
            return []
        rows: list[dict] = []
        for raw_line in reversed(lines):
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                rows.append({"timestamp": "", "action": "raw_log_line", "actor": "", "status": "", "target_type": "", "target_id": "", "details": raw_line})
                continue
            rows.append(
                {
                    "timestamp": payload.get("timestamp", ""),
                    "action": payload.get("action", ""),
                    "actor": payload.get("actor", ""),
                    "status": payload.get("status", ""),
                    "target_type": payload.get("target_type", ""),
                    "target_id": payload.get("target_id", ""),
                    "details": payload.get("details", {}),
                }
            )
        return rows

    def log_tail(self, audit: bool = False, limit: int = 30) -> list[str]:
        file_name = settings.audit_log_file if audit else settings.app_log_file
        path = self._resolve_path(settings.log_dir) / file_name
        if not path.exists():
            return []
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        except OSError:
            return []

    @staticmethod
    def _resolve_path(raw_value: str) -> Path:
        candidate = Path(raw_value)
        if candidate.is_absolute():
            return candidate
        return project_root() / candidate
