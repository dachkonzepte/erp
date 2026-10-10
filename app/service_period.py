"""Leistungszeitraum einer Rechnung (seit 1.8.74, Regel: jede Rechnung hat einen).

Beginn und Ende stehen an der Rechnung (Invoice.service_period_start/_end), Pflicht beim Festschreiben
(app/invoices.py::finalize_block_reason() -> missing_reason()), Ende >= Beginn (check_order()). Im Entwurf zeigt die
Rechnungsseite einen Vorschlag mit Quelle (proposal()); übernommen wird er nur per Klick -- nie still eingetragen.

Vorschlag je Rechnungsart (Zeitbuchungen: gebucht, mit Stunden, ohne Schlechtwetter -- dieselbe Auswahl wie die Rechnung aus
Aufwand, app/invoices.py::create_invoice_from_time_entries()):
- Abschlag (pauschal und nach Leistungsstand): erste bis letzte Zeitbuchung nach dem Ende des Zeitraums des vorigen gültigen
  Abschlags (festgeschrieben, nicht storniert, mit Zeitraum); ohne vorigen alle des Auftrags.
- Rechnung aus Aufwand: erste bis letzte abgerechnete Zeitbuchung (beim Anlegen festgehalten, Invoice.billed_work_from/_to).
- Schlussrechnung: erste Zeitbuchung des Auftrags bis zum Abnahmedatum (jüngste nicht verworfene Abnahme "abgenommen"), ohne
  Abnahme bis zur letzten Zeitbuchung.
- Ohne Zeitbuchungen am Auftrag: geplanter Zeitraum des Auftrags (Order.execution_start/_end).
- Storno: übernimmt den Zeitraum der stornierten Rechnung schon beim Anlegen (app/invoices.py::create_storno_draft()); fehlt er
  dort (vor 1.8.74), gibt es keinen Vorschlag."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Invoice, Order, OrderAcceptance, TimeEntry

NOT_WORK_ENTRY_TYPES = ("weather_winter", "weather_summer")  # wie create_invoice_from_time_entries()
PROGRESS_TYPES = ("abschlag_pauschal", "abschlag_leistungsstand")
VALID = ("versendet", "bezahlt")


@dataclass
class Proposal:
    start: date | None
    end: date | None
    source: str  # Quelle -- oder, ohne Daten, warum es keinen Vorschlag gibt

    def as_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "source": self.source}


def fmt(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def period_text(start: date, end: date) -> str:
    """"Leistungszeitraum: 01.10.2026 bis 08.10.2026", an einem Tag "Leistungsdatum: 08.10.2026" (PDF, Oberfläche)."""
    return f"Leistungsdatum: {fmt(start)}" if start == end else f"Leistungszeitraum: {fmt(start)} bis {fmt(end)}"


def check_order(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and end < start:
        raise ValueError(f"Das Ende des Leistungszeitraums ({fmt(end)}) liegt vor dem Beginn ({fmt(start)}).")


def missing_reason(invoice: Invoice) -> str | None:
    """Warum der Leistungszeitraum ein Festschreiben verhindert, sonst None."""
    start, end = invoice.service_period_start, invoice.service_period_end
    if start is None or end is None:
        missing = "Beginn und Ende" if start is None and end is None else ("Beginn" if start is None else "Ende")
        return f"Der Leistungszeitraum fehlt ({missing}) -- jede Rechnung braucht einen. Bitte unter Rechnungsdaten eintragen."
    if end < start:
        return f"Das Ende des Leistungszeitraums ({fmt(end)}) liegt vor dem Beginn ({fmt(start)})."
    return None


def _work_dates(db: Session, order_id: int, *, after: date | None = None) -> tuple[date | None, date | None, int]:
    stmt = select(func.min(TimeEntry.work_date), func.max(TimeEntry.work_date), func.count(TimeEntry.id)).where(
        TimeEntry.order_id == order_id, TimeEntry.status == "booked", TimeEntry.hours > 0,
        TimeEntry.entry_type.not_in(NOT_WORK_ENTRY_TYPES),
    )
    if after is not None:
        stmt = stmt.where(TimeEntry.work_date > after)
    first, last, count = db.execute(stmt).one()
    return first, last, count


def _planned(order: Order, why: str) -> Proposal:
    start, end = order.execution_start, order.execution_end
    if start is None and end is None:
        return Proposal(None, None, f"{why} Am Auftrag ist auch kein geplanter Zeitraum hinterlegt -- bitte eintragen.")
    if start is not None and end is not None and end < start:
        return Proposal(None, None, f"{why} Der geplante Zeitraum am Auftrag ist ungültig (Ende vor Beginn) -- bitte eintragen.")
    missing = "" if start is not None and end is not None else (" (nur Beginn geplant)" if end is None else " (nur Ende geplant)")
    return Proposal(start, end, f"{why} Geplanter Zeitraum des Auftrags{missing}.")


def _bookings(count: int) -> str:
    return "1 Zeitbuchung" if count == 1 else f"{count} Zeitbuchungen"


def proposal(db: Session, invoice: Invoice) -> Proposal:
    """Vorschlag für den Leistungszeitraum dieser Rechnung -- nur lesen, nichts wird eingetragen."""
    order = invoice.order
    kind = invoice.invoice_type
    if kind == "storno":
        original = db.get(Invoice, invoice.storno_of_invoice_id) if invoice.storno_of_invoice_id else None
        if original is not None and original.service_period_start and original.service_period_end:
            return Proposal(original.service_period_start, original.service_period_end,
                            f"Zeitraum der stornierten Rechnung {original.invoice_number}.")
        number = original.invoice_number if original is not None else "?"
        return Proposal(None, None, f"Die stornierte Rechnung {number} hat keinen Leistungszeitraum (vor 1.8.74) -- bitte "
                                    "eintragen.")
    if kind == "aufwand":
        if invoice.billed_work_from is None or invoice.billed_work_to is None:
            return _planned(order, "Die Rechnung enthält keine Zeitbuchungen (nur Material oder vor 1.8.74 angelegt).")
        return Proposal(invoice.billed_work_from, invoice.billed_work_to,
                        "Erste bis letzte abgerechnete Zeitbuchung dieser Rechnung.")
    if _work_dates(db, order.id)[2] == 0:
        return _planned(order, "Keine Zeitbuchungen am Auftrag.")
    if kind in PROGRESS_TYPES:
        previous = [i for i in order.invoices if i.id != invoice.id and i.invoice_type in PROGRESS_TYPES
                    and i.status in VALID and i.service_period_end is not None]
        cutoff_invoice = max(previous, key=lambda i: (i.service_period_end, i.id), default=None)
        after = cutoff_invoice.service_period_end if cutoff_invoice else None
        first, last, count = _work_dates(db, order.id, after=after)
        if count == 0:
            return Proposal(None, None, f"Keine Zeitbuchung nach dem Leistungszeitraum von {cutoff_invoice.invoice_number} "
                                        f"(bis {fmt(after)}) -- bitte eintragen.")
        since = (f" nach dem Leistungszeitraum von {cutoff_invoice.invoice_number} (bis {fmt(after)})" if cutoff_invoice
                 else " des Auftrags")
        return Proposal(first, last, f"Erste bis letzte Zeitbuchung{since} ({_bookings(count)}).")
    # Schlussrechnung (und jede andere Art): erste Zeitbuchung bis Abnahme, sonst bis zur letzten
    first, last, count = _work_dates(db, order.id)
    accepted = db.scalar(select(func.max(OrderAcceptance.accepted_on)).where(
        OrderAcceptance.order_id == order.id, OrderAcceptance.discarded_at.is_(None), OrderAcceptance.result == "abgenommen"))
    if accepted is not None and accepted >= first:
        return Proposal(first, accepted, f"Erste Zeitbuchung des Auftrags bis zur Abnahme am {fmt(accepted)}.")
    note = f" (die Abnahme am {fmt(accepted)} liegt vor der ersten Zeitbuchung)" if accepted is not None else " (keine Abnahme)"
    return Proposal(first, last, f"Erste bis letzte Zeitbuchung des Auftrags{note}, {_bookings(count)}.")
