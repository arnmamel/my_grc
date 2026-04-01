from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from aws_local_audit.db import Base
from aws_local_audit.models import AuthorityDocument, Framework, SystemSetting
from aws_local_audit.services.asset_catalog import AssetCatalogService


class AssetCatalogServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    def tearDown(self) -> None:
        self.session.close()

    def test_create_update_delete_framework_with_reference(self) -> None:
        authority = AuthorityDocument(document_key="ISO27001_DOC", name="ISO 27001 Authority", version="2022")
        self.session.add(authority)
        self.session.flush()

        service = AssetCatalogService(self.session)
        framework = service.create_asset(
            "frameworks",
            {
                "authority_document_id": str(authority.id),
                "code": "ISO27001",
                "name": "ISO/IEC 27001",
                "version": "2022",
                "description": "Initial framework shell.",
            },
        )

        self.assertIsNotNone(framework.id)
        self.assertEqual(framework.authority_document_id, authority.id)

        payload = service.asset_payload("frameworks", framework.id)
        self.assertEqual(payload["code"], "ISO27001")
        self.assertEqual(payload["authority_document_id"], authority.id)

        service.update_asset(
            "frameworks",
            framework.id,
            {
                "description": "Updated framework shell.",
                "lifecycle_status": "active",
            },
        )
        updated = self.session.scalar(select(Framework).where(Framework.id == framework.id))
        self.assertEqual(updated.description, "Updated framework shell.")
        self.assertEqual(updated.lifecycle_status, "active")

        listed = service.list_assets("frameworks", limit=50, search="active")
        self.assertEqual(len(listed), 1)

        service.delete_asset("frameworks", framework.id)
        self.assertIsNone(self.session.get(Framework, framework.id))

    def test_create_and_update_system_setting(self) -> None:
        service = AssetCatalogService(self.session)
        record = service.create_asset(
            "system_settings",
            {
                "setting_key": "workspace.unified_default_page",
                "setting_value": "Workspace Home",
                "description": "Default landing page for the unified shell.",
            },
        )

        self.assertIsNotNone(record.id)
        service.update_asset("system_settings", record.id, {"setting_value": "Assistant Center"})
        setting = self.session.scalar(
            select(SystemSetting).where(SystemSetting.setting_key == "workspace.unified_default_page")
        )
        self.assertEqual(setting.setting_value, "Assistant Center")


if __name__ == "__main__":
    unittest.main()
