from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import select

from aws_local_audit.db import session_scope
from aws_local_audit.models import AssessmentRun, AssessmentSchedule, OrganizationFrameworkBinding, Product
from aws_local_audit.services.assessments import AssessmentService
from aws_local_audit.services.evidence import EvidenceService
from aws_local_audit.services.readiness import OperationalReadinessService
from ui_support import render_prerequisite_block, render_user_error


def _hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero"><h1 style="margin:0;">{title}</h1><p style="margin:0.35rem 0 0 0;">{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def _save_upload(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix or ".tmp"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(uploaded_file.getvalue())
        return handle.name


def render_operations_workspace() -> None:
    _hero(
        "Operations",
        "Collect evidence and run assessments with clear prerequisites, product scope guidance, and no flavor-specific detours.",
    )
    st.markdown(
        '<div class="section-note">Use this page when you are ready to test a product scope. If information is still missing, the page explains exactly what to prepare and where to go.</div>',
        unsafe_allow_html=True,
    )

    with session_scope() as session:
        bindings = session.scalars(
            select(OrganizationFrameworkBinding).order_by(OrganizationFrameworkBinding.binding_code)
        ).all()
        if not bindings:
            render_prerequisite_block(
                title="No framework binding is available yet",
                detail="Create an organization, a product, and a framework binding first. You can leave AWS profile information blank until the day you want a live AWS run.",
                links=[("Open Portfolio", "Portfolio"), ("Open Guided Setup", "Wizards")],
                key_prefix="operations_missing_bindings",
            )
            return

        binding_code = st.selectbox(
            "Framework binding",
            [item.binding_code for item in bindings],
            key="operations_binding_code",
        )
        binding = next(item for item in bindings if item.binding_code == binding_code)
        products = session.scalars(
            select(Product).where(Product.organization_id == binding.organization_id).order_by(Product.code)
        ).all()
        product_code = st.selectbox(
            "Product scope",
            [""] + [item.code for item in products],
            help="Choose a product when the assessment should be product-specific. Leave empty for binding-level checks.",
            key="operations_product_code_v2",
        )

        readiness_service = OperationalReadinessService(session)
        evidence_service = EvidenceService(session)
        assessment_service = AssessmentService(session)

        tabs = st.tabs(["Readiness", "Evidence", "Assessments", "Schedules"])

        with tabs[0]:
            st.caption("Run this first when you want the app to tell you what is still missing.")
            if st.button("Check readiness", type="primary", key="operations_check_readiness"):
                try:
                    st.session_state["operations_readiness_v2"] = readiness_service.assess_binding(
                        binding_code=binding_code,
                        product_code=product_code or None,
                    )
                except Exception as exc:
                    render_user_error(
                        title="Could not calculate readiness",
                        exc=exc,
                        fallback="The workspace could not calculate readiness for the selected scope right now.",
                        links=[("Open Portfolio", "Portfolio"), ("Open Control Framework Studio", "Control Framework Studio")],
                        key_prefix="operations_readiness_error",
                    )
            readiness = st.session_state.get("operations_readiness_v2")
            if readiness:
                st.success(f"{readiness['readiness_status']} ({readiness['overall_score']:.1f}/4)")
                st.dataframe(pd.DataFrame(readiness["areas"]), width="stretch", hide_index=True)
                detail_cols = st.columns(2)
                with detail_cols[0]:
                    if readiness["blockers"]:
                        st.markdown("**What must be completed first**")
                        for item in readiness["blockers"][:8]:
                            st.markdown(f"- {item}")
                    else:
                        st.info("No hard blockers were found for this scope.")
                with detail_cols[1]:
                    if readiness["warnings"]:
                        st.markdown("**What should be improved**")
                        for item in readiness["warnings"][:8]:
                            st.markdown(f"- {item}")
                    else:
                        st.info("No additional warnings were found for this scope.")
            else:
                st.info("Run readiness to see blockers, warnings, and fit for execution.")

        with tabs[1]:
            info_cols = st.columns([0.65, 0.35])
            with info_cols[0]:
                if st.button("Preview collection plan", key="operations_preview_collection_plan"):
                    try:
                        st.session_state["operations_collection_plan_v2"] = evidence_service.build_collection_plan_for_binding(
                            binding_code=binding_code,
                            product_code=product_code or None,
                        )
                    except Exception as exc:
                        render_user_error(
                            title="Could not build the collection plan",
                            exc=exc,
                            fallback="The collection plan could not be prepared right now.",
                            links=[("Open Control Framework Studio", "Control Framework Studio")],
                            key_prefix="operations_collection_plan_error",
                        )
                plan = st.session_state.get("operations_collection_plan_v2")
                if plan:
                    st.dataframe(pd.DataFrame(plan["controls"]), width="stretch", hide_index=True)
                else:
                    st.info("Preview the collection plan to see which controls will be tested and which AWS profiles are needed.")
            with info_cols[1]:
                if st.button("Collect live evidence now", type="primary", key="operations_collect_live"):
                    try:
                        collected = evidence_service.collect_for_binding(
                            binding_code=binding_code,
                            product_code=product_code or None,
                        )
                        st.success(f"Collected {len(collected)} evidence item(s).")
                    except Exception as exc:
                        render_user_error(
                            title="Could not collect live evidence",
                            exc=exc,
                            fallback="The live evidence run could not be completed right now.",
                            next_steps=[
                                "Run readiness first to confirm the required AWS profiles and collection plans are ready.",
                                "If the control is still manual, upload manual evidence from the form below.",
                            ],
                            links=[("Open AWS Profiles", "AWS Profiles"), ("Open Control Framework Studio", "Control Framework Studio")],
                            key_prefix="operations_collect_error",
                        )

                st.markdown("**Manual evidence when automation is not ready**")
                controls = binding.framework.controls if binding.framework else []
                with st.form("operations_manual_evidence_form"):
                    control_id = st.selectbox(
                        "Requirement / control",
                        [item.control_id for item in controls] if controls else [""],
                    )
                    status = st.selectbox("Assessment result", ["pass", "fail", "not_applicable"])
                    summary = st.text_area("Evidence summary", height=100)
                    note = st.text_area("Practitioner note", height=80)
                    uploaded = st.file_uploader(
                        "Optional attachment",
                        key="operations_manual_evidence_upload",
                    )
                    publish_to_confluence = st.checkbox("Also publish to Confluence when configured", value=False)
                    submit_manual = st.form_submit_button("Store manual evidence")
                if submit_manual and control_id and summary.strip():
                    source_path = _save_upload(uploaded) if uploaded is not None else None
                    try:
                        item = evidence_service.upload_manual_evidence(
                            binding_code=binding_code,
                            control_id=control_id,
                            summary=summary,
                            status=status,
                            product_code=product_code or None,
                            note=note,
                            file_path=source_path,
                            uploaded_by="workspace_user",
                            publish_to_confluence=publish_to_confluence,
                        )
                        st.success(f"Stored manual evidence item {item.id}.")
                    except Exception as exc:
                        render_user_error(
                            title="Could not store the manual evidence",
                            exc=exc,
                            fallback="The manual evidence item could not be stored right now.",
                            key_prefix="operations_manual_evidence_error",
                        )
                    finally:
                        if source_path:
                            Path(source_path).unlink(missing_ok=True)

        with tabs[2]:
            readiness = st.session_state.get("operations_readiness_v2")
            if readiness and readiness["blockers"]:
                render_prerequisite_block(
                    title="Some required information is still missing",
                    detail="Review the readiness blockers above before running the assessment so the result is complete and reliable.",
                    links=[("Open Control Framework Studio", "Control Framework Studio"), ("Open Portfolio", "Portfolio")],
                    key_prefix="operations_assessment_blockers",
                )
            if st.button("Run assessment now", type="primary", key="operations_run_assessment"):
                try:
                    run = assessment_service.run_binding_assessment(
                        binding_code=binding_code,
                        product_code=product_code or None,
                    )
                    st.success(f"Assessment completed with score {run.score}.")
                except Exception as exc:
                    render_user_error(
                        title="Could not run the assessment",
                        exc=exc,
                        fallback="The assessment could not be completed right now.",
                        next_steps=[
                            "Check readiness first.",
                            "Confirm the selected product scope has SoA, implementation, and testing data in Control Framework Studio.",
                        ],
                        links=[("Open Control Framework Studio", "Control Framework Studio")],
                        key_prefix="operations_run_assessment_error",
                    )

            runs = session.scalars(
                select(AssessmentRun)
                .where(
                    AssessmentRun.framework_id == binding.framework_id,
                    AssessmentRun.organization_id == binding.organization_id,
                )
                .order_by(AssessmentRun.started_at.desc())
            ).all()
            if product_code:
                runs = [item for item in runs if item.product and item.product.code == product_code]
            if runs:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Started": item.started_at,
                                "Status": item.status,
                                "Review": item.review_status,
                                "Assurance": item.assurance_status,
                                "Score": item.score,
                                "Summary": item.summary,
                            }
                            for item in runs[:30]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No assessment runs have been recorded yet for this scope.")

        with tabs[3]:
            with st.form("operations_schedule_form"):
                name = st.text_input(
                    "Schedule name",
                    value=f"{binding.binding_code} {product_code or 'binding'} assessment",
                )
                cadence = st.selectbox("Cadence", ["monthly", "quarterly", "yearly"])
                execution_mode = st.selectbox("Execution mode", ["assisted", "autonomous"])
                notes = st.text_area("Notes", height=80)
                save_schedule = st.form_submit_button("Save recurring assessment", type="primary")
            if save_schedule and name.strip():
                try:
                    schedule = assessment_service.create_schedule(
                        framework_codes=[binding.framework.code],
                        name=name,
                        cadence=cadence,
                        binding_code=binding.binding_code,
                        product_code=product_code or None,
                        execution_mode=execution_mode,
                        notes=notes,
                    )
                    st.success(f"Saved schedule {schedule.name}.")
                except Exception as exc:
                    render_user_error(
                        title="Could not save the recurring assessment",
                        exc=exc,
                        fallback="The recurring assessment schedule could not be saved right now.",
                        key_prefix="operations_schedule_error",
                    )

            schedules = session.scalars(
                select(AssessmentSchedule).order_by(AssessmentSchedule.updated_at.desc())
            ).all()
            schedules = [
                item
                for item in schedules
                if item.framework_binding and item.framework_binding.binding_code == binding_code
            ]
            if product_code:
                schedules = [item for item in schedules if item.product and item.product.code == product_code]
            if schedules:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Name": item.name,
                                "Cadence": item.cadence,
                                "Execution": item.execution_mode,
                                "Next run": item.next_run_at,
                                "Last status": item.last_run_status,
                                "Enabled": item.enabled,
                            }
                            for item in schedules
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No recurring assessments are configured yet for this scope.")
