from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.services.validation import ValidationError
from aws_local_audit.services.workspace_auth import WorkspaceAuthService, WorkspaceAuthenticationError


class WorkspaceAuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        self.service = WorkspaceAuthService(self.session)

    def tearDown(self) -> None:
        self.session.close()

    def test_bootstrap_and_authenticate_local_user(self) -> None:
        principal = self.service.bootstrap_local_admin(
            principal_key="grc.lead",
            display_name="GRC Lead",
            password="MyStr0ng!Password",
            email="lead@example.com",
        )

        authenticated = self.service.authenticate(principal.principal_key, "MyStr0ng!Password")
        self.assertEqual(authenticated.principal_key, "grc.lead")
        self.assertEqual(self.service.credential_count(), 1)
        self.assertEqual(self.service.health_summary()["status"], "pass")

    def test_failed_password_attempts_trigger_lock(self) -> None:
        self.service.bootstrap_local_admin(
            principal_key="grc.lead",
            display_name="GRC Lead",
            password="MyStr0ng!Password",
        )
        for _ in range(5):
            with self.assertRaises(WorkspaceAuthenticationError):
                self.service.authenticate("grc.lead", "wrong-password")
        with self.assertRaises(WorkspaceAuthenticationError):
            self.service.authenticate("grc.lead", "MyStr0ng!Password")

    def test_set_password_rejects_weak_password(self) -> None:
        principal = self.service.bootstrap_local_admin(
            principal_key="grc.lead",
            display_name="GRC Lead",
            password="MyStr0ng!Password",
        )
        with self.assertRaises(ValidationError):
            self.service.set_password(principal.principal_key, password="weak")


if __name__ == "__main__":
    unittest.main()
