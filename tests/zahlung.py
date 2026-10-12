"""Test-Helfer seit 1.8.78 (Zahlungsstufe Z1): "bezahlt" ist kein Status mehr, sondern folgt aus gebuchten Zahlungen.

voll_bezahlen(db, invoice) bucht einen Zahlungseingang über das Brutto der Rechnung und ordnet ihn ganz ihr zu -- über denselben
Weg wie die Oberfläche (app/payments.py::book_payment()). Für Tests, die eine bezahlte Rechnung brauchen (bis 1.8.77
mark_invoice_paid()); die Zahlungen selbst prüft tests/test_v381_zahlungen.py."""

from datetime import date

from app.berlin_time import berlin_today
from app.payments import Line, book_payment, invoice_customer_id, payable_gross


def voll_bezahlen(db, invoice, received_on: date | None = None, *, user_name: str = "Test"):
    gross = payable_gross(invoice)
    return book_payment(db, customer_id=invoice_customer_id(invoice), received_on=received_on or berlin_today(),
                        amount=gross, note=None, lines=[Line(invoice.id, zahlung=gross)], user_name=user_name)
