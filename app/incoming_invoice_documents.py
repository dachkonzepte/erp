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


def store_document(original_filename: str, data: bytes) -> str:
    """Legt einen neuen Beleg ab und gibt seinen stored_filename zurück (für IncomingInvoice.document_filename). Seit 1.9.238 (Stufe 6, R3b,
    Punkt 0a) löscht sie den alten nicht mehr selbst (bis 1.9.237 replace_document()): den alten löscht app/incoming_invoices.py::
    set_invoice_document() erst nach dem Commit -- scheitert das Speichern, bleibt der alte Beleg stehen."""
    stored = make_stored_filename(original_filename)
    document_directory()
    document_path(stored).write_bytes(data)
    return stored


def delete_document_file(stored_filename: str | None) -> None:
    if stored_filename:
        document_path(stored_filename).unlink(missing_ok=True)
