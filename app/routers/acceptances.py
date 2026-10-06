"""Router: Abnahme und Gewährleistung (seit 1.8.46, Stufe 2c-1, docs/archiv/abnahme-und-gewaehrleistung.md).

- PUT /api/orders/{order_id}/warranty: Leistungsart und Gewährleistungsdauer festlegen (Vorschlag übernehmen oder
  abweichend mit Begründung; nach einer Abnahme jede Änderung mit Begründung); GET /api/orders/{order_id}/warranty-preview
  (seit 1.8.47): welche Gewährleistungsenden sich verschieben würden; GET /api/orders/{order_id}/warranty-changes: Historie.
- GET /api/orders/{order_id}/acceptances: alle Abnahmen des Auftrags samt verworfener, mit Prüfung von Inhalt und
  Belegen und dem abgeleiteten Gewährleistungsende.
- GET /api/orders/{order_id}/acceptance-options: Auswahl zum Erfassen (Dachflächen des Objekts, Beteiligte).
- POST /api/orders/{order_id}/acceptances: erfassen (multipart: "data" als JSON, "files" als Belege).
- POST /api/order-acceptances/{acceptance_id}/discard: verwerfen mit Begründung.
- GET /api/order-acceptances/{acceptance_id}/files/{file_id}: Beleg, nur mit stimmender Prüfsumme.
- GET /api/properties/{property_id}/acceptance-warranties, GET /api/roof-areas/{roof_area_id}/acceptance-warranties:
  Gewährleistung aus Abnahmen für Objekt- und Dachflächenseite.
- Seit 1.8.63 (Abnahme aus dem Abnahmeprotokoll): GET /api/orders/{order_id}/pending-protocol-acceptances -- Protokolle mit
  gültiger Unterschrift des Auftraggebers ohne Abnahme, mit Grund; POST /api/checklists/{checklist_id}/acceptance-from-protocol
  -- die Folge nachholen (409 mit Grund, wenn sie weiter aussteht). Modul "checklisten" muss aktiv sein.

Alles ab buero_auftrag; Monteure sehen nichts davon (403). Kein Ändern und kein Löschen einer Abnahme.
"""

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload

from ..acceptances import (
    MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES, AcceptanceConflict, AcceptanceFileError, acceptance_options,
    acceptance_to_dict, create_acceptance, discard_acceptance, list_acceptances, property_acceptance_warranties,
    read_acceptance_file, roof_area_acceptance_warranties,
)
from ..acceptance_protocol import (
    acceptance_for_signature, customer_signature, pending_protocol_acceptances, protocol_acceptance_problem,
)
from ..checklist_follow_ups import run_checklist_follow_ups
from ..checklist_purposes import ACCEPTANCE_PURPOSE
from ..checklists import get_checklist_row
from ..database import get_db
from ..email_dispatch import actor_of
from ..models import AppUser, Order, OrderAcceptance, OrderAcceptanceFile, Property, RoofArea
from ..modules import is_module_enabled
from ..orders import load_order, order_to_dict
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import OrderAcceptanceCreate, OrderAcceptanceDiscard, OrderOut, OrderWarrantyUpdate
from ..warranty import WarrantyLockedError, list_warranty_changes, set_order_warranty, warranty_change_preview

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Abnahme und Gewährleistung sind nur für Büro und "
                                                                  "Administratoren verfügbar."))


def _order_or_404(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    return order


def _acceptance_or_404(db: Session, acceptance_id: int) -> OrderAcceptance:
    acceptance = db.get(OrderAcceptance, acceptance_id, options=[
        selectinload(OrderAcceptance.roof_areas), selectinload(OrderAcceptance.files)])
    if acceptance is None:
        raise HTTPException(status_code=404, detail="Abnahme nicht gefunden.")
    return acceptance


@router.put("/api/orders/{order_id}/warranty", response_model=OrderOut)
def put_order_warranty(order_id: int, payload: OrderWarrantyUpdate, db: Session = Depends(get_db),
                       user: AppUser = _role_dep):
    order = _order_or_404(db, order_id)
    _user_id, user_name = actor_of(user)
    try:
        set_order_warranty(db, order, work_kind=payload.work_kind, warranty_months=payload.warranty_months,
                           warranty_days=payload.warranty_days, reason=payload.reason, actor_name=user_name)
    except WarrantyLockedError as exc:  # seit 1.8.50: der festgeschriebene Vertrag nennt die Dauer
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OrderOut.model_validate(order_to_dict(load_order(db, order_id), db))


@router.get("/api/orders/{order_id}/warranty-preview")
def get_order_warranty_preview(order_id: int, work_kind: str, warranty_months: int, warranty_days: int,
                               db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Seit 1.8.47: was eine Festlegung bewirken würde -- Begründung nötig?, welche Gewährleistungsenden sich
    verschieben. Liest nur; die Auftragsseite zeigt es vor dem Speichern."""
    order = _order_or_404(db, order_id)
    try:
        return warranty_change_preview(db, order, work_kind=work_kind, warranty_months=warranty_months,
                                       warranty_days=warranty_days)
    except WarrantyLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/orders/{order_id}/warranty-changes")
def get_order_warranty_changes(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _order_or_404(db, order_id)
    return list_warranty_changes(db, order_id)


@router.get("/api/orders/{order_id}/acceptances")
def get_order_acceptances(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return list_acceptances(db, _order_or_404(db, order_id))


@router.get("/api/orders/{order_id}/acceptance-options")
def get_order_acceptance_options(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return acceptance_options(db, _order_or_404(db, order_id))


@router.post("/api/orders/{order_id}/acceptances")
def post_order_acceptance(
    order_id: int, data: str = Form(...), files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db), user: AppUser = _role_dep,
):
    """`data`: OrderAcceptanceCreate als JSON; `files`: die Nachweise (PDF oder Foto). Größen werden beim Lesen
    begrenzt (je Datei und zusammen), damit kein übergroßer Upload ganz in den Speicher kommt."""
    order = _order_or_404(db, order_id)
    try:
        payload = OrderAcceptanceCreate.model_validate_json(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json(include_url=False))) from exc
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Höchstens {MAX_FILES} Belege je Abnahme.")
    uploads, total = [], 0
    for upload in files:
        content = upload.file.read(min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total) + 1)
        total += len(content)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=400, detail=f"Die Belege sind zusammen größer als "
                                                        f"{MAX_TOTAL_BYTES // 1_000_000} MB.")
        uploads.append((upload.filename, content))
    user_id, user_name = actor_of(user)
    try:
        acceptance = create_acceptance(db, order, payload.model_dump(), uploads, user_id=user_id, user_name=user_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return acceptance_to_dict(_acceptance_or_404(db, acceptance.id), order)


@router.post("/api/order-acceptances/{acceptance_id}/discard")
def post_discard_order_acceptance(acceptance_id: int, payload: OrderAcceptanceDiscard,
                                  db: Session = Depends(get_db), user: AppUser = _role_dep):
    acceptance = _acceptance_or_404(db, acceptance_id)
    user_id, user_name = actor_of(user)
    try:
        discard_acceptance(db, acceptance, reason=payload.reason, user_id=user_id, user_name=user_name)
    except AcceptanceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return acceptance_to_dict(_acceptance_or_404(db, acceptance_id), db.get(Order, acceptance.order_id))


@router.get("/api/order-acceptances/{acceptance_id}/files/{file_id}")
def get_order_acceptance_file(acceptance_id: int, file_id: int, db: Session = Depends(get_db),
                              _role: AppUser = _role_dep):
    """Der Beleg genau so wie hochgeladen -- nur mit stimmender Prüfsumme (sonst 409, fehlt 410); nosniff."""
    row = db.get(OrderAcceptanceFile, file_id)
    if row is None or row.acceptance_id != acceptance_id:
        raise HTTPException(status_code=404, detail="Beleg nicht gefunden.")
    try:
        content = read_acceptance_file(row)
    except AcceptanceFileError as e:
        raise HTTPException(status_code=410 if e.status == "fehlt" else 409, detail=str(e)) from e
    suffix = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[row.content_type]
    name = "Vollmacht" if row.kind == "vollmacht" else "Abnahme-Beleg"
    return Response(content=content, media_type=row.content_type, headers={
        "Content-Disposition": f'inline; filename="{name}-{row.acceptance_id}-{row.id}.{suffix}"',
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/api/orders/{order_id}/pending-protocol-acceptances")
def get_pending_protocol_acceptances(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Seit 1.8.63: ausstehende Abnahmen aus Abnahmeprotokollen dieses Auftrags (Hinweis mit "Nachholen") -- liest nur.
    Ohne Modul "checklisten" gibt es keine Protokolle."""
    order = _order_or_404(db, order_id)
    if not is_module_enabled(db, "checklisten"):
        return []
    return pending_protocol_acceptances(db, order)


@router.post("/api/checklists/{checklist_id}/acceptance-from-protocol")
def post_acceptance_from_protocol(checklist_id: int, db: Session = Depends(get_db), user: AppUser = _role_dep):
    """Seit 1.8.63: die Folge "Abnahme am Auftrag anlegen" nachholen -- über die Folgen der Checkliste (idempotent, je
    Unterschrift höchstens eine Abnahme). Steht sie danach weiter aus, 409 mit dem Grund."""
    if not is_module_enabled(db, "checklisten"):
        raise HTTPException(status_code=403, detail="Das Modul Checklisten & Formulare ist deaktiviert.")
    checklist = get_checklist_row(db, checklist_id)
    if checklist is None or checklist.template_version.purpose != ACCEPTANCE_PURPOSE:
        raise HTTPException(status_code=404, detail="Abnahmeprotokoll nicht gefunden.")
    run_checklist_follow_ups(db, checklist_id, actor=actor_of(user))
    db.expire_all()
    checklist = get_checklist_row(db, checklist_id)
    signature = customer_signature(checklist)
    if signature is None:
        raise HTTPException(status_code=409, detail="Die Unterschrift des Auftraggebers fehlt oder ist verworfen – keine "
                                                    "Abnahme aus diesem Protokoll.")
    acceptance = acceptance_for_signature(db, signature.id)
    if acceptance is None:
        problem = protocol_acceptance_problem(db, checklist, signature)
        raise HTTPException(status_code=409, detail=problem or "Die Abnahme wurde nicht angelegt – bitte später erneut "
                                                               "versuchen.")
    return acceptance_to_dict(_acceptance_or_404(db, acceptance.id), db.get(Order, acceptance.order_id))


@router.get("/api/properties/{property_id}/acceptance-warranties")
def get_property_acceptance_warranties(property_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    if db.get(Property, property_id) is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    return property_acceptance_warranties(db, property_id)


@router.get("/api/roof-areas/{roof_area_id}/acceptance-warranties")
def get_roof_area_acceptance_warranties(roof_area_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    roof_area = db.get(RoofArea, roof_area_id)
    if roof_area is None:
        raise HTTPException(status_code=404, detail="Dachfläche nicht gefunden.")
    return roof_area_acceptance_warranties(db, roof_area)
