"""Gemeinsame, rein generische Datei-Hilfsfunktionen (seit 1.0.54).

Extrahiert aus app/project_documents.py, das project_documents.py weiterhin
denselben Import-Pfad für Bestandscode anbietet (siehe Re-Export dort) --
customer_documents.py importiert direkt von hier, ohne Umweg.
"""

import uuid
from pathlib import Path


def make_stored_filename(original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()[:20]
    return f"{uuid.uuid4().hex}{suffix}"


def is_image_type(content_type: str | None) -> bool:
    return bool(content_type and content_type.lower().startswith("image/"))


def can_preview_type(content_type: str | None) -> bool:
    return is_image_type(content_type) or (content_type or "").lower() == "application/pdf"
