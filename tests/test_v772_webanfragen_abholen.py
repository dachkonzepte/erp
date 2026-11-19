"""Version 1.10.0 (Stufe W1a): Anfragen der Webseite abholen (app/webanfragen.py::abholen()) -- gegen die Attrappe des Empfangsdienstes
(scripts/empfangsdienst_attrappe.py), nur Musterdaten.

    Ablauf      neue Anfrage: Umschlag und Dateien holen, prüfen, ablegen, eine Transaktion, dann „übernommen“ melden (erp_id eingang-<id>)
    doppelt     nie: die Nummer der Webseite ist eindeutig; eine schon abgeholte, noch gelistete wird nur (wieder) gemeldet
    Fremddaten  Datei mit falscher Prüfsumme, falscher Größe, falschem Typ, zu groß: nichts ablegen, nichts melden, Grund im Stand
                Dateiname nie als Pfad, „pfad“ des Umschlags nie benutzt; unbekannte Art/Fassung, ungültige Angaben: Prüfliste, nie ein Fehler
                Antwort unlesbar, zu groß, zu tief verschachtelt: Lauf endet mit festem Text; Umleitung nie gefolgt (Schlüssel bliebe beim Ziel)
    Ausfall     bricht der Empfangsdienst mitten in einer Anfrage ab: keine Zeile, keine Datei; was vorher vollständig war, bleibt
    Sperre      zwei Läufe nie zugleich (bedingtes UPDATE); nach SPERRE_GILT gilt eine liegen gebliebene Belegung nicht mehr
    Schlüssel   nur aus der Umgebung, nie in Stand, Ergebnis, Protokoll; Adresse nur auf diesem Server
"""

import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from sqlalchemy import select

from app import webanfragen as W
from app.models import WebAnfrage, WebAnfrageDatei, WebanfragenAbholung
from scripts.empfangsdienst_attrappe import Attrappe, jpeg_bytes, muster

R1, R2, K1 = "R-20261119-0910-0A1B", "R-20261119-0911-0C2D", "K-20261119-0912-0E3F"


@pytest.fixture
def dienst(monkeypatch, tmp_path):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path / "daten"))
    with Attrappe() as a:
        monkeypatch.setenv(W.ADRESSE_VARIABLE, a.adresse)
        monkeypatch.setenv(W.SCHLUESSEL_VARIABLE, a.schluessel)
        yield a


def _ablage(tmp_path) -> list[str]:
    ordner = tmp_path / "daten" / "webanfragen"
    return sorted(p.name for p in ordner.iterdir()) if ordner.exists() else []


def _stand(db) -> WebanfragenAbholung:
    db.expire_all()
    return db.get(WebanfragenAbholung, 1)


def test_abholen_legt_an_und_meldet(db_session, dienst, tmp_path):
    dienst.dazu(muster(R1, "reparatur", fotos=2))
    dienst.dazu(muster(K1, "kantservice"))
    erg = W.abholen(db_session)
    assert (erg.neu, erg.gemeldet, erg.fehler, erg.nicht_abgeholt) == (2, 2, None, [])
    zeilen = {z.nummer: z for z in db_session.scalars(select(WebAnfrage).order_by(WebAnfrage.id))}
    assert set(zeilen) == {R1, K1}
    r = zeilen[R1]
    assert (r.art, r.art_name, r.fassung, r.status, r.kontakt_name, r.spamverdacht, r.pruefen_grund) == (
        "reparatur", "Reparatur-Anfrage", "dk-anfrage/1", "neu", "Max Muster", False, None)
    assert r.eingang_am == datetime(2026, 11, 19, 9, 10)
    assert [(d.name, d.typ) for d in r.dateien] == [("anfrage.pdf", "application/pdf"), ("foto-1.jpg", "image/jpeg"), ("foto-2.jpg", "image/jpeg")]
    for d in r.dateien:
        inhalt = W.datei_pfad(d).read_bytes()
        assert hashlib.sha256(inhalt).hexdigest() == d.sha256 == hashlib.sha256(dienst.anfragen[R1]["dateien"][d.name]).hexdigest()
        assert d.groesse == len(inhalt) and W.ABLAGENAME.match(d.gespeichert_als)
    assert json.loads(r.umschlag)["nr"] == R1 and r.umschlag_sha256 == hashlib.sha256(r.umschlag.encode("utf-8")).hexdigest()
    assert dienst.uebernommen == {R1: f"eingang-{r.id}", K1: f"eingang-{zeilen[K1].id}"}
    assert r.gemeldet_am is not None
    s = _stand(db_session)
    assert (s.letzte_neu, s.letzter_fehler, s.lauf_kennung, s.lauf_seit) == (2, None, None, None)
    assert s.letzter_erfolg_am is not None


def test_nie_doppelt(db_session, dienst):
    dienst.dazu(muster(R1, fotos=1))
    W.abholen(db_session)
    dienst.uebernommen.clear()  # der Empfangsdienst hat den Vermerk verloren: die Anfrage steht wieder in der Liste
    erg = W.abholen(db_session)
    assert (erg.neu, erg.gemeldet) == (0, 1)
    assert db_session.scalar(select(WebAnfrage.id).where(WebAnfrage.nummer == R1)) is not None
    assert len(db_session.scalars(select(WebAnfrage)).all()) == 1
    assert sum(1 for m, p, _ in dienst.aufrufe if m == "GET" and p == f"/erp/v1/anfragen/{R1}") == 1  # der Umschlag nur einmal geholt


@pytest.mark.parametrize("stoerung,grund", [
    ("pruefsumme", W.G_PRUEFSUMME),
    ("groesse", W.G_GROESSE),
    ("typ", W.G_TYP),
    ("fehlt", W.G_DATEI_FEHLT),
])
def test_datei_stimmt_nicht_nichts_ablegen_nichts_melden(db_session, dienst, tmp_path, stoerung, grund):
    a = muster(R1, fotos=2)
    angabe = a["umschlag"]["dateien"][2]  # foto-2.jpg
    if stoerung == "pruefsumme":
        angabe["sha256"] = "0" * 64
    elif stoerung == "groesse":
        angabe["bytes"] += 1
    elif stoerung == "typ":  # HTML statt JPEG, Prüfsumme und Größe passend
        a["dateien"]["foto-2.jpg"] = b"<html><script>alert(1)</script></html>"
        angabe["bytes"], angabe["sha256"] = len(a["dateien"]["foto-2.jpg"]), hashlib.sha256(a["dateien"]["foto-2.jpg"]).hexdigest()
    else:
        del a["dateien"]["foto-2.jpg"]
    dienst.dazu(a)
    erg = W.abholen(db_session)
    assert (erg.neu, erg.gemeldet, erg.fehler) == (0, 0, None)
    assert erg.nicht_abgeholt == [{"nummer": R1, "grund": grund}]
    assert db_session.scalars(select(WebAnfrage)).all() == [] and db_session.scalars(select(WebAnfrageDatei)).all() == []
    assert _ablage(tmp_path) == []  # auch die schon geholten Dateien sind wieder weg
    assert dienst.uebernommen == {}
    assert json.loads(_stand(db_session).nicht_abgeholt) == [{"nummer": R1, "grund": grund}]
    # Im nächsten Lauf kommt sie wieder -- stimmt die Datei dann, wird sie abgelegt
    dienst.dazu(muster(R1, fotos=2))
    assert W.abholen(db_session).neu == 1


def test_zu_grosse_datei(db_session, dienst, tmp_path, monkeypatch):
    monkeypatch.setattr(W, "DATEI_MAX", 1000)
    a = muster(R1, fotos=1)
    for angabe in a["umschlag"]["dateien"]:
        angabe["bytes"] = 900  # die Angaben lügen -- gelesen wird trotzdem nur bis zur Grenze
    dienst.dazu(a)
    erg = W.abholen(db_session)
    assert erg.nicht_abgeholt == [{"nummer": R1, "grund": W.G_ZU_GROSS}] and _ablage(tmp_path) == []


def test_zu_grosse_datei_ohne_laengenangabe(db_session, dienst, tmp_path, monkeypatch):
    """Ohne Content-Length greift die Grenze beim Lesen selbst."""
    monkeypatch.setattr(W, "DATEI_MAX", 1000)
    a = muster(R1)
    a["umschlag"]["dateien"][0]["bytes"] = 900
    dienst.dazu(a)
    dienst.stoerung["ohne_laenge"] = (R1, "anfrage.pdf")
    erg = W.abholen(db_session)
    assert erg.nicht_abgeholt == [{"nummer": R1, "grund": W.G_ZU_GROSS}] and _ablage(tmp_path) == []


def test_zu_grosse_liste_ohne_laengenangabe(db_session, dienst, monkeypatch):
    monkeypatch.setattr(W, "LISTE_MAX", 100)
    dienst.stoerung["liste_roh"] = json.dumps({"ok": True, "anfragen": [{"nr": R1}] * 20, "weitere": False}).encode()
    dienst.stoerung["ohne_laenge"] = "liste"
    assert W.abholen(db_session).fehler == W.UNLESBAR


def test_zu_gross_angekuendigt_in_die_pruefliste(db_session, dienst, monkeypatch):
    monkeypatch.setattr(W, "DATEI_MAX", 1000)
    dienst.dazu(muster(R1, fotos=1))  # die echten Angaben liegen über der Grenze: nichts angefragt, Prüfliste
    erg = W.abholen(db_session)
    zeile = db_session.scalar(select(WebAnfrage))
    assert (erg.neu, zeile.pruefen_grund, zeile.dateien) == (1, W.P_DATEIEN, [])
    assert not any("/dateien/" in p for _, p, _ in dienst.aufrufe)


def test_dateiname_nie_als_pfad(db_session, dienst, tmp_path):
    a = muster(R1, fotos=1)
    a["umschlag"]["dateien"][1]["name"] = "../../boese.jpg"
    a["umschlag"]["dateien"][0]["pfad"] = "http://example.invalid/fremd.pdf"
    dienst.dazu(a)
    erg = W.abholen(db_session)
    zeile = db_session.scalar(select(WebAnfrage))
    assert erg.neu == 1 and zeile.pruefen_grund == W.P_DATEIEN and zeile.dateien == []  # in die Prüfliste, ohne Dateien
    assert not any("dateien" in p for _, p, _ in dienst.aufrufe)  # keine Datei angefragt, auch nicht über „pfad“
    assert not (tmp_path / "boese.jpg").exists() and _ablage(tmp_path) == []


def test_angegebener_pfad_wird_nie_benutzt(db_session, dienst):
    a = muster(R1, fotos=1)
    for d in a["umschlag"]["dateien"]:
        d["pfad"] = "/erp/v1/anfragen/ANDERE/dateien/x"
    dienst.dazu(a)
    W.abholen(db_session)
    assert sorted(p for m, p, _ in dienst.aufrufe if "/dateien/" in p) == [f"/erp/v1/anfragen/{R1}/dateien/anfrage.pdf",
                                                                           f"/erp/v1/anfragen/{R1}/dateien/foto-1.jpg"]


def test_unbekannte_art_in_die_pruefliste(db_session, dienst):
    a = muster("X-20261119-0913-0A0A", "reparatur", fotos=1)
    a["umschlag"]["art"] = "kranmiete"
    dienst.dazu(a)
    erg = W.abholen(db_session)
    zeile = db_session.scalar(select(WebAnfrage))
    assert (erg.neu, erg.pruefen, zeile.art, zeile.pruefen_grund, len(zeile.dateien)) == (1, 1, "kranmiete", W.P_ART, 2)
    assert dienst.uebernommen == {"X-20261119-0913-0A0A": f"eingang-{zeile.id}"}


def test_unbekannte_fassung_in_die_pruefliste_ohne_dateien(db_session, dienst):
    a = muster(R1, fotos=1)
    a["umschlag"]["schema"] = "dk-anfrage/2"
    dienst.dazu(a)
    erg = W.abholen(db_session)
    zeile = db_session.scalar(select(WebAnfrage))
    assert (erg.neu, zeile.fassung, zeile.pruefen_grund, zeile.dateien) == (1, "dk-anfrage/2", W.P_FASSUNG, [])
    assert not any("dateien" in p for _, p, _ in dienst.aufrufe)


@pytest.mark.parametrize("feld,wert,grund", [
    ("betreff", "x" * 256, W.P_BETREFF),
    ("betreff", "Zeile\u0000Null", W.P_BETREFF),
    ("zeit", "gestern", W.P_EINGANG),
    ("zeit", 4_000_000_000, W.P_EINGANG),
    ("art_name", ["keine", "Zeichenkette"], W.P_ART_NAME),
])
def test_ungueltige_angaben_in_die_pruefliste(db_session, dienst, feld, wert, grund):
    a = muster(R1)
    a["umschlag"][feld] = wert
    dienst.dazu(a)
    W.abholen(db_session)
    zeile = db_session.scalar(select(WebAnfrage))
    assert zeile.pruefen_grund == grund and getattr(zeile, {"zeit": "eingang_am"}.get(feld, feld)) is None


def test_zu_langer_name_in_die_pruefliste(db_session, dienst):
    a = muster(R1)
    a["umschlag"]["kontakt"]["name"] = "N" * 300
    dienst.dazu(a)
    W.abholen(db_session)
    zeile = db_session.scalar(select(WebAnfrage))
    assert (zeile.kontakt_name, zeile.pruefen_grund) == (None, W.P_NAME)
    assert json.loads(zeile.umschlag)["kontakt"]["name"] == "N" * 300  # der Umschlag bleibt unverändert


def test_spamverdacht_steht_am_eingang(db_session, dienst):
    dienst.dazu(muster(R1, spam=True))
    W.abholen(db_session)
    assert db_session.scalar(select(WebAnfrage.spamverdacht)) is True


def test_nummer_ungueltig_wird_nie_angefragt(db_session, dienst):
    dienst.stoerung["liste_extra"] = ["../../etc/passwd", "R-1"]
    dienst.dazu(muster(R1))
    erg = W.abholen(db_session)
    assert erg.neu == 1 and [x["grund"] for x in erg.nicht_abgeholt] == [W.G_NUMMER, W.G_NUMMER]
    assert all(".." not in p for _, p, _ in dienst.aufrufe)


@pytest.mark.parametrize("roh", [b"kein json", b"[" * 5000 + b"]" * 5000, json.dumps({"ok": True, "anfragen": [[0] * 30000]}).encode(),
                                 json.dumps({"ok": False}).encode(), b"\xff\xfe"],
                         ids=["kein_json", "tief", "zu_viele_teile", "nicht_ok", "kein_utf8"])
def test_liste_unlesbar_ohne_ausnahme(db_session, dienst, roh):
    dienst.stoerung["liste_roh"] = roh
    erg = W.abholen(db_session)
    assert (erg.fehler, erg.neu) == (W.UNLESBAR, 0) and _stand(db_session).letzter_fehler == W.UNLESBAR


def test_zu_grosse_liste(db_session, dienst, monkeypatch):
    monkeypatch.setattr(W, "LISTE_MAX", 100)
    dienst.dazu(muster(R1))
    dienst.dazu(muster(R2))
    assert W.abholen(db_session).fehler == W.UNLESBAR


def test_umschlag_unlesbar_nicht_abgeholt(db_session, dienst):
    dienst.dazu(muster(R1))
    dienst.stoerung["umschlag_roh"] = {R1: b"{\"nr\": "}
    erg = W.abholen(db_session)
    assert erg.nicht_abgeholt == [{"nummer": R1, "grund": W.G_UNLESBAR}] and dienst.uebernommen == {}


def test_umschlag_mit_anderer_nummer(db_session, dienst):
    a = muster(R1)
    dienst.dazu(a)
    dienst.stoerung["umschlag_roh"] = {R1: json.dumps(dict(a["umschlag"], nr=R2)).encode()}
    erg = W.abholen(db_session)
    assert erg.nicht_abgeholt == [{"nummer": R1, "grund": W.G_NUMMER_ANDERS}] and erg.neu == 0


class _Mithoerer:
    """Ein zweiter Dienst als Ziel einer Umleitung: merkt sich, ob ein Schlüssel ankam."""

    def __init__(self):
        self.kopfzeilen: list[str] = []
        mithoerer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):  # noqa: N802
                mithoerer.kopfzeilen.append(self.headers.get("Authorization") or "")
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def test_umleitung_nie_gefolgt(db_session, dienst):
    m = _Mithoerer()
    try:
        dienst.stoerung["umleitung"] = f"http://127.0.0.1:{m.server.server_address[1]}/fremd"
        erg = W.abholen(db_session)
    finally:
        m.stop()
    assert erg.fehler == W.UMLEITUNG and m.kopfzeilen == []


def test_proxy_der_umgebung_nie_benutzt(db_session, dienst, monkeypatch):
    """Ein Proxy aus der Umgebung (http_proxy) bekäme sonst jeden Aufruf samt Schlüssel."""
    m = _Mithoerer()
    try:
        for name in ("http_proxy", "HTTP_PROXY"):
            monkeypatch.setenv(name, f"http://127.0.0.1:{m.server.server_address[1]}")
        for name in ("no_proxy", "NO_PROXY"):
            monkeypatch.delenv(name, raising=False)
        dienst.dazu(muster(R1))
        erg = W.abholen(db_session)
    finally:
        m.stop()
    assert m.kopfzeilen == [] and erg.neu == 1


def test_ausfall_mitten_in_einer_datei(db_session, dienst, tmp_path):
    dienst.dazu(muster(K1, "kantservice"))
    dienst.dazu(muster(R1, fotos=2))  # nach K1 einsortiert (K < R)
    dienst.stoerung["abbruch_datei"] = (R1, "foto-2.jpg")
    erg = W.abholen(db_session)
    assert (erg.fehler, erg.neu, erg.nicht_abgeholt) == (None, 1, [{"nummer": R1, "grund": W.G_UNVOLLSTAENDIG}])
    assert [z.nummer for z in db_session.scalars(select(WebAnfrage))] == [K1]  # K1 vollständig, R1 gar nicht
    zeile = db_session.scalar(select(WebAnfrage))
    assert _ablage(tmp_path) == sorted(d.gespeichert_als for d in zeile.dateien)  # keine Datei von R1, keine .teil
    assert dienst.uebernommen == {K1: f"eingang-{zeile.id}"}
    assert _stand(db_session).lauf_kennung is None  # Sperre freigegeben


def test_empfangsdienst_aus(db_session, dienst):
    dienst.stop()
    erg = W.abholen(db_session)
    assert erg.fehler == W.NICHT_ERREICHBAR and _stand(db_session).letzter_fehler == W.NICHT_ERREICHBAR
    assert _stand(db_session).letzter_erfolg_am is None


def test_falscher_schluessel(db_session, dienst, monkeypatch):
    monkeypatch.setenv(W.SCHLUESSEL_VARIABLE, "f" * 64)
    dienst.dazu(muster(R1))
    erg = W.abholen(db_session)
    assert erg.fehler == W.ABGELEHNT and erg.neu == 0


def test_schluessel_nie_in_stand_ergebnis_protokoll(db_session, dienst, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    dienst.dazu(muster(R1, fotos=1))
    a = muster(R2)
    a["umschlag"]["dateien"][0]["sha256"] = "0" * 64
    dienst.dazu(a)
    erg = W.abholen(db_session)
    monkeypatch.setenv(W.SCHLUESSEL_VARIABLE, "e" * 64)  # zweiter Lauf: abgelehnt
    erg2 = W.abholen(db_session)
    texte = [repr(erg), repr(erg2), json.dumps(erg.als_dict()), json.dumps(W.stand(db_session), default=str), caplog.text,
             repr(W.verbindung()[0])]
    assert all(dienst.schluessel not in t and "e" * 64 not in t for t in texte)


@pytest.mark.parametrize("adresse", ["http://example.org:8095", "https://127.0.0.1:8095", "http://nutzer:pw@127.0.0.1:8095",
                                     "http://127.0.0.1:8095/erp", "http://127.0.0.1.example.org", "ftp://127.0.0.1", "http://[::1"])
def test_adresse_nur_auf_diesem_server(db_session, dienst, monkeypatch, adresse):
    monkeypatch.setenv(W.ADRESSE_VARIABLE, adresse)
    erg = W.abholen(db_session)
    assert erg.fehler == W.NICHT_LOKAL and dienst.aufrufe == []


@pytest.mark.parametrize("schluessel", ["", "kurz", "x" * 40 + "\r\nX-Real-IP: 1", "ä" * 40])
def test_ohne_gueltigen_schluessel_nicht_eingerichtet(db_session, dienst, monkeypatch, schluessel):
    monkeypatch.setenv(W.SCHLUESSEL_VARIABLE, schluessel)
    erg = W.abholen(db_session)
    assert erg.fehler == W.NICHT_EINGERICHTET and dienst.aufrufe == []
    assert W.stand(db_session)["eingerichtet"] is False


def test_adresse_vorgabe():
    assert W.adresse_pruefen(W.ADRESSE_VORGABE) == "http://127.0.0.1:8095"
    assert W.adresse_pruefen("http://localhost:8095/") == "http://localhost:8095"
    assert W.adresse_pruefen("http://[::1]:8095") == "http://[::1]:8095"


def test_sperre_zwei_laeufe_nie_zugleich(db_session, dienst):
    dienst.dazu(muster(R1))
    s = _stand(db_session)
    s.lauf_kennung, s.lauf_seit = "anderer-lauf", datetime.utcnow() - timedelta(minutes=9)  # gilt 10 Minuten
    db_session.commit()
    erg = W.abholen(db_session)
    assert erg.laeuft_schon is True and dienst.aufrufe == [] and _stand(db_session).lauf_kennung == "anderer-lauf"
    s = _stand(db_session)
    s.lauf_seit = datetime.utcnow() - timedelta(minutes=11)  # liegen geblieben
    db_session.commit()
    assert W.abholen(db_session).neu == 1 and _stand(db_session).lauf_kennung is None


def test_melden_gescheitert_wird_nachgeholt(db_session, dienst):
    dienst.dazu(muster(R1))
    dienst.stoerung["melden_status"] = 500
    erg = W.abholen(db_session)
    zeile = db_session.scalar(select(WebAnfrage))
    assert (erg.neu, erg.gemeldet, zeile.gemeldet_am) == (1, 0, None)
    del dienst.stoerung["melden_status"]
    erg = W.abholen(db_session)
    db_session.refresh(zeile)
    assert (erg.neu, erg.gemeldet) == (0, 1) and zeile.gemeldet_am is not None and dienst.uebernommen == {R1: f"eingang-{zeile.id}"}


def test_hoechstens_je_lauf_und_seiten(db_session, dienst, monkeypatch):
    monkeypatch.setattr(W, "SEITE", 2)
    for i in range(5):
        dienst.dazu(muster(f"R-20261119-09{i:02d}-0A0{i}"))
    erg = W.abholen(db_session, hoechstens=3)
    assert (erg.neu, erg.weitere) == (3, True)
    erg = W.abholen(db_session, hoechstens=3)
    assert (erg.neu, erg.weitere) == (2, False)
    assert len(dienst.uebernommen) == 5


def test_frist_des_knopfs(db_session, dienst):
    dienst.dazu(muster(R1))
    dienst.dazu(muster(R2))
    erg = W.abholen(db_session, frist_sekunden=0.000001)
    assert erg.neu <= 1 and erg.weitere is True


def test_nicht_eingerichtet_ohne_schluessel_schreibt_stand(db_session, monkeypatch):
    monkeypatch.delenv(W.SCHLUESSEL_VARIABLE, raising=False)
    erg = W.abholen(db_session)
    assert erg.fehler == W.NICHT_EINGERICHTET and _stand(db_session).letzter_fehler == W.NICHT_EINGERICHTET


def test_datei_pfad_nur_fuer_eigene_namen(tmp_path, monkeypatch):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path))
    for name in ["../x.pdf", "a" * 32 + ".exe", "anfrage.pdf"]:
        with pytest.raises(ValueError):
            W.datei_pfad(WebAnfrageDatei(gespeichert_als=name))


def test_jpeg_der_attrappe_ist_ein_bild():
    assert jpeg_bytes().startswith(b"\xff\xd8\xff")


# --- Skript des Timers --------------------------------------------------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent


def test_skript_ohne_database_url_bricht_ab(monkeypatch, capsys):
    """Ohne DATABASE_URL nie still gegen eine SQLite-Datei (Vorfall 1): Rückgabe 2, app.database wird gar nicht erst geladen."""
    from scripts import webanfragen_abholen as S
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert S.main() == 2
    assert "DATABASE_URL fehlt" in capsys.readouterr().err


def test_skript_holt_ab(dienst, tmp_path):
    """Ein echter Lauf als Kindprozess gegen eine Wegwerf-SQLite (nie die echte Datenbank, Regel 16)."""
    import os
    import subprocess
    import sys

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.grunddaten import anlegen
    from tests.pg_schutz import pg_url_pruefen

    url = f"sqlite:///{(tmp_path / 'skript.db').as_posix()}"
    engine = create_engine(url)
    try:
        Base.metadata.create_all(engine)
        with sessionmaker(bind=engine)() as db:
            anlegen(db)
        dienst.dazu(muster(R1, fotos=1))
        umgebung = dict(os.environ, DATABASE_URL=pg_url_pruefen(url), ERP_ENV="test", PYTHONIOENCODING="utf-8")
        lauf = subprocess.run([sys.executable, str(ROOT / "scripts" / "webanfragen_abholen.py")], env=umgebung, cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert lauf.returncode == 0, lauf.stderr[-2000:]
        assert dienst.schluessel not in lauf.stdout + lauf.stderr
        with sessionmaker(bind=engine)() as db:
            assert db.scalar(select(WebAnfrage.nummer)) == R1
        assert dienst.uebernommen.keys() == {R1}
        umgebung[W.SCHLUESSEL_VARIABLE] = "d" * 64  # abgelehnt: Rückgabe 1
        lauf = subprocess.run([sys.executable, str(ROOT / "scripts" / "webanfragen_abholen.py")], env=umgebung, cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert lauf.returncode == 1 and "d" * 64 not in lauf.stdout + lauf.stderr
    finally:
        engine.dispose()


# --- PostgreSQL (Wegwerf-Schema, Regel 27) ---------------------------------------------------------------------------------------------------

def test_postgresql_lauf_sperre_und_nummer(dienst, tmp_path):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker

    from tests.befund_vor_echtbetrieb import pg_sitzung

    with pg_sitzung("webanfragen") as db:
        dienst.dazu(muster(R1, fotos=2))
        dienst.dazu(muster(K1, "kantservice"))
        erg = W.abholen(db)
        assert (erg.neu, erg.gemeldet, erg.fehler) == (2, 2, None)
        assert sorted(db.scalars(select(WebAnfrage.nummer))) == [K1, R1]
        assert len(db.scalars(select(WebAnfrageDatei)).all()) == 4
        zweite = sessionmaker(bind=db.get_bind())()
        try:
            assert W._sperre_nehmen(db, datetime.utcnow()) is not None
            assert W._sperre_nehmen(zweite, datetime.utcnow()) is None  # belegt: die zweite Sitzung bekommt die Sperre nicht
            assert W.abholen(zweite).laeuft_schon is True
            zweite.add(WebAnfrage(nummer=R1, fassung="dk-anfrage/1", umschlag="{}", umschlag_sha256="0" * 64))
            with pytest.raises(IntegrityError):
                zweite.commit()
        finally:
            zweite.rollback()
            zweite.close()


# --- Migration -------------------------------------------------------------------------------------------------------------------------------

def _migration():
    import importlib.util
    pfad = next((ROOT / "alembic" / "versions").glob("*_webanfragen_eingang.py"))
    spec = importlib.util.spec_from_file_location("migration_webanfragen", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_downgrade_bricht_mit_eingang_ab(db_session):
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import inspect

    from app.webanfragen import STATUS_NEU

    modul = _migration()
    db_session.add(WebAnfrage(nummer=R1, fassung="dk-anfrage/1", umschlag="{}", umschlag_sha256="0" * 64, status=STATUS_NEU))
    db_session.commit()
    conn = db_session.connection()
    with Operations.context(MigrationContext.configure(conn)):
        with pytest.raises(RuntimeError, match="nicht leer"):
            modul.downgrade()
    assert "webanfragen" in inspect(conn).get_table_names()
    db_session.query(WebAnfrage).delete()
    db_session.commit()
    conn = db_session.connection()
    with Operations.context(MigrationContext.configure(conn)):
        modul.downgrade()
    assert not {"webanfragen", "webanfrage_dateien", "webanfragen_abholung"} & set(inspect(conn).get_table_names())
