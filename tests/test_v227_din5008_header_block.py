"""Version 1.3.3 -- gemeinsamer Kopfbereich-Baustein build_din5008_header_block()
(app/document_pdf.py), erster Nutzer die Mahnung (app/reminder_pdf.py).

Deckt ab: die kleine, unterstrichene Absenderzeile (DIN 5008), die Empfängeranschrift als echte,
einzelne Zeilen statt eines zusammengezogenen Absatzes, den Meta-Block als Zweispalten-Tabelle mit
einer Zeile pro Beschriftung/Wert-Paar, sowie die Mahnung als konkreten Nutzer (inkl. Aufteilung
des eingefrorenen "Straße, PLZ Ort"-Textschnappschusses in zwei Zeilen). build_customer_and_meta_block()
(weiterhin von quote_pdf.py/order_pdf.py/invoice_pdf.py genutzt) bleibt unangetastet -- das prüft
bereits test_v153_mahnwesen.py::test_reminder_pdf_reuses_shared_document_blocks."""

from decimal import Decimal

import pytest
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table

from app.document_pdf import build_din5008_header_block, build_styles
from tests.test_v153_mahnwesen import db_session, make_sent_overdue_invoice
from tests.test_v213_inspection_items import _extract_pdf_text


def _left_cell_flowables(result):
    """result ist [outer_table, spacer] -- outer_table hat genau eine Zeile mit drei Zellen
    (Anschrift, leere Lücken-Spalte, Meta-Tabelle -- siehe DIN5008_GAP_COL_WIDTH)."""
    outer = result[0]
    return outer._cellvalues[0][0]


def _meta_table(result):
    outer = result[0]
    return outer._cellvalues[0][2]


# ---------------------------------------------------------------------------
# build_din5008_header_block() isoliert
# ---------------------------------------------------------------------------

def test_sender_line_is_underlined_and_smaller_than_body_text():
    styles = build_styles()
    result = build_din5008_header_block("Firma - Straße 1 - 12345 Ort", ["Empfänger"], [("Datum", "01.01.2026")], styles)
    left = _left_cell_flowables(result)
    sender_para = left[0]
    assert isinstance(sender_para, Paragraph)
    assert "<u>" in sender_para.text and "</u>" in sender_para.text
    assert "Firma - Straße 1 - 12345 Ort" in sender_para.text
    assert sender_para.style.fontSize < styles["body"].fontSize


def test_without_sender_line_only_recipient_paragraph_is_drawn():
    styles = build_styles()
    result = build_din5008_header_block(None, ["Empfänger", "Straße 1"], [("Datum", "01.01.2026")], styles)
    left = _left_cell_flowables(result)
    assert len(left) == 1
    assert isinstance(left[0], Paragraph)
    assert "<u>" not in left[0].text


def test_recipient_lines_stay_on_separate_lines_not_merged():
    styles = build_styles()
    result = build_din5008_header_block(
        "Absender", ["Max Mustermann", "Musterstraße 1", "12345 Musterstadt"], [("Datum", "01.01.2026")], styles,
    )
    left = _left_cell_flowables(result)
    recipient_para = left[-1]
    assert recipient_para.text == "Max Mustermann<br/>Musterstraße 1<br/>12345 Musterstadt"


def test_empty_recipient_lines_are_skipped():
    styles = build_styles()
    result = build_din5008_header_block(None, ["Max Mustermann", "", "12345 Musterstadt"], [("Datum", "01.01.2026")], styles)
    left = _left_cell_flowables(result)
    assert left[0].text == "Max Mustermann<br/>12345 Musterstadt"


def test_sender_line_spacing_to_recipient_is_tight():
    """Seit 1.3.17 (Betreiberfund, CLAUDE.md "Gemeinsamer Dokumenttyp"): der Abstand zwischen der
    Absenderzeile und der Anschrift darunter war mit 2mm zu groß -- beide sollten als ein Block
    wirken. Der Spacer dazwischen ist jetzt auf 0,8mm verkleinert; betrifft alle vier
    Dokumenttypen, die diesen gemeinsamen Baustein nutzen."""
    styles = build_styles()
    result = build_din5008_header_block("Firma - Straße 1 - 12345 Ort", ["Empfänger"], [("Datum", "01.01.2026")], styles)
    left = _left_cell_flowables(result)
    spacer = left[1]
    assert isinstance(spacer, Spacer)
    assert spacer.height < 2 * mm  # vorher 2mm
    assert spacer.height == pytest.approx(0.8 * mm)


def test_meta_table_has_one_row_per_label_value_pair_not_two_per_row():
    styles = build_styles()
    meta_rows = [("Mahnungsnr.", "M-0001"), ("Datum", "01.01.2026"), ("zu Rechnung", "R-0001"), ("vom", "02.01.2026")]
    result = build_din5008_header_block(None, ["Kunde"], meta_rows, styles)
    meta_table = _meta_table(result)
    assert len(meta_table._cellvalues) == 4
    assert meta_table._cellvalues[0] == ["Mahnungsnr.", "M-0001"]
    assert meta_table._cellvalues[2] == ["zu Rechnung", "R-0001"]


# ---------------------------------------------------------------------------
# Reminder als konkreter Nutzer (app/reminder_pdf.py)
# ---------------------------------------------------------------------------

def test_reminder_pdf_uses_din5008_header_block_and_splits_frozen_address():
    from app.reminders import create_reminder, ensure_default_reminder_levels
    from app.reminder_pdf import build_reminder_pdf

    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    invoice.customer_address = "Musterstraße 1, 12345 Musterstadt"
    db.commit()
    reminder = create_reminder(db, invoice, 1)

    pdf_bytes = build_reminder_pdf(db, reminder)
    assert pdf_bytes[:4] == b"%PDF"
    text = _extract_pdf_text(pdf_bytes)
    assert b"Musterstra" in text
    assert b"12345" in text
    assert b"Mahnungsnr" in text
    assert b"Datum" in text
    assert b"zu Rechnung" in text


def test_reminder_pdf_without_customer_address_does_not_crash():
    """invoice.customer_address kann None sein (z.B. make_sent_overdue_invoice() setzt es
    nicht) -- der neue Split-Code darf dann nicht auf None.split() laufen."""
    from app.reminders import create_reminder, ensure_default_reminder_levels
    from app.reminder_pdf import build_reminder_pdf

    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    assert invoice.customer_address is None
    reminder = create_reminder(db, invoice, 1)

    pdf_bytes = build_reminder_pdf(db, reminder)
    assert pdf_bytes[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Linke/rechte Fluchtlinie -- tatsächlich im PDF nachgemessen (pypdfium2-Zeichenboxen), nicht nur
# über die Flowable-Struktur geprüft. Siehe CLAUDE.md, Abschnitt "Kopfbereich", Nachtrag zum
# nachträglich gemessenen Zellenpolster-Fehler.
# ---------------------------------------------------------------------------

def _char_x_range_mm(pdf_bytes: bytes, needle: str) -> tuple[float, float] | None:
    import pypdfium2 as pdfium

    mm_per_pt = 25.4 / 72.0
    pdf = pdfium.PdfDocument(pdf_bytes)
    textpage = pdf[0].get_textpage()
    try:
        searcher = textpage.search(needle, match_case=False)
        result = searcher.get_next()
        searcher.close()
        if result is None:
            return None
        idx, count = result
        left, _, _, _ = textpage.get_charbox(idx)
        _, _, right, _ = textpage.get_charbox(idx + count - 1)
        return left * mm_per_pt, right * mm_per_pt
    finally:
        textpage.close()
        pdf.close()


def _build_measurable_reminder_pdf(db):
    from app.reminders import create_reminder, ensure_default_reminder_levels
    from app.reminder_pdf import build_reminder_pdf

    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    invoice.customer_address = "Musterstraße 1, 12345 Musterstadt"
    invoice.property_name = "Testobjekt"
    invoice.property_address = "Objektstraße 2\n54321 Objektstadt"
    db.commit()
    reminder = create_reminder(db, invoice, 1)
    return build_reminder_pdf(db, reminder)


def test_left_edge_of_sender_line_heading_body_and_amount_table_line_up():
    """Absenderzeile, Ausführungsort, Überschrift, Fließtext und Forderungstabelle müssen alle auf
    derselben linken Fluchtlinie (dem konfigurierten linken Rand, 18mm) beginnen -- das war vor
    1.3.3 nicht der Fall (Forderungstabelle lag durch hAlign="RIGHT" bei ca. 36mm, siehe
    CHANGELOG). Toleranz 0,6mm für normale Schriftbild-Unterschiede zwischen Buchstaben/Ziffern."""
    db = db_session()
    pdf_bytes = _build_measurable_reminder_pdf(db)
    left_margin_mm = 18.0
    for needle in ["DACHKONZEPTE", "Ausführungsort", "1. Mahnung", "Trotz Fälligkeit", "Offener Rechnungsbetrag"]:
        r = _char_x_range_mm(pdf_bytes, needle)
        assert r is not None, f"{needle!r} nicht im PDF gefunden"
        left, _ = r
        assert abs(left - left_margin_mm) < 0.6, f"{needle!r}: left={left:.2f}mm, erwartet ~{left_margin_mm}mm"


def test_right_edge_of_meta_value_and_amount_table_line_up_with_right_margin():
    """Wertespalte im Meta-Block UND Forderungstabelle müssen beide auf derselben rechten
    Fluchtlinie enden (rechter Rand bei 210-16=194mm) -- vor 1.3.3 endete die Meta-Wertespalte bei
    ca. 142mm, weit vor dem rechten Rand (siehe CHANGELOG)."""
    db = db_session()
    pdf_bytes = _build_measurable_reminder_pdf(db)
    right_margin_mm = 210.0 - 16.0
    for needle in ["R-2026-0001", "5.955,00 EUR"]:
        r = _char_x_range_mm(pdf_bytes, needle)
        assert r is not None, f"{needle!r} nicht im PDF gefunden"
        _, right = r
        assert abs(right - right_margin_mm) < 0.6, f"{needle!r}: right={right:.2f}mm, erwartet ~{right_margin_mm}mm"
