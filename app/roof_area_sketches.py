"""Skizzenbild-Ablage für Dachflächen (seit 1.2.14).

Ein Skizzenbild pro Dachfläche -- strukturell wie app/document_layout_background.py (ein Bild
pro Fremdschlüssel, kein Dokumentenmanagement mit Kategorien/Unterordnern/mehreren Dateien wie
bei project_documents.py/customer_documents.py)."""

import os
from pathlib import Path

from .document_storage import make_stored_filename  # noqa: F401 -- Re-Export für Konsistenz
from .paths import data_dir

SKETCH_ROOT = Path(os.getenv("DACHKONZEPTE_ROOF_SKETCH_FILE_ROOT", data_dir() / "roof_area_sketches"))
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # eine gescannte/fotografierte Dachskizze darf größer sein als ein reines Logo


def sketch_directory() -> Path:
    SKETCH_ROOT.mkdir(parents=True, exist_ok=True)
    return SKETCH_ROOT


def sketch_path(stored_filename: str) -> Path:
    return SKETCH_ROOT / stored_filename


def replace_sketch(old_stored_filename: str | None, original_filename: str, data: bytes) -> str:
    """Legt die neue Skizzendatei ab und entfernt die alte (falls vorhanden). Gibt den neuen
    stored_filename zurück, der auf RoofArea.sketch_path gespeichert werden muss."""
    if old_stored_filename:
        sketch_path(old_stored_filename).unlink(missing_ok=True)
    stored = make_stored_filename(original_filename)
    sketch_directory()
    sketch_path(stored).write_bytes(data)
    return stored


def delete_sketch_file(stored_filename: str | None) -> None:
    if stored_filename:
        sketch_path(stored_filename).unlink(missing_ok=True)
