"""Seit 1.9.54 (Stufe 4, R2 Nachrunde 2, Punkt 2): eine Dachfläche, die ein Einsatzbericht nennt, lässt sich nicht löschen -- dieselbe Regel
wie beim Bauteil seit 1.9.51.

    Sperre         DELETE /api/roof-areas/{id} 409 mit der Zahl der Berichte, die die Fläche nennen: als ihre Fläche, an einem Prüfpunkt oder
                   Material, oder über eines ihrer Bauteile an einem Prüfpunkt oder Befund (DachflaecheInBerichten) -- auch im Entwurf;
                   Fläche, Bauteile und Verweise bleiben, kein ON DELETE SET NULL oder CASCADE
    bis 1.9.53     keine Prüfung der Berichte; das Löschen riss die Bauteile per Kaskade mit -- unter PostgreSQL 500 am Fremdschlüssel,
                   unter SQLite Verweise ins Leere
    frei           eine Fläche ohne Bericht lässt sich weiter löschen (samt Bauteilen), archivieren geht immer; Wartungsvertrag, Abnahme
                   und Mangel sperren wie bisher (400)
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.findings import create_finding
from app.models import Finding, InspectionItem, RoofArea, RoofComponent, ServiceReportRoofArea
from app.roof_areas import (
    DachflaecheInBerichten, create_roof_area, create_roof_component, delete_roof_area, set_roof_area_archived,
)
from app.routers.roof_areas import router as roof_areas_router
from app.service_reports import add_material, create_report
from tests.befund_vor_echtbetrieb import pg_sitzung
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import _seed_test_template
from tests.test_v325_contract_basis import beauftragen, make_quote


def _welt(db):
    """Testvorlage mit Punkten für Gullys, Objekt mit Dachfläche und Gully, ein Auftrag am Objekt (über Angebot und Beauftragen, läuft auch
    unter PostgreSQL)."""
    _seed_test_template(db)
    _, prop = make_customer_and_property(db)
    flaeche = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    gully = create_roof_component(db, flaeche["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0481"))
    order.project.property_id = prop.id  # seit 1.8.70: Dachflächen nur aus dem Objekt des Auftrags
    db.commit()
    return prop, flaeche, gully, order


def _stand(db, flaeche_id, gully_id):
    """Was nicht verloren gehen darf: Fläche, Bauteil, Verweise der Berichte, Prüfpunkte, Befunde."""
    return (db.get(RoofArea, flaeche_id) is not None, db.get(RoofComponent, gully_id) is not None,
            sorted(db.scalars(select(ServiceReportRoofArea.id).where(ServiceReportRoofArea.roof_area_id == flaeche_id)).all()),
            sorted(db.scalars(select(InspectionItem.id).where((InspectionItem.roof_area_id == flaeche_id)
                                                              | (InspectionItem.roof_component_id == gully_id))).all()),
            sorted(db.scalars(select(Finding.id).where(Finding.roof_component_id == gully_id)).all()))


@pytest.mark.parametrize("berichte, wo", [(1, "einem Einsatzbericht"), (2, "2 Einsatzberichten")], ids=["ein_bericht", "zwei_berichte"])
def test_flaeche_mit_bericht_409(threaded_db_session, router_test_client, berichte, wo):
    """Angriff: Wartungsberichte (Entwürfe) an der Fläche -- 409 mit Anzahl; Fläche, Bauteil, Verweise und Prüfpunkte unverändert."""
    db = threaded_db_session
    _, flaeche, gully, order = _welt(db)
    for _ in range(berichte):
        create_report(db, order.id, "wartung", roof_area_ids=[flaeche["id"]])
    vorher = _stand(db, flaeche["id"], gully["id"])
    assert len(vorher[2]) == berichte and vorher[3]
    antwort = router_test_client(db, roof_areas_router).delete(f"/api/roof-areas/{flaeche['id']}")
    assert antwort.status_code == 409, antwort.text
    assert antwort.json()["detail"] == f"Diese Dachfläche steckt in {wo} und lässt sich deshalb nicht löschen. Archivieren geht weiter."
    db.expire_all()
    assert _stand(db, flaeche["id"], gully["id"]) == vorher


def test_befund_am_bauteil_sperrt_die_flaeche(threaded_db_session, router_test_client):
    """Angriff: ein Bericht ohne Fläche, nur ein Befund an ihrem Gully -- auch das sperrt (409, ein Bericht)."""
    db = threaded_db_session
    _, flaeche, gully, order = _welt(db)
    bericht = create_report(db, order.id, "rapport")
    create_finding(db, bericht["id"], "Gully verstopft", "gering", "sofort_behoben", roof_component_id=gully["id"])
    vorher = _stand(db, flaeche["id"], gully["id"])
    antwort = router_test_client(db, roof_areas_router).delete(f"/api/roof-areas/{flaeche['id']}")
    assert antwort.status_code == 409 and "einem Einsatzbericht" in antwort.json()["detail"]
    db.expire_all()
    assert _stand(db, flaeche["id"], gully["id"]) == vorher


def test_material_an_der_flaeche_sperrt(threaded_db_session):
    """Angriff: ein Bericht ohne Fläche, nur Material an ihr gebucht -- auch das sperrt."""
    db = threaded_db_session
    _, flaeche, _, order = _welt(db)
    bericht = create_report(db, order.id, "rapport")
    add_material(db, bericht["id"], description="Dachbahn", quantity=Decimal("2"), unit="m²", roof_area_id=flaeche["id"])
    with pytest.raises(DachflaecheInBerichten) as fehler:
        delete_roof_area(db, flaeche["id"])
    assert fehler.value.berichte == 1


def test_flaeche_ohne_bericht_geloescht_archivieren_geht(threaded_db_session, router_test_client):
    """Gegenprobe: ohne Bericht -- gelöscht, samt Bauteil; eine gesperrte Fläche lässt sich archivieren."""
    db = threaded_db_session
    prop, flaeche, gully, order = _welt(db)
    client = router_test_client(db, roof_areas_router)
    assert client.delete(f"/api/roof-areas/{flaeche['id']}").status_code == 200
    db.expire_all()
    assert db.get(RoofArea, flaeche["id"]) is None and db.get(RoofComponent, gully["id"]) is None
    zweite = create_roof_area(db, prop.id, "Anbau", roof_type="Flachdach")
    create_report(db, order.id, "wartung", roof_area_ids=[zweite["id"]])
    assert client.delete(f"/api/roof-areas/{zweite['id']}").status_code == 409
    assert set_roof_area_archived(db, zweite["id"], True)["archived"] is True


def test_unter_postgresql_kein_500():
    """Unter PostgreSQL (dort griff bis 1.9.53 der Fremdschlüssel, 500): Sperre statt IntegrityError, die Sitzung bleibt brauchbar."""
    with pg_sitzung("dachflaeche") as db:
        prop, flaeche, gully, order = _welt(db)
        create_report(db, order.id, "wartung", roof_area_ids=[flaeche["id"]])
        vorher = _stand(db, flaeche["id"], gully["id"])
        with pytest.raises(DachflaecheInBerichten) as fehler:
            delete_roof_area(db, flaeche["id"])
        assert fehler.value.berichte == 1
        assert _stand(db, flaeche["id"], gully["id"]) == vorher
        frei = create_roof_area(db, prop.id, "Anbau", roof_type="Flachdach")
        create_roof_component(db, frei["id"], "Gully 2", component_type="Gully", sort_order=10)
        assert delete_roof_area(db, frei["id"]) is True
