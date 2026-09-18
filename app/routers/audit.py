"""Router: audit

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 1 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from ..audit import WAGE_FIELD_NAMES, audit_rows, redact_wage_snapshot
from ..database import get_db
from ..models import AppUser
from ..permissions import ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, has_min_role, require_min_role
from ..schemas import AuditLogOut

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): die Änderungshistorie zeigt Vorher-/Nachher-Werte
# über alle Entitäten hinweg (auch Mitarbeiter/Preise) -- Büro/Admin, nicht für einen Monteur.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


@router.get("/api/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(project_id: int | None = None, entity_type: str | None = None, entity_id: str | None = None, actor: str | None = None, limit: int = 250, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    rows = audit_rows(db, project_id=project_id, entity_type=entity_type, entity_id=entity_id, actor=actor, limit=limit)
    if has_min_role(_role, ROLE_OFFICE_FINANZEN):
        return rows
    # Rechtekonzept "Vier Rollen" Etappe 2 (seit 1.4.8): buero_auftrag sieht denselben Endpunkt,
    # aber ohne Vergütung ("jede Auswertung, die Löhne zeigt") -- geänderte Lohnfelder entfallen
    # ganz (nie old/new_value zeigen), angelegt/gelöscht-Schnappschüsse werden bereinigt.
    result = []
    for row in rows:
        if row.field_name in WAGE_FIELD_NAMES:
            continue
        out = AuditLogOut.model_validate(row)
        out.details = redact_wage_snapshot(out.details)
        result.append(out)
    return result
