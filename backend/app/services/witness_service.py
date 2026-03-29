# backend/app/services/witness_service.py
"""
Witness service — HMAC token generation and confirmation.
Signature: HMAC-SHA256(expense_id + witness_id + amount + currency + timestamp, WITNESS_SECRET)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ExpenseWitness, Expense, User

logger = logging.getLogger("trustflow.services.witness")


def generate_witness_token(
    expense_id: str,
    witness_id: str,
    amount: Decimal,
    currency: str,
    timestamp: str,
) -> str:
    """
    Generate an HMAC-SHA256 witness confirmation token.

    Token = HMAC-SHA256(expense_id + witness_id + amount + currency + timestamp, WITNESS_SECRET)

    Args:
        expense_id: Expense UUID.
        witness_id: Witness user UUID.
        amount: Expense amount.
        currency: Currency code.
        timestamp: ISO timestamp string.

    Returns:
        Hex-encoded HMAC token.
    """
    message = f"{expense_id}{witness_id}{amount}{currency}{timestamp}"
    token = hmac.new(
        settings.WITNESS_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return token


async def add_witness(
    session: AsyncSession,
    expense_id: str,
    witness_user_id: str,
    company_id: str,
) -> dict:
    """
    Add a witness to an expense.

    Validates that the witness is in the same company.
    Generates a confirmation token.

    Args:
        session: Database session.
        expense_id: Expense UUID.
        witness_user_id: Witness user UUID.
        company_id: Company UUID for validation.

    Returns:
        Dict with witness_id and confirmation token.
    """
    # Validate witness is in same company
    stmt = select(User).where(
        and_(User.id == witness_user_id, User.company_id == company_id)
    )
    result = await session.execute(stmt)
    witness_user = result.scalar_one_or_none()
    if not witness_user:
        raise ValueError("Witness must be an employee in the same company")

    # Validate expense exists
    stmt = select(Expense).where(
        and_(Expense.id == expense_id, Expense.company_id == company_id)
    )
    result = await session.execute(stmt)
    expense = result.scalar_one_or_none()
    if not expense:
        raise ValueError(f"Expense {expense_id} not found")

    # Generate token
    timestamp = datetime.utcnow().isoformat()
    token = generate_witness_token(
        expense_id, witness_user_id,
        expense.original_amount, expense.original_currency,
        timestamp,
    )

    # Create witness record
    witness = ExpenseWitness(
        id=str(uuid.uuid4()),
        expense_id=expense_id,
        witness_user_id=witness_user_id,
        status="pending",
        signature_hash=token,
    )
    session.add(witness)
    await session.flush()
    await session.refresh(witness)

    logger.info(
        "Added witness %s for expense %s",
        witness_user_id[:8], expense_id,
    )

    return {
        "witness_id": witness.id,
        "token": token,
        "status": "pending",
    }


async def confirm_witness(
    session: AsyncSession,
    token: str,
) -> dict:
    """
    Confirm a witness via their HMAC token.

    Validates the token against stored signature_hash.

    Args:
        session: Database session.
        token: The HMAC token to verify.

    Returns:
        Dict with confirmation result.
    """
    # Find the witness record by signature hash
    stmt = select(ExpenseWitness).where(
        and_(
            ExpenseWitness.signature_hash == token,
            ExpenseWitness.status == "pending",
        )
    )
    result = await session.execute(stmt)
    witness = result.scalar_one_or_none()

    if not witness:
        raise ValueError("Invalid or expired witness confirmation token")

    # Confirm the witness
    witness.status = "confirmed"
    witness.confirmed_at = datetime.utcnow()
    await session.flush()

    logger.info("Witness %s confirmed for expense %s", witness.id, witness.expense_id)

    return {
        "witness_id": witness.id,
        "expense_id": witness.expense_id,
        "status": "confirmed",
    }
