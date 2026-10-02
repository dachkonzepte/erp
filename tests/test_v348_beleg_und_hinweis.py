"""Version 1.8.45 -- Bedenkenanzeige abrunden: Feldtyp "Beleg" und der Hinweis "Offene Bedenken" auf weiteren Seiten.

Punkt 1: neuer Feldtyp "beleg" für Checklisten -- PDF oder Foto, am Inhalt erkannt wie bei "Zustellung nachtragen"
(app/email_dispatch.py::receipt_content_type()), dieselbe Größengrenze (15 MB), unverändert gespeichert, in Prüfsumme
und Versiegelung eingeschlossen. Das Systemfeld "Antwort als Beleg" der Bedenkenanzeige wird zu diesem Typ; die
Migration 2798ba2fb235 stellt nur eine unveränderte Startvorlage im Entwurf um, sonst weist der Editor darauf hin.
Punkt 2: der Hinweis "Offene Bedenken …" erscheint auch auf der Einsatzbericht-Seite und der Checklisten-Seite des
Auftrags, im Büro und für Monteure (GET /api/orders/{id}/open-concerns jetzt auch für den Monteur an seinem Auftrag).
Herleitung: docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.45".
"""
import hashlib
import json

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.checklist_rules import rule_matches
from app.checklist_templates import (
    add_field, add_rule, create_template, get_template, publish_draft, reorder_fields, start_draft, sync_system_fields,
    update_template,
)
from app.checklists import (
    MAX_BELEG_UPLOAD_BYTES, add_attachment, attachment_path, check_completion, check_signature, create_checklist,
    get_checklist_row,
)
from app.database import Base
from app.models import ChecklistAttachment, ChecklistTemplate, ChecklistTemplateField, ChecklistTemplateVersion
from app.routers.pages import router as pages_router
from tests.grunddaten_schalter import ohne_grunddaten
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v305_checklist_filling import _client, _fields, _jpeg, _png, world  # noqa: F401 -- Fixture
from tests.test_v326_monteur_datengrenze import _verstoesse
from tests.test_v346_bedenkenanzeige import (  # noqa: F401 -- Fixture
    BELEG_MIG, K, MIG, OFFICE_KEYS, _answer, _collect_keys, _notice, _report, _sign, _start, _template_id, kworld,
)

BELEG = K + "antwort_beleg"
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
SVG = (b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
       b'<script>alert(1)</script></svg>')
HTML = b"<!doctype html><html><body><script>alert(1)</script>Antwort</body></html>"


def _upload(client, c, data, name="antwort.pdf", content_type="application/pdf", key=BELEG):
    return client.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[key]},
                       files={"file": (name, data, content_type)})


def _belege(body):
    field_id = _fields(body)[BELEG]
    return [a for a in body["attachments"] if a["field_id"] == field_id]


def _decision_ready(office, c):
    """Meldung und Anzeige fertig, Entscheidung eingetragen -- bereit für den Beleg."""
    _report(office, c)
    _notice(office, c)
    for key, value in ((K + "eingegangen_am", "2026-10-05"), (K + "entscheidung", "bedenken_gefolgt")):
        assert _answer(office, c, key, value).status_code == 200, key


# --- Punkt 1: Beleg annehmen, ablehnen, ausliefern --------------------------------------------

def test_pdf_and_photo_are_accepted_and_stored_unchanged(kworld, router_test_client):
    office = _client(kworld, router_test_client, "office")
    c = _start(kworld, office)
    assert next(f for f in c["fields"] if f["field_key"] == BELEG)["field_type"] == "beleg"
    resp = _upload(office, c, PDF)
    assert resp.status_code == 200, resp.text
    jpeg = _jpeg()
    resp = _upload(office, c, jpeg, name="foto.jpg", content_type="image/jpeg")
    assert resp.status_code == 200, resp.text
    pdf_att, photo_att = _belege(resp.json())
    assert (pdf_att["kind"], pdf_att["content_type"]) == ("beleg", "application/pdf")
    assert (photo_att["kind"], photo_att["content_type"]) == ("beleg", "image/jpeg")
    db = kworld["db"]
    for att, original in ((pdf_att, PDF), (photo_att, jpeg)):  # unverändert, nicht verkleinert oder umkodiert
        assert attachment_path(db.get(ChecklistAttachment, att["id"])).read_bytes() == original
    # Auslieferung mit dem erkannten Typ, nosniff, als Beleg benannt.
    file = office.get(pdf_att["url"])
    assert file.status_code == 200 and file.content == PDF
    assert file.headers["content-type"] == "application/pdf"
    assert file.headers["x-content-type-options"] == "nosniff"
    assert f'filename="Beleg-{pdf_att["id"]}.pdf"' in file.headers["content-disposition"]
    assert office.get(photo_att["url"]).headers["content-type"] == "image/jpeg"


def test_svg_html_and_spoofed_pdf_header_are_rejected_and_nothing_is_stored(kworld, router_test_client, tmp_path):
    office = _client(kworld, router_test_client, "office")
    c = _start(kworld, office)
    for name, data, content_type in (("antwort.svg", SVG, "image/svg+xml"), ("antwort.html", HTML, "text/html"),
                                     ("antwort.pdf", HTML, "application/pdf"),  # Name und Angabe vorgetäuscht
                                     ("antwort.png", SVG, "image/png")):
        resp = _upload(office, c, data, name=name, content_type=content_type)
        assert resp.status_code == 400, (name, resp.text)
        assert resp.json()["detail"] == "Der Beleg muss ein Foto (JPEG, PNG, WebP) oder ein PDF sein.", name
    assert _belege(office.get(f"/api/checklists/{c['id']}").json()) == []
    folder = tmp_path / "checklisten" / str(c["id"])
    assert not folder.exists() or list(folder.iterdir()) == []


def test_size_limit_is_the_one_of_the_delivery_receipt(kworld, router_test_client):
    from app.email_dispatch import MAX_RECEIPT_BYTES

    assert MAX_BELEG_UPLOAD_BYTES == MAX_RECEIPT_BYTES
    office = _client(kworld, router_test_client, "office")
    c = _start(kworld, office)
    too_big = PDF + b"0" * (MAX_BELEG_UPLOAD_BYTES + 1 - len(PDF))
    resp = _upload(office, c, too_big)
    assert resp.status_code == 400 and resp.json()["detail"] == "Der Beleg ist größer als 15 MB."
    assert _upload(office, c, too_big[:MAX_BELEG_UPLOAD_BYTES]).status_code == 200  # genau die Grenze geht


def test_field_cannot_add_a_receipt_to_the_office_field(kworld, router_test_client):
    field = _client(kworld, router_test_client, "a")
    c = _start(kworld, field)
    resp = _upload(field, c, PDF)
    assert resp.status_code == 403 and resp.json()["detail"] == "Dieses Feld füllt das Büro aus."


# --- Punkt 1: Prüfsumme und Versiegelung --------------------------------------------------------

def test_receipt_is_part_of_signature_and_completion_hash(kworld, router_test_client):
    db = kworld["db"]
    office = _client(kworld, router_test_client, "office")
    c = _start(kworld, office)
    _decision_ready(office, c)
    beleg = _belege(_upload(office, c, PDF).json())[0]
    assert _sign(office, c, K + "unterschrift_entscheidung", "Olga Office").status_code == 200

    sig = db.scalar(select(ChecklistAttachment).where(ChecklistAttachment.checklist_id == c["id"],
                                                      ChecklistAttachment.kind == "unterschrift")
                    .order_by(ChecklistAttachment.id.desc()))
    sealed = {e["field_key"]: e for e in json.loads(sig.sealed_content)["fields"]}
    assert sealed[BELEG] == {"field_key": BELEG, "files": [{"id": beleg["id"], "sha256": hashlib.sha256(PDF).hexdigest()}]}
    body = office.get(f"/api/checklists/{c['id']}").json()
    assert _belege(body)[0]["bound_by_signature"]
    # Versiegelt: nicht löschen, nichts dazu.
    resp = office.delete(f"/api/checklist-attachments/{beleg['id']}")
    assert resp.status_code == 409, resp.text
    assert _upload(office, c, PDF).status_code == 409
    assert office.post(f"/api/checklists/{c['id']}/complete").status_code == 200
    db.expire_all()
    row = get_checklist_row(db, c["id"])
    assert check_signature(row, sig)["status"] == "unveraendert"
    assert check_completion(row)["status"] == "unveraendert"

    # Die Datei an der Sperre vorbei geändert: Unterschrift und Abschluss weichen ab -- im Feld "Antwort als Beleg".
    attachment_path(db.get(ChecklistAttachment, beleg["id"])).write_bytes(PDF + b"% nachtraeglich\n")
    db.expire_all()
    row = get_checklist_row(db, c["id"])
    for check in (check_signature(row, db.get(ChecklistAttachment, sig.id)), check_completion(row)):
        assert check["status"] == "abweichend" and check["changed_fields"] == ["Antwort als Beleg"], check
        assert "weicht von der Prüfsumme ab" in check["text"]
    body = office.get(f"/api/checklists/{c['id']}").json()
    assert body["completion_seal"]["status"] == "abweichend"
    assert [a["seal"]["status"] for a in body["attachments"] if a["id"] == sig.id] == ["abweichend"]


def test_pdf_of_the_checklist_lists_both_kinds_of_receipt_with_hash(kworld, router_test_client):
    office = _client(kworld, router_test_client, "office")
    c = _start(kworld, office)
    _decision_ready(office, c)
    jpeg = _jpeg()
    assert _upload(office, c, PDF).status_code == 200
    assert _upload(office, c, jpeg, name="foto.jpg", content_type="image/jpeg").status_code == 200
    assert _sign(office, c, K + "unterschrift_entscheidung", "Olga Office").status_code == 200
    assert office.post(f"/api/checklists/{c['id']}/complete").status_code == 200
    resp = office.get(f"/api/checklists/{c['id']}/pdf")
    assert resp.status_code == 200
    text = _extract_pdf_text(resp.content)
    assert b"PDF-Beleg vom" in text and b"Foto-Beleg vom" in text
    for data in (PDF, jpeg):
        assert hashlib.sha256(data).hexdigest().encode() in text


def test_rule_filled_counts_a_receipt(world):
    db = world["db"]
    t = create_template(db, label="Entsorgung", contexts=["auftrag"])
    v = t["draft_version_id"]
    add_field(db, v, {"field_type": "beleg", "label": "Wiegeschein", "field_key": "wiegeschein", "max_count": 3})
    add_rule(db, v, {"field_key": "wiegeschein", "operator": "ausgefuellt", "task_title": "Beleg prüfen",
                     "task_priority": "normal", "assignee_mode": "rolle", "min_visible_role": "buero_auftrag"})
    field = db.scalar(select(ChecklistTemplateField).where(ChecklistTemplateField.version_id == v))
    assert (field.field_type, field.max_count) == ("beleg", 3)  # Höchstanzahl bleibt beim Normalisieren
    tpl = publish_draft(db, t["id"])
    c = create_checklist(db, template_id=tpl["id"], context_type="auftrag", order_id=world["orders"]["mine"].id,
                         created_by_employee_id=world["emps"]["office"].id)
    row = get_checklist_row(db, c["id"])
    rule = row.template_version.rules[0]
    assert not rule_matches(row, rule)
    add_attachment(db, c["id"], _fields(c)["wiegeschein"], PDF)
    db.expire_all()
    assert rule_matches(get_checklist_row(db, c["id"]), rule)


# --- Punkt 1: Migration der Startvorlage und Hinweis --------------------------------------------

def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    with ohne_grunddaten():
        Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def _beleg_field(db, version_id):
    return db.scalar(select(ChecklistTemplateField).where(ChecklistTemplateField.version_id == version_id,
                                                          ChecklistTemplateField.field_key == BELEG))


def test_migration_switches_only_an_unchanged_draft_and_back():
    engine, db = _fresh_db()
    conn = db.connection()
    assert MIG.insert_concern_template(conn)
    version_id = db.scalar(select(ChecklistTemplateVersion.id))
    assert (_beleg_field(db, version_id).field_type, _beleg_field(db, version_id).help_text) == ("foto", BELEG_MIG.OLD_HELP)
    assert BELEG_MIG.answer_as_beleg(conn)
    assert not BELEG_MIG.answer_as_beleg(conn)  # schon umgestellt
    db.expire_all()
    assert (_beleg_field(db, version_id).field_type, _beleg_field(db, version_id).help_text) == ("beleg", BELEG_MIG.NEW_HELP)
    assert BELEG_MIG.answer_as_photo(conn)
    db.expire_all()
    assert (_beleg_field(db, version_id).field_type, _beleg_field(db, version_id).help_text) == ("foto", BELEG_MIG.OLD_HELP)
    # Eigener Hilfetext bleibt, der Typ wird trotzdem umgestellt.
    db.execute(update(ChecklistTemplateField).where(ChecklistTemplateField.field_key == BELEG).values(help_text="Eigener Text"))
    assert BELEG_MIG.answer_as_beleg(conn)
    db.expire_all()
    assert (_beleg_field(db, version_id).field_type, _beleg_field(db, version_id).help_text) == ("beleg", "Eigener Text")
    db.close()
    engine.dispose()


def test_published_starter_stays_with_a_hint_and_a_new_draft_switches():
    engine, db = _fresh_db()
    assert MIG.insert_concern_template(db.connection())
    # Wie auf dem Server, wenn die Startvorlage unter 1.8.43/1.8.44 veröffentlicht wurde (damals mit Fotofeld).
    db.execute(update(ChecklistTemplateVersion).values(status="veroeffentlicht"))
    db.commit()
    assert not BELEG_MIG.answer_as_beleg(db.connection())
    template_id = _template_id(db)
    old_version = db.scalar(select(ChecklistTemplateVersion.id))
    assert _beleg_field(db, old_version).field_type == "foto"
    detail = get_template(db, template_id)
    assert detail["system_field_problems"] == []
    assert detail["published_system_field_problems"] == [
        "Das Systemfeld „Antwort als Beleg“ (bedenkenanzeige.antwort_beleg) weicht von der Vorgabe ab: Typ."]
    draft = start_draft(db, template_id)  # gleicht an: das Systemfeld wird ein Belegfeld
    assert draft["system_field_problems"] == [] and draft["published_system_field_problems"] == []
    assert _beleg_field(db, draft["draft_version_id"]).field_type == "beleg"
    assert _beleg_field(db, old_version).field_type == "foto"  # die gültige Fassung bleibt, wie sie ist
    published = publish_draft(db, template_id)
    assert published["published_version_no"] == 2 and published["published_system_field_problems"] == []
    db.close()
    engine.dispose()


def test_changed_draft_stays_with_a_hint_and_sync_switches():
    engine, db = _fresh_db()
    assert MIG.insert_concern_template(db.connection())
    db.commit()
    template_id = _template_id(db)
    version = db.scalar(select(ChecklistTemplateVersion))
    ids = [f.id for f in version.fields]
    reorder_fields(db, version.id, [ids[1], ids[0], *ids[2:]])  # vom Büro umsortiert: nicht mehr unverändert
    assert not BELEG_MIG.answer_as_beleg(db.connection())
    detail = get_template(db, template_id)
    assert detail["system_field_problems"] == [
        "Das Systemfeld „Antwort als Beleg“ (bedenkenanzeige.antwort_beleg) weicht von der Vorgabe ab: Typ."]
    sync_system_fields(db, version.id)  # "Systemfelder angleichen"
    assert get_template(db, template_id)["system_field_problems"] == []
    assert _beleg_field(db, version.id).field_type == "beleg"
    db.close()
    engine.dispose()


def test_ordinary_field_with_the_key_and_another_type_still_blocks(world):
    db = world["db"]
    t = create_template(db, label="Eigene Anzeige", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "text", "label": "Antwort", "field_key": BELEG})
    try:
        update_template(db, t["id"], label="Eigene Anzeige", description=None, contexts=["auftrag"],
                        field_readable=False, purpose="bedenkenanzeige")
    except ValueError as exc:
        assert "trägt den Schlüssel bedenkenanzeige.antwort_beleg" in str(exc)
    else:
        raise AssertionError("ein gewöhnliches Feld mit dem Schlüssel wurde still umgestellt")
    db.rollback()
    field = db.scalar(select(ChecklistTemplateField).where(ChecklistTemplateField.field_key == BELEG,
                                                           ChecklistTemplateField.version_id == t["draft_version_id"]))
    assert (field.field_type, field.is_system) == ("text", False)


# --- Punkt 2: Hinweis auf Einsatzbericht- und Checklisten-Seite, Büro und Monteur -----------------

def test_hint_endpoint_for_field_at_own_order_with_link_only_where_readable(kworld, router_test_client):
    office = _client(kworld, router_test_client, "office")
    field = _client(kworld, router_test_client, "a")
    mine, foreign = kworld["orders"]["mine"].id, kworld["orders"]["foreign"].id
    own = _start(kworld, field)
    other = _start(kworld, office)  # vom Büro angelegt, Vorlage nicht field_readable
    resp = field.get(f"/api/orders/{mine}/open-concerns")
    assert resp.status_code == 200, resp.text
    assert [(h["checklist_id"], h["can_open"]) for h in resp.json()["concerns"]] == [(own["id"], True), (other["id"], False)]
    assert field.get(f"/api/checklists/{other['id']}").status_code == 403  # deshalb ohne Link
    assert [h["can_open"] for h in office.get(f"/api/orders/{mine}/open-concerns").json()["concerns"]] == [True, True]
    # Ohne Auftragsbezug: 403 wie jeder Auftragszugriff -- fremder Auftrag, Monteur ohne Einsatz.
    assert field.get(f"/api/orders/{foreign}/open-concerns").status_code == 403
    assert _client(kworld, router_test_client, "c").get(f"/api/orders/{mine}/open-concerns").status_code == 403
    # Mit Lesefreigabe der Vorlage öffnet der Monteur auch die fremde Anzeige.
    db = kworld["db"]
    db.get(ChecklistTemplate, kworld["concern_tpl"]["id"]).field_readable = True
    db.commit()
    assert [h["can_open"] for h in field.get(f"/api/orders/{mine}/open-concerns").json()["concerns"]] == [True, True]


def test_hint_box_on_service_report_page_and_order_checklist_page_for_office_and_field(kworld, router_test_client):
    order_id = kworld["orders"]["mine"].id
    for role, employee in (("buero_auftrag", kworld["emps"]["office"].id), ("field", kworld["emps"]["a"].id)):
        client = router_test_client(kworld["db"], pages_router, role=role, employee_id=employee)
        for url in (f"/orders/{order_id}/service-reports", f"/checklisten/auftrag/{order_id}"):
            resp = client.get(url)
            assert resp.status_code == 200, (role, url)
            html = resp.text
            assert 'id="concernAlert" class="concern-alert" role="alert" hidden' in html, (role, url)
            assert "function offeneBedenkenZeigen(boxId,orderId)" in html, (role, url)
            assert "offeneBedenkenZeigen('concernAlert',orderId)" in html, (role, url)
            assert "/open-concerns" in html and "c.can_open?" in html, (role, url)


def test_field_responses_carry_no_office_data_key_scan(kworld, router_test_client):
    """Schlüssel-Scan wie test_v326 (verbotene Namen, Personendaten) und die Büro-Schlüssel der Bedenkenanzeige -- über
    den Hinweis-Endpunkt und die eigene Checkliste mit Beleg, als Monteur."""
    office = _client(kworld, router_test_client, "office")
    field = _client(kworld, router_test_client, "a")
    mine = kworld["orders"]["mine"].id
    c = _start(kworld, field)
    _report(field, c)
    _notice(office, c)
    assert _upload(office, c, PDF).status_code == 200
    antworten = []
    for route, url in (("/api/orders/{order_id}/open-concerns", f"/api/orders/{mine}/open-concerns"),
                       ("/api/checklists/{checklist_id}", f"/api/checklists/{c['id']}"),
                       ("/api/checklists", f"/api/checklists?order_id={mine}")):
        resp = field.get(url)
        assert resp.status_code == 200, (url, resp.text)
        antworten.append({"route": route, "body": resp.json()})
    assert antworten[0]["body"]["concerns"] and _belege(antworten[1]["body"])  # Inhalt da, sonst prüft der Scan nichts
    gefunden, _genutzt = _verstoesse(antworten)
    assert gefunden == []
    for antwort in antworten:
        assert not _collect_keys(antwort["body"], set()) & OFFICE_KEYS, antwort["route"]
    # Der Monteur sieht den Beleg an seiner Checkliste (lesend), die Datei mit dem erkannten Typ.
    beleg = _belege(antworten[1]["body"])[0]
    assert field.get(beleg["url"]).headers["content-type"] == "application/pdf"
