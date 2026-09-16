from datetime import date, timedelta
from pathlib import Path

from starlette.requests import Request

from app.auth import hash_password
from app.maintenance_contracts import (
    check_due_contracts_and_create_reminders, create_contract, create_project_from_contract,
    delete_contract, list_contracts, set_contract_status, update_contract,
)
from app.models import AppUser, Customer, Employee, MaintenanceContract, Project, Property, Task
from app.modules import set_module_enabled
from app.project_pipeline_columns import default_pipeline_column_id
from app.tasks import list_tasks
from tests.test_v153_mahnwesen import db_session


def make_customer_and_property(db):
    customer = Customer(name="Testkunde GmbH", last_name="Testkunde GmbH")
    db.add(customer); db.flush()
    prop = Property(customer_id=customer.id, name="Musterstraße 1")
    db.add(prop); db.commit()
    return customer, prop


def make_template_project(db, customer, prop, number="P-TEMPLATE-0001"):
    project = Project(project_number=number, name="Jahreswartung Dach", customer_id=customer.id,
                       property_id=prop.id, is_template=True, status="anfrage",
                       pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.commit()
    return project


def request_with_user(user):
    req = Request({"type": "http", "method": "GET", "path": "/api/maintenance-contracts", "headers": [],
                   "query_string": b"", "server": ("test", 80), "client": ("test", 1234), "scheme": "http"})
    req.state.erp_user = user
    return req


def test_create_contract_rejects_zero_interval():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    try:
        create_contract(db, customer.id, prop.id, "Test", 0, date.today())
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_is_due_reflects_next_due_date():
    """Jenseits der Standard-Vorlaufzeit (30 Tage, siehe MaintenanceSettings) liegend --
    das eigentliche Vorlaufzeit-Verhalten selbst ist in test_v207_maintenance_settings.py
    getestet."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    past = create_contract(db, customer.id, prop.id, "Fällig", 12, date.today() - timedelta(days=1))
    future = create_contract(db, customer.id, prop.id, "Nicht fällig", 12, date.today() + timedelta(days=90))
    rows = {r["id"]: r for r in list_contracts(db)}
    assert rows[past["id"]]["is_due"] is True
    assert rows[future["id"]]["is_due"] is False


def test_check_due_creates_reminder_task_and_is_idempotent():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    emp = Employee(first_name="Erika", last_name="Eins", employee_group="angestellt", active=True)
    db.add(emp); db.commit()
    contract = create_contract(db, customer.id, prop.id, "Dachwartung", 12, date.today() - timedelta(days=1),
                                responsible_employee_id=emp.id)

    reminded = check_due_contracts_and_create_reminders(db)
    assert reminded == [contract["id"]]
    tasks = list_tasks(db, employee_id=emp.id)
    assert len(tasks) == 1
    assert tasks[0]["source_module"] == "wartungsvertrag"
    assert tasks[0]["source_url"] == f"/maintenance-contracts/{contract['id']}"

    # Erneuter Aufruf für denselben Fälligkeitszyklus darf nicht doppelt erinnern.
    reminded_again = check_due_contracts_and_create_reminders(db)
    assert reminded_again == []
    assert len(list_tasks(db, employee_id=emp.id)) == 1


def test_check_due_skips_paused_and_ended_contracts():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Pausiert", 12, date.today() - timedelta(days=1))
    set_contract_status(db, contract["id"], "pausiert")
    assert check_due_contracts_and_create_reminders(db) == []


def test_check_due_skips_reminder_when_aufgabenmanagement_disabled():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    create_contract(db, customer.id, prop.id, "Ohne Aufgaben", 12, date.today() - timedelta(days=1))
    set_module_enabled(db, "aufgabenmanagement", False)
    assert check_due_contracts_and_create_reminders(db) == []
    assert db.query(Task).count() == 0


def test_create_project_from_contract_advances_due_date_and_resets_reminder_stamp():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    template = make_template_project(db, customer, prop)
    contract = create_contract(db, customer.id, prop.id, "Dachwartung", 3, date(2026, 11, 30),
                                template_project_id=template.id)
    check_due_contracts_and_create_reminders(db)  # noch nicht fällig -> kein Reminder, nur zur Sicherheit aufgerufen

    result = create_project_from_contract(db, contract["id"])
    assert result["project_number"] != template.project_number

    updated = list_contracts(db)[0]
    assert updated["next_due_date"] == date(2027, 2, 28)  # 30.11.2026 + 3 Monate, Februar hat nur 28 Tage
    row = db.get(MaintenanceContract, contract["id"])
    assert row.last_reminder_due_date is None


def test_create_project_from_contract_requires_template():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Ohne Vorlage", 12, date.today())
    try:
        create_project_from_contract(db, contract["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Mustervorgang" in str(exc)


def test_update_contract_and_set_status_reject_invalid_input():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Test", 12, date.today())
    try:
        update_contract(db, contract["id"], title="Test", interval_months=0, next_due_date=date.today(),
                         template_project_id=None, responsible_employee_id=None, notes=None)
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
    try:
        set_contract_status(db, contract["id"], "unbekannt")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_contract_without_property_falls_back_to_customer_main_address():
    db = db_session()
    customer = Customer(name="Testkunde GmbH", last_name="Testkunde GmbH", street="Hauptstraße 5", postal_code="12345", city="Musterstadt")
    db.add(customer); db.commit()

    contract = create_contract(db, customer.id, None, "Ohne Objekt", 12, date.today())
    assert contract["property_id"] is None
    assert contract["property_name"] == "Hauptadresse"
    assert contract["property_address"] == "Hauptstraße 5, 12345 Musterstadt"


def test_update_contract_can_set_and_clear_property_id():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Test", 12, date.today())
    assert contract["property_id"] == prop.id

    cleared = update_contract(db, contract["id"], title="Test", interval_months=12, next_due_date=date.today(),
                               template_project_id=None, responsible_employee_id=None, notes=None, property_id=None)
    assert cleared["property_id"] is None
    assert cleared["property_name"] == "Hauptadresse"

    restored = update_contract(db, contract["id"], title="Test", interval_months=12, next_due_date=date.today(),
                                template_project_id=None, responsible_employee_id=None, notes=None, property_id=prop.id)
    assert restored["property_id"] == prop.id
    assert restored["property_name"] == prop.name


def test_delete_contract_removes_it_and_reports_missing_id():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Zu löschen", 12, date.today())

    assert delete_contract(db, contract["id"]) is True
    assert db.get(MaintenanceContract, contract["id"]) is None
    assert delete_contract(db, contract["id"]) is False


def test_maintenance_contracts_endpoints_return_403_when_module_disabled():
    from app.routers.maintenance_contracts import (
        delete_maintenance_contract, get_maintenance_contracts, post_maintenance_contract,
    )
    from app.schemas import MaintenanceContractCreate

    db = db_session()
    set_module_enabled(db, "wartungen", False)
    admin = AppUser(username="admin1", display_name="Admin", role="admin", active=True, password_hash=hash_password("Passwort123"))
    db.add(admin); db.commit()

    def expect_403(fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
            assert False, "sollte HTTPException auslösen"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403

    expect_403(get_maintenance_contracts, status=None, db=db)
    expect_403(post_maintenance_contract, MaintenanceContractCreate(customer_id=1, property_id=1, title="x", next_due_date=date.today()), db=db)
    expect_403(delete_maintenance_contract, contract_id=1, db=db)


def test_ui_wires_maintenance_contracts_page_and_sidebar():
    root = Path(__file__).parents[1]
    pages_src = (root / "app/routers/pages.py").read_text(encoding="utf-8")
    assert '"/maintenance-contracts"' in pages_src
    assert (root / "app/templates/maintenance_contracts.html").exists()
    sidebar = (root / "app/templates/_sidebar.html").read_text(encoding="utf-8")
    assert "is_module_enabled('wartungen')" in sidebar
    assert 'href="/maintenance-contracts"' in sidebar
