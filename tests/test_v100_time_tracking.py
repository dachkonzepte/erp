from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import re

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.main import create_customer, create_project, create_quote, add_quote_item
from app.models import Employee, Service
from app.orders import create_order_from_quote
from app.schemas import CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate
from app.service import persist_project
from app.time_tracking import (
    create_manual_entry, start_timer, stop_timer, order_actual_hours,
    order_item_actual_hours, time_tracking_context,
)
from app.work_preparation import ensure_preparation, preparation_to_dict


def db_session():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_order(db):
    sample=Path(__file__).parents[1]/"sample_data"/"Thiefes.xml"
    persist_project(db,parse_leistungen_dach_xml(sample.read_bytes()),"Thiefes.xml")
    customer=create_customer(CustomerCreate(last_name="Zeitkunde",street="Dachweg 1",postal_code="52531",city="Übach-Palenberg"),db)
    project=create_project(ProjectCreate(customer_id=customer.id,name="Zeitprojekt"),db)
    quote=create_quote(project.id,QuoteCreate(title="Zeitangebot"),db)
    service=db.scalar(select(Service).where(Service.external_id=="L600109101011"))
    add_quote_item(quote.id,QuoteItemCreate(service_id=service.id,quantity=Decimal("10")),db)
    return create_order_from_quote(db,quote.id,order_date=date(2026,9,1),execution_start=None,execution_end=None,caseworker_employee_id=None,project_manager_employee_id=None,payment_terms=None,remarks=None)


def add_employee(db):
    e=Employee(employee_number="MA-Z1",first_name="Max",last_name="Zeit",employee_group="gewerblich",hourly_wage=Decimal("20"),weekly_hours=Decimal("40"),active=True)
    db.add(e);db.commit();db.refresh(e);return e


def test_manual_productive_and_travel_hours_are_separated():
    db=db_session();order=setup_order(db);emp=add_employee(db);item=order.items[0]
    create_manual_entry(db,employee_id=emp.id,order_id=order.id,order_item_id=item.id,work_date=date(2026,9,7),hours=Decimal("7.5"),entry_type="site")
    create_manual_entry(db,employee_id=emp.id,order_id=order.id,work_date=date(2026,9,7),hours=Decimal("1"),entry_type="travel")
    result=order_actual_hours(db,order.id)
    assert result["productive_hours"]==Decimal("7.50")
    assert result["travel_hours"]==Decimal("1.00")
    assert result["total_hours"]==Decimal("8.50")
    by_item=order_item_actual_hours(db,order.id)
    assert by_item[item.id]==Decimal("7.50")


def test_timer_start_stop_computes_net_hours_and_prevents_parallel_timer():
    db=db_session();order=setup_order(db);emp=add_employee(db)
    row=start_timer(db,employee_id=emp.id,order_id=order.id,entry_type="site",started_at=datetime(2026,9,7,7,0,0))
    try:
        start_timer(db,employee_id=emp.id,order_id=order.id,entry_type="travel",started_at=datetime(2026,9,7,8,0,0))
        assert False,"Parallel timer should fail"
    except ValueError as exc:
        assert "läuft bereits" in str(exc)
    row=stop_timer(db,row.id,ended_at=datetime(2026,9,7,16,0,0),break_minutes=30)
    assert row.status=="booked"
    assert row.hours==Decimal("8.2500")


def test_work_preparation_uses_time_entries_for_actual_and_variance():
    db=db_session();order=setup_order(db);emp=add_employee(db);prep=ensure_preparation(db,order.id)
    create_manual_entry(db,employee_id=emp.id,order_id=order.id,work_date=date(2026,9,7),hours=Decimal("4"),entry_type="site")
    create_manual_entry(db,employee_id=emp.id,order_id=order.id,work_date=date(2026,9,7),hours=Decimal("0.5"),entry_type="travel")
    data=preparation_to_dict(db,prep)
    assert data["actual_total_hours"]==Decimal("4.00")
    assert data["actual_travel_hours"]==Decimal("0.50")
    assert data["actual_all_hours"]==Decimal("4.50")
    assert data["hours_variance"]==Decimal("4.00")-data["planned_total_hours"]


def test_time_tracking_context_contains_order_items_and_mobile_ui_exists():
    db=db_session();order=setup_order(db);emp=add_employee(db)
    ctx=time_tracking_context(db,employee_id=emp.id,include_all_orders=True)
    found=next(x for x in ctx["orders"] if x["id"]==order.id)
    assert found["items"] and found["items"][0]["short_text"]
    root=Path(__file__).parents[1]
    main=(root/"app/main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root/"app/routers").glob("*.py")))
    html=(root/"app/templates/time_tracking.html").read_text(encoding="utf-8")
    project_html=(root/"app/templates/project_folder.html").read_text(encoding="utf-8")
    options=(root/"app/option_settings.py").read_text(encoding="utf-8")
    assert '/time-tracking' in main and '/api/time-entries/start' in main
    assert 'Schnell starten' in html and 'LV-Position' in html and 'Fahrzeit' in html
    assert 'time_entry_types' in options and 'time_entry_activities' in options
    assert 'Zeiterfassung im Projekt' in project_html and 'href="#sec-times"' in project_html


def test_version_1_0():
    root=Path(__file__).parents[1]
    assert re.match(r"^\d+\.\d+\.\d+$", (root/"VERSION").read_text(encoding="utf-8").strip())


def test_time_tracking_ui_loads_core_data_independently_and_auth_exposes_employee_id():
    root=Path(__file__).parents[1]
    html=(root/"app/templates/time_tracking.html").read_text(encoding="utf-8")
    main=(root/"app/routers/auth.py").read_text(encoding="utf-8")
    assert "safeOptionGroup" in html
    assert "Mitarbeiter-Fallback" in html and "Auftrags-Fallback" in html
    assert "keinem Mitarbeiter zugeordnet" in html
    assert '"employee_id":user.employee_id' in main
