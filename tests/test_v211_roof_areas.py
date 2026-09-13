from decimal import Decimal

from app import roof_area_sketches
from app.models import Property, RoofArea, RoofComponent
from app.roof_areas import (
    create_roof_area, create_roof_component, delete_roof_area, delete_roof_component,
    get_roof_area, list_roof_areas, list_roof_components, set_roof_area_archived,
    set_roof_area_sketch, set_roof_component_archived, set_roof_component_position,
    update_roof_area, update_roof_component,
)
from app.routers.settings import get_setting_option_group
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property


def test_property_with_two_roof_areas_and_five_components_each_is_buildable():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area1 = create_roof_area(db, prop.id, "Hauptdach Süd", roof_type="Steildach", covering="Ziegel")
    area2 = create_roof_area(db, prop.id, "Nebendach Nord", roof_type="Flachdach", covering="Bitumen zweilagig")

    for area in (area1, area2):
        for i in range(5):
            create_roof_component(db, area["id"], f"Bauteil {i + 1}", component_type="Gully", sort_order=(i + 1) * 10)

    areas = list_roof_areas(db, prop.id)
    assert len(areas) == 2
    assert {a["component_count"] for a in areas} == {5}
    assert sum(len(list_roof_components(db, a["id"])) for a in areas) == 10


def test_list_roof_areas_and_components_hide_archived_by_default():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    component = create_roof_component(db, area["id"], "Gully Nordost")

    set_roof_area_archived(db, area["id"], True)
    assert list_roof_areas(db, prop.id) == []
    assert [a["id"] for a in list_roof_areas(db, prop.id, include_archived=True)] == [area["id"]]

    set_roof_area_archived(db, area["id"], False)
    set_roof_component_archived(db, component["id"], True)
    assert list_roof_components(db, area["id"]) == []
    assert [c["id"] for c in list_roof_components(db, area["id"], include_archived=True)] == [component["id"]]


def test_update_roof_area_and_component_replace_all_fields():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    updated = update_roof_area(
        db, area["id"], "Hauptdach Süd", roof_type="Steildach", covering="Ziegel",
        area_sqm=Decimal("123.45"), notes="Frisch saniert",
    )
    assert updated["name"] == "Hauptdach Süd"
    assert updated["area_sqm"] == Decimal("123.45")
    assert updated["notes"] == "Frisch saniert"

    component = create_roof_component(db, area["id"], "Gully")
    updated_component = update_roof_component(
        db, component["id"], "Gully Nordost", component_type="Gully", quantity=Decimal("2"), unit="Stück", sort_order=50,
    )
    assert updated_component["name"] == "Gully Nordost"
    assert updated_component["sort_order"] == 50


def test_set_roof_component_position_sets_percentage_coordinates():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    component = create_roof_component(db, area["id"], "Gully Nordost")
    assert component["sketch_x"] is None

    positioned = set_roof_component_position(db, component["id"], Decimal("42.50"), Decimal("17.25"))
    assert positioned["sketch_x"] == Decimal("42.50")
    assert positioned["sketch_y"] == Decimal("17.25")


def test_delete_roof_area_removes_sketch_file_and_cascades_components(tmp_path):
    roof_area_sketches.SKETCH_ROOT = tmp_path / "sketches"
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    create_roof_component(db, area["id"], "Gully Nordost")
    set_roof_area_sketch(db, area["id"], "skizze.png", b"fake-image-bytes")

    stored_path = roof_area_sketches.sketch_path(db.get(RoofArea, area["id"]).sketch_path)
    assert stored_path.is_file()

    assert delete_roof_area(db, area["id"]) is True
    assert not stored_path.is_file()
    assert db.query(RoofArea).count() == 0
    assert db.query(RoofComponent).count() == 0


def test_delete_roof_component_works_independently():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    component = create_roof_component(db, area["id"], "Gully Nordost")
    assert delete_roof_component(db, component["id"]) is True
    assert list_roof_components(db, area["id"], include_archived=True) == []


def test_deleting_property_cascades_roof_areas_and_components_rows():
    """Regressionstest für den vom Nutzer explizit angefragten Fall: Property wird aktuell
    nirgends im Produktivcode gelöscht (kein DELETE-Endpunkt, kein db.delete() irgendwo), aber
    Property.roof_areas trägt bewusst cascade="all, delete-orphan" (anders als Property.projects),
    damit ein hypothetisches künftiges db.delete(property) keine verwaisten RoofArea-/
    RoofComponent-Zeilen zurücklässt."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    create_roof_component(db, area["id"], "Gully Nordost")

    property_row = db.get(Property, prop.id)
    db.delete(property_row)
    db.commit()

    assert db.query(RoofArea).count() == 0
    assert db.query(RoofComponent).count() == 0


def test_deleting_property_also_removes_roof_area_sketch_file(tmp_path):
    """Ergänzung: das before_delete-Event auf RoofArea muss auch beim über
    Property.roof_areas kaskadierten Löschweg feuern, nicht nur beim direkten Aufruf von
    delete_roof_area()."""
    roof_area_sketches.SKETCH_ROOT = tmp_path / "sketches"
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    set_roof_area_sketch(db, area["id"], "skizze.png", b"fake-image-bytes")
    stored_path = roof_area_sketches.sketch_path(db.get(RoofArea, area["id"]).sketch_path)
    assert stored_path.is_file()

    property_row = db.get(Property, prop.id)
    db.delete(property_row)
    db.commit()

    assert not stored_path.is_file()


def test_second_sketch_upload_removes_first_file_from_disk(tmp_path):
    """Ein zweiter Upload auf dieselbe RoofArea muss die erste Datei tatsächlich von der
    Festplatte entfernen, nicht nur den DB-Verweis überschreiben."""
    roof_area_sketches.SKETCH_ROOT = tmp_path / "sketches"
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")

    first = set_roof_area_sketch(db, area["id"], "erste.png", b"erstes-bild")
    first_path = roof_area_sketches.sketch_path(db.get(RoofArea, area["id"]).sketch_path)
    assert first_path.is_file()

    second = set_roof_area_sketch(db, area["id"], "zweite.png", b"zweites-bild")
    second_path = roof_area_sketches.sketch_path(db.get(RoofArea, area["id"]).sketch_path)

    assert not first_path.is_file()
    assert second_path.is_file()
    assert second_path != first_path
    assert second["has_sketch"] is True


def test_roof_option_groups_seed_on_first_access_via_the_real_endpoint():
    """Beweist das Selbst-Seeding beim allerersten Zugriff über exakt den Endpunkt, den
    roof_area.html auch verwendet (GET /api/settings/option-groups/{group_key}) -- nicht nur
    einen Aufruf auf bereits vorbereiteten Fixtures."""
    db = db_session()
    roof_types = get_setting_option_group(group_key="roof_types", db=db)
    assert [o["value"] for o in roof_types["options"]] == ["Steildach", "Flachdach", "Gründach", "Terrasse"]
    assert next(o for o in roof_types["options"] if o["is_default"])["value"] == "Steildach"

    coverings = get_setting_option_group(group_key="roof_coverings", db=db)
    assert "Bitumen zweilagig" in [o["value"] for o in coverings["options"]]
    # "roof_component_types" ist seit 1.2.19 keine SettingOptionGroup mehr, sondern eine echte
    # Tabelle (RoofComponentType) -- Selbst-Seeding-Test dafür siehe tests/test_v217_*.py.


def test_get_roof_area_reports_missing_id():
    db = db_session()
    assert get_roof_area(db, 999) is None
