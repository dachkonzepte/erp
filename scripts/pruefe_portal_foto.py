"""Prüft das Neukodieren der Fotos für das Kundenportal auf dem Rechner, auf dem es läuft (seit 1.11.33, Stufe P2b; Server-Schritt P2b-4).

Ohne Datenbank, ohne Dateien, schreibt nichts: erfundene Bilder, im Speicher erzeugt, gehen durch denselben Kindprozess wie im Postboten
(app/portal_kopien.py::foto_neu_kodieren() bzw. kind_befehl(), app/portal_foto_kind.py):

    1. ein Foto mit EXIF (samt GPS) und Kommentar      -> ein JPEG ohne APP1–APP15 und ohne Kommentar
    2. eine Dekompressionsbombe (100000 × 100000)      -> „zu_gross“
    3. ein Bild, das die Grenze für Speicher sprengt    -> „abbruch“ (unter Linux greift RLIMIT_AS, unter Windows das Job-Objekt)
    4. nur unter Linux (seit 1.11.35): das Kind steht für den OOM-Killer an erster Stelle -- /proc/<pid>/oom_score_adj des laufenden Kinds ist 1000
    Messung (Bauplan P2, B12; seit 1.11.35 je Kind, nicht über alle): ein Foto mit 48 Mio. Bildpunkten (Rauschen, JPEG) und ein PNG mit 36 Mio.
    Bildpunkten und Alpha, je mit der Grenze des Postboten -- Ergebnis, Dauer und unter Linux die Spitze des Speichers dieses Kinds (wait4); keine Prüfung

Auf dem Server als Benutzer des ERP, im Repo-Ordner:

    cd /home/tobias/erp && .venv/bin/python scripts/pruefe_portal_foto.py

Ausgabe: je Prüfung eine Zeile „ok“ bzw. „!!!“ (unter Windows „--“ für Prüfung 4), die Zeile mit der Grenze, zwei Zeilen „Messung: …“ und am Ende
„alle Prüfungen wie erwartet“; Rückgabe 0, sonst 1. Braucht kurz bis zu rund 450 MB Speicher (außerhalb der Einheit des Postboten).
"""

import io
import os
import struct
import subprocess
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


def _vorrang() -> bool:
    """Das Kind läuft (wartet auf das Bild) -- sein oom_score_adj muss 1000 sein, bevor es ein Byte liest. Danach bekommt es nichts und endet."""
    from app.portal_kopien import _kind_umgebung, kind_befehl
    kind = subprocess.Popen(kind_befehl(), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_kind_umgebung())
    try:
        ende = time.monotonic() + 10
        while time.monotonic() < ende:
            try:
                if Path(f"/proc/{kind.pid}/oom_score_adj").read_text(encoding="ascii").strip() == "1000":
                    return True
            except OSError:
                pass
            if kind.poll() is not None:
                return False
            time.sleep(0.05)
        return False
    finally:
        kind.stdin.close()
        try:
            kind.wait(timeout=30)
        except subprocess.TimeoutExpired:
            kind.kill()
            kind.wait()


def _messen(daten: bytes) -> tuple[str, float, str]:
    """Ein Lauf des Kinds mit der Grenze des Postboten: Ergebnis, Dauer, unter Linux die Spitze genau dieses Kinds (wait4, nicht über alle Kinder)."""
    from app.portal_kopien import KIND_WORT, _kind_umgebung, kind_befehl
    start = time.monotonic()
    kind = subprocess.Popen(kind_befehl(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=_kind_umgebung())
    kind.stdin.write(daten)  # das Kind liest erst alles, schreibt dann
    kind.stdin.close()
    aus = kind.stdout.read()
    kind.stdout.close()
    spitze = ""
    if hasattr(os, "wait4"):
        _pid, status, nutzung = os.wait4(kind.pid, 0)
        kind.returncode = os.waitstatus_to_exitcode(status)
        spitze = f", Spitze {nutzung.ru_maxrss / 1024:.0f} MB"  # Linux: KB
    else:
        kind.wait()
    dauer = time.monotonic() - start
    ergebnis = f"JPEG {len(aus) // 1024} KB" if kind.returncode == 0 else KIND_WORT.get(kind.returncode, "abbruch")
    return ergebnis, dauer, spitze


def main(ausgabe=print) -> int:
    from app.portal_kopien import FOTO_SPEICHER, POSTBOTE_RAUM, foto_neu_kodieren

    ergebnisse = []
    foto = foto_neu_kodieren(_foto())
    ergebnisse.append(("Foto ohne Metadaten", isinstance(foto, bytes) and _ohne_metadaten(foto)))
    ergebnisse.append(("Bombe -> zu_gross", foto_neu_kodieren(_bombe()) == "zu_gross"))
    ergebnisse.append(("Speicher gesprengt -> abbruch", foto_neu_kodieren(_gross(), speicher=150 * 1024 * 1024) == "abbruch"))
    if sys.platform.startswith("linux"):
        ergebnisse.append(("Vorrang für den OOM-Killer: Kind mit oom_score_adj 1000", _vorrang()))
    for name, ok in ergebnisse:
        ausgabe(f"{'ok ' if ok else '!!!'} {name}")
    if not sys.platform.startswith("linux"):
        ausgabe("--  Vorrang für den OOM-Killer: entfällt (nur unter Linux)")
    ausgabe(f"Grenze des Kinds {FOTO_SPEICHER // 2**20} MB (MemoryHigh der Einheit minus {POSTBOTE_RAUM // 2**20} MB für den Postboten)")
    from PIL import Image
    gross = io.BytesIO()
    Image.effect_noise((8000, 6000), 60).convert("RGB").save(gross, "JPEG", quality=90)
    ergebnis, dauer, spitze = _messen(gross.getvalue())
    ausgabe(f"Messung: JPEG 48 Mio. Bildpunkte, {len(gross.getvalue()) / 2**20:.0f} MB -> {ergebnis}, {dauer:.1f} s{spitze}")
    ergebnis, dauer, spitze = _messen(_gross())
    ausgabe(f"Messung: PNG 36 Mio. Bildpunkte mit Alpha -> {ergebnis}, {dauer:.1f} s{spitze}")
    alle = all(ok for _n, ok in ergebnisse)
    ausgabe("alle Prüfungen wie erwartet" if alle else "NICHT wie erwartet -- nicht in Betrieb nehmen, bitte melden")
    return 0 if alle else 1


if __name__ == "__main__":
    sys.exit(main())
