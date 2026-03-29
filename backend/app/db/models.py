# backend/app/db/models.py
"""
SQLAlchemy ORM models for all TrustFlow tables.
All primary keys are UUID (CHAR(36)). Money columns use DECIMAL(12,2).
GPS columns use DECIMAL(10,7). Append-only tables are noted.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def generate_uuid() -> str:
    """Generate a new UUID4 string for use as a primary key."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Company(Base):
    """Company entity — all data is scoped by company_id."""
    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    country = Column(String(100), nullable=False, default="India")
    currency = Column(String(3), nullable=False, default="INR")
    auto_approve_threshold = Column(Numeric(12, 2), nullable=False, default=Decimal("2000.00"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    users = relationship("User", back_populates="company")
    expenses = relationship("Expense", back_populates="company")
    expense_groups = relationship("ExpenseGroup", back_populates="company")


class User(Base):
    """User with role-based access control."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        Enum("employee", "manager", "admin", name="user_role_enum"),
        nullable=False,
        default="employee",
    )
    manager_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    company = relationship("Company", back_populates="users")
    manager = relationship("User", remote_side="User.id", backref="direct_reports")
    expenses = relationship("Expense", back_populates="user", foreign_keys="Expense.user_id")
    refresh_tokens = relationship("RefreshToken", back_populates="user")


class Expense(Base):
    """Core expense entity with currency conversion fields."""
    __tablename__ = "expenses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    original_amount = Column(Numeric(12, 2), nullable=False)
    original_currency = Column(String(3), nullable=False)
    converted_amount = Column(Numeric(12, 2), nullable=True)
    exchange_rate = Column(Numeric(10, 6), nullable=True)
    conversion_at = Column(DateTime, nullable=True)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum("DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "FLAGGED", name="expense_status_enum"),
        nullable=False,
        default="DRAFT",
    )
    vendor_name = Column(String(255), nullable=True)
    gps_lat = Column(Numeric(10, 7), nullable=True)
    gps_lng = Column(Numeric(10, 7), nullable=True)
    idempotency_key = Column(String(36), unique=True, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="expenses", foreign_keys=[user_id])
    company = relationship("Company", back_populates="expenses")
    proofs = relationship("ExpenseProof", back_populates="expense")
    trust_audits = relationship("TrustScoreAudit", back_populates="expense")
    approval_steps = relationship("ApprovalStep", back_populates="expense")
    approval_events = relationship("ApprovalEvent", back_populates="expense")
    validation_logs = relationship("BillValidationLog", back_populates="expense")
    async_jobs = relationship("AsyncJob", back_populates="expense")
    witnesses = relationship("ExpenseWitness", back_populates="expense")

    __table_args__ = (
        Index("ix_expenses_user_status", "user_id", "status"),
        Index("ix_expenses_created_at", "created_at"),
    )


class ExpenseProof(Base):
    """Receipt, payment proof, or witness-only proof for an expense."""
    __tablename__ = "expense_proofs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    expense_id = Column(String(36), ForeignKey("expenses.id"), nullable=False)
    proof_type = Column(
        Enum("receipt", "payment_proof", "witness_only", "none", name="proof_type_enum"),
        nullable=False,
        default="receipt",
    )
    minio_object_key = Column(String(500), nullable=True)
    ocr_confidence = Column(Numeric(4, 3), nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    ocr_parsed_amount = Column(Numeric(12, 2), nullable=True)
    ocr_parsed_vendor = Column(String(255), nullable=True)
    ocr_parsed_gstin = Column(String(20), nullable=True)
    ocr_parsed_date = Column(String(20), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    expense = relationship("Expense", back_populates="proofs")


class TrustScoreAudit(Base):
    """
    Immutable trust score audit trail. APPEND ONLY — no UPDATE method.
    Each computation creates a new row with input_hash for tamper detection.
    """
    __tablename__ = "trust_score_audit"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    expense_id = Column(String(36), ForeignKey("expenses.id"), nullable=False)
    score = Column(Numeric(5, 2), nullable=False)
    grade = Column(
        Enum("HIGH", "MEDIUM", "LOW", "BLOCKED", name="trust_grade_enum"),
        nullable=False,
    )
    receipt_score = Column(Numeric(5, 2), nullable=False)
    gst_score = Column(Numeric(5, 2), nullable=False)
    vendor_score = Column(Numeric(5, 2), nullable=False)
    behavior_score = Column(Numeric(5, 2), nullable=False)
    proof_score = Column(Numeric(5, 2), nullable=False)
    formula_version = Column(String(10), nullable=False, default="v1.0")
    input_hash = Column(String(64), nullable=False)
    weights_json = Column(Text, nullable=False)
    computed_at = Column(DateTime, nullable=False, server_default=func.now())

    expense = relationship("Expense", back_populates="trust_audits")

    __table_args__ = (
        Index("ix_trust_audit_expense_computed", "expense_id", "computed_at"),
    )


class ApprovalStep(Base):
    """Configuration of approval chain steps for an expense."""
    __tablename__ = "approval_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    expense_id = Column(String(36), ForeignKey("expenses.id"), nullable=False)
    approver_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    current_status = Column(
        Enum("pending", "approved", "rejected", name="approval_status_enum"),
        nullable=False,
        default="pending",
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    expense = relationship("Expense", back_populates="approval_steps")
    approver = relationship("User")

    __table_args__ = (
        Index("ix_approval_steps_expense_order", "expense_id", "step_order"),
    )


class ApprovalEvent(Base):
    """
    Immutable approval event log. APPEND ONLY — no UPDATE method.
    Authoritative state derived from these events, not approval_steps.current_status.
    """
    __tablename__ = "approval_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    expense_id = Column(String(36), ForeignKey("expenses.id"), nullable=False)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    from_state = Column(String(20), nullable=False)
    to_state = Column(String(20), nullable=False)
    comment = Column(Text, nullable=True)
    idempotency_key = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    expense = relationship("Expense", back_populates="approval_events")
    actor = relationship("User")

    __table_args__ = (
        Index("ix_approval_events_expense_created", "expense_id", "created_at"),
    )


class BillValidationLog(Base):
    """
    Immutable validation check results. APPEND ONLY — no UPDATE method.
    One row per check type per validation run.
    """
    __tablename__ = "bill_validation_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    expense_id = Column(String(36), ForeignKey("expenses.id"), nullable=False)
    check_type = Column(String(50), nullable=False)
    passed = Column(Boolean, nullable=False)
    confidence = Column(Numeric(4, 3), nullable=True)
    fraud_signal = Column(Boolean, nullable=False, default=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    expense = relationship("Expense", back_populates="validation_logs")


class AsyncJob(Base):
    """Tracks Celery async job status for polling by the frontend."""
    __tablename__ = "async_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    expense_id = Column(String(36), ForeignKey("expenses.id"), nullable=False)
    job_type = Column(
        Enum("ocr", "trust", "validation", "notification", name="job_type_enum"),
        nullable=False,
    )
    celery_task_id = Column(String(255), nullable=True)
    status = Column(
        Enum("queued", "running", "completed", "failed", name="job_status_enum"),
        nullable=False,
        default="queued",
    )
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    expense = relationship("Expense", back_populates="async_jobs")

    __table_args__ = (
        Index("ix_async_jobs_expense_type", "expense_id", "job_type"),
    )


class ExpenseWitness(Base):
    """Witness confirmations for expenses."""
    __tablename__ = "expense_witnesses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    expense_id = Column(String(36), ForeignKey("expenses.id"), nullable=False)
    witness_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(
        Enum("pending", "confirmed", "rejected", name="witness_status_enum"),
        nullable=False,
        default="pending",
    )
    signature_hash = Column(String(64), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    expense = relationship("Expense", back_populates="witnesses")
    witness_user = relationship("User")


class ExpenseGroup(Base):
    """Named expense groups for bundling trip or project expenses."""
    __tablename__ = "expense_groups"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    company = relationship("Company", back_populates="expense_groups")
    creator = relationship("User")
    members = relationship("ExpenseGroupMember", back_populates="group")


class ExpenseGroupMember(Base):
    """Many-to-many link between expense groups and expenses."""
    __tablename__ = "expense_group_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    group_id = Column(String(36), ForeignKey("expense_groups.id"), nullable=False)
    expense_id = Column(String(36), ForeignKey("expenses.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    group = relationship("ExpenseGroup", back_populates="members")
    expense = relationship("Expense")


class RefreshToken(Base):
    """Refresh token storage — hashed, with revocation support."""
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_refresh_tokens_token_hash", "token_hash"),
    )
