"""Version 1.9.243 (Stufe 6, R4, Punkt 0a): „Nächste Tage“ -- wer an einem Tag der Zeile abwesend ist, fehlt dort im „mit …“.

    je Tag     der Zusatz „mit <Vornamen>“ gilt je Tag: wer an dem Tag abwesend ist (genehmigt oder Freistellung des Arbeitszeitkalenders, dieselbe
               Regel wie „ist nicht da“ auf der Karte), fehlt; ein offener Antrag zählt nicht als abwesend
    Zeile      die Zeile teilt sich, wo sich der Zusatz ändert; ohne andere Person bleibt „vorläufig“ bzw. der Titel des Auftrags
    Art        die Art der Abwesenheit einer anderen Person steht nirgends in der Antwort
"""

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app.heute import heute_fuer
from app.models import EmployeeAbsence, EmployeeAbsenceRequest
from app.planning import create_slot
from app.sollzeit import zeile_anlegen
from tests.test_v090_planning_board import setup_order
from tests.test_v633_besetzung_je_einsatz import _kolonne, _person

DI = date(2026, 11, 10)  # FESTER_TAG: Dienstag
D = Decimal


@pytest.fixture()
def welt(threaded_db_session, fester_tag):
    db = threaded_db_session
    mia, ole, tom = _person(db, "M-1", "Mia"), _person(db, "M-2", "Ole"), _person(db, "M-3", "Tom")
    return {"db": db, "mia": mia, "ole": ole, "tom": tom, "order": setup_order(db, "1"), "nord": _kolonne(db, "N", [mia, ole, tom])}


def _zeilen(w, heute=DI):
    h = heute_fuer(w["db"], w["mia"].id, heute=heute, jetzt=datetime.combine(heute, time(10)), ist_monteur=True)
    return h, [(z["von"], z["bis"], z["nebentext"]) for z in h["naechste_tage"] if z["art"] == "einsatz"]


def _einsatz(w, von, bis, **mehr):
    return create_slot(w["db"], **{"order_id": w["order"].id, "team_id": w["nord"].id, "start_date": von, "end_date": bis,
                                   "planned_hours": D("1"), "trotzdem_planen": True, **mehr})


def tag(n):
    return DI + timedelta(days=n)


def test_abwesend_an_einem_tag_fehlt_dort_und_die_zeile_teilt_sich(welt):
    db = welt["db"]
    _einsatz(welt, tag(1), tag(3))  # Mi 11. bis Fr 13., beginnt morgen
    db.add(EmployeeAbsence(employee_id=welt["tom"].id, absence_type="Krankheit", absence_category="krankheit", start_date=tag(2), end_date=tag(2)))
    db.commit()
    h, zeilen = _zeilen(welt)
    assert zeilen == [(tag(1), tag(1), "mit Ole, Tom · vorläufig"), (tag(2), tag(2), "mit Ole · vorläufig"), (tag(3), tag(3), "mit Ole, Tom · vorläufig")]
    assert "Krankheit" not in json.dumps(h, default=str)  # die Art einer anderen Person steht nirgends


def test_ohne_abwesenheit_eine_zeile(welt):
    _einsatz(welt, tag(1), tag(3), status="fest")
    assert _zeilen(welt)[1] == [(tag(1), tag(3), "mit Ole, Tom")]


def test_offener_antrag_zaehlt_nicht(welt):
    db = welt["db"]
    _einsatz(welt, tag(1), tag(3))
    db.add(EmployeeAbsenceRequest(employee_id=welt["tom"].id, absence_type="Urlaub", absence_category="urlaub", start_date=tag(2), end_date=tag(2),
                                  status="pending"))
    db.commit()
    assert _zeilen(welt)[1] == [(tag(1), tag(3), "mit Ole, Tom · vorläufig")]


def test_alle_anderen_weg_ohne_mit(welt):
    db = welt["db"]
    _einsatz(welt, tag(1), tag(2), status="fest")
    for p in (welt["ole"], welt["tom"]):
        db.add(EmployeeAbsence(employee_id=p.id, absence_type="Urlaub", absence_category="urlaub", start_date=tag(2), end_date=tag(2)))
    db.commit()
    titel = welt["order"].title or welt["order"].order_number
    assert _zeilen(welt)[1] == [(tag(1), tag(1), "mit Ole, Tom"), (tag(2), tag(2), titel)]


def test_freistellung_des_arbeitszeitkalenders_fehlt_wie_abwesend(welt):
    """Heiligabend (Do 24.12.2026): Ole und Tom sind freigestellt; Mia hat am Donnerstag keine Sollzeit -- für sie ist es ein Arbeitstag."""
    db = welt["db"]
    zeile_anlegen(db, welt["mia"].id, date(2026, 12, 1), {"montag": D("8"), "dienstag": D("8"), "mittwoch": D("8"), "freitag": D("8")})
    montag = date(2026, 12, 21)
    _einsatz(welt, montag + timedelta(days=1), montag + timedelta(days=3), status="fest")  # Di 22. bis Do 24.
    _h, zeilen = _zeilen(welt, heute=montag)
    titel = welt["order"].title or welt["order"].order_number
    assert zeilen == [(montag + timedelta(days=1), montag + timedelta(days=2), "mit Ole, Tom"), (montag + timedelta(days=3), montag + timedelta(days=3), titel)]


def test_weiter_bleibt_weiter(welt):
    """Läuft der Einsatz heute schon, heißt jeder weitere Tag „weiter“ -- dort stehen keine Namen, eine Abwesenheit teilt nichts."""
    db = welt["db"]
    _einsatz(welt, DI, tag(3))
    db.add(EmployeeAbsence(employee_id=welt["tom"].id, absence_type="Urlaub", absence_category="urlaub", start_date=tag(2), end_date=tag(2)))
    db.commit()
    assert _zeilen(welt)[1] == [(tag(1), tag(3), "weiter")]
