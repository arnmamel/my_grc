from __future__ import annotations

from sqlalchemy import select

from aws_local_audit.models import (
    Control,
    ControlImplementation,
    EvidenceCollectionPlan,
    Framework,
    Organization,
    Product,
    ProductControlProfile,
    ProductFlavor,
    UnifiedControl,
    UnifiedControlMapping,
)
from aws_local_audit.services.frameworks import FrameworkService
from aws_local_audit.services.governance import GovernanceService
from aws_local_audit.services.workbench import WorkbenchService


SCF_PIVOT_FRAMEWORK_CODE = "SCF_2025_3_1"
ISO_ANNEX_A_FRAMEWORK_CODE = "ISO27001_2022"
ISO_ANNEX_A_EXERCISE_CONTROL_ID = "A.5.1"
SCF_PIVOT_EXERCISE_UNIFIED_CONTROL = "SCF_PIVOT_POLICIES_FOR_INFORMATION_SECURITY"
LOCAL_WORKSPACE_ORG_CODE = "LOCAL_WORKSPACE"
LOCAL_WORKSPACE_PRODUCT_CODE = "MY_GRC_PLATFORM"
LOCAL_WORKSPACE_FLAVOR_CODE = "DEFAULT"


class FoundationUpliftService:
    def __init__(self, session):
        self.session = session
        self.frameworks = FrameworkService(session)
        self.governance = GovernanceService(session)
        self.workbench = WorkbenchService(session)

    def phase1_backbone_status(self) -> dict:
        framework = self.session.scalar(select(Framework).where(Framework.code == ISO_ANNEX_A_FRAMEWORK_CODE))
        control = None
        if framework is not None:
            control = self.session.scalar(
                select(Control).where(Control.framework_id == framework.id, Control.control_id == ISO_ANNEX_A_EXERCISE_CONTROL_ID)
            )
        unified = self.session.scalar(
            select(UnifiedControl).where(UnifiedControl.code == SCF_PIVOT_EXERCISE_UNIFIED_CONTROL)
        )
        organization = self.session.scalar(select(Organization).where(Organization.code == LOCAL_WORKSPACE_ORG_CODE))
        product = None
        flavor = None
        if organization is not None:
            product = self.session.scalar(
                select(Product).where(Product.organization_id == organization.id, Product.code == LOCAL_WORKSPACE_PRODUCT_CODE)
            )
        if product is not None:
            flavor = self.session.scalar(
                select(ProductFlavor).where(ProductFlavor.product_id == product.id, ProductFlavor.code == LOCAL_WORKSPACE_FLAVOR_CODE)
            )

        mapping = None
        if control is not None and unified is not None:
            mapping = self.session.scalar(
                select(UnifiedControlMapping).where(
                    UnifiedControlMapping.unified_control_id == unified.id,
                    UnifiedControlMapping.control_id == control.id,
                )
            )

        implementation = None
        profile = None
        plan = None
        if organization is not None and product is not None and unified is not None:
            implementation = self.session.scalar(
                select(ControlImplementation).where(
                    ControlImplementation.organization_id == organization.id,
                    ControlImplementation.product_id == product.id,
                    ControlImplementation.product_flavor_id == (flavor.id if flavor else None),
                    ControlImplementation.unified_control_id == unified.id,
                )
            )
            profile = self.session.scalar(
                select(ProductControlProfile).where(
                    ProductControlProfile.organization_id == organization.id,
                    ProductControlProfile.product_id == product.id,
                    ProductControlProfile.product_flavor_id == (flavor.id if flavor else None),
                    ProductControlProfile.unified_control_id == unified.id,
                )
            )
        if unified is not None:
            plan = self.session.scalar(
                select(EvidenceCollectionPlan).where(
                    EvidenceCollectionPlan.unified_control_id == unified.id,
                    EvidenceCollectionPlan.plan_code == "PHASE1_SCF_PIVOT_A_5_1"
                )
            )

        return {
            "pivot_framework_code": self.governance.pivot_framework_code(),
            "framework_seeded": framework is not None,
            "iso_control_present": control is not None,
            "pivot_unified_control_present": unified is not None,
            "approved_mapping_present": mapping is not None and mapping.approval_status == "approved",
            "organization_present": organization is not None,
            "product_present": product is not None,
            "flavor_present": flavor is not None,
            "implementation_present": implementation is not None,
            "product_control_profile_present": profile is not None,
            "evidence_plan_present": plan is not None,
        }

    def ensure_phase1_backbone_path(
        self,
        *,
        organization_code: str = LOCAL_WORKSPACE_ORG_CODE,
        organization_name: str = "Local Workspace",
        product_code: str = LOCAL_WORKSPACE_PRODUCT_CODE,
        product_name: str = "my_grc Platform",
        product_flavor_code: str = LOCAL_WORKSPACE_FLAVOR_CODE,
        product_flavor_name: str = "Default",
    ) -> dict:
        self.frameworks.seed_templates()
        self.governance.set_pivot_framework_code(
            SCF_PIVOT_FRAMEWORK_CODE,
            "Secure Controls Framework is the pivot baseline for converged unified control mapping.",
        )

        organization = self.workbench.create_organization(
            name=organization_name,
            code=organization_code,
            description="Local enterprise workspace used to exercise the Phase 1 foundation and mapped control paths.",
        )
        product = self.workbench.create_product(
            organization_code=organization.code,
            name=product_name,
            code=product_code,
            description="Primary local platform record used to exercise unified controls, implementations, and assessments.",
            product_type="platform",
            deployment_model="hybrid",
            data_classification="internal",
            owner="grc_workspace",
        )
        flavor = self.workbench.create_product_flavor(
            organization_code=organization.code,
            product_code=product.code,
            name=product_flavor_name,
            code=product_flavor_code,
            description="Default operating flavor for the local workspace and backbone maturity exercise.",
            deployment_model="hybrid",
            hosting_model="aws",
            region_scope="eu-west-1",
            customer_segment="internal",
            attributes_json='{"workspace_role":"phase1_backbone"}',
        )
        unified = self.workbench.create_unified_control(
            code=SCF_PIVOT_EXERCISE_UNIFIED_CONTROL,
            name="Policies for information security",
            description=(
                "SCF-pivot unified control path for policy governance, using ISO/IEC 27001:2022 Annex A "
                "A.5.1 as the first exercised mapped requirement in the local workspace."
            ),
            domain="governance",
            family="policy_management",
            control_type="preventive",
            default_severity="high",
            implementation_guidance=(
                "Maintain approved information security policies, assign ownership, publish them through governed channels, "
                "and keep review evidence linked to the product and flavor scope."
            ),
            test_guidance=(
                "Review the implementation narrative, confirm policy ownership and review cadence, and gather documentary "
                "evidence or governed repository metadata when automation is not sufficient."
            ),
        )
        mapping = self.workbench.map_framework_control(
            unified_control_code=unified.code,
            framework_code=ISO_ANNEX_A_FRAMEWORK_CODE,
            control_id=ISO_ANNEX_A_EXERCISE_CONTROL_ID,
            mapping_type="mapped",
            rationale=(
                "Initial Phase 1 backbone path. ISO/IEC 27001:2022 Annex A A.5.1 is mapped into the SCF-pivot unified "
                "control baseline to prove end-to-end traceability in the local workspace."
            ),
            confidence=1.0,
            inheritance_strategy="manual_review",
            approval_status="approved",
            reviewed_by="foundation_uplift_service",
            approval_notes="Approved as the initial SCF-pivot Phase 1 control path.",
        )
        plan = self.workbench.upsert_evidence_collection_plan(
            name="Phase 1 SCF pivot policy governance plan",
            framework_code=ISO_ANNEX_A_FRAMEWORK_CODE,
            control_id=ISO_ANNEX_A_EXERCISE_CONTROL_ID,
            unified_control_code=unified.code,
            plan_code="PHASE1_SCF_PIVOT_A_5_1",
            scope_type="product_flavor",
            execution_mode="manual",
            collector_key="manual.policy_review",
            evidence_type="manual_artifact",
            instructions=(
                "Collect the approved policy set, review metadata, ownership, and review cadence for the scoped product "
                "and flavor. Store documentary evidence or a manual attestation when automation does not apply."
            ),
            expected_artifacts_json='["policy_document","manual_attestation","review_record"]',
            review_frequency="quarterly",
            minimum_freshness_days=90,
            lifecycle_status="approved",
        )
        implementation = self.workbench.upsert_control_implementation(
            organization_code=organization.code,
            product_code=product.code,
            product_flavor_code=flavor.code,
            unified_control_code=unified.code,
            framework_code=ISO_ANNEX_A_FRAMEWORK_CODE,
            control_id=ISO_ANNEX_A_EXERCISE_CONTROL_ID,
            title="my_grc policy governance implementation",
            objective="Define, approve, communicate, and periodically review information security policies.",
            impl_aws=(
                "Policy repositories for the product are stored in controlled AWS-backed locations with encryption, "
                "versioning, and restricted access. Review artifacts are retained for assurance activity."
            ),
            impl_general=(
                "The GRC team owns the policy lifecycle, assigns reviewers, and tracks review outcomes through the workspace."
            ),
            status="implemented",
            lifecycle="operate",
            owner="grc_workspace",
            priority="high",
            frequency="quarterly",
            test_plan="Review policy ownership, approval evidence, publication path, and review cadence.",
            evidence_links="PHASE1_SCF_PIVOT_A_5_1",
            design_doc="SCF pivot Phase 1 local workspace backbone path",
            notes="Created automatically to exercise the Phase 1 backbone with a SCF-pivoted ISO Annex A path.",
        )
        profile = self.workbench.upsert_product_control_profile(
            organization_code=organization.code,
            product_code=product.code,
            product_flavor_code=flavor.code,
            unified_control_code=unified.code,
            framework_code=ISO_ANNEX_A_FRAMEWORK_CODE,
            control_id=ISO_ANNEX_A_EXERCISE_CONTROL_ID,
            applicability_status="applicable",
            implementation_status="implemented",
            assessment_mode="assisted",
            maturity_governance=4,
            maturity_implementation=4,
            maturity_observability=3,
            maturity_automation=2,
            maturity_assurance=3,
            rationale=(
                "This profile exercises the Phase 1 backbone in a realistic local scope while preserving manual-evidence "
                "options for the parts that are not fully automatable."
            ),
            evidence_strategy="Documentary review with governed manual evidence until a stronger automation path is available.",
            review_notes="Initial local workspace profile created by the foundation uplift workflow.",
        )

        self.session.flush()
        return {
            "pivot_framework_code": self.governance.pivot_framework_code(),
            "framework_code": ISO_ANNEX_A_FRAMEWORK_CODE,
            "control_id": ISO_ANNEX_A_EXERCISE_CONTROL_ID,
            "unified_control_code": unified.code,
            "mapping_id": mapping.id,
            "organization_code": organization.code,
            "product_code": product.code,
            "product_flavor_code": flavor.code,
            "implementation_code": implementation.implementation_code,
            "product_control_profile_id": profile.id,
            "evidence_plan_code": plan.plan_code,
        }
