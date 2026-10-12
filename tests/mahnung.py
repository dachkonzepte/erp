"""Test-Helfer seit 1.8.79 (Zahlungsstufe Z2a): die nächste Mahnstufe ist erst nach Ablauf der Frist der vorigen möglich.

frist_ablaufen(db, reminder) verlegt Mahndatum und Frist einer festgeschriebenen Mahnung in die Vergangenheit -- so, als wären
seit ihrem Festschreiben Wochen ohne Zahlung vergangen. Direkt in der Datenbank (beim Festschreiben setzt der Code Mahndatum =
heute). festschreiben_und_ablaufen() schreibt einen Entwurf fest, stellt ihn zu und lässt seine Frist ablaufen: danach ist die
nächste Stufe möglich.

Seit 1.8.80 (Z2b "Vorweg" 2) ist eine Stufe erst mit Versand oder Zustellung erreicht: zustellen(db, reminder) trägt eine
Zustellung (Einschreiben, an den Auftraggeber) direkt ins Versandprotokoll ein -- so, wie record_manual_delivery() sie
hinterlässt, ohne PDF und Ablage."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import update

from app.berlin_time import berlin_today
from app.models import EmailDispatch, Reminder
from app.reminders import finalize_and_send_reminder


def frist_ablaufen(db, reminder, *, tage_her: int = 1, frist: int = 7):
    """Frist endete vor tage_her Tagen, Mahndatum frist Tage davor."""
    ende = berlin_today() - timedelta(days=tage_her)
    db.execute(update(Reminder).where(Reminder.id == reminder.id)
               .values(reminder_date=ende - timedelta(days=frist), new_due_date=ende))
    db.commit()
    db.refresh(reminder)
    return reminder


def zustellen(db, reminder, *, on=None, channel: str = "einschreiben", to_client: bool | None = True, status: str = "gesendet"):
    """Eine festgeschriebene Mahnung gilt als zugestellt (Versandprotokoll, nachgetragene Zustellung) -- am Tag on, sonst an
    ihrem Mahndatum. channel "smtp" spielt einen E-Mail-Versand nach (ohne delivered_on, Abschluss = jetzt)."""
    manual = channel != "smtp"
    row = EmailDispatch(
        dispatch_key=f"test-{uuid.uuid4()}", message_ref=str(uuid.uuid4()), status=status, channel=channel,
        document_type="mahnung", document_id=reminder.id, document_number=reminder.reminder_number,
        to_recipients="Kunde" if manual else "kunde@example.com", subject="Mahnung", finished_at=datetime.utcnow(),
        delivered_on=(on or reminder.reminder_date) if manual else None, delivered_to_client=to_client if manual else None,
    )
    db.add(row)
    db.commit()
    return row


def festschreiben_und_ablaufen(db, reminder, **kwargs):
    finalize_and_send_reminder(db, reminder)
    frist_ablaufen(db, reminder, **kwargs)
    zustellen(db, reminder)
    db.refresh(reminder.invoice)
    return reminder
