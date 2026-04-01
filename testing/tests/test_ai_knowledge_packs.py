from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.ai_pack_loader import load_template_by_code
from aws_local_audit.db import Base
from aws_local_audit.models import Control, ControlMetadata, Framework
from aws_local_audit.services.knowledge_packs import AIKnowledgePackService
from aws_local_audit.services.workbench import WorkbenchService


class AIKnowledgePackTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        self.workbench = WorkbenchService(self.session)
        self.service = AIKnowledgePackService(self.session)

        framework = Framework(code="ISO27001_2022", name="ISO/IEC 27001:2022", version="2022")
        scf = Framework(code="SCF_2025_3_1", name="Secure Controls Framework", version="2025.3.1")
        self.session.add_all([framework, scf])
        self.session.flush()
        control = Control(
            framework_id=framework.id,
            control_id="A.5.1",
            title="Policies for information security",
            description="Define, approve, publish, and periodically review information security policies.",
            evidence_query="manual.policy_review",
            severity="high",
        )
        self.session.add(control)
        self.session.flush()
        self.session.add(
            ControlMetadata(
                control_id=control.id,
                summary="Define and review approved information security policies.",
                aws_guidance="Store approved policies in a governed repository and review them periodically.",
                check_type="manual",
                source_reference="ISO27001_2022 A.5.1",
            )
        )
        self.session.flush()

        self.workbench.create_organization("Acme", code="ACME")
        self.workbench.create_product("ACME", "Customer Portal", code="CUSTOMER_PORTAL")
        self.workbench.create_unified_control(
            code="SCF_POL_001",
            name="Security policy governance",
            description="Maintain approved security policies and periodic review.",
            implementation_guidance="Maintain policy ownership, approval, publication, and review.",
            test_guidance="Verify approval, publication, and review cadence.",
        )
        self.workbench.map_framework_control(
            unified_control_code="SCF_POL_001",
            framework_code="ISO27001_2022",
            control_id="A.5.1",
            approval_status="approved",
            reviewed_by="tester",
            rationale="Policy governance covers the requirement intent.",
        )
        self.workbench.upsert_control_implementation(
            organization_code="ACME",
            product_code="CUSTOMER_PORTAL",
            unified_control_code="SCF_POL_001",
            framework_code="ISO27001_2022",
            control_id="A.5.1",
            title="Customer Portal policy governance",
            objective="Ensure security policies are approved and periodically reviewed.",
            impl_general="Policy set is owned by the security team and reviewed annually.",
            impl_aws="Policies for AWS environments are stored in a governed repository.",
            test_plan="Review approval records and repository controls.",
        )
        self.workbench.upsert_product_control_profile(
            organization_code="ACME",
            product_code="CUSTOMER_PORTAL",
            unified_control_code="SCF_POL_001",
            framework_code="ISO27001_2022",
            control_id="A.5.1",
            assessment_mode="assisted",
            maturity_governance=4,
            maturity_implementation=4,
            maturity_observability=3,
            maturity_automation=2,
            maturity_assurance=3,
            rationale="Pilot control path for governed copilot drafting.",
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()

    def test_pack_template_seeds_tasks_and_eval_cases(self) -> None:
        pack = self.service.upsert_pack_from_template(load_template_by_code("SCF_ISO27001_ANNEX_A"))
        self.assertEqual(pack.pack_code, "SCF_ISO27001_ANNEX_A")
        version = self.service.active_version(pack.pack_code)
        self.assertEqual(len(version.tasks), 3)
        self.assertGreaterEqual(len(version.eval_cases), 3)
        self.assertGreaterEqual(len(version.references), 2)

    def test_build_task_package_returns_governed_draft(self) -> None:
        self.service.upsert_pack_from_template(load_template_by_code("SCF_ISO27001_ANNEX_A"))
        bundle = self.service.build_task_package(
            pack_code="SCF_ISO27001_ANNEX_A",
            task_key="mapping_rationale",
            framework_code="ISO27001_2022",
            control_id="A.5.1",
            unified_control_code="SCF_POL_001",
            organization_code="ACME",
            product_code="CUSTOMER_PORTAL",
        )
        self.assertEqual(bundle["prompt_package"]["pack_code"], "SCF_ISO27001_ANNEX_A")
        self.assertEqual(bundle["draft_response"]["task_key"], "mapping_rationale")
        self.assertTrue(bundle["citations"])
        self.assertIn("mapping_summary", bundle["draft_response"]["draft"])

    def test_capture_task_suggestion_stores_governed_ai_output(self) -> None:
        self.service.upsert_pack_from_template(load_template_by_code("SCF_ISO27001_ANNEX_A"))
        suggestion = self.service.capture_task_suggestion(
            pack_code="SCF_ISO27001_ANNEX_A",
            task_key="implementation_narrative",
            framework_code="ISO27001_2022",
            control_id="A.5.1",
            unified_control_code="SCF_POL_001",
            organization_code="ACME",
            product_code="CUSTOMER_PORTAL",
        )
        self.assertEqual(suggestion.provider, "knowledge_pack")
        self.assertEqual(suggestion.task_key, "implementation_narrative")
        self.assertTrue(suggestion.citations_json)


if __name__ == "__main__":
    unittest.main()
