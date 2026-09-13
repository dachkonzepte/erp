from datetime import date, timedelta

from app.auth import hash_password
from app.maintenance_contracts import (
    check_due_contracts_and_create_reminders, create_contract, delete_contract,
    list_contracts, set_contract_archived,
)
from app.models import AppUser, Task
from app.modules import set_module_enabled
from app.tasks import create_task, list_tasks, set_task_archived
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property


def test_set_task_archived_hides_from_default_list_but_stays_retrievable():
    db = db_session()
    task = create_task(db, title="Alte Aufgabe")
    assert task["archived"] is False

    archived = set_task_archived(db, task["id"], True)
    assert archived["archived"] is True
    assert [t["id"] for t in list_tasks(db)] == []
    assert [t["id"] for t in list_tasks(db, include_archived=True)] == [task["id"]]

    unarchived = set_task_archived(db, task["id"], False)
    assert unarchived["archived"] is False
    assert [t["id"] for t in list_tasks(db)] == [task["id"]]


def test_set_task_archived_reports_missing_id():
    db = db_session()
    assert set_task_archived(db, 999, True) is None


def test_set_contract_archived_hides_from_default_list_but_stays_retrievable():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "DachCheck", 12, date.today())

    archived = set_contract_archived(db, contract["id"], True)
    assert archived["archived"] is True
    assert list_contracts(db) == []
    assert [c["id"] for c in list_contracts(db, include_archived=True)] == [contract["id"]]

    unarchived = set_contract_archived(db, contract["id"], False)
    assert unarchived["archived"] is False
    assert [c["id"] for c in list_contracts(db)] == [contract["id"]]


def test_check_due_skips_archived_contracts():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Archiviert und fällig", 12, date.today() - timedelta(days=1))
    set_contract_archived(db, contract["id"], True)
    assert check_due_contracts_and_create_reminders(db) == []
    assert db.query(Task).count() == 0


def test_delete_contract_also_deletes_its_reminder_tasks():
    """Regressionstest für den von Tobias gemeldeten Fall: eine gelöschte Wartung blieb als
    Aufgabe zurück, weil die Aufgabe nur locker über source_url an den Vertrag gebunden ist
    (keine FK-Beziehung, siehe Docstring von delete_contract())."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "DachCheck", 12, date.today() - timedelta(days=1))
    check_due_contracts_and_create_reminders(db)
    assert db.query(Task).filter(Task.source_url == f"/maintenance-contracts/{contract['id']}").count() == 1

    # Eine andere, unabhängige Aufgabe mit demselben source_module aber anderem Vertrag/URL
    # darf beim Löschen nicht mitgerissen werden.
    other = create_contract(db, customer.id, prop.id, "Anderer Vertrag", 12, date.today() - timedelta(days=1))
    check_due_contracts_and_create_reminders(db)

    assert delete_contract(db, contract["id"]) is True
    assert db.query(Task).filter(Task.source_url == f"/maintenance-contracts/{contract['id']}").count() == 0
    assert db.query(Task).filter(Task.source_url == f"/maintenance-contracts/{other['id']}").count() == 1


def test_archive_endpoints_return_403_when_module_disabled():
    from app.routers.maintenance_contracts import archive_maintenance_contract, unarchive_maintenance_contract
    from app.routers.tasks import archive_task_endpoint, unarchive_task_endpoint

    db = db_session()
    set_module_enabled(db, "wartungen", False)
    set_module_enabled(db, "aufgabenmanagement", False)
    admin = AppUser(username="admin1", display_name="Admin", role="admin", active=True, password_hash=hash_password("Passwort123"))
    db.add(admin); db.commit()

    def expect_403(fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
            assert False, "sollte HTTPException auslösen"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403

    expect_403(archive_maintenance_contract, contract_id=1, db=db)
    expect_403(unarchive_maintenance_contract, contract_id=1, db=db)
    expect_403(archive_task_endpoint, task_id=1, db=db)
    expect_403(unarchive_task_endpoint, task_id=1, db=db)
