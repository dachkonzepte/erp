"""Firmenlogo- und Sidebar-Logo-Ablage (Firmenlogo seit 1.0.58, Sidebar-Logo seit 1.3.43).

Zwei unabhängige, ansonsten baugleiche Uploads:

- **Firmenlogo** (`LOGO_ROOT`, `GeneralSettings.logo_filename`) -- für PDF-Dokumente
  (`document_frame.py`) und das PWA-Startbildschirm-Icon der Monteursansicht
  (`mobile_manifest.py`); beide lesen die Originaldatei direkt von der Platte, volle Auflösung
  zählt dort tatsächlich.
- **Sidebar-Logo** (`SIDEBAR_LOGO_ROOT`, `GeneralSettings.sidebar_logo_filename`) --
  ausschließlich für `_sidebar.html`. Nötig geworden, weil das echte Firmenlogo einen
  Schriftzug enthält ("DACHKONZEPTE GmbH"/"RÖDCHEN" unterhalb des Dachzeichens), der in der
  schmalen Sidebar bei keiner erlaubten Höhe (24-80px) mehr lesbar wäre -- eine ursprünglich
  (1.3.39) per Bounding-Box-Auswertung des Alphakanals gestellte Fehldiagnose ("kein
  Schriftzug vorhanden") wurde dadurch entdeckt, dass Text und Bildzeichen räumlich zu nah
  beieinander liegen, um automatisiert getrennt zu werden -- ein Betreiber kann hier stattdessen
  von Hand eine eigene, reduzierte Variante hinterlegen (z. B. nur das Bildzeichen).

`sidebar_logo_filename()` löst daraus auf, was `_sidebar.html` tatsächlich zeigen soll, in
dieser Rangfolge: (1) das Sidebar-Logo, falls hinterlegt, (2) sonst das Firmenlogo, (3) sonst
der Schriftzug (`None` -- der eigentliche Rückfall bleibt in `_sidebar.html`). Beide Uploads
teilen sich dieselbe Speicher-/Validierungslogik (`root`-Parameter unten) -- nur Ablageordner
und `GeneralSettings`-Spalte unterscheiden sich.

Anzeige-Rendition (seit 1.3.39, gilt seither für beide Logos): ein real hochgeladenes Firmenlogo
kam mit 8000x5295px/252KB daher -- für die Sidebar auf 24-80px Höhe herunterskaliert, lädt und
dekodiert der Browser bei JEDER Seitenanfrage trotzdem die vollen 42 Megapixel (dieses Projekt
macht ausschließlich klassische Mehrseiten-Navigation, keine SPA -- die Sidebar wird also bei
jedem Klick neu angefordert). `replace_logo()`/`replace_sidebar_logo()` erzeugen deshalb
zusätzlich zur Originaldatei (fürs Firmenlogo weiterhin unverändert wichtig für PDFs/das
PWA-Icon) eine verkleinerte Anzeige-Rendition -- die jeweilige GET-Route liefert bevorzugt
diese, fällt aber auf das Original zurück, wenn keine Rendition existiert (SVG -- dort unnötig,
da bereits vektoriell/klein -- oder ein Upload ohne erfolgreiche Rendition-Erzeugung)."""

import os
from io import BytesIO
from pathlib import Path
from typing import NamedTuple

from PIL import Image
from sqlalchemy.orm import Session

from .document_storage import make_stored_filename
from .paths import data_dir
from .settings import get_or_create_general_settings

LOGO_ROOT = Path(os.getenv("DACHKONZEPTE_LOGO_FILE_ROOT", data_dir() / "company_logo"))
SIDEBAR_LOGO_ROOT = Path(os.getenv("DACHKONZEPTE_SIDEBAR_LOGO_FILE_ROOT", data_dir() / "sidebar_logo"))
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB reicht für ein Logo bei weitem, verhindert versehentliche Großuploads
MAX_DISPLAY_DIMENSION = 480  # längste Kante der Anzeige-Rendition -- reicht für 80px CSS-Höhe
# selbst auf einem 3x-Retina-Bildschirm bequem aus, ohne bei einem quadratischen/breiten Logo
# unnötig groß zu werden

# Anzeigehöhe des in der Sidebar gezeigten Logos (seit 1.3.39) -- gilt unabhängig davon, ob
# tatsächlich das Sidebar-Logo oder ersatzweise das Firmenlogo gezeigt wird (siehe
# sidebar_logo_filename() unten), einstellbar, damit ein kleines Bildzeichen größer dargestellt
# werden kann, ohne dass der Betreiber dafür Code ändern lassen muss.
DEFAULT_SIDEBAR_LOGO_HEIGHT_PX = 48
MIN_SIDEBAR_LOGO_HEIGHT_PX = 24
MAX_SIDEBAR_LOGO_HEIGHT_PX = 80


def logo_directory(root: Path | None = None) -> Path:
    # root=None (statt root: Path = LOGO_ROOT als Vorgabewert) ist bewusst so gewaehlt: ein
    # Vorgabewert wird einmalig bei der Modul-Definition gebunden, nicht bei jedem Aufruf neu
    # gelesen -- ein in Tests per monkeypatch.setattr(company_logo, "LOGO_ROOT", ...) geaenderter
    # Wert wuerde von einem echten Vorgabewert nie gesehen. Erst die Aufloesung HIER, im
    # Funktionskoerper, liest LOGO_ROOT bei jedem Aufruf frisch als Modul-Global.
    if root is None:
        root = LOGO_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def logo_path(stored_filename: str, root: Path | None = None) -> Path:
    if root is None:
        root = LOGO_ROOT
    return root / stored_filename


def _display_stored_filename(stored_filename: str) -> str:
    return f"{Path(stored_filename).stem}_display.png"


def display_logo_path(stored_filename: str, root: Path | None = None) -> Path:
    if root is None:
        root = LOGO_ROOT
    return root / _display_stored_filename(stored_filename)


def _generate_display_rendition(stored_filename: str, data: bytes, root: Path | None = None) -> None:
    """Erzeugt (falls möglich) eine verkleinerte Anzeige-Rendition neben der Originaldatei --
    für SVG (bereits vektoriell/klein) oder falls Pillow das Format nicht öffnen kann, bewusst
    KEINE Rendition: die jeweilige GET-Route fällt dann auf das Original zurück, statt den
    Upload an einem Rendition-Fehler scheitern zu lassen (ein etwas größeres Original ist besser
    als ein fehlgeschlagener Upload)."""
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
    display_logo_path(stored_filename, root).write_bytes(_encode_png(image))


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


def replace_logo(old_stored_filename: str | None, original_filename: str, data: bytes, root: Path | None = None) -> str:
    """Legt die neue Logo-Datei ab und entfernt die alte (falls vorhanden). Gibt den neuen
    stored_filename zurück. Gemeinsame Implementierung für Firmenlogo (Standard, `root=None` ->
    `LOGO_ROOT`, Ergebnis auf `GeneralSettings.logo_filename` gespeichert) und Sidebar-Logo
    (siehe replace_sidebar_logo() unten, Ergebnis auf `GeneralSettings.sidebar_logo_filename`)."""
    if old_stored_filename:
        delete_logo(old_stored_filename, root)
    stored = make_stored_filename(original_filename)
    logo_directory(root)
    logo_path(stored, root).write_bytes(data)
    _generate_display_rendition(stored, data, root)
    return stored


def delete_logo(stored_filename: str | None, root: Path | None = None) -> None:
    if stored_filename:
        logo_path(stored_filename, root).unlink(missing_ok=True)
        display_logo_path(stored_filename, root).unlink(missing_ok=True)


def replace_sidebar_logo(old_stored_filename: str | None, original_filename: str, data: bytes) -> str:
    """Wie replace_logo(), aber im eigenen Ordner (SIDEBAR_LOGO_ROOT) für das dedizierte
    Sidebar-Logo (seit 1.3.43, siehe Moduldocstring)."""
    return replace_logo(old_stored_filename, original_filename, data, root=SIDEBAR_LOGO_ROOT)


def delete_sidebar_logo(stored_filename: str | None) -> None:
    delete_logo(stored_filename, root=SIDEBAR_LOGO_ROOT)


def sidebar_logo_path(stored_filename: str) -> Path:
    return logo_path(stored_filename, root=SIDEBAR_LOGO_ROOT)


def sidebar_logo_display_path(stored_filename: str) -> Path:
    return display_logo_path(stored_filename, root=SIDEBAR_LOGO_ROOT)


class SidebarLogoReference(NamedTuple):
    """Ergebnis von sidebar_logo_filename() (seit 1.3.43): sagt dem Aufrufer nicht nur WELCHE
    Datei zu zeigen ist, sondern auch AUS WELCHEM Ordner/über welchen Endpunkt -- Sidebar-Logo
    und Firmenlogo liegen in getrennten Ordnern hinter getrennten Auslieferungsrouten
    (GET /api/settings/general/sidebar-logo bzw. .../logo)."""
    source: str  # "sidebar" oder "company"
    stored_filename: str


def sidebar_logo_filename(db: Session) -> SidebarLogoReference | None:
    """Liefert, welches Logo _sidebar.html oben links zeigen soll, in dieser Rangfolge (seit
    1.3.43, siehe CLAUDE.md "Firmenlogo in der Sidebar"): (1) das eigene Sidebar-Logo, falls
    hinterlegt UND die Datei tatsächlich noch auf der Platte liegt, (2) sonst das Firmenlogo
    unter derselben Bedingung, (3) sonst None (Rückfall auf den Schriftzug in _sidebar.html --
    eine leere Stelle wäre schlechter als Text). Ein Datenbankeintrag ohne zugehörige Datei
    fällt auf die nächste Stufe zurück, statt zu einem defekten <img> zu führen.

    Vor 1.3.43 zeigte die Sidebar immer das Firmenlogo (kein eigener Upload) -- das erwies sich
    als unzureichend: das echte Firmenlogo enthält einen Schriftzug ("DACHKONZEPTE GmbH"/
    "RÖDCHEN" unter dem Dachzeichen), der in der schmalen Sidebar bei keiner erlaubten Höhe
    mehr lesbar ist."""
    settings = get_or_create_general_settings(db)
    if settings.sidebar_logo_filename and sidebar_logo_path(settings.sidebar_logo_filename).is_file():
        return SidebarLogoReference("sidebar", settings.sidebar_logo_filename)
    if settings.logo_filename and logo_path(settings.logo_filename).is_file():
        return SidebarLogoReference("company", settings.logo_filename)
    return None


def sidebar_logo_height_px(db: Session) -> int:
    """Liefert die eingestellte Anzeigehöhe des Sidebar-Logos in Pixeln (Einstellungen ->
    Unternehmensstammdaten, Feld direkt neben dem Logo-Upload) -- auf den erlaubten Bereich
    geklammert, falls der gespeicherte Wert (z. B. durch einen direkten Datenbankzugriff)
    außerhalb liegt."""
    settings = get_or_create_general_settings(db)
    height = settings.sidebar_logo_height_px or DEFAULT_SIDEBAR_LOGO_HEIGHT_PX
    return max(MIN_SIDEBAR_LOGO_HEIGHT_PX, min(MAX_SIDEBAR_LOGO_HEIGHT_PX, height))
