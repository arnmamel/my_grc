from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from aws_local_audit.models import (
    AwsEvidenceTarget,
    ControlImplementation,
    EvidenceCollectionPlan,
    Framework,
    Organization,
    Product,
    ProductControlProfile,
    UnifiedControl,
    UnifiedControlMapping,
)
from aws_local_audit.services.governance import GovernanceService


SCF_PIVOT_FRAMEWORK_CODE = "SCF_2025_3_1"


class ControlMatrixService:
    def __init__(self, session):
        self.session = session
        self.governance = GovernanceService(session)

    def available_scopes(self) -> list[dict]:
        products = self.session.scalars(
            select(Product)
            .options(selectinload(Product.organization))
            .order_by(Product.organization_id, Product.code)
        ).all()
        scopes = []
        for product in products:
            scopes.append(
                {
                    "scope_key": self.scope_key(product.organization.code, product.code),
                    "label": f"{product.organization.code} / {product.code}",
                    "organization_code": product.organization.code,
                    "organization_name": product.organization.name,
                    "product_code": product.code,
                    "product_name": product.name,
                }
            )
        return scopes

    def setup_guidance(self, organization_code: str | None = None, product_code: str | None = None) -> list[dict]:
        guidance: list[dict] = []
        pivot_code = self.governance.pivot_framework_code()
        scf_framework = self.session.scalar(select(Framework).where(Framework.code == SCF_PIVOT_FRAMEWORK_CODE))
        if scf_framework is None:
            guidance.append(
                {
                    "title": "Load the Secure Controls Framework baseline",
                    "detail": "Import the latest SCF workbook or seed the baseline templates so the unified control framework has a pivot backbone.",
                    "page": "Wizards",
                }
            )
        elif pivot_code != SCF_PIVOT_FRAMEWORK_CODE:
            guidance.append(
                {
                    "title": "Set SCF as the pivot framework",
                    "detail": "The workspace should use SCF as the converged baseline for mappings and SoA management.",
                    "page": "Wizards",
                }
            )

        if self.session.scalar(select(UnifiedControl.id).limit(1)) is None:
            guidance.append(
                {
                    "title": "Create or import unified controls",
                    "detail": "The SCF baseline should appear as the core control library before implementation work starts.",
                    "page": "Control Framework Studio",
                }
            )

        if organization_code is None:
            guidance.append(
                {
                    "title": "Create an organization",
                    "detail": "Organizations define who is implementing and operating the controls.",
                    "page": "Portfolio",
                }
            )
            return guidance

        if product_code is None:
            guidance.append(
                {
                    "title": "Create a product",
                    "detail": "Products let you record scope-specific SoA decisions, implementations, and testing strategies.",
                    "page": "Portfolio",
                }
            )
            return guidance

        organization = self.session.scalar(select(Organization).where(Organization.code == organization_code))
        product = self.session.scalar(
            select(Product).where(Product.organization.has(code=organization_code), Product.code == product_code)
        )
        if organization is None or product is None:
            guidance.append(
                {
                    "title": "Fix the selected working scope",
                    "detail": "The selected organization or product no longer exists. Recreate the scope or choose another one.",
                    "page": "Portfolio",
                }
            )
            return guidance

        implementations = self.session.scalars(
            select(ControlImplementation).where(
                ControlImplementation.organization_id == organization.id,
                ControlImplementation.product_id == product.id,
            )
        ).all()
        if not implementations:
            guidance.append(
                {
                    "title": "Write implementation narratives",
                    "detail": "Describe how the selected product implements the applicable SCF controls.",
                    "page": "Control Framework Studio",
                }
            )

        profiles = self.session.scalars(
            select(ProductControlProfile).where(
                ProductControlProfile.organization_id == organization.id,
                ProductControlProfile.product_id == product.id,
            )
        ).all()
        if not profiles:
            guidance.append(
                {
                    "title": "Record SoA applicability decisions",
                    "detail": "Mark which controls apply to the selected product and explain the rationale for non-applicable ones.",
                    "page": "Control Framework Studio",
                }
            )

        plans = self.session.scalars(
            select(EvidenceCollectionPlan).where(EvidenceCollectionPlan.unified_control_id.is_not(None))
        ).all()
        if not plans:
            guidance.append(
                {
                    "title": "Define testing and evidence plans",
                    "detail": "Each control should tell the team how it is tested and what evidence should be collected.",
                    "page": "Control Framework Studio",
                }
            )
        return guidance

    def matrix_rows(
        self,
        *,
        organization_code: str | None = None,
        product_code: str | None = None,
        comparison_scope_keys: list[str] | None = None,
        search: str = "",
        framework_codes: list[str] | None = None,
    ) -> list[dict]:
        unified_controls = self.session.scalars(
            select(UnifiedControl)
            .options(
                selectinload(UnifiedControl.mappings).selectinload(UnifiedControlMapping.framework),
                selectinload(UnifiedControl.mappings).selectinload(UnifiedControlMapping.control),
            )
            .order_by(UnifiedControl.code)
        ).all()
        query_text = search.strip().lower()
        if query_text:
            unified_controls = [
                item
                for item in unified_controls
                if query_text in item.code.lower()
                or query_text in item.name.lower()
                or query_text in item.description.lower()
                or query_text in item.implementation_guidance.lower()
            ]

        approved_mappings = self.session.scalars(
            select(UnifiedControlMapping)
            .options(
                selectinload(UnifiedControlMapping.framework),
                selectinload(UnifiedControlMapping.control),
                selectinload(UnifiedControlMapping.unified_control),
            )
            .where(UnifiedControlMapping.approval_status == "approved")
        ).all()
        mapping_groups: dict[int, list[UnifiedControlMapping]] = defaultdict(list)
        for mapping in approved_mappings:
            if framework_codes and mapping.framework.code not in framework_codes:
                continue
            mapping_groups[mapping.unified_control_id].append(mapping)

        scope_pairs = []
        if organization_code and product_code:
            scope_pairs.append((organization_code, product_code))
        for scope_key in comparison_scope_keys or []:
            org_code, prod_code = self.scope_pair_from_key(scope_key)
            if not org_code or not prod_code:
                continue
            if (org_code, prod_code) not in scope_pairs:
                scope_pairs.append((org_code, prod_code))

        scoped_profiles = self._profiles_for_scopes(scope_pairs)
        scoped_implementations = self._implementations_for_scopes(scope_pairs)
        evidence_plans = self.session.scalars(
            select(EvidenceCollectionPlan)
            .where(EvidenceCollectionPlan.lifecycle_status != "retired")
            .order_by(EvidenceCollectionPlan.updated_at.desc())
        ).all()
        targets = self._targets_for_scopes(scope_pairs)

        rows: list[dict] = []
        for unified_control in unified_controls:
            mappings = mapping_groups.get(unified_control.id, [])
            standards = sorted({item.framework.code for item in mappings})
            requirement_refs = [
                f"{item.framework.code}:{item.control.control_id}"
                for item in mappings
                if item.framework is not None and item.control is not None
            ]
            representative_control_ids = {item.control_id for item in mappings}
            representative_plan = self._best_plan(
                unified_control_id=unified_control.id,
                control_ids=representative_control_ids,
                evidence_plans=evidence_plans,
            )

            primary_state = self._scope_state(
                organization_code=organization_code,
                product_code=product_code,
                unified_control=unified_control,
                mappings=mappings,
                profiles=scoped_profiles,
                implementations=scoped_implementations,
                targets=targets,
                plan=representative_plan,
            )
            row = {
                "SCF Control": unified_control.code,
                "Control Name": unified_control.name,
                "Domain": unified_control.domain,
                "Family": unified_control.family,
                "Requirement Coverage Summary": unified_control.description,
                "Implementation Guidance": unified_control.implementation_guidance,
                "Test Guidance": unified_control.test_guidance,
                "Control Type": unified_control.control_type,
                "Default Severity": unified_control.default_severity,
                "Mapped Standards": ", ".join(standards) if standards else "Not mapped yet",
                "Mapped Requirements": "; ".join(requirement_refs[:8]) if requirement_refs else "",
                "SoA": primary_state["applicability_status"],
                "SoA Rationale": primary_state["rationale"],
                "Implementation": primary_state["implementation_status"],
                "Implementation Summary": primary_state["implementation_summary"],
                "Assessment Mode": primary_state["assessment_mode"],
                "Testing": primary_state["testing_summary"],
                "Evidence Plan": primary_state["evidence_plan_summary"],
                "AWS Scope": primary_state["aws_scope_summary"],
                "_scope_profile": primary_state["profile"],
                "_implementation": primary_state["implementation"],
                "_plan": representative_plan,
                "_mappings": mappings,
                "_unified_control_id": unified_control.id,
            }

            for scope_key in comparison_scope_keys or []:
                scope_org, scope_product = self.scope_pair_from_key(scope_key)
                if not scope_org or not scope_product:
                    continue
                scope_state = self._scope_state(
                    organization_code=scope_org,
                    product_code=scope_product,
                    unified_control=unified_control,
                    mappings=mappings,
                    profiles=scoped_profiles,
                    implementations=scoped_implementations,
                    targets=targets,
                    plan=representative_plan,
                )
                scope_label = scope_key.replace("::", " / ")
                row[f"{scope_label} SoA"] = scope_state["applicability_status"]
                row[f"{scope_label} Impl"] = scope_state["implementation_status"]
            rows.append(row)

        return rows

    @staticmethod
    def scope_key(organization_code: str, product_code: str) -> str:
        return f"{organization_code}::{product_code}"

    @staticmethod
    def scope_pair_from_key(scope_key: str) -> tuple[str, str]:
        if "::" not in scope_key:
            return "", ""
        organization_code, product_code = scope_key.split("::", 1)
        return organization_code, product_code

    def _profiles_for_scopes(self, scope_pairs: list[tuple[str, str]]) -> list[ProductControlProfile]:
        if not scope_pairs:
            return []
        rows = []
        for organization_code, product_code in scope_pairs:
            product = self.session.scalar(
                select(Product).where(Product.organization.has(code=organization_code), Product.code == product_code)
            )
            if product is not None:
                rows.append(product.id)
        if not rows:
            return []
        return list(
            self.session.scalars(
                select(ProductControlProfile)
                .options(
                selectinload(ProductControlProfile.product),
                selectinload(ProductControlProfile.product_flavor),
                selectinload(ProductControlProfile.unified_control),
                selectinload(ProductControlProfile.control),
            )
            .where(ProductControlProfile.product_id.in_(rows))
            .order_by(ProductControlProfile.updated_at.desc())
            )
        )

    def _implementations_for_scopes(self, scope_pairs: list[tuple[str, str]]) -> list[ControlImplementation]:
        if not scope_pairs:
            return []
        rows = []
        for organization_code, product_code in scope_pairs:
            product = self.session.scalar(
                select(Product).where(Product.organization.has(code=organization_code), Product.code == product_code)
            )
            if product is not None:
                rows.append(product.id)
        if not rows:
            return []
        return list(
            self.session.scalars(
                select(ControlImplementation)
                .options(
                selectinload(ControlImplementation.product),
                selectinload(ControlImplementation.product_flavor),
                selectinload(ControlImplementation.unified_control),
                selectinload(ControlImplementation.control),
            )
                .where(ControlImplementation.product_id.in_(rows))
                .order_by(ControlImplementation.updated_at.desc())
            )
        )

    def _targets_for_scopes(self, scope_pairs: list[tuple[str, str]]) -> list[AwsEvidenceTarget]:
        if not scope_pairs:
            return []
        rows = []
        for organization_code, product_code in scope_pairs:
            product = self.session.scalar(
                select(Product).where(Product.organization.has(code=organization_code), Product.code == product_code)
            )
            if product is not None:
                rows.append(product.id)
        if not rows:
            return []
        return list(
            self.session.scalars(
                select(AwsEvidenceTarget)
                .options(
                selectinload(AwsEvidenceTarget.product),
                selectinload(AwsEvidenceTarget.product_flavor),
                selectinload(AwsEvidenceTarget.unified_control),
                selectinload(AwsEvidenceTarget.control),
            )
                .where(AwsEvidenceTarget.product_id.in_(rows))
                .order_by(AwsEvidenceTarget.updated_at.desc())
            )
        )

    @staticmethod
    def _best_plan(
        *,
        unified_control_id: int,
        control_ids: set[int],
        evidence_plans: list[EvidenceCollectionPlan],
    ) -> EvidenceCollectionPlan | None:
        candidates = [
            item
            for item in evidence_plans
            if item.unified_control_id == unified_control_id or item.control_id in control_ids
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                2 if item.unified_control_id == unified_control_id else 1,
                1 if item.lifecycle_status in {"approved", "ready", "active", "published"} else 0,
                item.updated_at,
            ),
            reverse=True,
        )
        return candidates[0]

    def _scope_state(
        self,
        *,
        organization_code: str | None,
        product_code: str | None,
        unified_control: UnifiedControl,
        mappings: list[UnifiedControlMapping],
        profiles: list[ProductControlProfile],
        implementations: list[ControlImplementation],
        targets: list[AwsEvidenceTarget],
        plan: EvidenceCollectionPlan | None,
    ) -> dict:
        if not organization_code or not product_code:
            return {
                "applicability_status": "Select a scope",
                "rationale": "",
                "implementation_status": "Not scoped",
                "implementation_summary": "",
                "assessment_mode": "",
                "testing_summary": "",
                "evidence_plan_summary": self._plan_summary(plan),
                "aws_scope_summary": "",
                "profile": None,
                "implementation": None,
            }

        product = self.session.scalar(
            select(Product).where(Product.organization.has(code=organization_code), Product.code == product_code)
        )
        if product is None:
            return {
                "applicability_status": "Scope missing",
                "rationale": "",
                "implementation_status": "Scope missing",
                "implementation_summary": "",
                "assessment_mode": "",
                "testing_summary": "",
                "evidence_plan_summary": self._plan_summary(plan),
                "aws_scope_summary": "",
                "profile": None,
                "implementation": None,
            }

        control_ids = {item.control_id for item in mappings}
        profile = next(
            (
                item
                for item in profiles
                if item.product_id == product.id
                and (item.unified_control_id == unified_control.id or item.control_id in control_ids)
            ),
            None,
        )
        implementation = next(
            (
                item
                for item in implementations
                if item.product_id == product.id
                and (item.unified_control_id == unified_control.id or item.control_id in control_ids)
            ),
            None,
        )
        related_targets = [
            item
            for item in targets
            if item.product_id == product.id
            and (item.unified_control_id == unified_control.id or item.control_id in control_ids)
        ]
        implementation_status = profile.implementation_status if profile else (implementation.status if implementation else "Not recorded")
        return {
            "applicability_status": profile.applicability_status if profile else "Not assessed",
            "rationale": profile.rationale if profile else "",
            "implementation_status": implementation_status,
            "implementation_summary": self._implementation_summary(implementation),
            "assessment_mode": profile.assessment_mode if profile else "",
            "testing_summary": self._testing_summary(implementation, profile, plan),
            "evidence_plan_summary": self._plan_summary(plan),
            "aws_scope_summary": self._target_summary(related_targets),
            "profile": profile,
            "implementation": implementation,
        }

    @staticmethod
    def _implementation_summary(implementation: ControlImplementation | None) -> str:
        if implementation is None:
            return ""
        summary = " | ".join(
            item
            for item in [
                implementation.title,
                implementation.objective.strip(),
                implementation.impl_general.strip(),
                implementation.impl_aws.strip(),
            ]
            if item
        )
        return summary[:260]

    @staticmethod
    def _testing_summary(
        implementation: ControlImplementation | None,
        profile: ProductControlProfile | None,
        plan: EvidenceCollectionPlan | None,
    ) -> str:
        parts = []
        if profile and profile.assessment_mode:
            parts.append(profile.assessment_mode)
        if implementation and implementation.test_plan.strip():
            parts.append(implementation.test_plan.strip())
        elif plan and plan.instructions.strip():
            parts.append(plan.instructions.strip())
        return " | ".join(parts)[:220]

    @staticmethod
    def _plan_summary(plan: EvidenceCollectionPlan | None) -> str:
        if plan is None:
            return "Not defined"
        parts = [plan.plan_code, plan.execution_mode, plan.evidence_type]
        if plan.review_frequency:
            parts.append(plan.review_frequency)
        return " | ".join(item for item in parts if item)

    @staticmethod
    def _target_summary(targets: list[AwsEvidenceTarget]) -> str:
        if not targets:
            return ""
        primary = targets[0]
        return " | ".join(
            item
            for item in [
                primary.aws_profile,
                primary.aws_account_id,
                primary.role_name,
                primary.regions_json.replace('"', "").replace("[", "").replace("]", ""),
            ]
            if item
        )
