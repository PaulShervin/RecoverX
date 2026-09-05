"""Tests for the heuristic recovery probability model."""
import pytest
from app.modules.recovery_model import score


def test_temporary_failure_high_probability():
    p = score("TEMPORARY_FAILURE", retry_count=0, previous_success_rate=0.95, total_transactions=10)
    assert p >= 0.75


def test_repeated_failure_low_probability():
    p = score("REPEATED_FAILURE", retry_count=3, previous_success_rate=0.50, total_transactions=5)
    assert p <= 0.20


def test_probability_clamps_to_zero():
    p = score("REPEATED_FAILURE", retry_count=10, previous_success_rate=0.10, total_transactions=2)
    assert p == 0.0


def test_probability_clamps_to_one():
    p = score("TEMPORARY_FAILURE", retry_count=0, previous_success_rate=1.0, total_transactions=20)
    assert p <= 1.0


def test_retry_penalty_reduces_probability():
    p0 = score("TEMPORARY_FAILURE", retry_count=0, previous_success_rate=0.85, total_transactions=10)
    p2 = score("TEMPORARY_FAILURE", retry_count=2, previous_success_rate=0.85, total_transactions=10)
    assert p0 > p2


def test_good_history_boosts_probability():
    p_good = score("INSUFFICIENT_FUNDS", retry_count=0, previous_success_rate=0.95, total_transactions=20)
    p_poor = score("INSUFFICIENT_FUNDS", retry_count=0, previous_success_rate=0.30, total_transactions=20)
    assert p_good > p_poor


def test_output_always_in_range():
    import random
    rng = random.Random(42)
    reasons = ["TEMPORARY_FAILURE", "INSUFFICIENT_FUNDS", "EXPIRED_CARD", "REPEATED_FAILURE", None]
    for _ in range(200):
        p = score(
            failure_reason=rng.choice(reasons),
            retry_count=rng.randint(0, 10),
            previous_success_rate=rng.random(),
            total_transactions=rng.randint(0, 50),
        )
        assert 0.0 <= p <= 1.0
