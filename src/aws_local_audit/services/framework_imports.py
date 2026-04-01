from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from aws_local_audit.models import (
    Control,
    Framework,
    FrameworkImportBatch,
    ImportedRequirement,
    ImportedRequirementReference,
    UnifiedControl,
)
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.frameworks import FrameworkService
from aws_local_audit.services.lifecycle import LifecycleService
from aws_local_audit.services.reference_library import ReferenceLibraryService
from aws_local_audit.services.suggestions import SuggestionService
from aws_local_audit.services.workbench import WorkbenchService


COLUMN_ALIASES = {
    "external_id": [
        "external_id",
        "id",
        "control_id",
        "control id",
        "code",
        "reference",
        "req_id",
        "requirement id",
        "ccm id",
        "specification id",
    ],
    "title": [
        "title",
        "name",
        "control",
        "control title",
        "control name",
        "requirement title",
        "objective",
    ],
    "description": [
        "description",
        "summary",
        "specification",
        "requirement",
        "details",
        "text",
        "question",
    ],
    "domain": ["domain", "control domain", "family", "pillar"],
    "family": ["subdomain", "sub-domain", "control family", "group", "category"],
    "section": ["section", "clause", "annex", "category", "control domain"],
    "source_reference": ["source_reference", "reference", "citation", "control id", "ccm id", "specification id"],
    "severity": ["severity", "priority", "impact"],
    "aws_guidance": ["aws_guidance", "aws guidance", "implementation guidance", "guidance"],
}

SCF_PIVOT_FRAMEWORK_CODE = "SCF_2025_3_1"
SCF_PIVOT_FRAMEWORK_NAME = "Secure Controls Framework"
SCF_PIVOT_FRAMEWORK_VERSION = "2025.3.1"
SCF_PIVOT_SHEET_NAME = "SCF 2025.3.1"
SCF_PIVOT_SOURCE_URL = "https://securecontrolsframework.com/"
SCF_PIVOT_COLUMN_MAPPING = {
    "external_id": "SCF #",
    "title": "SCF Control",
    "description": "Secure Controls Framework (SCF) Control Description",
    "domain": "SCF Domain",
    "family": "SCF Domain",
    "section": "SCF Domain",
    "source_reference": "SCF #",
    "aws_guidance": "",
}
SCF_ENRICHMENT_METADATA_COLUMNS = {
    "SCF Domain",
    "SCF Control",
    "SCF #",
    "Secure Controls Framework (SCF) Control Description",
    "Conformity Validation Cadence",
    "Evidence Request List (ERL) #",
    "SCF Control Question",
    "Relative Control Weighting",
}
SCF_SOLUTION_COLUMNS = (
    "Possible Solutions & Considerations for a Small-Sized Organization",
    "Possible Solutions & Considerations for a Medium-Sized Organization",
    "Possible Solutions & Considerations for a Large-Sized Organization",
)
SCF_REFERENCE_IGNORE_FRAGMENTS = (
    "possible solutions",
    "control question",
    "validation cadence",
    "relative control weighting",
    "evidence request list",
    "threat",
    "risk",
)


def _normalize_code(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.strip().upper())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


class FrameworkImportService:
    def __init__(self, session):
        self.session = session
        self.frameworks = FrameworkService(session)
        self.workbench = WorkbenchService(session)
        self.suggestions = SuggestionService(session)
        self.lifecycle = LifecycleService(session)
        self.governance = GovernanceService(session)
        self.reference_library = ReferenceLibraryService(session)

    def available_sheets(self, file_path: str) -> list[str]:
        path = Path(file_path)
        if path.suffix.lower() not in {".xlsx", ".xls"}:
            return []
        workbook = pd.ExcelFile(path)
        return list(workbook.sheet_names)

    def preview_source(
        self,
        file_path: str,
        sheet_name: str = "",
        column_mapping: dict[str, str] | None = None,
        limit: int = 25,
    ) -> dict:
        dataframe = self._read_dataframe(file_path=file_path, sheet_name=sheet_name or None)
        columns = [str(item) for item in dataframe.columns]
        resolved_mapping = self._resolve_column_mapping(columns, column_mapping)
        normalized_records = [
            self._normalize_record(index=index + 2, row=row, column_mapping=resolved_mapping)
            for index, row in enumerate(dataframe.to_dict(orient="records"))
        ]
        preview_rows = normalized_records[:limit]
        return {
            "row_count": len(normalized_records),
            "columns": columns,
            "column_mapping": resolved_mapping,
            "records": preview_rows,
            "unmapped_fields": [name for name, value in resolved_mapping.items() if not value],
        }

    def import_secure_controls_framework(
        self,
        *,
        file_path: str,
        actor: str = "scf_import_wizard",
        sheet_name: str = SCF_PIVOT_SHEET_NAME,
        mark_as_pivot: bool = True,
        mapping_mode: str = "create_baseline",
        auto_approve_mappings: bool = True,
        auto_mapping_threshold: float = 0.84,
        source_name: str = "",
        source_url: str = SCF_PIVOT_SOURCE_URL,
        source_version: str = SCF_PIVOT_FRAMEWORK_VERSION,
    ) -> dict:
        preview = self.preview_source(file_path=file_path, sheet_name=sheet_name)
        column_mapping = {}
        for logical_name, preferred in SCF_PIVOT_COLUMN_MAPPING.items():
            column_mapping[logical_name] = preferred if preferred in preview["columns"] else preview["column_mapping"].get(
                logical_name, ""
            )
        result = self.import_source(
            file_path=file_path,
            framework_code=SCF_PIVOT_FRAMEWORK_CODE,
            framework_name=SCF_PIVOT_FRAMEWORK_NAME,
            framework_version=SCF_PIVOT_FRAMEWORK_VERSION,
            source_name=source_name or Path(file_path).name,
            source_type=self._source_type_for_path(file_path),
            source_url=source_url,
            source_version=source_version,
            sheet_name=sheet_name,
            column_mapping=column_mapping,
            category="metaframework",
            description=(
                "Secure Controls Framework imported as the pivot baseline for converged control mapping, "
                "implementation guidance, and multi-standard traceability."
            ),
            issuing_body="Secure Controls Framework Council",
            jurisdiction="global",
            actor=actor,
            mapping_mode=mapping_mode,
            auto_mapping_threshold=auto_mapping_threshold,
            auto_approve_mappings=auto_approve_mappings,
            default_evidence_query="manual_review",
            default_check_type="hybrid",
            baseline_code_strategy="source_control_id",
            baseline_prefix="SCF",
            enrichment_preset="scf_2025_3_1",
        )
        if mark_as_pivot:
            self.governance.set_pivot_framework_code(
                SCF_PIVOT_FRAMEWORK_CODE,
                "Secure Controls Framework imported as the pivot baseline for converged control mapping.",
            )
        return result

    def import_source(
        self,
        *,
        file_path: str,
        framework_code: str,
        framework_name: str,
        framework_version: str,
        source_name: str = "",
        source_type: str = "",
        source_url: str = "",
        source_version: str = "",
        sheet_name: str = "",
        column_mapping: dict[str, str] | None = None,
        category: str = "framework",
        description: str = "",
        issuing_body: str = "",
        jurisdiction: str = "global",
        actor: str = "framework_import_service",
        mapping_mode: str = "suggest_only",
        suggestion_limit: int = 3,
        auto_mapping_threshold: float = 0.84,
        auto_approve_mappings: bool = False,
        default_evidence_query: str = "manual_review",
        default_check_type: str = "manual",
        baseline_code_strategy: str = "framework_prefixed",
        baseline_prefix: str = "",
        enrichment_preset: str = "",
    ) -> dict:
        if mapping_mode not in {"none", "suggest_only", "map_existing", "create_baseline"}:
            raise ValueError("mapping_mode must be one of: none, suggest_only, map_existing, create_baseline")

        preview = self.preview_source(
            file_path=file_path,
            sheet_name=sheet_name,
            column_mapping=column_mapping,
            limit=10_000,
        )
        framework = self.frameworks.create_framework_shell(
            code=framework_code,
            name=framework_name,
            version=framework_version,
            category=category,
            description=description,
            issuing_body=issuing_body,
            jurisdiction=jurisdiction,
            source_url=source_url,
            source="import",
            lifecycle_status="draft",
        )
        import_code = self._next_import_code(framework.code)
        batch = FrameworkImportBatch(
            framework_id=framework.id,
            import_code=import_code,
            name=f"{framework.code} import {datetime.utcnow():%Y-%m-%d %H:%M}",
            source_name=source_name or Path(file_path).name,
            source_type=source_type or self._source_type_for_path(file_path),
            source_version=source_version,
            source_url=source_url,
            file_name=Path(file_path).name,
            sheet_name=sheet_name,
            status="importing",
            initiated_by=actor,
            row_count=preview["row_count"],
            imported_count=0,
            column_mapping_json=json.dumps(preview["column_mapping"], indent=2),
        )
        self.session.add(batch)
        self.session.flush()

        dataframe = self._read_dataframe(file_path=file_path, sheet_name=sheet_name or None)
        raw_rows = [self._serialize_raw_row(row) for row in dataframe.to_dict(orient="records")]
        imported_rows = [
            self._normalize_record(index=index + 2, row=row, column_mapping=preview["column_mapping"])
            for index, row in enumerate(raw_rows)
        ]
        control_index = {
            item.control_id: item
            for item in self.session.scalars(select(Control).where(Control.framework_id == framework.id)).all()
        }

        created_unified_controls = 0
        created_mappings = 0
        captured_suggestions = 0
        created_reference_documents = 0
        created_reference_links = 0

        for record, raw_row in zip(imported_rows, raw_rows):
            control_id = record["external_id"] or self._generated_control_id(framework.code, record, record["row_number"])
            existing = control_index.get(control_id)
            control = self.frameworks.upsert_framework_control(
                framework_code=framework.code,
                control_id=control_id,
                title=record["title"] or control_id,
                description=record["description"],
                evidence_query=default_evidence_query,
                severity=record["severity"] or "medium",
                summary=record["description"] or record["title"],
                aws_guidance=record["aws_guidance"],
                check_type=default_check_type,
                source_reference=record["source_reference"] or record["section"] or record["domain"],
                notes=(
                    f"Imported from {batch.source_name or batch.file_name} "
                    f"row {record['row_number']} via batch {batch.import_code}."
                ),
            )
            control_index[control.control_id] = control
            imported_requirement = ImportedRequirement(
                import_batch_id=batch.id,
                framework_id=framework.id,
                control_id=control.id,
                external_id=control.control_id,
                title=record["title"],
                description=record["description"],
                source_domain=record["domain"],
                source_family=record["family"],
                source_section=record["section"],
                source_reference=record["source_reference"],
                source_hash=self._record_hash(record),
                row_number=record["row_number"],
                row_payload_json=json.dumps({"normalized": record, "raw": raw_row}, indent=2),
                import_action="updated_control" if existing else "created_control",
            )
            self.session.add(imported_requirement)
            batch.imported_count += 1

            if mapping_mode != "none":
                mapping_result = self._apply_mapping_strategy(
                    framework=framework,
                    control=control,
                    record=record,
                    actor=actor,
                    mapping_mode=mapping_mode,
                    suggestion_limit=suggestion_limit,
                    auto_mapping_threshold=auto_mapping_threshold,
                    auto_approve_mappings=auto_approve_mappings,
                    baseline_code_strategy=baseline_code_strategy,
                    baseline_prefix=baseline_prefix,
                )
                created_unified_controls += mapping_result["created_unified_controls"]
                created_mappings += mapping_result["created_mappings"]
                captured_suggestions += mapping_result["captured_suggestions"]
                enrichment = self._apply_import_enrichment(
                    preset=enrichment_preset,
                    framework=framework,
                    control=control,
                    record=record,
                    raw_row=raw_row,
                    imported_requirement=imported_requirement,
                    mapped_unified_control=mapping_result.get("mapped_unified_control"),
                    actor=actor,
                )
                created_reference_documents += enrichment["created_reference_documents"]
                created_reference_links += enrichment["created_reference_links"]
            elif enrichment_preset:
                enrichment = self._apply_import_enrichment(
                    preset=enrichment_preset,
                    framework=framework,
                    control=control,
                    record=record,
                    raw_row=raw_row,
                    imported_requirement=imported_requirement,
                    mapped_unified_control=None,
                    actor=actor,
                )
                created_reference_documents += enrichment["created_reference_documents"]
                created_reference_links += enrichment["created_reference_links"]

        batch.created_unified_controls = created_unified_controls
        batch.created_mappings = created_mappings
        batch.captured_suggestions = captured_suggestions
        batch.created_reference_documents = created_reference_documents
        batch.created_reference_links = created_reference_links
        batch.status = "imported"
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="framework_import_batch",
            entity_id=batch.id,
            lifecycle_name="framework_lifecycle",
            to_state=batch.status,
            actor=actor,
            payload={
                "framework": framework.code,
                "row_count": batch.row_count,
                "imported_count": batch.imported_count,
                "created_unified_controls": batch.created_unified_controls,
                "created_mappings": batch.created_mappings,
                "captured_suggestions": batch.captured_suggestions,
                "created_reference_documents": batch.created_reference_documents,
                "created_reference_links": batch.created_reference_links,
                "mapping_mode": mapping_mode,
            },
        )
        return {
            "framework": framework,
            "batch": batch,
            "summary": {
                "row_count": batch.row_count,
                "imported_count": batch.imported_count,
                "created_unified_controls": batch.created_unified_controls,
                "created_mappings": batch.created_mappings,
                "captured_suggestions": batch.captured_suggestions,
                "created_reference_documents": batch.created_reference_documents,
                "created_reference_links": batch.created_reference_links,
            },
        }

    def list_import_batches(self, framework_code: str | None = None) -> list[FrameworkImportBatch]:
        query = select(FrameworkImportBatch).options(selectinload(FrameworkImportBatch.framework)).order_by(
            FrameworkImportBatch.created_at.desc()
        )
        if framework_code:
            framework = self.session.scalar(select(Framework).where(Framework.code == framework_code))
            if framework is None:
                raise ValueError(f"Framework not found: {framework_code}")
            query = query.where(FrameworkImportBatch.framework_id == framework.id)
        return list(self.session.scalars(query))

    def traceability_rows(self, framework_code: str | None = None, limit: int = 200) -> list[dict]:
        query = (
            select(ImportedRequirement)
            .options(
                selectinload(ImportedRequirement.import_batch),
                selectinload(ImportedRequirement.framework),
                selectinload(ImportedRequirement.control).selectinload(Control.unified_mappings),
                selectinload(ImportedRequirement.reference_links).selectinload(
                    ImportedRequirementReference.reference_document
                ),
            )
            .order_by(ImportedRequirement.created_at.desc())
        )
        if framework_code:
            framework = self.session.scalar(select(Framework).where(Framework.code == framework_code))
            if framework is None:
                raise ValueError(f"Framework not found: {framework_code}")
            query = query.where(ImportedRequirement.framework_id == framework.id)
        rows = []
        for item in self.session.scalars(query.limit(limit)).all():
            mapped = []
            if item.control is not None:
                mapped = [
                    mapping.unified_control.code
                    for mapping in item.control.unified_mappings
                    if mapping.unified_control is not None
                ]
            rows.append(
                {
                    "framework": item.framework.code if item.framework else "",
                    "control_id": item.control.control_id if item.control else item.external_id,
                    "title": item.title,
                    "domain": item.source_domain,
                    "family": item.source_family,
                    "section": item.source_section,
                    "source_reference": item.source_reference,
                    "import_batch": item.import_batch.import_code if item.import_batch else "",
                    "import_action": item.import_action,
                    "mapped_unified_controls": mapped,
                    "reference_documents": [
                        link.reference_document.short_name or link.reference_document.name
                        for link in item.reference_links
                        if link.reference_document is not None
                    ],
                }
            )
        return rows

    def _apply_mapping_strategy(
        self,
        *,
        framework: Framework,
        control: Control,
        record: dict,
        actor: str,
        mapping_mode: str,
        suggestion_limit: int,
        auto_mapping_threshold: float,
        auto_approve_mappings: bool,
        baseline_code_strategy: str,
        baseline_prefix: str,
    ) -> dict:
        matches = self.suggestions.suggest_unified_control_matches([record], limit=suggestion_limit)[0]["matches"]
        top_match = matches[0] if matches else {}
        approval_status = "approved" if auto_approve_mappings else "proposed"
        created_unified_controls = 0
        created_mappings = 0
        captured_suggestions = 0
        mapped_unified_control = None

        if mapping_mode == "suggest_only":
            captured = self.suggestions.capture_mapping_suggestions_from_records(
                framework_code=framework.code,
                records=[record],
                limit=suggestion_limit,
            )
            return {
                "created_unified_controls": 0,
                "created_mappings": 0,
                "captured_suggestions": len(captured),
                "mapped_unified_control": None,
            }

        if top_match and float(top_match.get("score", 0.0)) >= auto_mapping_threshold:
            self.workbench.map_framework_control(
                unified_control_code=top_match["unified_control_code"],
                framework_code=framework.code,
                control_id=control.control_id,
                mapping_type="mapped",
                rationale=top_match.get("rationale", "Imported from external framework source."),
                confidence=float(top_match.get("score", 0.0)),
                approval_status=approval_status,
                reviewed_by=actor,
                approval_notes=f"Imported from external source for {framework.code} {control.control_id}.",
            )
            mapped_unified_control = self.session.scalar(
                select(UnifiedControl).where(UnifiedControl.code == top_match["unified_control_code"])
            )
            created_mappings = 1
            return {
                "created_unified_controls": 0,
                "created_mappings": created_mappings,
                "captured_suggestions": 0,
                "mapped_unified_control": mapped_unified_control,
            }

        if mapping_mode == "create_baseline":
            unified_control = self._create_unified_control_from_record(
                framework.code,
                control.control_id,
                record,
                baseline_code_strategy=baseline_code_strategy,
                baseline_prefix=baseline_prefix,
            )
            self.workbench.map_framework_control(
                unified_control_code=unified_control.code,
                framework_code=framework.code,
                control_id=control.control_id,
                mapping_type="mapped",
                rationale="Created from imported framework requirement to extend the unified-control baseline.",
                confidence=1.0,
                approval_status=approval_status,
                reviewed_by=actor,
                approval_notes=f"Imported baseline control created from {framework.code} {control.control_id}.",
            )
            created_unified_controls = 1
            created_mappings = 1
            return {
                "created_unified_controls": created_unified_controls,
                "created_mappings": created_mappings,
                "captured_suggestions": 0,
                "mapped_unified_control": unified_control,
            }

        captured = self.suggestions.capture_mapping_suggestions_from_records(
            framework_code=framework.code,
            records=[record],
            limit=suggestion_limit,
        )
        captured_suggestions = len(captured)
        return {
            "created_unified_controls": 0,
            "created_mappings": 0,
            "captured_suggestions": captured_suggestions,
            "mapped_unified_control": None,
        }

    def _create_unified_control_from_record(
        self,
        framework_code: str,
        control_id: str,
        record: dict,
        *,
        baseline_code_strategy: str = "framework_prefixed",
        baseline_prefix: str = "",
    ) -> UnifiedControl:
        if baseline_code_strategy == "source_control_id":
            prefix = baseline_prefix or framework_code
            base_code = _normalize_code(f"{prefix}_{control_id}")
        else:
            base_code = _normalize_code(f"UCF_{framework_code}_{control_id}")
        code = base_code
        sequence = 2
        while self.session.scalar(select(UnifiedControl).where(UnifiedControl.code == code)) is not None:
            code = f"{base_code}_{sequence}"
            sequence += 1
        return self.workbench.create_unified_control(
            code=code,
            name=record["title"] or control_id,
            description=record["description"],
            domain=record["domain"],
            family=record["family"],
            control_type="baseline",
            implementation_guidance=(
                f"Baseline control imported from {framework_code} requirement {control_id}. "
                "Complete organization-specific implementation details in the workbench."
            ),
            test_guidance=(
                "Define governed evidence plans, scope-specific AWS targets, and review expectations "
                "before marking this control autonomous."
            ),
        )

    def _apply_import_enrichment(
        self,
        *,
        preset: str,
        framework: Framework,
        control: Control,
        record: dict,
        raw_row: dict,
        imported_requirement: ImportedRequirement,
        mapped_unified_control: UnifiedControl | None,
        actor: str,
    ) -> dict[str, int]:
        if preset != "scf_2025_3_1":
            return {"created_reference_documents": 0, "created_reference_links": 0}
        return self._apply_scf_enrichment(
            framework=framework,
            control=control,
            record=record,
            raw_row=raw_row,
            imported_requirement=imported_requirement,
            mapped_unified_control=mapped_unified_control,
            actor=actor,
        )

    def _apply_scf_enrichment(
        self,
        *,
        framework: Framework,
        control: Control,
        record: dict,
        raw_row: dict,
        imported_requirement: ImportedRequirement,
        mapped_unified_control: UnifiedControl | None,
        actor: str,
    ) -> dict[str, int]:
        metadata = control.metadata_entry
        cadence = _cell(raw_row.get("Conformity Validation Cadence", ""))
        erl_reference = _cell(raw_row.get("Evidence Request List (ERL) #", ""))
        control_question = _cell(raw_row.get("SCF Control Question", ""))
        weighting = _cell(raw_row.get("Relative Control Weighting", ""))
        solution_guidance = self._scf_solution_guidance(raw_row)

        note_lines = [
            line
            for line in [
                f"SCF validation cadence: {cadence}" if cadence else "",
                f"SCF evidence request list reference: {erl_reference}" if erl_reference else "",
                f"SCF relative control weighting: {weighting}" if weighting else "",
                f"SCF control question: {control_question}" if control_question else "",
                solution_guidance,
            ]
            if line
        ]
        if metadata is not None and note_lines:
            metadata.notes = self._merge_text(metadata.notes, "\n".join(note_lines))
            metadata.summary = metadata.summary or record["description"] or record["title"]
            if solution_guidance and not metadata.aws_guidance:
                metadata.aws_guidance = solution_guidance

        if mapped_unified_control is not None:
            mapped_unified_control.implementation_guidance = self._merge_text(
                mapped_unified_control.implementation_guidance,
                solution_guidance or "Imported from the Secure Controls Framework implementation guidance columns.",
            )
            mapped_unified_control.test_guidance = self._merge_text(
                mapped_unified_control.test_guidance,
                "\n".join(
                    line
                    for line in [
                        f"Assessment prompt: {control_question}" if control_question else "",
                        f"Validation cadence: {cadence}" if cadence else "",
                        f"Evidence request list reference: {erl_reference}" if erl_reference else "",
                    ]
                    if line
                ),
            )

        created_reference_documents = 0
        created_reference_links = 0
        for reference in self._scf_reference_entries(raw_row):
            for reference_code in self._split_reference_codes(reference["raw_value"]):
                _, doc_created, link_created = self.reference_library.link_imported_requirement(
                    imported_requirement_id=imported_requirement.id,
                    document_key=reference["document_key"],
                    document_name=reference["document_name"],
                    reference_code=reference_code,
                    reference_text=reference["raw_value"],
                    relationship_type=reference["relationship_type"],
                    raw_value=reference["raw_value"],
                    short_name=reference["short_name"],
                    version=reference["version"],
                    issuing_body=reference["issuing_body"],
                    document_type=reference["document_type"],
                    jurisdiction=reference["jurisdiction"],
                    citation_format=reference["column_name"],
                    source_url=reference["source_url"],
                    notes="Imported from the Secure Controls Framework authoritative mapping columns.",
                    actor=actor,
                )
                created_reference_documents += 1 if doc_created else 0
                created_reference_links += 1 if link_created else 0
                if mapped_unified_control is not None:
                    _, doc_created, uc_link_created = self.reference_library.link_unified_control(
                        unified_control_id=mapped_unified_control.id,
                        document_key=reference["document_key"],
                        document_name=reference["document_name"],
                        reference_code=reference_code,
                        reference_text=reference["raw_value"],
                        relationship_type="implementation_reference",
                        framework_id=framework.id,
                        control_id=control.id,
                        imported_requirement_id=imported_requirement.id,
                        rationale=(
                            f"Imported from SCF authoritative-source column `{reference['column_name']}` "
                            f"for {control.control_id}."
                        ),
                        short_name=reference["short_name"],
                        version=reference["version"],
                        issuing_body=reference["issuing_body"],
                        document_type=reference["document_type"],
                        jurisdiction=reference["jurisdiction"],
                        citation_format=reference["column_name"],
                        source_url=reference["source_url"],
                        notes="Mirrored from the imported SCF requirement into the pivot unified-control baseline.",
                        actor=actor,
                    )
                    created_reference_documents += 1 if doc_created else 0
                    created_reference_links += 1 if uc_link_created else 0
        self.session.flush()
        return {
            "created_reference_documents": created_reference_documents,
            "created_reference_links": created_reference_links,
        }

    def _scf_reference_entries(self, raw_row: dict) -> list[dict]:
        entries = []
        for column_name, raw_value in raw_row.items():
            if not self._is_scf_reference_column(column_name):
                continue
            cell_value = _cell(raw_value)
            if not cell_value:
                continue
            entries.append(self._reference_document_metadata(column_name, cell_value))
        return entries

    def _is_scf_reference_column(self, column_name: str) -> bool:
        lowered = column_name.strip().lower()
        if not lowered or lowered.startswith("unnamed:"):
            return False
        if column_name in SCF_ENRICHMENT_METADATA_COLUMNS or column_name in SCF_SOLUTION_COLUMNS:
            return False
        if any(fragment in lowered for fragment in SCF_REFERENCE_IGNORE_FRAGMENTS):
            return False
        return True

    def _reference_document_metadata(self, column_name: str, raw_value: str) -> dict:
        normalized_name = " ".join(column_name.replace("_", " ").split())
        lowered = normalized_name.lower()
        issuing_body = "External Source"
        document_type = "reference"
        jurisdiction = "global"
        source_url = ""
        short_name = normalized_name
        version = ""

        if "nist" in lowered:
            issuing_body = "NIST"
            source_url = "https://csrc.nist.gov/publications"
            document_type = "framework" if "csf" in lowered else "guide"
            short_name = normalized_name.replace("revision", "rev").replace("Revision", "rev")
        elif "ccn" in lowered or "stic" in lowered:
            issuing_body = "CCN-CERT"
            document_type = "implementation_guide"
            jurisdiction = "spain"
            source_url = "https://www.ccn-cert.cni.es/"
        elif "csa" in lowered or "cloud security alliance" in lowered:
            issuing_body = "Cloud Security Alliance"
            document_type = "framework"
            source_url = "https://cloudsecurityalliance.org/"
        elif "iso" in lowered or "iec" in lowered:
            issuing_body = "ISO/IEC"
            document_type = "framework"
            source_url = "https://www.iso.org/"
        elif "cis" in lowered:
            issuing_body = "Center for Internet Security"
            document_type = "guide"
        elif "cobit" in lowered:
            issuing_body = "ISACA"
            document_type = "framework"
        elif "pci" in lowered:
            issuing_body = "PCI Security Standards Council"
            document_type = "framework"
        elif "soc 2" in lowered or "aicpa" in lowered:
            issuing_body = "AICPA"
            document_type = "framework"
        elif "hipaa" in lowered or "hhs" in lowered:
            issuing_body = "U.S. HHS"
            document_type = "regulation"
            jurisdiction = "united_states"
        elif "gdpr" in lowered or "european union" in lowered:
            issuing_body = "European Union"
            document_type = "regulation"
            jurisdiction = "eu"
        elif "scf" in lowered:
            issuing_body = "Secure Controls Framework Council"
            document_type = "framework"
            source_url = SCF_PIVOT_SOURCE_URL

        return {
            "column_name": column_name,
            "document_key": f"REF_{_normalize_code(normalized_name)}",
            "document_name": normalized_name,
            "short_name": short_name,
            "version": version,
            "issuing_body": issuing_body,
            "document_type": document_type,
            "jurisdiction": jurisdiction,
            "relationship_type": "mapped_requirement",
            "raw_value": raw_value,
            "source_url": source_url,
        }

    def _scf_solution_guidance(self, raw_row: dict) -> str:
        sections = []
        labels = {
            "Possible Solutions & Considerations for a Small-Sized Organization": "Small organization guidance",
            "Possible Solutions & Considerations for a Medium-Sized Organization": "Medium organization guidance",
            "Possible Solutions & Considerations for a Large-Sized Organization": "Large organization guidance",
        }
        for column_name in SCF_SOLUTION_COLUMNS:
            text = _cell(raw_row.get(column_name, ""))
            if text:
                sections.append(f"{labels[column_name]}: {text}")
        return "\n".join(sections)

    @staticmethod
    def _split_reference_codes(raw_value: str) -> list[str]:
        flattened = raw_value.replace("\r", "\n").replace("|", "\n")
        values = []
        for line in flattened.split("\n"):
            for token in line.split(";"):
                cleaned = token.strip(" ,")
                if not cleaned or cleaned.lower() in {"n/a", "na", "-"}:
                    continue
                values.append(cleaned)
        deduped = []
        seen = set()
        for item in values or [raw_value.strip()]:
            if not item or item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    @staticmethod
    def _merge_text(existing: str, addition: str) -> str:
        base = (existing or "").strip()
        extra = (addition or "").strip()
        if not extra:
            return base
        if not base:
            return extra
        if extra in base:
            return base
        return f"{base}\n{extra}"

    def _next_import_code(self, framework_code: str) -> str:
        return _normalize_code(f"IMPORT_{framework_code}_{datetime.utcnow():%Y%m%d_%H%M%S}")

    def _generated_control_id(self, framework_code: str, record: dict, row_number: int) -> str:
        seed = record["title"] or record["description"] or f"ROW_{row_number}"
        return _normalize_code(f"{framework_code}_{seed}")[:100]

    @staticmethod
    def _record_hash(record: dict) -> str:
        normalized = json.dumps(record, sort_keys=True)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _read_dataframe(self, *, file_path: str, sheet_name: str | None) -> pd.DataFrame:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            dataframe = pd.read_excel(path, sheet_name=sheet_name or 0).fillna("")
        else:
            dataframe = pd.read_csv(path).fillna("")
        if dataframe.empty:
            raise ValueError("The selected source file does not contain any rows.")
        dataframe.columns = [str(item).strip() for item in dataframe.columns]
        return dataframe

    @staticmethod
    def _serialize_raw_row(row: dict) -> dict[str, str]:
        return {str(key).strip(): _cell(value) for key, value in row.items()}

    def _resolve_column_mapping(self, columns: list[str], provided: dict[str, str] | None) -> dict[str, str]:
        lowered = {column.lower(): column for column in columns}
        resolved = {}
        for logical_name, aliases in COLUMN_ALIASES.items():
            explicit = (provided or {}).get(logical_name, "").strip()
            if explicit and explicit in columns:
                resolved[logical_name] = explicit
                continue
            resolved[logical_name] = next((lowered[name] for name in aliases if name in lowered), "")
        return resolved

    def _normalize_record(self, *, index: int, row: dict, column_mapping: dict[str, str]) -> dict:
        normalized = {
            "row_number": index,
            "external_id": _cell(row.get(column_mapping.get("external_id", ""), "")),
            "title": _cell(row.get(column_mapping.get("title", ""), "")),
            "description": _cell(row.get(column_mapping.get("description", ""), "")),
            "domain": _cell(row.get(column_mapping.get("domain", ""), "")),
            "family": _cell(row.get(column_mapping.get("family", ""), "")),
            "section": _cell(row.get(column_mapping.get("section", ""), "")),
            "source_reference": _cell(row.get(column_mapping.get("source_reference", ""), "")),
            "severity": _cell(row.get(column_mapping.get("severity", ""), "")).lower(),
            "aws_guidance": _cell(row.get(column_mapping.get("aws_guidance", ""), "")),
        }
        normalized["severity"] = normalized["severity"] if normalized["severity"] in {"low", "medium", "high", "critical"} else "medium"
        if not normalized["source_reference"]:
            normalized["source_reference"] = normalized["external_id"]
        return normalized

    @staticmethod
    def _source_type_for_path(file_path: str) -> str:
        suffix = Path(file_path).suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            return "xlsx"
        if suffix == ".csv":
            return "csv"
        return "file"
