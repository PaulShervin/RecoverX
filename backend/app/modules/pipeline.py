"""
Full recovery pipeline: Detect → Diagnose → Score → Decide → Guard → Execute → Track.
Each step writes to the audit trail before proceeding.
"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from ..models import Case, ActionEnum, CaseStatus, Customer
from datetime import datetime, timezone as _tz
from ..schemas import PolicyInput
from ..audit import log_event
from ..modules.recovery_model import score as recovery_score
from ..modules.diagnosis_agent import get_diagnosis
from ..modules.policy_engine import decide
from ..modules.action_executor import execute
from ..modules.outcome_tracker import update_outcome

logger = logging.getLogger(__name__)


def process_case(case: Case, db: Session) -> dict:
    """
    Run one case through the full pipeline.
    Returns a summary dict. Errors in one case never crash others.
    """
    # Skip snoozed cases until promise_date passes
    if case.status == CaseStatus.PROMISED_TO_PAY:
        now = datetime.now(_tz.utc).replace(tzinfo=None)
        if case.promise_date and case.promise_date > now:
            log_event(db, case.case_id, "SNOOZED", f"Skipped: promised to pay by {case.promise_date.date()}")
            db.commit()
            return {"case_id": case.case_id, "approved_action": None, "status": "PROMISED_TO_PAY", "error": None}
        # Promise date passed — reopen
        case.status = CaseStatus.OPEN
        log_event(db, case.case_id, "PROMISE_EXPIRED", "Promise date passed; resuming recovery")
        db.commit()
    try:
        return _run(case, db)
    except Exception as e:
        logger.error("Pipeline error for case %s: %s", case.case_id, e, exc_info=True)
        log_event(db, case.case_id, "PIPELINE_ERROR", f"Unhandled error: {e}")
        db.commit()
        return {"case_id": case.case_id, "error": str(e)}


def _run(case: Case, db: Session) -> dict:
    customer = db.query(Customer).filter_by(customer_id=case.customer_id).first()
    prev_success = customer.previous_success_rate if customer else 0.75
    total_tx = customer.total_transactions if customer else 0
    customer_name = customer.name if customer else "Unknown"

    # ── Step 1: Recovery probability (heuristic model) ───────────────────────
    prob = recovery_score(
        failure_reason=case.failure_reason,
        retry_count=case.retry_count,
        previous_success_rate=prev_success,
        total_transactions=total_tx,
    )
    log_event(db, case.case_id, "SCORED", f"Recovery probability = {prob:.0%} (heuristic model)")

    # ── Step 2: AI Diagnosis (LLM) ───────────────────────────────────────────
    log_event(db, case.case_id, "DIAGNOSING", "Sending to AI Diagnosis Agent")
    diagnosis = get_diagnosis({
        "case_id": case.case_id,
        "case_type": case.case_type.value,
        "failure_reason": case.failure_reason,
        "amount": case.amount,
        "retry_count": case.retry_count,
        "previous_success_rate": prev_success,
        "total_transactions": total_tx,
        "customer_name": customer_name,
    })

    # Override probability with heuristic model (LLM is advisory on prob only)
    diagnosis_prob = prob  # heuristic wins; LLM reasoning captured for audit

    case.diagnosis = diagnosis.diagnosis
    case.recovery_probability = diagnosis_prob
    case.recommended_action = diagnosis.recommended_action
    case.reasoning = diagnosis.reasoning
    db.flush()

    log_event(db, case.case_id, "DIAGNOSED", (
        f"Diagnosis: {diagnosis.diagnosis} | "
        f"LLM recommended: {diagnosis.recommended_action.value} | "
        f"Probability: {diagnosis_prob:.0%}"
    ))

    # ── Step 3: Policy Engine decision ───────────────────────────────────────
    contacts_24h = _contacts_last_24h(case.customer_id, db)
    recommended = diagnosis.recommended_action
    policy_in = PolicyInput(
        case_id=case.case_id,
        case_type=case.case_type,
        failure_reason=case.failure_reason,
        retry_count=case.retry_count,
        amount=case.amount,
        recovery_probability=diagnosis_prob,
        recommended_action=recommended,
        contacts_last_24h=contacts_24h,
    )
    policy_out = decide(policy_in)

    case.approved_action = policy_out.approved_action
    case.guardrail_override = policy_out.blocked or policy_out.overridden
    case.guardrail_reason = policy_out.block_reason or policy_out.override_reason
    db.flush()

    override_info = ""
    if policy_out.blocked:
        override_info = f" [GUARDRAIL BLOCK: {policy_out.block_reason}]"
    elif policy_out.overridden:
        override_info = f" [POLICY OVERRIDE: {policy_out.override_reason}]"

    log_event(db, case.case_id, "DECIDED", (
        f"Approved action: {policy_out.approved_action.value}{override_info}"
    ))

    # ── Step 4: Execute ───────────────────────────────────────────────────────
    result = execute(case, policy_out.approved_action, db)

    # ── Step 5: Outcome tracking (terminal actions resolve immediately) ───────
    update_outcome(case, policy_out.approved_action, result["success"], db)

    return {
        "case_id": case.case_id,
        "approved_action": policy_out.approved_action.value,
        "recovery_probability": diagnosis_prob,
        "status": case.status.value,
        "guardrail_override": case.guardrail_override,
        "razorpay_order_id": result.get("razorpay_order_id"),
        "error": None,
    }


_CUSTOMER_CONTACT_ACTIONS = {
    "RETRY_NOW", "RETRY_DELAYED", "REQUEST_PAYMENT_METHOD_UPDATE",
    "SEND_RECOVERY_LINK", "SEND_REMINDER", "FOLLOW_UP_OVERDUE_INVOICE",
}


def _contacts_last_24h(customer_id: str, db: Session) -> int:
    """Count customer-facing contact actions in the last 24h — excludes internal actions."""
    from ..models import AuditEvent, Case as CaseModel
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    events = (
        db.query(AuditEvent)
        .join(CaseModel, AuditEvent.case_id == CaseModel.case_id)
        .filter(
            CaseModel.customer_id == customer_id,
            AuditEvent.event_type == "ACTION_EXECUTING",
            AuditEvent.timestamp >= cutoff,
        )
        .all()
    )
    return sum(
        1 for e in events
        if any(action in e.details for action in _CUSTOMER_CONTACT_ACTIONS)
    )


def run_batch(cases: list[Case], db: Session) -> list[dict]:
    """Process all cases; a failure in one never blocks others."""
    return [process_case(c, db) for c in cases]
