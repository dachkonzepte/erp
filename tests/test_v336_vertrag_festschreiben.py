"""Version 1.8.33 -- Stufe 2b, Runde 2b-1b Teil 2 (Punkte 1–3 und 7): Vertrag festschreiben, Anlage,
Versand; Schnellauftrag ohne automatischen Entwurf.

Punkt 1: Festschreiben friert Vorlagentext, Verbraucher-Merkmal, Fallfelder und Anlage ein (JSON mit
Prüfsumme an der Fassung, PDF in der Ablage), sperrt den Entwurf, Änderungen nur als neue Fassung; bis
dahin folgt der Entwurf einer geänderten Vertragsgrundlage. Punkt 2: Anlage = zuletzt versendete Fassung
des Angebots, bei Abweichung oder ohne versendete Fassung bewusste Wahl. Punkt 3: Versand über
dispatch_email(), immer die festgeschriebene Fassung. Punkt 7: Schnellauftrag. Punkt 8 (Teil): Gegenproben
im Scratchpad, Monteur 403 (dazu test_v326_monteur_datengrenze.py).
"""

import hashlib
import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text

from app import sent_documents as sent_documents_module
from app.berlin_time import berlin_today
from app.contract_basis import change_order_contract_basis
from app.contract_templates import get_order_contract
from app.contract_versions import (
    ContractStateError, attachment_options, freeze_contract, pdf_plain_text, start_new_version,
)
from app.database import Base
from app.models import (
    ArchiveImmutableError, AuditLog, EmailDispatch, OrderContractVersion, QuoteItem, SentDocument,
)
from app.orders import load_order
from app.projects import load_quote, send_quote_email
from app.routers import contract_templates as contract_router
from app.routers import email_dispatches as dispatches_router_module
from app.sent_documents import read_sent_document
from tests.test_v321_email_dispatch import FakeSMTP, _attachment, _configure_smtp
from tests.test_v325_contract_basis import make_quote, pdf_text
from tests.test_v335_vertragsvorlagen import SECTIONS, beauftragen, save, section

dispatches_router = dispatches_router_module.router
CUSTOMER_EMAIL = "kunde@example.com"


@pytest.fixture
def world(threaded_db_session, monkeypatch):
    """Geprüfte Vorlage für Verbraucher, ein Verbraucher-Auftrag mit Entwurf, SMTP-Attrappe."""
    db = threaded_db_session
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    save(db, reviewed=True)
    return db


def _quote(db, number="0001", *, is_consumer=True, sent=False):
    quote = make_quote(db, number=number, is_consumer=is_consumer)
    quote.project.customer.email = CUSTOMER_EMAIL
    quote.status = "versendet"
    db.commit()
    quote = load_quote(db, quote.id)
    if sent:
        send_quote_email(db, quote, to_email=CUSTOMER_EMAIL, dispatch_key=f"angebot-{number}-versand1")
    return load_quote(db, quote.id)


def _office(db, router_test_client, role="buero_auftrag"):
    return router_test_client(db, contract_router.router, dispatches_router, role=role)


def _freeze(client, order, **payload):
    return client.post(f"/api/orders/{order.id}/contract/freeze", json=payload)


def _versions(db, order):
    db.expire_all()
    return sorted(get_order_contract(db, order.id).versions, key=lambda v: v.version_no)


def _archive_path(doc):
    return sent_documents_module.SENT_DOCUMENT_ROOT / doc.stored_filename


# --- Punkt 1: Festschreiben ---------------------------------------------------------------------

def test_freeze_archives_pdf_and_content_and_locks_the_draft(world, router_test_client):
    db = world
    order = beauftragen(db, _quote(db))
    client = _office(db, router_test_client)
    client.put(f"/api/orders/{order.id}/contract", json={"payment_plan": "30/70", "special_terms": "Gerüst stellt der Kunde"})
    res = _freeze(client, order, attachment="aktuell")
    assert res.status_code == 200, res.text
    state = res.json()["contract"]
    assert state["status"] == "festgeschrieben" and len(state["versions"]) == 1
    [version] = _versions(db, order)
    content = json.loads(version.frozen_content)
    assert version.content_sha256 == hashlib.sha256(version.frozen_content.encode("utf-8")).hexdigest()
    assert content["is_consumer"] is True and content["basis_key"] == "bgb_vob_c_4_5"
    assert content["case_fields"]["payment_plan"] == "30/70"
    assert content["template"]["reviewed_by"] == "RA Beispiel"
    assert [s["with_checkbox"] for s in content["sections"]][-1] is True  # vorzeitiger Beginn (nur Verbraucher)
    assert "Abschlaege: 30/70" in " ".join(s["text"] for s in content["sections"])
    # PDF in der Ablage mit Prüfsumme; der Abruf liefert genau diese Bytes.
    archived = _archive_path(version.sent_document).read_bytes()
    assert hashlib.sha256(archived).hexdigest() == version.sent_document.sha256
    assert version.sent_document.document_type == "vertrag" and version.sent_document.document_id == version.contract_id
    pdf = client.get(f"/api/orders/{order.id}/contract/pdf")
    assert pdf.content == archived and pdf.headers["X-DK-Ablage"] == str(version.sent_document_id)
    assert "Fassung 1" in pdf_text(archived) and "Gerüst stellt der Kunde" in pdf_text(archived)
    # Danach gesperrt: Fallfelder nicht änderbar, kein zweites Festschreiben.
    assert client.put(f"/api/orders/{order.id}/contract", json={"payment_plan": "neu"}).status_code == 422
    assert _freeze(client, order, attachment="aktuell").status_code == 409
    assert db.scalar(select(AuditLog).where(AuditLog.entity_type == "Vertrag", AuditLog.field_label == "Vertrag festgeschrieben")) is not None


def test_template_changed_afterwards_leaves_the_frozen_pdf_as_it_was(world, router_test_client):
    """Punkt 8: Festschreiben friert ein -- Vorlage danach ändern, PDF gleich."""
    db = world
    order = beauftragen(db, _quote(db))
    client = _office(db, router_test_client)
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    [version] = _versions(db, order)
    before = client.get(f"/api/orders/{order.id}/contract/pdf").content
    changed = [dict(s) for s in SECTIONS]
    changed[1]["body_text"] = "GEAENDERTER-VERTRAGSTEXT {auftragstitel}"
    save(db, sections=changed, reviewed_on=berlin_today(), by="RA Neu")
    db.commit()
    after = client.get(f"/api/orders/{order.id}/contract/pdf").content
    assert after == before and "GEAENDERTER-VERTRAGSTEXT" not in pdf_text(after)
    assert client.get(f"/api/sent-documents/{version.sent_document_id}/file").content == before
    # Gegenprobe: der Entwurf einer neuen Fassung liest die Vorlage von heute.
    assert client.post(f"/api/orders/{order.id}/contract/new-version").status_code == 200
    assert "GEAENDERTER-VERTRAGSTEXT" in pdf_text(client.get(f"/api/orders/{order.id}/contract/pdf").content)
    assert client.get(f"/api/sent-documents/{version.sent_document_id}/file").content == before


def test_unreviewed_template_is_not_frozen(world, router_test_client):
    db = world
    save(db)  # gleiche Abschnitte, ohne Prüfangaben
    order = beauftragen(db, _quote(db))
    client = _office(db, router_test_client)
    res = _freeze(client, order, attachment="aktuell")
    assert res.status_code == 409 and "nicht rechtlich geprüft" in res.json()["detail"]
    assert get_order_contract(db, order.id).status == "entwurf"
    assert db.query(OrderContractVersion).count() == 0 and db.query(SentDocument).count() == 0


def test_draft_follows_a_changed_basis_until_frozen_then_the_version_is_outdated(world, router_test_client):
    db = world
    save(db, "vob_b", sections=[section("VOB-Vertrag", "Nach VOB/B fuer {kundenname}")], title="VOB-Vertrag", reviewed=True)
    order = beauftragen(db, _quote(db, is_consumer=False))
    assert order.contract_basis == "vob_b"
    change_order_contract_basis(db, load_order(db, order.id), contract_basis="bgb_vob_c_4_5", reason="Kunde wünscht BGB")
    client = _office(db, router_test_client)
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    [version] = _versions(db, order)
    content = json.loads(version.frozen_content)
    assert version.basis_key == content["basis_key"] == "bgb_vob_c_4_5"
    assert content["title"].startswith("Bauvertrag") and version.is_consumer is False
    assert "VERTRAGSGEGENSTAND-IMMER" in pdf_text(_archive_path(version.sent_document).read_bytes())
    assert client.get(f"/api/orders/{order.id}/contract").json()["contract"]["differences"] == []
    # Nach dem Festschreiben folgt die Fassung nicht mehr: sie passt nicht zum Auftrag, Versand gesperrt.
    change_order_contract_basis(db, load_order(db, order.id), contract_basis="vob_b", reason="doch VOB/B")
    differences = client.get(f"/api/orders/{order.id}/contract").json()["contract"]["differences"]
    assert len(differences) == 1 and differences[0].startswith("Vertragsgrundlage")
    res = client.post(f"/api/orders/{order.id}/contract/send-email", json={"dispatch_key": "vertrag-alt-0001"})
    assert res.status_code == 409 and "passt nicht mehr" in res.json()["detail"]
    assert FakeSMTP.sent == [] and db.query(EmailDispatch).count() == 0


def test_changed_value_of_a_used_placeholder_makes_the_version_outdated(world, router_test_client):
    db = world
    order = beauftragen(db, _quote(db))
    client = _office(db, router_test_client)
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    item = load_order(db, order.id).items[0]
    item.unit_price = item.unit_price * 2  # Auftragssumme brutto steht im Vertragstext
    db.commit()
    differences = client.get(f"/api/orders/{order.id}/contract").json()["contract"]["differences"]
    assert any(d.startswith("Auftragssumme brutto") for d in differences), differences


def test_new_version_keeps_the_old_one_and_supersedes_it_when_frozen(world, router_test_client):
    db = world
    order = beauftragen(db, _quote(db))
    client = _office(db, router_test_client)
    assert client.post(f"/api/orders/{order.id}/contract/new-version").status_code == 409  # noch Entwurf
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    state = client.post(f"/api/orders/{order.id}/contract/new-version").json()["contract"]
    assert state["status"] == "entwurf" and [v["version_no"] for v in state["versions"]] == [1]
    # Im Entwurf wird nicht versendet, auch nicht die unveränderte letzte Fassung.
    res = client.post(f"/api/orders/{order.id}/contract/send-email", json={"dispatch_key": "vertrag-entwurf-01"})
    assert res.status_code == 409 and "nur ein festgeschriebener Vertrag" in res.json()["detail"]
    assert FakeSMTP.sent == []
    assert client.put(f"/api/orders/{order.id}/contract", json={"special_terms": "Fassung zwei"}).status_code == 200
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    first, second = _versions(db, order)
    assert first.superseded_at is not None and second.superseded_at is None
    assert "Fassung zwei" not in pdf_text(read_sent_document(first.sent_document))
    assert "Fassung zwei" in pdf_text(read_sent_document(second.sent_document))
    listed = client.get(f"/api/orders/{order.id}/contract").json()["contract"]["versions"]
    assert [(v["version_no"], v["current"]) for v in listed] == [(2, True), (1, False)]


# --- Punkt 2: Anlage ------------------------------------------------------------------------------

def test_never_sent_quote_needs_a_conscious_choice(world, router_test_client):
    db = world
    order = beauftragen(db, _quote(db))
    client = _office(db, router_test_client)
    options = client.get(f"/api/orders/{order.id}/contract/attachment-options").json()
    assert options["last_sent"] is None and options["choice_required"] is True and options["default"] is None
    res = _freeze(client, order)
    assert res.status_code == 409 and "nie versendet" in res.json()["detail"]
    assert _freeze(client, order, attachment="versendet", attachment_document_id=1).status_code == 409
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    [version] = _versions(db, order)
    attachment = json.loads(version.frozen_content)["attachment"]
    assert version.attachment_kind == attachment["kind"] == "aktuell" and version.attachment_document_id is None
    texts = pdf_text(read_sent_document(version.sent_document))
    assert f"Anlage: Angebot {order.quote_number_snapshot}" in texts and "Angebotssumme brutto" in texts


def test_unchanged_sent_quote_is_attached_without_asking(world, router_test_client):
    db = world
    quote = _quote(db, sent=True)
    [sent] = db.scalars(select(SentDocument).where(SentDocument.document_type == "angebot")).all()
    order = beauftragen(db, quote)
    client = _office(db, router_test_client)
    options = client.get(f"/api/orders/{order.id}/contract/attachment-options").json()
    assert options["matches_current"] is True and options["choice_required"] is False and options["default"] == "versendet"
    assert options["last_sent"]["sent_document_id"] == sent.id and options["last_sent"]["how"] == f"per E-Mail an {CUSTOMER_EMAIL}"
    assert _freeze(client, order).status_code == 200
    [version] = _versions(db, order)
    attachment = json.loads(version.frozen_content)["attachment"]
    assert version.attachment_kind == "versendet" and version.attachment_document_id == sent.id
    assert attachment["sha256"] == sent.sha256 and attachment["sent_on"] == berlin_today().isoformat()
    # Die angehängten Seiten sind die versendete Fassung.
    frozen = read_sent_document(version.sent_document)
    quote_pages = pdf_plain_text(read_sent_document(sent)).split("\f")
    assert pdf_plain_text(frozen).split("\f")[-len(quote_pages):] == quote_pages
    assert "versendeten Fassung" in pdf_text(frozen)


def test_quote_changed_after_sending_needs_a_conscious_choice(world, router_test_client):
    db = world
    quote = _quote(db, sent=True)
    sent = db.scalar(select(SentDocument).where(SentDocument.document_type == "angebot"))
    order = beauftragen(db, quote)
    db.get(QuoteItem, load_quote(db, quote.id).items[0].id).unit_price = 77  # 770,00 statt 500,00 netto
    db.commit()
    client = _office(db, router_test_client)
    options = client.get(f"/api/orders/{order.id}/contract/attachment-options").json()
    assert options["matches_current"] is False and options["choice_required"] is True
    res = _freeze(client, order)
    assert res.status_code == 409 and "weicht von der versendeten Fassung ab" in res.json()["detail"]
    assert _freeze(client, order, attachment="versendet", attachment_document_id=sent.id + 99).status_code == 409
    assert _freeze(client, order, attachment="versendet", attachment_document_id=sent.id).status_code == 200
    assert "770,00" not in pdf_text(read_sent_document(_versions(db, order)[0].sent_document))
    # Gegenprobe: neue Fassung mit dem heutigen Stand.
    client.post(f"/api/orders/{order.id}/contract/new-version")
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    assert "770,00" in pdf_text(read_sent_document(_versions(db, order)[1].sent_document))


def test_failed_quote_dispatch_does_not_count_as_sent(world):
    db = world
    quote = _quote(db)
    FakeSMTP.fail = OSError("Verbindung abgelehnt")
    with pytest.raises(Exception):
        send_quote_email(db, quote, to_email=CUSTOMER_EMAIL, dispatch_key="angebot-fehl-0001")
    FakeSMTP.fail = None
    assert db.query(SentDocument).count() == 1  # abgelegt, aber der Versand schlug fehl
    order = beauftragen(db, load_quote(db, quote.id))
    options = attachment_options(db, load_order(db, order.id))
    assert options["last_sent"] is None and options["choice_required"] is True


def test_damaged_sent_quote_is_never_attached(world, router_test_client):
    db = world
    quote = _quote(db, sent=True)
    sent = db.scalar(select(SentDocument).where(SentDocument.document_type == "angebot"))
    order = beauftragen(db, quote)
    path = _archive_path(sent)
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    path.write_bytes(path.read_bytes() + b"%veraendert")
    client = _office(db, router_test_client)
    options = client.get(f"/api/orders/{order.id}/contract/attachment-options").json()
    assert options["last_sent"]["intact"] is False and options["choice_required"] is True
    assert _freeze(client, order).status_code == 409
    assert _freeze(client, order, attachment="versendet", attachment_document_id=sent.id).status_code == 409
    assert _freeze(client, order, attachment="aktuell").status_code == 200


# --- Punkt 3: Versand -----------------------------------------------------------------------------

def test_sending_attaches_exactly_the_frozen_pdf_and_archives_nothing_new(world, router_test_client):
    db = world
    order = beauftragen(db, _quote(db))
    client = _office(db, router_test_client)
    assert client.get(f"/api/orders/{order.id}/contract").json()["contract"]["recipient_email"] == CUSTOMER_EMAIL
    assert _freeze(client, order, attachment="aktuell").status_code == 200
    [version] = _versions(db, order)
    archived_before = db.query(SentDocument).count()
    res = client.post(f"/api/orders/{order.id}/contract/send-email",
                      json={"to_email": CUSTOMER_EMAIL, "cc_email": "chef@example.com", "dispatch_key": "vertrag-versand-0001"})
    assert res.status_code == 200, res.text
    [mail] = FakeSMTP.sent
    assert _attachment(mail["message"]) == read_sent_document(version.sent_document)
    assert mail["message"]["Subject"] == f"Vertrag zu Auftrag {order.order_number}"
    [row] = db.scalars(select(EmailDispatch)).all()
    assert (row.document_type, row.document_id, row.status) == ("vertrag", version.contract_id, "gesendet")
    assert row.sent_document_id == version.sent_document_id and db.query(SentDocument).count() == archived_before
    assert row.document_number == f"{order.order_number} · Fassung 1"
    # Derselbe Schlüssel sendet nicht noch einmal; das Protokoll verlinkt auf den Auftrag.
    client.post(f"/api/orders/{order.id}/contract/send-email", json={"to_email": CUSTOMER_EMAIL, "dispatch_key": "vertrag-versand-0001"})
    assert len(FakeSMTP.sent) == 1
    listed = client.get("/api/email-dispatches?document_type=vertrag").json()["items"]
    assert [(d["document_id"], d["order_id"]) for d in listed] == [(version.contract_id, order.id)]


def test_contract_email_template_is_used(world, router_test_client):
    from app.document_email_templates import update_email_template
    db = world
    update_email_template(db, "contract", subject_template="Ihr Vertrag {auftragsnummer}/{fassung}",
                          body_template="Grundlage {vertragsgrundlage} für {kundenname}")
    order = beauftragen(db, _quote(db))
    client = _office(db, router_test_client)
    _freeze(client, order, attachment="aktuell")
    client.post(f"/api/orders/{order.id}/contract/send-email", json={"dispatch_key": "vertrag-vorlage-0001"})
    [mail] = FakeSMTP.sent
    assert mail["message"]["Subject"] == f"Ihr Vertrag {order.order_number}/1"
    body = next(p for p in mail["message"].walk() if p.get_content_type() == "text/plain").get_payload(decode=True).decode("utf-8")
    assert "Grundlage BGB mit VOB/C Abschnitt 4 und 5 für Kunde 0001" in body


def test_manual_delivery_of_the_contract_uses_the_frozen_version(world, router_test_client):
    db = world
    order = beauftragen(db, _quote(db))
    client = _office(db, router_test_client)
    contract_id = get_order_contract(db, order.id).id
    data = {"document_type": "vertrag", "document_id": str(contract_id), "channel": "persoenlich",
            "delivered_on": berlin_today().isoformat(), "note": "Beim Termin übergeben", "recipient": "", "dispatch_key": "vertrag-hand-0001"}
    res = client.post("/api/email-dispatches/manual", data=data)
    assert res.status_code == 400 and "festgeschrieben" in res.json()["detail"]  # Entwurf: nicht zustellbar
    _freeze(client, order, attachment="aktuell")
    [version] = _versions(db, order)
    res = client.post("/api/email-dispatches/manual", data=data)
    assert res.status_code == 200, res.text
    assert res.json()["sent_document"]["id"] == version.sent_document_id
    assert db.query(SentDocument).count() == 1  # nur die Fassung selbst, nichts neu abgelegt


# --- Rechte, Punkt 7, Unveränderlichkeit, Migration ----------------------------------------------

def test_monteur_gets_403_on_every_new_contract_route(world, router_test_client):
    db = world
    order = beauftragen(db, _quote(db))
    field = router_test_client(db, contract_router.router, role="field")
    assert field.get(f"/api/orders/{order.id}/contract/attachment-options").status_code == 403
    assert field.post(f"/api/orders/{order.id}/contract/freeze", json={"attachment": "aktuell"}).status_code == 403
    office = _office(db, router_test_client)
    assert _freeze(office, order, attachment="aktuell").status_code == 200
    assert field.get(f"/api/orders/{order.id}/contract/pdf").status_code == 403
    assert field.post(f"/api/orders/{order.id}/contract/new-version").status_code == 403
    assert field.post(f"/api/orders/{order.id}/contract/send-email", json={"dispatch_key": "vertrag-monteur-01"}).status_code == 403
    assert FakeSMTP.sent == [] and get_order_contract(db, order.id).status == "festgeschrieben"


def test_quick_order_gets_no_automatic_draft_but_one_by_hand(world, router_test_client):
    from app.models import Customer
    from app.quick_service_orders import create_quick_service_order
    db = world
    customer = Customer(name="Schnell", last_name="Schnell", is_consumer=True)
    db.add(customer)
    db.commit()
    result = create_quick_service_order(db, customer_id=customer.id, property_id=None, order_type="reparatur", title="Sturmschaden")
    order = load_order(db, result["order_id"])
    assert order.contract_basis == "bgb_vob_c_4_5"  # für diese Grundlage gibt es eine Vorlage
    assert get_order_contract(db, order.id) is None
    client = _office(db, router_test_client)
    assert client.post(f"/api/orders/{order.id}/contract").json()["contract"]["status"] == "entwurf"
    # Gegenprobe: das normale Beauftragen legt weiterhin einen an.
    assert get_order_contract(db, beauftragen(db, _quote(db, number="0002")).id) is not None


def test_frozen_version_is_unchangeable_and_keeps_its_order(world):
    db = world
    order = beauftragen(db, _quote(db))
    freeze_contract(db, load_order(db, order.id), attachment="aktuell")
    [version] = _versions(db, order)
    version.frozen_content = version.frozen_content.replace("Kunde 0001", "Kunde X")
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    with pytest.raises(ArchiveImmutableError):
        db.delete(_versions(db, order)[0])
        db.commit()
    db.rollback()
    with pytest.raises(ArchiveImmutableError):
        db.delete(load_order(db, order.id))
        db.commit()
    db.rollback()
    # superseded_at genau einmal
    start_new_version(db, load_order(db, order.id))
    freeze_contract(db, load_order(db, order.id), attachment="aktuell")
    first = _versions(db, order)[0]
    assert first.superseded_at is not None
    first.superseded_at = first.superseded_at.replace(year=2030)
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()


def test_freeze_business_function_reports_state_errors(world):
    db = world
    order = beauftragen(db, _quote(db))
    with pytest.raises(ContractStateError, match="bewusst wählen"):
        freeze_contract(db, load_order(db, order.id))
    with pytest.raises(ContractStateError, match="Eine neue Fassung"):
        start_new_version(db, load_order(db, order.id))


def _migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_vertrag_festschreiben.py"))
    spec = importlib.util.spec_from_file_location("migration_1833_vertrag_festschreiben", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, fn_name):
    module = _migration()
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, fn_name)()


def test_migration_downgrade_refuses_while_versions_exist_and_upgrade_restores():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO order_contracts (order_id, status, created_by_name, created_at, updated_at) "
                          "VALUES (1, 'festgeschrieben', 'X', '2026-10-01 00:00:00', '2026-10-01 00:00:00')"))
    with pytest.raises(RuntimeError, match="1 nicht mehr im Entwurf"):
        _run(engine, "downgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE order_contracts SET status = 'entwurf'"))
    _run(engine, "downgrade")
    assert "order_contract_versions" not in inspect(engine).get_table_names()
    _run(engine, "upgrade")
    columns = {c["name"] for c in inspect(engine).get_columns("order_contract_versions")}
    assert {"frozen_content", "content_sha256", "sent_document_id", "attachment_kind", "superseded_at"} <= columns
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO order_contract_versions (contract_id, version_no, basis_key, is_consumer, "
                          "frozen_content, content_sha256, sent_document_id, attachment_kind, created_at) "
                          "VALUES (1, 1, 'bgb', true, '{}', 'x', 1, 'aktuell', '2026-10-01 00:00:00')"))
    with pytest.raises(RuntimeError, match="1 festgeschriebene Vertragsfassungen"):
        _run(engine, "downgrade")
