from __future__ import annotations

import csv
import json
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from aws_local_audit.models import ControlImplementation, CustomerQuestionnaire, CustomerQuestionnaireItem
from aws_local_audit.services.lifecycle import LifecycleService
from aws_local_audit.services.workbench import WorkbenchService


class QuestionnaireService:
    def __init__(self, session):
        self.session = session
        self.workbench = WorkbenchService(session)
        self.lifecycle = LifecycleService(session)

    def import_csv_questionnaire(
        self,
        organization_code: str,
        product_code: str,
        csv_path: str,
        name: str,
        customer_name: str = "",
        product_flavor_code: str | None = None,
    ) -> CustomerQuestionnaire:
        questionnaire = self.workbench.create_questionnaire(
            organization_code=organization_code,
            product_code=product_code,
            name=name,
            customer_name=customer_name,
            product_flavor_code=product_flavor_code,
            source_type="csv",
            source_name=Path(csv_path).name,
        )
        return self._import_rows(
            questionnaire=questionnaire,
            rows=self._question_rows(csv_path),
            scope_refs=[{"organization_code": organization_code, "product_code": product_code}],
        )

    def import_questionnaire_file(
        self,
        primary_organization_code: str,
        primary_product_code: str,
        file_path: str,
        name: str,
        customer_name: str = "",
        scope_refs: list[dict] | None = None,
    ) -> CustomerQuestionnaire:
        resolved_scope_refs = scope_refs or [
            {"organization_code": primary_organization_code, "product_code": primary_product_code}
        ]
        questionnaire = self.workbench.create_questionnaire(
            organization_code=primary_organization_code,
            product_code=primary_product_code,
            name=name,
            customer_name=customer_name,
            source_type=Path(file_path).suffix.lower().lstrip(".") or "file",
            source_name=Path(file_path).name,
        )
        questionnaire.generated_summary = json.dumps(
            {"scope_refs": resolved_scope_refs},
            indent=2,
        )
        return self._import_rows(
            questionnaire=questionnaire,
            rows=self._question_rows(file_path),
            scope_refs=resolved_scope_refs,
        )

    def _answer_question(
        self,
        organization_code: str,
        product_code: str,
        question_text: str,
        product_flavor_code: str | None = None,
    ) -> dict:
        organization = self.workbench._organization_by_code(organization_code)
        product = self.workbench._product_by_code(organization_code, product_code)
        flavor = (
            self.workbench._product_flavor_by_code(organization_code, product_code, product_flavor_code)
            if product_flavor_code
            else None
        )

        implementations = self.session.scalars(
            select(ControlImplementation).where(
                ControlImplementation.organization_id == organization.id,
                or_(
                    (
                        (ControlImplementation.product_id == product.id)
                        & (ControlImplementation.product_flavor_id == (flavor.id if flavor else None))
                    ),
                    (
                        (ControlImplementation.product_id == product.id)
                        & ControlImplementation.product_flavor_id.is_(None)
                    ),
                    ControlImplementation.product_id.is_(None),
                ),
            )
        ).all()

        best = self._best_implementation_match(question_text, implementations)
        if best is None:
            return {
                "normalized_question": question_text.strip().lower(),
                "mapped_unified_control_id": None,
                "mapped_control_implementation_id": None,
                "suggested_answer": "No supported answer could be drafted from the current implementation records.",
                "rationale": "No strong implementation match was found for this question.",
                "confidence": 0.0,
            }

        implementation, score = best
        answer_parts = [segment for segment in [implementation.objective, implementation.impl_general, implementation.impl_aws] if segment]
        suggested_answer = "\n\n".join(answer_parts) if answer_parts else implementation.title
        rationale = f"Matched to implementation '{implementation.title}' with heuristic score {score:.2f}."
        return {
            "normalized_question": question_text.strip().lower(),
            "mapped_unified_control_id": implementation.unified_control_id,
            "mapped_control_implementation_id": implementation.id,
            "suggested_answer": suggested_answer,
            "rationale": rationale,
            "confidence": round(score, 4),
        }

    def preview_questionnaire_answers_from_file(
        self,
        scope_refs: list[dict],
        file_path: str,
    ) -> list[dict]:
        previews = []
        for row in self._question_rows(file_path):
            question_text = self._pick_value(row, ["question", "requirement", "text", "description", "prompt"])
            if not question_text:
                continue
            answer_bundle = self._answer_question_for_scopes(scope_refs, question_text)
            previews.append(
                {
                    "question": question_text,
                    "answer": answer_bundle["suggested_answer"],
                    "confidence": answer_bundle["confidence"],
                    "source": answer_bundle["answer_source"],
                    "matched_scope": answer_bundle["matched_scope"],
                    "reused_from": answer_bundle["reused_from"],
                    "rationale": answer_bundle["rationale"],
                }
            )
        return previews

    def preview_questionnaire_answers(
        self,
        organization_code: str,
        product_code: str,
        csv_path: str,
        product_flavor_code: str | None = None,
    ) -> list[dict]:
        return self.preview_questionnaire_answers_from_file(
            [{"organization_code": organization_code, "product_code": product_code}],
            csv_path,
        )

    def reusable_answers(
        self,
        question_text: str,
        scope_refs: list[dict] | None = None,
        limit: int = 5,
    ) -> list[dict]:
        normalized_question = question_text.strip().lower()
        items = self.session.scalars(
            select(CustomerQuestionnaireItem)
            .options(
                selectinload(CustomerQuestionnaireItem.questionnaire).selectinload(CustomerQuestionnaire.product),
                selectinload(CustomerQuestionnaireItem.questionnaire).selectinload(CustomerQuestionnaire.organization),
                selectinload(CustomerQuestionnaireItem.mapped_control_implementation),
            )
            .where(CustomerQuestionnaireItem.normalized_question == normalized_question)
            .order_by(CustomerQuestionnaireItem.updated_at.desc())
        ).all()
        scope_keys = {
            (item["organization_code"], item["product_code"])
            for item in (scope_refs or [])
            if item.get("organization_code") and item.get("product_code")
        }
        reusable = []
        for item in items:
            questionnaire = item.questionnaire
            scope_match = not scope_keys or (
                questionnaire.organization.code,
                questionnaire.product.code,
            ) in scope_keys
            if not scope_match:
                continue
            reusable.append(
                {
                    "questionnaire_id": questionnaire.id,
                    "questionnaire": questionnaire.name,
                    "customer": questionnaire.customer_name,
                    "organization_code": questionnaire.organization.code,
                    "product_code": questionnaire.product.code,
                    "answer": item.suggested_answer,
                    "review_status": item.review_status,
                    "confidence": item.confidence,
                    "mapped_control_implementation_id": item.mapped_control_implementation_id,
                }
            )
            if len(reusable) >= limit:
                break
        return reusable

    def review_questionnaire_item(
        self,
        item_id: int,
        review_status: str,
        reviewer: str = "",
        approved_answer: str = "",
        rationale_note: str = "",
    ) -> CustomerQuestionnaireItem:
        item = self.session.get(CustomerQuestionnaireItem, item_id)
        if item is None:
            raise ValueError(f"Questionnaire item not found: {item_id}")
        previous_state = item.review_status
        self.lifecycle.ensure_transition(
            entity_type="customer_questionnaire_item",
            lifecycle_name="assurance_lifecycle",
            from_state=previous_state,
            to_state=review_status,
        )
        item.review_status = review_status
        if approved_answer.strip():
            item.suggested_answer = approved_answer.strip()
        if rationale_note.strip():
            item.rationale = f"{item.rationale}\n\nReview note: {rationale_note.strip()}".strip()
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="customer_questionnaire_item",
            entity_id=item.id,
            lifecycle_name="assurance_lifecycle",
            from_state=previous_state,
            to_state=item.review_status,
            actor=reviewer or "questionnaire_service",
            payload={
                "questionnaire": item.questionnaire.name,
                "question": item.question_text[:120],
                "confidence": item.confidence,
            },
        )
        return item

    def _import_rows(
        self,
        *,
        questionnaire: CustomerQuestionnaire,
        rows: list[dict],
        scope_refs: list[dict],
    ) -> CustomerQuestionnaire:
        for row in rows:
            external_id = self._pick_value(row, ["id", "question_id", "control_id", "req_id", "reference"])
            section = self._pick_value(row, ["section", "domain", "category"])
            question_text = self._pick_value(row, ["question", "requirement", "text", "description", "prompt"])
            if not question_text:
                continue
            answer_bundle = self._answer_question_for_scopes(scope_refs, question_text)
            item = CustomerQuestionnaireItem(
                questionnaire_id=questionnaire.id,
                external_id=external_id,
                section=section,
                question_text=question_text,
                normalized_question=answer_bundle["normalized_question"],
                mapped_unified_control_id=answer_bundle["mapped_unified_control_id"],
                mapped_control_implementation_id=answer_bundle["mapped_control_implementation_id"],
                suggested_answer=answer_bundle["suggested_answer"],
                rationale=answer_bundle["rationale"],
                confidence=answer_bundle["confidence"],
            )
            self.session.add(item)
        return questionnaire

    def _answer_question_for_scopes(self, scope_refs: list[dict], question_text: str) -> dict:
        normalized_question = question_text.strip().lower()
        candidates: list[tuple[ControlImplementation, str]] = []
        for scope in scope_refs:
            organization_code = scope.get("organization_code", "")
            product_code = scope.get("product_code", "")
            if not organization_code or not product_code:
                continue
            candidates.extend(self._candidate_implementations_for_scope(organization_code, product_code))

        reusable = self.reusable_answers(question_text, scope_refs=scope_refs, limit=3)
        best = self._best_implementation_match(question_text, [item for item, _ in candidates])
        matched_scope = ""
        if best is None and reusable:
            top = reusable[0]
            return {
                "normalized_question": normalized_question,
                "mapped_unified_control_id": None,
                "mapped_control_implementation_id": top["mapped_control_implementation_id"],
                "suggested_answer": top["answer"],
                "rationale": (
                    f"Reused from questionnaire '{top['questionnaire']}' for "
                    f"{top['organization_code']}/{top['product_code']}."
                ),
                "confidence": round(top["confidence"], 4),
                "answer_source": "reused answer memory",
                "matched_scope": f"{top['organization_code']} / {top['product_code']}",
                "reused_from": top["questionnaire"],
            }

        if best is None:
            return {
                "normalized_question": normalized_question,
                "mapped_unified_control_id": None,
                "mapped_control_implementation_id": None,
                "suggested_answer": "No supported answer could be drafted from the current implementation records.",
                "rationale": "No strong implementation match or reusable answer was found for this question.",
                "confidence": 0.0,
                "answer_source": "no match",
                "matched_scope": "",
                "reused_from": "",
            }

        implementation, score = best
        for candidate, scope_label in candidates:
            if candidate.id == implementation.id:
                matched_scope = scope_label
                break
        answer_parts = [
            segment
            for segment in [implementation.objective, implementation.impl_general, implementation.impl_aws]
            if segment
        ]
        suggested_answer = "\n\n".join(answer_parts) if answer_parts else implementation.title
        rationale = f"Matched to implementation '{implementation.title}' with heuristic score {score:.2f}."
        reused_from = ""
        answer_source = "implementation narrative"
        if reusable and reusable[0]["confidence"] >= max(score - 0.05, 0.0):
            top = reusable[0]
            suggested_answer = top["answer"]
            rationale = (
                f"Reused from questionnaire '{top['questionnaire']}' for {top['organization_code']}/{top['product_code']}; "
                f"the same question already had a stored answer."
            )
            answer_source = "reused answer memory"
            reused_from = top["questionnaire"]
            matched_scope = f"{top['organization_code']} / {top['product_code']}"

        return {
            "normalized_question": normalized_question,
            "mapped_unified_control_id": implementation.unified_control_id,
            "mapped_control_implementation_id": implementation.id,
            "suggested_answer": suggested_answer,
            "rationale": rationale,
            "confidence": round(max(score, reusable[0]["confidence"] if reusable else 0.0), 4),
            "answer_source": answer_source,
            "matched_scope": matched_scope,
            "reused_from": reused_from,
        }

    def _candidate_implementations_for_scope(
        self,
        organization_code: str,
        product_code: str,
    ) -> list[tuple[ControlImplementation, str]]:
        organization = self.workbench._organization_by_code(organization_code)
        product = self.workbench._product_by_code(organization_code, product_code)
        implementations = self.session.scalars(
            select(ControlImplementation).where(
                ControlImplementation.organization_id == organization.id,
                or_(
                    ControlImplementation.product_id == product.id,
                    ControlImplementation.product_id.is_(None),
                ),
            )
        ).all()
        scope_label = f"{organization.code} / {product.code}"
        return [(item, scope_label) for item in implementations]

    @staticmethod
    def _question_rows(file_path: str) -> list[dict]:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".csv":
            with Path(file_path).open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                return list(reader)
        if suffix in {".xlsx", ".xls"}:
            dataframe = pd.read_excel(file_path, dtype=str).fillna("")
            return dataframe.to_dict(orient="records")
        raise ValueError(f"Unsupported questionnaire file type: {suffix}")

    @staticmethod
    def _best_implementation_match(question_text: str, implementations: list[ControlImplementation]):
        best_item = None
        best_score = 0.0
        normalized_question = question_text.strip().lower()
        for implementation in implementations:
            reference = " ".join(
                filter(
                    None,
                    [
                        implementation.title,
                        implementation.objective,
                        implementation.impl_general,
                        implementation.impl_aws,
                        implementation.impl_onprem,
                        implementation.test_plan,
                    ],
                )
            )
            score = SequenceMatcher(None, normalized_question, reference.strip().lower()).ratio()
            if score > best_score:
                best_score = score
                best_item = implementation
        if best_item is None or best_score < 0.20:
            return None
        return best_item, best_score

    @staticmethod
    def _pick_value(row: dict, names: list[str]) -> str:
        lowered = {str(key).lower(): value for key, value in row.items()}
        for name in names:
            if name in lowered and lowered[name] is not None:
                return str(lowered[name]).strip()
        return ""
