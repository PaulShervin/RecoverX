"""
Razorpay Standard Checkout — create order + verify payment signature.
KEY_SECRET never leaves this module. Only KEY_ID is exposed to the frontend.
"""
import hashlib
import hmac
import logging
from typing import Optional
import razorpay
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import Case, CaseStatus
from ..modules.outcome_tracker import mark_recovered

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


def _client():
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


class CreateOrderRequest(BaseModel):
    amount: int = Field(..., ge=100, description="Amount in paise (min ₹1 = 100 paise)")
    currency: str = "INR"
    receipt: str = Field(default="receipt", max_length=40)
    case_id: Optional[str] = None


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str


@router.post("/create-order", response_model=CreateOrderResponse)
def create_order(req: CreateOrderRequest, db: Session = Depends(get_db)):
    try:
        order = _client().order.create({
            "amount": req.amount,
            "currency": req.currency,
            "receipt": req.receipt,
        })
        # Link order to case so webhook can find it later
        if req.case_id:
            case = db.query(Case).filter_by(case_id=req.case_id).first()
            if case and case.status != CaseStatus.RECOVERED:
                case.razorpay_order_id = order["id"]
                db.commit()
        return CreateOrderResponse(
            order_id=order["id"],
            amount=order["amount"],
            currency=order["currency"],
        )
    except razorpay.errors.BadRequestError as e:
        raise HTTPException(status_code=400, detail=f"Invalid order request: {e}")
    except Exception as e:
        logger.error("Razorpay order creation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Order creation failed: {e}")


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    case_id: Optional[str] = None


@router.post("/verify")
def verify_payment(req: VerifyRequest, db: Session = Depends(get_db)):
    if not req.razorpay_order_id or not req.razorpay_payment_id or not req.razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing required fields")

    message = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
    expected = hmac.new(
        settings.razorpay_key_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, req.razorpay_signature):
        logger.warning("Signature mismatch for order %s", req.razorpay_order_id)
        raise HTTPException(status_code=400, detail="Signature verification failed")

    # Signature valid — find and recover the case in DB
    case = (
        db.query(Case).filter_by(case_id=req.case_id).first()
        if req.case_id
        else db.query(Case).filter_by(razorpay_order_id=req.razorpay_order_id).first()
    )
    if case and case.status != CaseStatus.RECOVERED:
        mark_recovered(case, req.razorpay_payment_id, db)

    return {"verified": True, "payment_id": req.razorpay_payment_id}
