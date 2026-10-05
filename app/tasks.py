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

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from .grunddaten import einzelzeile
from .audit import TASK_ENTITY_TYPE, record_audit_entry
from .models import AppUser, Employee, Task, TaskChecklistItem, TaskColumn, TaskSettings
from .permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, ROLES, has_min_role, has_role

PRIORITIES = ("niedrig", "normal", "hoch", "dringend")
TASK_ALREADY_TAKEN = "Diese Aufgabe hat bereits jemand anderes übernommen."


def _employee_name(e: Employee | None) -> str | None:
    return f"{e.first_name} {e.last_name}".strip() if e else None


def _columns_by_key(db: Session) -> dict[str, TaskColumn]:
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
        "min_visible_role": task.min_visible_role,
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
                project_id: int | None = None, include_archived: bool = False,
                unassigned_only: bool = False, search: str | None = None) -> list[dict]:
    query = select(Task).options(
        selectinload(Task.assigned_employee), selectinload(Task.project), selectinload(Task.checklist_items)
    )
    if unassigned_only:
        query = query.where(Task.assigned_employee_id.is_(None))
    elif employee_id is not None:
        query = query.where(Task.assigned_employee_id == employee_id)
    if status is not None:
        query = query.where(Task.status == status)
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    if search:
        query = query.where(Task.title.ilike(f"%{search}%"))
    if not include_archived:
        query = query.where(Task.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(Task.due_date.is_(None), Task.due_date, Task.id.desc())
    columns_by_key = _columns_by_key(db)
    return [task_to_dict(t, columns_by_key) for t in db.scalars(query).all()]


def task_visible_for_user(user: AppUser, assigned_employee_id: int | None, min_visible_role: str | None) -> bool:
    """DIE Sichtbarkeitsregel einer Aufgabe (seit 1.8.26): Lesen (list_tasks_for_user()) und jede
    Änderung an einer einzelnen Aufgabe (Bearbeiten, Löschen, Archivieren, Zurück in den Büro-Eingang,
    Checkliste -- app/routers/tasks.py::_require_visible_task()) prüfen dieselbe. Büro ab
    buero_auftrag; eine Ziel-Mindestrolle muss erfüllt sein; Admin sieht dann alles, jedes andere
    Büro-Konto die eigenen und die empfängerlosen Aufgaben. Bis 1.8.25 prüften die Einzel-Endpunkte nur
    die Rolle -- wer eine ID erriet, konnte eine Finanz-Aufgabe als buero_auftrag ändern."""
    if not has_min_role(user, ROLE_OFFICE_AUFTRAG):
        return False
    if min_visible_role is not None and not has_min_role(user, min_visible_role):
        return False
    if has_role(user, ROLE_ADMIN):
        return True
    return assigned_employee_id is None or (user.employee_id is not None and assigned_employee_id == user.employee_id)


def list_tasks_for_user(db: Session, user: AppUser, *, status: str | None = None,
                         project_id: int | None = None, include_archived: bool = False,
                         employee_id: int | None = None, unassigned_only: bool = False,
                         search: str | None = None) -> list[dict]:
    """Der EINE, rollenbewusste Einstiegspunkt für Task-Sichtbarkeit -- ersetzt die frühere,
    inline im Router sitzende is_admin-Prüfung (siehe CLAUDE.md "Änderung am Aufgabenmodul").
    Nutzt has_role() (app/permissions.py) statt einer eigenen Rollenbestimmung -- dieselbe
    Quelle wie require_role()/can(). Monteure sehen NIE etwas (die gesamte /api/tasks*-Familie
    ist Büro/Admin-only, unverändert seit "Rechtekonzept") -- der Aufrufer (der Router) muss das
    ohnehin schon per require_role() durchsetzen, diese Funktion verweigert zusätzlich, falls sie
    doch mit einer anderen Rolle aufgerufen wird (leere Liste statt eines Fehlers, da sie selbst
    keine HTTP-Antwort formuliert).

    unassigned_only hat Vorrang und gilt für JEDES Büro-/Admin-Konto gleich -- empfängerlose
    Aufgaben sind der gemeinsame Büro-Eingang, unabhängig von der eigenen employee_id. Ohne
    unassigned_only bleibt Admin frei wählbar (employee_id-Parameter), ein Büro-Konto ist
    dagegen zwingend auf die eigene employee_id festgelegt (der employee_id-Parameter wird für
    diese Rolle ignoriert) -- exakt das bisherige Verhalten von GET /api/tasks, nur zentralisiert.

    search wird unverändert an list_tasks() durchgereicht (Titel-ILIKE) -- genutzt von
    app/search.py::_search_tasks() (Büro-Suche), damit die Sichtbarkeitsregel dort NICHT ein
    zweites Mal nachgebaut wird, siehe dort.

    min_visible_role (seit 1.5.0, allgemeine Erweiterung des claim/release-Modells, nicht nur
    für Betriebskosten -- siehe CLAUDE.md "Aufgabe"): eine empfängerlose Aufgabe kann optional
    eine Ziel-Mindestrolle tragen. Der Filter wird UNBEDINGT auf jede zurückgegebene Zeile
    angewendet (has_min_role(user, row.min_visible_role)), nicht nur im unassigned_only-Zweig --
    für Konsistenz, auch wenn er praktisch nur dort greift (eine bereits einem konkreten
    Mitarbeiter zugewiesene Aufgabe ist ohnehin nur für diesen selbst oder Admin sichtbar,
    unabhängig von min_visible_role). Ein buero_auftrag-Konto sieht dadurch eine
    finanz-adressierte Aufgabe an KEINER Stelle -- weder in der Liste noch im gemeinsamen
    Büro-Eingang."""
    if not has_min_role(user, ROLE_OFFICE_AUFTRAG):
        return []
    if unassigned_only:
        effective_employee_id = None
    elif has_role(user, ROLE_ADMIN):
        effective_employee_id = employee_id
    else:
        if user.employee_id is None:
            raise ValueError("Ihr Büro-Konto ist keinem Mitarbeiter zugeordnet.")
        effective_employee_id = user.employee_id
    rows = list_tasks(db, employee_id=effective_employee_id, status=status, project_id=project_id,
                       include_archived=include_archived, unassigned_only=unassigned_only, search=search)
    return [r for r in rows if task_visible_for_user(user, r["assigned_employee_id"], r["min_visible_role"])]


def claim_task(db: Session, task_id: int, user: AppUser) -> dict | None:
    """"Übernehmen" -- weist eine bisher empfängerlose Aufgabe fest der übernehmenden Person zu
    (kein dritter Zustand neben zugewiesen/empfängerlos, siehe CLAUDE.md). Dasselbe Feld wie
    jede andere Zuweisung (Task.assigned_employee_id) -- keine zweite Zuweisungsart. Lehnt ab,
    wenn das Büro-Konto keiner employee_id zugeordnet ist (dieselbe, klare Meldung wie beim
    bisherigen Monteur-Fall in GET /api/tasks) oder die Aufgabe bereits vergeben ist (verhindert,
    dass "Übernehmen" versehentlich eine Kollegen-Aufgabe stiehlt -- eine neue, bewusste Sperre,
    die die bestehende PUT-Zuweisung nicht kennt, da Übernehmen ausdrücklich nur für wirklich
    empfängerlose Aufgaben gedacht ist).

    Rollen-Gate (seit 1.5.0): trägt die Aufgabe ein min_visible_role, das die übernehmende
    Person nicht erfüllt, wird mit PermissionError abgelehnt -- bewusst ein anderer
    Exception-Typ als ValueError, damit der Router das als 403 (Rollenverstoß) statt 400
    (Geschäftsregel) beantworten kann. Geprüft VOR der "bereits vergeben"-Prüfung, damit eine
    geratene Aufgaben-ID einer fremden Rolle immer dasselbe 403 liefert, unabhängig vom
    Zuweisungszustand.

    Gleichzeitiges Übernehmen (seit 1.8.18): die Zuweisung ist ein bedingtes UPDATE ("nur wenn
    noch empfängerlos"), kein Lesen-Prüfen-Schreiben. Klicken zwei gleichzeitig, trifft das
    UPDATE nur beim ersten eine Zeile; der zweite bekommt TASK_ALREADY_TAKEN statt die Aufgabe
    still zu überschreiben. Die Übernahme steht in der Änderungshistorie (Eintrag in derselben
    Transaktion; sichtbar nur für Admin, siehe app/routers/audit.py)."""
    if user.employee_id is None:
        raise ValueError("Ihr Büro-Konto ist keinem Mitarbeiter zugeordnet.")
    task = db.get(Task, task_id)
    if task is None:
        return None
    if task.min_visible_role is not None and not has_min_role(user, task.min_visible_role):
        raise PermissionError("Diese Aufgabe ist für Ihre Rolle nicht sichtbar.")
    if task.assigned_employee_id is not None:
        raise ValueError(TASK_ALREADY_TAKEN)
    claimed = db.execute(
        update(Task)
        .where(Task.id == task_id, Task.assigned_employee_id.is_(None))
        .values(assigned_employee_id=user.employee_id)
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise ValueError(TASK_ALREADY_TAKEN)
    record_audit_entry(
        db, action="geändert", entity_type=TASK_ENTITY_TYPE, entity_id=task.id,
        entity_label=f"Nr. {task.id} · {task.title}", project_id=task.project_id,
        field_name="assigned_employee_id", field_label="Zuständig (übernommen)",
        old_value=None, new_value=_employee_name(db.get(Employee, user.employee_id)),
        actor_user_id=user.id, actor_name=user.display_name or user.username,
    )
    db.commit()
    task = _load_task(db, task_id)
    notify_task_assignment(db, task)
    return task_to_dict(task, _columns_by_key(db))


def release_task(db: Session, task_id: int) -> dict | None:
    """"Zurück in den Büro-Eingang" -- macht eine Aufgabe wieder empfängerlos. Rollenblind; wer das
    darf, entscheidet seit 1.8.26 der Router über task_visible_for_user() (dieselbe Regel wie das
    Lesen: eigene und empfängerlose Aufgaben, Admin alle)."""
    task = db.get(Task, task_id)
    if task is None:
        return None
    task.assigned_employee_id = None
    db.commit()
    return task_to_dict(_load_task(db, task.id), _columns_by_key(db))


def load_task_settings(db: Session) -> TaskSettings:
    """Nur lesen -- die Zeile legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    return einzelzeile(db, TaskSettings)


def update_task_settings(db: Session, notify_on_assignment: bool) -> TaskSettings:
    settings = load_task_settings(db)
    settings.notify_on_assignment = notify_on_assignment
    db.commit()
    return settings


# Art einer Aufgabe in der Benachrichtigung (seit 1.8.53) -- aus dem Ursprung (source_module), nie aus dem Inhalt.
TASK_MAIL_KINDS = {
    "maengel": "Mangel",
    "wartungsbericht": "Einsatzbericht",
    "wartungsvertrag": "Wartungsvertrag",
    "checklisten": "Checkliste",
    "buchhaltung": "Eingangsrechnung",
    "betriebsmittel": "Betriebsmittel",
    "betriebskosten": "Betriebskosten",
}
TASK_MAIL_KIND_DEFAULT = "allgemeine Aufgabe"
TASK_MAIL_SUBJECT = "Neue Aufgabe im ERP"


def task_mail_kind(source_module: str | None) -> str:
    return TASK_MAIL_KINDS.get(source_module or "", TASK_MAIL_KIND_DEFAULT)


def task_mail_link(db: Session, task_id: int) -> str:
    """Link zur Aufgabe (/tasks?task=<id> öffnet sie im Editor). Absolut nur mit der öffentlichen Adresse aus
    Einstellungen -> Allgemein -- die Benachrichtigung entsteht in der Geschäftslogik, ohne Anfrage."""
    from .settings import load_general_settings

    path = f"/tasks?task={task_id}"
    base = (load_general_settings(db).public_base_url or "").strip().rstrip("/")
    return f"{base}{path}" if base else f"im ERP unter „Aufgaben“ ({path})"


def notify_task_assignment(db: Session, task: Task) -> None:
    """Benachrichtigt den zugewiesenen Mitarbeiter per E-Mail über eine neue Aufgabe (seit
    1.1.3). Stiller No-op, wenn die Benachrichtigung abgeschaltet ist oder der Mitarbeiter
    keine E-Mail-Adresse hinterlegt hat (EmployeeProfile.email ist optional). Ein Versandfehler
    (z. B. falsch konfigurierter Mailserver) wird hier abgefangen -- er darf das eigentliche
    Speichern der Aufgabe, das zu diesem Zeitpunkt bereits erfolgt ist, nicht rückwirkend als
    Fehler erscheinen lassen.

    Seit 1.8.17 über app/email_dispatch.py: jede Benachrichtigung steht im Versandprotokoll
    (Dokumentart "aufgabe", nur für Admins sichtbar). Ein fehlgeschlagener Versand ist dort
    sichtbar statt still verschluckt; die Aufgabe bleibt trotzdem gespeichert. Kein
    Parallelversand-Block: jede Zuweisung ist ein eigener Anlass.

    Seit 1.8.53 ohne Inhalt der Aufgabe (Betreibervorgabe 2c-2b): nur Art (aus dem Ursprung,
    task_mail_kind()) und Link. Titel, Beschreibung, Projekt, Fälligkeit und Priorität verließen
    vorher das ERP -- an die Adresse im Mitarbeiterprofil, die privat sein kann (seit 1.8.51 mit
    der Kurzfassung eines Mangels im Titel). tests/test_v355_aufgaben_mail_ohne_inhalt.py prüft
    jede Aufgaben-Mail: per AST, welche Felder der Aufgabe hier gelesen werden, und am Versand
    selbst, dass keins ankommt."""
    from .email_dispatch import DispatchConflict, dispatch_email, new_dispatch_key
    settings = load_task_settings(db)
    if not settings.notify_on_assignment:
        return
    employee = task.assigned_employee
    if employee is None or employee.profile is None or not employee.profile.email:
        return
    body = (
        "Hallo,\n\n"
        "dir wurde im ERP eine Aufgabe zugewiesen.\n\n"
        f"Art: {task_mail_kind(task.source_module)}\n"
        f"Link: {task_mail_link(db, task.id)}\n\n"
        "Was zu tun ist, steht nur im ERP (nach der Anmeldung).\n\n"
        "Diese Nachricht wurde automatisch vom ERP versendet."
    )
    try:
        dispatch_email(
            db, dispatch_key=new_dispatch_key(f"aufgabe-{task.id}"), document_type="aufgabe",
            document_id=task.id, document_number=None, to=employee.profile.email, cc=None,
            subject=TASK_MAIL_SUBJECT, body_text=body, block_parallel=False,
        )
    except (ValueError, DispatchConflict):
        pass


def create_task(db: Session, title: str, description: str | None = None, priority: str = "normal",
                 due_date: date | None = None, assigned_employee_id: int | None = None,
                 project_id: int | None = None, created_by_user_id: int | None = None,
                 source_module: str | None = None, source_label: str | None = None,
                 source_url: str | None = None, status: str | None = None,
                 min_visible_role: str | None = None) -> dict:
    """Legt eine neue Aufgabe an. Wird sowohl vom manuellen "+Aufgabe"-Endpunkt als auch
    -- künftig -- direkt von anderen Modulen aufgerufen (siehe Modul-Docstring oben).

    min_visible_role (seit 1.5.0): optionale Ziel-Mindestrolle für eine empfängerlose Aufgabe
    (siehe list_tasks_for_user()/claim_task()). Wirkt unabhängig von assigned_employee_id --
    bewusst nicht dagegen validiert, ob beide gleichzeitig gesetzt sind: eine bereits
    zugewiesene Aufgabe wird über die Zuweisung selbst gesteuert, ein zusätzlich gesetztes
    min_visible_role ist dann folgenlos, aber kein Fehler."""
    if min_visible_role is not None and min_visible_role not in ROLES:
        raise ValueError(f"Unbekannte Rolle: {min_visible_role}")
    columns_by_key = _columns_by_key(db)
    if status is None:
        status = _default_column_key(db)
    else:
        _validate_status(status, columns_by_key)
    task = Task(
        title=title.strip(), description=(description or None), status=status, priority=priority,
        due_date=due_date, assigned_employee_id=assigned_employee_id, project_id=project_id,
        created_by_user_id=created_by_user_id, source_module=source_module,
        source_label=source_label, source_url=source_url, min_visible_role=min_visible_role,
    )
    db.add(task)
    db.commit()
    task = _load_task(db, task.id)
    if assigned_employee_id is not None:
        notify_task_assignment(db, task)
    return task_to_dict(task, columns_by_key)


# Ohne min_visible_role (seit 1.8.26): die Sichtbarkeitsgrenze setzt nur, wer die Aufgabe anlegt.
TASK_UPDATE_FIELDS = ("title", "description", "status", "priority", "due_date", "assigned_employee_id",
                      "project_id")


def update_task(db: Session, task_id: int, **changes) -> dict | None:
    """Teil-Update (seit 1.8.25): nur die übergebenen Felder ändern sich. Der Editor auf /tasks
    schickt min_visible_role nicht mit -- vorher setzte jedes Speichern es auf None zurück, eine
    Finanz-Aufgabe wurde dadurch für jedes Büro-Konto sichtbar. Seit 1.8.26 ist die
    Sichtbarkeitsgrenze hier gar nicht mehr änderbar (TASK_UPDATE_FIELDS)."""
    unknown = set(changes) - set(TASK_UPDATE_FIELDS)
    if unknown:
        raise TypeError(f"Unbekannte Felder: {sorted(unknown)}")
    task = db.get(Task, task_id)
    if task is None:
        return None
    columns_by_key = _columns_by_key(db)
    if "status" in changes:
        _validate_status(changes["status"], columns_by_key)
    was_done = columns_by_key[task.status].is_done if task.status in columns_by_key else False
    previous_employee_id = task.assigned_employee_id
    if "title" in changes:
        changes["title"] = changes["title"].strip()
    if "description" in changes:
        changes["description"] = changes["description"] or None
    for key, value in changes.items():
        setattr(task, key, value)
    now_done = columns_by_key[task.status].is_done if task.status in columns_by_key else False
    if now_done and not was_done:
        task.completed_at = datetime.utcnow()
    elif not now_done and was_done:
        task.completed_at = None
    db.commit()
    task = _load_task(db, task.id)
    if task.assigned_employee_id is not None and task.assigned_employee_id != previous_employee_id:
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
