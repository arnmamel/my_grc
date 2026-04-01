from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.models import (
    ControlImplementation,
    EvidenceCollectionPlan,
    Organization,
    Product,
    ProductControlProfile,
    ProductFlavor,
    UnifiedControl,
    UnifiedControlMapping,
)
from aws_local_audit.services.foundation_uplift import (
    FoundationUpliftService,
    ISO_ANNEX_A_EXERCISE_CONTROL_ID,
    ISO_ANNEX_A_FRAMEWORK_CODE,
    LOCAL_WORKSPACE_FLAVOR_CODE,
    LOCAL_WORKSPACE_ORG_CODE,
    LOCAL_WORKSPACE_PRODUCT_CODE,
    SCF_PIVOT_EXERCISE_UNIFIED_CONTROL,
)
from aws_local_audit.services.governance import GovernanceService


class FoundationUpliftServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    def tearDown(self) -> None:
        self.session.close()

    def test_ensure_phase1_backbone_path_creates_real_scoped_records(self) -> None:
        service = FoundationUpliftService(self.session)

        result = service.ensure_phase1_backbone_path()

        self.assertEqual(GovernanceService(self.session).pivot_framework_code(), "SCF_2025_3_1")
        self.assertEqual(result["framework_code"], ISO_ANNEX_A_FRAMEWORK_CODE)
        self.assertEqual(result["control_id"], ISO_ANNEX_A_EXERCISE_CONTROL_ID)
        self.assertEqual(result["unified_control_code"], SCF_PIVOT_EXERCISE_UNIFIED_CONTROL)

        organization = self.session.scalar(select(Organization).where(Organization.code == LOCAL_WORKSPACE_ORG_CODE))
        product = self.session.scalar(
            select(Product).where(Product.organization_id == organization.id, Product.code == LOCAL_WORKSPACE_PRODUCT_CODE)
        )
        flavor = self.session.scalar(
            select(ProductFlavor).where(ProductFlavor.product_id == product.id, ProductFlavor.code == LOCAL_WORKSPACE_FLAVOR_CODE)
        )
        unified = self.session.scalar(select(UnifiedControl).where(UnifiedControl.code == SCF_PIVOT_EXERCISE_UNIFIED_CONTROL))
        mapping = self.session.scalar(
            select(UnifiedControlMapping).where(UnifiedControlMapping.unified_control_id == unified.id)
        )
        implementation = self.session.scalar(
            select(ControlImplementation).where(ControlImplementation.unified_control_id == unified.id)
        )
        profile = self.session.scalar(
            select(ProductControlProfile).where(ProductControlProfile.unified_control_id == unified.id)
        )
        plan = self.session.scalar(
            select(EvidenceCollectionPlan).where(EvidenceCollectionPlan.plan_code == "PHASE1_SCF_PIVOT_A_5_1")
        )

        self.assertIsNotNone(organization)
        self.assertIsNotNone(product)
        self.assertIsNotNone(flavor)
        self.assertIsNotNone(unified)
        self.assertEqual(mapping.approval_status, "approved")
        self.assertEqual(implementation.product_flavor_id, flavor.id)
        self.assertEqual(profile.product_flavor_id, flavor.id)
        self.assertEqual(profile.control_implementation_id, implementation.id)
        self.assertEqual(plan.unified_control_id, unified.id)
        self.assertEqual(plan.lifecycle_status, "approved")

    def test_phase1_backbone_status_reflects_exercised_path(self) -> None:
        service = FoundationUpliftService(self.session)
        before = service.phase1_backbone_status()
        self.assertFalse(before["approved_mapping_present"])

        service.ensure_phase1_backbone_path()
        after = service.phase1_backbone_status()

        self.assertTrue(after["framework_seeded"])
        self.assertTrue(after["iso_control_present"])
        self.assertTrue(after["pivot_unified_control_present"])
        self.assertTrue(after["approved_mapping_present"])
        self.assertTrue(after["organization_present"])
        self.assertTrue(after["product_present"])
        self.assertTrue(after["flavor_present"])
        self.assertTrue(after["implementation_present"])
        self.assertTrue(after["product_control_profile_present"])
        self.assertTrue(after["evidence_plan_present"])


if __name__ == "__main__":
    unittest.main()
