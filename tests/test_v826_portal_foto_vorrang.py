"""Version 1.11.35 (vor P2c, Vorgabe des Betriebs vom 27.11.2026): wird die Einheit des Postboten eng, scheitert das Kind, nie der Postbote.

    Vorrang     das Kind (app/portal_foto_kind.py) setzt unter Linux selbst oom_score_adj 1000 (anheben darf jeder Prozess ohne Rechte) und prüft den
                Wert; steht er danach nicht auf 1000, endet es mit 13, bevor es ein Byte liest -- der Postbote macht daraus „abbruch“
    Einheit     OOMPolicy=continue: beendet der Kernel nur das Kind, läuft der Postbote weiter (ab Werk „stop“ hielte systemd die ganze Einheit an)
    Grenzen     die Grenze des Kinds plus der Raum für den Postboten liegt unter MemoryHigh der Einheit, MemoryHigh unter MemoryMax -- das Kind scheitert an
                seiner eigenen Grenze, bevor die Einheit eng wird (über MemoryHigh bremst der Kernel jeden Prozess der Einheit, auch den Postboten)
    JPEG        wird nach seinem Seitenverhältnis verkleinert dekodiert: ein Foto 8000 × 6000 braucht so rund 100 statt 280 MB (gemessen unter Windows) und
                kommt mit 200 MB Grenze durch, in der richtigen Größe und Lage

Unter Linux prüft scripts/pruefe_portal_foto.py den Vorrang am laufenden Kind (Server-Schritt P2b-4) -- hier gibt es kein Linux.
"""

import io
import re
import sys
from pathlib import Path

from PIL import Image

from app import portal_foto_kind as kind
from app import portal_kopien
from app.portal_kopien import FOTO_SPEICHER, POSTBOTE_RAUM, foto_neu_kodieren

ROOT = Path(__file__).resolve().parents[1]
EINHEIT = ROOT / "scripts" / "server" / "erp-portalpost.service"


def _einheit() -> dict:
    return {z.split("=", 1)[0]: z.split("=", 1)[1] for z in EINHEIT.read_text(encoding="utf-8").splitlines() if "=" in z and not z.startswith("#")}


def _bytes(wert: str) -> int:
    zahl, einheit = re.fullmatch(r"(\d+)([KMG])", wert).groups()
    return int(zahl) * {"K": 2**10, "M": 2**20, "G": 2**30}[einheit]


def test_einheit_laesst_den_postboten_nach_dem_oom_des_kinds_weiterlaufen():
    assert _einheit()["OOMPolicy"] == "continue"


def test_das_kind_scheitert_vor_der_einheit():
    zeilen = _einheit()
    hoch, max_ = _bytes(zeilen["MemoryHigh"]), _bytes(zeilen["MemoryMax"])
    assert FOTO_SPEICHER + POSTBOTE_RAUM <= hoch < max_, (FOTO_SPEICHER, POSTBOTE_RAUM, hoch, max_)
    assert POSTBOTE_RAUM >= 192 * 2**20  # der Postbote braucht auf dem Server rund 100 MB (S6), dazu eine PDF-Kopie bis 25 MB zweimal
    assert portal_kopien.kind_befehl()[3] == str(FOTO_SPEICHER)  # der Postbote ruft das Kind wirklich mit dieser Grenze auf


def test_vorrang_setzen_schreibt_1000_und_liest_nach(tmp_path):
    datei = tmp_path / "oom_score_adj"
    datei.write_text("0", encoding="ascii")
    assert kind.vorrang_setzen(str(datei)) is True
    assert datei.read_text(encoding="ascii") == "1000"


def test_vorrang_nicht_schreibbar_heisst_nein(tmp_path):
    assert kind.vorrang_setzen(str(tmp_path)) is False  # ein Ordner: Schreiben scheitert
    assert kind.vorrang_setzen(str(tmp_path / "fehlt" / "oom_score_adj")) is False


def test_vorrang_mit_anderem_wert_danach_heisst_nein(tmp_path, monkeypatch):
    """Schreiben gelingt, gelesen wird etwas anderes (z. B. ein Kernel, der den Wert begrenzt): kein Vorrang."""
    echtes_open = open

    def open_mit_anderem_wert(datei, modus="r", **kw):
        if "w" in modus:
            return echtes_open(datei, modus, **kw)
        return io.StringIO("500\n")

    monkeypatch.setattr(kind, "open", open_mit_anderem_wert, raising=False)
    assert kind.vorrang_setzen(str(tmp_path / "oom_score_adj")) is False


def test_ohne_vorrang_unter_linux_endet_das_kind_mit_13_vor_allem_anderen(tmp_path, monkeypatch):
    monkeypatch.setattr(kind, "LINUX", True)
    monkeypatch.setattr(kind, "VORRANG_DATEI", str(tmp_path))  # nicht schreibbar

    def nicht_erreicht(*_a, **_kw):
        raise AssertionError("das Kind ging ohne Vorrang weiter")

    monkeypatch.setattr(kind, "speicher_begrenzen", nicht_erreicht)
    monkeypatch.setattr(kind, "neu_kodieren", nicht_erreicht)
    monkeypatch.setattr(sys, "stdin", None)  # gelesen wird nichts
    assert kind.main(["kind", "1", "1", "1", "1"]) == kind.OHNE_VORRANG == 13


def test_mit_vorrang_unter_linux_geht_das_kind_weiter(tmp_path, monkeypatch):
    datei = tmp_path / "oom_score_adj"
    datei.write_text("0", encoding="ascii")
    monkeypatch.setattr(kind, "LINUX", True)
    monkeypatch.setattr(kind, "VORRANG_DATEI", str(datei))
    gesehen = []
    monkeypatch.setattr(kind, "speicher_begrenzen", lambda grenze: gesehen.append(("grenze", grenze, datei.read_text(encoding="ascii"))))
    monkeypatch.setattr(kind, "neu_kodieren", lambda *_a: b"jpeg")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"bild")))
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO()))
    assert kind.main(["kind", "123", "1", "1", "1"]) == 0
    assert gesehen == [("grenze", 123, "1000")]  # der Vorrang stand, bevor die Grenze gesetzt und das Bild gelesen wurde


def test_der_postbote_macht_aus_13_abbruch():
    assert portal_kopien.KIND_WORT.get(13) is None
    assert foto_neu_kodieren(b"x", befehl=[sys.executable, "-c", "import sys; sys.exit(13)"]) == "abbruch"


def _foto(breite, hoehe) -> bytes:
    """Links rot, rechts blau (über die lange Seite geteilt), als JPEG."""
    bild = Image.new("RGB", (breite, hoehe), "blue")
    bild.paste(Image.new("RGB", (breite // 2, hoehe), "red"), (0, 0))
    aus = io.BytesIO()
    bild.save(aus, "JPEG", quality=90)
    return aus.getvalue()


def test_grosses_jpeg_wird_verkleinert_dekodiert():
    """8000 × 6000 und hochkant 6000 × 8000 mit 200 MB Grenze: ohne verkleinertes Dekodieren „abbruch“ (gemessen 280 MB), so ein JPEG in Größe und Lage."""
    for (breite, hoehe), ziel in (((8000, 6000), (1600, 1200)), ((6000, 8000), (1200, 1600))):
        jpeg = foto_neu_kodieren(_foto(breite, hoehe), speicher=200 * 2**20)
        assert isinstance(jpeg, bytes), jpeg
        bild = Image.open(io.BytesIO(jpeg))
        assert bild.size == ziel
        links, rechts = bild.getpixel((ziel[0] // 8, ziel[1] // 2)), bild.getpixel((ziel[0] * 7 // 8, ziel[1] // 2))
        assert links[0] > 200 and links[2] < 60 and rechts[2] > 200 and rechts[0] < 60, (links, rechts)
