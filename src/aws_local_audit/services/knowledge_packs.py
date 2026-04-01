from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select

from aws_local_audit.ai_pack_loader import load_templates
from aws_local_audit.models import (
    AIKnowledgePack,
    AIKnowledgePackEvalCase,
    AIKnowledgePackReference,
    AIKnowledgePackTask,
    AIKnowledgePackVersion,
    AISuggestion,
    Control,
    ControlImplementation,
    Framework,
    ImportedRequirement,
    Organization,
    Product,
    ProductControlProfile,
    ProductFlavor,
    UnifiedControl,
    UnifiedControlMapping,
)
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.lifecycle import LifecycleService
from aws_local_audit.services.reference_library import ReferenceLibraryService


def _normalize_code(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in (value or "").strip().upper())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


class AIKnowledgePackService:
    def __init__(self, session):
        self.session = session
        self.lifecycle = LifecycleService(session)
        self.reference_library = ReferenceLibraryService(session)
        self.governance = GovernanceService(session)

    def seed_templates(self, actor: str = "knowledge_pack_seed") -> list[AIKnowledgePack]:
        touched: list[AIKnowledgePack] = []
        for payload in load_templates():
            touched.append(self.upsert_pack_from_template(payload, actor=actor))
        if touched and not self.governance.get_setting("ai.default_pack_code"):
            default_pack = touched[0]
            self.governance.set_setting(
                "ai.default_pack_code",
                default_pack.pack_code,
                "Default governed AI knowledge pack for control mapping and implementation drafting.",
            )
        return touched

    def list_packs(self) -> list[AIKnowledgePack]:
        return list(self.session.scalars(select(AIKnowledgePack).order_by(AIKnowledgePack.pack_code)))

    def list_tasks(self, pack_code: str) -> list[AIKnowledgePackTask]:
        version = self.active_version(pack_code)
        return sorted(version.tasks, key=lambda item: item.task_key)

    def default_pack_code(self) -> str:
        return self.governance.get_setting("ai.default_pack_code", "")

    def active_version(self, pack_code: str | None = None) -> AIKnowledgePackVersion:
        resolved_code = (pack_code or self.default_pack_code()).strip().upper()
        if not resolved_code:
            raise ValueError("No AI knowledge pack code was provided and no default AI knowledge pack is configured.")
        pack = self.session.scalar(select(AIKnowledgePack).where(AIKnowledgePack.pack_code == resolved_code))
        if pack is None:
            raise ValueError(f"AI knowledge pack not found: {resolved_code}")
        versions = sorted(pack.versions, key=lambda item: item.id, reverse=True)
        candidate = next((item for item in versions if item.status == "active"), None)
        if candidate is None:
            candidate = next((item for item in versions if item.status == "approved"), None)
        if candidate is None and versions:
            candidate = versions[0]
        if candidate is None:
            raise ValueError(f"AI knowledge pack has no versions: {resolved_code}")
        return candidate

    def build_task_package(
        self,
        *,
        pack_code: str | None,
        task_key: str,
        framework_code: str,
        control_id: str,
        unified_control_code: str,
        organization_code: str | None = None,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
    ) -> dict[str, Any]:
        version = self.active_version(pack_code)
        pack = version.knowledge_pack
        task = next((item for item in version.tasks if item.task_key == task_key and item.enabled), None)
        if task is None:
            raise ValueError(f"Knowledge pack task not found or disabled: {task_key}")

        framework = self._framework_by_code(framework_code)
        control = self.session.scalar(
            select(Control).where(Control.framework_id == framework.id, Control.control_id == control_id)
        )
        if control is None:
            raise ValueError(f"Framework control not found: {framework_code} {control_id}")
        unified_control = self._unified_control_by_code(unified_control_code)

        mapping = self.session.scalar(
            select(UnifiedControlMapping).where(
                UnifiedControlMapping.framework_id == framework.id,
                UnifiedControlMapping.control_id == control.id,
                UnifiedControlMapping.unified_control_id == unified_control.id,
            )
        )
        organization = self._organization_by_code(organization_code) if organization_code else None
        product = self._product_by_code(organization, product_code) if organization and product_code else None
        product_flavor = (
            self._product_flavor_by_code(product, product_flavor_code)
            if product and product_flavor_code
            else None
        )
        implementation = self._implementation_for_scope(
            organization=organization,
            product=product,
            product_flavor=product_flavor,
            framework=framework,
            control=control,
            unified_control=unified_control,
        )
        product_profile = self._product_profile_for_scope(
            organization=organization,
            product=product,
            product_flavor=product_flavor,
            framework=framework,
            control=control,
            unified_control=unified_control,
        )
        citations = self._citations_for_context(version, framework, control, unified_control)
        context = {
            "framework": {"code": framework.code, "name": framework.name, "version": framework.version},
            "framework_control": {
                "control_id": control.control_id,
                "title": control.title,
                "description": control.description,
                "summary": control.metadata_entry.summary if control.metadata_entry else "",
                "aws_guidance": control.metadata_entry.aws_guidance if control.metadata_entry else "",
                "check_type": control.metadata_entry.check_type if control.metadata_entry else "",
            },
            "unified_control": {
                "code": unified_control.code,
                "name": unified_control.name,
                "description": unified_control.description,
                "domain": unified_control.domain,
                "family": unified_control.family,
                "implementation_guidance": unified_control.implementation_guidance,
                "test_guidance": unified_control.test_guidance,
            },
            "mapping": {
                "status": mapping.approval_status if mapping else "missing",
                "mapping_type": mapping.mapping_type if mapping else "",
                "confidence": mapping.confidence if mapping else 0.0,
                "rationale": mapping.rationale if mapping else "",
            },
            "organization": {"code": organization.code if organization else "", "name": organization.name if organization else ""},
            "product": {
                "code": product.code if product else "",
                "name": product.name if product else "",
                "type": product.product_type if product else "",
            },
            "product_flavor": {
                "code": product_flavor.code if product_flavor else "",
                "name": product_flavor.name if product_flavor else "",
            },
            "implementation": {
                "id": implementation.id if implementation else None,
                "title": implementation.title if implementation else "",
                "objective": implementation.objective if implementation else "",
                "impl_general": implementation.impl_general if implementation else "",
                "impl_aws": implementation.impl_aws if implementation else "",
                "test_plan": implementation.test_plan if implementation else "",
                "status": implementation.status if implementation else "",
                "owner": implementation.owner if implementation else "",
            },
            "product_control_profile": {
                "id": product_profile.id if product_profile else None,
                "applicability_status": product_profile.applicability_status if product_profile else "",
                "implementation_status": product_profile.implementation_status if product_profile else "",
                "assessment_mode": product_profile.assessment_mode if product_profile else "",
                "autonomy_recommendation": product_profile.autonomy_recommendation if product_profile else "",
                "maturity_level": product_profile.maturity_level if product_profile else None,
                "review_notes": product_profile.review_notes if product_profile else "",
            },
        }
        draft = self._draft_response(task.task_key, context, citations)
        prompt_package = {
            "pack_code": pack.pack_code,
            "pack_name": pack.name,
            "version_label": version.version_label,
            "task_key": task.task_key,
            "task_name": task.name,
            "system_instruction": version.system_instruction,
            "operating_principles": self._json_list(version.operating_principles_json),
            "prompt_contract": self._json_dict(version.prompt_contract_json),
            "output_contract": self._json_dict(version.output_contract_json),
            "task_instructions": task.instruction_text,
            "review_checklist": self._json_list(task.review_checklist_json),
            "citations": citations,
            "context": context,
            "review_required": version.review_required,
        }
        return {
            "pack": pack,
            "version": version,
            "task": task,
            "prompt_package": prompt_package,
            "draft_response": draft,
            "citations": citations,
            "context": context,
            "framework": framework,
            "control": control,
            "unified_control": unified_control,
            "organization": organization,
            "implementation": implementation,
        }

    def capture_task_suggestion(
        self,
        *,
        pack_code: str | None,
        task_key: str,
        framework_code: str,
        control_id: str,
        unified_control_code: str,
        organization_code: str | None = None,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
        actor: str = "knowledge_pack_service",
    ) -> AISuggestion:
        bundle = self.build_task_package(
            pack_code=pack_code,
            task_key=task_key,
            framework_code=framework_code,
            control_id=control_id,
            unified_control_code=unified_control_code,
            organization_code=organization_code,
            product_code=product_code,
            product_flavor_code=product_flavor_code,
        )
        suggestion = AISuggestion(
            organization_id=bundle["organization"].id if bundle["organization"] else None,
            knowledge_pack_version_id=bundle["version"].id,
            unified_control_id=bundle["unified_control"].id,
            control_implementation_id=bundle["implementation"].id if bundle["implementation"] else None,
            framework_id=bundle["framework"].id,
            control_id=bundle["control"].id,
            suggestion_type="knowledge_pack_draft",
            task_key=task_key,
            provider="knowledge_pack",
            model_name=f"{bundle['pack'].pack_code}:{bundle['version'].version_label}",
            prompt_text=json.dumps(bundle["prompt_package"], indent=2, default=str),
            response_text=json.dumps(bundle["draft_response"], indent=2, default=str),
            citations_json=json.dumps(bundle["citations"], indent=2, default=str),
            accepted=False,
        )
        self.session.add(suggestion)
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="ai_suggestion",
            entity_id=suggestion.id,
            lifecycle_name="assurance_lifecycle",
            to_state="captured",
            actor=actor,
            payload={
                "pack_code": bundle["pack"].pack_code,
                "version_label": bundle["version"].version_label,
                "task_key": task_key,
                "framework_code": framework_code,
                "control_id": control_id,
                "unified_control_code": unified_control_code,
            },
        )
        return suggestion

    def upsert_pack_from_template(self, payload: dict[str, Any], actor: str = "knowledge_pack_seed") -> AIKnowledgePack:
        pack_code = _normalize_code(payload["pack_code"])
        pack = self.session.scalar(select(AIKnowledgePack).where(AIKnowledgePack.pack_code == pack_code))
        created = pack is None
        if pack is None:
            pack = AIKnowledgePack(pack_code=pack_code, name=payload["name"])
            self.session.add(pack)
        pack.name = payload["name"]
        pack.description = payload.get("description", "")
        pack.domain = payload.get("domain", "compliance_copilot")
        pack.scope_type = payload.get("scope_type", "cross_framework")
        pack.owner = payload.get("owner", "")
        pack.lifecycle_status = payload.get("lifecycle_status", "draft")
        pack.approval_status = payload.get("approval_status", "proposed")
        pack.default_task_key = payload.get("default_task_key", "")
        pack.notes = payload.get("notes", "")
        self.session.flush()

        version_payload = payload.get("version", {})
        version_label = version_payload.get("version_label", "1.0")
        version = self.session.scalar(
            select(AIKnowledgePackVersion).where(
                AIKnowledgePackVersion.knowledge_pack_id == pack.id,
                AIKnowledgePackVersion.version_label == version_label,
            )
        )
        if version is None:
            version = AIKnowledgePackVersion(knowledge_pack_id=pack.id, version_label=version_label)
            self.session.add(version)
        version.status = version_payload.get("status", "draft")
        version.review_required = bool(version_payload.get("review_required", True))
        version.system_instruction = version_payload.get("system_instruction", "")
        version.operating_principles_json = json.dumps(version_payload.get("operating_principles", []), indent=2)
        version.prompt_contract_json = json.dumps(version_payload.get("prompt_contract", {}), indent=2)
        version.output_contract_json = json.dumps(version_payload.get("output_contract", {}), indent=2)
        version.model_constraints_json = json.dumps(version_payload.get("model_constraints", {}), indent=2)
        version.created_by = version_payload.get("created_by", actor)
        version.approved_by = version_payload.get("approved_by", actor if version.status in {"approved", "active"} else "")
        version.approved_at = datetime.utcnow() if version.approved_by else None
        version.activated_at = datetime.utcnow() if version.status == "active" else None
        self.session.flush()

        existing_tasks = {item.task_key: item for item in version.tasks}
        for task_payload in version_payload.get("tasks", []):
            task = existing_tasks.get(task_payload["task_key"])
            if task is None:
                task = AIKnowledgePackTask(
                    knowledge_pack_version_id=version.id,
                    task_key=task_payload["task_key"],
                    name=task_payload["name"],
                )
                self.session.add(task)
            task.name = task_payload["name"]
            task.workflow_area = task_payload.get("workflow_area", "")
            task.description = task_payload.get("description", "")
            task.objective = task_payload.get("objective", "")
            task.input_schema_json = json.dumps(task_payload.get("input_schema", {}), indent=2)
            task.output_schema_json = json.dumps(task_payload.get("output_schema", {}), indent=2)
            task.instruction_text = task_payload.get("instruction_text", "")
            task.review_checklist_json = json.dumps(task_payload.get("review_checklist", []), indent=2)
            task.enabled = bool(task_payload.get("enabled", True))

        existing_cases = {item.case_code: item for item in version.eval_cases}
        for case_payload in version_payload.get("eval_cases", []):
            case = existing_cases.get(case_payload["case_code"])
            if case is None:
                case = AIKnowledgePackEvalCase(
                    knowledge_pack_version_id=version.id,
                    case_code=case_payload["case_code"],
                    name=case_payload["name"],
                )
                self.session.add(case)
            case.task_key = case_payload.get("task_key", "")
            case.name = case_payload["name"]
            case.input_payload_json = json.dumps(case_payload.get("input_payload", {}), indent=2)
            case.expected_assertions_json = json.dumps(case_payload.get("expected_assertions", []), indent=2)
            case.status = case_payload.get("status", "active")
            case.notes = case_payload.get("notes", "")

        for item in list(version.references):
            self.session.delete(item)
        self.session.flush()
        for reference_payload in version_payload.get("references", []):
            document = None
            if reference_payload.get("document_key") or reference_payload.get("document_name"):
                document, _ = self.reference_library.upsert_reference_document(
                    document_key=reference_payload.get("document_key") or reference_payload.get("document_name", ""),
                    name=reference_payload.get("document_name") or reference_payload.get("document_key", ""),
                    version=reference_payload.get("version", ""),
                    issuing_body=reference_payload.get("issuing_body", ""),
                    document_type=reference_payload.get("document_type", "reference"),
                    jurisdiction=reference_payload.get("jurisdiction", "global"),
                    source_url=reference_payload.get("source_url", ""),
                    notes=reference_payload.get("notes", ""),
                    actor=actor,
                )
            framework = (
                self.session.scalar(select(Framework).where(Framework.code == reference_payload["framework_code"]))
                if reference_payload.get("framework_code")
                else None
            )
            unified_control = (
                self.session.scalar(
                    select(UnifiedControl).where(
                        UnifiedControl.code == _normalize_code(reference_payload["unified_control_code"])
                    )
                )
                if reference_payload.get("unified_control_code")
                else None
            )
            imported_requirement = (
                self.session.get(ImportedRequirement, int(reference_payload["imported_requirement_id"]))
                if reference_payload.get("imported_requirement_id")
                else None
            )
            control = None
            if framework and reference_payload.get("control_id"):
                control = self.session.scalar(
                    select(Control).where(
                        Control.framework_id == framework.id,
                        Control.control_id == reference_payload["control_id"],
                    )
                )
            self.session.add(
                AIKnowledgePackReference(
                    knowledge_pack_version_id=version.id,
                    reference_document_id=document.id if document else None,
                    framework_id=framework.id if framework else None,
                    control_id=control.id if control else None,
                    unified_control_id=unified_control.id if unified_control else None,
                    imported_requirement_id=imported_requirement.id if imported_requirement else None,
                    use_mode=reference_payload.get("use_mode", "guidance"),
                    priority=int(reference_payload.get("priority", 100)),
                    notes=reference_payload.get("notes", ""),
                )
            )

        self.session.flush()
        if created:
            self.lifecycle.record_event(
                entity_type="ai_knowledge_pack",
                entity_id=pack.id,
                lifecycle_name="assurance_lifecycle",
                to_state=pack.lifecycle_status,
                actor=actor,
                payload={"pack_code": pack.pack_code},
            )
        self.lifecycle.record_event(
            entity_type="ai_knowledge_pack_version",
            entity_id=version.id,
            lifecycle_name="assurance_lifecycle",
            to_state=version.status,
            actor=actor,
            payload={"pack_code": pack.pack_code, "version_label": version.version_label},
        )
        return pack

    def _citations_for_context(
        self,
        version: AIKnowledgePackVersion,
        framework: Framework,
        control: Control,
        unified_control: UnifiedControl,
    ) -> list[dict[str, str]]:
        citations: list[dict[str, str]] = [
            {
                "type": "framework_control",
                "key": f"{framework.code}:{control.control_id}",
                "label": f"{framework.code} {control.control_id}",
                "source": control.title,
            },
            {
                "type": "unified_control",
                "key": unified_control.code,
                "label": unified_control.code,
                "source": unified_control.name,
            },
        ]
        for reference in sorted(version.references, key=lambda item: (item.priority, item.id)):
            if reference.reference_document:
                citations.append(
                    {
                        "type": "reference_document",
                        "key": reference.reference_document.document_key,
                        "label": reference.reference_document.name,
                        "source": reference.use_mode,
                    }
                )
            elif reference.framework:
                citations.append(
                    {
                        "type": "framework",
                        "key": reference.framework.code,
                        "label": reference.framework.name,
                        "source": reference.use_mode,
                    }
                )
        for link in unified_control.reference_links[:8]:
            if link.reference_document:
                citations.append(
                    {
                        "type": "unified_control_reference",
                        "key": link.reference_document.document_key,
                        "label": link.reference_document.name,
                        "source": link.relationship_type,
                    }
                )
        return self._dedupe_citations(citations)

    def _draft_response(self, task_key: str, context: dict[str, Any], citations: list[dict[str, str]]) -> dict[str, Any]:
        framework_control = context["framework_control"]
        unified_control = context["unified_control"]
        mapping = context["mapping"]
        implementation = context["implementation"]
        product = context["product"]
        product_flavor = context["product_flavor"]
        profile = context["product_control_profile"]
        assumptions = []
        review_points = []
        if mapping["status"] == "missing":
            review_points.append("No stored approved mapping exists yet; validate coverage before approval.")
        if not implementation["id"]:
            assumptions.append("No scoped implementation record exists yet; draft is based on control-level context only.")
        if product.get("code") and not product_flavor.get("code"):
            assumptions.append("No product flavor was selected, so the draft uses product-level wording.")

        if task_key == "mapping_rationale":
            draft = {
                "mapping_summary": (
                    f"{unified_control['code']} is a candidate pivot control for {context['framework']['code']} "
                    f"{framework_control['control_id']} because it addresses {framework_control['title'].lower()} "
                    "through reusable implementation and testing expectations."
                ),
                "rationale": (
                    f"The source requirement expects {framework_control['description'] or framework_control['summary'] or framework_control['title']}. "
                    f"The unified control centers on {unified_control['description'] or unified_control['name']}. "
                    "This mapping should be approved only if local implementation wording and evidence plans cover the full requirement intent."
                ),
                "implementation_angle": (
                    framework_control["aws_guidance"]
                    or unified_control["implementation_guidance"]
                    or "Refine AWS and operational guidance before final approval."
                ),
                "review_notes": (
                    mapping["rationale"] or "Add explicit notes for partial coverage, inherited controls, or shared-control dependencies."
                ),
            }
            confidence = 0.79 if mapping["status"] != "missing" else 0.62
        elif task_key == "unified_control_wording":
            draft = {
                "control_name": unified_control["name"] or framework_control["title"],
                "requirement_coverage_summary": (
                    f"Maintain a reusable control that covers {framework_control['title'].lower()} "
                    f"for {context['framework']['code']} {framework_control['control_id']}."
                ),
                "implementation_guidance": (
                    unified_control["implementation_guidance"]
                    or framework_control["aws_guidance"]
                    or "Define ownership, operating procedures, and technology configuration needed to satisfy the requirement."
                ),
                "test_guidance": (
                    unified_control["test_guidance"]
                    or "Review implementation records, supporting evidence, and control operation results against the source requirement."
                ),
            }
            confidence = 0.76
        else:
            scope = product["name"] or product["code"] or "the scoped product"
            if product_flavor["name"] or product_flavor["code"]:
                scope = f"{scope} ({product_flavor['name'] or product_flavor['code']})"
            draft = {
                "title": implementation["title"] or f"{unified_control['name']} implementation for {scope}",
                "objective": implementation["objective"] or framework_control["summary"] or framework_control["title"],
                "implementation_general": (
                    implementation["impl_general"]
                    or f"{scope} implements {unified_control['code']} through documented ownership, operating procedures, and periodic review."
                ),
                "implementation_aws": (
                    implementation["impl_aws"]
                    or framework_control["aws_guidance"]
                    or "Add AWS-specific technical enforcement and monitoring details for the scoped environment."
                ),
                "testing_approach": (
                    implementation["test_plan"]
                    or f"Assess the control using the current assessment mode `{profile['assessment_mode'] or 'manual'}` and align evidence collection with approved plans."
                ),
            }
            confidence = 0.72 if implementation["id"] else 0.58

        if not citations:
            review_points.append("No citations were attached; verify reference coverage before using this draft.")
        if profile.get("maturity_level") is not None and profile["maturity_level"] < 3:
            review_points.append("Control maturity is below 3; keep human review and manual validation prominent.")

        return {
            "task_key": task_key,
            "summary": draft[next(iter(draft))] if draft else "",
            "draft": draft,
            "citations": citations,
            "assumptions": assumptions,
            "review_points": review_points or ["Human reviewer must validate wording and traceability before acceptance."],
            "confidence": round(confidence, 2),
        }

    @staticmethod
    def _json_list(value: str) -> list[Any]:
        try:
            payload = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []

    @staticmethod
    def _json_dict(value: str) -> dict[str, Any]:
        try:
            payload = json.loads(value or "{}")
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _dedupe_citations(citations: list[dict[str, str]]) -> list[dict[str, str]]:
        seen = set()
        unique = []
        for item in citations:
            key = (item.get("type", ""), item.get("key", ""))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _framework_by_code(self, framework_code: str) -> Framework:
        framework = self.session.scalar(select(Framework).where(Framework.code == framework_code))
        if framework is None:
            raise ValueError(f"Framework not found: {framework_code}")
        return framework

    def _unified_control_by_code(self, unified_control_code: str) -> UnifiedControl:
        normalized = _normalize_code(unified_control_code)
        unified_control = self.session.scalar(select(UnifiedControl).where(UnifiedControl.code == normalized))
        if unified_control is None:
            raise ValueError(f"Unified control not found: {normalized}")
        return unified_control

    def _organization_by_code(self, organization_code: str | None) -> Organization | None:
        if not organization_code:
            return None
        organization = self.session.scalar(select(Organization).where(Organization.code == organization_code))
        if organization is None:
            raise ValueError(f"Organization not found: {organization_code}")
        return organization

    def _product_by_code(self, organization: Organization | None, product_code: str | None) -> Product | None:
        if organization is None or not product_code:
            return None
        product = self.session.scalar(
            select(Product).where(Product.organization_id == organization.id, Product.code == product_code)
        )
        if product is None:
            raise ValueError(f"Product not found: {organization.code} {product_code}")
        return product

    def _product_flavor_by_code(self, product: Product | None, product_flavor_code: str | None) -> ProductFlavor | None:
        if product is None or not product_flavor_code:
            return None
        flavor = self.session.scalar(
            select(ProductFlavor).where(
                ProductFlavor.product_id == product.id,
                ProductFlavor.code == product_flavor_code,
            )
        )
        if flavor is None:
            raise ValueError(f"Product flavor not found: {product.code} {product_flavor_code}")
        return flavor

    def _implementation_for_scope(
        self,
        *,
        organization: Organization | None,
        product: Product | None,
        product_flavor: ProductFlavor | None,
        framework: Framework,
        control: Control,
        unified_control: UnifiedControl,
    ) -> ControlImplementation | None:
        query = select(ControlImplementation).where(
            ControlImplementation.framework_id == framework.id,
            ControlImplementation.control_id == control.id,
            ControlImplementation.unified_control_id == unified_control.id,
        )
        if organization is not None:
            query = query.where(ControlImplementation.organization_id == organization.id)
        if product is not None:
            query = query.where(ControlImplementation.product_id == product.id)
        if product_flavor is not None:
            query = query.where(ControlImplementation.product_flavor_id == product_flavor.id)
        return self.session.scalar(query.order_by(ControlImplementation.id.desc()))

    def _product_profile_for_scope(
        self,
        *,
        organization: Organization | None,
        product: Product | None,
        product_flavor: ProductFlavor | None,
        framework: Framework,
        control: Control,
        unified_control: UnifiedControl,
    ) -> ProductControlProfile | None:
        if organization is None or product is None:
            return None
        query = select(ProductControlProfile).where(
            ProductControlProfile.organization_id == organization.id,
            ProductControlProfile.product_id == product.id,
            ProductControlProfile.framework_id == framework.id,
            ProductControlProfile.control_id == control.id,
            ProductControlProfile.unified_control_id == unified_control.id,
        )
        if product_flavor is None:
            query = query.where(ProductControlProfile.product_flavor_id.is_(None))
        else:
            query = query.where(ProductControlProfile.product_flavor_id == product_flavor.id)
        return self.session.scalar(query.order_by(ProductControlProfile.id.desc()))
