"""Seit 1.9.44 (Stufe 4, R2): „Heute“ für die Monteurin -- der Server (app/heute.py, GET /api/field-view/today Schlüssel "heute").

    Vorschau       GET /api/time-entries/{id}/ende-vorschau rechnet wie die Buchung (ende_rechnen(), eine Funktion für Stopp,
                   Gruppen-Stopp, Ende nachtragen, Zeitart wechseln und Vorschau) -- dieselben Zahlen, nichts gebucht
    Gruppe         der Kolonnenführer, der die Gruppenzeit gestartet hat, bekommt "kolonnenfuehrer" (Knopf „Feierabend für die Gruppe“),
                   jedes Mitglied "stoppt" mit seinem Namen und keinen Knopf
    Einsatz        eine Karte je Auftrag, auch bei zwei Plantafel-Abschnitten; Zeitraum über beide
    Nächste Tage   ab morgen, 14 Tage, heute nie (außer bei offener Zeit von früher: „Heute und nächste Tage“), aufeinander folgende Tage
                   desselben Auftrags in einer Zeile
    Zeitart        POST /api/time-entries/{id}/zeitart-wechseln: die laufende Zeit endet, die neue beginnt im selben Augenblick -- zwei
    wechseln       Buchungen ohne Lücke und ohne Überschneidung; nicht für eine Gruppenzeit, eine Zeit von früher, eine fremde Zeit
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import berlin_time
from app.models import PlanningSlot, TeamEmployee, TimeEntry, WorkPreparation, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee
from app.routers import field_view as field_view_router
from app.routers import time_tracking as time_tracking_router
from app.time_tracking import start_group_timer, start_timer
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    heute = berlin_time.berlin_today()
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0471a"))
    order.title = "Wartung"
    team = make_team(db, "K-1", "Kolonne 1")
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    tom = make_employee(db, "M-2", "Tom", "Monteur")
    for emp, fuehrt in ((mia, True), (tom, False)):
        db.add(TeamEmployee(team_id=team.id, employee_id=emp.id, is_crew_leader=fuehrt))
    db.commit()
    return {"db": db, "heute": heute, "gestern": heute - timedelta(days=1), "order": order, "team": team, "mia": mia, "tom": tom,
            "client": router_test_client}


def _als(w, emp):
    return w["client"](w["db"], time_tracking_router.router, field_view_router.router, role="field", employee_id=emp.id)


def _einsatz(w, order, abschnitte, leute):
    """Ein Plantafel-Einsatz am Auftrag (eine Arbeitsvorbereitung je Auftrag) mit einem oder mehreren Abschnitten (von, bis)."""
    db = w["db"]
    prep = WorkPreparation(order_id=order.id, status="offen")
    db.add(prep); db.flush()
    zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=w["team"].id, team_name_snapshot=w["team"].name)
    db.add(zuordnung); db.flush()
    for emp in leute:
        db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=emp.id, employee_name_snapshot=emp.first_name))
    for von, bis in abschnitte:
        db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=von, end_date=bis))
    db.commit()


def _zweiter_auftrag(w):
    order = beauftragen(w["db"], make_quote(w["db"], is_consumer=False, number="0471b"))
    order.title = "Rinne erneuern"
    w["db"].commit()
    return order


def _heute(w, emp):
    antwort = _als(w, emp).get("/api/field-view/today")
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["heute"]


# --- Vorschau = Buchung ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ende, pause", [("16:00", 0), ("12:30", 0), ("16:00", 60)], ids=["9h15", "5h45", "mindestpause_60"])
def test_vorschau_und_buchung_dieselben_zahlen(welt, ende, pause):
    _einsatz(welt, welt["order"], [(welt["gestern"], welt["heute"])], [welt["mia"]])
    row = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(6, 45)))
    client = _als(welt, welt["mia"])
    vorschau = client.get(f"/api/time-entries/{row.id}/ende-vorschau",
                          params={"ende": f"{welt['gestern'].isoformat()}T{ende}", "pause_minuten": pause})
    assert vorschau.status_code == 200, vorschau.text
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, row.id).status == "running"  # die Vorschau bucht nichts
    gebucht = client.post(f"/api/time-entries/{row.id}/ende-nachtragen",
                          json={"ende": f"{welt['gestern'].isoformat()}T{ende}", "pause_minuten": pause}).json()
    v = vorschau.json()
    assert (Decimal(v["anwesend"]), v["pause"], Decimal(v["gebucht"])) == (
        Decimal(gebucht["anwesend"]), gebucht["pause"], Decimal(gebucht["hours"]))
    if ende == "16:00" and pause == 0:
        assert (Decimal(v["anwesend"]), v["pause"]) == (Decimal("9.25"), 45)  # Zeitregel der Grunddaten: ab 9 h 45 Minuten


def test_vorschau_gruppenzeit_wie_gruppen_stopp(welt):
    """Der Kolonnenführer trägt das Ende der Gruppenzeit nach: seine Vorschau = seine gebuchte Zeile."""
    _einsatz(welt, welt["order"], [(welt["gestern"], welt["heute"])], [welt["mia"], welt["tom"]])
    gruppe = start_group_timer(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id,
                               actor_employee_id=welt["mia"].id, is_admin=False, order_id=welt["order"].id,
                               started_at=datetime.combine(welt["gestern"], time(7)))
    eigene = welt["db"].scalar(select(TimeEntry).where(TimeEntry.employee_id == welt["mia"].id, TimeEntry.status == "running"))
    client = _als(welt, welt["mia"])
    v = client.get(f"/api/time-entries/{eigene.id}/ende-vorschau", params={"ende": f"{welt['gestern'].isoformat()}T15:30"}).json()
    gebucht = client.post(f"/api/time-entries/{eigene.id}/ende-nachtragen", json={"ende": f"{welt['gestern'].isoformat()}T15:30"}).json()
    assert (Decimal(v["anwesend"]), v["pause"], Decimal(v["gebucht"])) == (Decimal(gebucht["anwesend"]), gebucht["pause"], Decimal(gebucht["hours"]))
    assert gruppe.id


def test_vorschau_rechte_wie_nachtragen(welt):
    """Angriff: Vorschau einer fremden Zeit 403, einer heute gestarteten 409, Ende am falschen Tag 422 -- wie beim Nachtragen."""
    _einsatz(welt, welt["order"], [(welt["gestern"], welt["heute"])], [welt["mia"], welt["tom"]])
    toms = start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(7)))
    client = _als(welt, welt["mia"])
    assert client.get(f"/api/time-entries/{toms.id}/ende-vorschau", params={"ende": f"{welt['gestern'].isoformat()}T15:00"}).status_code == 403
    eigene = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    assert client.get(f"/api/time-entries/{eigene.id}/ende-vorschau", params={"ende": f"{welt['heute'].isoformat()}T09:00"}).status_code == 409


# --- Arbeitszeit: läuft, Gruppe, nichts, früher ----------------------------------------------------------------------------------------

def test_laeuft_mit_dauer_und_objekt(welt):
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"])], [welt["mia"]])
    start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(6, 45)))
    z = _heute(welt, welt["mia"])["arbeitszeit"]
    assert (z["zustand"], z["beginn"], z["zeitart_label"], z["order_number"], z["gruppe"]) == (
        "laeuft", "06:45", "Baustellenzeit", welt["order"].order_number, None)
    assert z["dauer_minuten"] == 195  # feste Uhr 10:00


def test_gruppenmitglied_ohne_knopf_kolonnenfuehrer_mit(welt):
    """Angriff/Gegenprobe: Tom (Mitglied) bekommt "stoppt Mia" und keinen Knopf, Mia (Kolonnenführerin, hat gestartet) den Knopf."""
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"])], [welt["mia"], welt["tom"]])
    gruppe = start_group_timer(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id,
                               actor_employee_id=welt["mia"].id, is_admin=False, order_id=welt["order"].id,
                               started_at=datetime.combine(welt["heute"], time(7)))
    tom = _heute(welt, welt["tom"])["arbeitszeit"]["gruppe"]
    mia = _heute(welt, welt["mia"])["arbeitszeit"]["gruppe"]
    assert tom == {"id": gruppe.id, "kolonnenfuehrer": False, "stoppt": "Mia Monteurin"}
    assert mia == {"id": gruppe.id, "kolonnenfuehrer": True, "stoppt": None}
    # der Knopf wäre für Tom ohnehin wirkungslos: die Gruppe stoppt nur, wer sie gestartet hat
    assert _als(welt, welt["tom"]).post(f"/api/time-entry-groups/{gruppe.id}/stop", json={"break_minutes": 0}).status_code == 403


def test_kolonnenfuehrer_ohne_kennzeichen_wird_mitglied(welt):
    """Gegenprobe zur Regel von 1.8.144: hat Mia das Kennzeichen nicht mehr, stoppt auch sie die Gruppe nicht -- kein Knopf."""
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"])], [welt["mia"], welt["tom"]])
    start_group_timer(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id,
                      actor_employee_id=welt["mia"].id, is_admin=False, order_id=welt["order"].id,
                      started_at=datetime.combine(welt["heute"], time(7)))
    for te in welt["db"].scalars(select(TeamEmployee).where(TeamEmployee.employee_id == welt["mia"].id)):
        te.is_crew_leader = False
    welt["db"].commit()
    assert _heute(welt, welt["mia"])["arbeitszeit"]["gruppe"]["kolonnenfuehrer"] is False


def test_nichts_laeuft_auftrag_vorbelegt_bei_genau_einem(welt):
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"])], [welt["mia"]])
    z = _heute(welt, welt["mia"])["arbeitszeit"]
    assert (z["zustand"], z["vorbelegt"]) == ("nichts", welt["order"].id)
    assert welt["order"].id in {a["id"] for a in z["auftraege"]}
    zweiter = _zweiter_auftrag(welt)
    _einsatz(welt, zweiter, [(welt["heute"], welt["heute"])], [welt["mia"]])
    assert _heute(welt, welt["mia"])["arbeitszeit"]["vorbelegt"] is None  # zwei Aufträge heute: nichts vorbelegt


def test_frueher_offen_mit_monat_abgeschlossen(welt):
    from app.time_backoffice import set_time_lock
    _einsatz(welt, welt["order"], [(welt["gestern"], welt["heute"])], [welt["mia"]])
    start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(6, 45)))
    z = _heute(welt, welt["mia"])["arbeitszeit"]
    assert (z["zustand"], z["gestern"], z["beginn"], z["monat_abgeschlossen"], z["nachtragen_durch"]) == ("frueher", True, "06:45", False, None)
    set_time_lock(welt["db"], welt["gestern"], user_id=None)
    assert _heute(welt, welt["mia"])["arbeitszeit"]["monat_abgeschlossen"] is True


def test_frueher_offen_gruppenmitglied_traegt_nicht_nach(welt):
    _einsatz(welt, welt["order"], [(welt["gestern"], welt["heute"])], [welt["mia"], welt["tom"]])
    start_group_timer(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id,
                      actor_employee_id=welt["mia"].id, is_admin=False, order_id=welt["order"].id,
                      started_at=datetime.combine(welt["gestern"], time(7)))
    assert _heute(welt, welt["tom"])["arbeitszeit"]["nachtragen_durch"] == "Mia Monteurin"
    assert _heute(welt, welt["mia"])["arbeitszeit"]["nachtragen_durch"] is None


# --- Einsatz je Auftrag, Nächste Tage --------------------------------------------------------------------------------------------------

def test_zwei_zeitfenster_am_selben_auftrag_eine_karte(welt):
    h = welt["heute"]
    _einsatz(welt, welt["order"], [(h - timedelta(days=1), h + timedelta(days=1)), (h, h + timedelta(days=2))], [welt["mia"]])
    karten = _heute(welt, welt["mia"])["einsaetze"]
    assert [(k["order_id"], k["von"], k["bis"]) for k in karten] == [
        (welt["order"].id, (h - timedelta(days=1)).isoformat(), (h + timedelta(days=2)).isoformat())]


def test_heute_nicht_in_naechste_tage_morgen_drin(welt):
    h = welt["heute"]
    zweiter = _zweiter_auftrag(welt)
    _einsatz(welt, welt["order"], [(h, h + timedelta(days=2))], [welt["mia"]])
    _einsatz(welt, zweiter, [(h + timedelta(days=5), h + timedelta(days=6)), (h + timedelta(days=15), h + timedelta(days=16))], [welt["mia"]])
    zeilen = _heute(welt, welt["mia"])["naechste_tage"]
    assert [(z["order_id"], z["von"], z["bis"], z["nebentext"]) for z in zeilen] == [
        (welt["order"].id, (h + timedelta(days=1)).isoformat(), (h + timedelta(days=2)).isoformat(), "Fortsetzung"),
        (zweiter.id, (h + timedelta(days=5)).isoformat(), (h + timedelta(days=6)).isoformat(), "Rinne erneuern"),
    ]  # heute nie, ab morgen in einer Zeile, nach 14 Tagen nichts mehr


def test_offene_zeit_von_frueher_zeigt_heute_als_eigene_zeile(welt):
    """Vorlage „Heute und nächste Tage“: bei offener Zeit von gestern steht heute vorn, die folgenden Tage desselben Auftrags danach."""
    h = welt["heute"]
    _einsatz(welt, welt["order"], [(welt["gestern"], h + timedelta(days=2))], [welt["mia"]])
    start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(7)))
    zeilen = _heute(welt, welt["mia"])["naechste_tage"]
    assert [(z["von"], z["bis"], z["nebentext"]) for z in zeilen] == [
        (h.isoformat(), h.isoformat(), "Wartung"),
        ((h + timedelta(days=1)).isoformat(), (h + timedelta(days=2)).isoformat(), "Fortsetzung")]


# --- Zeitart wechseln ------------------------------------------------------------------------------------------------------------------

def test_zeitart_wechseln_ohne_luecke_und_ueberschneidung(welt):
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"])], [welt["mia"]])
    alt = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, entry_type="travel",
                      started_at=datetime.combine(welt["heute"], time(6, 15)))
    antwort = _als(welt, welt["mia"]).post(f"/api/time-entries/{alt.id}/zeitart-wechseln", json={"entry_type": "site"})
    assert antwort.status_code == 200, antwort.text
    welt["db"].expire_all()
    zeilen = welt["db"].scalars(select(TimeEntry).where(TimeEntry.employee_id == welt["mia"].id).order_by(TimeEntry.started_at)).all()
    assert [(z.entry_type, z.status, z.order_id) for z in zeilen] == [("travel", "booked", welt["order"].id), ("site", "running", welt["order"].id)]
    assert zeilen[0].ended_at == zeilen[1].started_at == datetime.combine(welt["heute"], time(10))  # feste Uhr: keine Lücke, keine Überschneidung
    assert zeilen[0].hours == Decimal("3.75") and zeilen[0].break_minutes == 0
    assert antwort.json()["id"] == zeilen[1].id


def test_zeitart_wechseln_abgelehnt(welt):
    """Angriff: Gruppenzeit 409, Zeit von gestern 409, fremde Zeit 403, dieselbe Zeitart 422, unbekannte 422 -- nichts geändert."""
    _einsatz(welt, welt["order"], [(welt["gestern"], welt["heute"])], [welt["mia"], welt["tom"]])
    gestern = start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(7)))
    assert _als(welt, welt["tom"]).post(f"/api/time-entries/{gestern.id}/zeitart-wechseln", json={"entry_type": "travel"}).status_code == 409
    assert _als(welt, welt["mia"]).post(f"/api/time-entries/{gestern.id}/zeitart-wechseln", json={"entry_type": "travel"}).status_code == 403
    eigene = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    client = _als(welt, welt["mia"])
    assert client.post(f"/api/time-entries/{eigene.id}/zeitart-wechseln", json={"entry_type": "site"}).status_code == 422
    assert client.post(f"/api/time-entries/{eigene.id}/zeitart-wechseln", json={"entry_type": "urlaub"}).status_code == 422
    welt["db"].expire_all()
    assert welt["db"].scalar(select(TimeEntry.status).where(TimeEntry.id == eigene.id)) == "running"
    assert welt["db"].scalar(select(TimeEntry.status).where(TimeEntry.id == gestern.id)) == "running"


def test_zeitart_wechseln_nicht_in_der_gruppe(welt):
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"])], [welt["mia"], welt["tom"]])
    start_group_timer(welt["db"], employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id,
                      actor_employee_id=welt["mia"].id, is_admin=False, order_id=welt["order"].id,
                      started_at=datetime.combine(welt["heute"], time(7)))
    eigene = welt["db"].scalar(select(TimeEntry).where(TimeEntry.employee_id == welt["mia"].id, TimeEntry.status == "running"))
    antwort = _als(welt, welt["mia"]).post(f"/api/time-entries/{eigene.id}/zeitart-wechseln", json={"entry_type": "travel"})
    assert antwort.status_code == 409 and "Gruppenzeit" in antwort.json()["detail"]
