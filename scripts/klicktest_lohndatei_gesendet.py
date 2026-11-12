"""Klicktest: „An das Steuerbüro gesendet“ an der abgelegten Lohndatei (1.9.328, Lohn L2c-2, Punkt 1).

Stehende Uhr Di 05.01.2027 10:00 (gespeicherte Zeitstempel laufen mit der echten Zeit, siehe cdp_klicktest.py), „Abgeschlossen bis“ 31.12.2026, Berater- und Mandantennummer erfunden. Ada Arbeit (gewerblich, Personalnummer 00094
erfunden); für Dezember 2026 zwei abgelegte Lohndateien (die zweite „zum Nachsehen“). Fiona Finanz (Büro – Finanzen), Anna (Admin).

    Fiona         „Monat & Lohn“, Dezember: an beiden Dateien „An das Steuerbüro gesendet“, kein „Zurücknehmen“; Klick an der älteren -- danach trägt sie
                  „An das Steuerbüro gesendet <Zeitpunkt> · Fiona Finanz“, kein Knopf mehr an einer Datei des Monats
    Anna          sieht „Zurücknehmen“ nur an der gesendeten; die Rückfrage steht auf der Seite („Vermerk „gesendet“ zurücknehmen?“ mit „Abbrechen“ und
                  „Zurücknehmen“), „Abbrechen“ lässt alles stehen; zurückgenommen -- kein Vermerk, beide Knöpfe wieder da
    Fiona         vermerkt die jüngere als gesendet
    Bilder        die Liste mit „gesendet“ bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_lohndatei_gesendet.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

PRUEFEN_BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''"
GELADEN = "!!window.M&&document.getElementById('lohnMonat').textContent!==''"
DEZEMBER = "!!window.M&&M.monat==='2026-12'&&document.querySelectorAll('#lohnDateien li').length===2"
KNOEPFE = "[...document.querySelectorAll('#lohnDateien li')].map(li=>[...li.querySelectorAll('button')].map(b=>b.textContent))"
VERMERKE = ("[...document.querySelectorAll('#lohnDateien li')].map(li=>{const v=li.querySelector('.lohndatei-vermerk');"
            r"return v?v.textContent.replace(/\d\d\.\d\d\.\d{4} \d\d:\d\d/,'<Zeitpunkt>'):''})")
GESENDET = "An das Steuerbüro gesendet <Zeitpunkt> · Fiona Finanz"


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Employee, EmployeePayrollSettings, TimeTrackingSettings
    from app.time_backoffice import lohndatei_erzeugen

    s = db.get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = "1234567", "12345", date(2026, 12, 31)
    ada = Employee(employee_number="M-1", first_name="Ada", last_name="Arbeit", employee_group="gewerblich", hourly_wage=Decimal("20"),
                   weekly_hours=Decimal("40"), active=True)
    db.add(ada)
    db.flush()
    db.add(EmployeePayrollSettings(employee_id=ada.id, export_umfang="alles", payroll_export_enabled=True, datev_personnel_number="00094"))
    fiona = AppUser(username="fiona", display_name="Fiona Finanz", role="buero_finanzen", password_hash=k.passwort())
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    db.add_all([fiona, anna])
    db.commit()
    for _ in range(2):
        lohndatei_erzeugen(db, date(2026, 12, 1), user_id=fiona.id, user_name="Fiona Finanz")
    return {"fiona": k.cookies(fiona), "anna": k.cookies(anna), "uhr_ms": k.uhr_ms()}


async def dezember(tab, p, name):
    """„Monat & Lohn“ öffnet den ersten offenen Monat (Januar) -- einen Monat zurück."""
    p.pruefe(f"{name}: Monat & Lohn geladen", await tab.oeffnen(f"/zeiten?n={name}#monat", GELADEN), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('lohnZurueck').click()")
    p.pruefe(f"{name}: Dezember mit zwei Dateien", await tab.warten(DEZEMBER, 15), True)
    await tab.warte_auf_ruhe()


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=m=>{console.error('confirm(): '+m);return false};")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["fiona"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", PRUEFEN_BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await dezember(tab, p, "fiona1")
    p.pruefe("Fiona: an beiden Dateien der Knopf, kein „Zurücknehmen“", await tab.js(KNOEPFE),
             [["An das Steuerbüro gesendet"], ["An das Steuerbüro gesendet"]])
    p.pruefe("Fiona: noch kein Vermerk", await tab.js(VERMERKE), ["", ""])
    # die ältere steht unten (neueste zuerst)
    p.pruefe("Fiona: Klick an der älteren, neu geladen", await tab.warte_auf_neu_geladene_liste(
        "document.querySelectorAll('#lohnDateien li')[1].querySelector('button').click()", "#lohnDateien li"), True)
    p.pruefe("Fiona: die ältere trägt den Vermerk mit Zeitpunkt und Konto", await tab.js(VERMERKE),
             ["", GESENDET])
    p.pruefe("Fiona: kein Knopf mehr im Monat (je Monat eine, zurücknehmen nur der Admin)", await tab.js(KNOEPFE), [[], []])
    p.pruefe("Meldung", await tab.js("document.getElementById('ergebnis').textContent"), "Als an das Steuerbüro gesendet vermerkt.")

    await tab.anmelden(seed["anna"])
    await dezember(tab, p, "anna")
    p.pruefe("Anna: „Zurücknehmen“ nur an der gesendeten", await tab.js(KNOEPFE), [[], ["Zurücknehmen"]])
    await tab.js("document.querySelectorAll('#lohnDateien li')[1].querySelector('button').click()")
    p.pruefe("Anna: die Rückfrage auf der Seite", await tab.js(
        "[document.querySelectorAll('#lohnDateien li')[1].querySelector('.rueckfrage').textContent,"
        "[...document.querySelectorAll('#lohnDateien li')[1].querySelectorAll('button')].map(b=>b.textContent)]"),
        ["Vermerk „gesendet“ zurücknehmen?", ["Abbrechen", "Zurücknehmen"]])
    await tab.js("document.querySelector('#lohnDateien [data-aktion=lohndatei-nein]').click()")
    p.pruefe("Anna: „Abbrechen“ lässt den Vermerk stehen", [await tab.js(KNOEPFE), (await tab.js(VERMERKE))[1]], [[[], ["Zurücknehmen"]], GESENDET])
    await tab.js("document.querySelectorAll('#lohnDateien li')[1].querySelector('button').click()")
    p.pruefe("Anna: zurückgenommen, neu geladen", await tab.warte_auf_neu_geladene_liste(
        "document.querySelector('#lohnDateien [data-aktion=lohndatei-zuruecknehmen]').click()", "#lohnDateien li"), True)
    p.pruefe("Anna: kein Vermerk mehr", await tab.js(VERMERKE), ["", ""])
    p.pruefe("Anna: beide Knöpfe wieder da", await tab.js(KNOEPFE), [["An das Steuerbüro gesendet"], ["An das Steuerbüro gesendet"]])

    await tab.anmelden(seed["fiona"])
    await dezember(tab, p, "fiona2")
    p.pruefe("Fiona: die jüngere vermerkt", await tab.warte_auf_neu_geladene_liste(
        "document.querySelectorAll('#lohnDateien li')[0].querySelector('button').click()", "#lohnDateien li"), True)
    p.pruefe("Fiona: Vermerk an der jüngeren", await tab.js(VERMERKE), [GESENDET, ""])

    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            await dezember(tab, p, f"bild_{breite}_{name}")
            if mobil:
                p.pruefe(f"Bild {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('lohnDateien').scrollIntoView({block:'center'})")
            await tab.bild(f"zeiten_monat_lohndatei_gesendet_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-01-05 10:00"))
