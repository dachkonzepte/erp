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
    create_manual_entry, start_timer, stop_timer, time_tracking_context,
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
    # seit 1.9.126 rechnet app/akte.py die Stunden (bis 1.9.125 order_actual_hours(): „produktiv“ statt Baustelle & Werkstatt)
    from app.akte import ist_je_position, stunden
    result=stunden(db,order)
    assert result["baustelle_werkstatt"]==Decimal("7.50")
    assert result["fahrzeit"]==Decimal("1.00")
    assert result["gebucht"]==Decimal("8.50")
    by_item=ist_je_position(db,order.id)
    assert by_item[item.id]==Decimal("7.50")


def test_timer_start_stop_computes_net_hours_and_prevents_parallel_timer():
    db=db_session();order=setup_order(db);emp=add_employee(db)
    row=start_timer(db,employee_id=emp.id,order_id=order.id,entry_type="site",started_at=datetime(2026,9,7,7,0,0))
    try:
        start_timer(db,employee_id=emp.id,order_id=order.id,entry_type="travel",started_at=datetime(2026,9,7,8,0,0))
        assert False,"Parallel timer should fail"
    except ValueError as exc:
        # seit 1.9.35: der 07.09.2026 liegt vor heute -- die laufende Zeit ist eine offene Zeit von früher, die Meldung verweist auf
        # „Ende nachtragen“ (bis 1.9.34 „läuft bereits“; der Fall „heute schon gestartet“ in test_v463)
        assert "läuft noch – zuerst das Ende nachtragen" in str(exc)
    row=stop_timer(db,row.id,ended_at=datetime(2026,9,7,16,0,0),break_minutes=30)
    assert row.status=="booked"
    assert row.hours==Decimal("8.5000")  # seit 1.9.48: genau 9:00 h ist nicht „mehr als 9 h“ -> 30 min (bis 1.9.46 45 min, 8,25 h)


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
    html=(root/"app/templates/zeiten.html").read_text(encoding="utf-8")  # seit 1.9.98 „Zeiten“ statt der Zeiterfassung
    project_html=(root/"app/templates/akte.html").read_text(encoding="utf-8")
    options=(root/"app/option_settings.py").read_text(encoding="utf-8")
    assert '/time-tracking' in main and '/api/time-entries/start' in main
    assert 'LV-Position' in html and 'id="bdPosition"' in html and "/api/time-tracking/context" in html  # bis 1.9.97 „Schnell starten“
    assert 'time_entry_types' in options and 'time_entry_activities' in options
    # Seit 1.3.74 (Umbau der Projekt-Detailseite): kein Sprungmarken-Link mehr,
    # sondern ein echter Reiter (siehe tests/test_v064_project_folders.py für
    # die vollständige Prüfung der Reiterleiste).
    assert 'id="zeitenStand"' in project_html and 'data-reiter="ausfuehrung"' in project_html  # seit 1.9.129 die Akte (Projektmappe und Auftragsseite in einer Seite): Zeiten im Reiter „Ausführung“


def test_version_1_0():
    root=Path(__file__).parents[1]
    assert re.match(r"^\d+\.\d+\.\d+$", (root/"VERSION").read_text(encoding="utf-8").strip())


def test_time_tracking_ui_loads_core_data_independently_and_auth_exposes_employee_id():
    root=Path(__file__).parents[1]
    html=(root/"app/templates/zeiten.html").read_text(encoding="utf-8")  # seit 1.9.98 „Zeiten“ (bis 1.9.97 Zeiterfassung mit Ausweichwegen)
    main=(root/"app/routers/auth.py").read_text(encoding="utf-8")
    # die Tätigkeiten lädt die Seite getrennt -- fehlt die Liste, bleibt der Dialog benutzbar
    assert "api('/api/settings/option-groups/time_entry_activities').catch(function(){return {options:[]}})" in html
    assert '"employee_id"' in main and "user.employee_id" in main  # exakte Formatierung ist beim Umbau auf 2FA (1.3.34) nicht mehr identisch
