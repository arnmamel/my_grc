from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from control_framework_studio_v2 import render_control_framework_studio
from operations_workspace import render_operations_workspace
from portfolio_center import render_portfolio_center
from questionnaire_center import render_questionnaire_center
from setup_center import render_guided_setup
from about_center import render_about_center
from aws_local_audit.collectors import COLLECTORS
from aws_local_audit.config import settings
from aws_local_audit.db import init_database, session_scope
from aws_local_audit.framework_loader import load_templates
from aws_local_audit.logging_utils import audit_event, configure_logging, get_logger
from aws_local_audit.models import (
    AISuggestion,
    AssessmentSchedule,
    AssessmentScriptBinding,
    AssessmentScriptModule,
    AssessmentRun,
    AwsCliProfile,
    AwsEvidenceTarget,
    ConfluenceConnection,
    Control,
    ControlImplementation,
    CustomerQuestionnaire,
    CustomerQuestionnaireItem,
    EvidenceItem,
    EvidenceCollectionPlan,
    Framework,
    FrameworkImportBatch,
    ImportedRequirement,
    ImportedRequirementReference,
    LifecycleEvent,
    Organization,
    OrganizationFrameworkBinding,
    Product,
    ProductControlProfile,
    ProductFlavor,
    ReferenceDocument,
    SecretMetadata,
    UnifiedControl,
    UnifiedControlReference,
    UnifiedControlMapping,
)
from aws_local_audit.services.assessments import AssessmentService
from aws_local_audit.services.aws_profiles import AwsProfileService
from aws_local_audit.services.enterprise_maturity import EnterpriseMaturityService
from aws_local_audit.services.evidence import EvidenceService
from aws_local_audit.services.foundation_uplift import FoundationUpliftService
from aws_local_audit.services.framework_imports import FrameworkImportService
from aws_local_audit.services.frameworks import FrameworkService
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.maturity import MaturityService
from aws_local_audit.services.phase1_maturity import Phase1MaturityService
from aws_local_audit.services.readiness import OperationalReadinessService
from aws_local_audit.services.questionnaires import QuestionnaireService
from aws_local_audit.services.review_queue import ReviewQueueService
from aws_local_audit.services.security import ConfluenceConnectionService
from aws_local_audit.services.script_modules import ScriptModuleService
from aws_local_audit.services.suggestions import SuggestionService
from aws_local_audit.services.validation import ValidationError
from aws_local_audit.services.workbench import WorkbenchService
from aws_local_audit.services.workspace_auth import WorkspaceAuthService, WorkspaceAuthenticationError
from ui_support import render_user_error
from ux_redesign import (
    UNIFIED_WORKSPACE_SECTIONS,
    render_artifact_explorer,
    render_asset_catalog,
    render_assistant_center,
    render_governance_center,
    render_help_center,
    render_operations_center,
    render_settings_integrations,
    render_workspace_assessment,
    render_workspace_home,
)

configure_logging()
APP_LOGGER = get_logger("workspace")

st.set_page_config(
    page_title="my_grc Workspace",
    page_icon="GRC",
    layout="wide",
    initial_sidebar_state="collapsed",
)
_STARTUP_ERROR: Exception | None = None
try:
    init_database()
    APP_LOGGER.info("Streamlit workspace initialized.")
except Exception as exc:
    _STARTUP_ERROR = exc
    APP_LOGGER.exception("Workspace startup failed.")


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        html, body, [class*="css"] { font-family: "IBM Plex Sans", "Noto Sans", "Segoe UI", sans-serif; }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(217, 119, 6, 0.18), transparent 30%),
                radial-gradient(circle at bottom right, rgba(14, 116, 144, 0.20), transparent 35%),
                linear-gradient(180deg, #f8fafc 0%, #f4f1ea 100%);
        }
        .block-container { max-width: 1500px; padding-top: 1rem; padding-bottom: 1rem; }
        h1, h2, h3 { font-family: "Space Grotesk", "Aptos Display", "Trebuchet MS", sans-serif; letter-spacing: -0.02em; }
        .hero {
            background: linear-gradient(135deg, #102a43 0%, #0f766e 55%, #d97706 100%);
            color: #f8fafc; padding: 1.3rem 1.5rem; border-radius: 20px; margin-bottom: 1rem;
            box-shadow: 0 18px 50px rgba(15, 23, 42, 0.18);
        }
        .metric-card {
            background: rgba(255,255,255,0.84); border: 1px solid rgba(15,23,42,0.08);
            border-radius: 18px; padding: 1rem; box-shadow: 0 10px 30px rgba(15,23,42,0.08);
        }
        .label { font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; color: #486581; }
        .value { font-size: 2rem; font-weight: 700; color: #102a43; line-height: 1.1; }
        .section-note {
            background: rgba(255,255,255,0.72); border-left: 4px solid #0f766e;
            padding: 0.8rem 1rem; border-radius: 10px; margin-bottom: 1rem;
        }
        .attention-card {
            background: rgba(255,255,255,0.88); border: 1px solid rgba(217, 119, 6, 0.28);
            border-radius: 16px; padding: 0.95rem 1rem; box-shadow: 0 10px 24px rgba(15,23,42,0.07);
        }
        .workflow-card {
            background: rgba(255,255,255,0.90); border: 1px solid rgba(15,23,42,0.07);
            border-radius: 18px; padding: 1rem 1.1rem; box-shadow: 0 10px 24px rgba(15,23,42,0.06);
            min-height: 145px;
        }
        [data-testid="collapsedControl"] {
            background: rgba(16,42,67,0.95);
            border-radius: 999px;
            padding: 0.2rem 0.35rem;
            box-shadow: 0 8px 20px rgba(15,23,42,0.18);
        }
        section[data-testid="stSidebar"] {
            background: rgba(250,252,255,0.96);
            backdrop-filter: blur(16px);
            border-right: 1px solid rgba(15,23,42,0.08);
        }
        div[data-baseweb="tab-list"] button {
            border-radius: 999px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def _save_upload(uploaded_file, suffix: str | None = None) -> str:
    resolved_suffix = suffix or Path(uploaded_file.name).suffix or ".tmp"
    with tempfile.NamedTemporaryFile(delete=False, suffix=resolved_suffix) as handle:
        handle.write(uploaded_file.getvalue())
        return handle.name


def _org_codes(session) -> list[str]:
    return [item.code for item in session.scalars(select(Organization).order_by(Organization.code)).all()]


def _framework_codes(session) -> list[str]:
    return [item.code for item in session.scalars(select(Framework).order_by(Framework.code)).all()]


def _binding_codes(session, organization_code: str | None = None) -> list[str]:
    query = select(OrganizationFrameworkBinding).order_by(OrganizationFrameworkBinding.binding_code)
    if organization_code:
        organization = session.scalar(select(Organization).where(Organization.code == organization_code))
        if organization is None:
            return []
        query = query.where(OrganizationFrameworkBinding.organization_id == organization.id)
    return [item.binding_code for item in session.scalars(query).all()]


def _product_codes(session, organization_code: str) -> list[str]:
    organization = session.scalar(select(Organization).where(Organization.code == organization_code))
    if organization is None:
        return []
    return [item.code for item in session.scalars(select(Product).where(Product.organization_id == organization.id).order_by(Product.code)).all()]


def _flavor_codes(session, organization_code: str, product_code: str) -> list[str]:
    organization = session.scalar(select(Organization).where(Organization.code == organization_code))
    if organization is None:
        return []
    product = session.scalar(select(Product).where(Product.organization_id == organization.id, Product.code == product_code))
    if product is None:
        return []
    return [item.code for item in session.scalars(select(ProductFlavor).where(ProductFlavor.product_id == product.id).order_by(ProductFlavor.code)).all()]


def _default_section() -> str:
    with session_scope() as session:
        return GovernanceService(session).default_workspace_section()


def _default_unified_section() -> str:
    with session_scope() as session:
        governance = GovernanceService(session)
        override = governance.get_setting("workspace.unified_default_page")
        if override:
            return override
        return "Assistant Center" if governance.onboarding_status()["first_run_needed"] else "Control Framework Studio"


def _log_workspace_navigation(mode: str, page: str) -> None:
    previous = (
        st.session_state.get("_logged_workspace_mode"),
        st.session_state.get("_logged_workspace_page"),
    )
    current = (mode, page)
    if current == previous:
        return
    audit_event(
        action="workspace_navigation",
        actor=st.session_state.get("workspace_principal_key", "streamlit"),
        target_type="workspace_page",
        target_id=page,
        status="success",
        details={"mode": mode},
    )
    st.session_state["_logged_workspace_mode"] = mode
    st.session_state["_logged_workspace_page"] = page


def _profile_names(session) -> list[str]:
    return [item.profile_name for item in session.scalars(select(AwsCliProfile).order_by(AwsCliProfile.profile_name)).all()]


def _regions_json_from_csv(raw_value: str) -> str:
    regions = [item.strip() for item in raw_value.split(",") if item.strip()]
    return json.dumps(regions, indent=2)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clear_workspace_auth_state() -> None:
    for key in ("workspace_principal_key", "workspace_authenticated_at"):
        st.session_state.pop(key, None)


def _workspace_session_valid() -> bool:
    principal_key = st.session_state.get("workspace_principal_key")
    authenticated_at = st.session_state.get("workspace_authenticated_at")
    if not principal_key or not authenticated_at:
        return False
    try:
        login_time = datetime.fromisoformat(authenticated_at)
    except ValueError:
        _clear_workspace_auth_state()
        return False
    max_age = settings.workspace_session_timeout_minutes * 60
    if (datetime.now().astimezone() - login_time).total_seconds() > max_age:
        _clear_workspace_auth_state()
        return False
    st.session_state["workspace_authenticated_at"] = _utc_now_iso()
    return True


def _render_workspace_auth_gate() -> None:
    if not settings.workspace_auth_required:
        return
    if _workspace_session_valid():
        return
    should_rerun = False
    with session_scope() as session:
        auth = WorkspaceAuthService(session)
        _hero("Workspace Access", "Sign in before using the GRC workspace. The app stays offline-first, but the operator shell now has its own access gate.")
        st.markdown(
            '<div class="section-note">This protects local control narratives, assessments, evidence references, and release-governance views. If this is the first secure start, create the first workspace user here.</div>',
            unsafe_allow_html=True,
        )
        if auth.bootstrap_required():
            st.info("No workspace credentials exist yet. Create the first secure workspace user.")
            with st.form("workspace_auth_bootstrap"):
                principal_key = st.text_input("User key", help="Lowercase key for the first workspace user, for example `grc.lead`.")
                display_name = st.text_input("Display name")
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                password_confirm = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Create first workspace user", type="primary")
                if submitted:
                    if password != password_confirm:
                        st.warning("The password confirmation does not match.")
                    else:
                        try:
                            principal = auth.bootstrap_local_admin(
                                principal_key=principal_key,
                                display_name=display_name,
                                password=password,
                                email=email,
                            )
                            st.session_state["workspace_principal_key"] = principal.principal_key
                            st.session_state["workspace_authenticated_at"] = _utc_now_iso()
                            st.success("Workspace access was initialized successfully.")
                            should_rerun = True
                        except (ValidationError, WorkspaceAuthenticationError) as exc:
                            issues = exc.issues if isinstance(exc, ValidationError) else [str(exc)]
                            for issue in issues:
                                st.warning(issue)
            if should_rerun:
                pass
            else:
                st.stop()

        principals = auth.active_principals()
        if not principals:
            st.error("Workspace access is enabled, but there are no active users with credentials.")
            st.stop()
        principal_options = {f"{item.display_name} ({item.principal_key})": item.principal_key for item in principals}
        with st.form("workspace_auth_login"):
            principal_label = st.selectbox("Workspace user", list(principal_options))
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
            if submitted:
                try:
                    principal = auth.authenticate(principal_options[principal_label], password)
                    st.session_state["workspace_principal_key"] = principal.principal_key
                    st.session_state["workspace_authenticated_at"] = _utc_now_iso()
                    st.success(f"Signed in as {principal.display_name}.")
                    should_rerun = True
                except (ValidationError, WorkspaceAuthenticationError) as exc:
                    issues = exc.issues if isinstance(exc, ValidationError) else [str(exc)]
                    for issue in issues:
                        st.warning(issue)
    if should_rerun:
        st.rerun()
    st.stop()


def render_wizards() -> None:
    _hero("Wizards", "Guided setup for first-run onboarding and the highest-friction GRC authoring workflows.")
    st.markdown(
        '<div class="section-note">Phase 1 focuses on guided adoption: seed frameworks, create core entities, define approved mappings, register evidence plans, load questionnaires, and trigger scoped operations without jumping across multiple pages.</div>',
        unsafe_allow_html=True,
    )
    with session_scope() as session:
        governance = GovernanceService(session)
        framework_service = FrameworkService(session)
        workbench = WorkbenchService(session)
        questionnaire_service = QuestionnaireService(session)
        assessment_service = AssessmentService(session)
        onboarding = governance.onboarding_status()
        offline_mode = governance.offline_mode_enabled()

        st.progress(onboarding["progress"])
        metric_cols = st.columns(5)
        with metric_cols[0]:
            _metric("Onboarding", f'{onboarding["completed_steps"]}/{onboarding["total_steps"]}')
        with metric_cols[1]:
            _metric("Frameworks", str(onboarding["counts"]["frameworks"]))
        with metric_cols[2]:
            _metric("AWS Profiles", str(onboarding["counts"]["aws_profiles"]))
        with metric_cols[3]:
            _metric("Bindings", str(onboarding["counts"]["bindings"]))
        with metric_cols[4]:
            _metric("AWS Targets", str(onboarding["counts"]["aws_targets"]))

        st.caption(
            "Runtime mode: Offline-first"
            if offline_mode
            else "Runtime mode: AWS-enabled. Evidence collection expects `aws sso login --profile <name>` before execution."
        )

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Step": item["label"],
                        "Completed": item["completed"],
                        "Detail": item["detail"],
                    }
                    for item in onboarding["steps"]
                ]
            ),
            width="stretch",
            hide_index=True,
        )

        tab_first, tab_framework, tab_control, tab_target, tab_questionnaire, tab_assessment = st.tabs(
            [
                "First Run",
                "Framework Wizard",
                "Control Wizard",
                "AWS Target Wizard",
                "Questionnaire Wizard",
                "Assessment Wizard",
            ]
        )

        with tab_first:
            left, right = st.columns([1.1, 0.9])
            with left:
                st.subheader("Bootstrap")
                offline_toggle = st.checkbox(
                    "Enable offline-first mode",
                    value=offline_mode,
                    help="When enabled, metadata, frameworks, controls, questionnaires, and reporting remain available locally and AWS evidence collection is deferred.",
                )
                if offline_toggle != offline_mode:
                    governance.set_offline_mode(offline_toggle)
                    st.success("Runtime mode updated.")
                if st.button("Seed baseline framework templates", type="primary", key="wizard_seed_templates"):
                    touched = framework_service.seed_templates()
                    governance.set_setting(
                        "wizard.bootstrap.last_seed_count",
                        str(len(touched)),
                        "Last template seed count from the wizard",
                    )
                    st.success(f"Synchronized {len(touched)} framework template(s).")

                with st.form("wizard_first_org_form"):
                    st.markdown("#### Organization")
                    org_name = st.text_input("Organization name")
                    org_code = st.text_input("Organization code")
                    org_description = st.text_area("Description", height=90)
                    if st.form_submit_button("Create organization", type="primary") and org_name:
                        organization = workbench.create_organization(
                            name=org_name,
                            code=org_code or None,
                            description=org_description,
                        )
                        governance.set_setting(
                            "wizard.bootstrap.last_org",
                            organization.code,
                            "Last organization created from the first-run wizard",
                        )
                        st.success(f"Organization ready: {organization.code}")

                org_codes = _org_codes(session)
                framework_codes = _framework_codes(session)
                if org_codes:
                    with st.form("wizard_first_product_form"):
                        st.markdown("#### Product")
                        selected_org = st.selectbox("Organization", org_codes, key="wizard_first_product_org")
                        product_name = st.text_input("Product name")
                        product_code = st.text_input("Product code")
                        product_type = st.selectbox(
                            "Product type",
                            ["service", "platform", "feature", "component"],
                            key="wizard_first_product_type",
                        )
                        deployment_model = st.selectbox(
                            "Deployment model",
                            ["saas", "managed", "single-tenant", "self-hosted", "hybrid"],
                            key="wizard_first_product_deployment",
                        )
                        if st.form_submit_button("Create product", type="primary") and product_name:
                            product = workbench.create_product(
                                organization_code=selected_org,
                                name=product_name,
                                code=product_code or None,
                                product_type=product_type,
                                deployment_model=deployment_model,
                            )
                            st.success(f"Product ready: {product.code}")

                if org_codes and framework_codes:
                    with st.form("wizard_first_binding_form"):
                        st.markdown("#### Framework binding")
                        selected_org = st.selectbox("Organization ", org_codes, key="wizard_first_bind_org")
                        selected_framework = st.selectbox("Framework", framework_codes, key="wizard_first_bind_framework")
                        aws_profile = st.text_input("AWS profile")
                        aws_region = st.text_input("AWS region", value="eu-west-1")
                        if st.form_submit_button("Create binding", type="primary") and aws_profile:
                            binding = workbench.bind_framework(
                                organization_code=selected_org,
                                framework_code=selected_framework,
                                aws_profile=aws_profile,
                                aws_region=aws_region,
                            )
                            st.success(f"Binding ready: {binding.binding_code}")

            with right:
                st.subheader("Current baseline")
                frameworks = framework_service.list_frameworks()
                if frameworks:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Framework": item.code,
                                    "Version": item.version,
                                    "Controls": len(item.controls),
                                    "Source": item.source,
                                }
                                for item in frameworks
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("No frameworks are available yet. Seed the template catalog first.")

        with tab_framework:
            left, right = st.columns(2)
            with left:
                st.subheader("Template activation")
                templates = load_templates()
                if templates:
                    with st.form("wizard_template_activation_form"):
                        template_code = st.selectbox(
                            "Template",
                            [item["code"] for item in templates],
                            format_func=lambda code: next(
                                item["name"] for item in templates if item["code"] == code
                            ),
                        )
                        aws_profile = st.text_input("AWS profile ", help="Local AWS CLI profile to associate with the framework.")
                        aws_region = st.text_input("AWS region ", value="eu-west-1")
                        if st.form_submit_button("Activate template framework", type="primary") and aws_profile:
                            framework_service.seed_templates()
                            framework = framework_service.enable_framework(template_code, aws_profile, aws_region)
                            st.success(f"Framework active: {framework.code}")
                else:
                    st.info("No template files were found.")

            with right:
                st.subheader("Custom framework shell")
                with st.form("wizard_custom_framework_form"):
                    code = st.text_input("Framework code")
                    name = st.text_input("Framework name")
                    version = st.text_input("Version")
                    category = st.selectbox("Category", ["framework", "policy", "procedure", "standard"])
                    issuing_body = st.text_input("Issuing body")
                    jurisdiction = st.text_input("Jurisdiction", value="global")
                    source_url = st.text_input("Source URL")
                    description = st.text_area("Description", height=90)
                    first_control_id = st.text_input("First control ID")
                    first_control_title = st.text_input("First control title")
                    first_control_query = st.text_input("First control evidence query", value="manual_review")
                    if st.form_submit_button("Create custom framework", type="primary") and code and name and version:
                        framework = framework_service.create_framework_shell(
                            code=code,
                            name=name,
                            version=version,
                            category=category,
                            description=description,
                            issuing_body=issuing_body,
                            jurisdiction=jurisdiction,
                            source_url=source_url,
                        )
                        if first_control_id and first_control_title:
                            framework_service.upsert_framework_control(
                                framework_code=framework.code,
                                control_id=first_control_id,
                                title=first_control_title,
                                evidence_query=first_control_query,
                            )
                        st.success(f"Framework shell ready: {framework.code}")

        with tab_control:
            col_uc, col_map, col_plan = st.columns(3)
            with col_uc:
                st.subheader("Unified control")
                with st.form("wizard_unified_control_form"):
                    code = st.text_input("Code")
                    name = st.text_input("Name")
                    domain = st.text_input("Domain")
                    family = st.text_input("Family")
                    description = st.text_area("Description", height=90)
                    if st.form_submit_button("Save unified control", type="primary") and code and name:
                        unified = workbench.create_unified_control(
                            code=code,
                            name=name,
                            domain=domain,
                            family=family,
                            description=description,
                        )
                        st.success(f"Unified control ready: {unified.code}")

            with col_map:
                st.subheader("Approved mapping")
                unified_codes = [item.code for item in workbench.list_unified_controls()]
                framework_codes = _framework_codes(session)
                if unified_codes and framework_codes:
                    with st.form("wizard_mapping_form"):
                        unified_code = st.selectbox("Unified control", unified_codes, key="wizard_map_uc")
                        framework_code = st.selectbox("Framework ", framework_codes, key="wizard_map_fw")
                        framework = session.scalar(select(Framework).where(Framework.code == framework_code))
                        control_options = [
                            item.control_id
                            for item in session.scalars(
                                select(Control).where(Control.framework_id == framework.id).order_by(Control.control_id)
                            ).all()
                        ]
                        control_choice = st.selectbox("Framework control", control_options) if control_options else ""
                        mapping_type = st.selectbox(
                            "Mapping type",
                            ["mapped", "partial", "supports", "inherits"],
                        )
                        approval_status = st.selectbox(
                            "Approval status",
                            ["proposed", "approved", "rejected", "needs_review"],
                        )
                        reviewed_by = st.text_input("Reviewed by")
                        confidence = st.slider("Confidence", 0.0, 1.0, 0.8, 0.05)
                        rationale = st.text_area("Rationale", height=90)
                        approval_notes = st.text_area("Approval notes", height=70)
                        if st.form_submit_button("Save mapping", type="primary") and control_choice:
                            mapping = workbench.map_framework_control(
                                unified_control_code=unified_code,
                                framework_code=framework_code,
                                control_id=control_choice,
                                mapping_type=mapping_type,
                                rationale=rationale,
                                confidence=confidence,
                                approval_status=approval_status,
                                reviewed_by=reviewed_by,
                                approval_notes=approval_notes,
                            )
                            st.success(f"Mapping saved with state {mapping.approval_status}.")
                else:
                    st.info("Create at least one unified control and framework before mapping.")

            with col_plan:
                st.subheader("Evidence plan")
                framework_codes = _framework_codes(session)
                unified_codes = [item.code for item in workbench.list_unified_controls()]
                with st.form("wizard_evidence_plan_form"):
                    name = st.text_input("Plan name")
                    plan_code = st.text_input("Plan code")
                    plan_framework = st.selectbox("Framework", [""] + framework_codes)
                    plan_control = ""
                    if plan_framework:
                        framework = session.scalar(select(Framework).where(Framework.code == plan_framework))
                        control_options = [
                            item.control_id
                            for item in session.scalars(
                                select(Control).where(Control.framework_id == framework.id).order_by(Control.control_id)
                            ).all()
                        ]
                        plan_control = st.selectbox("Framework control ", [""] + control_options)
                    plan_unified = st.selectbox("Unified control ", [""] + unified_codes)
                    scope_type = st.selectbox("Scope type", ["binding", "product", "product_flavor", "organization"])
                    execution_mode = st.selectbox("Execution mode", ["manual", "assisted", "autonomous"])
                    available_script_collectors = [
                        f"script:{item.module_code}" for item in ScriptModuleService(session).list_modules()
                    ]
                    collector_choices = [""] + sorted(COLLECTORS.keys()) + available_script_collectors
                    collector_key = st.selectbox(
                        "Collector key",
                        collector_choices,
                        help="Built-in collectors and registered external script modules are both supported.",
                    )
                    evidence_type = st.selectbox(
                        "Evidence type",
                        ["configuration_snapshot", "report", "attestation", "artifact_bundle"],
                    )
                    review_frequency = st.selectbox("Review frequency", ["", "monthly", "quarterly", "yearly"])
                    minimum_freshness_days = st.number_input("Minimum freshness days", min_value=1, value=30, step=1)
                    instructions = st.text_area("Instructions", height=90)
                    expected_artifacts_json = st.text_area("Expected artifacts JSON", value="[]", height=70)
                    if st.form_submit_button("Save evidence plan", type="primary") and name:
                        plan = workbench.upsert_evidence_collection_plan(
                            name=name,
                            framework_code=plan_framework or None,
                            control_id=plan_control or None,
                            unified_control_code=plan_unified or None,
                            plan_code=plan_code or None,
                            scope_type=scope_type,
                            execution_mode=execution_mode,
                            collector_key=collector_key,
                            evidence_type=evidence_type,
                            instructions=instructions,
                            expected_artifacts_json=expected_artifacts_json,
                            review_frequency=review_frequency,
                            minimum_freshness_days=int(minimum_freshness_days),
                        )
                        st.success(f"Evidence plan ready: {plan.plan_code}")

                plans = workbench.list_evidence_collection_plans()
                if plans:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Plan": item.plan_code,
                                    "Scope": item.scope_type,
                                    "Mode": item.execution_mode,
                                    "Framework": item.framework.code if item.framework else "",
                                    "Unified Control": item.unified_control.code if item.unified_control else "",
                                }
                                for item in plans[:10]
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )

        with tab_target:
            st.subheader("AWS SSO evidence targets")
            st.markdown(
                '<div class="section-note">Targets tell the system where a control actually lives: which AWS account IDs, which regions, and which local SSO profile the user will authenticate with through `aws sso login`.</div>',
                unsafe_allow_html=True,
            )
            left, right = st.columns([1.1, 0.9])
            with left:
                org_codes = _org_codes(session)
                if not org_codes:
                    st.info("Create an organization and framework binding first.")
                else:
                    with st.form("wizard_aws_target_form"):
                        org_code = st.selectbox("Organization", org_codes, key="wizard_target_org")
                        binding_codes = _binding_codes(session, org_code)
                        binding_code = st.selectbox("Framework binding", [""] + binding_codes)
                        product_codes = _product_codes(session, org_code)
                        product_code = st.selectbox("Product", [""] + product_codes, key="wizard_target_product")
                        flavor_codes = _flavor_codes(session, org_code, product_code) if product_code else []
                        flavor_code = st.selectbox("Flavor", [""] + flavor_codes, key="wizard_target_flavor")
                        unified_codes = [item.code for item in workbench.list_unified_controls()]
                        unified_code = st.selectbox("Unified control", [""] + unified_codes, key="wizard_target_uc")
                        framework_code = st.selectbox("Framework", [""] + _framework_codes(session), key="wizard_target_fw")
                        control_choice = ""
                        if framework_code:
                            framework = session.scalar(select(Framework).where(Framework.code == framework_code))
                            control_options = [
                                item.control_id
                                for item in session.scalars(
                                    select(Control).where(Control.framework_id == framework.id).order_by(Control.control_id)
                                ).all()
                            ]
                            control_choice = st.selectbox("Framework control", [""] + control_options, key="wizard_target_control")
                        name = st.text_input("Target name")
                        target_code = st.text_input("Target code")
                        aws_profile = st.text_input("AWS profile", help="This local profile will be used after the user runs `aws sso login --profile ...`.")
                        aws_account_id = st.text_input("AWS Account ID")
                        role_name = st.text_input("Role name", help="Informational only for Phase 1.")
                        regions_csv = st.text_input("Regions", value="eu-west-1", help="Comma-separated list, for example `eu-west-1,eu-central-1`.")
                        is_primary = st.checkbox("Primary target", value=True)
                        notes = st.text_area("Notes", height=90)
                        if st.form_submit_button("Save AWS target", type="primary") and org_code and name and aws_profile:
                            target = workbench.upsert_aws_evidence_target(
                                organization_code=org_code,
                                binding_code=binding_code or None,
                                product_code=product_code or None,
                                product_flavor_code=flavor_code or None,
                                unified_control_code=unified_code or None,
                                framework_code=framework_code or None,
                                control_id=control_choice or None,
                                name=name,
                                target_code=target_code or None,
                                aws_profile=aws_profile,
                                aws_account_id=aws_account_id,
                                role_name=role_name,
                                regions_json=_regions_json_from_csv(regions_csv),
                                execution_mode="aws_sso_login",
                                is_primary=is_primary,
                                notes=notes,
                            )
                            st.success(f"AWS evidence target ready: {target.target_code}")
            with right:
                targets = workbench.list_aws_evidence_targets()
                if targets:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Target": item.target_code,
                                    "Profile": item.aws_profile,
                                    "Account": item.aws_account_id,
                                    "Regions": ", ".join(json.loads(item.regions_json or "[]")),
                                    "Product": item.product.code if item.product else "",
                                    "Flavor": item.product_flavor.code if item.product_flavor else "",
                                    "Control": item.control.control_id if item.control else "",
                                    "Unified": item.unified_control.code if item.unified_control else "",
                                }
                                for item in targets[:20]
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.info("No AWS evidence targets have been registered yet.")

        with tab_questionnaire:
            st.subheader("Implementation-driven questionnaire loading")
            org_codes = _org_codes(session)
            if not org_codes:
                st.info("Create an organization, product, and implementation records before loading a questionnaire.")
            else:
                org_code = st.selectbox("Organization", org_codes, key="wizard_q_org")
                product_codes = _product_codes(session, org_code)
                if not product_codes:
                    st.info("Create a product first for the selected organization.")
                else:
                    product_code = st.selectbox("Product", product_codes, key="wizard_q_product")
                    flavor_codes = _flavor_codes(session, org_code, product_code)
                    flavor_code = st.selectbox("Flavor", [""] + flavor_codes, key="wizard_q_flavor")
                    uploaded = st.file_uploader(
                        "Upload questionnaire CSV",
                        type=["csv"],
                        key="wizard_questionnaire_file",
                    )
                    if uploaded is not None:
                        csv_path = _save_upload(uploaded)
                        try:
                            preview = questionnaire_service.preview_questionnaire_answers(
                                organization_code=org_code,
                                product_code=product_code,
                                csv_path=csv_path,
                                product_flavor_code=flavor_code or None,
                            )
                            if preview:
                                st.dataframe(pd.DataFrame(preview), width="stretch", hide_index=True)
                                questionnaire_name = st.text_input(
                                    "Questionnaire name",
                                    value=uploaded.name.replace(".csv", ""),
                                    key="wizard_q_name",
                                )
                                customer_name = st.text_input("Customer name", key="wizard_q_customer")
                                if st.button("Store questionnaire", type="primary", key="wizard_q_store"):
                                    questionnaire = questionnaire_service.import_csv_questionnaire(
                                        organization_code=org_code,
                                        product_code=product_code,
                                        csv_path=csv_path,
                                        name=questionnaire_name,
                                        customer_name=customer_name,
                                        product_flavor_code=flavor_code or None,
                                    )
                                    st.success(f"Questionnaire stored: {questionnaire.name}")
                            else:
                                st.warning("No draft answers could be generated from the current implementation records.")
                        finally:
                            Path(csv_path).unlink(missing_ok=True)

        with tab_assessment:
            st.subheader("Scoped evidence and assessment run")
            org_codes = _org_codes(session)
            if not org_codes:
                st.info("Create an organization and at least one framework binding first.")
            else:
                if offline_mode:
                    st.warning("Offline-first mode is enabled. New collection will be deferred and assessments will use local evidence only.")
                org_code = st.selectbox("Organization", org_codes, key="wizard_assess_org")
                binding_codes = _binding_codes(session, org_code)
                if not binding_codes:
                    st.info("Create a framework binding first for the selected organization.")
                    binding_code = ""
                else:
                    binding_code = st.selectbox("Binding", binding_codes)
                product_codes = _product_codes(session, org_code)
                product_code = st.selectbox("Product", [""] + product_codes, key="wizard_assess_product")
                flavor_codes = _flavor_codes(session, org_code, product_code) if product_code else []
                flavor_code = st.selectbox("Flavor", [""] + flavor_codes, key="wizard_assess_flavor")
                action = st.selectbox("Action", ["collect evidence only", "collect evidence and assess"])
                login_confirmed = offline_mode
                if binding_code and not offline_mode:
                    wizard_plan = EvidenceService(session).build_collection_plan_for_binding(
                        binding_code=binding_code,
                        product_code=product_code or None,
                        product_flavor_code=flavor_code or None,
                    )
                    if wizard_plan["profiles"]:
                        st.caption("Required SSO login profiles for this wizard run")
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "Profile": item["aws_profile"],
                                        "Accounts": ", ".join(item["aws_account_ids"]),
                                        "Regions": ", ".join(item["regions"]),
                                        "Controls": len(item["controls"]),
                                        "Registered": item["registered_in_app"],
                                        "Login": item["login_command"],
                                    }
                                    for item in wizard_plan["profiles"]
                                ]
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                        if wizard_plan["missing_profile_metadata"]:
                            st.warning(
                                "Some required profiles are not registered in the app metadata: "
                                + ", ".join(wizard_plan["missing_profile_metadata"])
                            )
                        login_confirmed = st.checkbox(
                            "I have completed aws sso login for the required profiles for this run",
                            value=False,
                            key=f"wizard_login_confirmed_{binding_code}_{product_code}_{flavor_code}",
                        )
                    else:
                        login_confirmed = True
                if st.button("Run operation", type="primary", disabled=not binding_code or not login_confirmed, key="wizard_run_operation"):
                    if action == "collect evidence only":
                        results = EvidenceService(session).collect_for_binding(
                            binding_code=binding_code,
                            product_code=product_code or None,
                            product_flavor_code=flavor_code or None,
                        )
                        st.success(f"Collected {len(results)} evidence item(s).")
                    else:
                        run = assessment_service.run_binding_assessment(
                            binding_code=binding_code,
                            product_code=product_code or None,
                            product_flavor_code=flavor_code or None,
                        )
                        st.success(f"Assessment completed with score {run.score}%.")


def render_overview() -> None:
    _hero("my_grc Workspace", "Product-aware GRC operations across frameworks, products, flavors, mappings, questionnaires, and maturity.")
    with session_scope() as session:
        governance = GovernanceService(session)
        phase1 = Phase1MaturityService(session).assess()
        enterprise = EnterpriseMaturityService(session).assess()
        review_summary = ReviewQueueService(session).summary()
        metrics = {
            "Frameworks": session.scalar(select(func.count()).select_from(Framework)) or 0,
            "Unified Controls": session.scalar(select(func.count()).select_from(UnifiedControl)) or 0,
            "Organizations": session.scalar(select(func.count()).select_from(Organization)) or 0,
            "Products": session.scalar(select(func.count()).select_from(Product)) or 0,
            "AWS Profiles": session.scalar(select(func.count()).select_from(AwsCliProfile)) or 0,
            "Implementations": session.scalar(select(func.count()).select_from(ControlImplementation)) or 0,
            "Control Profiles": session.scalar(select(func.count()).select_from(ProductControlProfile)) or 0,
            "Questionnaires": session.scalar(select(func.count()).select_from(CustomerQuestionnaire)) or 0,
            "Connections": session.scalar(select(func.count()).select_from(ConfluenceConnection)) or 0,
            "AWS Targets": session.scalar(select(func.count()).select_from(AwsEvidenceTarget)) or 0,
            "Import Batches": session.scalar(select(func.count()).select_from(FrameworkImportBatch)) or 0,
            "Script Modules": session.scalar(select(func.count()).select_from(AssessmentScriptModule)) or 0,
            "Secrets": session.scalar(select(func.count()).select_from(SecretMetadata)) or 0,
            "Lifecycle Events": session.scalar(select(func.count()).select_from(LifecycleEvent)) or 0,
            "Collectors": len(COLLECTORS),
        }
        cols = st.columns(5)
        for idx, item in enumerate(metrics.items()):
            with cols[idx % 5]:
                _metric(item[0], str(item[1]))

        runtime_label = "Offline-first mode is enabled." if governance.offline_mode_enabled() else "AWS runtime is enabled through local `aws sso login` profiles."
        st.markdown(f'<div class="section-note">Seeded frameworks and collector coverage are visible below. The project now includes encrypted evidence-at-rest, OS-keyring-backed secret handling, lifecycle event tracking for major GRC objects, and product-aware AWS evidence targets. {runtime_label}</div>', unsafe_allow_html=True)
        template_df = pd.DataFrame(
            [{"Code": item["code"], "Framework": item["name"], "Version": item["version"], "Controls": len(item.get("controls", []))} for item in load_templates()]
        )
        st.dataframe(template_df, width="stretch", hide_index=True)

        st.subheader("Phase 1 Readiness")
        st.caption(f"Estimated maturity toward the Phase 1 4/5 target: {phase1['overall_score']}/4.0")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Area": item["area"],
                        "Score": item["score"],
                        "Target": item["target"],
                        "Top Gap": item["gaps"][0] if item["gaps"] else "",
                    }
                    for item in phase1["areas"]
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        if phase1["top_blockers"]:
            st.markdown("#### Main blockers to reach 4/5")
            for blocker in phase1["top_blockers"][:6]:
                st.write(f"- {blocker}")

        st.subheader("Unified Level-4 Maturity")
        top_cols = st.columns(4)
        with top_cols[0]:
            _metric("Enterprise", f"{enterprise['overall_score']}/4.0")
        with top_cols[1]:
            _metric("Queue", str(review_summary["total"]))
        with top_cols[2]:
            _metric("Critical", str(review_summary["priorities"].get("critical", 0)))
        with top_cols[3]:
            _metric("High", str(review_summary["priorities"].get("high", 0)))

        maturity_tab, queue_tab = st.tabs(["Phase View", "Needs Attention"])
        with maturity_tab:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Area": item["area"],
                            "Score": item["score"],
                            "Target": item["target"],
                            "Top Gap": item["gaps"][0] if item["gaps"] else "",
                        }
                        for item in enterprise["phases"] + enterprise["qualities"]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            if enterprise["top_blockers"]:
                st.markdown("#### Priority blockers to reach a level-4 product")
                for blocker in enterprise["top_blockers"][:8]:
                    st.write(f"- {blocker}")
        with queue_tab:
            if review_summary["top_items"]:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Category": item["category"],
                                "Priority": item["priority"],
                                "Status": item["status"],
                                "Reference": item["reference"],
                                "Title": item["title"],
                                "Detail": item["detail"],
                            }
                            for item in review_summary["top_items"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.success("No pending review items are currently blocking enterprise maturity.")


def render_standards() -> None:
    _hero("Standards", "Review frameworks, control metadata, and supported evidence patterns.")
    with session_scope() as session:
        frameworks = FrameworkService(session).list_frameworks()
        if frameworks:
            st.dataframe(
                pd.DataFrame(
                    [{"Code": item.code, "Name": item.name, "Version": item.version, "Controls": len(item.controls), "Active": item.active} for item in frameworks]
                ),
                width="stretch",
                hide_index=True,
            )
            selected = st.selectbox("Inspect framework controls", [item.code for item in frameworks])
            framework = session.scalar(select(Framework).where(Framework.code == selected))
            controls = session.scalars(select(Control).where(Control.framework_id == framework.id).order_by(Control.control_id)).all()
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Control ID": item.control_id,
                            "Title": item.title,
                            "Severity": item.severity,
                            "Evidence Query": item.evidence_query,
                            "Check Type": item.metadata_entry.check_type if item.metadata_entry else "",
                        }
                        for item in controls
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("No frameworks seeded yet.")


def render_portfolio() -> None:
    _hero("Portfolio", "Create organizations, products, flavors, AWS bindings, and implementation records.")
    with session_scope() as session:
        service = WorkbenchService(session)
        tab_org, tab_product, tab_impl = st.tabs(["Organizations", "Products & Flavors", "Bindings & Implementations"])
        with tab_org:
            with st.form("org_form"):
                name = st.text_input("Organization name")
                code = st.text_input("Organization code")
                description = st.text_area("Description", height=100)
                if st.form_submit_button("Save organization", type="primary") and name:
                    service.create_organization(name=name, code=code or None, description=description)
                    st.success("Organization saved.")
            orgs = service.list_organizations()
            if orgs:
                st.dataframe(pd.DataFrame([{"Code": item.code, "Name": item.name, "Status": item.status} for item in orgs]), width="stretch", hide_index=True)

        with tab_product:
            org_codes = _org_codes(session)
            if not org_codes:
                st.info("Create an organization first so products and flavors can be scoped correctly.")
                return
            left, right = st.columns(2)
            with left:
                with st.form("product_form"):
                    org_code = st.selectbox("Organization", org_codes)
                    name = st.text_input("Product name")
                    code = st.text_input("Product code")
                    product_type = st.selectbox("Product type", ["service", "platform", "feature", "component"])
                    deployment_model = st.selectbox("Deployment model", ["saas", "managed", "single-tenant", "self-hosted", "hybrid"])
                    owner = st.text_input("Owner")
                    if st.form_submit_button("Save product", type="primary") and org_code and name:
                        service.create_product(organization_code=org_code, name=name, code=code or None, product_type=product_type, deployment_model=deployment_model, owner=owner)
                        st.success("Product saved.")
            with right:
                with st.form("flavor_form"):
                    org_code = st.selectbox("Organization ", org_codes, key="flavor_org")
                    product_codes = _product_codes(session, org_code) if org_code else []
                    if not product_codes:
                        st.info("Create a product first for the selected organization.")
                        product_code = ""
                    else:
                        product_code = st.selectbox("Product", product_codes)
                    name = st.text_input("Flavor name")
                    code = st.text_input("Flavor code")
                    hosting_model = st.text_input("Hosting model")
                    region_scope = st.text_input("Region scope")
                    if st.form_submit_button("Save flavor", type="primary") and org_code and product_code and name:
                        service.create_product_flavor(organization_code=org_code, product_code=product_code, name=name, code=code or None, hosting_model=hosting_model, region_scope=region_scope)
                        st.success("Flavor saved.")
            products = service.list_products()
            if products:
                st.dataframe(pd.DataFrame([{"Organization": item.organization.code, "Product": item.code, "Name": item.name, "Type": item.product_type, "Deployment": item.deployment_model} for item in products]), width="stretch", hide_index=True)

        with tab_impl:
            left, right = st.columns(2)
            with left:
                with st.form("binding_form"):
                    org_codes = _org_codes(session)
                    framework_codes = _framework_codes(session)
                    if not org_codes or not framework_codes:
                        st.info("Seed at least one framework and create one organization before creating bindings.")
                        org_code = ""
                        framework_code = ""
                    else:
                        org_code = st.selectbox("Organization  ", org_codes, key="bind_org")
                        framework_code = st.selectbox("Framework", framework_codes)
                    connection_names = [item.name for item in ConfluenceConnectionService(session).list_connections()]
                    confluence_connection = st.selectbox("Confluence connection", [""] + connection_names)
                    aws_profile = st.text_input("AWS profile")
                    aws_region = st.text_input("AWS region", value="eu-west-1")
                    if st.form_submit_button("Bind framework", type="primary") and org_code and framework_code and aws_profile:
                        service.bind_framework(
                            organization_code=org_code,
                            framework_code=framework_code,
                            aws_profile=aws_profile,
                            aws_region=aws_region,
                            confluence_connection_name=confluence_connection or None,
                        )
                        st.success("Binding saved.")
                with st.form("impl_form"):
                    org_codes = _org_codes(session)
                    unified_codes = [item.code for item in service.list_unified_controls()]
                    framework_codes = _framework_codes(session)
                    if not org_codes:
                        st.info("Create an organization before adding implementations.")
                        org_code = ""
                        product_code = ""
                        unified_code = ""
                        framework_code = ""
                        control_id = ""
                        flavor_code = ""
                    else:
                        org_code = st.selectbox("Organization   ", org_codes, key="impl_org")
                        product_codes = _product_codes(session, org_code) if org_code else []
                        if not product_codes:
                            st.info("Create a product before adding implementations.")
                            product_code = ""
                        else:
                            product_code = st.selectbox("Product ", product_codes)
                        flavor_codes = _flavor_codes(session, org_code, product_code) if org_code and product_code else []
                        flavor_code = st.selectbox("Flavor", [""] + flavor_codes)
                        unified_code = st.selectbox("Unified control", [""] + unified_codes)
                        framework_code = st.selectbox("Framework control source", [""] + framework_codes)
                        control_id = ""
                        if framework_code:
                            framework = session.scalar(select(Framework).where(Framework.code == framework_code))
                            controls = session.scalars(
                                select(Control).where(Control.framework_id == framework.id).order_by(Control.control_id)
                            ).all()
                            control_options = [item.control_id for item in controls]
                            control_id = st.selectbox("Framework control", [""] + control_options)
                    title = st.text_input("Implementation title")
                    owner = st.text_input("Owner ")
                    status = st.selectbox("Status", ["draft", "planned", "implemented", "in_review", "operational"])
                    implementation_code = st.text_input("Implementation code", help="Optional stable identifier. Leave blank to auto-generate from scope and control.")
                    objective = st.text_area("Objective", height=90)
                    impl_general = st.text_area("General implementation", height=100)
                    impl_aws = st.text_area("AWS implementation", height=120)
                    test_plan = st.text_area("Test plan", height=100)
                    if st.form_submit_button("Save implementation", type="primary") and org_code and product_code and title:
                        service.upsert_control_implementation(
                            organization_code=org_code,
                            product_code=product_code,
                            product_flavor_code=flavor_code or None,
                            unified_control_code=unified_code or None,
                            framework_code=framework_code or None,
                            control_id=control_id or None,
                            title=title,
                            implementation_code=implementation_code or None,
                            owner=owner,
                            status=status,
                            objective=objective,
                            impl_general=impl_general,
                            impl_aws=impl_aws,
                            test_plan=test_plan,
                        )
                        st.success("Implementation saved.")
            with right:
                bindings = service.list_framework_bindings()
                if bindings:
                    st.dataframe(pd.DataFrame([{"Binding": item.binding_code, "Organization": item.organization.code, "Framework": item.framework.code, "AWS Profile": item.aws_profile, "AWS Region": item.aws_region, "Confluence": item.confluence_connection.name if item.confluence_connection else ""} for item in bindings]), width="stretch", hide_index=True)
                implementations = service.list_control_implementations()
                if implementations:
                    st.dataframe(pd.DataFrame([{"ID": item.id, "Organization": item.organization.code, "Product": item.product.code if item.product else "", "Flavor": item.product_flavor.code if item.product_flavor else "", "Title": item.title, "Status": item.status} for item in implementations]), width="stretch", hide_index=True)


def render_unified_controls() -> None:
    render_control_framework_studio()
    return
    _hero("Unified Controls", "Manage the common control backbone and map framework controls into it.")
    with session_scope() as session:
        service = WorkbenchService(session)
        left, right = st.columns(2)
        with left:
            with st.form("ucf_form"):
                code = st.text_input("Unified control code")
                name = st.text_input("Unified control name")
                domain = st.text_input("Domain")
                family = st.text_input("Family")
                description = st.text_area("Description", height=100)
                if st.form_submit_button("Save unified control", type="primary") and code and name:
                    service.create_unified_control(code=code, name=name, domain=domain, family=family, description=description)
                    st.success("Unified control saved.")
        with right:
            unified_codes = [item.code for item in service.list_unified_controls()]
            framework_codes = _framework_codes(session)
            if not unified_codes or not framework_codes:
                st.info("Create unified controls and seed frameworks before creating mappings.")
            else:
                with st.form("map_form"):
                    unified_code = st.selectbox("Unified control", unified_codes)
                    framework_code = st.selectbox("Framework", framework_codes)
                    framework = session.scalar(select(Framework).where(Framework.code == framework_code))
                    control_options = [item.control_id for item in session.scalars(select(Control).where(Control.framework_id == framework.id).order_by(Control.control_id)).all()]
                    if not control_options:
                        st.info("The selected framework does not have controls yet.")
                        control_id = ""
                    else:
                        control_id = st.selectbox("Framework control", control_options)
                    rationale = st.text_area("Rationale", height=100)
                    if st.form_submit_button("Create mapping", type="primary") and unified_code and framework_code and control_id:
                        service.map_framework_control(unified_control_code=unified_code, framework_code=framework_code, control_id=control_id, rationale=rationale, confidence=0.8)
                        st.success("Mapping saved.")

        unified_controls = service.list_unified_controls()
        if unified_controls:
            st.dataframe(pd.DataFrame([{"Code": item.code, "Name": item.name, "Domain": item.domain, "Family": item.family, "Severity": item.default_severity} for item in unified_controls]), width="stretch", hide_index=True)


def render_mapping_lab() -> None:
    render_control_framework_studio()
    return
    _hero("Mapping Lab", "Upload CSVs and let the system propose unified-control associations for human review.")
    st.markdown('<div class="section-note">This is the first autonomy layer for mappings. It reads CSV rows, compares them to the existing unified-control library, and ranks likely matches.</div>', unsafe_allow_html=True)
    with session_scope() as session:
        framework_codes = _framework_codes(session)
        framework_code = st.selectbox(
            "Framework context",
            [""] + framework_codes,
            help="Optional. Select a framework if you want to persist the top matches into the governed review queue.",
        )
    uploaded = st.file_uploader("Upload a control CSV", type=["csv"])
    if uploaded is None:
        st.info("Upload a CSV to preview suggestions.")
        return
    csv_path = _save_upload(uploaded)
    try:
        with session_scope() as session:
            suggestion_service = SuggestionService(session)
            suggestions = suggestion_service.suggest_unified_control_matches_from_csv(csv_path, limit=3)
            rows = []
            for item in suggestions:
                for rank, match in enumerate(item["matches"], start=1):
                    rows.append(
                        {
                            "External ID": item["external_id"],
                            "Title": item["title"],
                            "Rank": rank,
                            "Unified Control": match["unified_control_code"],
                            "Unified Name": match["unified_control_name"],
                            "Score": match["score"],
                            "Rationale": match["rationale"],
                        }
                    )
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
                if framework_code:
                    if st.button("Capture top suggestions for review", type="primary"):
                        try:
                            stored = suggestion_service.capture_mapping_suggestions_from_csv(
                                framework_code=framework_code,
                                csv_path=csv_path,
                                limit=3,
                            )
                            st.success(f"Captured {len(stored)} suggestion(s) for governance review.")
                        except ValueError as exc:
                            st.error(str(exc))
                else:
                    st.caption("Select a framework context to persist the suggested matches into the review queue.")
            else:
                st.warning("No suggestions could be produced.")
    finally:
        Path(csv_path).unlink(missing_ok=True)


def render_import_studio() -> None:
    render_control_framework_studio()
    return
    _hero(
        "Import Studio",
        "Bring external frameworks and existing assessment scripts into the governed my_grc operating model.",
    )
    st.markdown(
        '<div class="section-note">Use this workspace to import authoritative framework source files with traceability, then register existing Python assessment scripts so evidence plans can execute them like native collectors.</div>',
        unsafe_allow_html=True,
    )
    with session_scope() as session:
        import_service = FrameworkImportService(session)
        script_service = ScriptModuleService(session)
        workbench = WorkbenchService(session)
        framework_codes = _framework_codes(session)
        org_codes = _org_codes(session)
        unified_codes = [item.code for item in workbench.list_unified_controls()]

        tab_framework, tab_traceability, tab_scripts = st.tabs(
            ["Framework Import Wizard", "Traceability", "Script Modules"]
        )

        with tab_framework:
            pivot_framework_code = GovernanceService(session).pivot_framework_code()
            st.markdown("#### Secure Controls Framework Pivot Wizard")
            st.caption(
                "Use this fast lane to import the Secure Controls Framework workbook, create the converged baseline controls, and capture authoritative-source references such as NIST and CCN-STIC."
            )
            if pivot_framework_code:
                st.info(f"Current pivot framework: `{pivot_framework_code}`")
            scf_upload = st.file_uploader(
                "Upload Secure Controls Framework workbook",
                type=["xlsx", "xls"],
                key="scf_pivot_workbook",
                help="Recommended for the official SCF workbook such as secure-controls-framework-scf-2025-3-1.xlsx.",
            )
            if scf_upload is not None:
                scf_path = _save_upload(scf_upload)
                try:
                    scf_actor = st.text_input("SCF import actor", value="workspace_scf_import")
                    scf_sheet = st.text_input("SCF worksheet", value="SCF 2025.3.1")
                    scf_make_pivot = st.checkbox(
                        "Make Secure Controls Framework the pivot baseline",
                        value=True,
                        key="scf_make_pivot",
                    )
                    if st.button("Import Secure Controls Framework", type="primary", key="import_scf_workbook"):
                        try:
                            result = import_service.import_secure_controls_framework(
                                file_path=scf_path,
                                actor=scf_actor,
                                sheet_name=scf_sheet,
                                mark_as_pivot=scf_make_pivot,
                            )
                            summary = result["summary"]
                            st.success(
                                "Imported SCF with "
                                f"{summary['imported_count']} requirement(s), "
                                f"{summary['created_unified_controls']} baseline control(s), "
                                f"{summary['created_mappings']} approved mapping(s), "
                                f"{summary['created_reference_documents']} reference document(s), and "
                                f"{summary['created_reference_links']} reference link(s)."
                            )
                        except ValueError as exc:
                            st.error(str(exc))
                finally:
                    Path(scf_path).unlink(missing_ok=True)

            st.markdown("---")
            st.markdown("#### Generic Framework Import Wizard")
            uploaded = st.file_uploader(
                "Upload framework source",
                type=["csv", "xlsx", "xls"],
                help="CSV and spreadsheet sources are supported. This works well for sources like the CSA CCM spreadsheet.",
                key="generic_framework_upload",
            )
            if uploaded is None:
                st.info("Upload a CSV or spreadsheet to start the framework import wizard.")
            else:
                file_path = _save_upload(uploaded)
                try:
                    available_sheets = import_service.available_sheets(file_path)
                    selected_sheet = ""
                    if available_sheets:
                        selected_sheet = st.selectbox("Worksheet", available_sheets)
                    initial_preview = import_service.preview_source(file_path=file_path, sheet_name=selected_sheet)
                    st.caption("Map the source columns into the normalized my_grc import format.")
                    column_mapping = {}
                    mapping_cols = st.columns(3)
                    logical_fields = [
                        ("external_id", "Requirement ID"),
                        ("title", "Requirement title"),
                        ("description", "Requirement text"),
                        ("domain", "Domain"),
                        ("family", "Family"),
                        ("section", "Section"),
                        ("source_reference", "Source reference"),
                        ("severity", "Severity"),
                        ("aws_guidance", "AWS guidance"),
                    ]
                    source_columns = [""] + initial_preview["columns"]
                    for idx, (field_name, label) in enumerate(logical_fields):
                        detected = initial_preview["column_mapping"].get(field_name, "")
                        detected_index = source_columns.index(detected) if detected in source_columns else 0
                        with mapping_cols[idx % 3]:
                            column_mapping[field_name] = st.selectbox(
                                label,
                                source_columns,
                                index=detected_index,
                                key=f"framework_import_{uploaded.name}_{field_name}",
                            )
                    preview = import_service.preview_source(
                        file_path=file_path,
                        sheet_name=selected_sheet,
                        column_mapping=column_mapping,
                    )
                    st.dataframe(pd.DataFrame(preview["records"]), width="stretch", hide_index=True)
                    if preview["unmapped_fields"]:
                        st.caption("Unmapped fields: " + ", ".join(preview["unmapped_fields"]))

                    existing_framework = st.checkbox("Import into an existing framework", value=False)
                    if existing_framework and framework_codes:
                        existing_code = st.selectbox("Framework", framework_codes, key="framework_import_existing_code")
                        framework = session.scalar(select(Framework).where(Framework.code == existing_code))
                        framework_code = framework.code
                        framework_name = framework.name
                        framework_version = framework.version
                        category = framework.category
                        description = framework.description
                        issuing_body = framework.authority_document.issuing_body if framework.authority_document else ""
                        jurisdiction = framework.authority_document.jurisdiction if framework.authority_document else "global"
                    else:
                        framework_code = st.text_input("Framework code", value=Path(uploaded.name).stem.upper())
                        framework_name = st.text_input("Framework name")
                        framework_version = st.text_input("Framework version")
                        category = st.selectbox("Category", ["framework", "policy", "procedure", "standard"])
                        description = st.text_area("Framework description", height=90)
                        issuing_body = st.text_input("Issuing body")
                        jurisdiction = st.text_input("Jurisdiction", value="global")

                    source_name = st.text_input("Source name", value=uploaded.name)
                    source_url = st.text_input("Source URL")
                    source_version = st.text_input("Source version")
                    mapping_mode = st.selectbox(
                        "Unified-control strategy",
                        [
                            "suggest_only",
                            "map_existing",
                            "create_baseline",
                            "none",
                        ],
                        format_func=lambda item: {
                            "suggest_only": "Capture governed mapping suggestions",
                            "map_existing": "Auto-map to existing unified controls when confidence is high",
                            "create_baseline": "Extend the unified-control baseline for unmatched requirements",
                            "none": "Import framework requirements only",
                        }[item],
                    )
                    auto_approve = st.checkbox(
                        "Approve generated mappings immediately",
                        value=False,
                        help="Leave this off if you want new mappings to flow through the review queue first.",
                    )
                    threshold = st.slider("Auto-map confidence threshold", 0.5, 0.99, 0.84, 0.01)
                    actor = st.text_input("Import actor", value="workspace_import_wizard")
                    if st.button("Import framework source", type="primary"):
                        try:
                            result = import_service.import_source(
                                file_path=file_path,
                                framework_code=framework_code,
                                framework_name=framework_name or framework_code,
                                framework_version=framework_version or "imported",
                                source_name=source_name,
                                source_type=Path(uploaded.name).suffix.lstrip("."),
                                source_url=source_url,
                                source_version=source_version,
                                sheet_name=selected_sheet,
                                column_mapping=column_mapping,
                                category=category,
                                description=description,
                                issuing_body=issuing_body,
                                jurisdiction=jurisdiction,
                                actor=actor,
                                mapping_mode=mapping_mode,
                                auto_mapping_threshold=threshold,
                                auto_approve_mappings=auto_approve,
                            )
                            summary = result["summary"]
                            st.success(
                                "Imported "
                                f"{summary['imported_count']} requirement(s), "
                                f"created {summary['created_mappings']} mapping(s), "
                                f"created {summary['created_unified_controls']} unified control(s), "
                                f"captured {summary['captured_suggestions']} suggestion(s), "
                                f"created {summary['created_reference_documents']} reference document(s), "
                                f"and created {summary['created_reference_links']} reference link(s)."
                            )
                        except ValueError as exc:
                            st.error(str(exc))
                finally:
                    Path(file_path).unlink(missing_ok=True)

        with tab_traceability:
            framework_filter = st.selectbox("Framework filter", [""] + framework_codes, key="traceability_framework")
            batches = import_service.list_import_batches(framework_filter or None)
            if batches:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Import": item.import_code,
                                "Framework": item.framework.code if item.framework else "",
                                "Rows": item.row_count,
                                "Imported": item.imported_count,
                                "Mappings": item.created_mappings,
                                "Baseline Controls": item.created_unified_controls,
                                "Suggestions": item.captured_suggestions,
                                "Reference Docs": item.created_reference_documents,
                                "Reference Links": item.created_reference_links,
                                "Status": item.status,
                            }
                            for item in batches[:20]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No import batches have been recorded yet.")

            rows = import_service.traceability_rows(framework_filter or None, limit=200)
            if rows:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Framework": item["framework"],
                                "Requirement": item["control_id"],
                                "Title": item["title"],
                                "Domain": item["domain"],
                                "Section": item["section"],
                                "Source Ref": item["source_reference"],
                                "Unified Controls": ", ".join(item["mapped_unified_controls"]),
                                "References": ", ".join(item["reference_documents"]),
                                "Import Action": item["import_action"],
                            }
                            for item in rows
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("Traceability rows will appear here after the first framework import.")

        with tab_scripts:
            module_tab, binding_tab, catalog_tab = st.tabs(["Register Module", "Bind Module", "Catalog"])
            with module_tab:
                manifest = st.file_uploader("Optional manifest file", type=["yaml", "yml", "json"], key="script_manifest")
                if manifest is not None:
                    manifest_path = _save_upload(manifest)
                    try:
                        if st.button("Register from manifest", key="script_manifest_register"):
                            module = script_service.register_module_from_manifest(manifest_path)
                            st.success(f"Script module registered: {module.module_code}")
                    except ValueError as exc:
                        st.error(str(exc))
                    finally:
                        Path(manifest_path).unlink(missing_ok=True)

                with st.form("script_module_form"):
                    module_code = st.text_input("Module code")
                    name = st.text_input("Module name")
                    entrypoint_ref = st.text_input("Entrypoint path", help="Python file, module, or executable path.")
                    entrypoint_type = st.selectbox("Entrypoint type", ["python_file", "module", "command"])
                    interpreter = st.text_input("Interpreter", value="python3")
                    working_directory = st.text_input("Working directory", value="scripts")
                    context_argument_name = st.text_input("Context argument", value="--context-file")
                    default_arguments_json = st.text_area(
                        "Default arguments JSON",
                        value="[]",
                        height=90,
                        help='Example: ["--config", "{config_path}"]',
                    )
                    default_config_path = st.text_input("Default config path")
                    notes = st.text_area("Notes", height=90)
                    if st.form_submit_button("Save script module", type="primary") and module_code and name and entrypoint_ref:
                        try:
                            module = script_service.register_module(
                                module_code=module_code,
                                name=name,
                                entrypoint_ref=entrypoint_ref,
                                entrypoint_type=entrypoint_type,
                                interpreter=interpreter,
                                working_directory=working_directory,
                                context_argument_name=context_argument_name,
                                default_arguments_json=default_arguments_json,
                                default_config_path=default_config_path,
                                notes=notes,
                            )
                            st.success(f"Script module ready: {module.module_code}")
                        except ValueError as exc:
                            st.error(str(exc))

            with binding_tab:
                modules = script_service.list_modules()
                module_codes = [item.module_code for item in modules]
                if not module_codes:
                    st.info("Register a script module first.")
                else:
                    with st.form("script_binding_form"):
                        module_code = st.selectbox("Module", module_codes)
                        name = st.text_input("Binding name")
                        binding_code = st.text_input("Binding code")
                        org_code = st.selectbox("Organization", [""] + org_codes)
                        binding_codes = _binding_codes(session, org_code) if org_code else []
                        framework_binding_code = st.selectbox("Framework binding", [""] + binding_codes)
                        product_codes = _product_codes(session, org_code) if org_code else []
                        product_code = st.selectbox("Product", [""] + product_codes)
                        flavor_codes = _flavor_codes(session, org_code, product_code) if org_code and product_code else []
                        product_flavor_code = st.selectbox("Product flavor", [""] + flavor_codes)
                        unified_control_code = st.selectbox("Unified control", [""] + unified_codes)
                        framework_code = st.selectbox("Framework", [""] + framework_codes)
                        control_choice = ""
                        if framework_code:
                            framework = session.scalar(select(Framework).where(Framework.code == framework_code))
                            control_options = [
                                item.control_id
                                for item in session.scalars(
                                    select(Control).where(Control.framework_id == framework.id).order_by(Control.control_id)
                                ).all()
                            ]
                            control_choice = st.selectbox("Framework control", [""] + control_options)
                        plan_codes = [
                            item.plan_code
                            for item in session.scalars(
                                select(EvidenceCollectionPlan).order_by(EvidenceCollectionPlan.plan_code)
                            ).all()
                        ]
                        evidence_plan_code = st.selectbox("Evidence plan", [""] + plan_codes)
                        config_path = st.text_input("Config path")
                        config_json = st.text_area("Config JSON", value="{}", height=90)
                        arguments_json = st.text_area(
                            "Arguments JSON",
                            value="[]",
                            height=90,
                            help='Example: ["--config", "{config_path}", "--product", "{product_code}"]',
                        )
                        expected_outputs_json = st.text_area("Expected outputs JSON", value="[]", height=80)
                        if st.form_submit_button("Save script binding", type="primary") and name:
                            try:
                                binding = script_service.upsert_binding(
                                    module_code=module_code,
                                    name=name,
                                    binding_code=binding_code or None,
                                    organization_code=org_code or None,
                                    framework_binding_code=framework_binding_code or None,
                                    product_code=product_code or None,
                                    product_flavor_code=product_flavor_code or None,
                                    unified_control_code=unified_control_code or None,
                                    framework_code=framework_code or None,
                                    control_id=control_choice or None,
                                    evidence_plan_code=evidence_plan_code or None,
                                    config_path=config_path,
                                    config_json=config_json,
                                    arguments_json=arguments_json,
                                    expected_outputs_json=expected_outputs_json,
                                )
                                st.success(f"Script binding ready: {binding.binding_code}")
                            except ValueError as exc:
                                st.error(str(exc))

            with catalog_tab:
                modules = script_service.list_modules()
                if modules:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Module": item.module_code,
                                    "Name": item.name,
                                    "Entrypoint": item.entrypoint_ref,
                                    "Type": item.entrypoint_type,
                                    "Working Dir": item.working_directory,
                                }
                                for item in modules
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                bindings = script_service.list_bindings()
                if bindings:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Binding": item.binding_code,
                                    "Module": item.module.module_code if item.module else "",
                                    "Plan": item.evidence_plan.plan_code if item.evidence_plan else "",
                                    "Framework Binding": item.framework_binding.binding_code if item.framework_binding else "",
                                    "Product": item.product.code if item.product else "",
                                    "Flavor": item.product_flavor.code if item.product_flavor else "",
                                    "Control": item.control.control_id if item.control else "",
                                }
                                for item in bindings
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )


def render_review_queue() -> None:
    _hero("Review Queue", "Drive pending governance, validation, and assurance work toward a level-4 operating posture.")
    st.markdown(
        '<div class="section-note">This queue consolidates the main pending items across mappings, evidence plans, evidence actions, questionnaires, assessments, AI suggestions, AWS profile validation, and Confluence health. Clearing this queue is one of the fastest ways to improve enterprise maturity.</div>',
        unsafe_allow_html=True,
    )
    with session_scope() as session:
        queue_service = ReviewQueueService(session)
        summary = queue_service.summary()
        metric_cols = st.columns(4)
        with metric_cols[0]:
            _metric("Pending", str(summary["total"]))
        with metric_cols[1]:
            _metric("Critical", str(summary["priorities"].get("critical", 0)))
        with metric_cols[2]:
            _metric("High", str(summary["priorities"].get("high", 0)))
        with metric_cols[3]:
            _metric("Categories", str(len(summary["categories"])))

        if summary["top_items"]:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Category": item["category"],
                            "Priority": item["priority"],
                            "Status": item["status"],
                            "Reference": item["reference"],
                            "Title": item["title"],
                            "Detail": item["detail"],
                        }
                        for item in summary["top_items"]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.success("The review queue is empty. This workspace is in a strong operating state for the currently configured scope.")

        tab_mapping, tab_plan, tab_questionnaire, tab_assessment, tab_ai, tab_runtime = st.tabs(
            ["Mappings", "Evidence Plans", "Questionnaires", "Assessments", "AI Suggestions", "Runtime Health"]
        )

        with tab_mapping:
            pending_mappings = session.scalars(
                select(UnifiedControlMapping)
                .where(UnifiedControlMapping.approval_status != "approved")
                .order_by(UnifiedControlMapping.created_at.desc())
            ).all()
            if pending_mappings:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "ID": item.id,
                                "Framework": item.framework.code,
                                "Control": item.control.control_id,
                                "Unified": item.unified_control.code,
                                "Status": item.approval_status,
                                "Confidence": item.confidence,
                                "Reviewed By": item.reviewed_by,
                            }
                            for item in pending_mappings
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                with st.form("review_mapping_form"):
                    selected = st.selectbox(
                        "Mapping to review",
                        [item.id for item in pending_mappings],
                        format_func=lambda mapping_id: next(
                            (
                                f"{item.id} | {item.framework.code} {item.control.control_id} -> {item.unified_control.code}"
                                for item in pending_mappings
                                if item.id == mapping_id
                            ),
                            str(mapping_id),
                        ),
                    )
                    approval_status = st.selectbox("Decision", ["approved", "proposed", "rejected"])
                    reviewed_by = st.text_input("Reviewer")
                    notes = st.text_area("Review notes", height=80)
                    if st.form_submit_button("Update mapping", type="primary"):
                        try:
                            WorkbenchService(session).review_mapping(selected, approval_status, reviewed_by, notes)
                            st.success("Mapping review updated.")
                        except ValueError as exc:
                            st.error(str(exc))
            else:
                st.info("No mapping reviews are pending.")

        with tab_plan:
            pending_plans = session.scalars(
                select(EvidenceCollectionPlan)
                .where(EvidenceCollectionPlan.lifecycle_status.not_in(["approved", "active", "ready", "published"]))
                .order_by(EvidenceCollectionPlan.updated_at.desc())
            ).all()
            if pending_plans:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Plan": item.plan_code,
                                "Name": item.name,
                                "Status": item.lifecycle_status,
                                "Scope": item.scope_type,
                                "Mode": item.execution_mode,
                                "Freshness": item.minimum_freshness_days,
                            }
                            for item in pending_plans
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                with st.form("review_plan_form"):
                    plan_code = st.selectbox("Evidence plan", [item.plan_code for item in pending_plans])
                    lifecycle_status = st.selectbox("Lifecycle", ["approved", "active", "ready", "draft", "retired"])
                    actor = st.text_input("Reviewer ", value="workspace_reviewer")
                    rationale = st.text_area("Rationale", height=80)
                    if st.form_submit_button("Update plan", type="primary"):
                        try:
                            WorkbenchService(session).review_evidence_collection_plan(plan_code, lifecycle_status, actor, rationale)
                            st.success("Evidence plan updated.")
                        except ValueError as exc:
                            st.error(str(exc))
            else:
                st.info("No evidence plan reviews are pending.")

        with tab_questionnaire:
            pending_items = session.scalars(
                select(CustomerQuestionnaireItem)
                .where(CustomerQuestionnaireItem.review_status != "approved")
                .order_by(CustomerQuestionnaireItem.updated_at.desc())
            ).all()
            if pending_items:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "ID": item.id,
                                "Questionnaire": item.questionnaire.name,
                                "Question": item.question_text[:120],
                                "Status": item.review_status,
                                "Confidence": item.confidence,
                            }
                            for item in pending_items
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                with st.form("review_questionnaire_form"):
                    item_id = st.selectbox("Questionnaire item", [item.id for item in pending_items])
                    review_status = st.selectbox("Review status", ["approved", "needs_revision", "rejected", "suggested"])
                    reviewer = st.text_input("Reviewer  ", value="workspace_reviewer")
                    approved_answer = st.text_area("Approved answer override", height=120)
                    note = st.text_area("Review note ", height=80)
                    if st.form_submit_button("Update questionnaire item", type="primary"):
                        try:
                            QuestionnaireService(session).review_questionnaire_item(
                                item_id=item_id,
                                review_status=review_status,
                                reviewer=reviewer,
                                approved_answer=approved_answer,
                                rationale_note=note,
                            )
                            st.success("Questionnaire item updated.")
                        except ValueError as exc:
                            st.error(str(exc))
            else:
                st.info("No questionnaire reviews are pending.")

        with tab_assessment:
            pending_runs = session.scalars(
                select(AssessmentRun)
                .where(AssessmentRun.review_status != "approved")
                .order_by(AssessmentRun.started_at.desc())
            ).all()
            failed_schedules = session.scalars(
                select(AssessmentSchedule)
                .where(AssessmentSchedule.last_run_status == "error")
                .order_by(AssessmentSchedule.last_run_at.desc())
            ).all()
            if pending_runs:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Run ID": item.id,
                                "Framework": item.framework.code,
                                "Started": item.started_at,
                                "Score": item.score,
                                "Review": item.review_status,
                                "Assurance": item.assurance_status,
                            }
                            for item in pending_runs
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                with st.form("review_assessment_form"):
                    run_id = st.selectbox("Assessment run", [item.id for item in pending_runs])
                    review_status = st.selectbox("Assessment decision", ["approved", "pending_review", "rejected"])
                    assurance_status = st.selectbox("Assurance status", ["assessed", "accepted", "needs_evidence", "rejected"])
                    actor = st.text_input("Reviewer   ", value="workspace_reviewer")
                    rationale = st.text_area("Assessment rationale", height=80)
                    if st.form_submit_button("Update assessment review", type="primary"):
                        try:
                            AssessmentService(session).review_run(run_id, review_status, assurance_status, actor, rationale)
                            st.success("Assessment review updated.")
                        except ValueError as exc:
                            st.error(str(exc))
            else:
                st.info("No assessment reviews are pending.")
            if failed_schedules:
                st.markdown("#### Failed schedules")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "ID": item.id,
                                "Schedule": item.name,
                                "Binding": item.framework_binding.binding_code if item.framework_binding else "",
                                "Last Run": item.last_run_at,
                                "Message": item.last_run_message,
                            }
                            for item in failed_schedules
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )

        with tab_ai:
            suggestion_service = SuggestionService(session)
            pending_suggestions = suggestion_service.list_pending_mapping_suggestions()
            if pending_suggestions:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "ID": item.id,
                                "Framework": item.framework.code if item.framework else "",
                                "Control": item.control.control_id if item.control else "",
                                "Type": item.suggestion_type,
                                "Provider": item.provider,
                                "Top Match": suggestion_service.top_match_for_suggestion(item).get("unified_control_code", ""),
                                "Score": suggestion_service.top_match_for_suggestion(item).get("score", ""),
                            }
                            for item in pending_suggestions
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                with st.form("review_ai_suggestion_form"):
                    suggestion_id = st.selectbox(
                        "Suggestion",
                        [item.id for item in pending_suggestions],
                        format_func=lambda item_id: next(
                            (
                                f"{item.id} | {item.framework.code if item.framework else ''} "
                                f"{item.control.control_id if item.control else '(unlinked)'}"
                                for item in pending_suggestions
                                if item.id == item_id
                            ),
                            str(item_id),
                        ),
                    )
                    action = st.selectbox("Action", ["promote_to_mapping", "mark_reviewed"])
                    reviewer = st.text_input("Reviewer    ", value="workspace_reviewer")
                    notes = st.text_area("Review note", height=80)
                    if st.form_submit_button("Resolve suggestion", type="primary"):
                        try:
                            if action == "promote_to_mapping":
                                suggestion_service.promote_mapping_suggestion(suggestion_id, reviewer=reviewer, notes=notes)
                                st.success("Suggestion promoted into an approved mapping.")
                            else:
                                suggestion_service.dismiss_suggestion(suggestion_id, reviewer=reviewer, notes=notes)
                                st.success("Suggestion marked as reviewed.")
                        except ValueError as exc:
                            st.error(str(exc))
            else:
                st.info("No AI-assisted mapping suggestions are pending review.")

        with tab_runtime:
            profile_service = AwsProfileService(session)
            connection_service = ConfluenceConnectionService(session)
            profiles = [
                item
                for item in profile_service.list_profiles()
                if item.status == "active" and item.last_validation_status != "pass"
            ]
            connections = [
                item
                for item in connection_service.list_connections()
                if item.status == "active" and item.last_test_status != "pass"
            ]
            if profiles:
                st.markdown("#### AWS profiles needing validation")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Profile": item.profile_name,
                                "Status": item.last_validation_status or "unknown",
                                "Message": item.last_validation_message,
                            }
                            for item in profiles
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                selected_profile = st.selectbox("Profile to validate", [item.profile_name for item in profiles])
                if st.button("Validate profile now", key="review_validate_profile"):
                    result = profile_service.validate_profile(selected_profile)
                    if result["status"] == "pass":
                        st.success(result["message"])
                    else:
                        st.error(result["message"])
            else:
                st.success("All active AWS profiles have a passing validation state.")

            if connections:
                st.markdown("#### Confluence connections needing health checks")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Connection": item.name,
                                "Status": item.last_test_status or "untested",
                                "Message": item.last_test_message,
                            }
                            for item in connections
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                selected_connection = st.selectbox("Connection to test", [item.name for item in connections])
                if st.button("Test connection now", key="review_test_confluence"):
                    result = connection_service.test_connection(selected_connection)
                    if result["status"] == "pass":
                        st.success(result["message"])
                    else:
                        st.error(result["message"])
            else:
                st.success("All active Confluence connections have a passing health state.")


def render_operations() -> None:
    _hero("Operations", "Collect evidence and run assessments at binding, product, and flavor scope.")
    st.markdown('<div class="section-note">This is the operating surface for product-aware GRC execution. Use bindings as the AWS/Confluence anchor, then optionally scope the run to a product and flavor.</div>', unsafe_allow_html=True)
    with session_scope() as session:
        governance = GovernanceService(session)
        workbench = WorkbenchService(session)
        evidence_service = EvidenceService(session)
        assessment_service = AssessmentService(session)
        bindings = session.scalars(select(OrganizationFrameworkBinding).order_by(OrganizationFrameworkBinding.binding_code)).all()
        if not bindings:
            st.info("Create at least one framework binding before running evidence collection or assessments.")
            return

        binding_code = st.selectbox("Framework binding", [item.binding_code for item in bindings])
        binding = session.scalar(select(OrganizationFrameworkBinding).where(OrganizationFrameworkBinding.binding_code == binding_code))
        org_code = binding.organization.code
        product_codes = _product_codes(session, org_code)
        product_choice = st.selectbox("Product scope", [""] + product_codes)
        flavor_codes = _flavor_codes(session, org_code, product_choice) if product_choice else []
        flavor_choice = st.selectbox("Flavor scope", [""] + flavor_codes)
        collection_plan = EvidenceService(session).build_collection_plan_for_binding(
            binding_code=binding_code,
            product_code=product_choice or None,
            product_flavor_code=flavor_choice or None,
        )
        readiness = OperationalReadinessService(session).assess_binding(
            binding_code=binding_code,
            product_code=product_choice or None,
            product_flavor_code=flavor_choice or None,
        )
        st.subheader("Operational readiness")
        metric_cols = st.columns(5)
        with metric_cols[0]:
            _metric("Readiness", f"{readiness['overall_score']}/4.0")
        with metric_cols[1]:
            _metric("Status", readiness["readiness_status"].replace("_", " ").title())
        with metric_cols[2]:
            _metric("Fresh Evidence", str(readiness["counts"]["fresh_controls"]))
        with metric_cols[3]:
            _metric("Pending Review", str(readiness["counts"]["review_pending_controls"]))
        with metric_cols[4]:
            _metric("Plans", str(readiness["counts"]["controls_with_plans"]))
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Area": item["area"],
                        "Score": item["score"],
                        "Target": item["target"],
                        "Summary": item["summary"],
                    }
                    for item in readiness["areas"]
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        if readiness["blockers"]:
            st.error("Readiness blockers detected. Review these before relying on the run for governed assurance:")
            for item in readiness["blockers"][:10]:
                st.write(f"- {item}")
        if readiness["warnings"]:
            st.warning("Operational warnings")
            for item in readiness["warnings"][:10]:
                st.write(f"- {item}")
        if governance.offline_mode_enabled():
            st.warning("Offline-first mode is enabled. Assessments will reuse existing local evidence and new collection requests will be deferred.")
        else:
            st.info("AWS evidence collection uses the local AWS CLI SSO profile model. Run `aws sso login --profile <profile>` for the target profiles before collecting.")
            if collection_plan["profiles"]:
                st.caption("Required SSO login profiles for this run")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Profile": item["aws_profile"],
                                "Accounts": ", ".join(item["aws_account_ids"]),
                                "Regions": ", ".join(item["regions"]),
                                "Controls": len(item["controls"]),
                                "Registered": item["registered_in_app"],
                                "Validated": item["last_validation_status"] or "unknown",
                                "Detected Account": item["detected_account_id"],
                                "Alignment": item["account_alignment"],
                                "Login": item["login_command"],
                            }
                            for item in collection_plan["profiles"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                if collection_plan["missing_profile_metadata"]:
                    st.warning(
                        "Some required profiles are not registered in the app metadata: "
                        + ", ".join(collection_plan["missing_profile_metadata"])
                    )
                login_confirmed = st.checkbox(
                    "I have completed aws sso login for the profiles above",
                    value=False,
                    key=f"ops_login_confirmed_{binding_code}_{product_choice}_{flavor_choice}",
                )
            else:
                login_confirmed = True
        if governance.offline_mode_enabled():
            login_confirmed = True

        st.markdown("#### Control execution map")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Control": item["control_id"],
                        "Applicability": item["applicability_status"],
                        "Plan": item["plan_code"] or "(missing)",
                        "Plan Status": item["plan_status"],
                        "Mode": item["execution_mode"],
                        "Evidence Type": item["evidence_type"] or "",
                        "Freshness (Days)": item["minimum_freshness_days"],
                        "Targets": len(item["targets"]),
                    }
                    for item in collection_plan["controls"]
                ]
            ),
            width="stretch",
            hide_index=True,
        )

        targets = workbench.list_aws_evidence_targets(
            organization_code=org_code,
            binding_code=binding_code,
            product_code=product_choice or None,
        )
        if targets:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Target": item.target_code,
                            "Profile": item.aws_profile,
                            "Account": item.aws_account_id,
                            "Regions": ", ".join(json.loads(item.regions_json or "[]")),
                            "Flavor": item.product_flavor.code if item.product_flavor else "",
                            "Control": item.control.control_id if item.control else "",
                            "Unified": item.unified_control.code if item.unified_control else "",
                        }
                        for item in targets[:12]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

        left, right = st.columns(2)
        with left:
            if st.button("Collect evidence now", type="primary", disabled=not login_confirmed):
                try:
                    results = evidence_service.collect_for_binding(
                        binding_code=binding_code,
                        product_code=product_choice or None,
                        product_flavor_code=flavor_choice or None,
                    )
                    st.success(f"Collected {len(results)} evidence item(s).")
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Control": item.control.control_id,
                                    "Status": item.status,
                                    "Summary": item.summary,
                                    "Confluence": item.confluence_page_id or "",
                                }
                                for item in results
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                except ValueError as exc:
                    st.error(str(exc))
        with right:
            if st.button("Run assessment now", disabled=not login_confirmed):
                try:
                    run = assessment_service.run_binding_assessment(
                        binding_code=binding_code,
                        product_code=product_choice or None,
                        product_flavor_code=flavor_choice or None,
                    )
                    st.success(f"Assessment completed with score {run.score}% and assurance state {run.assurance_status}.")
                except ValueError as exc:
                    st.error(str(exc))

        product_id = None
        product_flavor_id = None
        if product_choice:
            product_id = session.scalar(
                select(Product.id).where(Product.organization.has(code=org_code), Product.code == product_choice)
            )
        if flavor_choice:
            product_flavor_id = session.scalar(
                select(ProductFlavor.id).where(
                    ProductFlavor.product.has(Product.organization.has(code=org_code)),
                    ProductFlavor.product.has(Product.code == product_choice),
                    ProductFlavor.code == flavor_choice,
                )
            )

        recent_evidence = EvidenceService.latest_for_framework(
            binding.framework_id,
            session,
            organization_id=binding.organization_id,
            product_id=product_id,
            product_flavor_id=product_flavor_id,
        )
        if recent_evidence:
            st.subheader("Latest evidence")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Control": item.control.control_id,
                            "Status": item.status,
                            "Lifecycle": item.lifecycle_status,
                            "Summary": item.summary,
                            "Collected": item.collected_at,
                            "Product": item.product.code if item.product else "",
                            "Flavor": item.product_flavor.code if item.product_flavor else "",
                        }
                        for item in recent_evidence
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            latest_payload = evidence_service.decrypt_payload(recent_evidence[0])
            target_rows = latest_payload.get("targets", [])
            if target_rows:
                st.caption("Target details from the most recent evidence item")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Target": item.get("target_code", ""),
                                "Profile": item.get("aws_profile", ""),
                                "Account": item.get("aws_account_id", ""),
                                "Region": item.get("region", ", ".join(item.get("regions", []))),
                                "Status": item.get("status", ""),
                                "Summary": item.get("summary", ""),
                            }
                            for item in target_rows
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            st.markdown("#### Evidence explorer")
            selected_evidence_id = st.selectbox(
                "Inspect evidence item",
                [item.id for item in recent_evidence],
                format_func=lambda evidence_id: next(
                    (
                        f"{item.id} | {item.control.control_id} | {item.status} | {item.lifecycle_status}"
                        for item in recent_evidence
                        if item.id == evidence_id
                    ),
                    str(evidence_id),
                ),
                key=f"ops_evidence_inspect_{binding_code}_{product_choice}_{flavor_choice}",
            )
            selected_evidence = next(item for item in recent_evidence if item.id == selected_evidence_id)
            st.code(json.dumps(evidence_service.decrypt_payload(selected_evidence), indent=2, default=str), language="json")
            manual_artifact = evidence_service.manual_artifact(selected_evidence)
            if manual_artifact:
                st.download_button(
                    "Download evidence artifact",
                    data=manual_artifact["content_bytes"],
                    file_name=manual_artifact["file_name"],
                    mime=manual_artifact["content_type"],
                )

        st.subheader("Manual evidence")
        control_options = [item.control_id for item in binding.framework.controls]
        with st.form(f"ops_manual_evidence_form_{binding_code}_{product_choice}_{flavor_choice}"):
            selected_control = st.selectbox("Control for manual evidence", control_options)
            manual_summary = st.text_area("Evidence summary", height=90)
            manual_status = st.selectbox("Evidence result", ["pass", "fail", "observed"])
            manual_uploaded_by = st.text_input("Uploaded by")
            manual_note = st.text_area("Operator note", height=80)
            manual_classification = st.selectbox("Classification", ["confidential", "restricted", "internal"])
            manual_publish = st.checkbox("Publish to Confluence when possible", value=False)
            manual_upload = st.file_uploader(
                "Supporting artifact",
                type=None,
                key=f"ops_manual_file_{binding_code}_{product_choice}_{flavor_choice}",
            )
            if st.form_submit_button("Store manual evidence", type="primary") and selected_control and manual_summary:
                upload_path = None
                if manual_upload is not None:
                    suffix = Path(manual_upload.name).suffix or ".bin"
                    upload_path = _save_upload(manual_upload, suffix=suffix)
                try:
                    evidence = evidence_service.upload_manual_evidence(
                        binding_code=binding_code,
                        control_id=selected_control,
                        summary=manual_summary,
                        status=manual_status,
                        product_code=product_choice or None,
                        product_flavor_code=flavor_choice or None,
                        note=manual_note,
                        file_path=upload_path,
                        uploaded_by=manual_uploaded_by,
                        classification=manual_classification,
                        publish_to_confluence=manual_publish,
                    )
                    st.success(f"Manual evidence stored as item {evidence.id} and marked {evidence.lifecycle_status}.")
                except ValueError as exc:
                    st.error(str(exc))
                finally:
                    if upload_path:
                        Path(upload_path).unlink(missing_ok=True)

        evidence_action_items = [
            item
            for item in evidence_service.list_evidence_items(
                framework_id=binding.framework_id,
                organization_id=binding.organization_id,
                product_id=product_id,
                product_flavor_id=product_flavor_id,
                limit=50,
            )
            if item.lifecycle_status in {"awaiting_collection", "pending_review"}
        ]
        if evidence_action_items:
            st.markdown("#### Evidence action queue")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "ID": item.id,
                            "Control": item.control.control_id,
                            "Status": item.status,
                            "Lifecycle": item.lifecycle_status,
                            "Summary": item.summary,
                            "Collected": item.collected_at,
                        }
                        for item in evidence_action_items
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            awaiting_collection = [item for item in evidence_action_items if item.lifecycle_status == "awaiting_collection"]
            if awaiting_collection:
                st.info(
                    "Some controls still need manual or assisted evidence collection. "
                    "Use the manual evidence form above or complete the required collection steps before approving assessments."
                )
        pending_evidence_reviews = [item for item in evidence_action_items if item.lifecycle_status == "pending_review"]
        if pending_evidence_reviews:
            with st.form(f"ops_evidence_review_form_{binding_code}_{product_choice}_{flavor_choice}"):
                evidence_id = st.selectbox("Evidence item", [item.id for item in pending_evidence_reviews])
                evidence_decision = st.selectbox("Decision", ["approved", "rejected", "pending_review"])
                evidence_actor = st.text_input("Reviewer", value="workspace_reviewer")
                evidence_rationale = st.text_area("Review rationale", height=80)
                if st.form_submit_button("Update evidence review", type="primary"):
                    try:
                        evidence_service.review_evidence_item(evidence_id, evidence_decision, evidence_actor, evidence_rationale)
                        st.success("Evidence review updated.")
                    except ValueError as exc:
                        st.error(str(exc))

        run_query = select(AssessmentRun).where(
            AssessmentRun.framework_id == binding.framework_id,
            AssessmentRun.organization_id == binding.organization_id,
        )
        if product_id is None:
            run_query = run_query.where(AssessmentRun.product_id.is_(None))
        else:
            run_query = run_query.where(AssessmentRun.product_id == product_id)
        if product_id is not None and product_flavor_id is None:
            run_query = run_query.where(AssessmentRun.product_flavor_id.is_(None))
        elif product_flavor_id is not None:
            run_query = run_query.where(AssessmentRun.product_flavor_id == product_flavor_id)
        recent_runs = session.scalars(run_query.order_by(AssessmentRun.started_at.desc())).all()
        if recent_runs:
            st.subheader("Recent assessments")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Started": item.started_at,
                            "Framework": item.framework.code,
                            "Score": item.score,
                            "Status": item.status,
                            "Product": item.product.code if item.product else "",
                            "Flavor": item.product_flavor.code if item.product_flavor else "",
                            "Confluence": item.confluence_page_id or "",
                        }
                        for item in recent_runs
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

        st.subheader("Recurring schedules")
        with st.form(f"ops_schedule_form_{binding_code}_{product_choice}_{flavor_choice}"):
            schedule_name = st.text_input("Schedule name")
            cadence = st.selectbox("Cadence", ["monthly", "quarterly", "yearly"])
            execution_mode = st.selectbox("Execution mode", ["manual", "assisted", "autonomous"])
            notes = st.text_area("Schedule notes", height=80)
            if st.form_submit_button("Create scoped schedule", type="primary") and schedule_name:
                try:
                    AssessmentService(session).create_schedule(
                        framework_codes=[binding.framework.code],
                        name=schedule_name,
                        cadence=cadence,
                        binding_code=binding_code,
                        product_code=product_choice or None,
                        product_flavor_code=flavor_choice or None,
                        execution_mode=execution_mode,
                        notes=notes,
                    )
                    st.success("Recurring schedule created.")
                except ValueError as exc:
                    st.error(str(exc))

        scoped_schedules = session.scalars(
            select(AssessmentSchedule)
            .where(AssessmentSchedule.framework_binding_id == binding.id)
            .order_by(AssessmentSchedule.next_run_at)
        ).all()
        if scoped_schedules:
            action_left, action_right = st.columns(2)
            with action_left:
                if st.button("Run all due schedules", key=f"ops_run_due_{binding_code}_{product_choice}_{flavor_choice}"):
                    try:
                        due_schedules = [item for item in scoped_schedules if item.enabled and item.next_run_at <= _utc_now_naive()]
                        runs = []
                        for item in due_schedules:
                            runs.extend(assessment_service.run_schedule(item.id))
                        st.success(f"Executed {len(runs)} due schedule run(s) in the current scope.")
                    except ValueError as exc:
                        st.error(str(exc))
            with action_right:
                selected_schedule_id = st.selectbox(
                    "Execute one schedule",
                    [item.id for item in scoped_schedules],
                    format_func=lambda item_id: next(
                        (f"{item.id} | {item.name}" for item in scoped_schedules if item.id == item_id),
                        str(item_id),
                    ),
                    key=f"ops_schedule_run_one_{binding_code}_{product_choice}_{flavor_choice}",
                )
                if st.button("Run selected schedule", key=f"ops_run_one_{binding_code}_{product_choice}_{flavor_choice}"):
                    try:
                        runs = assessment_service.run_schedule(selected_schedule_id)
                        st.success(f"Executed {len(runs)} assessment run(s) from schedule {selected_schedule_id}.")
                    except ValueError as exc:
                        st.error(str(exc))
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "ID": item.id,
                            "Name": item.name,
                            "Cadence": item.cadence,
                            "Mode": item.execution_mode,
                            "Product": item.product.code if item.product else "",
                            "Flavor": item.product_flavor.code if item.product_flavor else "",
                            "Last Status": item.last_run_status,
                            "Last Message": item.last_run_message,
                            "Next Run": item.next_run_at,
                        }
                        for item in scoped_schedules
                    ]
                ),
                width="stretch",
                hide_index=True,
            )


def render_aws_profiles() -> None:
    _hero("AWS Profiles", "Store local AWS CLI SSO profile definitions and prepare the exact login/config commands needed later.")
    st.markdown(
        '<div class="section-note">This section stores local AWS CLI profile metadata for your host or Ubuntu WSL environment. The app does not store AWS session credentials. When evidence must be collected, it will ask you to complete `aws sso login` for the required profiles.</div>',
        unsafe_allow_html=True,
    )
    with session_scope() as session:
        service = AwsProfileService(session)
        left, right = st.columns([1.05, 0.95])
        with left:
            with st.form("aws_profile_form"):
                profile_name = st.text_input("Profile name")
                sso_start_url = st.text_input("SSO start URL")
                sso_region = st.text_input("SSO region", value="eu-west-1")
                sso_account_id = st.text_input("Default account ID")
                sso_role_name = st.text_input("Default role name")
                default_region = st.text_input("Default AWS region", value="eu-west-1")
                output_format = st.selectbox("Output format", ["json", "yaml", "text"])
                sso_session_name = st.text_input("SSO session name", help="Optional. Leave blank to auto-derive it.")
                notes = st.text_area("Notes", height=90)
                if st.form_submit_button("Save AWS CLI profile", type="primary") and profile_name and sso_start_url and sso_region:
                    profile = service.upsert_profile(
                        profile_name=profile_name,
                        sso_start_url=sso_start_url,
                        sso_region=sso_region,
                        sso_account_id=sso_account_id,
                        sso_role_name=sso_role_name,
                        default_region=default_region,
                        output_format=output_format,
                        sso_session_name=sso_session_name or None,
                        notes=notes,
                    )
                    st.success(f"AWS CLI profile metadata saved: {profile.profile_name}")

        with right:
            profiles = service.list_profiles()
            if profiles:
                selected_name = st.selectbox("Inspect profile", [item.profile_name for item in profiles])
                st.code(service.render_config_block(selected_name), language="ini")
                st.code(service.login_command(selected_name), language="bash")
                if st.button("Validate selected profile via STS", key=f"validate_profile_{selected_name}"):
                    result = service.validate_profile(selected_name)
                    if result["status"] == "pass":
                        st.success(result["message"])
                    else:
                        st.error(result["message"])
                selected_profile = service.get_profile(selected_name)
                st.caption(
                    "Validation state: "
                    f"{selected_profile.last_validation_status or 'unknown'}"
                    + (f" | detected account {selected_profile.detected_account_id}" if selected_profile.detected_account_id else "")
                )
                st.caption("The configuration block above is intended for `~/.aws/config` in Ubuntu WSL or the host environment.")
                st.markdown("#### Combined config export")
                full_config = service.render_all_config_blocks()
                st.code(full_config, language="ini")
                st.download_button(
                    "Download aws config",
                    data=full_config,
                    file_name="aws-config.generated.ini",
                    mime="text/plain",
                )
            else:
                st.info("No AWS CLI profiles have been registered yet.")

        profiles = service.list_profiles()
        if profiles:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Profile": item.profile_name,
                            "Start URL": item.sso_start_url,
                            "SSO Region": item.sso_region,
                            "Account": item.sso_account_id,
                            "Role": item.sso_role_name,
                            "Default Region": item.default_region,
                            "Status": item.status,
                            "Validation": item.last_validation_status or "unknown",
                            "Detected Account": item.detected_account_id,
                        }
                        for item in profiles
                    ]
                ),
                width="stretch",
                hide_index=True,
            )


def render_security_lifecycle() -> None:
    _hero("Security & Lifecycle", "Manage secure Confluence connections and inspect lifecycle events.")
    st.markdown('<div class="section-note">Secrets are intended to live in the OS keyring or a private secret-files directory. This page stores only connection metadata in the database and keeps the credential hidden during entry.</div>', unsafe_allow_html=True)
    with session_scope() as session:
        governance = GovernanceService(session)
        service = ConfluenceConnectionService(session)
        offline_mode = governance.offline_mode_enabled()
        offline_toggle = st.checkbox(
            "Offline-first runtime mode",
            value=offline_mode,
            help="Disable live AWS collection and keep the workspace focused on local metadata, reporting, and previously collected evidence.",
        )
        if offline_toggle != offline_mode:
            governance.set_offline_mode(offline_toggle)
            st.success("Runtime mode updated.")
        left, right = st.columns(2)
        with left:
            with st.form("confluence_connection_form"):
                name = st.text_input("Connection name")
                base_url = st.text_input("Base URL")
                space_key = st.text_input("Space key")
                auth_mode = st.selectbox("Auth mode", ["basic", "bearer"])
                username = st.text_input("Username", help="Required for basic auth")
                parent_page_id = st.text_input("Default parent page ID")
                verify_tls = st.checkbox("Verify TLS", value=True)
                is_default = st.checkbox("Default connection", value=False)
                secret = st.text_input("PAT / token", type="password")
                if st.form_submit_button("Save connection", type="primary") and name and base_url and space_key and secret:
                    service.upsert_connection(
                        name=name,
                        base_url=base_url,
                        space_key=space_key,
                        secret_value=secret,
                        auth_mode=auth_mode,
                        username=username,
                        parent_page_id=parent_page_id,
                        verify_tls=verify_tls,
                        is_default=is_default,
                    )
                    st.success("Secure Confluence connection saved.")
            connections = service.list_connections()
            if connections:
                selected_connection = st.selectbox("Inspect connection", [item.name for item in connections])
                if st.button("Test selected connection", key=f"test_connection_{selected_connection}"):
                    result = service.test_connection(selected_connection)
                    if result["status"] == "pass":
                        st.success(result["message"])
                    else:
                        st.error(result["message"])
                    connections = service.list_connections()
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Name": item.name,
                                "Base URL": item.base_url,
                                "Space": item.space_key,
                                "Auth": item.auth_mode,
                                "Default": item.is_default,
                                "Status": item.status,
                                "Health": item.last_test_status or "untested",
                                "Last Tested": item.last_tested_at,
                            }
                            for item in connections
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
        with right:
            events = session.scalars(select(LifecycleEvent).order_by(LifecycleEvent.created_at.desc()).limit(50)).all()
            if events:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "When": item.created_at,
                                "Entity": item.entity_type,
                                "ID": item.entity_id,
                                "Lifecycle": item.lifecycle_name,
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
                st.info("No lifecycle events recorded yet.")


def render_questionnaires() -> None:
    _hero("Questionnaires", "Load a customer questionnaire for a product or flavor and answer it from implementation records.")
    with session_scope() as session:
        org_codes = _org_codes(session)
        if not org_codes:
            st.info("Create an organization first.")
            return
        org_code = st.selectbox("Organization", org_codes)
        product_codes = _product_codes(session, org_code)
        if not product_codes:
            st.info("Create a product first.")
            return
        product_code = st.selectbox("Product", product_codes)
        flavor_codes = _flavor_codes(session, org_code, product_code)
        flavor_code = st.selectbox("Flavor", [""] + flavor_codes)
        uploaded = st.file_uploader("Upload questionnaire CSV", type=["csv"], key="questionnaire_file")
        if uploaded is not None:
            csv_path = _save_upload(uploaded)
            try:
                service = QuestionnaireService(session)
                preview = service.preview_questionnaire_answers(organization_code=org_code, product_code=product_code, csv_path=csv_path, product_flavor_code=flavor_code or None)
                if preview:
                    st.dataframe(pd.DataFrame(preview), width="stretch", hide_index=True)
                    questionnaire_name = st.text_input("Questionnaire name", value=uploaded.name.replace(".csv", ""))
                    customer_name = st.text_input("Customer name")
                    if st.button("Store questionnaire", type="primary"):
                        service.import_csv_questionnaire(organization_code=org_code, product_code=product_code, csv_path=csv_path, name=questionnaire_name, customer_name=customer_name, product_flavor_code=flavor_code or None)
                        st.success("Questionnaire stored.")
                else:
                    st.warning("No answers could be drafted from the current implementations.")
            finally:
                Path(csv_path).unlink(missing_ok=True)

        stored = session.scalars(select(CustomerQuestionnaire).order_by(CustomerQuestionnaire.updated_at.desc())).all()
        if stored:
            st.dataframe(pd.DataFrame([{"Name": item.name, "Customer": item.customer_name, "Product": item.product.code, "Flavor": item.product_flavor.code if item.product_flavor else "", "Items": len(item.items), "Status": item.status} for item in stored]), width="stretch", hide_index=True)


def render_maturity_studio() -> None:
    _hero("Maturity Studio", "Profile the autonomy of controls per product and flavor using a 5-dimension maturity model.")
    st.markdown('<div class="section-note">Dimensions: governance, implementation, observability, automation, assurance. The service suggests an autonomy recommendation from those signals.</div>', unsafe_allow_html=True)
    with session_scope() as session:
        service = WorkbenchService(session)
        maturity = MaturityService(session)
        org_codes = _org_codes(session)
        if not org_codes:
            st.info("Create an organization first.")
            return
        with st.form("maturity_form"):
            org_code = st.selectbox("Organization", org_codes, key="mat_org")
            product_codes = _product_codes(session, org_code)
            if not product_codes:
                st.info("Create a product first.")
                return
            product_code = st.selectbox("Product", product_codes)
            flavor_codes = _flavor_codes(session, org_code, product_code) if product_code else []
            flavor_code = st.selectbox("Flavor", [""] + flavor_codes)
            unified_codes = [item.code for item in service.list_unified_controls()]
            if not unified_codes:
                st.info("Create unified controls before recording maturity profiles.")
                return
            unified_code = st.selectbox("Unified control", unified_codes)
            unified_control_id = session.scalar(select(UnifiedControl.id).where(UnifiedControl.code == unified_code))
            suggested = maturity.suggest_for_implementation(
                organization_id=session.scalar(select(Organization.id).where(Organization.code == org_code)),
                product_id=session.scalar(select(Product.id).where(Product.organization.has(code=org_code), Product.code == product_code)) if product_code else None,
                product_flavor_id=session.scalar(select(ProductFlavor.id).where(ProductFlavor.product.has(Product.organization.has(code=org_code)), ProductFlavor.product.has(Product.code == product_code), ProductFlavor.code == flavor_code)) if flavor_code else None,
                unified_control_id=unified_control_id,
                control_id=None,
            )
            st.markdown(f"Suggested autonomy: **{suggested['autonomy_recommendation']}**")
            governance = st.slider("Governance", 1, 5, suggested["maturity_governance"])
            implementation_score = st.slider("Implementation", 1, 5, suggested["maturity_implementation"])
            observability = st.slider("Observability", 1, 5, suggested["maturity_observability"])
            automation = st.slider("Automation", 1, 5, suggested["maturity_automation"])
            assurance = st.slider("Assurance", 1, 5, suggested["maturity_assurance"])
            applicability = st.selectbox("Applicability", ["applicable", "inherited", "not_applicable", "planned"])
            mode = st.selectbox("Assessment mode", ["manual", "assisted", "autonomous"])
            rationale = st.text_area("Rationale", height=100)
            if st.form_submit_button("Save maturity profile", type="primary") and org_code and product_code:
                service.upsert_product_control_profile(
                    organization_code=org_code,
                    product_code=product_code,
                    product_flavor_code=flavor_code or None,
                    unified_control_code=unified_code or None,
                    applicability_status=applicability,
                    assessment_mode=mode,
                    maturity_governance=governance,
                    maturity_implementation=implementation_score,
                    maturity_observability=observability,
                    maturity_automation=automation,
                    maturity_assurance=assurance,
                    rationale=rationale,
                )
                st.success("Maturity profile saved.")

        profiles = session.scalars(select(ProductControlProfile).order_by(ProductControlProfile.updated_at.desc())).all()
        if profiles:
            st.dataframe(pd.DataFrame([{"Product": item.product.code, "Flavor": item.product_flavor.code if item.product_flavor else "", "Unified Control": item.unified_control.code if item.unified_control else "", "Maturity": item.maturity_level, "Mode": item.assessment_mode, "Autonomy": item.autonomy_recommendation} for item in profiles]), width="stretch", hide_index=True)


_apply_styles()

if _STARTUP_ERROR is not None:
    render_user_error(
        title="The workspace could not start cleanly",
        exc=_STARTUP_ERROR,
        fallback="The database or application startup still needs attention before the workspace can be used.",
        next_steps=[
            "Run the end-to-end test script to validate the workspace environment.",
            "If the database was updated recently, let the migration finish and then reload the page.",
        ],
        key_prefix="workspace_startup_error",
    )
    st.stop()

_render_workspace_auth_gate()

with st.sidebar:
    st.markdown("## Workspace")
    if st.session_state.get("workspace_principal_key"):
        st.caption(f"Signed in as `{st.session_state['workspace_principal_key']}`")
        if st.button("Sign out", key="workspace_sign_out"):
            _clear_workspace_auth_state()
            st.rerun()
    workspace_mode = "Unified Workspace"
    st.session_state["workspace_mode"] = workspace_mode
    st.caption("Single unified workspace with overview and specialist workflows in one operating shell.")
    default_page = st.session_state.get("workspace_page", _default_unified_section())
    default_index = UNIFIED_WORKSPACE_SECTIONS.index(default_page) if default_page in UNIFIED_WORKSPACE_SECTIONS else 0
    workspace_page = st.selectbox("Navigate", UNIFIED_WORKSPACE_SECTIONS, index=default_index)
    st.session_state["workspace_page"] = workspace_page

_log_workspace_navigation(workspace_mode, workspace_page)

def _render_workspace_page(page: str) -> None:
    if page == "Workspace Home":
        render_workspace_home()
    elif page == "Assistant Center":
        render_assistant_center()
    elif page == "Asset Catalog":
        render_asset_catalog()
    elif page == "Artifact Explorer":
        render_artifact_explorer()
    elif page == "Operations Center":
        render_operations_workspace()
    elif page == "Governance Center":
        render_governance_center()
    elif page == "Settings & Integrations":
        render_settings_integrations()
    elif page == "About":
        render_about_center()
    elif page == "Help Center":
        render_help_center()
    elif page == "Wizards":
        render_guided_setup()
    elif page == "Overview":
        render_overview()
    elif page == "Standards":
        render_standards()
    elif page == "Portfolio":
        render_portfolio_center()
    elif page == "AWS Profiles":
        render_aws_profiles()
    elif page in {"Control Framework Studio", "Unified Controls", "Import Studio", "Mapping Lab"}:
        render_control_framework_studio()
    elif page == "Review Queue":
        render_review_queue()
    elif page == "Operations":
        render_operations_workspace()
    elif page == "Security & Lifecycle":
        render_security_lifecycle()
    elif page == "Questionnaires":
        render_questionnaire_center()
    elif page == "Maturity Studio":
        render_maturity_studio()
    elif page == "Workspace Assessment":
        render_workspace_assessment()


try:
    _render_workspace_page(workspace_page)
except Exception as exc:
    APP_LOGGER.exception("Workspace page render failed.", extra={"workspace_page": workspace_page})
    render_user_error(
        title=f"The {workspace_page} page could not be rendered cleanly",
        exc=exc,
        fallback="The workspace caught an unexpected error and stopped that page safely.",
        next_steps=[
            "Go back to Workspace Home or Assistant Center and reopen the workflow.",
            "If the same step keeps failing, use the testing script to confirm the environment is healthy.",
        ],
        key_prefix="workspace_render_error",
    )

