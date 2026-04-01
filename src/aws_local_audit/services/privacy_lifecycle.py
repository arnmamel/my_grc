from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from aws_local_audit.logging_utils import audit_event, metric_event
from aws_local_audit.models import CustomerQuestionnaire, EvidenceItem
from aws_local_audit.services.lifecycle import LifecycleService


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PrivacyLifecycleService:
    def __init__(self, session):
        self.session = session
        self.lifecycle = LifecycleService(session)

    def retention_report(
        self,
        *,
        questionnaire_retention_days: int = 365,
        evidence_freshness_days: int = 180,
        now: datetime | None = None,
    ) -> dict:
        current = now or _utc_now_naive()
        questionnaire_cutoff = current - timedelta(days=max(questionnaire_retention_days, 1))
        freshness_cutoff = current - timedelta(days=max(evidence_freshness_days, 1))

        questionnaires_due = list(
            self.session.scalars(
                select(CustomerQuestionnaire)
                .options(
                    selectinload(CustomerQuestionnaire.organization),
                    selectinload(CustomerQuestionnaire.product),
                    selectinload(CustomerQuestionnaire.items),
                )
                .where(
                    CustomerQuestionnaire.created_at <= questionnaire_cutoff,
                    CustomerQuestionnaire.status.not_in(["deleted", "purged"]),
                )
                .order_by(CustomerQuestionnaire.created_at.asc(), CustomerQuestionnaire.id.asc())
            )
        )
        expired_evidence = list(
            self.session.scalars(
                select(EvidenceItem)
                .where(EvidenceItem.expires_at.is_not(None), EvidenceItem.expires_at <= current)
                .order_by(EvidenceItem.expires_at.asc(), EvidenceItem.id.asc())
            )
        )
        stale_evidence = list(
            self.session.scalars(
                select(EvidenceItem)
                .where(EvidenceItem.collected_at <= freshness_cutoff)
                .order_by(EvidenceItem.collected_at.asc(), EvidenceItem.id.asc())
            )
        )

        return {
            "generated_at": f"{current.isoformat()}Z",
            "questionnaire_retention_days": questionnaire_retention_days,
            "evidence_freshness_days": evidence_freshness_days,
            "counts": {
                "questionnaires_due_for_review": len(questionnaires_due),
                "expired_evidence": len(expired_evidence),
                "stale_evidence": len(stale_evidence),
            },
            "questionnaires_due_for_review": [
                {
                    "questionnaire_id": item.id,
                    "name": item.name,
                    "status": item.status,
                    "customer_name": item.customer_name,
                    "organization_code": item.organization.code,
                    "product_code": item.product.code,
                    "created_at": item.created_at.isoformat() if item.created_at else "",
                    "item_count": len(item.items),
                }
                for item in questionnaires_due[:50]
            ],
            "expired_evidence": [
                {
                    "evidence_id": item.id,
                    "evidence_key": item.evidence_key,
                    "status": item.status,
                    "classification": item.classification,
                    "expires_at": item.expires_at.isoformat() if item.expires_at else "",
                }
                for item in expired_evidence[:50]
            ],
            "stale_evidence": [
                {
                    "evidence_id": item.id,
                    "evidence_key": item.evidence_key,
                    "status": item.status,
                    "collected_at": item.collected_at.isoformat() if item.collected_at else "",
                }
                for item in stale_evidence[:50]
            ],
        }

    def export_questionnaire_bundle(self, questionnaire_id: int) -> dict:
        questionnaire = self._questionnaire(questionnaire_id)
        return {
            "questionnaire": {
                "id": questionnaire.id,
                "name": questionnaire.name,
                "status": questionnaire.status,
                "customer_name": questionnaire.customer_name,
                "source_type": questionnaire.source_type,
                "source_name": questionnaire.source_name,
                "organization_code": questionnaire.organization.code,
                "product_code": questionnaire.product.code,
                "created_at": questionnaire.created_at.isoformat() if questionnaire.created_at else "",
                "updated_at": questionnaire.updated_at.isoformat() if questionnaire.updated_at else "",
            },
            "items": [
                {
                    "id": item.id,
                    "external_id": item.external_id,
                    "section": item.section,
                    "question_text": item.question_text,
                    "normalized_question": item.normalized_question,
                    "suggested_answer": item.suggested_answer,
                    "rationale": item.rationale,
                    "confidence": item.confidence,
                    "review_status": item.review_status,
                    "mapped_unified_control_id": item.mapped_unified_control_id,
                    "mapped_control_implementation_id": item.mapped_control_implementation_id,
                }
                for item in questionnaire.items
            ],
        }

    def export_questionnaire_bundle_json(self, questionnaire_id: int) -> str:
        return json.dumps(self.export_questionnaire_bundle(questionnaire_id), indent=2, ensure_ascii=True)

    def redact_questionnaire_customer(
        self,
        questionnaire_id: int,
        *,
        actor: str = "privacy_service",
        rationale: str = "",
    ) -> CustomerQuestionnaire:
        questionnaire = self._questionnaire(questionnaire_id)
        previous_status = questionnaire.status
        questionnaire.customer_name = ""
        questionnaire.status = "redacted" if questionnaire.status != "deleted" else questionnaire.status
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="customer_questionnaire",
            entity_id=questionnaire.id,
            lifecycle_name="privacy_lifecycle",
            from_state=previous_status,
            to_state=questionnaire.status,
            actor=actor,
            rationale=rationale or "Customer-facing questionnaire identity data was redacted.",
            payload={"questionnaire": questionnaire.name},
        )
        audit_event(
            action="questionnaire_redacted",
            actor=actor,
            target_type="customer_questionnaire",
            target_id=questionnaire.id,
            status="success",
            details={"questionnaire": questionnaire.name},
        )
        metric_event(name="privacy_questionnaire_redacted_total")
        return questionnaire

    def delete_questionnaire(
        self,
        questionnaire_id: int,
        *,
        actor: str = "privacy_service",
        rationale: str = "",
    ) -> dict:
        questionnaire = self._questionnaire(questionnaire_id)
        bundle = self.export_questionnaire_bundle(questionnaire_id)
        self.lifecycle.record_event(
            entity_type="customer_questionnaire",
            entity_id=questionnaire.id,
            lifecycle_name="privacy_lifecycle",
            from_state=questionnaire.status,
            to_state="deleted",
            actor=actor,
            rationale=rationale or "Questionnaire deleted under privacy governance.",
            payload={"questionnaire": questionnaire.name, "item_count": len(questionnaire.items)},
        )
        self.session.delete(questionnaire)
        self.session.flush()
        audit_event(
            action="questionnaire_deleted",
            actor=actor,
            target_type="customer_questionnaire",
            target_id=questionnaire_id,
            status="success",
            details={"item_count": len(bundle["items"])},
        )
        metric_event(name="privacy_questionnaire_deleted_total")
        return {
            "deleted_questionnaire_id": questionnaire_id,
            "deleted_items": len(bundle["items"]),
            "questionnaire_name": bundle["questionnaire"]["name"],
        }

    def _questionnaire(self, questionnaire_id: int) -> CustomerQuestionnaire:
        questionnaire = self.session.scalar(
            select(CustomerQuestionnaire)
            .options(
                selectinload(CustomerQuestionnaire.organization),
                selectinload(CustomerQuestionnaire.product),
                selectinload(CustomerQuestionnaire.items),
            )
            .where(CustomerQuestionnaire.id == questionnaire_id)
        )
        if questionnaire is None:
            raise ValueError(f"Questionnaire not found: {questionnaire_id}")
        return questionnaire
