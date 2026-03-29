# backend/app/workers/trust_worker.py
"""
Trust scoring worker — Celery task on queue 'trust'.
Computes weighted trust score, writes immutable trust_score_audit row,
then calls approval routing logic.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from decimal import Decimal

from app.workers.celery_app import celery_app

logger = logging.getLogger("trustflow.workers.trust")


@celery_app.task(
    bind=True,
    name="app.workers.trust_worker.compute_trust",
    queue="trust",
    max_retries=3,
    default_retry_delay=10,
)
def compute_trust(self, expense_id: str) -> dict:
    """
    Compute trust score and route through approval chain.

    1. Gather input signals from validation logs and expense data.
    2. Compute weighted trust score via trust_service.
    3. Write immutable trust_score_audit row.
    4. Call approval routing.

    Args:
        expense_id: Expense UUID.

    Returns:
        Dict with trust score results.
    """
    start_time = time.time()

    logger.info(
        json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "celery-trust-worker",
            "task_id": self.request.id,
            "expense_id": expense_id,
            "event": "trust_started",
        })
    )

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Update job status
        loop.run_until_complete(
            _update_job_status(expense_id, "trust", "running")
        )

        # Compute trust and route
        result = loop.run_until_complete(_compute_and_route(expense_id))
        loop.close()

        duration_ms = int((time.time() - start_time) * 1000)

        result_data = {
            "score": str(result["score"]),
            "grade": result["grade"],
            "routing_result": result["routing_result"],
        }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _update_job_status(expense_id, "trust", "completed", result_data)
        )
        loop.close()

        logger.info(
            json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "INFO",
                "service": "celery-trust-worker",
                "task_id": self.request.id,
                "expense_id": expense_id,
                "event": "trust_complete",
                "trust_score": str(result["score"]),
                "trust_grade": result["grade"],
                "duration_ms": duration_ms,
            })
        )

        return result_data

    except Exception as exc:
        logger.error(
            json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "service": "celery-trust-worker",
                "task_id": self.request.id,
                "expense_id": expense_id,
                "event": "trust_failed",
                "error": str(exc),
            })
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10 * (self.request.retries + 1))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _update_job_status(expense_id, "trust", "failed", {"error": str(exc)})
        )
        loop.close()

        return {"status": "failed", "error": str(exc)}


async def _compute_and_route(expense_id: str) -> dict:
    """Compute trust score and route expense through approval chain."""
    from app.db.session import async_session_factory
    from app.db.models import (
        Expense, ExpenseProof, BillValidationLog, TrustScoreAudit,
    )
    from app.services.trust_service import compute_trust_score
    from app.services.approval_service import route_expense
    from app.repositories import expense_repo, trust_audit_repo
    from app.domain.models import TrustInput
    from sqlalchemy import select, and_

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

        # Fetch validation logs
        validation_logs = await expense_repo.get_validation_logs(session, expense_id)

        # Gather input signals
        passed_count = sum(1 for log in validation_logs if log.passed)
        total_count = len(validation_logs)
        pass_rate = Decimal(str(passed_count)) / Decimal(str(total_count)) if total_count > 0 else Decimal("0")

        # GST signals from validation logs
        gst_verified = False
        gst_active = False
        gst_unverified = False
        for log in validation_logs:
            if "GST" in log.check_type:
                if log.check_type == "GST_API_VERIFIED":
                    gst_verified = True
                    gst_active = True
                elif log.check_type in ("GST_UNVERIFIED", "GST_REGEX_ONLY"):
                    gst_unverified = True
                    gst_active = log.passed

        # Vendor signals
        vendor_exact = False
        vendor_fuzzy = False
        fuzzy_ratio = Decimal("0")
        for log in validation_logs:
            if log.check_type == "GPS_CHECK" and log.passed:
                if log.confidence >= Decimal("0.85"):
                    vendor_exact = True
                elif log.confidence >= Decimal("0.6"):
                    vendor_fuzzy = True
                fuzzy_ratio = log.confidence

        # Behavior signals
        fraud_count = await expense_repo.get_fraud_signal_count(session, expense.user_id, 90)
        expense_count = await expense_repo.get_expense_count_for_user(session, expense.user_id)
        is_first = expense_count <= 1

        # Proof type
        proof_type = proof.proof_type if proof else "none"

        # Build trust input
        trust_input = TrustInput(
            expense_id=expense_id,
            user_id=expense.user_id,
            company_id=expense.company_id,
            receipt_pass_rate=pass_rate,
            gst_verified=gst_verified,
            gst_active=gst_active,
            gst_unverified=gst_unverified,
            vendor_exact_match=vendor_exact,
            vendor_fuzzy_match=vendor_fuzzy,
            vendor_fuzzy_ratio=fuzzy_ratio,
            fraud_signals_90d=fraud_count,
            is_first_expense=is_first,
            proof_type=proof_type,
        )

        # Compute score
        trust_result = compute_trust_score(trust_input)

        # Write immutable audit row
        audit = TrustScoreAudit(
            expense_id=expense_id,
            score=trust_result.score,
            grade=trust_result.grade,
            receipt_score=trust_result.receipt_score,
            gst_score=trust_result.gst_score,
            vendor_score=trust_result.vendor_score,
            behavior_score=trust_result.behavior_score,
            proof_score=trust_result.proof_score,
            formula_version=trust_result.formula_version,
            input_hash=trust_result.input_hash,
            weights_json=trust_result.weights_json,
        )
        await trust_audit_repo.insert(session, audit)

        # Route through approval chain
        routing_result = await route_expense(
            session,
            expense_id,
            expense.company_id,
            trust_result.grade,
            trust_result.score,
        )

        await session.commit()

        return {
            "score": trust_result.score,
            "grade": trust_result.grade,
            "routing_result": routing_result,
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
