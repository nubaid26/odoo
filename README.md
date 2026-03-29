# 🚀 TrustFlow — Intelligent Expense Management & Trust Scoring Platform

Production-grade, AI-assisted expense management system with automated validation, trust-based approvals, and fraud prevention.

---

## 📌 Overview

TrustFlow is a smart expense management platform designed for modern Indian enterprises.

It eliminates manual verification by combining:
- OCR-based receipt extraction  
- GST & vendor validation  
- GPS-based verification  
- Trust scoring engine  
- Automated approval workflows  

Result: Faster approvals, reduced fraud, and minimal manual intervention.

---

## 🎯 Problem Statement

Traditional expense systems suffer from:
- Manual verification delays  
- Fake or duplicate bills  
- No intelligent approval logic  
- Poor auditability  
- Lack of trust-based decision-making  

---

## 💡 Solution

TrustFlow introduces:
- AI-driven validation pipeline  
- Trust-based dynamic approval routing  
- Automated fraud detection signals  
- Real-time async processing  
- Enterprise-grade audit trails  

---

## 👥 Target Users

- Employees submitting expenses  
- Managers approving expenses  
- Finance/Admin teams auditing  
- Enterprises needing fraud-resistant systems  

---

## ⚙️ Core Features

### 🧾 Expense Submission
- Upload receipt image  
- Optional UPI/payment proof upload  
- Add metadata (amount, vendor, category, location)  
- Async (non-blocking) submission  

---

### 🔍 Automated Validation Engine

Sequential validation pipeline:

1. OCR Extraction  
   - Extracts vendor, amount, date  

2. GST Verification  
   - Validates GSTIN authenticity  

3. Vendor Verification  
   - Google Maps validation  

4. Location Validation  
   - Matches user vs vendor location  

5. Duplicate Detection  
   - Prevents reused receipts  

---

### 🧠 Trust Scoring System

```
trust_score = receipt_score * 0.40 
            + gst_score * 0.20 
            + vendor_score * 0.20
            + behavior_score * 0.10 
            + proof_score * 0.10
```

Grades:
- HIGH ≥ 80  
- MEDIUM 60–79  
- LOW 40–59  
- BLOCKED < 40  

---

### 🔄 Smart Approval Routing

| Trust Grade | Condition | Action |
|------------|----------|--------|
| HIGH | Below threshold | Auto-approved |
| MEDIUM | Any | Manager approval |
| LOW | High amount | Multi-level approval |
| BLOCKED | Any | Admin review |

---

### 👥 Witness System (Unique Feature)
- Add witnesses if no bill available  
- Secure HMAC confirmation links  
- Improves trust score  

---

### 📊 Expense Groups
- Group multiple expenses  
- Aggregated tracking & analytics  

---

### 🌍 Currency Support
- Country → currency mapping  
- Real-time conversion with caching  

---

### 📬 Notifications
- Email alerts:
  - Approval requests  
  - Approval/rejection updates  
  - Witness confirmations  

---

### 🔐 Authentication & Security
- JWT authentication  
- Refresh token rotation  
- Redis-based rate limiting  
- Secure HMAC tokens  

---

### 📈 Audit System
- Full audit trail per expense  
- State machine tracking  
- Trust score breakdown  

---

## 🧠 System Architecture

```
                    ┌───────────────┐
                    │   Frontend    │ (React SPA)
                    └──────┬────────┘
                           │ API Calls
                           ▼
                    ┌───────────────┐
                    │   FastAPI     │ (Backend)
                    └──────┬────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   MySQL DB           Redis Cache        MinIO Storage
 (13 Tables)      (Cache + Broker)     (Receipts / Files)

                           │
                           ▼
                    ┌───────────────┐
                    │   Celery      │ (Async Workers)
                    └──────┬────────┘
                           │
     ┌──────────────┬──────────────┬──────────────┬──────────────┐
     ▼              ▼              ▼              ▼
   OCR           Validation      Trust        Notifications
 Worker           Worker         Worker          Worker

                           │
                           ▼
              External API Integrations
   (GSTIN, Google Maps, ExchangeRate, SendGrid)
```

---

## 🔄 Processing Flow

```
User submits expense
        ↓
OCR Extraction
        ↓
Validation Checks
        ↓
Trust Score Calculation
        ↓
Approval Routing
        ↓
Notifications
```

---

## 🧱 Tech Stack

| Layer | Technology |
|------|-----------|
| Frontend | React 18 |
| Backend | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Database | MySQL 8 |
| Cache/Broker | Redis 7 |
| Workers | Celery |
| Storage | MinIO |
| OCR | Tesseract 5 |
| Deployment | Docker Compose |

---

## 🔌 External APIs

- ExchangeRate API → currency conversion  
- GSTIN API → GST validation  
- Google Maps API → vendor verification  
- RestCountries API → country data  
- SendGrid → email notifications  

---

## 📁 Project Structure

```
trustflow/
├── backend/
│   ├── api/              # REST endpoints
│   ├── services/         # Business logic
│   ├── workers/          # Celery async jobs
│   ├── repositories/     # DB layer
│   ├── external/         # API integrations
│   ├── middleware/       # auth, logging, rate limit
│   ├── domain/           # models + state machine
│   └── tests/            # unit + integration tests
├── frontend/             # React SPA
├── docker-compose.yml
└── .env.example
```

---

## 🔗 API Endpoints

- Auth → signup, login, logout  
- Expenses → submit, list, detail  
- Approvals → approve/reject  
- Witness → add, confirm  
- Groups → manage grouped expenses  
- Jobs → async status polling  
- Currencies → mapping  

---

## ⚡ Async Job Tracking

```
GET /api/v1/jobs/{expense_id}
```

---

## 🚀 Quick Start

```bash
cp .env.example .env
docker-compose up --build -d
docker-compose exec api alembic upgrade head
curl http://localhost:8000/health
```

---

## 🧪 Testing

```bash
pytest tests/ -v
```

Includes:
- Trust scoring tests  
- Validation tests  
- OCR parsing tests  
- State machine tests  

---

## 🔐 Environment Variables

- JWT_SECRET_KEY  
- GSTIN_API_KEY  
- GOOGLE_MAPS_API_KEY  
- SENDGRID_API_KEY  
- EXCHANGE_RATE_API_KEY  
- WITNESS_SECRET  

---

## 🏆 Key Highlights

- Real-world enterprise problem  
- Fully async scalable architecture  
- Unique trust-based approvals  
- Fraud detection built-in  
- Production-grade backend design  
- Multiple API integrations  
- Supports no-bill cases (UPI + witnesses)  

---

## 📜 License

MIT
