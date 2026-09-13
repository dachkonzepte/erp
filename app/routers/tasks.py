"""Router: tasks (seit 1.1.0) -- Aufgabenmanagement, das erste tatsächlich
ein-/ausschaltbare Modul (siehe app/modules.py, "aufgabenmanagement").

Jeder Endpunkt prüft zuerst is_module_enabled() -- 403 bei deaktiviertem Modul,
unabhängig von der Rolle, damit die API nicht heimlich weiter erreichbar ist, nur weil
die Oberfläche versteckt ist. Die Sichtbarkeits-Logik in GET /api/tasks ist bewusst
identisch zu get_open_work_preparation_tasks() (app/routers/work_preparation.py) und
get_absence_requests() (app/routers/absence_requests.py)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..modules import is_module_enabled
from ..schemas import (
    TaskChecklistItemCreate, TaskChecklistItemOut, TaskChecklistItemUpdate,
    TaskCreate, TaskOut, TaskSettingsOut, TaskSettingsUpdate, TaskUpdate,
)
from ..tasks import (
    add_checklist_item, create_task, delete_checklist_item, delete_task,
    get_or_create_task_settings, list_tasks, set_task_archived, update_checklist_item, update_task, update_task_settings,
)
from ..models import Task

router = APIRouter()

MODULE_KEY = "aufgabenmanagement"


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
def get_tasks(request: Request, employee_id: int | None = None, status: str | None = None,
              project_id: int | None = None, include_archived: bool = False, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    user = getattr(request.state, "erp_user", None)
    if user is not None and user.role != "admin":
        if user.employee_id is None:
            raise HTTPException(status_code=403, detail="Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet.")
        employee_id = user.employee_id
    return list_tasks(db, employee_id=employee_id, status=status, project_id=project_id, include_archived=include_archived)


@router.post("/api/tasks", response_model=TaskOut)
def post_task(payload: TaskCreate, request: Request, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    user = getattr(request.state, "erp_user", None)
    try:
        return create_task(
            db, title=payload.title, description=payload.description, priority=payload.priority,
            due_date=payload.due_date, assigned_employee_id=payload.assigned_employee_id,
            project_id=payload.project_id, created_by_user_id=getattr(user, "id", None),
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/tasks/{task_id}", response_model=TaskOut)
def put_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    try:
        result = update_task(
            db, task_id, title=payload.title, description=payload.description, status=payload.status,
            priority=payload.priority, due_date=payload.due_date,
            assigned_employee_id=payload.assigned_employee_id, project_id=payload.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return result


@router.delete("/api/tasks/{task_id}")
def delete_task_endpoint(task_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    if not delete_task(db, task_id):
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return {"ok": True}


@router.post("/api/tasks/{task_id}/archive", response_model=TaskOut)
def archive_task_endpoint(task_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    result = set_task_archived(db, task_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return result


@router.post("/api/tasks/{task_id}/unarchive", response_model=TaskOut)
def unarchive_task_endpoint(task_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    result = set_task_archived(db, task_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return result


@router.post("/api/tasks/{task_id}/checklist-items", response_model=TaskChecklistItemOut)
def post_checklist_item(task_id: int, payload: TaskChecklistItemCreate, request: Request, db: Session = Depends(get_db)):
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
def put_checklist_item(task_id: int, item_id: int, payload: TaskChecklistItemUpdate, request: Request, db: Session = Depends(get_db)):
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
def delete_checklist_item_endpoint(task_id: int, item_id: int, request: Request, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    _require_task_access(db, request, task_id)
    if not delete_checklist_item(db, task_id, item_id):
        raise HTTPException(status_code=404, detail="Checklisten-Punkt nicht gefunden.")
    return {"ok": True}


@router.get("/api/task-settings", response_model=TaskSettingsOut)
def get_task_settings(db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return get_or_create_task_settings(db)


@router.put("/api/task-settings", response_model=TaskSettingsOut)
def put_task_settings(payload: TaskSettingsUpdate, db: Session = Depends(get_db),
                       _admin=Depends(require_admin("Nur Administratoren dürfen die Aufgaben-Einstellungen ändern."))):
    _require_module_enabled(db)
    return update_task_settings(db, payload.notify_on_assignment)
