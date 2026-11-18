"""Version 1.9.370 (Nachrunde Urlaub, Punkt 1): Hinweis am Vorschlag, wenn er unter dem gesetzlichen Mindesturlaub liegt.

    Regel     app/urlaubskonto.py::mindesturlaub_fuer() (eine Stelle): Austritt in der zweiten Jahreshälfte (ab dem 01.07.) nach erfüllter Wartezeit
              (mindestens sechs volle Monate ab dem Eintritt; ohne Eintritt erfüllt) -- Mindesturlaub = Arbeitstage je Woche × 4 (mindesturlaub(); die Tage
              mit Sollzeit in den sieben Tagen bis zum Austritt)
    Hinweis   liegt der Vorschlag darunter: „Vorschlag liegt unter dem gesetzlichen Mindesturlaub (20 Tage) – prüfen“ -- nur Hinweis, nichts von selbst
"""

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import EmployeePayrollSettings, EmployeeTargetHours, LohnStartwert, Urlaubsanspruch
from app.urlaubskonto import mindesturlaub, konten
from tests.test_v224_field_view import make_employee

D = Decimal
ROOT = Path(__file__).resolve().parent.parent
HINWEIS = "Vorschlag liegt unter dem gesetzlichen Mindesturlaub ({} Tage) – prüfen"


@pytest.fixture
def db(threaded_db_session, fester_tag):
    return threaded_db_session


def _person(db, nummer, eintritt, austritt, anspruch=None, teilzeit=False):
    e = make_employee(db, nummer, "Pia", f"Probe{nummer}")
    db.add(EmployeePayrollSettings(employee_id=e.id, eintritt=eintritt, austritt=austritt))
    db.add(LohnStartwert(employee_id=e.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("0"), saldo_stunden=D("0"), herkunft="steuerbuero"))
    if anspruch is not None:
        db.add(Urlaubsanspruch(employee_id=e.id, jahr=2027, urlaubstage=D(anspruch)))
    if teilzeit:  # Mo–Mi je 8 h, Do–So frei
        db.add(EmployeeTargetHours(employee_id=e.id, valid_from=date(2020, 1, 1), montag=D("8"), dienstag=D("8"), mittwoch=D("8"), donnerstag=D("0"),
                                   freitag=D("0"), samstag=D("0"), sonntag=D("0")))
    db.commit()
    return konten(db, 2027, [e.id], heute=date(2027, 2, 10))[0]


def test_regel():
    assert (mindesturlaub(5), mindesturlaub(3), mindesturlaub(6), mindesturlaub(0)) == (D("20"), D("12"), D("24"), D("0"))


def test_austritt_in_der_zweiten_haelfte_unter_dem_mindesturlaub(db):
    k = _person(db, "M-1", date(2019, 4, 1), date(2027, 8, 31), anspruch="26")  # 26 ÷ 12 × 8 = 17,3 → 17,5 < 20
    assert (k.anteilig["vorschlag"], k.anteilig["mindesturlaub"]) == (D("17.5"), D("20"))
    assert HINWEIS.format("20") in k.hinweise and k.anspruch == D("26")  # nichts von selbst
    assert konten(db, 2027, [k.employee_id], heute=date(2027, 2, 10))[0].anspruch == D("26")  # auch nicht beim nächsten Lesen


def test_nicht_darunter_kein_hinweis(db):
    k = _person(db, "M-2", date(2019, 4, 1), date(2027, 8, 31))  # Vorgabe 30: 30 ÷ 12 × 8 = 20 -- nicht darunter
    assert (k.anteilig["vorschlag"], k.anteilig["mindesturlaub"]) == (D("20"), None)
    assert not any("Mindesturlaub" in h for h in k.hinweise)


def test_austritt_in_der_ersten_haelfte_kein_hinweis(db):
    k = _person(db, "M-3", date(2019, 4, 1), date(2027, 6, 30), anspruch="26")  # 26 ÷ 12 × 6 = 13 -- erste Hälfte: Teilurlaub
    assert k.anteilig["vorschlag"] == D("13") and not any("Mindesturlaub" in h for h in k.hinweise)
    k = _person(db, "M-4", date(2019, 4, 1), date(2027, 7, 1), anspruch="26")  # am 01.07. zweite Hälfte
    assert HINWEIS.format("20") in k.hinweise


def test_wartezeit(db):
    k = _person(db, "M-5", date(2027, 3, 1), date(2027, 8, 31), anspruch="26")  # 6 volle Monate: erfüllt; 26 ÷ 12 × 6 = 13
    assert HINWEIS.format("20") in k.hinweise
    k = _person(db, "M-6", date(2027, 3, 15), date(2027, 8, 31), anspruch="26")  # 5 volle Monate: nicht erfüllt
    assert not any("Mindesturlaub" in h for h in k.hinweise)
    k = _person(db, "M-7", None, date(2027, 8, 31), anspruch="26")  # ohne Eintritt: erfüllt
    assert HINWEIS.format("20") in k.hinweise


def test_teilzeit_nach_den_eigenen_arbeitstagen(db):
    k = _person(db, "M-8", date(2019, 4, 1), date(2027, 9, 30), anspruch="12", teilzeit=True)  # 12 ÷ 12 × 9 = 9 < 3 × 4 = 12
    assert (k.anteilig["mindesturlaub"], HINWEIS.format("12") in k.hinweise) == (D("12"), True)
    k = _person(db, "M-9", date(2019, 4, 1), date(2027, 9, 30), anspruch="18", teilzeit=True)  # 13,5 ≥ 12
    assert not any("Mindesturlaub" in h for h in k.hinweise)


def test_auch_nach_dem_uebernehmen(db):
    from app.lohnkonten import anteilig_uebernehmen
    k = _person(db, "M-10", date(2019, 4, 1), date(2027, 8, 31), anspruch="26")
    d = anteilig_uebernehmen(db, k.employee_id, 2027, "17.5")
    assert d["anspruch"] == D("17.5") and HINWEIS.format("20") in d["hinweise"]  # der Hinweis bleibt am übernommenen Vorschlag


def test_eine_stelle():
    """Die Regel steht nur in app/urlaubskonto.py: konten() nimmt mindesturlaub_fuer(), dieses mindesturlaub() und volle_monate()."""
    baum = ast.parse((ROOT / "app" / "urlaubskonto.py").read_text(encoding="utf-8"))

    def aufrufe(name):
        f = next(n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef) and n.name == name)
        return {getattr(c.func, "id", getattr(c.func, "attr", "")) for c in ast.walk(f) if isinstance(c, ast.Call)}
    assert "mindesturlaub_fuer" in aufrufe("konten") and {"mindesturlaub", "volle_monate"} <= aufrufe("mindesturlaub_fuer")
    andere = [p.name for p in (ROOT / "app").rglob("*.py") if p.name != "urlaubskonto.py" and "def mindesturlaub" in p.read_text(encoding="utf-8")]
    assert andere == []
