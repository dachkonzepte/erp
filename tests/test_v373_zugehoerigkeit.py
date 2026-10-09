"""Version 1.8.70 -- Angriffstests zur Reparatur Sicherheit (Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ Punkt 2,
docs/archiv/befund-vor-echtbetrieb.md). Die Eigenschaften selbst (nichts mit Bezug auf ein fremdes Objekt gespeichert) prüfen
die früheren xfail-Tests in tests/test_v372_befund_fremdes_objekt.py; hier, WIE abgelehnt wird:

1. Monteur-Wege (2a–2e): Dachfläche, Bauteil, Material nur aus dem Objekt des Auftrags -- 404, für eine fremde und eine nicht
   vorhandene ID dieselbe Antwort (app/zugehoerigkeit.py::require_in_order_property()).
2. Wartungshistorie in /mobil nur für Objekte der Aufträge des Monteurs (field_accessible_property_ids()).
3. "Erfasst von" am Prüfpunkt und "geschlossen von" am Mangel aus der Anmeldung; mitgeschickt 422.
4. Vorgang aus dem Wartungsvertrag mit Kunde und Objekt des Vertrags (2h); Rechnungsposition nur aus dem eigenen Auftrag (2i).
5. Schnellauftrag und Wartungsvertrag am Objekt eines anderen Kunden nur mit Bestätigung -- sonst 409 mit Hinweis (2f/2g).

Gegenprobe (Regel 24) je Schutz: siehe docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.70"."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (
    Customer, Finding, InspectionItem, MaintenanceContract, Project, Property, ServiceReport, ServiceReportMaterial,
)
from app.roof_areas import create_roof_area, create_roof_component
from app.routers.field_view import router as field_view_router
from app.routers.findings import router as findings_router
from app.routers.invoices import router as invoices_router
from app.routers.maintenance_contracts import router as contracts_router
from app.routers.projects import router as projects_router
from app.routers.quick_service_orders import router as qso_router
from app.routers.service_reports import router as sr_router
from tests.test_v213_inspection_items import _seed_test_template
from tests.test_v263_report_ownership_and_contract_scope import _assign_via_team, _employee, _order_with_property

ROUTERS = (sr_router, findings_router, field_view_router, contracts_router, qso_router, invoices_router, projects_router)


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    _seed_test_template(db, roof_type="Flachdach")
    monteurin = _employee(db, "T-373-M", "Mona", "Monteurin")
    kollege = _employee(db, "T-373-K", "Karl", "Kollege")
    order, kunde, eigen = _order_with_property(db, "AUF-373-0001", "P-373-0001", property_name="Objekt Eigen")
    _assign_via_team(db, order, monteurin)
    fremdkunde = Customer(name="Fremdkunde", last_name="Fremdkunde", city="Fremdstadt")
    db.add(fremdkunde)
    db.commit()
    fremder_auftrag, _, fremd = _order_with_property(db, "AUF-373-0002", "P-373-0002", customer=fremdkunde,
                                                     property_name="Objekt Fremd")
    flaeche = create_roof_area(db, eigen.id, "Hauptdach", roof_type="Flachdach")["id"]
    zweite = create_roof_area(db, eigen.id, "Anbau", roof_type="Flachdach")["id"]
    bauteil = create_roof_component(db, flaeche, "Gully Haupt", component_type="Gully")["id"]
    bauteil_anbau = create_roof_component(db, zweite, "Gully Anbau", component_type="Gully")["id"]
    fremde_flaeche = create_roof_area(db, fremd.id, "Fremddach", roof_type="Flachdach")["id"]
    fremdes_bauteil = create_roof_component(db, fremde_flaeche, "Fremdgully", component_type="Gully")["id"]

    def client(role="field", employee_id=monteurin.id):
        return router_test_client(db, *ROUTERS, role=role, employee_id=employee_id)

    return {"db": db, "client": client, "monteurin": monteurin, "kollege": kollege, "order": order, "kunde": kunde,
            "eigen": eigen, "fremdkunde": fremdkunde, "fremder_auftrag": fremder_auftrag, "fremd": fremd,
            "flaeche": flaeche, "zweite": zweite, "bauteil": bauteil, "bauteil_anbau": bauteil_anbau,
            "fremde_flaeche": fremde_flaeche, "fremdes_bauteil": fremdes_bauteil, "unbekannt": 987654}


def _bericht(w, flaechen=None, report_type="rapport", client=None):
    c = client or w["client"]()
    return c.post(f"/api/orders/{w['order'].id}/service-reports",
                  json={"report_type": report_type, "roof_area_ids": flaechen})


def _eigener_bericht(w, flaechen=None) -> int:
    r = _bericht(w, flaechen if flaechen is not None else [w["flaeche"]])
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _antwort(r):
    return r.status_code, r.json()


# ---------------------------------------------------------------------------
# 1. Monteur-Wege: 404 ohne Grund, fremd wie unbekannt
# ---------------------------------------------------------------------------

def test_report_with_foreign_or_unknown_roof_area_is_404_and_creates_nothing(welt):
    vorher = welt["db"].scalar(select(ServiceReport.id).order_by(ServiceReport.id.desc()))
    fremd = _bericht(welt, [welt["flaeche"], welt["fremde_flaeche"]], "wartung")
    unbekannt = _bericht(welt, [welt["flaeche"], welt["unbekannt"]], "wartung")
    assert _antwort(fremd) == _antwort(unbekannt) == (404, {"detail": "Dachfläche nicht gefunden."})
    welt["db"].expire_all()
    assert welt["db"].scalar(select(ServiceReport.id).order_by(ServiceReport.id.desc())) == vorher
    eigen = _bericht(welt, [welt["flaeche"], welt["zweite"]], "wartung")
    assert eigen.status_code == 200, eigen.text
    assert sorted(a["roof_area_id"] for a in eigen.json()["roof_areas"]) == sorted([welt["flaeche"], welt["zweite"]])


def test_office_gets_the_same_404_the_check_has_no_role(welt):
    r = _bericht(welt, [welt["fremde_flaeche"]], client=welt["client"]("buero_auftrag", None))
    assert _antwort(r) == (404, {"detail": "Dachfläche nicht gefunden."})


def test_order_without_property_takes_no_roof_area(welt):
    db = welt["db"]
    welt["order"].project.property_id = None
    db.commit()
    assert _antwort(_bericht(welt, [welt["flaeche"]])) == (404, {"detail": "Dachfläche nicht gefunden."})
    assert _bericht(welt, None).status_code == 200


def test_inspection_item_component_and_area_only_of_the_order_property(welt):
    report_id = _eigener_bericht(welt)
    c = welt["client"]()

    def punkt(**ids):
        return c.post(f"/api/service-reports/{report_id}/inspection-items",
                      json={"text": "Zusatz", "item_type": "ja_nein", **ids})

    bauteil = (404, {"detail": "Bauteil nicht gefunden."})
    flaeche = (404, {"detail": "Dachfläche nicht gefunden."})
    assert _antwort(punkt(roof_component_id=welt["fremdes_bauteil"])) == _antwort(punkt(roof_component_id=welt["unbekannt"])) == bauteil
    assert _antwort(punkt(roof_area_id=welt["fremde_flaeche"])) == _antwort(punkt(roof_area_id=welt["unbekannt"])) == flaeche
    # Bauteil des eigenen Objekts, aber auf einer anderen als der angegebenen Fläche
    assert _antwort(punkt(roof_component_id=welt["bauteil_anbau"], roof_area_id=welt["flaeche"])) == bauteil
    ok = punkt(roof_component_id=welt["bauteil"], roof_area_id=welt["flaeche"])
    assert ok.status_code == 200, ok.text
    welt["db"].expire_all()
    assert welt["db"].scalars(select(InspectionItem.roof_component_id).where(
        InspectionItem.service_report_id == report_id, InspectionItem.text == "Zusatz")).all() == [welt["bauteil"]]


def test_finding_component_only_of_the_order_property(welt):
    report_id = _eigener_bericht(welt)
    c = welt["client"]()

    def mangel(component_id):
        return c.post(f"/api/service-reports/{report_id}/findings", json={
            "description": "Riss", "severity": "mittel", "action": "zurueckgestellt",
            "resubmission_date": "2027-01-01", "roof_component_id": component_id})

    assert _antwort(mangel(welt["fremdes_bauteil"])) == _antwort(mangel(welt["unbekannt"])) == (
        404, {"detail": "Bauteil nicht gefunden."})
    assert mangel(welt["bauteil_anbau"]).status_code == 200  # eigenes Objekt, Fläche frei
    welt["db"].expire_all()
    assert welt["db"].scalars(select(Finding.roof_component_id).where(Finding.service_report_id == report_id)).all() == [
        welt["bauteil_anbau"]]


def test_material_roof_area_only_of_the_order_property_post_and_put(welt):
    report_id = _eigener_bericht(welt, [])  # Bericht ohne Flächen -- hier griff die alte Prüfung nicht
    c = welt["client"]()
    url = f"/api/service-reports/{report_id}/materials"
    body = {"description": "Dachbahn", "quantity": "2", "unit": "m²"}
    flaeche = (404, {"detail": "Dachfläche nicht gefunden."})
    assert _antwort(c.post(url, json={**body, "roof_area_id": welt["fremde_flaeche"]})) == flaeche
    assert _antwort(c.post(url, json={**body, "roof_area_id": welt["unbekannt"]})) == flaeche
    row = c.post(url, json={**body, "roof_area_id": welt["flaeche"]})
    assert row.status_code == 200, row.text
    put = c.put(f"/api/service-report-materials/{row.json()['id']}", json={"roof_area_id": welt["fremde_flaeche"]})
    assert _antwort(put) == flaeche
    welt["db"].expire_all()
    assert welt["db"].get(ServiceReportMaterial, row.json()["id"]).roof_area_id == welt["flaeche"]


def test_material_keeps_the_report_coverage_check(welt):
    """Fläche des eigenen Objekts, aber nicht am Bericht (der Flächen hat): wie bisher 400 mit Grund -- kein Geheimnis."""
    report_id = _eigener_bericht(welt, [welt["flaeche"]])
    r = welt["client"]().post(f"/api/service-reports/{report_id}/materials", json={
        "description": "Dachbahn", "quantity": "2", "unit": "m²", "roof_area_id": welt["zweite"]})
    assert _antwort(r) == (400, {"detail": "Diese Dachfläche gehört nicht zu diesem Bericht."})


def test_contract_item_fallback_skips_a_roof_area_of_another_property(welt):
    """Ohne ausdrückliche Auswahl nimmt der Bericht die Fläche der Vertragsposition -- seit 1.8.70 nur aus dem Objekt des
    Auftrags (ein älterer Vorgang aus einem Mustervorgang kann an einem anderen Objekt hängen), sonst ohne Fläche."""
    from app.models import MaintenanceContractItem, MaintenanceWindow, ProjectProfile
    from app.service_reports import create_report

    db = welt["db"]
    vertrag = MaintenanceContract(customer_id=welt["fremdkunde"].id, property_id=welt["fremd"].id, title="Fremdvertrag",
                                  interval_months=12, next_due_date=date(2027, 1, 1))
    fenster = MaintenanceWindow(label="Frühjahr", month_from=3, month_to=5)
    db.add_all([vertrag, fenster])
    db.flush()
    position = MaintenanceContractItem(contract_id=vertrag.id, roof_area_id=welt["fremde_flaeche"],
                                       maintenance_window_id=fenster.id, next_due_date=date(2027, 3, 1))
    db.add(position)
    db.flush()
    db.add(ProjectProfile(project_id=welt["order"].project_id, source_maintenance_contract_id=vertrag.id,
                          source_maintenance_contract_item_id=position.id))
    db.commit()
    report = create_report(db, welt["order"].id, "wartung")
    assert report["roof_areas"] == []


# ---------------------------------------------------------------------------
# 2. Wartungshistorie in /mobil
# ---------------------------------------------------------------------------

def _unterschriebener_bericht(db, order, employee):
    from app.service_reports import create_report

    report = create_report(db, order.id, "rapport", created_by_employee_id=employee.id)
    db.get(ServiceReport, report["id"]).status = "unterschrieben"
    db.commit()
    return report["id"]


def test_history_only_for_properties_of_own_orders(welt):
    db = welt["db"]
    fremder_bericht = _unterschriebener_bericht(db, welt["fremder_auftrag"], welt["kollege"])
    eigener_bericht = _unterschriebener_bericht(db, welt["order"], welt["kollege"])
    c = welt["client"]()
    base = "/api/field-view/properties"
    assert c.get(f"{base}/{welt['eigen'].id}/maintenance-history").status_code == 200
    assert c.get(f"{base}/{welt['eigen'].id}/maintenance-history/{eigener_bericht}/pdf").status_code == 200
    liste = c.get(f"{base}/{welt['fremd'].id}/maintenance-history")
    assert liste.status_code == 403
    assert "Objekte Ihrer Aufträge" in liste.json()["detail"]
    pdf = c.get(f"{base}/{welt['fremd'].id}/maintenance-history/{fremder_bericht}/pdf")
    assert _antwort(pdf) == _antwort(c.get(f"{base}/{welt['fremd'].id}/maintenance-history/{welt['unbekannt']}/pdf")) == (
        404, {"detail": "Bericht nicht gefunden."})
    # Objektansicht und Dokumente bleiben für jedes Objekt offen (Betreiberentscheidung "Dateiablage je Objekt").
    assert c.get(f"{base}/{welt['fremd'].id}").status_code == 200
    assert c.get(f"{base}/{welt['fremd'].id}/documents").status_code == 200


def test_history_follows_the_same_rule_as_order_and_report(welt):
    """Weg "eigener Bericht": ein Monteur, der am fremden Auftrag selbst einen Bericht angelegt hat, sieht dessen Objekt --
    wie er Auftrag und Bericht öffnen darf. Ohne Mitarbeiterverknüpfung nichts."""
    db = welt["db"]
    from app.service_reports import create_report

    url = f"/api/field-view/properties/{welt['fremd'].id}/maintenance-history"
    assert welt["client"]().get(url).status_code == 403
    create_report(db, welt["fremder_auftrag"].id, "rapport", created_by_employee_id=welt["monteurin"].id)
    assert welt["client"]().get(url).status_code == 200
    assert welt["client"]("field", None).get(url).status_code == 403


def test_office_sees_the_history_of_every_property(welt):
    _unterschriebener_bericht(welt["db"], welt["fremder_auftrag"], welt["kollege"])
    r = welt["client"]("buero_auftrag", None).get(f"/api/field-view/properties/{welt['fremd'].id}/maintenance-history")
    assert r.status_code == 200 and len(r.json()) == 1


# ---------------------------------------------------------------------------
# 3. "Erfasst von" und "geschlossen von" aus der Anmeldung
# ---------------------------------------------------------------------------

def _item_id(w, report_id):
    w["db"].expire_all()
    return w["db"].scalars(select(InspectionItem.id).where(InspectionItem.service_report_id == report_id)).first()


@pytest.mark.parametrize("wert", [None, "kollege", "selbst"])
def test_recorded_by_from_the_request_is_rejected(welt, wert):
    report_id = _eigener_bericht(welt, [])
    c = welt["client"]()
    item = c.post(f"/api/service-reports/{report_id}/inspection-items", json={"text": "Punkt", "item_type": "ja_nein"}).json()
    ids = {None: None, "kollege": welt["kollege"].id, "selbst": welt["monteurin"].id}
    r = c.put(f"/api/inspection-items/{item['id']}", json={"result": "ok", "recorded_by_employee_id": ids[wert]})
    assert r.status_code == 422
    assert "Erfasst von" in r.text
    welt["db"].expire_all()
    assert welt["db"].get(InspectionItem, item["id"]).result is None


def test_recorded_by_is_set_from_the_login(welt):
    report_id = _eigener_bericht(welt, [])
    c = welt["client"]()
    item = c.post(f"/api/service-reports/{report_id}/inspection-items", json={"text": "Punkt", "item_type": "ja_nein"}).json()
    r = c.put(f"/api/inspection-items/{item['id']}", json={"result": "ok"})
    assert r.status_code == 200 and r.json()["recorded_by_employee_id"] == welt["monteurin"].id
    # Das Büro ändert nach: "erfasst von" ist dann die Person der Anmeldung (ohne Verknüpfung leer), nicht der Monteur.
    r = welt["client"]("buero_auftrag", welt["kollege"].id).put(f"/api/inspection-items/{item['id']}", json={"result": "nicht_ok"})
    assert r.status_code == 200 and r.json()["recorded_by_employee_id"] == welt["kollege"].id
    r = welt["client"]("admin", None).put(f"/api/inspection-items/{item['id']}", json={"result": "ok"})
    assert r.status_code == 200 and r.json()["recorded_by_employee_id"] is None


def _mangel(w, action="zurueckgestellt", client=None):
    report_id = _eigener_bericht(w, [])
    body = {"description": "Riss", "severity": "mittel", "action": action}
    if action == "zurueckgestellt":
        body["resubmission_date"] = "2027-01-01"
    r = (client or w["client"]()).post(f"/api/service-reports/{report_id}/findings", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("wert", [None, "kollege", "selbst"])
def test_closed_by_from_the_request_is_rejected(welt, wert):
    mangel = _mangel(welt)
    ids = {None: None, "kollege": welt["kollege"].id, "selbst": welt["monteurin"].id}
    r = welt["client"]().put(f"/api/findings/{mangel['id']}/followup",
                             json={"status": "erledigt", "closed_by_employee_id": ids[wert]})
    assert r.status_code == 422 and "Geschlossen von" in r.text
    welt["db"].expire_all()
    assert welt["db"].get(Finding, mangel["id"]).status != "erledigt"


def test_closed_by_is_set_from_the_login(welt):
    mangel = _mangel(welt)
    r = welt["client"]().put(f"/api/findings/{mangel['id']}/followup", json={"status": "erledigt"})
    assert r.status_code == 200 and r.json()["closed_by_employee_id"] == welt["monteurin"].id
    # "sofort behoben" beim Anlegen: geschlossen von der Anmeldung, auch wenn ein Admin einen anderen als Ersteller einträgt.
    admin = welt["client"]("admin", None)
    report_id = _eigener_bericht(welt, [])
    r = admin.post(f"/api/service-reports/{report_id}/findings", json={
        "description": "Laub entfernt", "severity": "gering", "action": "sofort_behoben",
        "created_by_employee_id": welt["kollege"].id})
    assert r.status_code == 200
    assert r.json()["created_by_employee_id"] == welt["kollege"].id and r.json()["closed_by_employee_id"] is None
    mona = _mangel(welt, "sofort_behoben")
    assert mona["closed_by_employee_id"] == welt["monteurin"].id


# ---------------------------------------------------------------------------
# 4. 2h: Vorgang aus dem Wartungsvertrag, 2i: Rechnungsposition
# ---------------------------------------------------------------------------

def _muster(w):
    muster = w["fremder_auftrag"].project
    muster.is_template = True
    w["db"].commit()
    return muster


def test_project_from_contract_and_from_contract_item_get_customer_and_property_of_the_contract(welt):
    from app.maintenance_contracts import create_contract, create_contract_item, create_project_from_contract
    from app.models import MaintenanceWindow

    db = welt["db"]
    muster = _muster(welt)
    vertrag = create_contract(db, welt["kunde"].id, welt["eigen"].id, "Wartung", 12, date(2027, 1, 1),
                              template_project_id=muster.id)
    neu = db.get(Project, create_project_from_contract(db, vertrag["id"])["project_id"])
    assert (neu.customer_id, neu.property_id, neu.is_template) == (welt["kunde"].id, welt["eigen"].id, False)
    # je Position (Schalter "zu wartende Dachflächen")
    from app.maintenance_contracts import update_maintenance_settings
    update_maintenance_settings(db, 30, True, None)
    fenster = MaintenanceWindow(label="Frühjahr", month_from=3, month_to=5)
    db.add(fenster)
    db.commit()
    position = create_contract_item(db, vertrag["id"], welt["flaeche"], fenster.id, template_project_id=muster.id)
    neu = db.get(Project, create_project_from_contract(db, vertrag["id"], item_id=position["id"])["project_id"])
    assert (neu.customer_id, neu.property_id) == (welt["kunde"].id, welt["eigen"].id)


def test_template_project_must_be_a_template(welt):
    from app.maintenance_contracts import create_contract, update_contract

    db = welt["db"]
    kein_muster = welt["fremder_auftrag"].project
    with pytest.raises(ValueError, match="Mustervorgang nicht gefunden"):
        create_contract(db, welt["kunde"].id, welt["eigen"].id, "Wartung", 12, date(2027, 1, 1),
                        template_project_id=kein_muster.id)
    vertrag = create_contract(db, welt["kunde"].id, welt["eigen"].id, "Wartung", 12, date(2027, 1, 1))
    with pytest.raises(ValueError, match="Mustervorgang nicht gefunden"):
        update_contract(db, vertrag["id"], "Wartung", 12, date(2027, 1, 1), kein_muster.id, None, None,
                        property_id=welt["eigen"].id)


def test_unchanged_template_is_not_checked_again(welt):
    """Ein früher gespeicherter Mustervorgang, der keiner (mehr) ist, blockiert das Speichern nicht -- geprüft wird nur ein neu
    gewählter (wie "aktiv" bei Auswahllisten)."""
    from app.maintenance_contracts import create_contract, update_contract

    db = welt["db"]
    muster = _muster(welt)
    vertrag = create_contract(db, welt["kunde"].id, welt["eigen"].id, "Wartung", 12, date(2027, 1, 1),
                              template_project_id=muster.id)
    muster.is_template = False
    db.commit()
    assert update_contract(db, vertrag["id"], "Wartung neu", 12, date(2027, 1, 1), muster.id, None, None,
                           property_id=welt["eigen"].id)["title"] == "Wartung neu"


def test_invoice_item_only_from_the_order_of_the_invoice(welt):
    from app.invoices import create_schlussrechnung
    from app.models import OrderItem

    db = welt["db"]
    rechnung = create_schlussrechnung(db, welt["order"])
    fremde = db.scalar(select(OrderItem.id).where(OrderItem.order_id == welt["fremder_auftrag"].id))
    eigene = db.scalar(select(OrderItem.id).where(OrderItem.order_id == welt["order"].id))
    c = welt["client"]("buero_auftrag", None)
    body = {"short_text": "Nachtrag", "unit": "m²", "unit_price": "50", "ist_quantity": "1"}
    for falsch in (fremde, welt["unbekannt"]):
        r = c.post(f"/api/invoices/{rechnung.id}/items", json={**body, "source_order_item_id": falsch})
        assert _antwort(r) == (400, {"detail": "Die Auftragsposition gehört nicht zum Auftrag dieser Rechnung."})
    assert c.post(f"/api/invoices/{rechnung.id}/items", json={**body, "source_order_item_id": eigene}).status_code == 200
    assert c.post(f"/api/invoices/{rechnung.id}/items", json=body).status_code == 200  # Nachtrag ohne Position


# ---------------------------------------------------------------------------
# 5. Objekt eines anderen Kunden nur mit Bestätigung
# ---------------------------------------------------------------------------

def _schnellauftrag(w, property_id, confirm=None):
    body = {"customer_id": w["kunde"].id, "property_id": property_id, "order_type": "reparatur", "title": "Reparatur"}
    if confirm is not None:
        body["confirm_property_customer"] = confirm
    return w["client"]("buero_auftrag", None).post("/api/quick-service-orders", json=body)


@pytest.fixture
def echte_angebots_ids(welt):
    # Die Testwelt erfindet Angebots-IDs -- der Schnellauftrag legt echte an ("existiert bereits Auftrag" sonst).
    welt["order"].source_quote_id, welt["fremder_auftrag"].source_quote_id = 900001, 900002
    welt["db"].commit()


def test_quick_order_at_a_property_of_another_customer_needs_confirmation(welt, echte_angebots_ids):
    for confirm in (None, False):
        r = _schnellauftrag(welt, welt["fremd"].id, confirm)
        assert r.status_code == 409
        assert "Objekt Fremd" in r.json()["detail"] and "Fremdkunde" in r.json()["detail"]
        assert "bestätigen" in r.json()["detail"]
    welt["db"].expire_all()
    assert welt["db"].scalars(select(Project.id).where(Project.name == "Reparatur")).all() == []
    ok = _schnellauftrag(welt, welt["fremd"].id, True)
    assert ok.status_code == 200, ok.text
    projekt = welt["db"].get(Project, ok.json()["project_id"])
    assert (projekt.customer_id, projekt.property_id) == (welt["kunde"].id, welt["fremd"].id)
    # eigenes Objekt und Hauptadresse ohne Bestätigung, unbekanntes Objekt 400
    assert _schnellauftrag(welt, welt["eigen"].id).status_code == 200
    assert _schnellauftrag(welt, None).status_code == 200
    assert _antwort(_schnellauftrag(welt, welt["unbekannt"], True)) == (400, {"detail": "Objekt nicht gefunden."})


def _vertrag_body(w, property_id, **extra):
    return {"customer_id": w["kunde"].id, "property_id": property_id, "title": "Wartung", "interval_months": 12,
            "next_due_date": "2027-01-01", **extra}


def test_contract_at_a_property_of_another_customer_needs_confirmation(welt):
    c = welt["client"]("buero_auftrag", None)
    r = c.post("/api/maintenance-contracts", json=_vertrag_body(welt, welt["fremd"].id))
    assert r.status_code == 409 and "Objekt Fremd" in r.json()["detail"]
    ok = c.post("/api/maintenance-contracts", json=_vertrag_body(welt, welt["fremd"].id, confirm_property_customer=True))
    assert ok.status_code == 200, ok.text
    assert (ok.json()["customer_id"], ok.json()["property_id"]) == (welt["kunde"].id, welt["fremd"].id)


def test_contract_update_checks_only_a_newly_chosen_property(welt):
    c = welt["client"]("buero_auftrag", None)
    eigen = c.post("/api/maintenance-contracts", json=_vertrag_body(welt, welt["eigen"].id)).json()
    put = {"title": "Wartung", "interval_months": 12, "next_due_date": "2027-01-01"}
    r = c.put(f"/api/maintenance-contracts/{eigen['id']}", json={**put, "property_id": welt["fremd"].id})
    assert r.status_code == 409
    welt["db"].expire_all()
    assert welt["db"].get(MaintenanceContract, eigen["id"]).property_id == welt["eigen"].id
    r = c.put(f"/api/maintenance-contracts/{eigen['id']}",
              json={**put, "property_id": welt["fremd"].id, "confirm_property_customer": True})
    assert r.status_code == 200 and r.json()["property_id"] == welt["fremd"].id
    # Danach unverändert speichern: keine erneute Bestätigung nötig.
    r = c.put(f"/api/maintenance-contracts/{eigen['id']}", json={**put, "title": "Neu", "property_id": welt["fremd"].id})
    assert r.status_code == 200 and r.json()["title"] == "Neu"


def test_contract_property_change_is_refused_while_items_hang_on_the_old_property(welt):
    from app.maintenance_contracts import create_contract, create_contract_item, update_maintenance_settings
    from app.models import MaintenanceWindow

    db = welt["db"]
    update_maintenance_settings(db, 30, True, None)
    fenster = MaintenanceWindow(label="Frühjahr", month_from=3, month_to=5)
    db.add(fenster)
    db.commit()
    vertrag = create_contract(db, welt["kunde"].id, welt["eigen"].id, "Wartung", 12, date(2027, 1, 1))
    create_contract_item(db, vertrag["id"], welt["flaeche"], fenster.id)
    r = welt["client"]("buero_auftrag", None).put(f"/api/maintenance-contracts/{vertrag['id']}", json={
        "title": "Wartung", "interval_months": 12, "next_due_date": "2027-01-01", "property_id": welt["fremd"].id,
        "confirm_property_customer": True})
    assert r.status_code == 400 and "Positionen" in r.json()["detail"]


def test_perform_maintenance_at_a_confirmed_property_of_another_customer(welt):
    """Am Vertrag bestätigt -> "Wartung durchführen" fragt nicht erneut; der Bericht nimmt die Flächen dieses Objekts."""
    db = welt["db"]
    welt["order"].source_quote_id, welt["fremder_auftrag"].source_quote_id = 900001, 900002
    db.commit()
    from app.maintenance_contracts import create_contract, create_maintenance_visit

    vertrag = create_contract(db, welt["kunde"].id, welt["fremd"].id, "GU-Wartung", 12, date(2027, 1, 1),
                              confirm_property_customer=True)
    besuch = create_maintenance_visit(db, vertrag["id"])
    projekt = db.get(Project, besuch["project_id"])
    assert (projekt.customer_id, projekt.property_id) == (welt["kunde"].id, welt["fremd"].id)
    assert [a.roof_area_id for a in db.get(ServiceReport, besuch["report_id"]).report_roof_areas] == [welt["fremde_flaeche"]]


def test_project_with_confirmed_foreign_property_can_be_saved_unchanged(welt, echte_angebots_ids):
    ok = _schnellauftrag(welt, welt["fremd"].id, True).json()
    c = welt["client"]("buero_auftrag", None)
    body = {"customer_id": welt["kunde"].id, "property_id": welt["fremd"].id, "name": "GU-Reparatur", "status": "anfrage"}
    r = c.put(f"/api/projects/{ok['project_id']}", json=body)
    assert r.status_code == 200, r.text
    # Ein neu gewählter Kunde muss das Objekt besitzen -- wie bisher 422.
    neuer_kunde = Customer(name="Dritter", last_name="Dritter")
    welt["db"].add(neuer_kunde)
    welt["db"].commit()
    r = c.put(f"/api/projects/{ok['project_id']}", json={**body, "customer_id": neuer_kunde.id})
    assert r.status_code == 422


def test_mismatch_text_names_both_customers_and_the_property(welt):
    from app.zugehoerigkeit import property_customer_mismatch

    db = welt["db"]
    assert property_customer_mismatch(db, welt["kunde"].id, welt["eigen"].id) is None
    assert property_customer_mismatch(db, welt["kunde"].id, None) is None
    m = property_customer_mismatch(db, welt["kunde"].id, welt["fremd"].id)
    assert (m["customer"], m["property_customer"], m["property"]) == ("Testkunde", "Fremdkunde", "Objekt Fremd")
    with pytest.raises(ValueError, match="Objekt nicht gefunden"):
        property_customer_mismatch(db, welt["kunde"].id, welt["unbekannt"])
    assert db.get(Property, welt["fremd"].id).customer_id == welt["fremdkunde"].id
