"""Version 1.8.38 -- Stufe 2b, Runde 2b-3 Teil 1: Behinderungsanzeige erfassen
(app/checklist_purposes.py, app/checklist_follow_ups.py, app/obstruction_notices.py,
app/checklist_rules.py, Migration *_behinderungsanzeige_startvorlage.py; siehe
docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.38").

Geprüft: Systemfelder in drei Abschnitten und ihr Schutz (feste Eigenschaften, Löschen, Optionen,
Reihenfolge der Abschnitte); Startvorlage aus der Migration besteht die echte
Veröffentlichungsprüfung und ist am Auftrag startbar (Büro und Monteur); die Folge "Aufgabe
Behinderungsanzeige versenden" genau einmal nach der Unterschrift der Meldung -- auch beim
Nachholen, nach Verwerfen und erneuter Unterschrift, nach dem Abschluss; der Monteur erfasst und
unterschreibt die Meldung, füllt den Abschnitt Anzeige nicht und sieht keine Büro-Daten
(Schlüssel-Scan); Tagesbericht "Behinderung = ja" → Aufgabe mit Link zum Anlegen, keine zweite,
solange sie offen ist."""

import importlib.util
import json
import os
import threading
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

import app.checklist_follow_ups as follow_ups_module
import app.checklists as checklists_module
import app.obstruction_notices as obstruction_module
from app.berlin_time import to_berlin
from app.checklist_follow_ups import run_checklist_follow_ups
from app.checklists import add_attachment, complete_checklist, create_checklist, save_answer
from app.checklist_purposes import OBSTRUCTION_SYSTEM_FIELDS, PURPOSES, WEATHER_HINT
from app.checklist_templates import (
    _normalize_field, add_option, add_rule, delete_field, delete_option, get_template, publish_draft, reorder_fields,
    start_draft, update_field, update_option, validate_version_for_publish,
)
from app.database import Base
from app.models import (
    ChecklistAttachment, ChecklistFollowUp, ChecklistRuleExecution, ChecklistTemplate, ChecklistTemplateField,
    ChecklistTemplateRule, ChecklistTemplateVersion, Employee, EnabledModule, Task,
)
from app.orders import create_order_from_quote
from app.routers.pages import router as pages_router
from tests.test_v305_checklist_filling import _client, _fields, _jpeg, _png, world  # noqa: F401 -- Fixture
from tests.test_v325_contract_basis import make_quote

VERSIONS = Path(__file__).resolve().parent.parent.joinpath("alembic", "versions")
B = "behinderungsanzeige."
TASK_TITLE = "Behinderungsanzeige versenden"
# Nur in der Beschreibung der Folge-Aufgabe -- taucht er in einer Monteur-Antwort auf, ist sie durchgesickert.
TASK_TEXT = "als Büro unterschreiben und die Anzeige an den Auftraggeber senden"
# Was ein Monteur nie zu sehen bekommt (wie test_v320, dazu die Felder der Folgen-Liste und Aufgaben).
OFFICE_KEYS = {
    "rules", "rule_executions", "follow_ups", "follow_up_key", "target_type", "target_id", "target_title",
    "trigger_label", "task_id", "task_title", "task_description", "operator", "operand", "assignee_mode",
    "min_visible_role", "system_field_problems", "hourly_wage", "caseworker_employee_id", "assigned_employee_id",
    "link_purpose",
}


def _load(name: str):
    path = next(VERSIONS.glob(f"*_{name}.py"))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIG = _load("behinderungsanzeige_startvorlage")


def _collect_keys(value, keys):
    if isinstance(value, dict):
        for key, inner in value.items():
            keys.add(key)
            _collect_keys(inner, keys)
    elif isinstance(value, list):
        for inner in value:
            _collect_keys(inner, keys)
    return keys


def _template_id(db, label=MIG.LABEL):
    return db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == label))


@pytest.fixture
def bworld(world):
    """world aus test_v305 + Startvorlage aus der Migration (veröffentlicht) + Sachbearbeiterin am Auftrag."""
    db = world["db"]
    assert MIG.insert_obstruction_template(db.connection())
    db.commit()
    world["obstruction_tpl"] = publish_draft(db, _template_id(db))
    world["orders"]["mine"].caseworker_employee_id = world["emps"]["office"].id
    db.commit()
    return world


def _start(world, client, order_key="mine"):
    resp = client.post("/api/checklists", json={"template_id": world["obstruction_tpl"]["id"], "context_type": "auftrag",
                                                "order_id": world["orders"][order_key].id})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _answer(client, c, key, value):
    return client.put(f"/api/checklists/{c['id']}/answers/{_fields(c)[key]}", json={"value": value})


def _sign(client, c, key, name):
    return client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[key], "signer_name": name},
                       files={"file": ("s.png", _png(), "image/png")})


def _report(client, c) -> list:
    """Meldung erfassen und unterschreiben; liefert alle Antworten (für den Schlüssel-Scan)."""
    bodies = []
    for key, value in ((B + "bekannt_seit", "2026-10-02T07:45"), (B + "beschreibung", "Gerüst fehlt an der Nordseite")):
        resp = _answer(client, c, key, value)
        assert resp.status_code == 200, resp.text
        bodies.append(resp.json())
    resp = client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[B + "fotos"]},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")})
    assert resp.status_code == 200, resp.text
    bodies.append(resp.json())
    resp = _sign(client, c, B + "unterschrift_meldung", "Anna Alpha")
    assert resp.status_code == 200, resp.text
    bodies.append(resp.json())
    return bodies


def _notice(client, c) -> None:
    """Abschnitt Anzeige als Büro ausfüllen und unterschreiben."""
    for key, value in ((B + "ursache", "zugang_geruest"), (B + "ursache_beschreibung", "Gerüstbauer nicht erschienen"),
                       (B + "betroffene_leistungen", "Dachdeckung Nordseite"), (B + "beginn", "2026-10-02"),
                       (B + "dauer", "etwa eine Woche")):
        assert _answer(client, c, key, value).status_code == 200, key
    assert _sign(client, c, B + "unterschrift_buero", "Olga Office").status_code == 200


def _send_tasks(db):
    db.expire_all()
    return [t for t in db.scalars(select(Task)).all() if t.title == TASK_TITLE]


def _rows(db):
    db.expire_all()
    return db.scalars(select(ChecklistFollowUp)).all()


# --- Registry -------------------------------------------------------------------------------

def test_registry_three_sections_office_section_weather_hint_and_follow_up():
    purpose = PURPOSES["behinderungsanzeige"]
    assert purpose.contexts == ("auftrag",)
    by_section = {}
    for spec in purpose.system_fields:
        by_section.setdefault(spec.section, []).append(spec)
    assert list(by_section) == ["Meldung", "Anzeige", "Wegfall"]
    # Jeder Abschnitt endet mit seiner Unterschrift, alle drei Pflicht.
    for specs in by_section.values():
        assert specs[-1].field_type == "unterschrift" and specs[-1].required
        assert all(s.field_type != "unterschrift" for s in specs[:-1])
    assert [s.key for s in by_section["Meldung"]] == [B + k for k in ("bekannt_seit", "beschreibung", "fotos",
                                                                       "unterschrift_meldung")]
    assert by_section["Meldung"][0].field_type == "datum_uhrzeit"
    assert all(s.office_only for s in by_section["Anzeige"])
    assert not any(s.office_only for s in by_section["Meldung"] + by_section["Wegfall"])
    ursache = next(s for s in purpose.system_fields if s.key == B + "ursache")
    assert [label for _k, label in ursache.options] == [
        "fehlende Vorleistung eines anderen Gewerks", "fehlende Pläne oder Freigaben", "Zugang oder Gerüst",
        "vom Auftraggeber zu lieferndes Material", "außergewöhnliche Witterung", "Sonstiges"]
    assert dict(ursache.option_hints) == {"witterung": WEATHER_HINT}
    assert WEATHER_HINT == "Übliche Witterung ist nach § 6 Abs. 2 VOB/B keine Behinderung."
    [follow_up] = purpose.follow_ups
    assert (follow_up.after_signature, follow_up.module) == (B + "unterschrift_meldung", "aufgabenmanagement")


# --- Startvorlage aus der Migration ---------------------------------------------------------

def test_starter_template_passes_the_real_publish_check_and_matches_the_registry():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        assert MIG.insert_obstruction_template(conn)
        assert not MIG.insert_obstruction_template(conn)  # keine Dublette
    db = sessionmaker(bind=engine)()
    template = db.get(ChecklistTemplate, _template_id(db))
    [version] = template.versions
    assert (version.status, version.purpose, template.purpose) == ("entwurf", "behinderungsanzeige", "behinderungsanzeige")
    assert (template.context_order, template.context_property, template.context_asset, template.context_company) == (
        True, False, False, False)
    system = [f for f in version.fields if f.is_system]
    assert [f.field_key for f in system] == [s.key for s in OBSTRUCTION_SYSTEM_FIELDS]
    assert [f.group_name for f in system] == [s.section for s in OBSTRUCTION_SYSTEM_FIELDS]
    assert validate_version_for_publish(template, version) == []
    for field in version.fields:  # die echte Normalisierung ändert nichts (sonst still verändert beim Bearbeiten)
        before = {c: getattr(field, c) for c in ("required", "allow_na", "multiline", "multiple", "min_count",
                                                  "max_count", "signer_label", "group_name", "help_text")}
        _normalize_field(field)
        assert {c: getattr(field, c) for c in before} == before, field.field_key
    db.rollback()
    assert publish_draft(db, template.id)["published_version_no"] == 1
    db.close()


def test_published_starter_is_startable_at_the_order_in_the_office_and_in_mobil(bworld, router_test_client):
    tpl_id = bworld["obstruction_tpl"]["id"]
    for who in ("office", "a"):
        client = _client(bworld, router_test_client, who)
        offered = {t["id"]: t for t in client.get("/api/checklists/startable-templates?context=auftrag").json()}
        assert offered[tpl_id]["purpose"] == "behinderungsanzeige", who
        assert tpl_id not in [t["id"] for t in client.get("/api/checklists/startable-templates?context=objekt").json()]
        assert _start(bworld, client)["purpose_label"] == "Behinderungsanzeige"


def test_order_page_link_highlights_the_purpose(bworld, router_test_client):
    client = router_test_client(bworld["db"], pages_router, role="buero_auftrag")
    order_id = bworld["orders"]["mine"].id
    html = client.get(f"/checklisten/auftrag/{order_id}?zweck=behinderungsanzeige").text
    assert 'var zweck="behinderungsanzeige",zweckLabel="Behinderungsanzeige"' in html
    for unknown in ("gibt_es_nicht", "allgemein", ""):
        html = client.get(f"/checklisten/auftrag/{order_id}?zweck={unknown}").text
        assert "var zweck=null,zweckLabel=null" in html, unknown


# --- Systemfelder geschützt -----------------------------------------------------------------

def test_system_fields_are_protected_including_the_order_of_the_sections(bworld):
    db = bworld["db"]
    tpl_id = bworld["obstruction_tpl"]["id"]
    draft = start_draft(db, tpl_id)["editable_version"]
    system = {f["field_key"]: f for f in draft["fields"] if f["is_system"]}
    assert set(system) == {s.key for s in OBSTRUCTION_SYSTEM_FIELDS}
    for key, change in ((B + "bekannt_seit", {"field_type": "datum"}), (B + "beschreibung", {"required": False}),
                        (B + "unterschrift_meldung", {"field_key": "unterschrift"}),
                        (B + "unterschrift_buero", {"required": False}), (B + "fotos", {"min_count": 1}),
                        (B + "ursache", {"multiple": True})):
        with pytest.raises(ValueError, match="eines Systemfelds kann nicht geändert werden"):
            update_field(db, system[key]["id"], change)
    for key in (B + "unterschrift_meldung", B + "ursache", B + "beendet_am"):
        with pytest.raises(ValueError, match="nicht gelöscht"):
            delete_field(db, system[key]["id"])
    witterung = next(o for o in system[B + "ursache"]["options"] if o["option_key"] == "witterung")
    for call in (lambda: add_option(db, system[B + "ursache"]["id"], "Streik"),
                 lambda: update_option(db, witterung["id"], label="Wetter"),
                 lambda: delete_option(db, witterung["id"])):
        with pytest.raises(ValueError, match="fest vorgegeben"):
            call()
    # Frei: Beschriftung und Abschnittsname.
    update_field(db, system[B + "beschreibung"]["id"], {"label": "Was ist passiert?", "group_name": "Meldung vor Ort"})

    ids = [f["id"] for f in draft["fields"]]
    by_key = {f["field_key"]: f["id"] for f in draft["fields"]}
    # Innerhalb eines Abschnitts umsortieren ist erlaubt ...
    within = ids[:]
    a, b = within.index(by_key[B + "beginn"]), within.index(by_key[B + "dauer"])
    within[a], within[b] = within[b], within[a]
    reorder_fields(db, draft["id"], within)
    assert get_template(db, tpl_id)["system_field_problems"] == []
    # ... die Unterschrift des Büros vor die Ursache ziehen nicht: sie versiegelte die Anzeige nicht mehr.
    across = within[:]
    across.remove(by_key[B + "unterschrift_buero"])
    across.insert(across.index(by_key[B + "ursache"]), by_key[B + "unterschrift_buero"])
    reorder_fields(db, draft["id"], across)
    with pytest.raises(ValueError, match="nicht in der vorgegebenen Reihenfolge der Abschnitte"):
        publish_draft(db, tpl_id)
    # Ebenso ein Feld der Meldung unter die Unterschrift der Meldung.
    reorder_fields(db, draft["id"], within)
    late = within[:]
    late.remove(by_key[B + "beschreibung"])
    late.insert(late.index(by_key[B + "unterschrift_meldung"]) + 1, by_key[B + "beschreibung"])
    reorder_fields(db, draft["id"], late)
    assert any("Reihenfolge der Abschnitte" in p for p in get_template(db, tpl_id)["system_field_problems"])
    reorder_fields(db, draft["id"], within)
    assert publish_draft(db, tpl_id)["published_version_no"] == 2


# --- Folge nach der Unterschrift der Meldung ------------------------------------------------

def test_send_task_exactly_once_after_the_report_signature(bworld, router_test_client):
    db = bworld["db"]
    field = _client(bworld, router_test_client, "a")
    office = _client(bworld, router_test_client, "office")
    c = _start(bworld, field)
    for key, value in ((B + "bekannt_seit", "2026-10-02T07:45"), (B + "beschreibung", "Gerüst fehlt")):
        assert _answer(field, c, key, value).status_code == 200
    assert _send_tasks(db) == [] and _rows(db) == []  # vor der Unterschrift nichts -- auch nicht per Nachholen
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 0, "module_off": 0, "failed": 0}
    assert _send_tasks(db) == [] and _rows(db) == []
    assert _sign(field, c, B + "unterschrift_meldung", "Anna Alpha").status_code == 200

    [task] = _send_tasks(db)
    signature = db.scalar(select(ChecklistAttachment).where(ChecklistAttachment.checklist_id == c["id"]))
    order = bworld["orders"]["mine"]
    assert task.due_date == to_berlin(signature.created_at).date()  # fällig am Tag der Unterschrift
    assert (task.assigned_employee_id, task.priority, task.project_id) == (bworld["emps"]["office"].id, "hoch",
                                                                           order.project_id)
    assert (task.source_module, task.source_url) == ("checklisten", f"/checklisten/{c['id']}")
    assert task.source_label == "Behinderungsanzeige – Auftrag AU-2026-0001"
    assert "Anna Alpha" in task.description and TASK_TEXT in task.description
    [row] = _rows(db)
    assert (row.status, row.target_type, row.target_id) == ("erledigt", "task", task.id)
    [listed] = office.get(f"/api/checklists/{c['id']}/follow-ups").json()
    assert listed["target_title"] == TASK_TITLE
    assert listed["trigger_label"] == "nach der Unterschrift „Unterschrift des Meldenden“"

    # Nachholen, Büro-Unterschrift, Wegfall, Abschluss, zweiter Abschluss: keine zweite Aufgabe.
    zero = {"done": 0, "module_off": 0, "failed": 0}
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == zero
    assert office.post("/api/checklists/run-open-follow-ups").json() == zero
    _notice(office, c)
    for key, value in ((B + "beendet_am", "2026-10-06"), (B + "wieder_aufgenommen_am", "2026-10-07")):
        assert _answer(field, c, key, value).status_code == 200
    assert _sign(field, c, B + "unterschrift_wegfall", "Anna Alpha").status_code == 200
    assert field.post(f"/api/checklists/{c['id']}/complete").json()["status"] == "abgeschlossen"
    assert field.post(f"/api/checklists/{c['id']}/complete").status_code == 200
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == zero
    assert len(_send_tasks(db)) == 1 and len(_rows(db)) == 1


def test_without_caseworker_the_task_has_no_assignee(bworld, router_test_client):
    db = bworld["db"]
    bworld["orders"]["mine"].caseworker_employee_id = None
    db.commit()
    field = _client(bworld, router_test_client, "a")
    _report(field, _start(bworld, field))
    [task] = _send_tasks(db)
    assert (task.assigned_employee_id, task.min_visible_role) == (None, "buero_auftrag")


def test_caught_up_exactly_once_when_the_task_module_was_off(bworld, router_test_client):
    db = bworld["db"]
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    field = _client(bworld, router_test_client, "a")
    office = _client(bworld, router_test_client, "office")
    c = _start(bworld, field)
    _report(field, c)
    assert [r.status for r in _rows(db)] == ["modul_aus"] and _send_tasks(db) == []
    # Die Übersicht nennt die Checkliste (Entwurf!) als offen, Nachholen bei weiterhin aus: nichts.
    assert [x["id"] for x in office.get("/api/checklists?open_rules=true").json()] == [c["id"]]
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 0, "module_off": 1, "failed": 0}
    db.scalar(select(EnabledModule).where(EnabledModule.module_key == "aufgabenmanagement")).enabled = True
    db.commit()
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 1, "module_off": 0, "failed": 0}
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 0, "module_off": 0, "failed": 0}
    assert office.post("/api/checklists/run-open-follow-ups").json() == {"done": 0, "module_off": 0, "failed": 0}
    assert office.get("/api/checklists?open_rules=true").json() == []
    assert len(_send_tasks(db)) == 1 and [r.status for r in _rows(db)] == ["erledigt"]


def test_repeating_the_same_signature_catches_up_the_follow_up_once(bworld, router_test_client):
    """Stufe-3-Vorbereitung: dieselbe client_uuid noch einmal (das Gerät wiederholt, weil die Antwort
    ausblieb) legt keine zweite Unterschrift an, holt aber eine offene Folge nach -- genau einmal."""
    db = bworld["db"]
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    field = _client(bworld, router_test_client, "a")
    c = _start(bworld, field)
    for key, value in ((B + "bekannt_seit", "2026-10-02T07:45"), (B + "beschreibung", "Gerüst fehlt")):
        assert _answer(field, c, key, value).status_code == 200

    def sign_again():
        return field.post(f"/api/checklists/{c['id']}/attachments",
                          data={"field_id": _fields(c)[B + "unterschrift_meldung"], "signer_name": "Anna Alpha",
                                "client_uuid": "11111111-2222-4333-8444-555555555555"},
                          files={"file": ("s.png", _png(), "image/png")})

    assert sign_again().status_code == 200
    assert [r.status for r in _rows(db)] == ["modul_aus"] and _send_tasks(db) == []
    db.scalar(select(EnabledModule).where(EnabledModule.module_key == "aufgabenmanagement")).enabled = True
    db.commit()
    for _ in range(2):
        resp = sign_again()
        assert resp.status_code == 200, resp.text
        assert len([a for a in resp.json()["attachments"] if a["kind"] == "unterschrift"]) == 1
    assert len(_send_tasks(db)) == 1 and [r.status for r in _rows(db)] == ["erledigt"]


def test_failing_handler_stays_open_and_is_caught_up_once(bworld, router_test_client, monkeypatch):
    db = bworld["db"]
    real = obstruction_module.create_send_task
    calls = []

    def flaky(db_, checklist):
        calls.append(checklist.id)
        if len(calls) == 1:
            raise RuntimeError("Testfehler")
        return real(db_, checklist)

    monkeypatch.setattr(obstruction_module, "create_send_task", flaky)
    field = _client(bworld, router_test_client, "a")
    c = _start(bworld, field)
    bodies = _report(field, c)
    assert bodies[-1]["signed"]  # die Unterschrift gilt trotz des Fehlers
    assert [r.status for r in _rows(db)] == ["ausstehend"] and _send_tasks(db) == []
    office = _client(bworld, router_test_client, "office")
    assert office.post("/api/checklists/run-open-follow-ups").json() == {"done": 1, "module_off": 0, "failed": 0}
    assert office.post("/api/checklists/run-open-follow-ups").json() == {"done": 0, "module_off": 0, "failed": 0}
    assert len(_send_tasks(db)) == 1 and len(calls) == 2


def test_discarded_and_signed_again_does_not_trigger_twice(bworld, router_test_client):
    db = bworld["db"]
    field = _client(bworld, router_test_client, "a")
    office = _client(bworld, router_test_client, "office")
    c = _start(bworld, field)
    signed = _report(field, c)[-1]
    sig_id = next(a["id"] for a in signed["attachments"] if a["kind"] == "unterschrift")
    resp = office.post(f"/api/checklists/{c['id']}/discard-signatures",
                       json={"signature_id": sig_id, "reason": "Beschreibung unvollständig"})
    assert resp.status_code == 200, resp.text
    assert _answer(field, c, B + "beschreibung", "Gerüst fehlt an Nord- und Ostseite").status_code == 200
    assert _sign(field, c, B + "unterschrift_meldung", "Anna Alpha").status_code == 200
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json()["done"] == 0
    assert len(_send_tasks(db)) == 1 and len(_rows(db)) == 1


# --- Monteur: Meldung ja, Anzeige nein, keine Büro-Daten ------------------------------------

def test_field_reports_and_signs_but_neither_fills_the_notice_nor_sees_office_data(bworld, router_test_client):
    db = bworld["db"]
    field = _client(bworld, router_test_client, "a")
    office = _client(bworld, router_test_client, "office")
    responses = {"create": _start(bworld, field)}
    c = responses["create"]
    assert not c["can_fill_office_fields"] and c["can_edit"]
    flags = {f["field_key"]: f["office_only"] for f in c["fields"]}
    assert [k for k, v in flags.items() if v] == [s.key for s in OBSTRUCTION_SYSTEM_FIELDS if s.office_only]
    for i, body in enumerate(_report(field, c)):
        responses[f"report{i}"] = body
    assert responses["report3"]["signed"] and len(_send_tasks(db)) == 1  # die Folge lief -- während der Monteur zusah

    # Abschnitt Anzeige samt "Unterschrift Büro": 403, auch an der eigenen Checkliste.
    for key, value in ((B + "ursache", "zugang_geruest"), (B + "betroffene_leistungen", "Dach"), (B + "beginn", "2026-10-02")):
        resp = _answer(field, c, key, value)
        assert resp.status_code == 403 and resp.json()["detail"] == "Dieses Feld füllt das Büro aus.", key
    assert _sign(field, c, B + "unterschrift_buero", "Anna Alpha").status_code == 403
    # Wegfall darf er (Monteur oder Büro).
    assert _answer(field, c, B + "beendet_am", "2026-10-06").status_code == 200

    order_id = bworld["orders"]["mine"].id
    for name, url in (("detail", f"/api/checklists/{c['id']}"),
                      ("startable", "/api/checklists/startable-templates?context=auftrag"),
                      ("list", f"/api/checklists?order_id={order_id}"),
                      ("mine", "/api/checklists/mine")):
        resp = field.get(url)
        assert resp.status_code == 200, (name, resp.text)
        responses[name] = resp.json()
    for name, body in responses.items():
        leaked = _collect_keys(body, set()) & OFFICE_KEYS
        assert not leaked, (name, leaked)
        dumped = json.dumps(body, default=str, ensure_ascii=False)
        assert TASK_TEXT not in dumped and "Olga Office" not in dumped, name
    for method, url in (("GET", f"/api/checklists/{c['id']}/follow-ups"),
                        ("POST", f"/api/checklists/{c['id']}/run-follow-ups"),
                        ("POST", "/api/checklists/run-open-follow-ups"),
                        ("GET", f"/api/checklists/{c['id']}/rule-executions"),
                        ("GET", "/api/checklists?open_rules=true")):
        assert field.request(method, url).status_code == 403, url
    # Gegenprobe, dass der Scan nicht ins Leere geht: das Büro sieht Folge, Ziel und Aufgabe.
    [row] = office.get(f"/api/checklists/{c['id']}/follow-ups").json()
    assert row["target_type"] == "task" and row["target_title"] == TASK_TITLE
    detail = office.get(f"/api/checklists/{c['id']}").json()
    assert detail["can_fill_office_fields"]
    _notice(office, c)  # und das Büro füllt die Anzeige
    assert office.get(f"/api/checklists/{c['id']}").json()["signed"]


def test_weather_hint_is_delivered_with_the_cause_field(bworld, router_test_client):
    office = _client(bworld, router_test_client, "office")
    c = _start(bworld, office)
    ursache = next(f for f in c["fields"] if f["field_key"] == B + "ursache")
    assert ursache["option_hints"] == {"witterung": WEATHER_HINT} and ursache["office_only"]
    assert _answer(office, c, B + "ursache", "witterung").status_code == 200
    assert all(f["option_hints"] == {} for f in c["fields"] if f["field_key"] != B + "ursache")


# --- Tagesbericht: Regel mit Link, keine doppelten Aufgaben ---------------------------------

@pytest.fixture
def daily(bworld):
    db = bworld["db"]
    old = _load("checklisten_startvorlagen")
    assert "Tagesbericht" in old.insert_starter_templates(db.connection())
    assert MIG.link_daily_report_rule(db.connection())
    db.commit()
    bworld["daily_tpl"] = publish_draft(db, _template_id(db, "Tagesbericht"))
    return bworld


def _daily_report(world, client, obstruction="ja"):
    resp = client.post("/api/checklists", json={"template_id": world["daily_tpl"]["id"], "context_type": "auftrag",
                                                "order_id": world["orders"]["mine"].id})
    assert resp.status_code == 200, resp.text
    c = resp.json()
    for key, value in (("datum", "2026-10-02"), ("arbeiten", "Dachdeckung"), ("behinderung", obstruction)):
        assert _answer(client, c, key, value).status_code == 200, key
    resp = client.post(f"/api/checklists/{c['id']}/complete")
    assert resp.status_code == 200, resp.text
    return c


def _create_tasks(db):
    db.expire_all()
    return [t for t in db.scalars(select(Task)).all() if t.title.startswith("Behinderungsanzeige anlegen")]


def test_daily_report_obstruction_creates_one_task_linking_to_the_notice(daily, router_test_client):
    db = daily["db"]
    field = _client(daily, router_test_client, "a")
    office = _client(daily, router_test_client, "office")
    order_id = daily["orders"]["mine"].id
    rule = db.scalar(select(ChecklistTemplateRule).where(ChecklistTemplateRule.version_id
                                                         == daily["daily_tpl"]["published_version_id"],
                                                         ChecklistTemplateRule.field_key == "behinderung"))
    assert (rule.link_purpose, rule.task_title) == ("behinderungsanzeige", "Behinderungsanzeige anlegen: {kontext}")

    first = _daily_report(daily, field)
    [task] = _create_tasks(db)
    assert task.title == "Behinderungsanzeige anlegen: Auftrag AU-2026-0001"
    assert task.source_url == f"/checklisten/auftrag/{order_id}?zweck=behinderungsanzeige"
    assert task.source_label == "Behinderungsanzeige anlegen – Auftrag AU-2026-0001"
    assert task.assigned_employee_id == daily["emps"]["office"].id
    assert f"/checklisten/{first['id']}" in task.description  # die auslösende Checkliste steht in der Beschreibung
    assert len([t for t in db.scalars(select(Task)).all() if t.source_url == f"/checklisten/{first['id']}"]) == 0

    # Zweiter Tagesbericht mit "ja", solange die Aufgabe offen ist: keine zweite.
    second = _daily_report(daily, field)
    assert len(_create_tasks(db)) == 1
    execution = db.scalar(select(ChecklistRuleExecution).where(ChecklistRuleExecution.checklist_id == second["id"]))
    assert (execution.status, execution.task_id) == ("aufgabe_vorhanden", task.id)
    listed = office.get(f"/api/checklists/{second['id']}/rule-executions").json()
    assert [r["status_label"] for r in listed] == ["Aufgabe war schon offen"]
    assert office.post(f"/api/checklists/{second['id']}/run-rules").json() == {"created": 0, "module_off": 0}
    assert office.get("/api/checklists?open_rules=true").json() == []  # nichts nachzuholen

    # "nein": keine Aufgabe. Erledigt: der nächste Tagesbericht mit "ja" legt wieder eine an.
    _daily_report(daily, field, obstruction="nein")
    assert len(_create_tasks(db)) == 1
    task.status = "erledigt"
    db.commit()
    # "Aufgabe war schon offen" ist erledigt, nicht offen: auch jetzt kein Nachholen für den zweiten Bericht.
    assert office.post(f"/api/checklists/{second['id']}/run-rules").json() == {"created": 0, "module_off": 0}
    assert len(_create_tasks(db)) == 1
    _daily_report(daily, field)
    assert len(_create_tasks(db)) == 2


def test_rule_link_purpose_is_validated_and_copied(daily):
    db = daily["db"]
    draft = start_draft(db, daily["daily_tpl"]["id"])["editable_version"]
    [linked] = [r for r in draft["rules"] if r["field_key"] == "behinderung"]
    assert linked["link_purpose"] == "behinderungsanzeige"  # neuer Entwurf übernimmt den Link
    for bad in ("gibt_es_nicht", "allgemein"):
        with pytest.raises(ValueError, match="Unbekannter Zweck für den Link"):
            add_rule(db, draft["id"], {"operator": "immer", "task_title": "x", "link_purpose": bad})
    version = add_rule(db, draft["id"], {"operator": "immer", "task_title": "Leer", "link_purpose": ""})
    assert [r["link_purpose"] for r in version["rules"] if r["task_title"] == "Leer"] == [None]


# --- PostgreSQL (opt-in) --------------------------------------------------------------------

PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.mark.skipif(not PG_TEST_DATABASE_URL, reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
def test_postgresql_concurrent_catch_up_and_daily_report_query(tmp_path, monkeypatch):
    """Zwei gleichzeitige "Nachholen" einer offenen Folge legen genau eine Aufgabe an; die Abfrage
    nach einer offenen Aufgabe mit demselben Link (Tagesbericht) läuft unter PostgreSQL."""
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    schema = f"pgtest_behinderung_{uuid.uuid4().hex[:8]}"
    admin_engine = create_engine(PG_TEST_DATABASE_URL)
    with admin_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        monteur = Employee(first_name="Anna", last_name="Alpha", employee_group="angestellt", active=True)
        office = Employee(first_name="Olga", last_name="Office", employee_group="angestellt", active=True)
        db.add_all([monteur, office])
        db.commit()
        order = create_order_from_quote(db, make_quote(db, number="PG1").id, order_date=date(2026, 10, 1),
                                        execution_start=None, execution_end=None, caseworker_employee_id=office.id,
                                        project_manager_employee_id=None, payment_terms=None, remarks=None)
        old = _load("checklisten_startvorlagen")
        old.insert_starter_templates(db.connection())
        MIG.insert_obstruction_template(db.connection())
        MIG.link_daily_report_rule(db.connection())
        db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
        db.commit()
        notice_tpl = publish_draft(db, _template_id(db))["id"]
        daily_tpl = publish_draft(db, _template_id(db, "Tagesbericht"))["id"]
        order_id, monteur_id = order.id, monteur.id

        c = create_checklist(db, template_id=notice_tpl, context_type="auftrag", order_id=order_id,
                             created_by_employee_id=monteur_id)
        fields = _fields(c)
        save_answer(db, c["id"], fields[B + "bekannt_seit"], "2026-10-02T07:45")
        save_answer(db, c["id"], fields[B + "beschreibung"], "Gerüst fehlt")
        add_attachment(db, c["id"], fields[B + "unterschrift_meldung"], _png(), signer_name="Anna Alpha",
                       created_by_employee_id=monteur_id)
        assert [r.status for r in _rows(db)] == ["modul_aus"]
        db.scalar(select(EnabledModule)).enabled = True
        db.commit()
        db.close()

        # Beide lesen die offene Zeile, BEVOR einer sie belegt -- erst dann zählt die bedingte Belegung.
        barrier = threading.Barrier(2)
        results = []
        read_rows = follow_ups_module._existing_rows

        def read_then_wait(session, checklist_id):
            rows = read_rows(session, checklist_id)
            barrier.wait(timeout=20)
            return rows

        monkeypatch.setattr(follow_ups_module, "_existing_rows", read_then_wait)

        def worker():
            session = Session()
            try:
                results.append(run_checklist_follow_ups(session, c["id"])["done"])
            finally:
                session.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert sorted(results) == [0, 1], results
        check = Session()
        assert len(_send_tasks(check)) == 1 and [r.status for r in _rows(check)] == ["erledigt"]

        for _ in range(2):  # zwei Tagesberichte "Behinderung = ja": eine Aufgabe
            d = create_checklist(check, template_id=daily_tpl, context_type="auftrag", order_id=order_id,
                                 created_by_employee_id=monteur_id)
            f = _fields(d)
            for key, value in (("datum", "2026-10-02"), ("arbeiten", "Dachdeckung"), ("behinderung", "ja")):
                save_answer(check, d["id"], f[key], value)
            complete_checklist(check, d["id"], completed_by_employee_id=monteur_id)
        assert len(_create_tasks(check)) == 1
        assert sorted(e.status for e in check.scalars(select(ChecklistRuleExecution)).all()) == [
            "aufgabe_angelegt", "aufgabe_vorhanden"]
        check.close()
    finally:
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin_engine.dispose()


# --- Migration ------------------------------------------------------------------------------

def test_migration_links_only_an_unchanged_daily_report_and_removes_only_an_unused_draft(threaded_db_session):
    db = threaded_db_session
    old = _load("checklisten_startvorlagen")

    def run(fn):
        result = fn(db.connection())
        db.commit()
        return result

    run(old.insert_starter_templates)
    assert run(MIG.insert_obstruction_template)
    assert run(MIG.link_daily_report_rule) and not run(MIG.link_daily_report_rule)
    assert run(MIG.unlink_daily_report_rule) and not run(MIG.unlink_daily_report_rule)
    db.expire_all()
    rule = db.scalar(select(ChecklistTemplateRule).where(ChecklistTemplateRule.field_key == "behinderung"))
    assert (rule.task_title, rule.link_purpose) == ("Behinderung gemeldet: {kontext}", None)
    # Vom Büro geänderter Titel: bleibt unangetastet.
    rule.task_title = "Eigener Titel"
    db.commit()
    assert not run(MIG.link_daily_report_rule)
    rule.task_title = "Behinderung gemeldet: {kontext}"
    db.commit()
    # Veröffentlichter Tagesbericht: eingefroren, unangetastet.
    publish_draft(db, _template_id(db, "Tagesbericht"))
    assert not run(MIG.link_daily_report_rule)
    # Startvorlage: veröffentlicht → bleibt; als unbenutzter Entwurf → entfernt.
    tpl_id = _template_id(db)
    publish_draft(db, tpl_id)
    assert not run(MIG.remove_obstruction_template)
    version = db.scalar(select(ChecklistTemplateVersion).where(ChecklistTemplateVersion.template_id == tpl_id))
    version.status = "entwurf"
    version_id = version.id
    db.commit()
    assert run(MIG.remove_obstruction_template)
    db.expire_all()
    assert _template_id(db) is None
    assert db.scalars(select(ChecklistTemplateField).where(ChecklistTemplateField.version_id == version_id)).all() == []
