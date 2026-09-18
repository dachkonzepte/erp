"""Router: project_documents

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 4 Endpunkt(e) und 1 interne Hilfsfunktion(en), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..document_categories import resolve_category_id
from ..models import AppUser, ProjectDocument
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..project_documents import can_preview_type, document_path, is_image_type
from ..schemas import ProjectDocumentOut, ProjectDocumentUpdate

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Projektdokumente sind Büro-/Admin-Bereich -- kein
# Endpunkt dieser Datei wird von einer Monteur-Vorlage aufgerufen.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))

def _project_document_out(doc: ProjectDocument) -> ProjectDocumentOut:
    return ProjectDocumentOut(
        id=doc.id, project_id=doc.project_id, category=doc.category, subfolder=doc.subfolder, original_filename=doc.original_filename,
        content_type=doc.content_type, file_size=doc.file_size, description=doc.description,
        document_date=doc.document_date, uploaded_at=doc.uploaded_at, is_image=is_image_type(doc.content_type),
        can_preview=can_preview_type(doc.content_type),
    )


@router.put("/api/project-documents/{document_id}", response_model=ProjectDocumentOut)
def update_project_document(document_id: int, payload: ProjectDocumentUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(ProjectDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    doc.category = payload.category; doc.category_id = resolve_category_id(db, payload.category)
    doc.subfolder = (payload.subfolder or None); doc.description = payload.description; doc.document_date = payload.document_date
    db.commit(); db.refresh(doc); return _project_document_out(doc)


@router.get("/api/project-documents/{document_id}/view")
def view_project_document(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(ProjectDocument, document_id)
    if doc is None: raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(doc)
    if not path.is_file(): raise HTTPException(status_code=404, detail="Datei nicht im Projektspeicher gefunden.")
    return FileResponse(path, media_type=doc.content_type or "application/octet-stream", filename=doc.original_filename, content_disposition_type="inline")


@router.get("/api/project-documents/{document_id}/download")
def download_project_document(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(ProjectDocument, document_id)
    if doc is None: raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(doc)
    if not path.is_file(): raise HTTPException(status_code=404, detail="Datei nicht im Projektspeicher gefunden.")
    return FileResponse(path, media_type=doc.content_type or "application/octet-stream", filename=doc.original_filename)


@router.delete("/api/project-documents/{document_id}")
def delete_project_document(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(ProjectDocument, document_id)
    if doc is None: raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(doc); db.delete(doc); db.commit(); path.unlink(missing_ok=True)
    return {"deleted": True}
