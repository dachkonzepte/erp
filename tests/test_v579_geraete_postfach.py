"""Version 1.9.161 (Stufe 6, R2, Punkt 5): mehrere Postfächer, ein Postfach gehört einem Konto oder einem Gerät.

    Zuordnung   nur Admin; eine Adresse genau einem Konto oder Gerät (409 mit dem Namen), auch über beide Tabellen
    Abgleich    Termin aus dem Kran-Postfach hängt am Kran, ohne Konto; aus dem ERP: POST, PATCH, DELETE ins Kran-Postfach; Serienvorkommen ebenso; danach Ruhe
    Kalender    Liste nennt das Gerät, Auswahl im Dialog, wechseln zwischen Konto und Gerät zieht um; genau eines von beiden
    Einsatz     ein Termin am Kran an einem Arbeitstag des Einsatzes: 409 „Gerät doppelt“, trotzdem planbar; nicht an einem freien Tag, nicht an einem anderen Gerät, nicht bei geschlossenem Auftrag
                die Tafel zeichnet ihn noch nicht (kommt mit R4)
    Cron        gleicht Konten und Geräte ab, inaktive nicht
    Bestand     Migration b6e1d8f37a42
"""

import importlib.util
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.auftragsstatus import status_aendern
from app.models import CalendarEvent, OperationalResource, OutlookSeriesOccurrence
from app.outlook_calendar_sync import alle_postfaecher, postfach_des_geraets, sync_postfach, sync_user_calendar
from app.planning import planning_board
from app.routers.calendar_events import router as calendar_router
from app.routers.outlook_sync_settings import router as settings_router
from app.routers.planning import router as planning_router
from app.routers.resource_planning import router as resource_router
from app.routers.users import router as users_router
from tests.outlook_attrappe import Microsoft
from tests.test_v090_planning_board import setup_order
from tests.test_v297_outlook_calendar_sync import _enable_sync, _make_user, db_session
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v563_konflikte_beim_speichern import MONTAG, _body, _kolonne, _kran, _person

ROOT = Path(__file__).resolve().parent.parent
URLOPEN = "app.outlook_calendar_sync.urllib.request.urlopen"
KRAN, ANNA = "kran@x.de", "anna@x.de"
RUHE = ("created", "updated", "deleted", "pushed_created", "pushed_updated", "push_failed", "series_created", "series_updated", "series_deleted")
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    _enable_sync(db)
    ms = Microsoft()
    ms.postfach(KRAN)
    ms.postfach(ANNA)

    class Welt:
        pass

    w = Welt()
    w.db, w.ms, w.bauen = db, ms, router_test_client
    w.kran = _kran(db)
    w.anna = _make_user(db, username="anna", mailbox=ANNA)
    w.client = router_test_client(db, calendar_router, settings_router, planning_router, resource_router, users_router)
    assert w.client.put(f"/api/outlook-sync-settings/geraete/{w.kran.id}", json={"outlook_mailbox": " Kran@X.de "}).status_code == 200
    with patch(URLOPEN, side_effect=ms.urlopen):
        yield w


def _geraet(w):
    return w.db.get(OperationalResource, w.kran.id)


def _lauf(w):
    return sync_postfach(w.db, postfach_des_geraets(_geraet(w)))


def _termin(w, **werte):
    start = werte.pop("start", datetime(2026, 11, 3, 9, 0))
    antwort = w.client.post("/api/calendar-events", json={"title": "Vermietung", "start_at": start.isoformat(), "end_at": werte.pop("ende", start + timedelta(hours=2)).isoformat(), "resource_id": w.kran.id, **werte})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


# --- Zuordnung ----------------------------------------------------------------------------------------

def test_die_adresse_steht_klein_am_geraet(welt):
    assert _geraet(welt).outlook_mailbox == KRAN


@pytest.mark.parametrize("rolle", ["buero_finanzen", "buero_auftrag", "field"])
def test_nur_der_admin_ordnet_zu(welt, rolle):
    client = welt.bauen(welt.db, settings_router, role=rolle)
    assert client.put(f"/api/outlook-sync-settings/geraete/{welt.kran.id}", json={"outlook_mailbox": "x@x.de"}).status_code == 403
    assert _geraet(welt).outlook_mailbox == KRAN


def test_eine_adresse_gehoert_genau_einem(welt):
    w = welt
    antwort = w.client.put(f"/api/outlook-sync-settings/geraete/{w.kran.id}", json={"outlook_mailbox": "ANNA@x.de"})
    assert antwort.status_code == 409 and "anna" in antwort.json()["detail"]
    konto = {"username": "anna", "display_name": "Anna", "role": "buero_auftrag", "active": True}
    antwort = w.client.put(f"/api/users/{w.anna.id}", json={**konto, "outlook_mailbox": KRAN})
    assert antwort.status_code == 409 and "Kran 30 m" in antwort.json()["detail"]
    zweites = w.client.post("/api/resources", json={"resource_number": "K-2", "resource_type": "Maschine", "name": "Kran 2", "identifier": "K2"}).json()
    antwort = w.client.put(f"/api/outlook-sync-settings/geraete/{zweites['id']}", json={"outlook_mailbox": KRAN})
    assert antwort.status_code == 409 and "Kran 30 m" in antwort.json()["detail"]
    assert w.client.put(f"/api/outlook-sync-settings/geraete/{w.kran.id}", json={"outlook_mailbox": KRAN}).status_code == 200  # das eigene


def test_unbekanntes_geraet_404(welt):
    assert welt.client.put("/api/outlook-sync-settings/geraete/9999", json={"outlook_mailbox": "x@x.de"}).status_code == 404


def test_das_feld_ist_pflicht(welt):
    assert welt.client.put(f"/api/outlook-sync-settings/geraete/{welt.kran.id}", json={}).status_code == 422
    assert _geraet(welt).outlook_mailbox == KRAN


def test_alle_postfaecher_ohne_inaktive(welt):
    w = welt
    assert [(p.adresse, bool(p.konto), bool(p.geraet)) for p in alle_postfaecher(w.db)] == [(ANNA, True, False), (KRAN, False, True)]
    _geraet(w).active = False
    w.anna.active = False
    w.db.commit()
    assert alle_postfaecher(w.db) == []


# --- Abgleich ----------------------------------------------------------------------------------------

def test_termin_aus_outlook_haengt_am_kran(welt):
    w = welt
    kennung = w.ms.postfach(KRAN).anlegen("Nach Telefonat", datetime(2026, 11, 3, 8), datetime(2026, 11, 3, 12))
    assert _lauf(w)["created"] == 1
    zeile = w.db.scalar(select(CalendarEvent).where(CalendarEvent.outlook_event_id == kennung))
    assert (zeile.resource_id, zeile.owner_user_id, zeile.outlook_postfach, zeile.external_source) == (w.kran.id, None, KRAN, "outlook")


def test_termin_aus_dem_erp_geht_ins_kran_postfach_und_zurueck(welt):
    w = welt
    daten = _termin(w)
    zeile = w.db.get(CalendarEvent, daten["id"])
    assert zeile.outlook_postfach == KRAN and zeile.outlook_event_id in w.ms.postfach(KRAN).events
    assert w.ms.postfach(ANNA).events == {}
    assert w.client.put(f"/api/calendar-events/{zeile.id}", json={"title": "Geändert"}).status_code == 200
    assert w.ms.postfach(KRAN).events[zeile.outlook_event_id]["subject"] == "Geändert"
    kennung = zeile.outlook_event_id
    assert w.client.delete(f"/api/calendar-events/{zeile.id}").status_code == 200
    assert kennung not in w.ms.postfach(KRAN).events


def test_aenderung_in_outlook_kommt_an_und_danach_ist_ruhe(welt):
    w = welt
    daten = _termin(w)
    _lauf(w)
    kennung = w.db.get(CalendarEvent, daten["id"]).outlook_event_id
    w.ms.postfach(KRAN).aendern(kennung, subject="In Outlook verschoben")
    assert _lauf(w)["updated"] == 1
    assert w.db.get(CalendarEvent, daten["id"]).title == "In Outlook verschoben"
    for _ in range(4):
        ergebnis = _lauf(w)
        assert {k: ergebnis[k] for k in RUHE} == dict.fromkeys(RUHE, 0), ergebnis


def test_serienvorkommen_haengen_am_kran(welt):
    w = welt
    w.ms.postfach(KRAN).add_series("Wöchentlich vermietet", datetime.utcnow() + timedelta(days=1), count=3)
    assert _lauf(w)["series_created"] == 3
    zeilen = w.db.scalars(select(OutlookSeriesOccurrence)).all()
    assert {(z.resource_id, z.owner_user_id, z.outlook_postfach) for z in zeilen} == {(w.kran.id, None, KRAN)}
    daten = w.client.get("/api/calendar-series-occurrences").json()
    assert {(d["resource_id"], d["resource_name"]) for d in daten} == {(w.kran.id, "Kran 30 m")}


def test_postfach_am_geraet_entfernen(welt):
    w = welt
    w.ms.postfach(KRAN).add_series("Serie", datetime.utcnow() + timedelta(days=1), count=2)
    w.ms.postfach(KRAN).anlegen("Einzeln", datetime(2026, 11, 3, 8), datetime(2026, 11, 3, 12))
    _lauf(w)
    assert w.client.put(f"/api/outlook-sync-settings/geraete/{w.kran.id}", json={"outlook_mailbox": ""}).status_code == 200
    assert w.db.scalar(select(func.count()).select_from(OutlookSeriesOccurrence)) == 0
    assert w.db.scalar(select(func.count()).select_from(CalendarEvent)) == 1
    assert w.client.get("/api/calendar-events/geraete").json() == []


def test_der_cron_gleicht_konten_und_geraete_ab(welt):
    w = welt
    w.ms.postfach(KRAN).anlegen("Kran", datetime(2026, 11, 3, 8), datetime(2026, 11, 3, 12))
    w.ms.postfach(ANNA).anlegen("Anna", datetime(2026, 11, 3, 8), datetime(2026, 11, 3, 12))
    spec = importlib.util.spec_from_file_location("sync_outlook_calendars", ROOT / "scripts" / "sync_outlook_calendars.py")
    skript = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(skript)
    schliesst_nicht = w.db.close
    w.db.close = lambda: None
    try:
        with patch.object(skript, "SessionLocal", return_value=w.db), patch.object(skript, "configure_logging"):
            assert skript.main() == 0
    finally:
        w.db.close = schliesst_nicht
    assert {(z.title, z.resource_id, z.owner_user_id) for z in w.db.scalars(select(CalendarEvent))} == {("Kran", w.kran.id, None), ("Anna", None, w.anna.id)}


def test_oeffnen_des_kalenders_gleicht_nur_das_eigene_ab(welt):
    w = welt
    with patch("app.routers.calendar_events.sync_user_calendar", return_value={}) as aufruf:
        assert w.bauen(w.db, calendar_router, role="buero_auftrag", user_id=w.anna.id).post("/api/calendar-events/sync-outlook").status_code == 200
    assert aufruf.call_args.args[1].id == w.anna.id
    sync_user_calendar(w.db, w.anna)
    assert {u.split("/users/")[1].split("/")[0] for m, u in w.ms.anfragen if m == "GET"} == {"anna%40x.de"}


# --- Kalender ----------------------------------------------------------------------------------------

def test_die_liste_nennt_das_geraet(welt):
    w = welt
    _termin(w)
    zeile = w.client.get("/api/calendar-events").json()[0]
    assert (zeile["resource_id"], zeile["resource_name"], zeile["owner_user_id"], zeile["owner_name"]) == (w.kran.id, "Kran 30 m", None, None)


def test_auswahl_der_geraete(welt):
    w = welt
    assert w.client.get("/api/calendar-events/geraete").json() == [{"id": w.kran.id, "name": "Kran 30 m"}]
    assert w.bauen(w.db, calendar_router, role="field").get("/api/calendar-events/geraete").status_code == 403


def test_privat_am_kran_ist_fuer_alle_belegt(welt):
    w = welt
    _termin(w, is_private=True, title="Vertraulich")
    zeile = w.client.get("/api/calendar-events").json()[0]
    assert zeile["title"] == "Belegt" and "location" not in zeile and zeile["resource_name"] == "Kran 30 m"


@pytest.mark.parametrize("werte", [{"owner_user_id": "anna", "resource_id": "kran"}, {"resource_id": 9999}])
def test_nicht_beides_und_nur_was_es_gibt(welt, werte):
    w = welt
    koerper = {k: (w.anna.id if v == "anna" else w.kran.id if v == "kran" else v) for k, v in werte.items()}
    antwort = w.client.post("/api/calendar-events", json={"title": "T", "start_at": "2026-11-03T09:00:00", "end_at": "2026-11-03T10:00:00", **koerper})
    assert antwort.status_code == 422


def test_ohne_beides_der_eigene_besitzer(welt):
    w = welt
    client = w.bauen(w.db, calendar_router, role="buero_auftrag", user_id=w.anna.id)
    antwort = client.post("/api/calendar-events", json={"title": "T", "start_at": "2026-11-03T09:00:00", "end_at": "2026-11-03T10:00:00"})
    assert antwort.status_code == 200 and antwort.json()["owner_user_id"] == w.anna.id


def test_vom_konto_zum_kran_und_zurueck_zieht_um(welt):
    w = welt
    antwort = w.client.post("/api/calendar-events", json={"title": "T", "start_at": "2026-11-03T09:00:00", "end_at": "2026-11-03T10:00:00", "owner_user_id": w.anna.id})
    kennung = antwort.json()["id"]
    zeile = w.db.get(CalendarEvent, kennung)
    alt = zeile.outlook_event_id
    assert zeile.outlook_postfach == ANNA

    antwort = w.client.put(f"/api/calendar-events/{kennung}", json={"resource_id": w.kran.id})
    assert antwort.status_code == 200 and (antwort.json()["owner_user_id"], antwort.json()["resource_id"]) == (None, w.kran.id)
    w.db.refresh(zeile)
    assert zeile.outlook_postfach == KRAN and zeile.outlook_event_id in w.ms.postfach(KRAN).events and alt not in w.ms.postfach(ANNA).events

    antwort = w.client.put(f"/api/calendar-events/{kennung}", json={"owner_user_id": w.anna.id, "resource_id": None})
    assert antwort.status_code == 200 and (antwort.json()["owner_user_id"], antwort.json()["resource_id"]) == (w.anna.id, None)
    w.db.refresh(zeile)
    assert zeile.outlook_postfach == ANNA and w.ms.postfach(KRAN).events == {}

    assert w.client.put(f"/api/calendar-events/{kennung}", json={"owner_user_id": None, "resource_id": None}).status_code == 422


def test_ein_geraet_mit_terminen_wird_nur_deaktiviert(welt):
    w = welt
    _termin(w)
    antwort = w.client.delete(f"/api/resources/{w.kran.id}").json()
    assert antwort == {"deleted": False, "deactivated": True}
    assert alle_postfaecher(w.db) == [next(p for p in alle_postfaecher(w.db) if p.konto)]


def test_die_seite_kennt_den_kran():
    seite = (ROOT / "app" / "templates" / "calendar.html").read_text(encoding="utf-8")
    assert "api('/api/calendar-events/geraete')" in seite
    assert "resource_id:besitzer[0]==='g'?besitzerId:null" in seite
    assert "ownerOptionsHtml(besitzerWert(e),besitzerName(e))" in seite


# --- Einsatz ----------------------------------------------------------------------------------------

def _einsatz_welt(w):
    team = _kolonne(w.db, "A", [_person(w.db, "M-1", "Tom")], [w.kran])
    return team, setup_order(w.db, "1")


def _am_kran(w, tag, *, titel="Vermietung Müller", privat=False, modell=CalendarEvent, kennung=None, bis=None):
    werte = dict(title=titel, start_at=datetime.combine(tag, datetime.min.time()).replace(hour=8), end_at=datetime.combine(bis or tag, datetime.min.time()).replace(hour=12),
                 resource_id=w.kran.id, is_private=privat, outlook_postfach=KRAN, outlook_event_id=kennung or uuid.uuid4().hex)
    if modell is OutlookSeriesOccurrence:
        werte["occurrence_type"] = "occurrence"
    w.db.add(modell(**werte))
    w.db.commit()


def test_termin_am_kran_warnt_beim_speichern_und_ist_trotzdem_planbar(welt):
    w = welt
    team, order = _einsatz_welt(w)
    _am_kran(w, MONTAG + timedelta(days=1))
    antwort = w.client.post("/api/planning/slots", json=_body(order, team))
    assert antwort.status_code == 409, antwort.text
    warnung = antwort.json()["warnungen"]
    assert [(k["type"], k["label"], k["date"]) for k in warnung] == [("resource", "Kran 30 m · Termin: Vermietung Müller", (MONTAG + timedelta(days=1)).isoformat())]
    antwort = w.client.post("/api/planning/slots", json=_body(order, team, trotzdem_planen=True))
    assert antwort.status_code == 200
    assert [k["type"] for k in antwort.json()["warnungen"]] == ["resource"]


def test_verschieben_auf_einen_belegten_tag_fragt(welt):
    w = welt
    team, order = _einsatz_welt(w)
    _am_kran(w, MONTAG + timedelta(days=7))
    slot = w.client.post("/api/planning/slots", json=_body(order, team)).json()
    neu = (MONTAG + timedelta(days=7)).isoformat()
    antwort = w.client.put(f"/api/planning/slots/{slot['id']}", json={"start_date": neu, "end_date": neu})
    assert antwort.status_code == 409 and antwort.json()["warnungen"][0]["type"] == "resource"


def test_seriendaten_zaehlen_und_privat_steht_als_belegt_da(welt):
    w = welt
    team, order = _einsatz_welt(w)
    _am_kran(w, MONTAG, modell=OutlookSeriesOccurrence, titel="Jede Woche", privat=True)
    antwort = w.client.post("/api/planning/slots", json=_body(order, team))
    assert antwort.status_code == 409
    assert antwort.json()["warnungen"][0]["label"] == "Kran 30 m · Termin: Belegt"
    assert "Jede Woche" not in antwort.text


def test_mehrtaegiger_termin_warnt_einmal(welt):
    w = welt
    team, order = _einsatz_welt(w)
    _am_kran(w, MONTAG - timedelta(days=3), bis=MONTAG + timedelta(days=1))
    antwort = w.client.post("/api/planning/slots", json=_body(order, team))
    assert antwort.status_code == 409
    assert [k["date"] for k in antwort.json()["warnungen"]] == [MONTAG.isoformat()]  # der erste Arbeitstag des Einsatzes, den er berührt


@pytest.mark.parametrize("fall", ["danach", "anderes_geraet", "konto", "samstag"])
def test_was_nicht_warnt(welt, fall):
    w = welt
    team, order = _einsatz_welt(w)
    if fall == "danach":
        _am_kran(w, MONTAG + timedelta(days=30))
    elif fall == "anderes_geraet":
        anderes = w.client.post("/api/resources", json={"resource_number": "K-9", "resource_type": "Maschine", "name": "Anderes", "identifier": "K9"}).json()
        w.db.add(CalendarEvent(title="Fremd", start_at=datetime(2026, 11, 3, 8), end_at=datetime(2026, 11, 3, 12), resource_id=anderes["id"]))
        w.db.commit()
    elif fall == "konto":
        w.db.add(CalendarEvent(title="Annas Termin", start_at=datetime(2026, 11, 3, 8), end_at=datetime(2026, 11, 3, 12), owner_user_id=w.anna.id))
        w.db.commit()
    else:
        _am_kran(w, date(2026, 11, 7))  # Samstag: an dem Tag wird nicht gearbeitet
        antwort = w.client.post("/api/planning/slots", json=_body(order, team, start=date(2026, 11, 6), ende=date(2026, 11, 9)))
        assert antwort.status_code == 200, antwort.text
        return
    assert w.client.post("/api/planning/slots", json=_body(order, team)).status_code == 200


def test_einsatz_nur_am_samstag_zaehlt_seine_tage(welt):
    w = welt
    team, order = _einsatz_welt(w)
    _am_kran(w, date(2026, 11, 7))
    antwort = w.client.post("/api/planning/slots", json=_body(order, team, start=date(2026, 11, 7), ende=date(2026, 11, 7)))
    assert antwort.status_code == 409


def test_geschlossener_auftrag_warnt_nicht(welt):
    w = welt
    team, order = _einsatz_welt(w)
    slot = w.client.post("/api/planning/slots", json=_body(order, team)).json()
    status_aendern(w.db, order.id, "storniert", begruendung="abgesagt")
    w.db.commit()
    _am_kran(w, MONTAG)
    antwort = w.client.put(f"/api/planning/slots/{slot['id']}", json={"start_date": MONTAG.isoformat(), "end_date": (MONTAG + timedelta(days=3)).isoformat()})
    assert antwort.status_code == 200, antwort.text


def test_die_tafel_zeichnet_ihn_noch_nicht(welt):
    """Anzeige auf der Tafel kommt mit R4: dort steht der Einsatz bis dahin ohne diese Warnung."""
    w = welt
    team, order = _einsatz_welt(w)
    _am_kran(w, MONTAG)
    assert w.client.post("/api/planning/slots", json=_body(order, team, trotzdem_planen=True)).status_code == 200
    tafel = planning_board(w.db, MONTAG, MONTAG + timedelta(days=6))
    assert tafel["conflict_count"] == 0


# --- Genau eines von beiden --------------------------------------------------------------------------

@pytest.mark.parametrize("werte", [{}, {"owner_user_id": 1, "resource_id": 1}])
def test_die_datenbank_verlangt_genau_einen_besitzer(werte):
    db = db_session()
    db.add(CalendarEvent(title="T", start_at=datetime(2026, 11, 3), end_at=datetime(2026, 11, 3), **werte))
    with pytest.raises(IntegrityError):
        db.commit()


# --- Bestand -----------------------------------------------------------------------------------------

MIGRATION = "b6e1d8f37a42"
VORHER = "9d4b6f02a7c1"
ZEIT = "2026-09-01 08:00:00"


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        konto = c.execute(text("INSERT INTO app_users (username, display_name, password_hash, role, active, outlook_mailbox, created_at, updated_at) VALUES ('a', 'A', 'x', 'admin', :an, 'a@x.de', :z, :z) RETURNING id"), {"an": True, "z": ZEIT}).scalar()
        c.execute(text("INSERT INTO calendar_events (title, start_at, end_at, all_day, owner_user_id, is_private, external_source, outlook_postfach, outlook_event_id, created_at, updated_at) "
                       "VALUES ('Bestand', :z, :z, :f, :o, :f, 'erp', 'a@x.de', 'K1', :z, :z)"), {"z": ZEIT, "f": False, "o": konto})
        c.execute(text("INSERT INTO operational_resources (resource_type, name, active, created_at, updated_at) VALUES ('Maschine', 'Kran', :an, :z, :z)"), {"an": True, "z": ZEIT})
        geraet = c.execute(text("SELECT id FROM operational_resources")).scalar()

    _ok(_alembic(url, "upgrade", MIGRATION))
    assert MIGRATION in _ok(_alembic(url, "current")).stdout
    with engine.begin() as c:
        assert c.execute(text("SELECT title, owner_user_id, resource_id, outlook_postfach FROM calendar_events")).one() == ("Bestand", konto, None, "a@x.de")
        c.execute(text("UPDATE operational_resources SET outlook_mailbox = 'kran@x.de'"))
        c.execute(text("INSERT INTO calendar_events (title, start_at, end_at, all_day, resource_id, is_private, external_source, created_at, updated_at) VALUES ('Am Kran', :z, :z, :f, :g, :f, 'erp', :z, :z)"),
                  {"z": ZEIT, "f": False, "g": geraet})
        c.execute(text("INSERT INTO outlook_series_occurrences (resource_id, outlook_postfach, outlook_event_id, occurrence_type, title, start_at, end_at, all_day, is_private, created_at, updated_at) "
                       "VALUES (:g, 'kran@x.de', 'S1', 'occurrence', 'S', :z, :z, :f, :f, :z, :z)"), {"z": ZEIT, "f": False, "g": geraet})
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            c.execute(text("INSERT INTO calendar_events (title, start_at, end_at, all_day, is_private, external_source, created_at, updated_at) VALUES ('Niemand', :z, :z, :f, :f, 'erp', :z, :z)"), {"z": ZEIT, "f": False})

    _ok(_alembic(url, "downgrade", VORHER))
    assert VORHER in _ok(_alembic(url, "current")).stdout
    with engine.connect() as c:
        assert c.execute(text("SELECT title FROM calendar_events")).scalars().all() == ["Bestand"]
        assert c.execute(text("SELECT count(*) FROM outlook_series_occurrences")).scalar() == 0
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'geraet.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_geraet_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
