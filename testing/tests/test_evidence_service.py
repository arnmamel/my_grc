from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.models import (
    AssessmentRun,
    AssessmentRunItem,
    Control,
    EvidenceCollectionPlan,
    EvidenceItem,
    Framework,
    Organization,
    OrganizationFrameworkBinding,
)
from aws_local_audit.services.assessments import AssessmentService
from aws_local_audit.services.evidence import EvidenceService


class EvidenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    def tearDown(self) -> None:
        self.session.close()

    def _binding_fixture(self, with_plan: bool = True) -> tuple[Framework, Control, OrganizationFrameworkBinding]:
        organization = Organization(code="ACME", name="Acme")
        framework = Framework(code="ISO27001_2022", name="ISO 27001", version="2022")
        control = Control(
            framework=framework,
            control_id="A.5.1",
            title="Policies",
            evidence_query="manual_review",
            description="Policy evidence is gathered manually.",
        )
        binding = OrganizationFrameworkBinding(
            organization=organization,
            framework=framework,
            binding_code="ACME_ISO27001",
            name="Acme ISO 27001",
            aws_profile="prod-sso",
            aws_region="eu-west-1",
        )
        self.session.add_all([organization, framework, control, binding])
        self.session.flush()
        if with_plan:
            self.session.add(
                EvidenceCollectionPlan(
                    plan_code="PLAN_ISO27001_2022_A_5_1",
                    name="ISO A.5.1 evidence plan",
                    framework_id=framework.id,
                    control_id=control.id,
                    scope_type="binding",
                    execution_mode="manual",
                    evidence_type="manual_artifact",
                    instructions="Upload the approved policy document or screenshot evidence.",
                    lifecycle_status="ready",
                )
            )
        self.session.commit()
        return framework, control, binding

    def test_collect_for_binding_creates_manual_action_item_for_ready_manual_plan(self) -> None:
        _, _, binding = self._binding_fixture(with_plan=True)

        service = EvidenceService(self.session)
        collection_plan = service.build_collection_plan_for_binding(binding.binding_code)
        results = service.collect_for_binding(binding.binding_code)

        self.assertEqual(collection_plan["profiles"], [])
        self.assertEqual(len(results), 1)
        evidence = results[0]
        self.assertEqual(evidence.status, "manual_action_required")
        self.assertEqual(evidence.lifecycle_status, "awaiting_collection")
        payload = service.decrypt_payload(evidence)
        self.assertEqual(payload["plan"]["plan_status"], "ready")
        self.assertEqual(payload["collection_mode"], "manual")

    def test_collect_for_binding_requires_plan_before_collection(self) -> None:
        _, _, binding = self._binding_fixture(with_plan=False)

        service = EvidenceService(self.session)
        collection_plan = service.build_collection_plan_for_binding(binding.binding_code)
        results = service.collect_for_binding(binding.binding_code)

        self.assertEqual(collection_plan["profiles"], [])
        self.assertEqual(len(results), 1)
        evidence = results[0]
        self.assertEqual(evidence.status, "plan_missing")
        self.assertEqual(evidence.lifecycle_status, "awaiting_collection")

    def test_assessment_review_is_blocked_when_evidence_is_unresolved(self) -> None:
        framework, control, _ = self._binding_fixture(with_plan=True)
        evidence = EvidenceItem(
            framework_id=framework.id,
            control_id=control.id,
            status="manual_action_required",
            summary="Manual collection still required.",
            payload_json="{}",
            payload_storage_mode="plaintext",
            lifecycle_status="awaiting_collection",
        )
        run = AssessmentRun(
            framework_id=framework.id,
            status="completed",
            review_status="pending_review",
            assurance_status="needs_evidence",
        )
        self.session.add_all([evidence, run])
        self.session.flush()
        self.session.add(
            AssessmentRunItem(
                assessment_run_id=run.id,
                framework_id=framework.id,
                control_id=control.id,
                evidence_item_id=evidence.id,
                status=evidence.status,
                score=0,
                summary=evidence.summary,
            )
        )
        self.session.commit()

        with self.assertRaises(ValueError):
            AssessmentService(self.session).review_run(
                run_id=run.id,
                review_status="approved",
                assurance_status="accepted",
                actor="reviewer",
            )

    def test_assessment_review_can_close_when_evidence_is_collected(self) -> None:
        framework, control, _ = self._binding_fixture(with_plan=True)
        evidence = EvidenceItem(
            framework_id=framework.id,
            control_id=control.id,
            status="pass",
            summary="Policy evidence validated.",
            payload_json="{}",
            payload_storage_mode="plaintext",
            lifecycle_status="collected",
        )
        run = AssessmentRun(
            framework_id=framework.id,
            status="completed",
            review_status="pending_review",
            assurance_status="assessed",
        )
        self.session.add_all([evidence, run])
        self.session.flush()
        self.session.add(
            AssessmentRunItem(
                assessment_run_id=run.id,
                framework_id=framework.id,
                control_id=control.id,
                evidence_item_id=evidence.id,
                status=evidence.status,
                score=100,
                summary=evidence.summary,
            )
        )
        self.session.commit()

        updated = AssessmentService(self.session).review_run(
            run_id=run.id,
            review_status="approved",
            assurance_status="accepted",
            actor="reviewer",
        )
        self.assertEqual(updated.review_status, "approved")
        self.assertEqual(updated.assurance_status, "accepted")


if __name__ == "__main__":
    unittest.main()
