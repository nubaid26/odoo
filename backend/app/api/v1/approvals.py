# backend/app/api/v1/approvals.py
"""
Approval action routes — approve and reject expenses.
Thin handlers: validate, call service, return response.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import get_current_user, require_role
from app.services import approval_service

logger = logging.getLogger("trustflow.api.approvals")
router = APIRouter()


class ApprovalActionRequest(BaseModel):
    """Request body for approve/reject actions."""
    comment: Optional[str] = Field(None, max_length=1000)


@router.post("/{expense_id}/approve")
async def approve_expense(
    expense_id: str,
    request: Request,
    body: ApprovalActionRequest = ApprovalActionRequest(),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("manager", "admin")),
):
    """
    Approve an expense at the current approval step.

    Requires Idempotency-Key header and manager/admin role.
    Only the assigned approver for the current step can action it.
    """
    idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    try:
        result = await approval_service.approve_expense(
            session=session,
            expense_id=expense_id,
            company_id=current_user["company_id"],
            approver_id=current_user["user_id"],
            approver_role=current_user["role"],
            comment=body.comment,
            idempotency_key=idempotency_key,
        )
        await session.commit()
        return result

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{expense_id}/reject")
async def reject_expense(
    expense_id: str,
    request: Request,
    body: ApprovalActionRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("manager", "admin")),
):
    """
    Reject an expense at the current approval step.

    Requires comment explaining the rejection reason.
    """
    idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    if not body.comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection comment is required",
        )

    try:
        result = await approval_service.reject_expense(
            session=session,
            expense_id=expense_id,
            company_id=current_user["company_id"],
            approver_id=current_user["user_id"],
            approver_role=current_user["role"],
            comment=body.comment,
            idempotency_key=idempotency_key,
        )
        await session.commit()
        return result

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
