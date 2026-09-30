"""Versand fertigstellen, Teil 2 (1.8.20, Stufe 2, Runde 2a-3b, Punkte 5-8).

5. Versandverlauf am Dokument: E-Mail-Versände und nachgetragene Zustellungen aus dem Protokoll,
   auf Angebot, Auftrag, Rechnung, Mahnung und Checkliste statt "zuletzt versendet an".
6. Checkliste per E-Mail: Versand-PDF mit verkleinerten Fotos unter 3.000.000 Bytes, die Originale
   bleiben byte-gleich; der PDF-Knopf liefert weiter volle Auflösung.
7. Zustellung auf anderem Weg (Einschreiben, persönliche Übergabe, Bote, Fax) mit Datum, Notiz und
   optional Beleg -- im Protokoll und in der Ablage.
"""

import hashlib
import random
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

import app.checklists as checklists_module
from app.berlin_time import berlin_today
from app.checklist_pdf import build_checklist_email_pdf, build_checklist_pdf
from app.checklist_templates import add_field, create_template, publish_draft
from app.email_sending import MAX_ATTACHMENT_BYTES
from app.invoices import send_invoice_email
from app.models import (
    ArchiveImmutableError, Checklist, ChecklistAttachment, Customer, EmailDispatch, EnabledModule, Invoice, SentDocument,
)
from app.routers.checklists import router as checklists_router
from app.routers.email_dispatches import router as dispatches_router
from app.routers.invoices import router as invoices_router
from app.sent_documents import frozen_version
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v305_checklist_filling import _png, world  # noqa: F401 -- Fixture
from tests.test_v321_email_dispatch import FakeSMTP, _archive_path, _attachment, _configure_smtp, _dispatches

APP = Path(__file__).resolve().parent.parent / "app"
PHOTO_COUNT = 20


def _photo(seed: int) -> bytes:
    """Fotoähnlich: Rauschen in grober Auflösung, weich hochskaliert -- ein JPEG in der Größe
    echter Handyfotos nach der Verkleinerung auf 1600 px (einige hundert KB)."""
    rng = random.Random(seed)
    small = Image.frombytes("RGB", (200, 150), rng.randbytes(200 * 150 * 3))
    buf = BytesIO()
    small.resize((2000, 1500), Image.BILINEAR).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _jpeg_receipt() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (400, 300), (240, 240, 230)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def smtp_world(world, monkeypatch):
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    db = world["db"]
    _configure_smtp(db)
    db.get(Customer, world["orders"]["mine"].project.customer_id).email = "kunde@nord.example"
    db.commit()
    return world


def _office(world, router_test_client, role="buero_auftrag"):
    return router_test_client(world["db"], checklists_router, dispatches_router, role=role,
                              employee_id=world["emps"]["office"].id)


def _field(world, router_test_client):
    return router_test_client(world["db"], checklists_router, dispatches_router, role="field",
                              employee_id=world["emps"]["a"].id)


@pytest.fixture
def photo_checklist(smtp_world, router_test_client):
    """Abgeschlossene Checkliste am Auftrag mit 20 Fotos und einer Unterschrift (vom Monteur)."""
    db = smtp_world["db"]
    t = create_template(db, label="Fotodokumentation", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "foto", "label": "Fotos", "field_key": "fotos",
                                          "multiple": True, "min_count": 1, "max_count": PHOTO_COUNT})
    add_field(db, t["draft_version_id"], {"field_type": "unterschrift", "label": "Unterschrift Monteur", "field_key": "sig",
                                          "required": True})
    tpl = publish_draft(db, t["id"])
    field = _field(smtp_world, router_test_client)
    c = field.post("/api/checklists", json={"template_id": tpl["id"], "context_type": "auftrag",
                                             "order_id": smtp_world["orders"]["mine"].id}).json()
    ids = {f["field_key"]: f["id"] for f in c["fields"]}
    for n in range(PHOTO_COUNT):
        assert field.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": ids["fotos"]},
                          files={"file": (f"f{n}.jpg", _photo(n), "image/jpeg")}).status_code == 200
    assert field.post(f"/api/checklists/{c['id']}/attachments", data={"field_id": ids["sig"], "signer_name": "Anna Alpha"},
                      files={"file": ("s.png", _png(), "image/png")}).status_code == 200
    assert field.post(f"/api/checklists/{c['id']}/complete").status_code == 200
    checklist = db.get(Checklist, c["id"])
    return smtp_world, checklist


def _photo_hashes(checklist):
    return {a.id: hashlib.sha256(checklists_module.attachment_path(a).read_bytes()).hexdigest()
            for a in checklist.attachments if a.kind == "foto"}


# --- 6. Versand-PDF der Checkliste ----------------------------------------------------------

def test_email_pdf_with_20_photos_stays_under_the_limit_and_originals_stay(photo_checklist):
    world, checklist = photo_checklist
    db = world["db"]
    before = _photo_hashes(checklist)
    assert len(before) == PHOTO_COUNT
    full = build_checklist_pdf(db, checklist)
    assert len(full) > MAX_ATTACHMENT_BYTES, "ohne Verkleinerung wäre das PDF zu groß -- sonst prüft der Test nichts"
    small = build_checklist_email_pdf(db, checklist)
    assert small.startswith(b"%PDF") and len(small) <= MAX_ATTACHMENT_BYTES
    assert small.count(b"/Subtype /Image") >= PHOTO_COUNT + 1  # alle Fotos und die Unterschrift sind drin
    assert b"Die Originale liegen" in _extract_pdf_text(small)
    assert b"Die Originale liegen" not in _extract_pdf_text(full)
    assert _photo_hashes(checklist) == before, "die Originalfotos dürfen sich nicht ändern"


def test_checklist_is_sent_with_the_small_pdf_and_archived(photo_checklist, router_test_client):
    world, checklist = photo_checklist
    db = world["db"]
    before = _photo_hashes(checklist)
    office = _office(world, router_test_client)
    assert office.get(f"/api/checklists/{checklist.id}/email-recipient").json() == {"recipient_email": "kunde@nord.example"}
    response = office.post(f"/api/checklists/{checklist.id}/send-email",
                           json={"cc_email": "chef@nord.example", "dispatch_key": "checkliste-versand-0001"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["document_type"], body["document_id"], body["status"]) == ("checkliste", checklist.id, "gesendet")
    assert (body["to_recipients"], body["cc_recipients"]) == ("kunde@nord.example", "chef@nord.example")
    [mail] = FakeSMTP.sent
    attached = _attachment(mail["message"])
    assert len(attached) <= MAX_ATTACHMENT_BYTES
    [row] = _dispatches(db)
    assert _archive_path(row.sent_document).read_bytes() == attached
    assert row.subject == f"Fotodokumentation – Checkliste Nr. {checklist.id}"
    assert "Auftrag AU-2026-0001" in mail["message"].get_payload()[0].get_payload(decode=True).decode("utf-8")
    assert _photo_hashes(checklist) == before
    download = office.get(f"/api/checklists/{checklist.id}/pdf")
    assert download.status_code == 200 and len(download.content) > MAX_ATTACHMENT_BYTES  # Download: volle Auflösung


def test_too_large_even_when_reduced_gives_a_clear_message(photo_checklist, router_test_client, monkeypatch):
    import app.email_sending as email_sending_module
    world, checklist = photo_checklist
    monkeypatch.setattr(email_sending_module, "MAX_ATTACHMENT_BYTES", 40_000)
    response = _office(world, router_test_client).post(
        f"/api/checklists/{checklist.id}/send-email", json={"dispatch_key": "checkliste-gross-0001"})
    assert response.status_code == 400 and "Zustellung nachtragen" in response.json()["detail"]
    assert FakeSMTP.sent == [] and _dispatches(world["db"]) == []


def test_checklist_sending_is_office_only_and_needs_completion(smtp_world, router_test_client):
    db = smtp_world["db"]
    field = _field(smtp_world, router_test_client)
    c = field.post("/api/checklists", json={"template_id": smtp_world["order_tpl"]["id"], "context_type": "auftrag",
                                             "order_id": smtp_world["orders"]["mine"].id}).json()
    office = _office(smtp_world, router_test_client)
    draft = office.post(f"/api/checklists/{c['id']}/send-email", json={"to_email": "a@b.de", "dispatch_key": "checkliste-entwurf-01"})
    assert draft.status_code == 400 and "abgeschlossene" in draft.json()["detail"]
    for path, kwargs in ((f"/api/checklists/{c['id']}/send-email", {"json": {"to_email": "a@b.de", "dispatch_key": "checkliste-monteur-01"}}),):
        assert field.post(path, **kwargs).status_code == 403
    assert field.get(f"/api/checklists/{c['id']}/email-recipient").status_code == 403
    db.add(EnabledModule(module_key="checklisten", enabled=False))
    db.commit()
    assert office.post(f"/api/checklists/{c['id']}/send-email", json={"to_email": "a@b.de", "dispatch_key": "checkliste-modul-001"}).status_code == 403
    assert FakeSMTP.sent == []


# --- 7. Zustellung auf anderem Weg ----------------------------------------------------------

@pytest.fixture
def invoice_world(threaded_db_session, monkeypatch):
    db = threaded_db_session
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    return db, make_sent_overdue_invoice(db)


def _manual(client, document_type, document_id, *, key, channel="einschreiben", delivered_on=None, note="Sendungsnummer RR 1234 5678 9DE",
            recipient="Test Kunde, Dachstr. 1", receipt=None):
    data = {"document_type": document_type, "document_id": str(document_id), "channel": channel,
            "delivered_on": (delivered_on or berlin_today()).isoformat(), "note": note, "recipient": recipient,
            "dispatch_key": key}
    files = {"receipt": receipt} if receipt else None
    return client.post("/api/email-dispatches/manual", data=data, files=files)


def test_manual_delivery_lands_in_log_and_archive(invoice_world, router_test_client):
    db, invoice = invoice_world
    office = router_test_client(db, dispatches_router, invoices_router, role="buero_auftrag")
    receipt = _jpeg_receipt()
    response = _manual(office, "rechnung", invoice.id, key="manuell-rechnung-0001", delivered_on=berlin_today() - timedelta(days=2),
                       receipt=("C:\\fakepath\\Einlieferungsbeleg.jpg", receipt, "image/jpeg"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["channel"], body["channel_label"], body["manual"]) == ("gesendet", "einschreiben", "Einschreiben", True)
    assert body["delivered_on"] == (berlin_today() - timedelta(days=2)).isoformat()
    assert (body["delivery_note"], body["to_recipients"]) == ("Sendungsnummer RR 1234 5678 9DE", "Test Kunde, Dachstr. 1")
    assert body["subject"] == f"Einschreiben – Rechnung {invoice.invoice_number}"
    assert FakeSMTP.sent == [], "beim Nachtragen wird nichts gesendet"
    [row] = _dispatches(db)
    assert row.sent_document.content_type == "application/pdf" and _archive_path(row.sent_document).read_bytes().startswith(b"%PDF")
    assert row.receipt_document.content_type == "image/jpeg" and row.receipt_document.filename == "Einlieferungsbeleg.jpg"
    assert _archive_path(row.receipt_document).read_bytes() == receipt
    served = office.get(f"/api/sent-documents/{row.receipt_document_id}/file")
    assert served.status_code == 200 and served.headers["content-type"] == "image/jpeg" and served.content == receipt
    assert served.headers["x-content-type-options"] == "nosniff"
    # ab jetzt maßgeblich: Nachdruck = die bei der Zustellung abgelegte Fassung
    assert frozen_version(db, "rechnung", invoice.id).id == row.sent_document_id
    assert office.get(f"/api/invoices/{invoice.id}/pdf").content == _archive_path(row.sent_document).read_bytes()
    # derselbe Schlüssel noch einmal: kein zweiter Eintrag
    assert _manual(office, "rechnung", invoice.id, key="manuell-rechnung-0001").status_code == 200
    assert len(_dispatches(db)) == 1 and len(db.scalars(select(SentDocument)).all()) == 2


def test_manual_delivery_uses_the_archived_version_once_there_is_one(invoice_world, router_test_client):
    db, invoice = invoice_world
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-zuerst-0001")
    [sent] = _dispatches(db)
    office = router_test_client(db, dispatches_router, role="buero_auftrag")
    assert _manual(office, "rechnung", invoice.id, key="manuell-rechnung-0002", channel="fax", recipient="0421 12345").status_code == 200
    _sent, manual = _dispatches(db)
    assert manual.sent_document_id == sent.sent_document_id and manual.receipt_document_id is None
    assert len(db.scalars(select(SentDocument)).all()) == 1


@pytest.mark.parametrize("change,status,text", [
    ({"delivered_on": date.today() + timedelta(days=2)}, 400, "Zukunft"),
    ({"note": "  "}, 400, "Notiz"),
    ({"channel": "brieftaube"}, 400, "Weg"),
    ({"receipt": ("bild.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "image/svg+xml")}, 400, "Foto"),
    ({"receipt": ("beleg.jpg", b"<html><script>alert(1)</script></html>", "image/jpeg")}, 400, "Foto"),
])
def test_invalid_manual_delivery_writes_nothing(invoice_world, router_test_client, change, status, text):
    db, invoice = invoice_world
    office = router_test_client(db, dispatches_router, role="buero_auftrag")
    kwargs = {"key": "manuell-falsch-0001", **change}
    if "delivered_on" in change and change["delivered_on"] <= berlin_today():
        pytest.skip("Datum liegt nicht in der Zukunft (Zeitzone)")
    response = _manual(office, "rechnung", invoice.id, **kwargs)
    assert response.status_code == status and text in response.json()["detail"], response.text
    assert _dispatches(db) == [] and db.scalars(select(SentDocument)).all() == []


def test_too_large_receipt_is_rejected(invoice_world, router_test_client, monkeypatch):
    import app.email_dispatch as dispatch_module
    import app.routers.email_dispatches as router_module
    db, invoice = invoice_world
    monkeypatch.setattr(dispatch_module, "MAX_RECEIPT_BYTES", 1000)
    monkeypatch.setattr(router_module, "MAX_RECEIPT_BYTES", 1000)
    office = router_test_client(db, dispatches_router, role="buero_auftrag")
    response = _manual(office, "rechnung", invoice.id, key="manuell-gross-0001", receipt=("b.jpg", _jpeg_receipt(), "image/jpeg"))
    assert response.status_code == 400 and _dispatches(db) == []


def test_manual_delivery_rights_and_documents(invoice_world, router_test_client):
    db, invoice = invoice_world
    field = router_test_client(db, dispatches_router, role="field")
    assert _manual(field, "rechnung", invoice.id, key="manuell-monteur-0001").status_code == 403
    office = router_test_client(db, dispatches_router, role="buero_auftrag")
    assert _manual(office, "rechnung", 999999, key="manuell-fehlt-00001").status_code == 404
    assert _manual(office, "aufgabe", 1, key="manuell-aufgabe-0001").status_code == 404
    from app.invoices import create_schlussrechnung
    draft = create_schlussrechnung(db, invoice.order, due_date=date.today())
    assert db.get(Invoice, draft.id).status == "entwurf"
    response = _manual(office, "rechnung", draft.id, key="manuell-entwurf-0001")
    assert response.status_code == 400 and "Entwurf" in response.json()["detail"]
    assert _dispatches(db) == []


def test_manual_entry_is_unchangeable(invoice_world, router_test_client):
    db, invoice = invoice_world
    office = router_test_client(db, dispatches_router, role="buero_auftrag")
    assert _manual(office, "rechnung", invoice.id, key="manuell-fest-00001").status_code == 200
    [row] = _dispatches(db)
    row.delivery_note = "nachträglich anders"
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()


def test_manual_delivery_of_a_checklist_archives_the_full_pdf(photo_checklist, router_test_client):
    world, checklist = photo_checklist
    office = _office(world, router_test_client)
    response = _manual(office, "checkliste", checklist.id, key="manuell-checkliste-01", channel="persoenlich",
                       recipient="Herr Nord", note="Ausdruck vor Ort übergeben")
    assert response.status_code == 200, response.text
    [row] = _dispatches(world["db"])
    archived = _archive_path(row.sent_document).read_bytes()
    assert len(archived) > MAX_ATTACHMENT_BYTES and b"Die Originale liegen" not in _extract_pdf_text(archived)
    assert row.subject == f"Persönliche Übergabe – Checkliste Nr. {checklist.id} (Fotodokumentation)"


# --- 5. Versandverlauf am Dokument ----------------------------------------------------------

def test_history_of_a_document_shows_email_and_manual_deliveries(invoice_world, router_test_client):
    db, invoice = invoice_world
    send_invoice_email(db, invoice, to_email="kunde@example.com", cc_email="chef@example.com", dispatch_key="rechnung-verlauf-0001")
    office = router_test_client(db, dispatches_router, role="buero_auftrag")
    assert _manual(office, "rechnung", invoice.id, key="manuell-verlauf-0001", channel="bote", recipient="",
                   receipt=("scan.pdf", b"%PDF-1.4 Botenquittung", "application/pdf")).status_code == 200
    other = make_sent_overdue_invoice(db, suffix="0002")
    send_invoice_email(db, other, to_email="kunde@example.com", dispatch_key="rechnung-verlauf-0002")
    items = office.get(f"/api/email-dispatches?document_type=rechnung&document_id={invoice.id}").json()["items"]
    assert [(d["channel_label"], d["manual"]) for d in items] == [("Bote", True), ("SMTP", False)]
    manual, email = items
    assert manual["receipt_document"]["content_type"] == "application/pdf" and manual["delivery_note"]
    assert (email["to_recipients"], email["cc_recipients"]) == ("kunde@example.com", "chef@example.com")
    assert router_test_client(db, dispatches_router, role="field").get(
        f"/api/email-dispatches?document_type=rechnung&document_id={invoice.id}").status_code == 403


@pytest.mark.parametrize("template,call", [
    ("invoice_detail.html", "renderDispatchHistory('invoiceDispatchHistory','rechnung'"),
    ("order.html", "renderDispatchHistory('orderDispatchHistory','auftrag'"),
    ("quote_editor.html", "renderDispatchHistory('quoteDispatchHistory','angebot'"),
    ("mahnwesen.html", "renderDispatchHistory('dh'+id, 'mahnung'"),
    ("checklist.html", "renderDispatchHistory('clDispatchHistory','checkliste'"),
])
def test_every_document_page_shows_the_history_instead_of_last_sent(template, call):
    html = (APP / "templates" / template).read_text(encoding="utf-8")
    assert call in html
    assert "Zuletzt per E-Mail versendet" not in html
