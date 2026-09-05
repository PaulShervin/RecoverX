"""Outcome Tracker — updates case status to RECOVERED / FAILED / ESCALATED."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..models import Case, CaseStatus, ActionEnum
from ..audit import log_event


def update_outcome(case: Case, action: ActionEnum, execution_success: bool, db: Session) -> None:
    """
    Determine final or intermediate case status based on the executed action and its result.
    """
    terminal_actions = {
        ActionEnum.ESCALATE_TO_HUMAN: CaseStatus.ESCALATED,
        ActionEnum.STOP_RETRYING: CaseStatus.FAILED,
    }

    if action in terminal_actions:
        _resolve(case, terminal_actions[action], db)
        return

    if not execution_success:
        # Action failed to execute — increment retry count, stay OPEN
        case.retry_count += 1
        case.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        log_event(db, case.case_id, "EXECUTION_FAILED", "Action execution failed; case remains OPEN")
        db.commit()
        return

    # For non-terminal actions, case stays OPEN awaiting webhook confirmation
    case.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    log_event(db, case.case_id, "AWAITING_OUTCOME", f"Action {action.value} executed; awaiting payment outcome")
    db.commit()


def mark_recovered(case: Case, payment_id: str, db: Session) -> None:
    """Called by webhook handler when payment succeeds."""
    _resolve(case, CaseStatus.RECOVERED, db, extra=f"payment_id={payment_id}")
    case.razorpay_payment_id = payment_id
    db.commit()


def mark_failed(case: Case, reason: str, db: Session) -> None:
    """Called by webhook handler when payment definitively fails."""
    _resolve(case, CaseStatus.FAILED, db, extra=reason)


def _resolve(case: Case, status: CaseStatus, db: Session, extra: str = "") -> None:
    case.status = status
    case.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    case.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    msg = f"Case resolved: {status.value}"
    if extra:
        msg += f" | {extra}"
    if status == CaseStatus.RECOVERED:
        msg += f" | ₹{case.amount:,.2f} recovered"
    log_event(db, case.case_id, f"CASE_{status.value}", msg)
    db.commit()
