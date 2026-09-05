"""Pydantic schemas for API I/O and internal pipeline contracts."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator
from .models import CaseType, CaseStatus, ActionEnum, FailureReason


# ── Diagnosis Agent output schema (strict — LLM must match this) ────────────

VALID_ACTIONS = {a.value for a in ActionEnum}


class DiagnosisOutput(BaseModel):
    diagnosis: str = Field(..., min_length=1)
    recovery_probability: float = Field(..., ge=0.0, le=1.0)
    recommended_action: ActionEnum
    reasoning: str = Field(..., min_length=1)
    is_fallback: bool = False

    @field_validator("recommended_action", mode="before")
    @classmethod
    def validate_action(cls, v: Any) -> ActionEnum:
        if v not in VALID_ACTIONS and v not in ActionEnum.__members__:
            raise ValueError(f"Invalid action '{v}'. Must be one of: {VALID_ACTIONS}")
        return v


# ── Policy Engine I/O ────────────────────────────────────────────────────────

class PolicyInput(BaseModel):
    case_id: str
    case_type: CaseType
    failure_reason: Optional[str]
    retry_count: int
    amount: float
    recovery_probability: float
    recommended_action: ActionEnum
    contacts_last_24h: int = 0


class PolicyOutput(BaseModel):
    approved_action: ActionEnum
    overridden: bool = False
    override_reason: Optional[str] = None
    blocked: bool = False
    block_reason: Optional[str] = None


# ── Case schemas ─────────────────────────────────────────────────────────────

class AuditEventOut(BaseModel):
    id: int
    case_id: str
    timestamp: datetime
    event_type: str
    details: str

    model_config = {"from_attributes": True}


class CaseOut(BaseModel):
    case_id: str
    case_type: CaseType
    transaction_id: Optional[str]
    customer_id: str
    amount: float
    failure_reason: Optional[str]
    retry_count: int
    status: CaseStatus
    diagnosis: Optional[str]
    recovery_probability: Optional[float]
    recommended_action: Optional[ActionEnum]
    reasoning: Optional[str]
    approved_action: Optional[ActionEnum]
    guardrail_override: bool
    guardrail_reason: Optional[str]
    razorpay_order_id: Optional[str]
    razorpay_payment_id: Optional[str]
    payment_link_url: Optional[str] = None
    promise_date: Optional[datetime] = None
    promise_note: Optional[str] = None
    customer_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    audit_events: List[AuditEventOut] = []

    model_config = {"from_attributes": True}


# ── Analytics schema ─────────────────────────────────────────────────────────

class AnalyticsSummary(BaseModel):
    total_cases: int
    open_cases: int
    recovered_cases: int
    failed_cases: int
    escalated_cases: int
    promised_cases: int = 0
    total_revenue_at_risk: float
    total_revenue_recovered: float
    recovery_rate: float
    avg_recovery_probability: float
    false_positive_count: int
    avg_recovery_time_seconds: Optional[float]
    gateway_penalties_prevented: float = 0.0
    net_roi_recovered: float = 0.0


class OutreachMessage(BaseModel):
    channel: str
    label: str
    content: str


class OutreachResponse(BaseModel):
    case_id: str
    customer_name: str
    amount: float
    messages: List[OutreachMessage]


class PromiseToPayRequest(BaseModel):
    promise_date: datetime
    note: Optional[str] = None


# ── Webhook payload schemas ───────────────────────────────────────────────────

class RazorpayWebhookPayload(BaseModel):
    event: str
    payload: dict


# ── Synthetic data generation request ────────────────────────────────────────

class GenerateDataRequest(BaseModel):
    count: int = Field(default=300, ge=10, le=1000)
    seed: Optional[int] = None
