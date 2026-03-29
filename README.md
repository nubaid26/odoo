# TrustFlow — Expense Management & Trust Scoring Platform

Production-grade expense management and trust-scoring platform for Indian enterprises. Employees submit expenses with receipt uploads → automated validation (OCR, GST, GPS) → trust-weighted approval routing → email notifications.

## Architecture

| Component | Technology |
|-----------|-----------|
| **Frontend** | React 18 SPA (Stitch-generated) |
| **Backend** | FastAPI (async) + SQLAlchemy 2.0 |
| **Workers** | Celery 5 (4 queues: ocr, validation, trust, notifications) |
| **Database** | MySQL 8 (13 tables, UUID PKs) |
| **Cache/Broker** | Redis 7 (DB0: broker, DB1: results, DB2: cache) |
| **Storage** | MinIO (S3-compatible, via boto3) |
| **OCR** | Tesseract 5 (local, via pytesseract) |
| **Deployment** | Docker Compose (6 services) |

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your API keys

# 2. Start all services
docker-compose up --build -d

# 3. Run migrations
docker-compose exec api alembic upgrade head

# 4. Check health
curl http://localhost:8000/health

# 5. Open API docs
open http://localhost:8000/docs
```

## Project Structure

```
trustflow/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── countries_fallback.json
│   ├── templates/                    # Jinja2 email templates
│   │   ├── approval_request.html
│   │   ├── expense_approved.html
│   │   └── expense_rejected.html
│   ├── migrations/
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── app/
│   │   ├── main.py                   # FastAPI entry point
│   │   ├── config.py                 # Pydantic BaseSettings
│   │   ├── api/v1/                   # REST endpoints
│   │   │   ├── auth.py               # signup, login, refresh, logout
│   │   │   ├── expenses.py           # submit, list, detail
│   │   │   ├── approvals.py          # approve, reject
│   │   │   ├── witnesses.py          # add, confirm via HMAC
│   │   │   ├── groups.py             # expense groups
│   │   │   ├── jobs.py               # async job polling
│   │   │   └── currencies.py         # country-currency dropdown
│   │   ├── db/
│   │   │   ├── models.py             # 13 ORM models
│   │   │   └── session.py            # async engine + get_db
│   │   ├── domain/
│   │   │   ├── enums.py              # ExpenseStatus, TrustGrade, etc.
│   │   │   ├── models.py             # Pydantic domain models
│   │   │   └── states.py             # approval state machine
│   │   ├── external/                 # 6 API client integrations
│   │   │   ├── exchange_rate.py      # ExchangeRate API + Redis cache
│   │   │   ├── restcountries.py      # RestCountries + fallback JSON
│   │   │   ├── gstin.py              # GSTIN verification API
│   │   │   ├── google_maps.py        # Geocoding + Nearby Search
│   │   │   ├── tesseract.py          # Local Tesseract 5 OCR
│   │   │   ├── minio_client.py       # MinIO via boto3 (never minio pkg)
│   │   │   └── sendgrid.py           # SendGrid email delivery
│   │   ├── middleware/
│   │   │   ├── auth.py               # JWT + bcrypt + Redis user cache
│   │   │   ├── rate_limit.py         # Redis sliding-window
│   │   │   └── logging.py            # Structured JSON logging
│   │   ├── repositories/             # SQLAlchemy queries only
│   │   │   ├── expense_repo.py
│   │   │   ├── user_repo.py
│   │   │   ├── approval_repo.py
│   │   │   └── trust_audit_repo.py
│   │   ├── services/                 # Business logic
│   │   │   ├── expense_service.py    # Create flow orchestration
│   │   │   ├── approval_service.py   # Routing + approve/reject
│   │   │   ├── trust_service.py      # Weighted score formula v1.0
│   │   │   ├── validation_service.py # 4 sequential checks
│   │   │   ├── currency_service.py   # Conversion wrapper
│   │   │   ├── maps_service.py       # Haversine + vendor matching
│   │   │   ├── gstin_service.py      # GSTIN evaluation
│   │   │   ├── witness_service.py    # HMAC token generation
│   │   │   └── notification_service.py
│   │   └── workers/                  # Celery tasks
│   │       ├── celery_app.py         # 4 queues configuration
│   │       ├── ocr_worker.py         # Queue: ocr
│   │       ├── validation_worker.py  # Queue: validation
│   │       ├── trust_worker.py       # Queue: trust
│   │       └── notification_worker.py # Queue: notifications
│   └── tests/
│       ├── conftest.py               # Fixtures: SQLite, mock Redis/S3
│       ├── test_trust_service.py     # 15 parametrized tests
│       ├── test_validation_service.py
│       ├── test_maps_service.py      # Haversine + vendor verification
│       ├── test_state_machine.py     # Transition validation
│       └── test_ocr.py              # OCR parsing unit tests
└── frontend/                         # React 18 SPA
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/signup` | — | Register new user |
| POST | `/api/v1/auth/login` | — | Login (rate limited: 5/15min) |
| POST | `/api/v1/auth/refresh` | Cookie | Rotate refresh token |
| POST | `/api/v1/auth/logout` | Bearer | Revoke refresh token |
| POST | `/api/v1/expenses` | Bearer | Submit expense (202 Accepted) |
| GET | `/api/v1/expenses` | Bearer | List expenses (role-scoped) |
| GET | `/api/v1/expenses/{id}` | Bearer | Expense detail + audit trail |
| POST | `/api/v1/approvals/{id}/approve` | Bearer (manager+) | Approve step |
| POST | `/api/v1/approvals/{id}/reject` | Bearer (manager+) | Reject expense |
| POST | `/api/v1/expenses/{id}/witnesses` | Bearer | Add witness |
| POST | `/api/v1/witnesses/confirm/{token}` | — | Confirm via HMAC |
| POST | `/api/v1/groups` | Bearer | Create expense group |
| GET | `/api/v1/groups/{id}` | Bearer | Group detail + aggregates |
| GET | `/api/v1/jobs/{expense_id}` | Bearer | Poll async job status |
| GET | `/api/v1/currencies` | Bearer | Country-currency mapping |
| GET | `/health` | — | Dependency health check |

## Trust Scoring Formula (v1.0)

```
trust_score = receipt_score * 0.40 + gst_score * 0.20 + vendor_score * 0.20
            + behavior_score * 0.10 + proof_score * 0.10

Grades:  HIGH >= 80  |  MEDIUM 60-79  |  LOW 40-59  |  BLOCKED < 40
```

## Approval Routing

| Trust Grade | Amount Condition | Route |
|-------------|-----------------|-------|
| HIGH | < auto_approve_threshold | Auto-approved |
| MEDIUM | any | Single manager approval |
| LOW | > ₹10,000 | Manager + senior manager |
| BLOCKED | any | Flagged for admin review |

## Async Processing Pipeline

```
Submit Expense → [OCR Queue] → [Validation Queue] → [Trust Queue] → [Approval Routing]
                                                                   → [Notification Queue]
```

Client polls `GET /api/v1/jobs/{expense_id}` for status updates.

## Environment Variables

Copy `.env.example` to `.env` and configure all required values. Key variables:

- `JWT_SECRET_KEY` — HMAC signing key for JWT tokens
- `EXCHANGE_RATE_API_KEY` — ExchangeRate API key
- `GSTIN_API_KEY` — GSTIN verification API key
- `GOOGLE_MAPS_API_KEY` — Google Maps Platform key
- `SENDGRID_API_KEY` — SendGrid email API key
- `WITNESS_SECRET` — HMAC key for witness tokens

## Running Tests

```bash
# Inside the backend container
docker-compose exec api pytest tests/ -v --tb=short

# Or locally with venv
cd backend
pip install -r requirements.txt
pip install pytest pytest-asyncio aiosqlite httpx
pytest tests/ -v
```

## License

MIT
