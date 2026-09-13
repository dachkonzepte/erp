from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.calculation import build_calculation, get_or_create_settings
from app.catalogs import create_catalog
from app.database import Base
from app.models import ImportBatch, Material, MaterialCalculationOverride, Service, ServiceCalculation, ServiceMaterial
from app.services import copy_service_to_catalog, ensure_manual_import_batch, new_manual_external_id


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_service(db, external_id="ORIG"):
    batch = ImportBatch(source_type="leistungen_dach", source_name="Test", filename="t.xml")
    db.add(batch); db.commit()
    service = Service(
        import_batch_id=batch.id, source_type="leistungen_dach", external_id=external_id,
        short_text="Testleistung", quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"), sale_price=Decimal("10.00"),
    )
    db.add(service); db.commit(); db.refresh(service)
    return service


def test_manually_created_service_stores_long_text():
    db = db_session()
    batch = ensure_manual_import_batch(db)
    service = Service(
        import_batch_id=batch.id, source_type=batch.source_type, external_id=new_manual_external_id(),
        short_text="Kurz", long_text="Eine ausführliche Beschreibung der Leistung.",
        quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"), sale_price=Decimal("10"),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    assert service.long_text == "Eine ausführliche Beschreibung der Leistung."


def test_manual_service_with_manual_sale_price_has_zero_delta():
    # Deckt genau den gemeldeten Fehler ab: eine manuell erfasste Leistung
    # wurde bislang gegen einen aus ihrer (oft nur groben oder fehlenden)
    # Zeitangabe berechneten Preis verglichen, statt den eingetippten Preis
    # als verbindlich zu behandeln -- das erzeugte eine irreführende
    # Differenz, obwohl es gar keinen echten Referenzwert (wie bei einer
    # importierten Leistung) gibt. Exakt wie im echten Endpunkt: Service und
    # ServiceCalculation mit manual_sale_price zusammen anlegen.
    db = db_session()
    batch = ensure_manual_import_batch(db)
    service = Service(
        import_batch_id=batch.id, source_type=batch.source_type, external_id=new_manual_external_id(),
        short_text="Testleistung", quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("30"), workshop_time_raw=Decimal("0"), sale_price=Decimal("50.00"),
    )
    db.add(service)
    db.flush()
    service.calculation = ServiceCalculation(service_id=service.id, manual_sale_price=Decimal("50.00"))
    db.commit()
    db.refresh(service)

    settings = get_or_create_settings(db)
    calc = build_calculation(service, settings)
    assert calc["effective_sale_price"] == Decimal("50.00")
    assert calc["delta_to_source"] == Decimal("0")


def test_ensure_manual_import_batch_creates_exactly_one():
    db = db_session()
    a = ensure_manual_import_batch(db)
    b = ensure_manual_import_batch(db)
    assert a.id == b.id
    assert a.source_type == "manual"
    all_batches = db.query(ImportBatch).all()
    assert len(all_batches) == 1


def test_new_manual_external_id_is_unique_across_many_calls():
    ids = {new_manual_external_id() for _ in range(500)}
    assert len(ids) == 500  # keine Kollision unter 500 Erzeugungen
    assert all(x.startswith("MANUAL-") for x in ids)


def test_manually_created_service_has_sensible_defaults():
    # Bildet exakt nach, was der POST /api/services Endpunkt tut (ohne FastAPI
    # selbst, das ist hier nicht verfügbar) -- prüft, dass ein minimal
    # ausgefüllter Datensatz alle Pflichtfelder des Modells korrekt bekommt.
    db = db_session()
    catalog = create_catalog(db, "Testkatalog", None)
    batch = ensure_manual_import_batch(db)

    service = Service(
        import_batch_id=batch.id,
        catalog_id=catalog.id,
        source_type=batch.source_type,
        external_id=new_manual_external_id(),
        short_text="Dachrinne reinigen",
        quantity=Decimal("1"),
        unit="Stk",
        site_time_raw=Decimal("30"),
        workshop_time_raw=Decimal("0"),
        sale_price=Decimal("45.00"),
    )
    db.add(service)
    db.commit()
    db.refresh(service)

    assert service.catalog_id == catalog.id
    assert service.import_batch_id == batch.id
    assert service.source_type == "manual"
    assert service.long_text == ""  # Modell-Default, nicht explizit gesetzt
    assert service.title_name is None
    assert service.materials == []  # keine Materialien angehängt


def test_two_manually_created_services_get_different_external_ids():
    db = db_session()
    batch = ensure_manual_import_batch(db)
    s1 = Service(
        import_batch_id=batch.id, source_type=batch.source_type, external_id=new_manual_external_id(),
        short_text="A", quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"), sale_price=Decimal("10"),
    )
    s2 = Service(
        import_batch_id=batch.id, source_type=batch.source_type, external_id=new_manual_external_id(),
        short_text="B", quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"), sale_price=Decimal("20"),
    )
    db.add_all([s1, s2])
    db.commit()  # würde bei gleicher external_id an der UniqueConstraint scheitern
    assert s1.external_id != s2.external_id


def test_list_services_catalog_filter_logic():
    # Deckt die Filterlogik ab, die list_services() jetzt nutzt (kein FastAPI
    # nötig, reine SQLAlchemy-Abfrage wie im Endpunkt).
    from sqlalchemy import select
    db = db_session()
    cat_a = create_catalog(db, "A", None)
    cat_b = create_catalog(db, "B", None)
    batch = ensure_manual_import_batch(db)
    for cat, name in [(cat_a, "in A"), (cat_b, "in B"), (None, "ohne Katalog")]:
        db.add(Service(
            import_batch_id=batch.id, catalog_id=cat.id if cat else None,
            source_type=batch.source_type, external_id=new_manual_external_id(),
            short_text=name, quantity=Decimal("1"), unit="Stk",
            site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"), sale_price=Decimal("1"),
        ))
    db.commit()

    stmt = select(Service).where(Service.catalog_id == cat_a.id)
    only_a = db.scalars(stmt).all()
    assert len(only_a) == 1
    assert only_a[0].short_text == "in A"

    stmt_all = select(Service)
    everything = db.scalars(stmt_all).all()
    assert len(everything) == 3


def test_copy_service_creates_independent_service_with_own_id():
    db = db_session()
    target_catalog = create_catalog(db, "Zielkatalog", None)
    original = make_service(db, "ORIG-1")

    copy = copy_service_to_catalog(db, original, target_catalog.id)

    assert copy.id != original.id
    assert copy.external_id != original.external_id
    assert copy.source_type == "copied"
    assert copy.catalog_id == target_catalog.id
    assert copy.short_text == original.short_text
    assert copy.quantity == original.quantity
    assert copy.sale_price == original.sale_price
    # Original unverändert
    assert original.catalog_id is None


def test_copy_service_duplicates_calculation_independently():
    db = db_session()
    original = make_service(db, "ORIG-2")
    original.calculation = ServiceCalculation(
        service_id=original.id, site_time_minutes=Decimal("45"),
        manual_sale_price=Decimal("99.00"), notes="Original-Notiz",
    )
    db.commit()

    copy = copy_service_to_catalog(db, original, None)

    assert copy.calculation is not None
    assert copy.calculation.id != original.calculation.id
    assert copy.calculation.site_time_minutes == Decimal("45")
    assert copy.calculation.manual_sale_price == Decimal("99.00")
    assert copy.calculation.notes == "Original-Notiz"

    # Unabhängig: Änderung an der Kopie darf das Original nicht berühren
    copy.calculation.notes = "Geänderte Kopie"
    db.commit()
    db.refresh(original)
    assert original.calculation.notes == "Original-Notiz"


def test_copy_service_without_calculation_stays_without_calculation():
    db = db_session()
    original = make_service(db, "ORIG-3")  # kein .calculation gesetzt
    copy = copy_service_to_catalog(db, original, None)
    assert copy.calculation is None


def test_copy_service_duplicates_materials_pointing_to_same_catalog_material():
    # Der zentrale Punkt aus der Absprache: die Materialzuordnung wird
    # dupliziert (unabhängige Zeile für die Kopie), aber das zugrunde
    # liegende Material im Katalog bleibt dasselbe -- kein Katalog-Duplikat.
    db = db_session()
    original = make_service(db, "ORIG-4")
    material = Material(name="Dachziegel", unit="Stk", purchase_price=Decimal("2.50"), price_basis=Decimal("1"), source="imported")
    db.add(material); db.commit()
    db.add(ServiceMaterial(
        service_id=original.id, material_id=material.id, name="Dachziegel", article_number=None,
        quantity=Decimal("20"), unit="Stk", waste_raw=Decimal("0"),
        purchase_price=Decimal("2.50"), price_basis=Decimal("1"),
    ))
    db.commit(); db.refresh(original)

    copy = copy_service_to_catalog(db, original, None)

    assert len(copy.materials) == 1
    assert copy.materials[0].id != original.materials[0].id  # eigene Zeile
    assert copy.materials[0].material_id == material.id  # dasselbe Material im Katalog
    assert copy.materials[0].quantity == Decimal("20")


def test_copy_service_duplicates_material_overrides():
    db = db_session()
    original = make_service(db, "ORIG-5")
    db.add(MaterialCalculationOverride(
        service_id=original.id, article_number_key="ART-X", material_name_key="Dachziegel",
        quantity_override=Decimal("15"), waste_pct=Decimal("5"),
    ))
    db.commit()

    copy = copy_service_to_catalog(db, original, None)
    db.refresh(copy)

    copy_overrides = db.query(MaterialCalculationOverride).filter_by(service_id=copy.id).all()
    assert len(copy_overrides) == 1
    assert copy_overrides[0].article_number_key == "ART-X"
    assert copy_overrides[0].quantity_override == Decimal("15")
    # Original-Override bleibt unangetastet
    original_overrides = db.query(MaterialCalculationOverride).filter_by(service_id=original.id).all()
    assert len(original_overrides) == 1
