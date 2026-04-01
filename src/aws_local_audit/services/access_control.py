from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, select

from aws_local_audit.logging_utils import audit_event
from aws_local_audit.models import AccessRole, IdentityPrincipal, RoleAssignment


@dataclass(frozen=True, slots=True)
class RoleTemplate:
    role_key: str
    name: str
    description: str
    scope_type: str
    permissions: tuple[str, ...]
    approval_required: bool = False


DEFAULT_ROLE_TEMPLATES: tuple[RoleTemplate, ...] = (
    RoleTemplate(
        role_key="org_admin",
        name="Organization Admin",
        description="Full governance administration for an organization and its scoped GRC records.",
        scope_type="organization",
        permissions=(
            "framework.*",
            "mapping.*",
            "portfolio.*",
            "evidence.*",
            "assessment.*",
            "questionnaire.*",
            "rbac.*",
        ),
        approval_required=True,
    ),
    RoleTemplate(
        role_key="bu_owner",
        name="Business Unit Owner",
        description="Manage risks, findings, actions, and scoped product governance within a business unit.",
        scope_type="business_unit",
        permissions=("portfolio.read", "risk.*", "finding.*", "action.*", "assessment.read"),
    ),
    RoleTemplate(
        role_key="control_owner",
        name="Control Owner",
        description="Design and operate control implementations, evidence collection, and implementation updates.",
        scope_type="product",
        permissions=("control.read", "implementation.*", "evidence.collect", "evidence.submit", "assessment.read"),
    ),
    RoleTemplate(
        role_key="auditor",
        name="Auditor",
        description="Read-only oversight for assessments, evidence, lifecycle history, and control status.",
        scope_type="organization",
        permissions=("framework.read", "control.read", "assessment.read", "evidence.read", "lifecycle.read"),
        approval_required=True,
    ),
    RoleTemplate(
        role_key="approval_manager",
        name="Approval Manager",
        description="Approve mappings, evidence, questionnaires, and assessments with separation of duties.",
        scope_type="organization",
        permissions=("mapping.approve", "evidence.review", "questionnaire.approve", "assessment.approve"),
        approval_required=True,
    ),
    RoleTemplate(
        role_key="evidence_contributor",
        name="Evidence Contributor",
        description="Provide manual evidence and maintain supporting artifacts for scoped controls.",
        scope_type="product",
        permissions=("evidence.collect", "evidence.submit", "artifact.upload"),
    ),
    RoleTemplate(
        role_key="read_only",
        name="Read Only",
        description="View dashboards, controls, evidence, assessments, and portfolio records without changing them.",
        scope_type="organization",
        permissions=("framework.read", "control.read", "assessment.read", "evidence.read", "portfolio.read"),
    ),
)

CONFLICTING_ROLE_PAIRS: tuple[tuple[str, str], ...] = (
    ("org_admin", "auditor"),
    ("control_owner", "auditor"),
    ("evidence_contributor", "approval_manager"),
)


class AccessControlService:
    def __init__(self, session):
        self.session = session

    def seed_default_roles(self) -> int:
        created = 0
        for item in DEFAULT_ROLE_TEMPLATES:
            existing = self.session.scalar(select(AccessRole).where(AccessRole.role_key == item.role_key))
            if existing is None:
                self.session.add(
                    AccessRole(
                        role_key=item.role_key,
                        name=item.name,
                        description=item.description,
                        scope_type=item.scope_type,
                        permissions_json=json.dumps(list(item.permissions)),
                        builtin=True,
                        approval_required=item.approval_required,
                    )
                )
                created += 1
            else:
                existing.name = item.name
                existing.description = item.description
                existing.scope_type = item.scope_type
                existing.permissions_json = json.dumps(list(item.permissions))
                existing.builtin = True
                existing.approval_required = item.approval_required
        self.session.flush()
        return created

    def upsert_principal(
        self,
        *,
        principal_key: str,
        display_name: str,
        principal_type: str = "human",
        organization_id: int | None = None,
        email: str = "",
        external_id: str = "",
        source_system: str = "local",
        status: str = "active",
    ) -> IdentityPrincipal:
        principal = self.session.scalar(select(IdentityPrincipal).where(IdentityPrincipal.principal_key == principal_key))
        if principal is None:
            principal = IdentityPrincipal(principal_key=principal_key, display_name=display_name)
            self.session.add(principal)
        principal.display_name = display_name
        principal.principal_type = principal_type
        principal.organization_id = organization_id
        principal.email = email
        principal.external_id = external_id
        principal.source_system = source_system
        principal.status = status
        self.session.flush()
        return principal

    def assign_role(
        self,
        *,
        principal_key: str,
        role_key: str,
        actor: str,
        organization_id: int | None = None,
        business_unit_id: int | None = None,
        product_id: int | None = None,
        framework_binding_id: int | None = None,
        assignment_source: str = "manual",
        approval_status: str | None = None,
        approved_by: str = "",
        rationale: str = "",
        expires_at: datetime | None = None,
    ) -> RoleAssignment:
        principal = self.session.scalar(select(IdentityPrincipal).where(IdentityPrincipal.principal_key == principal_key))
        if principal is None:
            raise ValueError(f"Unknown principal `{principal_key}`.")
        role = self.session.scalar(select(AccessRole).where(AccessRole.role_key == role_key))
        if role is None:
            raise ValueError(f"Unknown role `{role_key}`.")
        self._validate_scope(
            role,
            organization_id=organization_id,
            business_unit_id=business_unit_id,
            product_id=product_id,
            framework_binding_id=framework_binding_id,
        )
        assignment = self._find_assignment(
            principal_id=principal.id,
            role_id=role.id,
            organization_id=organization_id,
            business_unit_id=business_unit_id,
            product_id=product_id,
            framework_binding_id=framework_binding_id,
        )
        if assignment is None:
            assignment = RoleAssignment(principal_id=principal.id, role_id=role.id)
            self.session.add(assignment)
        assignment.organization_id = organization_id
        assignment.business_unit_id = business_unit_id
        assignment.product_id = product_id
        assignment.framework_binding_id = framework_binding_id
        assignment.assignment_source = assignment_source
        assignment.approval_status = approval_status or ("pending_review" if role.approval_required and not approved_by else "approved")
        assignment.status = "active"
        assignment.assigned_by = actor
        assignment.approved_by = approved_by
        assignment.rationale = rationale
        assignment.expires_at = expires_at
        self.session.flush()
        audit_event(
            action="role_assignment_upserted",
            actor=actor,
            target_type="role_assignment",
            target_id=str(assignment.id),
            status="success",
            details={
                "principal_key": principal.principal_key,
                "role_key": role.role_key,
                "approval_status": assignment.approval_status,
            },
        )
        return assignment

    def approve_assignment(self, assignment_id: int, *, approver: str) -> RoleAssignment:
        assignment = self.session.get(RoleAssignment, assignment_id)
        if assignment is None:
            raise ValueError(f"Unknown role assignment `{assignment_id}`.")
        assignment.approval_status = "approved"
        assignment.approved_by = approver
        self.session.flush()
        audit_event(
            action="role_assignment_approved",
            actor=approver,
            target_type="role_assignment",
            target_id=str(assignment.id),
            status="success",
        )
        return assignment

    def list_roles(self) -> list[AccessRole]:
        return list(self.session.scalars(select(AccessRole).order_by(AccessRole.role_key)))

    def list_principals(self) -> list[IdentityPrincipal]:
        return list(self.session.scalars(select(IdentityPrincipal).order_by(IdentityPrincipal.principal_key)))

    def list_assignments(self) -> list[RoleAssignment]:
        return list(self.session.scalars(select(RoleAssignment).order_by(RoleAssignment.id)))

    def effective_permissions(self, principal_key: str, scope: dict | None = None) -> set[str]:
        principal = self.session.scalar(select(IdentityPrincipal).where(IdentityPrincipal.principal_key == principal_key))
        if principal is None or principal.status != "active":
            return set()
        permissions: set[str] = set()
        for assignment in self._active_assignments(principal.id):
            if not self._scope_matches(assignment, scope or {}):
                continue
            permissions.update(self._role_permissions(assignment.role))
        return permissions

    def can(self, principal_key: str, permission: str, scope: dict | None = None) -> bool:
        for granted in self.effective_permissions(principal_key, scope):
            if granted == "*" or granted == permission:
                return True
            if granted.endswith(".*") and permission.startswith(f"{granted[:-2]}."):
                return True
        return False

    def pending_assignments(self) -> list[RoleAssignment]:
        return list(
            self.session.scalars(
                select(RoleAssignment).where(RoleAssignment.approval_status != "approved").order_by(RoleAssignment.id)
            )
        )

    def segregation_conflicts(self) -> list[dict]:
        rows = []
        for principal in self.list_principals():
            assignments = [
                item for item in self._active_assignments(principal.id) if item.approval_status == "approved"
            ]
            for index, left_assignment in enumerate(assignments):
                for right_assignment in assignments[index + 1 :]:
                    left_key = left_assignment.role.role_key
                    right_key = right_assignment.role.role_key
                    if not self._roles_conflict(left_key, right_key):
                        continue
                    if not self._scopes_overlap(left_assignment, right_assignment):
                        continue
                    scope = self._merged_scope(left_assignment, right_assignment)
                    rows.append(
                        {
                            "principal_key": principal.principal_key,
                            "display_name": principal.display_name,
                            "scope": scope,
                            "roles": sorted([left_key, right_key]),
                            "detail": f"{principal.display_name} holds conflicting roles `{left_key}` and `{right_key}` in overlapping scope.",
                        }
                    )
        return rows

    def _active_assignments(self, principal_id: int) -> list[RoleAssignment]:
        now = datetime.utcnow()
        rows = self.session.scalars(
            select(RoleAssignment).where(
                RoleAssignment.principal_id == principal_id,
                RoleAssignment.status == "active",
            )
        ).all()
        return [item for item in rows if item.expires_at is None or item.expires_at > now]

    def _find_assignment(
        self,
        *,
        principal_id: int,
        role_id: int,
        organization_id: int | None,
        business_unit_id: int | None,
        product_id: int | None,
        framework_binding_id: int | None,
    ) -> RoleAssignment | None:
        query = select(RoleAssignment).where(
            RoleAssignment.principal_id == principal_id,
            RoleAssignment.role_id == role_id,
        )
        query = self._scope_filters(
            query,
            organization_id=organization_id,
            business_unit_id=business_unit_id,
            product_id=product_id,
            framework_binding_id=framework_binding_id,
        )
        return self.session.scalar(query)

    def _scope_filters(
        self,
        query: Select,
        *,
        organization_id: int | None,
        business_unit_id: int | None,
        product_id: int | None,
        framework_binding_id: int | None,
    ) -> Select:
        scope_pairs = (
            (RoleAssignment.organization_id, organization_id),
            (RoleAssignment.business_unit_id, business_unit_id),
            (RoleAssignment.product_id, product_id),
            (RoleAssignment.framework_binding_id, framework_binding_id),
        )
        for column, value in scope_pairs:
            query = query.where(column.is_(None) if value is None else column == value)
        return query

    @staticmethod
    def _validate_scope(
        role: AccessRole,
        *,
        organization_id: int | None,
        business_unit_id: int | None,
        product_id: int | None,
        framework_binding_id: int | None,
    ) -> None:
        if role.scope_type == "organization" and organization_id is None:
            raise ValueError(f"Role `{role.role_key}` requires organization scope.")
        if role.scope_type == "business_unit" and business_unit_id is None:
            raise ValueError(f"Role `{role.role_key}` requires business-unit scope.")
        if role.scope_type == "product" and product_id is None:
            raise ValueError(f"Role `{role.role_key}` requires product scope.")
        if framework_binding_id is not None and organization_id is None:
            raise ValueError("Framework-binding scope also requires organization scope.")

    @staticmethod
    def _role_permissions(role: AccessRole) -> set[str]:
        if not role.permissions_json:
            return set()
        try:
            values = json.loads(role.permissions_json)
        except json.JSONDecodeError:
            return set()
        return {str(item) for item in values}

    @staticmethod
    def _scope_matches(assignment: RoleAssignment, scope: dict) -> bool:
        checks = (
            ("organization_id", assignment.organization_id),
            ("business_unit_id", assignment.business_unit_id),
            ("product_id", assignment.product_id),
            ("framework_binding_id", assignment.framework_binding_id),
        )
        for key, value in checks:
            scope_value = scope.get(key)
            if value is None:
                continue
            if scope_value != value:
                return False
        return True

    @staticmethod
    def _roles_conflict(left_role_key: str, right_role_key: str) -> bool:
        pair = {left_role_key, right_role_key}
        return any(pair == {left, right} for left, right in CONFLICTING_ROLE_PAIRS)

    @staticmethod
    def _scopes_overlap(left: RoleAssignment, right: RoleAssignment) -> bool:
        for left_value, right_value in (
            (left.organization_id, right.organization_id),
            (left.business_unit_id, right.business_unit_id),
            (left.product_id, right.product_id),
            (left.framework_binding_id, right.framework_binding_id),
        ):
            if left_value is not None and right_value is not None and left_value != right_value:
                return False
        return True

    @staticmethod
    def _merged_scope(left: RoleAssignment, right: RoleAssignment) -> dict[str, int | None]:
        return {
            "organization_id": left.organization_id or right.organization_id,
            "business_unit_id": left.business_unit_id or right.business_unit_id,
            "product_id": left.product_id or right.product_id,
            "framework_binding_id": left.framework_binding_id or right.framework_binding_id,
        }
