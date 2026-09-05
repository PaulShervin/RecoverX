"""
Synthetic dataset generator — 300 realistic transaction/customer records.
Distributions are intentionally realistic, not uniform:
  - ~70% successful payments
  - Failures cluster on TEMPORARY_FAILURE and INSUFFICIENT_FUNDS
  - A small fraction of customers have poor payment history
Run: python -m data.generate_synthetic [--count N] [--seed S]
"""
import argparse
import json
import random
import sys
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal, init_db
from app.models import Customer, Transaction


# ── Realistic distributions ───────────────────────────────────────────────────

PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet", "emi"]
PAYMENT_METHOD_WEIGHTS = [0.45, 0.30, 0.12, 0.08, 0.05]

FAILURE_REASONS = [
    "TEMPORARY_FAILURE",
    "INSUFFICIENT_FUNDS",
    "EXPIRED_CARD",
    "PAYMENT_METHOD_INVALID",
    "REPEATED_FAILURE",
]
FAILURE_WEIGHTS = [0.38, 0.28, 0.18, 0.10, 0.06]

AMOUNT_RANGES = [
    (199, 999, 0.30),
    (1000, 4999, 0.40),
    (5000, 19999, 0.20),
    (20000, 99999, 0.10),
]

INDIAN_FIRST_NAMES = [
    "Aarav", "Aditya", "Akash", "Amit", "Ananya", "Anjali", "Arjun", "Deepak",
    "Divya", "Gaurav", "Kavita", "Kiran", "Manish", "Meera", "Neha", "Nikhil",
    "Pooja", "Priya", "Rahul", "Rajesh", "Ravi", "Rohit", "Sachin", "Sanjay",
    "Shreya", "Siddharth", "Sneha", "Suresh", "Tanvi", "Vikram", "Vikas", "Zara",
]
INDIAN_LAST_NAMES = [
    "Agarwal", "Bhat", "Chandra", "Desai", "Gupta", "Iyer", "Jain", "Kapoor",
    "Kumar", "Mehta", "Mishra", "Nair", "Patel", "Rao", "Sharma", "Singh",
    "Srinivasan", "Thakur", "Verma", "Yadav",
]


def _random_amount(rng: random.Random) -> float:
    ranges, weights = zip(*[(r[:2], r[2]) for r in AMOUNT_RANGES])
    chosen = rng.choices(ranges, weights=weights)[0]
    return round(rng.uniform(*chosen), 2)


def _make_customer(rng: random.Random) -> dict:
    first = rng.choice(INDIAN_FIRST_NAMES)
    last = rng.choice(INDIAN_LAST_NAMES)
    name = f"{first} {last}"
    email = f"{first.lower()}.{last.lower()}{rng.randint(1, 999)}@example.com"
    phone = f"+91 9{rng.randint(100000000, 999999999)}"

    # Most customers have good history; ~15% have mediocre history
    if rng.random() < 0.70:
        success_rate = rng.uniform(0.85, 1.0)
    elif rng.random() < 0.50:
        success_rate = rng.uniform(0.60, 0.85)
    else:
        success_rate = rng.uniform(0.20, 0.60)

    total_tx = rng.randint(1, 50)
    history = _make_history(rng, total_tx, success_rate)

    return {
        "customer_id": f"cust_{uuid.uuid4().hex[:10]}",
        "name": name,
        "email": email,
        "phone": phone,
        "previous_success_rate": round(success_rate, 3),
        "payment_history": history,
        "total_transactions": total_tx,
    }


def _make_history(rng: random.Random, total: int, rate: float) -> list:
    outcomes = []
    for i in range(min(total, 10)):
        outcomes.append({
            "date": (datetime.utcnow() - timedelta(days=rng.randint(1, 365))).isoformat(),
            "status": "success" if rng.random() < rate else "failed",
            "amount": round(rng.uniform(200, 10000), 2),
        })
    return outcomes


def _make_transaction(rng: random.Random, customer_id: str) -> dict:
    method = rng.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS)[0]
    amount = _random_amount(rng)

    # ~72% succeed
    is_success = rng.random() < 0.72

    if is_success:
        status = "captured"
        failure_reason = None
        retry_count = 0
        checkout_status = None
        subscription_status = None
        days_overdue = 0
    else:
        # Choose scenario
        scenario = rng.choices(
            ["payment_failed", "checkout_abandoned", "subscription_failed", "overdue"],
            weights=[0.60, 0.20, 0.12, 0.08],
        )[0]

        if scenario == "payment_failed":
            status = "failed"
            failure_reason = rng.choices(FAILURE_REASONS, weights=FAILURE_WEIGHTS)[0]
            retry_count = rng.choices([0, 1, 2, 3], weights=[0.55, 0.25, 0.12, 0.08])[0]
            checkout_status = None
            subscription_status = None
            days_overdue = 0
        elif scenario == "checkout_abandoned":
            status = "created"
            failure_reason = "CHECKOUT_ABANDONED"
            retry_count = 0
            checkout_status = "abandoned"
            subscription_status = None
            days_overdue = 0
        elif scenario == "subscription_failed":
            status = "failed"
            failure_reason = rng.choices(
                ["INSUFFICIENT_FUNDS", "EXPIRED_CARD", "TEMPORARY_FAILURE"],
                weights=[0.45, 0.35, 0.20],
            )[0]
            retry_count = rng.choices([0, 1], weights=[0.7, 0.3])[0]
            checkout_status = None
            subscription_status = "failed"
            days_overdue = 0
        else:  # overdue
            status = "pending"
            failure_reason = "OVERDUE_RECEIVABLE"
            retry_count = 0
            checkout_status = None
            subscription_status = None
            days_overdue = rng.randint(1, 60)

    created_at = datetime.utcnow() - timedelta(
        days=rng.randint(0, 30), hours=rng.randint(0, 23)
    )

    return {
        "transaction_id": f"tx_{uuid.uuid4().hex[:12]}",
        "customer_id": customer_id,
        "amount": amount,
        "currency": "INR",
        "payment_method": method,
        "payment_status": status,
        "failure_reason": failure_reason,
        "retry_count": retry_count,
        "subscription_status": subscription_status,
        "checkout_status": checkout_status,
        "days_overdue": days_overdue,
        "timestamp": created_at,
    }


def generate(count: int = 300, seed: int | None = None) -> tuple[list, list]:
    rng = random.Random(seed)

    # ~1 customer per 3 transactions on average
    n_customers = max(20, count // 3)
    customers = [_make_customer(rng) for _ in range(n_customers)]

    transactions = []
    for _ in range(count):
        cust = rng.choice(customers)
        transactions.append(_make_transaction(rng, cust["customer_id"]))

    return customers, transactions


def seed_database(count: int = 300, seed_val: int | None = None) -> dict:
    init_db()
    db = SessionLocal()
    try:
        customers, transactions = generate(count, seed_val)

        # Insert customers (skip duplicates)
        existing_ids = {r[0] for r in db.query(Customer.customer_id).all()}
        new_customers = 0
        for c in customers:
            if c["customer_id"] not in existing_ids:
                db.add(Customer(**c))
                new_customers += 1

        db.flush()

        # Insert transactions
        existing_tx = {r[0] for r in db.query(Transaction.transaction_id).all()}
        new_tx = 0
        for t in transactions:
            if t["transaction_id"] not in existing_tx:
                db.add(Transaction(**t))
                new_tx += 1

        db.commit()

        stats = {
            "customers_inserted": new_customers,
            "transactions_inserted": new_tx,
            "total_transactions": count,
        }
        print(f"Seeded: {stats}")
        return stats
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    seed_database(args.count, args.seed)
