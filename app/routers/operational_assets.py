"""Router: operational_assets (seit 1.4.0) -- Betriebsmittelverwaltung, Teil des Moduls
"betriebsmittel" (siehe app/modules.py). Jeder Endpunkt prüft zuerst is_module_enabled() --
403 bei deaktiviertem Modul, unabhängig von der Rolle, gleiches Muster wie
maintenance_contracts.py.

Seit Stufe 2 (siehe CLAUDE.md "Betriebsmittelverwaltung" -> Stufe 2) EINE Ausnahme:
GET /api/operational-assets/{asset_id} ist zusätzlich für `field` erreichbar (der QR-Code auf
dem Etikett führt jeden -- Büro wie Monteur -- auf /betriebsmittel/{id}) -- aber liefert dann
NIE mehr als OperationalAssetFieldOut, unabhängig davon, über welchen Weg (QR-Code oder die
volle Büro-URL) aufgerufen wurde: die Rollenprüfung sitzt serverseitig im Router, nicht am Pfad.
Jeder andere Endpunkt dieser Datei bleibt Büro-/Admin-only wie bisher -- ausdrücklich
eingeschlossen die drei Dokumentenablage-Endpunkte (seit 1.4.2, Punkt 4): eine
Betriebsmittel-Rechnung ist auch über eine geratene document_id nie für `field` erreichbar,
require_role() lehnt vor jedem Handler ab."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppUser
from ..modules import is_module_enabled
from ..operational_asset_documents import (
    ALLOWED_CONTENT_TYPES, MAX_UPLOAD_BYTES, document_path, replace_document, save_document,
)
from ..operational_assets import (
    MODULE_KEY, asset_qr_target_url, check_due_asset_inspections_and_create_reminders, create_asset,
    create_asset_document, create_inspection, delete_asset, delete_asset_document, delete_inspection, get_asset,
    get_asset_field, get_or_create_operational_asset_settings, list_assets, list_due_assets,
    operational_asset_settings_to_dict, remove_inspection_document, set_inspection_document, update_asset,
    update_inspection, update_operational_asset_settings,
)
from ..models import OperationalAsset, OperationalAssetDocument, OperationalAssetInspection
from ..permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE, require_role
from ..qr_codes import qr_code_png_bytes
from ..schemas import (
    OperationalAssetCreate, OperationalAssetDocumentOut, OperationalAssetFieldOut, OperationalAssetInspectionCreate,
    OperationalAssetInspectionOut, OperationalAssetInspectionUpdate, OperationalAssetListOut, OperationalAssetOut,
    OperationalAssetSettingsOut, OperationalAssetSettingsUpdate, OperationalAssetUpdate,
)
from ..settings import get_or_create_general_settings

router = APIRouter()

# Betriebsmittelverwaltung ist Büro-/Admin-Bereich, wie Fuhrpark & Maschinen (resource_planning.py)
# -- kein Endpunkt dieser Datei außer den beiden unten (Einzelabruf, QR-Code) wird von einer
# Monteur-Vorlage aufgerufen.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))
_any_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD))


def _resolve_public_base_url(request: Request, db: Session) -> str:
    """Domain für den QR-Code -- bevorzugt GeneralSettings.public_base_url (Einstellungen ->
    Unternehmensstammdaten), falls hinterlegt, sonst die tatsächliche Anfrage-Adresse
    (request.base_url). NIE hartkodiert -- sonst zeigten alle Codes auf localhost/127.0.0.1,
    sobald die App nicht lokal aufgerufen wird."""
    general = get_or_create_general_settings(db)
    configured = (general.public_base_url or "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Betriebsmittelverwaltung ist deaktiviert.")


@router.get("/api/operational-assets/due", response_model=list[OperationalAssetListOut])
def get_due_operational_assets(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Für die Übersicht (master_data.html) und das Dashboard-Widget -- bewusst als literaler
    Pfad VOR /{asset_id} deklariert (Muster GET /api/maintenance-contracts/due-items)."""
    _require_module_enabled(db)
    return list_due_assets(db)


@router.post("/api/operational-assets/check-due")
def post_operational_assets_check_due(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """On-Demand-Erinnerung (Punkt 2) -- vom Frontend beim Aufruf von master_data.html#assets
    ausgelöst, kein Hintergrund-Job (Muster POST /api/maintenance-contracts/check-due). Bewusst
    als literaler Pfad VOR /{asset_id} deklariert, wie /due oben."""
    _require_module_enabled(db)
    reminded = check_due_asset_inspections_and_create_reminders(db)
    return {"reminded_inspection_ids": reminded}


@router.get("/api/operational-assets", response_model=list[OperationalAssetListOut])
def get_operational_assets(include_inactive: bool = True, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return list_assets(db, include_inactive=include_inactive)


@router.get("/api/operational-assets/{asset_id}", response_model=OperationalAssetOut | OperationalAssetFieldOut)
def get_operational_asset(asset_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Für `field` (seit Stufe 2, siehe Moduldocstring): liefert ausschließlich
    OperationalAssetFieldOut, egal ob über den QR-Code-Etikett-Weg oder eine von Hand
    eingetippte Büro-URL aufgerufen -- die Antwort ist bereits als Pydantic-Modell validiert
    (Muster GET /api/orders/{order_id}), damit die Union-Response-Deklaration nie versehentlich
    das jeweils andere Schema für die Serialisierung wählt."""
    _require_module_enabled(db)
    if _role.role == ROLE_FIELD:
        result = get_asset_field(db, asset_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Betriebsmittel nicht gefunden.")
        return OperationalAssetFieldOut.model_validate(result)
    result = get_asset(db, asset_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Betriebsmittel nicht gefunden.")
    return OperationalAssetOut.model_validate(result)


@router.get("/api/operational-assets/{asset_id}/qr-code.png")
def get_operational_asset_qr_code(asset_id: int, request: Request, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Büro-/Admin-only -- das Drucken eines Etiketts ist ein Büro-Vorgang, das SCANNEN des
    fertigen Etiketts (GET .../{asset_id} oben) ist dagegen für jeden erreichbar."""
    _require_module_enabled(db)
    if get_asset(db, asset_id) is None:
        raise HTTPException(status_code=404, detail="Betriebsmittel nicht gefunden.")
    target_url = asset_qr_target_url(_resolve_public_base_url(request, db), asset_id)
    png = qr_code_png_bytes(target_url)
    return Response(content=png, media_type="image/png")


@router.post("/api/operational-assets", response_model=OperationalAssetOut)
def post_operational_asset(payload: OperationalAssetCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        return create_asset(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/api/operational-assets/{asset_id}", response_model=OperationalAssetOut)
def put_operational_asset(asset_id: int, payload: OperationalAssetUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    try:
        result = update_asset(db, asset_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Betriebsmittel nicht gefunden.")
    return result


@router.delete("/api/operational-assets/{asset_id}")
def delete_operational_asset(asset_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not delete_asset(db, asset_id):
        raise HTTPException(status_code=404, detail="Betriebsmittel nicht gefunden.")
    return {"deleted": True}


@router.post("/api/operational-assets/{asset_id}/inspections", response_model=OperationalAssetInspectionOut)
def post_operational_asset_inspection(asset_id: int, payload: OperationalAssetInspectionCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = create_inspection(db, asset_id, payload.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail="Betriebsmittel nicht gefunden.")
    return result


@router.put("/api/operational-asset-inspections/{inspection_id}", response_model=OperationalAssetInspectionOut)
def put_operational_asset_inspection(inspection_id: int, payload: OperationalAssetInspectionUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = update_inspection(db, inspection_id, payload.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail="Prüffrist nicht gefunden.")
    return result


@router.delete("/api/operational-asset-inspections/{inspection_id}")
def delete_operational_asset_inspection(inspection_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not delete_inspection(db, inspection_id):
        raise HTTPException(status_code=404, detail="Prüffrist nicht gefunden.")
    return {"deleted": True}


@router.post("/api/operational-asset-inspections/{inspection_id}/document", response_model=OperationalAssetInspectionOut)
async def upload_operational_asset_inspection_document(inspection_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    if (file.content_type or "").lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Bitte PDF, PNG, JPEG oder WebP verwenden.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 10 MB.")
    inspection = db.get(OperationalAssetInspection, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Prüffrist nicht gefunden.")
    stored = replace_document(inspection.document_filename, file.filename, data)
    return set_inspection_document(db, inspection_id, stored, file.filename)


@router.get("/api/operational-asset-inspections/{inspection_id}/document")
def get_operational_asset_inspection_document(inspection_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    inspection = db.get(OperationalAssetInspection, inspection_id)
    if inspection is None or not inspection.document_filename:
        raise HTTPException(status_code=404, detail="Kein Dokument hinterlegt.")
    path = document_path(inspection.document_filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dokumentdatei nicht gefunden.")
    return FileResponse(path, filename=inspection.document_original_name or path.name)


@router.delete("/api/operational-asset-inspections/{inspection_id}/document", response_model=OperationalAssetInspectionOut)
def delete_operational_asset_inspection_document(inspection_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    result = remove_inspection_document(db, inspection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Prüffrist nicht gefunden.")
    return result


# Betriebsmittel-Dokumentenablage (seit 1.4.2, Punkt 4) -- Anschaffungsrechnung, Leasingvertrag
# u. Ä. Ausnahmslos Büro-/Admin-only (_role_dep, NIE _any_role_dep): ein Monteur bekommt hier
# unabhängig von jeder geratenen document_id ein 403, bevor der Handler überhaupt läuft --
# require_role() schließt ROLE_FIELD aus diesen drei Endpunkten strukturell aus.
@router.post("/api/operational-assets/{asset_id}/documents", response_model=OperationalAssetDocumentOut)
async def upload_operational_asset_document(
    asset_id: int, document_type: str = Form(...), notes: str | None = Form(None),
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
    # Existenz VOR dem Speichern prüfen (siehe create_asset_document()-Docstring) -- eine Datei
    # für ein nicht existierendes Betriebsmittel wird nie erst auf die Platte geschrieben.
    if db.get(OperationalAsset, asset_id) is None:
        raise HTTPException(status_code=404, detail="Betriebsmittel nicht gefunden.")
    stored = save_document(file.filename, data)
    result = create_asset_document(
        db, asset_id, document_type=document_type, notes=notes, stored_filename=stored, original_filename=file.filename,
    )
    return result


@router.get("/api/operational-asset-documents/{document_id}/file")
def get_operational_asset_document_file(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    document = db.get(OperationalAssetDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(document.stored_filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dokumentdatei nicht gefunden.")
    return FileResponse(path, filename=document.original_filename or path.name)


@router.delete("/api/operational-asset-documents/{document_id}")
def delete_operational_asset_document_endpoint(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    if not delete_asset_document(db, document_id):
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    return {"deleted": True}


@router.get("/api/operational-asset-settings", response_model=OperationalAssetSettingsOut)
def get_operational_asset_settings_endpoint(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return operational_asset_settings_to_dict(get_or_create_operational_asset_settings(db))


@router.put("/api/operational-asset-settings", response_model=OperationalAssetSettingsOut)
def put_operational_asset_settings_endpoint(payload: OperationalAssetSettingsUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _require_module_enabled(db)
    return update_operational_asset_settings(db, payload.reminder_lead_days)
