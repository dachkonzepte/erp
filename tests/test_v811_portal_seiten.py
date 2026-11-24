"""Version 1.11.14 (Stufe P1e): die Seiten des Kundenportals nach den Entwürfen bildgrundlage/entwurf-p1/ (Bauplan P1, Abschnitt 5).

    Wege        GET/HEAD /, /s/portal.js, /s/portal.css in OEFFENTLICH; /static (Design-Dateien) nur GET/HEAD; keine anderen
    Seite       beginnt mit <!DOCTYPE html>; kein Inline-Skript, kein style- und kein on…-Attribut, kein javascript: (CSP); Skript und Stil nur von hier,
                mit ?v=<Prüfsumme des Inhalts>; Links nur tel:, mailto:, https://<Webseite>[/impressum|/datenschutz]; noscript mit Kontakt
    Werte       jeder Wert aus den Firmendaten als Text (Angriff über jeden), ungültige E-Mail ohne mailto:, ungültige Webseite ohne Links, Telefon als
                tel:+49…; ohne Telefon und E-Mail keine Kontaktkarte
    Fehler      eine Adresse, die es nicht gibt: Fehlerseite „nicht_gefunden“ mit 404 (unter /api/ JSON); ohne Firmendaten „technisch“ mit 500, im
                Protokoll nur die Klasse
    Speicher    Seite no-store; Skript, Stil und Design-Dateien ein Jahr (immutable), eine Design-Datei, die es nicht gibt, no-store
    Skript      nur Text (textContent) -- kein innerHTML, outerHTML, insertAdjacentHTML, document.write, eval, Function, kein setTimeout mit Text, kein
                document.cookie; der Link geht aus der Adresse, bevor eine Anfrage hinausgeht; nur Wege des Portals; die Fälle der Fehlerseite
    Wortlaut    jeder Satz der Entwürfe steht in Seite oder Skript
    gemessen    im Browser gegen den echten Dienst unter PostgreSQL: scripts/klicktest_portal_seiten.py (Bilder aller Zustände)
"""

from __future__ import annotations

import hashlib
import logging
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.pool import StaticPool

from app import portal_mails
from app.portal import routen, seiten, tabellen
from app.portal.main import erzeugen
from tests.aufraeumen import wegwerf_engine
from tests.test_v801_portal_dienst import EIGEN, HERKUNFT, _einstellungen

ROOT = Path(__file__).resolve().parent.parent
ORDNER = ROOT / "app" / "portal" / "seiten"
JS = (ORDNER / "portal.js").read_text(encoding="utf-8")
CSS = (ORDNER / "portal.css").read_text(encoding="utf-8")
BOESE = '<a href="https://boese.invalid">x</a> "><script>alert(1)</script> & \'Anf"ührung'
FIRMA = dict(id=1, company_name="Muster Bedachung GmbH", street="Dachweg 1", postal_code="12345", city="Musterstadt", phone="0123 456789",
             email="info@example.invalid", website="www.example.invalid")


def _client(**firma):
    engine = wegwerf_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)  # am Ende des Tests geschlossen
    tabellen.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(insert(tabellen.general_settings).values(**{**FIRMA, **firma}))
    app = erzeugen(_einstellungen(), engine=engine, pruefen=False)
    return TestClient(app, base_url=HERKUNFT), app, engine


@pytest.fixture
def dienst():
    client, app, engine = _client()
    with client:
        yield client, app, engine


class _Leser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.text = [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        self.text.append(data)


def lesen(html_: str) -> _Leser:
    leser = _Leser()
    leser.feed(html_)
    return leser


# --- Wege und Speicher ----------------------------------------------------------------------------------------------------------------------

def test_wege_der_seite_oeffentlich_und_nur_lesend():
    pfade = {r.path: r.methods for r in routen.router.routes if isinstance(r, APIRoute)}
    for pfad in ("/", "/s/portal.js", "/s/portal.css"):
        assert pfad in routen.OEFFENTLICH and pfade[pfad] == {"GET", "HEAD"}


def test_seite_skript_stil_und_design(dienst):
    client, app, _e = dienst
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"] == "text/html; charset=utf-8" and r.headers["cache-control"] == "no-store"
    assert r.text.startswith("<!DOCTYPE html>") and "require-trusted-types-for 'script'" in r.headers["content-security-policy"]
    assert r.headers["x-robots-tag"] == "noindex"
    assert client.head("/").status_code == 200
    assert client.post("/", headers=EIGEN).status_code == 405
    v = app.app.state.seiten.version
    for name, typ in (("portal.js", "text/javascript; charset=utf-8"), ("portal.css", "text/css; charset=utf-8")):
        a = client.get(f"/s/{name}")
        inhalt = (ORDNER / name).read_bytes()
        assert (a.status_code, a.headers["content-type"], a.content) == (200, typ, inhalt)
        assert a.headers["cache-control"] == seiten.DAUERHAFT and a.headers["x-content-type-options"] == "nosniff"
        assert f"/s/{name}?v={hashlib.sha256(inhalt).hexdigest()[:10]}" in r.text and v[name] == hashlib.sha256(inhalt).hexdigest()[:10]
    d = client.get(f"/static/ds/ds.css?v={v['ds.css']}")
    assert (d.status_code, d.headers["cache-control"], d.headers["content-type"]) == (200, seiten.DAUERHAFT, "text/css; charset=utf-8")
    assert f"/static/ds/ds.css?v={v['ds.css']}" in r.text
    schrift = client.get("/static/ds/schriften/ibm-plex-sans-latin-400-normal.woff2")
    assert (schrift.status_code, schrift.headers["cache-control"]) == (200, seiten.DAUERHAFT)
    fehlt = client.get("/static/ds/gibt-es-nicht.css")
    assert (fehlt.status_code, fehlt.headers["cache-control"]) == (404, "no-store")
    assert client.post("/static/ds/ds.css", headers=EIGEN).status_code in (404, 405)


def test_eine_adresse_die_es_nicht_gibt_ist_die_fehlerseite(dienst):
    client, _a, _e = dienst
    for pfad in ("/gibt-es-nicht", "/login", "/customers/1", "/s/andere.js"):
        r = client.get(pfad)
        assert (r.status_code, r.headers["content-type"], r.headers["cache-control"]) == (404, "text/html; charset=utf-8", "no-store"), pfad
        assert '<body data-fall="nicht_gefunden">' in r.text
    assert client.head("/gibt-es-nicht").status_code == 404
    j = client.get("/api/gibt-es-nicht")
    assert (j.status_code, j.json()) == (404, {"fehler": "nicht_gefunden"})
    assert client.post("/gibt-es-nicht", headers=EIGEN).json() == {"fehler": "nicht_gefunden"}


def test_ohne_firmendaten_technisch_ohne_details(dienst, monkeypatch, caplog):
    client, app, _e = dienst

    def kaputt():
        raise RuntimeError("Passwort-im-Text")
    monkeypatch.setattr(app.app.state.db, "kontakt", kaputt)
    with caplog.at_level(logging.ERROR, logger="dk_portal"):
        r = client.get("/")
    assert r.status_code == 500 and '<body data-fall="technisch">' in r.text and "Passwort-im-Text" not in r.text
    assert "Passwort-im-Text" not in caplog.text and "RuntimeError" in caplog.text
    assert "So erreichen Sie uns" not in r.text  # ohne Firmendaten kein Kontakt


# --- Aufbau der Seite (CSP) -----------------------------------------------------------------------------------------------------------------

def test_seite_ohne_inline_skript_stil_und_handler(dienst):
    client, _a, _e = dienst
    html_ = client.get("/").text
    leser = lesen(html_)
    skripte = [a for t, a in leser.tags if t == "script"]
    assert len(skripte) == 1 and re.fullmatch(r"/s/portal\.js\?v=[0-9a-f]{10}", skripte[0]["src"])
    assert html_.count("<script") == 1 and "</script>" in html_  # nur das eine, ohne Inhalt
    assert re.search(r"<script[^>]*>\s*</script>", html_)
    for tag, attrs in leser.tags:
        assert "style" not in attrs, tag
        assert not any(k.startswith("on") for k in attrs), (tag, attrs)
        for k in ("href", "src", "action"):
            assert not (attrs.get(k) or "").lower().startswith(("javascript:", "data:", "//")), (tag, attrs)
    assert "<style" not in html_.lower() and "<iframe" not in html_.lower() and "<form" not in html_.lower()
    css = [a["href"] for t, a in leser.tags if t == "link" and a.get("rel") == "stylesheet"]
    assert len(css) == 2 and css[0].startswith("/static/ds/ds.css?v=") and css[1].startswith("/s/portal.css?v=")
    hrefs = sorted({a["href"] for t, a in leser.tags if t == "a"})
    assert hrefs == ["https://www.example.invalid", "https://www.example.invalid/datenschutz", "https://www.example.invalid/impressum",
                     "mailto:info@example.invalid", "tel:+49123456789"], hrefs


def test_noscript_mit_kontakt_und_alle_abschnitte_verborgen(dienst):
    client, _a, _e = dienst
    html_ = client.get("/").text
    noscript = html_.split("<noscript>", 1)[1].split("</noscript>", 1)[0]
    assert "JavaScript ist ausgeschaltet" in noscript and "Bitte schalten Sie JavaScript ein, um das Kundenportal zu nutzen." in noscript
    assert 'href="tel:+49123456789"' in noscript
    for kennung in ("seite-a", "seite-b", "seite-c", "seite-d", "seite-e"):
        assert re.search(rf'<section[^>]*id="{kennung}"[^>]*\bhidden\b', html_), kennung
    assert re.search(r'id="kopf-abmelden"[^>]*\bhidden\b', html_)


# --- Werte aus den Firmendaten --------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("feld", ["company_name", "street", "postal_code", "city", "phone", "email", "website"])
def test_jeder_wert_als_text(feld):
    client, _a, engine = _client(**{feld: BOESE})
    with client:
        html_ = client.get("/").text
    leser = lesen(html_)
    assert "<script>alert" not in html_ and 'href="https://boese' not in html_
    assert all("boese" not in (a.get("href") or "") for _, a in leser.tags)
    assert {t for t, _ in leser.tags} <= {"html", "head", "meta", "title", "link", "script", "body", "header", "div", "span", "svg", "polygon", "path",
                                          "rect", "circle", "button", "main", "noscript", "section", "h1", "h2", "p", "a", "br", "strong", "label",
                                          "input", "ul", "li", "footer", "dialog"}
    if feld in ("company_name", "street", "postal_code", "city", "phone"):
        assert BOESE in "".join(leser.text)  # als Text, Zeichen für Zeichen (oder ganz weggelassen wie bei E-Mail und Webseite)


@pytest.mark.parametrize("eingabe, erwartet", [
    ("0123 456789", "+49123456789"), ("02451 9433606", "+4924519433606"), ("+49 2451 9433606", "+4924519433606"), ("0049 (2451) 94336-06", "+4924519433606"),
    ("02451/9433606", "+4924519433606"), ("  ", None), (None, None), ("12345", None), ("9433606", None), ("<script>", None), ("0 12", None),
])
def test_telefon_als_tel_link(eingabe, erwartet):
    assert seiten.tel_link(eingabe) == erwartet


@pytest.mark.parametrize("webseite", ["www.example.invalid", "https://www.example.invalid/", "HTTP://example.invalid", " www.example.invalid ", "",
                                      None, "www.example.invalid/kontakt", "javascript:alert(1)", "ex ample.invalid", 'www.example.invalid"><script>',
                                      "localhost", "https://"])
def test_webseite_wie_in_den_mails(webseite):
    assert seiten.webseite_host(webseite) == portal_mails.webseite_host(webseite)


def test_ungueltige_email_und_webseite_ohne_links():
    client, _a, engine = _client(email="info@example.invalid?subject=x", website="javascript:alert(1)", phone=None)
    with client:
        html_ = client.get("/").text
    hrefs = [a.get("href") for t, a in lesen(html_).tags if t == "a"]
    assert hrefs == []  # kein mailto:, kein tel:, keine Webseite, kein Impressum
    assert "So erreichen Sie uns" not in html_  # ohne Telefon und gültige E-Mail keine Kontaktkarte


def test_telefon_ohne_vorwahl_nur_als_text():
    client, _a, engine = _client(phone="9433606")
    with client:
        html_ = client.get("/").text
    assert "tel:" not in html_ and "9433606" in html_


def test_firma_mit_einem_wort_und_ohne_namen():
    f = seiten.firma({"company_name": "Muster", "phone": "0123 456789"})
    assert (f.marke, f.rest, f.hat_kontakt) == ("Muster", "", True)
    leer = seiten.firma(None)
    assert (leer.name, leer.marke, leer.hat_kontakt, leer.impressum) == ("", "", False, None)
    s = seiten.Seiten()
    assert "<title>Kundenportal</title>" in s.seite(None) and "Kundenportal – Muster" in s.seite({"company_name": "Muster"})
    with pytest.raises(ValueError):
        s.seite(None, "erfunden")


# --- Skript ---------------------------------------------------------------------------------------------------------------------------------

def _ohne_kommentare(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$|(?<=[;{}),])\s*//.*$", "", js)


def test_skript_nur_text_keine_gefaehrlichen_aufrufe():
    code = _ohne_kommentare(JS)
    for verboten in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "Function(", "document.cookie", "localStorage",
                     "srcdoc", ".src =", "setAttribute('href'", "setAttribute(\"href\"", "location.href =", "location.assign", "postMessage"):
        assert verboten not in code, verboten
    assert not re.search(r"setTimeout\(\s*['\"]", code) and not re.search(r"setInterval\(\s*['\"]", code)
    assert "textContent" in code
    assert "'use strict'" in code


def test_skript_nur_wege_des_portals():
    wege = set(re.findall(r"'(/api/[a-z/]+)'", JS))
    assert wege == {"/api/link", "/api/sitzung/weiter", "/api/code", "/api/code/stand", "/api/code/pruefen", "/api/willkommen", "/api/abmelden"}
    assert wege <= routen.OEFFENTLICH | routen.VORSTUFE | routen.SITZUNG


def test_link_aus_der_adresse_bevor_eine_anfrage_hinausgeht():
    start = JS[JS.index("function start()"):]
    assert start.index("history.replaceState") < start.index("linkPruefen(wert)") < start.index("ohneLink()")
    assert "'X-Portal-Link': wert" in JS  # der Link nur in der Kopfzeile, nie in Adresse oder Körper
    # im Speicher nur Schritt, Anzeige und seit 1.11.16 der Zeitpunkt der Anforderung (für die 30 Sekunden und die 60 Sekunden nach einem Neuladen)
    assert "sessionStorage" in JS and re.search(r"JSON\.stringify\(\{ schritt: schritt, adresse: adresse, seit: angefordert \}\)", JS)


def test_faelle_der_fehlerseite():
    faelle = set(re.findall(r"^\s{4}([a-z_]+): \[", JS[JS.index("var FEHLER = {"):JS.index("var TEXT = {")], flags=re.M))
    assert faelle == {"link", "lesezeichen", "abgemeldet", "zu_viele", "nicht_gefunden", "technisch", "wartung"}
    assert set(seiten.FAELLE) <= faelle


# --- Wortlaut der Entwürfe ------------------------------------------------------------------------------------------------------------------

WORTLAUT = [
    "Ihr Zugang wird geprüft …", "Einen Moment bitte.", "Willkommen im Kundenportal",
    "Zum Schutz Ihrer Unterlagen senden wir Ihnen beim ersten Öffnen auf einem Gerät einen Code per E-Mail.", "Der Code geht an", "Code senden",
    "Danach bleiben Sie auf diesem Gerät 30 Tage angemeldet.", "Wir fragen Sie nie nach einem Passwort oder nach Bankdaten.", "Code gesendet an",
    "Sehen Sie bitte auch im Spam-Ordner nach.", "Code eingeben", "Code aus der E-Mail", "6 Ziffern", "Der Code gilt 10 Minuten.", "Anmelden",
    "Neuen Code senden", "Dieser Code stimmt nicht. Noch ", "Neuen Code anfordern", "Dieser Code gilt nicht mehr.",
    "Er ist abgelaufen, wurde schon benutzt oder zu oft falsch eingegeben. Der neue Code geht wieder an", "Der neue Code gilt wieder 10 Minuten.",
    "Wird gesendet …", "Wird geprüft …",
    "Der Code konnte gerade nicht gesendet werden. Bitte versuchen Sie es gleich noch einmal oder rufen Sie uns an.", "Ein neuer Code ist in ",
    "Schön, dass Sie da sind. Hier finden Sie bald alle Unterlagen zu Ihren Aufträgen an einem Ort.", "Was Sie hier bald finden", "In Vorbereitung",
    "Angebote ansehen und digital annehmen", "Mit Unterschrift am Handy oder am Rechner.", "Auftragsbestätigungen und Verträge", "Immer die gültige Fassung.",
    "Rechnungen mit Zahlungsstand", "Auf einen Blick: offen oder bezahlt.", "Termine für Ihre Baustelle", "Wann wir bei Ihnen sind.",
    "Abnahme- und Wartungsprotokolle", "Zum Nachlesen und Herunterladen.", "Dokumente und Fotos",
    "Datenblätter der verbauten Produkte, Bilder Ihrer Baustelle und weitere Unterlagen.", "Bis dahin erhalten Sie Ihre Unterlagen wie gewohnt per E-Mail oder Post.",
    "So erreichen Sie uns", "Ihre Anmeldung", "Sie bleiben auf diesem Gerät angemeldet, solange Sie das Kundenportal mindestens alle 30 Tage öffnen.",
    "Auf allen Geräten abmelden", "Auf allen Geräten abmelden?",
    "Sie werden auf diesem und allen anderen Geräten abgemeldet. Zum erneuten Anmelden öffnen Sie den Link aus unserer E-Mail und fordern einen neuen Code an.",
    "Überall abmelden", "Abbrechen", "Dieser Link funktioniert nicht", "Bitte nutzen Sie den Link aus unserer letzten E-Mail. Gern senden wir Ihnen auch einen neuen.",
    "Bitte über den Link anmelden", "Öffnen Sie das Kundenportal über den Link aus unserer E-Mail.", "Sie sind abgemeldet",
    "Zum erneuten Anmelden öffnen Sie den Link aus unserer E-Mail.", "Zu viele Versuche", "Bitte versuchen Sie es in einigen Minuten erneut.",
    "Diese Seite gibt es nicht", "Gerade klappt etwas nicht", "Bitte versuchen Sie es später erneut oder rufen Sie uns an.", "Gleich wieder da",
    "Das Kundenportal ist in wenigen Minuten wieder erreichbar.", "JavaScript ist ausgeschaltet", "Bitte schalten Sie JavaScript ein, um das Kundenportal zu nutzen.",
    "Impressum", "Datenschutz", " anrufen",
    "Der Versand dauert länger als sonst. Der Code kann noch einige Minuten brauchen – sehen Sie bitte auch im Spam-Ordner nach.",  # seit 1.11.16
]


def test_wortlaut_der_entwuerfe(dienst):
    client, _a, _e = dienst
    alles = client.get("/").text + JS
    fehlt = [s for s in WORTLAUT if s not in alles]
    assert fehlt == []


def test_stil_ohne_fremde_quellen():
    assert "@import" not in CSS and "url(" not in CSS and "expression(" not in CSS
    assert "prefers-reduced-motion" in CSS


def test_versand_dauert_laenger_zeiten():
    """Seit 1.11.16 (Antwort P1e-4): nach 30 Sekunden weiter zu C mit Hinweis, weiter fragen (alle 5 Sekunden), gescheitert erst nach 10 Minuten oder auf
    Meldung des Postboten; „Neuen Code senden“ 60 Sekunden nach der Anforderung. Das Verhalten prüft scripts/klicktest_portal_seiten.py mit vorgestellter Uhr."""
    for zeile in ("var LANGSAM_MS = 30000;", "var AUFTRAG_MS = 600000;", "var STAND_MS = 1000;", "var STAND_LANGSAM_MS = 5000;", "var CODE_SEKUNDEN = 60;"):
        assert zeile in JS, zeile
    assert "STAND_VERSUCHE" not in JS  # bis 1.11.15: nach 30 Versuchen „gescheitert“
    assert "angefordert + CODE_SEKUNDEN * 1000 - Date.now()" in JS


def test_hinweis_versand_dauert_in_den_farben_fuer_fortschritt(dienst):
    """Seit 1.11.16: der Hinweis in den Info-Farben des Design-Systems (--ds-info: „läuft, Fortschritt“) mit Uhr, verborgen bis das Skript ihn zeigt."""
    client, _a, _e = dienst
    html_ = client.get("/").text
    assert re.search(r'<div class="hinweis info" id="c-dauert" role="status" hidden><svg', html_)
    regel = re.search(r"\.hinweis\.info \{([^}]*)\}", CSS).group(1)
    assert "var(--ds-info-hell)" in regel and "var(--ds-info-text)" in regel
