"""Version 1.9.148 (Stufe 6, R1, Punkt 6): P3, P4, P6, P13.

    P3   Planungsvorschlag für Büro – Auftrag: ohne Art nur der Name (bis 1.9.147 „Lia Lang (undefined)“)
    P4   leere Stunden beim neuen Einsatz = Reststunden des Auftrags (bis 1.9.147 schickte die Seite 0); beim Bearbeiten leer = unverändert
    P6   Kalender: der Zeitraum ist Berliner Wandzeit -- Termin 23:30 im Winter und 22:30 im Sommer in Tag, Woche und Monat; auch eine Grenze mit Zeitzone wird umgerechnet
    P13  Kapazitätsmeldung und Formel deutsch
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.calendar_events import list_events, zeitraum_berlin
from app.main import create_team
from app.models import AppUser, CalendarEvent, Employee, EmployeeAbsence, OrderItem, OrderItemCalculationSnapshot, OutlookSeriesOccurrence
from app.outlook_calendar_sync import list_series_occurrences
from app.planning import planning_suggestion
from app.routers.calendar_events import router as kalender_router
from app.routers.planning import router as planning_router
from app.schemas import TeamCreate, TeamEmployeeInput
from tests.test_v090_planning_board import setup_order

ROOT = Path(__file__).resolve().parent.parent
MONTAG = date(2026, 11, 2)


def _kolonne(db, *namen):
    personen = []
    for i, name in enumerate(namen):
        emp = Employee(employee_number=f"M-{i}", first_name=name, last_name="Test", employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True)
        db.add(emp)
        personen.append(emp)
    db.commit()
    team = create_team(TeamCreate(team_number="A", name="Kolonne A", employees=[TeamEmployeeInput(employee_id=p.id, role="Monteur") for p in personen], resources=[]), db)
    return team, personen


def _soll(db, order, minuten):
    """Soll aus der Kalkulation: eine Position mit genau diesen Minuten je Menge."""
    for item in db.query(OrderItem).filter_by(order_id=order.id):
        db.delete(item)
    db.flush()
    item = OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Eindecken", quantity=Decimal("1"), unit="St", unit_price=Decimal("1"))
    db.add(item)
    db.flush()
    db.add(OrderItemCalculationSnapshot(order_item_id=item.id, site_time_minutes=Decimal(minuten), workshop_time_minutes=Decimal("0")))
    db.commit()
    db.expire_all()


# --- P4 ------------------------------------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture()
def tafel(threaded_db_session, router_test_client):
    db = threaded_db_session
    return db, router_test_client(db, planning_router)


def _einsatz(client, order, team, von, bis, **mehr):
    antwort = client.post("/api/planning/slots", json={"order_id": order.id, "team_id": team.id, "start_date": von.isoformat(), "end_date": bis.isoformat(), "trotzdem_planen": True, **mehr})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def test_leere_stunden_sind_die_reststunden_des_auftrags(tafel):
    db, client = tafel
    team, _ = _kolonne(db, "Tom")
    order = setup_order(db)
    _soll(db, order, 1800)  # 30 h
    erster = _einsatz(client, order, team, MONTAG, MONTAG, planned_hours="12")
    assert Decimal(str(erster["planned_hours"])) == Decimal("12")
    zweiter = _einsatz(client, order, team, date(2026, 11, 9), date(2026, 11, 10), planned_hours=None)
    assert Decimal(str(zweiter["planned_hours"])) == Decimal("18")
    dritter = _einsatz(client, order, team, date(2026, 11, 16), date(2026, 11, 16), planned_hours=None)
    assert Decimal(str(dritter["planned_hours"])) == Decimal("0")  # nichts mehr übrig


def test_seite_schickt_leer_als_null_und_beim_bearbeiten_nichts():
    html = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    neu = html[html.index("async function saveNew("):]
    assert "planned_hours:zahlFeld('newPlannedHours',{leer:null})" in neu[:neu.index("\n")]
    aendern = html[html.index("async function saveEdit("):]
    assert "...(stunden===null?{}:{planned_hours:stunden})" in aendern[:aendern.index("\n")]
    assert 'placeholder="leer = Reststunden des Auftrags"' in html and 'placeholder="leer = unverändert"' in html


# --- P3 ------------------------------------------------------------------------------------------------------------------------------------------------------------

def test_vorschlag_nennt_die_art_nur_wenn_sie_da_ist(tafel, threaded_db_session, router_test_client):
    db = threaded_db_session
    team, (lia, tom) = _kolonne(db, "Lia", "Tom")
    order = setup_order(db)
    _soll(db, order, 2400)
    db.add(EmployeeAbsence(employee_id=lia.id, absence_type="Krankheit", absence_category="krankheit", start_date=MONTAG, end_date=MONTAG))
    db.commit()
    payload = {"order_id": order.id, "team_id": team.id, "start_date": MONTAG.isoformat()}
    tag = lambda rolle: router_test_client(db, planning_router, role=rolle).post("/api/planning/suggestion", json=payload).json()["days"][0]["absent_employees"][0]  # noqa: E731
    assert tag("buero_auftrag") == {"name": "Lia Test"}
    assert tag("buero_finanzen") == {"name": "Lia Test", "type": "Krankheit"}
    html = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    assert "a=>a.type?a.name+' ('+a.type+')':a.name" in html
    assert "a.name+' ('+a.type+')').join" not in html


# --- P13 -----------------------------------------------------------------------------------------------------------------------------------------------------------

def test_kapazitaet_und_formel_deutsch(tafel):
    db, client = tafel
    team, _ = _kolonne(db, "Tom", "Mia", "Ole", "Lia")
    order = setup_order(db)
    _soll(db, order, 1440)  # 24 h
    vorschlag = planning_suggestion(db, order_id=order.id, team_id=team.id, start_date=MONTAG, daily_work_hours=Decimal("8"), travel_hours_per_employee_day=Decimal("0"))
    assert vorschlag["formula"] == "24,00 h / (4 MA × (8,00 h − 0,00 h)) = 0,75 Teamtage"
    daten = _einsatz(client, order, team, MONTAG, MONTAG, planned_hours="56.5")
    assert [k["label"] for k in daten["hinweise"]] == ["Kapazität reicht um 24,50 h nicht aus"]


# --- P6 ------------------------------------------------------------------------------------------------------------------------------------------------------------

WINTER = datetime(2026, 1, 15, 23, 30)
SOMMER = datetime(2026, 7, 15, 22, 30)


def _kalender(db):
    konto = AppUser(username="anna", display_name="Anna", password_hash="x", role="admin")
    db.add(konto)
    db.flush()
    for wann, titel in ((WINTER, "Winter spät"), (SOMMER, "Sommer spät")):
        db.add(CalendarEvent(title=titel, start_at=wann, end_at=wann.replace(minute=45), owner_user_id=konto.id))
        db.add(OutlookSeriesOccurrence(owner_user_id=konto.id, outlook_event_id=f"S-{titel}", occurrence_type="occurrence", title=f"Serie {titel}", start_at=wann, end_at=wann.replace(minute=45)))
    db.commit()
    return konto


def test_tag_und_grenzen_in_wandzeit(threaded_db_session):
    db = threaded_db_session
    _kalender(db)
    for von, bis, titel in ((datetime(2026, 1, 15), datetime(2026, 1, 16), "Winter spät"), (datetime(2026, 7, 15), datetime(2026, 7, 16), "Sommer spät")):
        assert [e["title"] for e in list_events(db, start=von, end=bis)] == [titel]
        assert [e["title"] for e in list_series_occurrences(db, start=von, end=bis)] == [f"Serie {titel}"]


def test_grenze_mit_zeitzone_wird_umgerechnet():
    """Ein Aufrufer mit „…Z“: Mitternacht Berlin im Winter ist 23:00 UTC, im Sommer 22:00 UTC."""
    assert zeitraum_berlin(datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc)) == datetime(2026, 1, 16, 0, 0)
    assert zeitraum_berlin(datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)) == datetime(2026, 7, 15, 0, 0)
    assert zeitraum_berlin(datetime(2026, 7, 15, 0, 0)) == datetime(2026, 7, 15, 0, 0)  # ohne Zeitzone schon Wandzeit, nicht als UTC gelesen
    assert zeitraum_berlin(None) is None


@pytest.mark.parametrize("von,bis,titel", [
    ("2026-01-15T00:00:00", "2026-01-16T00:00:00", "Winter spät"),  # Tag
    ("2026-01-12T00:00:00", "2026-01-19T00:00:00", "Winter spät"),  # Woche
    ("2025-12-29T00:00:00", "2026-02-02T00:00:00", "Winter spät"),  # Monat
    ("2026-07-15T00:00:00", "2026-07-16T00:00:00", "Sommer spät"),
    ("2026-07-13T00:00:00", "2026-07-20T00:00:00", "Sommer spät"),
    ("2026-06-29T00:00:00", "2026-08-03T00:00:00", "Sommer spät"),
    ("2026-01-14T23:00:00Z", "2026-01-15T23:00:00Z", "Winter spät"),  # alte Form der Seite: mit Zeitzone
    ("2026-07-14T22:00:00Z", "2026-07-15T22:00:00Z", "Sommer spät"),
])
def test_api_findet_den_spaeten_termin(threaded_db_session, router_test_client, von, bis, titel):
    db = threaded_db_session
    _kalender(db)
    client = router_test_client(db, kalender_router)
    antwort = client.get("/api/calendar-events", params={"start": von, "end": bis})
    assert antwort.status_code == 200, antwort.text
    assert titel in [e["title"] for e in antwort.json()]
    antwort = client.get("/api/calendar-series-occurrences", params={"start": von, "end": bis})
    assert f"Serie {titel}" in [e["title"] for e in antwort.json()]


def test_seite_schickt_wandzeit_kein_utc():
    html = (ROOT / "app/templates/calendar.html").read_text(encoding="utf-8")
    assert "toISOString" not in html
    assert "start:toLocalIso(toDateStr(start)),end:toLocalIso(toDateStr(end))" in html
