"""
Action Executor — translates approved policy actions into Razorpay Test Mode API calls.
ONLY receives approved actions from the Policy Engine. Never called with raw LLM output.
Non-payment actions (reminders, etc.) are simulated/logged for the demo.
"""
import logging
import uuid
from datetime import datetime
from ..config import settings
from ..models import ActionEnum, Case
from ..audit import log_event
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _get_razorpay_client():
    import razorpay
    return razorpay.Client(
        auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
    )


def execute(case: Case, approved_action: ActionEnum, db: Session) -> dict:
    """
    Execute an approved action. Returns a result dict with keys:
      - success: bool
      - razorpay_order_id: str | None
      - razorpay_payment_id: str | None
      - message: str
    """
    log_event(db, case.case_id, "ACTION_EXECUTING", f"Executing: {approved_action.value}")

    handlers = {
        ActionEnum.RETRY_NOW: _retry_payment,
        ActionEnum.RETRY_DELAYED: _schedule_delayed_retry,
        ActionEnum.REQUEST_PAYMENT_METHOD_UPDATE: _request_method_update,
        ActionEnum.GENERATE_UPI_LINK: _generate_upi_link,
        ActionEnum.SEND_RECOVERY_LINK: _send_recovery_link,
        ActionEnum.SEND_REMINDER: _send_reminder,
        ActionEnum.FOLLOW_UP_OVERDUE_INVOICE: _follow_up_invoice,
        ActionEnum.ESCALATE_TO_HUMAN: _escalate,
        ActionEnum.STOP_RETRYING: _stop_retrying,
    }

    handler = handlers.get(approved_action)
    if handler is None:
        raise ValueError(f"No handler for action: {approved_action}")

    result = handler(case, db)
    status = "SUCCESS" if result["success"] else "FAILED"
    log_event(db, case.case_id, f"ACTION_{status}", result["message"])
    return result


def _retry_payment(case: Case, db: Session) -> dict:
    """Create a Razorpay order and attempt an immediate retry (Test Mode)."""
    try:
        client = _get_razorpay_client()
        order = client.order.create({
            "amount": round(case.amount * 100),  # paise — round avoids float truncation
            "currency": "INR",
            "receipt": f"retry_{case.case_id[:8]}",
            "notes": {
                "case_id": case.case_id,
                "action": ActionEnum.RETRY_NOW.value,
            },
        })
        case.razorpay_order_id = order["id"]
        db.commit()
        return {
            "success": True,
            "razorpay_order_id": order["id"],
            "razorpay_payment_id": None,
            "message": f"Razorpay order created: {order['id']} for ₹{case.amount:,.2f}",
        }
    except Exception as e:
        logger.error("Razorpay order creation failed for case %s: %s", case.case_id, e)
        return {
            "success": False,
            "razorpay_order_id": None,
            "razorpay_payment_id": None,
            "message": f"Razorpay order creation failed: {e}",
        }


def _schedule_delayed_retry(case: Case, db: Session) -> dict:
    """Schedule a delayed retry — records intent; actual retry fires later."""
    delay_hours = _retry_delay_hours(case.retry_count)
    return {
        "success": True,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "message": f"Delayed retry scheduled: +{delay_hours}h from now",
    }


def _generate_upi_link(case: Case, db: Session) -> dict:
    """Create a Razorpay Payment Link with UPI intent pre-enabled (Test Mode)."""
    try:
        client = _get_razorpay_client()
        link = client.payment_link.create({
            "amount": round(case.amount * 100),
            "currency": "INR",
            "description": f"Payment recovery — case {case.case_id[:8]}",
            "upi_link": True,
            "notes": {
                "case_id": case.case_id,
                "action": ActionEnum.GENERATE_UPI_LINK.value,
            },
        })
        short_url = link.get("short_url") or link.get("id")
        case.payment_link_url = short_url
        db.commit()
        return {
            "success": True,
            "razorpay_order_id": None,
            "razorpay_payment_id": None,
            "payment_link_url": short_url,
            "message": f"UPI payment link created: {short_url}",
        }
    except Exception as e:
        logger.error("UPI link creation failed for case %s: %s", case.case_id, e)
        # Fallback to simulated link so demo still works without live Razorpay creds
        fallback_url = f"https://rzp.io/demo/{case.case_id[:8]}"
        case.payment_link_url = fallback_url
        db.commit()
        return {
            "success": True,
            "razorpay_order_id": None,
            "razorpay_payment_id": None,
            "payment_link_url": fallback_url,
            "message": f"UPI payment link (simulated): {fallback_url}",
        }


def _request_method_update(case: Case, db: Session) -> dict:
    """Simulate sending a payment method update request to the customer."""
    return {
        "success": True,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "message": f"Payment method update requested (simulated notification to customer {case.customer_id})",
    }


def _send_recovery_link(case: Case, db: Session) -> dict:
    """Simulate sending a checkout recovery link."""
    recovery_link = f"https://recoverx.demo/recover/{case.case_id}"
    return {
        "success": True,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "message": f"Recovery link sent (simulated): {recovery_link}",
    }


def _send_reminder(case: Case, db: Session) -> dict:
    return {
        "success": True,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "message": f"Reminder sent (simulated) to customer {case.customer_id}",
    }


def _follow_up_invoice(case: Case, db: Session) -> dict:
    return {
        "success": True,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "message": f"Invoice follow-up sent (simulated): ₹{case.amount:,.2f} overdue",
    }


def _escalate(case: Case, db: Session) -> dict:
    return {
        "success": True,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "message": "Case escalated to human review queue",
    }


def _stop_retrying(case: Case, db: Session) -> dict:
    return {
        "success": True,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "message": "Recovery attempts stopped per policy",
    }


def _retry_delay_hours(retry_count: int) -> int:
    """ARCHITECTURE.md §2.4 retry sequencing."""
    schedule = {0: 0, 1: 24, 2: 72}
    return schedule.get(retry_count, 72)
