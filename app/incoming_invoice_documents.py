"""Beleg-Ablage für Eingangsrechnungen (Buchhaltung Stufe 1) -- EIN Beleg je Rechnung,
1:1-Muster wie app/operational_asset_documents.py's ursprünglicher Prüffristen-Teil
(replace_document()/delete_document_file(), ersetzt immer die vorherige Datei) statt der
Mehrfachdatei-Ablage bei Betriebsmittel-/Kostenposten-Dokumenten -- eine Eingangsrechnung hat
fachlich genau einen Beleg, kein Dokumenttyp-Katalog nötig."""

import os
from pathlib import Path

from .document_storage import make_stored_filename
from .paths import data_dir

DOCUMENT_ROOT = Path(os.getenv("DACHKONZEPTE_INCOMING_INVOICE_FILE_ROOT", data_dir() / "incoming_invoice_documents"))
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


def document_directory() -> Path:
    DOCUMENT_ROOT.mkdir(parents=True, exist_ok=True)
    return DOCUMENT_ROOT


def document_path(stored_filename: str) -> Path:
    return DOCUMENT_ROOT / stored_filename


def replace_document(old_stored_filename: str | None, original_filename: str, data: bytes) -> str:
    """Legt den neuen Beleg ab und entfernt den alten (falls vorhanden). Gibt den neuen
    stored_filename zurück, der auf IncomingInvoice.document_filename gespeichert werden muss."""
    if old_stored_filename:
        document_path(old_stored_filename).unlink(missing_ok=True)
    stored = make_stored_filename(original_filename)
    document_directory()
    document_path(stored).write_bytes(data)
    return stored


def delete_document_file(stored_filename: str | None) -> None:
    if stored_filename:
        document_path(stored_filename).unlink(missing_ok=True)
