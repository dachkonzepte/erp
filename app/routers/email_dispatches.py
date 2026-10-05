"""Router: Versandprotokoll und Ablage versendeter Dokumente (seit 1.8.17).

Lesen ab buero_auftrag -- wer Angebote, Aufträge, Rechnungen und Mahnungen versendet, muss sehen,
ob sie hinausgingen. Monteure: 403 an jedem Endpunkt. Aufgaben-Benachrichtigungen nur für Admins:
eine zugewiesene Aufgabe sieht außer ihrem Empfänger nur Admin (app/tasks.py::list_tasks_for_user()).
Bis 1.8.52 stand der Aufgabentitel im Betreff; seit 1.8.53 enthält die Mail keinen Inhalt der Aufgabe
mehr, der Eintrag verrät aber weiterhin, wer wann eine Aufgabe zugewiesen bekam.

Schreiben an genau zwei Stellen, beide ab buero_auftrag: einen hängengebliebenen Eintrag als
gesendet oder fehlgeschlagen klären, mit Notiz (seit 1.8.19; eine Aufgaben-Benachrichtigung nur
Admin, für alle anderen gibt es sie nicht -- 404), und eine Zustellung auf anderem Weg nachtragen
(seit 1.8.20; Einschreiben, persönliche Übergabe, Bote, Fax mit Datum, Notiz, optional Beleg; seit
1.8.41 mit Empfängerauswahl aus Auftraggeber und Beteiligten). Seit 1.8.41 dazu das Versandergebnis
("Empfang bestätigt am", "unzustellbar") je gesendetem Eintrag eines Dokuments, ebenfalls ab
buero_auftrag. Gesendet, geändert oder gelöscht wird dabei nichts.
"""

from datetime import date
from typing import Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..email_dispatch import (
    DISPATCH_TYPES, MAX_RECEIPT_BYTES, STATUSES, DispatchConflict, actor_of, delivery_recipients, dispatch_authorizations,
    dispatch_to_dict, list_dispatches, record_dispatch_outcome, record_manual_delivery, resolve_stuck_dispatch,
)
from ..modules import is_module_enabled
from ..models import AppUser, EmailDispatch, SentDocument
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, has_role, require_min_role
from ..schemas import EmailDispatchResolve
from ..sent_documents import (
    ArchiveFileError, frozen_or_fresh_pdf, read_sent_document, sent_document_to_dict, verify_sent_document,
)

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Das Versandprotokoll ist nur für Büro und Administratoren verfügbar."))


# Dokumentarten, die an einer Checkliste hängen -- ohne das Modul "checklisten" gesperrt (seit 1.8.41 für die neuen
# Endpunkte; "Zustellung nachtragen" prüft wie seit 1.8.20 nur "checkliste", siehe Nebenbefund 1.8.41).
CHECKLIST_DOCUMENT_TYPES = ("checkliste", "behinderungsanzeige", "wiederaufnahme", "bedenkenanzeige")


def _require_module_for(db: Session, document_type: str) -> None:
    if document_type in CHECKLIST_DOCUMENT_TYPES and not is_module_enabled(db, "checklisten"):
        raise HTTPException(status_code=403, detail="Das Modul Checklisten & Formulare ist deaktiviert.")


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


@router.get("/api/email-dispatches/delivery-recipients")
def get_delivery_recipients(document_type: str, document_id: int, db: Session = Depends(get_db),
                            _user: AppUser = _role_dep):
    """Empfängerauswahl für "Zustellung nachtragen" (seit 1.8.41): Auftraggeber und Beteiligte des Projekts."""
    _require_module_for(db, document_type)
    try:
        return delivery_recipients(db, document_type, document_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/email-dispatches/manual")
def post_manual_delivery(
    document_type: str = Form(...), document_id: int = Form(...), channel: str = Form(...),
    delivered_on: date = Form(...), note: str = Form(""), recipient: str = Form(""),
    dispatch_key: str = Form(...), receipt: UploadFile | None = File(None),
    to_client: bool = Form(False), participant_ids: list[int] = Form([]),
    db: Session = Depends(get_db), user: AppUser = _role_dep,
):
    """Zustellung auf anderem Weg nachtragen (seit 1.8.20): Eintrag im Protokoll, PDF des Dokuments
    und optional der Beleg in der Ablage. Gewöhnliche def-Route (PDF-Erzeugung, Bildprüfung). Seit 1.8.41
    Empfängerauswahl: to_client (Auftraggeber) und participant_ids (Beteiligte des Projekts, mehrfach)."""
    if document_type == "checkliste" and not is_module_enabled(db, "checklisten"):
        raise HTTPException(status_code=403, detail="Das Modul Checklisten & Formulare ist deaktiviert.")
    receipt_bytes = None
    if receipt is not None and receipt.filename:
        receipt_bytes = receipt.file.read(MAX_RECEIPT_BYTES + 1)
    user_id, user_name = actor_of(user)
    try:
        result = record_manual_delivery(
            db, dispatch_key=dispatch_key, document_type=document_type, document_id=document_id, channel=channel,
            delivered_on=delivered_on, note=note, recipient=recipient, receipt_bytes=receipt_bytes or None,
            receipt_filename=receipt.filename if receipt is not None else None, user_id=user_id, user_name=user_name,
            to_client=to_client, participant_ids=participant_ids,
        )
    except DispatchConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return dispatch_to_dict(result.dispatch, authorizations=dispatch_authorizations(db, [result.dispatch.id]).get(result.dispatch.id))


@router.post("/api/email-dispatches/{dispatch_id}/outcome")
def post_dispatch_outcome(
    dispatch_id: int, outcome: str = Form(...), outcome_on: date = Form(...), note: str = Form(""),
    receipt: UploadFile | None = File(None), db: Session = Depends(get_db), user: AppUser = _role_dep,
):
    """"Empfang bestätigt am" bzw. "als unzustellbar markieren" (seit 1.8.41): einmal je gesendetem Eintrag eines
    Dokuments, mit Datum, Notiz (bei unzustellbar Pflicht) und optional Beleg. Aufgaben-Benachrichtigungen haben kein
    Ergebnis (404). Gewöhnliche def-Route (Bildprüfung des Belegs)."""
    dispatch = db.get(EmailDispatch, dispatch_id)
    if dispatch is None or dispatch.document_type == "aufgabe":
        raise HTTPException(status_code=404, detail="Protokolleintrag nicht gefunden.")
    _require_module_for(db, dispatch.document_type)
    receipt_bytes = None
    if receipt is not None and receipt.filename:
        receipt_bytes = receipt.file.read(MAX_RECEIPT_BYTES + 1)
    user_id, user_name = actor_of(user)
    try:
        row = record_dispatch_outcome(
            db, dispatch_id, outcome=outcome, outcome_on=outcome_on, note=note, receipt_bytes=receipt_bytes or None,
            receipt_filename=receipt.filename if receipt is not None else None, user_id=user_id, user_name=user_name,
        )
    except DispatchConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.expire_all()
    return dispatch_to_dict(db.get(EmailDispatch, dispatch_id), outcome=row)


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
    filename = doc.filename.replace('"', "").replace("/", "-").replace("\\", "-")
    # seit 1.8.20 auch Belege (Bild/PDF, beim Hochladen am Inhalt erkannt, nie SVG/HTML); nosniff,
    # damit der Browser nichts anderes daraus macht.
    return Response(content=content, media_type=doc.content_type or "application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"', "X-Content-Type-Options": "nosniff"})
