"""Klicktest: Ziehen in der Ansicht „Aufträge“ (1.9.281, Stufe 6, R5c, Punkt 3) -- Testdaten wie klicktest_plantafel_auftraege.py (KW 46, stehende Uhr
Mi 11.11.2026 10:00), dazu ein offener Antrag von Nele für Fr 13.11. (wie in der Zeichnung entwurf-stufe6/plantafel-auftraege-regeln.html).

Maus, 1440 px hell:
    Antippen    Kai am Wasserturm Do antippen -> Leiste mit „Für diesen Tag herausnehmen“, „An allen Tagen herausnehmen“, „Einsatz öffnen“; der Einsatz-Dialog
                öffnet sich dabei nicht; „An allen Tagen herausnehmen“ -> Kai fehlt Do und Fr, Leiste „an allen Tagen herausgenommen“ mit „Rückgängig“
    Frei        Kai aus der Liste auf den Wasserturm Do: vor dem Loslassen „Frei – Do 12.11.“ (Bild), danach „Kai Kolb · nur Do 12.11.“, „Fr 13.11.: frei“,
                „bis Fr 13.11. verlängern“, „Rückgängig“ (Bild); verlängern -> Do und Fr; Rückgängig -> nur Do
    Woanders    Ole aus der Liste auf die Garage Mi: „Schon woanders: Sturmschaden …“ (Bild), Loslassen -> Rückfrage, Abbrechen -> nichts gespeichert; Ole aus seiner
                Zelle beim Sturmschaden auf die Garage Mi: „Frei“, umgesetzt ohne Rückfrage, Rückgängig -> wieder beim Sturmschaden
    Antrag      Nele aus der Liste auf den Wasserturm Fr: „Antrag offen – plant ohne Rückfrage“ (Bild), gespeichert ohne Rückfrage, Punkt am Chip
    Kolonne     Kolonne Süd aus der Liste auf Kaminverwahrung Mo (kein Einsatz): „Ganze Kolonne – Kai, Nele, HS-DK 204 schon woanders: Rückfrage für alle“
                (seit 1.9.286 mit dem Gerät; Bild), eine Rückfrage für alle, „Trotzdem planen“ -> neuer vorläufiger Einsatz mit Kai, Lia, Nele und HS-DK 204
    Liste       Lia aus der Zelle zurück auf die Liste -> für Mo herausgenommen
    Escape      mitten im Ziehen bricht ab, nichts gespeichert
Finger (Touch-Emulation), 1280 px dunkel: die Liste offen (seit 1.9.283), der Knopf „Zum Einplanen einklappen“; Chips greifbar (Höhe ≥ 40 px bei grobem Zeiger), antippen -> „Einsatz öffnen“, Nele aus der Zelle auf die Liste,
Lia aus der Liste auf Kaminverwahrung Mo mit Anzeige vor dem Loslassen (Bild) und „Rückgängig“.
Seit 1.9.287: die Anzeige schwebt über der Zelle (unten angesetzt), die Zeile wird beim Ziehen nicht höher (Woanders, Kolonne); Bilder dazu mit dem Finger
hell (1280 px) und mit der Maus dunkel (1440 px).
Keine JS-Fehler.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_auftraege_ziehen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_plantafel_auftraege import BEREIT, ZELLE  # noqa: E402
from klicktest_plantafel_auftraege import befuellen as befuellen_auftraege  # noqa: E402
from klicktest_plantafel_tage import UHR_MS  # noqa: E402

MO, DI, MI, DO, FR = "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"
WASSER, GARAGE, STURM, KAMIN = "Am Wasserturm 4", "Garage Lindenweg 7", "Sturmschaden Gartenstraße 2", "Kaminverwahrung Schulz"

# Elemente als JS-Ausdrücke
def liste(art: str, name: str) -> str:
    return f"[...document.querySelectorAll('#backlog .chip')].find(c=>c.dataset.art==={json.dumps(art)}&&c.textContent.trim()==={json.dumps(name)})"


def td(name: str, tag: str) -> str:
    return (f"(()=>{{const z=[...document.querySelectorAll('#planner tr.a-zeile')].find(r=>r.querySelector('.a-name a').textContent.trim()==={json.dumps(name)});"
            f"return z?z.querySelector('td[data-date=\"{tag}\"]'):null}})()")


def ziel(name: str, tag: str) -> str:
    """die Karte in der Zelle, sonst die Zelle"""
    return f"(t=>t&&(t.querySelector('.a-einsatz')||t))({td(name, tag)})"


def chip(name: str, tag: str, art: str, text: str) -> str:
    return f"(t=>t&&[...t.querySelectorAll('.chip')].find(c=>c.dataset.art==={json.dumps(art)}&&c.textContent.trim()==={json.dumps(text)}))({td(name, tag)})"


LISTE_BEREICH = "document.getElementById('backlog')"
LEISTE = ("(()=>{const l=document.getElementById('zugLeiste');return l&&!l.hidden?[...l.children].filter(e=>!e.classList.contains('zug-zu'))"
          ".map(e=>e.textContent.trim()):null})()")


def anzeige(name: str, tag: str) -> str:
    """was die Zelle vor dem Loslassen zeigt: [Klassen zug-…, Text]"""
    return (f"(t=>t?[[...t.classList].filter(k=>k.startsWith('zug-')).sort().join(' '),t.querySelector('.zug-anzeige')?.textContent||null]:null)"
            f"({td(name, tag)})")


def mass(name: str) -> str:
    """seit 1.9.287: Höhe der Zeile und Abstand zur nächsten Zeile (unabhängig vom Rollen) -- die Anzeige darf die Zeile nicht höher machen"""
    return (f"(z=>{{const b=z.getBoundingClientRect(),n=z.nextElementSibling;return [Math.round(b.height),n?Math.round(n.getBoundingClientRect().top-b.top):null]}})"
            f"([...document.querySelectorAll('#planner tr.a-zeile')].find(r=>r.querySelector('.a-name a').textContent.trim()==={json.dumps(name)}))")


def ueber_der_zelle(name: str, tag: str) -> str:
    """seit 1.9.287: die Anzeige schwebt oberhalb der Zelle, so breit wie sie (position absolute, ihre Unterkante über der Oberkante der Zelle)"""
    return (f"(t=>{{const e=t.querySelector('.zug-anzeige'),a=e.getBoundingClientRect(),r=t.getBoundingClientRect();"
            f"return [a.left>=r.left-0.5,a.right<=r.right+0.5,a.bottom<=r.top+0.5,getComputedStyle(e).position]}})({td(name, tag)})")


def durch_die_anzeige(name: str, tag: str) -> str:
    """seit 1.9.287 (Gegenprobe 287_2d blieb zuerst grün): die Anzeige fängt keinen Zeiger ab -- an ihrer Mitte findet die Seite (zielAnPunkt()) die Zelle
    darüber oder nichts, nie das Ziel, unter dem die Anzeige hängt"""
    return (f"(t=>{{const a=t.querySelector('.zug-anzeige').getBoundingClientRect(),z=zielAnPunkt((a.left+a.right)/2,(a.top+a.bottom)/2);"
            f"return !!z&&z.art==='zelle'&&z.td===t}})({td(name, tag)})")


def befuellen(db, k):
    from datetime import date

    from app.models import Employee, EmployeeAbsenceRequest

    seed = befuellen_auftraege(db, k)
    nele = db.query(Employee).filter_by(first_name="Nele").one()
    db.add(EmployeeAbsenceRequest(employee_id=nele.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 11, 13),
                                  end_date=date(2026, 11, 13), status="pending"))
    db.commit()
    return seed


async def punkte(tab, quelle: str, ziel_: str):
    """Mitte von Quelle und Ziel, beide sichtbar und im Fenster (die Seite rollt dafür) -- sonst None (auch ohne Größe, z. B. eingeklappt)."""
    return await tab.js(
        "((a,b)=>{if(!a||!b||!a.getClientRects().length||!b.getClientRects().length||!a.offsetWidth||!b.offsetWidth)return null;let ra=a.getBoundingClientRect(),rb=b.getBoundingClientRect();const o=Math.min(ra.top,rb.top),u=Math.max(ra.bottom,rb.bottom);"
        "if(o<0||u>innerHeight){window.scrollBy(0,(o+u)/2-innerHeight/2);ra=a.getBoundingClientRect();rb=b.getBoundingClientRect()}"
        "if(Math.min(ra.top,rb.top)<0||Math.max(ra.bottom,rb.bottom)>innerHeight)return null;"
        "return [ra.left+ra.width/2,ra.top+ra.height/2,rb.left+rb.width/2,rb.top+rb.height/2]})(" + quelle + "," + ziel_ + ")")


async def maus_ziehen(tab, p, anlass: str, quelle: str, ziel_: str):
    """drückt auf der Quelle und zieht über das Ziel, ohne loszulassen -- Rückgabe der Punkt zum Loslassen"""
    pk = await punkte(tab, quelle, ziel_)
    p.pruefe(f"{anlass}: Quelle und Ziel im Fenster", pk is not None, True)
    if pk is None:
        return None
    x, y, x2, y2 = pk
    await tab.ziehen(x, y, x2 - x, y2 - y, schritte=10, loslassen=False)
    return x2, y2


async def maus_los(tab, punkt) -> None:
    await tab.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=punkt[0], y=punkt[1], button="left", buttons=0, clickCount=1)
    await tab.warte_auf_ruhe()


async def tippen_maus(tab, element: str) -> None:
    pk = await punkte(tab, element, element)
    for art in ("mousePressed", "mouseReleased"):
        await tab.cmd("Input.dispatchMouseEvent", type=art, x=pk[0], y=pk[1], button="left", buttons=1 if art == "mousePressed" else 0, clickCount=1)
    await tab.warte_auf_ruhe()


async def finger(tab, x, y, dx=0.0, dy=0.0, *, loslassen=True) -> None:
    await tab.cmd("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x, "y": y}])
    if dx or dy:
        for i in range(1, 11):
            await tab.cmd("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": x + dx * i / 10, "y": y + dy * i / 10}])
    if loslassen:
        await tab.cmd("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])


async def knopf(tab, text: str) -> bool:
    """klickt den Knopf der Leiste mit diesem Text"""
    gefunden = await tab.js(f"(()=>{{const b=[...document.querySelectorAll('#zugLeiste button')].find(b=>b.textContent.trim()==={json.dumps(text)});if(b)b.click();return !!b}})()")
    await tab.warte_auf_ruhe()
    return gefunden


async def pruefen(tab, seed, p):
    zelle = lambda name, tag: tab.js(f"({ZELLE})({json.dumps(name)},{json.dumps(tag)})")  # noqa: E731
    namen = lambda name, tag: tab.js(f"(t=>t?[...t.querySelectorAll('.chip')].map(c=>c.textContent.trim()):null)({td(name, tag)})")  # noqa: E731
    await tab.browser_uhr_fest(UHR_MS)
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["anna"])
    p.pruefe("Plantafel geladen", await tab.oeffnen("/planning", "typeof board!=='undefined'&&!!board"), True)
    await tab.js("localStorage.setItem('erp_theme','light')")  # hell -- erst auf der Seite, dann neu laden
    p.pruefe("Plantafel hell", await tab.oeffnen("/planning", "typeof board!=='undefined'&&!!board&&document.documentElement.getAttribute('data-theme')!=='dark'"), True)
    await tab.warte_auf_ruhe()
    await tab.js("setView('auftraege')")
    p.pruefe("Aufträge bereit", await tab.warten(BEREIT), True)
    await tab.warte_auf_ruhe()

    # --- Antippen: Leiste am Chip, der Einsatz-Dialog bleibt zu; „An allen Tagen herausnehmen“
    await tippen_maus(tab, chip(WASSER, DO, "person", "Kai"))
    p.pruefe("Kai angetippt: Leiste", await tab.js(LEISTE),
             ["Kai Kolb", "Do 12.11.", "Für diesen Tag herausnehmen", "An allen Tagen herausnehmen", "Einsatz öffnen"])
    p.pruefe("Antippen öffnet den Einsatz nicht", await tab.js("document.getElementById('einsatzDialog').open"), False)
    p.pruefe("„An allen Tagen herausnehmen“", await knopf(tab, "An allen Tagen herausnehmen"), True)
    p.pruefe("Kai fehlt am Wasserturm Do", await namen(WASSER, DO), ["Tom", "Mia", "Ole", "HS-DK 202"])
    p.pruefe("Kai fehlt am Wasserturm Fr", await namen(WASSER, FR), ["Tom", "Mia", "Ole", "HS-DK 202", "Kran"])
    p.pruefe("Leiste: an allen Tagen herausgenommen", await tab.js(LEISTE), ["Kai Kolb", "an allen Tagen herausgenommen", "Rückgängig"])

    # --- Frei: Kai aus der Liste auf den Wasserturm Do
    gestartet = await tab.js("window.__dkAnfragen.gestartet")
    los = await maus_ziehen(tab, p, "Frei", liste("person", "Kai Kolb"), ziel(WASSER, DO))
    p.pruefe("Frei: keine Anfrage beim Ziehen", await tab.js("window.__dkAnfragen.gestartet"), gestartet)
    p.pruefe("Frei: Anzeige vor dem Loslassen", await tab.js(anzeige(WASSER, DO)), ["zug-frei zug-ziel", "Frei – Do 12.11."])
    p.pruefe("Frei: die Leiste ist beim Ziehen zu", await tab.js(LEISTE), None)
    # seit 1.9.287 rechts neben dem Zeiger, auf seiner Höhe (bis 1.9.286 über dem Zeiger)
    p.pruefe("Frei: nichts markiert, der Chip neben dem Zeiger", await tab.js(
        f"[String(getSelection()),(g=>{{if(!g)return null;const b=g.getBoundingClientRect();return b.left>={(los[0] if los else 0) + 12}&&b.top<={los[1] if los else 0}&&b.bottom>={los[1] if los else 0}}})"
        f"(document.querySelector('.zug-geist'))]"), ["", True])
    await tab.bild("ziehen_frei")
    if los:
        await maus_los(tab, los)
    p.pruefe("Frei: Kai am Wasserturm Do", await namen(WASSER, DO), ["Tom", "Mia", "Ole", "Kai", "HS-DK 202"])
    p.pruefe("Frei: keine Leiste über der Tafel (in „Aufträge“ steht sie am Chip, seit 1.9.282)", await tab.js("(b=>!!b&&b.hidden)(document.getElementById('zugBand'))"), True)
    p.pruefe("Frei: Anzeige weg", await tab.js("document.querySelectorAll('#planner .zug-anzeige, #planner td.zug-ziel').length"), 0)
    p.pruefe("nur Do mit verlängern", await tab.js(LEISTE), ["Kai Kolb · nur Do 12.11.", "Fr 13.11.: frei", "bis Fr 13.11. verlängern", "Rückgängig"])
    await tab.bild("nur_tag_verlaengern")
    p.pruefe("„bis Fr 13.11. verlängern“", await knopf(tab, "bis Fr 13.11. verlängern"), True)
    p.pruefe("verlängert: Kai Fr", await namen(WASSER, FR), ["Tom", "Mia", "Ole", "Kai", "HS-DK 202", "Kran"])
    p.pruefe("verlängert: Leiste", await tab.js(LEISTE), ["Kai Kolb · nur Do 12.11., Fr 13.11.", "Rückgängig"])
    p.pruefe("Rückgängig", await knopf(tab, "Rückgängig"), True)
    p.pruefe("Rückgängig: Kai nicht mehr Fr", await namen(WASSER, FR), ["Tom", "Mia", "Ole", "HS-DK 202", "Kran"])
    p.pruefe("Rückgängig: Kai weiter Do", await namen(WASSER, DO), ["Tom", "Mia", "Ole", "Kai", "HS-DK 202"])
    p.pruefe("Rückgängig: Leiste zu", await tab.js(LEISTE), None)

    # --- Schon woanders: Ole aus der Liste auf die Garage Mi -> Rückfrage; aus seiner Zelle -> umgesetzt ohne Rückfrage
    vorher = await tab.js(mass(GARAGE))
    los = await maus_ziehen(tab, p, "Woanders", liste("person", "Ole Offen"), ziel(GARAGE, MI))
    p.pruefe("Woanders: Anzeige", await tab.js(anzeige(GARAGE, MI)),
             ["zug-woanders zug-ziel", "Schon woanders: Sturmschaden Gartenstraße 2 – Rückfrage „Trotzdem planen“"])
    # seit 1.9.287 (R5d, Punkt 5): die Anzeige schwebt über der Zelle, die Zeile wird nicht höher, nichts darunter rutscht
    p.pruefe("Woanders: die Zeile wird nicht höher", await tab.js(mass(GARAGE)), vorher)
    p.pruefe("Woanders: die Anzeige schwebt über der Zelle", await tab.js(ueber_der_zelle(GARAGE, MI)), [True, True, True, "absolute"])
    p.pruefe("Woanders: die Anzeige fängt keinen Zeiger ab", await tab.js(durch_die_anzeige(GARAGE, MI)), False)
    await tab.bild("ziehen_schon_woanders")
    if los:
        await maus_los(tab, los)
    p.pruefe("Woanders: Rückfrage", await tab.warten("document.getElementById('konfliktDialog').open"), True)
    p.pruefe("Woanders: Rückfrage nennt Ole", await tab.js("document.getElementById('konfliktWarnungen').textContent.includes('Ole')"), True)
    await tab.js("document.querySelector('#konfliktDialog .dialog-fuss .ds-knopf:not(.ds-knopf-aktion)').click()")
    await tab.warte_auf_ruhe()
    p.pruefe("Woanders: abgebrochen, nichts gespeichert", await namen(GARAGE, MI), ["Kai", "Nele", "HS-DK 204"])
    los = await maus_ziehen(tab, p, "Umsetzen", chip(STURM, MI, "person", "Ole"), ziel(GARAGE, MI))
    p.pruefe("Umsetzen: Anzeige frei", await tab.js(anzeige(GARAGE, MI)), ["zug-frei zug-ziel", "Frei – Mi 11.11."])
    if los:
        await maus_los(tab, los)
    p.pruefe("Umsetzen: keine Rückfrage", await tab.js("document.getElementById('konfliktDialog').open"), False)
    p.pruefe("Umsetzen: Ole an der Garage Mi", await namen(GARAGE, MI), ["Kai", "Nele", "Ole", "HS-DK 204"])
    p.pruefe("Umsetzen: Ole nicht mehr beim Sturmschaden Mi", await namen(STURM, MI), ["Lia"])
    p.pruefe("Umsetzen: Leiste", await tab.js(LEISTE), ["Ole Offen · nur Mi 11.11.", "Rückgängig"])
    p.pruefe("Umsetzen: Rückgängig", await knopf(tab, "Rückgängig"), True)
    p.pruefe("Umsetzen rückgängig: Ole beim Sturmschaden", await namen(STURM, MI), ["Lia", "Ole"])
    p.pruefe("Umsetzen rückgängig: nicht an der Garage", await namen(GARAGE, MI), ["Kai", "Nele", "HS-DK 204"])

    # --- Antrag offen: Nele aus der Liste auf den Wasserturm Fr
    los = await maus_ziehen(tab, p, "Antrag", liste("person", "Nele Neu"), ziel(WASSER, FR))
    p.pruefe("Antrag: Anzeige", await tab.js(anzeige(WASSER, FR)), ["zug-antrag zug-ziel", "Antrag offen – plant ohne Rückfrage"])
    await tab.bild("ziehen_antrag_offen")
    if los:
        await maus_los(tab, los)
    p.pruefe("Antrag: keine Rückfrage", await tab.js("document.getElementById('konfliktDialog').open"), False)
    p.pruefe("Antrag: Nele am Wasserturm Fr mit Punkt", [z[1] for z in (await zelle(WASSER, FR) or [])],
             [["Tom", "Mia", "Ole", "Nele •", "HS-DK 202", "Kran ⚠ (Kran)"]])

    # --- Ganze Kolonne: Kolonne Süd auf Kaminverwahrung Mo (ohne Einsatz)
    vorher = await tab.js(mass(KAMIN))
    los = await maus_ziehen(tab, p, "Kolonne", liste("kolonne", "Kolonne Süd"), ziel(KAMIN, MO))
    p.pruefe("Kolonne: Anzeige", await tab.js(anzeige(KAMIN, MO)),
             ["zug-woanders zug-ziel", "Ganze Kolonne – Kai, Nele, HS-DK 204 schon woanders: Rückfrage für alle"])  # seit 1.9.286 auch das Gerät
    p.pruefe("Kolonne: die Zeile wird nicht höher", await tab.js(mass(KAMIN)), vorher)
    await tab.bild("ziehen_ganze_kolonne")
    if los:
        await maus_los(tab, los)
    p.pruefe("Kolonne: eine Rückfrage", await tab.warten("document.getElementById('konfliktDialog').open"), True)
    p.pruefe("Kolonne: Rückfrage nennt Kai und Nele",
             await tab.js("(t=>t.includes('Kai')&&t.includes('Nele'))(document.getElementById('konfliktWarnungen').textContent)"), True)
    await tab.js("document.getElementById('konfliktTrotzdem').click()")
    await tab.warten("!document.getElementById('konfliktDialog').open")
    await tab.warte_auf_ruhe()
    p.pruefe("Kolonne: neuer vorläufiger Einsatz", [[z[0], [c.replace(" ⚠", "") for c in z[1]]] for z in (await zelle(KAMIN, MO) or [])],
             [["vorlaeufig", ["Kai", "Lia", "Nele", "HS-DK 204"]]])
    p.pruefe("Kolonne: Leiste", await tab.js(LEISTE), ["Kolonne Süd", "Mo 09.11.", "Rückgängig"])

    # --- zurück auf die Liste: Lia für Mo herausnehmen
    los = await maus_ziehen(tab, p, "Liste", chip(KAMIN, MO, "person", "Lia"), LISTE_BEREICH)
    p.pruefe("Liste: Ziel markiert", await tab.js("document.getElementById('backlog').classList.contains('zug-ziel-liste')"), True)
    if los:
        await maus_los(tab, los)
    p.pruefe("Liste: Lia herausgenommen", await namen(KAMIN, MO), ["Kai", "Nele", "HS-DK 204"])
    p.pruefe("Liste: Leiste", await tab.js(LEISTE), ["Lia Lang", "Mo 09.11. herausgenommen", "Rückgängig"])

    # --- Escape mitten im Ziehen
    los = await maus_ziehen(tab, p, "Escape", liste("person", "Mia Monteurin"), ziel(KAMIN, MO))
    await tab.cmd("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    await tab.cmd("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    p.pruefe("Escape: Anzeige weg", await tab.js("[document.querySelectorAll('#planner td.zug-ziel').length,document.querySelectorAll('.zug-geist').length]"), [0, 0])
    if los:
        await maus_los(tab, los)
    p.pruefe("Escape: nichts gespeichert", await namen(KAMIN, MO), ["Kai", "Nele", "HS-DK 204"])

    # --- Finger, 1280 px dunkel
    await tab.fenster(1280, 1000)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.cmd("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    p.pruefe("Finger: neu geladen", await tab.oeffnen("/planning", "typeof board!=='undefined'&&!!board"), True)
    await tab.warte_auf_ruhe()
    await tab.js("setView('auftraege')")
    p.pruefe("Finger: Aufträge bereit", await tab.warten(BEREIT), True)
    await tab.warte_auf_ruhe()
    # seit 1.9.283 startet „Zum Einplanen“ in „Aufträge“ immer offen, auch unter 1440 px (bis 1.9.282 dort eingeklappt) -- der Knopf heißt wie die Liste
    p.pruefe("Finger: Liste offen, Knopf „Zum Einplanen einklappen“", await tab.js(
        "[document.getElementById('tafelLayout').classList.contains('rk-zu'),document.getElementById('rkKnopf').getAttribute('aria-label')]"),
        [False, "Zum Einplanen einklappen"])
    p.pruefe("Finger: Liste offen", await tab.warten("!document.getElementById('tafelLayout').classList.contains('rk-zu')&&!!document.querySelector('#backlog .chip')"), True)
    await tab.warte_auf_ruhe()
    # seit 1.9.284 (R5d, Punkt 2): mit dem Finger 32 px hoch (bis 1.9.283 40 px), der Treffbereich reicht 4 px darüber und darunter hinaus
    grob = await tab.js("matchMedia('(pointer:coarse)').matches")
    p.pruefe("Finger: grober Zeiger", grob, True)
    p.pruefe("Finger: Chip 32 px hoch, 3 px darüber und darunter trifft noch den Chip", await tab.js(
        f"(c=>{{const r=c.getBoundingClientRect(),x=r.left+r.width/2,an=y=>{{const e=document.elementFromPoint(x,y);return !!e&&e.closest('.chip')===c}};"
        f"return [Math.round(r.height),an(r.top-3),an(r.bottom+3),an(r.top-7)]}})({chip(WASSER, FR, 'person', 'Nele')})"), [32, True, True, False])
    pk = await punkte(tab, chip(WASSER, FR, "person", "Nele"), chip(WASSER, FR, "person", "Nele"))
    await finger(tab, pk[0], pk[1])
    await tab.warte_auf_ruhe()
    p.pruefe("Finger: angetippt, Leiste", await tab.js(LEISTE),
             ["Nele Neu", "Fr 13.11.", "Für diesen Tag herausnehmen", "An allen Tagen herausnehmen", "Einsatz öffnen"])
    p.pruefe("Finger: Antippen öffnet den Einsatz nicht", await tab.js("document.getElementById('einsatzDialog').open"), False)
    p.pruefe("Finger: „Einsatz öffnen“", await knopf(tab, "Einsatz öffnen"), True)
    p.pruefe("Finger: der Einsatz vom Wasserturm", await tab.warten(f"document.getElementById('einsatzDialog').open&&einsatz&&einsatz.id==={seed['wasserturm']}"), True)
    await tab.js("document.getElementById('einsatzDialog').close()")
    pk = await punkte(tab, chip(WASSER, FR, "person", "Nele"), LISTE_BEREICH)
    p.pruefe("Finger: Nele und die Liste im Fenster", pk is not None, True)
    await finger(tab, pk[0], pk[1], pk[2] - pk[0], pk[3] - pk[1])
    await tab.warte_auf_ruhe()
    p.pruefe("Finger: Nele auf die Liste -> herausgenommen", await namen(WASSER, FR), ["Tom", "Mia", "Ole", "HS-DK 202", "Kran"])
    pk = await punkte(tab, liste("person", "Lia Lang"), ziel(KAMIN, MO))
    p.pruefe("Finger: Lia und das Ziel im Fenster", pk is not None, True)
    await finger(tab, pk[0], pk[1], pk[2] - pk[0], pk[3] - pk[1], loslassen=False)
    p.pruefe("Finger: Anzeige vor dem Loslassen", await tab.js(anzeige(KAMIN, MO)), ["zug-frei zug-ziel", "Frei – Mo 09.11."])
    await tab.bild("ziehen_finger_1280_dunkel")
    await tab.cmd("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    await tab.warte_auf_ruhe()
    p.pruefe("Finger: Lia wieder an Kaminverwahrung Mo (dazu ans Ende)", await namen(KAMIN, MO), ["Kai", "Nele", "Lia", "HS-DK 204"])
    p.pruefe("Finger: Leiste", await tab.js(LEISTE), ["Lia Lang · alle Tage", "Rückgängig"])
    p.pruefe("Finger: Rückgängig", await knopf(tab, "Rückgängig"), True)
    p.pruefe("Finger: rückgängig", await namen(KAMIN, MO), ["Kai", "Nele", "HS-DK 204"])
    # Bilder (seit 1.9.287): mit dem Finger auch hell, mit der Maus auch dunkel -- vor dem Loslassen, danach zurück an den Start (Liste auf Liste: nichts)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Finger hell: neu geladen", await tab.oeffnen("/planning", "typeof board!=='undefined'&&!!board"), True)
    await tab.warte_auf_ruhe()
    await tab.js("setView('auftraege')")
    p.pruefe("Finger hell: Aufträge bereit", await tab.warten(BEREIT), True)
    await tab.warte_auf_ruhe()
    # ohne Warnung passt jeder Name; ein Chip mit ⚠ (hier die Pritsche 204, am Mo doppelt) braucht 16 px mehr und darf kürzen -- der Name steht im title
    p.pruefe("Finger hell: kein Name ohne Warnung gekürzt (seitlich 6 px wie mit der Maus)", await tab.js(
        "[...document.querySelectorAll('#planner .chip:not(.warn) .chip-text')].filter(c=>c.scrollWidth>c.clientWidth).map(c=>c.textContent.trim())"), [])
    vorher = await tab.js(mass(GARAGE))
    pk = await punkte(tab, liste("person", "Ole Offen"), ziel(GARAGE, MI))
    await finger(tab, pk[0], pk[1], pk[2] - pk[0], pk[3] - pk[1], loslassen=False)
    await tab.warten(f"(t=>!!t&&t.classList.contains('zug-ziel'))({td(GARAGE, MI)})", 5)  # der letzte Fingerschritt kann nach dem Senden noch laufen
    p.pruefe("Finger hell: Anzeige schwebt, die Zeile wird nicht höher", [(await tab.js(anzeige(GARAGE, MI)))[0], await tab.js(mass(GARAGE)),
                                                                       await tab.js(ueber_der_zelle(GARAGE, MI))],
             ["zug-woanders zug-ziel", vorher, [True, True, True, "absolute"]])
    await tab.bild("ziehen_finger_1280_hell")
    await tab.cmd("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": pk[0], "y": pk[1]}])
    await tab.cmd("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    await tab.warte_auf_ruhe()
    p.pruefe("Finger hell: zurück auf die Liste, nichts geändert", await namen(GARAGE, MI), ["Kai", "Nele", "HS-DK 204"])
    await tab.cmd("Emulation.setTouchEmulationEnabled", enabled=False)
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    p.pruefe("Maus dunkel: neu geladen", await tab.oeffnen("/planning", "typeof board!=='undefined'&&!!board"), True)
    await tab.warte_auf_ruhe()
    await tab.js("setView('auftraege')")
    p.pruefe("Maus dunkel: Aufträge bereit", await tab.warten(BEREIT), True)
    await tab.warte_auf_ruhe()
    vorher = await tab.js(mass(GARAGE))
    los = await maus_ziehen(tab, p, "Maus dunkel", liste("person", "Ole Offen"), ziel(GARAGE, MI))
    p.pruefe("Maus dunkel: Anzeige schwebt, die Zeile wird nicht höher", [(await tab.js(anzeige(GARAGE, MI)))[0], await tab.js(mass(GARAGE))],
             ["zug-woanders zug-ziel", vorher])
    await tab.bild("ziehen_schon_woanders_dunkel")
    await tab.cmd("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    await tab.cmd("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    if los:
        await maus_los(tab, los)
    p.pruefe("Maus dunkel: abgebrochen, nichts geändert", await namen(GARAGE, MI), ["Kai", "Nele", "HS-DK 204"])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00", silbentrennung=True))
