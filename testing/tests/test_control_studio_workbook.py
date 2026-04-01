from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.services.control_studio_workbook import ControlStudioWorkbookService
from aws_local_audit.services.foundation_uplift import (
    FoundationUpliftService,
    LOCAL_WORKSPACE_ORG_CODE,
    LOCAL_WORKSPACE_PRODUCT_CODE,
    SCF_PIVOT_EXERCISE_UNIFIED_CONTROL,
)


class ControlStudioWorkbookServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        FoundationUpliftService(self.session).ensure_phase1_backbone_path()
        self.service = ControlStudioWorkbookService(self.session)

    def tearDown(self) -> None:
        self.session.close()

    def test_control_register_rows_include_baseline_fields(self) -> None:
        rows = self.service.control_register_rows(
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )

        row = next(item for item in rows if item["SCF Control"] == SCF_PIVOT_EXERCISE_UNIFIED_CONTROL)
        self.assertNotEqual(row["Requirement Coverage Summary"], "")
        self.assertNotEqual(row["Implementation Guidance"], "")
        self.assertNotEqual(row["Test Guidance"], "")
        self.assertEqual(row["Default Severity"], "high")

    def test_apply_control_register_rows_updates_scope_narrative(self) -> None:
        rows = self.service.control_register_rows(
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )
        row = next(item for item in rows if item["SCF Control"] == SCF_PIVOT_EXERCISE_UNIFIED_CONTROL)
        row["SoA Rationale"] = "Scoped as applicable because policy governance is mandatory."
        row["Implementation Narrative"] = "Updated implementation narrative from workbook test."
        row["Owner"] = "control_owner"

        result = self.service.apply_control_register_rows(
            [row],
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )

        self.assertEqual(result["errors"], [])
        refreshed = self.service.control_register_rows(
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )
        refreshed_row = next(item for item in refreshed if item["SCF Control"] == SCF_PIVOT_EXERCISE_UNIFIED_CONTROL)
        self.assertEqual(refreshed_row["SoA Rationale"], "Scoped as applicable because policy governance is mandatory.")
        self.assertEqual(refreshed_row["Implementation Narrative"], "Updated implementation narrative from workbook test.")
        self.assertEqual(refreshed_row["Owner"], "control_owner")

    def test_apply_testing_rows_updates_testing_and_target_data(self) -> None:
        rows = self.service.testing_rows(
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )
        row = next(item for item in rows if item["SCF Control"] == SCF_PIVOT_EXERCISE_UNIFIED_CONTROL)
        row["Evidence Strategy"] = "Manual evidence plus quarterly governance review."
        row["Implementation Test Plan"] = "Review policy ownership and approval artifacts."
        row["Plan Status"] = "approved"
        row["AWS Profile"] = "workspace-sso"
        row["AWS Account ID"] = "123456789012"
        row["AWS Regions"] = "eu-west-1, eu-central-1"
        row["Target Status"] = "active"

        result = self.service.apply_testing_rows(
            [row],
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )

        self.assertEqual(result["errors"], [])
        refreshed_controls = self.service.control_register_rows(
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )
        refreshed_control = next(item for item in refreshed_controls if item["SCF Control"] == SCF_PIVOT_EXERCISE_UNIFIED_CONTROL)
        self.assertEqual(refreshed_control["Evidence Strategy"], "Manual evidence plus quarterly governance review.")
        self.assertEqual(refreshed_control["Testing Plan"], "Review policy ownership and approval artifacts.")

        refreshed_testing = self.service.testing_rows(
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )
        refreshed_row = next(item for item in refreshed_testing if item["SCF Control"] == SCF_PIVOT_EXERCISE_UNIFIED_CONTROL)
        self.assertTrue(refreshed_row["Plan Code"])
        self.assertEqual(refreshed_row["AWS Profile"], "workspace-sso")
        self.assertEqual(refreshed_row["AWS Account ID"], "123456789012")

    def test_export_workbook_bytes_returns_xlsx_payload(self) -> None:
        payload = self.service.export_workbook_bytes(
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )

        self.assertTrue(payload.startswith(b"PK"))
        self.assertGreater(len(payload), 1000)


if __name__ == "__main__":
    unittest.main()
