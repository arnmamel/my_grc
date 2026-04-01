from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from aws_local_audit.models import (
    AwsEvidenceTarget,
    Control,
    EvidenceCollectionPlan,
    Framework,
    ImportedRequirement,
    OrganizationFrameworkBinding,
    Product,
    ProductControlProfile,
    UnifiedControl,
    UnifiedControlMapping,
)
from aws_local_audit.services.control_matrix import ControlMatrixService
from aws_local_audit.services.frameworks import FrameworkService
from aws_local_audit.services.workbench import WorkbenchService


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _as_int(value, default: int) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _as_float(value, default: float) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _normalized_code(*parts: str) -> str:
    tokens: list[str] = []
    for part in parts:
        text = _text(part)
        if not text:
            continue
        cleaned = "".join(character if character.isalnum() else "_" for character in text.upper())
        cleaned = "_".join(segment for segment in cleaned.split("_") if segment)
        if cleaned:
            tokens.append(cleaned)
    return "_".join(tokens)


class ControlStudioWorkbookService:
    def __init__(self, session):
        self.session = session
        self.matrix = ControlMatrixService(session)
        self.workbench = WorkbenchService(session)
        self.frameworks = FrameworkService(session)

    def control_register_rows(
        self,
        *,
        organization_code: str | None = None,
        product_code: str | None = None,
        comparison_scope_keys: list[str] | None = None,
        framework_codes: list[str] | None = None,
        search: str = "",
    ) -> list[dict]:
        rows = self.matrix.matrix_rows(
            organization_code=organization_code,
            product_code=product_code,
            comparison_scope_keys=comparison_scope_keys,
            framework_codes=framework_codes,
            search=search,
        )
        target_lookup = self._target_lookup(organization_code=organization_code, product_code=product_code)

        workbook_rows: list[dict] = []
        for row in rows:
            implementation = row.get("_implementation")
            profile = row.get("_scope_profile")
            plan = row.get("_plan")
            target = target_lookup.get(row["SCF Control"])
            workbook_row = {
                "SCF Control": row["SCF Control"],
                "Control Name": row["Control Name"],
                "Domain": row["Domain"],
                "Family": row["Family"],
                "Requirement Coverage Summary": row.get("Requirement Coverage Summary", ""),
                "Implementation Guidance": row.get("Implementation Guidance", ""),
                "Test Guidance": row.get("Test Guidance", ""),
                "Control Type": row.get("Control Type", ""),
                "Default Severity": row.get("Default Severity", ""),
                "Mapped Standards": row["Mapped Standards"],
                "Mapped Requirements": row["Mapped Requirements"],
                "SoA": row["SoA"],
                "SoA Rationale": row["SoA Rationale"],
                "Implementation Status": row["Implementation"],
                "Assessment Mode": row["Assessment Mode"] or (profile.assessment_mode if profile else "manual"),
                "Implementation Narrative": implementation.impl_general if implementation else "",
                "AWS Narrative": implementation.impl_aws if implementation else "",
                "Testing Plan": implementation.test_plan if implementation else "",
                "Evidence Strategy": profile.evidence_strategy if profile else "",
                "Owner": implementation.owner if implementation else "",
                "Lifecycle": implementation.lifecycle if implementation else "design",
                "Priority": implementation.priority if implementation else "medium",
                "Maturity Governance": profile.maturity_governance if profile else 3,
                "Maturity Implementation": profile.maturity_implementation if profile else 3,
                "Maturity Observability": profile.maturity_observability if profile else 2,
                "Maturity Automation": profile.maturity_automation if profile else 2,
                "Maturity Assurance": profile.maturity_assurance if profile else 2,
                "Current Evidence Plan": plan.plan_code if plan else "",
                "Current AWS Target": target.target_code if target else "",
                "Scope Flavor": (
                    implementation.product_flavor.code
                    if implementation and implementation.product_flavor is not None
                    else (
                        profile.product_flavor.code
                        if profile and profile.product_flavor is not None
                        else ""
                    )
                ),
            }
            for key, value in row.items():
                if key.endswith(" SoA") or key.endswith(" Impl"):
                    workbook_row[key] = value
            workbook_rows.append(workbook_row)
        return workbook_rows

    def mapping_rows(self, *, framework_codes: list[str] | None = None, search: str = "") -> list[dict]:
        query = (
            select(UnifiedControlMapping)
            .options(
                selectinload(UnifiedControlMapping.unified_control),
                selectinload(UnifiedControlMapping.framework),
                selectinload(UnifiedControlMapping.control),
            )
            .order_by(UnifiedControlMapping.created_at.desc())
        )
        mappings = self.session.scalars(query).all()
        rows = []
        query_text = search.strip().lower()
        for mapping in mappings:
            if framework_codes and mapping.framework.code not in framework_codes:
                continue
            row = {
                "SCF Control": mapping.unified_control.code if mapping.unified_control else "",
                "SCF Name": mapping.unified_control.name if mapping.unified_control else "",
                "Framework": mapping.framework.code if mapping.framework else "",
                "Requirement": mapping.control.control_id if mapping.control else "",
                "Requirement Title": mapping.control.title if mapping.control else "",
                "Mapping Status": mapping.approval_status,
                "Mapping Type": mapping.mapping_type,
                "Confidence": mapping.confidence,
                "Inheritance Strategy": mapping.inheritance_strategy,
                "Rationale": mapping.rationale,
                "Reviewed By": mapping.reviewed_by,
                "Approval Notes": mapping.approval_notes,
            }
            if query_text and query_text not in " ".join(str(item).lower() for item in row.values()):
                continue
            rows.append(row)
        return rows

    def testing_rows(
        self,
        *,
        organization_code: str | None = None,
        product_code: str | None = None,
        framework_codes: list[str] | None = None,
        search: str = "",
    ) -> list[dict]:
        register_rows = self.control_register_rows(
            organization_code=organization_code,
            product_code=product_code,
            framework_codes=framework_codes,
            search=search,
        )
        target_lookup = self._target_lookup(organization_code=organization_code, product_code=product_code)
        binding_codes = self._binding_codes(organization_code)
        plan_lookup = {
            plan.unified_control.code: plan
            for plan in self.session.scalars(
                select(EvidenceCollectionPlan)
                .options(selectinload(EvidenceCollectionPlan.unified_control))
                .where(EvidenceCollectionPlan.unified_control_id.is_not(None))
                .order_by(EvidenceCollectionPlan.updated_at.desc())
            ).all()
            if plan.unified_control is not None
        }

        rows: list[dict] = []
        for row in register_rows:
            code = row["SCF Control"]
            plan = plan_lookup.get(code)
            target = target_lookup.get(code)
            rows.append(
                {
                    "SCF Control": code,
                    "Control Name": row["Control Name"],
                    "Scope Flavor": row.get("Scope Flavor", ""),
                    "Plan Code": plan.plan_code if plan else _normalized_code(organization_code, product_code, code, "PLAN"),
                    "Binding": target.framework_binding.binding_code if target and target.framework_binding else (binding_codes[0] if binding_codes else ""),
                    "Plan Name": plan.name if plan else f"{code} testing plan",
                    "Plan Status": plan.lifecycle_status if plan else "draft",
                    "Execution Mode": plan.execution_mode if plan else "manual",
                    "Evidence Type": plan.evidence_type if plan else "manual_artifact",
                    "Collector Key": plan.collector_key if plan else "",
                    "Review Frequency": plan.review_frequency if plan else "quarterly",
                    "Evidence Strategy": row.get("Evidence Strategy", ""),
                    "Implementation Test Plan": row.get("Testing Plan", ""),
                    "Instructions": plan.instructions if plan else "",
                    "Expected Artifacts JSON": plan.expected_artifacts_json if plan else "[]",
                    "Target Code": target.target_code if target else _normalized_code(organization_code, product_code, code, "TARGET"),
                    "AWS Profile": target.aws_profile if target else "",
                    "AWS Account ID": target.aws_account_id if target else "",
                    "AWS Role": target.role_name if target else "",
                    "AWS Regions": self._regions_text(target.regions_json if target else "[]"),
                    "Target Status": target.lifecycle_status if target else "active",
                    "Target Notes": target.notes if target else "",
                }
            )
        return rows

    def framework_rows(self) -> list[dict]:
        frameworks = self.frameworks.list_frameworks()
        rows: list[dict] = []
        for framework in frameworks:
            authority_document = getattr(framework, "authority_document", None)
            rows.append(
                {
                    "Framework": framework.code,
                    "Name": framework.name,
                    "Version": framework.version,
                    "Category": framework.category,
                    "Issuing Body": getattr(framework, "issuing_body", "") or (authority_document.issuing_body if authority_document else ""),
                    "Jurisdiction": getattr(framework, "jurisdiction", "") or (authority_document.jurisdiction if authority_document else ""),
                    "Source URL": getattr(framework, "source_url", "") or (authority_document.source_url if authority_document else ""),
                    "Description": framework.description,
                    "Lifecycle": framework.lifecycle_status,
                    "Controls": len(framework.controls),
                }
            )
        return rows

    def imported_requirement_rows(
        self,
        *,
        framework_codes: list[str] | None = None,
        search: str = "",
    ) -> list[dict]:
        requirements = self.session.scalars(
            select(ImportedRequirement)
            .options(
                selectinload(ImportedRequirement.framework),
                selectinload(ImportedRequirement.control),
            )
            .order_by(ImportedRequirement.updated_at.desc())
        ).all()
        query_text = search.strip().lower()
        rows = []
        for item in requirements:
            if framework_codes and item.framework.code not in framework_codes:
                continue
            row = {
                "Framework": item.framework.code if item.framework else "",
                "Requirement": item.external_id,
                "Title": item.title,
                "Description": item.description,
                "Source Domain": item.source_domain,
                "Source Family": item.source_family,
                "Source Section": item.source_section,
                "Source Reference": item.source_reference,
                "Row Number": item.row_number,
                "Import Action": item.import_action,
            }
            if query_text and query_text not in " ".join(str(value).lower() for value in row.values()):
                continue
            rows.append(row)
        return rows

    def export_workbook_bytes(
        self,
        *,
        organization_code: str | None = None,
        product_code: str | None = None,
        comparison_scope_keys: list[str] | None = None,
        framework_codes: list[str] | None = None,
        search: str = "",
    ) -> bytes:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame(
                self.control_register_rows(
                    organization_code=organization_code,
                    product_code=product_code,
                    comparison_scope_keys=comparison_scope_keys,
                    framework_codes=framework_codes,
                    search=search,
                )
            ).to_excel(writer, sheet_name="Control Register", index=False)
            pd.DataFrame(self.mapping_rows(framework_codes=framework_codes, search=search)).to_excel(
                writer, sheet_name="Mappings", index=False
            )
            pd.DataFrame(
                self.testing_rows(
                    organization_code=organization_code,
                    product_code=product_code,
                    framework_codes=framework_codes,
                    search=search,
                )
            ).to_excel(writer, sheet_name="Testing", index=False)
            pd.DataFrame(self.framework_rows()).to_excel(writer, sheet_name="Frameworks", index=False)
            pd.DataFrame(self.imported_requirement_rows(framework_codes=framework_codes, search=search)).to_excel(
                writer, sheet_name="Imported Requirements", index=False
            )
        return buffer.getvalue()

    def read_rows_from_file(self, file_path: str, sheet_name: str = "") -> list[dict]:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            dataframe = pd.read_csv(path, dtype=str).fillna("")
            return dataframe.to_dict(orient="records")
        if suffix in {".xlsx", ".xls"}:
            dataframe = pd.read_excel(path, sheet_name=sheet_name or 0, dtype=str).fillna("")
            return dataframe.to_dict(orient="records")
        raise ValueError(f"Unsupported file type: {suffix}")

    def apply_control_register_rows(
        self,
        rows: list[dict],
        *,
        organization_code: str | None = None,
        product_code: str | None = None,
    ) -> dict:
        updated = 0
        errors: list[str] = []
        current_rows = {
            row["SCF Control"]: row
            for row in self.control_register_rows(
                organization_code=organization_code,
                product_code=product_code,
            )
        }
        for row in rows:
            control_code = _text(row.get("SCF Control"))
            if not control_code:
                continue
            current = current_rows.get(control_code, {})
            scope_flavor_code = _text(row.get("Scope Flavor")) or _text(current.get("Scope Flavor"))
            try:
                self.workbench.create_unified_control(
                    code=control_code,
                    name=_text(row.get("Control Name")) or _text(current.get("Control Name")) or control_code,
                    description=_text(row.get("Requirement Coverage Summary") or row.get("Description")) or _text(current.get("Requirement Coverage Summary")),
                    domain=_text(row.get("Domain")) or _text(current.get("Domain")),
                    family=_text(row.get("Family")) or _text(current.get("Family")),
                    control_type=_text(row.get("Control Type")) or _text(current.get("Control Type")),
                    default_severity=_text(row.get("Default Severity")) or _text(current.get("Default Severity")) or "medium",
                    implementation_guidance=_text(row.get("Implementation Guidance") or row.get("Implementation Narrative")) or _text(current.get("Implementation Narrative")),
                    test_guidance=_text(row.get("Test Guidance") or row.get("Testing Plan")) or _text(current.get("Testing Plan")),
                )
                if organization_code and product_code:
                    implementation = self.workbench.upsert_control_implementation(
                        organization_code=organization_code,
                        product_code=product_code,
                        product_flavor_code=scope_flavor_code or None,
                        unified_control_code=control_code,
                        title=_text(row.get("Implementation Title")) or _text(row.get("Control Name")) or control_code,
                        owner=_text(row.get("Owner")),
                        status=_text(row.get("Implementation Status")) or "planned",
                        lifecycle=_text(row.get("Lifecycle")) or "design",
                        priority=_text(row.get("Priority")) or "medium",
                        objective=_text(row.get("Objective")),
                        impl_general=_text(row.get("Implementation Narrative")),
                        impl_aws=_text(row.get("AWS Narrative")),
                        test_plan=_text(row.get("Testing Plan")),
                        notes=_text(row.get("Notes")),
                    )
                    self.workbench.upsert_product_control_profile(
                        organization_code=organization_code,
                        product_code=product_code,
                        product_flavor_code=scope_flavor_code or None,
                        unified_control_code=control_code,
                        applicability_status=_text(row.get("SoA")) or "applicable",
                        implementation_status=_text(row.get("Implementation Status")) or "planned",
                        assessment_mode=_text(row.get("Assessment Mode")) or "manual",
                        maturity_governance=_as_int(row.get("Maturity Governance"), 3),
                        maturity_implementation=_as_int(row.get("Maturity Implementation"), 3),
                        maturity_observability=_as_int(row.get("Maturity Observability"), 2),
                        maturity_automation=_as_int(row.get("Maturity Automation"), 2),
                        maturity_assurance=_as_int(row.get("Maturity Assurance"), 2),
                        rationale=_text(row.get("SoA Rationale")),
                        evidence_strategy=_text(row.get("Evidence Strategy")) or _text(row.get("Testing Plan")),
                        review_notes=f"Updated from control register grid for {implementation.implementation_code}.",
                    )
                updated += 1
            except Exception as exc:
                errors.append(f"{control_code}: {exc}")
        self.session.flush()
        return {"updated_count": updated, "errors": errors}

    def apply_mapping_rows(self, rows: list[dict]) -> dict:
        updated = 0
        errors: list[str] = []
        for row in rows:
            control_code = _text(row.get("SCF Control"))
            framework_code = _text(row.get("Framework"))
            requirement = _text(row.get("Requirement"))
            if not control_code or not framework_code or not requirement:
                continue
            try:
                self.workbench.map_framework_control(
                    unified_control_code=control_code,
                    framework_code=framework_code,
                    control_id=requirement,
                    mapping_type=_text(row.get("Mapping Type")) or "mapped",
                    rationale=_text(row.get("Rationale")),
                    confidence=_as_float(row.get("Confidence"), 0.85),
                    inheritance_strategy=_text(row.get("Inheritance Strategy")) or "manual_review",
                    approval_status=_text(row.get("Mapping Status")) or "approved",
                    reviewed_by=_text(row.get("Reviewed By")) or "workspace_grid",
                    approval_notes=_text(row.get("Approval Notes")),
                )
                updated += 1
            except Exception as exc:
                errors.append(f"{control_code} -> {framework_code} {requirement}: {exc}")
        self.session.flush()
        return {"updated_count": updated, "errors": errors}

    def apply_testing_rows(
        self,
        rows: list[dict],
        *,
        organization_code: str | None = None,
        product_code: str | None = None,
    ) -> dict:
        if not organization_code or not product_code:
            raise ValueError("An organization and product scope are required for testing rows.")
        updated = 0
        errors: list[str] = []
        current_rows = {
            row["SCF Control"]: row
            for row in self.control_register_rows(
                organization_code=organization_code,
                product_code=product_code,
            )
        }
        for row in rows:
            control_code = _text(row.get("SCF Control"))
            if not control_code:
                continue
            try:
                current = current_rows.get(control_code, {})
                scope_flavor_code = _text(row.get("Scope Flavor")) or _text(current.get("Scope Flavor"))
                plan_code = _text(row.get("Plan Code")) or _normalized_code(organization_code, product_code, control_code, "PLAN")
                target_code = _text(row.get("Target Code")) or _normalized_code(organization_code, product_code, control_code, "TARGET")
                self.workbench.upsert_evidence_collection_plan(
                    name=_text(row.get("Plan Name")) or f"{control_code} testing plan",
                    unified_control_code=control_code,
                    plan_code=plan_code,
                    scope_type="product",
                    execution_mode=_text(row.get("Execution Mode")) or "manual",
                    collector_key=_text(row.get("Collector Key")),
                    evidence_type=_text(row.get("Evidence Type")) or "manual_artifact",
                    instructions=_text(row.get("Instructions")),
                    expected_artifacts_json=_text(row.get("Expected Artifacts JSON")) or "[]",
                    review_frequency=_text(row.get("Review Frequency")) or "quarterly",
                    lifecycle_status=_text(row.get("Plan Status")) or "draft",
                )
                self.workbench.upsert_control_implementation(
                    organization_code=organization_code,
                    product_code=product_code,
                    product_flavor_code=scope_flavor_code or None,
                    unified_control_code=control_code,
                    title=_text(current.get("Control Name")) or f"{control_code} implementation",
                    owner=_text(current.get("Owner")),
                    status=_text(current.get("Implementation Status")) or "planned",
                    lifecycle=_text(current.get("Lifecycle")) or "design",
                    priority=_text(current.get("Priority")) or "medium",
                    impl_general=_text(current.get("Implementation Narrative")),
                    impl_aws=_text(current.get("AWS Narrative")),
                    test_plan=_text(row.get("Implementation Test Plan")),
                )
                self.workbench.upsert_product_control_profile(
                    organization_code=organization_code,
                    product_code=product_code,
                    product_flavor_code=scope_flavor_code or None,
                    unified_control_code=control_code,
                    applicability_status=_text(current.get("SoA")) or "applicable",
                    implementation_status=_text(current.get("Implementation Status")) or "planned",
                    assessment_mode=_text(current.get("Assessment Mode")) or "manual",
                    maturity_governance=_as_int(current.get("Maturity Governance"), 3),
                    maturity_implementation=_as_int(current.get("Maturity Implementation"), 3),
                    maturity_observability=_as_int(current.get("Maturity Observability"), 2),
                    maturity_automation=_as_int(current.get("Maturity Automation"), 2),
                    maturity_assurance=_as_int(current.get("Maturity Assurance"), 2),
                    rationale=_text(current.get("SoA Rationale")),
                    evidence_strategy=_text(row.get("Evidence Strategy")),
                )
                if any(
                    _text(row.get(key))
                    for key in ["AWS Profile", "AWS Account ID", "AWS Role", "AWS Regions", "Binding"]
                ):
                    regions = [item.strip() for item in _text(row.get("AWS Regions")).split(",") if item.strip()]
                    self.workbench.upsert_aws_evidence_target(
                        organization_code=organization_code,
                        product_code=product_code,
                        product_flavor_code=scope_flavor_code or None,
                        target_code=target_code,
                        binding_code=_text(row.get("Binding")) or None,
                        unified_control_code=control_code,
                        name=f"{control_code} live target",
                        aws_profile=_text(row.get("AWS Profile")),
                        aws_account_id=_text(row.get("AWS Account ID")),
                        role_name=_text(row.get("AWS Role")),
                        regions_json=json.dumps(regions or []),
                        lifecycle_status=_text(row.get("Target Status")) or "active",
                        notes=_text(row.get("Target Notes")),
                    )
                updated += 1
            except Exception as exc:
                errors.append(f"{control_code}: {exc}")
        self.session.flush()
        return {"updated_count": updated, "errors": errors}

    def apply_framework_rows(self, rows: list[dict]) -> dict:
        updated = 0
        errors: list[str] = []
        for row in rows:
            framework_code = _text(row.get("Framework"))
            if not framework_code:
                continue
            try:
                self.frameworks.create_framework_shell(
                    code=framework_code,
                    name=_text(row.get("Name")) or framework_code,
                    version=_text(row.get("Version")) or "current",
                    category=_text(row.get("Category")) or "framework",
                    description=_text(row.get("Description")),
                    issuing_body=_text(row.get("Issuing Body")),
                    jurisdiction=_text(row.get("Jurisdiction")) or "global",
                    source_url=_text(row.get("Source URL")),
                    lifecycle_status=_text(row.get("Lifecycle")) or "draft",
                )
                updated += 1
            except Exception as exc:
                errors.append(f"{framework_code}: {exc}")
        self.session.flush()
        return {"updated_count": updated, "errors": errors}

    def _binding_codes(self, organization_code: str | None) -> list[str]:
        query = select(OrganizationFrameworkBinding).order_by(OrganizationFrameworkBinding.binding_code)
        if organization_code:
            organization = self.workbench._organization_by_code(organization_code)
            query = query.where(OrganizationFrameworkBinding.organization_id == organization.id)
        return [item.binding_code for item in self.session.scalars(query).all()]

    def _target_lookup(
        self,
        *,
        organization_code: str | None = None,
        product_code: str | None = None,
    ) -> dict[str, AwsEvidenceTarget]:
        query = (
            select(AwsEvidenceTarget)
            .options(
                selectinload(AwsEvidenceTarget.unified_control),
                selectinload(AwsEvidenceTarget.framework_binding),
            )
            .order_by(AwsEvidenceTarget.updated_at.desc())
        )
        if organization_code:
            organization = self.workbench._organization_by_code(organization_code)
            query = query.where(AwsEvidenceTarget.organization_id == organization.id)
        if organization_code and product_code:
            product = self.workbench._product_by_code(organization_code, product_code)
            query = query.where(AwsEvidenceTarget.product_id == product.id)
        lookup: dict[str, AwsEvidenceTarget] = {}
        for target in self.session.scalars(query).all():
            if target.unified_control and target.unified_control.code not in lookup:
                lookup[target.unified_control.code] = target
        return lookup

    @staticmethod
    def _regions_text(regions_json: str) -> str:
        try:
            regions = json.loads(regions_json or "[]")
            if isinstance(regions, list):
                return ", ".join(str(item) for item in regions)
        except Exception:
            pass
        return _text(regions_json)
