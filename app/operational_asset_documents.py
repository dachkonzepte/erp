"""Dokument-Ablage für Betriebsmittel-Prüffristen UND, seit 1.4.2, für die allgemeine
Betriebsmittel-Dokumentenablage (Modul "betriebsmittel").

Zwei Verwendungen, EIN Ordner (DOCUMENT_ROOT): das ursprüngliche, 1:1-Muster je Prüffrist
(replace_document()/delete_document_file(), strukturell wie app/roof_area_sketches.py -- ein
Beleg je Fremdschlüssel, ersetzt immer die vorherige Datei) UND, seit 1.4.2, save_document()
für die unabhängige, mehrere Dateien je Betriebsmittel erlaubende Ablage
(OperationalAssetDocument, siehe app/models.py) -- ersetzt NIE eine vorhandene Datei, jeder
Aufruf legt eine neue, eigenständige Zeile an. delete_document_file() bleibt für beide
Verwendungen dieselbe, bereits bestehende Funktion. Anders als bei der Skizze sind hier neben
Bildern zusätzlich PDF-Dokumente üblich (TÜV-Bericht, Anschaffungsrechnung, Leasingvertrag)."""

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


def save_document(original_filename: str, data: bytes) -> str:
    """Legt ein neues, UNABHÄNGIGES Dokument ab -- anders als replace_document() (1:1 je
    Prüffrist) wird nie eine vorhandene Datei ersetzt/gelöscht: die allgemeine Betriebsmittel-
    Dokumentenablage (OperationalAssetDocument, seit 1.4.2) erlaubt mehrere unabhängige
    Dateien je Betriebsmittel (Anschaffungsrechnung UND Leasingvertrag UND ...)."""
    stored = make_stored_filename(original_filename)
    document_directory()
    document_path(stored).write_bytes(data)
    return stored
