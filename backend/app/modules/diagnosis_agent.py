"""
AI Diagnosis Agent — wraps Ollama LLM call, enforces fixed JSON schema.
The LLM only reasons; it never executes actions.
"""
import json
import logging
from typing import Optional
import httpx
from ..config import settings
from ..schemas import DiagnosisOutput, VALID_ACTIONS
from ..models import ActionEnum

logger = logging.getLogger(__name__)

def _build_heuristic_diagnosis(case_data: dict) -> DiagnosisOutput:
    """
    Intelligent domain heuristic diagnosis used when Ollama is offline or times out.
    Produces explainable diagnoses and sensible recovery recommendations instead of
    blindly escalating every case to human review.
    """
    reason = str(case_data.get("failure_reason") or "")
    case_type = str(case_data.get("case_type") or "")
    retry_count = int(case_data.get("retry_count") or 0)
    amount = float(case_data.get("amount") or 0.0)

    if amount > settings.max_auto_approved_amount or retry_count >= settings.max_retries_per_transaction:
        return DiagnosisOutput(
            diagnosis=f"High-risk transaction (₹{amount:,.2f}, retry #{retry_count}) requiring human review.",
            recovery_probability=0.25,
            recommended_action=ActionEnum.ESCALATE_TO_HUMAN,
            reasoning="Amount or retry ceiling exceeds autonomous threshold.",
            is_fallback=True,
        )

    if reason == "TEMPORARY_FAILURE" or "TIMEOUT" in reason:
        return DiagnosisOutput(
            diagnosis="Bank gateway or network timeout during authorization window.",
            recovery_probability=0.82,
            recommended_action=ActionEnum.RETRY_DELAYED,
            reasoning="Temporary network degradation observed; retry with backoff schedule.",
            is_fallback=True,
        )
    elif reason == "INSUFFICIENT_FUNDS":
        return DiagnosisOutput(
            diagnosis="Issuer declined transaction due to temporary insufficient card balance.",
            recovery_probability=0.50,
            recommended_action=ActionEnum.GENERATE_UPI_LINK,
            reasoning="Card retry likely to fail; offer instant UPI / QR alternative.",
            is_fallback=True,
        )
    elif reason in ("EXPIRED_CARD", "PAYMENT_METHOD_INVALID"):
        return DiagnosisOutput(
            diagnosis="Payment credential is expired or invalid on issuer network.",
            recovery_probability=0.65,
            recommended_action=ActionEnum.GENERATE_UPI_LINK,
            reasoning="Card cannot be charged; dispatch dynamic UPI link or update method.",
            is_fallback=True,
        )
    elif case_type == "CHECKOUT_ABANDONED" or reason == "CHECKOUT_ABANDONED":
        return DiagnosisOutput(
            diagnosis="Customer abandoned checkout session prior to payment capture.",
            recovery_probability=0.55,
            recommended_action=ActionEnum.SEND_RECOVERY_LINK,
            reasoning="Cart session preserved; dispatch personalized 1-click recovery link.",
            is_fallback=True,
        )
    elif case_type == "SUBSCRIPTION_RENEWAL_FAILED" or reason == "SUBSCRIPTION_RENEWAL_FAILED":
        return DiagnosisOutput(
            diagnosis="Recurring subscription mandate execution failed at issuing bank.",
            recovery_probability=0.60,
            recommended_action=ActionEnum.REQUEST_PAYMENT_METHOD_UPDATE,
            reasoning="Mandate invalid or declined; request customer update payment method.",
            is_fallback=True,
        )
    elif case_type == "OVERDUE_RECEIVABLE" or reason == "OVERDUE_RECEIVABLE":
        return DiagnosisOutput(
            diagnosis="Commercial invoice passed credit terms due date without payment.",
            recovery_probability=0.40,
            recommended_action=ActionEnum.FOLLOW_UP_OVERDUE_INVOICE,
            reasoning="B2B receivable overdue; dispatch gentle reminder and payment link.",
            is_fallback=True,
        )
    elif reason == "REPEATED_FAILURE" or retry_count >= 3:
        return DiagnosisOutput(
            diagnosis="Repeated payment failures across multiple settlement attempts.",
            recovery_probability=0.10,
            recommended_action=ActionEnum.ESCALATE_TO_HUMAN,
            reasoning="Diminishing returns on automated retries; route to human specialist.",
            is_fallback=True,
        )
    else:
        return DiagnosisOutput(
            diagnosis="Payment processing exception detected.",
            recovery_probability=0.50,
            recommended_action=ActionEnum.RETRY_DELAYED,
            reasoning="Default to delayed retry with backoff.",
            is_fallback=True,
        )

_SYSTEM_PROMPT = f"""You are a financial recovery analyst AI. Given a payment failure case,
you must return ONLY a valid JSON object matching this exact schema — nothing else:
{{
  "diagnosis": "<plain-language explanation of why revenue is at risk>",
  "recovery_probability": <float 0.0 to 1.0>,
  "recommended_action": "<one of: {', '.join(sorted(VALID_ACTIONS))}>",
  "reasoning": "<short chain of reasoning for audit trail>"
}}
Rules:
- recommended_action MUST be exactly one of the listed values.
- recovery_probability must be a number between 0 and 1.
- Return ONLY the JSON object — no markdown, no preamble, no explanation.
"""


def _build_user_prompt(case_data: dict) -> str:
    return f"""Payment failure case details:
- Case type: {case_data.get('case_type')}
- Failure reason: {case_data.get('failure_reason')}
- Amount: ₹{case_data.get('amount', 0):,.2f}
- Retry count: {case_data.get('retry_count', 0)}
- Customer previous success rate: {case_data.get('previous_success_rate', 1.0):.0%}
- Total past transactions: {case_data.get('total_transactions', 0)}
- Customer name: {case_data.get('customer_name', 'Unknown')}

Analyze this case and return your JSON diagnosis."""


def _parse_llm_response(text: str) -> Optional[DiagnosisOutput]:
    text = text.strip()
    # Extract JSON block if wrapped in markdown
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                text = part
                break

    try:
        data = json.loads(text)
        return DiagnosisOutput(**data)
    except Exception as e:
        logger.warning("LLM parse failed: %s | raw=%r", e, text[:200])
        return None


def _call_ollama(prompt: str, system: str) -> Optional[str]:
    try:
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "format": "json",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except httpx.TimeoutException:
        logger.error("Ollama timeout")
    except Exception as e:
        logger.error("Ollama error: %s", e)
    return None


def get_diagnosis(case_data: dict) -> DiagnosisOutput:
    """
    Call LLM for diagnosis. Retries once with corrective prompt on bad output.
    Falls back to ESCALATE_TO_HUMAN if both attempts fail.
    """
    user_prompt = _build_user_prompt(case_data)

    raw = _call_ollama(user_prompt, _SYSTEM_PROMPT)
    if raw:
        result = _parse_llm_response(raw)
        if result:
            return result

    # Retry once with a corrective prompt
    corrective = (
        user_prompt
        + "\n\nIMPORTANT: Your previous response was invalid. "
        "Return ONLY the JSON object with keys: diagnosis, recovery_probability, "
        "recommended_action, reasoning. No other text."
    )
    raw2 = _call_ollama(corrective, _SYSTEM_PROMPT)
    if raw2:
        result2 = _parse_llm_response(raw2)
        if result2:
            return result2

    logger.info("LLM call skipped or failed for case %s — using domain heuristic diagnosis", case_data.get("case_id"))
    return _build_heuristic_diagnosis(case_data)
