from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from aws_local_audit.config import settings
from aws_local_audit.db import init_database, session_scope
from aws_local_audit.framework_loader import load_templates
from aws_local_audit.logging_utils import audit_event, configure_logging, get_logger
from aws_local_audit.models import AssessmentRun, AssessmentSchedule, Control, EvidenceItem, Framework, LifecycleEvent
from aws_local_audit.security import EvidenceVault, KeyringSecretStore
from aws_local_audit.services.assessments import AssessmentService
from aws_local_audit.services.access_control import AccessControlService
from aws_local_audit.services.aws_profiles import AwsProfileService
from aws_local_audit.services.backup_restore import BackupRestoreService
from aws_local_audit.services.enterprise_maturity import EnterpriseMaturityService
from aws_local_audit.services.evidence import EvidenceService
from aws_local_audit.services.framework_imports import FrameworkImportService
from aws_local_audit.services.frameworks import FrameworkService
from aws_local_audit.services.knowledge_packs import AIKnowledgePackService
from aws_local_audit.services.observability import ObservabilityService
from aws_local_audit.services.phase1_maturity import Phase1MaturityService
from aws_local_audit.services.platform_foundation import (
    ArchitectureBoundaryService,
    AuditTrailService,
    FeatureFlagService,
    HealthCheckService,
)
from aws_local_audit.services.privacy_lifecycle import PrivacyLifecycleService
from aws_local_audit.services.readiness import OperationalReadinessService
from aws_local_audit.services.questionnaires import QuestionnaireService
from aws_local_audit.services.reference_library import ReferenceLibraryService
from aws_local_audit.services.review_queue import ReviewQueueService
from aws_local_audit.services.security import ConfluenceConnectionService, SecretService
from aws_local_audit.services.script_modules import ScriptModuleService
from aws_local_audit.services.suggestions import SuggestionService
from aws_local_audit.services.validation import ValidationError
from aws_local_audit.services.workbench import WorkbenchService
from aws_local_audit.services.workspace_auth import WorkspaceAuthService, WorkspaceAuthenticationError

configure_logging()
LOGGER = get_logger("cli")
app = typer.Typer(help="Local AWS Audit Manager for AWS CLI SSO profiles.")
framework_app = typer.Typer(help="Manage compliance frameworks.")
evidence_app = typer.Typer(help="Collect evidence.")
assessment_app = typer.Typer(help="Run assessments.")
schedule_app = typer.Typer(help="Manage assessment schedules.")
aws_profile_app = typer.Typer(help="Manage local AWS CLI SSO profile metadata.")
maturity_app = typer.Typer(help="Inspect maturity and readiness scoring.")
org_app = typer.Typer(help="Manage organizations and framework bindings.")
ucf_app = typer.Typer(help="Manage unified controls and mappings.")
implementation_app = typer.Typer(help="Manage organization-specific control implementations.")
security_app = typer.Typer(help="Manage security bootstrap and secure secret metadata.")
confluence_app = typer.Typer(help="Manage secure Confluence connections.")
lifecycle_app = typer.Typer(help="Inspect lifecycle history.")
review_app = typer.Typer(help="Review pending governance and operator work.")
import_app = typer.Typer(help="Import external framework sources with traceability.")
copilot_app = typer.Typer(help="Manage governed AI knowledge packs and draft controlled copilot outputs.")
script_app = typer.Typer(help="Register and bind external assessment script modules.")
platform_app = typer.Typer(help="Inspect platform health, feature flags, architecture boundaries, and audit integrity.")
rbac_app = typer.Typer(help="Manage principals, roles, and scoped RBAC assignments.")
auth_app = typer.Typer(help="Manage local workspace authentication and credentials.")
privacy_app = typer.Typer(help="Manage privacy lifecycle operations for questionnaires and sensitive records.")
console = Console()

app.add_typer(framework_app, name="framework")
app.add_typer(evidence_app, name="evidence")
app.add_typer(assessment_app, name="assessment")
app.add_typer(schedule_app, name="schedule")
app.add_typer(aws_profile_app, name="aws-profile")
app.add_typer(maturity_app, name="maturity")
app.add_typer(org_app, name="org")
app.add_typer(ucf_app, name="ucf")
app.add_typer(implementation_app, name="implementation")
app.add_typer(security_app, name="security")
app.add_typer(confluence_app, name="confluence")
app.add_typer(lifecycle_app, name="lifecycle")
app.add_typer(review_app, name="review")
app.add_typer(import_app, name="importer")
app.add_typer(copilot_app, name="copilot")
app.add_typer(script_app, name="script")
app.add_typer(platform_app, name="platform")
app.add_typer(rbac_app, name="rbac")
app.add_typer(auth_app, name="auth")
app.add_typer(privacy_app, name="privacy")


@app.callback()
def main(ctx: typer.Context) -> None:
    command_name = ctx.invoked_subcommand or "root"
    LOGGER.info("CLI command invoked: %s", command_name)
    audit_event(
        action="cli_command_invoked",
        actor="cli",
        target_type="command",
        target_id=command_name,
        status="success",
    )


@app.command("init-db")
def init_db() -> None:
    init_database()
    console.print(f"Database initialized at {settings.database_url}")


@aws_profile_app.command("upsert")
def upsert_aws_profile(
    profile_name: str = typer.Argument(..., help="AWS CLI profile name"),
    sso_start_url: str = typer.Option(..., help="IAM Identity Center start URL"),
    sso_region: str = typer.Option(..., help="IAM Identity Center region"),
    sso_account_id: str = typer.Option("", help="Default AWS account ID"),
    sso_role_name: str = typer.Option("", help="Default role name"),
    default_region: str = typer.Option(settings.default_aws_region, help="Default AWS region"),
    output_format: str = typer.Option("json", help="AWS CLI output format"),
    sso_session_name: Optional[str] = typer.Option(None, help="SSO session name"),
    notes: str = typer.Option("", help="Notes"),
) -> None:
    with session_scope() as session:
        profile = AwsProfileService(session).upsert_profile(
            profile_name=profile_name,
            sso_start_url=sso_start_url,
            sso_region=sso_region,
            sso_account_id=sso_account_id,
            sso_role_name=sso_role_name,
            default_region=default_region,
            output_format=output_format,
            sso_session_name=sso_session_name,
            notes=notes,
        )
        console.print(f"AWS CLI profile metadata saved: {profile.profile_name}")


@aws_profile_app.command("list")
def list_aws_profiles() -> None:
    with session_scope() as session:
        profiles = AwsProfileService(session).list_profiles()
        table = Table(title="AWS CLI Profiles")
        table.add_column("Profile")
        table.add_column("SSO Region")
        table.add_column("Account")
        table.add_column("Role")
        table.add_column("Default Region")
        table.add_column("Validation")
        table.add_column("Detected Account")
        for item in profiles:
            table.add_row(
                item.profile_name,
                item.sso_region,
                item.sso_account_id,
                item.sso_role_name,
                item.default_region,
                item.last_validation_status or "unknown",
                item.detected_account_id,
            )
        console.print(table)


@aws_profile_app.command("show-config")
def show_aws_profile_config(profile_name: str = typer.Argument(..., help="AWS CLI profile name")) -> None:
    with session_scope() as session:
        service = AwsProfileService(session)
        console.print(service.render_config_block(profile_name))
        console.print(service.login_command(profile_name))


@aws_profile_app.command("export-config")
def export_aws_profile_config() -> None:
    with session_scope() as session:
        service = AwsProfileService(session)
        console.print(service.render_all_config_blocks())


@aws_profile_app.command("validate")
def validate_aws_profile(profile_name: str = typer.Argument(..., help="AWS CLI profile name")) -> None:
    with session_scope() as session:
        result = AwsProfileService(session).validate_profile(profile_name)
        console.print(f"[{result['status']}] {profile_name}: {result['message']}")
        if result.get("account_id"):
            console.print(f"Account: {result['account_id']}")
        if result.get("arn"):
            console.print(f"ARN: {result['arn']}")


@maturity_app.command("phase1-score")
def phase1_score() -> None:
    with session_scope() as session:
        assessment = Phase1MaturityService(session).assess()
        console.print(f"Phase 1 maturity score: {assessment['overall_score']}/4.0")
        table = Table(title="Phase 1 Maturity Areas")
        table.add_column("Area")
        table.add_column("Score")
        table.add_column("Target")
        table.add_column("Top Gap")
        for item in assessment["areas"]:
            table.add_row(
                item["area"],
                str(item["score"]),
                str(item["target"]),
                item["gaps"][0] if item["gaps"] else "",
            )
        console.print(table)


@maturity_app.command("enterprise-score")
def enterprise_score() -> None:
    with session_scope() as session:
        assessment = EnterpriseMaturityService(session).assess()
        console.print(f"Enterprise maturity score: {assessment['overall_score']}/4.0")
        phase_table = Table(title="Phase Maturity")
        phase_table.add_column("Area")
        phase_table.add_column("Score")
        phase_table.add_column("Target")
        phase_table.add_column("Top Gap")
        for item in assessment["phases"]:
            phase_table.add_row(
                item["area"],
                str(item["score"]),
                str(item["target"]),
                item["gaps"][0] if item["gaps"] else "",
            )
        console.print(phase_table)
        quality_table = Table(title="Quality Areas")
        quality_table.add_column("Area")
        quality_table.add_column("Score")
        quality_table.add_column("Target")
        quality_table.add_column("Top Gap")
        for item in assessment["qualities"]:
            quality_table.add_row(
                item["area"],
                str(item["score"]),
                str(item["target"]),
                item["gaps"][0] if item["gaps"] else "",
            )
        console.print(quality_table)


@platform_app.command("health")
def platform_health() -> None:
    with session_scope() as session:
        report = HealthCheckService(session).run()
        console.print(f"Platform health: {report['status']}")
        table = Table(title="Health Checks")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Detail")
        for item in report["checks"]:
            table.add_row(item["name"], item["status"], item["detail"])
        console.print(table)


@platform_app.command("feature-flags")
def list_feature_flags() -> None:
    with session_scope() as session:
        rows = FeatureFlagService(session).list_flags()
        table = Table(title="Feature Flags")
        table.add_column("Key")
        table.add_column("Enabled")
        table.add_column("Strategy")
        table.add_column("Owner")
        table.add_column("Description")
        for item in rows:
            table.add_row(item.flag_key, str(item.enabled), item.rollout_strategy, item.owner or "", item.description or "")
        console.print(table)


@platform_app.command("set-feature-flag")
def set_feature_flag(
    flag_key: str = typer.Argument(..., help="Feature flag key"),
    enabled: bool = typer.Option(..., "--enabled/--disabled", help="Enable or disable the flag"),
    name: str = typer.Option("", help="Friendly name"),
    description: str = typer.Option("", help="Description"),
    rollout_strategy: str = typer.Option("static", help="Rollout strategy"),
    owner: str = typer.Option("", help="Owner"),
    actor: str = typer.Option("platform_cli", help="Actor"),
) -> None:
    with session_scope() as session:
        flag = FeatureFlagService(session).set_flag(
            flag_key=flag_key,
            enabled=enabled,
            actor=actor,
            name=name or flag_key,
            description=description,
            rollout_strategy=rollout_strategy,
            owner=owner,
        )
        console.print(f"Feature flag {flag.flag_key} set to {flag.enabled}")


@platform_app.command("architecture")
def platform_architecture() -> None:
    rows = ArchitectureBoundaryService().describe()
    table = Table(title="Bounded Contexts")
    table.add_column("Key")
    table.add_column("Name")
    table.add_column("Purpose")
    table.add_column("Owned Entities")
    for item in rows:
        table.add_row(item["key"], item["name"], item["purpose"], ", ".join(item["owned_entities"]))
    console.print(table)


@platform_app.command("verify-audit-chain")
def verify_audit_chain() -> None:
    with session_scope() as session:
        report = AuditTrailService(session).verify_chain()
        console.print(f"Audit trail valid: {report['valid']}")
        console.print(f"Events checked: {report['events']}")
        if report["failures"]:
            console.print(json.dumps(report["failures"], indent=2))


@platform_app.command("observability")
def platform_observability() -> None:
    report = ObservabilityService().runtime_summary()
    console.print(f"Observability: {report['status']}")
    console.print(report["detail"])
    metric_table = Table(title="Metric Events")
    metric_table.add_column("Metric")
    metric_table.add_column("Events")
    metric_table.add_column("Value Sum")
    for item in report["metrics"]["metrics"]:
        metric_table.add_row(item["metric"], str(item["events"]), str(item["value_sum"]))
    console.print(metric_table)
    trace_table = Table(title="Trace Events")
    trace_table.add_column("Span")
    trace_table.add_column("Events")
    for item in report["traces"]["spans"]:
        trace_table.add_row(item["name"], str(item["events"]))
    console.print(trace_table)


@platform_app.command("backup-create")
def platform_backup_create(
    label: str = typer.Option("manual", help="Human-friendly backup label"),
    actor: str = typer.Option("platform_cli", help="Actor"),
) -> None:
    manifest = BackupRestoreService().create_backup(label=label, actor=actor)
    console.print(f"Backup created: {manifest['backup_name']}")
    console.print(f"Checksum: {manifest['sha256']}")


@platform_app.command("backup-list")
def platform_backup_list() -> None:
    rows = BackupRestoreService().list_backups()
    table = Table(title="Database Backups")
    table.add_column("Backup")
    table.add_column("Created")
    table.add_column("Size")
    table.add_column("Label")
    for item in rows:
        table.add_row(item["backup_name"], item["created_at"], str(item["size_bytes"]), item["label"])
    console.print(table)


@platform_app.command("backup-verify")
def platform_backup_verify(backup_name: str = typer.Argument(..., help="Backup file name")) -> None:
    report = BackupRestoreService().verify_backup(backup_name)
    console.print(f"[{report['status']}] {report['detail']}")


@platform_app.command("backup-restore")
def platform_backup_restore(
    backup_name: str = typer.Argument(..., help="Backup file name"),
    actor: str = typer.Option("platform_cli", help="Actor"),
) -> None:
    report = BackupRestoreService().restore_backup(backup_name, actor=actor)
    console.print(f"Restored backup: {report['restored']}")
    console.print(f"Pre-restore snapshot: {report['pre_restore_backup']}")


@platform_app.command("recovery-drill")
def platform_recovery_drill(
    actor: str = typer.Option("platform_cli", help="Actor"),
) -> None:
    report = BackupRestoreService().run_restore_drill(actor=actor)
    console.print(f"Recovery drill: {report['status']}")
    console.print(f"Verified backup: {report['backup_name']}")
    console.print(f"Table count: {report['table_count']}")


@rbac_app.command("seed-roles")
def seed_rbac_roles() -> None:
    with session_scope() as session:
        created = AccessControlService(session).seed_default_roles()
        console.print(f"Seeded or refreshed RBAC roles. Newly created: {created}")


@rbac_app.command("upsert-principal")
def upsert_principal(
    principal_key: str = typer.Argument(..., help="Stable principal key"),
    display_name: str = typer.Option(..., help="Display name"),
    principal_type: str = typer.Option("human", help="Principal type"),
    organization_id: Optional[int] = typer.Option(None, help="Optional organization scope"),
    email: str = typer.Option("", help="Email address"),
    external_id: str = typer.Option("", help="External identity ID"),
    source_system: str = typer.Option("local", help="Identity source"),
    status: str = typer.Option("active", help="Status"),
) -> None:
    with session_scope() as session:
        principal = AccessControlService(session).upsert_principal(
            principal_key=principal_key,
            display_name=display_name,
            principal_type=principal_type,
            organization_id=organization_id,
            email=email,
            external_id=external_id,
            source_system=source_system,
            status=status,
        )
        console.print(f"Principal saved: {principal.principal_key}")


@rbac_app.command("roles")
def list_rbac_roles() -> None:
    with session_scope() as session:
        rows = AccessControlService(session).list_roles()
        table = Table(title="Access Roles")
        table.add_column("Key")
        table.add_column("Name")
        table.add_column("Scope")
        table.add_column("Approval")
        table.add_column("Builtin")
        for item in rows:
            table.add_row(item.role_key, item.name, item.scope_type, str(item.approval_required), str(item.builtin))
        console.print(table)


@rbac_app.command("principals")
def list_rbac_principals() -> None:
    with session_scope() as session:
        rows = AccessControlService(session).list_principals()
        table = Table(title="Identity Principals")
        table.add_column("Key")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Organization")
        for item in rows:
            table.add_row(
                item.principal_key,
                item.display_name,
                item.principal_type,
                item.status,
                str(item.organization_id or ""),
            )
        console.print(table)


@auth_app.command("status")
def auth_status() -> None:
    with session_scope() as session:
        service = WorkspaceAuthService(session)
        report = service.health_summary()
        console.print(f"Workspace auth: {report['status']}")
        console.print(report["detail"])


@auth_app.command("bootstrap")
def auth_bootstrap(
    principal_key: str = typer.Argument(..., help="Principal key"),
    display_name: str = typer.Option(..., help="Display name"),
    email: str = typer.Option("", help="Email address"),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True, help="Local workspace password"),
) -> None:
    with session_scope() as session:
        try:
            service = WorkspaceAuthService(session)
            principal = service.bootstrap_local_admin(
                principal_key=principal_key,
                display_name=display_name,
                password=password,
                email=email,
            )
            console.print(f"Workspace authentication initialized for {principal.principal_key}")
        except (ValidationError, WorkspaceAuthenticationError) as exc:
            raise typer.BadParameter(str(exc)) from exc


@auth_app.command("set-password")
def auth_set_password(
    principal_key: str = typer.Argument(..., help="Principal key"),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True, help="Local workspace password"),
    actor: str = typer.Option("auth_cli", help="Actor"),
) -> None:
    with session_scope() as session:
        try:
            WorkspaceAuthService(session).set_password(principal_key, password=password, actor=actor)
            console.print(f"Workspace password updated for {principal_key}")
        except (ValidationError, WorkspaceAuthenticationError) as exc:
            raise typer.BadParameter(str(exc)) from exc


@privacy_app.command("report")
def privacy_report(
    questionnaire_retention_days: int = typer.Option(365, help="Questionnaire retention threshold in days"),
    evidence_freshness_days: int = typer.Option(180, help="Evidence freshness threshold in days"),
) -> None:
    with session_scope() as session:
        report = PrivacyLifecycleService(session).retention_report(
            questionnaire_retention_days=questionnaire_retention_days,
            evidence_freshness_days=evidence_freshness_days,
        )
        console.print("Privacy lifecycle report")
        console.print(json.dumps(report["counts"], indent=2))
        table = Table(title="Questionnaires Due For Review")
        table.add_column("ID")
        table.add_column("Questionnaire")
        table.add_column("Customer")
        table.add_column("Scope")
        table.add_column("Created")
        for item in report["questionnaires_due_for_review"]:
            table.add_row(
                str(item["questionnaire_id"]),
                item["name"],
                item["customer_name"],
                f"{item['organization_code']} / {item['product_code']}",
                item["created_at"],
            )
        console.print(table)


@privacy_app.command("export-questionnaire")
def privacy_export_questionnaire(
    questionnaire_id: int = typer.Argument(..., help="Questionnaire ID"),
    output_path: Optional[str] = typer.Option(None, help="Optional JSON output path"),
) -> None:
    with session_scope() as session:
        payload = PrivacyLifecycleService(session).export_questionnaire_bundle_json(questionnaire_id)
        if output_path:
            Path(output_path).write_text(payload, encoding="utf-8")
            console.print(f"Questionnaire export written to {output_path}")
        else:
            console.print(payload)


@privacy_app.command("redact-questionnaire")
def privacy_redact_questionnaire(
    questionnaire_id: int = typer.Argument(..., help="Questionnaire ID"),
    actor: str = typer.Option("privacy_cli", help="Actor"),
    rationale: str = typer.Option("", help="Rationale"),
) -> None:
    with session_scope() as session:
        questionnaire = PrivacyLifecycleService(session).redact_questionnaire_customer(
            questionnaire_id,
            actor=actor,
            rationale=rationale,
        )
        console.print(f"Questionnaire redacted: {questionnaire.id} ({questionnaire.name})")


@privacy_app.command("delete-questionnaire")
def privacy_delete_questionnaire(
    questionnaire_id: int = typer.Argument(..., help="Questionnaire ID"),
    actor: str = typer.Option("privacy_cli", help="Actor"),
    rationale: str = typer.Option("", help="Rationale"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirm questionnaire deletion"),
) -> None:
    if not confirm:
        raise typer.BadParameter("Use --confirm to delete a questionnaire bundle.")
    with session_scope() as session:
        report = PrivacyLifecycleService(session).delete_questionnaire(
            questionnaire_id,
            actor=actor,
            rationale=rationale,
        )
        console.print(
            f"Deleted questionnaire {report['deleted_questionnaire_id']} with {report['deleted_items']} related item(s)."
        )


@rbac_app.command("assign")
def assign_rbac_role(
    principal_key: str = typer.Argument(..., help="Principal key"),
    role_key: str = typer.Argument(..., help="Role key"),
    actor: str = typer.Option("rbac_cli", help="Actor"),
    organization_id: Optional[int] = typer.Option(None, help="Organization scope"),
    business_unit_id: Optional[int] = typer.Option(None, help="Business unit scope"),
    product_id: Optional[int] = typer.Option(None, help="Product scope"),
    framework_binding_id: Optional[int] = typer.Option(None, help="Framework binding scope"),
    approved_by: str = typer.Option("", help="Approver"),
    rationale: str = typer.Option("", help="Rationale"),
) -> None:
    with session_scope() as session:
        assignment = AccessControlService(session).assign_role(
            principal_key=principal_key,
            role_key=role_key,
            actor=actor,
            organization_id=organization_id,
            business_unit_id=business_unit_id,
            product_id=product_id,
            framework_binding_id=framework_binding_id,
            approved_by=approved_by,
            rationale=rationale,
        )
        console.print(
            f"Role assignment saved: {assignment.id} ({assignment.approval_status})"
        )


@rbac_app.command("approve")
def approve_rbac_assignment(
    assignment_id: int = typer.Argument(..., help="Role assignment ID"),
    approver: str = typer.Option(..., help="Approver"),
) -> None:
    with session_scope() as session:
        assignment = AccessControlService(session).approve_assignment(assignment_id, approver=approver)
        console.print(f"Approved assignment {assignment.id} for principal {assignment.principal.principal_key}")


@rbac_app.command("assignments")
def list_rbac_assignments() -> None:
    with session_scope() as session:
        rows = AccessControlService(session).list_assignments()
        table = Table(title="Role Assignments")
        table.add_column("ID")
        table.add_column("Principal")
        table.add_column("Role")
        table.add_column("Approval")
        table.add_column("Scope")
        for item in rows:
            scope = ",".join(
                value
                for value in [
                    f"org={item.organization_id}" if item.organization_id else "",
                    f"bu={item.business_unit_id}" if item.business_unit_id else "",
                    f"product={item.product_id}" if item.product_id else "",
                    f"binding={item.framework_binding_id}" if item.framework_binding_id else "",
                ]
                if value
            ) or "global"
            table.add_row(str(item.id), item.principal.principal_key, item.role.role_key, item.approval_status, scope)
        console.print(table)


@rbac_app.command("check")
def check_rbac_permission(
    principal_key: str = typer.Argument(..., help="Principal key"),
    permission: str = typer.Argument(..., help="Permission name"),
    organization_id: Optional[int] = typer.Option(None, help="Organization scope"),
    business_unit_id: Optional[int] = typer.Option(None, help="Business unit scope"),
    product_id: Optional[int] = typer.Option(None, help="Product scope"),
    framework_binding_id: Optional[int] = typer.Option(None, help="Framework binding scope"),
) -> None:
    with session_scope() as session:
        allowed = AccessControlService(session).can(
            principal_key,
            permission,
            {
                "organization_id": organization_id,
                "business_unit_id": business_unit_id,
                "product_id": product_id,
                "framework_binding_id": framework_binding_id,
            },
        )
        console.print(f"{principal_key} -> {permission}: {allowed}")


@rbac_app.command("conflicts")
def list_rbac_conflicts() -> None:
    with session_scope() as session:
        rows = AccessControlService(session).segregation_conflicts()
        table = Table(title="Segregation Of Duties Conflicts")
        table.add_column("Principal")
        table.add_column("Roles")
        table.add_column("Scope")
        for item in rows:
            scope = ",".join(
                f"{key}={value}" for key, value in item["scope"].items() if value is not None
            ) or "global"
            table.add_row(item["principal_key"], ", ".join(item["roles"]), scope)
        console.print(table)


@framework_app.command("seed")
def seed_frameworks() -> None:
    with session_scope() as session:
        touched = FrameworkService(session).seed_templates()
        console.print(f"Synchronized {len(touched)} framework template(s)")


@framework_app.command("list-templates")
def list_templates() -> None:
    table = Table(title="Framework Templates")
    table.add_column("Code")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Controls")
    for item in load_templates():
        table.add_row(item["code"], item["name"], item["version"], str(len(item.get("controls", []))))
    console.print(table)


@framework_app.command("list")
def list_frameworks() -> None:
    with session_scope() as session:
        frameworks = FrameworkService(session).list_frameworks()
        table = Table(title="Frameworks")
        table.add_column("Code")
        table.add_column("Name")
        table.add_column("Active")
        table.add_column("AWS Profile")
        table.add_column("AWS Region")
        table.add_column("Controls")
        for item in frameworks:
            table.add_row(
                item.code,
                item.name,
                str(item.active),
                item.aws_profile or "",
                item.aws_region or "",
                str(len(item.controls)),
            )
        console.print(table)


@framework_app.command("seed-evidence-plans")
def seed_evidence_plans(
    framework: Optional[str] = typer.Option(None, "--framework", help="Optional framework code"),
) -> None:
    with session_scope() as session:
        count = FrameworkService(session).seed_default_evidence_plans(framework)
        console.print(f"Seeded or refreshed {count} default evidence plan(s).")


@framework_app.command("enable")
def enable_framework(
    code: str = typer.Argument(..., help="Framework code"),
    aws_profile: str = typer.Option(..., help="Local AWS CLI SSO profile name"),
    aws_region: str = typer.Option(settings.default_aws_region, help="AWS region"),
) -> None:
    with session_scope() as session:
        framework = FrameworkService(session).enable_framework(code, aws_profile, aws_region)
        console.print(f"Enabled {framework.code} for profile={aws_profile} region={aws_region}")


@framework_app.command("disable")
def disable_framework(code: str = typer.Argument(..., help="Framework code")) -> None:
    with session_scope() as session:
        framework = FrameworkService(session).disable_framework(code)
        console.print(f"Disabled {framework.code}")


@framework_app.command("controls")
def list_controls(code: str = typer.Argument(..., help="Framework code")) -> None:
    with session_scope() as session:
        framework = session.scalar(
            select(Framework)
            .options(selectinload(Framework.controls).selectinload(Control.metadata_entry))
            .where(Framework.code == code)
        )
        if framework is None:
            raise typer.BadParameter(f"Framework not found: {code}")
        table = Table(title=f"Controls for {framework.code}")
        table.add_column("Control ID")
        table.add_column("Title")
        table.add_column("Evidence Query")
        table.add_column("Check Type")
        table.add_column("Severity")
        for control in framework.controls:
            check_type = control.metadata_entry.check_type if control.metadata_entry else ""
            table.add_row(control.control_id, control.title, control.evidence_query, check_type, control.severity)
        console.print(table)


@evidence_app.command("collect")
def collect_evidence(
    framework: Optional[str] = typer.Option(None, "--framework", help="Framework code"),
    binding: Optional[str] = typer.Option(None, "--binding", help="Organization framework binding code"),
    product: Optional[str] = typer.Option(None, "--product", help="Product code for scoped collection"),
    flavor: Optional[str] = typer.Option(None, "--flavor", help="Product flavor code for scoped collection"),
) -> None:
    if not framework and not binding:
        raise typer.BadParameter("Provide either --framework or --binding")
    if framework and binding:
        raise typer.BadParameter("Use either --framework or --binding, not both")
    with session_scope() as session:
        service = EvidenceService(session)
        if binding:
            results = service.collect_for_binding(binding_code=binding, product_code=product, product_flavor_code=flavor)
            title = f"Evidence Collection {binding}"
        else:
            results = service.collect_for_framework(framework)
            title = f"Evidence Collection {framework}"
        table = Table(title=title)
        table.add_column("Control")
        table.add_column("Status")
        table.add_column("Summary")
        table.add_column("Confluence Page")
        for item in results:
            table.add_row(
                item.control.control_id,
                item.status,
                item.summary,
                item.confluence_page_id or "",
            )
        console.print(table)


@evidence_app.command("login-plan")
def evidence_login_plan(
    binding: str = typer.Option(..., "--binding", help="Organization framework binding code"),
    product: Optional[str] = typer.Option(None, "--product", help="Product code for scoped collection"),
    flavor: Optional[str] = typer.Option(None, "--flavor", help="Product flavor code for scoped collection"),
) -> None:
    with session_scope() as session:
        plan = EvidenceService(session).build_collection_plan_for_binding(
            binding_code=binding,
            product_code=product,
            product_flavor_code=flavor,
        )
        table = Table(title=f"SSO Login Plan {binding}")
        table.add_column("Profile")
        table.add_column("Accounts")
        table.add_column("Regions")
        table.add_column("Controls")
        table.add_column("Registered")
        table.add_column("Validation")
        table.add_column("Alignment")
        table.add_column("Login Command")
        for item in plan["profiles"]:
            table.add_row(
                item["aws_profile"],
                ", ".join(item["aws_account_ids"]),
                ", ".join(item["regions"]),
                str(len(item["controls"])),
                str(item["registered_in_app"]),
                item["last_validation_status"] or "unknown",
                item["account_alignment"],
                item["login_command"],
            )
        console.print(table)
        if plan["missing_profile_metadata"]:
            console.print(
                "Profiles missing app metadata: " + ", ".join(plan["missing_profile_metadata"])
            )


@evidence_app.command("readiness-report")
def evidence_readiness_report(
    binding: str = typer.Option(..., "--binding", help="Organization framework binding code"),
    product: Optional[str] = typer.Option(None, "--product", help="Product code for scoped readiness"),
    flavor: Optional[str] = typer.Option(None, "--flavor", help="Product flavor code for scoped readiness"),
) -> None:
    with session_scope() as session:
        readiness = OperationalReadinessService(session).assess_binding(
            binding_code=binding,
            product_code=product,
            product_flavor_code=flavor,
        )
        console.print(
            f"Operational readiness for {binding}: {readiness['overall_score']}/4.0 ({readiness['readiness_status']})"
        )
        area_table = Table(title="Readiness Areas")
        area_table.add_column("Area")
        area_table.add_column("Score")
        area_table.add_column("Target")
        area_table.add_column("Summary")
        for item in readiness["areas"]:
            area_table.add_row(item["area"], str(item["score"]), str(item["target"]), item["summary"])
        console.print(area_table)

        profile_table = Table(title="Required Profiles")
        profile_table.add_column("Profile")
        profile_table.add_column("Registered")
        profile_table.add_column("Validation")
        profile_table.add_column("Detected Account")
        profile_table.add_column("Alignment")
        profile_table.add_column("Controls")
        for item in readiness["profiles"]:
            profile_table.add_row(
                item["aws_profile"],
                str(item["registered_in_app"]),
                item["last_validation_status"],
                item["detected_account_id"],
                item["account_alignment"],
                str(item["controls"]),
            )
        console.print(profile_table)

        if readiness["blockers"]:
            console.print("Blockers:")
            for item in readiness["blockers"]:
                console.print(f"- {item}")
        if readiness["warnings"]:
            console.print("Warnings:")
            for item in readiness["warnings"][:10]:
                console.print(f"- {item}")


@evidence_app.command("upload-manual")
def upload_manual_evidence(
    binding: str = typer.Option(..., "--binding", help="Organization framework binding code"),
    control_id: str = typer.Option(..., "--control-id", help="Framework control ID"),
    summary: str = typer.Option(..., help="Evidence summary"),
    status: str = typer.Option("pass", help="pass, fail, observed"),
    product: Optional[str] = typer.Option(None, "--product", help="Product code"),
    flavor: Optional[str] = typer.Option(None, "--flavor", help="Product flavor code"),
    file_path: Optional[str] = typer.Option(None, "--file", help="Optional file path for a supporting artifact"),
    uploaded_by: str = typer.Option("", help="Operator identity"),
    note: str = typer.Option("", help="Manual evidence notes"),
    classification: str = typer.Option("confidential", help="Evidence classification"),
    publish_to_confluence: bool = typer.Option(False, "--publish-to-confluence/--no-publish-to-confluence"),
) -> None:
    with session_scope() as session:
        evidence = EvidenceService(session).upload_manual_evidence(
            binding_code=binding,
            control_id=control_id,
            summary=summary,
            status=status,
            product_code=product,
            product_flavor_code=flavor,
            note=note,
            file_path=file_path,
            uploaded_by=uploaded_by,
            classification=classification,
            publish_to_confluence=publish_to_confluence,
        )
        console.print(f"Manual evidence created: {evidence.id} ({evidence.lifecycle_status})")


@evidence_app.command("show")
def show_evidence(
    evidence_id: int = typer.Argument(..., help="Evidence item ID"),
) -> None:
    with session_scope() as session:
        evidence = session.get(EvidenceItem, evidence_id)
        if evidence is None:
            raise typer.BadParameter(f"Evidence item not found: {evidence_id}")
        payload = EvidenceService(session).decrypt_payload(evidence)
        console.print(f"Evidence {evidence.id}: {evidence.control.framework.code} {evidence.control.control_id}")
        console.print(f"Status: {evidence.status} | Lifecycle: {evidence.lifecycle_status}")
        console.print(f"Collected: {evidence.collected_at.isoformat()}")
        console.print(json.dumps(payload, indent=2, default=str))
        artifact = EvidenceService(session).manual_artifact(evidence)
        if artifact:
            console.print(
                f"Manual artifact: {artifact['file_name']} ({artifact['content_type']}, {artifact['size_bytes']} bytes)"
            )


@evidence_app.command("review")
def review_evidence(
    evidence_id: int = typer.Argument(..., help="Evidence item ID"),
    lifecycle_status: str = typer.Option(..., help="approved, rejected, pending_review"),
    actor: str = typer.Option("review_cli", help="Reviewer identity"),
    rationale: str = typer.Option("", help="Review rationale"),
) -> None:
    with session_scope() as session:
        evidence = EvidenceService(session).review_evidence_item(evidence_id, lifecycle_status, actor, rationale)
        console.print(f"Evidence {evidence.id} is now {evidence.lifecycle_status}")


@assessment_app.command("run")
def run_assessment(
    framework: list[str] = typer.Option([], "--framework", help="Framework code; repeat for multiple"),
    binding: Optional[str] = typer.Option(None, "--binding", help="Organization framework binding code"),
    product: Optional[str] = typer.Option(None, "--product", help="Product code for scoped assessments"),
    flavor: Optional[str] = typer.Option(None, "--flavor", help="Product flavor code for scoped assessments"),
) -> None:
    if binding and framework:
        raise typer.BadParameter("Use either repeated --framework values or --binding, not both")
    if not binding and not framework:
        raise typer.BadParameter("Provide at least one --framework or one --binding")
    with session_scope() as session:
        service = AssessmentService(session)
        if binding:
            run = service.run_binding_assessment(binding_code=binding, product_code=product, product_flavor_code=flavor)
            console.print(f"Assessment completed for {binding} with score {run.score}%")
        else:
            runs = service.run_assessments(framework)
            for run, framework_code in zip(runs, framework):
                console.print(f"Assessment completed for {framework_code} with score {run.score}%")


@assessment_app.command("list")
def list_assessments(
    framework: Optional[str] = typer.Option(None, "--framework", help="Optional framework code filter"),
    status: Optional[str] = typer.Option(None, "--status", help="Optional assessment status filter"),
    limit: int = typer.Option(50, "--limit", min=1, max=500, help="Maximum rows to show"),
) -> None:
    with session_scope() as session:
        query = (
            select(AssessmentRun)
            .options(
                selectinload(AssessmentRun.framework),
                selectinload(AssessmentRun.organization),
                selectinload(AssessmentRun.product),
                selectinload(AssessmentRun.product_flavor),
            )
            .order_by(AssessmentRun.started_at.desc())
        )
        if framework:
            query = query.join(AssessmentRun.framework).where(Framework.code == framework)
        if status:
            query = query.where(AssessmentRun.status == status)
        runs = session.scalars(query.limit(limit)).all()

        table = Table(title="Assessment Runs")
        table.add_column("ID")
        table.add_column("Framework")
        table.add_column("Organization")
        table.add_column("Product")
        table.add_column("Flavor")
        table.add_column("Started")
        table.add_column("Status")
        table.add_column("Review")
        table.add_column("Assurance")
        table.add_column("Score")
        for item in runs:
            table.add_row(
                str(item.id),
                item.framework.code if item.framework else "",
                item.organization.code if item.organization else "",
                item.product.code if item.product else "",
                item.product_flavor.code if item.product_flavor else "",
                item.started_at.isoformat() if item.started_at else "",
                item.status,
                item.review_status,
                item.assurance_status,
                str(item.score),
            )
        console.print(table)


@schedule_app.command("create")
def create_schedule(
    name: str = typer.Option(..., help="Schedule name"),
    cadence: str = typer.Option(..., help="monthly, quarterly, yearly"),
    framework: list[str] = typer.Option([], "--framework", help="Framework code; repeat for multiple"),
    binding: Optional[str] = typer.Option(None, "--binding", help="Framework binding code for scoped schedules"),
    product: Optional[str] = typer.Option(None, "--product", help="Product code for binding-scoped schedules"),
    flavor: Optional[str] = typer.Option(None, "--flavor", help="Product flavor code for binding-scoped schedules"),
    execution_mode: str = typer.Option("assisted", help="manual, assisted, autonomous"),
    notes: str = typer.Option("", help="Operational notes"),
) -> None:
    with session_scope() as session:
        schedule = AssessmentService(session).create_schedule(
            framework_codes=framework,
            name=name,
            cadence=cadence,
            binding_code=binding,
            product_code=product,
            product_flavor_code=flavor,
            execution_mode=execution_mode,
            notes=notes,
        )
        console.print(
            f"Created schedule {schedule.name} for {schedule.framework_codes} next run at {schedule.next_run_at.isoformat()}"
        )


@schedule_app.command("list")
def list_schedules(framework: Optional[str] = typer.Option(None, "--framework")) -> None:
    with session_scope() as session:
        query = select(AssessmentSchedule).options(
            selectinload(AssessmentSchedule.framework),
            selectinload(AssessmentSchedule.framework_binding),
            selectinload(AssessmentSchedule.product),
            selectinload(AssessmentSchedule.product_flavor),
        )
        if framework:
            query = query.join(Framework).where(Framework.code == framework)
        schedules = session.scalars(query).all()
        table = Table(title="Assessment Schedules")
        table.add_column("Name")
        table.add_column("Framework")
        table.add_column("Binding")
        table.add_column("Product")
        table.add_column("Flavor")
        table.add_column("Cadence")
        table.add_column("Mode")
        table.add_column("Enabled")
        table.add_column("Last Status")
        table.add_column("Last Run")
        table.add_column("Next Run")
        for item in schedules:
            table.add_row(
                item.name,
                item.framework_codes or (item.framework.code if item.framework else ""),
                item.framework_binding.binding_code if item.framework_binding else "",
                item.product.code if item.product else "",
                item.product_flavor.code if item.product_flavor else "",
                item.cadence,
                item.execution_mode,
                str(item.enabled),
                item.last_run_status,
                item.last_run_at.isoformat() if item.last_run_at else "",
                item.next_run_at.isoformat(),
            )
        console.print(table)


@schedule_app.command("run-due")
def run_due_schedules() -> None:
    with session_scope() as session:
        runs = AssessmentService(session).run_due_schedules()
        console.print(f"Executed {len(runs)} due schedule(s)")


@schedule_app.command("run-one")
def run_one_schedule(
    schedule_id: int = typer.Argument(..., help="Assessment schedule ID"),
) -> None:
    with session_scope() as session:
        runs = AssessmentService(session).run_schedule(schedule_id)
        console.print(f"Executed schedule {schedule_id} with {len(runs)} assessment run(s)")


@org_app.command("create")
def create_organization(
    name: str = typer.Argument(..., help="Organization display name"),
    code: Optional[str] = typer.Option(None, help="Stable organization code"),
    description: str = typer.Option("", help="Organization description"),
) -> None:
    with session_scope() as session:
        organization = WorkbenchService(session).create_organization(name=name, code=code, description=description)
        console.print(f"Organization ready: {organization.code} ({organization.name})")


@org_app.command("list")
def list_organizations() -> None:
    with session_scope() as session:
        organizations = WorkbenchService(session).list_organizations()
        table = Table(title="Organizations")
        table.add_column("Code")
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Bindings")
        for item in organizations:
            table.add_row(item.code, item.name, item.status, str(len(item.framework_bindings)))
        console.print(table)


@org_app.command("bind-framework")
def bind_framework(
    org: str = typer.Option(..., "--org", help="Organization code"),
    framework: str = typer.Option(..., "--framework", help="Framework code"),
    aws_profile: str = typer.Option(..., help="AWS CLI profile"),
    aws_region: str = typer.Option(settings.default_aws_region, help="AWS region"),
    name: Optional[str] = typer.Option(None, help="Binding display name"),
    binding_code: Optional[str] = typer.Option(None, help="Stable binding code"),
    aws_account_id: Optional[str] = typer.Option(None, help="AWS account ID"),
    confluence_connection: Optional[str] = typer.Option(None, help="Secure Confluence connection name"),
    confluence_parent_page_id: Optional[str] = typer.Option(None, help="Confluence parent page override"),
    lifecycle_status: str = typer.Option("active", help="Lifecycle status"),
    notes: str = typer.Option("", help="Operational notes"),
) -> None:
    with session_scope() as session:
        binding = WorkbenchService(session).bind_framework(
            organization_code=org,
            framework_code=framework,
            aws_profile=aws_profile,
            aws_region=aws_region,
            name=name,
            binding_code=binding_code,
            aws_account_id=aws_account_id,
            confluence_connection_name=confluence_connection,
            confluence_parent_page_id=confluence_parent_page_id,
            lifecycle_status=lifecycle_status,
            notes=notes,
        )
        console.print(f"Framework binding ready: {binding.binding_code}")


@org_app.command("bindings")
def list_bindings(org: Optional[str] = typer.Option(None, "--org", help="Organization code")) -> None:
    with session_scope() as session:
        bindings = WorkbenchService(session).list_framework_bindings(organization_code=org)
        table = Table(title="Framework Bindings")
        table.add_column("Binding Code")
        table.add_column("Organization")
        table.add_column("Framework")
        table.add_column("AWS Profile")
        table.add_column("AWS Region")
        table.add_column("Confluence")
        table.add_column("Enabled")
        for item in bindings:
            table.add_row(
                item.binding_code,
                item.organization.code,
                item.framework.code,
                item.aws_profile,
                item.aws_region,
                item.confluence_connection.name if item.confluence_connection else "",
                str(item.enabled),
            )
        console.print(table)


@org_app.command("review-binding")
def review_binding(
    binding: str = typer.Option(..., "--binding", help="Framework binding code"),
    lifecycle_status: str = typer.Option(..., "--status", help="New lifecycle status"),
    actor: str = typer.Option("workbench_cli", help="Reviewer"),
    rationale: str = typer.Option("", help="Rationale"),
) -> None:
    with session_scope() as session:
        item = WorkbenchService(session).review_framework_binding(
            binding_code=binding,
            lifecycle_status=lifecycle_status,
            actor=actor,
            rationale=rationale,
        )
        console.print(f"Framework binding {item.binding_code} moved to {item.lifecycle_status}")


@org_app.command("add-aws-target")
def add_aws_target(
    org: str = typer.Option(..., "--org", help="Organization code"),
    name: str = typer.Option(..., help="Target display name"),
    aws_profile: str = typer.Option(..., help="Local AWS CLI SSO profile"),
    regions: str = typer.Option(..., help="Comma-separated region list"),
    binding: Optional[str] = typer.Option(None, "--binding", help="Framework binding code"),
    product: Optional[str] = typer.Option(None, "--product", help="Product code"),
    flavor: Optional[str] = typer.Option(None, "--flavor", help="Product flavor code"),
    unified_control: Optional[str] = typer.Option(None, "--unified-control", help="Unified control code"),
    framework: Optional[str] = typer.Option(None, "--framework", help="Framework code"),
    control_id: Optional[str] = typer.Option(None, "--control-id", help="Framework control ID"),
    target_code: Optional[str] = typer.Option(None, "--target-code", help="Stable target identifier"),
    aws_account_id: str = typer.Option("", help="AWS account ID"),
    role_name: str = typer.Option("", help="Informational role name"),
    lifecycle_status: str = typer.Option("active", help="Lifecycle status"),
    notes: str = typer.Option("", help="Notes"),
) -> None:
    with session_scope() as session:
        target = WorkbenchService(session).upsert_aws_evidence_target(
            organization_code=org,
            binding_code=binding,
            product_code=product,
            product_flavor_code=flavor,
            unified_control_code=unified_control,
            framework_code=framework,
            control_id=control_id,
            name=name,
            target_code=target_code,
            aws_profile=aws_profile,
            aws_account_id=aws_account_id,
            role_name=role_name,
            regions_json=json.dumps([item.strip() for item in regions.split(",") if item.strip()]),
            execution_mode="aws_sso_login",
            lifecycle_status=lifecycle_status,
            notes=notes,
        )
        console.print(f"AWS evidence target ready: {target.target_code}")


@org_app.command("aws-targets")
def list_aws_targets(
    org: Optional[str] = typer.Option(None, "--org", help="Organization code"),
    binding: Optional[str] = typer.Option(None, "--binding", help="Framework binding code"),
    product: Optional[str] = typer.Option(None, "--product", help="Product code"),
) -> None:
    with session_scope() as session:
        targets = WorkbenchService(session).list_aws_evidence_targets(
            organization_code=org,
            binding_code=binding,
            product_code=product,
        )
        table = Table(title="AWS Evidence Targets")
        table.add_column("Target")
        table.add_column("Profile")
        table.add_column("Account")
        table.add_column("Regions")
        table.add_column("Product")
        table.add_column("Flavor")
        table.add_column("Control")
        for item in targets:
            table.add_row(
                item.target_code,
                item.aws_profile,
                item.aws_account_id,
                ", ".join(json.loads(item.regions_json or "[]")),
                item.product.code if item.product else "",
                item.product_flavor.code if item.product_flavor else "",
                item.control.control_id if item.control else (item.unified_control.code if item.unified_control else ""),
            )
        console.print(table)


@org_app.command("review-aws-target")
def review_aws_target(
    target_code: str = typer.Option(..., "--target", help="AWS evidence target code"),
    lifecycle_status: str = typer.Option(..., "--status", help="New lifecycle status"),
    actor: str = typer.Option("workbench_cli", help="Reviewer"),
    rationale: str = typer.Option("", help="Rationale"),
) -> None:
    with session_scope() as session:
        item = WorkbenchService(session).review_aws_evidence_target(
            target_code=target_code,
            lifecycle_status=lifecycle_status,
            actor=actor,
            rationale=rationale,
        )
        console.print(f"AWS evidence target {item.target_code} moved to {item.lifecycle_status}")


@ucf_app.command("create")
def create_unified_control(
    code: str = typer.Argument(..., help="Unified control code"),
    name: str = typer.Option(..., help="Unified control name"),
    description: str = typer.Option("", help="Description"),
    domain: str = typer.Option("", help="Domain"),
    family: str = typer.Option("", help="Family"),
    control_type: str = typer.Option("", help="Control type"),
    default_severity: str = typer.Option("medium", help="Default severity"),
    implementation_guidance: str = typer.Option("", help="Shared implementation guidance"),
    test_guidance: str = typer.Option("", help="Shared test guidance"),
) -> None:
    with session_scope() as session:
        unified_control = WorkbenchService(session).create_unified_control(
            code=code,
            name=name,
            description=description,
            domain=domain,
            family=family,
            control_type=control_type,
            default_severity=default_severity,
            implementation_guidance=implementation_guidance,
            test_guidance=test_guidance,
        )
        console.print(f"Unified control ready: {unified_control.code}")


@ucf_app.command("list")
def list_unified_controls() -> None:
    with session_scope() as session:
        unified_controls = WorkbenchService(session).list_unified_controls()
        table = Table(title="Unified Controls")
        table.add_column("Code")
        table.add_column("Name")
        table.add_column("Domain")
        table.add_column("Family")
        table.add_column("Severity")
        for item in unified_controls:
            table.add_row(item.code, item.name, item.domain, item.family, item.default_severity)
        console.print(table)


@ucf_app.command("map")
def map_framework_control(
    unified_control: str = typer.Option(..., "--unified-control", help="Unified control code"),
    framework: str = typer.Option(..., "--framework", help="Framework code"),
    control_id: str = typer.Option(..., "--control-id", help="Framework control ID"),
    mapping_type: str = typer.Option("mapped", help="Mapping type"),
    rationale: str = typer.Option("", help="Mapping rationale"),
    confidence: float = typer.Option(1.0, help="Mapping confidence"),
    inheritance_strategy: str = typer.Option("manual_review", help="Inheritance strategy"),
) -> None:
    with session_scope() as session:
        mapping = WorkbenchService(session).map_framework_control(
            unified_control_code=unified_control,
            framework_code=framework,
            control_id=control_id,
            mapping_type=mapping_type,
            rationale=rationale,
            confidence=confidence,
            inheritance_strategy=inheritance_strategy,
        )
        console.print(f"Mapped control {mapping.control.control_id} to {mapping.unified_control.code}")


@implementation_app.command("upsert")
def upsert_implementation(
    org: str = typer.Option(..., "--org", help="Organization code"),
    title: str = typer.Option(..., help="Implementation title"),
    unified_control: Optional[str] = typer.Option(None, "--unified-control", help="Unified control code"),
    framework: Optional[str] = typer.Option(None, "--framework", help="Framework code"),
    control_id: Optional[str] = typer.Option(None, "--control-id", help="Framework control ID"),
    implementation_code: Optional[str] = typer.Option(None, help="Stable implementation code"),
    objective: str = typer.Option("", help="Control objective"),
    impl_aws: str = typer.Option("", help="AWS implementation notes"),
    impl_onprem: str = typer.Option("", help="On-prem implementation notes"),
    impl_general: str = typer.Option("", help="General implementation notes"),
    status: str = typer.Option("draft", help="Status"),
    lifecycle: str = typer.Option("design", help="Lifecycle stage"),
    owner: str = typer.Option("", help="Owner"),
    priority: str = typer.Option("medium", help="Priority"),
    frequency: str = typer.Option("", help="Review frequency"),
    test_plan: str = typer.Option("", help="Test plan"),
    evidence_links: str = typer.Option("", help="Evidence links"),
    jira_key: str = typer.Option("", help="Jira issue key"),
    servicenow_ticket: str = typer.Option("", help="ServiceNow ticket"),
    design_doc: str = typer.Option("", help="Design document link"),
    blockers: str = typer.Option("", help="Known blockers"),
    notes: str = typer.Option("", help="Additional notes"),
) -> None:
    with session_scope() as session:
        implementation = WorkbenchService(session).upsert_control_implementation(
            organization_code=org,
            title=title,
            unified_control_code=unified_control,
            framework_code=framework,
            control_id=control_id,
            implementation_code=implementation_code,
            objective=objective,
            impl_aws=impl_aws,
            impl_onprem=impl_onprem,
            impl_general=impl_general,
            status=status,
            lifecycle=lifecycle,
            owner=owner,
            priority=priority,
            frequency=frequency,
            test_plan=test_plan,
            evidence_links=evidence_links,
            jira_key=jira_key,
            servicenow_ticket=servicenow_ticket,
            design_doc=design_doc,
            blockers=blockers,
            notes=notes,
        )
        console.print(f"Implementation saved: {implementation.id}")


@implementation_app.command("list")
def list_implementations(org: Optional[str] = typer.Option(None, "--org", help="Organization code")) -> None:
    with session_scope() as session:
        implementations = WorkbenchService(session).list_control_implementations(organization_code=org)
        table = Table(title="Control Implementations")
        table.add_column("ID")
        table.add_column("Organization")
        table.add_column("Title")
        table.add_column("Status")
        table.add_column("Lifecycle")
        table.add_column("Owner")
        for item in implementations:
            table.add_row(str(item.id), item.organization.code, item.title, item.status, item.lifecycle, item.owner)
        console.print(table)


@security_app.command("bootstrap")
def bootstrap_security() -> None:
    init_database()
    store = KeyringSecretStore(settings.secret_namespace, settings.secret_files_dir)
    key_ref = EvidenceVault(store).initialize()
    provider = store.last_provider or "secure backend"
    console.print(f"Security bootstrap completed. Evidence master key is stored in the {provider} backend as {key_ref}.")


@security_app.command("secrets")
def list_secrets() -> None:
    with session_scope() as session:
        rows = SecretService(session).list_secrets()
        table = Table(title="Secret Metadata")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Provider")
        table.add_column("Status")
        table.add_column("Last Validated")
        for item in rows:
            table.add_row(
                item.name,
                item.secret_type,
                item.provider,
                item.status,
                item.last_validated_at.isoformat() if item.last_validated_at else "",
            )
        console.print(table)


@confluence_app.command("upsert")
def upsert_confluence_connection(
    name: str = typer.Option(..., help="Stable connection name"),
    base_url: str = typer.Option(..., help="Confluence base URL"),
    space_key: str = typer.Option(..., help="Confluence space key"),
    auth_mode: str = typer.Option("basic", help="basic or bearer"),
    username: str = typer.Option("", help="Username or email for basic auth"),
    parent_page_id: str = typer.Option("", help="Default parent page ID"),
    framework: Optional[str] = typer.Option(None, help="Optional framework code"),
    verify_tls: bool = typer.Option(True, "--verify-tls/--no-verify-tls", help="Enable TLS verification"),
    is_default: bool = typer.Option(False, "--default/--not-default", help="Mark as default connection"),
    secret: str = typer.Option(
        ...,
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="PAT, API token, or bearer token stored securely in the OS keyring",
    ),
) -> None:
    with session_scope() as session:
        connection = ConfluenceConnectionService(session).upsert_connection(
            name=name,
            base_url=base_url,
            space_key=space_key,
            secret_value=secret,
            auth_mode=auth_mode,
            username=username,
            parent_page_id=parent_page_id,
            framework_code=framework,
            verify_tls=verify_tls,
            is_default=is_default,
        )
        console.print(f"Confluence connection ready: {connection.name}")


@confluence_app.command("list")
def list_confluence_connections() -> None:
    with session_scope() as session:
        rows = ConfluenceConnectionService(session).list_connections()
        table = Table(title="Confluence Connections")
        table.add_column("Name")
        table.add_column("Base URL")
        table.add_column("Space")
        table.add_column("Auth")
        table.add_column("Default")
        table.add_column("Status")
        table.add_column("Health")
        for item in rows:
            table.add_row(
                item.name,
                item.base_url,
                item.space_key,
                item.auth_mode,
                str(item.is_default),
                item.status,
                item.last_test_status or "untested",
            )
        console.print(table)


@confluence_app.command("test")
def test_confluence_connection(
    name: Optional[str] = typer.Option(None, help="Connection name. Uses the default connection when omitted."),
) -> None:
    with session_scope() as session:
        result = ConfluenceConnectionService(session).test_connection(name)
        console.print(f"[{result['status']}] {result['message']}")


@lifecycle_app.command("recent")
def list_lifecycle_events(
    entity_type: Optional[str] = typer.Option(None, help="Filter by entity type"),
    limit: int = typer.Option(50, help="Maximum number of rows"),
) -> None:
    with session_scope() as session:
        query = select(LifecycleEvent).order_by(LifecycleEvent.created_at.desc())
        if entity_type:
            query = query.where(LifecycleEvent.entity_type == entity_type)
        rows = session.scalars(query.limit(limit)).all()
        table = Table(title="Lifecycle Events")
        table.add_column("When")
        table.add_column("Entity")
        table.add_column("ID")
        table.add_column("Lifecycle")
        table.add_column("From")
        table.add_column("To")
        table.add_column("Actor")
        for item in rows:
            table.add_row(
                item.created_at.isoformat(),
                item.entity_type,
                str(item.entity_id),
                item.lifecycle_name,
                item.from_state,
                item.to_state,
                item.actor,
            )
        console.print(table)


@review_app.command("queue")
def review_queue() -> None:
    with session_scope() as session:
        summary = ReviewQueueService(session).summary()
        console.print(f"Pending review items: {summary['total']}")
        table = Table(title="Review Queue")
        table.add_column("Category")
        table.add_column("Priority")
        table.add_column("Status")
        table.add_column("Reference")
        table.add_column("Title")
        table.add_column("Detail")
        for item in summary["top_items"]:
            table.add_row(
                item["category"],
                item["priority"],
                item["status"],
                item["reference"],
                item["title"],
                item["detail"],
            )
        console.print(table)


@review_app.command("mapping")
def review_mapping(
    mapping_id: int = typer.Argument(..., help="Unified mapping ID"),
    approval_status: str = typer.Option(..., help="approved, proposed, rejected"),
    reviewed_by: str = typer.Option("", help="Reviewer identity"),
    notes: str = typer.Option("", help="Review notes"),
) -> None:
    with session_scope() as session:
        mapping = WorkbenchService(session).review_mapping(mapping_id, approval_status, reviewed_by, notes)
        console.print(f"Mapping {mapping.id} is now {mapping.approval_status}")


@review_app.command("plan")
def review_plan(
    plan_code: str = typer.Argument(..., help="Evidence plan code"),
    lifecycle_status: str = typer.Option(..., help="draft, approved, active, ready, retired"),
    actor: str = typer.Option("review_cli", help="Reviewer identity"),
    rationale: str = typer.Option("", help="Review rationale"),
) -> None:
    with session_scope() as session:
        plan = WorkbenchService(session).review_evidence_collection_plan(plan_code, lifecycle_status, actor, rationale)
        console.print(f"Evidence plan {plan.plan_code} is now {plan.lifecycle_status}")


@review_app.command("questionnaire-item")
def review_questionnaire_item(
    item_id: int = typer.Argument(..., help="Questionnaire item ID"),
    review_status: str = typer.Option(..., help="approved, suggested, rejected, needs_revision"),
    reviewer: str = typer.Option("", help="Reviewer identity"),
    approved_answer: str = typer.Option("", help="Optional approved answer override"),
    note: str = typer.Option("", help="Review note"),
) -> None:
    with session_scope() as session:
        item = QuestionnaireService(session).review_questionnaire_item(
            item_id=item_id,
            review_status=review_status,
            reviewer=reviewer,
            approved_answer=approved_answer,
            rationale_note=note,
        )
        console.print(f"Questionnaire item {item.id} is now {item.review_status}")


@review_app.command("assessment")
def review_assessment(
    run_id: int = typer.Argument(..., help="Assessment run ID"),
    review_status: str = typer.Option(..., help="approved, pending_review, rejected"),
    assurance_status: Optional[str] = typer.Option(None, help="Optional assurance status update"),
    actor: str = typer.Option("review_cli", help="Reviewer identity"),
    rationale: str = typer.Option("", help="Review rationale"),
) -> None:
    with session_scope() as session:
        run = AssessmentService(session).review_run(run_id, review_status, assurance_status, actor, rationale)
        console.print(f"Assessment run {run.id} review status is now {run.review_status}")


@review_app.command("ai-suggestion")
def review_ai_suggestion(
    suggestion_id: int = typer.Argument(..., help="AI suggestion ID"),
    action: str = typer.Option(..., help="promote or dismiss"),
    actor: str = typer.Option("review_cli", help="Reviewer identity"),
    rationale: str = typer.Option("", help="Review rationale"),
) -> None:
    with session_scope() as session:
        service = SuggestionService(session)
        if action == "promote":
            suggestion = service.promote_mapping_suggestion(suggestion_id, reviewer=actor, notes=rationale)
            console.print(f"AI suggestion {suggestion.id} promoted into an approved mapping")
            return
        if action == "dismiss":
            suggestion = service.dismiss_suggestion(suggestion_id, reviewer=actor, notes=rationale)
            console.print(f"AI suggestion {suggestion.id} marked as reviewed")
            return
        raise typer.BadParameter("Action must be either 'promote' or 'dismiss'.")


@copilot_app.command("seed")
def seed_copilot_packs() -> None:
    with session_scope() as session:
        packs = AIKnowledgePackService(session).seed_templates()
        console.print(f"Synchronized {len(packs)} AI knowledge pack template(s).")


@copilot_app.command("list")
def list_copilot_packs() -> None:
    with session_scope() as session:
        service = AIKnowledgePackService(session)
        table = Table(title="AI Knowledge Packs")
        table.add_column("Pack")
        table.add_column("Name")
        table.add_column("Domain")
        table.add_column("Lifecycle")
        table.add_column("Approval")
        table.add_column("Active Version")
        for item in service.list_packs():
            try:
                active = service.active_version(item.pack_code)
                version_label = active.version_label
            except ValueError:
                version_label = ""
            table.add_row(
                item.pack_code,
                item.name,
                item.domain,
                item.lifecycle_status,
                item.approval_status,
                version_label,
            )
        console.print(table)


@copilot_app.command("tasks")
def list_copilot_tasks(
    pack: Optional[str] = typer.Option(None, "--pack", help="Pack code. Uses the configured default pack when omitted."),
) -> None:
    with session_scope() as session:
        service = AIKnowledgePackService(session)
        version = service.active_version(pack)
        table = Table(title=f"AI Knowledge Pack Tasks: {version.knowledge_pack.pack_code}")
        table.add_column("Task")
        table.add_column("Name")
        table.add_column("Workflow")
        table.add_column("Enabled")
        for item in service.list_tasks(version.knowledge_pack.pack_code):
            table.add_row(item.task_key, item.name, item.workflow_area, str(item.enabled))
        console.print(table)


@copilot_app.command("draft")
def draft_copilot_output(
    task: str = typer.Option(..., "--task", help="Knowledge pack task key"),
    framework: str = typer.Option(..., "--framework", help="Framework code"),
    control_id: str = typer.Option(..., "--control-id", help="Framework control ID"),
    unified_control: str = typer.Option(..., "--unified-control", help="Unified control code"),
    pack: Optional[str] = typer.Option(None, "--pack", help="Optional knowledge pack code"),
    org: Optional[str] = typer.Option(None, "--org", help="Optional organization code"),
    product: Optional[str] = typer.Option(None, "--product", help="Optional product code"),
    flavor: Optional[str] = typer.Option(None, "--flavor", help="Optional product flavor code"),
    store: bool = typer.Option(False, "--store/--no-store", help="Store the governed draft as an AI suggestion"),
) -> None:
    with session_scope() as session:
        service = AIKnowledgePackService(session)
        if store:
            suggestion = service.capture_task_suggestion(
                pack_code=pack,
                task_key=task,
                framework_code=framework,
                control_id=control_id,
                unified_control_code=unified_control,
                organization_code=org,
                product_code=product,
                product_flavor_code=flavor,
                actor="cli_copilot",
            )
            console.print(f"Stored governed draft as AI suggestion {suggestion.id}")
            return
        bundle = service.build_task_package(
            pack_code=pack,
            task_key=task,
            framework_code=framework,
            control_id=control_id,
            unified_control_code=unified_control,
            organization_code=org,
            product_code=product,
            product_flavor_code=flavor,
        )
        console.print("Prompt package:")
        console.print(json.dumps(bundle["prompt_package"], indent=2, default=str))
        console.print("\nDraft response:")
        console.print(json.dumps(bundle["draft_response"], indent=2, default=str))


@import_app.command("preview-framework")
def preview_framework_import(
    file_path: str = typer.Argument(..., help="Path to the CSV or spreadsheet source"),
    sheet_name: str = typer.Option("", help="Worksheet name for Excel sources"),
) -> None:
    with session_scope() as session:
        preview = FrameworkImportService(session).preview_source(file_path=file_path, sheet_name=sheet_name)
        console.print(f"Rows detected: {preview['row_count']}")
        console.print("Column mapping:")
        console.print(json.dumps(preview["column_mapping"], indent=2))
        table = Table(title="Framework Import Preview")
        table.add_column("Row")
        table.add_column("Requirement")
        table.add_column("Title")
        table.add_column("Domain")
        table.add_column("Section")
        for item in preview["records"][:15]:
            table.add_row(
                str(item["row_number"]),
                item["external_id"],
                item["title"],
                item["domain"],
                item["section"],
            )
        console.print(table)


@import_app.command("load-framework")
def load_framework_import(
    file_path: str = typer.Argument(..., help="Path to the CSV or spreadsheet source"),
    framework_code: str = typer.Option(..., help="Framework code"),
    framework_name: str = typer.Option(..., help="Framework name"),
    framework_version: str = typer.Option(..., help="Framework version"),
    sheet_name: str = typer.Option("", help="Worksheet name for Excel sources"),
    source_name: str = typer.Option("", help="Source name"),
    source_url: str = typer.Option("", help="Source URL"),
    source_version: str = typer.Option("", help="Source version"),
    category: str = typer.Option("framework", help="Framework category"),
    issuing_body: str = typer.Option("", help="Issuing body"),
    jurisdiction: str = typer.Option("global", help="Jurisdiction"),
    mapping_mode: str = typer.Option("suggest_only", help="none, suggest_only, map_existing, create_baseline"),
    auto_approve: bool = typer.Option(False, "--auto-approve/--no-auto-approve", help="Approve generated mappings immediately"),
    threshold: float = typer.Option(0.84, help="Confidence threshold for auto-mapping"),
    actor: str = typer.Option("cli_importer", help="Actor name for lifecycle traceability"),
) -> None:
    with session_scope() as session:
        result = FrameworkImportService(session).import_source(
            file_path=file_path,
            framework_code=framework_code,
            framework_name=framework_name,
            framework_version=framework_version,
            source_name=source_name or file_path,
            source_type=Path(file_path).suffix.lstrip("."),
            source_url=source_url,
            source_version=source_version,
            sheet_name=sheet_name,
            category=category,
            issuing_body=issuing_body,
            jurisdiction=jurisdiction,
            mapping_mode=mapping_mode,
            auto_mapping_threshold=threshold,
            auto_approve_mappings=auto_approve,
            actor=actor,
        )
        summary = result["summary"]
        console.print(
            f"Imported {summary['imported_count']} row(s); "
            f"mappings={summary['created_mappings']}, "
            f"baseline_controls={summary['created_unified_controls']}, "
            f"suggestions={summary['captured_suggestions']}, "
            f"reference_documents={summary['created_reference_documents']}, "
            f"reference_links={summary['created_reference_links']}"
        )


@import_app.command("load-scf")
def load_secure_controls_framework(
    file_path: str = typer.Argument(..., help="Path to the Secure Controls Framework workbook"),
    sheet_name: str = typer.Option("SCF 2025.3.1", help="Worksheet name"),
    actor: str = typer.Option("cli_scf_importer", help="Actor name for lifecycle traceability"),
    mark_as_pivot: bool = typer.Option(
        True,
        "--mark-as-pivot/--no-mark-as-pivot",
        help="Set Secure Controls Framework as the pivot framework for converged mappings.",
    ),
) -> None:
    with session_scope() as session:
        result = FrameworkImportService(session).import_secure_controls_framework(
            file_path=file_path,
            sheet_name=sheet_name,
            actor=actor,
            mark_as_pivot=mark_as_pivot,
        )
        summary = result["summary"]
        console.print(
            f"Imported SCF {summary['imported_count']} row(s); "
            f"baseline_controls={summary['created_unified_controls']}, "
            f"mappings={summary['created_mappings']}, "
            f"reference_documents={summary['created_reference_documents']}, "
            f"reference_links={summary['created_reference_links']}"
        )


@import_app.command("traceability")
def import_traceability(
    framework: Optional[str] = typer.Option(None, "--framework", help="Optional framework code filter"),
    limit: int = typer.Option(50, help="Maximum rows"),
) -> None:
    with session_scope() as session:
        rows = FrameworkImportService(session).traceability_rows(framework, limit=limit)
        table = Table(title="Framework Traceability")
        table.add_column("Framework")
        table.add_column("Requirement")
        table.add_column("Title")
        table.add_column("Source Ref")
        table.add_column("Unified Controls")
        table.add_column("References")
        for item in rows:
            table.add_row(
                item["framework"],
                item["control_id"],
                item["title"],
                item["source_reference"],
                ", ".join(item["mapped_unified_controls"]),
                ", ".join(item["reference_documents"]),
            )
        console.print(table)


@import_app.command("reference-documents")
def list_reference_documents() -> None:
    with session_scope() as session:
        rows = ReferenceLibraryService(session).list_reference_documents()
        table = Table(title="Reference Documents")
        table.add_column("Key")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Issuing Body")
        table.add_column("Jurisdiction")
        for item in rows:
            table.add_row(
                item.document_key,
                item.short_name or item.name,
                item.document_type,
                item.issuing_body,
                item.jurisdiction,
            )
        console.print(table)


@script_app.command("register")
def register_script_module(
    module_code: Optional[str] = typer.Option(None, help="Stable module code"),
    name: Optional[str] = typer.Option(None, help="Module name"),
    entrypoint_ref: Optional[str] = typer.Option(None, help="Python file, module, or executable path"),
    entrypoint_type: str = typer.Option("python_file", help="python_file, module, or command"),
    interpreter: str = typer.Option("python3", help="Interpreter for python-based modules"),
    working_directory: str = typer.Option("scripts", help="Working directory"),
    context_argument_name: str = typer.Option("--context-file", help="Optional context argument name"),
    default_arguments_json: str = typer.Option("[]", help="JSON array of default arguments"),
    default_config_path: str = typer.Option("", help="Default config file path"),
    manifest_path: str = typer.Option("", help="Optional manifest file path"),
    notes: str = typer.Option("", help="Notes"),
) -> None:
    with session_scope() as session:
        service = ScriptModuleService(session)
        if manifest_path:
            module = service.register_module_from_manifest(manifest_path)
        else:
            if not module_code or not name or not entrypoint_ref:
                raise typer.BadParameter("module_code, name, and entrypoint_ref are required when --manifest-path is not used.")
            module = service.register_module(
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
        console.print(f"Script module ready: {module.module_code}")


@script_app.command("list")
def list_script_modules() -> None:
    with session_scope() as session:
        rows = ScriptModuleService(session).list_modules()
        table = Table(title="Script Modules")
        table.add_column("Module")
        table.add_column("Name")
        table.add_column("Entrypoint")
        table.add_column("Type")
        table.add_column("Working Directory")
        for item in rows:
            table.add_row(item.module_code, item.name, item.entrypoint_ref, item.entrypoint_type, item.working_directory)
        console.print(table)


@script_app.command("bind")
def bind_script_module(
    module_code: str = typer.Option(..., help="Registered module code"),
    name: str = typer.Option(..., help="Binding name"),
    binding_code: str = typer.Option("", help="Optional stable binding code"),
    organization: str = typer.Option("", help="Organization code"),
    framework_binding: str = typer.Option("", help="Framework binding code"),
    product: str = typer.Option("", help="Product code"),
    flavor: str = typer.Option("", help="Product flavor code"),
    unified_control: str = typer.Option("", help="Unified control code"),
    framework: str = typer.Option("", help="Framework code"),
    control_id: str = typer.Option("", help="Framework control ID"),
    evidence_plan: str = typer.Option("", help="Evidence plan code"),
    config_path: str = typer.Option("", help="Config file path"),
    config_json: str = typer.Option("{}", help="JSON object for inline config"),
    arguments_json: str = typer.Option("[]", help="JSON array of arguments"),
    expected_outputs_json: str = typer.Option("[]", help="JSON array of expected outputs"),
    notes: str = typer.Option("", help="Notes"),
) -> None:
    with session_scope() as session:
        binding = ScriptModuleService(session).upsert_binding(
            module_code=module_code,
            name=name,
            binding_code=binding_code or None,
            organization_code=organization or None,
            framework_binding_code=framework_binding or None,
            product_code=product or None,
            product_flavor_code=flavor or None,
            unified_control_code=unified_control or None,
            framework_code=framework or None,
            control_id=control_id or None,
            evidence_plan_code=evidence_plan or None,
            config_path=config_path,
            config_json=config_json,
            arguments_json=arguments_json,
            expected_outputs_json=expected_outputs_json,
            notes=notes,
        )
        console.print(f"Script binding ready: {binding.binding_code}")


@script_app.command("bindings")
def list_script_bindings(module_code: Optional[str] = typer.Option(None, help="Optional module code filter")) -> None:
    with session_scope() as session:
        rows = ScriptModuleService(session).list_bindings(module_code)
        table = Table(title="Script Bindings")
        table.add_column("Binding")
        table.add_column("Module")
        table.add_column("Plan")
        table.add_column("Framework Binding")
        table.add_column("Product")
        table.add_column("Flavor")
        table.add_column("Control")
        for item in rows:
            table.add_row(
                item.binding_code,
                item.module.module_code if item.module else "",
                item.evidence_plan.plan_code if item.evidence_plan else "",
                item.framework_binding.binding_code if item.framework_binding else "",
                item.product.code if item.product else "",
                item.product_flavor.code if item.product_flavor else "",
                item.control.control_id if item.control else "",
            )
        console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
