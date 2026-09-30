"""Version 1.8.15 -- Checklisten, Stufe 2, Runde 2a-1c: Verwerfen je Unterschrift, Abschluss mit
Prüfsumme, zwei Startvorlagen in Abschnitten.

1. Verwerfen wählt EINE Unterschrift; mit ihr fallen alle Unterschriften in Feldern, die in der
   Vorlage nach ihrem Feld stehen. Unterschriften im selben Feld bleiben. Begründung Pflicht.
2. Abschließen legt wie eine Unterschrift eine feste Kopie ab -- aller Felder samt Unterschriften --
   mit Prüfsumme; Seite (API) und PDF zeigen "Inhalt unverändert" oder "weicht ab". Vorher
   abgeschlossene Checklisten bleiben ohne Prüfsumme.
3. Startvorlagen "Nachtragsmeldung" und "Entsorgungsnachweis" in je zwei Abschnitte, nur als
   unveränderter Entwurf (Daten-Migration 803d94127c12).

Aufbau aus tests/test_v305_checklist_filling.py (Monteurin A ist dem Auftrag zugeordnet) mit den
ECHTEN Startvorlagen Heißarbeiten (zwei Abschnitte seit 1.8.14) und Sicherheitsunterweisung."""

import hashlib
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.audit  # noqa: F401 -- registriert die Historien-Listener, wie in Produktion app.main
import app.checklists as checklists_module
from app.checklist_templates import publish_draft, validate_version_for_publish
from app.checklists import get_checklist_row
from app.database import Base
from app.models import (
    AuditLog, Checklist, ChecklistAnswer, ChecklistAttachment, ChecklistTemplate, ChecklistTemplateRule,
    ChecklistTemplateVersion,
)
from tests.test_v305_checklist_filling import _client, _fields, world  # noqa: F401
from tests.test_v318_checklist_signature_sections import _load, _pdf_text, _photo, _put, _sign

HOT = "Heißarbeiten mit Brandwache"
BRIEFING = "Sicherheitsunterweisung"
EXTRA = "Nachtragsmeldung"
DISPOSAL = "Entsorgungsnachweis"
RELEASE_KEYS = ("arbeitsbereich", "geraete_ok", "brennbares", "loeschmittel", "brandwache_name", "beginn")


@pytest.fixture
def starters(world):
    """Alle Startvorlagen wie nach dem Einspielen von 1.8.15, die vier hier gebrauchten veröffentlicht."""
    db = world["db"]
    _load("checklisten_startvorlagen").insert_starter_templates(db.connection())
    assert _load("heissarbeiten_zwei_unterschriften").split_hot_work_template(db.connection()) is True
    assert _load("startvorlagen_nachtrag_entsorgung").split_starter_templates(db.connection()) == [EXTRA, DISPOSAL]
    db.commit()
    world["tpl"] = {}
    for label in (HOT, BRIEFING, EXTRA, DISPOSAL):
        template = db.scalar(select(ChecklistTemplate).where(ChecklistTemplate.label == label))
        world["tpl"][label] = publish_draft(db, template.id)["id"]
    return world


def _start(world, client, label, context="auftrag"):
    payload = {"template_id": world["tpl"][label], "context_type": context}
    if context == "auftrag":
        payload["order_id"] = world["orders"]["mine"].id
    resp = client.post("/api/checklists", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fill(client, c, values):
    for key, value in values:
        resp = _put(client, c, key, value)
        assert resp.status_code == 200, (key, resp.text)


def _sigs(body, key=None):
    """Gültige Unterschriften als {Name: Anhang} -- optional nur eines Felds."""
    field_id = _fields(body)[key] if key else None
    return {a["signer_name"]: a for a in body["attachments"]
            if a["kind"] == "unterschrift" and (field_id is None or a["field_id"] == field_id)}


def _discard(client, c, signature_id, reason="Korrektur nötig"):
    return client.post(f"/api/checklists/{c['id']}/discard-signatures", json={"reason": reason, "signature_id": signature_id})


def _hot_signed_twice(world, a):
    """Heißarbeiten: Freigabe ausgefüllt und von Anna unterschrieben, Nachkontrolle ausgefüllt (mit
    Foto) und von der Brandwache Bernd unterschrieben -- noch nicht abgeschlossen."""
    c = _start(world, a, HOT)
    _fill(a, c, zip(RELEASE_KEYS, ("Attika", "ja", "ja", ["pulver"], "Bernd Beta", "2026-09-30T08:00")))
    assert _sign(a, c, "unterschrift_ausfuehrender", "Anna Alpha").status_code == 200
    _fill(a, c, (("ende", "2026-09-30T10:00"), ("nachkontrolle_bis", "2026-09-30T12:00"), ("nachkontrolle_ohne_befund", "ja")))
    assert _photo(a, c, "fotos").status_code == 200
    resp = _sign(a, c, "unterschrift_brandwache", "Bernd Beta")
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- 1. Verwerfen je Unterschrift -----------------------------------------------------------

def test_attack_discard_fire_watch_reopens_check_but_release_stays_sealed(starters, router_test_client):
    """Brandwache verwerfen: die Nachkontrolle wird wieder änderbar, die Freigabe bleibt gesperrt --
    für die Monteurin wie fürs Büro. Jeder Durchlass oberhalb zählt."""
    a = _client(starters, router_test_client, "a")
    office = _client(starters, router_test_client, "office")
    body = _hot_signed_twice(starters, a)
    release, watch = _sigs(body)["Anna Alpha"], _sigs(body)["Bernd Beta"]
    assert release["discards_with"] == [watch["id"]] and watch["discards_with"] == []

    resp = _discard(office, body, watch["id"], "Nachkontrolle zu früh beendet")
    assert resp.status_code == 200, resp.text
    after = resp.json()
    assert list(_sigs(after)) == ["Anna Alpha"] and _sigs(after)["Anna Alpha"]["seal"]["status"] == "unveraendert"
    assert [(d["signer_name"], d["discard_reason"]) for d in after["discarded_signatures"]] == [
        ("Bernd Beta", "Nachkontrolle zu früh beendet")]
    f = _fields(after)
    assert set(after["sealed_field_ids"]) == {f[k] for k in ("freigabe_auftraggeber", *RELEASE_KEYS)}

    _fill(a, after, (("ende", "2026-09-30T11:00"), ("nachkontrolle_bis", "2026-09-30T13:00"),
                     ("nachkontrolle_ohne_befund", "nein")))
    passed = []
    for who, client in (("monteur", a), ("buero", office)):
        for key, value in (("arbeitsbereich", "anderswo"), ("geraete_ok", "nein"), ("beginn", "2026-09-30T09:00"),
                           ("brandwache_name", None), ("loeschmittel", ["co2"])):
            resp = _put(client, after, key, value)
            if resp.status_code != 409:
                passed.append((who, key, resp.status_code))
    assert passed == [], passed
    seen = a.get(f"/api/checklists/{body['id']}").json()
    assert seen["answers"][str(f["arbeitsbereich"])]["value"] == "Attika"
    assert seen["answers"][str(f["nachkontrolle_ohne_befund"])]["value"] == "nein"
    # Die Brandwache unterschreibt neu, danach ist die Liste abschließbar.
    assert _sign(a, after, "unterschrift_brandwache", "Bernd Beta").status_code == 200
    assert a.post(f"/api/checklists/{body['id']}/complete").json()["status"] == "abgeschlossen"


def test_discard_release_takes_the_fire_watch_with_it(starters, router_test_client):
    a = _client(starters, router_test_client, "a")
    office = _client(starters, router_test_client, "office")
    body = _hot_signed_twice(starters, a)
    after = _discard(office, body, _sigs(body)["Anna Alpha"]["id"], "Arbeitsbereich falsch").json()
    assert _sigs(after) == {} and not after["signed"] and after["sealed_field_ids"] == []
    assert sorted(d["signer_name"] for d in after["discarded_signatures"]) == ["Anna Alpha", "Bernd Beta"]
    assert {d["discard_reason"] for d in after["discarded_signatures"]} == {"Arbeitsbereich falsch"}
    assert _put(a, after, "arbeitsbereich", "Attika Süd").status_code == 200


def test_discard_one_participant_keeps_the_others(starters, router_test_client):
    """Unterweisung: eine Teilnehmer-Unterschrift verwerfen -- die anderen Teilnehmer bleiben, die
    Unterschrift des Unterweisenden (Feld darunter) fällt mit."""
    office = _client(starters, router_test_client, "office")
    c = _start(starters, office, BRIEFING, "betrieb")
    _fill(office, c, (("inhalt", "Absturzsicherung"), ("unterweisender", "Olga Office"), ("zeitpunkt", "2026-09-30T07:00")))
    for name in ("Anna Alpha", "Bernd Beta", "Carla Gamma"):
        assert _sign(office, c, "teilnehmer", name).status_code == 200
    body = _sign(office, c, "unterschrift_unterweisender", "Olga Office").json()
    teacher = _sigs(body)["Olga Office"]
    assert _sigs(body, "teilnehmer")["Bernd Beta"]["discards_with"] == [teacher["id"]]

    after = _discard(office, body, _sigs(body, "teilnehmer")["Bernd Beta"]["id"], "falsche Person").json()
    assert list(_sigs(after, "teilnehmer")) == ["Anna Alpha", "Carla Gamma"]
    assert [s["seal"]["status"] for s in _sigs(after, "teilnehmer").values()] == ["unveraendert"] * 2
    assert sorted(d["signer_name"] for d in after["discarded_signatures"]) == ["Bernd Beta", "Olga Office"]
    f = _fields(after)
    assert set(after["sealed_field_ids"]) == {f[k] for k in ("themen", "inhalt", "unterweisender", "zeitpunkt", "dauer")}
    assert _put(office, after, "inhalt", "anders").status_code == 409  # die übrigen Teilnehmer sperren weiter
    assert _sign(office, c, "teilnehmer", "Bernd Beta").status_code == 200
    assert _sign(office, c, "unterschrift_unterweisender", "Olga Office").status_code == 200


def test_attack_discard_foreign_or_invalid_signature(starters, router_test_client):
    """Das Büro schickt an Checkliste Y die Unterschrift einer anderen Checkliste X, ein Foto, eine
    schon verworfene oder gar keine Unterschrift. Nichts davon verwirft etwas."""
    a = _client(starters, router_test_client, "a")
    office = _client(starters, router_test_client, "office")
    x = _hot_signed_twice(starters, a)
    y = _hot_signed_twice(starters, a)
    photo = next(p for p in y["attachments"] if p["kind"] == "foto")
    answers = []
    for payload in ({"signature_id": _sigs(x)["Bernd Beta"]["id"]}, {"signature_id": photo["id"]},
                    {"signature_id": 999_999}, {}, {"signature_id": None}):
        resp = office.post(f"/api/checklists/{y['id']}/discard-signatures", json={"reason": "Test", **payload})
        answers.append(resp.status_code)
    assert answers == [404, 404, 404, 400, 400]
    db = starters["db"]
    db.expire_all()
    assert db.query(ChecklistAttachment).filter(ChecklistAttachment.discarded_at.isnot(None)).count() == 0

    _discard(office, y, _sigs(y)["Bernd Beta"]["id"])
    resp = _discard(office, y, _sigs(y)["Bernd Beta"]["id"])
    assert resp.status_code == 400 and "bereits verworfen" in resp.json()["detail"]
    resp = office.post(f"/api/checklists/{y['id']}/discard-signatures", json={"signature_id": _sigs(y)["Anna Alpha"]["id"]})
    assert resp.status_code == 400 and "begründen" in resp.json()["detail"]
    assert _discard(a, y, _sigs(y)["Anna Alpha"]["id"]).status_code == 403  # Monteurin: nie
    assert list(_sigs(a.get(f"/api/checklists/{x['id']}").json())) == ["Anna Alpha", "Bernd Beta"]


# --- 2. Abschluss mit Prüfsumme -------------------------------------------------------------

def _completed_hot(starters, a):
    body = _hot_signed_twice(starters, a)
    done = a.post(f"/api/checklists/{body['id']}/complete").json()
    assert done["status"] == "abgeschlossen"
    return done


def test_completion_stores_copy_of_all_fields_and_signatures(starters, router_test_client):
    a = _client(starters, router_test_client, "a")
    db = starters["db"]
    done = _completed_hot(starters, a)
    checklist = db.get(Checklist, done["id"])
    assert checklist.content_sha256 == hashlib.sha256(checklist.sealed_content.encode("utf-8")).hexdigest()
    assert done["completion_sha256"] == checklist.content_sha256
    assert done["completion_seal"] == {"status": "unveraendert", "changed_fields": [],
                                       "text": "Inhalt unverändert – passt zur Prüfsumme."}
    copy = json.loads(checklist.sealed_content)
    assert copy["v"] == 2 and copy["sealed_by"] == "abschluss" and copy["checklist_id"] == done["id"]
    keys = [f.field_key for f in checklist.template_version.fields if f.field_type != "hinweis"]
    assert [e["field_key"] for e in copy["fields"]] == keys  # alle Felder, auch beide Unterschriften
    by_key = {e["field_key"]: e for e in copy["fields"]}
    watch = db.get(ChecklistAttachment, _sigs(done)["Bernd Beta"]["id"])
    assert by_key["unterschrift_brandwache"]["signatures"] == [{
        "id": watch.id, "signer_name": "Bernd Beta", "signed_at": watch.created_at.isoformat(),
        "content_sha256": watch.content_sha256,
        "sha256": hashlib.sha256(checklists_module.attachment_path(watch).read_bytes()).hexdigest(),
    }]
    assert by_key["arbeitsbereich"]["value"] == "Attika" and len(by_key["fotos"]["photos"]) == 1
    text = _pdf_text(db, done["id"])
    assert b"Abschluss" in text and checklist.content_sha256.encode() in text and text.count(b"Inhalt unver") == 3
    # Änderungshistorie: die Prüfsumme des Abschlusses steht darin, die Kopie selbst nicht.
    history = db.query(AuditLog).filter_by(entity_type="Checkliste", entity_id=str(done["id"]))
    assert [r.new_value for r in history.filter_by(field_name="content_sha256")] == [checklist.content_sha256]
    assert history.filter_by(field_name="sealed_content").count() == 0


def test_attack_changes_after_completion_show_as_deviation(starters, router_test_client):
    """An der Sperre vorbei, direkt in der Datenbank bzw. an der Datei: ein Unterschriftsname (den
    keine Unterschrift selbst abdeckt), eine Antwort, ein Unterschriftsbild. Seite und PDF zeigen
    jede Änderung am Abschluss."""
    a = _client(starters, router_test_client, "a")
    db = starters["db"]
    done = _completed_hot(starters, a)
    cid = done["id"]

    watch = db.get(ChecklistAttachment, _sigs(done)["Bernd Beta"]["id"])
    watch.signer_name = "Mallory"
    db.commit()
    seen = a.get(f"/api/checklists/{cid}").json()
    assert seen["completion_seal"]["status"] == "abweichend"
    assert seen["completion_seal"]["text"] == "Inhalt weicht von der Prüfsumme ab: Unterschrift Brandwache."
    assert [s["seal"]["status"] for s in _sigs(seen).values()] == ["unveraendert"] * 2  # nur der Abschluss sieht es
    assert _pdf_text(db, cid).count(b"weicht von der Pr") == 1
    watch.signer_name = "Bernd Beta"
    db.commit()
    assert a.get(f"/api/checklists/{cid}").json()["completion_seal"]["status"] == "unveraendert"

    answer = db.scalar(select(ChecklistAnswer).where(ChecklistAnswer.checklist_id == cid,
                                                     ChecklistAnswer.field_key == "nachkontrolle_ohne_befund"))
    answer.value_text = "nein"
    db.commit()
    seen = a.get(f"/api/checklists/{cid}").json()
    assert seen["completion_seal"]["changed_fields"] == ["Nachkontrolle ohne Befund"]
    assert _pdf_text(db, cid).count(b"weicht von der Pr") == 2  # Brandwache + Abschluss
    answer.value_text = "ja"
    db.commit()

    path = checklists_module.attachment_path(db.get(ChecklistAttachment, _sigs(done)["Anna Alpha"]["id"]))
    path.write_bytes(path.read_bytes() + b"x")
    seen = a.get(f"/api/checklists/{cid}").json()
    assert seen["completion_seal"]["changed_fields"] == ["Unterschrift Ausführender"]


def test_tampered_completion_copy_is_reported(starters, router_test_client):
    a = _client(starters, router_test_client, "a")
    db = starters["db"]
    done = _completed_hot(starters, a)
    checklist = db.get(Checklist, done["id"])
    copy = json.loads(checklist.sealed_content)
    copy["fields"][0]["value"] = "nein"
    checklist.sealed_content = json.dumps(copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    db.commit()
    assert a.get(f"/api/checklists/{done['id']}").json()["completion_seal"]["status"] == "kopie_veraendert"


def test_completed_before_the_copy_stays_without_hash(starters, router_test_client):
    a = _client(starters, router_test_client, "a")
    db = starters["db"]
    done = _completed_hot(starters, a)
    checklist = db.get(Checklist, done["id"])
    checklist.sealed_content = None  # so sieht eine vor 1.8.15 abgeschlossene Checkliste aus
    checklist.content_sha256 = None
    db.commit()
    seen = a.get(f"/api/checklists/{done['id']}").json()
    assert seen["completion_sha256"] is None
    assert seen["completion_seal"] == {"status": "ohne_pruefsumme", "changed_fields": [],
                                       "text": "Ohne Prüfsumme abgeschlossen (älterer Stand) – nicht prüfbar."}
    text = _pdf_text(db, done["id"])
    assert b"Ohne Pr" in text and b"Versiegelt alle Angaben" not in text


def test_draft_has_no_completion_seal(starters, router_test_client):
    a = _client(starters, router_test_client, "a")
    body = _hot_signed_twice(starters, a)
    assert body["completion_seal"] is None and body["completion_sha256"] is None
    assert starters["db"].get(Checklist, body["id"]).sealed_content is None


# --- 3. Startvorlagen Nachtragsmeldung und Entsorgungsnachweis ------------------------------

@pytest.fixture
def fresh_starters():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        _load("checklisten_startvorlagen").insert_starter_templates(conn)
    db = sessionmaker(bind=engine)()
    try:
        yield _load("startvorlagen_nachtrag_entsorgung"), engine, db
    finally:
        db.close()


def _version(db, label):
    template = db.scalar(select(ChecklistTemplate).where(ChecklistTemplate.label == label))
    return template, db.scalars(select(ChecklistTemplateVersion).where(ChecklistTemplateVersion.template_id == template.id)).one()


def test_starter_templates_get_two_sections_and_back(fresh_starters):
    mig, engine, db = fresh_starters
    with engine.begin() as conn:
        assert mig.split_starter_templates(conn) == [EXTRA, DISPOSAL]
        assert mig.split_starter_templates(conn) == []  # zweiter Lauf: nichts mehr zu tun
    expected = {
        EXTRA: (["hinweis_pruefung", "hinweis_keine_zusage"],
                ["art", "beschreibung", "menge", "einheit", "angeordnet_durch", "unterschrift_kunde"],
                ["zeitaufwand", "material", "bereits_ausgefuehrt", "fotos", "unterschrift_monteur"],
                ("Anordnung", "Ausführung"), "unterschrift_monteur", "Monteur"),
        DISPOSAL: (["hinweis_pruefung"],
                   ["abfallart", "menge", "einheit", "entsorger", "uebergabe", "unterschrift_monteur"],
                   ["beleg_nr", "beleg_foto", "bemerkung", "unterschrift_beleg"],
                   ("Übergabe", "Beleg"), "unterschrift_beleg", "Monteur/Büro"),
    }
    for label, (head, first, second, groups, new_key, signer) in expected.items():
        template, version = _version(db, label)
        assert [f.field_key for f in version.fields] == head + first + second, label
        by_key = {f.field_key: f for f in version.fields}
        assert [by_key[k].group_name for k in head] == [None] * len(head)
        assert {by_key[k].group_name for k in first} == {groups[0]} and {by_key[k].group_name for k in second} == {groups[1]}
        new = by_key[new_key]
        assert (new.field_type, new.signer_label, new.required, new.multiple, new.max_count) == \
            ("unterschrift", signer, False, False, 1)
        assert all(f.help_text for f in version.fields if f.field_type == "unterschrift")
        assert validate_version_for_publish(template, version) == [], label

    with engine.begin() as conn:
        assert mig.join_starter_templates(conn) == [EXTRA, DISPOSAL]  # downgrade
    db.expire_all()
    for spec in mig.SPECS:
        _template, version = _version(db, spec["label"])
        assert [(f.field_key, f.sort_order) for f in version.fields] == mig.layout(spec["original"])
        assert all(f.group_name is None for f in version.fields)
        assert all(f.help_text is None for f in version.fields if f.field_type == "unterschrift")


def test_changed_starter_templates_are_left_alone(fresh_starters):
    mig, engine, db = fresh_starters
    template, _version_row = _version(db, EXTRA)
    publish_draft(db, template.id)  # vom Büro veröffentlicht -- gehört jetzt dem Betrieb
    _template, version = _version(db, DISPOSAL)
    next(f for f in version.fields if f.field_key == "bemerkung").sort_order = 15  # vom Büro umsortiert
    db.commit()
    with engine.begin() as conn:
        assert mig.split_starter_templates(conn) == []
    db.expire_all()
    assert "unterschrift_monteur" not in [f.field_key for f in _version(db, EXTRA)[1].fields]


def test_downgrade_keeps_a_new_signature_the_office_uses_in_a_rule(fresh_starters):
    mig, engine, db = fresh_starters
    with engine.begin() as conn:
        mig.split_starter_templates(conn)
    _template, version = _version(db, DISPOSAL)
    db.add(ChecklistTemplateRule(version_id=version.id, field_key="unterschrift_beleg", operator="ausgefuellt",
                                 task_title="Beleg prüfen", task_priority="normal", assignee_mode="rolle",
                                 min_visible_role="buero_auftrag", sort_order=10))
    db.commit()
    with engine.begin() as conn:
        assert mig.join_starter_templates(conn) == [EXTRA]
    db.expire_all()
    assert "unterschrift_beleg" in [f.field_key for f in _version(db, DISPOSAL)[1].fields]


def test_extra_work_customer_signs_the_order_execution_stays_open(starters, router_test_client):
    """Nachtragsmeldung Ende zu Ende: der Kunde unterschreibt die Anordnung, Fotos und "bereits
    ausgeführt" bleiben offen, der Monteur unterschreibt nach der Ausführung."""
    a = _client(starters, router_test_client, "a")
    c = _start(starters, a, EXTRA)
    _fill(a, c, (("art", "zusatzleistung"), ("beschreibung", "Zweiter Lichtkuppelrahmen"), ("angeordnet_durch", "Hr. Kunde")))
    assert _sign(a, c, "unterschrift_kunde", "Karl Kunde").status_code == 200
    assert _put(a, c, "beschreibung", "anders").status_code == 409
    _fill(a, c, (("zeitaufwand", "3"), ("bereits_ausgefuehrt", "ja")))
    assert _photo(a, c, "fotos").status_code == 200
    assert _sign(a, c, "unterschrift_monteur", "Anna Alpha").status_code == 200
    done = a.post(f"/api/checklists/{c['id']}/complete").json()
    assert done["status"] == "abgeschlossen" and done["completion_seal"]["status"] == "unveraendert"
    assert [s["seal"]["status"] for s in _sigs(done).values()] == ["unveraendert"] * 2


def test_disposal_handover_signed_receipt_stays_open(starters, router_test_client):
    """Entsorgungsnachweis Ende zu Ende: Übergabe unterschreiben, Beleg später erfassen, zweite
    Unterschrift, abschließen."""
    a = _client(starters, router_test_client, "a")
    c = _start(starters, a, DISPOSAL)
    _fill(a, c, (("abfallart", "bitumen"), ("menge", "1,5"), ("einheit", "t"), ("entsorger", "Recyclinghof"),
                 ("uebergabe", "2026-09-30T09:00")))
    assert _sign(a, c, "unterschrift_monteur", "Anna Alpha").status_code == 200
    assert _put(a, c, "menge", "2").status_code == 409
    _fill(a, c, (("beleg_nr", "WS-4711"),))
    assert _photo(a, c, "beleg_foto").status_code == 200
    assert a.post(f"/api/checklists/{c['id']}/complete").status_code == 200  # zweite Unterschrift ist keine Pflicht
    c2 = _start(starters, a, DISPOSAL)
    _fill(a, c2, (("abfallart", "holz"), ("menge", "3"), ("einheit", "m3"), ("entsorger", "Hof"),
                  ("uebergabe", "2026-09-30T09:00")))
    assert _sign(a, c2, "unterschrift_monteur", "Anna Alpha").status_code == 200
    assert _photo(a, c2, "beleg_foto").status_code == 200
    assert _sign(a, c2, "unterschrift_beleg", "Olga Office").status_code == 200
    assert _photo(a, c2, "beleg_foto").status_code == 409
    done = a.post(f"/api/checklists/{c2['id']}/complete").json()
    assert done["completion_seal"]["status"] == "unveraendert"
    assert {name: s["seal"]["status"] for name, s in _sigs(done).items()} == {
        "Anna Alpha": "unveraendert", "Olga Office": "unveraendert"}
