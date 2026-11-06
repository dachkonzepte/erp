"""Seit 1.9.231 (Stufe 6, R3a, Punkt 0b, Festlegung 1.9.223 Nr. 6): keine Buchung wird mehr gerundet -- weder einzeln noch je Mitglied einer
Gruppe; gerundet wird nur die Arbeit eines Tags im Lohn (arbeit_des_tags(), 0,25 h). 1.9.39–1.9.230 rundete gebucht_nach_zeitregel() jede neue
Buchung nach der Einstellung „Rundung“ der Zeitregeln (rounding_minutes), dieser Test prüfte das je Weg (Stopp, Gruppen-Stopp, Stopp im Gruppenfall,
Nachtrag, Gruppen-Nachtrag, Ende nachtragen). Jetzt prüft er dieselben Wege mit der alten Spalte auf 15 Minuten: der Wert bleibt minutengenau.

    eine Funktion  app/time_tracking.py::gebucht_nach_zeitregel() -- gibt die Stunden unverändert zurück; rounded_hours() gibt es nicht mehr
    alte Buchungen bleiben, wie sie sind (keine Umrechnung, auch keine gerundeten)
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
ROH = Decimal("5.1167")       # 07:00–12:07 = 5 h 7 min, unter 6 h keine Pause; bis 1.9.230 auf 15 Minuten gerundet 5,00


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


def test_gruppen_stopp_rundet_nicht(welt):
    """Bis 1.9.230 test_gruppen_stopp_rundet_je_mitglied (5,00 h je Mitglied)."""
    g = _gruppe(welt)
    antwort = welt["client"].post(f"/api/time-entry-groups/{g.id}/stop", json={"ended_at": _ende(welt), "break_minutes": 0})
    assert antwort.status_code == 200, antwort.text
    assert _stunden(welt) == {welt["mia"].id: ROH, welt["tom"].id: ROH}


def test_stopp_im_gruppenfall_rundet_nicht(welt):
    """Bis 1.9.230 test_stopp_im_gruppenfall_rundet_alle (5,00 h)."""
    g = _gruppe(welt)
    eigene = next(e.id for e in welt["db"].scalars(select(TimeEntry).where(TimeEntry.employee_id == welt["mia"].id)).all())
    antwort = welt["client"].post(f"/api/time-entries/{eigene}/stop", json={"ended_at": _ende(welt), "break_minutes": 0})
    assert antwort.status_code == 200, antwort.text
    assert _stunden(welt) == {welt["mia"].id: ROH, welt["tom"].id: ROH}
    assert welt["db"].get(type(g), g.id).hours == ROH


def test_gruppen_nachtrag_rundet_nicht(welt):
    """Bis 1.9.230 test_gruppen_nachtrag_rundet_je_mitglied (5,1 -> 5,00 h)."""
    antwort = welt["client"].post("/api/time-entry-groups", json={
        "employee_ids": [welt["mia"].id, welt["tom"].id], "team_id": welt["team"].id, "order_id": welt["order"].id,
        "work_date": welt["heute"].isoformat(), "hours": "5.1", "entry_type": "site"})
    assert antwort.status_code == 200, antwort.text
    assert _stunden(welt) == {welt["mia"].id: Decimal("5.1"), welt["tom"].id: Decimal("5.1")}


def test_ende_nachtragen_der_gruppe_rundet_nicht(welt):
    """Bis 1.9.230 test_ende_nachtragen_der_gruppe_rundet_je_mitglied (5,00 h)."""
    gestern = welt["heute"] - timedelta(days=1)
    g = _gruppe(welt, tag=gestern)
    eigene = next(e.id for e in welt["db"].scalars(select(TimeEntry).where(TimeEntry.employee_id == welt["mia"].id)).all())
    antwort = welt["client"].post(f"/api/time-entries/{eigene}/ende-nachtragen", json={"ende": _ende(welt, gestern)})
    assert antwort.status_code == 200, antwort.text
    assert _stunden(welt) == {welt["mia"].id: ROH, welt["tom"].id: ROH}
    assert g.id


def test_einzel_stopp_rundet_nicht(welt):
    """Bis 1.9.230 test_einzel_stopp_rundet_wie_die_gruppe (5,00 h)."""
    row = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    antwort = welt["client"].post(f"/api/time-entries/{row.id}/stop", json={"ended_at": _ende(welt), "break_minutes": 0})
    assert Decimal(antwort.json()["hours"]) == ROH


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


def test_waechter_keine_rundung_je_buchung():
    """Seit 1.9.231: unter app/ ruft niemand rounded_hours() (es gibt sie nicht mehr), und keine Antwort der Zeitregeln nennt eine Rundung. Bis
    1.9.230 test_waechter_eine_rundung: nur gebucht_nach_zeitregel() rief sie."""
    from app import time_backoffice
    assert not hasattr(time_backoffice, "rounded_hours")
    funde = []
    for pfad in sorted((ROOT / "app").rglob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for fn in ast.walk(baum):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for knoten in ast.walk(fn):
                if isinstance(knoten, ast.Call) and getattr(knoten.func, "id", getattr(knoten.func, "attr", None)) == "rounded_hours":
                    funde.append((pfad.relative_to(ROOT).as_posix(), fn.name))
    assert funde == []
