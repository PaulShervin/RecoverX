"""Data management endpoints — seed synthetic data, reset DB."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import GenerateDataRequest

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/seed")
def seed(req: GenerateDataRequest, db: Session = Depends(get_db)):
    """Generate synthetic customers and transactions."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from data.generate_synthetic import seed_database
    stats = seed_database(req.count, req.seed)
    return stats


@router.delete("/reset")
def reset_all(db: Session = Depends(get_db)):
    """Wipe all data (dev/demo only)."""
    from ..models import AuditEvent, WebhookEvent, Case, Transaction, Customer
    db.query(AuditEvent).delete()
    db.query(WebhookEvent).delete()
    db.query(Case).delete()
    db.query(Transaction).delete()
    db.query(Customer).delete()
    db.commit()
    return {"status": "reset"}
