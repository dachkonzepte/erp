"""Version 1.8.3 -- Regeln einer Checkliste legen beim Abschluss Aufgaben fürs Büro an
(app/checklist_rules.py, siehe docs/archiv/modul-checklisten.md, "Umsetzung 1.8.3").

Geprüft: jeder Operator, Platzhalter/Priorität/Fälligkeit/Empfänger, Idempotenz (zweiter Aufruf,
zweiter Abschluss), Aufgabenmodul aus → "modul_aus" → nachholen, Abbruch beim Anlegen →
"ausstehend" → nachholen ohne Doppel, konkurrierendes Nachholen, eingefrorene Fassung, Rechte."""

from datetime import timedelta

import pytest

import app.tasks as tasks_module
from app.checklist_rules import _claim_open, run_checklist_rules
from app.checklist_templates import add_field, add_option, add_rule, create_template, publish_draft, start_draft
from app.models import ChecklistRuleExecution, EnabledModule, Task
from tests.test_v305_checklist_filling import _client, _fields, _jpeg, world  # noqa: F401 -- Fixture

EXPECTED = {"Immer Regeltest / Auftrag AU-2026-0001 / Anna Alpha", "nein-frei", "hat-geruest", "wind-30",
            "fotos-da", "finanzen"}


def _rule_template(db):
    t = create_template(db, label="Regeltest", contexts=["auftrag"])
    v = t["draft_version_id"]
    add_field(db, v, {"field_type": "ja_nein", "label": "Frei", "field_key": "frei"})
    art = add_field(db, v, {"field_type": "auswahl", "label": "Art", "field_key": "art", "multiple": True})
    art_id = next(f["id"] for f in art["fields"] if f["field_key"] == "art")
    add_option(db, art_id, "Gerüst", option_key="geruest")
    add_option(db, art_id, "Netz", option_key="netz")
    typ = add_field(db, v, {"field_type": "auswahl", "label": "Typ", "field_key": "typ"})
    typ_id = next(f["id"] for f in typ["fields"] if f["field_key"] == "typ")
    add_option(db, typ_id, "A", option_key="a")
    add_option(db, typ_id, "B", option_key="b")
    add_field(db, v, {"field_type": "zahl", "label": "Wind", "field_key": "wind"})
    add_field(db, v, {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    add_field(db, v, {"field_type": "foto", "label": "Fotos", "field_key": "fotos"})
    for rule in (
        {"operator": "immer", "task_title": "Immer {vorlage} / {kontext} / {ersteller}", "task_priority": "hoch",
         "due_in_days": 3, "assignee_mode": "sachbearbeiter", "task_description": "Bitte {vorlage} prüfen {nicht}"},
        {"operator": "ist_nein", "field_key": "frei", "task_title": "nein-frei"},
        {"operator": "ist_ja", "field_key": "frei", "task_title": "ja-frei"},
        {"operator": "enthaelt", "field_key": "art", "operand": "geruest", "task_title": "hat-geruest"},
        {"operator": "enthaelt", "field_key": "typ", "operand": "b", "task_title": "typ-b"},
        {"operator": "groesser", "field_key": "wind", "operand": "50", "task_title": "wind-gross"},
        {"operator": "kleiner", "field_key": "wind", "operand": "10", "task_title": "wind-klein"},
        {"operator": "gleich", "field_key": "wind", "operand": "30", "task_title": "wind-30"},
        {"operator": "ausgefuellt", "field_key": "bem", "task_title": "bem-da"},
        {"operator": "ausgefuellt", "field_key": "fotos", "task_title": "fotos-da"},
        {"operator": "immer", "task_title": "finanzen", "min_visible_role": "buero_finanzen"},
    ):
        add_rule(db, v, rule)
    return publish_draft(db, t["id"])


@pytest.fixture
def rules(world):
    db = world["db"]
    world["orders"]["mine"].caseworker_employee_id = world["emps"]["office"].id
    db.commit()
    world["rule_tpl"] = _rule_template(db)
    return world


def _start_filled(world, client):
    c = client.post("/api/checklists", json={"template_id": world["rule_tpl"]["id"], "context_type": "auftrag",
                                             "order_id": world["orders"]["mine"].id}).json()
    f = _fields(c)
    for key, value in (("frei", "nein"), ("art", ["geruest"]), ("typ", "a"), ("wind", "30")):
        assert client.put(f"/api/checklists/{c['id']}/answers/{f[key]}", json={"value": value}).status_code == 200
    assert client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["fotos"]},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).status_code == 200
    return c


def _tasks(world):
    return {t.title: t for t in world["db"].query(Task).all()}


def test_completion_creates_tasks_for_matching_rules(rules, router_test_client):
    field = _client(rules, router_test_client, "a")
    c = _start_filled(rules, field)
    assert _tasks(rules) == {}  # vor dem Abschluss nichts
    done = field.post(f"/api/checklists/{c['id']}/complete")
    assert done.status_code == 200 and done.json()["status"] == "abgeschlossen"

    tasks = _tasks(rules)
    assert set(tasks) == EXPECTED
    always = tasks["Immer Regeltest / Auftrag AU-2026-0001 / Anna Alpha"]
    assert always.priority == "hoch"
    assert always.assigned_employee_id == rules["emps"]["office"].id  # Sachbearbeiter des Auftrags
    assert always.project_id == rules["orders"]["mine"].project_id
    assert always.source_module == "checklisten" and always.source_url == f"/checklisten/{c['id']}"
    assert always.description.startswith("Bitte Regeltest prüfen {nicht}")  # fremde Klammer bleibt stehen
    assert "Bedingung: immer beim Abschluss" in always.description
    checklist_row = rules["db"].query(ChecklistRuleExecution).filter_by(task_id=always.id).one().checklist
    assert always.due_date == checklist_row.completed_at.date() + timedelta(days=3)
    assert tasks["finanzen"].assigned_employee_id is None and tasks["finanzen"].min_visible_role == "buero_finanzen"
    assert tasks["nein-frei"].min_visible_role == "buero_auftrag" and tasks["nein-frei"].priority == "normal"
    assert "„Frei“ ist nein" in tasks["nein-frei"].description
    assert "„Art“ enthält „Gerüst“" in tasks["hat-geruest"].description

    # Idempotent: erneuter Abschluss und erneute Auswertung legen nichts doppelt an.
    assert field.post(f"/api/checklists/{c['id']}/complete").status_code == 200
    assert run_checklist_rules(rules["db"], c["id"]) == {"created": 0, "module_off": 0}
    assert rules["db"].query(Task).count() == len(EXPECTED)
    statuses = {e.status for e in rules["db"].query(ChecklistRuleExecution).all()}
    assert statuses == {"aufgabe_angelegt"}

    office = _client(rules, router_test_client, "office")
    rows = office.get(f"/api/checklists/{c['id']}/rule-executions").json()
    assert {r["task_title"] for r in rows} == EXPECTED and all(r["task_id"] for r in rows)


def test_sachbearbeiter_missing_falls_back_to_role(rules, router_test_client):
    rules["orders"]["mine"].caseworker_employee_id = None
    rules["db"].commit()
    field = _client(rules, router_test_client, "a")
    c = _start_filled(rules, field)
    field.post(f"/api/checklists/{c['id']}/complete")
    task = _tasks(rules)["Immer Regeltest / Auftrag AU-2026-0001 / Anna Alpha"]
    assert task.assigned_employee_id is None and task.min_visible_role == "buero_auftrag"


def test_task_module_off_is_recorded_and_can_be_caught_up(rules, router_test_client):
    db = rules["db"]
    module = EnabledModule(module_key="aufgabenmanagement", enabled=False)
    db.add(module)
    db.commit()
    field = _client(rules, router_test_client, "a")
    office = _client(rules, router_test_client, "office")
    c = _start_filled(rules, field)
    assert field.post(f"/api/checklists/{c['id']}/complete").status_code == 200
    assert db.query(Task).count() == 0
    rows = office.get(f"/api/checklists/{c['id']}/rule-executions").json()
    assert len(rows) == len(EXPECTED) and {r["status"] for r in rows} == {"modul_aus"}
    assert {r["rule_title"] for r in rows} == EXPECTED  # Platzhalter schon vor dem Anlegen eingesetzt
    assert [r["id"] for r in office.get("/api/checklists?open_rules=true").json()] == [c["id"]]

    # Nachholen bei weiterhin ausgeschaltetem Modul ändert nichts.
    assert office.post(f"/api/checklists/{c['id']}/run-rules").json() == {"created": 0, "module_off": len(EXPECTED)}
    assert db.query(Task).count() == 0

    module.enabled = True
    db.commit()
    assert office.post("/api/checklists/run-open-rules").json() == {"created": len(EXPECTED), "module_off": 0}
    assert office.post(f"/api/checklists/{c['id']}/run-rules").json() == {"created": 0, "module_off": 0}
    assert db.query(Task).count() == len(EXPECTED)
    assert office.get("/api/checklists?open_rules=true").json() == []


def test_failure_while_creating_leaves_pending_and_catch_up_creates_no_duplicates(rules, router_test_client, monkeypatch):
    real_create = tasks_module.create_task
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("Datenbank kurz weg")
        return real_create(*args, **kwargs)

    monkeypatch.setattr(tasks_module, "create_task", flaky)
    field = _client(rules, router_test_client, "a")
    office = _client(rules, router_test_client, "office")
    c = _start_filled(rules, field)
    done = field.post(f"/api/checklists/{c['id']}/complete")
    assert done.status_code == 200 and done.json()["status"] == "abgeschlossen"  # Abschluss bleibt gültig
    db = rules["db"]
    assert db.query(Task).count() == 1
    assert [e.status for e in db.query(ChecklistRuleExecution).all()] == ["aufgabe_angelegt", "ausstehend"]
    assert [r["id"] for r in office.get("/api/checklists?open_rules=true").json()] == [c["id"]]

    assert office.post(f"/api/checklists/{c['id']}/run-rules").json()["created"] == len(EXPECTED) - 1
    assert set(_tasks(rules)) == EXPECTED and db.query(Task).count() == len(EXPECTED)


def test_open_execution_is_claimed_only_once(rules, router_test_client):
    """Zwei gleichzeitige "Nachholen" derselben "ausstehend"-Zeile: der Status allein unterscheidet
    die beiden nicht (ausstehend → ausstehend), nur der Stempel executed_at -- wer mit veraltetem
    Stand belegen will, verliert."""
    db = rules["db"]
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    field = _client(rules, router_test_client, "a")
    c = _start_filled(rules, field)
    field.post(f"/api/checklists/{c['id']}/complete")
    row = db.query(ChecklistRuleExecution).first()
    row.status = "ausstehend"
    db.commit()
    stale = db.get(ChecklistRuleExecution, row.id)
    db.expunge(stale)  # Stand "vor" dem anderen Aufrufer festhalten
    fresh = db.get(ChecklistRuleExecution, stale.id)
    assert _claim_open(db, fresh, "ausstehend") is True
    assert _claim_open(db, stale, "ausstehend") is False


def test_rules_of_the_frozen_version_apply(rules, router_test_client):
    """Eine Checkliste auf Fassung 1 bekommt keine Regel, die erst Fassung 2 hinzufügt."""
    db = rules["db"]
    field = _client(rules, router_test_client, "a")
    c = _start_filled(rules, field)
    draft = start_draft(db, rules["rule_tpl"]["id"])
    add_rule(db, draft["draft_version_id"], {"operator": "immer", "task_title": "erst-in-fassung-2"})
    publish_draft(db, rules["rule_tpl"]["id"])
    field.post(f"/api/checklists/{c['id']}/complete")
    assert "erst-in-fassung-2" not in _tasks(rules) and set(_tasks(rules)) == EXPECTED


def test_draft_rules_cannot_be_run(rules, router_test_client):
    office = _client(rules, router_test_client, "office")
    c = _start_filled(rules, _client(rules, router_test_client, "a"))
    assert office.post(f"/api/checklists/{c['id']}/run-rules").status_code == 400
    assert rules["db"].query(Task).count() == 0


def test_field_never_sees_or_triggers_rule_executions(rules, router_test_client):
    field = _client(rules, router_test_client, "a")
    c = _start_filled(rules, field)
    field.post(f"/api/checklists/{c['id']}/complete")
    order_id = rules["orders"]["mine"].id
    for method, url in (("GET", f"/api/checklists/{c['id']}/rule-executions"),
                        ("POST", f"/api/checklists/{c['id']}/run-rules"),
                        ("POST", "/api/checklists/run-open-rules"),
                        ("GET", f"/api/checklists?open_rules=true&order_id={order_id}")):
        assert field.request(method, url).status_code == 403, url
    assert "rule_executions" not in field.get(f"/api/checklists/{c['id']}").json()
