"""Add enterprise foundation entities and platform controls.

Revision ID: 20260317_0003
Revises: 20260317_0002
Create Date: 2026-03-17 18:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260317_0003"
down_revision = "20260317_0002"
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "business_units" not in tables:
        op.create_table(
            "business_units",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("owner", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.UniqueConstraint("organization_id", "code", name="uq_org_business_unit_code"),
        )
        op.create_index("ix_business_units_organization_id", "business_units", ["organization_id"])
        op.create_index("ix_business_units_code", "business_units", ["code"])

    if "assets" not in tables:
        op.create_table(
            "assets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("business_unit_id", sa.Integer(), nullable=True),
            sa.Column("product_id", sa.Integer(), nullable=True),
            sa.Column("asset_code", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("asset_type", sa.String(length=64), nullable=False, server_default="application"),
            sa.Column("criticality", sa.String(length=32), nullable=False, server_default="medium"),
            sa.Column("data_classification", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("owner", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("attributes_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["business_unit_id"], ["business_units.id"]),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.UniqueConstraint("organization_id", "asset_code", name="uq_org_asset_code"),
        )
        op.create_index("ix_assets_organization_id", "assets", ["organization_id"])
        op.create_index("ix_assets_business_unit_id", "assets", ["business_unit_id"])
        op.create_index("ix_assets_product_id", "assets", ["product_id"])
        op.create_index("ix_assets_asset_code", "assets", ["asset_code"])

    if "threats" not in tables:
        op.create_table(
            "threats",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("threat_code", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=False, server_default=""),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("source", sa.String(length=100), nullable=False, server_default="catalog"),
            sa.Column("severity", sa.String(length=32), nullable=False, server_default="medium"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.UniqueConstraint("threat_code", name="uq_threats_threat_code"),
        )
        op.create_index("ix_threats_organization_id", "threats", ["organization_id"])
        op.create_index("ix_threats_threat_code", "threats", ["threat_code"], unique=True)

    if "risks" not in tables:
        op.create_table(
            "risks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("business_unit_id", sa.Integer(), nullable=True),
            sa.Column("asset_id", sa.Integer(), nullable=True),
            sa.Column("threat_id", sa.Integer(), nullable=True),
            sa.Column("unified_control_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="identified"),
            sa.Column("likelihood", sa.Float(), nullable=False, server_default="0"),
            sa.Column("impact", sa.Float(), nullable=False, server_default="0"),
            sa.Column("inherent_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("residual_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("owner", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("review_due_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["business_unit_id"], ["business_units.id"]),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
            sa.ForeignKeyConstraint(["threat_id"], ["threats.id"]),
            sa.ForeignKeyConstraint(["unified_control_id"], ["unified_controls.id"]),
        )
        op.create_index("ix_risks_organization_id", "risks", ["organization_id"])
        op.create_index("ix_risks_business_unit_id", "risks", ["business_unit_id"])
        op.create_index("ix_risks_asset_id", "risks", ["asset_id"])
        op.create_index("ix_risks_threat_id", "risks", ["threat_id"])
        op.create_index("ix_risks_unified_control_id", "risks", ["unified_control_id"])

    if "risk_treatments" not in tables:
        op.create_table(
            "risk_treatments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("risk_id", sa.Integer(), nullable=False),
            sa.Column("unified_control_id", sa.Integer(), nullable=True),
            sa.Column("control_implementation_id", sa.Integer(), nullable=True),
            sa.Column("treatment_type", sa.String(length=32), nullable=False, server_default="mitigate"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
            sa.Column("owner", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("target_date", sa.DateTime(), nullable=True),
            sa.Column("plan", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["risk_id"], ["risks.id"]),
            sa.ForeignKeyConstraint(["unified_control_id"], ["unified_controls.id"]),
            sa.ForeignKeyConstraint(["control_implementation_id"], ["control_implementations.id"]),
        )
        op.create_index("ix_risk_treatments_risk_id", "risk_treatments", ["risk_id"])
        op.create_index("ix_risk_treatments_unified_control_id", "risk_treatments", ["unified_control_id"])
        op.create_index("ix_risk_treatments_control_implementation_id", "risk_treatments", ["control_implementation_id"])

    if "findings" not in tables:
        op.create_table(
            "findings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("business_unit_id", sa.Integer(), nullable=True),
            sa.Column("risk_id", sa.Integer(), nullable=True),
            sa.Column("assessment_run_id", sa.Integer(), nullable=True),
            sa.Column("framework_id", sa.Integer(), nullable=True),
            sa.Column("control_id", sa.Integer(), nullable=True),
            sa.Column("unified_control_id", sa.Integer(), nullable=True),
            sa.Column("evidence_item_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("source_type", sa.String(length=64), nullable=False, server_default="assessment"),
            sa.Column("severity", sa.String(length=32), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
            sa.Column("owner", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("detected_at", sa.DateTime(), nullable=False),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["business_unit_id"], ["business_units.id"]),
            sa.ForeignKeyConstraint(["risk_id"], ["risks.id"]),
            sa.ForeignKeyConstraint(["assessment_run_id"], ["assessment_runs.id"]),
            sa.ForeignKeyConstraint(["framework_id"], ["frameworks.id"]),
            sa.ForeignKeyConstraint(["control_id"], ["controls.id"]),
            sa.ForeignKeyConstraint(["unified_control_id"], ["unified_controls.id"]),
            sa.ForeignKeyConstraint(["evidence_item_id"], ["evidence_items.id"]),
        )
        op.create_index("ix_findings_organization_id", "findings", ["organization_id"])
        op.create_index("ix_findings_business_unit_id", "findings", ["business_unit_id"])
        op.create_index("ix_findings_risk_id", "findings", ["risk_id"])

    if "action_items" not in tables:
        op.create_table(
            "action_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("business_unit_id", sa.Integer(), nullable=True),
            sa.Column("finding_id", sa.Integer(), nullable=True),
            sa.Column("risk_id", sa.Integer(), nullable=True),
            sa.Column("control_implementation_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("priority", sa.String(length=32), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
            sa.Column("owner", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["business_unit_id"], ["business_units.id"]),
            sa.ForeignKeyConstraint(["finding_id"], ["findings.id"]),
            sa.ForeignKeyConstraint(["risk_id"], ["risks.id"]),
            sa.ForeignKeyConstraint(["control_implementation_id"], ["control_implementations.id"]),
        )
        op.create_index("ix_action_items_organization_id", "action_items", ["organization_id"])
        op.create_index("ix_action_items_business_unit_id", "action_items", ["business_unit_id"])
        op.create_index("ix_action_items_finding_id", "action_items", ["finding_id"])
        op.create_index("ix_action_items_risk_id", "action_items", ["risk_id"])

    if "feature_flags" not in tables:
        op.create_table(
            "feature_flags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("flag_key", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("rollout_strategy", sa.String(length=32), nullable=False, server_default="static"),
            sa.Column("owner", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("flag_key", name="uq_feature_flags_flag_key"),
        )
        op.create_index("ix_feature_flags_flag_key", "feature_flags", ["flag_key"], unique=True)

    if "circuit_breaker_states" not in tables:
        op.create_table(
            "circuit_breaker_states",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("integration_key", sa.String(length=255), nullable=False),
            sa.Column("state", sa.String(length=32), nullable=False, server_default="closed"),
            sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("threshold", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("opened_at", sa.DateTime(), nullable=True),
            sa.Column("reopen_after_seconds", sa.Integer(), nullable=False, server_default="300"),
            sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("integration_key", name="uq_circuit_breaker_states_integration_key"),
        )
        op.create_index("ix_circuit_breaker_states_integration_key", "circuit_breaker_states", ["integration_key"], unique=True)

    if "external_call_ledger" not in tables:
        op.create_table(
            "external_call_ledger",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("integration_key", sa.String(length=255), nullable=False),
            sa.Column("operation", sa.String(length=120), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("request_hash", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="started"),
            sa.Column("response_payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("integration_key", "operation", "idempotency_key", name="uq_external_call_idempotency"),
        )
        op.create_index("ix_external_call_ledger_integration_key", "external_call_ledger", ["integration_key"])
        op.create_index("ix_external_call_ledger_operation", "external_call_ledger", ["operation"])
        op.create_index("ix_external_call_ledger_idempotency_key", "external_call_ledger", ["idempotency_key"])

    if "products" in tables:
        columns = _column_names(bind, "products")
        with op.batch_alter_table("products") as batch_op:
            if "business_unit_id" not in columns:
                batch_op.add_column(sa.Column("business_unit_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key("fk_products_business_unit_id", "business_units", ["business_unit_id"], ["id"])
                batch_op.create_index("ix_products_business_unit_id", ["business_unit_id"], unique=False)

    if "evidence_items" in tables:
        columns = _column_names(bind, "evidence_items")
        with op.batch_alter_table("evidence_items") as batch_op:
            if "evidence_key" not in columns:
                batch_op.add_column(sa.Column("evidence_key", sa.String(length=120), nullable=False, server_default=""))
                batch_op.create_index("ix_evidence_items_evidence_key", ["evidence_key"], unique=False)
            if "version_label" not in columns:
                batch_op.add_column(sa.Column("version_label", sa.String(length=64), nullable=False, server_default="v1"))
            if "submitted_by" not in columns:
                batch_op.add_column(sa.Column("submitted_by", sa.String(length=255), nullable=False, server_default=""))
            if "expires_at" not in columns:
                batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))

    if "lifecycle_events" in tables:
        columns = _column_names(bind, "lifecycle_events")
        with op.batch_alter_table("lifecycle_events") as batch_op:
            if "previous_hash" not in columns:
                batch_op.add_column(sa.Column("previous_hash", sa.String(length=128), nullable=False, server_default=""))
            if "event_hash" not in columns:
                batch_op.add_column(sa.Column("event_hash", sa.String(length=128), nullable=False, server_default=""))
                batch_op.create_index("ix_lifecycle_events_event_hash", ["event_hash"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "lifecycle_events" in tables:
        columns = _column_names(bind, "lifecycle_events")
        with op.batch_alter_table("lifecycle_events") as batch_op:
            if "event_hash" in columns:
                batch_op.drop_index("ix_lifecycle_events_event_hash")
                batch_op.drop_column("event_hash")
            if "previous_hash" in columns:
                batch_op.drop_column("previous_hash")

    if "evidence_items" in tables:
        columns = _column_names(bind, "evidence_items")
        with op.batch_alter_table("evidence_items") as batch_op:
            if "expires_at" in columns:
                batch_op.drop_column("expires_at")
            if "submitted_by" in columns:
                batch_op.drop_column("submitted_by")
            if "version_label" in columns:
                batch_op.drop_column("version_label")
            if "evidence_key" in columns:
                batch_op.drop_index("ix_evidence_items_evidence_key")
                batch_op.drop_column("evidence_key")

    if "products" in tables:
        columns = _column_names(bind, "products")
        if "business_unit_id" in columns:
            with op.batch_alter_table("products") as batch_op:
                batch_op.drop_index("ix_products_business_unit_id")
                batch_op.drop_constraint("fk_products_business_unit_id", type_="foreignkey")
                batch_op.drop_column("business_unit_id")

    for table_name in [
        "external_call_ledger",
        "circuit_breaker_states",
        "feature_flags",
        "action_items",
        "findings",
        "risk_treatments",
        "risks",
        "threats",
        "assets",
        "business_units",
    ]:
        if table_name in tables:
            op.drop_table(table_name)
