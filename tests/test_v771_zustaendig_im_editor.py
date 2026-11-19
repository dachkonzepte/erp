"""Version 1.9.373 (Nachrunde Urlaub, F1 aus dem Bericht a8d04f7): die Liste „Zuständig“ im Aufgaben-Editor bietet nur Personen an, die die
Aufgabe sähen -- nach derselben Regel wie die Prüfung beim Zuweisen (zuweisung_grund(), auch mit Mindestrolle).

    Regel        app/tasks.py::zustaendige(db, Mindestrolle): die Personen mit einem aktiven Konto, das eine ihnen zugewiesene Aufgabe sähe
                 (task_visible_for_user()); zuweisung_grund() fragt nur sie -- die Regel steht an einer Stelle
    Server       GET /api/tasks/zustaendige: je Mindestrolle (keine und jede Rolle, die das Konto selbst hat) die Personen; ab Büro – Auftrag,
                 Modul an
    Editor       tasks.html::employeeOptionsHtml(gespeichert, Mindestrolle): neu angeboten nur aktive Personen aus der Menge der Mindestrolle der
                 Aufgabe (neue Aufgabe: keine); eine gespeicherte außerhalb bleibt gewählt, „(sieht die Aufgabe nicht)“, eine inaktive „(inaktiv)“
                 (Regel 22) -- und wird unverändert gespeichert (Festlegung 1.9.371 Nr. 7); fehlt die Liste, alle aktiven wie bis 1.9.372
    Filter       „Mitarbeiter“ über dem Board (nur Admin) unverändert: jede aktive Person
"""

import ast
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import AppUser, EnabledModule, Employee, Task, TaskColumn
from app.routers import tasks as tasks_router
from app.tasks import zustaendige, zustaendige_je_mindestrolle, zuweisung_grund
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v447_auswahl_altwerte import WIRKSAM

ROOT = Path(__file__).resolve().parent.parent
MINDESTROLLEN = (None, "field", "buero_auftrag", "buero_finanzen", "admin")


def _person(db, nr, vor, nach, *, aktiv=True):
    p = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="angestellt", hourly_wage="20", weekly_hours="40", active=aktiv)
    db.add(p)
    db.flush()
    return p.id


@pytest.fixture
def welt(threaded_db_session):
    """Ada: Admin; Erika: Büro – Finanzen; Otto: Büro – Auftrag; Ina: Konto Büro – Auftrag inaktiv; Mo: Monteur; Olga: ohne Konto;
    Paul: Büro – Auftrag, die Person selbst inaktiv. Erfundene Namen."""
    db = threaded_db_session
    ids = {k: _person(db, f"Z-{i}", vor, nach, aktiv=k != "paul") for i, (k, vor, nach) in enumerate(
        (("ada", "Ada", "Admin"), ("erika", "Erika", "Eins"), ("otto", "Otto", "Zwei"), ("ina", "Ina", "Inaktiv"), ("mo", "Mo", "Monteur"),
         ("olga", "Olga", "Ohnekonto"), ("paul", "Paul", "Pause")), 1)}
    for k, rolle, aktiv in (("ada", "admin", True), ("erika", "buero_finanzen", True), ("otto", "buero_auftrag", True),
                            ("ina", "buero_auftrag", False), ("mo", "field", True), ("paul", "buero_auftrag", True)):
        db.add(AppUser(username=k, display_name=k, role=rolle, employee_id=ids[k], active=aktiv, password_hash="-"))
    db.commit()
    return {"db": db, **ids}


def test_regel_je_mindestrolle(welt):
    db, w = welt["db"], welt
    buero = {w["ada"], w["erika"], w["otto"], w["paul"]}  # Ina: Konto inaktiv; Mo: Monteur; Olga: kein Konto; Paul: die Person ist inaktiv, das Konto nicht
    assert zustaendige(db, None) == buero
    assert zustaendige(db, "field") == buero
    assert zustaendige(db, "buero_auftrag") == buero
    assert zustaendige(db, "buero_finanzen") == {w["ada"], w["erika"]}
    assert zustaendige(db, "admin") == {w["ada"]}
    assert zustaendige(db, "buero_finanzen", [w["otto"], w["erika"]]) == {w["erika"]}  # nur die genannten Personen


def test_dieselbe_menge_wie_die_pruefung_beim_zuweisen(welt):
    db = welt["db"]
    personen = [welt[k] for k in ("ada", "erika", "otto", "ina", "mo", "olga", "paul")]
    for rolle in MINDESTROLLEN:
        menge = zustaendige(db, rolle)
        assert {p for p in personen if zuweisung_grund(db, p, rolle) is None} == menge, rolle


def _funktion(name: str) -> ast.FunctionDef:
    baum = ast.parse((ROOT / "app" / "tasks.py").read_text(encoding="utf-8"))
    return next(n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef) and n.name == name)


def _aufrufe(f: ast.FunctionDef) -> set[str]:
    return {n.func.id for n in ast.walk(f) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def test_regel_an_einer_stelle():
    """zuweisung_grund() fragt zustaendige(), statt die Konten selbst zu lesen; zustaendige() prüft über task_visible_for_user() -- dieselbe Regel
    wie das Lesen. Der Endpunkt nimmt zustaendige_je_mindestrolle(), die wieder zustaendige()."""
    grund = _funktion("zuweisung_grund")
    assert "zustaendige" in _aufrufe(grund)
    assert "task_visible_for_user" not in _aufrufe(grund)
    assert not any(isinstance(n, ast.Attribute) and n.attr == "scalars" for n in ast.walk(grund))  # keine eigene Abfrage der Konten
    assert "task_visible_for_user" in _aufrufe(_funktion("zustaendige"))
    assert "zustaendige" in _aufrufe(_funktion("zustaendige_je_mindestrolle"))


def test_je_mindestrolle_nur_die_eigenen_rollen(welt):
    db, w = welt["db"], welt
    ada, otto = (db.scalar(select(AppUser).where(AppUser.username == n)) for n in ("ada", "otto"))
    assert [e["min_visible_role"] for e in zustaendige_je_mindestrolle(db, ada)] == list(MINDESTROLLEN)
    auftrag = zustaendige_je_mindestrolle(db, otto)
    assert [e["min_visible_role"] for e in auftrag] == [None, "field", "buero_auftrag"]  # nichts zu Büro – Finanzen und Administrator
    assert auftrag[0]["employee_ids"] == sorted([w["ada"], w["erika"], w["otto"], w["paul"]])


def test_endpunkt(welt, router_test_client):
    db, w = welt["db"], welt
    antwort = router_test_client(db, tasks_router.router, role="admin").get("/api/tasks/zustaendige")
    assert antwort.status_code == 200, antwort.text
    assert antwort.json() == [{"min_visible_role": r, "employee_ids": sorted(zustaendige(db, r))} for r in MINDESTROLLEN]
    auftrag = router_test_client(db, tasks_router.router, role="buero_auftrag").get("/api/tasks/zustaendige")
    assert [e["min_visible_role"] for e in auftrag.json()] == [None, "field", "buero_auftrag"]
    assert router_test_client(db, tasks_router.router, role="field").get("/api/tasks/zustaendige").status_code == 403
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    aus = router_test_client(db, tasks_router.router, role="admin").get("/api/tasks/zustaendige")
    assert aus.status_code == 403 and aus.json()["detail"] == "Das Modul Aufgabenmanagement ist deaktiviert."


def test_bestand_unveraendert_speichern(welt, router_test_client):
    """Die gespeicherte Zuweisung bleibt gewählt -- unverändert mitgeschickt nimmt der Server sie an (Festlegung 1.9.371 Nr. 7)."""
    db, w = welt["db"], welt
    spalte = db.scalar(select(TaskColumn.key).order_by(TaskColumn.sort_order, TaskColumn.id))
    task = Task(title="Alt an Mo", status=spalte, priority="normal", assigned_employee_id=w["mo"])  # vor 1.9.371 so zugewiesen
    db.add(task)
    db.commit()
    c = router_test_client(db, tasks_router.router, role="admin")
    r = c.put(f"/api/tasks/{task.id}", json={"title": "Alt an Mo", "assigned_employee_id": w["mo"], "priority": "hoch"})
    assert r.status_code == 200 and r.json()["assigned_employee_id"] == w["mo"]


# --- Editor in node -------------------------------------------------------------------------------------------------------------------

MITARBEITER = [{"id": 1, "first_name": "Ada", "last_name": "Admin", "active": True},
               {"id": 2, "first_name": "Erika", "last_name": "Eins", "active": True},
               {"id": 3, "first_name": "Otto", "last_name": "Zwei", "active": True},
               {"id": 4, "first_name": "Mo", "last_name": "Monteur", "active": True},
               {"id": 5, "first_name": "Olga", "last_name": "Ohnekonto", "active": True},
               {"id": 6, "first_name": "Paul", "last_name": "Pause", "active": False},
               {"id": 7, "first_name": "Ina", "last_name": "Inaktiv", "active": False}]  # Paul sähe sie (Konto aktiv), Ina nicht
ZUSTAENDIGE = [{"min_visible_role": None, "employee_ids": [1, 2, 3, 6]}, {"min_visible_role": "field", "employee_ids": [1, 2, 3, 6]},
               {"min_visible_role": "buero_auftrag", "employee_ids": [1, 2, 3, 6]}, {"min_visible_role": "buero_finanzen", "employee_ids": [1, 2]},
               {"min_visible_role": "admin", "employee_ids": [1]}]
AUFGABE = {"id": 7, "title": "T", "description": "", "status": "offen", "priority": "normal", "due_date": None, "assigned_employee_id": None,
           "project_id": None, "min_visible_role": None, "checklist_items": [], "source_module": None, "source_label": None, "archived": False}
ANTWORTEN = {"/api/auth/status": {"authenticated": True, "user": {"role": "admin", "employee_id": None}}, "/api/employees": MITARBEITER,
             "/api/projects?include_archived=true": [], "/api/task-columns": [{"key": "offen", "label": "Offen"}],
             "/api/tasks?include_archived=true": [], "/api/tasks?unassigned_only=true": []}


def _lauf(ablauf: str, antworten: dict | None = None):
    vorab = f"employees = {json.dumps(MITARBEITER)}; zustaendige = {json.dumps(ZUSTAENDIGE)}; projects = [];"
    return im_browser(seite("tasks.html", "\ninit();") + WIRKSAM, vorab + ablauf, antworten)["ergebnis"]


def _optionen(ausdruck: str) -> str:
    return f"_optionen({ausdruck}).map(o => [o.value, o.text, o.selected])"


@nur_mit_node
def test_editor_neue_aufgabe_nur_wer_sie_saehe():
    assert _lauf(f"return {_optionen('employeeOptionsHtml(null, null)')};") == [
        ["", "— nicht zugeordnet —", True], ["1", "Ada Admin", False], ["2", "Erika Eins", False], ["3", "Otto Zwei", False]]


@nur_mit_node
def test_editor_mit_mindestrolle():
    assert _lauf(f"return [{_optionen('employeeOptionsHtml(null, \"buero_finanzen\")')}, {_optionen('employeeOptionsHtml(null, \"admin\")')}];") == [
        [["", "— nicht zugeordnet —", True], ["1", "Ada Admin", False], ["2", "Erika Eins", False]],
        [["", "— nicht zugeordnet —", True], ["1", "Ada Admin", False]]]


@nur_mit_node
def test_editor_gespeicherte_zuweisung_bleibt_gekennzeichnet():
    ergebnis = _lauf("return [_wirksam('<select id=\"t\">' + employeeOptionsHtml(4, null) + '</select>', 'id=\"t\"'),"
                     " _wirksam('<select id=\"t\">' + employeeOptionsHtml(5, null) + '</select>', 'id=\"t\"'),"
                     " _wirksam('<select id=\"t\">' + employeeOptionsHtml(6, null) + '</select>', 'id=\"t\"'),"
                     " _wirksam('<select id=\"t\">' + employeeOptionsHtml(3, 'buero_finanzen') + '</select>', 'id=\"t\"'),"
                     " _wirksam('<select id=\"t\">' + employeeOptionsHtml(7, null) + '</select>', 'id=\"t\"'),"
                     f" {_optionen('employeeOptionsHtml(4, null)')}.map(o => o[0])];")
    assert ergebnis == [["4", "Mo Monteur (sieht die Aufgabe nicht)"], ["5", "Olga Ohnekonto (sieht die Aufgabe nicht)"],
                        ["6", "Paul Pause (inaktiv)"], ["3", "Otto Zwei (sieht die Aufgabe nicht)"],
                        ["7", "Ina Inaktiv (inaktiv)"],  # inaktiv geht vor
                        ["", "1", "2", "3", "4"]]  # Olga bleibt draußen; Mo nur, weil gespeichert


@nur_mit_node
def test_editor_oeffnen_nimmt_die_mindestrolle_der_aufgabe():
    fin = dict(AUFGABE, min_visible_role="buero_finanzen")
    alt = dict(AUFGABE, id=8, assigned_employee_id=4)
    ergebnis = _lauf(f"tasks = [{json.dumps(fin)}, {json.dumps(alt)}];"
                     f"openEditor(7); const a = {_optionen('_element(\"editEmployee\").innerHTML')};"
                     f"openEditor(8); const b = _feld('editEmployee');"
                     f"authStatus = {{user: {{employee_id: 3}}}}; columns = []; openCreateEditor(); const c = {_optionen('_element(\"editEmployee\").innerHTML')};"
                     "return [a.map(o => o[0]), b, c];")
    assert ergebnis == [["", "1", "2"], ["4", "Mo Monteur (sieht die Aufgabe nicht)"],
                        [["", "— nicht zugeordnet —", False], ["1", "Ada Admin", False], ["2", "Erika Eins", False],
                         ["3", "Otto Zwei", True]]]  # neu: ohne Mindestrolle, die eigene Person vorgewählt und ohne Kennzeichen


@nur_mit_node
def test_editor_speichert_die_gespeicherte_zuweisung_unveraendert():
    alt = dict(AUFGABE, id=8, assigned_employee_id=4)
    ergebnis = _lauf(f"authStatus = {{user: {{role: 'admin', employee_id: null}}}}; tasks = [{json.dumps(alt)}]; openEditor(8); await saveTask();"
                     "return AUFRUFE.filter(a => a.methode === 'PUT').map(a => [a.url, a.body.assigned_employee_id]);",
                     {"/api/tasks?include_archived=true": [], "/api/tasks?unassigned_only=true": []})
    assert ergebnis == [["/api/tasks/8", 4]]


@nur_mit_node
def test_init_laedt_die_liste_und_faellt_sonst_zurueck():
    mit = _lauf("zustaendige = null; await init(); return [AUFRUFE.some(a => a.url === '/api/tasks/zustaendige'),"
                f" {_optionen('employeeOptionsHtml(null, null)')}.map(o => o[0])];", dict(ANTWORTEN, **{"/api/tasks/zustaendige": ZUSTAENDIGE}))
    assert mit == [True, ["", "1", "2", "3"]]
    ohne = _lauf(f"zustaendige = null; await init(); return [zustaendige, {_optionen('employeeOptionsHtml(null, null)')}.map(o => o[0])];", ANTWORTEN)
    assert ohne == [None, ["", "1", "2", "3", "4", "5"]]  # Liste fehlt: alle aktiven wie bis 1.9.372, der Server prüft weiter


@nur_mit_node
def test_filter_des_admins_unveraendert():
    """Der Filter „Mitarbeiter“ über dem Board ist keine Zuweisung: jede aktive Person, auch wer keine Aufgabe sähe."""
    ergebnis = _lauf("authStatus = {user: {role: 'admin', employee_id: null}}; await loadFilters();"
                     f"return {_optionen('_element(\"employeeFilter\").innerHTML')}.map(o => o[0]);")
    assert ergebnis == ["", "1", "2", "3", "4", "5"]
