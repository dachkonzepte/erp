from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.main import create_customer, create_project, create_quote, add_quote_item, update_quote_item
from app.models import Service, AuditLog
from app.orders import create_order_from_quote, load_order, order_to_dict, update_order_header
from app.order_pdf import build_order_pdf
from app.projects import load_quote
from app.schemas import CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate, QuoteItemUpdate
from app.service import persist_project
from app.settings import update_sequence
from app.audit import set_audit_context, reset_audit_context


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_quote(db):
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    persist_project(db, parse_leistungen_dach_xml(sample.read_bytes()), "Thiefes.xml")
    customer = create_customer(CustomerCreate(last_name="Auftrag Kunde", street="Dachweg 1", postal_code="52531", city="Übach-Palenberg"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Auftrag Projekt"), db)
    quote = create_quote(project.id, QuoteCreate(title="Dachsanierung"), db)
    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    quote = add_quote_item(quote.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("10")), db)
    return project, quote


def create_order(db, quote_id):
    return create_order_from_quote(
        db, quote_id, order_date=date(2026, 9, 1), execution_start=date(2026, 9, 15),
        execution_end=date(2026, 10, 15), caseworker_employee_id=None,
        project_manager_employee_id=None, payment_terms="14 Tage netto", remarks="Testauftrag",
        status="beauftragt",
    )


def test_order_number_snapshot_and_quote_is_frozen():
    db = db_session(); project, quote_out = setup_quote(db)
    update_sequence(db, "order", format_pattern="AUF-{YYYY}-{NNNN}", start_value=500, next_value=500, reset_yearly=True)
    order = create_order(db, quote_out.id)
    data = order_to_dict(order)
    assert order.order_number == "AUF-2026-0500"
    assert data["project_number"] == project.project_number
    assert data["quote_number_snapshot"] == quote_out.quote_number
    assert data["items"][0]["quantity"] == Decimal("10")
    assert order.items[0].calculation_snapshot is not None
    assert order.items[0].calculation_snapshot.site_time_minutes > 0
    assert len(order.items[0].calculation_snapshot.materials) > 0
    original_total = data["gross_total"]

    qi = load_quote(db, quote_out.id).items[0]
    update_quote_item(quote_out.id, qi.id, QuoteItemUpdate(
        quantity=Decimal("99"), short_text=qi.short_text, long_text=qi.long_text, unit=qi.unit,
        unit_price=Decimal("999"), position_type=qi.position_type, gaeb_oz=qi.gaeb_oz,
    ), db)
    frozen = order_to_dict(load_order(db, order.id))
    assert frozen["items"][0]["quantity"] == Decimal("10")
    assert frozen["gross_total"] == original_total


def test_same_quote_cannot_be_commissioned_twice():
    db = db_session(); _, quote = setup_quote(db); create_order(db, quote.id)
    with pytest.raises(ValueError, match="bereits Auftrag"):
        create_order(db, quote.id)


def test_order_pdf_is_valid():
    db = db_session(); _, quote = setup_quote(db); order = create_order(db, quote.id)
    pdf = build_order_pdf(db, order)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 2500


class User:
    id = 77
    display_name = "Tobias Rödchen"
    username = "tobias"


def test_order_changes_are_audited_with_project():
    db = db_session(); _, quote = setup_quote(db)
    tokens = set_audit_context(User(), None)
    try:
        order = create_order(db, quote.id)
        update_order_header(db, order, title="Geänderter Auftrag", status="arbeitsvorbereitung", order_date=order.order_date,
                            execution_start=order.execution_start, execution_end=order.execution_end,
                            caseworker_employee_id=None, project_manager_employee_id=None,
                            payment_terms=order.payment_terms, remarks="Neue Bemerkung")
    finally:
        reset_audit_context(tokens)
    row = db.scalar(select(AuditLog).where(AuditLog.entity_type == "Auftrag", AuditLog.field_name == "status").order_by(AuditLog.id.desc()))
    assert row is not None
    assert row.actor_name == "Tobias Rödchen"
    assert row.project_id == order.project_id
    assert row.old_value == "beauftragt"
    assert row.new_value == "arbeitsvorbereitung"


def test_order_ui_and_routes_exist():
    root = Path(__file__).parents[1]
    main = (root / "app/main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root / "app/routers").glob("*.py")))
    quote = (root / "app/templates/quote_editor.html").read_text(encoding="utf-8")
    project = (root / "app/templates/project_folder.html").read_text(encoding="utf-8")
    order = (root / "app/templates/order.html").read_text(encoding="utf-8")
    assert "convert-to-order" in main and "/api/orders/{order_id}/pdf" in main
    assert "Angebot beauftragen" in quote and "createOrder" in quote
    assert "Aufträge im Projekt" in project
    assert "Auftragsstand" in order and "PDF-Auftragsbestätigung" in order
