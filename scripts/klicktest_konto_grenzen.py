"""Klicktest: Grenzen des Arbeitszeitkontos (1.9.336, Lohn L2c-3, Punkt 3).

Testdaten wie klicktest_konto_monat.py (stehende Uhr Mi 03.02.2027; Ada Arbeit mit Startwert +12,50 h, im Januar Saldo +1,50, bis 02.02. Stand +15,00 h; Bo Bau
ohne Startwert); Fiona Finanz (Büro – Finanzen).

    Zeitregeln    „Arbeitszeitkonto: Hinweis ab Plus“ 10 und „… ab Minus“ 5 getippt und gespeichert, nach dem Neuladen stehen sie da; „0“ abgelehnt
    Prüfen        Karte „Arbeitszeitkonto an der Grenze“ mit „Ada Arbeit: Stand +15,00 h – Hinweis ab Plus 10,00 h“ -- Bo nicht (ohne Startwert)
    Monat & Lohn  im Januar an Ada „Hinweis ab Plus 10,00 h“ unter dem Stand
    Bilder        Zeitregeln mit den Grenzen und „Prüfen“ mit der Karte bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_konto_grenzen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_konto_monat import befuellen, monat  # noqa: E402

REGELN_BEREIT = "document.getElementById('kvTage').value!==''&&document.getElementById('kontenZeilen').children.length>0"
PRUEFEN_BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''"


async def regeln(tab, p, name):
    p.pruefe(f"{name}: Zeitregeln geladen", await tab.oeffnen(f"/settings?n={name}#time-rules", REGELN_BEREIT), True)
    await tab.warte_auf_ruhe()


async def tippen(tab, feld, text):
    await tab.js(f"(()=>{{const f=document.getElementById('{feld}');f.value='';f.focus()}})()")
    await tab.cmd("Input.insertText", text=text)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=m=>{console.error('confirm(): '+m);return false};")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["fiona"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", "!!window.P")
    await tab.js("localStorage.setItem('erp_theme','light')")
    await regeln(tab, p, "leer")
    p.pruefe("vorher: beide leer", await tab.js("[document.getElementById('kvPlus').value,document.getElementById('kvMinus').value]"), ["", ""])
    await tippen(tab, "kvPlus", "0")
    await tab.js("document.querySelector('[data-klick=konten-vorgaben]').click()")
    p.pruefe("„0“ abgelehnt", await tab.warten("document.getElementById('kontenVorgabenStatus').textContent.includes('größer als 0')", 10), True)
    await tippen(tab, "kvPlus", "10")
    await tippen(tab, "kvMinus", "5")
    await tab.js("document.querySelector('[data-klick=konten-vorgaben]').click()")
    p.pruefe("gespeichert", await tab.warten("document.getElementById('kontenVorgabenStatus').textContent==='Gespeichert.'", 10), True)
    await regeln(tab, p, "danach")
    p.pruefe("nach dem Neuladen stehen sie da", await tab.js("[document.getElementById('kvPlus').value,document.getElementById('kvMinus').value]"),
             ["10,00", "5,00"])
    p.pruefe("Prüfen geladen", await tab.oeffnen("/zeiten?n=p1", PRUEFEN_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Prüfen: die Karte mit Ada, ohne Bo", await tab.js(
        "[document.getElementById('grenzeKarte').hidden,document.getElementById('grenzeZahl').textContent,"
        "[...document.querySelectorAll('#grenzeListe li')].map(li=>li.textContent)]"),
        [False, "1 Person", ["Ada Arbeit: Stand +15,00 h – Hinweis ab Plus 10,00 h"]])
    await monat(tab, p, "jan", "2027-01")
    p.pruefe("Monat & Lohn: an Ada der Hinweis", await tab.js(
        "[...document.querySelectorAll('#kontoZeilen tr')].map(tr=>(tr.querySelector('.konto-grenze')||{}).textContent||'')"),
        ["Hinweis ab Plus 10,00 h", ""])
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            await regeln(tab, p, f"bild_r_{breite}_{name}")
            if mobil:
                p.pruefe(f"Bild Zeitregeln {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('kvPlus').scrollIntoView({block:'center'})")
            await tab.bild(f"einstellungen_zeitregeln_grenzen_{breite}_{name}")
            p.pruefe(f"Bild Prüfen {breite} {name}: geladen", await tab.oeffnen(f"/zeiten?n=bild_{breite}_{name}", PRUEFEN_BEREIT), True)
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Bild Prüfen {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('grenzeKarte').scrollIntoView({block:'center'})")
            await tab.bild(f"zeiten_pruefen_grenze_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-02-03 10:00"))
