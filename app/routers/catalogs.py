"""Router: catalogs (seit 1.0.14).

Verwaltung der Leistungskataloge selbst (anlegen, auflisten, archivieren).
Die Leistungen innerhalb eines Katalogs laufen weiterhin über die
bestehenden /api/services-Endpunkte (jetzt mit optionalem catalog_id-Filter).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..catalogs import create_catalog, list_catalogs, set_catalog_archived
from ..database import get_db
from ..models import AppUser
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..schemas import CatalogCreate, CatalogOut

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): reine Katalog-Container-Verwaltung, Büro/Admin.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


@router.get("/api/catalogs", response_model=list[CatalogOut])
def get_catalogs(include_archived: bool = Query(default=False), db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return list_catalogs(db, include_archived=include_archived)


@router.post("/api/catalogs", response_model=CatalogOut)
def post_catalog(payload: CatalogCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return create_catalog(db, payload.name, payload.description)


@router.post("/api/catalogs/{catalog_id}/archive", response_model=CatalogOut)
def archive_catalog(catalog_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    try:
        catalog = set_catalog_archived(db, catalog_id, True)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if catalog is None:
        raise HTTPException(status_code=404, detail="Katalog nicht gefunden.")
    return catalog


@router.post("/api/catalogs/{catalog_id}/unarchive", response_model=CatalogOut)
def unarchive_catalog(catalog_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    catalog = set_catalog_archived(db, catalog_id, False)
    if catalog is None:
        raise HTTPException(status_code=404, detail="Katalog nicht gefunden.")
    return catalog
