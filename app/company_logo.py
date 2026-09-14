"""Firmenlogo-Ablage (seit 1.0.58, Grundlage für den PDF-Layout-Editor).

Bewusst denkbar einfach gehalten: es gibt genau ein Logo für die ganze
Firma (nicht pro Dokumenttyp), gespeichert unter einem festen Namen im
eigenen Ordner. Ein neuer Upload ersetzt den alten -- die alte Datei wird
dabei entfernt, damit sich keine verwaisten Logo-Dateien ansammeln.

Anzeige-Rendition (seit 1.3.39): ein real hochgeladenes Logo kam mit 8000x5295px/252KB daher --
für die Sidebar auf 24-80px Höhe herunterskaliert, lädt und dekodiert der Browser bei JEDER
Seitenanfrage trotzdem die vollen 42 Megapixel (dieses Projekt macht ausschließlich klassische
Mehrseiten-Navigation, keine SPA -- die Sidebar wird also bei jedem Klick neu angefordert).
replace_logo() erzeugt deshalb zusätzlich zur Originaldatei (unverändert für PDFs/das PWA-Icon,
die beide direkt von der Platte lesen, siehe document_frame.py/mobile_manifest.py) eine
verkleinerte Anzeige-Rendition -- GET .../logo (der einzige HTTP-Auslieferungsweg, von Sidebar
UND Einstellungen-Vorschau genutzt) liefert bevorzugt diese, fällt aber auf das Original
zurück, wenn keine Rendition existiert (SVG -- dort unnötig, da bereits vektoriell/klein -- oder
ein vor 1.3.39 hochgeladenes Logo ohne nachträgliche Regenerierung)."""

import os
from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from .document_storage import make_stored_filename
from .paths import data_dir
from .settings import get_or_create_general_settings

LOGO_ROOT = Path(os.getenv("DACHKONZEPTE_LOGO_FILE_ROOT", data_dir() / "company_logo"))
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB reicht für ein Logo bei weitem, verhindert versehentliche Großuploads
MAX_DISPLAY_DIMENSION = 480  # längste Kante der Anzeige-Rendition -- reicht für 80px CSS-Höhe
# selbst auf einem 3x-Retina-Bildschirm bequem aus, ohne bei einem quadratischen/breiten Logo
# unnötig groß zu werden

# Anzeigehöhe des Sidebar-Logos (seit 1.3.39) -- einstellbar, damit ein Logo mit kleinem
# Bildzeichen samt Schriftzug darunter (in einer schmalen Sidebar sonst schnell unleserlich)
# größer dargestellt werden kann, ohne dass der Betreiber dafür Code ändern lassen muss.
DEFAULT_SIDEBAR_LOGO_HEIGHT_PX = 48
MIN_SIDEBAR_LOGO_HEIGHT_PX = 24
MAX_SIDEBAR_LOGO_HEIGHT_PX = 80


def logo_directory() -> Path:
    LOGO_ROOT.mkdir(parents=True, exist_ok=True)
    return LOGO_ROOT


def logo_path(stored_filename: str) -> Path:
    return LOGO_ROOT / stored_filename


def _display_stored_filename(stored_filename: str) -> str:
    return f"{Path(stored_filename).stem}_display.png"


def display_logo_path(stored_filename: str) -> Path:
    return LOGO_ROOT / _display_stored_filename(stored_filename)


def _generate_display_rendition(stored_filename: str, data: bytes) -> None:
    """Erzeugt (falls möglich) eine verkleinerte Anzeige-Rendition neben der Originaldatei --
    für SVG (bereits vektoriell/klein) oder falls Pillow das Format nicht öffnen kann, bewusst
    KEINE Rendition: view_company_logo() fällt dann auf das Original zurück, statt den Upload
    an einem Rendition-Fehler scheitern zu lassen (ein etwas größeres Original ist besser als
    ein fehlgeschlagener Upload)."""
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception:
        return
    if image.mode not in ("RGBA", "RGB", "LA", "L"):
        image = image.convert("RGBA")  # deckt u. a. Palette-PNGs (Modus "P") ab, Pillow löst
        # eine dort ggf. vorhandene Transparenz beim Konvertieren korrekt in einen echten
        # Alphakanal auf
    image.thumbnail((MAX_DISPLAY_DIMENSION, MAX_DISPLAY_DIMENSION), Image.LANCZOS)
    display_logo_path(stored_filename).write_bytes(_encode_png(image))


def _encode_png(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def validate_logo_image(content_type: str | None, data: bytes) -> None:
    """Prüft VOR jeder Persistierung, dass eine hochgeladene Rasterdatei tatsächlich ein von
    Pillow dekodierbares Bild ist -- der vom Client mitgeschickte content_type ist nur ein
    Hinweis (frei wählbar, kein verlässlicher Nachweis des tatsächlichen Dateiinhalts). SVG wird
    bewusst ausgenommen: Pillow kann SVG grundsätzlich nicht öffnen, das ist dort kein Fehler,
    kein Dateiformatproblem. Muss vom Aufrufer VOR replace_logo()/vor dem Setzen von
    GeneralSettings.logo_filename/vor db.commit() aufgerufen werden -- ein fehlgeschlagener
    Upload darf keine Datenbankzeile auf eine nie gespeicherte oder unbrauchbare Datei zeigen
    lassen (siehe CLAUDE.md "Firmenlogo in der Sidebar", Fehlerbehebung)."""
    if (content_type or "").lower() == "image/svg+xml":
        return
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception as exc:
        raise ValueError(f"Ungültiges Bild: {exc}") from exc


def replace_logo(old_stored_filename: str | None, original_filename: str, data: bytes) -> str:
    """Legt die neue Logo-Datei ab und entfernt die alte (falls vorhanden).
    Gibt den neuen stored_filename zurück, der auf GeneralSettings.logo_filename
    gespeichert werden muss."""
    if old_stored_filename:
        delete_logo(old_stored_filename)
    stored = make_stored_filename(original_filename)
    logo_directory()
    logo_path(stored).write_bytes(data)
    _generate_display_rendition(stored, data)
    return stored


def delete_logo(stored_filename: str | None) -> None:
    if stored_filename:
        logo_path(stored_filename).unlink(missing_ok=True)
        display_logo_path(stored_filename).unlink(missing_ok=True)


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


def sidebar_logo_height_px(db: Session) -> int:
    """Liefert die eingestellte Anzeigehöhe des Sidebar-Logos in Pixeln (Einstellungen ->
    Unternehmensstammdaten, Feld direkt neben dem Logo-Upload) -- auf den erlaubten Bereich
    geklammert, falls der gespeicherte Wert (z. B. durch einen direkten Datenbankzugriff)
    außerhalb liegt."""
    settings = get_or_create_general_settings(db)
    height = settings.sidebar_logo_height_px or DEFAULT_SIDEBAR_LOGO_HEIGHT_PX
    return max(MIN_SIDEBAR_LOGO_HEIGHT_PX, min(MAX_SIDEBAR_LOGO_HEIGHT_PX, height))
