"""Version 1.9.319 (Nachrunde L2b, Punkt C): beim Stellen „· mit den anderen offenen Anträgen m Tage“.

    Regel         gibt es im Jahr weitere offene Anträge auf Urlaub, dazu „ · mit den anderen offenen Anträgen m Tage“ -- m = Rest nach den offenen Anträgen
                  minus dieser Urlaub; ohne weitere nicht; Sonderurlaub und entschiedene Anträge zählen nicht; ein offener Antrag in einem anderen Jahr nicht;
                  vor dem Hinweis „ohne Übertrag – Startwert folgt“
    Stellen       GET /api/absence-requests/rest-danach nennt es; beim Genehmigen (an den offenen Anträgen) nicht -- dort ist der Antrag selbst unter den offenen
Stehende Uhr 10.11.2026 (fester_tag).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models import EmployeeAbsence, EmployeeAbsenceRequest, LohnStartwert
from app.routers import absence_requests as antraege_router
from app.routers import zeiten as zeiten_router
from app.urlaubskonto import rest_danach
from tests.test_v224_field_view import make_employee

D = Decimal
R = "/api/absence-requests/rest-danach"


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    ada, bo = make_employee(db, "M-1", "Ada", "Monteurin"), make_employee(db, "M-2", "Bo", "Monteur")
    db.add(LohnStartwert(employee_id=ada.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("4.5"), saldo_stunden=D("0"), herkunft="steuerbuero"))
    db.add(EmployeeAbsence(employee_id=ada.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 1, 4), end_date=date(2027, 1, 8)))
    db.commit()
    return {"db": db, "ada": ada, "bo": bo, "client": router_test_client}


def antrag(w, e, von, bis, kategorie="urlaub", status="pending"):
    w["db"].add(EmployeeAbsenceRequest(employee_id=e.id, absence_type=kategorie.capitalize(), absence_category=kategorie, start_date=von, end_date=bis,
                                       status=status))
    w["db"].commit()


def text(w, e, von, bis):
    return w["client"](w["db"], antraege_router.router, role="admin").get(f"{R}?employee_id={e.id}&von={von}&bis={bis}").json()["text"]


def test_ohne_weitere_offene_kein_zusatz(w):
    antrag(w, w["ada"], date(2027, 6, 7), date(2027, 6, 11), status="approved")  # entschieden
    antrag(w, w["ada"], date(2027, 6, 14), date(2027, 6, 15), kategorie="sonderurlaub")  # zählt nicht gegen den Urlaub
    antrag(w, w["ada"], date(2028, 3, 6), date(2028, 3, 10))  # anderes Jahr
    assert text(w, w["ada"], "2027-04-12", "2027-04-16") == "danach Rest 24,5 Tage"


def test_mit_weiteren_offenen(w):
    db, ada, bo = w["db"], w["ada"], w["bo"]
    antrag(w, ada, date(2027, 6, 21), date(2027, 6, 25))  # 5 Tage offen (eine Woche ohne Feiertag)
    assert text(w, ada, "2027-04-12", "2027-04-16") == "danach Rest 24,5 Tage · mit den anderen offenen Anträgen 19,5 Tage"
    d = rest_danach(db, ada.id, date(2027, 4, 12), date(2027, 4, 16), andere_offene=True)
    assert [(x["rest_danach"], x["mit_anderen"]) for x in d["jahre"]] == [(D("24.5"), D("19.5"))]
    # vor dem Hinweis ohne Startwert; über den Jahreswechsel je Jahr mit offenen Anträgen
    antrag(w, bo, date(2027, 5, 3), date(2027, 5, 4))
    assert text(w, bo, "2027-04-12", "2027-04-16") == ("danach Rest 25 Tage · mit den anderen offenen Anträgen 23 Tage"
                                                       " · ohne Übertrag – Startwert folgt")
    assert text(w, ada, "2027-12-27", "2028-01-07") == ("danach Rest 2027: 24,5 Tage · 2028: 25 Tage · mit den anderen offenen Anträgen 2027: 19,5 Tage")


def test_beim_genehmigen_nicht(w):
    db, ada = w["db"], w["ada"]
    antrag(w, ada, date(2027, 4, 12), date(2027, 4, 16))
    antrag(w, ada, date(2027, 6, 21), date(2027, 6, 25))
    liste = w["client"](db, zeiten_router.router, role="admin").get("/api/zeiten/abwesenheiten").json()["antraege"]
    assert sorted(a["rest_danach"] for a in liste) == ["danach Rest 24,5 Tage", "danach Rest 24,5 Tage"]
