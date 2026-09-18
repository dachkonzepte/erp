"""Router: document_categories (seit 1.3.62, Fundament für die Dateiablage je Objekt, siehe
CLAUDE.md "Dateiablage je Objekt"). Verwaltung der echten Kategorie-Stammdaten -- Büro/Admin,
wie die übrige Stammdatenverwaltung (Muster app/routers/roof_areas.py, dort
GET/POST/PUT/activate/deactivate /api/roof-component-types). Bewusst KEIN DELETE-Endpunkt in
dieser Runde -- die beiden fest gesperrten Kategorien (Rechnungen/Belege, Verträge/Freigaben)
dürfen ohnehin nie verschwinden, und ob ein "Löschen blockiert bei Verwendung"-Mechanismus wie
bei RoofComponentType gebraucht wird, entscheidet sich erst, wenn echte Dokumente category_id
tragen (nächste Runde) -- vorerst reicht Deaktivieren."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..document_categories import create_category, list_categories, set_category_active, update_category
from ..models import AppUser
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import DocumentCategoryCreate, DocumentCategoryOut, DocumentCategoryUpdate

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


@router.get("/api/document-categories", response_model=list[DocumentCategoryOut])
def get_document_categories(include_inactive: bool = False, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return list_categories(db, include_inactive=include_inactive)


@router.post("/api/document-categories", response_model=DocumentCategoryOut)
def post_document_category(payload: DocumentCategoryCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        return create_category(db, payload.key, payload.label, is_sensitive=payload.is_sensitive, is_field_visible=payload.is_field_visible)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/api/document-categories/{category_id}", response_model=DocumentCategoryOut)
def put_document_category(category_id: int, payload: DocumentCategoryUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        result = update_category(db, category_id, label=payload.label, is_field_visible=payload.is_field_visible, is_sensitive=payload.is_sensitive)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden.")
    return result


@router.post("/api/document-categories/{category_id}/activate", response_model=DocumentCategoryOut)
def activate_document_category(category_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    result = set_category_active(db, category_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden.")
    return result


@router.post("/api/document-categories/{category_id}/deactivate", response_model=DocumentCategoryOut)
def deactivate_document_category(category_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    result = set_category_active(db, category_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden.")
    return result
