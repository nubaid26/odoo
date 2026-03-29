# backend/app/middleware/auth.py
"""
JWT authentication middleware and dependencies.
Bearer token decode, optional Redis user cache (user:{id} TTL 900s), 401 on failure.
Gracefully degrades when Redis is unavailable.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.repositories import user_repo

logger = logging.getLogger("trustflow.middleware.auth")

# Password hashing with bcrypt cost=12
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# Bearer token extractor
security = HTTPBearer(auto_error=False)

USER_CACHE_TTL = 900  # 15 minutes


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with cost=12."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, role: str, company_id: str) -> str:
    """
    Create a JWT access token with 15-minute expiry.

    Payload includes: sub (user_id), role, company_id, exp.
    """
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
        "company_id": company_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """
    Create a JWT refresh token with 30-day expiry.

    Payload includes: sub (user_id), exp, type.
    """
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Raises HTTPException(401) on invalid or expired tokens.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _try_redis_get(cache_key: str) -> Optional[str]:
    """Try to get a value from Redis, return None on any error."""
    try:
        import redis.asyncio as aioredis
        r = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.CACHE_REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=1,
        )
        try:
            val = await r.get(cache_key)
            return val
        finally:
            await r.aclose()
    except Exception:
        return None


async def _try_redis_set(cache_key: str, value: str, ttl: int) -> None:
    """Try to set a value in Redis, silently ignore errors."""
    try:
        import redis.asyncio as aioredis
        r = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.CACHE_REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=1,
        )
        try:
            await r.setex(cache_key, ttl, value)
        finally:
            await r.aclose()
    except Exception:
        pass


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    FastAPI dependency: extract and validate Bearer token, load user.

    Checks Redis cache first (user:{id} TTL 900s) — gracefully skips if Redis is down.
    On cache miss: loads from DB, caches in Redis.

    Returns dict with user_id, role, company_id, email, name.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — expected access token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID",
        )

    # Try Redis cache (non-blocking)
    cache_key = f"user:{user_id}"
    cached = await _try_redis_get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss — load from DB
    user = await user_repo.get_by_id(session, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    user_data = {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "company_id": user.company_id,
        "manager_id": user.manager_id,
    }

    # Try to cache in Redis (non-blocking)
    await _try_redis_set(cache_key, json.dumps(user_data), USER_CACHE_TTL)

    return user_data


def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based access control.

    Usage: Depends(require_role("manager", "admin"))
    """
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user['role']}' not authorized. Required: {', '.join(allowed_roles)}",
            )
        return current_user
    return role_checker
