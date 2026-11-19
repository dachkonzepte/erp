"""Version 1.10.3 (Stufe W1b): Anzeige der Anfragen der Webseite nach den Funden aus echten Anfragen -- nur Musterdaten.

    Adresse     die Adresse des Objekts nur aus den strukturierten Angaben (app/webanfrage_angaben.py::objekt_adresse()): Reparatur und Wartung
                daten.objekt, Dach und PV daten.strasse/plz/ort, Kantservice keine; nie aus Betreff oder Nachricht; Fremddaten außerhalb der Grenzen
                zählen nicht. Abholen füllt die Spalten, Liste und Anfrage zeigen sie oben.
    Abschnitte  nur die der Art, nur mit Inhalt -- der echte Dienst schickt positionen [] und aufmass false bei jeder Art
    Nachricht   wiederholt sie nur die Angaben (Reparatur, Wartung), eingeklappt; sonst offen
    Zeit        Nummer und Eingang des Empfangsdienstes in Europe/Berlin; das ERP zeigt den Eingang in Berlin -- gleich der Minute der Nummer, auch im Sommer
    Attrappe    Aufbau und Zeitformat wie der echte Dienst (Liste mit Kopfdaten nach Minute und Nummer, Eingang mit Versatz)
    Migration   994be7557612 füllt die Spalten des Bestands aus dem Umschlag (SQLite und PostgreSQL), downgrade() nimmt sie wieder weg
"""

import importlib.util
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app import webanfragen as W
from app.models import WebAnfrage
from app.routers import webanfragen as router_modul
from app.webanfrage_angaben import abschnitte, adresse_text, nachricht_wiederholt, objekt_adresse, reparatur_text
from scripts.empfangsdienst_attrappe import Attrappe, muster
from tests.test_v334_auswahl_restfaelle import NODE, im_browser, nur_mit_node, seite
from tests.test_v447_auswahl_altwerte import WIRKSAM

ROOT = Path(__file__).resolve().parent.parent
BERLIN = ZoneInfo("Europe/Berlin")
BOESE = '<img src=x onerror="alert(1)">'
ARTEN = ("reparatur", "wartung", "dach", "pv", "kantservice")


@pytest.fixture
def dienst(monkeypatch, tmp_path):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path / "daten"))
    with Attrappe() as a:
        monkeypatch.setenv(W.ADRESSE_VARIABLE, a.adresse)
        monkeypatch.setenv(W.SCHLUESSEL_VARIABLE, a.schluessel)
        yield a


# --- Adresse des Objekts ---------------------------------------------------------------------------------------------------------------------

def test_adresse_je_art():
    erwartet = {"strasse": "Musterweg 1", "plz": "00000", "ort": "Musterstadt"}
    for art in ("reparatur", "wartung", "dach", "pv"):
        assert objekt_adresse(art, muster(art=art)["umschlag"]) == erwartet, art
    assert objekt_adresse("kantservice", muster(art="kantservice")["umschlag"]) is None  # Kantservice: kein Objekt, nur ein freies Feld „Ort“
    assert objekt_adresse("dach", muster(art="dach", adresse=False)["umschlag"]) is None  # beim Konfigurator freiwillig
    assert adresse_text(erwartet) == "Musterweg 1, 00000 Musterstadt" and adresse_text(None) is None
    assert adresse_text({"strasse": None, "plz": "00000", "ort": "Musterstadt"}) == "00000 Musterstadt"


def test_adresse_nie_aus_betreff_oder_nachricht():
    u = muster(art="dach", adresse=False)["umschlag"]
    u["betreff"] = "Werkstraße 6b – Flachdach"
    u["text"] = "Anschrift des Hauses: Werkstraße 6b, 00000 Musterstadt"
    u["kontakt"]["ort"] = "Werkstraße 6b, 00000 Musterstadt"  # abgeleitet, kein strukturiertes Feld des Objekts
    assert objekt_adresse("dach", u) is None
    k = muster(art="kantservice")["umschlag"]
    k["daten"] = {"strasse": "Werkstraße 6b", "plz": "00000", "ort": "Musterstadt"}  # Kantservice hat keine Adresse -- auch nicht untergeschoben
    assert objekt_adresse("kantservice", k) is None


def test_adresse_nur_gueltige_fremddaten():
    u = muster(art="reparatur")["umschlag"]
    u["daten"]["objekt"].update(strasse="x" * 101, plz=12345, ort="Muster\u0000stadt")
    assert objekt_adresse("reparatur", u) is None  # zu lang, keine Zeichenkette, Steuerzeichen: alles verworfen, kein Fehler
    u["daten"]["objekt"]["strasse"] = "  Musterweg   1  "
    assert objekt_adresse("reparatur", u) == {"strasse": "Musterweg 1", "plz": None, "ort": None}
    u["daten"]["schema"] = "dk-reparatur/2"
    assert objekt_adresse("reparatur", u) is None  # andere Fassung: nichts geraten
    for kaputt in (None, {}, {"daten": "x"}, {"daten": {"objekt": []}}, {"daten": {"schema": "dk-reparatur/1", "objekt": "x"}}):
        assert objekt_adresse("reparatur", kaputt) is None and objekt_adresse("dach", kaputt) is None


def test_abholen_fuellt_die_adresse(db_session, dienst):
    for i, art in enumerate(ARTEN):
        dienst.dazu(muster(art=art, eingang=datetime(2026, 11, 19, 9, 10 + i, 5, tzinfo=BERLIN)))
    assert W.abholen(db_session).neu == 5
    zeilen = {z.art: z for z in db_session.scalars(select(WebAnfrage))}
    for art in ("reparatur", "wartung", "dach", "pv"):
        assert (zeilen[art].objekt_strasse, zeilen[art].objekt_plz, zeilen[art].objekt_ort) == ("Musterweg 1", "00000", "Musterstadt"), art
    assert (zeilen["kantservice"].objekt_strasse, zeilen["kantservice"].objekt_plz, zeilen["kantservice"].objekt_ort) == (None, None, None)
    zeile = W.zeile_zu_dict(zeilen["dach"])
    assert (zeile["objekt_strasse"], zeile["objekt_plz"], zeile["objekt_ort"]) == ("Musterweg 1", "00000", "Musterstadt") and "umschlag" not in zeile


# --- Abschnitte je Art ----------------------------------------------------------------------------------------------------------------------

def test_abschnitte_nur_der_art_und_mit_inhalt():
    erwartet = {"reparatur": ["reparatur"], "wartung": ["reparatur"], "dach": ["konfigurator"], "pv": ["konfigurator"], "kantservice": ["kantservice"]}
    for art in ARTEN:
        u = muster(art=art)["umschlag"]
        assert ("positionen" in u, "aufmass" in u) == (True, True)  # wie der echte Dienst: jede Art trägt beide Felder
        assert abschnitte(art, u) == erwartet[art], art
    k = muster(art="kantservice")["umschlag"]
    k["positionen"] = []
    assert abschnitte("kantservice", k) == []  # ohne Positionen und ohne Aufmaß: kein Abschnitt
    k["aufmass"] = True
    assert abschnitte("kantservice", k) == ["kantservice"]
    r = muster(art="reparatur")["umschlag"]
    r["positionen"], r["aufmass"] = [{"x": 1}], True
    assert abschnitte("reparatur", r) == ["reparatur"]  # Positionen gehören nur zum Kantservice
    assert abschnitte("dach", {"daten": {}}) == [] and abschnitte(None, {"daten": {"x": 1}}) == ["weitere"]
    r["daten"]["schema"] = "dk-reparatur/2"
    assert abschnitte("reparatur", r) == ["weitere"]


def test_detail_nennt_abschnitte_und_nachricht(dienst, router_test_client, threaded_db_session):
    for i, art in enumerate(ARTEN):
        dienst.dazu(muster(art=art, eingang=datetime(2026, 11, 19, 9, 10 + i, 5, tzinfo=BERLIN)))
    W.abholen(threaded_db_session)
    c = router_test_client(threaded_db_session, router_modul.router, role="buero_auftrag")
    ids = {z.art: z.id for z in threaded_db_session.scalars(select(WebAnfrage))}
    for art, (teile, wiederholt) in {"reparatur": (["reparatur"], True), "wartung": (["reparatur"], True), "dach": (["konfigurator"], False),
                                     "pv": (["konfigurator"], False), "kantservice": (["kantservice"], False)}.items():
        d = c.get(f"/api/webanfragen/{ids[art]}").json()
        assert (d["abschnitte"], d["nachricht_wiederholt"]) == (teile, wiederholt), art
    liste = {z["art"]: z for z in c.get("/api/webanfragen").json()}
    assert (liste["pv"]["objekt_strasse"], liste["pv"]["objekt_plz"], liste["pv"]["objekt_ort"]) == ("Musterweg 1", "00000", "Musterstadt")
    assert liste["kantservice"]["objekt_strasse"] is None


# --- Nachricht ------------------------------------------------------------------------------------------------------------------------------

def test_nachricht_wiederholt_nur_die_angaben():
    for art in ("reparatur", "wartung"):
        for rolle, mehr in (("eigentuemer", {}), ("verwaltung", {"firma": "Verwaltung Muster GmbH"}), ("mieter", {"hausverwaltung": "HV Muster"})):
            u = muster(art=art, rolle=rolle, vor_ort={"name": "Erika Muster", "telefon": "0000 1"}, fotos=2, **mehr)["umschlag"]
            assert nachricht_wiederholt(art, u), (art, rolle)
    u = muster(art="reparatur", nachricht="Bitte vorher anrufen, der Hund ist im Garten.")["umschlag"]
    assert not nachricht_wiederholt("reparatur", u)  # eigener Text: offen
    u = muster(art="reparatur")["umschlag"]
    u["text"] = u["text"] + "\nNachtrag: Schlüssel beim Nachbarn."
    assert not nachricht_wiederholt("reparatur", u)
    u = muster(art="reparatur")["umschlag"]
    u["text"] = u["text"].replace("\n", "\r\n") + "  \n"
    assert nachricht_wiederholt("reparatur", u)  # nur Zeilenenden und Leerraum am Ende verschieden
    for art in ("dach", "pv", "kantservice"):
        assert not nachricht_wiederholt(art, muster(art=art, nachricht="Bitte zurückrufen.")["umschlag"]), art
    kaputt = muster(art="reparatur")["umschlag"]
    kaputt["daten"]["melder"] = "x"
    assert not nachricht_wiederholt("reparatur", kaputt) and reparatur_text(kaputt["daten"]) is None  # unpassende Angaben: offen, kein Fehler


# --- Zeit -----------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("eingang", [datetime(2026, 11, 19, 7, 5, 12, tzinfo=BERLIN), datetime(2026, 7, 1, 7, 5, 12, tzinfo=BERLIN)],
                         ids=["winter", "sommer"])
def test_eingang_gleich_der_minute_der_nummer(db_session, dienst, eingang):
    a = muster(art="reparatur", eingang=eingang)
    u = a["umschlag"]
    assert u["nr"][2:15] == eingang.strftime("%Y%m%d-%H%M")  # Nummer in Berlin wie anfrage.py::neue_nr() (TZ=Europe/Berlin)
    assert u["eingang"] == eingang.isoformat()  # mit Versatz, ohne Bruchteile wie zeit_iso()
    dienst.dazu(a)
    W.abholen(db_session)
    zeile = db_session.scalar(select(WebAnfrage))
    assert zeile.eingang_am == eingang.astimezone(timezone.utc).replace(tzinfo=None)  # gespeichert als naives UTC
    if NODE is None:  # ohne node nur der Server-Teil
        return
    tag = im_browser(seite("webanfragen.html", "\nladen().catch("), f"return berlinZeitpunkt({json.dumps(zeile.eingang_am.isoformat())});")["ergebnis"]
    assert tag == eingang.strftime("%d.%m.%Y %H:%M")  # angezeigt in Berlin: dieselbe Minute wie in der Nummer


# --- Attrappe wie der echte Dienst ----------------------------------------------------------------------------------------------------------

def test_attrappe_liste_wie_der_echte_dienst(dienst):
    import urllib.request
    spaet = dienst.dazu(muster("K-20261119-0912-0E3F", "kantservice"))
    frueh = dienst.dazu(muster("R-20261119-0910-0A1B", "reparatur"))
    anfrage = urllib.request.Request(dienst.adresse + "/erp/v1/anfragen", headers={"Authorization": "Bearer " + dienst.schluessel})
    with urllib.request.urlopen(anfrage, timeout=10) as antwort:
        liste = json.loads(antwort.read())
    assert [x["nr"] for x in liste["anfragen"]] == [frueh, spaet]  # nach Minute des Eingangs, dann Nummer (anfrage.py::_erp_folge())
    assert set(liste["anfragen"][0]) == {"schema", "nr", "art", "art_name", "eingang", "zeit", "betreff", "kontakt", "spamverdacht", "uebernommen", "pfad"}
    assert liste["anfragen"][0]["eingang"] == "2026-11-19T09:10:27+01:00" and set(liste["anfragen"][0]["kontakt"]) == {"name"}


# --- Seiten (node) --------------------------------------------------------------------------------------------------------------------------

def _detail(art: str, u: dict, **mehr) -> dict:
    adresse = objekt_adresse(art, u) or {}
    return {"id": 7, "nummer": u["nr"], "art": art, "art_name": u["art_name"], "fassung": "dk-anfrage/1", "eingang_am": "2026-11-19T06:05:12",
            "betreff": u["betreff"], "kontakt_name": u["kontakt"]["name"], "objekt_strasse": adresse.get("strasse"), "objekt_plz": adresse.get("plz"),
            "objekt_ort": adresse.get("ort"), "spamverdacht": False, "pruefen_grund": None, "status": "neu", "abgeholt_am": "2026-11-19T06:06:00",
            "gemeldet_am": None, "dateien": 0, "umschlag": u, "dateiliste": [], "abschnitte": abschnitte(art, u),
            "nachricht_wiederholt": nachricht_wiederholt(art, u), **mehr}


def _seite_detail(d: dict) -> dict:
    ablauf = (f"zeichnen({json.dumps(d)});"
              "return Object.fromEntries(['seitenkopfUntertitel','kontakt','anfrage','angaben'].map(i => [i, _element(i).innerHTML||_element(i).textContent]));")
    return im_browser(seite("webanfrage.html", "\nlesen('anfrage',") + WIRKSAM, ablauf)["ergebnis"]


@nur_mit_node
def test_seite_adresse_oben_ort_nur_beim_kantservice():
    erg = _seite_detail(_detail("reparatur", muster(art="reparatur")["umschlag"]))
    assert erg["seitenkopfUntertitel"].startswith("Objekt: Musterweg 1, 00000 Musterstadt · Eingang 19.11.2026")
    assert "<dt>Objekt</dt><dd>Musterweg 1, 00000 Musterstadt</dd>" in erg["anfrage"]
    assert "<dt>Ort</dt>" not in erg["kontakt"]  # abgeleitet aus dem Objekt -- steht oben
    erg = _seite_detail(_detail("kantservice", muster(art="kantservice")["umschlag"]))
    assert erg["seitenkopfUntertitel"].startswith("Kantservice – ohne Objekt-Adresse")
    assert "<dt>Ort</dt><dd>00000 Musterstadt</dd>" in erg["kontakt"]  # das freie Feld „Ort“ des Kantservice bleibt
    erg = _seite_detail(_detail("dach", muster(art="dach", adresse=False)["umschlag"]))
    assert erg["seitenkopfUntertitel"].startswith("ohne Objekt-Adresse") and "<dt>Ort</dt>" not in erg["kontakt"]


@nur_mit_node
def test_seite_abschnitte_je_art():
    for art in ARTEN:
        erg = _seite_detail(_detail(art, muster(art=art)["umschlag"]))
        angaben = erg["angaben"]
        assert ("Kantteil-Zeichner" in angaben, "Aufmaß vor Ort gewünscht" in angaben) == ((art == "kantservice",) * 2), art
        assert ("Preise und Förderung" in angaben) == (art in ("dach", "pv")), art
        assert ("<dt>Meldet</dt>" in angaben) == (art in ("reparatur", "wartung")), art


@nur_mit_node
def test_seite_nachricht_eingeklappt_nur_wenn_wiederholt():
    erg = _seite_detail(_detail("reparatur", muster(art="reparatur", name=BOESE)["umschlag"]))
    assert '<details class="nachricht"><summary>' in erg["anfrage"] and "<details class=\"nachricht\" open" not in erg["anfrage"]
    assert "<img" not in erg["anfrage"] and "&lt;img" in erg["anfrage"]
    erg = _seite_detail(_detail("reparatur", muster(art="reparatur", nachricht="Bitte vorher anrufen.")["umschlag"]))
    assert "<details" not in erg["anfrage"] and "Bitte vorher anrufen." in erg["anfrage"]
    erg = _seite_detail(_detail("dach", muster(art="dach", nachricht="Bitte zurückrufen.")["umschlag"]))
    assert "<details" not in erg["anfrage"] and "Bitte zurückrufen." in erg["anfrage"]


@nur_mit_node
def test_liste_zeigt_die_adresse():
    zeilen = []
    for i, art in enumerate(ARTEN):
        u = muster(art=art, name=BOESE if art == "pv" else "Max Muster")["umschlag"]
        d = _detail(art, u, id=i + 1)
        d.pop("umschlag"), d.pop("dateiliste"), d.pop("abschnitte"), d.pop("nachricht_wiederholt")
        zeilen.append(d)
    zeilen[2]["objekt_strasse"] = BOESE
    stand = {"eingerichtet": True, "laeuft": False, "letzter_lauf_am": None, "letzter_erfolg_am": None, "letzter_fehler": None, "letzte_neu": 0,
             "nicht_abgeholt": [], "neu": 5, "spamverdacht": 0, "pruefen": 0}
    ablauf = f"stand = {json.dumps(stand)}; liste = {json.dumps(zeilen)}; listeZeichnen(); return _element('listeRahmen').innerHTML;"
    tabelle = im_browser(seite("webanfragen.html", "\nladen().catch(") + WIRKSAM, ablauf)["ergebnis"]
    assert "<th>Objekt</th>" in tabelle and tabelle.count('data-titel="Objekt">Musterweg 1, 00000 Musterstadt</td>') == 3
    assert 'data-titel="Objekt">—</td>' in tabelle  # Kantservice: keine Adresse
    assert "<img" not in tabelle and "&lt;img" in tabelle


# --- Migration auf einem Bestand -------------------------------------------------------------------------------------------------------------

def _modul(teil: str):
    pfad = next((ROOT / "alembic" / "versions").glob(f"*_{teil}.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{teil}", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _bestand_pruefen(conn) -> None:
    """Auf dem Stand vor 994be7557612: Bestand anlegen, upgrade(), Spalten prüfen, downgrade()."""
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    alt, neu = _modul("webanfragen_eingang"), _modul("webanfragen_objekt_adresse")
    with Operations.context(MigrationContext.configure(conn)):
        alt.upgrade()
    zeilen = [("R-20261119-0910-0A1B", "reparatur", json.dumps(muster(art="reparatur", strasse="Bestandweg 2")["umschlag"])),
              ("D-20261119-0911-0A1B", "dach", json.dumps(muster(art="dach")["umschlag"])),
              ("K-20261119-0912-0A1B", "kantservice", json.dumps(muster(art="kantservice")["umschlag"])),
              ("W-20261119-0913-0A1B", "wartung", "{kaputt"),
              ("X-20261119-0914-0A1B", None, json.dumps({"daten": {"strasse": "Fremdweg 3"}}))]
    for nummer, art, umschlag in zeilen:
        conn.execute(text("INSERT INTO webanfragen (nummer, art, fassung, umschlag, umschlag_sha256, status, abgeholt_am, spamverdacht) "
                          "VALUES (:n, :a, 'dk-anfrage/1', :u, :s, 'neu', :t, false)"),
                     {"n": nummer, "a": art, "u": umschlag, "s": "0" * 64, "t": datetime(2026, 11, 19, 8, 0)})
    with Operations.context(MigrationContext.configure(conn)):
        neu.upgrade()
    werte = {r[0]: tuple(r[1:]) for r in conn.execute(text("SELECT nummer, objekt_strasse, objekt_plz, objekt_ort FROM webanfragen ORDER BY id"))}
    assert werte == {"R-20261119-0910-0A1B": ("Bestandweg 2", "00000", "Musterstadt"), "D-20261119-0911-0A1B": ("Musterweg 1", "00000", "Musterstadt"),
                     "K-20261119-0912-0A1B": (None, None, None), "W-20261119-0913-0A1B": (None, None, None), "X-20261119-0914-0A1B": (None, None, None)}
    with Operations.context(MigrationContext.configure(conn)):
        neu.downgrade()
    assert not {"objekt_strasse", "objekt_plz", "objekt_ort"} & {c["name"] for c in inspect(conn).get_columns("webanfragen")}


def test_migration_fuellt_den_bestand_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")
    try:
        with engine.begin() as conn:
            _bestand_pruefen(conn)
    finally:
        engine.dispose()


def test_migration_fuellt_den_bestand_postgresql():
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_w1b_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.begin() as conn:
            _bestand_pruefen(conn)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@nur_mit_node
def test_start_zeigt_die_adresse():
    from tests.test_v774_webanfragen_start import STAND, ZEILE, _widget
    mit = dict(ZEILE, id=8, nummer="R-20261119-0910-0A1B", objekt_strasse="Musterweg 1", objekt_plz="00000", objekt_ort=BOESE)
    html = _widget(STAND, [mit, dict(ZEILE, objekt_strasse=None, objekt_plz=None, objekt_ort=None)])
    assert "R-20261119-0910-0A1B · Musterweg 1, 00000 &lt;img" in html and "<img" not in html
    assert "W-20261119-0912-0E3F · Spamverdacht" in html  # ohne Adresse kein Trenner
