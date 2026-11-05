"""Klicktest: Zuordnung für den DATEV-Export in Einstellungen → Zeitregeln und DATEV (1.9.169, Lohn L1a, Punkt 4, E7, E10).

    Büro – Finanzen  Fin: Zeilen wie vorbelegt (Arbeit 1/1000, Feiertag F/1012, Urlaub U/8000, Krankheit K/1650, Schlechtwetter Winter
                     WA/8195 (seit 1.9.214, bis 1.9.213 „Monatszeile 8110“), Art Weiterbildung 1/1000; Berufsschule (seit 1.9.214 FE ohne
                     Lohnart), Fortbildung, Freizeitausgleich, Schlechtwetter Sommer „nicht exportiert“); Lohnart „10a“ -> Meldung, nichts gespeichert; Freizeitausgleich Z / 1500 gespeichert -> „Wirkt“ und die Art
                     Freizeitausgleich danach „wie die Kategorie – Freizeitausgleich: Z / 1500“ -- Bild; seit 1.9.203 (L1a Stufe 4, Punkt 2):
                     der Satz über der Tabelle nennt die Jahreszeit bei Schlechtwetter; eine gespeicherte Zeile „art:schlechtwetter“ S / 8111
                     (Altbestand, direkt angelegt) „wird übergangen“, ein neuer Wert -> Meldung „Für Schlechtwetter gilt immer die Jahreszeit
                     …“, nichts gespeichert -- Bild; leeren -> „nach der Jahreszeit“; keine JS-Fehler
    Büro – Auftrag   Bea: dieselben Zeilen, Felder gesperrt, kein „Speichern“ -- Bild; keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_lohnarten.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "typeof lohnarten!=='undefined'&&lohnarten.length>0&&!!document.querySelector('#lohnartZeilen [data-wirkt]')"


def _wirkt(schluessel: str) -> str:
    return f"document.querySelector('[data-lohnart=\"{schluessel}\"] [data-wirkt]').innerText"


def _index(schluessel: str) -> str:
    return f"lohnarten.findIndex(z=>z.schluessel==='{schluessel}')"


def befuellen(db, k):
    from app.models import AppUser, LohnartZuordnung

    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Auftrag", role="buero_auftrag", password_hash=k.passwort())
    # seit 1.9.203: eine Zeile, wie sie bis 1.9.202 entstehen konnte -- am heutigen speichern() vorbei
    db.add_all([fin, bea, LohnartZuordnung(schluessel="art:schlechtwetter", kennzeichen="S", lohnart="8111", monatszeile=False)])
    db.commit()
    return {"fin": k.cookies(fin), "bea": k.cookies(bea)}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    vorbelegt = {"arbeit": "1 / 1000", "feiertag": "F / 1012", "kategorie:urlaub": "U / 8000", "kategorie:krankheit": "K / 1650",
                 "schlechtwetter:winter": "WA / 8195", "art:weiterbildung": "1 / 1000", "kategorie:fortbildung": "nicht exportiert",  # seit 1.9.214 WA / 8195
                 "kategorie:freizeitausgleich": "nicht exportiert", "schlechtwetter:sommer": "nicht exportiert",
                 "art:berufsschule": "wie die Kategorie – Fortbildung: nicht exportiert"}
    liste = "[" + ",".join(_wirkt(s) for s in vorbelegt) + "]"

    await tab.anmelden(seed["fin"])
    p.pruefe("Fin: Zuordnung geladen", await tab.oeffnen("/settings#time-rules", BEREIT), True)
    p.pruefe("Fin: vorbelegt nach E7, Leeres sichtbar", await tab.js(liste), list(vorbelegt.values()))
    i = await tab.js(_index("kategorie:freizeitausgleich"))
    await tab.js(f"document.getElementById('lzK-{i}').value='Z';document.getElementById('lzL-{i}').value='10a'")
    await tab.js(f"document.querySelector('[data-klick=lohnart-speichern][data-i=\"{i}\"]').click()")
    p.pruefe("Fin: Lohnart „10a“ abgelehnt", await tab.warten(
        "document.getElementById('lohnartStatus').textContent==='Fehler: Die Lohnart hat 1 bis 4 Ziffern, z. B. 1000.'", 10), True)
    await tab.js(f"document.getElementById('lzL-{i}').value='1500'")
    await tab.warte_auf_neu_geladene_liste(f"document.querySelector('[data-klick=lohnart-speichern][data-i=\"{i}\"]').click()", "#lohnartZeilen")
    p.pruefe("Fin: Freizeitausgleich Z / 1500, die Art folgt der Kategorie", await tab.js(
        f"[{_wirkt('kategorie:freizeitausgleich')},{_wirkt('art:freizeitausgleich')},document.getElementById('lohnartStatus').textContent]"),
        ["Z / 1500", "wie die Kategorie – Freizeitausgleich: Z / 1500", "Gespeichert."])
    await tab.js("document.getElementById('lohnartenBlock').scrollIntoView({block:'start'})")
    await tab.bild("lohnarten_fin")

    # seit 1.9.203: für Schlechtwetter gilt immer die Jahreszeit
    p.pruefe("Fin: der Satz über der Tabelle nennt die Jahreszeit bei Schlechtwetter", await tab.js(
        "document.querySelector('#lohnartenBlock .muted').textContent.includes('Eine Art mit eigener Zuordnung geht ihrer Kategorie vor – "
        "außer bei Schlechtwetter: dort gilt immer die Jahreszeit.')"), True)
    sw = await tab.js(_index("art:schlechtwetter"))
    p.pruefe("Fin: gespeicherte Zeile „art:schlechtwetter“ wird übergangen", await tab.js(f"[{sw}>=0,{_wirkt('art:schlechtwetter')}]"),
             [True, "gespeichert S / 8111 – wird übergangen, es gilt die Jahreszeit (Schlechtwetter Winter bzw. Sommer)"])
    await tab.js(f"document.getElementById('lzL-{sw}').value='8112'")
    await tab.js(f"document.querySelector('[data-klick=lohnart-speichern][data-i=\"{sw}\"]').click()")
    p.pruefe("Fin: neuer Wert für Schlechtwetter abgelehnt, Meldung auf der Seite", await tab.warten(
        "document.getElementById('lohnartStatus').textContent==='Fehler: Für Schlechtwetter gilt immer die Jahreszeit (Zeilen "
        "„Schlechtwetter Winter“ und „Schlechtwetter Sommer“) – eine eigene Zuordnung je Art gibt es dort nicht.'", 10), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: nichts gespeichert", await tab.js(f"[lohnarten[{sw}].lohnart,{_wirkt('art:schlechtwetter')}]"),
             ["8111", "gespeichert S / 8111 – wird übergangen, es gilt die Jahreszeit (Schlechtwetter Winter bzw. Sommer)"])
    await tab.js(f"document.querySelector('[data-lohnart=\"art:schlechtwetter\"]').scrollIntoView({{block:'center'}})")
    await tab.bild("lohnarten_schlechtwetter_abgelehnt")
    await tab.js(f"document.getElementById('lzK-{sw}').value='';document.getElementById('lzL-{sw}').value=''")
    await tab.warte_auf_neu_geladene_liste(f"document.querySelector('[data-klick=lohnart-speichern][data-i=\"{sw}\"]').click()", "#lohnartZeilen")
    p.pruefe("Fin: geleert -> „nach der Jahreszeit“", await tab.js(
        f"[{_wirkt('art:schlechtwetter')},document.getElementById('lohnartStatus').textContent]"),
        ["nach der Jahreszeit (Schlechtwetter Winter bzw. Sommer)", "Gespeichert."])
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    await tab.anmelden(seed["bea"])
    p.pruefe("Bea: geladen", await tab.oeffnen("/settings?als=bea#time-rules", BEREIT), True)
    p.pruefe("Bea: Felder gesperrt, kein Speichern, Werte sichtbar", await tab.js(
        "[[...document.querySelectorAll('#lohnartZeilen input')].every(f=>f.disabled),"
        "[...document.querySelectorAll('#lohnartZeilen [data-klick=lohnart-speichern]')].every(k=>k.hidden),"
        f"{_wirkt('kategorie:freizeitausgleich')}]"), [True, True, "Z / 1500"])
    await tab.js("document.getElementById('lohnartenBlock').scrollIntoView({block:'start'})")
    await tab.bild("lohnarten_bea")
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
