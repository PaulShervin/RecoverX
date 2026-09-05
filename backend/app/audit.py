"""Append-only audit log. Every state transition writes here BEFORE the action."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .models import AuditEvent


def log_event(db: Session, case_id: str, event_type: str, details: str) -> AuditEvent:
    """
    Write an audit event atomically with the calling transaction.
    If the DB write fails, the caller's transaction rolls back — the action won't proceed.
    """
    event = AuditEvent(
        case_id=case_id,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        event_type=event_type,
        details=details,
    )
    db.add(event)
    db.flush()  # writes within the current transaction, before commit
    return event
