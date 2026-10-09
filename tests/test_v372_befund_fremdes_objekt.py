"""Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026, docs/archiv/befund-vor-echtbetrieb.md), Punkt 2:
Einsatzbericht mit Dachflächen und Bauteilen aus einem fremden Objekt, als Monteur.

Die Monteurin ist über die Kolonne an der Arbeitsvorbereitung dem Auftrag am Objekt "Eigen" zugeordnet. Ein zweites Objekt eines
anderen Kunden ("FREMD…") hat eine Dachfläche und ein Bauteil. Der Server nimmt deren IDs an drei Stellen ungeprüft an:
roof_area_ids beim Anlegen des Berichts (app/service_reports.py::create_report()), roof_component_id/roof_area_id am Prüfpunkt
(add_inspection_item()) und roof_component_id am Mangel (app/findings.py::create_finding()). Die Oberfläche bietet nur die
Flächen des eigenen Objekts an -- der Weg ist der direkte API-Aufruf.

Seit 1.8.70 behoben, die Tests sind die Abnahmetests (bis dahin xfail, tests/befund_vor_echtbetrieb.py). Geprüft wird die
Eigenschaft (nichts mit Bezug auf das fremde Objekt gespeichert, nichts davon in einer Antwort an die Monteurin), nicht der Weg
(ablehnen oder weglassen); wie abgelehnt wird (404 ohne Grund, 409 mit Bestätigung), prüft tests/test_v373_zugehoerigkeit.py. Dazu 2e-2i: dasselbe Muster
(ID aus der Anfrage ohne Prüfung der Zugehörigkeit) an weiteren Stellen, gefunden bei der Suche über den ganzen Code."""

import json
import re

import pytest
from sqlalchemy import or_, select

from app.models import Customer, Finding, InspectionItem, ServiceReport, ServiceReportRoofArea
from app.roof_areas import create_roof_area, create_roof_component
from app.routers.field_view import router as field_view_router
from app.routers.findings import router as findings_router
from app.routers.roof_areas import router as roof_router
from app.routers.service_reports import router as sr_router
from tests.test_v213_inspection_items import _extract_pdf_text, _seed_test_template
from tests.test_v263_report_ownership_and_contract_scope import _assign_via_team, _employee, _order_with_property
from tests.befund_vor_echtbetrieb import vorbedingung as _vorbedingung
from tests.test_v326_monteur_datengrenze import _verstoesse

MARKE = "FREMD"  # steht in jedem Namen und in der Adresse des fremden Objekts


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    _seed_test_template(db, roof_type="Flachdach")
    monteurin = _employee(db, "T-372-M", "Mona", "Monteurin")
    order, _, eigen = _order_with_property(db, "AUF-372-0001", "P-372-0001", property_name="Objekt Eigen")
    _assign_via_team(db, order, monteurin)
    fremdkunde = Customer(name=f"{MARKE}KUNDE Geheim", last_name=f"{MARKE}KUNDE Geheim", city="Fremdstadt")
    db.add(fremdkunde)
    db.commit()
    fremder_auftrag, _, fremd = _order_with_property(db, "AUF-372-0002", "P-372-0002", customer=fremdkunde,
                                                     property_name=f"{MARKE}OBJEKT Villa")
    fremd.street = f"{MARKE}WEG 7"
    db.commit()
    eigene_flaeche = create_roof_area(db, eigen.id, "Hauptdach Eigen", roof_type="Flachdach")
    create_roof_component(db, eigene_flaeche["id"], "Gully Eigen", component_type="Gully")
    fremde_flaeche = create_roof_area(db, fremd.id, f"{MARKE}DACH Villa Sued", roof_type="Flachdach")
    fremdes_bauteil = create_roof_component(db, fremde_flaeche["id"], f"{MARKE}GULLY Villa", component_type="Gully")
    client = router_test_client(db, sr_router, findings_router, field_view_router, roof_router, role="field",
                                employee_id=monteurin.id)
    return {"db": db, "client": client, "order": order, "eigen": eigen, "fremd": fremd, "fremder_auftrag": fremder_auftrag,
            "eigene_flaeche": eigene_flaeche["id"], "fremde_flaeche": fremde_flaeche["id"],
            "fremdes_bauteil": fremdes_bauteil["id"]}


def _bericht(w, flaechen, report_type="wartung"):
    return w["client"].post(f"/api/orders/{w['order'].id}/service-reports",
                            json={"report_type": report_type, "roof_area_ids": flaechen})


def _eigener_bericht(w) -> int:
    r = _bericht(w, [w["eigene_flaeche"]])
    _vorbedingung(r.status_code == 200, r.text)
    return r.json()["id"]


def _gespeichert_mit_fremdem_bezug(w) -> list[str]:
    db = w["db"]
    db.expire_all()
    fl, bt = w["fremde_flaeche"], w["fremdes_bauteil"]
    funde = [f"Bericht {r.service_report_id}: Dachfläche {r.roof_area_id}" for r in db.scalars(
        select(ServiceReportRoofArea).where(ServiceReportRoofArea.roof_area_id == fl))]
    funde += [f"Prüfpunkt {i.id}: Fläche {i.roof_area_id}, Bauteil {i.roof_component_id}" for i in db.scalars(
        select(InspectionItem).where(or_(InspectionItem.roof_area_id == fl, InspectionItem.roof_component_id == bt)))]
    funde += [f"Mangel {f.id}: Bauteil {f.roof_component_id}" for f in db.scalars(
        select(Finding).where(Finding.roof_component_id == bt))]
    return funde


# ---------------------------------------------------------------------------
# 2a-2c: gespeichert wird der Bezug auf das fremde Objekt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_type", ["wartung", "rapport"])
def test_report_does_not_store_a_roof_area_of_another_property(welt, report_type):
    _bericht(welt, [welt["eigene_flaeche"], welt["fremde_flaeche"]], report_type)
    assert _gespeichert_mit_fremdem_bezug(welt) == []


def test_inspection_item_does_not_store_a_component_or_area_of_another_property(welt):
    report_id = _eigener_bericht(welt)
    welt["client"].post(f"/api/service-reports/{report_id}/inspection-items", json={
        "text": "Zusatzpunkt", "item_type": "ja_nein",
        "roof_component_id": welt["fremdes_bauteil"], "roof_area_id": welt["fremde_flaeche"]})
    assert _gespeichert_mit_fremdem_bezug(welt) == []


def test_finding_does_not_store_a_component_of_another_property(welt):
    report_id = _eigener_bericht(welt)
    welt["client"].post(f"/api/service-reports/{report_id}/findings", json={
        "description": "Riss", "severity": "mittel", "action": "buero_pruefen",
        "roof_component_id": welt["fremdes_bauteil"]})
    assert _gespeichert_mit_fremdem_bezug(welt) == []


# ---------------------------------------------------------------------------
# 2d: was die Monteurin danach vom fremden Objekt sieht
# ---------------------------------------------------------------------------

def _alles_versuchen(w) -> int:
    """Die drei Wege nacheinander, wie ein Angreifer sie ginge; liefert die ID des Berichts."""
    r = _bericht(w, [w["eigene_flaeche"], w["fremde_flaeche"]])
    report_id = r.json()["id"] if r.status_code == 200 else _eigener_bericht(w)
    w["client"].post(f"/api/service-reports/{report_id}/inspection-items", json={
        "text": "Zusatzpunkt", "item_type": "ja_nein",
        "roof_component_id": w["fremdes_bauteil"], "roof_area_id": w["fremde_flaeche"]})
    w["client"].post(f"/api/service-reports/{report_id}/findings", json={
        "description": "Riss", "severity": "mittel", "action": "buero_pruefen",
        "roof_component_id": w["fremdes_bauteil"]})
    return report_id


def _antworten(w, report_id) -> list[dict]:
    """Was die Monteurin danach abrufen kann -- je Antwort das Routenmuster (für die Ausnahmen in test_v326). Erst im Entwurf
    (dann steht der Bericht in /api/field-view/today), danach unterschrieben (Wartungshistorie: am Auftrag nur andere Aufträge
    des Objekts, in /mobil je Objekt alle -- die öffnet jeder Monteur für jedes Objekt). Die Unterschrift wird am ORM vorbei
    gesetzt: ihre Pflichtprüfungen (Pflichtpunkte, Fotos am Mangel) sind hier nicht Gegenstand."""
    c, oid = w["client"], w["order"].id
    entwurf = [
        ("/api/orders/{order_id}/service-reports", f"/api/orders/{oid}/service-reports"),
        ("/api/orders/{order_id}/roof-areas", f"/api/orders/{oid}/roof-areas"),
        ("/api/service-reports/{report_id}/inspection-items", f"/api/service-reports/{report_id}/inspection-items"),
        ("/api/service-reports/{report_id}/findings", f"/api/service-reports/{report_id}/findings"),
        ("/api/field-view/today", "/api/field-view/today"),
    ]
    pid = w["eigen"].id
    unterschrieben = [
        ("/api/orders/{order_id}/property-service-reports", f"/api/orders/{oid}/property-service-reports"),
        ("/api/field-view/properties/{property_id}/maintenance-history",
         f"/api/field-view/properties/{pid}/maintenance-history"),
    ]
    antworten = []
    for abrufe in (entwurf, unterschrieben):
        if abrufe is unterschrieben:
            w["db"].get(ServiceReport, report_id).status = "unterschrieben"
            w["db"].commit()
        for route, url in abrufe:
            r = c.get(url)
            _vorbedingung(r.status_code == 200, f"{url}: {r.status_code} {r.text}")
            antworten.append({"route": route, "body": r.json()})
    r = c.get(f"/api/service-reports/{report_id}/pdf")
    _vorbedingung(r.status_code == 200, f"PDF: {r.status_code} {r.text}")
    antworten.append({"route": "/api/service-reports/{report_id}/pdf", "body": None, "pdf": r.content})
    return antworten


def _fremde_werte(value, w, path="$") -> list[str]:
    """Jeder Schlüssel, dessen Wert vom fremden Objekt kommt: Text mit der Marke oder eine ID der fremden Fläche bzw. des
    fremden Bauteils unter einem Schlüssel mit "roof"."""
    ids = {w["fremde_flaeche"], w["fremdes_bauteil"]}
    funde = []
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str) and MARKE in child:
                funde.append(f"{path}.{key} = {child!r}")
            elif isinstance(child, int) and not isinstance(child, bool) and "roof" in key and child in ids:
                funde.append(f"{path}.{key} = {child}")
            else:
                funde += _fremde_werte(child, w, f"{path}.{key}")
    elif isinstance(value, list):
        for child in value:
            funde += _fremde_werte(child, w, f"{path}[]")
    return funde


def test_today_key_scan_of_the_data_boundary_finds_nothing(welt):
    """Grün, zur Einordnung: der rekursive Schlüssel-Scan aus test_v326 (verbotene Schlüsselnamen) schlägt bei keiner dieser
    Antworten an -- was vom fremden Objekt durchkommt, steht unter erlaubten Namen (roof_area_name, text,
    roof_component_name, …). Die Lücke sieht nur ein Scan der Werte (2d)."""
    report_id = _alles_versuchen(welt)
    gefunden, _ = _verstoesse(_antworten(welt, report_id))
    assert gefunden == []


def test_monteur_sees_nothing_of_the_other_property_in_json_or_pdf(welt):
    report_id = _alles_versuchen(welt)
    funde = []
    for antwort in _antworten(welt, report_id):
        if "pdf" in antwort:
            pdf = _extract_pdf_text(antwort["pdf"]).decode("latin-1")
            funde += [f"PDF: {m}" for m in sorted(set(re.findall(rf"{MARKE}[A-Z]+[ A-Za-z]*", pdf)))]
        else:
            funde += [f"{antwort['route']}  {f}" for f in _fremde_werte(antwort["body"], welt)]
    assert funde == [], "\n" + "\n".join(funde)


def test_today_other_property_itself_stays_closed_for_the_monteur(welt):
    """Grün, zur Einordnung: Adresse und Kunde des fremden Objekts erscheinen nicht -- weder in den Antworten oben noch über
    die Dachflächen-Routen (Büro, 403). Name und Adresse eines Objekts sind für den Monteur ohnehin kein Geheimnis
    (/api/field-view/properties/{id}, PropertyAccessOut)."""
    report_id = _alles_versuchen(welt)
    antworten = _antworten(welt, report_id)
    text = json.dumps([a["body"] for a in antworten], ensure_ascii=False)
    text += " ".join(_extract_pdf_text(a["pdf"]).decode("latin-1") for a in antworten if "pdf" in a)
    assert f"{MARKE}KUNDE" not in text and f"{MARKE}WEG" not in text and f"{MARKE}OBJEKT" not in text
    for url in (f"/api/roof-areas/{welt['fremde_flaeche']}", f"/api/roof-areas/{welt['fremde_flaeche']}/components"):
        assert welt["client"].get(url).status_code == 403, url


# ---------------------------------------------------------------------------
# 2e-2i: dasselbe Muster an weiteren Stellen (Suche über den ganzen Code, Liste im Archiv)
# ---------------------------------------------------------------------------

def test_material_does_not_store_a_roof_area_of_another_property(welt):
    from app.models import ServiceReportMaterial

    r = _bericht(welt, [], "rapport")
    _vorbedingung(r.status_code == 200, r.text)
    welt["client"].post(f"/api/service-reports/{r.json()['id']}/materials", json={
        "description": "Dachbahn", "quantity": "2", "unit": "m²", "roof_area_id": welt["fremde_flaeche"]})
    db = welt["db"]
    db.expire_all()
    assert db.scalars(select(ServiceReportMaterial.id).where(
        ServiceReportMaterial.roof_area_id == welt["fremde_flaeche"])).all() == []


def _objekt_passt_zum_kunden(db, customer_id, property_id) -> bool:
    from app.models import Property

    return property_id is None or db.get(Property, property_id).customer_id == customer_id


def test_quick_service_order_keeps_property_and_customer_together(welt):
    from app.models import Order, Project
    from app.quick_service_orders import create_quick_service_order

    db = welt["db"]
    # Die Testwelt erfindet Angebots-IDs (1, 2) -- der Schnellauftrag legt echte an; sonst "existiert bereits Auftrag".
    welt["order"].source_quote_id, welt["fremder_auftrag"].source_quote_id = 900001, 900002
    db.commit()
    kunde_x = welt["order"].project.customer_id
    eigen = create_quick_service_order(db, customer_id=kunde_x, property_id=welt["eigen"].id, order_type="reparatur",
                                       title="Reparatur am eigenen Objekt")
    _vorbedingung(db.get(Project, eigen["project_id"]).property_id == welt["eigen"].id, "Schnellauftrag scheitert")
    try:
        create_quick_service_order(db, customer_id=kunde_x, property_id=welt["fremd"].id, order_type="reparatur",
                                   title="Reparatur")
    except ValueError:
        pass
    db.expire_all()
    assert [p.id for p in db.scalars(select(Project)) if not _objekt_passt_zum_kunden(db, p.customer_id, p.property_id)] == []
    assert [o.order_number for o in db.scalars(select(Order).where(Order.customer_name != f"{MARKE}KUNDE Geheim"))
            if f"{MARKE}OBJEKT" in (o.property_name or "")] == []


def test_maintenance_contract_keeps_property_and_customer_together(welt):
    from datetime import date

    from app.maintenance_contracts import create_contract, update_contract
    from app.models import MaintenanceContract

    db = welt["db"]
    kunde_x = welt["order"].project.customer_id
    try:
        neu = create_contract(db, kunde_x, welt["eigen"].id, "Wartung", 12, date(2027, 1, 1))
        update_contract(db, neu["id"], "Wartung", 12, date(2027, 1, 1), None, None, None, property_id=welt["fremd"].id)
    except ValueError:
        pass
    try:
        create_contract(db, kunde_x, welt["fremd"].id, "Wartung 2", 12, date(2027, 1, 1))
    except ValueError:
        pass
    db.expire_all()
    falsch = [c.id for c in db.scalars(select(MaintenanceContract))
              if not _objekt_passt_zum_kunden(db, c.customer_id, c.property_id)]
    assert falsch == []


def test_project_from_maintenance_contract_belongs_to_the_contract_customer(welt):
    from datetime import date

    from app.maintenance_contracts import create_contract, create_project_from_contract
    from app.models import Project

    db = welt["db"]
    kunde_x = welt["order"].project.customer_id
    muster = welt["fremder_auftrag"].project  # Projekt des Fremdkunden als Mustervorgang
    muster.is_template = True
    db.commit()
    vertrag = create_contract(db, kunde_x, welt["eigen"].id, "Wartung", 12, date(2027, 1, 1),
                              template_project_id=muster.id)
    vorher = {p.id for p in db.scalars(select(Project))}
    try:
        create_project_from_contract(db, vertrag["id"])
    except ValueError:
        pass
    db.expire_all()
    neue = [(p.customer_id, p.property_id) for p in db.scalars(select(Project)) if p.id not in vorher]
    assert all(neu == (kunde_x, welt["eigen"].id) for neu in neue), neue


def test_invoice_item_does_not_refer_to_an_item_of_another_order(welt):
    from decimal import Decimal

    from app.invoices import add_invoice_item, create_schlussrechnung
    from app.models import InvoiceItem, OrderItem

    db = welt["db"]
    fremde_position = db.scalar(select(OrderItem).where(OrderItem.order_id == welt["fremder_auftrag"].id))
    rechnung = create_schlussrechnung(db, welt["order"])
    try:
        add_invoice_item(db, rechnung, short_text="Nachtrag", long_text="", unit="m²", unit_price=Decimal("50"),
                         ist_quantity=Decimal("10"), source_order_item_id=fremde_position.id)
    except ValueError:
        pass
    db.expire_all()
    assert db.scalars(select(InvoiceItem.id).where(InvoiceItem.invoice_id == rechnung.id,
                                                   InvoiceItem.source_order_item_id == fremde_position.id)).all() == []
