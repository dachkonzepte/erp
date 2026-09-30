"""Version 1.8.14 -- Checklisten, Stufe 2, Runde 2a-1b: die Unterschrift versiegelt abschnittsweise.

Eine Unterschrift versiegelt nur die Felder, die in der Vorlage vor ihr stehen; Felder danach
bleiben bis zur nächsten Unterschrift offen. Beim Unterschreiben wird der versiegelte Inhalt als
feste Kopie abgelegt (Fassung, Feldschlüssel, Antworten, Prüfsummen der Fotos), content_sha256 ist
die Prüfsumme genau dieser Kopie. Seite (API) und PDF zeigen je Unterschrift, ob der aktuelle
Inhalt noch dazu passt. Fotos, auf die eine Unterschrift verweist -- auch eine verworfene --,
werden nie gelöscht. Dazu die Startvorlage "Heißarbeiten" in zwei Abschnitten (Daten-Migration).

Vorlage "Heißarbeit (Test)": Abschnitt 1 (frei, bereich, fotos_vorher) → sig1 (Ausführender),
Abschnitt 2 (ende, befund, fotos_nachher) → sig2 (Brandwache). Aufbau sonst aus
tests/test_v305_checklist_filling.py (Monteur A ist dem Auftrag zugeordnet)."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.checklists as checklists_module
from app.checklist_pdf import build_checklist_pdf
from app.checklist_templates import add_field, create_template, publish_draft, validate_version_for_publish
from app.checklists import get_checklist_row
from app.database import Base
from app.models import ChecklistAnswer, ChecklistAttachment, ChecklistTemplate, ChecklistTemplateVersion
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v305_checklist_filling import _client, _fields, _jpeg, _png, world  # noqa: F401

VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"


@pytest.fixture
def hot(world):
    """Vorlage mit zwei Abschnitten, veröffentlicht."""
    db = world["db"]
    t = create_template(db, label="Heißarbeit (Test)", contexts=["auftrag"])
    v = t["draft_version_id"]
    add_field(db, v, {"field_type": "hinweis", "label": "Vor Beginn lesen"})
    add_field(db, v, {"field_type": "ja_nein", "label": "Freigabe", "field_key": "frei", "required": True})
    add_field(db, v, {"field_type": "text", "label": "Arbeitsbereich", "field_key": "bereich"})
    add_field(db, v, {"field_type": "foto", "label": "Fotos vorher", "field_key": "fotos_vorher", "max_count": 3})
    add_field(db, v, {"field_type": "unterschrift", "label": "Unterschrift Ausführender", "field_key": "sig1",
                      "signer_label": "Ausführender", "required": True})
    add_field(db, v, {"field_type": "text", "label": "Ende", "field_key": "ende"})
    add_field(db, v, {"field_type": "ja_nein", "label": "Nachkontrolle ohne Befund", "field_key": "befund", "required": True})
    add_field(db, v, {"field_type": "foto", "label": "Fotos nachher", "field_key": "fotos_nachher", "max_count": 3})
    add_field(db, v, {"field_type": "unterschrift", "label": "Unterschrift Brandwache", "field_key": "sig2",
                      "signer_label": "Brandwache", "required": True})
    world["hot_tpl"] = publish_draft(db, t["id"])
    return world


def _start(world, client):
    resp = client.post("/api/checklists", json={"template_id": world["hot_tpl"]["id"], "context_type": "auftrag",
                                                "order_id": world["orders"]["mine"].id})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _put(client, c, key, value):
    return client.put(f"/api/checklists/{c['id']}/answers/{_fields(c)[key]}", json={"value": value})


def _photo(client, c, key):
    return client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[key]},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")})


def _sign(client, c, key, name="Anna Alpha"):
    return client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[key], "signer_name": name},
                       files={"file": ("s.png", _png(), "image/png")})


def _section_one_signed(world, client):
    """Abschnitt 1 ausgefüllt (mit einem Foto) und von Anna unterschrieben."""
    c = _start(world, client)
    assert _put(client, c, "frei", "ja").status_code == 200
    assert _put(client, c, "bereich", "Attika Nord").status_code == 200
    assert _photo(client, c, "fotos_vorher").status_code == 200
    resp = _sign(client, c, "sig1")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _signature(body, key):
    field_id = _fields(body)[key]
    return next(a for a in body["attachments"] if a["field_id"] == field_id)


def _ids(body, *keys):
    f = _fields(body)
    return sorted(f[k] for k in keys)


# --- Abschnittsweise Sperre -----------------------------------------------------------------

def test_signature_seals_only_the_fields_above_it(hot, router_test_client):
    body = _section_one_signed(hot, _client(hot, router_test_client, "a"))
    assert body["signed"] and body["can_edit"] and body["can_sign"]
    assert body["sealed_field_ids"] == _ids(body, "frei", "bereich", "fotos_vorher")
    assert not body["can_delete"]


def test_attack_change_above_a_signature_is_rejected(hot, router_test_client):
    """Monteurin A (Erstellerin) und das Büro probieren alles, was den Inhalt oberhalb von sig1
    verändern würde. Jeder Durchlass zählt."""
    a = _client(hot, router_test_client, "a")
    office = _client(hot, router_test_client, "office")
    body = _section_one_signed(hot, a)
    cid, f = body["id"], _fields(body)
    photo = next(x for x in body["attachments"] if x["kind"] == "foto")
    passed = []
    for who, client in (("monteur", a), ("buero", office)):
        for method, url, kw in (
            ("PUT", f"/api/checklists/{cid}/answers/{f['frei']}", {"json": {"value": "nein"}}),
            ("PUT", f"/api/checklists/{cid}/answers/{f['bereich']}", {"json": {"value": "anderswo",
                                                                                "client_uuid": "ffffffff-0000-0000-0000-000000000001"}}),
            ("PUT", f"/api/checklists/{cid}/answers/{f['bereich']}", {"json": {"value": None}}),
            ("POST", f"/api/checklists/{cid}/attachments", {"data": {"field_id": f["fotos_vorher"]},
                                                             "files": {"file": ("f.jpg", _jpeg(), "image/jpeg")}}),
            ("DELETE", f"/api/checklist-attachments/{photo['id']}", {}),
        ):
            resp = client.request(method, url, **kw)
            if resp.status_code != 409:
                passed.append((who, method, url, resp.status_code))
    assert passed == [], passed
    after = a.get(f"/api/checklists/{cid}").json()
    assert after["answers"] == body["answers"]
    assert [x["id"] for x in after["attachments"]] == [x["id"] for x in body["attachments"]]
    assert _signature(after, "sig1")["seal"]["status"] == "unveraendert"


def test_change_below_a_signature_is_allowed_until_the_next_one(hot, router_test_client):
    a = _client(hot, router_test_client, "a")
    body = _section_one_signed(hot, a)
    cid = body["id"]
    assert _put(a, body, "ende", "16:30").status_code == 200
    assert _put(a, body, "befund", "nein").status_code == 200
    assert _put(a, body, "befund", "ja").status_code == 200  # darunter bleibt alles änderbar
    added = _photo(a, body, "fotos_nachher")
    assert added.status_code == 200
    extra = [x for x in added.json()["attachments"] if x["field_id"] == _fields(body)["fotos_nachher"]]
    assert a.delete(f"/api/checklist-attachments/{extra[0]['id']}").status_code == 200  # kein Nachweis, darf weg
    assert _photo(a, body, "fotos_nachher").status_code == 200
    mid = a.get(f"/api/checklists/{cid}").json()
    assert _signature(mid, "sig1")["seal"]["status"] == "unveraendert"  # Abschnitt 2 gehört nicht dazu

    done = _sign(a, body, "sig2", "Bernd Beta").json()
    assert done["sealed_field_ids"] == _ids(done, "frei", "bereich", "fotos_vorher", "ende", "befund", "fotos_nachher")
    assert not done["can_edit"] and done["can_sign"]
    assert _put(a, body, "ende", "17:00").status_code == 409
    assert _photo(a, body, "fotos_nachher").status_code == 409
    assert a.post(f"/api/checklists/{cid}/complete").json()["status"] == "abgeschlossen"


def test_signature_order_does_not_matter_lower_signature_seals_everything_above(hot, router_test_client):
    """Unterschreibt zuerst die untere Unterschrift, ist alles darüber gesperrt -- die obere
    Unterschrift bleibt trotzdem möglich (Unterschriftsfelder sperren sich nicht gegenseitig)."""
    a = _client(hot, router_test_client, "a")
    c = _start(hot, a)
    _put(a, c, "frei", "ja")
    body = _sign(a, c, "sig2").json()
    assert body["sealed_field_ids"] == _ids(body, "frei", "bereich", "fotos_vorher", "ende", "befund", "fotos_nachher")
    assert _sign(a, c, "sig1").status_code == 200


# --- Feste Kopie ----------------------------------------------------------------------------

def test_sealed_copy_is_stored_and_the_hash_is_its_sha256(hot, router_test_client):
    a = _client(hot, router_test_client, "a")
    body = _section_one_signed(hot, a)
    sig = hot["db"].get(ChecklistAttachment, _signature(body, "sig1")["id"])
    assert sig.content_sha256 == hashlib.sha256(sig.sealed_content.encode("utf-8")).hexdigest()
    copy = json.loads(sig.sealed_content)
    checklist = get_checklist_row(hot["db"], body["id"])
    assert copy["v"] == 2 and copy["signature_field_key"] == "sig1"
    assert copy["template_version_id"] == checklist.template_version_id
    assert copy["version_no"] == checklist.template_version.version_no
    assert [e["field_key"] for e in copy["fields"]] == ["frei", "bereich", "fotos_vorher"]  # nichts von darunter
    assert copy["fields"][0]["value"] == "ja" and copy["fields"][1]["value"] == "Attika Nord"
    photo = hot["db"].get(ChecklistAttachment, next(x["id"] for x in body["attachments"] if x["kind"] == "foto"))
    file_hash = hashlib.sha256(checklists_module.attachment_path(photo).read_bytes()).hexdigest()
    assert copy["fields"][2]["photos"] == [{"id": photo.id, "sha256": file_hash}]

    _put(a, body, "befund", "ja")
    second = hot["db"].get(ChecklistAttachment, _signature(_sign(a, body, "sig2").json(), "sig2")["id"])
    keys = [e["field_key"] for e in json.loads(second.sealed_content)["fields"]]
    assert keys == ["frei", "bereich", "fotos_vorher", "ende", "befund", "fotos_nachher"]
    assert {e["field_key"]: e.get("value") for e in json.loads(second.sealed_content)["fields"]}["ende"] is None


# --- Fotos verworfener Unterschriften -------------------------------------------------------

def test_attack_photo_of_a_discarded_signature_is_never_deleted(hot, router_test_client):
    a = _client(hot, router_test_client, "a")
    office = _client(hot, router_test_client, "office")
    body = _section_one_signed(hot, a)
    cid = body["id"]
    photo = next(x for x in body["attachments"] if x["kind"] == "foto")
    path = checklists_module.attachment_path(hot["db"].get(ChecklistAttachment, photo["id"]))
    after = office.post(f"/api/checklists/{cid}/discard-signatures",
                        json={"reason": "Bereich falsch", "signature_id": _signature(body, "sig1")["id"]}).json()
    assert after["sealed_field_ids"] == [] and after["can_edit"] and not after["can_delete"]
    assert [x["bound_by_signature"] for x in after["attachments"]] == [True]  # die Seite zeigt kein ×

    assert _put(a, after, "bereich", "Attika Süd").status_code == 200  # wieder offen
    passed = []
    for who, client in (("monteur", a), ("buero", office)):
        for url in (f"/api/checklist-attachments/{photo['id']}", f"/api/checklists/{cid}"):
            resp = client.delete(url)
            if resp.status_code != 409:
                passed.append((who, url, resp.status_code))
    assert passed == [], passed
    assert path.exists() and hot["db"].get(ChecklistAttachment, photo["id"]) is not None
    # Ein Foto, das erst nach dem Verwerfen dazukam, gehört zu keiner Unterschrift -- darf weg.
    new = next(x for x in _photo(a, after, "fotos_vorher").json()["attachments"]
               if x["kind"] == "foto" and x["id"] != photo["id"])
    assert new["bound_by_signature"] is False
    assert a.delete(f"/api/checklist-attachments/{new['id']}").status_code == 200


# --- Abweichung sichtbar machen -------------------------------------------------------------

def _pdf_text(db, checklist_id):
    db.expire_all()
    return _extract_pdf_text(build_checklist_pdf(db, get_checklist_row(db, checklist_id)))


def test_attack_answer_changed_in_the_database_shows_as_deviation(hot, router_test_client):
    a = _client(hot, router_test_client, "a")
    db = hot["db"]
    body = _section_one_signed(hot, a)
    cid = body["id"]
    _put(a, body, "ende", "16:30")
    _put(a, body, "befund", "ja")
    _photo(a, body, "fotos_nachher")
    _sign(a, body, "sig2", "Bernd Beta")
    done = a.post(f"/api/checklists/{cid}/complete").json()
    assert [_signature(done, k)["seal"]["status"] for k in ("sig1", "sig2")] == ["unveraendert", "unveraendert"]
    text = _pdf_text(db, cid)
    assert text.count(b"Inhalt unver") == 3 and b"weicht" not in text  # zwei Unterschriften + Abschluss (seit 1.8.15)

    # An der Sperre vorbei: Antwort in Abschnitt 2 direkt in der Datenbank geändert.
    answer = db.scalar(select(ChecklistAnswer).where(ChecklistAnswer.checklist_id == cid, ChecklistAnswer.field_key == "ende"))
    answer.value_text = "18:00"
    db.commit()
    seen = a.get(f"/api/checklists/{cid}").json()
    assert _signature(seen, "sig1")["seal"]["status"] == "unveraendert"  # Abschnitt 1 ist unberührt
    sig2 = _signature(seen, "sig2")["seal"]
    assert sig2["status"] == "abweichend" and sig2["changed_fields"] == ["Ende"]
    assert sig2["text"] == "Inhalt weicht von der Prüfsumme ab: Ende."
    text = _pdf_text(db, cid)
    assert text.count(b"weicht von der Pr") == 2 and b"ab: Ende." in text  # sig2 + Abschluss

    # Und in Abschnitt 1: beide Unterschriften zeigen es.
    answer = db.scalar(select(ChecklistAnswer).where(ChecklistAnswer.checklist_id == cid, ChecklistAnswer.field_key == "bereich"))
    answer.value_text = "Attika Süd"
    db.commit()
    seen = a.get(f"/api/checklists/{cid}").json()
    assert [_signature(seen, k)["seal"]["changed_fields"] for k in ("sig1", "sig2")] == [["Arbeitsbereich"], ["Arbeitsbereich", "Ende"]]
    assert _pdf_text(db, cid).count(b"weicht von der Pr") == 3  # beide Unterschriften + Abschluss


def test_photo_file_changed_on_disk_shows_as_deviation(hot, router_test_client):
    a = _client(hot, router_test_client, "a")
    body = _section_one_signed(hot, a)
    photo = hot["db"].get(ChecklistAttachment, next(x["id"] for x in body["attachments"] if x["kind"] == "foto"))
    path = checklists_module.attachment_path(photo)
    path.write_bytes(path.read_bytes() + b"x")
    seal = _signature(a.get(f"/api/checklists/{body['id']}").json(), "sig1")["seal"]
    assert seal["status"] == "abweichend" and seal["changed_fields"] == ["Fotos vorher"]


def test_tampered_copy_is_reported_and_still_protects_photos(hot, router_test_client):
    """Wird die abgelegte Kopie selbst verändert, passt sie nicht mehr zu ihrer Prüfsumme -- das
    wird gemeldet, und sie kann kein Foto zum Löschen freigeben."""
    a = _client(hot, router_test_client, "a")
    office = _client(hot, router_test_client, "office")
    body = _section_one_signed(hot, a)
    sig = hot["db"].get(ChecklistAttachment, _signature(body, "sig1")["id"])
    copy = json.loads(sig.sealed_content)
    copy["fields"][2]["photos"] = []  # Foto aus der Kopie "entfernt"
    sig.sealed_content = json.dumps(copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    hot["db"].commit()
    seen = a.get(f"/api/checklists/{body['id']}").json()
    assert _signature(seen, "sig1")["seal"]["status"] == "kopie_veraendert"
    office.post(f"/api/checklists/{body['id']}/discard-signatures",
                json={"reason": "Test", "signature_id": _signature(body, "sig1")["id"]})
    photo = next(x for x in body["attachments"] if x["kind"] == "foto")
    assert a.delete(f"/api/checklist-attachments/{photo['id']}").status_code == 409


# --- Unterschriften von vor 1.8.14 ----------------------------------------------------------

def test_signature_without_copy_still_seals_the_whole_checklist(hot, router_test_client):
    a = _client(hot, router_test_client, "a")
    body = _section_one_signed(hot, a)
    sig = hot["db"].get(ChecklistAttachment, _signature(body, "sig1")["id"])
    checklist = get_checklist_row(hot["db"], body["id"])
    sig.sealed_content = None  # so sieht eine 1.8.13-Unterschrift aus
    sig.content_sha256 = checklists_module._legacy_content_sha256(checklist)
    hot["db"].commit()
    seen = a.get(f"/api/checklists/{body['id']}").json()
    assert seen["sealed_field_ids"] == _ids(seen, "frei", "bereich", "fotos_vorher", "ende", "befund", "fotos_nachher")
    assert _signature(seen, "sig1")["seal"]["status"] == "unveraendert"
    assert _put(a, body, "ende", "16:30").status_code == 409
    sig.content_sha256 = None  # vor 1.8.13: keine Prüfsumme
    hot["db"].commit()
    assert _signature(a.get(f"/api/checklists/{body['id']}").json(), "sig1")["seal"]["status"] == "ohne_pruefsumme"


# --- Startvorlage Heißarbeiten (Daten-Migration) --------------------------------------------

def _load(name_part):
    path = next(VERSIONS.glob(f"*_{name_part}.py"))
    spec = importlib.util.spec_from_file_location(name_part, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def starter():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        _load("checklisten_startvorlagen").insert_starter_templates(conn)
    db = sessionmaker(bind=engine)()
    try:
        yield _load("heissarbeiten_zwei_unterschriften"), engine, db
    finally:
        db.close()


def _hot_version(db):
    template = db.scalar(select(ChecklistTemplate).where(ChecklistTemplate.label == "Heißarbeiten mit Brandwache"))
    return template, db.scalars(select(ChecklistTemplateVersion).where(ChecklistTemplateVersion.template_id == template.id)).one()


def test_hot_work_starter_template_gets_two_sections(starter):
    mig, engine, db = starter
    with engine.begin() as conn:
        assert mig.split_hot_work_template(conn) is True
        assert mig.split_hot_work_template(conn) is False  # zweiter Lauf: nichts mehr zu tun
    template, version = _hot_version(db)
    keys = [f.field_key for f in version.fields]
    first, second = keys.index("unterschrift_ausfuehrender"), keys.index("unterschrift_brandwache")
    assert keys[:first] == ["hinweis_pruefung", "freigabe_auftraggeber", "arbeitsbereich", "geraete_ok", "brennbares",
                            "loeschmittel", "brandwache_name", "beginn"]
    assert keys[first + 1:second] == ["ende", "nachkontrolle_bis", "nachkontrolle_ohne_befund", "fotos"]
    assert second == len(keys) - 1
    groups = {f.field_key: f.group_name for f in version.fields}
    assert groups["hinweis_pruefung"] is None and groups["beginn"] == groups["unterschrift_ausfuehrender"] == "Freigabe vor Arbeitsbeginn"
    assert groups["ende"] == groups["unterschrift_brandwache"] == "Nachkontrolle"
    assert all(f.help_text for f in version.fields if f.field_type == "unterschrift")
    assert validate_version_for_publish(template, version) == []

    with engine.begin() as conn:
        assert mig.join_hot_work_template(conn) is True  # downgrade
    db.expire_all()
    _template, version = _hot_version(db)
    assert [f.field_key for f in version.fields] == mig.ORIGINAL_ORDER
    assert all(f.group_name is None for f in version.fields)
    assert all(f.help_text is None for f in version.fields if f.field_type == "unterschrift")


def test_hot_work_template_changed_by_the_office_is_left_alone(starter):
    mig, engine, db = starter
    template, version = _hot_version(db)
    publish_draft(db, template.id)  # vom Büro veröffentlicht -- gehört jetzt dem Betrieb
    with engine.begin() as conn:
        assert mig.split_hot_work_template(conn) is False
    db.expire_all()
    assert [f.field_key for f in _hot_version(db)[1].fields] == mig.ORIGINAL_ORDER


def test_hot_work_template_in_use_keeps_end_and_check_open_after_the_first_signature(hot, router_test_client):
    """Ende zu Ende mit der echten Startvorlage: Erlaubnisschein vor Arbeitsbeginn unterschreiben,
    danach Ende und Nachkontrolle nachtragen, Brandwache unterschreibt, abschließen."""
    db = hot["db"]
    _load("checklisten_startvorlagen").insert_starter_templates(db.connection())
    assert _load("heissarbeiten_zwei_unterschriften").split_hot_work_template(db.connection()) is True
    db.commit()
    template = db.scalar(select(ChecklistTemplate).where(ChecklistTemplate.label == "Heißarbeiten mit Brandwache"))
    publish_draft(db, template.id)
    a = _client(hot, router_test_client, "a")
    c = a.post("/api/checklists", json={"template_id": template.id, "context_type": "auftrag",
                                        "order_id": hot["orders"]["mine"].id}).json()
    for key, value in (("arbeitsbereich", "Attika"), ("geraete_ok", "ja"), ("brennbares", "ja"),
                       ("loeschmittel", ["pulver"]), ("brandwache_name", "Bernd Beta"), ("beginn", "2026-09-30T08:00")):
        assert _put(a, c, key, value).status_code == 200, key
    assert _sign(a, c, "unterschrift_ausfuehrender").status_code == 200
    assert _put(a, c, "arbeitsbereich", "anders").status_code == 409
    for key, value in (("ende", "2026-09-30T10:00"), ("nachkontrolle_bis", "2026-09-30T12:00"),
                       ("nachkontrolle_ohne_befund", "ja")):
        assert _put(a, c, key, value).status_code == 200, key
    assert _sign(a, c, "unterschrift_brandwache", "Bernd Beta").status_code == 200
    done = a.post(f"/api/checklists/{c['id']}/complete").json()
    assert done["status"] == "abgeschlossen"
    assert [x["seal"]["status"] for x in done["attachments"] if x["kind"] == "unterschrift"] == ["unveraendert"] * 2
