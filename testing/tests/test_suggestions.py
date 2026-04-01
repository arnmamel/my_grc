from __future__ import annotations

import csv
import os
import tempfile
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.models import AISuggestion, Control, Framework, UnifiedControl, UnifiedControlMapping
from aws_local_audit.services.suggestions import SuggestionService


class SuggestionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        framework = Framework(code="ISO27001_2022", name="ISO 27001", version="2022")
        control = Control(
            framework=framework,
            control_id="A.8.15",
            title="Logging",
            description="Logging and monitoring controls.",
            evidence_query="cloudtrail.multi_region_trail",
        )
        unified = UnifiedControl(
            code="LOGGING_MONITORING",
            name="Logging and Monitoring",
            description="Central logging, monitoring, and alerting controls.",
            domain="security",
            family="monitoring",
        )
        self.session.add_all([framework, control, unified])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()

    def test_capture_and_promote_mapping_suggestion(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as handle:
            writer = csv.DictWriter(handle, fieldnames=["control_id", "title", "description"])
            writer.writeheader()
            writer.writerow(
                {
                    "control_id": "A.8.15",
                    "title": "Logging",
                    "description": "Ensure logging and monitoring coverage is implemented.",
                }
            )
            csv_path = handle.name

        try:
            service = SuggestionService(self.session)
            suggestions = service.capture_mapping_suggestions_from_csv("ISO27001_2022", csv_path, limit=1)
            self.assertEqual(len(suggestions), 1)
            top_match = service.top_match_for_suggestion(suggestions[0])
            self.assertEqual(top_match["unified_control_code"], "LOGGING_MONITORING")

            service.promote_mapping_suggestion(suggestions[0].id, reviewer="tester", notes="Looks correct.")

            mapping = self.session.scalar(select(UnifiedControlMapping))
            self.assertIsNotNone(mapping)
            self.assertEqual(mapping.approval_status, "approved")
            self.assertEqual(mapping.unified_control.code, "LOGGING_MONITORING")
            self.assertTrue(self.session.get(AISuggestion, suggestions[0].id).accepted)
        finally:
            os.unlink(csv_path)


if __name__ == "__main__":
    unittest.main()
