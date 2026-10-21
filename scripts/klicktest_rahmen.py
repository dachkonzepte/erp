"""Klicktest: Rahmen der Seiten, Stufe 2 „Rahmen“, Runde 1 (seit 1.8.163; Seitenleiste 1.8.162, Kopfzeile 1.8.163, Monteurskopf 1.8.164).

Geprüft wird im echten Browser auf den Testdaten der Bildgrundlage (scripts/bildgrundlage.py, stehende Uhr), hell und dunkel:

    Seitenleiste   in jeder Rolle bei 1440 × 900 und 1280 × 800 ohne Bildlauf, die Version unten im Fenster; 232 px breit, Logo-Zeile
                   52 px mit Kachel 36 px, Zeilen 36 px, vier Gruppen; Grund in --ds-navi-grund (dunkel in beiden Modi); aktiv genau der
                   Eintrag des Bereichs der Seite (Projektmappe -> Projekte, Rechnung -> Projekte, Kunde -> Stammdaten, Befunde, Suche
                   und Konto keiner), mit aria-current, 3 px Strich in --ds-marke-hell auf --ds-navi-aktiv
    Schrift        auf jeder Seite mit Leiste (Büro – Finanzen, seit 1.8.166): normale Einträge 500, der aktive 600 -- keine Seitenregel
                   greift hinein
    Menüknopf      klappt die Leiste ein (60 px) und wieder aus, aria-expanded folgt
    Kopfzeile      64 px, Suche 480 px breit, rechts der Kontoknopf mit Initialen im Kreis in --ds-aktion und dem vollen Namen
                   (ganz zu sehen); bei 412 px nur die Initialen, kein waagrechter Bildlauf
    Kontomenü      per Tastatur: Enter, Pfeil runter und Pfeil hoch am Knopf öffnen (Fokus auf den ersten bzw. letzten Eintrag),
                   Pfeile wandern im Kreis, Pos1/Ende, Escape schließt mit Fokus zurück am Knopf, Tab schließt; role menu/menuitem,
                   aria-haspopup, aria-controls, aria-expanded folgt; Mein Konto · Hell/Dunkel · Abmelden; Hell/Dunkel per Enter
                   schaltet data-theme um und zeigt den Zustand; Klick daneben schließt
    Vollname       seit 1.8.167: ist der Name im Kontoknopf gekürzt oder ausgeblendet (Büro bei 412 px, Monteurin mit schmalem Knopf),
                   steht er vollständig oben im Kontomenü; ganz zu sehen bleibt er dort verborgen; die Tastatur springt darüber
    Prüfvorlagen   seit 1.9.3 (Pilot): .ds-seite, Seitenkopf mit Titel 30 px und genau einer grünen Hauptaktion (Schrift
                   auf-aktion), Menü „⋮“ per Tastatur mit „Archivierte anzeigen“, Dachtyp ausgeschrieben, Karten 12 px und Knöpfe 10 px
                   Ecken, Leiste und Kontomenü unverändert (Farben, keine Linkfarbe); Kontrast jedes sichtbaren Texts gegen seinen
                   Hintergrund (4,5 : 1, großer Text 3 : 1) hell und dunkel, auch mit offenem Menü und offenem Editor
    Kopfgruppe     seit 1.9.7 die 15 Seiten der Gruppe „Titelzeilen und Titelkarten“ (Start, Aufgaben, Checklisten,
                   Checklisten-Vorlagen, Wartungen, Befunde, Eingangsrechnungen, Betriebskosten, Projekte, Finanzen, Mahnwesen,
                   Versandprotokoll, Changelog, Suche, Zeiterfassung), hell und dunkel: .ds-seite, genau ein h1 (das des Seitenkopfs) mit
                   dem Titel, höchstens eine grüne Hauptaktion (Schrift auf-aktion), das Menü „⋮“ mit seinen Einträgen (per Tastatur,
                   Umschalter wechseln ihren Text), jeder sichtbare Textlink im Inhalt in --ds-link, das erste Feld mit Fokus im Umriss
                   --ds-fokus, Kontrast jedes Texts; die Hauptaktion tut, was sie vorher tat (Editor offen, „+ Projekt“ nach
                   /projects/new)
    Seitenregeln   auf den Einstellungen (button:hover und button:active in der Akzentfarbe): Kontoknopf unter der Maus und per
                   Leertaste gedrückt (:active ohne :hover), Menüeintrag unter der Maus -- nie in der Akzentfarbe
    Monteurskopf   auf jeder Seite der Monteurin (Mobil, Objekt, Stundenzettel, Zeiterfassung, Betriebsmittel, Checkliste,
                   Checklisten je Auftrag, Einsatzbericht, Konto) bei 1280 × 620 und 800 × 1100: 64 px, einzeilig, keine Seitenleiste
                   und keine Kopfzeile des Büros, Name ganz zu sehen, Reiter 48 px mit 16 px, der richtige aktiv (3 px Strich in
                   marke-hell), Lupe 48 × 48 -- auch auf den drei Seiten mit button{min-height:44px;width:100%}; hell und dunkel; bei
                   412 px zwei Zeilen (112 px) mit Name; Lupe öffnet die Objektsuche mit Fokus im Feld, Escape schließt mit Fokus an
                   der Lupe; Kontomenü per Tastatur

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_rahmen.py [--nur TEIL[,TEIL]] [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

--nur: nur diese Teile (seitenleiste, aktiv, schrift, menueknopf, kopfzeile, kontomenue, vollname, pruefvorlagen, kopfgruppe,
seitenregeln, monteurskopf) -- für
Gegenproben, die nach 2 min
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

ROLLEN = (bg.BUERO, bg.BUERO_AUFTRAG, bg.ADMIN)  # die Monteurin hat seit 1.8.164 keine Seitenleiste mehr (Teil "monteurskopf")
GRUPPEN = {r: ["Übersicht", "Aufträge", "Kaufmännisch", "Verwaltung"] for r in ROLLEN}
SEITE_JE_ROLLE = {bg.BUERO: "start", bg.BUERO_AUFTRAG: "start", bg.ADMIN: "start"}
# Seiten der Monteurin -> aktiver Reiter
MONTEUR_SEITEN = {"mobil": "Einsätze", "mobil_objekt": "Einsätze", "stundenzettel": "Stundenzettel",
                  "zeiterfassung_monteur": "Zeiterfassung", "betriebsmittel_monteur": "Einsätze", "checkliste": "Einsätze",
                  "checklisten_auftrag": "Einsätze", "einsatzbericht": "Einsätze", "konto": None}
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
strich:a?[cs(a).boxShadow===F('--ds-marke-hell')+' 3px 0px 0px 0px inset',cs(a).backgroundColor===F('--ds-navi-aktiv'),cs(a).color,
cs(a).borderTopLeftRadius,Math.round(r(a).left-r(s).left),Math.round(r(s).right-r(a).right)]:null,
kachel_weiss:cs(s.querySelector('.app-sidebar-kachel')).backgroundColor==='rgb(255, 255, 255)',
bildmarke:s.querySelectorAll('.app-sidebar-kachel svg polygon').length,bild:!!s.querySelector('.app-sidebar-kachel img')}})()""" % FARBE

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

MKOPF = """(()=>{const F=%s;const w=document.getElementById('mobileHeaderWrap');const h=w&&w.querySelector('.mobile-header');
const r=e=>e?e.getBoundingClientRect():null;const cs=e=>getComputedStyle(e);
const teile=h?[h.querySelector('.mobile-header-kachel'),h.querySelector('.mobile-nav'),document.getElementById('mobileSearchToggle'),
document.getElementById('appTopbarAccountBtn')]:[];
const mitten=teile.map(e=>e?Math.round(r(e).top+r(e).height/2):null);const name=h&&h.querySelector('.app-konto-name');
const reiter=h?[...h.querySelectorAll('.mobile-nav-reiter')]:[];const aktiv=reiter.filter(a=>a.classList.contains('active'));
const lupe=document.getElementById('mobileSearchToggle');
return {hoehe:h?Math.round(r(h).height):null,wrap:w?Math.round(r(w).height):null,
einzeilig:mitten.every(m=>m!==null)&&Math.max(...mitten)-Math.min(...mitten)<=2,
leiste:!!document.getElementById('appSidebar'),topbar:!!document.querySelector('.app-topbar'),
name:name?name.textContent:null,name_ganz:!!name&&cs(name).display!=='none'&&r(name).width>0&&name.scrollWidth<=name.clientWidth,
reiter:reiter.map(a=>[a.textContent.trim(),Math.round(r(a).height),cs(a).fontSize]),
aktiv:aktiv.map(a=>[a.textContent.trim(),a.getAttribute('aria-current'),cs(a).boxShadow===F('--ds-marke-hell')+' 0px -3px 0px 0px inset',
cs(a).backgroundColor===F('--ds-navi-aktiv'),cs(a).borderTopLeftRadius,cs(a).color,cs(a).fontWeight]),
lupe:lupe?[Math.round(r(lupe).width),Math.round(r(lupe).height)]:null,grund_navi:h?cs(h).backgroundColor===F('--ds-navi-grund'):null,
kachel:h?(k=>[Math.round(r(k).width),cs(k).backgroundColor,k.querySelectorAll('svg polygon').length,!!k.querySelector('img')])(h.querySelector('.mobile-header-kachel')):null,
breit_scroll:document.documentElement.scrollWidth>innerWidth+1}})()""" % FARBE

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
            p.pruefe(f"{wo}: Bildmarke auf weißer Kachel (seit 1.8.165)", [m["kachel_weiss"], m["bildmarke"], m["bild"]], [True, 3, False])
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
            # seit 1.8.169 der Strich als inset-Schatten innerhalb der 8-px-Ecken, Schrift weiß, 12 px vom Rand (bis dahin linker Rand)
            p.pruefe(f"{wo}: Strich 3 px in marke-hell (Schatten) auf navi-aktiv, weiß, Ecken 8 px, 12 px vom Rand", m["strich"],
                     [True, True, "rgb(255, 255, 255)", "8px", 12, 12])
        if i < 2:
            sel = "#appSidebar .app-sidebar-link:not(.active)"
            await _maus(tab, "mouseMoved", sel)
            # seit 1.9.1 der Wert --ds-navi-hover (hell #2A3238, dunkel #171D20; bis dahin fest #2A3238)
            p.pruefe(f"{wo}: Hover eines anderen Eintrags in navi-hover mit 8 px Ecken", await tab.js(
                f"(e=>[getComputedStyle(e).backgroundColor==={FARBE}('--ds-navi-hover'),getComputedStyle(e).borderTopLeftRadius])"
                f"(document.querySelector({json.dumps(sel)}))"), [True, "8px"])
            await tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=900, y=500)


SCHRIFT = """(()=>{const s=document.getElementById('appSidebar');if(!s)return null;const w=e=>getComputedStyle(e).fontWeight;
const l=[...s.querySelectorAll('.app-sidebar-link')];
return {normal:[...new Set(l.filter(a=>!a.classList.contains('active')).map(a=>w(a.querySelector('.app-sidebar-label'))))],
aktiv:l.filter(a=>a.classList.contains('active')).map(a=>w(a.querySelector('.app-sidebar-label')))}})()"""


async def _schrift(tab, seed, p):
    """Seit 1.8.166: Schriftstärke der Einträge auf jeder Seite, die das Büro mit Leiste öffnet."""
    await tab.anmelden(seed["cookies"][bg.BUERO])
    mit_leiste = 0
    for a in bg.AUFNAHMEN:
        if bg.BUERO not in a.rollen or a.vorlage == "access_denied.html":
            continue
        if not await _laden(tab, seed, a.name, "hell", 1440, 900):
            p.pruefe(f"Schrift {a.name}: geladen", False, True)
            continue
        m = await tab.js(SCHRIFT)
        if m is None:
            continue  # Seite ohne Leiste (Monteursansicht)
        mit_leiste += 1
        p.pruefe(f"Schrift {a.name}: normal 500, aktiv 600", [m["normal"], sorted(set(m["aktiv"]))], [["500"], ["600"] if m["aktiv"] else []])
    p.pruefe("Schrift: Seiten mit Leiste geprüft", mit_leiste >= 40, True)


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
    # Bernd ist mit seinem Mitarbeiter verknüpft (Vor- und Nachname), Ada nicht -- dann zeigt der Knopf seit 1.8.168 den Anzeigenamen
    # des Kontos (bis dahin den Benutzernamen „ada“), app/auth.py::resolve_account_display()
    namen = {bg.BUERO: "Bernd Büro", bg.ADMIN: "Ada Admin"}
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


VOLLNAME = """(()=>{const v=document.getElementById('appKontoVollname'),m=document.getElementById('appTopbarAccountMenu');
const n=document.querySelector('#appTopbarAccountBtn .app-konto-name');const r=v.getBoundingClientRect();
return {offen:!m.hidden,sichtbar:!v.hidden&&r.width>0,text:v.textContent.trim(),ganz:v.scrollWidth<=v.clientWidth+1,
name_gekuerzt:n.offsetWidth===0||n.scrollWidth>n.clientWidth,fokus:document.activeElement&&(document.activeElement.id||document.activeElement.getAttribute('href'))}})()"""


async def _vollname(tab, seed, p):
    """Seit 1.8.167: der volle Name im Kontomenü, wenn der Knopf ihn kürzt."""
    await tab.anmelden(seed["cookies"][bg.BUERO])
    for breite, hoehe, gekuerzt in ((1440, 900, False), (412, 900, True)):
        wo = f"Vollname Büro {breite} px"
        p.pruefe(f"{wo}: geladen", await _laden(tab, seed, "projektmappe", "hell", breite, hoehe), True)
        await tab.js("document.getElementById('appTopbarAccountBtn').focus()")
        await _taste(tab, "Enter")
        m = await tab.js(VOLLNAME)
        p.pruefe(f"{wo}: Name im Knopf gekürzt → oben im Menü vollständig, Fokus auf dem ersten Eintrag",
                 [m["offen"], m["name_gekuerzt"], m["sichtbar"], m["text"], m["fokus"]], [True, gekuerzt, gekuerzt, "Bernd Büro", "/account"])
        await _taste(tab, "Escape")
    # Monteurin: der Knopf wird schmal gemacht (langer Name), danach Größenänderung -- wie ein schmales Fenster
    await tab.anmelden(seed["cookies"][bg.MONTEUR])
    for thema in ("hell", "dunkel"):
        wo = f"Vollname Monteurin {thema}"
        p.pruefe(f"{wo}: geladen", await _laden(tab, seed, "einsatzbericht", thema, 1280, 620), True)
        await tab.js("document.getElementById('appTopbarAccountBtn').click()")
        vorher = await tab.js(VOLLNAME)
        await _taste(tab, "Escape")
        await tab.js("document.querySelector('.mobile-header-wrap .app-konto').style.maxWidth='110px';dispatchEvent(new Event('resize'))")
        await tab.js("document.getElementById('appTopbarAccountBtn').focus()")
        await _taste(tab, "Enter")
        m = await tab.js(VOLLNAME)
        p.pruefe(f"{wo}: Name ganz → kein Kopf; gekürzt → Kopf mit vollem Namen, ganz zu sehen, Fokus auf dem ersten Eintrag",
                 [vorher["sichtbar"], m["name_gekuerzt"], m["sichtbar"], m["text"], m["ganz"], m["fokus"]],
                 [False, True, True, "Mia Monteurin", True, "/account"])
        await _taste(tab, "Escape")
    p.pruefe("Vollname: keine JS-Fehler", tab.fehler, [])


KONTRAST = """(()=>{const teil=c=>{const m=c.match(/rgba?\\(([^)]+)\\)/);if(!m)return null;const p=m[1].split(',').map(parseFloat);
return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}};
const lin=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};const L=c=>0.2126*lin(c.r)+0.7152*lin(c.g)+0.0722*lin(c.b);
const misch=(o,u)=>({r:o.r*o.a+u.r*(1-o.a),g:o.g*o.a+u.g*(1-o.a),b:o.b*o.a+u.b*(1-o.a),a:1});
const grund=el=>{const s=[];for(let e=el;e;e=e.parentElement){const c=teil(getComputedStyle(e).backgroundColor);if(c&&c.a>0){s.push(c);if(c.a>=1)break}}
let u={r:255,g:255,b:255,a:1};for(let i=s.length-1;i>=0;i--)u=misch(s[i],u);return u};
const sichtbar=e=>e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).opacity!=='0';
const elemente=[...document.querySelectorAll('main *, #seitenkopfMenue *')].filter(e=>sichtbar(e)&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()));
let min=99,schwach=[];
for(const e of elemente){const cs=getComputedStyle(e);const g=grund(e);const f=misch(teil(cs.color),g);const a=L(f),b=L(g);
const k=(Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);const px=parseFloat(cs.fontSize),w=parseInt(cs.fontWeight);
const gross=px>=24||(px>=18.66&&w>=700);const soll=gross?3:4.5;if(k<min)min=k;
if(k<soll)schwach.push(e.tagName+'.'+e.className+' „'+e.textContent.trim().slice(0,30)+'“ '+k.toFixed(2))}
return {anzahl:elemente.length,min:Math.round(min*100)/100,schwach}})()"""

PILOT = """(()=>{const cs=e=>getComputedStyle(e);const F=%s;const k=document.getElementById('seitenkopf');
const titel=document.getElementById('seitenkopfTitel');const aktion=[...k.querySelectorAll('.ds-knopf-aktion')];
const karte=document.querySelector('main .pv-karte');const knopf=document.querySelector('#templateRows .ds-knopf');
const leiste=document.querySelector('#appSidebar .app-sidebar-link:not(.active) .app-sidebar-label');
return {ds_seite:document.body.classList.contains('ds-seite'),titel:[titel.textContent,cs(titel).fontSize],
aktion:aktion.map(a=>[a.textContent.trim(),cs(a).backgroundColor===F('--ds-aktion'),cs(a).color===F('--ds-auf-aktion'),cs(a).borderTopLeftRadius]),
menue:!!document.getElementById('seitenkopfMenueKnopf'),karte:karte?cs(karte).borderTopLeftRadius:null,knopf:knopf?cs(knopf).borderTopLeftRadius:null,
dachtyp:[...document.querySelectorAll('#templateRows tr td:nth-child(2)')].map(t=>t.textContent.trim()),
leiste:leiste?cs(leiste).color===F('--ds-navi-text'):null}})()""" % FARBE

# Seit 1.9.4: ds-basis.css hat das Gewicht null (:where). Ein alter Knopf mit eigener Klasse (ohne Regel für Schrift und Ecken) bekommt
# Schrift und Ecken der Grundregeln, eine Klasse der Seite überstimmt sie. Eingeschoben, gemessen, wieder entfernt.
GEWICHT_NULL = """(()=>{const F=%s;const cs=e=>getComputedStyle(e);const s=document.createElement('style');
s.textContent='.alt-feld{border-radius:0}.alt-rot{color:rgb(170,0,0)}';document.head.appendChild(s);
const d=document.createElement('div');d.innerHTML='<button type="button" class="btn-alt">Alt</button><button type="button">Ohne</button>'
+'<a class="alt-link" href="#">Mit</a><a href="#">Ohne</a><input class="alt-feld"><a class="alt-rot" href="#">Rot</a>';
document.querySelector('main').appendChild(d);const [k1,k2,l1,l2,f,r]=d.children;const b=document.body;
const knopf=k=>[cs(k).fontFamily===cs(b).fontFamily,cs(k).fontSize===cs(b).fontSize,cs(k).borderTopLeftRadius];
const e={knopf_klasse:knopf(k1),knopf_ohne:knopf(k2),links:[cs(l1).color===F('--ds-link'),cs(l2).color===F('--ds-link')],
feld_klasse:cs(f).borderTopLeftRadius,link_rot:cs(r).color};d.remove();s.remove();return e})()""" % FARBE


async def _pruefvorlagen(tab, seed, p):
    """Seit 1.9.3: die Pilotseite Prüfvorlagen."""
    await tab.anmelden(seed["cookies"][bg.BUERO])
    for thema in ("hell", "dunkel"):
        wo = f"Prüfvorlagen {thema}"
        p.pruefe(f"{wo}: geladen", await _laden(tab, seed, "pruefvorlagen", thema, 1440, 900), True)
        m = await tab.js(PILOT)
        p.pruefe(f"{wo}: .ds-seite, Titel 30 px, genau eine grüne Hauptaktion (Schrift auf-aktion, Ecken 10 px), Menü „⋮“",
                 [m["ds_seite"], m["titel"], m["aktion"], m["menue"]],
                 [True, ["Prüfvorlagen", "30px"], [["+ Neue Vorlage", True, True, "10px"]], True])
        p.pruefe(f"{wo}: Karten 12 px, Knöpfe 10 px, Dachtyp wie gespeichert (Altwert markiert), Leiste unverändert",
                 [m["karte"], m["knopf"], m["dachtyp"], m["leiste"]],
                 ["12px", "10px", ["Flachdach", "flachdach nicht mehr verfügbar"], True])  # seit 1.9.6 der gespeicherte Wert, Altwert markiert
        g = await tab.js(GEWICHT_NULL)
        p.pruefe(f"{wo}: Grundregeln mit Gewicht null -- alter Knopf mit Klasse bekommt Schrift und Ecken wie einer ohne, Link mit und "
                 "ohne Klasse in Linkfarbe, die Klasse einer Seite überstimmt Ecken des Felds und Farbe des Links",
                 [g["knopf_klasse"], g["knopf_ohne"], g["links"], g["feld_klasse"], g["link_rot"]],
                 [[True, True, "10px"], [True, True, "10px"], [True, True], "0px", "rgb(170, 0, 0)"])
        k = await tab.js(KONTRAST)
        p.pruefe(f"{wo}: Kontrast jedes Texts ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", k["schwach"], [])
        # Menü „⋮“ per Tastatur, „Archivierte anzeigen“ schaltet um
        await tab.js("document.getElementById('seitenkopfMenueKnopf').focus()")
        await _taste(tab, "Enter")
        offen = await tab.js("[!document.getElementById('seitenkopfMenue').hidden,document.activeElement.id,"
                             "document.getElementById('seitenkopfMenueKnopf').getAttribute('aria-expanded')]")
        k_menue = await tab.js(KONTRAST)
        await _taste(tab, "Enter")
        nachher = await tab.js("[document.getElementById('seitenkopfMenue').hidden,"
                               "document.getElementById('archivierteUmschalten').textContent]")
        p.pruefe(f"{wo}: Menü per Enter offen (Fokus auf „Archivierte anzeigen“), Enter schaltet um und schließt",
                 [offen, nachher], [[True, "archivierteUmschalten", "true"], [True, "Archivierte ausblenden"]])
        p.pruefe(f"{wo}: Kontrast mit offenem Menü (kleinster {k_menue['min']} : 1)", k_menue["schwach"], [])
        # Kontomenü: „Mein Konto“ nicht in Linkfarbe
        await tab.js("document.getElementById('appTopbarAccountBtn').click()")
        p.pruefe(f"{wo}: „Mein Konto“ im Kontomenü in Textfarbe, nicht Linkfarbe", await tab.js(
            f"getComputedStyle(document.querySelector('#appTopbarAccountMenu a')).color==={FARBE}('--ds-text')"), True)
        await _taste(tab, "Escape")
        # Editor offen
        await tab.js("document.querySelector('[data-klick=\"neue-vorlage\"]').click()")
        k_editor = await tab.js(KONTRAST)
        p.pruefe(f"{wo}: Editor offen, Fokus im Feld, Kontrast (kleinster {k_editor['min']} : 1)",
                 [await tab.js("document.activeElement.id"), k_editor["schwach"]], ["editLabel", []])
        p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    p.pruefe("Prüfvorlagen 412 px: geladen", await _laden(tab, seed, "pruefvorlagen", "hell", 412, 900), True)
    k = await tab.js(KONTRAST)
    p.pruefe(f"Prüfvorlagen 412 px: Kontrast (kleinster {k['min']} : 1), kein waagrechter Bildlauf",
             [k["schwach"], await tab.js("document.documentElement.scrollWidth<=innerWidth+1")], [[], True])
    # seit 1.9.6: der Editor einer Prüfvorlage mit Altwert behält ihn -- vorgewählt als „… (nicht mehr verfügbar)“, Speichern ändert nichts
    adresse = f"/inspection-templates/{seed['pruefvorlage_altwert']}"
    bereit = "document.getElementById('editRoofType')&&document.getElementById('editRoofType').options.length>1"
    gewaehlt = "(s=>[s.value,s.options[s.selectedIndex].text])(document.getElementById('editRoofType'))"
    p.pruefe("Prüfvorlage mit Altwert: geladen", await tab.oeffnen(adresse, bereit), True)
    p.pruefe("Prüfvorlage mit Altwert: „flachdach (nicht mehr verfügbar)“ vorgewählt", await tab.js(gewaehlt),
             ["flachdach", "flachdach (nicht mehr verfügbar)"])
    await tab.js("saveTemplateMeta()")
    p.pruefe("Prüfvorlage mit Altwert: Kopf gespeichert", await tab.js("document.getElementById('metaStatus').textContent"), "Gespeichert.")
    p.pruefe("Prüfvorlage mit Altwert: nach dem Neuladen weiter „flachdach“",
             await tab.oeffnen(adresse + "?neu=1", bereit) and await tab.js(gewaehlt), ["flachdach", "flachdach (nicht mehr verfügbar)"])
    p.pruefe("Prüfvorlage mit Altwert: keine JS-Fehler", tab.fehler, [])


# Seit 1.9.7: die Gruppe „Titelzeilen und Titelkarten“ -- Aufnahme, Titel, Hauptaktion (oder None), Einträge des Menüs, was die
# Hauptaktion tut ("editor": #editorCard sichtbar, "/…": Ziel des Links, None: nicht geklickt -- legt sofort etwas an)
KOPFGRUPPE = (
    ("start", "Guten Morgen, Bernd Büro.", None, [], None),
    ("aufgaben", "Aufgaben", "+ Aufgabe", [], "editor"),
    ("checklisten", "Checklisten", None, ["Vorlagen verwalten"], None),
    ("checklistenvorlagen", "Checklisten-Vorlagen", "+ Neue Vorlage", ["Archivierte anzeigen"], None),
    ("wartungen", "Wartungen & Reparaturen", "+ Wartungsvertrag", ["Archivierte anzeigen"], "editor"),
    ("befunde", "Mängel", None, [], None),
    ("eingangsrechnungen", "Eingangsrechnungen", "+ Eingangsrechnung", [], "editor"),
    ("betriebskosten", "Betriebskosten-Übersicht", "+ Kostenposten", ["Inaktive anzeigen"], "editor"),
    ("projekte", "Projekte", "+ Projekt", [], "/projects/new"),
    ("finanzen", "Finanzen", None, [], None),
    ("mahnwesen", "Mahnwesen", None, ["Versandprotokoll der Mahnungen"], None),
    ("versandprotokoll", "Versandprotokoll", None, [], None),
    ("changelog", "Changelog", None, [], None),
    ("suche", "Suche", None, [], None),
    ("zeiterfassung", "Zeiterfassung", None, [], None),
)
UMSCHALTER = {"Archivierte anzeigen": "Archivierte ausblenden", "Inaktive anzeigen": "Inaktive ausblenden"}
KOPFGRUPPE_JS = """(()=>{const F=%s;const cs=e=>getComputedStyle(e);const k=document.getElementById('seitenkopf');
const akt=[...k.querySelectorAll('.ds-knopf-aktion')];
const links=[...document.querySelectorAll('main a[href]')].filter(a=>a.getClientRects().length&&!a.closest('#seitenkopf')
  &&!a.matches('.ds-knopf,.ds-menue-eintrag')&&['inline','inline-block'].includes(cs(a).display)
  &&cs(a).backgroundColor==='rgba(0, 0, 0, 0)'&&cs(a).borderTopStyle==='none');
return {ds:document.body.classList.contains('ds-seite'),h1:[...document.querySelectorAll('h1')].map(e=>[e.id,e.textContent.trim()]),
  aktion:akt.map(a=>[a.textContent.trim(),cs(a).backgroundColor===F('--ds-aktion'),cs(a).color===F('--ds-auf-aktion')]),
  menue:[...document.querySelectorAll('#seitenkopfMenue .ds-menue-eintrag')].map(e=>e.textContent.trim()),
  links:links.length,falsch:links.filter(a=>cs(a).color!==F('--ds-link')).map(a=>a.textContent.trim().slice(0,30)+' '+cs(a).color)}})()""" % FARBE
KOPFGRUPPE_FOKUS = """(()=>{const F=%s;const e=[...document.querySelectorAll('main input:not([type=checkbox]):not([type=radio]):not([type=hidden]),main select,main textarea')]
  .find(x=>x.getClientRects().length&&!x.disabled);if(!e)return 'kein Feld';e.focus();const s=getComputedStyle(e);
  const r=[s.outlineStyle,s.outlineColor===F('--ds-fokus')];e.blur();return r})()""" % FARBE


async def _kopfgruppe(tab, seed, p):
    """Seit 1.9.7: die 15 Seiten der Gruppe „Titelzeilen und Titelkarten“ im gemeinsamen Seitenkopf. Textlinks = Links in der Zeile
    (display inline/inline-block) ohne Fläche und Rahmen -- Zeilen- und Kachellinks (ganze Zeile klickbar, display block/flex) behalten
    ihre Textfarbe. Fokus: das kopflose Chrome hat keinen Fensterfokus, ohne Fokus-Emulation griffe :focus nicht."""
    await tab.cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    await tab.anmelden(seed["cookies"][bg.BUERO])
    for name, titel, aktion, menue, klick in KOPFGRUPPE:
        for thema in ("hell", "dunkel"):
            wo = f"Kopf {name} {thema}"
            p.pruefe(f"{wo}: geladen", await _laden(tab, seed, name, thema, 1440, 900), True)
            m = await tab.js(KOPFGRUPPE_JS)
            p.pruefe(f"{wo}: .ds-seite, genau ein h1 (Seitenkopf) „{titel}“, Hauptaktion {aktion or '—'}, Menü {menue or '—'}",
                     [m["ds"], m["h1"], m["aktion"], m["menue"]],
                     [True, [["seitenkopfTitel", titel]], [[aktion, True, True]] if aktion else [], menue])
            p.pruefe(f"{wo}: {m['links']} Textlinks im Inhalt, alle in --ds-link", m["falsch"], [])
            fokus = await tab.js(KOPFGRUPPE_FOKUS)
            p.pruefe(f"{wo}: erstes Feld mit Fokus im Umriss --ds-fokus", fokus if fokus == "kein Feld" else fokus[1],
                     "kein Feld" if fokus == "kein Feld" else True)
            k = await tab.js(KONTRAST)
            p.pruefe(f"{wo}: Kontrast ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", k["schwach"], [])
            if menue:
                await tab.js("document.getElementById('seitenkopfMenueKnopf').focus()")
                await _taste(tab, "Enter")
                offen = await tab.js("[!document.getElementById('seitenkopfMenue').hidden,document.activeElement.textContent.trim()]")
                k_menue = await tab.js(KONTRAST)
                eintrag = menue[0]
                if eintrag in UMSCHALTER:
                    await _taste(tab, "Enter")
                    nachher = await tab.js("[document.getElementById('seitenkopfMenue').hidden,"
                                           "document.querySelector('#seitenkopfMenue .ds-menue-eintrag').textContent.trim()]")
                    p.pruefe(f"{wo}: Menü per Enter offen (Fokus „{eintrag}“), Enter schaltet um und schließt", [offen, nachher],
                             [[True, eintrag], [True, UMSCHALTER[eintrag]]])
                else:
                    ziel = await tab.js("document.querySelector('#seitenkopfMenue .ds-menue-eintrag').getAttribute('href')")
                    await _taste(tab, "Escape")
                    p.pruefe(f"{wo}: Menü per Enter offen (Fokus „{eintrag}“), Link {ziel}, Escape schließt",
                             [offen, await tab.js("document.getElementById('seitenkopfMenue').hidden")], [[True, eintrag], True])
                p.pruefe(f"{wo}: Kontrast mit offenem Menü (kleinster {k_menue['min']} : 1)", k_menue["schwach"], [])
            if klick == "editor" and thema == "hell":
                await tab.js("document.querySelector('#seitenkopf .ds-knopf-aktion').click()")
                p.pruefe(f"{wo}: „{aktion}“ öffnet den Editor", await tab.warten(
                    "!document.getElementById('editorCard').classList.contains('hidden')", 10), True)
            elif klick and klick.startswith("/") and thema == "hell":
                p.pruefe(f"{wo}: „{aktion}“ führt nach {klick}", await tab.js(
                    "document.querySelector('#seitenkopf .ds-knopf-aktion').getAttribute('href')"), klick)
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    await tab.bild("kopfgruppe_zuletzt")


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


async def _monteurskopf(tab, seed, p):
    await tab.anmelden(seed["cookies"][bg.MONTEUR])
    for (breite, hoehe), thema in (((1280, 620), "hell"), ((800, 1100), "hell"), ((1280, 620), "dunkel"), ((800, 1100), "dunkel")):
        seiten = MONTEUR_SEITEN if thema == "hell" else {n: MONTEUR_SEITEN[n] for n in ("einsatzbericht", "konto", "zeiterfassung_monteur")}
        for name, reiter in seiten.items():
            wo = f"Monteurskopf {name} {thema} {breite}×{hoehe}"
            p.pruefe(f"{wo}: geladen", await _laden(tab, seed, name, thema, breite, hoehe), True)
            m = await tab.js(MKOPF)
            p.pruefe(f"{wo}: 64 px, einzeilig, ohne Leiste und Kopfzeile des Büros, Grund navi",
                     [m["hoehe"], m["wrap"], m["einzeilig"], m["leiste"], m["topbar"], m["grund_navi"], m["breit_scroll"]],
                     [64, 64, True, False, False, True, False])
            p.pruefe(f"{wo}: Name ganz zu sehen", [m["name"], m["name_ganz"]], ["Mia Monteurin", True])
            p.pruefe(f"{wo}: Reiter 48 px mit 16 px, Lupe 48 × 48", [m["reiter"], m["lupe"]],
                     [[["Einsätze", 48, "16px"], ["Zeiterfassung", 48, "16px"], ["Stundenzettel", 48, "16px"]], [48, 48]])
            # seit 1.8.170 auf navi-aktiv mit 10 px Ecken, der Strich als inset-Schatten (bis dahin unterer Rand von 3 px)
            # seit 1.9.0 Schrift weiß in 600 (bis dahin navi-text in 500)
            p.pruefe(f"{wo}: aktiver Reiter", m["aktiv"], [[reiter, "page", True, True, "10px", "rgb(255, 255, 255)", "600"]] if reiter else [])
            p.pruefe(f"{wo}: Bildmarke auf weißer Kachel 40 px (seit 1.8.165)", m["kachel"], [40, "rgb(255, 255, 255)", 3, False])
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    # seit 1.9.1: Hover eines nicht aktiven Reiters in navi-hover, hell und dunkel
    for thema in ("hell", "dunkel"):
        p.pruefe(f"Monteurskopf Hover {thema}: geladen", await _laden(tab, seed, "einsatzbericht", thema, 1280, 620), True)
        sel = ".mobile-header-wrap .mobile-nav-reiter:not(.active)"
        await _maus(tab, "mouseMoved", sel)
        p.pruefe(f"Monteurskopf Hover {thema}: anderer Reiter in navi-hover", await tab.js(
            f"getComputedStyle(document.querySelector({json.dumps(sel)})).backgroundColor==={FARBE}('--ds-navi-hover')"), True)
        await tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=640, y=400)
    # Telefon: zwei Zeilen, Name bleibt
    p.pruefe("Monteurskopf 412 px: geladen", await _laden(tab, seed, "einsatzbericht", "hell", 412, 900), True)
    m = await tab.js(MKOPF)
    p.pruefe("Monteurskopf 412 px: zwei Zeilen (112 px), Name ganz, kein waagrechter Bildlauf",
             [m["hoehe"], m["name"], m["name_ganz"], m["breit_scroll"]], [112, "Mia Monteurin", True, False])
    # Lupe und Kontomenü per Tastatur
    p.pruefe("Monteurskopf Lupe: geladen", await _laden(tab, seed, "einsatzbericht", "hell", 1280, 620), True)
    suche = ("(()=>{const l=document.getElementById('mobileSearchToggle'),s=document.getElementById('mobileSearchPanel');"
             "return [!s.hidden,l.getAttribute('aria-expanded'),document.activeElement&&document.activeElement.id]})()")
    await tab.js("document.getElementById('mobileSearchToggle').focus()")
    await _taste(tab, "Enter")
    p.pruefe("Monteurskopf Lupe: Enter öffnet die Suche, Fokus im Feld", await tab.js(suche), [True, "true", "mobileObjectSearch"])
    await _taste(tab, "Escape")
    p.pruefe("Monteurskopf Lupe: Escape schließt, Fokus an der Lupe", await tab.js(suche), [False, "false", "mobileSearchToggle"])
    await tab.js("document.getElementById('appTopbarAccountBtn').focus()")
    for taste, offen, fokus in (("Enter", True, "/account"), ("ArrowDown", True, "appThemeToggle"), ("End", True, "appTopbarLogout"),
                                ("Escape", False, "knopf")):
        await _taste(tab, taste)
        m = await tab.js(MENUE)
        p.pruefe(f"Monteurskopf Kontomenü: {taste}", [m["offen"], m["expanded"], m["fokus"]], [offen, "true" if offen else "false", fokus])
    p.pruefe("Monteurskopf: keine JS-Fehler", tab.fehler, [])


TEILE = {"seitenleiste": _seitenleiste, "aktiv": _aktiv, "schrift": _schrift, "menueknopf": _menueknopf, "kopfzeile": _kopfzeile,
         "kontomenue": _kontomenue, "vollname": _vollname, "pruefvorlagen": _pruefvorlagen, "kopfgruppe": _kopfgruppe,
         "seitenregeln": _seitenregeln, "monteurskopf": _monteurskopf}
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
