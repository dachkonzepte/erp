from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.calculation import build_calculation, get_or_create_settings, get_settings_for_catalog
from app.catalogs import backfill_existing_services, create_catalog, ensure_import_catalog, list_catalogs, set_catalog_archived
from app.database import Base
from app.importers.leistungen_dach import ParsedMaterial, ParsedProject, ParsedService
from app.models import Catalog, CalculationSettings, ImportBatch, Service
from app.service import persist_project


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_imported_service(db, catalog_id=None, external_id="X1"):
    batch = ImportBatch(source_type="leistungen_dach", source_name="Test", filename="test.xml")
    db.add(batch); db.commit()
    service = Service(
        import_batch_id=batch.id, catalog_id=catalog_id, source_type="leistungen_dach", external_id=external_id,
        short_text="Testleistung", quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("60"), workshop_time_raw=Decimal("0"), sale_price=Decimal("100"),
    )
    db.add(service); db.commit(); db.refresh(service)
    return service


def test_backfill_returns_minus_one_when_migration_not_yet_applied():
    # Stellt genau die Situation nach, die beim ersten echten pytest-Lauf nach
    # 1.0.14 aufgetreten ist: eine bereits bestehende Datenbank, bei der
    # Base.metadata.create_all() die neue Spalte services.catalog_id NICHT
    # nachträglich ergänzt hat (das kann nur eine Alembic-Migration). Vorher
    # ist backfill_existing_services() dabei mit einem sqlite3.OperationalError
    # abgestürzt -- und zwar direkt beim Programmstart, noch bevor überhaupt
    # ein einziger Test lief.
    #
    # Statt die Spalte per DROP COLUMN aus der echten Tabelle zu entfernen
    # (daran hängen sowohl ein Index als auch der Fremdschlüssel auf
    # catalogs.id -- beides bringt SQLites ALTER TABLE bei einem Schema
    # dieser Größe durcheinander, wie sich beim echten Testlauf zeigte): die
    # echte Tabelle umbenennen und eine neue, minimale 'services'-Tabelle ohne
    # catalog_id anlegen. backfill_existing_services() bricht bei fehlender
    # Spalte VOR jedem weiteren Zugriff ab (siehe _services_table_has_catalog_column),
    # daher reicht diese minimale Tabelle für den Test vollständig aus.
    db = db_session()
    catalog = ensure_import_catalog(db)
    db.execute(text("ALTER TABLE services RENAME TO services_real"))
    db.execute(text("CREATE TABLE services (id INTEGER PRIMARY KEY)"))
    db.commit()

    result = backfill_existing_services(db, catalog)
    assert result == -1  # kein Absturz, klares "noch nicht migriert"-Signal


def test_backfill_works_normally_once_column_exists():
    # Gegenprobe zum vorigen Test: sobald die Spalte da ist (wie bei einer
    # frischen Datenbank oder nach erfolgreicher Migration), funktioniert der
    # Backfill wie gehabt -- kein Kollateralschaden durch den neuen Check.
    db = db_session()
    catalog = ensure_import_catalog(db)
    make_imported_service(db, catalog_id=None)
    result = backfill_existing_services(db, catalog)
    assert result == 1


def test_get_or_create_settings_raises_clear_error_when_migration_not_yet_applied():
    # Genau der Fehler, der nach 1.0.18 real aufgetreten ist ("Einstellungen
    # konnten nicht geladen werden"): die Einstellungsseite ruft
    # get_or_create_settings() auf, das seit 1.0.17 nach catalog_id IS NULL
    # sucht -- auf einer noch nicht migrierten echten Datenbank gibt es diese
    # Spalte in calculation_settings aber noch gar nicht. Ein ORM-Fallback ist
    # hier NICHT möglich (anders als bei backfill_existing_services): jede
    # Abfrage über das CalculationSettings-Modell würde ebenfalls an der
    # fehlenden Spalte scheitern, da das Modell catalog_id kennt. Die Funktion
    # muss daher klar fehlschlagen statt einen nicht funktionierenden
    # Fallback vorzutäuschen -- geprüft wird hier, dass die Fehlermeldung
    # verständlich ist (landet vollständig in data/erp.log).
    db = db_session()
    db.execute(text("ALTER TABLE calculation_settings RENAME TO calculation_settings_real"))
    db.execute(text("CREATE TABLE calculation_settings (id INTEGER PRIMARY KEY)"))
    db.commit()

    try:
        get_or_create_settings(db)
        assert False, "sollte RuntimeError auslösen"
    except RuntimeError as exc:
        assert "Migration" in str(exc) or "migriert" in str(exc)
        assert "alembic" in str(exc)


def test_ensure_import_catalog_creates_exactly_one():
    db = db_session()
    a = ensure_import_catalog(db)
    b = ensure_import_catalog(db)
    assert a.id == b.id
    assert a.is_import_catalog is True
    all_catalogs = db.query(Catalog).all()
    assert len(all_catalogs) == 1


def test_backfill_assigns_catalogless_services_and_is_idempotent():
    db = db_session()
    catalog = ensure_import_catalog(db)
    make_imported_service(db, catalog_id=None, external_id="X1")
    make_imported_service(db, catalog_id=None, external_id="X2")
    moved = backfill_existing_services(db, catalog)
    assert moved == 2
    assert all(s.catalog_id == catalog.id for s in db.query(Service).all())
    # zweiter Lauf darf nichts mehr finden (nichts mehr katalog-los)
    assert backfill_existing_services(db, catalog) == 0


def test_backfill_does_not_touch_services_already_in_another_catalog():
    db = db_session()
    import_catalog = ensure_import_catalog(db)
    own_catalog = create_catalog(db, "Eigener Katalog", None)
    make_imported_service(db, catalog_id=own_catalog.id)
    backfill_existing_services(db, import_catalog)
    service = db.query(Service).one()
    assert service.catalog_id == own_catalog.id  # unverändert, nicht überschrieben


def test_create_and_list_catalogs_excludes_archived_by_default():
    db = db_session()
    ensure_import_catalog(db)
    a = create_catalog(db, "Katalog A", "Beschreibung A")
    b = create_catalog(db, "Katalog B", None)
    set_catalog_archived(db, b.id, True)
    names = {c.name for c in list_catalogs(db)}
    assert "Katalog A" in names
    assert "Katalog B" not in names
    names_with_archived = {c.name for c in list_catalogs(db, include_archived=True)}
    assert "Katalog B" in names_with_archived


def test_import_catalog_cannot_be_archived():
    db = db_session()
    catalog = ensure_import_catalog(db)
    try:
        set_catalog_archived(db, catalog.id, True)
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
    db.refresh(catalog)
    assert catalog.archived is False


def test_unarchive_restores_visibility():
    db = db_session()
    ensure_import_catalog(db)
    cat = create_catalog(db, "Test", None)
    set_catalog_archived(db, cat.id, True)
    set_catalog_archived(db, cat.id, False)
    assert cat.id in {c.id for c in list_catalogs(db)}


def test_service_without_own_catalog_settings_uses_global_fallback():
    db = db_session()
    catalog = create_catalog(db, "Katalog ohne eigene Kalkulation", None)
    service = make_imported_service(db, catalog_id=catalog.id)
    global_settings = get_or_create_settings(db)
    global_settings.labor_rate = Decimal("82.00")
    db.commit()
    resolved = get_settings_for_catalog(db, service.catalog_id)
    assert resolved.id == global_settings.id
    assert resolved.labor_rate == Decimal("82.00")


def test_service_with_own_catalog_settings_uses_those_not_global():
    db = db_session()
    catalog = create_catalog(db, "Katalog mit eigener Kalkulation", None)
    service = make_imported_service(db, catalog_id=catalog.id)
    own = CalculationSettings(catalog_id=catalog.id, labor_rate=Decimal("95.00"))
    db.add(own); db.commit()

    resolved = get_settings_for_catalog(db, service.catalog_id)
    assert resolved.catalog_id == catalog.id
    assert resolved.labor_rate == Decimal("95.00")

    # Wirkt sich tatsächlich auf die Kalkulation aus, nicht nur auf den gelesenen Datensatz:
    calc_with_own = build_calculation(service, resolved)
    calc_with_global = build_calculation(service, get_or_create_settings(db))
    assert calc_with_own["effective_sale_price"] != calc_with_global["effective_sale_price"]


def test_two_catalogs_resolve_independently_in_same_request():
    # Deckt genau das ab, was list_services() jetzt pro Leistung braucht:
    # unterschiedliche Kataloge in derselben Anfrage dürfen sich nicht vermischen.
    db = db_session()
    cat_a = create_catalog(db, "A", None)
    cat_b = create_catalog(db, "B", None)
    db.add(CalculationSettings(catalog_id=cat_a.id, labor_rate=Decimal("70.00")))
    db.add(CalculationSettings(catalog_id=cat_b.id, labor_rate=Decimal("110.00")))
    db.commit()

    cache = {}
    settings_a = get_settings_for_catalog(db, cat_a.id, cache)
    settings_b = get_settings_for_catalog(db, cat_b.id, cache)
    assert settings_a.labor_rate == Decimal("70.00")
    assert settings_b.labor_rate == Decimal("110.00")


def _minimal_project(external_id="L1", with_material=True):
    materials = [
        ParsedMaterial(
            name="Dachziegel", article_number="ART1", quantity=Decimal("10"),
            unit="Stk", waste_raw=Decimal("0"), purchase_price=Decimal("2.50"), price_basis=Decimal("1"),
        )
    ] if with_material else []
    service = ParsedService(
        external_id=external_id, title_name=None, short_text="Testleistung", long_text="",
        rtf_text=None, image_reference=None, quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("30"), workshop_time_raw=Decimal("0"),
        sale_price=Decimal("50.00"), activity_code=None, materials=materials,
    )
    return ParsedProject(source_name="Test", source_version="1", title_count=1, services=[service])


def test_persist_project_on_fresh_database_does_not_raise_integrity_error():
    # Regressionstest für 1.0.25/1.0.26: auf einer komplett frischen Datenbank
    # existiert der Fertigkatalog noch nicht. ensure_import_catalog() legt ihn
    # dann per internem commit() an -- das expired bei SQLAlchemy per Default
    # JEDES Objekt in der Session, nicht nur das gerade committete. War
    # ensure_import_catalog() zu dem Zeitpunkt schon NACH dem Anlegen von
    # `batch` aufgerufen worden, führte ein späterer batch.id-Zugriff zu einem
    # verfrühten Autoflush der noch unvollständigen Leistung -> IntegrityError.
    # Traf in der Praxis 40 Tests in völlig unabhängigen Bereichen, weil sie
    # alle über persist_project() importieren.
    db = db_session()
    assert db.query(Catalog).count() == 0  # sicherstellen: wirklich noch kein Fertigkatalog

    inserted, replaced = persist_project(db, _minimal_project(), "test.xml")

    assert inserted == 1
    assert replaced == 0
    service = db.query(Service).filter_by(external_id="L1").one()
    assert service.import_batch_id is not None
    assert service.catalog_id is not None
    catalog = db.get(Catalog, service.catalog_id)
    assert catalog.is_import_catalog is True


def test_persist_project_reimport_also_does_not_raise():
    # Zweiter Import direkt danach -- diesmal existiert der Fertigkatalog
    # schon (kein commit() mehr in ensure_import_catalog nötig), muss aber
    # ebenso sauber durchlaufen.
    db = db_session()
    persist_project(db, _minimal_project(), "test.xml")
    inserted, replaced = persist_project(db, _minimal_project(), "test.xml")
    assert inserted == 0
    assert replaced == 1
