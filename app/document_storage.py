"""Gemeinsame, rein generische Datei-Hilfsfunktionen (seit 1.0.54).

Extrahiert aus app/project_documents.py, das project_documents.py weiterhin
denselben Import-Pfad für Bestandscode anbietet (siehe Re-Export dort) --
customer_documents.py importiert direkt von hier, ohne Umweg.
"""

import uuid
from pathlib import Path

from .dateiauslieferung import anzeigbar, ist_rasterbild


def make_stored_filename(original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()[:20]
    return f"{uuid.uuid4().hex}{suffix}"


def is_image_type(content_type: str | None) -> bool:
    """Seit 1.8.101 nur Rasterbilder (JPEG, PNG, GIF, WebP) -- vorher jedes image/*, auch SVG (app/dateiauslieferung.py)."""
    return ist_rasterbild(content_type)


def can_preview_type(content_type: str | None) -> bool:
    """Seit 1.8.101 nur, was der Browser zeigen darf: Rasterbilder und PDF (app/dateiauslieferung.py)."""
    return anzeigbar(content_type)
