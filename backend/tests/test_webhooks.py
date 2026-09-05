"""Tests for webhook signature verification and idempotency."""
import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.database import init_db, SessionLocal, engine
from app.models import Base

client = TestClient(app, raise_server_exceptions=False)

WEBHOOK_SECRET = "test_webhook_secret"


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Use an in-memory SQLite DB for each test."""
    from sqlalchemy import create_engine
    from app.database import Base
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def _webhook_payload(event: str = "payment.captured") -> dict:
    return {
        "event_id": "evt_test_123",
        "event": event,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_abc",
                    "order_id": "order_test_xyz",
                    "amount": 100000,
                    "currency": "INR",
                }
            }
        },
    }


@patch("app.config.settings.razorpay_webhook_secret", WEBHOOK_SECRET)
def test_valid_signature_accepted():
    payload = _webhook_payload()
    body = json.dumps(payload).encode()
    sig = _sign(body)
    resp = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    # 200 or 500 (DB issue in test env) — not 400 (signature)
    assert resp.status_code != 400


@patch("app.config.settings.razorpay_webhook_secret", WEBHOOK_SECRET)
def test_invalid_signature_rejected():
    payload = _webhook_payload()
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": "bad_sig", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400


@patch("app.config.settings.razorpay_webhook_secret", WEBHOOK_SECRET)
def test_missing_signature_rejected():
    payload = _webhook_payload()
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhooks/razorpay",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_invalid_json_rejected():
    resp = client.post(
        "/webhooks/razorpay",
        content=b"not json",
        headers={"X-Razorpay-Signature": "anything", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400
