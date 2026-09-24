"""Router: calendar_events -- Kalender-Modul (Büro-Termine, seit 1.7.0), Teil des Moduls
"kalender" (siehe app/modules.py). Jeder Endpunkt prüft is_module_enabled() -- 403 bei
deaktiviertem Modul, unabhängig von der Rolle, Muster app/routers/accounts.py.

Ausnahmslos require_min_role(ROLE_OFFICE_AUFTRAG) -- buero_auftrag/buero_finanzen/admin, `field`
bekommt 403. Bewusst OHNE Eigentümerschafts-Prüfung beim Ändern/Löschen (Muster PUT/DELETE
/api/tasks/{id}, siehe CalendarEvent-Klassendocstring app/models.py) -- Privatsphäre wirkt nur
beim LESEN fremder Termine (list_calendar_events()), nicht als Schreibschranke.

GET /api/calendar-events/owners ist bewusst VOR GET /api/calendar-events/{event_id} registriert
-- sonst würde "owners" als event_id (int) fehlschlagen, bekannte Literal-vs-Platzhalter-
Kollision (siehe CLAUDE.md, mehrfach dokumentiert, z. B. "Büro-Suche")."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..calendar_events import (
    MODULE_KEY, create_event, delete_event, get_event, is_redacted_for_viewer, list_events,
    list_owners, redact_for_busy, update_event,
)
from ..database import get_db
from ..modules import is_module_enabled
from ..models import AppUser
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, require_min_role
from ..schemas import CalendarEventCreate, CalendarEventUpdate, CalendarOwnerOut

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))

# Die drei Rollen mit Zugriff auf dieses Modul -- selbe Menge wie require_min_role(ROLE_OFFICE_AUFTRAG)
# zulässt, hier als Tupel für list_owners() (Kandidaten für den Besitzer-Dropdown).
_OWNER_ROLES = (ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, ROLE_ADMIN)


def _require_module_enabled(db: Session) -> None:
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Kalender ist deaktiviert.")


def _out(data: dict, viewer_user_id: int | None) -> dict:
    return redact_for_busy(data) if is_redacted_for_viewer(data, viewer_user_id) else data


@router.get("/api/calendar-events/owners", response_model=list[CalendarOwnerOut])
def get_calendar_owners(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return list_owners(db, role_keys=_OWNER_ROLES)


@router.get("/api/calendar-events")
def get_calendar_events(
    start: datetime | None = None, end: datetime | None = None,
    project_id: int | None = None, quote_id: int | None = None,
    db: Session = Depends(get_db), _role: AppUser = _role_dep,
):
    """Bewusst ohne response_model -- pro Zeile wird explizit zwischen dem vollen und dem
    reduzierten Schema gewählt (Muster app/routers/service_reports.py::get_service_reports()),
    ein response_model=list[A] | list[B] würde nicht zeilenweise, sondern nur für die GESAMTE
    Liste greifen."""
    _require_module_enabled(db)
    rows = list_events(db, start=start, end=end, project_id=project_id, quote_id=quote_id)
    return [_out(row, _role.id) for row in rows]


@router.get("/api/calendar-events/{event_id}")
def get_calendar_event(event_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    data = get_event(db, event_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Termin nicht gefunden.")
    return _out(data, _role.id)


@router.post("/api/calendar-events")
def post_calendar_event(payload: CalendarEventCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        data = create_event(
            db, title=payload.title, start_at=payload.start_at, end_at=payload.end_at,
            all_day=payload.all_day, location=payload.location, notes=payload.notes,
            owner_user_id=payload.owner_user_id or _role.id,
            project_id=payload.project_id, quote_id=payload.quote_id, is_private=payload.is_private,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _out(data, _role.id)


@router.put("/api/calendar-events/{event_id}")
def put_calendar_event(event_id: int, payload: CalendarEventUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        data = update_event(db, event_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if data is None:
        raise HTTPException(status_code=404, detail="Termin nicht gefunden.")
    return _out(data, _role.id)


@router.delete("/api/calendar-events/{event_id}")
def delete_calendar_event(event_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not delete_event(db, event_id):
        raise HTTPException(status_code=404, detail="Termin nicht gefunden.")
    return {"deleted": True}
