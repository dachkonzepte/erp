"""Router: checklist_templates (seit 1.8.0) -- Vorlagenverwaltung des Moduls "checklisten"
(siehe docs/archiv/modul-checklisten.md). Jeder Endpunkt prüft zuerst is_module_enabled() --
403 bei deaktiviertem Modul, auch für Admins.

Vorlagen pflegt buero_auftrag aufwärts (Betreibervorgabe). Monteure lesen in 1.8.0 noch gar
nichts hiervon; die veröffentlichte Fassung für das Ausfüllen kommt mit 1.8.1 über einen eigenen,
auf veröffentlichte Fassungen und passende Kontexte beschränkten Endpunkt -- nicht über diese
Verwaltungs-Endpunkte, die auch Entwürfe und Regeln zeigen."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..checklist_purposes import list_purposes
from ..checklist_templates import (
    add_field, add_option, add_rule, copy_template, create_template, delete_field, delete_option, delete_rule,
    delete_template, discard_draft, get_template, get_version, list_templates, publish_draft, reorder_fields,
    set_template_archived, start_draft, sync_system_fields, update_field, update_option, update_rule,
    update_template,
)
from ..database import get_db
from ..models import AppUser
from ..modules import is_module_enabled
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import (
    ChecklistPurposeOut, ChecklistTemplateCopy, ChecklistTemplateCreate, ChecklistTemplateFieldReorder,
    ChecklistTemplateFieldWrite, ChecklistTemplateOptionCreate, ChecklistTemplateOptionUpdate, ChecklistTemplateOut, ChecklistTemplateRuleWrite,
    ChecklistTemplateUpdate, ChecklistTemplateVersionOut,
)

router = APIRouter()

MODULE_KEY = "checklisten"

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Checklisten & Formulare ist deaktiviert.")


def _call(fn, *args, not_found: str = "Nicht gefunden.", **kwargs):
    """ValueError → 400 (fachlich abgelehnt), LookupError/None → 404."""
    try:
        result = fn(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=not_found)
    return result


@router.get("/api/checklist-purposes", response_model=list[ChecklistPurposeOut])
def get_checklist_purposes(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Zwecke mit erlaubten Kontexten und Systemfeldern (seit 1.8.16) -- für die Auswahl im Editor."""
    _require_module_enabled(db)
    return list_purposes()


@router.get("/api/checklist-templates", response_model=list[ChecklistTemplateOut])
def get_checklist_templates(include_archived: bool = False, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return list_templates(db, include_archived=include_archived)


@router.post("/api/checklist-templates", response_model=ChecklistTemplateOut)
def post_checklist_template(payload: ChecklistTemplateCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(create_template, db, label=payload.label, description=payload.description,
                 contexts=payload.contexts, field_readable=payload.field_readable, purpose=payload.purpose)


@router.get("/api/checklist-templates/{template_id}", response_model=ChecklistTemplateOut)
def get_checklist_template(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(get_template, db, template_id, not_found="Vorlage nicht gefunden.")


@router.put("/api/checklist-templates/{template_id}", response_model=ChecklistTemplateOut)
def put_checklist_template(template_id: int, payload: ChecklistTemplateUpdate, db: Session = Depends(get_db),
                           _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(update_template, db, template_id, label=payload.label, description=payload.description,
                 contexts=payload.contexts, field_readable=payload.field_readable, purpose=payload.purpose,
                 not_found="Vorlage nicht gefunden.")


@router.delete("/api/checklist-templates/{template_id}")
def delete_checklist_template(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not _call(delete_template, db, template_id, not_found="Vorlage nicht gefunden."):
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden.")
    return {"ok": True}


@router.post("/api/checklist-templates/{template_id}/archive", response_model=ChecklistTemplateOut)
def archive_checklist_template(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(set_template_archived, db, template_id, True, not_found="Vorlage nicht gefunden.")


@router.post("/api/checklist-templates/{template_id}/unarchive", response_model=ChecklistTemplateOut)
def unarchive_checklist_template(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(set_template_archived, db, template_id, False, not_found="Vorlage nicht gefunden.")


@router.post("/api/checklist-templates/{template_id}/copy", response_model=ChecklistTemplateOut)
def post_copy_checklist_template(template_id: int, payload: ChecklistTemplateCopy, db: Session = Depends(get_db),
                                 _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(copy_template, db, template_id, payload.label)


@router.post("/api/checklist-templates/{template_id}/draft", response_model=ChecklistTemplateOut)
def post_checklist_template_draft(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(start_draft, db, template_id, not_found="Vorlage nicht gefunden.")


@router.delete("/api/checklist-templates/{template_id}/draft", response_model=ChecklistTemplateOut)
def delete_checklist_template_draft(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(discard_draft, db, template_id, not_found="Vorlage nicht gefunden.")


@router.post("/api/checklist-templates/{template_id}/publish", response_model=ChecklistTemplateOut)
def post_checklist_template_publish(template_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(publish_draft, db, template_id, published_by_user_id=getattr(_role, "id", None),
                 not_found="Vorlage nicht gefunden.")


@router.get("/api/checklist-template-versions/{version_id}", response_model=ChecklistTemplateVersionOut)
def get_checklist_template_version(version_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(get_version, db, version_id, not_found="Fassung nicht gefunden.")


@router.post("/api/checklist-template-versions/{version_id}/fields", response_model=ChecklistTemplateVersionOut)
def post_checklist_template_field(version_id: int, payload: ChecklistTemplateFieldWrite, db: Session = Depends(get_db),
                                  _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(add_field, db, version_id, payload.model_dump(exclude_unset=True))


@router.post("/api/checklist-template-versions/{version_id}/system-fields", response_model=ChecklistTemplateVersionOut)
def post_checklist_template_system_fields(version_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """"Systemfelder angleichen" (seit 1.8.16): fehlende Systemfelder des Zwecks im Entwurf
    anlegen, feste Eigenschaften auf die Vorgabe setzen."""
    _require_module_enabled(db)
    return _call(sync_system_fields, db, version_id)


@router.post("/api/checklist-template-versions/{version_id}/fields/reorder", response_model=ChecklistTemplateVersionOut)
def post_checklist_template_field_reorder(version_id: int, payload: ChecklistTemplateFieldReorder,
                                          db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(reorder_fields, db, version_id, payload.field_ids)


@router.put("/api/checklist-template-fields/{field_id}", response_model=ChecklistTemplateVersionOut)
def put_checklist_template_field(field_id: int, payload: ChecklistTemplateFieldWrite, db: Session = Depends(get_db),
                                 _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(update_field, db, field_id, payload.model_dump(exclude_unset=True), not_found="Feld nicht gefunden.")


@router.delete("/api/checklist-template-fields/{field_id}", response_model=ChecklistTemplateVersionOut)
def delete_checklist_template_field(field_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(delete_field, db, field_id, not_found="Feld nicht gefunden.")


@router.post("/api/checklist-template-fields/{field_id}/options", response_model=ChecklistTemplateVersionOut)
def post_checklist_template_option(field_id: int, payload: ChecklistTemplateOptionCreate, db: Session = Depends(get_db),
                                   _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(add_option, db, field_id, payload.label, payload.option_key)


@router.put("/api/checklist-template-field-options/{option_id}", response_model=ChecklistTemplateVersionOut)
def put_checklist_template_option(option_id: int, payload: ChecklistTemplateOptionUpdate, db: Session = Depends(get_db),
                                  _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(update_option, db, option_id, label=payload.label, sort_order=payload.sort_order,
                 not_found="Option nicht gefunden.")


@router.delete("/api/checklist-template-field-options/{option_id}", response_model=ChecklistTemplateVersionOut)
def delete_checklist_template_option(option_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(delete_option, db, option_id, not_found="Option nicht gefunden.")


@router.post("/api/checklist-template-versions/{version_id}/rules", response_model=ChecklistTemplateVersionOut)
def post_checklist_template_rule(version_id: int, payload: ChecklistTemplateRuleWrite, db: Session = Depends(get_db),
                                 _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(add_rule, db, version_id, payload.model_dump(exclude_unset=True))


@router.put("/api/checklist-template-rules/{rule_id}", response_model=ChecklistTemplateVersionOut)
def put_checklist_template_rule(rule_id: int, payload: ChecklistTemplateRuleWrite, db: Session = Depends(get_db),
                                _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(update_rule, db, rule_id, payload.model_dump(exclude_unset=True), not_found="Regel nicht gefunden.")


@router.delete("/api/checklist-template-rules/{rule_id}", response_model=ChecklistTemplateVersionOut)
def delete_checklist_template_rule(rule_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return _call(delete_rule, db, rule_id, not_found="Regel nicht gefunden.")
