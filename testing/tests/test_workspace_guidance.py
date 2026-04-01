from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.models import Organization
from aws_local_audit.services.workspace_guidance import WorkspaceGuidanceService
from workspace.ux_redesign import COMMON_ACTIONS, _assistant_action_key


class WorkspaceGuidanceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    def tearDown(self) -> None:
        self.session.close()

    def test_summary_returns_inventory_and_actions_on_empty_workspace(self) -> None:
        summary = WorkspaceGuidanceService(self.session).summary()

        self.assertIn("inventory", summary)
        self.assertTrue(summary["actions"])
        self.assertEqual(summary["actions"][0]["title"], "Complete onboarding foundations")

    def test_summary_reflects_inventory_counts(self) -> None:
        self.session.add(Organization(code="ACME", name="Acme Corp"))
        self.session.flush()

        summary = WorkspaceGuidanceService(self.session).summary()
        org_row = next(item for item in summary["inventory"] if item["key"] == "organizations")

        self.assertEqual(org_row["count"], 1)
        self.assertGreaterEqual(summary["phase1"]["overall_score"], 0.0)

    def test_assistant_action_keys_are_unique_for_displayed_actions(self) -> None:
        keys = [_assistant_action_key(index, action) for index, action in enumerate(COMMON_ACTIONS[:3])]

        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
