import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.email_sending import (
    check_smtp_connection,
    get_or_create_smtp_settings,
    is_smtp_configured,
    send_email_with_attachment,
    set_send_method,
    update_graph_settings,
    update_smtp_settings,
)
from tests.test_v153_mahnwesen import db_session


def _configure_graph(db, **overrides):
    defaults = dict(tenant_id="tenant-123", client_id="client-abc", sender_mailbox="buero@firma.de", client_secret="geheim")
    defaults.update(overrides)
    set_send_method(db, "graph_oauth2")
    update_graph_settings(db, **defaults)


def _fake_token_response(token="FAKE_TOKEN"):
    resp = MagicMock()
    resp.read.return_value = json.dumps({"access_token": token, "expires_in": 3599}).encode("utf-8")
    resp.__enter__.return_value = resp
    return resp


# ---------------------------------------------------------------------------
# send_method: Umschalten
# ---------------------------------------------------------------------------

def test_send_method_defaults_to_smtp():
    db = db_session()
    s = get_or_create_smtp_settings(db)
    assert s.send_method == "smtp"


def test_set_send_method_switches_to_graph():
    db = db_session()
    set_send_method(db, "graph_oauth2")
    assert get_or_create_smtp_settings(db).send_method == "graph_oauth2"


def test_set_send_method_rejects_unknown_value():
    db = db_session()
    try:
        set_send_method(db, "imap")
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# is_smtp_configured(): je nach send_method andere Pflichtfelder
# ---------------------------------------------------------------------------

def test_is_configured_false_for_graph_without_settings():
    db = db_session()
    set_send_method(db, "graph_oauth2")
    assert is_smtp_configured(db) is False


def test_is_configured_true_for_graph_with_complete_settings():
    db = db_session()
    _configure_graph(db)
    assert is_smtp_configured(db) is True


def test_is_configured_false_for_graph_without_secret_ever_set():
    db = db_session()
    set_send_method(db, "graph_oauth2")
    update_graph_settings(db, tenant_id="t", client_id="c", sender_mailbox="m@x.de")  # kein client_secret
    assert is_smtp_configured(db) is False


def test_check_connection_error_names_exactly_the_missing_field():
    """Nachstellung des tatsächlich aufgetretenen Falls: Mandanten-ID,
    Anwendungs-ID und Absender-Postfach sind gesetzt, nur das Client-Secret
    fehlt (z.B. weil in der Oberfläche fälschlich als 'unverändert lassen'
    verstanden) -- die Fehlermeldung muss das konkret benennen, nicht nur
    pauschal 'nicht vollständig konfiguriert' melden."""
    db = db_session()
    set_send_method(db, "graph_oauth2")
    update_graph_settings(db, tenant_id="tenant-123", client_id="client-abc", sender_mailbox="buero@firma.de")  # bewusst ohne client_secret
    try:
        check_smtp_connection(db)
        assert False, "hätte ValueError werfen müssen"
    except ValueError as e:
        assert "Client-Secret" in str(e)
        assert "Mandanten-ID" not in str(e)  # die anderen drei Felder sind ja gesetzt
        assert "Absender-Postfach" not in str(e)


def test_smtp_settings_do_not_count_when_graph_is_active():
    """Auch wenn zufällig noch alte SMTP-Daten hinterlegt sind, zählt nur
    die AKTIVE Methode -- sonst könnte is_smtp_configured() fälschlich
    True zurückgeben, obwohl der aktive Graph-Weg noch unvollständig ist."""
    db = db_session()
    update_smtp_settings(db, host="smtp.x.de", port=587, username="u", encryption="starttls", sender_email="a@x.de", sender_name=None, password="pw")
    set_send_method(db, "graph_oauth2")
    assert is_smtp_configured(db) is False  # Graph-Felder sind noch leer


# ---------------------------------------------------------------------------
# update_graph_settings(): "None-Secret-behalten"-Muster wie beim SMTP-Passwort
# ---------------------------------------------------------------------------

def test_update_graph_settings_none_secret_keeps_existing():
    from app.crypto import decrypt_secret
    db = db_session()
    _configure_graph(db, client_secret="erstes-secret")
    first_encrypted = get_or_create_smtp_settings(db).graph_client_secret_encrypted

    update_graph_settings(db, tenant_id="tenant-123", client_id="neue-client-id", sender_mailbox="buero@firma.de", client_secret=None)
    settings = get_or_create_smtp_settings(db)
    assert settings.graph_client_id == "neue-client-id"  # andere Felder geändert
    assert settings.graph_client_secret_encrypted == first_encrypted  # Secret unangetastet
    assert decrypt_secret(settings.graph_client_secret_encrypted) == "erstes-secret"


# ---------------------------------------------------------------------------
# Token-Abruf und Graph-Versand: urllib wird gemockt, nie echte Netzwerkverbindung
# ---------------------------------------------------------------------------

@patch("app.email_sending.urllib.request.urlopen")
def test_check_connection_graph_fetches_token_only(mock_urlopen):
    db = db_session()
    _configure_graph(db)
    mock_urlopen.return_value = _fake_token_response()

    check_smtp_connection(db)  # darf nicht werfen
    mock_urlopen.assert_called_once()
    called_url = mock_urlopen.call_args[0][0].full_url
    assert "tenant-123" in called_url
    assert "login.microsoftonline.com" in called_url


def test_check_connection_graph_raises_if_not_configured():
    db = db_session()
    set_send_method(db, "graph_oauth2")
    try:
        check_smtp_connection(db)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


@patch("app.email_sending.urllib.request.urlopen")
def test_check_connection_graph_wraps_http_error(mock_urlopen):
    import urllib.error
    db = db_session()
    _configure_graph(db)
    error = urllib.error.HTTPError(url="x", code=401, msg="Unauthorized", hdrs=None, fp=None)
    error.read = MagicMock(return_value=b'{"error":"invalid_client"}')
    mock_urlopen.side_effect = error

    try:
        check_smtp_connection(db)
        assert False, "hätte ValueError werfen müssen"
    except ValueError as e:
        assert "Microsoft 365" in str(e)


@patch("app.email_sending.urllib.request.urlopen")
def test_send_email_access_denied_gets_actionable_hint(mock_urlopen):
    """Nachstellung des tatsächlich aufgetretenen Falls: Graph liefert
    ErrorAccessDenied beim eigentlichen sendMail-Aufruf (Token-Abruf war
    erfolgreich, nur die Mail.Send-Berechtigung griff nicht) -- die
    Fehlermeldung muss einen konkreten, umsetzbaren Hinweis enthalten,
    nicht nur Microsofts rohe, wenig aussagekräftige Meldung."""
    import urllib.error
    db = db_session()
    _configure_graph(db)
    token_resp = _fake_token_response()
    error = urllib.error.HTTPError(url="x", code=403, msg="Forbidden", hdrs=None, fp=None)
    error.read = MagicMock(return_value=b'{"error":{"code":"ErrorAccessDenied","message":"Access is denied. Check credentials and try again."}}')
    mock_urlopen.side_effect = [token_resp, error]  # Token-Abruf klappt, erst der Sendeversuch schlägt fehl

    try:
        send_email_with_attachment(db, to_email="kunde@example.com", subject="Betreff", body_text="Text", attachment_bytes=b"%PDF-", attachment_filename="test.pdf")
        assert False, "hätte ValueError werfen müssen"
    except ValueError as e:
        assert "ErrorAccessDenied" in str(e)  # Microsofts Originalmeldung bleibt erhalten
        assert "Administratorzustimmung" in str(e)  # zusätzlicher, konkreter Hinweis


@patch("app.email_sending.urllib.request.urlopen")
def test_send_email_dispatches_to_graph_when_active(mock_urlopen):
    db = db_session()
    _configure_graph(db)
    token_resp = _fake_token_response()
    send_resp = MagicMock()  # kein __enter__ nötig -- sendMail-Aufruf nutzt urlopen() nicht als Context-Manager
    mock_urlopen.side_effect = [token_resp, send_resp]  # erst Token, dann sendMail

    send_email_with_attachment(db, to_email="kunde@example.com", subject="Betreff", body_text="Text", attachment_bytes=b"%PDF-", attachment_filename="test.pdf")

    assert mock_urlopen.call_count == 2
    send_request = mock_urlopen.call_args_list[1][0][0]
    assert "graph.microsoft.com" in send_request.full_url
    assert "buero%40firma.de" in send_request.full_url  # URL-kodiertes Absender-Postfach
    assert send_request.headers.get("Authorization") == "Bearer FAKE_TOKEN"


@patch("app.email_sending.urllib.request.urlopen")
def test_graph_send_payload_structure_and_attachment_roundtrip(mock_urlopen):
    import base64
    db = db_session()
    _configure_graph(db)
    token_resp = _fake_token_response()
    send_resp = MagicMock()  # kein __enter__ nötig -- sendMail-Aufruf nutzt urlopen() nicht als Context-Manager
    mock_urlopen.side_effect = [token_resp, send_resp]

    send_email_with_attachment(db, to_email="kunde@example.com", subject="Mahnung", body_text="Bitte begleichen", attachment_bytes=b"%PDF-1.4 echt", attachment_filename="M-2026-0001.pdf")

    send_request = mock_urlopen.call_args_list[1][0][0]
    payload = json.loads(send_request.data.decode("utf-8"))
    assert payload["message"]["subject"] == "Mahnung"
    assert payload["message"]["toRecipients"][0]["emailAddress"]["address"] == "kunde@example.com"
    attachment = payload["message"]["attachments"][0]
    assert attachment["name"] == "M-2026-0001.pdf"
    assert base64.b64decode(attachment["contentBytes"]) == b"%PDF-1.4 echt"


@patch("app.email_sending.smtplib.SMTP")
def test_send_email_still_uses_smtp_when_that_is_active(mock_smtp_cls):
    """Rückwärtskompatibilität: ohne Umschalten bleibt SMTP der aktive Weg,
    Graph-Code wird dabei gar nicht erst angefasst."""
    db = db_session()
    update_smtp_settings(db, host="smtp.x.de", port=587, username="u", encryption="starttls", sender_email="a@x.de", sender_name=None, password="pw")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_email_with_attachment(db, to_email="kunde@example.com", subject="Betreff", body_text="Text", attachment_bytes=b"%PDF-", attachment_filename="test.pdf")
    mock_conn.sendmail.assert_called_once()


# ---------------------------------------------------------------------------
# Statische Prüfungen
# ---------------------------------------------------------------------------

def test_email_settings_router_has_graph_endpoints():
    src = (Path(__file__).parents[1] / "app" / "routers" / "email_settings.py").read_text(encoding="utf-8")
    assert '@router.put("/api/email-settings/method"' in src
    assert '@router.put("/api/email-settings/graph"' in src


def test_settings_page_has_graph_fields():
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    for marker in ["emailSendMethod", "graphTenantId", "graphClientId", "graphClientSecret", "graphSenderMailbox", "saveGraphSettings", "onEmailSendMethodChange"]:
        assert marker in html, f"fehlt: {marker}"


def test_secret_fields_have_no_misleading_static_placeholder():
    """Der tatsächlich aufgetretene Fehler: ein fest im HTML stehender
    placeholder="unverändert lassen" täuschte bei der allerersten
    Einrichtung (wo es noch gar nichts zum Unverändertlassen gibt) einen
    bereits gespeicherten Wert vor. Platzhalter müssen jetzt dynamisch per
    JS gesetzt werden, abhängig vom tatsächlichen Zustand."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert 'id="smtpPassword" type="password"' in html
    assert 'id="graphClientSecret" type="password"' in html
    assert 'graphClientSecret\').placeholder' in html
    assert 'smtpPassword\').placeholder' in html
