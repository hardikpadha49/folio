# FolioPulse AI — Intelligent Portfolio Analytics Platform

FolioPulse AI is an institutional-grade investment portfolio analysis, optimization, and risk intelligence platform built with **Next.js 16**, **TypeScript**, **Tailwind CSS**, **FastAPI**, **PostgreSQL 16**, and **PyPortfolioOpt**.

---

## 🎯 Architecture & Current Phase Status

| Phase | Milestone | Status |
|---|---|---|
| **Phase 1** | **Foundation & Authentication** | **Complete & Verified ✅** |
| Phase 2 | Portfolio & Online Market Data Integration | Pending Phase 1 Approval |
| Phase 3 | Analytics Engine (Risk, Sharpe, VaR, Health Score) | Planned |
| Phase 4 | Mathematical Optimization & Monte Carlo Simulation | Planned |
| Phase 5 | Honest ML Forecasting vs. Baselines | Planned |
| Phase 6 | Conversational AI Financial Advisor & RAG | Planned |
| Phase 7 | Multilingual Explanations, Sandbox KYC & PDF Reports | Planned |
| Phase 8 | Security Hardening & End-to-End Demo Preparation | Planned |

---

## ⚡ Quick Start (Local Development)

### 1. Prerequisites
- **macOS (Apple Silicon or Intel)** or Linux
- **Node.js** v20+ / v24+ & `npm`
- **Python** 3.13+
- **PostgreSQL** 16 (`brew install postgresql@16`)

### 2. Database Setup
```bash
brew services start postgresql@16
psql -U $(whoami) postgres -c "CREATE USER foliopulse WITH PASSWORD 'foliopulse_dev_pwd';"
psql -U $(whoami) postgres -c "CREATE DATABASE foliopulse_db OWNER foliopulse;"
```

### 3. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Run automated test suite (30 unit & integration tests)
pytest tests/ -v

# Start FastAPI dev server on port 8000
uvicorn app.main:app --port 8000 --reload
```

### 4. Frontend Setup
```bash
cd ../frontend
npm install
npm run build
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🛡️ Security Architecture
- **Row-Level Authorization**: Every database query filters strictly by the authenticated user's UUID.
- **Stateless Tokens**: HS256 JWT access tokens paired with SHA-256 hashed refresh tokens stored in PostgreSQL for immediate revocation upon logout.
- **Cryptographic Security**: Passwords hashed using standard `bcrypt` with work factor 12.
- **Zero Raw SQL**: All operations mediated through SQLAlchemy 2.0 ORM with Alembic schema versioning.
