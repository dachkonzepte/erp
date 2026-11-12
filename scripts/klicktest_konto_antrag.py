"""Klicktest: der Stand des Arbeitszeitkontos beim Antrag auf Freizeitausgleich oder Unbezahlt (1.9.337, Lohn L2c-3, Punkt 4).

Testdaten wie klicktest_konto_monat.py (stehende Uhr Mi 03.02.2027; Ada Arbeit Stand bis 02.02. +15,00 h; Bo Bau ohne Startwert), dazu offene Anträge: Ada
Freizeitausgleich 08.–10.02. (drei Tage zu 7,50 h), Bo Unbezahlt 09.02.; die Monteurin Mia Monteurin (gewerblich, Startwert +20,00 h, je Arbeitstag 7,50 h
gebucht) mit einem offenen Antrag auf Freizeitausgleich am 12.02. Anna Admin, Fiona Finanz (Büro – Finanzen).

    Anna          „Prüfen“ und „Abwesenheiten“: an Adas Antrag „Stand vorläufig +15,00 h · danach -7,50 h“ mit „Plusstunden reichen nicht“, an Bos „Stand
                  vorläufig: Startwert folgt“; an Mias Antrag „Stand vorläufig +20,00 h · danach …“
    Fiona         „Abwesenheit beantragen“ für Ada, Freizeitausgleich 15.–16.02.: „Stand vorläufig +15,00 h · danach +0,00 h“, ohne Hinweis; Urlaub: keine Zeile
    Mia           „Meine Zeiten“ -> „Abwesenheit beantragen“ mit Freizeitausgleich: keine Zahl, keine Anfrage an /api/zeiten/konto-danach; ihr Antrag ohne Zahl
    Bilder        „Prüfen“ mit den Anträgen (Anna) und der Antrag der Monteurin bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_konto_antrag.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_konto_monat import befuellen as befuellen_konto  # noqa: E402

PRUEFEN_BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''"
MOBIL_BEREIT = "!document.getElementById('tage').classList.contains('laedt')&&document.getElementById('monatName').textContent!==''"
KONTO_ZEILEN = "[...document.querySelectorAll('{sel} .konto-danach')].map(s=>s.textContent)"


def befuellen(db, k):
    from datetime import date, datetime, timedelta
    from decimal import Decimal

    from app.absence_requests import create_request
    from app.models import AppUser, Employee, EmployeePayrollSettings, LohnStartwert, Order, TimeEntry

    seed = befuellen_konto(db, k)
    mia = Employee(employee_number="M-3", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", hourly_wage=Decimal("20"),
                   weekly_hours=Decimal("40"), active=True)
    db.add(mia); db.flush()
    db.add(EmployeePayrollSettings(employee_id=mia.id, export_umfang="alles", payroll_export_enabled=True, datev_personnel_number="00097", eintritt=date(2020, 1, 1)))
    db.add(LohnStartwert(employee_id=mia.id, stichtag=date(2026, 12, 31), saldo_stunden=Decimal("20")))
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    mia_konto = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort())
    db.add_all([anna, mia_konto])
    auftrag = db.query(Order).first()
    t = date(2027, 1, 4)
    while t <= date(2027, 2, 2):  # je Arbeitstag 7,50 h -- im Konto neutral, der Stand bleibt beim Startwert
        if t.weekday() < 5:
            db.add(TimeEntry(employee_id=mia.id, project_id=auftrag.project_id, order_id=auftrag.id, work_date=t, entry_type="site", hours=Decimal("7.5"),
                             break_minutes=0, status="booked", started_at=datetime(t.year, t.month, t.day, 7),
                             ended_at=datetime(t.year, t.month, t.day, 14, 30)))
        t += timedelta(days=1)
    db.commit()
    leute = {e.first_name: e for e in db.query(Employee).all()}
    create_request(db, employee_id=leute["Ada"].id, absence_category="freizeitausgleich", start_date=date(2027, 2, 8), end_date=date(2027, 2, 10))
    create_request(db, employee_id=leute["Bo"].id, absence_category="unbezahlt", start_date=date(2027, 2, 9), end_date=date(2027, 2, 9))
    create_request(db, employee_id=mia.id, absence_category="freizeitausgleich", start_date=date(2027, 2, 12), end_date=date(2027, 2, 12))
    return {**seed, "anna": k.cookies(anna), "mia": k.cookies(mia_konto)}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=m=>{console.error('confirm(): '+m);return false};")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["anna"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", "!!window.P")
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Anna: Prüfen geladen", await tab.oeffnen("/zeiten?n=a1", PRUEFEN_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anna, Prüfen: an jedem Antrag auf Freizeitausgleich oder Unbezahlt der Stand", await tab.js(KONTO_ZEILEN.replace("{sel}", "#antragListe")), [  # die jüngsten Anträge zuerst: Mia, Bo, Ada
        "Stand vorläufig +20,00 h · danach +12,50 h", "Stand vorläufig: Startwert folgt",
        "Stand vorläufig +15,00 h · danach -7,50 h Plusstunden reichen nicht"])
    p.pruefe("Anna, Abwesenheiten geladen", await tab.oeffnen("/zeiten?n=a2#abwesenheiten",
                                                             "!!window.A&&document.querySelectorAll('#abwListe .zeile').length>0"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anna, Abwesenheiten: dieselben Zeilen", await tab.js(KONTO_ZEILEN.replace("{sel}", "#abwListe")), [  # die jüngsten Anträge zuerst: Mia, Bo, Ada
        "Stand vorläufig +20,00 h · danach +12,50 h", "Stand vorläufig: Startwert folgt",
        "Stand vorläufig +15,00 h · danach -7,50 h Plusstunden reichen nicht"])

    await tab.anmelden(seed["fiona"])
    p.pruefe("Fiona, Abwesenheiten geladen", await tab.oeffnen("/zeiten?n=f1#abwesenheiten", "!!window.A&&!document.getElementById('abwNeu').hidden"), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('abwNeu').click()")
    await tab.js("(()=>{const s=document.getElementById('adMitarbeiter');s.value=[...s.options].find(o=>o.textContent.includes('Ada')).value;"
                 "s.dispatchEvent(new Event('change'));const k=document.getElementById('adKategorie');k.value='freizeitausgleich';k.dispatchEvent(new Event('change'));"
                 "const v=document.getElementById('adVon');v.value='2027-02-15';v.dispatchEvent(new Event('change'));"
                 "const b=document.getElementById('adBis');b.value='2027-02-16';b.dispatchEvent(new Event('change'))})()")
    p.pruefe("Fiona, beim Stellen: Stand und danach", await tab.warten(
        "!document.getElementById('adKonto').hidden&&document.getElementById('adKonto').textContent==='Stand vorläufig +15,00 h · danach +0,00 h'", 10), True)
    await tab.js("(()=>{const k=document.getElementById('adKategorie');k.value='urlaub';k.dispatchEvent(new Event('change'))})()")
    p.pruefe("Fiona, Urlaub: keine Zeile zum Konto", await tab.warten("document.getElementById('adKonto').hidden", 10), True)

    await tab.anmelden(seed["mia"])
    p.pruefe("Mia: Meine Zeiten geladen", await tab.oeffnen("/mobil/zeiten?n=m1", MOBIL_BEREIT), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('antragKnopf').click()")
    await tab.js("(()=>{const k=document.getElementById('adKategorie');k.value='freizeitausgleich';k.dispatchEvent(new Event('change'));"
                 "const b=document.getElementById('adBis');b.value='2027-02-05';b.dispatchEvent(new Event('change'))})()")
    await tab.warte_auf_ruhe()
    p.pruefe("Mia: keine Zahl im Dialog, keine Anfrage ans Konto", await tab.js(
        "[document.getElementById('abwDialog').open,document.getElementById('abwDialog').textContent.includes('Stand vorläufig'),"
        "performance.getEntriesByType('resource').some(e=>e.name.includes('konto-danach')),document.getElementById('adKonto')===null]"), [True, False, False, True])
    p.pruefe("Mia: ihr Antrag ohne Zahl", await tab.js(
        "[document.getElementById('adAntraege').textContent.includes('Freizeitausgleich'),document.body.textContent.includes('Stand vorläufig')]"), [True, False])
    await tab.js("document.getElementById('abwDialog').close()")

    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            await tab.anmelden(seed["anna"])
            p.pruefe(f"Bild Anna {breite} {name}: geladen", await tab.oeffnen(f"/zeiten?n=b{breite}{name}", PRUEFEN_BEREIT), True)
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Bild Anna {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('antragKarte').scrollIntoView({block:'end'});window.scrollBy(0,16)")
            await tab.bild(f"zeiten_pruefen_antrag_stand_{breite}_{name}")
            await tab.anmelden(seed["mia"])
            p.pruefe(f"Bild Mia {breite} {name}: geladen", await tab.oeffnen(f"/mobil/zeiten?n=m{breite}{name}", MOBIL_BEREIT), True)
            await tab.warte_auf_ruhe()
            await tab.js("document.getElementById('antragKnopf').click()")
            await tab.js("(()=>{const k=document.getElementById('adKategorie');k.value='freizeitausgleich';k.dispatchEvent(new Event('change'))})()")
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Bild Mia {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.bild(f"mobil_zeiten_antrag_ohne_zahl_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-02-03 10:00"))
