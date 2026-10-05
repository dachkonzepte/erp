"""Router: Mängel zur Beseitigung in der Monteursansicht /mobil (seit 1.8.52, Stufe 2c-2b,
docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.52").

- GET /api/field-view/defects: die Mängel, die der eigene Mitarbeiter beseitigen soll -- freigegeben, Status offen, nicht
  verworfen, an einem Auftrag, den er öffnen darf (app/defects.py::list_field_defects()). Antwortschema FieldDefectOut
  ist die Positivliste.
- GET /api/field-view/defects/{defect_id}/photos/{file_id}: ein Foto genau dieses Mangels, dieselbe Prüfung wie die
  Liste, nur Art "foto", nur mit stimmender Prüfsumme (409/410), nosniff. Der Büro-Weg /api/defects/... bleibt 403.
- POST /api/field-view/defects/{defect_id}/remedied: "beseitigt" melden (multipart: "data" = FieldDefectRemedied als
  JSON, "photos" mindestens eins), idempotent über client_uuid; seit 1.8.54 optional ein kurzer Hinweis ("note"), nur
  fürs Büro -- die Antwort nennt ihn nicht.

Der Mitarbeiter kommt ausschließlich aus dem angemeldeten Konto (wie GET /api/field-view/today), nie aus der Anfrage.
Was der Monteur nicht sehen darf -- nicht freigegeben, fremder Auftrag, verworfen, schon beseitigt, gibt es nicht --,
beantworten alle drei Routen gleich mit 404, ohne den Grund zu nennen. Offen für jede Rolle (require_min_role(field));
ein Büro-Konto sieht damit seine eigenen Mängel, ohne Mitarbeiter 422.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..defects import (
    AcceptanceFileError, DefectConflict, field_photo, field_report_dict, field_report_replay, field_visible_defect,
    list_field_defects, read_defect_file, report_remedied,
)
from ..email_dispatch import actor_of
from ..models import AppUser
from ..permissions import ROLE_FIELD, require_min_role
from ..schemas import FieldDefectOut, FieldDefectRemedied, FieldDefectReportOut
from .defects import _parse, _read_uploads

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_FIELD))
NOT_FOUND = "Mangel nicht gefunden."


def _employee_id(user: AppUser) -> int:
    if user.employee_id is None:
        raise HTTPException(status_code=422, detail="Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet -- bitte "
                                                    "einen Administrator kontaktieren.")
    return user.employee_id


def _visible_or_404(db: Session, user: AppUser, defect_id: int):
    defect = field_visible_defect(db, _employee_id(user), defect_id)
    if defect is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return defect


@router.get("/api/field-view/defects", response_model=list[FieldDefectOut])
def get_field_defects(db: Session = Depends(get_db), user: AppUser = _role_dep):
    return list_field_defects(db, _employee_id(user))


@router.get("/api/field-view/defects/{defect_id}/photos/{file_id}")
def get_field_defect_photo(defect_id: int, file_id: int, db: Session = Depends(get_db), user: AppUser = _role_dep):
    row = field_photo(_visible_or_404(db, user, defect_id), file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Foto nicht gefunden.")
    try:
        content = read_defect_file(row)
    except AcceptanceFileError as e:
        raise HTTPException(status_code=410 if e.status == "fehlt" else 409, detail=str(e)) from e
    suffix = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[row.content_type]
    return Response(content=content, media_type=row.content_type, headers={
        "Content-Disposition": f'inline; filename="Mangel-{defect_id}-{row.id}.{suffix}"',
        "X-Content-Type-Options": "nosniff",
    })


@router.post("/api/field-view/defects/{defect_id}/remedied", response_model=FieldDefectReportOut)
def post_field_defect_remedied(defect_id: int, data: str = Form(...), photos: list[UploadFile] = File(default=[]),
                               db: Session = Depends(get_db), user: AppUser = _role_dep):
    """Zuerst die Wiederholung (dieselbe Kennung -> dieselbe Antwort, auch wenn der Mangel durch die Meldung schon
    unsichtbar ist), dann die Sichtbarkeit (404), dann die Meldung selbst (400/409)."""
    _employee_id(user)
    payload = _parse(FieldDefectRemedied, data)
    user_id, user_name = actor_of(user)
    try:
        replay = field_report_replay(db, defect_id, payload.client_uuid, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if replay is not None:
        return field_report_dict(replay)
    defect = _visible_or_404(db, user, defect_id)
    uploads = _read_uploads([("foto", photos)])
    try:
        event = report_remedied(db, defect, event_date=payload.event_date, client_uuid=payload.client_uuid,
                                files=uploads, note=payload.note, user_id=user_id, user_name=user_name)
    except DefectConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return field_report_dict(event)
