"""Klicktest: das Arbeitszeitkonto in „Monat & Lohn“ (1.9.334, Lohn L2c-3, Punkt 1).

Stehende Uhr Mi 03.02.2027 10:00. Gewerblich: Ada Arbeit (Startwert +12,50 h; im Januar je Arbeitstag 8,00 h gebucht, Urlaub am 13.01., Freizeitausgleich
am 20.01.), Bo Bau (am Stichtag beschäftigt, ohne Startwert; 7,50 h je Arbeitstag bis auf den 25.01.); kaufmännisch: Kai Kontor (kein Konto). Sollzeit im
Januar 7,50 h (KW 49–17), Neujahr ein Feiertag. Fiona Finanz (Büro – Finanzen).

    Januar 2027   Karte „Arbeitszeitkonto“ unter „Stunden je Mitarbeiter“ mit „vorläufig – maßgeblich ist die Lohnabrechnung“; je gewerblicher Person Soll im
                  Monat, Saldo des Monats, Stand am Monatsende -- Bo mit „Startwert folgt“; Kai nicht; die Spalten „Konto · 0,25 je Tag“
    Dezember 2026 keine Karte und keine Anfrage ans Konto (vor dem Kontobeginn)
    Februar 2027  „Stand bis 02.02.2027“, „gezählt bis gestern“
    Bilder        die Karte bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_konto_monat.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

KONTO_BEREIT = "!!window.M&&M.monat==='{m}'&&!!window.KONTO&&document.getElementById('kontoZeilen').children.length>0"
ZEILEN = "[...document.querySelectorAll('#kontoZeilen tr')].map(tr=>[...tr.children].slice(0,4).map(td=>td.textContent.trim()))"


def befuellen(db, k):
    from datetime import date, datetime, timedelta
    from decimal import Decimal

    from app.absence_requests import eintragen
    from app.models import (AppUser, Customer, Employee, EmployeePayrollSettings, LohnStartwert, Order, Project, Property, Quote, TimeEntry)
    from app.project_pipeline_columns import default_pipeline_column_id

    kunde = Customer(name="Konto", last_name="Konto", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Konto", street="-", postal_code="00000", city="-")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KONTO", name="Konto", customer_id=kunde.id, property_id=objekt.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(project_id=projekt.id, quote_number="A-KONTO", title="Konto")
    db.add(angebot); db.flush()
    auftrag = Order(order_number="AUF-KONTO", project_id=projekt.id, source_quote_id=angebot.id, quote_number_snapshot="A-KONTO", title="Konto",
                    customer_name="Konto", status="laeuft")
    db.add(auftrag); db.flush()
    leute = {}
    for nr, vor, nach, gruppe, pnr in (("M-1", "Ada", "Arbeit", "gewerblich", "00094"), ("M-2", "Bo", "Bau", "gewerblich", "00095"),
                                       ("K-1", "Kai", "Kontor", "kaufmaennisch", "00096")):
        e = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group=gruppe, hourly_wage=Decimal("20"), weekly_hours=Decimal("40"),
                     active=True)
        db.add(e); db.flush()
        db.add(EmployeePayrollSettings(employee_id=e.id, export_umfang="alles", payroll_export_enabled=True, datev_personnel_number=pnr,
                                       eintritt=date(2020, 1, 1)))
        leute[vor] = e
    db.add(LohnStartwert(employee_id=leute["Ada"].id, stichtag=date(2026, 12, 31), resturlaub_tage=Decimal("3"), saldo_stunden=Decimal("12.5")))
    fiona = AppUser(username="fiona", display_name="Fiona Finanz", role="buero_finanzen", password_hash=k.passwort())
    db.add(fiona)
    db.commit()
    frei = {"Ada": {date(2027, 1, 13), date(2027, 1, 20)}, "Bo": {date(2027, 1, 25)}}
    stunden = {"Ada": Decimal("8"), "Bo": Decimal("7.5")}
    for vor in ("Ada", "Bo"):
        t = date(2027, 1, 4)
        while t <= date(2027, 2, 2):
            if t.weekday() < 5 and t not in frei[vor]:
                h = stunden[vor]
                db.add(TimeEntry(employee_id=leute[vor].id, project_id=projekt.id, order_id=auftrag.id, work_date=t, entry_type="site", hours=h, break_minutes=0,
                                 status="booked", started_at=datetime(t.year, t.month, t.day, 7), ended_at=datetime(t.year, t.month, t.day, 7) + timedelta(hours=float(h))))
            t += timedelta(days=1)
    db.commit()
    for tag, kat, art in ((date(2027, 1, 13), "urlaub", "Urlaub"), (date(2027, 1, 20), "freizeitausgleich", "Freizeitausgleich")):
        eintragen(db, gleich_genehmigt=True, employee_id=leute["Ada"].id, absence_category=kat, absence_type=art, start_date=tag, end_date=tag)
    return {"fiona": k.cookies(fiona), "uhr_ms": k.uhr_ms()}


async def monat(tab, p, name, m):
    p.pruefe(f"{name}: Monat & Lohn {m} geladen", await tab.oeffnen(f"/zeiten?lohnmonat={m}&n={name}#monat",
                                                                   f"!!window.M&&M.monat==='{m}'&&document.getElementById('lohnMonat').textContent!==''"), True)
    await tab.warte_auf_ruhe()
    # das Konto lädt nach dem Monat und „Nach dem Versand“ -- erst danach ist die Karte fertig (vor Januar 2027 bleibt sie leer)
    p.pruefe(f"{name}: Konto gezeichnet", await tab.warten(f"'{m}'<'2027-01'||(!!window.KONTO&&KONTO.monat==='{m}')", 10), True)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=m=>{console.error('confirm(): '+m);return false};")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["fiona"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", "!!window.P")
    await tab.js("localStorage.setItem('erp_theme','light')")
    await monat(tab, p, "jan", "2027-01")
    p.pruefe("Januar: die Karte mit „vorläufig“", await tab.js(
        "[document.getElementById('kontoKarte').hidden,document.getElementById('kontoVorlaeufig').textContent,document.getElementById('kontoStandKopf').textContent,"
        "document.getElementById('kontoGezaehlt').textContent]"), [False, "vorläufig – maßgeblich ist die Lohnabrechnung", "Stand am Monatsende", ""])
    p.pruefe("Januar: die Spalten als Konto beschriftet", await tab.js(
        "[...document.querySelectorAll('#kontoKarte thead th')].slice(1,4).map(th=>th.querySelector('.konto-kopf-einheit').textContent)"),
        ["Konto · 0,25 je Tag", "Konto · 0,25 je Tag", "ab dem Startwert"])
    # Soll: 21 Arbeitstage (01.–29.01.) zu 7,50 h = 157,50. Ada: 18 Tage (04.–29.01. ohne 13. und 20.) zu 8,00 h = je +0,50 = +9,00; 13.01. Urlaub neutral;
    # 20.01. Freizeitausgleich −7,50; 01.01. Feiertag neutral -- Saldo +1,50, Stand +12,50 + 1,50 = +14,00. Bo: 19 Tage zu 7,50 neutral, 25.01. ohne Eintrag −7,50
    p.pruefe("Januar: Soll, Saldo und Stand je gewerblicher Person", await tab.js(ZEILEN), [
        ["Ada Arbeit", "157,50 h", "+1,50 h", "+14,00 h"], ["Bo Bau", "157,50 h", "-7,50 h", "Startwert folgt"]])
    await monat(tab, p, "dez", "2026-12")
    p.pruefe("Dezember 2026: keine Karte, keine Anfrage ans Konto, keine Meldung", await tab.js(
        "[document.getElementById('kontoKarte').hidden,performance.getEntriesByType('resource').some(e=>e.name.includes('/api/zeiten/arbeitszeitkonto')),"
        "document.getElementById('seitenStatus').textContent]"), [True, False, ""])
    await monat(tab, p, "feb", "2027-02")
    p.pruefe("Februar: bis gestern gezählt", await tab.js(
        "[document.getElementById('kontoStandKopf').textContent,document.getElementById('kontoGezaehlt').textContent]"),
        ["Stand bis 02.02.2027", "gezählt bis gestern, 02.02.2027"])
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            await monat(tab, p, f"bild_{breite}_{name}", "2027-01")
            if mobil:
                p.pruefe(f"Bild {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('kontoKarte').scrollIntoView({block:'end'});window.scrollBy(0,16)")
            await tab.bild(f"zeiten_monat_konto_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-02-03 10:00"))
