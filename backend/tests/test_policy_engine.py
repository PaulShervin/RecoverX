"""Unit tests for Policy Engine — covers every row in the policy table and guardrails."""
import pytest
from app.models import ActionEnum, CaseType, FailureReason
from app.schemas import PolicyInput, PolicyOutput
from app.modules.policy_engine import decide
from app.config import settings


def _inp(**overrides) -> PolicyInput:
    defaults = dict(
        case_id="test-case",
        case_type=CaseType.PAYMENT_FAILURE,
        failure_reason=FailureReason.TEMPORARY_FAILURE.value,
        retry_count=0,
        amount=1000.0,
        recovery_probability=0.80,
        recommended_action=ActionEnum.RETRY_DELAYED,
        contacts_last_24h=0,
    )
    defaults.update(overrides)
    return PolicyInput(**defaults)


# ── Policy table ──────────────────────────────────────────────────────────────

def test_temporary_failure_maps_to_retry_delayed():
    out = decide(_inp(failure_reason="TEMPORARY_FAILURE", recovery_probability=0.80))
    assert out.approved_action == ActionEnum.RETRY_DELAYED
    assert not out.blocked


def test_insufficient_funds_maps_to_generate_upi_link():
    out = decide(_inp(
        failure_reason="INSUFFICIENT_FUNDS",
        recovery_probability=0.50,
        recommended_action=ActionEnum.RETRY_DELAYED,
    ))
    assert out.approved_action == ActionEnum.GENERATE_UPI_LINK


def test_expired_card_maps_to_generate_upi_link():
    out = decide(_inp(
        failure_reason="EXPIRED_CARD",
        recovery_probability=0.65,
        recommended_action=ActionEnum.REQUEST_PAYMENT_METHOD_UPDATE,
    ))
    assert out.approved_action == ActionEnum.GENERATE_UPI_LINK


def test_checkout_abandoned_maps_to_send_recovery_link():
    out = decide(_inp(
        case_type=CaseType.CHECKOUT_ABANDONED,
        failure_reason="CHECKOUT_ABANDONED",
        recovery_probability=0.40,
        recommended_action=ActionEnum.SEND_RECOVERY_LINK,
    ))
    assert out.approved_action == ActionEnum.SEND_RECOVERY_LINK


def test_subscription_renewal_failed_maps_to_method_update():
    out = decide(_inp(
        case_type=CaseType.SUBSCRIPTION_RENEWAL_FAILED,
        failure_reason="SUBSCRIPTION_RENEWAL_FAILED",
        recovery_probability=0.55,
        recommended_action=ActionEnum.REQUEST_PAYMENT_METHOD_UPDATE,
    ))
    assert out.approved_action == ActionEnum.REQUEST_PAYMENT_METHOD_UPDATE


def test_repeated_failure_maps_to_escalate():
    out = decide(_inp(
        failure_reason="REPEATED_FAILURE",
        retry_count=3,
        recovery_probability=0.20,
        recommended_action=ActionEnum.ESCALATE_TO_HUMAN,
    ))
    assert out.approved_action == ActionEnum.ESCALATE_TO_HUMAN


def test_overdue_receivable_maps_to_follow_up():
    out = decide(_inp(
        case_type=CaseType.OVERDUE_RECEIVABLE,
        failure_reason="OVERDUE_RECEIVABLE",
        recovery_probability=0.35,
        recommended_action=ActionEnum.FOLLOW_UP_OVERDUE_INVOICE,
    ))
    assert out.approved_action == ActionEnum.FOLLOW_UP_OVERDUE_INVOICE


# ── Low probability threshold ─────────────────────────────────────────────────

def test_low_probability_stops_retrying():
    out = decide(_inp(recovery_probability=0.05))
    assert out.approved_action == ActionEnum.STOP_RETRYING
    assert out.overridden or out.approved_action == ActionEnum.STOP_RETRYING


def test_above_threshold_allows_action():
    out = decide(_inp(recovery_probability=0.80))
    assert out.approved_action != ActionEnum.STOP_RETRYING


# ── Guardrails ────────────────────────────────────────────────────────────────

def test_guardrail_max_retries_blocks():
    out = decide(_inp(retry_count=settings.max_retries_per_transaction))
    assert out.blocked
    assert out.approved_action == ActionEnum.ESCALATE_TO_HUMAN


def test_guardrail_max_contacts_blocks():
    out = decide(_inp(contacts_last_24h=settings.max_contacts_per_24h))
    assert out.blocked
    assert out.approved_action == ActionEnum.STOP_RETRYING


def test_guardrail_high_value_escalates():
    out = decide(_inp(amount=settings.max_auto_approved_amount + 1))
    assert out.blocked
    assert out.approved_action == ActionEnum.ESCALATE_TO_HUMAN


def test_guardrail_does_not_block_below_limit():
    out = decide(_inp(amount=settings.max_auto_approved_amount - 1))
    assert not out.blocked


# ── LLM conservative override preserved ──────────────────────────────────────

def test_llm_escalate_preserved_by_policy():
    """If LLM recommends ESCALATE_TO_HUMAN, policy honours it even if table disagrees."""
    out = decide(_inp(
        failure_reason="TEMPORARY_FAILURE",
        recovery_probability=0.80,
        recommended_action=ActionEnum.ESCALATE_TO_HUMAN,
    ))
    assert out.approved_action == ActionEnum.ESCALATE_TO_HUMAN
