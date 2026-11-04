"""Version 1.9.210 (Lohn L1a, Stufe 5, Punkt 3): jede neue Festlegung bekommt in derselben Runde ihre eigene Gegenprobe -- die Lücke aus Stufe 4.

Genannt waren 1.9.202 Nr. 2 und Nr. 3 (sie haben Tests, aber keine eigene Gegenprobe); die Durchsicht aller Festlegungen von Stufe 4 fand dazu
Aussagen ohne Test, die eine Gegenprobe grün ließe -- hier geprüft:

    1.9.202 Nr. 1  beim Genehmigen gelten die Rückfragen des Dialogs nicht (gebuchte Zeit, betriebsfreier Tag) -- auch unter „Zeiten“
    1.9.204 Nr. 1  „schon abwesend“ ist ein abgelehnter Tag (422) und kommt vor der Rückfrage zu gebuchter Zeit (409)
    1.9.204 Nr. 3  je Person ein Grund: erst die Gründe des Tags (grund_gegen()), dann abwesend, dann offener Antrag

Die Tabelle aller Gegenproben dieser Runde: docs/archiv/gegenproben-lohn-l1a.md, Abschnitt „Stufe 4 und 5“. Feste Tage wie
tests/test_v588_schlechtwetter.py: Mo 07.12.2026.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.absence_requests import belegt, create_request, review_request
from app.models import EmployeeAbsenceRequest, PlanningHoliday
from app.sollzeit import zeile_anlegen
from tests.test_v588_schlechtwetter import MO, _abwesenheiten, _als, _eintragen, welt  # noqa: F401  (Fixture)
from tests.test_v605_festlegungen_170_173 import _buchung


def _antrag_von_tom(w) -> int:
    assert _eintragen(_als(w, "field", "tom"), w["tom"]).status_code == 200
    return w["db"].scalar(select(EmployeeAbsenceRequest.id))


def _genehmigt(w, emp, tag=MO, kategorie="urlaub"):
    db = w["db"]
    review_request(db, create_request(db, employee_id=emp.id, absence_category=kategorie, start_date=tag, end_date=tag).id,
                   decision="approved", reviewed_by_user_id=None)


# --- 1.9.202 Nr. 1 ------------------------------------------------------------------------------------------------------------------------

def test_unter_zeiten_genehmigt_trotz_gebuchter_zeit(welt):  # noqa: F811
    """Tom bucht nach seinem Antrag Zeit am Montag: der Admin genehmigt unter „Zeiten“ ohne Rückfrage (die Rückfrage gilt nur beim Eintragen)."""
    antrag = _antrag_von_tom(welt)
    _buchung(welt, welt["tom"])
    r = _als(welt).post(f"/api/absence-requests/{antrag}/review", json={"decision": "approved"})
    assert (r.status_code, r.json()["status"]) == (200, "approved"), r.text
    assert _abwesenheiten(welt) == [(welt["tom"].id, MO, MO, "schlechtwetter", "Schlechtwetter")]


def test_unter_zeiten_genehmigt_am_betriebsfreien_tag(welt):  # noqa: F811
    antrag = _antrag_von_tom(welt)
    welt["db"].add(PlanningHoliday(holiday_date=MO, name="Betriebsausflug", active=True))
    welt["db"].commit()
    r = _als(welt).post(f"/api/absence-requests/{antrag}/review", json={"decision": "approved"})
    assert (r.status_code, r.json()["status"]) == (200, "approved"), r.text


# --- 1.9.204 Nr. 1 ------------------------------------------------------------------------------------------------------------------------

def test_schon_abwesend_vor_der_rueckfrage(welt):  # noqa: F811
    """Mia ist am Montag schon abwesend und hat dort Zeit gebucht, Tom hat nur Zeit gebucht: 422 mit Mia -- keine Rückfrage (409) zuerst."""
    _genehmigt(welt, welt["mia"])
    _buchung(welt, welt["mia"])
    _buchung(welt, welt["tom"])
    r = _eintragen(_als(welt), welt["mia"], welt["tom"])
    assert r.status_code == 422, r.text
    assert [x["text"] for x in r.json()["liste"]] == ["Mia Monteurin: am 07.12.2026 bereits abwesend"]
    assert "warnungen" not in r.json()


# --- 1.9.204 Nr. 3 ------------------------------------------------------------------------------------------------------------------------

def test_erst_der_grund_des_tags(welt):  # noqa: F811
    """Mia hat montags keine Sollzeit und ist dort trotzdem als abwesend eingetragen: genannt wird nur „keine Sollzeit“."""
    _genehmigt(welt, welt["mia"])
    zeile_anlegen(welt["db"], welt["mia"].id, date(2026, 12, 1), {"dienstag": Decimal("4")})
    r = _eintragen(_als(welt), welt["mia"])
    assert [x["text"] for x in r.json()["liste"]] == ["Mia Monteurin: am 07.12.2026 keine Sollzeit"], r.text


def test_erst_abwesend_dann_offener_antrag(welt):  # noqa: F811
    """Altbestand: eine genehmigte Abwesenheit und ein offener Antrag am selben Tag (heute nicht mehr anzulegen) -- belegt() nennt die
    Abwesenheit."""
    db = welt["db"]
    _genehmigt(welt, welt["mia"])
    db.add(EmployeeAbsenceRequest(employee_id=welt["mia"].id, absence_type="Krankheit", absence_category="krankheit", start_date=MO, end_date=MO,
                                  status="pending"))
    db.commit()
    assert belegt(db, welt["mia"].id, MO, MO) == "am 07.12.2026 bereits abwesend"
