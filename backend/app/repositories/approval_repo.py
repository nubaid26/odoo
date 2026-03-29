# backend/app/repositories/approval_repo.py
"""
Approval repository — SQLAlchemy queries for approval steps and events.
approval_events is APPEND ONLY — no update method provided.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApprovalStep, ApprovalEvent

logger = logging.getLogger("trustflow.repositories.approval")


async def create_steps(
    session: AsyncSession,
    steps: List[ApprovalStep],
) -> List[ApprovalStep]:
    """
    Insert approval step rows for an expense.

    Args:
        session: Database session.
        steps: List of ApprovalStep models to insert.

    Returns:
        The inserted steps with generated IDs.
    """
    for step in steps:
        session.add(step)
    await session.flush()
    for step in steps:
        await session.refresh(step)
    logger.info("Created %d approval steps", len(steps))
    return steps


async def get_steps_for_expense(
    session: AsyncSession,
    expense_id: str,
) -> List[ApprovalStep]:
    """Get all approval steps for an expense, ordered by step_order."""
    stmt = (
        select(ApprovalStep)
        .where(ApprovalStep.expense_id == expense_id)
        .order_by(ApprovalStep.step_order)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_current_step(
    session: AsyncSession,
    expense_id: str,
) -> Optional[ApprovalStep]:
    """
    Get the current pending approval step for an expense.

    Returns the first step with status 'pending' ordered by step_order.
    """
    stmt = (
        select(ApprovalStep)
        .where(
            and_(
                ApprovalStep.expense_id == expense_id,
                ApprovalStep.current_status == "pending",
            )
        )
        .order_by(ApprovalStep.step_order)
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_step_status(
    session: AsyncSession,
    step_id: str,
    new_status: str,
) -> bool:
    """Update the status of an approval step."""
    stmt = (
        update(ApprovalStep)
        .where(ApprovalStep.id == step_id)
        .values(current_status=new_status)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def append_event(
    session: AsyncSession,
    event: ApprovalEvent,
) -> ApprovalEvent:
    """
    Append a new approval event — APPEND ONLY, never update or delete.

    Args:
        session: Database session.
        event: ApprovalEvent model to insert.

    Returns:
        The inserted event with generated ID.
    """
    session.add(event)
    await session.flush()
    await session.refresh(event)
    logger.info(
        "Appended approval event: expense=%s, %s → %s by %s",
        event.expense_id, event.from_state, event.to_state, event.actor_id[:8],
    )
    return event


async def get_events_for_expense(
    session: AsyncSession,
    expense_id: str,
) -> List[ApprovalEvent]:
    """Get all approval events for an expense, ordered by creation time."""
    stmt = (
        select(ApprovalEvent)
        .where(ApprovalEvent.expense_id == expense_id)
        .order_by(ApprovalEvent.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def check_idempotency_key(
    session: AsyncSession,
    idempotency_key: str,
) -> bool:
    """
    Check if an idempotency key has been used in approval events.

    Returns True if already used, False otherwise.
    """
    stmt = select(ApprovalEvent).where(
        ApprovalEvent.idempotency_key == idempotency_key
    ).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None
