"""Seit 1.9.39 (Stufe 4, R1 Nachrunde, Punkt 2): Gruppenzeiten werden je Mitglied genau wie Einzelzeiten gerundet.

    eine Funktion  app/time_tracking.py::gebucht_nach_zeitregel() -- Rundung der Zeitregeln (rounding_minutes) für jede neue Buchung: Stopp,
                   Gruppen-Stopp, Stopp im Gruppenfall, Nachtrag, Gruppen-Nachtrag, Ende nachtragen (einzeln und Gruppe); ohne Rundung bleibt
                   der Wert. Bis 1.9.38 rundeten nur Einzel-Stopp und Einzel-Nachtrag (im Router), der Stopp im Gruppenfall nur die Zeit
                   dessen, der stoppte. Wächter: unter app/ ruft nur sie rounded_hours() (außer dem DATEV-Export in time_backoffice.py).
    alte Buchungen bleiben, wie sie sind (keine Umrechnung)
"""

import ast
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app import berlin_time
from app.models import TeamEmployee, TimeEntry
from app.routers import time_tracking as time_tracking_router
from app.time_backoffice import load_time_settings
from app.time_tracking import start_group_timer, start_timer, stop_group_timer
from tests.test_v133_invoices import make_order_with_item
from tests.test_v224_field_view import make_employee, make_team

ROOT = Path(__file__).resolve().parents[1]
ROH = Decimal("5.1167")       # 07:00–12:07 = 5 h 7 min, unter 6 h keine Pause
GERUNDET = Decimal("5")       # auf 15 Minuten: 5,1167 / 0,25 = 20,47 -> 20 -> 5,00


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    team = make_team(db, "K-1", "Kolonne 1")
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    db.add_all([TeamEmployee(team_id=team.id, employee_id=mia.id, is_crew_leader=True), TeamEmployee(team_id=team.id, employee_id=tom.id)])
    db.commit()
    _rundung(db, 15)
    return {"db": db, "order": order, "team": team, "mia": mia, "tom": tom, "heute": berlin_time.berlin_today(),
            "client": router_test_client(db, time_tracking_router.router)}


def _rundung(db, minuten):
    load_time_settings(db).rounding_minutes = minuten
    db.commit()


def _gruppe(w, tag=None, um=time(7)):
    return start_group_timer(w["db"], employee_ids=[w["mia"].id, w["tom"].id], team_id=w["team"].id, actor_employee_id=w["mia"].id,
                             is_admin=True, order_id=w["order"].id, started_at=datetime.combine(tag or w["heute"], um))


def _stunden(w, gruppe_id=None):
    w["db"].expire_all()
    rows = w["db"].scalars(select(TimeEntry).where(TimeEntry.order_id == w["order"].id).order_by(TimeEntry.id)).all()
    return {r.employee_id: r.hours for r in rows}


def _ende(w, tag=None):
    return f"{(tag or w['heute']).isoformat()}T12:07:00"


def test_gruppen_stopp_rundet_je_mitglied(welt):
    """Angriff auf die alte Rechnung: der Gruppen-Stopp rundete nicht (5,1167 h je Mitglied)."""
    g = _gruppe(welt)
    antwort = welt["client"].post(f"/api/time-entry-groups/{g.id}/stop", json={"ended_at": _ende(welt), "break_minutes": 0})
    assert antwort.status_code == 200, antwort.text
    assert _stunden(welt) == {welt["mia"].id: GERUNDET, welt["tom"].id: GERUNDET}


def test_stopp_im_gruppenfall_rundet_alle(welt):
    """Angriff: bis 1.9.38 rundete der Stopp im Gruppenfall nur die Zeit dessen, der stoppte."""
    g = _gruppe(welt)
    eigene = next(e.id for e in welt["db"].scalars(select(TimeEntry).where(TimeEntry.employee_id == welt["mia"].id)).all())
    antwort = welt["client"].post(f"/api/time-entries/{eigene}/stop", json={"ended_at": _ende(welt), "break_minutes": 0})
    assert antwort.status_code == 200, antwort.text
    assert _stunden(welt) == {welt["mia"].id: GERUNDET, welt["tom"].id: GERUNDET}
    assert welt["db"].get(type(g), g.id).hours == GERUNDET


def test_gruppen_nachtrag_rundet_je_mitglied(welt):
    antwort = welt["client"].post("/api/time-entry-groups", json={
        "employee_ids": [welt["mia"].id, welt["tom"].id], "team_id": welt["team"].id, "order_id": welt["order"].id,
        "work_date": welt["heute"].isoformat(), "hours": "5.1", "entry_type": "site"})
    assert antwort.status_code == 200, antwort.text
    assert _stunden(welt) == {welt["mia"].id: GERUNDET, welt["tom"].id: GERUNDET}


def test_ende_nachtragen_der_gruppe_rundet_je_mitglied(welt):
    gestern = welt["heute"] - timedelta(days=1)
    g = _gruppe(welt, tag=gestern)
    eigene = next(e.id for e in welt["db"].scalars(select(TimeEntry).where(TimeEntry.employee_id == welt["mia"].id)).all())
    antwort = welt["client"].post(f"/api/time-entries/{eigene}/ende-nachtragen", json={"ende": _ende(welt, gestern)})
    assert antwort.status_code == 200, antwort.text
    assert _stunden(welt) == {welt["mia"].id: GERUNDET, welt["tom"].id: GERUNDET}
    assert g.id


def test_einzel_stopp_rundet_wie_die_gruppe(welt):
    """Gegenprobe: der Einzel-Stopp rundet wie bisher -- dieselben 5,00 h wie je Mitglied der Gruppe."""
    row = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    antwort = welt["client"].post(f"/api/time-entries/{row.id}/stop", json={"ended_at": _ende(welt), "break_minutes": 0})
    assert Decimal(antwort.json()["hours"]) == GERUNDET


def test_ohne_rundung_bleibt_der_wert(welt):
    _rundung(welt["db"], 0)
    g = _gruppe(welt)
    welt["client"].post(f"/api/time-entry-groups/{g.id}/stop", json={"ended_at": _ende(welt), "break_minutes": 0})
    assert _stunden(welt) == {welt["mia"].id: ROH, welt["tom"].id: ROH}


def test_alte_gruppenbuchungen_bleiben_unveraendert(welt):
    """Gegenprobe: eine schon gebuchte Gruppenzeit (ungerundet) wird durch die neue Regel nicht umgerechnet."""
    _rundung(welt["db"], 0)
    alt = _gruppe(welt)
    stop_group_timer(welt["db"], alt.id, ended_at=datetime.combine(welt["heute"], time(12, 7)))
    vorher = _stunden(welt)
    _rundung(welt["db"], 15)
    neu = start_group_timer(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id,
                            actor_employee_id=welt["mia"].id, is_admin=True, order_id=welt["order"].id,
                            started_at=datetime.combine(welt["heute"], time(13)))
    welt["client"].post(f"/api/time-entry-groups/{neu.id}/stop", json={"ended_at": f"{welt['heute'].isoformat()}T18:07:00", "break_minutes": 0})
    welt["db"].expire_all()
    alte = {e.employee_id: e.hours for e in welt["db"].scalars(select(TimeEntry).where(TimeEntry.ended_at == datetime.combine(welt["heute"], time(12, 7)))).all()}
    assert alte == vorher == {welt["mia"].id: ROH, welt["tom"].id: ROH}


def test_waechter_eine_rundung():
    """Unter app/ ruft nur gebucht_nach_zeitregel() die Rundung der Zeitregeln -- außer dem DATEV-Export (rundet beim Summieren)."""
    funde = []
    for pfad in sorted((ROOT / "app").rglob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for fn in ast.walk(baum):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for knoten in ast.walk(fn):
                if isinstance(knoten, ast.Call) and getattr(knoten.func, "id", getattr(knoten.func, "attr", None)) == "rounded_hours":
                    funde.append((pfad.relative_to(ROOT).as_posix(), fn.name))
    assert sorted(set(funde)) == [("app/time_backoffice.py", "build_datev_export"), ("app/time_tracking.py", "gebucht_nach_zeitregel")]
