"""Klicktest: Hinweis beim Deaktivieren einer Person ohne Austritt (1.9.325, Lohn L2c-1, Nachrunde, Punkt B).

Testdaten: Ada, Ben, Eva, Gil Ohneaustritt (gewerblich, aktiv, Lohnstammdaten ohne Austritt) und Cem Mitaustritt (Austritt 31.03.2027); Fin (Büro – Finanzen).

    Deaktivieren    im Mitarbeiterformular „Inaktiv“ wählen und speichern: die Seite bleibt stehen, „Gespeichert.“, darunter der Hinweis „Austritt eintragen –
                    sonst läuft die Sollzeit weiter. Zu den Lohnstammdaten · Zur Liste“ (Link /settings?mitarbeiter=<id>#time-rules); gespeichert ist
    Bilder          je eine Person bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    Weg             Klick auf „Zu den Lohnstammdaten“: Einstellungen → Zeitregeln und DATEV, die Person steht trotz „Inaktive ausblenden“ in der Liste, ihre Zeile
                    hervorgehoben, der Cursor in ihrem Feld „Austritt“; Bild
    mit Austritt    Cem deaktiviert: kein Hinweis, zurück zur Liste wie bisher
    überall         keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_austritt_hinweis.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

HINWEIS = "Austritt eintragen – sonst läuft die Sollzeit weiter. Zu den Lohnstammdaten · Zur Liste"


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from sqlalchemy import select

    from app.models import (AppUser, Employee, EmployeeCompensationSettings, EmployeeCostAllocationSettings, EmployeeFunction, EmployeePayrollSettings,
                            EmployeeProfile)

    funktion = db.scalar(select(EmployeeFunction.id).where(EmployeeFunction.name == "Dachdecker Geselle"))
    ids = {}
    for nr, vor, nach, austritt in (("M-1", "Ada", "Ohneaustritt", None), ("M-2", "Ben", "Ohneaustritt", None), ("M-3", "Eva", "Ohneaustritt", None),
                                    ("M-4", "Gil", "Ohneaustritt", None), ("M-5", "Cem", "Mitaustritt", date(2027, 3, 31))):
        e = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"),
                     active=True, compensation=EmployeeCompensationSettings(compensation_type="hourly"))
        db.add(e)
        db.flush()
        db.add_all([EmployeeCostAllocationSettings(employee_id=e.id, allocation_type="labor_rate"), EmployeeProfile(employee_id=e.id, function_id=funktion),
                    EmployeePayrollSettings(employee_id=e.id, export_umfang="alles", austritt=austritt)])
        ids[vor.lower()] = e.id
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    db.add(fin)
    db.commit()
    return {"fin": k.cookies(fin), **ids}


async def deaktivieren(tab, mitarbeiter_id: int, vorname: str) -> None:
    await tab.oeffnen(f"/master-data/employees/{mitarbeiter_id}/edit?n={mitarbeiter_id}",
                      f"!!document.getElementById('activeSelect')&&document.getElementById('firstName').value==={json.dumps(vorname)}")
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('activeSelect').value='0';document.getElementById('saveBtn').click()")
    await tab.warte_auf_ruhe()


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["fin"])
    n = 0
    for (breite, mobil, thema, name), vorname in zip(((1440, False, "light", "hell"), (1440, False, "dark", "dunkel"), (412, True, "light", "hell"),
                                                     (412, True, "dark", "dunkel")), ("ada", "ben", "eva", "gil")):
        n += 1
        await tab.fenster(breite, 1000, mobil=mobil)
        await tab.oeffnen(f"/master-data?n={n}", "!!document.body")
        await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
        await deaktivieren(tab, seed[vorname], vorname.capitalize())
        p.pruefe(f"{vorname.capitalize()} {breite} {name}: Seite bleibt, „Gespeichert.“ und der Hinweis", await tab.warten(
            "!document.getElementById('austrittHinweis').hidden", 10), True)
        p.pruefe(f"{vorname.capitalize()} {breite} {name}: Text, Weg und Adresse", await tab.js(
            "[document.getElementById('msg').textContent,document.getElementById('austrittHinweis').innerText.trim(),"
            "document.getElementById('austrittWeg').getAttribute('href'),location.pathname]"),
            ["Gespeichert.", HINWEIS, f"/settings?mitarbeiter={seed[vorname]}#time-rules", f"/master-data/employees/{seed[vorname]}/edit"])
        p.pruefe(f"{vorname.capitalize()}: gespeichert -- inaktiv", await tab.js(f"fetch('/api/employees/{seed[vorname]}').then(r=>r.json()).then(d=>d.active)"),
                 False)
        if mobil:
            p.pruefe(f"412 {name}: nichts läuft über", await tab.ueberlauf(), [])
        await tab.bild(f"mitarbeiter_austritt_hinweis_{breite}_{name}")

    # ---- der Weg zu den Lohnstammdaten (echter Klick) ------------------------------------------------------------------------------------
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await deaktivieren(tab, seed["ada"], "Ada")  # schon inaktiv: kein Hinweis mehr -- zurück zur Liste
    p.pruefe("Ada schon inaktiv: kein Hinweis, zurück zur Liste", await tab.warten("location.pathname==='/master-data'", 10), True)
    await tab.oeffnen(f"/master-data/employees/{seed['ada']}/edit?n=20", "!!document.getElementById('activeSelect')&&document.getElementById('firstName').value==='Ada'")
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('activeSelect').value='1';document.getElementById('saveBtn').click()")
    await tab.warten("location.pathname==='/master-data'", 10)
    await deaktivieren(tab, seed["ada"], "Ada")
    p.pruefe("Ada wieder deaktiviert: Hinweis", await tab.warten("!document.getElementById('austrittHinweis').hidden", 10), True)
    await tab.js("document.getElementById('austrittWeg').click()")
    p.pruefe("Lohnstammdaten: geladen, Ada sichtbar trotz „Inaktive ausblenden“", await tab.warten(
        f"!!document.getElementById('paus-{seed['ada']}')&&document.getElementById('lohnInaktiveAusblenden').checked", 15), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Lohnstammdaten: Zeile hervorgehoben, Cursor im Feld „Austritt“, andere Inaktive ausgeblendet", await tab.js(
        f"[document.getElementById('paus-{seed['ada']}').closest('tr').classList.contains('lohn-ziel'),document.activeElement.id,"
        f"!!document.getElementById('paus-{seed['ben']}'),location.hash]"), [True, f"paus-{seed['ada']}", False, "#time-rules"])
    await tab.bild("lohnstammdaten_austritt_ziel_1440_hell")

    # ---- mit Austritt: kein Hinweis ---------------------------------------------------------------------------------------------------------
    await deaktivieren(tab, seed["cem"], "Cem")
    p.pruefe("Cem mit Austritt: kein Hinweis, zurück zur Liste", await tab.warten("location.pathname==='/master-data'", 10), True)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
