"""Version 1.8.40 -- Stufe 2b, Runde 2b-3 Teil 2, Punkte 1–3: Behinderungsanzeige als Brief und Versand
(app/notice_letters.py, app/notice_letter_pdf.py, app/notice_reservations.py, app/routers/notice_letters.py,
Migration *_behinderungsanzeige_brief_und_versand.py; docs/archiv/vertragsgrundlage-und-vertrag.md,
"Umsetzung 1.8.40").

Geprüft: der Brief kommt aus der versiegelten Kopie der Abschnittsunterschrift (Empfänger mit Anrede, Betreff
mit Bauvorhaben und Auftragsnummer, Angaben, "Kopie an:", Unterschrift Büro, Fotos verkleinert als Anlage) und
entsteht nicht, wenn der Inhalt an der Sperre vorbei geändert wurde; Anzeige der Wiederaufnahme nach dem
Wegfall; Vorbehalt je Briefart und Vertragsgrundlage nur geprüft gedruckt, Versand trotzdem möglich; Versand
erst nach der Unterschrift des Abschnitts, immer die abgelegte Fassung; An immer der Auftraggeber, CC aus
"Kopie bei Anzeigen", entdoppelt; Vollmacht beim Versand eingefroren und nach dem Ersetzen unverändert in der
Ablage; danach ist die Aufgabe "Behinderungsanzeige versenden" erledigt (auch per nachgetragener Zustellung);
Monteur 403; Fassung und Vollmacht unveränderlich; Migration; zwei gleichzeitige Fassungen gegen PostgreSQL."""

import hashlib
import importlib.util
import json
import os
import stat
import threading
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from PIL import Image
from sqlalchemy import create_engine, func, inspect, select, text, update
from sqlalchemy.orm import sessionmaker

import app.sent_documents as sent_documents_module
from app.berlin_time import berlin_today
from app.checklist_follow_ups import run_checklist_follow_ups
from app.database import Base
from app.models import (
    ArchiveImmutableError, ChecklistAnswer, ChecklistAttachment, ChecklistFollowUp, Contact, DispatchAuthorization, EmailDispatch,
    EnabledModule, NoticeLetter, Project, SentDocument, Task,
)
from app.notice_letters import ensure_letter
from app.notice_reservations import update_reservation
from app.project_participants import add_participant, store_power_of_attorney
from app.routers.checklists import router as checklists_router
from app.routers.email_dispatches import router as dispatches_router
from app.routers.notice_letters import router as notice_router
from app.settings import load_general_settings
from tests.test_v305_checklist_filling import _client, _fields, _jpeg, _png, world  # noqa: F401 -- Fixture
from tests.test_v321_email_dispatch import FakeSMTP, _attachment, _configure_smtp
from tests.test_v325_contract_basis import pdf_text
from tests.test_v341_behinderungsanzeige import (  # noqa: F401 -- Fixture
    B, TASK_TITLE, _answer, _notice, _report, _send_tasks, _sign, _start, bworld,
)

VERSIONS = Path(__file__).resolve().parent.parent.joinpath("alembic", "versions")
AG_EMAIL = "auftraggeber@example.com"
NOTICE = "behinderungsanzeige"
RESUME = "wiederaufnahme"


def _pdf_bytes(content: bytes = b"Vollmacht A") -> bytes:
    """Ein echtes, kleines PDF (am Inhalt erkannt wie der Beleg einer Zustellung)."""
    buf = BytesIO()
    Image.new("RGB", (40, 40), (255, 255, 255)).save(buf, format="PDF")
    return buf.getvalue().replace(b"%%EOF", b"% " + content + b"\n%%EOF")


@pytest.fixture
def nworld(bworld, monkeypatch):
    """bworld (veröffentlichte Behinderungsanzeige, Sachbearbeiterin am Auftrag) + SMTP-Attrappe + Auftraggeber mit
    Anrede und E-Mail."""
    db = bworld["db"]
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    customer = bworld["orders"]["mine"].project.customer
    customer.email, customer.salutation, customer.title = AG_EMAIL, "Herr", "Dr."
    customer.first_name, customer.last_name, customer.name = "Max", "Muster", "Herr Dr. Max Muster"
    customer.street, customer.postal_code, customer.city = "Kundenweg 3", "50667", "Köln"
    # Seit 1.8.44 verlangt ein abweichender Kunde laut Auftrag eine Bestätigung -- hier stimmen beide überein.
    bworld["orders"]["mine"].customer_name = customer.name
    load_general_settings(bworld["db"]).company_name = "Dach GmbH"
    db.commit()
    return bworld


def _office(w, rtc, role="buero_auftrag"):
    return rtc(w["db"], checklists_router, notice_router, dispatches_router, role=role,
               employee_id=w["emps"]["office"].id)


def _signed(w, rtc) -> dict:
    """Meldung von der Monteurin, Anzeige vom Büro -- beide unterschrieben."""
    field, office = _client(w, rtc, "a"), _client(w, rtc, "office")
    c = _start(w, field)
    _report(field, c)
    _notice(office, c)
    return c


def _wegfall(w, rtc, c) -> None:
    field = _client(w, rtc, "a")
    for key, value in ((B + "beendet_am", "2026-10-06"), (B + "wieder_aufgenommen_am", "2026-10-07")):
        assert _answer(field, c, key, value).status_code == 200
    assert _sign(field, c, B + "unterschrift_wegfall", "Anna Alpha").status_code == 200


def _send(client, c, kind=NOTICE, **payload):
    payload.setdefault("dispatch_key", f"{kind}-{uuid.uuid4().hex}")
    return client.post(f"/api/checklists/{c['id']}/notice-letters/{kind}/send-email", json=payload)


def _state(client, c) -> dict:
    res = client.get(f"/api/checklists/{c['id']}/notice-letters")
    assert res.status_code == 200, res.text
    return res.json()


def _kind(state, kind=NOTICE) -> dict:
    return next(k for k in state["kinds"] if k["kind"] == kind)


def _letters(db, kind=NOTICE) -> list[NoticeLetter]:
    db.expire_all()
    return db.scalars(select(NoticeLetter).where(NoticeLetter.kind == kind).order_by(NoticeLetter.version_no)).all()


def _participant(db, w, *, name, email, role="architekt_planer", copy=True, authorized=False):
    contact = Contact(kind="firma", company_name=name, email=email)
    db.add(contact)
    db.flush()
    project = db.get(Project, w["orders"]["mine"].project_id)
    return add_participant(db, project, contact, role=role, copy_on_notices=copy, authorized_recipient=authorized)


def _archive_bytes(doc: SentDocument) -> bytes:
    return (sent_documents_module.SENT_DOCUMENT_ROOT / doc.stored_filename).read_bytes()


def _review(db, kind=NOTICE, group="bgb", text_value="Wir behalten uns vor, Mehrkosten geltend zu machen."):
    return update_reservation(db, kind, group, reservation_text=text_value, reviewed_on=berlin_today(),
                              reviewed_by="RA Beispiel")


# --- Punkt 1: der Brief ---------------------------------------------------------------------

def test_letter_from_the_sealed_sections_with_recipient_subject_copies_signature_and_photos(nworld, router_test_client):
    db = nworld["db"]
    _participant(db, nworld, name="Architekturbüro Plan", email="arch@example.com")
    _participant(db, nworld, name="Hausverwaltung Ohne Kopie", email="hv@example.com", role="hausverwaltung", copy=False)
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    # Wegfall schon eingetragen (aber nicht unterschrieben) -- gehört nicht in die Behinderungsanzeige.
    assert _answer(_client(nworld, router_test_client, "a"), c, B + "beendet_am", "2026-10-06").status_code == 200

    state = _state(office, c)
    assert _kind(state)["ready"] and not _kind(state, RESUME)["ready"]
    assert state["recipient"]["email"] == AG_EMAIL and state["cc_prefill"] == "arch@example.com"
    res = office.post(f"/api/checklists/{c['id']}/notice-letters/{NOTICE}/freeze")
    assert res.status_code == 200, res.text
    [letter] = _letters(db)
    content = json.loads(letter.content)
    assert letter.content_sha256 == hashlib.sha256(letter.content.encode("utf-8")).hexdigest()
    assert content["recipient"]["lines"] == ["Herr Dr. Max Muster", "Kundenweg 3", "50667 Köln"]
    assert content["salutation"] == "Sehr geehrter Herr Dr. Muster,"
    assert content["subject"] == "Behinderungsanzeige"
    assert content["subject_line"] == "Bauvorhaben: Halle Nord, Weg 1, 12345 Stadt · Auftrag AU-2026-0001"
    assert [(i["label"], i["value"]) for i in content["items"]] == [
        ("Bekannt seit", "02.10.2026, 07:45 Uhr"), ("Beschreibung", "Gerüst fehlt an der Nordseite"),
        ("Ursache", "Zugang oder Gerüst"), ("Beschreibung der Ursache", "Gerüstbauer nicht erschienen"),
        ("Betroffene Leistungen", "Dachdeckung Nordseite"), ("Beginn der Behinderung", "02.10.2026"),
        ("Voraussichtliche Dauer", "etwa eine Woche")]
    assert content["copy_to"] == [{"participant_id": content["copy_to"][0]["participant_id"],
                                   "name": "Architekturbüro Plan", "role_label": "Architekt/Planer"}]
    assert content["signature"]["signer_name"] == "Olga Office" and content["signature"]["field_key"] == B + "unterschrift_buero"
    # Die Fotos mit der Prüfsumme aus der versiegelten Kopie der Unterschrift.
    signature = db.get(ChecklistAttachment, content["signature"]["attachment_id"])
    sealed_photos = next(e["photos"] for e in json.loads(signature.sealed_content)["fields"] if e["field_key"] == B + "fotos")
    [photo] = content["photos"]
    assert [{"id": p["id"], "sha256": p["sha256"]} for p in content["photos"]] == sealed_photos
    assert content["signature"]["content_sha256"] == letter.signature_sha256 == signature.content_sha256
    archived = _archive_bytes(letter.sent_document)
    assert hashlib.sha256(archived).hexdigest() == letter.sent_document.sha256
    assert letter.sent_document.document_type == NOTICE and letter.sent_document.document_id == c["id"]
    text_ = pdf_text(archived)
    for expected in ("Herr Dr. Max Muster", "Kundenweg 3", "50667 Köln", "Sehr geehrter Herr Dr. Muster,",
                     "Behinderungsanzeige", "Halle Nord", "AU-2026-0001", "Gerüst fehlt an der Nordseite",
                     "Zugang oder Gerüst", "Kopie an:", "Architekturbüro Plan (Architekt/Planer)", "Olga Office",
                     "Dach GmbH", "Mit freundlichen Grüßen", "Anlage – Fotos", letter.signature_sha256):
        assert expected in text_, expected
    assert "1 Foto (verkleinert)" in text_
    assert "Hausverwaltung Ohne Kopie" not in text_ and "beendet am" not in text_
    assert photo["sha256"] and photo["field_key"] == B + "fotos"


def test_photos_are_reduced_below_the_mail_limit(nworld, router_test_client, monkeypatch):
    """Fünf große Fotos mit Rauschen (kaum komprimierbar): das PDF bleibt unter 3.000.000 Bytes, die Originale
    unverändert."""
    import random

    import app.notice_letter_pdf as letter_pdf
    db = nworld["db"]
    field, office = _client(nworld, router_test_client, "a"), _client(nworld, router_test_client, "office")
    c = _start(nworld, field)
    rng = random.Random(7)
    for _ in range(5):
        img = Image.frombytes("RGB", (1600, 1200), bytes(rng.getrandbits(8) for _ in range(1600 * 1200 * 3)))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=95)
        assert field.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": _fields(c)[B + "fotos"]},
                          files={"file": ("f.jpg", buf.getvalue(), "image/jpeg")}).status_code == 200
    for key, value in ((B + "bekannt_seit", "2026-10-02T07:45"), (B + "beschreibung", "Gerüst fehlt")):
        assert _answer(field, c, key, value).status_code == 200
    assert _sign(field, c, B + "unterschrift_meldung", "Anna Alpha").status_code == 200
    _notice(office, c)
    import app.checklists as checklists_module
    photos = [a for a in db.scalars(select(ChecklistAttachment).where(ChecklistAttachment.checklist_id == c["id"],
                                                                     ChecklistAttachment.kind == "foto")).all()]
    originals = {a.id: checklists_module.attachment_path(a).read_bytes() for a in photos}
    rendered = []
    original_render = letter_pdf.render_notice_letter_pdf
    monkeypatch.setattr(letter_pdf, "render_notice_letter_pdf",
                        lambda *a, **k: rendered.append(sum(len(p) for p in k["photos"])) or original_render(*a, **k))
    letter = ensure_letter(db, c["id"], NOTICE)
    assert letter.sent_document.size_bytes <= 3_000_000
    assert len(json.loads(letter.content)["photos"]) == 5 and rendered  # verkleinert gerendert
    assert sum(originals_size := [len(b) for b in originals.values()]) > 3_000_000  # ohne Verkleinerung zu groß
    assert {a.id: checklists_module.attachment_path(a).read_bytes() for a in photos} == originals
    assert "5 Fotos (verkleinert)" in pdf_text(_archive_bytes(letter.sent_document))


def test_letter_is_refused_when_the_signed_content_was_changed_behind_the_lock(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    db.execute(update(ChecklistAnswer).where(ChecklistAnswer.checklist_id == c["id"],
                                             ChecklistAnswer.field_key == B + "beschreibung")
               .values(value_text="nachträglich geändert"))
    db.commit()
    for res in (office.post(f"/api/checklists/{c['id']}/notice-letters/{NOTICE}/freeze"), _send(office, c),
                office.get(f"/api/checklists/{c['id']}/notice-letters/{NOTICE}/preview")):
        assert res.status_code == 409 and "weicht von der Prüfsumme ab" in res.json()["detail"], res.text
    assert _kind(_state(office, c))["blocked"] is True
    assert _letters(db) == [] and FakeSMTP.sent == []
    db.execute(update(ChecklistAnswer).where(ChecklistAnswer.checklist_id == c["id"],
                                             ChecklistAnswer.field_key == B + "beschreibung")
               .values(value_text="Gerüst fehlt an der Nordseite"))
    db.commit()
    assert office.post(f"/api/checklists/{c['id']}/notice-letters/{NOTICE}/freeze").status_code == 200


def test_preview_is_marked_and_stores_nothing(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    before = db.scalar(select(func.count()).select_from(SentDocument))
    res = office.get(f"/api/checklists/{c['id']}/notice-letters/{NOTICE}/preview")
    assert res.status_code == 200 and res.headers["content-type"] == "application/pdf"
    assert "Vorschau" in pdf_text(res.content)
    assert db.scalar(select(func.count()).select_from(SentDocument)) == before and _letters(db) == []


def test_resumption_letter_after_wegfall_refers_to_the_sent_notice(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    res = _send(office, c, RESUME)
    assert res.status_code == 409 and "Wegfall" in res.json()["detail"]
    assert _send(office, c).status_code == 200
    _wegfall(nworld, router_test_client, c)
    assert _kind(_state(office, c), RESUME)["ready"]
    res = _send(office, c, RESUME)
    assert res.status_code == 200, res.text
    [letter] = _letters(db, RESUME)
    content = json.loads(letter.content)
    assert content["subject"] == "Anzeige der Wiederaufnahme"
    assert f"mit unserer Behinderungsanzeige vom {berlin_today():%d.%m.%Y} angezeigte" in content["intro"]
    assert [(i["label"], i["value"]) for i in content["items"]] == [
        ("Beginn der Behinderung", "02.10.2026"), ("Behinderung beendet am", "06.10.2026"),
        ("Arbeit wieder aufgenommen am", "07.10.2026")]
    assert content["signature"]["signer_name"] == "Anna Alpha" and content["photos"] == []
    assert "Anzeige der Wiederaufnahme" in pdf_text(_archive_bytes(letter.sent_document))


# --- Punkt 2: Vorbehalt ---------------------------------------------------------------------

def test_reservation_printed_only_when_reviewed_per_letter_kind_and_contract_basis(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    order = nworld["orders"]["mine"]
    order.contract_basis = "vob_b"
    db.commit()
    c = _signed(nworld, router_test_client)
    # Ungeprüft: nicht gedruckt, Seite warnt, Versand geht trotzdem.
    update_reservation(db, NOTICE, "vob_b", reservation_text="VOB-Vorbehalt ungeprüft", reviewed_on=None, reviewed_by=None)
    _review(db, NOTICE, "bgb", "BGB-Vorbehalt geprüft")
    _review(db, RESUME, "vob_b", "Wiederaufnahme-Vorbehalt geprüft")
    reservation = _kind(_state(office, c))["reservation"]
    assert (reservation["basis_group"], reservation["reviewed"], reservation["has_text"]) == ("vob_b", False, True)
    assert _send(office, c).status_code == 200
    [letter] = _letters(db)
    assert letter.reservation_printed is False
    text_ = pdf_text(_archive_bytes(letter.sent_document))
    assert "VOB-Vorbehalt" not in text_ and "BGB-Vorbehalt" not in text_ and "Wiederaufnahme-Vorbehalt" not in text_

    # Geprüft (VOB/B, Behinderungsanzeige): gedruckt -- in einer neuen Fassung nach neuer Unterschrift.
    _review(db, NOTICE, "vob_b", "VOB-Vorbehalt geprüft")
    office_c = _client(nworld, router_test_client, "office")
    signature_id = _kind(_state(office, c))["signature"]["id"]
    assert office_c.post(f"/api/checklists/{c['id']}/discard-signatures",
                         json={"signature_id": signature_id, "reason": "Vorbehalt nachtragen"}).status_code == 200
    assert _sign(office_c, office_c.get(f"/api/checklists/{c['id']}").json(), B + "unterschrift_buero", "Olga Office").status_code == 200
    assert _send(office, c).status_code == 200
    first, second = _letters(db)
    assert (first.version_no, second.version_no, second.reservation_printed) == (1, 2, True)
    text_ = pdf_text(_archive_bytes(second.sent_document))
    assert "VOB-Vorbehalt geprüft" in text_ and "BGB-Vorbehalt" not in text_ and "Wiederaufnahme" not in text_


def test_reservation_rules_and_rights(nworld, router_test_client):
    db = nworld["db"]
    admin = _office(nworld, router_test_client, role="admin")
    office = _office(nworld, router_test_client)
    url = f"/api/settings/notice-reservations/{NOTICE}/vob_b"
    body = {"reservation_text": "Vorbehalt", "reviewed_on": str(berlin_today()), "reviewed_by": "RA Beispiel"}
    assert office.put(url, json=body).status_code == 403
    assert admin.put(url, json=body).json()["reviewed"] is True
    # Text geändert, dieselben Prüfangaben mit -> Prüfung fällt weg.
    res = admin.put(url, json={**body, "reservation_text": "Vorbehalt neu"}).json()
    assert (res["reviewed"], res["review_reset"], res["reviewed_on"]) == (False, True, None)
    for bad in ({**body, "reviewed_by": None}, {**body, "reviewed_on": "2999-01-01"},
                {"reservation_text": None, "reviewed_on": str(berlin_today()), "reviewed_by": "RA"}):
        assert admin.put(url, json=bad).status_code == 422, bad
    assert admin.put(url, json={"reservation_text": "x"}).status_code == 422  # alle Felder Pflicht (Regel 22)
    assert admin.put(f"/api/settings/notice-reservations/{NOTICE}/vob_c", json=body).status_code == 404
    listed = office.get("/api/settings/notice-reservations").json()
    assert [(r["letter_kind"], r["basis_group"]) for r in listed] == [
        (NOTICE, "vob_b"), (NOTICE, "bgb"), (RESUME, "vob_b"), (RESUME, "bgb"),
        ("bedenkenanzeige", "vob_b"), ("bedenkenanzeige", "bgb")]  # seit 1.8.44


# --- Punkt 3: Versand -----------------------------------------------------------------------

def test_send_refused_before_the_section_signature(nworld, router_test_client):
    db = nworld["db"]
    field, office_c = _client(nworld, router_test_client, "a"), _client(nworld, router_test_client, "office")
    office = _office(nworld, router_test_client)
    c = _start(nworld, field)
    _report(field, c)  # nur die Meldung
    for res in (_send(office, c), office.post(f"/api/checklists/{c['id']}/notice-letters/{NOTICE}/freeze"),
                office.get(f"/api/checklists/{c['id']}/notice-letters/{NOTICE}/preview")):
        assert res.status_code == 409 and "Unterschrift Büro" in res.json()["detail"], res.text
    manual = office.post("/api/email-dispatches/manual", data={
        "document_type": NOTICE, "document_id": c["id"], "channel": "einschreiben",
        "delivered_on": str(berlin_today()), "note": "Einschreiben", "dispatch_key": f"manuell-{uuid.uuid4().hex}"})
    assert manual.status_code == 400
    assert FakeSMTP.sent == [] and _letters(db) == [] and db.scalars(select(EmailDispatch)).all() == []
    _notice(office_c, c)
    assert _send(office, c).status_code == 200
    # Die Unterschrift Büro verworfen: nicht mehr versendbar, bis neu unterschrieben ist.
    signature_id = _kind(_state(office, c))["signature"]["id"]
    assert office_c.post(f"/api/checklists/{c['id']}/discard-signatures",
                         json={"signature_id": signature_id, "reason": "Ursache falsch"}).status_code == 200
    assert _send(office, c).status_code == 409


def test_client_is_always_in_to_and_recipients_are_deduplicated(nworld, router_test_client):
    db = nworld["db"]
    _participant(db, nworld, name="Architekt", email="arch@example.com")
    _participant(db, nworld, name="Eigentümer", email="ARCH@example.com", role="eigentuemer")
    _participant(db, nworld, name="Verwaltung mit AG-Adresse", email=AG_EMAIL.upper(), role="hausverwaltung")
    _participant(db, nworld, name="Ohne E-Mail", email=None, role="sachverstaendiger")
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    state = _state(office, c)
    assert state["cc_prefill"] == "arch@example.com"
    res = _send(office, c, to_email="fremd@example.com",
                cc_email=f"arch@example.com; {AG_EMAIL.upper()}, ARCH@example.com, neu@example.com")
    assert res.status_code == 200, res.text
    dispatch = res.json()
    assert dispatch["to_recipients"] == AG_EMAIL
    assert dispatch["cc_recipients"] == "arch@example.com, neu@example.com"
    [mail] = FakeSMTP.sent
    assert mail["recipients"] == [AG_EMAIL, "arch@example.com", "neu@example.com"]
    assert "fremd@example.com" not in json.dumps(dispatch)
    # Ohne E-Mail des Auftraggebers kein Versand -- und auch keine Fassung.
    c2 = _signed(nworld, router_test_client)
    nworld["orders"]["mine"].project.customer.email = None
    db.commit()
    res = _send(office, c2)
    assert res.status_code == 400 and "keine E-Mail-Adresse" in res.json()["detail"]
    assert [l.checklist_id for l in _letters(db)] == [c["id"]]


def test_always_the_archived_letter(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    assert _send(office, c).status_code == 200
    [letter] = _letters(db)
    archived = _archive_bytes(letter.sent_document)
    documents = db.scalar(select(func.count()).select_from(SentDocument))
    # Briefkopf, Beteiligte und Kundenname geändert -- der nächste Versand schickt dieselben Bytes.
    load_general_settings(db).company_name = "Neuer Name GmbH"
    nworld["orders"]["mine"].project.customer.name = "Ganz anders"
    db.commit()
    _participant(db, nworld, name="Später dazu", email="spaet@example.com")
    # Seit 1.8.44: der umbenannte Kunde weicht vom Kunden laut Auftrag ab -- erst mit Bestätigung.
    assert _send(office, c, cc_email="spaet@example.com").status_code == 409
    assert _send(office, c, cc_email="spaet@example.com", confirm_customer=True).status_code == 200
    first, second = FakeSMTP.sent
    assert _attachment(first["message"]) == archived == _attachment(second["message"])
    assert db.scalar(select(func.count()).select_from(SentDocument)) == documents
    dispatches = db.scalars(select(EmailDispatch).order_by(EmailDispatch.id)).all()
    assert {d.sent_document_id for d in dispatches} == {letter.sent_document_id}
    assert [l.id for l in _letters(db)] == [letter.id]
    # Beschädigte Ablage: nichts versendet, nie still neu erzeugt.
    path = sent_documents_module.SENT_DOCUMENT_ROOT / letter.sent_document.stored_filename
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    path.write_bytes(archived + b"x")
    res = _send(office, c, confirm_customer=True)
    assert res.status_code == 409 and "nicht mehr unversehrt" in res.json()["detail"]
    assert len(FakeSMTP.sent) == 2 and [l.id for l in _letters(db)] == [letter.id]


def test_power_of_attorney_frozen_at_dispatch_and_unchanged_after_replacement(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    arch = _participant(db, nworld, name="Architekt", email="arch@example.com", authorized=True)
    hv = _participant(db, nworld, name="Hausverwaltung", email="hv@example.com", role="hausverwaltung", copy=False,
                      authorized=True)
    bau = _participant(db, nworld, name="Bauleitung", email="bau@example.com", role="bauleitung_ag", authorized=True)
    first_poa, second_poa = _pdf_bytes(b"Vollmacht A"), _pdf_bytes(b"Vollmacht B")
    store_power_of_attorney(db, arch, filename="vollmacht.pdf", data=first_poa, user_name="Olga")
    store_power_of_attorney(db, hv, filename="hv.pdf", data=_pdf_bytes(b"HV"), user_name="Olga")
    c = _signed(nworld, router_test_client)
    res = _send(office, c, cc_email="arch@example.com, bau@example.com")
    assert res.status_code == 200, res.text
    rows = db.scalars(select(DispatchAuthorization).order_by(DispatchAuthorization.id)).all()
    assert [(r.contact_name, r.note) for r in rows] == [("Architekt", None), ("Bauleitung", "Keine Vollmacht hinterlegt.")]
    frozen = rows[0].sent_document
    assert _archive_bytes(frozen) == first_poa and frozen.sha256 == hashlib.sha256(first_poa).hexdigest()
    assert (frozen.document_type, frozen.document_id, frozen.content_type) == (NOTICE, c["id"], "application/pdf")
    # Vollmacht ersetzt: die eingefrorene Kopie bleibt, der nächste Versand friert die neue ein.
    store_power_of_attorney(db, db.get(type(arch), arch.id), filename="neu.pdf", data=second_poa, user_name="Olga")
    assert _archive_bytes(frozen) == first_poa
    assert sent_documents_module.verify_sent_document(frozen)["status"] == "unveraendert"
    assert _send(office, c, cc_email="arch@example.com").status_code == 200
    db.expire_all()
    rows = db.scalars(select(DispatchAuthorization).order_by(DispatchAuthorization.id)).all()
    assert [_archive_bytes(r.sent_document) for r in rows if r.sent_document] == [first_poa, second_poa]
    # Im Versandverlauf je Versand.
    items = office.get(f"/api/email-dispatches?document_type={NOTICE}&document_id={c['id']}").json()["items"]
    assert [[a["contact_name"] for a in d["authorizations"]] for d in items] == [["Architekt"], ["Architekt", "Bauleitung"]]


def test_send_task_done_after_sending_by_mail_or_recorded_delivery(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    c = _signed(nworld, router_test_client)
    [task] = _send_tasks(db)
    assert task.status == "offen" and task.completed_at is None
    assert _send(office, c).status_code == 200
    db.expire_all()
    task = db.get(Task, task.id)
    assert task.status == "erledigt" and task.completed_at is not None
    # Zweite Anzeige: per Einschreiben zugestellt und nachgetragen.
    c2 = _signed(nworld, router_test_client)
    task2 = next(t for t in _send_tasks(db) if t.source_url == f"/checklisten/{c2['id']}")
    res = office.post("/api/email-dispatches/manual", data={
        "document_type": NOTICE, "document_id": c2["id"], "channel": "einschreiben", "delivered_on": str(berlin_today()),
        "note": "Einschreiben RR 123", "recipient": "Herr Dr. Muster", "dispatch_key": f"manuell-{uuid.uuid4().hex}"})
    assert res.status_code == 200, res.text
    [letter2] = [l for l in _letters(db) if l.checklist_id == c2["id"]]
    assert res.json()["sent_document"]["id"] == letter2.sent_document_id
    db.expire_all()
    assert db.get(Task, task2.id).status == "erledigt"


def test_wiederaufnahme_leaves_the_task_and_a_late_follow_up_creates_none(nworld, router_test_client):
    db = nworld["db"]
    office = _office(nworld, router_test_client)
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    c = _signed(nworld, router_test_client)
    assert _send_tasks(db) == []  # Aufgabenmodul aus: Folge "modul_aus"
    assert _send(office, c).status_code == 200
    db.execute(update(EnabledModule).where(EnabledModule.module_key == "aufgabenmanagement").values(enabled=True))
    db.commit()
    assert run_checklist_follow_ups(db, c["id"])["done"] == 1
    assert _send_tasks(db) == []  # schon versendet -- keine Aufgabe mehr
    [row] = db.scalars(select(ChecklistFollowUp).where(ChecklistFollowUp.checklist_id == c["id"])).all()
    assert (row.status, row.target_id) == ("erledigt", None)


# --- Rechte, Unveränderlichkeit -------------------------------------------------------------

def test_monteur_gets_403_everywhere_even_at_his_own_checklist(nworld, router_test_client):
    db = nworld["db"]
    c = _signed(nworld, router_test_client)
    field = router_test_client(db, checklists_router, notice_router, dispatches_router, role="field",
                               employee_id=nworld["emps"]["a"].id)
    base = f"/api/checklists/{c['id']}/notice-letters"
    for res in (field.get(base), field.get(f"{base}/{NOTICE}/preview"), field.post(f"{base}/{NOTICE}/freeze"),
                _send(field, c), field.get("/api/settings/notice-reservations"),
                field.put(f"/api/settings/notice-reservations/{NOTICE}/bgb",
                          json={"reservation_text": None, "reviewed_on": None, "reviewed_by": None})):
        assert res.status_code == 403, res.request.url
    assert FakeSMTP.sent == [] and _letters(db) == []
    # Der Checklisten-Abruf des Monteurs trägt nichts vom Brief.
    detail = _client(nworld, router_test_client, "a").get(f"/api/checklists/{c['id']}").json()
    assert "notice" not in json.dumps(detail) and AG_EMAIL not in json.dumps(detail)


def test_letter_and_authorization_are_immutable(nworld, router_test_client):
    db = nworld["db"]
    arch = _participant(db, nworld, name="Architekt", email="arch@example.com", authorized=True)
    store_power_of_attorney(db, arch, filename="v.pdf", data=_pdf_bytes(), user_name="Olga")
    c = _signed(nworld, router_test_client)
    assert _send(_office(nworld, router_test_client), c, cc_email="arch@example.com").status_code == 200
    [letter] = _letters(db)
    letter.content = "{}"
    with pytest.raises(ArchiveImmutableError):
        db.flush()
    db.rollback()
    with pytest.raises(ArchiveImmutableError):
        db.delete(db.get(NoticeLetter, letter.id))
        db.flush()
    db.rollback()
    [row] = db.scalars(select(DispatchAuthorization)).all()
    row.note = "geändert"
    with pytest.raises(ArchiveImmutableError):
        db.flush()
    db.rollback()
    with pytest.raises(ArchiveImmutableError):
        db.delete(db.get(DispatchAuthorization, row.id))
        db.flush()
    db.rollback()


def test_new_document_types_are_registered():
    from app.document_frame import RENDERERS_USING_SHARED_FRAME
    from app.document_layout import DOCUMENT_TYPES as LAYOUT_TYPES
    from app.document_email_templates import DOCUMENT_TYPES as MAIL_TYPES
    from app.sent_documents import DOCUMENT_TYPES

    assert "notice" in RENDERERS_USING_SHARED_FRAME and "notice" in LAYOUT_TYPES
    assert {NOTICE, RESUME} <= set(DOCUMENT_TYPES) and {NOTICE, RESUME} <= MAIL_TYPES


# --- Migration ------------------------------------------------------------------------------

def _migration():
    path = next(VERSIONS.glob("*_behinderungsanzeige_brief_und_versand.py"))
    spec = importlib.util.spec_from_file_location("migration_1840_brief", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, fn_name):
    module = _migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, fn_name)()


def test_migration_creates_the_tables_and_refuses_a_lossy_downgrade():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = ("notice_letters", "notice_reservations", "dispatch_authorizations")
    with engine.begin() as conn:
        for table in tables:
            conn.execute(text(f"DROP TABLE {table}"))
    _run(engine, "upgrade")
    assert set(tables) <= set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO notice_reservations (letter_kind, basis_group, reservation_text, updated_at) "
                          "VALUES ('behinderungsanzeige', 'bgb', 'Vorbehalt', '2026-10-02 10:00:00')"))
    with pytest.raises(RuntimeError, match="Vorbehalte"):
        _run(engine, "downgrade")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM notice_reservations"))
    _run(engine, "downgrade")
    assert not set(tables) & set(inspect(engine).get_table_names())
    _run(engine, "upgrade")
    assert set(tables) <= set(inspect(engine).get_table_names())


# --- Gleichzeitig gegen PostgreSQL ----------------------------------------------------------

PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.mark.skipif(not PG_TEST_DATABASE_URL, reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
def test_postgresql_two_simultaneous_letters_make_one_version(tmp_path, monkeypatch):
    """Zwei gleichzeitige "Brief erstellen" zur selben Unterschrift: beide lesen "keine Fassung", genau eine entsteht,
    beide bekommen sie."""
    import app.checklists as checklists_module
    from app.checklist_templates import publish_draft
    from app.checklists import add_attachment, create_checklist, save_answer
    from app.models import ChecklistTemplate, Order
    from tests.test_v325_contract_basis import make_quote
    from tests.test_v341_behinderungsanzeige import MIG

    monkeypatch.setattr(checklists_module, "CHECKLIST_ROOT", tmp_path / "checklisten")
    schema = f"pgtest_brief_{uuid.uuid4().hex[:8]}"
    admin_engine = create_engine(PG_TEST_DATABASE_URL)
    with admin_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={schema}",
                                                               "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        quote = make_quote(setup)  # echtes Angebot: unter PostgreSQL hält der Fremdschlüssel source_quote_id
        order = Order(order_number="AU-2026-0001", project_id=quote.project_id, source_quote_id=quote.id,
                      quote_number_snapshot=quote.quote_number, title="Auftrag",
                      customer_name=setup.get(Project, quote.project_id).customer.name,  # wie beim Beauftragen
                      property_name="Halle", property_address="Weg 1")
        setup.add(order)
        setup.commit()
        assert MIG.insert_obstruction_template(setup.connection())
        setup.commit()
        template_id = setup.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == MIG.LABEL))
        publish_draft(setup, template_id)
        c = create_checklist(setup, template_id=template_id, context_type="auftrag", order_id=order.id)
        fields = {f["field_key"]: f["id"] for f in c["fields"]}
        for key, value in ((B + "bekannt_seit", "2026-10-02T07:45"), (B + "beschreibung", "Gerüst fehlt"),
                           (B + "ursache", "zugang_geruest"), (B + "ursache_beschreibung", "Gerüst"),
                           (B + "betroffene_leistungen", "Dach"), (B + "beginn", "2026-10-02")):
            if key == B + "ursache":
                add_attachment(setup, c["id"], fields[B + "unterschrift_meldung"], _png(), signer_name="Anna")
            save_answer(setup, c["id"], fields[key], value)
        add_attachment(setup, c["id"], fields[B + "unterschrift_buero"], _png(), signer_name="Olga")
        setup.close()

        barrier = threading.Barrier(2)
        results, errors = {}, {}

        def worker(name):
            session = Session()
            original = session.scalar
            calls = []

            def read_then_wait(*args, **kwargs):
                result = original(*args, **kwargs)
                calls.append(1)
                if len(calls) == 1:
                    try:
                        barrier.wait(timeout=5)  # beide sind bis zur Sperre gekommen
                    except threading.BrokenBarrierError:
                        pass
                return result

            session.scalar = read_then_wait
            try:
                results[name] = ensure_letter(session, c["id"], NOTICE).id
            except Exception as exc:  # noqa: BLE001 -- im Test sichtbar machen
                errors[name] = repr(exc)
            finally:
                session.close()

        threads = [threading.Thread(target=worker, args=(name,)) for name in ("A", "B")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert errors == {} and len(results) == 2 and results["A"] == results["B"], (results, errors)
        check = Session()
        assert check.scalar(select(func.count()).select_from(NoticeLetter)) == 1
        check.close()
    finally:
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n "
                              "AND pid <> pg_backend_pid()"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin_engine.dispose()
