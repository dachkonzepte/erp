from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.main import create_customer, create_project, create_quote, add_quote_item
from app.models import Service, Employee, WorkPreparationTask
from app.orders import create_order_from_quote
from app.schemas import CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate
from app.service import persist_project
from app.work_preparation import ensure_preparation, preparation_to_dict


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_order(db):
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    persist_project(db, parse_leistungen_dach_xml(sample.read_bytes()), "Thiefes.xml")
    customer = create_customer(CustomerCreate(last_name="AV Kunde", street="Dachweg 1", postal_code="52531", city="Übach-Palenberg"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="AV Projekt"), db)
    quote = create_quote(project.id, QuoteCreate(title="AV Angebot"), db)
    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    quote = add_quote_item(quote.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("10")), db)
    return create_order_from_quote(db, quote.id, order_date=date(2026,9,1), execution_start=date(2026,9,15), execution_end=date(2026,10,15), caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)


def test_work_preparation_uses_frozen_order_hours_and_materials():
    db=db_session(); order=setup_order(db)
    prep=ensure_preparation(db, order.id); data=preparation_to_dict(db, prep)
    assert data["planned_total_hours"] > 0
    assert data["material_count"] >= 4
    rinnen = next(x for x in data["materials"] if x["article_number"] == "5835413")
    assert rinnen["calculated_quantity"] == Decimal("10.500")
    assert rinnen["planned_quantity"] == Decimal("10.500")
    assert rinnen["source_position"] is not None


def test_work_preparation_tracks_team_and_tasks():
    db=db_session(); order=setup_order(db); prep=ensure_preparation(db, order.id)
    employee=Employee(employee_number="MA-1",first_name="Max",last_name="Dach",job_title="Geselle",employee_group="gewerblich",weekly_hours=Decimal("40"),hourly_wage=Decimal("20"),active=True)
    db.add(employee); db.flush()
    from app.models import WorkPreparationEmployee
    db.add(WorkPreparationEmployee(preparation_id=prep.id,employee_id=employee.id,role="Vorarbeiter",planned_hours=Decimal("20")))
    db.add(WorkPreparationTask(preparation_id=prep.id,title="Gerüst bestellen",status="offen",priority="hoch",assigned_employee_id=employee.id))
    db.commit(); data=preparation_to_dict(db, ensure_preparation(db,order.id))
    assert data["assigned_planned_hours"] == Decimal("20.00")
    assert data["open_task_count"] == 1
    assert data["employees"][0]["employee_name"] == "Max Dach"


def test_work_preparation_ui_and_routes_exist():
    root=Path(__file__).parents[1]
    main=(root/'app/main.py').read_text(encoding='utf-8') + "".join(p.read_text(encoding="utf-8") for p in sorted((root/'app/routers').glob("*.py")))
    page=(root/'app/templates/work_preparation.html').read_text(encoding='utf-8')
    order=(root/'app/templates/order.html').read_text(encoding='utf-8')
    project=(root/'app/templates/project_folder.html').read_text(encoding='utf-8')
    assert '/orders/{order_id}/work-preparation' in main
    assert 'Soll-Stunden' in page and 'Materialbedarf' in page and 'Team / Kolonne' in page
    assert 'workPrepLink' in order
    assert 'Arbeitsvorbereitung' in project
