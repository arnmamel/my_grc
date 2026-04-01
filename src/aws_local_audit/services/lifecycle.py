from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select

from aws_local_audit.logging_utils import audit_event
from aws_local_audit.models import LifecycleEvent


class LifecycleTransitionError(ValueError):
    pass


TRANSITION_POLICIES: dict[tuple[str, str], dict[str, set[str]]] = {
    ("framework_binding", "framework_binding_lifecycle"): {
        "active": {"active", "disabled", "retired"},
        "disabled": {"disabled", "active", "retired"},
        "retired": {"retired"},
    },
    ("unified_control_mapping", "control_lifecycle"): {
        "proposed": {"approved", "rejected"},
        "approved": {"approved", "retired"},
        "rejected": {"proposed", "rejected"},
        "retired": {"retired"},
    },
    ("evidence_collection_plan", "evidence_lifecycle"): {
        "draft": {"approved", "retired"},
        "approved": {"active", "ready", "retired"},
        "active": {"ready", "published", "retired"},
        "ready": {"active", "published", "retired"},
        "published": {"active", "retired", "published"},
        "retired": {"archived", "retired"},
        "archived": {"archived"},
    },
    ("evidence_item", "evidence_lifecycle"): {
        "awaiting_collection": {"collected", "pending_review", "approved", "rejected", "awaiting_collection"},
        "collected": {"approved", "rejected", "pending_review", "collected"},
        "pending_review": {"approved", "rejected", "pending_review"},
        "approved": {"approved"},
        "rejected": {"pending_review", "rejected"},
        "collection_error": {"pending_review", "rejected", "collection_error"},
        "collector_missing": {"pending_review", "rejected", "collector_missing"},
        "skipped": {"skipped", "approved"},
    },
    ("aws_evidence_target", "evidence_lifecycle"): {
        "draft": {"draft", "active", "disabled", "retired"},
        "active": {"active", "disabled", "retired"},
        "disabled": {"disabled", "active", "retired"},
        "retired": {"retired"},
    },
    ("customer_questionnaire_item", "assurance_lifecycle"): {
        "suggested": {"approved", "rejected", "needs_revision"},
        "needs_revision": {"suggested", "approved", "rejected"},
        "rejected": {"suggested", "rejected"},
        "approved": {"approved"},
    },
    ("assessment_run", "audit_lifecycle"): {
        "pending_review": {"approved", "rejected"},
        "rejected": {"pending_review", "rejected"},
        "approved": {"approved"},
    },
}


class LifecycleService:
    def __init__(self, session):
        self.session = session

    def ensure_transition(
        self,
        entity_type: str,
        lifecycle_name: str,
        from_state: str = "",
        to_state: str = "",
    ) -> None:
        current = (from_state or "").strip()
        target = (to_state or "").strip()
        if not current or not target or current == target:
            return
        policy = TRANSITION_POLICIES.get((entity_type, lifecycle_name))
        if not policy:
            return
        allowed = policy.get(current, set())
        if target not in allowed:
            raise LifecycleTransitionError(
                f"Transition `{current}` -> `{target}` is not allowed for {entity_type}/{lifecycle_name}."
            )

    def record_event(
        self,
        entity_type: str,
        entity_id: int,
        lifecycle_name: str,
        from_state: str = "",
        to_state: str = "",
        actor: str = "system",
        rationale: str = "",
        payload: dict[str, Any] | None = None,
    ) -> LifecycleEvent:
        previous = self.session.scalar(select(LifecycleEvent).order_by(LifecycleEvent.id.desc()).limit(1))
        previous_hash = previous.event_hash if previous else ""
        event = LifecycleEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            lifecycle_name=lifecycle_name,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            rationale=rationale,
            payload_json=json.dumps(payload or {}, indent=2, default=str),
            previous_hash=previous_hash,
        )
        self.session.add(event)
        self.session.flush()
        event.event_hash = self._event_hash(event, previous_hash)
        self.session.flush()
        audit_event(
            action="lifecycle_transition",
            actor=actor,
            target_type=entity_type,
            target_id=entity_id,
            status="success",
            details={
                "lifecycle_name": lifecycle_name,
                "from_state": from_state,
                "to_state": to_state,
                "rationale": rationale,
                "payload": payload or {},
            },
        )
        return event

    @staticmethod
    def _event_hash(event: LifecycleEvent, previous_hash: str) -> str:
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
