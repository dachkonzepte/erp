"""Hintergrundbild-Ablage für den PDF-Layout-Editor (seit 1.0.61).

Ein Hintergrund pro Dokumenttyp (z.B. der vorgedruckte Briefbogen für
Angebote) -- strukturell wie app/company_logo.py, nur mit einem eigenen
Unterordner je Dokumenttyp statt einer einzigen Datei, und über die
DocumentLayoutBackground-Tabelle statt eines einzelnen Felds verwaltet, da
es (anders als das eine Firmenlogo) mehrere Dokumenttypen geben kann.

Seit 1.3.1 (siehe app/document_frame.py, CLAUDE.md "PDF-Rahmen"): der seitentypbewusste Upload
(GET/POST/DELETE .../backgrounds/{page_type} in routers/document_layout.py) akzeptiert zusätzlich
application/pdf -- reportlab kann keine PDF-Seite direkt zeichnen (drawImage nimmt nur
Rasterbilder), daher wird nur die ERSTE Seite einer hochgeladenen PDF-Datei gerastert
(pypdfium2, reine Wheel-Abhängigkeit ohne externe Poppler-Installation, siehe requirements.txt).
Jede Quelle (PDF-gerastert oder direkt hochgeladenes Bild) wird für diesen Weg einheitlich nach
JPEG normalisiert -- gemessen (siehe CLAUDE.md): ein ganzseitiger fotografischer/körniger
Hintergrund wird als PNG bis zu ~3,7 MB groß, als JPEG q85 nur ~0,9 MB, bei sauberem/flächigem
Briefpapier ist der Unterschied vernachlässigbar. Die ALTE, unveränderte Bild-Upload-Route des
Angebots (replace_background(), weiterhin nur PNG/JPEG/WebP, kein Rastern, keine Normalisierung)
bleibt davon unberührt."""

import io
import os
from pathlib import Path

from PIL import Image as PILImage
import pypdfium2 as pdfium

from .document_storage import make_stored_filename  # noqa: F401 -- Re-Export für Bestandscode/Konsistenz
from .paths import data_dir

BACKGROUND_ROOT = Path(os.getenv("DACHKONZEPTE_LAYOUT_BACKGROUND_ROOT", data_dir() / "document_layout_backgrounds"))
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # ein gescannter/exportierter Briefbogen darf größer sein als ein reines Logo

RASTER_DPI = 200  # ausreichend für Druck, siehe Messung in CLAUDE.md -- JPEG statt PNG loest das
                  # Groessenproblem wirksamer als eine niedrigere Aufloesung
A4_ASPECT_RATIO = 210 / 297  # Hochformat, Breite/Höhe
ASPECT_RATIO_TOLERANCE = 0.02  # 2% -- laesst Scan-Ungenauigkeit zu, faengt US-Letter (~9%) o.ae. ab


def background_directory() -> Path:
    BACKGROUND_ROOT.mkdir(parents=True, exist_ok=True)
    return BACKGROUND_ROOT


def background_path(stored_filename: str) -> Path:
    return BACKGROUND_ROOT / stored_filename


def replace_background(old_stored_filename: str | None, original_filename: str, data: bytes) -> str:
    """Legt die neue Hintergrunddatei ab und entfernt die alte (falls
    vorhanden). Gibt den neuen stored_filename zurück."""
    if old_stored_filename:
        background_path(old_stored_filename).unlink(missing_ok=True)
    stored = make_stored_filename(original_filename)
    background_directory()
    background_path(stored).write_bytes(data)
    return stored


def delete_background_file(stored_filename: str | None) -> None:
    if stored_filename:
        background_path(stored_filename).unlink(missing_ok=True)


def _encode_jpeg(image: PILImage.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


def convert_pdf_first_page_to_image(data: bytes, *, dpi: int = RASTER_DPI) -> bytes:
    """Rendert Seite 0 einer hochgeladenen PDF-Datei zu JPEG-Bytes (seit 1.3.1). Nur die erste
    Seite wird verwendet -- unterschiedliches Briefpapier für Seite 1/Folgeseiten kommt aus zwei
    getrennt hochgeladenen Dateien (siehe app/document_frame.py), kein automatisches Aufteilen
    einer mehrseitigen PDF."""
    pdf = pdfium.PdfDocument(data)
    try:
        image = pdf[0].render(scale=dpi / 72).to_pil()
    finally:
        pdf.close()
    return _encode_jpeg(image)


def validate_a4_aspect_ratio(width: int, height: int) -> None:
    """Lehnt ein Seitenverhältnis ab, das deutlich von A4-Hochformat (210:297) abweicht -- sonst
    würde document_frame.py es (wenn auch verzerrungsfrei skaliert statt gestreckt, siehe dort)
    sichtbar falsch proportioniert zeichnen. 2% Toleranz lässt normale Scan-Ungenauigkeit zu,
    fängt aber z. B. US-Letter (8,5:11, ~9% Abweichung) oder ein Querformat-Bild zuverlässig ab."""
    ratio = width / height
    deviation = abs(ratio - A4_ASPECT_RATIO) / A4_ASPECT_RATIO
    if deviation > ASPECT_RATIO_TOLERANCE:
        raise ValueError(
            "Das Bild/PDF hat kein A4-Hochformat (Seitenverhältnis 210:297) -- bitte eine Datei "
            "verwenden, die für DIN A4 hochkant erstellt wurde."
        )


def prepare_background_upload(data: bytes, content_type: str, *, dpi: int = RASTER_DPI) -> bytes:
    """Gemeinsamer Weg für den seitentypbewussten Hintergrund-Upload (seit 1.3.1, siehe
    POST .../backgrounds/{page_type} in routers/document_layout.py): eine PDF-Datei wird über
    convert_pdf_first_page_to_image() gerastert, ein direkt hochgeladenes Bild wird ebenso nach
    JPEG normalisiert -- beide Quellen laufen danach durch dieselbe Seitenverhältnis-Prüfung.
    Wirft ValueError bei zu starker Abweichung von A4 (siehe validate_a4_aspect_ratio()). Die
    alte, unveränderte Bild-Upload-Route des Angebots (replace_background()) durchläuft das
    bewusst NICHT -- kein neues Verhalten am produktiv genutzten Angebots-Layout."""
    if content_type == "application/pdf":
        jpeg_bytes = convert_pdf_first_page_to_image(data, dpi=dpi)
    else:
        with PILImage.open(io.BytesIO(data)) as im:
            jpeg_bytes = _encode_jpeg(im)
    with PILImage.open(io.BytesIO(jpeg_bytes)) as im:
        validate_a4_aspect_ratio(im.width, im.height)
    return jpeg_bytes
