"""Klicktest: Design-System auf der Anmeldeseite -- ds.css und alle drei Schriftfamilien laden ohne Anmeldung (1.8.127, Stufe 1 des
Redesigns, Vorgabe vom 19.10.2026, Punkt 7).

    ds.css          die Anmeldeseite bindet /static/ds/ds.css?v=<Version> ein (seit 1.8.161 danach ds-basis.css, wirksam erst mit
                    .ds-seite): --ds-grund hell #EEF0F1, dunkel #121619; die Akzentfarbe aus den Einstellungen (--accent) und die
                    Schrift der Seite bleiben, wie sie sind
    Schriften       document.fonts.load() lädt Archivo 500/600/700, IBM Plex Sans 400/500/600 und IBM Plex Mono 400/500 -- je mit
                    deutschem Text (latin) und mit "ŐŁ" (latin-ext); danach meldet document.fonts.check() alle als geladen, 16 woff2
                    kamen mit 200
    Kopfzeilen      eine Schrift, ds.css und ds-basis.css ohne Anmeldung: Typ fest, "Cache-Control: public, max-age=31536000, immutable",
                    nosniff

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_ds_schriften.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

SCHNITTE = [("Archivo", 500), ("Archivo", 600), ("Archivo", 700), ("IBM Plex Sans", 400), ("IBM Plex Sans", 500), ("IBM Plex Sans", 600),
            ("IBM Plex Mono", 400), ("IBM Plex Mono", 500)]
DAUERHAFT = "public, max-age=31536000, immutable"


def befuellen(db, k):
    from app.models import AppUser
    from app.settings import load_general_settings

    db.add(AppUser(username="bea", display_name="Bea Büro", role="buero_finanzen", password_hash=k.passwort()))
    db.flush()
    return {"akzent": load_general_settings(db).accent_color}


def _laden(familie: str, gewicht: int, text: str) -> str:
    """Lädt einen Schnitt für text; Ergebnis [Anzahl Flächen, alle geladen, Familien, Gewichte]."""
    return (f"document.fonts.load({json.dumps(f'{gewicht} 16px \"{familie}\"')}, {json.dumps(text)})"
            ".then(f=>[f.length,f.every(x=>x.status==='loaded'),[...new Set(f.map(x=>x.family.replace(/\"/g,'')))],"
            "[...new Set(f.map(x=>x.weight))]])")


async def pruefen(tab, seed, p):
    await tab.anmelden({})
    p.pruefe("Anmeldeseite ohne Anmeldung", await tab.oeffnen("/login", "document.readyState==='complete'&&!!document.getElementById('u')"),
             True)
    # seit 1.8.161 bindet _ds_kopf.html nach ds.css auch ds-basis.css ein (bis dahin nur ds.css)
    p.pruefe("ds.css und ds-basis.css eingebunden", await tab.js(
        "[...document.querySelectorAll('link[rel=stylesheet]')].map(l=>new URL(l.href).pathname)"),
        ["/static/ds/ds.css", "/static/ds/ds-basis.css"])
    token = "getComputedStyle(document.documentElement).getPropertyValue('{}').trim()"
    # das Thema ausdrücklich -- ohne gespeicherte Wahl folgt die Seite dem Farbschema des Systems (headless auch dunkel)
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    p.pruefe("--ds-grund hell", await tab.js(token.format("--ds-grund")), "#EEF0F1")
    p.pruefe("Akzentfarbe unverändert", (await tab.js(token.format("--accent"))).lower(), seed["akzent"].lower())
    schrift = await tab.js("getComputedStyle(document.body).fontFamily")
    p.pruefe("Schrift der Seite unverändert (keine neue Familie)", any(f in schrift for f in ("Archivo", "Plex")), False)
    p.pruefe("vorher nichts geladen", await tab.js("[...document.fonts].filter(f=>f.status==='loaded').length"), 0)

    for familie, gewicht in SCHNITTE:
        p.pruefe(f"{familie} {gewicht} latin", await tab.js(_laden(familie, gewicht, "Dachfläche Größe 1.250,00 € „Signal“")),
                 [1, True, [familie], [str(gewicht)]])
        p.pruefe(f"{familie} {gewicht} latin-ext", await tab.js(_laden(familie, gewicht, "ŐŁ")), [1, True, [familie], [str(gewicht)]])
    p.pruefe("document.fonts.check für alle Schnitte", await tab.js(
        "[" + ",".join(f"document.fonts.check({json.dumps(f'{g} 16px \"{f}\"')}, 'AŐ')" for f, g in SCHNITTE) + "]"), [True] * 8)
    await tab.warte_auf_ruhe()
    schriften = sorted({(e["url"].rsplit("/", 1)[-1], e.get("status")) for e in tab.netz.verlauf
                        if e.get("url") and "/static/ds/schriften/" in e["url"]})
    p.pruefe("16 woff2 geladen, alle 200", (len(schriften), {s for _, s in schriften}), (16, {200}))

    kopf = ("fetch('{}').then(r=>[r.status,r.headers.get('content-type'),r.headers.get('cache-control'),"
            "r.headers.get('x-content-type-options')])")
    p.pruefe("woff2: Kopfzeilen", await tab.js(kopf.format("/static/ds/schriften/archivo-latin-700-normal.woff2")),
             [200, "font/woff2", DAUERHAFT, "nosniff"])
    p.pruefe("ds.css: Kopfzeilen", await tab.js(kopf.format("/static/ds/ds.css?v=x")),
             [200, "text/css; charset=utf-8", DAUERHAFT, "nosniff"])
    p.pruefe("ds-basis.css: Kopfzeilen", await tab.js(kopf.format("/static/ds/ds-basis.css?v=x")),
             [200, "text/css; charset=utf-8", DAUERHAFT, "nosniff"])

    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    p.pruefe("--ds-grund dunkel", await tab.js(token.format("--ds-grund")), "#121619")
    await tab.bild("anmeldung_dunkel")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
