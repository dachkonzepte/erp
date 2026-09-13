from pathlib import Path
from unittest.mock import MagicMock, patch

from app.email_sending import (
    check_smtp_connection,
    get_or_create_smtp_settings,
    is_smtp_configured,
    send_email_with_attachment,
    update_smtp_settings,
)
from app.reminders import (
    compute_reminder_status,
    create_reminder,
    ensure_default_reminder_levels,
    finalize_and_send_reminder,
    get_reminder_recipient_email,
    send_reminder_email,
    update_reminder_level,
)
from tests.test_v153_mahnwesen import db_session, make_sent_overdue_invoice


def extract_plain_text(raw_message: str) -> str:
    """Dekodiert den text/plain-Teil einer rohen MIME-Nachricht.

    Direkte Substring-Prüfungen auf msg.as_string() sind unzuverlässig,
    sobald der Text Nicht-ASCII-Zeichen enthält (z.B. das Euro-Zeichen aus
    {gesamtbetrag}) -- Python kodiert den Textteil dann automatisch als
    Base64/Quoted-Printable, wodurch selbst reiner ASCII-Text daraus nicht
    mehr als lesbare Zeichenkette im Rohformat auftaucht. Über das
    email-Modul selbst geparst, wird das automatisch richtig aufgelöst."""
    import email
    parsed = email.message_from_string(raw_message)
    for part in parsed.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset)
    return ""


def finalized_reminder(db, *, customer_email=None):
    """Baut eine bereits finalisierte (versendete) Mahnung -- Grundlage für
    die meisten E-Mail-Versand-Tests, die eine bereits versendete Mahnung
    voraussetzen (send_reminder_email() lehnt Entwürfe ab)."""
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    if customer_email is not None:
        invoice.order.project.customer.email = customer_email
        db.commit()
    status = compute_reminder_status(db, invoice)
    reminder = create_reminder(db, invoice, status["next_level"])
    return finalize_and_send_reminder(db, reminder)


# ---------------------------------------------------------------------------
# SmtpSettings: Geschäftslogik
# ---------------------------------------------------------------------------

def test_get_or_create_smtp_settings_seeds_defaults():
    db = db_session()
    s = get_or_create_smtp_settings(db)
    assert s.id == 1
    assert s.port == 587
    assert s.encryption == "starttls"


def test_is_smtp_configured_false_when_empty():
    db = db_session()
    assert is_smtp_configured(db) is False


def test_is_smtp_configured_true_after_update_with_password():
    db = db_session()
    update_smtp_settings(
        db, host="smtp.example.com", port=587, username="buero@example.com",
        encryption="starttls", sender_email="buero@example.com", sender_name="Test GmbH",
        password="geheim123",
    )
    assert is_smtp_configured(db) is True


def test_is_smtp_configured_false_without_password():
    """Ohne jemals ein Passwort gesetzt zu haben, gilt SMTP nicht als
    vollständig konfiguriert, selbst wenn alle anderen Felder gesetzt sind."""
    db = db_session()
    update_smtp_settings(
        db, host="smtp.example.com", port=587, username="buero@example.com",
        encryption="starttls", sender_email="buero@example.com", sender_name=None,
    )
    assert is_smtp_configured(db) is False


def test_update_smtp_settings_none_password_keeps_existing():
    db = db_session()
    update_smtp_settings(
        db, host="smtp.example.com", port=587, username="buero@example.com",
        encryption="starttls", sender_email="buero@example.com", sender_name=None, password="erstes-passwort",
    )
    first_encrypted = get_or_create_smtp_settings(db).password_encrypted

    update_smtp_settings(
        db, host="smtp.example.com", port=465, username="buero@example.com",
        encryption="ssl", sender_email="buero@example.com", sender_name="Neuer Name", password=None,
    )
    settings = get_or_create_smtp_settings(db)
    assert settings.port == 465  # andere Felder wurden geändert
    assert settings.password_encrypted == first_encrypted  # Passwort unangetastet


def test_update_smtp_settings_rejects_unknown_encryption():
    db = db_session()
    try:
        update_smtp_settings(
            db, host="smtp.example.com", port=587, username="x", encryption="wpa2",
            sender_email="x@example.com", sender_name=None,
        )
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_password_round_trips_through_encryption():
    """Das gespeicherte Passwort muss über decrypt_secret() wieder exakt
    lesbar sein -- die eigentliche Verschlüsselungslogik selbst wurde
    bereits isoliert mit der echten cryptography-Bibliothek bestätigt."""
    from app.crypto import decrypt_secret
    db = db_session()
    update_smtp_settings(
        db, host="smtp.example.com", port=587, username="x", encryption="starttls",
        sender_email="x@example.com", sender_name=None, password="mein-geheimes-passwort",
    )
    settings = get_or_create_smtp_settings(db)
    assert decrypt_secret(settings.password_encrypted) == "mein-geheimes-passwort"


# ---------------------------------------------------------------------------
# send_email_with_attachment() / check_smtp_connection(): SMTP wird gemockt,
# es darf in Tests nie eine echte Netzwerkverbindung aufgebaut werden.
# ---------------------------------------------------------------------------

def _configure_smtp(db, encryption="starttls"):
    update_smtp_settings(
        db, host="smtp.example.com", port=587, username="buero@example.com",
        encryption=encryption, sender_email="buero@example.com", sender_name="Test GmbH",
        password="geheim123",
    )


def test_send_email_raises_if_not_configured():
    db = db_session()
    try:
        send_email_with_attachment(db, to_email="kunde@example.com", subject="Test", body_text="Text", attachment_bytes=b"%PDF-", attachment_filename="test.pdf")
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


@patch("app.email_sending.smtplib.SMTP")
def test_send_email_uses_starttls_and_sends(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db, encryption="starttls")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_email_with_attachment(db, to_email="kunde@example.com", subject="Betreff", body_text="Nachricht", attachment_bytes=b"%PDF-1.4 ...", attachment_filename="mahnung.pdf")

    mock_smtp_cls.assert_called_once()
    mock_conn.starttls.assert_called_once()
    mock_conn.login.assert_called_once_with("buero@example.com", "geheim123")
    mock_conn.sendmail.assert_called_once()
    mock_conn.quit.assert_called_once()


@patch("app.email_sending.smtplib.SMTP_SSL")
def test_send_email_uses_ssl_without_starttls(mock_smtp_ssl_cls):
    db = db_session()
    _configure_smtp(db, encryption="ssl")
    mock_conn = MagicMock()
    mock_smtp_ssl_cls.return_value = mock_conn

    send_email_with_attachment(db, to_email="kunde@example.com", subject="Betreff", body_text="Nachricht", attachment_bytes=b"%PDF-", attachment_filename="mahnung.pdf")

    mock_smtp_ssl_cls.assert_called_once()
    mock_conn.starttls.assert_not_called()
    mock_conn.sendmail.assert_called_once()


@patch("app.email_sending.smtplib.SMTP")
def test_send_email_wraps_smtp_exception_as_value_error(mock_smtp_cls):
    import smtplib
    db = db_session()
    _configure_smtp(db)
    mock_conn = MagicMock()
    mock_conn.sendmail.side_effect = smtplib.SMTPException("Postfach abgelehnt")
    mock_smtp_cls.return_value = mock_conn

    try:
        send_email_with_attachment(db, to_email="kunde@example.com", subject="Betreff", body_text="Nachricht", attachment_bytes=b"%PDF-", attachment_filename="mahnung.pdf")
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


@patch("app.email_sending.smtplib.SMTP")
def test_smtp_connection_test_logs_in_and_quits(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    check_smtp_connection(db)
    mock_conn.login.assert_called_once()
    mock_conn.quit.assert_called_once()


def test_smtp_connection_test_raises_if_not_configured():
    db = db_session()
    try:
        check_smtp_connection(db)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


@patch("app.email_sending.smtplib.SMTP")
def test_smtp_connection_test_wraps_auth_error(mock_smtp_cls):
    import smtplib
    db = db_session()
    _configure_smtp(db)
    mock_conn = MagicMock()
    mock_conn.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
    mock_smtp_cls.return_value = mock_conn

    try:
        check_smtp_connection(db)
        assert False, "hätte ValueError werfen müssen"
    except ValueError as e:
        assert "Anmeldung" in str(e)


# ---------------------------------------------------------------------------
# get_reminder_recipient_email() / send_reminder_email()
# ---------------------------------------------------------------------------

def test_get_reminder_recipient_email_none_without_customer_email():
    db = db_session()
    reminder = finalized_reminder(db)  # kein customer_email gesetzt
    assert get_reminder_recipient_email(reminder) is None


def test_get_reminder_recipient_email_returns_live_customer_email():
    db = db_session()
    reminder = finalized_reminder(db, customer_email="kunde@example.com")
    assert get_reminder_recipient_email(reminder) == "kunde@example.com"


def test_send_reminder_email_rejects_draft():
    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    status = compute_reminder_status(db, invoice)
    draft = create_reminder(db, invoice, status["next_level"])  # nicht finalisiert
    try:
        send_reminder_email(db, draft)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_send_reminder_email_rejects_missing_recipient():
    db = db_session()
    reminder = finalized_reminder(db)  # keine customer_email
    try:
        send_reminder_email(db, reminder)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


@patch("app.email_sending.smtplib.SMTP")
def test_send_reminder_email_uses_customer_email_and_records_it(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    reminder = finalized_reminder(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    result = send_reminder_email(db, reminder)

    assert result.email_sent_to == "kunde@example.com"
    assert result.email_sent_at is not None
    mock_conn.sendmail.assert_called_once()


@patch("app.email_sending.smtplib.SMTP")
def test_send_reminder_email_override_beats_customer_email(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    reminder = finalized_reminder(db, customer_email="alt@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    result = send_reminder_email(db, reminder, to_email="korrigiert@example.com")

    assert result.email_sent_to == "korrigiert@example.com"


@patch("app.email_sending.smtplib.SMTP")
def test_send_reminder_email_can_be_repeated(mock_smtp_cls):
    """Erneuter Versand (z.B. Kunde hat die Mahnung nicht erhalten) muss
    möglich sein und email_sent_at/email_sent_to jedes Mal aktualisieren."""
    db = db_session()
    _configure_smtp(db)
    reminder = finalized_reminder(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_reminder_email(db, reminder)
    first_sent_at = reminder.email_sent_at
    send_reminder_email(db, reminder, to_email="andere@example.com")

    assert reminder.email_sent_to == "andere@example.com"
    assert reminder.email_sent_at >= first_sent_at
    assert mock_conn.sendmail.call_count == 2


@patch("app.email_sending.smtplib.SMTP")
def test_send_reminder_email_uses_custom_level_templates(mock_smtp_cls):
    """Klärung: E-Mail-Text soll pro Mahnstufe konfigurierbar sein."""
    from sqlalchemy import select
    from app.models import ReminderLevel

    db = db_session()
    _configure_smtp(db)
    reminder = finalized_reminder(db, customer_email="kunde@example.com")
    level_row = db.scalar(select(ReminderLevel).where(ReminderLevel.level == reminder.level))
    update_reminder_level(
        db, level_row, label=level_row.label, days_after_previous_step=level_row.days_after_previous_step,
        fee_amount=level_row.fee_amount, text_template=level_row.text_template, active=level_row.active,
        email_subject_template="Individueller Betreff {rechnungsnummer}",
        email_body_template="Individueller Text mit {gesamtbetrag}",
    )
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_reminder_email(db, reminder)

    sent_message = mock_conn.sendmail.call_args[0][2]
    assert "Individueller Betreff" in sent_message  # Betreff bleibt rein ASCII, daher unkodiert lesbar
    assert "Individueller Text mit" in extract_plain_text(sent_message)  # Text enthält € -> wird kodiert, muss dekodiert geprüft werden


@patch("app.email_sending.smtplib.SMTP")
def test_send_reminder_email_falls_back_to_default_text(mock_smtp_cls):
    """Ohne eigene Anpassung (NULL) muss trotzdem sofort ein sinnvoller
    Standardtext funktionieren."""
    db = db_session()
    _configure_smtp(db)
    reminder = finalized_reminder(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_reminder_email(db, reminder)  # darf nicht abstürzen, keine Templates gesetzt
    mock_conn.sendmail.assert_called_once()


# ---------------------------------------------------------------------------
# Statische Prüfungen
# ---------------------------------------------------------------------------

def test_email_settings_router_registered_and_admin_protected():
    src = (Path(__file__).parents[1] / "app" / "routers" / "email_settings.py").read_text(encoding="utf-8")
    assert '@router.get("/api/email-settings"' in src
    assert '@router.put("/api/email-settings"' in src
    assert '@router.post("/api/email-settings/test")' in src
    assert "require_admin" in src


def test_main_registers_email_settings_router():
    src = (Path(__file__).parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "email_settings" in src
    assert "app.include_router(email_settings.router)" in src


def test_reminders_router_has_send_email_endpoint():
    src = (Path(__file__).parents[1] / "app" / "routers" / "reminders.py").read_text(encoding="utf-8")
    assert '@router.post("/api/reminders/{reminder_id}/send-email"' in src


def test_settings_page_has_email_section():
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    for marker in ["smtpHost", "smtpPort", "smtpUsername", "smtpPassword", "smtpEncryption", "saveSmtpSettings", "testEmailSettings"]:
        assert marker in html, f"fehlt: {marker}"


def test_mahnwesen_page_has_send_email_action():
    html = (Path(__file__).parents[1] / "app" / "templates" / "mahnwesen.html").read_text(encoding="utf-8")
    assert "sendReminderEmail" in html
    assert "/send-email" in html


def test_mahnwesen_page_uses_visible_input_not_popup_prompt():
    """Klärung: kein Popup-Fenster zur E-Mail-Eingabe -- stattdessen ein
    bereits sichtbares, vorausgefülltes Eingabefeld direkt in der Zeile."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "mahnwesen.html").read_text(encoding="utf-8")
    assert "prompt(" not in html
    assert 'type="email"' in html
    assert "reminderEmailInput" in html


def test_requirements_include_cryptography():
    req = (Path(__file__).parents[1] / "requirements.txt").read_text(encoding="utf-8")
    assert "cryptography" in req
