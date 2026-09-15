"""Router: inspection_templates (seit 1.2.16) -- Prüfvorlagen für Einsatzberichte, Teil des
Moduls "wartungen" (siehe app/modules.py). Jeder Endpunkt prüft zuerst is_module_enabled() --
403 bei deaktiviertem Modul, gleiches Muster wie bei maintenance_contracts.py/service_reports.py."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..inspection_templates import (
    copy_template, create_template, create_template_item, delete_template_item, get_template,
    list_roof_type_template_defaults, list_templates, set_roof_type_template_default, set_template_archived,
    update_template, update_template_item,
)
from ..models import AppUser
from ..modules import is_module_enabled
from ..permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE, require_role
from ..schemas import (
    InspectionTemplateCopy, InspectionTemplateCreate, InspectionTemplateItemCreate, InspectionTemplateItemOut,
    InspectionTemplateItemUpdate, InspectionTemplateOut, InspectionTemplateUpdate, RoofTypeTemplateDefaultOut,
    RoofTypeTemplateDefaultUpdate,
)

router = APIRouter()

MODULE_KEY = "wartungen"

# Seit "Rechtekonzept", Teil B (siehe CLAUDE.md): Prüfvorlagen sind Stammdatenpflege des Büros
# (Einstellungen → Prüfvorlagen) -- Anlegen/Ändern/Archivieren/Kopieren, die Einzelansicht und
# die Dachtyp-Standardzuordnung bleiben Büro/Admin. Einzige Ausnahme: die Vorlagenliste selbst
# (GET /api/inspection-templates) -- service_reports.html lädt sie für die Vorlagenauswahl beim
# Anlegen eines Berichts vor Ort; sie enthält Bezeichnung/Dachtyp/Prüfpunkttexte, keine Preise,
# Kunden- oder Personendaten.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))
_any_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Wartungen & Reparaturen ist deaktiviert.")


@router.get("/api/inspection-templates", response_model=list[InspectionTemplateOut])
def get_inspection_templates(include_archived: bool = False, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    return list_templates(db, include_archived=include_archived)


@router.post("/api/inspection-templates", response_model=InspectionTemplateOut)
def post_inspection_template(payload: InspectionTemplateCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_template(db, payload.label, roof_type=payload.roof_type, description=payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/inspection-templates/{template_id}", response_model=InspectionTemplateOut)
def get_inspection_template(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = get_template(db, template_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden.")
    return result


@router.put("/api/inspection-templates/{template_id}", response_model=InspectionTemplateOut)
def put_inspection_template(template_id: int, payload: InspectionTemplateUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = update_template(db, template_id, payload.label, payload.roof_type, payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden.")
    return result


@router.post("/api/inspection-templates/{template_id}/archive", response_model=InspectionTemplateOut)
def archive_inspection_template(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = set_template_archived(db, template_id, True)
    if result is None:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden.")
    return result


@router.post("/api/inspection-templates/{template_id}/unarchive", response_model=InspectionTemplateOut)
def unarchive_inspection_template(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = set_template_archived(db, template_id, False)
    if result is None:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden.")
    return result


@router.post("/api/inspection-templates/{template_id}/copy", response_model=InspectionTemplateOut)
def post_copy_inspection_template(template_id: int, payload: InspectionTemplateCopy, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return copy_template(db, template_id, payload.label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/inspection-templates/{template_id}/items", response_model=InspectionTemplateItemOut)
def post_inspection_template_item(template_id: int, payload: InspectionTemplateItemCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_template_item(
            db, template_id, payload.text, payload.item_type, group_name=payload.group_name,
            component_type=payload.component_type, required=payload.required, target_min=payload.target_min,
            target_max=payload.target_max, unit=payload.unit, photo_required=payload.photo_required,
            photo_before_after=payload.photo_before_after, sort_order=payload.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/inspection-template-items/{item_id}", response_model=InspectionTemplateItemOut)
def put_inspection_template_item(item_id: int, payload: InspectionTemplateItemUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = update_template_item(
            db, item_id, payload.text, payload.item_type, payload.group_name, payload.component_type,
            payload.required, payload.target_min, payload.target_max, payload.unit, payload.photo_required,
            payload.photo_before_after, payload.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Prüfpunkt nicht gefunden.")
    return result


@router.delete("/api/inspection-template-items/{item_id}")
def delete_inspection_template_item(item_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not delete_template_item(db, item_id):
        raise HTTPException(status_code=404, detail="Prüfpunkt nicht gefunden.")
    return {"ok": True}


# --- Version 1.2.22: explizite Dachtyp -> Standardvorlage-Zuordnung ---

@router.get("/api/roof-type-template-defaults", response_model=list[RoofTypeTemplateDefaultOut])
def get_roof_type_template_defaults(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return list_roof_type_template_defaults(db)


@router.put("/api/roof-type-template-defaults/{roof_type}", response_model=list[RoofTypeTemplateDefaultOut])
def put_roof_type_template_default(roof_type: str, payload: RoofTypeTemplateDefaultUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        set_roof_type_template_default(db, roof_type, payload.inspection_template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return list_roof_type_template_defaults(db)
