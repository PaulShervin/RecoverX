"""Analytics API — all metrics computed from real logged case data."""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Case, CaseStatus, ActionEnum
from ..schemas import AnalyticsSummary

_GATEWAY_PENALTY_PER_RETRY = 25.0  # ₹ estimated fee per doomed retry stopped
_INTERVENTION_COST_PER_CASE = 5.0  # ₹ estimated processing cost per case

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(db: Session = Depends(get_db)):
    cases = db.query(Case).all()

    total = len(cases)
    open_c = sum(1 for c in cases if c.status == CaseStatus.OPEN)
    recovered = [c for c in cases if c.status == CaseStatus.RECOVERED]
    failed_c = sum(1 for c in cases if c.status == CaseStatus.FAILED)
    escalated = sum(1 for c in cases if c.status == CaseStatus.ESCALATED)
    promised = sum(1 for c in cases if c.status == CaseStatus.PROMISED_TO_PAY)

    revenue_at_risk = sum(c.amount for c in cases)
    revenue_recovered = sum(c.amount for c in recovered)
    recovery_rate = revenue_recovered / revenue_at_risk * 100 if revenue_at_risk > 0 else 0.0

    probs = [c.recovery_probability for c in cases if c.recovery_probability is not None]
    avg_prob = sum(probs) / len(probs) if probs else 0.0

    # False positives: cases flagged as high-probability (≥50%) but FAILED
    false_positives = sum(
        1 for c in cases
        if c.status == CaseStatus.FAILED and c.recovery_probability and c.recovery_probability >= 0.5
    )

    # Average recovery time
    times = []
    for c in recovered:
        if c.resolved_at and c.created_at:
            times.append((c.resolved_at - c.created_at).total_seconds())
    avg_time = sum(times) / len(times) if times else None

    # Gateway penalties prevented: cases where STOP_RETRYING was approved
    # and recovery_probability < 0.15 (doomed retries stopped)
    stopped_doomed = sum(
        1 for c in cases
        if c.approved_action == ActionEnum.STOP_RETRYING
        and c.recovery_probability is not None
        and c.recovery_probability < 0.15
    )
    gateway_penalties_prevented = round(stopped_doomed * _GATEWAY_PENALTY_PER_RETRY, 2)

    # Net ROI = revenue recovered + penalties prevented - intervention costs
    total_interventions = sum(
        1 for c in cases if c.approved_action is not None
    )
    net_roi = round(
        revenue_recovered + gateway_penalties_prevented
        - (total_interventions * _INTERVENTION_COST_PER_CASE),
        2,
    )

    return AnalyticsSummary(
        total_cases=total,
        open_cases=open_c,
        recovered_cases=len(recovered),
        failed_cases=failed_c,
        escalated_cases=escalated,
        promised_cases=promised,
        total_revenue_at_risk=round(revenue_at_risk, 2),
        total_revenue_recovered=round(revenue_recovered, 2),
        recovery_rate=round(recovery_rate, 2),
        avg_recovery_probability=round(avg_prob, 4),
        false_positive_count=false_positives,
        avg_recovery_time_seconds=round(avg_time, 1) if avg_time else None,
        gateway_penalties_prevented=gateway_penalties_prevented,
        net_roi_recovered=net_roi,
    )


@router.get("/by-case-type")
def by_case_type(db: Session = Depends(get_db)):
    rows = (
        db.query(Case.case_type, Case.status, func.count(Case.case_id), func.sum(Case.amount))
        .group_by(Case.case_type, Case.status)
        .all()
    )
    result: dict = {}
    for case_type, status, count, total in rows:
        key = case_type.value if hasattr(case_type, "value") else str(case_type)
        if key not in result:
            result[key] = {}
        result[key][status.value if hasattr(status, "value") else str(status)] = {
            "count": count,
            "amount": round(total or 0, 2),
        }
    return result


@router.get("/by-action")
def by_action(db: Session = Depends(get_db)):
    rows = (
        db.query(Case.approved_action, func.count(Case.case_id), func.sum(Case.amount))
        .filter(Case.approved_action.isnot(None))
        .group_by(Case.approved_action)
        .all()
    )
    return [
        {
            "action": a.value if hasattr(a, "value") else str(a),
            "count": c,
            "total_amount": round(t or 0, 2),
        }
        for a, c, t in rows
    ]
