"""Version 1.8.71 -- Spaltenschlüssel von Aufgaben und Pipeline gekürzt und eindeutig (Befund „Vor dem Echtbetrieb: Geld und
Sicherheit“ Punkt 5, docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.71").

Muster (app/spaltenlaenge.py): ein abgeleiteter Wert wird dort gekürzt, wo er entsteht, gegen die kürzeste Spalte, in die er
geschrieben wird -- Länge aus dem Modell. Der Schlüssel einer Aufgabenspalte steht in TaskColumn.key (40) und Task.status (30),
der einer Pipelinespalte nur in ProjectPipelineColumn.key (40; Projekte verweisen über die ID). Die Abnahmetests 5a-5c (gegen
PostgreSQL) stehen in tests/test_v372_befund_spaltenschluessel.py."""

import pytest
from sqlalchemy import select

from app import project_pipeline_columns, task_columns
from app.models import ProjectPipelineColumn, Task, TaskColumn
from app.routers.project_pipeline_columns import router as pipeline_router
from app.routers.task_columns import router as task_columns_router
from app.spaltenlaenge import eindeutig_gekuerzt, laenge
from app.tasks import create_task
from tests.befund_vor_echtbetrieb import pg_sitzung
from tests.test_v133_invoices import db_session

LABEL_80 = "Wartet auf Rückmeldung des Auftraggebers, der Hausverwaltung und des Architekten"  # höchstens 80 erlaubt


def test_label_is_the_longest_allowed():
    from app.schemas import ProjectPipelineColumnCreate, TaskColumnCreate

    assert len(LABEL_80) == 80
    TaskColumnCreate(label=LABEL_80)
    ProjectPipelineColumnCreate(label=LABEL_80)


def test_length_comes_from_the_model():
    assert laenge(TaskColumn.key, Task.status) == 30
    assert laenge(Task.status, TaskColumn.key) == 30
    assert laenge(ProjectPipelineColumn.key) == 40


def test_length_follows_a_changed_model(monkeypatch):
    """Wird eine Spalte im Modell kürzer, folgt die Kürzung ohne Codeänderung."""
    monkeypatch.setattr(Task.__table__.c.status.type, "length", 12)
    db = db_session()
    spalte = task_columns.create_column(db, LABEL_80)
    assert spalte["key"] == "wartet_auf_r"
    assert create_task(db, "Rückruf", status=spalte["key"])["status"] == "wartet_auf_r"


@pytest.mark.parametrize("basis,belegt,erwartet", [
    ("kurz", set(), "kurz"),
    ("abcdefghij", set(), "abcde"),
    ("abcd_fghij", set(), "abcd"),                       # kein "_" am Ende
    ("abcdefghij", {"abcde"}, "abc_2"),                  # Anhang passt mit hinein
    ("abc", {"abc", "abc_2"}, "abc_3"),
    ("abcdefghij", {"abcde", *(f"abc_{n}" for n in range(2, 10))}, "ab_10"),  # zweistelliger Anhang kürzt weiter
])
def test_unique_and_shortened(basis, belegt, erwartet):
    assert eindeutig_gekuerzt(basis, 5, belegt.__contains__) == erwartet


def test_same_long_label_many_times_stays_unique_and_fits():
    db = db_session()
    aufgaben = [task_columns.create_column(db, LABEL_80)["key"] for _ in range(12)]
    pipeline = [project_pipeline_columns.create_column(db, LABEL_80)["key"] for _ in range(12)]
    assert len(set(aufgaben)) == 12 and all(len(k) <= 30 for k in aufgaben)
    assert len(set(pipeline)) == 12 and all(len(k) <= 40 for k in pipeline)
    assert aufgaben[:3] == ["wartet_auf_r_ckmeldung_des_auf", "wartet_auf_r_ckmeldung_des_a_2",
                            "wartet_auf_r_ckmeldung_des_a_3"]
    assert aufgaben[-1] == "wartet_auf_r_ckmeldung_des_12"  # zweistelliger Anhang, "_" am Ende der Kürzung fällt weg
    for key in aufgaben:
        assert create_task(db, "Rückruf", status=key)["status"] == key


def test_admin_route_creates_columns_with_the_longest_label(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, task_columns_router, pipeline_router)
    r = client.post("/api/task-columns", json={"label": LABEL_80})
    assert r.status_code == 200, r.text
    assert r.json()["key"] == "wartet_auf_r_ckmeldung_des_auf" and r.json()["label"] == LABEL_80
    r = client.post("/api/project-pipeline-columns", json={"label": LABEL_80})
    assert r.status_code == 200, r.text
    assert r.json()["key"] == "wartet_auf_r_ckmeldung_des_auftraggebers"


@pytest.fixture
def pg():
    with pg_sitzung("spaltenlaenge") as db:
        yield db


def test_postgresql_many_long_labels_and_a_task_in_each(pg):
    """PostgreSQL lehnt einen zu langen Wert ab -- hier entsteht jede Spalte, und in jede kommt eine Aufgabe, auch als
    vorderste Spalte über den Standard (wie die Aufgaben eines Mangels oder einer Folge)."""
    keys = [task_columns.create_column(pg, LABEL_80)["key"] for _ in range(11)]
    for key in keys:
        assert create_task(pg, "Rückruf", status=key)["status"] == key
    ids = [c.id for c in pg.scalars(select(TaskColumn).order_by(TaskColumn.sort_order, TaskColumn.id))]
    task_columns.reorder_columns(pg, ids[-1:] + ids[:-1])
    assert create_task(pg, "Mangel beseitigen")["status"] == keys[-1]
    assert all(len(project_pipeline_columns.create_column(pg, LABEL_80)["key"]) <= 40 for _ in range(11))
