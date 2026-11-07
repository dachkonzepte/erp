"""Klicktest: die Ansichten „Personen“ und „Geräte“ nach der Zeichnung entwurf-stufe6/plantafel-personen.html (1.9.250, Stufe 6, R4, Punkt 3).

Testdaten wie klicktest_plantafel_tafel (Zeichnung KW 45–46), dazu Bea Bauer (Bauleiterin, ohne Kolonne, Konto „bea“ mit Rolle Büro – Auftrag) mit vier
Terminen im Kalender: Di 03.11. 10:00 Aufmaß, Do 05.11. 08:00 Angebot vor Ort, Fr 06.11. 09:00 privat „Zahnarzt“, Fr 13.11. 14:00 Abnahme.
Stehende Uhr Di 03.11.2026 10:00.

    Gruppen      KOLONNE NORD (Tom KF, Mia, Ole), KOLONNE SÜD (Kai KF, Lia, Nele), BAULEITUNG · TERMINE AUS DEM KALENDER (Bea); jede Person einmal
    Zeile        Tom „Kolonnenführer“; Kai „Kolonnenführer“ und rot „doppelt 03.–05.11.“; Nele „Antrag 05.–06.11.“; Bea „Bauleiterin“
    Balken       nur die Warnungen und Hinweise der Person: Kai „Am Wasserturm 4 · mit Nord“ und „Garage“ mit Warnung (doppelt), Mia und Ole am selben
                 Einsatz ohne, Nele „Garage“ mit dem Punkt für ihren Antrag; Tom „Urlaub · genehmigt“ schraffiert; Nele „Urlaub · beantragt“ gestrichelt; Lia
                 „Kran Böcker AHK 36 · Vermietung“ blau; Bea die Termine zweizeilig (Uhrzeit über dem Titel), der private „Belegt“
    Maße         1440 und 1280 px: kein Balken verdeckt einen anderen, jeder Text sichtbar oder im title; hell und dunkel als Bild
    Büro – Auftrag  als Bea: Tom „abwesend“ und Nele „beantragt“ ohne Art; ihr eigener privater Termin mit Titel
    Geräte       Kran mit dem Termin aus seinem Postfach („Müller“, 10.–11.11.) und der Vermietung, die Pritschen
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_personen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_plantafel_tafel import BEREIT, HEUTE, TEXTE, UHR_MS, UNTER, VERDECKT, ZEILEN  # noqa: E402
from klicktest_plantafel_tafel import befuellen as tafel_befuellen  # noqa: E402


def befuellen(db, k):
    from datetime import datetime
    from decimal import Decimal

    from app.models import AppUser, CalendarEvent, Employee

    seed = tafel_befuellen(db, k)
    bea = Employee(employee_number="M-7", first_name="Bea", last_name="Bauer", employee_group="angestellt", job_title="Bauleiterin",
                   weekly_hours=Decimal("40"), active=True)
    db.add(bea); db.flush()
    konto = AppUser(username="bea", display_name="Bea Bauer", role="buero_auftrag", employee_id=bea.id, password_hash=k.passwort())
    db.add(konto); db.flush()
    for tag, stunde, titel, privat in ((3, 10, "Aufmaß", False), (5, 8, "Angebot vor Ort", False), (6, 9, "Zahnarzt", True), (13, 14, "Abnahme", False)):
        db.add(CalendarEvent(title=titel, start_at=datetime(2026, 11, tag, stunde), end_at=datetime(2026, 11, tag, stunde + 1), owner_user_id=konto.id,
                             is_private=privat))
    db.commit()
    return {**seed, "bea": k.cookies(konto)}


# je Zeile die Balken: [Text, Art] -- Art: abwesend, beantragt, termin, kran, vorlaeufig, fest; „!“ bei Warnung, „·“ bei Hinweis
BALKEN_JE_ZEILE = ("(n=>[...[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent.trim()===n)"
                   ".querySelectorAll('.slot')].map(s=>[s.querySelector('.slot-text').textContent.trim(),"
                   "['abwesend','beantragt','termin','kran','vorlaeufig','fest'].find(c=>s.classList.contains(c))+(s.classList.contains('conflict')?' !':'')"
                   "+(s.querySelector('.hinweis-punkt')?' ·':'')]))")


async def ansicht(tab, name):
    await tab.js(f"document.querySelector('.viewtabs button[data-view={name}]').click()")
    await tab.warten(f"view==='{name}'&&!!document.querySelector('#planner .planner-row')")
    await tab.warte_auf_ruhe()


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_ruhe()
    await ansicht(tab, "employees")

    p.pruefe("Gruppen nach Kolonnen, dann Bauleitung; jede Person einmal", await tab.js(ZEILEN),
             ["[Kolonne Nord]", "Tom Monteur", "Mia Monteurin", "Ole Offen", "[Kolonne Süd]", "Kai Kolb", "Lia Lang", "Nele Neu",
              "[Bauleitung · Termine aus dem Kalender]", "Bea Bauer"])
    p.pruefe("Unterzeilen: KF, doppelt, Antrag, Funktion", [await tab.js(UNTER + f"('{n}')") for n in ("Tom Monteur", "Kai Kolb", "Nele Neu", "Bea Bauer", "Mia Monteurin")],
             [["Kolonnenführer"], ["Kolonnenführer", "doppelt 03.–05.11."], ["Antrag 05.–06.11."], ["Bauleiterin"], []])
    p.pruefe("„doppelt“ rot, die übrigen Unterzeilen nicht", await tab.js(
        "[...document.querySelectorAll('#planner .row-label .unter.warn')].map(u=>u.textContent)"), ["doppelt 03.–05.11."])
    p.pruefe("Tom: Urlaub genehmigt schraffiert, KW 46 Wasserturm", await tab.js(BALKEN_JE_ZEILE + "('Tom Monteur')"),
             [["Am Wasserturm 4", "fest"], ["Urlaub · genehmigt", "abwesend"]])
    p.pruefe("Mia: derselbe Einsatz ohne Warnung (sie betrifft Kai)", await tab.js(BALKEN_JE_ZEILE + "('Mia Monteurin')"),
             [["Am Wasserturm 4", "fest"], ["Am Wasserturm 4", "fest"]])
    p.pruefe("Kai: mit Nord (Warnung), Garage (Warnung), Wartung", await tab.js(BALKEN_JE_ZEILE + "('Kai Kolb')"),
             [["Am Wasserturm 4 · mit Nord", "fest !"], ["Garage Lindenweg 7", "vorlaeufig !"], ["Wartung", "fest"]])
    p.pruefe("Lia: Kranvermietung mit dem Gerät, Notdienst", await tab.js(BALKEN_JE_ZEILE + "('Lia Lang')"),
             [["Kran Böcker AHK 36 · Vermietung", "kran"], ["Notdienst", "fest"]])
    p.pruefe("Nele: Garage mit dem Punkt für ihren Antrag (Kais Warnung nicht), Urlaub beantragt gestrichelt", await tab.js(BALKEN_JE_ZEILE + "('Nele Neu')"),
             [["Garage Lindenweg 7", "vorlaeufig ·"], ["Urlaub · beantragt", "beantragt"]])
    p.pruefe("Bea: Termine aus dem Kalender, privat „Belegt“", await tab.js(BALKEN_JE_ZEILE + "('Bea Bauer')"),
             [["10:00 Aufmaß", "termin"], ["08:00 Angebot vor Ort", "termin"], ["09:00 Belegt", "termin"], ["14:00 Abnahme", "termin"]])
    p.pruefe("Termin zweizeilig: Uhrzeit über dem Titel", await tab.js(
        "(()=>{const t=[...document.querySelectorAll('#planner .slot.termin')].find(s=>s.textContent.includes('Aufmaß')).querySelector('.slot-text');"
        "const [a,b]=[...t.children].map(x=>x.getBoundingClientRect());return [t.children.length,b.top>=a.bottom-1]})()"), [2, True])
    p.pruefe("1440 px: kein Balken verdeckt einen anderen", await tab.js(VERDECKT), [])
    p.pruefe("1440 px: jeder Text sichtbar oder im title", await tab.js(TEXTE), [])
    await tab.bild("personen_1440_hell")
    await tab.fenster(1280, 900)
    await tab.warte_auf_ruhe()
    p.pruefe("1280 px: die Seite läuft nicht über", await tab.ueberlauf(), [])
    p.pruefe("1280 px: kein Balken verdeckt einen anderen", await tab.js(VERDECKT), [])
    p.pruefe("1280 px: jeder Text sichtbar oder im title", await tab.js(TEXTE), [])
    await tab.bild("personen_1280_hell")

    # --- Geräte ---
    await tab.fenster(1440, 1000)
    await ansicht(tab, "resources")
    p.pruefe("Geräte: Kran mit dem Termin aus seinem Postfach und der Vermietung", await tab.js(BALKEN_JE_ZEILE + "('Kran Böcker AHK 36')"),
             [["Am Wasserturm 4", "fest !"], ["Vermietung · Lia", "kran"], ["Am Wasserturm 4", "fest"], ["Outlook · Müller", "termin"]])  # erst die Einsätze
    p.pruefe("Geräte: kein Balken verdeckt einen anderen", await tab.js(VERDECKT), [])
    p.pruefe("Geräte: jeder Text sichtbar oder im title", await tab.js(TEXTE), [])
    await tab.bild("geraete_1440_hell")

    # --- dunkel ---
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','dark')}catch(e){}")
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_ruhe()
    await ansicht(tab, "employees")
    await tab.bild("personen_1440_dunkel")
    await tab.fenster(1280, 900)
    await tab.warte_auf_ruhe()
    await tab.bild("personen_1280_dunkel")
    p.pruefe("dunkel: kein Balken verdeckt einen anderen", await tab.js(VERDECKT), [])

    # --- als Bea (Büro – Auftrag): ohne Art, ihr privater Termin mit Titel ---
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.anmelden(seed["bea"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_ruhe()
    await ansicht(tab, "employees")
    p.pruefe("Büro – Auftrag: Abwesenheit ohne Art", [await tab.js(BALKEN_JE_ZEILE + "('Tom Monteur')"), await tab.js(BALKEN_JE_ZEILE + "('Nele Neu')")],
             [[["Am Wasserturm 4", "fest"], ["abwesend", "abwesend"]], [["Garage Lindenweg 7", "vorlaeufig ·"], ["beantragt", "beantragt"]]])
    p.pruefe("Bea sieht ihren privaten Termin mit Titel", await tab.js(BALKEN_JE_ZEILE + "('Bea Bauer')"),
             [["10:00 Aufmaß", "termin"], ["08:00 Angebot vor Ort", "termin"], ["09:00 Zahnarzt", "termin"], ["14:00 Abnahme", "termin"]])
    await tab.bild("personen_buero_auftrag")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=f"{HEUTE} 10:00"))
