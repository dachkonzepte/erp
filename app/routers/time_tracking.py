"""Router: time_tracking

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 13 Endpunkt(e) und 5 interne Hilfsfunktion(en), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.

Seit "Rechtekonzept", Teil B (siehe CLAUDE.md): jeder Endpunkt hier ist Selbstbedienung fuer
JEDE Rolle -- ein Monteur bucht eigene Zeiten und sieht eigene. Die eigentliche Eingrenzung auf
die eigene Person sitzt bereits seit jeher in den Endpunkten selbst, nicht im Rollen-Gate:
_time_entry_employee_for_request() (nur die eigene employee_id darf angegeben werden),
_time_entry_can_edit() (aendern/loeschen nur eigene Zeilen), _group_actor() (Gruppenbuchung nur
mit eigener Mitarbeiterverknuepfung) und _visible_employee_id() fuer Liste und Summen (ein
Monteur bekommt IMMER employee_id = eigene, auch bei ?order_id=... -- list_entries() verknuepft
beide Filter mit UND, siehe app/time_tracking.py; die Zeitbuchungen der Kollegen zum selben
Auftrag bleiben also unsichtbar). Seit 1.3.56 gilt diese Lese-Eingrenzung nur noch fuer ROLE_FIELD, nicht mehr fuer
jeden Nicht-Admin: das Buero sieht die Buchungen aller (es rechnet sie ab, order.html/
project_folder.html lesen "alle Buchungen des Auftrags/Projekts"). Der Backoffice-Bereich
(app/routers/time_backoffice.py) ist davon getrennt und bleibt wie bisher admin-only ueber
require_admin().
"""

from fastapi import APIRouter
from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from ..berlin_time import BERLIN, berlin_now, berlin_today
from ..meldungen import KEIN_MITARBEITER
from ..database import get_db
from ..models import AppUser, TimeEntry, TimeEntryGroup
from ..permissions import ROLE_FIELD, darf_zeit_fuer_andere_buchen, require_min_role
from .orders import require_field_order_access
from ..schemas import CrewGroupSummaryOut, CrewOut, TimeEntryManualCreate, TimeEntryOut, TimeEntrySummaryOut, TimeEntryUpdate, TimeGroupManualCreate, TimeGroupOut, TimeGroupTimerStart, TimeGroupTimerStop, TimeGroupUpdate, TimeEndeNachtragen, TimeEndeVorschauOut, TimeZeitartWechseln, TimeTimerStart, TimeTimerStop, TimeTrackingSettingsOut
from ..heute import zeitarten
from ..time_backoffice import load_time_settings, locked_until, time_settings_dict
from ..time_tracking import MAX_LIST_LIMIT, active_group_for_employee, active_entry as active_time_entry, count_entries, create_group_manual_entry, create_manual_entry, crew_leader_team_ids, delete_entry as delete_time_entry_row, delete_group, ende_nachtragen, ende_vorschau, ZeitartInGruppe, zeitart_wechseln, entry_to_dict, field_time_tracking_context, laeuft_seit_frueher, load_entry, nachtrag_nach_zeitregel, OffeneZeit, group_for_entry, group_member_ids, group_to_dict, list_crews_for_leader, list_entries as list_time_entries, list_groups_initiated_by, start_group_timer, start_timer, stop_group_timer, stop_timer, summarize_entries, time_tracking_context, update_entry as update_time_entry_row, update_group

router = APIRouter()

_any_role_dep = Depends(require_min_role(ROLE_FIELD))

def _time_entry_employee_for_request(request: Request, requested_employee_id: int | None, db: Session) -> int:
    user = getattr(request.state, "erp_user", None)
    if not darf_zeit_fuer_andere_buchen(user):  # seit 1.8.152 aus app/permissions.py, dieselbe Regel wie die Oberfläche
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail=KEIN_MITARBEITER)
        if requested_employee_id is not None and requested_employee_id != user.employee_id:
            raise HTTPException(status_code=403, detail="Du darfst nur eigene Zeiten erfassen.")
        return user.employee_id
    if requested_employee_id is None:
        if user is not None and user.employee_id is not None:
            return user.employee_id
        raise HTTPException(status_code=422, detail="Bitte Mitarbeiter auswählen.")
    return requested_employee_id


def _time_entry_can_edit(request: Request, row: TimeEntry) -> bool:
    user = getattr(request.state, "erp_user", None)
    return darf_zeit_fuer_andere_buchen(user) or (user.employee_id is not None and user.employee_id == row.employee_id)


def _validate_time_rules(db: Session, *, order_item_id: int | None, activity: str | None, manual: bool = False, group: bool = False):
    settings=load_time_settings(db)
    if manual and not settings.allow_manual_entries:
        raise HTTPException(status_code=403,detail="Manuelle Zeitbuchungen sind im Zeiterfassungs-Backoffice deaktiviert.")
    if group and not settings.allow_group_bookings:
        raise HTTPException(status_code=403,detail="Gruppenbuchungen sind im Zeiterfassungs-Backoffice deaktiviert.")
    if settings.require_order_item and order_item_id is None:
        raise HTTPException(status_code=422,detail="Für Zeitbuchungen ist eine LV-Position erforderlich.")
    if settings.require_activity and not (activity or "").strip():
        raise HTTPException(status_code=422,detail="Für Zeitbuchungen ist eine Tätigkeit erforderlich.")
    return settings


def _require_bookable_order(request: Request, db: Session, order_id: int) -> None:
    """Seit 1.7.9: ein Monteur bucht nur auf Aufträge, die field_may_access_order() ihm zuordnet
    (Planungsbezug oder eigener Bericht, ohne Zeitfenster) -- vorher nahm der Server jede
    existierende Auftrags-ID an und lieferte Auftragsnummer/Projektname in der Antwort zurück.
    Büro/Admin unverändert."""
    user = getattr(request.state, "erp_user", None)
    if user is not None:
        require_field_order_access(db, user, order_id)


def _require_open_period(request: Request, db: Session, *work_dates: date) -> None:
    """Seit 1.7.10: Buchungen im abgeschlossenen Zeitraum (work_date <= locked_until) legt nur noch
    ein Admin an, ändert, stoppt oder löscht -- auch die eigenen eines Monteurs, denn sie sind
    dann bereits in die Lohnabrechnung eingegangen."""
    user = getattr(request.state, "erp_user", None)
    if user is None or user.role == "admin":
        return
    lock = locked_until(db)
    if lock is not None and any(d is not None and d <= lock for d in work_dates):
        raise HTTPException(status_code=403, detail=f"Die Zeiterfassung ist bis {lock:%d.%m.%Y} abgeschlossen. Änderungen in diesem Zeitraum nur durch einen Administrator.")


CREW_LEADER_ONLY = "Gruppenbuchungen sind für Monteure dem Kolonnenführer des Teams vorbehalten."
# Seit 1.9.35 (Stufe 4, R1, Punkt 2): eine Zeit, die seit einem früheren Tag läuft
MONAT_ABGESCHLOSSEN = "Monat abgeschlossen – das Büro schließt die Zeit."
GRUPPENZEIT_NUR_KOLONNENFUEHRER = "Die Gruppenzeit schließt der Kolonnenführer."


def _stopp_vom_vortag(started_at) -> str:
    return f"Diese Zeit läuft seit dem {started_at:%d.%m.%Y} – bitte „Ende nachtragen“ (Ende am Starttag) statt stoppen."

_TIME_FIELDS = ("order_id", "order_item_id", "work_date", "entry_type", "activity", "hours", "break_minutes", "notes")


def _merge_time_changes(stored, changes: dict) -> dict:
    """Teil-Update einer Zeit- oder Gruppenbuchung (seit 1.8.25): die gespeicherten Werte, darüber
    die gesendeten. Die mobile Zeiterfassung schickt beim Ändern weder Pause noch LV-Position --
    bis dahin ersetzte der Server die Pause durch den Standard und leerte die LV-Position.
    Wechselt der Auftrag ohne neue LV-Position, entfällt die alte: sie gehört zum alten Auftrag."""
    merged = {key: getattr(stored, key) for key in _TIME_FIELDS}
    if "order_id" in changes and changes["order_id"] != stored.order_id and "order_item_id" not in changes:
        merged["order_item_id"] = None
    merged.update((key, value) for key, value in changes.items() if key in _TIME_FIELDS)
    return merged


def _require_crew_leader(request: Request, db: Session, team_id: int | None) -> None:
    """Seit 1.7.12: bis dahin war die Gruppenbuchung für `field` nur in der Oberfläche
    ausgeblendet, serverseitig konnte jeder Monteur für seine Teamkollegen buchen. Jetzt nur noch,
    wer im gewählten (aktiven) Team als Kolonnenführer eingetragen ist. Büro/Admin unverändert."""
    user = getattr(request.state, "erp_user", None)
    if user is None or user.role != ROLE_FIELD:
        return
    if team_id is None or team_id not in crew_leader_team_ids(db, user.employee_id):
        raise HTTPException(status_code=403, detail=CREW_LEADER_ONLY)


def _require_group_owner(request: Request, db: Session, group: TimeEntryGroup) -> None:
    """Ändern/Löschen einer Gruppenbuchung: Admin, oder wer sie angelegt hat -- ein Monteur
    zusätzlich nur, solange er im Team der Buchung noch Kolonnenführer ist."""
    user = getattr(request.state, "erp_user", None)
    if user is None or user.role == "admin":
        return
    if user.employee_id is None or user.employee_id != group.initiated_by_employee_id:
        raise HTTPException(status_code=403, detail="Nur wer die Gruppenbuchung angelegt hat, darf sie ändern oder löschen.")
    if user.role == ROLE_FIELD and group.team_id not in crew_leader_team_ids(db, user.employee_id):
        raise HTTPException(status_code=403, detail=CREW_LEADER_ONLY)


def _noch_kolonnenfuehrer(request: Request, db: Session, group: TimeEntryGroup) -> bool:
    """Seit 1.8.144 (Entscheidung vom 19.10.2026): eine Gruppenzeit für alle stoppen darf ein Monteur nur, solange er im Team der
    Buchung Kolonnenführer ist -- wie Ändern und Löschen (_require_group_owner()). Bis dahin genügte "hat sie angelegt" (Befund
    1.8.142). Büro und Admin unverändert."""
    user = getattr(request.state, "erp_user", None)
    return user is None or user.role != ROLE_FIELD or group.team_id in crew_leader_team_ids(db, user.employee_id)


def _group_out(request: Request, db: Session, group: TimeEntryGroup) -> TimeGroupOut:
    """Für Monteure ohne die vollständigen Buchungen der Kollegen (keine Sicht auf fremde Zeiten)
    -- nur Name, Stunden und Status je Mitglied."""
    data = group_to_dict(db, group)
    user = getattr(request.state, "erp_user", None)
    if user is not None and user.role == ROLE_FIELD:
        data["member_entries"] = [{"employee_id": e["employee_id"], "employee_name": e["employee_name"],
                                   "hours": e["hours"], "status": e["status"]} for e in data["member_entries"]]
    return TimeGroupOut.model_validate(data)


def _group_actor(request: Request) -> tuple[int | None, bool, int | None]:
    user=getattr(request.state,"erp_user",None)
    is_admin=bool(user is None or user.role=="admin")
    actor_employee_id=getattr(user,"employee_id",None) if user is not None else None
    if not is_admin and actor_employee_id is None:
        raise HTTPException(status_code=403,detail=KEIN_MITARBEITER)
    return actor_employee_id,is_admin,getattr(user,"id",None)


@router.get("/api/time-tracking/settings", response_model=TimeTrackingSettingsOut)
def get_mobile_time_settings(db:Session=Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    return TimeTrackingSettingsOut.model_validate(time_settings_dict(load_time_settings(db), db))


@router.get("/api/time-tracking/context")
def get_time_tracking_context(request: Request, employee_id: int | None = None, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    """Seit 1.8.24 bekommt ein Monteur nur sich selbst, als Kolonnenführer seine Kolonne, und seine
    buchbaren Aufträge -- ohne Personalnummern (field_time_tracking_context()). Büro unverändert."""
    user = getattr(request.state, "erp_user", None)
    resolved = employee_id
    include_all = bool(user and user.role == "admin")
    if user is not None and user.role != "admin":
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail=KEIN_MITARBEITER)
        resolved = user.employee_id
    if user is not None and user.role == ROLE_FIELD:
        result = field_time_tracking_context(db, resolved)
    else:
        result = time_tracking_context(db, employee_id=resolved, include_all_orders=include_all)
    result["current_employee_id"] = resolved
    result["is_admin"] = bool(user is None or user.role == "admin")
    return result


@router.post("/api/time-entry-groups", response_model=TimeGroupOut)
def create_time_group_manual(payload:TimeGroupManualCreate,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity,manual=True,group=True)
    actor,is_admin,user_id=_group_actor(request)
    _require_crew_leader(request,db,payload.team_id)
    _require_bookable_order(request,db,payload.order_id)
    _require_open_period(request,db,payload.work_date)
    try:
        group=create_group_manual_entry(db,employee_ids=payload.employee_ids,team_id=payload.team_id,actor_employee_id=actor,is_admin=is_admin,order_id=payload.order_id,order_item_id=payload.order_item_id,work_date=payload.work_date,entry_type=payload.entry_type,activity=payload.activity,hours=payload.hours,break_minutes=payload.break_minutes,notes=payload.notes,created_by_user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409 if "läuft bereits" in str(exc) else 422,detail=str(exc)) from exc
    return _group_out(request,db,group)


@router.post("/api/time-entry-groups/start", response_model=TimeGroupOut)
def start_time_group(payload:TimeGroupTimerStart,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity,group=True)
    actor,is_admin,user_id=_group_actor(request)
    _require_crew_leader(request,db,payload.team_id)
    _require_bookable_order(request,db,payload.order_id)
    _require_open_period(request,db,(payload.started_at or berlin_now()).date())
    try:
        group=start_group_timer(db,employee_ids=payload.employee_ids,team_id=payload.team_id,actor_employee_id=actor,is_admin=is_admin,order_id=payload.order_id,order_item_id=payload.order_item_id,entry_type=payload.entry_type,activity=payload.activity,notes=payload.notes,started_at=payload.started_at,created_by_user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409 if "läuft bereits" in str(exc) else 422,detail=str(exc)) from exc
    return _group_out(request,db,group)


@router.get("/api/time-entry-groups/active", response_model=TimeGroupOut | None)
def get_active_time_group(request:Request,employee_id:int|None=None,db:Session=Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    resolved=_time_entry_employee_for_request(request,employee_id,db)
    user=getattr(request.state,"erp_user",None)
    row=active_group_for_employee(db,resolved,initiated_only=bool(user is not None and user.role!="admin"))
    return _group_out(request,db,row) if row else None


@router.get("/api/time-entry-groups/mine", response_model=list[CrewGroupSummaryOut])
def get_my_time_groups(request:Request,days:int=14,db:Session=Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    """Seit 1.7.12: die selbst angelegten Gruppenbuchungen (zum Korrigieren) -- nur Namen und
    Stunden je Mitglied, keine vollständigen Buchungen der Kollegen."""
    user=getattr(request.state,"erp_user",None)
    if user is None or user.employee_id is None:
        return []
    start=berlin_today()-timedelta(days=max(1,min(days,62)))
    return [CrewGroupSummaryOut.model_validate(x) for x in list_groups_initiated_by(db,user.employee_id,start_date=start)]


@router.get("/api/time-tracking/crews", response_model=list[CrewOut])
def get_my_crews(request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    """Seit 1.7.12: die Kolonnen, für die der angemeldete Mitarbeiter als Kolonnenführer buchen
    darf -- leer für jeden anderen (die mobile Ansicht blendet den Abschnitt dann aus)."""
    user=getattr(request.state,"erp_user",None)
    return [CrewOut.model_validate(x) for x in list_crews_for_leader(db,getattr(user,"employee_id",None))]


@router.put("/api/time-entry-groups/{group_id}", response_model=TimeGroupOut)
def put_time_group(group_id:int,payload:TimeGroupUpdate,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    # Seit 1.8.99 gesperrt vor dem Zusammenführen (Festlegung 1.8.96 Nr. 19 korrigiert): eine LV-Position gehört zum Auftrag -- ein
    # gleichzeitiger Auftragswechsel ließ sonst eine Position des alten Auftrags stehen.
    group=db.get(TimeEntryGroup,group_id,with_for_update=True,populate_existing=True)
    if group is None: raise HTTPException(status_code=404,detail="Gruppenbuchung wurde nicht gefunden.")
    _require_group_owner(request,db,group)
    values=_merge_time_changes(group,payload.model_dump(exclude_unset=True))
    _validate_time_rules(db,order_item_id=values["order_item_id"],activity=values["activity"],manual=True,group=True)
    _require_bookable_order(request,db,values["order_id"])
    _require_open_period(request,db,group.work_date,values["work_date"])
    try:
        group,skipped=update_group(db,group_id,**values)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    out=_group_out(request,db,group)
    out.skipped_members=skipped
    return out


@router.delete("/api/time-entry-groups/{group_id}")
def remove_time_group(group_id:int,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    group=db.get(TimeEntryGroup,group_id)
    if group is None: raise HTTPException(status_code=404,detail="Gruppenbuchung wurde nicht gefunden.")
    _require_group_owner(request,db,group)
    _require_open_period(request,db,group.work_date)
    try:
        kept=delete_group(db,group_id)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {"deleted": True, "kept_members": kept}


@router.post("/api/time-entry-groups/{group_id}/stop", response_model=TimeGroupOut)
def stop_time_group(group_id:int,payload:TimeGroupTimerStop,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    group=db.get(TimeEntryGroup,group_id)
    if group is None: raise HTTPException(status_code=404,detail="Gruppenbuchung wurde nicht gefunden.")
    user=getattr(request.state,"erp_user",None)
    if user is not None and user.role!="admin" and user.employee_id!=group.initiated_by_employee_id:
        raise HTTPException(status_code=403,detail="Nur der Initiator der Gruppenbuchung oder ein Administrator darf die gesamte Gruppe stoppen.")
    if not _noch_kolonnenfuehrer(request,db,group):
        raise HTTPException(status_code=403,detail=CREW_LEADER_ONLY)
    _require_open_period(request,db,group.work_date)
    if group.status=="running" and group.started_at is not None and group.started_at.date()<berlin_today():  # seit 1.9.35
        raise HTTPException(status_code=409,detail=_stopp_vom_vortag(group.started_at))
    try:
        group=stop_group_timer(db,group_id,ended_at=payload.ended_at or berlin_now(),break_minutes=payload.break_minutes)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return _group_out(request,db,group)


def _visible_employee_id(request: Request, employee_id: int | None) -> int | None:
    """Die eine Sichtbarkeitsregel für Liste UND Summen (GET /api/time-entries und
    /api/time-entries/summary). Seit 1.3.56 nur noch für Monteure (vorher: jeder Nicht-Admin): ein
    Monteur sieht ausschließlich eigene Buchungen, auch bei ?order_id=... oder
    ?employee_id=<Kollege>; Büro/Admin sehen alle -- das Büro rechnet sie ab (Einsatzbericht-Seite
    und Projektmappe lesen darüber "alle Buchungen des Auftrags/Projekts")."""
    user = getattr(request.state, "erp_user", None)
    if user is not None and user.role == ROLE_FIELD:
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail=KEIN_MITARBEITER)
        return user.employee_id
    return employee_id


@router.get("/api/time-entries", response_model=list[TimeEntryOut])
def get_time_entries(request: Request, response: Response, employee_id: int | None = None, project_id: int | None = None, order_id: int | None = None, start_date: date | None = None, end_date: date | None = None, limit: int = Query(500, ge=1, le=MAX_LIST_LIMIT), db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    # Seit 1.8.9: X-Total-Count meldet die Gesamtzahl der Treffer. Liefert die Liste weniger
    # (höchstens limit, neueste zuerst), zeigt die Oberfläche "Liste gekürzt". Ein limit über
    # 2000 wird mit 422 abgelehnt, statt still gekappt zu werden.
    filters = dict(employee_id=_visible_employee_id(request, employee_id), project_id=project_id, order_id=order_id, start_date=start_date, end_date=end_date)
    response.headers["X-Total-Count"] = str(count_entries(db, **filters))
    return [TimeEntryOut.model_validate(entry_to_dict(x)) for x in list_time_entries(db, **filters, limit=limit)]


@router.get("/api/time-entries/summary", response_model=TimeEntrySummaryOut)
def get_time_entries_summary(request: Request, employee_id: int | None = None, project_id: int | None = None, order_id: int | None = None, start_date: date | None = None, end_date: date | None = None, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    """Seit 1.8.9: Summen zu GET /api/time-entries per SUM in der Datenbank, statt sie in der
    Oberfläche aus der gekürzten Liste zu bilden -- dieselben Filter, dieselbe Sichtbarkeit."""
    return TimeEntrySummaryOut.model_validate(summarize_entries(db, employee_id=_visible_employee_id(request, employee_id), project_id=project_id, order_id=order_id, start_date=start_date, end_date=end_date))


@router.get("/api/time-entries/active", response_model=TimeEntryOut | None)
def get_active_time_entry(request: Request, employee_id: int | None = None, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    resolved = _time_entry_employee_for_request(request, employee_id, db)
    row = active_time_entry(db, resolved)
    return TimeEntryOut.model_validate(entry_to_dict(row)) if row else None


@router.post("/api/time-entries", response_model=TimeEntryOut)
def create_time_entry(payload: TimeEntryManualCreate, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity,manual=True)
    employee_id = _time_entry_employee_for_request(request, payload.employee_id, db)
    _require_bookable_order(request, db, payload.order_id)
    _require_open_period(request, db, payload.work_date)
    user = getattr(request.state, "erp_user", None)
    try:
        # Seit 1.9.34: mit Von/Bis die Pause nach der Zeitregel (dieselbe Funktion wie beim Feierabend), gebucht = anwesend − Pause;
        # eine reine Dauer ist gebuchte Arbeitszeit (netto) wie bisher
        beginn = ende = None
        stunden, pause = Decimal(payload.hours or 0), payload.break_minutes
        if payload.von is not None:
            werte = nachtrag_nach_zeitregel(db, employee_id=employee_id, work_date=payload.work_date, von=payload.von, bis=payload.bis,
                                            mindestpause=payload.break_minutes)
            stunden, pause, beginn, ende = werte["netto"], werte["pause"], werte["beginn"], werte["ende"]
        row = create_manual_entry(db, employee_id=employee_id, order_id=payload.order_id, order_item_id=payload.order_item_id, work_date=payload.work_date, entry_type=payload.entry_type, activity=payload.activity, hours=stunden, break_minutes=pause, started_at=beginn, ended_at=ende, notes=payload.notes, created_by_user_id=getattr(user, "id", None))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeEntryOut.model_validate(entry_to_dict(row))


@router.post("/api/time-entries/start", response_model=TimeEntryOut)
def start_time_entry(payload: TimeTimerStart, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity)
    employee_id = _time_entry_employee_for_request(request, payload.employee_id, db)
    _require_bookable_order(request, db, payload.order_id)
    _require_open_period(request, db, (payload.started_at or berlin_now()).date())
    user = getattr(request.state, "erp_user", None)
    try:
        row = start_timer(db, employee_id=employee_id, order_id=payload.order_id, order_item_id=payload.order_item_id, entry_type=payload.entry_type, activity=payload.activity, notes=payload.notes, started_at=payload.started_at, created_by_user_id=getattr(user, "id", None))
    except OffeneZeit as exc:  # seit 1.9.35: eine Zeit von früher ist noch offen
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409 if "läuft bereits" in str(exc) else 422, detail=str(exc)) from exc
    return TimeEntryOut.model_validate(entry_to_dict(row))


@router.post("/api/time-entries/{entry_id}/stop", response_model=TimeEntryOut)
def stop_time_entry(entry_id: int, payload: TimeTimerStop, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    current = db.get(TimeEntry, entry_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeiterfassung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Du darfst diese Zeiterfassung nicht ändern.")
    _require_open_period(request, db, current.work_date)
    if laeuft_seit_frueher(current):  # seit 1.9.35: bis dahin buchte der Stopp sie bis jetzt auf den Starttag (z. B. 24 h)
        raise HTTPException(status_code=409, detail=_stopp_vom_vortag(current.started_at))
    try:
        group = group_for_entry(db, entry_id)
        user = getattr(request.state, "erp_user", None)
        # Seit 1.8.144: ohne Kennzeichen stoppt die Initiatorin nur noch ihre eigene Zeit, wie ein Mitglied (die Gruppe läuft weiter).
        if group is not None and group.status == "running" and (user is None or user.role == "admin" or user.employee_id == group.initiated_by_employee_id) and _noch_kolonnenfuehrer(request, db, group):
            # seit 1.9.34 rechnet die Pause stop_group_timer()/stop_timer() selbst nach der einen Zeitregel (pause_nach_zeitregel())
            stop_group_timer(db, group.id, ended_at=payload.ended_at or berlin_now(), break_minutes=payload.break_minutes)
            row = db.get(TimeEntry, entry_id)
        else:
            row = stop_timer(db, entry_id, ended_at=payload.ended_at or berlin_now(), break_minutes=payload.break_minutes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    loaded = db.get(TimeEntry, row.id)
    # Beziehungen fuer die Ausgabe wie beim regulaeren Stop neu laden.
    loaded = next((x for x in list_time_entries(db, employee_id=loaded.employee_id, start_date=loaded.work_date, end_date=loaded.work_date, limit=2000) if x.id==loaded.id), loaded)
    return TimeEntryOut.model_validate(entry_to_dict(loaded))


@router.post("/api/time-entries/{entry_id}/ende-nachtragen", response_model=TimeEntryOut)
def ende_nachtragen_endpunkt(entry_id: int, payload: TimeEndeNachtragen, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    """Seit 1.9.35 (Stufe 4, R1, Punkt 2): das Ende einer Zeit nachtragen, die seit einem früheren Tag läuft (vergessener Feierabend).
    Die eigene Zeit, oder die einer anderen Person nach darf_zeit_fuer_andere_buchen() (heute nur Admin; wer, steht im Verlauf). Ist der
    Monat des Starttags abgeschlossen, schließt sie nur ein Admin (wie jede Änderung dort). Gehört sie zu einer laufenden Gruppe, schließt
    sie nur der Kolonnenführer, der die Gruppe gestartet hat (oder ein Admin) -- für die ganze Gruppe, wie der Gruppen-Stopp."""
    current = _ende_nachtragen_pruefen(request, db, entry_id)
    ende = payload.ende
    if ende.tzinfo is not None:  # Beginn und Ende einer Zeitbuchung sind naive Ortszeit (Regel 20)
        ende = ende.astimezone(BERLIN).replace(tzinfo=None)
    try:
        row = ende_nachtragen(db, entry_id, ende=ende, mindestpause=payload.pause_minuten)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeEntryOut.model_validate(entry_to_dict(load_entry(db, row.id)))


@router.get("/api/time-entries/{entry_id}/ende-vorschau", response_model=TimeEndeVorschauOut)
def ende_vorschau_endpunkt(entry_id: int, ende: datetime, request: Request, pause_minuten: int = Query(0, ge=0, le=720),
                          db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    """Seit 1.9.44 (Stufe 4, R2): was „Ende nachtragen“ mit diesem Ende buchen würde -- anwesend, Pause nach der Zeitregel,
    gebucht --, ohne zu buchen (ende_vorschau(), dieselbe Rechnung wie die Buchung). Dieselben Prüfungen wie das Nachtragen."""
    _ende_nachtragen_pruefen(request, db, entry_id)
    if ende.tzinfo is not None:
        ende = ende.astimezone(BERLIN).replace(tzinfo=None)
    try:
        return ende_vorschau(db, entry_id, ende=ende, mindestpause=pause_minuten)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _ende_nachtragen_pruefen(request: Request, db: Session, entry_id: int) -> TimeEntry:
    """Rechte für Ende nachtragen und seine Vorschau (seit 1.9.35, seit 1.9.44 für beide)."""
    current = db.get(TimeEntry, entry_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeiterfassung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Du darfst diese Zeit nicht schließen.")
    if current.status != "running":
        raise HTTPException(status_code=409, detail="Diese Zeit ist schon geschlossen.")
    if not laeuft_seit_frueher(current):
        raise HTTPException(status_code=409, detail="Diese Zeit läuft seit heute – bitte normal stoppen.")
    user = getattr(request.state, "erp_user", None)
    lock = locked_until(db)
    if user is not None and user.role == ROLE_FIELD and lock is not None and current.work_date <= lock:
        raise HTTPException(status_code=403, detail=MONAT_ABGESCHLOSSEN)
    _require_open_period(request, db, current.work_date)  # für das Büro unverändert: im abgeschlossenen Zeitraum nur ein Admin
    group = group_for_entry(db, entry_id)
    gruppe_laeuft = group is not None and group.status == "running"
    if gruppe_laeuft:
        kolonnenfuehrer = (user is not None and user.employee_id == group.initiated_by_employee_id
                           and _noch_kolonnenfuehrer(request, db, group))
        if not (darf_zeit_fuer_andere_buchen(user) or kolonnenfuehrer):
            raise HTTPException(status_code=403, detail=GRUPPENZEIT_NUR_KOLONNENFUEHRER)
    return current


@router.post("/api/time-entries/{entry_id}/zeitart-wechseln", response_model=TimeEntryOut)
def zeitart_wechseln_endpunkt(entry_id: int, payload: TimeZeitartWechseln, request: Request,
                             db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    """Seit 1.9.44 (Stufe 4, R2): die laufende Zeit endet jetzt nach der Zeitregel, im selben Augenblick beginnt eine neue mit der
    neuen Zeitart auf demselben Auftrag (zeitart_wechseln()). Nur die eigene Zeit (oder nach darf_zeit_fuer_andere_buchen()), nicht im
    abgeschlossenen Zeitraum, nicht für eine Zeit von früher und nicht für eine laufende Gruppenzeit (409); dieselben Regeln wie ein
    Start (LV-Position, Tätigkeit, buchbarer Auftrag) für die neue Zeit."""
    current = db.get(TimeEntry, entry_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeiterfassung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Du darfst diese Zeiterfassung nicht ändern.")
    if current.status != "running":
        raise HTTPException(status_code=409, detail="Diese Zeiterfassung läuft nicht mehr.")
    _require_open_period(request, db, current.work_date, berlin_today())
    if laeuft_seit_frueher(current):
        raise HTTPException(status_code=409, detail=_stopp_vom_vortag(current.started_at))
    if payload.entry_type not in {a["value"] for a in zeitarten(db)}:
        raise HTTPException(status_code=422, detail="Unbekannte Zeitart.")
    _validate_time_rules(db, order_item_id=current.order_item_id, activity=current.activity)
    _require_bookable_order(request, db, current.order_id)
    user = getattr(request.state, "erp_user", None)
    try:
        row = zeitart_wechseln(db, entry_id, payload.entry_type, created_by_user_id=getattr(user, "id", None))
    except (OffeneZeit, ZeitartInGruppe) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeEntryOut.model_validate(entry_to_dict(row))


@router.put("/api/time-entries/{entry_id}", response_model=TimeEntryOut)
def put_time_entry(entry_id: int, payload: TimeEntryUpdate, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    # Seit 1.8.99 gesperrt vor dem Zusammenführen (Festlegung 1.8.96 Nr. 19 korrigiert): Auftrag und LV-Position gehören zusammen, und
    # eine gleichzeitige Korrektur der Gruppenbuchung wartet auf diese (oder umgekehrt) -- siehe app/time_tracking.py::update_group().
    current = db.get(TimeEntry, entry_id, with_for_update=True, populate_existing=True)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeitbuchung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Du darfst diese Zeitbuchung nicht ändern.")
    changes = payload.model_dump(exclude_unset=True)
    values = _merge_time_changes(current, changes)
    _validate_time_rules(db, order_item_id=values["order_item_id"], activity=values["activity"])
    employee_id = (_time_entry_employee_for_request(request, changes["employee_id"], db)
                   if "employee_id" in changes else current.employee_id)
    _require_bookable_order(request, db, values["order_id"])
    _require_open_period(request, db, current.work_date, values["work_date"])
    try:
        row = update_time_entry_row(db, entry_id, employee_id=employee_id, **values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeEntryOut.model_validate(entry_to_dict(row))


@router.delete("/api/time-entries/{entry_id}")
def remove_time_entry(entry_id: int, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    current = db.get(TimeEntry, entry_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeitbuchung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Du darfst diese Zeitbuchung nicht löschen.")
    _require_open_period(request, db, current.work_date)
    try:
        delete_time_entry_row(db, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"deleted": True}
