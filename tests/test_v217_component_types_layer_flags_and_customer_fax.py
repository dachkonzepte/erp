"""Version 1.2.19 -- Punkt 5 (RoofLayerType-Flags has_execution/has_notes), Punkt 6
(RoofComponentType als echte Tabelle, Migrations-Übernahme aus setting_options, flächige
Bauteile auf der Skizze), Punkt 7 (Customer.fax)."""

import importlib.util
from decimal import Decimal
from pathlib import Path

from app.inspection_templates import create_template, create_template_item
from app.models import SettingOption, SettingOptionGroup
from app.roof_areas import (
    create_component_type, create_layer_type, create_roof_area, create_roof_component,
    delete_component_type, list_component_types, list_layer_types, reorder_component_types,
    set_component_type_active, set_roof_component_position, update_component_type, update_layer_type,
)
from app.routers.customers import create_customer, update_customer
from app.schemas import CustomerCreate, CustomerUpdate
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property


def _migration_module():
    path = next(Path(__file__).resolve().parents[1].glob(
        "alembic/versions/*_punkt2_5_6_7_settings_layertype_flags_*.py"
    ))
    spec = importlib.util.spec_from_file_location("migration_1219_component_types", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Punkt 6, Migration: setting_options statt Code-Konstante ---

def test_migration_picks_up_custom_option_added_before_migration():
    """Geforderter Test: eine zusätzliche, vor der Migration selbst angelegte Option landet
    danach als RoofComponentType -- die Migration darf nicht blind aus
    DEFAULT_OPTION_GROUPS lesen, sonst würde genau diese Zeile verschwinden."""
    db = db_session()
    group = SettingOptionGroup(group_key="roof_component_types", label="Bauteiltyp", sort_order=73)
    db.add(group); db.flush()
    db.add_all([
        SettingOption(group_id=group.id, label="Gully", value="Gully", sort_order=10, active=True),
        SettingOption(group_id=group.id, label="Eigene Bauteilart", value="Eigene Bauteilart", sort_order=999, active=True),
        SettingOption(group_id=group.id, label="Deaktivierte Bauteilart", value="Deaktivierte Bauteilart", sort_order=998, active=False),
    ])
    db.commit()

    rows = _migration_module()._resolve_roof_component_type_rows(db.connection())
    values = {value for _, _, value in rows}
    assert "Eigene Bauteilart" in values
    assert "Gully" in values
    assert "Deaktivierte Bauteilart" not in values  # nur aktive Optionen werden übernommen


def test_migration_falls_back_to_code_defaults_when_group_never_seeded():
    """Eine frische DB, die roof_component_types nie gesät hat, fällt auf die 15 Code-Werte
    zurück -- keine leere Bauteilarten-Liste nach der Migration."""
    db = db_session()
    rows = _migration_module()._resolve_roof_component_type_rows(db.connection())
    values = {value for _, _, value in rows}
    assert len(rows) == 15
    assert "Photovoltaik" in values
    assert "Gully" in values


# --- Punkt 5: has_execution/has_thickness/has_notes ---

def test_layer_type_flags_roundtrip_through_create_update_and_list():
    db = db_session()
    created = create_layer_type(
        db, "test_ohne_ausfuehrung", "Trennlage", roof_type="Flachdach",
        has_execution=False, has_thickness=False, has_notes=True,
    )
    assert created["has_execution"] is False
    assert created["has_thickness"] is False
    assert created["has_notes"] is True

    updated = update_layer_type(
        db, created["id"], "Trennlage", roof_type="Flachdach",
        has_execution=True, has_thickness=True, has_notes=False,
    )
    assert updated["has_execution"] is True
    assert updated["has_thickness"] is True
    assert updated["has_notes"] is False

    listed = {t["id"]: t for t in list_layer_types(db, roof_type="Flachdach")}
    assert listed[created["id"]]["has_notes"] is False


# --- Punkt 6: RoofComponentType-CRUD ---

def test_component_type_crud_and_reorder():
    db = db_session()
    a = create_component_type(db, "Gully", "Gully", is_area=False)
    b = create_component_type(db, "Photovoltaik", "Photovoltaik", is_area=True)
    assert a["is_area"] is False
    assert b["is_area"] is True

    updated = update_component_type(db, a["id"], "Gully (aktualisiert)", is_area=False)
    assert updated["label"] == "Gully (aktualisiert)"

    deactivated = set_component_type_active(db, b["id"], False)
    assert deactivated["active"] is False
    assert b["id"] not in {t["id"] for t in list_component_types(db)}  # nicht mehr in der Standardliste
    assert b["id"] in {t["id"] for t in list_component_types(db, include_inactive=True)}

    reordered = reorder_component_types(db, [b["id"], a["id"]])
    assert [t["id"] for t in reordered] == [b["id"], a["id"]]


def test_delete_component_type_blocks_when_used_by_component_or_template_item():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    component_type = create_component_type(db, "Gully", "Gully")
    create_roof_component(db, area["id"], "Gully Nordost", component_type="Gully")

    try:
        delete_component_type(db, component_type["id"])
        assert False, "sollte ValueError auslösen (von RoofComponent verwendet)"
    except ValueError as exc:
        assert "Bauteil" in str(exc)

    # Deaktivieren bleibt uneingeschränkt möglich, auch wenn die Bauteilart verwendet wird.
    deactivated = set_component_type_active(db, component_type["id"], False)
    assert deactivated["active"] is False

    other_type = create_component_type(db, "Notueberlauf", "Notüberlauf")
    template = create_template(db, "Testvorlage")
    create_template_item(db, template["id"], "Prüfpunkt", "ja_nein", component_type="Notueberlauf")
    try:
        delete_component_type(db, other_type["id"])
        assert False, "sollte ValueError auslösen (von InspectionTemplateItem verwendet)"
    except ValueError as exc:
        assert "Prüfvorlage" in str(exc)


def test_set_roof_component_position_supports_point_and_rectangle():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    component = create_roof_component(db, area["id"], "Gully Nordost", component_type="Gully")

    point = set_roof_component_position(db, component["id"], Decimal("10.5"), Decimal("20.5"))
    assert point["sketch_x"] == Decimal("10.5")
    assert point["sketch_w"] is None  # Punktmarker: keine Ausdehnung

    rect = set_roof_component_position(
        db, component["id"], Decimal("5.0"), Decimal("6.0"), sketch_w=Decimal("30.0"), sketch_h=Decimal("15.0"),
    )
    assert rect["sketch_w"] == Decimal("30.0")
    assert rect["sketch_h"] == Decimal("15.0")

    # Erneutes Ziehen ersetzt das Rechteck durch einen Punktmarker (beide None).
    back_to_point = set_roof_component_position(db, component["id"], Decimal("1.0"), Decimal("2.0"))
    assert back_to_point["sketch_w"] is None and back_to_point["sketch_h"] is None


# --- Punkt 7: Customer.fax ---

def test_customer_fax_roundtrip_via_create_and_update():
    db = db_session()
    created = create_customer(CustomerCreate(last_name="Testkunde GmbH", fax="02451-123456"), db)
    assert created.fax == "02451-123456"

    updated = update_customer(
        created.id, CustomerUpdate(last_name="Testkunde GmbH", fax="02451-999999"), db,
    )
    assert updated.fax == "02451-999999"
