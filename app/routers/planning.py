"""Router: planning

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 16 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from datetime import date
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import AppUser, Employee, EmployeeAbsence, PlanningHoliday
from ..permissions import ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, has_min_role, require_min_role
from ..planning import GERMAN_STATES, create_slot, delete_slot, get_or_create_planning_settings, get_or_create_region_settings, planning_board, planning_settings_dict, planning_suggestion, slot_to_dict, sync_school_holidays, update_planning_settings, update_slot
from ..schemas import EmployeeAbsenceCreate, EmployeeAbsenceOut, EmployeeAbsencePlanningOut, EmployeeAbsenceUpdate, PlanningHolidayCreate, PlanningHolidayOut, PlanningSettingsOut, PlanningSettingsUpdate, PlanningSlotCreate, PlanningSlotUpdate, PlanningSuggestionRequest

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Plantafel-Verwaltung (Kapazität, Feiertage,
# Abwesenheiten, Slots) ist Büro-/Admin-Bereich -- geprüft, kein Endpunkt dieser Datei wird von
# einer Monteur-Vorlage aufgerufen (die Monteursansicht liest ihre eigenen Einsätze über den
# unabhängigen, bereits ausgenommenen GET /api/field-view/today).
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))

# Krankheitssichtbarkeit (siehe CLAUDE.md): buero_auftrag sieht bei jeder Abwesenheit --
# egal wer/wann sie angelegt hat, auch die eigene soeben erstellte -- ausschließlich "abwesend"
# mit Zeitraum, nie Art (absence_type/absence_category) oder Grund (notes). buero_finanzen/admin
# sehen unverändert alles. "Einmal eintragen, nie wieder lesen": buero_auftrag darf beim Anlegen
# weiterhin die echte Art eintippen (z. B. nach einem Telefonanruf), das Ergebnis der eigenen
# Anfrage zeigt sie danach aber ebenso wenig wie jede spätere Abfrage.
ABSENCE_FIELD_NAMES = {"absence_type", "absence_category", "notes"}


def _absence_out_for_role(role: AppUser, data: dict):
    if has_min_role(role, ROLE_OFFICE_FINANZEN):
        return EmployeeAbsenceOut.model_validate(data)
    return EmployeeAbsencePlanningOut.model_validate(data)


def _redact_board_absences(board: dict, role: AppUser) -> dict:
    """Entfernt Art/Grund aus JEDER Stelle, an der GET /api/planning Abwesenheiten einbettet --
    Konflikt-Labels je Slot, Team-/Mitarbeiter-Tageskapazität, die Backoffice-Abwesenheitsliste
    selbst (board["absences"], die tatsächliche Datenquelle von planning.html::renderAbsences()).
    Für buero_finanzen/admin unverändert, nur die internen label_redacted-Hilfsfelder werden
    aufgeräumt, damit sie nicht versehentlich in der Antwort auftauchen."""
    for slot in board.get("slots", []):
        for conflict in slot.get("conflicts", []):
            if has_min_role(role, ROLE_OFFICE_FINANZEN):
                conflict.pop("label_redacted", None)
            elif conflict.get("type") == "absence":
                conflict["label"] = conflict.pop("label_redacted", conflict["label"])
            else:
                conflict.pop("label_redacted", None)
    if has_min_role(role, ROLE_OFFICE_FINANZEN):
        return board
    for team_rows in board.get("team_capacity", {}).values():
        for day_row in team_rows.values():
            for entry in day_row.get("absences", []):
                entry.pop("type", None)
    for emp_rows in board.get("employee_capacity", {}).values():
        for day_row in emp_rows.values():
            if day_row.get("absence"):
                day_row["absence"] = "abwesend"
    board["absences"] = [
        {"id": a["id"], "employee_id": a["employee_id"], "employee_name": a["employee_name"],
         "start_date": a["start_date"], "end_date": a["end_date"]}
        for a in board.get("absences", [])
    ]
    return board


def _redact_suggestion_absences(suggestion: dict, role: AppUser) -> dict:
    if has_min_role(role, ROLE_OFFICE_FINANZEN):
        return suggestion
    for day_row in suggestion.get("days", []):
        for entry in day_row.get("absent_employees", []):
            entry.pop("type", None)
    return suggestion

@router.get("/api/planning/settings", response_model=PlanningSettingsOut)
def get_planning_capacity_settings(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return planning_settings_dict(get_or_create_planning_settings(db), db)


@router.put("/api/planning/settings", response_model=PlanningSettingsOut)
def put_planning_capacity_settings(payload: PlanningSettingsUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    row = update_planning_settings(db, **payload.model_dump())
    return planning_settings_dict(row, db)


@router.post("/api/planning/school-holidays/sync")
def sync_planning_school_holidays(start_year: int | None = None, years: int = 3, force: bool = False, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    region = get_or_create_region_settings(db)
    start_year = start_year or date.today().year
    years = max(1, min(int(years), 6))
    results = [sync_school_holidays(db, region.federal_state_code, year, force=force) for year in range(start_year, start_year + years)]
    return {"state_code": region.federal_state_code, "state_name": GERMAN_STATES.get(region.federal_state_code), "results": results}


@router.get("/api/planning/holidays", response_model=list[PlanningHolidayOut])
def list_planning_holidays(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return db.scalars(select(PlanningHoliday).order_by(PlanningHoliday.holiday_date)).all()


@router.post("/api/planning/holidays", response_model=PlanningHolidayOut)
def create_planning_holiday(payload: PlanningHolidayCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    if db.scalar(select(PlanningHoliday).where(PlanningHoliday.holiday_date == payload.holiday_date)):
        raise HTTPException(status_code=409, detail="Für dieses Datum ist bereits ein Feiertag / betriebsfreier Tag hinterlegt.")
    row=PlanningHoliday(**payload.model_dump()); db.add(row); db.commit(); db.refresh(row); return row


@router.put("/api/planning/holidays/{holiday_id}", response_model=PlanningHolidayOut)
def update_planning_holiday(holiday_id:int, payload:PlanningHolidayCreate, db:Session=Depends(get_db),_role:AppUser=_role_dep):
    row=db.get(PlanningHoliday,holiday_id)
    if row is None: raise HTTPException(status_code=404,detail="Feiertag / betriebsfreier Tag nicht gefunden.")
    duplicate=db.scalar(select(PlanningHoliday).where(PlanningHoliday.holiday_date==payload.holiday_date, PlanningHoliday.id!=holiday_id))
    if duplicate: raise HTTPException(status_code=409,detail="Für dieses Datum ist bereits ein Feiertag / betriebsfreier Tag hinterlegt.")
    for k,v in payload.model_dump().items(): setattr(row,k,v)
    db.commit(); db.refresh(row); return row


@router.delete("/api/planning/holidays/{holiday_id}")
def delete_planning_holiday(holiday_id:int, db:Session=Depends(get_db),_role:AppUser=_role_dep):
    row=db.get(PlanningHoliday,holiday_id)
    if row is None: raise HTTPException(status_code=404,detail="Feiertag / betriebsfreier Tag nicht gefunden.")
    db.delete(row); db.commit(); return {"deleted":True}


@router.get("/api/planning/absences", response_model=list[EmployeeAbsenceOut] | list[EmployeeAbsencePlanningOut])
def list_employee_absences(start:date|None=None,end:date|None=None,employee_id:int|None=None,absence_category:str|None=None,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    stmt=select(EmployeeAbsence).options(selectinload(EmployeeAbsence.employee)).order_by(EmployeeAbsence.start_date.desc(),EmployeeAbsence.id.desc())
    if start is not None: stmt=stmt.where(EmployeeAbsence.end_date>=start)
    if end is not None: stmt=stmt.where(EmployeeAbsence.start_date<=end)
    if employee_id is not None: stmt=stmt.where(EmployeeAbsence.employee_id==employee_id)
    if absence_category is not None: stmt=stmt.where(EmployeeAbsence.absence_category==absence_category)
    rows=db.scalars(stmt).all()
    return [_absence_out_for_role(_role, {"id":x.id,"employee_id":x.employee_id,"employee_name":f"{x.employee.first_name} {x.employee.last_name}".strip() if x.employee else None,"absence_type":x.absence_type,"absence_category":x.absence_category,"start_date":x.start_date,"end_date":x.end_date,"notes":x.notes}) for x in rows]


@router.post("/api/planning/absences", response_model=EmployeeAbsenceOut | EmployeeAbsencePlanningOut)
def create_employee_absence(payload:EmployeeAbsenceCreate,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    emp=db.get(Employee,payload.employee_id)
    if emp is None: raise HTTPException(status_code=404,detail="Mitarbeiter nicht gefunden.")
    row=EmployeeAbsence(**payload.model_dump()); db.add(row); db.commit(); db.refresh(row)
    # "Einmal eintragen, nie wieder lesen" (siehe CLAUDE.md "Krankheitssichtbarkeit"): buero_auftrag
    # darf Art/Grund hier weiterhin eintippen (payload bleibt ungefiltert), bekommt die soeben
    # selbst angelegte Zeile in der ANTWORT aber bereits redigiert zurück -- keine Ausnahme "aber
    # ich habe es doch gerade selbst getippt".
    return _absence_out_for_role(_role, {"id":row.id,"employee_id":row.employee_id,"employee_name":f"{emp.first_name} {emp.last_name}".strip(),"absence_type":row.absence_type,"absence_category":row.absence_category,"start_date":row.start_date,"end_date":row.end_date,"notes":row.notes})


@router.put("/api/planning/absences/{absence_id}", response_model=EmployeeAbsenceOut | EmployeeAbsencePlanningOut)
def update_employee_absence(absence_id:int,payload:EmployeeAbsenceUpdate,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    row=db.get(EmployeeAbsence,absence_id)
    if row is None: raise HTTPException(status_code=404,detail="Abwesenheit nicht gefunden.")
    fields=payload.model_dump(exclude_unset=True)
    if "employee_id" in fields:
        emp=db.get(Employee,fields["employee_id"])
        if emp is None: raise HTTPException(status_code=404,detail="Mitarbeiter nicht gefunden.")
    # Echtes Teil-Update (nur tatsächlich mitgesendete Felder) -- buero_auftrag sendet
    # absence_type/absence_category/notes gar nicht erst mit (das Formular zeigt sie nicht mehr
    # an, siehe planning.html), ein Blanket-Overwrite hätte sie sonst stillschweigend auf einen
    # Leerwert zurückgesetzt (dieselbe Gefahrenklasse wie bei upsert_roof_layer() vor 1.2.19).
    new_start=fields.get("start_date",row.start_date); new_end=fields.get("end_date",row.end_date)
    if new_end<new_start: raise HTTPException(status_code=422,detail="Enddatum darf nicht vor dem Startdatum liegen.")
    for k,v in fields.items(): setattr(row,k,v)
    db.commit(); db.refresh(row)
    emp=row.employee
    return _absence_out_for_role(_role, {"id":row.id,"employee_id":row.employee_id,"employee_name":f"{emp.first_name} {emp.last_name}".strip() if emp else None,"absence_type":row.absence_type,"absence_category":row.absence_category,"start_date":row.start_date,"end_date":row.end_date,"notes":row.notes})


@router.delete("/api/planning/absences/{absence_id}")
def delete_employee_absence(absence_id:int,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    row=db.get(EmployeeAbsence,absence_id)
    if row is None: raise HTTPException(status_code=404,detail="Abwesenheit nicht gefunden.")
    db.delete(row); db.commit(); return {"deleted":True}


@router.post("/api/planning/suggestion")
def get_planning_suggestion(payload:PlanningSuggestionRequest,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    try: return _redact_suggestion_absences(planning_suggestion(db,**payload.model_dump()), _role)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.get("/api/planning")
def get_planning_board(start: date, end: date, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        return _redact_board_absences(planning_board(db, start, end), _role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/planning/slots")
def create_planning_slot(payload: PlanningSlotCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        slot = create_slot(db, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return slot_to_dict(slot, db=db)


@router.put("/api/planning/slots/{slot_id}")
def put_planning_slot(slot_id: int, payload: PlanningSlotUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        slot = update_slot(db, slot_id, **payload.model_dump())
    except ValueError as exc:
        code = 404 if "nicht gefunden" in str(exc) else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return slot_to_dict(slot, db=db)


@router.delete("/api/planning/slots/{slot_id}")
def remove_planning_slot(slot_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        prep_id = delete_slot(db, slot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True, "preparation_id": prep_id}
