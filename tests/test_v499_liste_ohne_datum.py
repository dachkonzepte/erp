"""Seit 1.9.76 (Stufe 4, R4 Nachtrag 2, Punkt 1): Aufträge, denen die Monteurin an der Arbeitsvorbereitung ohne Datum zugeordnet ist, stehen in
ihrer Liste -- für „Zeit nachtragen“, „Heute“ und das Anlegen eines Berichts gleich (eine Funktion: list_field_bookable_orders()).

    ohne Datum      zugeordnet (einzeln oder über die Kolonne), die Arbeitsvorbereitung ohne Abschnitt der Plantafel und ohne geplanten
                    Zeitraum -> in der Liste, Bericht und Nachtrag gehen (bis 1.9.75 nicht in der Liste, seit 1.9.74 kein Bericht)
    draußen         nie zugeordnet (Nachtrag 403), abgeschlossen oder storniert (auch ohne Datum), datiert außerhalb der 14 Tage -- einen
                    Bericht legt sie seit 1.9.79 trotzdem zu jedem nicht stornierten an (test_v502)
    unverändert     „Wartungen an meinen Objekten“ (list_field_relevant_property_ids()) nimmt ein Objekt ohne Datum weiter nicht auf
"""

from datetime import timedelta

import pytest

from app import berlin_time
from app.models import Property, WorkPreparation, WorkPreparationEmployee, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee
from app.planning import list_field_bookable_orders, list_field_relevant_property_ids
from app.routers import field_view as field_view_router
from app.routers import service_reports as service_reports_router
from app.routers import time_tracking as time_tracking_router
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import _einsatz


def _ohne_datum(db, order, emp, *, team=None):
    prep = WorkPreparation(order_id=order.id, status="offen")
    db.add(prep); db.flush()
    if team is None:
        db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=emp.id))
    else:
        zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
        db.add(zuordnung); db.flush()
        db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=emp.id, employee_name_snapshot=emp.first_name))
    db.commit()


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    heute = berlin_time.berlin_today()
    mia = make_employee(db, "M-499", "Mia", "Monteurin")
    namen = ("einzeln", "kolonne", "fremd", "abgeschlossen", "storniert", "alt")
    auftraege = {n: beauftragen(db, make_quote(db, is_consumer=False, number=f"0499{i}")) for i, n in enumerate(namen)}
    w = {"db": db, "heute": heute, "mia": mia, "team": make_team(db, "K-499", "Kolonne 499"), "auftraege": auftraege,
         "client": router_test_client}
    halle = Property(customer_id=auftraege["einzeln"].project.customer_id, name="Halle 499")  # ein Objekt für den Wächter unten
    db.add(halle); db.flush()
    auftraege["einzeln"].project.property_id = halle.id
    _ohne_datum(db, auftraege["einzeln"], mia)
    _ohne_datum(db, auftraege["kolonne"], mia, team=w["team"])
    for n in ("abgeschlossen", "storniert"):
        _ohne_datum(db, auftraege[n], mia)
        auftraege[n].status = n
    _einsatz(w, auftraege["alt"], [(heute - timedelta(days=40), heute - timedelta(days=40))], [mia])  # datiert, außerhalb der 14 Tage
    db.commit()
    w["als_mia"] = router_test_client(db, time_tracking_router.router, field_view_router.router, service_reports_router.router,
                                      role="field", employee_id=mia.id)
    return w


def _ids(w, *namen):
    return {w["auftraege"][n].id for n in namen}


def _bericht(w, name):
    return w["als_mia"].post(f"/api/orders/{w['auftraege'][name].id}/service-reports", json={"report_type": "rapport"})


def _nachtrag(w, name):
    return w["als_mia"].post("/api/time-entries", json={"employee_id": w["mia"].id, "order_id": w["auftraege"][name].id,
                                                        "work_date": w["heute"].isoformat(), "von": "07:00", "bis": "09:00"})


def test_ohne_datum_in_der_liste_an_allen_stellen(welt):
    """Angriff: einzeln und über die Kolonne ohne Datum zugeordnet -> in der Liste von „Zeit nachtragen“, „Heute“ und der Auswahl der
    Zeiterfassung; abgeschlossen, storniert, außerhalb der 14 Tage und nie zugeordnet nicht."""
    soll = _ids(welt, "einzeln", "kolonne")
    assert {o["id"] for o in list_field_bookable_orders(welt["db"], welt["mia"].id)} == soll
    client = welt["als_mia"]
    assert {o["id"] for o in client.get("/api/field-view/time-tracking/orders").json()} == soll
    assert {o["id"] for o in client.get("/api/field-view/meine-zeiten").json()["auftraege"]} == soll
    assert {o["id"] for o in client.get("/api/field-view/today").json()["heute"]["auftraege"]} == soll


@pytest.mark.parametrize("name", ["einzeln", "kolonne"])
def test_ohne_datum_bericht_und_nachtrag_gehen(welt, name):
    bericht = _bericht(welt, name)
    assert bericht.status_code == 200, bericht.text
    nachtrag = _nachtrag(welt, name)
    assert nachtrag.status_code == 200, nachtrag.text


def test_nie_zugeordnet_kein_nachtrag(welt):
    """Gegenprobe: nie zugeordnet -> Nachtrag 403 wie bisher; einen Bericht legt sie seit 1.9.79 an (1.9.74–1.9.78: 403)."""
    assert _nachtrag(welt, "fremd").status_code == 403
    assert _bericht(welt, "fremd").status_code == 200


@pytest.mark.parametrize("name", ["abgeschlossen", "storniert", "alt"])
def test_abgeschlossen_storniert_und_alt_nicht_in_der_liste(welt, name):
    """Nicht in der Liste; einen Bericht legt sie seit 1.9.79 trotzdem an -- außer zum stornierten (1.9.74–1.9.78: alle drei 403)."""
    assert welt["auftraege"][name].id not in {o["id"] for o in list_field_bookable_orders(welt["db"], welt["mia"].id)}
    assert _bericht(welt, name).status_code == (409 if name == "storniert" else 200)  # seit 1.9.124 409 (bis dahin 403)


def test_wartungen_an_meinen_objekten_unveraendert(welt):
    """Die Liste der Objekte für „Wartungen an meinen Objekten“ (eigenes Zeitfenster, seit 1.3.58) nimmt nichts ohne Datum auf."""
    assert list_field_relevant_property_ids(welt["db"], welt["mia"].id) == set()
