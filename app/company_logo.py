"""Firmenlogo-Ablage (seit 1.0.58, Grundlage für den PDF-Layout-Editor).

Bewusst denkbar einfach gehalten: es gibt genau ein Logo für die ganze
Firma (nicht pro Dokumenttyp), gespeichert unter einem festen Namen im
eigenen Ordner. Ein neuer Upload ersetzt den alten -- die alte Datei wird
dabei entfernt, damit sich keine verwaisten Logo-Dateien ansammeln.
"""

import os
from pathlib import Path

from sqlalchemy.orm import Session

from .document_storage import make_stored_filename
from .paths import data_dir
from .settings import get_or_create_general_settings

LOGO_ROOT = Path(os.getenv("DACHKONZEPTE_LOGO_FILE_ROOT", data_dir() / "company_logo"))
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB reicht für ein Logo bei weitem, verhindert versehentliche Großuploads


def logo_directory() -> Path:
    LOGO_ROOT.mkdir(parents=True, exist_ok=True)
    return LOGO_ROOT


def logo_path(stored_filename: str) -> Path:
    return LOGO_ROOT / stored_filename


def replace_logo(old_stored_filename: str | None, original_filename: str, data: bytes) -> str:
    """Legt die neue Logo-Datei ab und entfernt die alte (falls vorhanden).
    Gibt den neuen stored_filename zurück, der auf GeneralSettings.logo_filename
    gespeichert werden muss."""
    if old_stored_filename:
        logo_path(old_stored_filename).unlink(missing_ok=True)
    stored = make_stored_filename(original_filename)
    logo_directory()
    logo_path(stored).write_bytes(data)
    return stored


def delete_logo(stored_filename: str | None) -> None:
    if stored_filename:
        logo_path(stored_filename).unlink(missing_ok=True)


def sidebar_logo_filename(db: Session) -> str | None:
    """Liefert den stored_filename des Logos, das die Sidebar (_sidebar.html) zeigen soll --
    heute immer das eine Firmenlogo (GeneralSettings.logo_filename), da es dafür (noch) keinen
    eigenen, zweiten Upload gibt (siehe CLAUDE.md "Firmenlogo in der Sidebar"). Bewusst eine
    eigene Funktion statt GeneralSettings.logo_filename direkt an der Aufrufstelle zu lesen:
    ein späterer, dedizierter Sidebar-Logo-Upload müsste dann nur hier umgestellt werden, nicht
    an jeder Stelle, die die Sidebar-Logo-Datei braucht. Prüft zusätzlich, ob die Datei
    tatsächlich noch auf der Platte liegt (dieselbe Vorsicht wie view_company_logo()) -- ein
    Datenbankeintrag ohne Datei soll zum Schriftzug zurückfallen, nicht zu einem defekten Bild."""
    settings = get_or_create_general_settings(db)
    if not settings.logo_filename:
        return None
    if not logo_path(settings.logo_filename).is_file():
        return None
    return settings.logo_filename
