"""Aufgabenmanagement (seit 1.1.0) -- freie, eigenständige Aufgaben, unabhängig von den
auftragsgebundenen WorkPreparationTask-Zeilen (app/work_preparation.py).

create_task() ist die eine, dokumentierte Stelle, über die auch künftige Module (z. B.
digitale Wartungsberichte) automatisiert Aufgaben anlegen sollen -- direkt, in-process,
ohne HTTP-Umweg. Siehe source_module/source_label/source_url auf dem Task-Modell für die
Automatisierungs-Anschlussstelle. Für Idempotenz (kein doppeltes Anlegen bei mehrfachem
Auslösen) ist das aufrufende Modul selbst zuständig.

Die Spalten (früher ein fest kodiertes STATUSES-Tupel) sind seit 1.1.1 über TaskColumn
konfigurierbar (siehe app/task_columns.py) -- Task.status ist weiterhin ein freier String,
referenziert aber TaskColumn.key statt eines Literals."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .email_sending import send_plain_email
from .models import Employee, Task, TaskChecklistItem, TaskColumn, TaskSettings
from .task_columns import ensure_default_columns

PRIORITIES = ("niedrig", "normal", "hoch", "dringend")


def _employee_name(e: Employee | None) -> str | None:
    return f"{e.first_name} {e.last_name}".strip() if e else None


def _columns_by_key(db: Session) -> dict[str, TaskColumn]:
    ensure_default_columns(db)
    return {c.key: c for c in db.scalars(select(TaskColumn)).all()}


def _default_column_key(db: Session) -> str:
    column = db.scalar(select(TaskColumn).order_by(TaskColumn.sort_order, TaskColumn.id))
    if column is None:
        raise ValueError("Keine Aufgaben-Spalte vorhanden.")
    return column.key


def _validate_status(status: str, columns_by_key: dict[str, TaskColumn]) -> None:
    if status not in columns_by_key:
        raise ValueError(f"Unbekannte Aufgaben-Spalte: {status}")


def task_to_dict(task: Task, columns_by_key: dict[str, TaskColumn] | None = None) -> dict:
    column = (columns_by_key or {}).get(task.status)
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "status_label": column.label if column else task.status,
        "status_is_done": column.is_done if column else False,
        "priority": task.priority,
        "due_date": task.due_date,
        "assigned_employee_id": task.assigned_employee_id,
        "assigned_employee_name": _employee_name(task.assigned_employee),
        "project_id": task.project_id,
        "project_number": task.project.project_number if task.project else None,
        "project_name": task.project.name if task.project else None,
        "created_by_user_id": task.created_by_user_id,
        "source_module": task.source_module,
        "source_label": task.source_label,
        "source_url": task.source_url,
        "archived": task.archived,
        "checklist_items": [
            {"id": i.id, "title": i.title, "done": i.done} for i in sorted(task.checklist_items, key=lambda i: (i.sort_order, i.id))
        ],
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
    }


def _load_task(db: Session, task_id: int) -> Task | None:
    return db.scalar(
        select(Task)
        .options(selectinload(Task.assigned_employee), selectinload(Task.project), selectinload(Task.checklist_items))
        .where(Task.id == task_id)
    )


def list_tasks(db: Session, employee_id: int | None = None, status: str | None = None,
                project_id: int | None = None, include_archived: bool = False) -> list[dict]:
    query = select(Task).options(
        selectinload(Task.assigned_employee), selectinload(Task.project), selectinload(Task.checklist_items)
    )
    if employee_id is not None:
        query = query.where(Task.assigned_employee_id == employee_id)
    if status is not None:
        query = query.where(Task.status == status)
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    if not include_archived:
        query = query.where(Task.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(Task.due_date.is_(None), Task.due_date, Task.id.desc())
    columns_by_key = _columns_by_key(db)
    return [task_to_dict(t, columns_by_key) for t in db.scalars(query).all()]


def get_or_create_task_settings(db: Session) -> TaskSettings:
    settings = db.get(TaskSettings, 1)
    if settings is None:
        settings = TaskSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_task_settings(db: Session, notify_on_assignment: bool) -> TaskSettings:
    settings = get_or_create_task_settings(db)
    settings.notify_on_assignment = notify_on_assignment
    db.commit()
    return settings


def notify_task_assignment(db: Session, task: Task) -> None:
    """Benachrichtigt den zugewiesenen Mitarbeiter per E-Mail über eine neue Aufgabe (seit
    1.1.3). Stiller No-op, wenn die Benachrichtigung abgeschaltet ist oder der Mitarbeiter
    keine E-Mail-Adresse hinterlegt hat (EmployeeProfile.email ist optional). Ein Versandfehler
    (z. B. falsch konfigurierter Mailserver) wird hier abgefangen -- er darf das eigentliche
    Speichern der Aufgabe, das zu diesem Zeitpunkt bereits erfolgt ist, nicht rückwirkend als
    Fehler erscheinen lassen."""
    settings = get_or_create_task_settings(db)
    if not settings.notify_on_assignment:
        return
    employee = task.assigned_employee
    if employee is None or employee.profile is None or not employee.profile.email:
        return
    due = f"\nFälligkeit: {task.due_date.strftime('%d.%m.%Y')}" if task.due_date else ""
    project = f"\nProjekt: {task.project.project_number} · {task.project.name}" if task.project else ""
    body = (
        f"Hallo {employee.first_name},\n\n"
        f"dir wurde die Aufgabe \"{task.title}\" zugewiesen.\n"
        f"Priorität: {task.priority}{due}{project}\n\n"
        f"Diese Nachricht wurde automatisch vom ERP versendet."
    )
    try:
        send_plain_email(db, to_email=employee.profile.email, subject=f"Neue Aufgabe: {task.title}", body_text=body)
    except ValueError:
        pass


def create_task(db: Session, title: str, description: str | None = None, priority: str = "normal",
                 due_date: date | None = None, assigned_employee_id: int | None = None,
                 project_id: int | None = None, created_by_user_id: int | None = None,
                 source_module: str | None = None, source_label: str | None = None,
                 source_url: str | None = None, status: str | None = None) -> dict:
    """Legt eine neue Aufgabe an. Wird sowohl vom manuellen "+Aufgabe"-Endpunkt als auch
    -- künftig -- direkt von anderen Modulen aufgerufen (siehe Modul-Docstring oben)."""
    columns_by_key = _columns_by_key(db)
    if status is None:
        status = _default_column_key(db)
    else:
        _validate_status(status, columns_by_key)
    task = Task(
        title=title.strip(), description=(description or None), status=status, priority=priority,
        due_date=due_date, assigned_employee_id=assigned_employee_id, project_id=project_id,
        created_by_user_id=created_by_user_id, source_module=source_module,
        source_label=source_label, source_url=source_url,
    )
    db.add(task)
    db.commit()
    task = _load_task(db, task.id)
    if assigned_employee_id is not None:
        notify_task_assignment(db, task)
    return task_to_dict(task, columns_by_key)


def update_task(db: Session, task_id: int, title: str, description: str | None, status: str,
                 priority: str, due_date: date | None, assigned_employee_id: int | None,
                 project_id: int | None) -> dict | None:
    task = db.get(Task, task_id)
    if task is None:
        return None
    columns_by_key = _columns_by_key(db)
    _validate_status(status, columns_by_key)
    was_done = columns_by_key[task.status].is_done if task.status in columns_by_key else False
    previous_employee_id = task.assigned_employee_id
    task.title = title.strip()
    task.description = description or None
    task.status = status
    task.priority = priority
    task.due_date = due_date
    task.assigned_employee_id = assigned_employee_id
    task.project_id = project_id
    now_done = columns_by_key[status].is_done
    if now_done and not was_done:
        task.completed_at = datetime.utcnow()
    elif not now_done and was_done:
        task.completed_at = None
    db.commit()
    task = _load_task(db, task.id)
    if assigned_employee_id is not None and assigned_employee_id != previous_employee_id:
        notify_task_assignment(db, task)
    return task_to_dict(task, columns_by_key)


def set_task_archived(db: Session, task_id: int, archived: bool) -> dict | None:
    """Rein informatives Aus-/Einblenden aus dem Standard-Board (seit 1.2.10, gleiches Muster
    wie set_project_archived() in app/projects.py) -- jederzeit umkehrbar, unabhängig von
    status/is_done. Echtes Löschen (delete_task()) bleibt zusätzlich möglich."""
    task = db.get(Task, task_id)
    if task is None:
        return None
    task.archived = archived
    db.commit()
    return task_to_dict(_load_task(db, task.id), _columns_by_key(db))


def delete_task(db: Session, task_id: int) -> bool:
    task = db.get(Task, task_id)
    if task is None:
        return False
    db.delete(task)
    db.commit()
    return True


def add_checklist_item(db: Session, task_id: int, title: str) -> dict | None:
    task = db.get(Task, task_id)
    if task is None:
        return None
    title = title.strip()
    if not title:
        raise ValueError("Bitte einen Titel angeben.")
    max_sort = max((i.sort_order for i in task.checklist_items), default=-10)
    item = TaskChecklistItem(task_id=task_id, title=title, sort_order=max_sort + 10)
    db.add(item)
    db.commit()
    return {"id": item.id, "title": item.title, "done": item.done}


def update_checklist_item(db: Session, task_id: int, item_id: int, title: str | None = None,
                           done: bool | None = None) -> dict | None:
    item = db.scalar(select(TaskChecklistItem).where(TaskChecklistItem.id == item_id, TaskChecklistItem.task_id == task_id))
    if item is None:
        return None
    if title is not None:
        title = title.strip()
        if not title:
            raise ValueError("Bitte einen Titel angeben.")
        item.title = title
    if done is not None:
        item.done = done
    db.commit()
    return {"id": item.id, "title": item.title, "done": item.done}


def delete_checklist_item(db: Session, task_id: int, item_id: int) -> bool:
    item = db.scalar(select(TaskChecklistItem).where(TaskChecklistItem.id == item_id, TaskChecklistItem.task_id == task_id))
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
