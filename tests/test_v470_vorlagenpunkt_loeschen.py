"""Seit 1.9.43 (Stufe 4, R2, Punkt 7): ein Vorlagenpunkt, der in Einsatzberichten steckt, lässt sich nicht löschen.

    Sperre         DELETE /api/inspection-template-items/{id} 409 mit der Zahl der Berichte, deren Prüfpunkte über template_item_id auf
                   ihn verweisen (VorlagenpunktInBerichten); Punkt, Version der Vorlage und Verweise bleiben -- kein ON DELETE SET NULL
                   oder CASCADE, template_item_id eines Punkts aus der Vorlage wird nie leer (daran erkennt der Bericht ihn, 1.9.41)
    bis 1.9.42     unter PostgreSQL 500 am Fremdschlüssel, unter SQLite ein Verweis ins Leere (der Punkt galt danach als "von Hand")
    frei           ein Punkt ohne Bericht lässt sich weiter löschen
"""

from sqlalchemy import select

import pytest

from app.inspection_templates import VorlagenpunktInBerichten, create_template_item, delete_template_item, get_template
from app.models import InspectionItem, InspectionTemplateItem
from app.roof_areas import create_roof_area
from app.routers.inspection_templates import router as inspection_templates_router
from app.service_reports import create_report
from tests.befund_vor_echtbetrieb import pg_sitzung
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import _seed_test_template
from tests.test_v325_contract_basis import beauftragen, make_quote


def _vorlage_mit_berichten(db, berichte: int):
    """Testvorlage, dazu `berichte` Wartungsberichte aus ihr an einem Auftrag (über Angebot und Beauftragen, läuft auch unter PostgreSQL)."""
    vorlage = _seed_test_template(db)
    _, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0470"))
    order.project.property_id = prop.id  # seit 1.8.70: Dachflächen nur aus dem Objekt des Auftrags
    db.commit()
    for _ in range(berichte):
        create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    punkt = next(p for p in vorlage["items"] if p["text"] == "Zugang und Absturzsicherung geprüft")
    return vorlage, punkt


def _verweise(db, punkt_id):
    return sorted(db.scalars(select(InspectionItem.id).where(InspectionItem.template_item_id == punkt_id)).all())


@pytest.mark.parametrize("berichte, wo", [(1, "einem Einsatzbericht"), (2, "2 Einsatzberichten")], ids=["ein_bericht", "zwei_berichte"])
def test_punkt_in_berichten_409(threaded_db_session, router_test_client, berichte, wo):
    """Angriff: der Punkt steckt in Berichten -- 409 mit Anzahl; Punkt, Version und Verweise unverändert."""
    db = threaded_db_session
    vorlage, punkt = _vorlage_mit_berichten(db, berichte)
    verweise = _verweise(db, punkt["id"])
    assert len(verweise) == berichte
    client = router_test_client(db, inspection_templates_router)
    antwort = client.delete(f"/api/inspection-template-items/{punkt['id']}")
    assert antwort.status_code == 409, antwort.text
    assert antwort.json()["detail"] == (f"Dieser Prüfpunkt steckt in {wo} und lässt sich deshalb nicht löschen. "
                                        "Für neue Berichte ohne ihn: Vorlage kopieren und den Punkt in der Kopie löschen.")
    db.expire_all()
    assert db.get(InspectionTemplateItem, punkt["id"]) is not None
    assert get_template(db, vorlage["id"])["version"] == vorlage["version"]
    assert _verweise(db, punkt["id"]) == verweise


def test_punkt_ohne_bericht_geloescht(threaded_db_session, router_test_client):
    """Gegenprobe: derselbe Aufbau, ein neuer Punkt steckt in keinem Bericht -- gelöscht, Version eins weiter."""
    db = threaded_db_session
    vorlage, _ = _vorlage_mit_berichten(db, 1)
    neu = create_template_item(db, vorlage["id"], "Steigleiter geprüft", "ja_nein")
    version = get_template(db, vorlage["id"])["version"]
    client = router_test_client(db, inspection_templates_router)
    assert client.delete(f"/api/inspection-template-items/{neu['id']}").status_code == 200
    db.expire_all()
    assert db.get(InspectionTemplateItem, neu["id"]) is None
    assert get_template(db, vorlage["id"])["version"] == version + 1


def test_unter_postgresql_kein_500():
    """Unter PostgreSQL (dort griff bis 1.9.42 der Fremdschlüssel, 500): Sperre statt IntegrityError, die Sitzung bleibt brauchbar."""
    with pg_sitzung("vorlagenpunkt") as db:
        vorlage, punkt = _vorlage_mit_berichten(db, 2)
        verweise = _verweise(db, punkt["id"])
        with pytest.raises(VorlagenpunktInBerichten) as fehler:
            delete_template_item(db, punkt["id"])
        assert fehler.value.berichte == 2
        assert db.get(InspectionTemplateItem, punkt["id"]) is not None and _verweise(db, punkt["id"]) == verweise
        neu = create_template_item(db, vorlage["id"], "Steigleiter geprüft", "ja_nein")
        assert delete_template_item(db, neu["id"]) is True
