"""Klicktest: Ziehen in „Personen“ und „Geräte“ nur für diese Person bzw. dieses Gerät (1.9.270, Stufe 6, R5b, Punkt 4, Antwort 12).

Testdaten wie klicktest_plantafel_tage (Zeichnung KW 46), dazu die Pritsche HS-DK 204 am Fr 13.11. bei der Garage. Stehende Uhr Mi 11.11.2026 10:00. Echte
Mauseingaben über CDP (Tab.ziehen()), keine Aufrufe der Seitenfunktionen für das Ziehen.

    Personen  eigene Zeile: Lias „Sturmschaden“ (Di–Mi) einen Tag weiter -> Mi–Do, Ole bleibt am Mi; andere Zeile: Kais „Garage“ (Fr) in Lias Zeile -> Lia
              übernimmt den Freitag, Kai ist nicht mehr doppelt; Rückfrage: Oles „Sturmschaden“ (Mi) in Toms Zeile -> Tom wäre doppelt (Ortgang) -> Rückfrage,
              „Trotzdem planen“ -> Tom am Sturmschaden
    Geräte    eigene Zeile: die Pritsche 202 „Am Wasserturm“ Mo–Di einen Tag weiter -> Di–Fr (Mo heraus, Mi dazu), der Rest des Einsatzes bleibt; andere
              Zeile mit Rückfrage: 202 Di–Fr in die Zeile der 204 -> 204 wäre am Fr doppelt (Garage) -> „Trotzdem planen“ -> 204 Di–Fr, 202 nicht mehr am Wasserturm
    Kolonnen  weiter der ganze Einsatz: nicht hier (klicktest_plantafel_bedienen)
    zurück    nach jeder Ansicht macht der Klicktest alle Züge über „Rückgängig“ des Servers rückgängig (die Umkehrung aus der Antwort, rückwärts) -- danach
              wieder der Stand von vorher
    Bilder    vor und nach dem Ziehen in der eigenen und in eine andere Zeile, die Rückfrage dabei -- „Personen“ und „Geräte“, 1440 und 1280 px, hell und dunkel
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_ziehen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_plantafel_tage import BALKEN_JE_ZEILE, UHR_MS, _ansicht, bereit  # noqa: E402
from klicktest_plantafel_tage import befuellen as befuellen_tage  # noqa: E402

DI, MI, DO, FR = "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"


def befuellen(db, k):
    from app.models import OperationalResource, PlanningSlotResource
    seed = befuellen_tage(db, k)
    p204 = OperationalResource(resource_number="F-204", resource_type="Fahrzeug", name="Pritsche HS-DK 204", identifier="HS-DK 204", active=True)
    db.add(p204)
    db.flush()
    db.add(PlanningSlotResource(slot_id=seed["garage"], resource_id=p204.id, tage=None))
    db.commit()
    return seed


def _zeile(name):
    return "[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent.trim()===" + repr(name) + ")"


async def _balken(tab, zeile, text, nr=0):
    """Ein Punkt am Anfang des nr-ten Balkens der Zeile mit diesem Text (im ersten Tag des Stücks)."""
    return await tab.js("(()=>{const s=[..." + _zeile(zeile) + ".querySelectorAll('.slot')].filter(x=>x.textContent.includes(" + repr(text) + "))[" + str(nr) + "];"
                        "const r=s.getBoundingClientRect(),w=geo.spalten.find(c=>c.w>30).w;return [r.left+Math.min(w/2,r.width/2),r.top+r.height/2]})()")


async def _zeile_y(tab, name):
    return await tab.js("(()=>{const r=" + _zeile(name) + ".querySelector('.track').getBoundingClientRect();return r.top+Math.min(26,r.height/2)})()")


async def _ziehen(tab, zeile, text, tage, ziel_zeile=None, nr=0):
    """Zieht den Balken um so viele Tage (und in die Zeile ziel_zeile) -- echte Mauseingabe."""
    w = await tab.js("geo.spalten.find(c=>c.w>30).w")
    x, y = await _balken(tab, zeile, text, nr)
    dy = (await _zeile_y(tab, ziel_zeile)) - y if ziel_zeile else 0
    await tab.ziehen(x, y, tage * w, dy)


PERSON_TAGE = "((name,projekt)=>{const p=board.employees.find(e=>e.name===name),s=board.slots.find(x=>x.project_name===projekt);if(!s||!p)return null;" \
              "const e=s.employees.find(x=>x.id===p.id);return e?(e.tage||'alle'):null})"
GERAET_TAGE = "((name,projekt)=>{const r=board.resources.find(e=>e.name===name),s=board.slots.find(x=>x.project_name===projekt);if(!s||!r)return null;" \
              "const g=s.resources.find(x=>x.id===r.id);return g?(g.tage||'alle'):null})"
STAND = "JSON.stringify(board.slots.map(s=>[s.project_name,s.start_date,s.end_date,s.employees.map(e=>[e.id,e.tage]),s.resources.map(r=>[r.id,r.tage])]))"
# merkt die Umkehrung jeder gelungenen Tag-Aktion (aus der Antwort) -- für „zurück“ am Ende jeder Ansicht
MERKEN = ("(()=>{if(window.__umk)return;window.__umk=[];const alt=api;api=async(...a)=>{const r=await alt(...a);if(r&&r.umkehrung)window.__umk.push(r.umkehrung);"
          "return r}})()")
ZURUECK = ("(async()=>{const u=window.__umk.splice(0).reverse();for(const x of u)await api(x.pfad,{method:'POST',headers:{'Content-Type':'application/json'},"
           "body:JSON.stringify(x.body)});await loadBoard();return u.length})()")


async def _warte_stand(tab, bedingung):
    await tab.warten(bedingung, 10)
    await tab.warte_auf_ruhe()


async def _personen(tab, p, breite, thema, vorher):
    await _ansicht(tab, "employees")
    await tab.bild(f"ziehen_personen_vor_{breite}_{thema}")
    # eigene Zeile: Lia Sturmschaden Di–Mi -> Mi–Do
    await _ziehen(tab, "Lia Lang", "Sturmschaden", 1)
    await _warte_stand(tab, PERSON_TAGE + "('Lia Lang','Sturmschaden Gartenstraße 2')==='alle'&&board.slots.find(s=>s.project_name.startsWith('Sturm')).start_date===" + repr(MI))
    p.pruefe(f"Personen {breite} {thema}: eigene Zeile -- Lia Mi–Do am Sturmschaden, Ole bleibt am Mi, keine Rückfrage",
             [await tab.js(PERSON_TAGE + "('Lia Lang','Sturmschaden Gartenstraße 2')"), await tab.js(PERSON_TAGE + "('Ole Offen','Sturmschaden Gartenstraße 2')"),
              await tab.js("[board.slots.find(s=>s.project_name.startsWith('Sturm')).start_date,board.slots.find(s=>s.project_name.startsWith('Sturm')).end_date]"),
              await tab.js("konfliktDialog.open")], ["alle", [MI], [MI, DO], False])
    await tab.bild(f"ziehen_personen_eigene_{breite}_{thema}")
    # andere Zeile: Kais Garage (Fr) in Lias Zeile
    await _ziehen(tab, "Kai Kolb", "Garage", 0, "Lia Lang")
    await _warte_stand(tab, PERSON_TAGE + "('Lia Lang','Garage Lindenweg 7')!==null")
    p.pruefe(f"Personen {breite} {thema}: andere Zeile -- Lia übernimmt die Garage, Kai ist dort weg und nicht mehr doppelt",
             [await tab.js(PERSON_TAGE + "('Lia Lang','Garage Lindenweg 7')"), await tab.js(PERSON_TAGE + "('Kai Kolb','Garage Lindenweg 7')"),
              await tab.js(BALKEN_JE_ZEILE + "('Kai Kolb')")], ["alle", None, [["Am Wasserturm 4 · mit Nord", "fest"]]])
    await tab.bild(f"ziehen_personen_andere_{breite}_{thema}")
    # Rückfrage: Oles Sturmschaden (Mi) in Toms Zeile -- Tom ist am Mi beim Ortgang
    await _ziehen(tab, "Ole Offen", "Sturmschaden", 0, "Tom Monteur")
    await tab.warten("konfliktDialog.open", 8)
    await tab.warte_auf_ruhe()
    p.pruefe(f"Personen {breite} {thema}: Rückfrage -- Tom wäre doppelt, nichts gespeichert",
             [await tab.js("document.getElementById('konfliktWarnungen').textContent.includes('Tom Monteur')"),
              await tab.js(PERSON_TAGE + "('Tom Monteur','Sturmschaden Gartenstraße 2')")], [True, None])
    await tab.bild(f"ziehen_personen_rueckfrage_{breite}_{thema}")
    await tab.js("document.getElementById('konfliktTrotzdem').click()")
    await _warte_stand(tab, "!konfliktDialog.open&&" + PERSON_TAGE + "('Tom Monteur','Sturmschaden Gartenstraße 2')!==null")
    p.pruefe(f"Personen {breite} {thema}: Trotzdem planen -- Tom am Mi am Sturmschaden, Ole nicht mehr",
             [await tab.js(PERSON_TAGE + "('Tom Monteur','Sturmschaden Gartenstraße 2')"), await tab.js(PERSON_TAGE + "('Ole Offen','Sturmschaden Gartenstraße 2')")],
             [[MI], None])
    p.pruefe(f"Personen {breite} {thema}: Rückgängig -- drei Züge zurück, wieder der Stand von vorher", [await tab.js(ZURUECK), await tab.js(STAND)], [3, vorher])


async def _geraete(tab, p, breite, thema, vorher):
    await _ansicht(tab, "resources")
    await tab.bild(f"ziehen_geraete_vor_{breite}_{thema}")
    # eigene Zeile: 202 Mo–Di einen Tag weiter
    await _ziehen(tab, "Pritsche HS-DK 202", "Am Wasserturm", 1)
    await _warte_stand(tab, "JSON.stringify(" + GERAET_TAGE + "('Pritsche HS-DK 202','Am Wasserturm 4'))===" + repr(f'["{DI}","{MI}","{DO}","{FR}"]'))
    p.pruefe(f"Geräte {breite} {thema}: eigene Zeile -- 202 Di–Fr, der Einsatz bleibt Mo–Fr, Tom unverändert",
             [await tab.js(GERAET_TAGE + "('Pritsche HS-DK 202','Am Wasserturm 4')"),
              await tab.js("[board.slots.find(s=>s.project_name==='Am Wasserturm 4').start_date,board.slots.find(s=>s.project_name==='Am Wasserturm 4').end_date]"),
              await tab.js(PERSON_TAGE + "('Tom Monteur','Am Wasserturm 4')")],
             [[DI, MI, DO, FR], ["2026-11-09", FR], ["2026-11-09", DI, DO, FR]])
    await tab.bild(f"ziehen_geraete_eigene_{breite}_{thema}")
    # andere Zeile mit Rückfrage: 202 Di–Fr in die Zeile der 204 -- 204 ist am Fr bei der Garage
    await _ziehen(tab, "Pritsche HS-DK 202", "Am Wasserturm", 0, "Pritsche HS-DK 204")
    await tab.warten("konfliktDialog.open", 8)
    await tab.warte_auf_ruhe()
    p.pruefe(f"Geräte {breite} {thema}: Rückfrage -- 204 wäre am Fr doppelt",
             await tab.js("document.getElementById('konfliktWarnungen').textContent.includes('Pritsche HS-DK 204')"), True)
    await tab.bild(f"ziehen_geraete_rueckfrage_{breite}_{thema}")
    await tab.js("document.getElementById('konfliktTrotzdem').click()")
    await _warte_stand(tab, "!konfliktDialog.open&&" + GERAET_TAGE + "('Pritsche HS-DK 204','Am Wasserturm 4')!==null")
    p.pruefe(f"Geräte {breite} {thema}: andere Zeile -- 204 übernimmt Di–Fr, 202 nicht mehr am Wasserturm",
             [await tab.js(GERAET_TAGE + "('Pritsche HS-DK 204','Am Wasserturm 4')"), await tab.js(GERAET_TAGE + "('Pritsche HS-DK 202','Am Wasserturm 4')")],
             [[DI, MI, DO, FR], None])
    await tab.bild(f"ziehen_geraete_andere_{breite}_{thema}")
    p.pruefe(f"Geräte {breite} {thema}: Rückgängig -- zwei Züge zurück, wieder der Stand von vorher", [await tab.js(ZURUECK), await tab.js(STAND)], [2, vorher])


async def _durchgang(tab, p, breite, thema):
    await tab.js(MERKEN)
    vorher = await tab.js(STAND)
    await _personen(tab, p, breite, thema, vorher)
    await _geraete(tab, p, breite, thema, vorher)
    await _ansicht(tab, "teams")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light');localStorage.removeItem('plantafel_rueckstand')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()
    await _durchgang(tab, p, 1440, "hell")
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','dark')}catch(e){}")
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()
    await _durchgang(tab, p, 1440, "dunkel")
    await tab.fenster(1280, 900)
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()
    await _durchgang(tab, p, 1280, "dunkel")
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()
    await _durchgang(tab, p, 1280, "hell")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
