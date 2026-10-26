from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Employee
from app.schemas import TimeTrackingSettingsUpdate
from app.time_backoffice import (
    build_datev_export, get_employee_payroll, load_time_settings,
    payroll_rows, time_settings_dict, update_time_settings,
)
from app.time_tracking import start_timer, stop_timer
from app.work_time_models import (
    automatic_break_minutes_for_duration, ensure_default_work_time_models,
    load_advanced_settings, list_models, set_employee_model,
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
    current = load_time_settings(db)
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
    # seit 1.9.92: der Export nur abgeschlossen und mit Berater- und Mandantennummer (fehlt etwas: 409, keine Warnungen mehr)
    current = load_time_settings(db)
    current.locked_until, current.datev_beraternummer, current.datev_mandantennummer = date(2026,9,30), "1001", "1"
    db.commit()
    data, ext = build_datev_export(db, date(2026,9,1), date(2026,9,30))
    assert ext == "csv" and "MA-0042;Max Dach" in data.decode("utf-8-sig")


def test_work_time_models_and_automatic_break_on_timer():
    db = db_session(); order = setup_order(db)
    emp = Employee(employee_number="MA-01", first_name="Anna", last_name="Sommer", employee_group="gewerblich", hourly_wage=Decimal("22"), weekly_hours=Decimal("40"), active=True)
    db.add(emp); db.commit(); db.refresh(emp)
    ensure_default_work_time_models(db)
    models = list_models(db)
    summer = next(x for x in models if x["code"] == "summer")
    set_employee_model(db, emp.id, summer["id"])
    assert automatic_break_minutes_for_duration(db, emp.id, Decimal("5.99")) == 0
    # seit 1.9.48 „mehr als“ die Schwelle (bis 1.9.46 „ab“: 6,00 -> 30, 9,00 -> 45)
    assert automatic_break_minutes_for_duration(db, emp.id, Decimal("6.00")) == 0
    assert automatic_break_minutes_for_duration(db, emp.id, Decimal("6.0167")) == 30
    assert automatic_break_minutes_for_duration(db, emp.id, Decimal("9.00")) == 30
    assert automatic_break_minutes_for_duration(db, emp.id, Decimal("9.0167")) == 45
    entry = start_timer(db, employee_id=emp.id, order_id=order.id, started_at=datetime(2026,9,1,7,0))
    entry = stop_timer(db, entry.id, ended_at=datetime(2026,9,1,16,15), break_minutes=0)  # 9:15 h (bis 1.9.46 16:00)
    assert entry.break_minutes == 45
    assert entry.hours == Decimal("8.5000")


def test_backoffice_ui_has_separate_options_work_models_and_current_month_entries():
    """Seit 1.8.112 (neue Ordnung): Arbeitszeitmodelle, Zeit-Listen und DATEV-Personalnummern stehen in den Einstellungen
    (Personal -> Zeitregeln und DATEV, Listen -> Zeitarten/Tätigkeiten/Abwesenheitsarten), das Backoffice behält die Buchungen."""
    root = Path(__file__).parents[1]
    html = (root / "app/templates/time_backoffice.html").read_text(encoding="utf-8")
    settings = (root / "app/templates/settings.html").read_text(encoding="utf-8")
    assert 'data-settings-section="time-rules"' in settings and 'id="workModelCards"' in settings
    assert 'data-settings-section="time-entry-types"' in settings and 'data-settings-section="absence-types"' in settings
    assert "DATEV-Personalnummer entspricht der ERP-Mitarbeiternummer" in settings
    assert 'data-tab="workmodels"' not in html and 'data-tab="options"' not in html
    assert "currentMonthQs()" in html
    assert "loadEntries(){const [f,t]=currentMonthRange()" in html
    assert "Sommermodell" not in html and "Sommermodell" not in settings  # Modelle kommen aus der DB, nicht hart aus dem Frontend.


def test_advanced_settings_default_model_is_created():
    db = db_session(); ensure_default_work_time_models(db)
    advanced = load_advanced_settings(db)
    assert advanced.default_work_time_model_id is not None
    assert len(list_models(db)) >= 2
