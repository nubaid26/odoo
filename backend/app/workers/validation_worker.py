# backend/app/workers/validation_worker.py
"""
Validation worker — Celery task on queue 'validation'.
Runs 4 checks via validation_service, writes bill_validation_logs,
then enqueues trust task.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime

from app.workers.celery_app import celery_app

logger = logging.getLogger("trustflow.workers.validation")


@celery_app.task(
    bind=True,
    name="app.workers.validation_worker.run_validation",
    queue="validation",
    max_retries=3,
    default_retry_delay=15,
)
def run_validation(self, expense_id: str) -> dict:
    """
    Run all 4 validation checks for an expense.

    1. Math check (OCR vs submitted amount)
    2. Date check (within 90 days)
    3. GST check (API or regex)
    4. GPS check (geocoding + nearby + Haversine)

    Each check writes a row to bill_validation_logs.
    On completion, enqueues the trust scoring task.

    Args:
        expense_id: Expense UUID.

    Returns:
        Dict with validation summary.
    """
    start_time = time.time()

    logger.info(
        json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "celery-validation-worker",
            "task_id": self.request.id,
            "expense_id": expense_id,
            "event": "validation_started",
        })
    )

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Update job status
        loop.run_until_complete(
            _update_job_status(expense_id, "validation", "running")
        )

        # Run validation checks
        result = loop.run_until_complete(_run_checks(expense_id))
        loop.close()

        duration_ms = int((time.time() - start_time) * 1000)

        result_data = {
            "passed_count": result["passed_count"],
            "failed_count": result["failed_count"],
            "checks": result["checks"],
        }

        # Update job status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _update_job_status(expense_id, "validation", "completed", result_data)
        )
        loop.close()

        logger.info(
            json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "INFO",
                "service": "celery-validation-worker",
                "task_id": self.request.id,
                "expense_id": expense_id,
                "event": "validation_complete",
                "passed": result["passed_count"],
                "failed": result["failed_count"],
                "duration_ms": duration_ms,
            })
        )

        # Enqueue trust scoring
        from app.workers.trust_worker import compute_trust
        compute_trust.delay(expense_id)

        return result_data

    except Exception as exc:
        logger.error(
            json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "service": "celery-validation-worker",
                "task_id": self.request.id,
                "expense_id": expense_id,
                "event": "validation_failed",
                "error": str(exc),
            })
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=15 * (self.request.retries + 1))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _update_job_status(expense_id, "validation", "failed", {"error": str(exc)})
        )
        loop.close()

        # Still enqueue trust with whatever data exists
        from app.workers.trust_worker import compute_trust
        compute_trust.delay(expense_id)

        return {"status": "failed", "error": str(exc)}


async def _run_checks(expense_id: str) -> dict:
    """Run all validation checks within an async context."""
    from app.db.session import async_session_factory
    from app.db.models import Expense, ExpenseProof
    from app.services.validation_service import run_all_checks
    from sqlalchemy import select

    async with async_session_factory() as session:
        # Fetch expense
        stmt = select(Expense).where(Expense.id == expense_id)
        result = await session.execute(stmt)
        expense = result.scalar_one_or_none()
        if not expense:
            raise ValueError(f"Expense {expense_id} not found")

        # Fetch proof
        stmt = select(ExpenseProof).where(ExpenseProof.expense_id == expense_id)
        result = await session.execute(stmt)
        proof = result.scalar_one_or_none()
        if not proof:
            from app.db.models import ExpenseProof as EP
            proof = EP(expense_id=expense_id, proof_type="none")

        # Run checks
        validation_result = await run_all_checks(session, expense, proof)
        await session.commit()

        return {
            "passed_count": validation_result.passed_count,
            "failed_count": validation_result.failed_count,
            "checks": [
                {
                    "check_type": c.check_type,
                    "passed": c.passed,
                    "confidence": str(c.confidence),
                    "fraud_signal": c.fraud_signal,
                    "message": c.message,
                }
                for c in validation_result.checks
            ],
        }


async def _update_job_status(
    expense_id: str,
    job_type: str,
    status: str,
    result_data: dict = None,
) -> None:
    """Update the async_jobs status."""
    from app.db.session import async_session_factory
    from app.db.models import AsyncJob
    from sqlalchemy import update, and_

    async with async_session_factory() as session:
        stmt = (
            update(AsyncJob)
            .where(
                and_(
                    AsyncJob.expense_id == expense_id,
                    AsyncJob.job_type == job_type,
                )
            )
            .values(
                status=status,
                result_json=json.dumps(result_data) if result_data else None,
            )
        )
        await session.execute(stmt)
        await session.commit()
