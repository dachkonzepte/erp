"""Version 1.9.166 (Lohn L1a, Punkt 1, Entscheidung Tobias E1 und E2): die gesetzliche Pause nach Lesart A.

    Regel        je Pausenregel höchstens die Minuten über ihrer Schwelle, davon das Maximum (app/work_time_models.py::pflichtpause()):
                 der kleinste Wert, der zur Arbeitszeit danach passt: nie unter 6,00 h -- 07:15–13:30 ohne Pause = 6,00 h --, unter 9,00 h
                 schon (9:15 h -> 30 min, 8,75 h; Festlegung 1.9.166 Nr. 1, neu gefasst 1.9.179)
    Tag          weiter je Tag (seit 1.9.48): die Pflichtpause wächst nie schneller als die Anwesenheit, also nimmt die neue Buchung die
                 fehlende Pause immer ganz auf -- auch eine kurze letzte Buchung (L0, Abschnitt 2.3)
    Dauer        eine Dauer ist Arbeitszeit; was ihr an Pause fehlt, rechnet fehlende_pause() so, dass es danach passt: 6,25 h ohne Pause
                 -> 30 min (nicht erst 15, dann 30)
    Kein Stichtag  die Regel gilt für alle Buchungen (E2). Feste Tage (Fixture fester_tag), nicht relativ zu heute.
"""

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.models import TeamEmployee, TimeEntry
from app.routers import time_backoffice as time_backoffice_router
from app.routers import time_tracking as time_tracking_router
from app.routers import zeiten as zeiten_router
from app.time_tracking import create_manual_entry, pausen_vorschau, start_timer, stop_timer
from app.work_time_models import fehlende_pause, pflichtpause
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote

TAG = date(2026, 11, 9)  # Montag vor dem festen Tag 10.11.2026
REGELN = [(Decimal("6"), 30), (Decimal("9"), 45)]  # die Grunddaten


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0584"))
    team = make_team(db, "K-1", "Kolonne 1")
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    db.add_all([TeamEmployee(team_id=team.id, employee_id=mia.id, is_crew_leader=True), TeamEmployee(team_id=team.id, employee_id=tom.id)])
    db.commit()
    return {"db": db, "order": order, "mia": mia, "tom": tom, "client": router_test_client}


def _als(w, rolle="buero_finanzen", employee_id=None):
    w["db"].commit()
    return w["client"](w["db"], zeiten_router.router, time_tracking_router.router, time_backoffice_router.router, role=rolle,
                       employee_id=employee_id)


def _zeit(w, emp, von, bis, tag=TAG):
    row = start_timer(w["db"], employee_id=emp.id, order_id=w["order"].id, started_at=datetime.combine(tag, von))
    return stop_timer(w["db"], row.id, ended_at=datetime.combine(tag, bis))


def _h(hm: str) -> Decimal:
    s, m = hm.split(":")
    return (Decimal(int(s)) + Decimal(int(m)) / 60).quantize(Decimal("0.0001"))


# --- die Formel -------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("anwesend, pause", [
    ("6:00", 0), ("6:01", 1), ("6:15", 15), ("6:20", 20), ("6:30", 30), ("6:45", 30), ("9:00", 30), ("9:01", 30), ("9:15", 30),
    ("9:30", 30), ("9:40", 40), ("9:45", 45), ("10:00", 45), ("12:00", 45)])
def test_pflichtpause_lesart_a(anwesend, pause):
    """Die Tabelle aus L0, Abschnitt 2.2 (Spalte „neu (A)“). Bis 1.9.165 über 6 h immer 30 und über 9 h immer 45 min."""
    assert pflichtpause(REGELN, _h(anwesend)) == pause


def test_waechst_nie_schneller_als_die_anwesenheit():
    """Von Minute zu Minute über 0 bis 12 h wächst die Pflichtpause um höchstens eine Minute -- darum nimmt die letzte Buchung eines Tags die
    fehlende Pause immer ganz auf."""
    vorher = 0
    for minute in range(0, 12 * 60 + 1):
        jetzt = pflichtpause(REGELN, (Decimal(minute) / 60).quantize(Decimal("0.0001")))
        assert 0 <= jetzt - vorher <= 1, minute
        vorher = jetzt


def test_sekunden_und_vier_stellen():
    """20 min = 0,3333 h kommen als 20 min heraus, 40 Sekunden über 6 h als 0 (abgerundet, nie unter 6,00 h)."""
    assert pflichtpause(REGELN, Decimal("6.3333")) == 20
    assert pflichtpause(REGELN, Decimal("6.0111")) == 0


@pytest.mark.parametrize("netto, pause, fehlt", [
    ("6.25", 0, 30), ("6.25", 15, 15), ("6.25", 30, 0), ("6.00", 0, 0), ("5.50", 0, 0), ("8.75", 30, 0), ("9.00", 30, 0),
    ("9.25", 30, 15), ("9.50", 40, 5), ("8.00", 60, 0)])
def test_fehlende_pause_einer_dauer(netto, pause, fehlt):
    """Eine Dauer (Stunden netto) mit eingetragener Pause: was fehlt, damit es passt. 6,25 h ohne Pause -> 30 min (L0, 2.3 a: bis 1.9.165
    erst 15, mit 15 eingetragen dann 30). Über 6 h Arbeit 30 min, über 9 h Arbeit 45 min."""
    anwesend = Decimal(netto) + Decimal(pause) / 60
    assert fehlende_pause(REGELN, anwesend, pause) == fehlt
    if fehlt:  # trägt man die fehlende Pause nach, passt es
        assert fehlende_pause(REGELN, anwesend + Decimal(fehlt) / 60, pause + fehlt) == 0


# --- gebucht ----------------------------------------------------------------------------------------------------------------------------

def test_beispiel_tobias_0715_bis_1330(welt):
    """07:15–13:30 ohne Pause = 6,00 h (bis 1.9.165 5,75 h)."""
    row = _zeit(welt, welt["mia"], time(7, 15), time(13, 30))
    assert (row.break_minutes, row.hours) == (15, Decimal("6.0000"))


@pytest.mark.parametrize("erste, zweite, pausen, gebucht", [
    ((time(7), time(13)), (time(13), time(13, 10)), (0, 10), (Decimal("6"), Decimal("0"))),     # 6:00 + 0:10 (bis 1.9.165 still 20 min zu wenig)
    ((time(7), time(12)), (time(12), time(13, 20)), (0, 20), (Decimal("5"), Decimal("1"))),     # 5:00 + 1:20
    ((time(7), time(13, 20)), (time(13, 20), time(13, 30)), (20, 10), (Decimal("6"), Decimal("0"))),  # 6:20 + 0:10
    ((time(6), time(15)), (time(15), time(15, 10)), (30, 0), (Decimal("8.5"), Decimal("0.1667"))),  # 9:00 + 0:10 (bis 1.9.165 8,50 + 0)
    ((time(6), time(15, 30)), (time(15, 30), time(15, 40)), (30, 10), (Decimal("9"), Decimal("0"))),  # 9:30 + 0:10
    ((time(6), time(15, 30)), (time(15, 30), time(16)), (30, 15), (Decimal("9"), Decimal("0.25"))),  # 9:30 + 0:30
], ids=["6h_10min", "5h_1h20", "6h20_10min", "9h_10min", "9h30_10min", "9h30_30min"])
def test_letzte_buchung_nimmt_die_fehlende_pause_ganz_auf(welt, erste, zweite, pausen, gebucht):
    """L0, Abschnitt 2.3: bis 1.9.165 konnte der letzten Buchung des Tags weniger Pause bleiben, als fehlte (6:00 + 0:10: 10 statt 30 min,
    „Prüfen“ sagte „passt“). Nach Lesart A fehlt nie mehr, als die neue Buchung hergibt -- der Tag passt danach wirklich."""
    a = _zeit(welt, welt["mia"], *erste)
    b = _zeit(welt, welt["mia"], *zweite)
    assert (a.break_minutes, b.break_minutes) == pausen
    assert (a.hours, b.hours) == gebucht
    stand = pausen_vorschau(welt["db"], welt["mia"].id, TAG)
    assert (stand["passt"], stand["fehlt"], stand["abgezogen"], stand["noetig"]) == (True, 0, sum(pausen), sum(pausen))


def test_spaetere_zeit_zuerst_wie_am_stueck(welt):
    """12:00–13:20 gebucht, dann 07:00–12:00 nachgetragen: zusammen 6,00 h wie 07:00–13:20 am Stück; der Tag passt."""
    nachmittag = _zeit(welt, welt["mia"], time(12), time(13, 20))
    vormittag = _zeit(welt, welt["mia"], time(7), time(12))
    am_stueck = _zeit(welt, welt["tom"], time(7), time(13, 20))
    assert nachmittag.hours + vormittag.hours == am_stueck.hours == Decimal("6")
    assert pausen_vorschau(welt["db"], welt["mia"].id, TAG)["passt"] is True


# --- Meldung für die Dauer -------------------------------------------------------------------------------------------------------------

def test_dauer_6_25_sagt_gleich_30(welt):
    """L0, 2.3 (a): „Neue Buchung“ als Dauer 6,25 h ohne Pause -> „nach Zeitregel 0:30 h“; mit 15 min weiter 30 (bis 1.9.165 erst 15, dann
    30); mit 30 passt der Tag. Gespeichert ohne Pause zeigt „Prüfen“ dieselbe Zahl."""
    client = _als(welt)
    def vorschau(pause):
        r = client.get("/api/time-entries/dauer-vorschau", params={"work_date": TAG.isoformat(), "hours": "6.25", "break_minutes": pause,
                                                                   "employee_id": welt["mia"].id})
        assert r.status_code == 200, r.text
        return r.json()
    assert [(v["passt"], v["noetig"]) for v in (vorschau(0), vorschau(15), vorschau(30))] == [(False, 30), (False, 30), (True, 30)]
    create_manual_entry(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, work_date=TAG, hours=Decimal("6.25"))
    stand = pausen_vorschau(welt["db"], welt["mia"].id, TAG)
    assert (stand["passt"], stand["fehlt"], stand["noetig"]) == (False, 30, 30)
    pruefen = client.get("/api/zeiten/pruefen").json()["pausen"]
    assert [(t["tag"], t["noetig"], t["fehlt"]) for t in pruefen] == [(TAG.isoformat(), 30, 30)]


def test_dauer_und_kurze_zeit(welt):
    """8,00 h Dauer ohne Pause + 0:10 mit Uhrzeit: die Zeit bekommt 10 min, der Dauer fehlen 20 -- zusammen die 30, die 8,17 h Arbeit brauchen
    (L0, 2.3 a: bleibt so, eine Dauer ist netto)."""
    create_manual_entry(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, work_date=TAG, hours=Decimal("8"))
    kurz = _zeit(welt, welt["mia"], time(16), time(16, 10))
    stand = pausen_vorschau(welt["db"], welt["mia"].id, TAG)
    assert (kurz.break_minutes, stand["fehlt"], stand["noetig"], stand["passt"]) == (10, 20, 30, False)


def test_alte_buchung_heisst_jetzt_passt_nicht(welt):
    """Kein Stichtag (E2): eine Buchung nach der alten Regel (6:15 h mit 30 min, Mindestpause 0) passt nicht mehr -- „Pausen neu rechnen“
    schlägt 15 min vor, nur auf Klick."""
    beginn, ende = datetime.combine(TAG, time(7)), datetime.combine(TAG, time(13, 15))
    alt = create_manual_entry(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, work_date=TAG, hours=Decimal("5.75"),
                              started_at=beginn, ended_at=ende, break_minutes=30)
    alt.min_break_minutes = 0
    welt["db"].commit()
    stand = pausen_vorschau(welt["db"], welt["mia"].id, TAG)
    assert (stand["passt"], [(b["pause_alt"], b["pause_neu"], b["gebucht_neu"]) for b in stand["buchungen"]]) == (False, [(30, 15, Decimal("6"))])
    welt["db"].expire_all()
    assert welt["db"].get(TimeEntry, alt.id).break_minutes == 30
