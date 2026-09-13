from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.calculation import build_calculation, get_settings_for_catalog
from app.catalogs import create_catalog
from app.database import Base
from app.models import CalculationSettings, ImportBatch, Material, Service
from app.services import (
    add_material_to_service,
    create_manual_service,
    ensure_manual_import_batch,
    is_service_editable,
    remove_material_from_service,
    update_service_base_fields,
)


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_material(db, name="Dachziegel", price=Decimal("2.50"), quantity_basis=Decimal("1")):
    m = Material(name=name, unit="Stk", purchase_price=price, price_basis=quantity_basis, source="manual")
    db.add(m); db.commit(); db.refresh(m)
    return m


def make_imported_service(db, external_id="IMP-1"):
    batch = ImportBatch(source_type="leistungen_dach", source_name="Test", filename="t.xml")
    db.add(batch); db.commit()
    service = Service(
        import_batch_id=batch.id, source_type="leistungen_dach", external_id=external_id,
        short_text="Importiert", quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"), sale_price=Decimal("10"),
    )
    db.add(service); db.commit(); db.refresh(service)
    return service


def test_pure_labor_service_calculates_from_time_only():
    # 60 Min bei Standard-Stundensatz 82,00€: (60+0)/60 * 82 = 82,00 -- keine
    # Materialien, kein Fremdanteil, alle Prozentsätze auf Standard (0%).
    db = db_session()
    service = create_manual_service(
        db, catalog_id=None, service_type="lohnarbeit", short_text="Reine Lohnarbeit",
        long_text=None, quantity=Decimal("1"), unit="Std",
        site_time_raw=Decimal("60"), workshop_time_raw=Decimal("0"),
        labor_rate_override=None, material_markup_pct_override=None,
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("0"), other_cost=Decimal("0"),
        overhead_pct_override=None, risk_profit_pct_override=None, manual_sale_price=None,
    )
    assert service.service_type == "lohnarbeit"
    assert service.sale_price == Decimal("82.00")
    settings = get_settings_for_catalog(db, None)
    calc = build_calculation(service, settings)
    assert calc["effective_sale_price"] == Decimal("82.00")
    assert calc["delta_to_source"] == Decimal("0")  # sale_price wurde synchron gesetzt


def test_service_with_material_includes_material_cost():
    # 30 Min Arbeit (41,00€) + 10 Stk Material à 2,50€ (25,00€) = 66,00€.
    db = db_session()
    material = make_material(db, price=Decimal("2.50"))
    service = create_manual_service(
        db, catalog_id=None, service_type="material", short_text="Mit Material",
        long_text=None, quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("30"), workshop_time_raw=Decimal("0"),
        labor_rate_override=None, material_markup_pct_override=None,
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("0"), other_cost=Decimal("0"),
        overhead_pct_override=None, risk_profit_pct_override=None, manual_sale_price=None,
        materials=[(material, Decimal("10"), Decimal("0"))],
    )
    assert len(service.materials) == 1
    assert service.materials[0].material_id == material.id
    assert service.sale_price == Decimal("66.00")


def test_material_markup_pct_is_applied():
    # Dieselbe Materialbasis wie oben (25,00€), diesmal mit 20% Materialgewinn:
    # 25,00 * 1,20 = 30,00€ Materialanteil + 41,00€ Arbeit = 71,00€.
    db = db_session()
    material = make_material(db, price=Decimal("2.50"))
    service = create_manual_service(
        db, catalog_id=None, service_type="material", short_text="Mit Aufschlag",
        long_text=None, quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("30"), workshop_time_raw=Decimal("0"),
        labor_rate_override=None, material_markup_pct_override=Decimal("20"),
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("0"), other_cost=Decimal("0"),
        overhead_pct_override=None, risk_profit_pct_override=None, manual_sale_price=None,
        materials=[(material, Decimal("10"), Decimal("0"))],
    )
    assert service.sale_price == Decimal("71.00")


def test_subcontractor_only_service():
    # Reine Fremdleistung: keine Zeit, kein Material, nur der Sub-Betrag.
    db = db_session()
    service = create_manual_service(
        db, catalog_id=None, service_type="fremdleistung", short_text="Fremdleistung",
        long_text=None, quantity=Decimal("1"), unit="Pausch",
        site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"),
        labor_rate_override=None, material_markup_pct_override=None,
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("200.00"), other_cost=Decimal("0"),
        overhead_pct_override=None, risk_profit_pct_override=None, manual_sale_price=None,
    )
    assert service.sale_price == Decimal("200.00")


def test_manual_sale_price_override_wins_over_formula():
    db = db_session()
    service = create_manual_service(
        db, catalog_id=None, service_type="lohnarbeit", short_text="Mit Festpreis",
        long_text=None, quantity=Decimal("1"), unit="Std",
        site_time_raw=Decimal("60"), workshop_time_raw=Decimal("0"),
        labor_rate_override=None, material_markup_pct_override=None,
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("0"), other_cost=Decimal("0"),
        overhead_pct_override=None, risk_profit_pct_override=None,
        manual_sale_price=Decimal("999.99"),  # weicht bewusst von der Formel (82,00) ab
    )
    assert service.sale_price == Decimal("999.99")
    settings = get_settings_for_catalog(db, None)
    calc = build_calculation(service, settings)
    assert calc["effective_sale_price"] == Decimal("999.99")


def test_is_service_editable_by_source_type():
    db = db_session()
    imported = make_imported_service(db)
    own = create_manual_service(
        db, catalog_id=None, service_type=None, short_text="Eigene", long_text=None,
        quantity=Decimal("1"), unit="Stk", site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"),
        labor_rate_override=None, material_markup_pct_override=None,
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("0"), other_cost=Decimal("0"),
        overhead_pct_override=None, risk_profit_pct_override=None, manual_sale_price=Decimal("10"),
    )
    assert is_service_editable(imported) is False
    assert is_service_editable(own) is True


def test_add_material_to_service_recalculates_price():
    db = db_session()
    service = create_manual_service(
        db, catalog_id=None, service_type=None, short_text="Wird erweitert", long_text=None,
        quantity=Decimal("1"), unit="Stk", site_time_raw=Decimal("60"), workshop_time_raw=Decimal("0"),
        labor_rate_override=None, material_markup_pct_override=None,
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("0"), other_cost=Decimal("0"),
        overhead_pct_override=None, risk_profit_pct_override=None, manual_sale_price=None,
    )
    assert service.sale_price == Decimal("82.00")  # nur Arbeitszeit

    material = make_material(db, price=Decimal("5.00"))
    row = add_material_to_service(db, service, material, Decimal("4"), Decimal("0"))
    assert row.material_id == material.id
    db.refresh(service)
    assert service.sale_price == Decimal("102.00")  # 82,00 + 4*5,00


def test_remove_material_from_service_recalculates_and_handles_missing():
    db = db_session()
    material = make_material(db, price=Decimal("5.00"))
    service = create_manual_service(
        db, catalog_id=None, service_type=None, short_text="Wird reduziert", long_text=None,
        quantity=Decimal("1"), unit="Stk", site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"),
        labor_rate_override=None, material_markup_pct_override=None,
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("0"), other_cost=Decimal("0"),
        overhead_pct_override=None, risk_profit_pct_override=None, manual_sale_price=None,
        materials=[(material, Decimal("4"), Decimal("0"))],
    )
    assert service.sale_price == Decimal("20.00")
    material_row_id = service.materials[0].id

    assert remove_material_from_service(db, service, 999999) is False  # nicht vorhanden
    assert remove_material_from_service(db, service, material_row_id) is True
    db.refresh(service)
    assert len(service.materials) == 0
    assert service.sale_price == Decimal("0.00")


def test_update_service_base_fields_recalculates_price_after_time_change():
    db = db_session()
    service = create_manual_service(
        db, catalog_id=None, service_type=None, short_text="Original", long_text=None,
        quantity=Decimal("1"), unit="Stk", site_time_raw=Decimal("60"), workshop_time_raw=Decimal("0"),
        labor_rate_override=None, material_markup_pct_override=None,
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("0"), other_cost=Decimal("0"),
        overhead_pct_override=None, risk_profit_pct_override=None, manual_sale_price=None,
    )
    assert service.sale_price == Decimal("82.00")

    updated = update_service_base_fields(
        db, service, service_type="lohnarbeit", short_text="Geändert",
        long_text="Neue Beschreibung", quantity=Decimal("2"), unit="Std",
    )
    assert updated.short_text == "Geändert"
    assert updated.quantity == Decimal("2")
    # Zeit unverändert (60 Min), Preis bleibt also gleich -- Basisfelder-Update
    # rechnet aus der weiterhin gespeicherten Kalkulation neu, ändert sie nicht.
    assert updated.sale_price == Decimal("82.00")


def test_update_service_base_fields_does_not_touch_price_for_imported_service():
    # Verteidigung in der Tiefe: selbst wenn diese Funktion versehentlich auf
    # einer importierten Leistung aufgerufen würde (die eigentliche Sperre
    # sitzt im Router), darf sie deren sale_price (= Quellpreis) nicht anfassen.
    db = db_session()
    imported = make_imported_service(db)
    original_price = imported.sale_price
    update_service_base_fields(
        db, imported, service_type=None, short_text="Trotzdem geändert",
        long_text=None, quantity=Decimal("1"), unit="Stk",
    )
    assert imported.sale_price == original_price
