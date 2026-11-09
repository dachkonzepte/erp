"""Klicktest: Stammdaten -> Mitarbeiter, Kästchen „Inaktive MA ausblenden“ (1.9.271).

Testdaten: vier Mitarbeiter -- Tom Dach und Kai Ziegel (gewerblich, Verrechnungssatz, 25 bzw. 22 €/h, je 40 h), Vera Kontor (kaufmännisch,
Variable GK, aktiv) und Ina Alt (kaufmännisch, Variable GK, INAKTIV -- wie im Bestand); Anna (Admin) und Bert (Büro – Auftrag).

    Vorgabe     Kästchen angehakt, daneben „1 inaktiv“, Ina fehlt in der Liste; Kacheln 2 / 23,50 €/h / 1; Untertitel „3 aktiv · 1 inaktiv“ (seit 1.9.274)
    ohne Haken  per Mausklick: Ina steht grau mit „Inaktiv“ in der Liste, Kacheln und Zahl unverändert, keine Anfrage an den Server
    Suche       ohne Haken findet „Alt“ Ina, mit Haken nicht; die Zahl bleibt „1 inaktiv“, auch während der Suche
    merken      nach dem Neuladen bleibt die Wahl (hell und dunkel, beide Richtungen); Bilder je Zustand hell und dunkel
    Büro – A.   sieht das Kästchen mit derselben Wahl (der Browser merkt sie je Gerät), ohne Kachel Mittellohn
    412 px      das Kästchen macht die Seite nicht breiter und bleibt in der Karte; seit 1.9.275 läuft die Seite dort nicht mehr über

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_stammdaten_inaktive.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute. Bilder: stammdaten_inaktive_{hell|dunkel}_{ausgeblendet|gezeigt}.png.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "!!document.getElementById('inaktiveAusblenden')&&document.querySelectorAll('#content tbody tr').length>0"
ANGEHAKT = "document.getElementById('inaktiveAusblenden').checked"
ZAHL = "document.getElementById('inaktivZahl').textContent"
UNTERTITEL = "document.getElementById('seitenkopfUntertitel').textContent"  # seit 1.9.274
NAMEN = ("[...document.querySelectorAll('#content tbody tr')].filter(r=>r.cells.length>1)"
         ".map(r=>r.cells[0].querySelector('b').textContent).sort()")  # seit 1.9.275 der Name in der ersten Spalte (bis 1.9.274 die Nummer davor)
KACHELN = ("[...document.querySelectorAll('#content .metric')]"
           ".map(m=>m.querySelector('.muted').textContent+': '+m.querySelector('b').textContent)")
GEMERKT = "localStorage.getItem('erp_stammdaten_inaktive')"
# Farbe der Zeile Ina gegen die gedämpfte Schrift der Seite (die Zahl daneben trägt sie) und gegen eine aktive Zeile -- seit 1.9.275 Name in der
# ersten Spalte, „nr“ ist die Zelle Funktion daneben (bis 1.9.274 die Spalte Nr.)
FARBEN = """(()=>{const z=[...document.querySelectorAll('#content tbody tr')];
const ina=z.find(r=>r.textContent.includes('Ina Alt')),tom=z.find(r=>r.textContent.includes('Tom Dach'));
if(!ina||!tom)return null;
return {klasse:ina.className,name:getComputedStyle(ina.cells[0].querySelector('b')).color,nr:getComputedStyle(ina.cells[1]).color,
 tom:getComputedStyle(tom.cells[0].querySelector('b')).color,muted:getComputedStyle(document.getElementById('inaktivZahl')).color,
 status:ina.cells[ina.cells.length-2].textContent.trim()}})()"""
ZAEHLER = ("(()=>{window.__anfragen=0;const f=window.fetch;window.fetch=function(){window.__anfragen++;return f.apply(this,arguments)};"
           "const o=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(){window.__anfragen++;return o.apply(this,arguments)};return true})()")


def befuellen(db, k):
    from decimal import Decimal

    from app.models import AppUser, Employee, EmployeeCompensationSettings, EmployeeCostAllocationSettings

    def person(nr, vor, nach, gruppe, lohn, stunden, zuordnung, aktiv=True):
        e = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group=gruppe, hourly_wage=Decimal(lohn),
                     weekly_hours=Decimal(stunden), active=aktiv, compensation=EmployeeCompensationSettings(compensation_type="hourly"))
        db.add(e); db.flush()
        db.add(EmployeeCostAllocationSettings(employee_id=e.id, allocation_type=zuordnung))

    person("M-01", "Tom", "Dach", "gewerblich", "25", "40", "labor_rate")
    person("M-02", "Kai", "Ziegel", "gewerblich", "22", "40", "labor_rate")
    person("M-03", "Vera", "Kontor", "kaufmaennisch", "20", "30", "variable_overhead")
    person("M-04", "Ina", "Alt", "kaufmaennisch", "18", "20", "variable_overhead", aktiv=False)
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    db.add_all([anna, bert]); db.flush()
    return {"anna": k.cookies(anna), "bert": k.cookies(bert)}


async def klicken(tab, selektor: str) -> None:
    """Ein echter Mausklick in die Mitte des Elements (Input.dispatchMouseEvent), nicht element.click()."""
    x, y = await tab.js(f"(()=>{{const e=document.querySelector({json.dumps(selektor)});e.scrollIntoView({{block:'center'}});"
                        "const b=e.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2]})()")
    await tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    for art in ("mousePressed", "mouseReleased"):
        await tab.cmd("Input.dispatchMouseEvent", type=art, x=x, y=y, button="left", clickCount=1)


async def suchen(tab, text: str) -> None:
    await tab.js(f"(()=>{{const s=document.getElementById('search');s.value={json.dumps(text)};s.dispatchEvent(new Event('input'));return true}})()")


async def neu_laden(tab, p, n: int, anlass: str) -> None:
    await tab.js("window.__dkVorDemNeuladen=1")
    p.pruefe(f"{anlass}: Seite geladen", await tab.oeffnen(f"/master-data?n={n}#employees", BEREIT), True)
    p.pruefe(f"{anlass}: wirklich neu geladen", await tab.js("window.__dkVorDemNeuladen===undefined"), True)
    await tab.warte_auf_ruhe()


def grau(f) -> bool:
    return bool(f) and f["klasse"] == "inaktiv" and f["name"] == f["muted"] and f["nr"] == f["muted"] and f["tom"] != f["muted"]


async def pruefen(tab, seed, p):
    kacheln_admin = ["MA im Verrechnungssatz: 2", "Gewichteter Mittellohn: 23,50 €/h", "MA in variablen GK: 1"]
    aktive = ["Kai", "Tom", "Vera"]
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["anna"])
    p.pruefe("Seite geladen", await tab.oeffnen("/master-data#employees", BEREIT), True)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await neu_laden(tab, p, 1, "hell")

    # Vorgabe: angehakt, Ina fehlt
    p.pruefe("Vorgabe: Kästchen angehakt", await tab.js(ANGEHAKT), True)
    p.pruefe("Vorgabe: nichts gemerkt", await tab.js(GEMERKT), None)
    p.pruefe("Vorgabe: Text am Kästchen", await tab.js("document.querySelector('.inaktiv-wahl label').textContent.trim()"),
             "Inaktive MA ausblenden")
    p.pruefe("Vorgabe: daneben die Zahl", await tab.js(ZAHL), "1 inaktiv")
    p.pruefe("Vorgabe: Ina nicht in der Liste", [n.split()[0] for n in await tab.js(NAMEN)], aktive)
    p.pruefe("Vorgabe: Kacheln", await tab.js(KACHELN), kacheln_admin)
    p.pruefe("Vorgabe: Untertitel", await tab.js(UNTERTITEL), "3 aktiv · 1 inaktiv")
    p.pruefe("Vorgabe: Kästchen zwischen Kacheln und Tabelle", await tab.js(
        "(()=>{const k=[...document.querySelectorAll('#content .metric')].pop().getBoundingClientRect(),"
        "w=document.querySelector('.inaktiv-wahl').getBoundingClientRect(),t=document.querySelector('#content table').getBoundingClientRect();"
        "return k.bottom<=w.top&&w.bottom<=t.top})()"), True)
    await tab.bild("stammdaten_inaktive_hell_ausgeblendet")

    # ohne Haken, per Mausklick
    await tab.js(ZAEHLER)
    vorher = len(tab.netz.verlauf)
    await klicken(tab, "#inaktiveAusblenden")
    await tab.warte_auf_ruhe()
    await tab.nachlesen()
    p.pruefe("ohne Haken: Kästchen leer", await tab.js(ANGEHAKT), False)
    p.pruefe("ohne Haken: gemerkt", await tab.js(GEMERKT), "zeigen")
    p.pruefe("ohne Haken: Ina in der Liste", [n.split()[0] for n in await tab.js(NAMEN)], ["Ina", "Kai", "Tom", "Vera"])
    farben = await tab.js(FARBEN)
    p.pruefe("ohne Haken: Ina grau, Tom nicht (hell)", grau(farben), True)
    p.pruefe("ohne Haken: Ina mit „Inaktiv“", (farben or {}).get("status"), "Inaktiv")
    p.pruefe("ohne Haken: Kacheln unverändert", await tab.js(KACHELN), kacheln_admin)
    p.pruefe("ohne Haken: Zahl unverändert", await tab.js(ZAHL), "1 inaktiv")
    p.pruefe("ohne Haken: Untertitel unverändert", await tab.js(UNTERTITEL), "3 aktiv · 1 inaktiv")
    p.pruefe("ohne Haken: keine Anfrage der Seite", await tab.js("window.__anfragen"), 0)
    p.pruefe("ohne Haken: nichts an /api/ im Netz", [e["url"] for e in tab.netz.suche(r"/api/", None, ab=vorher)], [])
    await tab.bild("stammdaten_inaktive_hell_gezeigt")

    # Suche
    await suchen(tab, "Alt")
    p.pruefe("Suche ohne Haken: „Alt“ findet Ina", await tab.js(NAMEN), ["Ina Alt"])
    await klicken(tab, "#inaktiveAusblenden")
    p.pruefe("Suche mit Haken: Kästchen angehakt", await tab.js(ANGEHAKT), True)
    p.pruefe("Suche mit Haken: „Alt“ findet niemanden", await tab.js(
        "document.querySelector('#content tbody td.empty')?.textContent"), "Keine Einträge gefunden.")
    p.pruefe("Suche mit Haken: Zahl bleibt", await tab.js(ZAHL), "1 inaktiv")
    await suchen(tab, "Tom")
    p.pruefe("Suche „Tom“: nur Tom", await tab.js(NAMEN), ["Tom Dach"])
    p.pruefe("Suche „Tom“: Zahl bleibt", await tab.js(ZAHL), "1 inaktiv")
    p.pruefe("Suche „Tom“: Untertitel bleibt", await tab.js(UNTERTITEL), "3 aktiv · 1 inaktiv")
    await suchen(tab, "")
    await klicken(tab, "#inaktiveAusblenden")
    p.pruefe("wieder ohne Haken", await tab.js(GEMERKT), "zeigen")

    # merken: hell neu laden, dann dunkel
    await neu_laden(tab, p, 2, "neu geladen hell")
    p.pruefe("neu geladen hell: weiter ohne Haken", await tab.js(ANGEHAKT), False)
    p.pruefe("neu geladen hell: Ina in der Liste", [n.split()[0] for n in await tab.js(NAMEN)], ["Ina", "Kai", "Tom", "Vera"])
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await neu_laden(tab, p, 3, "dunkel")
    p.pruefe("dunkel: Thema dunkel", await tab.js("document.documentElement.getAttribute('data-theme')"), "dark")
    p.pruefe("dunkel: weiter ohne Haken", await tab.js(ANGEHAKT), False)
    p.pruefe("dunkel: Ina grau, Tom nicht", grau(await tab.js(FARBEN)), True)
    await tab.bild("stammdaten_inaktive_dunkel_gezeigt")
    await klicken(tab, "#inaktiveAusblenden")
    p.pruefe("dunkel mit Haken: Ina nicht in der Liste", [n.split()[0] for n in await tab.js(NAMEN)], aktive)
    await tab.bild("stammdaten_inaktive_dunkel_ausgeblendet")
    await neu_laden(tab, p, 4, "neu geladen dunkel")
    p.pruefe("neu geladen dunkel: weiter angehakt", await tab.js(ANGEHAKT), True)
    p.pruefe("neu geladen dunkel: gemerkt", await tab.js(GEMERKT), "ausblenden")
    p.pruefe("neu geladen dunkel: Ina nicht in der Liste", [n.split()[0] for n in await tab.js(NAMEN)], aktive)

    # Büro – Auftrag: dasselbe Kästchen, dieselbe Wahl des Browsers
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.anmelden(seed["bert"])
    await neu_laden(tab, p, 5, "Büro – Auftrag")
    p.pruefe("Büro – Auftrag: Kästchen angehakt (gemerkt im Browser)", await tab.js(ANGEHAKT), True)
    p.pruefe("Büro – Auftrag: Zahl", await tab.js(ZAHL), "1 inaktiv")
    p.pruefe("Büro – Auftrag: Untertitel", await tab.js(UNTERTITEL), "3 aktiv · 1 inaktiv")
    p.pruefe("Büro – Auftrag: Kacheln ohne Mittellohn", await tab.js(KACHELN), ["MA im Verrechnungssatz: 2", "MA in variablen GK: 1"])
    await klicken(tab, "#inaktiveAusblenden")
    p.pruefe("Büro – Auftrag ohne Haken: Ina grau", grau(await tab.js(FARBEN)), True)

    # 412 px -- bis 1.9.274 liefen die Stammdaten dort in jeder Ansicht über (Nebenbefund 1.9.271, behoben mit 1.9.275: das Raster mit
    # minmax(0,1fr), klicktest_stammdaten_breite); geprüft wird, dass das Kästchen die Seite nicht breiter macht und in der Karte bleibt
    await tab.fenster(412, 900, mobil=True)
    await neu_laden(tab, p, 6, "412 px")
    mit = await tab.ueberlauf()
    await tab.js("document.querySelector('.inaktiv-wahl').style.display='none'")
    ohne = await tab.ueberlauf()
    await tab.js("document.querySelector('.inaktiv-wahl').style.display=''")
    p.pruefe("412 px: das Kästchen macht die Seite nicht breiter", mit == ohne, True)
    p.pruefe("412 px: die Seite läuft nicht über (seit 1.9.275)", mit, [])
    p.pruefe("412 px: Kästchen und Zahl in der Karte", await tab.js(
        "(()=>{const c=document.getElementById('content').getBoundingClientRect();"
        "return [...document.querySelectorAll('.inaktiv-wahl label, #inaktivZahl')].every(e=>{const b=e.getBoundingClientRect();"
        "return b.left>=c.left&&b.right<=c.right})})()"), True)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
