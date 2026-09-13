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
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .invoices import compute_invoice_totals, get_invoice
from .models import Invoice, Reminder, ReminderLevel
from .settings import get_or_create_general_settings, issue_number

HOUR = Decimal("0.01")  # für Geldbeträge wiederverwendet, siehe quantize-Aufrufe unten

DEFAULT_REMINDER_LEVELS = [
    # (level, label, days_after_previous_step, fee_amount, text_template)
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
    Verwendung mit einem Steuerberater/Rechtsanwalt abgleichen."""
    if db.scalar(select(ReminderLevel.id).limit(1)) is not None:
        return
    for level, label, days, fee, text in DEFAULT_REMINDER_LEVELS:
        db.add(ReminderLevel(
            level=level, label=label, days_after_previous_step=days,
            fee_amount=fee, text_template=text, active=True, sort_order=level * 10,
        ))
    db.commit()


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


def compute_reminder_status(db: Session, invoice: Invoice) -> dict:
    """Ermittelt, auf welcher Mahnstufe sich eine Rechnung aktuell befindet
    und wann die nächste (aktive) Stufe fällig wird. Deaktivierte Stufen
    werden dabei übersprungen -- ist z.B. Stufe 2 deaktiviert, springt die
    nächste fällige Stufe nach Stufe 1 direkt auf Stufe 3.

    Enthält seit 1.0.70 zusätzlich 'draft': die bereits bestehende, noch
    nicht versendete Mahnung zu dieser Rechnung (als reminder_to_dict()),
    oder None -- damit z.B. die Mahnwesen-Übersicht direkt weiß, ob pro
    Rechnung ein "erstellen"- oder ein "versenden/löschen"-Zustand
    angezeigt werden muss, ohne dafür eine eigene Anfrage zu benötigen."""
    if invoice.status != "versendet" or invoice.due_date is None:
        return {"current_level": 0, "next_level": None, "next_due_on": None, "is_due_now": False, "draft": None}

    active_levels = {
        lvl.level: lvl for lvl in db.scalars(select(ReminderLevel).where(ReminderLevel.active == True)).all()  # noqa: E712
    }
    sent = [r for r in invoice.reminders if r.status == "versendet"]
    current_level = max((r.level for r in sent), default=0)

    reference_date = invoice.due_date
    if current_level:
        last_at_level = max((r for r in sent if r.level == current_level), key=lambda r: r.reminder_date)
        reference_date = last_at_level.reminder_date

    next_level = min((lvl for lvl in active_levels if lvl > current_level), default=None)
    next_due_on = None
    is_due_now = False
    if next_level is not None:
        cfg = active_levels[next_level]
        next_due_on = reference_date + timedelta(days=cfg.days_after_previous_step)
        is_due_now = date.today() >= next_due_on

    draft = next((r for r in invoice.reminders if r.status == "entwurf"), None)

    return {
        "current_level": current_level, "next_level": next_level,
        "next_due_on": next_due_on, "is_due_now": is_due_now,
        "draft": reminder_to_dict(draft) if draft is not None else None,
    }


def _reminder_placeholders(reminder: Reminder) -> dict:
    """Gemeinsame Platzhalter-Werte für PDF-Text UND E-Mail-Betreff/-Text
    (seit 1.0.74, vorher nur für format_reminder_text() intern)."""
    invoice = reminder.invoice
    total = (reminder.outstanding_amount + reminder.fee_amount).quantize(HOUR)
    money = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"  # noqa: E731
    previous = [r for r in invoice.reminders if r.status == "versendet" and r.level == reminder.level - 1]
    previous_date = previous[0].reminder_date.strftime("%d.%m.%Y") if previous else ""
    return {
        "{rechnungsnummer}": invoice.invoice_number or "",
        "{rechnungsdatum}": invoice.invoice_date.strftime("%d.%m.%Y"),
        "{faelligkeitsdatum}": invoice.due_date.strftime("%d.%m.%Y") if invoice.due_date else "",
        "{offener_betrag}": money(reminder.outstanding_amount),
        "{mahngebuehr}": money(reminder.fee_amount),
        "{gesamtbetrag}": money(total),
        "{neue_frist}": reminder.new_due_date.strftime("%d.%m.%Y") if reminder.new_due_date else "",
        "{vorheriges_mahndatum}": previous_date,
    }


def _apply_placeholders(text: str, replacements: dict) -> str:
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def format_reminder_text(reminder: Reminder) -> str:
    """Ersetzt Platzhalter in reminder.text mit den echten Werten -- analog
    zu format_payment_terms_sentence() in app/invoices.py. Ein unbekannter
    Platzhalter bleibt einfach stehen, kein Fehler."""
    return _apply_placeholders(reminder.text or "", _reminder_placeholders(reminder))


def create_reminder(db: Session, invoice: Invoice, level: int) -> Reminder:
    if invoice.status != "versendet":
        raise ValueError("Nur zu versendeten Rechnungen kann eine Mahnung erstellt werden.")
    cfg = db.scalar(select(ReminderLevel).where(ReminderLevel.level == level, ReminderLevel.active == True))  # noqa: E712
    if cfg is None:
        raise ValueError(f"Mahnstufe {level} ist nicht aktiv oder existiert nicht.")
    today = date.today()
    reminder = Reminder(
        invoice_id=invoice.id, level=level, status="entwurf", reminder_date=today,
        new_due_date=today + timedelta(days=cfg.days_after_previous_step),
        outstanding_amount=compute_invoice_totals(invoice)["gross_total"],
        fee_amount=cfg.fee_amount, text=cfg.text_template,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def finalize_and_send_reminder(db: Session, reminder: Reminder) -> Reminder:
    if reminder.status != "entwurf":
        raise ValueError("Nur Mahnungen im Entwurf können versendet werden.")
    reminder.reminder_number = issue_number(db, "reminder")
    reminder.status = "versendet"
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
    Absturz bringen, sondern nur zu 'keine Adresse hinterlegt' führen."""
    order = reminder.invoice.order
    customer = order.project.customer if order and order.project else None
    return (customer.email or None) if customer else None


def send_reminder_email(db: Session, reminder: Reminder, *, to_email: str | None = None) -> Reminder:
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
    nicht auf reminders.py zurückgreifen soll."""
    from .email_sending import send_email_with_attachment
    from .reminder_pdf import build_reminder_pdf

    if reminder.status != "versendet":
        raise ValueError("Nur bereits finalisierte Mahnungen können per E-Mail versendet werden.")

    recipient = (to_email or "").strip() or get_reminder_recipient_email(reminder)
    if not recipient:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")

    level_cfg = db.scalar(select(ReminderLevel).where(ReminderLevel.level == reminder.level))
    level_label = level_cfg.label if level_cfg else f"{reminder.level}. Mahnung"
    placeholders = _reminder_placeholders(reminder) | {"{mahnstufe}": level_label}

    subject_template = (level_cfg.email_subject_template if level_cfg else None) or DEFAULT_REMINDER_EMAIL_SUBJECT
    body_template = (level_cfg.email_body_template if level_cfg else None) or DEFAULT_REMINDER_EMAIL_BODY
    subject = _apply_placeholders(subject_template, placeholders)
    body = _apply_placeholders(body_template, placeholders)

    pdf_bytes = build_reminder_pdf(db, reminder)
    send_email_with_attachment(
        db, to_email=recipient, subject=subject, body_text=body,
        attachment_bytes=pdf_bytes, attachment_filename=f"{reminder.reminder_number}.pdf",
    )

    reminder.email_sent_at = datetime.utcnow()
    reminder.email_sent_to = recipient
    db.commit()
    db.refresh(reminder)
    return reminder


def update_reminder_draft(
    db: Session, reminder: Reminder, *, text: str | None, fee_amount: Decimal, new_due_date: date | None,
) -> Reminder:
    """Bearbeiten eines noch nicht versendeten Mahnungsentwurfs (seit 1.3.21) -- gleiches Muster
    wie update_report() beim Einsatzbericht (app/service_reports.py): der Status-Schutz sitzt HIER,
    in der Geschäftslogik, nicht nur als Oberflächen-Beschränkung, damit ein direkter API-Aufruf
    ihn nicht umgehen kann. Eine bereits versendete Mahnung ist unveränderlich (GoBD, Regel 5).

    text bleibt bewusst das ROHE Textfeld mit unaufgelösten Platzhaltern (`{mahngebuehr}` usw.,
    siehe ReminderLevel.text_template/format_reminder_text()) -- exakt dieselbe Konvention wie
    beim Bearbeiten einer Mahnstufe selbst (Einstellungen → Mahnstufen). fee_amount/new_due_date
    werden unabhängig vom Text geändert; was das für den bei jedem Lesezugriff frisch aus text +
    diesen Feldern zusammengesetzten formatted_text bedeutet, ist bewusst NICHT Teil dieser
    Funktion (siehe CLAUDE.md, Abschnitt "Mahnwesen")."""
    if reminder.status != "entwurf":
        raise ValueError("Nur Mahnungen im Entwurf können bearbeitet werden.")
    reminder.text = text
    reminder.fee_amount = fee_amount
    reminder.new_due_date = new_due_date
    db.commit()
    db.refresh(reminder)
    return reminder


def delete_reminder_draft(db: Session, reminder: Reminder) -> None:
    if reminder.status != "entwurf":
        raise ValueError("Nur Mahnungen im Entwurf können gelöscht werden.")
    db.delete(reminder)
    db.commit()


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
    return db.scalars(select(Reminder).order_by(Reminder.reminder_date.desc(), Reminder.id.desc())).all()


def get_reminder_auto_create_setting(db: Session) -> bool:
    return get_or_create_general_settings(db).reminders_auto_create_drafts


def set_reminder_auto_create_setting(db: Session, enabled: bool) -> bool:
    general = get_or_create_general_settings(db)
    general.reminders_auto_create_drafts = enabled
    db.commit()
    return general.reminders_auto_create_drafts


def auto_create_due_reminder_drafts(db: Session) -> list[Reminder]:
    """Automatisierung (seit 1.0.71): legt für jede Rechnung, deren nächste
    Mahnstufe bereits fällig ist und die noch keinen Entwurf hat, direkt
    einen Mahnungs-ENTWURF an -- spart den bisher nötigen manuellen Klick
    auf "erstellen" pro Rechnung.

    Erstellt bewusst ausschließlich Entwürfe, niemals versendete Mahnungen
    -- das Versenden (Nummernvergabe, Unveränderlichkeit) bleibt immer ein
    bewusster, manueller Schritt, unabhängig von dieser Einstellung.

    Läuft nur, wenn reminders_auto_create_drafts aktiv ist (Standard: an).
    Übersprungene Einzelfälle (z.B. Stufe zwischenzeitlich deaktiviert)
    brechen den gesamten Lauf nicht ab, sondern werden einfach ausgelassen.

    Wird gezielt beim Aufruf der Mahnwesen-Seite ausgelöst (siehe
    POST /api/reminders/auto-create), nicht bei jedem einfachen Lesezugriff
    auf die Übersicht -- ein GET soll keine Nebenwirkungen haben."""
    if not get_reminder_auto_create_setting(db):
        return []
    created = []
    for row in list_invoices_needing_attention(db):
        if not row["is_due_now"] or row["draft"] is not None:
            continue
        invoice = get_invoice(db, row["invoice_id"])
        if invoice is None:
            continue
        try:
            created.append(create_reminder(db, invoice, row["next_level"]))
        except ValueError:
            continue
    return created


def reminder_to_dict(reminder: Reminder) -> dict:
    invoice = reminder.invoice
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
        "outstanding_amount": reminder.outstanding_amount,
        "fee_amount": reminder.fee_amount,
        "total_amount": (reminder.outstanding_amount + reminder.fee_amount).quantize(HOUR),
        "text": reminder.text,
        "formatted_text": format_reminder_text(reminder),
        "customer_name": invoice.customer_name,
        "email_sent_at": reminder.email_sent_at,
        "email_sent_to": reminder.email_sent_to,
        "recipient_email": get_reminder_recipient_email(reminder),
    }


def list_invoices_needing_attention(db: Session) -> list[dict]:
    """Für eine Mahnwesen-Übersicht: alle versendeten, überfälligen
    Rechnungen mit ihrer aktuellen Mahnstufe und dem Datum, ab dem die
    nächste Stufe fällig wird -- unabhängig davon, ob diese Stufe bereits
    heute erreicht ist (is_due_now zeigt das pro Zeile an, die Sortierung
    legt die dringendsten Fälle nach oben)."""
    overdue = db.scalars(
        select(Invoice).where(Invoice.status == "versendet", Invoice.due_date < date.today())
    ).all()
    rows = []
    for invoice in overdue:
        status = compute_reminder_status(db, invoice)
        rows.append({
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "order_id": invoice.order_id,
            "customer_name": invoice.customer_name,
            "due_date": invoice.due_date,
            "outstanding_amount": compute_invoice_totals(invoice)["gross_total"],
            "caseworker_employee_id": invoice.caseworker_employee_id,
            **status,
        })
    rows.sort(key=lambda r: (not r["is_due_now"], r["due_date"]))
    return rows
