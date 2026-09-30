"""Folgen des Abschlusses einer Checkliste nach dem Zweck ihrer Fassung (seit 1.8.16, Modul
"checklisten").

Herleitung: docs/archiv/modul-checklisten.md, "Umsetzung 1.8.16". Welche Folgen ein Zweck hat,
steht in app/checklist_purposes.py (FollowUp); bisher hat kein Zweck eine -- die ersten kommen in
den Runden 2b/2c, die Tests arbeiten mit einem eigenen Test-Zweck.

Ablauf wie bei den Regeln (app/checklist_rules.py, Fund 4):
- Nur eine ABGESCHLOSSENE Checkliste, nur die Folgen des Zwecks ihrer Fassung.
- Je (Checkliste, Folgeschlüssel) zuerst eine ChecklistFollowUp-Zeile belegen (Unique-Constraint,
  SAVEPOINT, eigener Commit), dann den Handler aufrufen (er darf selbst committen), dann Status
  "erledigt" und das Ziel vermerken. Ein zweiter Aufruf -- Doppelklick, Wiederholung,
  "Nachholen" -- findet die Zeile und führt nichts doppelt aus.
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

from .checklist_purposes import get_purpose
from .models import Checklist, ChecklistAnswer, ChecklistFollowUp, ChecklistTemplateField, ChecklistTemplateVersion
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


def run_checklist_follow_ups(db: Session, checklist_id: int) -> dict:
    """Führt die noch offenen Folgen einer abgeschlossenen Checkliste aus. Idempotent -- dient
    zugleich als "Nachholen". Liefert {"done": n, "module_off": n, "failed": n}."""
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    if checklist.status != "abgeschlossen":
        raise ValueError("Folgen werden erst beim Abschluss ausgeführt.")
    counts = {"done": 0, "module_off": 0, "failed": 0}
    purpose = get_purpose(checklist.template_version.purpose)
    if purpose is None or not purpose.follow_ups:
        return counts
    existing = _existing_rows(db, checklist_id)
    for spec in purpose.follow_ups:
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


def list_follow_ups(db: Session, checklist_id: int) -> list[dict]:
    """Folgen einer Checkliste fürs Büro, in der Reihenfolge des Zwecks (unbekannte Schlüssel am
    Ende), mit Ziel."""
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        return []
    purpose = get_purpose(checklist.template_version.purpose)
    specs = {s.key: (i, s.label) for i, s in enumerate(purpose.follow_ups)} if purpose else {}
    rows = db.scalars(select(ChecklistFollowUp).where(ChecklistFollowUp.checklist_id == checklist_id)).all()
    rows = sorted(rows, key=lambda r: (specs.get(r.follow_up_key, (len(specs), ""))[0], r.id))
    return [{
        "id": r.id, "follow_up_key": r.follow_up_key, "label": specs.get(r.follow_up_key, (0, r.follow_up_key))[1],
        "status": r.status, "status_label": STATUS_LABELS.get(r.status, r.status),
        "target_type": r.target_type, "target_id": r.target_id, "executed_at": r.executed_at,
    } for r in rows]


def list_checklists_with_open_follow_ups(db: Session, limit: int = 200) -> list[int]:
    """IDs der Checklisten mit offenen Folgen (modul_aus/ausstehend) -- für "alle nachholen"."""
    return list(db.scalars(
        select(ChecklistFollowUp.checklist_id)
        .where(ChecklistFollowUp.status.in_(OPEN_STATUSES))
        .group_by(ChecklistFollowUp.checklist_id)
        .order_by(ChecklistFollowUp.checklist_id)
        .limit(limit)
    ).all())
