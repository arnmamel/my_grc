from __future__ import annotations

import json

from aws_local_audit.collectors import COLLECTORS
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from aws_local_audit.framework_loader import load_template_by_code, load_templates
from aws_local_audit.models import AuthorityDocument, Control, ControlMetadata, EvidenceCollectionPlan, Framework
from aws_local_audit.services.lifecycle import LifecycleService


def _normalize_code(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.strip().upper())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


class FrameworkService:
    def __init__(self, session):
        self.session = session
        self.lifecycle = LifecycleService(session)

    def seed_templates(self) -> list[Framework]:
        touched = []
        for template in load_templates():
            framework = self._upsert_framework_from_template(template)
            touched.append(framework)
        self.seed_default_evidence_plans()
        return touched

    def list_frameworks(self) -> list[Framework]:
        query = select(Framework).options(
            selectinload(Framework.controls).selectinload(Control.metadata_entry)
        ).order_by(Framework.name)
        return list(self.session.scalars(query))

    def enable_framework(self, code: str, aws_profile: str, aws_region: str) -> Framework:
        framework = self._upsert_framework_from_template(load_template_by_code(code))
        previous = framework.lifecycle_status
        framework.active = True
        framework.lifecycle_status = "active"
        framework.aws_profile = aws_profile
        framework.aws_region = aws_region
        self.lifecycle.record_event(
            entity_type="framework",
            entity_id=framework.id,
            lifecycle_name="framework_lifecycle",
            from_state=previous,
            to_state=framework.lifecycle_status,
            actor="framework_service",
            payload={"aws_profile": aws_profile, "aws_region": aws_region},
        )
        return framework

    def disable_framework(self, code: str) -> Framework:
        framework = self.session.scalar(select(Framework).where(Framework.code == code))
        if framework is None:
            raise ValueError(f"Framework not found: {code}")
        previous = framework.lifecycle_status
        framework.active = False
        framework.lifecycle_status = "inactive"
        self.lifecycle.record_event(
            entity_type="framework",
            entity_id=framework.id,
            lifecycle_name="framework_lifecycle",
            from_state=previous,
            to_state=framework.lifecycle_status,
            actor="framework_service",
        )
        return framework

    def get_framework_by_code(self, code: str) -> Framework:
        framework = self.session.scalar(
            select(Framework).options(selectinload(Framework.controls)).where(Framework.code == code)
        )
        if framework is None:
            raise ValueError(f"Framework not found: {code}")
        return framework

    def create_framework_shell(
        self,
        code: str,
        name: str,
        version: str,
        category: str = "framework",
        description: str = "",
        authority_document_key: str | None = None,
        issuing_body: str = "",
        jurisdiction: str = "global",
        source_url: str = "",
        authority_notes: str = "",
        source: str = "manual",
        lifecycle_status: str = "draft",
    ) -> Framework:
        normalized_code = _normalize_code(code)
        authority_document = self._upsert_authority_document(
            {
                "code": normalized_code,
                "name": name,
                "version": version,
                "category": category,
                "issuing_body": issuing_body,
                "jurisdiction": jurisdiction,
                "source_url": source_url,
                "authority_notes": authority_notes,
                "authority_document_key": authority_document_key or normalized_code,
            }
        )
        framework = self.session.scalar(select(Framework).where(Framework.code == normalized_code))
        created = framework is None
        if framework is None:
            framework = Framework(
                authority_document_id=authority_document.id,
                code=normalized_code,
                name=name,
                version=version,
                category=category,
                description=description,
                source=source,
                active=False,
                lifecycle_status=lifecycle_status,
            )
            self.session.add(framework)
        else:
            framework.authority_document_id = authority_document.id
            framework.name = name
            framework.version = version
            framework.category = category
            framework.description = description
            framework.source = source
            framework.lifecycle_status = lifecycle_status
        self.session.flush()
        if created:
            self.lifecycle.record_event(
                entity_type="framework",
                entity_id=framework.id,
                lifecycle_name="framework_lifecycle",
                to_state=framework.lifecycle_status,
                actor="framework_service",
                payload={"source": source},
            )
        return framework

    def upsert_framework_control(
        self,
        framework_code: str,
        control_id: str,
        title: str,
        description: str = "",
        evidence_query: str = "manual_review",
        severity: str = "medium",
        summary: str = "",
        aws_guidance: str = "",
        check_type: str = "manual",
        boto3_check: str = "",
        boto3_services: list[str] | None = None,
        source_reference: str = "",
        notes: str = "",
    ) -> Control:
        framework = self.session.scalar(select(Framework).where(Framework.code == framework_code))
        if framework is None:
            raise ValueError(f"Framework not found: {framework_code}")

        normalized_control_id = control_id.strip()
        control = self.session.scalar(
            select(Control).where(Control.framework_id == framework.id, Control.control_id == normalized_control_id)
        )
        if control is None:
            control = Control(
                framework_id=framework.id,
                control_id=normalized_control_id,
                title=title,
                description=description,
                evidence_query=evidence_query,
                severity=severity,
            )
            self.session.add(control)
        else:
            control.title = title
            control.description = description
            control.evidence_query = evidence_query
            control.severity = severity

        metadata = control.metadata_entry
        if metadata is None:
            metadata = ControlMetadata(control=control)
            self.session.add(metadata)

        metadata.summary = summary
        metadata.aws_guidance = aws_guidance
        metadata.check_type = check_type
        metadata.boto3_check = boto3_check
        metadata.boto3_services_json = json.dumps(boto3_services or [])
        metadata.source_reference = source_reference
        metadata.notes = notes
        self.session.flush()
        self._upsert_default_plan_for_control(framework, control)
        return control

    def seed_default_evidence_plans(self, framework_code: str | None = None) -> int:
        query = select(Framework).options(selectinload(Framework.controls).selectinload(Control.metadata_entry))
        if framework_code:
            query = query.where(Framework.code == framework_code)
        frameworks = self.session.scalars(query).all()
        plan_count = 0
        for framework in frameworks:
            for control in framework.controls:
                self._upsert_default_plan_for_control(framework, control)
                plan_count += 1
        return plan_count

    def _upsert_framework_from_template(self, template: dict) -> Framework:
        authority_document = self._upsert_authority_document(template)
        framework = self.session.scalar(select(Framework).where(Framework.code == template["code"]))
        if framework is None:
            framework = Framework(
                authority_document_id=authority_document.id,
                code=template["code"],
                name=template["name"],
                version=template["version"],
                category=template.get("category", "framework"),
                description=template.get("description", ""),
                source="template",
                active=False,
                lifecycle_status="draft",
            )
            self.session.add(framework)
            self.session.flush()
            self.lifecycle.record_event(
                entity_type="framework",
                entity_id=framework.id,
                lifecycle_name="framework_lifecycle",
                to_state=framework.lifecycle_status,
                actor="framework_service",
                payload={"source": "template"},
            )
        else:
            framework.authority_document_id = authority_document.id
            framework.name = template["name"]
            framework.version = template["version"]
            framework.category = template.get("category", framework.category)
            framework.description = template.get("description", framework.description)

        existing_controls = {
            control.control_id: control
            for control in self.session.scalars(select(Control).where(Control.framework_id == framework.id)).all()
        }
        template_control_ids = {item["control_id"] for item in template.get("controls", [])}
        for item in template.get("controls", []):
            control = existing_controls.get(item["control_id"])
            if control is None:
                control = Control(
                    framework_id=framework.id,
                    control_id=item["control_id"],
                    title=item["title"],
                    description=item.get("description", ""),
                    evidence_query=item["evidence_query"],
                    severity=item.get("severity", "medium"),
                )
                self.session.add(control)
                self.session.flush()
                existing_controls[control.control_id] = control
            else:
                control.title = item["title"]
                control.description = item.get("description", control.description)
                control.evidence_query = item["evidence_query"]
                control.severity = item.get("severity", control.severity)

            metadata = control.metadata_entry
            if metadata is None:
                metadata = ControlMetadata(control_id=control.id)
                self.session.add(metadata)

            metadata.summary = item.get("summary", "")
            metadata.aws_guidance = item.get("aws_guidance", "")
            metadata.check_type = item.get("check_type", "manual")
            metadata.boto3_check = item.get("boto3_check", "")
            metadata.boto3_services_json = json.dumps(item.get("boto3_services", []))
            metadata.source_reference = item.get("source_reference", "")
            metadata.notes = item.get("notes", "")
            self._upsert_default_plan_for_control(framework, control)

        stale_control_ids = [control_id for control_id in existing_controls if control_id not in template_control_ids]
        for control_id in stale_control_ids:
            self.session.delete(existing_controls[control_id])

        return framework

    def _upsert_authority_document(self, template: dict) -> AuthorityDocument:
        document_key = template.get("authority_document_key") or template["code"]
        document = self.session.scalar(select(AuthorityDocument).where(AuthorityDocument.document_key == document_key))
        if document is None:
            document = AuthorityDocument(document_key=document_key, name=template["name"])
            self.session.add(document)
        document.name = template["name"]
        document.version = template["version"]
        document.category = template.get("category", "framework")
        document.issuing_body = template.get("issuing_body", "")
        document.jurisdiction = template.get("jurisdiction", "global")
        document.source_url = template.get("source_url", "")
        document.lifecycle_status = "published"
        document.notes = template.get("authority_notes", "")
        self.session.flush()
        return document

    def _upsert_default_plan_for_control(self, framework: Framework, control: Control) -> EvidenceCollectionPlan:
        metadata = control.metadata_entry
        automated = control.evidence_query in COLLECTORS
        execution_mode = "automated" if automated else "manual"
        evidence_type = "api_payload" if automated else "manual_artifact"
        review_frequency = "monthly" if automated else "quarterly"
        instructions = (
            (metadata.aws_guidance if metadata and metadata.aws_guidance else "")
            or (metadata.summary if metadata and metadata.summary else "")
            or control.description
            or f"Collect evidence for {control.control_id} ({control.title}) and review it against the control intent."
        )
        expected_artifacts = (
            ["encrypted_api_payload", "confluence_attachment"]
            if automated
            else ["supporting_document", "screenshot", "manual_attestation"]
        )
        plan_code = _normalize_code(f"PLAN_{framework.code}_{control.control_id}")
        plan = self.session.scalar(select(EvidenceCollectionPlan).where(EvidenceCollectionPlan.plan_code == plan_code))
        if plan is None:
            plan = EvidenceCollectionPlan(plan_code=plan_code, name=f"{framework.code} {control.control_id} evidence plan")
            self.session.add(plan)
        plan.framework_id = framework.id
        plan.control_id = control.id
        plan.scope_type = "binding"
        plan.execution_mode = execution_mode
        plan.collector_key = control.evidence_query if automated else ""
        plan.evidence_type = evidence_type
        plan.instructions = instructions
        plan.expected_artifacts_json = json.dumps(expected_artifacts)
        plan.review_frequency = review_frequency
        plan.minimum_freshness_days = 30 if automated else 90
        if plan.lifecycle_status in {"", "draft"}:
            plan.lifecycle_status = "ready"
        self.session.flush()
        return plan
