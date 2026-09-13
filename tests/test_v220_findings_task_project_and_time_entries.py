"""Version 1.2.21 -- Punkt 1 (Maßnahmen-Zusammenführung + Migrationssperre), Punkt 2 (Vorgang
aus der Aufgabe heraus), Punkt 3 (Zeitbuchung direkt im Bericht)."""

from decimal import Decimal

from sqlalchemy import text

from app.findings import _action_already_executed, create_finding, create_follow_up_project_for_task, get_finding_for_task
from app.models import Employee, Finding, Project, Task
from app.service_reports import create_report
from app.time_tracking import create_manual_entry
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v214_findings_and_photos import _build_extra_order


def _make_order_for_report(db):
    order, _ = make_order_with_item(db)
    return order


# --- Punkt 1: Migration folgeauftrag/angebot_erforderlich -> buero_pruefen ---

def test_migrated_folgeauftrag_finding_stays_locked_despite_missing_follow_up_task_id():
    """Simuliert exakt die Alembic-Migration (reines UPDATE-Statement) gegen einen Finding, der
    unter der alten Maßnahme "folgeauftrag" einen echten Auftrag erzeugt hatte -- er trägt
    follow_up_order_id, aber nie ein follow_up_task_id. _action_already_executed() muss ihn
    trotzdem als bereits ausgeführt behandeln, sonst würde ein erneuter Klick auf "Büro prüfen
    lassen" eine überflüssige zweite Aufgabe erzeugen."""
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = Finding(
        service_report_id=report["id"], description="Alter Folgeauftrag-Mangel", severity="dringend",
        action="folgeauftrag", follow_up_order_id=order.id, follow_up_project_id=order.project_id,
    )
    db.add(finding)
    db.commit()

    db.execute(text("UPDATE findings SET action = 'buero_pruefen' WHERE action IN ('folgeauftrag', 'angebot_erforderlich')"))
    db.commit()

    row = db.get(Finding, finding.id)
    assert row.action == "buero_pruefen"
    assert row.follow_up_task_id is None
    assert row.follow_up_order_id == order.id  # unverändert, wie gefordert
    assert _action_already_executed(row, "buero_pruefen") is True


# --- Punkt 2: Vorgang aus der Aufgabe heraus ---

def test_get_finding_for_task_returns_none_for_unrelated_task():
    db = db_session()
    task = Task(title="Manuelle Aufgabe ohne Mangelbezug")
    db.add(task)
    db.commit()
    assert get_finding_for_task(db, task.id) is None


def test_create_follow_up_project_for_task_creates_order_and_sets_back_references():
    db = db_session()
    # source_quote_id weit weg von 1, da create_follow_up_project_for_task() intern über
    # create_quick_service_order() eine ECHTE, ab 1 autoinkrementierte Quote anlegt (Muster wie
    # in test_v214_findings_and_photos.py::_build_extra_order()).
    order, _customer, _project = _build_extra_order(db, "9101", source_quote_id=9101)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Ziegel gebrochen", "dringend", "buero_pruefen")
    assert finding["follow_up_task_id"] is not None
    assert finding["follow_up_order_id"] is None

    task_id = finding["follow_up_task_id"]
    found = get_finding_for_task(db, task_id)
    assert found["id"] == finding["id"]

    result = create_follow_up_project_for_task(db, task_id)
    assert result["project_id"] is not None
    assert result["order_id"] is not None

    updated = db.get(Finding, finding["id"])
    assert updated.follow_up_project_id == result["project_id"]
    assert updated.follow_up_order_id == result["order_id"]
    assert updated.status == "in_bearbeitung"
    project = db.get(Project, result["project_id"])
    assert "Ziegel gebrochen" in project.description

    # Idempotenzsperre: ein zweiter Versuch für dieselbe Aufgabe lehnt ab.
    try:
        create_follow_up_project_for_task(db, task_id)
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "bereits" in str(exc)


def test_create_follow_up_project_for_task_rejects_task_without_finding():
    db = db_session()
    task = Task(title="Manuelle Aufgabe ohne Mangelbezug")
    db.add(task)
    db.commit()
    try:
        create_follow_up_project_for_task(db, task.id)
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Mangel" in str(exc)


def test_router_endpoints_for_task_finding_and_create_follow_up_project(threaded_db_session, router_test_client):
    from app.routers.findings import router as findings_router

    db = threaded_db_session
    order, _customer, _project = _build_extra_order(db, "9102", source_quote_id=9102)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Dachfenster undicht", "mittel", "buero_pruefen")
    task_id = finding["follow_up_task_id"]
    client = router_test_client(db, findings_router)

    get_resp = client.get(f"/api/tasks/{task_id}/finding")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["id"] == finding["id"]

    post_resp = client.post(f"/api/tasks/{task_id}/create-follow-up-project")
    assert post_resp.status_code == 200, post_resp.text
    assert post_resp.json()["project_id"] is not None

    second_resp = client.post(f"/api/tasks/{task_id}/create-follow-up-project")
    assert second_resp.status_code == 400


# --- Punkt 3: Zeitbuchung (Regressionsbeleg -- create_manual_entry()/POST /api/time-entries
# bleiben durch das kompakte Formular auf service_reports.html unverändert) ---

def test_create_manual_entry_still_works_for_the_compact_report_form():
    """Reiner Regressionsbeleg: das kompakte Zeitformular auf service_reports.html ruft denselben
    Endpunkt (create_manual_entry() über POST /api/time-entries) auf wie time_tracking.html --
    keine Geschäftslogik wurde dafür dupliziert oder verändert."""
    db = db_session()
    order = _make_order_for_report(db)
    employee = Employee(first_name="Max", last_name="Mustermann", employee_group="gewerblich", active=True)
    db.add(employee)
    db.commit()
    entry = create_manual_entry(
        db, employee_id=employee.id, order_id=order.id, work_date=order.order_date,
        hours=Decimal("2.5"), entry_type="site", activity="Wartung",
    )
    assert entry.hours == Decimal("2.5")
    assert entry.order_id == order.id
