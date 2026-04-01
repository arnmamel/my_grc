"""Add RBAC and access-governance foundation tables.

Revision ID: 20260317_0004
Revises: 20260317_0003
Create Date: 2026-03-17 19:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260317_0004"
down_revision = "20260317_0003"
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "identity_principals" not in tables:
        op.create_table(
            "identity_principals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("principal_key", sa.String(length=150), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("principal_type", sa.String(length=32), nullable=False, server_default="human"),
            sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("external_id", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("source_system", sa.String(length=100), nullable=False, server_default="local"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.UniqueConstraint("principal_key", name="uq_identity_principals_principal_key"),
        )
        op.create_index("ix_identity_principals_organization_id", "identity_principals", ["organization_id"])
        op.create_index("ix_identity_principals_principal_key", "identity_principals", ["principal_key"], unique=True)

    if "access_roles" not in tables:
        op.create_table(
            "access_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role_key", sa.String(length=100), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("scope_type", sa.String(length=64), nullable=False, server_default="organization"),
            sa.Column("permissions_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("role_key", name="uq_access_roles_role_key"),
        )
        op.create_index("ix_access_roles_role_key", "access_roles", ["role_key"], unique=True)

    if "role_assignments" not in tables:
        op.create_table(
            "role_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("principal_id", sa.Integer(), nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("business_unit_id", sa.Integer(), nullable=True),
            sa.Column("product_id", sa.Integer(), nullable=True),
            sa.Column("framework_binding_id", sa.Integer(), nullable=True),
            sa.Column("assignment_source", sa.String(length=64), nullable=False, server_default="manual"),
            sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="approved"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("assigned_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("approved_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["principal_id"], ["identity_principals.id"]),
            sa.ForeignKeyConstraint(["role_id"], ["access_roles.id"]),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["business_unit_id"], ["business_units.id"]),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.ForeignKeyConstraint(["framework_binding_id"], ["organization_framework_bindings.id"]),
        )
        op.create_index("ix_role_assignments_principal_id", "role_assignments", ["principal_id"])
        op.create_index("ix_role_assignments_role_id", "role_assignments", ["role_id"])
        op.create_index("ix_role_assignments_organization_id", "role_assignments", ["organization_id"])
        op.create_index("ix_role_assignments_business_unit_id", "role_assignments", ["business_unit_id"])
        op.create_index("ix_role_assignments_product_id", "role_assignments", ["product_id"])
        op.create_index("ix_role_assignments_framework_binding_id", "role_assignments", ["framework_binding_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    for table_name in ["role_assignments", "access_roles", "identity_principals"]:
        if table_name in tables:
            op.drop_table(table_name)
