"""Gemeinsamer Bild-Speicherhelfer (seit 1.8.1).

Vorher existierte dieselbe Pillow-Verkleinerung zweimal fest an einen Zielordner gebunden
(app/service_report_photos.py::resize_and_store_photo(), app/property_documents.py::
_store_uploaded_file()) -- für die Checklisten sollte keine dritte Kopie entstehen (Befund
docs/archiv/modul-checklisten.md). Dieser Helfer nimmt den Zielordner als Argument;
resize_and_store_photo() delegiert seither hierher, mit unverändertem Verhalten.
property_documents.py bleibt bewusst unangetastet (verzweigt zusätzlich nach Dokument vs. Bild,
eigener Umbau ohne Anlass).

CPU-gebunden und synchron -- nur aus gewöhnlichen `def`-Routen aufrufen (Starlette-Threadpool),
nie direkt aus `async def` (Befund 1.3.62: blockiert sonst einen der beiden gunicorn-Worker)."""

import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

MAX_DIMENSION = 1600  # längste Kante nach der Verkleinerung
JPEG_QUALITY = 82


def resize_and_store_jpeg(directory: Path, data: bytes, *, max_dimension: int = MAX_DIMENSION) -> str:
    """Öffnet mit Pillow, wendet die EXIF-Rotation an, verkleinert auf max_dimension und
    speichert einheitlich als JPEG in `directory` (wird angelegt). Gibt den gespeicherten
    Dateinamen zurück. Wirft bei nicht dekodierbaren Daten die Pillow-Ausnahme weiter -- der
    Aufrufer übersetzt sie in eine verständliche Meldung."""
    image = Image.open(BytesIO(data))
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.thumbnail((max_dimension, max_dimension))
    directory.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.jpg"
    image.save(directory / stored, format="JPEG", quality=JPEG_QUALITY)
    return stored


def store_png(directory: Path, data: bytes, *, max_dimension: int = MAX_DIMENSION) -> str:
    """Für Unterschriften (Canvas-PNG mit Transparenz): prüft per Pillow, dass es wirklich ein
    Bild ist, verkleinert bei Bedarf und speichert als PNG -- Transparenz bleibt erhalten."""
    image = Image.open(BytesIO(data))
    image.load()
    if image.mode not in ("RGBA", "RGB", "LA", "L"):
        image = image.convert("RGBA")
    image.thumbnail((max_dimension, max_dimension))
    directory.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.png"
    image.save(directory / stored, format="PNG")
    return stored
