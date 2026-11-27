"""Version 1.11.44 (Stufe P2e, Teil 2): die Vorschau eines Fotos im Kundenportal (Bauplan P2, B5; Entwurf P2, Seiten 4 und 5: Bildreihe je 12).

    Ohne Datenbank  derselbe Kindprozess mit 400 px und Qualität 75; ein echtes Foto wird höchstens 400 px groß; portal_vorschau() liest nur (STABLE, kein
                    Protokoll, keine Bremse), jedes Ergebniswort ist im Dienst behandelt; die Migration trägt den Text wörtlich
    PostgreSQL      Postbote: ein Foto bekommt mit der Kopie eine Vorschau, ein PDF keine; Rücknahme nimmt beide; scheitert die Vorschau, gilt die Kopie
                    trotzdem und der volle Lauf holt sie nach, ohne die Kopie anzufassen; eine fehlende Vorschau-Datei legt beides neu an; Waisen ja,
                    Vorschauen nein
                    Dienst über die Attrappe von nginx: Vorschau ohne Anforderung und ohne Protokoll; fremd, ohne Vorschau, zurückgenommen außen gleich 404;
                    ohne Sitzung 401
"""

import importlib.util
import io
import re
from pathlib import Path

import pytest
from PIL import Image

from app import portal_kopien
from app.portal import routen, schaufenster
from app.portal.rechte import FUNKTIONEN

ROOT = Path(__file__).resolve().parents[1]


def _jpeg(breite=1600, hoehe=1200) -> bytes:
    aus = io.BytesIO()
    Image.new("RGB", (breite, hoehe), "teal").save(aus, "JPEG", quality=90)
    return aus.getvalue()


def _sql() -> str:
    return next(s for n, _a, s in schaufenster._FUNKTIONEN if n == "portal_vorschau")


# --- ohne Datenbank ------------------------------------------------------------------------------------------------------------------------------------

def test_derselbe_kindprozess_mit_400_px():
    befehl = portal_kopien.kind_befehl(portal_kopien.FOTO_SPEICHER, portal_kopien.FOTO_PIXEL, portal_kopien.VORSCHAU_KANTE, portal_kopien.VORSCHAU_QUALITAET)
    assert befehl[-2:] == ["400", "75"] and befehl[:4] == portal_kopien.kind_befehl()[:4]
    klein = portal_kopien.vorschau_kodieren(_jpeg())
    assert isinstance(klein, bytes) and Image.open(io.BytesIO(klein)).size == (400, 300) and Image.open(io.BytesIO(klein)).format == "JPEG"


def test_funktion_liest_nur_und_jedes_wort_ist_behandelt():
    sql = _sql()
    assert "STABLE SECURITY DEFINER" in sql and "SET search_path = pg_catalog, @SCHEMA@, pg_temp" in sql
    rumpf = sql.split("$$", 1)[1]
    for verboten in ("INSERT", "UPDATE", "DELETE", "portal_protokoll", "portal_bremse", "EXECUTE"):
        assert verboten not in rumpf, verboten
    woerter = set(re.findall(r"RETURN QUERY SELECT '(\w+)'::text", rumpf)) | set(re.findall(r"THEN '(\w+)' ELSE '(\w+)'", rumpf)[0])
    assert routen.BEHANDELT["portal_vorschau"] == woerter == {"ok", "keine", "unbekannt", "ungueltig"}
    assert FUNKTIONEN["portal_vorschau"] == "p_sitzung text, p_freigabe integer"
    assert "/datei/{freigabe}/vorschau" in routen.SITZUNG


def test_migration_traegt_den_text_woertlich():
    pfad = next((ROOT / "alembic" / "versions").glob("b3e7a1d9c5f2_*.py"))
    spec = importlib.util.spec_from_file_location("migration_vorschau", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul.down_revision == "f8b2d6a4c9e1" and schaufenster.MIGRATIONEN[-1] == "b3e7a1d9c5f2"
    assert modul.ANWEISUNGEN_SCHAUFENSTER == (_sql(), "REVOKE ALL ON FUNCTION portal_vorschau(text, integer) FROM PUBLIC")


# --- PostgreSQL: Postbote ------------------------------------------------------------------------------------------------------------------------------

from tests.test_v822_portal_unterlagen_matrix import _freigabe as _freigabe_matrix  # noqa: E402
from tests.test_v823_portal_kopien import _abgleich, _kunde, echte_quelle, w, welt  # noqa: E402,F401  (w und welt sind Fixtures)


def _vorschau_zeile(w, fid):
    return w.erp("SELECT kopie_name, kopie_vorschau, kopie_bereit_am FROM portal_freigaben WHERE id = :i", i=fid)[0]


def _dateien(w) -> set[str]:
    return {p.name for p in w.ordner.iterdir()} - {portal_kopien.BESITZER}


def test_pg_foto_mit_vorschau_pdf_ohne_und_ruecknahme_nimmt_beide(w):
    kunde, _sitz = _kunde(w, "Vorschau")
    foto, _ = echte_quelle(w, "service_report_photos", kunde, inhalt=_jpeg(800, 600))
    pdf, _ = echte_quelle(w, "customer_documents", kunde)
    f_foto, f_pdf = _freigabe_matrix(w, kunde, foto, bereit=False), _freigabe_matrix(w, kunde, pdf, bereit=False)
    assert _abgleich(w).angelegt == 2
    name, klein, _bereit = _vorschau_zeile(w, f_foto)
    assert portal_kopien.NAME.match(klein) and klein.endswith(".jpg") and klein != name
    assert Image.open(w.ordner / klein).size == (400, 300) and Image.open(w.ordner / name).size == (800, 600)
    assert _vorschau_zeile(w, f_pdf)[1] is None
    assert _dateien(w) == {name, klein, _vorschau_zeile(w, f_pdf)[0]}
    w.erp("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_von_name = 'Büro' WHERE id = :i", i=f_foto)
    assert _abgleich(w).entfernt == 1
    assert _vorschau_zeile(w, f_foto)[:2] == (None, None) and name not in _dateien(w) and klein not in _dateien(w)


def test_pg_vorschau_scheitert_kopie_gilt_und_der_volle_lauf_holt_nach(w):
    kunde, _sitz = _kunde(w, "Nachholen")
    foto, _ = echte_quelle(w, "service_report_photos", kunde, inhalt=_jpeg(800, 600))
    fid = _freigabe_matrix(w, kunde, foto, bereit=False)
    assert _abgleich(w, vorschau=lambda _d: "abbruch").angelegt == 1
    name, klein, bereit = _vorschau_zeile(w, fid)
    assert name and bereit is not None and klein is None  # die Kopie gilt
    stand = _abgleich(w, voll=True)
    assert (stand.vorschauen, stand.angelegt, stand.entfernt, stand.nachgeholt) == (1, 0, 0, 0), stand
    name2, klein2, bereit2 = _vorschau_zeile(w, fid)
    assert (name2, bereit2) == (name, bereit) and klein2 and Image.open(w.ordner / klein2).size == (400, 300)  # die Kopie unberührt
    assert _abgleich(w, voll=True).vorschauen == 0  # nichts doppelt


def test_pg_fehlende_vorschau_legt_beides_neu_an_waisen_ja_vorschauen_nein(w):
    kunde, _sitz = _kunde(w, "Waisen")
    foto, _ = echte_quelle(w, "service_report_photos", kunde, inhalt=_jpeg(800, 600))
    fid = _freigabe_matrix(w, kunde, foto, bereit=False)
    _abgleich(w)
    name, klein, _b = _vorschau_zeile(w, fid)
    fremd = portal_kopien.secrets.token_hex(32) + ".jpg"
    (w.ordner / fremd).write_bytes(b"\xff\xd8\xff")  # eine Waise
    assert _abgleich(w, voll=True).waisen == 1 and {name, klein} <= _dateien(w) and fremd not in _dateien(w)
    (w.ordner / klein).unlink()
    stand = _abgleich(w, voll=True)
    assert (stand.nachgeholt, stand.angelegt) == (1, 1), stand
    name3, klein3, _b3 = _vorschau_zeile(w, fid)
    assert name3 != name and klein3 and {name3, klein3} <= _dateien(w) and name not in _dateien(w)


# --- PostgreSQL: Dienst ---------------------------------------------------------------------------------------------------------------------------------

from tests.test_v825_portal_dateien import _anfrage, _freigabe as _freigabe_dienst, _kunde as _kunde_dienst, pg_modul  # noqa: E402,F401


@pytest.fixture
def dienst(pg_modul):  # noqa: F811
    pg_modul.w.erp("DELETE FROM portal_bremsen")
    return pg_modul


def _mit_vorschau(p, kunde, inhalt):
    fid, _name = _freigabe_dienst(p, kunde, titel="Foto Dach", typ="image/jpeg", inhalt=_jpeg(800, 600))
    klein = portal_kopien.secrets.token_hex(32) + ".jpg"
    (p.ordner / klein).write_bytes(inhalt)
    p.w.erp("UPDATE portal_freigaben SET kopie_vorschau = :v WHERE id = :i", v=klein, i=fid)
    return fid


def test_pg_vorschau_ohne_anforderung_und_ohne_protokoll(dienst):
    p = dienst
    kunde, keks = _kunde_dienst(p)
    klein = _jpeg(400, 300)
    fid = _mit_vorschau(p, kunde, klein)
    vorher = p.w.erp("SELECT count(*) FROM portal_zugriffe")[0][0]
    r = _anfrage(p.nginx, "GET", f"/datei/{fid}/vorschau", keks=keks)
    assert r.status == 200 and r.koerper == klein and r.kopf["content-type"] == "image/jpeg" and r.kopf["cache-control"] == "private, no-store"
    assert "x-accel-redirect" not in r.kopf
    assert p.w.erp("SELECT count(*) FROM portal_zugriffe")[0][0] == vorher  # kein Protokoll, keine Anforderung
    beim_dienst = _anfrage(p.port, "GET", f"/datei/{fid}/vorschau", keks=keks)
    assert beim_dienst.status == 200 and beim_dienst.koerper == b"" and beim_dienst.kopf["x-accel-redirect"].startswith("/_portal_dateien/")


def test_pg_vorschau_aussen_gleich_404_und_ohne_sitzung_401(dienst):
    p = dienst
    kunde, keks = _kunde_dienst(p)
    _fremd, keks_fremd = _kunde_dienst(p)
    fid = _mit_vorschau(p, kunde, _jpeg(400, 300))
    ohne, _n = _freigabe_dienst(p, kunde, titel="Foto ohne", typ="image/jpeg", inhalt=_jpeg(80, 60))
    antworten = [_anfrage(p.port, "GET", f"/datei/{fid}/vorschau", keks=keks_fremd),   # fremd
                 _anfrage(p.port, "GET", f"/datei/{ohne}/vorschau", keks=keks),        # ohne Vorschau
                 _anfrage(p.port, "GET", "/datei/2147483000/vorschau", keks=keks)]     # unbekannt
    p.w.erp("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_von_name = 'Büro' WHERE id = :i", i=fid)
    antworten.append(_anfrage(p.port, "GET", f"/datei/{fid}/vorschau", keks=keks))      # zurückgenommen
    assert [(a.status, a.koerper) for a in antworten] == [(404, b'{"fehler":"nicht_gefunden"}')] * 4
    assert all("x-accel-redirect" not in a.kopf for a in antworten)
    assert _anfrage(p.port, "GET", f"/datei/{ohne}/vorschau").status == 401
