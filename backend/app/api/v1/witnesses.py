# backend/app/api/v1/witnesses.py
"""
Witness routes — add witness to expense, confirm via HMAC token.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.services import witness_service

logger = logging.getLogger("trustflow.api.witnesses")
router = APIRouter()


class AddWitnessRequest(BaseModel):
    """Request to add a witness to an expense."""
    witness_user_id: str = Field(..., description="UUID of the witness user")


@router.post("/expenses/{expense_id}/witnesses", status_code=status.HTTP_201_CREATED)
async def add_witness(
    expense_id: str,
    body: AddWitnessRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Add a witness to an expense.

    The witness must be in the same company as the submitter.
    Generates a confirmation token (HMAC-SHA256).
    """
    try:
        result = await witness_service.add_witness(
            session=session,
            expense_id=expense_id,
            witness_user_id=body.witness_user_id,
            company_id=current_user["company_id"],
        )
        await session.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/witnesses/confirm/{token}")
async def confirm_witness(
    token: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Confirm a witness via their HMAC token.

    Public endpoint — token is the authentication.
    """
    try:
        result = await witness_service.confirm_witness(session=session, token=token)
        await session.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
