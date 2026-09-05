"""
Policy Engine — pure deterministic function. No LLM, no side effects.
Input: (diagnosis, probability, case data) → approved action.
This is the ONLY thing that can approve an action for execution.
"""
from ..models import ActionEnum, CaseType, FailureReason
from ..schemas import PolicyInput, PolicyOutput
from ..config import settings


def decide(inp: PolicyInput) -> PolicyOutput:
    """
    Deterministic policy decision. Guardrails are checked FIRST (hard blocks),
    then the policy table maps failure reason → action.
    """
    # ── Guardrail hard-blocks (non-negotiable) ────────────────────────────────
    guard = _check_guardrails(inp)
    if guard.blocked:
        return guard

    # ── Low probability → stop retrying ──────────────────────────────────────
    if inp.recovery_probability < settings.stop_retry_probability_threshold:
        return PolicyOutput(
            approved_action=ActionEnum.STOP_RETRYING,
            overridden=inp.recommended_action != ActionEnum.STOP_RETRYING,
            override_reason=(
                f"Recovery probability {inp.recovery_probability:.0%} is below "
                f"threshold {settings.stop_retry_probability_threshold:.0%}"
            ),
        )

    # ── Policy table ──────────────────────────────────────────────────────────
    policy_action = _policy_table(inp)

    # Use LLM recommendation if it agrees with or is safer than policy table
    final_action = _resolve(inp.recommended_action, policy_action, inp)

    overridden = final_action != inp.recommended_action
    return PolicyOutput(
        approved_action=final_action,
        overridden=overridden,
        override_reason=f"Policy table mapped to {policy_action.value}" if overridden else None,
    )


def _check_guardrails(inp: PolicyInput) -> PolicyOutput:
    """Hard limits — block and escalate if any are violated."""

    # Max retries
    if inp.retry_count >= settings.max_retries_per_transaction:
        return PolicyOutput(
            approved_action=ActionEnum.ESCALATE_TO_HUMAN,
            blocked=True,
            block_reason=(
                f"Max retries exceeded: {inp.retry_count} >= "
                f"{settings.max_retries_per_transaction}"
            ),
        )

    # Max contacts per 24h
    if inp.contacts_last_24h >= settings.max_contacts_per_24h:
        return PolicyOutput(
            approved_action=ActionEnum.STOP_RETRYING,
            blocked=True,
            block_reason=(
                f"Max contacts/24h exceeded: {inp.contacts_last_24h} >= "
                f"{settings.max_contacts_per_24h}"
            ),
        )

    # High-value auto-approval limit
    contact_actions = {
        ActionEnum.RETRY_NOW,
        ActionEnum.RETRY_DELAYED,
        ActionEnum.REQUEST_PAYMENT_METHOD_UPDATE,
        ActionEnum.SEND_RECOVERY_LINK,
    }
    if (
        inp.amount > settings.max_auto_approved_amount
        and inp.recommended_action in contact_actions
    ):
        return PolicyOutput(
            approved_action=ActionEnum.ESCALATE_TO_HUMAN,
            blocked=True,
            block_reason=(
                f"Amount ₹{inp.amount:,.2f} exceeds auto-approval limit "
                f"₹{settings.max_auto_approved_amount:,.2f}"
            ),
        )

    return PolicyOutput(approved_action=inp.recommended_action, blocked=False)


def _policy_table(inp: PolicyInput) -> ActionEnum:
    """
    Deterministic mapping: failure reason + case type → action.
    Mirrors ARCHITECTURE.md §2.4 policy table exactly.
    """
    reason = inp.failure_reason or ""

    if reason == FailureReason.TEMPORARY_FAILURE.value:
        return ActionEnum.RETRY_DELAYED

    if reason == FailureReason.INSUFFICIENT_FUNDS.value:
        return ActionEnum.GENERATE_UPI_LINK

    if reason == FailureReason.EXPIRED_CARD.value:
        return ActionEnum.GENERATE_UPI_LINK

    if reason == FailureReason.PAYMENT_METHOD_INVALID.value:
        return ActionEnum.GENERATE_UPI_LINK

    if reason == FailureReason.REPEATED_FAILURE.value or inp.retry_count >= 3:
        return ActionEnum.ESCALATE_TO_HUMAN

    if inp.case_type == CaseType.CHECKOUT_ABANDONED:
        return ActionEnum.SEND_RECOVERY_LINK

    if inp.case_type == CaseType.SUBSCRIPTION_RENEWAL_FAILED:
        return ActionEnum.REQUEST_PAYMENT_METHOD_UPDATE

    if inp.case_type == CaseType.OVERDUE_RECEIVABLE:
        return ActionEnum.FOLLOW_UP_OVERDUE_INVOICE

    # Default: retry with delay
    return ActionEnum.RETRY_DELAYED


def _resolve(recommended: ActionEnum, policy: ActionEnum, inp: PolicyInput) -> ActionEnum:
    """
    If LLM recommendation is ESCALATE_TO_HUMAN or STOP_RETRYING, honour it
    (conservative). Otherwise use policy table result.
    """
    conservative = {ActionEnum.ESCALATE_TO_HUMAN, ActionEnum.STOP_RETRYING}
    if recommended in conservative:
        return recommended
    return policy
