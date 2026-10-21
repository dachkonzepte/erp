"""Seit 1.9.20 (Runde 8, Punkt 1): die Testdaten der Bildgrundlage hängen nicht am Lauftag.

Bis 1.9.19 bekam das Angebot beim Befüllen created_at aus der echten Uhr (Spaltenvorgabe datetime.utcnow) -- seine Kopfzeile daraus
Datum und „Gültig bis“ (Date-Spalten, die _zeitstempel_festsetzen() nicht erfasst), die Abschrift des Auftrags (snapshot_json) ebenso;
das PDF des Angebots zeigte den Tag des Laufs und war nur am selben Tag mit einem anderen Lauf vergleichbar.

Prüfung: die Testdaten wie ein Klicktest befüllen (Wegwerf-Instanz unter tmp_path, Regel 16), aber mit einer stehenden Uhr weit weg vom
Lauftag (2030). Was der Uhr folgt, landet 2030; ein Datum vor 2029 in einer Date- oder DateTime-Spalte oder ein Datum 2026/2027 in einer
Textspalte oder einer abgelegten Datei (PDF: dekodierte Ströme) hängt an der echten Zeit. Ausgenommen: der Ablauf der Sitzungen
(expires_at, gegen die echte Zeit geprüft) und die festen Nummern der Testdaten (P-2026-0001, A-2026-0001, AN-2026-0001 und ihre Echos).
"""

import base64
import re
import sqlite3
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import cdp_klicktest as ck  # noqa: E402

FERNE_UHR = "2030-01-15 10:00"
NUMMER = re.compile(r"\b[A-Z]{1,4}-20\d\d-\d{4}\b")
DATUM_TEXT = re.compile(r"\b20(?:2[0-8])-\d\d-\d\d|\b\d\d\.\d\d\.20(?:2[0-8])\b")
AUSGENOMMEN = {("user_sessions", "expires_at")}


@pytest.fixture(scope="module")
def befuellt(tmp_path_factory):
    ordner = tmp_path_factory.mktemp("erp-klicktest-lauftag")
    for sub in ("data", "shots", "chrome-profile"):
        (ordner / sub).mkdir()
    (ordner / ck.MARKER).write_text("Wegwerf-Instanz eines Tests\n", encoding="utf-8")
    env = ck._isolierte_umgebung(ordner)
    env[ck.UHR_ENV] = ck._uhr_marke(FERNE_UHR)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "bildgrundlage.py"), "--nur-befuellen", str(ordner / "seed.json")],
                       env=env, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=240)
    assert r.returncode == 0, r.stderr[-2000:]
    return Path(env["DATABASE_URL"].removeprefix("sqlite:///")), ordner / "data"


def _spalten(db):
    for (tabelle,) in db.execute("select name from sqlite_master where type='table'"):
        for _, name, typ, *_ in db.execute(f'pragma table_info("{tabelle}")'):
            yield tabelle, name, (typ or "").upper()


def test_kein_datum_aus_der_echten_zeit(befuellt):
    datei, _ = befuellt
    db = sqlite3.connect(datei)
    funde = []
    for tabelle, name, typ in _spalten(db):
        if "DATE" not in typ or (tabelle, name) in AUSGENOMMEN:
            continue
        for (wert,) in db.execute(f'select "{name}" from "{tabelle}" where "{name}" is not null'):
            if str(wert)[:4] < "2029":
                funde.append(f"{tabelle}.{name} = {wert}")
    assert funde == [], "Date/DateTime aus der echten Zeit statt der stehenden Uhr: " + "; ".join(sorted(set(funde)))


def test_kein_datumstext_aus_der_echten_zeit(befuellt):
    datei, _ = befuellt
    db = sqlite3.connect(datei)
    funde = []
    for tabelle, name, typ in _spalten(db):
        if not any(t in typ for t in ("CHAR", "TEXT", "JSON", "CLOB")):
            continue
        for (wert,) in db.execute(f'select "{name}" from "{tabelle}" where "{name}" is not null'):
            if m := DATUM_TEXT.search(NUMMER.sub("", str(wert))):
                funde.append(f"{tabelle}.{name}: {m.group(0)}")
    assert funde == [], "Datum im Text aus der echten Zeit: " + "; ".join(sorted(set(funde)))


def _pdf_text(daten: bytes) -> bytes:
    teile = []
    for m in re.finditer(rb"<<((?:(?!<<).)*?)/Length (\d+)\s*>>\s*stream\r?\n", daten, flags=re.S):
        strom = daten[m.end():m.end() + int(m.group(2))]
        if b"/ASCII85Decode" in m.group(1):
            strom = base64.a85decode(strom.strip().removesuffix(b"~>").replace(b"\n", b"").replace(b"\r", b""), adobe=False)
        if b"/FlateDecode" in m.group(1):
            strom = zlib.decompress(strom)
        teile.append(strom)
    return b"".join(teile)


def test_keine_abgelegte_datei_mit_datum_aus_der_echten_zeit(befuellt):
    """Abgelegte Dateien (z. B. feste Fassungen als PDF); das Protokoll der App (*.log) trägt die echte Zeit und zeigt keine Seite."""
    _, daten = befuellt
    funde = []
    for p in daten.rglob("*"):
        if not p.is_file() or p.suffix == ".log":
            continue
        inhalt = p.read_bytes()
        text = (_pdf_text(inhalt) if inhalt.startswith(b"%PDF") else inhalt).decode("latin-1")
        if m := DATUM_TEXT.search(NUMMER.sub("", text)):
            funde.append(f"{p.relative_to(daten)}: {m.group(0)}")
    assert funde == []


def test_die_ferne_uhr_wirkt(befuellt):
    """Vergleich: was der Uhr folgt, steht 2030 -- sonst prüften die anderen Tests nichts."""
    db = sqlite3.connect(befuellt[0])
    assert db.execute("select quote_date, valid_until from quote_document_meta order by id").fetchone() == ("2030-01-15", "2030-02-14")
    assert db.execute("select min(created_at) from quotes").fetchone()[0].startswith("2030-01-15")
