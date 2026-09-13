from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.calculation import get_or_create_settings
from app.database import Base
from app.employees import employee_to_dict
from app.labor_rate import calculate_labor_rate, get_or_create_labor_rate_settings, get_or_create_overhead_settings
from app.models import Employee, EmployeeCompensationSettings, EmployeeCostAllocationSettings
from app.schemas import EmployeeCreate


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_employee(db, first, group, wage=None, salary=None, allocation="labor_rate"):
    comp_type = "fixed_salary" if salary is not None else "hourly"
    e = Employee(
        first_name=first,
        last_name="Test",
        employee_group=group,
        hourly_wage=Decimal(str(wage or 0)) if wage is not None else None,
        weekly_hours=Decimal("40"),
        active=True,
        compensation=EmployeeCompensationSettings(
            compensation_type=comp_type,
            monthly_salary=Decimal(str(salary)) if salary is not None else None,
        ),
    )
    db.add(e); db.flush()
    db.add(EmployeeCostAllocationSettings(employee_id=e.id, allocation_type=allocation))
    return e


def test_variable_overhead_employee_is_not_in_mean_wage_but_added_to_overhead():
    db = new_db()
    params = get_or_create_labor_rate_settings(db)
    params.employer_cost_pct = Decimal("0")
    params.productive_time_pct = Decimal("100")
    params.target_profit_pct = Decimal("0")
    params.weeks_per_year = Decimal("52")
    overhead = get_or_create_overhead_settings(db, params)
    overhead.fixed_overhead_mode = "eur"; overhead.fixed_overhead_value = Decimal("0")
    overhead.variable_overhead_mode = "eur"; overhead.variable_overhead_value = Decimal("0")
    add_employee(db, "Direkt", "gewerblich", wage=20, allocation="labor_rate")
    add_employee(db, "Büro", "kaufmaennisch", salary=3000, allocation="variable_overhead")
    db.commit()

    result = calculate_labor_rate(db, get_or_create_settings(db))
    assert result["direct_employee_count"] == 1
    assert result["variable_overhead_employee_count"] == 1
    assert result["weighted_mean_wage"] == Decimal("20.00")
    assert result["annual_gross_wages"] == Decimal("41600.00")
    assert result["variable_employee_costs"] == Decimal("36000.00")
    assert result["labor_cost_per_productive_hour"] == Decimal("20.00")
    assert result["variable_overhead_per_productive_hour"] == Decimal("17.31")
    assert result["suggested_labor_rate"] == Decimal("37.31")


def test_fixed_and_variable_overheads_can_be_percent_of_direct_labor_cost():
    db = new_db()
    params = get_or_create_labor_rate_settings(db)
    params.employer_cost_pct = Decimal("0")
    params.productive_time_pct = Decimal("100")
    params.target_profit_pct = Decimal("0")
    params.weeks_per_year = Decimal("52")
    overhead = get_or_create_overhead_settings(db, params)
    overhead.fixed_overhead_mode = "pct"; overhead.fixed_overhead_value = Decimal("10")
    overhead.variable_overhead_mode = "pct"; overhead.variable_overhead_value = Decimal("5")
    add_employee(db, "Direkt", "gewerblich", wage=20, allocation="labor_rate")
    db.commit()

    result = calculate_labor_rate(db, get_or_create_settings(db))
    assert result["direct_labor_annual_cost"] == Decimal("41600.00")
    assert result["fixed_overhead_annual"] == Decimal("4160.00")
    assert result["manual_variable_overhead_annual"] == Decimal("2080.00")
    assert result["fixed_overhead_per_productive_hour"] == Decimal("2.00")
    assert result["variable_overhead_per_productive_hour"] == Decimal("1.00")
    assert result["suggested_labor_rate"] == Decimal("23.00")


def test_overhead_euro_mode_uses_annual_amounts():
    db = new_db()
    params = get_or_create_labor_rate_settings(db)
    params.employer_cost_pct = Decimal("0")
    params.productive_time_pct = Decimal("100")
    params.target_profit_pct = Decimal("0")
    params.weeks_per_year = Decimal("52")
    overhead = get_or_create_overhead_settings(db, params)
    overhead.fixed_overhead_mode = "eur"; overhead.fixed_overhead_value = Decimal("10000")
    overhead.variable_overhead_mode = "eur"; overhead.variable_overhead_value = Decimal("5000")
    add_employee(db, "Direkt", "gewerblich", wage=20, allocation="labor_rate")
    db.commit()

    result = calculate_labor_rate(db, get_or_create_settings(db))
    assert result["fixed_overhead_annual"] == Decimal("10000.00")
    assert result["variable_overhead_annual"] == Decimal("5000.00")
    assert result["overhead_per_productive_hour"] == Decimal("7.21")
    assert result["suggested_labor_rate"] == Decimal("27.21")


def test_employee_in_variable_overhead_requires_compensation():
    with pytest.raises(ValidationError):
        EmployeeCreate(
            first_name="Anna", last_name="Büro", employee_group="kaufmaennisch",
            cost_allocation="variable_overhead", compensation_type="hourly",
            hourly_wage=None, weekly_hours=Decimal("40"), active=True,
        )


def test_legacy_office_employee_without_allocation_stays_excluded():
    db = new_db()
    employee = Employee(
        first_name="Alt", last_name="Büro", employee_group="kaufmaennisch",
        hourly_wage=None, weekly_hours=Decimal("40"), active=True,
    )
    db.add(employee); db.commit(); db.refresh(employee)
    assert employee_to_dict(employee, db)["cost_allocation"] == "excluded"
