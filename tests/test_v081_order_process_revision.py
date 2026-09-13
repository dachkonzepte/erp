from datetime import date
from decimal import Decimal
from pathlib import Path
import re

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.main import create_customer, create_project, create_quote, add_quote_item, update_quote_item
from app.models import Service, OrderRevision
from app.orders import (
    create_order_from_quote, load_order, order_to_dict, sync_order_from_source_quote,
    update_order_item, update_order_section,
)
from app.projects import load_quote, create_quote_section
from app.schemas import CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate, QuoteItemUpdate
from app.service import persist_project
from app.work_preparation import ensure_preparation, preparation_to_dict


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup(db):
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    persist_project(db, parse_leistungen_dach_xml(sample.read_bytes()), "Thiefes.xml")
    customer = create_customer(CustomerCreate(last_name="Prozess Kunde", street="Dachweg 1", postal_code="52531", city="Übach-Palenberg"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Prozess Projekt"), db)
    quote = create_quote(project.id, QuoteCreate(title="Angebot Prozess"), db)
    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    quote = add_quote_item(quote.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("10")), db)
    order = create_order_from_quote(
        db, quote.id, order_date=date(2026,9,1), execution_start=None, execution_end=None,
        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
        remarks=None, actor_name="Tobias",
    )
    return quote, order


def test_initial_order_has_revision_and_source_is_in_sync():
    db = db_session(); quote, order = setup(db)
    data = order_to_dict(load_order(db, order.id), db)
    assert data["source_quote_in_sync"] is True
    assert data["revision_count"] == 1
    rev = db.scalar(select(OrderRevision).where(OrderRevision.order_id == order.id))
    assert rev.revision_number == 1
    assert rev.reason == "Erstbeauftragung aus Angebot"


def test_changed_quote_can_be_synchronized_into_existing_order():
    db = db_session(); quote_out, order = setup(db)
    quote = load_quote(db, quote_out.id)
    item = quote.items[0]
    update_quote_item(quote.id, item.id, QuoteItemUpdate(
        quantity=Decimal("12"), short_text=item.short_text, long_text=item.long_text,
        unit=item.unit, unit_price=item.unit_price, position_type=item.position_type, gaeb_oz=item.gaeb_oz,
    ), db)
    create_quote_section(db, quote.id, "Zusätzlicher Titel", "Neu nach Auftrag", None)
    before = order_to_dict(load_order(db, order.id), db)
    assert before["source_quote_in_sync"] is False
    updated = sync_order_from_source_quote(db, load_order(db, order.id), actor_name="Tobias")
    data = order_to_dict(updated, db)
    assert data["source_quote_in_sync"] is True
    assert data["items"][0]["quantity"] == Decimal("12")
    assert any(s["title"] == "Zusätzlicher Titel" for s in data["sections"])
    assert data["revision_count"] == 2


def test_order_scope_is_directly_editable_and_auditable_basis_remains():
    db = db_session(); quote, order = setup(db)
    item = load_order(db, order.id).items[0]
    updated = update_order_item(
        db, order.id, item.id, quantity=Decimal("11.5"), unit=item.unit,
        unit_price=Decimal("77.77"), short_text="Geänderte Auftragsleistung",
        long_text=item.long_text, position_type=item.position_type, gaeb_oz=item.gaeb_oz,
        include_in_total=True,
    )
    data = order_to_dict(updated, db)
    assert data["items"][0]["quantity"] == Decimal("11.5")
    assert data["items"][0]["unit_price"] == Decimal("77.77")
    assert data["source_quote_in_sync"] is False


def test_work_preparation_refreshes_after_order_quantity_change_but_keeps_manual_plan():
    db = db_session(); quote, order = setup(db)
    prep = ensure_preparation(db, order.id)
    before = preparation_to_dict(db, prep)
    target = next(x for x in prep.materials if x.article_number == "5835413")
    target.planned_quantity = Decimal("99")
    target.supplier = "Testlieferant"
    db.commit()
    item = load_order(db, order.id).items[0]
    update_order_item(
        db, order.id, item.id, quantity=Decimal("20"), unit=item.unit,
        unit_price=item.unit_price, short_text=item.short_text, long_text=item.long_text,
        position_type=item.position_type, gaeb_oz=item.gaeb_oz, include_in_total=item.include_in_total,
    )
    after = preparation_to_dict(db, ensure_preparation(db, order.id))
    row = next(x for x in after["materials"] if x["article_number"] == "5835413")
    assert row["calculated_quantity"] == Decimal("21.000")
    assert row["planned_quantity"] == Decimal("99.000")
    assert row["supplier"] == "Testlieferant"


def test_update_script_reads_central_version_file():
    root = Path(__file__).parents[1]
    bat = (root / "update_windows.bat").read_text(encoding="utf-8")
    assert "if exist VERSION set /p APP_VERSION=<VERSION" in bat
    assert "Version %APP_VERSION% abgeschlossen" in bat
    assert re.match(r"^\d+\.\d+\.\d+$", (root / "VERSION").read_text(encoding="utf-8").strip())
