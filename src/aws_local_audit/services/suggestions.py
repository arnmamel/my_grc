from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import select

from aws_local_audit.models import AISuggestion, Control, ControlMetadata, Framework, UnifiedControl
from aws_local_audit.services.lifecycle import LifecycleService
from aws_local_audit.services.workbench import WorkbenchService


def _normalize_text(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _token_score(left: str, right: str) -> float:
    left_tokens = set(_normalize_text(left).split())
    right_tokens = set(_normalize_text(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _normalize_text(left), _normalize_text(right)).ratio()


@dataclass(slots=True)
class MappingSuggestion:
    external_id: str
    title: str
    description: str
    unified_control_code: str
    unified_control_name: str
    score: float
    rationale: str


class SuggestionService:
    def __init__(self, session):
        self.session = session
        self.lifecycle = LifecycleService(session)
        self.workbench = WorkbenchService(session)

    def suggest_unified_control_matches(self, records: list[dict], limit: int = 3) -> list[dict]:
        unified_controls = self.session.scalars(select(UnifiedControl).order_by(UnifiedControl.code)).all()
        suggestions: list[dict] = []
        for record in records:
            candidates = []
            source_title = record.get("title", "")
            source_description = record.get("description", "")
            source_text = f"{source_title} {source_description}".strip()
            for control in unified_controls:
                reference = " ".join(
                    [control.code, control.name, control.description, control.domain, control.family]
                ).strip()
                similarity_score = _similarity(source_text, reference)
                token_score = _token_score(source_text, reference)
                combined = round((similarity_score * 0.7) + (token_score * 0.3), 4)
                candidates.append(
                    {
                        "unified_control_code": control.code,
                        "unified_control_name": control.name,
                        "score": combined,
                        "rationale": (
                            f"title/description similarity={similarity_score:.2f}, keyword overlap={token_score:.2f}"
                        ),
                    }
                )
            ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)[:limit]
            suggestions.append(
                {
                    "external_id": record.get("external_id", ""),
                    "title": source_title,
                    "description": source_description,
                    "matches": ranked,
                }
            )
        return suggestions

    def suggest_unified_control_matches_from_csv(self, csv_path: str, limit: int = 3) -> list[dict]:
        path = Path(csv_path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)

        if not rows:
            return []

        normalized = self._normalize_csv_rows(rows)
        return self.suggest_unified_control_matches(normalized, limit=limit)

    def capture_mapping_suggestions_from_csv(
        self,
        framework_code: str,
        csv_path: str,
        limit: int = 3,
        provider: str = "heuristic",
        model_name: str = "sequence_matcher",
    ) -> list[AISuggestion]:
        path = Path(csv_path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        normalized = self._normalize_csv_rows(rows)
        return self.capture_mapping_suggestions_from_records(
            framework_code=framework_code,
            records=normalized,
            limit=limit,
            provider=provider,
            model_name=model_name,
        )

    def capture_mapping_suggestions_from_records(
        self,
        framework_code: str,
        records: list[dict],
        limit: int = 3,
        provider: str = "heuristic",
        model_name: str = "sequence_matcher",
    ) -> list[AISuggestion]:
        framework = self.session.scalar(select(Framework).where(Framework.code == framework_code))
        if framework is None:
            raise ValueError(f"Framework not found: {framework_code}")
        normalized = self._normalize_csv_rows(records)
        suggestions = self.suggest_unified_control_matches(normalized, limit=limit)
        controls = self.session.scalars(select(Control).where(Control.framework_id == framework.id)).all()
        controls_by_id = {item.control_id.upper(): item for item in controls}
        stored: list[AISuggestion] = []
        for record, suggestion in zip(normalized, suggestions):
            prompt_text = json.dumps(record, indent=2)
            external_id = (record.get("external_id") or "").upper()
            linked_control = controls_by_id.get(external_id)
            if linked_control is None and record.get("title"):
                linked_control = next(
                    (item for item in controls if item.title.strip().lower() == record["title"].strip().lower()),
                    None,
                )
            existing = self.session.scalar(
                select(AISuggestion).where(
                    AISuggestion.framework_id == framework.id,
                    AISuggestion.control_id == (linked_control.id if linked_control else None),
                    AISuggestion.suggestion_type == "mapping_csv_match",
                    AISuggestion.prompt_text == prompt_text,
                    AISuggestion.accepted.is_(False),
                )
            )
            suggestion_row = existing or AISuggestion(
                framework_id=framework.id,
                control_id=linked_control.id if linked_control else None,
                suggestion_type="mapping_csv_match",
            )
            if existing is None:
                self.session.add(suggestion_row)
            suggestion_row.provider = provider
            suggestion_row.model_name = model_name
            suggestion_row.prompt_text = prompt_text
            suggestion_row.response_text = json.dumps(suggestion["matches"], indent=2)
            suggestion_row.accepted = False
            self.session.flush()
            self.lifecycle.record_event(
                entity_type="ai_suggestion",
                entity_id=suggestion_row.id,
                lifecycle_name="assurance_lifecycle",
                to_state="captured",
                actor="suggestion_service",
                payload={
                    "framework_code": framework.code,
                    "control_id": linked_control.control_id if linked_control else record.get("external_id", ""),
                    "suggestion_type": suggestion_row.suggestion_type,
                    "provider": suggestion_row.provider,
                },
            )
            stored.append(suggestion_row)
        return stored

    def list_pending_mapping_suggestions(self, framework_code: str | None = None) -> list[AISuggestion]:
        query = select(AISuggestion).where(
            AISuggestion.suggestion_type == "mapping_csv_match",
            AISuggestion.accepted.is_(False),
        )
        if framework_code:
            framework = self.session.scalar(select(Framework).where(Framework.code == framework_code))
            if framework is None:
                raise ValueError(f"Framework not found: {framework_code}")
            query = query.where(AISuggestion.framework_id == framework.id)
        return list(self.session.scalars(query.order_by(AISuggestion.created_at.desc())))

    def top_match_for_suggestion(self, suggestion: AISuggestion) -> dict:
        payload = self._suggestion_matches(suggestion)
        return payload[0] if payload else {}

    def promote_mapping_suggestion(
        self,
        suggestion_id: int,
        reviewer: str = "suggestion_service",
        notes: str = "",
    ) -> AISuggestion:
        suggestion = self.session.get(AISuggestion, suggestion_id)
        if suggestion is None:
            raise ValueError(f"Suggestion not found: {suggestion_id}")
        if suggestion.framework is None or suggestion.control is None:
            raise ValueError("The selected suggestion is not linked to a framework control.")
        top_match = self.top_match_for_suggestion(suggestion)
        if not top_match.get("unified_control_code"):
            raise ValueError("The selected suggestion does not contain a promotable unified control match.")
        self.workbench.map_framework_control(
            unified_control_code=top_match["unified_control_code"],
            framework_code=suggestion.framework.code,
            control_id=suggestion.control.control_id,
            rationale=(notes or top_match.get("rationale") or "Promoted from mapping suggestion review."),
            confidence=float(top_match.get("score", 0.0)),
            approval_status="approved",
            reviewed_by=reviewer,
            approval_notes=f"Promoted from AI suggestion {suggestion.id}.",
        )
        self._resolve_suggestion(suggestion, decision="promoted", reviewer=reviewer, notes=notes)
        return suggestion

    def dismiss_suggestion(
        self,
        suggestion_id: int,
        reviewer: str = "suggestion_service",
        notes: str = "",
    ) -> AISuggestion:
        suggestion = self.session.get(AISuggestion, suggestion_id)
        if suggestion is None:
            raise ValueError(f"Suggestion not found: {suggestion_id}")
        self._resolve_suggestion(suggestion, decision="dismissed", reviewer=reviewer, notes=notes)
        return suggestion

    def suggest_framework_controls_for_question(self, question_text: str, limit: int = 3) -> list[dict]:
        query = select(Control).join(ControlMetadata, isouter=True).order_by(Control.control_id)
        controls = self.session.scalars(query).all()
        candidates = []
        for control in controls:
            metadata = control.metadata_entry
            reference = " ".join(
                filter(
                    None,
                    [
                        control.control_id,
                        control.title,
                        control.description,
                        metadata.summary if metadata else "",
                        metadata.aws_guidance if metadata else "",
                    ],
                )
            )
            similarity_score = _similarity(question_text, reference)
            token_score = _token_score(question_text, reference)
            combined = round((similarity_score * 0.65) + (token_score * 0.35), 4)
            candidates.append(
                {
                    "framework_code": control.framework.code,
                    "control_id": control.control_id,
                    "title": control.title,
                    "score": combined,
                    "rationale": (
                        f"question similarity={similarity_score:.2f}, keyword overlap={token_score:.2f}"
                    ),
                }
            )
        return sorted(candidates, key=lambda item: item["score"], reverse=True)[:limit]

    @staticmethod
    def _normalize_csv_rows(rows: list[dict]) -> list[dict]:
        normalized = []
        for row in rows:
            external_id = SuggestionService._pick_value(
                row,
                ["external_id", "id", "control_id", "req_id", "code", "reference"],
            )
            title = SuggestionService._pick_value(row, ["title", "name", "control", "control_name", "question"])
            description = SuggestionService._pick_value(row, ["description", "summary", "requirement", "text"])
            normalized.append(
                {
                    "external_id": external_id,
                    "title": title,
                    "description": description,
                }
            )
        return normalized

    @staticmethod
    def _suggestion_matches(suggestion: AISuggestion) -> list[dict]:
        if not suggestion.response_text:
            return []
        try:
            payload = json.loads(suggestion.response_text)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict):
            matches = payload.get("matches", [])
            return matches if isinstance(matches, list) else []
        return payload if isinstance(payload, list) else []

    def _resolve_suggestion(self, suggestion: AISuggestion, decision: str, reviewer: str, notes: str) -> None:
        matches = self._suggestion_matches(suggestion)
        suggestion.accepted = True
        suggestion.response_text = json.dumps(
            {
                "decision": decision,
                "reviewed_by": reviewer,
                "review_notes": notes,
                "reviewed_at": datetime.utcnow().isoformat(),
                "matches": matches,
            },
            indent=2,
        )
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="ai_suggestion",
            entity_id=suggestion.id,
            lifecycle_name="assurance_lifecycle",
            from_state="captured",
            to_state=decision,
            actor=reviewer,
            rationale=notes,
            payload={
                "suggestion_type": suggestion.suggestion_type,
                "framework_code": suggestion.framework.code if suggestion.framework else "",
                "control_id": suggestion.control.control_id if suggestion.control else "",
            },
        )

    @staticmethod
    def _pick_value(row: dict, names: list[str]) -> str:
        lowered = {str(key).lower(): value for key, value in row.items()}
        for name in names:
            if name in lowered and lowered[name] is not None:
                return str(lowered[name]).strip()
        return ""
