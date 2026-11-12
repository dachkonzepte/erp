"""Version 1.9.320 (Lohn L2c-1, Punkt 0; Antwort B16 des Befunds L2c): „ohne Übertrag – Startwert folgt“ nur für Personen, die am 31.12.2026 beschäftigt
waren (app/lohnkonten.py::am_stichtag_beschaeftigt()).

    beschäftigt   Eintritt leer oder bis 31.12.2026, Austritt leer oder ab 31.12.2026 (beide Tage eingeschlossen); ohne Lohnstammdaten gilt die Person als
                  beschäftigt -- der Hinweis bleibt, solange der Startwert fehlt
    danach        wer erst 2027 eintritt, bekommt keinen Startwert: Übertrag 0 ohne Hinweis, „Anspruch prüfen“ bleibt (Eintritt im Jahr)
    überall       das Konto, „danach Rest“ und „Meine Zeiten“ lesen den Hinweis aus derselben Stelle
Stehende Uhr 10.11.2026 (fester_tag).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.lohnkonten import am_stichtag_beschaeftigt
from app.meine_zeiten import meine_zeiten
from app.models import EmployeePayrollSettings, LohnStartwert
from app.urlaubskonto import ANSPRUCH_PRUEFEN, OHNE_STARTWERT, konten, rest_danach
from tests.test_v224_field_view import make_employee

D = Decimal
H = " · ohne Übertrag – Startwert folgt"


@pytest.fixture
def w(threaded_db_session, fester_tag):
    db = threaded_db_session
    leute = {n: make_employee(db, f"M-{i}", n, "Monteur") for i, n in enumerate(("Ada", "Bo", "Cem", "Dan", "Eli", "Fe", "Gus"), start=1)}
    lohn = {"Bo": (date(2027, 1, 1), None), "Cem": (date(2026, 12, 31), None), "Dan": (date(2027, 3, 1), None), "Eli": (None, None),
            "Fe": (date(2020, 1, 1), date(2026, 12, 30)), "Gus": (date(2020, 1, 1), date(2026, 12, 31))}
    for name, (eintritt, austritt) in lohn.items():
        db.add(EmployeePayrollSettings(employee_id=leute[name].id, eintritt=eintritt, austritt=austritt, export_umfang="alles", payroll_export_enabled=True))
    db.add(LohnStartwert(employee_id=leute["Ada"].id, stichtag=date(2026, 12, 31), resturlaub_tage=None, saldo_stunden=D("0"), herkunft="steuerbuero"))
    db.commit()
    return {"db": db, **leute}


def hinweise(w, name):
    return next(k for k in konten(w["db"], 2027, heute=date(2027, 2, 1)) if k.employee_id == w[name].id).hinweise


def test_regel_am_stichtag():
    assert am_stichtag_beschaeftigt(None)  # ohne Lohnstammdaten
    for eintritt, austritt, soll in [(None, None, True), (date(2026, 12, 31), None, True), (date(2027, 1, 1), None, False),
                                     (date(2020, 1, 1), date(2026, 12, 31), True), (date(2020, 1, 1), date(2026, 12, 30), False)]:
        assert am_stichtag_beschaeftigt(EmployeePayrollSettings(eintritt=eintritt, austritt=austritt)) is soll, (eintritt, austritt)


def test_hinweis_nur_wer_am_stichtag_beschaeftigt_war(w):
    assert hinweise(w, "Ada") == [OHNE_STARTWERT]  # Startwert ohne Resturlaub, ohne Lohnstammdaten: beschäftigt
    assert hinweise(w, "Cem") == [OHNE_STARTWERT]  # Eintritt am Stichtag
    assert hinweise(w, "Eli") == [OHNE_STARTWERT]  # Lohnstammdaten ohne Eintritt
    assert hinweise(w, "Bo") == [ANSPRUCH_PRUEFEN]  # Eintritt 01.01.2027: kein Startwert, „Anspruch prüfen“ bleibt
    assert hinweise(w, "Dan") == [ANSPRUCH_PRUEFEN]  # Eintritt 01.03.2027
    k = next(k for k in konten(w["db"], 2027, heute=date(2027, 2, 1)) if k.employee_id == w["Bo"].id)
    assert (k.uebertrag, k.uebertrag_quelle) == (D("0"), "startwert")


def test_austritt_vor_und_am_stichtag(w):
    # ausgetreten 2026: ein Konto 2027 gibt es nur, wenn man danach fragt -- dann ohne Hinweis, wer am 30.12. ging; mit, wer am 31.12. ging
    db = w["db"]
    k = {x.employee_id: x for x in konten(db, 2027, [w["Fe"].id, w["Gus"].id], heute=date(2027, 2, 1))}
    assert k[w["Fe"].id].hinweise == [] and k[w["Gus"].id].hinweise == [OHNE_STARTWERT]


def test_danach_rest_und_meine_zeiten(w):
    db = w["db"]
    assert rest_danach(db, w["Bo"].id, date(2027, 3, 1), date(2027, 3, 5))["text"] == "danach Rest 25 Tage"
    assert rest_danach(db, w["Cem"].id, date(2027, 3, 1), date(2027, 3, 5))["text"] == "danach Rest 25 Tage" + H
    assert meine_zeiten(db, w["Dan"].id, monat=date(2026, 11, 1), heute=date(2026, 11, 10))["urlaub"]["hinweise"] == [ANSPRUCH_PRUEFEN]
    assert meine_zeiten(db, w["Eli"].id, monat=date(2026, 11, 1), heute=date(2026, 11, 10))["urlaub"]["hinweise"] == [OHNE_STARTWERT]
