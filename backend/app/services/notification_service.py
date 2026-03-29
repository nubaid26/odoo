# backend/app/services/notification_service.py
"""
Notification service — enqueues Celery tasks for email delivery.
Never calls SendGrid directly — only enqueues tasks to the notifications queue.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("trustflow.services.notification")


def enqueue_notification(
    expense_id: str,
    template_name: str,
    recipient_user_id: str,
) -> None:
    """
    Enqueue a notification email via Celery.

    This function NEVER calls SendGrid directly.
    It only enqueues a task on the notifications queue.

    Args:
        expense_id: Expense UUID for context.
        template_name: Email template name (e.g., "approval_request").
        recipient_user_id: User UUID of the recipient.
    """
    try:
        from app.workers.notification_worker import send_notification
        send_notification.delay(expense_id, template_name, recipient_user_id)
        logger.info(
            "Enqueued notification: template=%s, expense=%s, recipient=%s",
            template_name, expense_id, recipient_user_id[:8],
        )
    except Exception as exc:
        logger.error("Failed to enqueue notification: %s", exc)
