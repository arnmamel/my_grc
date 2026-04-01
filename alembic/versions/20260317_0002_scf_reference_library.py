"""Add SCF reference library and import enrichment tables.

Revision ID: 20260317_0002
Revises: 20260314_0001
Create Date: 2026-03-17 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260317_0002"
down_revision = "20260314_0001"
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    if "reference_documents" not in _table_names(bind):
        op.create_table(
            "reference_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_key", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("short_name", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("version", sa.String(length=100), nullable=False, server_default=""),
            sa.Column("issuing_body", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("document_type", sa.String(length=64), nullable=False, server_default="reference"),
            sa.Column("jurisdiction", sa.String(length=100), nullable=False, server_default="global"),
            sa.Column("citation_format", sa.Text(), nullable=False, server_default=""),
            sa.Column("source_url", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("document_key", name="uq_reference_documents_document_key"),
        )
    if "ix_reference_documents_document_key" not in _index_names(bind, "reference_documents"):
        op.create_index(
            "ix_reference_documents_document_key",
            "reference_documents",
            ["document_key"],
            unique=True,
        )

    if "imported_requirement_references" not in _table_names(bind):
        op.create_table(
            "imported_requirement_references",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("imported_requirement_id", sa.Integer(), nullable=False),
            sa.Column("reference_document_id", sa.Integer(), nullable=False),
            sa.Column("reference_code", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("reference_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("relationship_type", sa.String(length=64), nullable=False, server_default="mapped_requirement"),
            sa.Column("raw_value", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["imported_requirement_id"], ["imported_requirements.id"]),
            sa.ForeignKeyConstraint(["reference_document_id"], ["reference_documents.id"]),
            sa.UniqueConstraint(
                "imported_requirement_id",
                "reference_document_id",
                "reference_code",
                "relationship_type",
                name="uq_imported_requirement_reference",
            ),
        )
        op.create_index(
            "ix_imported_requirement_references_imported_requirement_id",
            "imported_requirement_references",
            ["imported_requirement_id"],
            unique=False,
        )
        op.create_index(
            "ix_imported_requirement_references_reference_document_id",
            "imported_requirement_references",
            ["reference_document_id"],
            unique=False,
        )

    if "unified_control_references" not in _table_names(bind):
        op.create_table(
            "unified_control_references",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("unified_control_id", sa.Integer(), nullable=False),
            sa.Column("reference_document_id", sa.Integer(), nullable=False),
            sa.Column("framework_id", sa.Integer(), nullable=True),
            sa.Column("control_id", sa.Integer(), nullable=True),
            sa.Column("imported_requirement_id", sa.Integer(), nullable=True),
            sa.Column("reference_code", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("reference_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("relationship_type", sa.String(length=64), nullable=False, server_default="mapped_requirement"),
            sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["unified_control_id"], ["unified_controls.id"]),
            sa.ForeignKeyConstraint(["reference_document_id"], ["reference_documents.id"]),
            sa.ForeignKeyConstraint(["framework_id"], ["frameworks.id"]),
            sa.ForeignKeyConstraint(["control_id"], ["controls.id"]),
            sa.ForeignKeyConstraint(["imported_requirement_id"], ["imported_requirements.id"]),
            sa.UniqueConstraint(
                "unified_control_id",
                "reference_document_id",
                "reference_code",
                "relationship_type",
                name="uq_unified_control_reference",
            ),
        )
        op.create_index(
            "ix_unified_control_references_unified_control_id",
            "unified_control_references",
            ["unified_control_id"],
            unique=False,
        )
        op.create_index(
            "ix_unified_control_references_reference_document_id",
            "unified_control_references",
            ["reference_document_id"],
            unique=False,
        )
        op.create_index("ix_unified_control_references_framework_id", "unified_control_references", ["framework_id"])
        op.create_index("ix_unified_control_references_control_id", "unified_control_references", ["control_id"])
        op.create_index(
            "ix_unified_control_references_imported_requirement_id",
            "unified_control_references",
            ["imported_requirement_id"],
        )

    if "framework_import_batches" in _table_names(bind):
        columns = _column_names(bind, "framework_import_batches")
        if "created_reference_documents" not in columns:
            op.add_column(
                "framework_import_batches",
                sa.Column("created_reference_documents", sa.Integer(), nullable=False, server_default="0"),
            )
        if "created_reference_links" not in columns:
            op.add_column(
                "framework_import_batches",
                sa.Column("created_reference_links", sa.Integer(), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    bind = op.get_bind()

    if "framework_import_batches" in _table_names(bind):
        columns = _column_names(bind, "framework_import_batches")
        with op.batch_alter_table("framework_import_batches") as batch_op:
            if "created_reference_documents" in columns:
                batch_op.drop_column("created_reference_documents")
            if "created_reference_links" in columns:
                batch_op.drop_column("created_reference_links")

    if "unified_control_references" in _table_names(bind):
        op.drop_table("unified_control_references")
    if "imported_requirement_references" in _table_names(bind):
        op.drop_table("imported_requirement_references")
    if "reference_documents" in _table_names(bind):
        op.drop_table("reference_documents")
