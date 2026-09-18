"""Router: document_email_templates (seit 1.0.82).

E-Mail-Betreff/-Text-Vorlagen je Dokumenttyp (Angebot/Auftrag/Rechnung) --
siehe app/document_email_templates.py für die Geschäftslogik.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..document_email_templates import DOCUMENT_TYPES, get_email_template, update_email_template
from ..models import AppUser
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import DocumentEmailTemplateOut, DocumentEmailTemplateUpdate

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): E-Mail-Vorlagen für Angebot/Auftrag/Rechnung sind
# Büro-/Admin-Konfiguration, für keinen Monteur relevant.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


def _validate_document_type(document_type: str) -> None:
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unbekannter Dokumenttyp: {document_type}")


@router.get("/api/document-email-templates/{document_type}", response_model=DocumentEmailTemplateOut)
def get_document_email_template(document_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_document_type(document_type)
    row = get_email_template(db, document_type)
    return DocumentEmailTemplateOut(
        document_type=document_type,
        subject_template=row.subject_template if row else None,
        body_template=row.body_template if row else None,
    )


@router.put("/api/document-email-templates/{document_type}", response_model=DocumentEmailTemplateOut)
def put_document_email_template(document_type: str, payload: DocumentEmailTemplateUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_document_type(document_type)
    row = update_email_template(db, document_type, subject_template=payload.subject_template, body_template=payload.body_template)
    return DocumentEmailTemplateOut(document_type=document_type, subject_template=row.subject_template, body_template=row.body_template)
