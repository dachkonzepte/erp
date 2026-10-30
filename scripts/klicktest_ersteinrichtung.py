"""Klicktest: ohne Konto bleibt das ERP geschlossen (1.8.130, Runde 1d, Vorgabe vom 19.10.2026, Punkt 1).

Die Instanz hat kein einziges Konto. Seit 1.8.130 hält die Anmeldeschranke die App dann geschlossen: durch gehen nur /health und die
Design-Dateien, jede Seite zeigt den Hinweis mit dem Befehl für die Ersteinrichtung (503), alles andere bekommt 503 als JSON.

    Seite           /, /login, /users, /projects: Status 503, Überschrift "Ersteinrichtung", der Befehl als Text (mit "<benutzername>"),
                    kein Formular, ds.css geladen (Titel in Archivo); hell und dunkel nach dem Farbschema des Systems, 412 und 1440 px
    API             aus der Seite: /api/auth/status, /api/users (GET und POST mit einem vollständigen Konto), /api/mobile-icon 503 mit
                    ersteinrichtung=true; danach immer noch kein Konto (POST /api/auth/login scheitert ebenso)
    frei            /health 200, ds.css 200

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_ersteinrichtung.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEFEHL = "python scripts/erstes_konto.py <benutzername>"
BEREIT = "document.readyState==='complete'&&!!document.querySelector('main pre')"
STATUS = "performance.getEntriesByType('navigation')[0].responseStatus"
KONTO = {"username": "mallory", "password": "geheim-genug", "display_name": "Mallory", "role": "admin"}


def befuellen(db, k):
    from app.models import AppUser
    from sqlalchemy import func, select

    assert db.scalar(select(func.count(AppUser.id))) == 0  # die Instanz beginnt ohne Konto
    return {}


def _api(methode: str, pfad: str, koerper: dict | None = None) -> str:
    optionen = {"method": methode}
    if koerper is not None:
        optionen.update(headers={"Content-Type": "application/json"}, body=json.dumps(koerper))
    return (f"fetch({json.dumps(pfad)},{json.dumps(optionen)}).then(async r=>[r.status,"
            "(r.headers.get('content-type')||'').split(';')[0],r.status===503?(await r.json()).ersteinrichtung:null])")


async def pruefen(tab, seed, p):
    await tab.anmelden({})
    for thema in ("light", "dark"):
        await tab.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": thema}])
        for breite in (412, 1440):
            await tab.cmd("Emulation.setDeviceMetricsOverride", width=breite, height=900, deviceScaleFactor=1, mobile=breite <= 412)
            for pfad in ("/", "/login", "/users", "/projects"):
                name = f"{pfad} {thema} {breite}"
                p.pruefe(f"{name}: Hinweis geladen", await tab.oeffnen(pfad, BEREIT), True)
                p.pruefe(f"{name}: Status 503", await tab.js(STATUS), 503)
                p.pruefe(f"{name}: Befehl als Text", await tab.js("document.querySelector('main pre').textContent"), BEFEHL)
                p.pruefe(f"{name}: kein Formular", await tab.js("document.querySelectorAll('form,input,button').length"), 0)
            p.pruefe(f"{thema} {breite}: Thema der Seite", await tab.js("document.documentElement.getAttribute('data-theme')"),
                     "dark" if thema == "dark" else None)
            p.pruefe(f"{thema} {breite}: Hintergrund aus ds.css", await tab.js(
                "getComputedStyle(document.body).backgroundColor"), "rgb(18, 22, 25)" if thema == "dark" else "rgb(238, 240, 241)")
            p.pruefe(f"{thema} {breite}: nichts ragt über die Gerätebreite", await tab.ueberlauf(breite), [])
            await tab.bild_ganz(f"breite_ersteinrichtung_{thema}_{breite}")
            p.pruefe(f"{thema} {breite}: passt in der Höhe ins Fenster", await tab.js(
                "document.documentElement.scrollHeight<=window.innerHeight"), True)
            await tab.js("document.fonts.ready")
            p.pruefe(f"{thema} {breite}: Titel in Archivo", await tab.js(
                "document.fonts.check('700 16px \"Archivo\"','Ersteinrichtung')&&getComputedStyle(document.querySelector('h1'))"
                ".fontFamily.includes('Archivo')"), True)
            await tab.bild(f"ersteinrichtung_{thema}_{breite}")

    p.pruefe("/health frei", await tab.js("fetch('/health').then(r=>r.status)"), 200)
    p.pruefe("ds.css frei", await tab.js("fetch('/static/ds/ds.css').then(r=>r.status)"), 200)
    p.pruefe("GET /api/auth/status", await tab.js(_api("GET", "/api/auth/status")), [503, "application/json", True])
    p.pruefe("GET /api/users", await tab.js(_api("GET", "/api/users")), [503, "application/json", True])
    p.pruefe("POST /api/users mit vollständigem Konto", await tab.js(_api("POST", "/api/users", KONTO)), [503, "application/json", True])
    p.pruefe("POST /api/auth/login", await tab.js(_api("POST", "/api/auth/login", {"username": "mallory", "password": "geheim-genug"})),
             [503, "application/json", True])
    p.pruefe("GET /api/mobile-icon/192.png", await tab.js(_api("GET", "/api/mobile-icon/192.png")), [503, "application/json", True])
    p.pruefe("danach weiter geschlossen", await tab.oeffnen("/users", BEREIT), True)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
