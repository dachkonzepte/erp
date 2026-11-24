"""Mails des Kundenportals (seit 1.11.5, Stufe P1c): Link und Anmeldecode -- fester Betreff, gesiezt, nur über Microsoft 365, ohne „Gesendete Elemente“.

Die Graph-Attrappe ist die aus tests/test_v321_email_dispatch.py (verhält sich wie der echte Dienst); hier merkt sie sich zusätzlich die ganze Anfrage, um
saveToSentItems zu sehen.
"""

from __future__ import annotations

import ast
import json
import logging
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.email_dispatch import DISPATCH_TYPES, DOCUMENT_TYPES, PORTAL_TYPES, dispatch_email
from app.models import Customer, EmailDispatch
from app import portal_mails
from app.settings import load_general_settings
from tests.test_v321_email_dispatch import FakeGraph, FakeSMTP, _configure_graph, _configure_smtp

ROOT = Path(__file__).resolve().parents[1]
CODE = "480913"
LINK = "https://kunde.dachkonzepte.gmbh/#z=" + "Testwert_nur-fuer-den-Test" + "a" * 17  # 43 Zeichen wie pruefwerte.neuer_wert()


class GraphMitAnfrage(FakeGraph):
    """Die Attrappe aus test_v321, dazu jede ganze Anfrage an sendMail."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.anfragen = []

    def __call__(self, req, timeout=None):
        if req.full_url.endswith("/sendMail"):
            anfrage = json.loads(req.data)
            assert anfrage.get("saveToSentItems") in ("true", "false"), "Graph erwartet true oder false"
            self.anfragen.append(anfrage)
        return super().__call__(req, timeout=timeout)


@pytest.fixture
def graph(monkeypatch):
    fake = GraphMitAnfrage()
    monkeypatch.setattr("app.email_sending.urllib.request.urlopen", fake)
    return fake


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    return FakeSMTP


def _kunde(db, **werte) -> Customer:
    felder = dict(name="Herr Dr. Max Muster", salutation="Herr", title="Dr.", first_name="Max", last_name="Muster", email="max@example.invalid")
    felder.update(werte)
    kunde = Customer(**felder)
    db.add(kunde)
    db.commit()
    return kunde


def _firma(db):
    s = load_general_settings(db)
    s.company_name, s.street, s.postal_code, s.city = "Muster Bedachung GmbH", "Dachweg 1", "12345", "Musterstadt"
    s.phone, s.email, s.website = "0123 456789", "info@example.invalid", "www.example.invalid"
    db.commit()


def _alles_gespeicherte(db) -> str:
    return " ".join(str(v) for row in db.scalars(select(EmailDispatch)).all() for v in row.__dict__.values())


def test_versandarten_des_portals():
    assert PORTAL_TYPES == {"portal_link": "Link zum Kundenportal", "portal_code": "Anmeldecode des Kundenportals"}
    assert set(PORTAL_TYPES) <= set(DISPATCH_TYPES) and not set(PORTAL_TYPES) & set(DOCUMENT_TYPES)  # keine Dokumente: kein PDF, keine Ablage
    for betreff in portal_mails.BETREFF.values():  # fest, ohne Link und Code
        assert not any(z.isdigit() for z in betreff) and "http" not in betreff and "#" not in betreff


def test_code_ueber_graph_ohne_gesendete_elemente(db_session, graph):
    db = db_session
    _configure_graph(db)
    _firma(db)
    kunde = _kunde(db)
    ergebnis = portal_mails.senden(db, art="portal_code", dokument_id=7, an="max@example.invalid", html_=portal_mails.code_html(db, kunde, CODE),
                                   dispatch_key="portal-code-7", user_name="Postbote")
    assert ergebnis.newly_sent
    [anfrage] = graph.anfragen
    assert anfrage["saveToSentItems"] == "false"
    nachricht = anfrage["message"]
    assert nachricht["subject"] == "Ihr Anmeldecode für das Kundenportal"
    assert [r["emailAddress"]["address"] for r in nachricht["toRecipients"]] == ["max@example.invalid"] and "ccRecipients" not in nachricht
    assert "attachments" not in nachricht and nachricht["body"]["contentType"] == "HTML"  # seit 1.11.8 als HTML
    assert portal_mails.code_gruppen(CODE) in nachricht["body"]["content"]
    [zeile] = db.scalars(select(EmailDispatch)).all()
    assert (zeile.document_type, zeile.document_id, zeile.status, zeile.channel) == ("portal_code", 7, "gesendet", "graph_oauth2")
    assert zeile.subject == "Ihr Anmeldecode für das Kundenportal" and zeile.created_by_name == "Postbote" and zeile.sent_document_id is None
    assert CODE not in _alles_gespeicherte(db)


def test_link_ueber_graph_ohne_gesendete_elemente(db_session, graph):
    db = db_session
    _configure_graph(db)
    kunde = _kunde(db)
    html_ = portal_mails.link_html(db, kunde, LINK, datetime(2027, 11, 24, 10, 0))
    portal_mails.senden(db, art="portal_link", dokument_id=3, an="max@example.invalid", html_=html_, dispatch_key="portal-link-3-test")
    [anfrage] = graph.anfragen
    assert anfrage["saveToSentItems"] == "false" and anfrage["message"]["subject"] == "Ihr Zugang zum Kundenportal"
    assert f'href="{LINK}"' in anfrage["message"]["body"]["content"] and anfrage["message"]["body"]["contentType"] == "HTML"
    assert "#z=" not in _alles_gespeicherte(db)


def test_andere_mails_weiter_in_gesendete_elemente(db_session, graph):
    db = db_session
    _configure_graph(db)
    dispatch_email(db, dispatch_key="aufgabe-test-0001", document_type="aufgabe", document_id=1, document_number=None, to="a@example.invalid",
                   cc=None, subject="Neue Aufgabe im ERP", body_text="Text")
    [anfrage] = graph.anfragen
    assert anfrage["saveToSentItems"] == "true"


def test_smtp_lehnt_mails_des_portals_ab(db_session, smtp):
    """P1-3: über SMTP gibt es keine Steuerung von „Gesendete Elemente“ -- abgelehnt, bevor etwas geschrieben oder gesendet wird."""
    db = db_session
    _configure_smtp(db)
    kunde = _kunde(db)
    with pytest.raises(ValueError, match="nur über Microsoft 365"):
        portal_mails.senden(db, art="portal_code", dokument_id=8, an="max@example.invalid", html_=portal_mails.code_html(db, kunde, CODE),
                            dispatch_key="portal-code-8")
    assert smtp.sent == [] and db.scalars(select(EmailDispatch)).all() == []


def test_smtp_versand_selbst_lehnt_ab(db_session, smtp):
    """Zweite Sicherung: auch der SMTP-Versand selbst sendet nichts ohne „Gesendete Elemente“ (dispatch_email() lehnt vorher ab)."""
    from app.email_sending import load_smtp_settings, send_message
    db = db_session
    _configure_smtp(db)
    with pytest.raises(ValueError, match="nicht steuern"):
        send_message(load_smtp_settings(db), to=["a@example.invalid"], cc=[], subject="x", body_text="y", gesendete_elemente=False)
    assert smtp.sent == []


def test_art_des_portals_nur_ohne_gesendete_elemente(db_session, graph):
    db = db_session
    _configure_graph(db)
    with pytest.raises(ValueError, match="Gesendete Elemente"):
        dispatch_email(db, dispatch_key="portal-code-9", document_type="portal_code", document_id=9, document_number=None, to="a@example.invalid",
                       cc=None, subject="Ihr Anmeldecode für das Kundenportal", body_text="", body_html="<p>x</p>")
    assert graph.anfragen == [] and db.scalars(select(EmailDispatch)).all() == []


def test_gescheitert_nennt_nichts_vom_text(db_session, monkeypatch, caplog):
    db = db_session
    _configure_graph(db)
    fake = GraphMitAnfrage(fail_status=403, fail_detail="Access is denied.")
    monkeypatch.setattr("app.email_sending.urllib.request.urlopen", fake)
    kunde = _kunde(db)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ValueError) as fehler:
        portal_mails.senden(db, art="portal_code", dokument_id=10, an="max@example.invalid", html_=portal_mails.code_html(db, kunde, CODE),
                            dispatch_key="portal-code-10")
    gruppen = portal_mails.code_gruppen(CODE)
    assert CODE not in str(fehler.value) and CODE not in caplog.text and gruppen not in str(fehler.value) and gruppen not in caplog.text
    [zeile] = db.scalars(select(EmailDispatch)).all()
    assert zeile.status == "fehlgeschlagen" and zeile.error_class and CODE not in _alles_gespeicherte(db)


@pytest.mark.parametrize("werte, erste_zeile", [
    ({}, "Guten Tag, Herr Dr. Muster,"),
    ({"salutation": "Frau", "title": None, "first_name": "Erika", "name": "Frau Erika Muster"}, "Guten Tag, Frau Muster,"),
    ({"salutation": "Firma", "title": None, "first_name": None, "last_name": "Muster Dach GmbH", "name": "Muster Dach GmbH"},
     "Guten Tag, Muster Dach GmbH,"),
])
def test_mails_gesiezt_mit_hinweis_und_absender(db_session, werte, erste_zeile):
    """Seit 1.11.8 als HTML -- den ganzen Wortlaut prüft tests/test_v807_portal_mails_html.py; hier Anrede, Hinweis und Absender je Art."""
    from tests.test_v807_portal_mails_html import absaetze
    db = db_session
    _firma(db)
    kunde = _kunde(db, **werte)
    code = absaetze(portal_mails.code_html(db, kunde, CODE))
    link = absaetze(portal_mails.link_html(db, kunde, LINK, datetime(2027, 11, 23, 23, 30)))  # in Berlin schon der 24.
    for text_ in (code, link):
        assert erste_zeile in text_
        assert any(a.startswith("Wir fragen Sie nie") for a in text_) and any("rufen Sie uns" in a or "Rufen Sie uns" in a for a in text_)
        assert text_[-2:] == ["Muster Bedachung GmbH · Dachweg 1 · 12345 Musterstadt\nTelefon 0123 456789 · www.example.invalid\nImpressum · Datenschutz",
                              "Sitz Musterstadt"]  # seit 1.11.12 die Zeile nach § 35a GmbHG (hier ist nur der Ort gepflegt)
    assert "480 913" in code and any("10 Minuten" in a for a in code)
    assert any("gilt bis 24.11.2027" in a and "nicht weiter" in a for a in link)


# --- Wächter: nur senden() nimmt eine Art des Portals oder den Schalter ----------------------------------------------------------------------------

def _aufrufe(name: str):
    for pfad in sorted([*(ROOT / "app").rglob("*.py"), *(ROOT / "scripts").rglob("*.py")]):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for k in ast.walk(baum):
            if isinstance(k, ast.Call) and (getattr(k.func, "id", None) == name or getattr(k.func, "attr", None) == name):
                yield pfad.relative_to(ROOT).as_posix(), k


def test_nur_senden_nimmt_eine_art_des_portals():
    gefunden = []
    for rel, k in _aufrufe("dispatch_email"):
        woerter = {kw.arg: kw.value for kw in k.keywords}
        art = woerter.get("document_type")
        portal_art = isinstance(art, ast.Constant) and str(art.value).startswith("portal_")
        if rel == "app/portal_mails.py":
            assert portal_art, "senden() nimmt je Art eine feste Versandart"
            gefunden.append(art.value)
            schalter = woerter.get("gesendete_elemente")
            assert isinstance(schalter, ast.Constant) and schalter.value is False, "Mails des Portals ohne „Gesendete Elemente“"
            assert ast.unparse(woerter["subject"]) == f"BETREFF['{art.value}']", "fester Betreff der Art"
        else:
            assert not portal_art, f"{rel}:{k.lineno} -- Mails des Portals nur über app/portal_mails.py::senden()"
            assert "gesendete_elemente" not in woerter, f"{rel}:{k.lineno} -- der Schalter gehört nur den Mails des Portals"
    assert sorted(gefunden) == sorted(PORTAL_TYPES)

