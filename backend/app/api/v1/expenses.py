# backend/app/api/v1/expenses.py
"""
Expense routes — submit expense, list expenses, get detail.
Thin handlers only — no business logic.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import get_current_user, require_role
from app.middleware.rate_limit import rate_limit_expense_create
from app.repositories import expense_repo, user_repo
from app.services import expense_service

logger = logging.getLogger("trustflow.api.expenses")
router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_expense(
    request: Request,
    amount: Decimal = Form(...),
    currency: str = Form(..., min_length=3, max_length=3),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    vendor_name: Optional[str] = Form(None),
    gps_lat: Optional[Decimal] = Form(None),
    gps_lng: Optional[Decimal] = Form(None),
    receipt: Optional[UploadFile] = File(None),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Submit a new expense with optional receipt upload.

    Requires Idempotency-Key header (UUID).
    Returns 202 Accepted with expense_id, job_ids, and status: "processing".
    """
    # Validate Idempotency-Key header
    idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    # Rate limit
    await rate_limit_expense_create(current_user["user_id"])

    # Read receipt file
    receipt_bytes = None
    receipt_content_type = "application/octet-stream"
    receipt_filename = "receipt"
    if receipt:
        receipt_bytes = await receipt.read()
        receipt_content_type = receipt.content_type or "image/jpeg"
        receipt_filename = receipt.filename or "receipt"

    # Attach user_id to request state for logging
    request.state.user_id = current_user["user_id"]

    result = await expense_service.create_expense(
        session=session,
        user_id=current_user["user_id"],
        company_id=current_user["company_id"],
        amount=amount,
        currency=currency,
        category=category,
        description=description,
        vendor_name=vendor_name,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        receipt_file=receipt_bytes,
        receipt_content_type=receipt_content_type,
        receipt_filename=receipt_filename,
        idempotency_key=idempotency_key,
    )

    return result


@router.get("")
async def list_expenses(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List expenses scoped by user role.

    - Employee: own expenses only
    - Manager: direct reports' expenses
    - Admin: company-scoped
    """
    role = current_user["role"]
    company_id = current_user["company_id"]
    user_id = current_user["user_id"]

    if role == "employee":
        expenses = await expense_repo.get_by_user(
            session, user_id, company_id, status_filter
        )
    elif role == "manager":
        # Get direct reports
        reports = await user_repo.get_direct_reports(session, user_id, company_id)
        report_ids = [r.id for r in reports] + [user_id]

        all_expenses = []
        for rid in report_ids:
            user_expenses = await expense_repo.get_by_user(
                session, rid, company_id, status_filter
            )
            all_expenses.extend(user_expenses)
        expenses = sorted(all_expenses, key=lambda e: e.created_at, reverse=True)[:limit]
    else:
        # Admin sees all company expenses
        expenses = await expense_repo.list_with_filters(
            session, company_id, status=status_filter, limit=limit, offset=offset
        )

    return [
        {
            "id": e.id,
            "amount": str(e.original_amount),
            "currency": e.original_currency,
            "converted_amount": str(e.converted_amount) if e.converted_amount else None,
            "category": e.category,
            "description": e.description,
            "vendor_name": e.vendor_name,
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in expenses
    ]


@router.get("/{expense_id}")
async def get_expense(
    expense_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get expense detail with proofs, validation logs, and trust audit."""
    expense = await expense_repo.get_by_id(
        session, expense_id, current_user["company_id"]
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Role-based access check
    role = current_user["role"]
    if role == "employee" and expense.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    elif role == "manager":
        reports = await user_repo.get_direct_reports(
            session, current_user["user_id"], current_user["company_id"]
        )
        report_ids = {r.id for r in reports} | {current_user["user_id"]}
        if expense.user_id not in report_ids:
            raise HTTPException(status_code=403, detail="Access denied")

    # Load related data
    proofs = await expense_repo.get_proofs_for_expense(session, expense_id)
    validation_logs = await expense_repo.get_validation_logs(session, expense_id)
    jobs = await expense_repo.get_async_jobs(session, expense_id)

    # Load trust audit
    from app.repositories import trust_audit_repo
    trust_audit = await trust_audit_repo.get_latest_for_expense(session, expense_id)

    # Load approval events
    from app.repositories import approval_repo
    approval_events = await approval_repo.get_events_for_expense(session, expense_id)
    approval_steps = await approval_repo.get_steps_for_expense(session, expense_id)

    return {
        "id": expense.id,
        "user_id": expense.user_id,
        "amount": str(expense.original_amount),
        "currency": expense.original_currency,
        "converted_amount": str(expense.converted_amount) if expense.converted_amount else None,
        "exchange_rate": str(expense.exchange_rate) if expense.exchange_rate else None,
        "category": expense.category,
        "description": expense.description,
        "vendor_name": expense.vendor_name,
        "gps_lat": str(expense.gps_lat) if expense.gps_lat else None,
        "gps_lng": str(expense.gps_lng) if expense.gps_lng else None,
        "status": expense.status,
        "created_at": expense.created_at.isoformat() if expense.created_at else None,
        "proofs": [
            {
                "id": p.id,
                "proof_type": p.proof_type,
                "ocr_confidence": str(p.ocr_confidence) if p.ocr_confidence else None,
                "ocr_parsed_amount": str(p.ocr_parsed_amount) if p.ocr_parsed_amount else None,
                "ocr_parsed_vendor": p.ocr_parsed_vendor,
                "ocr_parsed_gstin": p.ocr_parsed_gstin,
                "ocr_parsed_date": p.ocr_parsed_date,
            }
            for p in proofs
        ],
        "validation_logs": [
            {
                "check_type": v.check_type,
                "passed": v.passed,
                "confidence": str(v.confidence) if v.confidence else None,
                "fraud_signal": v.fraud_signal,
                "message": v.message,
            }
            for v in validation_logs
        ],
        "trust_audit": {
            "score": str(trust_audit.score),
            "grade": trust_audit.grade,
            "receipt_score": str(trust_audit.receipt_score),
            "gst_score": str(trust_audit.gst_score),
            "vendor_score": str(trust_audit.vendor_score),
            "behavior_score": str(trust_audit.behavior_score),
            "proof_score": str(trust_audit.proof_score),
            "formula_version": trust_audit.formula_version,
        } if trust_audit else None,
        "approval_steps": [
            {
                "id": s.id,
                "approver_id": s.approver_id,
                "step_order": s.step_order,
                "current_status": s.current_status,
            }
            for s in approval_steps
        ],
        "approval_events": [
            {
                "id": e.id,
                "actor_id": e.actor_id,
                "from_state": e.from_state,
                "to_state": e.to_state,
                "comment": e.comment,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in approval_events
        ],
        "jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "result_json": j.result_json,
            }
            for j in jobs
        ],
    }
