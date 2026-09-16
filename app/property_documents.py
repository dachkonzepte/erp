"""Dateiablage je Objekt (seit "Dateiablage je Objekt", siehe CLAUDE.md) -- Runde 2 der
Monteurs-Erweiterung, Schritt 2 (nach den Kategorie-Stammdaten aus 1.3.62).

Zwei Dokumentquellen werden für ein Objekt zusammengeführt, siehe list_merged_documents_for_property():
1. PropertyDocument -- eigene, objektgebundene Uploads (insbesondere die eines Monteurs vor Ort,
   siehe Klassen-Docstring in app/models.py für die Begründung, warum das eine eigene Tabelle statt
   eines Sammelprojekts je Objekt ist).
2. ProjectDocument -- die Dokumente ALLER NICHT ARCHIVIERTEN Projekte dieses Objekts
   (Project.property_id), wie vom Betreiber vorgegeben ("ein Dachdecker denkt in Objekten, nicht
   in Projektnummern"). CustomerDocument bleibt bewusst AUSSEN VOR -- das ist Kundenebene, nicht
   Objektebene, und gehört fachlich nicht zu "die Dokumente dieses Objekts".

Bildformat-Verkleinerung wie bei den Berichtsfotos aus 1.2.17 (app/service_report_photos.py),
aber NICHT durch Aufruf jener Funktion -- die ist fest an PHOTO_ROOT gebunden (siehe Recherche
vor dieser Änderung), diese Datei trägt deshalb eine eigene, strukturell identische Kopie mit
eigenem PROPERTY_ROOT. Dokumente (PDF u. Ä.) bleiben unverändert im Original erhalten, nur Bilder
werden verkleinert."""

import os
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .document_categories import field_may_see_category
from .document_storage import can_preview_type, is_image_type, make_stored_filename  # noqa: F401
from .models import DocumentCategory, Project, PropertyDocument, ProjectDocument
from .paths import data_dir

PROPERTY_ROOT = Path(os.getenv("DACHKONZEPTE_PROPERTY_FILE_ROOT", data_dir() / "property_files"))
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # Rohdatei vor einer eventuellen Bild-Verkleinerung
MAX_IMAGE_DIMENSION = 1600  # längste Kante nach der Verkleinerung, wie bei Berichtsfotos (1.2.17)
IMAGE_JPEG_QUALITY = 82


def property_directory(property_id: int) -> Path:
    path = PROPERTY_ROOT / str(property_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def document_path(document: PropertyDocument) -> Path:
    return PROPERTY_ROOT / str(document.property_id) / document.stored_filename


def _store_uploaded_file(property_id: int, original_filename: str, content_type: str | None, data: bytes) -> str:
    """Bilder werden wie Berichtsfotos verkleinert und einheitlich als JPEG gespeichert,
    Dokumente (PDF u. Ä.) bleiben im Original erhalten -- exakt die vom Betreiber verlangte
    Unterscheidung. Gibt den gespeicherten Dateinamen zurück."""
    target_dir = property_directory(property_id)
    if is_image_type(content_type):
        image = Image.open(BytesIO(data))
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
        stored = f"{uuid.uuid4().hex}.jpg"
        image.save(target_dir / stored, format="JPEG", quality=IMAGE_JPEG_QUALITY)
        return stored
    stored = make_stored_filename(original_filename)
    (target_dir / stored).write_bytes(data)
    return stored


def create_property_document(
    db: Session, property_id: int, *, category_id: int, file_data: bytes, original_filename: str,
    content_type: str | None, description: str | None = None, uploaded_by_employee_id: int | None = None,
) -> PropertyDocument:
    stored = _store_uploaded_file(property_id, original_filename, content_type, file_data)
    doc = PropertyDocument(
        property_id=property_id, category_id=category_id, original_filename=Path(original_filename).name,
        stored_filename=stored, content_type=content_type, file_size=len(file_data),
        description=(description or None), uploaded_by_employee_id=uploaded_by_employee_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def delete_property_document(db: Session, document: PropertyDocument) -> None:
    path = document_path(document)
    db.delete(document)
    db.commit()
    path.unlink(missing_ok=True)


def _document_category_allowed(category: DocumentCategory | None, *, field_visible_only: bool) -> bool:
    if category is None or not category.active:
        return False
    if field_visible_only:
        return field_may_see_category(category)
    return True


def list_merged_documents_for_property(db: Session, property_id: int, *, field_visible_only: bool = False) -> list[dict]:
    """Führt PropertyDocument (eigene Objekt-Uploads) und ProjectDocument (aus allen NICHT
    archivierten Projekten dieses Objekts) zu einer gemeinsamen, nach Kategorie-Reihenfolge
    sortierten Liste zusammen -- reine Dicts statt ORM-Objekte, damit Büro-Ansicht (voller
    Bestand) und Monteursansicht (field_visible_only=True) dieselbe Funktion nutzen können.

    field_visible_only=True ist die einzige Stelle, an der ein Monteur überhaupt erfährt, dass
    ein Dokument existiert -- field_may_see_category() prüft dabei BEIDE Schlösser aus 1.3.62
    (is_sensitive/is_field_visible UND die feste HARD_LOCKED_CATEGORY_KEYS-Sperrliste)."""
    property_docs = db.scalars(
        select(PropertyDocument)
        .options(selectinload(PropertyDocument.document_category))
        .where(PropertyDocument.property_id == property_id)
    ).all()
    project_docs = db.scalars(
        select(ProjectDocument)
        .join(Project, ProjectDocument.project_id == Project.id)
        .options(selectinload(ProjectDocument.document_category))
        .where(Project.property_id == property_id, Project.archived == False)  # noqa: E712
    ).all()

    items: list[dict] = []
    for doc in property_docs:
        if not _document_category_allowed(doc.document_category, field_visible_only=field_visible_only):
            continue
        items.append({
            "source": "property", "id": doc.id, "property_id": doc.property_id, "project_id": None,
            "category_key": doc.document_category.key, "category_label": doc.document_category.label,
            "category_sort_order": doc.document_category.sort_order,
            "original_filename": doc.original_filename, "content_type": doc.content_type,
            "file_size": doc.file_size, "description": doc.description, "uploaded_at": doc.uploaded_at,
            "is_image": is_image_type(doc.content_type), "can_preview": can_preview_type(doc.content_type),
        })
    for doc in project_docs:
        if not _document_category_allowed(doc.document_category, field_visible_only=field_visible_only):
            continue
        items.append({
            "source": "project", "id": doc.id, "property_id": property_id, "project_id": doc.project_id,
            "category_key": doc.document_category.key, "category_label": doc.document_category.label,
            "category_sort_order": doc.document_category.sort_order,
            "original_filename": doc.original_filename, "content_type": doc.content_type,
            "file_size": doc.file_size, "description": doc.description, "uploaded_at": doc.uploaded_at,
            "is_image": is_image_type(doc.content_type), "can_preview": can_preview_type(doc.content_type),
        })
    items.sort(key=lambda d: (d["category_sort_order"], d["uploaded_at"] is None, -(d["uploaded_at"].timestamp() if d["uploaded_at"] else 0)))
    return items


def resolve_property_document_for_field(db: Session, property_id: int, source: str, document_id: int):
    """Löst ein einzelnes Dokument für den Datei-Abruf der Monteursansicht auf -- liefert
    (doc, path) NUR, wenn das Dokument tatsächlich zu diesem Objekt gehört (bei source="project"
    zusätzlich: das Projekt ist nicht archiviert) UND seine Kategorie field_may_see_category()
    erfüllt. Sonst None -- ununterscheidbar von "existiert nicht", damit ein Monteur über eine
    geratene ID nicht einmal bestätigt bekommt, dass eine gesperrte Datei überhaupt existiert.
    Beide Schlösser aus 1.3.62 greifen hier am Ausliefer-Zeitpunkt, nicht nur beim Auflisten."""
    if source == "property":
        doc = db.scalar(
            select(PropertyDocument)
            .options(selectinload(PropertyDocument.document_category))
            .where(PropertyDocument.id == document_id, PropertyDocument.property_id == property_id)
        )
        if doc is None or not field_may_see_category(doc.document_category):
            return None
        return doc, document_path(doc)
    if source == "project":
        from .project_documents import document_path as project_document_path

        doc = db.scalar(
            select(ProjectDocument)
            .join(Project, ProjectDocument.project_id == Project.id)
            .options(selectinload(ProjectDocument.document_category))
            .where(
                ProjectDocument.id == document_id, Project.property_id == property_id,
                Project.archived == False,  # noqa: E712
            )
        )
        if doc is None or not field_may_see_category(doc.document_category):
            return None
        return doc, project_document_path(doc)
    return None
