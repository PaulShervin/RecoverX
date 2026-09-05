# ARCHITECTURE — AI Revenue Recovery Agent

> This is the authoritative architecture reference. If code and this document
> disagree, this document wins until deliberately updated. Every module below
> should map to a real folder/service in the codebase.

---

## 0. Guiding Principle

> **The LLM does not execute financial actions. It reasons. A deterministic
> policy engine decides what is allowed. Only approved actions reach Razorpay.**

```
ML / Rules        → Risk scoring + prediction
LLM / Agent       → Diagnosis + reasoning + orchestration
Policy Engine     → Guardrails (deterministic, non-negotiable)
Razorpay          → Payment execution (Test Mode only)
Analytics         → Measurement (recovery rate, precision, etc.)
```

This separation is the single most important architectural decision in this
project. It is what distinguishes this from "an LLM that does everything,"
which is not credible for a fintech use case.

---

## 1. System Overview

```
                        DATA SOURCES
                            │
                            ▼
                ┌───────────────────────┐
                │ 1. Revenue-at-Risk    │
                │    Detector           │
                └──────────┬────────────┘
                           │
                           ▼
                ┌───────────────────────┐
                │ 2. AI Diagnosis Agent │  (LLM)
                └──────────┬────────────┘
                           │
                           ▼
                ┌───────────────────────┐
                │ 3. Recovery           │
                │    Probability /      │  (ML model or heuristic v1)
                │    Risk Model         │
                └──────────┬────────────┘
                           │
                           ▼
                ┌───────────────────────┐
                │ 4. Decision / Policy  │  (deterministic)
                │    Engine             │
                └──────────┬────────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
           Retry        Notify       Escalate
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                ┌───────────────────────┐
                │ 5. Razorpay Test Mode │
                │    / Action Executor  │
                └──────────┬────────────┘
                           │
                           ▼
                ┌───────────────────────┐
                │ 6. Payment Outcome    │  (via webhook)
                └──────────┬────────────┘
                           │
                           ▼
                ┌───────────────────────┐
                │ 7. Outcome Tracker    │
                └──────────┬────────────┘
                           │
                           ▼
                ┌───────────────────────┐
                │ 8. Analytics + Audit  │
                │    Trail              │
                └───────────────────────┘
```

---

## 2. Module Reference

### 2.1 Revenue-at-Risk Detector
**Input:** raw transaction/subscription/invoice/checkout data
**Output:** a "case" record flagged as at-risk, with a case type

Case types:
| Type | Trigger condition |
|---|---|
| `PAYMENT_FAILURE` | Transaction status = failed |
| `CHECKOUT_ABANDONED` | Checkout started, not completed within threshold |
| `SUBSCRIPTION_RENEWAL_FAILED` | Recurring charge fails |
| `OVERDUE_RECEIVABLE` | Invoice due date passed, unpaid |

---

### 2.2 AI Diagnosis Agent (LLM)
**Input:** case record + failure reason + customer history + retry count
**Output:** a structured diagnosis object

```json
{
  "diagnosis": "string — plain-language explanation of why revenue is at risk",
  "recovery_probability": 0.0,
  "recommended_action": "one of the fixed action enum values",
  "reasoning": "string — short chain of reasoning for audit trail"
}
```

Rules for this module:
- Must always return the fixed JSON schema above — no free-form response.
- Must never invoke a payment action directly. It only recommends.
- `recommended_action` must be one of the values defined in §2.4 action enum — reject/retry the LLM call if it returns anything else.

---

### 2.3 Recovery Probability / Risk Model
**Input:** failure reason, retry count, customer_history, previous_success_rate
**Output:** a probability score (0.0–1.0)

**TODO — decide and document which of these v1 uses:**
- [ ] Trained classifier (e.g., logistic regression / gradient boosting on synthetic data)
- [ ] Rule-based heuristic scoring (transparent, explainable, faster to build)
- [ ] LLM-estimated score (fastest to build, least rigorous — must be disclosed as such in the pitch)

Whichever is chosen, this must be stated plainly in the demo — do not claim "ML model" if it is actually an LLM guess.

---

### 2.4 Decision / Policy Engine (deterministic — no LLM here)
**Input:** diagnosis + recovery probability + case type
**Output:** an approved action (or a block/override of the LLM's suggestion)

**Fixed action enum:**
```
RETRY_NOW
RETRY_DELAYED
REQUEST_PAYMENT_METHOD_UPDATE
SEND_RECOVERY_LINK
SEND_REMINDER
FOLLOW_UP_OVERDUE_INVOICE
ESCALATE_TO_HUMAN
STOP_RETRYING
```

**Policy table (baseline — extend as needed):**
| Condition | Action |
|---|---|
| Temporary payment failure | `RETRY_DELAYED` |
| Insufficient funds | `RETRY_DELAYED` |
| Expired card | `REQUEST_PAYMENT_METHOD_UPDATE` |
| Checkout abandoned | `SEND_RECOVERY_LINK` |
| Subscription renewal failed | `REQUEST_PAYMENT_METHOD_UPDATE` |
| Repeated failure (≥3 attempts, 0 recoveries) | `ESCALATE_TO_HUMAN` |
| High-value overdue invoice | `FOLLOW_UP_OVERDUE_INVOICE` |
| Recovery probability < threshold (TODO: set %) | `STOP_RETRYING` |

**Retry sequencing rule (do not retry blindly forever):**
```
Attempt 1 → immediate/initial retry
Attempt 2 → +24 hours
Attempt 3 → +72 hours
Attempt 4 → escalate (never auto-retry past this)
```
The engine should weigh failure reason + customer history alongside this schedule, not follow it blindly.

---

### 2.5 Guardrails (hard rules — must be enforced in code, not by prompting)

> **TODO — team must fill in exact numeric limits before demo. These are non-negotiable constraints the policy engine enforces regardless of what the LLM recommends.**

- [ ] Max retry attempts per transaction: ___
- [ ] Max customer contacts (notifications) per 24h: ___
- [ ] Max transaction amount eligible for fully-automated action (above this → force `ESCALATE_TO_HUMAN`): ___
- [ ] No refunds or account changes are ever performed by this agent (only retries, reminders, escalation)
- [ ] Every action must be logged to the audit trail before execution, not after

---

### 2.6 Action Executor / Razorpay Test Mode
**Input:** approved action from Policy Engine
**Output:** an executed operation against Razorpay's Test Mode API

```
YOUR AI → decision → RAZORPAY (Test Mode) → executes/simulates → outcome → YOUR AI analyzes
```

- Never use live money / production keys.
- All payment operations go through Razorpay Test Mode endpoints.
- Non-payment actions (send reminder, request method update) can be simulated/mocked notifications for the demo.

---

### 2.7 Webhooks / Event Layer
Replaces polling with event-driven updates.

```
Payment → Razorpay → Webhook → Backend → Update transaction record → AI evaluates outcome
```

- Webhook endpoint must verify signature before trusting payload (standard Razorpay webhook security).
- On receipt: update case status, trigger outcome tracker.

---

### 2.8 Outcome Tracker
Updates each case to one of:
```
RECOVERED
FAILED
ESCALATED
```
Also records recovery time (detection timestamp → resolution timestamp).

---

### 2.9 Analytics + Audit Trail
**Audit trail** — every step of every case, timestamped, human-readable:
```
09:01:02  Revenue risk detected
09:01:03  Failure classified as temporary
09:01:03  Recovery probability = 82%
09:01:04  Retry selected
09:01:04  Policy check passed
09:01:05  Retry executed
09:01:07  Payment successful
09:01:07  ₹2,499 recovered
```

**Analytics/dashboard** feeds off the same event log — see SOLUTION.md §8 for the metrics it must compute.

---

## 3. Data Model (minimum viable schema)

```
Case
├── case_id
├── case_type            (PAYMENT_FAILURE | CHECKOUT_ABANDONED | SUBSCRIPTION_RENEWAL_FAILED | OVERDUE_RECEIVABLE)
├── transaction_id / invoice_id / checkout_id (as applicable)
├── customer_id
├── amount
├── failure_reason
├── retry_count
├── status               (OPEN | RECOVERED | FAILED | ESCALATED)
├── diagnosis             (from AI Diagnosis Agent)
├── recovery_probability
├── recommended_action
├── approved_action        (post-guardrail — may differ from recommended)
├── created_at / updated_at / resolved_at

Customer
├── customer_id
├── previous_success_rate
├── payment_history[]     (list of past transaction outcomes)

AuditEvent
├── case_id
├── timestamp
├── event_type
├── details
```

---

## 4. Component-to-Layer Mapping

| Layer | Module(s) | LLM involved? |
|---|---|---|
| Data | Detector, synthetic dataset | No |
| Reasoning | AI Diagnosis Agent | Yes |
| Prediction | Recovery Probability Model | Depends on §2.3 decision |
| Control | Policy Engine, Guardrails | No — must stay deterministic |
| Execution | Action Executor, Razorpay Test Mode | No |
| Observability | Webhooks, Outcome Tracker, Audit Trail, Analytics | No |

---

## 5. Non-Goals / Explicit Boundaries

- No live payments.
- No LLM-initiated financial actions (LLM output is always routed through the Policy Engine).
- No fraud detection, tax handling, or unrelated verticals in scope for this build.
- No unbounded retry loops.

---

## 6. Open Architecture Decisions (must be resolved before/during build)

- [ ] TODO — Recovery probability: trained model vs heuristic vs LLM-scored (§2.3)
- [ ] TODO — Exact guardrail numeric limits (§2.5)
- [ ] TODO — Retry threshold probability below which the engine stops retrying
- [ ] TODO — Whether notifications (recovery links, reminders) are real (email/SMS) or simulated for demo purposes
- [ ] TODO — Final tech stack (see TOOLS_AND_RULES.md)
