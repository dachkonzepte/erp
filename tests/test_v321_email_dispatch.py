"""Ablage versendeter Dokumente und Versandprotokoll (1.8.17, Stufe 2, Runde 2a-3a).

Die Graph-Attrappe verhält sich wie der echte Dienst, nicht wie ein nachgiebiges MagicMock: Token
als JSON, sendMail mit 202 und leerem Körper (wer ihn als JSON lesen will, scheitert), 413 bei
einer Anfrage über 4 MiB, 404 für jeden anderen Pfad -- auch für die, die mehr als Mail.Send
bräuchten (Entwürfe, Upload-Sitzung). Seit 1.8.19 außerdem: formal ungültige Empfänger lehnt sie wie
Exchange mit 400 ErrorInvalidRecipients ab (eigene Prüfung, unabhängig vom Code unter app/),
Fehlercode und Anmeldefehler (AADSTS) sind einstellbar.
"""

import ast
import base64
import email
import io
import json
import logging
import os
import smtplib
import stat
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from email.message import Message
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app.email_dispatch as dispatch_module
import app.sent_documents as sent_documents_module
from app.email_dispatch import HEADER_NAME, STUCK_AFTER, DispatchConflict, dispatch_email, list_dispatches, new_dispatch_key
from app.email_sending import MAX_ATTACHMENT_BYTES, set_send_method, update_graph_settings, update_smtp_settings
from app.invoices import send_invoice_email
from app.models import ArchiveImmutableError, EmailDispatch, SentDocument
from app.orders import send_order_email
from app.projects import send_quote_email
from app.reminders import send_reminder_email
from app.sent_documents import ArchiveFileError, read_sent_document, store_sent_document, verify_sent_document
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.test_v174_email_sending import finalized_reminder
from tests.test_v187_quote_email import sendable_quote
from tests.test_v190_order_email import sendable_order
from tests.test_v260_role_audit import TestObjectFilteringForFieldTeilB as FieldWorld
from tests.test_v320_checklist_purposes import (  # noqa: F401 -- Fixtures
    SYSTEM_FIELDS, TEST_KEY, _client, _fill_and_complete, _start, purpose_world, testzweck, world,
)

APP = Path(__file__).resolve().parent.parent / "app"
GRAPH_REQUEST_LIMIT = 4 * 1024 * 1024
LOG_SECRET = "GEHEIM-Kunde-Mueller-Dachstr-7"


# --- Attrappen ------------------------------------------------------------------------------

class _Response:
    def __init__(self, status, body=b""):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(url, code, msg, payload):
    return urllib.error.HTTPError(url, code, msg, Message(), io.BytesIO(json.dumps(payload).encode("utf-8")))


_ATEXT = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-/=?^_`{|}~")


def graph_accepts_address(address: str) -> bool:
    """Was Exchange als SMTP-Adresse annimmt (dot-atom vor dem @, Labels ohne Bindestrich am Rand,
    Endung aus Buchstaben) -- bewusst hier eigenständig nachgebaut, nicht aus app/ übernommen."""
    if address.count("@") != 1:
        return False
    local, domain = address.split("@")
    if not local or local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    if not all(c in _ATEXT or c == "." or ord(c) > 127 for c in local):
        return False
    labels = domain.split(".")
    if len(labels) < 2:
        return False
    for label in labels:
        if not label or label.startswith("-") or label.endswith("-") or not all(c.isalnum() or c == "-" for c in label):
            return False
    return labels[-1].isalpha() and len(labels[-1]) >= 2


class FakeGraph:
    """Microsoft 365 wie der echte Dienst (so weit er ohne Mandanten nachstellbar ist)."""

    def __init__(self, fail_status=None, fail_detail="", fail_code="ErrorAccessDenied", token_error=None):
        self.urls = []
        self.messages = []
        self.request_sizes = []
        self.fail_status = fail_status
        self.fail_detail = fail_detail
        self.fail_code = fail_code
        self.token_error = token_error  # error_description der Anmeldung, z. B. "AADSTS7000215: ..."

    def __call__(self, req, timeout=None):
        url = req.full_url
        body = req.data or b""
        self.urls.append(url)
        if url.startswith("https://login.microsoftonline.com/") and url.endswith("/oauth2/v2.0/token"):
            form = urllib.parse.parse_qs(body.decode("utf-8"))
            assert form["grant_type"] == ["client_credentials"]
            assert form["scope"] == ["https://graph.microsoft.com/.default"]
            if self.token_error:
                raise _http_error(url, 401, "Unauthorized", {"error": "invalid_client", "error_description": self.token_error,
                                                             "error_codes": [7000215], "trace_id": "t"})
            return _Response(200, json.dumps({"token_type": "Bearer", "expires_in": 3599, "access_token": "TOKEN"}).encode())
        if url.startswith("https://graph.microsoft.com/v1.0/users/") and url.endswith("/sendMail"):
            assert req.get_method() == "POST"
            assert req.get_header("Authorization") == "Bearer TOKEN"
            self.request_sizes.append(len(body))
            if len(body) > GRAPH_REQUEST_LIMIT:
                raise _http_error(url, 413, "Request Entity Too Large",
                                  {"error": {"code": "RequestEntityTooLarge", "message": "Request entity too large"}})
            message = json.loads(body)["message"]
            assert message["toRecipients"], "Graph verlangt mindestens einen Empfänger"
            for recipient in message["toRecipients"] + message.get("ccRecipients", []):
                address = recipient["emailAddress"]["address"]
                assert address
                if not graph_accepts_address(address):
                    raise _http_error(url, 400, "Bad Request", {"error": {
                        "code": "ErrorInvalidRecipients",
                        "message": f"At least one recipient isn't valid., Recipient '{address}' isn't resolved. "
                                   "All recipients must be resolved before a message can be submitted."}})
            for header in message.get("internetMessageHeaders", []):
                assert header["name"].lower().startswith("x-"), "Graph nimmt nur X-Kopfzeilen an"
            for attachment in message.get("attachments", []):
                assert attachment["@odata.type"] == "#microsoft.graph.fileAttachment"
                base64.b64decode(attachment["contentBytes"], validate=True)
            if self.fail_status:
                raise _http_error(url, self.fail_status, "Error", {"error": {"code": self.fail_code, "message": self.fail_detail}})
            self.messages.append(message)
            return _Response(202, b"")  # 202 Accepted, kein Inhalt
        raise _http_error(url, 404, "Not Found", {"error": {"code": "ResourceNotFound", "message": "Unbekannter Pfad"}})


class FakeSMTP:
    """smtplib.SMTP-Ersatz: merkt sich Umschlag und Rohtext; `during_send` läuft IN sendmail()."""
    sent: list = []
    fail: Exception | None = None
    during_send = None

    def __init__(self, host, port, timeout=None):
        pass

    def starttls(self):
        pass

    def login(self, username, password):
        pass

    def sendmail(self, sender, recipients, raw):
        if FakeSMTP.during_send:
            FakeSMTP.during_send()
        if FakeSMTP.fail:
            raise FakeSMTP.fail
        FakeSMTP.sent.append({"sender": sender, "recipients": list(recipients), "message": email.message_from_string(raw)})

    def quit(self):
        pass


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    return FakeSMTP


@pytest.fixture
def graph(monkeypatch):
    fake = FakeGraph()
    monkeypatch.setattr("app.email_sending.urllib.request.urlopen", fake)
    return fake


def _configure_smtp(db):
    update_smtp_settings(db, host="smtp.example.com", port=587, username="buero@example.com", encryption="starttls",
                         sender_email="buero@example.com", sender_name="Test GmbH", password="geheim123")


def _configure_graph(db):
    set_send_method(db, "graph_oauth2")
    update_graph_settings(db, tenant_id="tenant-1", client_id="client-1", sender_mailbox="buero@firma.de", client_secret="s")


def _attachment(message):
    for part in message.walk():
        if part.get_content_disposition() == "attachment":
            return part.get_payload(decode=True)
    return None


def _dispatches(db):
    db.expire_all()
    return db.scalars(select(EmailDispatch).order_by(EmailDispatch.id)).all()


def _archive_path(doc):
    return sent_documents_module.SENT_DOCUMENT_ROOT / doc.stored_filename


def _make_writable(path):
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


# --- 1. Ablage ------------------------------------------------------------------------------

def test_sent_pdf_is_archived_exactly_as_attached(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-test-0001")

    [mail] = smtp.sent
    attached = _attachment(mail["message"])
    [row] = _dispatches(db)
    doc = row.sent_document
    assert attached.startswith(b"%PDF")
    assert _archive_path(doc).read_bytes() == attached
    assert doc.sha256 == __import__("hashlib").sha256(attached).hexdigest()
    assert (doc.document_type, doc.document_id, doc.document_number) == ("rechnung", invoice.id, invoice.invoice_number)
    assert doc.filename == f"{invoice.invoice_number}.pdf" and doc.size_bytes == len(attached)
    assert doc.created_at is not None and doc.created_by_name == "System"
    assert verify_sent_document(doc)["status"] == "unveraendert"
    assert not os.access(_archive_path(doc), os.W_OK), "abgelegte Datei muss schreibgeschützt sein"


def test_archive_never_overwrites_an_existing_file(db_session, monkeypatch):
    """Die Datei wird exklusiv angelegt: liegt unter dem Namen schon etwas, bleibt es unangetastet."""
    import hashlib
    import uuid as uuid_module

    db = db_session
    fixed = uuid_module.UUID("12345678123456781234567812345678")
    monkeypatch.setattr(sent_documents_module.uuid, "uuid4", lambda: fixed)
    content = b"%PDF-1.4 neu"
    now = datetime.utcnow()
    target = sent_documents_module.SENT_DOCUMENT_ROOT / f"{now:%Y}/{now:%m}/{fixed.hex}_{hashlib.sha256(content).hexdigest()[:16]}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"schon da")
    try:
        with pytest.raises(FileExistsError):
            store_sent_document(db, document_type="rechnung", document_id=1, document_number="R-1", filename="R-1.pdf",
                                content=content, user_id=None, user_name="Test")
        assert target.read_bytes() == b"schon da"
        assert db.scalars(select(SentDocument)).all() == []
    finally:
        target.unlink()


def test_archive_and_log_rows_cannot_be_changed_or_deleted(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-test-0002")
    [row] = _dispatches(db)
    doc = row.sent_document

    doc.sha256 = "0" * 64
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    db.delete(doc)
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    row.subject = "anderer Betreff"
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    row.status = "fehlgeschlagen"  # abgeschlossen bleibt abgeschlossen
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    db.delete(row)
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    assert [r.status for r in _dispatches(db)] == ["gesendet"]
    assert verify_sent_document(doc)["status"] == "unveraendert"


def test_archive_code_has_no_way_to_delete_or_overwrite():
    """Kein Löschen und kein Überschreiben im Ablage- und Versandcode (Datei wie Zeile)."""
    for name in ("sent_documents.py", "email_dispatch.py"):
        tree = ast.parse((APP / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"unlink", "remove", "rmtree", "rename", "replace", "write_bytes", "write_text"}:
                pytest.fail(f"{name}:{node.lineno} {node.attr}")
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "delete":
                pytest.fail(f"{name}:{node.lineno} delete()")
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
                modes = [a.value for a in node.args[1:2] if isinstance(a, ast.Constant)]
                assert modes in (["xb"], ["rb"]), f"{name}:{node.lineno} open(..., {modes})"


@pytest.fixture
def sent_invoice(threaded_db_session, monkeypatch):
    db = threaded_db_session
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="kunde@example.com", cc_email="chef@example.com",
                       dispatch_key="rechnung-test-0003")
    [row] = _dispatches(db)
    return db, invoice, row


def _office(db, router_test_client, role="buero_auftrag"):
    from app.routers.email_dispatches import router
    return router_test_client(db, router, role=role)


def test_modified_archive_file_is_detected_and_not_served(sent_invoice, router_test_client):
    db, _invoice, row = sent_invoice
    office = _office(db, router_test_client)
    doc_id = row.sent_document_id
    assert office.get(f"/api/sent-documents/{doc_id}/check").json()["check"]["status"] == "unveraendert"
    original = office.get(f"/api/sent-documents/{doc_id}/file")
    assert original.status_code == 200 and original.content.startswith(b"%PDF")

    path = _archive_path(row.sent_document)
    _make_writable(path)
    path.write_bytes(original.content.replace(b"%PDF", b"%PDX", 1))
    check = office.get(f"/api/sent-documents/{doc_id}/check").json()["check"]
    assert check["status"] == "abweichend"
    tampered = office.get(f"/api/sent-documents/{doc_id}/file")
    assert tampered.status_code == 409 and "Prüfsumme" in tampered.json()["detail"]
    with pytest.raises(ArchiveFileError):
        read_sent_document(row.sent_document)


def test_deleted_archive_file_is_detected(sent_invoice, router_test_client):
    db, _invoice, row = sent_invoice
    office = _office(db, router_test_client)
    path = _archive_path(row.sent_document)
    _make_writable(path)
    path.unlink()
    assert office.get(f"/api/sent-documents/{row.sent_document_id}/check").json()["check"]["status"] == "fehlt"
    assert office.get(f"/api/sent-documents/{row.sent_document_id}/file").status_code == 410
    assert office.get("/api/sent-documents/999999/file").status_code == 404


# --- 2./3. Versandprotokoll ----------------------------------------------------------------

def test_entry_exists_in_progress_before_sending_then_sent(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    seen = []

    def during_send():
        [row] = _dispatches(db)
        seen.append((row.status, row.sent_document_id is not None, row.finished_at))
    smtp.during_send = during_send

    send_invoice_email(db, invoice, to_email="kunde@example.com; zweite@example.com", cc_email="chef@example.com",
                       dispatch_key="rechnung-test-0004")
    assert seen == [("in_arbeit", True, None)], "Eintrag mit Ablage muss VOR dem Senden stehen"
    [row] = _dispatches(db)
    [mail] = smtp.sent
    assert row.status == "gesendet" and row.finished_at is not None
    assert (row.to_recipients, row.cc_recipients) == ("kunde@example.com, zweite@example.com", "chef@example.com")
    assert row.subject == mail["message"]["Subject"] and row.channel == "smtp"
    assert (row.document_type, row.document_id, row.document_number) == ("rechnung", invoice.id, invoice.invoice_number)
    assert mail["message"][HEADER_NAME] == row.message_ref
    assert invoice.email_sent_to == "kunde@example.com, zweite@example.com"


def test_failure_is_logged_with_class_and_code_only(db_session, graph):
    db = db_session
    _configure_graph(db)
    graph.fail_status = 403
    graph.fail_detail = f"Access is denied {LOG_SECRET}"
    invoice = make_sent_overdue_invoice(db)
    with pytest.raises(ValueError) as exc:
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-test-0005")
    assert "ERP-Zugriff" in str(exc.value)  # der Mensch bekommt den Text weiterhin
    [row] = _dispatches(db)
    assert (row.status, row.error_class, row.error_code) == ("fehlgeschlagen", "HTTPError", "403")
    assert row.finished_at is not None and row.sent_document_id is not None
    for column in EmailDispatch.__table__.columns:
        assert LOG_SECRET not in str(getattr(row, column.key)), column.key
    assert invoice.email_sent_at is None


def test_stuck_entry_is_listed_and_never_resent(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    stuck = EmailDispatch(
        dispatch_key="rechnung-haengt-0001", message_ref="00000000-0000-0000-0000-000000000001", status="in_arbeit",
        channel="smtp", document_type="rechnung", document_id=invoice.id, document_number=invoice.invoice_number,
        to_recipients="kunde@example.com", subject="Rechnung", created_at=datetime.utcnow() - STUCK_AFTER - timedelta(minutes=1),
    )
    db.add(stuck)
    db.commit()

    listing = list_dispatches(db)
    assert listing["stuck_count"] == 1 and listing["items"][0]["stuck"] is True
    assert list_dispatches(db, stuck_only=True)["items"][0]["dispatch_key"] == "rechnung-haengt-0001"
    with pytest.raises(DispatchConflict):  # derselbe Auftrag: nie ein zweites Mal
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-haengt-0001")
    assert smtp.sent == []
    assert _dispatches(db)[0].status == "in_arbeit"  # bleibt, wie er ist -- nichts wird still "repariert"

    # ein NEUER Klick ist ein neuer Auftrag; ein hängender blockiert ihn nicht, ein laufender schon
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-neu-0001")
    assert len(smtp.sent) == 1
    running = EmailDispatch(
        dispatch_key="rechnung-laeuft-0001", message_ref="00000000-0000-0000-0000-000000000002", status="in_arbeit",
        channel="smtp", document_type="rechnung", document_id=invoice.id, to_recipients="kunde@example.com",
        subject="Rechnung", created_at=datetime.utcnow(),
    )
    db.add(running)
    db.commit()
    with pytest.raises(DispatchConflict):
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-neu-0002")
    assert len(smtp.sent) == 1


# --- 4. Sperre gegen Doppelversand ---------------------------------------------------------

def test_same_key_is_never_sent_twice(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-doppelt-0001")
    first_sent_at = invoice.email_sent_at
    again = send_invoice_email(db, invoice, to_email="anderer@example.com", dispatch_key="rechnung-doppelt-0001")
    assert len(smtp.sent) == 1 and len(_dispatches(db)) == 1
    assert again.email_sent_at == first_sent_at and again.email_sent_to == "kunde@example.com"
    assert len(db.scalars(select(SentDocument)).all()) == 1


def test_same_key_twice_through_the_api(sent_invoice, router_test_client):
    from app.routers.invoices import router as invoices_router
    db, invoice, _row = sent_invoice
    client = router_test_client(db, invoices_router, role="buero_auftrag")
    body = {"to_email": "kunde@example.com", "dispatch_key": "rechnung-api-0001"}
    assert client.post(f"/api/invoices/{invoice.id}/send-email", json=body).status_code == 200
    assert client.post(f"/api/invoices/{invoice.id}/send-email", json=body).status_code == 200
    assert len(FakeSMTP.sent) == 2  # der aus der Fixture und genau einer über die API
    assert client.post(f"/api/invoices/{invoice.id}/send-email", json={"to_email": "kunde@example.com"}).status_code == 422
    assert len(FakeSMTP.sent) == 2


def test_concurrent_same_key_is_stopped_by_the_unique_key(db_session, smtp, monkeypatch):
    """Beide Anfragen sehen den Schlüssel in der Vorabprüfung als frei; erst der Unique-Schlüssel
    beim Anlegen entscheidet."""
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-race-0001")
    monkeypatch.setattr(dispatch_module, "_key_taken", lambda db, key: False)
    result = send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-race-0001")
    assert result.id == invoice.id
    assert len(smtp.sent) == 1 and len(_dispatches(db)) == 1


def test_failed_key_is_not_retried(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    smtp.fail = smtplib.SMTPRecipientsRefused({"kunde@example.com": (550, b"unbekannt")})
    with pytest.raises(ValueError):
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-fehl-0001")
    smtp.fail = None
    with pytest.raises(DispatchConflict):
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-fehl-0001")
    assert smtp.sent == []
    [row] = _dispatches(db)
    assert (row.status, row.error_class) == ("fehlgeschlagen", "SMTPRecipientsRefused")
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-fehl-0002")
    assert len(smtp.sent) == 1


# --- 5. Graph und SMTP ---------------------------------------------------------------------

def test_graph_sends_to_several_recipients_with_cc_and_header(db_session, graph):
    db = db_session
    _configure_graph(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="a@example.com, b@example.com", cc_email="c@example.com, A@example.com",
                       dispatch_key="rechnung-graph-0001")
    [message] = graph.messages
    [row] = _dispatches(db)
    assert [r["emailAddress"]["address"] for r in message["toRecipients"]] == ["a@example.com", "b@example.com"]
    assert [r["emailAddress"]["address"] for r in message["ccRecipients"]] == ["c@example.com"]  # A@ steht schon in An
    assert message["internetMessageHeaders"] == [{"name": HEADER_NAME, "value": row.message_ref}]
    assert "bccRecipients" not in message
    assert base64.b64decode(message["attachments"][0]["contentBytes"]) == _archive_path(row.sent_document).read_bytes()
    assert (row.status, row.channel) == ("gesendet", "graph_oauth2")
    # nur Token und sendMail -- nichts, was mehr als Mail.Send bräuchte (Entwurf, Upload-Sitzung)
    assert len(graph.urls) == 2 and graph.urls[1] == "https://graph.microsoft.com/v1.0/users/buero%40firma.de/sendMail"


def test_graph_code_needs_nothing_but_send_mail():
    source = (APP / "email_sending.py").read_text(encoding="utf-8")
    for forbidden in ("createUploadSession", "/messages", "/attachments", "/mailFolders"):
        assert forbidden not in source, forbidden


def test_smtp_envelope_carries_to_and_cc_but_no_bcc(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="a@example.com;b@example.com", cc_email="c@example.com",
                       dispatch_key="rechnung-smtp-0001")
    [mail] = smtp.sent
    assert mail["recipients"] == ["a@example.com", "b@example.com", "c@example.com"]
    assert mail["message"]["To"] == "a@example.com, b@example.com" and mail["message"]["Cc"] == "c@example.com"
    assert mail["message"]["Bcc"] is None


@pytest.mark.parametrize("to,cc", [("kein-at-zeichen", None), ("kunde@example.com", "x@y"), ("a@b.de\nBcc: z@z.de", None)])
def test_invalid_address_is_rejected_before_anything_is_written(db_session, smtp, to, cc):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    with pytest.raises(ValueError):
        send_invoice_email(db, invoice, to_email=to, cc_email=cc, dispatch_key="rechnung-adresse-0001")
    assert smtp.sent == [] and _dispatches(db) == [] and db.scalars(select(SentDocument)).all() == []


@pytest.mark.parametrize("channel", ["smtp", "graph"])
def test_too_large_attachment_is_rejected_before_anything_is_written(db_session, smtp, graph, channel):
    db = db_session
    _configure_smtp(db) if channel == "smtp" else _configure_graph(db)
    with pytest.raises(ValueError) as exc:
        dispatch_email(db, dispatch_key="rechnung-gross-0001", document_type="rechnung", document_id=1,
                       document_number="R-1", to="kunde@example.com", cc=None, subject="Rechnung", body_text="Text",
                       attachment_bytes=b"%PDF" + b"0" * MAX_ATTACHMENT_BYTES, attachment_filename="R-1.pdf")
    assert "höchstens 3 MB" in str(exc.value) and "nichts versendet" in str(exc.value)
    assert smtp.sent == [] and graph.urls == [] and _dispatches(db) == [] and db.scalars(select(SentDocument)).all() == []


def test_largest_allowed_attachment_fits_the_graph_request_limit(db_session, graph):
    db = db_session
    _configure_graph(db)
    result = dispatch_email(db, dispatch_key="rechnung-grenze-0001", document_type="rechnung", document_id=1,
                            document_number="R-1", to="kunde@example.com", cc="chef@example.com", subject="Rechnung R-1",
                            body_text="Sehr geehrte Damen und Herren,\n" * 40,
                            attachment_bytes=b"%PDF" + b"1" * (MAX_ATTACHMENT_BYTES - 4), attachment_filename="R-1.pdf")
    assert result.dispatch.status == "gesendet"
    assert graph.request_sizes[0] <= GRAPH_REQUEST_LIMIT


def test_graph_rejects_too_large_request_like_the_real_service(db_session, graph, monkeypatch):
    """Ohne die eigene Größenprüfung antwortet die Attrappe wie Graph mit 413 -- der Eintrag wird
    fehlgeschlagen, mit Klasse und Code."""
    import app.email_sending as email_sending_module
    db = db_session
    _configure_graph(db)
    monkeypatch.setattr(email_sending_module, "MAX_ATTACHMENT_BYTES", 10 * 1024 * 1024)
    with pytest.raises(ValueError):
        dispatch_email(db, dispatch_key="rechnung-413-0001", document_type="rechnung", document_id=1,
                       document_number="R-1", to="kunde@example.com", cc=None, subject="Rechnung", body_text="Text",
                       attachment_bytes=b"%PDF" + b"2" * 3_500_000, attachment_filename="R-1.pdf")
    [row] = _dispatches(db)
    assert (row.status, row.error_class, row.error_code) == ("fehlgeschlagen", "HTTPError", "413")
    assert graph.messages == []


# --- 6. Alle Versender ---------------------------------------------------------------------

def _quote(db):
    quote = sendable_quote(db, customer_email="kunde@example.com")
    return quote, send_quote_email, "angebot", quote.quote_number


def _order(db):
    order = sendable_order(db, customer_email="kunde@example.com")
    return order, send_order_email, "auftrag", order.order_number


def _invoice(db):
    invoice = make_sent_overdue_invoice(db)
    invoice.order.project.customer.email = "kunde@example.com"
    db.commit()
    return invoice, send_invoice_email, "rechnung", invoice.invoice_number


def _reminder(db):
    reminder = finalized_reminder(db, customer_email="kunde@example.com")
    return reminder, send_reminder_email, "mahnung", reminder.reminder_number


@pytest.mark.parametrize("make", [_quote, _order, _invoice, _reminder], ids=["angebot", "auftrag", "rechnung", "mahnung"])
def test_every_document_sender_logs_and_archives(db_session, smtp, make):
    from app.models import AppUser
    db = db_session
    _configure_smtp(db)
    user = AppUser(username="anna", display_name="Anna Büro", role="buero_auftrag", active=True, password_hash="x")
    db.add(user)
    db.commit()
    document, send, document_type, number = make(db)
    send(db, document, cc_email="chef@example.com", dispatch_key=f"{document_type}-sender-0001", user=user)
    [mail] = smtp.sent
    [row] = _dispatches(db)
    assert (row.document_type, row.document_id, row.document_number) == (document_type, document.id, number)
    assert (row.to_recipients, row.cc_recipients, row.status) == ("kunde@example.com", "chef@example.com", "gesendet")
    assert (row.created_by_user_id, row.created_by_name) == (user.id, "Anna Büro")
    assert row.sent_document.created_by_name == "Anna Büro"
    assert _archive_path(row.sent_document).read_bytes() == _attachment(mail["message"])
    assert document.email_sent_to == "kunde@example.com"


def test_task_mail_is_logged_without_attachment_and_only_admin_sees_it(db_session, smtp):
    from app.models import Employee, EmployeeProfile
    from app.tasks import create_task
    db = db_session
    _configure_smtp(db)
    emp = Employee(employee_number="M-1", first_name="Max", last_name="Muster", employee_group="angestellt",
                   hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp)
    db.flush()
    db.add(EmployeeProfile(employee_id=emp.id, email="max@example.com"))
    db.commit()
    task = create_task(db, title="Dachrinne prüfen", assigned_employee_id=emp.id)
    [row] = _dispatches(db)
    assert (row.document_type, row.document_id, row.status) == ("aufgabe", task["id"], "gesendet")
    assert row.sent_document_id is None and row.subject == "Neue Aufgabe: Dachrinne prüfen"
    assert list_dispatches(db)["items"] == []
    assert [d["id"] for d in list_dispatches(db, include_task_mails=True)["items"]] == [row.id]


def test_task_mails_in_the_api_only_for_admin(router_test_client, threaded_db_session, monkeypatch):
    from app.models import Employee, EmployeeProfile
    from app.tasks import create_task
    db = threaded_db_session
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    emp = Employee(employee_number="M-3", first_name="Ole", last_name="Muster", employee_group="angestellt",
                   hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp)
    db.flush()
    db.add(EmployeeProfile(employee_id=emp.id, email="ole@example.com"))
    db.commit()
    create_task(db, title="Vertraulich: Lohngespräch", assigned_employee_id=emp.id)
    for role in ("buero_auftrag", "buero_finanzen"):
        body = _office(db, router_test_client, role=role).get("/api/email-dispatches").json()
        assert body["items"] == [], role
        assert _office(db, router_test_client, role=role).get("/api/email-dispatches?document_type=aufgabe").json()["items"] == []
    [item] = _office(db, router_test_client, role="admin").get("/api/email-dispatches").json()["items"]
    assert item["subject"] == "Neue Aufgabe: Vertraulich: Lohngespräch"


def test_task_mail_failure_is_logged_and_task_still_saved(db_session, smtp):
    from app.models import Employee, EmployeeProfile, Task
    from app.tasks import create_task
    db = db_session
    _configure_smtp(db)
    smtp.fail = smtplib.SMTPServerDisconnected("weg")
    emp = Employee(employee_number="M-2", first_name="Mia", last_name="Muster", employee_group="angestellt",
                   hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp)
    db.flush()
    db.add(EmployeeProfile(employee_id=emp.id, email="mia@example.com"))
    db.commit()
    task = create_task(db, title="Ortstermin", assigned_employee_id=emp.id)
    assert db.get(Task, task["id"]) is not None
    [row] = _dispatches(db)
    assert (row.status, row.error_class) == ("fehlgeschlagen", "SMTPServerDisconnected")


def _calls_outside(allowed: set[str]) -> list[str]:
    """Jeder Aufruf des Transports außerhalb der erlaubten Module (Dateiname:Zeile)."""
    transport = {"send_message", "_send_via_smtp", "_send_via_graph", "sendmail", "send_message_raw"}
    hits = []
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(APP).as_posix()
        if rel in allowed:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in transport:
                    hits.append(f"{rel}:{node.lineno}")
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("email_sending"):
                for alias in node.names:
                    if alias.name in transport:
                        hits.append(f"{rel}:{node.lineno} import {alias.name}")
    return hits


def test_no_mail_leaves_the_system_past_the_dispatch_log():
    assert _calls_outside({"email_sending.py", "email_dispatch.py"}) == []


# --- 8. Rechte: Monteur ---------------------------------------------------------------------

def test_field_cannot_read_the_log_or_the_archive(sent_invoice, router_test_client):
    from app.routers.pages import router as pages_router
    db, _invoice, row = sent_invoice
    field = _office(db, router_test_client, role="field")
    for path in ("/api/email-dispatches", "/api/email-dispatches?stuck=true",
                 f"/api/sent-documents/{row.sent_document_id}/check", f"/api/sent-documents/{row.sent_document_id}/file"):
        assert field.get(path).status_code == 403, path
    assert router_test_client(db, pages_router, role="field").get("/versandprotokoll").status_code == 403
    for role in ("buero_auftrag", "buero_finanzen", "admin"):
        office = _office(db, router_test_client, role=role)
        assert office.get("/api/email-dispatches").json()["items"][0]["id"] == row.id, role
        assert office.get(f"/api/sent-documents/{row.sent_document_id}/file").status_code == 200, role
        assert router_test_client(db, pages_router, role=role).get("/versandprotokoll").status_code == 200, role


OFFICE_DISPATCH_KEYS = {
    "dispatch_key", "message_ref", "to_recipients", "cc_recipients", "sent_document", "sent_document_id", "sha256",
    "stored_filename", "email_sent_to", "email_sent_at", "recipient_email", "error_class", "channel",
}


def _scan(value, keys, texts):
    if isinstance(value, dict):
        for key, inner in value.items():
            keys.add(key)
            _scan(inner, keys, texts)
    elif isinstance(value, list):
        for inner in value:
            _scan(inner, keys, texts)
    elif isinstance(value, str):
        texts.append(value)
    return keys, texts


def test_field_responses_carry_nothing_from_the_dispatch(router_test_client, threaded_db_session, monkeypatch, feste_uhr):
    # feste_uhr (seit 1.8.36): /api/field-view/today meldet ab 19 Uhr ab -- sonst abends rot.
    from app.routers.field_view import router as field_view_router
    from app.routers.orders import router as orders_router
    from app.routers.service_reports import router as reports_router
    db = threaded_db_session
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    monteur = FieldWorld._employee(db, "T-V1", "Max", "Monteur")
    order, _customer, _prop = FieldWorld._order(db, "AUF-V-0001", "P-V-0001")
    FieldWorld._assign_individually(db, order, monteur)
    send_order_email(db, order, to_email="geheim.kunde@example.com", cc_email="geheim.chef@example.com",
                     dispatch_key="auftrag-scan-0001")
    [row] = _dispatches(db)
    secrets = {"geheim.kunde@example.com", "geheim.chef@example.com", row.message_ref, row.dispatch_key, row.subject,
               row.sent_document.sha256}

    field = router_test_client(db, orders_router, field_view_router, reports_router, role="field", employee_id=monteur.id)
    keys, texts = set(), []
    for path in (f"/api/orders/{order.id}", "/api/field-view/today", "/api/field-view/upcoming",
                 "/api/field-view/time-tracking/orders", f"/api/orders/{order.id}/service-reports",
                 f"/api/orders/{order.id}/property"):
        response = field.get(path)
        assert response.status_code == 200, (path, response.text)
        _scan(response.json(), keys, texts)
    assert not keys & OFFICE_DISPATCH_KEYS, keys & OFFICE_DISPATCH_KEYS
    assert not [t for t in texts if any(s in t for s in secrets)]
    assert order.order_number in texts  # die Abfrage hat den Auftrag tatsächlich geliefert


# --- 7. Regel 18: Protokoll der Regeln und Folgen ------------------------------------------

def _assert_only_class_name(caplog, class_name):
    records = [r for r in caplog.records if r.name.startswith("app.checklist")]
    assert records, "kein Protokolleintrag"
    formatter = logging.Formatter("%(message)s")
    for record in records:
        text = formatter.format(record)
        assert LOG_SECRET not in text, text
        assert record.exc_info is None and record.exc_text is None
        assert class_name in text


def test_rule_failure_is_logged_with_class_name_only(db_session, monkeypatch, caplog):
    import app.checklist_rules as rules

    def fail(db, checklist_id):
        raise IntegrityError("INSERT INTO tasks (title, description) VALUES (?, ?)", (LOG_SECRET, "Auftrag A-1"),
                             Exception("UNIQUE constraint failed"))
    monkeypatch.setattr(rules, "run_checklist_rules", fail)
    with caplog.at_level(logging.DEBUG):
        rules.run_rules_after_completion(db_session, 42)
    _assert_only_class_name(caplog, "IntegrityError")


def test_follow_up_failures_are_logged_with_class_name_only(purpose_world, router_test_client, monkeypatch, caplog):
    import app.checklist_follow_ups as follow_ups
    from app.checklist_purposes import PURPOSES, ChecklistPurpose, FollowUp

    def handler(db, checklist):
        raise RuntimeError(f"{LOG_SECRET} Auftrag {checklist.context_label_snapshot}")
    monkeypatch.setitem(PURPOSES, TEST_KEY, ChecklistPurpose(
        TEST_KEY, "Testzweck", ("auftrag",), SYSTEM_FIELDS, (FollowUp("testzweck.folge", "Testfolge", handler),),
    ))
    field = _client(purpose_world, router_test_client, "a")
    with caplog.at_level(logging.DEBUG):
        _fill_and_complete(field, _start(purpose_world, field))
    _assert_only_class_name(caplog, "RuntimeError")

    caplog.clear()

    def outer(db, checklist_id):
        raise RuntimeError(LOG_SECRET)
    monkeypatch.setattr(follow_ups, "run_checklist_follow_ups", outer)
    with caplog.at_level(logging.DEBUG):
        follow_ups.run_follow_ups_after_completion(purpose_world["db"], 1)
    _assert_only_class_name(caplog, "RuntimeError")
