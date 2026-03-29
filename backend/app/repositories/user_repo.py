# backend/app/repositories/user_repo.py
"""
User repository — SQLAlchemy queries only, no business logic.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

logger = logging.getLogger("trustflow.repositories.user")


async def create(session: AsyncSession, user: User) -> User:
    """Insert a new user row."""
    session.add(user)
    await session.flush()
    await session.refresh(user)
    logger.info("Created user %s (%s)", user.id[:8], user.email)
    return user


async def get_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Look up a user by email address."""
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_id(
    session: AsyncSession,
    user_id: str,
    company_id: Optional[str] = None,
) -> Optional[User]:
    """
    Get a user by ID, optionally scoped by company_id.

    Args:
        session: Database session.
        user_id: User UUID.
        company_id: Optional company scope for cross-company protection.
    """
    conditions = [User.id == user_id]
    if company_id:
        conditions.append(User.company_id == company_id)

    stmt = select(User).where(and_(*conditions))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_direct_reports(
    session: AsyncSession,
    manager_id: str,
    company_id: str,
) -> List[User]:
    """
    Get all direct reports for a manager, scoped by company_id.

    Args:
        session: Database session.
        manager_id: Manager's user UUID.
        company_id: Company scope for security.
    """
    stmt = select(User).where(
        and_(
            User.manager_id == manager_id,
            User.company_id == company_id,
            User.is_active == True,
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_all_by_company(
    session: AsyncSession,
    company_id: str,
    limit: int = 100,
    offset: int = 0,
) -> List[User]:
    """Get all users in a company (admin use)."""
    stmt = (
        select(User)
        .where(User.company_id == company_id)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
