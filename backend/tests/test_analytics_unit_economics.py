"""Tests for the unit economics analytics fields."""
import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
from app.models import Case, Customer, CaseStatus, CaseType, ActionEnum


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


def _add_customer(db):
    cid = f"cust_{uuid.uuid4().hex[:8]}"
    db.add(Customer(
        customer_id=cid, name="Test", email="t@t.com",
        previous_success_rate=0.8, payment_history=[], total_transactions=3,
    ))
    return cid


def _add_case(db, status, action, prob, amount=1000.0):
    cid = _add_customer(db)
    case = Case(
        case_id=f"case_{uuid.uuid4().hex[:8]}",
        case_type=CaseType.PAYMENT_FAILURE,
        customer_id=cid,
        amount=amount,
        status=status,
        approved_action=action,
        recovery_probability=prob,
        retry_count=0,
    )
    db.add(case)
    return case


def test_summary_has_new_fields(client, db_session):
    resp = client.get("/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "gateway_penalties_prevented" in data
    assert "net_roi_recovered" in data
    assert "promised_cases" in data


def test_gateway_penalties_counted_for_stopped_doomed(client, db_session):
    _add_case(db_session, CaseStatus.FAILED, ActionEnum.STOP_RETRYING, 0.05)
    _add_case(db_session, CaseStatus.FAILED, ActionEnum.STOP_RETRYING, 0.10)
    # this one has prob >= 0.15 — should NOT count
    _add_case(db_session, CaseStatus.FAILED, ActionEnum.STOP_RETRYING, 0.20)
    db_session.commit()

    resp = client.get("/analytics/summary")
    data = resp.json()
    # 2 doomed stops × ₹25 = ₹50
    assert data["gateway_penalties_prevented"] == 50.0


def test_net_roi_includes_recovered_revenue(client, db_session):
    recovered = _add_case(db_session, CaseStatus.RECOVERED, ActionEnum.RETRY_DELAYED, 0.8, amount=5000.0)
    _add_case(db_session, CaseStatus.FAILED, ActionEnum.STOP_RETRYING, 0.05)
    db_session.commit()

    resp = client.get("/analytics/summary")
    data = resp.json()
    # net_roi = recovered (5000) + penalties (25) - interventions (2 × 5 = 10) = 5015
    assert data["net_roi_recovered"] == pytest.approx(5015.0, abs=1.0)


def test_promised_cases_count(client, db_session):
    _add_case(db_session, CaseStatus.PROMISED_TO_PAY, None, 0.6)
    _add_case(db_session, CaseStatus.PROMISED_TO_PAY, None, 0.7)
    _add_case(db_session, CaseStatus.OPEN, None, 0.5)
    db_session.commit()

    resp = client.get("/analytics/summary")
    data = resp.json()
    assert data["promised_cases"] == 2
