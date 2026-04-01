from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from aws_local_audit.integrations.confluence import ConfluenceClient
from aws_local_audit.config import settings
from aws_local_audit.models import ConfluenceConnection, Framework, SecretMetadata
from aws_local_audit.security import KeyringSecretStore
from aws_local_audit.services.lifecycle import LifecycleService


class SecretService:
    def __init__(self, session):
        self.session = session
        self.secret_store = KeyringSecretStore(settings.secret_namespace, settings.secret_files_dir)
        self.lifecycle = LifecycleService(session)

    def set_secret(
        self,
        name: str,
        value: str,
        secret_type: str,
        description: str = "",
    ) -> SecretMetadata:
        provider = self.secret_store.set_secret(name, value)
        record = self.session.scalar(select(SecretMetadata).where(SecretMetadata.name == name))
        if record is None:
            record = SecretMetadata(name=name, secret_type=secret_type)
            self.session.add(record)
        record.secret_type = secret_type
        record.provider = provider
        record.external_ref = self.secret_store.external_ref(name)
        record.description = description
        record.status = "active"
        record.last_validated_at = datetime.utcnow()
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="secret_metadata",
            entity_id=record.id,
            lifecycle_name="secret_lifecycle",
            to_state=record.status,
            actor="security_service",
            payload={"name": record.name, "secret_type": record.secret_type, "provider": record.provider},
        )
        return record

    def get_secret(self, name: str) -> str:
        return self.secret_store.get_secret(name)

    def list_secrets(self) -> list[SecretMetadata]:
        return list(self.session.scalars(select(SecretMetadata).order_by(SecretMetadata.name)))


class ConfluenceConnectionService:
    def __init__(self, session):
        self.session = session
        self.secrets = SecretService(session)
        self.lifecycle = LifecycleService(session)

    def upsert_connection(
        self,
        name: str,
        base_url: str,
        space_key: str,
        secret_value: str,
        auth_mode: str = "basic",
        username: str = "",
        parent_page_id: str = "",
        framework_code: str | None = None,
        verify_tls: bool = True,
        is_default: bool = False,
    ) -> ConfluenceConnection:
        if auth_mode not in {"basic", "bearer"}:
            raise ValueError("Confluence auth_mode must be 'basic' or 'bearer'")
        if auth_mode == "basic" and not username:
            raise ValueError("A username is required for basic Confluence authentication")

        secret_name = f"confluence::{name}"
        self.secrets.set_secret(
            name=secret_name,
            value=secret_value,
            secret_type="confluence_credential",
            description=f"Credential for Confluence connection {name}",
        )

        framework = None
        if framework_code:
            framework = self.session.scalar(select(Framework).where(Framework.code == framework_code))
            if framework is None:
                raise ValueError(f"Framework not found: {framework_code}")

        connection = self.session.scalar(select(ConfluenceConnection).where(ConfluenceConnection.name == name))
        if connection is None:
            connection = ConfluenceConnection(name=name, base_url=base_url, space_key=space_key, secret_name=secret_name)
            self.session.add(connection)
        connection.framework_id = framework.id if framework else None
        connection.base_url = base_url.rstrip("/")
        connection.space_key = space_key
        connection.parent_page_id = parent_page_id or None
        connection.auth_mode = auth_mode
        connection.username = username
        connection.secret_name = secret_name
        connection.verify_tls = verify_tls
        connection.is_default = is_default
        connection.status = "active"
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="confluence_connection",
            entity_id=connection.id,
            lifecycle_name="connection_lifecycle",
            to_state=connection.status,
            actor="security_service",
            payload={"name": connection.name, "base_url": connection.base_url, "auth_mode": connection.auth_mode},
        )

        if is_default:
            for item in self.session.scalars(
                select(ConfluenceConnection).where(
                    ConfluenceConnection.id != connection.id,
                    ConfluenceConnection.is_default.is_(True),
                )
            ):
                item.is_default = False

        self.session.flush()
        return connection

    def list_connections(self) -> list[ConfluenceConnection]:
        return list(self.session.scalars(select(ConfluenceConnection).order_by(ConfluenceConnection.name)))

    def get_connection(self, name: str | None = None) -> ConfluenceConnection | None:
        if name:
            return self.session.scalar(select(ConfluenceConnection).where(ConfluenceConnection.name == name))
        return self.session.scalar(
            select(ConfluenceConnection).where(
                ConfluenceConnection.is_default.is_(True),
                ConfluenceConnection.status == "active",
            )
        )

    def test_connection(self, name: str | None = None) -> dict:
        connection = self.get_connection(name)
        if connection is None:
            return {"status": "error", "message": "Confluence connection not found."}
        try:
            result = ConfluenceClient(self.session, connection.name).test_connection()
            connection.last_tested_at = datetime.utcnow()
            connection.last_test_status = result["status"]
            connection.last_test_message = result["message"]
            self.session.flush()
            self.lifecycle.record_event(
                entity_type="confluence_connection",
                entity_id=connection.id,
                lifecycle_name="connection_lifecycle",
                to_state=connection.status,
                actor="security_service",
                payload={"name": connection.name, "test_status": connection.last_test_status},
            )
            return result
        except Exception as exc:
            connection.last_tested_at = datetime.utcnow()
            connection.last_test_status = "error"
            connection.last_test_message = str(exc)
            self.session.flush()
            self.lifecycle.record_event(
                entity_type="confluence_connection",
                entity_id=connection.id,
                lifecycle_name="connection_lifecycle",
                to_state="error",
                actor="security_service",
                payload={"name": connection.name, "test_status": connection.last_test_status, "error": str(exc)},
            )
            return {"status": "error", "message": str(exc)}
