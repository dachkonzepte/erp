"""Router: customer_documents (seit 1.0.54).

Operationen auf einem einzelnen, bereits vorhandenen Kundendokument -- exakt
nach dem Muster von app/routers/project_documents.py (dort auch die
Begründung für Struktur/Fehlerbehandlung). Liste/Upload leben dagegen in
customers.py, analog zu list_project_documents/upload_project_document in
projects.py.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..customer_documents import can_preview_type, document_path, is_image_type
from ..database import get_db
from ..document_categories import resolve_category_id
from ..models import AppUser, CustomerDocument
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import CustomerDocumentOut, CustomerDocumentUpdate

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Kundendokumente sind Büro-/Admin-Bereich -- kein
# Endpunkt dieser Datei wird von einer Monteur-Vorlage aufgerufen.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))

def _customer_document_out(doc: CustomerDocument) -> CustomerDocumentOut:
    return CustomerDocumentOut(
        id=doc.id, customer_id=doc.customer_id, category=doc.category, subfolder=doc.subfolder, original_filename=doc.original_filename,
        content_type=doc.content_type, file_size=doc.file_size, description=doc.description,
        document_date=doc.document_date, uploaded_at=doc.uploaded_at, is_image=is_image_type(doc.content_type),
        can_preview=can_preview_type(doc.content_type),
    )


@router.put("/api/customer-documents/{document_id}", response_model=CustomerDocumentOut)
def update_customer_document(document_id: int, payload: CustomerDocumentUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(CustomerDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    doc.category = payload.category; doc.category_id = resolve_category_id(db, payload.category)
    doc.subfolder = (payload.subfolder or None); doc.description = payload.description; doc.document_date = payload.document_date
    db.commit(); db.refresh(doc); return _customer_document_out(doc)


@router.get("/api/customer-documents/{document_id}/view")
def view_customer_document(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(CustomerDocument, document_id)
    if doc is None: raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(doc)
    if not path.is_file(): raise HTTPException(status_code=404, detail="Datei nicht im Kundenspeicher gefunden.")
    return FileResponse(path, media_type=doc.content_type or "application/octet-stream", filename=doc.original_filename, content_disposition_type="inline")


@router.get("/api/customer-documents/{document_id}/download")
def download_customer_document(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(CustomerDocument, document_id)
    if doc is None: raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(doc)
    if not path.is_file(): raise HTTPException(status_code=404, detail="Datei nicht im Kundenspeicher gefunden.")
    return FileResponse(path, media_type=doc.content_type or "application/octet-stream", filename=doc.original_filename)


@router.delete("/api/customer-documents/{document_id}")
def delete_customer_document(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(CustomerDocument, document_id)
    if doc is None: raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(doc); db.delete(doc); db.commit(); path.unlink(missing_ok=True)
    return {"deleted": True}
