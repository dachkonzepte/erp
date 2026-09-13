from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.auth import hash_password
from app.database import Base
from app.models import AppUser, Employee, TaskChecklistItem
from app.tasks import add_checklist_item, create_task, delete_checklist_item, delete_task, list_tasks, update_checklist_item


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def request_with_user(user):
    req = Request({"type": "http", "method": "GET", "path": "/api/tasks", "headers": [],
                   "query_string": b"", "server": ("test", 80), "client": ("test", 1234), "scheme": "http"})
    req.state.erp_user = user
    return req


def make_employee(db):
    emp = Employee(employee_number="T-1", first_name="Erika", last_name="Eins", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp); db.commit()
    return emp


def test_add_checklist_item_appears_on_the_task():
    db = db_session()
    emp = make_employee(db)
    task = create_task(db, title="Mit Checkliste", assigned_employee_id=emp.id)
    item = add_checklist_item(db, task["id"], "Erster Punkt")
    assert item["title"] == "Erster Punkt"
    assert item["done"] is False


def test_add_checklist_item_rejects_empty_title():
    db = db_session()
    emp = make_employee(db)
    task = create_task(db, title="X", assigned_employee_id=emp.id)
    try:
        add_checklist_item(db, task["id"], "   ")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_toggle_and_rename_checklist_item():
    db = db_session()
    emp = make_employee(db)
    task = create_task(db, title="X", assigned_employee_id=emp.id)
    item = add_checklist_item(db, task["id"], "Punkt")
    done = update_checklist_item(db, task["id"], item["id"], done=True)
    assert done["done"] is True
    renamed = update_checklist_item(db, task["id"], item["id"], title="Neuer Titel")
    assert renamed["title"] == "Neuer Titel"
    assert renamed["done"] is True


def test_delete_checklist_item():
    db = db_session()
    emp = make_employee(db)
    task = create_task(db, title="X", assigned_employee_id=emp.id)
    item = add_checklist_item(db, task["id"], "Punkt")
    assert delete_checklist_item(db, task["id"], item["id"]) is True
    assert delete_checklist_item(db, task["id"], item["id"]) is False


def test_checklist_items_are_included_in_task_dict():
    db = db_session()
    emp = make_employee(db)
    task = create_task(db, title="X", assigned_employee_id=emp.id)
    add_checklist_item(db, task["id"], "Punkt A")
    add_checklist_item(db, task["id"], "Punkt B")
    rows = list_tasks(db, employee_id=emp.id)
    assert len(rows[0]["checklist_items"]) == 2
    assert [i["title"] for i in rows[0]["checklist_items"]] == ["Punkt A", "Punkt B"]


def test_deleting_task_cascades_checklist_items():
    """Anders als bei den migrationsarmen Zusatztabellen zu bestehenden Kern-Tabellen (siehe
    CLAUDE.md) bekommt TaskChecklistItem eine echte cascade="all, delete-orphan"-Relationship,
    weil Task unser eigenes, neues Modul ist -- kein manuelles Aufräumen nötig."""
    db = db_session()
    emp = make_employee(db)
    task = create_task(db, title="X", assigned_employee_id=emp.id)
    add_checklist_item(db, task["id"], "Punkt")
    assert db.scalar(select(TaskChecklistItem)) is not None
    delete_task(db, task["id"])
    assert db.scalar(select(TaskChecklistItem)) is None


def test_non_admin_cannot_mutate_checklist_of_a_foreign_task():
    from app.routers.tasks import post_checklist_item
    from app.schemas import TaskChecklistItemCreate

    db = db_session()
    emp1 = make_employee(db)
    emp2 = Employee(employee_number="T-2", first_name="Otto", last_name="Zwei", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp2); db.commit()
    task = create_task(db, title="Für Erika", assigned_employee_id=emp1.id)
    user2 = AppUser(username="u2", display_name="U2", role="user", employee_id=emp2.id, active=True, password_hash=hash_password("Passwort123"))
    db.add(user2); db.commit()
    try:
        post_checklist_item(task["id"], TaskChecklistItemCreate(title="x"), request_with_user(user2), db=db)
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
