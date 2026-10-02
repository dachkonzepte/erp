"""Version 1.8.16 -- Stufe 2, Runde 2a-2: Zweck, Systemfelder, Folgetabelle
(app/checklist_purposes.py, app/checklist_templates.py, app/checklist_follow_ups.py; siehe
docs/archiv/modul-checklisten.md, "Umsetzung 1.8.16").

Abnahme, Behinderungs- und Bedenkenanzeige tragen noch keine Systemfelder und Folgen -- geprüft
wird mit einem Test-Zweck, der per monkeypatch in die Registry kommt: vier Systemfelder (ja/nein
mit "entfällt", Auswahl mit Optionen, Foto mit Mindestanzahl, Unterschrift) und eine Folge, die wie
eine echte eine Büro-Aufgabe anlegt."""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app.checklist_follow_ups as follow_ups_module
from app.checklist_purposes import PURPOSES, ChecklistPurpose, FollowUp, SystemField, section_order_problem
from app.checklist_templates import (
    _FIELD_KEY_PATTERN, CONTEXT_TYPES, FIELD_TYPES, _normalize_field, add_field, add_option, add_rule, copy_template,
    create_template, delete_field, delete_option, delete_template, get_template, publish_draft, set_template_archived,
    start_draft, sync_system_fields, update_field, update_option, update_template,
)
from app.checklists import create_checklist, list_startable_templates
from app.models import (
    ChecklistFollowUp, ChecklistTemplate, ChecklistTemplateField, ChecklistTemplateVersion, EnabledModule, Task,
)
from app.routers.checklist_templates import router as checklist_templates_router
from app.tasks import create_task
from tests.test_v305_checklist_filling import _client, _fields, _jpeg, _png, world  # noqa: F401 -- Fixture

TEST_KEY = "testzweck"
SECRET = "GEHEIM-BUERO"
SYSTEM_FIELDS = (
    SystemField("testzweck.bestaetigt", "ja_nein", "Bestätigt", required=True, allow_na=True),
    SystemField("testzweck.art", "auswahl", "Art", required=True,
                options=(("voll", "vollständig"), ("teil", "teilweise"))),
    SystemField("testzweck.fotos", "foto", "Nachweisfotos", min_count=1),
    SystemField("testzweck.unterschrift", "unterschrift", "Unterschrift", required=True),
)
# Was ein Monteur nie zu sehen bekommt: Regeln und ihre Aufgaben, Folgen und ihr Ziel, Lohndaten.
OFFICE_KEYS = {
    "rules", "rule_executions", "follow_ups", "follow_up_key", "target_type", "target_id", "task_id", "task_title",
    "task_description", "operator", "operand", "assignee_mode", "min_visible_role", "system_field_problems",
    "hourly_wage", "caseworker_employee_id",
}


def _register(monkeypatch, state, *, module=None, extra_fields=()):
    def handler(db, checklist):
        state["calls"].append(checklist.id)
        if state["fail"]:
            state["fail"] -= 1
            raise RuntimeError("Testfehler")
        task = create_task(db, title=f"{SECRET} Folge {checklist.id}", source_module="checklisten",
                           min_visible_role="buero_auftrag")
        return "task", task["id"]

    monkeypatch.setitem(PURPOSES, TEST_KEY, ChecklistPurpose(
        TEST_KEY, "Testzweck", ("auftrag",), SYSTEM_FIELDS + tuple(extra_fields),
        (FollowUp("testzweck.folge", "Testfolge", handler, module=module),),
    ))


@pytest.fixture
def testzweck(monkeypatch):
    state = {"calls": [], "fail": 0}
    _register(monkeypatch, state)
    return state


def _meta(t, **changes):
    values = {"label": t["label"], "description": t["description"], "contexts": t["contexts"],
              "field_readable": t["field_readable"]}
    values.update(changes)
    return values


def _purpose_template(db, label="Testvorlage", publish=True):
    t = create_template(db, label=label, contexts=["auftrag"], purpose=TEST_KEY)
    add_field(db, t["draft_version_id"], {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    add_rule(db, t["draft_version_id"], {"operator": "immer", "task_title": f"{SECRET} Regel"})
    return publish_draft(db, t["id"]) if publish else get_template(db, t["id"])


def _system(fields):
    return {f["field_key"]: f for f in fields if f["is_system"]}


def _collect_keys(value, keys):
    if isinstance(value, dict):
        for key, inner in value.items():
            keys.add(key)
            _collect_keys(inner, keys)
    elif isinstance(value, list):
        for inner in value:
            _collect_keys(inner, keys)
    return keys


# --- Registry -------------------------------------------------------------------------------

def test_registry_has_the_four_purposes_and_the_three_only_at_orders():
    assert {"allgemein", "abnahme", "behinderungsanzeige", "bedenkenanzeige"} <= set(PURPOSES)
    assert PURPOSES["allgemein"].contexts == ("auftrag", "objekt", "betriebsmittel", "betrieb")
    for key in ("abnahme", "behinderungsanzeige", "bedenkenanzeige"):
        assert PURPOSES[key].contexts == ("auftrag",)
    # die Behinderungsanzeige hat sie seit 1.8.38 (test_v341), die Bedenkenanzeige seit 1.8.43 (test_v346)
    assert PURPOSES["abnahme"].system_fields == () and PURPOSES["abnahme"].follow_ups == ()  # kommt in 2c


def test_every_registered_purpose_is_consistent(testzweck):
    """Wächter für 2b/2c: jede Vorgabe muss sich als Feld anlegen lassen, ohne dass die
    Normalisierung eine feste Eigenschaft verändert (sonst meldete Veröffentlichen eine
    Abweichung, die niemand beheben kann)."""
    for purpose in PURPOSES.values():
        assert purpose.contexts and set(purpose.contexts) <= set(CONTEXT_TYPES), purpose.key
        assert len({f.key for f in purpose.follow_ups}) == len(purpose.follow_ups), purpose.key
        assert len({s.key for s in purpose.system_fields}) == len(purpose.system_fields), purpose.key
        signatures = {s.key for s in purpose.system_fields if s.field_type == "unterschrift"}
        for follow_up in purpose.follow_ups:  # seit 1.8.38: Auslöser ist ein Unterschrifts-Systemfeld
            assert follow_up.after_signature is None or follow_up.after_signature in signatures, follow_up.key
            # seit 1.8.43: oder der Versand eines Briefs -- höchstens ein Auslöser je Folge
            assert not (follow_up.after_signature and follow_up.after_letter), follow_up.key
        # Abschnitte (seit 1.8.38): entweder alle Systemfelder mit Abschnitt oder keines, und die
        # Vorgabe selbst steht in einer Reihenfolge, die das Veröffentlichen annimmt.
        sections = [s.section for s in purpose.system_fields]
        assert all(sections) or not any(sections), purpose.key
        assert section_order_problem(purpose, [s.key for s in purpose.system_fields]) is None, purpose.key
        for spec in purpose.system_fields:
            assert spec.field_type in FIELD_TYPES and spec.field_type != "hinweis", spec.key
            assert _FIELD_KEY_PATTERN.match(spec.key), spec.key
            assert bool(spec.options) == (spec.field_type == "auswahl"), spec.key
            assert {k for k, _hint in spec.option_hints} <= {k for k, _label in spec.options}, spec.key
            field = ChecklistTemplateField(field_key=spec.key, field_type=spec.field_type, label=spec.label,
                                           required=spec.required, allow_na=spec.allow_na, multiple=spec.multiple,
                                           min_count=spec.min_count)
            _normalize_field(field)
            assert (field.required, field.allow_na, field.multiple, field.min_count) == (
                spec.required, spec.allow_na, spec.multiple, spec.min_count), spec.key


# --- Zweck setzen, Kontexte -----------------------------------------------------------------

def test_setting_the_purpose_adds_its_system_fields_to_the_draft(world, testzweck):
    db = world["db"]
    t = create_template(db, label="Später mit Zweck", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    t = update_template(db, t["id"], **_meta(t, purpose=TEST_KEY))
    v = t["editable_version"]
    assert t["purpose"] == TEST_KEY and v["purpose"] == TEST_KEY and t["purpose_label"] == "Testzweck"
    assert t["system_field_problems"] == [] and not t["purpose_locked"]
    system = _system(v["fields"])
    assert set(system) == {s.key for s in SYSTEM_FIELDS}
    assert v["fields"][0]["field_key"] == "bem"  # Systemfelder werden angehängt
    assert system["testzweck.bestaetigt"]["required"] and system["testzweck.bestaetigt"]["allow_na"]
    assert [o["option_key"] for o in system["testzweck.art"]["options"]] == ["voll", "teil"]
    assert system["testzweck.fotos"]["min_count"] == 1
    assert system["testzweck.unterschrift"]["max_count"] == 1  # wie jede Einzelunterschrift

    # Zurück auf "allgemein" (nie veröffentlicht): die Felder bleiben, sind aber gewöhnliche Felder.
    t = update_template(db, t["id"], **_meta(t, purpose="allgemein"))
    assert not _system(t["editable_version"]["fields"]) and len(t["editable_version"]["fields"]) == 5
    delete_field(db, next(f["id"] for f in t["editable_version"]["fields"] if f["field_key"] == "testzweck.art"))


def test_purpose_restricts_the_contexts(world, testzweck):
    db = world["db"]
    t = create_template(db, label="Zwei Kontexte", contexts=["auftrag", "objekt"])
    with pytest.raises(ValueError, match="nur im Kontext Auftrag möglich -- bitte Objekt abwählen"):
        update_template(db, t["id"], **_meta(t, purpose=TEST_KEY))
    after = get_template(db, t["id"])
    assert after["purpose"] == "allgemein" and after["editable_version"]["fields"] == []  # nichts halb gespeichert
    t = update_template(db, t["id"], **_meta(t, contexts=["auftrag"], purpose=TEST_KEY))
    with pytest.raises(ValueError, match="nur im Kontext Auftrag"):
        update_template(db, t["id"], **_meta(t, contexts=["auftrag", "objekt"]))  # Zweck unverändert
    for key in ("abnahme", "behinderungsanzeige", "bedenkenanzeige"):
        with pytest.raises(ValueError, match="nur im Kontext Auftrag"):
            create_template(db, label=key, contexts=["betrieb"], purpose=key)
    with pytest.raises(ValueError, match="Unbekannter Zweck"):
        create_template(db, label="Unbekannt", contexts=["auftrag"], purpose="gibt_es_nicht")


# --- Systemfelder ---------------------------------------------------------------------------

def test_system_field_locked_attributes_options_and_deletion(world, testzweck):
    db = world["db"]
    t = _purpose_template(db, publish=False)
    before = t["editable_version"]["fields"]
    system = _system(before)
    ja, art, fotos = system["testzweck.bestaetigt"], system["testzweck.art"], system["testzweck.fotos"]
    for field_id, change in ((ja["id"], {"field_key": "anders"}), (ja["id"], {"field_type": "text"}),
                             (ja["id"], {"required": False}), (ja["id"], {"allow_na": False}),
                             (art["id"], {"multiple": True}), (fotos["id"], {"min_count": 0}),
                             (fotos["id"], {"min_count": None})):
        with pytest.raises(ValueError, match="eines Systemfelds kann nicht geändert werden"):
            update_field(db, field_id, change)
    with pytest.raises(ValueError, match="Systemfeld kann nicht gelöscht werden"):
        delete_field(db, ja["id"])
    with pytest.raises(ValueError, match="fest vorgegeben"):
        add_option(db, art["id"], "Neu")
    with pytest.raises(ValueError, match="fest vorgegeben"):
        update_option(db, art["options"][0]["id"], label="Anders")
    with pytest.raises(ValueError, match="fest vorgegeben"):
        delete_option(db, art["options"][0]["id"])
    assert get_template(db, t["id"])["editable_version"]["fields"] == before  # nichts verändert

    # Frei: Beschriftung, Hilfetext, Abschnitt -- feste Werte dürfen unverändert mitkommen (Editor).
    v = update_field(db, ja["id"], {"label": "Abnahme erklärt", "help_text": "Mit dem Kunden", "group_name": "Ergebnis",
                                    "field_key": " testzweck.bestaetigt ", "required": True, "allow_na": True})
    changed = _system(v["fields"])["testzweck.bestaetigt"]
    assert (changed["label"], changed["group_name"], changed["is_system"]) == ("Abnahme erklärt", "Ergebnis", True)
    assert changed["field_key"] == "testzweck.bestaetigt"


def test_publish_requires_every_system_field_as_prescribed(world, testzweck, monkeypatch):
    db = world["db"]
    # 1. Der Zweck bekommt nach dem Anlegen des Entwurfs ein weiteres Systemfeld (wie in 2b/2c).
    t = _purpose_template(db, publish=False)
    _register(monkeypatch, testzweck, extra_fields=(SystemField("testzweck.datum", "datum", "Datum", required=True),))
    with pytest.raises(ValueError, match=r"„Datum“ \(testzweck.datum\) fehlt"):
        publish_draft(db, t["id"])
    assert get_template(db, t["id"])["published_version_no"] is None
    assert get_template(db, t["id"])["system_field_problems"] == ["Das Systemfeld „Datum“ (testzweck.datum) fehlt."]
    v = sync_system_fields(db, t["draft_version_id"])
    assert "testzweck.datum" in _system(v["fields"])
    assert publish_draft(db, t["id"])["published_version_no"] == 1

    # 2. Systemfeld an der API vorbei gelöscht.
    t2 = _purpose_template(db, label="Ohne Art", publish=False)
    db.delete(db.scalar(select(ChecklistTemplateField).where(
        ChecklistTemplateField.version_id == t2["draft_version_id"], ChecklistTemplateField.field_key == "testzweck.art")))
    db.commit()
    with pytest.raises(ValueError, match=r"„Art“ \(testzweck.art\) fehlt"):
        publish_draft(db, t2["id"])

    # 3. Feste Eigenschaft und Optionen an der API vorbei verändert.
    t3 = _purpose_template(db, label="Verändert", publish=False)
    fields = {f.field_key: f for f in db.scalars(select(ChecklistTemplateField).where(
        ChecklistTemplateField.version_id == t3["draft_version_id"])).all()}
    fields["testzweck.bestaetigt"].required = False
    fields["testzweck.art"].options[0].option_key = "anders"
    db.commit()
    with pytest.raises(ValueError, match="weicht von der Vorgabe ab: Pflichtfeld.*weicht von der Vorgabe ab: Optionen"):
        publish_draft(db, t3["id"])
    assert get_template(db, t3["id"])["published_version_no"] is None


# --- Einfrieren, Kopie, Löschen -------------------------------------------------------------

def test_purpose_is_frozen_at_publishing_and_cannot_change_afterwards(world, testzweck):
    db = world["db"]
    t = _purpose_template(db)
    assert t["purpose_locked"]
    version_id = t["published_version_id"]
    assert db.get(ChecklistTemplateVersion, version_id).purpose == TEST_KEY
    with pytest.raises(ValueError, match="seit der ersten Veröffentlichung festgelegt"):
        update_template(db, t["id"], **_meta(t, purpose="allgemein"))
    db.expire_all()
    assert db.get(ChecklistTemplate, t["id"]).purpose == TEST_KEY
    assert db.get(ChecklistTemplateVersion, version_id).purpose == TEST_KEY
    # Verwaltungsdaten ohne Zweckangabe bleiben änderbar.
    assert update_template(db, t["id"], **_meta(t, label="Umbenannt"))["label"] == "Umbenannt"
    # Ein neuer Entwurf trägt denselben Zweck, die Systemfelder bleiben geschützt.
    draft = start_draft(db, t["id"])
    assert draft["editable_version"]["purpose"] == TEST_KEY and draft["system_field_problems"] == []
    with pytest.raises(ValueError, match="nicht gelöscht"):
        delete_field(db, _system(draft["editable_version"]["fields"])["testzweck.art"]["id"])
    with pytest.raises(ValueError, match="festgelegt"):
        update_template(db, t["id"], **_meta(t, purpose="abnahme"))


def test_checklist_uses_the_purpose_of_its_version(world, testzweck):
    db = world["db"]
    t = _purpose_template(db)
    # Die Vorlage an der Geschäftslogik vorbei verbogen: Zweck zurück, Objekt erlaubt. Maßgeblich
    # bleibt der an der Fassung eingefrorene Zweck.
    template = db.get(ChecklistTemplate, t["id"])
    template.purpose, template.context_property = "allgemein", True
    db.commit()
    assert t["id"] not in [x["id"] for x in list_startable_templates(db, "objekt")]
    offered = [x for x in list_startable_templates(db, "auftrag") if x["id"] == t["id"]]
    assert offered and offered[0]["purpose"] == TEST_KEY and offered[0]["purpose_label"] == "Testzweck"
    with pytest.raises(ValueError, match="Zweck Testzweck ist nur im Kontext Auftrag"):
        create_checklist(db, template_id=t["id"], context_type="objekt", property_id=world["prop"].id)
    c = create_checklist(db, template_id=t["id"], context_type="auftrag", order_id=world["orders"]["mine"].id)
    assert c["purpose"] == TEST_KEY

    # Unbekannter Zweck (aus der Registry verschwunden): nicht mehr startbar.
    db.get(ChecklistTemplateVersion, t["published_version_id"]).purpose = "verschwunden"
    db.commit()
    assert t["id"] not in [x["id"] for x in list_startable_templates(db, "auftrag")]
    with pytest.raises(ValueError, match="unbekannt"):
        create_checklist(db, template_id=t["id"], context_type="auftrag", order_id=world["orders"]["mine"].id)


def test_copy_inherits_purpose_and_system_fields(world, testzweck):
    db = world["db"]
    t = _purpose_template(db)
    copy = copy_template(db, t["id"], "Kopie")
    assert copy["purpose"] == TEST_KEY and not copy["purpose_locked"]
    assert copy["editable_version"]["purpose"] == TEST_KEY
    system = _system(copy["editable_version"]["fields"])
    assert set(system) == {s.key for s in SYSTEM_FIELDS}
    with pytest.raises(ValueError, match="nicht gelöscht"):
        delete_field(db, system["testzweck.bestaetigt"]["id"])
    assert publish_draft(db, copy["id"])["published_version_no"] == 1


def test_template_with_purpose_can_only_be_archived(world, testzweck):
    db = world["db"]
    never_published = _purpose_template(db, publish=False)
    real = create_template(db, label="Abnahme", contexts=["auftrag"], purpose="abnahme")
    for t in (never_published, real):
        with pytest.raises(ValueError, match="nur archiviert"):
            delete_template(db, t["id"])
        assert set_template_archived(db, t["id"], True)["archived"]
    plain = create_template(db, label="Ohne Zweck", contexts=["auftrag"])
    assert delete_template(db, plain["id"])


# --- Über HTTP ------------------------------------------------------------------------------

def test_purpose_and_system_fields_over_http(world, testzweck, router_test_client):
    client = router_test_client(world["db"], checklist_templates_router, role="buero_auftrag")
    purposes = {p["key"]: p for p in client.get("/api/checklist-purposes").json()}
    assert purposes["abnahme"]["contexts"] == ["auftrag"] and purposes["abnahme"]["system_fields"] == []
    assert [s["key"] for s in purposes[TEST_KEY]["system_fields"]] == [s.key for s in SYSTEM_FIELDS]
    t = client.post("/api/checklist-templates", json={"label": "Über HTTP", "contexts": ["auftrag"],
                                                      "purpose": TEST_KEY}).json()
    system = _system(t["editable_version"]["fields"])
    field_id = system["testzweck.bestaetigt"]["id"]
    assert client.put(f"/api/checklist-template-fields/{field_id}", json={"required": False}).status_code == 400
    assert client.delete(f"/api/checklist-template-fields/{field_id}").status_code == 400
    option_id = system["testzweck.art"]["options"][0]["id"]
    assert client.delete(f"/api/checklist-template-field-options/{option_id}").status_code == 400
    assert client.post(f"/api/checklist-templates/{t['id']}/publish").status_code == 200
    resp = client.put(f"/api/checklist-templates/{t['id']}", json={"label": "Über HTTP", "contexts": ["auftrag"],
                                                                    "purpose": "allgemein"})
    assert resp.status_code == 400 and "festgelegt" in resp.json()["detail"]
    assert client.get(f"/api/checklist-templates/{t['id']}").json()["purpose"] == TEST_KEY
    assert client.delete(f"/api/checklist-templates/{t['id']}").status_code == 400
    assert client.post("/api/checklist-template-versions/999/system-fields").status_code == 404
    draft = client.post(f"/api/checklist-templates/{t['id']}/draft").json()
    assert client.post(f"/api/checklist-template-versions/{draft['draft_version_id']}/system-fields").status_code == 200


# --- Folgen ---------------------------------------------------------------------------------

@pytest.fixture
def purpose_world(world, testzweck):
    world["purpose_tpl"] = _purpose_template(world["db"])
    world["state"] = testzweck
    return world


def _start(world, client):
    resp = client.post("/api/checklists", json={"template_id": world["purpose_tpl"]["id"], "context_type": "auftrag",
                                                "order_id": world["orders"]["mine"].id})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fill_and_complete(client, c):
    f = _fields(c)
    for key, value in (("testzweck.bestaetigt", "ja"), ("testzweck.art", "voll")):
        assert client.put(f"/api/checklists/{c['id']}/answers/{f[key]}", json={"value": value}).status_code == 200
    assert client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["testzweck.fotos"]},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).status_code == 200
    assert client.post(f"/api/checklists/{c['id']}/attachments",
                       data={"field_id": f["testzweck.unterschrift"], "signer_name": "Anna Alpha"},
                       files={"file": ("s.png", _png(), "image/png")}).status_code == 200
    resp = client.post(f"/api/checklists/{c['id']}/complete")
    assert resp.status_code == 200, resp.text
    return resp


def _rows(db):
    db.expire_all()
    return db.scalars(select(ChecklistFollowUp)).all()


def _follow_up_tasks(db):
    return [t for t in db.scalars(select(Task)).all() if t.title.startswith(f"{SECRET} Folge")]


def test_completion_runs_the_follow_up_once(purpose_world, router_test_client):
    db, state = purpose_world["db"], purpose_world["state"]
    field = _client(purpose_world, router_test_client, "a")
    c = _fill_and_complete(field, _start(purpose_world, field)).json()
    [row] = _rows(db)
    assert (row.checklist_id, row.follow_up_key, row.status, row.target_type) == (c["id"], "testzweck.folge",
                                                                                  "erledigt", "task")
    [task] = _follow_up_tasks(db)
    assert row.target_id == task.id and state["calls"] == [c["id"]]

    office = _client(purpose_world, router_test_client, "office")
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 0, "module_off": 0, "failed": 0}
    assert office.post("/api/checklists/run-open-follow-ups").json() == {"done": 0, "module_off": 0, "failed": 0}
    assert field.post(f"/api/checklists/{c['id']}/complete").status_code == 200  # zweiter Abschluss
    assert len(_rows(db)) == 1 and len(_follow_up_tasks(db)) == 1 and state["calls"] == [c["id"]]
    [listed] = office.get(f"/api/checklists/{c['id']}/follow-ups").json()
    assert (listed["label"], listed["status_label"], listed["target_id"]) == ("Testfolge", "erledigt", task.id)


def test_duplicate_follow_up_is_impossible(purpose_world, router_test_client, monkeypatch):
    db, state = purpose_world["db"], purpose_world["state"]
    field = _client(purpose_world, router_test_client, "a")
    c = _fill_and_complete(field, _start(purpose_world, field)).json()
    # Datenbank: eine zweite Zeile für dieselbe (Checkliste, Folge) scheitert am Unique-Constraint.
    db.add(ChecklistFollowUp(checklist_id=c["id"], follow_up_key="testzweck.folge", status="ausstehend"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # Wettlauf: ein zweiter Aufruf hat einen Lesestand von VOR der Belegung -- er darf die Folge
    # nicht noch einmal ausführen.
    monkeypatch.setattr(follow_ups_module, "_existing_rows", lambda _db, _id: {})
    assert follow_ups_module.run_checklist_follow_ups(db, c["id"]) == {"done": 0, "module_off": 0, "failed": 0}
    assert len(_rows(db)) == 1 and len(_follow_up_tasks(db)) == 1 and state["calls"] == [c["id"]]


def test_failing_follow_up_stays_open_and_is_caught_up(purpose_world, router_test_client):
    db, state = purpose_world["db"], purpose_world["state"]
    state["fail"] = 1
    field = _client(purpose_world, router_test_client, "a")
    c = _fill_and_complete(field, _start(purpose_world, field)).json()
    assert c["status"] == "abgeschlossen"  # der Abschluss selbst gilt
    [row] = _rows(db)
    assert (row.status, row.target_id) == ("ausstehend", None) and not _follow_up_tasks(db)
    office = _client(purpose_world, router_test_client, "office")
    assert office.get(f"/api/checklists/{c['id']}/follow-ups").json()[0]["status_label"] == "nicht ausgeführt (unterbrochen)"
    assert office.post("/api/checklists/run-open-follow-ups").json() == {"done": 1, "module_off": 0, "failed": 0}
    [row] = _rows(db)
    [task] = _follow_up_tasks(db)
    assert (row.status, row.target_id) == ("erledigt", task.id) and state["calls"] == [c["id"], c["id"]]
    assert office.post("/api/checklists/run-open-follow-ups").json() == {"done": 0, "module_off": 0, "failed": 0}


def test_follow_up_needing_a_disabled_module_is_caught_up(purpose_world, router_test_client, monkeypatch):
    db, state = purpose_world["db"], purpose_world["state"]
    _register(monkeypatch, state, module="aufgabenmanagement")
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    field = _client(purpose_world, router_test_client, "a")
    c = _fill_and_complete(field, _start(purpose_world, field)).json()
    assert [r.status for r in _rows(db)] == ["modul_aus"] and state["calls"] == []
    office = _client(purpose_world, router_test_client, "office")
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 0, "module_off": 1, "failed": 0}
    db.scalar(select(EnabledModule).where(EnabledModule.module_key == "aufgabenmanagement")).enabled = True
    db.commit()
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 1, "module_off": 0, "failed": 0}
    assert [r.status for r in _rows(db)] == ["erledigt"] and len(_follow_up_tasks(db)) == 1


def test_field_completes_a_purpose_checklist_without_seeing_office_data(purpose_world, router_test_client):
    db = purpose_world["db"]
    field = _client(purpose_world, router_test_client, "a")
    c = _start(purpose_world, field)
    order_id = purpose_world["orders"]["mine"].id
    responses = {"complete": _fill_and_complete(field, c).json()}
    for name, url in (("detail", f"/api/checklists/{c['id']}"),
                      ("startable", "/api/checklists/startable-templates?context=auftrag"),
                      ("list", f"/api/checklists?order_id={order_id}"),
                      ("mine", "/api/checklists/mine?status=abgeschlossen")):
        resp = field.get(url)
        assert resp.status_code == 200, (name, resp.text)
        responses[name] = resp.json()
    for name, body in responses.items():
        leaked = _collect_keys(body, set()) & OFFICE_KEYS
        assert not leaked, (name, leaked)
        assert SECRET not in json.dumps(body, default=str), name
    assert responses["complete"]["purpose"] == TEST_KEY and responses["complete"]["status"] == "abgeschlossen"
    # Gegenprobe, dass der Scan nicht ins Leere geht: das Büro sieht Folge und Regel-Aufgabe.
    office = _client(purpose_world, router_test_client, "office")
    assert office.get(f"/api/checklists/{c['id']}/follow-ups").json()[0]["target_type"] == "task"
    assert any(SECRET in r["task_title"] for r in office.get(f"/api/checklists/{c['id']}/rule-executions").json())
    for method, url in (("GET", f"/api/checklists/{c['id']}/follow-ups"),
                        ("POST", f"/api/checklists/{c['id']}/run-follow-ups"),
                        ("POST", "/api/checklists/run-open-follow-ups")):
        assert field.request(method, url).status_code == 403, url
