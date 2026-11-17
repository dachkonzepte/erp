"""Version 1.9.346 -- E7 und E8 (Runde ab 1.9.346, Punkt 2; Entscheidung Tobias 17.11.2026: je B, 409 mit Grund und Rat).

E7: eine Aufgabe, auf die ein Befund („Büro prüfen lassen“) oder eine Regel einer Checkliste zeigt, wird von Hand nicht gelöscht -- 409 mit dem Rat, sie
zu erledigen oder zu archivieren. E8: ein Projekt ohne Auftrag, an dem eine Aufgabe hängt, wird nicht gelöscht -- 409 mit dem Rat, es zu archivieren
oder zuerst die Aufgaben zu löschen (Rückfrage 17.11.2026: „absagen“ gibt es nicht, der Rat heißt „archivieren“). Bis 1.9.345 scheiterten beide am
Fremdschlüssel (live 500, in der Suite seit 1.9.339 `FOREIGN KEY constraint failed`) -- die Fälle mit Verweis unten waren vorher rot."""

from sqlalchemy import func, select

from app.database import Base
from app.findings import create_finding
from app.models import AuditLog, ChecklistRuleExecution, Finding, Project, Task
from app.routers.projects import router as projekte_router
from app.routers.tasks import router as aufgaben_router
from app.service_reports import create_report
from app.tasks import MIT_DER_AUFGABE, VERWEISE_AUF_AUFGABEN, create_task
from tests.test_v192_project_templates import make_full_project
from tests.test_v214_findings_and_photos import _build_extra_order
from tests.test_v305_checklist_filling import _client, world  # noqa: F401 -- Fixture
from tests.test_v307_checklist_rules import _start_filled, rules  # noqa: F401 -- Fixture

RAT_AUFGABE = "deshalb lässt sie sich nicht löschen. Erledige oder archiviere sie stattdessen."
RAT_PROJEKT = "deshalb lässt es sich nicht löschen. Archiviere das Projekt stattdessen oder lösche zuerst seine Aufgaben."


def _geloescht(db):
    return db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "Aufgabe", AuditLog.action == "gelöscht"))


# --- E7 -------------------------------------------------------------------------------------------------------------------------------------------

def test_folgeaufgabe_eines_befunds_nicht_von_hand_loeschen(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _customer, _project = _build_extra_order(db, "9601")
    report = create_report(db, order.id, "rapport", description="Arbeiten laut Testfall")
    finding = create_finding(db, report["id"], "Riss in der Attika", "mittel", "buero_pruefen")
    r = router_test_client(db, aufgaben_router).delete(f"/api/tasks/{finding['follow_up_task_id']}")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Die Aufgabe gehört zu einem Befund im Einsatzbericht – {RAT_AUFGABE}"
    db.expire_all()
    assert db.get(Task, finding["follow_up_task_id"]) is not None
    assert db.get(Finding, finding["id"]).follow_up_task_id == finding["follow_up_task_id"]
    assert _geloescht(db) == 0


def test_aufgabe_einer_checklisten_regel_nicht_von_hand_loeschen(rules, router_test_client):
    db = rules["db"]
    c = _start_filled(rules, _client(rules, router_test_client, "a"))
    assert _client(rules, router_test_client, "a").post(f"/api/checklists/{c['id']}/complete").status_code == 200
    task_id = db.scalar(select(ChecklistRuleExecution.task_id).where(ChecklistRuleExecution.task_id.is_not(None)).limit(1))
    r = router_test_client(db, aufgaben_router).delete(f"/api/tasks/{task_id}")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Die Aufgabe gehört zu einer Regel einer Checkliste – {RAT_AUFGABE}"
    db.expire_all()
    assert db.get(Task, task_id) is not None


def test_aufgabe_ohne_verweis_geht_wie_bisher(threaded_db_session, router_test_client):
    db = threaded_db_session
    tid = create_task(db, "Rückruf Kunde")["id"]
    assert router_test_client(db, aufgaben_router).delete(f"/api/tasks/{tid}").status_code == 200
    assert db.get(Task, tid) is None and _geloescht(db) == 1


def test_jeder_fremdschluessel_auf_aufgaben_ist_eingeordnet():
    alle = {(t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns for fk in c.foreign_keys if fk.column.table.name == "tasks"}
    eingeordnet = set(MIT_DER_AUFGABE) | set(VERWEISE_AUF_AUFGABEN)
    assert alle == eingeordnet, f"nicht eingeordnet: {sorted(alle - eingeordnet)}; veraltet: {sorted(eingeordnet - alle)}"


# --- E8 -------------------------------------------------------------------------------------------------------------------------------------------

def test_projekt_mit_aufgabe_nicht_loeschen(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = make_full_project(db)
    db.add(Task(title="Rückruf Kunde", project_id=project.id))
    db.commit()
    client = router_test_client(db, projekte_router)
    r = client.delete(f"/api/projects/{project.id}")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Am Projekt hängt noch 1 Aufgabe – {RAT_PROJEKT}"
    db.add(Task(title="Angebot nachfassen", project_id=project.id))
    db.commit()
    assert client.delete(f"/api/projects/{project.id}").json()["detail"] == f"Am Projekt hängen noch 2 Aufgaben – {RAT_PROJEKT}"
    db.expire_all()
    assert db.get(Project, project.id) is not None
    assert db.scalar(select(func.count()).select_from(Task).where(Task.project_id == project.id)) == 2


def test_projekt_ohne_aufgabe_geht_wie_bisher(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = make_full_project(db)
    assert router_test_client(db, projekte_router).delete(f"/api/projects/{project.id}").status_code == 200
    assert db.get(Project, project.id) is None


# Was delete_project() mit jedem Fremdschlüssel auf projects tut. OFFEN: scheitert heute am Fremdschlüssel (live 500), nicht entschieden -- darf nur
# kürzer werden (Funde 17.11.2026, Bericht der Runde ab 1.9.346).
PROJEKT_FREMDSCHLUESSEL = {
    ("project_profiles", "project_id"): "geht mit (Kaskade)",
    ("project_documents", "project_id"): "geht mit (Kaskade)",
    ("quotes", "project_id"): "geht mit (Kaskade, Zusatztabellen vorher)",
    ("project_participants", "project_id"): "geht mit (delete_participants_of_project)",
    ("inquiries", "project_id"): "gelöst (Beziehung source_inquiry)",
    ("calendar_events", "project_id"): "gelöst (unlink_calendar_events_for_project)",
    ("orders", "project_id"): "sperrt (400, nur archivieren)",
    ("tasks", "project_id"): "sperrt (409, E8)",
    ("time_entries", "project_id"): "nur mit Auftrag -- sperrt über orders",
    ("time_entry_groups", "project_id"): "nur mit Auftrag -- sperrt über orders",
    ("findings", "follow_up_project_id"): "Vorgang aus einem Befund hat einen Auftrag -- sperrt über orders",
}
OFFEN = {
    ("maintenance_contracts", "template_project_id"): "Vorlage eines Wartungsvertrags",
    ("maintenance_contract_items", "template_project_id"): "Vorlage einer Position eines Wartungsvertrags",
    ("incoming_invoices", "project_id"): "Eingangsrechnung am Projekt",
}


def test_jeder_fremdschluessel_auf_projekte_ist_eingeordnet():
    alle = {(t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns for fk in c.foreign_keys if fk.column.table.name == "projects"}
    eingeordnet = set(PROJEKT_FREMDSCHLUESSEL) | set(OFFEN)
    assert not set(PROJEKT_FREMDSCHLUESSEL) & set(OFFEN)
    assert alle == eingeordnet, f"nicht eingeordnet: {sorted(alle - eingeordnet)}; veraltet: {sorted(eingeordnet - alle)}"
