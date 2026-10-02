"""Folgen des Abschlusses einer Checkliste nach dem Zweck ihrer Fassung (seit 1.8.16, Modul
"checklisten") -- seit 1.8.38 auch Folgen nach der Unterschrift in einem bestimmten Systemfeld.

Herleitung: docs/archiv/modul-checklisten.md, "Umsetzung 1.8.16", und
docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.38". Welche Folgen ein Zweck hat,
steht in app/checklist_purposes.py (FollowUp); die erste echte ist "Behinderungsanzeige
versenden" nach der Unterschrift der Meldung.

Ablauf wie bei den Regeln (app/checklist_rules.py, Fund 4):
- Fällig ist eine Folge nach dem Abschluss (Standard) bzw. -- mit after_signature -- sobald im
  genannten Unterschriftsfeld eine gültige (nicht verworfene) Unterschrift steht, auch an einem
  Entwurf. Nur die Folgen des Zwecks der Fassung. Aufgerufen nach dem Commit des Abschlusses und
  jeder Unterschrift; "Nachholen" führt aus, was fällig und offen ist.
- Je (Checkliste, Folgeschlüssel) zuerst eine ChecklistFollowUp-Zeile belegen (Unique-Constraint,
  SAVEPOINT, eigener Commit), dann den Handler aufrufen (er darf selbst committen), dann Status
  "erledigt" und das Ziel vermerken. Ein zweiter Aufruf -- Doppelklick, Wiederholung,
  "Nachholen" -- findet die Zeile und führt nichts doppelt aus. Wird die auslösende Unterschrift
  verworfen und neu geleistet, bleibt es bei der einen Ausführung.
- "modul_aus" (die Folge braucht ein ausgeschaltetes Modul) und "ausstehend" (belegt, aber nicht
  bestätigt ausgeführt: Abbruch oder Fehler im Handler) sind offen und nachholbar; Nachholen belegt
  per bedingtem UPDATE auf (id, status, executed_at), nur einer gewinnt. Dasselbe Restrisiko wie
  bei den Regeln: Abbruch GENAU zwischen Handler und Vermerk → späteres Nachholen führt ihn erneut
  aus.
- Ein Fehler im Handler wird je Folge abgefangen: Rollback, Protokoll nur mit Schlüssel, ID und
  Klassenname der Ausnahme (Regel 18), die übrigen Folgen laufen weiter.

Rollenlos; Folgen sind Büro-intern -- Lesen und Nachholen nur über Büro-Endpunkte, nie im
Checklisten-Abruf (app/checklists.py::checklist_to_dict())."""

import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .checklist_purposes import FollowUp, get_purpose
from .checklists import VOID_STATUS, active_attachments
from .models import (
    Checklist, ChecklistAnswer, ChecklistAttachment, ChecklistFollowUp, ChecklistTemplateField,
    ChecklistTemplateVersion, Task,
)
from .modules import is_module_enabled

logger = logging.getLogger(__name__)

STATUS_DONE = "erledigt"
STATUS_MODULE_OFF = "modul_aus"
STATUS_PENDING = "ausstehend"
OPEN_STATUSES = (STATUS_MODULE_OFF, STATUS_PENDING)
STATUS_LABELS = {STATUS_DONE: "erledigt", STATUS_MODULE_OFF: "nicht ausgeführt (Modul aus)",
                 STATUS_PENDING: "nicht ausgeführt (unterbrochen)"}


def _load(db: Session, checklist_id: int) -> Checklist | None:
    return db.scalar(
        select(Checklist).options(
            selectinload(Checklist.template_version).selectinload(ChecklistTemplateVersion.fields)
            .selectinload(ChecklistTemplateField.options),
            selectinload(Checklist.answers).selectinload(ChecklistAnswer.selections),
            selectinload(Checklist.attachments),
            selectinload(Checklist.created_by_employee),
        ).where(Checklist.id == checklist_id)
    )


def _existing_rows(db: Session, checklist_id: int) -> dict[str, ChecklistFollowUp]:
    """Vorhandene Zeilen je Folgeschlüssel -- nur ein Lesestand; zwischen Lesen und Belegen kann
    ein anderer Aufruf schneller sein, dagegen steht _claim_new()."""
    return {r.follow_up_key: r for r in db.scalars(
        select(ChecklistFollowUp).where(ChecklistFollowUp.checklist_id == checklist_id)).all()}


def _claim_new(db: Session, checklist_id: int, key: str, status: str) -> ChecklistFollowUp | None:
    """Neue Zeile anlegen und committen. None = ein anderer Aufruf war schneller."""
    row = ChecklistFollowUp(checklist_id=checklist_id, follow_up_key=key, status=status, executed_at=datetime.utcnow())
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return None
    db.commit()
    return row


def _claim_open(db: Session, row: ChecklistFollowUp, status: str) -> bool:
    """Offene Zeile (modul_aus/ausstehend) per bedingtem UPDATE belegen -- nur ein Aufrufer gewinnt."""
    result = db.execute(
        update(ChecklistFollowUp)
        .where(ChecklistFollowUp.id == row.id, ChecklistFollowUp.status == row.status,
               ChecklistFollowUp.executed_at == row.executed_at)
        .values(status=status, executed_at=datetime.utcnow())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


def triggering_signature(checklist: Checklist, field_key: str) -> ChecklistAttachment | None:
    """Die gültige Unterschrift im Unterschriftsfeld mit diesem Schlüssel (die erste, falls das
    Feld mehrere nimmt) -- None, solange keine da ist oder alle verworfen sind."""
    field_ids = {f.id for f in checklist.template_version.fields
                 if f.field_key == field_key and f.field_type == "unterschrift"}
    return next((a for a in active_attachments(checklist)
                 if a.kind == "unterschrift" and a.template_field_id in field_ids), None)


def follow_up_due(checklist: Checklist, spec: FollowUp, db: Session | None = None) -> bool:
    """Seit 1.8.38: nach einer Unterschrift (after_signature) oder -- Standard -- nach dem Abschluss. Seit 1.8.41
    nie an einer als gegenstandslos abgeschlossenen Checkliste (auch nicht beim Nachholen). Seit 1.8.43 nach dem
    Versand eines Briefs (after_letter: beim Auftraggeber angekommen) -- dafür braucht es db."""
    if checklist.status == VOID_STATUS:
        return False
    if spec.after_letter:
        from .notice_letters import letter_was_sent  # lokal: das Briefmodul importiert von hier
        return db is not None and letter_was_sent(db, spec.after_letter, checklist.id)
    if spec.after_signature:
        return triggering_signature(checklist, spec.after_signature) is not None
    return checklist.status == "abgeschlossen"


def trigger_label(checklist: Checklist | None, spec: FollowUp | None) -> str:
    if spec is None:
        return ""
    if spec.after_letter:
        purpose = get_purpose(spec.after_letter)
        return f"nach dem Versand „{purpose.label if purpose else spec.after_letter}“"
    if not spec.after_signature:
        return "nach dem Abschluss"
    fields = checklist.template_version.fields if checklist is not None else []
    label = next((f.label for f in fields if f.field_key == spec.after_signature), spec.after_signature)
    return f"nach der Unterschrift „{label}“"


def run_checklist_follow_ups(db: Session, checklist_id: int) -> dict:
    """Führt die fälligen, noch offenen Folgen einer Checkliste aus (follow_up_due()). Idempotent --
    dient zugleich als "Nachholen", seit 1.8.38 auch an einem Entwurf (Folgen nach einer
    Unterschrift). Liefert {"done": n, "module_off": n, "failed": n}."""
    checklist = _load(db, checklist_id)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    counts = {"done": 0, "module_off": 0, "failed": 0}
    purpose = get_purpose(checklist.template_version.purpose)
    if purpose is None or not purpose.follow_ups:
        return counts
    due = [spec for spec in purpose.follow_ups if follow_up_due(checklist, spec, db)]
    if not due:
        return counts
    existing = _existing_rows(db, checklist_id)
    for spec in due:
        module_on = spec.module is None or is_module_enabled(db, spec.module)
        target_status = STATUS_PENDING if module_on else STATUS_MODULE_OFF
        row = existing.get(spec.key)
        if row is None:
            row = _claim_new(db, checklist_id, spec.key, target_status)
            if row is None:
                continue
        elif row.status == STATUS_DONE:
            continue
        elif row.status == STATUS_MODULE_OFF and not module_on:
            counts["module_off"] += 1  # weiterhin offen -- zählt, damit das Büro den Grund sieht
            continue
        elif not _claim_open(db, row, target_status):
            continue
        if not module_on:
            counts["module_off"] += 1
            continue
        row_id = row.id
        try:
            target = spec.handler(db, _load(db, checklist_id))
        except Exception as exc:  # noqa: BLE001 -- jede Folge für sich, siehe Moduldocstring
            db.rollback()
            logger.warning("Folge %s der Checkliste %s nicht ausgeführt (%s)", spec.key, checklist_id,
                           type(exc).__name__)
            counts["failed"] += 1
            continue
        target_type, target_id = target if target else (None, None)
        db.execute(update(ChecklistFollowUp).where(ChecklistFollowUp.id == row_id)
                   .values(status=STATUS_DONE, target_type=target_type, target_id=target_id)
                   .execution_options(synchronize_session=False))
        db.commit()
        counts["done"] += 1
    db.expire_all()
    return counts


def run_follow_ups_after_completion(db: Session, checklist_id: int) -> None:
    """Aufruf aus complete_checklist() NACH dessen Commit. Ein Fehler hier darf den gespeicherten
    Abschluss nicht als gescheitert erscheinen lassen -- offene Folgen sind im Büro nachholbar."""
    try:
        run_checklist_follow_ups(db, checklist_id)
    except Exception as exc:  # noqa: BLE001 -- bewusst breit, siehe Docstring
        db.rollback()
        logger.warning("Folgen der Checkliste %s nicht ausgewertet (%s)", checklist_id, type(exc).__name__)


def run_follow_ups_after_signature(db: Session, checklist_id: int) -> None:
    """Aufruf aus add_attachment() NACH dem Commit einer Unterschrift (seit 1.8.38) -- dieselbe
    Absicherung wie nach dem Abschluss: die Unterschrift gilt, offene Folgen sind nachholbar."""
    try:
        run_checklist_follow_ups(db, checklist_id)
    except Exception as exc:  # noqa: BLE001 -- bewusst breit, siehe Docstring
        db.rollback()
        logger.warning("Folgen der Checkliste %s nach einer Unterschrift nicht ausgewertet (%s)", checklist_id,
                       type(exc).__name__)


def run_follow_ups_after_letter(db: Session, checklist_id: int) -> None:
    """Aufruf NACH dem Commit eines Versands bzw. einer nachgetragenen Zustellung (seit 1.8.43, Folgen mit
    after_letter) -- dieselbe Absicherung: der Versand gilt, offene Folgen sind nachholbar."""
    try:
        run_checklist_follow_ups(db, checklist_id)
    except Exception as exc:  # noqa: BLE001 -- bewusst breit, siehe Docstring
        db.rollback()
        logger.warning("Folgen der Checkliste %s nach dem Versand nicht ausgewertet (%s)", checklist_id,
                       type(exc).__name__)


def list_follow_ups(db: Session, checklist_id: int) -> list[dict]:
    """Folgen einer Checkliste fürs Büro, in der Reihenfolge des Zwecks (unbekannte Schlüssel am
    Ende), mit Auslöser und Ziel (bei einer Aufgabe deren Titel)."""
    checklist = _load(db, checklist_id)
    if checklist is None:
        return []
    purpose = get_purpose(checklist.template_version.purpose)
    specs = {s.key: (i, s) for i, s in enumerate(purpose.follow_ups)} if purpose else {}
    rows = db.scalars(select(ChecklistFollowUp).where(ChecklistFollowUp.checklist_id == checklist_id)).all()
    rows = sorted(rows, key=lambda r: (specs.get(r.follow_up_key, (len(specs), None))[0], r.id))
    task_ids = [r.target_id for r in rows if r.target_type == "task" and r.target_id is not None]
    titles = dict(db.execute(select(Task.id, Task.title).where(Task.id.in_(task_ids))).all()) if task_ids else {}
    result = []
    for r in rows:
        spec = specs.get(r.follow_up_key, (0, None))[1]
        result.append({
            "id": r.id, "follow_up_key": r.follow_up_key, "label": spec.label if spec else r.follow_up_key,
            "trigger_label": trigger_label(checklist, spec),
            "status": r.status, "status_label": STATUS_LABELS.get(r.status, r.status),
            "target_type": r.target_type, "target_id": r.target_id,
            "target_title": titles.get(r.target_id) if r.target_type == "task" else None,
            "executed_at": r.executed_at,
        })
    return result


def list_checklists_with_open_follow_ups(db: Session, limit: int = 200) -> list[int]:
    """IDs der Checklisten mit offenen Folgen (modul_aus/ausstehend) -- für "alle nachholen". Seit 1.8.41 ohne
    gegenstandslose Checklisten: ihre Folgen werden nie mehr ausgeführt."""
    return list(db.scalars(
        select(ChecklistFollowUp.checklist_id)
        .join(Checklist, Checklist.id == ChecklistFollowUp.checklist_id)
        .where(ChecklistFollowUp.status.in_(OPEN_STATUSES), Checklist.status != VOID_STATUS)
        .group_by(ChecklistFollowUp.checklist_id)
        .order_by(ChecklistFollowUp.checklist_id)
        .limit(limit)
    ).all())


def _follow_up_task_ids(db: Session, checklist_id: int, follow_up_key: str | None) -> list[int]:
    query = select(ChecklistFollowUp.target_id).where(
        ChecklistFollowUp.checklist_id == checklist_id, ChecklistFollowUp.target_type == "task",
        ChecklistFollowUp.target_id.is_not(None))
    if follow_up_key is not None:
        query = query.where(ChecklistFollowUp.follow_up_key == follow_up_key)
    return list(db.scalars(query).all())


def _set_follow_up_tasks(db: Session, checklist_id: int, follow_up_key: str | None, *, done: bool) -> int:
    """Gemeinsam für Erledigen und Wiederöffnen: je Aufgabe aus einer Folge der Checkliste die erste "erledigt"-
    bzw. die erste offene Spalte (Kanban-Reihenfolge). Archivierte Aufgaben bleiben, wie sie sind. Ein Fehler hier
    macht den Anlass (Versand, Abschluss) nicht ungeschehen -- Rollback, nur Klassenname im Protokoll (Regel 18)."""
    from .models import TaskColumn
    from .tasks import update_task  # lokal: app.tasks zieht E-Mail-Versand u. a. nach

    changed = 0
    try:
        columns = db.scalars(select(TaskColumn).order_by(TaskColumn.sort_order, TaskColumn.id)).all()
        done_keys = {c.key for c in columns if c.is_done}
        target = next((c.key for c in columns if c.is_done == done), None)
        for task_id in _follow_up_task_ids(db, checklist_id, follow_up_key):
            task = db.get(Task, task_id)
            if task is None or task.archived or target is None or (task.status in done_keys) == done:
                continue
            update_task(db, task_id, status=target)
            changed += 1
    except Exception as exc:  # noqa: BLE001 -- der Anlass ist geschehen, die Aufgabe bleibt dann, wie sie ist
        db.rollback()
        logger.warning("Aufgaben aus Folgen der Checkliste %s nicht %s (%s)", checklist_id,
                       "erledigt" if done else "wieder geöffnet", type(exc).__name__)
    return changed


def complete_follow_up_tasks(db: Session, checklist_id: int, follow_up_key: str | None = None) -> int:
    """Offene Aufgaben aus Folgen der Checkliste erledigen (seit 1.8.41 gemeinsam für den Versand der
    Behinderungsanzeige und "als gegenstandslos abschließen"); follow_up_key None = alle Folgen. Liefert die Zahl."""
    return _set_follow_up_tasks(db, checklist_id, follow_up_key, done=True)


def reopen_follow_up_tasks(db: Session, checklist_id: int, follow_up_key: str) -> int:
    """Erledigte Aufgaben aus dieser Folge wieder öffnen (seit 1.8.41: die Behinderungsanzeige ist als unzustellbar
    vermerkt und kam auf keinem anderen Weg an). Liefert die Zahl."""
    return _set_follow_up_tasks(db, checklist_id, follow_up_key, done=False)
