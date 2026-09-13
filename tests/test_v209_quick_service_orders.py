from app.auth import hash_password
from app.models import AppUser, Order, Project
from app.modules import set_module_enabled
from app.quick_service_orders import create_quick_service_order
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property


def test_create_quick_service_order_reparatur_creates_full_chain():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    result = create_quick_service_order(
        db, customer_id=customer.id, property_id=prop.id, order_type="reparatur",
        title="Dachrinne verstopft",
    )
    project = db.get(Project, result["project_id"])
    assert project.name == "Dachrinne verstopft"
    assert project.status == "beauftragt"

    order = db.get(Order, result["order_id"])
    assert order.order_number == result["order_number"]
    assert len(order.items) == 1
    assert order.items[0].short_text == "Reparatur nach Aufwand"
    assert order.items[0].unit_price == 0


def test_create_quick_service_order_wartung_uses_wartung_label():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    result = create_quick_service_order(
        db, customer_id=customer.id, property_id=prop.id, order_type="wartung",
        title="Dachkontrolle",
    )
    order = db.get(Order, result["order_id"])
    assert order.items[0].short_text == "Wartung nach Aufwand"


def test_create_quick_service_order_without_property_uses_customer_main_address():
    db = db_session()
    customer, _ = make_customer_and_property(db)
    result = create_quick_service_order(
        db, customer_id=customer.id, property_id=None, order_type="reparatur", title="Test",
    )
    project = db.get(Project, result["project_id"])
    assert project.property_id is None

    # Regression: contract_to_dict() (app/maintenance_contracts.py) synthetisiert für einen
    # Wartungsvertrag ohne Objekt bereits "Hauptadresse" als Anzeigename -- der per Schnellauftrag
    # erzeugte Auftrag muss denselben Wert im eingefrorenen Snapshot tragen, siehe
    # CLAUDE.md "Objekte: Hauptadressen kennzeichnen und ausblenden".
    order = db.get(Order, result["order_id"])
    assert order.property_name == "Hauptadresse"
    assert order.property_address is None  # Testkunde hat keine Adresse hinterlegt


def test_create_quick_service_order_without_property_freezes_customer_main_address():
    db = db_session()
    customer, _ = make_customer_and_property(db)
    customer.street = "Hauptstraße 5"
    customer.postal_code = "12345"
    customer.city = "Musterstadt"
    db.commit()
    result = create_quick_service_order(
        db, customer_id=customer.id, property_id=None, order_type="reparatur", title="Test",
    )
    order = db.get(Order, result["order_id"])
    assert order.property_name == "Hauptadresse"
    assert order.property_address == "Hauptstraße 5, 12345 Musterstadt"


def test_create_quick_service_order_rejects_invalid_type():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    try:
        create_quick_service_order(db, customer_id=customer.id, property_id=prop.id, order_type="sonstiges", title="x")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_create_quick_service_order_rejects_empty_title():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    try:
        create_quick_service_order(db, customer_id=customer.id, property_id=prop.id, order_type="reparatur", title="   ")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_quick_service_order_endpoint_returns_403_when_module_disabled():
    from app.routers.quick_service_orders import post_quick_service_order
    from app.schemas import QuickServiceOrderCreate

    db = db_session()
    set_module_enabled(db, "wartungen", False)
    admin = AppUser(username="admin1", display_name="Admin", role="admin", active=True, password_hash=hash_password("Passwort123"))
    db.add(admin); db.commit()

    try:
        post_quick_service_order(QuickServiceOrderCreate(customer_id=1, property_id=None, order_type="reparatur", title="x"), db=db)
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
