import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.document_email_templates import get_email_template, update_email_template
from app.email_sending import update_smtp_settings
from app.invoices import get_invoice_recipient_email, send_invoice_email
from tests.test_v153_mahnwesen import db_session, make_sent_overdue_invoice


def _configure_smtp(db):
    update_smtp_settings(
        db, host="smtp.example.com", port=587, username="buero@example.com",
        encryption="starttls", sender_email="buero@example.com", sender_name="Test GmbH",
        password="geheim123",
    )


# ---------------------------------------------------------------------------
# DocumentEmailTemplate: Geschäftslogik
# ---------------------------------------------------------------------------

def test_get_email_template_none_when_never_set():
    db = db_session()
    assert get_email_template(db, "invoice") is None


def test_update_email_template_creates_and_updates():
    db = db_session()
    update_email_template(db, "invoice", subject_template="Betreff X", body_template="Text X")
    row = get_email_template(db, "invoice")
    assert row.subject_template == "Betreff X"
    assert row.body_template == "Text X"

    update_email_template(db, "invoice", subject_template="Betreff Y", body_template="Text Y")
    row2 = get_email_template(db, "invoice")
    assert row2.subject_template == "Betreff Y"  # aktualisiert, keine zweite Zeile


def test_email_templates_independent_per_document_type():
    db = db_session()
    update_email_template(db, "invoice", subject_template="Rechnungs-Betreff", body_template=None)
    update_email_template(db, "quote", subject_template="Angebots-Betreff", body_template=None)
    assert get_email_template(db, "invoice").subject_template == "Rechnungs-Betreff"
    assert get_email_template(db, "quote").subject_template == "Angebots-Betreff"


def test_get_email_template_rejects_unknown_document_type():
    db = db_session()
    try:
        get_email_template(db, "mahnung")
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# get_invoice_recipient_email()
# ---------------------------------------------------------------------------

def test_get_invoice_recipient_email_none_without_customer_email():
    db = db_session()
    invoice = make_sent_overdue_invoice(db)  # kein customer.email gesetzt
    assert get_invoice_recipient_email(invoice) is None


def test_get_invoice_recipient_email_returns_live_customer_email():
    db = db_session()
    invoice = make_sent_overdue_invoice(db)
    invoice.order.project.customer.email = "kunde@example.com"
    db.commit()
    assert get_invoice_recipient_email(invoice) == "kunde@example.com"


# ---------------------------------------------------------------------------
# send_invoice_email()
# ---------------------------------------------------------------------------

def test_send_invoice_email_rejects_draft():
    from decimal import Decimal
    from app.models import Customer, Invoice, Order, Project
    from app.project_pipeline_columns import default_pipeline_column_id
    db = db_session()
    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-DRAFT-0001", name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-DRAFT-0001", project_id=project.id, source_quote_id=1, quote_number_snapshot="A-DRAFT-0001",
        title="Testauftrag", vat_rate=Decimal("19.00"), customer_name="Test Kunde", customer_number="K-D001",
    )
    db.add(order)
    db.flush()
    draft = Invoice(invoice_number=None, order_id=order.id, invoice_type="schluss", status="entwurf", customer_name="Test Kunde", vat_rate=Decimal("19.00"))
    db.add(draft)
    db.commit()
    db.refresh(draft)
    try:
        send_invoice_email(db, draft)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_send_invoice_email_rejects_missing_recipient():
    db = db_session()
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)  # keine customer_email
    try:
        send_invoice_email(db, invoice)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


@patch("app.email_sending.smtplib.SMTP")
def test_send_invoice_email_uses_customer_email_and_records_it(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    invoice.order.project.customer.email = "kunde@example.com"
    db.commit()
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    result = send_invoice_email(db, invoice)

    assert result.email_sent_to == "kunde@example.com"
    assert result.email_sent_at is not None
    mock_conn.sendmail.assert_called_once()


@patch("app.email_sending.smtplib.SMTP")
def test_send_invoice_email_override_beats_customer_email(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    invoice.order.project.customer.email = "alt@example.com"
    db.commit()
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    result = send_invoice_email(db, invoice, to_email="korrigiert@example.com")
    assert result.email_sent_to == "korrigiert@example.com"


@patch("app.email_sending.smtplib.SMTP")
def test_send_invoice_email_can_be_repeated(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    invoice.order.project.customer.email = "kunde@example.com"
    db.commit()
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_invoice_email(db, invoice)
    send_invoice_email(db, invoice, to_email="andere@example.com")
    assert invoice.email_sent_to == "andere@example.com"
    assert mock_conn.sendmail.call_count == 2


@patch("app.email_sending.smtplib.SMTP")
def test_send_invoice_email_uses_custom_template(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    update_email_template(db, "invoice", subject_template="Individueller Betreff {rechnungsnummer}", body_template="Individueller Rechnungstext")
    invoice = make_sent_overdue_invoice(db)
    invoice.order.project.customer.email = "kunde@example.com"
    db.commit()
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_invoice_email(db, invoice)

    sent_message = mock_conn.sendmail.call_args[0][2]
    assert "Individueller Betreff" in sent_message
    assert invoice.invoice_number in sent_message  # Platzhalter tatsächlich ersetzt


@patch("app.email_sending.smtplib.SMTP")
def test_send_invoice_email_falls_back_to_default_text(mock_smtp_cls):
    """Ohne eigene Anpassung (NULL) muss trotzdem sofort ein sinnvoller
    Standardtext funktionieren -- darf nicht abstürzen."""
    db = db_session()
    _configure_smtp(db)
    invoice = make_sent_overdue_invoice(db)
    invoice.order.project.customer.email = "kunde@example.com"
    db.commit()
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_invoice_email(db, invoice)
    mock_conn.sendmail.assert_called_once()


# ---------------------------------------------------------------------------
# Statische Prüfungen
# ---------------------------------------------------------------------------

def test_invoices_router_has_send_email_endpoint():
    src = (Path(__file__).parents[1] / "app" / "routers" / "invoices.py").read_text(encoding="utf-8")
    assert '@router.post("/api/invoices/{invoice_id}/send-email"' in src


def test_document_email_templates_router_registered():
    src = (Path(__file__).parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "document_email_templates" in src
    assert "app.include_router(document_email_templates.router)" in src


def test_invoice_detail_page_has_send_email_action():
    html = (Path(__file__).parents[1] / "app" / "templates" / "invoice_detail.html").read_text(encoding="utf-8")
    assert "sendInvoiceEmail" in html
    assert "/send-email" in html


def test_invoice_detail_page_uses_visible_input_not_popup_prompt():
    """Klärung: kein Popup-Fenster zur E-Mail-Eingabe -- stattdessen ein
    bereits sichtbares, vorausgefülltes Eingabefeld direkt auf der Seite."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "invoice_detail.html").read_text(encoding="utf-8")
    assert "prompt(" not in html
    assert 'type="email"' in html
    assert "invoiceEmailInput" in html


def test_settings_page_has_email_template_section():
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    for marker in ["emailTemplateType", "emailTemplateSubject", "emailTemplateBody", "saveEmailTemplate", "loadEmailTemplate"]:
        assert marker in html, f"fehlt: {marker}"


def test_settings_email_templates_include_reminder_levels():
    """Ursprünglich fehlten die Mahnungs-Vorlagen in der einheitlichen
    E-Mail-Vorlagen-Sektion (lebten nur in der Mahnstufen-Sektion) --
    jetzt über denselben, einheitlichen Bereich erreichbar."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "populateReminderLevelEmailOptions" in html
    assert "reminder:" in html
    assert "/api/reminder-levels/" in html  # saveEmailTemplate() muss dorthin schreiben können
