from decimal import Decimal
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.employees import (
    apply_employee_payload, employee_to_dict, ensure_default_employee_functions, load_employee_functions,
    load_employees,
)
from app.models import Employee, EmployeeFunction, EmployeeProfile
from app.schemas import EmployeeCreate


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_default_functions_are_seeded_and_grouped():
    db = new_db()
    functions = load_employee_functions(db)
    names = {f.name: f.employee_group for f in functions}
    assert names["Dachdecker Geselle"] == "gewerblich"
    assert names["Büro / Verwaltung"] == "kaufmaennisch"


def test_employee_profile_stores_address_contact_birthday_and_info():
    db = new_db()
    ensure_default_employee_functions(db)
    function = db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == "Dachdecker Geselle"))
    payload = EmployeeCreate(
        employee_number="MA-01", first_name="Max", last_name="Muster",
        function_id=function.id, job_title=function.name, employee_group=function.employee_group,
        hourly_wage=Decimal("21.50"), weekly_hours=Decimal("40"),
        street="Musterweg 1", postal_code="52531", city="Übach-Palenberg",
        phone="02451 123", mobile="0171 123", email="max@example.de",
        birthday="1990-05-12", important_info="Führerschein BE", active=True,
    )
    employee = Employee(first_name="Max", last_name="Muster", employee_group="gewerblich", hourly_wage=Decimal("21.50"), weekly_hours=Decimal("40"))
    apply_employee_payload(db, employee, payload)
    db.add(employee); db.commit(); db.refresh(employee)
    out = employee_to_dict(db.get(Employee, employee.id))
    assert out["function_name"] == "Dachdecker Geselle"
    assert out["city"] == "Übach-Palenberg"
    assert out["mobile"] == "0171 123"
    assert str(out["birthday"]) == "1990-05-12"
    assert out["important_info"] == "Führerschein BE"


def test_legacy_employee_is_read_without_creating_profile_or_function():
    """Seit 1.8.84 (Regel 23): ein Mitarbeiter ohne Profil wird gelesen, nicht ergänzt -- bis 1.8.83 legte das Lesen Profil
    und eine Funktion aus der Berufsbezeichnung an. Angezeigt wird die Berufsbezeichnung; gibt es eine gleichnamige Funktion,
    deren ID; das Profil entsteht beim Speichern."""
    db = new_db()
    employee = Employee(
        first_name="Alt", last_name="Bestand", job_title="Eigene Altfunktion",
        employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True,
    )
    db.add(employee); db.commit()
    out = employee_to_dict(load_employees(db)[0], db)
    assert out["function_name"] == "Eigene Altfunktion"
    assert out["function_id"] is None
    assert db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == "Eigene Altfunktion")) is None
    assert db.scalar(select(EmployeeProfile)) is None
    assert not db.new and not db.dirty
    gleichnamig = db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == "Dachdecker Geselle"))
    employee.job_title = "Dachdecker Geselle"
    db.commit()
    out = employee_to_dict(load_employees(db)[0], db)
    assert (out["function_id"], out["function_name"]) == (gleichnamig.id, "Dachdecker Geselle")
    assert db.scalar(select(EmployeeProfile)) is None
