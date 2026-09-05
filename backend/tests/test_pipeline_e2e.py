"""
End-to-end integration test: synthetic case → full pipeline → terminal state + audit trail.
Uses an in-memory SQLite DB and mocked LLM/Razorpay calls.
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Case, Customer, Transaction, CaseStatus, CaseType, ActionEnum
from app.schemas import DiagnosisOutput
from app.modules.detector import detect_cases
from app.modules.pipeline import process_case
import uuid
from datetime import datetime, timezone


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _seed(db, failure_reason="TEMPORARY_FAILURE", retry_count=0, amount=2499.0):
    cid = f"cust_{uuid.uuid4().hex[:8]}"
    customer = Customer(
        customer_id=cid,
        name="Test User",
        email="test@example.com",
        previous_success_rate=0.90,
        payment_history=[],
        total_transactions=10,
    )
    db.add(customer)

    tx = Transaction(
        transaction_id=f"tx_{uuid.uuid4().hex[:10]}",
        customer_id=cid,
        amount=amount,
        payment_method="card",
        payment_status="failed",
        failure_reason=failure_reason,
        retry_count=retry_count,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(tx)
    db.commit()
    return customer, tx


MOCK_DIAGNOSIS = DiagnosisOutput(
    diagnosis="Temporary network failure caused the payment to fail.",
    recovery_probability=0.80,
    recommended_action=ActionEnum.RETRY_DELAYED,
    reasoning="Temporary failures have high recovery rate with a delayed retry.",
)


@patch("app.modules.pipeline.get_diagnosis", return_value=MOCK_DIAGNOSIS)
def test_full_pipeline_creates_terminal_state(mock_diag, db):
    """Happy path: temporary failure → RETRY_DELAYED → case awaiting outcome."""
    customer, tx = _seed(db)

    cases = detect_cases([tx], db)
    assert len(cases) == 1
    case = cases[0]
    assert case.status == CaseStatus.OPEN

    result = process_case(case, db)
    assert result["error"] is None
    assert result["approved_action"] is not None

    db.refresh(case)
    # Case should have diagnosis, probability, approved_action
    assert case.diagnosis is not None
    assert case.recovery_probability is not None
    assert case.approved_action is not None
    # Audit trail must have ≥4 events
    assert len(case.audit_events) >= 4


@patch("app.modules.pipeline.get_diagnosis", return_value=MOCK_DIAGNOSIS)
def test_guardrail_blocks_excessive_retries(mock_diag, db):
    """Guardrail: retry_count at max → ESCALATE_TO_HUMAN, case is ESCALATED."""
    from app.config import settings
    customer, tx = _seed(db, retry_count=settings.max_retries_per_transaction)

    cases = detect_cases([tx], db)
    case = cases[0]

    result = process_case(case, db)
    assert result["approved_action"] == ActionEnum.ESCALATE_TO_HUMAN.value

    db.refresh(case)
    assert case.status == CaseStatus.ESCALATED
    assert case.guardrail_override is True


@patch("app.modules.pipeline.get_diagnosis", return_value=MOCK_DIAGNOSIS)
def test_high_value_escalates(mock_diag, db):
    """Guardrail: amount over limit → ESCALATE_TO_HUMAN."""
    from app.config import settings
    customer, tx = _seed(db, amount=settings.max_auto_approved_amount + 1000)

    cases = detect_cases([tx], db)
    result = process_case(cases[0], db)
    assert result["approved_action"] == ActionEnum.ESCALATE_TO_HUMAN.value


@patch("app.modules.pipeline.get_diagnosis", return_value=MOCK_DIAGNOSIS)
def test_expired_card_gets_upi_link(mock_diag, db):
    """Policy table: expired card → GENERATE_UPI_LINK (UPI cascading fallback)."""
    customer, tx = _seed(db, failure_reason="EXPIRED_CARD")
    cases = detect_cases([tx], db)
    result = process_case(cases[0], db)
    assert result["approved_action"] == ActionEnum.GENERATE_UPI_LINK.value


@patch("app.modules.pipeline.get_diagnosis", return_value=DiagnosisOutput(
    diagnosis="Very unlikely to recover.",
    recovery_probability=0.05,
    recommended_action=ActionEnum.RETRY_NOW,
    reasoning="Low probability case.",
))
def test_low_probability_stops_retrying(mock_diag, db):
    """Low recovery probability → STOP_RETRYING regardless of LLM recommendation."""
    customer, tx = _seed(db, failure_reason="REPEATED_FAILURE", retry_count=3)
    cases = detect_cases([tx], db)
    result = process_case(cases[0], db)
    assert result["approved_action"] == ActionEnum.STOP_RETRYING.value


@patch("app.modules.pipeline.get_diagnosis", return_value=MOCK_DIAGNOSIS)
def test_batch_runs_all_cases_independently(mock_diag, db):
    """A failure in one case must not prevent others from processing."""
    from app.modules.pipeline import run_batch

    c1, tx1 = _seed(db, failure_reason="TEMPORARY_FAILURE")
    c2, tx2 = _seed(db, failure_reason="EXPIRED_CARD")
    c3, tx3 = _seed(db, failure_reason="INSUFFICIENT_FUNDS")

    cases = detect_cases([tx1, tx2, tx3], db)
    results = run_batch(cases, db)
    assert len(results) == 3
    for r in results:
        assert r.get("error") is None or isinstance(r.get("error"), str)


@patch("app.modules.pipeline.get_diagnosis", return_value=MOCK_DIAGNOSIS)
def test_audit_trail_is_complete(mock_diag, db):
    """Every state transition must produce an audit event."""
    customer, tx = _seed(db)
    cases = detect_cases([tx], db)
    case = cases[0]

    process_case(case, db)
    db.refresh(case)

    event_types = {e.event_type for e in case.audit_events}
    required = {"DETECTED", "SCORED", "DIAGNOSING", "DIAGNOSED", "DECIDED"}
    assert required.issubset(event_types), f"Missing events: {required - event_types}"


@patch("app.modules.pipeline.get_diagnosis", return_value=MOCK_DIAGNOSIS)
def test_duplicate_detection_skipped(mock_diag, db):
    """A transaction already in an open case must not produce a second case."""
    customer, tx = _seed(db)
    cases1 = detect_cases([tx], db)
    cases2 = detect_cases([tx], db)
    assert len(cases1) == 1
    assert len(cases2) == 0
