"""Seit 1.9.34 (Stufe 4, R1, Punkt 3): Nachtragen nach derselben Pausenregel wie der Feierabend.

    eine Regel     app/time_tracking.py::pause_nach_zeitregel() -- die automatische Pause des Arbeitszeitmodells nach der Anwesenheit
                   (Vorgabe ab 6 h 30 min, ab 9 h 45 min), mindestens die eingegebene Pause; Stopp, Gruppen-Stopp und Nachtrag mit Von/Bis
                   nehmen sie, keine zweite Rechnung (Wächter über app/)
    Nachtrag       mit Von/Bis zieht der Server die Pause ab (bis 1.9.33 speicherte er sie nur); eine reine Dauer ist gebuchte Arbeitszeit
                   (netto) wie bisher und wie „Stunden (netto)“ im Büro
    Antwort        anwesend (Stunden vor der Pause), Pause (Minuten), gebucht (Stunden)
    Mindestpause   „Zusätzliche Pause“ bleibt Mindestpause: max(eingegeben, Regel), keine Summe
"""

import ast
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.routers import time_tracking as time_tracking_router
from app.time_tracking import start_timer, stop_timer
from tests.test_v133_invoices import make_order_with_item
from tests.test_v224_field_view import make_employee, make_slot_for_individual, make_team

ROOT = Path(__file__).resolve().parents[1]
TAG = date(2026, 10, 14)


@pytest.fixture
def monteurin(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    emp = make_employee(db, "M-1", "Mia", "Monteurin")
    make_slot_for_individual(db, order, make_team(db, "K-1", "Kolonne 1"), emp, TAG - timedelta(days=7), TAG + timedelta(days=7))
    client = router_test_client(db, time_tracking_router.router, role="field", employee_id=emp.id)
    return db, client, order, emp


def _nachtrag(client, order, emp, **werte):
    return client.post("/api/time-entries", json={"employee_id": emp.id, "order_id": order.id, "work_date": TAG.isoformat(), **werte})


def test_nachtrag_von_bis_zieht_die_pause_nach_der_zeitregel_ab(monkeypatch, monteurin):
    """Angriff auf die alte Rechnung: 06:45–16:00 sind 9,25 h anwesend -- ab 9 h 45 min Pause, gebucht 8,50 h (bis 1.9.33: 9,25 h)."""
    db, client, order, emp = monteurin
    antwort = _nachtrag(client, order, emp, von="06:45", bis="16:00")
    assert antwort.status_code == 200, antwort.text
    d = antwort.json()
    assert (Decimal(d["anwesend"]), d["pause"], Decimal(d["gebucht"])) == (Decimal("9.25"), 45, Decimal("8.5"))
    assert (d["started_at"], d["ended_at"]) == ("2026-10-14T06:45:00", "2026-10-14T16:00:00")
    assert d["hours"] == d["gebucht"] and d["break_minutes"] == d["pause"]


@pytest.mark.parametrize("werte", [{"hours": "4"}, {"von": "07:00", "bis": "11:00"}], ids=["dauer", "von_bis"])
def test_nachtrag_4_stunden_ohne_abzug(monteurin, router_test_client, werte):
    """Gegenprobe: 4 h -- als Dauer wie als Von/Bis unter der ersten Schwelle, kein Abzug. Seit 1.9.60 bucht die Dauer das Büro (die
    Monteurin nur mit Von und Bis, tests/test_v485_nur_von_bis.py)."""
    db, client, order, emp = monteurin
    if "hours" in werte:  # seit 1.9.89 Büro – Finanzen (Büro – Auftrag liest nur)
        client = router_test_client(db, time_tracking_router.router, role="buero_finanzen", employee_id=emp.id)
    d = _nachtrag(client, order, emp, **werte).json()
    assert (Decimal(d["anwesend"]), d["pause"], Decimal(d["gebucht"])) == (Decimal("4"), 0, Decimal("4"))


def test_eine_dauer_bleibt_gebuchte_arbeitszeit(monteurin, router_test_client):
    """9 h als Dauer sind gebuchte Arbeitszeit (netto) -- die Regel greift nur, wo die Anwesenheit eingegeben wird. Seit 1.9.60 als Büro
    (eine reine Dauer trägt nur das Büro ein), seit 1.9.89 als Büro – Finanzen (Büro – Auftrag liest nur)."""
    db, _, order, emp = monteurin
    client = router_test_client(db, time_tracking_router.router, role="buero_finanzen", employee_id=emp.id)
    d = _nachtrag(client, order, emp, hours="9").json()
    assert (Decimal(d["gebucht"]), d["pause"], Decimal(d["anwesend"])) == (Decimal("9"), 0, Decimal("9"))


@pytest.mark.parametrize("eingegeben, pause", [(20, 45), (60, 60)])
def test_zusaetzliche_pause_bleibt_mindestpause(monteurin, eingegeben, pause):
    db, client, order, emp = monteurin
    d = _nachtrag(client, order, emp, von="06:45", bis="16:00", break_minutes=eingegeben).json()
    assert d["pause"] == pause
    assert Decimal(d["gebucht"]) == Decimal("9.25") - Decimal(pause) / Decimal(60)


@pytest.mark.parametrize("werte, text", [({"von": "07:00"}, "Von und Bis"), ({"von": "16:00", "bis": "07:00"}, "Bis muss nach Von"),
                                         ({}, "Dauer oder Von und Bis")])
def test_unvollstaendiger_nachtrag_422(monteurin, werte, text):
    db, client, order, emp = monteurin
    antwort = _nachtrag(client, order, emp, **werte)
    assert antwort.status_code == 422 and text in antwort.text


def test_feierabend_bucht_nach_derselben_regel(monteurin):
    """Der Stopp eines Timers 06:45–16:00 ergibt dieselben Werte wie der Nachtrag."""
    db, client, order, emp = monteurin
    row = start_timer(db, employee_id=emp.id, order_id=order.id, started_at=datetime(2026, 10, 14, 6, 45))
    row = stop_timer(db, row.id, ended_at=datetime(2026, 10, 14, 16, 0))
    assert (row.break_minutes, row.hours) == (45, Decimal("8.5"))


def _aufrufe(baum, name):
    return [k for k in ast.walk(baum) if isinstance(k, ast.Call) and getattr(k.func, "id", getattr(k.func, "attr", None)) == name]


def test_eine_pausenregel_keine_zweite_rechnung():
    """Wächter: die automatische Pause des Arbeitszeitmodells ruft unter app/ nur pause_nach_zeitregel() auf -- Stopp, Gruppen-Stopp und
    Nachtrag nehmen diese eine Funktion (bis 1.9.33 rechneten Router und Stopp je für sich)."""
    funde = []
    for pfad in sorted((ROOT / "app").rglob("*.py")):
        if pfad.name == "work_time_models.py":
            continue
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for funktion in [k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)]:
            for name in ("automatic_break_minutes_for_duration", "automatic_break_minutes_for_timer"):
                if _aufrufe(funktion, name) and funktion.name != "pause_nach_zeitregel":
                    funde.append(f"{pfad.relative_to(ROOT).as_posix()}::{funktion.name} ruft {name}")
    assert funde == []
    quelle = ast.parse((ROOT / "app" / "time_tracking.py").read_text(encoding="utf-8"))
    nutzer = {f.name for f in ast.walk(quelle) if isinstance(f, ast.FunctionDef) and _aufrufe(f, "pause_nach_zeitregel")}
    assert {"ende_rechnen", "nachtrag_nach_zeitregel"} <= nutzer
    # seit 1.9.44 rechnen Stopp, Gruppen-Stopp, die Vorschau von „Ende nachtragen“ und „Zeitart wechseln“ über ende_rechnen()
    rechnen = {f.name for f in ast.walk(quelle) if isinstance(f, ast.FunctionDef) and _aufrufe(f, "ende_rechnen")}
    assert {"stop_timer", "stop_group_timer", "ende_vorschau", "zeitart_wechseln"} <= rechnen
