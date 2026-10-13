"""Zahlungseingänge (seit 1.8.78, Zahlungsstufe Z1, docs/archiv/zahlungen.md).

Eine Zahlung (Payment) ist ein Geldeingang eines Kunden mit Eingangsdatum, Betrag und Notiz. Zugeordnet wird sie auf eine oder
mehrere festgeschriebene Rechnungen desselben Kunden (PaymentAllocation, Art "zahlung"); mit ihr gebucht werden die Abzüge je
Rechnung, Skonto und Einbehalt. Was nicht zugeordnet ist, bleibt als Rest am Kunden sichtbar und lässt sich später zuordnen
(allocate_rest()).

Beträge je Rechnung (payment_state()), nie gespeichert:
  offen     = Brutto − Zahlungen − Skonto
  mahnfähig = offen − Einbehalt; der Einbehalt deckt höchstens den offenen Betrag ("Einbehalt offen" = der kleinere von beiden),
              so ist ein später gezahlter Einbehalt erledigt, ohne dass etwas zurückgenommen wird (Festlegung 1.8.78 Nr. 3).
Zustand nur abgeleitet: offen, teilweise bezahlt, Einbehalt offen, bezahlt. Ein Entwurf, eine Stornorechnung, eine stornierte
Rechnung und eine Rechnung über 0 € oder weniger haben keinen -- sie sind nie offen und nicht bebuchbar (payable()).
Brutto heißt hier: auf den Cent nach der Rundungsregel der Rechnung (payable_gross(); Altbestand vor 1.8.11 rechnet ungerundet).

Buchen: der Vorschlag (proposal()) geht zuerst auf die älteren offenen Rechnungen desselben Auftrags, dann auf die gewählte;
weitere Rechnungen nur von Hand. Skonto nur als Vorschlag, wenn der Eingang in der Frist liegt und der Betrag genau passt;
Einbehalt nie automatisch. Gebucht wird nur, was das Büro bestätigt (book_payment(), allocate_rest()) -- ohne Überbuchung einer
Rechnung oder der Zahlung, nur auf Rechnungen desselben Kunden.

Unveränderlich (ORM-Sperre in app/models.py): Korrektur nur als Gegenbuchung mit Begründung (reverse_allocation(),
reverse_payment()), nichts wird gelöscht. Buchen und Korrigieren laufen unter der Sperre der betroffenen Auftragszeilen in fester
Reihenfolge: erst die Aufträge aufsteigend nach ID (app/invoices.py::lock_order_invoices(), dieselbe Sperre wie Festschreiben,
Storno und Mahnung), dann die Zahlungen aufsteigend (lock_for_booking()) -- zwei Buchungen aus dem Rest derselben Zahlung auf
Rechnungen verschiedener Aufträge warten so aufeinander.

Seit 1.8.81 (Z2b Punkt 8): Zahlungen auch auf Nebenforderungen (Mahngebühr, Pauschale, Verzugszinsen; app/dunning_charges.py) --
Zuordnung Art "nebenforderung" mit der Nebenforderung (charge_id), an der Rechnung dieser Nebenforderung, unter derselben Sperre.
Der Vorschlag verteilt nach § 367 Abs. 1 BGB: je Rechnung erst die Kosten (Gebühr, Pauschale), dann die Zinsen, dann die Rechnung;
über mehrere Rechnungen weiter die älteste zuerst. Gebucht wird, was das Büro bestätigt -- auch abweichend (§ 366 Abs. 1 BGB:
eine Tilgungsbestimmung des Kunden geht vor). Eine Zahlung auf eine Nebenforderung mindert den Zahlstand der Rechnung nicht.

Seit 1.8.90 (R4c Punkt 6): Erstattung als Zahlungsausgang (book_refund()). Lautet eine gültige Endrechnung unter 0 € und übersteigt die
Überzahlung, was aus den abgezogenen Rechnungen noch offen ist, steht ein Guthaben am Kunden (app/final_dunning.py, DunningState.credit,
customer_credits()). Die Erstattung ist eine Zahlung mit negativem Betrag (Geld geht hinaus) und einer Zuordnung Art "erstattung" an
der Endrechnung, ebenfalls negativ -- höchstens das Guthaben, unter der Sperre der Auftragszeile; zurückgenommen nur als Ganzes
(reverse_payment()).

Seit 1.8.93 (Nacharbeit R4c Punkt 3): das Guthaben des Kunden sind die nicht zugeordneten Reste seiner Zahlungen und die Guthaben aus
Endrechnungen zusammen (customer_balance(), aufgeschlüsselt). Ein Zahlungsausgang kann beides erstatten (book_customer_refund()): aus
einem Rest über PaymentRefundSource (der Rest der Zahlung sinkt, der Zahlungsausgang ist damit zugeordnet), aus einem Guthaben wie
book_refund(). Sperren wie beim Buchen: erst die Aufträge der Endrechnungen, dann die Zahlungen, aus deren Rest erstattet wird.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from .berlin_time import berlin_today
from .invoices import (  # invoice_customer_id: seit 1.8.79 dort (der festgehaltene Kunde), hier weiter importierbar
    EDITABLE_STATUS, compute_invoice_totals, invoice_customer_id, invoice_rounding, lock_order_invoices, skonto_offer,
)
from .models import Customer, Invoice, InvoiceCharge, Payment, PaymentAllocation, PaymentRefundSource, Reminder
from .rounding import CENT, round_money
from .zugehoerigkeit import IdNichtGefunden

ORIGINS = ("erfasst", "uebernommen")
KINDS = ("zahlung", "skonto", "einbehalt", "nebenforderung", "erstattung")  # erstattung seit 1.8.90
KIND_LABELS = {"zahlung": "Zahlung", "skonto": "Skonto", "einbehalt": "Einbehalt", "nebenforderung": "Zahlung auf Nebenforderung",
               "erstattung": "Erstattung (Zahlungsausgang)"}
# Teile des Betrags der Zahlung (Skonto und Einbehalt sind Abzüge); eine Erstattung ist der (negative) Betrag eines Zahlungsausgangs.
MONEY_KINDS = ("zahlung", "nebenforderung", "erstattung")
STATES = ("offen", "teilweise_bezahlt", "einbehalt_offen", "bezahlt")
STATE_LABELS = {"offen": "offen", "teilweise_bezahlt": "teilweise bezahlt", "einbehalt_offen": "Einbehalt offen",
                "bezahlt": "bezahlt"}
ZERO = Decimal("0.00")


class PaymentRejected(ValueError):
    """Eine Buchung oder Gegenbuchung ist am Stand nicht möglich (Überbuchung, Rechnung eines anderen Kunden, Stornorechnung,
    schon gegengebucht …) -- Router: 409 mit dem Text."""


# ---------------------------------------------------------------------------
# Beträge je Rechnung
# ---------------------------------------------------------------------------

def _de(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def payable_gross(invoice: Invoice) -> Decimal:
    """Brutto auf den Cent nach der Rundungsregel der Rechnung -- der Betrag, gegen den gebucht wird (wie die Mahnung,
    app/reminders.py::reminder_total())."""
    return compute_invoice_totals(invoice)["gross_total"].quantize(CENT, rounding=invoice_rounding(invoice))


def not_payable_reason(invoice: Invoice) -> str | None:
    """Warum auf diese Rechnung nichts gebucht werden kann (sie ist nie offen), sonst None."""
    number = invoice.invoice_number or "(Entwurf)"
    if invoice.invoice_type == "storno":
        return f"{number} ist eine Stornorechnung -- sie ist nie offen und nicht bebuchbar."
    if invoice.status == EDITABLE_STATUS:
        return "Ein Rechnungsentwurf ist nicht bebuchbar -- erst nach dem Finalisieren."
    if invoice.status == "storniert":
        return f"Die Rechnung {number} ist storniert und nicht bebuchbar."
    if invoice.status != "versendet":
        return f"Die Rechnung {number} ist nicht bebuchbar (Status {invoice.status})."
    gross = payable_gross(invoice)
    if gross < 0 and invoice.invoice_type == "schluss":  # seit 1.8.90 (R4c Punkt 6)
        return (f"Die Schlussrechnung {number} weist eine Überzahlung aus ({money(-gross)}) -- auf sie wird nichts gebucht; ein "
                "Guthaben des Kunden wird als Erstattung (Zahlungsausgang) gebucht.")
    if gross <= 0:
        return f"Die Rechnung {number} lautet über 0 € oder weniger und ist nicht bebuchbar."
    return None


def payable(invoice: Invoice) -> bool:
    return not_payable_reason(invoice) is None


@dataclass(frozen=True)
class Sums:
    """Noch geltende Buchungen an einer Rechnung (Gegenbuchungen abgezogen)."""
    paid: Decimal = ZERO
    skonto: Decimal = ZERO
    retained: Decimal = ZERO
    last_received_on: date | None = None  # Eingangsdatum der jüngsten noch geltenden Zahlung
    charges_paid: Decimal = ZERO  # seit 1.8.81: Zahlungen auf Nebenforderungen der Rechnung (nicht im Zahlstand)
    refunded: Decimal = ZERO  # seit 1.8.90: erstattet (Zahlungsausgang an einer Endrechnung mit Überzahlung), positiv

    @property
    def any(self) -> bool:
        return bool(self.paid or self.skonto or self.retained or self.charges_paid or self.refunded)


def allocation_sums(db: Session, invoice_ids: Iterable[int], *, received_until: date | None = None) -> dict[int, Sums]:
    """Summen je Rechnung in zwei Abfragen (Finanzen, Mahnwesen: viele Rechnungen auf einmal). received_until (seit 1.8.79):
    nur Buchungen aus Zahlungen mit Eingangsdatum bis zu diesem Tag -- der Stand an einem Tag (payment_state_on()). Eine
    Gegenbuchung hängt an derselben Zahlung wie ihre Zuordnung, zählt also mit ihr oder gar nicht: zurückgenommen gilt nie."""
    ids = sorted(set(invoice_ids))
    if not ids:
        return {}
    totals: dict[int, dict[str, Decimal]] = {}
    stmt = (select(PaymentAllocation.invoice_id, PaymentAllocation.kind, func.sum(PaymentAllocation.amount))
            .where(PaymentAllocation.invoice_id.in_(ids)).group_by(PaymentAllocation.invoice_id, PaymentAllocation.kind))
    if received_until is not None:
        stmt = stmt.join(Payment, Payment.id == PaymentAllocation.payment_id).where(Payment.received_on <= received_until)
    for invoice_id, kind, amount in db.execute(stmt):
        totals.setdefault(invoice_id, {})[kind] = round_money(amount)
    reversal = aliased(PaymentAllocation)
    last_stmt = (
        select(PaymentAllocation.invoice_id, func.max(Payment.received_on))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .outerjoin(reversal, reversal.reverses_allocation_id == PaymentAllocation.id)
        .where(PaymentAllocation.invoice_id.in_(ids), PaymentAllocation.kind == "zahlung",
               PaymentAllocation.reverses_allocation_id.is_(None), reversal.id.is_(None))
        .group_by(PaymentAllocation.invoice_id)
    )
    if received_until is not None:
        last_stmt = last_stmt.where(Payment.received_on <= received_until)
    last = dict(db.execute(last_stmt).all())
    return {i: Sums(paid=totals.get(i, {}).get("zahlung", ZERO), skonto=totals.get(i, {}).get("skonto", ZERO),
                    retained=totals.get(i, {}).get("einbehalt", ZERO), last_received_on=last.get(i),
                    charges_paid=totals.get(i, {}).get("nebenforderung", ZERO),
                    refunded=-totals.get(i, {}).get("erstattung", ZERO)) for i in ids}


@dataclass(frozen=True)
class PaymentState:
    gross: Decimal
    paid: Decimal
    skonto: Decimal
    retained: Decimal
    open: Decimal
    retained_open: Decimal
    dunnable: Decimal
    state: str
    paid_on: date | None

    def as_dict(self) -> dict:
        return {"gross": self.gross, "paid": self.paid, "skonto": self.skonto, "retained": self.retained,
                "open": self.open, "retained_open": self.retained_open, "dunnable": self.dunnable, "state": self.state,
                "state_label": STATE_LABELS[self.state], "paid_on": self.paid_on}


def _state(invoice: Invoice, sums: Sums) -> PaymentState | None:
    if not payable(invoice):
        return None
    gross = payable_gross(invoice)
    open_ = max(gross - sums.paid - sums.skonto, ZERO)
    retained_open = min(max(sums.retained, ZERO), open_)
    dunnable = open_ - retained_open
    if open_ == 0:
        state = "bezahlt"
    elif dunnable == 0:
        state = "einbehalt_offen"
    elif sums.paid > 0 or sums.skonto > 0:
        state = "teilweise_bezahlt"
    else:
        state = "offen"
    return PaymentState(gross=gross, paid=sums.paid, skonto=sums.skonto, retained=sums.retained, open=open_,
                        retained_open=retained_open, dunnable=dunnable, state=state,
                        paid_on=sums.last_received_on if state == "bezahlt" else None)


def payment_state(db: Session, invoice: Invoice) -> PaymentState | None:
    """Zahlstand der Rechnung, frisch aus der Datenbank; None, wenn sie nie offen ist (siehe not_payable_reason())."""
    if not payable(invoice):
        return None
    return _state(invoice, allocation_sums(db, [invoice.id])[invoice.id])


def payment_state_on(db: Session, invoice: Invoice, day: date) -> PaymentState | None:
    """Zahlstand der Rechnung, wie er an diesem Tag war (seit 1.8.79, Zustellung einer Mahnung nachtragen): nur Zahlungen mit
    Eingangsdatum bis dahin; eine zurückgenommene Buchung gilt nie."""
    if not payable(invoice):
        return None
    return _state(invoice, allocation_sums(db, [invoice.id], received_until=day)[invoice.id])


def invoice_payment_lines(db: Session, invoice: Invoice) -> list[tuple[date, Decimal]]:
    """Noch geltende Zahlungen an der Rechnung je Zahlungseingang (Eingangsdatum, Betrag), ältester zuerst -- für die
    Aufstellung der Mahnung (seit 1.8.79). Summe = Sums.paid."""
    reversal = aliased(PaymentAllocation)
    rows = db.execute(
        select(Payment.received_on, Payment.id, func.sum(PaymentAllocation.amount))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .outerjoin(reversal, reversal.reverses_allocation_id == PaymentAllocation.id)
        .where(PaymentAllocation.invoice_id == invoice.id, PaymentAllocation.kind == "zahlung",
               PaymentAllocation.reverses_allocation_id.is_(None), reversal.id.is_(None))
        .group_by(Payment.received_on, Payment.id).order_by(Payment.received_on, Payment.id)
    ).all()
    return [(received_on, round_money(amount)) for received_on, _, amount in rows if amount]


def payment_states(db: Session, invoices: Iterable[Invoice]) -> dict[int, PaymentState | None]:
    invoices = list(invoices)
    sums = allocation_sums(db, [i.id for i in invoices if payable(i)])
    return {i.id: (_state(i, sums[i.id]) if i.id in sums else None) for i in invoices}


def has_allocations(db: Session, invoice_id: int) -> bool:
    """Hängen an der Rechnung noch geltende Buchungen (Zahlung, Skonto oder Einbehalt)? -- Sperrgrund für das Storno."""
    return allocation_sums(db, [invoice_id])[invoice_id].any


def allocation_block_reason(db: Session, invoice: Invoice) -> str | None:
    """Warum die Rechnung (noch) nicht storniert werden kann: ihr sind Zahlungen zugeordnet (Vorgabe Z1 Nr. 5)."""
    sums = allocation_sums(db, [invoice.id])[invoice.id]
    if not sums.any:
        return None
    parts = [f"{KIND_LABELS[k]} {money(v)}" for k, v in (("zahlung", sums.paid), ("skonto", sums.skonto),
                                                         ("einbehalt", sums.retained),
                                                         ("nebenforderung", sums.charges_paid),
                                                         ("erstattung", sums.refunded)) if v]
    refund = (" Eine Erstattung wird als Ganzes zurückgenommen (Kundenakte, „Zahlung zurücknehmen“)." if sums.refunded
              else "")  # seit 1.8.90
    return (f"Der Rechnung sind Zahlungen zugeordnet ({', '.join(parts)}). Erst die Zuordnungen lösen (Gegenbuchung mit "
            f"Begründung) -- die Zahlung bleibt dann beim Kunden, nicht zugeordnet.{refund}")


_UNSET = object()


def dunning_block_reason(db: Session, invoice: Invoice, state=_UNSET) -> str | None:
    """Warum zu dieser Rechnung keine Mahnung entsteht oder hinausgeht, weil nichts mahnfähig ist (app/reminders.py).
    state: der schon geladene Zahlstand (seit 1.8.79, Listen), sonst frisch."""
    number = invoice.invoice_number or "(Entwurf)"
    if invoice.invoice_type == "storno":
        return f"{number} ist eine Stornorechnung -- sie ist nie offen, dazu geht keine Mahnung hinaus."
    if state is _UNSET:
        state = payment_state(db, invoice)
    if state is None or state.dunnable > 0:
        return None
    if state.state == "bezahlt":
        paid = f" (am {_de(state.paid_on)})" if state.paid_on else ""
        return f"Die Rechnung {number} ist bezahlt{paid} -- dazu geht keine Mahnung mehr hinaus."
    return (f"Von der Rechnung {number} ist nur noch der Einbehalt offen ({money(state.retained_open)}) -- ein Einbehalt "
            "wird nicht gemahnt.")


# ---------------------------------------------------------------------------
# Vorschlag
# ---------------------------------------------------------------------------

def _skonto_proposal(invoice: Invoice, state: PaymentState, received_on: date) -> dict | None:
    """Skonto laut Rechnung, wenn der Eingang in der Frist liegt und noch keins gebucht ist -- sonst None."""
    offer = skonto_offer(invoice)
    if offer is None:
        return None
    until, amount = offer
    return {"until": until, "amount": amount,
            "in_period": received_on <= until and state.skonto == 0 and 0 < amount < state.open}


def proposal(db: Session, invoice: Invoice, *, amount: Decimal, received_on: date) -> dict:
    """Vorschlag für einen Zahlungseingang an dieser Rechnung (Vorgabe Z1 Nr. 2): zuerst die älteren offenen Rechnungen
    desselben Auftrags (nach Rechnungsdatum, ältester zuerst), dann diese. Reicht der Betrag für alle, werden alle voll
    zugeordnet und der Rest bleibt am Kunden. Skonto nur, wo der Eingang in der Frist liegt und der Betrag genau passt: entweder
    für alle mit Skonto zusammen, oder an der Rechnung, an der der Betrag endet. Einbehalt nie. Nur ein Vorschlag -- gebucht wird
    erst mit book_payment()."""
    from .dunning_charges import charge_lines, open_charge_rows  # lokal: app/dunning_charges.py importiert app/invoices.py

    reason = not_payable_reason(invoice)
    if reason:
        raise PaymentRejected(reason)
    amount = _cents(amount, "Der Betrag", positive=True)
    others = [i for i in invoice.order.invoices if i.id != invoice.id and payable(i)
              and (i.invoice_date, i.id) < (invoice.invoice_date, invoice.id)]
    candidates = sorted(others, key=lambda i: (i.invoice_date, i.id)) + [invoice]
    states = payment_states(db, candidates)
    rows = []
    for inv in candidates:
        state = states[inv.id]
        # Seit 1.8.81: offene Nebenforderungen der Rechnung, in der Reihenfolge nach § 367 Abs. 1 BGB (Kosten, dann Zinsen).
        charges = open_charge_rows(db, inv) if state is not None else []
        if inv.id != invoice.id and (state is None or (state.open == 0 and not charges)):
            continue
        rows.append({"invoice": inv, "state": state, "skonto": _skonto_proposal(inv, state, received_on),
                     "charges": charges})

    def eligible(row) -> Decimal | None:
        return row["skonto"]["amount"] if row["skonto"] and row["skonto"]["in_period"] else None

    def charges_open(row) -> Decimal:
        return sum((rest for _, rest in row["charges"]), ZERO)

    alloc = {r["invoice"].id: [ZERO, ZERO] for r in rows}  # [zahlung, skonto]
    charge_alloc: dict[int, Decimal] = {}
    total_open = sum((charges_open(r) + r["state"].open for r in rows), ZERO)
    with_skonto = sum((charges_open(r) + r["state"].open - (eligible(r) or ZERO) for r in rows), ZERO)
    if amount >= total_open:
        for r in rows:
            charge_alloc.update({c.id: rest for c, rest in r["charges"]})
            alloc[r["invoice"].id][0] = r["state"].open
    elif any(eligible(r) for r in rows) and amount == with_skonto:
        for r in rows:
            s = eligible(r) or ZERO
            charge_alloc.update({c.id: rest for c, rest in r["charges"]})
            alloc[r["invoice"].id] = [r["state"].open - s, s]
    else:
        # § 367 Abs. 1 BGB je Rechnung: Kosten, Zinsen, dann die Rechnung -- die älteste Rechnung zuerst.
        remaining = amount
        for r in rows:
            for c, rest in r["charges"]:
                if remaining <= 0:
                    break
                charge_alloc[c.id] = min(rest, remaining)
                remaining -= charge_alloc[c.id]
            if remaining <= 0:
                break
            open_, s = r["state"].open, eligible(r)
            if open_ <= 0:
                continue
            if remaining >= open_:
                alloc[r["invoice"].id][0] = open_
            elif s is not None and remaining == open_ - s:
                alloc[r["invoice"].id] = [remaining, s]
            else:
                alloc[r["invoice"].id][0] = remaining
            remaining -= alloc[r["invoice"].id][0]
    lines = []
    for r in rows:
        inv, state, sk = r["invoice"], r["state"], r["skonto"]
        zahlung, skonto = alloc[inv.id]
        labels = {line["id"]: line for line in charge_lines(db, [c for c, _ in r["charges"]])}
        lines.append({
            "invoice_id": inv.id, "invoice_number": inv.invoice_number, "invoice_type": inv.invoice_type,
            "invoice_date": inv.invoice_date, "order_id": inv.order_id, "is_selected": inv.id == invoice.id,
            "open": state.open, "zahlung": zahlung, "skonto": skonto, "einbehalt": ZERO,
            "skonto_offer": ({"until": sk["until"], "amount": sk["amount"], "in_period": sk["in_period"]} if sk else None),
            "charges": [{"charge_id": c.id, "kind": c.kind, "label": labels[c.id]["label"], "open": rest,
                         "amount": charge_alloc.get(c.id, ZERO)} for c, rest in r["charges"]],
        })
    allocated = sum((line["zahlung"] + sum((c["amount"] for c in line["charges"]), ZERO) for line in lines), ZERO)
    return {"amount": amount, "received_on": received_on, "lines": lines, "rest": amount - allocated}


# ---------------------------------------------------------------------------
# Buchen
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChargeLine:
    """Seit 1.8.81: was von der Zahlung auf eine Nebenforderung der Rechnung der Zeile geht."""
    charge_id: int
    amount: Decimal


@dataclass(frozen=True)
class Line:
    """Eine bestätigte Zeile: was von der Zahlung auf die Rechnung geht und welche Abzüge mit ihr gebucht werden; seit 1.8.81
    dazu, was auf ihre Nebenforderungen geht (charges)."""
    invoice_id: int
    zahlung: Decimal = ZERO
    skonto: Decimal = ZERO
    einbehalt: Decimal = ZERO
    charges: tuple[ChargeLine, ...] = ()

    @property
    def money_total(self) -> Decimal:
        """Was von der Zahlung auf diese Zeile geht (Rechnung und Nebenforderungen, ohne Abzüge)."""
        return self.zahlung + sum((c.amount for c in self.charges), ZERO)


def _cents(value: Decimal, label: str, *, positive: bool = False) -> Decimal:
    value = Decimal(value)
    if value != round_money(value):
        raise ValueError(f"{label}: höchstens zwei Nachkommastellen.")
    if positive and value <= 0:
        raise ValueError(f"{label} muss größer als 0 sein.")
    if value < 0:
        raise ValueError(f"{label} darf nicht negativ sein.")
    return round_money(value)


def _check_lines(lines: list[Line]) -> list[Line]:
    seen, seen_charges = set(), set()
    checked = []
    for line in lines:
        if line.invoice_id in seen:
            raise ValueError("Jede Rechnung höchstens einmal je Buchung.")
        seen.add(line.invoice_id)
        z, s, e = (_cents(line.zahlung, "Zahlung"), _cents(line.skonto, "Skonto"), _cents(line.einbehalt, "Einbehalt"))
        charges = []
        for c in line.charges:
            if c.charge_id in seen_charges:
                raise ValueError("Jede Nebenforderung höchstens einmal je Buchung.")
            seen_charges.add(c.charge_id)
            amount = _cents(c.amount, "Zahlung auf Nebenforderung")
            if amount:
                charges.append(ChargeLine(c.charge_id, amount))
        if not (z or s or e or charges):
            raise ValueError("Eine Zeile ohne Betrag -- bitte weglassen.")
        checked.append(Line(line.invoice_id, z, s, e, tuple(charges)))
    return checked


def _reason(text: str | None) -> str:
    text = (text or "").strip()
    if not text:
        raise ValueError("Bitte eine Begründung angeben.")
    return text


def lock_for_booking(db: Session, order_ids: Iterable[int], payment_ids: Iterable[int] = ()) -> None:
    """Feste Reihenfolge (Vorgabe Z1 Nr. 4): erst die Auftragszeilen aufsteigend nach ID, dann die Zahlungen aufsteigend -- so
    warten zwei Buchungen aufeinander, statt sich gegenseitig zu blockieren. Unter PostgreSQL; SQLite serialisiert ohnehin."""
    for order_id in sorted(set(order_ids)):
        lock_order_invoices(db, order_id)
    ids = sorted(set(payment_ids))
    if ids:
        db.execute(select(Payment.id).where(Payment.id.in_(ids)).order_by(Payment.id).with_for_update())


def _reversed_payment_ids(db: Session, payment_ids: Iterable[int]) -> set[int]:
    ids = list(payment_ids)
    if not ids:
        return set()
    return set(db.scalars(select(Payment.reverses_payment_id).where(Payment.reverses_payment_id.in_(ids))))


def refunded_from_rest(db: Session, payment_ids: Iterable[int]) -> dict[int, Decimal]:
    """Je Zahlung, was aus ihrem nicht zugeordneten Rest erstattet ist (seit 1.8.93) -- über Zahlungsausgänge, die nicht
    zurückgenommen sind."""
    ids = sorted(set(payment_ids))
    if not ids:
        return {}
    reversed_ids = select(Payment.reverses_payment_id).where(Payment.reverses_payment_id.is_not(None))
    rows = db.execute(
        select(PaymentRefundSource.source_payment_id, func.sum(PaymentRefundSource.amount))
        .where(PaymentRefundSource.source_payment_id.in_(ids), PaymentRefundSource.refund_payment_id.not_in(reversed_ids))
        .group_by(PaymentRefundSource.source_payment_id)
    ).all()
    return {payment_id: round_money(total) for payment_id, total in rows}


def payment_rest(db: Session, payment: Payment) -> Decimal:
    """Noch nicht zugeordneter Betrag der Zahlung (0, wenn sie zurückgenommen ist). Seit 1.8.93 abzüglich dessen, was aus dem Rest
    erstattet ist; an einem Zahlungsausgang zählt, was er aus Resten erstattet, als zugeordnet."""
    if payment.reverses_payment_id is not None or payment.id in _reversed_payment_ids(db, [payment.id]):
        return ZERO
    allocated = db.scalar(select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
        PaymentAllocation.payment_id == payment.id, PaymentAllocation.kind.in_(MONEY_KINDS)))
    from_rest = refunded_from_rest(db, [payment.id]).get(payment.id, ZERO)
    as_refund = db.scalar(select(func.coalesce(func.sum(PaymentRefundSource.amount), 0)).where(
        PaymentRefundSource.refund_payment_id == payment.id))
    return round_money(Decimal(payment.amount) - Decimal(allocated or 0) - from_rest + Decimal(as_refund or 0))


def _load_invoices(db: Session, lines: list[Line]) -> dict[int, Invoice]:
    invoices = {}
    for line in lines:
        invoice = db.get(Invoice, line.invoice_id)
        if invoice is None:
            raise IdNichtGefunden(f"Rechnung {line.invoice_id} nicht gefunden.")
        invoices[line.invoice_id] = invoice
    return invoices


def _apply(db: Session, payment: Payment, lines: list[Line], invoices: dict[int, Invoice], *, user_id, name) -> None:
    """Prüft unter der Sperre und schreibt die Zuordnungen. Wirft PaymentRejected -- der Aufrufer rollt zurück."""
    if payment.reverses_payment_id is not None or payment.id in _reversed_payment_ids(db, [payment.id]):
        raise PaymentRejected("Die Zahlung ist zurückgenommen -- daraus lässt sich nichts mehr zuordnen.")
    total = sum((line.money_total for line in lines), ZERO)
    rest = payment_rest(db, payment)
    if total > rest:
        raise PaymentRejected(f"Überbuchung der Zahlung: zugeordnet werden sollen {money(total)}, offen an der Zahlung sind "
                              f"{money(rest)}.")
    sums = allocation_sums(db, invoices)
    for line in lines:
        invoice = invoices[line.invoice_id]
        number = invoice.invoice_number or "(Entwurf)"
        if invoice_customer_id(invoice) != payment.customer_id:
            raise PaymentRejected(f"Die Rechnung {number} gehört zu einem anderen Kunden als die Zahlung.")
        reason = not_payable_reason(invoice)
        if reason:
            raise PaymentRejected(reason)
        state = _state(invoice, sums[invoice.id])
        if line.zahlung + line.skonto > state.open:
            raise PaymentRejected(
                f"Überbuchung der Rechnung {number}: offen sind {money(state.open)}, gebucht werden sollen "
                f"{money(line.zahlung + line.skonto)} (Zahlung {money(line.zahlung)}, Skonto {money(line.skonto)}).")
        open_after = state.open - line.zahlung - line.skonto
        if state.retained + line.einbehalt > open_after and line.einbehalt:
            raise PaymentRejected(
                f"Der Einbehalt an der Rechnung {number} wäre höher als der danach offene Betrag ({money(open_after)}).")
        _check_charge_lines(db, invoice, line)
    for line in lines:
        for kind, value in (("zahlung", line.zahlung), ("skonto", line.skonto), ("einbehalt", line.einbehalt)):
            if value:
                db.add(PaymentAllocation(payment_id=payment.id, invoice_id=line.invoice_id, kind=kind, amount=value,
                                         created_by_user_id=user_id, created_by_name=name))
        for c in line.charges:
            db.add(PaymentAllocation(payment_id=payment.id, invoice_id=line.invoice_id, kind="nebenforderung", amount=c.amount,
                                     charge_id=c.charge_id, created_by_user_id=user_id, created_by_name=name))


def _check_charge_lines(db: Session, invoice: Invoice, line: Line) -> None:
    """Seit 1.8.81: nur auf eine geltende Nebenforderung dieser Rechnung, höchstens ihren offenen Rest (unter der Sperre der
    Auftragszeile -- Nebenforderungen entstehen und werden gegengebucht unter derselben)."""
    from .dunning_charges import charge_label, charge_paid, charges_in_force  # lokal: Zirkel-Import

    if not line.charges:
        return
    number = invoice.invoice_number or "(Entwurf)"
    in_force = {c.id: c for c in charges_in_force(db, [invoice.id])[invoice.id]}
    paid = charge_paid(db, [c.charge_id for c in line.charges])
    for c in line.charges:
        charge = db.get(InvoiceCharge, c.charge_id)
        if charge is None:
            raise IdNichtGefunden(f"Nebenforderung {c.charge_id} nicht gefunden.")
        if charge.invoice_id != line.invoice_id:
            raise PaymentRejected(f"Die Nebenforderung {c.charge_id} gehört nicht zur Rechnung {number}.")
        if charge.id not in in_force:
            raise PaymentRejected(f"Die Nebenforderung {c.charge_id} ist gegengebucht bzw. eine Gegenbuchung -- darauf lässt "
                                  "sich nichts buchen.")
        rest = round_money(Decimal(charge.amount) - paid.get(charge.id, ZERO))
        if c.amount > rest:
            label = charge_label(charge, None, {})
            raise PaymentRejected(f"Überbuchung der Nebenforderung „{label}“ an der Rechnung {number}: offen sind {money(rest)}, "
                                  f"gebucht werden sollen {money(c.amount)}.")


def book_payment(db: Session, *, customer_id: int, received_on: date, amount: Decimal, note: str | None,
                 lines: list[Line], user_id: int | None = None, user_name: str | None = None) -> Payment:
    """Zahlungseingang erfassen und, wie bestätigt, zuordnen (lines darf leer sein: alles bleibt Rest am Kunden)."""
    amount = _cents(amount, "Der Betrag", positive=True)
    if received_on > berlin_today():
        raise ValueError("Das Eingangsdatum liegt in der Zukunft.")
    lines = _check_lines(lines)
    if db.get(Customer, customer_id) is None:
        raise IdNichtGefunden("Kunde nicht gefunden.")
    invoices = _load_invoices(db, lines)
    name = (user_name or "System")[:160]
    lock_for_booking(db, [i.order_id for i in invoices.values()])
    try:
        payment = Payment(customer_id=customer_id, received_on=received_on, amount=amount,
                          note=(note or "").strip() or None, origin="erfasst", created_by_user_id=user_id, created_by_name=name)
        db.add(payment)
        db.flush()
        _apply(db, payment, lines, invoices, user_id=user_id, name=name)
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(payment)
    return payment


def allocate_rest(db: Session, payment: Payment, lines: list[Line], *, user_id: int | None = None,
                  user_name: str | None = None) -> Payment:
    """Rest einer vorhandenen Zahlung zuordnen (von Hand, z. B. nach einem Storno auf die neue Rechnung)."""
    lines = _check_lines(lines)
    if not lines:
        raise ValueError("Bitte mindestens eine Rechnung angeben.")
    invoices = _load_invoices(db, lines)
    name = (user_name or "System")[:160]
    lock_for_booking(db, [i.order_id for i in invoices.values()], [payment.id])
    try:
        _apply(db, payment, lines, invoices, user_id=user_id, name=name)
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(payment)
    return payment


# ---------------------------------------------------------------------------
# Erstattung (seit 1.8.90, R4c Punkt 6)
# ---------------------------------------------------------------------------

def book_refund(db: Session, invoice: Invoice, *, paid_on: date, amount: Decimal, note: str | None,
                user_id: int | None = None, user_name: str | None = None) -> Payment:
    """Erstattung eines Guthabens als Zahlungsausgang: eine Zahlung des Kunden über −amount mit einer Zuordnung Art "erstattung"
    (ebenfalls −amount) an der Endrechnung. Unter der Sperre der Auftragszeile geprüft: gültige Endrechnung mit Guthaben
    (app/final_dunning.py::DunningState.credit), höchstens das Guthaben, Ausgangsdatum nicht in der Zukunft. Seit 1.8.93 erstattet
    book_customer_refund() in der Kundenakte auch Reste von Zahlungen, mit denselben Prüfungen (_check_credit())."""
    amount = _cents(amount, "Der Betrag", positive=True)
    if paid_on > berlin_today():
        raise ValueError("Das Datum des Zahlungsausgangs liegt in der Zukunft.")
    name = (user_name or "System")[:160]
    lock_order_invoices(db, invoice.order_id)
    try:
        _check_credit(db, invoice, amount)
        payment = Payment(customer_id=invoice_customer_id(invoice), received_on=paid_on, amount=-amount,
                          note=(note or "").strip() or None, origin="erfasst", created_by_user_id=user_id, created_by_name=name)
        db.add(payment)
        db.flush()
        db.add(PaymentAllocation(payment_id=payment.id, invoice_id=invoice.id, kind="erstattung", amount=-amount,
                                 created_by_user_id=user_id, created_by_name=name))
        db.flush()
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(payment)
    return payment


def _check_credit(db: Session, invoice: Invoice, amount: Decimal) -> None:
    """Unter der Sperre der Auftragszeile: gültige Endrechnung mit Guthaben, höchstens das Guthaben (book_refund(), seit 1.8.93 auch
    book_customer_refund())."""
    from .final_dunning import dunning_state  # lokal: app/final_dunning.py importiert app/payments.py

    number = invoice.invoice_number or "(Entwurf)"
    state = dunning_state(db, invoice) if invoice.status == "versendet" else None
    if state is None or not state.is_final:
        raise PaymentRejected(f"Eine Erstattung gibt es nur zu einer festgeschriebenen Schlussrechnung mit Überzahlung -- "
                              f"{number} ist keine.")
    if state.credit <= 0:
        raise PaymentRejected(f"Aus der Schlussrechnung {number} steht kein Guthaben des Kunden offen.")
    if amount > state.credit:
        raise PaymentRejected(f"Überbuchung: das Guthaben aus der Schlussrechnung {number} beträgt {money(state.credit)}, "
                              f"erstattet werden sollen {money(amount)}.")


@dataclass(frozen=True)
class RefundLine:
    """Seit 1.8.93: ein Teil einer Erstattung -- aus dem Guthaben einer Endrechnung (invoice_id) oder aus dem nicht zugeordneten Rest
    einer Zahlung (payment_id), genau eins von beiden."""
    amount: Decimal
    invoice_id: int | None = None
    payment_id: int | None = None


def _check_refund_lines(lines: list[RefundLine]) -> list[RefundLine]:
    if not lines:
        raise ValueError("Bitte mindestens einen Betrag zum Erstatten angeben.")
    seen = set()
    checked = []
    for line in lines:
        if (line.invoice_id is None) == (line.payment_id is None):
            raise ValueError("Jede Zeile erstattet entweder aus einer Schlussrechnung oder aus einer Zahlung.")
        key = ("rechnung", line.invoice_id) if line.invoice_id is not None else ("zahlung", line.payment_id)
        if key in seen:
            raise ValueError("Jede Schlussrechnung und jede Zahlung höchstens einmal je Erstattung.")
        seen.add(key)
        checked.append(RefundLine(_cents(line.amount, "Der Betrag", positive=True), line.invoice_id, line.payment_id))
    return checked


def _check_rest_line(db: Session, customer_id: int, payment: Payment, amount: Decimal) -> None:
    """Unter der Sperre der Zahlung: ein Zahlungseingang desselben Kunden, nicht zurückgenommen, höchstens sein Rest."""
    if payment.customer_id != customer_id:
        raise PaymentRejected(f"Die Zahlung Nr. {payment.id} gehört zu einem anderen Kunden.")
    if payment.reverses_payment_id is not None or payment.id in _reversed_payment_ids(db, [payment.id]):
        raise PaymentRejected(f"Die Zahlung Nr. {payment.id} ist zurückgenommen -- daraus lässt sich nichts erstatten.")
    if Decimal(payment.amount) < 0:
        raise PaymentRejected(f"Nr. {payment.id} ist ein Zahlungsausgang -- erstattet wird nur aus dem Rest eines Zahlungseingangs.")
    rest = payment_rest(db, payment)
    if amount > rest:
        raise PaymentRejected(f"Überbuchung: an der Zahlung Nr. {payment.id} sind {money(rest)} nicht zugeordnet, erstattet werden "
                              f"sollen {money(amount)}.")


def book_customer_refund(db: Session, customer_id: int, *, paid_on: date, note: str | None, lines: list[RefundLine],
                         user_id: int | None = None, user_name: str | None = None) -> Payment:
    """Erstattung des Guthabens des Kunden als ein Zahlungsausgang (seit 1.8.93, Nacharbeit R4c Punkt 3): aus Guthaben von Endrechnungen
    (Zuordnung Art "erstattung" an der Endrechnung, wie book_refund()) und aus nicht zugeordneten Resten seiner Zahlungen
    (PaymentRefundSource) zugleich. Unter den Sperren in fester Reihenfolge (lock_for_booking()): die Aufträge der Endrechnungen, dann
    die Zahlungen, aus deren Rest erstattet wird -- je Zeile höchstens das Guthaben bzw. der Rest, nur Rechnungen und Zahlungen dieses
    Kunden, Datum nicht in der Zukunft. Zurückgenommen nur als Ganzes (reverse_payment())."""
    if paid_on > berlin_today():
        raise ValueError("Das Datum des Zahlungsausgangs liegt in der Zukunft.")
    lines = _check_refund_lines(lines)
    if db.get(Customer, customer_id) is None:
        raise IdNichtGefunden("Kunde nicht gefunden.")
    invoices: dict[int, Invoice] = {}
    payments: dict[int, Payment] = {}
    for line in lines:
        if line.invoice_id is not None:
            invoice = db.get(Invoice, line.invoice_id)
            if invoice is None:
                raise IdNichtGefunden(f"Rechnung {line.invoice_id} nicht gefunden.")
            invoices[invoice.id] = invoice
        else:
            payment = db.get(Payment, line.payment_id)
            if payment is None:
                raise IdNichtGefunden(f"Zahlung {line.payment_id} nicht gefunden.")
            payments[payment.id] = payment
    name = (user_name or "System")[:160]
    lock_for_booking(db, [i.order_id for i in invoices.values()], payments)
    try:
        for line in lines:
            if line.invoice_id is not None:
                invoice = invoices[line.invoice_id]
                if invoice_customer_id(invoice) != customer_id:
                    raise PaymentRejected(f"Die Rechnung {invoice.invoice_number or '(Entwurf)'} gehört zu einem anderen Kunden.")
                _check_credit(db, invoice, line.amount)
            else:
                _check_rest_line(db, customer_id, payments[line.payment_id], line.amount)
        total = sum((line.amount for line in lines), ZERO)
        refund = Payment(customer_id=customer_id, received_on=paid_on, amount=-total, note=(note or "").strip() or None,
                         origin="erfasst", created_by_user_id=user_id, created_by_name=name)
        db.add(refund)
        db.flush()
        for line in lines:
            if line.invoice_id is not None:
                db.add(PaymentAllocation(payment_id=refund.id, invoice_id=line.invoice_id, kind="erstattung", amount=-line.amount,
                                         created_by_user_id=user_id, created_by_name=name))
            else:
                db.add(PaymentRefundSource(refund_payment_id=refund.id, source_payment_id=line.payment_id, amount=line.amount,
                                           created_by_user_id=user_id, created_by_name=name))
        db.flush()
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(refund)
    return refund


def customer_credits(db: Session, customer_id: int) -> list[dict]:
    """Guthaben des Kunden (seit 1.8.90): je gültiger Endrechnung mit Überzahlung, was nach den Erstattungen noch zu erstatten ist."""
    from .final_dunning import dunning_states  # lokal: Zirkel-Import

    finals = list(db.scalars(select(Invoice).where(Invoice.customer_id == customer_id, Invoice.invoice_type == "schluss",
                                                   Invoice.status == "versendet").order_by(Invoice.invoice_date, Invoice.id)))
    states = dunning_states(db, finals)
    return [{"invoice_id": inv.id, "invoice_number": inv.invoice_number, "invoice_date": inv.invoice_date,
             "credit": states[inv.id].credit} for inv in finals if states[inv.id].credit > 0]


# ---------------------------------------------------------------------------
# Gegenbuchung
# ---------------------------------------------------------------------------

def _reversed_allocation_ids(db: Session, allocation_ids: Iterable[int]) -> set[int]:
    ids = list(allocation_ids)
    if not ids:
        return set()
    return set(db.scalars(select(PaymentAllocation.reverses_allocation_id).where(
        PaymentAllocation.reverses_allocation_id.in_(ids))))


def _counter(allocation: PaymentAllocation, reason: str, user_id, name) -> PaymentAllocation:
    return PaymentAllocation(payment_id=allocation.payment_id, invoice_id=allocation.invoice_id, kind=allocation.kind,
                             amount=-allocation.amount, charge_id=allocation.charge_id,  # seit 1.8.81: dieselbe Nebenforderung
                             reverses_allocation_id=allocation.id, reason=reason, created_by_user_id=user_id,
                             created_by_name=name)


def reverse_allocation(db: Session, allocation: PaymentAllocation, *, reason: str | None, user_id: int | None = None,
                       user_name: str | None = None) -> PaymentAllocation:
    """Gegenbuchung einer Zuordnung bzw. eines Abzugs, ganz (Festlegung 1.8.78 Nr. 9): der Betrag geht an die Rechnung zurück,
    eine Zahlung wird wieder Rest am Kunden."""
    reason = _reason(reason)
    name = (user_name or "System")[:160]
    invoice = db.get(Invoice, allocation.invoice_id)
    lock_for_booking(db, [invoice.order_id], [allocation.payment_id])
    try:
        if allocation.reverses_allocation_id is not None:
            raise PaymentRejected("Eine Gegenbuchung lässt sich nicht gegenbuchen.")
        if allocation.kind == "erstattung":  # seit 1.8.90: der Zahlungsausgang als Ganzes
            raise PaymentRejected("Eine Erstattung wird als Ganzes zurückgenommen – in der Kundenakte „Zahlung zurücknehmen“.")
        if allocation.id in _reversed_allocation_ids(db, [allocation.id]):
            raise PaymentRejected("Diese Zuordnung ist schon gegengebucht.")
        counter = _counter(allocation, reason, user_id, name)
        db.add(counter)
        db.flush()
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(counter)
    return counter


def reverse_payment(db: Session, payment: Payment, *, reason: str | None, user_id: int | None = None,
                    user_name: str | None = None) -> Payment:
    """Zahlung zurücknehmen (falsch erfasst, nie eingegangen): Gegenbuchung jeder noch geltenden Zuordnung und der Zahlung
    selbst, mit derselben Begründung, in einem Schritt."""
    reason = _reason(reason)
    name = (user_name or "System")[:160]
    if payment.reverses_payment_id is not None:
        raise PaymentRejected("Eine Gegenbuchung lässt sich nicht zurücknehmen.")

    def rows_and_orders():
        rows = list(db.scalars(select(PaymentAllocation).where(PaymentAllocation.payment_id == payment.id)))
        return rows, {db.get(Invoice, a.invoice_id).order_id for a in rows}

    # Die Aufträge stehen erst nach dem Lesen der Zuordnungen fest; kam bis zur Sperre der Zahlung eine Zuordnung auf einen
    # weiteren Auftrag dazu, wird neu gesperrt -- die feste Reihenfolge (Aufträge, dann Zahlung) bleibt so gewahrt.
    for _ in range(3):
        rows, order_ids = rows_and_orders()
        lock_for_booking(db, order_ids, [payment.id])
        rows, locked = rows_and_orders()
        if locked <= order_ids:
            break
        db.rollback()
    else:
        raise PaymentRejected("Die Zahlung wird gerade neu zugeordnet -- bitte erneut versuchen.")
    try:
        if payment.id in _reversed_payment_ids(db, [payment.id]):
            raise PaymentRejected("Diese Zahlung ist schon zurückgenommen.")
        # Seit 1.8.93: aus ihrem Rest erstattet -- erst den Zahlungsausgang zurücknehmen (sonst wäre Geld erstattet, das es nicht gab).
        refunds = _live_refunds_from(db, payment.id)
        if refunds:
            numbers = ", ".join(f"Nr. {r.refund_payment_id}" for r in refunds)
            raise PaymentRejected(f"Aus dem Rest dieser Zahlung ist erstattet ({money(sum((r.amount for r in refunds), ZERO))}, "
                                  f"Zahlungsausgang {numbers}) -- erst den Zahlungsausgang zurücknehmen.")
        done = _reversed_allocation_ids(db, [a.id for a in rows])
        for allocation in rows:
            if allocation.reverses_allocation_id is None and allocation.id not in done:
                db.add(_counter(allocation, reason, user_id, name))
        counter = Payment(customer_id=payment.customer_id, received_on=payment.received_on, amount=-payment.amount,
                          note=payment.note, origin=payment.origin, reverses_payment_id=payment.id, reason=reason,
                          created_by_user_id=user_id, created_by_name=name)
        db.add(counter)
        db.flush()
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(payment)
    return payment


def _live_refunds_from(db: Session, payment_id: int) -> list[PaymentRefundSource]:
    """Erstattungen aus dem Rest dieser Zahlung über Zahlungsausgänge, die nicht zurückgenommen sind (seit 1.8.93)."""
    reversed_ids = select(Payment.reverses_payment_id).where(Payment.reverses_payment_id.is_not(None))
    return list(db.scalars(select(PaymentRefundSource).where(
        PaymentRefundSource.source_payment_id == payment_id, PaymentRefundSource.refund_payment_id.not_in(reversed_ids))
        .order_by(PaymentRefundSource.id)))


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------

def _allocation_rows(db: Session, rows: list[PaymentAllocation]) -> list[dict]:
    """Zuordnungen mit Rechnung, Zahlung und Gegenbuchung -- die Gegenbuchung selbst steht an ihrer Zuordnung."""
    counters = {a.reverses_allocation_id: a for a in rows if a.reverses_allocation_id is not None}
    missing = [a.id for a in rows if a.reverses_allocation_id is None and a.id not in counters]
    if missing:
        for c in db.scalars(select(PaymentAllocation).where(PaymentAllocation.reverses_allocation_id.in_(missing))):
            counters[c.reverses_allocation_id] = c
    from .dunning_charges import _level_labels, charge_label  # lokal: Zirkel-Import

    labels = _level_labels(db) if any(a.charge_id for a in rows) else {}
    result = []
    for a in rows:
        if a.reverses_allocation_id is not None:
            continue
        invoice = db.get(Invoice, a.invoice_id)
        payment = db.get(Payment, a.payment_id)
        counter = counters.get(a.id)
        charge = db.get(InvoiceCharge, a.charge_id) if a.charge_id else None
        kind_label = KIND_LABELS.get(a.kind, a.kind)
        if charge is not None:
            kind_label = "Zahlung auf " + charge_label(charge, db.get(Reminder, charge.reminder_id) if charge.reminder_id
                                                       else None, labels)
        result.append({
            "id": a.id, "payment_id": a.payment_id, "invoice_id": a.invoice_id,
            "invoice_number": invoice.invoice_number if invoice else None, "order_id": invoice.order_id if invoice else None,
            "kind": a.kind, "kind_label": kind_label, "amount": a.amount, "charge_id": a.charge_id,
            "received_on": payment.received_on if payment else None, "payment_note": payment.note if payment else None,
            "payment_origin": payment.origin if payment else None,
            "created_at": a.created_at, "created_by_name": a.created_by_name,
            "reversed": counter is not None,
            "reversal": ({"id": counter.id, "reason": counter.reason, "created_at": counter.created_at,
                          "created_by_name": counter.created_by_name} if counter else None),
        })
    return result


def invoice_allocations(db: Session, invoice: Invoice) -> list[dict]:
    rows = list(db.scalars(select(PaymentAllocation).where(PaymentAllocation.invoice_id == invoice.id)
                           .order_by(PaymentAllocation.id)))
    return _allocation_rows(db, rows)


def payment_to_dict(db: Session, payment: Payment) -> dict:
    rows = list(db.scalars(select(PaymentAllocation).where(PaymentAllocation.payment_id == payment.id)
                           .order_by(PaymentAllocation.id)))
    counter = db.scalar(select(Payment).where(Payment.reverses_payment_id == payment.id))
    return {
        "id": payment.id, "customer_id": payment.customer_id, "received_on": payment.received_on, "amount": payment.amount,
        "note": payment.note, "origin": payment.origin, "created_at": payment.created_at,
        "created_by_name": payment.created_by_name, "rest": payment_rest(db, payment),
        "is_refund": Decimal(payment.amount) < 0,  # seit 1.8.90: Zahlungsausgang (Erstattung)
        # Seit 1.8.93: am Zahlungsausgang, aus welchen Resten er erstattet; an einer Zahlung, was aus ihrem Rest erstattet ist.
        "refund_sources": [{"payment_id": s.source_payment_id, "amount": s.amount,
                            "received_on": db.get(Payment, s.source_payment_id).received_on}
                           for s in db.scalars(select(PaymentRefundSource).where(PaymentRefundSource.refund_payment_id == payment.id)
                                               .order_by(PaymentRefundSource.id))],
        "refunded_from_rest": [{"refund_payment_id": s.refund_payment_id, "amount": s.amount,
                                "paid_on": db.get(Payment, s.refund_payment_id).received_on}
                               for s in _live_refunds_from(db, payment.id)],
        "reversed": counter is not None,
        "reversal": ({"reason": counter.reason, "created_at": counter.created_at, "created_by_name": counter.created_by_name}
                     if counter else None),
        "allocations": _allocation_rows(db, rows),
    }


def customer_payments(db: Session, customer_id: int) -> dict:
    """Zahlungen eines Kunden, neueste zuerst, mit dem nicht zugeordneten Rest (ohne die Gegenbuchungen selbst)."""
    payments = list(db.scalars(select(Payment).where(Payment.customer_id == customer_id,
                                                     Payment.reverses_payment_id.is_(None))
                               .order_by(Payment.received_on.desc(), Payment.id.desc())))
    rows = [payment_to_dict(db, p) for p in payments]
    credits = customer_credits(db, customer_id)  # seit 1.8.90
    return {"customer_id": customer_id, "payments": rows, "rest": sum((r["rest"] for r in rows), ZERO),
            "credits": credits, "credit_total": sum((c["credit"] for c in credits), ZERO),
            "balance": customer_balance(rows, credits)}


def customer_balance(payment_rows: list[dict], credits: list[dict]) -> dict:
    """Guthaben des Kunden (seit 1.8.93, Nacharbeit R4c Punkt 3): die nicht zugeordneten Reste seiner Zahlungen und die Guthaben aus
    Endrechnungen zusammen, je Zahlung bzw. Schlussrechnung eine Zeile (ältere zuerst)."""
    lines = [{"kind": "rest", "payment_id": r["id"], "invoice_id": None, "invoice_number": None, "date": r["received_on"],
              "amount": r["rest"]}
             for r in sorted(payment_rows, key=lambda r: (r["received_on"], r["id"])) if r["rest"] > 0]
    lines += [{"kind": "guthaben", "payment_id": None, "invoice_id": c["invoice_id"], "invoice_number": c["invoice_number"],
               "date": c["invoice_date"], "amount": c["credit"]} for c in credits]
    rest = sum((line["amount"] for line in lines if line["kind"] == "rest"), ZERO)
    credit = sum((line["amount"] for line in lines if line["kind"] == "guthaben"), ZERO)
    return {"rest": rest, "credit": credit, "total": rest + credit, "lines": lines}


def open_invoices_of_customer(db: Session, customer_id: int) -> list[dict]:
    """Offene, bebuchbare Rechnungen des Kunden -- für "weitere Rechnungen von Hand" und das Zuordnen eines Rests."""
    # Seit 1.8.79 nach dem Kunden, den die Rechnung beim Festschreiben festhielt (Invoice.customer_id), nicht mehr nach dem
    # Kunden ihres Projekts.
    from .dunning_charges import charge_lines, open_charge_rows  # lokal: Zirkel-Import

    invoices = list(db.scalars(
        select(Invoice).where(Invoice.customer_id == customer_id, Invoice.status == "versendet", Invoice.invoice_type != "storno")
        .order_by(Invoice.invoice_date, Invoice.id)))
    states = payment_states(db, invoices)
    result = []
    for inv in invoices:
        state = states[inv.id]
        if state is None:
            continue
        # Seit 1.8.81 auch mit offenen Nebenforderungen allein (Rechnung bezahlt, Mahngebühr offen).
        charges = open_charge_rows(db, inv)
        if state.open == 0 and not charges:
            continue
        labels = {line["id"]: line["label"] for line in charge_lines(db, [c for c, _ in charges])}
        offer = skonto_offer(inv)
        result.append({"invoice_id": inv.id, "invoice_number": inv.invoice_number, "invoice_type": inv.invoice_type,
                       "invoice_date": inv.invoice_date, "order_id": inv.order_id,
                       "order_number": inv.order.order_number if inv.order else None, "payment": state.as_dict(),
                       "skonto_offer": {"until": offer[0], "amount": offer[1]} if offer else None,
                       "charges": [{"charge_id": c.id, "kind": c.kind, "label": labels[c.id], "open": rest}
                                   for c, rest in charges]})
    return result


def customer_balances(db: Session) -> list[dict]:
    """Guthaben der Kunden (Finanzen, Dashboard; seit 1.8.93): je Kunde nicht zugeordneter Rest und Guthaben aus Endrechnungen, nur
    Kunden mit einem von beiden, das größte zuerst."""
    from .final_dunning import dunning_states  # lokal: Zirkel-Import

    rests = {r["customer_id"]: r["rest"] for r in unallocated_by_customer(db)}
    finals = list(db.scalars(select(Invoice).where(Invoice.invoice_type == "schluss", Invoice.status == "versendet")))
    states = dunning_states(db, finals)
    credits: dict[int, Decimal] = {}
    for invoice in finals:
        if states[invoice.id].credit > 0:
            customer_id = invoice_customer_id(invoice)
            credits[customer_id] = credits.get(customer_id, ZERO) + states[invoice.id].credit
    result = []
    for customer_id in set(rests) | set(credits):
        customer = db.get(Customer, customer_id)
        rest, credit = rests.get(customer_id, ZERO), credits.get(customer_id, ZERO)
        result.append({"customer_id": customer_id, "customer_name": customer.name if customer else None, "rest": rest,
                       "credit": credit, "total": rest + credit})
    return sorted(result, key=lambda r: (-r["total"], r["customer_id"]))


def unallocated_by_customer(db: Session) -> list[dict]:
    """Kunden mit nicht zugeordnetem Rest (Finanzen): Summe der Zahlungen minus Zuordnungen, ohne zurückgenommene."""
    reversed_ids = select(Payment.reverses_payment_id).where(Payment.reverses_payment_id.is_not(None))
    allocated = (select(PaymentAllocation.payment_id, func.sum(PaymentAllocation.amount).label("allocated"))
                 .where(PaymentAllocation.kind.in_(MONEY_KINDS)).group_by(PaymentAllocation.payment_id).subquery())
    rows = db.execute(
        select(Payment.customer_id, func.sum(Payment.amount - func.coalesce(allocated.c.allocated, 0)))
        .outerjoin(allocated, allocated.c.payment_id == Payment.id)
        .where(Payment.reverses_payment_id.is_(None), Payment.id.not_in(reversed_ids))
        .group_by(Payment.customer_id)
    ).all()
    result = []
    for customer_id, rest in rows:
        rest = round_money(rest)
        if rest > 0:
            customer = db.get(Customer, customer_id)
            result.append({"customer_id": customer_id, "customer_name": customer.name if customer else None, "rest": rest})
    return sorted(result, key=lambda r: -r["rest"])
