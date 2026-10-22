"""Seit 1.9.35 (Stufe 4, R1, Punkt 2): vergessener Feierabend -- nichts geschieht von selbst, das Ende wird auf Klick nachgetragen.

    offene Zeit    eine laufende Zeit, die an einem früheren Tag (Berlin) begann: GET /api/field-view/today nennt sie (Start mit Datum,
                   Zeitart, Auftrag), die Zeit trägt laeuft_seit_frueher
    Stopp          der normale Stopp (einzeln wie Gruppe) lehnt sie ab (409) und verweist auf „Ende nachtragen“ -- bis 1.9.34 buchte er sie bis
                   jetzt auf den Starttag; eine heute gestartete Zeit stoppt wie bisher
    Ende nachtragen POST /api/time-entries/{id}/ende-nachtragen: Ende am Starttag und nach dem Start, Pause nach derselben Zeitregel wie
                   beim Feierabend (pause_nach_zeitregel()); eine schon geschlossene Zeit 409
    Start          solange sie offen ist, kein neuer Start (409 mit Meldung, kein 500)
    Rechte         die eigene Zeit, eine fremde nur nach darf_zeit_fuer_andere_buchen() (heute Admin; wer, steht im Verlauf); eine laufende
                   Gruppenzeit nur der Kolonnenführer, der sie gestartet hat (für die ganze Gruppe), oder ein Admin
    Abschluss      Monat des Starttags abgeschlossen: die Monteurin nicht („Monat abgeschlossen – das Büro schließt die Zeit.“), für das
                   Büro unverändert (_require_open_period(): nur ein Admin)
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app import berlin_time
from app.audit import reset_audit_context, set_audit_context
from app.models import AuditLog, TeamEmployee, TimeEntry, WorkPreparationEmployee
from app.routers import field_view as field_view_router
from app.routers import time_tracking as time_tracking_router
from app.time_backoffice import set_time_lock
from app.time_tracking import laeuft_seit_frueher, start_group_timer, start_timer
from tests.test_v133_invoices import make_order_with_item
from tests.test_v224_field_view import make_employee, make_slot_for_individual, make_team


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    heute = berlin_time.berlin_today()
    order, _ = make_order_with_item(db)
    team = make_team(db, "K-1", "Kolonne 1")
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    tom = make_employee(db, "M-2", "Tom", "Monteur")
    _, prep = make_slot_for_individual(db, order, team, mia, heute - timedelta(days=7), heute + timedelta(days=7))
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=tom.id))
    db.commit()
    return {"db": db, "heute": heute, "gestern": heute - timedelta(days=1), "order": order, "team": team, "mia": mia, "tom": tom,
            "client": router_test_client}


def _als(w, emp=None, rolle="field", **mehr):
    return w["client"](w["db"], time_tracking_router.router, field_view_router.router, role=rolle,
                       employee_id=emp.id if emp is not None else None, **mehr)


def _gestern_gestartet(w, emp, um=time(6, 45)):
    return start_timer(w["db"], employee_id=emp.id, order_id=w["order"].id, started_at=datetime.combine(w["gestern"], um))


def _ende(client, entry_id, tag, uhrzeit, pause=0):
    return client.post(f"/api/time-entries/{entry_id}/ende-nachtragen", json={"ende": f"{tag.isoformat()}T{uhrzeit}", "pause_minuten": pause})


# --- offene Zeit in /mobil ------------------------------------------------------------------------------------------------------------

def test_today_nennt_die_offene_zeit(welt):
    row = _gestern_gestartet(welt, welt["mia"])
    d = _als(welt, welt["mia"]).get("/api/field-view/today").json()
    z = d["offene_zeit"]
    assert (z["id"], z["work_date"], z["started_at"]) == (row.id, welt["gestern"].isoformat(), f"{welt['gestern'].isoformat()}T06:45:00")
    assert (z["entry_type"], z["entry_type_label"], z["order_number"], z["gruppe"], z["selbst_schliessen"]) == (
        "site", "Baustellenzeit", welt["order"].order_number, False, True)


def test_today_ohne_offene_zeit(welt):
    """Gegenprobe: eine heute gestartete Zeit ist keine offene Zeit."""
    start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    assert _als(welt, welt["mia"]).get("/api/field-view/today").json()["offene_zeit"] is None


# --- normaler Stopp -------------------------------------------------------------------------------------------------------------------

def test_stopp_am_naechsten_morgen_abgelehnt(welt):
    """Angriff: der Stopp am nächsten Morgen buchte bis 1.9.34 über 24 h auf den Vortag."""
    row = _gestern_gestartet(welt, welt["mia"])
    antwort = _als(welt, welt["mia"]).post(f"/api/time-entries/{row.id}/stop", json={"break_minutes": 0})
    assert antwort.status_code == 409 and "Ende nachtragen" in antwort.json()["detail"]
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, row.id).status == "running"


def test_stopp_heute_gestartet_ok(welt):
    """Gegenprobe: eine heute gestartete Zeit stoppt wie bisher."""
    row = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    antwort = _als(welt, welt["mia"]).post(f"/api/time-entries/{row.id}/stop",
                                            json={"break_minutes": 0, "ended_at": f"{welt['heute'].isoformat()}T09:00:00"})
    assert antwort.status_code == 200 and antwort.json()["status"] == "booked"


def test_gruppen_stopp_am_naechsten_morgen_abgelehnt(welt):
    db = welt["db"]
    db.add(TeamEmployee(team_id=welt["team"].id, employee_id=welt["mia"].id, is_crew_leader=True))
    db.add(TeamEmployee(team_id=welt["team"].id, employee_id=welt["tom"].id))
    db.commit()
    gruppe = start_group_timer(db, employee_ids=[welt["mia"].id, welt["tom"].id], team_id=welt["team"].id, actor_employee_id=welt["mia"].id,
                               is_admin=True, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(7)))
    antwort = _als(welt, welt["mia"]).post(f"/api/time-entry-groups/{gruppe.id}/stop", json={"break_minutes": 0})
    assert antwort.status_code == 409 and "Ende nachtragen" in antwort.json()["detail"]


# --- Ende nachtragen ------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tag_versatz, uhrzeit, text", [
    (0, "06:30", "nach dem Start"),         # Ende vor dem Start
    (0, "06:45", "nach dem Start"),         # Ende gleich dem Start
    (1, "08:00", "am Starttag"),            # am Folgetag
], ids=["vor_start", "gleich_start", "folgetag"])
def test_falsches_ende_abgelehnt(welt, tag_versatz, uhrzeit, text):
    row = _gestern_gestartet(welt, welt["mia"])
    antwort = _ende(_als(welt, welt["mia"]), row.id, welt["gestern"] + timedelta(days=tag_versatz), uhrzeit)
    assert antwort.status_code == 422 and text in antwort.json()["detail"]
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, row.id).status == "running"


def test_richtiges_ende_gebucht_mit_pause_nach_zeitregel(welt):
    """Gegenprobe: 06:45–16:00 am Starttag -- gebucht wie ein Feierabend um 16:00 (9,25 h anwesend, 45 min Pause, 8,50 h)."""
    row = _gestern_gestartet(welt, welt["mia"])
    antwort = _ende(_als(welt, welt["mia"]), row.id, welt["gestern"], "16:00")
    assert antwort.status_code == 200, antwort.text
    d = antwort.json()
    assert (d["status"], d["ended_at"], d["laeuft_seit_frueher"]) == ("booked", f"{welt['gestern'].isoformat()}T16:00:00", False)
    assert (Decimal(d["anwesend"]), d["pause"], Decimal(d["gebucht"])) == (Decimal("9.25"), 45, Decimal("8.5"))


def test_eingegebene_pause_ist_mindestpause(welt):
    row = _gestern_gestartet(welt, welt["mia"])
    d = _ende(_als(welt, welt["mia"]), row.id, welt["gestern"], "16:00", pause=60).json()
    assert (d["pause"], Decimal(d["gebucht"])) == (60, Decimal("8.25"))


def test_zweimal_schliessen_abgelehnt(welt):
    row = _gestern_gestartet(welt, welt["mia"])
    client = _als(welt, welt["mia"])
    assert _ende(client, row.id, welt["gestern"], "16:00").status_code == 200
    antwort = _ende(client, row.id, welt["gestern"], "17:00")
    assert (antwort.status_code, antwort.json()["detail"]) == (409, "Diese Zeit ist schon geschlossen.")


def test_heute_gestartete_zeit_nicht_ueber_ende_nachtragen(welt):
    row = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    antwort = _ende(_als(welt, welt["mia"]), row.id, welt["heute"], "09:00")
    assert antwort.status_code == 409 and "normal stoppen" in antwort.json()["detail"]


# --- Start bei offener Zeit -----------------------------------------------------------------------------------------------------------

def test_start_mit_offener_zeit_abgelehnt(welt):
    _gestern_gestartet(welt, welt["mia"])
    antwort = _als(welt, welt["mia"]).post("/api/time-entries/start", json={"employee_id": welt["mia"].id, "order_id": welt["order"].id,
                                                                              "entry_type": "site"})
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == (f"Die Zeit vom {welt['gestern']:%d.%m.%Y} läuft noch – zuerst das Ende nachtragen, dann neu "
                                        "starten.")


def test_start_neben_heute_laufender_zeit_wie_bisher(welt):
    """Gegenprobe: läuft die Zeit seit heute, bleibt die Meldung „läuft bereits“ (409)."""
    start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    antwort = _als(welt, welt["mia"]).post("/api/time-entries/start", json={"employee_id": welt["mia"].id, "order_id": welt["order"].id,
                                                                              "entry_type": "site"})
    assert antwort.status_code == 409 and "läuft bereits" in antwort.json()["detail"]


def test_start_nach_ende_nachtragen_ok(welt):
    """Gegenprobe: nach „Ende nachtragen“ startet die Monteurin neu."""
    row = _gestern_gestartet(welt, welt["mia"])
    client = _als(welt, welt["mia"])
    assert _ende(client, row.id, welt["gestern"], "16:00").status_code == 200
    antwort = client.post("/api/time-entries/start", json={"employee_id": welt["mia"].id, "order_id": welt["order"].id, "entry_type": "site"})
    assert antwort.status_code == 200 and antwort.json()["status"] == "running"


# --- Rechte ---------------------------------------------------------------------------------------------------------------------------

def test_monteurin_schliesst_fremde_zeit_nicht(welt):
    row = _gestern_gestartet(welt, welt["tom"])
    antwort = _ende(_als(welt, welt["mia"]), row.id, welt["gestern"], "16:00")
    assert (antwort.status_code, antwort.json()["detail"]) == (403, "Du darfst diese Zeit nicht schließen.")


@pytest.mark.parametrize("rolle", ["buero_finanzen", "buero_auftrag"])
def test_buero_schliesst_fremde_zeit_nicht(welt, rolle):
    """darf_zeit_fuer_andere_buchen() ist heute nur Admin -- das Büro schließt keine fremde Zeit."""
    row = _gestern_gestartet(welt, welt["tom"])
    assert _ende(_als(welt, rolle=rolle), row.id, welt["gestern"], "16:00").status_code == 403


def test_admin_schliesst_fremde_zeit_und_steht_im_verlauf(welt):
    """Gegenprobe: ein Admin schließt Toms Zeit -- im Verlauf steht, wer."""
    row = _gestern_gestartet(welt, welt["tom"])
    client = _als(welt, rolle="admin", display_name="Admin Anna")

    @client.app.middleware("http")
    async def _verlauf(request, call_next):  # wie die Anmeldeschranke: der Name des Kontos für den Verlauf
        tokens = set_audit_context(type("Konto", (), {"id": None, "display_name": "Admin Anna"})(), request)
        try:
            return await call_next(request)
        finally:
            reset_audit_context(tokens)

    vorher = welt["db"].scalar(select(func.max(AuditLog.id))) or 0
    antwort = _ende(client, row.id, welt["gestern"], "16:00")
    assert antwort.status_code == 200 and antwort.json()["status"] == "booked"
    neu = welt["db"].execute(select(AuditLog.actor_name, AuditLog.entity_id, AuditLog.field_name).where(AuditLog.id > vorher)).all()
    assert {(n, i) for n, i, _ in neu} == {("Admin Anna", str(row.id))}
    assert {"status", "ended_at", "hours"} <= {f for _, _, f in neu}


def _gruppe_gestern(w, kolonnenfuehrer=True):
    db = w["db"]
    db.add(TeamEmployee(team_id=w["team"].id, employee_id=w["mia"].id, is_crew_leader=kolonnenfuehrer))
    db.add(TeamEmployee(team_id=w["team"].id, employee_id=w["tom"].id))
    db.commit()
    gruppe = start_group_timer(db, employee_ids=[w["mia"].id, w["tom"].id], team_id=w["team"].id, actor_employee_id=w["mia"].id, is_admin=True,
                               order_id=w["order"].id, started_at=datetime.combine(w["gestern"], time(6, 45)))
    return {e.employee_id: e.id for e in db.scalars(select(TimeEntry).where(TimeEntry.status == "running")).all()}, gruppe


def test_ex_kolonnenfuehrer_schliesst_gruppenzeit_nicht(welt):
    """Angriff: Mia hat die Gruppe gestartet, ist aber nicht mehr Kolonnenführerin."""
    zeiten, _ = _gruppe_gestern(welt, kolonnenfuehrer=False)
    antwort = _ende(_als(welt, welt["mia"]), zeiten[welt["mia"].id], welt["gestern"], "16:00")
    assert (antwort.status_code, antwort.json()["detail"]) == (403, "Die Gruppenzeit schließt der Kolonnenführer.")


def test_mitglied_schliesst_gruppenzeit_nicht(welt):
    zeiten, _ = _gruppe_gestern(welt)
    antwort = _ende(_als(welt, welt["tom"]), zeiten[welt["tom"].id], welt["gestern"], "16:00")
    assert antwort.status_code == 403
    start = _als(welt, welt["tom"]).post("/api/time-entries/start", json={"employee_id": welt["tom"].id, "order_id": welt["order"].id,
                                                                          "entry_type": "site"})
    assert start.status_code == 409 and "Kolonnenführer" in start.json()["detail"]


def test_kolonnenfuehrer_schliesst_die_ganze_gruppe(welt):
    """Gegenprobe: die Kolonnenführerin schließt -- für die Gruppe, wie der Gruppen-Stopp, jede Person nach der Zeitregel."""
    zeiten, gruppe = _gruppe_gestern(welt)
    antwort = _ende(_als(welt, welt["mia"]), zeiten[welt["mia"].id], welt["gestern"], "16:00")
    assert antwort.status_code == 200, antwort.text
    db = welt["db"]
    db.expire_all()
    for entry_id in zeiten.values():
        e = db.get(TimeEntry, entry_id)
        assert (e.status, e.ended_at, e.break_minutes, e.hours) == ("booked", datetime.combine(welt["gestern"], time(16)), 45, Decimal("8.5"))
    assert db.get(type(gruppe), gruppe.id).status == "booked"


# --- Abschluss ------------------------------------------------------------------------------------------------------------------------

def test_monteurin_im_abgeschlossenen_monat_abgelehnt(welt):
    row = _gestern_gestartet(welt, welt["mia"])
    set_time_lock(welt["db"], welt["gestern"], user_id=None)
    antwort = _ende(_als(welt, welt["mia"]), row.id, welt["gestern"], "16:00")
    assert (antwort.status_code, antwort.json()["detail"]) == (403, "Monat abgeschlossen – das Büro schließt die Zeit.")


def test_admin_im_abgeschlossenen_monat_ok(welt):
    """Gegenprobe: ein Admin schließt sie dort (wie jede Änderung im abgeschlossenen Zeitraum)."""
    row = _gestern_gestartet(welt, welt["mia"])
    set_time_lock(welt["db"], welt["gestern"], user_id=None)
    assert _ende(_als(welt, rolle="admin"), row.id, welt["gestern"], "16:00").status_code == 200


def test_laeuft_seit_frueher_nach_berliner_datum(welt):
    row = _gestern_gestartet(welt, welt["mia"], um=time(23, 30))
    assert laeuft_seit_frueher(row) and not laeuft_seit_frueher(row, heute=welt["gestern"])
