"""Klicktest: „Besprochen“ in „Nach dem Versand geändert“ (1.9.330, Lohn L2c-2, Punkt 3).

Testdaten wie klicktest_nach_dem_versand.py (die Dezember-Datei gesendet, danach vier Änderungen durch Anna Admin); Fiona Finanz (Büro – Finanzen).

    vorher        „4 Änderungen nach dem Versand“, darunter „Notiz zum Telefonat“ und „Besprochen“
    ohne Notiz    „Notiz fehlt – z. B. „Telefonat 05.02.“.“, nichts gesendet
    Besprochen    mit „Telefonat 05.02.“ (getippt): danach „Keine Änderung seit „Besprochen“.“, keine Tabelle, kein „Besprochen“ mehr, Bezug „besprochen <Zeitpunkt>
                  · Fiona Finanz – „Telefonat 05.02.““; in der Ablage eine Zeile „Besprochen … – „Telefonat 05.02.““ ohne Knopf „An das Steuerbüro gesendet“
    Bilder        vor dem Klick die Liste mit Notizfeld (1440, hell); danach die Karte und die Ablage bei 1440 und 412 px, hell und dunkel (412: nichts
                  läuft über)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_besprochen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_nach_dem_versand import GELADEN, PRUEFEN_BEREIT, ZEITPUNKT, befuellen, monat_zurueck  # noqa: E402

ABLAGE = ("[...document.querySelectorAll('#lohnDateien li')].map(li=>[li.dataset.art,li.querySelector('.text').textContent.replace(" + ZEITPUNKT
          + ",'<Zeitpunkt>').replace(/Prüfsumme .*$/,'Prüfsumme …'),[...li.querySelectorAll('button')].map(b=>b.textContent)])")


async def dezember(tab, p, name):
    p.pruefe(f"{name}: Monat & Lohn geladen", await tab.oeffnen(f"/zeiten?n={name}#monat", GELADEN), True)
    await tab.warte_auf_ruhe()
    await monat_zurueck(tab, p, name, "2026-12")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true;")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["fiona"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", PRUEFEN_BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await dezember(tab, p, "vorher")
    p.pruefe("vorher: vier Änderungen, „Besprochen“ sichtbar", await tab.js(
        "[document.getElementById('nvText').textContent,document.getElementById('nvBesprochen').hidden]"), ["4 Änderungen nach dem Versand", False])
    p.pruefe("ohne Notiz: Meldung, nichts gesendet", await tab.js(
        "(()=>{document.getElementById('nvBesprochenKnopf').click();return document.getElementById('nvFehlt').textContent})()"),
        "Notiz fehlt – z. B. „Telefonat 05.02.“.")
    p.pruefe("ohne Notiz: keine Abgleich-Zeile", await tab.js("[...document.querySelectorAll('#lohnDateien li')].map(li=>li.dataset.art)"), ["datei"])
    await tab.js("document.getElementById('nvNotiz').focus()")
    await tab.cmd("Input.insertText", text="Telefonat 05.02.")
    p.pruefe("getippt: die Meldung ist weg", await tab.js("document.getElementById('nvFehlt').textContent"), "")
    await tab.js("document.getElementById('nachVersand').scrollIntoView({block:'start'});window.scrollBy(0,-80)")
    await tab.bild("zeiten_monat_besprochen_vorher_1440_hell")  # die Liste mit Notizfeld und „Besprochen“, vor dem Klick
    p.pruefe("Besprochen, neu geladen", await tab.warte_auf_neu_geladene_liste("document.getElementById('nvBesprochenKnopf').click()", "#lohnDateien li"), True)
    p.pruefe("danach: keine Änderung, keine Tabelle, kein „Besprochen“", await tab.js(
        "[document.getElementById('nvText').textContent,document.getElementById('nvTabelle').hidden,document.getElementById('nvBesprochen').hidden,"
        "document.getElementById('nvNotiz').value]"), ["Keine Änderung seit „Besprochen“.", True, True, ""])
    p.pruefe("Bezug: besprochen, mit Notiz", await tab.js(f"document.getElementById('nvBezug').textContent.replace({ZEITPUNKT},'<Zeitpunkt>')"),
             "Bezug: besprochen <Zeitpunkt> · Fiona Finanz – „Telefonat 05.02.“")
    p.pruefe("Meldung", await tab.js("document.getElementById('ergebnis').textContent"), "Besprochen – der Stand von heute ist abgelegt.")
    p.pruefe("Ablage: die Abgleich-Zeile oben, ohne Knopf; die Datei gesendet", await tab.js(ABLAGE), [
        ["abgleich", "Besprochen <Zeitpunkt> · Fiona Finanz – „Telefonat 05.02.“ · Prüfsumme …", []],
        ["datei", "Abgelegt <Zeitpunkt> · Fiona Finanz · Prüfsumme …", []]])
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            await dezember(tab, p, f"bild_{breite}_{name}")
            if mobil:
                p.pruefe(f"Bild {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('lohnDateien').scrollIntoView({block:'start'});window.scrollBy(0,-120)")
            await tab.bild(f"zeiten_monat_besprochen_ablage_{breite}_{name}")
            await tab.js("document.getElementById('nachVersand').scrollIntoView({block:'start'});window.scrollBy(0,-80)")
            await tab.bild(f"zeiten_monat_besprochen_karte_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-01-05 10:00"))
