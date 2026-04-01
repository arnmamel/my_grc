from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import select

from aws_local_audit.db import session_scope
from aws_local_audit.models import Framework
from aws_local_audit.services.control_matrix import SCF_PIVOT_FRAMEWORK_CODE, ControlMatrixService
from aws_local_audit.services.foundation_uplift import FoundationUpliftService
from aws_local_audit.services.framework_imports import FrameworkImportService
from aws_local_audit.services.frameworks import FrameworkService
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.workbench import WorkbenchService
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


def _save_upload(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix or ".tmp"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(uploaded_file.getvalue())
        return handle.name


def render_guided_setup() -> None:
    _hero(
        "Guided Setup",
        "Set up the SCF baseline, create the working scope, and only configure AWS when you are ready to collect live evidence.",
    )
    st.markdown(
        '<div class="section-note">This setup is intentionally scope-first. You do not need an AWS profile to start using the platform. First establish the control backbone and the organization/product scope, then add AWS access later when you want live evidence collection.</div>',
        unsafe_allow_html=True,
    )

    with session_scope() as session:
        governance = GovernanceService(session)
        framework_service = FrameworkService(session)
        importer = FrameworkImportService(session)
        workbench = WorkbenchService(session)
        matrix = ControlMatrixService(session)
        foundation = FoundationUpliftService(session)
        onboarding = governance.onboarding_status()
        scopes = matrix.available_scopes()
        frameworks = session.scalars(select(Framework).order_by(Framework.code)).all()

        metrics = st.columns(5)
        with metrics[0]:
            _metric("SCF Pivot", governance.pivot_framework_code() or "Not set")
        with metrics[1]:
            _metric("Frameworks", str(onboarding["counts"]["frameworks"]))
        with metrics[2]:
            _metric("Organizations", str(onboarding["counts"]["organizations"]))
        with metrics[3]:
            _metric("Products", str(onboarding["counts"]["products"]))
        with metrics[4]:
            _metric("AWS Profiles", str(onboarding["counts"]["aws_profiles"]), "Optional until live evidence runs")

        tabs = st.tabs(
            [
                "1. Foundation",
                "2. SCF Baseline",
                "3. Organizations & Products",
                "4. What Comes Next",
            ]
        )

        with tabs[0]:
            st.markdown(
                """
### What happens here

1. Seed the built-in standards catalog.
2. Make SCF the pivot baseline.
3. Optionally bootstrap a local example path so the first matrix is not empty.

AWS connectivity is not part of the first-run requirement.
"""
            )
            if st.button("Seed baseline framework catalog", type="primary", key="setup_seed_frameworks"):
                touched = framework_service.seed_templates()
                governance.set_pivot_framework_code(
                    SCF_PIVOT_FRAMEWORK_CODE,
                    "Secure Controls Framework is the pivot baseline for the unified control model.",
                )
                st.success(f"Synchronized {len(touched)} framework template(s) and set SCF as the pivot baseline.")

            if st.button("Bootstrap a local SCF example path", key="setup_bootstrap_example"):
                try:
                    result = foundation.ensure_phase1_backbone_path()
                    st.success(
                        f"Created a working example for {result['organization_code']} / {result['product_code']} with control {result['unified_control_code']}."
                    )
                except Exception as exc:
                    render_user_error(
                        title="Could not bootstrap the local example path",
                        exc=exc,
                        fallback="The workspace could not create the initial SCF example path right now.",
                        next_steps=[
                            "Seed the framework catalog first.",
                            "If the issue continues, create the organization and product manually, then come back here.",
                        ],
                        links=[("Open Portfolio", "Portfolio"), ("Open Control Studio", "Control Framework Studio")],
                        key_prefix="setup_bootstrap_error",
                    )

            if frameworks:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Framework": item.code,
                                "Name": item.name,
                                "Version": item.version,
                                "Source": item.source,
                            }
                            for item in frameworks
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                render_prerequisite_block(
                    title="No frameworks are loaded yet",
                    detail="Seed the baseline framework catalog first so the SCF matrix has something to work with.",
                )

        with tabs[1]:
            scf_framework = next((item for item in frameworks if item.code == SCF_PIVOT_FRAMEWORK_CODE), None)
            if scf_framework is None:
                render_prerequisite_block(
                    title="SCF is not available yet",
                    detail="Upload the latest SCF workbook or seed a baseline to establish the unified control framework.",
                )
            uploaded = st.file_uploader(
                "Upload the Secure Controls Framework workbook",
                type=["xlsx", "xls"],
                key="setup_scf_workbook",
                help="Use the latest SCF spreadsheet here to populate the pivot baseline with full source traceability.",
            )
            if uploaded is not None and st.button("Import SCF workbook", key="setup_import_scf", type="primary"):
                source_path = _save_upload(uploaded)
                try:
                    result = importer.import_secure_controls_framework(
                        file_path=source_path,
                        sheet_name="SCF 2025.3.1",
                        actor="guided_setup",
                        auto_mapping_threshold=0.9,
                        auto_approve_mappings=False,
                    )
                    st.success(
                        f"Imported {result['summary']['imported_count']} SCF rows and refreshed the pivot baseline."
                    )
                except Exception as exc:
                    render_user_error(
                        title="SCF import failed",
                        exc=exc,
                        fallback="The workbook could not be imported. Please check the file format and sheet names.",
                        next_steps=[
                            "Confirm the file is the Secure Controls Framework workbook.",
                            "If needed, open Control Framework Studio and use the import tools there.",
                        ],
                        links=[("Open Control Studio", "Control Framework Studio")],
                        key_prefix="setup_import_scf_error",
                    )
                finally:
                    Path(source_path).unlink(missing_ok=True)

            st.caption(
                "Once SCF is loaded, the main work happens in Control Framework Studio as a single table-like control matrix."
            )
            if st.button("Open Control Framework Studio", key="setup_open_control_studio"):
                jump_to_page("Control Framework Studio")

        with tabs[2]:
            left, right = st.columns(2)
            with left:
                with st.form("setup_org_form"):
                    st.markdown("### Organization")
                    org_name = st.text_input("Organization name")
                    org_code = st.text_input("Organization code")
                    org_description = st.text_area("Description", height=100)
                    save_org = st.form_submit_button("Save organization", type="primary")
                if save_org and org_name:
                    try:
                        organization = workbench.create_organization(
                            name=org_name,
                            code=org_code or None,
                            description=org_description,
                        )
                        st.success(f"Organization ready: {organization.code}")
                    except Exception as exc:
                        render_user_error(
                            title="Could not save the organization",
                            exc=exc,
                            fallback="The organization could not be saved right now.",
                            key_prefix="setup_org_error",
                        )
            with right:
                st.markdown("### Product")
            org_codes = [item.code for item in workbench.list_organizations()]
            if org_codes:
                with st.form("setup_product_real_form"):
                    selected_org = st.selectbox("Organization", org_codes, key="setup_product_org")
                    product_name = st.text_input("Product name")
                    product_code = st.text_input("Product code")
                    product_type = st.selectbox("Product type", ["service", "platform", "application", "component"])
                    deployment_model = st.selectbox("Deployment model", ["saas", "managed", "hybrid", "self-hosted"])
                    owner = st.text_input("Owner")
                    save_product = st.form_submit_button("Save product", type="primary")
                if save_product and product_name:
                    try:
                        product = workbench.create_product(
                            organization_code=selected_org,
                            name=product_name,
                            code=product_code or None,
                            product_type=product_type,
                            deployment_model=deployment_model,
                            owner=owner,
                        )
                        st.success(f"Product ready: {product.code}")
                    except Exception as exc:
                        render_user_error(
                            title="Could not save the product",
                            exc=exc,
                            fallback="The product could not be saved right now.",
                            key_prefix="setup_product_error",
                        )
            else:
                render_prerequisite_block(
                    title="Create an organization first",
                    detail="Products are defined inside organizations. Save an organization on the left first.",
                )

            if scopes:
                st.dataframe(
                    pd.DataFrame(scopes),
                    width="stretch",
                    hide_index=True,
                )
                if st.button("Open the SCF matrix for this scope", key="setup_open_matrix_scope"):
                    jump_to_page("Control Framework Studio")

        with tabs[3]:
            st.markdown(
                """
### After the initial setup

- Use `Control Framework Studio` to manage the SCF matrix, SoA decisions, implementation wording, mappings, and evidence plans.
- Use `Questionnaires` to upload a customer spreadsheet and get suggested answers from your stored implementation narratives.
- Use `AWS Profiles` only when you want live evidence collection.
- Use `Operations` when you are ready to collect evidence or run assessments.
"""
            )
            render_prerequisite_block(
                title="AWS is optional at startup",
                detail="You only need AWS CLI SSO profiles when you choose to collect live evidence or run a live assessment. Until then, the workspace remains fully usable offline with local metadata, mappings, SoA decisions, implementations, questionnaires, and reporting.",
                links=[
                    ("Open AWS Profiles", "AWS Profiles"),
                    ("Open Operations", "Operations"),
                    ("Open Questionnaires", "Questionnaires"),
                ],
                key_prefix="setup_next_steps",
            )
