"""Version 1.9.223 (Lohn L1b, Vorgabe Tobias): die Arbeit eines Tags im Lohn kaufmännisch auf 0,25 h.

    gerundet     je Person und Tag die gebuchten Stunden (nach der Pause, alle Zeitarten zusammen) -- app/time_tracking.py::arbeit_des_tags(),
                 über app/rounding.py::round_quarter_hours(); der Monat ist die Summe der gerundeten Tage (arbeit_im_lohn())
    nicht        je Buchung, je Zeitart oder je Monat; die Buchungen selbst bleiben minutengenau
    wo           „Monat & Lohn“ (Zusammen), Schlechtwetter (Sollzeit − Arbeit); Stundenzettel, Übersicht und die Spalten je Zeitart bleiben
                 minutengenau

Feste Tage: Mo 07.12. bis Do 10.12.2026 (KW 50, Tarif 7,50 h). Beispiel: Mo 4,10 h Baustelle + 4,10 h Werkstatt = 8,20 -> 8,25 (je Buchung
gerundet wären es 8,00); Di, Mi, Do je 0,10 h -> je 0,00. Arbeit im Lohn 8,25 -- minutengenau wären es 8,50, der Monat gerundet auch 8,50.
"""

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import EmployeeAbsence, TimeEntry
from app.rounding import round_quarter_hours
from app.schlechtwetter import ausfall
from app.time_backoffice import backoffice_summary
from app.time_tracking import arbeit_des_tags, arbeit_im_lohn
from app.zeiten import monat
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote

MO, DI, MI, DO = date(2026, 12, 7), date(2026, 12, 8), date(2026, 12, 9), date(2026, 12, 10)
D = Decimal


@pytest.mark.parametrize("wert, erwartet", [
    ("8.1667", "8.25"), ("8.125", "8.25"), ("8.12", "8.00"), ("0.10", "0.00"), ("0.125", "0.25"), ("9.13", "9.25"),
    ("7.875", "8.00"), ("7.874", "7.75"), ("0.625", "0.75"), (0.625, "0.75"), ("0", "0.00"), (None, "0.00"),
])
def test_viertelstunde_kaufmaennisch(wert, erwartet):
    """Die Hälfte rundet auf (0,625 -> 0,75; halb-gerade gäbe 0,50), Ergebnis mit zwei Stellen."""
    assert str(round_quarter_hours(wert)) == erwartet


@pytest.fixture
def welt(db_session, fester_tag):
    db = db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0625"))
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "order": order}


def _buchen(w, emp, stunden, tag, art="site", status="booked", ab=7):
    o = w["order"]
    w["db"].add(TimeEntry(employee_id=emp.id, project_id=o.project_id, order_id=o.id, work_date=tag, entry_type=art, hours=D(stunden),
                          break_minutes=0, status=status, started_at=datetime.combine(tag, time(ab)),
                          ended_at=None if status == "running" else datetime.combine(tag, time(ab + 1))))
    w["db"].commit()


def _beispiel(w, emp):
    _buchen(w, emp, "4.10", MO)
    _buchen(w, emp, "4.10", MO, art="workshop", ab=12)
    for tag in (DI, MI, DO):
        _buchen(w, emp, "0.10", tag)


def _zeilen(w, emp):
    return w["db"].query(TimeEntry).filter(TimeEntry.employee_id == emp.id).all()


def test_arbeit_des_tags_alle_zeitarten_zusammen(welt):
    """Nicht je Buchung (4,00 + 4,00) und nicht je Zeitart; eine laufende Zeit zählt nicht."""
    _beispiel(welt, welt["mia"])
    _buchen(welt, welt["mia"], "3", MO, status="running", ab=17)
    mo = [r for r in _zeilen(welt, welt["mia"]) if r.work_date == MO]
    assert arbeit_des_tags(mo) == D("8.25")


def test_monat_ist_die_summe_der_gerundeten_tage(welt):
    """8,25 + 0 + 0 + 0 -- nicht der gerundete Monat (8,50), nicht minutengenau (8,50), nicht je Buchung (8,00)."""
    _beispiel(welt, welt["mia"])
    _beispiel(welt, welt["tom"])
    assert arbeit_im_lohn(_zeilen(welt, welt["mia"])) == D("8.25")
    assert arbeit_im_lohn(welt["db"].query(TimeEntry).all()) == D("16.50")  # je Person und Tag, nicht je Tag über alle


def test_buchungen_bleiben_minutengenau(welt):
    _beispiel(welt, welt["mia"])
    monat(welt["db"], date(2026, 12, 1))
    assert sorted(str(r.hours) for r in _zeilen(welt, welt["mia"])) == ["0.1000", "0.1000", "0.1000", "4.1000", "4.1000"]


def test_monat_und_lohn_zusammen_gerundet_spalten_minutengenau(welt):
    _beispiel(welt, welt["mia"])
    d = monat(welt["db"], date(2026, 12, 1))
    z = next(x for x in d["zeilen"] if x["employee_id"] == welt["mia"].id)
    assert (z["zusammen"], z["stunden"]["site"], z["stunden"]["workshop"], z["tage"]) == (D("8.25"), D("4.40"), D("4.10"), 4)
    assert (d["summe"]["zusammen"], d["summe"]["stunden"]["site"]) == (D("8.25"), D("4.40"))


def test_schlechtwetter_rechnet_mit_der_gerundeten_arbeit(welt):
    """Sollzeit 7,50 − Arbeit 2,10 h gebucht = 2,00 im Lohn -> Ausfall 5,50 (minutengenau wären es 5,40)."""
    db = welt["db"]
    db.add(EmployeeAbsence(employee_id=welt["mia"].id, absence_type="Schlechtwetter", absence_category="schlechtwetter", start_date=MO,
                           end_date=MO))
    _buchen(welt, welt["mia"], "2.10", MO)
    a = ausfall(db, [(welt["mia"].id, MO)])[(welt["mia"].id, MO)]
    assert (a["gebucht"], a["stunden"], a["text"]) == (D("2.00"), D("5.50"), "Ausfall 5,50 h (Sollzeit 7,50 h − gebucht 2,00 h)")
    z = next(x for x in monat(db, date(2026, 12, 1))["zeilen"] if x["employee_id"] == welt["mia"].id)
    assert (z["zusammen"], z["schlechtwetter"]["stunden"]) == (D("2.00"), D("5.50"))


def test_uebersicht_bleibt_minutengenau(welt):
    """Die Übersicht (wie der Stundenzettel) zählt die Buchungen, nicht die Arbeit im Lohn."""
    _beispiel(welt, welt["mia"])
    s = backoffice_summary(welt["db"], date(2026, 12, 1), date(2026, 12, 31))
    assert (s["total_hours"], s["employees"][0]["hours"]) == (D("8.50"), D("8.50"))


def test_seite_nennt_die_rundung():
    text = (Path(__file__).resolve().parent.parent / "app" / "templates" / "zeiten.html").read_text(encoding="utf-8")
    assert "„Zusammen“ ist die Arbeit für den Lohn, je Tag auf 0,25 h gerundet" in text
    assert 'title="Arbeit für den Lohn: je Tag auf 0,25 h gerundet">Zusammen</th>' in text
