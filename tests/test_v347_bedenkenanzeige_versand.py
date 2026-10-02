"""Version 1.8.44 -- Stufe 2b, Runde 2b-4 Teil 2: Bedenkenanzeige als Brief und Versand, Empfänger (Punkte 4–5 und ihre
Tests aus Punkt 6).

Punkt 4: Brief "Bedenkenanzeige" nach der Unterschrift Büro, Inhalt Meldung und Anzeige aus der versiegelten Kopie,
Vorbehalt je Vertragsgrundlage (nur geprüft gedruckt), Kopie an Beteiligte, Vollmacht beim Versand, Zustellung
nachtragen, Versandergebnis, "gegenstandslos" -- dieselben Bausteine wie die Behinderungsanzeige
(app/notice_letters.py, seit 1.8.44 Briefarten je Zweck). Nach dem Versand ist "Bedenkenanzeige versenden" erledigt und
"Antwort des Auftraggebers prüfen" angelegt (Folge nach dem Versand, 1.8.43). Punkt 5: Kundenwechsel im Projekt
gesperrt, sobald ein Auftrag einen festgeschriebenen Vertrag hat; sonst verlangen Brief und Versand beider Anzeigen
eine Bestätigung, wenn Kunde des Projekts und Kunde laut Auftrag auseinanderfallen. Herleitung:
docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.44".
"""
import hashlib
import json
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.berlin_time import berlin_today
from app.checklist_templates import publish_draft
from app.models import (
    AuditLog, ChecklistTemplate, Customer, DispatchAuthorization, NoticeLetter, OrderContractVersion, Project, Task,
    TaskColumn,
)
from app.notice_reservations import update_reservation
from app.project_participants import add_participant, store_power_of_attorney
from app.routers.checklists import router as checklists_router
from app.routers.email_dispatches import router as dispatches_router
from app.routers.notice_letters import router as notice_router
from app.routers.projects import router as projects_router
from app.settings import load_general_settings
from tests.test_v305_checklist_filling import _client, world  # noqa: F401 -- Fixture
from tests.test_v321_email_dispatch import FakeSMTP, _attachment, _configure_smtp
from tests.test_v325_contract_basis import pdf_text
from tests.test_v343_behinderungsanzeige_versand import _archive_bytes, _participant, _pdf_bytes
from tests.test_v344_behinderungsanzeige_abschluss import _manual, _outcome
from tests.test_v346_bedenkenanzeige import (  # noqa: F401 -- Fixture
    ANSWER_TITLE, K, SEND_TITLE, _decide, _notice, _report, _start, _tasks, kworld,
)

AG_EMAIL = "auftraggeber@example.com"
KIND = "bedenkenanzeige"


@pytest.fixture
def mworld(kworld, monkeypatch):
    """kworld (veröffentlichte Bedenkenanzeige, Sachbearbeiterin am Auftrag) + SMTP-Attrappe + Auftraggeber mit Anrede
    und E-Mail, Kunde laut Auftrag wie der Kunde des Projekts."""
    db = kworld["db"]
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    customer = kworld["orders"]["mine"].project.customer
    customer.email, customer.salutation = AG_EMAIL, "Frau"
    customer.first_name, customer.last_name, customer.name = "Erika", "Bauherrin", "Frau Erika Bauherrin"
    customer.street, customer.postal_code, customer.city = "Bauweg 7", "50667", "Köln"
    kworld["orders"]["mine"].customer_name = customer.name
    load_general_settings(db).company_name = "Dach GmbH"
    db.commit()
    return kworld


def _office(w, rtc, role="buero_auftrag"):
    return rtc(w["db"], checklists_router, notice_router, dispatches_router, role=role,
               employee_id=w["emps"]["office"].id)


def _signed(w, rtc, deadline="2026-10-09") -> dict:
    """Meldung von der Monteurin, Anzeige vom Büro -- beide unterschrieben."""
    field, office = _client(w, rtc, "a"), _client(w, rtc, "office")
    c = _start(w, field)
    _report(field, c)
    _notice(office, c, deadline=deadline)
    return c


def _send(client, c, kind=KIND, **payload):
    payload.setdefault("dispatch_key", f"{kind}-{uuid.uuid4().hex}")
    return client.post(f"/api/checklists/{c['id']}/notice-letters/{kind}/send-email", json=payload)


def _freeze(client, c, kind=KIND, **payload):
    return client.post(f"/api/checklists/{c['id']}/notice-letters/{kind}/freeze", json=payload or None)


def _state(client, c) -> dict:
    res = client.get(f"/api/checklists/{c['id']}/notice-letters")
    assert res.status_code == 200, res.text
    return res.json()


def _letters(db, checklist_id=None) -> list[NoticeLetter]:
    db.expire_all()
    rows = db.scalars(select(NoticeLetter).where(NoticeLetter.kind == KIND).order_by(NoticeLetter.id)).all()
    return [r for r in rows if checklist_id is None or r.checklist_id == checklist_id]


def _done(db, task) -> bool:
    db.expire_all()
    task = db.get(Task, task.id)
    return task.status in {c.key for c in db.scalars(select(TaskColumn)).all() if c.is_done}


# --- Punkt 4: der Brief -------------------------------------------------------------------------

def test_letter_from_report_and_notice_with_items_subject_copies_and_footer(mworld, router_test_client):
    db = mworld["db"]
    _participant(db, mworld, name="Architekturbüro Plan", email="arch@example.com")
    office = _office(mworld, router_test_client)
    c = _signed(mworld, router_test_client)
    # Entscheidung schon eingetragen (nicht unterschrieben) -- gehört nicht in die Bedenkenanzeige.
    assert office.put(f"/api/checklists/{c['id']}/answers/"
                      f"{next(f['id'] for f in c['fields'] if f['field_key'] == K + 'notiz')}",
                      json={"value": "intern"}).status_code == 200

    state = _state(office, c)
    assert (state["purpose"], state["purpose_label"], [k["kind"] for k in state["kinds"]]) == (
        KIND, "Bedenkenanzeige", [KIND])
    assert state["kinds"][0]["ready"] and state["customer_mismatch"] is None
    assert [s["key"] for s in state["timeline"]] == ["bekannt_seit", "meldung", "versendet"]
    assert state["timeline"][0]["at_local"] == "2026-10-02T07:45"
    assert state["cc_prefill"] == "arch@example.com"
    assert _freeze(office, c).status_code == 200
    [letter] = _letters(db)
    content = json.loads(letter.content)
    assert (content["subject"], content["kind"], content["source_label"]) == ("Bedenkenanzeige", KIND, "Bedenkenanzeige")
    assert content["salutation"] == "Sehr geehrte Frau Bauherrin,"
    assert content["intro"].startswith("hiermit melden wir Ihnen Bedenken")
    assert [(i["label"], i["value"]) for i in content["items"]] == [
        ("Bekannt seit", "02.10.2026, 07:45 Uhr"), ("Beschreibung", "Gelieferte Dämmplatten sind nass"),
        ("Bedenken gegen", "vorgesehene Art der Ausführung, vom Auftraggeber gelieferte Stoffe oder Bauteile"),
        ("Begründung", "Durchfeuchtete Dämmung verliert ihre Wirkung"),
        ("Mögliche Folgen", "Tauwasser, Schimmel, Mängelansprüche"),
        ("Vorschlag zur Abhilfe", "Neue, trockene Platten liefern"), ("Entscheidung erbeten bis", "09.10.2026")]
    assert content["signature"]["field_key"] == K + "unterschrift_buero"
    assert len(content["photos"]) == 1 and content["copy_to"][0]["name"] == "Architekturbüro Plan"
    doc = letter.sent_document
    assert (doc.document_type, doc.document_id, doc.filename) == (KIND, c["id"], "Bedenkenanzeige_AU-2026-0001_Fassung_1.pdf")
    text_ = pdf_text(_archive_bytes(doc))
    for expected in ("Bedenkenanzeige", "Sehr geehrte Frau Bauherrin,", "vom Auftraggeber gelieferte Stoffe oder Bauteile",
                     "Entscheidung erbeten bis", "09.10.2026",
                     "Kopie an:", f"Erstellt aus der Bedenkenanzeige Nr. {c['id']}", letter.signature_sha256):
        assert expected in text_, expected
    assert "intern" not in text_ and "Behinderung" not in text_


def test_letter_only_after_the_office_signature_and_only_kinds_of_the_purpose(mworld, router_test_client):
    office = _office(mworld, router_test_client)
    field = _client(mworld, router_test_client, "a")
    c = _start(mworld, field)
    _report(field, c)
    state = _state(office, c)
    assert not state["kinds"][0]["ready"] and "Unterschrift Büro" in state["kinds"][0]["waiting_text"]
    res = _freeze(office, c)
    assert res.status_code == 409 and "Unterschrift Büro" in res.json()["detail"]
    assert _send(office, c).status_code == 409 and FakeSMTP.sent == []
    for kind in ("behinderungsanzeige", "wiederaufnahme"):  # Briefe einer anderen Anzeige
        assert office.get(f"/api/checklists/{c['id']}/notice-letters/{kind}/preview").status_code == 404
        assert _freeze(office, c, kind=kind).status_code == 404
    other = office.post("/api/checklists", json={"template_id": mworld["order_tpl"]["id"], "context_type": "auftrag",
                                                  "order_id": mworld["orders"]["mine"].id}).json()
    assert office.get(f"/api/checklists/{other['id']}/notice-letters").status_code == 404


def test_reservation_per_contract_basis_printed_only_when_reviewed(mworld, router_test_client):
    db = mworld["db"]
    office = _office(mworld, router_test_client)
    update_reservation(db, KIND, "vob_b", reservation_text="Vorbehalt nach § 4 Abs. 3 VOB/B.", reviewed_on=berlin_today(),
                       reviewed_by="RA Beispiel")
    update_reservation(db, KIND, "bgb", reservation_text="Vorbehalt BGB (ungeprüft).", reviewed_on=None, reviewed_by=None)
    order = mworld["orders"]["mine"]
    order.contract_basis = "vob_b"
    db.commit()
    c = _signed(mworld, router_test_client)
    assert _state(office, c)["kinds"][0]["reservation"]["reviewed"] is True
    assert _freeze(office, c).status_code == 200
    [letter] = _letters(db)
    assert letter.reservation_printed and "Vorbehalt nach § 4 Abs. 3 VOB/B." in pdf_text(_archive_bytes(letter.sent_document))
    order.contract_basis = "bgb_vob_c_4_5"
    db.commit()
    c2 = _signed(mworld, router_test_client)
    assert _state(office, c2)["kinds"][0]["reservation"]["reviewed"] is False
    assert _freeze(office, c2).status_code == 200
    [letter2] = _letters(db, c2["id"])
    assert not letter2.reservation_printed and "ungeprüft" not in pdf_text(_archive_bytes(letter2.sent_document))
    rows = {(r["letter_kind"], r["basis_group"]) for r in office.get("/api/settings/notice-reservations").json()}
    assert {(KIND, "vob_b"), (KIND, "bgb")} <= rows


def test_send_by_mail_completes_send_task_creates_answer_task_and_freezes_power_of_attorney(mworld, router_test_client):
    db = mworld["db"]
    arch = _participant(db, mworld, name="Architekt", email="arch@example.com", authorized=True)
    poa_bytes = _pdf_bytes()
    store_power_of_attorney(db, arch, filename="v.pdf", data=poa_bytes, user_name="Olga")
    office = _office(mworld, router_test_client)
    c = _signed(mworld, router_test_client, deadline="2026-10-12")
    [send_task] = _tasks(db, SEND_TITLE)
    assert not _done(db, send_task) and _tasks(db, ANSWER_TITLE) == []
    res = _send(office, c, cc_email="arch@example.com")
    assert res.status_code == 200, res.text
    [mail] = FakeSMTP.sent
    assert sorted(mail["recipients"]) == sorted([AG_EMAIL, "arch@example.com"])
    from email.header import decode_header, make_header
    subject = str(make_header(decode_header(mail["message"]["Subject"])))
    assert mail["message"]["To"] == AG_EMAIL and subject == "Bedenkenanzeige – Auftrag AU-2026-0001"
    [letter] = _letters(db)
    assert _attachment(mail["message"]) == _archive_bytes(letter.sent_document)
    assert _done(db, send_task)
    [answer] = _tasks(db, ANSWER_TITLE)
    assert answer.due_date == date(2026, 10, 12) and not _done(db, answer)
    [poa] = db.scalars(select(DispatchAuthorization)).all()
    from app.models import EmailDispatch
    assert db.get(EmailDispatch, poa.dispatch_id).document_type == KIND and _archive_bytes(poa.sent_document) == poa_bytes
    state = _state(office, c)
    assert state["kinds"][0]["status"] == "versendet" and state["timeline"][2]["at_local"]
    # Zweiter Versand: keine zweite Antwort-Aufgabe; die Entscheidung erledigt sie.
    assert _send(office, c).status_code == 200 and len(_tasks(db, ANSWER_TITLE)) == 1
    _decide(office, c)
    assert _done(db, answer)


def test_recorded_delivery_to_the_client_counts_a_copy_does_not_and_undeliverable_reopens(mworld, router_test_client):
    db = mworld["db"]
    office = _office(mworld, router_test_client)
    copy = _participant(db, mworld, name="Gutachter Kopie", email=None)
    c = _signed(mworld, router_test_client)
    [send_task] = _tasks(db, SEND_TITLE)
    res = _manual(office, KIND, c["id"], participant_ids=[copy.id], note="Kopie per Post")
    assert res.status_code == 200, res.text
    assert not _done(db, send_task) and _tasks(db, ANSWER_TITLE) == []  # nur eine Kopie
    res = _manual(office, KIND, c["id"], to_client=True)
    assert res.status_code == 200, res.text
    assert _done(db, send_task) and len(_tasks(db, ANSWER_TITLE)) == 1
    assert len(_letters(db)) == 1  # eine Fassung für beide Zustellungen
    res = _outcome(office, res.json()["id"], "unzustellbar", note="Annahme verweigert")
    assert res.status_code == 200, res.text
    assert not _done(db, send_task)  # wieder offen -- die Anzeige muss noch hinaus
    assert _state(office, c)["kinds"][0]["status"] == "unzustellbar"


def test_void_concern_sends_nothing_but_keeps_a_created_letter(mworld, router_test_client):
    db = mworld["db"]
    office = _office(mworld, router_test_client)
    c = _signed(mworld, router_test_client)
    assert _freeze(office, c).status_code == 200
    assert office.post(f"/api/checklists/{c['id']}/void", json={"reason": "Platten getauscht"}).status_code == 200
    res = _send(office, c)
    assert res.status_code == 409 and "gegenstandslos" in res.json()["detail"]
    assert FakeSMTP.sent == [] and len(_letters(db)) == 1
    assert _state(office, c)["voided"] is True
    assert _manual(office, KIND, c["id"], to_client=True).status_code == 200  # schon erstellte Fassung nachtragbar


# --- Punkt 5: Empfänger -------------------------------------------------------------------------

def _audit_labels(db) -> list[str]:
    db.expire_all()
    return [a.field_label for a in db.scalars(select(AuditLog).order_by(AuditLog.id)).all() if a.field_label]


def test_both_notices_need_a_confirmation_when_project_and_order_customer_differ(mworld, router_test_client):
    db = mworld["db"]
    from tests.test_v341_behinderungsanzeige import MIG as OBSTRUCTION_MIG
    from tests.test_v341_behinderungsanzeige import _notice as obstruction_notice
    from tests.test_v341_behinderungsanzeige import _report as obstruction_report

    office = _office(mworld, router_test_client)
    c = _signed(mworld, router_test_client)
    order = mworld["orders"]["mine"]
    order.customer_name = "Alte Hausverwaltung GmbH"  # Schnappschuss beim Beauftragen -- inzwischen anderer Kunde
    db.commit()
    mismatch = _state(office, c)["customer_mismatch"]
    assert mismatch["project_customer"] == "Frau Erika Bauherrin" and mismatch["order_customer"] == "Alte Hausverwaltung GmbH"
    for res in (_freeze(office, c), _send(office, c)):
        assert res.status_code == 409 and "weicht vom Kunden laut Auftrag AU-2026-0001" in res.json()["detail"]
    assert _letters(db) == [] and FakeSMTP.sent == []
    assert _freeze(office, c, confirm_customer=True).status_code == 200
    assert _send(office, c).status_code == 409  # der Versand fragt erneut (eigene Bestätigung)
    assert _send(office, c, confirm_customer=True).status_code == 200
    labels = _audit_labels(db)
    assert "Bedenkenanzeige als Brief erstellt" in labels and "Bedenkenanzeige: abweichender Kunde bestätigt" in labels
    created = next(a for a in db.scalars(select(AuditLog)).all() if a.field_label == "Bedenkenanzeige als Brief erstellt")
    assert "abweichend vom Kunden laut Auftrag (Alte Hausverwaltung GmbH) – bestätigt" in created.new_value

    # Dieselbe Regel an der Behinderungsanzeige.
    assert OBSTRUCTION_MIG.insert_obstruction_template(db.connection())
    db.commit()
    tpl = publish_draft(db, db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == OBSTRUCTION_MIG.LABEL)))
    field = _client(mworld, router_test_client, "a")
    b = field.post("/api/checklists", json={"template_id": tpl["id"], "context_type": "auftrag", "order_id": order.id}).json()
    obstruction_report(field, b)
    obstruction_notice(_client(mworld, router_test_client, "office"), b)
    assert _state(office, b)["customer_mismatch"] is not None
    res = _send(office, b, kind="behinderungsanzeige")
    assert res.status_code == 409 and "weicht vom Kunden laut Auftrag" in res.json()["detail"]
    assert _send(office, b, kind="behinderungsanzeige", confirm_customer=True).status_code == 200


def test_customer_number_decides_when_both_sides_have_one(mworld, router_test_client):
    from app.models import CustomerProfile
    from app.notice_letters import customer_mismatch
    db = mworld["db"]
    order = mworld["orders"]["mine"]
    customer = order.project.customer
    db.add(CustomerProfile(customer_id=customer.id, customer_number="K-100"))
    db.commit()
    db.refresh(customer)
    order.customer_number, order.customer_name = "K-100", "Bauherrin (alter Name)"
    assert customer_mismatch(order, customer) is None  # gleiche Nummer, anderer Name: derselbe Kunde
    order.customer_number = "K-200"
    assert customer_mismatch(order, customer)["order_customer"] == "Bauherrin (alter Name) (K-200)"
    order.customer_number = None
    assert customer_mismatch(order, customer) is not None  # ohne Nummer zählt der Name
    order.customer_name = "  frau erika   BAUHERRIN "
    assert customer_mismatch(order, customer) is None  # Groß-/Kleinschreibung und Leerraum zählen nicht
    assert customer_mismatch(order, None) is None


def test_client_change_locked_once_an_order_has_a_frozen_contract(threaded_db_session, router_test_client):
    from app.contract_versions import freeze_contract
    from app.orders import load_order
    from tests.test_v325_contract_basis import make_quote
    from tests.test_v335_vertragsvorlagen import beauftragen, save

    db = threaded_db_session
    save(db, reviewed=True)
    order = beauftragen(db, make_quote(db, number="V1"))  # legt den Vertragsentwurf an
    project = db.get(Project, order.project_id)
    other = Customer(name="Neuer Bauherr", last_name="Neuer Bauherr")
    db.add(other)
    db.commit()
    client = router_test_client(db, projects_router, role="buero_auftrag")
    body = {"customer_id": other.id, "property_id": None, "name": project.name, "status": project.status,
            "description": project.description}
    old_customer = project.customer_id
    # Nur ein Entwurf: der Wechsel geht (und zurück).
    assert client.put(f"/api/projects/{project.id}", json=body).status_code == 200
    assert client.put(f"/api/projects/{project.id}", json={**body, "customer_id": old_customer}).status_code == 200
    freeze_contract(db, load_order(db, order.id), attachment="aktuell")
    assert db.scalar(select(OrderContractVersion.version_no)) == 1
    res = client.put(f"/api/projects/{project.id}", json=body)
    assert res.status_code == 409, res.text
    assert "Auftrag" in res.json()["detail"] and "festgeschriebenen Vertrag (Fassung 1)" in res.json()["detail"]
    db.expire_all()
    assert db.get(Project, project.id).customer_id == old_customer
    # Derselbe Kunde, nur der Name des Projekts: geht.
    assert client.put(f"/api/projects/{project.id}", json={**body, "customer_id": old_customer, "name": "Neu"}).status_code == 200


# --- Rechte, Registrierung ----------------------------------------------------------------------

def test_monteur_gets_403_at_every_letter_route_of_the_concern(mworld, router_test_client):
    db = mworld["db"]
    c = _signed(mworld, router_test_client)
    field = router_test_client(db, checklists_router, notice_router, dispatches_router, role="field",
                               employee_id=mworld["emps"]["a"].id)
    base = f"/api/checklists/{c['id']}/notice-letters"
    for res in (field.get(base), field.get(f"{base}/{KIND}/preview"), field.post(f"{base}/{KIND}/freeze"),
                _send(field, c), field.put(f"/api/settings/notice-reservations/{KIND}/bgb",
                                           json={"reservation_text": None, "reviewed_on": None, "reviewed_by": None})):
        assert res.status_code == 403, res.request.url
    assert FakeSMTP.sent == [] and _letters(db) == []
    detail = _client(mworld, router_test_client, "a").get(f"/api/checklists/{c['id']}").json()
    dumped = json.dumps(detail)
    assert "notice" not in dumped and AG_EMAIL not in dumped and "customer_mismatch" not in dumped


def test_bedenkenanzeige_is_registered_everywhere():
    from app.dispatch_documents import _REGISTRY
    from app.document_email_templates import DOCUMENT_TYPES as MAIL_TYPES
    from app.notice_letters import LETTER_KINDS, NOTICE_PURPOSES
    from app.notice_reservations import RESERVATION_LETTER_KINDS
    from app.routers.email_dispatches import CHECKLIST_DOCUMENT_TYPES
    from app.sent_documents import DOCUMENT_TYPES

    assert LETTER_KINDS[KIND].purpose == KIND and LETTER_KINDS[KIND].is_main and KIND in NOTICE_PURPOSES
    assert not LETTER_KINDS["wiederaufnahme"].is_main
    for registry in (_REGISTRY, MAIL_TYPES, RESERVATION_LETTER_KINDS, CHECKLIST_DOCUMENT_TYPES, DOCUMENT_TYPES):
        assert KIND in registry
    assert set(LETTER_KINDS) <= set(RESERVATION_LETTER_KINDS) <= set(DOCUMENT_TYPES)


def test_letter_content_checksum_and_archive_are_consistent(mworld, router_test_client):
    db = mworld["db"]
    c = _signed(mworld, router_test_client)
    assert _freeze(_office(mworld, router_test_client), c).status_code == 200
    [letter] = _letters(db)
    assert letter.content_sha256 == hashlib.sha256(letter.content.encode("utf-8")).hexdigest()
    assert hashlib.sha256(_archive_bytes(letter.sent_document)).hexdigest() == letter.sent_document.sha256
