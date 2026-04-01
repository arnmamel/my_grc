from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.services.control_matrix import ControlMatrixService
from aws_local_audit.services.foundation_uplift import (
    FoundationUpliftService,
    LOCAL_WORKSPACE_ORG_CODE,
    LOCAL_WORKSPACE_PRODUCT_CODE,
    SCF_PIVOT_EXERCISE_UNIFIED_CONTROL,
)


class ControlMatrixServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    def tearDown(self) -> None:
        self.session.close()

    def test_setup_guidance_requests_foundation_when_workspace_is_empty(self) -> None:
        service = ControlMatrixService(self.session)

        guidance = service.setup_guidance()

        self.assertTrue(any(item["page"] == "Wizards" for item in guidance))
        self.assertTrue(any("Create an organization" == item["title"] for item in guidance))

    def test_matrix_rows_surface_scf_scope_data_for_exercised_path(self) -> None:
        FoundationUpliftService(self.session).ensure_phase1_backbone_path()
        service = ControlMatrixService(self.session)

        rows = service.matrix_rows(
            organization_code=LOCAL_WORKSPACE_ORG_CODE,
            product_code=LOCAL_WORKSPACE_PRODUCT_CODE,
        )

        row = next(item for item in rows if item["SCF Control"] == SCF_PIVOT_EXERCISE_UNIFIED_CONTROL)
        self.assertEqual(row["SoA"], "applicable")
        self.assertIn("ISO27001_2022", row["Mapped Standards"])
        self.assertNotEqual(row["Implementation Summary"], "")
        self.assertNotEqual(row["Evidence Plan"], "Not defined")


if __name__ == "__main__":
    unittest.main()
