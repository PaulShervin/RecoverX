"""
Razorpay webhook handler.
- Verifies HMAC-SHA256 signature before trusting any payload.
- Idempotent: duplicate deliveries are silently skipped.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..config import settings
from ..models import WebhookEvent, Case, CaseStatus
from ..modules.outcome_tracker import mark_recovered, mark_failed
from ..audit import log_event

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not _verify_signature(body, signature):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id = payload.get("event_id") or payload.get("id", "")
    event_type = payload.get("event", "")

    # Idempotency check — skip duplicates
    existing = db.query(WebhookEvent).filter_by(event_id=event_id).first()
    if existing and existing.processed:
        logger.info("Duplicate webhook ignored: %s", event_id)
        return {"status": "already_processed"}

    # Persist webhook event
    if not existing:
        wh = WebhookEvent(
            event_id=event_id or f"unknown_{datetime.now(timezone.utc).timestamp()}",
            event_type=event_type,
            payload=payload,
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(wh)
        db.flush()
    else:
        wh = existing

    # Route to handler
    try:
        _route_event(event_type, payload, db)
        wh.processed = True
        wh.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    except Exception as e:
        logger.error("Webhook processing error: %s", e, exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Processing error")

    return {"status": "ok"}


def _route_event(event_type: str, payload: dict, db: Session) -> None:
    if event_type in ("payment.captured", "order.paid"):
        _handle_payment_captured(payload, db)
    elif event_type == "payment.failed":
        _handle_payment_failed(payload, db)
    else:
        logger.debug("Unhandled webhook event type: %s", event_type)


def _handle_payment_captured(payload: dict, db: Session) -> None:
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = payment.get("order_id")
    payment_id = payment.get("id")

    if not order_id:
        return

    case = db.query(Case).filter_by(razorpay_order_id=order_id).first()
    if not case:
        logger.warning("No case found for order_id %s", order_id)
        return

    if case.status == CaseStatus.RECOVERED:
        return  # already processed

    log_event(db, case.case_id, "WEBHOOK_RECEIVED", f"payment.captured | payment_id={payment_id}")
    mark_recovered(case, payment_id, db)


def _handle_payment_failed(payload: dict, db: Session) -> None:
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = payment.get("order_id")
    error_desc = payment.get("error_description", "payment failed")

    if not order_id:
        return

    case = db.query(Case).filter_by(razorpay_order_id=order_id).first()
    if not case or case.status != CaseStatus.OPEN:
        return

    # Only permanently fail the case once max retries are exhausted
    if case.retry_count >= settings.max_retries_per_transaction:
        log_event(db, case.case_id, "WEBHOOK_RECEIVED",
                  f"payment.failed | reason={error_desc} | max retries reached")
        mark_failed(case, error_desc, db)
    else:
        case.retry_count += 1
        log_event(db, case.case_id, "WEBHOOK_RECEIVED",
                  f"payment.failed | reason={error_desc} | retry {case.retry_count}/{settings.max_retries_per_transaction}")
        db.commit()
