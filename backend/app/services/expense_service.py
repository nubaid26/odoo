# backend/app/services/expense_service.py
"""
Expense service — orchestrates expense creation flow:
1. Idempotency check
2. Currency conversion
3. File upload to MinIO
4. DB writes (expense, proof, async jobs)
5. Celery job enqueue
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Expense, ExpenseProof, AsyncJob
from app.domain.enums import ExpenseStatus, ProofType, JobType, JobStatus
from app.external import minio_client
from app.repositories import expense_repo
from app.services import currency_service

logger = logging.getLogger("trustflow.services.expense")


def _get_redis() -> aioredis.Redis:
    """Create a Redis client for idempotency cache."""
    return aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.CACHE_REDIS_DB,
        decode_responses=True,
    )


async def create_expense(
    session: AsyncSession,
    user_id: str,
    company_id: str,
    amount: Decimal,
    currency: str,
    category: str,
    description: Optional[str],
    vendor_name: Optional[str],
    gps_lat: Optional[Decimal],
    gps_lng: Optional[Decimal],
    receipt_file: Optional[bytes],
    receipt_content_type: str,
    receipt_filename: str,
    idempotency_key: str,
) -> dict:
    """
    Create a new expense with receipt upload and async job enqueue.

    Returns 202-style response dict immediately for fast HTTP response.

    Args:
        session: Database session.
        user_id: Submitting user's UUID.
        company_id: User's company UUID.
        amount: Original expense amount.
        currency: ISO currency code.
        category: Expense category.
        description: Optional description.
        vendor_name: Optional vendor name.
        gps_lat: Optional GPS latitude.
        gps_lng: Optional GPS longitude.
        receipt_file: Receipt image bytes.
        receipt_content_type: MIME type of the receipt file.
        receipt_filename: Original filename.
        idempotency_key: UUID for deduplication.

    Returns:
        Dict with expense_id, job_ids, and status.
    """
    # ── Step 1: Idempotency check ──
    r = _get_redis()
    try:
        idempotency_cache_key = f"idempotency:{idempotency_key}"
        cached = await r.get(idempotency_cache_key)
        if cached:
            logger.info("Idempotency hit for key %s", idempotency_key)
            return json.loads(cached)
    finally:
        await r.aclose()

    # Check DB too for idempotency
    existing = await expense_repo.get_by_idempotency_key(session, idempotency_key)
    if existing:
        logger.info("Idempotency DB hit for key %s", idempotency_key)
        response = {
            "expense_id": existing.id,
            "job_ids": [],
            "status": "processing",
        }
        return response

    # ── Step 2: Currency conversion ──
    conversion = await currency_service.convert_currency(amount, currency, "INR")

    # ── Step 3: Create expense record ──
    expense = Expense(
        id=str(uuid.uuid4()),
        user_id=user_id,
        company_id=company_id,
        original_amount=conversion["original_amount"],
        original_currency=conversion["original_currency"],
        converted_amount=conversion["converted_amount"],
        exchange_rate=conversion["exchange_rate"],
        conversion_at=conversion["conversion_at"],
        category=category,
        description=description,
        vendor_name=vendor_name,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        status=ExpenseStatus.DRAFT.value,
        idempotency_key=idempotency_key,
    )
    expense = await expense_repo.create_expense(session, expense)

    # ── Step 4: Upload receipt to MinIO and create proof ──
    minio_object_key = None
    proof_type = ProofType.NONE.value

    if receipt_file:
        minio_object_key = f"receipts/{expense.id}/{receipt_filename}"
        minio_client.upload_file(
            bucket=settings.MINIO_BUCKET,
            key=minio_object_key,
            data=receipt_file,
            content_type=receipt_content_type,
        )
        proof_type = ProofType.RECEIPT.value
        logger.info("Uploaded receipt to s3://%s/%s", settings.MINIO_BUCKET, minio_object_key)

    proof = ExpenseProof(
        id=str(uuid.uuid4()),
        expense_id=expense.id,
        proof_type=proof_type,
        minio_object_key=minio_object_key,
    )
    await expense_repo.create_proof(session, proof)

    # ── Step 5: Create async jobs ──
    job_ids = []
    for job_type in [JobType.OCR, JobType.VALIDATION, JobType.TRUST]:
        job = AsyncJob(
            id=str(uuid.uuid4()),
            expense_id=expense.id,
            job_type=job_type.value,
            status=JobStatus.QUEUED.value,
        )
        job = await expense_repo.create_async_job(session, job)
        job_ids.append(job.id)

    # Commit all writes
    await session.commit()

    # ── Step 6: Enqueue OCR task (starts the pipeline) ──
    from app.workers.ocr_worker import process_ocr
    celery_result = process_ocr.delay(expense.id, proof.id)
    logger.info(
        "Enqueued OCR task %s for expense %s",
        celery_result.id, expense.id,
    )

    # ── Step 7: Cache idempotency response ──
    response = {
        "expense_id": expense.id,
        "job_ids": job_ids,
        "status": "processing",
    }
    r = _get_redis()
    try:
        await r.setex(
            f"idempotency:{idempotency_key}",
            86400,  # 24h TTL
            json.dumps(response),
        )
    finally:
        await r.aclose()

    return response
