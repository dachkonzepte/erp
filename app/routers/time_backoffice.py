"""Router: time_backoffice

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 15 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.

Rechtekonzept "Vier Rollen" Etappe 2 (seit 1.4.8, siehe CLAUDE.md): von require_admin() auf
require_min_role(ROLE_OFFICE_AUFTRAG) angehoben -- Betreiberbegründung: Zeiten der Kolonnen
korrigieren/Abwesenheiten verwalten gehört zum laufenden, von buero_auftrag geführten Betrieb.
Vor der Anhebung geprüft (wie verlangt), ob dabei Vergütung mitsichtbar wird -- app/time_backoffice.py
gelesen: payroll_rows()/EmployeePayrollSettingsOut tragen nur datev_personnel_number/
payroll_export_enabled (eine Personalnummer-Zuordnung fürs DATEV-Mapping, kein Betrag);
backoffice_summary()/build_timesheet_pdf()/build_time_csv() zeigen ausschließlich Stunden;
build_datev_export()s "Lohnart" ist eine DATEV-Buchungskategorie (Zeitart-zu-Buchungscode-
Zuordnung), kein €-Betrag. Kein einziges €-Vergütungsfeld in dieser Datei -- nichts zu
verengen, die gesamte Datei hebt sich deshalb einheitlich auf buero_auftrag.
"""

from datetime import date

from fastapi import APIRouter, Depends
from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import EmployeePayrollSettingsOut, EmployeePayrollSettingsUpdate, EmployeeWorkTimeModelBulkUpdate, EmployeeWorkTimeModelUpdate, TimeTrackingSettingsOut, TimeTrackingSettingsUpdate, WorkTimeModelUpsert
from ..time_backoffice import backoffice_summary, build_datev_export, build_time_csv, build_timesheet_pdf, get_or_create_time_settings, payroll_rows, set_employee_payroll, time_settings_dict, update_time_settings
from ..work_time_models import bulk_set_employee_model, delete_model as delete_work_time_model, employee_model_rows, list_models as list_work_time_models, save_model as save_work_time_model, set_employee_model

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Das Zeiterfassungs-Backoffice ist nur für Büro und Administratoren verfügbar."))


@router.get("/api/time-backoffice/settings", response_model=TimeTrackingSettingsOut)
def get_time_backoffice_settings(db: Session = Depends(get_db), _role=_role_dep):
    return TimeTrackingSettingsOut.model_validate(time_settings_dict(get_or_create_time_settings(db), db))


@router.put("/api/time-backoffice/settings", response_model=TimeTrackingSettingsOut)
def put_time_backoffice_settings(payload: TimeTrackingSettingsUpdate, db: Session = Depends(get_db), _role=_role_dep):
    try:
        row = update_time_settings(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeTrackingSettingsOut.model_validate(time_settings_dict(row, db))


@router.get("/api/time-backoffice/work-time-models")
def get_work_time_models(db: Session = Depends(get_db), _role=_role_dep):
    return list_work_time_models(db)


@router.post("/api/time-backoffice/work-time-models")
def create_work_time_model(payload: WorkTimeModelUpsert, db: Session = Depends(get_db), _role=_role_dep):
    try:
        row=save_work_time_model(db,model_id=None,name=payload.name,code=payload.code,daily_target_hours=payload.daily_target_hours,valid_from_week=payload.valid_from_week,valid_to_week=payload.valid_to_week,description=payload.description,active=payload.active,sort_order=payload.sort_order,break_rules=[x.model_dump() for x in payload.break_rules])
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {x["id"]:x for x in list_work_time_models(db)}.get(row.id)


@router.put("/api/time-backoffice/work-time-models/{model_id}")
def put_work_time_model(model_id: int, payload: WorkTimeModelUpsert, db: Session = Depends(get_db), _role=_role_dep):
    try:
        row=save_work_time_model(db,model_id=model_id,name=payload.name,code=payload.code,daily_target_hours=payload.daily_target_hours,valid_from_week=payload.valid_from_week,valid_to_week=payload.valid_to_week,description=payload.description,active=payload.active,sort_order=payload.sort_order,break_rules=[x.model_dump() for x in payload.break_rules])
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {x["id"]:x for x in list_work_time_models(db)}.get(row.id)


@router.delete("/api/time-backoffice/work-time-models/{model_id}")
def remove_work_time_model(model_id: int, db: Session = Depends(get_db), _role=_role_dep):
    try: delete_work_time_model(db,model_id)
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
    return {"ok":True}


@router.get("/api/time-backoffice/work-time-assignments")
def get_work_time_assignments(db: Session = Depends(get_db), _role=_role_dep):
    return employee_model_rows(db)


@router.put("/api/time-backoffice/work-time-assignments/{employee_id}")
def put_work_time_assignment(employee_id: int, payload: EmployeeWorkTimeModelUpdate, db: Session = Depends(get_db), _role=_role_dep):
    try: return set_employee_model(db,employee_id,payload.model_id)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.post("/api/time-backoffice/work-time-assignments/bulk")
def put_work_time_assignments_bulk(payload: EmployeeWorkTimeModelBulkUpdate, db: Session = Depends(get_db), _role=_role_dep):
    try: return bulk_set_employee_model(db,payload.employee_ids,payload.model_id)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.get("/api/time-backoffice/payroll-employees", response_model=list[EmployeePayrollSettingsOut])
def get_time_payroll_employees(db: Session = Depends(get_db), _role=_role_dep):
    return [EmployeePayrollSettingsOut.model_validate(x) for x in payroll_rows(db)]


@router.put("/api/time-backoffice/payroll-employees/{employee_id}", response_model=EmployeePayrollSettingsOut)
def put_time_payroll_employee(employee_id: int, payload: EmployeePayrollSettingsUpdate, db: Session = Depends(get_db), _role=_role_dep):
    try: row=set_employee_payroll(db,employee_id,payload)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return EmployeePayrollSettingsOut.model_validate(row)


@router.get("/api/time-backoffice/summary")
def get_time_backoffice_summary(start_date: date, end_date: date, employee_id: int | None = None, db: Session = Depends(get_db), _role=_role_dep):
    return backoffice_summary(db,start_date,end_date,employee_id)


@router.get("/api/time-backoffice/timesheet.pdf")
def export_time_sheet_pdf(start_date: date, end_date: date, employee_id: int | None = None, db: Session = Depends(get_db), _role=_role_dep):
    data=build_timesheet_pdf(db,start_date,end_date,employee_id)
    filename=f"Stundenzettel_{start_date.isoformat()}_{end_date.isoformat()}.pdf"
    return Response(content=data,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{filename}"'})


@router.get("/api/time-backoffice/timesheet.csv")
def export_time_sheet_csv(start_date: date, end_date: date, employee_id: int | None = None, db: Session = Depends(get_db), _role=_role_dep):
    data=build_time_csv(db,start_date,end_date,employee_id)
    filename=f"Stunden_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    return Response(content=data,media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="{filename}"'})


@router.get("/api/time-backoffice/datev-export")
def export_datev_payroll(start_date: date, end_date: date, db: Session = Depends(get_db), _role=_role_dep):
    data,ext,warnings=build_datev_export(db,start_date,end_date)
    filename=f"DATEV_Lohndaten_{start_date.strftime('%Y-%m')}.{ext}"
    media="text/plain; charset=windows-1252" if ext=="txt" else "text/csv; charset=utf-8"
    return Response(content=data,media_type=media,headers={"Content-Disposition":f'attachment; filename="{filename}"',"X-DATEV-Warnings":str(len(warnings))})
