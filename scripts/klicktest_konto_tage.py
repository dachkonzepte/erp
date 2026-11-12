"""Klicktest: „Tage ansehen“ im Arbeitszeitkonto (1.9.335, Lohn L2c-3, Punkt 2).

Testdaten wie klicktest_konto_monat.py (Januar 2027: Ada Arbeit mit Startwert, 8,00 h je Arbeitstag, Urlaub am 13.01., Freizeitausgleich am 20.01.; Bo Bau
ohne Startwert, der 25.01. ohne Eintrag); Fiona Finanz (Büro – Finanzen).

    Ada           „Tage ansehen“ öffnet den Dialog „Tage im Konto · Ada Arbeit“ -- je Tag mit Sollzeit Soll, Ist, Gutschrift, Saldo, Vermerk: der Feiertag
                  gutgeschrieben, ein Arbeitstag +0,50, der Urlaub gutgeschrieben, der Freizeitausgleich „zählt nicht“ (−7,50); darunter der Monat
    Bo            der 25.01. „kein Eintrag – zählt als Minus“; im Kopf „Startwert folgt“
    Bilder        Adas Tage bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_konto_tage.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_konto_monat import befuellen, monat  # noqa: E402

TAG = ("(t=>{const tr=[...document.querySelectorAll('#ktZeilen tr')].find(z=>z.children[0].textContent.includes(t));"
       "return tr?[...tr.children].map(td=>td.textContent.trim()):null})")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=m=>{console.error('confirm(): '+m);return false};")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["fiona"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", "!!window.P")
    await tab.js("localStorage.setItem('erp_theme','light')")
    await monat(tab, p, "jan", "2027-01")
    await tab.js("document.querySelectorAll('#kontoZeilen [data-aktion=konto-tage]')[0].click()")
    p.pruefe("Ada: der Dialog mit Name und Stand", await tab.js(
        "[document.getElementById('kontoTageDialog').open,document.getElementById('ktTitel').textContent,document.getElementById('ktUnter').textContent,"
        "document.getElementById('ktVorlaeufig').textContent]"),
        [True, "Tage im Konto · Ada Arbeit", "Januar 2027 · Stand am Monatsende: +14,00 h", "vorläufig – maßgeblich ist die Lohnabrechnung"])
    p.pruefe("Ada: der Feiertag gutgeschrieben", await tab.js(TAG + "('01.01.')"),
             ["Fr 01.01.", "7,50 h", "7,50 h", "7,50 h", "0,00 h", "Feiertag 7,50 h gutgeschrieben"])
    p.pruefe("Ada: ein Arbeitstag +0,50", await tab.js(TAG + "('04.01.')"), ["Mo 04.01.", "7,50 h", "8,00 h", "0,00 h", "+0,50 h", ""])
    p.pruefe("Ada: der Urlaub gutgeschrieben", await tab.js(TAG + "('13.01.')"),
             ["Mi 13.01.", "7,50 h", "7,50 h", "7,50 h", "0,00 h", "Urlaub 7,50 h gutgeschrieben"])
    p.pruefe("Ada: der Freizeitausgleich zählt nicht", await tab.js(TAG + "('20.01.')"),
             ["Mi 20.01.", "7,50 h", "0,00 h", "0,00 h", "-7,50 h", "Freizeitausgleich 7,50 h – zählt nicht"])
    p.pruefe("Ada: kein Tag ohne Sollzeit (Wochenende)", await tab.js(TAG + "('02.01.')"), None)
    p.pruefe("Ada: der Monat", await tab.js("[...document.querySelectorAll('#ktSumme td')].map(td=>td.textContent.trim())"),
             ["Monat", "157,50 h", "159,00 h", "15,00 h", "+1,50 h", ""])
    await tab.js("document.getElementById('ktZu').click()")
    await tab.js("document.querySelectorAll('#kontoZeilen [data-aktion=konto-tage]')[1].click()")
    p.pruefe("Bo: kein Eintrag zählt als Minus, ohne Startwert", await tab.js(
        "[" + TAG + "('25.01.'),document.getElementById('ktUnter').textContent]"),
        [["Mo 25.01.", "7,50 h", "0,00 h", "0,00 h", "-7,50 h", "kein Eintrag – zählt als Minus"], "Januar 2027 · Stand am Monatsende: Startwert folgt"])
    await tab.js("document.getElementById('ktZu').click()")
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            await monat(tab, p, f"bild_{breite}_{name}", "2027-01")
            await tab.js("document.querySelectorAll('#kontoZeilen [data-aktion=konto-tage]')[0].click()")
            p.pruefe(f"Bild {breite} {name}: Dialog offen", await tab.warten("document.getElementById('kontoTageDialog').open", 5), True)
            if mobil:
                p.pruefe(f"Bild {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.bild(f"zeiten_monat_konto_tage_{breite}_{name}")
            await tab.js("document.getElementById('ktZu').click()")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-02-03 10:00"))
