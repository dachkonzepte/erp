"""Änderung am Aufgabenmodul (seit 1.4.3, siehe CLAUDE.md "Änderung am Aufgabenmodul"):
empfängerlose Aufgaben werden für ALLE Büro-/Admin-Konten sichtbar, nicht nur für den Admin
bzw. den zufällig zugewiesenen Mitarbeiter. Rollenbestimmung läuft dabei zentral über
has_min_role() (app/permissions.py, seit der Vier-Rollen-Erweiterung -- siehe CLAUDE.md
"Rechtekonzept" -> "Vier Rollen") statt einer eigenen, zweiten is_admin-Prüfung: sowohl
buero_finanzen als auch buero_auftrag erfüllen den Mindestrang buero_auftrag, beide werden
hier deshalb gleich behandelt ("buero_auftrag" im Testcode unten steht repräsentativ für "irgendeine
Bürorolle", siehe die dedizierte Hierarchie-Prüfung in test_v281_role_hierarchy.py für den
Nachweis, dass buero_finanzen dort dasselbe leistet).

Drei Dinge werden hier belegt:
1. app/tasks.py::list_tasks_for_user() ist die EINE Stelle, an der jede Sichtbarkeitsregel
   entschieden wird -- Admin frei, Büro auf eigene employee_id ODER (bei unassigned_only) den
   gemeinsamen Eingang, niemals auf Kollegen-Aufgaben.
2. claim_task()/release_task() -- "Übernehmen" weist fest zu (kein dritter Zustand), lehnt
   bereits vergebene Aufgaben ab, verlangt eine employee_id-Verknüpfung; "Zurück in den
   Büro-Eingang" hat bewusst KEINE Eigentümerschafts-Prüfung (Konsistenz mit der bereits
   bestehenden Lücke bei PUT/DELETE/archive, siehe CLAUDE.md "Aufgabe").
3. Der verlangte Angriffstest: ein Monteur kommt über KEINEN Weg an eine empfängerlose
   Büro-Aufgabe -- auch nicht über den Übernehmen-Endpunkt mit einer geratenen ID --, und ein
   Büro-Konto sieht die empfängerlosen, aber nicht die persönlich zugewiesenen Aufgaben der
   Kollegen."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.database import Base
from app.models import AppUser, Employee
from app.permissions import ROLE_OFFICE_AUFTRAG, has_min_role
from app.tasks import claim_task, create_task, list_tasks, list_tasks_for_user, release_task


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_employees(db):
    emp1 = Employee(employee_number="V-1", first_name="Erika", last_name="Eins", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    emp2 = Employee(employee_number="V-2", first_name="Otto", last_name="Zwei", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add_all([emp1, emp2]); db.commit()
    return emp1, emp2


def make_user(db, role, employee_id=None, username="u"):
    user = AppUser(username=username, display_name=username, role=role, employee_id=employee_id,
                    active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    return user


# --- has_min_role() / list_tasks() Grundlagen ---

def test_has_min_role_is_the_shared_check():
    """Seit der Vier-Rollen-Erweiterung nutzt list_tasks_for_user() has_min_role(user,
    ROLE_OFFICE_AUFTRAG) statt has_role(user, ROLE_ADMIN, ROLE_OFFICE) -- admin UND
    buero_finanzen erfüllen diesen Mindestrang automatisch (Hierarchie), buero_auftrag ist
    die Schwelle selbst, field bleibt darunter."""
    admin = AppUser(username="a", display_name="A", role="admin", active=True, password_hash="x")
    finanzen = AppUser(username="b1", display_name="B1", role="buero_finanzen", active=True, password_hash="x")
    auftrag = AppUser(username="b2", display_name="B2", role="buero_auftrag", active=True, password_hash="x")
    field = AppUser(username="c", display_name="C", role="field", active=True, password_hash="x")
    assert has_min_role(admin, ROLE_OFFICE_AUFTRAG)
    assert has_min_role(finanzen, ROLE_OFFICE_AUFTRAG)
    assert has_min_role(auftrag, ROLE_OFFICE_AUFTRAG)
    assert not has_min_role(field, ROLE_OFFICE_AUFTRAG)
    assert not has_min_role(None, ROLE_OFFICE_AUFTRAG)


def test_list_tasks_unassigned_only_ignores_employee_id_and_takes_precedence():
    db = db_session()
    emp1, emp2 = make_employees(db)
    create_task(db, title="Für Erika", assigned_employee_id=emp1.id)
    create_task(db, title="Empfängerlos 1")
    create_task(db, title="Empfängerlos 2")
    rows = list_tasks(db, employee_id=emp1.id, unassigned_only=True)
    assert {r["title"] for r in rows} == {"Empfängerlos 1", "Empfängerlos 2"}


# --- list_tasks_for_user(): die eine Sichtbarkeitsregel ---

def test_admin_sees_everything_by_default():
    db = db_session()
    emp1, emp2 = make_employees(db)
    create_task(db, title="Für Erika", assigned_employee_id=emp1.id)
    create_task(db, title="Für Otto", assigned_employee_id=emp2.id)
    create_task(db, title="Empfängerlos")
    admin = make_user(db, "admin", username="admin1")
    rows = list_tasks_for_user(db, admin)
    assert {r["title"] for r in rows} == {"Für Erika", "Für Otto", "Empfängerlos"}


def test_office_without_unassigned_only_sees_only_own_never_colleagues():
    db = db_session()
    emp1, emp2 = make_employees(db)
    create_task(db, title="Für Erika", assigned_employee_id=emp1.id)
    create_task(db, title="Für Otto", assigned_employee_id=emp2.id)
    create_task(db, title="Empfängerlos")
    office = make_user(db, "buero_auftrag", employee_id=emp1.id, username="office1")
    rows = list_tasks_for_user(db, office)
    assert {r["title"] for r in rows} == {"Für Erika"}
    # Auch ein manipulierter employee_id-Parameter wird ignoriert -- das Büro-Konto bleibt
    # zwingend auf die eigene employee_id festgelegt.
    rows_tampered = list_tasks_for_user(db, office, employee_id=emp2.id)
    assert {r["title"] for r in rows_tampered} == {"Für Erika"}


def test_office_sees_unassigned_but_not_colleagues_assigned_tasks():
    db = db_session()
    emp1, emp2 = make_employees(db)
    create_task(db, title="Für Otto", assigned_employee_id=emp2.id)
    create_task(db, title="Offene Büro-Aufgabe 1")
    create_task(db, title="Offene Büro-Aufgabe 2")
    office = make_user(db, "buero_auftrag", employee_id=emp1.id, username="office2")
    rows = list_tasks_for_user(db, office, unassigned_only=True)
    assert {r["title"] for r in rows} == {"Offene Büro-Aufgabe 1", "Offene Büro-Aufgabe 2"}


def test_office_without_employee_link_can_still_see_the_shared_inbox():
    """Sehen der empfängerlosen Aufgaben braucht keine employee_id-Verknüpfung -- nur das
    Übernehmen selbst (claim_task) verlangt sie, siehe unten."""
    db = db_session()
    create_task(db, title="Empfängerlos")
    office = make_user(db, "buero_auftrag", employee_id=None, username="office3")
    rows = list_tasks_for_user(db, office, unassigned_only=True)
    assert {r["title"] for r in rows} == {"Empfängerlos"}


def test_office_without_employee_link_gets_value_error_for_non_unassigned_view():
    db = db_session()
    office = make_user(db, "buero_auftrag", employee_id=None, username="office4")
    with pytest.raises(ValueError):
        list_tasks_for_user(db, office)


def test_field_role_gets_empty_list_never_an_exception():
    db = db_session()
    create_task(db, title="Empfängerlos")
    field = make_user(db, "field", username="field1")
    assert list_tasks_for_user(db, field) == []
    assert list_tasks_for_user(db, field, unassigned_only=True) == []


# --- claim_task() / release_task() ---

def test_claim_assigns_to_own_employee_id_no_third_state():
    db = db_session()
    emp1, _ = make_employees(db)
    t = create_task(db, title="Empfängerlos")
    office = make_user(db, "buero_auftrag", employee_id=emp1.id, username="office5")
    result = claim_task(db, t["id"], office)
    assert result["assigned_employee_id"] == emp1.id


def test_claim_rejects_already_assigned_task():
    db = db_session()
    emp1, emp2 = make_employees(db)
    t = create_task(db, title="Für Otto", assigned_employee_id=emp2.id)
    office = make_user(db, "buero_auftrag", employee_id=emp1.id, username="office6")
    with pytest.raises(ValueError):
        claim_task(db, t["id"], office)


def test_claim_without_employee_link_raises_clear_error_not_silent_failure():
    db = db_session()
    t = create_task(db, title="Empfängerlos")
    office = make_user(db, "buero_auftrag", employee_id=None, username="office7")
    with pytest.raises(ValueError):
        claim_task(db, t["id"], office)


def test_claim_unknown_task_returns_none():
    db = db_session()
    emp1, _ = make_employees(db)
    office = make_user(db, "buero_auftrag", employee_id=emp1.id, username="office8")
    assert claim_task(db, 9999, office) is None


def test_release_clears_assignment_without_ownership_check():
    """Bewusst OHNE Eigentümerschafts-Prüfung -- konsistent mit der bereits bestehenden Lücke
    bei PUT/DELETE/archive (siehe CLAUDE.md "Aufgabe")."""
    db = db_session()
    emp1, _ = make_employees(db)
    t = create_task(db, title="Für Erika", assigned_employee_id=emp1.id)
    result = release_task(db, t["id"])
    assert result["assigned_employee_id"] is None


def test_release_unknown_task_returns_none():
    db = db_session()
    assert release_task(db, 9999) is None


# --- Angriffstest über den echten Router (wie ausdrücklich verlangt) ---

def test_field_cannot_list_unassigned_tasks_via_router(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, _ = make_employees(db)
    create_task(db, title="Empfängerlos")
    client = router_test_client(db, tasks_router.router, role="field", employee_id=emp1.id)
    resp = client.get("/api/tasks?unassigned_only=true")
    assert resp.status_code == 403, resp.text


def test_field_cannot_claim_any_task_via_router_not_even_a_guessed_id(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, _ = make_employees(db)
    real = create_task(db, title="Empfängerlos")
    client = router_test_client(db, tasks_router.router, role="field", employee_id=emp1.id)
    # Sowohl eine echte als auch eine geratene, nicht existierende ID müssen gleich 403
    # liefern -- die Rollenprüfung (_role_dep) muss vor jeder Geschäftslogik greifen, ein 404
    # für die geratene ID wäre bereits ein (kleiner) Informationsleck.
    resp_real = client.post(f"/api/tasks/{real['id']}/claim")
    resp_guessed = client.post("/api/tasks/999999/claim")
    assert resp_real.status_code == 403, resp_real.text
    assert resp_guessed.status_code == 403, resp_guessed.text
    # Die Aufgabe ist danach nachweislich unverändert unangetastet.
    task_after = list_tasks(db, unassigned_only=True)
    assert len(task_after) == 1


def test_field_cannot_release_any_task_via_router_not_even_a_guessed_id(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, emp2 = make_employees(db)
    real = create_task(db, title="Für Otto", assigned_employee_id=emp2.id)
    client = router_test_client(db, tasks_router.router, role="field", employee_id=emp1.id)
    resp_real = client.post(f"/api/tasks/{real['id']}/release")
    resp_guessed = client.post("/api/tasks/999999/release")
    assert resp_real.status_code == 403, resp_real.text
    assert resp_guessed.status_code == 403, resp_guessed.text


def test_office_sees_unassigned_via_router_but_never_colleagues_assigned_task(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, emp2 = make_employees(db)
    create_task(db, title="Für Otto", assigned_employee_id=emp2.id)
    create_task(db, title="Offene Büro-Aufgabe")
    client = router_test_client(db, tasks_router.router, role="buero_auftrag", employee_id=emp1.id)

    default_resp = client.get("/api/tasks")
    assert default_resp.status_code == 200, default_resp.text
    assert [t["title"] for t in default_resp.json()] == []

    unassigned_resp = client.get("/api/tasks?unassigned_only=true")
    assert unassigned_resp.status_code == 200, unassigned_resp.text
    titles = [t["title"] for t in unassigned_resp.json()]
    assert titles == ["Offene Büro-Aufgabe"]
    assert "Für Otto" not in titles


def test_office_can_claim_unassigned_task_via_router_and_then_release_it(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, _ = make_employees(db)
    task = create_task(db, title="Offene Büro-Aufgabe")
    client = router_test_client(db, tasks_router.router, role="buero_auftrag", employee_id=emp1.id)

    claim_resp = client.post(f"/api/tasks/{task['id']}/claim")
    assert claim_resp.status_code == 200, claim_resp.text
    assert claim_resp.json()["assigned_employee_id"] == emp1.id

    # Danach ist sie aus dem gemeinsamen Büro-Eingang verschwunden.
    still_unassigned = client.get("/api/tasks?unassigned_only=true")
    assert still_unassigned.json() == []

    release_resp = client.post(f"/api/tasks/{task['id']}/release")
    assert release_resp.status_code == 200, release_resp.text
    assert release_resp.json()["assigned_employee_id"] is None
    back_in_inbox = client.get("/api/tasks?unassigned_only=true")
    assert [t["title"] for t in back_in_inbox.json()] == ["Offene Büro-Aufgabe"]


def test_office_without_employee_link_gets_clear_403_when_claiming(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    task = create_task(db, title="Offene Büro-Aufgabe")
    client = router_test_client(db, tasks_router.router, role="buero_auftrag", employee_id=None)
    resp = client.post(f"/api/tasks/{task['id']}/claim")
    assert resp.status_code == 400, resp.text
    assert "Mitarbeiter" in resp.json()["detail"]


def test_claiming_an_already_taken_task_via_router_returns_400_not_a_silent_steal(router_test_client, threaded_db_session):
    from app.routers import tasks as tasks_router
    db = threaded_db_session
    emp1, emp2 = make_employees(db)
    task = create_task(db, title="Für Otto", assigned_employee_id=emp2.id)
    client = router_test_client(db, tasks_router.router, role="buero_auftrag", employee_id=emp1.id)
    resp = client.post(f"/api/tasks/{task['id']}/claim")
    assert resp.status_code == 400, resp.text
    reloaded = list_tasks(db, employee_id=emp2.id)
    assert reloaded[0]["assigned_employee_id"] == emp2.id
