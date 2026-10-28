"""Router: audit

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 1 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, Query, Response
from sqlalchemy.orm import Session

from ..audit import ABSENCE_ENTITY_TYPES, ABSENCE_FIELD_NAMES, TASK_ENTITY_TYPE, WAGE_FIELD_NAMES, audit_rows, redact_absence_snapshot, redact_wage_snapshot
from ..database import get_db
from ..models import AppUser
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, has_min_role, has_role, require_min_role
from ..schemas import AuditLogOut
from ..verlauf_namen import lesbar_alle

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): die Änderungshistorie zeigt Vorher-/Nachher-Werte
# über alle Entitäten hinweg (auch Mitarbeiter/Preise) -- Büro/Admin, nicht für einen Monteur.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))

# Seit 1.8.150: ein Versatz darüber findet sicher nichts (so viele Einträge gibt es nicht) und ginge an die Datenbank nicht durch --
# SQLite und PostgreSQL rechnen OFFSET in 64 Bit, eine größere Zahl war bis dahin ein Serverfehler (OverflowError, 500).
GROESSTER_VERSATZ = 2**62
_INT64 = range(-2**63, 2**63)


@router.get("/api/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(response: Response, project_id: int | None = None, entity_type: str | None = None, entity_id: str | None = None, actor: str | None = None, limit: int = 250, offset: int = Query(0, ge=0), db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.8.138: mit Versatz (offset) zum Blättern -- `X-DK-Weitere: 1`, wenn nach dieser Seite noch Einträge kommen (gezählt vor
    der Schwärzung, sonst verschwände der Weg zu älteren Einträgen); jede Zeile mit lesbaren Namen (app/verlauf_namen.py, nach der
    Schwärzung, die an den rohen Namen hängt)."""
    # Seit 1.8.150: offset negativ oder keine Zahl 422 (bis dahin galt ein negativer still als 0); sehr groß -- auch eine Projekt-ID
    # jenseits von 64 Bit -- eine leere Seite statt 500.
    if offset > GROESSTER_VERSATZ or (project_id is not None and project_id not in _INT64):
        response.headers["X-DK-Weitere"] = "0"
        return []
    limit = min(max(limit, 1), 1000)
    rows = audit_rows(db, project_id=project_id, entity_type=entity_type, entity_id=entity_id, actor=actor, limit=limit + 1, offset=offset)
    response.headers["X-DK-Weitere"] = "1" if len(rows) > limit else "0"
    return sichtbar(db, rows[:limit], _role)


def sichtbar(db: Session, rows, _role: AppUser) -> list[AuditLogOut]:
    """Die Zeilen, die das Konto sehen darf, lesbar (seit 1.9.127 als eigene Funktion: auch der Verlauf der Akte, app/akte_verlauf.py)."""
    if has_role(_role, ROLE_ADMIN):
        return lesbar_alle(db, [AuditLogOut.model_validate(row) for row in rows])  # seit 1.9.123 mit einem Kontext je Antwort
    # Aufgaben (seit 1.8.18, "Übernehmen"): der Eintrag nennt den Titel, und eine zugewiesene
    # Aufgabe sieht außer dem Zuständigen nur Admin; eine finanz-gebundene nie buero_auftrag.
    # Deshalb nur für Admin -- dieselbe Grenze wie beim Versandprotokoll (Aufgaben-Mails, 1.8.17).
    rows = [row for row in rows if row.entity_type != TASK_ENTITY_TYPE]
    if has_min_role(_role, ROLE_OFFICE_FINANZEN):
        return lesbar_alle(db, [AuditLogOut.model_validate(row) for row in rows])
    # Rechtekonzept "Vier Rollen" Etappe 2 (seit 1.4.8): buero_auftrag sieht denselben Endpunkt,
    # aber ohne Vergütung ("jede Auswertung, die Löhne zeigt") -- geänderte Lohnfelder entfallen
    # ganz (nie old/new_value zeigen), angelegt/gelöscht-Schnappschüsse werden bereinigt.
    # Krankheitssichtbarkeit (siehe CLAUDE.md): dieselbe Behandlung für Art/Kategorie/Notiz einer
    # Abwesenheit -- entitätstyp-gebunden (redact_absence_snapshot()), da "notes" bei jeder
    # anderen Entität weiterhin unredigiert bleiben soll.
    result = []
    for row in rows:
        if row.field_name in WAGE_FIELD_NAMES:
            continue
        if row.entity_type in ABSENCE_ENTITY_TYPES and row.field_name in ABSENCE_FIELD_NAMES:
            continue
        out = AuditLogOut.model_validate(row)
        out.details = redact_wage_snapshot(out.details)
        out.details = redact_absence_snapshot(row.entity_type, out.details)
        result.append(out)
    return lesbar_alle(db, result)
