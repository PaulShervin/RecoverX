"""Tests for the outreach generator module."""
import pytest
from unittest.mock import MagicMock
from app.modules.outreach import generate_outreach, _reason_hindi
from app.models import Case, CaseType


def _make_case(case_type=CaseType.PAYMENT_FAILURE, failure_reason="EXPIRED_CARD",
               amount=2499.0, case_id="case-test-001", payment_link_url=None):
    case = MagicMock(spec=Case)
    case.case_id = case_id
    case.case_type = case_type
    case.failure_reason = failure_reason
    case.amount = amount
    case.payment_link_url = payment_link_url
    return case


def test_generate_outreach_returns_three_messages():
    case = _make_case()
    msgs = generate_outreach(case, "Priya Sharma")
    assert len(msgs) == 3


def test_outreach_channels_are_correct():
    case = _make_case()
    msgs = generate_outreach(case, "Ravi Kumar")
    channels = {m["channel"] for m in msgs}
    assert channels == {"whatsapp", "email", "voice"}


def test_whatsapp_message_contains_hinglish():
    case = _make_case()
    msgs = generate_outreach(case, "Amit Singh")
    wa = next(m for m in msgs if m["channel"] == "whatsapp")
    assert "Namaste" in wa["content"] or "Aapka" in wa["content"]
    assert "₹2,499" in wa["content"]


def test_whatsapp_uses_upi_link_when_available():
    case = _make_case(payment_link_url="https://rzp.io/l/abc123")
    msgs = generate_outreach(case, "Deepa")
    wa = next(m for m in msgs if m["channel"] == "whatsapp")
    assert "rzp.io/l/abc123" in wa["content"]


def test_email_message_is_english():
    case = _make_case()
    msgs = generate_outreach(case, "John Doe")
    email = next(m for m in msgs if m["channel"] == "email")
    assert "Dear John Doe" in email["content"]
    assert "Subject:" in email["content"]


def test_voice_script_has_all_sections():
    case = _make_case()
    msgs = generate_outreach(case, "Sonia")
    voice = next(m for m in msgs if m["channel"] == "voice")
    for section in ["[OPENING]", "[EMPATHY]", "[EXPLANATION]", "[UPI CTA]", "[CLOSE]"]:
        assert section in voice["content"]


def test_checkout_abandoned_whatsapp_copy():
    case = _make_case(case_type=CaseType.CHECKOUT_ABANDONED, failure_reason="CHECKOUT_ABANDONED")
    msgs = generate_outreach(case, "Maya")
    wa = next(m for m in msgs if m["channel"] == "whatsapp")
    assert "order" in wa["content"].lower() or "complete" in wa["content"].lower()


def test_subscription_failure_copy():
    case = _make_case(
        case_type=CaseType.SUBSCRIPTION_RENEWAL_FAILED,
        failure_reason="SUBSCRIPTION_RENEWAL_FAILED",
    )
    msgs = generate_outreach(case, "Kiran")
    wa = next(m for m in msgs if m["channel"] == "whatsapp")
    assert "subscription" in wa["content"].lower()


def test_reason_hindi_mapping():
    assert "card" in _reason_hindi("EXPIRED_CARD")
    assert "balance" in _reason_hindi("INSUFFICIENT_FUNDS")
    assert "technical" in _reason_hindi("UNKNOWN_REASON")
