from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import requests
from sqlalchemy import select

from aws_local_audit.config import settings
from aws_local_audit.logging_utils import metric_event, trace_span
from aws_local_audit.models import ConfluenceConnection
from aws_local_audit.security import KeyringSecretStore, SecurityError
from aws_local_audit.services.platform_foundation import ResilienceError, ResilienceService


@dataclass(slots=True)
class ConfluencePage:
    page_id: str
    title: str
    url: str


class ConfluenceClient:
    def __init__(self, session=None, connection_name: str | None = None) -> None:
        self.session = session
        self.connection_name = connection_name
        self.secret_store = KeyringSecretStore(settings.secret_namespace, settings.secret_files_dir)
        self.resilience = ResilienceService(session) if session is not None else None
        self.connection = self._load_connection()

        if self.connection is not None:
            self.base_url = self.connection.base_url.rstrip("/")
            self.space_key = self.connection.space_key
            self.parent_page_id = self.connection.parent_page_id or ""
            self.auth_mode = self.connection.auth_mode.lower()
            self.username = self.connection.username
            self.secret_name = self.connection.secret_name
            self.verify_tls = self.connection.verify_tls
        else:
            self.base_url = settings.confluence_base_url.rstrip("/")
            self.space_key = settings.confluence_space_key
            self.parent_page_id = settings.confluence_parent_page_id
            self.auth_mode = settings.confluence_auth_mode.lower()
            self.username = settings.confluence_username
            self.secret_name = ""
            self.verify_tls = True

    def configured(self) -> bool:
        return bool(self.base_url and self.space_key and self._has_auth())

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {self._secret_value()}"
        return headers

    def _auth(self):
        if self.auth_mode == "basic":
            return (self.username, self._secret_value())
        return None

    def create_page(self, title: str, body_html: str, parent_page_id: str | None = None) -> ConfluencePage:
        if not self.configured():
            raise RuntimeError("Confluence integration is not configured.")
        resolved_parent_page_id = parent_page_id or self.parent_page_id
        if not resolved_parent_page_id:
            raise RuntimeError("Confluence parent page is not configured.")
        payload = {
            "type": "page",
            "title": title,
            "ancestors": [{"id": resolved_parent_page_id}],
            "space": {"key": self.space_key},
            "body": {"storage": {"value": body_html, "representation": "storage"}},
        }
        data = self._request_json(
            operation="create_page",
            method="post",
            url=f"{self.base_url}/rest/api/content",
            payload=payload,
            idempotency_key=f"create_page::{self.space_key}::{resolved_parent_page_id}::{title}",
            timeout=30,
        )
        return ConfluencePage(
            page_id=data["id"],
            title=data["title"],
            url=f"{self.base_url}{data['_links']['webui']}",
        )

    def upload_attachment(
        self,
        page_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        comment: str = "",
    ) -> dict:
        if not self.configured():
            raise RuntimeError("Confluence integration is not configured.")
        headers: dict[str, str] = {"X-Atlassian-Token": "no-check"}
        if self.auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {self._secret_value()}"
        idempotency_key = (
            f"upload_attachment::{page_id}::{filename}::"
            f"{hashlib.sha256(content).hexdigest()}"
        )
        data = self._request_json(
            operation="upload_attachment",
            method="post",
            url=f"{self.base_url}/rest/api/content/{page_id}/child/attachment",
            payload={"page_id": page_id, "filename": filename, "comment": comment or "Uploaded by my_grc"},
            idempotency_key=idempotency_key,
            timeout=60,
            headers=headers,
            files={"file": (filename, content, content_type)},
            form_data={"comment": comment or "Uploaded by my_grc"},
        )
        results = data.get("results", [])
        if not results:
            return {"status": "pass", "filename": filename, "attachment_id": "", "url": ""}
        attachment = results[0]
        webui = attachment.get("_links", {}).get("webui", "")
        return {
            "status": "pass",
            "filename": filename,
            "attachment_id": attachment.get("id", ""),
            "url": f"{self.base_url}{webui}" if webui else "",
        }

    def test_connection(self) -> dict:
        if not self.configured():
            return {"status": "error", "message": "Confluence integration is not configured."}
        try:
            data = self._request_json(
                operation="test_connection",
                method="get",
                url=f"{self.base_url}/rest/api/space/{self.space_key}",
                payload={"space_key": self.space_key},
                idempotency_key="",
                timeout=20,
            )
        except ResilienceError as exc:
            return {"status": "error", "message": str(exc)}
        return {
            "status": "pass",
            "message": f"Connected to Confluence space {data.get('key', self.space_key)}.",
            "space_key": data.get("key", self.space_key),
            "space_name": data.get("name", ""),
        }

    def _load_connection(self) -> ConfluenceConnection | None:
        if self.session is None:
            return None
        if self.connection_name:
            return self.session.scalar(
                select(ConfluenceConnection).where(
                    ConfluenceConnection.name == self.connection_name,
                    ConfluenceConnection.status == "active",
                )
            )
        return self.session.scalar(
            select(ConfluenceConnection).where(
                ConfluenceConnection.is_default.is_(True),
                ConfluenceConnection.status == "active",
            )
        )

    def _has_auth(self) -> bool:
        try:
            return bool(self._secret_value())
        except SecurityError:
            return False

    def _secret_value(self) -> str:
        if self.connection is not None and self.secret_name:
            return self.secret_store.get_secret(self.secret_name)

        if settings.allow_insecure_env_secrets:
            if self.auth_mode == "bearer" and settings.confluence_bearer_token:
                return settings.confluence_bearer_token
            if self.auth_mode == "basic" and settings.confluence_api_token:
                return settings.confluence_api_token

        raise SecurityError(
            "No secure Confluence secret is configured. Use the secure connection workflow or explicitly opt into legacy env secrets."
        )

    def _integration_key(self) -> str:
        return f"confluence::{self.connection_name or self.base_url or 'default'}"

    def _request_json(
        self,
        *,
        operation: str,
        method: str,
        url: str,
        payload: dict,
        idempotency_key: str,
        timeout: int,
        headers: dict[str, str] | None = None,
        files: dict | None = None,
        form_data: dict | None = None,
    ) -> dict:
        integration_key = self._integration_key()
        if self.resilience is not None:
            self.resilience.assert_call_allowed(integration_key)
            cached = self.resilience.idempotent_response(
                integration_key=integration_key,
                operation=operation,
                idempotency_key=idempotency_key,
            )
            if cached is not None:
                metric_event(name="external_call_idempotent_hit_total", tags={"integration": integration_key, "operation": operation})
                return cached

        request_headers = headers or self._headers()
        kwargs = {
            "headers": request_headers,
            "auth": self._auth(),
            "timeout": timeout,
            "verify": self.verify_tls,
        }
        if files is not None:
            kwargs["files"] = files
            kwargs["data"] = form_data or {}
        elif method.lower() == "get":
            kwargs["params"] = payload
        else:
            kwargs["data"] = json.dumps(payload)

        with trace_span(
            "confluence_request",
            details={"operation": operation, "integration_key": integration_key, "url": url},
        ):
            try:
                response = requests.request(method.upper(), url, **kwargs)
                response.raise_for_status()
                data = response.json()
                if self.resilience is not None:
                    self.resilience.record_success(
                        integration_key=integration_key,
                        operation=operation,
                        idempotency_key=idempotency_key,
                        request_payload=payload,
                        response_payload=data,
                    )
                return data
            except Exception as exc:
                if self.resilience is not None:
                    self.resilience.record_failure(
                        integration_key=integration_key,
                        operation=operation,
                        idempotency_key=idempotency_key,
                        request_payload=payload,
                        error_message=str(exc),
                    )
                raise
