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

Seit 1.8.80 (Zahlungsstufe Z2b, docs/archiv/zahlungen.md "Umsetzung 1.8.80"):
- Erreicht ist eine Stufe erst mit Versand oder Zustellung ("Vorweg" 2): zählt nur eine festgeschriebene Mahnung, die beim
  Auftraggeber ankam (reached_map(), app/email_dispatch.py::document_reached_on()). Eine festgeschriebene, die nie hinausging, lässt
  sich durch eine neue derselben Stufe ersetzen -- beim Festschreiben der neuen gilt sie als ersetzt (replaced_by_id), geht nicht
  mehr hinaus, und ihre Nebenforderungen werden gegengebucht.
- Mahngebühren und Pauschale nur eingeschaltet (app/dunning_charges.py): die Gebühr der Stufe ist ein Vorschlag, die Pauschale
  ebenso; beides bewusst übernommen (set_reminder_charges()), erst beim Festschreiben eine Nebenforderung. Die Aufstellung
  (Format 2) zeigt unter dem angemahnten Betrag die geltenden Nebenforderungen der Rechnung und den Gesamtbetrag; ausgeschaltet
  keine. Versand und Zustellung prüfen auch die Nebenforderungen.

Seit 1.8.81 (Z2b Punkte 7-9, "Vorweg" 1): Verzugszinsen als Vorschlag bis zum Mahndatum, bewusst übernommen
(Reminder.interest_accepted), beim Festschreiben frisch unter der Sperre berechnet und eine Nebenforderung; keine Gebühr neben
einer gebuchten oder übernommenen Pauschale; die Aufstellung (Format 3) zeigt je Nebenforderung, was darauf gezahlt ist, die
Abschnitte der Zinsen und die gedruckten Rechtstexte (app/dunning_texts.py) -- eingefroren beim Festschreiben.

Seit 1.8.89 (R4c Punkte 3-5, app/final_dunning.py): mit einer gültigen Endrechnung wird eine abgezogene Rechnung nicht mehr einzeln
gemahnt (nicht zur Mahnung fällig, kein neuer Entwurf, ein offener ist überholt, eine festgeschriebene Mahnung geht nicht mehr hinaus),
ihr Einbehalt wird mit der Endrechnung fällig, und die Mahnung der Endrechnung lautet über den Zahlbetrag: ihr mahnfähiger Betrag plus
die offenen Beträge der abgezogenen Rechnungen (Aufstellung Format 4, je Rechnung mit Nummer). "state" ist hier überall ein
app/final_dunning.py::DunningState (dunnable = angemahnter Hauptbetrag, own = Zahlstand der Rechnung selbst).
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session, selectinload

from .berlin_time import berlin_today
from .default_interest import interest_proposal
from .dunning_charges import (
    DISABLED_TEXT, FLAT_FEE, ChargeRejected, active_default_start, add_charges, charge_lines, charges_enabled, charges_in_force,
    charges_of_reminders, draft_proposals, fee_block_reason, flat_fee_block_reason, money, new_charge_lines, open_charges,
    reverse_charges_of,
)
from .dunning_texts import texts_for
from .final_dunning import dunning_state, dunning_states, nothing_to_dun_reason, settled_text
from .invoices import InvoiceBlocked, invoice_customer, invoice_rounding, lock_order_invoices
from .models import Invoice, Reminder, ReminderLevel
from .placeholders import apply_placeholders
from .rounding import CENT, round_money
from .settings import issue_number

FINALIZED = "versendet"
_UNSET = object()


def _de(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _money(x: Decimal) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def reminder_total(reminder: Reminder) -> Decimal:
    """Gesamtbetrag der Mahnung (seit 1.8.80 aus charges_view()): angemahnter Betrag + Nebenforderungen. Mahnungen von vor 1.8.80:
    offener Betrag + Mahngebühr, auf den Cent nach der Rundungsregel der Rechnung (seit 1.8.11,
    app/invoices.py::invoice_rounding()): kaufmännisch bei Rechnungen ab 1.8.11, halb-gerade wie bisher bei vorher
    versendeten -- deren offener Betrag ist ungerundet gespeichert, und eine versendete Mahnung soll beim Nachdruck denselben
    Gesamtbetrag zeigen."""
    return charges_view(reminder)["total"]


def reminder_amount(reminder: Reminder) -> Decimal:
    """Der gemahnte Betrag auf den Cent (wie reminder_total() ohne Gebühr) -- für den Vergleich mit dem mahnfähigen Betrag."""
    return reminder.outstanding_amount.quantize(CENT, rounding=invoice_rounding(reminder.invoice))


DEFAULT_REMINDER_LEVELS = [
    # (level, label, days_after_previous_step = Zahlungsfrist in Tagen seit 1.8.79, fee_amount, text_template)
    # Seit 1.8.80 (Z2b): die Gebühr ist nur ein Vorschlag (bei eingeschalteten Mahngebühren), Stufe 1 ohne (die erste Mahnung
    # begründet meist erst den Verzug); die Texte nennen den Gesamtbetrag, die Aufstellung im PDF zeigt die Teile -- ohne
    # "zuzüglich einer Mahngebühr", das bei ausgeschalteten Gebühren "0,00 €" drucken würde. Die Migration 8e2f4b6d1c97 stellt
    # unveränderte Standardtexte und die Gebühr 5,00 € der Stufe 1 ebenso um.
    (
        1, "1. Mahnung", 7, Decimal("0.00"),
        "Trotz Fälligkeit am {faelligkeitsdatum} konnten wir bis heute keinen Zahlungseingang zu "
        "Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Bitte begleichen Sie den "
        "Betrag von {gesamtbetrag} (Aufstellung unten) bis zum {neue_frist}. Sollte Ihre Zahlung "
        "bereits erfolgt sein, betrachten Sie dieses Schreiben bitte als gegenstandslos.",
    ),
    (
        2, "2. Mahnung", 7, Decimal("10.00"),
        "Leider konnten wir trotz unserer Zahlungserinnerung vom {vorheriges_mahndatum} bis heute "
        "keinen Zahlungseingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Wir "
        "bitten Sie letztmalig, den Betrag von {gesamtbetrag} (Aufstellung unten) bis zum "
        "{neue_frist} zu begleichen.",
    ),
    (
        3, "3. Mahnung", 7, Decimal("15.00"),
        "Auch nach unserer 2. Mahnung vom {vorheriges_mahndatum} ist Rechnung {rechnungsnummer} vom "
        "{rechnungsdatum} weiterhin nicht ausgeglichen. Wir bitten Sie letztmalig um Zahlung von "
        "{gesamtbetrag} (Aufstellung unten) bis zum {neue_frist}. Nach fruchtlosem Ablauf dieser "
        "Frist behalten wir uns weitere rechtliche Schritte vor.",
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


LEVEL_FIELDS = ("label", "days_after_previous_step", "fee_amount", "text_template", "email_subject_template",
                "email_body_template", "active")


def update_reminder_level(db: Session, level_row: ReminderLevel, **changes) -> ReminderLevel:
    """Seit 1.8.80 nur die gesendeten Felder (Regel 22): die Seite schickt die Gebühr nur bei eingeschalteten Mahngebühren, der
    Bereich "E-Mail-Vorlagen" nur Betreff und Text."""
    unknown = set(changes) - set(LEVEL_FIELDS)
    if unknown:
        raise ValueError(f"Unbekannte Felder: {', '.join(sorted(unknown))}")
    for key, value in changes.items():
        setattr(level_row, key, value)
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


def _finalized(invoice: Invoice) -> list[Reminder]:
    return [r for r in invoice.reminders if r.status == FINALIZED]


def reached_map(db: Session, reminders) -> dict[int, date]:
    """Je festgeschriebener Mahnung der Tag, an dem sie zuerst hinausging -- versendet oder zugestellt und beim Auftraggeber
    angekommen (seit 1.8.80, "Vorweg" 2, app/email_dispatch.py::document_reached_on()). Fehlt eine, ging sie nie hinaus."""
    from .email_dispatch import document_reached_on  # lokal: app/email_dispatch.py zieht den Versand nach

    return document_reached_on(db, "mahnung", [r for r in reminders if r.status == FINALIZED])


def _reached_of(db: Session, invoice: Invoice, reached: dict[int, date] | None) -> dict[int, date]:
    return reached if reached is not None else reached_map(db, invoice.reminders)


def pending_reminder(invoice: Invoice, reached: dict[int, date]) -> Reminder | None:
    """Die jüngste festgeschriebene Mahnung, die nie hinausging und nicht ersetzt ist -- sie lässt sich versenden oder durch eine
    neue derselben Stufe ersetzen (seit 1.8.80)."""
    rows = [r for r in _finalized(invoice) if r.id not in reached and r.replaced_by_id is None]
    return max(rows, key=lambda r: (r.level, r.reminder_date, r.id)) if rows else None


def replaceable(invoice: Invoice, reached: dict[int, date], level: int, *, exclude_id: int | None = None) -> list[Reminder]:
    """Die festgeschriebenen Mahnungen bis zu dieser Stufe, die nie hinausgingen und nicht ersetzt sind -- eine neue dieser Stufe
    ersetzt sie beim Festschreiben (seit 1.8.80, "Vorweg" 2)."""
    return [r for r in _finalized(invoice) if r.id != exclude_id and r.id not in reached and r.replaced_by_id is None
            and r.level <= level]


def replaces_info(db: Session, reminders: list[Reminder]) -> list[dict]:
    """Seit 1.8.81 (Festlegung 1.8.80 Nr. 2): je Mahnung, die ein Festschreiben ersetzt, ihre Nummer und die Nebenforderungen, die
    dabei gegengebucht werden -- die Oberfläche nennt sie vor dem Ersetzen."""
    result = []
    for old in sorted(reminders, key=lambda r: (r.level, r.id)):
        lines = charge_lines(db, charges_of_reminders(db, [old]))
        result.append({"id": old.id, "reminder_number": old.reminder_number, "level": old.level,
                       "charges": [{"label": line["label"], "amount": line["amount"]} for line in lines]})
    return result


def _step(invoice: Invoice, levels: dict[int, ReminderLevel], reached: dict[int, date]) -> dict:
    """Aktuelle Stufe (höchste erreichte -- seit 1.8.80 nur eine versendete oder zugestellte Mahnung), ihre letzte Mahnung,
    nächste aktive Stufe und ab wann sie möglich ist."""
    sent = [r for r in _finalized(invoice) if r.id in reached]
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
    """Warum zur Rechnung nichts zu mahnen ist (Entwurf, storniert, Storno, bezahlt, nur Einbehalt, 0 €, seit 1.8.89 in einer
    Endrechnung abgezogen bzw. ihr Zahlbetrag beglichen), sonst None. state: DunningState."""
    number = invoice.invoice_number or "(Entwurf)"
    if invoice.status == "entwurf":
        return "Nur zu festgeschriebenen Rechnungen entsteht eine Mahnung."
    if invoice.status == "storniert":
        return f"Die Rechnung {number} ist storniert -- dazu geht keine Mahnung mehr hinaus."
    return nothing_to_dun_reason(db, invoice, state)


def create_block_reason(db: Session, invoice: Invoice, *, state=_UNSET, levels: dict[int, ReminderLevel] | None = None,
                        level: int | None = None, draft: Reminder | None = None,
                        reached: dict[int, date] | None = None) -> str | None:
    """Warum zu dieser Rechnung jetzt keine Mahnung entsteht (Vorgabe Z2a Nr. 2), sonst None -- beim Anlegen (level: die
    verlangte Stufe, None = die nächste) und beim Festschreiben (draft: dieser Entwurf, seine Stufe muss die nächste sein).
    Reihenfolge: nichts zu mahnen (Storno, storniert, bezahlt, nur Einbehalt), nicht fällig, schon ein Entwurf, keine weitere
    Stufe, nicht die nächste Stufe, Frist der vorigen noch nicht abgelaufen. Seit 1.8.80 zählt als erreicht nur eine
    versendete oder zugestellte Mahnung -- eine nie hinausgegangene derselben Stufe hält eine neue nicht auf (sie wird ersetzt).
    Seit 1.8.89: in einer gültigen Endrechnung abgezogen -- kein neuer Entwurf, ein offener ist überholt (R4c Punkt 3)."""
    if state is _UNSET:
        state = dunning_state(db, invoice)
    if levels is None:
        levels = _levels(db)
    reason = _amount_reason(db, invoice, state)
    if reason and draft is not None and state.settled_in is not None:
        return (f"Der Entwurf ({_label(levels, draft.level)}) ist überholt: {settled_text(invoice, state.settled_in)} Bitte den "
                "Entwurf löschen.")
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
    step = _step(invoice, levels, _reached_of(db, invoice, reached))
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
                            levels: dict[int, ReminderLevel] | None = None, reached: dict[int, date] | None = None) -> dict:
    """Auf welcher Mahnstufe die Rechnung steht, welche aktive Stufe als Nächstes kommt und ab wann (seit 1.8.79: ab dem Tag
    nach der Fälligkeit bzw. nach dem Ende der Frist der vorigen Mahnung). Deaktivierte Stufen werden übersprungen.

    draft: der bestehende Entwurf (reminder_to_dict()) oder None; create_block (seit 1.8.79): warum jetzt kein Entwurf
    entsteht -- die Oberfläche zeigt den Grund statt des Knopfs. pending (seit 1.8.80): eine festgeschriebene Mahnung, die nie
    hinausging -- mit dispatch_block, falls sie auch nicht mehr hinausgehen kann (dann ist eine neue fällig, die sie ersetzt).
    Seit 1.8.89 dunning (app/final_dunning.py): angemahnter Betrag samt den offenen abgezogenen Rechnungen bzw. die Endrechnung, in
    der die Rechnung abgezogen ist."""
    if state is _UNSET:
        state = dunning_state(db, invoice)
    if levels is None:
        levels = _levels(db)
    reached = _reached_of(db, invoice, reached)
    block = create_block_reason(db, invoice, state=state, levels=levels, reached=reached)
    draft = next((r for r in invoice.reminders if r.status == "entwurf"), None)
    draft_dict = reminder_to_dict(draft, state=state, levels=levels, reached=reached) if draft is not None else None
    pending = pending_reminder(invoice, reached)
    pending_dict = None
    if pending is not None:
        pending_dict = {"id": pending.id, "reminder_number": pending.reminder_number, "level": pending.level,
                        "label": _label(levels, pending.level), "reminder_date": pending.reminder_date,
                        "dispatch_block": dispatch_block_reason(db, pending, state=state, levels=levels, reached=reached),
                        # seit 1.8.81: was beim Ersetzen gegengebucht würde
                        "charges": replaces_info(db, [pending])[0]["charges"]}
    dunning = state.as_dict()
    if invoice.status != FINALIZED or invoice.due_date is None or state.dunnable <= 0:
        return {"current_level": 0, "next_level": None, "next_due_on": None, "is_due_now": False,
                "draft": draft_dict, "create_block": block, "pending": pending_dict, "dunning": dunning}
    step = _step(invoice, levels, reached)
    is_due_now = step["next_level"] is not None and berlin_today() >= step["next_due_on"]
    return {
        "current_level": step["current_level"], "next_level": step["next_level"],
        "next_due_on": step["next_due_on"] if step["next_level"] is not None else None, "is_due_now": is_due_now,
        "draft": draft_dict, "create_block": block, "pending": pending_dict, "dunning": dunning,
    }


# ---------------------------------------------------------------------------
# Aufstellung des gemahnten Betrags (seit 1.8.79, Vorgabe Z2a Nr. 4)
# ---------------------------------------------------------------------------

def legal_topics(db: Session, invoice: Invoice, lines: list[dict], on: date) -> dict[str, dict]:
    """Welche Rechtstexte die Mahnung vom Tag on nennt, mit den Werten ihrer Platzhalter (seit 1.8.81, app/dunning_texts.py):
    "verzug", wenn ein bestätigter Verzugsbeginn am Mahndatum gilt; "zinsen", wenn sie Verzugszinsen zeigt (Werte der jüngsten
    Zinszeile); "pauschale", wenn sie die Pauschale zeigt."""
    topics: dict[str, dict] = {}
    start = active_default_start(db, invoice.id)
    if start is not None and start.starts_on <= on:
        topics["verzug"] = {"{verzugsbeginn}": _de(start.starts_on)}
    interest = [line for line in lines if line["kind"] == "zinsen"]
    if interest:
        last = interest[-1]
        surcharge = last.get("surcharge")
        topics["zinsen"] = {
            "{prozentpunkte}": f"{Decimal(surcharge).normalize():f}" if surcharge is not None else "",
            "{zinsen_von}": _de(last["period_start"]) if last.get("period_start") else "",
            "{zinsen_bis}": _de(last["period_end"]) if last.get("period_end") else ""}
    if any(line["kind"] == "pauschale" for line in lines):
        topics["pauschale"] = {"{pauschale}": money(FLAT_FEE)}
    return topics


def _line_json(line: dict) -> dict:
    return {"kind": line["kind"], "label": line["label"], "amount": str(line["amount"]), "paid": str(line.get("paid") or 0),
            "sections": [{"text": s["text"]} for s in line.get("sections") or []]}


def amounts_snapshot(db: Session, invoice: Invoice, state, *, enabled: bool, on: date | None = None) -> str:
    """Aufstellung aus dem Zahlstand als kanonisches JSON: Brutto, je noch geltender Zahlung Eingangsdatum und Betrag, Skonto,
    Einbehalt (der abgezogene Teil, höchstens der offene Betrag), mahnfähig. Brutto − Zahlungen − Skonto − Einbehalt =
    mahnfähig. Seit 1.8.80 (Format 2) dazu die geltenden Nebenforderungen der Rechnung (Bezeichnung, Betrag) und der
    Gesamtbetrag = mahnfähig + Nebenforderungen; bei ausgeschalteten Mahngebühren (enabled) keine. Seit 1.8.81 (Format 3) je
    Nebenforderung das darauf Gezahlte, bei Zinsen die Abschnitte, offen = Summe − Gezahltes, und die gedruckten Rechtstexte der
    Mahnung vom Tag on (Platzhalter eingesetzt).

    Seit 1.8.89 (Format 4, R4c Punkt 5, state: DunningState): "dunnable" ist der mahnfähige Betrag der Rechnung selbst, "deducted"
    an der Endrechnung je abgezogener Rechnung mit offenem Betrag Nummer, Art, offen und davon Einbehalt, "principal" der angemahnte
    Betrag = dunnable + deducted (der Zahlbetrag); Gesamtbetrag = principal + Nebenforderungen. Rechnungsbetrag und Zahlungen einer
    Endrechnung, die nie offen ist (Rechnungsbetrag 0 €), stehen als 0."""
    from .payments import invoice_payment_lines, payable_gross  # lokal: Zirkel-Import
    on = on or berlin_today()
    own = state.own
    lines = charge_lines(db, charges_in_force(db, [invoice.id])[invoice.id]) if enabled else []
    charges_sum = sum((line["amount"] for line in lines), Decimal("0.00"))
    charges_paid = sum((line["paid"] for line in lines), Decimal("0.00"))
    printed = texts_for(db, legal_topics(db, invoice, lines, on))[0] if enabled else []
    zero = Decimal("0.00")
    data = {
        "format": 4, "gross": str(own.gross if own is not None else payable_gross(invoice)),
        "payments": ([{"received_on": d.isoformat(), "amount": str(a)} for d, a in invoice_payment_lines(db, invoice)]
                     if own is not None else []),
        "skonto": str(own.skonto if own is not None else zero),
        "retained": str(own.retained_open if own is not None else zero), "dunnable": str(state.own_part),
        "deducted": [{"invoice_id": d.invoice.id, "invoice_number": d.invoice.invoice_number,
                      "invoice_type": d.invoice.invoice_type, "open": str(d.open), "retained": str(d.retained)}
                     for d in state.deducted],
        "principal": str(state.dunnable),
        "charges_enabled": bool(enabled),
        "charges": [_line_json(line) for line in lines],
        "charges_paid": str(charges_paid), "charges_open": str(charges_sum - charges_paid),
        "total": str(state.dunnable + charges_sum - charges_paid),
        "legal_texts": printed,
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def amounts(reminder: Reminder) -> dict | None:
    """Die Aufstellung der Mahnung (Beträge als Decimal, Daten als date), None bei Mahnungen von vor 1.8.79. format 1 (1.8.79)
    ohne Nebenforderungen, format 2 (seit 1.8.80) mit charges_enabled, charges, charges_open und total; format 4 (seit 1.8.89) mit
    deducted (je abgezogener Rechnung Nummer, offen, davon Einbehalt) und principal (angemahnter Betrag; vorher = dunnable)."""
    if not reminder.amounts_json:
        return None
    raw = json.loads(reminder.amounts_json)
    return {
        "format": raw.get("format", 1),
        "gross": Decimal(raw["gross"]),
        "payments": [{"received_on": date.fromisoformat(p["received_on"]), "amount": Decimal(p["amount"])}
                     for p in raw["payments"]],
        "skonto": Decimal(raw["skonto"]), "retained": Decimal(raw["retained"]), "dunnable": Decimal(raw["dunnable"]),
        "deducted": [{"invoice_id": d["invoice_id"], "invoice_number": d["invoice_number"], "invoice_type": d["invoice_type"],
                      "open": Decimal(d["open"]), "retained": Decimal(d["retained"])} for d in raw.get("deducted", [])],
        "principal": Decimal(raw.get("principal", raw["dunnable"])),
        "charges_enabled": bool(raw.get("charges_enabled", False)),
        "charges": [{"kind": c["kind"], "label": c["label"], "amount": Decimal(c["amount"]),
                     "paid": Decimal(c.get("paid", "0")), "sections": c.get("sections", [])} for c in raw.get("charges", [])],
        "charges_paid": Decimal(raw.get("charges_paid", "0")),
        "charges_open": Decimal(raw["charges_open"]) if "charges_open" in raw else None,
        "total": Decimal(raw["total"]) if "total" in raw else None,
        "legal_texts": raw.get("legal_texts", []),
    }


def charges_view(reminder: Reminder, db: Session | None = None, *, interest=_UNSET) -> dict:
    """Nebenforderungen und Gesamtbetrag, wie die Mahnung sie zeigt (seit 1.8.80): {"enabled", "lines", "paid", "open", "total",
    "legal_texts", "legal_warnings"}.
    - Festgeschrieben ab 1.8.80: aus der Aufstellung (lines nur, wenn beim Festschreiben eingeschaltet; seit 1.8.81 Format 3 mit
      dem Gezahlten je Nebenforderung und den gedruckten Rechtstexten).
    - Entwurf: eingeschaltet die geltenden Nebenforderungen der Rechnung und die übernommenen neuen (Gebühr, Pauschale, seit
      1.8.81 Zinsen bis heute; "new"), sonst keine -- Gesamtbetrag = angemahnter Betrag + Nebenforderungen − darauf gezahlt;
      die Rechtstexte live, mit Warnung für ungeprüfte. interest: der schon berechnete Zinsvorschlag (sonst frisch).
    - Vor 1.8.80 festgeschrieben: wie bisher angemahnter Betrag + Mahngebühr (lines leer, enabled None)."""
    zero = Decimal("0.00")
    breakdown = amounts(reminder)
    if reminder.status != "entwurf":
        if breakdown is not None and breakdown["format"] >= 2:
            return {"enabled": breakdown["charges_enabled"], "lines": [dict(c, new=False) for c in breakdown["charges"]],
                    "paid": breakdown["charges_paid"], "open": breakdown["charges_open"], "total": breakdown["total"],
                    "legal_texts": breakdown["legal_texts"], "legal_warnings": []}
        total = (reminder.outstanding_amount + reminder.fee_amount).quantize(CENT, rounding=invoice_rounding(reminder.invoice))
        return {"enabled": None, "lines": [], "paid": zero, "open": None, "total": total, "legal_texts": [],
                "legal_warnings": []}
    db = db or object_session(reminder)
    enabled = charges_enabled(db) if db is not None else False
    principal = reminder_amount(reminder)
    if not enabled:
        return {"enabled": False, "lines": [], "paid": zero, "open": zero, "total": principal, "legal_texts": [],
                "legal_warnings": []}
    # Was der Entwurf ersetzen wird, zählt nicht: dessen Nebenforderungen werden beim Festschreiben gegengebucht.
    ignore = {r.id for r in replaceable(reminder.invoice, reached_map(db, reminder.invoice.reminders), reminder.level)}
    in_force = [c for c in charges_in_force(db, [reminder.invoice_id])[reminder.invoice_id] if c.reminder_id not in ignore]
    today = berlin_today()
    if interest is _UNSET:
        interest = (interest_proposal(db, reminder.invoice, until=today, ignore_reminder_ids=ignore)
                    if reminder.interest_accepted else None)
    lines = ([dict(line, new=False) for line in charge_lines(db, in_force)]
             + [dict(line, new=True) for line in new_charge_lines(db, reminder, enabled=True, interest=interest)])
    total_charges = sum((line["amount"] for line in lines), zero)
    paid = sum((line.get("paid") or zero for line in lines), zero)
    printed, warnings = texts_for(db, legal_topics(db, reminder.invoice, lines, today))
    return {"enabled": True, "lines": lines, "paid": paid, "open": total_charges - paid,
            "total": principal + total_charges - paid, "legal_texts": printed, "legal_warnings": warnings}


def fee_of(reminder: Reminder, view: dict | None = None) -> Decimal:
    """Die Gebühr dieser Mahnung: im Entwurf nur übernommen und eingeschaltet, festgeschrieben die gespeicherte (seit 1.8.80 beim
    Festschreiben die übernommene oder 0)."""
    if reminder.status != "entwurf":
        return reminder.fee_amount
    view = view or charges_view(reminder)
    return reminder.fee_amount if view["enabled"] and reminder.fee_accepted else Decimal("0.00")


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def _reminder_placeholders(reminder: Reminder) -> dict:
    """Gemeinsame Platzhalter-Werte für PDF-Text UND E-Mail-Betreff/-Text
    (seit 1.0.74, vorher nur für format_reminder_text() intern). Seit 1.8.79 im Entwurf mit Mahndatum und Frist des
    Festschreibens heute (effective_dates())."""
    invoice = reminder.invoice
    view = charges_view(reminder)
    db = object_session(reminder)
    # Seit 1.8.80 die vorige Stufe, die hinausging (eine ersetzte zählt nicht).
    reached = reached_map(db, invoice.reminders) if db is not None else {}
    previous = sorted((r for r in invoice.reminders
                       if r.status == FINALIZED and r.level == reminder.level - 1 and r.id in reached),
                      key=lambda r: (r.reminder_date, r.id))
    previous_date = previous[-1].reminder_date.strftime("%d.%m.%Y") if previous else ""
    _, new_due_date = effective_dates(reminder)
    return {
        "{rechnungsnummer}": invoice.invoice_number or "",
        "{rechnungsdatum}": invoice.invoice_date.strftime("%d.%m.%Y"),
        "{faelligkeitsdatum}": invoice.due_date.strftime("%d.%m.%Y") if invoice.due_date else "",
        "{offener_betrag}": _money(reminder.outstanding_amount),
        "{mahngebuehr}": _money(fee_of(reminder, view)),
        "{nebenforderungen}": _money(view["open"] or Decimal("0")),
        "{gesamtbetrag}": _money(view["total"]),
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
    (app/payments.py::dunning_block_reason()). Seit 1.8.89 (app/final_dunning.py): an der Endrechnung zählt der Zahlbetrag -- ist sie
    selbst bezahlt, aber ein Abschlag offen, geht ihre Mahnung hinaus; zu einer in ihr abgezogenen Rechnung nennen
    create_block_reason() (neu, Entwurf überholt) und dispatch_block_reason() (geht nicht mehr hinaus) den Grund."""
    number = invoice.invoice_number or "(Entwurf)"
    if invoice.status == "storniert":
        return f"Die Rechnung {number} ist storniert -- dazu geht keine Mahnung mehr hinaus."
    db = object_session(invoice)
    if db is None or invoice.status == "entwurf":
        return None
    state = dunning_state(db, invoice)
    if state.settled_in is not None or (state.own is None and not state.is_final and invoice.invoice_type != "storno"):
        return None  # abgezogen bzw. nie offen (z. B. 0 €) -- create_block_reason() bzw. dispatch_block_reason() nennen den Grund
    return nothing_to_dun_reason(db, invoice, state)


def dunnable_amount(db: Session, invoice: Invoice) -> Decimal:
    """Mahnfähiger Betrag der Rechnung (seit 1.8.78): offen − Einbehalt, 0 wenn sie nie offen ist. Seit 1.8.89 an der Endrechnung
    samt den offenen abgezogenen Rechnungen, an einer abgezogenen 0 (app/final_dunning.py)."""
    return dunning_state(db, invoice).dunnable


def stale_amount_reason(db: Session, reminder: Reminder, *, state=_UNSET) -> str | None:
    """Seit 1.8.78: ein Entwurf mahnt den Betrag von seinem Anlegen -- ist seither eine Zahlung gebucht oder gegengebucht,
    stimmt er nicht mehr, und der Entwurf wird nicht festgeschrieben (Grund statt "Versenden"). Seit 1.8.89 an der Endrechnung der
    Zahlbetrag (auch eine Zahlung auf eine abgezogene Rechnung ändert ihn)."""
    if reminder.status != "entwurf" or reminder.invoice.status != FINALIZED:
        return None
    if state is _UNSET:
        state = dunning_state(db, reminder.invoice)
    current = state.dunnable
    if current <= 0 or current == reminder_amount(reminder):
        return None
    return (f"Der Entwurf mahnt {_money(reminder.outstanding_amount)}, mahnfähig sind inzwischen {_money(current)} -- seit dem "
            "Anlegen wurde eine Zahlung gebucht. Bitte den Entwurf löschen und neu anlegen.")


def _new_reminder_hint(db: Session, invoice: Invoice, levels: dict[int, ReminderLevel],
                       reached: dict[int, date] | None = None) -> str:
    """"Bitte eine neue Mahnung anlegen …" mit Stufe und Tag, ab dem sie möglich ist."""
    step = _step(invoice, levels, _reached_of(db, invoice, reached))
    if step["next_level"] is None:
        return " Eine weitere Mahnstufe ist nicht aktiv."
    label = _label(levels, step["next_level"])
    if step["next_due_on"] is not None and berlin_today() < step["next_due_on"]:
        return f" Bitte eine neue Mahnung anlegen -- die {label} ist ab dem {_de(step['next_due_on'])} möglich."
    return f" Bitte eine neue Mahnung anlegen ({label})."


def dispatch_block_reason(db: Session, reminder: Reminder, *, on: date | None = None, state=_UNSET,
                          levels: dict[int, ReminderLevel] | None = None, reached: dict[int, date] | None = None) -> str | None:
    """Warum diese festgeschriebene Mahnung nicht (mehr) hinausgeht (Vorgabe Z2a Nr. 5), sonst None: die Rechnung ist storniert,
    oder ihr Betrag entspricht nicht mehr dem mahnfähigen. on: der Tag einer nachgetragenen Zustellung -- dann zählt der
    mahnfähige Betrag an diesem Tag (Zahlungen mit Eingangsdatum bis dahin; eine zurückgenommene Buchung gilt nie); ohne on der
    Stand heute (E-Mail-Versand). Storniert sperrt immer, auch eine Zustellung von vor dem Storno.

    Seit 1.8.80: eine ersetzte Mahnung geht nie mehr hinaus ("Vorweg" 2); eine mit Nebenforderungen (Format 2, eingeschaltet)
    nur, solange deren Summe noch stimmt -- am Tag der Zustellung die bis dahin entstandenen, eine gegengebuchte gilt nie.

    Seit 1.8.89 (R4c Punkt 3): zu einer in einer gültigen Endrechnung abgezogenen Rechnung geht keine Mahnung mehr hinaus -- eine
    Zustellung vor dem Tag der Endrechnung lässt sich nachtragen; an der Endrechnung zählt der Zahlbetrag (app/final_dunning.py)."""
    if reminder.status != FINALIZED:
        return None
    invoice = reminder.invoice
    number = reminder.reminder_number or ""
    inv_number = invoice.invoice_number or "(Entwurf)"
    if reminder.replaced_by_id is not None:
        newer = db.get(Reminder, reminder.replaced_by_id)
        newer_number = f" {newer.reminder_number}" if newer is not None and newer.reminder_number else ""
        return f"Die Mahnung {number} ging nie hinaus und ist durch die Mahnung{newer_number} ersetzt -- sie geht nicht mehr hinaus."
    if invoice.status == "storniert":
        return f"Die Rechnung {inv_number} ist storniert -- die Mahnung {number} geht nicht mehr hinaus."
    if invoice.invoice_type == "storno":
        return f"{inv_number} ist eine Stornorechnung -- die Mahnung {number} geht nicht hinaus."
    if on is None:
        current_state = dunning_state(db, invoice) if state is _UNSET else state
    else:
        current_state = dunning_state(db, invoice, on=on)
    if current_state.settled_in is not None:
        return f"{settled_text(invoice, current_state.settled_in)} Die Mahnung {number} geht nicht mehr hinaus."
    current = current_state.dunnable
    amount = reminder_amount(reminder)

    def hint() -> str:
        return _new_reminder_hint(db, invoice, levels or _levels(db), reached)

    if current != amount:
        when = f"waren am {_de(on)}" if on is not None else "sind inzwischen"
        return (f"Die Mahnung {number} lautet über {_money(amount)}, mahnfähig {when} {_money(current)} -- sie geht nicht mehr "
                f"hinaus.{hint()}")
    breakdown = amounts(reminder)
    if breakdown is not None and breakdown["format"] >= 2 and breakdown["charges_enabled"]:
        charges_now = open_charges(db, invoice, on=on)
        if charges_now != breakdown["charges_open"]:
            gelten = f"galten am {_de(on)}" if on is not None else "gelten inzwischen"
            return (f"Die Mahnung {number} nennt Nebenforderungen von {_money(breakdown['charges_open'])}, {gelten} "
                    f"{_money(charges_now)} -- sie geht nicht mehr hinaus.{hint()}")
    return None


def check_delivery(db: Session, reminder: Reminder, delivered_on: date) -> None:
    """Vor dem Eintrag einer nachgetragenen Zustellung (app/dispatch_documents.py, seit 1.8.79): unter der Sperre der
    Auftragszeile (Buchungen und Storno nehmen dieselbe) der Stand am Zustelltag -- InvoiceBlocked (409), der Aufrufer schreibt
    dann nichts. Die Sperre bleibt bis zum Commit des Eintrags."""
    lock_order_invoices(db, reminder.invoice.order_id)
    db.refresh(reminder)  # seit 1.8.80: inzwischen ersetzt? (das Festschreiben der neuen nimmt dieselbe Sperre)
    reason = dispatch_block_reason(db, reminder, on=delivered_on)
    if reason is None and delivered_on < reminder.reminder_date:
        reason = (f"Die Mahnung {reminder.reminder_number} ist vom {_de(reminder.reminder_date)} -- eine Zustellung davor ist "
                  "nicht möglich.")
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
    und Text aus Zahlstand und Stufe; Mahndatum und Frist rücken beim Festschreiben auf dessen Tag. Seit 1.8.89 an der Endrechnung über
    den Zahlbetrag (app/final_dunning.py)."""
    _lock_fresh(db, invoice)
    levels = _levels(db)
    state = dunning_state(db, invoice)
    reached = reached_map(db, invoice.reminders)
    reason = create_block_reason(db, invoice, state=state, levels=levels, level=level, reached=reached)
    if reason:
        raise _reject(db, reason)
    cfg = levels[_step(invoice, levels, reached)["next_level"]]
    today = berlin_today()
    enabled = charges_enabled(db)
    # Seit 1.8.81 ("Vorweg" 1): neben einer gebuchten Pauschale keine Gebühr als Vorschlag (§ 288 Abs. 5 S. 3 BGB).
    ignore = [r.id for r in replaceable(invoice, reached, cfg.level)]
    propose_fee = enabled and fee_block_reason(db, invoice, flat_fee_accepted=False, ignore_reminder_ids=ignore) is None
    reminder = Reminder(
        invoice_id=invoice.id, level=cfg.level, status="entwurf", reminder_date=today,
        new_due_date=today + timedelta(days=cfg.days_after_previous_step),
        # Seit 1.8.78 der mahnfähige Betrag (offen − Einbehalt), vorher das volle Brutto.
        outstanding_amount=state.dunnable, amounts_json=amounts_snapshot(db, invoice, state, enabled=enabled, on=today),
        # Seit 1.8.80 nur ein Vorschlag (eingeschaltet), bewusst übernommen über set_reminder_charges(); aus: keine Gebühr.
        fee_amount=cfg.fee_amount if propose_fee else Decimal("0"), fee_accepted=False, flat_fee_accepted=False,
        interest_accepted=False, text=cfg.text_template,
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
    (finalize_dates()); die Aufstellung wird unter der Sperre frisch geschrieben (der Betrag ist geprüft gleich).

    Seit 1.8.80: festgeschriebene Mahnungen bis zu dieser Stufe, die nie hinausgingen, gelten danach als ersetzt (replaced_by_id),
    ihre Nebenforderungen werden gegengebucht. Eingeschaltet entstehen aus der übernommenen Gebühr und Pauschale
    Nebenforderungen dieser Mahnung (die Pauschale noch einmal geprüft, sonst 409); ausgeschaltet trägt die Mahnung keine Gebühr.
    Seit 1.8.89: ein Entwurf zu einer inzwischen in einer Endrechnung abgezogenen Rechnung ist überholt (409)."""
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
    state = dunning_state(db, invoice)
    reached = reached_map(db, invoice.reminders)
    reason = create_block_reason(db, invoice, state=state, levels=levels, draft=reminder, reached=reached) or \
        stale_amount_reason(db, reminder, state=state)
    if reason:
        raise _reject(db, reason)
    today = berlin_today()
    enabled = charges_enabled(db)
    if not enabled:
        reminder.fee_amount, reminder.fee_accepted, reminder.flat_fee_accepted = Decimal("0"), False, False
        reminder.interest_accepted = False
    elif not reminder.fee_accepted:
        reminder.fee_amount = Decimal("0")
    reminder.reminder_date, reminder.new_due_date = finalize_dates(reminder, levels, today)
    reminder.reminder_number = issue_number(db, "reminder")
    reminder.status = FINALIZED
    replaced = replaceable(invoice, reached, reminder.level, exclude_id=reminder.id)
    if replaced:
        now = datetime.utcnow()
        for old in replaced:
            old.replaced_by_id, old.replaced_at = reminder.id, now
        numbers = ", ".join(r.reminder_number or "" for r in replaced)
        try:
            reverse_charges_of(db, replaced, reason=f"Mahnung {numbers} ging nie hinaus und ist durch die Mahnung "
                                                    f"{reminder.reminder_number} ersetzt.")
        except ChargeRejected as e:  # seit 1.8.81: eine Zahlung auf eine Nebenforderung der ersetzten Mahnung
            raise _reject(db, f"Die Mahnung {numbers} lässt sich nicht ersetzen: {e}") from None
    if enabled and reminder.flat_fee_accepted:
        reason = flat_fee_block_reason(db, invoice, on=today)
        if reason:
            raise _reject(db, reason)
    # Seit 1.8.81 ("Vorweg" 1): keine Gebühr neben einer gebuchten oder dieser Pauschale.
    if enabled and reminder.fee_accepted and Decimal(reminder.fee_amount or 0) > 0:
        reason = fee_block_reason(db, invoice, flat_fee_accepted=bool(reminder.flat_fee_accepted))
        if reason:
            raise _reject(db, reason)
    # Seit 1.8.81 (Punkt 7): die Zinsen frisch bis zum Mahndatum (heute), unter der Sperre -- eine inzwischen gebuchte Zahlung,
    # ein verworfener Verzugsbeginn oder ein fehlender Basiszinssatz zählen.
    interest = None
    if enabled and reminder.interest_accepted:
        interest = interest_proposal(db, invoice, until=today)
        if interest["block"]:
            raise _reject(db, f"Die übernommenen Verzugszinsen sind nicht mehr möglich: {interest['block']} Bitte den Entwurf "
                              "anpassen.")
    if enabled:
        add_charges(db, reminder, interest=interest)
    reminder.amounts_json = amounts_snapshot(db, invoice, state, enabled=enabled, on=today)
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
    db: Session, reminder: Reminder, *, text: str | None, payment_days: int,
) -> Reminder:
    """Bearbeiten eines noch nicht festgeschriebenen Mahnungsentwurfs (seit 1.3.21). Seit 1.8.79 (Vorgabe Z2a Nr. 3) unter der
    Sperre der Auftragszeile wie Festschreiben und Löschen: geändert wird nur, was danach noch Entwurf ist, sonst
    InvoiceBlocked (409) -- vorher wartete eine Änderung auf ein gleichzeitiges Festschreiben und schrieb danach in die
    festgeschriebene Mahnung. Die Frist ist eine Länge in Tagen (1–365): sie rechnet ab dem Tag des Festschreibens.
    Seit 1.8.80 nur Text und Frist; Gebühr und Pauschale über set_reminder_charges() (nur eingeschaltet).

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
    reminder.new_due_date = reminder.reminder_date + timedelta(days=int(payment_days))
    db.commit()
    db.refresh(reminder)
    return reminder


def set_reminder_charges(db: Session, reminder: Reminder, *, fee_amount: Decimal, fee_accepted: bool,
                         flat_fee_accepted: bool, interest_accepted: bool = False) -> Reminder:
    """Gebühr und Pauschale im Entwurf bewusst übernehmen oder nicht (seit 1.8.80, Z2b Nr. 5 und 6) -- nur bei eingeschalteten
    Mahngebühren (sonst 409), unter der Sperre der Auftragszeile, nur im Entwurf. Die Pauschale nur, wenn sie heute möglich ist
    (app/dunning_charges.py::flat_fee_block_reason(), 409 mit Grund); beim Festschreiben wird sie noch einmal geprüft.
    Seit 1.8.81: keine Gebühr neben einer gebuchten oder hier übernommenen Pauschale (fee_block_reason(), 409); Verzugszinsen
    (interest_accepted) nur, wenn es heute einen Vorschlag gibt (interest_proposal(), 409 mit Grund)."""
    fee_amount = Decimal(fee_amount)
    if fee_amount < 0 or fee_amount != round_money(fee_amount):
        raise ValueError("Die Gebühr: höchstens zwei Nachkommastellen, nicht negativ.")
    if not charges_enabled(db):
        raise InvoiceBlocked(DISABLED_TEXT)
    lock_order_invoices(db, reminder.invoice.order_id)
    _refresh_or_gone(db, reminder)
    if reminder.status != "entwurf":
        raise _reject(db, "Nur Mahnungen im Entwurf können bearbeitet werden. Die Mahnung ist inzwischen festgeschrieben "
                          f"({reminder.reminder_number}).")
    ignore = [r.id for r in replaceable(reminder.invoice, reached_map(db, reminder.invoice.reminders), reminder.level)]
    if flat_fee_accepted:
        reason = flat_fee_block_reason(db, reminder.invoice, on=berlin_today(), ignore_reminder_ids=ignore)
        if reason:
            raise _reject(db, reason)
    if fee_accepted and fee_amount > 0:
        reason = fee_block_reason(db, reminder.invoice, flat_fee_accepted=bool(flat_fee_accepted), ignore_reminder_ids=ignore)
        if reason:
            raise _reject(db, reason)
    if interest_accepted:
        proposal = interest_proposal(db, reminder.invoice, until=berlin_today(), ignore_reminder_ids=ignore)
        if proposal["block"]:
            raise _reject(db, proposal["block"])
    reminder.fee_amount = fee_amount
    reminder.fee_accepted = bool(fee_accepted)
    reminder.flat_fee_accepted = bool(flat_fee_accepted)
    reminder.interest_accepted = bool(interest_accepted)
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


def _block_of(db: Session, reminder: Reminder, state, levels: dict[int, ReminderLevel],
              reached: dict[int, date] | None = None) -> str | None:
    """Was die Oberfläche statt "Versenden" (Entwurf) bzw. statt E-Mail und Zustellung (festgeschrieben) zeigt."""
    if reminder.status == "entwurf":
        return (send_block_reason(reminder.invoice)
                or create_block_reason(db, reminder.invoice, state=state, levels=levels, draft=reminder, reached=reached)
                or stale_amount_reason(db, reminder, state=state))
    return send_block_reason(reminder.invoice) or dispatch_block_reason(db, reminder, state=state, levels=levels,
                                                                        reached=reached)


def reminder_to_dict(reminder: Reminder, *, state=_UNSET, levels: dict[int, ReminderLevel] | None = None,
                     reached: dict[int, date] | None = None) -> dict:
    """state/levels/reached: schon geladen (Listen, reminders_to_dicts()), sonst frisch."""
    invoice = reminder.invoice
    db = object_session(reminder)
    if db is not None and state is _UNSET:
        state = dunning_state(db, invoice)
    if db is not None and levels is None:
        levels = _levels(db)
    if db is not None and reached is None:
        reached = reached_map(db, invoice.reminders)
    reached = reached or {}
    reminder_date, new_due_date = effective_dates(reminder, levels or {})
    breakdown = amounts(reminder)
    replaced_by = db.get(Reminder, reminder.replaced_by_id) if db is not None and reminder.replaced_by_id else None
    draft = db is not None and reminder.status == "entwurf"
    to_replace = replaceable(invoice, reached, reminder.level) if draft else []
    proposals = (draft_proposals(db, reminder, on=reminder_date, ignore_reminder_ids=[r.id for r in to_replace])
                 if draft else None)
    # Seit 1.8.81: der Zinsvorschlag einmal berechnet -- für die Vorschläge und die neue Zeile im Entwurf.
    view = (charges_view(reminder, db, interest=proposals["interest"] if reminder.interest_accepted else None)
            if proposals is not None else charges_view(reminder, db))
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
        "total_amount": view["total"],
        "amounts": breakdown,
        # Seit 1.8.80: hinausgegangen (versendet oder zugestellt) am, ersetzt durch, Nebenforderungen und Vorschläge.
        "reached_on": reached.get(reminder.id),
        "replaced_by_id": reminder.replaced_by_id,
        "replaced_by_number": replaced_by.reminder_number if replaced_by else None,
        "fee_accepted": bool(reminder.fee_accepted),
        "flat_fee_accepted": bool(reminder.flat_fee_accepted),
        "interest_accepted": bool(reminder.interest_accepted),
        "charges_enabled": view["enabled"],
        "charges": view["lines"],
        "charges_paid": view["paid"],
        "charges_open": view["open"],
        "proposals": proposals,
        # Seit 1.8.81: gedruckte Rechtstexte und Warnungen (ungeprüft, nicht gedruckt); im Entwurf, was das Festschreiben ersetzt
        # und welche Nebenforderungen es dabei gegenbucht (für die Rückfrage vor dem Festschreiben).
        "legal_texts": view["legal_texts"],
        "legal_text_warnings": view["legal_warnings"],
        "replaces": replaces_info(db, to_replace) if draft else [],
        "text": reminder.text,
        "formatted_text": format_reminder_text(reminder),
        "customer_name": invoice.customer_name,
        "email_sent_at": reminder.email_sent_at,
        "email_sent_to": reminder.email_sent_to,
        "recipient_email": get_reminder_recipient_email(reminder),
        "send_block": (_block_of(db, reminder, state, levels or {}, reached) if db is not None
                       else send_block_reason(invoice)),
    }


def reminders_to_dicts(db: Session, reminders: list[Reminder]) -> list[dict]:
    """Viele Mahnungen auf einmal: Zahlstand aller Rechnungen in zwei Abfragen, Stufen einmal, erreicht für alle zusammen."""
    invoices = {r.invoice_id: r.invoice for r in reminders}
    states = dunning_states(db, invoices.values())
    levels = _levels(db)
    reached = reached_map(db, [r for inv in invoices.values() for r in inv.reminders])
    return [reminder_to_dict(r, state=states.get(r.invoice_id), levels=levels, reached=reached) for r in reminders]


def list_invoices_needing_attention(db: Session) -> list[dict]:
    """Überfällige Rechnungen mit mahnfähigem Betrag, ihrer Mahnstufe und ab wann die nächste möglich ist; is_due_now und
    create_block (leer) heißt "zur Mahnung fällig" (seit 1.8.79). Liest nur -- seit 1.8.79 legt nichts mehr von selbst einen
    Entwurf an. Sortiert: zur Mahnung fällig zuerst, dann nach Fälligkeit. caseworker_employee_id ist seit 1.8.79 der
    Sachbearbeiter des Auftrags (die Spalte an der Rechnung setzt niemand). Seit 1.8.89 ohne die in einer gültigen Endrechnung
    abgezogenen Rechnungen; die Endrechnung mit ihrem Zahlbetrag, auch wenn sie selbst schon bezahlt ist (app/final_dunning.py)."""
    overdue = db.scalars(
        select(Invoice).where(Invoice.status == FINALIZED, Invoice.invoice_type != "storno", Invoice.due_date < berlin_today())
        .options(selectinload(Invoice.reminders), selectinload(Invoice.order))
    ).all()
    # Seit 1.8.78 nur mit mahnfähigem Betrag (offen − Einbehalt), und dieser statt des Bruttos; seit 1.8.89 der angemahnte Betrag.
    states = dunning_states(db, overdue)
    levels = _levels(db)
    reached = reached_map(db, [r for inv in overdue for r in inv.reminders])
    rows = []
    for invoice in overdue:
        state = states[invoice.id]
        if state.dunnable <= 0:
            continue
        status = compute_reminder_status(db, invoice, state=state, levels=levels, reached=reached)
        rows.append({
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "order_id": invoice.order_id,
            "customer_name": invoice.customer_name,
            "due_date": invoice.due_date,
            "outstanding_amount": state.dunnable,
            "caseworker_employee_id": invoice.order.caseworker_employee_id if invoice.order else None,
            **status,
            "due_for_reminder": due_for_reminder(status),
        })
    rows.sort(key=lambda r: (not r["due_for_reminder"], r["due_date"]))
    return rows


def due_for_reminder(status: dict) -> bool:
    """"Zur Mahnung fällig" (seit 1.8.79): nächste Stufe jetzt möglich und kein Grund dagegen -- seit 1.8.80 nicht, solange eine
    festgeschriebene Mahnung noch hinausgehen kann (dann ist sie zu versenden, nicht zu ersetzen)."""
    pending = status.get("pending")
    return bool(status["is_due_now"] and status["create_block"] is None
                and not (pending and pending["dispatch_block"] is None))
