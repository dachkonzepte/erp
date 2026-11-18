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

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from .grunddaten import einzelzeile
from .meldungen import KEIN_MITARBEITER
from .audit import LOESCHANLASS, TASK_ENTITY_TYPE, record_audit_entry
from .models import AppUser, Employee, Task, TaskChecklistItem, TaskColumn, TaskSettings
from .suchmuster import passt
from .zugehoerigkeit import require_project
from .permissions import ROLE_ADMIN, ROLE_LABELS, ROLE_OFFICE_AUFTRAG, ROLES, has_min_role, has_role

PRIORITIES = ("niedrig", "normal", "hoch", "dringend")


class ZuweisungOhneRolle(ValueError):
    """Seit 1.9.369 (F2 c aus dem Bericht 1.9.364): die Person, der eine Aufgabe zugewiesen werden soll, sähe sie nicht -- 422 mit Grund."""
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


def _filter(query, *, status: str | None, project_id: int | None, include_archived: bool, search: str | None):
    """Die Filter einer Aufgabenliste, die nichts mit der Sichtbarkeit zu tun haben -- list_tasks() und aufgaben_abfrage()."""
    if status is not None:
        query = query.where(Task.status == status)
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    if search:
        query = query.where(passt(Task.title, search))  # seit 1.9.360 wie die Büro-Suche (telefonbuch(), F3)
    if not include_archived:
        query = query.where(Task.archived == False)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    return query


def _als_liste(db: Session, query) -> list[dict]:
    """Eine Aufgabenliste laden: Fälligkeit zuerst, ohne Fälligkeit am Ende, dann die neueste."""
    query = query.options(
        selectinload(Task.assigned_employee), selectinload(Task.project), selectinload(Task.checklist_items)
    ).order_by(Task.due_date.is_(None), Task.due_date.nulls_last(), Task.id.desc())
    columns_by_key = _columns_by_key(db)
    return [task_to_dict(t, columns_by_key) for t in db.scalars(query).all()]


def list_tasks(db: Session, employee_id: int | None = None, status: str | None = None,
                project_id: int | None = None, include_archived: bool = False,
                unassigned_only: bool = False, search: str | None = None) -> list[dict]:
    query = select(Task)
    if unassigned_only:
        query = query.where(Task.assigned_employee_id.is_(None))
    elif employee_id is not None:
        query = query.where(Task.assigned_employee_id == employee_id)
    return _als_liste(db, _filter(query, status=status, project_id=project_id, include_archived=include_archived, search=search))


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


def sichtbar_in_sql(user: AppUser):
    """task_visible_for_user() als Bedingung in SQL (seit 1.9.364) -- dieselbe Regel für eine Liste, die in der Datenbank
    zählt und begrenzt: eine erfüllte Ziel-Mindestrolle; der Admin dann alles, jedes andere Büro-Konto die eigenen und die
    empfängerlosen Aufgaben. tests/test_v764_aufgaben_suche_in_sql.py vergleicht beide über jede Kombination von Rolle,
    Konto, Zuweisung und Mindestrolle -- wer die eine ändert, ändert die andere. Nur für Konten ab buero_auftrag
    (aufgaben_abfrage() prüft das vorher)."""
    erfuellt = [rolle for rolle in ROLES if has_min_role(user, rolle)]
    bedingung = or_(Task.min_visible_role.is_(None), Task.min_visible_role.in_(erfuellt))
    if has_role(user, ROLE_ADMIN):
        return bedingung
    eigen = [Task.assigned_employee_id.is_(None)]
    if user.employee_id is not None:
        eigen.append(Task.assigned_employee_id == user.employee_id)
    return and_(bedingung, or_(*eigen))


def aufgaben_abfrage(user: AppUser, *, status: str | None = None, project_id: int | None = None,
                     include_archived: bool = False, employee_id: int | None = None,
                     unassigned_only: bool = False, mit_eingang: bool = False, search: str | None = None):
    """Die Aufgaben, die dieses Konto sieht, als Abfrage ohne Reihenfolge (seit 1.9.364): die Sichtbarkeitsregel
    (sichtbar_in_sql()) und die Auswahl des Aufrufers. list_tasks_for_user() führt sie aus; die Büro-Suche
    (app/search.py::_search_tasks()) zählt und begrenzt dieselbe Abfrage in SQL -- die Regel steht nur hier. None: das
    Konto sieht keine Aufgabe (unter buero_auftrag).

    Auswahl: unassigned_only -- nur der gemeinsame Büro-Eingang, für jedes Konto gleich; mit_eingang -- alles, was die
    Regel zeigt, eigene und empfängerlose zusammen (die Suche: ein Büro-Konto ohne Mitarbeiter nur den Eingang, der Admin
    alles); sonst der Admin frei (employee_id), ein Büro-Konto nur die eigenen (ohne Mitarbeiter ValueError)."""
    if not has_min_role(user, ROLE_OFFICE_AUFTRAG):
        return None
    query = select(Task).where(sichtbar_in_sql(user))
    if unassigned_only:
        query = query.where(Task.assigned_employee_id.is_(None))
    elif mit_eingang:
        pass
    elif has_role(user, ROLE_ADMIN):
        if employee_id is not None:
            query = query.where(Task.assigned_employee_id == employee_id)
    else:
        if user.employee_id is None:
            raise ValueError(KEIN_MITARBEITER)
        query = query.where(Task.assigned_employee_id == user.employee_id)
    return _filter(query, status=status, project_id=project_id, include_archived=include_archived, search=search)


def zuweisung_grund(db: Session, assigned_employee_id: int | None, min_visible_role: str | None) -> str | None:
    """Seit 1.9.369 (F2 c aus dem Bericht 1.9.364): sähe die Person, der die Aufgabe zugewiesen wird, sie? Nur bei einer Mindestrolle; es zählt jedes
    aktive Konto der Person nach DERSELBEN Regel wie das Lesen (task_visible_for_user()). Nein: der Grund, z. B. „Diese Aufgabe sieht nur Büro – Finanzen
    und Administrator – Erika Eins hat kein Konto mit dieser Rolle.“; ja (oder ohne Zuweisung, ohne Mindestrolle): None."""
    if assigned_employee_id is None or min_visible_role is None:
        return None
    konten = db.scalars(select(AppUser).where(AppUser.employee_id == assigned_employee_id, AppUser.active.is_(True)).order_by(AppUser.id)).all()
    if any(task_visible_for_user(k, assigned_employee_id, min_visible_role) for k in konten):
        return None
    sehen = [ROLE_LABELS[r] for r in ROLES if has_min_role(AppUser(role=r), ROLE_OFFICE_AUFTRAG) and has_min_role(AppUser(role=r), min_visible_role)]
    rollen = ", ".join(sehen[:-1]) + " und " + sehen[-1] if len(sehen) > 1 else (sehen[0] if sehen else "niemand")
    name = _employee_name(db.get(Employee, assigned_employee_id)) or "diese Person"
    return f"Diese Aufgabe sieht nur {rollen} – {name} hat kein Konto mit dieser Rolle."


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

    search filtert den Titel (passt(), wie die Büro-Suche). Seit 1.9.364 baut aufgaben_abfrage() die
    Abfrage samt Sichtbarkeitsregel; die Büro-Suche (app/search.py::_search_tasks()) zählt und
    begrenzt dieselbe in SQL, statt diese Liste zweimal ganz zu laden -- die Regel wird dort NICHT
    ein zweites Mal nachgebaut, siehe dort.

    min_visible_role (seit 1.5.0, allgemeine Erweiterung des claim/release-Modells, nicht nur
    für Betriebskosten -- siehe CLAUDE.md "Aufgabe"): eine empfängerlose Aufgabe kann optional
    eine Ziel-Mindestrolle tragen. Der Filter gilt UNBEDINGT für jede Zeile (seit 1.9.364 in SQL,
    sichtbar_in_sql(); bis dahin je Zeile über task_visible_for_user()), nicht nur im
    unassigned_only-Zweig -- auch eine zugewiesene Aufgabe sieht ihre Person nur mit der Mindestrolle
    (bis 1.9.368 stand hier, das sei unabhängig von min_visible_role -- falsch; seit 1.9.369 lehnt
    die Zuweisung von Hand eine solche Person ab, zuweisung_grund()). Ein buero_auftrag-Konto sieht dadurch eine
    finanz-adressierte Aufgabe an KEINER Stelle -- weder in der Liste noch im gemeinsamen
    Büro-Eingang."""
    query = aufgaben_abfrage(user, status=status, project_id=project_id, include_archived=include_archived,
                             employee_id=employee_id, unassigned_only=unassigned_only, search=search)
    if query is None:
        return []
    return _als_liste(db, query)


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
        raise ValueError(KEIN_MITARBEITER)
    task = db.get(Task, task_id)
    if task is None:
        return None
    if task.min_visible_role is not None and not has_min_role(user, task.min_visible_role):
        raise PermissionError("Diese Aufgabe ist für deine Rolle nicht sichtbar.")
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
                 min_visible_role: str | None = None, zuweisung: str = "eingang") -> dict:
    """Legt eine neue Aufgabe an. Wird sowohl vom manuellen "+Aufgabe"-Endpunkt als auch
    -- künftig -- direkt von anderen Modulen aufgerufen (siehe Modul-Docstring oben).

    min_visible_role (seit 1.5.0): optionale Ziel-Mindestrolle; sie gilt für jede Aufgabe, auch eine
    zugewiesene (task_visible_for_user(); bis 1.9.368 stand hier fälschlich, sie sei dann folgenlos).
    Seit 1.9.369 (F2 c): sähe die zugewiesene Person die Aufgabe nicht (zuweisung_grund()), lehnt
    zuweisung="ablehnen" (der Endpunkt, von Hand) mit ZuweisungOhneRolle ab; die Vorgabe "eingang" (die
    Module) legt sie empfängerlos in den Büro-Eingang -- wie ohne Sachbearbeiter."""
    if min_visible_role is not None and min_visible_role not in ROLES:
        raise ValueError(f"Unbekannte Rolle: {min_visible_role}")
    grund = zuweisung_grund(db, assigned_employee_id, min_visible_role)  # seit 1.9.369
    if grund is not None:
        if zuweisung == "ablehnen":
            raise ZuweisungOhneRolle(grund)
        assigned_employee_id = None
    if project_id is not None:  # seit 1.8.71: unbekannt 404 statt Fremdschlüssel (PostgreSQL 500)
        require_project(db, project_id)
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
    if changes.get("project_id") is not None:  # seit 1.8.71: unbekannt 404 statt Fremdschlüssel (PostgreSQL 500)
        require_project(db, changes["project_id"])
    if changes.get("assigned_employee_id") is not None:  # seit 1.9.369 (F2 c): nicht an jemanden, der die Aufgabe nicht sähe
        grund = zuweisung_grund(db, changes["assigned_employee_id"], task.min_visible_role)
        if grund is not None:
            raise ZuweisungOhneRolle(grund)
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


ANLASS_VON_HAND = "von Hand"

# Seit 1.9.346 (E7, Entscheidung Tobias 17.11.2026): zeigt etwas auf eine Aufgabe, wird sie nicht gelöscht -- 409 mit dem Grund und dem Rat, sie zu
# erledigen oder zu archivieren (bis 1.9.345 scheiterte das Löschen am Fremdschlüssel, live 500). Jeder Fremdschlüssel auf tasks steht in
# MIT_DER_AUFGABE oder VERWEISE_AUF_AUFGABEN; ein neuer kommt dort hinein (Wächter tests/test_v746_aufgabe_und_projekt_loeschen.py).
MIT_DER_AUFGABE = {("task_checklist_items", "task_id"): "Unteraufgaben (Kaskade an Task.checklist_items)"}
VERWEISE_AUF_AUFGABEN = {
    ("findings", "follow_up_task_id"): "einem Befund im Einsatzbericht",
    ("checklist_rule_executions", "task_id"): "einer Regel einer Checkliste",
}


class AufgabeVerwendet(ValueError):
    """Etwas zeigt auf die Aufgabe (seit 1.9.346, E7) -- der Router antwortet mit 409."""


def aufgabe_verwendungen(db: Session, task_id: int) -> list[str]:
    """Wozu die Aufgabe gehört (Bereiche aus VERWEISE_AUF_AUFGABEN), leer = nichts zeigt auf sie."""
    from .database import Base

    bereiche = []
    for (tabelle, spalte), bereich in VERWEISE_AUF_AUFGABEN.items():
        t = Base.metadata.tables[tabelle]
        if db.scalar(select(func.count()).select_from(t).where(t.c[spalte] == task_id)):
            bereiche.append(bereich)
    return bereiche


def aufgabe_loeschen(db: Session, task: Task, anlass: str, user: AppUser | None = None) -> None:
    """Der eine Weg, eine Aufgabe zu löschen (seit 1.9.344): merkt Anlass und Konto an der Aufgabe und löscht sie, die Unteraufgaben gehen per
    Kaskade mit. Den Eintrag in der Änderungshistorie (Titel, Konto, Zeitpunkt, Anlass) schreibt app/audit.py::collect_audit() im Flush -- auch
    für ein Löschen an diesem Weg vorbei, dann „ohne Angabe“. Ein Löschen über die Tabelle (delete(Task), SQL) sähe sie nicht: verboten, Wächter
    tests/test_v744_aufgaben_loeschen_historie.py. Seit 1.9.346 nicht, wenn etwas auf die Aufgabe zeigt (AufgabeVerwendet). Committet nicht."""
    bereiche = aufgabe_verwendungen(db, task.id)  # seit 1.9.346 (E7)
    if bereiche:
        raise AufgabeVerwendet(f"Die Aufgabe gehört zu {' und '.join(bereiche)} – deshalb lässt sie sich nicht löschen. "
                               "Erledige oder archiviere sie stattdessen.")
    setattr(task, LOESCHANLASS, (anlass, user))
    db.delete(task)


def delete_task(db: Session, task_id: int, user: AppUser | None = None) -> bool:
    task = db.get(Task, task_id)
    if task is None:
        return False
    aufgabe_loeschen(db, task, ANLASS_VON_HAND, user)
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
