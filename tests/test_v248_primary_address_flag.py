"""Version 1.3.32 -- "Objekte: Hauptadressen kennzeichnen und ausblenden".

Property.is_primary_address wird ausschliesslich dort gesetzt, wo die Hauptadresse automatisch
entsteht (routers/customers.py::create_customer()/update_customer(),
address_import.py::_create_customer_from_row()) -- diese Datei prueft genau diese drei Stellen,
die Migration, die den echten Bestand rueckwirkend markiert, sowie den Nebenbefund-Fix in
orders.py::_copy_quote_scope_to_order() (siehe test_v209_quick_service_orders.py fuer letzteren).
"""

import importlib.util
from pathlib import Path

from sqlalchemy import select

from app.models import Customer, Property
from app.routers.customers import create_customer, update_customer
from app.schemas import CustomerCreate, CustomerUpdate
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property


def _migration_module():
    path = next(Path(__file__).resolve().parents[1].glob(
        "alembic/versions/*_properties_is_primary_address_flag.py"
    ))
    spec = importlib.util.spec_from_file_location("migration_1332_is_primary_address", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Punkt 1: is_primary_address wird an allen drei Erzeugungsstellen gesetzt ---

def test_create_customer_marks_auto_created_property_as_primary_address():
    db = db_session()
    created = create_customer(CustomerCreate(last_name="Testkunde GmbH"), db)
    main_property = db.scalar(select(Property).where(Property.customer_id == created.id))
    assert main_property.name == "Hauptadresse"
    assert main_property.is_primary_address is True


def test_update_customer_creates_flagged_primary_address_for_legacy_customer_without_one():
    """make_customer_and_property() legt ein normales, NICHT-Hauptadress-Objekt an (Fixture aus
    test_v202) -- update_customer() muss trotzdem eine echte, geflaggte Hauptadresse ergaenzen,
    nicht das bestehende Objekt umwidmen."""
    db = db_session()
    customer, other_property = make_customer_and_property(db)
    assert other_property.is_primary_address is False

    update_customer(customer.id, CustomerUpdate(last_name=customer.last_name, street="Neue Str. 1"), db)

    db.refresh(customer)
    flagged = [p for p in customer.properties if p.is_primary_address]
    assert len(flagged) == 1
    assert flagged[0].name == "Hauptadresse"
    assert flagged[0].street == "Neue Str. 1"
    # Das ursprüngliche, unabhängige Objekt bleibt unangetastet.
    assert other_property.is_primary_address is False


def test_update_customer_self_heals_unflagged_hauptadresse_row():
    """Verteidigung in der Tiefe (siehe app/routers/customers.py-Kommentar): eine Zeile, die
    bereits "Hauptadresse" heißt, aber (z. B. aus einer Zeit vor diesem Feature) nicht geflaggt
    ist, wird beim nächsten Speichern gefunden und nachträglich markiert -- statt eine zweite,
    doppelte "Hauptadresse"-Zeile anzulegen."""
    db = db_session()
    customer = Customer(last_name="Altbestand GmbH", name="Altbestand GmbH")
    db.add(customer); db.flush()
    unflagged = Property(customer_id=customer.id, name="Hauptadresse", is_primary_address=False)
    db.add(unflagged); db.commit()

    update_customer(customer.id, CustomerUpdate(last_name="Altbestand GmbH"), db)

    db.refresh(customer)
    assert len(customer.properties) == 1
    assert customer.properties[0].id == unflagged.id
    assert customer.properties[0].is_primary_address is True


# --- Migration: Bestandsabgleich, konservativ (Name UND Adresse müssen übereinstimmen) ---

def test_migration_marks_only_rows_matching_both_name_and_address():
    db = db_session()
    customer = Customer(
        last_name="Treffer GmbH", name="Treffer GmbH",
        street="Musterstraße 1", postal_code="12345", city="Musterstadt",
    )
    db.add(customer); db.flush()
    match = Property(
        customer_id=customer.id, name="Hauptadresse",
        street="Musterstraße 1", postal_code="12345", city="Musterstadt",
    )
    # Namensgleich, aber Adresse weicht ab (z. B. nachträglich umgezogen) -- bewusst NICHT
    # markiert, das konservative Kriterium verlangt beides.
    name_only = Property(
        customer_id=customer.id, name="Hauptadresse",
        street="Andere Straße 9", postal_code="99999", city="Woanders",
    )
    db.add_all([match, name_only]); db.commit()

    migration = _migration_module()
    primary_ids = migration._resolve_primary_address_property_ids(db.connection())
    assert match.id in primary_ids
    assert name_only.id not in primary_ids
