"""Dokument-Ablage für Betriebsmittel-Prüffristen (seit 1.4.0, Modul "betriebsmittel").

Ein Dokument pro Prüffrist -- strukturell wie app/roof_area_sketches.py (ein Beleg je
Fremdschlüssel, kein Dokumentenmanagement mit Kategorien/Unterordnern/mehreren Dateien wie
bei project_documents.py/customer_documents.py). Anders als bei der Skizze sind hier neben
Bildern zusätzlich PDF-Prüfprotokolle üblich (TÜV-Bericht, Prüfplakette-Foto)."""

import os
from pathlib import Path

from .document_storage import make_stored_filename  # noqa: F401 -- Re-Export für Konsistenz
from .paths import data_dir

DOCUMENT_ROOT = Path(os.getenv("DACHKONZEPTE_OPERATIONAL_ASSET_FILE_ROOT", data_dir() / "operational_asset_documents"))
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


def document_directory() -> Path:
    DOCUMENT_ROOT.mkdir(parents=True, exist_ok=True)
    return DOCUMENT_ROOT


def document_path(stored_filename: str) -> Path:
    return DOCUMENT_ROOT / stored_filename


def replace_document(old_stored_filename: str | None, original_filename: str, data: bytes) -> str:
    """Legt das neue Dokument ab und entfernt das alte (falls vorhanden). Gibt den neuen
    stored_filename zurück, der auf OperationalAssetInspection.document_filename gespeichert
    werden muss."""
    if old_stored_filename:
        document_path(old_stored_filename).unlink(missing_ok=True)
    stored = make_stored_filename(original_filename)
    document_directory()
    document_path(stored).write_bytes(data)
    return stored


def delete_document_file(stored_filename: str | None) -> None:
    if stored_filename:
        document_path(stored_filename).unlink(missing_ok=True)
