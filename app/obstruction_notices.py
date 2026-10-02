"""Behinderungsanzeige (seit 1.8.38, Stufe 2b, Runde 2b-3 Teil 1).

Herleitung: docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.38". Die
Behinderungsanzeige ist eine Checkliste mit Zweck "behinderungsanzeige" (Systemfelder in
app/checklist_purposes.py): Meldung (meist der Monteur) → Unterschrift des Meldenden, Anzeige
(Büro) → Unterschrift Büro, Wegfall → Unterschrift. Brief und Versand seit 1.8.40 in
app/notice_letters.py -- der Versand erledigt die Aufgabe von hier.

Hier steht die Folge nach der Unterschrift der Meldung: eine Aufgabe "Behinderungsanzeige
versenden", fällig am Tag der Unterschrift (Europe/Berlin), an den Sachbearbeiter des Auftrags,
ohne ihn ohne Zuständigkeit für das Büro (buero_auftrag aufwärts). Ausgeführt über
app/checklist_follow_ups.py -- dort liegen Idempotenz, "modul_aus" und Nachholen. Seit 1.8.43
gemeinsam mit der Bedenkenanzeige (app/concern_notices.py) über create_notice_send_task(). Rollenlos."""

from sqlalchemy.orm import Session

from .berlin_time import berlin_now, to_berlin
from .checklist_follow_ups import triggering_signature
from .checklist_purposes import OBSTRUCTION_PURPOSE, OBSTRUCTION_REPORT_SIGNATURE
from .models import Checklist, Order

SEND_TASK_TITLE = "Behinderungsanzeige versenden"
SEND_TASK_PRIORITY = "hoch"  # Festlegung 1.8.38: die Anzeige muss unverzüglich hinaus
OFFICE_ROLE = "buero_auftrag"


def create_notice_send_task(db: Session, checklist: Checklist, *, letter_kind: str, report_signature: str,
                            title: str, label: str, reported: str) -> tuple[str, int] | None:
    """Aufgabe "<Anzeige> versenden" nach der Unterschrift der Meldung (create_task() committet selbst), liefert
    ("task", id). Nur Metadaten in der Beschreibung -- wer, wann, welcher Auftrag --, nicht der gemeldete Text.
    Keine Aufgabe, wenn der Brief schon beim Auftraggeber angekommen ist (Nachholen nach ausgeschaltetem
    Aufgabenmodul) -- dann gibt es nichts mehr zu tun (None). reported: "eine Behinderung" / "Bedenken"."""
    from .notice_letters import letter_was_sent  # lokal: das Briefmodul importiert die Folgen
    from .tasks import create_task  # lokal: app.tasks zieht E-Mail-Versand u. a. nach

    if letter_was_sent(db, letter_kind, checklist.id):
        return None

    signature = triggering_signature(checklist, report_signature)
    signed_at = to_berlin(signature.created_at) if signature is not None and signature.created_at else berlin_now()
    order = db.get(Order, checklist.order_id) if checklist.order_id is not None else None
    context = checklist.context_label_snapshot or "Auftrag"
    who = signature.signer_name if signature is not None and signature.signer_name else "unbekannt"
    description = (f"{who} hat am {signed_at.strftime('%d.%m.%Y')} um {signed_at.strftime('%H:%M')} Uhr {reported} "
                   f"gemeldet ({context}). Abschnitt „Anzeige“ in der {label} ausfüllen, als Büro unterschreiben und "
                   f"die Anzeige an den Auftraggeber senden.")
    task = create_task(
        db, title=title, description=description, priority=SEND_TASK_PRIORITY, due_date=signed_at.date(),
        assigned_employee_id=order.caseworker_employee_id if order is not None else None,
        project_id=order.project_id if order is not None else None,
        created_by_user_id=checklist.created_by_user_id, source_module="checklisten",
        source_label=f"{label} – {context}"[:255], source_url=f"/checklisten/{checklist.id}",
        min_visible_role=OFFICE_ROLE,
    )
    return "task", task["id"]


def create_send_task(db: Session, checklist: Checklist) -> tuple[str, int] | None:
    """Folge der Meldung der Behinderungsanzeige: Aufgabe "Behinderungsanzeige versenden"."""
    return create_notice_send_task(db, checklist, letter_kind=OBSTRUCTION_PURPOSE,
                                   report_signature=OBSTRUCTION_REPORT_SIGNATURE, title=SEND_TASK_TITLE,
                                   label="Behinderungsanzeige", reported="eine Behinderung")
