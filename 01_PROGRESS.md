# PROGRESS — AI Revenue Recovery Agent (Razorpay Buildathon, Track 03)

> Purpose: single running log of what's decided, what's built, what's pending.

---

## 1. Track & Team

- **Track:** 03 — AI Revenue Recovery
- **Core one-liner:**
  > "We're building an AI Revenue Recovery Agent that detects revenue at risk, diagnoses the cause, chooses the optimal bounded recovery action, executes it through Razorpay's test environment, and measures the actual revenue recovered."

---

## 2. Current Status

| Area | Status | Notes |
|---|---|---|
| Track selection | ✅ Done | Track 03, scored 9.2/10 |
| Scope (MVP boundary) | ✅ Done | See SOLUTION.md |
| Architecture | ✅ Done | See ARCHITECTURE.md |
| DB schema + ORM models | ✅ Done | Customer, Transaction, Case, AuditEvent, WebhookEvent |
| Synthetic dataset | ✅ Done | 200–300 records via `/data/seed`; realistic distributions |
| Detection module | ✅ Done | `detector.py` — PAYMENT_FAILURE / CHECKOUT_ABANDONED / SUBSCRIPTION / OVERDUE |
| Diagnosis (LLM) module | ✅ Done | `diagnosis_agent.py` — Ollama llama3.1, fixed JSON schema, retry+fallback |
| Recovery probability model | ✅ Done | `recovery_model.py` — heuristic (disclosed as such); per-reason base rates + retry penalty |
| Policy engine | ✅ Done | `policy_engine.py` — pure function, full policy table + guardrail hard limits |
| Guardrails | ✅ Done | max 4 retries, max 3 contacts/24h, max ₹50K auto, 15% stop-retry threshold |
| Action executor | ✅ Done | `action_executor.py` — Razorpay Test Mode for RETRY_NOW; others simulated/logged |
| Outcome tracker | ✅ Done | `outcome_tracker.py` — terminal/non-terminal action routing |
| Webhook handler | ✅ Done | `webhooks.py` — HMAC-SHA256 sig verify, idempotency, payment.captured/failed routing |
| Audit trail | ✅ Done | `audit.py` — append-only, every state transition logged before action |
| Analytics API | ✅ Done | `/analytics/summary` — all metrics from real Case data, no hardcoded values |
| FastAPI backend | ✅ Done | `main.py` — lifespan pattern, CORS, /health, 4 routers |
| Dashboard (React) | ✅ Done | KPI cards, pie/bar charts, case table, case detail modal, audit trail viewer |
| Full pipeline | ✅ Done | `pipeline.py` — Detect→Score→Diagnose→Decide→Guard→Execute→Track |
| Test suite | ✅ Done | 60 tests passing (100%) — guardrails/pipeline/policy/webhooks/recovery/outreach/p2p/economics |
| Razorpay Test Mode | ✅ Done | RETRY_NOW + UPI Payment Link fallback in Test Mode |
| Hinglish Recovery Outreach | ✅ Done | Multi-channel WhatsApp (Hinglish), Voice Call Script & Email (`outreach.py`) |
| Promise-to-Pay (P2P) Engine | ✅ Done | P2P date capture, status `PROMISED_TO_PAY`, auto-snooze pipeline, audit log |
| Unit Economics / Penalty ROI | ✅ Done | Gateway fees prevented metric + net ROI calculated and displayed |
| Stretch: Checkout Recovery | ✅ Done | Detected + SEND_RECOVERY_LINK action in pipeline |
| Stretch: Subscription Recovery | ✅ Done | Detected + REQUEST_PAYMENT_METHOD_UPDATE in pipeline |

Legend: ✅ Done · 🟡 In progress · ⬜ Not started

---

## 3. Architecture Decisions (Locked)

- LLM (Ollama llama3.1) does **diagnosis + reasoning only** — never executes financial actions
- Heuristic model does **recovery probability** — not a trained ML model (disclosed in pitch)
- Deterministic policy engine **approves/overrides** LLM recommendations; LLM cannot bypass guardrails
- Razorpay Test Mode only — no live money
- SQLite (WAL) default; `DATABASE_URL` in `.env` to switch to Postgres
- Audit log uses `db.flush()` — writes within calling transaction, guarantees atomicity

---

## 4. How to Run

### Backend
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env    # fill in Razorpay test keys
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

### Tests
```bash
cd backend
pytest tests/ -v
```

### Demo flow
1. Click **Seed 300 Records** — generates realistic dataset
2. Click **Detect Cases** — scans for at-risk revenue, creates cases
3. Click **Process All Open** — runs full AI pipeline on every case (requires Ollama running)
4. Watch KPIs update, inspect individual cases, review audit trail

---

## 5. Session Notes

> Append-only. Newest at top.

- 2026-09-01 — Full build complete. Backend (FastAPI + SQLite + all pipeline modules), frontend (React + Vite + Recharts), 41 tests all passing. Fixed `@app.on_event("startup")` → `lifespan`, fixed all `datetime.utcnow()` deprecation warnings throughout codebase.
