from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.auth import hash_password
from app.database import Base
from app.models import AppUser, Employee
from app.modules import set_module_enabled
from app.routers.tasks import delete_task_endpoint, get_tasks, post_task, put_task
from app.schemas import TaskCreate, TaskUpdate
from app.tasks import create_task, list_tasks, update_task


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def request_with_user(user):
    req = Request({"type": "http", "method": "GET", "path": "/api/tasks", "headers": [],
                   "query_string": b"", "server": ("test", 80), "client": ("test", 1234), "scheme": "http"})
    req.state.erp_user = user
    return req


def make_employees(db):
    emp1 = Employee(employee_number="T-1", first_name="Erika", last_name="Eins", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    emp2 = Employee(employee_number="T-2", first_name="Otto", last_name="Zwei", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add_all([emp1, emp2]); db.commit()
    return emp1, emp2


def test_list_tasks_filters_by_employee_status_and_project():
    db = db_session()
    emp1, emp2 = make_employees(db)
    create_task(db, title="Für Erika, offen", assigned_employee_id=emp1.id, due_date=date(2026, 9, 10))
    create_task(db, title="Für Otto, offen", assigned_employee_id=emp2.id, due_date=date(2026, 9, 5))
    t3 = create_task(db, title="Für Erika, erledigt", assigned_employee_id=emp1.id)
    update_task(db, t3["id"], title=t3["title"], description=None, status="erledigt", priority="normal", due_date=None, assigned_employee_id=emp1.id, project_id=None)

    all_rows = list_tasks(db)
    assert len(all_rows) == 3
    emp1_rows = list_tasks(db, employee_id=emp1.id)
    assert {r["title"] for r in emp1_rows} == {"Für Erika, offen", "Für Erika, erledigt"}
    open_rows = list_tasks(db, status="offen")
    assert {r["title"] for r in open_rows} == {"Für Erika, offen", "Für Otto, offen"}
    # Sortierung: nach Fälligkeit, NULLs zuletzt -- "Für Otto" (5.9.) vor "Für Erika" (10.9.)
    assert [r["title"] for r in list_tasks(db, status="offen")] == ["Für Otto, offen", "Für Erika, offen"]


def test_update_task_sets_and_clears_completed_at():
    db = db_session()
    emp1, _ = make_employees(db)
    created = create_task(db, title="Test", assigned_employee_id=emp1.id)
    assert created["completed_at"] is None
    done = update_task(db, created["id"], title="Test", description=None, status="erledigt", priority="normal", due_date=None, assigned_employee_id=emp1.id, project_id=None)
    assert done["completed_at"] is not None
    reopened = update_task(db, created["id"], title="Test", description=None, status="offen", priority="normal", due_date=None, assigned_employee_id=emp1.id, project_id=None)
    assert reopened["completed_at"] is None


def test_create_task_with_automation_source_fields_round_trips():
    """Belegt die Automatisierungs-Anschlussstelle: ein künftiges Modul (hier nur
    simuliert, da es noch nicht existiert) ruft create_task() mit source_*-Feldern auf."""
    db = db_session()
    emp1, _ = make_employees(db)
    result = create_task(
        db, title="Rechnung erstellen für Wartungsbericht WB-2026-004",
        assigned_employee_id=emp1.id, source_module="wartungsbericht",
        source_label="Wartungsbericht WB-2026-004", source_url="/wartungsberichte/42",
    )
    assert result["source_module"] == "wartungsbericht"
    assert result["source_label"] == "Wartungsbericht WB-2026-004"
    assert result["source_url"] == "/wartungsberichte/42"
    reloaded = list_tasks(db, employee_id=emp1.id)[0]
    assert reloaded["source_label"] == "Wartungsbericht WB-2026-004"


def test_non_admin_locked_to_own_tasks_regardless_of_param():
    db = db_session()
    emp1, emp2 = make_employees(db)
    create_task(db, title="Für Erika", assigned_employee_id=emp1.id)
    create_task(db, title="Für Otto", assigned_employee_id=emp2.id)
    user = AppUser(username="u1", display_name="U1", role="user", employee_id=emp1.id, active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    rows = get_tasks(request_with_user(user), employee_id=emp2.id, status=None, project_id=None, db=db)
    assert [r["title"] for r in rows] == ["Für Erika"]


def test_non_admin_without_employee_link_gets_403():
    db = db_session()
    user = AppUser(username="u2", display_name="U2", role="user", employee_id=None, active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    try:
        get_tasks(request_with_user(user), employee_id=None, status=None, project_id=None, db=db)
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403


def test_admin_can_choose_employee_or_all():
    db = db_session()
    emp1, emp2 = make_employees(db)
    create_task(db, title="Für Erika", assigned_employee_id=emp1.id)
    create_task(db, title="Für Otto", assigned_employee_id=emp2.id)
    admin = AppUser(username="admin1", display_name="Admin", role="admin", employee_id=None, active=True, password_hash=hash_password("Passwort123"))
    db.add(admin); db.commit()
    all_rows = get_tasks(request_with_user(admin), employee_id=None, status=None, project_id=None, db=db)
    assert len(all_rows) == 2
    emp2_rows = get_tasks(request_with_user(admin), employee_id=emp2.id, status=None, project_id=None, db=db)
    assert [r["title"] for r in emp2_rows] == ["Für Otto"]


def test_tasks_endpoints_return_403_when_module_disabled_even_for_admin():
    db = db_session()
    set_module_enabled(db, "aufgabenmanagement", False)
    admin = AppUser(username="admin2", display_name="Admin", role="admin", active=True, password_hash=hash_password("Passwort123"))
    db.add(admin); db.commit()

    def expect_403(fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
            assert False, "sollte 403 auslösen"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403

    expect_403(get_tasks, request_with_user(admin), employee_id=None, status=None, project_id=None, db=db)
    expect_403(post_task, TaskCreate(title="x"), request_with_user(admin), db=db)
    expect_403(put_task, 1, TaskUpdate(title="x", status="offen", priority="normal"), db=db)
    expect_403(delete_task_endpoint, 1, db=db)


def test_ui_wires_task_page_sidebar_and_dashboard():
    root = Path(__file__).parents[1]
    pages_src = (root / "app/routers/pages.py").read_text(encoding="utf-8")
    assert '"/tasks"' in pages_src
    assert (root / "app/templates/tasks.html").exists()
    sidebar = (root / "app/templates/_sidebar.html").read_text(encoding="utf-8")
    assert "is_module_enabled('aufgabenmanagement')" in sidebar
    assert 'href="/tasks"' in sidebar
    dashboard_html = (root / "app/templates/dashboard.html").read_text(encoding="utf-8")
    assert "/api/tasks" in dashboard_html
    assert "/api/modules" in dashboard_html
