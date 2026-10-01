"""Version 1.8.28 -- Mangel zur Aufgabe und "Vorgang erstellen" prüfen die Aufgaben-Sichtbarkeit.

Nebenbefund aus 1.8.26: GET /api/tasks/{id}/finding und POST /api/tasks/{id}/create-follow-up-project
(app/routers/findings.py) prüften nur die Rolle (buero_auftrag aufwärts). Wer die ID der Aufgabe eines
Kollegen oder einer Finanz-Aufgabe errät, las den Mangel dazu und legte daraus den Vorgang an. Jetzt
prüfen beide dieselbe Regel wie GET /api/tasks (task_visible_for_user(), über _require_visible_task()).

1. Matrix: für vier Konten ist die Menge der lesbaren Aufgaben gleich der Menge, deren Mangel lesbar ist,
   und gleich der Menge, aus der sich ein Vorgang erstellen lässt.
2. Angriffstest: buero_auftrag gegen die Aufgabe des Kollegen und eine Finanz-Aufgabe -- 403 ohne
   Mangeltext, kein Vorgang entsteht, der Mangel bleibt unverändert."""

import pytest
from sqlalchemy import func, select

from app.findings import create_finding
from app.models import Finding, Order, Project, Task
from app.routers import findings as findings_router
from app.routers import tasks as tasks_router
from app.service_reports import create_report
from tests.test_v214_findings_and_photos import _build_extra_order
from tests.test_v279_task_visibility import make_employees

GEHEIM = "Attika-Blech lose, Kunde will Kostenvoranschlag"


@pytest.fixture
def welt(threaded_db_session):
    db = threaded_db_session
    erika, otto = make_employees(db)       # Erika ist "ich", Otto der Kollege
    order, _kunde, _projekt = _build_extra_order(db, "9331", source_quote_id=9331)
    report = create_report(db, order.id, "rapport")
    zuordnung = {
        "eingang": (None, None),
        "meine": (erika.id, None),
        "kollege": (otto.id, None),
        "eingang_finanzen": (None, "buero_finanzen"),
    }
    aufgaben, maengel = {}, {}
    for key, (mitarbeiter, mindestrolle) in zuordnung.items():
        mangel = create_finding(db, report["id"], f"{GEHEIM} ({key})", "dringend", "buero_pruefen")
        task = db.get(Task, mangel["follow_up_task_id"])
        task.assigned_employee_id, task.min_visible_role = mitarbeiter, mindestrolle
        aufgaben[key], maengel[key] = task.id, mangel["id"]
    db.commit()
    return {"db": db, "erika": erika.id, "aufgaben": aufgaben, "maengel": maengel}


KONTEN = [("admin", True), ("buero_finanzen", True), ("buero_auftrag", True), ("buero_auftrag", False)]


def _client(router_test_client, welt, rolle, mit_mitarbeiter):
    return router_test_client(welt["db"], tasks_router.router, findings_router.router, role=rolle,
                              employee_id=welt["erika"] if mit_mitarbeiter else None)


def _lesbar(client) -> set[int]:
    ids = {t["id"] for t in client.get("/api/tasks?unassigned_only=true&include_archived=true").json()}
    eigene = client.get("/api/tasks?include_archived=true")
    if eigene.status_code == 200:
        ids |= {t["id"] for t in eigene.json()}
    return ids


def _anzahl_projekte(db) -> int:
    return db.scalar(select(func.count(Project.id)))


@pytest.mark.parametrize("rolle,mit_mitarbeiter", KONTEN)
def test_lesbar_gleich_mangel_lesbar_gleich_vorgang_erstellbar(router_test_client, welt, rolle, mit_mitarbeiter):
    client = _client(router_test_client, welt, rolle, mit_mitarbeiter)
    lesbar = _lesbar(client)
    mangel_lesbar = {tid for tid in welt["aufgaben"].values()
                     if client.get(f"/api/tasks/{tid}/finding").status_code == 200}
    vorgang = {tid for tid in welt["aufgaben"].values()
               if client.post(f"/api/tasks/{tid}/create-follow-up-project").status_code == 200}
    assert lesbar == mangel_lesbar == vorgang
    erwartet = {
        ("admin", True): set(welt["aufgaben"]),
        ("buero_finanzen", True): {"eingang", "meine", "eingang_finanzen"},
        ("buero_auftrag", True): {"eingang", "meine"},
        ("buero_auftrag", False): {"eingang"},
    }[(rolle, mit_mitarbeiter)]
    assert lesbar == {welt["aufgaben"][k] for k in erwartet}


@pytest.mark.parametrize("ziel", ["kollege", "eingang_finanzen"])
def test_angriff_buero_auftrag_per_geratener_aufgaben_id(router_test_client, welt, ziel):
    db, tid, fid = welt["db"], welt["aufgaben"][ziel], welt["maengel"][ziel]
    client = _client(router_test_client, welt, "buero_auftrag", True)
    projekte_vorher = _anzahl_projekte(db)

    lesen = client.get(f"/api/tasks/{tid}/finding")
    assert lesen.status_code == 403, lesen.text
    assert "Attika" not in lesen.text

    anlegen = client.post(f"/api/tasks/{tid}/create-follow-up-project")
    assert anlegen.status_code == 403, anlegen.text
    assert "Attika" not in anlegen.text

    db.expire_all()
    mangel = db.get(Finding, fid)
    assert (mangel.follow_up_order_id, mangel.follow_up_project_id) == (None, None)
    assert _anzahl_projekte(db) == projekte_vorher


def test_unbekannte_aufgabe_ist_404(router_test_client, welt):
    client = _client(router_test_client, welt, "buero_auftrag", True)
    assert client.get("/api/tasks/999999/finding").status_code == 404
    assert client.post("/api/tasks/999999/create-follow-up-project").status_code == 404


def test_berechtigte_erstellen_weiterhin_den_vorgang(router_test_client, welt):
    db = welt["db"]
    client = _client(router_test_client, welt, "buero_auftrag", True)
    tid, fid = welt["aufgaben"]["meine"], welt["maengel"]["meine"]
    assert client.get(f"/api/tasks/{tid}/finding").json()["id"] == fid
    ergebnis = client.post(f"/api/tasks/{tid}/create-follow-up-project").json()
    db.expire_all()
    assert db.get(Finding, fid).follow_up_order_id == ergebnis["order_id"]
    assert db.get(Order, ergebnis["order_id"]) is not None
