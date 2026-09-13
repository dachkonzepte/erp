from datetime import date
from pathlib import Path
import re

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.auth import hash_password
from app.dashboard import get_widget_layout, save_widget_layout
from app.database import Base
from app.main import create_customer, create_project, create_quote
from app.models import AppUser, Employee, Order, UserDashboardWidget, WorkPreparation, WorkPreparationTask
from app.routers.work_preparation import get_open_work_preparation_tasks
from app.schemas import CustomerCreate, ProjectCreate, QuoteCreate
from app.work_preparation import list_open_tasks


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def request_with_user(user):
    req = Request({"type": "http", "method": "GET", "path": "/api/work-preparation/tasks", "headers": [],
                   "query_string": b"", "server": ("test", 80), "client": ("test", 1234), "scheme": "http"})
    req.state.erp_user = user
    return req


def make_employee(db, number, first, last):
    e = Employee(employee_number=number, first_name=first, last_name=last, employee_group="gewerblich", hourly_wage="20", weekly_hours="40", active=True)
    db.add(e); db.commit()
    return e


def make_order_with_tasks(db):
    """Zwei Mitarbeiter, ein Auftrag mit drei AV-Aufgaben: zwei offen (je einem
    Mitarbeiter zugeordnet, eine mit Fälligkeitsdatum), eine bereits erledigt."""
    emp1 = make_employee(db, "D-1", "Erika", "Eins")
    emp2 = make_employee(db, "D-2", "Otto", "Zwei")
    customer = create_customer(CustomerCreate(last_name="Dashboardkunde"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Dashboardprojekt"), db)
    quote = create_quote(project.id, QuoteCreate(title="Dashboardangebot"), db)
    order = Order(
        order_number="A-DASH-1", project_id=project.id, source_quote_id=quote.id,
        quote_number_snapshot=quote.quote_number, title="Dashboardauftrag", customer_name="Dashboardkunde",
    )
    db.add(order); db.commit()
    prep = WorkPreparation(order_id=order.id, status="offen")
    db.add(prep); db.commit()
    t1 = WorkPreparationTask(preparation_id=prep.id, title="Geruest bestellen", status="offen", priority="hoch", due_date=date(2026, 9, 10), assigned_employee_id=emp1.id)
    t2 = WorkPreparationTask(preparation_id=prep.id, title="Material abholen", status="offen", priority="normal", assigned_employee_id=emp2.id)
    t3 = WorkPreparationTask(preparation_id=prep.id, title="Bereits erledigt", status="erledigt", assigned_employee_id=emp1.id)
    db.add_all([t1, t2, t3]); db.commit()
    return emp1, emp2, order


def test_list_open_tasks_excludes_done_and_sorts_by_due_date():
    db = db_session()
    emp1, emp2, order = make_order_with_tasks(db)
    rows = list_open_tasks(db)
    assert [r["title"] for r in rows] == ["Geruest bestellen", "Material abholen"]
    assert rows[0]["order_number"] == "A-DASH-1"
    assert rows[0]["project_name"] == "Dashboardprojekt"


def test_list_open_tasks_filters_by_employee():
    db = db_session()
    emp1, emp2, order = make_order_with_tasks(db)
    rows = list_open_tasks(db, employee_id=emp1.id)
    assert [r["title"] for r in rows] == ["Geruest bestellen"]


def test_non_admin_locked_to_own_employee_regardless_of_param():
    db = db_session()
    emp1, emp2, order = make_order_with_tasks(db)
    user = AppUser(username="sb1", display_name="Sachbearbeiter Eins", role="user", employee_id=emp1.id, active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    rows = get_open_work_preparation_tasks(request_with_user(user), employee_id=emp2.id, db=db)
    assert [r["title"] for r in rows] == ["Geruest bestellen"]


def test_non_admin_without_employee_link_gets_403():
    db = db_session()
    make_order_with_tasks(db)
    user = AppUser(username="sb2", display_name="Ohne Mitarbeiter", role="user", employee_id=None, active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    try:
        get_open_work_preparation_tasks(request_with_user(user), employee_id=None, db=db)
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403


def test_admin_can_choose_specific_employee_or_all():
    db = db_session()
    emp1, emp2, order = make_order_with_tasks(db)
    admin = AppUser(username="admin1", display_name="Admin", role="admin", employee_id=None, active=True, password_hash=hash_password("Passwort123"))
    db.add(admin); db.commit()
    all_rows = get_open_work_preparation_tasks(request_with_user(admin), employee_id=None, db=db)
    assert len(all_rows) == 2
    emp2_rows = get_open_work_preparation_tasks(request_with_user(admin), employee_id=emp2.id, db=db)
    assert [r["title"] for r in emp2_rows] == ["Material abholen"]


def test_default_widget_layout_is_not_persisted_until_saved():
    db = db_session()
    user = AppUser(username="u1", display_name="U1", role="user", active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    layout = get_widget_layout(db, user.id)
    assert [w["widget_key"] for w in layout] == ["my_tasks", "kpis", "active_projects"]
    assert all(w["visible"] for w in layout)
    assert len(db.scalars(select(UserDashboardWidget)).all()) == 0


def test_save_widget_layout_persists_and_isolates_between_users():
    db = db_session()
    u1 = AppUser(username="u2", display_name="U2", role="user", active=True, password_hash=hash_password("Passwort123"))
    u2 = AppUser(username="u3", display_name="U3", role="user", active=True, password_hash=hash_password("Passwort123"))
    db.add_all([u1, u2]); db.commit()

    saved = save_widget_layout(db, u1.id, [
        {"widget_key": "kpis", "sort_order": 10, "visible": True},
        {"widget_key": "my_tasks", "sort_order": 20, "visible": False},
    ])
    assert [w["widget_key"] for w in saved] == ["kpis", "my_tasks"]
    assert next(w for w in saved if w["widget_key"] == "my_tasks")["visible"] is False

    reloaded = get_widget_layout(db, u1.id)
    assert [w["widget_key"] for w in reloaded] == ["kpis", "my_tasks"]

    # anderer Benutzer bleibt unberuehrt, bekommt weiterhin den Standard
    untouched = get_widget_layout(db, u2.id)
    assert [w["widget_key"] for w in untouched] == ["my_tasks", "kpis", "active_projects"]


def test_dashboard_is_new_start_page_and_service_catalog_moved():
    root = Path(__file__).parents[1]
    pages_src = (root / "app/routers/pages.py").read_text(encoding="utf-8")
    assert 'name="dashboard.html"' in pages_src
    assert '"/leistungskatalog"' in pages_src and 'name="index.html"' in pages_src

    dashboard_html = (root / "app/templates/dashboard.html").read_text(encoding="utf-8")
    assert "WIDGETS" in dashboard_html
    assert "Meine Aufgaben" in dashboard_html and "Kennzahlen" in dashboard_html and "Laufende Projekte" in dashboard_html
    assert "/api/dashboard/widgets" in dashboard_html
    assert "/api/work-preparation/tasks" in dashboard_html

    # Seit 1.3.27 hat "Leistungskatalog" keinen eigenen Sidebar-Eintrag mehr -- der Einstieg
    # läuft über Stammdaten -> Leistungskataloge (siehe CLAUDE.md "Leistungskatalog vs.
    # Stammdaten"), /leistungskatalog selbst bleibt als Seite unverändert erreichbar.
    master_data_html = (root / "app/templates/master_data.html").read_text(encoding="utf-8")
    assert 'href="/leistungskatalog"' in master_data_html

    main_src = (root / "app/main.py").read_text(encoding="utf-8")
    assert "dashboard.router" in main_src
    assert re.match(r"^\d+\.\d+\.\d+$", (root / "VERSION").read_text(encoding="utf-8").strip())
