from __future__ import annotations

import pandas as pd
import streamlit as st

from aws_local_audit.db import session_scope
from aws_local_audit.services.product_about import ProductAboutService
from aws_local_audit.services.validation import ValidationError


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


def _note(body: str) -> None:
    st.markdown(f'<div class="section-note">{body}</div>', unsafe_allow_html=True)


def render_about_center() -> None:
    _hero("About my_grc", "Current product readiness, release history, historical maturity snapshots, and the practitioner feedback mailbox.")
    _note(
        "Use this page to understand the current version, what is strong already, what still needs work, and where to send suggestions or pain points from day-to-day GRC work."
    )

    with session_scope() as session:
        service = ProductAboutService(session)
        payload = service.about_payload()
        readiness = payload["delivery_readiness"]
        current_release = payload["current_release"] or {}

        metric_cols = st.columns(5)
        with metric_cols[0]:
            _metric("Version", payload["version"], current_release.get("title", "Current release"))
        with metric_cols[1]:
            _metric("Readiness", f'{readiness["overall_score"]:.2f}/5', readiness["deployment_readiness_verdict"]["status"])
        with metric_cols[2]:
            _metric("Phase 1", f'{readiness["phase1_score"]:.2f}/4', "Backbone maturity")
        with metric_cols[3]:
            _metric("Enterprise", f'{readiness["enterprise_score"]:.2f}/4', "Enterprise maturity")
        with metric_cols[4]:
            _metric("QA", readiness["qa_report_status"].title(), "Latest isolated validation")

        tabs = st.tabs(["Current Readiness", "Assessment History", "Release Notes", "Feedback Mailbox"])

        with tabs[0]:
            if current_release:
                st.markdown(f"### {current_release.get('title', 'Current release')}")
                st.write(current_release.get("summary", ""))
            st.markdown("#### Scorecard")
            st.dataframe(pd.DataFrame(readiness["scorecard"]), width="stretch", hide_index=True)

            st.markdown("#### Dimension details")
            dimension_labels = [item["name"] for item in readiness["dimensions"]]
            selected_dimension = st.selectbox("Open one dimension", dimension_labels, key="about_dimension")
            selected_payload = next(item for item in readiness["dimensions"] if item["name"] == selected_dimension)
            cols = st.columns(2)
            with cols[0]:
                st.markdown(f"**Score:** `{selected_payload['score']:.2f}/5`")
                st.markdown(f"**Confidence:** `{selected_payload['confidence']}`")
                st.markdown("**Strengths**")
                for item in selected_payload["strengths"]:
                    st.write(f"- {item}")
                st.markdown("**Gaps**")
                for item in selected_payload["gaps"]:
                    st.write(f"- {item}")
            with cols[1]:
                st.markdown("**Ways forward**")
                for item in selected_payload["improvements"]:
                    st.write(f"- {item}")
                st.markdown("**Sub-areas**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Sub-area": item["name"],
                                "Score": item["score"],
                                "Confidence": item["confidence"],
                                "State": item["implemented_state"],
                            }
                            for item in selected_payload["subareas"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )

            plan = readiness["improvement_plan"]
            plan_cols = st.columns(4)
            for column, label, steps in zip(
                plan_cols,
                ["Immediate", "30 Days", "60 Days", "90 Days"],
                [plan["immediate"], plan["days_30"], plan["days_60"], plan["days_90"]],
                strict=False,
            ):
                with column:
                    st.markdown(f"**{label}**")
                    for item in steps:
                        st.write(f"- {item}")

            detail_tabs = st.tabs(["Release blockers", "Business risks", "Quick wins", "Missing evidence"])
            with detail_tabs[0]:
                st.dataframe(pd.DataFrame(readiness["top_release_blockers"]), width="stretch", hide_index=True)
            with detail_tabs[1]:
                st.dataframe(pd.DataFrame(readiness["top_business_risks"]), width="stretch", hide_index=True)
            with detail_tabs[2]:
                st.dataframe(pd.DataFrame(readiness["quick_wins"]), width="stretch", hide_index=True)
            with detail_tabs[3]:
                st.dataframe(pd.DataFrame(readiness["missing_evidence"]), width="stretch", hide_index=True)

        with tabs[1]:
            st.markdown("#### Centralized maturity history")
            history = payload["maturity_history"]
            if history:
                rows = []
                for item in history:
                    score_summary = ", ".join(
                        f"{key}={value}" for key, value in (item.get("scores") or {}).items() if value not in {None, ""}
                    )
                    rows.append(
                        {
                            "Recorded On": item.get("recorded_on", ""),
                            "Title": item.get("title", ""),
                            "Scope": item.get("scope", ""),
                            "Model": item.get("model", ""),
                            "Confidence": item.get("confidence", ""),
                            "Scores": score_summary,
                            "Document": item.get("document", ""),
                        }
                    )
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            else:
                st.info("No maturity history entries are registered yet.")

            st.markdown("#### Assessment documents")
            st.dataframe(pd.DataFrame(payload["assessment_documents"]), width="stretch", hide_index=True)

        with tabs[2]:
            st.markdown("#### Release history")
            releases = payload["release_history"]
            if releases:
                release_options = [f'{item["version"]} - {item["title"]}' for item in releases]
                selected_release_label = st.selectbox("Open a release", release_options, key="about_release")
                selected_release = releases[release_options.index(selected_release_label)]
                st.markdown(f"### {selected_release['version']} · {selected_release['title']}")
                st.write(selected_release.get("summary", ""))
                st.markdown("**Highlights**")
                for item in selected_release.get("highlights", []):
                    st.write(f"- {item}")
                st.markdown("**Known issues**")
                for item in selected_release.get("known_issues", []):
                    st.write(f"- {item}")
            else:
                st.info("No release history entries are available yet.")

        with tabs[3]:
            st.markdown("#### Send a suggestion or pain point")
            with st.form("about_feedback_form", clear_on_submit=True):
                cols = st.columns(3)
                with cols[0]:
                    reporter_name = st.text_input("Your name")
                with cols[1]:
                    reporter_role = st.text_input("Your role")
                with cols[2]:
                    contact = st.text_input("Contact")
                cols = st.columns(3)
                with cols[0]:
                    area = st.selectbox(
                        "Area",
                        [
                            "Workspace",
                            "Control Framework Studio",
                            "Portfolio",
                            "Questionnaires",
                            "Operations",
                            "Integrations",
                            "Assessments",
                            "Reporting",
                            "Other",
                        ],
                    )
                with cols[1]:
                    page_context = st.text_input("Page or workflow")
                with cols[2]:
                    version_label = st.text_input("Version", value=payload["version"])
                subject = st.text_input("Subject")
                message = st.text_area("Suggestion or issue", height=180)
                submitted = st.form_submit_button("Send suggestion", type="primary")
                if submitted:
                    try:
                        service.submit_feedback(
                            subject=subject,
                            message=message,
                            area=area,
                            page_context=page_context,
                            reporter_name=reporter_name,
                            reporter_role=reporter_role,
                            contact=contact,
                            version_label=version_label,
                        )
                        st.success("Your suggestion was stored in the mailbox. Thank you.")
                    except ValidationError as exc:
                        for issue in exc.issues:
                            st.warning(issue)

            st.markdown("#### Mailbox")
            feedback_rows = service.list_feedback(limit=100)
            if feedback_rows:
                st.dataframe(pd.DataFrame(feedback_rows), width="stretch", hide_index=True)
            else:
                st.info("No feedback messages have been submitted yet.")
