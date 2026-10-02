"""Bedenkenanzeige (seit 1.8.43, Stufe 2b, Runde 2b-4).

Herleitung: docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.43". Die Bedenkenanzeige ist eine
Checkliste mit Zweck "bedenkenanzeige" (Systemfelder in app/checklist_purposes.py) nach dem Muster der
Behinderungsanzeige: Meldung (meist der Monteur) → Unterschrift des Meldenden, Anzeige (Büro: Bedenken gegen,
Begründung, mögliche Folgen, Vorschlag zur Abhilfe, Entscheidung erbeten bis) → Unterschrift Büro, Entscheidung
des Auftraggebers (Büro) → Unterschrift.

Hier stehen die Folgen (ausgeführt über app/checklist_follow_ups.py -- Idempotenz, "modul_aus", Nachholen):
- nach der Unterschrift der Meldung "Bedenkenanzeige versenden" (wie die Behinderungsanzeige,
  app/obstruction_notices.py::create_notice_send_task());
- nach dem Versand (Brief beim Auftraggeber angekommen) "Antwort des Auftraggebers prüfen", fällig am Datum
  "Entscheidung erbeten bis";
- nach der Unterschrift der Entscheidung diese Aufgabe erledigen.

Dazu "offene Bedenken" (open_concerns()): eine Bedenkenanzeige im Entwurf ohne gültige Unterschrift der
Entscheidung -- Auftragsseite und /mobil zeigen dann einen deutlichen Hinweis. Rollenlos."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .berlin_time import berlin_today
from .checklist_follow_ups import complete_follow_up_tasks, triggering_signature
from .checklist_purposes import (
    CONCERN_DEADLINE, CONCERN_DECISION_SIGNATURE, CONCERN_PURPOSE, CONCERN_REPORT_SIGNATURE,
)
from .models import Checklist, ChecklistAnswer, ChecklistAttachment, ChecklistTemplateField, ChecklistTemplateVersion, Order
from .obstruction_notices import OFFICE_ROLE, create_notice_send_task

SEND_TASK_TITLE = "Bedenkenanzeige versenden"
ANSWER_TASK_TITLE = "Antwort des Auftraggebers prüfen"
ANSWER_FOLLOW_UP_KEY = CONCERN_PURPOSE + ".antwort_pruefen"
OPEN_CONCERNS_TEXT = ("Offene Bedenken – vor Ausführung der betroffenen Leistung Entscheidung des Auftraggebers "
                      "abwarten oder mit dem Büro klären.")


def create_send_task(db: Session, checklist: Checklist) -> tuple[str, int] | None:
    """Folge der Meldung: Aufgabe "Bedenkenanzeige versenden", fällig am Tag der Unterschrift."""
    return create_notice_send_task(db, checklist, letter_kind=CONCERN_PURPOSE, report_signature=CONCERN_REPORT_SIGNATURE,
                                   title=SEND_TASK_TITLE, label="Bedenkenanzeige", reported="Bedenken")


def _deadline(checklist: Checklist):
    answer = next((a for a in checklist.answers if a.field_key == CONCERN_DEADLINE), None)
    return answer.value_date if answer is not None else None


def create_answer_task(db: Session, checklist: Checklist) -> tuple[str, int] | None:
    """Folge des Versands: Aufgabe "Antwort des Auftraggebers prüfen", fällig am Datum "Entscheidung erbeten bis"
    (fehlt es, heute). Keine Aufgabe, wenn die Entscheidung schon unterschrieben ist (None)."""
    from .tasks import create_task  # lokal: app.tasks zieht E-Mail-Versand u. a. nach

    if triggering_signature(checklist, CONCERN_DECISION_SIGNATURE) is not None:
        return None
    order = db.get(Order, checklist.order_id) if checklist.order_id is not None else None
    context = checklist.context_label_snapshot or "Auftrag"
    deadline = _deadline(checklist)
    due = deadline or berlin_today()
    description = (f"Die Bedenkenanzeige ({context}) ist beim Auftraggeber angekommen; Entscheidung erbeten bis "
                   f"{due.strftime('%d.%m.%Y')}. Die Antwort im Abschnitt „Entscheidung“ festhalten und unterschreiben "
                   f"– kommt keine, „keine Antwort“ eintragen.")
    task = create_task(
        db, title=ANSWER_TASK_TITLE, description=description, priority="normal", due_date=due,
        assigned_employee_id=order.caseworker_employee_id if order is not None else None,
        project_id=order.project_id if order is not None else None,
        created_by_user_id=checklist.created_by_user_id, source_module="checklisten",
        source_label=f"Bedenkenanzeige – {context}"[:255], source_url=f"/checklisten/{checklist.id}",
        min_visible_role=OFFICE_ROLE,
    )
    return "task", task["id"]


def complete_answer_tasks(db: Session, checklist: Checklist) -> None:
    """Folge der Unterschrift der Entscheidung: die Aufgabe "Antwort des Auftraggebers prüfen" ist erledigt. Legt
    nichts an (None)."""
    complete_follow_up_tasks(db, checklist.id, ANSWER_FOLLOW_UP_KEY)
    return None


def open_concerns(db: Session, order_ids: list[int]) -> dict[int, list[dict]]:
    """Offene Bedenken je Auftrag: Bedenkenanzeigen im Entwurf (nicht abgeschlossen, nicht gegenstandslos) ohne
    gültige Unterschrift der Entscheidung -- mit Nummer, Vorlage und "Entscheidung erbeten bis". Drei Abfragen,
    unabhängig von der Zahl der Aufträge."""
    if not order_ids:
        return {}
    rows = db.execute(
        select(Checklist.id, Checklist.order_id, Checklist.template_label_snapshot)
        .join(ChecklistTemplateVersion, ChecklistTemplateVersion.id == Checklist.template_version_id)
        .where(Checklist.order_id.in_(order_ids), Checklist.status == "entwurf",
               ChecklistTemplateVersion.purpose == CONCERN_PURPOSE)
        .order_by(Checklist.id)
    ).all()
    if not rows:
        return {}
    ids = [r.id for r in rows]
    decided = set(db.scalars(
        select(ChecklistAttachment.checklist_id)
        .join(ChecklistTemplateField, ChecklistTemplateField.id == ChecklistAttachment.template_field_id)
        .where(ChecklistAttachment.checklist_id.in_(ids), ChecklistAttachment.kind == "unterschrift",
               ChecklistAttachment.discarded_at.is_(None), ChecklistTemplateField.field_key == CONCERN_DECISION_SIGNATURE)
    ).all())
    deadlines = dict(db.execute(
        select(ChecklistAnswer.checklist_id, ChecklistAnswer.value_date)
        .where(ChecklistAnswer.checklist_id.in_(ids), ChecklistAnswer.field_key == CONCERN_DEADLINE)
    ).all())
    result: dict[int, list[dict]] = {}
    for r in rows:
        if r.id in decided:
            continue
        deadline = deadlines.get(r.id)
        result.setdefault(r.order_id, []).append({
            "checklist_id": r.id, "template_label": r.template_label_snapshot,
            "decision_due": deadline.isoformat() if deadline else None,
        })
    return result
