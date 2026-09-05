# TOOLS & AGENT RULES — AI Revenue Recovery Agent

> Purpose: what to build with, and the hard rules the coding agent (and every
> team member) must follow while building. Read this before writing code.

---

## 1. Tech Stack

**TODO — lock the final choice based on what the team already knows. Don't
add a technology just to make the architecture diagram look impressive.**

| Layer | Candidate(s) | Chosen |
|---|---|---|
| Frontend | React / Next.js | TODO |
| Backend | FastAPI / Node.js | TODO |
| Database | PostgreSQL | TODO |
| AI/ML | Python, classification/prediction models | TODO |
| Agent orchestration | LangGraph or equivalent | TODO |
| LLM provider | TODO | TODO |
| Payments | Razorpay Test Mode | ✅ Razorpay |
| Events | Razorpay Webhooks | ✅ |
| Analytics/Dashboard | TODO (custom / charting lib) | TODO |
| Deployment | Cloud (TODO which provider) | TODO |

---

## 2. Design Patterns to Use

- **Separation of concerns (hard requirement):** Reasoning (LLM) / Prediction (model) / Control (policy engine) / Execution (Razorpay) / Observability (analytics) must be separate modules/services — never merged into one "do everything" function.
- **Fixed schema I/O for the LLM:** the Diagnosis Agent must always emit structured JSON matching a fixed schema (see ARCHITECTURE.md §2.2). Never parse free-form text from the LLM for a decision that affects money.
- **Policy engine as a pure function:** given (diagnosis, probability, case data) → (approved action), with no side effects and no LLM call inside it. This makes it testable and auditable.
- **Event-driven state updates:** use Razorpay webhooks to update case state rather than polling.
- **Append-only audit log:** every state transition writes an audit event before or atomically with the action — never log after the fact only.
- **Idempotency:** webhook handlers and retry logic must be idempotent — a duplicate webhook delivery or retry trigger must not double-charge or double-log.

---

## 3. Rules the Agent Must Follow

### Hard rules (never break these)
1. **Never use live Razorpay keys or real money.** Test Mode only, always.
2. **The LLM never calls a payment-executing function directly.** Its output always passes through the Policy Engine first.
3. **Never let a case retry indefinitely.** Enforce the retry sequencing / escalation rule in ARCHITECTURE.md §2.4.
4. **Never skip the audit trail.** Every detect/diagnose/decide/act/observe step must produce a logged event.
5. **Never exceed the guardrail limits** defined in ARCHITECTURE.md §2.5 (max retries, max contacts/24h, max auto-approved amount), even if the LLM recommends otherwise.
6. **Never fabricate metrics.** Dashboard numbers must come from actual logged case data, not hardcoded/demo-faked values (synthetic data is fine; fake computed metrics are not).
7. **Never merge the Diagnosis Agent and Policy Engine into one component.** They must remain independently callable and testable.

### Working rules
- Keep the MVP scope to Payment Failure Recovery first. Do not start Checkout or Subscription recovery modules until the core loop (detect → diagnose → decide → act → observe → measure) works end-to-end on payment failures.
- When in doubt about scope, check SOLUTION.md §5 ("What We Are Explicitly NOT Building") before adding a feature.
- Any new guardrail, policy rule, or schema change must be reflected in ARCHITECTURE.md in the same work session — don't let code and docs drift apart.
- Log open decisions as `TODO` in the relevant doc (PROGRESS.md, ARCHITECTURE.md) rather than silently picking an approach and moving on, so the team can review.
- Be honest in code comments and docs about what's a real trained model vs. a heuristic vs. an LLM guess — this affects what the team can honestly claim in the demo.

---

## 4. File Map (how these docs relate)

```
01_PROGRESS.md        — status, timeline, decisions log, blockers (update every session)
02_SOLUTION.md         — what we're building and why (product spec)
03_ARCHITECTURE.md     — how it's built (system design, source of truth for structure)
04_TOOLS_AND_RULES.md  — this file: stack, patterns, hard rules for the agent
```

When starting a new work session with the coding agent, point it to all four files, in this order: SOLUTION → ARCHITECTURE → TOOLS_AND_RULES → PROGRESS.
