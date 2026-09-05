<p align="center">
  <h1 align="center">RecoverX — AI Revenue Recovery Agent</h1>
  <p align="center">
    Autonomous AI agent that detects, diagnoses, and recovers failed payments, abandoned checkouts, lapsed subscriptions, and overdue invoices — powered by LLM reasoning and Razorpay APIs.
  </p>
  <p align="center">
    <strong>🏗️ Razorpay Buildathon · Track 03</strong>
  </p>
</p>

---

## ✨ What It Does

RecoverX is an **end-to-end AI revenue recovery system** that acts as an autonomous agent. It ingests payment failure events (via Razorpay Webhooks), runs each case through a multi-stage recovery pipeline, and takes the optimal action — all with built-in guardrails and a full audit trail.

### Recovery Pipeline

```
Detect → Diagnose (LLM) → Score → Policy Decision → Guardrails → Execute → Track Outcome
```

| Stage | Description |
|---|---|
| **Detect** | Scans transactions for failures, abandoned checkouts, lapsed subscriptions, overdue invoices |
| **Diagnose** | LLM agent (Ollama / Llama 3.1) analyzes root cause and recommends an action |
| **Score** | Heuristic recovery probability model factors in failure reason, retry count, and customer history |
| **Policy Engine** | Pure deterministic engine maps diagnosis → approved action. LLM *advises*, policy *decides* |
| **Guardrails** | Hard blocks on max retries, contact frequency limits, and high-value auto-approval caps |
| **Execute** | Calls Razorpay APIs (Orders, Payment Links, UPI) or simulates outreach (WhatsApp, Email, Voice) |
| **Track** | Monitors outcomes, resolves cases, and updates customer success rates |

### Supported Case Types

| Case Type | Example Actions |
|---|---|
| 🔴 Payment Failure | Retry (immediate/delayed), Generate UPI link |
| 🛒 Abandoned Checkout | Send 1-click recovery link |
| 🔄 Subscription Renewal Failed | Request payment method update |
| 📄 Overdue Invoice | Follow-up with payment link |

### Supported Actions

`RETRY_NOW` · `RETRY_DELAYED` · `GENERATE_UPI_LINK` · `SEND_RECOVERY_LINK` · `REQUEST_PAYMENT_METHOD_UPDATE` · `SEND_REMINDER` · `FOLLOW_UP_OVERDUE_INVOICE` · `ESCALATE_TO_HUMAN` · `STOP_RETRYING`

---

## 🏛️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  React Dashboard                     │
│         (Vite + Recharts · port 5173)                │
└─────────────────────┬───────────────────────────────┘
                      │ REST API (/api proxy)
┌─────────────────────▼───────────────────────────────┐
│               FastAPI Backend (port 8000)             │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Webhooks │  │  Cases   │  │   Analytics API   │  │
│  │  (Razorpay) │  │  CRUD   │  │  (KPIs, Charts)   │  │
│  └────┬─────┘  └────┬─────┘  └───────────────────┘  │
│       │              │                                │
│  ┌────▼──────────────▼──────────────────────────┐    │
│  │            Recovery Pipeline                  │    │
│  │  Detector → Diagnosis Agent → Recovery Model  │    │
│  │  → Policy Engine → Action Executor → Tracker  │    │
│  └──────────────────────────────────────────────┘    │
│       │                          │                    │
│  ┌────▼────┐              ┌─────▼──────┐             │
│  │ Ollama  │              │  Razorpay  │             │
│  │ (LLM)   │              │  Test Mode │             │
│  └─────────┘              └────────────┘             │
│       │                                               │
│  ┌────▼──────────────────────────────────────────┐   │
│  │         SQLite (recoverx.db)                   │   │
│  │  Customers · Transactions · Cases · Audit Log  │   │
│  └────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

---

## 🔧 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python · FastAPI · SQLAlchemy · Pydantic |
| **AI/LLM** | Ollama (local) · Llama 3.1 (with heuristic fallback) |
| **Payments** | Razorpay Test Mode (Orders, Payment Links, Webhooks) |
| **Frontend** | React 18 · Vite · Recharts |
| **Database** | SQLite (swappable to PostgreSQL) |
| **Testing** | pytest · pytest-asyncio · Faker |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Ollama** installed and running (`ollama serve`) — [Install Ollama](https://ollama.com/download)
- **Razorpay Test Mode API keys** — [Dashboard → Settings → API Keys](https://dashboard.razorpay.com)

### 1. Clone the repository

```bash
git clone https://github.com/PaulShervin/RecoverX.git
cd RecoverX
```

### 2. Set up environment variables

```bash
cp .env.example backend/.env
```

Edit `backend/.env` with your credentials:

```env
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

### 3. Pull the LLM model

```bash
ollama pull llama3.1
```

> **Note:** If Ollama is offline, RecoverX automatically falls back to intelligent domain heuristics — no crash, no degradation.

### 4. Start the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

### 6. Quick demo flow

1. Click **⚡ Seed 300 Records** — generates realistic customers, transactions, and failure scenarios
2. Click **🔍 Detect Cases** — scans transactions and creates recovery cases
3. Click **▶ Process All Open** — runs every open case through the full AI pipeline
4. Click **🎯 Simulate Batch Recoveries** — simulates payment outcomes for demo purposes
5. Explore individual cases for AI diagnosis, audit trail, and outreach messages

---

## 📁 Project Structure

```
RecoverX/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Pydantic settings (env-driven)
│   │   ├── database.py          # SQLAlchemy engine & session
│   │   ├── models.py            # ORM models (Customer, Transaction, Case, AuditEvent)
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── audit.py             # Audit trail logger
│   │   ├── api/
│   │   │   ├── webhooks.py      # Razorpay webhook ingestion
│   │   │   ├── cases.py         # Case CRUD & pipeline trigger
│   │   │   ├── analytics.py     # KPI summary & chart endpoints
│   │   │   ├── payments.py      # Razorpay order/payment APIs
│   │   │   └── data.py          # Seed data & reset endpoints
│   │   └── modules/
│   │       ├── pipeline.py      # Orchestrates the full recovery pipeline
│   │       ├── detector.py      # Scans transactions → creates cases
│   │       ├── diagnosis_agent.py  # LLM diagnosis (Ollama) + heuristic fallback
│   │       ├── recovery_model.py   # Heuristic probability scoring
│   │       ├── policy_engine.py    # Deterministic action approval
│   │       ├── action_executor.py  # Razorpay API calls & simulated actions
│   │       ├── outcome_tracker.py  # Resolves cases & updates metrics
│   │       └── outreach.py         # WhatsApp/Email/Voice message generation
│   ├── tests/                   # pytest test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main dashboard (KPIs, charts, case table)
│   │   ├── api.js               # API client
│   │   ├── main.jsx             # React entry point
│   │   └── components/
│   │       ├── CaseList.jsx     # Paginated case table
│   │       ├── CaseDetail.jsx   # Full case view (diagnosis, audit, outreach)
│   │       ├── StatCard.jsx     # KPI card component
│   │       └── AuditTrail.jsx   # Timestamped event log
│   ├── package.json
│   └── vite.config.js
└── .env.example
```

---

## 🛡️ Guardrails & Safety

RecoverX enforces **hard limits** that the AI can never bypass:

| Guardrail | Default | Configurable |
|---|---|---|
| Max retries per transaction | 4 | `MAX_RETRIES_PER_TRANSACTION` |
| Max customer contacts per 24h | 3 | `MAX_CONTACTS_PER_24H` |
| Max auto-approved amount | ₹50,000 | `MAX_AUTO_APPROVED_AMOUNT` |
| Stop-retry probability threshold | 15% | `STOP_RETRY_PROBABILITY_THRESHOLD` |

**Design principle:** The LLM *recommends*, the Policy Engine *decides*, and Guardrails *block*. The AI never directly executes payment actions.

---

## 🧪 Running Tests

```bash
cd backend
pytest tests/ -v --tb=short
```

Test coverage includes:
- Recovery model scoring
- Policy engine decisions & guardrail enforcement
- End-to-end pipeline flows
- Promise-to-pay snooze/reopen logic
- Webhook processing
- Outreach message generation
- Analytics & unit economics

---

## 🔗 Razorpay Integration

RecoverX uses **Razorpay Test Mode** for real API interactions:

| Feature | API Used |
|---|---|
| Payment retry | `POST /orders` (create order) |
| UPI payment links | `POST /payment_links` (with `upi_link: true`) |
| Webhook ingestion | `payment.failed`, `payment.captured`, `order.paid` |
| Webhook verification | HMAC-SHA256 signature validation |

> **Local webhook testing:** Use [ngrok](https://ngrok.com) to tunnel your local server and set `NGROK_PUBLIC_URL` in `.env`.

---

## 📊 Dashboard Features

- **KPI Cards** — Revenue at risk, recovered, recovery rate, penalties saved, avg recovery time
- **Case Outcomes Pie Chart** — Visual breakdown of recovered / failed / escalated / open
- **Actions Taken Bar Chart** — Distribution of all actions executed
- **Case Table** — Filterable by status, click to inspect
- **Case Detail Modal** — AI diagnosis, reasoning, audit trail, outreach messages (WhatsApp/Email/Voice)
- **Promise-to-Pay** — Snooze cases with a promise date; auto-reopens on expiry
- **Activity Log** — Real-time event feed

---

## 📜 License

This project was built for the **Razorpay Buildathon**.

---

<p align="center">
  Built with ☕ and AI by <strong>Team RecoverX</strong>
</p>
