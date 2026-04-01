from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from aws_local_audit.logging_utils import audit_event, metric_event, trace_span
from aws_local_audit.models import IdentityPrincipal, WorkspaceCredential
from aws_local_audit.services.access_control import AccessControlService
from aws_local_audit.services.validation import ValidationError, validate_principal_key, validate_workspace_password


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkspaceAuthenticationError(RuntimeError):
    pass


class WorkspaceAuthService:
    def __init__(self, session):
        self.session = session

    def bootstrap_required(self) -> bool:
        return (self.session.scalar(select(func.count()).select_from(WorkspaceCredential)) or 0) == 0

    def credential_count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(WorkspaceCredential)) or 0)

    def active_principals(self) -> list[IdentityPrincipal]:
        return list(
            self.session.scalars(
                select(IdentityPrincipal)
                .join(WorkspaceCredential, WorkspaceCredential.principal_id == IdentityPrincipal.id)
                .where(IdentityPrincipal.status == "active", WorkspaceCredential.status == "active")
                .order_by(IdentityPrincipal.display_name, IdentityPrincipal.principal_key)
            )
        )

    def bootstrap_local_admin(
        self,
        *,
        principal_key: str,
        display_name: str,
        password: str,
        email: str = "",
    ) -> IdentityPrincipal:
        if not self.bootstrap_required():
            raise WorkspaceAuthenticationError("Workspace authentication is already initialized.")
        normalized_key = validate_principal_key(principal_key)
        validate_workspace_password(password)
        access = AccessControlService(self.session)
        access.seed_default_roles()
        principal = access.upsert_principal(
            principal_key=normalized_key,
            display_name=display_name.strip() or normalized_key,
            email=email.strip(),
            source_system="workspace_local",
            status="active",
        )
        self.set_password(principal.principal_key, password=password)
        audit_event(
            action="workspace_auth_bootstrapped",
            actor=principal.principal_key,
            target_type="identity_principal",
            target_id=str(principal.id),
            status="success",
        )
        return principal

    def set_password(self, principal_key: str, *, password: str, actor: str = "workspace_auth") -> WorkspaceCredential:
        validate_workspace_password(password)
        principal = self.session.scalar(select(IdentityPrincipal).where(IdentityPrincipal.principal_key == validate_principal_key(principal_key)))
        if principal is None:
            raise WorkspaceAuthenticationError(f"Unknown principal `{principal_key}`.")
        credential = self.session.scalar(select(WorkspaceCredential).where(WorkspaceCredential.principal_id == principal.id))
        if credential is None:
            credential = WorkspaceCredential(principal_id=principal.id)
            self.session.add(credential)
        if not credential.password_iterations:
            credential.password_iterations = 390000
        salt = secrets.token_hex(16)
        credential.password_salt = salt
        credential.password_hash = self._hash_password(password, salt, credential.password_iterations)
        credential.password_changed_at = _utc_now_naive()
        credential.failed_attempts = 0
        credential.locked_until = None
        credential.status = "active"
        self.session.flush()
        audit_event(
            action="workspace_password_updated",
            actor=actor,
            target_type="identity_principal",
            target_id=str(principal.id),
            status="success",
        )
        return credential

    def authenticate(self, principal_key: str, password: str) -> IdentityPrincipal:
        normalized_key = validate_principal_key(principal_key)
        with trace_span("workspace_authenticate", details={"principal_key": normalized_key}):
            principal = self.session.scalar(select(IdentityPrincipal).where(IdentityPrincipal.principal_key == normalized_key))
            if principal is None or principal.status != "active":
                metric_event(name="workspace_auth_failure_total", tags={"reason": "unknown_principal"})
                raise WorkspaceAuthenticationError("Unknown or inactive workspace user.")
            credential = self.session.scalar(select(WorkspaceCredential).where(WorkspaceCredential.principal_id == principal.id))
            if credential is None or credential.status != "active":
                metric_event(name="workspace_auth_failure_total", tags={"reason": "missing_credential"})
                raise WorkspaceAuthenticationError("Workspace access is not configured for this user.")
            now = _utc_now_naive()
            if credential.locked_until and credential.locked_until > now:
                metric_event(name="workspace_auth_failure_total", tags={"reason": "locked"})
                raise WorkspaceAuthenticationError("Workspace access is temporarily locked for this user.")
            computed = self._hash_password(password, credential.password_salt, credential.password_iterations)
            if not hmac.compare_digest(computed, credential.password_hash):
                credential.failed_attempts += 1
                if credential.failed_attempts >= 5:
                    credential.locked_until = now + timedelta(minutes=15)
                self.session.flush()
                metric_event(name="workspace_auth_failure_total", tags={"reason": "bad_password"})
                raise WorkspaceAuthenticationError("Workspace authentication failed.")
            credential.failed_attempts = 0
            credential.locked_until = None
            credential.last_authenticated_at = now
            self.session.flush()
            metric_event(name="workspace_auth_success_total", tags={"principal_key": normalized_key})
            audit_event(
                action="workspace_login",
                actor=principal.principal_key,
                target_type="identity_principal",
                target_id=str(principal.id),
                status="success",
            )
            return principal

    def health_summary(self) -> dict:
        credentials = self.credential_count()
        active_principals = len(self.active_principals())
        locked = int(
            self.session.scalar(
                select(func.count())
                .select_from(WorkspaceCredential)
                .where(WorkspaceCredential.locked_until.is_not(None))
            )
            or 0
        )
        status = "pass" if credentials and active_principals else "warn"
        detail = f"{credentials} credential(s), {active_principals} active principal(s), {locked} locked credential(s)."
        return {"status": status, "detail": detail}

    @staticmethod
    def _hash_password(password: str, salt: str, iterations: int) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            iterations,
        ).hex()
