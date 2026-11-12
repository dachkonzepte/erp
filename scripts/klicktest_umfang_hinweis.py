"""Klicktest: „DATEV bekommt keine Arbeit – Umfang prüfen“ (1.9.326, Lohn L2c-1, Nachrunde, Punkt C).

Stehende Uhr Mi 25.11.2026 10:00. Ada Abwesend (gewerblich, Export „nur Abwesenheiten“), Bo Nichts (gewerblich, „nichts“), Kai Kontor (kaufmännisch,
„nur Abwesenheiten“), Cem Alles (gewerblich, „alles“, Personalnummer 00094); Anna (Admin).

    Prüfen          „Vor dem Abschluss“ nennt „Ada Abwesend: DATEV bekommt keine Arbeit – Umfang prüfen“ und „Bo Nichts: …“ -- nicht Kai, nicht Cem
    Monat & Lohn    „1 Prüfen“ nennt dieselben zwei Zeilen mit dem Weg „Lohnstammdaten“ (/settings#time-rules); „Fehlt“ nennt den Umfang nicht
    Bilder          beide Ansichten bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    überall         keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_umfang_hinweis.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''"
TEXTE = ["Ada Abwesend: DATEV bekommt keine Arbeit – Umfang prüfen", "Bo Nichts: DATEV bekommt keine Arbeit – Umfang prüfen"]


def befuellen(db, k):
    from decimal import Decimal

    from app.models import AppUser, Employee, EmployeePayrollSettings

    for nr, vor, nach, gruppe, umfang, pnr in (("M-1", "Ada", "Abwesend", "gewerblich", "abwesenheiten", None), ("M-2", "Bo", "Nichts", "gewerblich", "nichts", None),
                                               ("K-1", "Kai", "Kontor", "kaufmaennisch", "abwesenheiten", None),
                                               ("M-3", "Cem", "Alles", "gewerblich", "alles", "00094")):
        e = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group=gruppe, hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True)
        db.add(e)
        db.flush()
        db.add(EmployeePayrollSettings(employee_id=e.id, export_umfang=umfang, payroll_export_enabled=umfang != "nichts", datev_personnel_number=pnr))
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    db.add(anna)
    db.commit()
    return {"anna": k.cookies(anna), "uhr_ms": k.uhr_ms()}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["anna"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Prüfen geladen", await tab.oeffnen("/zeiten?n=1", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("„Vor dem Abschluss“: die zwei gewerblichen Personen, nicht Kai und Cem", await tab.js(
        "[...document.querySelectorAll('#abschlussListe li[data-art=umfang]')].map(li=>li.textContent.trim())"), TEXTE)
    p.pruefe("Monat & Lohn geladen", await tab.oeffnen("/zeiten?n=2#monat", "!!document.getElementById('lohnPruefen')&&document.getElementById('lohnPruefen').children.length>0"),
             True)
    await tab.warte_auf_ruhe()
    p.pruefe("„1 Prüfen“: dieselben Zeilen mit dem Weg zu den Lohnstammdaten", await tab.js(
        "[...document.querySelectorAll('#lohnPruefen li')].filter(li=>li.textContent.includes('Umfang prüfen'))"
        ".map(li=>[li.querySelector('.text').textContent,li.querySelector('a').textContent,li.querySelector('a').getAttribute('href')])"),
        [[t, "Lohnstammdaten", "/settings#time-rules"] for t in TEXTE])
    p.pruefe("„Fehlt“ nennt den Umfang nicht", await tab.js("document.getElementById('lohnDatevFehlt').textContent.includes('Umfang')"), False)
    n = 2
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            for ansicht, hash_, ziel in (("pruefen", "", "abschlussListe"), ("monat", "#monat", "lohnPruefen")):
                n += 1
                bereit = BEREIT if not hash_ else "!!document.getElementById('lohnPruefen')&&document.getElementById('lohnPruefen').children.length>0"
                p.pruefe(f"Bild {ansicht} {breite} {name}: geladen", await tab.oeffnen(f"/zeiten?n={n}{hash_}", bereit), True)
                await tab.warte_auf_ruhe()
                if mobil:
                    p.pruefe(f"Bild {ansicht} 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
                await tab.js(f"document.getElementById('{ziel}').scrollIntoView({{block:'center'}})")
                await tab.bild(f"zeiten_{ansicht}_umfang_hinweis_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-25 10:00"))
