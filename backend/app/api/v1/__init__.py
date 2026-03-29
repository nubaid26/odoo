# backend/app/api/v1/__init__.py
"""API v1 route registration."""

from fastapi import APIRouter

from app.api.v1 import auth, expenses, approvals, witnesses, groups, jobs, currencies

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])
api_router.include_router(witnesses.router, tags=["Witnesses"])
api_router.include_router(groups.router, prefix="/groups", tags=["Groups"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(currencies.router, prefix="/currencies", tags=["Currencies"])
