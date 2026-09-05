"""Revenue-at-Risk Detector — classifies raw transaction data into Cases."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..models import Case, CaseType, CaseStatus, Transaction, AuditEvent
from ..audit import log_event


CHECKOUT_ABANDONMENT_THRESHOLD_MINUTES = 30


def detect_cases(transactions: list[Transaction], db: Session) -> list[Case]:
    """
    Given a list of transactions, produce Case records for any at-risk revenue.
    Skips transactions that already have an open case.
    """
    existing_tx_ids = {
        c.transaction_id
        for c in db.query(Case.transaction_id).all()
    }

    cases = []
    for tx in transactions:
        if tx.transaction_id in existing_tx_ids:
            continue

        case_type = _classify(tx)
        if case_type is None:
            continue

        case = Case(
            case_id=str(uuid.uuid4()),
            case_type=case_type,
            transaction_id=tx.transaction_id,
            customer_id=tx.customer_id,
            amount=tx.amount,
            failure_reason=tx.failure_reason,
            retry_count=tx.retry_count,
            status=CaseStatus.OPEN,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(case)
        db.flush()
        log_event(db, case.case_id, "DETECTED", (
            f"Revenue risk detected: {case_type.value} | "
            f"amount=₹{tx.amount:,.2f} | reason={tx.failure_reason}"
        ))
        cases.append(case)

    db.commit()
    return cases


def _classify(tx: Transaction) -> CaseType | None:
    if tx.payment_status == "failed":
        return CaseType.PAYMENT_FAILURE

    if tx.checkout_status == "abandoned":
        return CaseType.CHECKOUT_ABANDONED

    if tx.subscription_status == "failed":
        return CaseType.SUBSCRIPTION_RENEWAL_FAILED

    if tx.days_overdue and tx.days_overdue > 0:
        return CaseType.OVERDUE_RECEIVABLE

    return None
