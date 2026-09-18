"""Dokument-Ablage für Kostenposten der Betriebskosten-Übersicht (Modul "betriebskosten",
seit 1.5.0) -- Muster app/operational_asset_documents.py::save_document()/
delete_document_file(): ausschließlich die unabhängige, mehrere Dateien je Kostenposten
erlaubende Ablage (RecurringCostDocument, siehe app/models.py), kein 1:1-Ersetzungsfall wie bei
Prüffristen nötig."""

import os
from pathlib import Path

from .document_storage import make_stored_filename  # noqa: F401 -- Re-Export für Konsistenz
from .paths import data_dir

DOCUMENT_ROOT = Path(os.getenv("DACHKONZEPTE_RECURRING_COST_FILE_ROOT", data_dir() / "recurring_cost_documents"))
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


def document_directory() -> Path:
    DOCUMENT_ROOT.mkdir(parents=True, exist_ok=True)
    return DOCUMENT_ROOT


def document_path(stored_filename: str) -> Path:
    return DOCUMENT_ROOT / stored_filename


def save_document(original_filename: str, data: bytes) -> str:
    """Legt ein neues, unabhängiges Dokument ab -- ersetzt nie eine vorhandene Datei, ein
    Kostenposten kann beliebig viele Dokumente tragen (Vertrag UND Rechnung UND
    Kündigungsschreiben UND ...)."""
    stored = make_stored_filename(original_filename)
    document_directory()
    document_path(stored).write_bytes(data)
    return stored


def delete_document_file(stored_filename: str | None) -> None:
    if stored_filename:
        document_path(stored_filename).unlink(missing_ok=True)
