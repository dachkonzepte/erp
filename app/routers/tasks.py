"""Router: tasks (seit 1.1.0) -- Aufgabenmanagement, das erste tatsächlich
ein-/ausschaltbare Modul (siehe app/modules.py, "aufgabenmanagement").

Jeder Endpunkt prüft zuerst is_module_enabled() -- 403 bei deaktiviertem Modul,
unabhängig von der Rolle, damit die API nicht heimlich weiter erreichbar ist, nur weil
die Oberfläche versteckt ist. Die Sichtbarkeits-Logik in GET /api/tasks läuft seit der
Aufgaben-Sichtbarkeitsänderung ausschließlich über app/tasks.py::list_tasks_for_user() --
die EINE Stelle, an der jede Task-Ansicht entschieden wird (Liste, Dashboard-Widget,
Zähler), siehe CLAUDE.md "Änderung am Aufgabenmodul". Empfängerlose Aufgaben
(unassigned_only=True) sind seither für JEDES Büro-/Admin-Konto sichtbar -- der gemeinsame
Büro-Eingang; eine persönlich zugewiesene Aufgabe eines Kollegen bleibt weiterhin
unsichtbar, unverändert."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..modules import is_module_enabled
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import (
    TaskChecklistItemCreate, TaskChecklistItemOut, TaskChecklistItemUpdate,
    TaskCreate, TaskOut, TaskSettingsOut, TaskSettingsUpdate, TaskUpdate,
)
from ..tasks import (
    add_checklist_item, claim_task, create_task, delete_checklist_item, delete_task,
    get_or_create_task_settings, list_tasks_for_user, release_task, set_task_archived,
    update_checklist_item, update_task, update_task_settings,
)
from ..models import AppUser, Task

router = APIRouter()

MODULE_KEY = "aufgabenmanagement"

# Seit "Rechtekonzept" (siehe CLAUDE.md → "Aufgaben"): heute wird in der echten Datenbank keine
# einzige Aufgabe an einen Monteur zugewiesen -- Aufgaben bleiben deshalb für `field` vorerst
# vollständig gesperrt, unabhängig von der bereits bestehenden Employee-Eigentümer-Filterung
# unten (die weiterhin unverändert für jeden Nicht-Admin greift, der `office` erreicht). Siehe
# CLAUDE.md für die dabei gefundene, noch offene Lücke (PUT/DELETE/archive prüfen heute KEINE
# Eigentümerschaft) -- Grund, warum eine Öffnung für `field` nicht ohne Weiteres möglich ist.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Aufgabenmanagement ist deaktiviert.")


def _require_task_access(db: Session, request: Request, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    user = getattr(request.state, "erp_user", None)
    if user is not None and user.role != "admin":
        if user.employee_id is None or task.assigned_employee_id != user.employee_id:
            raise HTTPException(status_code=403, detail="Sie dürfen nur eigene Aufgaben bearbeiten.")
    return task


@router.get("/api/tasks", response_model=list[TaskOut])
def get_tasks(employee_id: int | None = None, status: str | None = None,
              project_id: int | None = None, include_archived: bool = False,
              unassigned_only: bool = False, db: Session = Depends(get_db),
              _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return list_tasks_for_user(
            db, _role, status=status, project_id=project_id, include_archived=include_archived,
            employee_id=employee_id, unassigned_only=unassigned_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/api/tasks", response_model=TaskOut)
def post_task(payload: TaskCreate, request: Request, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    user = getattr(request.state, "erp_user", None)
    try:
        return create_task(
            db, title=payload.title, description=payload.description, priority=payload.priority,
            due_date=payload.due_date, assigned_employee_id=payload.assigned_employee_id,
            project_id=payload.project_id, created_by_user_id=getattr(user, "id", None),
            status=payload.status, min_visible_role=payload.min_visible_role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/tasks/{task_id}", response_model=TaskOut)
def put_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = update_task(
            db, task_id, title=payload.title, description=payload.description, status=payload.status,
            priority=payload.priority, due_date=payload.due_date,
            assigned_employee_id=payload.assigned_employee_id, project_id=payload.project_id,
            min_visible_role=payload.min_visible_role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return result


@router.delete("/api/tasks/{task_id}")
def delete_task_endpoint(task_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not delete_task(db, task_id):
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return {"ok": True}


@router.post("/api/tasks/{task_id}/archive", response_model=TaskOut)
def archive_task_endpoint(task_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = set_task_archived(db, task_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return result


@router.post("/api/tasks/{task_id}/unarchive", response_model=TaskOut)
def unarchive_task_endpoint(task_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = set_task_archived(db, task_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return result


@router.post("/api/tasks/{task_id}/claim", response_model=TaskOut)
def claim_task_endpoint(task_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """"Übernehmen" -- weist eine empfängerlose Aufgabe fest der aufrufenden Person zu. Die
    primäre Absicherung gegen einen Monteur mit geratener Aufgaben-ID ist bereits _role_dep
    (Büro/Admin, 403 vor jeder Geschäftslogik) -- siehe CLAUDE.md "Änderung am Aufgabenmodul".
    Eine zweite, feinere Absicherung (seit 1.5.0): trägt die Aufgabe ein min_visible_role, das
    die aufrufende Rolle nicht erfüllt (z. B. buero_auftrag gegen eine finanz-adressierte
    Aufgabe), wirft app/tasks.py::claim_task() ein PermissionError -- hier auf 403 gemappt,
    getrennt von der 400-Zuordnung für ValueError (Geschäftsregel)."""
    _require_module_enabled(db)
    try:
        result = claim_task(db, task_id, _role)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return result


@router.post("/api/tasks/{task_id}/release", response_model=TaskOut)
def release_task_endpoint(task_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """"Zurück in den Büro-Eingang" -- macht eine Aufgabe wieder empfängerlos. Bewusst ohne
    Eigentümerschafts-Prüfung, siehe app/tasks.py::release_task()."""
    _require_module_enabled(db)
    result = release_task(db, task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return result


@router.post("/api/tasks/{task_id}/checklist-items", response_model=TaskChecklistItemOut)
def post_checklist_item(task_id: int, payload: TaskChecklistItemCreate, request: Request, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    _require_task_access(db, request, task_id)
    try:
        item = add_checklist_item(db, task_id, payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return item


@router.put("/api/tasks/{task_id}/checklist-items/{item_id}", response_model=TaskChecklistItemOut)
def put_checklist_item(task_id: int, item_id: int, payload: TaskChecklistItemUpdate, request: Request, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    _require_task_access(db, request, task_id)
    try:
        item = update_checklist_item(db, task_id, item_id, title=payload.title, done=payload.done)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Checklisten-Punkt nicht gefunden.")
    return item


@router.delete("/api/tasks/{task_id}/checklist-items/{item_id}")
def delete_checklist_item_endpoint(task_id: int, item_id: int, request: Request, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    _require_task_access(db, request, task_id)
    if not delete_checklist_item(db, task_id, item_id):
        raise HTTPException(status_code=404, detail="Checklisten-Punkt nicht gefunden.")
    return {"ok": True}


@router.get("/api/task-settings", response_model=TaskSettingsOut)
def get_task_settings(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return get_or_create_task_settings(db)


@router.put("/api/task-settings", response_model=TaskSettingsOut)
def put_task_settings(payload: TaskSettingsUpdate, db: Session = Depends(get_db),
                       _admin=Depends(require_admin("Nur Administratoren dürfen die Aufgaben-Einstellungen ändern."))):
    _require_module_enabled(db)
    return update_task_settings(db, payload.notify_on_assignment)
