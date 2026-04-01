from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.integrations.confluence import ConfluenceClient
from aws_local_audit.models import (
    AuthorityDocument,
    ConfluenceConnection,
    FeatureFlag,
    Framework,
)
from aws_local_audit.services.asset_catalog import AssetCatalogService
from aws_local_audit.services.lifecycle import LifecycleService
from aws_local_audit.services.platform_foundation import (
    AuditTrailService,
    FeatureFlagService,
    HealthCheckService,
    ResilienceError,
    ResilienceService,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class PlatformFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    def tearDown(self) -> None:
        self.session.close()

    def test_feature_flag_service_round_trip(self) -> None:
        service = FeatureFlagService(self.session)
        service.ensure_flag(
            flag_key="ops.health_panel",
            name="Health Panel",
            description="Show platform health in the unified workspace.",
            enabled=False,
        )
        updated = service.set_flag("ops.health_panel", True, actor="test")
        self.assertTrue(updated.enabled)
        self.assertTrue(service.enabled("ops.health_panel"))
        self.assertEqual(len(service.list_flags()), 1)

    def test_lifecycle_events_are_tamper_evident(self) -> None:
        lifecycle = LifecycleService(self.session)
        lifecycle.record_event(
            entity_type="framework",
            entity_id=1,
            lifecycle_name="framework_lifecycle",
            to_state="draft",
            actor="test",
            payload={"code": "ISO27001"},
        )
        lifecycle.record_event(
            entity_type="framework",
            entity_id=1,
            lifecycle_name="framework_lifecycle",
            from_state="draft",
            to_state="active",
            actor="test",
            payload={"code": "ISO27001"},
        )
        report = AuditTrailService(self.session).verify_chain()
        self.assertTrue(report["valid"])
        self.assertEqual(report["events"], 2)

    def test_resilience_service_opens_circuit_after_repeated_failures(self) -> None:
        service = ResilienceService(self.session)
        for _ in range(3):
            service.record_failure(
                integration_key="confluence::default",
                operation="create_page",
                idempotency_key="page-1",
                request_payload={"title": "Assessment"},
                error_message="boom",
            )
        with self.assertRaises(ResilienceError):
            service.assert_call_allowed("confluence::default")

    def test_health_check_reports_registered_flags(self) -> None:
        self.session.add(FeatureFlag(flag_key="release.canary", name="Canary"))
        self.session.flush()
        report = HealthCheckService(self.session).run()
        feature_flag_check = next(item for item in report["checks"] if item["name"] == "feature_flags")
        self.assertEqual(feature_flag_check["status"], "pass")

    def test_asset_catalog_supports_business_unit_and_asset_crud(self) -> None:
        authority = AuthorityDocument(document_key="AUTH", name="Authority", version="1")
        self.session.add(authority)
        self.session.flush()
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
        asset = catalog.create_asset(
            "assets",
            {
                "organization_id": str(organization.id),
                "business_unit_id": str(business_unit.id),
                "product_id": str(product.id),
                "asset_code": "PORTAL_WEB",
                "name": "Portal Web",
                "asset_type": "application",
            },
        )
        self.assertIsNotNone(asset.id)
        payload = catalog.asset_payload("assets", asset.id)
        self.assertEqual(payload["asset_code"], "PORTAL_WEB")

    @patch("aws_local_audit.integrations.confluence.requests.request")
    @patch.object(ConfluenceClient, "_secret_value", return_value="token")
    def test_confluence_client_uses_idempotency_cache(self, _secret_mock, request_mock) -> None:
        framework = Framework(code="ISO27001_2022", name="ISO", version="2022")
        self.session.add(framework)
        self.session.flush()
        self.session.add(
            ConfluenceConnection(
                framework_id=framework.id,
                name="default",
                base_url="https://confluence.example",
                space_key="GRC",
                parent_page_id="123",
                auth_mode="bearer",
                secret_name="confluence::default",
                verify_tls=True,
                is_default=True,
                status="active",
            )
        )
        self.session.commit()

        request_mock.return_value = _FakeResponse(
            {"id": "42", "title": "Page", "_links": {"webui": "/pages/viewpage.action?pageId=42"}}
        )
        client = ConfluenceClient(self.session, "default")
        first = client.create_page("Page", "<p>Hello</p>")
        second = client.create_page("Page", "<p>Hello</p>")
        self.assertEqual(first.page_id, "42")
        self.assertEqual(second.page_id, "42")
        self.assertEqual(request_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
