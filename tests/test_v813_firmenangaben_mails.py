"""Version 1.11.17 (§ 35a GmbHG, Antwort des Betriebs vom 24.11.2026): unter jede Mail an Kunden und Beteiligte setzt dispatch_email() nach einer Leerzeile
Name, Anschrift und Pflichtangaben aus den Firmendaten -- eine Quelle (app/firmenangaben.py) für die Mails des ERP und des Kundenportals; die Aufgaben-Mails an
Mitarbeiter ohne.

    Arten       jede Versandart ist eingeordnet: ohne nur „aufgabe“; jede andere Text-Mail bekommt den Schluss, die Mails des Portals tragen dieselben Angaben in
                ihrer HTML-Fußzeile
    Schluss     nach einer Leerzeile „Name · Straße · PLZ Ort“, darunter „Sitz … · Registergericht Nummer · Geschäftsführer: …“; fehlt ein Feld, fällt nur
                dieses weg; ohne jede Angabe bleibt der Text, wie er war
    Beispiel    eine echte Angebotsmail (send_quote_email) mit dem Schluss
"""

import pytest

from app import email_dispatch, firmenangaben, portal_mails
from app.email_dispatch import DISPATCH_TYPES, OHNE_FIRMENANGABEN, PORTAL_TYPES, dispatch_email
from app.models import Customer
from app.projects import send_quote_email
from app.settings import load_general_settings
from tests.test_v187_quote_email import _configure_smtp, sendable_quote

FIRMA = dict(company_name="Muster Bedachung GmbH", street="Dachweg 1", postal_code="12345", city="Musterstadt", register_court="Amtsgericht Musterstadt",
             register_number="HRB 99999", managing_director="Erika Beispiel")
ANSCHRIFT = "Muster Bedachung GmbH · Dachweg 1 · 12345 Musterstadt"
PFLICHT = "Sitz Musterstadt · Amtsgericht Musterstadt HRB 99999 · Geschäftsführer: Erika Beispiel"
SCHLUSS = f"\n\n{ANSCHRIFT}\n{PFLICHT}"


def _db():
    from tests.test_v153_mahnwesen import db_session
    return db_session()


def _firma(db, **werte):
    s = load_general_settings(db)
    for k, v in {**FIRMA, **werte}.items():
        setattr(s, k, v)
    db.commit()


@pytest.fixture
def gesendet(monkeypatch):
    mails = []
    monkeypatch.setattr(email_dispatch, "send_message", lambda _settings, **kw: mails.append(kw))
    return mails


def _senden(db, art, text="Guten Tag,\n\nanbei.\n\nMit freundlichen Grüßen\n", **extra):
    return dispatch_email(db, dispatch_key=f"test-{art}-{len(text)}-1234", document_type=art, document_id=1, document_number="N-1",
                          to="kunde@example.invalid", cc=None, subject="Betreff", body_text=text, **extra)


def test_jede_versandart_eingeordnet():
    assert OHNE_FIRMENANGABEN == frozenset({"aufgabe"})  # nur die Mails an Mitarbeiter
    assert OHNE_FIRMENANGABEN <= set(DISPATCH_TYPES) and not (OHNE_FIRMENANGABEN & set(PORTAL_TYPES))


@pytest.mark.parametrize("art", sorted(set(DISPATCH_TYPES) - OHNE_FIRMENANGABEN - set(PORTAL_TYPES)))
def test_jede_mail_an_kunden_mit_dem_schluss(gesendet, art):
    db = _db()
    _configure_smtp(db)
    _firma(db)
    _senden(db, art)
    assert gesendet[-1]["body_text"] == "Guten Tag,\n\nanbei.\n\nMit freundlichen Grüßen" + SCHLUSS


def test_aufgaben_mails_ohne(gesendet):
    db = _db()
    _configure_smtp(db)
    _firma(db)
    _senden(db, "aufgabe", text="Neue Aufgabe: …\n")
    assert gesendet[-1]["body_text"] == "Neue Aufgabe: …\n"


@pytest.mark.parametrize("felder, schluss", [
    ({"register_court": None, "register_number": None, "managing_director": None}, f"\n\n{ANSCHRIFT}\nSitz Musterstadt"),
    ({"city": "", "postal_code": "", "register_number": " "}, "\n\nMuster Bedachung GmbH · Dachweg 1\nAmtsgericht Musterstadt · Geschäftsführer: Erika Beispiel"),
    ({"company_name": "", "street": None}, "\n\n12345 Musterstadt\n" + PFLICHT),
    ({"company_name": "", "street": None, "postal_code": None, "city": None, "register_court": None, "register_number": None, "managing_director": None}, ""),
])
def test_fehlt_ein_feld_faellt_nur_dieses_weg(gesendet, felder, schluss):
    db = _db()
    _configure_smtp(db)
    _firma(db, **felder)
    _senden(db, "rechnung")
    assert gesendet[-1]["body_text"] == "Guten Tag,\n\nanbei.\n\nMit freundlichen Grüßen" + schluss


def test_angebotsmail_mit_name_anschrift_und_pflichtangaben(gesendet):
    """Das Beispiel für den Bericht: eine echte Angebotsmail mit dem Text der Vorgabe und dem Schluss."""
    db = _db()
    _configure_smtp(db)
    _firma(db)
    quote = sendable_quote(db, customer_email="kunde@example.invalid")
    send_quote_email(db, quote)
    text = gesendet[-1]["body_text"]
    assert text.startswith("Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie unser Angebot ")
    assert text.endswith("Mit freundlichen Grüßen" + SCHLUSS)


def test_eine_quelle_fuer_portal_und_erp():
    db = _db()
    _firma(db)
    f = portal_mails.firma(db)
    assert firmenangaben.zeilen(db) == [f.anschrift, f.pflichtangaben] == [ANSCHRIFT, PFLICHT]
    assert portal_mails.pflichtangaben is firmenangaben.pflichtangaben


def test_mails_des_portals_ohne_textschluss_mit_html_fusszeile(gesendet):
    db = _db()
    _firma(db)
    from tests.test_v321_email_dispatch import _configure_graph
    _configure_graph(db)
    kunde = Customer(name="Herr Max Muster", salutation="Herr", first_name="Max", last_name="Muster", email="max@example.invalid")
    db.add(kunde)
    db.commit()
    html_ = portal_mails.code_html(db, kunde, "481207")
    portal_mails.senden(db, art="portal_code", dokument_id=1, an="max@example.invalid", html_=html_, dispatch_key="portal-code-test-0001")
    assert gesendet[-1]["body_text"] == "" and PFLICHT in gesendet[-1]["body_html"] and ANSCHRIFT in gesendet[-1]["body_html"]
