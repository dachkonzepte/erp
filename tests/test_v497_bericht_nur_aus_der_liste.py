"""Seit 1.9.74 (Stufe 4, R4 Nachtrag, Punkt 2): die Monteurin legt einen Bericht nur für einen Auftrag ihrer Liste an.

    Liste      app/planning.py::list_field_bookable_orders() -- dieselbe Liste wie „Zeit nachtragen“ in „Meine Zeiten“: Aufträge, die in den
               letzten oder nächsten 14 Tagen für sie eingeplant sind (Abschnitt der Plantafel oder Datum der Arbeitsvorbereitung),
               Aufträge mit einem eigenen Bericht und seit 1.9.76 solche, denen sie ohne Datum zugeordnet ist (test_v499); ohne
               abgeschlossene und stornierte
    Regel      POST /api/orders/{id}/service-reports als Monteurin nur, wenn field_order_in_list() den Auftrag in dieser Liste findet --
               eine Regel für Liste und Prüfung, sonst 403 (BERICHT_NUR_EIGENE_AUFTRAEGE); auch ohne heutigen Einsatz
    bis 1.9.73 jeder Auftrag, auf den sie zugreifen darf (require_field_order_access(): Zuordnung an der Arbeitsvorbereitung auch ohne Datum,
               eigener Bericht) -- auch abgeschlossene und solche, die sie in keiner Auswahl findet
Das Büro legt weiter für jeden Auftrag an.
"""

import ast
import inspect
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app import berlin_time, planning
from app.meldungen import BERICHT_NUR_EIGENE_AUFTRAEGE, KEIN_MITARBEITER
from app.models import ServiceReport, WorkPreparation, WorkPreparationEmployee
from app.routers import field_view as field_view_router
from app.routers import service_reports as service_reports_router
from app.service_reports import create_report
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import _einsatz


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    heute = berlin_time.berlin_today()
    mia = make_employee(db, "M-497", "Mia", "Monteurin")
    auftraege = {name: beauftragen(db, make_quote(db, is_consumer=False, number=f"0497{i}"))
                 for i, name in enumerate(("gestern", "ohne_datum", "alt", "fremd", "abgeschlossen", "eigener_bericht", "heute"))}
    w = {"db": db, "heute": heute, "mia": mia, "team": make_team(db, "K-497", "Kolonne 497"), "auftraege": auftraege,
         "client": router_test_client}
    _einsatz(w, auftraege["gestern"], [(heute - timedelta(days=1), heute - timedelta(days=1))], [mia])  # kein Einsatz heute
    _einsatz(w, auftraege["heute"], [(heute, heute)], [mia])
    _einsatz(w, auftraege["alt"], [(heute - timedelta(days=30), heute - timedelta(days=30))], [mia])  # außerhalb der 14 Tage
    _einsatz(w, auftraege["abgeschlossen"], [(heute, heute)], [mia])
    auftraege["abgeschlossen"].status = "abgeschlossen"
    prep = WorkPreparation(order_id=auftraege["ohne_datum"].id, status="offen")  # zugeordnet, aber ohne jedes Datum
    db.add(prep); db.flush()
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia.id))
    db.commit()
    create_report(db, auftraege["eigener_bericht"].id, "rapport", "Notdienst", created_by_employee_id=mia.id)  # ohne Plantafel
    return w


def _als_monteurin(w, employee_id="mia"):
    eid = w["mia"].id if employee_id == "mia" else employee_id
    return w["client"](w["db"], service_reports_router.router, field_view_router.router, role="field", employee_id=eid)


def _anlegen(client, order_id):
    return client.post(f"/api/orders/{order_id}/service-reports", json={"report_type": "rapport", "description": "Notdienst"})


def _berichte(w, order_id):
    return w["db"].scalar(select(func.count()).select_from(ServiceReport).where(ServiceReport.order_id == order_id))


def test_ohne_heutigen_einsatz_fuer_einen_auftrag_der_liste_angelegt(welt):
    """Angriff: gestern eingeplant, heute kein Einsatz -- der Auftrag steht in der Liste, der Bericht entsteht und gehört der Monteurin."""
    order = welt["auftraege"]["gestern"]
    antwort = _anlegen(_als_monteurin(welt), order.id)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["created_by_employee_id"] == welt["mia"].id and antwort.json()["order_id"] == order.id


@pytest.mark.parametrize("name", ["alt", "fremd", "abgeschlossen"])
def test_auftrag_ausserhalb_der_liste_403_und_nichts_angelegt(welt, name):
    """Angriff direkt über die API: vor 30 Tagen eingeplant, nie zugeordnet, abgeschlossen -- 403 mit der Meldung, kein Bericht.
    „abgeschlossen“ ging bis 1.9.73 durch; „ohne_datum“ (zugeordnet ohne Datum) war 1.9.74–1.9.75 hier, seit 1.9.76 steht er in der Liste."""
    order = welt["auftraege"][name]
    antwort = _anlegen(_als_monteurin(welt), order.id)
    assert antwort.status_code == 403 and antwort.json()["detail"] == BERICHT_NUR_EIGENE_AUFTRAEGE
    assert _berichte(welt, order.id) == 0


def test_eigener_bericht_genuegt(welt):
    """Gegenprobe: ein Auftrag ohne Plantafel, aber mit eigenem Bericht steht in der Liste -- ein zweiter Bericht entsteht."""
    order = welt["auftraege"]["eigener_bericht"]
    assert _anlegen(_als_monteurin(welt), order.id).status_code == 200
    assert _berichte(welt, order.id) == 2


def test_liste_und_pruefung_sind_eine_regel(welt):
    """Für jeden Auftrag: in der Liste (GET …/time-tracking/orders, ebenso „Meine Zeiten“) genau dann, wenn das Anlegen gelingt."""
    client = _als_monteurin(welt)
    liste = {o["id"] for o in client.get("/api/field-view/time-tracking/orders").json()}
    assert liste == {o["id"] for o in client.get("/api/field-view/meine-zeiten").json()["auftraege"]}
    angelegt = {order.id for order in welt["auftraege"].values() if _anlegen(client, order.id).status_code == 200}
    assert angelegt == liste == {welt["auftraege"][n].id for n in ("gestern", "heute", "eigener_bericht", "ohne_datum")}


def test_buero_legt_fuer_jeden_auftrag_an(welt):
    buero = welt["client"](welt["db"], service_reports_router.router)
    for name in ("fremd", "abgeschlossen", "ohne_datum"):
        assert _anlegen(buero, welt["auftraege"][name].id).status_code == 200, name


def test_konto_ohne_mitarbeiter_403(welt):
    client = welt["client"](welt["db"], service_reports_router.router, role="field", employee_id=None)
    antwort = _anlegen(client, welt["auftraege"]["heute"].id)
    assert antwort.status_code == 403 and antwort.json()["detail"] == KEIN_MITARBEITER


def _aufrufe(funktion) -> set[str]:
    baum = ast.parse(inspect.getsource(funktion).lstrip())
    return {n.func.id if isinstance(n.func, ast.Name) else n.func.attr for n in ast.walk(baum) if isinstance(n, ast.Call)
            and isinstance(n.func, (ast.Name, ast.Attribute))}


def test_eine_stelle():
    """Die Regel steht an einer Stelle: das Anlegen fragt field_order_in_list(), und die liest genau list_field_bookable_orders() -- die
    Liste von „Zeit nachtragen“; die alte Prüfung (require_field_order_access) steht im Anlegen nicht mehr."""
    anlegen = _aufrufe(service_reports_router.post_service_report)
    assert "field_order_in_list" in anlegen and "require_field_order_access" not in anlegen
    assert "list_field_bookable_orders" in _aufrufe(planning.field_order_in_list)
