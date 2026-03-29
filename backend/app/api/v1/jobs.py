# backend/app/api/v1/jobs.py
"""
Job polling endpoint — GET /jobs/{expense_id}.
Returns async job statuses, trust grade, and validation summary.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.repositories import expense_repo, trust_audit_repo

logger = logging.getLogger("trustflow.api.jobs")
router = APIRouter()


@router.get("/{expense_id}")
async def get_job_status(
    expense_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Poll async job statuses for an expense.

    Returns:
    - jobs: array of {job_type, status, result_json} for all async_jobs
    - expense_status: current expense status
    - trust_grade: trust grade if computed (null otherwise)
    - validation_summary: {passed_count, failed_count} from bill_validation_logs
    """
    # Verify expense access
    expense = await expense_repo.get_by_id(
        session, expense_id, current_user["company_id"]
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Get async jobs
    jobs = await expense_repo.get_async_jobs(session, expense_id)

    # Parse result_json for each job
    jobs_data = []
    for job in jobs:
        result = None
        if job.result_json:
            try:
                result = json.loads(job.result_json)
            except (json.JSONDecodeError, TypeError):
                result = job.result_json

        jobs_data.append({
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "result": result,
        })

    # Get trust audit
    trust_audit = await trust_audit_repo.get_latest_for_expense(session, expense_id)

    # Get validation summary
    validation_logs = await expense_repo.get_validation_logs(session, expense_id)
    passed_count = sum(1 for v in validation_logs if v.passed)
    failed_count = sum(1 for v in validation_logs if not v.passed)

    return {
        "expense_id": expense_id,
        "expense_status": expense.status,
        "trust_grade": trust_audit.grade if trust_audit else None,
        "trust_score": str(trust_audit.score) if trust_audit else None,
        "validation_summary": {
            "passed_count": passed_count,
            "failed_count": failed_count,
            "total": len(validation_logs),
        },
        "jobs": jobs_data,
    }
