"""
Build four role-distribution zip archives from the TrustFlow tree.
Run from repo root: python scripts/build_role_zips.py
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "role-zips"
PREFIX = "trustflow"  # path inside zip


def rel(path: str) -> Path:
    return ROOT / path


def write_zip(name: str, paths: list[str], extras: list[tuple[str, str]] | None = None) -> Path:
    """
    paths: repo-relative POSIX paths under ROOT.
    extras: (arcname_under_prefix, file_content_str)
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zpath = OUT_DIR / f"{name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            src = rel(p)
            if not src.exists():
                raise FileNotFoundError(src)
            arc = f"{PREFIX}/{p}"
            zf.write(src, arc)
        if extras:
            for arc_suffix, content in extras:
                zf.writestr(f"{PREFIX}/{arc_suffix}", content)
    return zpath


BACKEND_CORE_PATHS = [
    "backend/app/__init__.py",
    "backend/app/config.py",
    "backend/app/main.py",
    "backend/app/api/__init__.py",
    "backend/app/api/v1/__init__.py",
    "backend/app/api/v1/auth.py",
    "backend/app/api/v1/expenses.py",
    "backend/app/api/v1/approvals.py",
    "backend/app/api/v1/groups.py",
    "backend/app/api/v1/witnesses.py",
    "backend/app/api/v1/currencies.py",
    "backend/app/api/v1/jobs.py",
    "backend/app/middleware/__init__.py",
    "backend/app/middleware/auth.py",
    "backend/app/middleware/rate_limit.py",
    "backend/app/middleware/logging.py",
    "backend/app/db/__init__.py",
    "backend/app/db/models.py",
    "backend/app/db/session.py",
    "backend/app/domain/__init__.py",
    "backend/app/domain/enums.py",
    "backend/app/domain/models.py",
    "backend/app/domain/states.py",
    "backend/app/repositories/__init__.py",
    "backend/app/repositories/expense_repo.py",
    "backend/app/repositories/user_repo.py",
    "backend/app/repositories/approval_repo.py",
    "backend/app/repositories/trust_audit_repo.py",
    "backend/app/services/__init__.py",
    "backend/app/services/expense_service.py",
    "backend/app/services/approval_service.py",
    "backend/app/services/witness_service.py",
    "backend/migrations/env.py",
    "backend/migrations/script.py.mako",
    "backend/migrations/versions/0001_initial_schema.py",
    "backend/alembic.ini",
    "backend/requirements.txt",
]

AI_ASYNC_PATHS = [
    "backend/app/__init__.py",
    "backend/app/config.py",
    "backend/app/workers/__init__.py",
    "backend/app/workers/celery_app.py",
    "backend/app/workers/ocr_worker.py",
    "backend/app/workers/validation_worker.py",
    "backend/app/workers/trust_worker.py",
    "backend/app/workers/notification_worker.py",
    "backend/app/services/__init__.py",
    "backend/app/services/validation_service.py",
    "backend/app/services/trust_service.py",
    "backend/app/services/currency_service.py",
    "backend/app/services/gstin_service.py",
    "backend/app/services/maps_service.py",
    "backend/app/services/notification_service.py",
    "backend/app/external/__init__.py",
    "backend/app/external/tesseract.py",
    "backend/app/external/minio_client.py",
    "backend/app/external/gstin.py",
    "backend/app/external/google_maps.py",
    "backend/app/external/exchange_rate.py",
    "backend/app/external/sendgrid.py",
    "backend/app/db/__init__.py",
    "backend/app/db/models.py",
    "backend/app/db/session.py",
    "backend/app/domain/__init__.py",
    "backend/app/domain/enums.py",
    "backend/app/domain/models.py",
    "backend/app/domain/states.py",
    "backend/app/repositories/__init__.py",
    "backend/app/repositories/expense_repo.py",
    "backend/app/repositories/trust_audit_repo.py",
    "backend/app/repositories/user_repo.py",
    "backend/app/repositories/approval_repo.py",
    "backend/app/services/approval_service.py",
    "backend/requirements.txt",
    "backend/tests/__init__.py",
    "backend/tests/conftest.py",
    "backend/tests/test_ocr.py",
    "backend/tests/test_validation_service.py",
    "backend/tests/test_trust_service.py",
    "backend/tests/test_maps_service.py",
]

DEVOPS_PATHS = [
    "docker-compose.yml",
    ".env.example",
    ".gitignore",
    "backend/Dockerfile",
    "backend/requirements.txt",
    "backend/alembic.ini",
    "backend/countries_fallback.json",
    "backend/app/__init__.py",
    "backend/app/config.py",
    "backend/app/main.py",
    "backend/app/middleware/__init__.py",
    "backend/app/middleware/logging.py",
    "backend/app/middleware/rate_limit.py",
    "backend/app/middleware/auth.py",
    "backend/app/external/__init__.py",
    "backend/app/external/exchange_rate.py",
    "backend/app/external/gstin.py",
    "backend/app/external/google_maps.py",
    "backend/app/external/minio_client.py",
    "backend/app/external/restcountries.py",
    "backend/app/external/sendgrid.py",
    "backend/app/external/tesseract.py",
    "backend/templates/approval_request.html",
    "backend/templates/expense_approved.html",
    "backend/templates/expense_rejected.html",
    "backend/tests/__init__.py",
    "backend/tests/conftest.py",
    "backend/tests/test_state_machine.py",
    "backend/tests/test_ocr.py",
    "backend/tests/test_validation_service.py",
    "backend/tests/test_trust_service.py",
    "backend/tests/test_maps_service.py",
    "backend/migrations/env.py",
    "backend/migrations/script.py.mako",
    "backend/migrations/versions/0001_initial_schema.py",
    "backend/app/db/__init__.py",
    "backend/app/db/models.py",
    "backend/app/db/session.py",
]

ROLE_NOTE_BACK = """Role: Backend Core Engineer (Foundation)
Includes: JWT/auth routes, RBAC middleware, rate limiting, SQLAlchemy models & session,
Alembic migrations, repositories (expense, user, approval, trust_audit),
sync API routes under /api/v1 for auth, expenses, approvals, groups, witnesses,
jobs, currencies; expense/approval/witness services; FastAPI entry (main.py).
"""

ROLE_NOTE_AI = """Role: AI / Async Systems Engineer
Includes: Celery app and workers (ocr, validation, trust, notifications),
intelligence services (validation, trust, currency, GSTIN, maps, notifications),
Tesseract OCR integration and external clients required by those services,
plus DB/domain/repo slices and approval_service needed by trust_worker.
Tests: OCR, validation, trust, maps.
"""

ROLE_NOTE_DEVOPS = """Role: DevOps + Integration Engineer
Includes: docker-compose, backend Dockerfile, env template, structured logging &
rate-limit middleware, all external integration clients, email templates,
pytest suite, Alembic + DB models for integration context, countries fallback JSON.
"""

ROLE_NOTE_FE = """Role: Frontend Engineer
No React/SPA source tree was found under this workspace (trustflow/).
Add your Login, Dashboard, New Expense, Expense Detail, Approvals, Admin pages,
Zustand stores, Axios client, TrustBadge, ValidationResults, ApprovalTimeline,
JobPoller here and re-run scripts/build_role_zips.py after placing frontend/
next to backend/ (update FRONTEND_PATHS in the script).
"""


def main() -> None:
    built = []
    built.append(
        write_zip(
            "01-backend-core-engineer",
            BACKEND_CORE_PATHS,
            [("ROLE_MANIFEST.txt", ROLE_NOTE_BACK)],
        )
    )
    built.append(
        write_zip(
            "02-ai-async-systems-engineer",
            AI_ASYNC_PATHS,
            [("ROLE_MANIFEST.txt", ROLE_NOTE_AI)],
        )
    )
    built.append(
        write_zip(
            "03-devops-integration-engineer",
            DEVOPS_PATHS,
            [("ROLE_MANIFEST.txt", ROLE_NOTE_DEVOPS)],
        )
    )
    built.append(
        write_zip(
            "04-frontend-engineer",
            [],
            [("ROLE_MANIFEST.txt", ROLE_NOTE_FE)],
        )
    )
    print("Wrote:")
    for p in built:
        print(" ", p)


if __name__ == "__main__":
    main()
