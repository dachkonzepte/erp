"""Version 1.3.1 -- PDF-Rahmen, erste Etappe: Inhalts-Regressionstest für die Mahnung
(app/reminder_pdf.py), geschrieben als Baseline VOR dem Umbau auf den gemeinsamen PDF-Rahmen
(app/document_frame.py, siehe test_v226_document_frame.py) und danach unverändert grün geblieben
-- der Rahmen ändert das Aussehen (Briefkopf/Fußzeile wandern in den optionalen, abschaltbaren
Rahmen, siehe CLAUDE.md "PDF-Rahmen"), nicht den Inhalt. Prüft Mahnstufe, Rechnungsnummer,
Betrag, Frist und Anschrift als tatsächlichen PDF-Textinhalt (Content-Stream-Dekoder aus
tests/test_v213_inspection_items.py, nicht dupliziert)."""

from app.document_pdf import money
from app.reminder_pdf import build_reminder_pdf
from app.reminders import create_reminder, ensure_default_reminder_levels, finalize_and_send_reminder
from tests.test_v153_mahnwesen import db_session, make_sent_overdue_invoice
from tests.test_v213_inspection_items import _extract_pdf_text


def test_reminder_pdf_contains_level_invoice_amount_deadline_and_address():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)
    finalize_and_send_reminder(db, reminder)

    pdf_bytes = build_reminder_pdf(db, reminder)
    assert pdf_bytes[:4] == b"%PDF"
    text = _extract_pdf_text(pdf_bytes)

    # Mahnstufe (Betreff)
    assert b"1. Mahnung" in text
    # Rechnungsnummer (Bezug) und Mahnungsnummer (Beleg selbst)
    assert invoice.invoice_number.encode("utf-8") in text
    assert reminder.reminder_number.encode("utf-8") in text
    # Betrag: Gesamtbetrag (offener Betrag + Mahngebühr) in der Forderungsaufstellung
    total = (reminder.outstanding_amount + reminder.fee_amount).quantize(reminder.outstanding_amount)
    assert money(total).encode("utf-8") in text
    # Frist: die neue Zahlungsfrist steht im Mahntext ("... bis zum {neue_frist}.")
    assert reminder.new_due_date.strftime("%d.%m.%Y").encode("utf-8") in text
    # Anschrift
    assert invoice.customer_name.encode("utf-8") in text


def test_reminder_pdf_draft_shows_placeholder_number():
    """Ein noch nicht versendeter Entwurf hat keine reminder_number -- die Mahnung muss trotzdem
    ein gültiges PDF ergeben (unverändertes Verhalten, siehe reminder_pdf.py "(Entwurf)")."""
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)

    pdf_bytes = build_reminder_pdf(db, reminder)
    assert pdf_bytes[:4] == b"%PDF"
    text = _extract_pdf_text(pdf_bytes)
    # "(" und ")" sind in PDF-Textliteralen Trennzeichen -- ein wörtliches "(Entwurf)" im
    # Inhalt wird deshalb als "\(Entwurf\)" escaped, daher hier nur auf den Wortteil geprüft.
    assert b"Entwurf" in text
