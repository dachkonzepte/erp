"""Router: roof_areas (seit 1.2.14) -- Dachflächen und Bauteile unter einem Objekt (Property).

Bewusst KEINE is_module_enabled("wartungen")-Prüfung: Property ist Kern-Stammdatum ohne
Eintrag in OPTIONAL_MODULES, siehe app/roof_areas.py."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RoofArea
from ..roof_area_sketches import MAX_UPLOAD_BYTES, sketch_path
from ..roof_areas import (
    clear_roof_area_sketch, create_component_type, create_layer_type,
    create_roof_area, create_roof_areas_bulk, create_roof_component, delete_component_type,
    delete_layer_type, delete_roof_area, delete_roof_component, get_roof_area, list_component_types,
    list_layer_types, list_roof_areas, list_roof_components, list_roof_layers, reorder_component_types,
    reorder_layer_types, set_component_type_active, set_layer_type_active, set_roof_area_archived,
    set_roof_area_sketch, set_roof_component_archived, set_roof_component_position, update_layer_type,
    update_component_type, update_roof_area, update_roof_component, upsert_roof_layer,
)
from ..schemas import (
    ComponentTypeReorder, LayerTypeReorder, RoofAreaBulkCreate, RoofAreaCreate, RoofAreaOut,
    RoofAreaUpdate, RoofComponentCreate, RoofComponentOut, RoofComponentPositionUpdate,
    RoofComponentTypeCreate, RoofComponentTypeOut, RoofComponentTypeUpdate, RoofComponentUpdate,
    RoofLayerOut, RoofLayerTypeCreate, RoofLayerTypeOut, RoofLayerTypeUpdate, RoofLayerUpsert,
)

router = APIRouter()

SKETCH_CONTENT_TYPES = ("image/png", "image/jpeg", "image/webp")


@router.get("/api/roof-areas", response_model=list[RoofAreaOut])
def get_roof_areas(property_id: int, include_archived: bool = False, db: Session = Depends(get_db)):
    return list_roof_areas(db, property_id, include_archived=include_archived)


@router.get("/api/roof-areas/{roof_area_id}", response_model=RoofAreaOut)
def get_roof_area_detail(roof_area_id: int, db: Session = Depends(get_db)):
    result = get_roof_area(db, roof_area_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dachfläche nicht gefunden.")
    return result


@router.post("/api/roof-areas", response_model=RoofAreaOut)
def post_roof_area(payload: RoofAreaCreate, db: Session = Depends(get_db)):
    try:
        return create_roof_area(
            db, payload.property_id, payload.name, roof_type=payload.roof_type, covering=payload.covering,
            pitch_degrees=payload.pitch_degrees, area_sqm=payload.area_sqm,
            last_renovation=payload.last_renovation,
            contractor=payload.contractor, warranty_until=payload.warranty_until, notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/properties/{property_id}/roof-areas/bulk", response_model=list[RoofAreaOut])
def post_roof_areas_bulk(property_id: int, payload: RoofAreaBulkCreate, db: Session = Depends(get_db)):
    try:
        return create_roof_areas_bulk(db, property_id, payload.roof_type, payload.names)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/roof-areas/{roof_area_id}", response_model=RoofAreaOut)
def put_roof_area(roof_area_id: int, payload: RoofAreaUpdate, db: Session = Depends(get_db)):
    try:
        result = update_roof_area(
            db, roof_area_id, payload.name, roof_type=payload.roof_type, covering=payload.covering,
            pitch_degrees=payload.pitch_degrees, area_sqm=payload.area_sqm,
            last_renovation=payload.last_renovation,
            contractor=payload.contractor, warranty_until=payload.warranty_until, notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Dachfläche nicht gefunden.")
    return result


@router.post("/api/roof-areas/{roof_area_id}/archive", response_model=RoofAreaOut)
def archive_roof_area(roof_area_id: int, db: Session = Depends(get_db)):
    result = set_roof_area_archived(db, roof_area_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Dachfläche nicht gefunden.")
    return result


@router.post("/api/roof-areas/{roof_area_id}/unarchive", response_model=RoofAreaOut)
def unarchive_roof_area(roof_area_id: int, db: Session = Depends(get_db)):
    result = set_roof_area_archived(db, roof_area_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Dachfläche nicht gefunden.")
    return result


@router.delete("/api/roof-areas/{roof_area_id}")
def delete_roof_area_endpoint(roof_area_id: int, db: Session = Depends(get_db)):
    try:
        deleted = delete_roof_area(db, roof_area_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Dachfläche nicht gefunden.")
    return {"ok": True}


@router.post("/api/roof-areas/{roof_area_id}/sketch", response_model=RoofAreaOut)
async def upload_roof_area_sketch(roof_area_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    if (file.content_type or "").lower() not in SKETCH_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Bitte PNG, JPEG oder WebP verwenden.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 10 MB.")
    result = set_roof_area_sketch(db, roof_area_id, file.filename, data)
    if result is None:
        raise HTTPException(status_code=404, detail="Dachfläche nicht gefunden.")
    return result


@router.get("/api/roof-areas/{roof_area_id}/sketch")
def get_roof_area_sketch(roof_area_id: int, db: Session = Depends(get_db)):
    result = get_roof_area(db, roof_area_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dachfläche nicht gefunden.")
    if not result["has_sketch"]:
        raise HTTPException(status_code=404, detail="Keine Skizze hinterlegt.")
    roof_area = db.get(RoofArea, roof_area_id)
    path = sketch_path(roof_area.sketch_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Skizzendatei nicht gefunden.")
    return FileResponse(path)


@router.delete("/api/roof-areas/{roof_area_id}/sketch", response_model=RoofAreaOut)
def delete_roof_area_sketch(roof_area_id: int, db: Session = Depends(get_db)):
    result = clear_roof_area_sketch(db, roof_area_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dachfläche nicht gefunden.")
    return result


@router.get("/api/roof-areas/{roof_area_id}/components", response_model=list[RoofComponentOut])
def get_roof_components(roof_area_id: int, include_archived: bool = False, db: Session = Depends(get_db)):
    return list_roof_components(db, roof_area_id, include_archived=include_archived)


@router.post("/api/roof-areas/{roof_area_id}/components", response_model=RoofComponentOut)
def post_roof_component(roof_area_id: int, payload: RoofComponentCreate, db: Session = Depends(get_db)):
    try:
        return create_roof_component(
            db, roof_area_id, payload.name, component_type=payload.component_type,
            quantity=payload.quantity, unit=payload.unit, year_built=payload.year_built,
            sort_order=payload.sort_order, notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/roof-components/{component_id}", response_model=RoofComponentOut)
def put_roof_component(component_id: int, payload: RoofComponentUpdate, db: Session = Depends(get_db)):
    try:
        result = update_roof_component(
            db, component_id, payload.name, component_type=payload.component_type,
            quantity=payload.quantity, unit=payload.unit, year_built=payload.year_built,
            sort_order=payload.sort_order, notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Bauteil nicht gefunden.")
    return result


@router.put("/api/roof-components/{component_id}/position", response_model=RoofComponentOut)
def put_roof_component_position(component_id: int, payload: RoofComponentPositionUpdate, db: Session = Depends(get_db)):
    result = set_roof_component_position(
        db, component_id, payload.sketch_x, payload.sketch_y,
        sketch_w=payload.sketch_w, sketch_h=payload.sketch_h,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Bauteil nicht gefunden.")
    return result


@router.post("/api/roof-components/{component_id}/archive", response_model=RoofComponentOut)
def archive_roof_component(component_id: int, db: Session = Depends(get_db)):
    result = set_roof_component_archived(db, component_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Bauteil nicht gefunden.")
    return result


@router.post("/api/roof-components/{component_id}/unarchive", response_model=RoofComponentOut)
def unarchive_roof_component(component_id: int, db: Session = Depends(get_db)):
    result = set_roof_component_archived(db, component_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Bauteil nicht gefunden.")
    return result


@router.delete("/api/roof-components/{component_id}")
def delete_roof_component_endpoint(component_id: int, db: Session = Depends(get_db)):
    try:
        deleted = delete_roof_component(db, component_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Bauteil nicht gefunden.")
    return {"ok": True}


# --- Dachaufbau (RoofLayerType/RoofLayer, seit 1.2.18) -- bewusst ebenfalls ungated, siehe
# Moduldocstring oben. "/reorder" ist ein konkreter Pfad und deshalb VOR "/{layer_type_id}"
# deklariert (Starlette matched nach Deklarationsreihenfolge). ---

@router.get("/api/roof-layer-types", response_model=list[RoofLayerTypeOut])
def get_layer_types(roof_type: str | None = None, include_inactive: bool = False, db: Session = Depends(get_db)):
    return list_layer_types(db, roof_type=roof_type, include_inactive=include_inactive)


@router.post("/api/roof-layer-types", response_model=RoofLayerTypeOut)
def post_layer_type(payload: RoofLayerTypeCreate, db: Session = Depends(get_db)):
    try:
        return create_layer_type(
            db, payload.key, payload.label, roof_type=payload.roof_type, option_group=payload.option_group,
            has_execution=payload.has_execution, has_thickness=payload.has_thickness, has_notes=payload.has_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/roof-layer-types/reorder", response_model=list[RoofLayerTypeOut])
def put_layer_types_reorder(payload: LayerTypeReorder, db: Session = Depends(get_db)):
    try:
        return reorder_layer_types(db, payload.roof_type, payload.ordered_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/roof-layer-types/{layer_type_id}", response_model=RoofLayerTypeOut)
def put_layer_type(layer_type_id: int, payload: RoofLayerTypeUpdate, db: Session = Depends(get_db)):
    try:
        result = update_layer_type(
            db, layer_type_id, payload.label, roof_type=payload.roof_type, option_group=payload.option_group,
            has_execution=payload.has_execution, has_thickness=payload.has_thickness, has_notes=payload.has_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Schichttyp nicht gefunden.")
    return result


@router.post("/api/roof-layer-types/{layer_type_id}/activate", response_model=RoofLayerTypeOut)
def activate_layer_type(layer_type_id: int, db: Session = Depends(get_db)):
    result = set_layer_type_active(db, layer_type_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Schichttyp nicht gefunden.")
    return result


@router.post("/api/roof-layer-types/{layer_type_id}/deactivate", response_model=RoofLayerTypeOut)
def deactivate_layer_type(layer_type_id: int, db: Session = Depends(get_db)):
    result = set_layer_type_active(db, layer_type_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Schichttyp nicht gefunden.")
    return result


@router.delete("/api/roof-layer-types/{layer_type_id}")
def delete_layer_type_endpoint(layer_type_id: int, db: Session = Depends(get_db)):
    try:
        deleted = delete_layer_type(db, layer_type_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Schichttyp nicht gefunden.")
    return {"ok": True}


@router.get("/api/roof-areas/{roof_area_id}/layers", response_model=list[RoofLayerOut])
def get_roof_layers(roof_area_id: int, db: Session = Depends(get_db)):
    return list_roof_layers(db, roof_area_id)


@router.put("/api/roof-areas/{roof_area_id}/layers/{layer_type_id}", response_model=RoofLayerOut)
def put_roof_layer(roof_area_id: int, layer_type_id: int, payload: RoofLayerUpsert, db: Session = Depends(get_db)):
    """fields enthält seit 1.2.19 nur die im JSON-Body tatsächlich mitgeschickten Schlüssel
    (exclude_unset) -- ein weggelassenes Feld bleibt in upsert_roof_layer() unverändert, ein
    ausdrücklich gesendetes null leert es. Siehe Docstring dort für den Datenverlust-Fund, den
    das behebt."""
    fields = payload.model_dump(exclude_unset=True)
    try:
        return upsert_roof_layer(db, roof_area_id, layer_type_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Bauteilarten (RoofComponentType, seit 1.2.19) -- ungated, Muster wie roof-layer-types
# oben. "/reorder" ist konkret und deshalb vor "/{component_type_id}" deklariert. ---

@router.get("/api/roof-component-types", response_model=list[RoofComponentTypeOut])
def get_component_types(include_inactive: bool = False, db: Session = Depends(get_db)):
    return list_component_types(db, include_inactive=include_inactive)


@router.post("/api/roof-component-types", response_model=RoofComponentTypeOut)
def post_component_type(payload: RoofComponentTypeCreate, db: Session = Depends(get_db)):
    try:
        return create_component_type(db, payload.key, payload.label, is_area=payload.is_area)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/roof-component-types/reorder", response_model=list[RoofComponentTypeOut])
def put_component_types_reorder(payload: ComponentTypeReorder, db: Session = Depends(get_db)):
    try:
        return reorder_component_types(db, payload.ordered_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/roof-component-types/{component_type_id}", response_model=RoofComponentTypeOut)
def put_component_type(component_type_id: int, payload: RoofComponentTypeUpdate, db: Session = Depends(get_db)):
    result = update_component_type(db, component_type_id, payload.label, is_area=payload.is_area)
    if result is None:
        raise HTTPException(status_code=404, detail="Bauteilart nicht gefunden.")
    return result


@router.post("/api/roof-component-types/{component_type_id}/activate", response_model=RoofComponentTypeOut)
def activate_component_type(component_type_id: int, db: Session = Depends(get_db)):
    result = set_component_type_active(db, component_type_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Bauteilart nicht gefunden.")
    return result


@router.post("/api/roof-component-types/{component_type_id}/deactivate", response_model=RoofComponentTypeOut)
def deactivate_component_type(component_type_id: int, db: Session = Depends(get_db)):
    result = set_component_type_active(db, component_type_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Bauteilart nicht gefunden.")
    return result


@router.delete("/api/roof-component-types/{component_type_id}")
def delete_component_type_endpoint(component_type_id: int, db: Session = Depends(get_db)):
    try:
        deleted = delete_component_type(db, component_type_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Bauteilart nicht gefunden.")
    return {"ok": True}
