"""Prüft das Neukodieren der Fotos für das Kundenportal auf dem Rechner, auf dem es läuft (seit 1.11.33, Stufe P2b; Server-Schritt P2b-4).

Ohne Datenbank, ohne Dateien, schreibt nichts: drei erfundene Bilder, im Speicher erzeugt, gehen durch denselben Kindprozess wie im Postboten
(app/portal_kopien.py::foto_neu_kodieren(), app/portal_foto_kind.py):

    1. ein Foto mit EXIF (samt GPS) und Kommentar      -> ein JPEG ohne APP1–APP15 und ohne Kommentar
    2. eine Dekompressionsbombe (100000 × 100000)      -> „zu_gross“
    3. ein Bild, das die Grenze für Speicher sprengt    -> „abbruch“ (unter Linux greift RLIMIT_AS, unter Windows das Job-Objekt)
    4. Messung (Bauplan P2, B12): ein Foto mit 48 Mio. Bildpunkten (Rauschen, ungünstig groß) -> JPEG; dazu Dauer und unter Linux die Spitze des
       Speichers im Kindprozess (getrusage) -- eine Zeile „Messung: …“, keine Prüfung

Auf dem Server als Benutzer des ERP, im Repo-Ordner:

    cd /home/tobias/erp && .venv/bin/python scripts/pruefe_portal_foto.py

Ausgabe: je Prüfung eine Zeile „ok“ bzw. „!!!“, die Zeile „Messung: …“ und am Ende „alle drei wie erwartet“; Rückgabe 0, sonst 1. Braucht kurz rund
200 MB Speicher für das erfundene große Foto (außerhalb der Grenzen des Postboten).
"""

import io
import struct
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _foto() -> bytes:
    from PIL import Image
    exif = Image.Exif()
    exif[0x010E] = "erfundene Beschreibung"
    exif.get_ifd(0x8825)[1] = "N"
    aus = io.BytesIO()
    Image.new("RGB", (800, 600), "red").save(aus, "JPEG", exif=exif.tobytes(), comment=b"erfundener Kommentar")
    return aus.getvalue()


def _bombe() -> bytes:
    def chunk(art, daten):
        return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 100_000, 100_000, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00" * 1024)) + chunk(b"IEND", b""))


def _gross() -> bytes:
    from PIL import Image
    aus = io.BytesIO()
    Image.new("RGBA", (6000, 6000), (10, 20, 30, 255)).save(aus, "PNG")  # 144 MB entpackt, die Datei klein
    return aus.getvalue()


def _ohne_metadaten(jpeg: bytes) -> bool:
    i = 2
    while i < len(jpeg) and jpeg[i] == 0xFF:
        marker = jpeg[i + 1]
        if marker == 0xDA:
            return True
        if 0xE1 <= marker <= 0xEF or marker == 0xFE:
            return False
        i += 2 + struct.unpack(">H", jpeg[i + 2:i + 4])[0]
    return False


def main(ausgabe=print) -> int:
    from app.portal_kopien import foto_neu_kodieren

    ergebnisse = []
    foto = foto_neu_kodieren(_foto())
    ergebnisse.append(("Foto ohne Metadaten", isinstance(foto, bytes) and _ohne_metadaten(foto)))
    ergebnisse.append(("Bombe -> zu_gross", foto_neu_kodieren(_bombe()) == "zu_gross"))
    ergebnisse.append(("Speicher gesprengt -> abbruch", foto_neu_kodieren(_gross(), speicher=150 * 1024 * 1024) == "abbruch"))
    for name, ok in ergebnisse:
        ausgabe(f"{'ok ' if ok else '!!!'} {name}")
    from PIL import Image
    gross = io.BytesIO()
    Image.effect_noise((8000, 6000), 60).convert("RGB").save(gross, "JPEG", quality=90)
    start = time.monotonic()
    ergebnis = foto_neu_kodieren(gross.getvalue())
    dauer = time.monotonic() - start
    spitze = ""
    try:
        import resource
        spitze = f", Spitze des Kindprozesses {resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024:.0f} MB"  # Linux: KB
    except ImportError:
        pass
    ausgabe(f"Messung: 48 Mio. Bildpunkte, {len(gross.getvalue()) / 2**20:.0f} MB -> "
            f"{'JPEG ' + str(len(ergebnis) // 1024) + ' KB' if isinstance(ergebnis, bytes) else ergebnis}, {dauer:.1f} s{spitze}")
    alle = all(ok for _n, ok in ergebnisse)
    ausgabe("alle drei wie erwartet" if alle else "NICHT wie erwartet -- nicht in Betrieb nehmen, bitte melden")
    return 0 if alle else 1


if __name__ == "__main__":
    sys.exit(main())
