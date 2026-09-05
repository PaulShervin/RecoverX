"""Prove guardrails block violations regardless of LLM recommendation."""
import pytest
from app.models import ActionEnum, CaseType
from app.schemas import PolicyInput
from app.modules.policy_engine import decide, _check_guardrails
from app.config import settings

RETRY_ACTIONS = [
    ActionEnum.RETRY_NOW,
    ActionEnum.RETRY_DELAYED,
    ActionEnum.REQUEST_PAYMENT_METHOD_UPDATE,
    ActionEnum.SEND_RECOVERY_LINK,
]


@pytest.mark.parametrize("action", RETRY_ACTIONS)
def test_high_value_blocks_any_payment_action(action):
    """No payment action should pass for amounts over the auto-approval limit."""
    inp = PolicyInput(
        case_id="g1",
        case_type=CaseType.PAYMENT_FAILURE,
        failure_reason="TEMPORARY_FAILURE",
        retry_count=0,
        amount=settings.max_auto_approved_amount + 10000,
        recovery_probability=0.95,
        recommended_action=action,
        contacts_last_24h=0,
    )
    out = decide(inp)
    assert out.blocked
    assert out.approved_action == ActionEnum.ESCALATE_TO_HUMAN


def test_retry_count_at_limit_blocks():
    inp = PolicyInput(
        case_id="g2",
        case_type=CaseType.PAYMENT_FAILURE,
        failure_reason="TEMPORARY_FAILURE",
        retry_count=settings.max_retries_per_transaction,
        amount=500.0,
        recovery_probability=0.99,
        recommended_action=ActionEnum.RETRY_NOW,
        contacts_last_24h=0,
    )
    out = decide(inp)
    assert out.blocked


def test_retry_count_below_limit_passes():
    inp = PolicyInput(
        case_id="g3",
        case_type=CaseType.PAYMENT_FAILURE,
        failure_reason="TEMPORARY_FAILURE",
        retry_count=settings.max_retries_per_transaction - 1,
        amount=500.0,
        recovery_probability=0.80,
        recommended_action=ActionEnum.RETRY_DELAYED,
        contacts_last_24h=0,
    )
    out = decide(inp)
    assert not out.blocked


def test_contacts_at_limit_blocks():
    inp = PolicyInput(
        case_id="g4",
        case_type=CaseType.PAYMENT_FAILURE,
        failure_reason="TEMPORARY_FAILURE",
        retry_count=0,
        amount=500.0,
        recovery_probability=0.80,
        recommended_action=ActionEnum.SEND_RECOVERY_LINK,
        contacts_last_24h=settings.max_contacts_per_24h,
    )
    out = decide(inp)
    assert out.blocked


def test_guardrail_check_is_independent_of_llm_output():
    """
    CRITICAL: The LLM's raw recommended_action must never reach the executor
    if a guardrail is violated. This test proves the block fires before the
    recommended_action is used.
    """
    for action in RETRY_ACTIONS:
        inp = PolicyInput(
            case_id="g5",
            case_type=CaseType.PAYMENT_FAILURE,
            failure_reason="TEMPORARY_FAILURE",
            retry_count=settings.max_retries_per_transaction + 10,
            amount=500.0,
            recovery_probability=1.0,
            recommended_action=action,
            contacts_last_24h=0,
        )
        guard_out = _check_guardrails(inp)
        assert guard_out.blocked, f"Guardrail should block action={action} with excessive retries"
        assert guard_out.approved_action != action, "Guardrail must override LLM action"
