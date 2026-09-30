"""Router: Versandprotokoll und Ablage versendeter Dokumente (seit 1.8.17).

Lesen ab buero_auftrag -- wer Angebote, Aufträge, Rechnungen und Mahnungen versendet, muss sehen,
ob sie hinausgingen. Monteure: 403 an jedem Endpunkt. Aufgaben-Benachrichtigungen (Betreff =
Aufgabentitel) nur für Admins: eine zugewiesene Aufgabe sieht außer ihrem Empfänger nur Admin
(app/tasks.py::list_tasks_for_user()). Schreibende Endpunkte gibt es nicht -- Einträge entstehen
nur beim Versand, nichts wird geändert oder gelöscht.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..email_dispatch import DISPATCH_TYPES, STATUSES, list_dispatches
from ..models import AppUser, SentDocument
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, has_role, require_min_role
from ..sent_documents import ArchiveFileError, read_sent_document, sent_document_to_dict, verify_sent_document

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Das Versandprotokoll ist nur für Büro und Administratoren verfügbar."))


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
        raise HTTPException(status_code=410 if e.status == "fehlt" else 409, detail=str(e))
    filename = doc.filename.replace('"', "").replace("/", "-")
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})
