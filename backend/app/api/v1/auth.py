# backend/app/api/v1/auth.py
"""
Authentication routes — signup, login, refresh, logout.
Thin handlers: validate input, call services, return response.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, Company, RefreshToken
from app.db.session import get_db
from app.middleware.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.middleware.rate_limit import rate_limit_login, rate_limit_signup
from app.repositories import user_repo

logger = logging.getLogger("trustflow.api.auth")
router = APIRouter()


# ── Request/Response schemas ──────────────────────────────

class SignupRequest(BaseModel):
    """User registration request."""
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    company_name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(default="employee")


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    """Refresh token request — token comes from httpOnly cookie."""
    pass


# ── Routes ────────────────────────────────────────────────

@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def signup(
    request: Request,
    body: SignupRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.

    Rate limited: 3 per hour per IP.
    Creates a company if one doesn't exist with the given name.
    """
    await rate_limit_signup(request)

    # Check if email already exists
    existing = await user_repo.get_by_email(session, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Find or create company
    stmt = select(Company).where(Company.name == body.company_name)
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        company = Company(
            id=str(uuid.uuid4()),
            name=body.company_name,
        )
        session.add(company)
        await session.flush()

    # Create user
    user = User(
        id=str(uuid.uuid4()),
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        company_id=company.id,
    )
    user = await user_repo.create(session, user)

    # Generate tokens
    access_token = create_access_token(user.id, user.role, user.company_id)
    refresh_token = create_refresh_token(user.id)

    # Store refresh token hash
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    rt = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(rt)

    await session.commit()

    response = TokenResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "company_id": user.company_id,
        },
    )

    # Set refresh token in httpOnly cookie
    api_response = Response(
        content=response.model_dump_json(),
        media_type="application/json",
        status_code=201,
    )
    api_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.APP_ENV != "development",
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return api_response


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Authenticate and receive JWT tokens.

    Rate limited: 5 per 15 minutes per IP+email.
    Returns access token in body, refresh token in httpOnly cookie.
    """
    await rate_limit_login(request, body.email)

    user = await user_repo.get_by_email(session, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Generate tokens
    access_token = create_access_token(user.id, user.role, user.company_id)
    refresh_token = create_refresh_token(user.id)

    # Store refresh token hash
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    rt = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(rt)
    await session.commit()

    response_data = TokenResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "company_id": user.company_id,
        },
    )

    api_response = Response(
        content=response_data.model_dump_json(),
        media_type="application/json",
        status_code=200,
    )
    api_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.APP_ENV != "development",
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return api_response


@router.post("/refresh")
async def refresh(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """
    Rotate refresh token — revoke old, issue new.

    Refresh token read from httpOnly cookie.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token cookie found",
        )

    # Decode the refresh token
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    # Find the stored token
    stmt = select(RefreshToken).where(
        and_(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at == None,
        )
    )
    result = await session.execute(stmt)
    stored_token = result.scalar_one_or_none()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found or already revoked",
        )

    if stored_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Revoke old token
    stored_token.revoked_at = datetime.utcnow()

    # Load user
    user = await user_repo.get_by_id(session, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Issue new tokens
    new_access_token = create_access_token(user.id, user.role, user.company_id)
    new_refresh_token = create_refresh_token(user.id)

    new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
    new_rt = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=new_token_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(new_rt)
    await session.commit()

    response_data = {
        "access_token": new_access_token,
        "token_type": "bearer",
    }

    api_response = Response(
        content=json.dumps(response_data),
        media_type="application/json",
        status_code=200,
    )
    api_response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=settings.APP_ENV != "development",
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return api_response


@router.post("/logout")
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Revoke the current refresh token."""
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        stmt = select(RefreshToken).where(
            and_(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at == None,
            )
        )
        result = await session.execute(stmt)
        stored_token = result.scalar_one_or_none()
        if stored_token:
            stored_token.revoked_at = datetime.utcnow()
            await session.commit()

    api_response = Response(
        content='{"message": "Logged out successfully"}',
        media_type="application/json",
        status_code=200,
    )
    api_response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return api_response


# Need to import json for refresh endpoint
import json
