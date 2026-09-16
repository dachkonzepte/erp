"""Router: property_documents ("Dateiablage je Objekt", siehe CLAUDE.md) -- Büro-/Admin-Sicht.

Liste + Upload + Einzeldokument-CRUD bewusst in EINER Datei (anders als beim
Kunden-/Projektmappen-Muster, das Liste+Upload im jeweiligen Eltern-Router hält, siehe
customers.py/customer_documents.py) -- properties.py bleibt dadurch unangetastet, dessen
Docstring beschreibt ausdrücklich nur die vier ursprünglichen, unveränderten Endpunkte.

Zeigt die zusammengeführte Liste aus PropertyDocument (eigene Objekt-Uploads, u. a. die eines
Monteurs über die mobile Ansicht) UND ProjectDocument (alle nicht archivierten Projekte dieses
Objekts) -- damit Monteur-Uploads hier tatsächlich "auffindbar" sind, wie gefordert. Ein
ProjectDocument-Eintrag in dieser Liste wird über den bereits bestehenden, unveränderten
/api/project-documents/{id}/...-Weg angesehen/heruntergeladen (kein zweiter Weg dafür nötig)."""

from fastapi import APIRouter
from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppUser, DocumentCategory, Property, PropertyDocument
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..property_documents import (
    MAX_UPLOAD_BYTES, can_preview_type, create_property_document, delete_property_document,
    document_path, is_image_type, list_merged_documents_for_property,
)
from ..schemas import PropertyDocumentListItemOut, PropertyDocumentOut

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): die Objekt-Dokumentverwaltung selbst ist Büro-/
# Admin-Bereich -- der feldsichere, stark eingeschränkte Lesezugriff eines Monteurs läuft über
# eigene, unabhängige Endpunkte (app/routers/field_view.py).
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


def _property_document_out(doc: PropertyDocument) -> PropertyDocumentOut:
    return PropertyDocumentOut(
        id=doc.id, property_id=doc.property_id, category_id=doc.category_id,
        category_key=doc.document_category.key, category_label=doc.document_category.label,
        original_filename=doc.original_filename, content_type=doc.content_type, file_size=doc.file_size,
        description=doc.description, uploaded_at=doc.uploaded_at,
        uploaded_by_employee_id=doc.uploaded_by_employee_id,
        is_image=is_image_type(doc.content_type), can_preview=can_preview_type(doc.content_type),
    )


@router.get("/api/properties/{property_id}/documents", response_model=list[PropertyDocumentListItemOut])
def list_property_documents(property_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    if db.get(Property, property_id) is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    return list_merged_documents_for_property(db, property_id)


@router.post("/api/properties/{property_id}/documents", response_model=PropertyDocumentOut)
async def upload_property_document(
    property_id: int, file: UploadFile = File(...), category_id: int = Form(...),
    description: str | None = Form(None), db: Session = Depends(get_db), _role: AppUser = _role_dep,
):
    if db.get(Property, property_id) is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    category = db.get(DocumentCategory, category_id)
    if category is None:
        raise HTTPException(status_code=422, detail="Kategorie nicht gefunden.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 50 MB.")
    doc = create_property_document(
        db, property_id, category_id=category_id, file_data=data, original_filename=file.filename,
        content_type=file.content_type, description=description,
    )
    db.refresh(doc, attribute_names=["document_category"])
    return _property_document_out(doc)


@router.get("/api/property-documents/{document_id}/view")
def view_property_document(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(PropertyDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(doc)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datei nicht im Objektspeicher gefunden.")
    return FileResponse(path, media_type=doc.content_type or "application/octet-stream", filename=doc.original_filename, content_disposition_type="inline")


@router.get("/api/property-documents/{document_id}/download")
def download_property_document(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(PropertyDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    path = document_path(doc)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datei nicht im Objektspeicher gefunden.")
    return FileResponse(path, media_type=doc.content_type or "application/octet-stream", filename=doc.original_filename)


@router.delete("/api/property-documents/{document_id}")
def delete_property_document_endpoint(document_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    doc = db.get(PropertyDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    delete_property_document(db, doc)
    return {"deleted": True}
