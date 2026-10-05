"""Version 1.8.1 -- Checklisten ausfüllen: Anlegen in vier Kontexten, Antworten je Feldtyp,
Fotos/Unterschriften, Abschließen, Idempotenz (client_uuid) und Rechte samt Angriffstest
(siehe docs/archiv/modul-checklisten.md, Abschnitt "Rechte").

Aufbau: drei Monteure -- A und B sind demselben Auftrag zugeordnet, C keinem. Vorlage "Auftrag"
ist NICHT für Monteure lesbar, Vorlage "Gerät" schon (field_readable)."""

from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image

import app.checklists as checklists_module
from app.checklist_templates import (
    add_field, add_option, create_template, publish_draft, set_template_archived,
)
from app.models import (
    ChecklistAttachment, Customer, EnabledModule, Employee, OperationalAsset, Order, Project, Property,
    WorkPreparationEmployee,
)
from app.project_pipeline_columns import default_pipeline_column_id
from app.routers.checklists import router as checklists_router
from app.work_preparation import ensure_preparation


def _png(color=(10, 120, 90), size=(60, 30)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (2400, 1200), (200, 30, 30)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def world(threaded_db_session, tmp_path, monkeypatch):
    db = threaded_db_session
    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    emps = {}
    for key, (first, last) in {"a": ("Anna", "Alpha"), "b": ("Bernd", "Beta"), "c": ("Carla", "Gamma"),
                               "office": ("Olga", "Office")}.items():
        e = Employee(first_name=first, last_name=last, employee_group="angestellt", hourly_wage="30",
                     weekly_hours="40", active=True)
        db.add(e)
        db.flush()
        emps[key] = e
    customer = Customer(name="Kunde Nord", last_name="Kunde Nord")
    db.add(customer)
    db.flush()
    prop = Property(customer_id=customer.id, name="Halle Nord", street="Weg 1", postal_code="12345", city="Stadt")
    db.add(prop)
    db.flush()
    orders = {}
    for n, key in ((1, "mine"), (2, "foreign")):
        project = Project(project_number=f"P-{n}", name="Projekt", customer_id=customer.id, property_id=prop.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(project)
        db.flush()
        order = Order(order_number=f"AU-2026-000{n}", project_id=project.id, source_quote_id=n,
                      quote_number_snapshot=f"A-{n}", title="Auftrag", customer_name="Kunde Nord",
                      property_name="Halle Nord", property_address="Weg 1\n12345 Stadt")
        db.add(order)
        db.flush()
        orders[key] = order
    asset = OperationalAsset(name="Hubsteiger", asset_type="Maschine", asset_number="BM-7")
    db.add(asset)
    db.commit()
    prep = ensure_preparation(db, orders["mine"].id)
    for key in ("a", "b"):
        db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=emps[key].id))
    db.commit()

    t = create_template(db, label="Sicherheitscheck", contexts=["auftrag", "objekt"])
    v = t["draft_version_id"]
    add_field(db, v, {"field_type": "hinweis", "label": "Vor Beginn lesen"})
    add_field(db, v, {"field_type": "ja_nein", "label": "Freigegeben", "field_key": "frei", "required": True, "allow_na": True})
    add_field(db, v, {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    add_field(db, v, {"field_type": "zahl", "label": "Wind", "field_key": "wind", "min_value": "0", "max_value": "100", "decimals": 1})
    x = add_field(db, v, {"field_type": "auswahl", "label": "Sicherung", "field_key": "sich", "multiple": True})
    fid = next(f["id"] for f in x["fields"] if f["field_key"] == "sich")
    add_option(db, fid, "Gerüst")
    add_option(db, fid, "Fangnetz")
    add_field(db, v, {"field_type": "datum", "label": "Datum", "field_key": "datum"})
    add_field(db, v, {"field_type": "datum_uhrzeit", "label": "Beginn", "field_key": "beginn"})
    add_field(db, v, {"field_type": "foto", "label": "Fotos", "field_key": "fotos", "min_count": 1, "max_count": 2})
    add_field(db, v, {"field_type": "unterschrift", "label": "Unterschrift Monteur", "field_key": "sig", "required": True})
    order_tpl = publish_draft(db, t["id"])

    t2 = create_template(db, label="Geräte-Sichtprüfung", contexts=["betriebsmittel"], field_readable=True)
    add_field(db, t2["draft_version_id"], {"field_type": "ja_nein", "label": "Einsatzbereit",
                                          "field_key": "einsatzbereit", "required": True})
    asset_tpl = publish_draft(db, t2["id"])

    t3 = create_template(db, label="Unterweisung", contexts=["betrieb"])
    add_field(db, t3["draft_version_id"], {"field_type": "unterschrift", "label": "Teilnehmer", "field_key": "tn",
                                          "multiple": True, "min_count": 2, "max_count": 10})
    company_tpl = publish_draft(db, t3["id"])

    return {"db": db, "emps": emps, "orders": orders, "prop": prop, "asset": asset, "order_tpl": order_tpl,
            "asset_tpl": asset_tpl, "company_tpl": company_tpl}


def _client(world, router_test_client, who):
    if who == "office":
        return router_test_client(world["db"], checklists_router, role="buero_auftrag",
                                  employee_id=world["emps"]["office"].id)
    return router_test_client(world["db"], checklists_router, role="field", employee_id=world["emps"][who].id)


def _fields(checklist):
    return {f["field_key"]: f["id"] for f in checklist["fields"]}


def _start_order(world, client, **extra):
    resp = client.post("/api/checklists", json={"template_id": world["order_tpl"]["id"], "context_type": "auftrag",
                                                "order_id": world["orders"]["mine"].id, **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fill_order_checklist(client, c):
    f = _fields(c)
    assert client.put(f"/api/checklists/{c['id']}/answers/{f['frei']}", json={"value": "ja"}).status_code == 200
    assert client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["fotos"]},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).status_code == 200
    resp = client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["sig"], "signer_name": "Anna Alpha"},
                       files={"file": ("s.png", _png(), "image/png")})
    assert resp.status_code == 200
    return resp.json()


# --- Anlegen --------------------------------------------------------------------------------

def test_field_creates_checklist_at_assigned_order_with_snapshots(world, router_test_client):
    c = _start_order(world, _client(world, router_test_client, "a"))
    assert c["status"] == "entwurf" and c["is_own"] and c["can_edit"]
    assert c["context_label"] == "Auftrag AU-2026-0001"
    assert "Kunde Nord" in c["context_detail"] and "12345 Stadt" in c["context_detail"]
    assert c["created_by_name"] == "Anna Alpha"
    assert [f["field_key"] for f in c["fields"]][:2] == ["vor_beginn_lesen", "frei"]
    assert "rules" not in c  # Regeln sind Büro-intern


def test_field_cannot_start_at_foreign_or_unknown_order(world, router_test_client):
    client = _client(world, router_test_client, "a")
    for order_id in (world["orders"]["foreign"].id, 99999):
        resp = client.post("/api/checklists", json={"template_id": world["order_tpl"]["id"], "context_type": "auftrag",
                                                    "order_id": order_id})
        assert resp.status_code == 403


def test_company_context_is_office_only(world, router_test_client):
    field = _client(world, router_test_client, "a")
    payload = {"template_id": world["company_tpl"]["id"], "context_type": "betrieb"}
    assert field.post("/api/checklists", json=payload).status_code == 403
    assert field.get("/api/checklists/startable-templates?context=betrieb").status_code == 403
    office = _client(world, router_test_client, "office")
    resp = office.post("/api/checklists", json=payload)
    assert resp.status_code == 200 and resp.json()["context_label"] == "Betrieb"


def test_template_must_fit_context_be_published_and_active(world, router_test_client):
    client = _client(world, router_test_client, "a")
    wrong = client.post("/api/checklists", json={"template_id": world["asset_tpl"]["id"], "context_type": "objekt",
                                                 "property_id": world["prop"].id})
    assert wrong.status_code == 400
    draft_only = create_template(world["db"], label="Nur Entwurf", contexts=["objekt"])
    resp = client.post("/api/checklists", json={"template_id": draft_only["id"], "context_type": "objekt",
                                                "property_id": world["prop"].id})
    assert resp.status_code == 400 and "veröffentlicht" in resp.json()["detail"]
    set_template_archived(world["db"], world["order_tpl"]["id"], True)
    assert client.post("/api/checklists", json={"template_id": world["order_tpl"]["id"], "context_type": "objekt",
                                                "property_id": world["prop"].id}).status_code == 404


def test_startable_templates_show_only_published_for_context(world, router_test_client):
    client = _client(world, router_test_client, "a")
    create_template(world["db"], label="Entwurf Objekt", contexts=["objekt"])
    labels = [t["label"] for t in client.get("/api/checklists/startable-templates?context=objekt").json()]
    assert labels == ["Sicherheitscheck"]
    assert [t["label"] for t in client.get("/api/checklists/startable-templates?context=betriebsmittel").json()] \
        == ["Geräte-Sichtprüfung"]


def test_field_can_start_at_any_property_and_asset(world, router_test_client):
    client = _client(world, router_test_client, "c")  # keinem Auftrag zugeordnet
    p = client.post("/api/checklists", json={"template_id": world["order_tpl"]["id"], "context_type": "objekt",
                                             "property_id": world["prop"].id})
    assert p.status_code == 200 and p.json()["context_label"] == "Halle Nord"
    a = client.post("/api/checklists", json={"template_id": world["asset_tpl"]["id"], "context_type": "betriebsmittel",
                                             "operational_asset_id": world["asset"].id})
    assert a.status_code == 200 and a.json()["context_label"] == "Hubsteiger (BM-7)"


def test_asset_context_needs_asset_module_for_field(world, router_test_client):
    world["db"].add(EnabledModule(module_key="betriebsmittel", enabled=False))
    world["db"].commit()
    client = _client(world, router_test_client, "a")
    resp = client.post("/api/checklists", json={"template_id": world["asset_tpl"]["id"], "context_type": "betriebsmittel",
                                                "operational_asset_id": world["asset"].id})
    assert resp.status_code == 403


def test_field_without_employee_is_rejected(world, router_test_client):
    client = router_test_client(world["db"], checklists_router, role="field", employee_id=None)
    resp = client.post("/api/checklists", json={"template_id": world["order_tpl"]["id"], "context_type": "objekt",
                                                "property_id": world["prop"].id})
    assert resp.status_code == 403


def test_disabled_module_rejects_everything(world, router_test_client):
    world["db"].add(EnabledModule(module_key="checklisten", enabled=False))
    world["db"].commit()
    office = _client(world, router_test_client, "office")
    assert office.get("/api/checklists").status_code == 403
    assert office.get("/api/checklists/startable-templates?context=objekt").status_code == 403


# --- Antworten ------------------------------------------------------------------------------

def test_answers_per_field_type_and_validation(world, router_test_client):
    client = _client(world, router_test_client, "a")
    c = _start_order(world, client)
    f = _fields(c)
    url = f"/api/checklists/{c['id']}/answers/"
    good = {"frei": "entfaellt", "bem": "  alles gut ", "wind": "12,5", "sich": ["fangnetz", "geruest"],
            "datum": "2026-09-29", "beginn": "2026-09-29T07:30"}
    for key, value in good.items():
        resp = client.put(url + str(f[key]), json={"value": value})
        assert resp.status_code == 200, (key, resp.text)
    answers = resp.json()["answers"]
    assert answers[str(f["frei"])]["value"] == "entfaellt"
    assert answers[str(f["bem"])]["value"] == "alles gut"
    assert Decimal(str(answers[str(f["wind"])]["value"])) == Decimal("12.5")
    assert answers[str(f["sich"])]["value"] == ["geruest", "fangnetz"]  # Reihenfolge der Vorlage
    assert answers[str(f["beginn"])]["value"] == "2026-09-29T07:30"
    bad = {"frei": "vielleicht", "wind": "150", "sich": ["leiter"], "datum": "29.09.2026"}
    for key, value in bad.items():
        assert client.put(url + str(f[key]), json={"value": value}).status_code == 400, key
    assert client.put(url + str(f["wind"]), json={"value": "1.25"}).status_code == 400  # decimals=1
    assert client.put(url + str(f["fotos"]), json={"value": "x"}).status_code == 400  # Foto = Anhang
    # Mehrfachauswahl umstellen und leeren
    assert client.put(url + str(f["sich"]), json={"value": ["geruest"]}).json()["answers"][str(f["sich"])]["value"] == ["geruest"]
    cleared = client.put(url + str(f["bem"]), json={"value": ""}).json()
    assert cleared["answers"][str(f["bem"])]["value"] is None


def test_answer_for_field_of_other_version_is_rejected(world, router_test_client):
    client = _client(world, router_test_client, "a")
    c = _start_order(world, client)
    other = world["asset_tpl"]["editable_version"]["fields"][0]["id"]
    assert client.put(f"/api/checklists/{c['id']}/answers/{other}", json={"value": "ja"}).status_code == 404


def test_idempotent_create_and_answer(world, router_test_client):
    client = _client(world, router_test_client, "a")
    uuid = "11111111-2222-3333-4444-555555555555"
    first = _start_order(world, client, client_uuid=uuid)
    second = _start_order(world, client, client_uuid=uuid)
    assert first["id"] == second["id"]
    other = _client(world, router_test_client, "b")
    resp = other.post("/api/checklists", json={"template_id": world["order_tpl"]["id"], "context_type": "auftrag",
                                               "order_id": world["orders"]["mine"].id, "client_uuid": uuid})
    assert resp.status_code == 400  # fremde UUID liefert nie fremde Daten
    f = _fields(first)
    body = {"value": "nein", "client_uuid": "aaaaaaaa-0000-0000-0000-000000000001"}
    assert client.put(f"/api/checklists/{first['id']}/answers/{f['frei']}", json=body).status_code == 200
    body_replay = {"value": "ja", "client_uuid": "aaaaaaaa-0000-0000-0000-000000000001"}
    replay = client.put(f"/api/checklists/{first['id']}/answers/{f['frei']}", json=body_replay)
    assert replay.status_code == 200
    assert replay.json()["answers"][str(f["frei"])]["value"] == "nein"  # Wiederholung ändert nichts


def test_older_client_answer_does_not_overwrite_newer(world, router_test_client):
    client = _client(world, router_test_client, "a")
    c = _start_order(world, client)
    f = _fields(c)
    url = f"/api/checklists/{c['id']}/answers/{f['bem']}"
    client.put(url, json={"value": "neu", "client_recorded_at": "2026-09-29T10:00:00"})
    resp = client.put(url, json={"value": "alt", "client_recorded_at": "2026-09-29T09:00:00"})
    assert resp.json()["answers"][str(f["bem"])]["value"] == "neu"


# --- Anhänge --------------------------------------------------------------------------------

def test_photos_and_signatures(world, router_test_client):
    client = _client(world, router_test_client, "a")
    c = _start_order(world, client)
    f = _fields(c)
    url = f"/api/checklists/{c['id']}/attachments"
    body = client.post(url, data={"field_id": f["fotos"], "client_uuid": "bbbbbbbb-0000-0000-0000-000000000001"},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).json()
    photo = body["attachments"][0]
    stored = world["db"].get(ChecklistAttachment, photo["id"])
    with Image.open(checklists_module.attachment_path(stored)) as img:
        assert max(img.size) == 1600  # verkleinert
    replay = client.post(url, data={"field_id": f["fotos"], "client_uuid": "bbbbbbbb-0000-0000-0000-000000000001"},
                         files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).json()
    assert len(replay["attachments"]) == 1  # keine zweite Datei
    assert client.get(photo["url"]).status_code == 200
    client.post(url, data={"field_id": f["fotos"]}, files={"file": ("g.jpg", _jpeg(), "image/jpeg")})
    too_many = client.post(url, data={"field_id": f["fotos"]}, files={"file": ("h.jpg", _jpeg(), "image/jpeg")})
    assert too_many.status_code == 400  # max_count=2
    assert client.post(url, data={"field_id": f["fotos"]}, files={"file": ("x.jpg", b"kein bild", "image/jpeg")}).status_code == 400
    assert client.post(url, data={"field_id": f["sig"]}, files={"file": ("s.png", _png(), "image/png")}).status_code == 400
    # Seit 1.8.56 verlangt die Unterschrift die Pflichtangaben oberhalb ("Freigegeben").
    assert client.put(f"/api/checklists/{c['id']}/answers/{f['frei']}", json={"value": "ja"}).status_code == 200
    client.post(url, data={"field_id": f["sig"], "signer_name": "Anna"}, files={"file": ("s.png", _png(), "image/png")})
    again = client.post(url, data={"field_id": f["sig"], "signer_name": "Anna Alpha"},
                        files={"file": ("s.png", _png((0, 0, 0)), "image/png")})
    assert again.status_code == 409  # seit 1.8.13 ersetzt keine Unterschrift die andere (test_v317)
    sigs = [a for a in client.get(f"/api/checklists/{c['id']}").json()["attachments"] if a["kind"] == "unterschrift"]
    assert [s["signer_name"] for s in sigs] == ["Anna"]
    assert client.post(url, data={"field_id": f["frei"]}, files={"file": ("s.png", _png(), "image/png")}).status_code == 400


def test_multiple_signatures_for_company_briefing(world, router_test_client):
    office = _client(world, router_test_client, "office")
    c = office.post("/api/checklists", json={"template_id": world["company_tpl"]["id"], "context_type": "betrieb"}).json()
    tn = _fields(c)["tn"]
    office.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": tn, "signer_name": "Anna Alpha"},
                files={"file": ("s.png", _png(), "image/png")})
    missing = office.post(f"/api/checklists/{c['id']}/complete")
    assert missing.status_code == 400 and "mindestens 2" in missing.json()["detail"]
    office.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": tn, "signer_name": "Bernd Beta"},
                files={"file": ("s.png", _png(), "image/png")})
    assert office.post(f"/api/checklists/{c['id']}/complete").json()["status"] == "abgeschlossen"


# --- Abschließen, Löschen -------------------------------------------------------------------

def test_complete_requires_mandatory_fields_and_freezes(world, router_test_client):
    client = _client(world, router_test_client, "a")
    c = _start_order(world, client)
    missing = client.post(f"/api/checklists/{c['id']}/complete")
    assert missing.status_code == 400
    assert "Freigegeben" in missing.json()["detail"] and "Unterschrift Monteur" in missing.json()["detail"]
    body = _fill_order_checklist(client, c)
    assert body["missing_required"] == []
    done = client.post(f"/api/checklists/{c['id']}/complete").json()
    assert done["status"] == "abgeschlossen" and not done["can_edit"] and done["completed_at"]
    assert client.post(f"/api/checklists/{c['id']}/complete").status_code == 200  # idempotent
    f = _fields(c)
    assert client.put(f"/api/checklists/{c['id']}/answers/{f['bem']}", json={"value": "zu spät"}).status_code == 409
    assert client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["fotos"]},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).status_code == 409
    assert client.delete(f"/api/checklist-attachments/{done['attachments'][0]['id']}").status_code == 409
    assert client.delete(f"/api/checklists/{c['id']}").status_code == 409


def test_replay_after_completion_is_still_success(world, router_test_client):
    client = _client(world, router_test_client, "a")
    c = _start_order(world, client)
    f = _fields(c)
    body = {"value": "text", "client_uuid": "cccccccc-0000-0000-0000-000000000001"}
    client.put(f"/api/checklists/{c['id']}/answers/{f['bem']}", json=body)
    _fill_order_checklist(client, c)
    client.post(f"/api/checklists/{c['id']}/complete")
    assert client.put(f"/api/checklists/{c['id']}/answers/{f['bem']}", json=body).status_code == 200


def test_deleting_draft_removes_files(world, router_test_client):
    """Nur ein UNunterschriebener Entwurf -- einen unterschriebenen löscht seit 1.8.13 niemand
    (test_v317)."""
    client = _client(world, router_test_client, "a")
    c = _start_order(world, client)
    f = _fields(c)
    for name in ("f.jpg", "g.jpg"):
        body = client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": f["fotos"]},
                           files={"file": (name, _jpeg(), "image/jpeg")}).json()
    paths = [checklists_module.attachment_path(world["db"].get(ChecklistAttachment, a["id"])) for a in body["attachments"]]
    assert all(p.exists() for p in paths)
    assert client.delete(f"/api/checklists/{c['id']}").status_code == 200
    assert not any(p.exists() for p in paths)
    assert client.get(f"/api/checklists/{c['id']}").status_code == 404


# --- Rechte zwischen Monteuren --------------------------------------------------------------

def test_colleague_sees_summary_only_for_unreadable_template(world, router_test_client):
    a = _client(world, router_test_client, "a")
    c = _start_order(world, a)
    _fill_order_checklist(a, c)
    b = _client(world, router_test_client, "b")  # demselben Auftrag zugeordnet
    rows = b.get(f"/api/checklists?order_id={world['orders']['mine'].id}").json()
    assert len(rows) == 1 and rows[0]["can_open"] is False and rows[0]["is_own"] is False
    assert "answers" not in rows[0] and "fields" not in rows[0]
    assert b.get(f"/api/checklists/{c['id']}").status_code == 403
    attachment_url = a.get(f"/api/checklists/{c['id']}").json()["attachments"][0]["url"]
    assert b.get(attachment_url).status_code == 403
    f = _fields(c)
    assert b.put(f"/api/checklists/{c['id']}/answers/{f['bem']}", json={"value": "x"}).status_code == 403
    assert b.post(f"/api/checklists/{c['id']}/complete").status_code == 403
    assert b.delete(f"/api/checklists/{c['id']}").status_code == 403


def test_colleague_reads_but_cannot_write_readable_template(world, router_test_client):
    a = _client(world, router_test_client, "a")
    c = a.post("/api/checklists", json={"template_id": world["asset_tpl"]["id"], "context_type": "betriebsmittel",
                                        "operational_asset_id": world["asset"].id}).json()
    field_id = _fields(c)["einsatzbereit"]
    a.put(f"/api/checklists/{c['id']}/answers/{field_id}", json={"value": "nein"})
    other = _client(world, router_test_client, "c")
    detail = other.get(f"/api/checklists/{c['id']}")
    assert detail.status_code == 200 and detail.json()["can_edit"] is False
    assert detail.json()["answers"][str(field_id)]["value"] == "nein"
    assert other.put(f"/api/checklists/{c['id']}/answers/{field_id}", json={"value": "ja"}).status_code == 403


def test_unassigned_field_cannot_list_or_open_order_checklists(world, router_test_client):
    a = _client(world, router_test_client, "a")
    c = _start_order(world, a)
    other = _client(world, router_test_client, "c")
    assert other.get(f"/api/checklists?order_id={world['orders']['mine'].id}").status_code == 403
    assert other.get(f"/api/checklists/{c['id']}").status_code == 403
    assert other.get("/api/checklists").status_code == 403  # keine Gesamtliste für Monteure


def test_own_checklist_stays_reachable_after_unassignment(world, router_test_client):
    a = _client(world, router_test_client, "a")
    c = _start_order(world, a)
    db = world["db"]
    db.query(WorkPreparationEmployee).filter_by(employee_id=world["emps"]["a"].id).delete()
    db.commit()
    assert a.get(f"/api/checklists/{c['id']}").status_code == 200
    f = _fields(c)
    assert a.put(f"/api/checklists/{c['id']}/answers/{f['bem']}", json={"value": "weiter"}).status_code == 200
    # ... aber die Checkliste öffnet nicht den Auftrag: neue Checkliste dort geht nicht mehr.
    resp = a.post("/api/checklists", json={"template_id": world["order_tpl"]["id"], "context_type": "auftrag",
                                           "order_id": world["orders"]["mine"].id})
    assert resp.status_code == 403


def test_office_sees_and_edits_everything(world, router_test_client):
    a = _client(world, router_test_client, "a")
    c = _start_order(world, a)
    office = _client(world, router_test_client, "office")
    assert office.get(f"/api/checklists/{c['id']}").json()["can_edit"] is True
    f = _fields(c)
    assert office.put(f"/api/checklists/{c['id']}/answers/{f['bem']}", json={"value": "Büro"}).status_code == 200
    assert len(office.get("/api/checklists").json()) == 1


def test_mine_lists_own_drafts(world, router_test_client):
    a = _client(world, router_test_client, "a")
    c1 = _start_order(world, a)
    c2 = _start_order(world, a)
    _fill_order_checklist(a, c2)
    a.post(f"/api/checklists/{c2['id']}/complete")
    _start_order(world, _client(world, router_test_client, "b"))
    assert [r["id"] for r in a.get("/api/checklists/mine").json()] == [c1["id"]]


# --- Einsatzbereitschaft --------------------------------------------------------------------

def test_asset_readiness_uses_latest_completed_answer(world, router_test_client):
    client = _client(world, router_test_client, "c")
    asset_id = world["asset"].id
    assert client.get(f"/api/checklists/asset-readiness/{asset_id}").json()["ready"] is None

    def run(value, complete=True):
        c = client.post("/api/checklists", json={"template_id": world["asset_tpl"]["id"], "context_type": "betriebsmittel",
                                                 "operational_asset_id": asset_id}).json()
        client.put(f"/api/checklists/{c['id']}/answers/{_fields(c)['einsatzbereit']}", json={"value": value})
        if complete:
            client.post(f"/api/checklists/{c['id']}/complete")

    run("nein")
    state = client.get(f"/api/checklists/asset-readiness/{asset_id}").json()
    assert state["ready"] is False and state["created_by_name"] == "Carla Gamma"
    run("ja", complete=False)  # Entwurf zählt nicht
    assert client.get(f"/api/checklists/asset-readiness/{asset_id}").json()["ready"] is False
    run("ja")
    assert client.get(f"/api/checklists/asset-readiness/{asset_id}").json()["ready"] is True


# --- Angriffstest ---------------------------------------------------------------------------

def test_attack_foreign_checklists_by_guessed_ids(world, router_test_client):
    """Monteur C (keinem Auftrag zugeordnet) probiert jede Checklisten-/Anhang-ID durch: fremde
    Auftrags-Checkliste, fremde Betrieb-Checkliste, fremde Objekt-Checkliste einer nicht lesbaren
    Vorlage. Erlaubt ist nur, was die Regeln vorsehen -- gezählt wird jeder Durchlass."""
    a = _client(world, router_test_client, "a")
    office = _client(world, router_test_client, "office")
    order_c = _start_order(world, a)
    _fill_order_checklist(a, order_c)
    prop_c = a.post("/api/checklists", json={"template_id": world["order_tpl"]["id"], "context_type": "objekt",
                                             "property_id": world["prop"].id}).json()
    company_c = office.post("/api/checklists", json={"template_id": world["company_tpl"]["id"],
                                                     "context_type": "betrieb"}).json()
    office.post(f"/api/checklists/{company_c['id']}/attachments", data={"field_id": _fields(company_c)["tn"],
                "signer_name": "Olga"}, files={"file": ("s.png", _png(), "image/png")})
    attacker = _client(world, router_test_client, "c")
    passed = []
    for cid in (order_c["id"], prop_c["id"], company_c["id"], 9999):
        for method, url, kw in (
            ("GET", f"/api/checklists/{cid}", {}),
            ("PUT", f"/api/checklists/{cid}/answers/1", {"json": {"value": "ja"}}),
            ("POST", f"/api/checklists/{cid}/complete", {}),
            ("DELETE", f"/api/checklists/{cid}", {}),
            ("POST", f"/api/checklists/{cid}/attachments", {"data": {"field_id": 1},
                                                             "files": {"file": ("s.png", _png(), "image/png")}}),
        ):
            resp = attacker.request(method, url, **kw)
            if resp.status_code < 400:
                passed.append((method, url, resp.status_code))
    for attachment_id in range(1, 10):
        for method in ("GET", "DELETE"):
            url = f"/api/checklist-attachments/{attachment_id}" + ("/file" if method == "GET" else "")
            resp = attacker.request(method, url)
            if resp.status_code < 400:
                passed.append((method, url, resp.status_code))
    for params in ("", "?context=betrieb", f"?order_id={world['orders']['mine'].id}",
                   f"?order_id={world['orders']['foreign'].id}"):
        resp = attacker.get("/api/checklists" + params)
        if resp.status_code < 400:
            passed.append(("GET", "/api/checklists" + params, resp.status_code))
    assert passed == [], passed
