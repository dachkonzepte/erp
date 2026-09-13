from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Employee
from app.task_columns import create_column, delete_column, list_columns, reorder_columns, update_column
from app.tasks import create_task, update_task


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_employee(db):
    emp = Employee(employee_number="T-1", first_name="Erika", last_name="Eins", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp); db.commit()
    return emp


def test_list_columns_self_seeds_the_three_defaults_on_an_empty_database():
    db = db_session()
    cols = list_columns(db)
    assert [c["key"] for c in cols] == ["offen", "in_arbeit", "erledigt"]
    assert cols[0]["is_done"] is False
    assert cols[2]["is_done"] is True


def test_create_task_defaults_to_the_column_with_the_lowest_sort_order():
    db = db_session()
    emp = make_employee(db)
    task = create_task(db, title="Ohne Status", assigned_employee_id=emp.id)
    assert task["status"] == "offen"


def test_create_column_generates_a_unique_slug_key():
    db = db_session()
    c1 = create_column(db, "Wartet auf Kunde")
    c2 = create_column(db, "Wartet auf Kunde")
    assert c1["key"] == "wartet_auf_kunde"
    assert c2["key"] == "wartet_auf_kunde_2"
    assert c1["sort_order"] < c2["sort_order"]


def test_update_column_renames_label_but_keeps_key_stable():
    db = db_session()
    cols = list_columns(db)
    offen_id = next(c["id"] for c in cols if c["key"] == "offen")
    updated = update_column(db, offen_id, label="Neu eingegangen")
    assert updated["key"] == "offen"
    assert updated["label"] == "Neu eingegangen"


def test_reorder_columns_updates_sort_order():
    db = db_session()
    cols = list_columns(db)
    ids = [c["id"] for c in cols]
    reversed_ids = list(reversed(ids))
    reordered = reorder_columns(db, reversed_ids)
    assert [c["id"] for c in reordered] == reversed_ids


def test_reorder_columns_rejects_incomplete_id_list():
    db = db_session()
    cols = list_columns(db)
    try:
        reorder_columns(db, [cols[0]["id"]])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_delete_column_blocked_while_tasks_still_use_it():
    db = db_session()
    emp = make_employee(db)
    create_task(db, title="Aufgabe", assigned_employee_id=emp.id, status="offen")
    cols = list_columns(db)
    offen_id = next(c["id"] for c in cols if c["key"] == "offen")
    try:
        delete_column(db, offen_id)
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "verwenden" in str(exc)


def test_delete_column_blocked_when_it_is_the_last_one():
    db = db_session()
    cols = list_columns(db)
    for c in cols[1:]:
        delete_column(db, c["id"])
    remaining = list_columns(db)
    assert len(remaining) == 1
    try:
        delete_column(db, remaining[0]["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "letzte" in str(exc)


def test_delete_column_succeeds_once_unused():
    db = db_session()
    new_col = create_column(db, "Archiv", is_done=True)
    delete_column(db, new_col["id"])
    assert new_col["key"] not in {c["key"] for c in list_columns(db)}


def test_update_task_uses_custom_column_is_done_flag_for_completed_at():
    """completed_at darf sich nicht mehr am Literal 'erledigt' orientieren, sondern muss jede
    Spalte mit is_done=True als abgeschlossen behandeln."""
    db = db_session()
    emp = make_employee(db)
    archiv = create_column(db, "Archiviert", is_done=True)
    task = create_task(db, title="Custom-Spalten-Test", assigned_employee_id=emp.id)
    assert task["completed_at"] is None
    moved = update_task(db, task["id"], title=task["title"], description=None, status=archiv["key"],
                         priority="normal", due_date=None, assigned_employee_id=emp.id, project_id=None)
    assert moved["status_is_done"] is True
    assert moved["completed_at"] is not None
    reopened = update_task(db, task["id"], title=task["title"], description=None, status="offen",
                            priority="normal", due_date=None, assigned_employee_id=emp.id, project_id=None)
    assert reopened["completed_at"] is None


def test_update_task_rejects_unknown_status():
    db = db_session()
    emp = make_employee(db)
    task = create_task(db, title="X", assigned_employee_id=emp.id)
    try:
        update_task(db, task["id"], title="X", description=None, status="nicht_vorhanden",
                    priority="normal", due_date=None, assigned_employee_id=emp.id, project_id=None)
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
