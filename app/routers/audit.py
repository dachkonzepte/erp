"""Router: audit

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 1 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from ..audit import audit_rows
from ..database import get_db
from ..schemas import AuditLogOut

router = APIRouter()

@router.get("/api/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(project_id: int | None = None, entity_type: str | None = None, entity_id: str | None = None, actor: str | None = None, limit: int = 250, db: Session = Depends(get_db)):
    return audit_rows(db, project_id=project_id, entity_type=entity_type, entity_id=entity_id, actor=actor, limit=limit)
