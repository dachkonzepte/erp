"""Aufgaben ohne Zuständigkeit (seit 1.8.18).

1. Jedes Büro-Konto (buero_auftrag aufwärts) sieht fremde Aufgaben ohne Zuständigkeit, ein Monteur
   nicht; die persönlich zugewiesene Aufgabe eines Kollegen bleibt unsichtbar (Gegenprobe).
2. Eine über ihren Ursprung rollengebundene Aufgabe (min_visible_role) bleibt auch ohne
   Zuständigkeit auf diese Rolle beschränkt -- Liste, Übernehmen, Änderungshistorie.
3. "Übernehmen" ist ein bedingtes UPDATE: übernehmen zwei gleichzeitig, gewinnt einer, der andere
   bekommt TASK_ALREADY_TAKEN statt die Aufgabe still zu überschreiben. Die Übernahme steht in der
   Änderungshistorie.
4. Dashboard: "Ohne Zuständigkeit" ist Standard-Widget, auch in bereits gespeicherten Layouts.

Der Wettlauf wird zweimal geprüft: in SQLite deterministisch über eine veraltete Session (genau das
Fenster zwischen Prüfen und Schreiben), gegen PostgreSQL mit zwei echten, gleichzeitigen Threads
(opt-in über ERP_TEST_POSTGRES_URL, in einem Wegwerf-Schema, Regel 16)."""

import os
import threading
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.dashboard import get_widget_layout, save_widget_layout
from app.models import AppUser, AuditLog, Employee, Task
from app.tasks import TASK_ALREADY_TAKEN, claim_task, create_task, list_tasks_for_user
from tests.test_v279_task_visibility import db_session, make_employees, make_user


def _transient_user(role, employee_id, name):
    """Wie der Anmeldekontext in router_test_client: nicht gespeichert, nur Rolle und Verknüpfung."""
    return AppUser(username=name, display_name=name, role=role, employee_id=employee_id,
                   active=True, password_hash="-")


def _task_audit_rows(db, task_id):
    return db.scalars(select(AuditLog).where(AuditLog.entity_type == "Aufgabe",
                                             AuditLog.entity_id == str(task_id))).all()


# --- 1. Sichtbarkeit: Büro ja, Monteur nein ---

@pytest.mark.parametrize("role", ["buero_auftrag", "buero_finanzen"])
def test_office_sees_foreign_unassigned_task_but_not_colleagues_assigned_one(router_test_client, threaded_db_session, role):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, emp2 = make_employees(db)
    colleague = make_user(db, "buero_auftrag", employee_id=emp2.id, username="kollege")
    create_task(db, title="Vom Kollegen, ohne Zuständigkeit", created_by_user_id=colleague.id)
    create_task(db, title="Für Otto persönlich", assigned_employee_id=emp2.id, created_by_user_id=colleague.id)
    client = router_test_client(db, tasks_router.router, role=role, employee_id=emp1.id)

    resp = client.get("/api/tasks?unassigned_only=true")
    assert resp.status_code == 200, resp.text
    assert [t["title"] for t in resp.json()] == ["Vom Kollegen, ohne Zuständigkeit"]


def test_field_does_not_see_unassigned_task_office_does(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, _ = make_employees(db)
    create_task(db, title="Ohne Zuständigkeit")

    field_client = router_test_client(db, tasks_router.router, role="field", employee_id=emp1.id)
    assert field_client.get("/api/tasks?unassigned_only=true").status_code == 403
    assert list_tasks_for_user(db, _transient_user("field", emp1.id, "monteur"), unassigned_only=True) == []

    # Gegenprobe: dieselbe Aufgabe ist für ein Büro-Konto da.
    office_client = router_test_client(db, tasks_router.router, role="buero_auftrag", employee_id=emp1.id)
    assert [t["title"] for t in office_client.get("/api/tasks?unassigned_only=true").json()] == ["Ohne Zuständigkeit"]


# --- 2. Rollengebundene Aufgabe bleibt beschränkt ---

def test_finance_bound_task_stays_hidden_and_unclaimable_for_buero_auftrag(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, emp2 = make_employees(db)
    create_task(db, title="Allgemein")
    bound = create_task(db, title="Skonto nutzen", min_visible_role="buero_finanzen")

    auftrag = router_test_client(db, tasks_router.router, role="buero_auftrag", employee_id=emp1.id)
    assert [t["title"] for t in auftrag.get("/api/tasks?unassigned_only=true").json()] == ["Allgemein"]
    denied = auftrag.post(f"/api/tasks/{bound['id']}/claim")
    assert denied.status_code == 403, denied.text
    assert db.get(Task, bound["id"]).assigned_employee_id is None

    # Gegenprobe: Finanzen sieht und übernimmt sie.
    finanzen = router_test_client(db, tasks_router.router, role="buero_finanzen", employee_id=emp2.id)
    assert {t["title"] for t in finanzen.get("/api/tasks?unassigned_only=true").json()} == {"Allgemein", "Skonto nutzen"}
    claimed = finanzen.post(f"/api/tasks/{bound['id']}/claim")
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["assigned_employee_id"] == emp2.id


def test_claim_history_entry_is_admin_only(router_test_client, threaded_db_session):
    """Der Eintrag nennt den Titel -- eine finanz-gebundene Aufgabe darf darüber nicht bei
    buero_auftrag auftauchen, eine zugewiesene nicht bei Kollegen. Deshalb nur Admin."""
    from app.routers import audit as audit_router
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, _ = make_employees(db)
    bound = create_task(db, title="Kündigungsfrist Leasing", min_visible_role="buero_finanzen")
    finanzen = router_test_client(db, tasks_router.router, role="buero_finanzen", employee_id=emp1.id)
    assert finanzen.post(f"/api/tasks/{bound['id']}/claim").status_code == 200

    def task_rows(role):
        client = router_test_client(db, audit_router.router, role=role)
        resp = client.get("/api/audit-logs?entity_type=Aufgabe")
        assert resp.status_code == 200, resp.text
        return resp.json()

    admin_rows = task_rows("admin")
    assert len(admin_rows) == 1
    assert "Kündigungsfrist Leasing" in admin_rows[0]["entity_label"]
    assert task_rows("buero_finanzen") == []
    assert task_rows("buero_auftrag") == []


# --- 3. Übernehmen: Historie und doppeltes Übernehmen ---

def test_claim_writes_history_entry_failed_claim_writes_none():
    db = db_session()
    emp1, emp2 = make_employees(db)
    task = create_task(db, title="Rückruf Kunde")
    anna = _transient_user("buero_auftrag", emp1.id, "Anna")

    claim_task(db, task["id"], anna)
    rows = _task_audit_rows(db, task["id"])
    assert len(rows) == 1
    row = rows[0]
    assert (row.action, row.field_name, row.old_value, row.new_value) == ("geändert", "assigned_employee_id", None, "Erika Eins")
    assert row.field_label == "Zuständig (übernommen)"
    assert row.actor_name == "Anna"
    assert row.entity_label == f"Nr. {task['id']} · Rückruf Kunde"

    # Gegenprobe: ein abgelehntes zweites Übernehmen hinterlässt keinen Eintrag.
    with pytest.raises(ValueError, match="bereits jemand anderes"):
        claim_task(db, task["id"], _transient_user("buero_auftrag", emp2.id, "Otto"))
    assert len(_task_audit_rows(db, task["id"])) == 1


def test_second_claim_via_router_gets_clear_message_and_first_keeps_task(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, emp2 = make_employees(db)
    task = create_task(db, title="Offen")
    first = router_test_client(db, tasks_router.router, role="buero_auftrag", employee_id=emp1.id)
    second = router_test_client(db, tasks_router.router, role="buero_finanzen", employee_id=emp2.id)

    assert first.post(f"/api/tasks/{task['id']}/claim").status_code == 200
    resp = second.post(f"/api/tasks/{task['id']}/claim")
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == TASK_ALREADY_TAKEN
    db.expire_all()
    assert db.get(Task, task["id"]).assigned_employee_id == emp1.id


def test_claim_race_window_second_claim_loses_instead_of_overwriting(tmp_path):
    """Genau das Fenster zwischen Prüfen und Schreiben: Session A hat die Aufgabe noch als
    empfängerlos gelesen, B übernimmt und committet, dann schreibt A. Vor 1.8.18 überschrieb A
    die Zuweisung von B (Lesen-Prüfen-Schreiben); jetzt trifft As bedingtes UPDATE keine Zeile."""
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    setup = Session()
    emp1, emp2 = make_employees(setup)
    task_id, emp1_id, emp2_id = create_task(setup, title="Offen")["id"], emp1.id, emp2.id
    setup.close()

    session_a, session_b = Session(), Session()
    # A liest: noch frei. Die Referenz festhalten -- die Session hält Objekte nur schwach, ohne
    # sie läse claim_task() neu und scheiterte schon an der Vorprüfung, nicht am UPDATE.
    stale = session_a.get(Task, task_id)
    assert stale.assigned_employee_id is None
    claim_task(session_b, task_id, _transient_user("buero_auftrag", emp2_id, "B"))
    with pytest.raises(ValueError) as exc:
        claim_task(session_a, task_id, _transient_user("buero_auftrag", emp1_id, "A"))
    assert str(exc.value) == TASK_ALREADY_TAKEN
    del stale

    check = Session()
    assert check.get(Task, task_id).assigned_employee_id == emp2_id
    assert len(_task_audit_rows(check, task_id)) == 1
    for s in (session_a, session_b, check):
        s.close()
    engine.dispose()


PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.mark.skipif(not PG_TEST_DATABASE_URL, reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
def test_two_simultaneous_claims_on_postgresql_exactly_one_wins():
    schema = f"pgtest_claim_{uuid.uuid4().hex[:8]}"
    admin_engine = create_engine(PG_TEST_DATABASE_URL)
    with admin_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        emp1, emp2 = make_employees(setup)
        task_id, employees = create_task(setup, title="Offen")["id"], {"A": emp1.id, "B": emp2.id}
        setup.close()

        barrier = threading.Barrier(2)
        results = {}

        def worker(name):
            session = Session()
            try:
                user = _transient_user("buero_auftrag", employees[name], name)
                barrier.wait()
                results[name] = claim_task(session, task_id, user)["assigned_employee_id"]
            except ValueError as exc:
                results[name] = str(exc)
            finally:
                session.close()

        threads = [threading.Thread(target=worker, args=(name,)) for name in employees]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        winners = [name for name, value in results.items() if value == employees[name]]
        losers = [name for name, value in results.items() if value == TASK_ALREADY_TAKEN]
        assert len(winners) == 1 and len(losers) == 1, results
        check = Session()
        assert check.get(Task, task_id).assigned_employee_id == employees[winners[0]]
        assert len(_task_audit_rows(check, task_id)) == 1
        check.close()
    finally:
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin_engine.dispose()


# --- 4. Dashboard ---

def test_unassigned_widget_is_default_and_reaches_saved_layouts():
    db = db_session()
    fresh = make_user(db, "buero_auftrag", username="neu")
    saved = make_user(db, "buero_auftrag", username="alt")
    removed = make_user(db, "buero_auftrag", username="weg")

    assert [w["widget_key"] for w in get_widget_layout(db, fresh.id)] == ["my_tasks", "open_office_tasks", "kpis", "active_projects"]

    # Layout aus der Zeit vor 1.8.18 (ohne Zeile für das Widget): es erscheint trotzdem.
    save_widget_layout(db, saved.id, [
        {"widget_key": "my_tasks", "sort_order": 10, "visible": True},
        {"widget_key": "kpis", "sort_order": 20, "visible": True},
        {"widget_key": "active_projects", "sort_order": 30, "visible": True},
    ])
    layout = get_widget_layout(db, saved.id)
    assert [w["widget_key"] for w in layout] == ["my_tasks", "open_office_tasks", "kpis", "active_projects"]
    assert next(w for w in layout if w["widget_key"] == "open_office_tasks")["visible"] is True

    # Gegenprobe: bewusst entfernt (ausgeblendete Zeile) bleibt entfernt.
    save_widget_layout(db, removed.id, [
        {"widget_key": "my_tasks", "sort_order": 10, "visible": True},
        {"widget_key": "open_office_tasks", "sort_order": 15, "visible": False},
    ])
    widget = next(w for w in get_widget_layout(db, removed.id) if w["widget_key"] == "open_office_tasks")
    assert widget["visible"] is False


def test_dashboard_widget_checks_current_office_roles_not_the_old_office_role():
    html = (Path(__file__).parents[1] / "app" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "['admin','office']" not in html
    assert "['admin','buero_finanzen','buero_auftrag'].includes(authStatus.user.role)" in html
    assert "open_office_tasks:{label:'Ohne Zuständigkeit'" in html
