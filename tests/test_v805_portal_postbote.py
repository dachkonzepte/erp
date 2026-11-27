"""Der Postbote des Kundenportals (seit 1.11.6, Stufe P1c): Code erzeugen, nur den Prüfwert speichern, über Microsoft 365 ohne „Gesendete Elemente“
senden, zweite Prüfung, ein Auftrag nie zweimal, genau ein Postbote, LISTEN, Aufräumen.

Gegen PostgreSQL in einem Schema für die ganze Datei (zwischen den Tests geleert, wie test_v802); das Portal ruft seine Funktionen als Testrolle (Welt aus
test_v800), der Postbote arbeitet als Benutzer des ERP. Graph ist die Attrappe aus test_v804 (wie der echte Dienst, mit der ganzen Anfrage).
"""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app import portal_postbote as postbote
from app.database import Base
from app.email_sending import set_send_method, update_graph_settings
from app.models import EmailDispatch
from app.portal import pruefwerte, rechte
from tests.test_v800_portal_funktionen import TESTROLLE, Welt
from tests.test_v804_portal_mails import GraphMitAnfrage

PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[1]
LEEREN = ("portal_zugriffe", "portal_codes", "portal_post", "portal_sitzungen", "portal_zugaenge", "portal_bremsen", "email_dispatches", "portal_rechnungen",
          "portal_termine", "portal_schaufenster", "customers")  # seit 1.11.41: das Schaufenster des Postboten vor den Kunden


@pytest.fixture(scope="module")
def pg_modul():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_pb_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    erp = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with erp.connect() as c:
            if c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": TESTROLLE}).first() is None:
                pytest.skip(f"Testrolle {TESTROLLE} fehlt (siehe tests/test_v799_portal_rechte.py)")
        Base.metadata.create_all(erp)
        with erp.begin() as c:
            c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            rechte.setzen(c, rolle=TESTROLLE, schema=schema)
        yield erp, schema
    finally:
        erp.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@pytest.fixture
def graph(monkeypatch):
    fake = GraphMitAnfrage()
    monkeypatch.setattr("app.email_sending.urllib.request.urlopen", fake)
    return fake


@pytest.fixture
def welt(pg_modul, graph):
    erp, schema = pg_modul
    with erp.begin() as c:
        for tabelle in LEEREN:
            c.execute(text(f"DELETE FROM {tabelle}"))
        c.execute(text("DELETE FROM enabled_modules WHERE module_key = 'kundenportal'"))
        c.execute(text("INSERT INTO enabled_modules (module_key, enabled, updated_at) VALUES ('kundenportal', true, now())"))
    with Session(erp) as db:
        set_send_method(db, "graph_oauth2")
        update_graph_settings(db, tenant_id="tenant-1", client_id="client-1", sender_mailbox="buero@firma.de", client_secret="s")
    w = Welt(erp, schema)
    w.graph = graph
    return w


def _db(w) -> Session:
    return Session(w.engine)


def _code_aus(anfrage) -> str:
    # seit 1.11.8 als HTML, der Code in Gruppen („481 207“, app/portal_mails.py::code_gruppen())
    assert anfrage["message"]["body"]["contentType"] == "HTML"
    [(vorne, hinten)] = re.findall(r">([0-9]{3}) ([0-9]{3})</td>", anfrage["message"]["body"]["content"])
    return vorne + hinten


def _angefordert(w):
    """Kunde mit Zugang, Link geöffnet (neues Gerät), Code angefordert -- gibt (zugang_id, Wert der vorläufigen Sitzung) zurück."""
    _kid, zid, link = w.kunde()
    (erg, _a, _m), vorlaeufig = w.oeffnen(link)
    assert erg == "code_noetig"
    assert w.anfordern(vorlaeufig) == ("angefordert", None)
    return zid, vorlaeufig


def _post(w):
    return w.erp("SELECT id, status, fehler, email_dispatch_id, erledigt_am FROM portal_post ORDER BY id")


def test_pg_code_geht_hinaus_und_meldet_an(welt):
    w = welt
    zid, vorlaeufig = _angefordert(w)
    with _db(w) as db:
        assert postbote.naechster(db) is not None
        assert postbote.naechster(db) is None
    [anfrage] = w.graph.anfragen
    assert anfrage["saveToSentItems"] == "false" and anfrage["message"]["subject"] == "Ihr Anmeldecode für das Kundenportal"
    assert [r["emailAddress"]["address"] for r in anfrage["message"]["toRecipients"]] == ["max@example.invalid"]
    code = _code_aus(anfrage)
    [(pid, status, fehler, dispatch_id, erledigt)] = _post(w)
    assert (status, fehler) == ("gesendet", None) and dispatch_id and erledigt
    [(art, dok, betreff, versand)] = w.erp("SELECT document_type, document_id, subject, status FROM email_dispatches")
    assert (art, dok, betreff, versand) == ("portal_code", pid, "Ihr Anmeldecode für das Kundenportal", "gesendet")
    [(gueltig,)] = w.erp("SELECT gueltig_bis - angelegt_am FROM portal_codes")
    assert gueltig == timedelta(minutes=10)
    alles = " ".join(str(z) for t in ("portal_codes", "portal_post", "email_dispatches", "portal_zugriffe") for z in w.erp(f"SELECT * FROM {t}"))
    assert code not in alles
    (erg, _z), _wert = w.pruefen(vorlaeufig, code)
    assert erg == "angemeldet"
    assert w.protokoll() == [("link_geoeffnet", "code_noetig"), ("code_angefordert", "ok"), ("code_gesendet", "ok"), ("angemeldet", "ok")]


def test_pg_neuer_code_ersetzt_den_alten(welt):
    w = welt
    _zid, vorlaeufig = _angefordert(w)
    with _db(w) as db:
        postbote.alle(db)
        w.erp("UPDATE portal_post SET angefordert_am = angefordert_am - interval '61 seconds'")  # das Portal lässt erst nach 60 Sekunden wieder
        assert w.anfordern(vorlaeufig) == ("angefordert", None)
        assert postbote.alle(db) == 1
    assert w.erp("SELECT count(*) FROM portal_codes WHERE ersetzt_am IS NULL AND verbraucht_am IS NULL")[0][0] == 1  # nur der neue gilt
    alt, neu = (_code_aus(a) for a in w.graph.anfragen)
    if alt != neu:
        (erg, rest), _ = w.pruefen(vorlaeufig, alt)
        assert erg == "falsch"
    (erg, _r), _ = w.pruefen(vorlaeufig, neu)
    assert erg == "angemeldet"


@pytest.mark.parametrize("fall, ergebnis, fehler", [
    ("zu_alt", "ungueltig", postbote.ZU_ALT),
    ("gesperrt", "gesperrt", postbote.ZUGANG),
    ("portal_aus", "portal_aus", postbote.ZUGANG),
    ("archiv", "archiv", postbote.ZUGANG),
    ("modul_aus", "modul_aus", postbote.ZUGANG),
    ("abgelaufen", "abgelaufen", postbote.ZUGANG),
    ("sitzung_beendet", "ungueltig", postbote.SITZUNG_UNGUELTIG),
    ("sitzung_abgelaufen", "ungueltig", postbote.SITZUNG_UNGUELTIG),
    ("grenze_zugang", "bremse", postbote.GRENZE),
    ("grenze_tag", "bremse", postbote.GRENZE),
    ("grenze_gesamt", "bremse", postbote.GRENZE),
])
def test_pg_zweite_pruefung_verwirft(welt, fall, ergebnis, fehler):
    w = welt
    zid, vorlaeufig = _angefordert(w)
    [(kid,)] = w.erp("SELECT customer_id FROM portal_zugaenge WHERE id = :z", z=zid)
    jetzt = "(now() AT TIME ZONE 'utc')"
    if fall == "zu_alt":
        w.erp("UPDATE portal_post SET angefordert_am = angefordert_am - interval '11 minutes'")
    elif fall == "gesperrt":
        w.erp("UPDATE portal_zugaenge SET gesperrt_am = now(), gesperrt_grund = 'Test' WHERE id = :z", z=zid)
    elif fall == "portal_aus":
        w.erp("UPDATE customers SET portal_aktiv = false WHERE id = :k", k=kid)
    elif fall == "archiv":
        w.erp("UPDATE customers SET archiviert_am = now() WHERE id = :k", k=kid)
    elif fall == "modul_aus":
        w.erp("UPDATE enabled_modules SET enabled = false WHERE module_key = 'kundenportal'")
    elif fall == "abgelaufen":
        w.erp(f"UPDATE portal_zugaenge SET gueltig_bis = {jetzt} - interval '1 minute' WHERE id = :z", z=zid)
    elif fall == "sitzung_beendet":
        w.erp("UPDATE portal_sitzungen SET beendet_am = now(), beendet_grund = 'abgemeldet'")
    elif fall == "sitzung_abgelaufen":
        w.erp(f"UPDATE portal_sitzungen SET laeuft_ab = {jetzt} - interval '1 second'")
    else:
        anzahl, fenster = {"grenze_zugang": (3, "14 minutes"), "grenze_tag": (10, "23 hours"), "grenze_gesamt": (200, "59 minutes")}[fall]
        [(sid,)] = w.erp("SELECT sitzung_id FROM portal_post")
        if fall == "grenze_gesamt":  # 200 gesendete Codes anderer Zugänge in der letzten Stunde
            _k2, z2, _l2 = w.kunde()
            zid_ = z2
            w.erp("INSERT INTO portal_sitzungen (zugang_id, wert_sha256, angelegt_am, laeuft_ab) VALUES (:z, :w, now(), now())", z=z2, w="f" * 64)
            [(sid,)] = w.erp("SELECT id FROM portal_sitzungen WHERE zugang_id = :z", z=z2)
        else:
            zid_ = zid
        w.erp(f"INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status, erledigt_am) SELECT 'code', :z, :s, {jetzt}, 'gesendet', "
              f"{jetzt} - interval '{fenster}' FROM generate_series(1, :n)", z=zid_, s=sid, n=anzahl)
    with _db(w) as db:
        assert postbote.alle(db) == 1
    assert w.graph.anfragen == []
    [(status, fehler_)] = w.erp("SELECT status, fehler FROM portal_post WHERE status <> 'gesendet'")
    assert (status, fehler_) == ("verworfen", fehler)
    assert w.erp("SELECT count(*) FROM portal_codes")[0][0] == 0 and w.erp("SELECT count(*) FROM email_dispatches")[0][0] == 0
    assert w.protokoll()[-1] == ("code_fehler", ergebnis)


def test_pg_grenze_knapp_darunter_geht_hinaus(welt):
    w = welt
    zid, _v = _angefordert(w)
    [(sid,)] = w.erp("SELECT sitzung_id FROM portal_post")
    w.erp("INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status, erledigt_am) SELECT 'code', :z, :s, now(), 'gesendet', "
          "(now() AT TIME ZONE 'utc') - interval '16 minutes' FROM generate_series(1, 9)", z=zid, s=sid)  # 9 am Tag, keiner in 15 Minuten
    with _db(w) as db:
        postbote.alle(db)
    assert len(w.graph.anfragen) == 1


def test_pg_versand_gescheitert_der_code_gilt_nicht(welt, monkeypatch, caplog):
    w = welt
    fake = GraphMitAnfrage(fail_status=403, fail_detail="Access is denied.")
    monkeypatch.setattr("app.email_sending.urllib.request.urlopen", fake)
    _zid, vorlaeufig = _angefordert(w)
    caplog.set_level(logging.DEBUG)
    with _db(w) as db:
        assert postbote.alle(db) == 1
    [(_pid, status, fehler, dispatch_id, _e)] = _post(w)
    assert (status, fehler) == ("fehler", postbote.VERSAND) and dispatch_id
    assert w.erp("SELECT status FROM email_dispatches")[0][0] == "fehlgeschlagen"
    assert w.erp("SELECT count(*) FROM portal_codes WHERE ersetzt_am IS NULL")[0][0] == 0
    (erg, _z), _ = w.pruefen(vorlaeufig, "000000")
    assert erg == "neu_anfordern"
    assert w.protokoll()[-2:] == [("code_fehler", "ungueltig"), ("code_abgelaufen", "ungueltig")]  # der Code gilt nicht
    code = _code_aus(fake.anfragen[0])  # die Anfrage ging an Graph, die Antwort war 403
    assert code not in caplog.text


def test_pg_smtp_kein_versand_kein_code(welt):
    w = welt
    with _db(w) as db:
        set_send_method(db, "smtp")
    _angefordert(w)
    with _db(w) as db:
        postbote.alle(db)
    [(_pid, status, fehler, dispatch_id, _e)] = _post(w)
    assert (status, fehler, dispatch_id) == ("fehler", postbote.VERSAND, None)
    assert w.erp("SELECT count(*) FROM portal_codes")[0][0] == 0 and w.erp("SELECT count(*) FROM email_dispatches")[0][0] == 0


@pytest.mark.parametrize("vorher, status, fehler", [("in_arbeit", "fehler", postbote.HAENGT), ("gesendet", "gesendet", None)])
def test_pg_abbruch_mitten_im_versand_nie_zweimal(welt, vorher, status, fehler):
    w = welt
    _angefordert(w)
    [(pid, *_r)] = _post(w)
    w.erp("INSERT INTO email_dispatches (dispatch_key, message_ref, status, channel, document_type, document_id, to_recipients, subject, created_at, "
          "created_by_name) VALUES (:k, 'ref-1', :s, 'graph_oauth2', 'portal_code', :p, 'max@example.invalid', 'Ihr Anmeldecode für das Kundenportal', "
          "now(), 'Postbote')", k=f"portal-code-{pid}", s=vorher, p=pid)
    with _db(w) as db:
        postbote.alle(db)
    assert w.graph.anfragen == [] and w.erp("SELECT count(*) FROM portal_codes")[0][0] == 0
    [(_p, st, fe, did, _e)] = _post(w)
    assert (st, fe) == (status, fehler) and did


def test_pg_ein_gehaltener_auftrag_wird_uebersprungen(welt):
    w = welt
    _angefordert(w)
    _angefordert(w)
    [(erster, *_a), (zweiter, *_b)] = _post(w)
    with w.engine.connect() as halter:
        halter.execute(text("SELECT id FROM portal_post WHERE id = :i FOR UPDATE"), {"i": erster})
        with _db(w) as db:
            assert postbote.naechster(db) == zweiter
            assert postbote.naechster(db) is None
        halter.rollback()
    with _db(w) as db:
        assert postbote.naechster(db) == erster


def test_pg_genau_ein_postbote_und_listen(welt):
    w = welt
    halt = threading.Event()
    fehler = []

    def lauf():
        try:
            postbote.laufen(w.engine, halt=halt.is_set, nachsehen=30, aufraeumen_alle=3600)
        except Exception as e:  # pragma: no cover -- im Test sichtbar machen
            fehler.append(e)

    faden = threading.Thread(target=lauf, daemon=True)
    faden.start()
    ende = time.monotonic() + 10
    while not w.erp("SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND classid = :k AND objsubid = 2 "
                    "AND objid = (hashtext(:s)::bigint & 4294967295)::oid", k=postbote.SPERRE, s=w.schema):
        assert time.monotonic() < ende, "Postbote nimmt die Sperre nicht"
        time.sleep(0.05)
    with pytest.raises(postbote.AndererPostbote):
        postbote.laufen(w.engine, halt=lambda: True)
    _angefordert(w)  # NOTIFY weckt ihn -- ohne Weckruf schaute er erst nach 30 Sekunden
    ende = time.monotonic() + 10
    while not w.graph.anfragen:
        assert time.monotonic() < ende, "der Weckruf kam nicht an"
        time.sleep(0.05)
    halt.set()
    w.erp("SELECT pg_notify('portal_post', '')")
    faden.join(10)
    assert not faden.is_alive() and fehler == []


def test_pg_aufraeumen_nach_den_fristen(welt):
    w = welt
    _zid, vorlaeufig = _angefordert(w)
    with _db(w) as db:
        postbote.alle(db)
    jetzt = "(now() AT TIME ZONE 'utc')"
    [(sid,)] = w.erp("SELECT id FROM portal_sitzungen")
    # eine alte, beendete Sitzung mit Code, Auftrag und Protokoll
    _k, z2, _l = w.kunde()
    alt = w.erp(f"INSERT INTO portal_sitzungen (zugang_id, wert_sha256, angelegt_am, laeuft_ab, beendet_am, beendet_grund) VALUES (:z, :w, "
                f"{jetzt} - interval '90 days', {jetzt} - interval '40 days', {jetzt} - interval '31 days', 'abgemeldet') RETURNING id",
                z=z2, w="e" * 64)[0][0]
    w.erp(f"INSERT INTO portal_codes (sitzung_id, pruefwert, angelegt_am, gueltig_bis) VALUES (:s, :p, {jetzt} - interval '25 hours', "
          f"{jetzt} - interval '24 hours')", s=sid, p="d" * 64)
    w.erp(f"INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status) VALUES ('code', :z, :s, {jetzt} - interval '31 days', 'gesendet')",
          z=z2, s=alt)
    w.erp(f"INSERT INTO portal_zugriffe (zeitpunkt, zugang_id, sitzung_id, aktion, ergebnis) VALUES ({jetzt} - interval '31 days', :z, :s, "
          f"'abgemeldet', 'ok'), ({jetzt} - interval '25 months', :z, NULL, 'link_geoeffnet', 'ok')", z=z2, s=alt)
    w.erp(f"INSERT INTO portal_bremsen (schluessel, fenster_beginn, zaehler) VALUES ('alt', {jetzt} - interval '49 hours', 1), "
          f"('frisch', {jetzt} - interval '47 hours', 1)")
    with _db(w) as db:
        zahlen = postbote.aufraeumen(db)
    assert zahlen == {"codes": 1, "sitzungen": 1, "bremsen": 1, "zugriffe": 1}
    assert w.erp("SELECT count(*) FROM portal_sitzungen WHERE id = :s", s=alt)[0][0] == 0
    assert w.erp("SELECT count(*) FROM portal_post WHERE sitzung_id = :s", s=alt)[0][0] == 0  # mit der Sitzung
    assert w.erp("SELECT sitzung_id FROM portal_zugriffe WHERE aktion = 'abgemeldet'") == [(None,)]  # Eintrag bleibt, ohne Sitzung
    assert w.erp("SELECT count(*) FROM portal_codes")[0][0] == 1  # der frische Code der laufenden Sitzung bleibt
    bremsen = {s for (s,) in w.erp("SELECT schluessel FROM portal_bremsen")}
    assert "alt" not in bremsen and "frisch" in bremsen  # dazu die frischen Bremsen des Ablaufs oben
    assert w.erp("SELECT count(*) FROM email_dispatches")[0][0] == 1  # das Versandprotokoll bleibt
    assert w.sitzung(vorlaeufig) == "ungueltig"  # unbestätigt -- unverändert


def test_pg_kein_code_im_protokoll(welt, caplog):
    w = welt
    _angefordert(w)
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.INFO, logger="sqlalchemy.engine")
    w.engine.echo = False
    with _db(w) as db:
        postbote.alle(db)
    code = _code_aus(w.graph.anfragen[0])
    assert "portal_codes" in caplog.text  # die Ausgabe von SQLAlchemy lief wirklich
    assert code not in caplog.text


# --- ohne Datenbank --------------------------------------------------------------------------------------------------------------------------------

def _skript():
    import importlib.util
    spec = importlib.util.spec_from_file_location("portal_postbote_skript", ROOT / "scripts" / "portal_postbote.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


URL = "DATABASE_URL"  # als Name, nicht als Schlüssel eines Wörterbuchs: test_v384 sähe sonst eine Verbindung an einen Kindprozess (hier keiner)


@pytest.mark.parametrize("wert, meldung", [(None, "DATABASE_URL"), ("sqlite://", "PostgreSQL")])
def test_skript_nur_mit_postgresql(wert, meldung):
    umgebung = {}
    if wert is not None:
        umgebung[URL] = wert
    aus = []
    assert _skript().main(umgebung=umgebung, ausgabe=aus.append) == 2 and meldung in aus[0]


def test_einheit_des_postboten():
    einheit = (ROOT / "scripts" / "server" / "erp-portalpost.service").read_text(encoding="utf-8")
    zeilen = {z.split("=", 1)[0]: z.split("=", 1)[1] for z in einheit.splitlines() if "=" in z and not z.startswith("#")}
    assert zeilen["User"] == "tobias" and zeilen["Restart"] == "always" and zeilen["Type"] == "simple"
    assert zeilen["ExecStart"] == "/bin/bash -c 'set -a; source .env; set +a; exec .venv/bin/python scripts/portal_postbote.py'"
    # seit 1.11.33 mehr Speicher: der Kindprozess für Fotos zählt zur Grenze der Einheit; bis 1.11.32 200M/256M (seit 1.11.35 die Grenze des Kinds
    # darunter und OOMPolicy=continue: tests/test_v826_portal_foto_vorrang.py)
    assert zeilen["MemoryMax"] == "768M" and zeilen["MemoryHigh"] == "640M" and zeilen["UMask"] == "0027"
