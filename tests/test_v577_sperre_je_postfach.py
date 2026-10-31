"""Version 1.9.159 (Stufe 6, R2, Punkt 3): Sperre je Postfach, auch über zwei Prozesse; eindeutige Outlook-Kennung je Postfach in der Datenbank.

    Sperre    einer hält sie, alle anderen bekommen None; läuft ab, wenn ein Prozess gestorben ist; nur die eigene wird freigegeben; ein Lauf, der sie verlor, hört auf
    Läufe     zwei zugleich: ein POST, ein Termin; der zweite meldet „busy“; Speichern während eines Laufs sendet nicht, der nächste Lauf sendet
    Prozesse  drei echte Prozesse nehmen sie gleichzeitig, genau einer bekommt sie (SQLite-Datei, PostgreSQL im Wegwerf-Schema)
    Index     (Postfach, Kennung) doppelt geht nicht, in zwei Postfächern schon; Serienvorkommen ebenso; ein Konto je Postfach
    Bestand   Migration 7c2e9b41d3a8 über alembic: Doppelte, zwei Konten an einem Postfach, Link auf ein anderes Postfach
"""

import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.database import Base
from app.models import AppUser, CalendarEvent, OutlookCalendarSyncState, OutlookSeriesOccurrence
from app.outlook_calendar_sync import (
    SPERRE_GILT, SperreVerloren, _apply_delta_change, _sperre_nehmen, get_or_create_sync_state, postfach_normal, push_event_best_effort, sync_user_calendar,
)
from app.routers.users import router as users_router
from tests.bestand_alt import auftrag
from tests.grunddaten_schalter import ohne_grunddaten
from tests.outlook_attrappe import Microsoft
from tests.pg_schutz import pg_url_pruefen
from tests.test_v297_outlook_calendar_sync import PG_TEST_DATABASE_URL, _enable_sync, _make_event, _make_user, db_session, pg_aufraeumen, pg_db_session
from tests.test_v380_nummern_eindeutig import _alembic, _ok

ROOT = Path(__file__).resolve().parent.parent
URLOPEN = "app.outlook_calendar_sync.urllib.request.urlopen"
ANNA = "anna@dachkonzepte.gmbh"
BEN = "ben@dachkonzepte.gmbh"
BEGINN = datetime(2026, 11, 10, 9, 0)
mit_pg = pytest.mark.skipif(not PG_TEST_DATABASE_URL, reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")


def _lauf(db, konto, ms):
    with patch(URLOPEN, side_effect=ms.urlopen):
        return sync_user_calendar(db, konto)


# --- Die Sperre ------------------------------------------------------------------------------------------

def test_nur_einer_haelt_sie_und_gibt_sie_frei():
    db = db_session()
    erste = _sperre_nehmen(db, ANNA)
    assert erste is not None
    assert _sperre_nehmen(db, ANNA) is None
    assert _sperre_nehmen(db, BEN) is not None  # je Postfach
    erste.freigeben()
    assert _sperre_nehmen(db, ANNA) is not None


def test_adresse_gross_und_klein_ist_dasselbe_postfach():
    db = db_session()
    assert _sperre_nehmen(db, "Anna@Dachkonzepte.GmbH ") is not None
    assert _sperre_nehmen(db, ANNA) is None
    assert db.scalar(select(func.count()).select_from(OutlookCalendarSyncState)) == 1


def test_laeuft_nach_der_frist_ab():
    """Ein gestorbener Prozess gibt nicht frei: nach SPERRE_GILT darf der nächste."""
    db = db_session()
    tote = _sperre_nehmen(db, ANNA)
    stand = get_or_create_sync_state(db, ANNA)
    stand.lauf_seit = datetime.utcnow() - SPERRE_GILT + timedelta(minutes=1)
    db.commit()
    assert _sperre_nehmen(db, ANNA) is None
    stand.lauf_seit = datetime.utcnow() - SPERRE_GILT - timedelta(seconds=1)
    db.commit()
    neue = _sperre_nehmen(db, ANNA)
    assert neue is not None
    tote.freigeben()  # gibt nur die eigene frei, die neue hält weiter
    assert _sperre_nehmen(db, ANNA) is None
    neue.freigeben()
    assert get_or_create_sync_state(db, ANNA).lauf_seit is None


def test_halten_erneuert_und_merkt_den_verlust():
    db = db_session()
    sperre = _sperre_nehmen(db, ANNA)
    stand = get_or_create_sync_state(db, ANNA)
    alt = datetime.utcnow() - timedelta(minutes=5)
    stand.lauf_seit = alt
    db.commit()
    sperre.halten()  # gerade erst genommen: schreibt noch nicht
    assert get_or_create_sync_state(db, ANNA).lauf_seit == alt
    sperre._zuletzt = 0
    sperre.halten()
    assert get_or_create_sync_state(db, ANNA).lauf_seit > alt
    stand = get_or_create_sync_state(db, ANNA)
    stand.lauf_kennung = "ein anderer"
    db.commit()
    sperre._zuletzt = 0
    with pytest.raises(SperreVerloren):
        sperre.halten()


# --- Läufe --------------------------------------------------------------------------------------------------

def _datei_db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'sperre.db').as_posix()}", connect_args={"timeout": 30})
    Base.metadata.create_all(engine)
    return engine


def _zwei_laeufe(machen):
    """Der erste Lauf hält im ersten POST an, bis der zweite fertig ist."""
    db_a, Sitzung = machen()
    _enable_sync(db_a)
    konto = _make_user(db_a, username="anna", mailbox=ANNA)
    _make_event(db_a, konto, title="Neu im ERP", start_at=BEGINN, end_at=BEGINN + timedelta(hours=1))
    ms = Microsoft()
    ms.postfach(ANNA)
    im_post, weiter = threading.Event(), threading.Event()

    def haken(methode, adresse, weg):
        if methode == "POST":
            im_post.set()
            assert weiter.wait(60)

    ms.vor_antwort = haken
    ergebnis = {}
    konto_id = konto.id

    def erster():
        db = Sitzung()
        try:
            ergebnis["a"] = sync_user_calendar(db, db.get(AppUser, konto_id))
        finally:
            db.close()

    db_b = Sitzung()
    with patch(URLOPEN, side_effect=ms.urlopen):
        faden = threading.Thread(target=erster)
        faden.start()
        assert im_post.wait(60)
        ergebnis["b"] = sync_user_calendar(db_b, db_b.get(AppUser, konto_id))
        weiter.set()
        faden.join(60)
        ms.vor_antwort = None
    assert ergebnis["b"].get("busy") is True and ergebnis["b"]["skipped"] is True
    assert ergebnis["a"]["pushed_created"] == 1
    assert len(ms.schreibend("POST")) == 1
    assert len(ms.postfach(ANNA).events) == 1
    db_b.expire_all()
    assert db_b.scalar(select(func.count()).select_from(CalendarEvent)) == 1
    with patch(URLOPEN, side_effect=ms.urlopen):
        danach = sync_user_calendar(db_b, db_b.get(AppUser, konto_id))
    assert not danach.get("busy") and danach["pushed_created"] == 0 and danach["created"] == 0
    db_a.close()
    db_b.close()


def test_zwei_laeufe_zugleich_ein_post_sqlite(tmp_path):
    engine = _datei_db(tmp_path)
    Sitzung = sessionmaker(bind=engine)
    _zwei_laeufe(lambda: (Sitzung(), Sitzung))
    engine.dispose()


@mit_pg
def test_zwei_laeufe_zugleich_ein_post_postgresql():
    db, engine = pg_db_session()
    Sitzung = sessionmaker(bind=engine)
    try:
        _zwei_laeufe(lambda: (db, Sitzung))
    finally:
        db.close()
        pg_aufraeumen(engine)


def test_speichern_waehrend_eines_laufs_sendet_nicht_der_naechste_lauf_sendet():
    db = db_session()
    _enable_sync(db)
    konto = _make_user(db, username="anna", mailbox=ANNA)
    ms = Microsoft()
    ms.postfach(ANNA)
    termin = _make_event(db, konto, title="Beim Speichern", start_at=BEGINN, end_at=BEGINN + timedelta(hours=1))
    sperre = _sperre_nehmen(db, ANNA)
    with patch(URLOPEN, side_effect=ms.urlopen):
        push_event_best_effort(db, termin.id)
    db.refresh(termin)
    assert termin.outlook_event_id is None and ms.schreibend() == []
    sperre.freigeben()
    assert _lauf(db, konto, ms)["pushed_created"] == 1


def test_speichern_gibt_die_sperre_auch_nach_einem_fehler_frei():
    db = db_session()
    _enable_sync(db)
    konto = _make_user(db, username="anna", mailbox=ANNA)
    ms = Microsoft()
    ms.postfach(ANNA)
    ms.gesperrt.add(ANNA)
    termin = _make_event(db, konto, title="T", start_at=BEGINN, end_at=BEGINN + timedelta(hours=1))
    with patch(URLOPEN, side_effect=ms.urlopen):
        push_event_best_effort(db, termin.id)
    assert get_or_create_sync_state(db, ANNA).lauf_seit is None


def test_ein_lauf_gibt_die_sperre_auch_nach_einem_fehler_frei():
    db = db_session()
    _enable_sync(db)
    konto = _make_user(db, username="anna", mailbox=ANNA)
    ms = Microsoft()
    ms.postfach(ANNA)
    ms.gesperrt.add(ANNA)
    assert _lauf(db, konto, ms)["error"] is True
    stand = get_or_create_sync_state(db, ANNA)
    assert stand.lauf_seit is None and stand.last_error_type == "OutlookSyncError"


def test_der_stand_haengt_an_der_adresse():
    """Befund XP1: nach einem Wechsel des Postfachs las der alte Link weiter das alte."""
    db = db_session()
    _enable_sync(db)
    konto = _make_user(db, username="anna", mailbox="alt@x.de")
    ms = Microsoft()
    ms.postfach("alt@x.de")
    ms.postfach("neu@x.de")
    _lauf(db, konto, ms)
    konto.outlook_mailbox = "neu@x.de"
    db.commit()
    ms.anfragen.clear()
    assert not _lauf(db, konto, ms).get("error")
    gelesen = [u for m, u in ms.anfragen if m == "GET" and "/delta" in u]
    assert gelesen and all("neu%40x.de" in u for u in gelesen) and "deltatoken" not in gelesen[0]


# --- Drei Prozesse ----------------------------------------------------------------------------------------

_PROZESS = """
import pathlib, sys, time
from app.database import SessionLocal
from app.outlook_calendar_sync import _sperre_nehmen
db = SessionLocal()
db.connection()
pathlib.Path(sys.argv[1]).write_text("bereit")
los = pathlib.Path(sys.argv[2])
while not los.exists():
    time.sleep(0.001)
print("ja" if _sperre_nehmen(db, "anna@x.de") else "nein", flush=True)
"""


def _prozesse(url: str, tmp_path: Path, anzahl: int = 3) -> list[str]:
    env = {**os.environ, "DATABASE_URL": pg_url_pruefen(url), "ERP_DATA_DIR": str(tmp_path / "data"), "ERP_SECRET_KEY": "test-" + "x" * 40, "PYTHONIOENCODING": "utf-8"}
    los = tmp_path / "los"
    bereit = [tmp_path / f"bereit{i}" for i in range(anzahl)]
    laeufe = [subprocess.Popen([sys.executable, "-c", _PROZESS, str(b), str(los)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for b in bereit]
    frist = time.monotonic() + 120
    while not all(b.exists() for b in bereit):
        assert time.monotonic() < frist, [p.poll() for p in laeufe]
        time.sleep(0.02)
    los.write_text("los")
    antworten = []
    for lauf in laeufe:
        aus, fehler = lauf.communicate(timeout=120)
        assert lauf.returncode == 0, fehler
        antworten.append(aus.strip())
    return antworten


def test_drei_prozesse_einer_bekommt_sie_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'prozesse.db').as_posix()}"
    engine = create_engine(url)
    with ohne_grunddaten():
        Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    get_or_create_sync_state(db, "anna@x.de")  # die Zeile steht, wie nach dem ersten Lauf
    db.close()
    engine.dispose()
    assert sorted(_prozesse(url, tmp_path)) == ["ja", "nein", "nein"]


@mit_pg
def test_drei_prozesse_einer_bekommt_sie_postgresql(tmp_path):
    schema = f"pgtest_sperre_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with ohne_grunddaten():
            Base.metadata.create_all(engine)
        url = f"{PG_TEST_DATABASE_URL}{'&' if '?' in PG_TEST_DATABASE_URL else '?'}options=-csearch_path={schema}"
        assert sorted(_prozesse(url, tmp_path)) == ["ja", "nein", "nein"]  # auch das Anlegen der Zeile treffen sich hier
        with engine.connect() as c:
            assert c.execute(text("SELECT count(*) FROM outlook_calendar_sync_state")).scalar() == 1
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


# --- Die eindeutige Kennung ----------------------------------------------------------------------------------

def _termin(db, konto, postfach, kennung):
    zeile = CalendarEvent(title="T", start_at=BEGINN, end_at=BEGINN, owner_user_id=konto.id, outlook_postfach=postfach, outlook_event_id=kennung)
    db.add(zeile)
    db.flush()
    return zeile


def _index_pruefen(db):
    konto = _make_user(db, username="anna", mailbox=ANNA)
    _termin(db, konto, ANNA, "K1")
    db.commit()
    _termin(db, konto, BEN, "K1")  # in einem anderen Postfach ist es ein anderer Termin
    _termin(db, konto, None, None)
    _termin(db, konto, None, None)  # ohne Verbindung zu Outlook beliebig viele
    db.commit()
    with pytest.raises(IntegrityError):
        _termin(db, konto, ANNA, "K1")
    db.rollback()
    db.add(OutlookSeriesOccurrence(owner_user_id=konto.id, outlook_postfach=ANNA, outlook_event_id="S1", occurrence_type="occurrence", title="S", start_at=BEGINN, end_at=BEGINN))
    db.commit()
    db.add(OutlookSeriesOccurrence(owner_user_id=konto.id, outlook_postfach=ANNA, outlook_event_id="S1", occurrence_type="occurrence", title="S", start_at=BEGINN, end_at=BEGINN))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(AppUser(username="zwei", display_name="Zwei", role="admin", active=True, password_hash="x", outlook_mailbox=ANNA))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_der_index_sqlite():
    _index_pruefen(db_session())


@mit_pg
def test_der_index_postgresql():
    db, engine = pg_db_session()
    try:
        _index_pruefen(db)
    finally:
        db.close()
        pg_aufraeumen(engine)


def test_treffen_sich_zwei_laeufe_doch_gilt_die_zeile_des_ersten():
    """Nach einer abgelaufenen Sperre: der zweite findet die Zeile beim Suchen noch nicht und läuft beim Anlegen in den Index -- kein Fehler, kein zweiter Termin."""
    db = db_session()
    konto = _make_user(db, username="anna", mailbox=ANNA)
    _termin(db, konto, ANNA, "K1")
    db.commit()
    zaehler = dict(created=0, updated=0, deleted=0, skipped_recurring=0, skipped_invalid=0)
    item = {"id": "K1", "subject": "Termin", "isAllDay": False, "start": {"dateTime": "2026-11-10T08:00:00"}, "end": {"dateTime": "2026-11-10T09:00:00"},
            "lastModifiedDateTime": "2026-11-01T00:00:00Z", "location": {}, "body": {"content": ""}}
    with patch("app.outlook_calendar_sync._termin_im_postfach", return_value=None):
        assert _apply_delta_change(db, konto, item, zaehler) is None
    assert zaehler["created"] == 0
    assert db.scalar(select(func.count()).select_from(CalendarEvent)) == 1


def test_postfach_normal():
    assert postfach_normal("  Anna@X.DE ") == "anna@x.de"
    assert postfach_normal("") is None and postfach_normal("   ") is None and postfach_normal(None) is None


def _konten_client(db, router_test_client):
    return router_test_client(db, users_router)


def test_benutzerseite_lehnt_ein_vergebenes_postfach_ab(router_test_client, threaded_db_session):
    db = threaded_db_session
    _make_user(db, username="anna", mailbox=ANNA, role="admin")
    ben = _make_user(db, username="ben", mailbox=None)
    client = _konten_client(db, router_test_client)
    aenderung = {"username": "ben", "display_name": "Ben", "role": "buero_auftrag", "active": True}
    antwort = client.put(f"/api/users/{ben.id}", json={**aenderung, "outlook_mailbox": "ANNA@dachkonzepte.gmbh"})
    assert antwort.status_code == 409 and "anna" in antwort.json()["detail"]
    antwort = client.put(f"/api/users/{ben.id}", json={**aenderung, "outlook_mailbox": " Ben@Dachkonzepte.GmbH "})
    assert antwort.status_code == 200 and antwort.json()["outlook_mailbox"] == BEN
    antwort = client.put(f"/api/users/{ben.id}", json={**aenderung, "outlook_mailbox": BEN})  # das eigene ist nicht vergeben
    assert antwort.status_code == 200
    antwort = client.post("/api/users", json={"username": "cara", "display_name": "Cara", "password": "Passwort123", "role": "buero_auftrag", "active": True, "outlook_mailbox": BEN})
    assert antwort.status_code == 409
    antwort = client.put(f"/api/users/{ben.id}", json={**aenderung, "outlook_mailbox": ""})
    assert antwort.status_code == 200 and antwort.json()["outlook_mailbox"] is None


# --- Bestand -------------------------------------------------------------------------------------------------

MIGRATION = "7c2e9b41d3a8"
VORHER = "4f7a1c9e2b60"
ZEIT = "2026-09-01 08:00:00"


def _bestand(engine) -> dict:
    db = sessionmaker(bind=engine)()
    p1, p2 = auftrag(db, number="1").project_id, auftrag(db, number="2").project_id
    db.close()
    with engine.begin() as c:
        def konto(name, postfach, aktiv=True):
            return c.execute(text("INSERT INTO app_users (username, display_name, password_hash, role, active, outlook_mailbox, created_at, updated_at) VALUES (:n, :n, 'x', 'admin', :a, :p, :z, :z) RETURNING id"),
                             {"n": name, "p": postfach, "a": aktiv, "z": ZEIT}).scalar()

        anna = konto("anna", " Anna@X.de ")
        inaktiv = konto("inaktiv", "ZWEI@x.de", False)  # dasselbe Postfach wie aktiv: das aktive behält es
        aktiv = konto("aktiv", "zwei@x.de")
        leer = konto("leer", "   ")
        ohne = konto("ohne", None)

        def termin(titel, besitzer, kennung, projekt=None):
            return c.execute(text("INSERT INTO calendar_events (title, start_at, end_at, all_day, owner_user_id, project_id, is_private, external_source, outlook_event_id, outlook_etag, outlook_synced_at, created_at, updated_at) "
                                  "VALUES (:t, :z, :z, :f, :o, :p, :f, 'erp', :k, :e, :s, :z, :z) RETURNING id"),
                             {"t": titel, "z": ZEIT, "f": False, "o": besitzer, "p": projekt, "k": kennung, "e": "etag" if kennung else None, "s": ZEIT if kennung else None}).scalar()

        termin("einzeln", anna, "E1")
        termin("ohne Kennung", anna, None)
        termin("doppelt alt ohne Bezug", anna, "D1")
        termin("doppelt mit Bezug", anna, "D1", p1)
        termin("doppelt eigener Bezug", anna, "D1", p2)
        termin("doppelt ohne Bezug", anna, "D1")
        termin("zwei Konten aktiv", aktiv, "Z1")
        termin("zwei Konten inaktiv", inaktiv, "Z1")
        termin("zwei Konten anderer", inaktiv, "Z2")
        termin("Besitzer ohne Postfach", ohne, "O1")

        def vorkommen(besitzer, kennung):
            c.execute(text("INSERT INTO outlook_series_occurrences (owner_user_id, outlook_event_id, occurrence_type, title, start_at, end_at, all_day, is_private, created_at, updated_at) "
                           "VALUES (:o, :k, 'occurrence', 'S', :z, :z, :f, :f, :z, :z)"), {"o": besitzer, "k": kennung, "z": ZEIT, "f": False})

        vorkommen(anna, "S1")
        vorkommen(aktiv, "S2")
        vorkommen(inaktiv, "S2")  # dasselbe Postfach, dasselbe Vorkommen
        vorkommen(ohne, "S3")

        def stand(besitzer, link, lauf):
            c.execute(text("INSERT INTO outlook_calendar_sync_state (app_user_id, delta_link, last_synced_at) VALUES (:o, :l, :s)"), {"o": besitzer, "l": link, "s": lauf})

        stand(anna, "https://graph.microsoft.com/v1.0/users/alt@x.de/events/delta?$deltatoken=abc", ZEIT)  # zeigt auf ein anderes Postfach
        stand(aktiv, "https://graph.microsoft.com/v1.0/users/zwei@x.de/events/delta?$deltatoken=neu", "2026-09-05 08:00:00")
        stand(inaktiv, "https://graph.microsoft.com/v1.0/users/zwei@x.de/events/delta?$deltatoken=alt", "2026-09-01 08:00:00")
        stand(ohne, "https://graph.microsoft.com/v1.0/users/x/events/delta?$deltatoken=weg", ZEIT)
    return {"anna": anna, "aktiv": aktiv, "inaktiv": inaktiv, "leer": leer, "ohne": ohne, "p1": p1, "p2": p2}


def _nach_titel(engine) -> dict:
    with engine.connect() as c:
        return {z.title: z for z in c.execute(text("SELECT title, outlook_event_id, outlook_postfach, outlook_etag, outlook_synced_at, project_id FROM calendar_events"))}


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    ids = _bestand(engine)

    _ok(_alembic(url, "upgrade", MIGRATION))
    assert MIGRATION in _ok(_alembic(url, "current")).stdout

    with engine.connect() as c:
        adressen = dict(c.execute(text("SELECT username, outlook_mailbox FROM app_users")).all())
    assert adressen == {"anna": "anna@x.de", "inaktiv": None, "aktiv": "zwei@x.de", "leer": None, "ohne": None}

    termine = _nach_titel(engine)
    assert termine["einzeln"].outlook_postfach == "anna@x.de"
    assert termine["ohne Kennung"].outlook_postfach is None
    assert termine["doppelt mit Bezug"].outlook_postfach == "anna@x.de" and termine["doppelt mit Bezug"].outlook_event_id == "D1"
    assert "doppelt alt ohne Bezug" not in termine and "doppelt ohne Bezug" not in termine
    eigener = termine["doppelt eigener Bezug"]  # hat sein eigenes Projekt: bleibt, ohne Verbindung, geht neu hinaus
    assert (eigener.outlook_event_id, eigener.outlook_postfach, eigener.outlook_etag, eigener.outlook_synced_at, eigener.project_id) == (None, None, None, None, ids["p2"])
    assert termine["zwei Konten aktiv"].outlook_event_id == "Z1"
    assert "zwei Konten inaktiv" not in termine  # derselbe Termin
    assert termine["zwei Konten anderer"].outlook_postfach == "zwei@x.de"  # liegt dort, sein Konto hat das Postfach verloren
    assert termine["Besitzer ohne Postfach"].outlook_postfach is None and termine["Besitzer ohne Postfach"].outlook_event_id == "O1"

    with engine.connect() as c:
        assert sorted(c.execute(text("SELECT outlook_postfach, outlook_event_id FROM outlook_series_occurrences")).all()) == [("anna@x.de", "S1"), ("zwei@x.de", "S2")]
        staende = {z.postfach: z for z in c.execute(text("SELECT postfach, delta_link, lauf_kennung, lauf_seit FROM outlook_calendar_sync_state"))}
    assert set(staende) == {"anna@x.de", "zwei@x.de"}
    assert staende["anna@x.de"].delta_link is None  # zeigte auf ein anderes Postfach
    assert staende["zwei@x.de"].delta_link.endswith("=neu")  # der jüngste der beiden
    assert staende["zwei@x.de"].lauf_seit is None

    with engine.begin() as c:  # der Index greift
        with pytest.raises(IntegrityError):
            with c.begin_nested():
                c.execute(text("UPDATE calendar_events SET outlook_postfach = 'zwei@x.de', outlook_event_id = 'Z2' WHERE title = 'einzeln'"))

    _ok(_alembic(url, "downgrade", VORHER))
    assert VORHER in _ok(_alembic(url, "current")).stdout
    with engine.connect() as c:
        assert sorted(c.execute(text("SELECT app_user_id FROM outlook_calendar_sync_state")).scalars().all()) == sorted([ids["anna"], ids["aktiv"]])
        assert c.execute(text("SELECT count(*) FROM outlook_series_occurrences")).scalar() == 2
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'postfach.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


@mit_pg
def test_migration_auf_einem_bestand_postgresql():
    schema = f"pgtest_mig_postf_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_TEST_DATABASE_URL}{'&' if '?' in PG_TEST_DATABASE_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
