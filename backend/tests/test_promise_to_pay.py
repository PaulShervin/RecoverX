"""Tests for the Promise-to-Pay API endpoint and pipeline snooze logic."""
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
from app.models import Case, Customer, Transaction, CaseStatus, CaseType
from app.modules.pipeline import process_case


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_case(db, status=CaseStatus.OPEN):
    cid = f"cust_{uuid.uuid4().hex[:8]}"
    db.add(Customer(
        customer_id=cid, name="Test User", email="t@t.com",
        previous_success_rate=0.8, payment_history=[], total_transactions=5,
    ))
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    case = Case(
        case_id=case_id, case_type=CaseType.PAYMENT_FAILURE,
        customer_id=cid, amount=1500.0, failure_reason="EXPIRED_CARD",
        retry_count=0, status=status,
    )
    db.add(case)
    db.commit()
    return case


def test_promise_to_pay_sets_status(client, db_session):
    case = _seed_case(db_session)
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    resp = client.post(
        f"/cases/{case.case_id}/promise-to-pay",
        json={"promise_date": future, "note": "Will pay on Friday"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PROMISED_TO_PAY"


def test_promise_to_pay_updates_db(client, db_session):
    case = _seed_case(db_session)
    future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    client.post(f"/cases/{case.case_id}/promise-to-pay", json={"promise_date": future})
    db_session.refresh(case)
    assert case.status == CaseStatus.PROMISED_TO_PAY
    assert case.promise_date is not None


def test_promise_to_pay_records_audit_event(client, db_session):
    case = _seed_case(db_session)
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    client.post(f"/cases/{case.case_id}/promise-to-pay", json={"promise_date": future, "note": "Payday"})
    db_session.refresh(case)
    event_types = {e.event_type for e in case.audit_events}
    assert "PROMISE_TO_PAY_RECORDED" in event_types


def test_promise_to_pay_rejects_wrong_status(client, db_session):
    case = _seed_case(db_session, status=CaseStatus.RECOVERED)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = client.post(f"/cases/{case.case_id}/promise-to-pay", json={"promise_date": future})
    assert resp.status_code == 400


def test_promise_to_pay_snoozes_pipeline(db_session):
    case = _seed_case(db_session)
    case.status = CaseStatus.PROMISED_TO_PAY
    case.promise_date = (datetime.now(timezone.utc) + timedelta(days=7)).replace(tzinfo=None)
    db_session.commit()

    result = process_case(case, db_session)
    assert result["status"] == "PROMISED_TO_PAY"
    assert result["approved_action"] is None


def test_promise_expired_reopens_case(db_session):
    from unittest.mock import patch
    from app.schemas import DiagnosisOutput
    from app.models import ActionEnum

    case = _seed_case(db_session)
    case.status = CaseStatus.PROMISED_TO_PAY
    case.promise_date = (datetime.now(timezone.utc) - timedelta(days=1)).replace(tzinfo=None)
    db_session.commit()

    mock_diag = DiagnosisOutput(
        diagnosis="Test", recovery_probability=0.7,
        recommended_action=ActionEnum.RETRY_DELAYED, reasoning="test",
    )
    with patch("app.modules.pipeline.get_diagnosis", return_value=mock_diag):
        result = process_case(case, db_session)
    assert result["status"] != "PROMISED_TO_PAY"
