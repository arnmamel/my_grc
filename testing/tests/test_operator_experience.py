from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.config import settings
from aws_local_audit.db import Base
from aws_local_audit.models import Framework
from aws_local_audit.services.operator_experience import OperatorExperienceService


class OperatorExperienceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        self.original_log_dir = settings.log_dir
        self.original_audit_log_file = settings.audit_log_file

    def tearDown(self) -> None:
        settings.log_dir = self.original_log_dir
        settings.audit_log_file = self.original_audit_log_file
        self.session.close()

    def test_pilot_checklist_reflects_seeded_frameworks(self) -> None:
        self.session.add(
            Framework(
                code="ISO27001_2022",
                name="ISO/IEC 27001",
                version="2022",
                active=True,
            )
        )
        self.session.flush()

        rows = OperatorExperienceService(self.session).pilot_checklist()
        framework_step = next(item for item in rows if item["step"] == "Seed the framework catalog")
        enabled_step = next(item for item in rows if item["step"] == "Enable at least one framework")

        self.assertTrue(framework_step["complete"])
        self.assertTrue(enabled_step["complete"])

    def test_recent_audit_activity_reads_structured_log_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            audit_path = log_dir / "audit.log"
            audit_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-03-15T08:00:00Z",
                                "action": "workspace_navigation",
                                "actor": "streamlit",
                                "status": "success",
                                "target_type": "workspace_page",
                                "target_id": "Workspace Home",
                                "details": {"mode": "Unified Workspace"},
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-15T08:01:00Z",
                                "action": "asset_created",
                                "actor": "asset_catalog",
                                "status": "success",
                                "target_type": "frameworks",
                                "target_id": 5,
                                "details": {"label": "ISO27001_2022"},
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )
            settings.log_dir = str(log_dir)
            settings.audit_log_file = "audit.log"

            rows = OperatorExperienceService(self.session).recent_audit_activity(limit=10)

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["action"], "asset_created")
            self.assertEqual(rows[1]["action"], "workspace_navigation")


if __name__ == "__main__":
    unittest.main()
