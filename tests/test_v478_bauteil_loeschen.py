"""Seit 1.9.51 (Stufe 4, R2 Nachrunde, Nebenbefund aus R2): ein Bauteil, auf das ein Prüfpunkt verweist, lässt sich nicht löschen --
wie der Vorlagenpunkt seit 1.9.43.

    Sperre         DELETE /api/roof-components/{id} 409 mit der Zahl der Berichte, deren Prüfpunkte über roof_component_id auf das
                   Bauteil verweisen (BauteilInBerichten) -- auch im Entwurf; Bauteil und Verweise bleiben, kein ON DELETE SET NULL
                   oder CASCADE
    bis 1.9.50     sperrte nur ein unterschriebener Bericht; der Prüfpunkt eines Entwurfs lief unter PostgreSQL in den Fremdschlüssel
                   (500), unter SQLite blieb ein Verweis ins Leere
    frei           ein Bauteil ohne Prüfpunkt lässt sich weiter löschen, archivieren geht immer
"""

import pytest
from sqlalchemy import select

from app.models import InspectionItem, RoofComponent
from app.roof_areas import BauteilInBerichten, create_roof_area, create_roof_component, delete_roof_component, set_roof_component_archived
from app.routers.roof_areas import router as roof_areas_router
from app.service_reports import create_report
from tests.befund_vor_echtbetrieb import pg_sitzung
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import _seed_test_template
from tests.test_v325_contract_basis import beauftragen, make_quote


def _bauteil_mit_berichten(db, berichte: int):
    """Testvorlage mit Punkten für Gullys, ein Gully an der Dachfläche, dazu `berichte` Wartungsberichte (Entwürfe) aus ihr an einem Auftrag
    (über Angebot und Beauftragen, läuft auch unter PostgreSQL)."""
    _seed_test_template(db)
    _, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    gully = create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0478"))
    order.project.property_id = prop.id  # seit 1.8.70: Dachflächen nur aus dem Objekt des Auftrags
    db.commit()
    for _ in range(berichte):
        create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    return area, gully


def _verweise(db, bauteil_id):
    return sorted(db.scalars(select(InspectionItem.id).where(InspectionItem.roof_component_id == bauteil_id)).all())


@pytest.mark.parametrize("berichte, wo", [(1, "einem Einsatzbericht"), (2, "2 Einsatzberichten")], ids=["ein_bericht", "zwei_berichte"])
def test_bauteil_in_entwuerfen_409(threaded_db_session, router_test_client, berichte, wo):
    """Angriff: das Bauteil steckt in Prüfpunkten von Entwürfen -- 409 mit Anzahl; Bauteil und Verweise unverändert."""
    db = threaded_db_session
    _, gully = _bauteil_mit_berichten(db, berichte)
    verweise = _verweise(db, gully["id"])
    assert len(verweise) == 2 * berichte  # zwei Gully-Punkte der Testvorlage je Bericht
    antwort = router_test_client(db, roof_areas_router).delete(f"/api/roof-components/{gully['id']}")
    assert antwort.status_code == 409, antwort.text
    assert antwort.json()["detail"] == f"Dieses Bauteil steckt in {wo} und lässt sich deshalb nicht löschen. Archivieren geht weiter."
    db.expire_all()
    assert db.get(RoofComponent, gully["id"]) is not None and _verweise(db, gully["id"]) == verweise


def test_bauteil_ohne_pruefpunkt_geloescht_archivieren_geht(threaded_db_session, router_test_client):
    """Gegenprobe: ein Bauteil, das erst nach den Berichten dazukam, steckt in keinem Prüfpunkt -- gelöscht; das gesperrte lässt sich
    archivieren."""
    db = threaded_db_session
    area, gully = _bauteil_mit_berichten(db, 1)
    neu = create_roof_component(db, area["id"], "Gully 2", component_type="Gully", sort_order=20)
    client = router_test_client(db, roof_areas_router)
    assert client.delete(f"/api/roof-components/{neu['id']}").status_code == 200
    db.expire_all()
    assert db.get(RoofComponent, neu["id"]) is None
    assert set_roof_component_archived(db, gully["id"], True)["archived"] is True


def test_unter_postgresql_kein_500():
    """Unter PostgreSQL (dort griff bis 1.9.50 der Fremdschlüssel, 500): Sperre statt IntegrityError, die Sitzung bleibt brauchbar."""
    with pg_sitzung("bauteil") as db:
        area, gully = _bauteil_mit_berichten(db, 2)
        verweise = _verweise(db, gully["id"])
        with pytest.raises(BauteilInBerichten) as fehler:
            delete_roof_component(db, gully["id"])
        assert fehler.value.berichte == 2
        assert db.get(RoofComponent, gully["id"]) is not None and _verweise(db, gully["id"]) == verweise
        neu = create_roof_component(db, area["id"], "Gully 2", component_type="Gully", sort_order=20)
        assert delete_roof_component(db, neu["id"]) is True
