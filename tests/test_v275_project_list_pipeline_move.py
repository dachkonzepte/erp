"""Projekt-Pipeline, "Runde 2" (seit 1.3.72) -- siehe CLAUDE.md "Umbau der Projektliste" für die
volle Herleitung. Deckt den neuen Endpunkt zum Verschieben eines Projekts im Kanban ab, sowie
dass die Projektlisten-Schemas jetzt pipeline_column_id mitliefern (Voraussetzung dafür, dass
die Kanban-Ansicht Karten überhaupt gruppieren kann):

1. `pipeline_column_id` steht in jeder GET-/POST-Antwort, die ProjectListOut/ProjectDetailOut
   nutzt (Liste, Mustervorgangsliste, Anlegen, Detail) -- an allen vier Stellen, die das Schema
   manuell befüllen (routers/projects.py x3, routers/inquiries.py x1).
2. `PUT /api/projects/{id}/pipeline-column` ändert ausschließlich die Spalte, nie Project.status
   -- Regressionstest genau für die im Round-1-Fundament vereinbarte Absicherung.
3. Validierung: unbekanntes Projekt -> 404, unbekannte Spalte -> 404.
4. Rollenprüfung: `field` bekommt 403 (Projekte sind vollständig gesperrt), `office`/`admin`
   dürfen verschieben (kein admin-only-Sonderfall wie bei den Spalten-Stammdaten selbst -- das
   Verschieben eines Projekts ist Tagesgeschäft, nicht Konfiguration).
"""

from app.models import Customer, Project
from app.project_pipeline_columns import create_column, default_pipeline_column_id, list_columns
from app.routers.projects import router as projects_router


def _customer(db):
    customer = Customer(name="Testkunde", last_name="Testkunde")
    db.add(customer)
    db.flush()
    return customer


def _project(db, *, status="anfrage"):
    customer = _customer(db)
    project = Project(
        project_number="P-MOVE-0001", name="Testprojekt", customer_id=customer.id,
        status=status, pipeline_column_id=default_pipeline_column_id(db),
    )
    db.add(project)
    db.flush()
    return project


# --- 1: pipeline_column_id in jeder ProjectListOut/ProjectDetailOut-Antwort ---

def test_list_projects_includes_pipeline_column_id(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = _project(db)
    db.commit()
    client = router_test_client(db, projects_router, role="office")
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert body and body[0]["id"] == project.id
    assert body[0]["pipeline_column_id"] == project.pipeline_column_id


def test_create_project_response_includes_pipeline_column_id(threaded_db_session, router_test_client):
    db = threaded_db_session
    customer = _customer(db)
    db.commit()
    client = router_test_client(db, projects_router, role="office")
    resp = client.post("/api/projects", json={"customer_id": customer.id, "name": "Neu"})
    assert resp.status_code == 200
    assert resp.json()["pipeline_column_id"] == default_pipeline_column_id(db)


def test_project_detail_response_includes_pipeline_column_id(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = _project(db)
    db.commit()
    client = router_test_client(db, projects_router, role="office")
    resp = client.get(f"/api/projects/{project.id}")
    assert resp.status_code == 200
    assert resp.json()["pipeline_column_id"] == project.pipeline_column_id


# --- 2+3: das eigentliche Verschieben ---

def test_move_pipeline_column_changes_only_the_column_never_status(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = _project(db, status="in_arbeit")
    target = create_column(db, "Wartet auf Rückmeldung")
    db.commit()
    original_status = project.status

    client = router_test_client(db, projects_router, role="office")
    resp = client.put(f"/api/projects/{project.id}/pipeline-column", json={"pipeline_column_id": target["id"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["pipeline_column_id"] == target["id"]
    assert body["status"] == original_status

    db.refresh(project)
    assert project.pipeline_column_id == target["id"]
    assert project.status == original_status


def test_move_pipeline_column_unknown_project_is_404(threaded_db_session, router_test_client):
    db = threaded_db_session
    column_id = list_columns(db)[0]["id"]
    db.commit()
    client = router_test_client(db, projects_router, role="office")
    resp = client.put("/api/projects/999999/pipeline-column", json={"pipeline_column_id": column_id})
    assert resp.status_code == 404


def test_move_pipeline_column_unknown_column_is_404(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = _project(db)
    db.commit()
    client = router_test_client(db, projects_router, role="office")
    resp = client.put(f"/api/projects/{project.id}/pipeline-column", json={"pipeline_column_id": 999999})
    assert resp.status_code == 404
    db.refresh(project)
    assert project.pipeline_column_id != 999999


# --- 4: Rollenprüfung ---

def test_field_cannot_move_projects_between_pipeline_columns(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = _project(db)
    column_id = list_columns(db)[0]["id"]
    db.commit()
    client = router_test_client(db, projects_router, role="field", employee_id=1)
    resp = client.put(f"/api/projects/{project.id}/pipeline-column", json={"pipeline_column_id": column_id})
    assert resp.status_code == 403


def test_admin_can_move_projects_between_pipeline_columns(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = _project(db)
    target = create_column(db, "Abgeschlossen (Test)")
    db.commit()
    client = router_test_client(db, projects_router, role="admin")
    resp = client.put(f"/api/projects/{project.id}/pipeline-column", json={"pipeline_column_id": target["id"]})
    assert resp.status_code == 200
    assert resp.json()["pipeline_column_id"] == target["id"]
