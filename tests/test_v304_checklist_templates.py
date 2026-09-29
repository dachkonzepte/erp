"""Version 1.8.0 -- Checklisten-Baukasten, Vorlagenverwaltung (siehe docs/archiv/modul-checklisten.md).

Geprüft: Fassungen (nur der Entwurf ist änderbar, Veröffentlichen löst die bisher gültige ab,
neuer Entwurf ist eine vollständige Kopie mit denselben Feldschlüsseln), Feldnormalisierung je
Typ, Regeln (Typ-Passung, Zielrolle nie "field"), Löschschutz bei verwendeter Vorlage, und die
Router-Rechte: Monteur 403 auf JEDEM Endpunkt, deaktiviertes Modul 403 auch für Admins."""

from decimal import Decimal

import pytest

from app.checklist_templates import (
    add_field, add_option, add_rule, copy_template, create_template, delete_field, delete_option, delete_template,
    discard_draft, get_template, publish_draft, reorder_fields, start_draft, update_field, update_rule,
)
from app.models import Checklist, EnabledModule
from app.routers.checklist_templates import router as checklist_templates_router


def _new(db, **kw):
    kw.setdefault("label", "Sicherheitscheck")
    kw.setdefault("contexts", ["auftrag"])
    return create_template(db, **kw)


def _draft_id(template: dict) -> int:
    return template["draft_version_id"]


def _publishable(db) -> dict:
    t = _new(db)
    add_field(db, _draft_id(t), {"field_type": "ja_nein", "label": "Absturzsicherung geprüft", "required": True})
    return get_template(db, t["id"])


# --- Fassungen ------------------------------------------------------------------------------

def test_new_template_starts_with_empty_draft_version_1(db_session):
    t = _new(db_session)
    assert t["draft_version_no"] == 1
    assert t["published_version_no"] is None
    assert t["editable_version"]["status"] == "entwurf"
    assert t["editable_version"]["fields"] == []


def test_publish_requires_context_and_an_answerable_field(db_session):
    t = _new(db_session, contexts=[])
    add_field(db_session, _draft_id(t), {"field_type": "hinweis", "label": "Nur lesen"})
    with pytest.raises(ValueError) as exc:
        publish_draft(db_session, t["id"])
    assert "Kontext" in str(exc.value)
    assert "mindestens ein Feld" in str(exc.value)


def test_publish_rejects_choice_field_without_options(db_session):
    t = _new(db_session)
    add_field(db_session, _draft_id(t), {"field_type": "auswahl", "label": "Art"})
    with pytest.raises(ValueError, match="keine Optionen"):
        publish_draft(db_session, t["id"])


def test_published_version_is_frozen(db_session):
    t = publish_draft(db_session, _publishable(db_session)["id"])
    published_id = t["published_version_id"]
    assert t["draft_version_id"] is None
    with pytest.raises(ValueError, match="Entwurfsfassung"):
        add_field(db_session, published_id, {"field_type": "text", "label": "Nachträglich"})
    field_id = t["editable_version"]["fields"][0]["id"]
    with pytest.raises(ValueError, match="Entwurfsfassung"):
        update_field(db_session, field_id, {"label": "Umbenannt"})


def test_new_draft_copies_fields_options_rules_and_keeps_keys(db_session):
    t = _new(db_session)
    v = add_field(db_session, _draft_id(t), {"field_type": "auswahl", "label": "Abfallart", "field_key": "abfall"})
    field_id = v["fields"][0]["id"]
    add_option(db_session, field_id, "Asbest")
    add_rule(db_session, _draft_id(t), {"operator": "enthaelt", "field_key": "abfall", "operand": "asbest",
                                        "task_title": "Asbest prüfen"})
    publish_draft(db_session, t["id"])

    t2 = start_draft(db_session, t["id"])
    assert t2["draft_version_no"] == 2
    draft = t2["editable_version"]
    assert draft["status"] == "entwurf"
    assert [f["field_key"] for f in draft["fields"]] == ["abfall"]
    assert [o["option_key"] for o in draft["fields"][0]["options"]] == ["asbest"]
    assert draft["rules"][0]["operand"] == "asbest"
    assert draft["fields"][0]["id"] != field_id  # echte Kopie, nicht dieselbe Zeile
    # Zweiter Aufruf legt keinen zweiten Entwurf an.
    assert start_draft(db_session, t["id"])["draft_version_id"] == t2["draft_version_id"]


def test_publishing_new_draft_supersedes_previous(db_session):
    t = publish_draft(db_session, _publishable(db_session)["id"])
    start_draft(db_session, t["id"])
    t = publish_draft(db_session, t["id"])
    statuses = {v["version_no"]: v["status"] for v in t["versions"]}
    assert statuses == {1: "abgeloest", 2: "veroeffentlicht"}
    assert t["published_version_no"] == 2


def test_discard_draft_only_when_something_was_published(db_session):
    t = _publishable(db_session)
    with pytest.raises(ValueError, match="noch nie veröffentlicht"):
        discard_draft(db_session, t["id"])
    publish_draft(db_session, t["id"])
    start_draft(db_session, t["id"])
    t = discard_draft(db_session, t["id"])
    assert t["draft_version_id"] is None
    assert t["editable_version"]["status"] == "veroeffentlicht"


def test_delete_template_blocked_while_a_checklist_uses_it(db_session):
    t = publish_draft(db_session, _publishable(db_session)["id"])
    db_session.add(Checklist(template_id=t["id"], template_version_id=t["published_version_id"],
                             template_label_snapshot=t["label"], context_type="betrieb"))
    db_session.commit()
    with pytest.raises(ValueError, match="archiviert"):
        delete_template(db_session, t["id"])


def test_delete_unused_template_removes_versions(db_session):
    t = _publishable(db_session)
    assert delete_template(db_session, t["id"]) is True
    assert get_template(db_session, t["id"]) is None


def test_copy_template_creates_independent_draft(db_session):
    t = publish_draft(db_session, _publishable(db_session)["id"])
    c = copy_template(db_session, t["id"], "Sicherheitscheck Kopie")
    assert c["id"] != t["id"]
    assert c["draft_version_no"] == 1 and c["published_version_no"] is None
    assert c["contexts"] == ["auftrag"]
    assert [f["label"] for f in c["editable_version"]["fields"]] == ["Absturzsicherung geprüft"]


# --- Felder ---------------------------------------------------------------------------------

def test_field_key_is_slugged_and_unique(db_session):
    t = _new(db_session)
    add_field(db_session, _draft_id(t), {"field_type": "text", "label": "Größe Fläche"})
    v = add_field(db_session, _draft_id(t), {"field_type": "text", "label": "Größe Fläche"})
    assert [f["field_key"] for f in v["fields"]] == ["groesse_flaeche", "groesse_flaeche_2"]


def test_invalid_field_key_rejected(db_session):
    t = _new(db_session)
    with pytest.raises(ValueError, match="Feldschlüssel"):
        add_field(db_session, _draft_id(t), {"field_type": "text", "label": "X", "field_key": "Mit Leerzeichen"})


def test_type_change_resets_foreign_settings(db_session):
    t = _new(db_session)
    v = add_field(db_session, _draft_id(t), {"field_type": "foto", "label": "Fotos", "min_count": 2, "max_count": 5})
    field_id = v["fields"][0]["id"]
    v = update_field(db_session, field_id, {"field_type": "ja_nein", "allow_na": True})
    f = v["fields"][0]
    assert (f["min_count"], f["max_count"], f["allow_na"]) == (None, None, True)
    v = update_field(db_session, field_id, {"field_type": "text"})
    assert v["fields"][0]["allow_na"] is False


def test_hint_field_is_never_required(db_session):
    t = _new(db_session)
    v = add_field(db_session, _draft_id(t), {"field_type": "hinweis", "label": "Achtung", "required": True})
    assert v["fields"][0]["required"] is False


def test_number_and_count_validation(db_session):
    t = _new(db_session)
    with pytest.raises(ValueError, match="Mindestwert"):
        add_field(db_session, _draft_id(t), {"field_type": "zahl", "label": "km", "min_value": 5, "max_value": 1})
    with pytest.raises(ValueError, match="Höchstanzahl"):
        add_field(db_session, _draft_id(t), {"field_type": "foto", "label": "F", "max_count": 50})
    v = add_field(db_session, _draft_id(t), {"field_type": "zahl", "label": "Temperatur", "unit": "°C",
                                             "min_value": "-30", "max_value": "50"})
    assert v["fields"][0]["min_value"] == Decimal("-30")


def test_single_signature_forces_max_count_one(db_session):
    t = _new(db_session)
    v = add_field(db_session, _draft_id(t), {"field_type": "unterschrift", "label": "Monteur", "max_count": 5})
    assert v["fields"][0]["max_count"] == 1
    v = update_field(db_session, v["fields"][0]["id"], {"multiple": True, "max_count": 12})
    assert v["fields"][0]["max_count"] == 12


def test_renaming_field_key_updates_rules(db_session):
    t = _new(db_session)
    v = add_field(db_session, _draft_id(t), {"field_type": "ja_nein", "label": "Freigegeben", "field_key": "frei"})
    add_rule(db_session, _draft_id(t), {"operator": "ist_nein", "field_key": "frei", "task_title": "Nicht frei"})
    v = update_field(db_session, v["fields"][0]["id"], {"field_key": "freigegeben"})
    assert v["rules"][0]["field_key"] == "freigegeben"


def test_field_used_by_rule_cannot_be_deleted(db_session):
    t = _new(db_session)
    v = add_field(db_session, _draft_id(t), {"field_type": "ja_nein", "label": "Frei", "field_key": "frei"})
    add_rule(db_session, _draft_id(t), {"operator": "ist_nein", "field_key": "frei", "task_title": "Nicht frei"})
    with pytest.raises(ValueError, match="Regel"):
        delete_field(db_session, v["fields"][0]["id"])


def test_reorder_requires_complete_list(db_session):
    t = _new(db_session)
    add_field(db_session, _draft_id(t), {"field_type": "text", "label": "A"})
    v = add_field(db_session, _draft_id(t), {"field_type": "text", "label": "B"})
    a, b = (f["id"] for f in v["fields"])
    with pytest.raises(ValueError):
        reorder_fields(db_session, _draft_id(t), [a])
    v = reorder_fields(db_session, _draft_id(t), [b, a])
    assert [f["label"] for f in v["fields"]] == ["B", "A"]


def test_option_used_by_rule_cannot_be_deleted(db_session):
    t = _new(db_session)
    v = add_field(db_session, _draft_id(t), {"field_type": "auswahl", "label": "Art", "field_key": "art"})
    v = add_option(db_session, v["fields"][0]["id"], "Asbest")
    add_rule(db_session, _draft_id(t), {"operator": "enthaelt", "field_key": "art", "operand": "asbest",
                                        "task_title": "Asbest"})
    with pytest.raises(ValueError, match="Regel"):
        delete_option(db_session, v["fields"][0]["options"][0]["id"])


# --- Regeln ---------------------------------------------------------------------------------

def test_rule_operator_must_fit_field_type(db_session):
    t = _new(db_session)
    add_field(db_session, _draft_id(t), {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    with pytest.raises(ValueError, match="Feldtyp"):
        add_rule(db_session, _draft_id(t), {"operator": "ist_ja", "field_key": "bem", "task_title": "X"})
    v = add_rule(db_session, _draft_id(t), {"operator": "ausgefuellt", "field_key": "bem", "task_title": "X"})
    assert v["rules"][0]["operator"] == "ausgefuellt"


def test_rule_never_targets_field_role(db_session):
    t = _new(db_session)
    with pytest.raises(ValueError, match="Monteure"):
        add_rule(db_session, _draft_id(t), {"operator": "immer", "task_title": "X", "min_visible_role": "field"})


def test_always_rule_drops_field_and_operand(db_session):
    t = _new(db_session)
    add_field(db_session, _draft_id(t), {"field_type": "ja_nein", "label": "A", "field_key": "a"})
    v = add_rule(db_session, _draft_id(t), {"operator": "immer", "field_key": "a", "operand": "x",
                                            "task_title": "Immer", "task_priority": "hoch"})
    r = v["rules"][0]
    assert (r["field_key"], r["operand"], r["task_priority"]) == (None, None, "hoch")


def test_number_rule_needs_numeric_operand_and_invalid_update_rolls_back(db_session):
    t = _new(db_session)
    add_field(db_session, _draft_id(t), {"field_type": "zahl", "label": "km", "field_key": "km"})
    with pytest.raises(ValueError, match="Zahl"):
        add_rule(db_session, _draft_id(t), {"operator": "groesser", "field_key": "km", "operand": "viel",
                                            "task_title": "X"})
    v = add_rule(db_session, _draft_id(t), {"operator": "groesser", "field_key": "km", "operand": "100",
                                            "task_title": "Weit"})
    rule_id = v["rules"][0]["id"]
    with pytest.raises(ValueError):
        update_rule(db_session, rule_id, {"task_priority": "egal"})
    assert get_template(db_session, t["id"])["editable_version"]["rules"][0]["task_priority"] == "normal"


def test_publish_revalidates_rules_after_field_change(db_session):
    t = _new(db_session)
    v = add_field(db_session, _draft_id(t), {"field_type": "ja_nein", "label": "A", "field_key": "a"})
    add_rule(db_session, _draft_id(t), {"operator": "ist_ja", "field_key": "a", "task_title": "Regel A"})
    update_field(db_session, v["fields"][0]["id"], {"field_type": "text"})
    with pytest.raises(ValueError, match="Regel A"):
        publish_draft(db_session, t["id"])


# --- Router ---------------------------------------------------------------------------------

def _routes():
    for route in checklist_templates_router.routes:
        for method in route.methods:
            yield method, route.path.replace("{template_id}", "1").replace("{version_id}", "1") \
                .replace("{field_id}", "1").replace("{option_id}", "1").replace("{rule_id}", "1")


def test_field_role_is_rejected_on_every_endpoint(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, checklist_templates_router, role="field", employee_id=1)
    for method, path in _routes():
        resp = client.request(method, path, json={})
        assert resp.status_code == 403, (method, path, resp.status_code)


def test_disabled_module_rejects_even_admin(threaded_db_session, router_test_client):
    threaded_db_session.add(EnabledModule(module_key="checklisten", enabled=False))
    threaded_db_session.commit()
    client = router_test_client(threaded_db_session, checklist_templates_router)
    resp = client.get("/api/checklist-templates")
    assert resp.status_code == 403
    assert "deaktiviert" in resp.json()["detail"]


def test_office_workflow_over_http(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, checklist_templates_router, role="buero_auftrag")
    t = client.post("/api/checklist-templates", json={"label": "Tagesbericht", "contexts": ["auftrag"]}).json()
    vid = t["draft_version_id"]
    resp = client.post(f"/api/checklist-template-versions/{vid}/fields", json={"field_type": "text", "label": "Arbeiten"})
    assert resp.status_code == 200
    # exclude_unset: nur das Pflicht-Häkchen ändern, die Beschriftung bleibt.
    fid = resp.json()["fields"][0]["id"]
    v = client.put(f"/api/checklist-template-fields/{fid}", json={"required": True}).json()
    assert v["fields"][0]["label"] == "Arbeiten" and v["fields"][0]["required"] is True
    bad = client.post(f"/api/checklist-template-versions/{vid}/rules", json={"operator": "ist_ja", "field_key": "arbeiten",
                                                                            "task_title": "X"})
    assert bad.status_code == 400
    published = client.post(f"/api/checklist-templates/{t['id']}/publish")
    assert published.status_code == 200 and published.json()["published_version_no"] == 1
    frozen = client.post(f"/api/checklist-template-versions/{vid}/fields", json={"field_type": "text", "label": "Y"})
    assert frozen.status_code == 400
    assert client.get("/api/checklist-templates/999").status_code == 404
    assert client.post("/api/checklist-template-versions/999/fields", json={"label": "Z"}).status_code == 404
