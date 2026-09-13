from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.calculation import get_or_create_settings
from app.labor_rate import calculate_labor_rate, get_or_create_labor_rate_settings
from app.models import Employee
from app.schemas import EmployeeCreate


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_commercial_employee_requires_hourly_wage():
    with pytest.raises(ValidationError):
        EmployeeCreate(
            first_name="Max", last_name="Muster", employee_group="gewerblich",
            hourly_wage=None, weekly_hours=Decimal("40"), active=True,
        )


def test_office_employee_does_not_require_hourly_wage():
    employee = EmployeeCreate(
        first_name="Anna", last_name="Büro", employee_group="kaufmaennisch",
        hourly_wage=None, weekly_hours=Decimal("40"), active=True,
    )
    assert employee.hourly_wage is None


def test_labor_rate_uses_weighted_mean_and_only_active_commercial_staff():
    db = new_db()
    db.add_all([
        Employee(first_name="A", last_name="Dach", employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True),
        Employee(first_name="B", last_name="Dach", employee_group="gewerblich", hourly_wage=Decimal("16"), weekly_hours=Decimal("20"), active=True),
        Employee(first_name="C", last_name="Büro", employee_group="kaufmaennisch", hourly_wage=None, weekly_hours=Decimal("40"), active=True),
        Employee(first_name="D", last_name="Alt", employee_group="gewerblich", hourly_wage=Decimal("99"), weekly_hours=Decimal("40"), active=False),
    ])
    db.commit()

    params = get_or_create_labor_rate_settings(db)
    params.employer_cost_pct = Decimal("25")
    params.productive_time_pct = Decimal("70")
    params.annual_overhead = Decimal("100000")
    params.target_profit_pct = Decimal("10")
    params.weeks_per_year = Decimal("52")
    calc_settings = get_or_create_settings(db)
    calc_settings.labor_rate = Decimal("82")
    db.commit()

    result = calculate_labor_rate(db, calc_settings)
    assert result["commercial_employee_count"] == 2
    assert result["weighted_mean_wage"] == Decimal("18.67")
    assert result["annual_paid_hours"] == Decimal("3120.00")
    assert result["annual_productive_hours"] == Decimal("2184.00")
    assert result["annual_gross_wages"] == Decimal("58240.00")
    assert result["annual_employer_costs"] == Decimal("14560.00")
    assert result["labor_cost_per_productive_hour"] == Decimal("33.33")
    assert result["overhead_per_productive_hour"] == Decimal("45.79")
    assert result["self_cost_per_hour"] == Decimal("79.12")
    assert result["target_profit_per_hour"] == Decimal("7.91")
    assert result["suggested_labor_rate"] == Decimal("87.03")
    assert result["difference_to_current"] == Decimal("5.03")


def test_no_employees_returns_explanation_instead_of_fake_rate():
    db = new_db()
    result = calculate_labor_rate(db, get_or_create_settings(db))
    assert result["can_calculate"] is False
    assert result["suggested_labor_rate"] is None
    assert "keine aktiven gewerblichen Mitarbeiter" in result["note"]
