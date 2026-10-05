"""Version 1.8.13 -- Checklisten, Stufe 2, Runde 2a-1: die Unterschrift bindet den Inhalt.

Mit der ersten Unterschrift sind Antworten und Fotos gesperrt; jede Unterschrift trägt Zeitpunkt
(UTC, Anzeige in Europe/Berlin) und die SHA-256-Prüfsumme des unterschriebenen Inhalts. Weitere
Unterschriften bleiben möglich, keine wird ersetzt oder gelöscht. Nur das Büro verwirft
Unterschriften, mit Begründung. Unterschreiben, Verwerfen, Abschließen und "als repariert
markieren" stehen in der Änderungshistorie. Dazu die Angriffstests aus der Vorgabe.

Nutzt den Aufbau aus tests/test_v305_checklist_filling.py (Monteur A ist dem Auftrag zugeordnet,
Vorlage "Sicherheitscheck" mit Einzelunterschrift "sig", Vorlage "Unterweisung" (Betrieb) mit
Mehrfachunterschrift "tn").

Seit 1.8.14 versiegelt eine Unterschrift nur die Felder oberhalb von ihr (tests/test_v318_*). Beide
Vorlagen hier haben ihre Unterschrift am Ende -- diese Tests belegen damit zugleich, dass sich
solche Vorlagen wie in 1.8.13 verhalten."""

import hashlib
import json
import re

import pytest
from sqlalchemy.exc import IntegrityError

import app.audit  # noqa: F401 -- registriert die Historien-Listener, wie in Produktion app.main
import app.checklists as checklists_module
from app.berlin_time import to_berlin
from app.checklist_pdf import build_checklist_pdf
from app.checklists import SEAL_FORMAT, get_checklist_row, seal_content, signer_content
from app.models import AuditLog, Checklist, ChecklistAssetRelease, ChecklistAttachment, Customer
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v305_checklist_filling import _client, _fields, _jpeg, _png, _start_order, world  # noqa: F401

SIG = {"file": ("s.png", _png(), "image/png")}


def _photo(client, c, field_key="fotos"):
    return client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[field_key]},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")})


def _sign(client, c, name="Anna Alpha", field_key="sig"):
    return client.post(f"/api/checklists/{c['id']}/attachments",
                       data={"field_id": _fields(c)[field_key], "signer_name": name}, files=SIG)


def _signed_order_checklist(world, client):
    """Auftrags-Checkliste, ausgefüllt und von Anna unterschrieben -- noch nicht abgeschlossen."""
    c = _start_order(world, client)
    f = _fields(c)
    assert client.put(f"/api/checklists/{c['id']}/answers/{f['frei']}", json={"value": "ja"}).status_code == 200
    assert client.put(f"/api/checklists/{c['id']}/answers/{f['wind']}", json={"value": "12,5"}).status_code == 200
    assert _photo(client, c).status_code == 200
    resp = _sign(client, c)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _sig_id(body):
    """Die (einzige) gültige Unterschrift -- seit 1.8.15 wählt das Verwerfen eine Unterschrift."""
    return next(x["id"] for x in body["attachments"] if x["kind"] == "unterschrift")


def _recomputed(world, checklist_id, field_key="sig"):
    """SHA-256 des aktuellen Inhalts, so wie ihn die Unterschrift im Feld field_key versiegelt -- seit 1.8.57 samt
    Unterzeichner, Zeitpunkt und Prüfsumme des Bilds (Siegelformat 3), wie check_signature() nachrechnet."""
    world["db"].expire_all()
    checklist = get_checklist_row(world["db"], checklist_id)
    field = next(f for f in checklist.template_version.fields if f.field_key == field_key)
    sig = next((a for a in checklist.attachments if a.template_field_id == field.id and a.kind == "unterschrift"
                and a.discarded_at is None), None)
    signer = (signer_content(sig, hashlib.sha256(checklists_module.attachment_path(sig).read_bytes()).hexdigest())
              if sig is not None and sig.seal_format == SEAL_FORMAT else None)
    return hashlib.sha256(seal_content(checklist, field, signer=signer).encode("utf-8")).hexdigest()


# --- Sperre und Prüfsumme -------------------------------------------------------------------

def test_first_signature_locks_answers_and_photos_and_stores_time_and_hash(world, router_test_client):
    a = _client(world, router_test_client, "a")
    body = _signed_order_checklist(world, a)
    cid, f = body["id"], _fields(body)
    assert body["signed"] and not body["can_edit"] and body["can_sign"] and not body["can_discard_signatures"]
    sig = next(x for x in body["attachments"] if x["kind"] == "unterschrift")
    assert re.fullmatch(r"[0-9a-f]{64}", sig["content_sha256"])
    stored = world["db"].get(ChecklistAttachment, sig["id"])
    assert sig["created_at_local"] == to_berlin(stored.created_at).strftime("%d.%m.%Y %H:%M")
    assert sig["content_sha256"] == _recomputed(world, cid)  # deterministisch, auch nach Neuladen

    photo = next(x for x in body["attachments"] if x["kind"] == "foto")
    assert a.put(f"/api/checklists/{cid}/answers/{f['bem']}", json={"value": "nachträglich"}).status_code == 409
    assert a.put(f"/api/checklists/{cid}/answers/{f['frei']}", json={"value": "nein"}).status_code == 409
    assert _photo(a, body).status_code == 409
    assert a.delete(f"/api/checklist-attachments/{photo['id']}").status_code == 409
    after = a.get(f"/api/checklists/{cid}").json()
    assert after["answers"] == body["answers"] and after["attachments"] == body["attachments"]
    assert sig["content_sha256"] == _recomputed(world, cid)  # Inhalt unverändert

    # Abschließen bleibt möglich -- genau dafür wird unterschrieben.
    done = a.post(f"/api/checklists/{cid}/complete").json()
    assert done["status"] == "abgeschlossen" and not done["can_sign"]


def test_lock_applies_to_office_too(world, router_test_client):
    body = _signed_order_checklist(world, _client(world, router_test_client, "a"))
    office = _client(world, router_test_client, "office")
    f = _fields(body)
    assert office.get(f"/api/checklists/{body['id']}").json()["can_discard_signatures"] is True
    assert office.put(f"/api/checklists/{body['id']}/answers/{f['bem']}", json={"value": "Büro"}).status_code == 409
    assert _photo(office, body).status_code == 409


def test_hash_covers_answers_and_photo_files(world, router_test_client):
    """Die Summe ändert sich mit jeder Antwort und mit dem Inhalt jeder Fotodatei -- so fällt
    eine Änderung an der Sperre vorbei (direkt in Datenbank oder Datenordner) später auf."""
    a = _client(world, router_test_client, "a")
    body = _signed_order_checklist(world, a)
    cid = body["id"]
    original = next(x for x in body["attachments"] if x["kind"] == "unterschrift")["content_sha256"]
    photo = world["db"].get(ChecklistAttachment, next(x["id"] for x in body["attachments"] if x["kind"] == "foto"))
    path = checklists_module.attachment_path(photo)
    path.write_bytes(path.read_bytes() + b"x")
    assert _recomputed(world, cid) != original
    path.write_bytes(path.read_bytes()[:-1])
    assert _recomputed(world, cid) == original
    checklist = get_checklist_row(world["db"], cid)
    answer = next(x for x in checklist.answers if x.field_key == "frei")
    answer.value_text = "nein"
    world["db"].commit()
    assert _recomputed(world, cid) != original


def test_further_signatures_allowed_but_never_replaced_or_deleted(world, router_test_client):
    office = _client(world, router_test_client, "office")
    c = office.post("/api/checklists", json={"template_id": world["company_tpl"]["id"], "context_type": "betrieb"}).json()
    assert _sign(office, c, "Anna Alpha", "tn").status_code == 200
    body = _sign(office, c, "Bernd Beta", "tn").json()  # weitere Unterschrift: erlaubt
    sigs = body["attachments"]
    assert [s["signer_name"] for s in sigs] == ["Anna Alpha", "Bernd Beta"]
    # Seit 1.8.57 steht der Unterzeichner im Siegel -- zwei Unterschriften, zwei Summen; die versiegelten Felder gleich.
    assert sigs[0]["content_sha256"] != sigs[1]["content_sha256"]
    rows = [world["db"].get(ChecklistAttachment, s["id"]) for s in sigs]
    assert [json.loads(r.sealed_content)["fields"] for r in rows][0] == json.loads(rows[1].sealed_content)["fields"]
    assert office.delete(f"/api/checklist-attachments/{sigs[0]['id']}").status_code == 409
    assert office.delete(f"/api/checklists/{c['id']}").status_code == 409
    assert office.post(f"/api/checklists/{c['id']}/complete").json()["status"] == "abgeschlossen"


def test_signed_draft_cannot_be_deleted_by_owner(world, router_test_client):
    a = _client(world, router_test_client, "a")
    body = _signed_order_checklist(world, a)
    resp = a.delete(f"/api/checklists/{body['id']}")
    assert resp.status_code == 409 and "verwerfen" in resp.json()["detail"]
    assert a.get(f"/api/checklists/{body['id']}").status_code == 200


# --- Verwerfen ------------------------------------------------------------------------------

def test_office_discards_signatures_with_reason_and_unlocks(world, router_test_client):
    a = _client(world, router_test_client, "a")
    office = _client(world, router_test_client, "office")
    body = _signed_order_checklist(world, a)
    cid, f = body["id"], _fields(body)
    old = next(x for x in body["attachments"] if x["kind"] == "unterschrift")
    old_path = checklists_module.attachment_path(world["db"].get(ChecklistAttachment, old["id"]))

    resp = office.post(f"/api/checklists/{cid}/discard-signatures",
                       json={"reason": "  Windangabe falsch  ", "signature_id": old["id"]})
    assert resp.status_code == 200, resp.text
    after = resp.json()
    assert not after["signed"] and after["can_edit"] and not after["can_discard_signatures"]
    assert [x["kind"] for x in after["attachments"]] == ["foto"]
    discarded = after["discarded_signatures"]
    assert len(discarded) == 1 and discarded[0]["id"] == old["id"]
    assert discarded[0]["discard_reason"] == "Windangabe falsch" and discarded[0]["discarded_by_name"] == "Buero_auftrag"
    assert discarded[0]["discarded_at_local"] and discarded[0]["content_sha256"] == old["content_sha256"]
    assert old_path.exists()  # Nachweis bleibt, nichts gelöscht
    assert "Unterschrift Monteur" in after["missing_required"]  # verworfen zählt nicht mehr
    assert a.post(f"/api/checklists/{cid}/complete").status_code == 400

    # Wieder offen: der Monteur korrigiert und unterschreibt neu -- neue Summe über neuen Inhalt.
    assert a.put(f"/api/checklists/{cid}/answers/{f['wind']}", json={"value": "8"}).status_code == 200
    new = next(x for x in _sign(a, after).json()["attachments"] if x["kind"] == "unterschrift")
    assert new["content_sha256"] != old["content_sha256"]
    assert a.delete(f"/api/checklist-attachments/{old['id']}").status_code == 409  # verworfene bleibt
    assert office.delete(f"/api/checklist-attachments/{old['id']}").status_code == 409
    done = a.post(f"/api/checklists/{cid}/complete").json()
    assert done["status"] == "abgeschlossen" and len(done["discarded_signatures"]) == 1


def test_discard_rules(world, router_test_client):
    a = _client(world, router_test_client, "a")
    office = _client(world, router_test_client, "office")
    unsigned = _start_order(world, a)
    resp = office.post(f"/api/checklists/{unsigned['id']}/discard-signatures", json={"reason": "x"})
    assert resp.status_code == 400  # nichts zu verwerfen
    body = _signed_order_checklist(world, a)
    a.post(f"/api/checklists/{body['id']}/complete")
    resp = office.post(f"/api/checklists/{body['id']}/discard-signatures", json={"reason": "zu spät"})
    assert resp.status_code == 409  # abgeschlossen bleibt eingefroren
    assert office.post("/api/checklists/9999/discard-signatures", json={"reason": "x"}).status_code == 404


def test_pdf_shows_valid_signature_with_hash_and_omits_discarded(world, router_test_client):
    a = _client(world, router_test_client, "a")
    office = _client(world, router_test_client, "office")
    c = _start_order(world, a)
    a.put(f"/api/checklists/{c['id']}/answers/{_fields(c)['frei']}", json={"value": "ja"})
    _photo(a, c)
    wrong = _sign(a, c, "Wrong Person").json()
    office.post(f"/api/checklists/{c['id']}/discard-signatures", json={"reason": "falsche Person", "signature_id": _sig_id(wrong)})
    new = next(x for x in _sign(a, c, "Anna Alpha").json()["attachments"] if x["kind"] == "unterschrift")
    a.post(f"/api/checklists/{c['id']}/complete")
    text = _extract_pdf_text(build_checklist_pdf(world["db"], get_checklist_row(world["db"], c["id"])))
    assert b"Anna Alpha" in text and new["content_sha256"].encode() in text
    assert b"Wrong Person" not in text


# --- Änderungshistorie ----------------------------------------------------------------------

def _audit(world, **filters):
    world["db"].expire_all()
    return world["db"].query(AuditLog).filter_by(**filters).order_by(AuditLog.id).all()


def test_history_records_sign_discard_complete_and_repair(world, router_test_client):
    a = _client(world, router_test_client, "a")
    office = _client(world, router_test_client, "office")
    body = _signed_order_checklist(world, a)
    cid = str(body["id"])
    project_id = world["orders"]["mine"].project_id

    signed = _audit(world, entity_type="Checklisten-Unterschrift", action="angelegt")
    assert len(signed) == 1 and signed[0].entity_id == cid and "Anna Alpha" in signed[0].entity_label
    assert signed[0].project_id == project_id  # auch in der Historie der Projektmappe
    assert json.loads(signed[0].details)["content_sha256"] == next(x for x in body["attachments"] if x["kind"] == "unterschrift")["content_sha256"]

    office.post(f"/api/checklists/{cid}/discard-signatures", json={"reason": "Windangabe falsch", "signature_id": _sig_id(body)})
    reasons = _audit(world, entity_type="Checklisten-Unterschrift", field_name="discard_reason")
    assert [(r.action, r.new_value, r.field_label) for r in reasons] == [
        ("geändert", "Windangabe falsch", "Begründung (Verwerfen)")]

    _sign(a, body)
    a.post(f"/api/checklists/{cid}/complete")
    status = _audit(world, entity_type="Checkliste", entity_id=cid, field_name="status")
    assert [(r.old_value, r.new_value) for r in status] == [("entwurf", "abgeschlossen")]
    assert _audit(world, entity_type="Checkliste", entity_id=cid, action="angelegt")

    # Als repariert markieren -- an einer Geräte-Checkliste mit "nicht einsatzbereit".
    c = _client(world, router_test_client, "c")
    report = c.post("/api/checklists", json={"template_id": world["asset_tpl"]["id"], "context_type": "betriebsmittel",
                                             "operational_asset_id": world["asset"].id}).json()
    c.put(f"/api/checklists/{report['id']}/answers/{_fields(report)['einsatzbereit']}", json={"value": "nein"})
    c.post(f"/api/checklists/{report['id']}/complete")
    office.post(f"/api/checklists/asset-readiness/{world['asset'].id}/repaired", json={"note": "Kabel getauscht"})
    repaired = _audit(world, entity_type="Gerät als repariert markiert")
    assert len(repaired) == 1 and repaired[0].entity_id == str(report["id"])
    assert "Hubsteiger (BM-7)" in repaired[0].entity_label
    assert json.loads(repaired[0].details)["note"] == "Kabel getauscht"


def test_failed_flush_leaves_no_stale_history_entry(world, router_test_client):
    """Nebenbefund: scheitert ein Einfügen im SAVEPOINT (gleichzeitige Wiederholung derselben
    client_uuid), durfte der schon vorgemerkte Historieneintrag nicht beim nächsten Speichern
    als Geisterzeile "angelegt" mitgeschrieben werden."""
    office = _client(world, router_test_client, "office")
    c = office.post("/api/checklists", json={"template_id": world["company_tpl"]["id"], "context_type": "betrieb",
                                             "client_uuid": "dddddddd-0000-0000-0000-000000000001"}).json()
    db = world["db"]
    row = db.get(Checklist, c["id"])
    duplicate = Checklist(template_id=row.template_id, template_version_id=row.template_version_id,
                          template_label_snapshot="Dublette", context_type="betrieb", client_uuid=row.client_uuid)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(duplicate)
            db.flush()
    db.add(Customer(name="Später", last_name="Später"))
    db.commit()
    created = _audit(world, entity_type="Checkliste", action="angelegt")
    assert [r.entity_id for r in created] == [str(c["id"])], [(r.entity_id, r.entity_label) for r in created]


# --- Angriffstests --------------------------------------------------------------------------

def test_attack_change_or_remove_after_signature(world, router_test_client):
    """Monteur A (Ersteller) und das Büro probieren nach der Unterschrift alles, was den
    unterschriebenen Inhalt oder die Unterschrift selbst verändern würde. Jeder Durchlass zählt."""
    a = _client(world, router_test_client, "a")
    office = _client(world, router_test_client, "office")
    body = _signed_order_checklist(world, a)
    cid, f = body["id"], _fields(body)
    photo = next(x for x in body["attachments"] if x["kind"] == "foto")
    sig = next(x for x in body["attachments"] if x["kind"] == "unterschrift")
    passed = []
    for who, client in (("monteur", a), ("buero", office)):
        for method, url, kw in (
            ("PUT", f"/api/checklists/{cid}/answers/{f['frei']}", {"json": {"value": "nein"}}),
            ("PUT", f"/api/checklists/{cid}/answers/{f['bem']}", {"json": {"value": "neu",
                                                                           "client_uuid": "eeeeeeee-0000-0000-0000-000000000001"}}),
            ("POST", f"/api/checklists/{cid}/attachments", {"data": {"field_id": f["fotos"]},
                                                             "files": {"file": ("f.jpg", _jpeg(), "image/jpeg")}}),
            ("DELETE", f"/api/checklist-attachments/{photo['id']}", {}),
            ("DELETE", f"/api/checklist-attachments/{sig['id']}", {}),
            ("POST", f"/api/checklists/{cid}/attachments", {"data": {"field_id": f["sig"], "signer_name": "Fremd"},
                                                             "files": SIG}),
            ("DELETE", f"/api/checklists/{cid}", {}),
        ):
            resp = client.request(method, url, **kw)
            if resp.status_code != 409:
                passed.append((who, method, url, resp.status_code))
    assert passed == [], passed
    after = a.get(f"/api/checklists/{cid}").json()
    assert after["answers"] == body["answers"] and after["attachments"] == body["attachments"]
    assert sig["content_sha256"] == _recomputed(world, cid)


def test_attack_discard_as_field_worker(world, router_test_client):
    """Weder der Ersteller noch ein anderer Monteur kann Unterschriften verwerfen."""
    a = _client(world, router_test_client, "a")
    body = _signed_order_checklist(world, a)
    for who in ("a", "b", "c"):
        resp = _client(world, router_test_client, who).post(
            f"/api/checklists/{body['id']}/discard-signatures", json={"reason": "bitte entsperren"})
        assert resp.status_code == 403, (who, resp.status_code)
    assert a.get(f"/api/checklists/{body['id']}").json()["signed"] is True


@pytest.mark.parametrize("payload", [{}, {"reason": None}, {"reason": ""}, {"reason": "   "}])
def test_attack_discard_without_reason(world, router_test_client, payload):
    body = _signed_order_checklist(world, _client(world, router_test_client, "a"))
    office = _client(world, router_test_client, "office")
    resp = office.post(f"/api/checklists/{body['id']}/discard-signatures", json=payload)
    assert resp.status_code == 400 and "begründen" in resp.json()["detail"]
    assert office.get(f"/api/checklists/{body['id']}").json()["signed"] is True
    assert world["db"].query(ChecklistAttachment).filter(ChecklistAttachment.discarded_at.isnot(None)).count() == 0


@pytest.mark.parametrize("payload", [{}, {"note": None}, {"note": ""}, {"note": "  "}])
def test_attack_repaired_without_note(world, router_test_client, payload):
    c = _client(world, router_test_client, "c")
    office = _client(world, router_test_client, "office")
    report = c.post("/api/checklists", json={"template_id": world["asset_tpl"]["id"], "context_type": "betriebsmittel",
                                             "operational_asset_id": world["asset"].id}).json()
    c.put(f"/api/checklists/{report['id']}/answers/{_fields(report)['einsatzbereit']}", json={"value": "nein"})
    c.post(f"/api/checklists/{report['id']}/complete")
    url = f"/api/checklists/asset-readiness/{world['asset'].id}/repaired"
    resp = office.post(url, json=payload)
    assert resp.status_code == 400 and "Notiz" in resp.json()["detail"]
    assert world["db"].query(ChecklistAssetRelease).count() == 0
    assert office.get(f"/api/checklists/asset-readiness/{world['asset'].id}").json()["ready"] is False
    assert office.post(url, json={"note": "Kabel getauscht"}).json()["ready"] is True  # mit Notiz geht es
