from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .models import (
    Employee, EmployeeCompensationSettings, EmployeeCostAllocationSettings, EmployeeFunction,
    EmployeeProfile, EmployeeRoleSettings, EmployeePlanningSettings,
)


DEFAULT_EMPLOYEE_FUNCTIONS = [
    (10, "Dachdeckermeister", "gewerblich"),
    (20, "Dachdecker Vorarbeiter", "gewerblich"),
    (30, "Dachdecker Geselle", "gewerblich"),
    (40, "Dachdecker Junggeselle", "gewerblich"),
    (50, "Dachdecker Helfer", "gewerblich"),
    (60, "Dachdecker Auszubildende/r", "gewerblich"),
    (70, "Zimmerer Geselle", "gewerblich"),
    (80, "Klempner/Spengler", "gewerblich"),
    (90, "Lagerist", "gewerblich"),
    (100, "Büro / Verwaltung", "kaufmaennisch"),
    (110, "Bauleitung / Projektleitung", "kaufmaennisch"),
    (120, "Geschäftsführung", "kaufmaennisch"),
    (900, "Gewerblicher Mitarbeiter", "gewerblich"),
    (910, "Kaufmännischer Mitarbeiter", "kaufmaennisch"),
]


def ensure_default_employee_functions(db: Session) -> list[EmployeeFunction]:
    """Gegen einen gleichzeitigen ersten Zugriff abgesichert (siehe CLAUDE.md "Self-Seeding
    gegen gleichzeitigen Zugriff absichern"): jede fehlende Funktion wird einzeln in einem
    SAVEPOINT angelegt -- eine UNIQUE-Verletzung auf name (ein anderer Prozess war schneller)
    wird als "schon gesät" behandelt, nicht als Fehler."""
    existing = {f.name: f for f in db.scalars(select(EmployeeFunction)).all()}
    changed = False
    for sort_order, name, group in DEFAULT_EMPLOYEE_FUNCTIONS:
        if name in existing:
            continue
        try:
            with db.begin_nested():
                fn = EmployeeFunction(name=name, employee_group=group, sort_order=sort_order, active=True)
                db.add(fn)
                db.flush()
        except IntegrityError:
            continue
        existing[name] = fn
        changed = True
    if changed:
        db.commit()
    return db.scalars(
        select(EmployeeFunction).order_by(EmployeeFunction.sort_order, EmployeeFunction.name)
    ).all()


def get_employee_function(db: Session, function_id: int | None) -> EmployeeFunction | None:
    if function_id is None:
        return None
    return db.get(EmployeeFunction, function_id)


def _function_for_legacy_employee(db: Session, employee: Employee) -> EmployeeFunction:
    ensure_default_employee_functions(db)
    if employee.job_title:
        existing = db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == employee.job_title.strip()))
        if existing:
            return existing
        fn = EmployeeFunction(
            name=employee.job_title.strip(),
            employee_group=employee.employee_group,
            sort_order=500,
            active=True,
            description="Automatisch aus bestehender Mitarbeiterfunktion übernommen.",
        )
        db.add(fn)
        db.flush()
        return fn
    fallback = "Gewerblicher Mitarbeiter" if employee.employee_group == "gewerblich" else "Kaufmännischer Mitarbeiter"
    return db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == fallback))


def ensure_employee_profile(db: Session, employee: Employee) -> EmployeeProfile:
    profile = employee.profile
    if profile is None:
        function = _function_for_legacy_employee(db, employee)
        profile = EmployeeProfile(employee_id=employee.id, function_id=function.id if function else None)
        db.add(profile)
        db.flush()
        employee.profile = profile
        db.commit()
        db.refresh(employee)
    return profile


def ensure_employee_profiles(db: Session) -> list[Employee]:
    ensure_default_employee_functions(db)
    employees = db.scalars(
        select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function))
        .order_by(Employee.active.desc(), Employee.last_name, Employee.first_name)
    ).all()
    changed = False
    for employee in employees:
        if employee.profile is None:
            function = _function_for_legacy_employee(db, employee)
            db.add(EmployeeProfile(employee_id=employee.id, function_id=function.id if function else None))
            changed = True
    if changed:
        db.commit()
        employees = db.scalars(
            select(Employee).options(selectinload(Employee.profile).selectinload(EmployeeProfile.function))
            .order_by(Employee.active.desc(), Employee.last_name, Employee.first_name)
        ).all()
    return employees


def get_or_create_role_settings(db: Session, employee: Employee) -> EmployeeRoleSettings:
    row = db.scalar(select(EmployeeRoleSettings).where(EmployeeRoleSettings.employee_id == employee.id)) if employee.id else None
    if row is None:
        row = EmployeeRoleSettings(employee_id=employee.id, available_as_caseworker=False)
        db.add(row)
        db.flush()
    return row




def _default_planning_visibility(employee: Employee) -> bool:
    """Kompatibler Fallback: Büro/Verwaltung und Lager standardmäßig ausblenden."""
    function_name = ""
    if employee.profile and employee.profile.function:
        function_name = employee.profile.function.name or ""
    elif employee.job_title:
        function_name = employee.job_title
    lowered = function_name.casefold()
    if employee.employee_group == "kaufmaennisch":
        return False
    if any(token in lowered for token in ("lager", "büro", "buero", "verwaltung")):
        return False
    return True


def effective_planning_visibility(db: Session, employee: Employee) -> bool:
    if employee.id:
        row = db.scalar(select(EmployeePlanningSettings).where(EmployeePlanningSettings.employee_id == employee.id))
        if row is not None:
            return bool(row.show_on_planning_board)
    return _default_planning_visibility(employee)


def set_planning_visibility(db: Session, employee: Employee, visible: bool | None) -> EmployeePlanningSettings | None:
    if not employee.id:
        return None
    row = db.scalar(select(EmployeePlanningSettings).where(EmployeePlanningSettings.employee_id == employee.id))
    target = _default_planning_visibility(employee) if visible is None else bool(visible)
    if row is None:
        row = EmployeePlanningSettings(employee_id=employee.id, show_on_planning_board=target)
        db.add(row)
    else:
        row.show_on_planning_board = target
    return row

def effective_cost_allocation(db: Session, employee: Employee) -> str:
    """Kosten-Zuordnung mit kompatiblem Fallback für Bestandsmitarbeiter."""
    if employee.id:
        row = db.scalar(
            select(EmployeeCostAllocationSettings).where(EmployeeCostAllocationSettings.employee_id == employee.id)
        )
        if row is not None:
            return row.allocation_type
    # Vor 0.6.9 flossen aktive gewerbliche Mitarbeiter in den Verrechnungssatz ein;
    # kaufmännische Mitarbeiter wurden nicht berücksichtigt.
    return "labor_rate" if employee.employee_group == "gewerblich" else "excluded"


def set_cost_allocation(db: Session, employee: Employee, allocation_type: str | None) -> EmployeeCostAllocationSettings | None:
    if not employee.id:
        return None
    target = allocation_type or ("labor_rate" if employee.employee_group == "gewerblich" else "excluded")
    if target not in {"labor_rate", "variable_overhead", "excluded"}:
        raise ValueError("Ungültige Kosten-Zuordnung für Mitarbeiter.")
    row = db.scalar(
        select(EmployeeCostAllocationSettings).where(EmployeeCostAllocationSettings.employee_id == employee.id)
    )
    if row is None:
        row = EmployeeCostAllocationSettings(employee_id=employee.id, allocation_type=target)
        db.add(row)
    else:
        row.allocation_type = target
    return row


def get_or_create_compensation_settings(db: Session, employee: Employee) -> EmployeeCompensationSettings:
    row = employee.compensation
    if row is None and employee.id:
        row = db.scalar(select(EmployeeCompensationSettings).where(EmployeeCompensationSettings.employee_id == employee.id))
    if row is None:
        row = EmployeeCompensationSettings(compensation_type="hourly", monthly_salary=None)
        employee.compensation = row
        if employee.id:
            row.employee_id = employee.id
        db.add(row)
        db.flush()
    return row


def effective_hourly_wage(employee: Employee, weeks_per_year: Decimal | int | float | str = Decimal("52")) -> Decimal | None:
    weekly_hours = Decimal(employee.weekly_hours or 0)
    weeks = Decimal(weeks_per_year or 0)
    comp = employee.compensation
    if comp is not None and comp.compensation_type == "fixed_salary":
        monthly = Decimal(comp.monthly_salary or 0)
        annual_hours = weekly_hours * weeks
        if monthly <= 0 or annual_hours <= 0:
            return None
        return (monthly * Decimal("12")) / annual_hours
    wage = Decimal(employee.hourly_wage or 0)
    return wage if wage > 0 else None


def annual_gross_wage(employee: Employee, weeks_per_year: Decimal | int | float | str = Decimal("52")) -> Decimal | None:
    weekly_hours = Decimal(employee.weekly_hours or 0)
    weeks = Decimal(weeks_per_year or 0)
    comp = employee.compensation
    if comp is not None and comp.compensation_type == "fixed_salary":
        monthly = Decimal(comp.monthly_salary or 0)
        return monthly * Decimal("12") if monthly > 0 else None
    wage = Decimal(employee.hourly_wage or 0)
    if wage <= 0 or weekly_hours <= 0 or weeks <= 0:
        return None
    return wage * weekly_hours * weeks

def employee_to_dict(employee: Employee, db: Session | None = None) -> dict:
    p = employee.profile
    f = p.function if p else None
    role = None
    weeks_per_year = Decimal("52")
    if db is not None and employee.id:
        role = db.scalar(select(EmployeeRoleSettings).where(EmployeeRoleSettings.employee_id == employee.id))
        from .labor_rate import get_or_create_labor_rate_settings
        weeks_per_year = Decimal(get_or_create_labor_rate_settings(db).weeks_per_year or Decimal("52"))
        if employee.compensation is None:
            existing = db.scalar(select(EmployeeCompensationSettings).where(EmployeeCompensationSettings.employee_id == employee.id))
            if existing is not None:
                employee.compensation = existing
    comp = employee.compensation
    effective = effective_hourly_wage(employee, weeks_per_year)
    annual = annual_gross_wage(employee, weeks_per_year)
    return {
        "id": employee.id,
        "employee_number": employee.employee_number,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "job_title": f.name if f else employee.job_title,
        "function_id": f.id if f else (p.function_id if p else None),
        "function_name": f.name if f else employee.job_title,
        "employee_group": f.employee_group if f else employee.employee_group,
        "compensation_type": comp.compensation_type if comp else "hourly",
        "hourly_wage": effective,
        "monthly_salary": comp.monthly_salary if comp and comp.compensation_type == "fixed_salary" else None,
        "effective_hourly_wage": effective,
        "annual_gross_wage": annual,
        "weekly_hours": employee.weekly_hours,
        "street": p.street if p else None,
        "postal_code": p.postal_code if p else None,
        "city": p.city if p else None,
        "country": p.country if p else "Deutschland",
        "phone": p.phone if p else None,
        "mobile": p.mobile if p else None,
        "email": p.email if p else None,
        "birthday": p.birthday if p else None,
        "important_info": p.important_info if p else None,
        "available_as_caseworker": bool(role.available_as_caseworker) if role else False,
        "show_on_planning_board": effective_planning_visibility(db, employee) if db is not None else _default_planning_visibility(employee),
        "cost_allocation": effective_cost_allocation(db, employee) if db is not None else ("labor_rate" if employee.employee_group == "gewerblich" else "excluded"),
        "active": employee.active,
    }


def apply_employee_payload(db: Session, employee: Employee, payload) -> Employee:
    function = get_employee_function(db, payload.function_id)
    if payload.function_id is not None and function is None:
        raise ValueError("Ausgewählte Funktion/Tätigkeit wurde nicht gefunden.")
    if function and not function.active:
        raise ValueError("Die ausgewählte Funktion/Tätigkeit ist inaktiv.")

    group = function.employee_group if function else payload.employee_group
    compensation_type = payload.compensation_type or "hourly"
    allocation = payload.cost_allocation
    requires_cost = group == "gewerblich" or allocation in {"labor_rate", "variable_overhead"}
    if requires_cost:
        if compensation_type == "hourly" and (payload.hourly_wage is None or payload.hourly_wage <= 0):
            raise ValueError("Für Mitarbeiter, die in die Kalkulation einfließen, ist bei Stundenlohn ein positiver Stundenlohn erforderlich.")
        if compensation_type == "fixed_salary" and (payload.monthly_salary is None or payload.monthly_salary <= 0):
            raise ValueError("Für Mitarbeiter, die in die Kalkulation einfließen, ist bei Festgehalt ein positives Monatsbruttogehalt erforderlich.")

    employee.employee_number = payload.employee_number
    employee.first_name = payload.first_name
    employee.last_name = payload.last_name
    employee.job_title = function.name if function else payload.job_title
    employee.employee_group = group
    employee.weekly_hours = payload.weekly_hours
    employee.active = payload.active

    if employee.compensation is None:
        employee.compensation = EmployeeCompensationSettings()
    employee.compensation.compensation_type = compensation_type
    employee.compensation.monthly_salary = payload.monthly_salary if compensation_type == "fixed_salary" else None
    if compensation_type == "hourly":
        employee.hourly_wage = payload.hourly_wage
    else:
        from .labor_rate import get_or_create_labor_rate_settings
        weeks = Decimal(get_or_create_labor_rate_settings(db).weeks_per_year or Decimal("52"))
        monthly = Decimal(payload.monthly_salary or 0)
        annual_hours = Decimal(payload.weekly_hours or 0) * weeks
        employee.hourly_wage = (monthly * Decimal("12") / annual_hours) if monthly > 0 and annual_hours > 0 else None

    if employee.profile is None:
        employee.profile = EmployeeProfile()
    p = employee.profile
    p.function_id = function.id if function else None
    p.street = payload.street
    p.postal_code = payload.postal_code
    p.city = payload.city
    p.country = payload.country or "Deutschland"
    p.phone = payload.phone
    p.mobile = payload.mobile
    p.email = payload.email
    p.birthday = payload.birthday
    p.important_info = payload.important_info
    # Zusatzrolle migrationsarm in eigener Tabelle pflegen. Bei neuen Mitarbeitern erst nach flush möglich.
    if employee.id:
        role = get_or_create_role_settings(db, employee)
        role.available_as_caseworker = bool(payload.available_as_caseworker)
    return employee
