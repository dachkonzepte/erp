from pathlib import Path
from unittest.mock import MagicMock, patch

from app.document_email_templates import update_email_template
from app.email_sending import update_smtp_settings
from app.orders import get_order_recipient_email, load_order, send_order_email
from tests.test_v133_invoices import make_order_with_item


def _configure_smtp(db):
    update_smtp_settings(
        db, host="smtp.example.com", port=587, username="buero@example.com",
        encryption="starttls", sender_email="buero@example.com", sender_name="Test GmbH",
        password="geheim123",
    )


def sendable_order(db, *, customer_email=None, status="beauftragt"):
    """make_order_with_item() setzt standardmäßig keinen Status (Modell-
    Default 'beauftragt', bereits versendbar -- anders als bei Angebot/
    Rechnung/Mahnung gibt es hier keinen 'entwurf'-Zustand)."""
    order, _item = make_order_with_item(db)
    order.status = status
    if customer_email is not None:
        order.project.customer.email = customer_email
    db.commit()
    db.refresh(order)
    return load_order(db, order.id)


# ---------------------------------------------------------------------------
# get_order_recipient_email()
# ---------------------------------------------------------------------------

def test_get_order_recipient_email_none_without_customer_email():
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    order = sendable_order(db)  # kein customer.email gesetzt
    assert get_order_recipient_email(order) is None


def test_get_order_recipient_email_returns_live_customer_email():
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    order = sendable_order(db, customer_email="kunde@example.com")
    assert get_order_recipient_email(order) == "kunde@example.com"


def test_get_order_recipient_email_ignores_customer_name_snapshot():
    """order.customer_name ist ein reiner Anzeige-Snapshot vom
    Beauftragungszeitpunkt -- die E-Mail-Adresse muss trotzdem live vom
    aktuellen Kundenstammdatensatz kommen, falls sich diese geändert hat."""
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    order = sendable_order(db, customer_email="neu@example.com")
    assert order.customer_name == "Test Kunde"  # Snapshot unverändert
    assert get_order_recipient_email(order) == "neu@example.com"  # E-Mail trotzdem aktuell


# ---------------------------------------------------------------------------
# send_order_email()
# ---------------------------------------------------------------------------

def test_send_order_email_rejects_cancelled():
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    order = sendable_order(db, customer_email="kunde@example.com", status="storniert")
    try:
        send_order_email(db, order)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_send_order_email_works_for_default_status_without_draft_concept():
    """Klärung: ein Auftrag hat (anders als Angebot/Rechnung/Mahnung) von
    Anfang an keinen 'entwurf'-Status -- der Standardstatus 'beauftragt'
    muss direkt versendbar sein, ohne vorherige Finalisierung."""
    from tests.test_v153_mahnwesen import db_session
    with patch("app.email_sending.smtplib.SMTP") as mock_smtp_cls:
        db = db_session()
        _configure_smtp(db)
        order = sendable_order(db, customer_email="kunde@example.com")
        assert order.status == "beauftragt"
        mock_conn = MagicMock()
        mock_smtp_cls.return_value = mock_conn
        send_order_email(db, order)
        mock_conn.sendmail.assert_called_once()


def test_send_order_email_rejects_missing_recipient():
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    order = sendable_order(db)  # keine customer_email
    try:
        send_order_email(db, order)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


@patch("app.email_sending.smtplib.SMTP")
def test_send_order_email_uses_customer_email_and_records_it(mock_smtp_cls):
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    order = sendable_order(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    result = send_order_email(db, order)

    assert result.email_sent_to == "kunde@example.com"
    assert result.email_sent_at is not None
    mock_conn.sendmail.assert_called_once()


@patch("app.email_sending.smtplib.SMTP")
def test_send_order_email_override_beats_customer_email(mock_smtp_cls):
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    order = sendable_order(db, customer_email="alt@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    result = send_order_email(db, order, to_email="korrigiert@example.com")
    assert result.email_sent_to == "korrigiert@example.com"


@patch("app.email_sending.smtplib.SMTP")
def test_send_order_email_can_be_repeated(mock_smtp_cls):
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    order = sendable_order(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_order_email(db, order)
    send_order_email(db, order, to_email="andere@example.com")
    assert order.email_sent_to == "andere@example.com"
    assert mock_conn.sendmail.call_count == 2


@patch("app.email_sending.smtplib.SMTP")
def test_send_order_email_uses_custom_template(mock_smtp_cls):
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    update_email_template(db, "order", subject_template="Individueller Betreff {auftragsnummer}", body_template="Individueller Auftragstext")
    order = sendable_order(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_order_email(db, order)

    sent_message = mock_conn.sendmail.call_args[0][2]
    assert "Individueller Betreff" in sent_message
    assert order.order_number in sent_message


@patch("app.email_sending.smtplib.SMTP")
def test_send_order_email_falls_back_to_default_text(mock_smtp_cls):
    """Ohne eigene Anpassung (NULL) muss trotzdem sofort ein sinnvoller
    Standardtext funktionieren -- darf nicht abstürzen."""
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    order = sendable_order(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_order_email(db, order)
    mock_conn.sendmail.assert_called_once()


# ---------------------------------------------------------------------------
# Statische Prüfungen
# ---------------------------------------------------------------------------

def test_orders_router_has_send_email_endpoint():
    src = (Path(__file__).parents[1] / "app" / "routers" / "orders.py").read_text(encoding="utf-8")
    assert '@router.post("/api/orders/{order_id}/send-email"' in src


def test_order_page_has_send_email_action():
    html = (Path(__file__).parents[1] / "app" / "templates" / "order.html").read_text(encoding="utf-8")
    assert "sendOrderEmail" in html
    assert "/send-email" in html


def test_order_page_does_not_use_popup_for_email_input():
    """Dieselbe Klärung wie bei Rechnung/Mahnung/Angebot: kein prompt()
    zur E-Mail-Eingabe. Die einzige verbleibende prompt()-Stelle in dieser
    Datei (saveRevision) ist unverwandt und bleibt bewusst unverändert."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "order.html").read_text(encoding="utf-8")
    assert "orderEmailInput" in html
    for line in html.splitlines():
        if "prompt(" in line:
            assert "sendOrderEmail" not in line and "orderEmailInput" not in line


def test_settings_page_order_placeholder_hint_is_active():
    """Ursprünglich stand hier 'noch nicht verfügbar' -- muss jetzt die
    echten Platzhalter zeigen, da die Integration fertig ist. Direkte
    Substring-Prüfung statt Split auf 'order:', da dieses Muster auch
    zufällig als Teil von CSS-'border:'-Deklarationen vorkommt."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "order: 'Verfügbare Platzhalter: {auftragsnummer}" in html
    assert "order: 'Für Aufträge noch nicht verfügbar" not in html
