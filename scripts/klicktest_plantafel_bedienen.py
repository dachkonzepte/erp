"""Klicktest: die Tafel bedienen (1.9.249, Stufe 6, R4, Punkt 2) -- Klick öffnet, Ziehen verschiebt (Maus und Finger), Klick in eine freie Zelle plant.

Testdaten wie klicktest_plantafel_tafel (Zeichnung KW 45–46). Stehende Uhr Di 03.11.2026 10:00. Echte Eingaben über CDP (Input.dispatchMouseEvent,
Input.dispatchTouchEvent mit Touch-Emulation) -- keine Aufrufe der Seitenfunktionen.

    Maus         „Wartung“ (Süd, 12.11.) einen Tag nach rechts -> 13.11., ohne Rückfrage
    Klick        ein Balken mit 3 px Zittern (unter der Schwelle von 6 px) öffnet den Einsatz, nichts verschoben
    Escape       ein Ziehen mit Escape abgebrochen -> nichts verschoben
    Finger       „Notdienst“ (ohne Kolonne, 10.–11.) am zweiten Tag gefasst, einen Tag nach links -> 09.–10.11.; danach öffnet der nächste Klick
    Rückfrage    „Garage Lindenweg 7“ (Süd) in die Zeile Nord -> Rückfrage mit Warnungen; Abbrechen -> nichts verschoben
    freie Zelle  Kolonne Süd am 02.11. -> „Einsatz planen“ mit Süd, 02.11.; Ohne Kolonne am 06.11. -> ohne Kolonne; Kran am 12.11. -> mit dem Kran;
                 „Personen“: Lia am 02.11. -> mit Lia
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_bedienen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_plantafel_tafel import BEREIT, HEUTE, UHR_MS, befuellen  # noqa: E402,F401


def _zeile(name):
    return "[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent.trim()===" + repr(name) + ")"


async def balken_mitte(tab, zeile, text):
    return await tab.js("(()=>{const s=[..." + _zeile(zeile) + ".querySelectorAll('.slot')].find(x=>x.textContent.includes(" + repr(text) + "));"
                        "const r=s.getBoundingClientRect();return [r.left+Math.min(20,r.width/2),r.top+r.height/2]})()")


async def balken_tag(tab, zeile, text, k):
    """Mitte des k-ten Tags (ab 0) eines Balkens -- gefasst mitten im Einsatz."""
    return await tab.js("(()=>{const s=[..." + _zeile(zeile) + ".querySelectorAll('.slot')].find(x=>x.textContent.includes(" + repr(text) + "));"
                        "const r=s.getBoundingClientRect(),w=geo.spalten.find(c=>c.w>30).w;return [r.left+w*" + str(k) + "+w/2,r.top+r.height/2]})()")


async def zelle_mitte(tab, zeile, tag):
    return await tab.js("(()=>{const c=" + _zeile(zeile) + ".querySelector('.day-cell[data-date=\"" + tag + "\"]');const r=c.getBoundingClientRect();"
                        "return [r.left+r.width/2,r.bottom-6]})()")


async def tagbreite(tab):
    return await tab.js("geo.spalten.find(c=>c.w>30).w")


async def maus_ziehen(tab, x, y, dx, dy):
    await tab.ziehen(x, y, dx, dy)  # seit 1.9.249 über den Helfer (test_v490: Bewegung mit gedrückter Taste nur in strich() und ziehen())


async def maus_klick(tab, x, y, zittern=0):
    """Klick; zittern = so viele Pixel bewegt zwischen Drücken und Loslassen (unter der Schwelle des Ziehens)."""
    if zittern:
        await tab.ziehen(x, y, zittern, 0, schritte=1)
        return
    await tab.cmd("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", buttons=1, clickCount=1)
    await tab.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", buttons=0, clickCount=1)


async def finger_ziehen(tab, x, y, dx, dy):
    await tab.cmd("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x, "y": y}])
    for i in range(1, 9):
        await tab.cmd("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": x + dx * i / 8, "y": y + dy * i / 8}])
    await tab.cmd("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])


async def _dialog_zu(tab):
    await tab.js("einsatzDialog.close()")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_ruhe()
    tag = await tagbreite(tab)
    stand = "(n=>{const s=board.slots.find(x=>x.project_name===n);return [s.start_date,s.end_date,s.team_id===null?null:board.teams.find(t=>t.id===s.team_id).name]})"

    # --- Maus: Wartung einen Tag nach rechts ---
    x, y = await balken_mitte(tab, "Kolonne Süd", "Wartung")
    await maus_ziehen(tab, x, y, tag, 0)
    await tab.warten(stand + "('Wartung')[0]==='2026-11-13'", 10)
    p.pruefe("Maus: Wartung auf den 13.11., ohne Rückfrage, kein Dialog danach", [await tab.js(stand + "('Wartung')"), await tab.js("konfliktDialog.open"),
             await tab.js("einsatzDialog.open")], [["2026-11-13", "2026-11-13", "Kolonne Süd"], False, False])
    await tab.warte_auf_ruhe()

    # --- Escape bricht ab ---
    x, y = await balken_mitte(tab, "Kolonne Süd", "Wartung")
    await tab.ziehen(x, y, -tag, 0, schritte=5, loslassen=False)
    await tab.cmd("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    await tab.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=x - tag, y=y, button="left", buttons=0, clickCount=1)
    await tab.warte_auf_ruhe()
    p.pruefe("Escape: abgebrochen, nichts verschoben", [await tab.js(stand + "('Wartung')"), await tab.js("einsatzDialog.open")],
             [["2026-11-13", "2026-11-13", "Kolonne Süd"], False])
    await tab.warte_auf_ruhe()

    # --- Klick (3 px Zittern, unter der Schwelle) öffnet ---
    x, y = await balken_mitte(tab, "Ohne Kolonne", "Notdienst")
    await maus_klick(tab, x, y, zittern=3)
    p.pruefe("Klick: der Einsatz öffnet sich, nichts verschoben", [await tab.warten("einsatzDialog.open"), await tab.js(stand + "('Notdienst')")],
             [True, ["2026-11-10", "2026-11-11", None]])
    await tab.warte_auf_ruhe()
    await _dialog_zu(tab)

    # --- Finger: Notdienst einen Tag nach links ---
    await tab.cmd("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    x, y = await balken_tag(tab, "Ohne Kolonne", "Notdienst", 1)  # am zweiten Tag gefasst: der Beginn zählt von dort
    await finger_ziehen(tab, x, y, -tag, 0)
    await tab.warten(stand + "('Notdienst')[0]==='2026-11-09'", 10)
    p.pruefe("Finger: Notdienst auf 09.–10.11.", await tab.js(stand + "('Notdienst')"), ["2026-11-09", "2026-11-10", None])
    await tab.cmd("Emulation.setTouchEmulationEnabled", enabled=False)
    await tab.warte_auf_ruhe()

    # --- nach dem Ziehen mit dem Finger (kein Klick danach) öffnet der nächste Klick ---
    x, y = await balken_mitte(tab, "Ohne Kolonne", "Notdienst")
    await maus_klick(tab, x, y)
    p.pruefe("nach dem Finger: der nächste Klick öffnet", await tab.warten("einsatzDialog.open"), True)
    await tab.warte_auf_ruhe()
    await _dialog_zu(tab)

    # --- Ziehen mit Warnung: Garage in die Zeile Nord ---
    x, y = await balken_mitte(tab, "Kolonne Süd", "Garage Lindenweg 7")
    ziel = await tab.js("(()=>{const a=" + _zeile("Kolonne Süd") + ".getBoundingClientRect(),b=" + _zeile("Kolonne Nord") + ".getBoundingClientRect();"
                        "return b.top+b.height-12-(a.top+a.height/2)})()")
    await maus_ziehen(tab, x, y, 0, ziel)
    p.pruefe("Rückfrage beim Ziehen in die Zeile Nord", await tab.warten("konfliktDialog.open&&document.getElementById('konfliktWarnungen').textContent.length>0", 10), True)
    await tab.bild("ziehen_rueckfrage")
    await tab.js("konfliktDialog.close()")
    p.pruefe("Abbrechen: nichts verschoben", await tab.js(stand + "('Garage Lindenweg 7')"), ["2026-11-03", "2026-11-05", "Kolonne Süd"])

    # --- Klick in eine freie Zelle ---
    async def zelle(zeile, datum):
        x, y = await zelle_mitte(tab, zeile, datum)
        await maus_klick(tab, x, y)
        await tab.warten("einsatzDialog.open&&!!pruefung||einsatzDialog.open&&!!document.getElementById('edMeldung').textContent", 10)
        await tab.warte_auf_ruhe()
        return await tab.js("[document.getElementById('edTitel').textContent,document.getElementById('edKolonne').selectedOptions[0].textContent,"
                            "document.getElementById('edVon').value,document.getElementById('edBis').value,"
                            "[...document.querySelectorAll('#edPersonen .wahl,#edGeraete .wahl')].filter(l=>l.querySelector('input').checked).map(l=>l.querySelector('.wahl-name').textContent)]")
    r = await zelle("Kolonne Süd", "2026-11-02")
    p.pruefe("freie Zelle Süd am 02.11.: Kolonne Süd, ein Tag", r[:4], ["Einsatz planen", "Kolonne Süd – schlägt Kai, Lia, Nele vor", "2026-11-02", "2026-11-02"])
    await _dialog_zu(tab)
    r = await zelle("Ohne Kolonne", "2026-11-06")
    p.pruefe("freie Zelle Ohne Kolonne am 06.11.: ohne Kolonne", r[1:4], ["ohne Kolonne – Personen selbst wählen", "2026-11-06", "2026-11-06"])
    await _dialog_zu(tab)
    r = await zelle("Kran Böcker AHK 36", "2026-11-12")
    p.pruefe("freie Zelle beim Kran am 12.11.: mit dem Kran", ["Kran Böcker AHK 36" in r[4], r[2]], [True, "2026-11-12"])
    await tab.js("document.querySelector('#edArt [data-art=kranvermietung]').click()")
    await tab.warte_auf_ruhe()
    p.pruefe("Art Kranvermietung: der Kran bleibt gewählt", await tab.js("(einsatz.geraete||[]).length===1&&einsatz.art==='kranvermietung'"), True)
    await _dialog_zu(tab)
    await tab.js("document.querySelector('.viewtabs button[data-view=employees]').click()")
    await tab.warten("view==='employees'")
    r = await zelle("Lia Lang", "2026-11-02")
    p.pruefe("freie Zelle bei Lia (Personen) am 02.11.: mit Lia", [r[4], r[2]], [["Lia Lang"], "2026-11-02"])
    await _dialog_zu(tab)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=f"{HEUTE} 10:00"))
