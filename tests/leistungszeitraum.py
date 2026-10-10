"""Test-Helfer seit 1.8.74: jede Rechnung braucht beim Festschreiben einen Leistungszeitraum (app/service_period.py).

festschreiben(db, invoice) trägt in einen Entwurf ohne Zeitraum einen ein -- wie ein Klick auf "Übernehmen" auf der
Rechnungsseite, über denselben Weg (update_invoice_header()) -- und schreibt dann fest. Für Tests, die etwas anderes prüfen
als den Leistungszeitraum; die Pflicht selbst prüft tests/test_v377_leistungszeitraum.py mit finalize_and_send_invoice()."""

from datetime import date

from app.invoices import finalize_and_send_invoice, update_invoice_header

ZEITRAUM = (date(2026, 9, 1), date(2026, 9, 30))


def mit_zeitraum(db, invoice, start: date = ZEITRAUM[0], end: date = ZEITRAUM[1]):
    if invoice.status == "entwurf" and (invoice.service_period_start is None or invoice.service_period_end is None):
        update_invoice_header(db, invoice, service_period_start=invoice.service_period_start or start,
                              service_period_end=invoice.service_period_end or end)
    return invoice


def festschreiben(db, invoice):
    return finalize_and_send_invoice(db, mit_zeitraum(db, invoice))


ZEITRAUM_JSON = {"service_period_start": ZEITRAUM[0].isoformat(), "service_period_end": ZEITRAUM[1].isoformat()}
