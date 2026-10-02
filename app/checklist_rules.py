"""Regeln einer Checkliste → Aufgaben fürs Büro (seit 1.8.3, Modul "checklisten").

Herleitung: docs/archiv/modul-checklisten.md (Fund 4, Betreiberentscheidung C, "Umsetzung 1.8.3").

- Ausgewertet wird ausschließlich eine ABGESCHLOSSENE Checkliste -- also eingefrorene Antworten --
  gegen die Regeln GENAU der Vorlagenfassung, mit der sie ausgefüllt wurde.
- app/tasks.py::create_task() committet selbst (Fund 4). Deshalb läuft die Auswertung erst NACH
  dem Commit des Abschlusses und belegt je (Checkliste, Regel) zuerst eine
  ChecklistRuleExecution-Zeile (Unique-Constraint, SAVEPOINT) und legt erst danach die Aufgabe an.
  Ein zweiter Aufruf -- Doppelklick, Wiederholung nach einem Abbruch, "Aufgaben nachholen" --
  findet die Zeile und legt nichts doppelt an.
- Status der Zeile: "aufgabe_angelegt" (fertig), "modul_aus" (Aufgabenmodul war aus,
  Betreiberentscheidung C: nachholbar statt still entfallen), "ausstehend" (belegt, aber die
  Aufgabe ist nicht bestätigt angelegt, z. B. Abbruch dazwischen -- ebenfalls nachholbar).
  Nachholen belegt eine offene Zeile per bedingtem UPDATE (executed_at als Versionsstempel), damit
  zwei gleichzeitige Nachhol-Klicks nicht beide eine Aufgabe anlegen. Restrisiko, bewusst
  hingenommen: bricht der Prozess GENAU zwischen create_task() und dem Vermerk der task_id ab,
  bleibt die Zeile "ausstehend" und ein späteres Nachholen legt eine zweite Aufgabe an.
- Rollenlos wie jede Geschäftslogik; wer Ausführungen sehen/nachholen darf, entscheidet der Router
  (nur Büro -- die Regeln sind Büro-intern).
- Link-Zweck (seit 1.8.38, ChecklistTemplateRule.link_purpose): die Aufgabe verlinkt nicht auf die
  Checkliste, sondern aufs Anlegen einer Checkliste dieses Zwecks am selben Auftrag
  (/checklisten/auftrag/{id}?zweck=...; Beispiel Tagesbericht "Behinderung = ja" →
  "Behinderungsanzeige anlegen"). Ist eine Aufgabe mit genau diesem Link noch offen, entsteht
  keine zweite: die Zeile bekommt Status "aufgabe_vorhanden" und verweist auf die offene. Ein
  Tagesbericht je Tag einer andauernden Behinderung legt so nicht täglich eine neue an."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .berlin_time import berlin_now, to_berlin
from .checklist_purposes import purpose_label
from .checklists import active_attachments
from .models import (
    Checklist, ChecklistAnswer, ChecklistRuleExecution, ChecklistTemplateField, ChecklistTemplateRule,
    ChecklistTemplateVersion, Order, Task, TaskColumn,
)
from .modules import is_module_enabled

logger = logging.getLogger(__name__)

TASK_MODULE_KEY = "aufgabenmanagement"
SOURCE_MODULE = "checklisten"
STATUS_DONE = "aufgabe_angelegt"
STATUS_EXISTING = "aufgabe_vorhanden"  # seit 1.8.38: offene Aufgabe mit demselben Link, keine zweite
STATUS_MODULE_OFF = "modul_aus"
STATUS_PENDING = "ausstehend"
OPEN_STATUSES = (STATUS_MODULE_OFF, STATUS_PENDING)
STATUS_LABELS = {STATUS_DONE: "Aufgabe angelegt", STATUS_EXISTING: "Aufgabe war schon offen",
                 STATUS_MODULE_OFF: "nicht angelegt (Aufgabenmodul aus)",
                 STATUS_PENDING: "nicht angelegt (unterbrochen)"}
OPERATOR_LABELS = {"immer": "immer", "ist_ja": "ist ja", "ist_nein": "ist nein", "enthaelt": "enthält",
                   "kleiner": "kleiner als", "groesser": "größer als", "gleich": "gleich",
                   "ausgefuellt": "ist ausgefüllt"}


def _load(db: Session, checklist_id: int) -> Checklist | None:
    return db.scalar(
        select(Checklist).options(
            selectinload(Checklist.template_version).selectinload(ChecklistTemplateVersion.fields)
            .selectinload(ChecklistTemplateField.options),
            selectinload(Checklist.template_version).selectinload(ChecklistTemplateVersion.rules),
            selectinload(Checklist.answers).selectinload(ChecklistAnswer.selections),
            selectinload(Checklist.attachments),
            selectinload(Checklist.rule_executions),
            selectinload(Checklist.created_by_employee),
        ).where(Checklist.id == checklist_id)
    )


def _decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def rule_matches(checklist: Checklist, rule: ChecklistTemplateRule) -> bool:
    """Trifft die Regel auf die (eingefrorenen) Antworten zu? Ein fehlendes Feld oder eine fehlende
    Antwort trifft nie zu -- außer bei "immer"."""
    if rule.operator == "immer":
        return True
    field = next((f for f in checklist.template_version.fields if f.field_key == rule.field_key), None)
    if field is None:
        return False
    if rule.operator == "ausgefuellt" and field.field_type in ("foto", "unterschrift"):
        return any(a.template_field_id == field.id for a in active_attachments(checklist))  # ohne verworfene
    answer = next((a for a in checklist.answers if a.template_field_id == field.id), None)
    if answer is None:
        return False
    if rule.operator == "ist_ja":
        return answer.value_text == "ja"
    if rule.operator == "ist_nein":
        return answer.value_text == "nein"
    if rule.operator == "enthaelt":
        if field.multiple:
            return any(s.option_key == rule.operand for s in answer.selections)
        return answer.value_text == rule.operand
    if rule.operator in ("kleiner", "groesser", "gleich"):
        operand = _decimal(rule.operand)
        if answer.value_number is None or operand is None:
            return False
        return {"kleiner": answer.value_number < operand, "groesser": answer.value_number > operand,
                "gleich": answer.value_number == operand}[rule.operator]
    if rule.operator == "ausgefuellt":
        return any(v not in (None, "") for v in (answer.value_text, answer.value_number, answer.value_date,
                                                 answer.value_time, answer.value_datetime)) or bool(answer.selections)
    return False


def _creator_name(checklist: Checklist) -> str:
    e = checklist.created_by_employee
    return " ".join(p for p in ((e.first_name, e.last_name) if e else ()) if p) or "unbekannt"


def _fill(text: str | None, checklist: Checklist) -> str:
    """Platzhalter {vorlage}, {kontext}, {ersteller} -- bewusst per replace, nicht format():
    eine geschweifte Klammer im Freitext des Büros darf nie zu einem Fehler führen."""
    text = text or ""
    for key, value in (("{vorlage}", checklist.template_label_snapshot or ""),
                       ("{kontext}", checklist.context_label_snapshot or ""),
                       ("{ersteller}", _creator_name(checklist))):
        text = text.replace(key, value)
    return text.strip()


def _condition_text(checklist: Checklist, rule: ChecklistTemplateRule) -> str:
    if rule.operator == "immer":
        return "immer beim Abschluss"
    field = next((f for f in checklist.template_version.fields if f.field_key == rule.field_key), None)
    label = field.label if field else rule.field_key
    operand = rule.operand
    if rule.operator == "enthaelt" and field is not None:
        operand = next((o.label for o in field.options if o.option_key == rule.operand), rule.operand)
    return f"„{label}“ {OPERATOR_LABELS.get(rule.operator, rule.operator)}" + (f" „{operand}“" if operand else "")


def _task_values(db: Session, checklist: Checklist, rule: ChecklistTemplateRule) -> dict:
    # completed_at ist UTC; Text und Fälligkeit brauchen das Datum in Ortszeit
    completed = to_berlin(checklist.completed_at) if checklist.completed_at else berlin_now()
    footer = (f"Ausgelöst durch die Checkliste „{checklist.template_label_snapshot}“ "
              f"({checklist.context_label_snapshot or 'Betrieb'}), abgeschlossen am "
              f"{completed.strftime('%d.%m.%Y')} von {_creator_name(checklist)}. "
              f"Bedingung: {_condition_text(checklist, rule)}.")
    description = _fill(rule.task_description, checklist)
    assigned, project_id = None, None
    if checklist.context_type == "auftrag" and checklist.order_id is not None:
        order = db.get(Order, checklist.order_id)
        if order is not None:
            project_id = order.project_id
            if rule.assignee_mode == "sachbearbeiter":
                assigned = order.caseworker_employee_id  # fehlt er: empfängerlos mit min_visible_role
    context = checklist.context_label_snapshot or "Betrieb"
    source_label = f"{checklist.template_label_snapshot} – {context}"
    source_url = f"/checklisten/{checklist.id}"
    if rule.link_purpose and checklist.context_type == "auftrag" and checklist.order_id is not None:
        # Seit 1.8.38: Link zum Anlegen einer Checkliste des Zwecks am selben Auftrag; die auslösende
        # Checkliste steht dann in der Fußzeile.
        source_label = f"{purpose_label(rule.link_purpose)} anlegen – {context}"
        source_url = f"/checklisten/auftrag/{checklist.order_id}?zweck={rule.link_purpose}"
        footer += f" Checkliste: /checklisten/{checklist.id}"
    return {
        "title": (_fill(rule.task_title, checklist) or checklist.template_label_snapshot)[:255],
        "description": f"{description}\n\n{footer}" if description else footer,
        "priority": rule.task_priority,
        "due_date": (completed.date() + timedelta(days=rule.due_in_days)) if rule.due_in_days is not None else None,
        "assigned_employee_id": assigned, "project_id": project_id,
        "created_by_user_id": checklist.created_by_user_id,
        "source_module": SOURCE_MODULE,
        "source_label": source_label[:255],
        "source_url": source_url,
        "min_visible_role": rule.min_visible_role,
    }


def _open_task_with_link(db: Session, source_url: str) -> Task | None:
    """Offene (nicht erledigte, nicht archivierte) Aufgabe mit genau diesem Link (seit 1.8.38)."""
    done_columns = select(TaskColumn.key).where(TaskColumn.is_done == True)  # noqa: E712 -- SQLAlchemy-Vergleich
    return db.scalar(select(Task).where(Task.source_url == source_url, Task.archived == False,  # noqa: E712
                                        Task.status.not_in(done_columns)).order_by(Task.id).limit(1))


def _claim_new(db: Session, checklist_id: int, rule_id: int, status: str) -> ChecklistRuleExecution | None:
    """Neue Zeile anlegen und committen. None = ein anderer Aufruf war schneller."""
    execution = ChecklistRuleExecution(checklist_id=checklist_id, rule_id=rule_id, status=status,
                                       executed_at=datetime.utcnow())
    try:
        with db.begin_nested():
            db.add(execution)
            db.flush()
    except IntegrityError:
        return None
    db.commit()
    return execution


def _claim_open(db: Session, execution: ChecklistRuleExecution, status: str) -> bool:
    """Offene Zeile (modul_aus/ausstehend) per bedingtem UPDATE belegen -- nur ein Aufrufer gewinnt."""
    stamp = datetime.utcnow()
    result = db.execute(
        update(ChecklistRuleExecution)
        .where(ChecklistRuleExecution.id == execution.id, ChecklistRuleExecution.status == execution.status,
               ChecklistRuleExecution.executed_at == execution.executed_at)
        .values(status=status, executed_at=stamp)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


def run_checklist_rules(db: Session, checklist_id: int) -> dict:
    """Wertet die Regeln einer abgeschlossenen Checkliste aus und legt fehlende Aufgaben an.
    Idempotent -- dient zugleich als "Aufgaben nachholen". Liefert {"created": n, "module_off": n}."""
    from .tasks import create_task  # lokal: app.tasks zieht E-Mail-Versand u. a. nach

    checklist = _load(db, checklist_id)
    if checklist is None:
        raise LookupError("Checkliste nicht gefunden.")
    if checklist.status != "abgeschlossen":
        raise ValueError("Regeln werden erst beim Abschluss ausgewertet.")
    module_on = is_module_enabled(db, TASK_MODULE_KEY)
    target_status = STATUS_PENDING if module_on else STATUS_MODULE_OFF
    existing = {e.rule_id: e for e in checklist.rule_executions}
    counts = {"created": 0, "module_off": 0}
    for rule in checklist.template_version.rules:
        if not rule_matches(checklist, rule):
            continue
        execution = existing.get(rule.id)
        if execution is None:
            execution = _claim_new(db, checklist.id, rule.id, target_status)
            if execution is None:
                continue
        elif execution.status in (STATUS_DONE, STATUS_EXISTING):
            continue
        elif execution.status == STATUS_MODULE_OFF and not module_on:
            counts["module_off"] += 1  # weiterhin offen -- zählt, damit das Büro den Grund sieht
            continue
        elif not _claim_open(db, execution, target_status):
            continue
        if not module_on:
            counts["module_off"] += 1
            continue
        values = _task_values(db, checklist, rule)
        linked = _open_task_with_link(db, values["source_url"]) if rule.link_purpose else None
        if linked is not None:  # seit 1.8.38: keine zweite offene Aufgabe zum selben Link
            db.execute(update(ChecklistRuleExecution).where(ChecklistRuleExecution.id == execution.id)
                       .values(status=STATUS_EXISTING, task_id=linked.id).execution_options(synchronize_session=False))
            db.commit()
            continue
        task = create_task(db, **values)
        db.execute(update(ChecklistRuleExecution).where(ChecklistRuleExecution.id == execution.id)
                   .values(status=STATUS_DONE, task_id=task["id"]).execution_options(synchronize_session=False))
        db.commit()
        counts["created"] += 1
    db.expire_all()
    return counts


def run_rules_after_completion(db: Session, checklist_id: int) -> None:
    """Aufruf aus complete_checklist() NACH dessen Commit. Ein Fehler hier darf den bereits
    gespeicherten Abschluss nicht als gescheitert erscheinen lassen -- die Zeile bleibt dann
    "ausstehend" (bzw. fehlt) und ist im Büro nachholbar."""
    try:
        run_checklist_rules(db, checklist_id)
    except Exception as exc:  # noqa: BLE001 -- bewusst breit, siehe Docstring
        db.rollback()
        # Regel 18 (seit 1.8.17): nur ID und Klassenname, kein logger.exception() -- dessen Meldung und
        # Traceback enthalten bei einer SQLAlchemy-Ausnahme die SQL samt Parametern, beim Anlegen der
        # Aufgabe also Titel und Beschreibung (Vorlage, Auftragsnummer, Ersteller).
        logger.error("Checklisten-Regeln für Checkliste %s konnten nicht ausgewertet werden (%s)",
                     checklist_id, type(exc).__name__)


def list_rule_executions(db: Session, checklist_id: int) -> list[dict]:
    """Ausgelöste Regeln einer Checkliste fürs Büro, inkl. verknüpfter Aufgabe. rule_title mit
    eingesetzten Platzhaltern -- so, wie die Aufgabe heißen wird (bzw. beim Anlegen hieß)."""
    checklist = _load(db, checklist_id)
    rows = db.execute(
        select(ChecklistRuleExecution, ChecklistTemplateRule, Task)
        .join(ChecklistTemplateRule, ChecklistTemplateRule.id == ChecklistRuleExecution.rule_id)
        .outerjoin(Task, Task.id == ChecklistRuleExecution.task_id)
        .where(ChecklistRuleExecution.checklist_id == checklist_id)
        .order_by(ChecklistTemplateRule.sort_order, ChecklistTemplateRule.id)
    ).all()
    return [{
        "id": e.id, "rule_id": r.id, "status": e.status, "status_label": STATUS_LABELS.get(e.status, e.status),
        "executed_at": e.executed_at, "task_id": e.task_id,
        "task_title": t.title if t is not None else None, "task_status": t.status if t is not None else None,
        "rule_title": (_fill(r.task_title, checklist) if checklist else r.task_title) or r.task_title,
        "priority": r.task_priority,
    } for e, r, t in rows]


def list_checklists_with_open_rules(db: Session, limit: int = 200) -> list[int]:
    """IDs der Checklisten mit nicht angelegten Aufgaben (modul_aus/ausstehend) -- für die
    Büro-Übersicht und "alle nachholen"."""
    return list(db.scalars(
        select(ChecklistRuleExecution.checklist_id)
        .where(ChecklistRuleExecution.status.in_(OPEN_STATUSES))
        .group_by(ChecklistRuleExecution.checklist_id)
        .order_by(ChecklistRuleExecution.checklist_id)
        .limit(limit)
    ).all())
