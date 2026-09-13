"""Fotoablage für Einsatzberichte (seit 1.2.17). Vorbild ist app/roof_area_sketches.py
(1.2.14) -- anders als dort aber MEHRERE Dateien je Bericht, deshalb kein 1:1-Ersatzmuster
(kein replace_sketch()), sondern reines Anlegen/Löschen je Foto.

Pillow ist bereits eine über reportlab gezogene Pflichtabhängigkeit (siehe requirements.txt) --
resize_and_store_photo() nutzt sie erstmals explizit, um jedes Foto serverseitig auf eine
handhabbare Größe zu verkleinern, unabhängig davon, was der Client tatsächlich hochlädt."""

import os
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from .paths import data_dir

PHOTO_ROOT = Path(os.getenv("DACHKONZEPTE_SERVICE_REPORT_PHOTO_ROOT", data_dir() / "service_report_photos"))
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # Rohdatei vor der Verkleinerung -- Handyfotos sind groß
MAX_DIMENSION = 1600  # längste Kante nach der Verkleinerung
JPEG_QUALITY = 82


def _photo_directory() -> Path:
    PHOTO_ROOT.mkdir(parents=True, exist_ok=True)
    return PHOTO_ROOT


def photo_path(stored_filename: str) -> Path:
    return PHOTO_ROOT / stored_filename


def resize_and_store_photo(original_filename: str, data: bytes) -> str:
    """Öffnet mit Pillow, wendet die EXIF-Rotation an (Handyfotos tragen die Drehung sonst nur
    im Metadaten-Tag, nicht in den Pixeln), verkleinert auf MAX_DIMENSION und speichert
    einheitlich als JPEG -- unabhängig vom Ursprungsformat, damit die Größe eines Berichts mit
    vielen Fotos handhabbar bleibt. Gibt den neuen, gespeicherten Dateinamen zurück (immer .jpg)."""
    image = Image.open(BytesIO(data))
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    stored = f"{uuid.uuid4().hex}.jpg"
    _photo_directory()
    image.save(photo_path(stored), format="JPEG", quality=JPEG_QUALITY)
    return stored


def delete_photo_file(stored_filename: str | None) -> None:
    if stored_filename:
        photo_path(stored_filename).unlink(missing_ok=True)
