"""
Recovery Probability Model — rule-based heuristic v1.

This is explicitly a heuristic, NOT a trained ML model.
Disclosed as such in ARCHITECTURE.md §2.3 and the demo.
The scoring logic is transparent and each factor is documented.
"""
from ..models import FailureReason


# Base probability per failure reason (empirical estimates)
_BASE_PROB: dict[str, float] = {
    FailureReason.TEMPORARY_FAILURE.value: 0.82,
    FailureReason.INSUFFICIENT_FUNDS.value: 0.45,
    FailureReason.EXPIRED_CARD.value: 0.68,   # high if customer updates card
    FailureReason.PAYMENT_METHOD_INVALID.value: 0.35,
    FailureReason.CHECKOUT_ABANDONED.value: 0.38,
    FailureReason.SUBSCRIPTION_RENEWAL_FAILED.value: 0.55,
    FailureReason.OVERDUE_RECEIVABLE.value: 0.30,
    FailureReason.REPEATED_FAILURE.value: 0.12,
}

_DEFAULT_BASE = 0.40


def score(
    failure_reason: str | None,
    retry_count: int,
    previous_success_rate: float,
    total_transactions: int,
) -> float:
    """Return a recovery probability in [0, 1]."""
    base = _BASE_PROB.get(failure_reason or "", _DEFAULT_BASE)

    # Penalty: each additional retry reduces probability
    retry_penalty = min(retry_count * 0.12, 0.48)

    # Boost: loyal customers with good history are more likely to recover
    history_boost = 0.0
    if previous_success_rate >= 0.85 and total_transactions >= 5:
        history_boost = 0.10
    elif previous_success_rate >= 0.70:
        history_boost = 0.05
    elif previous_success_rate < 0.40:
        history_boost = -0.10

    prob = base - retry_penalty + history_boost
    return round(max(0.0, min(1.0, prob)), 4)
