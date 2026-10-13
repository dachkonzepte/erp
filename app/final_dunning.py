"""Mahnen nach der Endrechnung (seit 1.8.89, R4c Punkte 3-5, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung R4c").

Mit einer gültigen Endrechnung -- einer festgeschriebenen, nicht stornierten Schlussrechnung mit Abzügen (InvoiceDeduction) -- gehen
die abgezogenen Rechnungen (Abschläge, Rechnungen aus Aufwand) für das Mahnen in ihr auf:
- Punkt 3: eine abgezogene Rechnung wird nicht mehr einzeln gemahnt -- nicht in "zur Mahnung fällig", kein neuer Entwurf, ein offener
  Entwurf ist überholt, eine festgeschriebene Mahnung geht nicht mehr hinaus (eine Zustellung vor dem Tag der Endrechnung lässt sich
  weiter nachtragen).
- Punkt 4: ihr Einbehalt wird mit der Endrechnung fällig -- gemahnt wird (über die Endrechnung) ihr ganzer offener Betrag.
- Punkt 5: die Mahnung der Endrechnung lautet über den Zahlbetrag -- ihr eigener mahnfähiger Betrag plus die offenen Beträge der
  abgezogenen Rechnungen, in der Aufstellung je Rechnung mit Nummer (app/reminders.py::amounts_snapshot(), Format 4).

DunningState ist, was zu einer Rechnung gemahnt werden kann: der Zahlstand der Rechnung selbst (own, app/payments.py, None wenn sie
nie offen ist), an der Endrechnung die offenen abgezogenen Rechnungen (deducted), an einer abgezogenen die Endrechnung (settled_in), und
der angemahnte Hauptbetrag (dunnable). Nur Ableitung, nichts gespeichert; Zahlungen bleiben je Rechnung. Eine Schlussrechnung von vor
1.8.85 (ohne Abzüge) und jede Rechnung daneben bleiben bei der Regel je Rechnung.

Seit 1.8.90 (R4c Punkt 6): eine Endrechnung darf unter 0 € lauten. Ihr eigener Teil ist dann die Überzahlung (negativ) zuzüglich der
schon gebuchten Erstattungen; angemahnt wird, was nach Verrechnung mit den offenen abgezogenen Rechnungen bleibt, und übersteigt die
Überzahlung sie, ist der Rest ein Guthaben des Kunden (credit), das als Erstattung gebucht wird (app/payments.py::book_refund()).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .invoices import VALID_STATUSES
from .models import Invoice, InvoiceDeduction

ZERO = Decimal("0.00")
TYPE_WORDS = {"abschlag_pauschal": "Abschlag", "abschlag_leistungsstand": "Abschlag", "aufwand": "Rechnung"}


def _de(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


@dataclass(frozen=True)
class DeductedOpen:
    """Eine abgezogene Rechnung mit offenem Betrag an der Endrechnung: offen einschließlich Einbehalt (mit der Endrechnung fällig)."""
    invoice: Invoice
    open: Decimal
    retained: Decimal  # davon Einbehalt

    def as_dict(self) -> dict:
        return {"invoice_id": self.invoice.id, "invoice_number": self.invoice.invoice_number,
                "invoice_type": self.invoice.invoice_type, "open": self.open, "retained": self.retained}


@dataclass(frozen=True)
class DunningState:
    invoice: Invoice
    own: object | None  # app/payments.py::PaymentState der Rechnung selbst, None wenn sie nie offen ist
    dunnable: Decimal  # angemahnter Hauptbetrag
    deducted: tuple[DeductedOpen, ...] = field(default_factory=tuple)
    settled_in: Invoice | None = None
    is_final: bool = False  # gültige Endrechnung (Schlussrechnung mit Abzügen)
    own_part: Decimal = ZERO  # seit 1.8.90: eigener Teil am Zahlbetrag (an einer Überzahlung negativ, abzüglich Erstattungen)
    credit: Decimal = ZERO  # seit 1.8.90: Guthaben des Kunden aus der Endrechnung (noch zu erstatten)
    refunded: Decimal = ZERO  # seit 1.8.94: an der Endrechnung schon erstattet (Zahlungsausgänge, nicht zurückgenommen), positiv

    @property
    def own_dunnable(self) -> Decimal:
        return self.own.dunnable if self.own is not None else ZERO

    @property
    def deducted_open(self) -> Decimal:
        return sum((d.open for d in self.deducted), ZERO)

    def as_dict(self) -> dict:
        return {"dunnable": self.dunnable, "own_dunnable": self.own_dunnable, "own_part": self.own_part, "credit": self.credit,
                "is_final": self.is_final,
                "deducted": [d.as_dict() for d in self.deducted], "deducted_open": self.deducted_open,
                "settled_in": ({"invoice_id": self.settled_in.id, "invoice_number": self.settled_in.invoice_number,
                                "invoice_date": self.settled_in.invoice_date} if self.settled_in is not None else None)}


def _valid_final(invoice: Invoice) -> bool:
    return invoice.invoice_type == "schluss" and invoice.status in VALID_STATUSES


def settling_finals(db: Session, invoice_ids: Iterable[int]) -> dict[int, Invoice]:
    """Je abgezogener Rechnung die gültige Endrechnung, die sie abzieht (nach ihrem Storno keine mehr) -- in einer Abfrage."""
    ids = sorted(set(invoice_ids))
    if not ids:
        return {}
    rows = db.execute(
        select(InvoiceDeduction.deducted_invoice_id, Invoice)
        .join(Invoice, Invoice.id == InvoiceDeduction.invoice_id)
        .where(InvoiceDeduction.deducted_invoice_id.in_(ids), Invoice.invoice_type == "schluss",
               Invoice.status.in_(VALID_STATUSES))
    ).all()
    return {deducted_id: final for deducted_id, final in rows}


def _deductions_of(db: Session, finals: list[Invoice]) -> dict[int, list[Invoice]]:
    ids = [f.id for f in finals]
    if not ids:
        return {}
    result: dict[int, list[Invoice]] = {i: [] for i in ids}
    rows = db.execute(
        select(InvoiceDeduction.invoice_id, Invoice)
        .join(Invoice, Invoice.id == InvoiceDeduction.deducted_invoice_id)
        .where(InvoiceDeduction.invoice_id.in_(ids))
        .order_by(InvoiceDeduction.invoice_id, InvoiceDeduction.sort_order, InvoiceDeduction.id)
    ).all()
    for final_id, deducted in rows:
        result[final_id].append(deducted)
    return result


def principal_invoice_ids(db: Session, invoice: Invoice) -> list[int]:
    """Rechnungen, deren Buchungen den angemahnten Betrag dieser Rechnung ändern: sie selbst, an einer gültigen Endrechnung dazu
    ihre abgezogenen (für die Abschnitte der Verzugszinsen, app/default_interest.py)."""
    if not _valid_final(invoice):
        return [invoice.id]
    return [invoice.id] + [d.id for d in _deductions_of(db, [invoice]).get(invoice.id, [])]


def dunning_states(db: Session, invoices: Iterable[Invoice], *, on: date | None = None) -> dict[int, DunningState]:
    """Was zu jeder Rechnung gemahnt werden kann (siehe Moduldocstring), für viele Rechnungen in wenigen Abfragen. on: der Stand an
    diesem Tag (nur Zahlungen mit Eingangsdatum bis dahin, app/payments.py::allocation_sums()), sonst heute."""
    from .payments import _state, allocation_sums, payable, payable_gross  # lokal: app/payments.py importiert app/invoices.py

    invoices = list(invoices)
    settled = settling_finals(db, [i.id for i in invoices if i.invoice_type != "schluss"])
    finals = [i for i in invoices if _valid_final(i)]
    deductions = _deductions_of(db, finals)
    involved = {i.id: i for i in invoices}
    for rows in deductions.values():
        involved.update({d.id: d for d in rows})
    payable_ids = [i.id for i in involved.values() if payable(i)]
    sums = allocation_sums(db, payable_ids + [f.id for f in finals if f.id not in payable_ids], received_until=on)
    states = {i: _state(involved[i], sums[i]) for i in payable_ids}
    result = {}
    for inv in invoices:
        own = states.get(inv.id)
        final = settled.get(inv.id)
        # Am Stand eines Tages vor der Endrechnung (nachgetragene Zustellung) war die Rechnung noch nicht abgezogen.
        if final is not None and (on is None or on >= final.invoice_date):
            result[inv.id] = DunningState(invoice=inv, own=own, dunnable=ZERO, settled_in=final)
            continue
        rows = deductions.get(inv.id) or []
        if not rows:
            own_dunnable = own.dunnable if own is not None else ZERO
            result[inv.id] = DunningState(invoice=inv, own=own, dunnable=own_dunnable, own_part=own_dunnable)
            continue
        parts = tuple(DeductedOpen(d, states[d.id].open, states[d.id].retained_open)
                      for d in rows if d.id in states and states[d.id].open > 0)
        # Seit 1.8.90: eine Endrechnung unter 0 € trägt ihre Überzahlung (negativ) zuzüglich der Erstattungen bei.
        own_part = own.dunnable if own is not None else min(payable_gross(inv), ZERO) + sums[inv.id].refunded
        total = own_part + sum((p.open for p in parts), ZERO)
        result[inv.id] = DunningState(invoice=inv, own=own, dunnable=max(total, ZERO), deducted=parts, is_final=True,
                                      own_part=own_part, credit=max(-total, ZERO), refunded=sums[inv.id].refunded)
    return result


def dunning_state(db: Session, invoice: Invoice, *, on: date | None = None) -> DunningState:
    return dunning_states(db, [invoice], on=on)[invoice.id]


def settled_text(invoice: Invoice, final: Invoice) -> str:
    number = invoice.invoice_number or "(Entwurf)"
    return (f"Die Rechnung {number} ist in der Schlussrechnung {final.invoice_number} abgezogen – gemahnt wird nur noch die "
            "Schlussrechnung (über den Zahlbetrag).")


def nothing_to_dun_reason(db: Session, invoice: Invoice, state: DunningState) -> str | None:
    """Warum zu dieser Rechnung nichts zu mahnen ist (seit 1.8.89 mit der Endrechnung), sonst None: Stornorechnung, in einer
    Endrechnung abgezogen, Zahlbetrag beglichen, bezahlt, nur Einbehalt offen. Eine Rechnung, die nie offen ist, nennt
    app/payments.py::not_payable_reason()."""
    from .payments import dunning_block_reason, not_payable_reason  # lokal: Zirkel-Import

    number = invoice.invoice_number or "(Entwurf)"
    if invoice.invoice_type == "storno":
        return dunning_block_reason(db, invoice, state.own)
    if state.settled_in is not None:
        return settled_text(invoice, state.settled_in)
    if state.dunnable > 0:
        return None
    if state.is_final:
        if state.credit > 0:  # seit 1.8.90
            return (f"Die Schlussrechnung {number} weist eine Überzahlung aus -- Guthaben des Kunden {_money(state.credit)}, nichts "
                    "zu mahnen.")
        if state.own is not None and state.own.retained_open > 0:
            return (f"Vom Zahlbetrag der Schlussrechnung {number} ist nur noch ihr Einbehalt offen "
                    f"({_money(state.own.retained_open)}) -- ein Einbehalt wird nicht gemahnt.")
        return f"Der Zahlbetrag der Schlussrechnung {number} ist beglichen -- nichts zu mahnen."
    if state.own is None:
        return not_payable_reason(invoice) or f"Die Rechnung {number} hat keinen mahnfähigen Betrag."
    return dunning_block_reason(db, invoice, state.own) or f"Die Rechnung {number} hat keinen mahnfähigen Betrag."


OVERVIEW_LABELS = {"zahlbetrag_offen": "Zahlbetrag offen", "guthaben": "Guthaben", "ausgeglichen": "ausgeglichen"}


def overview(state, dunning: DunningState | None) -> dict | None:
    """Wie eine Rechnung in Finanzen, Dashboard und den Rechnungslisten zählt (seit 1.8.91, Nacharbeit R4c Punkt 1): nach der
    gültigen Endrechnung je Auftrag nur noch ihr Zahlbetrag -- positiv als offen (davon Einbehalt), negativ als Guthaben. Eine darin
    abgezogene Rechnung mit offenem Betrag zählt nicht mehr einzeln ("enthalten in Schlussrechnung …"); bezahlt bleibt bezahlt.
    Sonst der Zahlstand der Rechnung (app/payments.py). state: PaymentState der Rechnung, None wenn sie nie offen ist; None auch
    zurück, wenn sie nicht zählt (Entwurf, Storno, storniert). Seit 1.8.94 "refunded": an der Endrechnung schon erstattet
    (Zahlungsausgänge) -- Finanzen zieht es von "Bezahlt (gesamt)" ab."""
    from .payments import STATE_LABELS  # lokal wie in dunning_states()

    refunded = dunning.refunded if dunning is not None else ZERO

    def row(key, label, *, open_=ZERO, retained=ZERO, credit=ZERO, settled_in=None):
        return {"state": key, "state_label": label, "open": open_, "retained": retained, "credit": credit,
                "refunded": refunded,
                "settled_in": ({"invoice_id": settled_in.id, "invoice_number": settled_in.invoice_number}
                               if settled_in is not None else None)}

    if dunning is not None and dunning.settled_in is not None and state is not None and state.open > 0:
        final = dunning.settled_in
        return row("enthalten", f"enthalten in Schlussrechnung {final.invoice_number}", settled_in=final)
    if dunning is not None and dunning.is_final:
        own = dunning.own
        total = (own.open if own is not None else dunning.own_part) + dunning.deducted_open
        if total < 0:
            return row("guthaben", OVERVIEW_LABELS["guthaben"], credit=-total)
        retained = (own.retained_open if own is not None else ZERO) + sum((d.retained for d in dunning.deducted), ZERO)
        if total == 0:
            key = own.state if own is not None else "ausgeglichen"
        elif own is not None and not dunning.deducted:
            key = own.state
        else:
            key = "zahlbetrag_offen"
        return row(key, STATE_LABELS.get(key) or OVERVIEW_LABELS[key], open_=total, retained=retained)
    if state is None:
        return None
    return row(state.state, STATE_LABELS[state.state], open_=state.open, retained=state.retained_open)


def deducted_hint(state: DunningState) -> str | None:
    """Hinweis an einer abgezogenen Rechnung (Rechnungsseite): nicht mehr einzeln gemahnt, der Einbehalt mit der Endrechnung fällig."""
    if state.settled_in is None:
        return None
    text = (f"In der Schlussrechnung {state.settled_in.invoice_number} vom {_de(state.settled_in.invoice_date)} abgezogen – diese "
            "Rechnung wird nicht mehr einzeln gemahnt; was hier offen ist, gehört zum Zahlbetrag der Schlussrechnung.")
    if state.own is not None and state.own.retained_open > 0:
        text += f" Der Einbehalt ({_money(state.own.retained_open)}) ist mit der Schlussrechnung fällig."
    return text
