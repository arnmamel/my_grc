from __future__ import annotations

import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.services.delivery_readiness import DeliveryReadinessAssessmentService


class DeliveryReadinessAssessmentTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        self.root = Path(__file__).resolve().parents[2]

    def tearDown(self) -> None:
        self.session.close()

    def test_assessment_returns_five_dimensions_and_verdict(self) -> None:
        payload = DeliveryReadinessAssessmentService(self.session, root=self.root).assess()

        self.assertEqual(payload["version"], "0.3.0")
        self.assertEqual(len(payload["dimensions"]), 5)
        self.assertEqual(len(payload["scorecard"]), 5)
        self.assertTrue(payload["top_release_blockers"])
        self.assertIn(
            payload["deployment_readiness_verdict"]["status"],
            {"Not ready", "Conditionally ready with blockers", "Ready with controlled risk", "Strong readiness"},
        )

    def test_each_dimension_contains_scored_subareas(self) -> None:
        payload = DeliveryReadinessAssessmentService(self.session, root=self.root).assess()

        for dimension in payload["dimensions"]:
            self.assertGreater(len(dimension["subareas"]), 0)
            self.assertGreaterEqual(dimension["score"], 0.0)
            self.assertLessEqual(dimension["score"], 5.0)
            for subarea in dimension["subareas"]:
                self.assertGreaterEqual(subarea["score"], 0.0)
                self.assertLessEqual(subarea["score"], 5.0)
                self.assertTrue(subarea["evidence"])


if __name__ == "__main__":
    unittest.main()
