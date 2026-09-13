from pathlib import Path
from unittest.mock import MagicMock, patch

from app.document_email_templates import update_email_template
from app.email_sending import update_smtp_settings
from app.projects import get_quote_recipient_email, load_quote, send_quote_email
from tests.test_v167_pagination import make_quote_with_items


def _configure_smtp(db):
    update_smtp_settings(
        db, host="smtp.example.com", port=587, username="buero@example.com",
        encryption="starttls", sender_email="buero@example.com", sender_name="Test GmbH",
        password="geheim123",
    )


def sendable_quote(db, *, customer_email=None, status="versendet"):
    """Erzeugt ein Angebot außerhalb des Status 'entwurf' -- Voraussetzung
    für send_quote_email(). make_quote_with_items() setzt standardmäßig
    keinen Status (Modell-Default 'entwurf'), daher hier explizit
    überschrieben."""
    quote = make_quote_with_items(db)
    quote.status = status
    if customer_email is not None:
        quote.project.customer.email = customer_email
    db.commit()
    db.refresh(quote)
    return load_quote(db, quote.id)


# ---------------------------------------------------------------------------
# get_quote_recipient_email()
# ---------------------------------------------------------------------------

def test_get_quote_recipient_email_none_without_customer_email():
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    quote = sendable_quote(db)  # kein customer.email gesetzt
    assert get_quote_recipient_email(quote) is None


def test_get_quote_recipient_email_returns_live_customer_email():
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    quote = sendable_quote(db, customer_email="kunde@example.com")
    assert get_quote_recipient_email(quote) == "kunde@example.com"


# ---------------------------------------------------------------------------
# send_quote_email()
# ---------------------------------------------------------------------------

def test_send_quote_email_rejects_draft():
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    quote = make_quote_with_items(db)  # Status bleibt 'entwurf'
    quote.project.customer.email = "kunde@example.com"
    db.commit()
    quote = load_quote(db, quote.id)
    try:
        send_quote_email(db, quote)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_send_quote_email_rejects_missing_recipient():
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    quote = sendable_quote(db)  # keine customer_email
    try:
        send_quote_email(db, quote)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


@patch("app.email_sending.smtplib.SMTP")
def test_send_quote_email_uses_customer_email_and_records_it(mock_smtp_cls):
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    quote = sendable_quote(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    result = send_quote_email(db, quote)

    assert result.email_sent_to == "kunde@example.com"
    assert result.email_sent_at is not None
    mock_conn.sendmail.assert_called_once()


@patch("app.email_sending.smtplib.SMTP")
def test_send_quote_email_override_beats_customer_email(mock_smtp_cls):
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    quote = sendable_quote(db, customer_email="alt@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    result = send_quote_email(db, quote, to_email="korrigiert@example.com")
    assert result.email_sent_to == "korrigiert@example.com"


@patch("app.email_sending.smtplib.SMTP")
def test_send_quote_email_can_be_repeated(mock_smtp_cls):
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    quote = sendable_quote(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_quote_email(db, quote)
    send_quote_email(db, quote, to_email="andere@example.com")
    assert quote.email_sent_to == "andere@example.com"
    assert mock_conn.sendmail.call_count == 2


@patch("app.email_sending.smtplib.SMTP")
def test_send_quote_email_uses_custom_template(mock_smtp_cls):
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    update_email_template(db, "quote", subject_template="Individueller Betreff {angebotsnummer}", body_template="Individueller Angebotstext")
    quote = sendable_quote(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_quote_email(db, quote)

    sent_message = mock_conn.sendmail.call_args[0][2]
    assert "Individueller Betreff" in sent_message
    assert quote.quote_number in sent_message


@patch("app.email_sending.smtplib.SMTP")
def test_send_quote_email_falls_back_to_default_text(mock_smtp_cls):
    """Ohne eigene Anpassung (NULL) muss trotzdem sofort ein sinnvoller
    Standardtext funktionieren -- darf nicht abstürzen."""
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    quote = sendable_quote(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_quote_email(db, quote)
    mock_conn.sendmail.assert_called_once()


@patch("app.email_sending.smtplib.SMTP")
def test_send_quote_email_attaches_a_pdf(mock_smtp_cls):
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    quote = sendable_quote(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_quote_email(db, quote)

    sent_message = mock_conn.sendmail.call_args[0][2]
    assert "application/pdf" in sent_message  # ein PDF-Anhang wurde tatsächlich gebaut und angehängt


@patch("app.email_sending.smtplib.SMTP")
@patch("app.quote_framed_pdf.build_quote_framed_pdf")
def test_send_quote_email_uses_the_shared_frame_renderer(mock_build, mock_smtp_cls):
    """Name/Zweck seit 1.3.13 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot, Punkt 4) --
    vorher 'test_send_quote_email_uses_layout_designer_pdf', prüfte aber tatsächlich nur, dass
    IRGENDEIN PDF angehängt wird, nicht welcher Renderer es gebaut hat (echter Fund beim Anfassen
    dieser Stelle). build_quote_framed_pdf() ist als lokaler Import in send_quote_email()
    eingebunden (app/projects.py) -- patchen am URSPRUNGSMODUL app.quote_framed_pdf ist hier
    deshalb richtig, nicht am Verwendungsort: der lokale Import löst den Namen bei JEDEM Aufruf
    frisch aus app.quote_framed_pdf auf, anders als ein Modul-weiter Import in projects.py selbst
    (vgl. CLAUDE.md "Testen" -- jene Regel gilt für smtplib, das email_sending.py modulweit
    importiert, ein anderer Fall)."""
    mock_build.return_value = b"%PDF-1.4 dummy"
    from tests.test_v153_mahnwesen import db_session
    db = db_session()
    _configure_smtp(db)
    quote = sendable_quote(db, customer_email="kunde@example.com")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    send_quote_email(db, quote)

    mock_build.assert_called_once()
    assert mock_build.call_args[0][1] is quote


# ---------------------------------------------------------------------------
# Statische Prüfungen
# ---------------------------------------------------------------------------

def test_quotes_router_has_send_email_endpoint():
    src = (Path(__file__).parents[1] / "app" / "routers" / "quotes.py").read_text(encoding="utf-8")
    assert '@router.post("/api/quotes/{quote_id}/send-email"' in src


def test_send_quote_email_uses_shared_frame_renderer():
    """Der eigentliche Renderer-Aufruf sitzt in send_quote_email() (app/projects.py), nicht im
    Router selbst -- die Prüfung muss deshalb auch dort lesen. Seit 1.3.13 (CLAUDE.md
    "Gemeinsamer Dokumenttyp"/Angebot, Punkt 4) build_quote_framed_pdf() statt des
    positionsbasierten build_quote_layout_pdf()."""
    src = (Path(__file__).parents[1] / "app" / "projects.py").read_text(encoding="utf-8")
    src = src[src.index("def send_quote_email("):]
    src = src[:src.index("\n\ndef ")]
    assert "from .quote_framed_pdf import build_quote_framed_pdf" in src
    assert "build_quote_layout_pdf(db, quote)" not in src  # der tatsächliche Aufruf, nicht die Docstring-Erwähnung der Historie


def test_quote_editor_has_send_email_action():
    html = (Path(__file__).parents[1] / "app" / "templates" / "quote_editor.html").read_text(encoding="utf-8")
    assert "sendQuoteEmail" in html
    assert "/send-email" in html
    assert "prompt(" not in html  # dieselbe Klärung wie bei Rechnung/Mahnung gilt auch hier


def test_settings_page_quote_placeholder_hint_is_active():
    """Ursprünglich stand hier 'noch nicht verfügbar' -- muss jetzt die
    echten Platzhalter zeigen, da die Integration fertig ist."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "noch nicht verfügbar" not in html.split("quote:")[1].split(",")[0]
