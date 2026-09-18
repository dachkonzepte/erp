"""Version 1.3.51 -- Rechtekonzept, Etappe 1+2 (Fundament): weitere Teile neben dem Rollen-Audit
in tests/test_v260_role_audit.py.

1. Property.access_notes/site_contact_name/site_contact_phone (Anmerkung 2, siehe CLAUDE.md
   "Rechtekonzept" -- ein Monteur soll Zugang/Ansprechpartner vor Ort über den Einsatzbericht
   lesen, nicht über die Kundenakte) und der neue, auftragsbezogene Lesepfad dafür.
2. Die Rollen-Datenmigration 7a2b4e9f1c3d (role='user' -> 'office').
3. AppUserCreate/-Update: neues Pattern, neuer Vorgabewert.
"""

import importlib.util
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AppUser, Customer, Order, Project, Property
from app.project_pipeline_columns import default_pipeline_column_id
from app.schemas import AppUserCreate, PropertyCreate, PropertyOut, PropertyUpdate
from app.service_reports import get_property_context_for_order


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Property: Zugang & Ansprechpartner vor Ort
# ---------------------------------------------------------------------------

def test_property_create_and_update_schemas_accept_the_new_fields():
    created = PropertyCreate(
        customer_id=1, name="Baustelle Nord", access_notes="Schlüssel beim Nachbarn Nr. 4",
        site_contact_name="Herr Meier", site_contact_phone="0170 1234567",
    )
    assert created.access_notes == "Schlüssel beim Nachbarn Nr. 4"
    updated = PropertyUpdate(name="Baustelle Nord", site_contact_phone="0170 1234567")
    assert updated.site_contact_name is None
    assert updated.site_contact_phone == "0170 1234567"


def test_property_out_reads_the_new_fields_from_the_orm_object():
    prop = Property(
        id=1, customer_id=1, name="Baustelle Nord", access_notes="Torcode 4711",
        site_contact_name="Frau Schmidt", site_contact_phone="0171 7654321", is_primary_address=False,
    )
    out = PropertyOut.model_validate(prop, from_attributes=True)
    assert out.access_notes == "Torcode 4711"
    assert out.site_contact_name == "Frau Schmidt"


def _make_order_with_property(db, order_number="AUF-TEST-0001"):
    """Muster aus tests/test_v133_invoices.py::make_order_with_item() -- source_quote_id ist
    hier ein reiner Literalwert ohne echte Quote-Zeile, wie dort etabliert (SQLite prüft
    Fremdschlüssel in dieser Testkonfiguration nicht)."""
    customer = Customer(name="Testkunde", last_name="Testkunde")
    db.add(customer); db.flush()
    prop = Property(
        customer_id=customer.id, name="Baustelle Nord", street="Teststr. 1", city="Teststadt",
        access_notes="Schlüsselkasten Code 4711", site_contact_name="Herr Meier",
        site_contact_phone="0170 1234567", notes="Büro-interner Vermerk, nicht für den Monteur",
    )
    db.add(prop); db.flush()
    project = Project(project_number="P-TEST-0001", name="Testprojekt", customer_id=customer.id, property_id=prop.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.flush()
    order = Order(
        order_number=order_number, project_id=project.id, source_quote_id=1, quote_number_snapshot="A-TEST-0001",
        title="Testauftrag", customer_name=customer.name, property_name=prop.name,
    )
    db.add(order); db.commit()
    return order, prop


def test_get_property_context_for_order_returns_the_live_property(db_session):
    order, prop = _make_order_with_property(db_session)
    context = get_property_context_for_order(db_session, order.id)
    assert context is not None
    assert context.id == prop.id
    assert context.access_notes == "Schlüsselkasten Code 4711"
    assert context.site_contact_name == "Herr Meier"


def test_get_property_context_for_order_returns_none_without_linked_property(db_session):
    customer = Customer(name="Testkunde", last_name="Testkunde")
    db_session.add(customer); db_session.flush()
    project = Project(project_number="P-TEST-0002", name="Testprojekt ohne Objekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db_session))
    db_session.add(project); db_session.flush()
    order = Order(
        order_number="AUF-TEST-0002", project_id=project.id, source_quote_id=1, quote_number_snapshot="A-TEST-0002",
        title="Testauftrag", customer_name=customer.name, property_name="Hauptadresse",
    )
    db_session.add(order); db_session.commit()
    assert get_property_context_for_order(db_session, order.id) is None


def test_get_property_for_order_endpoint(router_test_client, threaded_db_session):
    from app.routers.service_reports import router as sr_router
    order, prop = _make_order_with_property(threaded_db_session)
    client = router_test_client(threaded_db_session, sr_router)
    response = client.get(f"/api/orders/{order.id}/property")
    assert response.status_code == 200
    data = response.json()
    assert data["access_notes"] == "Schlüsselkasten Code 4711"
    assert data["site_contact_phone"] == "0170 1234567"


def test_get_property_for_order_endpoint_does_not_leak_internal_notes_or_customer_context(router_test_client, threaded_db_session):
    """Seit 1.3.53 behoben (echter Befund, siehe CLAUDE.md 'Rechtekonzept'): PropertyOut (die
    vorherige Antwortform) trug `notes`/`customer_id` mit -- genau der Kundenkontext, den dieser
    Endpunkt laut eigener Begründung NICHT zeigen soll. PropertyAccessOut lässt beide weg."""
    from app.routers.service_reports import router as sr_router
    order, prop = _make_order_with_property(threaded_db_session)
    client = router_test_client(threaded_db_session, sr_router)
    data = client.get(f"/api/orders/{order.id}/property").json()
    assert "notes" not in data
    assert "customer_id" not in data
    assert "is_primary_address" not in data
    assert set(data.keys()) == {
        "id", "name", "street", "postal_code", "city",
        "access_notes", "site_contact_name", "site_contact_phone",
    }


# ---------------------------------------------------------------------------
# AppUserCreate/-Update: vier Rollen (seit CLAUDE.md "Rechtekonzept" -> "Vier Rollen"), Vorgabewert
# ---------------------------------------------------------------------------

def test_app_user_create_accepts_all_four_roles_and_defaults_to_buero_auftrag():
    assert AppUserCreate(username="test1", password="Passwort123", display_name="Test").role == "buero_auftrag"
    for role in ("admin", "buero_finanzen", "buero_auftrag", "field"):
        assert AppUserCreate(username="test1", password="Passwort123", display_name="Test", role=role).role == role


def test_app_user_create_rejects_the_old_bare_user_role():
    with pytest.raises(Exception):
        AppUserCreate(username="test1", password="Passwort123", display_name="Test", role="user")


# ---------------------------------------------------------------------------
# Migration 7a2b4e9f1c3d: role='user' -> 'office', downgrade auf 'user'
# ---------------------------------------------------------------------------

def _load_role_migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_app_user_role_office_field.py"))
    spec = importlib.util.spec_from_file_location("migration_app_user_role_office_field", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration_step(engine, fn):
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        with Operations.context(ops):
            fn()
        conn.commit()


def test_migration_upgrade_turns_user_into_office_admin_untouched():
    migration = _load_role_migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        session.add(AppUser(username="bestandsadmin", password_hash="x", display_name="Admin", role="admin"))
        session.add(AppUser(username="altkonto", password_hash="x", display_name="Alt", role="user"))
        session.commit()

    _run_migration_step(engine, migration.upgrade)

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT username, role FROM app_users")).all())
    assert rows["bestandsadmin"] == "admin"
    assert rows["altkonto"] == "office"


def test_migration_downgrade_maps_office_and_field_back_to_user():
    migration = _load_role_migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        session.add(AppUser(username="admin1", password_hash="x", display_name="Admin", role="admin"))
        session.add(AppUser(username="office1", password_hash="x", display_name="Büro", role="office"))
        session.add(AppUser(username="field1", password_hash="x", display_name="Monteur", role="field"))
        session.commit()

    _run_migration_step(engine, migration.downgrade)

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT username, role FROM app_users")).all())
    assert rows["admin1"] == "admin"
    assert rows["office1"] == "user"
    assert rows["field1"] == "user"
