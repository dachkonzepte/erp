"""Version 1.3.10 -- vierte Etappe des PDF-Umbaus: der Auftrag wechselt auf den gemeinsamen
Rahmen (app/document_frame.py), analog zu Mahnung (1.3.1) und Rechnung (1.3.7).

Der Inhaltstest unten (test_order_pdf_contains_expected_content) ist bewusst VOR dem Umbau
geschrieben und muss unverändert grün bleiben, danach wie davor -- er prüft nur Teilstrings, die
mit dem Rahmenumbau selbst nichts zu tun haben (Auftragsnummer, Kundenname, Positionen, Netto,
Steuer, Brutto, Zahlungsbedingungen). Angebot und Einsatzbericht sind nicht Teil dieser Etappe.

Zusätzlich (Punkt 4/5 der Anfrage): dieselbe Breitenkorrektur wie bei der Rechnung (1.3.9,
185mm-colWidths-Summe vs. tatsächlich verfügbarer Breite) UND eine Regression dafür, dass der
Renderer/order_to_dict() den eingefrorenen Kunden-/Objekt-Schnappschuss nie durch die heutigen,
live nachschlagbaren Project/Customer-Daten ersetzt."""

from decimal import Decimal

import pypdfium2 as pdfium

from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v227_din5008_header_block import _char_x_range_mm
from tests.test_v230_invoice_pdf_shared_frame import _page_text
from tests.test_v167_pagination import count_pdf_pages

from app.document_page_margins import update_margins
from app.models import Customer, Employee, Order, OrderItem, Project
from app.project_pipeline_columns import default_pipeline_column_id


def test_order_pdf_contains_expected_content():
    """Muss vor UND nach dem Rahmenumbau identisch grün sein (siehe Modul-Docstring)."""
    from app.order_pdf import build_order_pdf

    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    order.payment_terms = "14 Tage netto"
    db.commit()

    pdf_bytes = build_order_pdf(db, order)
    assert pdf_bytes[:4] == b"%PDF"
    text = _extract_pdf_text(pdf_bytes)

    assert order.order_number.encode("utf-8") in text
    assert order.customer_name.encode("utf-8") in text
    assert b"Dacheindeckung" in text  # Position
    assert b"5.000,00" in text  # Nettosumme: 100 * 50
    assert b"19" in text  # MwSt.-Satz
    assert b"5.950,00" in text  # Bruttobetrag: 5000 * 1.19
    assert b"14 Tage netto" in text  # Zahlungsbedingung
    assert b"Auftragsbest" in text  # "Auftragsbestätigung"


# ---------------------------------------------------------------------------
# Rahmen: order steht in RENDERERS_USING_SHARED_FRAME, nutzt denselben geteilten Satz wie
# Mahnung/Rechnung
# ---------------------------------------------------------------------------

def test_order_is_registered_as_using_the_shared_frame():
    from app.document_frame import RENDERERS_USING_SHARED_FRAME

    assert "order" in RENDERERS_USING_SHARED_FRAME


def test_order_shares_background_and_margins_with_reminder_and_invoice_via_default():
    from app.document_layout import get_effective_background, set_background
    from app.document_page_margins import get_margins as _get_margins

    db = db_session()
    set_background(db, "default", "geteiltes-briefpapier.jpg", page_type="first")
    assert get_effective_background(db, "order", "first").stored_filename == "geteiltes-briefpapier.jpg"

    order_margins = _get_margins(db, "order", "first")
    invoice_margins = _get_margins(db, "invoice", "first")
    assert order_margins.top_mm == invoice_margins.top_mm == Decimal("25.0")


# ---------------------------------------------------------------------------
# Punkt 3: Sachbearbeiter/Projektleiter -- unabhaengig sichtbar, nicht mehr als feste Zweier-Paarung
# ---------------------------------------------------------------------------

def test_caseworker_and_project_manager_shown_independently():
    from app.order_pdf import build_order_pdf

    db = db_session()
    caseworker = Employee(first_name="Max", last_name="Mustermann")
    db.add(caseworker)
    db.commit()
    order, _ = make_order_with_item(db, caseworker_employee_id=caseworker.id)

    pdf_bytes = build_order_pdf(db, order)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Sachbearbeiter" in text
    assert b"Max Mustermann" in text
    assert b"Projektleiter" not in text  # keiner hinterlegt -- keine leere Zeile


def test_project_manager_shown_even_without_caseworker():
    """Vorher (zwei Felder in einer Zeile) haette das gar keine Zeile ergeben -- seit dem
    Umbau auf eine Zeile pro Feld ist Projektleiter unabhaengig vom Sachbearbeiter sichtbar."""
    from app.order_pdf import build_order_pdf

    db = db_session()
    project_manager = Employee(first_name="Erika", last_name="Musterfrau")
    db.add(project_manager)
    db.commit()
    order, _ = make_order_with_item(db, project_manager_employee_id=project_manager.id)

    pdf_bytes = build_order_pdf(db, order)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Projektleiter" in text
    assert b"Erika Musterfrau" in text
    assert b"Sachbearbeiter" not in text


# ---------------------------------------------------------------------------
# Punkt 5: eingefrorener Schnappschuss, nie order.project.customer
# ---------------------------------------------------------------------------

def test_order_pdf_uses_frozen_snapshot_not_live_customer_or_property_data():
    """order_to_dict()/order_pdf.py lesen ausschliesslich die eingefrorenen Order-Spalten
    (customer_name/customer_address/property_name/property_address) -- geprueft VOR dem Umbau
    (Punkt 5 der Anfrage), keine Fundstelle, die order.project.customer/-property live nachliest.
    Dieser Test haelt das als Regression fest: der Kunde zieht NACH der Beauftragung um, der
    Auftrag darf die neue Adresse nicht zeigen."""
    from app.order_pdf import build_order_pdf

    db = db_session()
    customer = Customer(name="Alter Kundenname", last_name="Alter Kundenname", street="Alte Straße 1", postal_code="11111", city="Altstadt")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0002", name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-TEST-0002", project_id=project.id, source_quote_id=2, quote_number_snapshot="A-TEST-0002",
        title="Testauftrag", vat_rate=Decimal("19.00"),
        customer_name="Alter Kundenname", customer_address="Alte Straße 1, 11111 Altstadt",
    )
    db.add(order)
    db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung", quantity=Decimal("1"), unit="m²", unit_price=Decimal("100")))
    db.commit()
    db.refresh(order)

    # Kunde zieht NACH der Beauftragung um -- der eingefrorene Auftrag darf das nicht nachziehen.
    customer.name = "Neuer Kundenname"
    customer.street = "Neue Straße 99"
    customer.postal_code = "99999"
    customer.city = "Neustadt"
    db.commit()

    pdf_bytes = build_order_pdf(db, order)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Alter Kundenname" in text
    assert b"Alte Stra" in text
    assert b"11111" in text
    assert b"Neuer Kundenname" not in text
    assert b"Neue Stra" not in text
    assert b"99999" not in text


# ---------------------------------------------------------------------------
# Punkt 4: 185mm-colWidths-Summe -> frame_content_width(), gleiche Fluchtlinie wie Kopfbereich
# ---------------------------------------------------------------------------

def _build_measurable_order_pdf(db, **margin_overrides):
    from app.order_pdf import build_order_pdf

    if margin_overrides:
        update_margins(db, "order", "first", **margin_overrides)
        update_margins(db, "order", "continuation", **margin_overrides)
    order, _ = make_order_with_item(db, quantity=Decimal("50.223"), unit_price=Decimal("50"))
    return build_order_pdf(db, order), order


def test_item_table_left_edge_matches_sender_line_and_heading_default_margins():
    db = db_session()
    pdf_bytes, _ = _build_measurable_order_pdf(db)
    left_margin_mm = 18.0
    for needle in ["DACHKONZEPTE", "Auftragsbest", "Pos.", "Nettosumme"]:
        r = _char_x_range_mm(pdf_bytes, needle)
        assert r is not None, f"{needle!r} nicht im PDF gefunden"
        left, _ = r
        assert abs(left - left_margin_mm) < 0.6, f"{needle!r}: left={left:.2f}mm, erwartet ~{left_margin_mm}mm"


def test_item_table_right_edge_matches_right_margin_default_margins():
    db = db_session()
    pdf_bytes, order = _build_measurable_order_pdf(db)
    right_margin_mm = 210.0 - 16.0
    for needle in ["2.511,15 EUR", "2.988,27 EUR"]:
        r = _char_x_range_mm(pdf_bytes, needle)
        assert r is not None, f"{needle!r} nicht im PDF gefunden"
        _, right = r
        assert abs(right - right_margin_mm) < 0.6, f"{needle!r}: right={right:.2f}mm, erwartet ~{right_margin_mm}mm"


def test_item_table_and_totals_follow_custom_margins_not_hardcoded_default():
    db = db_session()
    pdf_bytes, _ = _build_measurable_order_pdf(
        db, top_mm=Decimal("42.0"), bottom_mm=Decimal("20.0"), left_mm=Decimal("30.0"), right_mm=Decimal("25.0"),
    )
    left_margin_mm = 30.0
    right_margin_mm = 210.0 - 25.0
    for needle in ["DACHKONZEPTE", "Pos.", "Nettosumme"]:
        left, _ = _char_x_range_mm(pdf_bytes, needle)
        assert abs(left - left_margin_mm) < 0.6, f"{needle!r}: left={left:.2f}mm, erwartet ~{left_margin_mm}mm"
    for needle in ["2.511,15 EUR", "2.988,27 EUR"]:
        _, right = _char_x_range_mm(pdf_bytes, needle)
        assert abs(right - right_margin_mm) < 0.6, f"{needle!r}: right={right:.2f}mm, erwartet ~{right_margin_mm}mm"


# ---------------------------------------------------------------------------
# 1.3.17, Punkt 1+2: Waehrung nur noch im Spaltenkopf, Menge/EH vor Leistung
# ---------------------------------------------------------------------------

def test_currency_removed_from_item_values_kept_in_headers_and_totals():
    from app.order_pdf import build_order_pdf

    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("3"), unit_price=Decimal("7"))
    db.add(OrderItem(order_id=order.id, sort_order=20, position_number="2", short_text="Zweite Position", unit="Stk", unit_price=Decimal("50"), quantity=Decimal("1")))
    db.commit()

    pdf_bytes = build_order_pdf(db, order)
    text = _extract_pdf_text(pdf_bytes)
    assert b"EP/EUR" in text
    assert b"GP/EUR" in text
    assert b"21,00 EUR" not in text  # Zeilensumme (3*7) ohne Waehrungssuffix
    assert b"50,00 EUR" not in text
    assert b"21,00" in text and b"50,00" in text
    assert b"71,00 EUR" in text  # Nettosumme (21+50) behaelt die Waehrung im Summenblock


def test_menge_and_eh_columns_appear_before_leistung_column():
    from app.order_pdf import build_order_pdf

    db = db_session()
    order, _ = make_order_with_item(db)
    pdf_bytes = build_order_pdf(db, order)
    doc = pdfium.PdfDocument(pdf_bytes)
    tp = doc[0].get_textpage()
    text = tp.get_text_bounded()
    pos_left, *_ = tp.get_charbox(text.index("Pos."))
    menge_left, *_ = tp.get_charbox(text.index("Menge Einh."))
    leistung_left, *_ = tp.get_charbox(text.index("Leistung"))
    assert pos_left < menge_left < leistung_left


def test_quantity_and_unit_do_not_touch_each_other():
    """Seit 1.3.17 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Auftrag, Punkt 2) bewusst ENGER als vorher:
    Menge/EH stehen jetzt VOR der Leistung und sollen wie eine zusammengehoerige Einheit wirken
    ("1,00 psch") -- die Grenze sinkt deshalb von vorher 1.0mm (grosser Zellenpolster-Standard-
    Abstand) auf einen kleinen, aber sichtbaren Mindestabstand, der ein echtes Aneinanderkleben
    ("50,223m²" ohne jedes Leerzeichen) weiterhin ausschliesst."""
    db = db_session()
    pdf_bytes, _ = _build_measurable_order_pdf(db)
    _, qty_right = _char_x_range_mm(pdf_bytes, "50,223")
    unit_left, _ = _char_x_range_mm(pdf_bytes, "m²")
    gap = unit_left - qty_right
    assert 0.3 < gap < 3.0, f"Abstand Menge/EH={gap:.2f}mm -- erwartet ein kleiner, aber sichtbarer Zwischenraum"


# ---------------------------------------------------------------------------
# Wiederholungszeile auf Folgeseiten (bereits Teil des Rahmens, seit 1.3.7) -- greift jetzt auch
# fuer den Auftrag, ohne dass order_pdf.py dafuer etwas Eigenes bauen musste.
# ---------------------------------------------------------------------------

def _make_multipage_order(db):
    order, _ = make_order_with_item(db)
    for i in range(60):
        db.add(OrderItem(
            order_id=order.id, sort_order=20 + i, position_number=str(2 + i),
            short_text=f"Zusatzposition {i}", long_text="", unit="Stk",
            unit_price=Decimal("10"), quantity=Decimal("1"),
        ))
    db.commit()
    db.refresh(order)
    return order


def test_continuation_header_appears_on_order_multipage_pdf():
    from app.order_pdf import build_order_pdf

    db = db_session()
    order = _make_multipage_order(db)
    pdf_bytes = build_order_pdf(db, order)
    real_pages = count_pdf_pages(pdf_bytes)
    assert real_pages > 1

    continuation_marker = f"Auftragsnr.: {order.order_number}"
    first_page_text = _page_text(pdf_bytes, 0)
    assert continuation_marker not in first_page_text
    for page_index in range(1, real_pages):
        assert continuation_marker in _page_text(pdf_bytes, page_index)
