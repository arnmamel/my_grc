from __future__ import annotations

import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.services.product_about import ProductAboutService


class ProductAboutServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        self.root = Path(__file__).resolve().parents[2]
        self.service = ProductAboutService(self.session, root=self.root)

    def tearDown(self) -> None:
        self.session.close()

    def test_about_payload_loads_release_and_assessment_history(self) -> None:
        payload = self.service.about_payload()

        self.assertEqual(payload["product_name"], "my_grc")
        self.assertEqual(payload["version"], "0.3.0")
        self.assertTrue(payload["release_history"])
        self.assertTrue(payload["maturity_history"])
        self.assertTrue(payload["assessment_documents"])

    def test_feedback_mailbox_round_trip(self) -> None:
        created = self.service.submit_feedback(
            subject="Need easier export",
            message="Please add a simpler release export for audit packs.",
            area="Reporting",
            page_context="About",
            reporter_name="A. Practitioner",
            reporter_role="GRC Analyst",
            contact="analyst@example.com",
        )
        self.session.commit()

        rows = self.service.list_feedback()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject"], "Need easier export")
        self.assertEqual(rows[0]["status"], "new")

        updated = self.service.update_feedback_status(created.id, "reviewed")
        self.assertEqual(updated.status, "reviewed")


if __name__ == "__main__":
    unittest.main()
