"""Klicktest: Anmeldung läuft beim Speichern ab (1.8.103, Vorweg der Vorgabe vom 14.10.2026).

Läuft die Sitzung ab, während eine Seite offen ist (12 h, abgemeldet, von einem Administrator beendet), antwortet die
Anmeldeschranke auf das Speichern mit 401 und der Kopfzeile X-DK-Anmeldung: abgelaufen (app/anmeldeschranke.py); der Baustein
app/templates/_speichern.html zeigt oben den Hinweis „Anmeldung abgelaufen“, der Bereich meldet den Text des Servers, die Seite bleibt
mit allen Eingaben stehen. Nach dem Anmelden in einem neuen Tab speichert derselbe Klick, und der Hinweis verschwindet.

    Ablauf          Bea öffnet die Kundenakte und ändert Nachname und Notiz; Anna (Administratorin) beendet von außerhalb des
                    Browsers alle Sitzungen von Bea (POST /api/users/<id>/end-sessions, Korrektur 98-11)
    Speichern       Klick auf „Stammdaten speichern“: PUT 401 mit der Kopfzeile, Meldung „Anmeldung abgelaufen …“ am Bereich,
                    Hinweis oben, keine Navigation (weiter die Kundenakte, nicht /login), Nachname und Notiz unverändert in den
                    Feldern, auf dem Server nichts geändert
    Neuer Tab       zweiter Tab desselben Browsers: /login, Benutzername und Passwort getippt, Anmelden -> weitergeleitet; Tab zu
    Noch einmal     im ersten Tab derselbe Klick: „Gespeichert.“, Hinweis weg, Nachname und Notiz auf dem Server
    Ohne Cookie     ein Gerät, das nie angemeldet war (kein Cookie): 401 ohne die Kopfzeile (kein „abgelaufen“)

Feste Uhr 10:00. alert()/confirm() werden mitgeschrieben.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_anmeldung_abgelaufen.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_anmelden import DIALOGE, _klick, _tippen  # noqa: E402

PASSWORT_BEA = "Bea-Passwort-1"
HINWEIS = "#dkAnmeldungAbgelaufen"


def befuellen(db, k):
    from app.crm import ensure_customer_profile
    from app.models import AppUser, Customer

    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort(PASSWORT_BEA))
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort("Anna-Passwort-1"))
    kunde = Customer(name="Gerda Muster", last_name="Muster", first_name="Gerda", city="Musterstadt")
    db.add_all([bea, anna, kunde]); db.flush()
    ensure_customer_profile(db, kunde, category="Privatkunde")
    db.flush()
    return {"kunde": kunde.id, "bea": bea.id, "cookies_bea": k.cookies(bea), "cookies_anna": k.cookies(anna)}


def _anfrage(base: str, pfad: str, cookies: dict | None, methode: str = "GET") -> tuple[int, dict, dict]:
    """Eine Anfrage außerhalb des Browsers: Status, Kopfzeilen, JSON."""
    kopf = {"Cookie": "; ".join(f"{n}={w}" for n, w in cookies.items())} if cookies else {}
    if methode != "GET":
        kopf["Origin"] = base  # wie der Browser bei einer schreibenden Anfrage der eigenen Seite
    anfrage = urllib.request.Request(base + pfad, method=methode, headers=kopf, data=b"" if methode != "GET" else None)
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            return antwort.status, dict(antwort.headers), json.loads(antwort.read() or b"null")
    except urllib.error.HTTPError as fehler:
        return fehler.code, dict(fehler.headers), json.loads(fehler.read() or b"null")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=DIALOGE)
    pfad = f"/customers/{seed['kunde']}"
    await tab.anmelden(seed["cookies_bea"])
    await tab.oeffnen(pfad, "document.getElementById('lastName').value==='Muster'")
    await _tippen(tab, "#lastName", "Muster-Neu")
    await _tippen(tab, "#notes", "Notiz nach dem Ablauf")

    status, _, daten = _anfrage(tab.base, f"/api/users/{seed['bea']}/end-sessions", seed["cookies_anna"], "POST")
    p.pruefe("Admin beendet alle Sitzungen von Bea", (status, daten.get("sitzungen_beendet")), (200, 1))

    marke = len(tab.netz.suche(r"/api/customers/\d+$", "PUT"))
    await _klick(tab, "button[onclick='saveCustomer()']")
    await tab.warten("document.getElementById('customerStatus').textContent.includes('Anmeldung abgelaufen')")
    put = tab.netz.suche(r"/api/customers/\d+$", "PUT", ab=marke)
    p.pruefe("PUT 401", [e.get("status") for e in put], [401])
    p.pruefe("Meldung am Bereich", (await tab.js("document.getElementById('customerStatus').textContent"))[:30],
             "Fehler: Anmeldung abgelaufen –")
    p.pruefe("Hinweis oben sichtbar", await tab.js(
        f"(()=>{{const e=document.querySelector('{HINWEIS}');return !!e&&e.getBoundingClientRect().height>0"
        "&&e.textContent.startsWith('Anmeldung abgelaufen')})()"), True)
    p.pruefe("keine Navigation", await tab.js("location.pathname"), pfad)
    p.pruefe("Eingaben stehen", await tab.js("[document.getElementById('lastName').value,document.getElementById('notes').value]"),
             ["Muster-Neu", "Notiz nach dem Ablauf"])
    p.pruefe("kein Dialog", await tab.js("[window.__alerts.length,window.__confirms.length]"), [0, 0])
    await tab.bild("abgelaufen")
    _, _, kunde = _anfrage(tab.base, f"/api/customers/{seed['kunde']}", seed["cookies_anna"])
    p.pruefe("auf dem Server nichts geändert", kunde.get("last_name"), "Muster")

    async with tab.zweiter_tab() as neu:
        await neu.oeffnen("/login", "!!document.getElementById('u')")
        await _tippen(neu, "#u", "bea")
        await _tippen(neu, "#p", PASSWORT_BEA)
        await _klick(neu, "button[onclick='login()']")
        p.pruefe("im neuen Tab angemeldet", await neu.warten("location.pathname!=='/login'"), True)

    await _klick(tab, "button[onclick='saveCustomer()']")
    p.pruefe("derselbe Klick speichert", await tab.warten(
        "document.getElementById('customerStatus').textContent==='Gespeichert.'"), True)
    p.pruefe("Hinweis weg", await tab.js(f"!document.querySelector('{HINWEIS}')"), True)
    _, _, kunde = _anfrage(tab.base, f"/api/customers/{seed['kunde']}", seed["cookies_anna"])
    p.pruefe("auf dem Server gespeichert", [kunde.get("last_name"), (kunde.get("profile") or {}).get("notes", kunde.get("notes"))],
             ["Muster-Neu", "Notiz nach dem Ablauf"])

    status, kopf, daten = _anfrage(tab.base, "/api/customers", None)
    p.pruefe("ohne Cookie: 401 ohne „abgelaufen“", (status, kopf.get("X-DK-Anmeldung"), daten.get("detail")),
             (401, None, "Bitte zuerst als ERP-Benutzer anmelden."))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
