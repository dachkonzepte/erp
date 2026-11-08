"""Version 1.9.259 (Stufe 6, R5a, Punkt 0): die Kolonne schlägt niemanden mit dem Kennzeichen „Plantafel: nicht zeigen“ mehr vor.

    Vorschlag   app/planning.py::_kolonne_schlaegt_vor() -- beim Anlegen mit Kolonne, beim Wechsel der Kolonne und in der Prüfung des Dialogs; das Kennzeichen
                wie überall (gespeichert, sonst die Vorgabe aus Gruppe und Funktion). Einzeln gewählt kommt die Person weiter in den Einsatz.
    Verwaltung  Stammdaten -> Kolonnen: in der Liste und im Formular steht bei ihr „nicht zeigen“.
Bis 1.9.258 schlug die Kolonne auch sie vor (Festlegung 1.9.253 Nr. 6, zweiter Teil -- von Tobias nicht bestätigt).
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import Employee, EmployeePlanningSettings
from app.planning import create_slot, update_slot
from app.routers.planning import router as planning_router
from tests.test_v090_planning_board import setup_order
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v633_besetzung_je_einsatz import _besetzung, _kolonne, _person

ROOT = Path(__file__).resolve().parent.parent
MO = date(2026, 11, 2)


def _kennzeichen(db, emp, wert):
    db.add(EmployeePlanningSettings(employee_id=emp.id, plantafel=wert))
    db.commit()


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    tom, bea, vera, kai = (_person(db, "M-1", "Tom"), _person(db, "M-2", "Bea"), _person(db, "M-3", "Vera"), _person(db, "M-4", "Kai"))
    _kennzeichen(db, bea, "bauleitung")
    _kennzeichen(db, vera, "nicht_zeigen")
    # ohne Zeile: die Vorgabe aus der Gruppe -- kaufmännisch heißt „nicht zeigen“
    buero = Employee(employee_number="M-5", first_name="Uli", last_name="Test", employee_group="kaufmaennisch", hourly_wage=Decimal("20"),
                     weekly_hours=Decimal("40"), active=True)
    db.add(buero)
    db.commit()
    nord = _kolonne(db, "N", [tom, vera, bea, buero])
    sued = _kolonne(db, "S", [kai, vera])
    return {"db": db, "client": router_test_client(db, planning_router), "tom": tom, "bea": bea, "vera": vera, "kai": kai, "uli": buero,
            "nord": nord, "sued": sued, "auftrag": setup_order(db, "659")}


def test_anlegen_mit_kolonne_ohne_nicht_zeigen(welt):
    slot = create_slot(welt["db"], order_id=welt["auftrag"].id, team_id=welt["nord"].id, start_date=MO, end_date=MO, planned_hours=Decimal("1"))
    assert _besetzung(welt["db"], slot.id) == [welt["tom"].id, welt["bea"].id]  # Vera (gespeichert) und Uli (Vorgabe) fehlen; Bauleitung bleibt


def test_wechsel_der_kolonne_ohne_nicht_zeigen(welt):
    slot = create_slot(welt["db"], order_id=welt["auftrag"].id, team_id=welt["nord"].id, start_date=MO, end_date=MO, planned_hours=Decimal("1"))
    update_slot(welt["db"], slot.id, team_id=welt["sued"].id, trotzdem_planen=True)
    assert _besetzung(welt["db"], slot.id) == [welt["kai"].id]


def test_einzeln_gewaehlt_kommt_sie_weiter_in_den_einsatz(welt):
    slot = create_slot(welt["db"], order_id=welt["auftrag"].id, team_id=welt["nord"].id, start_date=MO, end_date=MO, planned_hours=Decimal("1"),
                       employee_ids=[welt["tom"].id, welt["vera"].id])
    assert _besetzung(welt["db"], slot.id) == [welt["tom"].id, welt["vera"].id]


def test_pruefung_des_dialogs_schlaegt_sie_nicht_vor(welt):
    r = welt["client"].post("/api/planning/slots/pruefen", json={"order_id": welt["auftrag"].id, "team_id": welt["nord"].id, "start_date": MO.isoformat(),
                                                                 "end_date": MO.isoformat(), "planned_hours": "1"})
    assert r.status_code == 200, r.text
    personen = r.json()["personen"]
    assert [(p["name"], p["gewaehlt"], p["vorschlag"]) for p in personen] == [("Tom Test", True, True), ("Bea Test", True, True)]


@nur_mit_node
def test_liste_der_kolonnen_nennt_nicht_zeigen():
    vorbereitung = ("var employees = [{id: 1, plantafel: 'einplanbar'}, {id: 2, plantafel: 'nicht_zeigen'}, {id: 3, plantafel: 'bauleitung'}];"
                    "var AUFRUFE = AUFRUFE || [];")
    [erg] = im_browser("master_data.html", ["plantafelHinweis"], vorbereitung,
                       "AUFRUFE.push([plantafelHinweis(1), plantafelHinweis(2), plantafelHinweis(3), plantafelHinweis(9)]);")
    assert erg == ["", " · nicht zeigen", "", ""]
    liste = (ROOT / "app/templates/master_data.html").read_text(encoding="utf-8")
    assert "${esc(e.employee_name+plantafelHinweis(e.employee_id))}" in liste  # die Liste der Kolonnen ruft ihn je Mitglied auf


def test_formular_der_kolonne_nennt_nicht_zeigen():
    form = (ROOT / "app/templates/master_data_form.html").read_text(encoding="utf-8")
    team_form = form[form.index("function teamForm"):form.index("function teamForm") + 4000]
    assert "${x.plantafel==='nicht_zeigen'?'<span class=\"muted\" title=\"Plantafel: nicht zeigen" in team_form
    assert "> · nicht zeigen</span>':''}" in team_form
