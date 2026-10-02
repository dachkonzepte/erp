"""Version 1.8.43 -- Stufe 2b, Runde 2b-4 Teil 1: Bedenkenanzeige erfassen (Punkte 1–3 und ihre Tests aus Punkt 6).

Punkt 1: Zweck "bedenkenanzeige" mit Systemfeldern in drei Abschnitten -- Meldung (bekannt seit, Beschreibung, Fotos,
Unterschrift des Meldenden), Anzeige nur Büro (Bedenken gegen, Begründung, mögliche Folgen, Vorschlag zur Abhilfe,
Entscheidung erbeten bis, Unterschrift Büro), Entscheidung des Auftraggebers nur Büro (eingegangen am, Entscheidung,
Antwort als Beleg, Notiz, Unterschrift). Punkt 2: Startvorlage als Entwurf; Folgen nach der Meldung "Bedenkenanzeige
versenden", nach dem Versand "Antwort des Auftraggebers prüfen" (fällig am Datum "Entscheidung erbeten bis"), nach der
Unterschrift der Entscheidung diese Aufgabe erledigt. Punkt 3: solange eine Bedenkenanzeige ohne Entscheidung offen ist,
zeigen Auftrag und /mobil den Hinweis "Offene Bedenken …". Herleitung: docs/archiv/vertragsgrundlage-und-vertrag.md,
"Umsetzung 1.8.43". Brief und Versand (Punkt 4) folgen in 1.8.44 -- bis dahin stellt dieser Test den Versand als
Protokolleintrag nach, wie ihn der Brief hinterlassen wird.
"""
import importlib.util
import json
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.berlin_time import berlin_today, to_berlin
from app.checklist_purposes import CONCERN_SYSTEM_FIELDS, PURPOSES
from app.checklist_templates import (
    _normalize_field, add_option, delete_field, delete_option, get_template, publish_draft, reorder_fields, start_draft,
    update_field, update_option, validate_version_for_publish,
)
from app.concern_notices import OPEN_CONCERNS_TEXT, open_concerns
from app.database import Base
from app.models import (
    ChecklistAttachment, ChecklistFollowUp, ChecklistTemplate, EmailDispatch, EnabledModule, PlanningSlot, Task,
    TaskColumn, Team, WorkPreparationTeamAssignment,
)
from app.routers.field_view import router as field_view_router
from app.routers.pages import router as pages_router
from tests.grunddaten_schalter import ohne_grunddaten
from tests.test_v305_checklist_filling import _client, _fields, _jpeg, _png, world  # noqa: F401 -- Fixture
from tests.uhr import uhr_festhalten

VERSIONS = Path(__file__).resolve().parent.parent.joinpath("alembic", "versions")
K = "bedenkenanzeige."
SEND_TITLE = "Bedenkenanzeige versenden"
ANSWER_TITLE = "Antwort des Auftraggebers prüfen"
# Nur in den Beschreibungen der Folge-Aufgaben -- taucht einer in einer Monteur-Antwort auf, ist er durchgesickert.
TASK_TEXTS = ("als Büro unterschreiben und die Anzeige an den Auftraggeber senden", "Abschnitt „Entscheidung“ festhalten")
OFFICE_KEYS = {
    "rules", "rule_executions", "follow_ups", "follow_up_key", "target_type", "target_id", "target_title",
    "trigger_label", "task_id", "task_title", "task_description", "min_visible_role", "system_field_problems",
    "caseworker_employee_id", "assigned_employee_id",
}


def _load(name: str):
    path = next(VERSIONS.glob(f"*_{name}.py"))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIG = _load("bedenkenanzeige_startvorlage")
BELEG_MIG = _load("bedenkenanzeige_antwort_als_beleg")  # seit 1.8.45: "Antwort als Beleg" wird ein Belegfeld


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
def kworld(world):
    """world aus test_v305 + Startvorlage aus den Migrationen (veröffentlicht) + Sachbearbeiterin am Auftrag."""
    db = world["db"]
    assert MIG.insert_concern_template(db.connection())
    assert BELEG_MIG.answer_as_beleg(db.connection())
    db.commit()
    world["concern_tpl"] = publish_draft(db, _template_id(db))
    world["orders"]["mine"].caseworker_employee_id = world["emps"]["office"].id
    db.commit()
    return world


def _start(world, client, order_key="mine"):
    resp = client.post("/api/checklists", json={"template_id": world["concern_tpl"]["id"], "context_type": "auftrag",
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
    for key, value in ((K + "bekannt_seit", "2026-10-02T07:45"),
                       (K + "beschreibung", "Gelieferte Dämmplatten sind nass")):
        resp = _answer(client, c, key, value)
        assert resp.status_code == 200, resp.text
        bodies.append(resp.json())
    resp = client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[K + "fotos"]},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")})
    assert resp.status_code == 200, resp.text
    bodies.append(resp.json())
    resp = _sign(client, c, K + "unterschrift_meldung", "Anna Alpha")
    assert resp.status_code == 200, resp.text
    bodies.append(resp.json())
    return bodies


def _notice(client, c, deadline="2026-10-09") -> None:
    """Abschnitt Anzeige als Büro ausfüllen und unterschreiben."""
    for key, value in ((K + "bedenken_gegen", ["stoffe_bauteile", "art_der_ausfuehrung"]),
                       (K + "begruendung", "Durchfeuchtete Dämmung verliert ihre Wirkung"),
                       (K + "moegliche_folgen", "Tauwasser, Schimmel, Mängelansprüche"),
                       (K + "vorschlag_abhilfe", "Neue, trockene Platten liefern"), (K + "entscheidung_bis", deadline)):
        resp = _answer(client, c, key, value)
        assert resp.status_code == 200, (key, resp.text)
    assert _sign(client, c, K + "unterschrift_buero", "Olga Office").status_code == 200


def _decide(client, c, decision="bedenken_gefolgt") -> None:
    for key, value in ((K + "eingegangen_am", "2026-10-05"), (K + "entscheidung", decision),
                       (K + "notiz", "Telefonisch bestätigt, schriftlich folgt")):
        assert _answer(client, c, key, value).status_code == 200, key
    resp = client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[K + "antwort_beleg"]},
                       files={"file": ("antwort.jpg", _jpeg(), "image/jpeg")})
    assert resp.status_code == 200, resp.text
    assert _sign(client, c, K + "unterschrift_entscheidung", "Olga Office").status_code == 200


def _delivered(db, checklist_id) -> None:
    """Stellt den Versand der Bedenkenanzeige nach, wie ihn der Brief ab 1.8.44 hinterlässt: ein gesendeter
    Protokolleintrag der Art "bedenkenanzeige" zur Checkliste."""
    db.add(EmailDispatch(dispatch_key=f"bedenkenanzeige-{uuid.uuid4().hex}", message_ref=str(uuid.uuid4()),
                         status="gesendet", channel="smtp", document_type="bedenkenanzeige", document_id=checklist_id,
                         to_recipients="kunde@example.org", subject="Bedenkenanzeige"))
    db.commit()


def _tasks(db, title):
    db.expire_all()
    return [t for t in db.scalars(select(Task)).all() if t.title == title]


def _rows(db):
    db.expire_all()
    return {r.follow_up_key: r for r in db.scalars(select(ChecklistFollowUp)).all()}


def _done(db, task) -> bool:
    done = {c.key for c in db.scalars(select(TaskColumn)).all() if c.is_done}
    return task.status in done


# --- Registry -------------------------------------------------------------------------------

def test_registry_three_sections_office_sections_and_three_follow_ups():
    purpose = PURPOSES["bedenkenanzeige"]
    assert (purpose.contexts, purpose.voidable) == (("auftrag",), True)
    by_section = {}
    for spec in purpose.system_fields:
        by_section.setdefault(spec.section, []).append(spec)
    assert list(by_section) == ["Meldung", "Anzeige", "Entscheidung"]
    for specs in by_section.values():  # jeder Abschnitt endet mit seiner Unterschrift, alle drei Pflicht
        assert specs[-1].field_type == "unterschrift" and specs[-1].required
        assert all(s.field_type != "unterschrift" for s in specs[:-1])
    assert [s.key for s in by_section["Meldung"]] == [K + k for k in ("bekannt_seit", "beschreibung", "fotos",
                                                                       "unterschrift_meldung")]
    assert [s.key for s in by_section["Anzeige"]] == [K + k for k in (
        "bedenken_gegen", "begruendung", "moegliche_folgen", "vorschlag_abhilfe", "entscheidung_bis", "unterschrift_buero")]
    assert [s.key for s in by_section["Entscheidung"]] == [K + k for k in (
        "eingegangen_am", "entscheidung", "antwort_beleg", "notiz", "unterschrift_entscheidung")]
    assert not any(s.office_only for s in by_section["Meldung"])
    assert all(s.office_only for s in by_section["Anzeige"] + by_section["Entscheidung"])
    spec = {s.key: s for s in purpose.system_fields}
    assert [label for _k, label in spec[K + "bedenken_gegen"].options] == [
        "vorgesehene Art der Ausführung", "vom Auftraggeber gelieferte Stoffe oder Bauteile",
        "Leistungen anderer Unternehmer"]
    assert spec[K + "bedenken_gegen"].multiple
    assert [label for _k, label in spec[K + "entscheidung"].options] == [
        "Bedenken gefolgt", "Ausführung trotz Bedenken angeordnet", "keine Antwort", "Sonstiges"]
    assert spec[K + "entscheidung_bis"].field_type == "datum" and spec[K + "entscheidung_bis"].required
    assert not spec[K + "vorschlag_abhilfe"].required and spec[K + "antwort_beleg"].field_type == "beleg"  # 1.8.45
    triggers = [(f.key, f.after_signature, f.after_letter, f.module) for f in purpose.follow_ups]
    assert triggers == [
        (K + "versenden", K + "unterschrift_meldung", None, "aufgabenmanagement"),
        (K + "antwort_pruefen", None, "bedenkenanzeige", "aufgabenmanagement"),
        (K + "entscheidung", K + "unterschrift_entscheidung", None, "aufgabenmanagement"),
    ]


# --- Startvorlage aus der Migration ---------------------------------------------------------

def test_starter_template_passes_the_real_publish_check_and_matches_the_registry():
    engine = create_engine("sqlite:///:memory:")
    with ohne_grunddaten():
        Base.metadata.create_all(engine)
    with engine.begin() as conn:
        assert MIG.insert_concern_template(conn)
        assert not MIG.insert_concern_template(conn)  # keine Dublette
        # 1.8.45: die Startvorlage aus 1.8.43 hat noch ein Fotofeld, die Folgemigration macht daraus ein Belegfeld
        assert BELEG_MIG.answer_as_beleg(conn)
    db = sessionmaker(bind=engine)()
    template = db.get(ChecklistTemplate, _template_id(db))
    [version] = template.versions
    assert (version.status, version.purpose, template.purpose) == ("entwurf", "bedenkenanzeige", "bedenkenanzeige")
    assert (template.context_order, template.context_property, template.context_asset, template.context_company) == (
        True, False, False, False)
    system = [f for f in version.fields if f.is_system]
    assert [f.field_key for f in system] == [s.key for s in CONCERN_SYSTEM_FIELDS]
    assert [f.group_name for f in system] == [s.section for s in CONCERN_SYSTEM_FIELDS]
    assert validate_version_for_publish(template, version) == []
    for field in version.fields:  # die echte Normalisierung ändert nichts (sonst still verändert beim Bearbeiten)
        before = {c: getattr(field, c) for c in ("required", "allow_na", "multiline", "multiple", "min_count",
                                                  "max_count", "signer_label", "group_name", "help_text")}
        _normalize_field(field)
        assert {c: getattr(field, c) for c in before} == before, field.field_key
    db.rollback()
    assert publish_draft(db, template.id)["published_version_no"] == 1
    db.close()


def test_migration_removes_only_an_unused_draft(threaded_db_session):
    db = threaded_db_session
    conn = db.connection()
    assert MIG.insert_concern_template(conn) and MIG.remove_concern_template(conn)
    assert _template_id(db) is None
    assert MIG.insert_concern_template(conn) and BELEG_MIG.answer_as_beleg(conn)  # Kette bis 1.8.45
    db.commit()
    publish_draft(db, _template_id(db))
    assert not MIG.remove_concern_template(db.connection())  # veröffentlicht: bleibt
    assert _template_id(db) is not None


def test_published_starter_is_startable_at_the_order_in_the_office_and_in_mobil(kworld, router_test_client):
    tpl_id = kworld["concern_tpl"]["id"]
    for who in ("office", "a"):
        client = _client(kworld, router_test_client, who)
        offered = {t["id"]: t for t in client.get("/api/checklists/startable-templates?context=auftrag").json()}
        assert offered[tpl_id]["purpose"] == "bedenkenanzeige", who
        assert _start(kworld, client)["purpose_label"] == "Bedenkenanzeige"


# --- Systemfelder geschützt -----------------------------------------------------------------

def test_system_fields_are_protected_including_the_order_of_the_sections(kworld):
    db = kworld["db"]
    tpl_id = kworld["concern_tpl"]["id"]
    draft = start_draft(db, tpl_id)["editable_version"]
    system = {f["field_key"]: f for f in draft["fields"] if f["is_system"]}
    assert set(system) == {s.key for s in CONCERN_SYSTEM_FIELDS}
    for key, change in ((K + "bekannt_seit", {"field_type": "datum"}), (K + "begruendung", {"required": False}),
                        (K + "entscheidung_bis", {"required": False}), (K + "bedenken_gegen", {"multiple": False}),
                        (K + "entscheidung", {"multiple": True}), (K + "unterschrift_entscheidung", {"required": False}),
                        (K + "unterschrift_buero", {"field_key": "unterschrift"})):
        with pytest.raises(ValueError, match="eines Systemfelds kann nicht geändert werden"):
            update_field(db, system[key]["id"], change)
    for key in (K + "unterschrift_meldung", K + "entscheidung", K + "antwort_beleg", K + "notiz"):
        with pytest.raises(ValueError, match="nicht gelöscht"):
            delete_field(db, system[key]["id"])
    gefolgt = next(o for o in system[K + "entscheidung"]["options"] if o["option_key"] == "bedenken_gefolgt")
    for call in (lambda: add_option(db, system[K + "bedenken_gegen"]["id"], "Statik"),
                 lambda: add_option(db, system[K + "entscheidung"]["id"], "Vielleicht"),
                 lambda: update_option(db, gefolgt["id"], label="Zugestimmt"),
                 lambda: delete_option(db, gefolgt["id"])):
        with pytest.raises(ValueError, match="fest vorgegeben"):
            call()
    update_field(db, system[K + "begruendung"]["id"], {"label": "Warum?", "group_name": "Anzeige an den AG"})  # frei

    ids = [f["id"] for f in draft["fields"]]
    by_key = {f["field_key"]: f["id"] for f in draft["fields"]}
    # Die Unterschrift der Entscheidung vor die Entscheidung ziehen: sie versiegelte die Entscheidung nicht.
    early = ids[:]
    early.remove(by_key[K + "unterschrift_entscheidung"])
    early.insert(early.index(by_key[K + "entscheidung"]), by_key[K + "unterschrift_entscheidung"])
    reorder_fields(db, draft["id"], early)
    with pytest.raises(ValueError, match="nicht in der vorgegebenen Reihenfolge der Abschnitte"):
        publish_draft(db, tpl_id)
    # Ebenso "Entscheidung erbeten bis" unter die Unterschrift Büro.
    reorder_fields(db, draft["id"], ids)
    late = ids[:]
    late.remove(by_key[K + "entscheidung_bis"])
    late.insert(late.index(by_key[K + "unterschrift_buero"]) + 1, by_key[K + "entscheidung_bis"])
    reorder_fields(db, draft["id"], late)
    assert any("Reihenfolge der Abschnitte" in p for p in get_template(db, tpl_id)["system_field_problems"])
    reorder_fields(db, draft["id"], ids)
    assert publish_draft(db, tpl_id)["published_version_no"] == 2


# --- Folgen genau einmal --------------------------------------------------------------------

def test_follow_ups_each_exactly_once_send_answer_and_decision(kworld, router_test_client):
    db = kworld["db"]
    field = _client(kworld, router_test_client, "a")
    office = _client(kworld, router_test_client, "office")
    zero = {"done": 0, "module_off": 0, "failed": 0}
    c = _start(kworld, field)
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == zero  # vor der Unterschrift nichts
    _report(field, c)

    [send] = _tasks(db, SEND_TITLE)
    signature = db.scalar(select(ChecklistAttachment).where(ChecklistAttachment.checklist_id == c["id"],
                                                            ChecklistAttachment.kind == "unterschrift"))
    order = kworld["orders"]["mine"]
    assert send.due_date == to_berlin(signature.created_at).date()
    assert (send.assigned_employee_id, send.priority, send.project_id, send.min_visible_role) == (
        kworld["emps"]["office"].id, "hoch", order.project_id, "buero_auftrag")
    assert (send.source_url, send.source_label) == (f"/checklisten/{c['id']}", "Bedenkenanzeige – Auftrag AU-2026-0001")
    assert "Anna Alpha" in send.description and "Bedenken gemeldet" in send.description
    assert set(_rows(db)) == {K + "versenden"}

    _notice(office, c, deadline="2026-10-09")
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == zero
    assert _tasks(db, ANSWER_TITLE) == []  # Anzeige unterschrieben, aber noch nicht versendet

    _delivered(db, c["id"])
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 1, "module_off": 0, "failed": 0}
    [answer] = _tasks(db, ANSWER_TITLE)
    assert answer.due_date == date(2026, 10, 9)  # = "Entscheidung erbeten bis"
    assert (answer.assigned_employee_id, answer.priority, answer.min_visible_role) == (
        kworld["emps"]["office"].id, "normal", "buero_auftrag")
    assert not _done(db, answer)
    listed = {r["follow_up_key"]: r for r in office.get(f"/api/checklists/{c['id']}/follow-ups").json()}
    assert listed[K + "antwort_pruefen"]["trigger_label"] == "nach dem Versand „Bedenkenanzeige“"
    assert listed[K + "antwort_pruefen"]["target_title"] == ANSWER_TITLE
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == zero
    assert office.post("/api/checklists/run-open-follow-ups").json() == zero
    _delivered(db, c["id"])  # zweiter Versand: keine zweite Aufgabe
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == zero

    _decide(office, c)
    db.expire_all()
    [answer] = _tasks(db, ANSWER_TITLE)
    assert _done(db, answer)  # mit der Unterschrift der Entscheidung erledigt
    rows = _rows(db)
    assert set(rows) == {K + "versenden", K + "antwort_pruefen", K + "entscheidung"}
    assert (rows[K + "entscheidung"].status, rows[K + "entscheidung"].target_type) == ("erledigt", None)
    assert field.post(f"/api/checklists/{c['id']}/complete").json()["status"] == "abgeschlossen"
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == zero
    assert len(_tasks(db, SEND_TITLE)) == 1 and len(_tasks(db, ANSWER_TITLE)) == 1 and len(_rows(db)) == 3


def test_no_answer_task_when_the_decision_came_before_the_dispatch(kworld, router_test_client):
    db = kworld["db"]
    office = _client(kworld, router_test_client, "office")
    c = _start(kworld, office)
    _report(office, c)
    _notice(office, c)
    _decide(office, c, decision="trotz_bedenken")
    _delivered(db, c["id"])
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 1, "module_off": 0, "failed": 0}
    assert _tasks(db, ANSWER_TITLE) == []
    row = _rows(db)[K + "antwort_pruefen"]
    assert (row.status, row.target_type) == ("erledigt", None)


def test_answer_task_without_deadline_is_due_today(kworld, router_test_client, monkeypatch):
    """Nachgeholt an einer älteren Fassung ohne "Entscheidung erbeten bis" -- dann heute fällig."""
    from app import concern_notices
    db = kworld["db"]
    office = _client(kworld, router_test_client, "office")
    c = _start(kworld, office)
    _report(office, c)
    monkeypatch.setattr(concern_notices, "_deadline", lambda checklist: None)
    _delivered(db, c["id"])
    office.post(f"/api/checklists/{c['id']}/run-follow-ups")
    [answer] = _tasks(db, ANSWER_TITLE)
    assert answer.due_date == berlin_today()


def test_answer_follow_up_is_caught_up_once_when_the_task_module_was_off(kworld, router_test_client):
    db = kworld["db"]
    office = _client(kworld, router_test_client, "office")
    c = _start(kworld, office)
    _report(office, c)
    _notice(office, c)
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    _delivered(db, c["id"])
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 0, "module_off": 1, "failed": 0}
    assert [x["id"] for x in office.get("/api/checklists?open_rules=true").json()] == [c["id"]]
    db.scalar(select(EnabledModule).where(EnabledModule.module_key == "aufgabenmanagement")).enabled = True
    db.commit()
    assert office.post("/api/checklists/run-open-follow-ups").json() == {"done": 1, "module_off": 0, "failed": 0}
    assert office.post("/api/checklists/run-open-follow-ups").json() == {"done": 0, "module_off": 0, "failed": 0}
    assert len(_tasks(db, ANSWER_TITLE)) == 1


def test_void_concern_runs_no_follow_ups_any_more(kworld, router_test_client):
    db = kworld["db"]
    office = _client(kworld, router_test_client, "office")
    c = _start(kworld, office)
    _report(office, c)
    resp = office.post(f"/api/checklists/{c['id']}/void", json={"reason": "Material wurde getauscht"})
    assert resp.status_code == 200, resp.text
    _delivered(db, c["id"])
    assert office.post(f"/api/checklists/{c['id']}/run-follow-ups").json() == {"done": 0, "module_off": 0, "failed": 0}
    assert _tasks(db, ANSWER_TITLE) == [] and _done(db, _tasks(db, SEND_TITLE)[0])


# --- Hinweis "Offene Bedenken" ----------------------------------------------------------------

def _hint(office, order_id):
    resp = office.get(f"/api/orders/{order_id}/open-concerns")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["text"] == OPEN_CONCERNS_TEXT
    return body["concerns"]


def test_hint_appears_with_the_concern_and_disappears_with_the_decision(kworld, router_test_client):
    db = kworld["db"]
    office = _client(kworld, router_test_client, "office")
    field = _client(kworld, router_test_client, "a")
    mine, foreign = kworld["orders"]["mine"].id, kworld["orders"]["foreign"].id
    assert _hint(office, mine) == []
    c = _start(kworld, field)
    [hint] = _hint(office, mine)  # vom Start an: die Bedenken sind da
    assert (hint["checklist_id"], hint["template_label"], hint["decision_due"]) == (c["id"], "Bedenkenanzeige", None)
    assert _hint(office, foreign) == []
    _report(field, c)
    _notice(office, c, deadline="2026-10-09")
    assert _hint(office, mine)[0]["decision_due"] == "2026-10-09"
    for key, value in ((K + "entscheidung", "keine_antwort"),):  # Antwort eingetragen, aber noch nicht unterschrieben
        assert _answer(office, c, key, value).status_code == 200
    assert len(_hint(office, mine)) == 1
    assert _sign(office, c, K + "unterschrift_entscheidung", "Olga Office").status_code == 200
    assert _hint(office, mine) == []  # mit der Entscheidung weg
    # Unterschrift verworfen: die Entscheidung gilt nicht mehr -- der Hinweis ist wieder da.
    sig = db.scalar(select(ChecklistAttachment).where(ChecklistAttachment.checklist_id == c["id"],
                                                      ChecklistAttachment.signer_name == "Olga Office",
                                                      ChecklistAttachment.discarded_at.is_(None))
                    .order_by(ChecklistAttachment.id.desc()))
    resp = office.post(f"/api/checklists/{c['id']}/discard-signatures", json={"signature_id": sig.id, "reason": "Falsch"})
    assert resp.status_code == 200, resp.text
    assert len(_hint(office, mine)) == 1


def test_hint_disappears_when_void_and_needs_the_module(kworld, router_test_client):
    db = kworld["db"]
    office = _client(kworld, router_test_client, "office")
    mine = kworld["orders"]["mine"].id
    c = _start(kworld, office)
    second = _start(kworld, office)
    assert [h["checklist_id"] for h in _hint(office, mine)] == [c["id"], second["id"]]
    assert office.post(f"/api/checklists/{c['id']}/void", json={"reason": "Kein Mangel"}).status_code == 200
    assert [h["checklist_id"] for h in _hint(office, mine)] == [second["id"]]
    db.add(EnabledModule(module_key="checklisten", enabled=False))
    db.commit()
    assert _hint(office, mine) == []
    assert open_concerns(db, [mine]) == {mine: [{"checklist_id": second["id"], "template_label": "Bedenkenanzeige",
                                                  "decision_due": None}]}  # die Abfrage selbst kennt kein Modul


def test_other_purposes_never_count_as_open_concerns(kworld, router_test_client):
    office = _client(kworld, router_test_client, "office")
    resp = office.post("/api/checklists", json={"template_id": kworld["order_tpl"]["id"], "context_type": "auftrag",
                                                "order_id": kworld["orders"]["mine"].id})
    assert resp.status_code == 200
    assert _hint(office, kworld["orders"]["mine"].id) == []


def test_mobil_shows_the_hint_per_assignment(kworld, router_test_client):
    db = kworld["db"]
    order = kworld["orders"]["mine"]
    with uhr_festhalten():
        from app.work_preparation import ensure_preparation
        prep = ensure_preparation(db, order.id)
        team = Team(name="Kolonne Nord", active=True)
        db.add(team)
        db.flush()
        assignment = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
        db.add(assignment)
        db.flush()
        db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=assignment.id, start_date=berlin_today(),
                            end_date=berlin_today()))
        db.commit()
        mobil = router_test_client(db, field_view_router, role="field", employee_id=kworld["emps"]["a"].id)
        [assignment] = mobil.get("/api/field-view/today").json()["assignments"]
        assert assignment["open_concerns"] == []
        c = _start(kworld, _client(kworld, router_test_client, "a"))
        today = mobil.get("/api/field-view/today").json()
        assert today["open_concerns_text"] == OPEN_CONCERNS_TEXT
        [assignment] = today["assignments"]
        assert [h["checklist_id"] for h in assignment["open_concerns"]] == [c["id"]]
        # Ein anderer Monteur ohne Einsatz an diesem Auftrag sieht nichts davon.
        other = router_test_client(db, field_view_router, role="field", employee_id=kworld["emps"]["c"].id)
        assert other.get("/api/field-view/today").json()["assignments"] == []
    page = router_test_client(db, pages_router, role="field", employee_id=kworld["emps"]["a"].id).get("/mobil").text
    assert json.dumps(OPEN_CONCERNS_TEXT) in page and "function concernAlert(a)" in page


def test_order_page_carries_the_hint_box(kworld, router_test_client):
    html = router_test_client(kworld["db"], pages_router, role="buero_auftrag").get(
        f"/orders/{kworld['orders']['mine'].id}").text
    assert 'id="concernAlert"' in html and "/open-concerns" in html


# --- Monteur: Meldung ja, Anzeige und Entscheidung nein, keine Büro-Daten ---------------------

def test_field_reports_but_neither_fills_notice_nor_decision_nor_sees_office_data(kworld, router_test_client):
    db = kworld["db"]
    field = _client(kworld, router_test_client, "a")
    office = _client(kworld, router_test_client, "office")
    responses = {"create": _start(kworld, field)}
    c = responses["create"]
    flags = {f["field_key"]: f["office_only"] for f in c["fields"]}
    assert [k for k, v in flags.items() if v] == [s.key for s in CONCERN_SYSTEM_FIELDS if s.office_only]
    for i, body in enumerate(_report(field, c)):
        responses[f"report{i}"] = body
    assert len(_tasks(db, SEND_TITLE)) == 1
    for key, value in ((K + "bedenken_gegen", ["stoffe_bauteile"]), (K + "begruendung", "x"),
                       (K + "entscheidung_bis", "2026-10-09"), (K + "eingegangen_am", "2026-10-05"),
                       (K + "entscheidung", "trotz_bedenken"), (K + "notiz", "y")):
        resp = _answer(field, c, key, value)
        assert resp.status_code == 403 and resp.json()["detail"] == "Dieses Feld füllt das Büro aus.", key
    for key in (K + "unterschrift_buero", K + "unterschrift_entscheidung"):
        assert _sign(field, c, key, "Anna Alpha").status_code == 403, key
    resp = field.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[K + "antwort_beleg"]},
                      files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    assert resp.status_code == 403
    _notice(office, c)
    _delivered(db, c["id"])
    office.post(f"/api/checklists/{c['id']}/run-follow-ups")
    assert len(_tasks(db, ANSWER_TITLE)) == 1  # die Folgen liefen -- der Monteur sieht keine davon

    order_id = kworld["orders"]["mine"].id
    # Seit 1.8.45 bekommt der Monteur den Hinweis "Offene Bedenken" auch über den Endpunkt (Einsatzbericht- und
    # Checklisten-Seite des Auftrags) -- an seinem Auftrag, ohne Büro-Daten.
    for name, url in (("detail", f"/api/checklists/{c['id']}"), ("list", f"/api/checklists?order_id={order_id}"),
                      ("mine", "/api/checklists/mine"), ("concerns", f"/api/orders/{order_id}/open-concerns")):
        resp = field.get(url)
        assert resp.status_code == 200, (name, resp.text)
        responses[name] = resp.json()
    for name, body in responses.items():
        assert not _collect_keys(body, set()) & OFFICE_KEYS, name
        dumped = json.dumps(body, default=str, ensure_ascii=False)
        assert not any(text in dumped for text in TASK_TEXTS), name
    assert [x["checklist_id"] for x in responses["concerns"]["concerns"]] == [c["id"]]
    for method, url in (("GET", f"/api/checklists/{c['id']}/follow-ups"),
                        ("POST", f"/api/checklists/{c['id']}/run-follow-ups")):
        assert field.request(method, url).status_code == 403, url
