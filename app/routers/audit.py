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
from ..models import AppUser
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..schemas import AuditLogOut

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): die Änderungshistorie zeigt Vorher-/Nachher-Werte
# über alle Entitäten hinweg (auch Mitarbeiter/Preise) -- Büro/Admin, nicht für einen Monteur.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


@router.get("/api/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(project_id: int | None = None, entity_type: str | None = None, entity_id: str | None = None, actor: str | None = None, limit: int = 250, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return audit_rows(db, project_id=project_id, entity_type=entity_type, entity_id=entity_id, actor=actor, limit=limit)
