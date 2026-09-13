"""Router: materials (seit 1.0.25), Materialkataloge (seit 1.0.30).

Verwaltung des Materialkatalogs selbst. Die Zuordnung, WELCHE Materialien zu
einer Leistung gehören, läuft weiterhin über service_materials (bestehende
Endpunkte in services.py) -- hier geht es nur um den Katalog der Materialien
selbst (anlegen, auflisten, bearbeiten) und seit 1.0.30 zusätzlich um die
Materialkataloge (Gruppen), in die Materialien einsortiert werden können.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from ..database import get_db
from ..material_groups import (
    copy_material_to_group, create_material_group, list_material_groups,
    move_material_to_group, set_material_group_archived,
)
from ..materials import create_manual_material, get_material, list_materials, update_material
from ..models import Material, MaterialGroup
from ..schemas import (
    MaterialCatalogCreate, MaterialCatalogOut, MaterialCatalogUpdate,
    MaterialGroupCreate, MaterialGroupOut, MaterialMoveOrCopy,
)

router = APIRouter()


@router.get("/api/materials", response_model=list[MaterialCatalogOut])
def get_materials(search: str | None = Query(default=None), catalog_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    return list_materials(db, search=search, catalog_id=catalog_id)


@router.get("/api/materials/{material_id}", response_model=MaterialCatalogOut)
def get_material_by_id(material_id: int, db: Session = Depends(get_db)):
    material = get_material(db, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")
    return material


@router.post("/api/materials", response_model=MaterialCatalogOut)
def post_material(payload: MaterialCatalogCreate, db: Session = Depends(get_db)):
    if payload.catalog_id is not None and db.get(MaterialGroup, payload.catalog_id) is None:
        raise HTTPException(status_code=404, detail="Materialkatalog nicht gefunden.")
    return create_manual_material(
        db, payload.name, payload.unit, payload.purchase_price,
        article_number=payload.article_number, price_basis=payload.price_basis,
        catalog_id=payload.catalog_id,
    )


@router.put("/api/materials/{material_id}", response_model=MaterialCatalogOut)
def put_material(material_id: int, payload: MaterialCatalogUpdate, db: Session = Depends(get_db)):
    material = update_material(
        db, material_id, payload.name, payload.unit, payload.purchase_price,
        payload.article_number, payload.price_basis,
    )
    if material is None:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")
    return material


@router.post("/api/materials/{material_id}/move", response_model=MaterialCatalogOut)
def move_material(material_id: int, payload: MaterialMoveOrCopy, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")
    if payload.catalog_id is not None and db.get(MaterialGroup, payload.catalog_id) is None:
        raise HTTPException(status_code=404, detail="Materialkatalog nicht gefunden.")
    return move_material_to_group(db, material, payload.catalog_id)


@router.post("/api/materials/{material_id}/copy", response_model=MaterialCatalogOut)
def copy_material(material_id: int, payload: MaterialMoveOrCopy, db: Session = Depends(get_db)):
    original = db.get(Material, material_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")
    if payload.catalog_id is not None and db.get(MaterialGroup, payload.catalog_id) is None:
        raise HTTPException(status_code=404, detail="Materialkatalog nicht gefunden.")
    return copy_material_to_group(db, original, payload.catalog_id)


@router.get("/api/material-groups", response_model=list[MaterialGroupOut])
def get_material_groups(include_archived: bool = Query(default=False), db: Session = Depends(get_db)):
    return list_material_groups(db, include_archived=include_archived)


@router.post("/api/material-groups", response_model=MaterialGroupOut)
def post_material_group(payload: MaterialGroupCreate, db: Session = Depends(get_db)):
    return create_material_group(db, payload.name, payload.description)


@router.post("/api/material-groups/{group_id}/archive", response_model=MaterialGroupOut)
def archive_material_group(group_id: int, db: Session = Depends(get_db)):
    try:
        group = set_material_group_archived(db, group_id, True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if group is None:
        raise HTTPException(status_code=404, detail="Materialkatalog nicht gefunden.")
    return group


@router.post("/api/material-groups/{group_id}/unarchive", response_model=MaterialGroupOut)
def unarchive_material_group(group_id: int, db: Session = Depends(get_db)):
    group = set_material_group_archived(db, group_id, False)
    if group is None:
        raise HTTPException(status_code=404, detail="Materialkatalog nicht gefunden.")
    return group
