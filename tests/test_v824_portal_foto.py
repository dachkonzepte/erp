"""Version 1.11.33 (Stufe P2b, Bauplan P2, B5 und Nachtrag 4): Fotos für das Kundenportal werden in einem Kindprozess neu kodiert
(app/portal_foto_kind.py, aufgerufen über app/portal_kopien.py::foto_neu_kodieren()). Jeder Test läuft durch den echten Kindprozess -- so wie der Postbote.

    Metadaten   ein JPEG mit EXIF (Beschreibung, Urheber, GPS), XMP mit Ort, IPTC, ICC-Profil und Kommentar: die Kopie hat keines der Segmente APP1–APP15
                und COM, keinen der Marker; Drehung aus EXIF angewandt; längste Kante 1600; ein angehängter Rest der Datei (ZIP, HTML) geht verloren
    Formate     PNG mit Transparenz (auf Weiß), GIF mit zwei Bildern (das erste), WebP -- je ein JPEG; alles andere ist nicht lesbar
    Grenzen     Bombe (100000 × 100000 Bildpunkte) und knapp über der Grenze: „zu_gross“; kaputtes und abgeschnittenes Bild: „nicht_lesbar“; ein Bild, das
                die Grenze für Speicher sprengt: „abbruch“; ein Kind, das abstürzt oder nicht fertig wird: „abbruch“ (und es läuft danach nicht mehr)
    Umgebung    das Kind bekommt keine Geheimnisse (nur PATH) und importiert nichts aus dem ERP
"""

import ast
import io
import os
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from app import portal_kopien
from app.portal_kopien import foto_neu_kodieren

ROOT = Path(__file__).resolve().parents[1]
MARKER = (b"GEHEIM-BESCHREIBUNG", b"GEHEIM-URHEBER", b"GEHEIM-XMP-ORT", b"GEHEIM-IPTC", b"GEHEIM-KOMMENTAR", b"GEHEIM-KAMERA")


def segmente(jpeg: bytes) -> list[int]:
    """Die Marker eines JPEG bis zum Beginn der Bilddaten (SOS)."""
    assert jpeg[:2] == b"\xff\xd8"
    i, gefunden = 2, []
    while i < len(jpeg):
        assert jpeg[i] == 0xFF, i
        marker = jpeg[i + 1]
        gefunden.append(marker)
        if marker == 0xDA:  # SOS
            break
        laenge = struct.unpack(">H", jpeg[i + 2:i + 4])[0]
        i += 2 + laenge
    return gefunden


def _iptc(jpeg: bytes) -> bytes:
    """Ein IPTC-Segment (APP13, Photoshop 3.0) gleich nach SOI einfügen."""
    eintrag = b"\x1c\x02\x78" + struct.pack(">H", len(MARKER[3])) + MARKER[3]
    block = b"8BIM\x04\x04\x00\x00" + struct.pack(">I", len(eintrag)) + eintrag
    inhalt = b"Photoshop 3.0\x00" + block
    return jpeg[:2] + b"\xff\xed" + struct.pack(">H", len(inhalt) + 2) + inhalt + jpeg[2:]


def foto_mit_allem(groesse=(4000, 3000), drehung=1) -> bytes:
    """Links rot, rechts blau -- mit EXIF (samt GPS), XMP, IPTC, ICC und Kommentar."""
    bild = Image.new("RGB", groesse, "blue")
    bild.paste(Image.new("RGB", (groesse[0] // 2, groesse[1]), "red"), (0, 0))
    exif = Image.Exif()
    exif[0x010E] = MARKER[0].decode()      # ImageDescription
    exif[0x013B] = MARKER[1].decode()      # Artist
    exif[0x0110] = MARKER[5].decode()      # Model
    exif[0x0112] = drehung
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (52.0, 31.0, 12.0), "E", (13.0, 24.0, 36.0)
    xmp = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
           b'xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/" photoshop:City="' + MARKER[2] + b'"/></rdf:RDF></x:xmpmeta>')
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    aus = io.BytesIO()
    bild.save(aus, "JPEG", quality=90, exif=exif.tobytes(), xmp=xmp, icc_profile=icc, comment=MARKER[4])
    return _iptc(aus.getvalue())


def test_eingang_traegt_wirklich_alles():
    """Damit die Prüfung unten etwas beweist: der Eingang hat jedes Segment und jeden Marker."""
    eingang = foto_mit_allem((400, 300))
    seg = segmente(eingang)
    assert {0xE1, 0xE2, 0xED, 0xFE} <= set(seg)  # APP1 (EXIF, XMP), APP2 (ICC), APP13 (IPTC), COM
    for m in MARKER:
        assert m in eingang, m
    assert Image.open(io.BytesIO(eingang)).getexif().get_ifd(0x8825), "GPS fehlt im Eingang"


def test_kopie_ohne_metadaten_mit_drehung_und_kante():
    kopie = foto_neu_kodieren(foto_mit_allem((4000, 3000), drehung=6))
    assert isinstance(kopie, bytes), kopie
    assert [m for m in segmente(kopie) if 0xE1 <= m <= 0xEF or m == 0xFE] == []
    for m in MARKER:
        assert m not in kopie, m
    bild = Image.open(io.BytesIO(kopie))
    assert bild.format == "JPEG" and bild.mode == "RGB"
    assert bild.size == (1200, 1600)  # gedreht (hoch) und auf 1600 verkleinert
    assert not bild.getexif() and "icc_profile" not in bild.info and "comment" not in bild.info and "xmp" not in bild.info
    rot, blau = bild.getpixel((600, 100)), bild.getpixel((600, 1500))
    assert rot[0] > 200 and rot[2] < 60 and blau[2] > 200 and blau[0] < 60  # Drehung 6 = 90° im Uhrzeigersinn: links (rot) kommt nach oben


@pytest.mark.parametrize("anhang", [b"PK\x03\x04" + b"\x00" * 26 + b"geheim.txt", b"<html><script>alert(1)</script></html>"], ids=["zip", "html"])
def test_angehaengter_rest_geht_verloren(anhang):
    eingang = foto_mit_allem((300, 200)) + anhang
    kopie = foto_neu_kodieren(eingang)
    assert isinstance(kopie, bytes) and anhang[:8] not in kopie and b"geheim" not in kopie and b"<script" not in kopie
    assert kopie.endswith(b"\xff\xd9")


def test_png_mit_transparenz_auf_weiss():
    bild = Image.new("RGBA", (100, 50), (255, 0, 0, 0))
    bild.paste(Image.new("RGBA", (50, 50), (0, 0, 255, 255)), (50, 0))
    aus = io.BytesIO()
    bild.save(aus, "PNG")
    kopie = foto_neu_kodieren(aus.getvalue())
    j = Image.open(io.BytesIO(kopie))
    assert j.format == "JPEG" and j.size == (100, 50)
    assert min(j.getpixel((10, 25))) > 245  # durchsichtig -> weiß, nicht rot
    assert j.getpixel((90, 25))[2] > 200


def test_gif_erstes_bild_und_webp():
    erstes, zweites = Image.new("RGB", (60, 40), "red"), Image.new("RGB", (60, 40), "blue")
    aus = io.BytesIO()
    erstes.save(aus, "GIF", save_all=True, append_images=[zweites])
    j = Image.open(io.BytesIO(foto_neu_kodieren(aus.getvalue())))
    assert j.getpixel((30, 20))[0] > 200 and j.getpixel((30, 20))[2] < 60
    aus = io.BytesIO()
    Image.new("RGB", (80, 60), "green").save(aus, "WEBP")
    assert Image.open(io.BytesIO(foto_neu_kodieren(aus.getvalue()))).size == (80, 60)


def _png_kopf(breite: int, hoehe: int) -> bytes:
    """Ein PNG, das diese Maße nur behauptet (die Daten sind winzig) -- eine Dekompressionsbombe für die Prüfung beim Öffnen."""
    def chunk(art, daten):
        return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00" * 1024)) + chunk(b"IEND", b""))


def test_bombe_zu_gross():
    assert foto_neu_kodieren(_png_kopf(100_000, 100_000)) == "zu_gross"


def test_knapp_ueber_der_grenze_zu_gross():
    """Pillow warnt erst über der Grenze und bricht über dem Doppelten ab -- hier ist schon über der Grenze zu groß."""
    assert foto_neu_kodieren(_png_kopf(9000, 8000)) == "zu_gross"  # 72 Mio. Bildpunkte, Grenze 64 Mio.
    aus = io.BytesIO()
    Image.new("1", (7000, 9000)).save(aus, "PNG")  # 63 Mio.: geht
    assert isinstance(foto_neu_kodieren(aus.getvalue()), bytes)


@pytest.mark.parametrize("art", ["kaputt", "abgeschnitten", "tiff", "text"])
def test_nicht_lesbar(art):
    voll = foto_mit_allem((800, 600))
    eingang = {"kaputt": b"\xff\xd8\xff\xe0" + os.urandom(4000), "abgeschnitten": voll[:len(voll) // 2],
               "tiff": None, "text": b"kein Bild"}[art]
    if art == "tiff":
        aus = io.BytesIO()
        Image.new("RGB", (20, 20)).save(aus, "TIFF")
        eingang = aus.getvalue()
    assert foto_neu_kodieren(eingang) == "nicht_lesbar"


def test_speicher_gesprengt_abbruch_und_der_aufrufer_laeuft_weiter():
    """Grenze 150 MB, Bild 6000 × 6000 mit Alpha (144 MB entpackt, die Datei klein): das Kind scheitert am Speicher, der Aufrufer bekommt „abbruch“.
    Dasselbe Bild mit der Grenze des Betriebs geht (die Grenze greift wirklich, nicht der Inhalt)."""
    aus = io.BytesIO()
    Image.new("RGBA", (6000, 6000), (10, 20, 30, 255)).save(aus, "PNG")
    assert foto_neu_kodieren(aus.getvalue(), speicher=150 * 1024 * 1024) == "abbruch"
    assert isinstance(foto_neu_kodieren(aus.getvalue()), bytes)


def test_absturz_und_zeit_abbruch(tmp_path):
    assert foto_neu_kodieren(b"x", befehl=[sys.executable, "-c", "import os; os.abort()"]) == "abbruch"
    assert foto_neu_kodieren(b"x", befehl=[sys.executable, "-c", "import sys; sys.exit(3)"]) == "abbruch"
    assert foto_neu_kodieren(b"x", befehl=[sys.executable, "-c", "import sys; sys.stdout.write('kein jpeg')"]) == "abbruch"
    start = time.monotonic()
    marke = tmp_path / "kind_lebt"
    langsam = f"import time, pathlib; time.sleep(3); pathlib.Path({str(marke)!r}).write_text('noch da')"
    assert foto_neu_kodieren(b"x", sekunden=0.5, befehl=[sys.executable, "-c", langsam]) == "abbruch"
    assert time.monotonic() - start < 3
    time.sleep(3.5)
    assert not marke.exists(), "das Kind lief nach der Zeitgrenze weiter"


def test_kind_bekommt_keine_geheimnisse(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://geheim")
    monkeypatch.setenv("ERP_SECRET_KEY", "geheim")
    umgebung = portal_kopien._kind_umgebung()
    assert set(umgebung) <= {"PATH", "SYSTEMROOT"} and "geheim" not in repr(umgebung)


def test_kind_importiert_nichts_aus_dem_erp():
    baum = ast.parse((ROOT / "app" / "portal_foto_kind.py").read_text(encoding="utf-8"))
    module = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            module |= {a.name.split(".")[0] for a in knoten.names}
        elif isinstance(knoten, ast.ImportFrom):
            assert knoten.level == 0, "relativer Import im Kind"
            module.add(knoten.module.split(".")[0])
    assert module <= {"io", "sys", "warnings", "ctypes", "resource", "PIL"}, module
    befehl = [sys.executable, "-I", str(portal_kopien.KIND)]
    assert subprocess.run(befehl + ["1"], capture_output=True, timeout=60).returncode == 2  # falsche Aufrufe: nichts gelesen, nichts geschrieben


def test_pruefskript_fuer_den_server_als_kindprozess():
    """Server-Schritt P2b-4: scripts/pruefe_portal_foto.py so, wie es auf dem Server läuft (Python aus .venv, im Repo-Ordner) -- drei Prüfungen, unter Linux
    vier (seit 1.11.35 der Vorrang des Kinds), zwei Messungen je Kind, Rückgabe 0."""
    lauf = subprocess.run([sys.executable, "scripts/pruefe_portal_foto.py"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    pruefungen = 4 if sys.platform.startswith("linux") else 3
    assert lauf.returncode == 0 and lauf.stdout.count("ok ") == pruefungen and "alle Prüfungen wie erwartet" in lauf.stdout and lauf.stderr == "", lauf
    assert lauf.stdout.count("Messung: ") == 2 and "Grenze des Kinds 448 MB" in lauf.stdout, lauf.stdout
