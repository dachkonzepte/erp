"""Seit 1.9.70 (Stufe 4, R4 Nachrunde, Punkt 2): „Noch offen“ mit der Dachfläche.

    Fläche     hat der Bericht mehr als eine Dachfläche, steht sie hinter der Zeile („Pflichtpunkt „…“ beantworten · Dachfläche Süd“) -- beim
               Pflichtpunkt und beim Befund zum Prüfpunkt über den Punkt, beim Foto und der Wiedervorlage eines Befunds über seinen Prüfpunkt
               oder sein Bauteil; mit einer Fläche keine Angabe
    eindeutig  bleiben zwei Zeilen trotzdem gleich (zwei von Hand ergänzte Punkte gleichen Namens ohne Fläche), bekommt die zweite „(2)“
(app/service_reports.py::noch_offen_je_schritt()). Bis 1.9.69 stand derselbe Pflichtpunkt zweier Flächen zweimal gleich da.
"""

import pytest

from app.findings import create_finding
from app.roof_areas import create_roof_area, create_roof_component
from app.routers.service_reports import router as service_reports_router
from app.service_reports import add_inspection_item, create_report, list_inspection_items, update_inspection_item
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import _make_order_for_report, _seed_test_template
from tests.test_v464_noch_offen import UNTERSCHRIFT

ZUGANG = "Pflichtpunkt „Zugang und Absturzsicherung geprüft“ beantworten"


@pytest.fixture
def zwei_flaechen(threaded_db_session, router_test_client):
    db = threaded_db_session
    _seed_test_template(db)
    _, prop = make_customer_and_property(db)
    nord = create_roof_area(db, prop.id, "Dachfläche Nord", roof_type="Flachdach")
    sued = create_roof_area(db, prop.id, "Dachfläche Süd", roof_type="Flachdach")
    create_roof_component(db, nord["id"], "Gully 1", component_type="Gully", sort_order=10)
    gully_sued = create_roof_component(db, sued["id"], "Gully S", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db, prop)
    report = create_report(db, order.id, "wartung", roof_area_ids=[nord["id"], sued["id"]])
    client = router_test_client(db, service_reports_router)
    return db, client, report, gully_sued


def _texte(client, report_id):
    return client.get(f"/api/service-reports/{report_id}/noch-offen").json()["offen"]


def test_zwei_flaechen_gleicher_pflichtpunkt_zwei_zeilen(zwei_flaechen):
    """Angriff: derselbe Pflichtpunkt auf zwei Flächen -> zwei verschiedene Zeilen mit der Fläche; keine Zeile doppelt, auch nicht in der
    Ablehnung der Unterschrift."""
    db, client, report, _ = zwei_flaechen
    texte = _texte(client, report["id"])
    assert [t for t in texte if t.startswith(ZUGANG)] == [f"{ZUGANG} · Dachfläche Nord", f"{ZUGANG} · Dachfläche Süd"]
    assert len(texte) == len(set(texte)) and all(" · Dachfläche " in t for t in texte)
    abgelehnt = client.post(f"/api/service-reports/{report['id']}/sign", json=UNTERSCHRIFT)
    assert abgelehnt.status_code == 409 and abgelehnt.json()["offen"] == texte


def test_eine_flaeche_ohne_angabe(threaded_db_session, router_test_client):
    """Gegenprobe: mit einer Fläche steht keine Fläche in der Zeile (wie bis 1.9.69)."""
    db = threaded_db_session
    _seed_test_template(db)
    _, prop = make_customer_and_property(db)
    nord = create_roof_area(db, prop.id, "Dachfläche Nord", roof_type="Flachdach")
    order = _make_order_for_report(db, prop)
    report = create_report(db, order.id, "wartung", roof_area_ids=[nord["id"]])
    texte = _texte(router_test_client(db, service_reports_router), report["id"])
    assert ZUGANG in texte and not any(" · " in t for t in texte)


def test_befund_mit_flaeche_ueber_pruefpunkt_und_bauteil(zwei_flaechen):
    db, client, report, gully_sued = zwei_flaechen
    for item in list_inspection_items(db, report["id"]):
        if item["required"]:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})
    gully_nord = next(i for i in list_inspection_items(db, report["id"]) if i["text"] == "Gully 1: Ablauf frei und funktionsfähig")
    create_finding(db, report["id"], "Ablauf verstopft", "mittel", "sofort_behoben", inspection_item_id=gully_nord["id"])
    create_finding(db, report["id"], "Laub im Gully", "gering", "sofort_behoben", roof_component_id=gully_sued["id"])
    create_finding(db, report["id"], "Allgemein", "gering", "sofort_behoben")
    assert _texte(client, report["id"]) == ["Foto zum Befund „Ablauf verstopft“ aufnehmen · Dachfläche Nord",
                                           "Foto zum Befund „Laub im Gully“ aufnehmen · Dachfläche Süd",
                                           "Foto zum Befund „Allgemein“ aufnehmen"]


def test_gleiche_zeilen_werden_gezaehlt(zwei_flaechen):
    """Angriff: zwei von Hand ergänzte Pflichtpunkte gleichen Namens ohne Fläche -> die zweite Zeile mit „(2)“."""
    db, client, report, _ = zwei_flaechen
    for item in list_inspection_items(db, report["id"]):
        if item["required"]:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})
    for _ in range(2):
        add_inspection_item(db, report["id"], "Steigleiter geprüft", "ja_nein", required=True)
    assert _texte(client, report["id"]) == ["Pflichtpunkt „Steigleiter geprüft“ beantworten",
                                           "Pflichtpunkt „Steigleiter geprüft“ beantworten (2)"]
