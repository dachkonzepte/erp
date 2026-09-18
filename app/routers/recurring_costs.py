"""Router: recurring_costs (seit 1.5.0) -- Betriebskosten-Übersicht, Teil des Moduls
"betriebskosten" (siehe app/modules.py). Jeder Endpunkt prüft zuerst is_module_enabled() --
403 bei deaktiviertem Modul, unabhängig von der Rolle, gleiches Muster wie
operational_assets.py.

Ausnahmslos require_min_role(ROLE_OFFICE_FINANZEN) -- Kalkulationsgrundlagen/
Stundenverrechnungssatz-Herleitung/Mitarbeitervergütung/Betriebskosten-Übersicht sind seit
Etappe 2 des Rechtekonzepts (1.4.8) die Finanzen-Achse: ein buero_auftrag-Konto sieht diesen
gesamten Bereich an KEINER Stelle, kein _any_role_dep wie bei der Betriebsmittelverwaltung
(dort gibt es eine Monteur-Ansicht, hier nicht)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppUser, RecurringCost, RecurringCostDocument
from ..modules import is_module_enabled
from ..permissions import ROLE_OFFICE_FINANZEN, require_min_role
from ..recurring_cost_documents import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_BYTES, document_path, save_document
from ..recurring_costs import (
    MODULE_KEY, check_due_cancellations_and_create_reminders, create_cost, create_cost_document,
    delete_cost, delete_cost_document, get_cost, get_or_create_recurring_cost_settings, list_costs,
    overview_summary, recurring_cost_settings_to_dict, update_cost, update_recurring_cost_settings,
)
from ..schemas import (
    RecurringCostCreate, RecurringCostDocumentOut, RecurringCostOut, RecurringCostOverviewOut,
    RecurringCostSettingsOut, RecurringCostSettingsUpdate, RecurringCostUpdate,
)

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_FINANZEN))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Betriebskosten-Übersicht ist deaktiviert.")


@router.get("/api/recurring-costs/overview", response_model=RecurringCostOverviewOut)
def get_recurring_costs_overview(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Monats-/Jahressumme über beide Kostenquellen, Kündigungsfristen hervorgehoben -- bewusst
    als literaler Pfad VOR /{cost_id} deklariert (Muster GET /api/operational-assets/due)."""
    _require_module_enabled(db)
    return overview_summary(db)


@router.post("/api/recurring-costs/check-due")
def post_recurring_costs_check_due(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """On-Demand-Erinnerung -- vom Frontend beim Aufruf der Betriebskosten-Übersicht ausgelöst,
    kein Hintergrund-Job (Muster POST /api/operational-assets/check-due)."""
    _require_module_enabled(db)
    reminded = check_due_cancellations_and_create_reminders(db)
    return {"reminded_cost_ids": reminded}


@router.get("/api/recurring-costs", response_model=list[RecurringCostOut])
def get_recurring_costs(include_inactive: bool = True, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return list_costs(db, include_inactive=include_inactive)


@router.get("/api/recurring-costs/{cost_id}", response_model=RecurringCostOut)
def get_recurring_cost(cost_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = get_cost(db, cost_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Kostenposten nicht gefunden.")
    return result


@router.post("/api/recurring-costs", response_model=RecurringCostOut)
def post_recurring_cost(payload: RecurringCostCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_cost(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/api/recurring-costs/{cost_id}", response_model=RecurringCostOut)
def put_recurring_cost(cost_id: int, payload: RecurringCostUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = update_cost(db, cost_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Kostenposten nicht gefunden.")
    return result


@router.delete("/api/recurring-costs/{cost_id}")
def delete_recurring_cost(cost_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not delete_cost(db, cost_id):
        raise HTTPException(status_code=404, detail="Kostenposten nicht gefunden.")
    return {"deleted": True}


@router.post("/api/recurring-costs/{cost_id}/documents", response_model=RecurringCostDocumentOut)
async def upload_recurring_cost_document(
    cost_id: int, document_type: str = Form(...), notes: str | None = Form(None),
    file: UploadFile = File(...), db: Session = Depends(get_db), _role: AppUser = _role_dep,
):
    _require_module_enabled(db)
    if not document_type.strip():
        raise HTTPException(status_code=422, detail="Bitte eine Art wählen.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    if (file.content_type or "").lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Bitte PDF, PNG, JPEG oder WebP verwenden.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 10 MB.")
    # Existenz VOR dem Speichern prüfen (Muster create_asset_document()) -- eine Datei für
    # einen nicht existierenden Kostenposten wird nie erst auf die Platte geschrieben.
    if db.get(RecurringCost, cost_id) is None:
        raise HTTPException(status_code=404, detail="Kostenposten nicht gefunden.")
    stored = save_document(file.filename, data)
    return create_cost_document(
        db, cost_id, document_type=document_type, notes=notes, stored_filename=stored, original_filename=file.filename,
    )


@router.get("/api/recurring-cost-documents/{document_id}/file")
def get_recurring_cost_document_file(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    document = db.get(RecurringCostDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(document.stored_filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dokumentdatei nicht gefunden.")
    return FileResponse(path, filename=document.original_filename or path.name)


@router.delete("/api/recurring-cost-documents/{document_id}")
def delete_recurring_cost_document_endpoint(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not delete_cost_document(db, document_id):
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    return {"deleted": True}


@router.get("/api/recurring-cost-settings", response_model=RecurringCostSettingsOut)
def get_recurring_cost_settings_endpoint(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return recurring_cost_settings_to_dict(get_or_create_recurring_cost_settings(db))


@router.put("/api/recurring-cost-settings", response_model=RecurringCostSettingsOut)
def put_recurring_cost_settings_endpoint(payload: RecurringCostSettingsUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return update_recurring_cost_settings(db, payload.reminder_lead_days)
