"""Version 1.9.211 (Lohn L1a, Stufe 5, Punkt 4): die Kapazität der Plantafel je Person und Tag kommt aus der Sollzeit des Lohns (app/sollzeit.py)
statt aus Wochenstunden und den Arbeitstagen der Planung.

    Kapazität   Sollzeit des Tags − Anfahrt, nie unter 0; ohne Sollzeit 0 (wie bisher an einem Kalendertag) -- die Person ist dann weder verfügbar
                noch abwesend; Feiertag und betriebsfreier Tag 0 für alle
    wirkt auf   Auslastung (Tafel), Verteilung der Stunden eines Einsatzes und den Hinweis „Kapazität reicht um … nicht aus“, Planungsvorschlag
                (volle Tageskapazität = erster Tag ab dem Start mit Sollzeit)
    nicht mehr  Wochenstunden des Mitarbeiters, Arbeitstage der Planung, „Arbeitsstunden je Tag“ (nur noch Obergrenze der Anfahrt)
    Abfragen    app/sollzeit.py::soll_fuer_personen(): je eine Abfrage für alle Personen, das Modell je Zuordnung und Kalenderwoche einmal

Feste Tage: Woche ab Mo 21.12.2026 (Winter, Tarif 7,50 h; Heiligabend Do 24.12., Freitag 25.12. Feiertag), Mo 02.11.2026 (Sommer, 8,00 h).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.models import EmployeePayrollSettings, PlanningHoliday, PlanningSettings
from app.planning import planning_board, planning_suggestion
from app.sollzeit import soll_fuer_personen, soll_zeitraum, zeile_anlegen
from tests.test_v090_planning_board import setup_order
from tests.test_v563_konflikte_beim_speichern import _kolonne, _person
from tests.test_v568_plantafel_kleinkram import _einsatz, _soll
from tests.test_v600_plantafel_kalender import MONTAG, tafel  # noqa: F401  (Fixture)

D = Decimal
SOMMER = date(2026, 11, 2)


def _kap(board, emp, tag):
    return board["employee_capacity"][str(emp.id)][tag.isoformat()]["capacity_hours"]


def test_kapazitaet_je_person_aus_der_sollzeit(tafel):  # noqa: F811
    """Mia Tarif (Dezember 7,50 h), Tom Di–Do 3,00 h, Ben Mo–Di 8,00 h -- alle mit 40 Wochenstunden (bis 1.9.210 je Arbeitstag 8,00 h)."""
    board = planning_board(tafel["db"], MONTAG, MONTAG + timedelta(days=6))
    woche = [MONTAG + timedelta(days=i) for i in range(4)]
    assert [_kap(board, tafel["mia"], t) for t in woche] == [D("7.50"), D("7.50"), D("7.50"), D("0")]  # Do: Heiligabend
    assert [_kap(board, tafel["tom"], t) for t in woche] == [D("0"), D("3.00"), D("3.00"), D("0")]
    assert [_kap(board, tafel["ben"], t) for t in woche] == [D("8.00"), D("8.00"), D("0"), D("0")]
    team = board["team_capacity"][str(tafel["team"].id)]
    assert [team[t.isoformat()]["capacity_hours"] for t in woche] == [D("15.50"), D("18.50"), D("10.50"), D("0")]
    assert [team[t.isoformat()]["available_employee_count"] for t in woche] == [2, 3, 2, 0]
    samstag, feiertag = MONTAG + timedelta(days=5), MONTAG + timedelta(days=4)
    assert team[samstag.isoformat()]["capacity_hours"] == D("0") and team[feiertag.isoformat()]["capacity_hours"] == D("0")


def test_ohne_sollzeit_nicht_abwesend(tafel):  # noqa: F811
    """Ben ist am Mittwoch ohne Sollzeit -- er zählt weder als verfügbar noch als abwesend, auch mit einer Abwesenheit an dem Tag nicht."""
    from app.models import EmployeeAbsence
    db = tafel["db"]
    mittwoch = MONTAG + timedelta(days=2)
    db.add(EmployeeAbsence(employee_id=tafel["ben"].id, absence_type="Urlaub", absence_category="urlaub", start_date=mittwoch, end_date=mittwoch))
    db.commit()
    board = planning_board(db, MONTAG, MONTAG + timedelta(days=6))
    team = board["team_capacity"][str(tafel["team"].id)][mittwoch.isoformat()]
    assert (team["available_employee_count"], team["absences"], team["capacity_hours"]) == (2, [], D("10.50"))
    # in seiner eigenen Zeile steht die Abwesenheit weiter da, Kapazität 0 (Gegenprobe 211_2b)
    zeile = board["employee_capacity"][str(tafel["ben"].id)][mittwoch.isoformat()]
    assert (zeile["absence"], zeile["capacity_hours"]) == ("Urlaub", D("0"))


def test_anfahrt_abgezogen_nie_unter_null(tafel):  # noqa: F811
    db = tafel["db"]
    db.query(PlanningSettings).one().default_travel_hours_per_employee_day = D("4")
    db.commit()
    board = planning_board(db, MONTAG, MONTAG + timedelta(days=6))
    dienstag = MONTAG + timedelta(days=1)
    assert [_kap(board, tafel[n], dienstag) for n in ("mia", "tom", "ben")] == [D("3.50"), D("0"), D("4.00")]


def test_arbeitstage_der_planung_zaehlen_nicht(tafel):  # noqa: F811
    """Samstag als Arbeitstag der Planung gibt ohne Sollzeit keine Kapazität, Mittwoch abgewählt nimmt sie nicht."""
    db = tafel["db"]
    einstellungen = db.query(PlanningSettings).one()
    einstellungen.saturday, einstellungen.wednesday = True, False
    db.commit()
    board = planning_board(db, MONTAG, MONTAG + timedelta(days=6))
    samstag, mittwoch = MONTAG + timedelta(days=5), MONTAG + timedelta(days=2)
    assert _kap(board, tafel["mia"], samstag) == D("0")
    assert _kap(board, tafel["mia"], mittwoch) == D("7.50")
    # auch die Kolonne -- sie rechnet auf eigenem Weg (_day_capacity()); bis zum Befund der Gegenprobe 211_4a nur die Person geprüft
    team = board["team_capacity"][str(tafel["team"].id)]
    assert (team[mittwoch.isoformat()]["capacity_hours"], team[samstag.isoformat()]["capacity_hours"]) == (D("10.50"), D("0"))


def test_feiertag_und_betriebsfreier_tag_null(tafel):  # noqa: F811
    db = tafel["db"]
    db.add(PlanningHoliday(holiday_date=MONTAG, name="Betriebsversammlung", active=True))
    db.commit()
    board = planning_board(db, MONTAG, MONTAG + timedelta(days=6))
    assert [_kap(board, tafel["mia"], t) for t in (MONTAG, MONTAG + timedelta(days=4))] == [D("0"), D("0")]
    team = board["team_capacity"][str(tafel["team"].id)]
    assert [team[t.isoformat()]["capacity_hours"] for t in (MONTAG, MONTAG + timedelta(days=4))] == [D("0"), D("0")]


def test_arbeitsstunden_je_tag_begrenzen_nicht(tafel):  # noqa: F811
    """„Arbeitsstunden je Tag“ 6,00 h: Mia hat weiter 7,50 h (bis 1.9.210 höchstens dieser Wert)."""
    db = tafel["db"]
    db.query(PlanningSettings).one().daily_work_hours = D("6")
    db.commit()
    board = planning_board(db, MONTAG, MONTAG + timedelta(days=6))
    assert _kap(board, tafel["mia"], MONTAG) == D("7.50")
    assert board["team_capacity"][str(tafel["team"].id)][MONTAG.isoformat()]["capacity_hours"] == D("15.50")  # Kolonne ebenso (Gegenprobe 211_4d)


def test_austritt_ohne_kapazitaet(tafel):  # noqa: F811
    db = tafel["db"]
    db.add(EmployeePayrollSettings(employee_id=tafel["mia"].id, austritt=MONTAG))
    db.commit()
    board = planning_board(db, MONTAG, MONTAG + timedelta(days=6))
    assert [_kap(board, tafel["mia"], t) for t in (MONTAG, MONTAG + timedelta(days=1))] == [D("7.50"), D("0")]


def test_kapazitaet_reicht_nicht_mit_der_sollzeit(threaded_db_session, router_test_client):
    """Zwei Personen im Winter (7,50 h): ein Tag mit 20 h geplant -- „um 5,00 h nicht aus“ (bis 1.9.210 mit 8,00 h: „um 4,00 h“); die Auslastung
    rechnet mit 15,00 h."""
    from app.routers.planning import router as planning_router
    db = threaded_db_session
    team = _kolonne(db, "A", [_person(db, "M-1", "Mia"), _person(db, "M-2", "Tom")])
    order = setup_order(db, "1")
    daten = _einsatz(router_test_client(db, planning_router), order, team, MONTAG, MONTAG, planned_hours="20")
    assert [k["label"] for k in daten["hinweise"] if k["type"] == "capacity"] == ["Kapazität reicht um 5,00 h nicht aus"]
    zeile = planning_board(db, MONTAG, MONTAG)["team_capacity"][str(team.id)][MONTAG.isoformat()]
    assert (zeile["capacity_hours"], zeile["planned_hours"], zeile["utilization_pct"]) == (D("15.00"), D("15.00"), D("100.0"))


def test_vorschlag_mit_der_sollzeit(tafel):  # noqa: F811
    """Start am Samstag 19.12.: die volle Kapazität ist die des Montags (15,50 h, Mia und Ben); 24,00 h verteilt auf Mo 15,50 und Di 8,50."""
    db = tafel["db"]
    order = setup_order(db, "1")
    _soll(db, order, 1440)
    s = planning_suggestion(db, order_id=order.id, team_id=tafel["team"].id, start_date=MONTAG - timedelta(days=2))
    assert (s["full_team_daily_capacity"], s["full_team_capacity_date"]) == (D("15.50"), MONTAG)
    assert s["formula"] == "24,00 h / 15,50 h (Sollzeit von 2 MA am 21.12.2026 − je 0,00 h Anfahrt) = 1,55 Teamtage"
    assert [(d["date"], d["capacity_hours"], d["assigned_hours"]) for d in s["days"]] == [
        (MONTAG, D("15.50"), D("15.50")), (MONTAG + timedelta(days=1), D("18.50"), D("8.50"))]
    assert s["suggested_end"] == MONTAG + timedelta(days=1)


def test_sollzeit_fuer_viele_wie_fuer_eine(tafel):  # noqa: F811
    db = tafel["db"]
    ids = [tafel[n].id for n in ("mia", "tom", "ben")]
    viele = soll_fuer_personen(db, ids, date(2026, 12, 1), date(2027, 1, 15))
    assert all(viele[i] == soll_zeitraum(db, i, date(2026, 12, 1), date(2027, 1, 15)) for i in ids)


def test_abfragen_haengen_nicht_an_der_zahl_der_personen(threaded_db_session):
    db = threaded_db_session
    wenige = [_person(db, f"W-{i}", f"W{i}") for i in range(2)]
    viele = wenige + [_person(db, f"V-{i}", f"V{i}") for i in range(10)]
    zeile_anlegen(db, viele[-1].id, date(2026, 12, 1), {"montag": D("4")})

    wenige_ids, viele_ids = [p.id for p in wenige], [p.id for p in viele]  # vorher -- das Nachladen abgelaufener Objekte zählte sonst mit

    def zaehlen(ids):
        n = [0]
        lauscher = lambda *a, **k: n.__setitem__(0, n[0] + 1)  # noqa: E731
        event.listen(db.get_bind(), "before_cursor_execute", lauscher)
        try:
            soll_fuer_personen(db, ids, MONTAG, MONTAG + timedelta(days=27))
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", lauscher)
        return n[0]

    zaehlen(wenige_ids)  # Leeraufruf
    assert zaehlen(viele_ids) == zaehlen(wenige_ids)


def test_seite_nennt_die_sollzeit():
    from tests import vorlagen_js as vj
    plantafel = vj.seitentext("planning.html")[0]
    assert "Sollzeit am ${fmt(s.full_team_capacity_date)} − je ${num(s.travel_hours_per_employee_day)} h Anfahrt" in plantafel
    einstellungen = vj.seitentext("settings.html")[0]
    assert "Die Kapazität je Mitarbeiter und Tag ist die Sollzeit aus „Zeitregeln und DATEV“" in einstellungen
    assert einstellungen.count("Nicht mehr für die Kapazität (die kommt aus der Sollzeit)") == 2


@pytest.mark.parametrize("tag, soll", [(SOMMER, D("8.00")), (MONTAG, D("7.50"))], ids=["sommer", "winter"])
def test_tarif_je_jahreszeit(threaded_db_session, tag, soll):
    db = threaded_db_session
    team = _kolonne(db, "A", [_person(db, "M-1", "Mia")])
    zeile = planning_board(db, tag, tag)["team_capacity"][str(team.id)][tag.isoformat()]
    assert zeile["capacity_hours"] == soll
