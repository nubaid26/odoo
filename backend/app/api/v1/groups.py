# backend/app/api/v1/groups.py
"""
Expense group routes — create groups, add expenses, view details.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExpenseGroup, ExpenseGroupMember, Expense
from app.db.session import get_db
from app.middleware.auth import get_current_user

logger = logging.getLogger("trustflow.api.groups")
router = APIRouter()


class CreateGroupRequest(BaseModel):
    """Request to create an expense group."""
    name: str = Field(..., min_length=2, max_length=255)


class AddExpenseToGroupRequest(BaseModel):
    """Request to add an expense to a group."""
    expense_id: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group(
    body: CreateGroupRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a named expense group for bundling trip or project expenses."""
    group = ExpenseGroup(
        id=str(uuid.uuid4()),
        name=body.name,
        company_id=current_user["company_id"],
        created_by=current_user["user_id"],
    )
    session.add(group)
    await session.flush()
    await session.refresh(group)
    await session.commit()

    return {
        "id": group.id,
        "name": group.name,
        "created_by": group.created_by,
        "created_at": group.created_at.isoformat() if group.created_at else None,
    }


@router.post("/{group_id}/expenses", status_code=status.HTTP_201_CREATED)
async def add_expense_to_group(
    group_id: str,
    body: AddExpenseToGroupRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add an expense to an existing group."""
    # Verify group exists and belongs to company
    stmt = select(ExpenseGroup).where(
        and_(
            ExpenseGroup.id == group_id,
            ExpenseGroup.company_id == current_user["company_id"],
        )
    )
    result = await session.execute(stmt)
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Verify expense exists and belongs to company
    stmt = select(Expense).where(
        and_(
            Expense.id == body.expense_id,
            Expense.company_id == current_user["company_id"],
        )
    )
    result = await session.execute(stmt)
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Check for duplicate
    stmt = select(ExpenseGroupMember).where(
        and_(
            ExpenseGroupMember.group_id == group_id,
            ExpenseGroupMember.expense_id == body.expense_id,
        )
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Expense already in group")

    member = ExpenseGroupMember(
        id=str(uuid.uuid4()),
        group_id=group_id,
        expense_id=body.expense_id,
    )
    session.add(member)
    await session.commit()

    return {"group_id": group_id, "expense_id": body.expense_id, "status": "added"}


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get group detail with all expenses and aggregate totals."""
    stmt = select(ExpenseGroup).where(
        and_(
            ExpenseGroup.id == group_id,
            ExpenseGroup.company_id == current_user["company_id"],
        )
    )
    result = await session.execute(stmt)
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Get members with expenses
    stmt = (
        select(ExpenseGroupMember)
        .where(ExpenseGroupMember.group_id == group_id)
    )
    result = await session.execute(stmt)
    members = list(result.scalars().all())

    expenses = []
    total_original = Decimal("0")
    total_converted = Decimal("0")

    for member in members:
        stmt = select(Expense).where(Expense.id == member.expense_id)
        result = await session.execute(stmt)
        expense = result.scalar_one_or_none()
        if expense:
            total_original += expense.original_amount
            if expense.converted_amount:
                total_converted += expense.converted_amount
            expenses.append({
                "id": expense.id,
                "amount": str(expense.original_amount),
                "currency": expense.original_currency,
                "converted_amount": str(expense.converted_amount) if expense.converted_amount else None,
                "category": expense.category,
                "status": expense.status,
                "vendor_name": expense.vendor_name,
            })

    return {
        "id": group.id,
        "name": group.name,
        "created_by": group.created_by,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "expense_count": len(expenses),
        "total_original_amount": str(total_original),
        "total_converted_amount": str(total_converted),
        "expenses": expenses,
    }
