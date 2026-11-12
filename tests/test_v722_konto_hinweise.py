"""Version 1.9.322 (Lohn L2c-1, Punkt 2): Hinweise zum Arbeitszeitkonto in „Zeiten → Prüfen“ (app/zeiten.py::konto_hinweise(); Antworten B4, B5, B11).

    ohne Eintrag   ein Tag mit Sollzeit einer gewerblichen Person ohne gebuchte und ohne laufende Zeit, ohne Abwesenheit, Feiertag, Kalendertag und Ausfalltag
                   -- auch ein betriebsfreier Tag ohne Urlaub: „Tag ohne Eintrag – zählt im Konto als Minus“, je Person mit Tagen und Sollzeit
    Arbeit         gebuchte Arbeit an einem ganzen Urlaubs- oder Kranktag: „Arbeit an einem Urlaubs- oder Kranktag – zählt im Konto als Plus“ -- nicht am halben
                   Urlaubstag, nicht an anderen Abwesenheiten, nicht am Feiertag
    wann           ab dem 01.01.2027, ab dem Beginn von „Prüfen“, bis gestern
    wer            nur gewerbliche; sehen nur Admin und Büro – Finanzen; keine Zahl am Reiter, keine Sperre des Abschlusses
"""

from datetime import date, datetime, time
from decimal import Decimal

from app.models import EmployeeAbsence, PlanningHoliday, TimeEntry
from app.routers import zeiten as zeiten_router
from app.time_backoffice import abschluss_hindernisse
from app.zeiten import ARBEIT_BEI_ABWESENHEIT, TAG_OHNE_EINTRAG, konto_hinweise
from tests.test_v626_lohndatei import abwesend, buchen, person, w  # noqa: F401  (w ist die Fixture)

D = Decimal


def laufend(w, e, tag):
    o = w["order"]
    w["db"].add(TimeEntry(employee_id=e.id, project_id=o.project_id, order_id=o.id, work_date=tag, entry_type="site", hours=D("0"), break_minutes=0,
                          status="running", started_at=datetime.combine(tag, time(7))))
    w["db"].commit()


def test_tag_ohne_eintrag(w):
    db = w["db"]
    a = person(w, "M-1", "Ada", "00091")
    k = person(w, "M-2", "Kai", "00092", gruppe="kaufmaennisch")  # ohne Konto: kein Hinweis
    e = person(w, "M-3", "Eva", "00093", eintritt=date(2027, 1, 6))
    db.add(PlanningHoliday(holiday_date=date(2027, 1, 6), name="Brückentag", active=True))  # betriebsfrei: zählt als Tag ohne Eintrag (B5)
    db.commit()
    buchen(w, a, "7.50", date(2027, 1, 4))
    abwesend(w, a, date(2027, 1, 7), kategorie="freizeitausgleich", art="Freizeitausgleich")  # eine Abwesenheit: kein Hinweis (das Minus ist gewollt)
    buchen(w, a, "7.50", date(2027, 1, 8))
    abwesend(w, e, date(2027, 1, 7), kategorie="schlechtwetter", art="Schlechtwetter")  # Ausfalltag: kein Hinweis
    laufend(w, e, date(2027, 1, 8))  # eine laufende Zeit: kein Hinweis (sie steht unter „Zeiten von früher“)
    h = konto_hinweise(db, date(2027, 1, 1), heute=date(2027, 1, 11))  # bis So 10.01.; Fr 01.01. Neujahr, Sa/So ohne Sollzeit
    assert h["ohne_eintrag"] == [
        {"employee_id": a.id, "name": "Ada Test", "tage": [date(2027, 1, 5), date(2027, 1, 6)], "soll": D("15.00"), "text": TAG_OHNE_EINTRAG},
        {"employee_id": e.id, "name": "Eva Test", "tage": [date(2027, 1, 6)], "soll": D("7.50"), "text": TAG_OHNE_EINTRAG}]  # vor dem Eintritt nichts
    assert h["arbeit_bei_abwesenheit"] == [] and k.id not in {x["employee_id"] for x in h["ohne_eintrag"]}


def test_arbeit_an_urlaubs_oder_kranktag(w):
    db = w["db"]
    b = person(w, "M-1", "Ben", "00091")
    abwesend(w, b, date(2027, 1, 4), date(2027, 1, 5))
    buchen(w, b, "3.00", date(2027, 1, 4))
    abwesend(w, b, date(2027, 1, 6), kategorie="krankheit", art="Krankheit")
    buchen(w, b, "2.00", date(2027, 1, 6))
    abwesend(w, b, date(2027, 1, 7), kategorie="sonderurlaub", art="Sonderurlaub")
    buchen(w, b, "1.00", date(2027, 1, 7))  # andere Abwesenheit: kein Hinweis
    db.add(EmployeeAbsence(employee_id=b.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 1, 8), end_date=date(2027, 1, 8),
                           halber_tag=True))
    db.commit()
    buchen(w, b, "4.00", date(2027, 1, 8))  # halber Urlaubstag mit Arbeit: gewollt
    buchen(w, b, "2.00", date(2027, 1, 1))  # Arbeit am Feiertag: ein Plus ohne Hinweis
    abwesend(w, b, date(2027, 1, 11), kategorie="krankheit", art="Krankheit")  # krank ohne Arbeit: nichts
    h = konto_hinweise(db, date(2027, 1, 1), heute=date(2027, 1, 12))
    assert h["arbeit_bei_abwesenheit"] == [{"employee_id": b.id, "name": "Ben Test", "text": ARBEIT_BEI_ABWESENHEIT, "tage": [
        {"tag": date(2027, 1, 4), "art": "Urlaub", "arbeit": D("3.00")}, {"tag": date(2027, 1, 6), "art": "Krankheit", "arbeit": D("2.00")}]}]
    assert h["ohne_eintrag"] == []


def test_ab_dem_kontobeginn_und_bis_gestern(w):
    db = w["db"]
    a = person(w, "M-1", "Ada", "00091")  # im Dezember 2026 jeden Tag ohne Eintrag -- vor dem Kontobeginn kein Hinweis
    assert konto_hinweise(db, date(2026, 12, 1), heute=date(2027, 1, 5))["ohne_eintrag"] == [
        {"employee_id": a.id, "name": "Ada Test", "tage": [date(2027, 1, 4)], "soll": D("7.50"), "text": TAG_OHNE_EINTRAG}]
    assert konto_hinweise(db, date(2027, 1, 1), heute=date(2027, 1, 4))["ohne_eintrag"] == []  # heute zählt nicht
    assert konto_hinweise(db, date(2026, 11, 1), heute=date(2026, 11, 10)) == {"ohne_eintrag": [], "arbeit_bei_abwesenheit": []}
    assert konto_hinweise(db, date(2027, 1, 5), heute=date(2027, 1, 7))["ohne_eintrag"][0]["tage"] == [date(2027, 1, 5), date(2027, 1, 6)]  # ab „Prüfen“


def test_schnittstelle_rechte_ohne_zahl_und_ohne_sperre(w, router_test_client, monkeypatch):
    db = w["db"]
    a = person(w, "M-1", "Ada", "00091")
    abwesend(w, a, date(2027, 1, 4), kategorie="krankheit", art="Krankheit")
    buchen(w, a, "2.00", date(2027, 1, 4))
    # die Fixture schließt bis 31.12.2026 ab: „Prüfen“ beginnt am 01.01.2027
    monkeypatch.setattr(zeiten_router, "berlin_today", lambda: date(2027, 1, 7))
    for rolle in ("admin", "buero_finanzen"):
        d = router_test_client(db, zeiten_router.router, role=rolle).get("/api/zeiten/pruefen").json()
        assert [x["tage"] for x in d["konto"]["ohne_eintrag"]] == [["2027-01-05", "2027-01-06"]], rolle
        assert [x["employee_id"] for x in d["konto"]["arbeit_bei_abwesenheit"]] == [a.id], rolle
        assert d["zahlen"]["pruefen"] == 0, rolle  # nur Hinweise: keine Zahl am Reiter
    d = router_test_client(db, zeiten_router.router, role="buero_auftrag").get("/api/zeiten/pruefen").json()
    assert d["konto"] == {"ohne_eintrag": [], "arbeit_bei_abwesenheit": []}  # Büro – Auftrag sieht die Hinweise nicht (Urlaub, Krankheit)
    assert abschluss_hindernisse(db, date(2027, 1, 31)) == []  # keine Sperre
