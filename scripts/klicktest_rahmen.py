"""Klicktest: Rahmen der Seiten, Stufe 2 „Rahmen“, Runde 1 (seit 1.8.163; Seitenleiste 1.8.162, Kopfzeile 1.8.163).

Geprüft wird im echten Browser auf den Testdaten der Bildgrundlage (scripts/bildgrundlage.py, stehende Uhr), hell und dunkel:

    Seitenleiste   in jeder Rolle bei 1440 × 900 und 1280 × 800 ohne Bildlauf, die Version unten im Fenster; 232 px breit, Logo-Zeile
                   52 px mit Kachel 36 px, Zeilen 36 px, vier Gruppen; Grund in --ds-navi-grund (dunkel in beiden Modi); aktiv genau der
                   Eintrag des Bereichs der Seite (Projektmappe -> Projekte, Rechnung -> Projekte, Kunde -> Stammdaten, Befunde, Suche
                   und Konto keiner), mit aria-current, 3 px Strich in --ds-marke-hell auf --ds-navi-aktiv
    Menüknopf      klappt die Leiste ein (60 px) und wieder aus, aria-expanded folgt
    Kopfzeile      64 px, Suche 480 px breit, rechts der Kontoknopf mit Initialen im Kreis in --ds-aktion und dem vollen Namen
                   (ganz zu sehen); bei 412 px nur die Initialen, kein waagrechter Bildlauf
    Kontomenü      per Tastatur: Enter, Pfeil runter und Pfeil hoch am Knopf öffnen (Fokus auf den ersten bzw. letzten Eintrag),
                   Pfeile wandern im Kreis, Pos1/Ende, Escape schließt mit Fokus zurück am Knopf, Tab schließt; role menu/menuitem,
                   aria-haspopup, aria-controls, aria-expanded folgt; Mein Konto · Hell/Dunkel · Abmelden; Hell/Dunkel per Enter
                   schaltet data-theme um und zeigt den Zustand; Klick daneben schließt
    Seitenregeln   auf den Einstellungen (button:hover und button:active in der Akzentfarbe): Kontoknopf unter der Maus und per
                   Leertaste gedrückt (:active ohne :hover), Menüeintrag unter der Maus -- nie in der Akzentfarbe

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_rahmen.py [--nur TEIL[,TEIL]] [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

--nur: nur diese Teile (seitenleiste, aktiv, menueknopf, kopfzeile, kontomenue, seitenregeln) -- für Gegenproben, die nach 2 min
abbrechen (Regel 24).

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bildgrundlage as bg  # noqa: E402
from cdp_klicktest import klicktest_main  # noqa: E402

ROLLEN = (bg.BUERO, bg.BUERO_AUFTRAG, bg.ADMIN, bg.MONTEUR)
GRUPPEN = {
    bg.BUERO: ["Übersicht", "Aufträge", "Kaufmännisch", "Verwaltung"],
    bg.BUERO_AUFTRAG: ["Übersicht", "Aufträge", "Kaufmännisch", "Verwaltung"],
    bg.ADMIN: ["Übersicht", "Aufträge", "Kaufmännisch", "Verwaltung"],
    bg.MONTEUR: ["Übersicht", "Kaufmännisch"],  # bis Teil 4 (1.8.164): Start und Zeiterfassung
}
SEITE_JE_ROLLE = {bg.BUERO: "start", bg.BUERO_AUFTRAG: "start", bg.ADMIN: "start", bg.MONTEUR: "einsatzbericht"}
AKTIV = [("projektmappe", "projekte"), ("rechnung", "projekte"), ("kunde", "stammdaten"), ("befunde", "befunde"),
         ("einstellungen", "einstellungen"), ("zeiterfassung", "zeiterfassung"), ("suche", None), ("konto", None)]

# Farbe eines --ds-Werts so, wie getComputedStyle sie meldet (rgb(...))
FARBE = ("(v=>{const d=document.createElement('div');d.style.color='var('+v+')';document.body.appendChild(d);"
         "const c=getComputedStyle(d).color;d.remove();return c})")

LEISTE = """(()=>{const F=%s;const s=document.getElementById('appSidebar');const n=s.querySelector('.app-sidebar-nav');
const r=e=>e?e.getBoundingClientRect():null;const cs=e=>getComputedStyle(e);const aktiv=[...s.querySelectorAll('.app-sidebar-link.active')];
const a=aktiv[0];const v=s.querySelector('.app-sidebar-version');
return {breite:Math.round(r(s).width),kopf:Math.round(r(s.querySelector('.app-sidebar-head')).height),
kachel:Math.round(r(s.querySelector('.app-sidebar-kachel')).height),zeile:Math.round(r(s.querySelector('.app-sidebar-link')).height),
scrollt:n.scrollHeight>n.clientHeight+1,version_im_fenster:r(v).bottom<=innerHeight&&r(v).height>0,
version:(v.textContent||'').trim().startsWith('Version '),grund_navi:cs(s).backgroundColor===F('--ds-navi-grund'),
gruppen:[...s.querySelectorAll('.app-sidebar-group')].map(g=>g.textContent.trim().toLowerCase()),
aktiv:aktiv.map(x=>x.dataset.bereich),aria:[...s.querySelectorAll('[aria-current="page"]')].map(x=>x.dataset.bereich||x.textContent.trim()),
strich:a?[cs(a).borderLeftWidth,cs(a).borderLeftColor===F('--ds-marke-hell'),cs(a).backgroundColor===F('--ds-navi-aktiv')]:null}})()""" % FARBE

KOPF = """(()=>{const F=%s;const t=document.querySelector('.app-topbar');const r=e=>e?e.getBoundingClientRect():null;
const such=document.querySelector('.app-topbar-search');const k=document.getElementById('appTopbarAccountBtn');
const name=k&&k.querySelector('.app-konto-name');const ini=k&&k.querySelector('.app-konto-initialen');
const sichtbar=e=>!!e&&getComputedStyle(e).display!=='none'&&r(e).width>0;
return {hoehe:Math.round(r(t).height),suche:such?Math.round(r(such).width):null,name:name?name.textContent:null,
name_sichtbar:sichtbar(name),name_ganz:!!name&&name.scrollWidth<=name.clientWidth,initialen:ini?ini.textContent:null,
kreis:ini?[Math.round(r(ini).width),Math.round(r(ini).height),getComputedStyle(ini).borderRadius,getComputedStyle(ini).backgroundColor===F('--ds-aktion')]:null,
knopf_rechts:k?Math.round(innerWidth-r(k).right)<=24:null,knopf_in_zeile:k?r(k).top>=r(t).top&&r(k).bottom<=r(t).bottom:null,
breit_scroll:document.documentElement.scrollWidth>innerWidth+1}})()""" % FARBE

MENUE = """(()=>{const k=document.getElementById('appTopbarAccountBtn');const m=document.getElementById('appTopbarAccountMenu');
const a=document.activeElement;
return {offen:!m.hidden,expanded:k.getAttribute('aria-expanded'),fokus:a===k?'knopf':(a&&a.closest&&a.closest('#appTopbarAccountMenu')?(a.id||a.getAttribute('href')):(a&&a.tagName))}})()"""

ARIA = """(()=>{const k=document.getElementById('appTopbarAccountBtn');const m=document.getElementById('appTopbarAccountMenu');
return {knopf:[k.getAttribute('aria-haspopup'),k.getAttribute('aria-controls'),k.getAttribute('aria-label')],rolle:m.getAttribute('role'),
eintraege:[...m.querySelectorAll('.ds-menue-eintrag')].map(e=>[e.getAttribute('role'),e.getAttribute('tabindex'),e.textContent.replace(/\\s+/g,' ').trim()])}})()"""

TASTEN = {"Enter": 13, "Escape": 27, "ArrowDown": 40, "ArrowUp": 38, "Home": 36, "End": 35, "Tab": 9}


async def _taste(tab, key):
    code = TASTEN[key]
    extra = {"text": "\r"} if key == "Enter" else {}
    await tab.cmd("Input.dispatchKeyEvent", type="keyDown", key=key, code=key, windowsVirtualKeyCode=code, nativeVirtualKeyCode=code, **extra)
    await tab.cmd("Input.dispatchKeyEvent", type="keyUp", key=key, code=key, windowsVirtualKeyCode=code, nativeVirtualKeyCode=code)


async def _maus(tab, art, selektor, knopf="none"):
    xy = await tab.js(f"(()=>{{const r=document.querySelector({json.dumps(selektor)}).getBoundingClientRect();"
                      "return [r.left+r.width/2,r.top+r.height/2]})()")
    await tab.cmd("Input.dispatchMouseEvent", type=art, x=xy[0], y=xy[1], button=knopf, clickCount=1 if knopf != "none" else 0)


async def _laden(tab, seed, name, thema, breite, hoehe):
    await tab.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark" if thema == "dunkel" else "light"}])
    await tab.cmd("Emulation.setDeviceMetricsOverride", width=breite, height=hoehe, deviceScaleFactor=1, mobile=breite in bg.GERAETE)
    ok = await tab.oeffnen(bg.AUFNAHME[name].pfad.format(**seed), bg.BEREIT, timeout=45)
    await tab.js(bg.RUHE)
    return ok


async def _seitenleiste(tab, seed, p):
    for rolle in ROLLEN:
        await tab.anmelden(seed["cookies"][rolle])
        for thema, (breite, hoehe) in (("hell", (1440, 900)), ("dunkel", (1440, 900)), ("hell", (1280, 800))):
            wo = f"Leiste {rolle} {thema} {breite}×{hoehe}"
            p.pruefe(f"{wo}: geladen", await _laden(tab, seed, SEITE_JE_ROLLE[rolle], thema, breite, hoehe), True)
            m = await tab.js(LEISTE)
            p.pruefe(f"{wo}: ohne Bildlauf, Version im Fenster", [m["scrollt"], m["version_im_fenster"], m["version"]], [False, True, True])
            p.pruefe(f"{wo}: 232 px, Kopf 52, Kachel 36, Zeile 36, Grund navi", [m["breite"], m["kopf"], m["kachel"], m["zeile"], m["grund_navi"]],
                     [232, 52, 36, 36, True])
            p.pruefe(f"{wo}: Gruppen", m["gruppen"], [g.lower() for g in GRUPPEN[rolle]])
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])


async def _aktiv(tab, seed, p):
    await tab.anmelden(seed["cookies"][bg.BUERO])
    for i, (name, bereich) in enumerate(AKTIV):
        thema = "dunkel" if i % 2 else "hell"
        wo = f"Aktiv {name} ({thema})"
        p.pruefe(f"{wo}: geladen", await _laden(tab, seed, name, thema, 1440, 900), True)
        m = await tab.js(LEISTE)
        soll = [bereich] if bereich else []
        p.pruefe(f"{wo}: aktiver Eintrag und aria-current", [m["aktiv"], m["aria"]], [soll, soll])
        if bereich:
            p.pruefe(f"{wo}: Strich 3 px in marke-hell auf navi-aktiv", m["strich"], ["3px", True, True])


async def _menueknopf(tab, seed, p):
    await tab.anmelden(seed["cookies"][bg.BUERO])
    for thema in ("hell", "dunkel"):
        p.pruefe(f"Menüknopf {thema}: geladen", await _laden(tab, seed, "start", thema, 1440, 900), True)
        zustand = ("(()=>{const s=document.getElementById('appSidebar');return [Math.round(s.getBoundingClientRect().width),"
                   "document.getElementById('appTopbarMenuBtn').getAttribute('aria-expanded')]})()")
        p.pruefe(f"Menüknopf {thema}: ausgeklappt", await tab.js(zustand), [232, "true"])
        await _maus(tab, "mousePressed", "#appTopbarMenuBtn", "left")
        await _maus(tab, "mouseReleased", "#appTopbarMenuBtn", "left")
        p.pruefe(f"Menüknopf {thema}: eingeklappt", await tab.js(zustand), [60, "false"])
        await _maus(tab, "mousePressed", "#appTopbarMenuBtn", "left")
        await _maus(tab, "mouseReleased", "#appTopbarMenuBtn", "left")
        p.pruefe(f"Menüknopf {thema}: wieder ausgeklappt", await tab.js(zustand), [232, "true"])


async def _kopfzeile(tab, seed, p):
    # Bernd ist mit seinem Mitarbeiter verknüpft (Vor- und Nachname), Ada nicht -- dann zeigt der Knopf den Benutzernamen
    # (app/auth.py::resolve_account_display(), unverändert)
    namen = {bg.BUERO: "Bernd Büro", bg.ADMIN: "ada"}
    for rolle in (bg.BUERO, bg.ADMIN):
        await tab.anmelden(seed["cookies"][rolle])
        for thema in ("hell", "dunkel"):
            wo = f"Kopfzeile {rolle} {thema}"
            p.pruefe(f"{wo}: geladen", await _laden(tab, seed, "projektmappe", thema, 1440, 900), True)
            m = await tab.js(KOPF)
            p.pruefe(f"{wo}: 64 px, Suche 480 px, Knopf rechts in der Zeile", [m["hoehe"], m["suche"], m["knopf_rechts"], m["knopf_in_zeile"]],
                     [64, 480, True, True])
            p.pruefe(f"{wo}: Name sichtbar und ganz, Initialen im Kreis in aktion",
                     [bool(m["name"]), m["name_sichtbar"], m["name_ganz"], len(m["initialen"] or ""), m["kreis"]],
                     [True, True, True, 2, [36, 36, "50%", True]])
            if namen.get(rolle):
                p.pruefe(f"{wo}: voller Name", m["name"], namen[rolle])
    await tab.anmelden(seed["cookies"][bg.BUERO])
    p.pruefe("Kopfzeile 412 px: geladen", await _laden(tab, seed, "projektmappe", "hell", 412, 900), True)
    m = await tab.js(KOPF)
    p.pruefe("Kopfzeile 412 px: 64 px, nur Initialen, kein waagrechter Bildlauf",
             [m["hoehe"], m["name_sichtbar"], bool(m["initialen"]), m["knopf_in_zeile"], m["breit_scroll"]], [64, False, True, True, False])


async def _kontomenue(tab, seed, p):
    await tab.anmelden(seed["cookies"][bg.BUERO])
    for thema in ("hell", "dunkel"):
        wo = f"Kontomenü {thema}"
        p.pruefe(f"{wo}: geladen", await _laden(tab, seed, "projektmappe", thema, 1440, 900), True)
        a = await tab.js(ARIA)
        p.pruefe(f"{wo}: aria am Knopf und an den Einträgen",
                 [a["knopf"][0], a["knopf"][1], a["knopf"][2].startswith("Konto: "), a["rolle"], [e[:2] for e in a["eintraege"]]],
                 ["menu", "appTopbarAccountMenu", True, "menu", [["menuitem", "-1"]] * 3])
        p.pruefe(f"{wo}: Einträge", [e[2].split(" ")[0] for e in a["eintraege"]], ["Mein", "Hell/Dunkel", "Abmelden"])
        await tab.js("document.getElementById('appTopbarAccountBtn').focus()")
        p.pruefe(f"{wo}: zu", await tab.js(MENUE), {"offen": False, "expanded": "false", "fokus": "knopf"})
        schritte = [("Enter", True, "/account"), ("ArrowDown", True, "appThemeToggle"), ("ArrowDown", True, "appTopbarLogout"),
                    ("ArrowDown", True, "/account"), ("ArrowUp", True, "appTopbarLogout"), ("Home", True, "/account"),
                    ("End", True, "appTopbarLogout"), ("Escape", False, "knopf"), ("ArrowDown", True, "/account"), ("Escape", False, "knopf"),
                    ("ArrowUp", True, "appTopbarLogout"), ("Tab", False, None)]
        for taste, offen, fokus in schritte:
            await _taste(tab, taste)
            m = await tab.js(MENUE)
            ist = [m["offen"], m["expanded"]] + ([m["fokus"]] if fokus else [])
            p.pruefe(f"{wo}: {taste}", ist, [offen, "true" if offen else "false"] + ([fokus] if fokus else []))
        # Hell/Dunkel per Tastatur
        vorher = await tab.js("document.documentElement.getAttribute('data-theme')")
        await tab.js("document.getElementById('appTopbarAccountBtn').focus()")
        await _taste(tab, "Enter")
        await _taste(tab, "ArrowDown")
        zustand_vorher = await tab.js("document.getElementById('appThemeState').textContent")
        await _taste(tab, "Enter")
        nachher = await tab.js("[document.documentElement.getAttribute('data-theme'),localStorage.getItem('erp_theme'),"
                               "document.getElementById('appThemeState').textContent,!document.getElementById('appTopbarAccountMenu').hidden]")
        neu = "light" if vorher == "dark" else "dark"
        p.pruefe(f"{wo}: Hell/Dunkel per Enter", [vorher, zustand_vorher, nachher],
                 ["dark" if thema == "dunkel" else "light", "dunkel" if thema == "dunkel" else "hell",
                  [neu, neu, "dunkel" if neu == "dark" else "hell", False]])
        # Klick daneben schließt
        await _maus(tab, "mousePressed", "#appTopbarAccountBtn", "left")
        await _maus(tab, "mouseReleased", "#appTopbarAccountBtn", "left")
        offen = (await tab.js(MENUE))["offen"]
        await tab.cmd("Input.dispatchMouseEvent", type="mousePressed", x=1000, y=32, button="left", clickCount=1)  # leere Stelle
        await tab.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=1000, y=32, button="left", clickCount=1)
        p.pruefe(f"{wo}: Klick öffnet, Klick daneben schließt", [offen, (await tab.js(MENUE))["offen"]], [True, False])
        p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])


async def _seitenregeln(tab, seed, p):
    """Die Einstellungen färben button:hover und button:active in der Akzentfarbe (Spezifität 0,1,1) -- im Kopf darf das nicht ankommen.
    :active ohne :hover gibt es beim Drücken per Leertaste: dann zählt allein die Spezifität der Regel des Kopfs."""
    await tab.anmelden(seed["cookies"][bg.BUERO])
    p.pruefe("Seitenregeln: geladen", await _laden(tab, seed, "einstellungen", "hell", 1440, 900), True)
    akzent = await tab.js(f"{FARBE}('--accent')")
    flaeche2 = await tab.js(f"{FARBE}('--ds-flaeche-2')")
    farbe = "(s=>getComputedStyle(document.querySelector(s)).backgroundColor)"
    await _maus(tab, "mouseMoved", "#appTopbarAccountBtn")
    hover = await tab.js(f"{farbe}('#appTopbarAccountBtn')")
    await tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=1000, y=32)  # leere Stelle der Kopfzeile
    await tab.js("document.getElementById('appTopbarAccountBtn').focus()")
    leer = dict(key=" ", code="Space", windowsVirtualKeyCode=32, nativeVirtualKeyCode=32)
    await tab.cmd("Input.dispatchKeyEvent", type="keyDown", text=" ", **leer)
    gedrueckt = await tab.js(f"[{farbe}('#appTopbarAccountBtn'),document.querySelector('#appTopbarAccountBtn:active')!==null]")
    await tab.cmd("Input.dispatchKeyEvent", type="keyUp", **leer)
    offen = (await tab.js(MENUE))["offen"]
    await _maus(tab, "mouseMoved", "#appTopbarLogout")
    eintrag = await tab.js(f"{farbe}('#appTopbarLogout')")
    await _taste(tab, "Escape")
    p.pruefe("Seitenregeln: Akzentfarbe der Seite bekannt", akzent.startswith("rgb") and akzent != flaeche2, True)
    p.pruefe("Seitenregeln: Kontoknopf unter der Maus flaeche-2, per Leertaste gedrückt durchsichtig (nie Akzent), Menüeintrag unter "
             "der Maus flaeche-2", [hover, gedrueckt, offen, eintrag], [flaeche2, ["rgba(0, 0, 0, 0)", True], True, flaeche2])
    p.pruefe("Seitenregeln: Menü zu, noch auf den Einstellungen", [(await tab.js(MENUE))["offen"], await tab.js("location.pathname")],
             [False, "/settings"])


TEILE = {"seitenleiste": _seitenleiste, "aktiv": _aktiv, "menueknopf": _menueknopf, "kopfzeile": _kopfzeile,
         "kontomenue": _kontomenue, "seitenregeln": _seitenregeln}
NUR: list = []


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=bg.STILL)
    await tab.browser_uhr_fest(seed["uhr_ms"])
    for name, teil in TEILE.items():
        if not NUR or name in NUR:
            await teil(tab, seed, p)


if __name__ == "__main__":
    eigene = argparse.ArgumentParser(add_help=False)
    eigene.add_argument("--nur")
    ns, rest = eigene.parse_known_args(sys.argv[1:])
    NUR.extend(t for t in (ns.nur or "").split(",") if t)
    unbekannt = [t for t in NUR if t not in TEILE]
    if unbekannt:
        sys.exit(f"unbekannte Teile: {unbekannt} (bekannt: {', '.join(TEILE)})")
    sys.argv = [sys.argv[0], *rest]
    sys.exit(klicktest_main(bg.befuellen, pruefen, beschreibung=__doc__, uhr="2026-10-14 10:00", zeitlimit_je_schritt=True,
                            chrome_argumente=bg.CHROME_ARGUMENTE))
