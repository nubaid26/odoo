# backend/app/services/approval_service.py
"""
Approval service — routing logic, step creation, state machine transitions.

Routing rules:
  HIGH + amount < auto_approve_threshold → auto-approve
  MEDIUM → single manager approval step
  LOW → full chain (manager, + manager's manager if amount > ₹10,000)
  BLOCKED → create steps, status=FLAGGED, suspended until admin
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApprovalStep, ApprovalEvent, Expense, Company, User
from app.domain.enums import (
    ExpenseStatus,
    TrustGrade,
    ApprovalStatus,
    UserRole,
)
from app.domain.states import transition_expense
from app.repositories import approval_repo, expense_repo, user_repo

logger = logging.getLogger("trustflow.services.approval")


async def route_expense(
    session: AsyncSession,
    expense_id: str,
    company_id: str,
    trust_grade: str,
    trust_score: Decimal,
) -> dict:
    """
    Route an expense through the approval chain based on trust grade.

    Args:
        session: Database session.
        expense_id: The expense UUID.
        company_id: The company UUID.
        trust_grade: TrustGrade value (HIGH, MEDIUM, LOW, BLOCKED).
        trust_score: Numeric trust score.

    Returns:
        Dict with routing result: status, steps created, auto_approved flag.
    """
    expense = await expense_repo.get_by_id(session, expense_id, company_id)
    if not expense:
        raise ValueError(f"Expense {expense_id} not found")

    # Get company threshold
    from sqlalchemy import select
    stmt = select(Company).where(Company.id == company_id)
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()
    auto_threshold = company.auto_approve_threshold if company else Decimal("2000.00")

    # Get the submitting user and their manager
    user = await user_repo.get_by_id(session, expense.user_id)
    if not user:
        raise ValueError(f"User {expense.user_id} not found")

    grade = TrustGrade(trust_grade)
    amount = expense.converted_amount or expense.original_amount

    # ── HIGH grade + below threshold → auto-approve ──
    if grade == TrustGrade.HIGH and amount < auto_threshold:
        logger.info(
            "Auto-approving expense %s (score=%.2f, amount=₹%s < threshold=₹%s)",
            expense_id, trust_score, amount, auto_threshold,
        )
        await expense_repo.update_status(
            session, expense_id, company_id, ExpenseStatus.APPROVED.value
        )

        # Create auto-approve event
        event = ApprovalEvent(
            id=str(uuid.uuid4()),
            expense_id=expense_id,
            actor_id=expense.user_id,
            from_state=ExpenseStatus.DRAFT.value,
            to_state=ExpenseStatus.APPROVED.value,
            comment=f"Auto-approved: trust score {trust_score} (HIGH), amount ₹{amount} < threshold ₹{auto_threshold}",
        )
        await approval_repo.append_event(session, event)

        # Enqueue notification
        _enqueue_notification(expense_id, "expense_approved", expense.user_id)

        return {"status": "auto_approved", "steps_created": 0, "auto_approved": True}

    # ── Build approval chain ──
    steps = []
    step_order = 1

    if grade == TrustGrade.BLOCKED:
        # BLOCKED: create steps but flag expense
        new_status = ExpenseStatus.FLAGGED.value
    else:
        new_status = ExpenseStatus.SUBMITTED.value

    # Single manager step for MEDIUM, full chain for LOW
    if user.manager_id:
        manager = await user_repo.get_by_id(session, user.manager_id)
        if manager:
            steps.append(
                ApprovalStep(
                    id=str(uuid.uuid4()),
                    expense_id=expense_id,
                    approver_id=manager.id,
                    step_order=step_order,
                    current_status=ApprovalStatus.PENDING.value,
                )
            )
            step_order += 1

            # LOW grade + amount > ₹10,000 → add manager's manager
            if grade == TrustGrade.LOW and amount > Decimal("10000"):
                if manager.manager_id:
                    senior_manager = await user_repo.get_by_id(session, manager.manager_id)
                    if senior_manager:
                        steps.append(
                            ApprovalStep(
                                id=str(uuid.uuid4()),
                                expense_id=expense_id,
                                approver_id=senior_manager.id,
                                step_order=step_order,
                                current_status=ApprovalStatus.PENDING.value,
                            )
                        )
                        step_order += 1

    if steps:
        await approval_repo.create_steps(session, steps)

    # Update expense status
    await expense_repo.update_status(session, expense_id, company_id, new_status)

    # Create routing event
    event = ApprovalEvent(
        id=str(uuid.uuid4()),
        expense_id=expense_id,
        actor_id=expense.user_id,
        from_state=ExpenseStatus.DRAFT.value,
        to_state=new_status,
        comment=f"Routed: trust grade={grade.value}, score={trust_score}, steps={len(steps)}",
    )
    await approval_repo.append_event(session, event)

    # Enqueue notification to first approver
    if steps and grade != TrustGrade.BLOCKED:
        _enqueue_notification(expense_id, "approval_request", steps[0].approver_id)

    logger.info(
        "Routed expense %s: grade=%s, status=%s, steps=%d",
        expense_id, grade.value, new_status, len(steps),
    )

    return {
        "status": new_status,
        "steps_created": len(steps),
        "auto_approved": False,
    }


async def approve_expense(
    session: AsyncSession,
    expense_id: str,
    company_id: str,
    approver_id: str,
    approver_role: str,
    comment: Optional[str],
    idempotency_key: str,
) -> dict:
    """
    Approve an expense at the current approval step.

    Validates: correct approver, correct step, correct status, idempotency.
    On final step approve: expense → APPROVED, notify submitter.

    Returns:
        Dict with result of the approval action.
    """
    # Idempotency check
    if await approval_repo.check_idempotency_key(session, idempotency_key):
        return {"status": "already_processed", "message": "Idempotency key already used"}

    expense = await expense_repo.get_by_id(session, expense_id, company_id)
    if not expense:
        raise ValueError(f"Expense {expense_id} not found")

    if expense.status != ExpenseStatus.SUBMITTED.value:
        raise ValueError(f"Expense {expense_id} is not in SUBMITTED status (current: {expense.status})")

    # Get current pending step
    current_step = await approval_repo.get_current_step(session, expense_id)
    if not current_step:
        raise ValueError(f"No pending approval step for expense {expense_id}")

    if current_step.approver_id != approver_id:
        raise ValueError("Only the assigned approver can action this step")

    # Update step status
    await approval_repo.update_step_status(session, current_step.id, ApprovalStatus.APPROVED.value)

    # Append event
    event = ApprovalEvent(
        id=str(uuid.uuid4()),
        expense_id=expense_id,
        actor_id=approver_id,
        from_state=ApprovalStatus.PENDING.value,
        to_state=ApprovalStatus.APPROVED.value,
        comment=comment,
        idempotency_key=idempotency_key,
    )
    await approval_repo.append_event(session, event)

    # Check if this was the final step
    next_step = await approval_repo.get_current_step(session, expense_id)
    if next_step is None:
        # All steps approved — expense is APPROVED
        await expense_repo.update_status(
            session, expense_id, company_id, ExpenseStatus.APPROVED.value
        )
        _enqueue_notification(expense_id, "expense_approved", expense.user_id)
        return {"status": "approved", "final": True, "message": "Expense fully approved"}
    else:
        # More steps remain — notify next approver
        _enqueue_notification(expense_id, "approval_request", next_step.approver_id)
        return {"status": "approved", "final": False, "message": "Step approved, awaiting next approver"}


async def reject_expense(
    session: AsyncSession,
    expense_id: str,
    company_id: str,
    approver_id: str,
    approver_role: str,
    comment: str,
    idempotency_key: str,
) -> dict:
    """
    Reject an expense at the current approval step.

    Sets expense status to REJECTED and notifies submitter.
    """
    if await approval_repo.check_idempotency_key(session, idempotency_key):
        return {"status": "already_processed", "message": "Idempotency key already used"}

    expense = await expense_repo.get_by_id(session, expense_id, company_id)
    if not expense:
        raise ValueError(f"Expense {expense_id} not found")

    if expense.status != ExpenseStatus.SUBMITTED.value:
        raise ValueError(f"Expense {expense_id} is not in SUBMITTED status")

    current_step = await approval_repo.get_current_step(session, expense_id)
    if not current_step:
        raise ValueError(f"No pending approval step for expense {expense_id}")

    if current_step.approver_id != approver_id:
        raise ValueError("Only the assigned approver can action this step")

    # Update step status
    await approval_repo.update_step_status(session, current_step.id, ApprovalStatus.REJECTED.value)

    # Append event
    event = ApprovalEvent(
        id=str(uuid.uuid4()),
        expense_id=expense_id,
        actor_id=approver_id,
        from_state=ApprovalStatus.PENDING.value,
        to_state=ApprovalStatus.REJECTED.value,
        comment=comment,
        idempotency_key=idempotency_key,
    )
    await approval_repo.append_event(session, event)

    # Set expense to REJECTED
    await expense_repo.update_status(
        session, expense_id, company_id, ExpenseStatus.REJECTED.value
    )

    # Notify submitter
    _enqueue_notification(expense_id, "expense_rejected", expense.user_id)

    return {"status": "rejected", "message": "Expense rejected"}


def _enqueue_notification(expense_id: str, template: str, recipient_user_id: str) -> None:
    """
    Enqueue a notification email via Celery. Never calls SendGrid directly.
    """
    try:
        from app.workers.notification_worker import send_notification
        send_notification.delay(expense_id, template, recipient_user_id)
        logger.info("Enqueued notification: %s for expense %s to user %s", template, expense_id, recipient_user_id[:8])
    except Exception as exc:
        logger.error("Failed to enqueue notification: %s", exc)
