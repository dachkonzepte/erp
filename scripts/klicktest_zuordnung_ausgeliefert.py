"""Klicktest: die Zuordnung für den DATEV-Export im ausgelieferten Zustand (1.9.222, L1a Stufe 7, Punkt 5) -- Einstellungen → Zeitregeln und DATEV.

    Büro – Finanzen  Fin (1440): eine frische Installation, in der Zuordnung nichts angelegt oder geändert (nur die Grunddaten des Starts):
                     jede Zeile mit „Wirkt“ wie ausgeliefert -- Arbeit 1/1000, Feiertag F/1012, Urlaub U/8000, Krankheit K/1650, Fortbildung,
                     Unbezahlt, Freizeitausgleich und Schlechtwetter Sommer „nicht exportiert“, Schlechtwetter Winter WA/8195, Heiligabend FR/1080,
                     Silvester UU ohne Lohnart, Weiterbildung 1/1000, Berufsschule FE ohne Lohnart; Stunden bei Schlechtwetter „Sollzeit −
                     gebuchte Arbeit“; das Häkchen Monatszeile bei Winter gesperrt mit Hinweis, bei Sommer frei -- Bild der ganzen Zuordnung
                     (die Tabelle ohne eigene Bildlaufleiste, alle Zeilen auf einem Bild); keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_zuordnung_ausgeliefert.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "typeof lohnarten!=='undefined'&&lohnarten.length>0&&!!document.querySelector('#lohnartZeilen [data-wirkt]')"
MIT = " – exportiert mit Lohnart"
OHNE = " – exportiert, Stunden ohne Lohnart"
AUSGELIEFERT = {
    "arbeit": "1 / 1000" + MIT, "mehrarbeit_azubi": "AA / 1900" + MIT, "feiertag": "F / 1012" + MIT, "kategorie:urlaub": "U / 8000" + MIT, "kategorie:krankheit": "K / 1650" + MIT,
    "kategorie:fortbildung": "nicht exportiert", "kategorie:unbezahlt": "nicht exportiert", "kategorie:freizeitausgleich": "nicht exportiert",
    "schlechtwetter:winter": "WA / 8195" + MIT, "schlechtwetter:sommer": "nicht exportiert",
    "kalender:heiligabend": "FR / 1080" + MIT, "kalender:silvester": "UU" + OHNE,
    "art:weiterbildung": "1 / 1000" + MIT, "art:berufsschule": "FE" + OHNE,
}


def befuellen(db, k):
    from app.models import AppUser

    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    db.add(fin)  # sonst nichts: die Zuordnung so, wie der Start sie anlegt (app/grunddaten.py)
    db.commit()
    return {"fin": k.cookies(fin)}


async def _bild_des_blocks(tab, element_id: str, name: str) -> None:
    """Das Element ganz, über das Fenster hinaus (die Tabelle zuvor ohne eigene Höhenbegrenzung). Feste und klebende Elemente (Kopfzeile der
    Seite) werden für die Aufnahme unsichtbar -- sonst liegen sie über dem oberen Rand des Blocks."""
    await tab.js("[...document.querySelectorAll('body *')].filter(e=>['fixed','sticky'].includes(getComputedStyle(e).position)"
                 "&&!e.closest('#" + element_id + "')).forEach(e=>e.style.visibility='hidden')")
    r = await tab.js(f"(e=>{{const r=e.getBoundingClientRect();return [r.left+window.scrollX,r.top+window.scrollY,r.width,r.height]}})"
                     f"(document.getElementById('{element_id}'))")
    data = (await tab.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                          clip={"x": max(0, r[0] - 16), "y": max(0, r[1] - 16), "width": r[2] + 32, "height": r[3] + 32, "scale": 1}))["data"]
    (tab.shots / f"{name}.png").write_bytes(base64.b64decode(data))


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["fin"])
    await tab.fenster(1440, 900)
    p.pruefe("Fin: Zuordnung geladen", await tab.oeffnen("/settings#time-rules", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: jede Zeile wie ausgeliefert", await tab.js(
        "Object.fromEntries([...document.querySelectorAll('#lohnartZeilen tr[data-lohnart]')]"
        ".filter(tr=>!tr.dataset.lohnart.startsWith('art:')||['art:weiterbildung','art:berufsschule'].includes(tr.dataset.lohnart))"
        ".map(tr=>[tr.dataset.lohnart,tr.querySelector('[data-wirkt]').textContent.trim()]))"), AUSGELIEFERT)
    p.pruefe("Fin: die übrigen Arten wie ihre Kategorie", await tab.js(
        "[...document.querySelectorAll('#lohnartZeilen tr[data-lohnart^=\"art:\"]')].filter(tr=>!['art:weiterbildung','art:berufsschule']"
        ".includes(tr.dataset.lohnart)).every(tr=>tr.querySelector('[data-wirkt]').textContent.startsWith('wie die Kategorie'))"), True)
    p.pruefe("Fin: Stunden bei Schlechtwetter", await tab.js(
        "['schlechtwetter:winter','schlechtwetter:sommer'].map(s=>document.querySelector(`[data-lohnart=\"${s}\"] td.small`).textContent.trim())"),
        ["Sollzeit − gebuchte Arbeit", "Sollzeit − gebuchte Arbeit"])
    p.pruefe("Fin: Monatszeile bei Winter gesperrt mit Hinweis, bei Sommer frei", await tab.js(
        "['schlechtwetter:winter','schlechtwetter:sommer'].map(s=>{const tr=document.querySelector(`[data-lohnart=\"${s}\"]`),"
        "m=tr.querySelector('input[type=checkbox]'),h=tr.querySelector('[id^=lzMH-]');return [m.disabled,!h.hidden]})"),
        [[True, True], [False, False]])
    await tab.js("document.querySelector('#lohnartenBlock div[style*=\"max-height\"]').style.maxHeight='none';"
                 "document.getElementById('lohnartenBlock').scrollIntoView({block:'start'})")
    await _bild_des_blocks(tab, "lohnartenBlock", "zuordnung_ausgeliefert")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
