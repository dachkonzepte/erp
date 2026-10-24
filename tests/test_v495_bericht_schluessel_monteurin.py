"""Seit 1.9.71 (Stufe 4, R4 Nachrunde, Punkt 6): was die Berichtsseite der Monteurin über ihren Bericht lädt, rekursiv geprüft.

    Schlüssel  GET /api/service-reports/{id}, …/noch-offen und …/zeiten als Monteurin: kein verbotener Schlüssel (Preise, Sätze, Löhne
               … -- dieselbe Prüfung wie der Rundgang in test_v326, _verboten()/_privatadresse()), keine Ausnahme
    Werte      kein Einkaufspreis des Materials im Bericht, kein Stundenlohn der Leute (als Zahl in irgendeinem Wert)
    Auftrag    jede order_id/order_number ist die des Berichts; kein Text eines anderen Auftrags (Nummer, Titel, Kunde, Befund und Zeiten
               ihres eigenen Berichts auf dem anderen Auftrag am selben Tag)
    Tag        die Zeiten nur vom Berichtstag (performed_at): nicht vom Vortag desselben Auftrags, nicht vom anderen Auftrag am selben Tag

…/zeiten nennt der Auftrag nicht wörtlich („Zeiten nur vom Berichtstag“ kommen auf der Berichtsseite von dort). Ein vor 1.9.42 unterschriebener
Bericht zeigt bewusst weiter alle Zeiten des Auftrags (zeiten_des_berichts(), Art „alt“) -- hier nicht Gegenstand.
"""

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.findings import create_finding
from app.materials import create_manual_material
from app.models import Customer, Order, OrderItem, Project, TimeEntry
from app.project_pipeline_columns import default_pipeline_column_id
from app.roof_areas import create_roof_area, create_roof_component
from app.routers.service_reports import router as service_reports_router
from app.service_reports import add_material, create_report
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import _make_order_for_report, _seed_test_template
from tests.test_v224_field_view import make_employee
from tests.test_v326_monteur_datengrenze import _privatadresse, _schluessel, _verboten

TAG = date(2026, 10, 14)
VORTAG = date(2026, 10, 13)
EINKAUF = Decimal("987.65")
LOHN = Decimal("54.32")
FREMD = ("AUF-FREMD-0001", "P-FREMD-0001", "Fremdauftrag Kehle", "Fremdkunde AG", "Fremdbefund Kehle")


def _fremder_auftrag(db):
    """Ein zweiter Auftrag eines anderen Kunden (make_order_with_item() vergibt feste Nummern, die eindeutig sein müssen)."""
    kunde = Customer(name="Fremdkunde AG", last_name="Fremdkunde AG")
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-FREMD-0001", name="Fremdprojekt", customer_id=kunde.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    order = Order(order_number="AUF-FREMD-0001", project_id=projekt.id, source_quote_id=2, quote_number_snapshot="A-FREMD-0001",
                  title="Fremdauftrag Kehle", vat_rate=Decimal("19.00"), customer_name="Fremdkunde AG", customer_number="K-FREMD")
    db.add(order); db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Kehle", quantity=Decimal("3"), unit="m",
                     unit_price=Decimal("80")))
    db.commit()
    return order


def _zeit(db, emp, order, tag, von, bis):
    beginn, ende = datetime.combine(tag, von), datetime.combine(tag, bis)
    db.add(TimeEntry(employee_id=emp.id, project_id=order.project_id, order_id=order.id, work_date=tag, started_at=beginn, ended_at=ende,
                     hours=Decimal(str((ende - beginn).seconds / 3600)), status="booked", source="manual"))


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    _seed_test_template(db)
    _, prop = make_customer_and_property(db)
    nord = create_roof_area(db, prop.id, "Dachfläche Nord", roof_type="Flachdach")
    sued = create_roof_area(db, prop.id, "Dachfläche Süd", roof_type="Flachdach")
    create_roof_component(db, nord["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db, prop)
    fremd = _fremder_auftrag(db)
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    tom = make_employee(db, "M-2", "Tom", "Monteur")
    for emp in (mia, tom):
        emp.hourly_wage = LOHN
    db.commit()

    report = create_report(db, order.id, "wartung", created_by_employee_id=mia.id, performed_at=TAG, roof_area_ids=[nord["id"], sued["id"]])
    create_finding(db, report["id"], "Ablauf verstopft", "mittel", "sofort_behoben", created_by_employee_id=mia.id)
    material = create_manual_material(db, "Bitumenbahn", "m²", EINKAUF)
    add_material(db, report["id"], material_id=material.id, quantity=Decimal("4"), created_by_employee_id=mia.id)
    # ihr eigener Bericht auf dem anderen Auftrag am selben Tag
    fremd_bericht = create_report(db, fremd.id, "rapport", "Kehle abgedichtet", created_by_employee_id=mia.id, performed_at=TAG)
    create_finding(db, fremd_bericht["id"], "Fremdbefund Kehle", "gering", "sofort_behoben", created_by_employee_id=mia.id)

    _zeit(db, mia, order, TAG, time(7, 0), time(12, 0))     # Berichtstag, Auftrag des Berichts
    _zeit(db, tom, order, TAG, time(12, 30), time(15, 30))  # Berichtstag, Auftrag des Berichts, andere Person
    _zeit(db, mia, order, VORTAG, time(6, 0), time(10, 0))  # Vortag, derselbe Auftrag
    _zeit(db, mia, fremd, TAG, time(13, 0), time(14, 0))    # Berichtstag, anderer Auftrag
    db.commit()
    client = router_test_client(db, service_reports_router, role="field", employee_id=mia.id)
    return {"db": db, "client": client, "report": report, "order": order}


def _antworten(welt):
    rid = welt["report"]["id"]
    antworten = {}
    for route in (f"/api/service-reports/{rid}", f"/api/service-reports/{rid}/noch-offen", f"/api/service-reports/{rid}/zeiten"):
        antwort = welt["client"].get(route)
        assert antwort.status_code == 200, (route, antwort.text)
        antworten[route] = antwort.json()
    return antworten


def _werte(value, path="$"):
    """(Pfad, Schlüssel, Wert) für jeden Wert, der kein dict und keine Liste ist."""
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                yield from _werte(child, f"{path}.{key}")
            else:
                yield path, key, child
    elif isinstance(value, list):
        for child in value:
            yield from _werte(child, f"{path}[]")


def test_keine_verbotenen_schluessel(welt):
    """Angriff: kein Schlüssel nach Preis, Satz, Lohn, Notiz, Kontakt … in den drei Antworten -- ohne Ausnahme."""
    verstoesse = [f"{route}: {path}.{key}" for route, body in _antworten(welt).items() for path, key in _schluessel(body)
                  if _verboten(key) or _privatadresse(route, path, key)]
    assert verstoesse == []


def test_kein_preis_und_kein_lohn_als_wert(welt):
    """Angriff: weder der Einkaufspreis des Materials im Bericht noch der Stundenlohn steht als Zahl in einem Wert."""
    verboten = {"987.65", "987,65", "54.32", "54,32"}
    funde = [f"{route}: {path}.{key}={wert!r}" for route, body in _antworten(welt).items() for path, key, wert in _werte(body)
             if any(v in str(wert) for v in verboten)]
    assert funde == []


def test_keine_daten_anderer_auftraege(welt):
    """Angriff: jede Auftragsangabe ist die des Berichts; kein Text des anderen Auftrags -- auch nicht aus ihrem eigenen Bericht dort."""
    order = welt["order"]
    antworten = _antworten(welt)
    for route, body in antworten.items():
        for path, key, wert in _werte(body):
            if key == "order_id":
                assert wert == order.id, (route, path)
            if key == "order_number":
                assert wert == order.order_number, (route, path)
            assert not any(f in str(wert) for f in FREMD), (route, path, key, wert)


def test_zeiten_nur_vom_berichtstag(welt):
    """Angriff: die Zeiten sind genau die des Berichtstags auf dem Auftrag des Berichts (alle Personen) -- nicht der Vortag, nicht der
    andere Auftrag am selben Tag."""
    zeiten = _antworten(welt)[f"/api/service-reports/{welt['report']['id']}/zeiten"]
    assert zeiten["art"] == "aktuell" and zeiten["tag"] == TAG.isoformat()
    assert {z["tag"] for z in zeiten["zeilen"]} == {TAG.isoformat()}
    assert [(z["von"], z["bis"]) for z in zeiten["zeilen"]] == [("07:00", "12:00"), ("12:30", "15:30")]
