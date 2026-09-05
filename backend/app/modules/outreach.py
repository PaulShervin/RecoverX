"""
Outreach Generator — produces contextual recovery copies for WhatsApp (Hinglish),
professional SMS/Email (English), and AI voice call script (Hinglish).
Pure function; no LLM calls, no side effects.
"""
from ..models import Case, CaseType


_PAY_URL_BASE = "https://recoverx.demo/pay"


def generate_outreach(case: Case, customer_name: str) -> list[dict]:
    """Return 3 recovery message dicts for the given case."""
    name = customer_name or "Customer"
    amt = f"₹{case.amount:,.0f}"
    pay_url = f"{_PAY_URL_BASE}/{case.case_id}"
    reason = case.failure_reason or "unknown reason"
    upi_url = case.payment_link_url or pay_url

    whatsapp = _whatsapp(case, name, amt, upi_url, reason)
    email = _email(case, name, amt, pay_url, reason)
    voice = _voice(case, name, amt, pay_url, reason)

    return [whatsapp, email, voice]


def _whatsapp(case: Case, name: str, amt: str, pay_url: str, reason: str) -> dict:
    first = name.split()[0]

    if case.case_type == CaseType.CHECKOUT_ABANDONED:
        content = (
            f"Namaste {first}! 🙏\n\n"
            f"Aapne {amt} ka order almost complete kar liya tha — bas ek step baaki hai!\n\n"
            f"Yahan click karke abhi complete karein: {pay_url}\n\n"
            f"Koi bhi problem ho toh reply karein, hum help karenge. 😊"
        )
    elif case.case_type == CaseType.SUBSCRIPTION_RENEWAL_FAILED:
        content = (
            f"Hi {first}! 👋\n\n"
            f"Aapki subscription renew nahi ho payi ({amt}). Aapka access band ho sakta hai.\n\n"
            f"Payment abhi karein: {pay_url}\n\n"
            f"UPI se sirf 10 seconds mein ho jayega! ⚡"
        )
    else:
        content = (
            f"Namaste {first}! 🙏\n\n"
            f"Aapka {amt} ka payment hold par hai. Reason: {_reason_hindi(reason)}\n\n"
            f"Ek click mein UPI se complete karein: {pay_url}\n\n"
            f"Safe & secure — Razorpay powered. 🔒"
        )

    return {"channel": "whatsapp", "label": "WhatsApp (Hinglish)", "content": content}


def _email(case: Case, name: str, amt: str, pay_url: str, reason: str) -> dict:
    if case.case_type == CaseType.CHECKOUT_ABANDONED:
        subject = f"Complete your order — {amt} is waiting"
        body = (
            f"Dear {name},\n\n"
            f"We noticed you left {amt} in your cart. Your items are reserved for a limited time.\n\n"
            f"Complete your purchase here: {pay_url}\n\n"
            f"If you faced any issues during checkout, our support team is ready to assist.\n\n"
            f"Best regards,\nRecoverX Team"
        )
    elif case.case_type == CaseType.SUBSCRIPTION_RENEWAL_FAILED:
        subject = f"Action required: Subscription renewal failed — {amt}"
        body = (
            f"Dear {name},\n\n"
            f"Your subscription renewal of {amt} could not be processed.\n"
            f"Reason: {reason.replace('_', ' ').title()}\n\n"
            f"To avoid service interruption, please update your payment method and renew here: {pay_url}\n\n"
            f"Best regards,\nRecoverX Team"
        )
    else:
        subject = f"Payment recovery required — {amt}"
        body = (
            f"Dear {name},\n\n"
            f"A payment of {amt} could not be processed.\n"
            f"Reason: {reason.replace('_', ' ').title()}\n\n"
            f"Please complete your payment at your earliest convenience: {pay_url}\n\n"
            f"Best regards,\nRecoverX Team"
        )

    return {
        "channel": "email",
        "label": "Email / SMS (English)",
        "content": f"Subject: {subject}\n\n{body}",
    }


def _voice(case: Case, name: str, amt: str, pay_url: str, reason: str) -> dict:
    first = name.split()[0]
    script = (
        f"[OPENING]\n"
        f"Namaste, main RecoverX se bol raha hoon. Kya main {first} ji se baat kar sakta hoon?\n\n"
        f"[EMPATHY]\n"
        f"Ji, bilkul. {first} ji, main samajh sakta hoon ki kabhi kabhi payments mein technical "
        f"problems aa jaati hain. Koi baat nahi.\n\n"
        f"[EXPLANATION]\n"
        f"Aapka {amt} ka payment process nahi ho paya — reason tha: {_reason_hindi(reason)}. "
        f"Iska matlab yeh nahi ki aapke account mein koi problem hai.\n\n"
        f"[UPI CTA]\n"
        f"Main aapko ek secure UPI payment link SMS kar raha hoon. "
        f"Bas apna UPI app open karein aur us link se {amt} complete karein — "
        f"sirf 10 seconds lagenge.\n\n"
        f"[CLOSE]\n"
        f"Kya aap abhi complete karna chahenge? Ya main aapko thodi der baad call karun?\n"
        f"Payment link: {pay_url}\n"
        f"Dhanyawad aur aapka din shubh ho! 🙏"
    )

    return {"channel": "voice", "label": "Voice Call Script (Hinglish)", "content": script}


def _reason_hindi(reason: str) -> str:
    mapping = {
        "EXPIRED_CARD": "card ki expiry date nikal gayi",
        "INSUFFICIENT_FUNDS": "account mein balance kam tha",
        "PAYMENT_METHOD_INVALID": "payment method valid nahi tha",
        "TEMPORARY_FAILURE": "ek temporary technical issue",
        "REPEATED_FAILURE": "repeated payment failure",
        "CHECKOUT_ABANDONED": "checkout incomplete raha",
        "SUBSCRIPTION_RENEWAL_FAILED": "subscription renew nahi hui",
        "OVERDUE_RECEIVABLE": "payment overdue ho gayi",
    }
    return mapping.get(reason, "ek technical issue")
