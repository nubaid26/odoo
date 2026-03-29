# backend/app/main.py
"""
FastAPI application entry point.
Mounts all routers, registers middleware, startup events, and health check.
"""

from __future__ import annotations

import json
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text as sa_text

from app.config import settings
from app.api.v1 import api_router
from app.middleware.logging import StructuredLoggingMiddleware

# ── Configure logging ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)

# ── Create FastAPI app ────────────────────────────────────
app = FastAPI(
    title="TrustFlow API",
    description="Expense management and trust-scoring platform for Indian enterprises",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ─────────────────────────────────────────────
# Order matters: outermost middleware runs first

# Structured JSON logging
app.add_middleware(StructuredLoggingMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# ── Mount API routes ──────────────────────────────────────
app.include_router(api_router)


# ── Startup events ────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    """
    Application startup:
    1. Create database tables (if using SQLite for local dev)
    2. Ensure MinIO bucket exists
    3. Fetch and cache country-currency mapping
    """
    logger = logging.getLogger("trustflow.startup")
    logger.info("Starting TrustFlow API (env=%s)", settings.APP_ENV)

    # Create database tables for SQLite (local development)
    if settings.is_sqlite:
        from app.db.session import engine
        from app.db.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite database tables created/verified")

    # Ensure MinIO bucket exists
    try:
        from app.external.minio_client import ensure_bucket_exists
        ensure_bucket_exists()
        logger.info("MinIO bucket '%s' verified", settings.MINIO_BUCKET)
    except Exception as exc:
        logger.warning("MinIO bucket check failed: %s (storage features will be limited)", exc)

    # Fetch and cache country-currency mapping from RestCountries
    try:
        from app.external.restcountries import fetch_and_cache_countries
        countries = await fetch_and_cache_countries()
        logger.info("Loaded %d country-currency mappings", len(countries))
    except Exception as exc:
        logger.warning("Country-currency fetch failed: %s (fallback will be used)", exc)

    logger.info("TrustFlow API started on %s:%d", settings.APP_HOST, settings.APP_PORT)
    logger.info("API docs available at http://localhost:%d/docs", settings.APP_PORT)


# ── Health check ──────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Dependency health check.

    Returns status of: db, cache (Redis), storage (MinIO), worker (Celery).
    """
    health = {
        "status": "healthy",
        "dependencies": {},
    }

    # Check Database
    try:
        from app.db.session import engine
        async with engine.connect() as conn:
            await conn.execute(sa_text("SELECT 1"))
        health["dependencies"]["db"] = {"status": "healthy"}
    except Exception as exc:
        health["dependencies"]["db"] = {"status": "unhealthy", "error": str(exc)}
        health["status"] = "degraded"

    # Check Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            socket_connect_timeout=1,
        )
        await r.ping()
        await r.aclose()
        health["dependencies"]["cache"] = {"status": "healthy"}
    except Exception as exc:
        health["dependencies"]["cache"] = {"status": "unavailable", "note": "Rate limiting and caching disabled"}
        if health["status"] == "healthy":
            health["status"] = "degraded"

    # Check MinIO
    try:
        from app.external.minio_client import check_health
        minio_ok = check_health()
        health["dependencies"]["storage"] = {
            "status": "healthy" if minio_ok else "unavailable"
        }
        if not minio_ok and health["status"] == "healthy":
            health["status"] = "degraded"
    except Exception as exc:
        health["dependencies"]["storage"] = {"status": "unavailable", "note": "File upload disabled"}
        if health["status"] == "healthy":
            health["status"] = "degraded"

    status_code = 200 if health["status"] in ("healthy", "degraded") else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(content=health, status_code=status_code)
