from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.services.questionnaires import QuestionnaireService
from aws_local_audit.services.workbench import WorkbenchService


class QuestionnaireServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        self.workbench = WorkbenchService(self.session)
        self.service = QuestionnaireService(self.session)

        self.workbench.create_organization(name="Org One", code="ORG1")
        self.workbench.create_product(organization_code="ORG1", name="Product Alpha", code="PRODA")
        self.workbench.upsert_control_implementation(
            organization_code="ORG1",
            product_code="PRODA",
            unified_control_code=None,
            title="Access review implementation",
            objective="Ensure access is reviewed and approved.",
            impl_general="Access is approved by the control owner and reviewed quarterly.",
            impl_aws="AWS access is federated through IAM Identity Center with least-privilege role assignments.",
            test_plan="Review access reports and approval records.",
        )

    def tearDown(self) -> None:
        self.session.close()

    def _write_csv(self, rows: list[dict]) -> str:
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        path = Path(handle.name)
        try:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
            return str(path)
        finally:
            handle.close()

    def test_preview_and_reuse_answers_for_selected_scope(self) -> None:
        source_path = self._write_csv(
            [
                {"question": "Access is approved by the control owner and reviewed quarterly."},
            ]
        )
        try:
            preview = self.service.preview_questionnaire_answers_from_file(
                [{"organization_code": "ORG1", "product_code": "PRODA"}],
                source_path,
            )
            self.assertEqual(len(preview), 1)
            self.assertIn("Access is approved", preview[0]["answer"])

            questionnaire = self.service.import_questionnaire_file(
                primary_organization_code="ORG1",
                primary_product_code="PRODA",
                file_path=source_path,
                name="Customer Access Questionnaire",
                customer_name="Customer A",
                scope_refs=[{"organization_code": "ORG1", "product_code": "PRODA"}],
            )
            self.assertEqual(questionnaire.name, "Customer Access Questionnaire")
            self.session.flush()

            reusable = self.service.reusable_answers(
                "Access is approved by the control owner and reviewed quarterly.",
                scope_refs=[{"organization_code": "ORG1", "product_code": "PRODA"}],
            )
            self.assertEqual(len(reusable), 1)
            self.assertIn("Access is approved", reusable[0]["answer"])
        finally:
            Path(source_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
