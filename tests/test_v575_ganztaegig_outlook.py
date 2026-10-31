"""Version 1.9.157 (Stufe 6, R2, Punkt 1): ganztägige Termine in beiden Richtungen -- ein Tag bleibt ein Tag, mehrtägige stimmen.

    ERP -> Outlook  Mitternacht in Europe/Berlin, Ende = Tag nach dem letzten; die Attrappe lehnt alles andere ab wie Microsoft
    Outlook -> ERP  Mitternacht „UTC“ ist ein Kalendertag; end_at = letzter Tag, auch bei Serien und über die Zeitumstellung
    Kalender        eventsForDay() zeigt einen Tag an einem Tag
    Bestand         Migration 4f7a1c9e2b60 repariert die Form 01:00/02:00, updated_at bleibt
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text

from app.models import CalendarEvent, OutlookSeriesOccurrence
from app.outlook_calendar_sync import _event_payload, _zeiten_aus_graph, push_event_best_effort, sync_user_calendar
from tests.node_lauf import node_ausfuehren
from tests.test_v297_outlook_calendar_sync import (
    FakeGraphServer, _enable_sync, _make_event, _make_user, db_session, make_realistic_urlopen,
)
from tests.test_v380_nummern_eindeutig import _alembic, _ok

ROOT = Path(__file__).resolve().parent.parent
TAG = datetime(2026, 11, 10)
URLOPEN = "app.outlook_calendar_sync.urllib.request.urlopen"
MIGRATION = "4f7a1c9e2b60"
VORHER = "b2c7f4e19a06"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _ganztag(start: str, ende: str, **werte) -> dict:
    return {"isAllDay": True, "start": {"dateTime": start, "timeZone": "UTC"}, "end": {"dateTime": ende, "timeZone": "UTC"}, **werte}


# --- ERP -> Outlook ------------------------------------------------------------------------------------

@pytest.mark.parametrize("beginn, ende, start_erwartet, ende_erwartet", [
    (TAG, TAG, "2026-11-10T00:00:00", "2026-11-11T00:00:00"),  # ein Tag, wie ihn der Dialog schickt
    (TAG, TAG + timedelta(days=2), "2026-11-10T00:00:00", "2026-11-13T00:00:00"),  # drei Tage
    (datetime(2026, 3, 29), datetime(2026, 3, 29), "2026-03-29T00:00:00", "2026-03-30T00:00:00"),  # Sprung auf Sommerzeit
    (datetime(2026, 10, 25), datetime(2026, 10, 25), "2026-10-25T00:00:00", "2026-10-26T00:00:00"),  # zurück auf Winterzeit
    (TAG + timedelta(hours=9), TAG + timedelta(hours=10), "2026-11-10T00:00:00", "2026-11-11T00:00:00"),  # mit Uhrzeit über die Schnittstelle angelegt
])
def test_was_nach_outlook_geht(beginn, ende, start_erwartet, ende_erwartet):
    nutzlast = _event_payload(CalendarEvent(title="Urlaub", start_at=beginn, end_at=ende, all_day=True, is_private=False))
    assert nutzlast["isAllDay"] is True
    assert nutzlast["start"] == {"dateTime": start_erwartet, "timeZone": "Europe/Berlin"}
    assert nutzlast["end"] == {"dateTime": ende_erwartet, "timeZone": "Europe/Berlin"}


def test_ein_termin_mit_uhrzeit_bleibt_in_utc():
    nutzlast = _event_payload(CalendarEvent(title="Aufmaß", start_at=TAG + timedelta(hours=9), end_at=TAG + timedelta(hours=10), all_day=False, is_private=False))
    assert nutzlast["start"] == {"dateTime": "2026-11-10T08:00:00", "timeZone": "UTC"}
    assert nutzlast["end"] == {"dateTime": "2026-11-10T09:00:00", "timeZone": "UTC"}


def test_microsoft_nimmt_ihn_an_und_nichts_wartet_danach():
    """Die Attrappe lehnt wie Microsoft jeden ganztägigen Termin ohne Mitternacht ab; die Fassung bis 1.9.156 blieb hier dauerhaft ungesendet."""
    db = db_session()
    _enable_sync(db)
    owner = _make_user(db)
    server = FakeGraphServer()
    event = _make_event(db, owner, start_at=TAG, end_at=TAG, all_day=True)
    with patch(URLOPEN, side_effect=make_realistic_urlopen(server)):
        push_event_best_effort(db, event.id)
    db.refresh(event)
    assert event.outlook_event_id == "graph-1"
    ablage = server.events["graph-1"]
    assert ablage["start"]["dateTime"].startswith("2026-11-10T00:00:00") and ablage["end"]["dateTime"].startswith("2026-11-11T00:00:00")


def test_rundlauf_bleibt_ruhig_und_ein_tag():
    db = db_session()
    _enable_sync(db)
    owner = _make_user(db)
    server = FakeGraphServer()
    einer = _make_event(db, owner, title="Ein Tag", start_at=TAG, end_at=TAG, all_day=True)
    drei = _make_event(db, owner, title="Drei Tage", start_at=TAG, end_at=TAG + timedelta(days=2), all_day=True)
    with patch(URLOPEN, side_effect=make_realistic_urlopen(server)):
        for lauf in range(5):
            ergebnis = sync_user_calendar(db, owner)
            assert not ergebnis.get("error")
            if lauf:  # ab dem zweiten Lauf nur noch Ruhe, auch wenn das Echo zurückkommt
                assert {k: ergebnis[k] for k in ("created", "updated", "deleted", "pushed_created", "pushed_updated", "push_failed")} == dict.fromkeys(
                    ("created", "updated", "deleted", "pushed_created", "pushed_updated", "push_failed"), 0), ergebnis
    db.refresh(einer)
    db.refresh(drei)
    assert (einer.start_at, einer.end_at, einer.all_day) == (TAG, TAG, True)
    assert (drei.start_at, drei.end_at) == (TAG, TAG + timedelta(days=2))


# --- Outlook -> ERP ------------------------------------------------------------------------------------

@pytest.mark.parametrize("start, ende, beginn_erwartet, ende_erwartet", [
    ("2026-11-10T00:00:00.0000000", "2026-11-11T00:00:00.0000000", TAG, TAG),  # ein Tag, Winter
    ("2026-07-10T00:00:00.0000000", "2026-07-11T00:00:00.0000000", datetime(2026, 7, 10), datetime(2026, 7, 10)),  # ein Tag, Sommer
    ("2026-11-10T00:00:00.0000000", "2026-11-13T00:00:00.0000000", TAG, TAG + timedelta(days=2)),  # drei Tage
    ("2026-10-24T00:00:00.0000000", "2026-10-27T00:00:00.0000000", datetime(2026, 10, 24), datetime(2026, 10, 26)),  # über die Zeitumstellung
    ("2026-11-09T23:00:00.0000000", "2026-11-10T23:00:00.0000000", TAG, TAG),  # falls doch Mitternacht Berlin als UTC kommt
])
def test_was_aus_outlook_kommt(start, ende, beginn_erwartet, ende_erwartet):
    assert _zeiten_aus_graph(_ganztag(start, ende)) == (beginn_erwartet, ende_erwartet)


def test_termin_mit_uhrzeit_wird_weiter_umgerechnet():
    item = {"isAllDay": False, "start": {"dateTime": "2026-11-10T08:00:00.0000000", "timeZone": "UTC"}, "end": {"dateTime": "2026-11-10T09:00:00.0000000", "timeZone": "UTC"}}
    assert _zeiten_aus_graph(item) == (TAG + timedelta(hours=9), TAG + timedelta(hours=10))


def test_ganztaegig_aus_outlook_kommt_als_ein_tag_an():
    db = db_session()
    _enable_sync(db)
    owner = _make_user(db)
    server = FakeGraphServer()
    server.create({"subject": "Betriebsausflug", "isAllDay": True, "start": {"dateTime": "2026-11-10T00:00:00", "timeZone": "W. Europe Standard Time"},
                   "end": {"dateTime": "2026-11-11T00:00:00", "timeZone": "W. Europe Standard Time"}, "location": {"displayName": ""}, "body": {"content": ""}})
    with patch(URLOPEN, side_effect=make_realistic_urlopen(server)):
        assert sync_user_calendar(db, owner)["created"] == 1
    zeile = db.query(CalendarEvent).one()
    assert (zeile.start_at, zeile.end_at, zeile.all_day) == (TAG, TAG, True)


def test_ganztaegiges_vorkommen_einer_serie():
    from app.outlook_calendar_sync import _series_fields
    felder = _series_fields(_ganztag("2026-11-10T00:00:00.0000000", "2026-11-11T00:00:00.0000000", type="occurrence", subject="Jour fixe"))
    assert (felder["start_at"], felder["end_at"], felder["all_day"]) == (TAG, TAG, True)
    assert OutlookSeriesOccurrence(**{k: v for k, v in felder.items()}).end_at == TAG


# --- Kalender ------------------------------------------------------------------------------------------

def _funktion(text_: str, kopf: str) -> str:
    start = text_.index(kopf)
    tiefe, i = 0, text_.index("{", start)
    while True:
        tiefe += {"{": 1, "}": -1}.get(text_[i], 0)
        i += 1
        if not tiefe:
            return text_[start:i]


@pytest.mark.parametrize("beginn, ende, tage", [
    ("2026-11-10T00:00:00", "2026-11-10T00:00:00", ["2026-11-10"]),
    ("2026-11-10T00:00:00", "2026-11-12T00:00:00", ["2026-11-10", "2026-11-11", "2026-11-12"]),
])
def test_der_kalender_zeigt_ihn_an_genau_diesen_tagen(beginn, ende, tage):
    """Dieselbe Rechnung wie calendar.html::eventsForDay(), mit der Form aus _zeiten_aus_graph()."""
    seite = (ROOT / "app" / "templates" / "calendar.html").read_text(encoding="utf-8")
    skript = "\n".join([
        _funktion(seite, "function pad("), _funktion(seite, "function toDateStr("), _funktion(seite, "function eventsForDay("),
        f"let events=[{{start_at:{json.dumps(beginn)},end_at:{json.dumps(ende)}}}];",
        "const gezeigt=[];for(let d=9;d<=13;d++){const t=`2026-11-${pad(d)}`;if(eventsForDay(t).length)gezeigt.push(t)}",
        "console.log(JSON.stringify(gezeigt));",
    ])
    assert node_ausfuehren(skript, tz="Europe/Berlin") == tage


# --- Bestand -------------------------------------------------------------------------------------------

JETZT = "2026-09-01 08:00:00"
SYNC = "2026-09-02 08:00:00"


def _bestand(engine) -> None:
    with engine.begin() as c:
        c.execute(text("INSERT INTO app_users (username, display_name, password_hash, role, active, created_at, updated_at) VALUES ('a', 'A', 'x', 'admin', :an, :z, :z)"), {"an": True, "z": JETZT})
        konto = c.execute(text("SELECT id FROM app_users")).scalar()

        def termin(titel, beginn, ende, ganz, quelle):
            c.execute(text("INSERT INTO calendar_events (title, start_at, end_at, all_day, owner_user_id, is_private, external_source, outlook_event_id, outlook_synced_at, created_at, updated_at) "
                           "VALUES (:t, :b, :e, :g, :o, :p, :q, :k, :s, :z, :s)"),
                      {"t": titel, "b": beginn, "e": ende, "g": ganz, "o": konto, "p": False, "q": quelle, "k": titel, "s": SYNC, "z": JETZT})

        termin("winter", "2026-11-10 01:00:00", "2026-11-11 01:00:00", True, "outlook")
        termin("sommer", "2026-07-10 02:00:00", "2026-07-11 02:00:00", True, "outlook")
        termin("mehrtaegig", "2026-11-10 01:00:00", "2026-11-13 01:00:00", True, "outlook")
        termin("umstellung", "2026-10-24 02:00:00", "2026-10-27 01:00:00", True, "outlook")
        termin("dialog", "2026-11-10 00:00:00", "2026-11-12 00:00:00", True, "erp")
        termin("uhrzeit", "2026-11-10 09:00:00", "2026-11-10 10:00:00", False, "erp")
        termin("api", "2026-11-10 09:00:00", "2026-11-11 10:00:00", True, "erp")


def _zeilen(engine) -> dict:
    with engine.connect() as c:
        return {t: (str(b)[:19], str(e)[:19], str(u)[:19]) for t, b, e, u in c.execute(text("SELECT title, start_at, end_at, updated_at FROM calendar_events"))}


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine)
    vorher = _zeilen(engine)
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert MIGRATION in _ok(_alembic(url, "current")).stdout
    nachher = _zeilen(engine)
    assert nachher["winter"] == ("2026-11-10 00:00:00", "2026-11-10 00:00:00", SYNC)
    assert nachher["sommer"] == ("2026-07-10 00:00:00", "2026-07-10 00:00:00", SYNC)
    assert nachher["mehrtaegig"] == ("2026-11-10 00:00:00", "2026-11-12 00:00:00", SYNC)
    assert nachher["umstellung"] == ("2026-10-24 00:00:00", "2026-10-26 00:00:00", SYNC)
    assert nachher["api"] == ("2026-11-10 00:00:00", "2026-11-11 00:00:00", SYNC)  # keine Form aus UTC: die Tage bleiben
    assert nachher["dialog"] == vorher["dialog"]
    assert nachher["uhrzeit"] == vorher["uhrzeit"]
    _ok(_alembic(url, "downgrade", VORHER))
    assert _zeilen(engine) == nachher  # die falsche Form kommt nicht zurück
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'ganztag.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_ganz_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
