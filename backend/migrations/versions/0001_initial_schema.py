# backend/migrations/versions/0001_initial_schema.py
"""
Initial schema — all TrustFlow tables, constraints, and indexes.

Revision ID: 0001
Revises: None
Create Date: 2025-01-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables with columns, constraints, and indexes."""

    # ── companies ─────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(100), nullable=False, server_default="India"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("auto_approve_threshold", sa.Numeric(12, 2), nullable=False, server_default="2000.00"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── users ─────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("employee", "manager", "admin", name="user_role_enum"),
            nullable=False,
            server_default="employee",
        ),
        sa.Column("manager_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── expenses ──────────────────────────────────────────
    op.create_table(
        "expenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("original_currency", sa.String(3), nullable=False),
        sa.Column("converted_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(10, 6), nullable=True),
        sa.Column("conversion_at", sa.DateTime, nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "FLAGGED", name="expense_status_enum"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("vendor_name", sa.String(255), nullable=True),
        sa.Column("gps_lat", sa.Numeric(10, 7), nullable=True),
        sa.Column("gps_lng", sa.Numeric(10, 7), nullable=True),
        sa.Column("idempotency_key", sa.String(36), nullable=False, unique=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_expenses_user_status", "expenses", ["user_id", "status"])
    op.create_index("ix_expenses_created_at", "expenses", ["created_at"])

    # ── expense_proofs ────────────────────────────────────
    op.create_table(
        "expense_proofs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column(
            "proof_type",
            sa.Enum("receipt", "payment_proof", "witness_only", "none", name="proof_type_enum"),
            nullable=False,
            server_default="receipt",
        ),
        sa.Column("minio_object_key", sa.String(500), nullable=True),
        sa.Column("ocr_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("ocr_raw_text", sa.Text, nullable=True),
        sa.Column("ocr_parsed_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("ocr_parsed_vendor", sa.String(255), nullable=True),
        sa.Column("ocr_parsed_gstin", sa.String(20), nullable=True),
        sa.Column("ocr_parsed_date", sa.String(20), nullable=True),
        sa.Column("verified_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── trust_score_audit (APPEND ONLY — no updates ever) ─
    op.create_table(
        "trust_score_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "grade",
            sa.Enum("HIGH", "MEDIUM", "LOW", "BLOCKED", name="trust_grade_enum"),
            nullable=False,
        ),
        sa.Column("receipt_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("gst_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("vendor_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("behavior_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("proof_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("formula_version", sa.String(10), nullable=False, server_default="v1.0"),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("weights_json", sa.Text, nullable=False),
        sa.Column("computed_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_trust_audit_expense_computed", "trust_score_audit", ["expense_id", "computed_at"])

    # ── approval_steps ────────────────────────────────────
    op.create_table(
        "approval_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column("approver_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column(
            "current_status",
            sa.Enum("pending", "approved", "rejected", name="approval_status_enum"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_approval_steps_expense_order", "approval_steps", ["expense_id", "step_order"])

    # ── approval_events (APPEND ONLY — no updates ever) ──
    op.create_table(
        "approval_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("from_state", sa.String(20), nullable=False),
        sa.Column("to_state", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("idempotency_key", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_approval_events_expense_created", "approval_events", ["expense_id", "created_at"])

    # ── bill_validation_logs (APPEND ONLY — no updates) ──
    op.create_table(
        "bill_validation_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("fraud_signal", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── async_jobs ────────────────────────────────────────
    op.create_table(
        "async_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column(
            "job_type",
            sa.Enum("ocr", "trust", "validation", "notification", name="job_type_enum"),
            nullable=False,
        ),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "completed", "failed", name="job_status_enum"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("result_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_async_jobs_expense_type", "async_jobs", ["expense_id", "job_type"])

    # ── expense_witnesses ─────────────────────────────────
    op.create_table(
        "expense_witnesses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column("witness_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "confirmed", "rejected", name="witness_status_enum"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("signature_hash", sa.String(64), nullable=True),
        sa.Column("confirmed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── expense_groups ────────────────────────────────────
    op.create_table(
        "expense_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── expense_group_members ─────────────────────────────
    op.create_table(
        "expense_group_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("expense_groups.id"), nullable=False),
        sa.Column("expense_id", sa.String(36), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── refresh_tokens ────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("expense_group_members")
    op.drop_table("expense_groups")
    op.drop_table("refresh_tokens")
    op.drop_table("expense_witnesses")
    op.drop_table("async_jobs")
    op.drop_table("bill_validation_logs")
    op.drop_table("approval_events")
    op.drop_table("approval_steps")
    op.drop_table("trust_score_audit")
    op.drop_table("expense_proofs")
    op.drop_table("expenses")
    op.drop_table("users")
    op.drop_table("companies")
