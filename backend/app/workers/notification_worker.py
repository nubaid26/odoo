# backend/app/workers/notification_worker.py
"""
Notification worker — Celery task on queue 'notifications'.
Calls SendGrid via the sendgrid external client.
Retry: 60s, 120s, 300s. Dead-letter to async_jobs on final failure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime

from app.workers.celery_app import celery_app

logger = logging.getLogger("trustflow.workers.notification")

RETRY_COUNTDOWNS = [60, 120, 300]


@celery_app.task(
    bind=True,
    name="app.workers.notification_worker.send_notification",
    queue="notifications",
    max_retries=3,
)
def send_notification(
    self,
    expense_id: str,
    template_name: str,
    recipient_user_id: str,
) -> dict:
    """
    Send a notification email via SendGrid.

    Loads the recipient user, builds template context from the expense,
    renders the Jinja2 template, and sends via SendGrid SDK.

    On failure: retries with 60s/120s/300s delays.
    After all retries: dead-letter to async_jobs with status=failed.

    Args:
        expense_id: Expense UUID for context.
        template_name: Template name (approval_request, expense_approved, expense_rejected).
        recipient_user_id: User UUID of the email recipient.

    Returns:
        Dict with send result.
    """
    start_time = time.time()

    logger.info(
        json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "celery-notification-worker",
            "task_id": self.request.id,
            "expense_id": expense_id,
            "event": "notification_started",
            "template": template_name,
        })
    )

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Build context and send
        result = loop.run_until_complete(
            _build_and_send(expense_id, template_name, recipient_user_id)
        )
        loop.close()

        duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "INFO",
                "service": "celery-notification-worker",
                "task_id": self.request.id,
                "expense_id": expense_id,
                "event": "notification_sent",
                "template": template_name,
                "duration_ms": duration_ms,
            })
        )

        return {"status": "sent", "template": template_name}

    except Exception as exc:
        logger.error(
            json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "service": "celery-notification-worker",
                "task_id": self.request.id,
                "expense_id": expense_id,
                "event": "notification_failed",
                "template": template_name,
                "error": str(exc),
                "attempt": self.request.retries + 1,
            })
        )

        if self.request.retries < self.max_retries:
            countdown = RETRY_COUNTDOWNS[min(self.request.retries, len(RETRY_COUNTDOWNS) - 1)]
            raise self.retry(exc=exc, countdown=countdown)

        # All retries exhausted — dead-letter to async_jobs
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _dead_letter(expense_id, template_name, str(exc))
        )
        loop.close()

        return {"status": "failed", "error": str(exc)}


async def _build_and_send(
    expense_id: str,
    template_name: str,
    recipient_user_id: str,
) -> None:
    """Build email context from DB and send via SendGrid."""
    from app.db.session import async_session_factory
    from app.db.models import Expense, User
    from app.external.sendgrid import send_email
    from sqlalchemy import select

    async with async_session_factory() as session:
        # Fetch recipient
        stmt = select(User).where(User.id == recipient_user_id)
        result = await session.execute(stmt)
        recipient = result.scalar_one_or_none()
        if not recipient:
            raise ValueError(f"Recipient user {recipient_user_id} not found")

        # Fetch expense
        stmt = select(Expense).where(Expense.id == expense_id)
        result = await session.execute(stmt)
        expense = result.scalar_one_or_none()
        if not expense:
            raise ValueError(f"Expense {expense_id} not found")

        # Fetch submitter
        stmt = select(User).where(User.id == expense.user_id)
        result = await session.execute(stmt)
        submitter = result.scalar_one_or_none()

        # Build template context
        context = {
            "expense_id": expense.id,
            "amount": str(expense.converted_amount or expense.original_amount),
            "currency": expense.original_currency,
            "category": expense.category,
            "description": expense.description or "",
            "vendor_name": expense.vendor_name or "N/A",
            "status": expense.status,
            "submitter_name": submitter.name if submitter else "Unknown",
            "submitter_email": submitter.email if submitter else "",
            "recipient_name": recipient.name,
            "created_at": expense.created_at.strftime("%Y-%m-%d %H:%M") if expense.created_at else "",
        }

        # Determine subject and template file
        template_file = f"{template_name}.html"
        subjects = {
            "approval_request": f"TrustFlow: Approval Required — Expense {expense.id[:8]}",
            "expense_approved": f"TrustFlow: Your Expense {expense.id[:8]} Has Been Approved",
            "expense_rejected": f"TrustFlow: Your Expense {expense.id[:8]} Has Been Rejected",
        }
        subject = subjects.get(template_name, f"TrustFlow: Expense {expense.id[:8]}")

        # Send email via SendGrid
        send_email(
            to_email=recipient.email,
            subject=subject,
            template_name=template_file,
            context=context,
        )


async def _dead_letter(expense_id: str, template_name: str, error: str) -> None:
    """Write failed notification to async_jobs as dead-letter."""
    from app.db.session import async_session_factory
    from app.db.models import AsyncJob
    import uuid

    async with async_session_factory() as session:
        job = AsyncJob(
            id=str(uuid.uuid4()),
            expense_id=expense_id,
            job_type="notification",
            status="failed",
            result_json=json.dumps({
                "template": template_name,
                "error": error,
                "dead_letter": True,
                "failed_at": datetime.utcnow().isoformat(),
            }),
        )
        session.add(job)
        await session.commit()
        logger.warning(
            "Dead-lettered notification for expense %s (template: %s)",
            expense_id, template_name,
        )
