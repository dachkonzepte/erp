"""Mahngebühren, Pauschale und Verzugsbeginn (seit 1.8.80, Zahlungsstufe Z2b, docs/archiv/zahlungen.md "Umsetzung 1.8.80").

Zuschaltbar (Nr. 3): GeneralSettings.dunning_charges_enabled, nur Admin, Vorgabe aus. Aus heißt: keine Felder, keine Beträge --
keine Gebühr je Stufe, keine Pauschale, keine neue Nebenforderung, eine neue Mahnung zeigt keine.

Nebenforderungen (Nr. 4, InvoiceCharge): je Rechnung, Art Gebühr oder Pauschale (Verzugszinsen folgen mit Punkt 7), nie im
Rechnungsbetrag und ohne Umsatzsteuer -- die Rechnung, ihr Zahlstand (app/payments.py) und ihr PDF bleiben unverändert. Sie
entstehen beim Festschreiben einer Mahnung aus dem, was ihr Entwurf bewusst übernahm (app/reminders.py::finalize_and_send_reminder()
-> add_charges()), unter der Sperre der Auftragszeile. Unveränderlich (ORM-Sperre); Korrektur oder Erlass nur als Gegenbuchung
mit Begründung (reverse_charge()). Jede Mahnung zeigt die geltenden aufsummiert (app/reminders.py::amounts_snapshot()).

Gebühr (Nr. 5): die Gebühr der Stufe ist ein Vorschlag, je Mahnung bewusst übernommen (Reminder.fee_accepted).

Pauschale (Nr. 6): 40 € nach § 288 Abs. 5 BGB, nur bei Kunden, die keine Verbraucher sind, einmal je Rechnung, erst ab Verzug --
als Vorschlag im Mahnungsentwurf, bewusst übernommen (Reminder.flat_fee_accepted), geprüft beim Übernehmen und beim Festschreiben
(flat_fee_block_reason()).

Verzugsbeginn (InvoiceDefaultStart): Vorschlag (default_start_proposal()) aus dem Zugang der ersten Mahnung (versendet oder
zugestellt, app/email_dispatch.py::document_reached_on()), bei Kunden, die keine Verbraucher sind, spätestens 30 Tage nach
Fälligkeit und Zugang der Rechnung (§ 286 Abs. 3 BGB) -- das frühere von beiden. Das Büro bestätigt ihn oder legt ihn abweichend mit
Begründung fest (confirm_default_start()); Korrektur durch Verwerfen mit Begründung (discard_default_start()), solange keine
Pauschale gilt. Keine Rechtsberatung: jeder Vorschlag nennt seine Quelle, entscheiden tut das Büro.

Seit 1.8.81 (Z2b Punkte 7 und 8, "Vorweg" 1 und 2):
- Verzugszinsen als Nebenforderung Art "zinsen" (app/default_interest.py): Vorschlag im Entwurf bis zum Mahndatum, bewusst
  übernommen (Reminder.interest_accepted), beim Festschreiben frisch berechnet und mit Zeitraum und Berechnung eingefroren.
- Zahlungen auf Nebenforderungen (PaymentAllocation Art "nebenforderung", app/payments.py): "offen" einer Nebenforderung = Betrag
  − Zahlungen darauf (charge_paid()). Gegenbuchen erst nach gelöster Zuordnung.
- Ist die Pauschale gebucht (oder übernimmt der Entwurf sie), schlägt die Mahnung keine Gebühr vor -- sie ist durch die Pauschale
  abgegolten (§ 288 Abs. 5 S. 3 BGB, fee_block_reason()).
- Storno nur ohne offene Nebenforderungen (charges_storno_block_reason(), app/invoices.py::storno_block_reason()).
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit import current_actor
from .berlin_time import berlin_today, to_berlin
from .default_interest import calculation_json, interest_label, interest_proposal, sections_of
from .invoices import invoice_customer, lock_order_invoices
from .models import GeneralSettings, Invoice, InvoiceCharge, InvoiceDefaultStart, Payment, PaymentAllocation, Reminder, ReminderLevel
from .rounding import round_money

KINDS = ("gebuehr", "pauschale", "zinsen")
KIND_LABELS = {"gebuehr": "Mahngebühr", "pauschale": "Pauschale nach § 288 Abs. 5 BGB", "zinsen": "Verzugszinsen"}
# § 367 Abs. 1 BGB: erst die Kosten, dann die Zinsen, dann die Hauptleistung -- Reihenfolge der Nebenforderungen je Rechnung.
COST_KINDS = ("gebuehr", "pauschale")
FEE_ABSORBED = "durch die Pauschale abgegolten (§ 288 Abs. 5 S. 3 BGB)"
BASES = ("mahnung", "dreissig_tage", "von_hand")
BASIS_LABELS = {"mahnung": "Zugang der ersten Mahnung", "dreissig_tage": "30 Tage nach Fälligkeit und Zugang der Rechnung",
                "von_hand": "abweichend festgelegt"}
FLAT_FEE = Decimal("40.00")
ZERO = Decimal("0.00")
DISABLED_TEXT = "Mahngebühren und Verzugszinsen sind ausgeschaltet (Einstellungen → Mahnstufen)."


class ChargeRejected(ValueError):
    """Gegenbuchung, Verzugsbeginn oder Übernahme am Stand nicht möglich -- Router: 409 mit dem Text."""


def _de(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _reason(text: str | None) -> str:
    text = (text or "").strip()
    if not text:
        raise ValueError("Bitte eine Begründung angeben.")
    return text


def _actor(user_id: int | None, user_name: str | None) -> tuple[int | None, str]:
    if user_id is None and user_name is None:
        user_id, user_name = current_actor()
    return user_id, (user_name or "System")[:160]


# ---------------------------------------------------------------------------
# Schalter (Nr. 3)
# ---------------------------------------------------------------------------

def charges_enabled(db: Session) -> bool:
    """Sind Mahngebühren und Verzugszinsen eingeschaltet? Ohne Einstellungszeile (sollte es nach dem Start nicht geben): aus."""
    settings = db.get(GeneralSettings, 1)
    return bool(settings is not None and settings.dunning_charges_enabled)


def set_charges_enabled(db: Session, enabled: bool) -> bool:
    from .settings import load_general_settings  # lokal: app/settings.py ist groß und hier nur dafür gebraucht

    settings = load_general_settings(db)
    settings.dunning_charges_enabled = bool(enabled)
    db.commit()
    return settings.dunning_charges_enabled


# ---------------------------------------------------------------------------
# Nebenforderungen (Nr. 4)
# ---------------------------------------------------------------------------

def _reversed_ids(db: Session, ids: Iterable[int]) -> set[int]:
    ids = list(ids)
    if not ids:
        return set()
    return set(db.scalars(select(InvoiceCharge.reverses_charge_id).where(InvoiceCharge.reverses_charge_id.in_(ids))))


def charges_in_force(db: Session, invoice_ids: Iterable[int], *, on: date | None = None) -> dict[int, list[InvoiceCharge]]:
    """Geltende Nebenforderungen je Rechnung, älteste zuerst: ohne Gegenbuchungen und ohne gegengebuchte -- eine gegengebuchte
    gilt nie, auch nicht für die Zeit davor. on: nur die bis zu diesem Tag (Europe/Berlin) entstandenen (Zustellung nachtragen)."""
    ids = sorted(set(invoice_ids))
    if not ids:
        return {}
    rows = list(db.scalars(select(InvoiceCharge).where(
        InvoiceCharge.invoice_id.in_(ids), InvoiceCharge.reverses_charge_id.is_(None)).order_by(InvoiceCharge.id)))
    reversed_ids = _reversed_ids(db, [r.id for r in rows])
    result: dict[int, list[InvoiceCharge]] = {i: [] for i in ids}
    for r in rows:
        if r.id in reversed_ids:
            continue
        if on is not None and to_berlin(r.created_at).date() > on:
            continue
        result[r.invoice_id].append(r)
    return result


def charges_total(charges: Iterable[InvoiceCharge]) -> Decimal:
    return round_money(sum((Decimal(c.amount) for c in charges), ZERO))


def charge_paid(db: Session, charge_ids: Iterable[int], *, received_until: date | None = None) -> dict[int, Decimal]:
    """Geltende Zahlungen je Nebenforderung (seit 1.8.81, Zuordnungen Art "nebenforderung", Gegenbuchungen abgezogen -- sie tragen
    dieselbe charge_id). received_until: nur aus Zahlungen mit Eingangsdatum bis zu diesem Tag (Stand an einem Tag)."""
    ids = sorted(set(charge_ids))
    if not ids:
        return {}
    stmt = (select(PaymentAllocation.charge_id, func.sum(PaymentAllocation.amount))
            .where(PaymentAllocation.charge_id.in_(ids), PaymentAllocation.kind == "nebenforderung")
            .group_by(PaymentAllocation.charge_id))
    if received_until is not None:
        stmt = stmt.join(Payment, Payment.id == PaymentAllocation.payment_id).where(Payment.received_on <= received_until)
    paid = {cid: round_money(amount or 0) for cid, amount in db.execute(stmt)}
    return {i: paid.get(i, ZERO) for i in ids}


def open_charges(db: Session, invoice: Invoice, *, on: date | None = None) -> Decimal:
    """Offene Nebenforderungen der Rechnung: die geltenden, abzüglich der Zahlungen darauf (seit 1.8.81). on: Stand an diesem Tag
    (bis dahin entstanden, Zahlungen mit Eingang bis dahin)."""
    charges = charges_in_force(db, [invoice.id], on=on)[invoice.id]
    paid = charge_paid(db, [c.id for c in charges], received_until=on)
    return round_money(charges_total(charges) - sum(paid.values(), ZERO))


def open_charge_rows(db: Session, invoice: Invoice) -> list[tuple[InvoiceCharge, Decimal]]:
    """Geltende Nebenforderungen mit offenem Rest > 0, in der Reihenfolge nach § 367 Abs. 1 BGB: erst die Kosten (Gebühr,
    Pauschale), dann die Zinsen -- je Art die älteste zuerst."""
    charges = charges_in_force(db, [invoice.id])[invoice.id]
    paid = charge_paid(db, [c.id for c in charges])
    rows = [(c, round_money(Decimal(c.amount) - paid[c.id])) for c in charges]
    rows = [(c, rest) for c, rest in rows if rest > 0]
    return sorted(rows, key=lambda r: (0 if r[0].kind in COST_KINDS else 1, r[0].id))


def _level_labels(db: Session) -> dict[int, str]:
    return {lvl.level: lvl.label for lvl in db.scalars(select(ReminderLevel))}


def charge_label(charge: InvoiceCharge, reminder: Reminder | None, labels: dict[int, str]) -> str:
    """"Mahngebühr (2. Mahnung M-2026-0004)", "Pauschale nach § 288 Abs. 5 BGB", "Verzugszinsen vom 01.03.2026 bis …"."""
    if charge.kind == "gebuehr" and reminder is not None:
        level = labels.get(reminder.level, f"{reminder.level}. Mahnung")
        return f"Mahngebühr ({level} {reminder.reminder_number or ''})".replace(" )", ")")
    if charge.kind == "zinsen":
        return interest_label(charge.period_start, charge.period_end)
    return KIND_LABELS.get(charge.kind, charge.kind)


def _sections_out(calculation: str | None) -> list[dict]:
    from .default_interest import section_text  # lokal: section_text braucht money() von hier
    return [dict(s, text=section_text(s)) for s in sections_of(calculation)]


def charge_lines(db: Session, charges: list[InvoiceCharge], *, received_until: date | None = None) -> list[dict]:
    """Zeilen für Mahnung und Aufstellung: Bezeichnung, Betrag und (seit 1.8.81) darauf gezahlt je geltender Nebenforderung, bei
    Zinsen dazu Zeitraum und Abschnitte."""
    labels = _level_labels(db)
    paid = charge_paid(db, [c.id for c in charges], received_until=received_until)
    return [{"id": c.id, "kind": c.kind, "label": charge_label(c, db.get(Reminder, c.reminder_id) if c.reminder_id else None,
                                                             labels),
             "amount": round_money(Decimal(c.amount)), "paid": paid.get(c.id, ZERO),
             "period_start": c.period_start, "period_end": c.period_end,
             "surcharge": _surcharge_of(c), "sections": _sections_out(c.calculation_json) if c.kind == "zinsen" else []}
            for c in charges]


def _surcharge_of(charge: InvoiceCharge) -> Decimal | None:
    if charge.kind != "zinsen" or not charge.calculation_json:
        return None
    return Decimal(json.loads(charge.calculation_json)["surcharge"])


def charge_rows(db: Session, invoice: Invoice) -> list[dict]:
    """Alle Nebenforderungen der Rechnung für die Rechnungsseite -- je Eintrag mit Gegenbuchung, falls es eine gibt, mit den
    Zahlungen darauf und (Zinsen) einem Hinweis, wenn eine Neuberechnung mit dem Stand heute anders ausfiele."""
    from .default_interest import recalculated  # lokal: liest den Zahlstand

    rows = list(db.scalars(select(InvoiceCharge).where(InvoiceCharge.invoice_id == invoice.id).order_by(InvoiceCharge.id)))
    counters = {r.reverses_charge_id: r for r in rows if r.reverses_charge_id is not None}
    labels = _level_labels(db)
    paid = charge_paid(db, [r.id for r in rows if r.reverses_charge_id is None])
    result = []
    for r in rows:
        if r.reverses_charge_id is not None:
            continue
        reminder = db.get(Reminder, r.reminder_id) if r.reminder_id else None
        counter = counters.get(r.id)
        amount = round_money(Decimal(r.amount))
        recalc = recalculated(db, invoice, r) if r.kind == "zinsen" and counter is None else None
        result.append({
            "id": r.id, "kind": r.kind, "kind_label": KIND_LABELS.get(r.kind, r.kind), "label": charge_label(r, reminder, labels),
            "amount": amount, "paid": paid.get(r.id, ZERO),
            "open": ZERO if counter is not None else round_money(amount - paid.get(r.id, ZERO)),
            "reminder_id": r.reminder_id, "reminder_number": reminder.reminder_number if reminder else None,
            "period_start": r.period_start, "period_end": r.period_end,
            "sections": _sections_out(r.calculation_json) if r.kind == "zinsen" else [],
            "recalculated": recalc if recalc is not None and recalc != amount else None,
            "created_at": r.created_at, "created_by_name": r.created_by_name, "reversed": counter is not None,
            "reversal": ({"reason": counter.reason, "created_at": counter.created_at, "created_by_name": counter.created_by_name}
                         if counter else None),
        })
    return result


def _counter(charge: InvoiceCharge, reason: str, user_id: int | None, name: str) -> InvoiceCharge:
    return InvoiceCharge(invoice_id=charge.invoice_id, kind=charge.kind, amount=-Decimal(charge.amount),
                         reminder_id=charge.reminder_id, reverses_charge_id=charge.id, reason=reason,
                         created_by_user_id=user_id, created_by_name=name)


def paid_block_reason(db: Session, charges: list[InvoiceCharge]) -> str | None:
    """Seit 1.8.81: eine Nebenforderung mit geltender Zahlung darauf wird nicht gegengebucht -- erst die Zuordnung lösen."""
    paid = charge_paid(db, [c.id for c in charges])
    with_payment = [c for c in charges if paid.get(c.id, ZERO) > 0]
    if not with_payment:
        return None
    labels = _level_labels(db)
    listed = ", ".join(f"{charge_label(c, db.get(Reminder, c.reminder_id) if c.reminder_id else None, labels)} "
                       f"({money(paid[c.id])} gezahlt)" for c in with_payment)
    return (f"Auf die Nebenforderung ist eine Zahlung gebucht: {listed}. Erst die Zuordnung gegenbuchen (Karte „Zahlungen“, mit "
            "Begründung) – die Zahlung bleibt dann beim Kunden –, dann die Nebenforderung.")


def reverse_charge(db: Session, charge: InvoiceCharge, *, reason: str | None, user_id: int | None = None,
                   user_name: str | None = None) -> InvoiceCharge:
    """Gegenbuchung einer Nebenforderung, ganz (Korrektur oder Erlass), mit Begründung -- unter der Sperre der Auftragszeile;
    höchstens einmal je Nebenforderung. Seit 1.8.81 nicht, solange eine Zahlung darauf gebucht ist (paid_block_reason())."""
    reason = _reason(reason)
    user_id, name = _actor(user_id, user_name)
    invoice = db.get(Invoice, charge.invoice_id)
    lock_order_invoices(db, invoice.order_id)
    try:
        if charge.reverses_charge_id is not None:
            raise ChargeRejected("Eine Gegenbuchung lässt sich nicht gegenbuchen.")
        if charge.id in _reversed_ids(db, [charge.id]):
            raise ChargeRejected("Diese Nebenforderung ist schon gegengebucht.")
        blocked = paid_block_reason(db, [charge])
        if blocked:
            raise ChargeRejected(blocked)
        counter = _counter(charge, reason, user_id, name)
        db.add(counter)
        db.flush()
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(counter)
    return counter


def charges_of_reminders(db: Session, reminders: list[Reminder]) -> list[InvoiceCharge]:
    """Die geltenden Nebenforderungen dieser Mahnungen (die beim Ersatz gegengebucht werden), älteste zuerst."""
    ids = [r.id for r in reminders]
    if not ids:
        return []
    rows = list(db.scalars(select(InvoiceCharge).where(
        InvoiceCharge.reminder_id.in_(ids), InvoiceCharge.reverses_charge_id.is_(None)).order_by(InvoiceCharge.id)))
    done = _reversed_ids(db, [r.id for r in rows])
    return [r for r in rows if r.id not in done]


def reverse_charges_of(db: Session, reminders: list[Reminder], *, reason: str) -> int:
    """Gegenbuchung der geltenden Nebenforderungen dieser Mahnungen (Vorgabe "Vorweg" 2: eine ersetzte Mahnung ging nie hinaus,
    ihre Gebühr und Pauschale gelten nicht). Unter der Sperre des Aufrufers, ohne Commit. Gibt die Zahl zurück. Seit 1.8.81
    ChargeRejected, wenn auf eine davon eine Zahlung gebucht ist (der Aufrufer rollt zurück)."""
    rows = charges_of_reminders(db, reminders)
    blocked = paid_block_reason(db, rows)
    if blocked:
        raise ChargeRejected(blocked)
    user_id, name = _actor(None, None)
    for r in rows:
        db.add(_counter(r, reason, user_id, name))
    db.flush()
    return len(rows)


def charges_storno_block_reason(db: Session, invoice: Invoice) -> str | None:
    """Seit 1.8.81 ("Vorweg" 2): eine Rechnung mit offenen Nebenforderungen wird nicht storniert -- wie bei Zahlungen erst lösen
    (gegenbuchen mit Begründung). Zahlungen auf eine Nebenforderung sperren das Storno schon als Zuordnung
    (app/payments.py::allocation_block_reason())."""
    rows = open_charge_rows(db, invoice)
    if not rows:
        return None
    labels = _level_labels(db)
    listed = ", ".join(f"{charge_label(c, db.get(Reminder, c.reminder_id) if c.reminder_id else None, labels)} {money(rest)}"
                       for c, rest in rows)
    return (f"An der Rechnung gelten offene Nebenforderungen ({listed}). Erst gegenbuchen (Karte „Nebenforderungen und Verzug“, "
            "mit Begründung), dann stornieren.")


# ---------------------------------------------------------------------------
# Verzugsbeginn
# ---------------------------------------------------------------------------

def active_default_start(db: Session, invoice_id: int) -> InvoiceDefaultStart | None:
    return db.scalar(select(InvoiceDefaultStart).where(
        InvoiceDefaultStart.invoice_id == invoice_id, InvoiceDefaultStart.discarded_at.is_(None))
        .order_by(InvoiceDefaultStart.id.desc()).limit(1))


def _first_reminder_reach(db: Session, invoice: Invoice) -> tuple[date, Reminder] | None:
    from .email_dispatch import document_reached_on  # lokal: app/email_dispatch.py zieht den Versand nach

    finalized = [r for r in invoice.reminders if r.status == "versendet"]
    reached = document_reached_on(db, "mahnung", finalized)
    if not reached:
        return None
    first = min(finalized, key=lambda r: (reached.get(r.id) or date.max, r.id))
    return reached[first.id], first


def invoice_reached_on(db: Session, invoice: Invoice) -> date | None:
    """Zugang der Rechnung: der erste Tag, an dem sie beim Auftraggeber ankam (versendet oder zugestellt)."""
    from .email_dispatch import document_reached_on

    return document_reached_on(db, "rechnung", [invoice]).get(invoice.id)


def default_start_proposal(db: Session, invoice: Invoice) -> dict:
    """Vorschlag für den Verzugsbeginn (erster Tag im Verzug), mit Quelle: {"starts_on", "basis", "source_text"} -- oder
    starts_on leer und "reason", warum es (noch) keinen gibt. Das frühere aus: Zugang der ersten Mahnung (Verzug ab diesem Tag);
    bei Kunden, die keine Verbraucher sind, 30 Tage nach Fälligkeit und Zugang der Rechnung (Verzug ab dem 31. Tag nach dem
    späteren von beiden, § 286 Abs. 3 BGB). Fälligkeit = die Fälligkeit der Rechnung, ohne sie das Rechnungsdatum."""
    labels = _level_labels(db)
    candidates = []
    notes = []
    first = _first_reminder_reach(db, invoice)
    if first is not None:
        day, reminder = first
        label = labels.get(reminder.level, f"{reminder.level}. Mahnung")
        candidates.append((day, "mahnung", f"Zugang der {label} {reminder.reminder_number} am {_de(day)}"))
    else:
        notes.append("noch keine Mahnung versendet oder zugestellt")
    customer = invoice_customer(invoice)
    if customer is not None and not customer.is_consumer:
        received = invoice_reached_on(db, invoice)
        due = invoice.due_date or invoice.invoice_date
        if received is None:
            notes.append("Zugang der Rechnung nicht festgehalten (kein Versand, keine Zustellung)")
        else:
            start = max(received, due) + timedelta(days=31)
            candidates.append((start, "dreissig_tage",
                               f"30 Tage nach Fälligkeit ({_de(due)}) und Zugang der Rechnung ({_de(received)}) – Verzug ab dem "
                               f"{_de(start)} (§ 286 Abs. 3 BGB)"))
    elif customer is not None:
        notes.append("Verbraucher: Verzug ohne Mahnung nur mit Hinweis in der Rechnung (§ 286 Abs. 3 BGB) – der ist nicht "
                     "festgehalten")
    if not candidates:
        return {"starts_on": None, "basis": None, "source_text": None,
                "reason": "Kein Vorschlag: " + "; ".join(notes) + "."}
    day, basis, text = min(candidates, key=lambda c: c[0])
    return {"starts_on": day, "basis": basis, "source_text": text, "reason": None}


def default_start_to_dict(row: InvoiceDefaultStart | None) -> dict | None:
    if row is None:
        return None
    return {"id": row.id, "starts_on": row.starts_on, "basis": row.basis, "basis_label": BASIS_LABELS.get(row.basis, row.basis),
            "source_text": row.source_text, "proposal_on": row.proposal_on, "reason": row.reason,
            "created_at": row.created_at, "created_by_name": row.created_by_name}


def _default_start_check(invoice: Invoice) -> None:
    """Nur eine festgeschriebene, nicht stornierte Rechnung (keine Stornorechnung) kann in Verzug sein."""
    number = invoice.invoice_number or "(Entwurf)"
    if invoice.invoice_type == "storno":
        raise ChargeRejected(f"{number} ist eine Stornorechnung – sie kommt nicht in Verzug.")
    if invoice.status == "entwurf":
        raise ChargeRejected("Ein Rechnungsentwurf kommt nicht in Verzug – erst nach dem Finalisieren.")
    if invoice.status != "versendet":
        raise ChargeRejected(f"Die Rechnung {number} ist storniert – sie kommt nicht in Verzug.")


def confirm_default_start(db: Session, invoice: Invoice, *, starts_on: date, reason: str | None,
                          user_id: int | None = None, user_name: str | None = None) -> InvoiceDefaultStart:
    """Verzugsbeginn bestätigen: der Vorschlag (Begründung freiwillig) oder ein anderer Tag mit Begründung. Unter der Sperre der
    Auftragszeile; höchstens einer gilt. Nicht in der Zukunft (bestätigt wird, was eingetreten ist) und nicht vor dem Tag nach
    der Fälligkeit (Verzug setzt sie voraus)."""
    user_id, name = _actor(user_id, user_name)
    lock_order_invoices(db, invoice.order_id)
    try:
        _default_start_check(invoice)
        existing = active_default_start(db, invoice.id)
        if existing is not None:
            raise ChargeRejected(f"Der Verzugsbeginn ist schon bestätigt ({_de(existing.starts_on)}) – zum Ändern erst "
                                 "verwerfen (mit Begründung).")
        if starts_on > berlin_today():
            raise ChargeRejected(f"Der Verzugsbeginn {_de(starts_on)} liegt in der Zukunft – bestätigen lässt er sich ab "
                                 "diesem Tag.")
        if invoice.due_date is not None and starts_on <= invoice.due_date:
            raise ChargeRejected(f"Verzug setzt Fälligkeit voraus – die Rechnung ist am {_de(invoice.due_date)} fällig, "
                                 f"Verzug frühestens ab dem {_de(invoice.due_date + timedelta(days=1))}.")
        proposal = default_start_proposal(db, invoice)
        text = (reason or "").strip() or None
        if proposal["starts_on"] == starts_on:
            basis = proposal["basis"]
        else:
            basis = "von_hand"
            if not text:
                vorschlag = (f"Vorschlag {_de(proposal['starts_on'])}" if proposal["starts_on"] else "ohne Vorschlag")
                raise ValueError(f"Abweichend vom Vorschlag ({vorschlag}) bitte eine Begründung angeben.")
        row = InvoiceDefaultStart(
            invoice_id=invoice.id, starts_on=starts_on, basis=basis,
            source_text=proposal["source_text"] or proposal["reason"], proposal_on=proposal["starts_on"], reason=text,
            created_by_user_id=user_id, created_by_name=name)
        db.add(row)
        db.flush()
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(row)
    return row


def discard_default_start(db: Session, row: InvoiceDefaultStart, *, reason: str | None, user_id: int | None = None,
                          user_name: str | None = None) -> InvoiceDefaultStart:
    """Verzugsbeginn verwerfen (mit Begründung) -- nicht, solange an der Rechnung eine Pauschale oder (seit 1.8.81) Verzugszinsen
    gelten (sie hängen an ihm)."""
    reason = _reason(reason)
    user_id, name = _actor(user_id, user_name)
    invoice = db.get(Invoice, row.invoice_id)
    lock_order_invoices(db, invoice.order_id)
    try:
        db.refresh(row)
        if row.discarded_at is not None:
            raise ChargeRejected("Dieser Verzugsbeginn ist schon verworfen.")
        depending = [c for c in charges_in_force(db, [invoice.id])[invoice.id] if c.kind in ("pauschale", "zinsen")]
        if depending:
            what = " und ".join(dict.fromkeys({"pauschale": "die Pauschale", "zinsen": "Verzugszinsen"}[c.kind]
                                              for c in depending))
            raise ChargeRejected(f"An der Rechnung gelten {what}, die auf diesem Verzugsbeginn beruhen – erst gegenbuchen (mit "
                                 "Begründung), dann den Verzugsbeginn verwerfen.")
        row.discarded_at = datetime.utcnow()
        row.discarded_by_user_id = user_id
        row.discarded_by_name = name
        row.discard_reason = reason
        db.flush()
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Gebühr und Pauschale im Mahnungsentwurf (Nr. 5 und 6)
# ---------------------------------------------------------------------------

def flat_fee_block_reason(db: Session, invoice: Invoice, *, on: date, ignore_reminder_ids: Iterable[int] = ()) -> str | None:
    """Warum die Pauschale zu einer Mahnung vom Tag on nicht möglich ist, sonst None: ausgeschaltet, Kunde ist Verbraucher,
    Verzugsbeginn nicht bestätigt oder nach diesem Tag, schon eine an der Rechnung. ignore_reminder_ids: Mahnungen, die der
    Entwurf ersetzen wird -- ihre Pauschale wird beim Festschreiben gegengebucht, zählt hier also nicht."""
    if not charges_enabled(db):
        return DISABLED_TEXT
    customer = invoice_customer(invoice)
    if customer is None or customer.is_consumer:
        return ("Der Kunde ist Verbraucher – die Pauschale gilt nur gegenüber Kunden, die keine Verbraucher sind "
                "(§ 288 Abs. 5 BGB).")
    start = active_default_start(db, invoice.id)
    if start is None:
        proposal = default_start_proposal(db, invoice)
        hint = (f" Vorschlag: {_de(proposal['starts_on'])} ({proposal['source_text']})." if proposal["starts_on"]
                else f" {proposal['reason']}")
        return f"Der Verzugsbeginn ist nicht bestätigt – die Pauschale gilt erst ab Verzug.{hint}"
    if start.starts_on > on:
        return f"Verzug erst ab dem {_de(start.starts_on)} – die Pauschale ist erst ab dann möglich."
    ignore = set(ignore_reminder_ids)
    flat = [c for c in charges_in_force(db, [invoice.id])[invoice.id] if c.kind == "pauschale" and c.reminder_id not in ignore]
    if flat:
        reminder = db.get(Reminder, flat[0].reminder_id) if flat[0].reminder_id else None
        with_ = f" (mit der Mahnung {reminder.reminder_number})" if reminder is not None else ""
        return f"Die Pauschale ist an dieser Rechnung schon berechnet{with_} – einmal je Rechnung."
    return None


def flat_fee_in_force(db: Session, invoice: Invoice, *, ignore_reminder_ids: Iterable[int] = ()) -> InvoiceCharge | None:
    ignore = set(ignore_reminder_ids)
    return next((c for c in charges_in_force(db, [invoice.id])[invoice.id]
                 if c.kind == "pauschale" and c.reminder_id not in ignore), None)


def fee_block_reason(db: Session, invoice: Invoice, *, flat_fee_accepted: bool,
                     ignore_reminder_ids: Iterable[int] = ()) -> str | None:
    """Seit 1.8.81 ("Vorweg" 1): ist an der Rechnung die Pauschale gebucht -- oder übernimmt dieser Entwurf sie --, schlägt die
    Mahnung keine Gebühr vor und übernimmt keine: sie ist durch die Pauschale abgegolten (§ 288 Abs. 5 S. 3 BGB). Sonst None.
    ignore_reminder_ids: Mahnungen, die der Entwurf ersetzen wird (ihre Pauschale wird gegengebucht)."""
    flat = flat_fee_in_force(db, invoice, ignore_reminder_ids=ignore_reminder_ids)
    if flat is not None:
        reminder = db.get(Reminder, flat.reminder_id) if flat.reminder_id else None
        with_ = f" (mit der Mahnung {reminder.reminder_number})" if reminder is not None else ""
        return f"Keine Mahngebühr – {FEE_ABSORBED}: die Pauschale ist an dieser Rechnung gebucht{with_}."
    if flat_fee_accepted:
        return f"Keine Mahngebühr neben der Pauschale dieser Mahnung – {FEE_ABSORBED}."
    return None


def draft_proposals(db: Session, reminder: Reminder, *, on: date, ignore_reminder_ids: Iterable[int] = ()) -> dict | None:
    """Was der Entwurf vorschlägt (nur eingeschaltet, sonst None): die Gebühr der Stufe -- seit 1.8.81 keine neben einer
    gebuchten oder übernommenen Pauschale (block) --, die Pauschale mit Grund, falls sie nicht möglich ist, und (seit 1.8.81) die
    Verzugszinsen bis zum Tag on (dem Mahndatum, app/default_interest.py::interest_proposal())."""
    if not charges_enabled(db):
        return None
    ignore = list(ignore_reminder_ids)
    level = db.scalar(select(ReminderLevel).where(ReminderLevel.level == reminder.level))
    fee_block = fee_block_reason(db, reminder.invoice, flat_fee_accepted=bool(reminder.flat_fee_accepted),
                                 ignore_reminder_ids=ignore)
    level_fee = round_money(Decimal(level.fee_amount)) if level is not None else ZERO
    from .default_interest import section_text  # lokal: section_text braucht money() von hier

    interest = interest_proposal(db, reminder.invoice, until=on, ignore_reminder_ids=ignore)
    interest["sections"] = [dict(s, text=section_text(s)) for s in interest["sections"]]
    return {
        "fee": {"amount": ZERO if fee_block else level_fee,
                "level_label": level.label if level is not None else f"{reminder.level}. Mahnung", "block": fee_block},
        "flat_fee": {"amount": FLAT_FEE, "block": flat_fee_block_reason(db, reminder.invoice, on=on,
                                                                        ignore_reminder_ids=ignore)},
        "interest": interest,
    }


def new_charge_lines(db: Session, reminder: Reminder, *, enabled: bool, interest: dict | None = None) -> list[dict]:
    """Die im Entwurf übernommenen, beim Festschreiben neu entstehenden Nebenforderungen (Bezeichnung, Betrag). interest: der
    Zinsvorschlag des Entwurfs (seit 1.8.81) -- übernommen und möglich, eine Zeile mit Zeitraum und Abschnitten."""
    from .default_interest import section_text

    if not enabled or reminder.status != "entwurf":
        return []
    lines = []
    if reminder.fee_accepted and Decimal(reminder.fee_amount or 0) > 0:
        labels = _level_labels(db)
        lines.append({"id": None, "kind": "gebuehr", "amount": round_money(Decimal(reminder.fee_amount)), "paid": ZERO,
                      "label": f"Mahngebühr ({labels.get(reminder.level, f'{reminder.level}. Mahnung')})", "sections": []})
    if reminder.flat_fee_accepted:
        lines.append({"id": None, "kind": "pauschale", "amount": FLAT_FEE, "paid": ZERO, "label": KIND_LABELS["pauschale"],
                      "sections": []})
    if reminder.interest_accepted and interest is not None and interest["block"] is None:
        lines.append({"id": None, "kind": "zinsen", "amount": interest["amount"], "paid": ZERO,
                      "label": interest_label(interest["period_start"], interest["period_end"]),
                      "period_start": interest["period_start"], "period_end": interest["period_end"],
                      "surcharge": interest["surcharge"],
                      "sections": [dict(s, text=section_text(s)) for s in interest["sections"]]})
    return lines


def add_charges(db: Session, reminder: Reminder, *, interest: dict | None = None) -> list[InvoiceCharge]:
    """Beim Festschreiben (unter der Sperre der Auftragszeile, ohne Commit): Gebühr, Pauschale und (seit 1.8.81) Verzugszinsen, die
    der Entwurf übernahm, als Nebenforderungen dieser Mahnung. Die Prüfungen macht der Aufrufer vorher (flat_fee_block_reason(),
    fee_block_reason(), interest: der unter der Sperre berechnete Vorschlag ohne block)."""
    user_id, name = _actor(None, None)
    rows = []
    if reminder.fee_accepted and Decimal(reminder.fee_amount or 0) > 0:
        rows.append(InvoiceCharge(invoice_id=reminder.invoice_id, kind="gebuehr", amount=round_money(Decimal(reminder.fee_amount)),
                                  reminder_id=reminder.id, created_by_user_id=user_id, created_by_name=name))
    if reminder.flat_fee_accepted:
        rows.append(InvoiceCharge(invoice_id=reminder.invoice_id, kind="pauschale", amount=FLAT_FEE, reminder_id=reminder.id,
                                  created_by_user_id=user_id, created_by_name=name))
    if reminder.interest_accepted and interest is not None:
        rows.append(InvoiceCharge(invoice_id=reminder.invoice_id, kind="zinsen", amount=interest["amount"],
                                  reminder_id=reminder.id, period_start=interest["period_start"],
                                  period_end=interest["period_end"], calculation_json=calculation_json(interest),
                                  created_by_user_id=user_id, created_by_name=name))
    for row in rows:
        db.add(row)
    db.flush()
    return rows


def invoice_charges_view(db: Session, invoice: Invoice) -> dict:
    """Karte "Nebenforderungen und Verzug" der Rechnungsseite. Seit 1.8.81 offen = geltende Nebenforderungen − Zahlungen darauf,
    dazu Zinszeitraum und Abschnitte je Zins-Nebenforderung."""
    enabled = charges_enabled(db)
    rows = charge_rows(db, invoice)
    start = active_default_start(db, invoice.id)
    return {
        "enabled": enabled, "charges": rows, "open_total": open_charges(db, invoice),
        "paid_total": round_money(sum((r["paid"] for r in rows if not r["reversed"]), ZERO)),
        "default_start": default_start_to_dict(start),
        "default_proposal": default_start_proposal(db, invoice) if invoice.status == "versendet" and start is None else None,
        "today": berlin_today(),
    }
