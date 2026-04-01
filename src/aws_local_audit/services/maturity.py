from __future__ import annotations

from sqlalchemy import select

from aws_local_audit.collectors import COLLECTORS
from aws_local_audit.models import Control, ControlImplementation, ProductControlProfile


class MaturityService:
    def __init__(self, session):
        self.session = session

    def suggest_profile_dimensions(self, implementation: ControlImplementation | None, control: Control | None) -> dict:
        governance = 1
        implementation_score = 1
        observability = 1
        automation = 1
        assurance = 1

        if implementation:
            if implementation.owner and implementation.frequency:
                governance = 3
            if implementation.status in {"implemented", "in_review", "operational"}:
                implementation_score = 3
            if implementation.objective and implementation.test_plan:
                assurance = 3
            if implementation.evidence_links or implementation.design_doc:
                observability = 2
            if implementation.impl_aws or implementation.impl_general:
                implementation_score = max(implementation_score, 4)

        if control:
            metadata = control.metadata_entry
            if metadata and metadata.check_type in {"hybrid", "automated"}:
                observability = max(observability, 3)
            if control.evidence_query in COLLECTORS:
                automation = 4
                observability = max(observability, 4)
                assurance = max(assurance, 4)
            elif metadata and metadata.check_type == "hybrid":
                automation = max(automation, 2)

        maturity_level = round((governance + implementation_score + observability + automation + assurance) / 5)
        if maturity_level >= 5 and automation >= 4 and assurance >= 4:
            autonomy = "autonomous_assessment_ready"
        elif maturity_level >= 4 and automation >= 3:
            autonomy = "assisted_autonomy"
        elif maturity_level >= 3:
            autonomy = "manual_with_assistance"
        else:
            autonomy = "manual_only"

        return {
            "maturity_level": maturity_level,
            "maturity_governance": governance,
            "maturity_implementation": implementation_score,
            "maturity_observability": observability,
            "maturity_automation": automation,
            "maturity_assurance": assurance,
            "autonomy_recommendation": autonomy,
        }

    def suggest_for_product_control_profile(self, profile: ProductControlProfile) -> dict:
        implementation = None
        control = None
        if profile.control_implementation_id:
            implementation = self.session.get(ControlImplementation, profile.control_implementation_id)
        if profile.control_id:
            control = self.session.get(Control, profile.control_id)
        return self.suggest_profile_dimensions(implementation=implementation, control=control)

    def suggest_for_implementation(
        self,
        organization_id: int,
        product_id: int | None,
        product_flavor_id: int | None,
        unified_control_id: int | None,
        control_id: int | None,
    ) -> dict:
        query = select(ControlImplementation).where(
            ControlImplementation.organization_id == organization_id,
            ControlImplementation.product_id == product_id,
            ControlImplementation.product_flavor_id == product_flavor_id,
        )
        if unified_control_id is not None:
            query = query.where(ControlImplementation.unified_control_id == unified_control_id)
        if control_id is not None:
            query = query.where(ControlImplementation.control_id == control_id)

        implementation = self.session.scalar(query.order_by(ControlImplementation.updated_at.desc()))
        if implementation is None and product_flavor_id is not None:
            fallback_query = select(ControlImplementation).where(
                ControlImplementation.organization_id == organization_id,
                ControlImplementation.product_id == product_id,
                ControlImplementation.product_flavor_id.is_(None),
            )
            if unified_control_id is not None:
                fallback_query = fallback_query.where(ControlImplementation.unified_control_id == unified_control_id)
            if control_id is not None:
                fallback_query = fallback_query.where(ControlImplementation.control_id == control_id)
            implementation = self.session.scalar(fallback_query.order_by(ControlImplementation.updated_at.desc()))
        control = self.session.get(Control, control_id) if control_id else None
        return self.suggest_profile_dimensions(implementation=implementation, control=control)
