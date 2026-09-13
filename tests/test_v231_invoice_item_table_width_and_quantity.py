"""Version 1.3.9 -- Positionstabelle der Rechnung: eine Mengenspalte statt drei, mit Einheit, und
alle Tabellen (Positionstabelle, Summenblock, Forderungsaufstellung der Mahnung) auf derselben
Fluchtlinie wie Kopfbereich/Fließtext -- abgeleitet aus den tatsächlich konfigurierten Rändern
(document_frame.py::frame_content_width()), nicht mehr aus dem hart codierten PAGE_CONTENT_WIDTH.

Vorher (an einer echten Schlussrechnung nachgemessen, Standardränder 18mm/16mm): die
Positionstabelle zeigte "Menge (Soll)"/"Ist (gesamt)"/"abger. Menge" ohne Einheit, ihre
colWidths summierten sich auf 185mm statt der verfügbaren 176mm -- reportlab zentriert eine
Tabelle ohne eigenes hAlign standardmäßig (Table.hAlign default 'CENTER'), wodurch die zu breite
Tabelle sowohl links (Position bei 15.82mm statt 18.20mm) als auch rechts (Betrag-Wert bei
196.35mm statt 194.00mm) über die gemeinsame Fluchtlinie hinausragte."""

from decimal import Decimal

from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v227_din5008_header_block import _char_x_range_mm
from tests.test_v230_invoice_pdf_shared_frame import _page_text

from app.document_page_margins import update_margins
from app.invoices import add_invoice_item, create_schlussrechnung, finalize_and_send_invoice


def _make_finalized_invoice(db, **kwargs):
    order, item = make_order_with_item(db, **kwargs)
    invoice = create_schlussrechnung(db, order)
    invoice = finalize_and_send_invoice(db, invoice)
    return invoice


# ---------------------------------------------------------------------------
# Punkt 1 + 2: eine Mengenspalte (abgerechnete Menge), mit Einheit
# ---------------------------------------------------------------------------

def test_invoice_pdf_shows_single_quantity_column_with_unit_not_soll_ist_split():
    from app.invoice_pdf import build_invoice_pdf

    db = db_session()
    invoice = _make_finalized_invoice(db, quantity=Decimal("50.223"), unit_price=Decimal("50"))

    pdf_bytes = build_invoice_pdf(db, invoice)
    text = _extract_pdf_text(pdf_bytes)

    assert b"50,223" in text
    assert b"Menge (Soll)" not in text
    assert b"Ist (gesamt)" not in text
    assert b"abger. Menge" not in text

    # "m2" (Sonderzeichen U+00B2) wird von reportlab ueber WinAnsiEncoding als Einzelbyte
    # geschrieben, nicht als UTF-8-Sequenz -- _extract_pdf_text() (rohe Content-Stream-Bytes)
    # kann das nicht zuverlaessig gegen einen Python-str vergleichen, pypdfium2s Textlayer schon.
    assert "m²" in _page_text(pdf_bytes, 0)


def test_invoice_detail_screen_still_shows_all_three_quantities():
    """Punkt 1 verlangt: nur reduzieren, wenn Soll/Ist/abgerechnet anderswo sichtbar bleiben --
    invoice_detail.html (Bildschirmansicht) zeigt weiterhin alle drei nebeneinander, siehe
    invoice_detail.html Zeile 16 (inv-head: Soll / Ist (gesamt) / abgerechnet). Reiner
    Quelltext-Beleg, kein Rendertest (die Seite lädt ihre Daten client-seitig per fetch())."""
    import re

    with open("app/templates/invoice_detail.html", encoding="utf-8") as f:
        src = f.read()
    head_match = re.search(r'class="inv-head">(.*?)</div><div id="itemsList"', src)
    assert head_match is not None
    head = head_match.group(1)
    assert ">Soll<" in head
    assert ">Ist (gesamt)<" in head
    assert ">abgerechnet<" in head


# ---------------------------------------------------------------------------
# 1.3.17, Punkt 1+2: Waehrung nur noch im Spaltenkopf ("GP/EUR" statt "Betrag"), Menge/EH vor
# Leistung
# ---------------------------------------------------------------------------

def test_currency_removed_from_item_values_kept_in_headers_and_totals():
    from app.invoice_pdf import build_invoice_pdf

    db = db_session()
    # Zweite Position mit anderem Betrag, damit der Zeilenwert eindeutig vom (weiterhin "EUR"
    # tragenden) Summenblock unterscheidbar bleibt -- add_invoice_item() vor dem Finalisieren.
    order, _ = make_order_with_item(db, quantity=Decimal("3"), unit_price=Decimal("7"))
    invoice = create_schlussrechnung(db, order)
    add_invoice_item(db, invoice, short_text="Zweite Position", long_text="", unit="Stk", unit_price=Decimal("50"), ist_quantity=Decimal("1"))
    invoice = finalize_and_send_invoice(db, invoice)

    pdf_bytes = build_invoice_pdf(db, invoice)
    text = _extract_pdf_text(pdf_bytes)
    assert b"EP/EUR" in text
    assert b"GP/EUR" in text
    assert b"Betrag" not in text  # alte Spaltenueberschrift, seit 1.3.17 vereinheitlicht
    assert b"21,00 EUR" not in text  # Zeilensumme (3*7) ohne Waehrungssuffix
    assert b"50,00 EUR" not in text
    assert b"21,00" in text and b"50,00" in text
    assert b"71,00 EUR" in text  # Nettosumme (21+50) behaelt die Waehrung im Summenblock


def test_menge_and_eh_columns_appear_before_leistung_column():
    db = db_session()
    invoice = _make_finalized_invoice(db, quantity=Decimal("50.223"), unit_price=Decimal("50"))
    from app.invoice_pdf import build_invoice_pdf
    pdf_bytes = build_invoice_pdf(db, invoice)

    pos_left, _ = _char_x_range_mm(pdf_bytes, "Pos.")
    menge_left, _ = _char_x_range_mm(pdf_bytes, "Menge Einh.")
    leistung_left, _ = _char_x_range_mm(pdf_bytes, "Leistung")
    assert pos_left < menge_left < leistung_left


# ---------------------------------------------------------------------------
# Punkt 3: gleiche Fluchtlinie wie Kopfbereich/Fließtext -- unter Standardraendern...
# ---------------------------------------------------------------------------

def _build_measurable_invoice_pdf(db, **margin_overrides):
    from app.invoice_pdf import build_invoice_pdf

    if margin_overrides:
        update_margins(db, "invoice", "first", **margin_overrides)
        update_margins(db, "invoice", "continuation", **margin_overrides)
    invoice = _make_finalized_invoice(db, quantity=Decimal("50.223"), unit_price=Decimal("50"))
    return build_invoice_pdf(db, invoice), invoice


def test_item_table_left_edge_matches_sender_line_and_heading_default_margins():
    db = db_session()
    pdf_bytes, _ = _build_measurable_invoice_pdf(db)
    left_margin_mm = 18.0
    for needle in ["DACHKONZEPTE", "Schlussrechnung", "Pos.", "Nettosumme"]:
        r = _char_x_range_mm(pdf_bytes, needle)
        assert r is not None, f"{needle!r} nicht im PDF gefunden"
        left, _ = r
        assert abs(left - left_margin_mm) < 0.6, f"{needle!r}: left={left:.2f}mm, erwartet ~{left_margin_mm}mm"


def test_item_table_right_edge_matches_right_margin_default_margins():
    db = db_session()
    pdf_bytes, invoice = _build_measurable_invoice_pdf(db)
    right_margin_mm = 210.0 - 16.0
    for needle in ["2.511,15 EUR", "2.988,27 EUR"]:
        r = _char_x_range_mm(pdf_bytes, needle)
        assert r is not None, f"{needle!r} nicht im PDF gefunden"
        _, right = r
        assert abs(right - right_margin_mm) < 0.6, f"{needle!r}: right={right:.2f}mm, erwartet ~{right_margin_mm}mm"


# ---------------------------------------------------------------------------
# ... UND unter selbst konfigurierten (von den Standardwerten abweichenden) Raendern -- der
# eigentliche Beleg fuer "die Breite richtet sich nach dem Satzspiegel, nicht umgekehrt".
# ---------------------------------------------------------------------------

def test_item_table_and_totals_follow_custom_margins_not_hardcoded_default():
    db = db_session()
    pdf_bytes, _ = _build_measurable_invoice_pdf(
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


def test_quantity_and_unit_do_not_touch_each_other():
    """Nur die AEUSSEREN Spaltenraender der Positionstabelle sind genullt (LEFTPADDING erste,
    RIGHTPADDING letzte Spalte) -- zwischen Menge und EH muss weiterhin ein sichtbarer
    Zwischenraum bleiben, sonst laesen sie wie "50,223m²" ohne Leerzeichen zusammen.

    Seit 1.3.17 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Rechnung, Punkt 2) bewusst ENGER als vorher:
    Menge/EH stehen jetzt VOR der Leistung und sollen wie eine zusammengehoerige Einheit wirken
    ("1,00 psch") -- die Grenze sinkt deshalb von vorher 1.0mm auf einen kleinen, aber
    sichtbaren Mindestabstand."""
    db = db_session()
    pdf_bytes, _ = _build_measurable_invoice_pdf(db)
    _, qty_right = _char_x_range_mm(pdf_bytes, "50,223")
    unit_left, _ = _char_x_range_mm(pdf_bytes, "m²")
    gap = unit_left - qty_right
    assert 0.3 < gap < 3.0, f"Abstand Menge/EH={gap:.2f}mm -- erwartet ein kleiner, aber sichtbarer Zwischenraum"


# ---------------------------------------------------------------------------
# Derselbe Fix gilt fuer die Mahnung (Forderungsaufstellung) -- "in allen bereits umgestellten
# Renderern", nicht nur der Rechnung.
# ---------------------------------------------------------------------------

def test_reminder_amount_table_follows_custom_margins_too():
    from app.reminders import create_reminder, ensure_default_reminder_levels
    from app.reminder_pdf import build_reminder_pdf
    from tests.test_v153_mahnwesen import make_sent_overdue_invoice

    db = db_session()
    update_margins(db, "reminder", "first", top_mm=Decimal("42.0"), bottom_mm=Decimal("20.0"), left_mm=Decimal("30.0"), right_mm=Decimal("25.0"))
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    invoice.customer_address = "Musterstraße 1, 12345 Musterstadt"
    db.commit()
    reminder = create_reminder(db, invoice, 1)

    pdf_bytes = build_reminder_pdf(db, reminder)
    left_margin_mm = 30.0
    right_margin_mm = 210.0 - 25.0
    left, _ = _char_x_range_mm(pdf_bytes, "DACHKONZEPTE")
    assert abs(left - left_margin_mm) < 0.6
    _, right = _char_x_range_mm(pdf_bytes, "5.955,00 EUR")
    assert abs(right - right_margin_mm) < 0.6
