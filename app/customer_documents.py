"""Datei-Ablage in der Kundenmappe (seit 1.0.54, Dokumentenmanagement).

Bewusst strukturell identisch zu app/project_documents.py -- eigener Speicherort
(data/customer_files/{customer_id}/...) statt einer gemeinsamen Ablage mit
Projektdateien, damit eine spätere Kundenlöschung nicht versehentlich in den
Projektdateien anderer Kunden nach etwas sucht.
"""

import os
from pathlib import Path

from .document_storage import can_preview_type, is_image_type, make_stored_filename  # noqa: F401
from .models import CustomerDocument

CUSTOMER_ROOT = Path(os.getenv("DACHKONZEPTE_CUSTOMER_FILE_ROOT", Path(__file__).resolve().parent.parent / "data" / "customer_files"))
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def customer_directory(customer_id: int) -> Path:
    path = CUSTOMER_ROOT / str(customer_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def document_path(document: CustomerDocument) -> Path:
    return CUSTOMER_ROOT / str(document.customer_id) / document.stored_filename
