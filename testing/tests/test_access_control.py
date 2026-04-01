from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.services.access_control import AccessControlService
from aws_local_audit.services.asset_catalog import AssetCatalogService
from aws_local_audit.services.platform_foundation import HealthCheckService


class AccessControlTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
        self.service = AccessControlService(self.session)
        self.service.seed_default_roles()

    def tearDown(self) -> None:
        self.session.close()

    def test_default_roles_are_seeded(self) -> None:
        roles = self.service.list_roles()
        self.assertGreaterEqual(len(roles), 7)
        self.assertTrue(any(item.role_key == "org_admin" for item in roles))

    def test_privileged_assignment_requires_approval(self) -> None:
        principal = self.service.upsert_principal(principal_key="alice", display_name="Alice", organization_id=1)
        assignment = self.service.assign_role(
            principal_key=principal.principal_key,
            role_key="org_admin",
            actor="seed",
            organization_id=1,
        )
        self.assertEqual(assignment.approval_status, "pending_review")

    def test_permission_check_respects_scope(self) -> None:
        catalog = AssetCatalogService(self.session)
        organization = catalog.create_asset("organizations", {"code": "ACME", "name": "Acme"})
        business_unit = catalog.create_asset(
            "business_units",
            {"organization_id": str(organization.id), "code": "PLATFORM", "name": "Platform"},
        )
        product = catalog.create_asset(
            "products",
            {
                "organization_id": str(organization.id),
                "business_unit_id": str(business_unit.id),
                "code": "PORTAL",
                "name": "Portal",
            },
        )
        self.service.upsert_principal(principal_key="bob", display_name="Bob", organization_id=organization.id)
        assignment = self.service.assign_role(
            principal_key="bob",
            role_key="control_owner",
            actor="seed",
            product_id=product.id,
            organization_id=organization.id,
            approved_by="approver",
        )
        self.assertEqual(assignment.approval_status, "approved")
        self.assertTrue(
            self.service.can(
                "bob",
                "evidence.collect",
                {"organization_id": organization.id, "product_id": product.id},
            )
        )
        self.assertFalse(
            self.service.can(
                "bob",
                "evidence.collect",
                {"organization_id": organization.id, "product_id": product.id + 1},
            )
        )

    def test_scope_validation_rejects_invalid_assignment(self) -> None:
        self.service.upsert_principal(principal_key="dave", display_name="Dave", organization_id=1)
        with self.assertRaises(ValueError):
            self.service.assign_role(principal_key="dave", role_key="control_owner", actor="seed", organization_id=1)

    def test_segregation_conflicts_are_detected(self) -> None:
        self.service.upsert_principal(principal_key="carol", display_name="Carol", organization_id=1)
        self.service.assign_role(
            principal_key="carol",
            role_key="control_owner",
            actor="seed",
            organization_id=1,
            product_id=1,
            approved_by="approver",
        )
        self.service.assign_role(
            principal_key="carol",
            role_key="auditor",
            actor="seed",
            organization_id=1,
            product_id=1,
            approved_by="approver",
        )
        conflicts = self.service.segregation_conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["principal_key"], "carol")

    def test_health_check_reports_rbac(self) -> None:
        report = HealthCheckService(self.session).run()
        rbac_check = next(item for item in report["checks"] if item["name"] == "rbac")
        self.assertEqual(rbac_check["status"], "warn")


if __name__ == "__main__":
    unittest.main()
