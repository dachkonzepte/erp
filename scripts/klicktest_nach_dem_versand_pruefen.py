"""Klicktest: „Nach dem Versand geändert“ in „Prüfen“ (1.9.331, Lohn L2c-2, Punkt 4).

Testdaten wie klicktest_nach_dem_versand.py (die Dezember-Datei gesendet, danach vier Änderungen durch Anna Admin); Fiona Finanz (Büro – Finanzen),
dazu Bea Büro (Büro – Auftrag). Stehende Uhr Mo 04.01.2027 10:00 -- bis gestern gibt es keinen Tag ohne Eintrag (01.01. Feiertag,
dann Wochenende): die Karte ist der einzige Hinweis in „Prüfen“.

    Fiona         „Prüfen“: die Karte „Nach dem Versand geändert“ mit „4 Änderungen“ und „Dezember 2026: 4 Änderungen nach dem Versand“ -- ohne Namen, mit dem
                  Weg „Monat & Lohn“ (/zeiten?lohnmonat=2026-12#monat); der Weg öffnet „Monat & Lohn“ im Dezember mit der Liste
    Bea           keine Karte (die Liste dahinter sieht nur Admin und Büro – Finanzen)
    Bilder        „Prüfen“ mit der Karte bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_nach_dem_versand_pruefen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_nach_dem_versand import PRUEFEN_BEREIT, befuellen as befuellen_versand  # noqa: E402

KARTE = ("(()=>{const k=document.getElementById('nachVersandKarte');return [k.hidden,document.getElementById('nachVersandZahl').textContent,"
         "[...k.querySelectorAll('li')].map(li=>[li.querySelector('.text').textContent,li.querySelector('a').textContent,li.querySelector('a').getAttribute('href')])]})()")


def befuellen(db, k):
    from app.models import AppUser
    seed = befuellen_versand(db, k)
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    db.add(bea)
    db.commit()
    return {**seed, "bea": k.cookies(bea)}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true;")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["fiona"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", PRUEFEN_BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Fiona: Prüfen geladen", await tab.oeffnen("/zeiten?n=1", PRUEFEN_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fiona: die Karte mit der Zahl, ohne Namen, mit dem Weg", await tab.js(KARTE), [
        False, "4 Änderungen", [["Dezember 2026: 4 Änderungen nach dem Versand", "Monat & Lohn", "/zeiten?lohnmonat=2026-12#monat"]]])
    p.pruefe("Fiona: kein Name in der Karte", await tab.js(
        "['Ada','Bo ','Cem'].filter(n=>document.getElementById('nachVersandKarte').textContent.includes(n))"), [])
    p.pruefe("Fiona: die Karte ist der einzige Hinweis, „Alles erledigt“ nicht sichtbar", await tab.js(
        "['offenKarte','pauseKarte','rueckfahrtKarte','ohneEintragKarte','abwArbeitKarte','nachVersandKarte','antragKarte']"
        ".filter(id=>!document.getElementById(id).hidden).concat([document.getElementById('allesGut').hidden])"), ["nachVersandKarte", True])
    await tab.js("document.querySelector('#nachVersandListe a').click()")
    p.pruefe("der Weg öffnet „Monat & Lohn“ im Dezember mit der Liste", await tab.warten(
        "location.search==='?lohnmonat=2026-12'&&!!window.M&&M.monat==='2026-12'&&document.getElementById('nvText').textContent==='4 Änderungen nach dem Versand'"
        "&&!document.getElementById('reiter-monat').hidden", 15), True)
    await tab.warte_auf_ruhe()

    await tab.anmelden(seed["bea"])
    p.pruefe("Bea: Prüfen geladen", await tab.oeffnen("/zeiten?n=2", PRUEFEN_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Bea: keine Karte", await tab.js("[document.getElementById('nachVersandKarte').hidden,document.getElementById('nachVersandListe').children.length]"),
             [True, 0])

    await tab.anmelden(seed["fiona"])
    n = 2
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            n += 1
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            p.pruefe(f"Bild {breite} {name}: geladen", await tab.oeffnen(f"/zeiten?n={n}", PRUEFEN_BEREIT), True)
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Bild {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('nachVersandKarte').scrollIntoView({block:'center'})")
            await tab.bild(f"zeiten_pruefen_nach_dem_versand_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-01-04 10:00"))
