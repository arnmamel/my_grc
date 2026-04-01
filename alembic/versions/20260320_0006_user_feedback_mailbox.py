"""Add user feedback mailbox table.

Revision ID: 20260320_0006
Revises: 20260319_0005
Create Date: 2026-03-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260320_0006"
down_revision = "20260319_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "user_feedback_messages" in tables:
        return
    op.create_table(
        "user_feedback_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version_label", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("reporter_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("reporter_role", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("contact", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("area", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("page_context", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("subject", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_feedback_messages" in set(inspector.get_table_names()):
        op.drop_table("user_feedback_messages")
