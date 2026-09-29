"""Kaufmännisches Runden: die eine Stelle für Geld- und Stundenrundung (seit 1.8.11).

Decimal.quantize() ohne rounding= rundet nach dem Decimal-Kontext, und der steht in Python auf
ROUND_HALF_EVEN: 0,125 wird zu 0,12, 0,135 zu 0,14. Kaufmännisch ist ROUND_HALF_UP, die Hälfte
rundet immer vom Nullpunkt weg (0,125 -> 0,13, -0,125 -> -0,13; PostgreSQL rundet NUMERIC genauso).
Jeder quantize()-Aufruf unter app/ nennt die Rundungsart deshalb ausdrücklich, für Geld und Stunden
über die Helfer hier. tests/test_v315_commercial_rounding.py sucht app/ nach Aufrufen ohne
rounding= ab.

Dasselbe halb-gerade Runden steckt in f"{betrag:.2f}": Ein Betrag mit mehr als zwei
Nachkommastellen wird beim Formatieren still gerundet. Beträge deshalb vor dem Formatieren mit
round_money() runden. Die Formatierer in app/document_pdf.py bleiben bewusst unverändert: Eine vor
1.8.11 versendete Rechnung druckt compute_invoice_totals() mit den alten, ungerundeten Werten nach
(Invoice.rounding_rule leer), und nur so kommt dasselbe Dokument heraus.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HUNDREDTH_HOUR = Decimal("0.01")

# Invoice.rounding_rule: Rechnungen ab 1.8.11 runden Positionsbeträge, USt und Skonto kaufmännisch.
# Leer heißt "vor 1.8.11 versendet", siehe app/invoices.py::invoice_rounding().
INVOICE_ROUNDING_HALF_UP = "half_up"


def round_half_up(value, exponent: Decimal) -> Decimal:
    """value auf die Stellen von exponent, Hälfte vom Nullpunkt weg. Ein float geht über seinen
    Text (0.285 -> "0.285"), nicht über seinen Binärwert (0.28499999...), der sonst abrundet."""
    if isinstance(value, float):
        value = str(value)
    return Decimal(value or 0).quantize(exponent, rounding=ROUND_HALF_UP)


def round_money(value) -> Decimal:
    """Geldbetrag auf den Cent."""
    return round_half_up(value, CENT)


def round_hours(value) -> Decimal:
    """Stunden auf zwei Nachkommastellen (Anzeige, Summen, Export). Gespeichert werden Stunden mit
    vier Nachkommastellen (TimeEntry.hours), dort über round_half_up(value, Decimal("0.0001"))."""
    return round_half_up(value, HUNDREDTH_HOUR)
