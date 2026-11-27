"""Prüft das Neukodieren der Fotos für das Kundenportal auf dem Rechner, auf dem es läuft (seit 1.11.33, Stufe P2b; Server-Schritt P2b-4).

Ohne Datenbank: erfundene Bilder gehen durch denselben Kindprozess wie im Postboten
(app/portal_kopien.py::foto_neu_kodieren() bzw. kind_befehl(), app/portal_foto_kind.py):

    1. ein Foto mit EXIF (samt GPS) und Kommentar      -> ein JPEG ohne APP1–APP15 und ohne Kommentar
    2. eine Dekompressionsbombe (100000 × 100000)      -> „zu_gross“
    3. ein Bild, das die Grenze für Speicher sprengt    -> „abbruch“ (unter Linux greift RLIMIT_AS, unter Windows das Job-Objekt)
    4. nur unter Linux (seit 1.11.35): das Kind steht für den OOM-Killer an erster Stelle -- /proc/<pid>/oom_score_adj des laufenden Kinds ist 1000
    Messung (Bauplan P2, B12; seit 1.11.35 je Kind, nicht über alle): ein Foto mit 48 Mio. Bildpunkten (Rauschen, JPEG) und ein PNG mit 36 Mio.
    Bildpunkten und Alpha, je mit der Grenze des Postboten -- Ergebnis, Dauer und unter Linux die Spitze des Speichers dieses Kinds (wait4); keine Prüfung.
    Seit 1.11.47 die Spitze genau des Kinds: Linux übernimmt beim Start eines Programms den Höchststand des startenden Prozesses in dessen Spitze
    (ru_maxrss, fs/exec.c: exec_mmap); bis 1.11.46 startete dieses Skript das Kind selbst, nachdem es die Testbilder im eigenen Speicher erzeugt hatte --
    gemessen wurden rund 320 MB, die Spitze dieses Skripts, nicht die des Kinds. Jetzt erzeugt ein eigener Prozess die beiden Testbilder in einem
    Wegwerf-Ordner (danach gelöscht), und ein kleiner Messprozess (MESSER, nur Standardbibliothek, hält kein Bild) startet das Kind und gibt ihm die Datei.

Auf dem Server als Benutzer des ERP, im Repo-Ordner:

    cd /home/tobias/erp && .venv/bin/python scripts/pruefe_portal_foto.py

Ausgabe: je Prüfung eine Zeile „ok“ bzw. „!!!“ (unter Windows „--“ für Prüfung 4), die Zeile mit der Grenze, zwei Zeilen „Messung: …“ und am Ende
„alle Prüfungen wie erwartet“; Rückgabe 0, sonst 1. Braucht kurz bis zu rund 450 MB Speicher (außerhalb der Einheit des Postboten); schreibt nur die
beiden Testbilder in einen Wegwerf-Ordner unter dem Ordner für temporäre Dateien.
"""

import io
import json
import os
import struct
import subprocess
import sys
import tempfile
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


# Seit 1.11.47: erzeugt die beiden großen Testbilder in einem eigenen Prozess (so hält dieses Skript sie nie im Speicher)
ERZEUGER = r"""
import sys
from PIL import Image
ordner = sys.argv[1]
Image.effect_noise((8000, 6000), 60).convert("RGB").save(ordner + "/gross.jpg", "JPEG", quality=90)
Image.new("RGBA", (6000, 6000), (10, 20, 30, 255)).save(ordner + "/gross.png", "PNG")
"""

# Seit 1.11.47: der kleine Messprozess -- nur Standardbibliothek, hält kein Bild; startet das Kind mit der Datei als Eingabe und meldet Ergebnis, Länge,
# Dauer und unter Linux die Spitze genau des Kinds (wait4). Weil er selbst klein ist, erbt das Kind beim Start keinen großen Höchststand.
MESSER = r"""
import json, os, subprocess, sys, time
datei, befehl = sys.argv[1], sys.argv[2:]
start = time.monotonic()
with open(datei, "rb") as ein:
    kind = subprocess.Popen(befehl, stdin=ein, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    laenge = len(kind.stdout.read())
    kind.stdout.close()
spitze = None
if hasattr(os, "wait4"):
    _pid, status, nutzung = os.wait4(kind.pid, 0)
    rc, spitze = os.waitstatus_to_exitcode(status), nutzung.ru_maxrss
else:
    rc = kind.wait()
print(json.dumps({"rc": rc, "laenge": laenge, "dauer": time.monotonic() - start, "spitze_kb": spitze}))
"""


def _messen(pfad: Path) -> tuple[str, float, str]:
    """Ein Lauf des Kinds mit der Grenze des Postboten, gestartet vom kleinen Messprozess (MESSER): Ergebnis, Dauer, unter Linux die Spitze genau dieses
    Kinds (wait4, nicht über alle Kinder und ohne den Höchststand dieses Skripts)."""
    from app.portal_kopien import KIND_WORT, _kind_umgebung, kind_befehl
    lauf = subprocess.run([sys.executable, "-I", "-c", MESSER, str(pfad), *kind_befehl()], capture_output=True, text=True, timeout=300,
                          env=_kind_umgebung())
    w = json.loads(lauf.stdout.strip().splitlines()[-1])
    spitze = f", Spitze {w['spitze_kb'] / 1024:.0f} MB" if w["spitze_kb"] is not None else ""  # Linux: KB
    ergebnis = f"JPEG {w['laenge'] // 1024} KB" if w["rc"] == 0 else KIND_WORT.get(w["rc"], "abbruch")
    return ergebnis, w["dauer"], spitze


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
    with tempfile.TemporaryDirectory(prefix="pruefe_portal_foto_") as ordner:  # seit 1.11.47: Testbilder aus einem eigenen Prozess, danach gelöscht
        subprocess.run([sys.executable, "-I", "-c", ERZEUGER, ordner], check=True, timeout=300, capture_output=True)
        jpg, png = Path(ordner) / "gross.jpg", Path(ordner) / "gross.png"
        ergebnis, dauer, spitze = _messen(jpg)
        ausgabe(f"Messung: JPEG 48 Mio. Bildpunkte, {jpg.stat().st_size / 2**20:.0f} MB -> {ergebnis}, {dauer:.1f} s{spitze}")
        ergebnis, dauer, spitze = _messen(png)
        ausgabe(f"Messung: PNG 36 Mio. Bildpunkte mit Alpha -> {ergebnis}, {dauer:.1f} s{spitze}")
    alle = all(ok for _n, ok in ergebnisse)
    ausgabe("alle Prüfungen wie erwartet" if alle else "NICHT wie erwartet -- nicht in Betrieb nehmen, bitte melden")
    return 0 if alle else 1


if __name__ == "__main__":
    sys.exit(main())
