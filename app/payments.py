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
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from .berlin_time import berlin_today
from .invoices import EDITABLE_STATUS, compute_invoice_totals, invoice_rounding, lock_order_invoices, skonto_offer
from .models import Customer, Invoice, Order, Payment, PaymentAllocation, Project
from .rounding import CENT, round_money
from .zugehoerigkeit import IdNichtGefunden

ORIGINS = ("erfasst", "uebernommen")
KINDS = ("zahlung", "skonto", "einbehalt")
KIND_LABELS = {"zahlung": "Zahlung", "skonto": "Skonto", "einbehalt": "Einbehalt"}
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
    if payable_gross(invoice) <= 0:
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

    @property
    def any(self) -> bool:
        return bool(self.paid or self.skonto or self.retained)


def allocation_sums(db: Session, invoice_ids: Iterable[int]) -> dict[int, Sums]:
    """Summen je Rechnung in zwei Abfragen (Finanzen, Mahnwesen: viele Rechnungen auf einmal)."""
    ids = sorted(set(invoice_ids))
    if not ids:
        return {}
    totals: dict[int, dict[str, Decimal]] = {}
    for invoice_id, kind, amount in db.execute(
        select(PaymentAllocation.invoice_id, PaymentAllocation.kind, func.sum(PaymentAllocation.amount))
        .where(PaymentAllocation.invoice_id.in_(ids)).group_by(PaymentAllocation.invoice_id, PaymentAllocation.kind)
    ):
        totals.setdefault(invoice_id, {})[kind] = round_money(amount)
    reversal = aliased(PaymentAllocation)
    last = dict(db.execute(
        select(PaymentAllocation.invoice_id, func.max(Payment.received_on))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .outerjoin(reversal, reversal.reverses_allocation_id == PaymentAllocation.id)
        .where(PaymentAllocation.invoice_id.in_(ids), PaymentAllocation.kind == "zahlung",
               PaymentAllocation.reverses_allocation_id.is_(None), reversal.id.is_(None))
        .group_by(PaymentAllocation.invoice_id)
    ).all())
    return {i: Sums(paid=totals.get(i, {}).get("zahlung", ZERO), skonto=totals.get(i, {}).get("skonto", ZERO),
                    retained=totals.get(i, {}).get("einbehalt", ZERO), last_received_on=last.get(i)) for i in ids}


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
                                                         ("einbehalt", sums.retained)) if v]
    return (f"Der Rechnung sind Zahlungen zugeordnet ({', '.join(parts)}). Erst die Zuordnungen lösen (Gegenbuchung mit "
            "Begründung) -- die Zahlung bleibt dann beim Kunden, nicht zugeordnet.")


def dunning_block_reason(db: Session, invoice: Invoice) -> str | None:
    """Warum zu dieser Rechnung keine Mahnung entsteht oder hinausgeht, weil nichts mahnfähig ist (app/reminders.py)."""
    number = invoice.invoice_number or "(Entwurf)"
    if invoice.invoice_type == "storno":
        return f"{number} ist eine Stornorechnung -- sie ist nie offen, dazu geht keine Mahnung hinaus."
    state = payment_state(db, invoice)
    if state is None or state.dunnable > 0:
        return None
    if state.state == "bezahlt":
        paid = f" (am {_de(state.paid_on)})" if state.paid_on else ""
        return f"Die Rechnung {number} ist bezahlt{paid} -- dazu geht keine Mahnung mehr hinaus."
    return (f"Von der Rechnung {number} ist nur noch der Einbehalt offen ({money(state.retained_open)}) -- ein Einbehalt "
            "wird nicht gemahnt.")


def invoice_customer_id(invoice: Invoice) -> int | None:
    """Kunde der Rechnung = Kunde ihres Projekts (die Rechnung trägt nur einen Schnappschuss des Namens)."""
    order = invoice.order
    return order.project.customer_id if order is not None and order.project is not None else None


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
        if inv.id != invoice.id and (state is None or state.open == 0):
            continue
        rows.append({"invoice": inv, "state": state, "skonto": _skonto_proposal(inv, state, received_on)})

    def eligible(row) -> Decimal | None:
        return row["skonto"]["amount"] if row["skonto"] and row["skonto"]["in_period"] else None

    alloc = {r["invoice"].id: [ZERO, ZERO] for r in rows}  # [zahlung, skonto]
    total_open = sum((r["state"].open for r in rows), ZERO)
    with_skonto = sum((r["state"].open - (eligible(r) or ZERO) for r in rows), ZERO)
    if amount >= total_open:
        for r in rows:
            alloc[r["invoice"].id][0] = r["state"].open
    elif any(eligible(r) for r in rows) and amount == with_skonto:
        for r in rows:
            s = eligible(r) or ZERO
            alloc[r["invoice"].id] = [r["state"].open - s, s]
    else:
        remaining = amount
        for r in rows:
            if remaining <= 0:
                break
            open_, s = r["state"].open, eligible(r)
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
        lines.append({
            "invoice_id": inv.id, "invoice_number": inv.invoice_number, "invoice_type": inv.invoice_type,
            "invoice_date": inv.invoice_date, "order_id": inv.order_id, "is_selected": inv.id == invoice.id,
            "open": state.open, "zahlung": zahlung, "skonto": skonto, "einbehalt": ZERO,
            "skonto_offer": ({"until": sk["until"], "amount": sk["amount"], "in_period": sk["in_period"]} if sk else None),
        })
    allocated = sum((line["zahlung"] for line in lines), ZERO)
    return {"amount": amount, "received_on": received_on, "lines": lines, "rest": amount - allocated}


# ---------------------------------------------------------------------------
# Buchen
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Line:
    """Eine bestätigte Zeile: was von der Zahlung auf die Rechnung geht und welche Abzüge mit ihr gebucht werden."""
    invoice_id: int
    zahlung: Decimal = ZERO
    skonto: Decimal = ZERO
    einbehalt: Decimal = ZERO


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
    seen = set()
    checked = []
    for line in lines:
        if line.invoice_id in seen:
            raise ValueError("Jede Rechnung höchstens einmal je Buchung.")
        seen.add(line.invoice_id)
        z, s, e = (_cents(line.zahlung, "Zahlung"), _cents(line.skonto, "Skonto"), _cents(line.einbehalt, "Einbehalt"))
        if not (z or s or e):
            raise ValueError("Eine Zeile ohne Betrag -- bitte weglassen.")
        checked.append(Line(line.invoice_id, z, s, e))
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


def payment_rest(db: Session, payment: Payment) -> Decimal:
    """Noch nicht zugeordneter Betrag der Zahlung (0, wenn sie zurückgenommen ist)."""
    if payment.reverses_payment_id is not None or payment.id in _reversed_payment_ids(db, [payment.id]):
        return ZERO
    allocated = db.scalar(select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
        PaymentAllocation.payment_id == payment.id, PaymentAllocation.kind == "zahlung"))
    return round_money(Decimal(payment.amount) - Decimal(allocated or 0))


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
    total = sum((line.zahlung for line in lines), ZERO)
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
    for line in lines:
        for kind, value in (("zahlung", line.zahlung), ("skonto", line.skonto), ("einbehalt", line.einbehalt)):
            if value:
                db.add(PaymentAllocation(payment_id=payment.id, invoice_id=line.invoice_id, kind=kind, amount=value,
                                         created_by_user_id=user_id, created_by_name=name))


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
                             amount=-allocation.amount, reverses_allocation_id=allocation.id, reason=reason,
                             created_by_user_id=user_id, created_by_name=name)


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
    result = []
    for a in rows:
        if a.reverses_allocation_id is not None:
            continue
        invoice = db.get(Invoice, a.invoice_id)
        payment = db.get(Payment, a.payment_id)
        counter = counters.get(a.id)
        result.append({
            "id": a.id, "payment_id": a.payment_id, "invoice_id": a.invoice_id,
            "invoice_number": invoice.invoice_number if invoice else None, "order_id": invoice.order_id if invoice else None,
            "kind": a.kind, "kind_label": KIND_LABELS.get(a.kind, a.kind), "amount": a.amount,
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
    return {"customer_id": customer_id, "payments": rows, "rest": sum((r["rest"] for r in rows), ZERO)}


def open_invoices_of_customer(db: Session, customer_id: int) -> list[dict]:
    """Offene, bebuchbare Rechnungen des Kunden -- für "weitere Rechnungen von Hand" und das Zuordnen eines Rests."""
    invoices = list(db.scalars(
        select(Invoice).join(Order, Order.id == Invoice.order_id).join(Project, Project.id == Order.project_id)
        .where(Project.customer_id == customer_id, Invoice.status == "versendet", Invoice.invoice_type != "storno")
        .order_by(Invoice.invoice_date, Invoice.id)))
    states = payment_states(db, invoices)
    result = []
    for inv in invoices:
        state = states[inv.id]
        if state is None or state.open == 0:
            continue
        offer = skonto_offer(inv)
        result.append({"invoice_id": inv.id, "invoice_number": inv.invoice_number, "invoice_type": inv.invoice_type,
                       "invoice_date": inv.invoice_date, "order_id": inv.order_id,
                       "order_number": inv.order.order_number if inv.order else None, "payment": state.as_dict(),
                       "skonto_offer": {"until": offer[0], "amount": offer[1]} if offer else None})
    return result


def unallocated_by_customer(db: Session) -> list[dict]:
    """Kunden mit nicht zugeordnetem Rest (Finanzen): Summe der Zahlungen minus Zuordnungen, ohne zurückgenommene."""
    reversed_ids = select(Payment.reverses_payment_id).where(Payment.reverses_payment_id.is_not(None))
    allocated = (select(PaymentAllocation.payment_id, func.sum(PaymentAllocation.amount).label("allocated"))
                 .where(PaymentAllocation.kind == "zahlung").group_by(PaymentAllocation.payment_id).subquery())
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
