from __future__ import annotations

import csv
import os
import tempfile
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.models import (
    FrameworkImportBatch,
    ImportedRequirement,
    ImportedRequirementReference,
    ReferenceDocument,
    SystemSetting,
    UnifiedControl,
    UnifiedControlMapping,
    UnifiedControlReference,
)
from aws_local_audit.services.framework_imports import FrameworkImportService


class FrameworkImportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    def tearDown(self) -> None:
        self.session.close()

    def test_import_source_creates_traceable_requirements_and_baseline_controls(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as handle:
            writer = csv.DictWriter(handle, fieldnames=["control_id", "title", "description", "domain", "section"])
            writer.writeheader()
            writer.writerow(
                {
                    "control_id": "IAM-01",
                    "title": "Identity lifecycle",
                    "description": "User identities are governed through onboarding, changes, and termination.",
                    "domain": "IAM",
                    "section": "Identity",
                }
            )
            writer.writerow(
                {
                    "control_id": "LOG-02",
                    "title": "Central logging",
                    "description": "Security logging is collected, retained, and reviewed.",
                    "domain": "LOG",
                    "section": "Logging",
                }
            )
            csv_path = handle.name

        try:
            service = FrameworkImportService(self.session)
            result = service.import_source(
                file_path=csv_path,
                framework_code="CSA_CCM_V4",
                framework_name="Cloud Controls Matrix",
                framework_version="4.0",
                source_name="CSA CCM sample",
                mapping_mode="create_baseline",
                auto_approve_mappings=True,
                actor="test_import",
            )

            self.assertEqual(result["summary"]["imported_count"], 2)
            self.assertEqual(result["summary"]["created_unified_controls"], 2)
            self.assertEqual(result["summary"]["created_mappings"], 2)
            self.assertEqual(result["summary"]["created_reference_documents"], 0)
            self.assertEqual(result["summary"]["created_reference_links"], 0)

            self.assertEqual(len(self.session.scalars(select(FrameworkImportBatch)).all()), 1)
            self.assertEqual(len(self.session.scalars(select(ImportedRequirement)).all()), 2)
            self.assertEqual(len(self.session.scalars(select(UnifiedControl)).all()), 2)
            mappings = self.session.scalars(select(UnifiedControlMapping)).all()
            self.assertEqual(len(mappings), 2)
            self.assertTrue(all(item.approval_status == "approved" for item in mappings))

            rows = service.traceability_rows("CSA_CCM_V4")
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(item["mapped_unified_controls"] for item in rows))
        finally:
            os.unlink(csv_path)

    def test_import_secure_controls_framework_sets_pivot_and_creates_reference_links(self) -> None:
        fieldnames = [
            "SCF Domain",
            "SCF Control",
            "SCF #",
            "Secure Controls Framework (SCF) Control Description",
            "Conformity Validation Cadence",
            "Evidence Request List (ERL) #",
            "Possible Solutions & Considerations for a Small-Sized Organization",
            "SCF Control Question",
            "Relative Control Weighting",
            "NIST 800-53 rev5",
            "Spain CCN-STIC 825",
        ]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(
                {
                    "SCF Domain": "Governance",
                    "SCF Control": "Identity lifecycle management",
                    "SCF #": "GOV-01",
                    "Secure Controls Framework (SCF) Control Description": "Manage identity lifecycle events.",
                    "Conformity Validation Cadence": "Quarterly",
                    "Evidence Request List (ERL) #": "ERL-001",
                    "Possible Solutions & Considerations for a Small-Sized Organization": "Use centralized IAM review and approval workflows.",
                    "SCF Control Question": "Are joiner, mover, and leaver actions governed?",
                    "Relative Control Weighting": "High",
                    "NIST 800-53 rev5": "AC-2; IA-4",
                    "Spain CCN-STIC 825": "op.acc.1",
                }
            )
            csv_path = handle.name

        try:
            service = FrameworkImportService(self.session)
            result = service.import_secure_controls_framework(file_path=csv_path, mark_as_pivot=True, sheet_name="")

            self.assertEqual(result["summary"]["imported_count"], 1)
            self.assertEqual(result["summary"]["created_unified_controls"], 1)
            self.assertEqual(result["summary"]["created_mappings"], 1)
            self.assertGreaterEqual(result["summary"]["created_reference_documents"], 2)
            self.assertGreaterEqual(result["summary"]["created_reference_links"], 4)

            pivot = self.session.scalar(
                select(SystemSetting).where(SystemSetting.setting_key == "control_mapping.pivot_framework_code")
            )
            self.assertIsNotNone(pivot)
            self.assertEqual(pivot.setting_value, "SCF_2025_3_1")

            self.assertGreaterEqual(len(self.session.scalars(select(ReferenceDocument)).all()), 2)
            self.assertGreaterEqual(len(self.session.scalars(select(ImportedRequirementReference)).all()), 3)
            self.assertGreaterEqual(len(self.session.scalars(select(UnifiedControlReference)).all()), 3)

            unified_control = self.session.scalar(select(UnifiedControl).where(UnifiedControl.code == "SCF_GOV_01"))
            self.assertIsNotNone(unified_control)
            self.assertIn("Use centralized IAM review", unified_control.implementation_guidance)
        finally:
            os.unlink(csv_path)


if __name__ == "__main__":
    unittest.main()
