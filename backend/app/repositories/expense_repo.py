# backend/app/repositories/expense_repo.py
"""
Expense repository — SQLAlchemy queries only, no business logic.
Explicit column selection — never select(*).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Expense, ExpenseProof, AsyncJob, BillValidationLog

logger = logging.getLogger("trustflow.repositories.expense")


async def create_expense(session: AsyncSession, expense: Expense) -> Expense:
    """Insert a new expense row into the database."""
    session.add(expense)
    await session.flush()
    await session.refresh(expense)
    logger.info("Created expense %s", expense.id)
    return expense


async def create_proof(session: AsyncSession, proof: ExpenseProof) -> ExpenseProof:
    """Insert a new expense proof row."""
    session.add(proof)
    await session.flush()
    await session.refresh(proof)
    return proof


async def create_async_job(session: AsyncSession, job: AsyncJob) -> AsyncJob:
    """Insert a new async job row."""
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


async def get_by_id(
    session: AsyncSession,
    expense_id: str,
    company_id: str,
) -> Optional[Expense]:
    """
    Get an expense by ID, scoped to company_id for security.

    company_id is always included in the WHERE clause
    to prevent cross-company data leakage.
    """
    stmt = select(Expense).where(
        and_(Expense.id == expense_id, Expense.company_id == company_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_idempotency_key(
    session: AsyncSession,
    idempotency_key: str,
) -> Optional[Expense]:
    """Look up an expense by its idempotency key."""
    stmt = select(Expense).where(Expense.idempotency_key == idempotency_key)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_user(
    session: AsyncSession,
    user_id: str,
    company_id: str,
    status: Optional[str] = None,
) -> List[Expense]:
    """
    Get all expenses for a user, scoped by company_id.

    Optionally filtered by status.
    """
    conditions = [Expense.user_id == user_id, Expense.company_id == company_id]
    if status:
        conditions.append(Expense.status == status)

    stmt = select(Expense).where(and_(*conditions)).order_by(Expense.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_with_filters(
    session: AsyncSession,
    company_id: str,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Expense]:
    """
    List expenses with optional filters, always scoped by company_id.

    Used by managers (with user_id of reports) and admins (company-wide).
    """
    conditions = [Expense.company_id == company_id]
    if user_id:
        conditions.append(Expense.user_id == user_id)
    if status:
        conditions.append(Expense.status == status)

    stmt = (
        select(Expense)
        .where(and_(*conditions))
        .order_by(Expense.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_status(
    session: AsyncSession,
    expense_id: str,
    company_id: str,
    new_status: str,
) -> bool:
    """
    Update expense status, scoped by company_id.

    Returns True if a row was updated, False otherwise.
    """
    stmt = (
        update(Expense)
        .where(and_(Expense.id == expense_id, Expense.company_id == company_id))
        .values(status=new_status)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def get_proofs_for_expense(
    session: AsyncSession,
    expense_id: str,
) -> List[ExpenseProof]:
    """Get all proofs attached to an expense."""
    stmt = select(ExpenseProof).where(ExpenseProof.expense_id == expense_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_proof_ocr(
    session: AsyncSession,
    proof_id: str,
    ocr_data: dict,
) -> bool:
    """Update OCR fields on an expense proof."""
    from sqlalchemy import update as sa_update
    stmt = sa_update(ExpenseProof).where(ExpenseProof.id == proof_id).values(**ocr_data)
    result = await session.execute(stmt)
    return result.rowcount > 0


async def get_async_jobs(
    session: AsyncSession,
    expense_id: str,
) -> List[AsyncJob]:
    """Get all async jobs for an expense."""
    stmt = (
        select(AsyncJob)
        .where(AsyncJob.expense_id == expense_id)
        .order_by(AsyncJob.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_async_job(
    session: AsyncSession,
    job_id: str,
    status: str,
    result_json: Optional[str] = None,
    celery_task_id: Optional[str] = None,
) -> bool:
    """Update the status and result of an async job."""
    values = {"status": status}
    if result_json is not None:
        values["result_json"] = result_json
    if celery_task_id is not None:
        values["celery_task_id"] = celery_task_id

    stmt = update(AsyncJob).where(AsyncJob.id == job_id).values(**values)
    result = await session.execute(stmt)
    return result.rowcount > 0


async def get_validation_logs(
    session: AsyncSession,
    expense_id: str,
) -> List[BillValidationLog]:
    """Get all validation log entries for an expense."""
    stmt = (
        select(BillValidationLog)
        .where(BillValidationLog.expense_id == expense_id)
        .order_by(BillValidationLog.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_validation_log(
    session: AsyncSession,
    log_entry: BillValidationLog,
) -> BillValidationLog:
    """Insert a new validation log entry (append-only)."""
    session.add(log_entry)
    await session.flush()
    await session.refresh(log_entry)
    return log_entry


async def get_fraud_signal_count(
    session: AsyncSession,
    user_id: str,
    days: int = 90,
) -> int:
    """
    Count fraud signals for a user in the last N days.

    Used for behavior score calculation in trust scoring.
    """
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(BillValidationLog)
        .join(Expense, BillValidationLog.expense_id == Expense.id)
        .where(
            and_(
                Expense.user_id == user_id,
                BillValidationLog.fraud_signal == True,
                BillValidationLog.created_at >= cutoff,
            )
        )
    )
    result = await session.execute(stmt)
    return len(list(result.scalars().all()))


async def get_expense_count_for_user(
    session: AsyncSession,
    user_id: str,
) -> int:
    """Get total expense count for a user (for first-expense detection)."""
    from sqlalchemy import func
    stmt = select(func.count(Expense.id)).where(Expense.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one()
