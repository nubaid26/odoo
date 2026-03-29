# backend/app/config.py
"""
Application configuration using Pydantic BaseSettings.
All environment variables are validated at startup.
External service keys default to empty strings in development mode.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Central configuration object — the single source of truth for all env vars."""

    # ── Application ───────────────────────────────────────
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "dev-secret-key-change-in-production"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # ── JWT ───────────────────────────────────────────────
    JWT_SECRET_KEY: str = "dev-jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Database ──────────────────────────────────────────
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "trustflow"
    MYSQL_USER: str = "trustflow_user"
    MYSQL_PASSWORD: str = "localdev"
    DATABASE_URL: str = "sqlite+aiosqlite:///./trustflow.db"

    # ── Redis ─────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CACHE_REDIS_DB: int = 2

    # ── MinIO (Local S3-compatible storage) ───────────────
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "trustflow-receipts"
    MINIO_USE_SSL: bool = False

    # ── Currency API ──────────────────────────────────────
    EXCHANGE_RATE_API_KEY: str = ""
    EXCHANGE_RATE_BASE_URL: str = "https://api.exchangerate-api.com/v4/latest"

    # ── RestCountries ─────────────────────────────────────
    COUNTRIES_API_URL: str = "https://restcountries.com/v3.1/all?fields=name,currencies"

    # ── GSTIN API ─────────────────────────────────────────
    GSTIN_API_KEY: str = ""
    GSTIN_API_BASE_URL: str = "https://apisetu.gov.in/gstn/v3/taxpayers"
    GSTIN_VERIFY_THRESHOLD: int = 5000

    # ── Google Maps ───────────────────────────────────────
    GOOGLE_MAPS_API_KEY: str = ""
    GOOGLE_MAPS_GEOCODE_URL: str = "https://maps.googleapis.com/maps/api/geocode/json"
    GOOGLE_MAPS_PLACES_URL: str = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    GPS_MISMATCH_THRESHOLD_METERS: int = 500

    # ── SendGrid ──────────────────────────────────────────
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@trustflow.in"
    SENDGRID_FROM_NAME: str = "TrustFlow"

    # ── Tesseract OCR ─────────────────────────────────────
    TESSERACT_CMD: str = "tesseract"

    # ── Celery ────────────────────────────────────────────
    CELERY_WORKER_CONCURRENCY: int = 2
    CELERY_TASK_MAX_RETRIES: int = 3

    # ── Security ──────────────────────────────────────────
    WITNESS_SECRET: str = "dev-witness-secret-change-in-production"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ── Rate Limiting ─────────────────────────────────────
    RATE_LIMIT_LOGIN: str = "5/15minute"
    RATE_LIMIT_SIGNUP: str = "3/hour"
    RATE_LIMIT_EXPENSE_CREATE: str = "20/hour"

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """Ensure CORS_ORIGINS is a non-empty comma-separated string."""
        if not v or not v.strip():
            raise ValueError("CORS_ORIGINS must not be empty")
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a list of strings."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        """Check if we're using SQLite (local development)."""
        return "sqlite" in self.DATABASE_URL.lower()

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# Singleton settings instance — imported throughout the application
settings = Settings()
