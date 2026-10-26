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
(app/routers/time_backoffice.py) ist davon getrennt.

Seit 1.9.89 (Stufe 4, R5a): jeder schreibende Endpunkt (dazu die Vorschauen des Buchens) traegt require_zeit_buchen aus
app/permissions.py -- Buero – Auftrag liest die Zeiten aller und aendert nichts, auch keine eigenen; fuer andere bucht nach
darf_zeit_fuer_andere_buchen() Admin und Buero – Finanzen. Die lesenden (laufende Zeit, laufende Gruppe, Pause des Tags, Kontext)
geben dem Buero jede Person.
"""

from fastapi import APIRouter
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from fastapi import Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from ..berlin_time import BERLIN, berlin_now, berlin_today
from ..meldungen import KEIN_MITARBEITER, MONAT_ABGESCHLOSSEN, NUR_VON_BIS
from ..database import get_db
from ..models import AppUser, Order, TimeEntry, TimeEntryGroup
from ..permissions import ROLE_FIELD, darf_zeit_buchen, darf_zeit_fuer_andere_buchen, has_role, require_min_role, require_zeit_buchen, zeit_nur_mit_von_bis
from .orders import require_field_order_access
from ..schemas import CrewGroupSummaryOut, CrewOut, TimeEntryManualCreate, TimeEntryOut, TimeEntrySummaryOut, TimeEntryUpdate, TimeGroupManualCreate, TimeGroupOut, TimeGroupTimerStart, TimeGroupTimerStop, TimeGroupUpdate, TimeKolonneVorschauOut, TimeEndeNachtragen, TimeEndeVorschauOut, TimePausenNeuRechnen, TimePausenVorschauOut, TimeZeitartWechseln, TimeTimerStart, TimeTimerStop, TimeTrackingSettingsOut
from ..heute import zeitarten
from ..time_backoffice import load_time_settings, locked_until, time_settings_dict
from ..time_tracking import MAX_LIST_LIMIT, active_group_for_employee, active_entry as active_time_entry, auftrag_zeiten_gesperrt, count_entries, create_group_manual_entry, create_manual_entry, crew_leader_team_ids, delete_entry as delete_time_entry_row, delete_group, ende_nachtragen, ende_vorschau, tag_stand, PausenVorschauVeraltet, pausen_neu_rechnen, pausen_vorschau, ZeitartInGruppe, zeitart_wechseln, entry_to_dict, field_time_tracking_context, laeuft_seit_frueher, load_entry, kolonne_vorschau, validate_group_members, nachtrag_nach_zeitregel, mindestpause_der_buchung, OffeneZeit, group_for_entry, group_member_ids, group_to_dict, list_crews_for_leader, list_entries as list_time_entries, list_groups_initiated_by, start_group_timer, start_timer, stop_group_timer, stop_timer, summarize_entries, time_tracking_context, update_entry as update_time_entry_row, update_group

router = APIRouter()

_any_role_dep = Depends(require_min_role(ROLE_FIELD))
# Seit 1.9.89 (Stufe 4, R5a): schreibende Endpunkte und die Vorschauen des Buchens -- Büro – Auftrag 403 (app/permissions.py)
_buchen_dep = Depends(require_zeit_buchen)

def _time_entry_employee_for_request(request: Request, requested_employee_id: int | None, db: Session, *, lesen: bool = False) -> int:
    """Für wen die Anfrage gilt. Wer nicht für andere bucht, nur für sich (ohne Mitarbeiter 403). Seit 1.9.89 mit lesen=True (laufende
    Zeit, laufende Gruppe, Pause des Tags): das Büro liest jede Person, wie _visible_employee_id() für Liste und Summen."""
    user = getattr(request.state, "erp_user", None)
    frei = darf_zeit_fuer_andere_buchen(user) or (lesen and user.role != ROLE_FIELD)
    if not frei:  # seit 1.8.152 aus app/permissions.py, dieselbe Regel wie die Oberfläche
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
    _require_order_open_for_field(request, db, order_id)


def _require_order_open_for_field(request: Request, db: Session, *order_ids: int | None) -> None:
    """Seit 1.9.81 (Stufe 4, R4 Nachtrag 3, B, Entscheidung Tobias): auf einen abgeschlossenen oder stornierten Auftrag bucht die
    Monteurin nicht -- Start, Nachtrag, Ändern (eine Buchung dorthin verschieben, dort ändern oder von dort wegschieben), Löschen,
    Kolonne, „Zeitart wechseln“, „Pausen neu rechnen“: 403 mit der Meldung aus auftrag_zeiten_gesperrt(). Eine laufende Zeit beendet sie
    immer (Stopp, Gruppen-Stopp, Ende nachtragen prüfen das nicht). Büro und Admin unverändert."""
    user = getattr(request.state, "erp_user", None)
    if user is None or user.role != ROLE_FIELD:
        return
    for order_id in dict.fromkeys(i for i in order_ids if i is not None):
        grund = auftrag_zeiten_gesperrt(db.get(Order, order_id))
        if grund:
            raise HTTPException(status_code=403, detail=grund)


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
    """Ändern/Löschen einer Gruppenbuchung: wer für andere bucht (seit 1.9.89 Admin und Büro – Finanzen), oder wer sie angelegt hat
    -- ein Monteur zusätzlich nur, solange er im Team der Buchung noch Kolonnenführer ist."""
    user = getattr(request.state, "erp_user", None)
    if darf_zeit_fuer_andere_buchen(user):
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
    """(buchender Mitarbeiter, darf für beliebige Mitglieder buchen, Konto). Seit 1.9.89 heißt das zweite: nach
    darf_zeit_fuer_andere_buchen() (Admin und Büro – Finanzen), bis dahin nur der Admin."""
    user=getattr(request.state,"erp_user",None)
    is_admin=darf_zeit_fuer_andere_buchen(user)
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
    buchbaren Aufträge -- ohne Personalnummern (field_time_tracking_context()).

    Seit 1.9.89 (Stufe 4, R5a) wie bis dahin nur der Admin: jedes Büro bekommt alle Mitarbeiter, alle offenen Aufträge und Teams, die
    gewählte Person (sonst die eigene, ohne verknüpften Mitarbeiter keine) -- auch ohne eigenen Mitarbeiter (bis dahin 403). Dazu, was
    das Konto darf: zeit_buchen (darf_zeit_buchen()), zeit_fuer_andere (darf_zeit_fuer_andere_buchen()). Der Monteur unverändert."""
    user = getattr(request.state, "erp_user", None)
    if user is not None and user.role == ROLE_FIELD:
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail=KEIN_MITARBEITER)
        resolved = user.employee_id
        result = field_time_tracking_context(db, resolved)
    else:
        resolved = employee_id or (user.employee_id if user is not None else None)
        result = time_tracking_context(db, employee_id=resolved, include_all_orders=True)
        result["zeit_buchen"] = darf_zeit_buchen(user)
        result["zeit_fuer_andere"] = darf_zeit_fuer_andere_buchen(user)
    result["current_employee_id"] = resolved
    result["is_admin"] = bool(user is None or user.role == "admin")
    return result


@router.post("/api/time-entry-groups", response_model=TimeGroupOut)
def create_time_group_manual(payload:TimeGroupManualCreate,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity,manual=True,group=True)
    actor,is_admin,user_id=_group_actor(request)
    _require_crew_leader(request,db,payload.team_id)
    _require_bookable_order(request,db,payload.order_id)
    _require_open_period(request,db,payload.work_date)
    if payload.von is None and zeit_nur_mit_von_bis(getattr(request.state,"erp_user",None)):
        # seit 1.9.63: der Kolonnenführer trägt für die Kolonne nur mit Von und Bis nach -- nach den Rechteprüfungen (403 bleibt 403)
        raise HTTPException(status_code=422,detail=NUR_VON_BIS)
    try:
        group=create_group_manual_entry(db,employee_ids=payload.employee_ids,team_id=payload.team_id,actor_employee_id=actor,is_admin=is_admin,order_id=payload.order_id,order_item_id=payload.order_item_id,work_date=payload.work_date,entry_type=payload.entry_type,activity=payload.activity,hours=payload.hours,break_minutes=payload.break_minutes,notes=payload.notes,created_by_user_id=user_id,von=payload.von,bis=payload.bis)
    except ValueError as exc:
        raise HTTPException(status_code=409 if "läuft bereits" in str(exc) else 422,detail=str(exc)) from exc
    return _group_out(request,db,group)


@router.get("/api/time-entry-groups/nachtrag-vorschau", response_model=TimeKolonneVorschauOut)
def kolonne_nachtrag_vorschau(request: Request, work_date: date, von: time, bis: time,
                              pause_minuten: int | None = Query(None, ge=0, le=720), team_id: int | None = None,
                              employee_ids: list[int] = Query(default=[]), group_id: int | None = None,
                              db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    """Seit 1.9.63 (Stufe 4, R3 Nachrunde, Punkt 1): was „Nachtrag für die Kolonne“ (team_id, employee_ids) bzw. „Für die Kolonne
    ändern“ (group_id) mit diesen Zeiten je Mitglied buchen würde -- dieselbe Rechnung wie die Buchung (kolonne_rechnen()). Liest nur.
    Rechte wie beim Buchen: Kolonnenführer der Kolonne bzw. wer die Kolonnenbuchung angelegt hat."""
    actor, is_admin, _ = _group_actor(request)
    try:
        if group_id is not None:
            group = db.get(TimeEntryGroup, group_id)
            if group is None:
                raise HTTPException(status_code=404, detail="Gruppenbuchung wurde nicht gefunden.")
            _require_group_owner(request, db, group)
            werte = kolonne_vorschau(db, group=group, work_date=work_date, von=von, bis=bis, mindestpause=pause_minuten)
        else:
            _require_crew_leader(request, db, team_id)
            employees = validate_group_members(db, employee_ids, team_id=team_id, actor_employee_id=actor, is_admin=is_admin)
            werte = kolonne_vorschau(db, employees=employees, work_date=work_date, von=von, bis=bis, mindestpause=pause_minuten)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeKolonneVorschauOut.model_validate(werte)


@router.post("/api/time-entry-groups/start", response_model=TimeGroupOut)
def start_time_group(payload:TimeGroupTimerStart,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
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
    resolved=_time_entry_employee_for_request(request,employee_id,db,lesen=True)
    user=getattr(request.state,"erp_user",None)
    # seit 1.9.89 liest das Büro jede laufende Gruppe der Person (bis dahin jeder außer dem Admin nur selbst gestartete)
    row=active_group_for_employee(db,resolved,initiated_only=has_role(user,ROLE_FIELD))
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
def put_time_group(group_id:int,payload:TimeGroupUpdate,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    # Seit 1.8.99 gesperrt vor dem Zusammenführen (Festlegung 1.8.96 Nr. 19 korrigiert): eine LV-Position gehört zum Auftrag -- ein
    # gleichzeitiger Auftragswechsel ließ sonst eine Position des alten Auftrags stehen.
    group=db.get(TimeEntryGroup,group_id,with_for_update=True,populate_existing=True)
    if group is None: raise HTTPException(status_code=404,detail="Gruppenbuchung wurde nicht gefunden.")
    _require_group_owner(request,db,group)
    _require_order_open_for_field(request,db,group.order_id)  # seit 1.9.81: auch dort ändern oder wegschieben
    changes=payload.model_dump(exclude_unset=True)
    values=_merge_time_changes(group,changes)
    _validate_time_rules(db,order_item_id=values["order_item_id"],activity=values["activity"],manual=True,group=True)
    _require_bookable_order(request,db,values["order_id"])
    _require_open_period(request,db,group.work_date,values["work_date"])
    if "hours" in changes and zeit_nur_mit_von_bis(getattr(request.state,"erp_user",None)):
        # seit 1.9.63: der Kolonnenführer ändert die Zeit der Kolonne nur über Von und Bis -- nach den Rechteprüfungen
        raise HTTPException(status_code=422,detail=NUR_VON_BIS)
    # seit 1.9.63: ohne „pause_minuten“ gilt je Mitglied die gemerkte Mindestpause (Regel 22)
    von_bis={"von":changes.get("von"),"bis":changes.get("bis"),"mindestpause":(changes.get("pause_minuten") or 0) if "pause_minuten" in changes else None}
    try:
        group,skipped=update_group(db,group_id,**values,**von_bis)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    out=_group_out(request,db,group)
    out.skipped_members=skipped
    return out


@router.delete("/api/time-entry-groups/{group_id}")
def remove_time_group(group_id:int,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    group=db.get(TimeEntryGroup,group_id)
    if group is None: raise HTTPException(status_code=404,detail="Gruppenbuchung wurde nicht gefunden.")
    _require_group_owner(request,db,group)
    _require_order_open_for_field(request,db,group.order_id)  # seit 1.9.81
    _require_open_period(request,db,group.work_date)
    try:
        kept=delete_group(db,group_id)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {"deleted": True, "kept_members": kept}


@router.post("/api/time-entry-groups/{group_id}/stop", response_model=TimeGroupOut)
def stop_time_group(group_id:int,payload:TimeGroupTimerStop,request:Request,db:Session=Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    group=db.get(TimeEntryGroup,group_id)
    if group is None: raise HTTPException(status_code=404,detail="Gruppenbuchung wurde nicht gefunden.")
    user=getattr(request.state,"erp_user",None)
    if not darf_zeit_fuer_andere_buchen(user) and user.employee_id!=group.initiated_by_employee_id:  # seit 1.9.89 auch Büro – Finanzen
        raise HTTPException(status_code=403,detail="Die ganze Gruppe stoppt, wer sie gestartet hat – oder Admin und Büro – Finanzen.")
    if not _noch_kolonnenfuehrer(request,db,group):
        raise HTTPException(status_code=403,detail=CREW_LEADER_ONLY)
    _require_open_period(request,db,group.work_date)
    if group.status=="running" and group.started_at is not None and group.started_at.date()<berlin_today():  # seit 1.9.35
        raise HTTPException(status_code=409,detail=_stopp_vom_vortag(group.started_at))
    try:
        group=stop_group_timer(db,group_id,ended_at=payload.ended_at or berlin_now(),break_minutes=payload.break_minutes)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    out=_group_out(request,db,group)
    if user is not None and user.employee_id in group_member_ids(db,group.id):  # seit 1.9.48: der eigene Tag dessen, der stoppt
        out=out.model_copy(update=tag_stand(db,user.employee_id,group.work_date))
    return out


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
    resolved = _time_entry_employee_for_request(request, employee_id, db, lesen=True)
    row = active_time_entry(db, resolved)
    return TimeEntryOut.model_validate(entry_to_dict(row)) if row else None


@router.post("/api/time-entries", response_model=TimeEntryOut)
def create_time_entry(payload: TimeEntryManualCreate, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    _validate_time_rules(db,order_item_id=payload.order_item_id,activity=payload.activity,manual=True)
    employee_id = _time_entry_employee_for_request(request, payload.employee_id, db)
    _require_bookable_order(request, db, payload.order_id)
    _require_open_period(request, db, payload.work_date)
    user = getattr(request.state, "erp_user", None)
    if payload.von is None and zeit_nur_mit_von_bis(user):
        # seit 1.9.60: die Monteurin nur mit Von und Bis -- nach den Rechteprüfungen (was nicht erlaubt ist, bleibt 403)
        raise HTTPException(status_code=422, detail=NUR_VON_BIS)
    try:
        # Seit 1.9.34: mit Von/Bis die Pause nach der Zeitregel (dieselbe Funktion wie beim Feierabend), gebucht = anwesend − Pause;
        # eine reine Dauer ist gebuchte Arbeitszeit (netto) wie bisher
        beginn = ende = None
        stunden, pause = Decimal(payload.hours or 0), payload.break_minutes
        if payload.von is not None:
            werte = nachtrag_nach_zeitregel(db, employee_id=employee_id, work_date=payload.work_date, von=payload.von, bis=payload.bis,
                                            mindestpause=payload.break_minutes)
            stunden, pause, beginn, ende = werte["netto"], werte["pause"], werte["beginn"], werte["ende"]
        row = create_manual_entry(db, employee_id=employee_id, order_id=payload.order_id, order_item_id=payload.order_item_id, work_date=payload.work_date, entry_type=payload.entry_type, activity=payload.activity, hours=stunden, break_minutes=pause, min_break_minutes=payload.break_minutes, started_at=beginn, ended_at=ende, notes=payload.notes, created_by_user_id=getattr(user, "id", None))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _mit_tag(db, entry_to_dict(row))


@router.post("/api/time-entries/start", response_model=TimeEntryOut)
def start_time_entry(payload: TimeTimerStart, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
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
def stop_time_entry(entry_id: int, payload: TimeTimerStop, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
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
        if group is not None and group.status == "running" and (darf_zeit_fuer_andere_buchen(user) or user.employee_id == group.initiated_by_employee_id) and _noch_kolonnenfuehrer(request, db, group):
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
    return _mit_tag(db, entry_to_dict(loaded))


@router.post("/api/time-entries/{entry_id}/ende-nachtragen", response_model=TimeEntryOut)
def ende_nachtragen_endpunkt(entry_id: int, payload: TimeEndeNachtragen, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    """Seit 1.9.35 (Stufe 4, R1, Punkt 2): das Ende einer Zeit nachtragen, die seit einem früheren Tag läuft (vergessener Feierabend).
    Die eigene Zeit, oder die einer anderen Person nach darf_zeit_fuer_andere_buchen() (seit 1.9.89 Admin und Büro – Finanzen; wer, steht
    im Verlauf). Ist der Monat des Starttags abgeschlossen, schließt sie nur ein Admin (wie jede Änderung dort). Gehört sie zu einer
    laufenden Gruppe, schließt sie nur der Kolonnenführer, der die Gruppe gestartet hat (oder wer für andere bucht) -- für die ganze
    Gruppe, wie der Gruppen-Stopp."""
    current = _ende_nachtragen_pruefen(request, db, entry_id)
    ende = payload.ende
    if ende.tzinfo is not None:  # Beginn und Ende einer Zeitbuchung sind naive Ortszeit (Regel 20)
        ende = ende.astimezone(BERLIN).replace(tzinfo=None)
    try:
        row = ende_nachtragen(db, entry_id, ende=ende, mindestpause=payload.pause_minuten)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _mit_tag(db, entry_to_dict(load_entry(db, row.id)))


@router.get("/api/time-entries/nachtrag-vorschau", response_model=TimeEndeVorschauOut)
def nachtrag_vorschau(request: Request, work_date: date, von: time, bis: time, pause_minuten: int | None = Query(None, ge=0, le=720),
                      entry_id: int | None = None, employee_id: int | None = None,
                      db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    """Seit 1.9.57 (Stufe 4, R3): was „Zeit nachtragen“ (bzw. mit entry_id „Ändern“) mit diesen Zeiten buchen würde -- dieselbe
    Rechnung wie die Buchung (nachtrag_nach_zeitregel(): Pause aus dem Tag, beim Ändern ohne die alte Fassung, Rundung der Zeitregeln,
    „Tag zusammen“). Liest nur. Mitarbeiter wie beim Buchen; die zu ändernde Buchung muss der Person gehören und änderbar sein."""
    mitarbeiter = _time_entry_employee_for_request(request, employee_id, db)
    ohne_id = None
    if entry_id is not None:
        row = db.get(TimeEntry, entry_id)
        if row is None or row.employee_id != mitarbeiter:
            raise HTTPException(status_code=404, detail="Zeitbuchung nicht gefunden.")
        if not _time_entry_can_edit(request, row):
            raise HTTPException(status_code=403, detail="Du darfst diese Zeitbuchung nicht ändern.")
        ohne_id = row.id
    if pause_minuten is None:  # seit 1.9.62 wie PUT: beim Ändern ohne Angabe die eingetragene Mindestpause der Buchung, sonst 0
        pause_minuten = mindestpause_der_buchung(row) if ohne_id is not None else 0
    try:
        werte = nachtrag_nach_zeitregel(db, employee_id=mitarbeiter, work_date=work_date, von=von, bis=bis, mindestpause=pause_minuten,
                                        ohne_id=ohne_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeEndeVorschauOut(anwesend=werte["anwesend"], pause=werte["pause"], gebucht=werte["gebucht"],
                               tag_zusammen=werte["tag_zusammen"], tag_buchungen=werte["tag_buchungen"])


@router.get("/api/time-entries/tagespause", response_model=TimePausenVorschauOut)
def tagespause(request: Request, work_date: date, employee_id: int | None = None,
               db: Session = Depends(get_db, scope="function"), _role: AppUser = _any_role_dep):
    """Seit 1.9.57 (Stufe 4, R3, Punkt 5): passt die abgezogene Pause des Tags noch zur Zeitregel, und was würde „Pausen neu rechnen“
    je Buchung ändern (time_tracking.pausen_vorschau())? Liest nur -- seit 1.9.89 für das Büro jede Person."""
    return pausen_vorschau(db, _time_entry_employee_for_request(request, employee_id, db, lesen=True), work_date)


@router.post("/api/time-entries/pausen-neu-rechnen", response_model=TimePausenVorschauOut)
def pausen_neu_rechnen_endpunkt(payload: TimePausenNeuRechnen, request: Request, db: Session = Depends(get_db, scope="function"),
                                _role: AppUser = _buchen_dep):
    """Seit 1.9.57 (Stufe 4, R3, Punkt 5): bucht genau die Vorschau der Seite (je Buchung die neue Pause) -- weicht die Rechnung jetzt
    ab, 409; im abgeschlossenen Zeitraum nur ein Admin (wie jede Änderung). Nie von selbst."""
    mitarbeiter = _time_entry_employee_for_request(request, payload.employee_id, db)
    _require_open_period(request, db, payload.work_date)
    # seit 1.9.81: neu rechnen ändert Pause und Stunden der genannten Buchungen -- keine eines abgeschlossenen Auftrags (Monteurin)
    buchungen = [db.get(TimeEntry, b.id) for b in payload.buchungen]
    _require_order_open_for_field(request, db, *(e.order_id for e in buchungen if e is not None and e.employee_id == mitarbeiter))
    try:
        return pausen_neu_rechnen(db, mitarbeiter, payload.work_date, {b.id: b.pause for b in payload.buchungen})
    except PausenVorschauVeraltet as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/time-entries/{entry_id}/ende-vorschau", response_model=TimeEndeVorschauOut)
def ende_vorschau_endpunkt(entry_id: int, ende: datetime, request: Request, pause_minuten: int = Query(0, ge=0, le=720),
                          db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
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
                             db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
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
    return _mit_tag(db, entry_to_dict(row))


def _mit_tag(db: Session, data: dict) -> TimeEntryOut:
    """Seit 1.9.48 (Stufe 4, R2 Nachrunde): die Antwort auf eine Buchung nennt „Tag zusammen“ (tag_stand())."""
    return TimeEntryOut.model_validate({**data, **tag_stand(db, data["employee_id"], data["work_date"])})


@router.put("/api/time-entries/{entry_id}", response_model=TimeEntryOut)
def put_time_entry(entry_id: int, payload: TimeEntryUpdate, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    # Seit 1.8.99 gesperrt vor dem Zusammenführen (Festlegung 1.8.96 Nr. 19 korrigiert): Auftrag und LV-Position gehören zusammen, und
    # eine gleichzeitige Korrektur der Gruppenbuchung wartet auf diese (oder umgekehrt) -- siehe app/time_tracking.py::update_group().
    current = db.get(TimeEntry, entry_id, with_for_update=True, populate_existing=True)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeitbuchung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Du darfst diese Zeitbuchung nicht ändern.")
    _require_order_open_for_field(request, db, current.order_id)  # seit 1.9.81: auch dort ändern oder wegschieben
    changes = payload.model_dump(exclude_unset=True)
    values = _merge_time_changes(current, changes)
    _validate_time_rules(db, order_item_id=values["order_item_id"], activity=values["activity"])
    employee_id = (_time_entry_employee_for_request(request, changes["employee_id"], db)
                   if "employee_id" in changes else current.employee_id)
    _require_bookable_order(request, db, values["order_id"])
    _require_open_period(request, db, current.work_date, values["work_date"])
    if "hours" in changes and zeit_nur_mit_von_bis(getattr(request.state, "erp_user", None)):
        # seit 1.9.60: die Monteurin ändert die Zeit nur über Von und Bis -- nach den Rechteprüfungen (403 bleibt 403)
        raise HTTPException(status_code=422, detail=NUR_VON_BIS)
    # Seit 1.9.57 (Stufe 4, R3): mit Von und Bis wie ein Nachtrag -- Pause aus dem Tag ohne die alte Fassung, Rundung der Zeitregeln
    # Seit 1.9.62: ohne „pause_minuten“ gilt die eingetragene Mindestpause der Buchung weiter (Regel 22; eine Buchung von vor 1.9.62: die
    # abgezogene Pause) -- bis 1.9.61 hieß ohne Angabe 0; eine Dauer mit Stunden oder Pause (Büro) merkt die neue Pause als Mindestpause
    mindest = (changes.get("pause_minuten") or 0) if "pause_minuten" in changes else mindestpause_der_buchung(current)
    von_bis = {"von": changes.get("von"), "bis": changes.get("bis"), "mindestpause": mindest}
    merken = values["break_minutes"] if changes.keys() & {"hours", "break_minutes"} else None
    try:
        row = update_time_entry_row(db, entry_id, employee_id=employee_id, **values, **von_bis, min_break_minutes=merken)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _mit_tag(db, entry_to_dict(row))


@router.delete("/api/time-entries/{entry_id}")
def remove_time_entry(entry_id: int, request: Request, db: Session = Depends(get_db, scope="function"), _role: AppUser = _buchen_dep):
    current = db.get(TimeEntry, entry_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Zeitbuchung nicht gefunden.")
    if not _time_entry_can_edit(request, current):
        raise HTTPException(status_code=403, detail="Du darfst diese Zeitbuchung nicht löschen.")
    _require_order_open_for_field(request, db, current.order_id)  # seit 1.9.81
    _require_open_period(request, db, current.work_date)
    try:
        delete_time_entry_row(db, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"deleted": True}
