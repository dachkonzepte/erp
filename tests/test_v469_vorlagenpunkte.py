"""Seit 1.9.41 (Stufe 4, R1 Nachrunde, Punkt 3): Prüfpunkte im Einsatzbericht -- löschbar ist nur ein von Hand ergänzter Punkt.

    Herkunft       ein Punkt aus der Vorlage trägt template_item_id (_generate_inspection_items()), ein von Hand ergänzter nie
                   (add_inspection_item()) -- daran unterscheidet der Server; ein Punkt aus der Vorlage 409 (dafür „Entfällt“), Pflicht oder nicht
    Seite          Löschknopf „×“ nur am von Hand ergänzten Punkt, am Ende der Titelzeile (48 × 48 px), mit Rückfrage „Prüfpunkt „…“ löschen?“
                   auf der Seite (<dialog>) statt confirm(); gemessen im Klicktest klicktest_monteurin_regeln
"""

import pytest

from app.routers.inspection_templates import router as inspection_templates_router
from app.routers.service_reports import router as service_reports_router
from app.roof_areas import create_roof_area, create_roof_component
from app.service_reports import add_inspection_item, list_inspection_items
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import _make_order_for_report, _seed_test_template
from tests.test_v224_field_view import make_employee, make_slot_for_individual, make_team
from tests.vorlagen_js import seitentext

VORLAGE = "Ein Prüfpunkt aus der Vorlage lässt sich nicht löschen – trifft er nicht zu, „Entfällt“ wählen."


@pytest.fixture
def monteurin(threaded_db_session, router_test_client):
    """Mias Wartungsbericht (Vorlage: Pflichtpunkte und freie Punkte) mit einem von ihr ergänzten Punkt, Mia angemeldet als Monteurin."""
    db = threaded_db_session
    _seed_test_template(db)
    _, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db, prop)
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    from datetime import date
    make_slot_for_individual(db, order, make_team(db, "K-1", "Kolonne 1"), mia, date(2026, 10, 1), date(2026, 10, 31))
    client = router_test_client(db, service_reports_router, inspection_templates_router, role="field", employee_id=mia.id)
    antwort = client.post(f"/api/orders/{order.id}/service-reports", json={"report_type": "wartung", "roof_area_ids": [area["id"]]})
    assert antwort.status_code == 200, antwort.text
    report_id = antwort.json()["id"]
    eigener = client.post(f"/api/service-reports/{report_id}/inspection-items", json={"text": "Dachluke geprüft", "item_type": "ja_nein"})
    assert eigener.status_code == 200, eigener.text
    return db, client, report_id, eigener.json()


def test_herkunft_unterscheidbar(monteurin):
    db, client, report_id, eigener = monteurin
    punkte = list_inspection_items(db, report_id)
    assert eigener["template_item_id"] is None
    assert all(p["template_item_id"] is not None for p in punkte if p["id"] != eigener["id"])
    assert {p["required"] for p in punkte if p["id"] != eigener["id"]} == {True, False}  # Pflicht und frei aus der Vorlage


@pytest.mark.parametrize("pflicht", [True, False], ids=["pflichtpunkt", "freier_punkt"])
def test_monteurin_loescht_vorlagenpunkt_nicht(monteurin, pflicht):
    """Angriff: ein Punkt aus der Vorlage -- Pflicht oder nicht -- 409, er bleibt (bis 1.9.40 ließ sich ein freier Punkt löschen)."""
    db, client, report_id, eigener = monteurin
    punkt = next(p for p in list_inspection_items(db, report_id) if p["template_item_id"] is not None and p["required"] is pflicht)
    antwort = client.delete(f"/api/inspection-items/{punkt['id']}")
    assert (antwort.status_code, antwort.json()["detail"]) == (409, VORLAGE)
    assert any(p["id"] == punkt["id"] for p in list_inspection_items(db, report_id))


def test_monteurin_loescht_eigenen_punkt(monteurin):
    """Gegenprobe: der von Hand ergänzte Punkt lässt sich löschen -- auch als Pflichtpunkt ergänzt (über die Schnittstelle)."""
    db, client, report_id, eigener = monteurin
    assert client.delete(f"/api/inspection-items/{eigener['id']}").status_code == 200
    pflicht_eigen = add_inspection_item(db, report_id, "Steigleiter geprüft", "ja_nein", required=True)
    assert client.delete(f"/api/inspection-items/{pflicht_eigen['id']}").status_code == 200
    assert {p["text"] for p in list_inspection_items(db, report_id)} & {"Dachluke geprüft", "Steigleiter geprüft"} == set()


def test_seite_knopf_nur_am_eigenen_punkt_mit_rueckfrage():
    # seit 1.9.67 auf der Berichtsseite: „Prüfpunkt löschen“ im Menü „⋮“ des Punkts (Einträge 48 px), Rückfrage im Dialog der Seite
    text, _ = seitentext("service_report.html")
    assert ("(p.template_item_id==null?'<button type=\"button\" class=\"ds-menue-eintrag ds-menue-eintrag-fehler\" "
            "data-klick=\"punkt-loeschen\"") in text
    loeschen = text[text.index("aktion('punkt-loeschen'"):text.index("// --- Befunde")]
    assert "confirm(" not in loeschen and "rueckfrage('Prüfpunkt löschen?','Prüfpunkt „'+(p?p.text:'')+'“ löschen?','Löschen')" in loeschen
    assert '<dialog id="rueckfrageDialog" class="dialog-karte"' in text
    assert ".menue-anker .ds-menue-eintrag{height:48px;min-height:48px;" in text
