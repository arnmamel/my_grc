"""Add governed AI knowledge pack entities.

Revision ID: 20260319_0005
Revises: 20260317_0004
Create Date: 2026-03-19 10:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260319_0005"
down_revision = "20260317_0004"
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(bind).get_indexes(table_name)}


def _foreign_key_names(bind, table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(bind).get_foreign_keys(table_name) if item.get("name")}


def _is_sqlite(bind) -> bool:
    return bind.dialect.name == "sqlite"


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "ai_knowledge_packs" not in tables:
        op.create_table(
            "ai_knowledge_packs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("pack_code", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("domain", sa.String(length=100), nullable=False, server_default="compliance_copilot"),
            sa.Column("scope_type", sa.String(length=64), nullable=False, server_default="cross_framework"),
            sa.Column("owner", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="proposed"),
            sa.Column("default_task_key", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("pack_code", name="uq_ai_knowledge_packs_pack_code"),
        )
        op.create_index("ix_ai_knowledge_packs_pack_code", "ai_knowledge_packs", ["pack_code"], unique=True)

    if "ai_knowledge_pack_versions" not in tables:
        op.create_table(
            "ai_knowledge_pack_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("knowledge_pack_id", sa.Integer(), nullable=False),
            sa.Column("version_label", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("system_instruction", sa.Text(), nullable=False, server_default=""),
            sa.Column("operating_principles_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("prompt_contract_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("output_contract_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("model_constraints_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("approved_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["knowledge_pack_id"], ["ai_knowledge_packs.id"]),
            sa.UniqueConstraint("knowledge_pack_id", "version_label", name="uq_ai_pack_version_label"),
        )
        op.create_index("ix_ai_knowledge_pack_versions_knowledge_pack_id", "ai_knowledge_pack_versions", ["knowledge_pack_id"])
        op.create_index("ix_ai_knowledge_pack_versions_version_label", "ai_knowledge_pack_versions", ["version_label"])

    if "ai_knowledge_pack_tasks" not in tables:
        op.create_table(
            "ai_knowledge_pack_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("knowledge_pack_version_id", sa.Integer(), nullable=False),
            sa.Column("task_key", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("workflow_area", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("objective", sa.Text(), nullable=False, server_default=""),
            sa.Column("input_schema_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("output_schema_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("instruction_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("review_checklist_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["knowledge_pack_version_id"], ["ai_knowledge_pack_versions.id"]),
            sa.UniqueConstraint("knowledge_pack_version_id", "task_key", name="uq_ai_pack_task_key"),
        )
        op.create_index("ix_ai_knowledge_pack_tasks_knowledge_pack_version_id", "ai_knowledge_pack_tasks", ["knowledge_pack_version_id"])
        op.create_index("ix_ai_knowledge_pack_tasks_task_key", "ai_knowledge_pack_tasks", ["task_key"])

    if "ai_knowledge_pack_references" not in tables:
        op.create_table(
            "ai_knowledge_pack_references",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("knowledge_pack_version_id", sa.Integer(), nullable=False),
            sa.Column("reference_document_id", sa.Integer(), nullable=True),
            sa.Column("framework_id", sa.Integer(), nullable=True),
            sa.Column("control_id", sa.Integer(), nullable=True),
            sa.Column("unified_control_id", sa.Integer(), nullable=True),
            sa.Column("imported_requirement_id", sa.Integer(), nullable=True),
            sa.Column("use_mode", sa.String(length=64), nullable=False, server_default="guidance"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["knowledge_pack_version_id"], ["ai_knowledge_pack_versions.id"]),
            sa.ForeignKeyConstraint(["reference_document_id"], ["reference_documents.id"]),
            sa.ForeignKeyConstraint(["framework_id"], ["frameworks.id"]),
            sa.ForeignKeyConstraint(["control_id"], ["controls.id"]),
            sa.ForeignKeyConstraint(["unified_control_id"], ["unified_controls.id"]),
            sa.ForeignKeyConstraint(["imported_requirement_id"], ["imported_requirements.id"]),
        )
        op.create_index("ix_ai_knowledge_pack_references_knowledge_pack_version_id", "ai_knowledge_pack_references", ["knowledge_pack_version_id"])
        op.create_index("ix_ai_knowledge_pack_references_reference_document_id", "ai_knowledge_pack_references", ["reference_document_id"])
        op.create_index("ix_ai_knowledge_pack_references_framework_id", "ai_knowledge_pack_references", ["framework_id"])
        op.create_index("ix_ai_knowledge_pack_references_control_id", "ai_knowledge_pack_references", ["control_id"])
        op.create_index("ix_ai_knowledge_pack_references_unified_control_id", "ai_knowledge_pack_references", ["unified_control_id"])
        op.create_index("ix_ai_knowledge_pack_references_imported_requirement_id", "ai_knowledge_pack_references", ["imported_requirement_id"])

    if "ai_knowledge_pack_eval_cases" not in tables:
        op.create_table(
            "ai_knowledge_pack_eval_cases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("knowledge_pack_version_id", sa.Integer(), nullable=False),
            sa.Column("task_key", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("case_code", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("input_payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("expected_assertions_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["knowledge_pack_version_id"], ["ai_knowledge_pack_versions.id"]),
            sa.UniqueConstraint("knowledge_pack_version_id", "case_code", name="uq_ai_pack_eval_case"),
        )
        op.create_index("ix_ai_knowledge_pack_eval_cases_knowledge_pack_version_id", "ai_knowledge_pack_eval_cases", ["knowledge_pack_version_id"])
        op.create_index("ix_ai_knowledge_pack_eval_cases_case_code", "ai_knowledge_pack_eval_cases", ["case_code"])

    ai_suggestion_columns = _column_names(bind, "ai_suggestions") if "ai_suggestions" in tables else set()
    ai_suggestion_indexes = _index_names(bind, "ai_suggestions") if "ai_suggestions" in tables else set()
    ai_suggestion_foreign_keys = _foreign_key_names(bind, "ai_suggestions") if "ai_suggestions" in tables else set()
    if "ai_suggestions" in tables and "knowledge_pack_version_id" not in ai_suggestion_columns:
        op.add_column("ai_suggestions", sa.Column("knowledge_pack_version_id", sa.Integer(), nullable=True))
    if "ai_suggestions" in tables and "ix_ai_suggestions_knowledge_pack_version_id" not in ai_suggestion_indexes:
        op.create_index("ix_ai_suggestions_knowledge_pack_version_id", "ai_suggestions", ["knowledge_pack_version_id"])
    if (
        "ai_suggestions" in tables
        and not _is_sqlite(bind)
        and "fk_ai_suggestions_knowledge_pack_version_id" not in ai_suggestion_foreign_keys
    ):
        op.create_foreign_key(
            "fk_ai_suggestions_knowledge_pack_version_id",
            "ai_suggestions",
            "ai_knowledge_pack_versions",
            ["knowledge_pack_version_id"],
            ["id"],
        )
    if "ai_suggestions" in tables and "task_key" not in ai_suggestion_columns:
        op.add_column(
            "ai_suggestions",
            sa.Column("task_key", sa.String(length=120), nullable=False, server_default=""),
        )
    if "ai_suggestions" in tables and "citations_json" not in ai_suggestion_columns:
        op.add_column(
            "ai_suggestions",
            sa.Column("citations_json", sa.Text(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "ai_suggestions" in tables:
        columns = _column_names(bind, "ai_suggestions")
        indexes = _index_names(bind, "ai_suggestions")
        foreign_keys = _foreign_key_names(bind, "ai_suggestions")
        if "citations_json" in columns:
            op.drop_column("ai_suggestions", "citations_json")
        if "task_key" in columns:
            op.drop_column("ai_suggestions", "task_key")
        if "knowledge_pack_version_id" in columns:
            if not _is_sqlite(bind) and "fk_ai_suggestions_knowledge_pack_version_id" in foreign_keys:
                op.drop_constraint("fk_ai_suggestions_knowledge_pack_version_id", "ai_suggestions", type_="foreignkey")
            if "ix_ai_suggestions_knowledge_pack_version_id" in indexes:
                op.drop_index("ix_ai_suggestions_knowledge_pack_version_id", table_name="ai_suggestions")
            op.drop_column("ai_suggestions", "knowledge_pack_version_id")

    for table_name in [
        "ai_knowledge_pack_eval_cases",
        "ai_knowledge_pack_references",
        "ai_knowledge_pack_tasks",
        "ai_knowledge_pack_versions",
        "ai_knowledge_packs",
    ]:
        if table_name in tables:
            op.drop_table(table_name)
