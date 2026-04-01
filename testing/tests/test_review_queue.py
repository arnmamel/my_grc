from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.models import (
    AssessmentRun,
    AwsCliProfile,
    ConfluenceConnection,
    Control,
    EvidenceItem,
    CustomerQuestionnaire,
    CustomerQuestionnaireItem,
    Framework,
    Organization,
    Product,
)
from aws_local_audit.services.review_queue import ReviewQueueService


class ReviewQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

        organization = Organization(code="ACME", name="Acme")
        product = Product(code="PORTAL", name="Portal", organization=organization)
        framework = Framework(code="ISO27001_2022", name="ISO 27001", version="2022")
        control = Control(framework=framework, control_id="A.5.1", title="Policies", evidence_query="manual_review")
        questionnaire = CustomerQuestionnaire(organization=organization, product=product, name="Customer DDQ")
        assessment = AssessmentRun(
            framework=framework,
            status="completed",
            review_status="pending_review",
        )
        self.session.add_all(
            [
                organization,
                product,
                framework,
                control,
                questionnaire,
                assessment,
                AwsCliProfile(profile_name="prod-sso", status="active", last_validation_status="error"),
                ConfluenceConnection(
                    name="MAIN",
                    base_url="https://confluence.example.com",
                    space_key="SEC",
                    secret_name="confluence::MAIN",
                    status="active",
                    last_test_status="error",
                ),
            ]
        )
        self.session.flush()
        self.session.add(
            CustomerQuestionnaireItem(
                questionnaire_id=questionnaire.id,
                question_text="Do you log administrative actions?",
                review_status="suggested",
                confidence=0.55,
                rationale="Drafted from implementation heuristics.",
            )
        )
        self.session.add(
            EvidenceItem(
                framework_id=framework.id,
                control_id=control.id,
                status="manual_action_required",
                summary="Manual evidence is still required.",
                payload_json="{}",
                payload_storage_mode="plaintext",
                lifecycle_status="awaiting_collection",
            )
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()

    def test_queue_surfaces_runtime_and_review_items(self) -> None:
        summary = ReviewQueueService(self.session).summary()
        self.assertGreaterEqual(summary["total"], 5)
        self.assertGreaterEqual(summary["priorities"].get("high", 0), 1)
        self.assertGreaterEqual(summary["categories"].get("evidence_review", 0), 1)


if __name__ == "__main__":
    unittest.main()
