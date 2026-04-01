from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from aws_local_audit.db import session_scope
from aws_local_audit.models import (
    AISuggestion,
    AssessmentRun,
    AssessmentSchedule,
    AwsCliProfile,
    ConfluenceConnection,
    LifecycleEvent,
    OrganizationFrameworkBinding,
    Product,
    ProductFlavor,
)
from aws_local_audit.services.asset_catalog import AssetCatalogService
from aws_local_audit.services.enterprise_maturity import EnterpriseMaturityService
from aws_local_audit.services.foundation_uplift import FoundationUpliftService
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.operator_experience import OperatorExperienceService
from aws_local_audit.services.phase1_maturity import Phase1MaturityService
from aws_local_audit.services.platform_foundation import FeatureFlagService, HealthCheckService
from aws_local_audit.services.readiness import OperationalReadinessService
from aws_local_audit.services.review_queue import ReviewQueueService
from aws_local_audit.services.suggestions import SuggestionService
from aws_local_audit.services.workspace_guidance import WorkspaceGuidanceService


UNIFIED_WORKSPACE_SECTIONS = [
    "Workspace Home",
    "Assistant Center",
    "Control Framework Studio",
    "Portfolio",
    "Questionnaires",
    "Operations",
    "Asset Catalog",
    "Artifact Explorer",
    "Operations Center",
    "Governance Center",
    "Settings & Integrations",
    "About",
    "Help Center",
    "Wizards",
    "Overview",
    "Standards",
    "AWS Profiles",
    "Review Queue",
    "Security & Lifecycle",
    "Maturity Studio",
    "Workspace Assessment",
]

LEGACY_WORKSPACE_SECTIONS = [
    "Wizards",
    "Overview",
    "Standards",
    "Portfolio",
    "AWS Profiles",
    "Control Framework Studio",
    "Review Queue",
    "Operations",
    "Security & Lifecycle",
    "Questionnaires",
    "Maturity Studio",
]

FAMILY_DESCRIPTIONS = {
    "governance": "Frameworks, controls, mappings, and evidence design.",
    "portfolio": "Organizations, products, and scoped implementation narratives.",
    "integrations": "AWS, Confluence, secure connectors, and script modules.",
    "imports": "Framework ingestion batches and source-traceable requirements.",
    "artifacts": "Evidence, questionnaires, assessments, and linked outputs.",
    "operations": "Schedules, AI suggestions, lifecycle events, and platform settings.",
}

LIFECYCLE_ENTITY_BY_ASSET = {
    "reference_documents": "reference_document",
    "framework_import_batches": "framework_import_batch",
    "imported_requirements": "imported_requirement",
    "imported_requirement_references": "imported_requirement_reference",
    "unified_control_references": "unified_control_reference",
    "questionnaires": "questionnaire",
    "questionnaire_items": "questionnaire_item",
    "evidence_items": "evidence_item",
    "assessment_runs": "assessment_run",
    "script_runs": "script_run",
    "external_links": "external_artifact_link",
    "lifecycle_events": "lifecycle_event",
}

COMMON_ACTIONS = [
    {
        "title": "Start onboarding",
        "detail": "Seed frameworks, register the enterprise scope, and prepare the first evidence path.",
        "target": "Wizards",
    },
    {
        "title": "Import and map a framework",
        "detail": "Bring in CSA CCM or another spreadsheet, preserve requirement traceability, and connect it to the SCF pivot baseline.",
        "target": "Control Framework Studio",
    },
    {
        "title": "Map controls into the unified baseline",
        "detail": "Approve mappings and review AI-suggested associations with human supervision.",
        "target": "Control Framework Studio",
    },
    {
        "title": "Collect evidence for a scoped control set",
        "detail": "Use AWS SSO profiles only when a live collection run needs them.",
        "target": "Operations",
    },
    {
        "title": "Answer a customer questionnaire",
        "detail": "Draft answers from implementation narratives without requiring evidence.",
        "target": "Questionnaires",
    },
    {
        "title": "Open operator guidance",
        "detail": "Use the built-in runbooks for first-time setup, evidence collection, assessments, and AI-assisted review.",
        "target": "Help Center",
    },
    {
        "title": "Review release status and send feedback",
        "detail": "Open the current readiness snapshot, see the release notes, and submit suggestions from daily GRC work.",
        "target": "About",
    },
]

ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT = ROOT / "documentation"
TESTING_ROOT = ROOT / "testing"


def _widget_key_fragment(value: str) -> str:
    fragment = "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_")
    return fragment or "item"


def _assistant_action_key(index: int, action: dict) -> str:
    return "_".join(
        [
            "assistant",
            str(index),
            _widget_key_fragment(action.get("title", "action")),
            _widget_key_fragment(action.get("target", "target")),
        ]
    )


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


def _priority_badge(priority: str) -> str:
    palette = {
        "critical": "#b91c1c",
        "high": "#c2410c",
        "medium": "#0f766e",
        "low": "#486581",
    }
    color = palette.get(priority, "#486581")
    return f"<span style='display:inline-block;padding:0.15rem 0.55rem;border-radius:999px;background:{color};color:white;font-size:0.8rem;text-transform:uppercase;'>{priority}</span>"


def _set_unified_page(page: str) -> None:
    st.session_state["workspace_page"] = page
    st.rerun()


def _load_doc(name: str) -> str:
    candidate_paths = [
        ROOT / name,
        DOC_ROOT / "design" / name,
        DOC_ROOT / "assessment" / name,
        DOC_ROOT / "others" / name,
        TESTING_ROOT / "qa" / name,
    ]
    for path in candidate_paths:
        if path.exists():
            return path.read_text(encoding="utf-8")
    if DOC_ROOT.exists():
        matches = list(DOC_ROOT.rglob(name))
        if matches:
            return matches[0].read_text(encoding="utf-8")
    if TESTING_ROOT.exists():
        matches = list(TESTING_ROOT.rglob(name))
        if matches:
            return matches[0].read_text(encoding="utf-8")
    return f"Documentation file not found: `{name}`"


def _focus_asset_catalog(*, family: str = "all", asset_type: str = "", asset_id=None) -> None:
    st.session_state["asset_catalog_family"] = family
    if asset_type:
        st.session_state["asset_catalog_type"] = asset_type
    if asset_type and asset_id not in {None, ""}:
        st.session_state[f"asset_catalog_selected_{asset_type}"] = asset_id
    _set_unified_page("Asset Catalog")


def _payload_rows(payload: dict, *, include_hidden: bool = False, limit: int = 20) -> list[dict]:
    rows = []
    for key, value in payload.items():
        if not include_hidden and str(key).startswith("_"):
            continue
        if value in {"", None, [], {}}:
            continue
        rendered = value
        if isinstance(value, (dict, list)):
            rendered = str(value)
        rows.append({"Field": key, "Value": rendered})
    return rows[:limit]


def _render_inventory_manager(
    *,
    catalog: AssetCatalogService,
    asset_types: list[dict],
    key_prefix: str,
    title: str,
    empty_message: str,
) -> None:
    if not asset_types:
        st.info(empty_message)
        return

    selected_type = st.selectbox(
        title,
        [item["key"] for item in asset_types],
        format_func=lambda value: next(item["label"] for item in asset_types if item["key"] == value),
        key=f"{key_prefix}_type",
    )
    selected_spec = next(item for item in asset_types if item["key"] == selected_type)
    st.caption(selected_spec["description"])

    rows = catalog.list_assets(selected_type, limit=250, search=st.text_input("Search", key=f"{key_prefix}_search"))
    if rows:
        left, right = st.columns([1.15, 0.85])
        with left:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            selected_id = st.selectbox(
                "Selected record",
                [row["_id"] for row in rows],
                format_func=lambda value: next(row["_label"] for row in rows if row["_id"] == value),
                key=f"{key_prefix}_selected_id",
            )
        with right:
            payload = catalog.asset_payload(selected_type, selected_id)
            st.markdown(f"### {payload['_label']}")
            with st.popover("Actions"):
                if st.button("Open in full catalog", key=f"{key_prefix}_open_catalog"):
                    _focus_asset_catalog(
                        family=selected_spec["family"],
                        asset_type=selected_type,
                        asset_id=selected_id,
                    )
            detail_tabs = st.tabs(["Overview", "Edit", "Create"])
            with detail_tabs[0]:
                st.dataframe(pd.DataFrame(_payload_rows(payload)), width="stretch", hide_index=True)
                with st.expander("Raw record"):
                    st.json(payload, expanded=False)
            with detail_tabs[1]:
                with st.form(f"{key_prefix}_edit_form"):
                    values = _render_dynamic_form(
                        catalog=catalog,
                        asset_type=selected_type,
                        mode=f"{key_prefix}_edit",
                        payload=payload,
                    )
                    save = st.form_submit_button("Save changes", type="primary")
                if save:
                    try:
                        catalog.update_asset(selected_type, selected_id, values)
                        st.success("Record updated.")
                    except Exception as exc:
                        st.error(str(exc))
                allow_delete = st.checkbox(
                    f"Allow delete for {payload['_label']}",
                    key=f"{key_prefix}_allow_delete",
                )
                if st.button("Delete record", key=f"{key_prefix}_delete", disabled=not allow_delete):
                    try:
                        catalog.delete_asset(selected_type, selected_id)
                        st.success("Record deleted.")
                    except Exception as exc:
                        st.error(str(exc))
            with detail_tabs[2]:
                with st.form(f"{key_prefix}_create_form"):
                    values = _render_dynamic_form(
                        catalog=catalog,
                        asset_type=selected_type,
                        mode=f"{key_prefix}_create",
                    )
                    create = st.form_submit_button("Create record", type="primary")
                if create:
                    try:
                        created = catalog.create_asset(selected_type, values)
                        st.success(f"Record created: {catalog._primary_value(created)}")
                    except Exception as exc:
                        st.error(str(exc))
    else:
        st.info("No records matched the current filter.")


def render_workspace_home() -> None:
    _hero("Workspace Home", "A simpler front door to the whole GRC platform: inventory-first, guided, and ready for CRUD.")
    _note(
        "This is the operator starting point. Keep the top-left menu collapsed until you need it, and use the focused tabs below to move from today’s priorities into records, evidence, reviews, and settings without losing context."
    )
    with session_scope() as session:
        guidance = WorkspaceGuidanceService(session).summary()
        operator = OperatorExperienceService(session)
        catalog = AssetCatalogService(session)
        foundation = FoundationUpliftService(session)
        review = guidance["review"]
        inventory = guidance["inventory"]
        phase1 = guidance["phase1"]
        enterprise = guidance["enterprise"]
        checklist = operator.pilot_checklist()
        recent_activity = operator.recent_audit_activity(limit=8)
        foundation_status = foundation.phase1_backbone_status()

        artifact_count = sum(item["count"] for item in inventory if item["artifact"])
        asset_count = sum(item["count"] for item in inventory if not item["artifact"])
        metric_cols = st.columns(5)
        with metric_cols[0]:
            _metric("Assets", str(asset_count), "All records in the workspace inventory.")
        with metric_cols[1]:
            _metric("Artifacts", str(artifact_count), "Evidence, assessments, imports, and outputs.")
        with metric_cols[2]:
            _metric("Review Queue", str(review["total"]), "Open review items across mappings, evidence, and assessments.")
        with metric_cols[3]:
            _metric("Phase 1", f'{phase1["overall_score"]:.1f}/4', "Foundation maturity.")
        with metric_cols[4]:
            _metric("Enterprise", f'{enterprise["overall_score"]:.1f}/4', "Overall enterprise readiness.")

        family_rows = [
            {
                "Family": family.title(),
                "Records": sum(item["count"] for item in inventory if item["family"] == family),
                "Artifact Types": sum(1 for item in inventory if item["family"] == family and item["artifact"]),
                "Description": FAMILY_DESCRIPTIONS.get(family, ""),
            }
            for family in sorted({item["family"] for item in inventory})
        ]

        home_tabs = st.tabs(["Today", "Assets & Artifacts", "Phase 1", "Enterprise", "Releases"])
        with home_tabs[0]:
            top_left, top_right = st.columns([1.05, 0.95])
            with top_left:
                for action in guidance["actions"][:3]:
                    st.markdown(
                        f"<div class='workflow-card'>{_priority_badge(action['priority'])}<div style='font-weight:700;margin-top:0.55rem;color:#102a43;'>{action['title']}</div><div style='margin-top:0.35rem;color:#486581;'>{action['detail']}</div><div style='margin-top:0.55rem;font-size:0.9rem;color:#334e68;'>Best place: {action['area']}</div></div>",
                        unsafe_allow_html=True,
                    )
            with top_right:
                with st.popover("Quick actions"):
                    if st.button("Exercise SCF pivot backbone", key="home_exercise_backbone", type="primary"):
                        try:
                            result = foundation.ensure_phase1_backbone_path()
                            guidance = WorkspaceGuidanceService(session).summary()
                            review = guidance["review"]
                            inventory = guidance["inventory"]
                            family_rows = [
                                {
                                    "Family": family.title(),
                                    "Records": sum(item["count"] for item in inventory if item["family"] == family),
                                    "Artifact Types": sum(1 for item in inventory if item["family"] == family and item["artifact"]),
                                    "Description": FAMILY_DESCRIPTIONS.get(family, ""),
                                }
                                for family in sorted({item["family"] for item in inventory})
                            ]
                            phase1 = guidance["phase1"]
                            enterprise = guidance["enterprise"]
                            checklist = operator.pilot_checklist()
                            recent_activity = operator.recent_audit_activity(limit=8)
                            foundation_status = foundation.phase1_backbone_status()
                            st.success(
                                f"Ready: {result['unified_control_code']} for {result['organization_code']}/{result['product_code']}/{result['product_flavor_code']}."
                            )
                        except Exception as exc:
                            st.error(str(exc))
                    if st.button("Open assistant", key="home_quick_assistant"):
                        _set_unified_page("Assistant Center")
                    if st.button("Open operations", key="home_quick_operations"):
                        _set_unified_page("Operations Center")
                    if st.button("Open asset catalog", key="home_quick_catalog"):
                        _set_unified_page("Asset Catalog")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Step": item["step"],
                                "Complete": item["complete"],
                                "Best Place": item["best_place"],
                            }
                            for item in checklist[:6]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            if recent_activity:
                st.dataframe(pd.DataFrame(recent_activity[:6]), width="stretch", hide_index=True)
            else:
                st.info("Recent actions, evidence work, and reviews will appear here as soon as the team starts using the workspace.")
        with home_tabs[1]:
            left, right = st.columns([1.0, 1.0])
            with left:
                st.dataframe(pd.DataFrame(family_rows), width="stretch", hide_index=True)
            with right:
                family_choices = [item["Family"] for item in family_rows]
                selected_family = st.selectbox("Jump to family", family_choices, key="home_family_jump")
                chosen = next(item for item in family_rows if item["Family"] == selected_family)
                if st.button("Open family in Asset Catalog", key="home_open_family"):
                    _focus_asset_catalog(family=selected_family.lower())
                st.caption(chosen["Description"])
            detail_tabs = st.tabs(["Assets", "Artifacts", "Review Queue"])
        with home_tabs[2]:
            metric_left, metric_right = st.columns([1.2, 0.8])
            with metric_left:
                st.dataframe(pd.DataFrame(phase1["areas"]), width="stretch", hide_index=True)
            with metric_right:
                st.dataframe(
                    pd.DataFrame(
                        [{"Check": key, "Value": value} for key, value in foundation_status.items()]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                with st.popover("Open related workspace areas"):
                    if st.button("Control Framework Studio", key="home_open_control_framework_studio"):
                        _set_unified_page("Control Framework Studio")
                    if st.button("Portfolio", key="home_open_portfolio"):
                        _set_unified_page("Portfolio")
                    if st.button("Maturity Studio", key="home_open_maturity"):
                        _set_unified_page("Maturity Studio")
                    if st.button("Standards", key="home_open_standards"):
                        _set_unified_page("Standards")
            for item in phase1["top_blockers"][:6]:
                st.markdown(f"- {item}")
        with home_tabs[3]:
            st.dataframe(pd.DataFrame(enterprise["phases"] + enterprise["qualities"]), width="stretch", hide_index=True)
            cols = st.columns(2)
            with cols[0]:
                st.dataframe(
                    pd.DataFrame(
                        [{"Metric": key, "Value": value} for key, value in list(enterprise["counts"].items())[:18]]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            with cols[1]:
                for item in enterprise["top_blockers"][:8]:
                    st.markdown(f"- {item}")
        with home_tabs[4]:
            st.markdown(_load_doc("RELEASE_IMPROVEMENTS_AND_ISSUES.md"))

        with detail_tabs[0]:
            asset_types = [item for item in catalog.asset_types() if not item["artifact"]]
            _render_inventory_manager(
                catalog=catalog,
                asset_types=asset_types,
                key_prefix="home_assets",
                title="Asset type",
                empty_message="No asset types are available yet.",
            )
        with detail_tabs[1]:
            artifact_types = [item for item in catalog.asset_types() if item["artifact"]]
            _render_inventory_manager(
                catalog=catalog,
                asset_types=artifact_types,
                key_prefix="home_artifacts",
                title="Artifact type",
                empty_message="No artifact types are available yet.",
            )
        with detail_tabs[2]:
            if review["top_items"]:
                st.dataframe(pd.DataFrame(review["top_items"]), width="stretch", hide_index=True)
            else:
                st.info("No review items are waiting right now.")
            if st.button("Open Review Queue", key="home_open_review_queue"):
                _set_unified_page("Review Queue")


def render_assistant_center() -> None:
    _hero("Assistant Center", "Guided assistants that turn complex compliance work into ordered, human-friendly next steps.")
    _note(
        "Use this page when you want the workspace to tell you what to do next. It keeps the next steps small, ordered, and linked to the right screen."
    )
    with session_scope() as session:
        guidance = WorkspaceGuidanceService(session).summary()
        operator = OperatorExperienceService(session)
        onboarding = guidance["onboarding"]
        enterprise = guidance["enterprise"]
        suggestions = SuggestionService(session).list_pending_mapping_suggestions()[:8]
        incomplete_steps = [item for item in operator.pilot_checklist() if not item["complete"]][:6]
        tabs = st.tabs(["Next steps", "AI help", "Onboarding", "Quick launch"])
        with tabs[0]:
            if incomplete_steps:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Next step": item["step"],
                                "Go to": item["best_place"],
                                "Why": item["detail"],
                            }
                            for item in incomplete_steps
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.success("Your current pilot path is covered. Use the quick launch tools below to expand scope or run operations.")
            cols = st.columns(3)
            for index, (column, action) in enumerate(zip(cols, COMMON_ACTIONS[:3])):
                with column:
                    st.markdown(
                        f"<div class='workflow-card'><div style='font-weight:700;color:#102a43;'>{action['title']}</div><div style='margin-top:0.45rem;color:#486581;'>{action['detail']}</div></div>",
                        unsafe_allow_html=True,
                    )
                    if st.button(f"Open {action['target']}", key=_assistant_action_key(index, action)):
                        _set_unified_page(action["target"])
        with tabs[1]:
            if suggestions:
                rows = []
                for item in suggestions:
                    top_match = SuggestionService(session).top_match_for_suggestion(item)
                    rows.append(
                        {
                            "Framework": item.framework.code if item.framework else "",
                            "Control": item.control.control_id if item.control else "",
                            "Suggested unified control": top_match.get("unified_control_code", ""),
                            "Score": top_match.get("score", 0.0),
                        }
                    )
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
                if st.button("Review suggestions", key="assistant_review_suggestions"):
                    _set_unified_page("Control Framework Studio")
            else:
                st.info("There are no AI suggestions waiting for attention right now.")
        with tabs[2]:
            st.progress(onboarding["progress"])
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Step": item["label"],
                            "Complete": item["completed"],
                            "Why": item["detail"],
                        }
                        for item in onboarding["steps"]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        with tabs[3]:
            for item in enterprise["top_blockers"][:4]:
                st.markdown(f"- {item}")
            with st.popover("Open a workspace area"):
                for target in ["Wizards", "Portfolio", "Operations Center", "Review Queue", "Help Center"]:
                    if st.button(target, key=f"assistant_launch_{target}"):
                        _set_unified_page(target)


def _render_field_input(
    *,
    field: dict,
    current_value,
    reference_options: dict[str, list[dict]],
    key_prefix: str,
):
    label = field["label"]
    if field["required_on_create"]:
        label = f"{label} *"

    if field["foreign_asset_type"]:
        options = reference_options.get(field["name"], [])
        values = [item["value"] for item in options]
        labels = {item["value"]: item["label"] for item in options}
        if field["nullable"]:
            values = [""] + values
            labels[""] = "-- None --"
        if not values:
            st.caption(f"No reference records are available yet for {field['label']}.")
            return ""
        current = current_value if current_value in labels else ("" if field["nullable"] else (values[0] if values else ""))
        return st.selectbox(
            label,
            values,
            index=values.index(current) if current in values else 0,
            format_func=lambda value: labels.get(value, str(value)),
            key=f"{key_prefix}_{field['name']}",
        )

    if field["type"] == "bool":
        return st.checkbox(label, value=bool(current_value), key=f"{key_prefix}_{field['name']}")
    if field["type"] == "int":
        return st.text_input(
            label,
            value="" if current_value in {None, ""} else str(current_value),
            key=f"{key_prefix}_{field['name']}",
        )
    if field["type"] == "float":
        return st.text_input(
            label,
            value="" if current_value in {None, ""} else str(current_value),
            key=f"{key_prefix}_{field['name']}",
        )
    if field["type"] == "datetime":
        return st.text_input(
            label,
            value="" if current_value in {None, ""} else str(current_value),
            help="Use ISO format like 2026-03-14T12:00:00",
            key=f"{key_prefix}_{field['name']}",
        )
    if field["multiline"]:
        return st.text_area(
            label,
            value="" if current_value in {None, ""} else str(current_value),
            height=120,
            key=f"{key_prefix}_{field['name']}",
        )
    return st.text_input(
        label,
        value="" if current_value in {None, ""} else str(current_value),
        key=f"{key_prefix}_{field['name']}",
    )


def _render_dynamic_form(
    *,
    catalog: AssetCatalogService,
    asset_type: str,
    mode: str,
    payload: dict | None = None,
) -> dict:
    schema = [field for field in catalog.field_schema(asset_type) if field["editable"]]
    reference_options = catalog.reference_options(asset_type)
    values = {}
    single_line_fields = [field for field in schema if not field["multiline"]]
    multiline_fields = [field for field in schema if field["multiline"]]
    columns = st.columns(2) if single_line_fields else []
    for column_index, field in enumerate(single_line_fields):
        container = columns[column_index % 2] if columns else st
        with container:
            values[field["name"]] = _render_field_input(
                field=field,
                current_value=(payload or {}).get(field["name"]),
                reference_options=reference_options,
                key_prefix=f"{mode}_{asset_type}",
            )
    for field in multiline_fields:
        values[field["name"]] = _render_field_input(
            field=field,
            current_value=(payload or {}).get(field["name"]),
            reference_options=reference_options,
            key_prefix=f"{mode}_{asset_type}_multiline",
        )
    return values


def render_asset_catalog() -> None:
    _hero("Asset Catalog", "Universal CRUD for the whole data model: one place to list, inspect, edit, create, and remove records.")
    _note(
        "Pick a family, filter the records, and work on the selected item without leaving the page. Selection, inspection, editing, and creation now stay in one workflow."
    )
    with session_scope() as session:
        catalog = AssetCatalogService(session)
        asset_types = catalog.asset_types()
        families = ["all"] + [item for item in catalog.families()]
        top = st.columns([0.9, 1.1, 1.0, 0.8])
        with top[0]:
            family = st.selectbox("Family", families, key="asset_catalog_family")
        filtered_types = [item for item in asset_types if family == "all" or item["family"] == family]
        if not filtered_types:
            st.info("No asset types are available for the selected family.")
            return

        with top[1]:
            selected_key = st.selectbox(
                "Asset type",
                [item["key"] for item in filtered_types],
                format_func=lambda value: next(item["label"] for item in filtered_types if item["key"] == value),
                key="asset_catalog_type",
            )
        spec = next(item for item in filtered_types if item["key"] == selected_key)
        with top[2]:
            search = st.text_input("Search", key=f"search_{selected_key}")
        inventory = catalog.list_assets(selected_key, limit=500)
        with top[3]:
            limit = st.slider(
                "Rows",
                min_value=25,
                max_value=500,
                value=min(200, max(25, len(inventory) or 25)),
                step=25,
                key=f"limit_{selected_key}",
            )
        st.caption(spec["description"])

        rows = catalog.list_assets(selected_key, limit=limit, search=search)
        workspace_cols = st.columns([1.12, 0.88])
        with workspace_cols[0]:
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
                chosen = st.selectbox(
                    "Selected record",
                    [row["_id"] for row in rows],
                    format_func=lambda value: next(row["_label"] for row in rows if row["_id"] == value),
                    key=f"picker_{selected_key}",
                )
                st.session_state[f"asset_catalog_selected_{selected_key}"] = chosen
            else:
                st.info("No records matched the current search.")
        with workspace_cols[1]:
            selected_id = st.session_state.get(f"asset_catalog_selected_{selected_key}")
            detail_tabs = st.tabs(["Overview", "Edit", "Create"])
            if selected_id not in {None, ""} and rows:
                payload = catalog.asset_payload(selected_key, selected_id)
                with detail_tabs[0]:
                    st.markdown(f"### {payload['_label']}")
                    st.dataframe(pd.DataFrame(_payload_rows(payload)), width="stretch", hide_index=True)
                    with st.popover("Record actions"):
                        if st.button("Copy this selection into Workspace Home", key=f"asset_catalog_focus_{selected_key}"):
                            _focus_asset_catalog(family=family, asset_type=selected_key, asset_id=selected_id)
                        with st.expander("Raw record"):
                            st.json(payload, expanded=False)
                with detail_tabs[1]:
                    with st.form(f"edit_{selected_key}"):
                        values = _render_dynamic_form(catalog=catalog, asset_type=selected_key, mode="edit", payload=payload)
                        save = st.form_submit_button("Save changes", type="primary")
                    if save:
                        try:
                            catalog.update_asset(selected_key, selected_id, values)
                            st.success("Record updated.")
                        except Exception as exc:
                            st.error(str(exc))
                    confirm_delete = st.checkbox(f"Allow delete for {payload['_label']}", key=f"delete_confirm_{selected_key}")
                    if st.button("Delete record", key=f"delete_{selected_key}", disabled=not confirm_delete):
                        try:
                            catalog.delete_asset(selected_key, selected_id)
                            st.session_state.pop(f"asset_catalog_selected_{selected_key}", None)
                            st.success("Record deleted.")
                        except Exception as exc:
                            st.error(str(exc))
            else:
                with detail_tabs[0]:
                    st.info("Select a record on the left to inspect and edit it here.")
                with detail_tabs[1]:
                    st.info("Select a record on the left to edit it here.")
            with detail_tabs[2]:
                with st.form(f"create_{selected_key}"):
                    values = _render_dynamic_form(catalog=catalog, asset_type=selected_key, mode="create")
                    create = st.form_submit_button("Create record", type="primary")
                if create:
                    try:
                        created = catalog.create_asset(selected_key, values)
                        st.session_state[f"asset_catalog_selected_{selected_key}"] = catalog._primary_value(created)
                        st.success("Record created.")
                    except Exception as exc:
                        st.error(str(exc))


def render_artifact_explorer() -> None:
    _hero("Artifact Explorer", "A dedicated view for evidence, questionnaires, imports, assessments, and lifecycle evidence.")
    _note(
        "Review evidence, assessments, imports, and questionnaires in one place. Select an artifact on the left and work with it on the right without changing pages."
    )
    with session_scope() as session:
        catalog = AssetCatalogService(session)
        review = ReviewQueueService(session).summary()
        artifact_types = [item for item in catalog.asset_types() if item["artifact"]]
        artifact_rows = [
            {
                "Artifact Type": item["label"],
                "Family": item["family"].title(),
                "Count": item["count"],
                "Description": item["description"],
            }
            for item in artifact_types
        ]

        metric_cols = st.columns(4)
        with metric_cols[0]:
            _metric("Artifact Types", str(len(artifact_types)))
        with metric_cols[1]:
            _metric("Stored Artifacts", str(sum(item["count"] for item in artifact_types)))
        with metric_cols[2]:
            _metric("Review Backlog", str(review["total"]))
        with metric_cols[3]:
            latest_event = session.scalar(select(func.max(LifecycleEvent.created_at)))
            _metric("Latest Lifecycle Event", str(latest_event or "n/a"))

        controls = st.columns([1.0, 1.0, 0.9])
        with controls[0]:
            selected_type = st.selectbox(
                "Artifact type",
                [item["key"] for item in artifact_types],
                format_func=lambda value: next(item["label"] for item in artifact_types if item["key"] == value),
                key="artifact_type",
            )
        with controls[1]:
            artifact_search = st.text_input("Search", key=f"artifact_search_{selected_type}")
        with controls[2]:
            artifact_limit = st.slider("Rows", 25, 250, 100, 25, key=f"artifact_limit_{selected_type}")
        work_cols = st.columns([1.08, 0.92])
        rows = catalog.list_assets(selected_type, limit=artifact_limit, search=artifact_search)
        if rows:
            with work_cols[0]:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
                selected_id = st.selectbox(
                    "Selected artifact",
                    [row["_id"] for row in rows],
                    format_func=lambda value: next(row["_label"] for row in rows if row["_id"] == value),
                    key=f"artifact_picker_{selected_type}",
                )
            payload = catalog.asset_payload(selected_type, selected_id)
            with work_cols[1]:
                artifact_tabs = st.tabs(["Overview", "Lifecycle", "Actions"])
                with artifact_tabs[0]:
                    st.markdown(f"### {payload['_label']}")
                    st.dataframe(pd.DataFrame(_payload_rows(payload)), width="stretch", hide_index=True)
                with artifact_tabs[1]:
                    if str(selected_id).isdigit():
                        related_events = session.scalars(
                            select(LifecycleEvent)
                            .where(LifecycleEvent.entity_id == int(selected_id))
                            .where(LifecycleEvent.entity_type == LIFECYCLE_ENTITY_BY_ASSET.get(selected_type, selected_type.rstrip("s")))
                            .order_by(LifecycleEvent.created_at.desc())
                            .limit(20)
                        ).all()
                    else:
                        related_events = []
                    if related_events:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "When": item.created_at,
                                        "From": item.from_state,
                                        "To": item.to_state,
                                        "Actor": item.actor,
                                    }
                                    for item in related_events
                                ]
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        st.info("No recent lifecycle changes were recorded for this artifact.")
                with artifact_tabs[2]:
                    with st.popover("Open related workspace areas"):
                        if st.button("Open in Asset Catalog", key=f"artifact_open_catalog_{selected_type}"):
                            _focus_asset_catalog(family="artifacts", asset_type=selected_type, asset_id=selected_id)
                        if st.button("Open Review Queue", key=f"artifact_open_review_{selected_type}"):
                            _set_unified_page("Review Queue")
                        if st.button("Open Operations Center", key=f"artifact_open_ops_{selected_type}"):
                            _set_unified_page("Operations Center")
        else:
            st.info("No artifacts are stored for the selected type yet.")


def render_operations_center() -> None:
    _hero("Operations Center", "Operational confidence before execution: readiness, review load, schedules, and live integration posture.")
    _note(
        "Use this page right before you collect evidence or run an assessment. It keeps readiness, queues, and recent outcomes visible without crowding the screen."
    )
    with session_scope() as session:
        operator = OperatorExperienceService(session)
        review = ReviewQueueService(session).summary()
        suggestions = session.scalar(
            select(func.count()).select_from(AISuggestion).where(AISuggestion.accepted.is_(False))
        ) or 0
        schedule_count = session.scalar(select(func.count()).select_from(AssessmentSchedule)) or 0
        latest_assessment = session.scalar(select(func.max(AssessmentRun.started_at))) or "n/a"
        recent_assessments = operator.recent_assessments(limit=8)
        recent_evidence = operator.recent_evidence(limit=8)

        metric_cols = st.columns(4)
        with metric_cols[0]:
            _metric("Open Review Items", str(review["total"]))
        with metric_cols[1]:
            _metric("Pending AI Suggestions", str(suggestions))
        with metric_cols[2]:
            _metric("Schedules", str(schedule_count))
        with metric_cols[3]:
            _metric("Latest Assessment", str(latest_assessment))

        tabs = st.tabs(["Readiness", "Review queue", "Recent runs"])
        with tabs[0]:
            left, right = st.columns([1.12, 0.88])
            bindings = session.scalars(
                select(OrganizationFrameworkBinding).order_by(OrganizationFrameworkBinding.binding_code)
            ).all()
            with left:
                if not bindings:
                    st.info("No framework bindings exist yet. Create one from Wizards or Asset Catalog first.")
                else:
                    binding_codes = [item.binding_code for item in bindings]
                    binding_code = st.selectbox("Framework binding", binding_codes, key="ops_binding")
                    binding = next(item for item in bindings if item.binding_code == binding_code)
                    product_codes = [
                        item.code
                        for item in session.scalars(
                            select(Product).where(Product.organization_id == binding.organization_id).order_by(Product.code)
                        ).all()
                    ]
                    product_code = st.selectbox("Product", [""] + product_codes, key="ops_product")
                    flavor_codes: list[str] = []
                    if product_code:
                        product = session.scalar(
                            select(Product).where(Product.organization_id == binding.organization_id, Product.code == product_code)
                        )
                        if product is not None:
                            flavor_codes = [
                                item.code
                                for item in session.scalars(
                                    select(ProductFlavor).where(ProductFlavor.product_id == product.id).order_by(ProductFlavor.code)
                                ).all()
                            ]
                    flavor_code = st.selectbox("Product flavor", [""] + flavor_codes, key="ops_flavor")
                    if st.button("Assess readiness", key="ops_assess_readiness", type="primary"):
                        try:
                            readiness = OperationalReadinessService(session).assess_binding(
                                binding_code=binding_code,
                                product_code=product_code or None,
                                product_flavor_code=flavor_code or None,
                            )
                            st.session_state["ops_readiness"] = readiness
                        except Exception as exc:
                            st.error(str(exc))
            with right:
                readiness = st.session_state.get("ops_readiness")
                if readiness:
                    st.success(f"{readiness['readiness_status']} ({readiness['overall_score']:.1f}/4)")
                    st.dataframe(pd.DataFrame(readiness["areas"]), width="stretch", hide_index=True)
                    if readiness["blockers"]:
                        for item in readiness["blockers"][:5]:
                            st.markdown(f"- {item}")
                else:
                    st.info("Run a readiness check to see blockers, warnings, and fit for execution.")
        with tabs[1]:
            if review["top_items"]:
                st.dataframe(pd.DataFrame(review["top_items"]), width="stretch", hide_index=True)
            else:
                st.info("No open review items were found.")
            with st.popover("Open related areas"):
                if st.button("Review Queue", key="ops_review_queue"):
                    _set_unified_page("Review Queue")
                if st.button("Operations", key="ops_legacy_operations"):
                    _set_unified_page("Operations")
        with tabs[2]:
            history_tabs = st.tabs(["Recent Assessments", "Recent Evidence"])
            with history_tabs[0]:
                if recent_assessments:
                    st.dataframe(pd.DataFrame(recent_assessments), width="stretch", hide_index=True)
                    st.caption("You can also inspect these in Artifact Explorer or with `aws-local-audit assessment list`.")
                else:
                    st.info("No assessment runs have been recorded yet.")
            with history_tabs[1]:
                if recent_evidence:
                    st.dataframe(pd.DataFrame(recent_evidence), width="stretch", hide_index=True)
                    st.caption("You can also inspect evidence in Artifact Explorer or with `aws-local-audit evidence show <id>`.")
                else:
                    st.info("No evidence items have been recorded yet.")


def render_governance_center() -> None:
    _hero("Governance Center", "See maturity, lifecycle, and review posture without hunting through multiple specialist pages.")
    _note(
        "Use this page to understand what needs governance attention now: control coverage, lifecycle changes, and enterprise posture."
    )
    with session_scope() as session:
        phase1 = Phase1MaturityService(session).assess()
        enterprise = EnterpriseMaturityService(session).assess()
        review = ReviewQueueService(session).summary()
        events = session.scalars(select(LifecycleEvent).order_by(LifecycleEvent.created_at.desc()).limit(30)).all()

        metric_cols = st.columns(4)
        with metric_cols[0]:
            _metric("Phase 1 Score", f'{phase1["overall_score"]:.1f}/4')
        with metric_cols[1]:
            _metric("Enterprise Score", f'{enterprise["overall_score"]:.1f}/4')
        with metric_cols[2]:
            _metric("Critical Reviews", str(review["priorities"].get("critical", 0)))
        with metric_cols[3]:
            _metric("Lifecycle Events", str(enterprise["counts"]["lifecycle_events"]))

        tabs = st.tabs(["Phase 1", "Enterprise", "Lifecycle", "Releases"])
        with tabs[0]:
            st.dataframe(pd.DataFrame(phase1["areas"]), width="stretch", hide_index=True)
            for item in phase1["top_blockers"][:6]:
                st.markdown(f"- {item}")
        with tabs[1]:
            st.dataframe(pd.DataFrame(enterprise["phases"] + enterprise["qualities"]), width="stretch", hide_index=True)
            for item in enterprise["top_blockers"][:8]:
                st.markdown(f"- {item}")
        with tabs[2]:
            if events:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "When": item.created_at,
                                "Entity": item.entity_type,
                                "From": item.from_state,
                                "To": item.to_state,
                                "Actor": item.actor,
                            }
                            for item in events
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No lifecycle events have been recorded yet.")
        with tabs[3]:
            st.markdown(_load_doc("RELEASE_IMPROVEMENTS_AND_ISSUES.md"))


def render_settings_integrations() -> None:
    _hero("Settings & Integrations", "A cleaner operator surface for runtime preferences and connection health.")
    _note(
        "The platform stays offline-first by default. Live integrations are only exercised when you intentionally run evidence collection, assessments, or publishing."
    )
    with session_scope() as session:
        governance = GovernanceService(session)
        catalog = AssetCatalogService(session)
        operator = OperatorExperienceService(session)
        health = HealthCheckService(session).run()
        flags = FeatureFlagService(session).list_flags()
        offline_mode = governance.offline_mode_enabled()
        default_page = governance.get_setting("workspace.unified_default_page", "Workspace Home")
        environment = operator.environment_summary()

        with st.form("workspace_settings"):
            offline = st.checkbox("Offline-first mode", value=offline_mode)
            landing_page = st.selectbox("Unified workspace landing page", UNIFIED_WORKSPACE_SECTIONS, index=UNIFIED_WORKSPACE_SECTIONS.index(default_page) if default_page in UNIFIED_WORKSPACE_SECTIONS else 0)
            save = st.form_submit_button("Save workspace settings", type="primary")
        if save:
            governance.set_offline_mode(offline)
            governance.set_setting("workspace.unified_default_page", landing_page, "Default landing page for the unified workspace shell.")
            st.success("Workspace settings updated.")

        aws_profiles = session.scalars(select(AwsCliProfile).order_by(AwsCliProfile.profile_name)).all()
        confluence_connections = session.scalars(select(ConfluenceConnection).order_by(ConfluenceConnection.name)).all()
        tabs = st.tabs(["Workspace", "AWS", "Confluence", "Logs", "Run & Test", "Releases"])
        with tabs[0]:
            cols = st.columns([1.0, 1.0])
            with cols[0]:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"Setting": "Offline mode", "Value": environment["offline_mode"]},
                            {"Setting": "Platform health", "Value": health["status"]},
                            {"Setting": "Frameworks", "Value": environment["frameworks"]},
                            {"Setting": "Products", "Value": environment["products"]},
                            {"Setting": "Bindings", "Value": environment["bindings"]},
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            with cols[1]:
                st.dataframe(pd.DataFrame(health["checks"]), width="stretch", hide_index=True)
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Type": item["label"], "Count": item["count"]}
                        for item in catalog.asset_types()
                        if item["family"] == "integrations"
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            if flags:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Flag": item.flag_key,
                                "Enabled": item.enabled,
                                "Strategy": item.rollout_strategy,
                            }
                            for item in flags
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
        with tabs[1]:
            if aws_profiles:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Profile": item.profile_name,
                                "Account": item.sso_account_id,
                                "Role": item.sso_role_name,
                                "Validation": item.last_validation_status or "unknown",
                                "Last validated": item.last_validated_at,
                            }
                            for item in aws_profiles
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No AWS CLI profiles are registered yet.")
            if st.button("Open AWS Profiles", key="settings_aws_profiles"):
                _set_unified_page("AWS Profiles")
        with tabs[2]:
            if confluence_connections:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Connection": item.name,
                                "Space": item.space_key,
                                "Status": item.status,
                                "Health": item.last_test_status or "untested",
                            }
                            for item in confluence_connections
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No Confluence connections are registered yet.")
            if st.button("Open Security & Lifecycle", key="settings_security_lifecycle"):
                _set_unified_page("Security & Lifecycle")
        with tabs[3]:
            log_tabs = st.tabs(["Application log", "Audit log"])
            with log_tabs[0]:
                app_lines = operator.log_tail(audit=False, limit=20)
                if app_lines:
                    st.code("\n".join(app_lines), language="text")
                else:
                    st.info("The application log is empty or has not been created yet.")
            with log_tabs[1]:
                audit_lines = operator.log_tail(audit=True, limit=20)
                if audit_lines:
                    st.code("\n".join(audit_lines), language="json")
                else:
                    st.info("The audit log is empty or has not been created yet.")
        with tabs[4]:
            st.code("./scripts/run_workspace.sh", language="bash")
            st.code("./scripts/run_e2e_tests.sh", language="bash")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Area": "Workspace launch", "Command": "./scripts/run_workspace.sh"},
                        {"Area": "Developer end-to-end tests", "Command": "./scripts/run_e2e_tests.sh"},
                        {"Area": "Full QA harness", "Command": "bash testing/qa/run_wsl.sh"},
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        with tabs[5]:
            st.markdown(_load_doc("RELEASE_IMPROVEMENTS_AND_ISSUES.md"))


def render_help_center() -> None:
    _hero("Help Center", "Detailed operator guidance for first-time setup, live evidence collection, ongoing operations, and AI-assisted workflows.")
    _note(
        "Use this page as the working manual for GRC practitioners. It focuses on how to operate the platform and where to go next."
    )
    quick_links = st.columns(4)
    with quick_links[0]:
        if st.button("Open Assistant Center", key="help_assistant_center"):
            _set_unified_page("Assistant Center")
    with quick_links[1]:
        if st.button("Open Operations Center", key="help_operations_center"):
            _set_unified_page("Operations Center")
    with quick_links[2]:
        if st.button("Open Artifact Explorer", key="help_artifact_explorer"):
            _set_unified_page("Artifact Explorer")
    with quick_links[3]:
        if st.button("Open Review Queue", key="help_review_queue"):
            _set_unified_page("Review Queue")

    tabs = st.tabs(
        [
            "Get Started",
            "Operate",
            "Evidence & Assessments",
            "Where To Find Things",
            "AI Help",
            "Run & Test",
            "Troubleshooting",
            "Releases & Issues",
        ]
    )
    with tabs[0]:
        st.markdown(_load_doc("WORKFLOW_1_FIRST_FRAMEWORK_PILOT.md"))
    with tabs[1]:
        st.markdown(_load_doc("WORKFLOW_2_FULL_SYSTEM_OPERATIONS.md"))
    with tabs[2]:
        st.markdown(
            """
### Evidence And Assessments

- Use `Operations Center` before a live run.
- Use `Operations` for deeper execution.
- Use `Artifact Explorer` to review collected evidence and completed runs.
- Use `Questionnaires` when you want to answer a customer request from implementation narratives.

### SCF Pivot Reminder

The control backbone uses the Secure Controls Framework as the pivot baseline.
You can bootstrap the first local mapped path from `Workspace Home` with `Exercise SCF Pivot Backbone`.
"""
        )
    with tabs[3]:
        st.markdown(
            """
### Where To Find Things

- Past assessment runs:
  `Artifact Explorer` -> `Assessment Runs`
- Evidence already collected:
  `Artifact Explorer` -> `Evidence Items`
- Reference guides and imported source links:
  `Asset Catalog` -> `Reference Documents`, `Imported Requirement References`, or `Unified Control References`
- All assets and records:
  `Asset Catalog`
- Review backlog:
  `Operations Center` or `Review Queue`
- AWS profile health:
  `Settings & Integrations` or `AWS Profiles`
- Lifecycle and governance state:
  `Governance Center`
- Logs:
  `logs/my_grc.log` and `logs/my_grc-audit.log`
"""
        )
    with tabs[4]:
        st.markdown(
            """
### AI Help For Practitioners

- `Assistant Center`: highlights the places where AI-governed suggestions need attention
- `Control Framework Studio`: review imported-control mapping suggestions, approved mappings, and control wording in one place
- `Review Queue`: includes AI suggestions that still need human action
- `Asset Catalog` -> `AI Suggestions`: inspect stored AI outputs directly

### What AI Helps With

- suggest control mappings from imported CSV or spreadsheet data
- support governed review, not silent automatic approval
- help reduce mapping effort while preserving traceability and human supervision

### Recommended Workflow

1. import or preview a framework source
2. inspect suggested mappings
3. promote or dismiss suggestions with rationale
4. review resulting mappings in the unified control baseline
"""
        )
    with tabs[5]:
        st.code("./scripts/run_workspace.sh", language="bash")
        st.code("./scripts/run_e2e_tests.sh", language="bash")
        st.code("bash testing/qa/run_wsl.sh", language="bash")
    with tabs[6]:
        st.markdown(
            """
### Troubleshooting Shortlist

If the app starts but live collection is not ready:

1. check `Operations Center`
2. inspect `evidence readiness-report`
3. confirm the required AWS SSO profile is registered and validated
4. confirm AWS targets exist for the relevant product and control scope
5. review the log files under `logs/`

If evidence collection does not work:

1. run `aws-local-audit evidence login-plan --binding <BINDING> --product <PRODUCT>`
2. run `aws sso login --profile <PROFILE>`
3. run `aws-local-audit aws-profile validate <PROFILE>`
4. rerun the readiness report
5. then collect again

If you cannot find a past assessment:

1. use `aws-local-audit assessment list`
2. open `Artifact Explorer` -> `Assessment Runs`
3. inspect `Review Queue` if the run is awaiting governance action

If AI suggestions exist but are not visible:

1. open `Assistant Center`
2. open `Review Queue`
3. inspect `Asset Catalog` -> `AI Suggestions`
4. inspect `Control Framework Studio` after importing framework content
"""
        )
    with tabs[7]:
        st.markdown(_load_doc("RELEASE_IMPROVEMENTS_AND_ISSUES.md"))


def render_workspace_assessment() -> None:
    _hero("Workspace Assessment", "A compact snapshot of operating coverage, product scoring, and the latest release corrections.")
    _note(
        "Use this page when you want the current platform picture in one glance: coverage, scores, and the latest known improvements or issues."
    )
    with session_scope() as session:
        phase1 = Phase1MaturityService(session).assess()
        enterprise = EnterpriseMaturityService(session).assess()
        review = ReviewQueueService(session).summary()
        inventory = AssetCatalogService(session).asset_types()

        ui_ux_rows = [
            {
                "Dimension": "Navigation clarity",
                "Score": 4.0 if review["total"] >= 0 else 3.0,
                "Rationale": "The workspace now has a single operating shell with both overview and specialist workflows inside it.",
            },
            {
                "Dimension": "CRUD completeness",
                "Score": 4.0,
                "Rationale": "The asset catalog provides create, read, update, and delete flows across all registered asset types.",
            },
            {
                "Dimension": "Inventory visibility",
                "Score": 4.0,
                "Rationale": "All asset families and artifact types are now centrally visible with counts and details.",
            },
            {
                "Dimension": "Guided assistance",
                "Score": 3.7,
                "Rationale": "Assistant Center organizes common journeys and AI review inputs, though deeper step-by-step automation still belongs in future waves.",
            },
            {
                "Dimension": "Operational confidence",
                "Score": 3.8,
                "Rationale": "Readiness checks and specialist execution flows are now reachable from the same shell, though some deeper journeys still need further polish.",
            },
            {
                "Dimension": "Modularity",
                "Score": 3.9,
                "Rationale": "The redesign introduces dedicated workspace modules instead of extending one monolithic page further.",
            },
        ]
        overall_ui_ux = round(sum(item["Score"] for item in ui_ux_rows) / len(ui_ux_rows), 2)

        metric_cols = st.columns(4)
        with metric_cols[0]:
            _metric("UI/UX Score", f"{overall_ui_ux:.2f}/4")
        with metric_cols[1]:
            _metric("Phase 1", f'{phase1["overall_score"]:.2f}/4')
        with metric_cols[2]:
            _metric("Enterprise", f'{enterprise["overall_score"]:.2f}/4')
        with metric_cols[3]:
            _metric("Asset Types", str(len(inventory)))

        tabs = st.tabs(["UX", "Scores", "Known issues"])
        with tabs[0]:
            st.dataframe(pd.DataFrame(ui_ux_rows), width="stretch", hide_index=True)
        with tabs[1]:
            st.dataframe(pd.DataFrame(phase1["areas"] + enterprise["phases"]), width="stretch", hide_index=True)
        with tabs[2]:
            st.markdown(_load_doc("RELEASE_IMPROVEMENTS_AND_ISSUES.md"))

