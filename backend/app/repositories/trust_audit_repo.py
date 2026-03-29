# backend/app/repositories/trust_audit_repo.py
"""
Trust score audit repository — APPEND ONLY.
No update method is provided — trust audit rows are immutable.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TrustScoreAudit

logger = logging.getLogger("trustflow.repositories.trust_audit")


async def insert(session: AsyncSession, audit: TrustScoreAudit) -> TrustScoreAudit:
    """
    Insert a new trust score audit row — APPEND ONLY.

    No update method exists for this repository.
    Each trust computation creates a new immutable row.

    Args:
        session: Database session.
        audit: TrustScoreAudit model to insert.

    Returns:
        The inserted audit row with generated ID.
    """
    session.add(audit)
    await session.flush()
    await session.refresh(audit)
    logger.info(
        "Inserted trust audit: expense=%s, score=%s, grade=%s, hash=%s",
        audit.expense_id, audit.score, audit.grade, audit.input_hash[:16],
    )
    return audit


async def get_latest_for_expense(
    session: AsyncSession,
    expense_id: str,
) -> Optional[TrustScoreAudit]:
    """
    Get the most recent trust score audit for an expense.

    Args:
        session: Database session.
        expense_id: The expense UUID.

    Returns:
        The latest TrustScoreAudit row, or None if no audit exists.
    """
    stmt = (
        select(TrustScoreAudit)
        .where(TrustScoreAudit.expense_id == expense_id)
        .order_by(TrustScoreAudit.computed_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
