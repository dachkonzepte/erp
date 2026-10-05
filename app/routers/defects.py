"""Router: Mängel aus der Abnahme (seit 1.8.49, Stufe 2c-2a, docs/archiv/abnahme-und-gewaehrleistung.md).

- GET /api/orders/{order_id}/defects: alle Mängel des Auftrags samt verworfener -- Stand, Verlauf, Prüfung, Aufgabe,
  bei VOB/B "Nachbesserung regulär bis".
- GET /api/order-acceptances/{acceptance_id}/defect-options: Auswahl zum Erfassen (Dachflächen aus dem Objekt der
  Abnahme, Beteiligte mit Vollmacht zur Abnahme).
- POST /api/order-acceptances/{acceptance_id}/defects: erfassen (multipart: "data" als JSON, "photos", "receipts").
- POST /api/defects/{defect_id}/stance und /release (JSON), /status (multipart: "data", "receipts"), /photos
  (multipart), seit 1.8.51 /receipts (multipart: Belege nachreichen), /discard (JSON).
- GET /api/defects/{defect_id}/files/{file_id}: Datei, nur mit stimmender Prüfsumme.

Alles ab buero_auftrag -- auch die Freigabe zur Beseitigung setzt nur das Büro; Monteure sehen nichts (403). Kein
Ändern und kein Löschen eines Mangels oder eines Eintrags im Verlauf.
"""

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..defects import (
    MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES, AcceptanceFileError, DefectConflict, add_photos, add_receipts,
    create_defect,
    defect_options, discard_defect, get_defect_dict, list_defects, read_defect_file, set_release, set_stance,
    set_status,
)
from ..email_dispatch import actor_of
from ..models import AppUser, Defect, DefectFile, Order, OrderAcceptance
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import DefectCreate, DefectDiscard, DefectRelease, DefectStance, DefectStatusChange

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Mängel sind nur für Büro und Administratoren "
                                                                  "verfügbar."))


def _order_or_404(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
    return order


def _acceptance_or_404(db: Session, acceptance_id: int) -> OrderAcceptance:
    acceptance = db.get(OrderAcceptance, acceptance_id)
    if acceptance is None:
        raise HTTPException(status_code=404, detail="Abnahme nicht gefunden.")
    return acceptance


def _defect_or_404(db: Session, defect_id: int) -> Defect:
    defect = db.get(Defect, defect_id, options=[selectinload(Defect.files), selectinload(Defect.events)])
    if defect is None:
        raise HTTPException(status_code=404, detail="Mangel nicht gefunden.")
    return defect


def _parse(model: type[BaseModel], data: str) -> BaseModel:
    try:
        return model.model_validate_json(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json(include_url=False))) from exc


def _read_uploads(groups: list[tuple[str, list[UploadFile]]]) -> list[tuple[str, str | None, bytes]]:
    """Dateien beim Lesen begrenzen (je Datei und zusammen) -- kein übergroßer Upload ganz im Speicher."""
    if sum(len(files) for _, files in groups) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Höchstens {MAX_FILES} Dateien je Speichern.")
    result, total = [], 0
    for kind, files in groups:
        for upload in files:
            content = upload.file.read(min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total) + 1)
            total += len(content)
            if total > MAX_TOTAL_BYTES:
                raise HTTPException(status_code=400, detail=f"Die Dateien sind zusammen größer als "
                                                            f"{MAX_TOTAL_BYTES // 1_000_000} MB.")
            result.append((kind, upload.filename, content))
    return result


def _run(db: Session, defect_id: int, action):
    try:
        action()
    except DefectConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_defect_dict(db, _defect_or_404(db, defect_id))


@router.get("/api/orders/{order_id}/defects")
def get_order_defects(order_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return list_defects(db, _order_or_404(db, order_id))


@router.get("/api/order-acceptances/{acceptance_id}/defect-options")
def get_defect_options(acceptance_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return defect_options(db, _acceptance_or_404(db, acceptance_id))


@router.post("/api/order-acceptances/{acceptance_id}/defects")
def post_defect(acceptance_id: int, data: str = Form(...), photos: list[UploadFile] = File(default=[]),
                receipts: list[UploadFile] = File(default=[]), db: Session = Depends(get_db),
                user: AppUser = _role_dep):
    """`data`: DefectCreate als JSON; `photos`: Fotos (JPEG, PNG, WebP), `receipts`: Belege (PDF oder Foto)."""
    acceptance = _acceptance_or_404(db, acceptance_id)
    payload = _parse(DefectCreate, data)
    uploads = _read_uploads([("foto", photos), ("beleg", receipts)])
    user_id, user_name = actor_of(user)
    try:
        defect = create_defect(db, acceptance, payload.model_dump(), uploads, user_id=user_id, user_name=user_name)
    except DefectConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_defect_dict(db, _defect_or_404(db, defect.id))


@router.post("/api/defects/{defect_id}/stance")
def post_defect_stance(defect_id: int, payload: DefectStance, db: Session = Depends(get_db),
                       user: AppUser = _role_dep):
    defect = _defect_or_404(db, defect_id)
    user_id, user_name = actor_of(user)
    return _run(db, defect_id, lambda: set_stance(db, defect, stance=payload.stance, reason=payload.reason,
                                                  user_id=user_id, user_name=user_name))


@router.post("/api/defects/{defect_id}/release")
def post_defect_release(defect_id: int, payload: DefectRelease, db: Session = Depends(get_db),
                        user: AppUser = _role_dep):
    defect = _defect_or_404(db, defect_id)
    user_id, user_name = actor_of(user)
    return _run(db, defect_id, lambda: set_release(db, defect, released=payload.released, reason=payload.reason,
                                                   user_id=user_id, user_name=user_name))


@router.post("/api/defects/{defect_id}/status")
def post_defect_status(defect_id: int, data: str = Form(...), receipts: list[UploadFile] = File(default=[]),
                       db: Session = Depends(get_db), user: AppUser = _role_dep):
    defect = _defect_or_404(db, defect_id)
    payload = _parse(DefectStatusChange, data)
    uploads = _read_uploads([("beleg", receipts)])
    user_id, user_name = actor_of(user)
    return _run(db, defect_id, lambda: set_status(db, defect, payload.model_dump(), uploads, user_id=user_id,
                                                  user_name=user_name))


@router.post("/api/defects/{defect_id}/photos")
def post_defect_photos(defect_id: int, photos: list[UploadFile] = File(default=[]), db: Session = Depends(get_db),
                       user: AppUser = _role_dep):
    defect = _defect_or_404(db, defect_id)
    uploads = _read_uploads([("foto", photos)])
    user_id, user_name = actor_of(user)
    return _run(db, defect_id, lambda: add_photos(db, defect, uploads, user_id=user_id, user_name=user_name))


@router.post("/api/defects/{defect_id}/receipts")
def post_defect_receipts(defect_id: int, receipts: list[UploadFile] = File(default=[]), db: Session = Depends(get_db),
                         user: AppUser = _role_dep):
    """Belege nachreichen (seit 1.8.51) -- wie Fotos nur ergänzen."""
    defect = _defect_or_404(db, defect_id)
    uploads = _read_uploads([("beleg", receipts)])
    user_id, user_name = actor_of(user)
    return _run(db, defect_id, lambda: add_receipts(db, defect, uploads, user_id=user_id, user_name=user_name))


@router.post("/api/defects/{defect_id}/discard")
def post_defect_discard(defect_id: int, payload: DefectDiscard, db: Session = Depends(get_db),
                        user: AppUser = _role_dep):
    defect = _defect_or_404(db, defect_id)
    user_id, user_name = actor_of(user)
    return _run(db, defect_id, lambda: discard_defect(db, defect, reason=payload.reason, user_id=user_id,
                                                      user_name=user_name))


@router.get("/api/defects/{defect_id}/files/{file_id}")
def get_defect_file(defect_id: int, file_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Die Datei genau so wie hochgeladen -- nur mit stimmender Prüfsumme (sonst 409, fehlt 410); nosniff."""
    row = db.get(DefectFile, file_id)
    if row is None or row.defect_id != defect_id:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.")
    try:
        content = read_defect_file(row)
    except AcceptanceFileError as e:
        raise HTTPException(status_code=410 if e.status == "fehlt" else 409, detail=str(e)) from e
    suffix = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[row.content_type]
    return Response(content=content, media_type=row.content_type, headers={
        "Content-Disposition": f'inline; filename="Mangel-{row.defect_id}-{row.id}.{suffix}"',
        "X-Content-Type-Options": "nosniff",
    })
