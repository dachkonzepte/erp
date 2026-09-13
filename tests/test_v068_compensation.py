from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.employees import apply_employee_payload, employee_to_dict
from app.labor_rate import calculate_labor_rate, get_or_create_labor_rate_settings
from app.calculation import get_or_create_settings
from app.models import Employee, EmployeeCompensationSettings
from app.schemas import EmployeeCreate


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_fixed_salary_is_converted_to_effective_hourly_wage():
    db = new_db()
    get_or_create_labor_rate_settings(db).weeks_per_year = Decimal("52")
    payload = EmployeeCreate(
        first_name="Max", last_name="Fix", employee_group="gewerblich",
        compensation_type="fixed_salary", monthly_salary=Decimal("3500"),
        hourly_wage=None, weekly_hours=Decimal("40"), active=True,
    )
    employee = Employee(first_name="Max", last_name="Fix", employee_group="gewerblich")
    apply_employee_payload(db, employee, payload)
    db.add(employee); db.commit(); db.refresh(employee)
    out = employee_to_dict(employee, db)
    assert out["compensation_type"] == "fixed_salary"
    assert out["monthly_salary"] == Decimal("3500.00")
    assert round(Decimal(out["effective_hourly_wage"]), 2) == Decimal("20.19")
    assert round(Decimal(employee.hourly_wage), 2) == Decimal("20.19")
    assert out["annual_gross_wage"] == Decimal("42000.00")


def test_labor_rate_combines_hourly_and_fixed_salary_employees():
    db = new_db()
    params = get_or_create_labor_rate_settings(db)
    params.weeks_per_year = Decimal("52")
    params.employer_cost_pct = Decimal("0")
    params.productive_time_pct = Decimal("100")
    params.annual_overhead = Decimal("0")
    params.target_profit_pct = Decimal("0")

    hourly = Employee(
        first_name="Anna", last_name="Stunde", employee_group="gewerblich",
        hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True,
        compensation=EmployeeCompensationSettings(compensation_type="hourly"),
    )
    fixed = Employee(
        first_name="Ben", last_name="Fix", employee_group="gewerblich",
        hourly_wage=Decimal("0"), weekly_hours=Decimal("40"), active=True,
        compensation=EmployeeCompensationSettings(compensation_type="fixed_salary", monthly_salary=Decimal("4160")),
    )
    db.add_all([hourly, fixed]); db.commit()
    result = calculate_labor_rate(db, get_or_create_settings(db))
    # Hourly employee: 41,600 €/year; fixed salary: 49,920 €/year.
    # Combined 91,520 € / 4,160 paid hours = 22 €/h.
    assert result["annual_gross_wages"] == Decimal("91520.00")
    assert result["weighted_mean_wage"] == Decimal("22.00")
    assert result["suggested_labor_rate"] == Decimal("22.00")


def test_legacy_employee_without_compensation_defaults_to_hourly():
    db = new_db()
    employee = Employee(
        first_name="Alt", last_name="Bestand", employee_group="gewerblich",
        hourly_wage=Decimal("19.50"), weekly_hours=Decimal("40"), active=True,
    )
    db.add(employee); db.commit(); db.refresh(employee)
    out = employee_to_dict(employee, db)
    assert out["compensation_type"] == "hourly"
    assert out["effective_hourly_wage"] == Decimal("19.500000")
