"""Test-Helfer seit 1.8.79 (Zahlungsstufe Z2a): die nächste Mahnstufe ist erst nach Ablauf der Frist der vorigen möglich.

frist_ablaufen(db, reminder) verlegt Mahndatum und Frist einer festgeschriebenen Mahnung in die Vergangenheit -- so, als wären
seit ihrem Festschreiben Wochen ohne Zahlung vergangen. Direkt in der Datenbank (beim Festschreiben setzt der Code Mahndatum =
heute). festschreiben_und_ablaufen() schreibt einen Entwurf fest und lässt seine Frist ablaufen: danach ist die nächste Stufe
möglich."""

from datetime import timedelta

from sqlalchemy import update

from app.berlin_time import berlin_today
from app.models import Reminder
from app.reminders import finalize_and_send_reminder


def frist_ablaufen(db, reminder, *, tage_her: int = 1, frist: int = 7):
    """Frist endete vor tage_her Tagen, Mahndatum frist Tage davor."""
    ende = berlin_today() - timedelta(days=tage_her)
    db.execute(update(Reminder).where(Reminder.id == reminder.id)
               .values(reminder_date=ende - timedelta(days=frist), new_due_date=ende))
    db.commit()
    db.refresh(reminder)
    return reminder


def festschreiben_und_ablaufen(db, reminder, **kwargs):
    finalize_and_send_reminder(db, reminder)
    frist_ablaufen(db, reminder, **kwargs)
    db.refresh(reminder.invoice)
    return reminder
