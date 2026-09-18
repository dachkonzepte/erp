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
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..planning import GERMAN_STATES, create_slot, delete_slot, get_or_create_planning_settings, get_or_create_region_settings, planning_board, planning_settings_dict, planning_suggestion, slot_to_dict, sync_school_holidays, update_planning_settings, update_slot
from ..schemas import EmployeeAbsenceCreate, EmployeeAbsenceOut, PlanningHolidayCreate, PlanningHolidayOut, PlanningSettingsOut, PlanningSettingsUpdate, PlanningSlotCreate, PlanningSlotUpdate, PlanningSuggestionRequest

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Plantafel-Verwaltung (Kapazität, Feiertage,
# Abwesenheiten, Slots) ist Büro-/Admin-Bereich -- geprüft, kein Endpunkt dieser Datei wird von
# einer Monteur-Vorlage aufgerufen (die Monteursansicht liest ihre eigenen Einsätze über den
# unabhängigen, bereits ausgenommenen GET /api/field-view/today).
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))

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


@router.get("/api/planning/absences", response_model=list[EmployeeAbsenceOut])
def list_employee_absences(start:date|None=None,end:date|None=None,employee_id:int|None=None,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    stmt=select(EmployeeAbsence).options(selectinload(EmployeeAbsence.employee)).order_by(EmployeeAbsence.start_date.desc(),EmployeeAbsence.id.desc())
    if start is not None: stmt=stmt.where(EmployeeAbsence.end_date>=start)
    if end is not None: stmt=stmt.where(EmployeeAbsence.start_date<=end)
    if employee_id is not None: stmt=stmt.where(EmployeeAbsence.employee_id==employee_id)
    rows=db.scalars(stmt).all()
    return [EmployeeAbsenceOut(id=x.id,employee_id=x.employee_id,employee_name=f"{x.employee.first_name} {x.employee.last_name}".strip() if x.employee else None,absence_type=x.absence_type,start_date=x.start_date,end_date=x.end_date,notes=x.notes) for x in rows]


@router.post("/api/planning/absences", response_model=EmployeeAbsenceOut)
def create_employee_absence(payload:EmployeeAbsenceCreate,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    emp=db.get(Employee,payload.employee_id)
    if emp is None: raise HTTPException(status_code=404,detail="Mitarbeiter nicht gefunden.")
    row=EmployeeAbsence(**payload.model_dump()); db.add(row); db.commit(); db.refresh(row)
    return EmployeeAbsenceOut(id=row.id,employee_id=row.employee_id,employee_name=f"{emp.first_name} {emp.last_name}".strip(),absence_type=row.absence_type,start_date=row.start_date,end_date=row.end_date,notes=row.notes)


@router.put("/api/planning/absences/{absence_id}", response_model=EmployeeAbsenceOut)
def update_employee_absence(absence_id:int,payload:EmployeeAbsenceCreate,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    row=db.get(EmployeeAbsence,absence_id)
    if row is None: raise HTTPException(status_code=404,detail="Abwesenheit nicht gefunden.")
    emp=db.get(Employee,payload.employee_id)
    if emp is None: raise HTTPException(status_code=404,detail="Mitarbeiter nicht gefunden.")
    for k,v in payload.model_dump().items(): setattr(row,k,v)
    db.commit(); db.refresh(row)
    return EmployeeAbsenceOut(id=row.id,employee_id=row.employee_id,employee_name=f"{emp.first_name} {emp.last_name}".strip(),absence_type=row.absence_type,start_date=row.start_date,end_date=row.end_date,notes=row.notes)


@router.delete("/api/planning/absences/{absence_id}")
def delete_employee_absence(absence_id:int,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    row=db.get(EmployeeAbsence,absence_id)
    if row is None: raise HTTPException(status_code=404,detail="Abwesenheit nicht gefunden.")
    db.delete(row); db.commit(); return {"deleted":True}


@router.post("/api/planning/suggestion")
def get_planning_suggestion(payload:PlanningSuggestionRequest,db:Session=Depends(get_db),_role:AppUser=_role_dep):
    try: return planning_suggestion(db,**payload.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.get("/api/planning")
def get_planning_board(start: date, end: date, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        return planning_board(db, start, end)
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
