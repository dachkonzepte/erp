"""Verzugszinsen und Basiszinssatz (seit 1.8.81, Zahlungsstufe Z2b Punkt 7, docs/archiv/zahlungen.md "Umsetzung 1.8.81").

Basiszinssatz (BaseInterestRate): eine Zeile je Halbjahr (ab 1. Januar bzw. 1. Juli, § 247 Abs. 1 S. 2 BGB), nur Admin, mit
"geprüft am/durch". Gezählt wird nur ein geprüfter Satz; fehlt ein Halbjahr im Zinszeitraum oder ist es nicht geprüft, gibt es
keinen Vorschlag -- mit Hinweis, welches.

Zinsen (interest_proposal()), nur als Vorschlag im Mahnungsentwurf bis zum Mahndatum; die Nebenforderung (InvoiceCharge Art
"zinsen") entsteht beim Festschreiben, frisch unter der Sperre der Auftragszeile berechnet (app/reminders.py):
- Zinssatz: Basiszinssatz + 5 Prozentpunkte bei Verbrauchern, sonst + 9 (§ 288 Abs. 1/2 BGB); der Kunde der Rechnung entscheidet.
- Zinsbeginn: der Tag nach dem Zugang der Mahnung (Verzugsbeginn Grundlage "mahnung", § 187 Abs. 1 BGB) bzw. nach einem abweichend
  festgelegten Verzugsbeginn; nach der 30-Tage-Regel der 31. Tag selbst (der Verzugsbeginn "dreissig_tage"). Ohne bestätigten
  Verzugsbeginn keine Zinsen. Schon berechnete Zinsen (geltende Nebenforderungen) schließen an: ab dem Tag nach dem letzten.
- Verzinst wird der mahnfähige Betrag der Rechnung (offen − Einbehalt), abschnittsweise: ein neuer Abschnitt beginnt am
  Eingangstag einer Zahlung (der gezahlte Teil ist ab diesem Tag zinsfrei) und am Beginn eines Halbjahres. Zahlungen auf
  Nebenforderungen mindern den Hauptbetrag nicht (§ 367 BGB, Zinseszins gibt es nicht, § 289 BGB). Seit 1.8.89 (R4c Punkt 5) an
  einer gültigen Endrechnung der angemahnte Betrag: ihr mahnfähiger Betrag plus die offenen Beträge der abgezogenen Rechnungen
  (app/final_dunning.py) -- ein Abschnitt beginnt auch am Eingangstag einer Zahlung auf eine abgezogene Rechnung.
- Tage: tatsächliche Tage, beide Enden eingeschlossen, durch 365. Je Abschnitt exakt (Decimal, ungerundet), einmal am Ende
  kaufmännisch auf den Cent gerundet (app/rounding.py, Regel 19).
Keine Rechtsberatung: jeder Vorschlag nennt seine Teile, entscheiden tut das Büro.
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .berlin_time import berlin_today
from .invoices import invoice_customer
from .models import BaseInterestRate, Invoice, InvoiceDefaultStart, Payment, PaymentAllocation
from .rounding import round_money

SURCHARGE_CONSUMER = Decimal("5")
SURCHARGE_BUSINESS = Decimal("9")
DAYS_PER_YEAR = Decimal(365)
PRINCIPAL_KINDS = ("zahlung", "skonto", "einbehalt")  # was den mahnfähigen Betrag ändert (nicht "nebenforderung")
MAX_RATE = Decimal("100")


def _de(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def percent(value: Decimal) -> str:
    """10.27 -> "10,27 %" (bis zu drei Nachkommastellen, ohne Nullen am Ende)."""
    text = f"{Decimal(value):.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") + " %"


# ---------------------------------------------------------------------------
# Halbjahre und Basiszinssatz
# ---------------------------------------------------------------------------

def half_year_of(day: date) -> date:
    return date(day.year, 1 if day.month <= 6 else 7, 1)


def half_year_end(start: date) -> date:
    return date(start.year, 6, 30) if start.month == 1 else date(start.year, 12, 31)


def next_half_year(start: date) -> date:
    return date(start.year, 7, 1) if start.month == 1 else date(start.year + 1, 1, 1)


def half_year_label(start: date) -> str:
    return f"{_de(start)}–{_de(half_year_end(start))}"


def rate_is_reviewed(row: BaseInterestRate | None) -> bool:
    return bool(row is not None and row.reviewed_on is not None and (row.reviewed_by or "").strip())


def rate_to_dict(row: BaseInterestRate) -> dict:
    return {"id": row.id, "half_year_start": row.half_year_start, "half_year_end": half_year_end(row.half_year_start),
            "rate_percent": row.rate_percent, "reviewed_on": row.reviewed_on, "reviewed_by": row.reviewed_by,
            "reviewed": rate_is_reviewed(row), "updated_at": row.updated_at, "updated_by_name": row.updated_by_name}


def list_rates(db: Session) -> list[dict]:
    """Alle Sätze, jüngstes Halbjahr zuerst, mit dem Halbjahr, das als Nächstes fehlt (für die Einstellungen)."""
    return [rate_to_dict(r) for r in db.scalars(select(BaseInterestRate).order_by(BaseInterestRate.half_year_start.desc()))]


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _rate_value(value) -> Decimal:
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Der Basiszinssatz ist keine Zahl.") from None
    if not rate.is_finite() or abs(rate) >= MAX_RATE or -rate.normalize().as_tuple().exponent > 3:
        raise ValueError("Der Basiszinssatz in Prozent: höchstens drei Nachkommastellen, zwischen −100 und 100.")
    return rate


def _review(reviewed_on: date | None, reviewed_by: str | None) -> tuple[date | None, str | None]:
    by = _clean(reviewed_by)
    if (reviewed_on is None) != (by is None):
        raise ValueError("„Geprüft am“ und „durch“ bitte gemeinsam angeben oder beide leer lassen.")
    if reviewed_on is not None and reviewed_on > berlin_today():
        raise ValueError("„Geprüft am“ darf nicht in der Zukunft liegen.")
    return reviewed_on, by


class RateConflict(ValueError):
    """Für das Halbjahr gibt es schon einen Satz, ein geprüfter wird nicht gelöscht -- Router: 409."""


def create_rate(db: Session, *, half_year_start: date, rate_percent, reviewed_on: date | None, reviewed_by: str | None,
                actor_name: str = "System") -> BaseInterestRate:
    """Neuer Satz für ein Halbjahr (1. Januar oder 1. Juli); höchstens einer je Halbjahr (UNIQUE)."""
    if (half_year_start.month, half_year_start.day) not in ((1, 1), (7, 1)):
        raise ValueError("Der Basiszinssatz gilt je Halbjahr – „gültig ab“ ist der 1. Januar oder der 1. Juli "
                         "(§ 247 Abs. 1 S. 2 BGB).")
    rate = _rate_value(rate_percent)
    reviewed_on, by = _review(reviewed_on, reviewed_by)
    row = BaseInterestRate(half_year_start=half_year_start, rate_percent=rate, reviewed_on=reviewed_on, reviewed_by=by,
                           updated_by_name=actor_name or "System", updated_at=datetime.utcnow())
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        db.rollback()
        raise RateConflict(f"Für das Halbjahr ab {_de(half_year_start)} gibt es schon einen Basiszinssatz – bitte diesen "
                           "ändern.") from None
    db.commit()
    db.refresh(row)
    return row


def update_rate(db: Session, row: BaseInterestRate, *, rate_percent, reviewed_on: date | None, reviewed_by: str | None,
                actor_name: str = "System") -> tuple[BaseInterestRate, bool]:
    """Satz und Prüfangaben ändern. Ändert sich der Satz und kommen dieselben Prüfangaben wie bisher mit (die Prüfung galt dem
    alten Satz), fallen sie weg -- review_reset True (wie bei den Klauseln, app/contract_basis.py::update_clause())."""
    rate = _rate_value(rate_percent)
    reviewed_on, by = _review(reviewed_on, reviewed_by)
    review_reset = False
    if rate != Decimal(row.rate_percent) and reviewed_on is not None and reviewed_on == row.reviewed_on \
            and by == row.reviewed_by:
        reviewed_on, by = None, None
        review_reset = True
    row.rate_percent, row.reviewed_on, row.reviewed_by = rate, reviewed_on, by
    row.updated_by_name, row.updated_at = actor_name or "System", datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row, review_reset


def delete_rate(db: Session, row: BaseInterestRate) -> None:
    """Nur ein ungeprüfter Satz lässt sich löschen (Tippfehler); ein geprüfter wird geändert und neu geprüft."""
    if rate_is_reviewed(row):
        raise RateConflict("Ein geprüfter Basiszinssatz wird nicht gelöscht – bei einem Fehler den Satz ändern und neu prüfen.")
    db.delete(row)
    db.commit()


def _rates(db: Session, starts: Iterable[date]) -> dict[date, BaseInterestRate]:
    starts = sorted(set(starts))
    if not starts:
        return {}
    rows = db.scalars(select(BaseInterestRate).where(BaseInterestRate.half_year_start.in_(starts)))
    return {r.half_year_start: r for r in rows}


def _half_years(first: date, last: date) -> list[date]:
    result, hy = [], half_year_of(first)
    while hy <= last:
        result.append(hy)
        hy = next_half_year(hy)
    return result


def rate_gap_reason(db: Session, first: date, last: date) -> str | None:
    """Warum es für die Tage first bis last keinen Zinsvorschlag gibt (Halbjahr ohne bzw. mit ungeprüftem Satz), sonst None."""
    halves = _half_years(first, last)
    rates = _rates(db, halves)
    missing = [hy for hy in halves if hy not in rates]
    unchecked = [hy for hy in halves if hy in rates and not rate_is_reviewed(rates[hy])]
    parts = []
    if missing:
        parts.append("kein Basiszinssatz für " + ", ".join(f"das Halbjahr {half_year_label(hy)}" for hy in missing))
    if unchecked:
        parts.append("nicht geprüft: " + ", ".join(f"das Halbjahr {half_year_label(hy)}" for hy in unchecked))
    if not parts:
        return None
    return ("Kein Zinsvorschlag – " + "; ".join(parts) + " (Einstellungen → Mahnstufen → Basiszinssatz, nur Administratoren).")


# ---------------------------------------------------------------------------
# Zinsen
# ---------------------------------------------------------------------------

def surcharge_for(invoice: Invoice) -> Decimal:
    """5 Prozentpunkte bei Verbrauchern, sonst 9 (§ 288 Abs. 1/2 BGB) -- der festgehaltene Kunde der Rechnung entscheidet."""
    customer = invoice_customer(invoice)
    return SURCHARGE_BUSINESS if customer is not None and customer.is_consumer is False else SURCHARGE_CONSUMER


def interest_start_day(start: InvoiceDefaultStart) -> date:
    """Erster Zinstag: nach der 30-Tage-Regel der Verzugsbeginn selbst (der 31. Tag); sonst -- Zugang der Mahnung, abweichend
    festgelegter Tag -- der Tag danach (§ 187 Abs. 1 BGB)."""
    return start.starts_on if start.basis == "dreissig_tage" else start.starts_on + timedelta(days=1)


def _principal_change_days(db: Session, invoice: Invoice, first: date, last: date) -> set[date]:
    """Eingangstage der Zahlungen mit Buchungen am Hauptbetrag der Rechnung (Zahlung, Skonto, Einbehalt) zwischen first
    (ausgeschlossen) und last -- an diesen Tagen kann sich der verzinste Betrag ändern. Seit 1.8.89 an der Endrechnung auch die
    Buchungen an ihren abgezogenen Rechnungen."""
    from .final_dunning import principal_invoice_ids  # lokal: app/final_dunning.py importiert app/invoices.py

    rows = db.scalars(
        select(Payment.received_on).join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
        .where(PaymentAllocation.invoice_id.in_(principal_invoice_ids(db, invoice)),
               PaymentAllocation.kind.in_(PRINCIPAL_KINDS), Payment.received_on > first, Payment.received_on <= last).distinct())
    return set(rows)


def _principal_on(db: Session, invoice: Invoice, day: date) -> Decimal:
    """Der verzinste Betrag an diesem Tag: der angemahnte Betrag (seit 1.8.89, app/final_dunning.py -- an der Endrechnung samt den
    offenen abgezogenen Rechnungen; vorher der mahnfähige Betrag der Rechnung)."""
    from .final_dunning import dunning_state  # lokal: Zirkel-Import

    return dunning_state(db, invoice, on=day).dunnable


def last_interest_end(db: Session, invoice: Invoice, *, ignore_reminder_ids: Iterable[int] = ()) -> date | None:
    """Bis wann Zinsen schon berechnet sind: das späteste Ende einer geltenden Zins-Nebenforderung (ohne die der Mahnungen, die ein
    Entwurf ersetzen wird)."""
    from .dunning_charges import charges_in_force  # lokal: app/dunning_charges.py importiert dieses Modul

    ignore = set(ignore_reminder_ids)
    ends = [c.period_end for c in charges_in_force(db, [invoice.id])[invoice.id]
            if c.kind == "zinsen" and c.period_end is not None and c.reminder_id not in ignore]
    return max(ends) if ends else None


def _blocked(reason: str, **extra) -> dict:
    return {"amount": None, "period_start": None, "period_end": None, "surcharge": None, "sections": [], "block": reason,
            **extra}


def interest_proposal(db: Session, invoice: Invoice, *, until: date, ignore_reminder_ids: Iterable[int] = ()) -> dict:
    """Vorschlag der Verzugszinsen bis zum Tag until (dem Mahndatum): {"amount", "period_start", "period_end", "surcharge",
    "sections", "block"} -- block nennt den Grund, wenn es keinen gibt (dann amount None). sections: je Abschnitt "from", "to",
    "principal", "base_rate", "rate", "days", "interest" (exakt). Liest nur."""
    from .dunning_charges import active_default_start  # lokal: Zirkel-Import

    start = active_default_start(db, invoice.id)
    if start is None:
        return _blocked("Der Verzugsbeginn ist nicht bestätigt – Zinsen laufen erst ab Verzug (Rechnungsseite, Karte "
                        "„Nebenforderungen und Verzug“).")
    first = interest_start_day(start)
    last = last_interest_end(db, invoice, ignore_reminder_ids=ignore_reminder_ids)
    from_ = max(first, last + timedelta(days=1)) if last is not None else first
    if from_ > until:
        if last is not None and last >= until:
            return _blocked(f"Zinsen sind bis zum {_de(last)} schon berechnet.")
        return _blocked(f"Zinsen laufen erst ab dem {_de(from_)}.")
    gap = rate_gap_reason(db, from_, until)
    if gap:
        return _blocked(gap)
    surcharge = surcharge_for(invoice)
    rates = _rates(db, _half_years(from_, until))
    cuts = {from_} | _principal_change_days(db, invoice, from_, until)
    cuts |= {hy for hy in _half_years(from_, until) if from_ < hy <= until}
    cuts = sorted(cuts)
    sections: list[dict] = []
    for i, s in enumerate(cuts):
        e = cuts[i + 1] - timedelta(days=1) if i + 1 < len(cuts) else until
        principal = _principal_on(db, invoice, s)
        base = Decimal(rates[half_year_of(s)].rate_percent)
        if sections and sections[-1]["principal"] == principal and sections[-1]["base_rate"] == base:
            sections[-1]["to"] = e
            continue
        sections.append({"from": s, "to": e, "principal": principal, "base_rate": base})
    result = []
    for sec in sections:
        if sec["principal"] <= 0:
            continue
        days = (sec["to"] - sec["from"]).days + 1
        rate = sec["base_rate"] + surcharge
        interest = sec["principal"] * rate * days / (Decimal(100) * DAYS_PER_YEAR)
        result.append({**sec, "rate": rate, "days": days, "interest": interest})
    total = round_money(sum((s["interest"] for s in result), Decimal("0")))
    if total <= 0:
        return _blocked(f"Vom {_de(from_)} bis zum {_de(until)} ist kein verzinslicher Betrag offen – keine Zinsen.")
    return {"amount": total, "period_start": from_, "period_end": until, "surcharge": surcharge, "sections": result,
            "block": None, "first_day": first, "continues_from": last}


def interest_label(period_start: date | None, period_end: date | None) -> str:
    if period_start is None or period_end is None:
        return "Verzugszinsen"
    return f"Verzugszinsen vom {_de(period_start)} bis {_de(period_end)}"


def section_text(sec: dict) -> str:
    """"01.03.2026–30.06.2026: 1.000,00 € zu 10,27 % (Basiszinssatz 1,27 % + 9 Prozentpunkte), 122 Tage"."""
    from .dunning_charges import money  # lokal: Zirkel-Import

    surcharge = Decimal(sec["rate"]) - Decimal(sec["base_rate"])
    return (f"{_de(sec['from'])}–{_de(sec['to'])}: {money(Decimal(sec['principal']))} zu {percent(Decimal(sec['rate']))} "
            f"(Basiszinssatz {percent(Decimal(sec['base_rate']))} + {surcharge.normalize():f} Prozentpunkte), "
            f"{sec['days']} {'Tag' if sec['days'] == 1 else 'Tage'}")


def calculation_json(proposal: dict) -> str:
    """Die Berechnung zum Einfrieren an der Nebenforderung: kanonisches JSON, Beträge als Text (exakt)."""
    data = {
        "days_per_year": 365, "surcharge": str(proposal["surcharge"]),
        "period_start": proposal["period_start"].isoformat(), "period_end": proposal["period_end"].isoformat(),
        "amount": str(proposal["amount"]),
        "sections": [{"from": s["from"].isoformat(), "to": s["to"].isoformat(), "principal": str(s["principal"]),
                      "base_rate": str(s["base_rate"]), "rate": str(s["rate"]), "days": s["days"],
                      "interest": str(s["interest"])} for s in proposal["sections"]],
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sections_of(calculation: str | None) -> list[dict]:
    """Die eingefrorenen Abschnitte einer Zins-Nebenforderung (Daten als date, Beträge als Decimal)."""
    if not calculation:
        return []
    raw = json.loads(calculation)
    return [{"from": date.fromisoformat(s["from"]), "to": date.fromisoformat(s["to"]), "principal": Decimal(s["principal"]),
             "base_rate": Decimal(s["base_rate"]), "rate": Decimal(s["rate"]), "days": int(s["days"]),
             "interest": Decimal(s["interest"])} for s in raw.get("sections", [])]


def recalculated(db: Session, invoice: Invoice, charge) -> Decimal | None:
    """Die Zinsen einer gebuchten Zins-Nebenforderung, neu berechnet für ihren Zeitraum mit dem Stand heute (z. B. nach einer
    später gebuchten Zahlung mit früherem Eingang) -- nur zum Hinweis, nichts wird geändert. None, wenn das nicht geht."""
    secs = sections_of(charge.calculation_json)
    if not secs or charge.period_start is None or charge.period_end is None:
        return None
    raw = json.loads(charge.calculation_json)
    surcharge = Decimal(raw["surcharge"])
    bases = {}
    for s in secs:
        bases.setdefault(half_year_of(s["from"]), s["base_rate"])
    cuts = {charge.period_start} | _principal_change_days(db, invoice, charge.period_start, charge.period_end)
    cuts |= {hy for hy in _half_years(charge.period_start, charge.period_end) if charge.period_start < hy <= charge.period_end}
    cuts = sorted(cuts)
    total = Decimal("0")
    for i, s in enumerate(cuts):
        e = cuts[i + 1] - timedelta(days=1) if i + 1 < len(cuts) else charge.period_end
        base = bases.get(half_year_of(s))
        if base is None:
            return None
        principal = _principal_on(db, invoice, s)
        if principal > 0:
            total += principal * (base + surcharge) * ((e - s).days + 1) / (Decimal(100) * DAYS_PER_YEAR)
    return round_money(total)
