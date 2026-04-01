from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, inspect, select, text

from aws_local_audit.logging_utils import audit_event, metric_event, trace_span
from aws_local_audit.models import (
    AccessRole,
    CircuitBreakerState,
    ExternalCallLedger,
    FeatureFlag,
    IdentityPrincipal,
    LifecycleEvent,
    RoleAssignment,
)
from aws_local_audit.services.access_control import AccessControlService
from aws_local_audit.services.backup_restore import BackupRestoreService
from aws_local_audit.services.observability import ObservabilityService
from aws_local_audit.services.workspace_auth import WorkspaceAuthService


@dataclass(frozen=True, slots=True)
class BoundedContext:
    key: str
    name: str
    purpose: str
    owned_entities: tuple[str, ...]
    anti_corruption_inputs: tuple[str, ...]


BOUNDED_CONTEXTS: tuple[BoundedContext, ...] = (
    BoundedContext(
        key="governance",
        name="Governance and Control Library",
        purpose="Own frameworks, controls, unified mappings, guidance references, and policy lifecycle.",
        owned_entities=("Framework", "Control", "UnifiedControl", "UnifiedControlMapping", "ReferenceDocument"),
        anti_corruption_inputs=("External framework imports", "Guide catalogs", "AI mapping suggestions"),
    ),
    BoundedContext(
        key="portfolio",
        name="Portfolio and Risk",
        purpose="Own organizations, business units, products, assets, risks, findings, and actions.",
        owned_entities=("Organization", "BusinessUnit", "Product", "Asset", "Risk", "Finding", "ActionItem"),
        anti_corruption_inputs=("CMDB feeds", "Cloud inventories", "Scanner findings"),
    ),
    BoundedContext(
        key="assurance",
        name="Evidence and Assurance",
        purpose="Own evidence plans, evidence items, assessments, schedules, and assurance decisions.",
        owned_entities=("EvidenceCollectionPlan", "EvidenceItem", "AssessmentRun", "AssessmentSchedule"),
        anti_corruption_inputs=("AWS collectors", "Manual uploads", "Questionnaires", "Confluence publishing"),
    ),
    BoundedContext(
        key="identity",
        name="Identity and Access Governance",
        purpose="Own principals, roles, approvals, and separation-of-duties policies for platform workflows.",
        owned_entities=("IdentityPrincipal", "AccessRole", "RoleAssignment"),
        anti_corruption_inputs=("Local operator directory", "Future SAML or OIDC identities", "SCIM provisioning"),
    ),
    BoundedContext(
        key="integrations",
        name="Integrations and Connectors",
        purpose="Own AWS profiles, Confluence connections, external script modules, and connector runtime state.",
        owned_entities=("AwsCliProfile", "ConfluenceConnection", "AssessmentScriptModule", "CircuitBreakerState"),
        anti_corruption_inputs=("AWS CLI", "Boto3", "HTTP APIs", "Local scripts"),
    ),
    BoundedContext(
        key="platform",
        name="Platform Operations",
        purpose="Own observability, feature flags, idempotency, health, lifecycle integrity, and deployment readiness.",
        owned_entities=("FeatureFlag", "ExternalCallLedger", "LifecycleEvent"),
        anti_corruption_inputs=("Runtime logs", "Metrics", "Trace events", "CI/CD"),
    ),
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FeatureFlagService:
    def __init__(self, session):
        self.session = session

    def ensure_flag(
        self,
        *,
        flag_key: str,
        name: str,
        description: str = "",
        enabled: bool = False,
        rollout_strategy: str = "static",
        owner: str = "",
    ) -> FeatureFlag:
        flag = self.session.scalar(select(FeatureFlag).where(FeatureFlag.flag_key == flag_key))
        if flag is None:
            flag = FeatureFlag(flag_key=flag_key, name=name)
            self.session.add(flag)
        flag.name = name
        flag.description = description
        flag.enabled = enabled if flag.id is None else flag.enabled
        flag.rollout_strategy = rollout_strategy
        flag.owner = owner
        self.session.flush()
        return flag

    def set_flag(
        self,
        flag_key: str,
        enabled: bool,
        *,
        actor: str = "feature_flag_service",
        description: str = "",
        name: str | None = None,
        rollout_strategy: str = "static",
        owner: str = "",
    ) -> FeatureFlag:
        flag = self.session.scalar(select(FeatureFlag).where(FeatureFlag.flag_key == flag_key))
        if flag is None:
            flag = FeatureFlag(flag_key=flag_key, name=name or flag_key)
            self.session.add(flag)
        if name:
            flag.name = name
        if description:
            flag.description = description
        flag.enabled = enabled
        flag.rollout_strategy = rollout_strategy or flag.rollout_strategy
        flag.owner = owner or flag.owner
        self.session.flush()
        audit_event(
            action="feature_flag_updated",
            actor=actor,
            target_type="feature_flag",
            target_id=flag.flag_key,
            status="success",
            details={"enabled": flag.enabled, "rollout_strategy": flag.rollout_strategy},
        )
        return flag

    def enabled(self, flag_key: str, default: bool = False) -> bool:
        flag = self.session.scalar(select(FeatureFlag).where(FeatureFlag.flag_key == flag_key))
        if flag is None:
            return default
        return flag.enabled

    def list_flags(self) -> list[FeatureFlag]:
        return list(self.session.scalars(select(FeatureFlag).order_by(FeatureFlag.flag_key)))

    def seed_defaults(self) -> int:
        defaults = [
            {
                "flag_key": "workspace.auth_required",
                "name": "Workspace Authentication Required",
                "description": "Require authenticated workspace access before practitioners can use the app shell.",
                "enabled": True,
                "owner": "platform",
            },
            {
                "flag_key": "workspace.health_panel",
                "name": "Workspace Health Panel",
                "description": "Surface platform health checks prominently in the unified workspace.",
                "enabled": True,
                "owner": "platform",
            },
            {
                "flag_key": "integrations.confluence_resilience",
                "name": "Confluence Resilience Guard",
                "description": "Protect Confluence calls with circuit breaker and idempotency controls.",
                "enabled": True,
                "owner": "platform",
            },
            {
                "flag_key": "governance.risk_domain",
                "name": "Risk Domain Backbone",
                "description": "Expose the new business-unit, asset, risk, finding, and action-item model in the workspace.",
                "enabled": True,
                "owner": "grc",
            },
        ]
        created = 0
        for item in defaults:
            existing = self.session.scalar(select(FeatureFlag).where(FeatureFlag.flag_key == item["flag_key"]))
            if existing is None:
                self.ensure_flag(**item)
                created += 1
        return created


class ResilienceError(RuntimeError):
    pass


class ResilienceService:
    def __init__(self, session):
        self.session = session

    def assert_call_allowed(self, integration_key: str) -> CircuitBreakerState:
        state = self._state(integration_key)
        if state.state == "open" and state.opened_at:
            if _utc_now_naive() < state.opened_at + timedelta(seconds=state.reopen_after_seconds):
                raise ResilienceError(
                    f"Circuit breaker is open for `{integration_key}`. Last error: {state.last_error or 'unknown'}"
                )
            state.state = "half_open"
            self.session.flush()
        return state

    def idempotent_response(
        self,
        *,
        integration_key: str,
        operation: str,
        idempotency_key: str,
    ) -> dict | None:
        if not idempotency_key:
            return None
        row = self.session.scalar(
            select(ExternalCallLedger).where(
                ExternalCallLedger.integration_key == integration_key,
                ExternalCallLedger.operation == operation,
                ExternalCallLedger.idempotency_key == idempotency_key,
                ExternalCallLedger.status == "success",
            )
        )
        if row is None or not row.response_payload_json:
            return None
        return json.loads(row.response_payload_json)

    def record_success(
        self,
        *,
        integration_key: str,
        operation: str,
        idempotency_key: str,
        request_payload: dict | None,
        response_payload: dict,
    ) -> None:
        with trace_span(
            "external_call_success",
            details={"integration_key": integration_key, "operation": operation},
        ):
            state = self._state(integration_key)
            state.state = "closed"
            state.failure_count = 0
            state.success_count += 1
            state.last_error = ""
            row = self._ledger_row(integration_key, operation, idempotency_key)
            row.request_hash = self._hash_payload(request_payload or {})
            row.status = "success"
            row.response_payload_json = json.dumps(response_payload, default=str)
            row.error_message = ""
            self.session.flush()
            metric_event(name="external_call_success_total", tags={"integration": integration_key, "operation": operation})

    def record_failure(
        self,
        *,
        integration_key: str,
        operation: str,
        idempotency_key: str,
        request_payload: dict | None,
        error_message: str,
    ) -> None:
        with trace_span(
            "external_call_failure",
            details={"integration_key": integration_key, "operation": operation, "error": error_message},
        ):
            state = self._state(integration_key)
            state.failure_count += 1
            state.last_error = error_message
            if state.failure_count >= state.threshold:
                state.state = "open"
                state.opened_at = _utc_now_naive()
            row = self._ledger_row(integration_key, operation, idempotency_key)
            row.request_hash = self._hash_payload(request_payload or {})
            row.status = "error"
            row.error_message = error_message
            self.session.flush()
            metric_event(name="external_call_failure_total", tags={"integration": integration_key, "operation": operation})

    def open_circuits(self) -> list[CircuitBreakerState]:
        return list(self.session.scalars(select(CircuitBreakerState).where(CircuitBreakerState.state == "open")))

    def _state(self, integration_key: str) -> CircuitBreakerState:
        state = self.session.scalar(select(CircuitBreakerState).where(CircuitBreakerState.integration_key == integration_key))
        if state is None:
            state = CircuitBreakerState(integration_key=integration_key)
            self.session.add(state)
            self.session.flush()
        return state

    def _ledger_row(self, integration_key: str, operation: str, idempotency_key: str) -> ExternalCallLedger:
        row = self.session.scalar(
            select(ExternalCallLedger).where(
                ExternalCallLedger.integration_key == integration_key,
                ExternalCallLedger.operation == operation,
                ExternalCallLedger.idempotency_key == (idempotency_key or ""),
            )
        )
        if row is None:
            row = ExternalCallLedger(
                integration_key=integration_key,
                operation=operation,
                idempotency_key=idempotency_key or "",
            )
            self.session.add(row)
            self.session.flush()
        return row

    @staticmethod
    def _hash_payload(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class AuditTrailService:
    def __init__(self, session):
        self.session = session

    def verify_chain(self) -> dict:
        events = self.session.scalars(select(LifecycleEvent).order_by(LifecycleEvent.id)).all()
        previous_hash = ""
        failures = []
        for item in events:
            expected = self._compute_hash(item, previous_hash)
            if item.previous_hash != previous_hash or item.event_hash != expected:
                failures.append(
                    {
                        "event_id": item.id,
                        "expected_previous_hash": previous_hash,
                        "stored_previous_hash": item.previous_hash,
                        "expected_event_hash": expected,
                        "stored_event_hash": item.event_hash,
                    }
                )
            previous_hash = item.event_hash
        return {"valid": not failures, "events": len(events), "failures": failures}

    @staticmethod
    def _compute_hash(event: LifecycleEvent, previous_hash: str) -> str:
        payload = {
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "lifecycle_name": event.lifecycle_name,
            "from_state": event.from_state,
            "to_state": event.to_state,
            "actor": event.actor,
            "rationale": event.rationale,
            "payload_json": event.payload_json,
            "created_at": event.created_at.isoformat() if event.created_at else "",
            "previous_hash": previous_hash,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class HealthCheckService:
    def __init__(self, session):
        self.session = session
        self.root = Path(__file__).resolve().parents[3]

    def run(self) -> dict:
        self.session.flush()
        self._connection = self.session.connection()
        checks = [
            self._database_check(),
            self._migration_check(),
            self._logging_check(),
            self._observability_check(),
            self._feature_flags_check(),
            self._rbac_check(),
            self._workspace_auth_check(),
            self._backup_check(),
            self._circuit_breaker_check(),
        ]
        overall = "pass"
        if any(item["status"] == "error" for item in checks):
            overall = "error"
        elif any(item["status"] == "warn" for item in checks):
            overall = "warn"
        return {"status": overall, "checks": checks}

    def _database_check(self) -> dict:
        try:
            self._connection.execute(text("SELECT 1"))
            return {"name": "database", "status": "pass", "detail": "Database connection is healthy."}
        except Exception as exc:
            return {"name": "database", "status": "error", "detail": str(exc)}

    def _migration_check(self) -> dict:
        if not (self.root / "alembic.ini").exists():
            return {"name": "migrations", "status": "error", "detail": "Alembic configuration is missing."}
        if "alembic_version" not in inspect(self._connection).get_table_names():
            return {"name": "migrations", "status": "warn", "detail": "alembic_version table not found yet."}
        return {"name": "migrations", "status": "pass", "detail": "Migration metadata is present."}

    def _logging_check(self) -> dict:
        log_dir = self.root / "logs"
        if not log_dir.exists():
            return {"name": "logging", "status": "warn", "detail": "Log directory has not been created yet."}
        return {"name": "logging", "status": "pass", "detail": f"Log directory ready at {log_dir}."}

    def _observability_check(self) -> dict:
        report = ObservabilityService(root=self.root).runtime_summary()
        return {"name": "observability", "status": report["status"], "detail": report["detail"]}

    def _feature_flags_check(self) -> dict:
        count = self.session.scalar(select(func.count(FeatureFlag.id))) or 0
        if count == 0:
            return {"name": "feature_flags", "status": "warn", "detail": "No feature flags are registered yet."}
        return {"name": "feature_flags", "status": "pass", "detail": f"{count} feature flag(s) registered."}

    def _rbac_check(self) -> dict:
        role_count = self.session.scalar(select(func.count(AccessRole.id))) or 0
        principal_count = self.session.scalar(select(func.count(IdentityPrincipal.id))) or 0
        assignment_count = self.session.scalar(select(func.count(RoleAssignment.id))) or 0
        conflicts = AccessControlService(self.session).segregation_conflicts()
        if role_count == 0:
            return {"name": "rbac", "status": "warn", "detail": "No RBAC roles are registered yet."}
        if conflicts:
            return {"name": "rbac", "status": "warn", "detail": f"{len(conflicts)} segregation-of-duties conflict(s) detected."}
        if principal_count == 0 or assignment_count == 0:
            return {"name": "rbac", "status": "warn", "detail": "RBAC roles exist, but principals or assignments are not configured yet."}
        return {
            "name": "rbac",
            "status": "pass",
            "detail": f"{role_count} role(s), {principal_count} principal(s), {assignment_count} assignment(s).",
        }

    def _workspace_auth_check(self) -> dict:
        report = WorkspaceAuthService(self.session).health_summary()
        return {"name": "workspace_auth", "status": report["status"], "detail": report["detail"]}

    def _backup_check(self) -> dict:
        report = BackupRestoreService(root=self.root).health_summary()
        return {"name": "backups", "status": report["status"], "detail": report["detail"]}

    def _circuit_breaker_check(self) -> dict:
        open_count = self.session.scalar(
            select(func.count()).select_from(CircuitBreakerState).where(CircuitBreakerState.state == "open")
        ) or 0
        if open_count:
            return {"name": "circuit_breakers", "status": "warn", "detail": f"{open_count} circuit breaker(s) are open."}
        return {"name": "circuit_breakers", "status": "pass", "detail": "No open circuit breakers."}


class ArchitectureBoundaryService:
    def describe(self) -> list[dict]:
        return [
            {
                "key": item.key,
                "name": item.name,
                "purpose": item.purpose,
                "owned_entities": list(item.owned_entities),
                "anti_corruption_inputs": list(item.anti_corruption_inputs),
            }
            for item in BOUNDED_CONTEXTS
        ]
