from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.main import (
    create_customer, create_project, create_quote, add_quote_item,
    add_quote_section_api, add_free_item_api, update_item_layout_api,
    auto_number_quote_api,
)
from app.models import Service
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.service import persist_project
from app.projects import load_quote, quote_to_dict
from app.quote_framed_pdf import build_quote_framed_pdf
from app.schemas import (
    CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate,
    QuoteSectionCreate, QuoteFreeItemCreate, QuoteItemLayoutUpdate,
)


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def build_base(db):
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    parsed = parse_leistungen_dach_xml(sample.read_bytes())
    persist_project(db, parsed, "Thiefes.xml")
    customer = create_customer(CustomerCreate(
        last_name="Familie LV-Test", street="Dachweg 1", postal_code="52531", city="Übach-Palenberg"
    ), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Dachsanierung"), db)
    quote = create_quote(project.id, QuoteCreate(title="Angebot Dachsanierung"), db)
    return customer, project, quote


def test_lv_sections_free_positions_optional_total_and_oz():
    db = make_db()
    _, _, quote = build_base(db)
    quote = add_quote_section_api(quote.id, QuoteSectionCreate(title="Steildach"), db)
    top = quote.sections[0]
    quote = add_quote_section_api(quote.id, QuoteSectionCreate(title="Dachentwässerung", parent_id=top.id), db)
    child = next(s for s in quote.sections if s.parent_id == top.id)

    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    quote = add_quote_item(quote.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("10"), section_id=child.id), db)
    assert quote.items[0].section_id == child.id
    assert quote.items[0].gaeb_oz == "01.01.0010"

    quote = add_free_item_api(quote.id, QuoteFreeItemCreate(
        short_text="Optionaler Austausch", quantity=Decimal("2"), unit="Stück",
        unit_price=Decimal("100"), position_type="alternativ", section_id=child.id,
        include_in_total=False,
    ), db)
    assert Decimal(quote.optional_total) == Decimal("200.00")
    assert quote.items[-1].include_in_total is False
    assert quote.items[-1].gaeb_oz == "01.01.0020"

    old_net = Decimal(quote.net_total)
    quote = update_item_layout_api(quote.id, quote.items[-1].id, QuoteItemLayoutUpdate(section_id=child.id, include_in_total=True), db)
    assert Decimal(quote.net_total) == old_net + Decimal("200.00")


def test_quote_pdf_is_valid_pdf():
    db = make_db()
    _, _, quote_out = build_base(db)
    quote_out = add_quote_section_api(quote_out.id, QuoteSectionCreate(title="Dacharbeiten"), db)
    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    quote_out = add_quote_item(quote_out.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("5"), section_id=quote_out.sections[0].id), db)
    quote = load_quote(db, quote_out.id)
    pdf = build_quote_framed_pdf(db, quote)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 2500


def test_quote_editor_template_and_route_features_exist():
    root = Path(__file__).parents[1]
    html = (root / "app" / "templates" / "quote_editor.html").read_text(encoding="utf-8")
    main = (root / "app" / "main.py").read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in sorted((root / "app" / "routers").glob("*.py")))
    assert "Leistungsverzeichnis" in html
    assert "Drag & Drop" in html
    assert "+ Freie Position" in html
    assert "Projektkalkulation" in html
    assert "/api/quotes/{quote_id}/pdf" in main
    assert '/quotes/{quote_id}/edit' in main
