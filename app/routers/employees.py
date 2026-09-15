"""Router: employees

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 5 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..employees import apply_employee_payload, employee_to_dict, ensure_default_employee_functions, ensure_employee_profiles, set_cost_allocation, set_planning_visibility
from ..models import AppUser, Employee, EmployeeProfile, EmployeeRoleSettings
from ..permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE, require_role
from ..schemas import EmployeeCreate, EmployeeNameOut, EmployeeOut, EmployeeUpdate

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): EmployeeOut trägt Lohn-/Gehaltsfelder
# (hourly_wage/effective_hourly_wage/annual_gross_wage) -- Büro/Admin, das war der zentrale
# Fund der Suche-Bestandsaufnahme (jeder angemeldete Benutzer konnte das bisher lesen).
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, message="Mitarbeiterdaten sind nur für Büro und Administratoren verfügbar."))
# GET /api/employees allein bleibt zusätzlich für `field` offen -- service_reports.html (vom
# Monteur genutzt) füllt darüber sein Mitarbeiter-Auswahlfeld für die kompakte Zeitbuchung
# (nur id/first_name/last_name/active gelesen, siehe employeeOptionsHtml() dort). Ohne diese
# Ausnahme wäre der Aufruf seit der obigen Sperre für `field` 403 gelaufen -- durch das dortige
# `.catch(()=>[])` unbemerkt, das Auswahlfeld aber stillschweigend leer (echter, jetzt behobener
# Fund). Ein Monteur bekommt dafür EmployeeNameOut statt EmployeeOut, siehe dort.
_any_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD))


@router.get("/api/employees", response_model=list[EmployeeOut] | list[EmployeeNameOut])
def list_employees(db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    employees = [employee_to_dict(e, db) for e in ensure_employee_profiles(db)]
    if _role.role == ROLE_FIELD:
        return [EmployeeNameOut.model_validate(e) for e in employees]
    return employees


@router.get("/api/employees/caseworkers", response_model=list[EmployeeOut])
def list_caseworkers(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    employees = ensure_employee_profiles(db)
    result = []
    for employee in employees:
        role = db.scalar(select(EmployeeRoleSettings).where(EmployeeRoleSettings.employee_id == employee.id))
        if employee.active and role is not None and role.available_as_caseworker:
            result.append(employee_to_dict(employee, db))
    return result


@router.get("/api/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    ensure_employee_profiles(db)
    employee = db.scalar(
        select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function))
        .where(Employee.id == employee_id)
    )
    if employee is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden.")
    return employee_to_dict(employee, db)


@router.post("/api/employees", response_model=EmployeeOut)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    ensure_default_employee_functions(db)
    if payload.employee_number:
        exists = db.scalar(select(Employee).where(Employee.employee_number == payload.employee_number))
        if exists:
            raise HTTPException(status_code=409, detail="Mitarbeiternummer ist bereits vergeben.")
    employee = Employee(
        first_name=payload.first_name, last_name=payload.last_name, employee_group=payload.employee_group,
        hourly_wage=payload.hourly_wage, weekly_hours=payload.weekly_hours, active=payload.active,
    )
    try:
        apply_employee_payload(db, employee, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.add(employee)
    db.commit()
    db.refresh(employee)
    # Relationship inklusive Funktion frisch laden.
    employee = db.scalar(select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function)).where(Employee.id == employee.id))
    # Rolle kann erst sicher nach dem ersten Flush angelegt werden.
    role = db.scalar(select(EmployeeRoleSettings).where(EmployeeRoleSettings.employee_id == employee.id))
    if role is None:
        role = EmployeeRoleSettings(employee_id=employee.id)
        db.add(role)
    role.available_as_caseworker = bool(payload.available_as_caseworker)
    set_planning_visibility(db, employee, payload.show_on_planning_board)
    set_cost_allocation(db, employee, payload.cost_allocation)
    db.commit()
    employee = db.scalar(select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function)).where(Employee.id == employee.id))
    return employee_to_dict(employee, db)


@router.put("/api/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, payload: EmployeeUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    employee = db.scalar(select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function)).where(Employee.id == employee_id))
    if employee is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden.")
    if payload.employee_number:
        exists = db.scalar(select(Employee).where(Employee.employee_number == payload.employee_number, Employee.id != employee_id))
        if exists:
            raise HTTPException(status_code=409, detail="Mitarbeiternummer ist bereits vergeben.")
    try:
        apply_employee_payload(db, employee, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    role = db.scalar(select(EmployeeRoleSettings).where(EmployeeRoleSettings.employee_id == employee.id))
    if role is None:
        role = EmployeeRoleSettings(employee_id=employee.id)
        db.add(role)
    role.available_as_caseworker = bool(payload.available_as_caseworker)
    set_planning_visibility(db, employee, payload.show_on_planning_board)
    set_cost_allocation(db, employee, payload.cost_allocation)
    db.commit()
    employee = db.scalar(select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function)).where(Employee.id == employee_id))
    return employee_to_dict(employee, db)
