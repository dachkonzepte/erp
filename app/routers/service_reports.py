"""Router: service_reports (seit 1.2.1) -- digitale Einsatzberichte, Teil des Moduls
"wartungen" (siehe app/modules.py). Jeder Endpunkt prüft zuerst is_module_enabled() -- 403 bei
deaktiviertem Modul, gleiches Muster wie bei maintenance_contracts.py/tasks.py.

Seit "Rechtekonzept", Teil B (siehe CLAUDE.md): fast jeder Endpunkt dieser Datei wird vom
Monteur selbst bedient (service_reports.html vor Ort) -- Rollen-Gate für jede Rolle, dazu für
`field` die Objekt-Filterung über require_field_order_access() (app/routers/orders.py, die eine
Übersetzung von app/orders.py::field_may_access_order() in ein 403) für Endpunkte, die einen
ganzen Auftrag betreffen (order_id direkt bekannt).

Seit dem Fund "fremde Berichte lesen und schreiben auf einem gemeinsamen Auftrag" (Sicherheits-
test, siehe CLAUDE.md "Rechtekonzept" -> "Berichts-Eigentümerschaft"): require_field_order_access()
allein reicht für einen EINZELNEN Bericht nicht -- auf einem Mehrpersonen-Auftrag (Team-Besetzung
an der AV) hätte sonst jeder Monteur mit Zugriff auf den Auftrag jeden Bericht darauf lesen,
ändern, löschen und signieren können, unabhängig vom Ersteller. Jeder Endpunkt, der einen
KONKRETEN Bericht (oder dessen Prüfpunkte/Fotos/Material) betrifft, prüft deshalb zusätzlich
über require_field_report_ownership() (app/routers/orders.py), dass der angemeldete Monteur der
Ersteller (created_by_employee_id) dieses Berichts ist -- Büro/Admin bleiben unbeschränkt.
Endpunkte, die nicht direkt über report_id laufen, lösen zuerst item_id/photo_id/material_id
über service_report_id auf (_report_id_for_child()). Die Berichtsliste eines Auftrags
(GET .../service-reports) ist die EINZIGE Ausnahme von der Ersteller-Prüfung: dort sieht ein
Monteur JEDEN Bericht des Auftrags, aber im reduzierten Schema für alles außer dem eigenen
(list_reports_for_field() in app/service_reports.py). Zweite Ausnahme, unverändert seit
1.3.55: GET /api/orders/{order_id}/materials (für order.html, "Rechnung aus Aufwand" -- reine
Büro-Entscheidung) bleibt Büro/Admin."""

import base64
import binascii

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppUser, InspectionItem, ServiceReportAsset, ServiceReportMaterial, ServiceReportPhoto
from ..modules import is_module_enabled
from ..permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE, require_role
from ..schemas import (
    InspectionItemCreate, InspectionItemOut, InspectionItemResultUpdate, InspectionItemsSyncResult,
    PropertyAccessOut, RoofAreaOut, ServiceReportAssetCreate, ServiceReportAssetOut, ServiceReportAssetUpdate,
    ServiceReportCreate, ServiceReportHistoryOut, ServiceReportMaterialCreate, ServiceReportMaterialOut,
    ServiceReportMaterialUpdate, ServiceReportOut, ServiceReportPhotoOut, ServiceReportSign, ServiceReportUpdate,
)
from ..service_report_pdf import build_service_report_pdf
from ..service_report_photos import MAX_UPLOAD_BYTES, photo_path
from ..service_reports import (
    add_asset_usage, add_inspection_item, add_material, add_photo, create_report, delete_asset_usage,
    delete_inspection_item, delete_material, delete_photo, delete_report, get_property_context_for_order,
    get_report_row, list_assets_for_report, list_inspection_items, list_materials_for_invoicing,
    list_materials_for_report, list_photos, list_property_history, list_property_history_for_field, list_reports,
    list_reports_for_field, list_roof_areas_for_order, material_to_dict, regenerate_inspection_items, sign_report,
    sync_inspection_items, update_asset_usage, update_inspection_item, update_material, update_report,
)
from .orders import require_field_order_access, require_field_report_ownership

router = APIRouter()

MODULE_KEY = "wartungen"
PHOTO_CONTENT_TYPES = ("image/png", "image/jpeg", "image/webp")

_any_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD))
_office_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


def _require_module_enabled(db: Session):
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Wartungen & Reparaturen ist deaktiviert.")


def _require_operational_assets_module_enabled(db: Session):
    """Zusätzlich zu _require_module_enabled() (wartungen) für die drei Betriebsmittel-Endpunkte
    unten (seit 1.4.5) -- ein Einsatzbericht kann Betriebsmittel nur dokumentieren, wenn BEIDE
    Module aktiv sind, sonst bliebe die Betriebsmittelverwaltung über diesen Umweg nutzbar,
    obwohl sie deaktiviert ist (dieselbe Regel wie bei jedem anderen modulgegateten Endpunkt,
    siehe CLAUDE.md "Modul-Umschalter")."""
    if not is_module_enabled(db, "betriebsmittel"):
        raise HTTPException(status_code=403, detail="Das Modul Betriebsmittelverwaltung ist deaktiviert.")


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


def _report_id_for_child(db: Session, model, row_id: int, not_found: str) -> int:
    """Auflösung Prüfpunkt/Foto/Material (und in findings.py der Mangel) -> service_report_id,
    für require_field_report_ownership() unten -- die den zugehörigen Auftrag und dessen
    Ersteller bereits selbst aus dem Bericht ableitet, eine Ebene tiefer als früher
    _order_id_for_report_child() (entfernt seit dem Fund "fremde Berichte lesen und schreiben
    auf einem gemeinsamen Auftrag", siehe CLAUDE.md "Rechtekonzept" -> "Berichts-
    Eigentümerschaft"). 404, wenn es die Zeile nicht gibt -- dieselbe Antwort, die der jeweilige
    Endpunkt ohnehin gegeben hätte."""
    row = db.get(model, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail=not_found)
    return row.service_report_id


@router.get("/api/orders/{order_id}/roof-areas", response_model=list[RoofAreaOut])
def get_roof_areas_for_order(order_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_order_access(db, _role, order_id)
    return list_roof_areas_for_order(db, order_id)


@router.get("/api/orders/{order_id}/property", response_model=PropertyAccessOut | None)
def get_property_for_order(order_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Seit "Rechtekonzept" (siehe CLAUDE.md): der Weg, über den der Einsatzbericht Objektname/
    Anschrift/Zugang/Ansprechpartner vor Ort zeigt -- bewusst NICHT über /api/properties/{id}
    (Kundenkontext, für einen Monteur gesperrt), sondern über den bereits erreichbaren
    Auftrag. Kein is_module_enabled()-Gate wie bei den übrigen Endpunkten dieser Datei -- ein
    Objekt ist Kern-Stammdatum, nicht Teil des Moduls "wartungen". Liefert seit 1.3.53
    PropertyAccessOut statt PropertyOut -- die volle Property (inkl. `notes`/`customer_id`) hätte
    genau den Kundenkontext wieder mitgeliefert, den dieser Endpunkt laut eigener Begründung
    NICHT zeigen soll (echter Befund, siehe CLAUDE.md "Rechtekonzept")."""
    require_field_order_access(db, _role, order_id)
    prop = get_property_context_for_order(db, order_id)
    return PropertyAccessOut.model_validate(prop) if prop is not None else None


@router.get("/api/orders/{order_id}/service-reports")
def get_service_reports(order_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Fund "fremde Berichte lesen und schreiben auf einem gemeinsamen Auftrag" (siehe CLAUDE.md
    "Rechtekonzept" -> "Berichts-Eigentümerschaft"): Büro/Admin bekommen wie bisher die volle
    Liste. Für `field` gilt jetzt PRO BERICHT, nicht mehr pro Auftrag: der eigene Bericht bleibt
    voll (zum Bearbeiten), jeder Bericht eines Kollegen kommt im reduzierten Schema der
    Wartungshistorie (list_reports_for_field() in app/service_reports.py). Bewusst OHNE
    response_model -- die beiden Schemata pro Zeile werden hier explizit einzeln validiert
    (siehe list_reports_for_field()s Docstring, warum ein response_model=list[A] | list[B]
    dafür nicht verlässlich genug wäre)."""
    _require_module_enabled(db)
    require_field_order_access(db, _role, order_id)
    if _role.role != ROLE_FIELD:
        return list_reports(db, order_id)
    return [
        (ServiceReportOut if is_own else ServiceReportHistoryOut).model_validate(row).model_dump(mode="json")
        for row, is_own in list_reports_for_field(db, order_id, _role.employee_id)
    ]


@router.get("/api/orders/{order_id}/materials", response_model=list[ServiceReportMaterialOut])
def get_order_materials(order_id: int, db: Session = Depends(get_db), _role: AppUser = _office_role_dep):
    """Für order.html -- ob "Rechnung aus Aufwand" auch ohne gebuchte Zeit sinnvoll ist (rein
    materialbasierter Einsatz), siehe list_materials_for_invoicing() in app/service_reports.py.
    Büro/Admin: eine Rechnungsentscheidung, kein Vor-Ort-Endpunkt (der Monteur liest sein
    Material je Bericht über GET /api/service-reports/{report_id}/materials)."""
    _require_module_enabled(db)
    return [material_to_dict(m) for m in list_materials_for_invoicing(db, order_id)]


@router.get("/api/orders/{order_id}/property-service-reports", response_model=list[ServiceReportOut] | list[ServiceReportHistoryOut])
def get_property_service_report_history(order_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Wartungshistorie desselben Objekts (seit 1.2.4) -- ein Monteur sieht hier bewusst auch
    frühere, unterschriebene Berichte ANDERER Aufträge, an denen er nicht beteiligt war (die
    Arbeit vor Ort braucht das). Die Zuordnung wird nur für den AKTUELLEN Auftrag geprüft.
    Für `field` seit 1.3.56 ein reduziertes Modell (ServiceReportHistoryOut: Datum, Berichtstyp,
    Monteur, Prüfergebnisse, Mängel mit Status -- Betreibervorgabe), Büro/Admin bekommen
    unverändert das volle ServiceReportOut; siehe tests/test_v260_role_audit.py."""
    _require_module_enabled(db)
    require_field_order_access(db, _role, order_id)
    if _role.role == ROLE_FIELD:
        return [ServiceReportHistoryOut.model_validate(r) for r in list_property_history_for_field(db, order_id)]
    return list_property_history(db, order_id)


@router.post("/api/orders/{order_id}/service-reports", response_model=ServiceReportOut)
def post_service_report(order_id: int, payload: ServiceReportCreate, request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_order_access(db, _role, order_id)
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
def put_service_report(report_id: int, payload: ServiceReportUpdate, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    try:
        result = update_report(db, report_id, report_type=payload.report_type,
                                description=payload.description, performed_at=payload.performed_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Bericht nicht gefunden.")
    return result


@router.delete("/api/service-reports/{report_id}")
def delete_service_report(report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
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
def post_sign_service_report(report_id: int, payload: ServiceReportSign, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
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
def get_service_report_pdf(report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
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
def get_inspection_items(report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    return list_inspection_items(db, report_id)


@router.post("/api/service-reports/{report_id}/inspection-items", response_model=InspectionItemOut)
def post_inspection_item(report_id: int, payload: InspectionItemCreate, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    try:
        return add_inspection_item(
            db, report_id, payload.text, payload.item_type, group_name=payload.group_name,
            required=payload.required, target_min=payload.target_min, target_max=payload.target_max,
            unit=payload.unit, roof_component_id=payload.roof_component_id, roof_area_id=payload.roof_area_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/service-reports/{report_id}/inspection-items/regenerate", response_model=ServiceReportOut)
def post_regenerate_inspection_items(report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    try:
        return regenerate_inspection_items(db, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/service-reports/{report_id}/inspection-items/sync", response_model=InspectionItemsSyncResult)
def post_sync_inspection_items(report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    try:
        return sync_inspection_items(db, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/inspection-items/{item_id}", response_model=InspectionItemOut)
def put_inspection_item(item_id: int, payload: InspectionItemResultUpdate, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, _report_id_for_child(db, InspectionItem, item_id, "Prüfpunkt nicht gefunden."))
    fields = payload.model_dump(exclude_unset=True)
    try:
        result = update_inspection_item(db, item_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Prüfpunkt nicht gefunden.")
    return result


@router.delete("/api/inspection-items/{item_id}")
def delete_inspection_item_endpoint(item_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, _report_id_for_child(db, InspectionItem, item_id, "Prüfpunkt nicht gefunden."))
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
def get_service_report_photos(report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    return list_photos(db, report_id)


@router.post("/api/service-reports/{report_id}/photos", response_model=ServiceReportPhotoOut)
async def post_service_report_photo(
    report_id: int, request: Request, file: UploadFile = File(...), inspection_item_id: int | None = Form(None),
    finding_id: int | None = Form(None), kind: str = Form("allgemein"), caption: str | None = Form(None),
    created_by_employee_id: int | None = Form(None), db: Session = Depends(get_db), _role: AppUser = _any_role_dep,
):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
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
def get_service_report_photo_file(photo_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    photo = db.get(ServiceReportPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Foto nicht gefunden.")
    require_field_report_ownership(db, _role, photo.service_report_id)
    path = photo_path(photo.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Bilddatei nicht gefunden.")
    return FileResponse(path)


@router.delete("/api/service-report-photos/{photo_id}")
def delete_service_report_photo(photo_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, _report_id_for_child(db, ServiceReportPhoto, photo_id, "Foto nicht gefunden."))
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
def get_service_report_materials(report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    return list_materials_for_report(db, report_id)


@router.post("/api/service-reports/{report_id}/materials", response_model=ServiceReportMaterialOut)
def post_service_report_material(
    report_id: int, payload: ServiceReportMaterialCreate, request: Request, db: Session = Depends(get_db),
    _role: AppUser = _any_role_dep,
):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
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
def put_service_report_material(material_id: int, payload: ServiceReportMaterialUpdate, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, _report_id_for_child(db, ServiceReportMaterial, material_id, "Material nicht gefunden."))
    fields = payload.model_dump(exclude_unset=True)
    try:
        result = update_material(db, material_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")
    return result


@router.delete("/api/service-report-materials/{material_id}")
def delete_service_report_material(material_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    require_field_report_ownership(db, _role, _report_id_for_child(db, ServiceReportMaterial, material_id, "Material nicht gefunden."))
    try:
        deleted = delete_material(db, material_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Material nicht gefunden.")
    return {"ok": True}


# --- Eingesetzte Betriebsmittel (seit 1.4.5, Betriebsmittelverwaltung Stufe 3) -- eigener
# Pfad-Präfix "service-report-assets" für die Einzelzeilen-Endpunkte, gleiches Muster wie bei
# Material oben. Jeder Endpunkt prüft ZUSÄTZLICH zu _require_module_enabled() (wartungen) auch
# _require_operational_assets_module_enabled() (betriebsmittel) -- siehe dort. ---

@router.get("/api/service-reports/{report_id}/assets", response_model=list[ServiceReportAssetOut])
def get_service_report_assets(report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    _require_operational_assets_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    return list_assets_for_report(db, report_id)


@router.post("/api/service-reports/{report_id}/assets", response_model=ServiceReportAssetOut)
def post_service_report_asset(
    report_id: int, payload: ServiceReportAssetCreate, request: Request, db: Session = Depends(get_db),
    _role: AppUser = _any_role_dep,
):
    _require_module_enabled(db)
    _require_operational_assets_module_enabled(db)
    require_field_report_ownership(db, _role, report_id)
    employee_id = _employee_for_request(request, payload.created_by_employee_id)
    try:
        return add_asset_usage(
            db, report_id, asset_id=payload.asset_id, notes=payload.notes,
            created_by_employee_id=employee_id, client_uuid=payload.client_uuid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/service-report-assets/{asset_row_id}", response_model=ServiceReportAssetOut)
def put_service_report_asset(asset_row_id: int, payload: ServiceReportAssetUpdate, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    _require_operational_assets_module_enabled(db)
    require_field_report_ownership(db, _role, _report_id_for_child(db, ServiceReportAsset, asset_row_id, "Betriebsmittel-Eintrag nicht gefunden."))
    fields = payload.model_dump(exclude_unset=True)
    result = update_asset_usage(db, asset_row_id, fields)
    if result is None:
        raise HTTPException(status_code=404, detail="Betriebsmittel-Eintrag nicht gefunden.")
    return result


@router.delete("/api/service-report-assets/{asset_row_id}")
def delete_service_report_asset(asset_row_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    _require_operational_assets_module_enabled(db)
    require_field_report_ownership(db, _role, _report_id_for_child(db, ServiceReportAsset, asset_row_id, "Betriebsmittel-Eintrag nicht gefunden."))
    if not delete_asset_usage(db, asset_row_id):
        raise HTTPException(status_code=404, detail="Betriebsmittel-Eintrag nicht gefunden.")
    return {"ok": True}
