from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aws_local_audit.db import Base


class AuthorityDocument(Base):
    __tablename__ = "authority_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(100), default="")
    issuing_body: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(100), default="framework")
    jurisdiction: Mapped[str] = mapped_column(String(100), default="global")
    source_url: Mapped[str] = mapped_column(String(500), default="")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="draft")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    frameworks: Mapped[list["Framework"]] = relationship(back_populates="authority_document")


class Framework(Base):
    __tablename__ = "frameworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    authority_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("authority_documents.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(100), default="framework")
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(100), default="template")
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="draft")
    aws_profile: Mapped[str | None] = mapped_column(String(255), nullable=True)
    aws_region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    controls: Mapped[list["Control"]] = relationship(back_populates="framework", cascade="all, delete-orphan")
    schedules: Mapped[list["AssessmentSchedule"]] = relationship(back_populates="framework", cascade="all, delete-orphan")
    authority_document: Mapped["AuthorityDocument"] = relationship(back_populates="frameworks")
    organization_bindings: Mapped[list["OrganizationFrameworkBinding"]] = relationship(
        back_populates="framework", cascade="all, delete-orphan"
    )
    unified_mappings: Mapped[list["UnifiedControlMapping"]] = relationship(
        back_populates="framework", cascade="all, delete-orphan"
    )
    confluence_connections: Mapped[list["ConfluenceConnection"]] = relationship(back_populates="framework")
    evidence_plans: Mapped[list["EvidenceCollectionPlan"]] = relationship(back_populates="framework")
    import_batches: Mapped[list["FrameworkImportBatch"]] = relationship(
        back_populates="framework", cascade="all, delete-orphan"
    )


class Control(Base):
    __tablename__ = "controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("frameworks.id"))
    control_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    evidence_query: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(32), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    framework: Mapped["Framework"] = relationship(back_populates="controls")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="control", cascade="all, delete-orphan")
    metadata_entry: Mapped["ControlMetadata"] = relationship(
        back_populates="control", cascade="all, delete-orphan", uselist=False
    )
    unified_mappings: Mapped[list["UnifiedControlMapping"]] = relationship(
        back_populates="control", cascade="all, delete-orphan"
    )
    evidence_plans: Mapped[list["EvidenceCollectionPlan"]] = relationship(back_populates="control")
    implementations: Mapped[list["ControlImplementation"]] = relationship(
        back_populates="control", cascade="all, delete-orphan"
    )
    assessment_items: Mapped[list["AssessmentRunItem"]] = relationship(back_populates="control")
    ai_suggestions: Mapped[list["AISuggestion"]] = relationship(back_populates="control", cascade="all, delete-orphan")
    aws_evidence_targets: Mapped[list["AwsEvidenceTarget"]] = relationship(back_populates="control")
    imported_requirements: Mapped[list["ImportedRequirement"]] = relationship(
        back_populates="control", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("framework_id", "control_id", name="uq_framework_control_id"),)


class ControlMetadata(Base):
    __tablename__ = "control_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("controls.id"), unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    aws_guidance: Mapped[str] = mapped_column(Text, default="")
    check_type: Mapped[str] = mapped_column(String(32), default="manual")
    boto3_check: Mapped[str] = mapped_column(Text, default="")
    boto3_services_json: Mapped[str] = mapped_column(Text, default="[]")
    source_reference: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    control: Mapped["Control"] = relationship(back_populates="metadata_entry")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    framework_bindings: Mapped[list["OrganizationFrameworkBinding"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    business_units: Mapped[list["BusinessUnit"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    principals: Mapped[list["IdentityPrincipal"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    role_assignments: Mapped[list["RoleAssignment"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    assets: Mapped[list["Asset"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    threats: Mapped[list["Threat"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    risks: Mapped[list["Risk"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    implementations: Mapped[list["ControlImplementation"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    product_control_profiles: Mapped[list["ProductControlProfile"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    questionnaires: Mapped[list["CustomerQuestionnaire"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    external_links: Mapped[list["ExternalArtifactLink"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    ai_suggestions: Mapped[list["AISuggestion"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    aws_evidence_targets: Mapped[list["AwsEvidenceTarget"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class BusinessUnit(Base):
    __tablename__ = "business_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="business_units")
    products: Mapped[list["Product"]] = relationship(back_populates="business_unit")
    assets: Mapped[list["Asset"]] = relationship(back_populates="business_unit")
    role_assignments: Mapped[list["RoleAssignment"]] = relationship(back_populates="business_unit")
    risks: Mapped[list["Risk"]] = relationship(back_populates="business_unit")
    findings: Mapped[list["Finding"]] = relationship(back_populates="business_unit")
    action_items: Mapped[list["ActionItem"]] = relationship(back_populates="business_unit")

    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_org_business_unit_code"),)


class OrganizationFrameworkBinding(Base):
    __tablename__ = "organization_framework_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("frameworks.id"), index=True)
    binding_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    aws_profile: Mapped[str] = mapped_column(String(255))
    aws_region: Mapped[str] = mapped_column(String(64))
    aws_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confluence_connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("confluence_connections.id"), nullable=True, index=True
    )
    confluence_parent_page_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="framework_bindings")
    framework: Mapped["Framework"] = relationship(back_populates="organization_bindings")
    confluence_connection: Mapped["ConfluenceConnection"] = relationship(back_populates="bindings")
    role_assignments: Mapped[list["RoleAssignment"]] = relationship(back_populates="framework_binding")
    aws_evidence_targets: Mapped[list["AwsEvidenceTarget"]] = relationship(
        back_populates="framework_binding", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "framework_id",
            "aws_profile",
            "aws_region",
            name="uq_org_framework_profile_region",
        ),
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    product_type: Mapped[str] = mapped_column(String(64), default="service")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active")
    deployment_model: Mapped[str] = mapped_column(String(64), default="")
    data_classification: Mapped[str] = mapped_column(String(64), default="")
    owner: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="products")
    business_unit: Mapped["BusinessUnit"] = relationship(back_populates="products")
    role_assignments: Mapped[list["RoleAssignment"]] = relationship(back_populates="product")
    flavors: Mapped[list["ProductFlavor"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    implementations: Mapped[list["ControlImplementation"]] = relationship(back_populates="product")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="product")
    assessment_runs: Mapped[list["AssessmentRun"]] = relationship(back_populates="product")
    assets: Mapped[list["Asset"]] = relationship(back_populates="product")
    control_profiles: Mapped[list["ProductControlProfile"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    questionnaires: Mapped[list["CustomerQuestionnaire"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    aws_evidence_targets: Mapped[list["AwsEvidenceTarget"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_org_product_code"),)


class IdentityPrincipal(Base):
    __tablename__ = "identity_principals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    principal_key: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    principal_type: Mapped[str] = mapped_column(String(32), default="human")
    email: Mapped[str] = mapped_column(String(255), default="")
    external_id: Mapped[str] = mapped_column(String(255), default="")
    source_system: Mapped[str] = mapped_column(String(100), default="local")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="principals")
    role_assignments: Mapped[list["RoleAssignment"]] = relationship(
        back_populates="principal", cascade="all, delete-orphan"
    )
    workspace_credentials: Mapped[list["WorkspaceCredential"]] = relationship(
        back_populates="principal", cascade="all, delete-orphan"
    )


class AccessRole(Base):
    __tablename__ = "access_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    scope_type: Mapped[str] = mapped_column(String(64), default="organization")
    permissions_json: Mapped[str] = mapped_column(Text, default="[]")
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignments: Mapped[list["RoleAssignment"]] = relationship(back_populates="role", cascade="all, delete-orphan")


class RoleAssignment(Base):
    __tablename__ = "role_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    principal_id: Mapped[int] = mapped_column(ForeignKey("identity_principals.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("access_roles.id"), index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    framework_binding_id: Mapped[int | None] = mapped_column(
        ForeignKey("organization_framework_bindings.id"), nullable=True, index=True
    )
    assignment_source: Mapped[str] = mapped_column(String(64), default="manual")
    approval_status: Mapped[str] = mapped_column(String(32), default="approved")
    status: Mapped[str] = mapped_column(String(32), default="active")
    assigned_by: Mapped[str] = mapped_column(String(255), default="")
    approved_by: Mapped[str] = mapped_column(String(255), default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    principal: Mapped["IdentityPrincipal"] = relationship(back_populates="role_assignments")
    role: Mapped["AccessRole"] = relationship(back_populates="assignments")
    organization: Mapped["Organization"] = relationship(back_populates="role_assignments")
    business_unit: Mapped["BusinessUnit"] = relationship(back_populates="role_assignments")
    product: Mapped["Product"] = relationship(back_populates="role_assignments")
    framework_binding: Mapped["OrganizationFrameworkBinding"] = relationship(back_populates="role_assignments")


class WorkspaceCredential(Base):
    __tablename__ = "workspace_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    principal_id: Mapped[int] = mapped_column(ForeignKey("identity_principals.id"), unique=True, index=True)
    auth_mode: Mapped[str] = mapped_column(String(32), default="local_password")
    password_salt: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    password_iterations: Mapped[int] = mapped_column(Integer, default=390000)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    principal: Mapped["IdentityPrincipal"] = relationship(back_populates="workspace_credentials")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    asset_code: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(255))
    asset_type: Mapped[str] = mapped_column(String(64), default="application")
    criticality: Mapped[str] = mapped_column(String(32), default="medium")
    data_classification: Mapped[str] = mapped_column(String(64), default="")
    owner: Mapped[str] = mapped_column(String(255), default="")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active")
    attributes_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="assets")
    business_unit: Mapped["BusinessUnit"] = relationship(back_populates="assets")
    product: Mapped["Product"] = relationship(back_populates="assets")
    risks: Mapped[list["Risk"]] = relationship(back_populates="asset")

    __table_args__ = (UniqueConstraint("organization_id", "asset_code", name="uq_org_asset_code"),)


class Threat(Base):
    __tablename__ = "threats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    threat_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(100), default="catalog")
    severity: Mapped[str] = mapped_column(String(32), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="threats")
    risks: Mapped[list["Risk"]] = relationship(back_populates="threat")


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id"), nullable=True, index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    threat_id: Mapped[int | None] = mapped_column(ForeignKey("threats.id"), nullable=True, index=True)
    unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="identified")
    likelihood: Mapped[float] = mapped_column(Float, default=0.0)
    impact: Mapped[float] = mapped_column(Float, default=0.0)
    inherent_score: Mapped[float] = mapped_column(Float, default=0.0)
    residual_score: Mapped[float] = mapped_column(Float, default=0.0)
    owner: Mapped[str] = mapped_column(String(255), default="")
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="risks")
    business_unit: Mapped["BusinessUnit"] = relationship(back_populates="risks")
    asset: Mapped["Asset"] = relationship(back_populates="risks")
    threat: Mapped["Threat"] = relationship(back_populates="risks")
    unified_control: Mapped["UnifiedControl"] = relationship()
    treatments: Mapped[list["RiskTreatment"]] = relationship(back_populates="risk", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="risk")
    action_items: Mapped[list["ActionItem"]] = relationship(back_populates="risk")


class RiskTreatment(Base):
    __tablename__ = "risk_treatments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id"), index=True)
    unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    control_implementation_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_implementations.id"), nullable=True, index=True
    )
    treatment_type: Mapped[str] = mapped_column(String(32), default="mitigate")
    status: Mapped[str] = mapped_column(String(32), default="planned")
    owner: Mapped[str] = mapped_column(String(255), default="")
    target_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    plan: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    risk: Mapped["Risk"] = relationship(back_populates="treatments")
    unified_control: Mapped["UnifiedControl"] = relationship()
    control_implementation: Mapped["ControlImplementation"] = relationship()


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id"), nullable=True, index=True)
    risk_id: Mapped[int | None] = mapped_column(ForeignKey("risks.id"), nullable=True, index=True)
    assessment_run_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_runs.id"), nullable=True, index=True)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    evidence_item_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_items.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(64), default="assessment")
    severity: Mapped[str] = mapped_column(String(32), default="medium")
    status: Mapped[str] = mapped_column(String(32), default="open")
    owner: Mapped[str] = mapped_column(String(255), default="")
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="findings")
    business_unit: Mapped["BusinessUnit"] = relationship(back_populates="findings")
    risk: Mapped["Risk"] = relationship(back_populates="findings")
    assessment_run: Mapped["AssessmentRun"] = relationship()
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship()
    unified_control: Mapped["UnifiedControl"] = relationship()
    evidence_item: Mapped["EvidenceItem"] = relationship()
    action_items: Mapped[list["ActionItem"]] = relationship(back_populates="finding", cascade="all, delete-orphan")


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id"), nullable=True, index=True)
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("findings.id"), nullable=True, index=True)
    risk_id: Mapped[int | None] = mapped_column(ForeignKey("risks.id"), nullable=True, index=True)
    control_implementation_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_implementations.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    status: Mapped[str] = mapped_column(String(32), default="open")
    owner: Mapped[str] = mapped_column(String(255), default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="action_items")
    business_unit: Mapped["BusinessUnit"] = relationship(back_populates="action_items")
    finding: Mapped["Finding"] = relationship(back_populates="action_items")
    risk: Mapped["Risk"] = relationship(back_populates="action_items")
    control_implementation: Mapped["ControlImplementation"] = relationship()


class ProductFlavor(Base):
    __tablename__ = "product_flavors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    deployment_model: Mapped[str] = mapped_column(String(64), default="")
    hosting_model: Mapped[str] = mapped_column(String(64), default="")
    region_scope: Mapped[str] = mapped_column(String(128), default="")
    customer_segment: Mapped[str] = mapped_column(String(128), default="")
    attributes_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="flavors")
    implementations: Mapped[list["ControlImplementation"]] = relationship(back_populates="product_flavor")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="product_flavor")
    assessment_runs: Mapped[list["AssessmentRun"]] = relationship(back_populates="product_flavor")
    control_profiles: Mapped[list["ProductControlProfile"]] = relationship(
        back_populates="product_flavor", cascade="all, delete-orphan"
    )
    questionnaires: Mapped[list["CustomerQuestionnaire"]] = relationship(
        back_populates="product_flavor", cascade="all, delete-orphan"
    )
    aws_evidence_targets: Mapped[list["AwsEvidenceTarget"]] = relationship(
        back_populates="product_flavor", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("product_id", "code", name="uq_product_flavor_code"),)


class UnifiedControl(Base):
    __tablename__ = "unified_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(100), default="")
    family: Mapped[str] = mapped_column(String(100), default="")
    control_type: Mapped[str] = mapped_column(String(64), default="")
    default_severity: Mapped[str] = mapped_column(String(32), default="medium")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="draft")
    implementation_guidance: Mapped[str] = mapped_column(Text, default="")
    test_guidance: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mappings: Mapped[list["UnifiedControlMapping"]] = relationship(
        back_populates="unified_control", cascade="all, delete-orphan"
    )
    implementations: Mapped[list["ControlImplementation"]] = relationship(
        back_populates="unified_control", cascade="all, delete-orphan"
    )
    assessment_items: Mapped[list["AssessmentRunItem"]] = relationship(back_populates="unified_control")
    ai_suggestions: Mapped[list["AISuggestion"]] = relationship(
        back_populates="unified_control", cascade="all, delete-orphan"
    )
    evidence_plans: Mapped[list["EvidenceCollectionPlan"]] = relationship(back_populates="unified_control")
    aws_evidence_targets: Mapped[list["AwsEvidenceTarget"]] = relationship(back_populates="unified_control")
    reference_links: Mapped[list["UnifiedControlReference"]] = relationship(
        back_populates="unified_control", cascade="all, delete-orphan"
    )


class UnifiedControlMapping(Base):
    __tablename__ = "unified_control_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unified_control_id: Mapped[int] = mapped_column(ForeignKey("unified_controls.id"), index=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("frameworks.id"), index=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("controls.id"), index=True)
    mapping_type: Mapped[str] = mapped_column(String(32), default="mapped")
    rationale: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    inheritance_strategy: Mapped[str] = mapped_column(String(64), default="manual_review")
    approval_status: Mapped[str] = mapped_column(String(32), default="proposed")
    reviewed_by: Mapped[str] = mapped_column(String(255), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    unified_control: Mapped["UnifiedControl"] = relationship(back_populates="mappings")
    framework: Mapped["Framework"] = relationship(back_populates="unified_mappings")
    control: Mapped["Control"] = relationship(back_populates="unified_mappings")

    __table_args__ = (UniqueConstraint("unified_control_id", "control_id", name="uq_unified_control_control"),)


class EvidenceCollectionPlan(Base):
    __tablename__ = "evidence_collection_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    unified_control_id: Mapped[int | None] = mapped_column(
        ForeignKey("unified_controls.id"), nullable=True, index=True
    )
    scope_type: Mapped[str] = mapped_column(String(32), default="product")
    execution_mode: Mapped[str] = mapped_column(String(32), default="automated")
    collector_key: Mapped[str] = mapped_column(String(255), default="")
    evidence_type: Mapped[str] = mapped_column(String(64), default="api_payload")
    instructions: Mapped[str] = mapped_column(Text, default="")
    expected_artifacts_json: Mapped[str] = mapped_column(Text, default="[]")
    review_frequency: Mapped[str] = mapped_column(String(64), default="")
    minimum_freshness_days: Mapped[int] = mapped_column(Integer, default=30)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    framework: Mapped["Framework"] = relationship(back_populates="evidence_plans")
    control: Mapped["Control"] = relationship(back_populates="evidence_plans")
    unified_control: Mapped["UnifiedControl"] = relationship(back_populates="evidence_plans")
    assessment_script_bindings: Mapped[list["AssessmentScriptBinding"]] = relationship(
        back_populates="evidence_plan", cascade="all, delete-orphan"
    )


class ControlImplementation(Base):
    __tablename__ = "control_implementations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    product_flavor_id: Mapped[int | None] = mapped_column(ForeignKey("product_flavors.id"), nullable=True, index=True)
    unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    implementation_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    impl_aws: Mapped[str] = mapped_column(Text, default="")
    impl_onprem: Mapped[str] = mapped_column(Text, default="")
    impl_general: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    lifecycle: Mapped[str] = mapped_column(String(64), default="design")
    owner: Mapped[str] = mapped_column(String(255), default="")
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    frequency: Mapped[str] = mapped_column(String(64), default="")
    test_plan: Mapped[str] = mapped_column(Text, default="")
    evidence_links: Mapped[str] = mapped_column(Text, default="")
    jira_key: Mapped[str] = mapped_column(String(100), default="")
    servicenow_ticket: Mapped[str] = mapped_column(String(100), default="")
    design_doc: Mapped[str] = mapped_column(String(500), default="")
    blockers: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="implementations")
    product: Mapped["Product"] = relationship(back_populates="implementations")
    product_flavor: Mapped["ProductFlavor"] = relationship(back_populates="implementations")
    unified_control: Mapped["UnifiedControl"] = relationship(back_populates="implementations")
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship(back_populates="implementations")
    product_control_profiles: Mapped[list["ProductControlProfile"]] = relationship(
        back_populates="control_implementation"
    )
    external_links: Mapped[list["ExternalArtifactLink"]] = relationship(
        back_populates="control_implementation", cascade="all, delete-orphan"
    )
    assessment_items: Mapped[list["AssessmentRunItem"]] = relationship(back_populates="control_implementation")
    ai_suggestions: Mapped[list["AISuggestion"]] = relationship(
        back_populates="control_implementation", cascade="all, delete-orphan"
    )


class AwsEvidenceTarget(Base):
    __tablename__ = "aws_evidence_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    framework_binding_id: Mapped[int | None] = mapped_column(
        ForeignKey("organization_framework_bindings.id"), nullable=True, index=True
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    product_flavor_id: Mapped[int | None] = mapped_column(ForeignKey("product_flavors.id"), nullable=True, index=True)
    unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    target_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    aws_profile: Mapped[str] = mapped_column(String(255))
    aws_account_id: Mapped[str] = mapped_column(String(64), default="")
    role_name: Mapped[str] = mapped_column(String(255), default="")
    regions_json: Mapped[str] = mapped_column(Text, default="[]")
    execution_mode: Mapped[str] = mapped_column(String(32), default="aws_sso_login")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="aws_evidence_targets")
    framework_binding: Mapped["OrganizationFrameworkBinding"] = relationship(back_populates="aws_evidence_targets")
    product: Mapped["Product"] = relationship(back_populates="aws_evidence_targets")
    product_flavor: Mapped["ProductFlavor"] = relationship(back_populates="aws_evidence_targets")
    unified_control: Mapped["UnifiedControl"] = relationship(back_populates="aws_evidence_targets")
    control: Mapped["Control"] = relationship()


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    product_flavor_id: Mapped[int | None] = mapped_column(ForeignKey("product_flavors.id"), nullable=True, index=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("frameworks.id"))
    control_id: Mapped[int] = mapped_column(ForeignKey("controls.id"))
    evidence_key: Mapped[str] = mapped_column(String(120), default="", index=True)
    version_label: Mapped[str] = mapped_column(String(64), default="v1")
    status: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(String(500))
    payload_json: Mapped[str] = mapped_column(Text)
    payload_storage_mode: Mapped[str] = mapped_column(String(32), default="plaintext")
    payload_digest: Mapped[str] = mapped_column(String(128), default="")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="collected")
    classification: Mapped[str] = mapped_column(String(32), default="confidential")
    submitted_by: Mapped[str] = mapped_column(String(255), default="")
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confluence_page_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    organization: Mapped["Organization"] = relationship()
    product: Mapped["Product"] = relationship(back_populates="evidence_items")
    product_flavor: Mapped["ProductFlavor"] = relationship(back_populates="evidence_items")
    control: Mapped["Control"] = relationship(back_populates="evidence_items")
    assessment_items: Mapped[list["AssessmentRunItem"]] = relationship(back_populates="evidence_item")
    external_links: Mapped[list["ExternalArtifactLink"]] = relationship(
        back_populates="evidence_item", cascade="all, delete-orphan"
    )


class AssessmentRun(Base):
    __tablename__ = "assessment_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    product_flavor_id: Mapped[int | None] = mapped_column(ForeignKey("product_flavors.id"), nullable=True, index=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("frameworks.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    review_status: Mapped[str] = mapped_column(String(32), default="pending_review")
    assurance_status: Mapped[str] = mapped_column(String(32), default="draft")
    score: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    confluence_page_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    organization: Mapped["Organization"] = relationship()
    product: Mapped["Product"] = relationship(back_populates="assessment_runs")
    product_flavor: Mapped["ProductFlavor"] = relationship(back_populates="assessment_runs")
    framework: Mapped["Framework"] = relationship()
    run_items: Mapped[list["AssessmentRunItem"]] = relationship(
        back_populates="assessment_run", cascade="all, delete-orphan"
    )
    external_links: Mapped[list["ExternalArtifactLink"]] = relationship(
        back_populates="assessment_run", cascade="all, delete-orphan"
    )


class AssessmentRunItem(Base):
    __tablename__ = "assessment_run_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_run_id: Mapped[int] = mapped_column(ForeignKey("assessment_runs.id"), index=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("frameworks.id"), index=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("controls.id"), index=True)
    unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    control_implementation_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_implementations.id"), nullable=True, index=True
    )
    evidence_item_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_items.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    score: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(String(500), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    assessment_run: Mapped["AssessmentRun"] = relationship(back_populates="run_items")
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship(back_populates="assessment_items")
    unified_control: Mapped["UnifiedControl"] = relationship(back_populates="assessment_items")
    control_implementation: Mapped["ControlImplementation"] = relationship(back_populates="assessment_items")
    evidence_item: Mapped["EvidenceItem"] = relationship(back_populates="assessment_items")


class ProductControlProfile(Base):
    __tablename__ = "product_control_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product_flavor_id: Mapped[int | None] = mapped_column(ForeignKey("product_flavors.id"), nullable=True, index=True)
    unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    control_implementation_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_implementations.id"), nullable=True, index=True
    )
    applicability_status: Mapped[str] = mapped_column(String(32), default="applicable")
    implementation_status: Mapped[str] = mapped_column(String(32), default="planned")
    assessment_mode: Mapped[str] = mapped_column(String(32), default="manual")
    assurance_status: Mapped[str] = mapped_column(String(32), default="not_assured")
    maturity_level: Mapped[int] = mapped_column(Integer, default=1)
    maturity_governance: Mapped[int] = mapped_column(Integer, default=1)
    maturity_implementation: Mapped[int] = mapped_column(Integer, default=1)
    maturity_observability: Mapped[int] = mapped_column(Integer, default=1)
    maturity_automation: Mapped[int] = mapped_column(Integer, default=1)
    maturity_assurance: Mapped[int] = mapped_column(Integer, default=1)
    autonomy_recommendation: Mapped[str] = mapped_column(String(64), default="manual_only")
    rationale: Mapped[str] = mapped_column(Text, default="")
    evidence_strategy: Mapped[str] = mapped_column(Text, default="")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="product_control_profiles")
    product: Mapped["Product"] = relationship(back_populates="control_profiles")
    product_flavor: Mapped["ProductFlavor"] = relationship(back_populates="control_profiles")
    unified_control: Mapped["UnifiedControl"] = relationship()
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship()
    control_implementation: Mapped["ControlImplementation"] = relationship(back_populates="product_control_profiles")


class CustomerQuestionnaire(Base):
    __tablename__ = "customer_questionnaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product_flavor_id: Mapped[int | None] = mapped_column(ForeignKey("product_flavors.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    customer_name: Mapped[str] = mapped_column(String(255), default="")
    source_type: Mapped[str] = mapped_column(String(32), default="csv")
    source_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    generated_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="questionnaires")
    product: Mapped["Product"] = relationship(back_populates="questionnaires")
    product_flavor: Mapped["ProductFlavor"] = relationship(back_populates="questionnaires")
    items: Mapped[list["CustomerQuestionnaireItem"]] = relationship(
        back_populates="questionnaire", cascade="all, delete-orphan"
    )


class CustomerQuestionnaireItem(Base):
    __tablename__ = "customer_questionnaire_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("customer_questionnaires.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(100), default="")
    section: Mapped[str] = mapped_column(String(255), default="")
    question_text: Mapped[str] = mapped_column(Text)
    normalized_question: Mapped[str] = mapped_column(Text, default="")
    mapped_unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    mapped_control_implementation_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_implementations.id"), nullable=True, index=True
    )
    suggested_answer: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    review_status: Mapped[str] = mapped_column(String(32), default="suggested")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questionnaire: Mapped["CustomerQuestionnaire"] = relationship(back_populates="items")
    mapped_unified_control: Mapped["UnifiedControl"] = relationship()
    mapped_control_implementation: Mapped["ControlImplementation"] = relationship()


class ExternalArtifactLink(Base):
    __tablename__ = "external_artifact_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    control_implementation_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_implementations.id"), nullable=True, index=True
    )
    evidence_item_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_items.id"), nullable=True, index=True)
    assessment_run_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_runs.id"), nullable=True, index=True)
    link_type: Mapped[str] = mapped_column(String(32), default="url")
    system_name: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    external_key: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="external_links")
    control_implementation: Mapped["ControlImplementation"] = relationship(back_populates="external_links")
    evidence_item: Mapped["EvidenceItem"] = relationship(back_populates="external_links")
    assessment_run: Mapped["AssessmentRun"] = relationship(back_populates="external_links")


class ReferenceDocument(Base):
    __tablename__ = "reference_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    short_name: Mapped[str] = mapped_column(String(120), default="")
    version: Mapped[str] = mapped_column(String(100), default="")
    issuing_body: Mapped[str] = mapped_column(String(255), default="")
    document_type: Mapped[str] = mapped_column(String(64), default="reference")
    jurisdiction: Mapped[str] = mapped_column(String(100), default="global")
    citation_format: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(500), default="")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    imported_requirement_links: Mapped[list["ImportedRequirementReference"]] = relationship(
        back_populates="reference_document", cascade="all, delete-orphan"
    )
    unified_control_links: Mapped[list["UnifiedControlReference"]] = relationship(
        back_populates="reference_document", cascade="all, delete-orphan"
    )
    knowledge_pack_links: Mapped[list["AIKnowledgePackReference"]] = relationship(
        back_populates="reference_document", cascade="all, delete-orphan"
    )


class FrameworkImportBatch(Base):
    __tablename__ = "framework_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("frameworks.id"), index=True)
    import_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    source_name: Mapped[str] = mapped_column(String(255), default="")
    source_type: Mapped[str] = mapped_column(String(32), default="csv")
    source_version: Mapped[str] = mapped_column(String(100), default="")
    source_url: Mapped[str] = mapped_column(String(500), default="")
    file_name: Mapped[str] = mapped_column(String(255), default="")
    sheet_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    initiated_by: Mapped[str] = mapped_column(String(255), default="")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    created_unified_controls: Mapped[int] = mapped_column(Integer, default=0)
    created_mappings: Mapped[int] = mapped_column(Integer, default=0)
    captured_suggestions: Mapped[int] = mapped_column(Integer, default=0)
    created_reference_documents: Mapped[int] = mapped_column(Integer, default=0)
    created_reference_links: Mapped[int] = mapped_column(Integer, default=0)
    column_mapping_json: Mapped[str] = mapped_column(Text, default="{}")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    framework: Mapped["Framework"] = relationship(back_populates="import_batches")
    imported_requirements: Mapped[list["ImportedRequirement"]] = relationship(
        back_populates="import_batch", cascade="all, delete-orphan"
    )


class ImportedRequirement(Base):
    __tablename__ = "imported_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("framework_import_batches.id"), index=True)
    framework_id: Mapped[int] = mapped_column(ForeignKey("frameworks.id"), index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    external_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    source_domain: Mapped[str] = mapped_column(String(255), default="")
    source_family: Mapped[str] = mapped_column(String(255), default="")
    source_section: Mapped[str] = mapped_column(String(255), default="")
    source_reference: Mapped[str] = mapped_column(String(255), default="")
    source_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    row_number: Mapped[int] = mapped_column(Integer, default=0)
    row_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    import_action: Mapped[str] = mapped_column(String(64), default="imported")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    import_batch: Mapped["FrameworkImportBatch"] = relationship(back_populates="imported_requirements")
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship(back_populates="imported_requirements")
    reference_links: Mapped[list["ImportedRequirementReference"]] = relationship(
        back_populates="imported_requirement", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("import_batch_id", "row_number", name="uq_import_batch_row_number"),)


class ImportedRequirementReference(Base):
    __tablename__ = "imported_requirement_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    imported_requirement_id: Mapped[int] = mapped_column(ForeignKey("imported_requirements.id"), index=True)
    reference_document_id: Mapped[int] = mapped_column(ForeignKey("reference_documents.id"), index=True)
    reference_code: Mapped[str] = mapped_column(String(255), default="")
    reference_text: Mapped[str] = mapped_column(Text, default="")
    relationship_type: Mapped[str] = mapped_column(String(64), default="mapped_requirement")
    raw_value: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    imported_requirement: Mapped["ImportedRequirement"] = relationship(back_populates="reference_links")
    reference_document: Mapped["ReferenceDocument"] = relationship(back_populates="imported_requirement_links")

    __table_args__ = (
        UniqueConstraint(
            "imported_requirement_id",
            "reference_document_id",
            "reference_code",
            "relationship_type",
            name="uq_imported_requirement_reference",
        ),
    )


class UnifiedControlReference(Base):
    __tablename__ = "unified_control_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unified_control_id: Mapped[int] = mapped_column(ForeignKey("unified_controls.id"), index=True)
    reference_document_id: Mapped[int] = mapped_column(ForeignKey("reference_documents.id"), index=True)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    imported_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("imported_requirements.id"), nullable=True, index=True
    )
    reference_code: Mapped[str] = mapped_column(String(255), default="")
    reference_text: Mapped[str] = mapped_column(Text, default="")
    relationship_type: Mapped[str] = mapped_column(String(64), default="mapped_requirement")
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    unified_control: Mapped["UnifiedControl"] = relationship(back_populates="reference_links")
    reference_document: Mapped["ReferenceDocument"] = relationship(back_populates="unified_control_links")
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship()
    imported_requirement: Mapped["ImportedRequirement"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "unified_control_id",
            "reference_document_id",
            "reference_code",
            "relationship_type",
            name="uq_unified_control_reference",
        ),
    )


class AIKnowledgePack(Base):
    __tablename__ = "ai_knowledge_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pack_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(100), default="compliance_copilot")
    scope_type: Mapped[str] = mapped_column(String(64), default="cross_framework")
    owner: Mapped[str] = mapped_column(String(255), default="")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="draft")
    approval_status: Mapped[str] = mapped_column(String(32), default="proposed")
    default_task_key: Mapped[str] = mapped_column(String(120), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions: Mapped[list["AIKnowledgePackVersion"]] = relationship(
        back_populates="knowledge_pack", cascade="all, delete-orphan"
    )


class AIKnowledgePackVersion(Base):
    __tablename__ = "ai_knowledge_pack_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_pack_id: Mapped[int] = mapped_column(ForeignKey("ai_knowledge_packs.id"), index=True)
    version_label: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    system_instruction: Mapped[str] = mapped_column(Text, default="")
    operating_principles_json: Mapped[str] = mapped_column(Text, default="[]")
    prompt_contract_json: Mapped[str] = mapped_column(Text, default="{}")
    output_contract_json: Mapped[str] = mapped_column(Text, default="{}")
    model_constraints_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by: Mapped[str] = mapped_column(String(255), default="")
    approved_by: Mapped[str] = mapped_column(String(255), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    knowledge_pack: Mapped["AIKnowledgePack"] = relationship(back_populates="versions")
    tasks: Mapped[list["AIKnowledgePackTask"]] = relationship(
        back_populates="knowledge_pack_version", cascade="all, delete-orphan"
    )
    references: Mapped[list["AIKnowledgePackReference"]] = relationship(
        back_populates="knowledge_pack_version", cascade="all, delete-orphan"
    )
    eval_cases: Mapped[list["AIKnowledgePackEvalCase"]] = relationship(
        back_populates="knowledge_pack_version", cascade="all, delete-orphan"
    )
    ai_suggestions: Mapped[list["AISuggestion"]] = relationship(back_populates="knowledge_pack_version")

    __table_args__ = (
        UniqueConstraint("knowledge_pack_id", "version_label", name="uq_ai_pack_version_label"),
    )


class AIKnowledgePackTask(Base):
    __tablename__ = "ai_knowledge_pack_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_pack_version_id: Mapped[int] = mapped_column(
        ForeignKey("ai_knowledge_pack_versions.id"), index=True
    )
    task_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(255))
    workflow_area: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    input_schema_json: Mapped[str] = mapped_column(Text, default="{}")
    output_schema_json: Mapped[str] = mapped_column(Text, default="{}")
    instruction_text: Mapped[str] = mapped_column(Text, default="")
    review_checklist_json: Mapped[str] = mapped_column(Text, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    knowledge_pack_version: Mapped["AIKnowledgePackVersion"] = relationship(back_populates="tasks")

    __table_args__ = (
        UniqueConstraint("knowledge_pack_version_id", "task_key", name="uq_ai_pack_task_key"),
    )


class AIKnowledgePackReference(Base):
    __tablename__ = "ai_knowledge_pack_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_pack_version_id: Mapped[int] = mapped_column(
        ForeignKey("ai_knowledge_pack_versions.id"), index=True
    )
    reference_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("reference_documents.id"), nullable=True, index=True
    )
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    unified_control_id: Mapped[int | None] = mapped_column(
        ForeignKey("unified_controls.id"), nullable=True, index=True
    )
    imported_requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("imported_requirements.id"), nullable=True, index=True
    )
    use_mode: Mapped[str] = mapped_column(String(64), default="guidance")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    knowledge_pack_version: Mapped["AIKnowledgePackVersion"] = relationship(back_populates="references")
    reference_document: Mapped["ReferenceDocument"] = relationship(back_populates="knowledge_pack_links")
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship()
    unified_control: Mapped["UnifiedControl"] = relationship()
    imported_requirement: Mapped["ImportedRequirement"] = relationship()


class AIKnowledgePackEvalCase(Base):
    __tablename__ = "ai_knowledge_pack_eval_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_pack_version_id: Mapped[int] = mapped_column(
        ForeignKey("ai_knowledge_pack_versions.id"), index=True
    )
    task_key: Mapped[str] = mapped_column(String(120), default="")
    case_code: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(255))
    input_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    expected_assertions_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="active")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    knowledge_pack_version: Mapped["AIKnowledgePackVersion"] = relationship(back_populates="eval_cases")

    __table_args__ = (
        UniqueConstraint("knowledge_pack_version_id", "case_code", name="uq_ai_pack_eval_case"),
    )


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    knowledge_pack_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_knowledge_pack_versions.id"), nullable=True, index=True
    )
    unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    control_implementation_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_implementations.id"), nullable=True, index=True
    )
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    suggestion_type: Mapped[str] = mapped_column(String(64))
    task_key: Mapped[str] = mapped_column(String(120), default="")
    provider: Mapped[str] = mapped_column(String(64), default="")
    model_name: Mapped[str] = mapped_column(String(100), default="")
    prompt_text: Mapped[str] = mapped_column(Text, default="")
    response_text: Mapped[str] = mapped_column(Text, default="")
    citations_json: Mapped[str] = mapped_column(Text, default="[]")
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="ai_suggestions")
    knowledge_pack_version: Mapped["AIKnowledgePackVersion"] = relationship(back_populates="ai_suggestions")
    unified_control: Mapped["UnifiedControl"] = relationship(back_populates="ai_suggestions")
    control_implementation: Mapped["ControlImplementation"] = relationship(back_populates="ai_suggestions")
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship(back_populates="ai_suggestions")


class AssessmentScriptModule(Base):
    __tablename__ = "assessment_script_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    entrypoint_type: Mapped[str] = mapped_column(String(32), default="python_file")
    entrypoint_ref: Mapped[str] = mapped_column(String(500), default="")
    interpreter: Mapped[str] = mapped_column(String(255), default="")
    working_directory: Mapped[str] = mapped_column(String(500), default="")
    context_argument_name: Mapped[str] = mapped_column(String(64), default="")
    default_arguments_json: Mapped[str] = mapped_column(Text, default="[]")
    manifest_path: Mapped[str] = mapped_column(String(500), default="")
    default_config_path: Mapped[str] = mapped_column(String(500), default="")
    output_contract: Mapped[str] = mapped_column(String(32), default="json_stdout")
    supported_actions_json: Mapped[str] = mapped_column(Text, default='["evidence_collection"]')
    supported_scopes_json: Mapped[str] = mapped_column(Text, default='["binding","product","product_flavor","control"]')
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=900)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bindings: Mapped[list["AssessmentScriptBinding"]] = relationship(
        back_populates="module", cascade="all, delete-orphan"
    )
    runs: Mapped[list["AssessmentScriptRun"]] = relationship(back_populates="module", cascade="all, delete-orphan")


class AssessmentScriptBinding(Base):
    __tablename__ = "assessment_script_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("assessment_script_modules.id"), index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    framework_binding_id: Mapped[int | None] = mapped_column(
        ForeignKey("organization_framework_bindings.id"), nullable=True, index=True
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    product_flavor_id: Mapped[int | None] = mapped_column(ForeignKey("product_flavors.id"), nullable=True, index=True)
    unified_control_id: Mapped[int | None] = mapped_column(ForeignKey("unified_controls.id"), nullable=True, index=True)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    evidence_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence_collection_plans.id"), nullable=True, index=True
    )
    binding_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    action_type: Mapped[str] = mapped_column(String(32), default="evidence_collection")
    config_path: Mapped[str] = mapped_column(String(500), default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    arguments_json: Mapped[str] = mapped_column(Text, default="[]")
    expected_outputs_json: Mapped[str] = mapped_column(Text, default="[]")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    module: Mapped["AssessmentScriptModule"] = relationship(back_populates="bindings")
    organization: Mapped["Organization"] = relationship()
    framework_binding: Mapped["OrganizationFrameworkBinding"] = relationship()
    product: Mapped["Product"] = relationship()
    product_flavor: Mapped["ProductFlavor"] = relationship()
    unified_control: Mapped["UnifiedControl"] = relationship()
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship()
    evidence_plan: Mapped["EvidenceCollectionPlan"] = relationship(back_populates="assessment_script_bindings")
    runs: Mapped[list["AssessmentScriptRun"]] = relationship(back_populates="binding", cascade="all, delete-orphan")


class AssessmentScriptRun(Base):
    __tablename__ = "assessment_script_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("assessment_script_modules.id"), index=True)
    binding_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_script_bindings.id"), nullable=True, index=True)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("controls.id"), nullable=True, index=True)
    evidence_item_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_items.id"), nullable=True, index=True)
    assessment_run_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_runs.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    summary: Mapped[str] = mapped_column(String(500), default="")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    command_line: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    module: Mapped["AssessmentScriptModule"] = relationship(back_populates="runs")
    binding: Mapped["AssessmentScriptBinding"] = relationship(back_populates="runs")
    framework: Mapped["Framework"] = relationship()
    control: Mapped["Control"] = relationship()
    evidence_item: Mapped["EvidenceItem"] = relationship()
    assessment_run: Mapped["AssessmentRun"] = relationship()


class SecretMetadata(Base):
    __tablename__ = "secret_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    secret_type: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32), default="keyring")
    external_ref: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ConfluenceConnection(Base):
    __tablename__ = "confluence_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    base_url: Mapped[str] = mapped_column(String(500))
    space_key: Mapped[str] = mapped_column(String(100))
    parent_page_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    auth_mode: Mapped[str] = mapped_column(String(32), default="basic")
    username: Mapped[str] = mapped_column(String(255), default="")
    secret_name: Mapped[str] = mapped_column(String(255))
    verify_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_status: Mapped[str] = mapped_column(String(32), default="")
    last_test_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    framework: Mapped["Framework"] = relationship(back_populates="confluence_connections")
    bindings: Mapped[list["OrganizationFrameworkBinding"]] = relationship(back_populates="confluence_connection")


class LifecycleEvent(Base):
    __tablename__ = "lifecycle_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    lifecycle_name: Mapped[str] = mapped_column(String(64), index=True)
    from_state: Mapped[str] = mapped_column(String(64), default="")
    to_state: Mapped[str] = mapped_column(String(64), default="")
    actor: Mapped[str] = mapped_column(String(255), default="system")
    rationale: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    previous_hash: Mapped[str] = mapped_column(String(128), default="")
    event_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setting_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    setting_value: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flag_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    rollout_strategy: Mapped[str] = mapped_column(String(32), default="static")
    owner: Mapped[str] = mapped_column(String(255), default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CircuitBreakerState(Base):
    __tablename__ = "circuit_breaker_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(32), default="closed")
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    threshold: Mapped[int] = mapped_column(Integer, default=3)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reopen_after_seconds: Mapped[int] = mapped_column(Integer, default=300)
    last_error: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExternalCallLedger(Base):
    __tablename__ = "external_call_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_key: Mapped[str] = mapped_column(String(255), index=True)
    operation: Mapped[str] = mapped_column(String(120), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), index=True)
    request_hash: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="started")
    response_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("integration_key", "operation", "idempotency_key", name="uq_external_call_idempotency"),
    )


class UserFeedbackMessage(Base):
    __tablename__ = "user_feedback_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_label: Mapped[str] = mapped_column(String(64), default="")
    reporter_name: Mapped[str] = mapped_column(String(255), default="")
    reporter_role: Mapped[str] = mapped_column(String(255), default="")
    contact: Mapped[str] = mapped_column(String(255), default="")
    area: Mapped[str] = mapped_column(String(120), default="")
    page_context: Mapped[str] = mapped_column(String(120), default="")
    subject: Mapped[str] = mapped_column(String(255), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AwsCliProfile(Base):
    __tablename__ = "aws_cli_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    sso_session_name: Mapped[str] = mapped_column(String(255), default="")
    sso_start_url: Mapped[str] = mapped_column(String(500), default="")
    sso_region: Mapped[str] = mapped_column(String(64), default="")
    sso_account_id: Mapped[str] = mapped_column(String(64), default="")
    sso_role_name: Mapped[str] = mapped_column(String(255), default="")
    default_region: Mapped[str] = mapped_column(String(64), default="")
    output_format: Mapped[str] = mapped_column(String(32), default="json")
    registration_mode: Mapped[str] = mapped_column(String(32), default="manual")
    config_scope: Mapped[str] = mapped_column(String(64), default="wsl_local")
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_validation_status: Mapped[str] = mapped_column(String(32), default="")
    last_validation_message: Mapped[str] = mapped_column(Text, default="")
    detected_account_id: Mapped[str] = mapped_column(String(64), default="")
    detected_arn: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AssessmentSchedule(Base):
    __tablename__ = "assessment_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    framework_binding_id: Mapped[int | None] = mapped_column(
        ForeignKey("organization_framework_bindings.id"), nullable=True, index=True
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    product_flavor_id: Mapped[int | None] = mapped_column(ForeignKey("product_flavors.id"), nullable=True, index=True)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey("frameworks.id"), nullable=True)
    framework_codes: Mapped[str] = mapped_column(Text, default="")
    name: Mapped[str] = mapped_column(String(255))
    cadence: Mapped[str] = mapped_column(String(32))
    execution_mode: Mapped[str] = mapped_column(String(32), default="assisted")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str] = mapped_column(String(32), default="")
    last_run_message: Mapped[str] = mapped_column(Text, default="")
    next_run_at: Mapped[datetime] = mapped_column(DateTime)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped["Organization"] = relationship()
    framework_binding: Mapped["OrganizationFrameworkBinding"] = relationship()
    product: Mapped["Product"] = relationship()
    product_flavor: Mapped["ProductFlavor"] = relationship()
    framework: Mapped["Framework"] = relationship(back_populates="schedules")
