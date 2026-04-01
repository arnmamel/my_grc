from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from aws_local_audit.models import (
    AwsEvidenceTarget,
    ConfluenceConnection,
    Control,
    ControlImplementation,
    CustomerQuestionnaire,
    CustomerQuestionnaireItem,
    EvidenceCollectionPlan,
    Framework,
    Organization,
    OrganizationFrameworkBinding,
    Product,
    ProductControlProfile,
    ProductFlavor,
    UnifiedControl,
    UnifiedControlMapping,
)
from aws_local_audit.services.lifecycle import LifecycleService


def _normalize_code(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.strip().upper())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


class WorkbenchService:
    def __init__(self, session):
        self.session = session
        self.lifecycle = LifecycleService(session)

    def create_organization(self, name: str, code: str | None = None, description: str = "") -> Organization:
        organization_code = _normalize_code(code or name)
        organization = self.session.scalar(select(Organization).where(Organization.code == organization_code))
        created = organization is None
        if organization is None:
            organization = Organization(code=organization_code, name=name, description=description)
            self.session.add(organization)
        else:
            organization.name = name
            organization.description = description
        self.session.flush()
        if created:
            self.lifecycle.record_event(
                entity_type="organization",
                entity_id=organization.id,
                lifecycle_name="organization_lifecycle",
                to_state=organization.status,
                actor="workbench_service",
            )
        return organization

    def list_organizations(self) -> list[Organization]:
        return list(self.session.scalars(select(Organization).order_by(Organization.name)))

    def create_product(
        self,
        organization_code: str,
        name: str,
        code: str | None = None,
        description: str = "",
        product_type: str = "service",
        lifecycle_status: str = "active",
        deployment_model: str = "",
        data_classification: str = "",
        owner: str = "",
    ) -> Product:
        organization = self._organization_by_code(organization_code)
        product_code = _normalize_code(code or name)
        product = self.session.scalar(
            select(Product).where(Product.organization_id == organization.id, Product.code == product_code)
        )
        if product is None:
            product = Product(organization_id=organization.id, code=product_code, name=name)
            self.session.add(product)
        product.name = name
        product.description = description
        product.product_type = product_type
        product.lifecycle_status = lifecycle_status
        product.deployment_model = deployment_model
        product.data_classification = data_classification
        product.owner = owner
        self.session.flush()
        return product

    def list_products(self, organization_code: str | None = None) -> list[Product]:
        query = select(Product).order_by(Product.name)
        if organization_code:
            organization = self._organization_by_code(organization_code)
            query = query.where(Product.organization_id == organization.id)
        return list(self.session.scalars(query))

    def create_product_flavor(
        self,
        organization_code: str,
        product_code: str,
        name: str,
        code: str | None = None,
        description: str = "",
        deployment_model: str = "",
        hosting_model: str = "",
        region_scope: str = "",
        customer_segment: str = "",
        attributes_json: str = "{}",
    ) -> ProductFlavor:
        product = self._product_by_code(organization_code, product_code)
        flavor_code = _normalize_code(code or name)
        flavor = self.session.scalar(
            select(ProductFlavor).where(ProductFlavor.product_id == product.id, ProductFlavor.code == flavor_code)
        )
        if flavor is None:
            flavor = ProductFlavor(product_id=product.id, code=flavor_code, name=name)
            self.session.add(flavor)
        flavor.name = name
        flavor.description = description
        flavor.deployment_model = deployment_model
        flavor.hosting_model = hosting_model
        flavor.region_scope = region_scope
        flavor.customer_segment = customer_segment
        flavor.attributes_json = attributes_json
        self.session.flush()
        return flavor

    def list_product_flavors(self, organization_code: str, product_code: str) -> list[ProductFlavor]:
        product = self._product_by_code(organization_code, product_code)
        return list(self.session.scalars(select(ProductFlavor).where(ProductFlavor.product_id == product.id).order_by(ProductFlavor.name)))

    def bind_framework(
        self,
        organization_code: str,
        framework_code: str,
        aws_profile: str,
        aws_region: str,
        name: str | None = None,
        binding_code: str | None = None,
        aws_account_id: str | None = None,
        confluence_connection_name: str | None = None,
        confluence_parent_page_id: str | None = None,
        lifecycle_status: str = "active",
        notes: str = "",
    ) -> OrganizationFrameworkBinding:
        organization = self._organization_by_code(organization_code)
        framework = self._framework_by_code(framework_code)
        confluence_connection = (
            self._confluence_connection_by_name(confluence_connection_name)
            if confluence_connection_name
            else None
        )
        resolved_binding_code = _normalize_code(
            binding_code or f"{organization.code}_{framework.code}_{aws_profile}_{aws_region}"
        )

        binding = self.session.scalar(
            select(OrganizationFrameworkBinding).where(OrganizationFrameworkBinding.binding_code == resolved_binding_code)
        )
        previous_state = binding.lifecycle_status if binding else ""
        if binding is None:
            binding = OrganizationFrameworkBinding(
                organization_id=organization.id,
                framework_id=framework.id,
                binding_code=resolved_binding_code,
                name=name or f"{organization.name} {framework.name}",
                aws_profile=aws_profile,
                aws_region=aws_region,
                aws_account_id=aws_account_id,
                confluence_connection_id=confluence_connection.id if confluence_connection else None,
                confluence_parent_page_id=confluence_parent_page_id,
                lifecycle_status=lifecycle_status,
                notes=notes,
            )
            self.session.add(binding)
        else:
            self.lifecycle.ensure_transition(
                entity_type="framework_binding",
                lifecycle_name="framework_binding_lifecycle",
                from_state=previous_state,
                to_state=lifecycle_status,
            )
            binding.name = name or binding.name
            binding.aws_profile = aws_profile
            binding.aws_region = aws_region
            binding.aws_account_id = aws_account_id
            binding.confluence_connection_id = confluence_connection.id if confluence_connection else None
            binding.confluence_parent_page_id = confluence_parent_page_id
            binding.lifecycle_status = lifecycle_status
            binding.notes = notes
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="framework_binding",
            entity_id=binding.id,
            lifecycle_name="framework_binding_lifecycle",
            from_state=previous_state,
            to_state=binding.lifecycle_status,
            actor="workbench_service",
            payload={"organization": organization.code, "framework": framework.code, "aws_profile": aws_profile},
        )
        return binding

    def review_framework_binding(
        self,
        binding_code: str,
        lifecycle_status: str,
        actor: str = "workbench_service",
        rationale: str = "",
    ) -> OrganizationFrameworkBinding:
        binding = self._binding_by_code(binding_code)
        previous_state = binding.lifecycle_status
        self.lifecycle.ensure_transition(
            entity_type="framework_binding",
            lifecycle_name="framework_binding_lifecycle",
            from_state=previous_state,
            to_state=lifecycle_status,
        )
        binding.lifecycle_status = lifecycle_status
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="framework_binding",
            entity_id=binding.id,
            lifecycle_name="framework_binding_lifecycle",
            from_state=previous_state,
            to_state=binding.lifecycle_status,
            actor=actor,
            rationale=rationale,
            payload={
                "binding_code": binding.binding_code,
                "framework": binding.framework.code,
                "organization": binding.organization.code,
            },
        )
        return binding

    def list_framework_bindings(self, organization_code: str | None = None) -> list[OrganizationFrameworkBinding]:
        query = select(OrganizationFrameworkBinding).order_by(OrganizationFrameworkBinding.name)
        if organization_code:
            organization = self._organization_by_code(organization_code)
            query = query.where(OrganizationFrameworkBinding.organization_id == organization.id)
        return list(self.session.scalars(query))

    def create_unified_control(
        self,
        code: str,
        name: str,
        description: str = "",
        domain: str = "",
        family: str = "",
        control_type: str = "",
        default_severity: str = "medium",
        implementation_guidance: str = "",
        test_guidance: str = "",
    ) -> UnifiedControl:
        unified_code = _normalize_code(code)
        unified_control = self.session.scalar(select(UnifiedControl).where(UnifiedControl.code == unified_code))
        created = unified_control is None
        if unified_control is None:
            unified_control = UnifiedControl(code=unified_code, name=name)
            self.session.add(unified_control)
        unified_control.name = name
        unified_control.description = description
        unified_control.domain = domain
        unified_control.family = family
        unified_control.control_type = control_type
        unified_control.default_severity = default_severity
        unified_control.implementation_guidance = implementation_guidance
        unified_control.test_guidance = test_guidance
        self.session.flush()
        if created:
            self.lifecycle.record_event(
                entity_type="unified_control",
                entity_id=unified_control.id,
                lifecycle_name="control_lifecycle",
                to_state=unified_control.lifecycle_status,
                actor="workbench_service",
            )
        return unified_control

    def list_unified_controls(self) -> list[UnifiedControl]:
        return list(self.session.scalars(select(UnifiedControl).order_by(UnifiedControl.code)))

    def map_framework_control(
        self,
        unified_control_code: str,
        framework_code: str,
        control_id: str,
        mapping_type: str = "mapped",
        rationale: str = "",
        confidence: float = 1.0,
        inheritance_strategy: str = "manual_review",
        approval_status: str = "proposed",
        reviewed_by: str = "",
        approval_notes: str = "",
    ) -> UnifiedControlMapping:
        unified_control = self._unified_control_by_code(unified_control_code)
        framework = self._framework_by_code(framework_code)
        control = self.session.scalar(
            select(Control).where(Control.framework_id == framework.id, Control.control_id == control_id)
        )
        if control is None:
            raise ValueError(f"Control not found: {framework_code} {control_id}")

        mapping = self.session.scalar(
            select(UnifiedControlMapping).where(
                UnifiedControlMapping.unified_control_id == unified_control.id,
                UnifiedControlMapping.control_id == control.id,
            )
        )
        previous_state = mapping.approval_status if mapping else ""
        if mapping is None:
            mapping = UnifiedControlMapping(
                unified_control_id=unified_control.id,
                framework_id=framework.id,
                control_id=control.id,
            )
            self.session.add(mapping)
        mapping.mapping_type = mapping_type
        mapping.rationale = rationale
        mapping.confidence = confidence
        mapping.inheritance_strategy = inheritance_strategy
        mapping.approval_status = approval_status
        mapping.reviewed_by = reviewed_by
        mapping.approval_notes = approval_notes
        mapping.reviewed_at = datetime.utcnow() if approval_status != "proposed" else None
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="unified_control_mapping",
            entity_id=mapping.id,
            lifecycle_name="control_lifecycle",
            from_state=previous_state,
            to_state=mapping.approval_status,
            actor=reviewed_by or "workbench_service",
            rationale=approval_notes,
            payload={
                "framework": framework.code,
                "control_id": control.control_id,
                "unified_control": unified_control.code,
                "confidence": mapping.confidence,
            },
        )
        return mapping

    def review_mapping(
        self,
        mapping_id: int,
        approval_status: str,
        reviewed_by: str = "",
        approval_notes: str = "",
    ) -> UnifiedControlMapping:
        mapping = self.session.get(UnifiedControlMapping, mapping_id)
        if mapping is None:
            raise ValueError(f"Unified control mapping not found: {mapping_id}")
        previous_state = mapping.approval_status
        self.lifecycle.ensure_transition(
            entity_type="unified_control_mapping",
            lifecycle_name="control_lifecycle",
            from_state=previous_state,
            to_state=approval_status,
        )
        mapping.approval_status = approval_status
        mapping.reviewed_by = reviewed_by
        mapping.approval_notes = approval_notes
        mapping.reviewed_at = datetime.utcnow()
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="unified_control_mapping",
            entity_id=mapping.id,
            lifecycle_name="control_lifecycle",
            from_state=previous_state,
            to_state=mapping.approval_status,
            actor=reviewed_by or "workbench_service",
            payload={
                "framework": mapping.framework.code,
                "control_id": mapping.control.control_id,
                "unified_control": mapping.unified_control.code,
            },
        )
        return mapping

    def upsert_evidence_collection_plan(
        self,
        name: str,
        framework_code: str | None = None,
        control_id: str | None = None,
        unified_control_code: str | None = None,
        plan_code: str | None = None,
        scope_type: str = "binding",
        execution_mode: str = "manual",
        collector_key: str = "",
        evidence_type: str = "configuration_snapshot",
        instructions: str = "",
        expected_artifacts_json: str = "[]",
        review_frequency: str = "",
        minimum_freshness_days: int = 30,
        lifecycle_status: str = "draft",
    ) -> EvidenceCollectionPlan:
        framework = self._framework_by_code(framework_code) if framework_code else None
        control = None
        if framework and control_id:
            control = self.session.scalar(
                select(Control).where(Control.framework_id == framework.id, Control.control_id == control_id)
            )
            if control is None:
                raise ValueError(f"Control not found: {framework_code} {control_id}")
        unified_control = self._unified_control_by_code(unified_control_code) if unified_control_code else None
        resolved_plan_code = _normalize_code(
            plan_code
            or "_".join(
                filter(
                    None,
                    [
                        scope_type,
                        framework.code if framework else "",
                        control.control_id if control else "",
                        unified_control.code if unified_control else "",
                        name,
                    ],
                )
            )
        )
        plan = self.session.scalar(select(EvidenceCollectionPlan).where(EvidenceCollectionPlan.plan_code == resolved_plan_code))
        previous_state = plan.lifecycle_status if plan else ""
        if plan is None:
            plan = EvidenceCollectionPlan(plan_code=resolved_plan_code, name=name)
            self.session.add(plan)
        plan.name = name
        plan.framework_id = framework.id if framework else None
        plan.control_id = control.id if control else None
        plan.unified_control_id = unified_control.id if unified_control else None
        plan.scope_type = scope_type
        plan.execution_mode = execution_mode
        plan.collector_key = collector_key
        plan.evidence_type = evidence_type
        plan.instructions = instructions
        plan.expected_artifacts_json = expected_artifacts_json
        plan.review_frequency = review_frequency
        plan.minimum_freshness_days = minimum_freshness_days
        plan.lifecycle_status = lifecycle_status
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="evidence_collection_plan",
            entity_id=plan.id,
            lifecycle_name="evidence_lifecycle",
            from_state=previous_state,
            to_state=plan.lifecycle_status,
            actor="workbench_service",
            payload={
                "plan_code": plan.plan_code,
                "scope_type": plan.scope_type,
                "execution_mode": plan.execution_mode,
                "collector_key": plan.collector_key,
            },
        )
        return plan

    def list_evidence_collection_plans(
        self,
        framework_code: str | None = None,
        unified_control_code: str | None = None,
    ) -> list[EvidenceCollectionPlan]:
        query = select(EvidenceCollectionPlan).order_by(EvidenceCollectionPlan.updated_at.desc())
        if framework_code:
            framework = self._framework_by_code(framework_code)
            query = query.where(EvidenceCollectionPlan.framework_id == framework.id)
        if unified_control_code:
            unified_control = self._unified_control_by_code(unified_control_code)
            query = query.where(EvidenceCollectionPlan.unified_control_id == unified_control.id)
        return list(self.session.scalars(query))

    def review_evidence_collection_plan(
        self,
        plan_code: str,
        lifecycle_status: str,
        actor: str = "workbench_service",
        rationale: str = "",
    ) -> EvidenceCollectionPlan:
        plan = self.session.scalar(select(EvidenceCollectionPlan).where(EvidenceCollectionPlan.plan_code == plan_code))
        if plan is None:
            raise ValueError(f"Evidence collection plan not found: {plan_code}")
        previous_state = plan.lifecycle_status
        self.lifecycle.ensure_transition(
            entity_type="evidence_collection_plan",
            lifecycle_name="evidence_lifecycle",
            from_state=previous_state,
            to_state=lifecycle_status,
        )
        plan.lifecycle_status = lifecycle_status
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="evidence_collection_plan",
            entity_id=plan.id,
            lifecycle_name="evidence_lifecycle",
            from_state=previous_state,
            to_state=plan.lifecycle_status,
            actor=actor,
            rationale=rationale,
            payload={
                "plan_code": plan.plan_code,
                "scope_type": plan.scope_type,
                "execution_mode": plan.execution_mode,
            },
        )
        return plan

    def upsert_aws_evidence_target(
        self,
        organization_code: str,
        name: str,
        aws_profile: str,
        regions_json: str,
        target_code: str | None = None,
        binding_code: str | None = None,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
        unified_control_code: str | None = None,
        framework_code: str | None = None,
        control_id: str | None = None,
        aws_account_id: str = "",
        role_name: str = "",
        execution_mode: str = "aws_sso_login",
        is_primary: bool = True,
        lifecycle_status: str = "active",
        notes: str = "",
    ) -> AwsEvidenceTarget:
        organization = self._organization_by_code(organization_code)
        binding = self._binding_by_code(binding_code) if binding_code else None
        product = self._product_by_code(organization_code, product_code) if product_code else None
        product_flavor = (
            self._product_flavor_by_code(organization_code, product_code, product_flavor_code)
            if product_code and product_flavor_code
            else None
        )
        unified_control = self._unified_control_by_code(unified_control_code) if unified_control_code else None
        framework = self._framework_by_code(framework_code) if framework_code else None
        control = None
        if framework and control_id:
            control = self.session.scalar(
                select(Control).where(Control.framework_id == framework.id, Control.control_id == control_id)
            )
            if control is None:
                raise ValueError(f"Control not found: {framework_code} {control_id}")

        resolved_target_code = _normalize_code(
            target_code
            or "_".join(
                filter(
                    None,
                    [
                        organization.code,
                        product.code if product else "",
                        product_flavor.code if product_flavor else "",
                        unified_control.code if unified_control else "",
                        control.control_id if control else "",
                        aws_account_id or aws_profile,
                        name,
                    ],
                )
            )
        )

        target = self.session.scalar(select(AwsEvidenceTarget).where(AwsEvidenceTarget.target_code == resolved_target_code))
        previous_state = target.lifecycle_status if target else ""
        if target is None:
            target = AwsEvidenceTarget(
                organization_id=organization.id,
                target_code=resolved_target_code,
                name=name,
                aws_profile=aws_profile,
                regions_json=regions_json,
            )
            self.session.add(target)
        else:
            self.lifecycle.ensure_transition(
                entity_type="aws_evidence_target",
                lifecycle_name="evidence_lifecycle",
                from_state=previous_state,
                to_state=lifecycle_status,
            )

        target.organization_id = organization.id
        target.framework_binding_id = binding.id if binding else None
        target.product_id = product.id if product else None
        target.product_flavor_id = product_flavor.id if product_flavor else None
        target.unified_control_id = unified_control.id if unified_control else None
        target.control_id = control.id if control else None
        target.name = name
        target.aws_profile = aws_profile
        target.aws_account_id = aws_account_id
        target.role_name = role_name
        target.regions_json = regions_json
        target.execution_mode = execution_mode
        target.is_primary = is_primary
        target.lifecycle_status = lifecycle_status
        target.notes = notes
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="aws_evidence_target",
            entity_id=target.id,
            lifecycle_name="evidence_lifecycle",
            from_state=previous_state,
            to_state=target.lifecycle_status,
            actor="workbench_service",
            payload={
                "target_code": target.target_code,
                "aws_profile": target.aws_profile,
                "aws_account_id": target.aws_account_id,
                "execution_mode": target.execution_mode,
            },
        )
        return target

    def review_aws_evidence_target(
        self,
        target_code: str,
        lifecycle_status: str,
        actor: str = "workbench_service",
        rationale: str = "",
    ) -> AwsEvidenceTarget:
        target = self.session.scalar(
            select(AwsEvidenceTarget).where(AwsEvidenceTarget.target_code == _normalize_code(target_code))
        )
        if target is None:
            raise ValueError(f"AWS evidence target not found: {target_code}")
        previous_state = target.lifecycle_status
        self.lifecycle.ensure_transition(
            entity_type="aws_evidence_target",
            lifecycle_name="evidence_lifecycle",
            from_state=previous_state,
            to_state=lifecycle_status,
        )
        target.lifecycle_status = lifecycle_status
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="aws_evidence_target",
            entity_id=target.id,
            lifecycle_name="evidence_lifecycle",
            from_state=previous_state,
            to_state=target.lifecycle_status,
            actor=actor,
            rationale=rationale,
            payload={
                "target_code": target.target_code,
                "aws_profile": target.aws_profile,
                "aws_account_id": target.aws_account_id,
            },
        )
        return target

    def list_aws_evidence_targets(
        self,
        organization_code: str | None = None,
        binding_code: str | None = None,
        product_code: str | None = None,
    ) -> list[AwsEvidenceTarget]:
        query = select(AwsEvidenceTarget).order_by(AwsEvidenceTarget.updated_at.desc(), AwsEvidenceTarget.name)
        if organization_code:
            organization = self._organization_by_code(organization_code)
            query = query.where(AwsEvidenceTarget.organization_id == organization.id)
        if binding_code:
            binding = self._binding_by_code(binding_code)
            query = query.where(AwsEvidenceTarget.framework_binding_id == binding.id)
        if organization_code and product_code:
            product = self._product_by_code(organization_code, product_code)
            query = query.where(AwsEvidenceTarget.product_id == product.id)
        return list(self.session.scalars(query))

    def upsert_control_implementation(
        self,
        organization_code: str,
        title: str,
        product_code: str | None = None,
        product_flavor_code: str | None = None,
        unified_control_code: str | None = None,
        framework_code: str | None = None,
        control_id: str | None = None,
        implementation_code: str | None = None,
        objective: str = "",
        impl_aws: str = "",
        impl_onprem: str = "",
        impl_general: str = "",
        status: str = "draft",
        lifecycle: str = "design",
        owner: str = "",
        priority: str = "medium",
        frequency: str = "",
        test_plan: str = "",
        evidence_links: str = "",
        jira_key: str = "",
        servicenow_ticket: str = "",
        design_doc: str = "",
        blockers: str = "",
        notes: str = "",
    ) -> ControlImplementation:
        organization = self._organization_by_code(organization_code)
        product = self._product_by_code(organization_code, product_code) if product_code else None
        product_flavor = (
            self._product_flavor_by_code(organization_code, product_code, product_flavor_code)
            if product_code and product_flavor_code
            else None
        )
        framework = self._framework_by_code(framework_code) if framework_code else None
        control = None
        if framework and control_id:
            control = self.session.scalar(
                select(Control).where(Control.framework_id == framework.id, Control.control_id == control_id)
            )
            if control is None:
                raise ValueError(f"Control not found: {framework_code} {control_id}")
        unified_control = self._unified_control_by_code(unified_control_code) if unified_control_code else None
        resolved_implementation_code = implementation_code or self._default_implementation_code(
            organization=organization,
            product=product,
            product_flavor=product_flavor,
            unified_control=unified_control,
            framework=framework,
            control=control,
            title=title,
        )

        implementation = None
        if resolved_implementation_code:
            implementation = self.session.scalar(
                select(ControlImplementation).where(
                    ControlImplementation.organization_id == organization.id,
                    ControlImplementation.product_id == (product.id if product else None),
                    ControlImplementation.product_flavor_id == (product_flavor.id if product_flavor else None),
                    ControlImplementation.implementation_code == resolved_implementation_code,
                )
            )
        if implementation is None and control is not None:
            implementation = self.session.scalar(
                select(ControlImplementation).where(
                    ControlImplementation.organization_id == organization.id,
                    ControlImplementation.product_id == (product.id if product else None),
                    ControlImplementation.product_flavor_id == (product_flavor.id if product_flavor else None),
                    ControlImplementation.control_id == control.id,
                )
            )
        if implementation is None and unified_control is not None:
            implementation = self.session.scalar(
                select(ControlImplementation).where(
                    ControlImplementation.organization_id == organization.id,
                    ControlImplementation.product_id == (product.id if product else None),
                    ControlImplementation.product_flavor_id == (product_flavor.id if product_flavor else None),
                    ControlImplementation.unified_control_id == unified_control.id,
                )
            )

        if implementation is None:
            implementation = ControlImplementation(
                organization_id=organization.id,
                product_id=product.id if product else None,
                product_flavor_id=product_flavor.id if product_flavor else None,
                implementation_code=resolved_implementation_code,
            )
            self.session.add(implementation)
            previous_lifecycle = ""
        else:
            previous_lifecycle = implementation.lifecycle

        implementation.product_id = product.id if product else None
        implementation.product_flavor_id = product_flavor.id if product_flavor else None
        implementation.unified_control_id = unified_control.id if unified_control else None
        implementation.framework_id = framework.id if framework else None
        implementation.control_id = control.id if control else None
        implementation.implementation_code = resolved_implementation_code
        implementation.title = title
        implementation.objective = objective
        implementation.impl_aws = impl_aws
        implementation.impl_onprem = impl_onprem
        implementation.impl_general = impl_general
        implementation.status = status
        implementation.lifecycle = lifecycle
        implementation.owner = owner
        implementation.priority = priority
        implementation.frequency = frequency
        implementation.test_plan = test_plan
        implementation.evidence_links = evidence_links
        implementation.jira_key = jira_key
        implementation.servicenow_ticket = servicenow_ticket
        implementation.design_doc = design_doc
        implementation.blockers = blockers
        implementation.notes = notes
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="control_implementation",
            entity_id=implementation.id,
            lifecycle_name="control_lifecycle",
            from_state=previous_lifecycle,
            to_state=implementation.lifecycle,
            actor="workbench_service",
            payload={"status": implementation.status, "implementation_code": implementation.implementation_code},
        )
        return implementation

    def list_control_implementations(self, organization_code: str | None = None) -> list[ControlImplementation]:
        query = select(ControlImplementation).order_by(ControlImplementation.updated_at.desc())
        if organization_code:
            organization = self._organization_by_code(organization_code)
            query = query.where(ControlImplementation.organization_id == organization.id)
        return list(self.session.scalars(query))

    def upsert_product_control_profile(
        self,
        organization_code: str,
        product_code: str,
        unified_control_code: str | None = None,
        framework_code: str | None = None,
        control_id: str | None = None,
        product_flavor_code: str | None = None,
        applicability_status: str = "applicable",
        implementation_status: str = "planned",
        assessment_mode: str = "manual",
        maturity_governance: int = 1,
        maturity_implementation: int = 1,
        maturity_observability: int = 1,
        maturity_automation: int = 1,
        maturity_assurance: int = 1,
        rationale: str = "",
        evidence_strategy: str = "",
        review_notes: str = "",
    ) -> ProductControlProfile:
        organization = self._organization_by_code(organization_code)
        product = self._product_by_code(organization_code, product_code)
        product_flavor = (
            self._product_flavor_by_code(organization_code, product_code, product_flavor_code)
            if product_flavor_code
            else None
        )
        unified_control = self._unified_control_by_code(unified_control_code) if unified_control_code else None
        framework = self._framework_by_code(framework_code) if framework_code else None
        control = None
        if framework and control_id:
            control = self.session.scalar(
                select(Control).where(Control.framework_id == framework.id, Control.control_id == control_id)
            )
            if control is None:
                raise ValueError(f"Control not found: {framework_code} {control_id}")

        profile = self.session.scalar(
            select(ProductControlProfile).where(
                ProductControlProfile.organization_id == organization.id,
                ProductControlProfile.product_id == product.id,
                ProductControlProfile.product_flavor_id == (product_flavor.id if product_flavor else None),
                ProductControlProfile.unified_control_id == (unified_control.id if unified_control else None),
                ProductControlProfile.control_id == (control.id if control else None),
            )
        )
        if profile is None:
            profile = ProductControlProfile(
                organization_id=organization.id,
                product_id=product.id,
                product_flavor_id=product_flavor.id if product_flavor else None,
            )
            self.session.add(profile)
            previous_assurance_status = ""
        else:
            previous_assurance_status = profile.assurance_status

        matching_implementation = self._find_matching_implementation(
            organization_id=organization.id,
            product_id=product.id,
            product_flavor_id=product_flavor.id if product_flavor else None,
            unified_control_id=unified_control.id if unified_control else None,
            control_id=control.id if control else None,
        )

        maturity_values = [
            maturity_governance,
            maturity_implementation,
            maturity_observability,
            maturity_automation,
            maturity_assurance,
        ]
        average = round(sum(maturity_values) / len(maturity_values))

        profile.unified_control_id = unified_control.id if unified_control else None
        profile.framework_id = framework.id if framework else None
        profile.control_id = control.id if control else None
        profile.control_implementation_id = matching_implementation.id if matching_implementation else None
        profile.applicability_status = applicability_status
        profile.implementation_status = implementation_status
        profile.assessment_mode = assessment_mode
        profile.assurance_status = self._assurance_status(average, assessment_mode)
        profile.maturity_governance = maturity_governance
        profile.maturity_implementation = maturity_implementation
        profile.maturity_observability = maturity_observability
        profile.maturity_automation = maturity_automation
        profile.maturity_assurance = maturity_assurance
        profile.maturity_level = average
        profile.autonomy_recommendation = self._autonomy_recommendation(average, maturity_automation, maturity_assurance)
        profile.rationale = rationale
        profile.evidence_strategy = evidence_strategy
        profile.review_notes = review_notes
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="product_control_profile",
            entity_id=profile.id,
            lifecycle_name="assurance_lifecycle",
            from_state=previous_assurance_status,
            to_state=profile.assurance_status,
            actor="workbench_service",
            payload={
                "assessment_mode": profile.assessment_mode,
                "autonomy_recommendation": profile.autonomy_recommendation,
                "maturity_level": profile.maturity_level,
            },
        )
        return profile

    def list_product_control_profiles(
        self,
        organization_code: str,
        product_code: str,
        product_flavor_code: str | None = None,
    ) -> list[ProductControlProfile]:
        product = self._product_by_code(organization_code, product_code)
        query = select(ProductControlProfile).where(ProductControlProfile.product_id == product.id)
        if product_flavor_code:
            flavor = self._product_flavor_by_code(organization_code, product_code, product_flavor_code)
            query = query.where(ProductControlProfile.product_flavor_id == flavor.id)
        return list(self.session.scalars(query.order_by(ProductControlProfile.updated_at.desc())))

    def create_questionnaire(
        self,
        organization_code: str,
        product_code: str,
        name: str,
        customer_name: str = "",
        product_flavor_code: str | None = None,
        source_type: str = "csv",
        source_name: str = "",
    ) -> CustomerQuestionnaire:
        organization = self._organization_by_code(organization_code)
        product = self._product_by_code(organization_code, product_code)
        product_flavor = (
            self._product_flavor_by_code(organization_code, product_code, product_flavor_code)
            if product_flavor_code
            else None
        )
        questionnaire = CustomerQuestionnaire(
            organization_id=organization.id,
            product_id=product.id,
            product_flavor_id=product_flavor.id if product_flavor else None,
            name=name,
            customer_name=customer_name,
            source_type=source_type,
            source_name=source_name,
        )
        self.session.add(questionnaire)
        self.session.flush()
        self.lifecycle.record_event(
            entity_type="customer_questionnaire",
            entity_id=questionnaire.id,
            lifecycle_name="assurance_lifecycle",
            to_state=questionnaire.status,
            actor="workbench_service",
        )
        return questionnaire

    def add_questionnaire_item(
        self,
        questionnaire_id: int,
        question_text: str,
        external_id: str = "",
        section: str = "",
        normalized_question: str = "",
        suggested_answer: str = "",
        rationale: str = "",
        confidence: float = 0.0,
    ) -> CustomerQuestionnaireItem:
        item = CustomerQuestionnaireItem(
            questionnaire_id=questionnaire_id,
            external_id=external_id,
            section=section,
            question_text=question_text,
            normalized_question=normalized_question,
            suggested_answer=suggested_answer,
            rationale=rationale,
            confidence=confidence,
        )
        self.session.add(item)
        self.session.flush()
        return item

    def _organization_by_code(self, code: str) -> Organization:
        organization = self.session.scalar(select(Organization).where(Organization.code == _normalize_code(code)))
        if organization is None:
            raise ValueError(f"Organization not found: {code}")
        return organization

    def _framework_by_code(self, code: str) -> Framework:
        framework = self.session.scalar(select(Framework).where(Framework.code == code))
        if framework is None:
            raise ValueError(f"Framework not found: {code}")
        return framework

    def _product_by_code(self, organization_code: str, product_code: str) -> Product:
        organization = self._organization_by_code(organization_code)
        product = self.session.scalar(
            select(Product).where(Product.organization_id == organization.id, Product.code == _normalize_code(product_code))
        )
        if product is None:
            raise ValueError(f"Product not found: {product_code}")
        return product

    def _product_flavor_by_code(self, organization_code: str, product_code: str, flavor_code: str) -> ProductFlavor:
        product = self._product_by_code(organization_code, product_code)
        flavor = self.session.scalar(
            select(ProductFlavor).where(ProductFlavor.product_id == product.id, ProductFlavor.code == _normalize_code(flavor_code))
        )
        if flavor is None:
            raise ValueError(f"Product flavor not found: {flavor_code}")
        return flavor

    def _unified_control_by_code(self, code: str) -> UnifiedControl:
        unified_control = self.session.scalar(select(UnifiedControl).where(UnifiedControl.code == _normalize_code(code)))
        if unified_control is None:
            raise ValueError(f"Unified control not found: {code}")
        return unified_control

    def _confluence_connection_by_name(self, name: str) -> ConfluenceConnection:
        connection = self.session.scalar(select(ConfluenceConnection).where(ConfluenceConnection.name == name))
        if connection is None:
            raise ValueError(f"Confluence connection not found: {name}")
        return connection

    def _binding_by_code(self, code: str) -> OrganizationFrameworkBinding:
        binding = self.session.scalar(
            select(OrganizationFrameworkBinding).where(OrganizationFrameworkBinding.binding_code == _normalize_code(code))
        )
        if binding is None:
            raise ValueError(f"Framework binding not found: {code}")
        return binding

    def _find_matching_implementation(
        self,
        organization_id: int,
        product_id: int,
        product_flavor_id: int | None,
        unified_control_id: int | None,
        control_id: int | None,
    ) -> ControlImplementation | None:
        exact_query = select(ControlImplementation).where(
            ControlImplementation.organization_id == organization_id,
            ControlImplementation.product_id == product_id,
            ControlImplementation.product_flavor_id == product_flavor_id,
        )
        if control_id is not None:
            exact_query = exact_query.where(ControlImplementation.control_id == control_id)
        elif unified_control_id is not None:
            exact_query = exact_query.where(ControlImplementation.unified_control_id == unified_control_id)
        else:
            return None
        implementation = self.session.scalar(exact_query.order_by(ControlImplementation.updated_at.desc()))
        if implementation is not None or product_flavor_id is None:
            return implementation

        fallback_query = select(ControlImplementation).where(
            ControlImplementation.organization_id == organization_id,
            ControlImplementation.product_id == product_id,
            ControlImplementation.product_flavor_id.is_(None),
        )
        if control_id is not None:
            fallback_query = fallback_query.where(ControlImplementation.control_id == control_id)
        else:
            fallback_query = fallback_query.where(ControlImplementation.unified_control_id == unified_control_id)
        return self.session.scalar(fallback_query.order_by(ControlImplementation.updated_at.desc()))

    @staticmethod
    def _default_implementation_code(
        organization: Organization,
        product: Product | None,
        product_flavor: ProductFlavor | None,
        unified_control: UnifiedControl | None,
        framework: Framework | None,
        control: Control | None,
        title: str,
    ) -> str:
        parts = [
            organization.code,
            product.code if product else "GLOBAL",
            product_flavor.code if product_flavor else "DEFAULT",
        ]
        if unified_control is not None:
            parts.append(unified_control.code)
        elif framework is not None and control is not None:
            parts.extend([framework.code, control.control_id])
        else:
            parts.append(title)
        return _normalize_code("_".join(filter(None, parts)))

    @staticmethod
    def _assurance_status(maturity_level: int, assessment_mode: str) -> str:
        if assessment_mode == "autonomous" and maturity_level >= 4:
            return "continuously_assured"
        if assessment_mode in {"assisted", "autonomous"} and maturity_level >= 3:
            return "partially_assured"
        if maturity_level >= 2:
            return "planned_assurance"
        return "not_assured"

    @staticmethod
    def _autonomy_recommendation(maturity_level: int, automation: int, assurance: int) -> str:
        if maturity_level >= 5 and automation >= 4 and assurance >= 4:
            return "autonomous_assessment_ready"
        if maturity_level >= 4 and automation >= 3:
            return "assisted_autonomy"
        if maturity_level >= 3:
            return "manual_with_assistance"
        return "manual_only"
