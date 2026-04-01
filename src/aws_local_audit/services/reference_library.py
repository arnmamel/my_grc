from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from aws_local_audit.models import (
    ImportedRequirement,
    ImportedRequirementReference,
    ReferenceDocument,
    UnifiedControl,
    UnifiedControlReference,
)
from aws_local_audit.services.lifecycle import LifecycleService


def _normalize_key(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in (value or "").strip().upper())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


class ReferenceLibraryService:
    def __init__(self, session):
        self.session = session
        self.lifecycle = LifecycleService(session)

    def upsert_reference_document(
        self,
        *,
        document_key: str,
        name: str,
        short_name: str = "",
        version: str = "",
        issuing_body: str = "",
        document_type: str = "reference",
        jurisdiction: str = "global",
        citation_format: str = "",
        source_url: str = "",
        notes: str = "",
        actor: str = "reference_library",
    ) -> tuple[ReferenceDocument, bool]:
        normalized_key = _normalize_key(document_key or name)
        document = self.session.scalar(
            select(ReferenceDocument).where(ReferenceDocument.document_key == normalized_key)
        )
        created = document is None
        if document is None:
            document = ReferenceDocument(document_key=normalized_key, name=name)
            self.session.add(document)
        document.name = name
        document.short_name = short_name or document.short_name or ""
        document.version = version or document.version or ""
        document.issuing_body = issuing_body or document.issuing_body or ""
        document.document_type = document_type or document.document_type or "reference"
        document.jurisdiction = jurisdiction or document.jurisdiction or "global"
        document.citation_format = citation_format or document.citation_format or ""
        document.source_url = source_url or document.source_url or ""
        document.notes = notes or document.notes or ""
        document.updated_at = datetime.utcnow()
        self.session.flush()
        if created:
            self.lifecycle.record_event(
                entity_type="reference_document",
                entity_id=document.id,
                lifecycle_name="framework_lifecycle",
                to_state=document.lifecycle_status,
                actor=actor,
                payload={"document_key": document.document_key, "document_type": document.document_type},
            )
        return document, created

    def link_imported_requirement(
        self,
        *,
        imported_requirement_id: int,
        document_key: str,
        document_name: str,
        reference_code: str = "",
        reference_text: str = "",
        relationship_type: str = "mapped_requirement",
        raw_value: str = "",
        short_name: str = "",
        version: str = "",
        issuing_body: str = "",
        document_type: str = "reference",
        jurisdiction: str = "global",
        citation_format: str = "",
        source_url: str = "",
        notes: str = "",
        actor: str = "reference_library",
    ) -> tuple[ImportedRequirementReference, bool, bool]:
        imported_requirement = self.session.get(ImportedRequirement, imported_requirement_id)
        if imported_requirement is None:
            raise ValueError(f"Imported requirement not found: {imported_requirement_id}")
        document, created_document = self.upsert_reference_document(
            document_key=document_key,
            name=document_name,
            short_name=short_name,
            version=version,
            issuing_body=issuing_body,
            document_type=document_type,
            jurisdiction=jurisdiction,
            citation_format=citation_format,
            source_url=source_url,
            notes=notes,
            actor=actor,
        )
        link = self.session.scalar(
            select(ImportedRequirementReference).where(
                ImportedRequirementReference.imported_requirement_id == imported_requirement.id,
                ImportedRequirementReference.reference_document_id == document.id,
                ImportedRequirementReference.reference_code == reference_code,
                ImportedRequirementReference.relationship_type == relationship_type,
            )
        )
        created_link = link is None
        if link is None:
            link = ImportedRequirementReference(
                imported_requirement_id=imported_requirement.id,
                reference_document_id=document.id,
                reference_code=reference_code,
                relationship_type=relationship_type,
            )
            self.session.add(link)
        link.reference_text = reference_text
        link.raw_value = raw_value
        self.session.flush()
        return link, created_document, created_link

    def link_unified_control(
        self,
        *,
        unified_control_id: int,
        document_key: str,
        document_name: str,
        reference_code: str = "",
        reference_text: str = "",
        relationship_type: str = "mapped_requirement",
        framework_id: int | None = None,
        control_id: int | None = None,
        imported_requirement_id: int | None = None,
        rationale: str = "",
        short_name: str = "",
        version: str = "",
        issuing_body: str = "",
        document_type: str = "reference",
        jurisdiction: str = "global",
        citation_format: str = "",
        source_url: str = "",
        notes: str = "",
        actor: str = "reference_library",
    ) -> tuple[UnifiedControlReference, bool, bool]:
        unified_control = self.session.get(UnifiedControl, unified_control_id)
        if unified_control is None:
            raise ValueError(f"Unified control not found: {unified_control_id}")
        document, created_document = self.upsert_reference_document(
            document_key=document_key,
            name=document_name,
            short_name=short_name,
            version=version,
            issuing_body=issuing_body,
            document_type=document_type,
            jurisdiction=jurisdiction,
            citation_format=citation_format,
            source_url=source_url,
            notes=notes,
            actor=actor,
        )
        link = self.session.scalar(
            select(UnifiedControlReference).where(
                UnifiedControlReference.unified_control_id == unified_control.id,
                UnifiedControlReference.reference_document_id == document.id,
                UnifiedControlReference.reference_code == reference_code,
                UnifiedControlReference.relationship_type == relationship_type,
            )
        )
        created_link = link is None
        if link is None:
            link = UnifiedControlReference(
                unified_control_id=unified_control.id,
                reference_document_id=document.id,
                reference_code=reference_code,
                relationship_type=relationship_type,
            )
            self.session.add(link)
        link.framework_id = framework_id
        link.control_id = control_id
        link.imported_requirement_id = imported_requirement_id
        link.reference_text = reference_text
        link.rationale = rationale
        self.session.flush()
        return link, created_document, created_link

    def list_reference_documents(self) -> list[ReferenceDocument]:
        return list(self.session.scalars(select(ReferenceDocument).order_by(ReferenceDocument.name)))
