from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from aws_local_audit.db import session_scope
from aws_local_audit.models import (
    Control,
    ControlImplementation,
    Framework,
    ImportedRequirement,
    ImportedRequirementReference,
    Organization,
    Product,
    ProductFlavor,
    ReferenceDocument,
    UnifiedControlMapping,
    UnifiedControlReference,
)
from aws_local_audit.services.foundation_uplift import FoundationUpliftService
from aws_local_audit.services.framework_imports import FrameworkImportService
from aws_local_audit.services.frameworks import FrameworkService
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.knowledge_packs import AIKnowledgePackService
from aws_local_audit.services.suggestions import SuggestionService
from aws_local_audit.services.workbench import WorkbenchService


def _hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero"><h1 style="margin:0;">{title}</h1><p style="margin:0.35rem 0 0 0;">{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def _metric(label: str, value: str) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="label">{label}</div><div class="value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def _option_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def _save_upload(uploaded_file, suffix: str | None = None) -> str:
    resolved_suffix = suffix or Path(uploaded_file.name).suffix or ".tmp"
    with tempfile.NamedTemporaryFile(delete=False, suffix=resolved_suffix) as handle:
        handle.write(uploaded_file.getvalue())
        return handle.name


def _org_codes(session) -> list[str]:
    return [item.code for item in session.scalars(select(Organization).order_by(Organization.code)).all()]


def _product_codes(session, organization_code: str) -> list[str]:
    organization = session.scalar(select(Organization).where(Organization.code == organization_code))
    if organization is None:
        return []
    return [
        item.code
        for item in session.scalars(
            select(Product).where(Product.organization_id == organization.id).order_by(Product.code)
        ).all()
    ]


def _flavor_codes(session, organization_code: str, product_code: str) -> list[str]:
    organization = session.scalar(select(Organization).where(Organization.code == organization_code))
    if organization is None:
        return []
    product = session.scalar(
        select(Product).where(Product.organization_id == organization.id, Product.code == product_code)
    )
    if product is None:
        return []
    return [
        item.code
        for item in session.scalars(
            select(ProductFlavor).where(ProductFlavor.product_id == product.id).order_by(ProductFlavor.code)
        ).all()
    ]


def render_control_framework_studio() -> None:
    _hero(
        "Control Framework Studio",
        "Manage the SCF pivot baseline, uploaded regulations, source requirements, mappings, and implementation wording in one operator workflow.",
    )
    st.markdown(
        '<div class="section-note">Use this page to keep regulatory requirements, the unified control baseline, mapped traceability, and the wording of implemented controls together. Pick a framework, focus a requirement, refine the unified control, approve the mapping, and update the scoped implementation without leaving the screen.</div>',
        unsafe_allow_html=True,
    )
    with session_scope() as session:
        governance = GovernanceService(session)
        workbench = WorkbenchService(session)
        importer = FrameworkImportService(session)
        framework_service = FrameworkService(session)
        suggestion_service = SuggestionService(session)
        knowledge_packs = AIKnowledgePackService(session)
        uplift = FoundationUpliftService(session)

        frameworks = session.scalars(select(Framework).order_by(Framework.code)).all()
        framework_codes = [item.code for item in frameworks]
        pivot_code = governance.pivot_framework_code()
        default_framework = st.session_state.get(
            "control_framework_studio_framework",
            pivot_code if pivot_code in framework_codes else (framework_codes[0] if framework_codes else ""),
        )

        if not frameworks:
            st.info("No frameworks are available yet. Seed the templates or import an external framework to start the unified control workflow.")
            if st.button("Seed framework templates", key="control_studio_seed_templates", type="primary"):
                touched = framework_service.seed_templates()
                st.success(f"Synchronized {len(touched)} framework template(s).")
            return

        top_cols = st.columns([0.85, 1.15, 0.95, 1.05])
        with top_cols[0]:
            st.metric("Pivot", pivot_code or "Not set")
        with top_cols[1]:
            selected_framework_code = st.selectbox(
                "Regulation / standard",
                framework_codes,
                index=_option_index(framework_codes, default_framework),
                key="control_framework_studio_framework",
            )
        framework = next(item for item in frameworks if item.code == selected_framework_code)
        controls = session.scalars(
            select(Control).where(Control.framework_id == framework.id).order_by(Control.control_id)
        ).all()
        control_options = [""] + [item.control_id for item in controls]
        with top_cols[2]:
            selected_control_code = st.selectbox(
                "Requirement / control",
                control_options,
                key="control_framework_studio_control",
            )
        selected_control = next((item for item in controls if item.control_id == selected_control_code), None)

        existing_control_mappings = (
            session.scalars(
                select(UnifiedControlMapping)
                .where(
                    UnifiedControlMapping.framework_id == framework.id,
                    UnifiedControlMapping.control_id == (selected_control.id if selected_control else -1),
                )
                .order_by(UnifiedControlMapping.approval_status.desc(), UnifiedControlMapping.confidence.desc())
            ).all()
            if selected_control
            else []
        )
        unified_controls = workbench.list_unified_controls()
        unified_codes = [""] + [item.code for item in unified_controls]
        default_unified = st.session_state.get("control_framework_studio_unified_control", "")
        if not default_unified and existing_control_mappings:
            default_unified = existing_control_mappings[0].unified_control.code
        with top_cols[3]:
            selected_unified_code = st.selectbox(
                "Unified control",
                unified_codes,
                index=_option_index(unified_codes, default_unified),
                key="control_framework_studio_unified_control",
            )
        selected_unified = next((item for item in unified_controls if item.code == selected_unified_code), None)

        approved_mapping_count = session.scalar(
            select(func.count()).select_from(UnifiedControlMapping).where(
                UnifiedControlMapping.framework_id == framework.id,
                UnifiedControlMapping.approval_status == "approved",
            )
        ) or 0
        imported_requirement_count = session.scalar(
            select(func.count()).select_from(ImportedRequirement).where(ImportedRequirement.framework_id == framework.id)
        ) or 0
        implementation_count = session.scalar(
            select(func.count()).select_from(ControlImplementation).where(
                ControlImplementation.framework_id == framework.id
            )
        ) or 0
        st.caption(
            f"{framework.code} | {len(controls)} source controls | {imported_requirement_count} imported requirements | {approved_mapping_count} approved mappings | {implementation_count} implementation record(s)"
        )

        tabs = st.tabs(
            [
                "Scope",
                "Source Requirements",
                "Unified Control",
                "Mappings",
                "Implementation Wording",
                "Import & Suggestions",
                "Traceability",
                "Copilot Pack",
            ]
        )

        with tabs[0]:
            metric_cols = st.columns(4)
            with metric_cols[0]:
                _metric("Framework", framework.code)
            with metric_cols[1]:
                _metric("Controls", str(len(controls)))
            with metric_cols[2]:
                _metric("Imported rows", str(imported_requirement_count))
            with metric_cols[3]:
                _metric("Approved mappings", str(approved_mapping_count))
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Code": framework.code,
                            "Name": framework.name,
                            "Version": framework.version,
                            "Category": framework.category,
                            "Authority": framework.authority_document.document_key if framework.authority_document else "",
                            "Source": framework.source,
                            "Lifecycle": framework.lifecycle_status,
                        }
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            if selected_control:
                path_rows = [
                    {
                        "Framework": framework.code,
                        "Requirement": selected_control.control_id,
                        "Requirement Title": selected_control.title,
                        "Unified Control": mapping.unified_control.code,
                        "Mapping Status": mapping.approval_status,
                        "Confidence": mapping.confidence,
                    }
                    for mapping in existing_control_mappings[:8]
                ]
                if path_rows:
                    st.dataframe(pd.DataFrame(path_rows), width="stretch", hide_index=True)
                else:
                    st.info("The selected requirement does not have a stored mapping yet.")
            if st.button("Bootstrap SCF pivot path", key="control_studio_bootstrap_backbone", type="primary"):
                try:
                    result = uplift.ensure_phase1_backbone_path()
                    st.success(
                        f"Ready: {result['unified_control_code']} mapped for {result['framework_code']} {result['control_id']} in {result['organization_code']}/{result['product_code']}/{result['product_flavor_code']}."
                    )
                except Exception as exc:
                    st.error(str(exc))

        with tabs[1]:
            left, right = st.columns([1.05, 0.95])
            with left:
                control_rows = [
                    {
                        "Control": item.control_id,
                        "Title": item.title,
                        "Severity": item.severity,
                        "Evidence Query": item.evidence_query,
                        "Imported rows": len(item.imported_requirements),
                    }
                    for item in controls[:200]
                ]
                if control_rows:
                    st.dataframe(pd.DataFrame(control_rows), width="stretch", hide_index=True)
                else:
                    st.info("This framework does not have controls yet.")
            with right:
                if selected_control is None:
                    st.info("Choose a framework control to inspect its wording, imported rows, and mappings.")
                else:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {"Field": "Control ID", "Value": selected_control.control_id},
                                {"Field": "Title", "Value": selected_control.title},
                                {"Field": "Description", "Value": selected_control.description},
                                {"Field": "Source Reference", "Value": selected_control.source_reference},
                                {"Field": "AWS Guidance", "Value": selected_control.metadata_entry.aws_guidance if selected_control.metadata_entry else ""},
                                {"Field": "Check Type", "Value": selected_control.metadata_entry.check_type if selected_control.metadata_entry else ""},
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                    imported_requirements = session.scalars(
                        select(ImportedRequirement)
                        .where(
                            ImportedRequirement.framework_id == framework.id,
                            ImportedRequirement.control_id == selected_control.id,
                        )
                        .order_by(ImportedRequirement.row_number)
                    ).all()
                    if imported_requirements:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "Row": item.row_number,
                                        "External ID": item.external_id,
                                        "Title": item.title,
                                        "Action": item.import_action,
                                        "Reference": item.source_reference,
                                    }
                                    for item in imported_requirements[:50]
                                ]
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        st.caption("No imported requirement rows are currently linked to this control.")

        with tabs[2]:
            left, right = st.columns([0.9, 1.1])
            with left:
                with st.form("control_framework_studio_unified_form"):
                    code = st.text_input("Control code", value=selected_unified.code if selected_unified else "")
                    name = st.text_input("Control name", value=selected_unified.name if selected_unified else "")
                    domain = st.text_input("Domain", value=selected_unified.domain if selected_unified else "")
                    family = st.text_input("Family", value=selected_unified.family if selected_unified else "")
                    control_type = st.text_input("Control type", value=selected_unified.control_type if selected_unified else "")
                    severity_choices = ["low", "medium", "high", "critical"]
                    severity = st.selectbox(
                        "Default severity",
                        severity_choices,
                        index=_option_index(severity_choices, selected_unified.default_severity if selected_unified else "medium"),
                    )
                    description = st.text_area("Requirement coverage summary", value=selected_unified.description if selected_unified else "", height=100)
                    implementation_guidance = st.text_area(
                        "How we implement this control",
                        value=selected_unified.implementation_guidance if selected_unified else "",
                        height=120,
                    )
                    test_guidance = st.text_area(
                        "How this control should be tested",
                        value=selected_unified.test_guidance if selected_unified else "",
                        height=100,
                    )
                    if st.form_submit_button("Save unified control", type="primary") and code and name:
                        try:
                            unified_control = workbench.create_unified_control(
                                code=code,
                                name=name,
                                description=description,
                                domain=domain,
                                family=family,
                                control_type=control_type,
                                default_severity=severity,
                                implementation_guidance=implementation_guidance,
                                test_guidance=test_guidance,
                            )
                            st.session_state["control_framework_studio_unified_control"] = unified_control.code
                            st.success(f"Unified control saved: {unified_control.code}")
                        except Exception as exc:
                            st.error(str(exc))
            with right:
                if unified_controls:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Code": item.code,
                                    "Name": item.name,
                                    "Domain": item.domain,
                                    "Family": item.family,
                                    "Severity": item.default_severity,
                                    "Lifecycle": item.lifecycle_status,
                                }
                                for item in unified_controls[:200]
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("Create the first SCF-backed unified control here.")

        with tabs[3]:
            left, right = st.columns([0.95, 1.05])
            with left:
                mapping_rows = session.scalars(
                    select(UnifiedControlMapping)
                    .where(UnifiedControlMapping.framework_id == framework.id)
                    .order_by(UnifiedControlMapping.reviewed_at.desc(), UnifiedControlMapping.id.desc())
                ).all()
                if mapping_rows:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Unified Control": item.unified_control.code,
                                    "Requirement": item.control.control_id,
                                    "Status": item.approval_status,
                                    "Type": item.mapping_type,
                                    "Confidence": item.confidence,
                                    "Reviewer": item.reviewed_by,
                                }
                                for item in mapping_rows[:150]
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("No mappings exist for this framework yet.")
            with right:
                if selected_control is None or not selected_unified_code:
                    st.info("Choose both a framework requirement and a unified control to create or update the mapping.")
                else:
                    current_mapping = next(
                        (
                            item
                            for item in existing_control_mappings
                            if item.unified_control.code == selected_unified_code
                        ),
                        None,
                    )
                    with st.form("control_framework_studio_mapping_form"):
                        mapping_type_choices = ["mapped", "partial", "supporting", "gap"]
                        inheritance_choices = ["manual_review", "direct", "shared_control", "product_specific"]
                        approval_choices = ["proposed", "approved", "rejected"]
                        mapping_type = st.selectbox(
                            "Mapping type",
                            mapping_type_choices,
                            index=_option_index(mapping_type_choices, current_mapping.mapping_type if current_mapping else "mapped"),
                        )
                        inheritance_strategy = st.selectbox(
                            "Inheritance strategy",
                            inheritance_choices,
                            index=_option_index(
                                inheritance_choices,
                                current_mapping.inheritance_strategy if current_mapping else "manual_review",
                            ),
                        )
                        approval_status = st.selectbox(
                            "Approval status",
                            approval_choices,
                            index=_option_index(
                                approval_choices,
                                current_mapping.approval_status if current_mapping else "proposed",
                            ),
                        )
                        confidence = st.slider(
                            "Confidence",
                            min_value=0.0,
                            max_value=1.0,
                            value=float(current_mapping.confidence if current_mapping else 0.85),
                            step=0.01,
                        )
                        reviewed_by = st.text_input(
                            "Reviewer",
                            value=current_mapping.reviewed_by if current_mapping else "workspace_reviewer",
                        )
                        rationale = st.text_area(
                            "Coverage rationale",
                            value=current_mapping.rationale if current_mapping else "",
                            height=110,
                        )
                        approval_notes = st.text_area(
                            "Approval notes",
                            value=current_mapping.approval_notes if current_mapping else "",
                            height=90,
                        )
                        if st.form_submit_button("Save mapping", type="primary"):
                            try:
                                saved = workbench.map_framework_control(
                                    unified_control_code=selected_unified_code,
                                    framework_code=framework.code,
                                    control_id=selected_control.control_id,
                                    mapping_type=mapping_type,
                                    rationale=rationale,
                                    confidence=confidence,
                                    inheritance_strategy=inheritance_strategy,
                                    approval_status=approval_status,
                                    reviewed_by=reviewed_by,
                                    approval_notes=approval_notes,
                                )
                                st.success(f"Mapping saved with status {saved.approval_status}.")
                            except Exception as exc:
                                st.error(str(exc))

                pending_suggestions = suggestion_service.list_pending_mapping_suggestions(framework.code)
                if selected_control:
                    pending_suggestions = [
                        item for item in pending_suggestions if item.control and item.control.id == selected_control.id
                    ]
                if pending_suggestions:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "ID": item.id,
                                    "Requirement": item.control.control_id if item.control else "",
                                    "Top Match": suggestion_service.top_match_for_suggestion(item).get("unified_control_code", ""),
                                    "Score": suggestion_service.top_match_for_suggestion(item).get("score", 0.0),
                                    "Provider": item.provider,
                                }
                                for item in pending_suggestions[:25]
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                    with st.form("control_framework_studio_suggestion_review"):
                        suggestion_id = st.selectbox(
                            "Suggestion to resolve",
                            [item.id for item in pending_suggestions],
                            format_func=lambda suggestion_id: next(
                                (
                                    f"{item.id} | {item.control.control_id if item.control else ''}"
                                    for item in pending_suggestions
                                    if item.id == suggestion_id
                                ),
                                str(suggestion_id),
                            ),
                        )
                        decision = st.selectbox("Decision", ["promote_to_mapping", "mark_reviewed"])
                        reviewer = st.text_input("Decision by", value="workspace_reviewer")
                        notes = st.text_area("Decision notes", height=80)
                        if st.form_submit_button("Resolve suggestion"):
                            try:
                                if decision == "promote_to_mapping":
                                    suggestion_service.promote_mapping_suggestion(suggestion_id, reviewer=reviewer, notes=notes)
                                    st.success("Suggestion promoted into an approved mapping.")
                                else:
                                    suggestion_service.dismiss_suggestion(suggestion_id, reviewer=reviewer, notes=notes)
                                    st.success("Suggestion marked as reviewed.")
                            except Exception as exc:
                                st.error(str(exc))

        with tabs[4]:
            org_codes = _org_codes(session)
            if not org_codes:
                st.info("Create an organization and product scope before storing implementation wording.")
            else:
                scope_cols = st.columns([0.9, 0.9, 0.7, 0.7])
                with scope_cols[0]:
                    organization_code = st.selectbox("Organization", org_codes, key="control_studio_impl_org")
                with scope_cols[1]:
                    product_codes = _product_codes(session, organization_code)
                    product_code = st.selectbox("Product", product_codes or [""], key="control_studio_impl_product")
                with scope_cols[2]:
                    flavor_codes = _flavor_codes(session, organization_code, product_code) if product_code else []
                    flavor_code = st.selectbox("Flavor", [""] + flavor_codes, key="control_studio_impl_flavor")
                with scope_cols[3]:
                    st.caption("Selected path")
                    st.write(selected_unified_code or "(choose unified control)")

                existing_implementation = None
                existing_profile = None
                if product_code:
                    implementations = workbench.list_control_implementations(organization_code=organization_code)
                    existing_implementation = next(
                        (
                            item
                            for item in implementations
                            if (item.product.code if item.product else "") == product_code
                            and (item.product_flavor.code if item.product_flavor else "") == (flavor_code or "")
                            and ((item.unified_control.code if item.unified_control else "") == selected_unified_code or not selected_unified_code)
                            and ((item.control.control_id if item.control else "") == (selected_control.control_id if selected_control else ""))
                        ),
                        None,
                    )
                    profiles = workbench.list_product_control_profiles(
                        organization_code=organization_code,
                        product_code=product_code,
                        product_flavor_code=flavor_code or None,
                    )
                    existing_profile = next(
                        (
                            item
                            for item in profiles
                            if ((item.unified_control.code if item.unified_control else "") == selected_unified_code or not selected_unified_code)
                            and ((item.control.control_id if item.control else "") == (selected_control.control_id if selected_control else ""))
                        ),
                        None,
                    )

                left, right = st.columns([1.05, 0.95])
                with left:
                    with st.form("control_framework_studio_implementation_form"):
                        title = st.text_input(
                            "Implementation title",
                            value=existing_implementation.title if existing_implementation else (selected_unified.name if selected_unified else (selected_control.title if selected_control else "")),
                        )
                        implementation_code = st.text_input(
                            "Implementation code",
                            value=existing_implementation.implementation_code if existing_implementation and existing_implementation.implementation_code else "",
                        )
                        owner = st.text_input("Owner", value=existing_implementation.owner if existing_implementation else "")
                        status_choices = ["draft", "planned", "implemented", "in_review", "operational"]
                        lifecycle_choices = ["design", "build", "operate", "review", "retire"]
                        status = st.selectbox(
                            "Status",
                            status_choices,
                            index=_option_index(status_choices, existing_implementation.status if existing_implementation else "draft"),
                        )
                        lifecycle = st.selectbox(
                            "Lifecycle",
                            lifecycle_choices,
                            index=_option_index(lifecycle_choices, existing_implementation.lifecycle if existing_implementation else "design"),
                        )
                        objective = st.text_area("Control objective", value=existing_implementation.objective if existing_implementation else "", height=90)
                        impl_general = st.text_area("General implementation wording", value=existing_implementation.impl_general if existing_implementation else "", height=120)
                        impl_aws = st.text_area("AWS implementation wording", value=existing_implementation.impl_aws if existing_implementation else "", height=120)
                        test_plan = st.text_area("How the control is tested", value=existing_implementation.test_plan if existing_implementation else "", height=100)
                        notes = st.text_area("Notes", value=existing_implementation.notes if existing_implementation else "", height=80)
                        save_impl = st.form_submit_button("Save implementation wording", type="primary")
                    if save_impl and organization_code and product_code and title:
                        try:
                            saved = workbench.upsert_control_implementation(
                                organization_code=organization_code,
                                product_code=product_code,
                                product_flavor_code=flavor_code or None,
                                unified_control_code=selected_unified_code or None,
                                framework_code=framework.code if selected_control else None,
                                control_id=selected_control.control_id if selected_control else None,
                                implementation_code=implementation_code or None,
                                title=title,
                                owner=owner,
                                status=status,
                                lifecycle=lifecycle,
                                objective=objective,
                                impl_general=impl_general,
                                impl_aws=impl_aws,
                                test_plan=test_plan,
                                notes=notes,
                            )
                            st.success(f"Implementation saved: {saved.implementation_code or saved.id}")
                        except Exception as exc:
                            st.error(str(exc))
                with right:
                    with st.form("control_framework_studio_profile_form"):
                        applicability_choices = ["applicable", "planned", "inherited", "not_applicable"]
                        mode_choices = ["manual", "assisted", "autonomous"]
                        applicability = st.selectbox(
                            "Applicability",
                            applicability_choices,
                            index=_option_index(
                                applicability_choices,
                                existing_profile.applicability_status if existing_profile else "applicable",
                            ),
                        )
                        assessment_mode = st.selectbox(
                            "Assessment mode",
                            mode_choices,
                            index=_option_index(
                                mode_choices,
                                existing_profile.assessment_mode if existing_profile else "manual",
                            ),
                        )
                        maturity_governance = st.slider("Governance maturity", 1, 5, existing_profile.maturity_governance if existing_profile else 3)
                        maturity_implementation = st.slider("Implementation maturity", 1, 5, existing_profile.maturity_implementation if existing_profile else 3)
                        maturity_observability = st.slider("Observability maturity", 1, 5, existing_profile.maturity_observability if existing_profile else 3)
                        maturity_automation = st.slider("Automation maturity", 1, 5, existing_profile.maturity_automation if existing_profile else 2)
                        maturity_assurance = st.slider("Assurance maturity", 1, 5, existing_profile.maturity_assurance if existing_profile else 2)
                        rationale = st.text_area("Rationale", value=existing_profile.rationale if existing_profile else "", height=90)
                        evidence_strategy = st.text_area("Evidence strategy", value=existing_profile.evidence_strategy if existing_profile else "", height=90)
                        review_notes = st.text_area("Review notes", value=existing_profile.review_notes if existing_profile else "", height=80)
                        save_profile = st.form_submit_button("Save product profile", type="primary")
                    if save_profile and organization_code and product_code:
                        try:
                            profile = workbench.upsert_product_control_profile(
                                organization_code=organization_code,
                                product_code=product_code,
                                product_flavor_code=flavor_code or None,
                                unified_control_code=selected_unified_code or None,
                                framework_code=framework.code if selected_control else None,
                                control_id=selected_control.control_id if selected_control else None,
                                applicability_status=applicability,
                                assessment_mode=assessment_mode,
                                maturity_governance=maturity_governance,
                                maturity_implementation=maturity_implementation,
                                maturity_observability=maturity_observability,
                                maturity_automation=maturity_automation,
                                maturity_assurance=maturity_assurance,
                                rationale=rationale,
                                evidence_strategy=evidence_strategy,
                                review_notes=review_notes,
                            )
                            st.success(f"Product control profile saved with autonomy {profile.autonomy_recommendation}.")
                        except Exception as exc:
                            st.error(str(exc))

        with tabs[5]:
            uploaded = st.file_uploader(
                "Upload CSV or Excel source",
                type=["csv", "xlsx", "xls"],
                key="control_framework_studio_upload",
                help="Use this for new regulations, standards, or spreadsheets such as CSA CCM or SCF.",
            )
            if uploaded is None:
                st.info("Upload a source file to preview its content, import it, or capture mapping suggestions.")
            else:
                suffix = Path(uploaded.name).suffix or ".tmp"
                source_path = _save_upload(uploaded, suffix=suffix)
                try:
                    sheet_name = ""
                    if suffix.lower() in {".xlsx", ".xls"}:
                        sheets = importer.available_sheets(source_path)
                        if sheets:
                            sheet_name = st.selectbox("Worksheet", sheets, key="control_framework_studio_sheet")
                    preview = importer.preview_source(source_path, sheet_name=sheet_name or "")
                    st.dataframe(pd.DataFrame(preview["records"]), width="stretch", hide_index=True)
                    column_pairs = []
                    for key, value in preview["column_mapping"].items():
                        rendered_value = value or "(unmapped)"
                        column_pairs.append(f"{key}->{rendered_value}")
                    st.caption(
                        f"{preview['row_count']} rows detected | mapped columns: {', '.join(column_pairs)}"
                    )
                    action_cols = st.columns([1.1, 1.0])
                    with action_cols[0]:
                        import_mode = st.selectbox(
                            "Action",
                            [
                                "Preview only",
                                "Import into selected framework",
                                "Import as SCF pivot baseline",
                                "Capture mapping suggestions",
                            ],
                            key="control_framework_studio_action",
                        )
                        mapping_mode = st.selectbox(
                            "Mapping strategy",
                            ["suggest_only", "map_existing", "create_baseline", "none"],
                            index=0,
                            key="control_framework_studio_mapping_mode",
                        )
                        auto_approve = st.checkbox("Auto-approve high-confidence mappings", value=False)
                        threshold = st.slider("Auto-mapping threshold", 0.5, 1.0, 0.84, 0.01)
                    with action_cols[1]:
                        if import_mode == "Import into selected framework":
                            if st.button("Import source now", key="control_framework_studio_import_now", type="primary"):
                                try:
                                    result = importer.import_source(
                                        file_path=source_path,
                                        framework_code=framework.code,
                                        framework_name=framework.name,
                                        framework_version=framework.version,
                                        source_name=uploaded.name,
                                        source_type="spreadsheet" if suffix.lower() in {".xlsx", ".xls"} else "csv",
                                        source_url=framework.source_url or "",
                                        source_version=framework.version,
                                        sheet_name=sheet_name,
                                        mapping_mode=mapping_mode,
                                        auto_mapping_threshold=threshold,
                                        auto_approve_mappings=auto_approve,
                                        category=framework.category or "framework",
                                        description=framework.description or "",
                                        issuing_body=framework.issuing_body or "",
                                        jurisdiction=framework.jurisdiction or "global",
                                    )
                                    st.success(
                                        f"Imported {result['summary']['imported_count']} rows into {framework.code}."
                                    )
                                except Exception as exc:
                                    st.error(str(exc))
                        elif import_mode == "Import as SCF pivot baseline":
                            if st.button("Import SCF baseline", key="control_framework_studio_import_scf", type="primary"):
                                try:
                                    result = importer.import_secure_controls_framework(
                                        file_path=source_path,
                                        sheet_name=sheet_name or "SCF 2025.3.1",
                                        actor="control_framework_studio",
                                        auto_mapping_threshold=threshold,
                                        auto_approve_mappings=auto_approve,
                                    )
                                    st.success(
                                        f"SCF pivot baseline imported with {result['summary']['imported_count']} rows."
                                    )
                                except Exception as exc:
                                    st.error(str(exc))
                        elif import_mode == "Capture mapping suggestions":
                            if suffix.lower() != ".csv":
                                st.info("Mapping suggestion capture currently expects a CSV source.")
                            elif st.button("Capture suggestions", key="control_framework_studio_capture_suggestions", type="primary"):
                                try:
                                    stored = suggestion_service.capture_mapping_suggestions_from_csv(
                                        framework_code=framework.code,
                                        csv_path=source_path,
                                        limit=3,
                                    )
                                    st.success(f"Captured {len(stored)} suggestion(s) for review.")
                                except Exception as exc:
                                    st.error(str(exc))
                finally:
                    Path(source_path).unlink(missing_ok=True)

        with tabs[6]:
            left, right = st.columns([1.0, 1.0])
            with left:
                if selected_unified is None:
                    st.info("Choose a unified control to inspect linked references and guidance.")
                else:
                    unified_references = session.scalars(
                        select(UnifiedControlReference)
                        .where(UnifiedControlReference.unified_control_id == selected_unified.id)
                        .order_by(UnifiedControlReference.created_at.desc())
                    ).all()
                    if unified_references:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "Document": item.reference_document.document_key,
                                        "Name": item.reference_document.name,
                                        "Relationship": item.relationship_type,
                                        "Reference": item.reference_code,
                                        "Source Framework": item.framework.code if item.framework else "",
                                        "Source Control": item.control.control_id if item.control else "",
                                    }
                                    for item in unified_references[:50]
                                ]
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        st.caption("No reference documents are linked yet to the selected unified control.")
                    standalone_references = session.scalars(
                        select(ReferenceDocument).order_by(ReferenceDocument.document_key)
                    ).all()
                    if standalone_references:
                        st.caption(f"Reference library size: {len(standalone_references)} document(s).")
            with right:
                if selected_control is None:
                    st.info("Choose a source requirement to inspect imported traceability references.")
                else:
                    imported_refs = session.scalars(
                        select(ImportedRequirementReference)
                        .join(ImportedRequirement, ImportedRequirement.id == ImportedRequirementReference.imported_requirement_id)
                        .where(
                            ImportedRequirement.framework_id == framework.id,
                            ImportedRequirement.control_id == selected_control.id,
                        )
                        .order_by(ImportedRequirementReference.created_at.desc())
                    ).all()
                    if imported_refs:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "Document": item.reference_document.document_key,
                                        "Reference": item.reference_code,
                                        "Relationship": item.relationship_type,
                                        "Text": item.reference_text,
                                    }
                                    for item in imported_refs[:50]
                                ]
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        st.caption("No imported requirement references are linked to the selected requirement yet.")

        with tabs[7]:
            packs = knowledge_packs.list_packs()
            if not packs:
                st.info("No governed AI knowledge packs are available yet.")
                if st.button("Seed AI knowledge pack templates", key="control_studio_seed_packs", type="primary"):
                    try:
                        touched = knowledge_packs.seed_templates()
                        st.success(f"Synchronized {len(touched)} AI knowledge pack template(s).")
                    except Exception as exc:
                        st.error(str(exc))
            else:
                pack_codes = [item.pack_code for item in packs]
                default_pack = knowledge_packs.default_pack_code()
                selected_pack_code = st.selectbox(
                    "Knowledge pack",
                    pack_codes,
                    index=_option_index(pack_codes, default_pack if default_pack in pack_codes else pack_codes[0]),
                    key="control_framework_studio_pack",
                )
                active_version = knowledge_packs.active_version(selected_pack_code)
                task_rows = knowledge_packs.list_tasks(selected_pack_code)
                task_keys = [item.task_key for item in task_rows]
                scope_cols = st.columns([0.95, 0.95, 0.85, 0.85])
                with scope_cols[0]:
                    copilot_org = st.selectbox(
                        "Organization",
                        [""] + _org_codes(session),
                        key="control_framework_studio_pack_org",
                    )
                with scope_cols[1]:
                    product_options = _product_codes(session, copilot_org) if copilot_org else []
                    copilot_product = st.selectbox(
                        "Product",
                        [""] + product_options,
                        key="control_framework_studio_pack_product",
                    )
                with scope_cols[2]:
                    flavor_options = _flavor_codes(session, copilot_org, copilot_product) if copilot_org and copilot_product else []
                    copilot_flavor = st.selectbox(
                        "Flavor",
                        [""] + flavor_options,
                        key="control_framework_studio_pack_flavor",
                    )
                with scope_cols[3]:
                    selected_task_key = st.selectbox(
                        "Task",
                        task_keys,
                        key="control_framework_studio_pack_task",
                    )

                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Pack": active_version.knowledge_pack.pack_code,
                                "Version": active_version.version_label,
                                "Status": active_version.status,
                                "Review Required": active_version.review_required,
                                "Tasks": len(task_rows),
                                "Eval Cases": len(active_version.eval_cases),
                            }
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )

                if selected_control is None or not selected_unified_code:
                    st.info("Choose both a source requirement and a unified control to generate a governed copilot draft.")
                else:
                    action_cols = st.columns([1.0, 1.0])
                    with action_cols[0]:
                        if st.button("Preview governed prompt package", key="control_studio_preview_pack", type="primary"):
                            try:
                                bundle = knowledge_packs.build_task_package(
                                    pack_code=selected_pack_code,
                                    task_key=selected_task_key,
                                    framework_code=framework.code,
                                    control_id=selected_control.control_id,
                                    unified_control_code=selected_unified_code,
                                    organization_code=copilot_org or None,
                                    product_code=copilot_product or None,
                                    product_flavor_code=copilot_flavor or None,
                                )
                                st.session_state["control_framework_studio_pack_bundle"] = {
                                    "pack_code": bundle["pack"].pack_code,
                                    "task_key": bundle["task"].task_key,
                                    "framework_code": framework.code,
                                    "control_id": selected_control.control_id,
                                    "unified_control_code": selected_unified_code,
                                    "prompt_package": bundle["prompt_package"],
                                    "draft_response": bundle["draft_response"],
                                    "citations": bundle["citations"],
                                }
                                st.success("Governed prompt package prepared.")
                            except Exception as exc:
                                st.error(str(exc))
                    with action_cols[1]:
                        if st.button("Store governed draft in review queue", key="control_studio_store_pack_draft"):
                            try:
                                suggestion = knowledge_packs.capture_task_suggestion(
                                    pack_code=selected_pack_code,
                                    task_key=selected_task_key,
                                    framework_code=framework.code,
                                    control_id=selected_control.control_id,
                                    unified_control_code=selected_unified_code,
                                    organization_code=copilot_org or None,
                                    product_code=copilot_product or None,
                                    product_flavor_code=copilot_flavor or None,
                                    actor="control_framework_studio",
                                )
                                st.success(f"Governed draft stored as AI suggestion {suggestion.id}.")
                            except Exception as exc:
                                st.error(str(exc))

                    bundle = st.session_state.get("control_framework_studio_pack_bundle")
                    if (
                        bundle
                        and bundle.get("pack_code") == selected_pack_code
                        and bundle.get("task_key") == selected_task_key
                        and bundle.get("framework_code") == framework.code
                        and bundle.get("control_id") == selected_control.control_id
                        and bundle.get("unified_control_code") == selected_unified_code
                    ):
                        preview_tabs = st.tabs(["Prompt Package", "Draft Response", "Citations"])
                        with preview_tabs[0]:
                            st.json(bundle["prompt_package"], expanded=False)
                        with preview_tabs[1]:
                            st.json(bundle["draft_response"], expanded=False)
                        with preview_tabs[2]:
                            st.dataframe(pd.DataFrame(bundle["citations"]), width="stretch", hide_index=True)
