from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.materials import (
    backfill_existing_service_materials,
    create_manual_material,
    find_or_create_material,
    list_materials,
    update_material,
)
from app.models import ImportBatch, Material, Service, ServiceMaterial


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_service(db, external_id="S1"):
    batch = ImportBatch(source_type="leistungen_dach", source_name="Test", filename="t.xml")
    db.add(batch); db.commit()
    service = Service(
        import_batch_id=batch.id, source_type="leistungen_dach", external_id=external_id,
        short_text="Test", quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"), sale_price=Decimal("10"),
    )
    db.add(service); db.commit(); db.refresh(service)
    return service


def test_exact_match_reuses_existing_material_not_duplicate():
    db = db_session()
    cache = {}
    m1 = find_or_create_material(db, "ART1", "Dachziegel", "Stk", Decimal("2.50"), Decimal("1"), cache)
    m2 = find_or_create_material(db, "ART1", "Dachziegel", "Stk", Decimal("2.50"), Decimal("1"), cache)
    assert m1.id == m2.id
    assert db.query(Material).count() == 1


def test_same_article_number_different_values_creates_marked_duplicate():
    # Der eigentliche Kern der vereinbarten Regel: bei widersprüchlichen
    # Werten unter derselben Artikelnummer NICHT stillschweigend zusammenführen.
    db = db_session()
    cache = {}
    m1 = find_or_create_material(db, "ART1", "Dachziegel rot", "Stk", Decimal("2.50"), Decimal("1"), cache)
    m2 = find_or_create_material(db, "ART1", "Dachziegel blau", "Stk", Decimal("2.50"), Decimal("1"), cache)
    assert m1.id != m2.id
    assert m1.article_number == "ART1"
    assert m2.article_number == "ART1-DUP2"
    assert db.query(Material).count() == 2


def test_third_variant_gets_dup3():
    db = db_session()
    cache = {}
    find_or_create_material(db, "ART1", "Variante A", "Stk", Decimal("1"), Decimal("1"), cache)
    find_or_create_material(db, "ART1", "Variante B", "Stk", Decimal("2"), Decimal("1"), cache)
    m3 = find_or_create_material(db, "ART1", "Variante C", "Stk", Decimal("3"), Decimal("1"), cache)
    assert m3.article_number == "ART1-DUP3"


def test_no_article_number_matches_by_name_price_unit():
    db = db_session()
    cache = {}
    m1 = find_or_create_material(db, None, "Kleinmaterial", "Pausch", Decimal("5.00"), Decimal("1"), cache)
    m2 = find_or_create_material(db, None, "Kleinmaterial", "Pausch", Decimal("5.00"), Decimal("1"), cache)
    assert m1.id == m2.id
    # anderer Name ohne Artikelnummer -> eigenständiges Material, keine "-DUP"-Kennung
    m3 = find_or_create_material(db, None, "Anderes Kleinmaterial", "Pausch", Decimal("3.00"), Decimal("1"), cache)
    assert m3.id != m1.id
    assert m3.article_number is None


def test_cross_run_deduplication_finds_material_from_earlier_run():
    # Simuliert: ein Material wurde in einem früheren Import (eigener Cache-
    # Durchlauf) angelegt: ein NEUER, leerer Cache muss es trotzdem über die
    # Datenbank wiederfinden, nicht erneut anlegen.
    db = db_session()
    first_run_cache = {}
    m1 = find_or_create_material(db, "ART9", "Firstziegel", "Stk", Decimal("4.00"), Decimal("1"), first_run_cache)

    second_run_cache = {}
    m2 = find_or_create_material(db, "ART9", "Firstziegel", "Stk", Decimal("4.00"), Decimal("1"), second_run_cache)
    assert m1.id == m2.id
    assert db.query(Material).count() == 1


def test_backfill_assigns_material_id_and_deduplicates():
    db = db_session()
    s1 = make_service(db, "S1")
    s2 = make_service(db, "S2")
    # Gleiches Material in zwei verschiedenen Leistungen (wie es vor dem
    # Materialkatalog unabhängig gespeichert war)
    db.add(ServiceMaterial(service_id=s1.id, name="Dachziegel", article_number="ART1",
                            quantity=Decimal("10"), unit="Stk", waste_raw=Decimal("0"),
                            purchase_price=Decimal("2.50"), price_basis=Decimal("1")))
    db.add(ServiceMaterial(service_id=s2.id, name="Dachziegel", article_number="ART1",
                            quantity=Decimal("5"), unit="Stk", waste_raw=Decimal("0"),
                            purchase_price=Decimal("2.50"), price_basis=Decimal("1")))
    db.commit()

    moved = backfill_existing_service_materials(db)
    assert moved == 2
    materials = db.query(Material).all()
    assert len(materials) == 1  # dedupliziert zu einem Material
    sm_rows = db.query(ServiceMaterial).all()
    assert all(row.material_id == materials[0].id for row in sm_rows)
    # unabhängige Mengen pro Leistung bleiben erhalten
    assert {row.quantity for row in sm_rows} == {Decimal("10"), Decimal("5")}

    # Idempotent: zweiter Lauf findet nichts mehr zu tun
    assert backfill_existing_service_materials(db) == 0


def test_backfill_returns_minus_one_when_migration_not_yet_applied():
    db = db_session()
    db.execute(text("ALTER TABLE service_materials RENAME TO service_materials_real"))
    db.execute(text("CREATE TABLE service_materials (id INTEGER PRIMARY KEY)"))
    db.commit()
    assert backfill_existing_service_materials(db) == -1


def test_create_and_update_manual_material():
    db = db_session()
    m = create_manual_material(db, "Eigenes Material", "Stk", Decimal("9.99"), article_number="EIGEN-1")
    assert m.source == "manual"
    assert m.id in {x.id for x in list_materials(db)}

    updated = update_material(db, m.id, "Neuer Name", "kg", Decimal("12.50"), "EIGEN-1", Decimal("1"))
    assert updated.name == "Neuer Name"
    assert updated.purchase_price == Decimal("12.50")


def test_list_materials_search_matches_name_or_article_number():
    db = db_session()
    create_manual_material(db, "Dachlatte", "m", Decimal("1.20"), article_number="LAT-1")
    create_manual_material(db, "Schraube", "Stk", Decimal("0.05"), article_number="SCHR-1")
    by_name = list_materials(db, search="Dach")
    assert len(by_name) == 1 and by_name[0].name == "Dachlatte"
    by_article = list_materials(db, search="SCHR")
    assert len(by_article) == 1 and by_article[0].name == "Schraube"
