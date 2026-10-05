"""Prüfung eines gezeichneten Unterschriftsbilds (seit 1.8.56, Stufe 2c-2c, Punkt 2) -- eine für jeden Unterschrift-Weg.

Gezeichnet wird überall auf derselben Fläche (app/templates/_unterschrift.html), das Bild kommt als PNG. Bis 1.8.55 prüfte
jeder Weg anders: der Vertrag auf dem Gerät auf PNG und "nicht leer" (seit 1.8.34), die Checkliste nur, ob Pillow es öffnen
kann (jedes Bildformat, auch ein leeres), der Einsatzbericht nur die Größe -- er schrieb die Bytes ungeprüft auf die Platte.
Jetzt rufen alle drei check_signature_png() auf, bevor etwas gespeichert wird:

- Checkliste: app/checklists.py::add_attachment() (Feldtyp "unterschrift"),
- Einsatzbericht: app/service_reports.py::sign_report() (Monteur und Kunde),
- Vertrag auf dem Gerät: app/contract_signatures.py::sign_contract_on_device() (Kunde und Betrieb).

Der Papier-Scan eines Vertrags ist kein gezeichnetes Bild (geprüft als Beleg, PDF oder Foto). tests/test_v358_unterschrift_
pruefung.py prüft per AST, dass jede Stelle, die ein Unterschriftsbild speichert, diese Prüfung aufruft, und ordnet jede Spalte
ein, deren Name nach Unterschrift klingt -- ein neuer Weg fällt dort auf.

Geprüft wird: vorhanden, höchstens 2 MB, ein PNG (am Inhalt erkannt, von Pillow vollständig gelesen), höchstens
MAX_SIGNATURE_EDGE Pixel je Kante und MAX_SIGNATURE_PIXELS insgesamt (ein kleines PNG kann sich zu einem riesigen Bild
entpacken -- Speicherbudget des 4-GB-Servers), und nicht leer: bei durchsichtigem Hintergrund (Zeichenfläche) ein sichtbares
Pixel, bei deckendem Hintergrund ein dunkles. Fehler als ValueError mit verständlichem Text -- die Router antworten 400.

CPU-gebunden und synchron (Pillow) -- nur aus gewöhnlichen def-Routen aufrufen (Befund 1.3.62)."""

import base64
import binascii
from io import BytesIO

MAX_SIGNATURE_PNG_BYTES = 2 * 1024 * 1024
MAX_SIGNATURE_EDGE = 5000  # Pixel je Kante -- die Fläche ist höchstens Bildschirmbreite mal Geräteauflösung
MAX_SIGNATURE_PIXELS = 12_000_000


def has_ink(image) -> bool:
    """Ob auf dem Bild etwas gezeichnet ist: bei durchsichtigem Hintergrund (Zeichenfläche) ein sichtbares Pixel, bei
    deckendem Hintergrund ein dunkles."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] == 255:
        return rgba.convert("L").getextrema()[0] < 160
    return alpha.point(lambda a: 255 if a > 32 else 0).getbbox() is not None


def check_signature_png(data: bytes, who: str) -> bytes:
    """Prüft ein gezeichnetes Unterschriftsbild (siehe Modulbeschreibung) und gibt die Bytes unverändert zurück. `who`
    ergänzt die Meldung ("des Kunden", "für den Betrieb", "in „Unterschrift Brandwache“"). Wirft ValueError."""
    from PIL import Image, UnidentifiedImageError

    if not data:
        raise ValueError(f"Bitte {who} unterschreiben.")
    if len(data) > MAX_SIGNATURE_PNG_BYTES:
        raise ValueError(f"Die Unterschrift {who} ist zu groß (höchstens {MAX_SIGNATURE_PNG_BYTES // (1024 * 1024)} MB).")
    fmt, ink, too_big = None, False, False
    try:
        with Image.open(BytesIO(data)) as image:
            fmt = image.format
            width, height = image.size
            too_big = width > MAX_SIGNATURE_EDGE or height > MAX_SIGNATURE_EDGE or width * height > MAX_SIGNATURE_PIXELS
            if fmt == "PNG" and not too_big:
                image.load()
                ink = has_ink(image)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        fmt, ink = None, False
    if fmt != "PNG":
        raise ValueError(f"Die Unterschrift {who} ist kein gültiges PNG.")
    if too_big:
        raise ValueError(f"Die Unterschrift {who} ist zu groß (höchstens {MAX_SIGNATURE_EDGE} Pixel je Seite).")
    if not ink:
        raise ValueError(f"Die Unterschrift {who} ist leer – bitte im Feld unterschreiben.")
    return data


def signature_png_from_base64(raw: str | None) -> bytes:
    """Das Bild aus dem JSON einer Unterschrift (Data-URL oder reines Base64) -- ValueError, wenn es kein Base64 ist. Die
    Prüfung des Bilds selbst macht check_signature_png()."""
    raw = (raw or "").strip()
    if raw.lower().startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Ungültige Unterschrift (kein gültiges Base64-PNG).") from exc
