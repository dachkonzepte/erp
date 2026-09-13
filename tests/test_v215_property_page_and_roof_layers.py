from datetime import date

from app.maintenance_contracts import create_contract, list_contracts_for_property
from app.models import RoofArea
from app.roof_areas import (
    create_layer_type, create_roof_area, create_roof_areas_bulk, delete_layer_type,
    list_layer_types, list_roof_layers, update_layer_type, update_roof_area,
    upsert_roof_layer,
)
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property, make_template_project


def _seed_layer_types(db):
    """Eine frische :memory:-Testdatenbank (Base.metadata.create_all()) enthält die
    Migrations-Seed-Zeilen für roof_layer_types NICHT, nur echte Alembic-Läufe gegen die
    Datei-Datenbank tun das (gleiches Prinzip wie test_v212_maintenance_windows.py für
    MaintenanceWindow) -- die für die Tests relevanten Schichttypen werden deshalb hier selbst
    angelegt."""
    create_layer_type(db, "test_steildach_unterspannbahn", "Unterspannbahn", roof_type="Steildach", option_group="layer_unterspannbahn")
    create_layer_type(db, "test_steildach_aufsparrendaemmung", "Aufsparrendämmung", roof_type="Steildach", option_group="layer_daemmung", has_thickness=True)
    create_layer_type(db, "test_flachdach_dampfsperre", "Dampfsperre", roof_type="Flachdach", option_group="layer_dampfsperre")
    create_layer_type(db, "test_flachdach_daemmung", "Dämmung", roof_type="Flachdach", option_group="layer_daemmung", has_thickness=True)
    create_layer_type(db, "test_flachdach_gefaelledaemmung", "Gefälledämmung", roof_type="Flachdach", option_group="layer_daemmung", has_thickness=True)
    create_layer_type(db, "test_flachdach_abdichtung", "Abdichtung", roof_type="Flachdach", option_group="layer_abdichtung")


def test_roof_area_to_dict_still_returns_property_id_for_breadcrumb():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    assert area["property_id"] == prop.id
    assert area["property_name"] == prop.name
    assert area["customer_id"] == customer.id


def test_create_roof_areas_bulk_creates_several_and_skips_blanks():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    result = create_roof_areas_bulk(db, prop.id, "Flachdach", ["Dach A", "  ", "Dach B", "", "Dach C"])
    assert [r["name"] for r in result] == ["Dach A", "Dach B", "Dach C"]
    assert all(r["roof_type"] == "Flachdach" for r in result)


def test_create_roof_areas_bulk_requires_at_least_one_name():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    try:
        create_roof_areas_bulk(db, prop.id, "Flachdach", ["", "   "])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_list_layer_types_does_not_cross_talk_between_roof_types():
    db = db_session()
    _seed_layer_types(db)
    flachdach_types = {t["label"] for t in list_layer_types(db, roof_type="Flachdach")}
    steildach_types = {t["label"] for t in list_layer_types(db, roof_type="Steildach")}
    assert "Dampfsperre" in flachdach_types
    assert "Gefälledämmung" in flachdach_types
    assert "Unterspannbahn" not in flachdach_types

    assert "Unterspannbahn" in steildach_types
    assert "Aufsparrendämmung" in steildach_types
    assert "Dampfsperre" not in steildach_types


def test_upsert_roof_layer_creates_then_updates_same_row():
    db = db_session()
    _seed_layer_types(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    layer_type = next(t for t in list_layer_types(db, roof_type="Flachdach") if t["label"] == "Dämmung")

    first = upsert_roof_layer(
        db, area["id"], layer_type["id"],
        {"present": True, "execution": "Mineralwolle", "thickness_mm": 160, "notes": "Testnotiz"},
    )
    assert first["present"] is True
    assert first["execution"] == "Mineralwolle"
    assert first["thickness_mm"] == 160

    second = upsert_roof_layer(db, area["id"], layer_type["id"], {"present": True, "execution": "PIR", "thickness_mm": 120})
    assert second["id"] == first["id"]

    layers = list_roof_layers(db, area["id"])
    assert len(layers) == 1
    assert layers[0]["execution"] == "PIR"
    assert layers[0]["thickness_mm"] == 120


def test_roof_type_change_keeps_existing_layer_rows():
    """Beleg für die Rückfrage-Entscheidung: eine erfasste Schicht bleibt nach einem
    Dachtypwechsel stehen, statt gelöscht zu werden."""
    db = db_session()
    _seed_layer_types(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Steildach")
    layer_type = next(t for t in list_layer_types(db, roof_type="Steildach") if t["label"] == "Aufsparrendämmung")
    upsert_roof_layer(db, area["id"], layer_type["id"], {"present": True, "execution": "Mineralwolle", "thickness_mm": 160})

    update_roof_area(db, area["id"], "Hauptdach", roof_type="Flachdach")

    layers = list_roof_layers(db, area["id"])
    assert len(layers) == 1
    assert layers[0]["layer_type_id"] == layer_type["id"]
    assert layers[0]["layer_type_roof_type"] == "Steildach"  # passt nicht mehr zum jetzigen "Flachdach"
    assert layers[0]["execution"] == "Mineralwolle"


def test_delete_layer_type_blocks_when_used_but_deactivate_still_works():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Steildach")
    layer_type = create_layer_type(db, "test_layer_typ", "Testschicht", roof_type="Steildach")
    upsert_roof_layer(db, area["id"], layer_type["id"], {"present": True})

    try:
        delete_layer_type(db, layer_type["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass

    deactivated = update_layer_type(db, layer_type["id"], "Testschicht", roof_type="Steildach")
    assert deactivated is not None  # update bleibt erlaubt
    from app.roof_areas import set_layer_type_active
    result = set_layer_type_active(db, layer_type["id"], False)
    assert result["active"] is False


def test_update_roof_area_does_not_touch_legacy_build_up_and_insulation():
    """Regressionstest für den beim Planen gefundenen Fehler: update_roof_area() darf
    build_up/insulation nicht mehr annehmen, sonst würde ein Speichern über das neue,
    reduzierte Formular den Altbestand-Text stillschweigend löschen."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    row = db.get(RoofArea, area["id"])
    row.build_up = "Alter Freitext aus 2019"
    row.insulation = "Mineralwolle 140mm"
    db.commit()

    updated = update_roof_area(db, area["id"], "Hauptdach umbenannt", contractor="Testfirma")
    assert updated["name"] == "Hauptdach umbenannt"
    assert updated["build_up"] == "Alter Freitext aus 2019"
    assert updated["insulation"] == "Mineralwolle 140mm"


def test_list_contracts_for_property_filters_correctly():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    other_customer, other_prop = make_customer_and_property(db)
    make_template_project(db, customer, prop, number="P-TEMPLATE-0002")
    create_contract(db, customer.id, prop.id, "Vertrag A", 12, date(2026, 1, 1))
    create_contract(db, other_customer.id, other_prop.id, "Vertrag B", 12, date(2026, 1, 1))

    result = list_contracts_for_property(db, prop.id)
    assert len(result) == 1
    assert result[0]["title"] == "Vertrag A"


def test_router_endpoints_bulk_create_and_layer_upsert_and_delete_blocked(threaded_db_session, router_test_client):
    from app.routers.roof_areas import router as roof_areas_router

    db = threaded_db_session
    _seed_layer_types(db)
    customer, prop = make_customer_and_property(db)
    client = router_test_client(db, roof_areas_router)

    bulk_resp = client.post(
        f"/api/properties/{prop.id}/roof-areas/bulk",
        json={"roof_type": "Flachdach", "names": ["Dach 1", "Dach 2"]},
    )
    assert bulk_resp.status_code == 200, bulk_resp.text
    areas = bulk_resp.json()
    assert len(areas) == 2

    types_resp = client.get("/api/roof-layer-types", params={"roof_type": "Flachdach"})
    assert types_resp.status_code == 200
    layer_type_id = next(t["id"] for t in types_resp.json() if t["label"] == "Abdichtung")

    put_resp = client.put(
        f"/api/roof-areas/{areas[0]['id']}/layers/{layer_type_id}",
        json={"present": True, "execution": "EPDM", "thickness_mm": None, "notes": None},
    )
    assert put_resp.status_code == 200, put_resp.text

    get_resp = client.get(f"/api/roof-areas/{areas[0]['id']}/layers")
    assert get_resp.status_code == 200
    assert any(l["layer_type_id"] == layer_type_id and l["execution"] == "EPDM" for l in get_resp.json())

    delete_resp = client.delete(f"/api/roof-layer-types/{layer_type_id}")
    assert delete_resp.status_code == 400
