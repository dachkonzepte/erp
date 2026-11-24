"""Mails des Kundenportals als HTML (seit 1.11.8) -- nach dem freigegebenen Entwurf bildgrundlage/entwurf-p1/Portal-Mails.dc.html (Wortlaut verbindlich).

Geprüft: der Wortlaut beider Mails Absatz für Absatz; der Aufbau (Tabellen und Stile in den Tags, höchstens 600 px, keine Bilder, keine Schriften, kein
<style>, nichts von außen, genau die erlaubten Links); jeder eingesetzte Wert maskiert (Angriffe über Kundennamen und Firmendaten); der Link nur in genau
der Form PORTAL_ADRESSE/#z=<Wert>; ohne Telefon fällt nur die Nummer weg; ohne Webseite keine Links auf Impressum und Datenschutz; HTML nur für die Mails des
Portals; das Portal nimmt den Code mit und ohne Leerzeichen. Seit 1.11.12 die kleine Zeile mit den Pflichtangaben nach § 35a GmbHG (Sitz,
Registergericht und -nummer, Geschäftsführer) zuletzt in der Fußzeile -- fehlt ein Feld, fällt nur dieses weg.
"""

from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import portal_mails
from app.email_dispatch import NUR_PORTAL_HTML, dispatch_email
from app.models import Customer, EmailDispatch
from app.portal import pruefwerte
from app.portal.routen import CodeIn
from app.settings import load_general_settings
from tests.test_v321_email_dispatch import _configure_graph, _configure_smtp
from tests.test_v804_portal_mails import GraphMitAnfrage, FakeSMTP

ROOT = Path(__file__).resolve().parents[1]
WERT = "Abc_def-123" + "x" * 32  # 43 Zeichen, die Form von pruefwerte.neuer_wert()
LINK = f"https://kunde.dachkonzepte.gmbh/#z={WERT}"
CODE = "481207"
BIS = datetime(2027, 11, 23, 9, 0)  # naives UTC -> 23.11.2027 in Berlin


# --- Hilfen: HTML lesen ----------------------------------------------------------------------------------------------------------------------------

BLOCK = {"p", "h1", "div", "td", "tr", "table", "body", "html"}


class _Leser(HTMLParser):
    """Absätze als Text (Blöcke getrennt, <br> als Zeilenumbruch), dazu jedes Tag mit seinen Attributen."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.teile, self.tags, self.titel, self._im_titel = [""], [], "", False

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == "br":
            self.teile[-1] += "\n"
        elif tag in BLOCK:
            self.teile.append("")
        self._im_titel = tag == "title"

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in BLOCK:
            self.teile.append("")
        self._im_titel = False

    def handle_data(self, data):
        if self._im_titel:
            self.titel += data
            return
        self.teile[-1] += data


def lesen(html_: str) -> _Leser:
    leser = _Leser()
    leser.feed(html_)
    leser.close()
    return leser


def absaetze(html_: str) -> list[str]:
    """Der sichtbare Text als Liste der Absätze (Leerzeichen am Rand entfernt, leere weg)."""
    return [t.strip() for t in lesen(html_).teile if t.strip()]


# --- Testdaten (erfunden) ---------------------------------------------------------------------------------------------------------------------------

def _kunde(db, **werte) -> Customer:
    felder = dict(name="Herr Dr. Max Muster", salutation="Herr", title="Dr.", first_name="Max", last_name="Muster", email="max@example.invalid")
    felder.update(werte)
    kunde = Customer(**felder)
    db.add(kunde)
    db.commit()
    return kunde


def _firma(db, **werte):
    s = load_general_settings(db)
    felder = dict(company_name="Muster Bedachung GmbH", street="Dachweg 1", postal_code="12345", city="Musterstadt", phone="0123 456789",
                  email="info@example.invalid", website="www.example.invalid", register_court="Amtsgericht Musterstadt", register_number="HRB 99999",
                  managing_director="Erika Beispiel, Max Beispiel")
    felder.update(werte)
    for k, v in felder.items():
        setattr(s, k, v)
    db.commit()


FUSS = "Muster Bedachung GmbH · Dachweg 1 · 12345 Musterstadt\nTelefon 0123 456789 · www.example.invalid\nImpressum · Datenschutz"
PFLICHT = "Sitz Musterstadt · Amtsgericht Musterstadt HRB 99999 · Geschäftsführer: Erika Beispiel, Max Beispiel"  # seit 1.11.12, § 35a GmbHG
GRUSS = "Mit freundlichen Grüßen\nIhr Team der Muster Bedachung GmbH"

LINK_WORTLAUT = [
    "Muster", "Bedachung GmbH",
    "Ihr persönlicher Zugang zum Kundenportal",
    "Guten Tag, Herr Dr. Muster,",
    "wie besprochen haben wir für Sie einen Zugang zu unserem Kundenportal eingerichtet. Dort finden Sie künftig Ihre Unterlagen zu Anfragen und "
    "Aufträgen an einem Ort.",
    "Kundenportal öffnen",
    "Beim ersten Öffnen auf einem Gerät senden wir Ihnen zur Sicherheit einen Code an diese E-Mail-Adresse. Danach bleiben Sie dort 30 Tage angemeldet.",
    "Der Link ist persönlich und gilt bis 23.11.2027. Bitte leiten Sie diese E-Mail nicht weiter.",
    "Wir fragen Sie nie nach einem Passwort oder nach Bankdaten. Unser Kundenportal finden Sie immer unter kunde.dachkonzepte.gmbh. Haben Sie diese "
    "E-Mail nicht erwartet? Dann rufen Sie uns bitte an: 0123 456789.",
    GRUSS,
    FUSS,
    PFLICHT,
]

CODE_WORTLAUT = [
    "Muster", "Bedachung GmbH",
    "Ihr Anmeldecode",
    "Guten Tag, Herr Dr. Muster,",
    "Ihr Code für das Kundenportal lautet:",
    "481 207",
    "Er gilt 10 Minuten und nur in dem Browser, in dem Sie ihn angefordert haben.",
    "Sie haben keinen Code angefordert? Dann hat wohl jemand anderes Ihren Link zum Kundenportal geöffnet. Ohne diesen Code kommt er nicht hinein. "
    "Rufen Sie uns bitte trotzdem an: 0123 456789 – wir sperren den Link und schicken Ihnen einen neuen.",
    "Wir fragen Sie nie nach diesem Code, einem Passwort oder Bankdaten. Geben Sie den Code nur im Kundenportal ein, nie am Telefon.",
    GRUSS,
    FUSS,
    PFLICHT,
]


def _mails(db, kunde=None):
    kunde = kunde or _kunde(db)
    return portal_mails.link_html(db, kunde, LINK, BIS), portal_mails.code_html(db, kunde, CODE)


# --- Wortlaut ---------------------------------------------------------------------------------------------------------------------------------------

def test_wortlaut_wie_im_entwurf(db_session):
    db = db_session
    _firma(db)
    link, code = _mails(db)
    assert absaetze(link) == LINK_WORTLAUT
    assert absaetze(code) == CODE_WORTLAUT
    assert lesen(link).titel == "Ihr Zugang zum Kundenportal" and lesen(code).titel == "Ihr Anmeldecode für das Kundenportal"


def test_ohne_telefon_faellt_nur_die_nummer_weg(db_session):
    db = db_session
    _firma(db, phone="  ")
    link, code = _mails(db)
    a_link, a_code = absaetze(link), absaetze(code)
    assert a_link[8].endswith("Haben Sie diese E-Mail nicht erwartet? Dann rufen Sie uns bitte an.")
    assert a_code[7].endswith("Rufen Sie uns bitte trotzdem an – wir sperren den Link und schicken Ihnen einen neuen.")
    for a in (a_link, a_code):
        assert a[-2:] == ["Muster Bedachung GmbH · Dachweg 1 · 12345 Musterstadt\nwww.example.invalid\nImpressum · Datenschutz", PFLICHT]
        assert "Telefon" not in a[-2]


@pytest.mark.parametrize("webseite, host", [
    ("www.example.invalid", "www.example.invalid"), ("https://www.example.invalid/", "www.example.invalid"),
    ("HTTP://example.invalid", "example.invalid"), (" www.example.invalid ", "www.example.invalid"),
    ("", None), (None, None), ("www.example.invalid/kontakt", None), ("javascript:alert(1)", None), ("ex ample.invalid", None),
    ('www.example.invalid"><script>', None), ("localhost", None), ("https://", None),
])
def test_impressum_und_datenschutz_aus_der_webseite(db_session, webseite, host):
    db = db_session
    _firma(db, website=webseite)
    f = portal_mails.firma(db)
    assert f.webseite == host
    links = [a.get("href") for tag, a in lesen(_mails(db)[1]).tags if tag == "a"]
    if host:
        assert links == [f"https://{host}/impressum", f"https://{host}/datenschutz"]
        assert absaetze(_mails(db)[1])[-2:] == [f"Muster Bedachung GmbH · Dachweg 1 · 12345 Musterstadt\nTelefon 0123 456789 · {host}\n"
                                                 "Impressum · Datenschutz", PFLICHT]
    else:
        assert links == [] and "Impressum" not in absaetze(_mails(db)[1])[-2] and absaetze(_mails(db)[1])[-1] == PFLICHT


def test_absender_ohne_leere_teile(db_session):
    db = db_session
    _firma(db, company_name="Muster", street=None, postal_code=None, city=" ", phone=None, website=None, register_court=None, register_number="",
           managing_director="  ")
    link, code = _mails(db)
    for html_ in (link, code):
        a = absaetze(html_)
        assert a[0] == "Muster" and a[1] != "Bedachung GmbH"  # ein Wort: die Wortmarke hat nur eine Zeile
        assert a[-2:] == ["Mit freundlichen Grüßen\nIhr Team der Muster", "Muster"]  # ohne Pflichtangaben keine Zeile (1.11.12)
        assert "Sitz" not in html_ and "Geschäftsführer" not in html_


# --- Pflichtangaben (seit 1.11.12, § 35a GmbHG) ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("felder, zeile", [
    ({}, PFLICHT),
    ({"city": None}, "Amtsgericht Musterstadt HRB 99999 · Geschäftsführer: Erika Beispiel, Max Beispiel"),
    ({"register_court": " "}, "Sitz Musterstadt · HRB 99999 · Geschäftsführer: Erika Beispiel, Max Beispiel"),
    ({"register_number": None}, "Sitz Musterstadt · Amtsgericht Musterstadt · Geschäftsführer: Erika Beispiel, Max Beispiel"),
    ({"register_court": None, "register_number": ""}, "Sitz Musterstadt · Geschäftsführer: Erika Beispiel, Max Beispiel"),
    ({"managing_director": ""}, "Sitz Musterstadt · Amtsgericht Musterstadt HRB 99999"),
    ({"city": "", "register_court": None, "register_number": None}, "Geschäftsführer: Erika Beispiel, Max Beispiel"),
    ({"city": "  Muster  stadt ", "managing_director": " Erika\n Beispiel "}, "Sitz Muster stadt · Amtsgericht Musterstadt HRB 99999 · Geschäftsführer: "
                                                                            "Erika Beispiel"),
    ({"city": None, "register_court": None, "register_number": None, "managing_director": None}, None),
])
def test_pflichtangaben_fehlt_ein_feld_faellt_nur_dieses_weg(db_session, felder, zeile):
    db = db_session
    _firma(db, **felder)
    for html_ in _mails(db):
        a = absaetze(html_)
        if zeile:
            assert a[-1] == zeile and a[-2].endswith("Impressum · Datenschutz")  # die Fußzeile davor bleibt
        else:
            assert a[-1].endswith("Impressum · Datenschutz") and "Sitz" not in html_ and "Geschäftsführer" not in html_


def test_pflichtangaben_klein_und_zuletzt_in_der_fusszeile(db_session):
    db = db_session
    _firma(db)
    for html_ in _mails(db):
        teil = html_.split("Datenschutz</a>", 1)[1]
        assert teil.startswith('<div style="margin:8px 0 0 0;font-size:11px;line-height:1.5;">' + PFLICHT + "</div></td></tr>")
    _firma(db, street=None, postal_code=None, city=None, phone=None, website=None, company_name="")
    for html_ in _mails(db):  # die Zeile allein in der Fußzeile: ohne Abstand nach oben
        assert '<div style="margin:0;font-size:11px;line-height:1.5;">Amtsgericht Musterstadt HRB 99999 · ' in html_


# --- Aufbau -----------------------------------------------------------------------------------------------------------------------------------------

ERLAUBTE_TAGS = {"html", "head", "meta", "title", "body", "table", "tr", "td", "div", "p", "h1", "a", "br"}


def test_aufbau_nur_tabellen_und_stile_in_den_tags(db_session):
    db = db_session
    _firma(db)
    for html_ in _mails(db):
        assert html_.startswith("<!DOCTYPE html>")
        leser = lesen(html_)
        tags = {tag for tag, _ in leser.tags}
        assert tags <= ERLAUBTE_TAGS, tags - ERLAUBTE_TAGS  # kein img, style, link, script, svg, form, iframe, font …
        for tag, attrs in leser.tags:
            assert set(attrs) <= {"style", "href", "role", "width", "cellpadding", "cellspacing", "border", "align", "lang", "charset", "name",
                                  "content"}, (tag, attrs)
            if tag == "meta":
                assert attrs in ({"charset": "utf-8"}, {"name": "viewport", "content": "width=device-width, initial-scale=1"})
            stil = (attrs.get("style") or "").lower()
            for verboten in ("url(", "@import", "@font-face", "expression(", "javascript:", "position:", "behavior"):
                assert verboten not in stil, (tag, stil)
            for schrift in re.findall(r"font-family:([^;]+)", stil):  # nur Systemschriften
                assert set(re.split(r",\s*", schrift.strip())) <= {"arial", "helvetica", "sans-serif", "consolas", "'courier new'", "monospace"}
            if "width" in attrs:
                assert attrs["width"] in ("100%", "600"), attrs
            for breite in re.findall(r"(?:^|;)\s*(?:max-)?width:\s*(\d+)px", stil):
                assert int(breite) <= 600
        assert "<style" not in html_.lower() and "src=" not in html_.lower() and "<img" not in html_.lower()
        hrefs = [attrs["href"] for tag, attrs in leser.tags if "href" in attrs]
        assert all(h in (LINK, "https://www.example.invalid/impressum", "https://www.example.invalid/datenschutz") for h in hrefs), hrefs
    link, code = _mails(db)
    assert [a["href"] for t, a in lesen(link).tags if t == "a"][0] == LINK
    assert "#z=" not in code  # die Mail mit dem Code trägt keinen Link


# --- Angriffe über eingesetzte Werte ----------------------------------------------------------------------------------------------------------------

BOESE = '<a href="https://boese.invalid">x</a> "><script>alert(1)</script> & \'Anf"ührung'


def test_jeder_eingesetzte_wert_ist_text(db_session):
    db = db_session
    _firma(db, company_name=f"Muster {BOESE}", street=BOESE, city=BOESE, phone=BOESE, register_court=BOESE, register_number=BOESE,
           managing_director=BOESE)
    for werte in ({"salutation": "Herr", "title": BOESE, "last_name": BOESE},
                  {"salutation": "Firma", "title": None, "first_name": None, "last_name": BOESE, "name": BOESE},
                  {"salutation": None, "title": None, "first_name": BOESE, "last_name": "", "name": BOESE}):
        kunde = _kunde(db, **werte)
        for html_ in _mails(db, kunde):
            leser = lesen(html_)
            assert {tag for tag, _ in leser.tags} <= ERLAUBTE_TAGS  # kein eingeschleustes script, kein zweites a mit fremdem Ziel
            assert all("boese" not in (a.get("href") or "") for _, a in leser.tags)
            text_ = "\n".join(absaetze(html_))
            assert BOESE in text_  # als Text, Zeichen für Zeichen
            assert "<script>" not in html_ and 'href="https://boese' not in html_
            assert "&lt;script&gt;" in html_ and "&quot;" in html_ and "&amp;" in html_ and "&#x27;" in html_


@pytest.mark.parametrize("adresse", [
    "", "https://kunde.dachkonzepte.gmbh/", "https://kunde.dachkonzepte.gmbh/#z=", f"http://kunde.dachkonzepte.gmbh/#z={WERT}",
    f"https://KUNDE.dachkonzepte.gmbh/#z={WERT}", f"https://kunde.dachkonzepte.gmbh.boese.invalid/#z={WERT}", f"https://app.dachkonzepte.gmbh/#z={WERT}",
    f"https://kunde.dachkonzepte.gmbh/x#z={WERT}", f"https://kunde.dachkonzepte.gmbh/?a=1#z={WERT}", f"https://kunde.dachkonzepte.gmbh/#z={WERT}x",
    f"https://kunde.dachkonzepte.gmbh/#z={WERT[:-1]}", f'https://kunde.dachkonzepte.gmbh/#z={WERT[:-1]}"', f"https://kunde.dachkonzepte.gmbh/#z={WERT[:-1]} ",
    f"https://kunde.dachkonzepte.gmbh/#z={WERT}\n", f"https://user@kunde.dachkonzepte.gmbh/#z={WERT}", f"https://kunde.dachkonzepte.gmbh:443/#z={WERT}",
    "javascript:alert(1)//#z=" + WERT, f"https://kunde.dachkonzepte.gmbh/#Z={WERT}", None, 42,
])
def test_link_nur_in_genau_dieser_form(db_session, adresse):
    db = db_session
    kunde = _kunde(db)
    with pytest.raises(ValueError) as fehler:
        portal_mails.link_html(db, kunde, adresse, BIS)
    assert str(fehler.value) == portal_mails.LINK_FALSCH  # nennt den Link nicht


def test_link_aus_einem_neuen_wert():
    for _ in range(50):
        wert = pruefwerte.neuer_wert()
        assert portal_mails.link_adresse(wert) == f"{portal_mails.PORTAL_ADRESSE}/#z={wert}"


def test_adresse_des_portals_wie_in_der_einheit():
    """PORTAL_ADRESSE steht fest im Code (F1); die Einheit des Portals bekommt denselben Wert als PORTAL_HERKUNFT."""
    muster = (ROOT / "scripts" / "server" / "portal.env.beispiel").read_text(encoding="utf-8")
    assert f"PORTAL_HERKUNFT={portal_mails.PORTAL_ADRESSE}\n" in muster
    assert portal_mails.PORTAL_HOST == "kunde.dachkonzepte.gmbh"


@pytest.mark.parametrize("code", ["48120", "4812077", "48a207", "", "481 207", None])
def test_code_nur_sechs_ziffern(code):
    with pytest.raises(ValueError):
        portal_mails.code_gruppen(code)


# --- HTML nur für die Mails des Portals -------------------------------------------------------------------------------------------------------------

@pytest.fixture
def graph(monkeypatch):
    fake = GraphMitAnfrage()
    monkeypatch.setattr("app.email_sending.urllib.request.urlopen", fake)
    return fake


def test_html_nur_fuer_die_mails_des_portals(db_session, graph):
    db = db_session
    _configure_graph(db)
    with pytest.raises(ValueError, match=re.escape(NUR_PORTAL_HTML)):  # eine andere Mail als HTML
        dispatch_email(db, dispatch_key="aufgabe-html-0001", document_type="aufgabe", document_id=1, document_number=None, to="a@example.invalid",
                       cc=None, subject="Neue Aufgabe im ERP", body_text="", body_html="<p>x</p>")
    with pytest.raises(ValueError, match=re.escape(NUR_PORTAL_HTML)):  # eine Mail des Portals als Text
        dispatch_email(db, dispatch_key="portal-code-text-1", document_type="portal_code", document_id=1, document_number=None,
                       to="a@example.invalid", cc=None, subject="Ihr Anmeldecode für das Kundenportal", body_text="481207", gesendete_elemente=False)
    with pytest.raises(ValueError, match=re.escape(NUR_PORTAL_HTML)):  # beides
        dispatch_email(db, dispatch_key="portal-code-text-2", document_type="portal_code", document_id=1, document_number=None,
                       to="a@example.invalid", cc=None, subject="Ihr Anmeldecode für das Kundenportal", body_text="x", body_html="<p>x</p>",
                       gesendete_elemente=False)
    assert graph.anfragen == [] and db.scalars(select(EmailDispatch)).all() == []
    dispatch_email(db, dispatch_key="aufgabe-text-0001", document_type="aufgabe", document_id=1, document_number=None, to="a@example.invalid",
                   cc=None, subject="Neue Aufgabe im ERP", body_text="Text")
    assert graph.anfragen[-1]["message"]["body"] == {"contentType": "Text", "content": "Text"}  # alle anderen weiter als Text


def test_graph_bekommt_genau_das_html(db_session, graph):
    db = db_session
    _configure_graph(db)
    _firma(db)
    kunde = _kunde(db)
    html_ = portal_mails.link_html(db, kunde, LINK, BIS)
    portal_mails.senden(db, art="portal_link", dokument_id=4, an="max@example.invalid", html_=html_, dispatch_key="portal-link-4-test")
    [anfrage] = graph.anfragen
    assert anfrage["message"]["body"] == {"contentType": "HTML", "content": html_}
    assert anfrage["saveToSentItems"] == "false"


def test_smtp_sendet_kein_html(db_session, monkeypatch):
    from app.email_sending import load_smtp_settings, send_message
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.during_send = [], None, None
    monkeypatch.setattr("app.email_sending.smtplib.SMTP", FakeSMTP)
    db = db_session
    _configure_smtp(db)
    with pytest.raises(ValueError, match="keine Mails als HTML"):
        send_message(load_smtp_settings(db), to=["a@example.invalid"], cc=[], subject="x", body_text="", body_html="<p>x</p>")
    assert FakeSMTP.sent == []


# --- Das Portal nimmt den Code mit und ohne Leerzeichen ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("eingabe", ["481207", "481 207", " 481 207 ", "481\u00a0207", "481\u202f207", "4 8 1 2 0 7", "481\u2009207"])
def test_portal_nimmt_den_code_mit_und_ohne_leerzeichen(eingabe):
    assert CodeIn.model_validate({"code": eingabe}).code == "481207"


@pytest.mark.parametrize("eingabe", ["481-207", "481\t207", "481\n207", "48120", "481 2077", "１２３４５６", "481 207" + " " * 14, 481207, "４８１ ２０７"])
def test_portal_lehnt_anderes_ab(eingabe):
    with pytest.raises(ValidationError):
        CodeIn.model_validate({"code": eingabe})
