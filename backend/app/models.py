"""SQLAlchemy ORM models — source of truth for DB schema."""
import enum
from datetime import datetime, timezone


from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Enum as SAEnum,
    ForeignKey, JSON, Boolean, Text, Index
)
from sqlalchemy.orm import relationship
from .database import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CaseType(str, enum.Enum):
    PAYMENT_FAILURE = "PAYMENT_FAILURE"
    CHECKOUT_ABANDONED = "CHECKOUT_ABANDONED"
    SUBSCRIPTION_RENEWAL_FAILED = "SUBSCRIPTION_RENEWAL_FAILED"
    OVERDUE_RECEIVABLE = "OVERDUE_RECEIVABLE"


class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"
    PROMISED_TO_PAY = "PROMISED_TO_PAY"


class ActionEnum(str, enum.Enum):
    RETRY_NOW = "RETRY_NOW"
    RETRY_DELAYED = "RETRY_DELAYED"
    REQUEST_PAYMENT_METHOD_UPDATE = "REQUEST_PAYMENT_METHOD_UPDATE"
    GENERATE_UPI_LINK = "GENERATE_UPI_LINK"
    SEND_RECOVERY_LINK = "SEND_RECOVERY_LINK"
    SEND_REMINDER = "SEND_REMINDER"
    FOLLOW_UP_OVERDUE_INVOICE = "FOLLOW_UP_OVERDUE_INVOICE"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    STOP_RETRYING = "STOP_RETRYING"


class FailureReason(str, enum.Enum):
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    EXPIRED_CARD = "EXPIRED_CARD"
    PAYMENT_METHOD_INVALID = "PAYMENT_METHOD_INVALID"
    CHECKOUT_ABANDONED = "CHECKOUT_ABANDONED"
    SUBSCRIPTION_RENEWAL_FAILED = "SUBSCRIPTION_RENEWAL_FAILED"
    OVERDUE_RECEIVABLE = "OVERDUE_RECEIVABLE"
    REPEATED_FAILURE = "REPEATED_FAILURE"


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    previous_success_rate = Column(Float, nullable=False, default=1.0)
    payment_history = Column(JSON, nullable=False, default=list)
    total_transactions = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    cases = relationship("Case", back_populates="customer")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    payment_method = Column(String, nullable=False)
    payment_status = Column(String, nullable=False)
    failure_reason = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    subscription_status = Column(String, nullable=True)
    checkout_status = Column(String, nullable=True)
    days_overdue = Column(Integer, default=0)
    razorpay_order_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    timestamp = Column(DateTime, default=_utcnow)
    created_at = Column(DateTime, default=_utcnow)


class Case(Base):
    __tablename__ = "cases"

    case_id = Column(String, primary_key=True, index=True)
    case_type = Column(SAEnum(CaseType), nullable=False)
    transaction_id = Column(String, ForeignKey("transactions.transaction_id"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    amount = Column(Float, nullable=False)
    failure_reason = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    status = Column(SAEnum(CaseStatus), default=CaseStatus.OPEN, nullable=False)

    # AI outputs
    diagnosis = Column(Text, nullable=True)
    recovery_probability = Column(Float, nullable=True)
    recommended_action = Column(SAEnum(ActionEnum), nullable=True)
    reasoning = Column(Text, nullable=True)

    # Policy engine output
    approved_action = Column(SAEnum(ActionEnum), nullable=True)
    guardrail_override = Column(Boolean, default=False)
    guardrail_reason = Column(Text, nullable=True)

    # Razorpay
    razorpay_order_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    payment_link_url = Column(String, nullable=True)

    # Promise-to-Pay
    promise_date = Column(DateTime, nullable=True)
    promise_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    resolved_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="cases")
    audit_events = relationship("AuditEvent", back_populates="case", order_by="AuditEvent.timestamp")

    @property
    def customer_name(self) -> str | None:
        return self.customer.name if self.customer else None

    __table_args__ = (
        Index("ix_cases_status", "status"),
        Index("ix_cases_customer_id", "customer_id"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String, ForeignKey("cases.case_id"), nullable=False)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    event_type = Column(String, nullable=False)
    details = Column(Text, nullable=False)

    case = relationship("Case", back_populates="audit_events")

    __table_args__ = (
        Index("ix_audit_case_id", "case_id"),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, unique=True, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    received_at = Column(DateTime, default=_utcnow)
    processed_at = Column(DateTime, nullable=True)
