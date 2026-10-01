"""Version 1.8.26 -- Aufgaben: Ändern prüft dieselbe Sichtbarkeit wie Lesen.

Bis 1.8.25 prüften PUT/DELETE/archive/unarchive/release auf /api/tasks/{id} nur die Rolle
(buero_auftrag aufwärts), nicht die Sichtbarkeit: wer die ID einer Finanz-Aufgabe (min_visible_role
buero_finanzen) oder der persönlichen Aufgabe eines Kollegen errät, konnte sie als buero_auftrag
ändern, löschen, archivieren oder in den Büro-Eingang zurücklegen -- und bekam beim Ändern den Titel
zurück. Über "Bearbeiten" ließ sich außerdem die Sichtbarkeitsgrenze selbst ändern.

Jetzt:
1. task_visible_for_user() (app/tasks.py) ist die eine Regel; list_tasks_for_user() (Lesen) und
   jeder Einzel-Endpunkt (Ändern) nutzen sie. Der Test beweist das über eine Matrix: für jede
   Rolle ist die Menge der lesbaren Aufgaben-IDs gleich der Menge der änderbaren.
2. Angriffstest: buero_auftrag ändert eine Finanz-Aufgabe per ID -- jeder Einzel-Endpunkt antwortet
   403 ohne Titel, die Aufgabe bleibt unverändert.
3. min_visible_role ist über PUT nicht änderbar (422, auch nicht für Admin)."""

import pytest

from app.models import AppUser, Task
from app.routers import tasks as tasks_router
from app.tasks import create_task, task_visible_for_user
from tests.test_v279_task_visibility import make_employees

TITEL = "Skonto Lieferant Dachbaustoffe Nord ziehen"


@pytest.fixture
def welt(threaded_db_session):
    db = threaded_db_session
    erika, otto = make_employees(db)       # Erika ist "ich", Otto der Kollege
    aufgaben = {
        "eingang": create_task(db, title="Eingang offen"),
        "eingang_finanzen": create_task(db, title=TITEL, min_visible_role="buero_finanzen"),
        "eingang_admin": create_task(db, title="Nur Admin", min_visible_role="admin"),
        "meine": create_task(db, title="Meine", assigned_employee_id=erika.id),
        "kollege": create_task(db, title="Ottos persönliche", assigned_employee_id=otto.id),
        "kollege_finanzen": create_task(db, title="Ottos Finanz", assigned_employee_id=otto.id,
                                        min_visible_role="buero_finanzen"),
    }
    return {"db": db, "erika": erika.id, "aufgaben": {k: v["id"] for k, v in aufgaben.items()}}


KONTEN = [("admin", True), ("buero_finanzen", True), ("buero_auftrag", True), ("buero_auftrag", False)]


def _client(router_test_client, welt, rolle, mit_mitarbeiter):
    return router_test_client(welt["db"], tasks_router.router, role=rolle,
                              employee_id=welt["erika"] if mit_mitarbeiter else None)


def _lesbar(client) -> set[int]:
    ids = {t["id"] for t in client.get("/api/tasks?unassigned_only=true&include_archived=true").json()}
    eigene = client.get("/api/tasks?include_archived=true")
    if eigene.status_code == 200:
        ids |= {t["id"] for t in eigene.json()}
    return ids


@pytest.mark.parametrize("rolle,mit_mitarbeiter", KONTEN)
def test_lesbar_gleich_aenderbar(router_test_client, welt, rolle, mit_mitarbeiter):
    client = _client(router_test_client, welt, rolle, mit_mitarbeiter)
    lesbar = _lesbar(client)
    aenderbar = {tid for tid in welt["aufgaben"].values()
                 if client.put(f"/api/tasks/{tid}", json={"priority": "hoch"}).status_code == 200}
    assert lesbar == aenderbar
    erwartet = {
        ("admin", True): set(welt["aufgaben"]),
        ("buero_finanzen", True): {"eingang", "eingang_finanzen", "meine"},
        ("buero_auftrag", True): {"eingang", "meine"},
        ("buero_auftrag", False): {"eingang"},
    }[(rolle, mit_mitarbeiter)]
    assert lesbar == {welt["aufgaben"][k] for k in erwartet}


def test_regel_ist_eine_funktion(welt):
    db = welt["db"]
    nutzer = AppUser(username="b", display_name="b", role="buero_auftrag", employee_id=welt["erika"],
                     active=True, password_hash="-")
    sichtbar = {k for k, tid in welt["aufgaben"].items()
                if task_visible_for_user(nutzer, db.get(Task, tid).assigned_employee_id,
                                         db.get(Task, tid).min_visible_role)}
    assert sichtbar == {"eingang", "meine"}
    monteur = AppUser(username="m", display_name="m", role="field", employee_id=welt["erika"], active=True,
                      password_hash="-")
    assert not task_visible_for_user(monteur, None, None)


AENDERN = [
    ("put", "/api/tasks/{id}", {"title": "Übernommen von Auftrag", "priority": "hoch"}),
    ("delete", "/api/tasks/{id}", None),
    ("post", "/api/tasks/{id}/archive", None),
    ("post", "/api/tasks/{id}/unarchive", None),
    ("post", "/api/tasks/{id}/release", None),
    ("post", "/api/tasks/{id}/checklist-items", {"title": "Punkt"}),
]


@pytest.mark.parametrize("methode,pfad,body", AENDERN)
def test_angriff_buero_auftrag_aendert_finanz_aufgabe_per_id(router_test_client, welt, methode, pfad, body):
    db, tid = welt["db"], welt["aufgaben"]["eingang_finanzen"]
    client = _client(router_test_client, welt, "buero_auftrag", True)
    kwargs = {"json": body} if body is not None else {}
    response = getattr(client, methode)(pfad.format(id=tid), **kwargs)
    assert response.status_code == 403, response.text
    assert TITEL not in response.text and "Skonto" not in response.text
    db.expire_all()
    task = db.get(Task, tid)
    assert task is not None
    assert (task.title, task.priority, task.archived, task.min_visible_role) == (TITEL, "normal", False,
                                                                                "buero_finanzen")
    assert task.checklist_items == []


def test_angriff_auch_auf_persoenliche_aufgabe_des_kollegen(router_test_client, welt):
    client = _client(router_test_client, welt, "buero_auftrag", True)
    tid = welt["aufgaben"]["kollege"]
    assert client.post(f"/api/tasks/{tid}/release").status_code == 403
    assert client.delete(f"/api/tasks/{tid}").status_code == 403
    welt["db"].expire_all()
    assert welt["db"].get(Task, tid).assigned_employee_id is not None


def test_unbekannte_id_bleibt_404(router_test_client, welt):
    client = _client(router_test_client, welt, "buero_auftrag", True)
    assert client.put("/api/tasks/999999", json={"priority": "hoch"}).status_code == 404


@pytest.mark.parametrize("rolle", ["admin", "buero_finanzen"])
@pytest.mark.parametrize("wert", [None, "buero_auftrag", "admin"])
def test_sichtbarkeitsgrenze_ist_ueber_bearbeiten_nicht_aenderbar(router_test_client, welt, rolle, wert):
    db, tid = welt["db"], welt["aufgaben"]["eingang_finanzen"]
    client = _client(router_test_client, welt, rolle, True)
    response = client.put(f"/api/tasks/{tid}", json={"title": "x", "min_visible_role": wert})
    assert response.status_code == 422
    assert "Sichtbarkeitsgrenze" in response.text
    db.expire_all()
    assert (db.get(Task, tid).title, db.get(Task, tid).min_visible_role) == (TITEL, "buero_finanzen")


def test_berechtigte_aendern_weiterhin(router_test_client, welt):
    db = welt["db"]
    finanzen = _client(router_test_client, welt, "buero_finanzen", True)
    tid = welt["aufgaben"]["eingang_finanzen"]
    assert finanzen.put(f"/api/tasks/{tid}", json={"priority": "dringend"}).status_code == 200
    assert finanzen.post(f"/api/tasks/{tid}/checklist-items", json={"title": "Beleg prüfen"}).status_code == 200
    auftrag = _client(router_test_client, welt, "buero_auftrag", True)
    meine = welt["aufgaben"]["meine"]
    for methode, pfad in (("post", "/api/tasks/{id}/archive"), ("post", "/api/tasks/{id}/unarchive"),
                          ("post", "/api/tasks/{id}/release")):
        assert getattr(auftrag, methode)(pfad.format(id=meine)).status_code == 200
    assert auftrag.delete(f"/api/tasks/{welt['aufgaben']['eingang']}").status_code == 200
    db.expire_all()
    assert db.get(Task, tid).priority == "dringend"
