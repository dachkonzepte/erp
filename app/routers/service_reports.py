"""Router: service_reports (seit 1.2.1) -- digitale Einsatzberichte, Teil des Moduls
"wartungen" (siehe app/modules.py). Jeder Endpunkt prüft zuerst is_module_enabled() -- 403 bei
deaktiviertem Modul, gleiches Muster wie bei maintenance_contracts.py/tasks.py."""

import base64
import binascii

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..modules import is_module_enabled
from ..schemas import (
    InspectionItemCreate, InspectionItemOut, InspectionItemResultUpdate, InspectionItemsSyncResult,
    RoofAreaOut, ServiceReportCreate, ServiceReportMaterialCreate, ServiceReportMaterialOut,
    ServiceReportMaterialUpdate, ServiceReportOut, ServiceReportPhotoOut, ServiceReportSign, ServiceReportUpdate,
)
from ..service_report_pdf import build_service_report_pdf
from ..service_report_photos import MAX_UPLOAD_BYTES, photo_path
from ..service_reports import (
    add_inspection_item, add_material, add_photo, create_report, delete_inspection_item, delete_material,
    delete_photo, delete_report, get_report_row, list_inspection_items, list_materials_for_invoicing,
    list_materials_for_report, list_photos, list_property_history, list_reports, list_roof_areas_for_order,
    material_to_dict, regenerate_inspection_items, sign_report, sync_inspection_items, update_inspection_item,
    update_material, update_report,
)
from ..models import ServiceReportPhoto

router = APIRouter()

MODULE_KEY = "wartungen"
PHOTO_CONTENT_TYPES = ("image/png", "image/jpeg", "image/webp")


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Wartungen & Reparaturen ist deaktiviert.")


def _employee_for_request(request: Request, requested_employee_id: int | None) -> int | None:
    """Seit 1.3.0: gleiche Sperre wie _time_entry_employee_for_request() in
    app/routers/time_tracking.py, aber ohne dessen 422-Zweig -- created_by_employee_id bleibt an
    allen vier Stellen (ServiceReport, ServiceReportPhoto, ServiceReportMaterial, Finding)
    nullable, anders als TimeEntry.employee_id. Ein Nicht-Admin darf nur die eigene employee_id
    setzen oder keine; ein Admin ist frei. Gilt für JEDEN Aufrufer, auch Schreibtisch-Nutzer --
    ein Mangel ist die Feststellung, aus der ggf. ein Folgeauftrag entsteht, ein Bericht kann
    versehentlich unter fremdem Namen unterschrieben werden, wenn das nicht durchgesetzt wird."""
    user = getattr(request.state, "erp_user", None)
    if user is not None and user.role != "admin":
        if requested_employee_id is not None and requested_employee_id != user.employee_id:
            raise HTTPException(status_code=403, detail="Sie dürfen nur sich selbst als Mitarbeiter angeben.")
        return user.employee_id
    return requested_employee_id


@router.get("/api/orders/{order_id}/roof-areas", response_model=list[RoofAreaOut])
def get_roof_areas_for_order(order_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return list_roof_areas_for_order(db, order_id)


@router.get("/api/orders/{order_id}/service-reports", response_model=list[ServiceReportOut])
def get_service_reports(order_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return list_reports(db, order_id)


@router.get("/api/orders/{order_id}/materials", response_model=list[ServiceReportMaterialOut])
def get_order_materials(order_id: int, db: Session = Depends(get_db)):
    """Für order.html -- ob "Rechnung aus Aufwand" auch ohne gebuchte Zeit sinnvoll ist (rein
    materialbasierter Einsatz), siehe list_materials_for_invoicing() in app/service_reports.py."""
    _require_module_enabled(db)
    return [material_to_dict(m) for m in list_materials_for_invoicing(db, order_id)]


@router.get("/api/orders/{order_id}/property-service-reports", response_model=list[ServiceReportOut])
def get_property_service_report_history(order_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return list_property_history(db, order_id)


@router.post("/api/orders/{order_id}/service-reports", response_model=ServiceReportOut)
def post_service_report(order_id: int, payload: ServiceReportCreate, request: Request, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    employee_id = _employee_for_request(request, payload.created_by_employee_id)
    try:
        return create_report(
            db, order_id, report_type=payload.report_type, description=payload.description,
            created_by_employee_id=employee_id, performed_at=payload.performed_at,
            roof_area_ids=payload.roof_area_ids, inspection_template_id=payload.inspection_template_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/service-reports/{report_id}", response_model=ServiceReportOut)
def put_service_report(report_id: int, payload: ServiceReportUpdate, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    try:
        result = update_report(db, report_id, report_type=payload.report_type,
                                description=payload.description, performed_at=payload.performed_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Bericht nicht gefunden.")
    return result


@router.delete("/api/service-reports/{report_id}")
def delete_service_report(report_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    try:
        deleted = delete_report(db, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Bericht nicht gefunden.")
    return {"ok": True}


def _decode_signature_png(raw: str) -> bytes:
    if "," in raw and raw.strip().lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Ungültige Unterschrift (kein gültiges Base64-PNG).") from exc


@router.post("/api/service-reports/{report_id}/sign", response_model=ServiceReportOut)
def post_sign_service_report(report_id: int, payload: ServiceReportSign, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    installer_bytes = _decode_signature_png(payload.installer_signature_png_base64)
    customer_bytes = _decode_signature_png(payload.customer_signature_png_base64)
    try:
        result = sign_report(
            db, report_id,
            installer_signature_png_bytes=installer_bytes, installer_signature_name=payload.installer_signature_name,
            customer_signature_png_bytes=customer_bytes, customer_signature_name=payload.customer_signature_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Bericht nicht gefunden.")
    return result


@router.get("/api/service-reports/{report_id}/pdf")
def get_service_report_pdf(report_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    report = get_report_row(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Bericht nicht gefunden.")
    try:
        pdf = build_service_report_pdf(db, report)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = f"Einsatzbericht_{report.order.order_number}_{report.id}.pdf".replace("/", "-")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


# --- Strukturierte Prüfpunkte (seit 1.2.16) -- eigener Pfad-Präfix "inspection-items" für die
# einzelpunkt-Endpunkte, keine Kollisionsgefahr mit den obigen service-reports-Routen. Die
# beiden Aktionsrouten (regenerate/sync) liegen als vierter Pfadabschnitt unter derselben
# bare POST-Route wie die manuelle Ergänzung, aber mit anderer Segmentzahl -- keine Kollision. ---

@router.get("/api/service-reports/{report_id}/inspection-items", response_model=list[InspectionItemOut])
def get_inspection_items(report_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return list_inspection_items(db, report_id)


@router.post("/api/service-reports/{report_id}/inspection-items", response_model=InspectionItemOut)
def post_inspection_item(report_id: int, payload: InspectionItemCreate, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    try:
        return add_inspection_item(
            db, report_id, payload.text, payload.item_type, group_name=payload.group_name,
            required=payload.required, target_min=payload.target_min, target_max=payload.target_max,
            unit=payload.unit, roof_component_id=payload.roof_component_id, roof_area_id=payload.roof_area_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/service-reports/{report_id}/inspection-items/regenerate", response_model=ServiceReportOut)
def post_regenerate_inspection_items(report_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    try:
        return regenerate_inspection_items(db, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/service-reports/{report_id}/inspection-items/sync", response_model=InspectionItemsSyncResult)
def post_sync_inspection_items(report_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    try:
        return sync_inspection_items(db, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/inspection-items/{item_id}", response_model=InspectionItemOut)
def put_inspection_item(item_id: int, payload: InspectionItemResultUpdate, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    fields = payload.model_dump(exclude_unset=True)
    try:
        result = update_inspection_item(db, item_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Prüfpunkt nicht gefunden.")
    return result


@router.delete("/api/inspection-items/{item_id}")
def delete_inspection_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    try:
        deleted = delete_inspection_item(db, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Prüfpunkt nicht gefunden.")
    return {"ok": True}


# --- Fotos (seit 1.2.17) -- eigener Pfad-Präfix "service-report-photos" für die
# einzelfoto-Endpunkte, keine Kollisionsgefahr mit den obigen service-reports-Routen. ---

@router.get("/api/service-reports/{report_id}/photos", response_model=list[ServiceReportPhotoOut])
def get_service_report_photos(report_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return list_photos(db, report_id)


@router.post("/api/service-reports/{report_id}/photos", response_model=ServiceReportPhotoOut)
async def post_service_report_photo(
    report_id: int, request: Request, file: UploadFile = File(...), inspection_item_id: int | None = Form(None),
    finding_id: int | None = Form(None), kind: str = Form("allgemein"), caption: str | None = Form(None),
    created_by_employee_id: int | None = Form(None), db: Session = Depends(get_db),
):
    _require_module_enabled(db)
    employee_id = _employee_for_request(request, created_by_employee_id)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    if (file.content_type or "").lower() not in PHOTO_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Bitte PNG, JPEG oder WebP verwenden.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 15 MB.")
    try:
        return add_photo(
            db, report_id, data, file.filename, inspection_item_id=inspection_item_id, finding_id=finding_id,
            kind=kind, caption=caption, created_by_employee_id=employee_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/service-report-photos/{photo_id}/file")
def get_service_report_photo_file(photo_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    photo = db.get(ServiceReportPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Foto nicht gefunden.")
    path = photo_path(photo.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Bilddatei nicht gefunden.")
    return FileResponse(path)


@router.delete("/api/service-report-photos/{photo_id}")
def delete_service_report_photo(photo_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    try:
        deleted = delete_photo(db, photo_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Foto nicht gefunden.")
    return {"ok": True}


# --- Verbrauchtes Material (seit 1.2.23) -- eigener Pfad-Präfix "service-report-materials" für
# die Einzelzeilen-Endpunkte, gleiches Muster wie bei den Fotos oben. ---

@router.get("/api/service-reports/{report_id}/materials", response_model=list[ServiceReportMaterialOut])
def get_service_report_materials(report_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    return list_materials_for_report(db, report_id)


@router.post("/api/service-reports/{report_id}/materials", response_model=ServiceReportMaterialOut)
def post_service_report_material(
    report_id: int, payload: ServiceReportMaterialCreate, request: Request, db: Session = Depends(get_db),
):
    _require_module_enabled(db)
    employee_id = _employee_for_request(request, payload.created_by_employee_id)
    try:
        return add_material(
            db, report_id, material_id=payload.material_id, description=payload.description,
            quantity=payload.quantity, unit=payload.unit, roof_area_id=payload.roof_area_id,
            inspection_item_id=payload.inspection_item_id, finding_id=payload.finding_id, notes=payload.notes,
            created_by_employee_id=employee_id, client_uuid=payload.client_uuid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/service-report-materials/{material_id}", response_model=ServiceReportMaterialOut)
def put_service_report_material(material_id: int, payload: ServiceReportMaterialUpdate, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    fields = payload.model_dump(exclude_unset=True)
    try:
        result = update_material(db, material_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")
    return result


@router.delete("/api/service-report-materials/{material_id}")
def delete_service_report_material(material_id: int, db: Session = Depends(get_db)):
    _require_module_enabled(db)
    try:
        deleted = delete_material(db, material_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")
    return {"ok": True}
