from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.inspection import inspect as sa_inspect

from aws_local_audit.logging_utils import audit_event
from aws_local_audit.models import (
    AIKnowledgePack,
    AIKnowledgePackEvalCase,
    AIKnowledgePackReference,
    AIKnowledgePackTask,
    AIKnowledgePackVersion,
    AISuggestion,
    AccessRole,
    AssessmentRun,
    AssessmentSchedule,
    AssessmentScriptBinding,
    AssessmentScriptModule,
    AssessmentScriptRun,
    Asset,
    AuthorityDocument,
    AwsCliProfile,
    AwsEvidenceTarget,
    ActionItem,
    BusinessUnit,
    CircuitBreakerState,
    ConfluenceConnection,
    Control,
    ControlImplementation,
    ControlMetadata,
    CustomerQuestionnaire,
    CustomerQuestionnaireItem,
    EvidenceCollectionPlan,
    EvidenceItem,
    ExternalArtifactLink,
    ExternalCallLedger,
    FeatureFlag,
    Finding,
    Framework,
    FrameworkImportBatch,
    ImportedRequirement,
    ImportedRequirementReference,
    IdentityPrincipal,
    LifecycleEvent,
    Organization,
    OrganizationFrameworkBinding,
    Product,
    ProductControlProfile,
    ProductFlavor,
    ReferenceDocument,
    RoleAssignment,
    Risk,
    RiskTreatment,
    SecretMetadata,
    SystemSetting,
    Threat,
    UnifiedControl,
    UnifiedControlReference,
    UnifiedControlMapping,
    UserFeedbackMessage,
)
from aws_local_audit.services.evidence import EvidenceService


@dataclass(frozen=True, slots=True)
class AssetSpec:
    key: str
    label: str
    family: str
    model: type
    display_fields: tuple[str, ...]
    order_field: str | None = None
    artifact: bool = False
    description: str = ""


ASSET_SPECS: tuple[AssetSpec, ...] = (
    AssetSpec("authority_documents", "Authority Documents", "governance", AuthorityDocument, ("document_key", "name"), "document_key", description="Normative documents and policy authorities backing a framework."),
    AssetSpec("frameworks", "Frameworks", "governance", Framework, ("code", "name", "version"), "code", description="Framework shells and imported standards managed by the platform."),
    AssetSpec("controls", "Framework Controls", "governance", Control, ("control_id", "title"), "control_id", description="Framework-specific control requirements and testing anchors."),
    AssetSpec("control_metadata", "Control Metadata", "governance", ControlMetadata, ("control_id", "source_reference"), "id", description="Paraphrased requirement guidance, AWS angle, and collector hints."),
    AssetSpec("unified_controls", "Unified Controls", "governance", UnifiedControl, ("code", "name"), "code", description="Reusable implementation controls that map many standards into one baseline."),
    AssetSpec("unified_control_mappings", "Unified Control Mappings", "governance", UnifiedControlMapping, ("id", "approval_status"), "id", description="Traceability links from source controls into the unified control baseline."),
    AssetSpec("reference_documents", "Reference Documents", "governance", ReferenceDocument, ("document_key", "name"), "document_key", description="Implementation guides, authoritative references, and cross-framework source documents."),
    AssetSpec("unified_control_references", "Unified Control References", "governance", UnifiedControlReference, ("id", "relationship_type"), "id", description="Explicit links from unified controls to guides, frameworks, and imported source requirements."),
    AssetSpec("ai_knowledge_packs", "AI Knowledge Packs", "governance", AIKnowledgePack, ("pack_code", "name"), "pack_code", description="Governed, inspectable, reusable compliance copilot packs."),
    AssetSpec("ai_knowledge_pack_versions", "AI Knowledge Pack Versions", "governance", AIKnowledgePackVersion, ("version_label", "status"), "id", description="Versioned pack behavior, contracts, and approval state."),
    AssetSpec("ai_knowledge_pack_tasks", "AI Knowledge Pack Tasks", "governance", AIKnowledgePackTask, ("task_key", "name"), "task_key", description="Reusable governed tasks exposed by a knowledge pack version."),
    AssetSpec("ai_knowledge_pack_references", "AI Knowledge Pack References", "governance", AIKnowledgePackReference, ("id", "use_mode"), "id", description="Reference and scope bindings used by a knowledge pack version."),
    AssetSpec("ai_knowledge_pack_eval_cases", "AI Knowledge Pack Eval Cases", "governance", AIKnowledgePackEvalCase, ("case_code", "name"), "case_code", description="Pack-specific evaluation cases and assertions."),
    AssetSpec("evidence_plans", "Evidence Plans", "governance", EvidenceCollectionPlan, ("plan_code", "name"), "plan_code", description="Governed plans describing how control evidence is collected and reviewed."),
    AssetSpec("organizations", "Organizations", "portfolio", Organization, ("code", "name"), "code", description="Enterprise tenants scoped inside the workspace."),
    AssetSpec("identity_principals", "Identity Principals", "portfolio", IdentityPrincipal, ("principal_key", "display_name"), "principal_key", description="Users, service accounts, or groups that can receive scoped governance roles."),
    AssetSpec("access_roles", "Access Roles", "portfolio", AccessRole, ("role_key", "name"), "role_key", description="Reusable RBAC roles with explicit permission bundles and approval semantics."),
    AssetSpec("role_assignments", "Role Assignments", "portfolio", RoleAssignment, ("id", "approval_status"), "id", description="Scoped role grants linking principals to organizations, business units, products, and bindings."),
    AssetSpec("business_units", "Business Units", "portfolio", BusinessUnit, ("code", "name"), "code", description="Business units used to scope ownership, reporting, and remediation responsibility."),
    AssetSpec("products", "Products", "portfolio", Product, ("code", "name"), "code", description="Products or services that inherit and implement controls."),
    AssetSpec("product_flavors", "Product Flavors", "portfolio", ProductFlavor, ("code", "name"), "code", description="Variants of a product with distinct compliance, region, or runtime traits."),
    AssetSpec("assets", "Assets", "portfolio", Asset, ("asset_code", "name"), "asset_code", description="Applications, services, data stores, and other governed assets in scope."),
    AssetSpec("framework_bindings", "Framework Bindings", "portfolio", OrganizationFrameworkBinding, ("binding_code", "name"), "binding_code", description="An organization/framework scope used for assessments and evidence runs."),
    AssetSpec("control_implementations", "Control Implementations", "portfolio", ControlImplementation, ("implementation_code", "title"), "id", description="How a given organization or product implements a control in practice."),
    AssetSpec("product_control_profiles", "Product Control Profiles", "portfolio", ProductControlProfile, ("id", "assessment_mode"), "id", description="Applicability, maturity, and autonomy profile of a control for a product or flavor."),
    AssetSpec("threats", "Threats", "portfolio", Threat, ("threat_code", "name"), "threat_code", description="Threat catalog entries linked to enterprise risks."),
    AssetSpec("risks", "Risks", "portfolio", Risk, ("id", "title"), "id", description="Enterprise risks that connect assets, threats, controls, and treatments."),
    AssetSpec("risk_treatments", "Risk Treatments", "portfolio", RiskTreatment, ("id", "treatment_type"), "id", description="Planned or active mitigations linked to risks and controls."),
    AssetSpec("findings", "Findings", "portfolio", Finding, ("id", "title"), "id", artifact=True, description="Issues and findings produced by assessments, reviews, or external sources."),
    AssetSpec("action_items", "Action Items", "portfolio", ActionItem, ("id", "title"), "id", artifact=True, description="Tracked remediation and follow-up actions with ownership and due dates."),
    AssetSpec("aws_profiles", "AWS CLI Profiles", "integrations", AwsCliProfile, ("profile_name", "sso_account_id"), "profile_name", description="Locally managed AWS CLI SSO profile metadata used for evidence operations."),
    AssetSpec("aws_targets", "AWS Evidence Targets", "integrations", AwsEvidenceTarget, ("target_code", "name"), "target_code", description="Account, region, and profile targeting for evidence collection."),
    AssetSpec("confluence_connections", "Confluence Connections", "integrations", ConfluenceConnection, ("name", "space_key"), "name", description="Governed publication destinations for evidence and reports."),
    AssetSpec("secret_metadata", "Secret Metadata", "integrations", SecretMetadata, ("name", "secret_type"), "name", description="Secret inventory and secure connector metadata tracked by the platform."),
    AssetSpec("feature_flags", "Feature Flags", "integrations", FeatureFlag, ("flag_key", "name"), "flag_key", description="Controlled rollout switches for dark launches, canaries, and operational toggles."),
    AssetSpec("circuit_breakers", "Circuit Breakers", "integrations", CircuitBreakerState, ("integration_key", "state"), "integration_key", description="Resilience state for external integrations and protected call paths."),
    AssetSpec("external_call_ledger", "External Call Ledger", "integrations", ExternalCallLedger, ("operation", "status"), "id", artifact=True, description="Idempotency and outcome ledger for external integration calls."),
    AssetSpec("script_modules", "Assessment Script Modules", "integrations", AssessmentScriptModule, ("module_code", "name"), "module_code", description="External Python modules registered as reusable assessment collectors."),
    AssetSpec("script_bindings", "Assessment Script Bindings", "integrations", AssessmentScriptBinding, ("binding_code", "name"), "binding_code", description="Bindings that attach external scripts to evidence or assessment plans."),
    AssetSpec("framework_import_batches", "Framework Import Batches", "imports", FrameworkImportBatch, ("import_code", "name"), "import_code", artifact=True, description="Import jobs that ingest framework content from external sources."),
    AssetSpec("imported_requirements", "Imported Requirements", "imports", ImportedRequirement, ("external_id", "title"), "id", artifact=True, description="Imported source rows with mapping status and provenance."),
    AssetSpec("imported_requirement_references", "Imported Requirement References", "imports", ImportedRequirementReference, ("id", "relationship_type"), "id", artifact=True, description="Reference links captured from imported source rows, preserving the original source taxonomy."),
    AssetSpec("questionnaires", "Customer Questionnaires", "artifacts", CustomerQuestionnaire, ("name", "customer_name"), "id", artifact=True, description="Stored customer questionnaires answered from implementation narratives."),
    AssetSpec("questionnaire_items", "Questionnaire Items", "artifacts", CustomerQuestionnaireItem, ("external_id", "question_text"), "id", artifact=True, description="Individual customer questions and drafted answers."),
    AssetSpec("evidence_items", "Evidence Items", "artifacts", EvidenceItem, ("id", "summary"), "id", artifact=True, description="Collected or imported evidence items, encrypted payloads, and review state."),
    AssetSpec("assessment_runs", "Assessment Runs", "artifacts", AssessmentRun, ("id", "status"), "id", artifact=True, description="Executed assessments, their scores, and approval state."),
    AssetSpec("assessment_schedules", "Assessment Schedules", "operations", AssessmentSchedule, ("name", "cadence"), "id", description="Recurring assessment schedules and scoped runtime settings."),
    AssetSpec("script_runs", "Assessment Script Runs", "operations", AssessmentScriptRun, ("id", "status"), "id", artifact=True, description="Execution history for external assessment script modules."),
    AssetSpec("external_links", "External Artifact Links", "artifacts", ExternalArtifactLink, ("title", "external_key"), "id", artifact=True, description="Links to external systems, artifacts, or uploads tied to a record."),
    AssetSpec("ai_suggestions", "AI Suggestions", "operations", AISuggestion, ("id", "suggestion_type"), "id", description="Governed AI outputs awaiting review or promotion."),
    AssetSpec("lifecycle_events", "Lifecycle Events", "operations", LifecycleEvent, ("entity_type", "to_state"), "id", artifact=True, description="Lifecycle evidence showing how controls, artifacts, and reviews evolved."),
    AssetSpec("system_settings", "System Settings", "operations", SystemSetting, ("setting_key", "description"), "setting_key", description="Workspace preferences, runtime toggles, and operator defaults."),
    AssetSpec("user_feedback_messages", "User Feedback Mailbox", "operations", UserFeedbackMessage, ("subject", "status"), "id", artifact=True, description="Suggestions, pain points, and improvement requests submitted by workspace users."),
)

SPECS_BY_KEY = {item.key: item for item in ASSET_SPECS}
SPECS_BY_TABLE = {item.model.__tablename__: item for item in ASSET_SPECS}


class AssetCatalogService:
    def __init__(self, session):
        self.session = session

    def asset_types(self) -> list[dict]:
        rows = []
        for spec in ASSET_SPECS:
            rows.append(
                {
                    "key": spec.key,
                    "label": spec.label,
                    "family": spec.family,
                    "artifact": spec.artifact,
                    "count": self.session.scalar(select(func.count()).select_from(spec.model)) or 0,
                    "description": spec.description,
                }
            )
        return rows

    def families(self) -> list[str]:
        return sorted({item.family for item in ASSET_SPECS})

    def asset_types_for_family(self, family: str | None = None) -> list[dict]:
        rows = self.asset_types()
        if family:
            rows = [item for item in rows if item["family"] == family]
        return rows

    def list_assets(self, asset_type: str, limit: int = 200, search: str = "") -> list[dict]:
        spec = self._spec(asset_type)
        query = select(spec.model)
        order_field = spec.order_field or self._primary_key_name(spec.model)
        if order_field and hasattr(spec.model, order_field):
            query = query.order_by(getattr(spec.model, order_field))
        rows = self.session.scalars(query.limit(limit)).all()
        rendered = [self._list_row(spec, item) for item in rows]
        if search.strip():
            needle = search.strip().lower()
            rendered = [
                item
                for item in rendered
                if any(needle in str(value).lower() for value in item.values() if value not in {None, ""})
            ]
        return rendered

    def reference_options(self, asset_type: str) -> dict[str, list[dict]]:
        spec = self._spec(asset_type)
        options = {}
        for field in self.field_schema(asset_type):
            if not field["foreign_asset_type"]:
                continue
            ref_spec = self._spec(field["foreign_asset_type"])
            rows = self.session.scalars(select(ref_spec.model).limit(500)).all()
            options[field["name"]] = [
                {
                    "value": self._primary_value(item),
                    "label": self._display_label(ref_spec, item),
                }
                for item in rows
            ]
        return options

    def field_schema(self, asset_type: str) -> list[dict]:
        spec = self._spec(asset_type)
        mapper = sa_inspect(spec.model)
        rows = []
        for column in mapper.columns:
            python_type = self._python_type_name(column.type)
            foreign_asset_type = ""
            if column.foreign_keys:
                fk = next(iter(column.foreign_keys))
                foreign_asset_type = SPECS_BY_TABLE.get(fk.column.table.name, AssetSpec("", "", "", object, tuple())).key
            rows.append(
                {
                    "name": column.key,
                    "label": column.key.replace("_", " ").title(),
                    "type": python_type,
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "editable": not column.primary_key and column.key not in {"created_at", "updated_at"},
                    "required_on_create": (not column.nullable) and column.default is None and not column.primary_key,
                    "foreign_asset_type": foreign_asset_type,
                    "multiline": self._is_multiline(column.key, python_type),
                }
            )
        return rows

    def get_asset(self, asset_type: str, identifier: Any):
        spec = self._spec(asset_type)
        value = self._coerce_identifier(spec.model, identifier)
        return self.session.get(spec.model, value)

    def asset_payload(self, asset_type: str, identifier: Any) -> dict:
        spec = self._spec(asset_type)
        instance = self.get_asset(asset_type, identifier)
        if instance is None:
            raise ValueError(f"{spec.label.rstrip('s')} not found: {identifier}")
        payload = {column.key: self._serialize_value(getattr(instance, column.key)) for column in sa_inspect(spec.model).columns}
        payload["_asset_type"] = spec.key
        payload["_label"] = self._display_label(spec, instance)
        if spec.key == "evidence_items":
            try:
                payload["_decrypted_payload"] = EvidenceService(self.session).decrypt_payload(instance)
            except Exception as exc:
                payload["_decrypted_payload_error"] = str(exc)
        return payload

    def create_asset(self, asset_type: str, values: dict[str, Any]):
        spec = self._spec(asset_type)
        payload = self._prepare_values(asset_type, values, creating=True)
        instance = spec.model(**payload)
        self.session.add(instance)
        self.session.flush()
        audit_event(
            action="asset_created",
            actor="asset_catalog",
            target_type=asset_type,
            target_id=self._primary_value(instance),
            status="success",
            details={"label": self._display_label(spec, instance)},
        )
        return instance

    def update_asset(self, asset_type: str, identifier: Any, values: dict[str, Any]):
        spec = self._spec(asset_type)
        instance = self.get_asset(asset_type, identifier)
        if instance is None:
            raise ValueError(f"{spec.label.rstrip('s')} not found: {identifier}")
        payload = self._prepare_values(asset_type, values, creating=False)
        for key, value in payload.items():
            setattr(instance, key, value)
        self.session.flush()
        audit_event(
            action="asset_updated",
            actor="asset_catalog",
            target_type=asset_type,
            target_id=self._primary_value(instance),
            status="success",
            details={"updated_fields": sorted(payload.keys()), "label": self._display_label(spec, instance)},
        )
        return instance

    def delete_asset(self, asset_type: str, identifier: Any) -> None:
        spec = self._spec(asset_type)
        instance = self.get_asset(asset_type, identifier)
        if instance is None:
            raise ValueError(f"{spec.label.rstrip('s')} not found: {identifier}")
        label = self._display_label(spec, instance)
        target_id = self._primary_value(instance)
        self.session.delete(instance)
        self.session.flush()
        audit_event(
            action="asset_deleted",
            actor="asset_catalog",
            target_type=asset_type,
            target_id=target_id,
            status="success",
            details={"label": label},
        )

    def _prepare_values(self, asset_type: str, values: dict[str, Any], creating: bool) -> dict[str, Any]:
        schema = {item["name"]: item for item in self.field_schema(asset_type)}
        payload = {}
        for key, raw_value in values.items():
            field = schema.get(key)
            if field is None:
                continue
            if not field["editable"]:
                continue
            if raw_value in {"", None} and field["type"] in {"int", "float", "datetime"}:
                if field.get("nullable", False):
                    payload[key] = None
                elif creating and field["required_on_create"]:
                    continue
                else:
                    continue
            payload[key] = self._coerce_field_value(field, raw_value)
        if creating:
            missing = [
                item["label"]
                for item in schema.values()
                if item["required_on_create"] and item["name"] not in payload
            ]
            if missing:
                raise ValueError("Missing required fields: " + ", ".join(missing))
        return payload

    def _list_row(self, spec: AssetSpec, instance) -> dict:
        payload = {"_id": self._primary_value(instance), "_label": self._display_label(spec, instance)}
        for field_name in spec.display_fields:
            payload[field_name] = self._serialize_value(getattr(instance, field_name, ""))
        for extra in self._extra_columns(spec):
            if extra in payload:
                continue
            payload[extra] = self._serialize_value(getattr(instance, extra, ""))
        return payload

    @staticmethod
    def _extra_columns(spec: AssetSpec) -> tuple[str, ...]:
        extras = {
            "frameworks": ("category", "source", "lifecycle_status"),
            "controls": ("evidence_query", "severity"),
            "unified_controls": ("domain", "family", "lifecycle_status"),
            "organizations": ("status",),
            "products": ("product_type", "deployment_model", "lifecycle_status"),
            "framework_bindings": ("aws_profile", "aws_region", "enabled"),
            "evidence_plans": ("scope_type", "execution_mode", "lifecycle_status"),
            "evidence_items": ("status", "lifecycle_status", "classification"),
            "assessment_runs": ("status", "review_status", "assurance_status", "score"),
            "assessment_schedules": ("cadence", "execution_mode", "enabled"),
            "aws_profiles": ("sso_region", "default_region", "last_validation_status"),
            "confluence_connections": ("auth_mode", "status", "last_test_status"),
            "framework_import_batches": ("status", "imported_count", "created_mappings"),
            "imported_requirements": ("source_reference", "import_action"),
            "script_modules": ("entrypoint_type", "working_directory", "lifecycle_status"),
            "script_bindings": ("action_type", "lifecycle_status"),
            "script_runs": ("status", "exit_code"),
        }
        return extras.get(spec.key, tuple())

    def _display_label(self, spec: AssetSpec, instance) -> str:
        parts = []
        for field_name in spec.display_fields:
            value = getattr(instance, field_name, "")
            if value:
                parts.append(str(value))
        if not parts:
            parts.append(str(self._primary_value(instance)))
        return " | ".join(parts[:3])

    @staticmethod
    def _primary_key_name(model: type) -> str:
        return sa_inspect(model).primary_key[0].key

    @staticmethod
    def _primary_value(instance) -> Any:
        mapper = sa_inspect(instance.__class__)
        return getattr(instance, mapper.primary_key[0].key)

    def _coerce_identifier(self, model: type, identifier: Any) -> Any:
        pk = sa_inspect(model).primary_key[0]
        field = {
            "name": pk.key,
            "type": self._python_type_name(pk.type),
            "nullable": False,
        }
        return self._coerce_field_value(field, identifier)

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    @staticmethod
    def _python_type_name(column_type) -> str:
        try:
            python_type = column_type.python_type
        except NotImplementedError:
            return "string"
        if python_type is bool:
            return "bool"
        if python_type is int:
            return "int"
        if python_type is float:
            return "float"
        if python_type is datetime:
            return "datetime"
        return "string"

    @staticmethod
    def _is_multiline(field_name: str, python_type: str) -> bool:
        return python_type == "string" and (
            field_name.endswith("_json")
            or field_name.endswith("_payload")
            or field_name.endswith("_text")
            or field_name.endswith("_notes")
            or field_name.endswith("_guidance")
            or field_name.endswith("_description")
            or field_name.endswith("_summary")
            or field_name.endswith("_query")
            or field_name.endswith("_links")
            or field_name.endswith("_plan")
            or field_name.endswith("_doc")
            or field_name in {"description", "notes", "summary", "payload_json", "response_text", "prompt_text", "rationale"}
        )

    @staticmethod
    def _coerce_field_value(field: dict, raw_value: Any) -> Any:
        if raw_value == "" and field.get("nullable", False):
            return None
        if field["type"] == "bool":
            if isinstance(raw_value, bool):
                return raw_value
            return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}
        if field["type"] == "int":
            if raw_value in {"", None}:
                return None if field.get("nullable", False) else 0
            return int(raw_value)
        if field["type"] == "float":
            if raw_value in {"", None}:
                return None if field.get("nullable", False) else 0.0
            return float(raw_value)
        if field["type"] == "datetime":
            if raw_value in {"", None}:
                return None if field.get("nullable", False) else datetime.utcnow()
            if isinstance(raw_value, datetime):
                return raw_value
            return datetime.fromisoformat(str(raw_value))
        return str(raw_value) if raw_value is not None else ""

    def _spec(self, asset_type: str) -> AssetSpec:
        spec = SPECS_BY_KEY.get(asset_type)
        if spec is None:
            raise ValueError(f"Unknown asset type: {asset_type}")
        return spec
