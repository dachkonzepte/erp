"""Version 1.10.4 (Stufe W1b): Prüfliste und Verwerfen der Anfragen der Webseite -- nur Musterdaten, gegen die Attrappe des Empfangsdienstes.

    Prüfliste   Spamverdacht oder ein Grund zum Prüfen, noch neu und noch nicht in den Eingang gegeben -- nicht im Eingang, nicht auf „Start“
    Aktionen    Verwerfen mit festem Grund (neu, auch aus der Prüfliste), In den Eingang (nur aus der Prüfliste), Zurückholen (nur verworfen) -- je ein
                bedingtes UPDATE: zweimal geht nicht (409), eine unbekannte Anfrage 404, ein freier Grund 422; Monteurin 403
    Historie    je Aktion ein Eintrag ohne Inhalte: Nummer, Status alt und neu (beim Verwerfen mit dem Grund)
    Melden      nach dem Verwerfen bekommt der Empfangsdienst „verworfen“ (F2), nach dem Zurückholen wieder eingang-<ID>; direkt nach der Aktion, wenn
                kein Lauf abholt -- sonst und nach einem Fehler meldet der nächste Lauf (auch wenn die Anfrage beim Empfangsdienst nicht mehr gelistet ist)
    Migration   a107b86d8e8d: gemeldete Anfragen des Bestands bekommen gemeldet_als = eingang-<ID>; downgrade() bricht ab, solange etwas erledigt ist
"""

import importlib.util
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app import webanfragen as W
from app.models import AuditLog, WebAnfrage
from app.routers import webanfragen as router_modul
from app.schemas import WebAnfrageVerwerfenIn
from scripts.empfangsdienst_attrappe import Attrappe, muster
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v447_auswahl_altwerte import WIRKSAM

ROOT = Path(__file__).resolve().parent.parent
R1, R2, R3 = "R-20261119-0910-0A1B", "R-20261119-0911-0C2D", "R-20261119-0912-0E3F"
BOESE = '<img src=x onerror="alert(1)">'


@pytest.fixture
def dienst(monkeypatch, tmp_path):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path / "daten"))
    with Attrappe() as a:
        monkeypatch.setenv(W.ADRESSE_VARIABLE, a.adresse)
        monkeypatch.setenv(W.SCHLUESSEL_VARIABLE, a.schluessel)
        yield a


@pytest.fixture
def welt(dienst, threaded_db_session, router_test_client):
    """Drei abgeholte Anfragen: R1 normal, R2 mit Spamverdacht, R3 normal -- und ein Büro-Konto (ID 1) für „von“."""
    dienst.dazu(muster(R1))
    dienst.dazu(muster(R2, spam=True))
    dienst.dazu(muster(R3))
    db = threaded_db_session
    assert W.abholen(db).neu == 3
    c = router_test_client(db, router_modul.router, role="buero_auftrag", user_id=1)
    ids = {z.nummer: z.id for z in db.scalars(select(WebAnfrage))}
    return {"db": db, "c": c, "ids": ids, "dienst": dienst}


def _ids(c, ansicht):
    return [z["nummer"] for z in c.get(f"/api/webanfragen?ansicht={ansicht}").json()]


def test_pruefliste_getrennt_vom_eingang(welt):
    c = welt["c"]
    assert _ids(c, "eingang") == [R3, R1] and _ids(c, "pruefliste") == [R2] and _ids(c, "erledigt") == []
    assert _ids(c, "eingang") == [z["nummer"] for z in c.get("/api/webanfragen").json()]  # Vorgabe: der Eingang
    s = c.get("/api/webanfragen/stand").json()
    assert (s["neu"], s["pruefliste"], s["spamverdacht"], s["pruefen"], s["meldung_offen"]) == (2, 1, 1, 0, 0)
    assert c.get("/api/webanfragen?ansicht=alle").status_code == 422
    d = c.get(f"/api/webanfragen/{welt['ids'][R2]}").json()
    assert (d["zustand"], d["in_pruefliste"], d["verwerfen_gruende"]) == ("pruefliste", True, W.VERWERFEN_GRUENDE)


def test_pruefen_grund_auch_in_der_pruefliste(welt):
    db = welt["db"]
    z = db.get(WebAnfrage, welt["ids"][R1])
    z.pruefen_grund = W.P_ART
    db.commit()
    assert _ids(welt["c"], "pruefliste") == [R2, R1] and _ids(welt["c"], "eingang") == [R3]


def test_in_den_eingang_nur_aus_der_pruefliste(welt):
    c, ids = welt["c"], welt["ids"]
    r = c.post(f"/api/webanfragen/{ids[R2]}/eingang")
    assert r.status_code == 200 and (r.json()["zustand"], r.json()["in_pruefliste"]) == ("neu", False) and r.json()["geprueft_am"]
    assert _ids(c, "eingang") == [R3, R2, R1] and _ids(c, "pruefliste") == []
    assert c.post(f"/api/webanfragen/{ids[R2]}/eingang").status_code == 409  # nicht mehr in der Prüfliste
    assert c.post(f"/api/webanfragen/{ids[R1]}/eingang").status_code == 409  # nie in der Prüfliste
    assert c.post("/api/webanfragen/999999/eingang").status_code == 404


def test_verwerfen_meldet_verworfen(welt):
    c, ids, dienst, db = welt["c"], welt["ids"], welt["dienst"], welt["db"]
    r = c.post(f"/api/webanfragen/{ids[R2]}/verwerfen", json={"grund": "spam"})
    assert r.status_code == 200
    d = r.json()
    assert (d["status"], d["zustand"], d["verworfen_grund"], d["verworfen_grund_text"]) == ("verworfen", "verworfen", "spam", "Spam")
    assert d["erledigt_am"] and (d["melden_soll"], d["gemeldet_als"], d["meldung_offen"]) == ("verworfen", "verworfen", False)
    assert dienst.uebernommen[R2] == "verworfen" and dienst.meldungen[-1] == (R2, "verworfen")
    assert _ids(c, "erledigt") == [R2] and R2 not in _ids(c, "pruefliste") + _ids(c, "eingang")
    assert c.post(f"/api/webanfragen/{ids[R2]}/verwerfen", json={"grund": "spam"}).status_code == 409  # nie zweimal
    assert c.post(f"/api/webanfragen/{ids[R1]}/verwerfen", json={"grund": "frei erfunden"}).status_code == 422
    assert c.post(f"/api/webanfragen/{ids[R1]}/verwerfen", json={}).status_code == 422
    assert c.post("/api/webanfragen/999999/verwerfen", json={"grund": "test"}).status_code == 404
    zeile = db.get(WebAnfrage, ids[R2])
    db.refresh(zeile)
    assert zeile.erledigt_von_user_id == 1


def test_historie_ohne_inhalte(welt):
    c, ids, db = welt["c"], welt["ids"], welt["db"]
    c.post(f"/api/webanfragen/{ids[R2]}/eingang")
    c.post(f"/api/webanfragen/{ids[R2]}/verwerfen", json={"grund": "doppelt"})
    c.post(f"/api/webanfragen/{ids[R2]}/zurueckholen")
    eintraege = db.scalars(select(AuditLog).where(AuditLog.entity_type == W.ART_HISTORIE).order_by(AuditLog.id)).all()
    assert [(e.action, e.entity_id, e.entity_label, e.old_value, e.new_value) for e in eintraege] == [
        ("aus der Prüfliste", str(ids[R2]), R2, "Prüfliste", "Eingang"),
        ("verworfen", str(ids[R2]), R2, "neu", "verworfen (Doppelt)"),
        ("zurückgeholt", str(ids[R2]), R2, "verworfen", "neu")]
    for e in eintraege:  # nichts aus dem Formular: kein Name, keine Adresse, keine E-Mail, kein Betreff
        text_ = json.dumps([e.old_value, e.new_value, e.entity_label, e.details], ensure_ascii=False)
        assert "Muster" not in text_ and "@" not in text_


def test_zurueckholen_meldet_wieder_eingang(welt):
    c, ids, dienst = welt["c"], welt["ids"], welt["dienst"]
    assert c.post(f"/api/webanfragen/{ids[R1]}/zurueckholen").status_code == 409  # nicht verworfen
    c.post(f"/api/webanfragen/{ids[R1]}/verwerfen", json={"grund": "test"})
    d = c.post(f"/api/webanfragen/{ids[R1]}/zurueckholen").json()
    assert (d["status"], d["verworfen_grund"], d["erledigt_am"], d["gemeldet_als"]) == ("neu", None, None, f"eingang-{ids[R1]}")
    assert dienst.meldungen[-2:] == [(R1, "verworfen"), (R1, f"eingang-{ids[R1]}")]
    assert R1 in _ids(c, "eingang")


def test_zurueckgeholt_steht_wieder_wo_sie_war_und_erledigt_nach_zeit(welt):
    c, ids, db = welt["c"], welt["ids"], welt["db"]
    c.post(f"/api/webanfragen/{ids[R2]}/verwerfen", json={"grund": "spam"})
    c.post(f"/api/webanfragen/{ids[R2]}/zurueckholen")
    assert _ids(c, "pruefliste") == [R2]  # Spamverdacht, nie in den Eingang gegeben: wieder in der Prüfliste
    c.post(f"/api/webanfragen/{ids[R1]}/verwerfen", json={"grund": "test"})
    c.post(f"/api/webanfragen/{ids[R3]}/verwerfen", json={"grund": "test"})
    assert _ids(c, "erledigt") == [R3, R1]  # zuletzt erledigt zuerst
    zeile = db.get(WebAnfrage, ids[R1])
    db.refresh(zeile)
    assert zeile.umschlag and len(zeile.dateien) == 1  # verworfen heißt nicht gelöscht (Archiv erst in W1c)


def test_ohne_empfangsdienst_meldet_der_naechste_lauf(welt):
    c, ids, dienst, db = welt["c"], welt["ids"], welt["dienst"], welt["db"]
    dienst.stoerung["melden_status"] = 500
    d = c.post(f"/api/webanfragen/{ids[R3]}/verwerfen", json={"grund": "test"}).json()
    assert (d["status"], d["melden_soll"], d["gemeldet_als"], d["meldung_offen"]) == ("verworfen", "verworfen", f"eingang-{ids[R3]}", True)
    assert c.get("/api/webanfragen/stand").json()["meldung_offen"] == 1
    del dienst.stoerung["melden_status"]
    assert R3 not in [n for n, _ in dienst.meldungen[-1:]] or dienst.meldungen[-1] != (R3, "verworfen")
    erg = W.abholen(db)  # R3 steht beim Empfangsdienst nicht mehr in der Liste (schon übernommen) -- der Lauf meldet sie trotzdem
    assert erg.fehler is None and dienst.uebernommen[R3] == "verworfen"
    zeile = db.get(WebAnfrage, ids[R3])
    db.refresh(zeile)
    assert (zeile.gemeldet_als, W.meldung_offen(zeile)) == ("verworfen", False)


def test_waehrend_eines_laufs_meldet_der_lauf(welt):
    c, ids, dienst, db = welt["c"], welt["ids"], welt["dienst"], welt["db"]
    kennung = W._sperre_nehmen(db, datetime.utcnow())  # ein Lauf hält die Sperre
    try:
        d = c.post(f"/api/webanfragen/{ids[R1]}/verwerfen", json={"grund": "test"}).json()
        assert d["meldung_offen"] is True and dienst.uebernommen[R1] == f"eingang-{ids[R1]}"  # nicht an der Sperre vorbei gemeldet
    finally:
        W._sperre_freigeben(db, kennung, {})
    W.abholen(db)
    assert dienst.uebernommen[R1] == "verworfen"


def test_lauf_meldet_die_gelistete_mit_dem_stand_von_jetzt(welt):
    """Eine Anfrage, die beim Empfangsdienst noch gelistet ist (Meldung gescheitert) und inzwischen verworfen wurde, meldet der Lauf als „verworfen“."""
    c, ids, dienst, db = welt["c"], welt["ids"], welt["dienst"], welt["db"]
    del dienst.uebernommen[R1]  # gelistet wie nie gemeldet
    zeile = db.get(WebAnfrage, ids[R1])
    zeile.gemeldet_als, zeile.gemeldet_am = None, None
    db.commit()
    dienst.stoerung["melden_status"] = 500
    c.post(f"/api/webanfragen/{ids[R1]}/verwerfen", json={"grund": "test"})
    del dienst.stoerung["melden_status"]
    vorher = len(dienst.meldungen)
    W.abholen(db)
    neue = dienst.meldungen[vorher:]
    assert dienst.uebernommen[R1] == "verworfen" and (R1, "verworfen") in neue and (R1, f"eingang-{ids[R1]}") not in neue


def test_monteurin_nirgends(welt, router_test_client):
    c = router_test_client(welt["db"], router_modul.router, role="field")
    i = welt["ids"][R2]
    assert c.get("/api/webanfragen?ansicht=pruefliste").status_code == 403
    assert c.post(f"/api/webanfragen/{i}/verwerfen", json={"grund": "spam"}).status_code == 403
    assert c.post(f"/api/webanfragen/{i}/eingang").status_code == 403
    assert c.post(f"/api/webanfragen/{i}/zurueckholen").status_code == 403


def test_gruende_fest_und_gleich():
    assert set(WebAnfrageVerwerfenIn.model_fields["grund"].annotation.__args__) == set(W.VERWERFEN_GRUENDE)
    assert W.STATUS == ("neu", "verworfen") and W.ERP_ID.match(W.ERP_ID_VERWORFEN)


# --- Seiten (node) --------------------------------------------------------------------------------------------------------------------------

def _detail(**mehr) -> dict:
    u = muster(R1)["umschlag"]
    d = {"id": 7, "nummer": R1, "art": "reparatur", "art_name": "Reparatur-Anfrage", "fassung": "dk-anfrage/1", "eingang_am": "2026-11-19T08:10:27",
         "betreff": None, "kontakt_name": None, "objekt_strasse": "Musterweg 1", "objekt_plz": "00000", "objekt_ort": "Musterstadt", "spamverdacht": False,
         "pruefen_grund": None, "status": "neu", "abgeholt_am": "2026-11-19T08:11:00", "gemeldet_am": "2026-11-19T08:11:00", "dateien": 0,
         "zustand": "neu", "in_pruefliste": False, "erledigt_am": None, "verworfen_grund": None, "verworfen_grund_text": None, "gemeldet_als": "eingang-7",
         "melden_soll": "eingang-7", "meldung_offen": False, "umschlag": u, "dateiliste": [], "abschnitte": ["reparatur"], "nachricht_wiederholt": True,
         "erledigt_von_name": None, "geprueft_am": None, "geprueft_von_name": None, "verwerfen_gruende": dict(W.VERWERFEN_GRUENDE)}
    d.update(mehr)
    return d


def _seite(d: dict) -> dict:
    ablauf = (f"zeichnen({json.dumps(d)});"
              "const z=id=>_element(id);"
              "return {stand:z('bearbeitungStand').textContent, ein:z('inDenEingangKnopf').hidden, weg:z('verwerfenOeffnenKnopf').hidden,"
              " zurueck:z('zurueckholenKnopf').hidden, gruende:z('verwerfenGrund').innerHTML, meldung:z('meldungText').textContent,"
              " status:z('seitenkopfStatus').textContent};")
    return im_browser(seite("webanfrage.html", "\nlesen('anfrage',") + WIRKSAM, ablauf)["ergebnis"]


@nur_mit_node
def test_seite_knoepfe_je_stand():
    neu = _seite(_detail())
    assert (neu["ein"], neu["weg"], neu["zurueck"], neu["status"]) == (True, False, True, "Neu") and neu["stand"].startswith("Im Eingang")
    assert neu["gruende"].startswith('<option value="">Bitte wählen</option>') and '<option value="spam">Spam</option>' in neu["gruende"]
    pruef = _seite(_detail(spamverdacht=True, in_pruefliste=True, zustand="pruefliste"))
    assert (pruef["ein"], pruef["weg"], pruef["zurueck"], pruef["status"]) == (False, False, True, "Prüfliste") and "Spamverdacht" in pruef["stand"]
    weg = _seite(_detail(status="verworfen", zustand="verworfen", verworfen_grund="spam", verworfen_grund_text="Spam", erledigt_am="2026-11-19T09:00:00",
                         erledigt_von_name=BOESE, melden_soll="verworfen", gemeldet_als="verworfen"))
    assert (weg["ein"], weg["weg"], weg["zurueck"], weg["status"]) == (True, True, False, "Verworfen")
    assert weg["stand"] == f"Verworfen (Spam) am 19.11.2026 10:00 von {BOESE}." and weg["meldung"] == "Beim Empfangsdienst gemeldet als „verworfen“."
    offen = _seite(_detail(status="verworfen", zustand="verworfen", melden_soll="verworfen", meldung_offen=True))
    assert offen["meldung"] == "Meldung „verworfen“ an den Empfangsdienst steht aus – der nächste Lauf meldet sie."


@nur_mit_node
def test_seite_gruende_ueber_esc():
    erg = _seite(_detail(verwerfen_gruende={BOESE: BOESE}))
    assert "<img" not in erg["gruende"] and "&lt;img" in erg["gruende"]


@nur_mit_node
def test_liste_reiter_und_kennzeichen():
    stand = {"eingerichtet": True, "laeuft": False, "letzter_lauf_am": None, "letzter_erfolg_am": None, "letzter_fehler": None, "letzte_neu": 0,
             "nicht_abgeholt": [], "neu": 2, "pruefliste": 1, "spamverdacht": 1, "pruefen": 0, "meldung_offen": 1}
    zeile = {k: v for k, v in _detail(status="verworfen", zustand="verworfen", verworfen_grund_text=BOESE, meldung_offen=True).items()
             if k not in ("umschlag", "dateiliste", "abschnitte", "nachricht_wiederholt", "erledigt_von_name", "geprueft_am", "geprueft_von_name",
                          "verwerfen_gruende")}
    ablauf = (f"stand = {json.dumps(stand)}; liste = [{json.dumps(zeile)}]; standZeichnen(); listeZeichnen();"
              "return [_element('standText').innerHTML, _element('zahlEingang').textContent, _element('zahlPruefliste').textContent,"
              " _element('zahlPruefliste').hidden, _element('listeRahmen').innerHTML];")
    text_, eingang, pruef, versteckt, tabelle = im_browser(seite("webanfragen.html", "\nladen().catch(") + WIRKSAM, ablauf)["ergebnis"]
    assert "<b>2</b> im Eingang" in text_ and "<b>1</b> in der Prüfliste (davon 1 mit Spamverdacht)" in text_ and "1 Meldung an den Empfangsdienst" in text_
    assert (eingang, pruef, versteckt) == ("2", "1", False)
    assert "verworfen: &lt;img" in tabelle and "Meldung steht aus" in tabelle and "<img" not in tabelle


@nur_mit_node
def test_start_nennt_die_pruefliste():
    from tests.test_v774_webanfragen_start import STAND, _widget
    html = _widget(dict(STAND, neu=2, pruefliste=3), [])
    assert '<a href="/anfragen/webseite#pruefliste"' in html and "3 in der Prüfliste</a>" in html and "Spamverdacht" not in html


# --- Migration ---------------------------------------------------------------------------------------------------------------------------------

def _modul(teil: str):
    pfad = next((ROOT / "alembic" / "versions").glob(f"*_{teil}.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{teil}", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _bestand_pruefen(conn, mit_dateien: bool) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    conn.execute(text("CREATE TABLE app_users (id INTEGER PRIMARY KEY)"))
    with Operations.context(MigrationContext.configure(conn)):
        _modul("webanfragen_eingang").upgrade()
        _modul("webanfragen_objekt_adresse").upgrade()
    for i, (nummer, gemeldet) in enumerate([(R1, datetime(2026, 11, 19, 8, 12)), (R2, None)], start=1):
        conn.execute(text("INSERT INTO webanfragen (id, nummer, fassung, umschlag, umschlag_sha256, status, abgeholt_am, spamverdacht, gemeldet_am) "
                          "VALUES (:i, :n, 'dk-anfrage/1', '{}', :s, 'neu', :t, false, :g)"),
                     {"i": i, "n": nummer, "s": "0" * 64, "t": datetime(2026, 11, 19, 8, 11), "g": gemeldet})
    if mit_dateien:
        conn.execute(text("INSERT INTO webanfrage_dateien (webanfrage_id, name, typ, groesse, sha256, gespeichert_als, created_at) "
                          "VALUES (1, 'anfrage.pdf', 'application/pdf', 10, :s, :g, :t)"), {"s": "0" * 64, "g": "a" * 32 + ".pdf", "t": datetime(2026, 11, 19)})
    neu = _modul("webanfragen_pruefliste_verwerfen")
    with Operations.context(MigrationContext.configure(conn)):
        neu.upgrade()
    werte = conn.execute(text("SELECT nummer, gemeldet_als, melden_soll, status FROM webanfragen ORDER BY id")).all()
    assert [tuple(w) for w in werte] == [(R1, "eingang-1", None, "neu"), (R2, None, None, "neu")]
    conn.execute(text("UPDATE webanfragen SET status = 'verworfen' WHERE id = 2"))
    with Operations.context(MigrationContext.configure(conn)):
        with pytest.raises(RuntimeError, match="erledigt"):
            neu.downgrade()
    conn.execute(text("UPDATE webanfragen SET status = 'neu' WHERE id = 2"))
    if not mit_dateien:  # SQLite baut die Tabelle für die Fremdschlüssel neu -- mit Dateien darauf verweigert es das Löschen der alten (wie test_v325)
        with Operations.context(MigrationContext.configure(conn)):
            neu.downgrade()
        assert "gemeldet_als" not in {c["name"] for c in inspect(conn).get_columns("webanfragen")}


def test_migration_bestand_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")
    try:
        with engine.begin() as conn:
            _bestand_pruefen(conn, mit_dateien=False)
    finally:
        engine.dispose()


def test_migration_bestand_postgresql():
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
            _bestand_pruefen(conn, mit_dateien=True)
        with engine.begin() as conn:  # unter PostgreSQL ohne Neuaufbau: das Downgrade geht auch mit Dateien
            from alembic.operations import Operations
            from alembic.runtime.migration import MigrationContext
            with Operations.context(MigrationContext.configure(conn)):
                _modul("webanfragen_pruefliste_verwerfen").downgrade()
            assert "gemeldet_als" not in {c["name"] for c in inspect(conn).get_columns("webanfragen")}
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
