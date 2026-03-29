# backend/app/domain/enums.py
"""
Application-wide enumerations. Used instead of hardcoded strings everywhere.
"""

from enum import Enum


class ExpenseStatus(str, Enum):
    """Lifecycle states of an expense."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


class ProofType(str, Enum):
    """Types of proof attached to an expense."""
    RECEIPT = "receipt"
    PAYMENT_PROOF = "payment_proof"
    WITNESS_ONLY = "witness_only"
    NONE = "none"


class TrustGrade(str, Enum):
    """Trust grade thresholds derived from weighted trust score."""
    HIGH = "HIGH"        # score >= 80
    MEDIUM = "MEDIUM"    # 60 <= score < 80
    LOW = "LOW"          # 40 <= score < 60
    BLOCKED = "BLOCKED"  # score < 40


class UserRole(str, Enum):
    """User access roles for RBAC enforcement."""
    EMPLOYEE = "employee"
    MANAGER = "manager"
    ADMIN = "admin"


class JobType(str, Enum):
    """Types of async Celery jobs."""
    OCR = "ocr"
    TRUST = "trust"
    VALIDATION = "validation"
    NOTIFICATION = "notification"


class JobStatus(str, Enum):
    """Status of an async Celery job."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    """Status of an approval step."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
