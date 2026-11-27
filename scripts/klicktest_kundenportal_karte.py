"""Klicktest: Karte „Kundenportal“ in der Kundenakte (1.11.11, Stufe P1d; Bauplan P1, Abschnitt 4; seit 1.11.13 die Antworten des Betriebs).

    Zustände            je ein Kunde: Portal aus; an, kein Zugang; an, ohne E-Mail; Zugang ohne Link; Link versendet (gültig bis, zuletzt genutzt);
                        läuft in 20 Tagen ab (Hinweis „Verlängern“); abgelaufen (kein „Verlängern“); gesperrt (Grund, von, am); Versand gescheitert
                        (eigener Zustand, „Link erneut senden“ ohne Warnung, danach aktiv); Kunde im Archiv (nur „Protokoll“ und „Sperren“ -- Sperren
                        geht dort, alles andere 409) -- je ein Bild der Karte
    Ablauf (Büro – Auftrag)   einschalten -> „Zugang anlegen“ (E-Mail des Kunden vorbelegt) -> „Link senden“ -> Mail an der Graph-Attrappe (ohne
                        „Gesendete Elemente“, HTML, Knopf mit dem Link) -> „Neuen Link senden“ mit Warnung und anderer Adresse -> Sperren ohne Grund
                        (Meldung) und mit Grund -> Entsperren -> Verlängern -> Protokoll (eine Zeile je Aktion, Portal und ERP) -> ausschalten; zwischen
                        den Schritten geht die stehende Uhr eine Minute weiter (wie Klicks im Betrieb)
    Rechte              Monteurin: Seite und Schnittstelle 403; Modul aus: keine Karte, keine Anfrage
    412 px              die Karte ragt nicht über die Gerätebreite

Microsoft 365 ist eine Attrappe auf 127.0.0.1 in diesem Skript (ERP_TEST_GRAPH, nur mit ERP_ENV development oder test -- app/email_sending.py::
graph_attrappe()); sie merkt sich jede Mail. Der Rest liegt in der Wegwerf-SQLite dieses Laufs (Regel 16). Stehende Uhr 24.11.2026 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_kundenportal_karte.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln: siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import base64
import json
import os
import re
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import _freier_port, klicktest_main  # noqa: E402

MAILS = []


class _Graph(BaseHTTPRequestHandler):
    """Attrappe von Microsoft 365: Anmeldung und sendMail (202), merkt sich jede Mail."""

    def log_message(self, *args):
        pass

    def do_POST(self):
        laenge = int(self.headers.get("Content-Length") or 0)
        koerper = self.rfile.read(laenge)
        if self.path.endswith("/oauth2/v2.0/token"):
            antwort = json.dumps({"access_token": "attrappe", "token_type": "Bearer", "expires_in": 3600}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(antwort)))
            self.end_headers()
            self.wfile.write(antwort)
            return
        if self.path.endswith("/sendMail"):
            MAILS.append(json.loads(koerper))
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()


def _graph_starten() -> int:
    port = _freier_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), _Graph)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port


KARTE = "document.getElementById('uPortal')"
GELADEN = "(()=>{const z=document.getElementById('portalZustand');return !!z&&z.textContent!=='Lädt …'})()"
ZUSTAND = "document.getElementById('portalZustand').textContent"
SICHTBARE_KNOEPFE = ("[...document.querySelectorAll('#portalKnoepfe button')].filter(b=>!b.hidden&&b.offsetParent!==null)"
                     ".map(b=>b.textContent)")
DATEN = "[...document.querySelectorAll('#portalDaten dt')].map(d=>d.textContent+': '+d.nextElementSibling.textContent)"
HINWEIS = "(()=>{const h=document.getElementById('portalHinweis');return h.hidden?'':h.textContent})()"


def befuellen(db, k):
    from datetime import datetime, timedelta

    from app.email_sending import load_smtp_settings, update_graph_settings
    from app.models import AppUser, Customer, EmailDispatch, EnabledModule, PortalZugang

    adm = AppUser(username="adri", display_name="Adri Admin", role="admin", password_hash=k.passwort())
    auf = AppUser(username="auri", display_name="Auri Auftrag", role="buero_auftrag", password_hash=k.passwort())
    mon = AppUser(username="moni", display_name="Moni Monteurin", role="field", password_hash=k.passwort())
    db.add_all([adm, auf, mon, EnabledModule(module_key="kundenportal", enabled=True)])
    from app.settings import load_general_settings
    load_general_settings(db).website = "www.muster-bedachung.example"  # seit 1.11.47: ohne Webseite kein Portal (Impressum und Datenschutz sind Pflicht)
    jetzt = datetime(2026, 11, 24, 9, 0)
    kunden = {}

    def kunde(schluessel, nachname, *, aktiv=True, email="max@example.invalid"):
        c = Customer(name=f"Herr Max {nachname}", salutation="Herr", first_name="Max", last_name=nachname, email=email, portal_aktiv=aktiv)
        db.add(c)
        db.flush()
        kunden[schluessel] = c.id
        return c

    def zugang(c, *, link=True, tage=200, gesperrt=False, genutzt=True):
        z = PortalZugang(customer_id=c.id, email=c.email or "max@example.invalid", email_anzeige="m***@example.invalid",
                         link_sha256=("%064x" % c.id) if link else None, link_erzeugt_am=jetzt - timedelta(days=30) if link else None,
                         gueltig_bis=jetzt + timedelta(days=tage) if link else None, angelegt_am=jetzt - timedelta(days=31),
                         angelegt_von_name="Auri Auftrag", zuletzt_genutzt_am=jetzt - timedelta(days=2) if (link and genutzt) else None)
        if gesperrt:
            z.gesperrt_am, z.gesperrt_grund, z.gesperrt_von_name = jetzt - timedelta(days=1), "Kunde meldet ein verlorenes Handy", "Adri Admin"
        db.add(z)
        db.flush()
        return z

    kunde("aus", "Aus", aktiv=False)
    kunde("kein_zugang", "Neu")
    kunde("ohne_email", "Ohnemail", email=None)
    zugang(kunde("ohne_link", "Ohnelink"), link=False)
    zugang(kunde("aktiv", "Aktiv"))
    zugang(kunde("laeuft_ab", "Bald"), tage=20)
    zugang(kunde("abgelaufen", "Alt"), tage=-5, genutzt=False)
    zugang(kunde("gesperrt", "Gesperrt"), gesperrt=True)
    z = zugang(kunde("gescheitert", "Fehler"), genutzt=False)
    db.add(EmailDispatch(dispatch_key="portal-link-bild-0001", message_ref="00000000-0000-0000-0000-000000000001", status="fehlgeschlagen",
                         channel="graph_oauth2", document_type="portal_link", document_id=z.id, to_recipients="max@example.invalid",
                         subject="Ihr Zugang zum Kundenportal", created_at=jetzt - timedelta(minutes=30), finished_at=jetzt - timedelta(minutes=30),
                         created_by_name="Auri Auftrag", error_class="ValueError"))
    archiviert = kunde("archiv", "Archiv")
    zugang(archiviert)
    archiviert.archiviert_am = jetzt  # erst anlegen, dann ins Archiv (Archivschutz: kein neuer Verweis auf einen Kunden im Archiv)
    db.flush()
    kunde("ablauf", "Ablauf", aktiv=False)
    db.flush()
    s = load_smtp_settings(db)
    s.send_method = "graph_oauth2"
    update_graph_settings(db, tenant_id="mandant-attrappe", client_id="anwendung-attrappe", sender_mailbox="buero@example.invalid",
                          client_secret="geheim-attrappe")
    return {"adm": k.cookies(adm), "auf": k.cookies(auf), "mon": k.cookies(mon), "kunden": kunden, "db_url": os.environ["DATABASE_URL"],
            "uhr_ms": k.uhr_ms()}


def _abfrage(seed, sql: str, *werte):
    pfad = seed["db_url"].removeprefix("sqlite:///")
    assert Path(pfad).parent.joinpath(".klicktest").exists(), pfad
    with sqlite3.connect(pfad) as c:
        return c.execute(sql, werte).fetchall()


def _sql(seed, sql: str, *werte) -> int:
    pfad = seed["db_url"].removeprefix("sqlite:///")
    assert Path(pfad).parent.joinpath(".klicktest").exists(), pfad
    with sqlite3.connect(pfad) as c:
        return c.execute(sql, werte).rowcount


async def _karte_bild(tab, name):
    """Nur die Karte (mit etwas Rand) als Bild."""
    r = await tab.js(f"(()=>{{const b={KARTE}.getBoundingClientRect();return [b.x,b.y+window.scrollY,b.width,b.height]}})()")
    daten = (await tab.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                           clip={"x": max(r[0] - 8, 0), "y": max(r[1] - 8, 0), "width": r[2] + 16, "height": r[3] + 16, "scale": 1}))["data"]
    tab.ablage(f"{name}.png").write_bytes(base64.b64decode(daten))


async def _kunde_oeffnen(tab, p, seed, schluessel):
    ok = await tab.oeffnen(f"/customers/{seed['kunden'][schluessel]}", GELADEN)
    p.pruefe(f"{schluessel}: Kundenakte mit Karte geladen", ok, True)
    await tab.warte_auf_ruhe()


def _tag(tage: int) -> str:
    """Tag in Berlin, tage nach dem 24.11.2026 09:00 UTC (stehende Uhr), wie die Karte ihn zeigt."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    return (datetime(2026, 11, 24, 9, 0, tzinfo=timezone.utc) + timedelta(days=tage)).astimezone(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y")


async def _klick(tab, js):
    return await tab.warte_auf_neu_geladene_liste(js)


PROTOKOLL_TEXTE = "[...document.querySelectorAll('#portalProtokollListe li')].map(li=>li.children.length>1?li.children[1].textContent:li.textContent)"
PROTOKOLL_ZEILEN = "[...document.querySelectorAll('#portalProtokollListe li')].map(li=>[...li.children].map(s=>s.textContent))"


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["auf"])
    await _kunde_oeffnen(tab, p, seed, "aus")
    await tab.js("localStorage.setItem('erp_theme','light')")  # Bilder hell; eins dunkel unten
    erwartet = {
        "aus": ("Aus", ["Portal einschalten"], ""),
        "kein_zugang": ("Kein Zugang", ["Zugang anlegen", "Portal ausschalten"], ""),
        "ohne_email": ("Ohne E-Mail", ["Portal ausschalten"], ""),
        "ohne_link": ("Ohne Link", ["Link senden", "Sperren", "Portal ausschalten"], ""),
        "aktiv": ("Aktiv", ["Neuen Link senden", "Verlängern", "Sperren", "Portal ausschalten"], ""),
        "laeuft_ab": ("Läuft bald ab", ["Neuen Link senden", "Verlängern", "Sperren", "Portal ausschalten"], f"Der Link läuft am {_tag(20)} ab"),
        "abgelaufen": ("Abgelaufen", ["Neuen Link senden", "Sperren", "Portal ausschalten"], ""),  # seit 1.11.13 ohne „Verlängern“
        "gesperrt": ("Gesperrt", ["Entsperren", "Portal ausschalten"], ""),
        "gescheitert": ("Versand gescheitert", ["Link erneut senden", "Sperren", "Portal ausschalten"], ""),  # seit 1.11.13 ein eigener Zustand
        "archiv": ("Im Archiv", ["Sperren"], ""),  # seit 1.11.13: Sperren geht auch im Archiv
    }
    for schluessel, (zustand, knoepfe, hinweis) in erwartet.items():
        await _kunde_oeffnen(tab, p, seed, schluessel)
        p.pruefe(f"{schluessel}: Zustand", await tab.js(ZUSTAND), zustand)
        p.pruefe(f"{schluessel}: Knöpfe", [k for k in await tab.js(SICHTBARE_KNOEPFE) if k != "Protokoll"], knoepfe)
        p.pruefe(f"{schluessel}: Hinweis", (await tab.js(HINWEIS)).startswith(hinweis) if hinweis else await tab.js(HINWEIS), True if hinweis else "")
        await _karte_bild(tab, f"karte_{schluessel}")
    await _kunde_oeffnen(tab, p, seed, "gesperrt")
    p.pruefe("gesperrt: Angaben", await tab.js(DATEN), ["E-Mail: max@example.invalid", f"Link gültig bis: {_tag(200)}", f"Link erzeugt: {_tag(-30)}",
                                                         f"Zuletzt genutzt: {_tag(-2)}", f"Gesperrt: {_tag(-1)} von Adri Admin",
                                                         "Grund: Kunde meldet ein verlorenes Handy"])
    await _kunde_oeffnen(tab, p, seed, "gescheitert")  # seit 1.11.13: Kennzeichen, Satz, Angabe, „Link erneut senden“ ohne Warnung
    p.pruefe("gescheitert: Satz", await tab.js("document.getElementById('portalText').textContent"), "Der Link ging nicht hinaus.")
    p.pruefe("gescheitert: Kennzeichen in Warnfarbe", await tab.js("document.getElementById('portalZustand').className"), "chip chip-warn")
    p.pruefe("gescheitert: Angabe mit Zeit und Adresse", [d for d in await tab.js(DATEN) if d.startswith("Versand gescheitert")],
             ["Versand gescheitert: 24.11.2026 09:30 an max@example.invalid"])
    await tab.js("document.getElementById('portalLinkSenden').click()")
    p.pruefe("gescheitert: Dialog „Link erneut senden“", await tab.js("document.getElementById('portalLinkTitel').textContent"), "Link erneut senden")
    p.pruefe("gescheitert: ohne Warnung", await tab.js("document.getElementById('portalLinkNeu').hidden"), True)
    await tab.bild("dialog_link_erneut")
    p.pruefe("gescheitert: erneut gesendet", await _klick(tab, "document.querySelector('[data-klick=\"portal-link-senden\"]').click()"), True)
    p.pruefe("gescheitert: danach aktiv", await tab.js(ZUSTAND), "Aktiv")
    await _kunde_oeffnen(tab, p, seed, "abgelaufen")
    antwort = await tab.js(f"fetch('/api/customers/{seed['kunden']['abgelaufen']}/portal/verlaengern',{{method:'POST'}}).then(r=>r.status)")
    p.pruefe("abgelaufen: Verlängern lehnt der Server ab", antwort, 409)

    await _kunde_oeffnen(tab, p, seed, "archiv")  # seit 1.11.13: Sperren geht auch im Archiv, alles andere 409
    await tab.js("document.getElementById('portalSperren').click()")
    p.pruefe("archiv: Feld „Grund“ frei", await tab.js("document.getElementById('portalSperrenGrund').disabled"), False)
    await tab.js("document.getElementById('portalSperrenGrund').value='Kunde im Archiv – Zugang schließen'")
    p.pruefe("archiv: gesperrt", await _klick(tab, "document.querySelector('[data-klick=\"portal-sperren\"]').click()"), True)
    p.pruefe("archiv: Angaben der Sperre", [d for d in await tab.js(DATEN) if d.startswith("Grund")], ["Grund: Kunde im Archiv – Zugang schließen"])
    p.pruefe("archiv: danach nur „Protokoll“", await tab.js(SICHTBARE_KNOEPFE), ["Protokoll"])
    await _karte_bild(tab, "karte_archiv_gesperrt")
    antwort = await tab.js(f"fetch('/api/customers/{seed['kunden']['archiv']}/portal/entsperren',{{method:'POST'}}).then(r=>r.status)")
    p.pruefe("archiv: Entsperren lehnt der Server ab", antwort, 409)

    # --- Ablauf als Büro – Auftrag ---------------------------------------------------------------------------------------------------------
    await _kunde_oeffnen(tab, p, seed, "ablauf")
    await tab.js("window.confirm=()=>true")
    minute = [0]
    mails_vorher = len(MAILS)  # „Link erneut senden“ oben schickte schon eine

    async def weiter():  # seit 1.11.13: wie Klicks im Betrieb -- jede Aktion eine Minute später (utc_jetzt() ist sekundengenau)
        minute[0] += 1
        await tab.uhr_stellen(seed["uhr_ms"] + minute[0] * 60_000)
    p.pruefe("Ablauf: einschalten", await _klick(tab, "document.getElementById('portalEin').click()"), True)
    p.pruefe("Ablauf: kein Zugang", await tab.js(ZUSTAND), "Kein Zugang")
    await tab.js("document.getElementById('portalZugangNeu').click()")
    p.pruefe("Zugang anlegen: E-Mail des Kunden vorbelegt", await tab.js("document.getElementById('portalZugangEmail').value"), "max@example.invalid")
    await tab.bild("dialog_zugang_anlegen")
    p.pruefe("Zugang anlegen: gespeichert", await _klick(tab, "document.querySelector('[data-klick=\"portal-zugang-anlegen\"]').click()"), True)
    p.pruefe("Zugang anlegen: Dialog zu", await tab.js("document.getElementById('portalZugangDialog').open"), False)
    p.pruefe("Ablauf: ohne Link", await tab.js(ZUSTAND), "Ohne Link")
    await tab.js("document.getElementById('portalLinkSenden').click()")
    p.pruefe("Link senden: ohne Warnung beim ersten Link", await tab.js("document.getElementById('portalLinkNeu').hidden"), True)
    await weiter()
    p.pruefe("Link senden: gesendet", await _klick(tab, "document.querySelector('[data-klick=\"portal-link-senden\"]').click()"), True)
    p.pruefe("Link senden: Zustand", await tab.js(ZUSTAND), "Aktiv")
    p.pruefe("Link senden: Meldung", await tab.js("document.getElementById('portalStatus').textContent"), "Link gesendet.")
    p.pruefe("Mail: eine an der Attrappe", len(MAILS) - mails_vorher, 1)
    mail = MAILS[-1]
    p.pruefe("Mail: ohne „Gesendete Elemente“", mail.get("saveToSentItems"), "false")
    p.pruefe("Mail: HTML mit Knopf zum Portal", (mail["message"]["body"]["contentType"],
                                                 bool(re.search(r'href="https://kunde\.dachkonzepte\.gmbh/#z=[A-Za-z0-9_-]{43}"', mail["message"]["body"]["content"]))),
             ("HTML", True))
    p.pruefe("Mail: Betreff fest", mail["message"]["subject"], "Ihr Zugang zum Kundenportal")
    await tab.js("document.getElementById('portalLinkSenden').click()")
    p.pruefe("Neuer Link: Warnung", await tab.js("document.getElementById('portalLinkNeu').hidden"), False)
    await tab.js("document.getElementById('portalLinkEmail').value='neu@example.invalid'")
    await tab.bild("dialog_neuer_link")
    await weiter()
    p.pruefe("Neuer Link: gesendet", await _klick(tab, "document.querySelector('[data-klick=\"portal-link-senden\"]').click()"), True)
    p.pruefe("Neuer Link: an die neue Adresse", [r["emailAddress"]["address"] for r in MAILS[-1]["message"]["toRecipients"]], ["neu@example.invalid"])
    p.pruefe("Neuer Link: E-Mail in der Karte", (await tab.js(DATEN))[0], "E-Mail: neu@example.invalid")
    await tab.js("document.getElementById('portalSperren').click()")
    await tab.js("document.querySelector('[data-klick=\"portal-sperren\"]').click()")
    p.pruefe("Sperren ohne Grund: Meldung", await tab.js("document.getElementById('portalSperrenStatus').textContent"), "Bitte einen Grund angeben.")
    await tab.js("document.getElementById('portalSperrenGrund').value='Kunde bittet darum'")
    await tab.bild("dialog_sperren")
    await weiter()
    p.pruefe("Sperren: gesperrt", await _klick(tab, "document.querySelector('[data-klick=\"portal-sperren\"]').click()"), True)
    p.pruefe("Sperren: Zustand", await tab.js(ZUSTAND), "Gesperrt")
    await weiter()
    p.pruefe("Entsperren", await _klick(tab, "document.getElementById('portalEntsperren').click()"), True)
    p.pruefe("Entsperren: Zustand", await tab.js(ZUSTAND), "Aktiv")
    await weiter()
    p.pruefe("Verlängern", await _klick(tab, "document.getElementById('portalVerlaengern').click()"), True)
    p.pruefe("Verlängern: gültig bis in 12 Monaten", [d for d in await tab.js(DATEN) if d.startswith("Link gültig bis")], ["Link gültig bis: 24.11.2027"])
    await tab.js("document.getElementById('portalProtokoll').click()")
    await tab.warte_auf_ruhe()
    zeilen = await tab.js(PROTOKOLL_ZEILEN)
    p.pruefe("Protokoll: eine Zeile je Aktion, mit Konto (seit 1.11.13)", [z[1:] for z in zeilen], [
        ["Link verlängert – gültig bis 24.11.2027", "Auri Auftrag"],
        ["Zugang entsperrt", "Auri Auftrag"],
        ["Zugang gesperrt – Grund: Kunde bittet darum", "Auri Auftrag"],
        ["Neuer Link gesendet an neu@example.invalid – gültig bis 24.11.2027 (E-Mail vorher max@example.invalid)", "Auri Auftrag"],
        ["Link gesendet an max@example.invalid – gültig bis 24.11.2027", "Auri Auftrag"],
        ["Zugang angelegt für max@example.invalid", "Auri Auftrag"],
        ["Kundenportal eingeschaltet", "Auri Auftrag"],
    ])
    await tab.bild("dialog_protokoll")
    await tab.js("document.querySelector('#portalProtokollDialog [data-klick=\"dialog-zu\"]').click()")
    p.pruefe("Ausschalten", await _klick(tab, "document.getElementById('portalAus').click()"), True)
    p.pruefe("Ausschalten: Zustand", await tab.js(ZUSTAND), "Aus")
    p.pruefe("Prüfwert nie in der Historie",
             _abfrage(seed, "SELECT count(*) FROM audit_logs WHERE field_name = 'link_sha256' OR new_value IN (SELECT link_sha256 FROM portal_zugaenge)"),
             [(0,)])

    # --- dunkel, 412 px, Admin ------------------------------------------------------------------------------------------------------------
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await _kunde_oeffnen(tab, p, seed, "laeuft_ab")
    await _karte_bild(tab, "karte_laeuft_ab_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(412, 900, mobil=True)
    await _kunde_oeffnen(tab, p, seed, "gesperrt")
    p.pruefe("412 px: nichts ragt über die Gerätebreite", await tab.ueberlauf(), [])
    await _karte_bild(tab, "karte_gesperrt_412")
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["adm"])
    await _kunde_oeffnen(tab, p, seed, "aktiv")
    p.pruefe("Admin: Karte wie im Büro", await tab.js(ZUSTAND), "Aktiv")

    # --- Monteurin und Modul aus ----------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["mon"])
    antwort = await tab.js(f"fetch('/api/customers/{seed['kunden']['aktiv']}/portal').then(r=>r.status)")
    p.pruefe("Monteurin: Schnittstelle 403", antwort, 403)
    await tab.anmelden(seed["auf"])
    _sql(seed, "UPDATE enabled_modules SET enabled = 0 WHERE module_key = 'kundenportal'")
    vorher = sum(1 for e in tab.netz.verlauf if "/portal" in str(e.get("url", "")))
    ok = await tab.oeffnen(f"/customers/{seed['kunden']['aktiv']}", "document.getElementById('stammdatenListe').children.length>0")
    p.pruefe("Modul aus: Kundenakte geladen", ok, True)
    await tab.warte_auf_ruhe()
    p.pruefe("Modul aus: keine Karte", await tab.js(f"!{KARTE}"), True)
    p.pruefe("Modul aus: keine Anfrage", sum(1 for e in tab.netz.verlauf if "/portal" in str(e.get("url", ""))) - vorher, 0)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-24 10:00",
                            umgebung={"ERP_TEST_GRAPH": f"http://127.0.0.1:{_graph_starten()}"}))
