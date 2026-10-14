"""Klicktest: Anfragen und Rahmen einer fremden Seite derselben Site (1.8.104, Vorgabe vom 14.10.2026, Punkte 3 und 4).

Eine Seite derselben Site -- hier ein zweiter Server auf 127.0.0.1 mit anderem Port, für den Browser "same-site" wie
www.dachkonzepte.gmbh neben app.dachkonzepte.gmbh: das SameSite=Lax-Cookie geht mit -- versucht, was Befund 1.8.100 Nr. 2 und 3
beschreiben:

    Rahmen          die Seite rahmt /account des ERP ein -> der Browser zeigt den Rahmen nicht (X-Frame-Options: DENY,
                    frame-ancestors 'none'), im Rahmen steht keine ERP-Seite
    Upload          ein Formular-Upload (FormData, ohne Vorabanfrage) an die Kundenakte -> 403, kein Dokument
    Ohne Body       Abmelden (POST ohne Body) -> 403, die Sitzung lebt
    Anmelden        Anmelden in ein Konto der fremden Seite (Formular-POST) -> 403
    Eigene Seite    danach speichert die Kundenakte im ERP wie immer ("Gespeichert.", Sec-Fetch-Site: same-origin) und lädt ein
                    Dokument hoch; die Anmeldeseite trägt X-Frame-Options: DENY

Feste Uhr 10:00. alert()/confirm() werden mitgeschrieben.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_fremde_seite.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import http.server
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_anmelden import DIALOGE, _freier_port, _klick, _tippen  # noqa: E402

PASSWORT_BEA = "Bea-Passwort-1"

ANGRIFF = """<!doctype html><html><head><meta charset="utf-8"><title>Fremde Seite</title></head><body>
<h1>Fremde Seite derselben Site</h1>
<iframe id="rahmen" src="__ERP__/account" width="700" height="300"></iframe>
<script>
const ERP = "__ERP__";
async function angriff(kunde) {
  const ergebnis = {};
  const fd = new FormData();
  fd.append("file", new Blob(["%PDF-1.4 fremd"], {type: "application/pdf"}), "fremd.pdf");
  fd.append("category", "Sonstiges");
  try { await fetch(ERP + "/api/customers/" + kunde + "/documents", {method: "POST", body: fd, mode: "no-cors", credentials: "include"}); ergebnis.upload = "gesendet"; }
  catch (e) { ergebnis.upload = "Fehler " + e.message; }
  try { await fetch(ERP + "/api/auth/logout", {method: "POST", mode: "no-cors", credentials: "include"}); ergebnis.abmelden = "gesendet"; }
  catch (e) { ergebnis.abmelden = "Fehler " + e.message; }
  const login = new URLSearchParams({username: "bea", password: "x"});
  try { await fetch(ERP + "/api/auth/login", {method: "POST", body: login, mode: "no-cors", credentials: "include"}); ergebnis.anmelden = "gesendet"; }
  catch (e) { ergebnis.anmelden = "Fehler " + e.message; }
  return ergebnis;
}
</script></body></html>"""


def befuellen(db, k):
    from app.crm import ensure_customer_profile
    from app.models import AppUser, Customer

    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort(PASSWORT_BEA))
    kunde = Customer(name="Gerda Muster", last_name="Muster", first_name="Gerda", city="Musterstadt")
    db.add_all([bea, kunde]); db.flush()
    ensure_customer_profile(db, kunde, category="Privatkunde")
    db.flush()
    return {"kunde": kunde.id, "cookies_bea": k.cookies(bea)}


class _Angreifer(http.server.BaseHTTPRequestHandler):
    seite = b""

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.seite)

    def log_message(self, *args):
        pass


def _kopf(url: str) -> dict:
    """Kopfzeilen einer Antwort, Namen klein geschrieben (der Server schickt sie klein, ein dict unterscheidet die Schreibweise)."""
    try:
        with urllib.request.urlopen(url, timeout=10) as antwort:
            return {k.lower(): v for k, v in antwort.headers.items()}
    except urllib.error.HTTPError as fehler:
        return {k.lower(): v for k, v in fehler.headers.items()}


async def _rahmen(tab) -> list[str]:
    baum = (await tab.cmd("Page.getFrameTree"))["frameTree"]
    return [kind["frame"].get("url", "") for kind in baum.get("childFrames", [])]


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=DIALOGE)
    await tab.anmelden(seed["cookies_bea"])
    kunde = seed["kunde"]

    port = _freier_port()
    _Angreifer.seite = ANGRIFF.replace("__ERP__", tab.base).encode()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Angreifer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        fremd = f"http://127.0.0.1:{port}"
        await tab.cmd("Page.navigate", url=fremd + "/")
        await tab.warten("typeof angriff==='function'&&document.readyState==='complete'")
        await tab.warten("false", 1.5, melden=False)  # der Rahmen lädt oder wird abgewiesen
        rahmen = await _rahmen(tab)
        p.pruefe("Rahmen nicht angezeigt", [u.startswith("chrome-error://") for u in rahmen], [True])
        marke = len(tab.netz.verlauf)
        ergebnis = await tab.js(f"angriff({kunde})")
        p.pruefe("Angriffe gesendet (no-cors)", ergebnis, {"upload": "gesendet", "abmelden": "gesendet", "anmelden": "gesendet"})
        await tab.warte_auf_ruhe()
        antworten = {e["url"].split("/api/", 1)[-1]: e["status"] for e in tab.netz.verlauf[marke:]
                     if e.get("url") and "/api/" in e["url"] and e.get("methode") == "POST"}
        p.pruefe("Server antwortet 403", antworten,
                 {f"customers/{kunde}/documents": 403, "auth/logout": 403, "auth/login": 403})
        await tab.bild("fremde_seite")
    finally:
        server.shutdown()
        server.server_close()

    await tab.oeffnen(f"/customers/{kunde}", "document.getElementById('lastName').value==='Muster'")
    p.pruefe("weiter angemeldet", await tab.js("fetch('/api/auth/status').then(r=>r.json()).then(d=>d.authenticated)"), True)
    p.pruefe("kein Dokument von der fremden Seite",
             await tab.js(f"fetch('/api/customers/{kunde}/documents').then(r=>r.json()).then(d=>d.length)"), 0)
    await _tippen(tab, "#notes", "Von der eigenen Seite")
    await _klick(tab, "button[onclick='saveCustomer()']")
    p.pruefe("eigene Seite speichert", await tab.warten(
        "document.getElementById('customerStatus').textContent==='Gespeichert.'"), True)
    hochgeladen = await tab.js(
        f"(async()=>{{const fd=new FormData();fd.append('file',new Blob(['%PDF-1.4 eigen'],{{type:'application/pdf'}}),'eigen.pdf');"
        f"const r=await fetch('/api/customers/{kunde}/documents',{{method:'POST',body:fd}});return r.status}})()")
    p.pruefe("eigene Seite lädt hoch", hochgeladen, 200)
    kopf = _kopf(tab.base + "/login")
    p.pruefe("Anmeldeseite ohne Rahmen", (kopf.get("x-frame-options"), "frame-ancestors 'none'" in (kopf.get("content-security-policy") or "")),
             ("DENY", True))
    p.pruefe("kein Dialog", await tab.js("[window.__alerts.length,window.__confirms.length]"), [0, 0])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
