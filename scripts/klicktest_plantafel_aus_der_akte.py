"""Klicktest: aus der Akte „Einsatz planen“ -> der Dialog der Plantafel -> zurück in die Akte (1.9.252, Stufe 6, R4, Punkt 6).

Testdaten wie klicktest_plantafel_tafel; „Dachfenster Krüger“ ist beauftragt und nicht eingeplant. Stehende Uhr Di 03.11.2026 10:00.

    Link         Akte, Reiter „Ausführung“: „Einsatz planen“ führt auf /planning?auftrag=<id>&zurueck=/projects/<p>?auftrag=<id>#ausfuehrung
    Speichern    der Dialog öffnet sich für den Auftrag; Von/Bis 16.–17.11. -> gespeichert -> zurück in der Akte (Reiter „Ausführung“), der Einsatz steht in der
                 Karte „Einsätze“
    Abbrechen    noch einmal „Einsatz planen“, „Abbrechen“ -> zurück in der Akte, kein zweiter Einsatz
    Hauptaktion  „Einsatz planen“ im Kopf der Akte -> derselbe Weg, Escape -> zurück
    ohne Akte    /planning?auftrag=<id> ohne Rücksprung: nach dem Dialog bleibt die Tafel
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_aus_der_akte.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_plantafel_tafel import BEREIT, HEUTE, UHR_MS  # noqa: E402
from klicktest_plantafel_tafel import befuellen as tafel_befuellen  # noqa: E402

ALLEIN = "Fenster von 1 s, in dem nach dem Dialog ohne Rücksprung keine Navigation beginnen darf"


def befuellen(db, k):
    from app.models import Order, Project

    seed = tafel_befuellen(db, k)
    projekt = db.query(Project).filter_by(name="Dachfenster Krüger").one()
    auftrag = db.query(Order).filter_by(project_id=projekt.id).one()
    return {**seed, "projekt": projekt.id, "auftrag": auftrag.id}


AKTE_BEREIT = "typeof akte!=='undefined'&&!!akte&&!!document.getElementById('einsatzLink').getAttribute('href').includes('zurueck=')"
EINSAETZE = "fetch('/api/planning?start=2026-11-02&end=2026-11-29').then(r=>r.json()).then(b=>b.slots.filter(s=>s.project_name==='Dachfenster Krüger').length)"


async def pruefen(tab, seed, p):
    akte = f"/projects/{seed['projekt']}?auftrag={seed['auftrag']}"
    tafel_offen = (f"location.pathname==='/planning'&&typeof einsatz!=='undefined'&&!!einsatz&&einsatz.order_id==={seed['auftrag']}"
                   "&&document.getElementById('einsatzDialog').open&&!!pruefung")
    zurueck = f"location.pathname==='/projects/{seed['projekt']}'&&location.hash==='#ausfuehrung'&&typeof akte!=='undefined'&&!!akte"
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen(akte + "#ausfuehrung", AKTE_BEREIT)
    await tab.warte_auf_ruhe()
    p.pruefe("Link mit Rücksprung", await tab.js("document.getElementById('einsatzLink').getAttribute('href')"),
             f"/planning?auftrag={seed['auftrag']}&zurueck=%2Fprojects%2F{seed['projekt']}%3Fauftrag%3D{seed['auftrag']}%23ausfuehrung")

    # --- Speichern -> zurück ---
    await tab.js("document.getElementById('einsatzLink').click()")
    p.pruefe("Plantafel: der Dialog für den Auftrag", await tab.warten(tafel_offen, 15), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Kopf nennt Projekt und Kunde", await tab.js("document.getElementById('edUnter').textContent"), "P-2026-0140 · Dachfenster Krüger · Familie Sommer")
    await tab.bild("aus_der_akte_dialog")
    await tab.js("document.getElementById('edVon').value='2026-11-16';document.getElementById('edBis').value='2026-11-17';void einsatzSpeichern()")
    p.pruefe("gespeichert: zurück in der Akte, Reiter „Ausführung“", await tab.warten(zurueck, 15), True)
    await tab.warte_auf_ruhe()
    p.pruefe("die Akte nennt den Einsatz", [await tab.js(EINSAETZE), await tab.js("document.getElementById('einsatzListe').textContent.includes('16.')")], [1, True])
    await tab.bild("aus_der_akte_zurueck")

    # --- Abbrechen -> zurück, nichts angelegt ---
    await tab.warten(AKTE_BEREIT)
    await tab.js("document.getElementById('einsatzLink').click()")
    p.pruefe("noch einmal: der Dialog", await tab.warten(tafel_offen, 15), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.querySelector('#einsatzDialog .dialog-fuss [data-klick=\"schliessen\"]').click()")
    p.pruefe("abgebrochen: zurück in der Akte, kein zweiter Einsatz", [await tab.warten(zurueck, 15), await tab.js(EINSAETZE)], [True, 1])

    # --- Hauptaktion, Escape ---
    await tab.warten(AKTE_BEREIT)
    await tab.warte_auf_ruhe()
    hat = await tab.js("!document.getElementById('hauptaktion').hidden&&document.getElementById('hauptaktion').textContent.trim()==='Einsatz planen'")
    p.pruefe("Hauptaktion „Einsatz planen“", hat, True)
    if hat:
        await tab.js("document.getElementById('hauptaktion').click()")
        p.pruefe("Hauptaktion: der Dialog", await tab.warten(tafel_offen, 15), True)
        await tab.warte_auf_ruhe()
        await tab.cmd("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        await tab.cmd("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        p.pruefe("Escape: zurück in der Akte", await tab.warten(zurueck, 15), True)

    # --- ohne Rücksprung bleibt die Tafel ---
    await tab.oeffnen(f"/planning?auftrag={seed['auftrag']}", BEREIT.replace("board.slots.length===6", "board.slots.length>=6"))
    await tab.warten(tafel_offen, 15)
    await tab.warte_auf_ruhe()
    await tab.js("einsatzDialog.close()")
    await tab.warten("false", 1.0, melden=False)  # eine Navigation hätte jetzt begonnen
    p.pruefe("ohne Rücksprung: die Tafel bleibt", await tab.js("[location.pathname,einsatzDialog.open]"), ["/planning", False])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=f"{HEUTE} 10:00"))
