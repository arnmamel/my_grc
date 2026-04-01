from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from aws_local_audit.db import session_scope
from aws_local_audit.models import AISuggestion, UnifiedControlMapping
from aws_local_audit.services.control_matrix import SCF_PIVOT_FRAMEWORK_CODE, ControlMatrixService
from aws_local_audit.services.control_studio_workbook import ControlStudioWorkbookService
from aws_local_audit.services.foundation_uplift import FoundationUpliftService
from aws_local_audit.services.framework_imports import FrameworkImportService
from aws_local_audit.services.frameworks import FrameworkService
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.knowledge_packs import AIKnowledgePackService
from ui_support import jump_to_page, render_prerequisite_block, render_user_error


def _hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero"><h1 style="margin:0;">{title}</h1><p style="margin:0.35rem 0 0 0;">{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def _metric(label: str, value: str, caption: str = "") -> None:
    detail = f'<div style="margin-top:0.35rem;color:#486581;font-size:0.9rem;">{caption}</div>' if caption else ""
    st.markdown(
        f'<div class="metric-card"><div class="label">{label}</div><div class="value">{value}</div>{detail}</div>',
        unsafe_allow_html=True,
    )


def _option_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def _csv_bytes(rows: list[dict]) -> bytes:
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def _empty_csv_bytes(columns: list[str]) -> bytes:
    return pd.DataFrame(columns=columns).to_csv(index=False).encode("utf-8")


def _save_upload(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix or ".tmp"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(uploaded_file.getvalue())
        return handle.name


def _show_apply_result(result: dict, noun: str) -> None:
    if result.get("updated_count", 0):
        st.success(f"Updated {result['updated_count']} {noun}.")
    if result.get("errors"):
        st.warning(f"{len(result['errors'])} row(s) could not be applied.")
        with st.expander("Rows with issues"):
            for item in result["errors"][:50]:
                st.markdown(f"- {item}")


def _uploaded_rows(workbook: ControlStudioWorkbookService, uploaded_file, *, sheet_name: str = "") -> list[dict]:
    source_path = _save_upload(uploaded_file)
    try:
        return workbook.read_rows_from_file(source_path, sheet_name=sheet_name)
    finally:
        Path(source_path).unlink(missing_ok=True)


def _scope_catalog(scopes: list[dict]) -> tuple[dict[str, dict], dict[tuple[str, str], dict]]:
    organizations: dict[str, dict] = {}
    scope_lookup: dict[tuple[str, str], dict] = {}
    for item in scopes:
        organization = organizations.setdefault(
            item["organization_code"],
            {
                "organization_name": item["organization_name"],
                "products": [],
            },
        )
        organization["products"].append(item)
        scope_lookup[(item["organization_code"], item["product_code"])] = item
    for item in organizations.values():
        item["products"].sort(key=lambda product: product["product_code"])
    return organizations, scope_lookup


def _subset_frame(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(rows)
    missing = [column for column in columns if column not in frame.columns]
    for column in missing:
        frame[column] = ""
    return frame[columns]


def render_control_framework_studio() -> None:
    _hero(
        "Control Framework Studio",
        "Work the whole control system like a governed spreadsheet: SCF baseline, requirement mappings, SoA decisions, implementation wording, and testing plans in one workbook.",
    )
    st.markdown(
        """
        <div class="section-note">
        This is the core operating surface of <strong>my_grc</strong>. Start with the SCF baseline, then choose an organization and product when you want to record how a control applies, how it is implemented, and how it is tested. Every worksheet below supports grid editing, drag-and-drop import, and export for offline work.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with session_scope() as session:
        governance = GovernanceService(session)
        matrix = ControlMatrixService(session)
        workbook = ControlStudioWorkbookService(session)
        framework_service = FrameworkService(session)
        importer = FrameworkImportService(session)
        knowledge_packs = AIKnowledgePackService(session)
        uplift = FoundationUpliftService(session)

        scopes = matrix.available_scopes()
        organizations, scope_lookup = _scope_catalog(scopes)
        frameworks = framework_service.list_frameworks()
        framework_codes = [item.code for item in frameworks]
        pivot_code = governance.pivot_framework_code() or SCF_PIVOT_FRAMEWORK_CODE

        if not frameworks:
            render_prerequisite_block(
                title="Load the framework catalog first",
                detail="Seed the baseline templates or import the latest SCF workbook before using the workbook tabs.",
                links=[("Open Guided Setup", "Wizards")],
                key_prefix="control_studio_missing_frameworks",
            )
            if st.button("Create starter SCF workspace", key="control_studio_bootstrap_empty", type="primary"):
                try:
                    uplift.ensure_phase1_backbone_path()
                    st.success("A starter SCF workspace was created. Reopen the page to begin working in the workbook.")
                except Exception as exc:
                    render_user_error(
                        title="Could not create the starter SCF workspace",
                        exc=exc,
                        fallback="The starter SCF workspace could not be created right now.",
                        key_prefix="control_studio_bootstrap_empty_error",
                    )
            return

        organization_codes = sorted(organizations)
        filters = st.columns([0.9, 0.9, 1.0, 1.0, 0.8])
        with filters[0]:
            selected_organization_code = st.selectbox(
                "Organization",
                [""] + organization_codes,
                format_func=lambda code: (
                    "Common SCF baseline"
                    if not code
                    else f"{code} - {organizations[code]['organization_name']}"
                ),
                key="control_studio_organization",
                help="Leave this blank when you only want to maintain the shared SCF baseline and mapped regulations.",
            )
        with filters[1]:
            product_options = [""] + [
                item["product_code"] for item in organizations.get(selected_organization_code, {}).get("products", [])
            ]
            selected_product_code = st.selectbox(
                "Product",
                product_options,
                format_func=lambda code: (
                    "No product selected"
                    if not code
                    else next(
                        item["product_name"]
                        for item in organizations[selected_organization_code]["products"]
                        if item["product_code"] == code
                    )
                ),
                key="control_studio_product",
                help="Choose a product when you want to record SoA, implementation, and testing details for that scope.",
            )
        selected_scope = scope_lookup.get((selected_organization_code, selected_product_code))

        comparison_candidates = [
            item["label"]
            for item in scopes
            if item["label"] != (selected_scope["label"] if selected_scope else "")
            and (not selected_organization_code or item["organization_code"] == selected_organization_code)
        ]
        with filters[2]:
            selected_comparisons = st.multiselect(
                "Compare with",
                comparison_candidates,
                max_selections=3,
                key="control_studio_compare_scopes",
                help="Bring in a few other products from the same organization to compare applicability and implementation status at a glance.",
            )
        with filters[3]:
            framework_filter = st.multiselect(
                "Standards shown",
                framework_codes,
                default=[code for code in framework_codes if code in {SCF_PIVOT_FRAMEWORK_CODE, "ISO27001_2022"}] or framework_codes[:4],
                key="control_studio_framework_filter",
            )
        with filters[4]:
            search = st.text_input("Find", key="control_studio_search")

        comparison_scope_keys = [
            matrix.scope_key(item["organization_code"], item["product_code"])
            for label in selected_comparisons
            for item in scopes
            if item["label"] == label
        ]
        comparison_scope_keys = list(dict.fromkeys(comparison_scope_keys))

        control_rows = workbook.control_register_rows(
            organization_code=selected_scope["organization_code"] if selected_scope else None,
            product_code=selected_scope["product_code"] if selected_scope else None,
            comparison_scope_keys=comparison_scope_keys,
            framework_codes=framework_filter or None,
            search=search,
        )
        mapping_rows = workbook.mapping_rows(framework_codes=framework_filter or None, search=search)
        testing_rows = (
            workbook.testing_rows(
                organization_code=selected_scope["organization_code"],
                product_code=selected_scope["product_code"],
                framework_codes=framework_filter or None,
                search=search,
            )
            if selected_scope
            else []
        )
        requirement_rows = workbook.imported_requirement_rows(
            framework_codes=framework_filter or None,
            search=search,
        )
        framework_rows = workbook.framework_rows()

        metrics = st.columns(5)
        with metrics[0]:
            _metric("Pivot baseline", pivot_code or "Not set")
        with metrics[1]:
            _metric("SCF controls", str(len(control_rows)))
        with metrics[2]:
            approved = session.scalar(
                select(func.count()).select_from(UnifiedControlMapping).where(UnifiedControlMapping.approval_status == "approved")
            ) or 0
            _metric("Approved mappings", str(approved))
        with metrics[3]:
            _metric("Imported requirements", str(len(requirement_rows)))
        with metrics[4]:
            _metric("Working mode", selected_scope["label"] if selected_scope else "Baseline only")

        action_bar = st.columns([0.9, 0.9, 0.9, 1.3])
        with action_bar[0]:
            st.download_button(
                "Export workbook (.xlsx)",
                data=workbook.export_workbook_bytes(
                    organization_code=selected_scope["organization_code"] if selected_scope else None,
                    product_code=selected_scope["product_code"] if selected_scope else None,
                    comparison_scope_keys=comparison_scope_keys,
                    framework_codes=framework_filter or None,
                    search=search,
                ),
                file_name="my_grc_control_framework_workbook.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        with action_bar[1]:
            if st.button("Create starter local path", key="control_studio_bootstrap_local", width="stretch"):
                try:
                    result = uplift.ensure_phase1_backbone_path()
                    st.success(
                        "Created the starter local SCF path for "
                        f"{result['organization_code']} / {result['product_code']}."
                    )
                except Exception as exc:
                    render_user_error(
                        title="Could not create the starter local path",
                        exc=exc,
                        fallback="The starter local path could not be created right now.",
                        key_prefix="control_studio_bootstrap_local_error",
                    )
        with action_bar[2]:
            if st.button("Open Portfolio", key="control_studio_open_portfolio", width="stretch"):
                jump_to_page("Portfolio")
        with action_bar[3]:
            st.caption(
                "Workbook rule: baseline tabs define the shared SCF library; scope tabs define how a chosen organization and product implement and test those controls."
            )

        guidance = matrix.setup_guidance(
            organization_code=selected_scope["organization_code"] if selected_scope else None,
            product_code=selected_scope["product_code"] if selected_scope else None,
        )
        if guidance:
            with st.expander("What still needs to be prepared", expanded=not control_rows or not selected_scope):
                for index, item in enumerate(guidance):
                    render_prerequisite_block(
                        title=item["title"],
                        detail=item["detail"],
                        links=[(f"Open {item['page']}", item["page"])],
                        key_prefix=f"control_studio_guidance_{index}",
                    )

        baseline_columns = [
            "SCF Control",
            "Control Name",
            "Domain",
            "Family",
            "Requirement Coverage Summary",
            "Implementation Guidance",
            "Test Guidance",
            "Control Type",
            "Default Severity",
            "Mapped Standards",
            "Mapped Requirements",
        ]
        comparison_columns = [
            column
            for column in (pd.DataFrame(control_rows).columns if control_rows else [])
            if column.endswith(" SoA") or column.endswith(" Impl")
        ]
        scope_columns = [
            "SCF Control",
            "Control Name",
            "Mapped Standards",
            "Mapped Requirements",
            "SoA",
            "SoA Rationale",
            "Implementation Status",
            "Assessment Mode",
            "Implementation Narrative",
            "AWS Narrative",
            "Testing Plan",
            "Evidence Strategy",
            "Owner",
            "Lifecycle",
            "Priority",
            "Maturity Governance",
            "Maturity Implementation",
            "Maturity Observability",
            "Maturity Automation",
            "Maturity Assurance",
            "Current Evidence Plan",
            "Current AWS Target",
        ] + comparison_columns

        tabs = st.tabs(
            [
                "1. SCF Register",
                "2. Scope Implementation",
                "3. Testing & Evidence",
                "4. Requirement Mappings",
                "5. Standards & Imports",
                "6. Copilot & Review",
            ]
        )

        with tabs[0]:
            st.caption(
                "Use this like the master spreadsheet for your unified control baseline. This is where you shape the SCF control wording and keep the common implementation and test guidance clean."
            )
            baseline_frame = _subset_frame(control_rows, baseline_columns)
            edited_baseline_frame = st.data_editor(
                baseline_frame,
                width="stretch",
                hide_index=True,
                key="control_studio_baseline_editor",
                num_rows="dynamic",
                disabled=["Mapped Standards", "Mapped Requirements"],
                column_config={
                    "Default Severity": st.column_config.SelectboxColumn(
                        "Default Severity",
                        options=["low", "medium", "high", "critical"],
                    ),
                },
            )
            baseline_actions = st.columns([0.9, 0.9, 0.9, 1.1])
            with baseline_actions[0]:
                if st.button("Apply baseline changes", type="primary", key="control_studio_apply_baseline", width="stretch"):
                    try:
                        result = workbook.apply_control_register_rows(edited_baseline_frame.to_dict(orient="records"))
                        _show_apply_result(result, "baseline row(s)")
                    except Exception as exc:
                        render_user_error(
                            title="Could not apply the baseline changes",
                            exc=exc,
                            fallback="The SCF baseline changes could not be applied right now.",
                            key_prefix="control_studio_apply_baseline_error",
                        )
            with baseline_actions[1]:
                st.download_button(
                    "Export sheet",
                    data=_csv_bytes(edited_baseline_frame.to_dict(orient="records")),
                    file_name="my_grc_scf_register.csv",
                    mime="text/csv",
                    width="stretch",
                )
            with baseline_actions[2]:
                st.download_button(
                    "Blank template",
                    data=_empty_csv_bytes(baseline_columns),
                    file_name="my_grc_scf_register_template.csv",
                    mime="text/csv",
                    width="stretch",
                )
            with baseline_actions[3]:
                uploaded_baseline = st.file_uploader(
                    "Drag and drop a register CSV or Excel file",
                    type=["csv", "xlsx", "xls"],
                    key="control_studio_upload_baseline",
                )
                if uploaded_baseline is not None and st.button(
                    "Import into SCF Register",
                    key="control_studio_import_baseline",
                    width="stretch",
                ):
                    try:
                        result = workbook.apply_control_register_rows(_uploaded_rows(workbook, uploaded_baseline))
                        _show_apply_result(result, "baseline row(s)")
                    except Exception as exc:
                        render_user_error(
                            title="Could not import the SCF register sheet",
                            exc=exc,
                            fallback="The uploaded SCF register sheet could not be applied right now.",
                            key_prefix="control_studio_import_baseline_error",
                        )

        with tabs[1]:
            st.caption(
                "Choose an organization and product at the top, then use this worksheet to write the SoA, rationale, implementation wording, ownership, and maturity for that scope."
            )
            if not selected_scope:
                render_prerequisite_block(
                    title="Choose an organization and product first",
                    detail="Scope implementation data belongs to a specific organization and product. Choose the scope at the top of the page first.",
                    links=[("Open Portfolio", "Portfolio")],
                    key_prefix="control_studio_scope_required",
                )
            else:
                scope_frame = _subset_frame(control_rows, scope_columns)
                edited_scope_frame = st.data_editor(
                    scope_frame,
                    width="stretch",
                    hide_index=True,
                    key="control_studio_scope_editor",
                    disabled=[
                        "Mapped Standards",
                        "Mapped Requirements",
                        "Current Evidence Plan",
                        "Current AWS Target",
                    ] + comparison_columns,
                    column_config={
                        "SoA": st.column_config.SelectboxColumn(
                            "SoA",
                            options=["applicable", "planned", "inherited", "not_applicable"],
                        ),
                        "Implementation Status": st.column_config.SelectboxColumn(
                            "Implementation Status",
                            options=["planned", "draft", "implemented", "operational"],
                        ),
                        "Assessment Mode": st.column_config.SelectboxColumn(
                            "Assessment Mode",
                            options=["manual", "assisted", "autonomous"],
                        ),
                        "Lifecycle": st.column_config.SelectboxColumn(
                            "Lifecycle",
                            options=["design", "build", "operate", "review", "retire"],
                        ),
                        "Priority": st.column_config.SelectboxColumn(
                            "Priority",
                            options=["low", "medium", "high", "critical"],
                        ),
                    },
                )
                scope_actions = st.columns([0.9, 0.9, 0.9, 1.1])
                with scope_actions[0]:
                    if st.button("Apply scope changes", type="primary", key="control_studio_apply_scope", width="stretch"):
                        try:
                            result = workbook.apply_control_register_rows(
                                edited_scope_frame.to_dict(orient="records"),
                                organization_code=selected_scope["organization_code"],
                                product_code=selected_scope["product_code"],
                            )
                            _show_apply_result(result, "scope row(s)")
                        except Exception as exc:
                            render_user_error(
                                title="Could not apply the scope changes",
                                exc=exc,
                                fallback="The scoped implementation changes could not be applied right now.",
                                key_prefix="control_studio_apply_scope_error",
                            )
                with scope_actions[1]:
                    st.download_button(
                        "Export sheet",
                        data=_csv_bytes(edited_scope_frame.to_dict(orient="records")),
                        file_name=f"my_grc_scope_{selected_scope['organization_code']}_{selected_scope['product_code']}.csv",
                        mime="text/csv",
                        width="stretch",
                    )
                with scope_actions[2]:
                    st.download_button(
                        "Blank template",
                        data=_empty_csv_bytes(scope_columns),
                        file_name="my_grc_scope_template.csv",
                        mime="text/csv",
                        width="stretch",
                    )
                with scope_actions[3]:
                    uploaded_scope = st.file_uploader(
                        "Drag and drop a scope worksheet",
                        type=["csv", "xlsx", "xls"],
                        key="control_studio_upload_scope",
                    )
                    if uploaded_scope is not None and st.button(
                        "Import into Scope Implementation",
                        key="control_studio_import_scope",
                        width="stretch",
                    ):
                        try:
                            result = workbook.apply_control_register_rows(
                                _uploaded_rows(workbook, uploaded_scope),
                                organization_code=selected_scope["organization_code"],
                                product_code=selected_scope["product_code"],
                            )
                            _show_apply_result(result, "scope row(s)")
                        except Exception as exc:
                            render_user_error(
                                title="Could not import the scope worksheet",
                                exc=exc,
                                fallback="The uploaded scope worksheet could not be applied right now.",
                                key_prefix="control_studio_import_scope_error",
                            )

        with tabs[2]:
            st.caption(
                "Use this worksheet for testing methods, evidence strategies, review frequency, and AWS live-collection targets. Leave AWS fields blank for manual or offline evidence."
            )
            if not selected_scope:
                render_prerequisite_block(
                    title="Choose an organization and product first",
                    detail="Testing and evidence data belongs to a specific organization and product. Choose the scope at the top of the page first.",
                    links=[("Open Portfolio", "Portfolio")],
                    key_prefix="control_studio_testing_scope_required",
                )
            else:
                testing_columns = [
                    "SCF Control",
                    "Control Name",
                    "Plan Code",
                    "Plan Name",
                    "Plan Status",
                    "Execution Mode",
                    "Evidence Type",
                    "Collector Key",
                    "Review Frequency",
                    "Evidence Strategy",
                    "Implementation Test Plan",
                    "Instructions",
                    "Expected Artifacts JSON",
                    "Binding",
                    "Target Code",
                    "AWS Profile",
                    "AWS Account ID",
                    "AWS Role",
                    "AWS Regions",
                    "Target Status",
                    "Target Notes",
                ]
                testing_frame = _subset_frame(testing_rows, testing_columns)
                edited_testing_frame = st.data_editor(
                    testing_frame,
                    width="stretch",
                    hide_index=True,
                    key="control_studio_testing_editor",
                    num_rows="dynamic",
                    disabled=["SCF Control", "Control Name", "Plan Code", "Target Code"],
                    column_config={
                        "Plan Status": st.column_config.SelectboxColumn(
                            "Plan Status",
                            options=["draft", "approved", "active", "published"],
                        ),
                        "Execution Mode": st.column_config.SelectboxColumn(
                            "Execution Mode",
                            options=["manual", "assisted", "autonomous"],
                        ),
                        "Evidence Type": st.column_config.SelectboxColumn(
                            "Evidence Type",
                            options=["manual_artifact", "configuration_snapshot", "api_payload", "report", "screenshot"],
                        ),
                        "Review Frequency": st.column_config.SelectboxColumn(
                            "Review Frequency",
                            options=["monthly", "quarterly", "yearly", "on_demand"],
                        ),
                        "Target Status": st.column_config.SelectboxColumn(
                            "Target Status",
                            options=["draft", "approved", "active", "retired"],
                        ),
                    },
                )
                testing_actions = st.columns([0.9, 0.9, 0.9, 1.1])
                with testing_actions[0]:
                    if st.button("Apply testing changes", type="primary", key="control_studio_apply_testing", width="stretch"):
                        try:
                            result = workbook.apply_testing_rows(
                                edited_testing_frame.to_dict(orient="records"),
                                organization_code=selected_scope["organization_code"],
                                product_code=selected_scope["product_code"],
                            )
                            _show_apply_result(result, "testing row(s)")
                        except Exception as exc:
                            render_user_error(
                                title="Could not apply the testing changes",
                                exc=exc,
                                fallback="The testing and evidence changes could not be applied right now.",
                                key_prefix="control_studio_apply_testing_error",
                            )
                with testing_actions[1]:
                    st.download_button(
                        "Export sheet",
                        data=_csv_bytes(edited_testing_frame.to_dict(orient="records")),
                        file_name="my_grc_testing_and_evidence.csv",
                        mime="text/csv",
                        width="stretch",
                    )
                with testing_actions[2]:
                    st.download_button(
                        "Blank template",
                        data=_empty_csv_bytes(testing_columns),
                        file_name="my_grc_testing_and_evidence_template.csv",
                        mime="text/csv",
                        width="stretch",
                    )
                with testing_actions[3]:
                    uploaded_testing = st.file_uploader(
                        "Drag and drop a testing worksheet",
                        type=["csv", "xlsx", "xls"],
                        key="control_studio_upload_testing",
                    )
                    if uploaded_testing is not None and st.button(
                        "Import into Testing & Evidence",
                        key="control_studio_import_testing",
                        width="stretch",
                    ):
                        try:
                            result = workbook.apply_testing_rows(
                                _uploaded_rows(workbook, uploaded_testing),
                                organization_code=selected_scope["organization_code"],
                                product_code=selected_scope["product_code"],
                            )
                            _show_apply_result(result, "testing row(s)")
                        except Exception as exc:
                            render_user_error(
                                title="Could not import the testing worksheet",
                                exc=exc,
                                fallback="The uploaded testing worksheet could not be applied right now.",
                                key_prefix="control_studio_import_testing_error",
                            )

        with tabs[3]:
            st.caption(
                "Manage requirement traceability here. Add or update mapped relationships between the SCF pivot baseline and the standards or regulations you import."
            )
            mapping_columns = [
                "SCF Control",
                "SCF Name",
                "Framework",
                "Requirement",
                "Requirement Title",
                "Mapping Status",
                "Mapping Type",
                "Confidence",
                "Inheritance Strategy",
                "Rationale",
                "Reviewed By",
                "Approval Notes",
            ]
            mapping_frame = _subset_frame(mapping_rows, mapping_columns)
            edited_mapping_frame = st.data_editor(
                mapping_frame,
                width="stretch",
                hide_index=True,
                key="control_studio_mapping_editor",
                num_rows="dynamic",
                disabled=["Requirement Title", "SCF Name"],
                column_config={
                    "Framework": st.column_config.SelectboxColumn("Framework", options=framework_codes),
                    "Mapping Status": st.column_config.SelectboxColumn("Mapping Status", options=["approved", "proposed", "rejected"]),
                    "Mapping Type": st.column_config.SelectboxColumn("Mapping Type", options=["mapped", "partial", "supporting", "gap"]),
                    "Inheritance Strategy": st.column_config.SelectboxColumn(
                        "Inheritance Strategy",
                        options=["manual_review", "direct", "shared_control", "product_specific"],
                    ),
                    "Confidence": st.column_config.NumberColumn("Confidence", min_value=0.0, max_value=1.0, step=0.01),
                },
            )
            mapping_actions = st.columns([0.9, 0.9, 0.9, 1.1])
            with mapping_actions[0]:
                if st.button("Apply mapping changes", type="primary", key="control_studio_apply_mappings", width="stretch"):
                    try:
                        result = workbook.apply_mapping_rows(edited_mapping_frame.to_dict(orient="records"))
                        _show_apply_result(result, "mapping row(s)")
                    except Exception as exc:
                        render_user_error(
                            title="Could not apply the mapping changes",
                            exc=exc,
                            fallback="The mapping changes could not be applied right now.",
                            key_prefix="control_studio_apply_mappings_error",
                        )
            with mapping_actions[1]:
                st.download_button(
                    "Export sheet",
                    data=_csv_bytes(edited_mapping_frame.to_dict(orient="records")),
                    file_name="my_grc_requirement_mappings.csv",
                    mime="text/csv",
                    width="stretch",
                )
            with mapping_actions[2]:
                st.download_button(
                    "Blank template",
                    data=_empty_csv_bytes(mapping_columns),
                    file_name="my_grc_requirement_mappings_template.csv",
                    mime="text/csv",
                    width="stretch",
                )
            with mapping_actions[3]:
                uploaded_mappings = st.file_uploader(
                    "Drag and drop a mapping worksheet",
                    type=["csv", "xlsx", "xls"],
                    key="control_studio_upload_mappings",
                )
                if uploaded_mappings is not None and st.button(
                    "Import into Requirement Mappings",
                    key="control_studio_import_mappings",
                    width="stretch",
                ):
                    try:
                        result = workbook.apply_mapping_rows(_uploaded_rows(workbook, uploaded_mappings))
                        _show_apply_result(result, "mapping row(s)")
                    except Exception as exc:
                        render_user_error(
                            title="Could not import the mapping worksheet",
                            exc=exc,
                            fallback="The uploaded mapping worksheet could not be applied right now.",
                            key_prefix="control_studio_import_mappings_error",
                        )
            suggestion_count = session.scalar(
                select(func.count()).select_from(AISuggestion).where(AISuggestion.accepted.is_(False))
            ) or 0
            if suggestion_count:
                st.info(f"{suggestion_count} AI suggestion(s) are waiting for review.")
                if st.button("Open Review Queue", key="control_studio_open_review_queue", width="stretch"):
                    jump_to_page("Review Queue")

        with tabs[4]:
            st.caption(
                "Keep your standards library tidy here, then drag-and-drop spreadsheets to load new regulatory or standards content while preserving traceability to the source rows."
            )
            library_tabs = st.tabs(["Framework Library", "Imported Requirements", "Import Source"])

            with library_tabs[0]:
                framework_columns = [
                    "Framework",
                    "Name",
                    "Version",
                    "Category",
                    "Issuing Body",
                    "Jurisdiction",
                    "Source URL",
                    "Description",
                    "Lifecycle",
                    "Controls",
                ]
                framework_frame = _subset_frame(framework_rows, framework_columns)
                edited_framework_frame = st.data_editor(
                    framework_frame,
                    width="stretch",
                    hide_index=True,
                    key="control_studio_framework_editor",
                    num_rows="dynamic",
                    disabled=["Controls"],
                    column_config={
                        "Category": st.column_config.SelectboxColumn(
                            "Category",
                            options=["framework", "policy", "procedure", "metaframework"],
                        ),
                        "Lifecycle": st.column_config.SelectboxColumn(
                            "Lifecycle",
                            options=["draft", "active", "inactive", "retired"],
                        ),
                    },
                )
                framework_actions = st.columns([0.9, 0.9, 0.9])
                with framework_actions[0]:
                    if st.button("Apply framework changes", type="primary", key="control_studio_apply_frameworks", width="stretch"):
                        try:
                            result = workbook.apply_framework_rows(edited_framework_frame.to_dict(orient="records"))
                            _show_apply_result(result, "framework row(s)")
                        except Exception as exc:
                            render_user_error(
                                title="Could not apply the framework changes",
                                exc=exc,
                                fallback="The framework changes could not be applied right now.",
                                key_prefix="control_studio_apply_frameworks_error",
                            )
                with framework_actions[1]:
                    st.download_button(
                        "Export sheet",
                        data=_csv_bytes(edited_framework_frame.to_dict(orient="records")),
                        file_name="my_grc_framework_library.csv",
                        mime="text/csv",
                        width="stretch",
                    )
                with framework_actions[2]:
                    st.download_button(
                        "Blank template",
                        data=_empty_csv_bytes(framework_columns),
                        file_name="my_grc_framework_library_template.csv",
                        mime="text/csv",
                        width="stretch",
                    )

            with library_tabs[1]:
                requirement_columns = [
                    "Framework",
                    "Requirement",
                    "Title",
                    "Description",
                    "Source Domain",
                    "Source Family",
                    "Source Section",
                    "Source Reference",
                    "Row Number",
                    "Import Action",
                ]
                requirement_frame = _subset_frame(requirement_rows, requirement_columns)
                st.data_editor(
                    requirement_frame,
                    width="stretch",
                    hide_index=True,
                    key="control_studio_requirement_editor",
                    disabled=requirement_columns,
                )
                st.download_button(
                    "Export sheet",
                    data=_csv_bytes(requirement_rows),
                    file_name="my_grc_imported_requirements.csv",
                    mime="text/csv",
                    width="stretch",
                )

            with library_tabs[2]:
                uploaded_source = st.file_uploader(
                    "Drag and drop a regulation, policy, or standard spreadsheet",
                    type=["csv", "xlsx", "xls"],
                    key="control_studio_upload_framework_source",
                )
                if uploaded_source is not None:
                    source_path = _save_upload(uploaded_source)
                    try:
                        suffix = Path(uploaded_source.name).suffix.lower()
                        sheet_name = ""
                        if suffix in {".xlsx", ".xls"}:
                            sheets = importer.available_sheets(source_path)
                            if sheets:
                                sheet_name = st.selectbox("Worksheet", sheets, key="control_studio_import_sheet")
                        preview = importer.preview_source(source_path, sheet_name=sheet_name or "")
                        st.dataframe(pd.DataFrame(preview["records"]), width="stretch", hide_index=True)

                        import_mode = st.selectbox(
                            "Import mode",
                            ["Refresh SCF pivot", "Import into existing framework", "Create new framework from source"],
                            key="control_studio_import_mode",
                        )
                        mapping_mode = st.selectbox(
                            "Mapping strategy",
                            ["suggest_only", "map_existing", "create_baseline", "none"],
                            key="control_studio_import_mapping_mode",
                        )
                        auto_approve = st.checkbox("Auto-approve high-confidence mappings", value=False)
                        threshold = st.slider(
                            "Auto-mapping threshold",
                            0.5,
                            1.0,
                            0.84,
                            0.01,
                            key="control_studio_import_threshold",
                        )
                        target_framework_code = ""
                        new_framework_code = ""
                        new_framework_name = ""
                        new_framework_version = ""
                        if import_mode == "Import into existing framework":
                            target_framework_code = st.selectbox(
                                "Target framework",
                                framework_codes,
                                key="control_studio_target_framework",
                            )
                        elif import_mode == "Create new framework from source":
                            new_framework_code = st.text_input("Framework code", key="control_studio_new_framework_code")
                            new_framework_name = st.text_input("Framework name", key="control_studio_new_framework_name")
                            new_framework_version = st.text_input("Version", key="control_studio_new_framework_version")

                        if st.button("Run source import", type="primary", key="control_studio_run_import", width="stretch"):
                            try:
                                if import_mode == "Refresh SCF pivot":
                                    result = importer.import_secure_controls_framework(
                                        file_path=source_path,
                                        sheet_name=sheet_name or "SCF 2025.3.1",
                                        actor="control_framework_studio",
                                        auto_mapping_threshold=threshold,
                                        auto_approve_mappings=auto_approve,
                                    )
                                    st.success(f"Imported {result['summary']['imported_count']} SCF row(s).")
                                elif import_mode == "Import into existing framework":
                                    target_framework = next(item for item in frameworks if item.code == target_framework_code)
                                    result = importer.import_source(
                                        file_path=source_path,
                                        framework_code=target_framework.code,
                                        framework_name=target_framework.name,
                                        framework_version=target_framework.version,
                                        source_name=uploaded_source.name,
                                        source_type="spreadsheet" if suffix in {".xlsx", ".xls"} else "csv",
                                        sheet_name=sheet_name,
                                        mapping_mode=mapping_mode,
                                        auto_mapping_threshold=threshold,
                                        auto_approve_mappings=auto_approve,
                                        category=target_framework.category or "framework",
                                        description=target_framework.description or "",
                                        issuing_body=target_framework.issuing_body or "",
                                        jurisdiction=target_framework.jurisdiction or "global",
                                    )
                                    st.success(f"Imported {result['summary']['imported_count']} row(s) into {target_framework.code}.")
                                else:
                                    result = importer.import_source(
                                        file_path=source_path,
                                        framework_code=new_framework_code,
                                        framework_name=new_framework_name,
                                        framework_version=new_framework_version,
                                        source_name=uploaded_source.name,
                                        source_type="spreadsheet" if suffix in {".xlsx", ".xls"} else "csv",
                                        sheet_name=sheet_name,
                                        mapping_mode=mapping_mode,
                                        auto_mapping_threshold=threshold,
                                        auto_approve_mappings=auto_approve,
                                    )
                                    st.success(f"Created {result['framework'].code} and imported {result['summary']['imported_count']} row(s).")
                            except Exception as exc:
                                render_user_error(
                                    title="Could not import the framework source",
                                    exc=exc,
                                    fallback="The source file could not be imported right now.",
                                    key_prefix="control_studio_import_source_error",
                                )
                    finally:
                        Path(source_path).unlink(missing_ok=True)

        with tabs[5]:
            st.caption(
                "Use governed copilot help when you want faster drafting with traceable citations. It should support the workbook, not replace human judgment."
            )
            packs = knowledge_packs.list_packs()
            if not packs:
                render_prerequisite_block(
                    title="No governed copilot pack is available yet",
                    detail="Seed the knowledge pack templates if you want help drafting mapping rationale or implementation wording from the SCF workbook.",
                    key_prefix="control_studio_no_packs",
                )
                if st.button("Seed knowledge pack templates", key="control_studio_seed_packs", type="primary", width="stretch"):
                    try:
                        touched = knowledge_packs.seed_templates()
                        st.success(f"Synchronized {len(touched)} knowledge pack template(s).")
                    except Exception as exc:
                        render_user_error(
                            title="Could not seed the knowledge pack templates",
                            exc=exc,
                            fallback="The knowledge pack templates could not be synchronized right now.",
                            key_prefix="control_studio_seed_packs_error",
                        )
            elif not mapping_rows:
                render_prerequisite_block(
                    title="Create at least one mapped control path first",
                    detail="The copilot is most useful once an SCF control is already mapped to at least one requirement from a standard or regulation.",
                    key_prefix="control_studio_copilot_needs_mapping",
                )
            else:
                pack_codes = [item.pack_code for item in packs]
                selected_pack_code = st.selectbox(
                    "Knowledge pack",
                    pack_codes,
                    index=_option_index(
                        pack_codes,
                        knowledge_packs.default_pack_code() if knowledge_packs.default_pack_code() in pack_codes else pack_codes[0],
                    ),
                    key="control_studio_pack_code",
                )
                task_rows = knowledge_packs.list_tasks(selected_pack_code)
                selected_task = st.selectbox(
                    "Copilot task",
                    [item.task_key for item in task_rows],
                    key="control_studio_pack_task",
                )
                mapping_choice = st.selectbox(
                    "Mapped control path",
                    [f"{row['Framework']}::{row['Requirement']}::{row['SCF Control']}" for row in mapping_rows],
                    key="control_studio_pack_mapping_choice",
                )
                framework_code, control_id, unified_control_code = mapping_choice.split("::", 2)
                if st.button("Prepare governed draft", type="primary", key="control_studio_prepare_draft", width="stretch"):
                    try:
                        bundle = knowledge_packs.build_task_package(
                            pack_code=selected_pack_code,
                            task_key=selected_task,
                            framework_code=framework_code,
                            control_id=control_id,
                            unified_control_code=unified_control_code,
                            organization_code=selected_scope["organization_code"] if selected_scope else None,
                            product_code=selected_scope["product_code"] if selected_scope else None,
                        )
                        st.session_state["control_studio_pack_bundle"] = {
                            "prompt_package": bundle["prompt_package"],
                            "draft_response": bundle["draft_response"],
                            "citations": bundle["citations"],
                        }
                        st.success("Governed draft package prepared.")
                    except Exception as exc:
                        render_user_error(
                            title="Could not prepare the governed draft",
                            exc=exc,
                            fallback="The governed draft package could not be prepared right now.",
                            key_prefix="control_studio_prepare_draft_error",
                        )
                bundle = st.session_state.get("control_studio_pack_bundle")
                if bundle:
                    pack_tabs = st.tabs(["Prompt Package", "Draft Response", "Citations"])
                    with pack_tabs[0]:
                        st.code(bundle["prompt_package"], language="markdown")
                    with pack_tabs[1]:
                        st.code(bundle["draft_response"], language="markdown")
                    with pack_tabs[2]:
                        st.dataframe(pd.DataFrame(bundle["citations"]), width="stretch", hide_index=True)
                    if st.button("Open Review Queue", key="control_studio_open_review_queue_bundle", width="stretch"):
                        jump_to_page("Review Queue")
