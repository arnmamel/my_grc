"""Initial schema baseline.

Revision ID: 20260314_0001
Revises:
Create Date: 2026-03-14 14:30:00
"""

from __future__ import annotations

from alembic import op

from aws_local_audit import models  # noqa: F401
from aws_local_audit.db import Base

revision = "20260314_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
