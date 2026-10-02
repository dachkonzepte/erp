"""Versand fertigstellen, Teil 1 (1.8.19, Stufe 2, Runde 2a-3b, Punkte 1-4).

1. Sperre "läuft gerade" in der Datenbank: zwei Tabs, die dasselbe Dokument in derselben Sekunde
   senden, bestehen beide die Vorabprüfung -- genau einer sendet (SQLite mit zwei Verbindungen
   genau im Fenster zwischen Prüfen und Schreiben, PostgreSQL mit zwei echten Threads, opt-in).
2. Jede Adresse wird vor dem Senden geprüft; was Exchange ablehnen würde, erreicht die
   Graph-Attrappe nicht. Graph-/Anmelde-/SMTP-Fehler als deutsche Meldung.
3. Hängengebliebene Einträge klärt das Büro mit Notiz; steht am Eintrag und in der Historie.
4. Rechnung, Storno, Mahnung: ab dem ersten Versand kommen Nachdruck, Download und erneuter
   Versand aus der Ablage -- byte-gleich, auch nach geändertem Briefkopf.
"""

import os
import smtplib
import stat
import threading
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import app.email_dispatch as dispatch_module
from app.database import Base
from app.email_dispatch import (
    RUNNING_TEXT, STUCK_AFTER, DispatchConflict, dispatch_email, parse_recipients, resolve_stuck_dispatch,
)
from app.invoice_pdf import build_invoice_pdf
from app.invoices import create_storno_draft, finalize_and_send_invoice, send_invoice_email
from app.models import AuditLog, EmailDispatch, Invoice, SentDocument
from app.reminder_pdf import build_reminder_pdf
from app.reminders import send_reminder_email
from app.sent_documents import frozen_version
from app.settings import load_general_settings
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.test_v174_email_sending import finalized_reminder
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v321_email_dispatch import (  # noqa: F401 -- Fixtures
    LOG_SECRET, FakeSMTP, _archive_path, _attachment, _configure_graph, _configure_smtp, _dispatches, graph, smtp,
)

OLD_LETTERHEAD = "Dachkonzepte Alt GmbH"
NEW_LETTERHEAD = "Neuer Briefkopf GmbH"
PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture
def file_db(tmp_path):
    """SQLite als Datei: zwei Sessions = zwei echte Verbindungen (zwei Tabs, zwei Anfragen)."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'versand.db').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()


def _stuck_entry(db, document_type, document_id, *, key, minutes_ago=None, lock=True, number=None):
    created = datetime.utcnow() - (timedelta(minutes=minutes_ago) if minutes_ago is not None else STUCK_AFTER + timedelta(minutes=1))
    row = EmailDispatch(
        dispatch_key=key, message_ref=str(uuid.uuid4()), status="in_arbeit", channel="smtp",
        document_type=document_type, document_id=document_id, document_number=number,
        to_recipients="kunde@example.com", subject="Rechnung", created_at=created,
        lock_key=f"{document_type}:{document_id}" if lock else None,
    )
    db.add(row)
    db.commit()
    return row


def _set_letterhead(db, name):
    general = load_general_settings(db)
    general.company_name = name
    db.commit()


# --- 1. Sperre "läuft gerade" ---------------------------------------------------------------

def test_two_tabs_in_the_same_second_only_one_sends(file_db, smtp, monkeypatch):
    """Beide Tabs haben die Vorabprüfung hinter sich, bevor einer schreibt (so sieht "dieselbe
    Sekunde" aus); Tab B klickt, während Tab A sendet -- eigene Verbindung, eigener Schlüssel."""
    tab_a, tab_b = file_db(), file_db()
    _configure_smtp(tab_a)
    invoice = make_sent_overdue_invoice(tab_a)
    invoice_in_b = tab_b.get(Invoice, invoice.id)
    monkeypatch.setattr(dispatch_module, "_running_dispatch", lambda db, document_type, document_id: None)
    outcome_b = []

    def tab_b_clicks():
        smtp.during_send = None
        try:
            send_invoice_email(tab_b, invoice_in_b, to_email="kunde@example.com", dispatch_key="rechnung-tab-b-0001")
            outcome_b.append("gesendet")
        except DispatchConflict as e:
            outcome_b.append(str(e))
    smtp.during_send = tab_b_clicks

    send_invoice_email(tab_a, invoice, to_email="kunde@example.com", dispatch_key="rechnung-tab-a-0001")
    assert outcome_b == [RUNNING_TEXT]
    assert len(smtp.sent) == 1
    [row] = _dispatches(tab_a)
    assert (row.dispatch_key, row.status, row.lock_key) == ("rechnung-tab-a-0001", "gesendet", None)
    for s in (tab_a, tab_b):
        s.close()


def test_the_database_holds_at_most_one_running_dispatch_per_document(db_session):
    db = db_session
    _stuck_entry(db, "rechnung", 7, key="rechnung-sperre-0001", minutes_ago=0)
    db.add(EmailDispatch(dispatch_key="rechnung-sperre-0002", message_ref=str(uuid.uuid4()), status="in_arbeit",
                         channel="smtp", document_type="rechnung", document_id=7, to_recipients="a@example.com",
                         subject="R", created_at=datetime.utcnow(), lock_key="rechnung:7"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_lock_is_released_after_success_and_failure(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-frei-0001")
    smtp.fail = smtplib.SMTPServerDisconnected("weg")
    with pytest.raises(ValueError):
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-frei-0002")
    smtp.fail = None
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-frei-0003")
    assert [(r.status, r.lock_key) for r in _dispatches(db)] == [("gesendet", None), ("fehlgeschlagen", None), ("gesendet", None)]


def test_stuck_entry_does_not_keep_its_lock(db_session, smtp):
    """Wie seit 1.8.17: ein hängender Versand blockiert einen neuen nicht -- er gibt seine Sperre
    ab, bleibt aber "in Arbeit" und damit im Protokoll als hängend sichtbar."""
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    stuck = _stuck_entry(db, "rechnung", invoice.id, key="rechnung-haengt-0009")
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-neu-0009")
    assert len(smtp.sent) == 1
    db.expire_all()
    assert (stuck.status, stuck.lock_key) == ("in_arbeit", None)


def test_task_mails_take_no_document_lock(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    for n in (1, 2):
        dispatch_email(db, dispatch_key=f"aufgabe-sperre-000{n}", document_type="aufgabe", document_id=5,
                       document_number=None, to="max@example.com", cc=None, subject="Neue Aufgabe", body_text="x",
                       block_parallel=False)
    assert [r.lock_key for r in _dispatches(db)] == [None, None] and len(smtp.sent) == 2


@pytest.mark.skipif(not PG_TEST_DATABASE_URL, reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
def test_two_simultaneous_dispatches_on_postgresql_exactly_one_sends(monkeypatch):
    """Zwei echte Threads, zwei Verbindungen; beide warten nach der Vorabprüfung aufeinander, so
    dass keiner den anderen dort sehen kann -- die Datenbank entscheidet (Wegwerf-Schema, Regel 16)."""
    schema = f"pgtest_versand_{uuid.uuid4().hex[:8]}"
    admin_engine = create_engine(PG_TEST_DATABASE_URL)
    with admin_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        _configure_smtp(setup)
        setup.close()
        FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
        monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
        barrier = threading.Barrier(2)
        original = dispatch_module._running_dispatch

        def check_then_wait(db, document_type, document_id):
            found = original(db, document_type, document_id)
            barrier.wait(timeout=15)
            return found
        monkeypatch.setattr(dispatch_module, "_running_dispatch", check_then_wait)
        results = {}

        def tab(name):
            session = Session()
            try:
                result = dispatch_email(
                    session, dispatch_key=f"rechnung-pg-{name}-0001", document_type="rechnung", document_id=4711,
                    document_number="R-4711", to="kunde@example.com", cc=None, subject="Rechnung R-4711",
                    body_text="Text", attachment_bytes=b"%PDF-1.4 " + name.encode(), attachment_filename="R-4711.pdf",
                )
                results[name] = result.dispatch.status
            except DispatchConflict as e:
                results[name] = str(e)
            finally:
                session.close()

        threads = [threading.Thread(target=tab, args=(name,)) for name in ("A", "B")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert sorted(results.values()) == sorted(["gesendet", RUNNING_TEXT]), results
        assert len(FakeSMTP.sent) == 1
        check = Session()
        [row] = check.scalars(select(EmailDispatch)).all()
        assert (row.status, row.lock_key) == ("gesendet", None)
        assert len(check.scalars(select(SentDocument)).all()) == 1
        check.close()
    finally:
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin_engine.dispose()


# --- 2. Adressen und Fehlermeldungen --------------------------------------------------------

# Alle hätte die Prüfung bis 1.8.18 durchgelassen; Exchange lehnt sie ab.
EXCHANGE_REJECTS = ["kunde@firma..de", "kunde.@firma.de", ".kunde@firma.de", "ku..nde@firma.de", "kunde@firma.de.",
                    "kunde@-firma.de", "kunde@firma.d", "kun(de)@firma.de", "kunde@firma.123"]


@pytest.mark.parametrize("address", EXCHANGE_REJECTS)
def test_invalid_address_never_reaches_graph(db_session, graph, address):
    from tests.test_v321_email_dispatch import graph_accepts_address
    assert not graph_accepts_address(address)  # die Attrappe würde ablehnen wie Exchange
    db = db_session
    _configure_graph(db)
    invoice = make_sent_overdue_invoice(db)
    with pytest.raises(ValueError) as exc:
        send_invoice_email(db, invoice, to_email=f"ok@example.com; {address}", dispatch_key="rechnung-adr-0001")
    assert f"„{address}“ ist keine gültige E-Mail-Adresse – " in str(exc.value)
    assert graph.urls == [], "die Adresse hat Microsoft 365 erreicht"
    assert _dispatches(db) == [] and db.scalars(select(SentDocument)).all() == []


def test_valid_addresses_pass_both_our_check_and_the_graph_fake(db_session, graph):
    db = db_session
    _configure_graph(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="Max Muster <max.muster@firma.de>; info@müller-dach.de\nbuchhaltung+rechnung@sub.firma.co.uk",
                       cc_email="o'brien@example.ie", dispatch_key="rechnung-adr-0002")
    [message] = graph.messages
    assert [r["emailAddress"]["address"] for r in message["toRecipients"]] == [
        "max.muster@firma.de", "info@müller-dach.de", "buchhaltung+rechnung@sub.firma.co.uk"]
    assert [r["emailAddress"]["address"] for r in message["ccRecipients"]] == ["o'brien@example.ie"]


@pytest.mark.parametrize("text,reason", [
    ("kunde firma.de", "Leerzeichen"), ("kunde.firma.de", "es fehlt das @"), ("a@b.de@c.de", "mehr als ein @"),
    ("kunde@firma", "fehlt die Endung"), ("kunde@firma.d", "„.d“ gibt es nicht"), ("kunde@firma..de", "zwei Punkte"),
])
def test_invalid_address_names_the_reason(text, reason):
    with pytest.raises(ValueError) as exc:
        parse_recipients(text, label="Empfänger")
    assert reason in str(exc.value) and str(exc.value).startswith("Empfänger: „")


@pytest.mark.parametrize("status,code,expected", [
    (400, "ErrorInvalidRecipients", "Empfängeradresse als ungültig abgelehnt"),
    (403, "ErrorAccessDenied", "ERP-Zugriff"),
    (404, "ErrorInvalidUser", "Absender-Postfach gibt es in Microsoft 365 nicht"),
    (429, "ApplicationThrottled", "bremst gerade"),
    (503, "ServiceUnavailable", "gestört"),
    (400, "ErrorQuotaExceeded", "Postfach ist voll"),
    (400, "ErrorUnbekannt", "Meldung von Microsoft: " + LOG_SECRET),
])
def test_graph_error_codes_become_german_messages(db_session, graph, status, code, expected):
    db = db_session
    _configure_graph(db)
    graph.fail_status, graph.fail_code, graph.fail_detail = status, code, LOG_SECRET
    invoice = make_sent_overdue_invoice(db)
    with pytest.raises(ValueError) as exc:
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-code-0001")
    message = str(exc.value)
    assert expected in message and f"{code}, HTTP {status}" in message
    assert '{"error"' not in message, "keine rohe JSON-Antwort mehr"
    if code == "ErrorInvalidRecipients":
        assert "Absender" not in message  # bis 1.8.18 hieß es fälschlich "Absender-Postfach existiert nicht"
    [row] = _dispatches(db)
    assert (row.status, row.error_class, row.error_code) == ("fehlgeschlagen", "HTTPError", str(status))
    for column in EmailDispatch.__table__.columns:  # Regel 18: nur Klasse und Code im Protokoll
        assert LOG_SECRET not in str(getattr(row, column.key)), column.key


@pytest.mark.parametrize("description,expected", [
    ("AADSTS7000215: Invalid client secret provided. Ensure the secret being sent in the request is the client "
     "secret value, not the client secret ID.\r\nTrace ID: 1\r\nCorrelation ID: 2", "Client-Secret ist falsch"),
    ("AADSTS7000222: The provided client secret keys for app '1' are expired.\r\nTrace ID: 1", "abgelaufen"),
    ("AADSTS90002: Tenant 'tenant-1' not found.\r\nTrace ID: 1", "Mandanten-ID ist unbekannt"),
    ("AADSTS12345: Something new.\r\nTrace ID: 1", "AADSTS12345: Something new. (invalid_client)"),
])
def test_token_errors_become_german_messages(db_session, graph, description, expected):
    db = db_session
    _configure_graph(db)
    graph.token_error = description
    invoice = make_sent_overdue_invoice(db)
    with pytest.raises(ValueError) as exc:
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-token-0001")
    assert str(exc.value).startswith("Anmeldung bei Microsoft 365 fehlgeschlagen: ") and expected in str(exc.value)
    assert "Trace ID" not in str(exc.value)
    assert graph.messages == []


def test_smtp_refused_recipients_get_a_clear_message(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    smtp.fail = smtplib.SMTPRecipientsRefused({"kunde@example.com": (550, b"5.1.1 unknown user")})
    invoice = make_sent_overdue_invoice(db)
    with pytest.raises(ValueError) as exc:
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-smtp-0009")
    assert "Der Mailserver hat die Empfänger abgelehnt: kunde@example.com (550)" in str(exc.value)
    assert _dispatches(db)[0].error_class == "SMTPRecipientsRefused"


# --- 3. Hängengebliebene Einträge klären ----------------------------------------------------

def _office(db, router_test_client, role="buero_auftrag"):
    from app.routers.email_dispatches import router
    return router_test_client(db, router, role=role)


@pytest.fixture
def stuck_invoice(threaded_db_session, monkeypatch):
    db = threaded_db_session
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    row = _stuck_entry(db, "rechnung", invoice.id, key="rechnung-haengt-0100", number=invoice.invoice_number)
    return db, invoice, row


@pytest.mark.parametrize("outcome", ["gesendet", "fehlgeschlagen"])
def test_office_resolves_stuck_entry_with_note_and_history(stuck_invoice, router_test_client, outcome):
    db, invoice, row = stuck_invoice
    response = _office(db, router_test_client).post(
        f"/api/email-dispatches/{row.id}/resolve", json={"outcome": outcome, "note": "  In Gesendete Elemente geprüft, 14:02  "})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["resolved"], body["stuck"]) == (outcome, True, False)
    assert (body["resolved_by_name"], body["resolution_note"]) == ("Buero_auftrag", "In Gesendete Elemente geprüft, 14:02")
    db.expire_all()
    assert (row.status, row.lock_key, row.finished_at) == (outcome, None, None)
    [audit] = db.scalars(select(AuditLog).where(AuditLog.entity_type == "Versand")).all()
    assert (audit.entity_id, audit.actor_name, audit.project_id) == (str(row.id), "Buero_auftrag", invoice.order.project_id)
    assert audit.new_value.endswith("Notiz: In Gesendete Elemente geprüft, 14:02") and audit.old_value.startswith("Hängengeblieben")
    assert row.message_ref in audit.entity_label and "kunde@example.com" not in audit.entity_label
    assert FakeSMTP.sent == [], "beim Klären wird nichts gesendet"


def test_resolution_is_refused_where_it_does_not_belong(stuck_invoice, router_test_client):
    db, invoice, row = stuck_invoice
    office = _office(db, router_test_client)
    url = f"/api/email-dispatches/{row.id}/resolve"
    assert office.post(url, json={"outcome": "gesendet", "note": "   "}).status_code == 400
    assert office.post(url, json={"outcome": "gesendet"}).status_code == 422
    assert office.post(url, json={"outcome": "vielleicht", "note": "x"}).status_code == 422
    assert office.post("/api/email-dispatches/999999/resolve", json={"outcome": "gesendet", "note": "geprüft"}).status_code == 404
    assert _office(db, router_test_client, role="field").post(url, json={"outcome": "gesendet", "note": "geprüft"}).status_code == 403
    fresh = _stuck_entry(db, "rechnung", invoice.id + 1000, key="rechnung-laeuft-0100", minutes_ago=2)
    running = office.post(f"/api/email-dispatches/{fresh.id}/resolve", json={"outcome": "gesendet", "note": "geprüft"})
    assert running.status_code == 409 and "läuft womöglich noch" in running.json()["detail"]
    assert office.post(url, json={"outcome": "fehlgeschlagen", "note": "nicht gefunden"}).status_code == 200
    again = office.post(url, json={"outcome": "gesendet", "note": "doch gefunden"})
    assert again.status_code == 409 and "bereits abgeschlossen" in again.json()["detail"]
    db.expire_all()
    assert (row.status, row.resolution_note) == ("fehlgeschlagen", "nicht gefunden")
    assert fresh.status == "in_arbeit"


def test_two_simultaneous_resolutions_exactly_one_wins(file_db):
    """Beide Büros haben den Eintrag als hängend geladen; der Spätere darf den Ersten nicht still
    überschreiben (bedingtes UPDATE)."""
    office_a, office_b = file_db(), file_db()
    row = _stuck_entry(office_a, "rechnung", 3, key="rechnung-haengt-0200")
    # B hält den Eintrag in seiner Session (Referenz nötig, sonst lädt get() später frisch) und sieht
    # ihn damit noch "in Arbeit", wenn A schon geklärt hat -- genau das Fenster zwischen Prüfen und Schreiben.
    seen_by_b = office_b.get(EmailDispatch, row.id)
    vorher = len(office_a.scalars(select(AuditLog)).all())  # seit 1.8.42 mit den Einträgen der Grunddaten
    resolve_stuck_dispatch(office_a, row.id, outcome="gesendet", note="gefunden", user_id=1, user_name="Anna")
    assert seen_by_b.status == "in_arbeit"
    with pytest.raises(DispatchConflict):
        resolve_stuck_dispatch(office_b, row.id, outcome="fehlgeschlagen", note="nicht gefunden", user_id=2, user_name="Ben")
    check = file_db()
    stored = check.get(EmailDispatch, row.id)
    assert (stored.status, stored.resolved_by_name, stored.resolution_note) == ("gesendet", "Anna", "gefunden")
    assert len(check.scalars(select(AuditLog)).all()) == vorher + 1
    for s in (office_a, office_b, check):
        s.close()


def test_task_mail_can_only_be_resolved_by_admin(threaded_db_session, router_test_client):
    db = threaded_db_session
    row = _stuck_entry(db, "aufgabe", 42, key="aufgabe-haengt-0001", lock=False)
    vorher = set(db.scalars(select(AuditLog.id)).all())  # seit 1.8.42 mit den Einträgen der Grunddaten
    url = f"/api/email-dispatches/{row.id}/resolve"
    for role in ("buero_auftrag", "buero_finanzen"):
        assert _office(db, router_test_client, role=role).post(url, json={"outcome": "gesendet", "note": "geprüft"}).status_code == 404
    assert _office(db, router_test_client, role="admin").post(url, json={"outcome": "gesendet", "note": "geprüft"}).status_code == 200
    [audit] = [a for a in db.scalars(select(AuditLog)).all() if a.id not in vorher]
    assert (audit.entity_type, audit.entity_id) == ("Aufgabe", "42")  # nur Admin sieht Aufgaben in der Historie


def test_resolved_entry_stays_unchangeable(stuck_invoice):
    from app.models import ArchiveImmutableError
    db, _invoice, row = stuck_invoice
    resolve_stuck_dispatch(db, row.id, outcome="gesendet", note="gefunden", user_id=None, user_name="Anna")
    row.resolution_note = "nachträglich anders"
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()


# --- 4. Nachdruck, Download und erneuter Versand aus der Ablage -----------------------------

@pytest.fixture
def office_world(threaded_db_session, monkeypatch):
    db = threaded_db_session
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    _configure_smtp(db)
    _set_letterhead(db, OLD_LETTERHEAD)
    return db


def _client(db, router_test_client):
    from app.routers.invoices import router as invoices_router
    from app.routers.reminders import router as reminders_router
    return router_test_client(db, invoices_router, reminders_router, role="buero_auftrag")


def _assert_reprint_is_the_archive(db, client, url, sent_bytes, rebuild):
    """Nach geändertem Briefkopf: der Abruf liefert genau die versendeten Bytes; neu erzeugt sähe
    das Dokument anders aus (Gegenprobe im Test selbst)."""
    _set_letterhead(db, NEW_LETTERHEAD)
    reprint = client.get(url)
    assert reprint.status_code == 200 and reprint.headers.get("X-DK-Ablage")
    assert reprint.content == sent_bytes
    assert OLD_LETTERHEAD.encode() in _extract_pdf_text(reprint.content)
    fresh = _extract_pdf_text(rebuild())
    assert NEW_LETTERHEAD.encode() in fresh and OLD_LETTERHEAD.encode() not in fresh


def test_reprint_of_a_sent_invoice_is_byte_identical_after_letterhead_change(office_world, router_test_client):
    db = office_world
    client = _client(db, router_test_client)
    invoice = make_sent_overdue_invoice(db)
    before = client.get(f"/api/invoices/{invoice.id}/pdf")
    assert before.status_code == 200 and "X-DK-Ablage" not in before.headers  # noch nie versendet: neu erzeugt
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-druck-0001")
    sent_bytes = _attachment(FakeSMTP.sent[0]["message"])
    [first] = _dispatches(db)
    assert _archive_path(first.sent_document).read_bytes() == sent_bytes
    _assert_reprint_is_the_archive(db, client, f"/api/invoices/{invoice.id}/pdf", sent_bytes,
                                   lambda: build_invoice_pdf(db, invoice))

    # erneuter Versand: dieselben Bytes, kein zweiter Ablage-Eintrag
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-druck-0002")
    assert _attachment(FakeSMTP.sent[1]["message"]) == sent_bytes
    first, second = _dispatches(db)
    assert second.sent_document_id == first.sent_document_id
    assert len(db.scalars(select(SentDocument)).all()) == 1


def test_reprint_of_a_sent_cancellation_is_byte_identical(office_world, router_test_client):
    db = office_world
    client = _client(db, router_test_client)
    original = make_sent_overdue_invoice(db)
    send_invoice_email(db, original, to_email="kunde@example.com", dispatch_key="rechnung-orig-0001")
    original_bytes = _attachment(FakeSMTP.sent[0]["message"])
    storno = finalize_and_send_invoice(db, create_storno_draft(db, original))
    assert storno.invoice_type == "storno"
    send_invoice_email(db, storno, to_email="kunde@example.com", dispatch_key="rechnung-storno-0001")
    storno_bytes = _attachment(FakeSMTP.sent[1]["message"])
    _assert_reprint_is_the_archive(db, client, f"/api/invoices/{storno.id}/pdf", storno_bytes,
                                   lambda: build_invoice_pdf(db, storno))
    assert client.get(f"/api/invoices/{original.id}/pdf").content == original_bytes  # die stornierte auch


def test_reprint_of_a_sent_reminder_is_byte_identical(office_world, router_test_client):
    db = office_world
    client = _client(db, router_test_client)
    reminder = finalized_reminder(db, customer_email="kunde@example.com")
    send_reminder_email(db, reminder, dispatch_key="mahnung-druck-0001")
    sent_bytes = _attachment(FakeSMTP.sent[0]["message"])
    _assert_reprint_is_the_archive(db, client, f"/api/reminders/{reminder.id}/pdf", sent_bytes,
                                   lambda: build_reminder_pdf(db, reminder))
    send_reminder_email(db, reminder, dispatch_key="mahnung-druck-0002")
    assert _attachment(FakeSMTP.sent[1]["message"]) == sent_bytes
    assert len(db.scalars(select(SentDocument)).all()) == 1


def test_failed_first_dispatch_does_not_freeze_the_document(db_session, graph):
    db = db_session
    _configure_graph(db)
    invoice = make_sent_overdue_invoice(db)
    graph.fail_status = 503
    with pytest.raises(ValueError):
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-frost-0001")
    [failed] = _dispatches(db)
    assert failed.sent_document_id is not None and frozen_version(db, "rechnung", invoice.id) is None
    graph.fail_status = None
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-frost-0002")
    _failed, sent = _dispatches(db)
    assert sent.sent_document_id != failed.sent_document_id
    assert frozen_version(db, "rechnung", invoice.id).id == sent.sent_document_id


def test_stuck_dispatch_freezes_until_resolved_as_failed(db_session, smtp):
    """Hängend heißt "womöglich beim Kunden" -- die Fassung gilt, bis das Büro klärt, dass sie nicht
    hinausging."""
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    smtp.during_send = lambda: (_ for _ in ()).throw(SystemExit("Prozess bricht ab"))
    with pytest.raises(SystemExit):
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-abbruch-0001")
    db.rollback()
    [row] = _dispatches(db)
    assert row.status == "in_arbeit" and frozen_version(db, "rechnung", invoice.id).id == row.sent_document_id
    db.execute(update(EmailDispatch).where(EmailDispatch.id == row.id)
               .values(created_at=datetime.utcnow() - STUCK_AFTER - timedelta(minutes=1)))
    db.commit()
    resolve_stuck_dispatch(db, row.id, outcome="fehlgeschlagen", note="nicht im Postausgang", user_id=None, user_name="Anna")
    assert frozen_version(db, "rechnung", invoice.id) is None


def test_quotes_and_orders_are_not_frozen(db_session):
    assert frozen_version(db_session, "angebot", 1) is None and frozen_version(db_session, "auftrag", 1) is None


@pytest.mark.parametrize("damage,status", [("veraendert", 409), ("fehlt", 410)])
def test_damaged_archive_is_neither_reprinted_nor_resent_nor_rebuilt(office_world, router_test_client, damage, status):
    db = office_world
    client = _client(db, router_test_client)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-schaden-0001")
    [row] = _dispatches(db)
    path = _archive_path(row.sent_document)
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    if damage == "fehlt":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes().replace(b"%PDF", b"%PDX", 1))
    response = client.get(f"/api/invoices/{invoice.id}/pdf")
    assert response.status_code == status and "Versandprotokoll" in response.json()["detail"]
    with pytest.raises(ValueError) as exc:
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-schaden-0002")
    assert "nicht mehr unversehrt" in str(exc.value)
    assert len(FakeSMTP.sent) == 1 and len(_dispatches(db)) == 1


def test_archived_document_must_match_the_attachment(db_session, smtp):
    db = db_session
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="rechnung-passt-0001")
    archived = _dispatches(db)[0].sent_document
    with pytest.raises(ValueError):
        dispatch_email(db, dispatch_key="rechnung-passt-0002", document_type="rechnung", document_id=invoice.id,
                       document_number=invoice.invoice_number, to="kunde@example.com", cc=None, subject="R",
                       body_text="x", attachment_bytes=b"%PDF-anderes", attachment_filename="R.pdf",
                       archived_document=archived)
    assert len(smtp.sent) == 1
