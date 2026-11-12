"""Klicktest: „Nach dem Versand geändert“ in „Monat & Lohn“ (1.9.329, Lohn L2c-2, Punkt 2).

Stehende Uhr Di 05.01.2027 10:00 (gespeicherte Zeitstempel laufen mit der echten Zeit, siehe cdp_klicktest.py), „Abgeschlossen bis“ 31.12.2026, Berater-
und Mandantennummer erfunden. Ada Arbeit (Urlaub 14.–15.12.), Bo Bau, Cem Code (Urlaub 16.12.) -- gewerblich, Personalnummern 00094–00096 erfunden. Die
Lohndatei Dezember ist erzeugt und als gesendet vermerkt (Fiona Finanz); danach ändert Anna Admin: Adas Urlaub endet am 14.12., Bo ist am 09.12. krank, Cem
bekommt die Personalnummer 00097 und sein Urlaub wird ein halber Tag (nur die Stunden ändern sich). Fiona Finanz (Büro – Finanzen).

    Dezember      die Karte nennt den Bezug („Bezug: Datei vom …, gesendet … · Fiona Finanz“), „4 Änderungen nach dem Versand“ und je Zeile Person mit
                  Personalnummer, Tag, „In der Datei“, „Heute“ und den Grund aus der Änderungshistorie („Abwesenheit geändert · … · Anna Admin“ …)
    November      ohne gesendete Datei „Noch nichts versendet – …“, keine Tabelle
    Bilder        die Karte bei 1440 und 412 px, hell und dunkel (412: nichts läuft über, die Tabelle rollt in ihrem Rahmen)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_nach_dem_versand.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

PRUEFEN_BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''"
GELADEN = "!!window.M&&document.getElementById('lohnMonat').textContent!==''"
ZEITPUNKT = r"/\d\d\.\d\d\.\d{4} \d\d:\d\d/g"
ZEILEN = ("[...document.querySelectorAll('#nvZeilen tr')].map(tr=>[...tr.children].map(td=>td.innerText.replace(" + ZEITPUNKT + ",'<Zeitpunkt>')"
          ".replace(/\\n/g,' | ')))")
KEIN_VERSAND = "Noch nichts versendet – vermerke an der Datei „An das Steuerbüro gesendet“."


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal
    from types import SimpleNamespace

    from app.audit import reset_audit_context, set_audit_context
    from app.lohndatei import versendet_setzen
    from app.models import AppUser, Employee, EmployeeAbsence, EmployeePayrollSettings, PersonalnummerVergabe, TimeTrackingSettings
    from app.time_backoffice import lohndatei_erzeugen

    s = db.get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = "1234567", "12345", date(2026, 12, 31)
    leute = {}
    for nr, vor, nach, pnr in (("M-1", "Ada", "Arbeit", "00094"), ("M-2", "Bo", "Bau", "00095"), ("M-3", "Cem", "Code", "00096")):
        e = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"),
                     active=True)
        db.add(e)
        db.flush()
        db.add(EmployeePayrollSettings(employee_id=e.id, export_umfang="alles", payroll_export_enabled=True, datev_personnel_number=pnr))
        leute[vor] = e
    urlaub = EmployeeAbsence(employee_id=leute["Ada"].id, start_date=date(2026, 12, 14), end_date=date(2026, 12, 15), absence_type="Urlaub",
                             absence_category="urlaub")
    cem_urlaub = EmployeeAbsence(employee_id=leute["Cem"].id, start_date=date(2026, 12, 16), end_date=date(2026, 12, 16), absence_type="Urlaub",
                                 absence_category="urlaub")
    db.add_all([urlaub, cem_urlaub])
    fiona = AppUser(username="fiona", display_name="Fiona Finanz", role="buero_finanzen", password_hash=k.passwort())
    db.add(fiona)
    db.commit()
    row = lohndatei_erzeugen(db, date(2026, 12, 1), user_id=fiona.id, user_name="Fiona Finanz")
    versendet_setzen(db, row.id, user_id=fiona.id, user_name="Fiona Finanz")
    # nach dem Versand ändert Anna Admin (im abgeschlossenen Monat darf das nur der Admin) -- die Änderungshistorie hält es fest
    token = set_audit_context(SimpleNamespace(id=1, display_name="Anna Admin"), None)
    try:
        db.refresh(urlaub)  # wie über die Oberfläche: frisch geladen -- sonst kennt die Änderungshistorie den alten Wert nicht (nach dem Commit abgelaufen)
        urlaub.end_date = date(2026, 12, 14)
        db.refresh(cem_urlaub)
        cem_urlaub.halber_tag = True  # nur die Stunden ändern sich
        db.add(EmployeeAbsence(employee_id=leute["Bo"].id, start_date=date(2026, 12, 9), end_date=date(2026, 12, 9), absence_type="Krankheit",
                               absence_category="krankheit"))
        cem = db.query(EmployeePayrollSettings).filter_by(employee_id=leute["Cem"].id).one()
        cem.datev_personnel_number = "00097"
        db.add(PersonalnummerVergabe(nummer="00096", employee_id=leute["Cem"].id))
        db.commit()
    finally:
        reset_audit_context(token)
    return {"fiona": k.cookies(fiona), "uhr_ms": k.uhr_ms()}


async def monat_zurueck(tab, p, name, monat, n=1):
    for _ in range(n):
        await tab.js("document.getElementById('lohnZurueck').click()")
    p.pruefe(f"{name}: {monat} geladen", await tab.warten(f"!!window.M&&M.monat==='{monat}'&&document.getElementById('nvText').textContent!==''", 15), True)
    await tab.warte_auf_ruhe()


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
    await dezember(tab, p, "dez")
    p.pruefe("Bezug: die gesendete Datei", await tab.js(f"document.getElementById('nvBezug').textContent.replace({ZEITPUNKT},'<Zeitpunkt>')"),
             "Bezug: Datei vom <Zeitpunkt>, gesendet <Zeitpunkt> · Fiona Finanz")
    p.pruefe("Stand: vier Änderungen", await tab.js("document.getElementById('nvText').textContent"), "4 Änderungen nach dem Versand")
    p.pruefe("Tabelle sichtbar, nichts „für viele zugleich“", await tab.js("[document.getElementById('nvTabelle').hidden,document.getElementById('nvAllgemeinKopf').hidden]"),
             [False, True])
    zeilen = await tab.js(ZEILEN)
    p.pruefe("je Zeile Person, Tag, In der Datei, Heute", [z[:4] for z in zeilen], [
        ["Ada Arbeit | 00094", "Di 15.12.", zeilen[0][2], "–"],
        ["Bo Bau | 00095", "Mi 09.12.", "–", zeilen[1][3]],
        ["Cem Code | 00097", "Personalnummer", "Personalnummer 00096", "Personalnummer 00097"],
        ["Cem Code | 00097", "Mi 16.12.", "U/8000 7,50 h", "U/8000 3,75 h"]])
    p.pruefe("Ada: in der Datei der Urlaub am 15.12.", zeilen[0][2].startswith("U"), True)
    p.pruefe("Bo: heute krank statt Arbeit", zeilen[1][3].startswith("K"), True)
    p.pruefe("der Grund aus der Änderungshistorie", [z[4] for z in zeilen], [
        "Abwesenheit geändert · <Zeitpunkt> · Anna Admin", "Abwesenheit angelegt · <Zeitpunkt> · Anna Admin", "Lohnstammdaten geändert · <Zeitpunkt> · Anna Admin",
        "Abwesenheit geändert · <Zeitpunkt> · Anna Admin | Lohnstammdaten geändert · <Zeitpunkt> · Anna Admin"])
    await monat_zurueck(tab, p, "nov", "2026-11")
    p.pruefe("November: noch nichts versendet, keine Tabelle", await tab.js(
        "[document.getElementById('nvText').textContent,document.getElementById('nvTabelle').hidden,document.getElementById('nvBezug').textContent]"),
        [KEIN_VERSAND, True, ""])
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            await dezember(tab, p, f"bild_{breite}_{name}")
            if mobil:
                p.pruefe(f"Bild {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('nachVersand').scrollIntoView({block:'start'});window.scrollBy(0,-80)")
            await tab.bild(f"zeiten_monat_nach_dem_versand_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-01-05 10:00"))
