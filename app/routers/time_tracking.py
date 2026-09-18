"""Router: time_tracking

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 13 Endpunkt(e) und 5 interne Hilfsfunktion(en), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.

Seit "Rechtekonzept", Teil B (siehe CLAUDE.md): jeder Endpunkt hier ist Selbstbedienung fuer
JEDE Rolle -- ein Monteur bucht eigene Zeiten und sieht eigene. Die eigentliche Eingrenzung auf
die eigene Person sitzt bereits seit jeher in den Endpunkten selbst, nicht im Rollen-Gate:
_time_entry_employee_for_request() (nur die eigene employee_id darf angegeben werden),
_time_entry_can_edit() (aendern/loeschen nur eigene Zeilen), _group_actor() (Gruppenbuchung nur
mit eigener Mitarbeiterverknuepfung) und get_time_entries() (ein Monteur bekommt IMMER
employee_id = eigene, auch bei ?order_id=... -- list_entries() verknuepft beide Filter mit UND,
siehe app/time_tracking.py; die Zeitbuchungen der Kollegen zum selben Auftrag bleiben also
unsichtbar). Seit 1.3.56 gilt diese Lese-Eingrenzung nur noch fuer ROLE_FIELD, nicht mehr fuer
jeden Nicht-Admin: das Buero sieht die Buchungen aller (es rechnet sie ab, order.html/
project_folder.html lesen "alle Buchungen des Auftrags/Projekts"). Der Backoffice-Bereich
(app/routers/time_backoffice.py) ist davon getrennt und bleibt wie bisher admin-only ueber
require_admin().
"""

from fastapi import APIRouter
from datetime import date, datetime
from decimal import Decimal
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppUser, TimeEntry, TimeEntryGroup
from ..permissions import ROLE_FIELD, require_min_role
from ..schemas import TimeEntryManualCreate, TimeEntryOut, TimeEntryUpdate, TimeGroupManualCreate, TimeGroupOut, TimeGroupTimerStart, TimeGroupTimerStop, TimeTimerStart, TimeTimerStop, TimeTrackingSettingsOut
from ..time_backoffice import get_or_create_time_settings, rounded_hours, time_settings_dict
from ..time_tracking import active_group_for_employee, active_entry as active_time_entry, create_group_manual_entry, create_manual_entry, delete_entry as delete_time_entry_row, entry_to_dict, group_for_entry, group_member_ids, group_to_dict, list_entries as list_time_entries, start_group_timer, start_timer, stop_group_timer, stop_timer, time_tracking_context, update_entry as update_time_entry_row
from ..work_time_models import automatic_break_minutes_for_timer

router = APIRouter()

_any_role_dep = Depends(require_min_role(ROLE_FIELD))

def _time_entry_employee_for_request(request: Request, requested_employee_id: int | None, db: Session) -> int:
    user = getattr(request.state, "erp_user", None)
    if user is not None and user.role != "admin":
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail="Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet.")
        if requested_employee_id is not None and requested_employee_id != user.employee_id:
            raise HTTPException(status_code=403, detail="Sie dürfen nur eigene Zeiten erfassen.")
        return user.employee_id
    if requested_employee_id is None:
        if user is not None and user.employee_id is not None:
            return user.employee_id
        raise HTTPException(status_code=422, detail="Bitte Mitarbeiter auswählen.")
    return requested_employee_id


def _time_entry_can_edit(request: Request, row: TimeEntry) -> bool:
    user = getattr(request.state, "erp_user", None)
    return user is None or user.role == "admin" or (user.employee_id is not None and user.employee_id == row.employee_id)


def _validate_time_rules(db: Session, *, order_item_id: int | None, activity: str | None, manual: bool = False, group: bool = False):
    settings=get_or_create_time_settings(db)
    if manual and not settings.allow_manual_entries:
        raise HTTPException(status_code=403,detail="Manuelle Zeitbuchungen sind im Zeiterfassungs-Backoffice deaktiviert.")
    if group and not settings.allow_group_bookings:
        raise HTTPException(status_code=403,detail="Gruppenbuchungen sind im Zeiterfassungs-Backoffice deaktiviert.")
    if settings.require_order_item and order_item_id is None:
        raise HTTPException(status_code=422,detail="Für Zeitbuchungen ist eine LV-Position erforderlich.")
    if settings.require_activity and not (activity or "").strip():
        raise HTTPException(status_code=422,detail="Für Zeitbuchungen ist eine Tätigkeit erforderlich.")
    return settings


def _apply_time_rounding(db: Session, entry: TimeEntry):
    settings=get_or_create_time_settings(db)
    if entry.status=="booked" and settings.rounding_minutes:
        entry.hours=rounded_hours(Decimal(entry.hours or 0),settings.rounding_minutes)
        db.commit(); db.refresh(entry)
    return entry


def _group_actor(request: Request) -> tuple[int | None, bool, int | None]:
    user=getattr(request.state,"erp_user",None)
    is_admin=bool(user is None or user.role=="admin")
    actor_employee_id=getattr(user,"employee_id",None) if user is not None else None
    if not is_admin and actor_employee_id is None:
        raise HTTPException(status_code=403,detail="Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet.")
    return actor_employee_id,is_admin,getattr(user,"id",None)


@router.get("/api/time-tracking/settings", response_model=TimeTrackingSettingsOut)
def get_mobile_time_settings(db:Session=Depends(get_db), _role: AppUser = _any_role_dep):
    return TimeTrackingSettingsOut.model_validate(time_settings_dict(get_or_create_time_settings(db), db))


@router.get("/api/time-tracking/context")
def get_time_tracking_context(request: Request, employee_id: int | None = None, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    user = getattr(request.state, "erp_user", None)
    resolved = employee_id
    include_all = bool(user and user.role == "admin")
    if user is not None and user.role != "admin":
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail="Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet.")
        resolved = user.employee_id
    result = time_tracking_context(db, employee_id=resolved, include_all_orders=include_all)
    result["current_employee_id"] = resolved
    result["is_admin"] = bool(user is None or user.role == "admin")
    return result


@router.post("/api/time-entry-groups", response_model=TimeGroupOut)
def create_time_group_manual(payload:TimeGroupManualCreate,request:Request,db:Session=Depends(get_db), _role: AppUser = _any_role_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity,manual=True,group=True)
    actor,is_admin,user_id=_group_actor(request)
    try:
        group=create_group_manual_entry(db,employee_ids=payload.employee_ids,team_id=payload.team_id,actor_employee_id=actor,is_admin=is_admin,order_id=payload.order_id,order_item_id=payload.order_item_id,work_date=payload.work_date,entry_type=payload.entry_type,activity=payload.activity,hours=payload.hours,break_minutes=payload.break_minutes,notes=payload.notes,created_by_user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409 if "läuft bereits" in str(exc) else 422,detail=str(exc)) from exc
    return TimeGroupOut.model_validate(group_to_dict(db,group))


@router.post("/api/time-entry-groups/start", response_model=TimeGroupOut)
def start_time_group(payload:TimeGroupTimerStart,request:Request,db:Session=Depends(get_db), _role: AppUser = _any_role_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity,group=True)
    actor,is_admin,user_id=_group_actor(request)
    try:
        group=start_group_timer(db,employee_ids=payload.employee_ids,team_id=payload.team_id,actor_employee_id=actor,is_admin=is_admin,order_id=payload.order_id,order_item_id=payload.order_item_id,entry_type=payload.entry_type,activity=payload.activity,notes=payload.notes,started_at=payload.started_at,created_by_user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409 if "läuft bereits" in str(exc) else 422,detail=str(exc)) from exc
    return TimeGroupOut.model_validate(group_to_dict(db,group))


@router.get("/api/time-entry-groups/active", response_model=TimeGroupOut | None)
def get_active_time_group(request:Request,employee_id:int|None=None,db:Session=Depends(get_db), _role: AppUser = _any_role_dep):
    resolved=_time_entry_employee_for_request(request,employee_id,db)
    user=getattr(request.state,"erp_user",None)
    row=active_group_for_employee(db,resolved,initiated_only=bool(user is not None and user.role!="admin"))
    return TimeGroupOut.model_validate(group_to_dict(db,row)) if row else None


@router.post("/api/time-entry-groups/{group_id}/stop", response_model=TimeGroupOut)
def stop_time_group(group_id:int,payload:TimeGroupTimerStop,request:Request,db:Session=Depends(get_db), _role: AppUser = _any_role_dep):
    group=db.get(TimeEntryGroup,group_id)
    if group is None: raise HTTPException(status_code=404,detail="Gruppenbuchung wurde nicht gefunden.")
    user=getattr(request.state,"erp_user",None)
    if user is not None and user.role!="admin" and user.employee_id!=group.initiated_by_employee_id:
        raise HTTPException(status_code=403,detail="Nur der Initiator der Gruppenbuchung oder ein Administrator darf die gesamte Gruppe stoppen.")
    try:
        end=payload.ended_at or datetime.now().replace(microsecond=0)
        member_breaks={eid:automatic_break_minutes_for_timer(db,eid,group.started_at,end) for eid in group_member_ids(db,group.id)} if group.started_at else {}
        group=stop_group_timer(db,group_id,ended_at=end,break_minutes=payload.break_minutes,break_minutes_by_employee=member_breaks)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return TimeGroupOut.model_validate(group_to_dict(db,group))


@router.get("/api/time-entries", response_model=list[TimeEntryOut])
def get_time_entries(request: Request, employee_id: int | None = None, project_id: int | None = None, order_id: int | None = None, start_date: date | None = None, end_date: date | None = None, limit: int = 500, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    user = getattr(request.state, "erp_user", None)
    # Seit 1.3.56 nur noch für Monteure (vorher: jeder Nicht-Admin): ein Monteur sieht
    # ausschließlich eigene Buchungen, auch bei ?order_id=...; Büro/Admin sehen alle -- das Büro
    # rechnet sie ab (order.html/project_folder.html lesen darüber "alle Buchungen des Auftrags").
    if user is not None and user.role == ROLE_FIELD:
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail="Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet.")
        employee_id = user.employee_id
    rows = list_time_entries(db, employee_id=employee_id, project_id=project_id, order_id=order_id, start_date=start_date, end_date=end_date, limit=limit)
    return [TimeEntryOut.model_validate(entry_to_dict(x)) for x in rows]


@router.get("/api/time-entries/active", response_model=TimeEntryOut | None)
def get_active_time_entry(request: Request, employee_id: int | None = None, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    resolved = _time_entry_employee_for_request(request, employee_id, db)
    row = active_time_entry(db, resolved)
    return TimeEntryOut.model_validate(entry_to_dict(row)) if row else None


@router.post("/api/time-entries", response_model=TimeEntryOut)
def create_time_entry(payload: TimeEntryManualCreate, request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    settings=_validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity,manual=True)
    employee_id = _time_entry_employee_for_request(request, payload.employee_id, db)
    user = getattr(request.state, "erp_user", None)
    try:
        row = create_manual_entry(db, employee_id=employee_id, order_id=payload.order_id, order_item_id=payload.order_item_id, work_date=payload.work_date, entry_type=payload.entry_type, activity=payload.activity, hours=rounded_hours(Decimal(payload.hours),settings.rounding_minutes), break_minutes=payload.break_minutes, notes=payload.notes, created_by_user_id=getattr(user, "id", None))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeEntryOut.model_validate(entry_to_dict(row))


@router.post("/api/time-entries/start", response_model=TimeEntryOut)
def start_time_entry(payload: TimeTimerStart, request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity)
    employee_id = _time_entry_employee_for_request(request, payload.employee_id, db)
    user = getattr(request.state, "erp_user", None)
    try:
        row = start_timer(db, employee_id=employee_id, order_id=payload.order_id, order_item_id=payload.order_item_id, entry_type=payload.entry_type, activity=payload.activity, notes=payload.notes, started_at=payload.started_at, created_by_user_id=getattr(user, "id", None))
    except ValueError as exc:
        raise HTTPException(status_code=409 if "läuft bereits" in str(exc) else 422, detail=str(exc)) from exc
    return TimeEntryOut.model_validate(entry_to_dict(row))


@router.post("/api/time-entries/{entry_id}/stop", response_model=TimeEntryOut)
def stop_time_entry(entry_id: int, payload: TimeTimerStop, request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    current = db.get(TimeEntry, entry_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeiterfassung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Sie dürfen diese Zeiterfassung nicht ändern.")
    try:
        group = group_for_entry(db, entry_id)
        user = getattr(request.state, "erp_user", None)
        if group is not None and group.status == "running" and (user is None or user.role == "admin" or user.employee_id == group.initiated_by_employee_id):
            end=payload.ended_at or datetime.now().replace(microsecond=0)
            member_breaks={eid:automatic_break_minutes_for_timer(db,eid,group.started_at,end) for eid in group_member_ids(db,group.id)} if group.started_at else {}
            stop_group_timer(db, group.id, ended_at=end, break_minutes=payload.break_minutes, break_minutes_by_employee=member_breaks)
            row = db.get(TimeEntry, entry_id)
        else:
            end=payload.ended_at or datetime.now().replace(microsecond=0)
            auto_break=automatic_break_minutes_for_timer(db,current.employee_id,current.started_at,end) if current.started_at else 0
            row = stop_timer(db, entry_id, ended_at=end, break_minutes=max(int(payload.break_minutes or 0),int(auto_break or 0)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    loaded = db.get(TimeEntry, row.id)
    # Beziehungen fuer die Ausgabe wie beim regulaeren Stop neu laden.
    loaded = next((x for x in list_time_entries(db, employee_id=loaded.employee_id, start_date=loaded.work_date, end_date=loaded.work_date, limit=2000) if x.id==loaded.id), loaded)
    loaded=_apply_time_rounding(db,loaded)
    return TimeEntryOut.model_validate(entry_to_dict(loaded))


@router.put("/api/time-entries/{entry_id}", response_model=TimeEntryOut)
def put_time_entry(entry_id: int, payload: TimeEntryUpdate, request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity)
    current = db.get(TimeEntry, entry_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeitbuchung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Sie dürfen diese Zeitbuchung nicht ändern.")
    employee_id = _time_entry_employee_for_request(request, payload.employee_id, db)
    try:
        row = update_time_entry_row(db, entry_id, employee_id=employee_id, order_id=payload.order_id, order_item_id=payload.order_item_id, work_date=payload.work_date, entry_type=payload.entry_type, activity=payload.activity, hours=payload.hours, break_minutes=payload.break_minutes, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeEntryOut.model_validate(entry_to_dict(row))


@router.delete("/api/time-entries/{entry_id}")
def remove_time_entry(entry_id: int, request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    current = db.get(TimeEntry, entry_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeitbuchung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Sie dürfen diese Zeitbuchung nicht löschen.")
    try:
        delete_time_entry_row(db, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"deleted": True}
