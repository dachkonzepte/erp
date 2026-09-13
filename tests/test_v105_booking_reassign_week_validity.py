from datetime import date
from decimal import Decimal
from pathlib import Path
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Employee
from app.time_tracking import create_manual_entry, update_entry
from app.work_time_models import ensure_default_work_time_models, employee_model, list_models, set_employee_model, week_in_range
from tests.test_v100_time_tracking import setup_order


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_backoffice_booking_can_be_reassigned_to_another_project_order():
    db = db_session()
    order1 = setup_order(db)
    order2 = setup_order(db)
    emp = Employee(employee_number="MA-U1", first_name="Uwe", last_name="Umbuchung", employee_group="gewerblich", hourly_wage=Decimal("22"), weekly_hours=Decimal("40"), active=True)
    db.add(emp); db.commit(); db.refresh(emp)
    entry = create_manual_entry(db, employee_id=emp.id, order_id=order1.id, order_item_id=order1.items[0].id, work_date=date(2026,9,1), hours=Decimal("8"), entry_type="site")
    changed = update_entry(db, entry.id, employee_id=emp.id, order_id=order2.id, order_item_id=order2.items[0].id, work_date=date(2026,9,1), hours=Decimal("7.5"), entry_type="site")
    assert changed.order_id == order2.id
    assert changed.project_id == order2.project_id
    assert changed.order_item_id == order2.items[0].id
    assert changed.hours == Decimal("7.5000")


def test_summer_winter_model_week_validity_and_automatic_effective_model():
    db = db_session()
    emp = Employee(employee_number="MA-KW", first_name="Klara", last_name="Kalender", employee_group="gewerblich", hourly_wage=Decimal("22"), weekly_hours=Decimal("40"), active=True)
    db.add(emp); db.commit(); db.refresh(emp)
    ensure_default_work_time_models(db)
    models = list_models(db)
    summer = next(x for x in models if x["code"] == "summer")
    winter = next(x for x in models if x["code"] == "winter")
    assert (summer["valid_from_week"], summer["valid_to_week"]) == (13,43)
    assert (winter["valid_from_week"], winter["valid_to_week"]) == (44,12)
    assert week_in_range(1,44,12) and week_in_range(50,44,12) and not week_in_range(20,44,12)
    set_employee_model(db, emp.id, summer["id"])
    assert employee_model(db, emp.id, date(2026,7,1)).code == "summer"
    assert employee_model(db, emp.id, date(2026,12,1)).code == "winter"


def test_backoffice_ui_exposes_project_order_and_calendar_week_fields():
    root = Path(__file__).parents[1]
    html = (root / "app/templates/time_backoffice.html").read_text(encoding="utf-8")
    assert 'id="editProject"' in html and 'id="editOrder"' in html and 'id="editOrderItem"' in html
    assert 'id="modelValidFrom"' in html and 'id="modelValidTo"' in html
    assert 'KW ${m.valid_from_week' in html
    assert re.match(r"^\d+\.\d+\.\d+$", (root / "VERSION").read_text(encoding="utf-8").strip())
