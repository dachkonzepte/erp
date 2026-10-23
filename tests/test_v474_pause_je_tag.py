"""Seit 1.9.48 (Stufe 4, R2 Nachrunde, Punkt 1, Entscheidung Tobias): die Pausenregel je Tag, nur für neue Buchungen.

    Schwelle       „mehr als“: über 6:00 h Anwesenheit 30 min, über 9:00 h 45 min (Werte aus den Grunddaten, bis 1.9.46 „ab“)
    Tag            maßgeblich ist die Anwesenheit der Person am Starttag über alle gebuchten Zeiten samt der neuen (eine reine Dauer zählt mit
                   Stunden + Pause); die neue Buchung bekommt, was dem Tag an Pflichtpause noch fehlt (Pflichtpause − schon abgezogene
                   Pausen), mindestens die eingegebene Pause, höchstens ihre Anwesenheit; frühere Buchungen nie angefasst
    überall        Stopp, Gruppen-Stopp (je Mitglied), Ende nachtragen, Nachtrag mit Von/Bis, Zeitart wechseln, Vorschau -- eine Funktion
                   (pause_nach_zeitregel() über ende_rechnen())
    Tag zusammen   Antwort und Vorschau nennen die gebuchten Stunden des Tages und die Zahl seiner Buchungen
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import berlin_time
from app.models import TeamEmployee, TimeEntry
from app.routers import field_view as field_view_router
from app.routers import time_tracking as time_tracking_router
from app.time_tracking import (
    create_manual_entry, ende_vorschau, start_group_timer, start_timer, stop_group_timer, stop_timer, zeitart_wechseln,
)
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    heute = berlin_time.berlin_today()
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0474"))
    team = make_team(db, "K-1", "Kolonne 1")
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    db.add_all([TeamEmployee(team_id=team.id, employee_id=mia.id, is_crew_leader=True), TeamEmployee(team_id=team.id, employee_id=tom.id)])
    db.commit()
    return {"db": db, "heute": heute, "tag": heute - timedelta(days=1), "order": order, "team": team, "mia": mia, "tom": tom,
            "client": router_test_client}


def _um(w, hh, mm=0):
    return datetime.combine(w["tag"], time(hh, mm))


def _zeit(w, emp, von, bis, pause=0, art="site"):
    """Eine Zeit mit Beginn und Ende am Tag (Timer gestartet und gestoppt)."""
    row = start_timer(w["db"], employee_id=emp.id, order_id=w["order"].id, entry_type=art, started_at=von)
    return stop_timer(w["db"], row.id, ended_at=bis, break_minutes=pause)


def _als(w, emp, rolle="field"):
    w["db"].commit()
    return w["client"](w["db"], time_tracking_router.router, field_view_router.router, role=rolle, employee_id=emp.id)


# --- Schwelle „mehr als“ ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bis, pause", [((13, 0), 0), ((13, 1), 30), ((16, 0), 30), ((16, 1), 45)],
                         ids=["genau_6h_0", "6h01_30", "genau_9h_30", "9h01_45"])
def test_schwelle_mehr_als(welt, bis, pause):
    row = _zeit(welt, welt["mia"], _um(welt, 7), _um(welt, *bis))
    assert row.break_minutes == pause


# --- je Tag statt je Buchung ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bis, pause_2, tag, je_buchung", [
    ((16, 0), 30, Decimal("8.5"), Decimal("9.0")),     # genau 9:00 h am Tag -> 30 min (das Beispiel der Vorgabe nennt 45 und 8,25 h)
    ((16, 15), 45, Decimal("8.5"), Decimal("9.25")),   # 9:15 h am Tag -> 45 min
], ids=["bis_16_00", "bis_16_15"])
def test_zeitart_wechseln_mittags_pause_bei_der_zweiten(welt, bis, pause_2, tag, je_buchung):
    """Baustelle 07:00–12:00, Wechsel, Werkstatt bis 16:00 (16:15): die erste Buchung bleibt ohne Pause (5 h), die zweite bekommt, was dem
    Tag fehlt -- je Buchung wären beide ohne Pause gewesen."""
    db, h = welt["db"], welt["heute"]  # heute: eine Zeit von gestern wechselt die Zeitart nicht (409)
    row = start_timer(db, employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(h, time(7)))
    neu = zeitart_wechseln(db, row.id, "workshop", jetzt=datetime.combine(h, time(12)))
    zweite = stop_timer(db, neu.id, ended_at=datetime.combine(h, time(*bis)))
    db.expire_all()
    erste = db.get(TimeEntry, row.id)
    assert (erste.break_minutes, erste.hours, zweite.break_minutes) == (0, Decimal("5.0000"), pause_2)
    assert erste.hours + zweite.hours == tag
    assert erste.hours + zweite.hours + Decimal(pause_2) / 60 == je_buchung  # je Buchung: keine Pause, alles gebucht


def test_zwei_buchungen_je_fuenf_stunden(welt):
    """Der Befund aus R2: zwei Buchungen à 5 h am selben Tag -- bis 1.9.46 ohne Pause (10,00 h), jetzt 45 min bei der zweiten."""
    erste = _zeit(welt, welt["mia"], _um(welt, 6), _um(welt, 11))
    zweite = _zeit(welt, welt["mia"], _um(welt, 11), _um(welt, 16))
    assert (erste.break_minutes, zweite.break_minutes, erste.hours + zweite.hours) == (0, 45, Decimal("9.2500"))


def test_nachtrag_vormittag_nach_der_nachmittagsbuchung(welt):
    """Der Nachmittag 12:30–16:00 ist gebucht (3:30 h, keine Pause); der Vormittag 07:00–12:00 kommt als Nachtrag mit Von/Bis: der Tag hat
    8:30 h, ihm fehlen 30 min -- sie gehen beim Nachtrag ab, die Nachmittagsbuchung bleibt, wie sie ist."""
    nachmittag = _zeit(welt, welt["mia"], _um(welt, 12, 30), _um(welt, 16))
    vorher = (nachmittag.break_minutes, nachmittag.hours, nachmittag.ended_at)
    antwort = _als(welt, welt["mia"], "admin").post("/api/time-entries", json={  # der Test-Auftrag ist niemandem zugeordnet
        "employee_id": welt["mia"].id, "order_id": welt["order"].id, "work_date": welt["tag"].isoformat(), "von": "07:00", "bis": "12:00"})
    assert antwort.status_code == 200, antwort.text
    d = antwort.json()
    assert (d["pause"], Decimal(d["gebucht"]), Decimal(d["tag_zusammen"]), d["tag_buchungen"]) == (30, Decimal("4.5"), Decimal("8"), 2)
    welt["db"].expire_all()
    n = welt["db"].get(TimeEntry, nachmittag.id)
    assert (n.break_minutes, n.hours, n.ended_at) == vorher


def test_eingegebene_pause_bleibt_mindestpause(welt):
    row = _zeit(welt, welt["mia"], _um(welt, 7), _um(welt, 16), pause=60)
    assert (row.break_minutes, row.hours) == (60, Decimal("8.0000"))


def test_dauer_buchung_zaehlt_mit_stunden_und_pause(welt):
    """Eine reine Dauer (4 h gebucht, 15 min Pause) zählt mit 4:15 h Anwesenheit und 15 min schon abgezogen."""
    create_manual_entry(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, work_date=welt["tag"], hours=Decimal("4"),
                        break_minutes=15)
    row = _zeit(welt, welt["mia"], _um(welt, 12), _um(welt, 14))  # Tag 6:15 h -> 30 min, 15 schon ab -> 15 min
    assert row.break_minutes == 15


def test_gruppenmitglied_mit_eigener_frueherer_buchung(welt):
    """Tom hat am Tag schon 06:00–07:00 gebucht; die Gruppenzeit 07:00–12:30 (5:30 h) gibt Mia keine Pause (Tag 5:30 h), Tom 30 min (Tag
    6:30 h) -- je Mitglied seine eigene Tagesrechnung."""
    db = welt["db"]
    _zeit(welt, welt["tom"], _um(welt, 6), _um(welt, 7))
    gruppe = start_group_timer(db, employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id, actor_employee_id=welt["mia"].id,
                               is_admin=False, order_id=welt["order"].id, started_at=_um(welt, 7))
    stop_group_timer(db, gruppe.id, ended_at=_um(welt, 12, 30))
    pausen = {r.employee_id: r.break_minutes for r in db.scalars(select(TimeEntry).where(TimeEntry.source == "group_timer"))}
    assert pausen == {welt["mia"].id: 0, welt["tom"].id: 30}


def test_fruehere_buchungen_bleiben_unveraendert(welt):
    """Keine Umrechnung: eine Buchung nach der alten Regel (je Buchung, 9:00 h -> 45 min) bleibt, die neue rechnet nur, was fehlt."""
    db = welt["db"]
    alt = create_manual_entry(db, employee_id=welt["mia"].id, order_id=welt["order"].id, work_date=welt["tag"], hours=Decimal("8.25"),
                              break_minutes=45, started_at=_um(welt, 6), ended_at=_um(welt, 15))
    vorher = (alt.hours, alt.break_minutes)
    neu = _zeit(welt, welt["mia"], _um(welt, 15), _um(welt, 16))  # Tag 10 h -> 45 min, 45 schon ab -> 0
    db.expire_all()
    assert (db.get(TimeEntry, alt.id).hours, db.get(TimeEntry, alt.id).break_minutes) == vorher and neu.break_minutes == 0


def test_fehlende_pause_zehrt_die_letzte_buchung_auf(welt):
    """07:00–13:00 (genau 6 h, keine Pause), dann 13:00–13:20: der Tag hat 6:20 h, ihm fehlen 30 min -- höchstens die 20 min der
    Buchung; der Stopp schließt sie mit 0 h, ein Nachtrag mit Von/Bis wird abgelehnt (keine Arbeitszeit übrig)."""
    _zeit(welt, welt["mia"], _um(welt, 7), _um(welt, 13))
    kurz = _zeit(welt, welt["mia"], _um(welt, 13), _um(welt, 13, 20))
    assert (kurz.break_minutes, kurz.hours) == (20, Decimal("0"))
    _zeit(welt, welt["tom"], _um(welt, 7), _um(welt, 13))
    antwort = _als(welt, welt["tom"], "admin").post("/api/time-entries", json={
        "employee_id": welt["tom"].id, "order_id": welt["order"].id, "work_date": welt["tag"].isoformat(), "von": "13:00", "bis": "13:20"})
    assert (antwort.status_code, antwort.json()["detail"]) == (422, "Nach Abzug der Pause bleibt keine Arbeitszeit.")


# --- Vorschau = Buchung, Tag zusammen --------------------------------------------------------------------------------------------

def test_vorschau_gleich_buchung_mit_frueherer_buchung_am_tag(welt):
    """Gestern Fahrzeit 06:00–06:45 gebucht, dann Baustelle seit 06:45 offen: Ende 16:00 -> Tag 10 h, 45 min fehlen -- Vorschau und
    „Ende nachtragen“ liefern dieselben Zahlen samt „Tag zusammen“."""
    _zeit(welt, welt["mia"], _um(welt, 6), _um(welt, 6, 45), art="travel")
    offen = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=_um(welt, 6, 45))
    client = _als(welt, welt["mia"])
    v = client.get(f"/api/time-entries/{offen.id}/ende-vorschau", params={"ende": f"{welt['tag'].isoformat()}T16:00"}).json()
    b = client.post(f"/api/time-entries/{offen.id}/ende-nachtragen", json={"ende": f"{welt['tag'].isoformat()}T16:00"}).json()
    assert (v["pause"], Decimal(v["gebucht"]), Decimal(v["tag_zusammen"]), v["tag_buchungen"]) == (45, Decimal("8.5"), Decimal("9.25"), 2)
    assert (b["pause"], Decimal(b["hours"]), Decimal(b["tag_zusammen"]), b["tag_buchungen"]) == (45, Decimal("8.5"), Decimal("9.25"), 2)


def test_vorschau_rechnet_wie_die_funktion(welt):
    offen = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=_um(welt, 7))
    v = ende_vorschau(welt["db"], offen.id, ende=_um(welt, 16, 1))
    assert (v["pause"], v["tag_buchungen"]) == (45, 1)


def test_feierabend_nennt_tag_zusammen(welt):
    """Stopp über die Schnittstelle heute: zweite Buchung des Tages -> „Tag zusammen“ mit beiden."""
    heute = welt["heute"]
    _zeit(welt, welt["mia"], datetime.combine(heute, time(6)), datetime.combine(heute, time(7)))
    laeuft = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(heute, time(7)))
    d = _als(welt, welt["mia"]).post(f"/api/time-entries/{laeuft.id}/stop", json={"break_minutes": 0}).json()
    assert (Decimal(d["tag_zusammen"]), d["tag_buchungen"]) == (Decimal("1") + Decimal(d["hours"]), 2)  # feste Uhr 10:00
