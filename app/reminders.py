"""Mahnwesen (seit 1.0.53).

Baut auf dem bestehenden Rechnungswesen auf: eine Mahnung bezieht sich auf
genau eine bereits versendete, überfällige Rechnung (Invoice, siehe
app/invoices.py). Bewusst ohne eigene Positionsliste -- eine Mahnung stellt
den offenen Rechnungsbetrag zuzüglich einer Mahngebühr der jeweiligen Stufe
dar, keine eigene Leistungsabrechnung.

Mahnstufen (ReminderLevel) sind admin-konfigurierbar, siehe
ensure_default_reminder_levels() für die drei Standardstufen. Jede Stufe
lässt sich einzeln über `active` deaktivieren, damit ein Betrieb frei wählen
kann, wie viele Stufen er tatsächlich nutzt.

Nummernvergabe wie bei Rechnungen: reminder_number bleibt NULL, solange
status='entwurf', wird erst bei finalize_and_send_reminder() vergeben.

Seit 1.8.78 (Zahlungsstufe Z1, app/payments.py): gemahnt wird der mahnfähige Betrag (offen − Einbehalt) statt des Bruttos;
ohne mahnfähigen Betrag (bezahlt, nur noch Einbehalt offen, Stornorechnung) entsteht und geht keine Mahnung.

Seit 1.8.79 (Zahlungsstufe Z2a, docs/archiv/zahlungen.md):
- Kein Entwurf entsteht von selbst (bis 1.8.78 legte das Öffnen des Mahnwesens Entwürfe an). Die Liste "zur Mahnung fällig"
  (list_invoices_needing_attention()) liest nur; Entwürfe entstehen per Klick, einzeln (create_reminder()) oder für mehrere
  (create_reminders()).
- Je Stufe eine Zahl, die Zahlungsfrist in Tagen ab dem Mahndatum (ReminderLevel.days_after_previous_step). Die erste Stufe ist
  ab dem Tag nach der Fälligkeit der Rechnung möglich, jede weitere ab dem Tag nach dem Ende der Frist der vorigen; nur die
  nächste aktive Stufe, höchstens ein Entwurf je Rechnung. Geprüft beim Anlegen und noch einmal beim Festschreiben, unter der
  Sperre der Auftragszeile (create_block_reason()): keine Mahnung zu einer Stornorechnung, einer stornierten, einer nicht
  fälligen oder einer nicht mahnfähigen Rechnung.
- Bearbeiten und Löschen eines Entwurfs unter derselben Sperre. Mahndatum = Tag des Festschreibens (Berlin), die Frist rechnet ab
  dann (im Entwurf trägt sie nur ihre Länge in Tagen, finalize_dates()).
- Die Mahnung zeigt Brutto, Zahlungen, Skonto, Einbehalt und den mahnfähigen Betrag (Reminder.amounts_json, amounts()).
- Eine festgeschriebene Mahnung geht per E-Mail und als nachgetragene Zustellung nur hinaus, solange ihr Betrag dem mahnfähigen
  entspricht und die Rechnung nicht storniert ist (dispatch_block_reason()) -- sonst 409 mit Hinweis auf eine neue Mahnung.
"""

import json
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session, selectinload

from .berlin_time import berlin_today
from .invoices import InvoiceBlocked, invoice_customer, invoice_rounding, lock_order_invoices
from .models import Invoice, Reminder, ReminderLevel
from .placeholders import apply_placeholders
from .rounding import CENT
from .settings import issue_number

FINALIZED = "versendet"
_UNSET = object()


def _de(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _money(x: Decimal) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def reminder_total(reminder: Reminder) -> Decimal:
    """Offener Betrag + Mahngebühr, auf den Cent nach der Rundungsregel der Rechnung (seit
    1.8.11, app/invoices.py::invoice_rounding()): kaufmännisch bei Rechnungen ab 1.8.11,
    halb-gerade wie bisher bei vorher versendeten -- deren offener Betrag ist ungerundet
    gespeichert, und eine versendete Mahnung soll beim Nachdruck denselben Gesamtbetrag zeigen."""
    return (reminder.outstanding_amount + reminder.fee_amount).quantize(CENT, rounding=invoice_rounding(reminder.invoice))


def reminder_amount(reminder: Reminder) -> Decimal:
    """Der gemahnte Betrag auf den Cent (wie reminder_total() ohne Gebühr) -- für den Vergleich mit dem mahnfähigen Betrag."""
    return reminder.outstanding_amount.quantize(CENT, rounding=invoice_rounding(reminder.invoice))


DEFAULT_REMINDER_LEVELS = [
    # (level, label, days_after_previous_step = Zahlungsfrist in Tagen seit 1.8.79, fee_amount, text_template)
    (
        1, "1. Mahnung", 7, Decimal("5.00"),
        "Trotz Fälligkeit am {faelligkeitsdatum} konnten wir bis heute keinen Zahlungseingang zu "
        "Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Bitte begleichen Sie den "
        "offenen Betrag von {offener_betrag} zuzüglich einer Mahngebühr von {mahngebuehr}, "
        "insgesamt {gesamtbetrag}, bis zum {neue_frist}. Sollte Ihre Zahlung bereits erfolgt sein, "
        "betrachten Sie dieses Schreiben bitte als gegenstandslos.",
    ),
    (
        2, "2. Mahnung", 7, Decimal("10.00"),
        "Leider konnten wir trotz unserer Zahlungserinnerung vom {vorheriges_mahndatum} bis heute "
        "keinen Zahlungseingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Wir "
        "bitten Sie letztmalig, den offenen Betrag von {offener_betrag} zuzüglich einer Mahngebühr "
        "von {mahngebuehr}, insgesamt {gesamtbetrag}, bis zum {neue_frist} zu begleichen.",
    ),
    (
        3, "3. Mahnung", 7, Decimal("15.00"),
        "Auch nach unserer 2. Mahnung vom {vorheriges_mahndatum} ist Rechnung {rechnungsnummer} vom "
        "{rechnungsdatum} weiterhin nicht ausgeglichen. Wir bitten Sie letztmalig um Zahlung des "
        "offenen Betrags von {offener_betrag} zuzüglich einer Mahngebühr von {mahngebuehr}, "
        "insgesamt {gesamtbetrag}, bis zum {neue_frist}. Nach fruchtlosem Ablauf dieser Frist "
        "behalten wir uns weitere rechtliche Schritte vor.",
    ),
]


def ensure_default_reminder_levels(db: Session) -> None:
    """Legt beim ersten Aufruf (leere Tabelle) die drei Standardstufen an.
    Rührt bestehende Stufen nicht an. Die vorgeschlagenen Fristen, Gebühren
    und Texte sind ein Startpunkt, keine Rechtsberatung -- insbesondere die
    Höhe zulässiger Mahngebühren und der genaue Wortlaut bitte vor
    Verwendung mit einem Steuerberater/Rechtsanwalt abgleichen.
    Anlegeschritt von app.grunddaten.anlegen() (seit 1.8.42): flush, kein commit -- ein Commit gäbe dort
    die Sperre frei. Lesepfade rufen das nicht mehr auf."""
    if db.scalar(select(ReminderLevel.id).limit(1)) is not None:
        return
    for level, label, days, fee, text in DEFAULT_REMINDER_LEVELS:
        db.add(ReminderLevel(
            level=level, label=label, days_after_previous_step=days,
            fee_amount=fee, text_template=text, active=True, sort_order=level * 10,
        ))
    db.flush()


def list_reminder_levels(db: Session) -> list[ReminderLevel]:
    return db.scalars(select(ReminderLevel).order_by(ReminderLevel.sort_order, ReminderLevel.level)).all()


def update_reminder_level(
    db: Session, level_row: ReminderLevel, *, label: str, days_after_previous_step: int,
    fee_amount: Decimal, text_template: str | None, active: bool,
    email_subject_template: str | None = None, email_body_template: str | None = None,
) -> ReminderLevel:
    level_row.label = label
    level_row.days_after_previous_step = days_after_previous_step
    level_row.fee_amount = fee_amount
    level_row.text_template = text_template
    level_row.email_subject_template = email_subject_template
    level_row.email_body_template = email_body_template
    level_row.active = active
    db.commit()
    db.refresh(level_row)
    return level_row


# ---------------------------------------------------------------------------
# Stufen und Fristen (seit 1.8.79)
# ---------------------------------------------------------------------------

def _levels(db: Session) -> dict[int, ReminderLevel]:
    """Alle Stufen nach Nummer (auch inaktive -- für Bezeichnung und Frist einer schon festgeschriebenen Mahnung)."""
    return {lvl.level: lvl for lvl in db.scalars(select(ReminderLevel))}


def _label(levels: dict[int, ReminderLevel], level: int) -> str:
    cfg = levels.get(level)
    return cfg.label if cfg is not None else f"{level}. Mahnung"


def deadline_of(reminder: Reminder, levels: dict[int, ReminderLevel]) -> date:
    """Ende der Frist einer festgeschriebenen Mahnung: ihre neue Frist; fehlt sie (Altbestand, bis 1.8.78 im Entwurf leerbar),
    Mahndatum + Zahlungsfrist ihrer Stufe."""
    if reminder.new_due_date is not None:
        return reminder.new_due_date
    cfg = levels.get(reminder.level)
    return reminder.reminder_date + timedelta(days=cfg.days_after_previous_step if cfg is not None else 0)


def payment_days(reminder: Reminder, levels: dict[int, ReminderLevel]) -> int:
    """Zahlungsfrist eines Entwurfs in Tagen: der Abstand von Frist und Mahndatum; fehlt die Frist (Altbestand), die Tage
    seiner Stufe."""
    if reminder.new_due_date is not None and reminder.reminder_date is not None:
        days = (reminder.new_due_date - reminder.reminder_date).days
        if days >= 1:
            return days
    cfg = levels.get(reminder.level)
    return cfg.days_after_previous_step if cfg is not None else 7


def finalize_dates(reminder: Reminder, levels: dict[int, ReminderLevel], today: date) -> tuple[date, date]:
    """(Mahndatum, Frist) beim Festschreiben an diesem Tag: das Mahndatum ist der Tag des Festschreibens, die Frist behält die
    Länge aus dem Entwurf und rechnet ab dann (Vorgabe Z2a Nr. 3, wie app/invoices.py::finalize_dates())."""
    return today, today + timedelta(days=payment_days(reminder, levels))


def effective_dates(reminder: Reminder, levels: dict[int, ReminderLevel] | None = None) -> tuple[date, date | None]:
    """Mahndatum und Frist, wie Text und PDF sie zeigen: festgeschrieben die gespeicherten, im Entwurf die des Festschreibens
    heute (dieselben Werte, die finalize_and_send_reminder() setzen würde)."""
    if reminder.status != "entwurf":
        return reminder.reminder_date, reminder.new_due_date
    if levels is None:
        db = object_session(reminder)
        levels = _levels(db) if db is not None else {}
    return finalize_dates(reminder, levels, berlin_today())


def _sent(invoice: Invoice) -> list[Reminder]:
    return [r for r in invoice.reminders if r.status == FINALIZED]


def _step(invoice: Invoice, levels: dict[int, ReminderLevel]) -> dict:
    """Aktuelle Stufe (höchste festgeschriebene), ihre letzte Mahnung, nächste aktive Stufe und ab wann sie möglich ist."""
    sent = _sent(invoice)
    current = max((r.level for r in sent), default=0)
    last = max((r for r in sent if r.level == current), key=lambda r: (r.reminder_date, r.id)) if current else None
    next_level = min((lvl for lvl, cfg in levels.items() if cfg.active and lvl > current), default=None)
    if invoice.due_date is None:
        next_due_on = None
    elif last is None:
        next_due_on = invoice.due_date + timedelta(days=1)
    else:
        next_due_on = deadline_of(last, levels) + timedelta(days=1)
    return {"current_level": current, "last": last, "next_level": next_level, "next_due_on": next_due_on}


def _amount_reason(db: Session, invoice: Invoice, state) -> str | None:
    """Warum zur Rechnung nichts zu mahnen ist (Entwurf, storniert, Storno, bezahlt, nur Einbehalt, 0 €), sonst None."""
    from .payments import dunning_block_reason, not_payable_reason  # lokal: app/payments.py importiert app/invoices.py
    number = invoice.invoice_number or "(Entwurf)"
    if invoice.status == "entwurf":
        return "Nur zu festgeschriebenen Rechnungen entsteht eine Mahnung."
    if invoice.status == "storniert":
        return f"Die Rechnung {number} ist storniert -- dazu geht keine Mahnung mehr hinaus."
    reason = dunning_block_reason(db, invoice, state)
    if reason:
        return reason
    if state is None or state.dunnable <= 0:
        return not_payable_reason(invoice) or f"Die Rechnung {number} hat keinen mahnfähigen Betrag."
    return None


def create_block_reason(db: Session, invoice: Invoice, *, state=_UNSET, levels: dict[int, ReminderLevel] | None = None,
                        level: int | None = None, draft: Reminder | None = None) -> str | None:
    """Warum zu dieser Rechnung jetzt keine Mahnung entsteht (Vorgabe Z2a Nr. 2), sonst None -- beim Anlegen (level: die
    verlangte Stufe, None = die nächste) und beim Festschreiben (draft: dieser Entwurf, seine Stufe muss die nächste sein).
    Reihenfolge: nichts zu mahnen (Storno, storniert, bezahlt, nur Einbehalt), nicht fällig, schon ein Entwurf, keine weitere
    Stufe, nicht die nächste Stufe, Frist der vorigen noch nicht abgelaufen."""
    from .payments import payment_state  # lokal: Zirkel-Import
    if state is _UNSET:
        state = payment_state(db, invoice)
    if levels is None:
        levels = _levels(db)
    reason = _amount_reason(db, invoice, state)
    if reason:
        return reason
    today = berlin_today()
    number = invoice.invoice_number or "(Entwurf)"
    if invoice.due_date is None:
        return f"Die Rechnung {number} hat keine Fälligkeit -- dazu entsteht keine Mahnung."
    if invoice.due_date >= today:
        return (f"Die Rechnung {number} ist erst am {_de(invoice.due_date)} fällig -- gemahnt werden kann ab dem "
                f"{_de(invoice.due_date + timedelta(days=1))}.")
    # Höchstens ein Entwurf je Rechnung -- beim Anlegen. Beim Festschreiben zählt ein zweiter (Altbestand bis 1.8.78) nicht: er
    # ist danach überholt (nicht mehr die nächste Stufe) und lässt sich nur noch löschen.
    other = next((r for r in invoice.reminders if r.status == "entwurf"), None) if draft is None else None
    if other is not None:
        return (f"Zu dieser Rechnung besteht schon ein Mahnungsentwurf ({_label(levels, other.level)}) -- erst festschreiben "
                "oder löschen.")
    step = _step(invoice, levels)
    if step["next_level"] is None:
        if step["last"] is None:
            return "Keine Mahnstufe ist aktiv (Einstellungen → Mahnstufen)."
        return (f"Keine weitere Mahnstufe ist aktiv -- zuletzt {_label(levels, step['current_level'])} "
                f"{step['last'].reminder_number or ''}".rstrip() + ".")
    wanted = draft.level if draft is not None else level
    if wanted is not None and wanted != step["next_level"]:
        if draft is not None:
            return (f"Der Entwurf ({_label(levels, draft.level)}) ist überholt: als Nächstes ist die "
                    f"{_label(levels, step['next_level'])} möglich. Bitte den Entwurf löschen und neu anlegen.")
        return f"Nur die nächste Stufe ist möglich: {_label(levels, step['next_level'])}."
    if today < step["next_due_on"]:
        last = step["last"]
        return (f"Die {_label(levels, step['next_level'])} ist erst ab dem {_de(step['next_due_on'])} möglich -- die Frist der "
                f"{_label(levels, last.level)} {last.reminder_number or ''} läuft bis zum {_de(deadline_of(last, levels))}.")
    return None


def compute_reminder_status(db: Session, invoice: Invoice, *, state=_UNSET,
                            levels: dict[int, ReminderLevel] | None = None) -> dict:
    """Auf welcher Mahnstufe die Rechnung steht, welche aktive Stufe als Nächstes kommt und ab wann (seit 1.8.79: ab dem Tag
    nach der Fälligkeit bzw. nach dem Ende der Frist der vorigen Mahnung). Deaktivierte Stufen werden übersprungen.

    draft: der bestehende Entwurf (reminder_to_dict()) oder None; create_block (seit 1.8.79): warum jetzt kein Entwurf
    entsteht -- die Oberfläche zeigt den Grund statt des Knopfs."""
    from .payments import payment_state  # lokal: Zirkel-Import
    if state is _UNSET:
        state = payment_state(db, invoice)
    if levels is None:
        levels = _levels(db)
    block = create_block_reason(db, invoice, state=state, levels=levels)
    draft = next((r for r in invoice.reminders if r.status == "entwurf"), None)
    if invoice.status != FINALIZED or invoice.due_date is None or state is None or state.dunnable <= 0:
        return {"current_level": 0, "next_level": None, "next_due_on": None, "is_due_now": False,
                "draft": reminder_to_dict(draft, state=state, levels=levels) if draft is not None else None,
                "create_block": block}
    step = _step(invoice, levels)
    is_due_now = step["next_level"] is not None and berlin_today() >= step["next_due_on"]
    return {
        "current_level": step["current_level"], "next_level": step["next_level"],
        "next_due_on": step["next_due_on"] if step["next_level"] is not None else None, "is_due_now": is_due_now,
        "draft": reminder_to_dict(draft, state=state, levels=levels) if draft is not None else None,
        "create_block": block,
    }


# ---------------------------------------------------------------------------
# Aufstellung des gemahnten Betrags (seit 1.8.79, Vorgabe Z2a Nr. 4)
# ---------------------------------------------------------------------------

def amounts_snapshot(db: Session, invoice: Invoice, state) -> str:
    """Aufstellung aus dem Zahlstand als kanonisches JSON: Brutto, je noch geltender Zahlung Eingangsdatum und Betrag, Skonto,
    Einbehalt (der abgezogene Teil, höchstens der offene Betrag), mahnfähig. Brutto − Zahlungen − Skonto − Einbehalt =
    mahnfähig."""
    from .payments import invoice_payment_lines  # lokal: Zirkel-Import
    data = {
        "format": 1, "gross": str(state.gross),
        "payments": [{"received_on": d.isoformat(), "amount": str(a)} for d, a in invoice_payment_lines(db, invoice)],
        "skonto": str(state.skonto), "retained": str(state.retained_open), "dunnable": str(state.dunnable),
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def amounts(reminder: Reminder) -> dict | None:
    """Die Aufstellung der Mahnung (Beträge als Decimal, Daten als date), None bei Mahnungen von vor 1.8.79."""
    if not reminder.amounts_json:
        return None
    raw = json.loads(reminder.amounts_json)
    return {
        "gross": Decimal(raw["gross"]),
        "payments": [{"received_on": date.fromisoformat(p["received_on"]), "amount": Decimal(p["amount"])}
                     for p in raw["payments"]],
        "skonto": Decimal(raw["skonto"]), "retained": Decimal(raw["retained"]), "dunnable": Decimal(raw["dunnable"]),
    }


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def _reminder_placeholders(reminder: Reminder) -> dict:
    """Gemeinsame Platzhalter-Werte für PDF-Text UND E-Mail-Betreff/-Text
    (seit 1.0.74, vorher nur für format_reminder_text() intern). Seit 1.8.79 im Entwurf mit Mahndatum und Frist des
    Festschreibens heute (effective_dates())."""
    invoice = reminder.invoice
    total = reminder_total(reminder)
    previous = [r for r in invoice.reminders if r.status == FINALIZED and r.level == reminder.level - 1]
    previous_date = previous[0].reminder_date.strftime("%d.%m.%Y") if previous else ""
    _, new_due_date = effective_dates(reminder)
    return {
        "{rechnungsnummer}": invoice.invoice_number or "",
        "{rechnungsdatum}": invoice.invoice_date.strftime("%d.%m.%Y"),
        "{faelligkeitsdatum}": invoice.due_date.strftime("%d.%m.%Y") if invoice.due_date else "",
        "{offener_betrag}": _money(reminder.outstanding_amount),
        "{mahngebuehr}": _money(reminder.fee_amount),
        "{gesamtbetrag}": _money(total),
        "{neue_frist}": new_due_date.strftime("%d.%m.%Y") if new_due_date else "",
        "{vorheriges_mahndatum}": previous_date,
    }


def format_reminder_text(reminder: Reminder) -> str:
    """Ersetzt Platzhalter in reminder.text mit den echten Werten -- analog
    zu format_payment_terms_sentence() in app/invoices.py. Ein unbekannter
    Platzhalter bleibt einfach stehen, kein Fehler."""
    return apply_placeholders(reminder.text or "", _reminder_placeholders(reminder))


# ---------------------------------------------------------------------------
# Sperrgründe
# ---------------------------------------------------------------------------

def send_block_reason(invoice: Invoice) -> str | None:
    """Warum zu dieser Rechnung keine Mahnung (mehr) entsteht oder hinausgeht (seit 1.8.72, Befund 1h), sonst None. Seit 1.8.78
    aus dem Zahlstand: bezahlt (am Eingangsdatum der letzten Zahlung), nur noch Einbehalt offen, Stornorechnung
    (app/payments.py::dunning_block_reason())."""
    from .payments import dunning_block_reason  # lokal: app/payments.py importiert app/invoices.py
    number = invoice.invoice_number or "(Entwurf)"
    if invoice.status == "storniert":
        return f"Die Rechnung {number} ist storniert -- dazu geht keine Mahnung mehr hinaus."
    db = object_session(invoice)
    return dunning_block_reason(db, invoice) if db is not None else None


def dunnable_amount(db: Session, invoice: Invoice) -> Decimal:
    """Mahnfähiger Betrag der Rechnung (seit 1.8.78): offen − Einbehalt, 0 wenn sie nie offen ist."""
    from .payments import payment_state  # lokal: Zirkel-Import
    state = payment_state(db, invoice)
    return state.dunnable if state is not None else Decimal("0")


def stale_amount_reason(db: Session, reminder: Reminder, *, state=_UNSET) -> str | None:
    """Seit 1.8.78: ein Entwurf mahnt den Betrag von seinem Anlegen -- ist seither eine Zahlung gebucht oder gegengebucht,
    stimmt er nicht mehr, und der Entwurf wird nicht festgeschrieben (Grund statt "Versenden")."""
    from .payments import payment_state  # lokal: Zirkel-Import
    if reminder.status != "entwurf" or reminder.invoice.status != FINALIZED:
        return None
    if state is _UNSET:
        state = payment_state(db, reminder.invoice)
    current = state.dunnable if state is not None else Decimal("0")
    if current <= 0 or current == reminder_amount(reminder):
        return None
    return (f"Der Entwurf mahnt {_money(reminder.outstanding_amount)}, mahnfähig sind inzwischen {_money(current)} -- seit dem "
            "Anlegen wurde eine Zahlung gebucht. Bitte den Entwurf löschen und neu anlegen.")


def _new_reminder_hint(db: Session, invoice: Invoice, levels: dict[int, ReminderLevel]) -> str:
    """"Bitte eine neue Mahnung anlegen …" mit Stufe und Tag, ab dem sie möglich ist."""
    step = _step(invoice, levels)
    if step["next_level"] is None:
        return " Eine weitere Mahnstufe ist nicht aktiv."
    label = _label(levels, step["next_level"])
    if step["next_due_on"] is not None and berlin_today() < step["next_due_on"]:
        return f" Bitte eine neue Mahnung anlegen -- die {label} ist ab dem {_de(step['next_due_on'])} möglich."
    return f" Bitte eine neue Mahnung anlegen ({label})."


def dispatch_block_reason(db: Session, reminder: Reminder, *, on: date | None = None, state=_UNSET) -> str | None:
    """Warum diese festgeschriebene Mahnung nicht (mehr) hinausgeht (Vorgabe Z2a Nr. 5), sonst None: die Rechnung ist storniert,
    oder ihr Betrag entspricht nicht mehr dem mahnfähigen. on: der Tag einer nachgetragenen Zustellung -- dann zählt der
    mahnfähige Betrag an diesem Tag (Zahlungen mit Eingangsdatum bis dahin; eine zurückgenommene Buchung gilt nie); ohne on der
    Stand heute (E-Mail-Versand). Storniert sperrt immer, auch eine Zustellung von vor dem Storno."""
    from .payments import payment_state, payment_state_on  # lokal: Zirkel-Import
    if reminder.status != FINALIZED:
        return None
    invoice = reminder.invoice
    number = reminder.reminder_number or ""
    inv_number = invoice.invoice_number or "(Entwurf)"
    if invoice.status == "storniert":
        return f"Die Rechnung {inv_number} ist storniert -- die Mahnung {number} geht nicht mehr hinaus."
    if invoice.invoice_type == "storno":
        return f"{inv_number} ist eine Stornorechnung -- die Mahnung {number} geht nicht hinaus."
    if on is None:
        current_state = payment_state(db, invoice) if state is _UNSET else state
    else:
        current_state = payment_state_on(db, invoice, on)
    current = current_state.dunnable if current_state is not None else Decimal("0")
    amount = reminder_amount(reminder)
    if current == amount:
        return None
    when = f"waren am {_de(on)}" if on is not None else "sind inzwischen"
    return (f"Die Mahnung {number} lautet über {_money(amount)}, mahnfähig {when} {_money(current)} -- sie geht nicht mehr "
            f"hinaus.{_new_reminder_hint(db, invoice, _levels(db))}")


def check_delivery(db: Session, reminder: Reminder, delivered_on: date) -> None:
    """Vor dem Eintrag einer nachgetragenen Zustellung (app/dispatch_documents.py, seit 1.8.79): unter der Sperre der
    Auftragszeile (Buchungen und Storno nehmen dieselbe) der Stand am Zustelltag -- InvoiceBlocked (409), der Aufrufer schreibt
    dann nichts. Die Sperre bleibt bis zum Commit des Eintrags."""
    lock_order_invoices(db, reminder.invoice.order_id)
    reason = dispatch_block_reason(db, reminder, on=delivered_on)
    if reason:
        db.rollback()
        raise InvoiceBlocked(reason)


# ---------------------------------------------------------------------------
# Anlegen, Festschreiben, Bearbeiten, Löschen -- unter der Sperre der Auftragszeile
# ---------------------------------------------------------------------------

def _lock_fresh(db: Session, invoice: Invoice) -> None:
    """Sperrt die Zeile des Auftrags (dieselbe Sperre wie Festschreiben, Storno und Zahlungen,
    app/invoices.py::lock_order_invoices()). Die lädt die Rechnungen mit populate_existing neu -- dabei verwirft SQLAlchemy auch
    ihre schon geladene Mahnungsliste, der nächste Zugriff liest sie frisch: jede Prüfung sieht den Stand, den die vorige Aktion
    hinterlassen hat (tests/test_v382_mahnwesen_pg.py lädt die Liste dafür vor dem Warten)."""
    lock_order_invoices(db, invoice.order_id)


def _reject(db: Session, reason: str) -> InvoiceBlocked:
    db.rollback()  # gibt die Sperre frei
    return InvoiceBlocked(reason)


def _refresh_or_gone(db: Session, reminder: Reminder) -> None:
    """Nach der Sperre frisch laden -- ein gleichzeitig gelöschter Entwurf ergibt InvoiceBlocked (409) statt eines
    Fehlers beim Neuladen (seit 1.8.73)."""
    if db.scalar(select(Reminder.id).where(Reminder.id == reminder.id)) is None:
        raise _reject(db, "Der Mahnungsentwurf wurde inzwischen gelöscht.")
    db.refresh(reminder)


def create_reminder(db: Session, invoice: Invoice, level: int | None = None) -> Reminder:
    """Mahnungsentwurf der nächsten Stufe (seit 1.8.79 nur die nächste; level, wenn angegeben, muss sie sein). Unter der
    Sperre geprüft (create_block_reason()), sonst InvoiceBlocked (409) und nichts geschrieben. Betrag, Aufstellung, Gebühr
    und Text aus Zahlstand und Stufe; Mahndatum und Frist rücken beim Festschreiben auf dessen Tag."""
    from .payments import payment_state  # lokal: Zirkel-Import
    _lock_fresh(db, invoice)
    levels = _levels(db)
    state = payment_state(db, invoice)
    reason = create_block_reason(db, invoice, state=state, levels=levels, level=level)
    if reason:
        raise _reject(db, reason)
    cfg = levels[_step(invoice, levels)["next_level"]]
    today = berlin_today()
    reminder = Reminder(
        invoice_id=invoice.id, level=cfg.level, status="entwurf", reminder_date=today,
        new_due_date=today + timedelta(days=cfg.days_after_previous_step),
        # Seit 1.8.78 der mahnfähige Betrag (offen − Einbehalt), vorher das volle Brutto.
        outstanding_amount=state.dunnable, amounts_json=amounts_snapshot(db, invoice, state),
        fee_amount=cfg.fee_amount, text=cfg.text_template,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def create_reminders(db: Session, invoice_ids: list[int]) -> dict:
    """Entwürfe für mehrere Rechnungen (Vorgabe Z2a Nr. 1), je Rechnung einzeln wie create_reminder() -- eine abgelehnte hält
    die anderen nicht auf. Ergebnis: angelegte Entwürfe und abgelehnte Rechnungen mit Grund."""
    created, rejected = [], []
    for invoice_id in dict.fromkeys(invoice_ids):
        invoice = db.get(Invoice, invoice_id)
        if invoice is None:
            rejected.append({"invoice_id": invoice_id, "invoice_number": None, "reason": "Rechnung nicht gefunden."})
            continue
        number = invoice.invoice_number
        try:
            created.append(create_reminder(db, invoice))
        except ValueError as e:  # auch InvoiceBlocked
            db.rollback()
            rejected.append({"invoice_id": invoice_id, "invoice_number": number, "reason": str(e)})
    return {"created": created, "rejected": rejected}


def finalize_and_send_reminder(db: Session, reminder: Reminder) -> Reminder:
    """Festschreiben (Nummer, unveränderlich). Unter der Sperre der Auftragszeile: die Rechnung darf weder storniert noch
    bezahlt sein (seit 1.8.72), der Entwurf muss die nächste Stufe sein und deren Zeit gekommen (seit 1.8.79, dieselben
    Prüfungen wie beim Anlegen), sein Betrag noch stimmen (seit 1.8.78). Mahndatum = heute (Berlin), die Frist rückt mit
    (finalize_dates()); die Aufstellung wird unter der Sperre frisch geschrieben (der Betrag ist geprüft gleich)."""
    from .payments import payment_state  # lokal: Zirkel-Import
    invoice = reminder.invoice
    _lock_fresh(db, invoice)
    reason = send_block_reason(invoice)
    if reason:
        raise _reject(db, reason)
    _refresh_or_gone(db, reminder)
    if reminder.status != "entwurf":
        db.rollback()
        raise ValueError("Nur Mahnungen im Entwurf können versendet werden.")
    levels = _levels(db)
    state = payment_state(db, invoice)
    reason = create_block_reason(db, invoice, state=state, levels=levels, draft=reminder) or \
        stale_amount_reason(db, reminder, state=state)
    if reason:
        raise _reject(db, reason)
    reminder.reminder_date, reminder.new_due_date = finalize_dates(reminder, levels, berlin_today())
    reminder.amounts_json = amounts_snapshot(db, invoice, state)
    reminder.reminder_number = issue_number(db, "reminder")
    reminder.status = FINALIZED
    db.commit()
    db.refresh(reminder)
    return reminder


DEFAULT_REMINDER_EMAIL_SUBJECT = "{mahnstufe} zu Rechnung {rechnungsnummer}"
DEFAULT_REMINDER_EMAIL_BODY = (
    "Sehr geehrte Damen und Herren,\n\n"
    "anbei erhalten Sie unsere {mahnstufe} zu Rechnung {rechnungsnummer}. "
    "Alle Einzelheiten entnehmen Sie bitte dem beigefügten PDF.\n\n"
    "Mit freundlichen Grüßen"
)


def get_reminder_recipient_email(reminder: Reminder) -> str | None:
    """Aktuelle, live nachgeschlagene Kunden-E-Mail (nicht als Schnappschuss
    gespeichert, da beim Versand -- anders als beim PDF-Inhalt -- die
    aktuell gültige Adresse gewollt ist, siehe Klärung dazu).

    Bewusst defensiv gegen fehlende Zwischenglieder (order/project/
    customer) -- diese Funktion läuft über reminder_to_dict() bei JEDEM
    Lesezugriff mit, ein fehlendes Glied soll die ganze Ansicht nicht zum
    Absturz bringen, sondern nur zu 'keine Adresse hinterlegt' führen. Seit 1.8.79 der Kunde der Rechnung
    (app/invoices.py::invoice_customer())."""
    customer = invoice_customer(reminder.invoice)
    return (customer.email or None) if customer else None


def send_reminder_email(
    db: Session, reminder: Reminder, *, to_email: str | None = None, cc_email: str | None = None,
    dispatch_key: str | None = None, user=None,
) -> Reminder:
    """Versendet eine bereits finalisierte Mahnung tatsächlich per E-Mail
    (seit 1.0.74) -- bewusst getrennt von finalize_and_send_reminder()
    (das nur Nummer und Status setzt, siehe Klärung: PDF-Erzeugung soll
    weiterhin unabhängig davon möglich bleiben). Kann auch mehrfach
    aufgerufen werden (z.B. erneuter Versand, falls der Kunde die Mahnung
    nicht erhalten hat) -- aktualisiert email_sent_at/email_sent_to bei
    jedem Aufruf neu.

    to_email überschreibt die automatisch ermittelte Kunden-E-Mail nur für
    DIESEN Versand (Klärung: vor dem Versand manuell korrigierbar), ändert
    aber nie die Kundenstammdaten selbst.

    PDF-Erzeugung erfolgt hier lokal (nicht über einen Import aus
    app/reminder_pdf.py am Modulanfang), um einen Zirkel-Import zu
    vermeiden: reminder_pdf.py baut auf document_pdf.py auf, das seinerseits
    nicht auf reminders.py zurückgreifen soll.

    Seit 1.8.17 über app/email_dispatch.py (Protokoll, Ablage, Doppelversand-Sperre, CC), siehe
    send_invoice_email() in app/invoices.py; seit 1.8.19 ab dem ersten Versand die abgelegte
    Fassung (app/sent_documents.py::frozen_or_fresh_pdf())."""
    from .email_dispatch import actor_of, dispatch_email, mark_document_sent, new_dispatch_key
    from .reminder_pdf import build_reminder_pdf
    from .sent_documents import ArchiveFileError, frozen_or_fresh_pdf

    if reminder.status != FINALIZED:
        raise ValueError("Nur bereits finalisierte Mahnungen können per E-Mail versendet werden.")
    # Seit 1.8.72: auch eine festgeschriebene Mahnung geht nach Storno oder Zahlung der Rechnung nicht mehr per E-Mail
    # hinaus (ohne Sperre der Auftragszeile -- sonst hielte der Versand sie über die Verbindung zum Mailserver). Seit 1.8.79
    # auch nicht nach einer Teilzahlung: ihr Betrag muss noch der mahnfähige sein (dispatch_block_reason()).
    reason = send_block_reason(reminder.invoice) or dispatch_block_reason(db, reminder)
    if reason:
        raise InvoiceBlocked(reason)

    recipient = (to_email or "").strip() or get_reminder_recipient_email(reminder)
    if not recipient:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")

    level_cfg = db.scalar(select(ReminderLevel).where(ReminderLevel.level == reminder.level))
    level_label = level_cfg.label if level_cfg else f"{reminder.level}. Mahnung"
    placeholders = _reminder_placeholders(reminder) | {"{mahnstufe}": level_label}

    subject_template = (level_cfg.email_subject_template if level_cfg else None) or DEFAULT_REMINDER_EMAIL_SUBJECT
    body_template = (level_cfg.email_body_template if level_cfg else None) or DEFAULT_REMINDER_EMAIL_BODY
    subject = apply_placeholders(subject_template, placeholders)
    body = apply_placeholders(body_template, placeholders)

    try:
        pdf = frozen_or_fresh_pdf(db, "mahnung", reminder.id, build=lambda: build_reminder_pdf(db, reminder),
                                  filename=f"{reminder.reminder_number}.pdf")
    except ArchiveFileError as e:
        raise ValueError(f"Die versendete Fassung dieser Mahnung in der Ablage ist nicht mehr unversehrt: {e} "
                         "Es wurde nichts versendet -- bitte im Versandprotokoll prüfen.") from e
    user_id, user_name = actor_of(user)
    result = dispatch_email(
        db, dispatch_key=dispatch_key or new_dispatch_key("mahnung"), document_type="mahnung",
        document_id=reminder.id, document_number=reminder.reminder_number, to=recipient, cc=cc_email,
        subject=subject, body_text=body, attachment_bytes=pdf.content, attachment_filename=pdf.filename,
        archived_document=pdf.archived, user_id=user_id, user_name=user_name,
    )
    mark_document_sent(db, reminder, result)
    return reminder


def update_reminder_draft(
    db: Session, reminder: Reminder, *, text: str | None, fee_amount: Decimal, payment_days: int,
) -> Reminder:
    """Bearbeiten eines noch nicht festgeschriebenen Mahnungsentwurfs (seit 1.3.21). Seit 1.8.79 (Vorgabe Z2a Nr. 3) unter der
    Sperre der Auftragszeile wie Festschreiben und Löschen: geändert wird nur, was danach noch Entwurf ist, sonst
    InvoiceBlocked (409) -- vorher wartete eine Änderung auf ein gleichzeitiges Festschreiben und schrieb danach in die
    festgeschriebene Mahnung. Die Frist ist eine Länge in Tagen (1–365): sie rechnet ab dem Tag des Festschreibens.

    text bleibt bewusst das ROHE Textfeld mit unaufgelösten Platzhaltern (`{mahngebuehr}` usw.,
    siehe ReminderLevel.text_template/format_reminder_text()) -- exakt dieselbe Konvention wie
    beim Bearbeiten einer Mahnstufe selbst (Einstellungen → Mahnstufen)."""
    if not 1 <= int(payment_days) <= 365:
        raise ValueError("Die Zahlungsfrist muss zwischen 1 und 365 Tagen liegen.")
    lock_order_invoices(db, reminder.invoice.order_id)
    _refresh_or_gone(db, reminder)
    if reminder.status != "entwurf":
        raise _reject(db, "Nur Mahnungen im Entwurf können bearbeitet werden. Die Mahnung ist inzwischen festgeschrieben "
                          f"({reminder.reminder_number}).")
    reminder.text = text
    reminder.fee_amount = fee_amount
    reminder.new_due_date = reminder.reminder_date + timedelta(days=int(payment_days))
    db.commit()
    db.refresh(reminder)
    return reminder


def delete_reminder_draft(db: Session, reminder: Reminder) -> None:
    """Seit 1.8.73 unter derselben Sperre wie das Festschreiben (wie app/invoices.py::delete_invoice_draft()): gelöscht
    wird nur, was danach noch Entwurf ist, sonst InvoiceBlocked (409) -- vorher konnte ein gleichzeitiges Löschen eine eben
    festgeschriebene Mahnung mitnehmen."""
    lock_order_invoices(db, reminder.invoice.order_id)
    _refresh_or_gone(db, reminder)
    if reminder.status != "entwurf":
        number = f" Die Mahnung ist inzwischen festgeschrieben ({reminder.reminder_number})." if reminder.reminder_number else ""
        raise _reject(db, f"Nur Mahnungen im Entwurf können gelöscht werden.{number}")
    db.delete(reminder)
    db.commit()


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------

def list_reminders_for_invoice(db: Session, invoice_id: int) -> list[Reminder]:
    return db.scalars(
        select(Reminder).where(Reminder.invoice_id == invoice_id).order_by(Reminder.level, Reminder.id)
    ).all()


def list_all_reminders(db: Session) -> list[Reminder]:
    """Für die Mahnwesen-Übersichtsseite (seit 1.0.70): alle Mahnungen im
    System, unabhängig von der Rechnung -- Entwürfe und versendete
    zusammen, neueste zuerst. Im Unterschied zu
    list_invoices_needing_attention() (nur überfällige Rechnungen ohne
    passende Mahnung) hier die vollständige Historie als Nachschlagewerk."""
    return db.scalars(
        select(Reminder).options(selectinload(Reminder.invoice).selectinload(Invoice.reminders))
        .order_by(Reminder.reminder_date.desc(), Reminder.id.desc())
    ).all()


def _block_of(db: Session, reminder: Reminder, state, levels: dict[int, ReminderLevel]) -> str | None:
    """Was die Oberfläche statt "Versenden" (Entwurf) bzw. statt E-Mail und Zustellung (festgeschrieben) zeigt."""
    if reminder.status == "entwurf":
        return (send_block_reason(reminder.invoice)
                or create_block_reason(db, reminder.invoice, state=state, levels=levels, draft=reminder)
                or stale_amount_reason(db, reminder, state=state))
    return send_block_reason(reminder.invoice) or dispatch_block_reason(db, reminder, state=state)


def reminder_to_dict(reminder: Reminder, *, state=_UNSET, levels: dict[int, ReminderLevel] | None = None) -> dict:
    """state/levels: schon geladen (Listen, reminders_to_dicts()), sonst frisch."""
    from .payments import payment_state  # lokal: Zirkel-Import
    invoice = reminder.invoice
    db = object_session(reminder)
    if db is not None and state is _UNSET:
        state = payment_state(db, invoice)
    if db is not None and levels is None:
        levels = _levels(db)
    reminder_date, new_due_date = effective_dates(reminder, levels or {})
    breakdown = amounts(reminder)
    return {
        "id": reminder.id,
        "reminder_number": reminder.reminder_number,
        "invoice_id": reminder.invoice_id,
        "invoice_number": invoice.invoice_number,
        "order_id": invoice.order_id,
        "level": reminder.level,
        "status": reminder.status,
        "reminder_date": reminder.reminder_date,
        "new_due_date": reminder.new_due_date,
        # Seit 1.8.79: im Entwurf, was das Festschreiben heute setzen würde, und die Frist in Tagen (das Bearbeiten-Feld).
        "effective_reminder_date": reminder_date,
        "effective_new_due_date": new_due_date,
        "payment_days": payment_days(reminder, levels or {}) if reminder.status == "entwurf" else None,
        "outstanding_amount": reminder.outstanding_amount,
        "fee_amount": reminder.fee_amount,
        "total_amount": reminder_total(reminder),
        "amounts": breakdown,
        "text": reminder.text,
        "formatted_text": format_reminder_text(reminder),
        "customer_name": invoice.customer_name,
        "email_sent_at": reminder.email_sent_at,
        "email_sent_to": reminder.email_sent_to,
        "recipient_email": get_reminder_recipient_email(reminder),
        "send_block": _block_of(db, reminder, state, levels or {}) if db is not None else send_block_reason(invoice),
    }


def reminders_to_dicts(db: Session, reminders: list[Reminder]) -> list[dict]:
    """Viele Mahnungen auf einmal: Zahlstand aller Rechnungen in zwei Abfragen, Stufen einmal."""
    from .payments import payment_states  # lokal: Zirkel-Import
    invoices = {r.invoice_id: r.invoice for r in reminders}
    states = payment_states(db, invoices.values())
    levels = _levels(db)
    return [reminder_to_dict(r, state=states.get(r.invoice_id), levels=levels) for r in reminders]


def list_invoices_needing_attention(db: Session) -> list[dict]:
    """Überfällige Rechnungen mit mahnfähigem Betrag, ihrer Mahnstufe und ab wann die nächste möglich ist; is_due_now und
    create_block (leer) heißt "zur Mahnung fällig" (seit 1.8.79). Liest nur -- seit 1.8.79 legt nichts mehr von selbst einen
    Entwurf an. Sortiert: zur Mahnung fällig zuerst, dann nach Fälligkeit. caseworker_employee_id ist seit 1.8.79 der
    Sachbearbeiter des Auftrags (die Spalte an der Rechnung setzt niemand)."""
    from .payments import payment_states  # lokal: Zirkel-Import
    overdue = db.scalars(
        select(Invoice).where(Invoice.status == FINALIZED, Invoice.invoice_type != "storno", Invoice.due_date < berlin_today())
        .options(selectinload(Invoice.reminders), selectinload(Invoice.order))
    ).all()
    # Seit 1.8.78 nur mit mahnfähigem Betrag (offen − Einbehalt), und dieser statt des Bruttos.
    states = payment_states(db, overdue)
    levels = _levels(db)
    rows = []
    for invoice in overdue:
        state = states.get(invoice.id)
        if state is None or state.dunnable <= 0:
            continue
        status = compute_reminder_status(db, invoice, state=state, levels=levels)
        rows.append({
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "order_id": invoice.order_id,
            "customer_name": invoice.customer_name,
            "due_date": invoice.due_date,
            "outstanding_amount": state.dunnable,
            "caseworker_employee_id": invoice.order.caseworker_employee_id if invoice.order else None,
            **status,
        })
    rows.sort(key=lambda r: (not (r["is_due_now"] and r["create_block"] is None), r["due_date"]))
    return rows
