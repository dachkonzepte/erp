"""Klicktest: die Seiten des Kundenportals (1.11.14, Stufe P1e; Bauplan P1, Abschnitt 5; Entwürfe bildgrundlage/entwurf-p1/).

Gegen den echten Portal-Dienst (app.portal.main:erzeugen) in einem eigenen Prozess -- das Portal läuft nur gegen PostgreSQL: ein Wegwerf-Schema
pgklick_<…> auf ERP_TEST_POSTGRES_URL (nie public, Regel 27), der Dienst als lokale Testrolle dkportal_test mit genau den Rechten aus
app/portal/rechte.py (P1-11), die Adresse http://localhost:<Port> (http nur lokal mit ERP_ENV test; Chrome nimmt Secure-Cookies von localhost).
Der Postbote (app/portal_postbote.py) läuft in diesem Prozess als Benutzer des ERP und schickt die Codes an eine Attrappe von Microsoft 365
(ERP_TEST_GRAPH, nur test/development, nur 127.0.0.1); der Klicktest liest den Code aus der Mail und tippt ihn ein -- wie der Kunde.

    Ablauf 1 (Herr Dr. Muster)  A „Ihr Zugang wird geprüft …“ (Antwort zurückgehalten), der Link verschwindet aus der Adresse -> B mit verdeckter
                                Adresse -> „Wird gesendet …“ -> C „Code gesendet an …“ mit „Neuen Code senden · in 1:00“ -> falscher Code „Noch 4
                                Versuche“ -> richtiger Code mit Leerzeichen („Wird geprüft …“) -> D „Guten Tag Herr Dr. Muster“, kein Cookie im
                                Skript lesbar -> neu laden: wieder D -> „Auf allen Geräten abmelden?“ (Abbrechen, dann überall) -> E „Sie sind
                                abgemeldet“ -> neu laden: E „Bitte über den Link anmelden“
    Ablauf 2 (Frau Muster)      B -> C -> neu laden ohne Link: C geht weiter (Speicher des Tabs) -> vier falsche („Noch 1 Versuch.“) -> fünfter
                                falsch: „Neuen Code anfordern“
    Ablauf 3 (Firma)            Versand scheitert (Attrappe antwortet 403) -> B „Der Code konnte gerade nicht gesendet werden …“ mit Telefon;
                                Bremse (Ersatz-Antwort 429): „Ein neuer Code ist in 12 Minuten wieder möglich.“, Knopf gesperrt
    Ablauf 4 (ohne Anrede)      bis D „Guten Tag Alex Beispiel“ -> „Abmelden“ oben -> E „Sie sind abgemeldet“
    Ablauf 5 (seit 1.11.16)     der Postbote hält an: B „Wird gesendet …“ -> die Uhr des Browsers 31 s weiter -> C „Der Versand dauert länger als sonst …“,
                                „Neuen Code senden · in 0:29“ -> neu laden: wieder C mit dem Hinweis -> der Postbote sendet: „Code gesendet an …“
    Ablauf 6 (seit 1.11.16)     der Postbote hält an, die Uhr 31 s und dann 10 Minuten weiter: C „Der Code konnte gerade nicht gesendet werden …“ mit Telefon
    Fehlerseite E               unbekannter, gesperrter und abgelaufener Link: dieselbe Seite; 429, 500, 502 (Ersatz-Antwort im Browser -- die
                                echten liefern test_v802 bzw. nginx); /gibt-es-nicht (404 vom Dienst); ohne JavaScript (noscript)
    Fuß (seit 1.11.47)          in jedem Zustand A bis E und jeder hellen Ansicht Impressum und Datenschutz als sichtbare Links auf die Webseite der
                                Unternehmensdaten, auch ohne JavaScript (Pflicht -- ohne gültige Webseite zeigt das Portal nur „technisch“, test_v837)
    Bilder                      jeder Zustand in 390 px hell und dunkel, 1280 px hell und dunkel, 360 px hell (Ordner der Screenshots, Namen
                                <zustand>_<breite>_<hell|dunkel>.png); 360 und 390 px ohne Überlauf; nirgends eine Verletzung der CSP, kein JS-Fehler

AUFRUF (aus dem Projektordner; braucht ERP_TEST_POSTGRES_URL und die Testrolle dkportal_test):

    .venv\\Scripts\\python.exe scripts\\klicktest_portal_seiten.py [--arbeitsordner PFAD] [--chrome PFAD] [--zeitlimit SEK] [--offen-lassen]

Rückgabecode wie scripts/cdp_klicktest.py (0 wie erwartet, 1 Abweichung, 2 nicht gestartet, 3 Zeitlimit). Dauer etwa zwei Minuten.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import (  # noqa: E402
    GEGENPROBE_MARKER, MARKER, ROOT, ZEITLIMIT_GEGENPROBE, Wachhund, _chrome_pfad, _chrome_port, _freier_port, _lauf, beenden, gegenprobe_im_code,
    klicktest_ordner,
)

if str(ROOT) not in sys.path:  # auch im Kindprozess (--portal-server): das Paket app
    sys.path.insert(0, str(ROOT))

TESTROLLE = "dkportal_test"
MAILS: list[dict] = []
GRAPH = {"fehler": False}  # True: sendMail antwortet 403 (Versand scheitert)
POSTBOTE_HAELT = threading.Event()  # seit 1.11.16: gesetzt erledigt der Postbote nichts (der Code wartet)
LINKS = {name: secrets.token_urlsafe(32) for name in ("muster", "erika", "firma", "alex", "bremse", "gesperrt", "alt", "langsam", "zehn")}
UNBEKANNT = secrets.token_urlsafe(32)
BILDER = {"an": True}  # unter einer Gegenprobe (Regel 24: höchstens 2 min) ohne Bilder -- die Prüfungen bleiben
# seit 1.11.47: der Fuß jeder Seite -- Text, Ziel und sichtbar je Link (Impressum und Datenschutz sind Pflicht)
FUSS = ("[...document.querySelectorAll('footer.fuss a')].map(a=>[a.textContent,a.getAttribute('href'),"
        "a.getClientRects().length>0&&getComputedStyle(a).visibility!=='hidden'])")
WEBSEITE = "www.example.invalid"
FUSS_SOLL = [["Impressum", f"https://{WEBSEITE}/impressum", True], ["Datenschutz", f"https://{WEBSEITE}/datenschutz", True]]
ANSICHTEN = [(390, 844, True, "light"), (390, 844, True, "dark"), (1280, 900, False, "light"), (1280, 900, False, "dark"), (360, 740, True, "light")]


# --- Attrappe von Microsoft 365 --------------------------------------------------------------------------------------------------------------

class _Graph(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _antwort(self, status: int, koerper: bytes = b"", typ: str = "application/json"):
        self.send_response(status)
        if koerper:
            self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(koerper)))
        self.end_headers()
        self.wfile.write(koerper)

    def do_POST(self):
        koerper = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path.endswith("/oauth2/v2.0/token"):
            return self._antwort(200, json.dumps({"access_token": "attrappe", "token_type": "Bearer", "expires_in": 3600}).encode())
        if self.path.endswith("/sendMail"):
            if GRAPH["fehler"]:
                return self._antwort(403, json.dumps({"error": {"code": "ErrorAccessDenied", "message": "Access is denied."}}).encode())
            MAILS.append(json.loads(koerper))
            return self._antwort(202)
        return self._antwort(404)


def _graph_starten() -> int:
    port = _freier_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), _Graph)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port


# --- Datenbank -------------------------------------------------------------------------------------------------------------------------------

def _engine(pg_url: str, schema: str, rolle: str | None = None):
    from sqlalchemy import create_engine
    optionen = f"-csearch_path={schema}" + (f" -crole={rolle}" if rolle else "")
    return create_engine(pg_url, connect_args={"options": optionen, "application_name": schema}, pool_pre_ping=True)


def befuellen(erp) -> dict:
    """Wegwerf-Schema: Tabellen und Funktionen (create_all), Revision, Rechte der Testrolle, Grunddaten, Firmendaten (erfunden), Modul an,
    Microsoft 365 als Attrappe, je Ablauf ein Kunde mit Zugang und bekanntem Link."""
    from datetime import timedelta

    from sqlalchemy import text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app import grunddaten
    from app.berlin_time import utc_jetzt
    from app.database import Base
    from app.email_sending import load_smtp_settings, update_graph_settings
    from app.models import Customer, EnabledModule, PortalZugang
    from app.portal import pruefwerte, rechte
    from app.portal.main import kopf_der_migrationen
    from app.settings import load_general_settings

    Base.metadata.create_all(erp)
    with erp.begin() as c:
        aktuell = c.execute(text("SELECT current_schema()")).scalar()
        c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        c.execute(text("INSERT INTO alembic_version VALUES (:k)"), {"k": kopf_der_migrationen()})
        rechte.setzen(c, rolle=TESTROLLE, schema=aktuell)
    with Session(erp) as db:
        grunddaten.anlegen(db)
        db.commit()
        s = load_general_settings(db)
        s.company_name, s.street, s.postal_code, s.city = "Muster Bedachung GmbH", "Dachweg 1", "12345", "Musterstadt"
        s.phone, s.email, s.website = "0123 456789", "info@example.invalid", WEBSEITE
        db.add(EnabledModule(module_key="kundenportal", enabled=True))
        m = load_smtp_settings(db)
        m.send_method = "graph_oauth2"
        update_graph_settings(db, tenant_id="mandant-attrappe", client_id="anwendung-attrappe", sender_mailbox="buero@example.invalid",
                              client_secret="geheim-attrappe")
        jetzt = utc_jetzt()
        kunden = {
            "muster": dict(name="Herr Dr. Max Muster", salutation="Herr", title="Dr.", first_name="Max", last_name="Muster", email="max@example.invalid"),
            "erika": dict(name="Frau Erika Muster", salutation="Frau", first_name="Erika", last_name="Muster", email="erika@example.invalid"),
            "firma": dict(name="Muster Dach GmbH", salutation="Firma", last_name="Muster Dach GmbH", email="firma@example.invalid"),
            "alex": dict(name="Alex Beispiel", first_name="Alex", last_name="Beispiel", email="alex@example.invalid"),
            "bremse": dict(name="Herr Bernd Bremse", salutation="Herr", first_name="Bernd", last_name="Bremse", email="bernd@example.invalid"),
            "gesperrt": dict(name="Herr Gerd Gesperrt", salutation="Herr", first_name="Gerd", last_name="Gesperrt", email="gerd@example.invalid"),
            "alt": dict(name="Frau Alma Alt", salutation="Frau", first_name="Alma", last_name="Alt", email="alma@example.invalid"),
            "langsam": dict(name="Herr Lars Langsam", salutation="Herr", first_name="Lars", last_name="Langsam", email="lars@example.invalid"),
            "zehn": dict(name="Frau Zoe Zehn", salutation="Frau", first_name="Zoe", last_name="Zehn", email="zoe@example.invalid"),
        }
        for name, werte in kunden.items():
            k = Customer(portal_aktiv=True, **werte)
            db.add(k)
            db.flush()
            z = PortalZugang(customer_id=k.id, email=werte["email"], email_anzeige=werte["email"][0] + "***@example.invalid",
                             link_sha256=pruefwerte.link(LINKS[name]), link_erzeugt_am=jetzt, gueltig_bis=jetzt + timedelta(days=200),
                             angelegt_am=jetzt, angelegt_von_name="Klicktest")
            if name == "gesperrt":
                z.gesperrt_am, z.gesperrt_grund, z.gesperrt_von_name = jetzt, "Klicktest", "Klicktest"
            if name == "alt":
                z.gueltig_bis = jetzt - timedelta(days=1)
            db.add(z)
        db.commit()
    return {"links": LINKS, "unbekannt": UNBEKANNT}


class Postbote:
    """Der Postbote des ERP in diesem Prozess: erledigt alle 0,3 s die wartenden Aufträge (app/portal_postbote.py::alle())."""

    def __init__(self, erp):
        self.erp, self.halt, self.fehler = erp, threading.Event(), []
        self.faden = threading.Thread(target=self._laufen, daemon=True)

    def _laufen(self):
        from sqlalchemy.orm import Session

        from app import portal_postbote
        while not self.halt.wait(0.3):
            if POSTBOTE_HAELT.is_set():
                continue
            try:
                with Session(self.erp) as db:
                    portal_postbote.alle(db)
            except Exception as exc:  # noqa: BLE001
                self.fehler.append(type(exc).__name__)


def _portal_server(port: int) -> None:
    """Kindprozess: der Portal-Dienst als Testrolle im Wegwerf-Schema (PORTAL_KLICK_SCHEMA), ohne Startprüfung (das Schema hat keine Migrationen)."""
    import uvicorn

    from app.portal.einstellungen import aus_umgebung
    from app.portal.main import erzeugen
    schema = os.environ["PORTAL_KLICK_SCHEMA"]
    if not re.fullmatch(r"pgklick_[0-9a-f]{8}", schema):
        raise SystemExit("kein Schema des Klicktests")
    engine = _engine(os.environ["ERP_TEST_POSTGRES_URL"], schema, TESTROLLE)
    uvicorn.run(erzeugen(aus_umgebung(), engine=engine, pruefen=False), host="127.0.0.1", port=port, log_level="warning")


def _bereit(port: int, timeout: float = 60) -> bool:
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Host": f"localhost:{port}"}), timeout=2)
            if r.status == 200:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    return False


# --- Hilfen im Browser ----------------------------------------------------------------------------------------------------------------------

ERSATZ = """(()=>{if(window.__dkErsatz)return;const E=window.__dkErsatz={regeln:(window.__dkErsatzVorab||[]).slice(),csp:0};
document.addEventListener('securitypolicyviolation',()=>{E.csp++});
const f=window.fetch;
window.fetch=function(input,init){
  if(window.__dkErsatzVorab){E.regeln.push(...window.__dkErsatzVorab);window.__dkErsatzVorab=null}
  const url=typeof input==='string'?input:((input&&input.url)||String(input));
  const methode=String((init&&init.method)||'GET').toUpperCase();
  const r=E.regeln.find(x=>x.anzahl>0&&new RegExp(x.muster).test(url)&&(!x.methode||x.methode===methode));
  if(!r)return f.apply(this,arguments);
  r.anzahl--;
  return Promise.resolve(new Response(JSON.stringify(r.koerper||{}),{status:r.status,headers:{'Content-Type':'application/json'}}));
};})()"""

# seit 1.11.16: die Uhr der Seite (Date.now -- damit rechnet das Skript des Portals die 30 Sekunden, 10 Minuten und 60 Sekunden) lässt sich vorstellen;
# der Versatz bleibt über ein Neuladen im Speicher des Tabs
ZEIT = """(()=>{if(window.__dkZeit)return;const e=Date.now.bind(Date);let v=0;try{v=+(sessionStorage.getItem('__dkVersatz')||0)}catch(x){}
window.__dkZeit={weiter(ms){v+=ms;try{sessionStorage.setItem('__dkVersatz',String(v))}catch(x){}return v}};Date.now=()=>e()+v;})()"""

SICHTBAR = "(id=>{const e=document.getElementById(id);return !!e&&!e.hidden&&e.offsetParent!==null})"


def sichtbar(kennung: str) -> str:
    return f"{SICHTBAR}({json.dumps(kennung)})"


def text_von(kennung: str) -> str:
    return f"(document.getElementById({json.dumps(kennung)})||{{}}).textContent"


async def _vorab(tab, js: str) -> str:
    """Ein Skript, das vor allen Skripten jedes neuen Dokuments läuft (etwa eine Regel für die Anfrage beim Laden); zurück: seine Kennung."""
    return (await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=js))["identifier"]


async def _vorab_weg(tab, kennung: str) -> None:
    await tab.cmd("Page.removeScriptToEvaluateOnNewDocument", identifier=kennung)


async def laden(tab, pfad: str, bereit: str) -> bool:
    """Über about:blank, damit auch eine Adresse, die sich nur im #-Fragment unterscheidet, die Seite neu lädt."""
    await tab.cmd("Page.navigate", url="about:blank")
    await asyncio.sleep(0.2)
    return await tab.oeffnen(pfad, bereit)


async def ersatz(tab, muster: str, methode: str, status: int, koerper: dict, anzahl: int = 1) -> None:
    regel = {"muster": muster, "methode": methode, "status": status, "koerper": koerper, "anzahl": anzahl}
    await tab.js(f"window.__dkErsatz.regeln.push({json.dumps(regel)})")


async def frisch(tab) -> None:
    """Neuer Besucher: keine Cookies, kein Speicher des Tabs."""
    await tab.cmd("Network.clearBrowserCookies")
    await tab.js("try{sessionStorage.clear()}catch(e){}")


async def ansicht(tab, breite: int, hoehe: int, mobil: bool, thema: str) -> None:
    await tab.fenster(breite, hoehe, mobil=mobil)
    await tab.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": thema}])
    await tab.warten(f"document.documentElement.getAttribute('data-theme')==={json.dumps(thema)}", 5, melden=False)
    await tab.js("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(true))))")


async def bilder(tab, p, name: str, *, fenster_nur: bool = False) -> None:
    """Der Zustand in allen Ansichten; schmal ohne Überlauf; danach wieder 390 px hell."""
    for breite, hoehe, mobil, thema in ANSICHTEN:
        await ansicht(tab, breite, hoehe, mobil, thema)
        if mobil:
            p.pruefe(f"{name}: {breite} px ohne Überlauf", await tab.ueberlauf(), [])
        if thema == "light":
            p.pruefe(f"{name}: {breite} px Impressum und Datenschutz", await tab.js(FUSS), FUSS_SOLL)
        datei = f"{name}_{breite}_{'hell' if thema == 'light' else 'dunkel'}"
        if not BILDER["an"]:
            continue
        if fenster_nur:
            await tab.bild(datei)
        else:
            await tab.bild_ganz(datei)
    await ansicht(tab, 390, 844, True, "light")


def code_aus_mail(mail: dict) -> str | None:
    m = re.search(r">(\d{3}) (\d{3})</td>", mail["message"]["body"]["content"])
    return (m.group(1) + m.group(2)) if m else None


async def warte_auf_mail(anzahl: int, timeout: float = 15) -> bool:
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        if len(MAILS) >= anzahl:
            return True
        await asyncio.sleep(0.2)
    return False


async def bis_c(tab, p, name: str, link: str, adresse: str) -> str | None:
    """Link öffnen, Code senden, bis C; zurück: der Code aus der Mail."""
    ok = await laden(tab, f"/#z={link}", sichtbar("seite-b"))
    p.pruefe(f"{name}: B", ok, True)
    p.pruefe(f"{name}: verdeckte Adresse", await tab.js(text_von("b-adresse")), adresse)
    vorher = len(MAILS)
    await tab.js("document.getElementById('b-senden').click()")
    p.pruefe(f"{name}: C nach dem Versand", await tab.warten(sichtbar("seite-c"), 20), True)
    p.pruefe(f"{name}: Mail an der Attrappe", await warte_auf_mail(vorher + 1), True)
    return code_aus_mail(MAILS[-1]) if len(MAILS) > vorher else None


async def eintippen(tab, wert: str) -> None:
    await tab.js("(()=>{const f=document.getElementById('c-code');f.value='';f.focus()})()")
    await tab.cmd("Input.insertText", text=wert)


async def pruefen(tab, seed, p):
    await _vorab(tab, ZEIT)
    await _vorab(tab, ERSATZ)
    await ansicht(tab, 390, 844, True, "light")
    L = seed["links"]

    # --- Ablauf 1 --------------------------------------------------------------------------------------------------------------------------
    regel = await _vorab(tab, "window.__dkRueckhalt&&window.__dkRueckhalt.regeln.push({muster:'/api/link$',methode:'POST',anzahl:1,art:'antwort'})")
    ok = await laden(tab, f"/#z={L['muster']}", sichtbar("seite-a"))
    await _vorab_weg(tab, regel)
    p.pruefe("A: Ihr Zugang wird geprüft …", (ok, await tab.js(text_von("seite-a") + ".replace(/\\s+/g,' ').trim()")),
             (True, "Ihr Zugang wird geprüft … Einen Moment bitte."))
    p.pruefe("A: der Link ist aus der Adresse", await tab.js("location.href.includes('#z=')||location.href.includes(" + json.dumps(L['muster']) + ")"), False)
    await tab.warte_bis_gehalten()
    await bilder(tab, p, "a_pruefen")
    await tab.freigeben()
    p.pruefe("B: nach dem Link", await tab.warten(sichtbar("seite-b"), 15), True)
    p.pruefe("B: verdeckte Adresse", await tab.js(text_von("b-adresse")), "m***@example.invalid")
    p.pruefe("B: kein Cookie im Skript lesbar", await tab.js("document.cookie"), "")
    await bilder(tab, p, "b_bereit")
    await ansicht(tab, 1280, 900, False, "light")  # seit 1.11.16: breit „Wir fragen Sie nie …“ direkt unter dem Inhalt
    abstand = await tab.js("(()=>{const s=document.querySelector('#seite-b .sicher').getBoundingClientRect().top;"
                           "const d=[...document.querySelectorAll('#seite-b p.leise')].pop().getBoundingClientRect().bottom;return Math.round(s-d)})()")
    p.pruefe("B breit: „Wir fragen Sie nie …“ direkt unter dem Inhalt", 0 <= abstand <= 24, True)
    await ansicht(tab, 390, 844, True, "light")
    for thema in ("dark", "light"):  # hell oder dunkel nach dem Gerät (data-theme wie im ERP)
        await ansicht(tab, 390, 844, True, thema)
        p.pruefe(f"B: Gerät {thema}", (await tab.js("document.documentElement.getAttribute('data-theme')"),
                                       await tab.js("getComputedStyle(document.body).backgroundColor")),
                 (thema, "rgb(18, 22, 25)" if thema == "dark" else "rgb(238, 240, 241)"))

    await tab.zurueckhalten(r"/api/code$", "POST", art="anfrage")
    await tab.js("void document.getElementById('b-senden').click()")
    await tab.warte_bis_gehalten(beantwortet=False)
    p.pruefe("B: Wird gesendet …", await tab.js("(()=>{const k=document.getElementById('b-senden');return [k.textContent,k.disabled]})()"),
             ["Wird gesendet …", True])
    await bilder(tab, p, "b_wird_gesendet")
    vorher = len(MAILS)
    await tab.freigeben()
    p.pruefe("C: nach dem Versand", await tab.warten(sichtbar("seite-c"), 20), True)
    p.pruefe("C: Code gesendet an …", await tab.js(text_von("c-gesendet") + ".trim()"),
             "Code gesendet an m***@example.invalid. Sehen Sie bitte auch im Spam-Ordner nach.")
    p.pruefe("C: Neuen Code senden erst nach 60 Sekunden",
             bool(re.fullmatch(r"Neuen Code senden · in (1:00|0:5\d)", await tab.js(text_von("c-neu")))) and await tab.js("document.getElementById('c-neu').disabled"),
             True)
    await bilder(tab, p, "c_gesendet")
    p.pruefe("Mail: ein Code an max@", await warte_auf_mail(vorher + 1) and [r["emailAddress"]["address"] for r in MAILS[-1]["message"]["toRecipients"]],
             ["max@example.invalid"])
    code = code_aus_mail(MAILS[-1])
    p.pruefe("Mail: Code lesbar", bool(code), True)
    vorher_pruefen = len(tab.netz.suche(r"/api/code/pruefen$", "POST"))
    await eintippen(tab, "12 345")
    await tab.js("document.getElementById('c-anmelden').click()")
    p.pruefe("C: keine 6 Ziffern -- Hinweis ohne Anfrage", (await tab.js(text_von("c-fehler-text")),
                                                          len(tab.netz.suche(r"/api/code/pruefen$", "POST")) - vorher_pruefen),
             ("Bitte geben Sie die 6 Ziffern aus der E-Mail ein.", 0))
    falsch = "000000" if code != "000000" else "111111"
    await eintippen(tab, falsch)
    await tab.js("document.getElementById('c-anmelden').click()")
    p.pruefe("C: falscher Code", await tab.warten(sichtbar("c-fehler"), 10) and await tab.js(text_von("c-fehler-text")),
             "Dieser Code stimmt nicht. Noch 4 Versuche.")
    p.pruefe("C: Feld markiert", await tab.js("document.getElementById('c-code').getAttribute('aria-invalid')"), "true")
    await bilder(tab, p, "c_falsch")
    await tab.zurueckhalten(r"/api/code/pruefen$", "POST", art="anfrage")
    await eintippen(tab, f"{code[:3]} {code[3:]}")  # wie in der Mail, mit Leerzeichen
    await tab.js("void document.getElementById('c-anmelden').click()")
    await tab.warte_bis_gehalten(beantwortet=False)
    p.pruefe("C: Wird geprüft …", await tab.js("(()=>{const k=document.getElementById('c-anmelden');return [k.textContent,k.disabled]})()"),
             ["Wird geprüft …", True])
    await bilder(tab, p, "c_wird_geprueft")
    await tab.freigeben()
    p.pruefe("D: Willkommen", await tab.warten(sichtbar("seite-d"), 15) and await tab.js(text_von("d-gruss")), "Guten Tag Herr Dr. Muster")
    p.pruefe("D: Abmelden im Kopf", await tab.js(sichtbar("kopf-abmelden")), True)
    p.pruefe("D: Anruf über tel:", await tab.js("[...document.querySelectorAll('#seite-d a[href^=\"tel:\"]')].map(a=>a.getAttribute('href'))"),
             ["tel:+49123456789"])
    p.pruefe("D: kein Cookie im Skript lesbar", await tab.js("document.cookie"), "")
    await bilder(tab, p, "d_willkommen")
    sichtbar_rest = "getComputedStyle(document.querySelector('.marke-rest')).display!=='none'"
    p.pruefe("D: Handy angemeldet -- im Kopf nur „Kundenportal“", await tab.js(sichtbar_rest), False)
    await ansicht(tab, 1280, 900, False, "light")
    p.pruefe("D: breit der ganze Name", await tab.js(sichtbar_rest), True)
    await ansicht(tab, 390, 844, True, "light")
    p.pruefe("D: neu laden bleibt angemeldet", await laden(tab, "/", sichtbar("seite-d")), True)
    await tab.js("document.getElementById('d-ueberall').click()")
    p.pruefe("D: Dialog offen", await tab.js("document.getElementById('dialog-ueberall').open"), True)
    await bilder(tab, p, "d_ueberall", fenster_nur=True)
    await tab.js("document.getElementById('dialog-ueberall-nein').click()")
    p.pruefe("D: Abbrechen schließt", await tab.js("document.getElementById('dialog-ueberall').open"), False)
    await tab.js("document.getElementById('d-ueberall').click()")
    await tab.js("document.getElementById('dialog-ueberall-ja').click()")
    p.pruefe("E: Sie sind abgemeldet", await tab.warten(sichtbar("seite-e"), 15) and await tab.js(text_von("e-titel")), "Sie sind abgemeldet")
    await bilder(tab, p, "e_abgemeldet")
    p.pruefe("E: neu laden ohne Sitzung", await laden(tab, "/", sichtbar("seite-e")) and await tab.js(text_von("e-titel")),
             "Bitte über den Link anmelden")
    await bilder(tab, p, "e_lesezeichen")

    # --- Ablauf 2 --------------------------------------------------------------------------------------------------------------------------
    await frisch(tab)
    code = await bis_c(tab, p, "Ablauf 2", L["erika"], "e***@example.invalid")
    p.pruefe("Ablauf 2: neu laden ohne Link -- C geht weiter", await laden(tab, "/", sichtbar("seite-c")) and await tab.js(text_von("c-adresse")),
             "e***@example.invalid")
    for i, falsch in enumerate(("000001", "000002", "000003", "000004"), start=1):
        if falsch == code:
            falsch = "999999"
        await eintippen(tab, falsch)
        await tab.js("document.getElementById('c-anmelden').click()")
        await tab.warten(f"{text_von('c-fehler-text')}.includes('Noch {5 - i} ')", 10, melden=False)
    p.pruefe("Ablauf 2: Einzahl", await tab.js(text_von("c-fehler-text")), "Dieser Code stimmt nicht. Noch 1 Versuch.")
    await eintippen(tab, "999998" if code != "999998" else "999997")
    await tab.js("document.getElementById('c-anmelden').click()")
    p.pruefe("C: Neuen Code anfordern", await tab.warten(sichtbar("c-abgelaufen"), 10) and await tab.js(text_von("c-titel")), "Neuen Code anfordern")
    p.pruefe("C: der neue Code geht an …", await tab.js(text_von("c-adresse-2")), "e***@example.invalid")
    await bilder(tab, p, "c_neu_anfordern")

    # --- Ablauf 3 --------------------------------------------------------------------------------------------------------------------------
    await frisch(tab)
    ok = await laden(tab, f"/#z={L['firma']}", sichtbar("seite-b"))
    p.pruefe("Ablauf 3: B", ok, True)
    GRAPH["fehler"] = True
    await tab.js("document.getElementById('b-senden').click()")
    p.pruefe("B: Versand gescheitert", await tab.warten(sichtbar("b-meldung"), 25) and await tab.js(text_von("b-meldung-text")),
             "Der Code konnte gerade nicht gesendet werden. Bitte versuchen Sie es gleich noch einmal oder rufen Sie uns an.")
    GRAPH["fehler"] = False
    p.pruefe("B: darunter das Telefon", (await tab.js(sichtbar("b-telefon")), await tab.js("document.getElementById('b-telefon').getAttribute('href')")),
             (True, "tel:+49123456789"))
    await bilder(tab, p, "b_gescheitert")
    await ersatz(tab, "/api/code$", "POST", 429, {"fehler": "bremse", "minuten": 12})
    await tab.js("document.getElementById('b-senden').click()")
    p.pruefe("B: zu viele Anforderungen", await tab.warten(f"{text_von('b-meldung-text')}.startsWith('Ein neuer Code')", 10)
             and await tab.js(text_von("b-meldung-text")), "Ein neuer Code ist in 12 Minuten wieder möglich.")
    p.pruefe("B: Knopf gesperrt", await tab.js("document.getElementById('b-senden').disabled"), True)
    await bilder(tab, p, "b_zu_viele")

    # --- Ablauf 4 --------------------------------------------------------------------------------------------------------------------------
    await frisch(tab)
    code = await bis_c(tab, p, "Ablauf 4", L["alex"], "a***@example.invalid")
    await eintippen(tab, code or "")
    await tab.js("document.getElementById('c-anmelden').click()")
    p.pruefe("Ablauf 4: Guten Tag ohne Anrede", await tab.warten(sichtbar("seite-d"), 15) and await tab.js(text_von("d-gruss")), "Guten Tag Alex Beispiel")
    await tab.js("document.getElementById('kopf-abmelden').click()")
    p.pruefe("Ablauf 4: Abmelden oben", await tab.warten(sichtbar("seite-e"), 15) and await tab.js(text_von("e-titel")), "Sie sind abgemeldet")

    # --- Ablauf 5: der Versand dauert länger (seit 1.11.16) -------------------------------------------------------------------------------
    await frisch(tab)
    POSTBOTE_HAELT.set()
    p.pruefe("Ablauf 5: B", await laden(tab, f"/#z={L['langsam']}", sichtbar("seite-b")), True)
    await tab.js("document.getElementById('b-senden').click()")
    await asyncio.sleep(2.5)
    p.pruefe("Ablauf 5: nach 2 s noch B „Wird gesendet …“", (await tab.js(sichtbar("seite-b")), await tab.js(text_von("b-senden"))), (True, "Wird gesendet …"))
    await tab.js("window.__dkZeit.weiter(31000)")
    p.pruefe("C: der Versand dauert länger", await tab.warten(sichtbar("c-dauert"), 8) and await tab.js(text_von("c-dauert") + ".trim()"),
             "Der Versand dauert länger als sonst. Der Code kann noch einige Minuten brauchen – sehen Sie bitte auch im Spam-Ordner nach.")
    p.pruefe("C: dabei kein „Code gesendet“ und keine Meldung", (await tab.js(sichtbar("c-gesendet")), await tab.js(sichtbar("c-meldung"))), (False, False))
    p.pruefe("C: „Neuen Code senden“ 60 Sekunden ab der Anforderung",
             bool(re.fullmatch(r"Neuen Code senden · in 0:(2\d|30)", await tab.js(text_von("c-neu")))) and await tab.js("document.getElementById('c-neu').disabled"), True)
    await bilder(tab, p, "c_versand_dauert")
    p.pruefe("Ablauf 5: neu laden -- C mit dem Hinweis", await laden(tab, "/", sichtbar("c-dauert")), True)
    vorher = len(MAILS)
    await eintippen(tab, "12")  # angefangene Eingabe
    POSTBOTE_HAELT.clear()
    p.pruefe("C: danach „Code gesendet an …“", await tab.warten(f"{sichtbar('c-gesendet')}&&!{sichtbar('c-dauert')}", 15), True)
    p.pruefe("C: die angefangene Eingabe bleibt stehen", await tab.js("document.getElementById('c-code').value"), "12")
    p.pruefe("Ablauf 5: Mail an lars@", await warte_auf_mail(vorher + 1) and [r["emailAddress"]["address"] for r in MAILS[-1]["message"]["toRecipients"]],
             ["lars@example.invalid"])
    await eintippen(tab, code_aus_mail(MAILS[-1]) or "")
    await tab.js("document.getElementById('c-anmelden').click()")
    p.pruefe("Ablauf 5: angemeldet", await tab.warten(sichtbar("seite-d"), 15) and await tab.js(text_von("d-gruss")), "Guten Tag Herr Langsam")

    # --- Ablauf 6: nach 10 Minuten nichts (seit 1.11.16) ----------------------------------------------------------------------------------
    await frisch(tab)
    POSTBOTE_HAELT.set()
    p.pruefe("Ablauf 6: B", await laden(tab, f"/#z={L['zehn']}", sichtbar("seite-b")), True)
    await tab.js("document.getElementById('b-senden').click()")
    await asyncio.sleep(1.5)
    await tab.js("window.__dkZeit.weiter(31000)")
    p.pruefe("Ablauf 6: nach 30 Sekunden C mit Hinweis", await tab.warten(sichtbar("c-dauert"), 8), True)
    await tab.js("window.__dkZeit.weiter(600000)")
    p.pruefe("C: nach 10 Minuten gescheitert", await tab.warten(sichtbar("c-meldung"), 12) and await tab.js(text_von("c-meldung-text")),
             "Der Code konnte gerade nicht gesendet werden. Bitte versuchen Sie es gleich noch einmal oder rufen Sie uns an.")
    p.pruefe("C: mit Telefon, ohne Hinweis, „Neuen Code senden“ frei",
             (await tab.js(sichtbar("c-telefon")), await tab.js(sichtbar("c-dauert")), await tab.js("document.getElementById('c-neu').disabled"),
              await tab.js(text_von("c-neu"))), (True, False, False, "Neuen Code senden"))
    await bilder(tab, p, "c_versand_gescheitert")
    POSTBOTE_HAELT.clear()

    # --- Fehlerseite ----------------------------------------------------------------------------------------------------------------------
    await frisch(tab)
    for name, link in (("unbekannt", seed["unbekannt"]), ("gesperrt", L["gesperrt"]), ("abgelaufen", L["alt"])):
        ok = await laden(tab, f"/#z={link}", sichtbar("seite-e"))
        p.pruefe(f"E: Link {name} -- dieselbe Seite", (ok, await tab.js(text_von("e-titel")), await tab.js(text_von("e-satz"))),
                 (True, "Dieser Link funktioniert nicht", "Bitte nutzen Sie den Link aus unserer letzten E-Mail. Gern senden wir Ihnen auch einen neuen."))
    await bilder(tab, p, "e_link")
    for name, status, koerper, titel in (("e_zu_viele", 429, {"fehler": "bremse", "minuten": 3}, "Zu viele Versuche"),
                                         ("e_technisch", 500, {"fehler": "technisch"}, "Gerade klappt etwas nicht"),
                                         ("e_wartung", 502, {}, "Gleich wieder da")):
        regel = await _vorab(tab, "window.__dkErsatzVorab=[" + json.dumps({"muster": "/api/link$", "methode": "POST", "status": status,
                                                                             "koerper": koerper, "anzahl": 1}) + "]")
        ok = await laden(tab, f"/#z={L['bremse']}", sichtbar("seite-e"))
        await _vorab_weg(tab, regel)
        p.pruefe(f"E: {status}", ok and await tab.js(text_von("e-titel")), titel)
        await bilder(tab, p, name)
    p.pruefe("E: Diese Seite gibt es nicht", await laden(tab, "/gibt-es-nicht", sichtbar("seite-e")) and await tab.js(text_von("e-titel")),
             "Diese Seite gibt es nicht")
    p.pruefe("E: 404 vom Dienst", await tab.js("fetch('/gibt-es-nicht').then(r=>r.status)"), 404)
    await bilder(tab, p, "e_nicht_gefunden")
    p.pruefe("keine Verletzung der CSP, kein JS-Fehler", (await tab.js("window.__dkErsatz.csp"), tab.fehler), (0, []))

    # ohne JavaScript: kein Aufruf ins Skript der Seite (Runtime.evaluate wartete dort ewig) -- geprüft über das DOM, die Bilder ohne Wartezeit aufs
    # Skript. Hell auch im dunklen Gerät: hell oder dunkel setzt das Skript (data-theme wie im ERP).
    await tab.cmd("Emulation.setScriptExecutionDisabled", value=True)
    await tab.cmd("Page.navigate", url="about:blank")
    await asyncio.sleep(0.3)
    await tab.cmd("Page.navigate", url=tab.base + "/")
    await asyncio.sleep(1.5)
    wurzel = (await tab.cmd("DOM.getDocument", depth=-1, pierce=False))["root"]["nodeId"]
    html_ = (await tab.cmd("DOM.getOuterHTML", nodeId=wurzel))["outerHTML"]
    p.pruefe("ohne JavaScript: Hinweis in der Seite", ("JavaScript ist ausgeschaltet" in html_, "Bitte schalten Sie JavaScript ein, um das Kundenportal zu nutzen." in html_),
             (True, True))
    p.pruefe("ohne JavaScript: Impressum und Datenschutz im Fuß", [f'href="https://{WEBSEITE}/{z}"' in html_ for z in ("impressum", "datenschutz")],
             [True, True])
    for breite, hoehe, mobil, thema in ANSICHTEN:
        await tab.fenster(breite, hoehe, mobil=mobil)
        await tab.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": thema}])
        await asyncio.sleep(0.4)
        if BILDER["an"]:
            await tab.bild_ganz(f"e_js_aus_{breite}_{'hell' if thema == 'light' else 'dunkel'}")
    await tab.cmd("Emulation.setScriptExecutionDisabled", value=False)
    await tab.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])
    await tab.cmd("Page.navigate", url="about:blank")
    await asyncio.sleep(0.3)


# --- Ablauf des Klicktests -----------------------------------------------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Klicktest: Seiten des Kundenportals")
    parser.add_argument("--arbeitsordner", type=Path)
    parser.add_argument("--chrome")
    parser.add_argument("--zeitlimit", type=float)
    parser.add_argument("--offen-lassen", action="store_true")
    parser.add_argument("--portal-server", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.portal_server:
        _portal_server(args.portal_server)
        return 0

    pg_url = os.environ.get("ERP_TEST_POSTGRES_URL")
    if not pg_url:
        print("ERP_TEST_POSTGRES_URL fehlt -- das Portal läuft nur gegen PostgreSQL.")
        return 2
    gegenprobe = gegenprobe_im_code()
    grenzen = [(args.zeitlimit, "--zeitlimit")] if args.zeitlimit else []
    if gegenprobe:
        grenzen.append((ZEITLIMIT_GEGENPROBE, f"Gegenprobe läuft, Marker {GEGENPROBE_MARKER} in {gegenprobe}"))
        BILDER["an"] = False
        print("Gegenprobe: ohne Bilder", flush=True)
    wachhund = Wachhund(*min(grenzen)) if grenzen else None
    if wachhund:
        wachhund.starten()

    ordner = klicktest_ordner(args.arbeitsordner, "erp-klicktest-")
    if ordner.exists() and any(ordner.iterdir()):
        raise SystemExit(f"Arbeitsordner ist nicht leer: {ordner}")
    for sub in ("data", "shots", "chrome-profile"):
        (ordner / sub).mkdir(parents=True, exist_ok=True)
    (ordner / MARKER).write_text("Wegwerf-Instanz eines Klicktests, darf gelöscht werden.\n", encoding="utf-8")

    graph_port = _graph_starten()
    # DATABASE_URL hier nur eine Wegwerf-SQLite im Arbeitsordner: was das ERP beim Import anlegt, trifft nie die echte Datenbank (Regel 16)
    os.environ.update({"ERP_ENV": "test", "ERP_DATA_DIR": str(ordner / "data"), "ERP_SECRET_KEY": secrets.token_urlsafe(32),
                       "DATABASE_URL": "sqlite:///" + (ordner / "erp.db").as_posix(),
                       "ERP_TEST_GRAPH": f"http://127.0.0.1:{graph_port}", "PYTHONIOENCODING": "utf-8"})
    sys.path.insert(0, str(ROOT))
    from sqlalchemy import create_engine, text

    schema = f"pgklick_{uuid.uuid4().hex[:8]}"
    verwaltung = create_engine(pg_url)
    with verwaltung.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
        c.execute(text(f"COMMENT ON SCHEMA {schema} IS 'Klicktest Kundenportal, pid {os.getpid()}'"))
    erp = _engine(pg_url, schema)
    server = chrome = postbote = None
    try:
        seed = befuellen(erp)
        postbote = Postbote(erp)
        postbote.faden.start()
        port = _freier_port()
        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        env.update({"PORTAL_KLICK_SCHEMA": schema, "PORTAL_HERKUNFT": f"http://localhost:{port}", "PORTAL_BREMSE_SCHLUESSEL": secrets.token_hex(32),
                    "DATABASE_URL": pg_url})
        with open(ordner / "portal.out.log", "ab") as out:
            server = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--portal-server", str(port)], env=env, cwd=ROOT,
                                      stdout=out, stderr=subprocess.STDOUT)
        if wachhund:
            wachhund.kinder.append(server)
        if not _bereit(port):
            print(f"Portal-Dienst antwortet nicht, siehe {ordner / 'portal.out.log'}")
            return 2
        print(f"Arbeitsordner {ordner}\nPortal http://localhost:{port}  Schema {schema}", flush=True)
        chrome = subprocess.Popen([_chrome_pfad(args.chrome), "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={ordner / 'chrome-profile'}",
                                   "--no-first-run", "--no-default-browser-check", "--disable-extensions", "about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wachhund:
            wachhund.kinder.append(chrome)
        cdp_port = _chrome_port(chrome, ordner / "chrome-profile", 30)
        if cdp_port is None:
            print("Chrome antwortet nicht auf dem CDP-Port.")
            return 2
        (ordner / "pids.txt").write_text(f"server={server.pid} chrome={chrome.pid}\n", encoding="utf-8")
        ok = asyncio.run(_lauf(pruefen, seed, cdp_port, f"http://localhost:{port}", ordner / "shots", None, wachhund))
        if postbote.fehler:
            print(f"XX  Postbote: {sorted(set(postbote.fehler))}")
            ok = False
        return 0 if ok else 1
    finally:
        if wachhund:
            wachhund.anhalten()
        if postbote is not None:
            postbote.halt.set()
            postbote.faden.join(5)
        if not args.offen_lassen:
            for proc in (chrome, server):
                if proc is not None:
                    beenden(proc.pid)
        erp.dispose()
        with verwaltung.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n AND pid <> pg_backend_pid()"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        verwaltung.dispose()


if __name__ == "__main__":
    sys.exit(main())
