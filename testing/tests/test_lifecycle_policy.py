from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.services.lifecycle import LifecycleService, LifecycleTransitionError


class LifecyclePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        self.lifecycle = LifecycleService(self.session)

    def tearDown(self) -> None:
        self.session.close()

    def test_allows_mapping_transition_from_proposed_to_approved(self) -> None:
        self.lifecycle.ensure_transition(
            entity_type="unified_control_mapping",
            lifecycle_name="control_lifecycle",
            from_state="proposed",
            to_state="approved",
        )

    def test_blocks_invalid_mapping_transition(self) -> None:
        with self.assertRaises(LifecycleTransitionError):
            self.lifecycle.ensure_transition(
                entity_type="unified_control_mapping",
                lifecycle_name="control_lifecycle",
                from_state="approved",
                to_state="proposed",
            )

    def test_allows_framework_binding_transition_from_active_to_disabled(self) -> None:
        self.lifecycle.ensure_transition(
            entity_type="framework_binding",
            lifecycle_name="framework_binding_lifecycle",
            from_state="active",
            to_state="disabled",
        )

    def test_blocks_invalid_aws_target_transition_from_retired_to_active(self) -> None:
        with self.assertRaises(LifecycleTransitionError):
            self.lifecycle.ensure_transition(
                entity_type="aws_evidence_target",
                lifecycle_name="evidence_lifecycle",
                from_state="retired",
                to_state="active",
            )


if __name__ == "__main__":
    unittest.main()
