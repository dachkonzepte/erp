from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.material_groups import (
    backfill_existing_materials,
    copy_material_to_group,
    create_material_group,
    ensure_import_material_group,
    list_material_groups,
    move_material_to_group,
    set_material_group_archived,
)
from app.materials import create_manual_material, find_or_create_material, list_materials
from app.models import Material, MaterialGroup


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_ensure_import_material_group_creates_exactly_one():
    db = db_session()
    a = ensure_import_material_group(db)
    b = ensure_import_material_group(db)
    assert a.id == b.id
    assert a.is_import_catalog is True
    assert db.query(MaterialGroup).count() == 1


def test_backfill_existing_materials_assigns_group_and_is_idempotent():
    db = db_session()
    m1 = Material(name="A", unit="Stk", purchase_price=Decimal("1"), price_basis=Decimal("1"), source="imported")
    m2 = Material(name="B", unit="Stk", purchase_price=Decimal("2"), price_basis=Decimal("1"), source="imported")
    db.add_all([m1, m2]); db.commit()

    group = ensure_import_material_group(db)
    moved = backfill_existing_materials(db, group)
    assert moved == 2
    db.refresh(m1); db.refresh(m2)
    assert m1.catalog_id == group.id
    assert m2.catalog_id == group.id

    assert backfill_existing_materials(db, group) == 0  # nichts mehr zu tun


def test_backfill_returns_minus_one_when_migration_not_yet_applied():
    db = db_session()
    db.execute(text("ALTER TABLE materials RENAME TO materials_real"))
    db.execute(text("CREATE TABLE materials (id INTEGER PRIMARY KEY)"))
    db.commit()
    group = MaterialGroup(name="x", is_import_catalog=True)
    assert backfill_existing_materials(db, group) == -1


def test_list_material_groups_filters_archived_by_default():
    db = db_session()
    active = create_material_group(db, "Aktiv", None)
    archived = create_material_group(db, "Archiviert", None)
    set_material_group_archived(db, archived.id, True)

    default_list = list_material_groups(db)
    assert active.id in {g.id for g in default_list}
    assert archived.id not in {g.id for g in default_list}

    full_list = list_material_groups(db, include_archived=True)
    assert archived.id in {g.id for g in full_list}


def test_fertigkatalog_cannot_be_archived():
    db = db_session()
    group = ensure_import_material_group(db)
    try:
        set_material_group_archived(db, group.id, True)
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass
    db.refresh(group)
    assert group.archived is False


def test_move_material_to_group():
    db = db_session()
    target = create_material_group(db, "Ziel", None)
    material = create_manual_material(db, "Testmaterial", "Stk", Decimal("5.00"))
    assert material.catalog_id is None

    moved = move_material_to_group(db, material, target.id)
    assert moved.catalog_id == target.id


def test_copy_material_creates_independent_row():
    db = db_session()
    source_group = create_material_group(db, "Quelle", None)
    target_group = create_material_group(db, "Ziel", None)
    original = create_manual_material(db, "Original", "Stk", Decimal("3.00"), article_number="ART-X", catalog_id=source_group.id)

    copy = copy_material_to_group(db, original, target_group.id)
    assert copy.id != original.id
    assert copy.name == original.name
    assert copy.purchase_price == original.purchase_price
    assert copy.article_number == "ART-X"
    assert copy.catalog_id == target_group.id
    # Original bleibt unangetastet in seiner ursprünglichen Gruppe
    db.refresh(original)
    assert original.catalog_id == source_group.id


def test_list_materials_filters_by_catalog():
    db = db_session()
    group_a = create_material_group(db, "A", None)
    group_b = create_material_group(db, "B", None)
    create_manual_material(db, "In A", "Stk", Decimal("1"), catalog_id=group_a.id)
    create_manual_material(db, "In B", "Stk", Decimal("1"), catalog_id=group_b.id)
    create_manual_material(db, "Ohne Katalog", "Stk", Decimal("1"))

    only_a = list_materials(db, catalog_id=group_a.id)
    assert len(only_a) == 1
    assert only_a[0].name == "In A"

    everything = list_materials(db)
    assert len(everything) == 3


def test_find_or_create_material_assigns_catalog_id_only_on_new_rows():
    # Neu angelegtes Material bekommt die übergebene Gruppe. Ein bereits
    # bestehendes (über Deduplizierung gefundenes) Material behält seine
    # ursprüngliche Zuordnung -- wird nicht nachträglich verschoben.
    db = db_session()
    group_a = create_material_group(db, "A", None)
    group_b = create_material_group(db, "B", None)
    cache = {}
    m1 = find_or_create_material(db, "ART1", "Ziegel", "Stk", Decimal("2.50"), Decimal("1"), cache, catalog_id=group_a.id)
    assert m1.catalog_id == group_a.id

    # Exakt derselbe Datensatz nochmal, diesmal mit group_b übergeben --
    # muss das VORHANDENE Material zurückgeben, nicht dessen Gruppe ändern.
    cache2 = {}
    m2 = find_or_create_material(db, "ART1", "Ziegel", "Stk", Decimal("2.50"), Decimal("1"), cache2, catalog_id=group_b.id)
    assert m2.id == m1.id
    assert m2.catalog_id == group_a.id  # unverändert, nicht auf group_b umgesprungen


def test_find_or_create_material_without_catalog_id_leaves_column_untouched():
    # Kein Fehler, wenn catalog_id=None nicht explizit gesetzt wird (Schutz
    # gegen "no such column", falls die Migration einmal noch nicht
    # angewendet ist -- siehe Kommentar in materials.py).
    db = db_session()
    cache = {}
    m = find_or_create_material(db, None, "Ohne Gruppe", "Stk", Decimal("1"), Decimal("1"), cache)
    assert m.catalog_id is None
