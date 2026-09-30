"""Router: Versandprotokoll und Ablage versendeter Dokumente (seit 1.8.17).

Lesen ab buero_auftrag -- wer Angebote, Aufträge, Rechnungen und Mahnungen versendet, muss sehen,
ob sie hinausgingen. Monteure: 403 an jedem Endpunkt. Aufgaben-Benachrichtigungen (Betreff =
Aufgabentitel) nur für Admins: eine zugewiesene Aufgabe sieht außer ihrem Empfänger nur Admin
(app/tasks.py::list_tasks_for_user()).

Schreiben (seit 1.8.19) nur an genau einer Stelle: einen hängengebliebenen Eintrag als gesendet
oder fehlgeschlagen klären, mit Notiz (ab buero_auftrag; eine Aufgaben-Benachrichtigung nur Admin,
für alle anderen gibt es sie nicht -- 404). Gesendet, geändert oder gelöscht wird dabei nichts
sonst; Einträge entstehen nur beim Versand.
"""

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..email_dispatch import (
    DISPATCH_TYPES, STATUSES, DispatchConflict, actor_of, dispatch_to_dict, list_dispatches, resolve_stuck_dispatch,
)
from ..models import AppUser, EmailDispatch, SentDocument
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, has_role, require_min_role
from ..schemas import EmailDispatchResolve
from ..sent_documents import (
    ArchiveFileError, frozen_or_fresh_pdf, read_sent_document, sent_document_to_dict, verify_sent_document,
)

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Das Versandprotokoll ist nur für Büro und Administratoren verfügbar."))


def _archive_http_error(e: ArchiveFileError) -> HTTPException:
    return HTTPException(status_code=410 if e.status == "fehlt" else 409, detail=str(e))


def document_pdf_response(db: Session, document_type: str, document_id: int, *, build: Callable[[], bytes],
                          filename: str) -> Response:
    """PDF-Antwort für Nachdruck/Download von Rechnung, Storno und Mahnung (seit 1.8.19): ab dem
    ersten Versand die abgelegte Fassung (Kopfzeile X-DK-Ablage mit ihrer ID), sonst neu erzeugt.
    Ist die abgelegte Datei verändert oder fehlt sie, wird nicht still neu erzeugt -- 409 bzw. 410
    wie beim Abruf aus dem Versandprotokoll. Die Rollenprüfung macht der aufrufende Router."""
    try:
        pdf = frozen_or_fresh_pdf(db, document_type, document_id, build=build, filename=filename)
    except ArchiveFileError as e:
        raise HTTPException(
            status_code=410 if e.status == "fehlt" else 409,
            detail=f"Die versendete Fassung in der Ablage ist nicht mehr unversehrt: {e} Bitte im Versandprotokoll prüfen.",
        )
    headers = {"Content-Disposition": f'inline; filename="{filename}"'}
    if pdf.archived is not None:
        headers["X-DK-Ablage"] = str(pdf.archived.id)
    return Response(content=pdf.content, media_type="application/pdf", headers=headers)


@router.get("/api/email-dispatches")
def get_email_dispatches(
    status: str | None = None, document_type: str | None = None, document_id: int | None = None,
    stuck: bool = False, limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db), user: AppUser = _role_dep,
):
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail="Unbekannter Status.")
    if document_type and document_type not in DISPATCH_TYPES:
        raise HTTPException(status_code=400, detail="Unbekannte Versandart.")
    return list_dispatches(
        db, status=status, document_type=document_type, document_id=document_id, stuck_only=stuck,
        include_task_mails=has_role(user, ROLE_ADMIN), limit=limit,
    )


@router.post("/api/email-dispatches/{dispatch_id}/resolve")
def post_resolve_email_dispatch(dispatch_id: int, payload: EmailDispatchResolve, db: Session = Depends(get_db),
                                user: AppUser = _role_dep):
    """Hängengebliebenen Versand klären (seit 1.8.19): nach Blick in den Postausgang als gesendet
    oder fehlgeschlagen, mit Pflicht-Notiz; steht am Eintrag und in der Änderungshistorie."""
    dispatch = db.get(EmailDispatch, dispatch_id)
    if dispatch is None or (dispatch.document_type == "aufgabe" and not has_role(user, ROLE_ADMIN)):
        raise HTTPException(status_code=404, detail="Protokolleintrag nicht gefunden.")
    user_id, user_name = actor_of(user)
    try:
        resolved = resolve_stuck_dispatch(db, dispatch_id, outcome=payload.outcome, note=payload.note,
                                          user_id=user_id, user_name=user_name)
    except DispatchConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return dispatch_to_dict(resolved)


def _sent_document_or_404(db: Session, sent_document_id: int) -> SentDocument:
    doc = db.get(SentDocument, sent_document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Abgelegtes Dokument nicht gefunden.")
    return doc


@router.get("/api/sent-documents/{sent_document_id}/check")
def check_sent_document(sent_document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Rechnet die Prüfsumme der Datei neu (liest die ganze Datei, deshalb nur auf Anfrage)."""
    doc = _sent_document_or_404(db, sent_document_id)
    return {**sent_document_to_dict(doc), "check": verify_sent_document(doc)}


@router.get("/api/sent-documents/{sent_document_id}/file")
def get_sent_document_file(sent_document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    """Die abgelegte Datei, genau so wie versendet -- nur, wenn ihre Prüfsumme stimmt. Eine
    veränderte Datei wird nicht als "das versendete Dokument" ausgeliefert (409), eine fehlende
    meldet 410."""
    doc = _sent_document_or_404(db, sent_document_id)
    try:
        content = read_sent_document(doc)
    except ArchiveFileError as e:
        raise _archive_http_error(e)
    filename = doc.filename.replace('"', "").replace("/", "-")
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})
