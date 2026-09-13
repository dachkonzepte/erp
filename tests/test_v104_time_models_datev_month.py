from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Employee
from app.schemas import TimeTrackingSettingsUpdate
from app.time_backoffice import (
    build_datev_export, get_employee_payroll, get_or_create_time_settings,
    payroll_rows, time_settings_dict, update_time_settings,
)
from app.time_tracking import start_timer, stop_timer
from app.work_time_models import (
    automatic_break_minutes_for_duration, ensure_default_work_time_models,
    get_or_create_advanced_settings, list_models, set_employee_model,
)
from tests.test_v100_time_tracking import setup_order


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_datev_can_use_erp_employee_number():
    db = db_session(); order = setup_order(db)
    emp = Employee(employee_number="MA-0042", first_name="Max", last_name="Dach", employee_group="gewerblich", hourly_wage=Decimal("22"), weekly_hours=Decimal("40"), active=True)
    db.add(emp); db.commit(); db.refresh(emp)
    get_employee_payroll(db, emp.id)
    current = get_or_create_time_settings(db)
    payload = TimeTrackingSettingsUpdate(**{
        **time_settings_dict(current, db),
        "datev_personnel_equals_erp_number": True,
        "datev_wage_type_site": "200",
    })
    update_time_settings(db, payload)
    from app.time_tracking import create_manual_entry
    create_manual_entry(db, employee_id=emp.id, order_id=order.id, work_date=date(2026,9,1), hours=Decimal("8"), entry_type="site")
    rows = payroll_rows(db)
    assert rows[0]["datev_personnel_number"] == "MA-0042"
    data, ext, warnings = build_datev_export(db, date(2026,9,1), date(2026,9,30))
    assert ext == "csv" and "MA-0042;Max Dach" in data.decode("utf-8-sig") and not warnings


def test_work_time_models_and_automatic_break_on_timer():
    db = db_session(); order = setup_order(db)
    emp = Employee(employee_number="MA-01", first_name="Anna", last_name="Sommer", employee_group="gewerblich", hourly_wage=Decimal("22"), weekly_hours=Decimal("40"), active=True)
    db.add(emp); db.commit(); db.refresh(emp)
    ensure_default_work_time_models(db)
    models = list_models(db)
    summer = next(x for x in models if x["code"] == "summer")
    set_employee_model(db, emp.id, summer["id"])
    assert automatic_break_minutes_for_duration(db, emp.id, Decimal("5.99")) == 0
    assert automatic_break_minutes_for_duration(db, emp.id, Decimal("6.00")) == 30
    assert automatic_break_minutes_for_duration(db, emp.id, Decimal("9.00")) == 45
    entry = start_timer(db, employee_id=emp.id, order_id=order.id, started_at=datetime(2026,9,1,7,0))
    entry = stop_timer(db, entry.id, ended_at=datetime(2026,9,1,16,0), break_minutes=0)
    assert entry.break_minutes == 45
    assert entry.hours == Decimal("8.2500")


def test_backoffice_ui_has_separate_options_work_models_and_current_month_entries():
    root = Path(__file__).parents[1]
    html = (root / "app/templates/time_backoffice.html").read_text(encoding="utf-8")
    assert 'data-tab="workmodels"' in html
    assert 'data-tab="options"' in html
    assert "DATEV-Personalnummer entspricht der ERP-Mitarbeiternummer" in html
    assert "currentMonthQs()" in html
    assert "loadEntries(){const [f,t]=currentMonthRange()" in html
    assert "Sommermodell" not in html  # Modelle kommen aus der DB, nicht hart aus dem Frontend.


def test_advanced_settings_default_model_is_created():
    db = db_session(); ensure_default_work_time_models(db)
    advanced = get_or_create_advanced_settings(db)
    assert advanced.default_work_time_model_id is not None
    assert len(list_models(db)) >= 2
