from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.models import Control, CustomerQuestionnaire, CustomerQuestionnaireItem, EvidenceItem, Framework, Organization, Product
from aws_local_audit.services.privacy_lifecycle import PrivacyLifecycleService


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PrivacyLifecycleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        self.service = PrivacyLifecycleService(self.session)
        self.now = _utc_now_naive()

        organization = Organization(code="ORG1", name="Org 1")
        framework = Framework(code="ISO27001_2022", name="ISO/IEC 27001", version="2022")
        product = Product(organization=organization, code="PROD1", name="Product 1")
        control = Control(framework=framework, control_id="A.5.1", title="Policies for information security", evidence_query="manual")
        self.session.add_all([organization, framework, product, control])
        self.session.flush()

        questionnaire = CustomerQuestionnaire(
            organization_id=organization.id,
            product_id=product.id,
            name="Customer Security Questionnaire",
            customer_name="Customer A",
            source_type="xlsx",
            source_name="customer_a.xlsx",
            status="approved",
            created_at=self.now - timedelta(days=500),
            updated_at=self.now - timedelta(days=500),
        )
        self.session.add(questionnaire)
        self.session.flush()
        questionnaire_item = CustomerQuestionnaireItem(
            questionnaire_id=questionnaire.id,
            external_id="Q-1",
            question_text="Do you have an information security policy?",
            normalized_question="do you have an information security policy?",
            suggested_answer="Yes. The policy is approved and reviewed annually.",
            rationale="Mapped to the product control implementation for policy governance.",
            confidence=0.93,
            review_status="approved",
        )
        evidence = EvidenceItem(
            organization_id=organization.id,
            product_id=product.id,
            framework_id=framework.id,
            control_id=control.id,
            evidence_key="EVID-001",
            status="approved",
            summary="Annual policy evidence",
            payload_json="{}",
            collected_at=self.now - timedelta(days=365),
            expires_at=self.now - timedelta(days=10),
        )
        self.session.add_all([questionnaire_item, evidence])
        self.session.commit()

        self.questionnaire_id = questionnaire.id

    def tearDown(self) -> None:
        self.session.close()

    def test_retention_report_detects_due_questionnaires_and_expired_evidence(self) -> None:
        report = self.service.retention_report(questionnaire_retention_days=365, evidence_freshness_days=180, now=self.now)

        self.assertEqual(report["counts"]["questionnaires_due_for_review"], 1)
        self.assertEqual(report["counts"]["expired_evidence"], 1)
        self.assertEqual(report["counts"]["stale_evidence"], 1)

    def test_export_questionnaire_bundle_returns_questions_and_answers(self) -> None:
        bundle = self.service.export_questionnaire_bundle(self.questionnaire_id)

        self.assertEqual(bundle["questionnaire"]["customer_name"], "Customer A")
        self.assertEqual(len(bundle["items"]), 1)
        self.assertEqual(bundle["items"][0]["external_id"], "Q-1")

    def test_redact_questionnaire_customer_clears_customer_name(self) -> None:
        questionnaire = self.service.redact_questionnaire_customer(self.questionnaire_id, actor="tester")
        self.session.commit()

        self.assertEqual(questionnaire.customer_name, "")
        self.assertEqual(questionnaire.status, "redacted")

    def test_delete_questionnaire_removes_questionnaire_and_items(self) -> None:
        report = self.service.delete_questionnaire(self.questionnaire_id, actor="tester")
        self.session.commit()

        self.assertEqual(report["deleted_items"], 1)
        self.assertIsNone(self.session.scalar(select(CustomerQuestionnaire).where(CustomerQuestionnaire.id == self.questionnaire_id)))
        self.assertEqual(
            len(self.session.scalars(select(CustomerQuestionnaireItem)).all()),
            0,
        )


if __name__ == "__main__":
    unittest.main()
