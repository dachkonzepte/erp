"""Router: project_pipeline_columns (seit 1.3.70) -- Verwaltung der konfigurierbaren
Projekt-Pipeline-Spalten, siehe app/project_pipeline_columns.py für die Geschäftslogik und
app/models.py::ProjectPipelineColumn für die Begründung, warum das ein von Project.status
getrenntes Feld ist.

Dieselbe Büro+Admin-Sperre wie der Rest der Projektverwaltung (app/routers/projects.py) --
Projekte sind für `field` vollständig gesperrt, das schließt die Spaltenliste ein. Die vier
verändernden Endpunkte sind zusätzlich admin-only (Muster app/routers/task_columns.py). Kein
Modul-Gate nötig -- Projekte sind Teil der immer aktiven Kern-ERP-Kette, kein
OPTIONAL_MODULES-Eintrag."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import AppUser
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..project_pipeline_columns import create_column, delete_column, list_columns, reorder_columns, update_column
from ..schemas import (
    ProjectPipelineColumnCreate,
    ProjectPipelineColumnOut,
    ProjectPipelineColumnReorder,
    ProjectPipelineColumnUpdate,
)

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


@router.get("/api/project-pipeline-columns", response_model=list[ProjectPipelineColumnOut])
def get_project_pipeline_columns(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return list_columns(db)


@router.post("/api/project-pipeline-columns", response_model=ProjectPipelineColumnOut)
def post_project_pipeline_column(payload: ProjectPipelineColumnCreate, db: Session = Depends(get_db),
                                  _admin=Depends(require_admin("Nur Administratoren dürfen Pipeline-Spalten anlegen."))):
    try:
        return create_column(db, payload.label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/project-pipeline-columns/reorder", response_model=list[ProjectPipelineColumnOut])
def put_project_pipeline_columns_reorder(payload: ProjectPipelineColumnReorder, db: Session = Depends(get_db),
                                          _admin=Depends(require_admin("Nur Administratoren dürfen Pipeline-Spalten umsortieren."))):
    try:
        return reorder_columns(db, payload.ordered_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/project-pipeline-columns/{column_id}", response_model=ProjectPipelineColumnOut)
def put_project_pipeline_column(column_id: int, payload: ProjectPipelineColumnUpdate, db: Session = Depends(get_db),
                                 _admin=Depends(require_admin("Nur Administratoren dürfen Pipeline-Spalten bearbeiten."))):
    try:
        return update_column(db, column_id, payload.label)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/project-pipeline-columns/{column_id}")
def delete_project_pipeline_column(column_id: int, db: Session = Depends(get_db),
                                    _admin=Depends(require_admin("Nur Administratoren dürfen Pipeline-Spalten löschen."))):
    try:
        delete_column(db, column_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
