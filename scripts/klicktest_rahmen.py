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
    Datensatzkopf  seit 1.9.10 die 7 Seiten der Gruppe „Datensatz mit Pfad“ (Objekt, Dachfläche, Betriebsmittel, Wartungsvertrag,
                   Checklisten-Vorlage, Prüfvorlage, Einsatzbericht -- dieser auch als Monteurin), hell und dunkel: .ds-seite, genau ein
                   h1 mit dem Titel, Kennung, Untertitel, Status als lesbares Kennzeichen in der Farbe seiner Bedeutung, Pfad mit Texten
                   und Zielen, jeder Link im Pfad öffnet eine Seite (200 ohne Umleitung, HTML), höchstens eine grüne Hauptaktion, Menü
                   „⋮“ mit genau den geltenden Einträgen (verborgene verborgen, „Löschen“ in der Fehlerfarbe), per Tastatur (der
                   gesperrte und der verborgene Eintrag werden übersprungen), Textlinks in --ds-link, Fokus in --ds-fokus, Kontrast;
                   „Löschen“ fragt wie bisher, „Kopieren …“ öffnet die Karte mit vorausgefülltem Namen, Pausieren/Reaktivieren wechselt
                   Status und Menü; „Wartung durchführen“ öffnet den Einsatzbericht des neuen Auftrags mit dem Wartungsvertrag im Pfad
    Rechnungskopf  seit 1.9.13 die Rechnung (Abschlag der Testdaten) als Entwurf hell und dunkel: .ds-seite, ein h1 mit der Art, Kennung
                   „ohne Nummer“ als Kennzeichen neben dem Status „Entwurf“ (warn), Pfad Projekte / Kunde / Projekt / Auftrag /
                   Rechnung (jeder Link öffnet eine Seite), Netto/MwSt./Brutto im Kopf, einzige Aktion „PDF herunterladen“ neutral, kein
                   Menü, kein alter Kopf; Textlinks in --ds-link, Fokus in --ds-fokus, Kontrast; „PDF herunterladen“ öffnet das PDF
                   wie bisher; über die unveränderte Karte „Status“ festgeschrieben: Kennung = Rechnungsnummer, Status „Offen“ (info),
                   Beträge gleich
    Angebotskopf   seit 1.9.18 das Angebot (LV-Editor, beauftragt) hell und dunkel: .ds-seite, ein h1 mit der Bezeichnung, Kennung =
                   Angebotsnummer als Kennzeichen neben dem Status „Beauftragt“ (ok), Pfad Projekte / Kunde / Projekt / Angebot (jeder
                   Link öffnet eine Seite), Netto/Optional/MwSt./Brutto, „PDF-Vorschau“ neutral und die grüne Hauptaktion, Menü „⋮“ mit
                   Angebotsdetails und OZ neu nummerieren per Tastatur, kein alter Kopf, Links, Fokus, Kontrast; „PDF-Vorschau“ öffnet
                   das PDF, „Angebotsdetails“ den Reiter, die Hauptaktion den Auftrag
    Untermenü      seit 1.9.21 die Seiten mit Untermenü links (Stammdaten, Einstellungen, Backoffice) und mit Zurück-Link und Karte
                   (Konto -- auch als Monteurin --, Benutzer, Änderungshistorie, Adressimport, Leistungskatalog) hell und dunkel:
                   .ds-seite, ein h1 mit dem Titel, Untertitel, Pfad statt „← …“ (jeder Link öffnet eine Seite; die Seiten mit Untermenü
                   ohne Pfad), kein .back, Hauptaktion nur „+ Hinzufügen“ der Stammdaten, kein Menü, Links, Fokus, Kontrast; Stammdaten:
                   Titel und Ziel von „+ Hinzufügen“ folgen dem Bereich, Büro – Auftrag ohne „+ Hinzufügen“ bei Mitarbeitern;
                   Einstellungen behalten den Titel; „Aktualisieren“ im Backoffice lädt ohne Fehler
    Formularseiten seit 1.9.22 Stammdaten-Formular (Mitarbeiter bearbeiten, Kunde anlegen, Kontakt aus der Projektmappe) und Leistung im
                   Rahmen, hell und dunkel: Leiste („Stammdaten“ aktiv) und Kopfzeile, ein h1, Pfad bis zur Seite (jeder Link öffnet eine
                   Seite), „Abbrechen“ neutral zum bisherigen Zurück-Ziel und „Speichern“ grün im Kopf, der Knopf unten bleibt, Links,
                   Fokus, Kontrast; „Speichern“ oben speichert wie unten (Ziel wie bisher), eine abgelehnte Eingabe zeigt die Meldung im
                   Bild, „Abbrechen“ führt zurück ohne zu speichern; seit 1.9.23 fragt es „Änderungen verwerfen?“ nur nach einer
                   Änderung (abgelehnt bleibt die Seite, die Materialsuche der Leistung zählt nicht)
    Anfragen, AV   seit 1.9.24 Anfragen (Titel über den Kennzahlen) und Arbeitsvorbereitung (Pfad Projekte / Kunde / Projekt / Auftrag /
                   Arbeitsvorbereitung, Kennung, Status als Kennzeichen, Zeiterfassung im Menü) hell und dunkel: ein h1, Pfad (jeder Link
                   öffnet eine Seite), kein alter Kopf, keine Hauptaktion, Links, Fokus, Kontrast; der Status wechselt nach dem Speichern
    Monteursseiten seit 1.9.25 Checkliste, Checklisten zum Auftrag, Objekt, Betriebsmittel, Einsatzbericht und Konto als Monteurin bei
                   1280 × 620 hell und dunkel: Monteursrahmen mit Tablet-Maßen (Pfad 15 px, Titel 26 px, Knöpfe mindestens 48 px), Pfad
                   nach dem Laden (Einsätze, die Checkliste über „Checklisten zum Auftrag“; jeder Link öffnet eine Seite), Kennung, Status,
                   „PDF“ nur ohne Entwurf, kein alter Kopf, Links, Fokus, Kontrast; Checkliste und Checklisten zum Auftrag auch fürs Büro
                   (gewohnter Kopf 13/30/40 px, Pfad über Checklisten und den Auftrag)
    Anmeldung      seit 1.9.27 Anmeldung (ohne Anmeldung) und Sperrseite (Monteurin auf /projects) bei 1440 und 412 px, hell und
                   dunkel: .ds-seite, Bildmarke mit Schriftzug in weißer Kachel über dem Seitenkopf, ein h1 in Archivo 30 px, Text in
                   IBM Plex Sans, Kontrast in der Karte; Anmeldung mit Untertitel „Melde dich mit deinem Benutzernamen an.“ und Fokus
                   in --ds-fokus; Sperrseite ohne doppelten Text, „Zur Startseite“ grün nach /mobil
    Ecken          seit 1.9.30 Karten mit 12 px Ecken auf Büro-Seiten (Start, Projekte, Einstellungen, Rechnung, Formular, Checkliste,
                   Einsatzbericht) und 16 px im Monteursrahmen (die Seiten der Monteurin bei 1280 × 620), hell und dunkel; in /mobil
                   schließt „Checklisten zu diesem Auftrag“ an seine Karte an
    Seitenregeln   auf den Einstellungen (button:hover und button:active in der Akzentfarbe): Kontoknopf unter der Maus und per
                   Leertaste gedrückt (:active ohne :hover), Menüeintrag unter der Maus -- nie in der Akzentfarbe
    Monteurskopf   auf jeder Seite der Monteurin (Mobil, Objekt, Meine Zeiten -- bis 1.9.58 Stundenzettel und Zeiterfassung --,
                   Betriebsmittel, Checkliste,
                   Checklisten je Auftrag, Einsatzbericht, Konto) bei 1280 × 620 und 800 × 1100: 64 px, einzeilig, keine Seitenleiste
                   und keine Kopfzeile des Büros, Name ganz zu sehen, Reiter 48 px mit 16 px, der richtige aktiv (3 px Strich in
                   marke-hell), Lupe 48 × 48 -- auch auf den drei Seiten mit button{min-height:44px;width:100%}; hell und dunkel; bei
                   412 px zwei Zeilen (112 px) mit Name; Lupe öffnet die Objektsuche mit Fokus im Feld, Escape schließt mit Fokus an
                   der Lupe; Kontomenü per Tastatur

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_rahmen.py [--nur TEIL[,TEIL]] [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

--nur: nur diese Teile (seitenleiste, aktiv, schrift, menueknopf, kopfzeile, kontomenue, vollname, pruefvorlagen, kopfgruppe,
seitenregeln, monteurskopf, datensatzkopf, rechnungskopf, angebotskopf, untermenue, formularseiten, anfragen_av, monteursseiten,
anmeldung, ecken) -- für
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
MONTEUR_SEITEN = {"mobil": "Heute", "mobil_objekt": "Heute", "meine_zeiten": "Meine Zeiten",  # seit 1.9.59
                  "betriebsmittel_monteur": "Heute", "checkliste": "Heute",
                  "checklisten_auftrag": "Heute", "einsatzbericht": "Heute", "konto": None}
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
        seiten = MONTEUR_SEITEN if thema == "hell" else {n: MONTEUR_SEITEN[n] for n in ("einsatzbericht", "konto", "meine_zeiten")}
        for name, reiter in seiten.items():
            wo = f"Monteurskopf {name} {thema} {breite}×{hoehe}"
            p.pruefe(f"{wo}: geladen", await _laden(tab, seed, name, thema, breite, hoehe), True)
            m = await tab.js(MKOPF)
            p.pruefe(f"{wo}: 64 px, einzeilig, ohne Leiste und Kopfzeile des Büros, Grund navi",
                     [m["hoehe"], m["wrap"], m["einzeilig"], m["leiste"], m["topbar"], m["grund_navi"], m["breit_scroll"]],
                     [64, 64, True, False, False, True, False])
            p.pruefe(f"{wo}: Name ganz zu sehen", [m["name"], m["name_ganz"]], ["Mia Monteurin", True])
            p.pruefe(f"{wo}: Reiter 48 px mit 16 px, Lupe 48 × 48", [m["reiter"], m["lupe"]],
                     [[["Heute", 48, "16px"], ["Meine Zeiten", 48, "16px"]], [48, 48]])  # seit 1.9.59
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


# Seit 1.9.10: die Gruppe „Datensatz mit Pfad“ -- je Aufnahme und Rolle: Titel, Kennung, Untertitel, Pfad als [Text, Ziel] (None = die
# Seite selbst), Status [Text, Art], Hauptaktion (oder None), sichtbare Einträge des Menüs, der erste per Tastatur erreichbare (ein
# gesperrter wird übersprungen), Anfang der Rückfrage von „Löschen“; {…} aus den Testdaten und der Schnittstelle (_datensatz_werte())
DATENSATZKOPF = (
    dict(seite="objekt", rolle=bg.BUERO, titel="Halle Nord", kennung="", untertitel="Werkstr. 5, 52531 Übach-Palenberg",
         pfad=[["Stammdaten", "/master-data"], ["Hallenbau GmbH", "/customers/{kunde}"], ["Halle Nord", None]],
         status=["", "neutral"], aktion=None, menue=[]),
    dict(seite="dachflaeche", rolle=bg.BUERO, titel="Nord", kennung="", untertitel="Noch keine Angaben",
         pfad=[["Stammdaten", "/master-data"], ["Hallenbau GmbH", "/customers/{kunde}"], ["Halle Nord", "/properties/{objekt}"],
               ["Nord", None]],
         status=["", "neutral"], aktion=None, menue=["Archivieren", "Löschen"], loeschen="Diese Dachfläche inkl. aller Bauteile"),
    dict(seite="betriebsmittel", rolle=bg.BUERO, titel="Anlegeleiter 3-teilig", kennung="{inventarnummer}", untertitel="Leiter · Eigenständig",
         pfad=[["Stammdaten", "/master-data"], ["Betriebsmittel", "/master-data#assets"], ["Anlegeleiter 3-teilig", None]],
         status=["", "neutral"], aktion=None, menue=["Etikett drucken", "Löschen"], loeschen="Dieses Betriebsmittel wirklich löschen?"),
    dict(seite="wartungsvertrag", rolle=bg.BUERO, titel="Wartung Halle Nord", kennung="",
         untertitel="Hallenbau GmbH · Halle Nord · 12 Monate Intervall",
         pfad=[["Wartungen", "/maintenance-contracts"], ["Hallenbau GmbH", "/customers/{kunde}"], ["Halle Nord", "/properties/{objekt}"],
               ["Wartung Halle Nord", None]],
         status=["Aktiv", "info"], aktion="Wartung durchführen", menue=["Vorgang erstellen", "Pausieren", "Beenden", "Archivieren", "Löschen"],
         erster="Pausieren", loeschen="Diesen Wartungsvertrag wirklich löschen?"),
    dict(seite="checklistenvorlage", rolle=bg.BUERO, titel="Sicherheitscheck", kennung="", untertitel="Gültig: Fassung 1",
         pfad=[["Checklisten", "/checklisten"], ["Vorlagen", "/checklisten/vorlagen"], ["Sicherheitscheck", None]],
         status=["Veröffentlicht", "ok"], aktion="Neuen Entwurf anlegen", menue=["Kopieren …", "Archivieren", "Löschen"],
         loeschen="Diese Vorlage mit allen Fassungen wirklich löschen?", kopie="Sicherheitscheck (Kopie)"),
    dict(seite="pruefvorlage", rolle=bg.BUERO, titel="Flachdach-Wartung", kennung="", untertitel="Version {pruefvorlage_version}",
         pfad=[["Einstellungen", "/settings"], ["Prüfvorlagen", "/inspection-templates"], ["Flachdach-Wartung", None]],
         status=["", "neutral"], aktion=None, menue=["Vorlage kopieren …"], kopie="Flachdach-Wartung (Kopie)"),
    dict(seite="einsatzbericht", rolle=bg.BUERO, titel="Einsatzbericht", kennung="{auftragsnummer}", untertitel="Hallenbau GmbH",
         pfad=[["Projekte", "/projects"], ["Hallenbau GmbH", "/customers/{kunde}"], ["Dachsanierung Halle Nord", "/projects/{projekt}"],
               ["{auftragsnummer}", "/orders/{auftrag}"], ["Einsatzbericht", None]],
         status=["Beauftragt", "info"], aktion=None, menue=["Zeiterfassung (Auftrag)"]),
    dict(seite="einsatzbericht", rolle=bg.MONTEUR, titel="Einsatzbericht", kennung="{auftragsnummer}", untertitel="Hallenbau GmbH",
         pfad=[["Heute", "/mobil"], ["Einsatzbericht", None]], status=["", "neutral"], aktion=None, menue=["Zeiterfassung (Auftrag)"]),
)
DATENSATZKOPF_JS = """(()=>{const F=%s;const cs=e=>getComputedStyle(e);const k=document.getElementById('seitenkopf');
const st=document.getElementById('seitenkopfStatus');const eintraege=[...document.querySelectorAll('#seitenkopfMenue .ds-menue-eintrag')];
const links=[...document.querySelectorAll('main a[href]')].filter(a=>a.getClientRects().length&&!a.closest('#seitenkopf')
  &&!a.matches('.ds-knopf,.ds-menue-eintrag')&&['inline','inline-block'].includes(cs(a).display)
  &&cs(a).backgroundColor==='rgba(0, 0, 0, 0)'&&cs(a).borderTopStyle==='none');
return {ds:document.body.classList.contains('ds-seite'),h1:[...document.querySelectorAll('h1')].map(e=>[e.id,e.textContent.trim()]),
  kennung:document.getElementById('seitenkopfKennung').textContent,untertitel:document.getElementById('seitenkopfUntertitel').textContent,
  kennzeichen:(()=>{const k=document.getElementById('seitenkopfKennung'),t=document.getElementById('seitenkopfTitel'),s=document.getElementById('seitenkopfStatus');
    if(!k.textContent)return cs(k).display==='none'?'verborgen':'leer, aber sichtbar';const r=e=>e.getBoundingClientRect(),m=e=>r(e).top+r(e).height/2;
    return [cs(k).fontFamily.includes('IBM Plex Mono'),cs(k).borderTopStyle,cs(k).borderTopColor===F('--ds-linie-stark'),cs(k).color===F('--ds-text-2'),
      Math.abs(m(k)-m(t))<8,r(k).left>=r(t).right,!s.textContent||(Math.abs(m(k)-m(s))<2&&r(k).right<=r(s).left)]})(),
  status:[st.textContent,st.className.replace('ds-status ds-status-',''),cs(st).display!=='none'],
  pfad:[...document.querySelectorAll('#seitenkopfPfad .ds-kopf-pfadglied,#seitenkopfPfad .ds-kopf-pfadende')]
    .map(e=>[e.textContent,e.getAttribute('href'),e.getAttribute('aria-current')]),
  aktion:[...k.querySelectorAll('.ds-knopf-aktion')].filter(a=>cs(a).display!=='none')
    .map(a=>[a.textContent.trim(),cs(a).backgroundColor===F('--ds-aktion'),cs(a).color===F('--ds-auf-aktion')]),
  menue:eintraege.filter(e=>!e.hidden).map(e=>e.textContent.trim()),
  verborgen_sichtbar:eintraege.filter(e=>e.hidden&&cs(e).display!=='none').map(e=>e.textContent.trim()),
  loeschen:eintraege.filter(e=>!e.hidden&&e.textContent.trim()==='Löschen').map(e=>e.classList.contains('ds-menue-eintrag-fehler')),
  links:links.length,falsch:links.filter(a=>cs(a).color!==F('--ds-link')).map(a=>a.textContent.trim().slice(0,30)+' '+cs(a).color)}})()""" % FARBE
# jeder Link im Pfad: mit der Anmeldung der Seite geladen -- 200, ohne Umleitung (auf /login oder anderswohin), eine HTML-Seite
PFAD_OEFFNEN = """(async()=>{const r=[];for(const a of document.querySelectorAll('#seitenkopfPfad a[href]')){const h=a.getAttribute('href');
try{const x=await fetch(h,{credentials:'same-origin'});r.push([h,x.status,x.redirected,(x.headers.get('content-type')||'').split(';')[0]])}
catch(e){r.push([h,String(e)])}}return r})()"""


async def _datensatz_werte(tab, seed):
    """Werte, die erst die Schnittstelle kennt (Nummernkreis, Version der Prüfvorlage), gelesen mit der Anmeldung des Büros."""
    holen = "(u=>fetch(u).then(r=>r.json()))"
    return {**seed,
            "auftragsnummer": await tab.js(f"{holen}('/api/orders/{seed['auftrag']}').then(o=>o.order_number)"),
            "pruefvorlage_version": await tab.js(f"{holen}('/api/inspection-templates/{seed['pruefvorlage']}').then(t=>t.version)"),
            "inventarnummer": await tab.js(f"{holen}('/api/operational-assets/{seed['geraet']}').then(a=>a.asset_number||'')")}


async def _datensatzkopf(tab, seed, p):
    """Seit 1.9.10: die 7 Seiten der Gruppe „Datensatz mit Pfad“ (Einsatzbericht auch als Monteurin) im gemeinsamen Seitenkopf, hell und
    dunkel; dazu (hell) Menü per Tastatur, „Löschen“ mit der bisherigen Rückfrage (abgelehnt, nichts gelöscht), „Kopieren …“ öffnet die
    Karte mit vorausgefülltem Namen, am Wartungsvertrag Pausieren/Reaktivieren mit Status und Menü; zum Schluss „Wartung durchführen“ ->
    Einsatzbericht des neuen Auftrags mit dem Wartungsvertrag im Pfad."""
    await tab.cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    werte, angemeldet = None, None
    for f in DATENSATZKOPF:
        if f["rolle"] != angemeldet:
            await tab.anmelden(seed["cookies"][f["rolle"]])
            angemeldet = f["rolle"]
        for thema in ("hell", "dunkel"):
            wo = f"Datensatzkopf {f['seite']} ({f['rolle']}) {thema}"
            p.pruefe(f"{wo}: geladen", await _laden(tab, seed, f["seite"], thema, 1440, 900), True)
            if werte is None:
                werte = await _datensatz_werte(tab, seed)
            soll = lambda s: s.format(**werte) if isinstance(s, str) else s  # noqa: E731
            m = await tab.js(DATENSATZKOPF_JS)
            p.pruefe(f"{wo}: .ds-seite, genau ein h1 „{f['titel']}“, Kennung, Untertitel", [m["ds"], m["h1"], m["kennung"], m["untertitel"]],
                     [True, [["seitenkopfTitel", f["titel"]]], soll(f["kennung"]), soll(f["untertitel"])])
            p.pruefe(f"{wo}: Status „{f['status'][0]}“ ({f['status'][1]})", m["status"], [*f["status"], bool(f["status"][0])])
            # seit 1.9.11: Kennung als Kennzeichen in Mono mit Rahmen (linie-stark, Schrift text-2), in der Zeile des Titels, rechts davon
            # und links vom Status; ohne Kennung verborgen
            p.pruefe(f"{wo}: Kennung als Kennzeichen", m["kennzeichen"],
                     [True, "solid", True, True, True, True, True] if soll(f["kennung"]) else "verborgen")
            pfad = [[soll(t), soll(h) if h else None, None if h else "page"] for t, h in f["pfad"]]
            p.pruefe(f"{wo}: Pfad {' / '.join(g[0] for g in pfad)}", m["pfad"], pfad)
            offen = await tab.js(PFAD_OEFFNEN)
            p.pruefe(f"{wo}: jeder Link im Pfad öffnet eine Seite ({len(offen)} Links)",
                     [o for o in offen if o[1:] != [200, False, "text/html"]], [])
            p.pruefe(f"{wo}: Hauptaktion {f['aktion'] or '—'}, Menü {f['menue'] or '—'}, Löschen in Fehlerfarbe, Verborgenes verborgen",
                     [m["aktion"], m["menue"], m["loeschen"], m["verborgen_sichtbar"]],
                     [[[f["aktion"], True, True]] if f["aktion"] else [], f["menue"], [True] if "Löschen" in f["menue"] else [], []])
            p.pruefe(f"{wo}: {m['links']} Textlinks im Inhalt, alle in --ds-link", m["falsch"], [])
            fokus = await tab.js(KOPFGRUPPE_FOKUS)
            p.pruefe(f"{wo}: erstes Feld mit Fokus im Umriss --ds-fokus", fokus if fokus == "kein Feld" else fokus[1],
                     "kein Feld" if fokus == "kein Feld" else True)
            k = await tab.js(KONTRAST)
            p.pruefe(f"{wo}: Kontrast ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", k["schwach"], [])
            if f["menue"]:
                await tab.js("document.getElementById('seitenkopfMenueKnopf').focus()")
                await _taste(tab, "Enter")
                auf = await tab.js("[!document.getElementById('seitenkopfMenue').hidden,document.activeElement.textContent.trim()]")
                k_menue = await tab.js(KONTRAST)
                folge = []
                if f["seite"] == "wartungsvertrag" and thema == "hell":
                    for _ in range(4):
                        await _taste(tab, "ArrowDown")
                        folge.append(await tab.js("document.activeElement.textContent.trim()"))
                await _taste(tab, "Escape")
                zu = await tab.js("[document.getElementById('seitenkopfMenue').hidden,document.activeElement.id]")
                p.pruefe(f"{wo}: Menü per Enter offen (Fokus „{f.get('erster', f['menue'][0])}“), Escape schließt, Fokus am Knopf",
                         [auf, zu], [[True, f.get("erster", f["menue"][0])], [True, "seitenkopfMenueKnopf"]])
                p.pruefe(f"{wo}: Kontrast mit offenem Menü (kleinster {k_menue['min']} : 1)", k_menue["schwach"], [])
                if folge:
                    p.pruefe(f"{wo}: Pfeil runter springt über den gesperrten und den verborgenen Eintrag", folge,
                             ["Beenden", "Archivieren", "Löschen", "Pausieren"])
            if thema == "hell" and f.get("loeschen"):
                await tab.js("window.__dkRueckfragen=[];window.confirm=t=>{window.__dkRueckfragen.push(t);return false}")
                await tab.js("document.querySelector('#seitenkopfMenue [data-klick=loeschen]').click()")
                r = await tab.js("[window.__dkRueckfragen.length,(window.__dkRueckfragen[0]||'').slice(0,%d),location.pathname]" % len(f["loeschen"]))
                p.pruefe(f"{wo}: „Löschen“ fragt wie bisher („{f['loeschen']} …“), abgelehnt bleibt die Seite", r,
                         [1, f["loeschen"], bg.AUFNAHME[f["seite"]].pfad.format(**seed)])
            if thema == "hell" and f.get("kopie"):
                await tab.js("document.querySelector('#seitenkopfMenue [data-klick=kopie-oeffnen]').click()")
                r = await tab.js("[!document.getElementById('kopieKarte').hidden,document.getElementById('copyLabel').value,"
                                 "document.activeElement&&document.activeElement.id]")
                p.pruefe(f"{wo}: „Kopieren …“ öffnet die Karte, Name vorausgefüllt, Fokus im Feld", r, [True, f["kopie"], "copyLabel"])
            if thema == "hell" and f["seite"] == "wartungsvertrag":
                zustand = ("[document.getElementById('seitenkopfStatus').textContent,document.getElementById('seitenkopfStatus').className,"
                           "[...document.querySelectorAll('#seitenkopfMenue .ds-menue-eintrag')].filter(e=>!e.hidden).map(e=>e.textContent.trim())]")
                await tab.js("document.querySelector('#seitenkopfMenue [data-klick=pausieren]').click()")
                await tab.warten("document.getElementById('seitenkopfStatus').textContent==='Pausiert'", 10)
                p.pruefe(f"{wo}: „Pausieren“ -> Status Pausiert (neutral), im Menü „Reaktivieren“ statt „Pausieren“", await tab.js(zustand),
                         ["Pausiert", "ds-status ds-status-neutral", ["Vorgang erstellen", "Reaktivieren", "Beenden", "Archivieren", "Löschen"]])
                await tab.js("document.querySelector('#seitenkopfMenue [data-klick=reaktivieren]').click()")
                await tab.warten("document.getElementById('seitenkopfStatus').textContent==='Aktiv'", 10)
                p.pruefe(f"{wo}: „Reaktivieren“ -> wieder Aktiv (info)", await tab.js(zustand),
                         ["Aktiv", "ds-status ds-status-info", f["menue"]])
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    # „Wartung durchführen“ legt Auftrag und Bericht an und öffnet den Einsatzbericht -- der Pfad führt zurück zum Vertrag
    await tab.anmelden(seed["cookies"][bg.BUERO])
    p.pruefe("Datensatzkopf Wartung durchführen: geladen", await _laden(tab, seed, "wartungsvertrag", "hell", 1440, 900), True)
    await tab.js("document.getElementById('performMaintenanceBtn').click()")
    da = await tab.warten("location.pathname.endsWith('/service-reports')&&document.querySelectorAll('#seitenkopfPfad a').length>=5", 30)
    m = await tab.js(DATENSATZKOPF_JS)
    g = m["pfad"]
    p.pruefe("Datensatzkopf Wartung durchführen: Einsatzbericht des neuen Auftrags, Pfad Projekte / Kunde / Wartungsvertrag / Projekt / "
             "Auftrag / Einsatzbericht",
             [da, [x[:2] for x in g[:3]], len(g), g[3][1].startswith("/projects/") if len(g) > 3 else None,
              g[4][1] == "/orders/" + str(await tab.js("Number(location.pathname.split('/')[2])")) if len(g) > 4 else None, g[-1][:2]],
             [True, [["Projekte", "/projects"], ["Hallenbau GmbH", f"/customers/{seed['kunde']}"],
                     ["Wartung Halle Nord", f"/maintenance-contracts/{seed['vertrag']}"]], 6, True, True, ["Einsatzbericht", None]])
    offen = await tab.js(PFAD_OEFFNEN)
    p.pruefe(f"Datensatzkopf Wartung durchführen: jeder Link im Pfad öffnet eine Seite ({len(offen)} Links)",
             [o for o in offen if o[1:] != [200, False, "text/html"]], [])
    p.pruefe("Datensatzkopf Wartung durchführen: keine JS-Fehler", tab.fehler, [])
    await tab.bild("datensatzkopf_zuletzt")


# Seit 1.9.13: Seitenkopf der Rechnung (Testdaten der Bildgrundlage: Abschlag pauschal 12.000 € netto, Entwurf)
RECHNUNGSKOPF_JS = """(()=>{const F=%s;const cs=e=>getComputedStyle(e);const k=document.getElementById('seitenkopf');
const st=document.getElementById('seitenkopfStatus');const sichtbar=e=>e.getClientRects().length>0;
const links=[...document.querySelectorAll('main a[href]')].filter(a=>sichtbar(a)&&!a.closest('#seitenkopf')
  &&!a.matches('.ds-knopf,.ds-menue-eintrag')&&['inline','inline-block'].includes(cs(a).display)
  &&cs(a).backgroundColor==='rgba(0, 0, 0, 0)'&&cs(a).borderTopStyle==='none');
const kz=document.getElementById('seitenkopfKennung'),t=document.getElementById('seitenkopfTitel'),r=e=>e.getBoundingClientRect(),m=e=>r(e).top+r(e).height/2;
return {ds:document.body.classList.contains('ds-seite'),h1:[...document.querySelectorAll('h1')].map(e=>[e.id,e.textContent.trim()]),
  kennung:kz.textContent,untertitel:document.getElementById('seitenkopfUntertitel').textContent,
  status:[st.textContent,st.className.replace('ds-status ds-status-',''),cs(st).display!=='none'],
  kennzeichen:[cs(kz).fontFamily.includes('IBM Plex Mono'),cs(kz).borderTopStyle,Math.abs(m(kz)-m(t))<8,r(kz).right<=r(st).left],
  pfad:[...document.querySelectorAll('#seitenkopfPfad .ds-kopf-pfadglied,#seitenkopfPfad .ds-kopf-pfadende')]
    .map(e=>[e.textContent,e.getAttribute('href'),e.getAttribute('aria-current')]),
  aktionen:[...k.querySelectorAll('.ds-kopf-aktionen .ds-knopf')].filter(sichtbar)
    .map(b=>[b.textContent.trim(),b.classList.contains('ds-knopf-aktion'),cs(b).backgroundColor===F('--ds-flaeche'),cs(b).color===F('--ds-text')]),
  menue:!!document.getElementById('seitenkopfMenueKnopf'),
  kennzahlen:[...k.querySelectorAll('.ds-kopf-kennzahlen .ds-kennzahl')].map(e=>[e.querySelector('.ds-kennzahl-name').textContent,
    e.querySelector('.ds-kennzahl-wert').textContent]),
  alt:['breadcrumb','backOrder','statusBadge','invTitle'].filter(id=>document.getElementById(id)),
  links:links.length,falsch:links.filter(a=>cs(a).color!==F('--ds-link')).map(a=>a.textContent.trim().slice(0,30)+' '+cs(a).color)}})()""" % FARBE
RECHNUNG_BETRAEGE = [["Netto", "12.000,00\xa0€"], ["MwSt.", "2.280,00\xa0€"], ["Brutto", "14.280,00\xa0€"]]


async def _rechnungskopf(tab, seed, p):
    """Seit 1.9.13: Kopf der Rechnung im gemeinsamen Seitenkopf -- als Entwurf hell und dunkel (Pfad mit allen Links geöffnet, Kennung
    „ohne Nummer“, Status „Entwurf“, Netto/MwSt./Brutto, „PDF herunterladen“ als einzige, neutrale Aktion ohne Menü, kein alter Kopf
    mehr), dann über die unveränderte Karte „Status“ festgeschrieben: Kennung = Rechnungsnummer, Status „Offen“, Beträge gleich."""
    await tab.cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    await tab.anmelden(seed["cookies"][bg.BUERO])
    holen = "(u=>fetch(u).then(r=>r.json()))"
    auftragsnummer = None
    for thema in ("hell", "dunkel"):
        wo = f"Rechnungskopf Entwurf {thema}"
        p.pruefe(f"{wo}: geladen", await _laden(tab, seed, "rechnung", thema, 1440, 900), True)
        if auftragsnummer is None:
            auftragsnummer = await tab.js(f"{holen}('/api/orders/{seed['auftrag']}').then(o=>o.order_number)")
        m = await tab.js(RECHNUNGSKOPF_JS)
        p.pruefe(f"{wo}: .ds-seite, h1 „Abschlagsrechnung (Pauschal)“, Kennung „ohne Nummer“, Untertitel, kein alter Kopf",
                 [m["ds"], m["h1"], m["kennung"], m["untertitel"], m["alt"]],
                 [True, [["seitenkopfTitel", "Abschlagsrechnung (Pauschal)"]], "ohne Nummer", "Hallenbau GmbH · Halle Nord", []])
        p.pruefe(f"{wo}: Status „Entwurf“ (warn), Kennung als Kennzeichen daneben", [m["status"], m["kennzeichen"]],
                 [["Entwurf", "warn", True], [True, "solid", True, True]])
        p.pruefe(f"{wo}: Pfad Projekte / Kunde / Projekt / Auftrag / Rechnung", m["pfad"],
                 [["Projekte", "/projects", None], ["Hallenbau GmbH", f"/customers/{seed['kunde']}", None],
                  ["P-2026-0001", f"/projects/{seed['projekt']}", None], [auftragsnummer, f"/orders/{seed['auftrag']}", None],
                  ["Rechnung", None, "page"]])
        offen = await tab.js(PFAD_OEFFNEN)
        p.pruefe(f"{wo}: jeder Link im Pfad öffnet eine Seite ({len(offen)} Links)", [o for o in offen if o[1:] != [200, False, "text/html"]],
                 [])
        p.pruefe(f"{wo}: einzige Aktion „PDF herunterladen“, neutral (Fläche, Schrift text), kein Menü; Netto/MwSt./Brutto im Kopf",
                 [m["aktionen"], m["menue"], m["kennzahlen"]], [[["PDF herunterladen", False, True, True]], False, RECHNUNG_BETRAEGE])
        p.pruefe(f"{wo}: {m['links']} Textlinks im Inhalt, alle in --ds-link", m["falsch"], [])
        fokus = await tab.js(KOPFGRUPPE_FOKUS)
        p.pruefe(f"{wo}: erstes Feld mit Fokus im Umriss --ds-fokus", fokus if fokus == "kein Feld" else fokus[1],
                 "kein Feld" if fokus == "kein Feld" else True)
        k = await tab.js(KONTRAST)
        p.pruefe(f"{wo}: Kontrast ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", k["schwach"], [])
        if thema == "hell":
            await tab.js("window.__dkGeoeffnet=[];window.open=(...a)=>{window.__dkGeoeffnet.push(a);return null}")
            await tab.js("document.querySelector('#seitenkopf .ds-knopf').click()")
            pdf = await tab.js(f"fetch('/api/invoices/{seed['rechnung']}/pdf').then(r=>[r.status,r.headers.get('content-type')])")
            p.pruefe(f"{wo}: „PDF herunterladen“ öffnet das PDF der Rechnung wie bisher", [await tab.js("window.__dkGeoeffnet"), pdf],
                     [[[f"/api/invoices/{seed['rechnung']}/pdf", "_blank"]], [200, "application/pdf"]])
        p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    # Festschreiben über die Karte „Status“ (unverändert), Leistungszeitraum vorher wie über „Übernehmen“
    wo = "Rechnungskopf festgeschrieben"
    await tab.js(f"fetch('/api/invoices/{seed['rechnung']}',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
                 "body:JSON.stringify({service_period_start:'2026-10-01',service_period_end:'2026-10-14'})}).then(r=>r.status)")
    p.pruefe(f"{wo}: geladen", await _laden(tab, seed, "rechnung", "hell", 1440, 900), True)
    await tab.js("window.confirm=()=>true")
    await tab.js("[...document.querySelectorAll('#statusActions button')].find(b=>b.textContent==='Rechnung finalisieren').click()")
    fertig = await tab.warten("invoice&&invoice.status==='versendet'&&document.getElementById('seitenkopfStatus').textContent==='Offen'", 20)
    nummer = await tab.js(f"{holen}('/api/invoices/{seed['rechnung']}').then(i=>i.invoice_number)")
    m = await tab.js(RECHNUNGSKOPF_JS)
    p.pruefe(f"{wo}: Kennung = Rechnungsnummer, Status „Offen“ (info), Beträge gleich, Titel gleich",
             [fertig, bool(nummer), m["kennung"], m["status"], m["kennzahlen"], m["h1"]],
             [True, True, nummer, ["Offen", "info", True], RECHNUNG_BETRAEGE, [["seitenkopfTitel", "Abschlagsrechnung (Pauschal)"]]])
    p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    await tab.bild("rechnungskopf_zuletzt")


# Seit 1.9.18: Seitenkopf des Angebots (Testdaten der Bildgrundlage: A-2026-0001, beauftragt, Auftrag gleichauf mit dem Angebot)
ANGEBOTSKOPF_JS = """(()=>{const F=%s;const cs=e=>getComputedStyle(e);const k=document.getElementById('seitenkopf');
const st=document.getElementById('seitenkopfStatus');const sichtbar=e=>e.getClientRects().length>0;
const eintraege=[...document.querySelectorAll('#seitenkopfMenue .ds-menue-eintrag')];
const links=[...document.querySelectorAll('main a[href]')].filter(a=>sichtbar(a)&&!a.closest('#seitenkopf')
  &&!a.matches('.ds-knopf,.ds-menue-eintrag,.secondary')&&['inline','inline-block'].includes(cs(a).display)
  &&cs(a).backgroundColor==='rgba(0, 0, 0, 0)'&&cs(a).borderTopStyle==='none');
const kz=document.getElementById('seitenkopfKennung'),t=document.getElementById('seitenkopfTitel'),r=e=>e.getBoundingClientRect(),m=e=>r(e).top+r(e).height/2;
return {ds:document.body.classList.contains('ds-seite'),h1:[...document.querySelectorAll('h1')].map(e=>[e.id,e.textContent.trim()]),
  kennung:kz.textContent,untertitel:document.getElementById('seitenkopfUntertitel').textContent,
  status:[st.textContent,st.className.replace('ds-status ds-status-',''),cs(st).display!=='none'],
  kennzeichen:[cs(kz).fontFamily.includes('IBM Plex Mono'),cs(kz).borderTopStyle,Math.abs(m(kz)-m(t))<8,r(kz).right<=r(st).left],
  pfad:[...document.querySelectorAll('#seitenkopfPfad .ds-kopf-pfadglied,#seitenkopfPfad .ds-kopf-pfadende')]
    .map(e=>[e.textContent,e.getAttribute('href'),e.getAttribute('aria-current')]),
  aktionen:[...k.querySelectorAll('.ds-kopf-aktionen > .ds-knopf')].filter(sichtbar).map(b=>{const a=b.classList.contains('ds-knopf-aktion');
    return [b.textContent.trim(),a,a?cs(b).backgroundColor===F('--ds-aktion')&&cs(b).color===F('--ds-auf-aktion')
      :cs(b).backgroundColor===F('--ds-flaeche')&&cs(b).color===F('--ds-text')]}),
  menue:eintraege.filter(e=>!e.hidden).map(e=>e.textContent.trim()),
  verborgen_sichtbar:eintraege.filter(e=>e.hidden&&cs(e).display!=='none').map(e=>e.textContent.trim()),
  kennzahlen:[...k.querySelectorAll('.ds-kopf-kennzahlen .ds-kennzahl')].map(e=>[e.querySelector('.ds-kennzahl-name').textContent,
    e.querySelector('.ds-kennzahl-wert').textContent]),
  alt:['breadcrumb','quoteName','quoteContext','quoteStatusBadge'].filter(id=>document.getElementById(id)),
  links:links.length,falsch:links.filter(a=>cs(a).color!==F('--ds-link')).map(a=>a.textContent.trim().slice(0,30)+' '+cs(a).color)}})()""" % FARBE
ANGEBOT_BETRAEGE = [["Netto", "45.945,00\xa0€"], ["Optional", "0,00\xa0€"], ["MwSt.", "8.729,55\xa0€"], ["Brutto", "54.674,55\xa0€"]]


async def _angebotskopf(tab, seed, p):
    """Seit 1.9.18: Kopf des Angebots (LV-Editor) im gemeinsamen Seitenkopf -- hell und dunkel: .ds-seite, ein h1 mit der Bezeichnung,
    Kennung = Angebotsnummer als Kennzeichen neben dem Status „Beauftragt“ (ok), Pfad Projekte / Kunde / Projekt / Angebot (jeder Link
    öffnet eine Seite), Netto/Optional/MwSt./Brutto, „PDF-Vorschau“ neutral und die grüne Hauptaktion (hier „Auftrag AUF-… öffnen“), Menü
    „⋮“ mit Angebotsdetails und OZ neu nummerieren (der Link zum Auftrag verborgen -- der Hauptknopf führt hin), per Tastatur; kein alter
    Kopf; Links, Fokus, Kontrast. Hell zusätzlich: „PDF-Vorschau“ öffnet das PDF wie bisher, „Angebotsdetails“ öffnet den Reiter, die
    Hauptaktion öffnet den Auftrag."""
    await tab.cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    await tab.anmelden(seed["cookies"][bg.BUERO])
    holen = "(u=>fetch(u).then(r=>r.json()))"
    angebot = auftragsnummer = None
    for thema in ("hell", "dunkel"):
        wo = f"Angebotskopf {thema}"
        p.pruefe(f"{wo}: geladen", await _laden(tab, seed, "angebot", thema, 1440, 900), True)
        if angebot is None:
            angebot = await tab.js(f"{holen}('/api/quotes/{seed['angebot']}')")
            auftragsnummer = await tab.js(f"{holen}('/api/orders/{seed['auftrag']}').then(o=>o.order_number)")
        m = await tab.js(ANGEBOTSKOPF_JS)
        p.pruefe(f"{wo}: .ds-seite, h1 = Bezeichnung, Kennung = Angebotsnummer, Untertitel, kein alter Kopf",
                 [m["ds"], m["h1"], m["kennung"], m["untertitel"], m["alt"]],
                 [True, [["seitenkopfTitel", angebot["title"]]], angebot["quote_number"],
                  f"{angebot['customer_name']} · {angebot['project_number']} · {angebot['property_name'] or 'ohne Objekt'}", []])
        p.pruefe(f"{wo}: Status „Beauftragt“ (ok), Kennung als Kennzeichen daneben", [m["status"], m["kennzeichen"]],
                 [["Beauftragt", "ok", True], [True, "solid", True, True]])
        p.pruefe(f"{wo}: Pfad Projekte / Kunde / Projekt / Angebot", m["pfad"],
                 [["Projekte", "/projects", None], [angebot["customer_name"], f"/customers/{seed['kunde']}", None],
                  [angebot["project_number"], f"/projects/{seed['projekt']}", None], ["Angebot", None, "page"]])
        offen = await tab.js(PFAD_OEFFNEN)
        p.pruefe(f"{wo}: jeder Link im Pfad öffnet eine Seite ({len(offen)} Links)", [o for o in offen if o[1:] != [200, False, "text/html"]],
                 [])
        p.pruefe(f"{wo}: „PDF-Vorschau“ neutral, Hauptaktion grün; Menü Angebotsdetails, OZ neu nummerieren; Kennzahlen",
                 [m["aktionen"], m["menue"], m["verborgen_sichtbar"], m["kennzahlen"]],
                 [[["PDF-Vorschau", False, True], [f"Auftrag {auftragsnummer} öffnen", True, True]],
                  ["Angebotsdetails", "OZ neu nummerieren"], [], ANGEBOT_BETRAEGE])
        p.pruefe(f"{wo}: {m['links']} Textlinks im Inhalt, alle in --ds-link", m["falsch"], [])
        fokus = await tab.js(KOPFGRUPPE_FOKUS)
        p.pruefe(f"{wo}: erstes Feld mit Fokus im Umriss --ds-fokus", fokus if fokus == "kein Feld" else fokus[1],
                 "kein Feld" if fokus == "kein Feld" else True)
        k = await tab.js(KONTRAST)
        p.pruefe(f"{wo}: Kontrast ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", k["schwach"], [])
        await tab.js("document.getElementById('seitenkopfMenueKnopf').focus()")
        await _taste(tab, "Enter")
        auf = await tab.js("[!document.getElementById('seitenkopfMenue').hidden,document.activeElement.textContent.trim()]")
        await _taste(tab, "ArrowDown")
        zweiter = await tab.js("document.activeElement.textContent.trim()")
        await _taste(tab, "Escape")
        zu = await tab.js("[document.getElementById('seitenkopfMenue').hidden,document.activeElement.id]")
        p.pruefe(f"{wo}: Menü per Enter offen (Fokus „Angebotsdetails“), Pfeil runter, Escape schließt mit Fokus am Knopf",
                 [auf, zweiter, zu], [[True, "Angebotsdetails"], "OZ neu nummerieren", [True, "seitenkopfMenueKnopf"]])
        if thema == "hell":
            await tab.js("window.__dkGeoeffnet=[];window.open=(...a)=>{window.__dkGeoeffnet.push(a);return null}")
            await tab.js("document.querySelector('#seitenkopf [data-klick=\"pdf-vorschau\"]').click()")
            pdf = await tab.js(f"fetch('/api/quotes/{seed['angebot']}/pdf').then(r=>[r.status,r.headers.get('content-type')])")
            p.pruefe(f"{wo}: „PDF-Vorschau“ öffnet das PDF des Angebots wie bisher", [await tab.js("window.__dkGeoeffnet"), pdf],
                     [[[f"/api/quotes/{seed['angebot']}/pdf", "_blank"]], [200, "application/pdf"]])
            await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
            await tab.js("document.querySelector('#seitenkopfMenue [data-klick=\"angebotsdetails\"]').click()")
            reiter = await tab.js("[!document.getElementById('panelDetails').classList.contains('hidden'),"
                                  "document.getElementById('tabDetails').classList.contains('active')]")
            p.pruefe(f"{wo}: „Angebotsdetails“ im Menü öffnet den Reiter", reiter, [True, True])
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
            await tab.js("document.getElementById('orderButton').click()")
            ziel = await tab.warten(f"location.pathname==='/orders/{seed['auftrag']}'", 20)
            p.pruefe(f"{wo}: Hauptaktion öffnet den Auftrag", ziel, True)
        else:
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    await tab.bild("angebotskopf_zuletzt")


# Seit 1.9.21: Seitenkopf der Gruppen „Untermenü links“ (K5) und „Zurück-Link + Karte“ (K6)
UNTERMENUE = (
    dict(seite="stammdaten", rolle=bg.BUERO, titel="Kunden", untertitel="2 Kundenstammsätze", pfad=[], aktion="+ Hinzufügen"),
    dict(seite="einstellungen", rolle=bg.BUERO, titel="Einstellungen", untertitel="", pfad=[], aktion=None),
    dict(seite="backoffice", rolle=bg.BUERO, titel="Zeiterfassungs-Backoffice",
         untertitel="Kontrolle, Monatsauswertung, Stundenzettel, Abschluss und Lohnexport.", pfad=[], aktion=None),
    dict(seite="konto", rolle=bg.BUERO, titel="Mein Konto", untertitel="", pfad=[["Start", "/"], ["Mein Konto", None]], aktion=None),
    dict(seite="konto", rolle=bg.MONTEUR, titel="Mein Konto", untertitel="", pfad=[["Heute", "/mobil"], ["Mein Konto", None]],
         aktion=None),
    dict(seite="benutzer", rolle=bg.ADMIN, titel="Benutzer und Zugriff", untertitel="",
         pfad=[["Einstellungen", "/settings"], ["Benutzer und Zugriff", None]], aktion=None),
    dict(seite="verlauf", rolle=bg.BUERO, titel="Änderungshistorie", untertitel="",
         pfad=[["Einstellungen", "/settings"], ["Änderungshistorie", None]], aktion=None),
    dict(seite="adressimport", rolle=bg.ADMIN, titel="Adressimport", untertitel="",
         pfad=[["Einstellungen", "/settings"], ["Adressimport", None]], aktion=None),
    dict(seite="leistungskatalog", rolle=bg.BUERO, titel="Leistungskatalog", untertitel="",
         pfad=[["Stammdaten", "/master-data"], ["Leistungskataloge", "/master-data#catalogs"], ["Leistungskatalog", None]], aktion=None),
)
HINZUFUEGEN = ("(()=>{const a=document.getElementById('addLink');return [document.getElementById('seitenkopfTitel').textContent,"
               "a.getAttribute('href'),a.hidden,getComputedStyle(a).display!=='none',location.hash]})()")


async def _untermenue(tab, seed, p):
    """Seit 1.9.21: die 3 Seiten mit Untermenü links (Stammdaten, Einstellungen, Backoffice) und die 5 mit Zurück-Link und Karte (Konto
    -- auch als Monteurin --, Benutzer, Änderungshistorie, Adressimport, Leistungskatalog) im gemeinsamen Seitenkopf, hell und dunkel:
    .ds-seite, genau ein h1 mit dem Titel, Untertitel, Pfad statt „← …“ (jeder Link öffnet eine Seite; ohne Pfad die Seiten mit
    Untermenü), kein .back mehr, Hauptaktion nur in den Stammdaten, kein Menü, Textlinks in --ds-link, Fokus in --ds-fokus, Kontrast.
    Dazu (hell): Stammdaten wechseln Titel und Ziel von „+ Hinzufügen“ mit dem Bereich, Büro – Auftrag sieht es bei Mitarbeitern nicht;
    Einstellungen behalten den Titel beim Wechsel des Bereichs; „Aktualisieren“ im Backoffice lädt ohne Fehler."""
    await tab.cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    # Büro – Auftrag legt keine Mitarbeiter an: „+ Hinzufügen“ dort verborgen, in den übrigen Bereichen sichtbar (wie bisher)
    await tab.anmelden(seed["cookies"][bg.BUERO_AUFTRAG])
    p.pruefe("Untermenü stammdaten (buero_auftrag): geladen", await _laden(tab, seed, "stammdaten", "hell", 1440, 900), True)
    await tab.js("document.querySelector('.side button[data-view=employees]').click()")
    mitarbeiter = await tab.js(HINZUFUEGEN)
    await tab.js("document.querySelector('.side button[data-view=suppliers]').click()")
    lieferanten = await tab.js(HINZUFUEGEN)
    p.pruefe("Untermenü stammdaten (buero_auftrag): „+ Hinzufügen“ bei Mitarbeitern verborgen, bei Lieferanten sichtbar",
             [mitarbeiter, lieferanten], [["Mitarbeiter", "/master-data/employees/new", True, False, "#employees"],
                                          ["Lieferanten", "/master-data/suppliers/new", False, True, "#suppliers"]])
    p.pruefe("Untermenü stammdaten (buero_auftrag): keine JS-Fehler", tab.fehler, [])
    angemeldet = None
    for f in UNTERMENUE:
        if f["rolle"] != angemeldet:
            await tab.anmelden(seed["cookies"][f["rolle"]])
            angemeldet = f["rolle"]
        for thema in ("hell", "dunkel"):
            wo = f"Untermenü {f['seite']} ({f['rolle']}) {thema}"
            p.pruefe(f"{wo}: geladen", await _laden(tab, seed, f["seite"], thema, 1440, 900), True)
            m = await tab.js(DATENSATZKOPF_JS)
            p.pruefe(f"{wo}: .ds-seite, genau ein h1 „{f['titel']}“, Untertitel, ohne Kennung und Status",
                     [m["ds"], m["h1"], m["untertitel"], m["kennzeichen"], m["status"]],
                     [True, [["seitenkopfTitel", f["titel"]]], f["untertitel"], "verborgen", ["", "neutral", False]])
            pfad = [[t, h, None if h else "page"] for t, h in f["pfad"]]
            p.pruefe(f"{wo}: Pfad {' / '.join(g[0] for g in pfad) or '—'}, kein „← …“ (.back)",
                     [m["pfad"], await tab.js("document.querySelectorAll('.back').length")], [pfad, 0])
            offen = await tab.js(PFAD_OEFFNEN)
            p.pruefe(f"{wo}: jeder Link im Pfad öffnet eine Seite ({len(offen)} Links)",
                     [o for o in offen if o[1:] != [200, False, "text/html"]], [])
            p.pruefe(f"{wo}: Hauptaktion {f['aktion'] or '—'}, kein Menü",
                     [m["aktion"], await tab.js("document.getElementById('seitenkopfMenueKnopf')===null")],
                     [[[f["aktion"], True, True]] if f["aktion"] else [], True])
            p.pruefe(f"{wo}: {m['links']} Textlinks im Inhalt, alle in --ds-link", m["falsch"], [])
            fokus = await tab.js(KOPFGRUPPE_FOKUS)
            p.pruefe(f"{wo}: erstes Feld mit Fokus im Umriss --ds-fokus", fokus if fokus == "kein Feld" else fokus[1],
                     "kein Feld" if fokus == "kein Feld" else True)
            k = await tab.js(KONTRAST)
            p.pruefe(f"{wo}: Kontrast ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", k["schwach"], [])
            if thema == "hell" and f["seite"] == "stammdaten":
                vorher = await tab.js(HINZUFUEGEN)
                await tab.js("document.querySelector('.side button[data-view=properties]').click()")
                nachher = await tab.js(HINZUFUEGEN)
                p.pruefe(f"{wo}: „Objekte“ im Untermenü -> Titel Objekte, „+ Hinzufügen“ legt ein Objekt an", [vorher, nachher],
                         [["Kunden", "/master-data/customers/new", False, True, ""],
                          ["Objekte", "/master-data/properties/new", False, True, "#properties"]])
            if thema == "hell" and f["seite"] == "einstellungen":
                await tab.js("document.querySelector('[data-settings-section=numbers]').click()")
                r = await tab.js("[document.getElementById('seitenkopfTitel').textContent,location.hash,"
                                 "document.querySelector('.settings-section.active h2').textContent.trim()]")
                p.pruefe(f"{wo}: Bereich Nummernkreise gewählt, Titel bleibt „Einstellungen“", r, ["Einstellungen", "#numbers", "Nummernkreise"])
            if thema == "hell" and f["seite"] == "backoffice":
                await tab.warte_auf_neu_geladene_liste("document.querySelector('.card.toolbar button').click()", "#metrics")
                p.pruefe(f"{wo}: „Aktualisieren“ lädt die Kennzahlen neu, der Kopf bleibt",
                         [await tab.js("document.querySelectorAll('#metrics .metric').length>0"),
                          await tab.js("document.getElementById('seitenkopfTitel').textContent")], [True, f["titel"]])
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    await tab.bild("untermenue_zuletzt")


# Seit 1.9.22: die Formularseiten Stammdaten-Formular und Leistung im Rahmen
FORMULARSEITEN = (
    dict(seite="stammdaten_mitarbeiter", adresse=None, titel="Mitarbeiter bearbeiten",
         pfad=[["Stammdaten", "/master-data"], ["Mitarbeiter", "/master-data#employees"], ["Mitarbeiter bearbeiten", None]],
         abbrechen="/master-data#employees"),
    dict(seite="leistung", adresse=None, titel="Leistung bearbeiten",
         pfad=[["Stammdaten", "/master-data"], ["Leistungskataloge", "/master-data#catalogs"], ["Leistungskatalog", "/leistungskatalog"],
               ["Leistung bearbeiten", None]], abbrechen="/leistungskatalog"),
    dict(seite="stammdaten_mitarbeiter", adresse="/master-data/customers/new", titel="Kunde anlegen",
         pfad=[["Stammdaten", "/master-data"], ["Kunden", "/master-data#customers"], ["Kunde anlegen", None]], abbrechen="/master-data#customers"),
    dict(seite="stammdaten_mitarbeiter", adresse="/master-data/contacts/new?projekt={projekt}", titel="Kontakt anlegen",
         pfad=[["Projekte", "/projects"], ["Projektmappe", "/projects/{projekt}#sec-participants"], ["Kontakt anlegen", None]],
         abbrechen="/projects/{projekt}#sec-participants"),
)
FORMULAR_JS = """(()=>{const F=%s;const cs=e=>getComputedStyle(e);const k=document.getElementById('seitenkopf');
const knoepfe=[...k.querySelectorAll('.ds-kopf-aktionen .ds-knopf')].filter(e=>cs(e).display!=='none');
const unten=document.getElementById('saveBtn');const aktiv=[...document.querySelectorAll('#appSidebar .app-sidebar-link.active')];
return {knoepfe:knoepfe.map(e=>[e.textContent.trim(),e.getAttribute('href'),e.classList.contains('ds-knopf-aktion'),
    cs(e).backgroundColor===F(e.classList.contains('ds-knopf-aktion')?'--ds-aktion':'--ds-flaeche')]),
  unten:[unten.textContent.trim(),unten.getAttribute('onclick'),cs(unten).display!=='none'],
  leiste:[aktiv.map(a=>a.dataset.bereich),aktiv.map(a=>a.getAttribute('aria-current'))],kopfzeile:!!document.querySelector('.app-topbar')}})()""" % FARBE
IM_BILD = ("(()=>{const r=document.getElementById('msg').getBoundingClientRect();"
           "return [document.getElementById('msg').textContent,r.top>=0&&r.bottom<=innerHeight,location.pathname]})()")


async def _formular_laden(tab, seed, f, thema):
    if not f["adresse"]:
        return await _laden(tab, seed, f["seite"], thema, 1440, 900)
    await tab.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark" if thema == "dunkel" else "light"}])
    await tab.cmd("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    ok = await tab.oeffnen(f["adresse"].format(**seed), bg.BEREIT, timeout=45)
    await tab.js(bg.RUHE)
    return ok


async def _formularseiten(tab, seed, p):
    """Seit 1.9.22: Stammdaten-Formular (Mitarbeiter bearbeiten, Kunde anlegen, Kontakt aus der Projektmappe) und Leistung im Rahmen,
    hell und dunkel: Leiste mit „Stammdaten“ aktiv und Kopfzeile, .ds-seite, ein h1 mit dem Titel, Pfad bis zur Seite (jeder Link öffnet
    eine Seite), im Kopf „Abbrechen“ neutral zum bisherigen Zurück-Ziel und „Speichern“ grün, der Knopf unten bleibt; Links, Fokus,
    Kontrast. Dazu (hell): „Speichern“ im Kopf speichert wie der Knopf unten (Mitarbeiter -> Liste der Mitarbeiter, Leistung -> Katalog),
    eine abgelehnte Eingabe zeigt die Meldung unten im Bild und die Seite bleibt; „Abbrechen“ führt zum Zurück-Ziel."""
    await tab.cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    await tab.anmelden(seed["cookies"][bg.BUERO])
    for f in FORMULARSEITEN:
        for thema in ("hell", "dunkel"):
            wo = f"Formular {f['adresse'] or f['seite']} {thema}"
            p.pruefe(f"{wo}: geladen", await _formular_laden(tab, seed, f, thema), True)
            await tab.warten("document.getElementById('seitenkopfTitel').textContent===%s" % json.dumps(f["titel"]), 10)
            m = await tab.js(DATENSATZKOPF_JS)
            p.pruefe(f"{wo}: .ds-seite, genau ein h1 „{f['titel']}“", [m["ds"], m["h1"]], [True, [["seitenkopfTitel", f["titel"]]]])
            pfad = [[t, h.format(**seed) if h else None, None if h else "page"] for t, h in f["pfad"]]
            p.pruefe(f"{wo}: Pfad {' / '.join(g[0] for g in pfad)}", m["pfad"], pfad)
            offen = await tab.js(PFAD_OEFFNEN)
            p.pruefe(f"{wo}: jeder Link im Pfad öffnet eine Seite ({len(offen)} Links)",
                     [o for o in offen if o[1:] != [200, False, "text/html"]], [])
            r = await tab.js(FORMULAR_JS)
            p.pruefe(f"{wo}: Leiste (Stammdaten aktiv) und Kopfzeile; im Kopf „Abbrechen“ neutral, „Speichern“ grün; Knopf unten bleibt",
                     [r["leiste"], r["kopfzeile"], r["knoepfe"], r["unten"]],
                     [[["stammdaten"], ["page"]], True, [["Abbrechen", f["abbrechen"].format(**seed), False, True], ["Speichern", None, True, True]],
                      ["Speichern", "save()", True]])
            p.pruefe(f"{wo}: {m['links']} Textlinks im Inhalt, alle in --ds-link", m["falsch"], [])
            fokus = await tab.js(KOPFGRUPPE_FOKUS)
            p.pruefe(f"{wo}: erstes Feld mit Fokus im Umriss --ds-fokus", fokus if fokus == "kein Feld" else fokus[1],
                     "kein Feld" if fokus == "kein Feld" else True)
            k = await tab.js(KONTRAST)
            p.pruefe(f"{wo}: Kontrast ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", k["schwach"], [])
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    # Leistung: Kurztext leer -> „Speichern“ oben lehnt ab wie unten, die Meldung rückt ins Bild; ausgefüllt speichert es und führt zum Katalog
    leistung = FORMULARSEITEN[1]
    p.pruefe("Formular leistung Speichern: geladen", await _formular_laden(tab, seed, leistung, "hell"), True)
    await tab.warten("document.getElementById('seitenkopfTitel').textContent==='Leistung bearbeiten'", 10)
    await tab.js("window.scrollTo(0,0);document.getElementById('shortText').value=''")
    await tab.js("document.getElementById('kopfSpeichern').click()")
    await tab.warten("document.getElementById('msg').textContent!==''", 10)
    p.pruefe("Formular leistung: „Speichern“ oben ohne Kurztext -> Meldung unten im Bild, Seite bleibt", await tab.js(IM_BILD),
             ["Bitte Kurztext und Einheit ausfüllen.", True, f"/services/{seed['leistung']}/edit"])
    await tab.js("window.scrollTo(0,0);document.getElementById('shortText').value='Rinne reinigen'")
    await tab.js("document.getElementById('kopfSpeichern').click()")
    p.pruefe("Formular leistung: „Speichern“ oben speichert und führt zum Katalog der Leistung",
             await tab.warten("location.pathname==='/leistungskatalog'&&location.search.startsWith('?catalog_id=')", 20), True)
    # Mitarbeiter: „Speichern“ oben -> Liste der Mitarbeiter; „Abbrechen“ -> dasselbe Ziel ohne Speichern
    mitarbeiter = FORMULARSEITEN[0]
    p.pruefe("Formular Mitarbeiter Speichern: geladen", await _formular_laden(tab, seed, mitarbeiter, "hell"), True)
    await tab.warten("document.getElementById('seitenkopfTitel').textContent==='Mitarbeiter bearbeiten'&&!!document.getElementById('lastName')", 10)
    await tab.js("document.getElementById('kopfSpeichern').click()")
    p.pruefe("Formular Mitarbeiter: „Speichern“ oben speichert und führt zur Liste der Mitarbeiter",
             await tab.warten("location.pathname==='/master-data'&&location.hash==='#employees'", 20), True)
    # seit 1.9.23: „Abbrechen“ fragt „Änderungen verwerfen?“, aber nur bei ungespeicherten Änderungen (die Rückfrage abgefangen wie beim
    # Löschen im Datensatzkopf: window.confirm zählt mit und antwortet wie vorgegeben)
    bereit = ("document.getElementById('seitenkopfTitel').textContent==='Mitarbeiter bearbeiten'&&_abbrechenStand!==null")
    rueckfrage = "window.__dkRueckfragen=[];window.confirm=t=>{window.__dkRueckfragen.push(t);return %s}"
    liste = "location.pathname==='/master-data'&&location.hash==='#employees'"
    # Klick ausgelöst wie vom Nutzer: dispatchEvent meldet false, wenn die Seite preventDefault rief (die Seite bleibt) -- ohne Wartefenster;
    # der Zustand danach im selben Schritt gelesen (folgte der Link doch, ist die Seite gleich weg)
    klick = ("(feld=>{const ev=new MouseEvent('click',{bubbles:true,cancelable:true,button:0});"
             "const verhindert=!document.getElementById('abbrechenLink').dispatchEvent(ev);"
             "return [verhindert,window.__dkRueckfragen,location.pathname,document.getElementById(feld).value]})(%s)")
    p.pruefe("Formular Mitarbeiter Abbrechen: geladen", await _formular_laden(tab, seed, mitarbeiter, "hell"), True)
    await tab.warten(bereit, 10)
    await tab.js(rueckfrage % "false")
    await tab.js("document.getElementById('abbrechenLink').click()")
    p.pruefe("Formular Mitarbeiter: „Abbrechen“ ohne Änderung führt ohne Rückfrage zur Liste", await tab.warten(liste, 20), True)
    p.pruefe("Formular Mitarbeiter Abbrechen: wieder geladen", await _formular_laden(tab, seed, mitarbeiter, "hell"), True)
    await tab.warten(bereit, 10)
    await tab.js(rueckfrage % "false")
    await tab.js("document.getElementById('lastName').value='Nicht gespeichert'")
    p.pruefe("Formular Mitarbeiter: geändert, „Abbrechen“ fragt „Änderungen verwerfen?“, abgelehnt bleibt die Seite mit der Eingabe",
             await tab.js(klick % "'lastName'"),
             [True, ["Änderungen verwerfen?"], f"/master-data/employees/{seed['mitarbeiter']}/edit", "Nicht gespeichert"])
    await tab.js(rueckfrage % "true")
    await tab.js("document.getElementById('abbrechenLink').click()")
    zurueck = await tab.warten(liste, 20)
    gespeichert = await tab.js(f"fetch('/api/employees').then(r=>r.json()).then(l=>l.find(e=>e.id==={seed['mitarbeiter']}).last_name)")
    p.pruefe("Formular Mitarbeiter: bestätigt führt „Abbrechen“ zur Liste, nichts gespeichert", [zurueck, gespeichert], [True, "Monteurin"])
    # Leistung: eine Eingabe im Kurztext zählt, die Materialsuche nicht
    p.pruefe("Formular leistung Abbrechen: geladen", await _formular_laden(tab, seed, leistung, "hell"), True)
    await tab.warten("document.getElementById('seitenkopfTitel').textContent==='Leistung bearbeiten'&&_abbrechenStand!==null", 10)
    await tab.js(rueckfrage % "false")
    await tab.js("document.getElementById('materialSearch').value='Bahn';document.getElementById('abbrechenLink').click()")
    p.pruefe("Formular leistung: nur die Materialsuche geändert -- „Abbrechen“ ohne Rückfrage zum Katalog",
             [await tab.warten("location.pathname==='/leistungskatalog'", 20), await tab.js("window.__dkRueckfragen||[]")], [True, []])
    p.pruefe("Formular leistung Abbrechen: wieder geladen", await _formular_laden(tab, seed, leistung, "hell"), True)
    await tab.warten("document.getElementById('seitenkopfTitel').textContent==='Leistung bearbeiten'&&_abbrechenStand!==null", 10)
    await tab.js(rueckfrage % "false")
    await tab.js("document.getElementById('shortText').value='Rinne reinigen und spülen'")
    p.pruefe("Formular leistung: Kurztext geändert -- „Abbrechen“ fragt, abgelehnt bleibt die Seite",
             await tab.js(klick % "'shortText'"),
             [True, ["Änderungen verwerfen?"], f"/services/{seed['leistung']}/edit", "Rinne reinigen und spülen"])
    p.pruefe("Formular: keine JS-Fehler", tab.fehler, [])
    await tab.bild("formularseiten_zuletzt")


# Seit 1.9.24: Seitenkopf von Anfragen und Arbeitsvorbereitung
ANFRAGEN_AV = (
    dict(seite="anfragen", titel="Anfragen", kennung="", untertitel="Vertriebsfälle von der Anfrage bis zum Projekt", pfad=[],
         status=["", "neutral"], menue=[]),
    dict(seite="arbeitsvorbereitung", titel="Arbeitsvorbereitung", kennung="{auftragsnummer}", untertitel="P-2026-0001 · Dachsanierung Halle Nord",
         pfad=[["Projekte", "/projects"], ["Hallenbau GmbH", "/customers/{kunde}"], ["Dachsanierung Halle Nord", "/projects/{projekt}#sec-orders"],
               ["{auftragsnummer}", "/orders/{auftrag}"], ["Arbeitsvorbereitung", None]],
         status=["Offen", "signal"], menue=["Zeiterfassung (Auftrag)"]),
)


async def _anfragen_av(tab, seed, p):
    """Seit 1.9.24: Anfragen (Titel über den Kennzahlen, keine Hauptaktion) und Arbeitsvorbereitung (Pfad Projekte / Kunde / Projekt /
    Auftrag / Arbeitsvorbereitung, Kennung = Auftragsnummer, Status der Arbeitsvorbereitung als Kennzeichen, „Zeiterfassung (Auftrag)“ im
    Menü, Kennzahlen unter dem Kopf), hell und dunkel: .ds-seite, ein h1, jeder Link im Pfad öffnet eine Seite, Links, Fokus, Kontrast; dazu
    (hell) der Status wechselt nach „Status“ + Speichern im Kopf mit (In Planung, info), die Kennzahlen der Anfragen stehen unter dem Kopf."""
    await tab.cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    await tab.anmelden(seed["cookies"][bg.BUERO])
    werte = None
    for f in ANFRAGEN_AV:
        for thema in ("hell", "dunkel"):
            wo = f"Kopf {f['seite']} {thema}"
            p.pruefe(f"{wo}: geladen", await _laden(tab, seed, f["seite"], thema, 1440, 900), True)
            if werte is None:
                werte = await _datensatz_werte(tab, seed)
            soll = lambda s: s.format(**werte) if isinstance(s, str) else s  # noqa: E731
            m = await tab.js(DATENSATZKOPF_JS)
            p.pruefe(f"{wo}: .ds-seite, genau ein h1 „{f['titel']}“, Kennung, Untertitel, Status „{f['status'][0]}“",
                     [m["ds"], m["h1"], m["kennung"], m["untertitel"], m["status"][:2]],
                     [True, [["seitenkopfTitel", f["titel"]]], soll(f["kennung"]), f["untertitel"], f["status"]])
            pfad = [[soll(t), soll(h) if h else None, None if h else "page"] for t, h in f["pfad"]]
            p.pruefe(f"{wo}: Pfad {' / '.join(g[0] for g in pfad) or '—'}, kein alter Kopf (.hero, .top-actions)",
                     [m["pfad"], await tab.js("document.querySelectorAll('.hero,.top-actions,#statusPill').length")], [pfad, 0])
            offen = await tab.js(PFAD_OEFFNEN)
            p.pruefe(f"{wo}: jeder Link im Pfad öffnet eine Seite ({len(offen)} Links)",
                     [o for o in offen if o[1:] != [200, False, "text/html"]], [])
            p.pruefe(f"{wo}: keine Hauptaktion, Menü {f['menue'] or '—'}", [m["aktion"], m["menue"]], [[], f["menue"]])
            p.pruefe(f"{wo}: {m['links']} Textlinks im Inhalt, alle in --ds-link", m["falsch"], [])
            fokus = await tab.js(KOPFGRUPPE_FOKUS)
            p.pruefe(f"{wo}: erstes Feld mit Fokus im Umriss --ds-fokus", fokus if fokus == "kein Feld" else fokus[1],
                     "kein Feld" if fokus == "kein Feld" else True)
            k = await tab.js(KONTRAST)
            p.pruefe(f"{wo}: Kontrast ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", k["schwach"], [])
            if thema == "hell" and f["seite"] == "anfragen":
                p.pruefe(f"{wo}: die Kennzahlen stehen unter dem Kopf", await tab.js(
                    "(()=>{const k=document.getElementById('seitenkopf').getBoundingClientRect(),m=document.querySelector('.metric-grid').getBoundingClientRect();"
                    "return [m.top>=k.bottom,document.getElementById('metricOpen')!==null]})()"), [True, True])
            if thema == "dunkel" and f["seite"] == "arbeitsvorbereitung":  # zuletzt: das Speichern ändert den Status
                p.pruefe(f"{wo}: Menü „Zeiterfassung (Auftrag)“ mit dem Auftrag", await tab.js(
                    "document.getElementById('timeLink').getAttribute('href')"), f"/time-tracking?order_id={seed['auftrag']}")
                await tab.warte_auf_neu_geladene_liste(
                    "document.getElementById('prepStatus').value='in_planung';saveHeader()", None)
                p.pruefe(f"{wo}: Status „In Planung“ gespeichert -- der Kopf wechselt mit (info)", await tab.js(
                    "[document.getElementById('seitenkopfStatus').textContent,document.getElementById('seitenkopfStatus').className]"),
                    ["In Planung", "ds-status ds-status-info"])
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    await tab.bild("anfragen_av_zuletzt")


# Seit 1.9.25: Seitenkopf der Monteursseiten (Tablet-Maße im Monteursrahmen), dazu Einsatzbericht und Konto der Monteurin
MASSE = """(()=>{const cs=e=>getComputedStyle(e);const k=document.getElementById('seitenkopf');const pf=k.querySelector('.ds-kopf-pfad');
const kn=[...k.querySelectorAll('.ds-knopf')].filter(e=>cs(e).display!=='none').map(e=>[e.id||e.textContent.trim(),Math.round(e.getBoundingClientRect().height),
  Math.round(e.getBoundingClientRect().width)]);
return {klasse:k.className,titel:cs(document.getElementById('seitenkopfTitel')).fontSize,pfad:pf?cs(pf).fontSize:null,knoepfe:kn,
  monteurskopf:!!document.getElementById('mobileHeaderWrap'),leiste:!!document.getElementById('appSidebar')}})()"""


async def _monteur_werte(tab, seed):
    holen = "(u=>fetch(u).then(r=>r.json()))"
    cl = await tab.js(f"{holen}('/api/checklists/{seed['checkliste']}')")
    a = await tab.js(f"{holen}('/api/operational-assets/{seed['geraet']}')")
    o = await tab.js(f"{holen}('/api/orders/{seed['auftrag']}')")
    return cl, a, o


async def _monteursseiten(tab, seed, p):
    """Seit 1.9.25: Checkliste, Checklisten zum Auftrag, Objekt und Betriebsmittel als Monteurin (1280 × 620, hell und dunkel) im
    Monteursrahmen mit Tablet-Maßen (Pfad 15 px, Titel 26 px, jeder Knopf im Kopf mindestens 48 px hoch), dazu Einsatzbericht und Konto der
    Monteurin; Checkliste und Checklisten zum Auftrag auch fürs Büro (1440 × 900, der gewohnte Kopf: 13 px, 30 px, 40 px). Je Seite
    .ds-seite, ein h1, Kennung, Untertitel, Status, Pfad nach dem Laden (jeder Link öffnet eine Seite), kein alter Kopf, Links, Fokus,
    Kontrast; „PDF“ der Checkliste nur, wenn sie kein Entwurf mehr ist."""
    await tab.cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    for rolle in (bg.MONTEUR, bg.BUERO):
        await tab.anmelden(seed["cookies"][rolle])
        p.pruefe(f"Monteursseiten ({rolle}): Werte laden", await _laden(tab, seed, "checkliste", "hell", 1440, 900), True)
        cl, a, o = await _monteur_werte(tab, seed)
        monteur = rolle == bg.MONTEUR
        status_cl = {"entwurf": ["Entwurf", "warn"], "abgeschlossen": ["Abgeschlossen", "ok"], "gegenstandslos": ["Gegenstandslos", "neutral"]}
        rueck_cl = f"/checklisten/auftrag/{cl['order_id']}" if monteur else f"/orders/{cl['order_id']}"
        anfang = ["Heute", "/mobil"] if monteur else ["Checklisten", "/checklisten"]
        seiten = [
            dict(seite="checkliste", titel=cl["template_label"], kennung="", status=status_cl[cl["status"]],
                 pfad=[anfang, [cl["context_label"], rueck_cl], [cl["template_label"], None]], pdf=cl["status"] != "entwurf"),
            dict(seite="checklisten_auftrag", titel="Checklisten zum Auftrag", kennung=o["order_number"], untertitel=o["customer_name"],
                 status=["", "neutral"], pfad=[anfang] + ([] if monteur else [[o["order_number"], f"/orders/{seed['auftrag']}"]])
                 + [["Checklisten zum Auftrag", None]]),
        ]
        if monteur:
            meta = " · ".join(x for x in (a.get("asset_type"), a.get("manufacturer"), a.get("model")) if x)
            seiten += [
                dict(seite="mobil_objekt", titel="Halle Nord", kennung="", untertitel="", status=["", "neutral"],
                     pfad=[["Heute", "/mobil"], ["Halle Nord", None]]),
                dict(seite="betriebsmittel_monteur", titel=a["name"], kennung="", untertitel=meta, status=["", "neutral"],
                     pfad=[["Heute", "/mobil"], [a["name"], None]]),
                dict(seite="einsatzbericht", titel="Einsatzbericht", kennung=o["order_number"], untertitel=o["customer_name"],
                     status=["", "neutral"], pfad=[["Heute", "/mobil"], ["Einsatzbericht", None]]),
                dict(seite="konto", titel="Mein Konto", kennung="", untertitel="", status=["", "neutral"],
                     pfad=[["Heute", "/mobil"], ["Mein Konto", None]]),
            ]
        breite, hoehe = (1280, 620) if monteur else (1440, 900)
        for f in seiten:
            for thema in ("hell", "dunkel"):
                wo = f"Monteursseite {f['seite']} ({rolle}) {thema}"
                p.pruefe(f"{wo}: geladen", await _laden(tab, seed, f["seite"], thema, breite, hoehe), True)
                await tab.warten("!!document.querySelector('#seitenkopfPfad .ds-kopf-pfadende')", 10)
                m = await tab.js(DATENSATZKOPF_JS)
                pruef = [m["ds"], m["h1"], m["kennung"], m["status"][:2]] + ([m["untertitel"]] if "untertitel" in f else [])
                soll = [True, [["seitenkopfTitel", f["titel"]]], f["kennung"], f["status"]] + ([f["untertitel"]] if "untertitel" in f else [])
                p.pruefe(f"{wo}: .ds-seite, ein h1 „{f['titel']}“, Kennung, Status{', Untertitel' if 'untertitel' in f else ''}", pruef, soll)
                pfad = [[t, h, None if h else "page"] for t, h in f["pfad"]]
                p.pruefe(f"{wo}: Pfad {' / '.join(g[0] for g in pfad)}, kein alter Kopf",
                         [m["pfad"], await tab.js("document.querySelectorAll('.back,.back-link,#orderTitle,.obj-name').length")], [pfad, 0])
                offen = await tab.js(PFAD_OEFFNEN)
                p.pruefe(f"{wo}: jeder Link im Pfad öffnet eine Seite ({len(offen)} Links)",
                         [o2 for o2 in offen if o2[1:] != [200, False, "text/html"]], [])
                mass = await tab.js(MASSE)
                if monteur:
                    p.pruefe(f"{wo}: Monteursrahmen mit Tablet-Maßen -- Pfad 15 px, Titel 26 px, jeder Knopf im Kopf mindestens 48 px",
                             [mass["klasse"], mass["monteurskopf"], mass["leiste"], mass["pfad"], mass["titel"],
                              [k for k in mass["knoepfe"] if k[1] < 48]], ["ds-kopf ds-kopf-tablet", True, False, "15px", "26px", []])
                else:
                    p.pruefe(f"{wo}: im Büro der gewohnte Kopf -- Pfad 13 px, Titel 30 px, Knöpfe 40 px",
                             [mass["klasse"], mass["leiste"], mass["pfad"], mass["titel"], [k for k in mass["knoepfe"] if k[1] != 40]],
                             ["ds-kopf", True, "13px", "30px", []])
                if "pdf" in f:
                    p.pruefe(f"{wo}: „PDF“ im Kopf {'sichtbar' if f['pdf'] else 'verborgen (Entwurf)'}", await tab.js(
                        "(e=>[getComputedStyle(e).display!=='none',e.getAttribute('href')])(document.getElementById('pdfLink'))"),
                        [f["pdf"], f"/api/checklists/{seed['checkliste']}/pdf"])
                p.pruefe(f"{wo}: {m['links']} Textlinks im Inhalt, alle in --ds-link", m["falsch"], [])
                fokus = await tab.js(KOPFGRUPPE_FOKUS)
                p.pruefe(f"{wo}: erstes Feld mit Fokus im Umriss --ds-fokus", fokus if fokus == "kein Feld" else fokus[1],
                         "kein Feld" if fokus == "kein Feld" else True)
                k = await tab.js(KONTRAST)
                p.pruefe(f"{wo}: Kontrast ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", k["schwach"], [])
                p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    await tab.bild("monteursseiten_zuletzt")

ANMELDUNG_JS = """(()=>{const F=%s;const cs=e=>getComputedStyle(e);const k=document.getElementById('seitenkopf');const m=document.querySelector('.marke');
const ka=m&&m.querySelector('.marke-kachel');const r=e=>e.getBoundingClientRect();const t=document.getElementById('seitenkopfTitel');
const erste=s=>s.split(',')[0].replace(/"/g,'').trim();
return {ds:document.body.classList.contains('ds-seite'),h1:[...document.querySelectorAll('h1')].map(e=>e.textContent.trim()),
 untertitel:document.getElementById('seitenkopfUntertitel').textContent,titel:[cs(t).fontSize,erste(cs(t).fontFamily)],
 marke:m?[m.querySelector('.marke-name').textContent,m.querySelector('.marke-zusatz').textContent,!!ka.querySelector('svg'),
   Math.round(r(ka).width),Math.round(r(ka).height),cs(ka).backgroundColor,erste(cs(m.querySelector('.marke-name')).fontFamily)]:null,
 vorKopf:!!(m&&k&&(m.compareDocumentPosition(k)&Node.DOCUMENT_POSITION_FOLLOWING)),schrift:erste(cs(document.body).fontFamily),
 grund:cs(document.body).backgroundColor===F('--ds-grund'),ohneBildlauf:document.documentElement.scrollWidth<=window.innerWidth,
 alt:document.querySelectorAll('.muted,.button').length}})()"""
# Farben und Maß eines Elements gegen --ds-Werte: [Höhe, Grund = --ds-aktion, Schrift = --ds-auf-aktion]
GRUENER_KNOPF = """(e=>{const F=%s;const cs=getComputedStyle(e);return [Math.round(e.getBoundingClientRect().height),
 cs.backgroundColor===F('--ds-aktion'),cs.color===F('--ds-auf-aktion'),e.className,e.getAttribute('href')]})"""
FOKUS_FELD = """(e=>{const F=%s;e.focus();const cs=getComputedStyle(e);return [document.activeElement===e,cs.outlineStyle,
 cs.outlineColor===F('--ds-fokus')]})"""
# KONTRAST misst unter main -- Anmeldung und Sperrseite haben keins, dort die Karte
KONTRAST_KARTE = KONTRAST.replace("'main *, #seitenkopfMenue *'", "'.card *'")
MARKE = ["DACHKONZEPTE", "Rödchen GmbH · ERP", True, 44, 44, "rgb(255, 255, 255)", "Archivo"]


async def _anmeldung(tab, seed, p):
    """Seit 1.9.27: Anmeldung (ohne Anmeldung) und Sperrseite (Monteurin auf /projects) bei 1440 × 900 und 412 × 915, hell und dunkel:
    .ds-seite, die Bildmarke mit Schriftzug in weißer Kachel (44 px) über dem Seitenkopf, ein h1 in Archivo 30 px, Text in IBM Plex Sans,
    kein waagrechter Bildlauf, Kontrast in der Karte. Anmeldung: Titel „Anmelden“, Untertitel „Melde dich mit deinem Benutzernamen an.“,
    Fokus im Benutzernamen in --ds-fokus, der grüne Knopf „Anmelden“. Sperrseite: Titel „Kein Zugriff auf diese Seite“, darunter nur,
    was zu tun ist (nichts doppelt, kein „nicht verfügbar“), „Zur Startseite“ als grüne Hauptaktion nach /mobil."""
    await tab.cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    fall = [("anmeldung", {}, "Anmelden", "Melde dich mit deinem Benutzernamen an."),
            ("sperrseite", seed["cookies"][bg.MONTEUR], "Kein Zugriff auf diese Seite", "")]
    for seite, cookies, titel, untertitel in fall:
        await tab.anmelden(cookies)
        for breite, hoehe in ((1440, 900), (412, 915)):
            for thema in ("hell", "dunkel"):
                wo = f"{seite} {breite} px {thema}"
                p.pruefe(f"{wo}: geladen", await _laden(tab, seed, seite, thema, breite, hoehe), True)
                m = await tab.js(ANMELDUNG_JS % FARBE)
                p.pruefe(f"{wo}: .ds-seite, Grund --ds-grund, ein h1 „{titel}“ in Archivo 30 px, Untertitel, Text in IBM Plex Sans, "
                         f"kein alter Kopf, kein waagrechter Bildlauf",
                         [m["ds"], m["grund"], m["h1"], m["titel"], m["untertitel"], m["schrift"], m["alt"], m["ohneBildlauf"]],
                         [True, True, [titel], ["30px", "Archivo"], untertitel, "IBM Plex Sans", 0, True])
                p.pruefe(f"{wo}: Bildmarke mit Schriftzug in weißer Kachel 44 px über dem Seitenkopf", [m["marke"], m["vorKopf"]],
                         [MARKE, True])
                if seite == "anmeldung":
                    p.pruefe(f"{wo}: „Anmelden“ grün", (await tab.js(f"({GRUENER_KNOPF % FARBE})(document.querySelector('.card button'))"))[1:3],
                             [True, True])
                    p.pruefe(f"{wo}: Fokus im Benutzernamen im Umriss --ds-fokus",
                             await tab.js(f"({FOKUS_FELD % FARBE})(document.getElementById('u'))"), [True, "solid", True])
                else:
                    texte = await tab.js("[[...document.querySelectorAll('.card > p')].map(e=>e.textContent.trim()),"
                                         "document.body.innerText.includes('nicht verfügbar')]")
                    p.pruefe(f"{wo}: darunter nur, was zu tun ist -- nichts doppelt", texte,
                             [["Brauchst du sie, wende dich an eine Person mit den passenden Rechten."], False])
                    p.pruefe(f"{wo}: „Zur Startseite“ grüne Hauptaktion 40 px nach /mobil",
                             await tab.js(f"({GRUENER_KNOPF % FARBE})(document.querySelector('.card a'))"),
                             [40, True, True, "ds-knopf ds-knopf-aktion", "/mobil"])
                k = await tab.js(KONTRAST_KARTE)
                p.pruefe(f"{wo}: Kontrast ({k['anzahl']} Elemente, kleinster {k['min']} : 1)", [k["anzahl"] > 3, k["schwach"]], [True, []])
                p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
        await tab.bild(f"{seite}_zuletzt")
    # „Zur Startseite“ führt die Monteurin zu ihren Einsätzen
    await tab.js("document.querySelector('.card a').click()")
    p.pruefe("Sperrseite: „Zur Startseite“ öffnet /mobil", await tab.warten("location.pathname==='/mobil'&&document.readyState==='complete'", 15),
             True)


# Ecke des ersten sichtbaren Elements je Selektor, ohne angehängten Link darunter: [Selektor, oben links, unten links] (None, wenn keins
# sichtbar) -- eine Einsatzkarte mit „Checklisten zu diesem Auftrag“ ist unten gewollt eckig, das prüft ANSCHLUSS
ECKEN = """(sel=>sel.map(s=>{const e=[...document.querySelectorAll(s)].find(x=>x.getClientRects().length&&!(x.nextElementSibling&&x.nextElementSibling.classList.contains('checklist-link')));if(!e)return [s,null,null];
const cs=getComputedStyle(e);return [s,cs.borderTopLeftRadius,cs.borderBottomLeftRadius]}))(%s)"""
# (Aufnahme, Rolle, Fenster, Selektoren der Karten, Soll)
ECKEN_FAELLE = [
    ("start", bg.BUERO, (1440, 900), [".widget-card", ".metric"], "12px"),
    ("projekte", bg.BUERO, (1440, 900), [".card"], "12px"),
    ("einstellungen", bg.BUERO, (1440, 900), [".settings-sidebar", ".card"], "12px"),
    ("rechnung", bg.BUERO, (1440, 900), [".card"], "12px"),
    ("stammdaten_mitarbeiter", bg.BUERO, (1440, 900), [".wrap"], "12px"),
    ("checkliste", bg.BUERO, (1440, 900), [".q", ".footer-card"], "12px"),
    ("einsatzbericht", bg.BUERO, (1440, 900), [".card"], "12px"),
    ("mobil", bg.MONTEUR, (1280, 620), [".heute-karte"], "16px"),
    ("meine_zeiten", bg.MONTEUR, (1280, 620), [".zahl-karte", ".zeiten-karte"], "16px"),  # seit 1.9.59
    ("checkliste", bg.MONTEUR, (1280, 620), [".q", ".footer-card"], "16px"),
    ("einsatzbericht", bg.MONTEUR, (1280, 620), [".card"], "16px"),
    ("konto", bg.MONTEUR, (1280, 620), [".card"], "16px"),
    ("mobil_objekt", bg.MONTEUR, (1280, 620), [".card"], "16px"),
    ("betriebsmittel_monteur", bg.MONTEUR, (1280, 620), [".card"], "16px"),
]
# Seit 1.9.45 („Heute“): Hinweis „Offene Bedenken“ und die Wege zum Auftrag stehen IN der Einsatzkarte, nichts hängt unten an (bis 1.9.44
# hing „Checklisten zu diesem Auftrag“ unter der Karte, die darüber unten eckig)
ANSCHLUSS = """[document.querySelectorAll('.checklist-link').length,
[...document.querySelectorAll('.einsatz-wege,.concern-alert')].every(e=>!!e.closest('.heute-karte'))]"""


async def _ecken(tab, seed, p):
    """Seit 1.9.30: Karten mit 12 px Ecken im Büro, 16 px im Monteursrahmen (die Seiten der Monteurin bei 1280 × 620; Checkliste und
    Einsatzbericht in beiden Rahmen), hell und dunkel; in /mobil schließt „Checklisten zu diesem Auftrag“ unten an seine Karte an (Karte
    unten eckig, Link unten rund)."""
    angemeldet = None
    for seite, rolle, (breite, hoehe), selektoren, soll in ECKEN_FAELLE:
        if rolle != angemeldet:
            await tab.anmelden(seed["cookies"][rolle])
            angemeldet = rolle
        for thema in ("hell", "dunkel"):
            wo = f"Ecken {seite} ({rolle}) {thema}"
            p.pruefe(f"{wo}: geladen", await _laden(tab, seed, seite, thema, breite, hoehe), True)
            ecken = await tab.js(ECKEN % json.dumps(selektoren))
            p.pruefe(f"{wo}: {', '.join(selektoren)} mit {soll} Ecken", ecken, [[s, soll, soll] for s in selektoren])
            if seite == "mobil":
                a = await tab.js(ANSCHLUSS)
                p.pruefe(f"{wo}: Hinweis und Wege in der Einsatzkarte, nichts angehängt", a, [0, True])
            p.pruefe(f"{wo}: keine JS-Fehler", tab.fehler, [])
    await tab.bild("ecken_zuletzt")


TEILE = {"seitenleiste": _seitenleiste, "aktiv": _aktiv, "schrift": _schrift, "menueknopf": _menueknopf, "kopfzeile": _kopfzeile,
         "kontomenue": _kontomenue, "vollname": _vollname, "pruefvorlagen": _pruefvorlagen, "kopfgruppe": _kopfgruppe,
         "seitenregeln": _seitenregeln, "monteurskopf": _monteurskopf, "datensatzkopf": _datensatzkopf,
         "rechnungskopf": _rechnungskopf, "angebotskopf": _angebotskopf, "untermenue": _untermenue,
         "formularseiten": _formularseiten, "anfragen_av": _anfragen_av,
         "monteursseiten": _monteursseiten, "anmeldung": _anmeldung, "ecken": _ecken}
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
