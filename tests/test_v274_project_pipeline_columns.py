"""Projekt-Pipeline, Fundament (seit 1.3.70) -- siehe CLAUDE.md "Umbau der Projektliste" für die
volle Herleitung. Deckt ab:

1. Selbst-Seeding der vier Startspalten, unverändert bei erneutem Aufruf (Muster
   app/task_columns.py::ensure_default_columns()).
2. default_pipeline_column_id() liefert die Spalte mit der niedrigsten sort_order --
   die Startspalte neu angelegter Projekte.
3. CRUD + Löschschutz (letzte Spalte, Spalte noch in Verwendung) -- Muster
   app/task_columns.py.
4. Regression an allen vier Project(...)-Konstruktionsstellen: jedes neu angelegte Projekt
   bekommt tatsächlich die Startspalte, nie NULL.
5. Router-Rollenprüfung: `field` bekommt auf jeden Endpunkt 403 (GET wie Mutationen), `office`
   darf lesen, aber nicht schreiben -- nur `admin` darf anlegen/bearbeiten/umsortieren/löschen.

Die eigentliche Migration (da9d9425e257) ist bereits gegen die reale, lokale Datenbank gelaufen
und dabei manuell verifiziert (8 Bestandsprojekte, alle auf die Startspalte "Neu" migriert, 0
NULL-Werte) -- ein weiterer, isolierter Replay-Test der batch_alter_table()-Schema-DDL wird hier
bewusst NICHT gebaut (siehe CLAUDE.md "Testen": SQLite-Batch-Modus braucht eine an echtes
target_metadata gebundene Umgebung, dieselbe Einschränkung wie bei den früheren
Migrationstests). Was hier stattdessen geprüft wird: dass DEFAULT_COLUMNS (das, was die
Migration sät) und die Geschäftslogik (das, was ein frisch erzeugtes Projekt danach zugewiesen
bekommt) übereinstimmen."""

import pytest

from app.models import Customer, Project, ProjectPipelineColumn
from app.project_pipeline_columns import (
    DEFAULT_COLUMNS,
    create_column,
    default_pipeline_column_id,
    delete_column,
    ensure_default_columns,
    list_columns,
    reorder_columns,
    update_column,
)
from app.routers.project_pipeline_columns import router as pipeline_columns_router


def _customer(db):
    customer = Customer(name="Testkunde", last_name="Testkunde")
    db.add(customer)
    db.flush()
    return customer


# --- 1+2: Selbst-Seeding, Startspalte ---

def test_ensure_default_columns_seeds_exactly_the_four_default_columns(db_session):
    ensure_default_columns(db_session)
    rows = list_columns(db_session)
    assert [(r["key"], r["label"]) for r in rows] == [(c["key"], c["label"]) for c in DEFAULT_COLUMNS]


def test_ensure_default_columns_never_touches_an_already_seeded_table(db_session):
    ensure_default_columns(db_session)
    only = db_session.query(ProjectPipelineColumn).filter_by(key="neu").one()
    only.label = "Umbenannt"
    db_session.commit()
    ensure_default_columns(db_session)
    assert db_session.query(ProjectPipelineColumn).filter_by(key="neu").one().label == "Umbenannt"
    assert db_session.query(ProjectPipelineColumn).count() == 4


def test_default_pipeline_column_id_is_the_lowest_sort_order_column(db_session):
    ensure_default_columns(db_session)
    first = db_session.query(ProjectPipelineColumn).order_by(ProjectPipelineColumn.sort_order).first()
    assert default_pipeline_column_id(db_session) == first.id
    assert first.key == "neu"


def test_default_pipeline_column_id_self_seeds_on_a_completely_empty_table(db_session):
    assert db_session.query(ProjectPipelineColumn).count() == 0
    column_id = default_pipeline_column_id(db_session)
    assert db_session.query(ProjectPipelineColumn).count() == 4
    assert db_session.get(ProjectPipelineColumn, column_id).key == "neu"


# --- 3: CRUD + Löschschutz ---

def test_create_column_generates_a_unique_slug_key_and_appends_after_the_highest_sort_order(db_session):
    ensure_default_columns(db_session)
    created = create_column(db_session, "  Warten auf Material  ")
    assert created["key"] == "warten_auf_material"
    assert created["label"] == "Warten auf Material"
    assert created["sort_order"] == 40  # nach "Abgeschlossen" (30)


def test_create_column_rejects_empty_label(db_session):
    with pytest.raises(ValueError):
        create_column(db_session, "   ")


def test_create_column_disambiguates_a_colliding_slug(db_session):
    ensure_default_columns(db_session)
    a = create_column(db_session, "Neu!")  # slugifiziert ebenfalls zu "neu"
    assert a["key"] == "neu_2"


def test_update_column_renames_label_but_never_the_key(db_session):
    ensure_default_columns(db_session)
    col = db_session.query(ProjectPipelineColumn).filter_by(key="wartet").one()
    updated = update_column(db_session, col.id, label="Zurückgestellt")
    assert updated["label"] == "Zurückgestellt"
    assert updated["key"] == "wartet"


def test_update_column_unknown_id_raises(db_session):
    ensure_default_columns(db_session)
    with pytest.raises(ValueError):
        update_column(db_session, 999999, label="X")


def test_reorder_columns_requires_the_full_set_of_ids(db_session):
    ensure_default_columns(db_session)
    ids = [c["id"] for c in list_columns(db_session)]
    with pytest.raises(ValueError):
        reorder_columns(db_session, ids[:-1])


def test_reorder_columns_applies_the_new_order(db_session):
    ensure_default_columns(db_session)
    ids = [c["id"] for c in list_columns(db_session)]
    reversed_ids = list(reversed(ids))
    result = reorder_columns(db_session, reversed_ids)
    assert [c["id"] for c in result] == reversed_ids


def test_delete_column_refuses_the_last_remaining_column(db_session):
    ensure_default_columns(db_session)
    ids = [c["id"] for c in list_columns(db_session)]
    for column_id in ids[:-1]:
        delete_column(db_session, column_id)
    with pytest.raises(ValueError, match="letzte"):
        delete_column(db_session, ids[-1])


def test_delete_column_refuses_a_column_still_used_by_a_project(db_session):
    ensure_default_columns(db_session)
    col = db_session.query(ProjectPipelineColumn).filter_by(key="wartet").one()
    customer = _customer(db_session)
    project = Project(project_number="P-TEST-0001", name="Testprojekt", customer_id=customer.id, pipeline_column_id=col.id)
    db_session.add(project)
    db_session.commit()
    with pytest.raises(ValueError, match="Projekt"):
        delete_column(db_session, col.id)


def test_delete_column_succeeds_once_no_project_uses_it_anymore(db_session):
    ensure_default_columns(db_session)
    col = db_session.query(ProjectPipelineColumn).filter_by(key="wartet").one()
    delete_column(db_session, col.id)
    assert db_session.get(ProjectPipelineColumn, col.id) is None


# --- 4: Regression an allen vier Project(...)-Konstruktionsstellen ---

def test_duplicate_project_assigns_the_default_pipeline_column(db_session):
    from app.projects import duplicate_project

    db = db_session
    customer = _customer(db)
    start_col = default_pipeline_column_id(db)
    other_col = create_column(db, "Andere Spalte")
    source = Project(
        project_number="P-SRC-0001", name="Quelle", customer_id=customer.id,
        pipeline_column_id=other_col["id"],
    )
    db.add(source)
    db.commit()

    copy = duplicate_project(db, source, as_template=False)
    assert copy.pipeline_column_id == start_col, "eine Kopie startet neu in der ersten Spalte, nicht in der der Quelle"


def test_quick_service_order_assigns_the_default_pipeline_column(db_session):
    from app.quick_service_orders import create_quick_service_order

    db = db_session
    customer = _customer(db)
    start_col = default_pipeline_column_id(db)
    result = create_quick_service_order(
        db, customer_id=customer.id, property_id=None, order_type="reparatur", title="Testreparatur",
    )
    project = db.get(Project, result["project_id"])
    assert project.pipeline_column_id == start_col


def test_convert_inquiry_assigns_the_default_pipeline_column(threaded_db_session, router_test_client):
    from app.inquiries import next_inquiry_number
    from app.models import Inquiry
    from app.routers.inquiries import router as inquiries_router

    db = threaded_db_session
    customer = _customer(db)
    start_col = default_pipeline_column_id(db)
    inquiry = Inquiry(inquiry_number=next_inquiry_number(db), customer_id=customer.id, title="Testanfrage", status="neu")
    db.add(inquiry)
    db.commit()

    client = router_test_client(db, inquiries_router)
    resp = client.post(f"/api/inquiries/{inquiry.id}/convert", json={"create_quote": False})
    assert resp.status_code == 200
    project_id = resp.json()["project"]["id"]
    assert db.get(Project, project_id).pipeline_column_id == start_col


def test_create_project_endpoint_assigns_the_default_pipeline_column(threaded_db_session, router_test_client):
    from app.routers.projects import router as projects_router

    db = threaded_db_session
    customer = _customer(db)
    start_col = default_pipeline_column_id(db)

    client = router_test_client(db, projects_router)
    resp = client.post("/api/projects", json={"customer_id": customer.id, "name": "Neues Projekt"})
    assert resp.status_code == 200
    project_id = resp.json()["id"]
    assert db.get(Project, project_id).pipeline_column_id == start_col


# --- 5: Router-Rollenprüfung ---

def test_field_gets_403_on_every_endpoint(threaded_db_session, router_test_client):
    db = threaded_db_session
    ensure_default_columns(db)
    column_id = list_columns(db)[0]["id"]
    client = router_test_client(db, pipeline_columns_router, role="field", employee_id=1)
    assert client.get("/api/project-pipeline-columns").status_code == 403
    assert client.post("/api/project-pipeline-columns", json={"label": "X"}).status_code == 403
    assert client.put(f"/api/project-pipeline-columns/{column_id}", json={"label": "X"}).status_code == 403
    assert client.put("/api/project-pipeline-columns/reorder", json={"ordered_ids": [column_id]}).status_code == 403
    assert client.delete(f"/api/project-pipeline-columns/{column_id}").status_code == 403


def test_office_can_read_but_not_mutate(threaded_db_session, router_test_client):
    db = threaded_db_session
    ensure_default_columns(db)
    column_id = list_columns(db)[0]["id"]
    client = router_test_client(db, pipeline_columns_router, role="buero_auftrag")
    assert client.get("/api/project-pipeline-columns").status_code == 200
    assert client.post("/api/project-pipeline-columns", json={"label": "X"}).status_code == 403
    assert client.put(f"/api/project-pipeline-columns/{column_id}", json={"label": "X"}).status_code == 403
    assert client.delete(f"/api/project-pipeline-columns/{column_id}").status_code == 403


def test_admin_can_read_and_mutate(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, pipeline_columns_router, role="admin")
    assert client.get("/api/project-pipeline-columns").status_code == 200
    created = client.post("/api/project-pipeline-columns", json={"label": "Neue Spalte"})
    assert created.status_code == 200
    column_id = created.json()["id"]
    assert client.put(f"/api/project-pipeline-columns/{column_id}", json={"label": "Umbenannt"}).status_code == 200
    ids = [c["id"] for c in client.get("/api/project-pipeline-columns").json()]
    assert client.put("/api/project-pipeline-columns/reorder", json={"ordered_ids": list(reversed(ids))}).status_code == 200
    assert client.delete(f"/api/project-pipeline-columns/{column_id}").status_code == 200
