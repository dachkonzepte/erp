"""Seit 1.9.79 (Stufe 4, R4 Nachtrag 3, Entscheidung A): die Monteurin legt zu jedem Auftrag einen Bericht an -- eingeplant oder nicht, auch
abgeschlossen; nur zu einem stornierten nicht (seit 1.9.124 409 für jede Rolle, bis dahin 403 und nur für die Monteurin).

    Regel      app/service_reports.py::bericht_zum_auftrag_moeglich() -- POST /api/orders/{id}/service-reports, bericht_anlegen an
               GET /api/orders/{id}, GET /api/field-view/auftraege/{id}/bericht-anlegen; die Suche lässt stornierte in SQL weg
    Suche      GET /api/field-view/auftraege-suche?q= -- alle nicht stornierten Aufträge nach Nummer, Titel, Objekt, Kunde, Adresse, ab 2
               Zeichen, höchstens 20, nur die sechs Anzeigefelder (keine Preise, Schlüssel-Scan wie test_v326)
    Anlegen    GET …/bericht-anlegen: der Auftrag als Zeile und seine Dachflächen (id, Name) -- für den Dialog
    Leserechte keine neuen: den Auftrag öffnet sie erst über den eigenen Bericht (field_may_access_order(), Weg 2)
1.9.74–1.9.78 legte sie nur zu Aufträgen ihrer Liste an (test_v497, mit 1.9.79 gelöscht), bis 1.9.73 zu jedem, auf den sie zugreifen durfte.
"""

import ast
import inspect

import pytest
from sqlalchemy import func, select

from app.meldungen import BERICHT_STORNIERT
from app.models import ServiceReport
from app.roof_areas import create_roof_area
from app.routers import field_view as field_view_router
from app.routers import orders as orders_router
from app.routers import service_reports as service_reports_router
from tests.test_v224_field_view import make_employee
from tests.test_v326_monteur_datengrenze import _privatadresse, _schluessel, _verboten
from tests.test_v325_contract_basis import beauftragen, make_quote

ANZEIGEFELDER = {"id", "order_number", "title", "property_name", "customer_name", "property_address"}


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    mia = make_employee(db, "M-502", "Mia", "Monteurin")
    daten = {  # name: (Nummer, Titel, Objekt, Status)
        "offen": ("AUF-0502-11", "Dachrinne Süd", "Lagerhalle West", "beauftragt"),
        "abgeschlossen": ("AUF-0502-12", "Attika Nord", "Bürohaus Ost", "abgeschlossen"),
        "storniert": ("AUF-0502-13", "Dachrinne Storno", "Lagerhalle West", "storniert"),
        "anderer": ("AUF-0502-14", "Kehle", "Wohnhaus Mitte", "beauftragt"),
    }
    auftraege = {}
    for i, (name, (nummer, titel, objekt, status)) in enumerate(daten.items()):
        order = beauftragen(db, make_quote(db, is_consumer=False, number=f"0502{i}"))
        order.order_number, order.title, order.property_name, order.status = nummer, titel, objekt, status
        order.property_address = "Industriestr. 7\n52531 Übach-Palenberg" if name == "offen" else "Ringweg 1\n52511 Geilenkirchen"
        auftraege[name] = order
    db.commit()
    from app.models import Property
    halle = Property(customer_id=auftraege["offen"].project.customer_id, name="Lagerhalle West")
    db.add(halle); db.flush()
    auftraege["offen"].project.property_id = halle.id
    db.commit()
    create_roof_area(db, halle.id, "Hauptdach", roof_type="Flachdach")
    routers = (service_reports_router.router, orders_router.router, field_view_router.router)
    return {"db": db, "mia": mia, "auftraege": auftraege,
            "als_mia": router_test_client(db, *routers, role="field", employee_id=mia.id),
            "buero": router_test_client(db, *routers)}


def _anlegen(client, order):
    return client.post(f"/api/orders/{order.id}/service-reports", json={"report_type": "rapport", "description": "Notdienst"})


def _berichte(w, order):
    return w["db"].scalar(select(func.count()).select_from(ServiceReport).where(ServiceReport.order_id == order.id))


@pytest.mark.parametrize("name", ["offen", "abgeschlossen"])
def test_bericht_zu_nicht_eingeplantem_offenem_und_abgeschlossenem(welt, name):
    """Angriff: nie zugeordnet, offen bzw. abgeschlossen -> angelegt, von ihr; danach öffnet sie den Auftrag über den eigenen Bericht."""
    order, client = welt["auftraege"][name], welt["als_mia"]
    assert client.get(f"/api/orders/{order.id}").status_code == 403  # vorher kein Leserecht
    antwort = _anlegen(client, order)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["created_by_employee_id"] == welt["mia"].id
    assert client.get(f"/api/orders/{order.id}").status_code == 200  # Weg 2: eigener Bericht


def test_storniert_409_und_nichts_angelegt(welt):
    order = welt["auftraege"]["storniert"]
    antwort = _anlegen(welt["als_mia"], order)
    assert antwort.status_code == 409 and antwort.json()["detail"] == BERICHT_STORNIERT  # seit 1.9.124 409 (bis dahin 403)
    assert _berichte(welt, order) == 0


def test_unbekannter_auftrag_404(welt):
    assert welt["als_mia"].post("/api/orders/999999/service-reports", json={"report_type": "rapport"}).status_code == 404


def test_keine_neuen_leserechte(welt):
    """Ein Bericht zu „offen“ öffnet nur „offen“ -- „anderer“ bleibt gesperrt, ebenso seine Dachflächen und seine Seite des Auftrags."""
    client, anderer = welt["als_mia"], welt["auftraege"]["anderer"]
    assert _anlegen(client, welt["auftraege"]["offen"]).status_code == 200
    for pfad in (f"/api/orders/{anderer.id}", f"/api/orders/{anderer.id}/roof-areas", f"/api/orders/{anderer.id}/service-reports"):
        assert client.get(pfad).status_code == 403, pfad


def test_bericht_anlegen_kennzeichen_wie_das_anlegen(welt):
    """bericht_anlegen an GET /api/orders/{id} (nach dem eigenen Bericht lesbar) folgt derselben Regel: offen und abgeschlossen ja."""
    client = welt["als_mia"]
    for name in ("offen", "abgeschlossen"):
        order = welt["auftraege"][name]
        _anlegen(client, order)
        assert client.get(f"/api/orders/{order.id}").json()["bericht_anlegen"] is True, name


def test_buero_zum_stornierten_ebenso_409(welt):
    """Seit 1.9.124 (Stufe 5, R2, Punkt 1): zum stornierten Auftrag legt auch das Büro keinen Bericht mehr an (bis 1.9.123 200, die Regel galt
    nur für die Monteurin); zu jedem anderen wie bisher."""
    antwort = _anlegen(welt["buero"], welt["auftraege"]["storniert"])
    assert antwort.status_code == 409 and antwort.json()["detail"] == BERICHT_STORNIERT
    assert _anlegen(welt["buero"], welt["auftraege"]["abgeschlossen"]).status_code == 200


# --- Suche ---------------------------------------------------------------------------------------------------------------------------

def _suche(w, q):
    antwort = w["als_mia"].get("/api/field-view/auftraege-suche", params={"q": q})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


@pytest.mark.parametrize("q", ["0502-11", "rinne süd", "Lagerhalle", "Industriestr"])
def test_suche_findet_fremden_auftrag(welt, q):
    """Angriff: nach Nummer, Titel (ohne Groß/klein), Objekt und Adresse -- der nie zugeordnete Auftrag ist dabei, der stornierte nie."""
    ids = [t["id"] for t in _suche(welt, q)]
    assert welt["auftraege"]["offen"].id in ids and welt["auftraege"]["storniert"].id not in ids


def test_suche_ab_zwei_zeichen_hoechstens_zwanzig_neueste_zuerst(welt):
    db = welt["db"]
    for i in range(22):
        order = beauftragen(db, make_quote(db, is_consumer=False, number=f"0503{i:02d}"))
        order.order_number, order.title = f"AUF-0503-{i:02d}", "Serienwartung"
    db.commit()
    assert _suche(welt, "S") == [] and _suche(welt, " ") == []
    treffer = _suche(welt, "Serienwartung")
    assert len(treffer) == 20 and [t["order_number"] for t in treffer] == [f"AUF-0503-{i:02d}" for i in range(21, 1, -1)]


def test_suche_nimmt_prozent_und_unterstrich_woertlich(welt):
    assert _suche(welt, "%%") == [] and _suche(welt, "__") == []


def test_suche_nur_anzeigefelder_ohne_preise(welt):
    """Gegenprobe zur Datengrenze: genau die sechs Anzeigefelder, kein verbotener Schlüssel (Preis, Kundennummer …)."""
    treffer = _suche(welt, "AUF-0502")
    assert treffer and all(set(t) == ANZEIGEFELDER for t in treffer)
    assert [f"{p}.{k}" for p, k in _schluessel(treffer) if _verboten(k) or _privatadresse("/api/field-view/auftraege-suche", p, k)] == []


# --- Daten zum Anlegen ---------------------------------------------------------------------------------------------------------------

def test_daten_zum_anlegen_auftrag_und_dachflaechen(welt):
    order = welt["auftraege"]["offen"]
    antwort = welt["als_mia"].get(f"/api/field-view/auftraege/{order.id}/bericht-anlegen")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert set(daten["auftrag"]) == ANZEIGEFELDER and daten["auftrag"]["title"] == "Dachrinne Süd"
    assert [set(a) for a in daten["dachflaechen"]] == [{"id", "name"}] and daten["dachflaechen"][0]["name"] == "Hauptdach"
    route = "/api/field-view/auftraege/{order_id}/bericht-anlegen"
    assert [f"{p}.{k}" for p, k in _schluessel(daten) if _verboten(k) or _privatadresse(route, p, k)] == []


def test_daten_zum_anlegen_storniert_409_unbekannt_404(welt):
    client = welt["als_mia"]
    assert client.get(f"/api/field-view/auftraege/{welt['auftraege']['storniert'].id}/bericht-anlegen").status_code == 409  # bis 1.9.123 403
    assert client.get("/api/field-view/auftraege/999999/bericht-anlegen").status_code == 404


def _aufrufe(funktion) -> set[str]:
    baum = ast.parse(inspect.getsource(funktion).lstrip())
    return {n.func.id if isinstance(n.func, ast.Name) else n.func.attr for n in ast.walk(baum) if isinstance(n, ast.Call)
            and isinstance(n.func, (ast.Name, ast.Attribute))}


def test_eine_regel():
    """Anlegen, Kennzeichen am Auftrag und Daten zum Anlegen fragen dieselbe Funktion."""
    for funktion in (service_reports_router.post_service_report, orders_router.get_order, field_view_router.get_field_view_bericht_anlegen):
        assert "bericht_zum_auftrag_moeglich" in _aufrufe(funktion), funktion.__name__
