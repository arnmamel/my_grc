from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import select

from aws_local_audit.db import session_scope
from aws_local_audit.models import CustomerQuestionnaire
from aws_local_audit.services.control_matrix import ControlMatrixService
from aws_local_audit.services.questionnaires import QuestionnaireService
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


def render_questionnaire_center() -> None:
    _hero(
        "Questionnaires",
        "Upload a customer spreadsheet, pick the relevant organization and product scopes, and generate suggested answers with memory reuse.",
    )
    st.markdown(
        '<div class="section-note">Questionnaires are managed independently from evidence. The answer engine reuses approved past answers when possible and falls back to implementation narratives stored in the SCF matrix.</div>',
        unsafe_allow_html=True,
    )

    with session_scope() as session:
        service = QuestionnaireService(session)
        matrix = ControlMatrixService(session)
        scopes = matrix.available_scopes()

        if not scopes:
            render_prerequisite_block(
                title="Create at least one organization and one product first",
                detail="Questionnaires are answered against one or more product scopes. Start by defining the scope in Portfolio.",
                links=[("Open Portfolio", "Portfolio"), ("Open Guided Setup", "Wizards")],
                key_prefix="questionnaire_missing_scope",
            )
            return

        scope_labels = [item["label"] for item in scopes]
        selected_scope_labels = st.multiselect(
            "Scopes involved in this customer questionnaire",
            scope_labels,
            default=scope_labels[:1],
            help="You can choose one or several organization/product scopes for the same customer engagement.",
        )
        selected_scopes = [item for item in scopes if item["label"] in selected_scope_labels]

        tabs = st.tabs(["Upload & Preview", "Answer Memory", "Stored Questionnaires"])

        with tabs[0]:
            uploaded = st.file_uploader(
                "Upload the questionnaire spreadsheet",
                type=["csv", "xlsx", "xls"],
                key="questionnaire_upload_v2",
            )
            if uploaded is None:
                st.info("Upload a questionnaire file to preview the suggested answers.")
            else:
                source_path = _save_upload(uploaded)
                try:
                    preview = service.preview_questionnaire_answers_from_file(
                        [
                            {
                                "organization_code": item["organization_code"],
                                "product_code": item["product_code"],
                            }
                            for item in selected_scopes
                        ],
                        source_path,
                    )
                    if preview:
                        st.dataframe(pd.DataFrame(preview), width="stretch", hide_index=True)
                        primary_scope = st.selectbox(
                            "Primary storage scope",
                            [item["label"] for item in selected_scopes],
                            help="The questionnaire record is stored under one primary scope, but the answer suggestions can use all selected scopes.",
                        )
                        questionnaire_name = st.text_input(
                            "Questionnaire name",
                            value=uploaded.name.rsplit(".", 1)[0],
                        )
                        customer_name = st.text_input("Customer name")
                        if st.button("Store questionnaire with suggested answers", type="primary"):
                            primary = next(item for item in selected_scopes if item["label"] == primary_scope)
                            try:
                                questionnaire = service.import_questionnaire_file(
                                    primary_organization_code=primary["organization_code"],
                                    primary_product_code=primary["product_code"],
                                    file_path=source_path,
                                    name=questionnaire_name,
                                    customer_name=customer_name,
                                    scope_refs=[
                                        {
                                            "organization_code": item["organization_code"],
                                            "product_code": item["product_code"],
                                        }
                                        for item in selected_scopes
                                    ],
                                )
                                st.success(f"Questionnaire stored: {questionnaire.name}")
                            except Exception as exc:
                                render_user_error(
                                    title="Could not store the questionnaire",
                                    exc=exc,
                                    fallback="The questionnaire could not be stored right now.",
                                    links=[("Open Control Framework Studio", "Control Framework Studio")],
                                    key_prefix="questionnaire_store_error",
                                )
                    else:
                        render_prerequisite_block(
                            title="No answers could be drafted yet",
                            detail="The selected scopes do not have enough implementation content. Add control implementations in Control Framework Studio and try again.",
                            links=[("Open Control Framework Studio", "Control Framework Studio")],
                            key_prefix="questionnaire_no_preview",
                        )
                except Exception as exc:
                    render_user_error(
                        title="Could not preview the questionnaire",
                        exc=exc,
                        fallback="The uploaded file could not be parsed or matched.",
                        next_steps=[
                            "Use a CSV or Excel file with a column such as question, requirement, text, description, or prompt.",
                            "Make sure the selected products already have implementation narratives in the control matrix.",
                        ],
                        links=[("Open Control Framework Studio", "Control Framework Studio")],
                        key_prefix="questionnaire_preview_error",
                    )
                finally:
                    Path(source_path).unlink(missing_ok=True)

        with tabs[1]:
            search_question = st.text_input("Look for reusable answers", key="questionnaire_memory_search")
            if search_question:
                memory = service.reusable_answers(
                    search_question,
                    scope_refs=[
                        {
                            "organization_code": item["organization_code"],
                            "product_code": item["product_code"],
                        }
                        for item in selected_scopes
                    ],
                    limit=10,
                )
                if memory:
                    st.dataframe(pd.DataFrame(memory), width="stretch", hide_index=True)
                else:
                    st.info("No reusable answers were found for that question in the selected scopes.")
            else:
                st.info("Search by a question to see reusable answers from previous questionnaires.")

        with tabs[2]:
            stored = session.scalars(select(CustomerQuestionnaire).order_by(CustomerQuestionnaire.updated_at.desc())).all()
            if stored:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Name": item.name,
                                "Customer": item.customer_name,
                                "Organization": item.organization.code,
                                "Product": item.product.code,
                                "Items": len(item.items),
                                "Status": item.status,
                            }
                            for item in stored
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No questionnaires have been stored yet.")
