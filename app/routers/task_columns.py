"""Router: task_columns (seit 1.1.1) -- Verwaltung der konfigurierbaren Aufgaben-Spalten.

GET ist für jeden eingeloggten Benutzer erreichbar (Board + Editor-Dropdown brauchen die
Liste), alle verändernden Endpunkte nur für Admins. Zusätzlich wie beim übrigen
Aufgabenmanagement hinter is_module_enabled() -- 403 bei deaktiviertem Modul, auch für
Admins, damit die API nicht heimlich weiter erreichbar bleibt."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..modules import is_module_enabled
from ..schemas import TaskColumnCreate, TaskColumnOut, TaskColumnReorder, TaskColumnUpdate
from ..task_columns import create_column, delete_column, list_columns, reorder_columns, update_column

router = APIRouter()

MODULE_KEY = "aufgabenmanagement"


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Aufgabenmanagement ist deaktiviert.")


@router.get("/api/task-columns", response_model=list[TaskColumnOut])
def get_task_columns(db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return list_columns(db)


@router.post("/api/task-columns", response_model=TaskColumnOut)
def post_task_column(payload: TaskColumnCreate, db: Session = Depends(get_db),
                      _admin=Depends(require_admin("Nur Administratoren dürfen Aufgaben-Spalten anlegen."))):
    _require_module_enabled(db)
    try:
        return create_column(db, payload.label, payload.is_done)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/task-columns/reorder", response_model=list[TaskColumnOut])
def put_task_columns_reorder(payload: TaskColumnReorder, db: Session = Depends(get_db),
                              _admin=Depends(require_admin("Nur Administratoren dürfen Aufgaben-Spalten umsortieren."))):
    _require_module_enabled(db)
    try:
        return reorder_columns(db, payload.ordered_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/task-columns/{column_id}", response_model=TaskColumnOut)
def put_task_column(column_id: int, payload: TaskColumnUpdate, db: Session = Depends(get_db),
                     _admin=Depends(require_admin("Nur Administratoren dürfen Aufgaben-Spalten bearbeiten."))):
    _require_module_enabled(db)
    try:
        return update_column(db, column_id, payload.label, payload.is_done)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/task-columns/{column_id}")
def delete_task_column(column_id: int, db: Session = Depends(get_db),
                        _admin=Depends(require_admin("Nur Administratoren dürfen Aufgaben-Spalten löschen."))):
    _require_module_enabled(db)
    try:
        delete_column(db, column_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
