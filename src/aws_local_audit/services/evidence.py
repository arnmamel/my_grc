from __future__ import annotations

import base64
import json
import mimetypes
from datetime import datetime
from pathlib import Path

from sqlalchemy import false, select
from sqlalchemy.orm import selectinload

from aws_local_audit.aws_session import build_session
from aws_local_audit.collectors import COLLECTORS
from aws_local_audit.config import settings
from aws_local_audit.integrations.confluence import ConfluenceClient
from aws_local_audit.models import (
    AwsEvidenceTarget,
    AwsCliProfile,
    Control,
    EvidenceCollectionPlan,
    EvidenceItem,
    Framework,
    OrganizationFrameworkBinding,
    Product,
    ProductControlProfile,
    ProductFlavor,
    SystemSetting,
    UnifiedControlMapping,
)
from aws_local_audit.security import EvidenceVault, KeyringSecretStore
from aws_local_audit.services.lifecycle import LifecycleService
from aws_local_audit.services.script_modules import ScriptModuleService


READY_PLAN_STATES = {"approved", "active", "ready", "published"}


class EvidenceService:
    def __init__(self, session):
        self.session = session
        self.vault = EvidenceVault(KeyringSecretStore(settings.secret_namespace, settings.secret_files_dir))
        self.lifecycle = LifecycleService(session)

    def collect_for_framework(self, framework_code: str) -> list[EvidenceItem]:
        framework = self.session.scalar(
            select(Framework).options(selectinload(Framework.controls)).where(Framework.code == framework_code)
        )
        if framework is None:
            raise ValueError(f"Framework not found: {framework_code}")
        if not framework.active or not framework.aws_profile or not framework.aws_region:
            raise ValueError(f"Framework {framework_code} is not enabled with an AWS profile and region.")

        return self._collect_controls(
            framework=framework,
            default_aws_profile=framework.aws_profile,
            default_aws_region=framework.aws_region,
            confluence=ConfluenceClient(self.session),
        )

    def collect_for_binding(
        self,
        binding_code: str,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
    ) -> list[EvidenceItem]:
        binding = self.session.scalar(
            select(OrganizationFrameworkBinding)
            .options(
                selectinload(OrganizationFrameworkBinding.framework).selectinload(Framework.controls),
                selectinload(OrganizationFrameworkBinding.confluence_connection),
            )
            .where(OrganizationFrameworkBinding.binding_code == binding_code)
        )
        if binding is None:
            raise ValueError(f"Framework binding not found: {binding_code}")
        if not binding.enabled:
            raise ValueError(f"Framework binding is disabled: {binding_code}")

        product = None
        flavor = None
        if product_code:
            product = self.session.scalar(
                select(Product).where(Product.organization_id == binding.organization_id, Product.code == product_code)
            )
            if product is None:
                raise ValueError(f"Product not found for binding {binding_code}: {product_code}")
        if product_flavor_code:
            if product is None:
                raise ValueError("A product is required when a product flavor is provided.")
            flavor = self.session.scalar(
                select(ProductFlavor).where(ProductFlavor.product_id == product.id, ProductFlavor.code == product_flavor_code)
            )
            if flavor is None:
                raise ValueError(f"Product flavor not found for binding {binding_code}: {product_flavor_code}")

        return self._collect_controls(
            framework=binding.framework,
            framework_binding_id=binding.id,
            default_aws_profile=binding.aws_profile,
            default_aws_region=binding.aws_region,
            default_aws_account_id=binding.aws_account_id or "",
            organization_id=binding.organization_id,
            product_id=product.id if product else None,
            product_flavor_id=flavor.id if flavor else None,
            confluence_parent_page_id=binding.confluence_parent_page_id,
            confluence=ConfluenceClient(
                self.session,
                binding.confluence_connection.name if binding.confluence_connection else None,
            ),
        )

    def build_collection_plan_for_binding(
        self,
        binding_code: str,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
    ) -> dict:
        binding = self.session.scalar(
            select(OrganizationFrameworkBinding)
            .options(selectinload(OrganizationFrameworkBinding.framework).selectinload(Framework.controls))
            .where(OrganizationFrameworkBinding.binding_code == binding_code)
        )
        if binding is None:
            raise ValueError(f"Framework binding not found: {binding_code}")
        if not binding.enabled:
            raise ValueError(f"Framework binding is disabled: {binding_code}")

        product = None
        flavor = None
        if product_code:
            product = self.session.scalar(
                select(Product).where(Product.organization_id == binding.organization_id, Product.code == product_code)
            )
            if product is None:
                raise ValueError(f"Product not found for binding {binding_code}: {product_code}")
        if product_flavor_code:
            if product is None:
                raise ValueError("A product is required when a product flavor is provided.")
            flavor = self.session.scalar(
                select(ProductFlavor).where(ProductFlavor.product_id == product.id, ProductFlavor.code == product_flavor_code)
            )
            if flavor is None:
                raise ValueError(f"Product flavor not found for binding {binding_code}: {product_flavor_code}")

        return self._build_collection_plan(
            framework=binding.framework,
            framework_binding_id=binding.id,
            default_aws_profile=binding.aws_profile,
            default_aws_region=binding.aws_region,
            default_aws_account_id=binding.aws_account_id or "",
            organization_id=binding.organization_id,
            product_id=product.id if product else None,
            product_flavor_id=flavor.id if flavor else None,
            binding_code=binding.binding_code,
            product_code=product.code if product else "",
            product_flavor_code=flavor.code if flavor else "",
        )

    def upload_manual_evidence(
        self,
        binding_code: str,
        control_id: str,
        summary: str,
        status: str = "pass",
        product_code: str | None = None,
        product_flavor_code: str | None = None,
        note: str = "",
        file_path: str | None = None,
        uploaded_by: str = "",
        classification: str = "confidential",
        publish_to_confluence: bool = False,
    ) -> EvidenceItem:
        binding = self.session.scalar(
            select(OrganizationFrameworkBinding)
            .options(
                selectinload(OrganizationFrameworkBinding.framework),
                selectinload(OrganizationFrameworkBinding.confluence_connection),
            )
            .where(OrganizationFrameworkBinding.binding_code == binding_code)
        )
        if binding is None:
            raise ValueError(f"Framework binding not found: {binding_code}")

        control = self.session.scalar(
            select(Control).where(Control.framework_id == binding.framework_id, Control.control_id == control_id)
        )
        if control is None:
            raise ValueError(f"Control not found for binding {binding_code}: {control_id}")

        product = None
        flavor = None
        if product_code:
            product = self.session.scalar(
                select(Product).where(Product.organization_id == binding.organization_id, Product.code == product_code)
            )
            if product is None:
                raise ValueError(f"Product not found for binding {binding_code}: {product_code}")
        if product_flavor_code:
            if product is None:
                raise ValueError("A product is required when a product flavor is provided.")
            flavor = self.session.scalar(
                select(ProductFlavor).where(ProductFlavor.product_id == product.id, ProductFlavor.code == product_flavor_code)
            )
            if flavor is None:
                raise ValueError(f"Product flavor not found for binding {binding_code}: {product_flavor_code}")

        artifact_payload = None
        if file_path:
            path = Path(file_path)
            content = path.read_bytes()
            artifact_payload = {
                "file_name": path.name,
                "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "content_b64": base64.b64encode(content).decode("ascii"),
                "size_bytes": len(content),
            }

        confluence_client = ConfluenceClient(
            self.session,
            binding.confluence_connection.name if binding.confluence_connection else None,
        )
        confluence_details = {"configured": confluence_client.configured()}
        confluence_page_id = ""
        payload = {
            "framework": binding.framework.code,
            "control": control.control_id,
            "source_type": "manual_upload",
            "uploaded_by": uploaded_by,
            "note": note,
            "artifact": artifact_payload,
            "status": status,
            "summary": summary,
        }

        if publish_to_confluence and confluence_client.configured():
            try:
                page = confluence_client.create_page(
                    title=f"Manual Evidence {binding.framework.code} {control.control_id} {datetime.utcnow():%Y-%m-%d %H:%M}",
                    body_html=self._evidence_body(
                        binding.framework,
                        control,
                        status,
                        summary,
                        json.dumps(payload, indent=2, default=str),
                    ),
                    parent_page_id=binding.confluence_parent_page_id,
                )
                confluence_page_id = page.page_id
                if artifact_payload is not None:
                    attachment = confluence_client.upload_attachment(
                        page_id=page.page_id,
                        filename=artifact_payload["file_name"],
                        content=base64.b64decode(artifact_payload["content_b64"]),
                        content_type=artifact_payload["content_type"],
                        comment="Manual evidence attachment uploaded by my_grc.",
                    )
                    confluence_details.update(
                        {
                            "page_id": page.page_id,
                            "page_url": page.url,
                            "attachment_id": attachment["attachment_id"],
                            "attachment_url": attachment["url"],
                        }
                    )
            except Exception as exc:
                confluence_details.update({"status": "error", "message": str(exc)})

        payload["confluence"] = confluence_details
        evidence = EvidenceItem(
            organization_id=binding.organization_id,
            product_id=product.id if product else None,
            product_flavor_id=flavor.id if flavor else None,
            framework_id=binding.framework_id,
            control_id=control.id,
            status=status,
            summary=summary,
            payload_json=self.vault.encrypt_json(payload),
            payload_storage_mode="aesgcm_v1",
            payload_digest=self.vault.digest_for_payload(payload),
            lifecycle_status="pending_review",
            classification=classification,
            confluence_page_id=confluence_page_id or None,
        )
        self.session.add(evidence)
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="evidence_item",
            entity_id=evidence.id,
            lifecycle_name="evidence_lifecycle",
            to_state=evidence.lifecycle_status,
            actor=uploaded_by or "evidence_service",
            rationale=note,
            payload={
                "framework": binding.framework.code,
                "control_id": control.control_id,
                "status": evidence.status,
                "source_type": "manual_upload",
            },
        )
        return evidence

    def review_evidence_item(
        self,
        evidence_id: int,
        lifecycle_status: str,
        actor: str = "evidence_service",
        rationale: str = "",
    ) -> EvidenceItem:
        evidence = self.session.get(EvidenceItem, evidence_id)
        if evidence is None:
            raise ValueError(f"Evidence item not found: {evidence_id}")
        previous_state = evidence.lifecycle_status
        self.lifecycle.ensure_transition(
            entity_type="evidence_item",
            lifecycle_name="evidence_lifecycle",
            from_state=previous_state,
            to_state=lifecycle_status,
        )
        evidence.lifecycle_status = lifecycle_status
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="evidence_item",
            entity_id=evidence.id,
            lifecycle_name="evidence_lifecycle",
            from_state=previous_state,
            to_state=evidence.lifecycle_status,
            actor=actor,
            rationale=rationale,
            payload={
                "framework_id": evidence.framework_id,
                "control_id": evidence.control.control_id if evidence.control else "",
                "status": evidence.status,
            },
        )
        return evidence

    def list_evidence_items(
        self,
        framework_id: int | None = None,
        organization_id: int | None = None,
        product_id: int | None = None,
        product_flavor_id: int | None = None,
        limit: int = 100,
    ) -> list[EvidenceItem]:
        query = select(EvidenceItem).order_by(EvidenceItem.collected_at.desc())
        if framework_id is not None:
            query = query.where(EvidenceItem.framework_id == framework_id)
        if organization_id is not None:
            query = query.where(EvidenceItem.organization_id == organization_id)
        if product_id is None and organization_id is not None:
            query = query.where(EvidenceItem.product_id.is_(None))
        elif product_id is not None:
            query = query.where(EvidenceItem.product_id == product_id)
        if product_flavor_id is None and product_id is not None:
            query = query.where(EvidenceItem.product_flavor_id.is_(None))
        elif product_flavor_id is not None:
            query = query.where(EvidenceItem.product_flavor_id == product_flavor_id)
        return list(self.session.scalars(query.limit(limit)))

    def manual_artifact(self, evidence_item: EvidenceItem) -> dict | None:
        payload = self.decrypt_payload(evidence_item)
        artifact = payload.get("artifact")
        if not artifact:
            return None
        return {
            "file_name": artifact.get("file_name", ""),
            "content_type": artifact.get("content_type", "application/octet-stream"),
            "size_bytes": artifact.get("size_bytes", 0),
            "content_bytes": base64.b64decode(artifact.get("content_b64", "") or b""),
        }

    def _record_evidence_item(
        self,
        *,
        framework: Framework,
        control: Control,
        status: str,
        summary: str,
        payload: dict,
        lifecycle_status: str,
        organization_id: int | None = None,
        product_id: int | None = None,
        product_flavor_id: int | None = None,
        classification: str = "confidential",
        confluence_page_id: str | None = None,
        actor: str = "evidence_service",
        rationale: str = "",
    ) -> EvidenceItem:
        evidence = EvidenceItem(
            organization_id=organization_id,
            product_id=product_id,
            product_flavor_id=product_flavor_id,
            framework_id=framework.id,
            control_id=control.id,
            status=status,
            summary=summary,
            payload_json=self.vault.encrypt_json(payload),
            payload_storage_mode="aesgcm_v1",
            payload_digest=self.vault.digest_for_payload(payload),
            lifecycle_status=lifecycle_status,
            classification=classification,
            confluence_page_id=confluence_page_id or None,
        )
        self.session.add(evidence)
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="evidence_item",
            entity_id=evidence.id,
            lifecycle_name="evidence_lifecycle",
            to_state=evidence.lifecycle_status,
            actor=actor,
            rationale=rationale,
            payload={"framework": framework.code, "control_id": control.control_id, "status": evidence.status},
        )
        return evidence

    def _publish_to_confluence(
        self,
        *,
        confluence_client: ConfluenceClient,
        framework: Framework,
        control: Control,
        aggregate_status: str,
        aggregate_summary: str,
        confluence_parent_page_id: str | None,
        payload: dict,
        attachments: list[dict],
    ) -> tuple[dict, str]:
        confluence_details = {"configured": confluence_client.configured()}
        confluence_page_id = ""
        if not confluence_client.configured():
            return confluence_details, confluence_page_id
        try:
            page = confluence_client.create_page(
                title=f"Evidence {framework.code} {control.control_id} {datetime.utcnow():%Y-%m-%d %H:%M}",
                body_html=self._evidence_body(
                    framework,
                    control,
                    aggregate_status,
                    aggregate_summary,
                    json.dumps(payload, indent=2, default=str),
                ),
                parent_page_id=confluence_parent_page_id,
            )
            confluence_page_id = page.page_id
            encrypted_attachment = self.vault.encrypt_json(payload).encode("utf-8")
            envelope = confluence_client.upload_attachment(
                page_id=page.page_id,
                filename=self._evidence_attachment_name(framework.code, control.control_id, suffix=".json"),
                content=encrypted_attachment,
                content_type="application/json",
                comment="Encrypted evidence envelope uploaded by my_grc.",
            )
            confluence_details.update(
                {
                    "page_id": page.page_id,
                    "page_url": page.url,
                    "attachment_filename": envelope["filename"],
                    "attachment_id": envelope["attachment_id"],
                    "attachment_url": envelope["url"],
                }
            )
            published_artifacts = []
            for item in attachments:
                path = Path(item.get("path", ""))
                if not path.exists():
                    continue
                uploaded = confluence_client.upload_attachment(
                    page_id=page.page_id,
                    filename=path.name,
                    content=path.read_bytes(),
                    content_type=item.get("content_type") or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    comment=f"Evidence artifact for {framework.code} {control.control_id}.",
                )
                published_artifacts.append(
                    {
                        "label": item.get("label", path.name),
                        "filename": uploaded["filename"],
                        "attachment_id": uploaded["attachment_id"],
                        "url": uploaded["url"],
                    }
                )
            if published_artifacts:
                confluence_details["published_artifacts"] = published_artifacts
        except Exception as exc:
            confluence_details.update({"status": "error", "message": str(exc)})
        return confluence_details, confluence_page_id

    @staticmethod
    def _evidence_attachment_name(framework_code: str, control_id: str, suffix: str = ".json") -> str:
        return (
            f"evidence-{framework_code.lower()}-{control_id.lower().replace('.', '_')}-"
            f"{datetime.utcnow():%Y%m%dT%H%M%S}{suffix}"
        )

    def _collect_controls(
        self,
        framework: Framework,
        default_aws_profile: str,
        default_aws_region: str,
        default_aws_account_id: str = "",
        framework_binding_id: int | None = None,
        organization_id: int | None = None,
        product_id: int | None = None,
        product_flavor_id: int | None = None,
        confluence_parent_page_id: str | None = None,
        confluence: ConfluenceClient | None = None,
    ) -> list[EvidenceItem]:
        results: list[EvidenceItem] = []
        confluence_client = confluence or ConfluenceClient(self.session)
        session_cache: dict[tuple[str, str], object] = {}
        offline_mode = self._offline_mode_enabled()
        unified_by_control = {
            item.control_id: item.unified_control_id
            for item in self.session.scalars(
                select(UnifiedControlMapping).where(
                    UnifiedControlMapping.framework_id == framework.id,
                    UnifiedControlMapping.approval_status == "approved",
                )
            ).all()
        }
        evidence_plans = self._load_evidence_plans(
            framework_id=framework.id,
            unified_control_ids={item for item in unified_by_control.values() if item is not None},
        )
        for control in framework.controls:
            applicability = self._resolve_applicability_profile(
                organization_id=organization_id,
                product_id=product_id,
                product_flavor_id=product_flavor_id,
                control_id=control.id,
            )
            unified_control_id = unified_by_control.get(control.id)
            plan = self._best_plan_for_control(
                framework_id=framework.id,
                control_id=control.id,
                unified_control_id=unified_control_id,
                evidence_plans=evidence_plans,
            )
            if applicability and applicability.applicability_status in {"not_applicable", "inherited"}:
                payload = {
                    "framework": framework.code,
                    "control": control.control_id,
                    "applicability_status": applicability.applicability_status,
                    "profile_id": applicability.id,
                }
                evidence = self._record_evidence_item(
                    framework=framework,
                    control=control,
                    organization_id=organization_id,
                    product_id=product_id,
                    product_flavor_id=product_flavor_id,
                    status=applicability.applicability_status,
                    summary=(
                        "Control marked as inherited in the product control profile."
                        if applicability.applicability_status == "inherited"
                        else "Control marked as not applicable in the product control profile."
                    ),
                    payload=payload,
                    lifecycle_status="skipped",
                )
                results.append(evidence)
                continue

            collection_targets = self._resolve_collection_targets(
                framework_binding_id=framework_binding_id,
                organization_id=organization_id,
                product_id=product_id,
                product_flavor_id=product_flavor_id,
                control=control,
                default_aws_profile=default_aws_profile,
                default_aws_region=default_aws_region,
                default_aws_account_id=default_aws_account_id,
            )
            execution_mode = plan.execution_mode if plan else ("automated" if control.evidence_query in COLLECTORS else "manual")
            collection_targets = self._normalize_collection_targets(
                execution_mode=execution_mode,
                plan=plan,
                targets=collection_targets,
            )
            plan_payload = {
                "plan_code": plan.plan_code if plan else "",
                "plan_status": plan.lifecycle_status if plan else "missing",
                "execution_mode": execution_mode,
                "evidence_type": plan.evidence_type if plan else "",
                "minimum_freshness_days": plan.minimum_freshness_days if plan else 30,
                "instructions": plan.instructions if plan else "",
            }

            if plan is None:
                payload = {
                    "framework": framework.code,
                    "control": control.control_id,
                    "collection_mode": "plan_required",
                    "targets": collection_targets,
                    "plan": plan_payload,
                }
                evidence = self._record_evidence_item(
                    framework=framework,
                    control=control,
                    organization_id=organization_id,
                    product_id=product_id,
                    product_flavor_id=product_flavor_id,
                    status="plan_missing",
                    summary=(
                        f"No approved evidence plan exists for {framework.code} {control.control_id}. "
                        "Create and approve a collection plan before attempting collection."
                    ),
                    payload=payload,
                    lifecycle_status="awaiting_collection",
                )
                results.append(evidence)
                continue

            if plan.lifecycle_status not in READY_PLAN_STATES:
                payload = {
                    "framework": framework.code,
                    "control": control.control_id,
                    "collection_mode": "plan_pending_review",
                    "targets": collection_targets,
                    "plan": plan_payload,
                }
                evidence = self._record_evidence_item(
                    framework=framework,
                    control=control,
                    organization_id=organization_id,
                    product_id=product_id,
                    product_flavor_id=product_flavor_id,
                    status="plan_pending_review",
                    summary=(
                        f"Evidence plan {plan.plan_code} is {plan.lifecycle_status}. "
                        "Approve or activate the plan before collection."
                    ),
                    payload=payload,
                    lifecycle_status="awaiting_collection",
                )
                results.append(evidence)
                continue

            if execution_mode in {"manual", "assisted"}:
                payload = {
                    "framework": framework.code,
                    "control": control.control_id,
                    "collection_mode": execution_mode,
                    "targets": collection_targets,
                    "plan": plan_payload,
                }
                evidence = self._record_evidence_item(
                    framework=framework,
                    control=control,
                    organization_id=organization_id,
                    product_id=product_id,
                    product_flavor_id=product_flavor_id,
                    status=f"{execution_mode}_action_required",
                    summary=self._manual_collection_summary(
                        control=control,
                        execution_mode=execution_mode,
                        plan=plan,
                        target_count=len(collection_targets),
                    ),
                    payload=payload,
                    lifecycle_status="awaiting_collection",
                )
                results.append(evidence)
                continue

            if offline_mode:
                payload = {
                    "framework": framework.code,
                    "control": control.control_id,
                    "collection_mode": "offline",
                    "targets": collection_targets,
                    "plan": plan_payload,
                }
                evidence = self._record_evidence_item(
                    framework=framework,
                    control=control,
                    organization_id=organization_id,
                    product_id=product_id,
                    product_flavor_id=product_flavor_id,
                    status="deferred_offline",
                    summary=f"Offline mode enabled; collection deferred for {len(collection_targets)} target(s).",
                    payload=payload,
                    lifecycle_status="awaiting_collection",
                )
                results.append(evidence)
                continue

            script_collector_key = plan.collector_key if plan and plan.collector_key.startswith(("script:", "script-binding:")) else ""
            if script_collector_key:
                try:
                    script_result = ScriptModuleService(self.session).execute_for_evidence(
                        script_collector_key,
                        framework=framework,
                        control=control,
                        plan=plan,
                        collection_targets=collection_targets,
                        organization_id=organization_id,
                        framework_binding_id=framework_binding_id,
                        product_id=product_id,
                        product_flavor_id=product_flavor_id,
                        unified_control_id=unified_control_id,
                    )
                    payload = {
                        "framework": framework.code,
                        "control": control.control_id,
                        "collected_at": datetime.utcnow().isoformat(),
                        "targets": collection_targets,
                        "script": script_result["payload"],
                        "artifacts": script_result["artifacts"],
                        "plan": plan_payload,
                    }
                    confluence_details, confluence_page_id = self._publish_to_confluence(
                        confluence_client=confluence_client,
                        framework=framework,
                        control=control,
                        aggregate_status=script_result["status"],
                        aggregate_summary=script_result["summary"],
                        confluence_parent_page_id=confluence_parent_page_id,
                        payload=payload,
                        attachments=script_result["artifacts"],
                    )
                    payload["confluence"] = confluence_details
                    evidence = self._record_evidence_item(
                        framework=framework,
                        control=control,
                        organization_id=organization_id,
                        product_id=product_id,
                        product_flavor_id=product_flavor_id,
                        status=script_result["status"],
                        summary=(
                            script_result["summary"]
                            if confluence_details.get("status") != "error"
                            else f"{script_result['summary']} Confluence publish warning: {confluence_details['message']}"
                        ),
                        payload=payload,
                        lifecycle_status="collection_error" if script_result["status"] == "error" else "collected",
                        confluence_page_id=confluence_page_id or None,
                    )
                    results.append(evidence)
                except ValueError as exc:
                    payload = {
                        "error": str(exc),
                        "targets": collection_targets,
                        "plan": plan_payload,
                    }
                    evidence = self._record_evidence_item(
                        framework=framework,
                        control=control,
                        organization_id=organization_id,
                        product_id=product_id,
                        product_flavor_id=product_flavor_id,
                        status="not_implemented",
                        summary=str(exc),
                        payload=payload,
                        lifecycle_status="collector_missing",
                    )
                    results.append(evidence)
                continue

            collector = COLLECTORS.get(control.evidence_query)
            if collector is None:
                payload = {
                    "error": f"No collector registered for {control.evidence_query}",
                    "targets": collection_targets,
                    "plan": plan_payload,
                }
                evidence = self._record_evidence_item(
                    framework=framework,
                    control=control,
                    organization_id=organization_id,
                    product_id=product_id,
                    product_flavor_id=product_flavor_id,
                    status="not_implemented",
                    summary=f"No collector registered for {control.evidence_query}",
                    payload=payload,
                    lifecycle_status="collector_missing",
                )
                results.append(evidence)
                continue

            target_results = []
            for target in collection_targets:
                for region_name in target["regions"]:
                    try:
                        session_key = (target["aws_profile"], region_name)
                        aws_session = session_cache.get(session_key)
                        if aws_session is None:
                            aws_session = build_session(target["aws_profile"], region_name)
                            session_cache[session_key] = aws_session
                        result = collector.collect(aws_session, region_name)
                        target_results.append(
                            {
                                "target_code": target["target_code"],
                                "target_name": target["name"],
                                "aws_profile": target["aws_profile"],
                                "aws_account_id": target["aws_account_id"],
                                "role_name": target["role_name"],
                                "region": region_name,
                                "status": result.status,
                                "summary": result.summary,
                                "payload": result.payload,
                            }
                        )
                    except Exception as exc:
                        target_results.append(
                            {
                                "target_code": target["target_code"],
                                "target_name": target["name"],
                                "aws_profile": target["aws_profile"],
                                "aws_account_id": target["aws_account_id"],
                                "role_name": target["role_name"],
                                "region": region_name,
                                "status": "error",
                                "summary": (
                                    f"AWS session unavailable for profile {target['aws_profile']}. "
                                    f"Run `aws sso login --profile {target['aws_profile']}` and retry. {exc}"
                                ),
                                "payload": {
                                    "error": str(exc),
                                    "hint": f"aws sso login --profile {target['aws_profile']}",
                                },
                            }
                        )

            aggregate_status, aggregate_summary = self._aggregate_target_results(target_results)
            payload = {
                "framework": framework.code,
                "control": control.control_id,
                "collected_at": datetime.utcnow().isoformat(),
                "targets": target_results,
                "plan": plan_payload,
            }
            confluence_details, confluence_page_id = self._publish_to_confluence(
                confluence_client=confluence_client,
                framework=framework,
                control=control,
                aggregate_status=aggregate_status,
                aggregate_summary=aggregate_summary,
                confluence_parent_page_id=confluence_parent_page_id,
                payload=payload,
                attachments=[],
            )
            payload["confluence"] = confluence_details
            evidence = self._record_evidence_item(
                framework=framework,
                control=control,
                organization_id=organization_id,
                product_id=product_id,
                product_flavor_id=product_flavor_id,
                status=aggregate_status,
                summary=(
                    aggregate_summary
                    if confluence_details.get("status") != "error"
                    else f"{aggregate_summary} Confluence publish warning: {confluence_details['message']}"
                ),
                payload=payload,
                lifecycle_status="collection_error" if aggregate_status == "error" else "collected",
                confluence_page_id=confluence_page_id or None,
            )
            results.append(evidence)
        return results

    def _build_collection_plan(
        self,
        framework: Framework,
        default_aws_profile: str,
        default_aws_region: str,
        default_aws_account_id: str = "",
        framework_binding_id: int | None = None,
        organization_id: int | None = None,
        product_id: int | None = None,
        product_flavor_id: int | None = None,
        binding_code: str = "",
        product_code: str = "",
        product_flavor_code: str = "",
    ) -> dict:
        profile_lookup = {
            item.profile_name: item
            for item in self.session.scalars(
                select(AwsCliProfile).where(AwsCliProfile.status == "active")
            ).all()
        }
        unified_by_control = {
            item.control_id: item.unified_control_id
            for item in self.session.scalars(
                select(UnifiedControlMapping).where(
                    UnifiedControlMapping.framework_id == framework.id,
                    UnifiedControlMapping.approval_status == "approved",
                )
            ).all()
        }
        evidence_plans = self._load_evidence_plans(
            framework_id=framework.id,
            unified_control_ids={item for item in unified_by_control.values() if item is not None},
        )
        profile_index: dict[str, dict] = {}
        controls: list[dict] = []
        for control in framework.controls:
            applicability = self._resolve_applicability_profile(
                organization_id=organization_id,
                product_id=product_id,
                product_flavor_id=product_flavor_id,
                control_id=control.id,
            )
            targets = self._resolve_collection_targets(
                framework_binding_id=framework_binding_id,
                organization_id=organization_id,
                product_id=product_id,
                product_flavor_id=product_flavor_id,
                control=control,
                default_aws_profile=default_aws_profile,
                default_aws_region=default_aws_region,
                default_aws_account_id=default_aws_account_id,
            )
            unified_control_id = unified_by_control.get(control.id)
            plan = self._best_plan_for_control(
                framework_id=framework.id,
                control_id=control.id,
                unified_control_id=unified_control_id,
                evidence_plans=evidence_plans,
            )
            applicability_status = applicability.applicability_status if applicability else "applicable"
            execution_mode = plan.execution_mode if plan else ("automated" if control.evidence_query in COLLECTORS else "manual")
            targets = self._normalize_collection_targets(
                execution_mode=execution_mode,
                plan=plan,
                targets=targets,
            )
            controls.append(
                {
                    "control_id": control.control_id,
                    "title": control.title,
                    "evidence_query": control.evidence_query,
                    "applicability_status": applicability_status,
                    "plan_code": plan.plan_code if plan else "",
                    "plan_status": plan.lifecycle_status if plan else "missing",
                    "execution_mode": execution_mode,
                    "collector_key": plan.collector_key if plan else control.evidence_query,
                    "evidence_type": plan.evidence_type if plan else "",
                    "instructions": plan.instructions if plan else "",
                    "minimum_freshness_days": plan.minimum_freshness_days if plan else 30,
                    "targets": targets,
                }
            )
            if applicability_status in {"not_applicable", "inherited"}:
                continue
            for target in targets:
                profile_entry = profile_index.setdefault(
                    target["aws_profile"],
                    {
                        "aws_profile": target["aws_profile"],
                        "aws_account_ids": set(),
                        "regions": set(),
                        "controls": set(),
                        "target_codes": set(),
                        "login_command": f"aws sso login --profile {target['aws_profile']}",
                        "registered_in_app": target["aws_profile"] in profile_lookup,
                    },
                )
                if target["aws_account_id"]:
                    profile_entry["aws_account_ids"].add(target["aws_account_id"])
                for region_name in target["regions"]:
                    profile_entry["regions"].add(region_name)
                profile_entry["controls"].add(control.control_id)
                profile_entry["target_codes"].add(target["target_code"])

        profiles = [
            self._profile_plan_entry(item, profile_lookup.get(item["aws_profile"]))
            for item in sorted(profile_index.values(), key=lambda value: value["aws_profile"])
        ]
        return {
            "binding_code": binding_code,
            "framework_code": framework.code,
            "product_code": product_code,
            "product_flavor_code": product_flavor_code,
            "offline_mode": self._offline_mode_enabled(),
            "profiles": profiles,
            "missing_profile_metadata": [item["aws_profile"] for item in profiles if not item["registered_in_app"]],
            "controls": controls,
        }

    def _load_evidence_plans(self, framework_id: int, unified_control_ids: set[int]) -> list[EvidenceCollectionPlan]:
        query = select(EvidenceCollectionPlan).where(EvidenceCollectionPlan.lifecycle_status.not_in(["retired", "archived"]))
        query = query.where(
            (EvidenceCollectionPlan.framework_id == framework_id)
            | (
                EvidenceCollectionPlan.unified_control_id.in_(sorted(unified_control_ids))
                if unified_control_ids
                else false()
            )
        )
        return list(self.session.scalars(query))

    @staticmethod
    def _best_plan_for_control(
        framework_id: int,
        control_id: int,
        unified_control_id: int | None,
        evidence_plans: list[EvidenceCollectionPlan],
    ) -> EvidenceCollectionPlan | None:
        candidates = [
            item
            for item in evidence_plans
            if (item.framework_id == framework_id and item.control_id == control_id)
            or (unified_control_id is not None and item.unified_control_id == unified_control_id)
        ]
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda item: (
                0 if item.control_id == control_id else 1,
                0 if item.lifecycle_status in READY_PLAN_STATES else 1,
                -(item.updated_at.timestamp() if item.updated_at else 0.0),
            ),
            reverse=False,
        )[0]

    @staticmethod
    def _manual_collection_summary(
        control: Control,
        execution_mode: str,
        plan: EvidenceCollectionPlan,
        target_count: int,
    ) -> str:
        target_text = f" across {target_count} target(s)" if target_count else ""
        guidance = f" Guidance: {plan.instructions}" if plan.instructions else ""
        return (
            f"{execution_mode.title()} evidence is required for {control.control_id}{target_text}. "
            f"Use manual intake or guided collection to satisfy plan {plan.plan_code}.{guidance}"
        ).strip()

    @staticmethod
    def _normalize_collection_targets(
        execution_mode: str,
        plan: EvidenceCollectionPlan | None,
        targets: list[dict],
    ) -> list[dict]:
        if not targets:
            return []
        if execution_mode == "automated":
            return targets
        if all(item.get("source") == "binding_default" for item in targets) and (
            plan is None or plan.evidence_type == "manual_artifact"
        ):
            return []
        return targets

    @staticmethod
    def _profile_plan_entry(item: dict, profile: AwsCliProfile | None) -> dict:
        expected_accounts = sorted(item["aws_account_ids"])
        detected_account_id = profile.detected_account_id if profile else ""
        account_alignment = "unknown"
        if expected_accounts:
            if not detected_account_id:
                account_alignment = "unverified"
            elif detected_account_id in expected_accounts:
                account_alignment = "matched"
            else:
                account_alignment = "mismatch"

        return {
            "aws_profile": item["aws_profile"],
            "aws_account_ids": expected_accounts,
            "regions": sorted(item["regions"]),
            "controls": sorted(item["controls"]),
            "target_codes": sorted(item["target_codes"]),
            "login_command": item["login_command"],
            "registered_in_app": item["registered_in_app"],
            "last_validation_status": profile.last_validation_status if profile else "",
            "last_validated_at": profile.last_validated_at.isoformat() if profile and profile.last_validated_at else "",
            "detected_account_id": detected_account_id,
            "detected_arn": profile.detected_arn if profile else "",
            "account_alignment": account_alignment,
        }

    def _offline_mode_enabled(self) -> bool:
        if getattr(settings, "offline_mode", False):
            return True
        setting = self.session.scalar(
            select(SystemSetting).where(SystemSetting.setting_key == "runtime.offline_mode")
        )
        if setting is None:
            return False
        return setting.setting_value.strip().lower() in {"1", "true", "yes", "on"}

    def _resolve_collection_targets(
        self,
        framework_binding_id: int | None,
        organization_id: int | None,
        product_id: int | None,
        product_flavor_id: int | None,
        control: Control,
        default_aws_profile: str,
        default_aws_region: str,
        default_aws_account_id: str,
    ) -> list[dict]:
        default_target = {
            "target_code": f"DEFAULT_{control.id}",
            "name": "Binding default target",
            "aws_profile": default_aws_profile,
            "aws_account_id": default_aws_account_id,
            "role_name": "",
            "regions": [default_aws_region],
            "source": "binding_default",
        }
        if organization_id is None:
            return [default_target]

        mapped_unified_ids = [
            row.unified_control_id
            for row in self.session.scalars(
                select(UnifiedControlMapping)
                .where(
                    UnifiedControlMapping.control_id == control.id,
                    UnifiedControlMapping.approval_status == "approved",
                )
                .order_by(UnifiedControlMapping.confidence.desc())
            ).all()
            if row.unified_control_id is not None
        ]

        candidates = self.session.scalars(
            select(AwsEvidenceTarget).where(
                AwsEvidenceTarget.organization_id == organization_id,
                AwsEvidenceTarget.lifecycle_status == "active",
            )
        ).all()

        matched: list[tuple[int, AwsEvidenceTarget]] = []
        for candidate in candidates:
            specificity = self._target_specificity(
                target=candidate,
                framework_binding_id=framework_binding_id,
                product_id=product_id,
                product_flavor_id=product_flavor_id,
                control_id=control.id,
                unified_control_ids=mapped_unified_ids,
            )
            if specificity >= 0:
                matched.append((specificity, candidate))

        if not matched:
            return [default_target]

        best_score = max(score for score, _ in matched)
        resolved = [target for score, target in matched if score == best_score]
        return [
            {
                "target_code": item.target_code,
                "name": item.name,
                "aws_profile": item.aws_profile,
                "aws_account_id": item.aws_account_id,
                "role_name": item.role_name,
                "regions": self._parse_regions(item.regions_json, default_aws_region),
                "source": "aws_evidence_target",
            }
            for item in resolved
        ]

    @staticmethod
    def _target_specificity(
        target: AwsEvidenceTarget,
        framework_binding_id: int | None,
        product_id: int | None,
        product_flavor_id: int | None,
        control_id: int,
        unified_control_ids: list[int],
    ) -> int:
        score = 0
        if target.framework_binding_id is not None:
            if framework_binding_id is None or target.framework_binding_id != framework_binding_id:
                return -1
            score += 2
        if target.product_id is not None:
            if product_id is None or target.product_id != product_id:
                return -1
            score += 4
        if target.product_flavor_id is not None:
            if product_flavor_id is None or target.product_flavor_id != product_flavor_id:
                return -1
            score += 8
        if target.control_id is not None:
            if target.control_id != control_id:
                return -1
            score += 4
        if target.unified_control_id is not None:
            if target.unified_control_id not in unified_control_ids:
                return -1
            score += 2
        if target.is_primary:
            score += 1
        return score

    @staticmethod
    def _parse_regions(regions_json: str, default_region: str) -> list[str]:
        try:
            parsed = json.loads(regions_json or "[]")
        except json.JSONDecodeError:
            parsed = []
        regions = [str(item).strip() for item in parsed if str(item).strip()]
        return regions or [default_region]

    @staticmethod
    def _aggregate_target_results(target_results: list[dict]) -> tuple[str, str]:
        total = len(target_results)
        passed = sum(1 for item in target_results if item["status"] == "pass")
        failed = sum(1 for item in target_results if item["status"] == "fail")
        errored = sum(1 for item in target_results if item["status"] == "error")
        if failed:
            return "fail", f"{failed}/{total} target checks failed; {passed} passed, {errored} errored."
        if errored:
            return "error", f"{errored}/{total} target checks errored; {passed} passed."
        return "pass", f"All {passed}/{total} target checks passed."

    @staticmethod
    def latest_for_framework(
        framework_id: int,
        session,
        organization_id: int | None = None,
        product_id: int | None = None,
        product_flavor_id: int | None = None,
    ) -> list[EvidenceItem]:
        query = select(EvidenceItem).where(EvidenceItem.framework_id == framework_id)
        if organization_id is not None:
            query = query.where(EvidenceItem.organization_id == organization_id)
        if product_id is None and organization_id is not None:
            query = query.where(EvidenceItem.product_id.is_(None))
        elif product_id is not None:
            query = query.where(EvidenceItem.product_id == product_id)
        if product_flavor_id is None and product_id is not None:
            query = query.where(EvidenceItem.product_flavor_id.is_(None))
        elif product_flavor_id is not None:
            query = query.where(EvidenceItem.product_flavor_id == product_flavor_id)
        rows = session.scalars(query.order_by(EvidenceItem.collected_at.desc())).all()
        latest_by_control: dict[int, EvidenceItem] = {}
        for row in rows:
            latest_by_control.setdefault(row.control_id, row)
        latest = list(latest_by_control.values())
        for item in latest:
            _ = item.control
        return latest

    def decrypt_payload(self, evidence_item: EvidenceItem) -> dict:
        if evidence_item.payload_storage_mode == "aesgcm_v1":
            return self.vault.decrypt_json(evidence_item.payload_json)
        return json.loads(evidence_item.payload_json)

    def _resolve_applicability_profile(
        self,
        organization_id: int | None,
        product_id: int | None,
        product_flavor_id: int | None,
        control_id: int,
    ) -> ProductControlProfile | None:
        if organization_id is None or product_id is None:
            return None

        mapping = self.session.scalar(
            select(UnifiedControlMapping)
            .where(
                UnifiedControlMapping.control_id == control_id,
                UnifiedControlMapping.approval_status == "approved",
            )
            .order_by(UnifiedControlMapping.confidence.desc())
        )
        query = select(ProductControlProfile).where(
            ProductControlProfile.organization_id == organization_id,
            ProductControlProfile.product_id == product_id,
        )
        if product_flavor_id is not None:
            query = query.where(
                (ProductControlProfile.product_flavor_id == product_flavor_id)
                | ProductControlProfile.product_flavor_id.is_(None)
            )
        else:
            query = query.where(ProductControlProfile.product_flavor_id.is_(None))
        if mapping is not None:
            query = query.where(
                (ProductControlProfile.control_id == control_id)
                | (ProductControlProfile.unified_control_id == mapping.unified_control_id)
            )
        else:
            query = query.where(ProductControlProfile.control_id == control_id)
        return self.session.scalar(query.order_by(ProductControlProfile.product_flavor_id.desc(), ProductControlProfile.updated_at.desc()))

    @staticmethod
    def _evidence_body(framework: Framework, control: Control, status: str, summary: str, payload_json: str) -> str:
        escaped_payload = payload_json.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return (
            f"<h1>{framework.name} - {control.control_id}</h1>"
            f"<p><strong>Status:</strong> {status}</p>"
            f"<p><strong>Summary:</strong> {summary}</p>"
            f"<p><strong>Control:</strong> {control.title}</p>"
            f"<pre>{escaped_payload}</pre>"
        )
