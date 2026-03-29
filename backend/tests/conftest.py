# backend/tests/conftest.py
"""
Pytest fixtures for TrustFlow tests.
- Async SQLite in-memory database
- Mock Redis client
- Mock MinIO boto3 client
- Async FastAPI test client via httpx
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base, Company, User
from app.db.session import get_db
from app.middleware.auth import hash_password


# ── Async event loop ──────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Test database (SQLite in-memory) ──────────────────────

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create an async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create an async session for testing."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


# ── Mock Redis ────────────────────────────────────────────

class MockRedis:
    """In-memory mock Redis client for testing."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        self._store[key] = value
        return True

    async def setex(self, key: str, ttl: int, value: str):
        self._store[key] = value
        return True

    async def incr(self, key: str):
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    async def expire(self, key: str, ttl: int):
        return True

    async def ttl(self, key: str):
        return 60

    async def delete(self, key: str):
        self._store.pop(key, None)
        return True

    async def ping(self):
        return True

    async def aclose(self):
        pass

    def pipeline(self):
        return MockPipeline(self)


class MockPipeline:
    """Mock Redis pipeline."""

    def __init__(self, redis: MockRedis):
        self._redis = redis
        self._commands = []

    async def incr(self, key: str):
        self._commands.append(("incr", key))
        return self

    async def expire(self, key: str, ttl: int):
        self._commands.append(("expire", key, ttl))
        return self

    async def execute(self):
        results = []
        for cmd in self._commands:
            if cmd[0] == "incr":
                val = int(self._redis._store.get(cmd[1], 0)) + 1
                self._redis._store[cmd[1]] = str(val)
                results.append(val)
            elif cmd[0] == "expire":
                results.append(True)
        return results


@pytest.fixture
def mock_redis():
    """Return a mock Redis instance."""
    return MockRedis()


# ── Mock MinIO (boto3 S3 client) ──────────────────────────

@pytest.fixture
def mock_s3_client():
    """Return a mock boto3 S3 client for MinIO."""
    client = MagicMock()
    client.put_object = MagicMock(return_value={})
    client.get_object = MagicMock(
        return_value={"Body": MagicMock(read=MagicMock(return_value=b"fake-image-bytes"))}
    )
    client.head_bucket = MagicMock(return_value={})
    client.list_buckets = MagicMock(return_value={"Buckets": []})
    return client


# ── Seed data ─────────────────────────────────────────────

@pytest_asyncio.fixture
async def seed_company(test_session: AsyncSession) -> Company:
    """Create a test company."""
    company = Company(
        id=str(uuid.uuid4()),
        name="Test Corp",
        country="India",
        currency="INR",
        auto_approve_threshold=Decimal("2000.00"),
    )
    test_session.add(company)
    await test_session.flush()
    await test_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def seed_employee(test_session: AsyncSession, seed_company: Company) -> User:
    """Create a test employee user."""
    user = User(
        id=str(uuid.uuid4()),
        name="Test Employee",
        email="employee@testcorp.com",
        password_hash=hash_password("TestPass123!"),
        role="employee",
        company_id=seed_company.id,
    )
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seed_manager(test_session: AsyncSession, seed_company: Company) -> User:
    """Create a test manager user."""
    user = User(
        id=str(uuid.uuid4()),
        name="Test Manager",
        email="manager@testcorp.com",
        password_hash=hash_password("TestPass123!"),
        role="manager",
        company_id=seed_company.id,
    )
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seed_employee_with_manager(
    test_session: AsyncSession,
    seed_company: Company,
    seed_manager: User,
) -> User:
    """Create an employee with a manager assigned."""
    user = User(
        id=str(uuid.uuid4()),
        name="Managed Employee",
        email="managed@testcorp.com",
        password_hash=hash_password("TestPass123!"),
        role="employee",
        company_id=seed_company.id,
        manager_id=seed_manager.id,
    )
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)
    return user


# ── FastAPI test client ───────────────────────────────────

@pytest_asyncio.fixture
async def test_client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async test client with DB dependency override.

    Uses the test SQLite database instead of MySQL.
    """
    from app.main import app

    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
