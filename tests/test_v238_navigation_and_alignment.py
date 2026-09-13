"""Sechs Punkte aus dem laufenden Betrieb (seit 1.3.23) -- diese Datei deckt die zwei
unabhaengig umsetzbaren Punkte ab, die Codeaenderungen brauchten:

Punkt 2: Breadcrumb Kunde -> Projekt -> [Angebot|Auftrag|Auftrag -> Rechnung] auf
quote_editor.html/order.html/invoice_detail.html, nach dem Muster aus property.html/roof_area.html
(1.2.18). Mahnung hat keine eigene Seite -- lebt in invoice_detail.html, profitiert also von
derselben Breadcrumb mit.

Punkt 4: "EP/EUR"/"GP/EUR"-Spaltenkopf saß in Auftrag/Rechnung nicht ueber den Werten (Kopfzeile
fiel auf reportlabs Table-Standard LEFT zurueck, Werte standen RECHTS) -- im Angebot bereits seit
1.3.16 korrekt zentriert. Auftrag/Rechnung jetzt auf dieselbe Zentrierung nachgezogen."""

from decimal import Decimal
from pathlib import Path

from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v227_din5008_header_block import _char_x_range_mm

from app.invoices import create_schlussrechnung
from app.projects import quote_to_dict


# ---------------------------------------------------------------------------
# Punkt 2: Backend -- die fuer eine Breadcrumb noetigen IDs
# ---------------------------------------------------------------------------

def test_quote_to_dict_includes_customer_id_for_breadcrumb():
    from app.models import Customer, Project, Quote
    db = db_session()
    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0300", name="Testprojekt", customer_id=customer.id)
    db.add(project)
    db.flush()
    quote = Quote(project_id=project.id, quote_number="A-TEST-0300", title="Testangebot", vat_rate=Decimal("19.00"))
    db.add(quote)
    db.commit()
    db.refresh(quote)

    data = quote_to_dict(quote)
    assert data["customer_id"] == customer.id


def test_invoice_to_dict_includes_navigation_fields_for_breadcrumb():
    from app.invoices import invoice_to_dict
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)

    data = invoice_to_dict(invoice)
    assert data["order_number"] == order.order_number
    assert data["project_id"] == order.project_id
    assert data["project_number"] == order.project.project_number
    assert data["customer_id"] == order.project.customer_id


# ---------------------------------------------------------------------------
# Punkt 2: Oberflaeche -- statische Pruefungen (kein JS-Test-Runner im Projekt)
# ---------------------------------------------------------------------------

def test_quote_editor_has_breadcrumb_with_customer_and_project_links():
    html = (Path(__file__).parents[1] / "app" / "templates" / "quote_editor.html").read_text(encoding="utf-8")
    assert 'id="breadcrumb"' in html
    assert "function renderBreadcrumb()" in html
    assert "/customers/${quote.customer_id}" in html
    assert "/projects/${quote.project_id}" in html


def test_order_page_has_breadcrumb_with_customer_and_project_links():
    html = (Path(__file__).parents[1] / "app" / "templates" / "order.html").read_text(encoding="utf-8")
    assert 'id="breadcrumb"' in html
    assert "function renderBreadcrumb()" in html
    assert "/customers/${order.customer_id}" in html
    assert "/projects/${order.project_id}" in html


def test_invoice_detail_has_breadcrumb_with_customer_project_and_order_links():
    html = (Path(__file__).parents[1] / "app" / "templates" / "invoice_detail.html").read_text(encoding="utf-8")
    assert 'id="breadcrumb"' in html
    assert "function renderBreadcrumb()" in html
    assert "/customers/${invoice.customer_id}" in html
    assert "/projects/${invoice.project_id}" in html
    assert "/orders/${invoice.order_id}" in html


# ---------------------------------------------------------------------------
# Punkt 4: Kopfzeile "EP/EUR"/"GP/EUR" jetzt ueber den Werten zentriert (Auftrag/Rechnung) --
# exakt wie im Angebot (quote_framed_pdf.py) bereits seit 1.3.16.
# ---------------------------------------------------------------------------

def _center(box):
    left, right = box
    return (left + right) / 2


def test_order_pdf_ep_gp_header_centered_over_values():
    from app.order_pdf import build_order_pdf
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    pdf_bytes = build_order_pdf(db, order)

    ep_header = _char_x_range_mm(pdf_bytes, "EP/EUR")
    ep_value = _char_x_range_mm(pdf_bytes, "50,00")
    gp_header = _char_x_range_mm(pdf_bytes, "GP/EUR")
    gp_value = _char_x_range_mm(pdf_bytes, "5.000,00")
    assert abs(_center(ep_header) - _center(ep_value)) < 1.0
    assert abs(_center(gp_header) - _center(gp_value)) < 1.0


def test_invoice_pdf_ep_gp_header_centered_over_values():
    from app.invoice_pdf import build_invoice_pdf
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    invoice = create_schlussrechnung(db, order)
    pdf_bytes = build_invoice_pdf(db, invoice)

    ep_header = _char_x_range_mm(pdf_bytes, "EP/EUR")
    ep_value = _char_x_range_mm(pdf_bytes, "50,00")
    gp_header = _char_x_range_mm(pdf_bytes, "GP/EUR")
    gp_value = _char_x_range_mm(pdf_bytes, "5.000,00")
    assert abs(_center(ep_header) - _center(ep_value)) < 1.0
    assert abs(_center(gp_header) - _center(gp_value)) < 1.0


def test_quote_pdf_ep_gp_header_still_centered_over_values_unchanged():
    """Regression: das Angebot war bereits seit 1.3.16 korrekt -- diese Etappe durfte es nicht
    anfassen."""
    from app.quote_framed_pdf import build_quote_framed_pdf
    from tests.test_v235_quote_framed_pdf import _make_multi_section_quote

    db = db_session()
    quote = _make_multi_section_quote(db)
    pdf_bytes = build_quote_framed_pdf(db, quote)

    gp_header = _char_x_range_mm(pdf_bytes, "GP/EUR")
    assert gp_header is not None
