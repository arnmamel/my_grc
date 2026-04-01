"""Add workspace credential table.

Revision ID: 20260320_0007
Revises: 20260320_0006
Create Date: 2026-03-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260320_0007"
down_revision = "20260320_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "workspace_credentials" in tables:
        return
    op.create_table(
        "workspace_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("principal_id", sa.Integer(), sa.ForeignKey("identity_principals.id"), nullable=False),
        sa.Column("auth_mode", sa.String(length=32), nullable=False, server_default="local_password"),
        sa.Column("password_salt", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("password_iterations", sa.Integer(), nullable=False, server_default="390000"),
        sa.Column("password_changed_at", sa.DateTime(), nullable=True),
        sa.Column("password_expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_authenticated_at", sa.DateTime(), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workspace_credentials_principal_id", "workspace_credentials", ["principal_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "workspace_credentials" not in tables:
        return
    index_names = {item["name"] for item in inspector.get_indexes("workspace_credentials")}
    if "ix_workspace_credentials_principal_id" in index_names:
        op.drop_index("ix_workspace_credentials_principal_id", table_name="workspace_credentials")
    op.drop_table("workspace_credentials")
