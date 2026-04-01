from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.services.phase1_maturity import Phase1MaturityService


class Phase1MaturityTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    def tearDown(self) -> None:
        self.session.close()

    def test_foundation_score_reflects_platform_capability_even_with_empty_workspace(self) -> None:
        assessment = Phase1MaturityService(self.session).assess()
        self.assertGreaterEqual(assessment["overall_score"], 4.0)
        self.assertIn("capabilities", assessment)
        self.assertEqual(len(assessment["areas"]), 7)

    def test_empty_workspace_still_surfaces_operational_gaps(self) -> None:
        assessment = Phase1MaturityService(self.session).assess()
        blockers = assessment["top_blockers"]
        self.assertTrue(any("organization and product scope" in item.lower() or "implementation records" in item.lower() for item in blockers))


if __name__ == "__main__":
    unittest.main()
