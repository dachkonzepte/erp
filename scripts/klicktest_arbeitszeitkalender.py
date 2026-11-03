"""Klicktest: Arbeitszeitkalender in Einstellungen → Zeitregeln und DATEV (1.9.175, L1a-Nachtrag, Punkt 2).

    Büro – Finanzen  Fin (1440): Heiligabend vorbelegt (24.12., 7,00 h, „Heiligabend – bezahlte Freistellung“, gewerbliche, nur Mo–Fr,
                     aktiv), Zuordnung „BF / Lohnart offen – nicht exportiert“; „+ Kalendertag“ Rosenmontag 15.02. -> neue Zeile und eine
                     Zeile in der Zuordnung; ein zweiter Eintrag am 24.12. -> Meldung, nichts gespeichert; Heiligabend mit 6,5 h -> „6,50 h“;
                     „Zeiten → Abwesenheiten“: Karte „Arbeitszeitkalender“ mit Do 24.12.2026, Mo 15.02.2027 und Fr 24.12.2027, Mias Urlaub 21.12.–01.01.
                     zählt 7 Arbeitstage -- Bilder; keine JS-Fehler
    Büro – Auftrag   Bea: der Kalender sichtbar, ohne „+ Kalendertag“ und „Bearbeiten“; keine JS-Fehler

Stehende Uhr Mi 11.11.2026, 10:00 Uhr.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_arbeitszeitkalender.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = ("typeof kalender!=='undefined'&&kalender.eintraege.length>0&&!!document.querySelector('#kalenderZeilen [data-kalendertag]')"
          "&&typeof lohnarten!=='undefined'&&lohnarten.length>0")
ZEITEN_BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''&&!!window.A"
ZEILE = "[...document.querySelectorAll('[data-kalendertag=\"{s}\"] td')].slice(0,7).map(t=>t.innerText.trim())"
WIRKT = "document.querySelector('[data-lohnart=\"kalender:{s}\"] [data-wirkt]').innerText"


def befuellen(db, k):
    from datetime import date

    from app.absence_requests import create_request
    from app.models import AppUser, Employee

    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    db.add(mia)
    db.flush()
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Auftrag", role="buero_auftrag", password_hash=k.passwort())
    db.add_all([fin, bea])
    db.commit()
    create_request(db, employee_id=mia.id, absence_category="urlaub", start_date=date(2026, 12, 21), end_date=date(2027, 1, 1))
    return {"fin": k.cookies(fin), "bea": k.cookies(bea), "uhr_ms": k.uhr_ms()}


async def _neu(tab, werte: dict):
    await tab.js("document.querySelector('#kalenderBlock [data-lohnregeln-knopf]').click()")
    await tab.js(";".join(f"document.getElementById('{i}').value={v!r}" for i, v in werte.items()))


async def _speichern(tab) -> str:
    await tab.js("document.getElementById('kalenderDialogStatus').textContent='';document.getElementById('kalenderStatus').textContent='';"
                 "saveKalendertag()")
    await tab.warten("document.getElementById('kalenderDialogStatus').textContent!==''||document.getElementById('kalenderStatus').textContent!==''", 10)
    await tab.warte_auf_ruhe()
    return await tab.js("document.getElementById('kalenderDialog').open?document.getElementById('kalenderDialogStatus').textContent"
                        ":document.getElementById('kalenderStatus').textContent")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.browser_uhr_fest(seed["uhr_ms"])

    await tab.anmelden(seed["fin"])
    await tab.fenster(1440, 900)
    p.pruefe("Fin: Kalender geladen", await tab.oeffnen("/settings#time-rules", BEREIT), True)
    p.pruefe("Fin: Heiligabend vorbelegt", await tab.js(ZEILE.format(s="heiligabend")),
             ["24.12.", "Heiligabend", "7,00 h", "Heiligabend – bezahlte Freistellung", "kein Urlaubstag – ein Urlaub über den Tag zählt ihn mit 0",
              "gewerbliche Mitarbeiter, nur Mo–Fr", "aktiv"])
    p.pruefe("Fin: Zuordnung BF ohne Lohnart", await tab.js(WIRKT.format(s="heiligabend")), "BF / Lohnart offen – nicht exportiert")

    await _neu(tab, {"kdName": "Rosenmontag", "kdAbwesenheit": "Rosenmontag – frei", "kdTag": "15", "kdMonat": "2"})
    p.pruefe("Fin: neuer Kalendertag gespeichert", await _speichern(tab), "Gespeichert.")
    p.pruefe("Fin: Rosenmontag in Kalender und Zuordnung", await tab.js(
        "[[...document.querySelectorAll('#kalenderZeilen [data-kalendertag]')].map(z=>z.dataset.kalendertag),"
        + WIRKT.format(s="rosenmontag") + "]"), [["rosenmontag", "heiligabend"], "nicht exportiert"])

    await _neu(tab, {"kdName": "Weihnachten", "kdAbwesenheit": "frei", "kdTag": "24", "kdMonat": "12"})
    p.pruefe("Fin: zweiter Eintrag am 24.12. abgelehnt", await _speichern(tab), "Fehler: Für den 24.12. steht schon „Heiligabend“ im Kalender.")
    await tab.js("document.getElementById('kalenderDialog').close()")
    p.pruefe("Fin: nichts gespeichert", await tab.js("kalender.eintraege.length"), 2)

    await tab.js("document.querySelector('[data-kalendertag=\"heiligabend\"] [data-klick=kalender-oeffnen]').click()")
    p.pruefe("Fin: Dialog mit den Werten von Heiligabend", await tab.js(
        "[document.getElementById('kalenderTitel').textContent,document.getElementById('kdSoll').value,document.getElementById('kdTag').value,"
        "document.getElementById('kdMonat').value,document.getElementById('kdUrlaub').value,document.getElementById('kdGewerblich').checked]"),
        ["Kalendertag – Heiligabend", "7,00", "24", "12", "kein_urlaubstag", True])
    await tab.js("document.getElementById('kdSoll').value='6,5'")
    p.pruefe("Fin: Sollzeit 6,5 h gespeichert", await _speichern(tab), "Gespeichert.")
    p.pruefe("Fin: Zeile zeigt 6,50 h", await tab.js(ZEILE.format(s="heiligabend") + "[2]"), "6,50 h")
    await tab.js("document.getElementById('kalenderBlock').scrollIntoView({block:'start'})")
    await tab.bild("kalender_fin")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    p.pruefe("Fin: Zeiten geladen", await tab.oeffnen("/zeiten#abwesenheiten", ZEITEN_BEREIT + "&&!document.getElementById('abwKalender').hidden"), True)
    p.pruefe("Fin: Karte Arbeitszeitkalender", await tab.js(
        "[...document.querySelectorAll('#abwKalenderListe .zeile')].map(z=>z.querySelector('.zeile-name').innerText+' | '"
        "+z.querySelector('.zeile-unter').innerText)"),
        ["Heiligabend – bezahlte Freistellung | Do 24.12.2026 · Sollzeit 6,50 h · für gewerbliche Mitarbeiter · gilt von selbst, ohne Antrag",
         "Rosenmontag – frei | Mo 15.02.2027 · für gewerbliche Mitarbeiter · gilt von selbst, ohne Antrag",
         "Heiligabend – bezahlte Freistellung | Fr 24.12.2027 · Sollzeit 6,50 h · für gewerbliche Mitarbeiter · gilt von selbst, ohne Antrag"])
    p.pruefe("Fin: Mias Urlaub zählt 7 Arbeitstage", await tab.js(
        "[...document.querySelectorAll('#abwListe .zeile-unter')].map(z=>z.innerText.split(' · ').slice(0,2).join(' · '))[0]"),
        "Mo 21.12.2026–Fr 01.01.2027 · 7 Arbeitstage")
    await tab.bild("kalender_zeiten_abwesenheiten")
    p.pruefe("Fin: keine JS-Fehler in Zeiten", tab.fehler, [])

    await tab.anmelden(seed["bea"])
    p.pruefe("Bea: geladen", await tab.oeffnen("/settings?als=bea#time-rules", BEREIT), True)
    p.pruefe("Bea: Kalender sichtbar, ohne „+ Kalendertag“ und „Bearbeiten“", await tab.js(
        "[document.querySelectorAll('#kalenderZeilen [data-kalendertag]').length,document.querySelector('#kalenderBlock [data-lohnregeln-knopf]').hidden,"
        "[...document.querySelectorAll('#kalenderZeilen [data-klick=kalender-oeffnen]')].every(k=>k.hidden)]"), [2, True, True])
    await tab.js("document.getElementById('kalenderBlock').scrollIntoView({block:'start'})")
    await tab.bild("kalender_bea")
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
