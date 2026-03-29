# backend/app/workers/ocr_worker.py
"""
OCR worker — Celery task on queue 'ocr'.
Downloads receipt from MinIO via boto3, runs local Tesseract OCR,
updates expense_proofs, then enqueues validation task.
No external OCR API — fully local.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from app.workers.celery_app import celery_app
from app.config import settings

logger = logging.getLogger("trustflow.workers.ocr")


@celery_app.task(
    bind=True,
    name="app.workers.ocr_worker.process_ocr",
    queue="ocr",
    max_retries=3,
    default_retry_delay=30,
)
def process_ocr(self, expense_id: str, proof_id: str) -> dict:
    """
    OCR processing task.

    1. Downloads receipt from MinIO via boto3.
    2. Runs local Tesseract OCR via pytesseract.
    3. Updates expense_proofs with OCR results.
    4. Enqueues validation task.

    Args:
        expense_id: Expense UUID.
        proof_id: ExpenseProof UUID.

    Returns:
        Dict with OCR results.
    """
    import asyncio
    start_time = time.time()

    logger.info(
        json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "celery-ocr-worker",
            "task_id": self.request.id,
            "expense_id": expense_id,
            "event": "ocr_started",
        })
    )

    try:
        # Update job status to running
        asyncio.get_event_loop().run_until_complete(
            _update_job_status(expense_id, "ocr", "running")
        )

        # Step 1: Download receipt from MinIO
        from app.external.minio_client import download_file
        from app.db.session import async_session_factory
        from app.db.models import ExpenseProof
        from sqlalchemy import select

        # Get the proof record to find minio_object_key
        async def get_proof():
            async with async_session_factory() as session:
                stmt = select(ExpenseProof).where(ExpenseProof.id == proof_id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        proof = asyncio.get_event_loop().run_until_complete(get_proof())
        if not proof or not proof.minio_object_key:
            logger.warning("No receipt file found for proof %s", proof_id)
            asyncio.get_event_loop().run_until_complete(
                _update_job_status(expense_id, "ocr", "completed", {"message": "No receipt file"})
            )
            # Still enqueue validation with empty OCR
            from app.workers.validation_worker import run_validation
            run_validation.delay(expense_id)
            return {"status": "no_file", "expense_id": expense_id}

        # Download file bytes from MinIO
        image_bytes = download_file(settings.MINIO_BUCKET, proof.minio_object_key)

        # Step 2: Run local Tesseract OCR
        from app.external.tesseract import extract_text_from_image_bytes
        ocr_result = extract_text_from_image_bytes(image_bytes)

        # Step 3: Update expense_proofs with OCR data
        async def update_proof():
            async with async_session_factory() as session:
                from app.repositories.expense_repo import update_proof_ocr
                await update_proof_ocr(session, proof_id, {
                    "ocr_raw_text": ocr_result.raw_text[:10000],  # Truncate for safety
                    "ocr_parsed_amount": ocr_result.parsed_amount,
                    "ocr_parsed_vendor": ocr_result.parsed_vendor,
                    "ocr_parsed_gstin": ocr_result.parsed_gstin,
                    "ocr_parsed_date": ocr_result.parsed_date,
                    "ocr_confidence": ocr_result.confidence,
                    "verified_at": datetime.utcnow(),
                })
                await session.commit()

        asyncio.get_event_loop().run_until_complete(update_proof())

        duration_ms = int((time.time() - start_time) * 1000)

        # Update job status
        result_data = {
            "ocr_confidence": str(ocr_result.confidence),
            "parsed_amount": str(ocr_result.parsed_amount) if ocr_result.parsed_amount else None,
            "parsed_vendor": ocr_result.parsed_vendor,
            "parsed_gstin": ocr_result.parsed_gstin,
            "parsed_date": ocr_result.parsed_date,
        }
        asyncio.get_event_loop().run_until_complete(
            _update_job_status(expense_id, "ocr", "completed", result_data)
        )

        logger.info(
            json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "INFO",
                "service": "celery-ocr-worker",
                "task_id": self.request.id,
                "expense_id": expense_id,
                "event": "ocr_complete",
                "ocr_confidence": str(ocr_result.confidence),
                "duration_ms": duration_ms,
            })
        )

        # Step 4: Enqueue validation task
        from app.workers.validation_worker import run_validation
        run_validation.delay(expense_id)

        return result_data

    except Exception as exc:
        logger.error(
            json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "service": "celery-ocr-worker",
                "task_id": self.request.id,
                "expense_id": expense_id,
                "event": "ocr_failed",
                "error": str(exc),
            })
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))

        # All retries exhausted — flag for manual review
        asyncio.get_event_loop().run_until_complete(
            _update_job_status(expense_id, "ocr", "failed", {"error": str(exc)})
        )

        # Still enqueue validation with zero OCR confidence
        from app.workers.validation_worker import run_validation
        run_validation.delay(expense_id)

        return {"status": "failed", "error": str(exc)}


async def _update_job_status(
    expense_id: str,
    job_type: str,
    status: str,
    result_data: dict = None,
) -> None:
    """Update the async_jobs status for tracking."""
    from app.db.session import async_session_factory
    from app.db.models import AsyncJob
    from sqlalchemy import select, update, and_

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
