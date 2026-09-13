from datetime import date, timedelta

from app.auth import hash_password
from app.maintenance_contracts import create_maintenance_contract_from_project
from app.models import AppUser, MaintenanceContract, Order, Project
from app.modules import set_module_enabled
from app.quick_service_orders import create_quick_service_order
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property


def test_create_maintenance_contract_from_project_builds_new_template_and_contract():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    quick = create_quick_service_order(
        db, customer_id=customer.id, property_id=prop.id, order_type="wartung", title="Dachkontrolle Musterhaus",
    )
    project_id = quick["project_id"]
    order_id = quick["order_id"]

    due = date.today() + timedelta(days=180)
    contract = create_maintenance_contract_from_project(db, project_id, interval_months=12, next_due_date=due)

    assert contract["customer_id"] == customer.id
    assert contract["property_id"] == prop.id
    assert contract["title"] == "Dachkontrolle Musterhaus"
    assert contract["next_due_date"] == due
    assert contract["template_project_id"] is not None
    assert contract["template_project_id"] != project_id

    template = db.get(Project, contract["template_project_id"])
    assert template.is_template is True
    assert template.name == "Dachkontrolle Musterhaus"

    # Ursprüngliches Projekt und dessen Auftrag bleiben unverändert bestehen.
    original = db.get(Project, project_id)
    assert original.is_template is False
    assert db.get(Order, order_id) is not None

    row = db.get(MaintenanceContract, contract["id"])
    assert row.template_project_id == template.id


def test_create_maintenance_contract_from_project_rejects_missing_project():
    db = db_session()
    try:
        create_maintenance_contract_from_project(db, 999, interval_months=12, next_due_date=date.today())
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_create_maintenance_contract_from_project_rejects_template_source():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    quick = create_quick_service_order(
        db, customer_id=customer.id, property_id=prop.id, order_type="wartung", title="Test",
    )
    project = db.get(Project, quick["project_id"])
    project.is_template = True
    db.commit()
    try:
        create_maintenance_contract_from_project(db, project.id, interval_months=12, next_due_date=date.today())
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Mustervorgang" in str(exc)


def test_maintenance_contract_from_project_endpoint_returns_403_when_module_disabled():
    from app.routers.maintenance_contracts import post_maintenance_contract_from_project
    from app.schemas import MaintenanceContractFromProjectCreate

    db = db_session()
    set_module_enabled(db, "wartungen", False)
    admin = AppUser(username="admin1", display_name="Admin", role="admin", active=True, password_hash=hash_password("Passwort123"))
    db.add(admin); db.commit()

    try:
        post_maintenance_contract_from_project(
            1, MaintenanceContractFromProjectCreate(interval_months=12, next_due_date=date.today()), db=db,
        )
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
