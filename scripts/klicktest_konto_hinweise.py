"""Klicktest: Hinweise zum Arbeitszeitkonto in „Zeiten → Prüfen“ (1.9.322, Lohn L2c-1, Punkt 2; Antworten B4, B5, B11 des Befunds L2c).

Stehende Uhr Fr 08.01.2027 10:00 (Server und Browser), abgeschlossen bis 31.12.2026 -- „Prüfen“ zählt Mo 04. bis Do 07.01. (Fr 01.01. Neujahr). Mi 06.01.
betriebsfrei („Brückentag“). Ada (gewerblich): gebucht Mo 04. und Do 07., nichts am Di 05. und Mi 06. Ben (gewerblich): Urlaub Mo 04.–Di 05. mit 3,00 h
am Mo 04., krank Mi 06. mit 2,00 h, gebucht Do 07. Cem (gewerblich): halber Urlaubstag Di 05. mit 4,00 h, sonst gebucht (auch am Mi 06.). Kai
(kaufmännisch): nichts. Anna (Admin), Fin (Büro – Finanzen), Bea (Büro – Auftrag).

    Admin            Karte „Tage ohne Eintrag“ (zur Info, „2 Tage“): „Ada Monteurin · 2 Tage“, „Di 05.01., Mi 06.01. · Sollzeit 15,00 h“, „Tag ohne Eintrag
                     – zählt im Konto als Minus“; Karte „Arbeit an Urlaubs- oder Kranktagen“ („2 Tage“): „Ben Monteur · 2 Tage“, „Urlaub Mo 04.01. · 3,00 h
                     gebucht; Krankheit Mi 06.01. · 2,00 h gebucht“, „Arbeit an einem Urlaubs- oder Kranktag – zählt im Konto als Plus“; kein Cem, kein Kai;
                     keine Zahl am Reiter, „Nichts zu prüfen“ verborgen
    Bilder           beide Karten bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    Büro – Finanzen  dieselben Zeilen
    Büro – Auftrag   beide Karten verborgen
    Löschen          Ben: die Buchung am Mo 04. gelöscht -> nur noch der Kranktag
    überall          keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_konto_hinweise.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''"


def zeilen(liste: str) -> str:
    return (f"[...document.querySelectorAll('#{liste} .zeile')].map(z=>[z.querySelector('.zeile-name').innerText,"
            "[...z.querySelectorAll('.zeile-unter')].map(u=>u.innerText)])")


OHNE = [["Ada Monteurin · 2 Tage", ["Di 05.01., Mi 06.01. · Sollzeit 15,00 h", "Tag ohne Eintrag – zählt im Konto als Minus"]]]
ABW = [["Ben Monteur · 2 Tage", ["Urlaub Mo 04.01. · 3,00 h gebucht; Krankheit Mi 06.01. · 2,00 h gebucht",
                                 "Arbeit an einem Urlaubs- oder Kranktag – zählt im Konto als Plus"]]]
KARTEN = ("[document.getElementById('ohneEintragKarte').hidden,document.getElementById('abwArbeitKarte').hidden,"
          "document.getElementById('ohneEintragZahl').innerText,document.getElementById('abwArbeitZahl').innerText,"
          "document.querySelector('#ohneEintragKarte .eb').innerText.trim(),document.getElementById('zahlPruefen').hidden,"
          "document.getElementById('allesGut').hidden]")


def befuellen(db, k):
    from datetime import date, datetime, time
    from decimal import Decimal

    from app.models import (AppUser, Customer, Employee, EmployeeAbsence, Order, PlanningHoliday, Project, TimeEntry, TimeTrackingSettings)
    from app.project_pipeline_columns import default_pipeline_column_id

    ada = Employee(employee_number="M-1", first_name="Ada", last_name="Monteurin", employee_group="gewerblich", active=True)
    ben = Employee(employee_number="M-2", first_name="Ben", last_name="Monteur", employee_group="gewerblich", active=True)
    cem = Employee(employee_number="M-3", first_name="Cem", last_name="Monteur", employee_group="gewerblich", active=True)
    kai = Employee(employee_number="K-1", first_name="Kai", last_name="Kaufmann", employee_group="kaufmaennisch", active=True)
    bea_ma = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="kaufmaennisch", active=True)
    db.add_all([ada, ben, cem, kai, bea_ma])
    db.flush()
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", employee_id=bea_ma.id, password_hash=k.passwort())
    db.add_all([anna, fin, bea])
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde)
    db.flush()
    projekt = Project(project_number="P-KT-AZK", name="Halle", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt)
    db.flush()
    auftrag = Order(order_number="AUF-2027-0322", project_id=projekt.id, source_quote_id=322, quote_number_snapshot="A-KT-322", title="Halle",
                    customer_name=kunde.name)
    db.add(auftrag)
    db.flush()
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 12, 31)
    db.add(PlanningHoliday(holiday_date=date(2027, 1, 6), name="Brückentag", active=True))

    def buchen(e, tag, von, bis, pause=0):
        beginn, ende = datetime.combine(tag, time(*von)), datetime.combine(tag, time(*bis))
        stunden = (Decimal((ende - beginn).seconds) / 3600 - Decimal(pause) / 60).quantize(Decimal("0.01"))
        db.add(TimeEntry(employee_id=e.id, project_id=projekt.id, order_id=auftrag.id, work_date=tag, entry_type="site", hours=stunden, break_minutes=pause,
                         min_break_minutes=pause, status="booked", started_at=beginn, ended_at=ende))

    def abwesend(e, von, bis, kategorie, art, halber_tag=False):
        db.add(EmployeeAbsence(employee_id=e.id, absence_type=art, absence_category=kategorie, start_date=von, end_date=bis, halber_tag=halber_tag))

    buchen(ada, date(2027, 1, 4), (7, 0), (15, 0), 30)
    buchen(ada, date(2027, 1, 7), (7, 0), (15, 0), 30)
    abwesend(ben, date(2027, 1, 4), date(2027, 1, 5), "urlaub", "Urlaub")
    buchen(ben, date(2027, 1, 4), (7, 0), (10, 0))
    abwesend(ben, date(2027, 1, 6), date(2027, 1, 6), "krankheit", "Krankheit")
    buchen(ben, date(2027, 1, 6), (12, 0), (14, 0))
    buchen(ben, date(2027, 1, 7), (7, 0), (15, 0), 30)
    buchen(cem, date(2027, 1, 4), (7, 0), (15, 0), 30)
    abwesend(cem, date(2027, 1, 5), date(2027, 1, 5), "urlaub", "Urlaub", halber_tag=True)
    buchen(cem, date(2027, 1, 5), (7, 0), (11, 0))
    buchen(cem, date(2027, 1, 6), (7, 0), (15, 0), 30)
    buchen(cem, date(2027, 1, 7), (7, 0), (15, 0), 30)
    db.commit()
    ben_buchung = db.query(TimeEntry).filter_by(employee_id=ben.id, work_date=date(2027, 1, 4)).one().id
    return {"anna": k.cookies(anna), "fin": k.cookies(fin), "bea": k.cookies(bea), "uhr_ms": k.uhr_ms(), "ben_buchung": ben_buchung}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.browser_uhr_fest(seed["uhr_ms"])

    # ---- Admin ---------------------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["anna"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Anna: Prüfen geladen", await tab.oeffnen("/zeiten?n=1", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anna: Tage ohne Eintrag je Person", await tab.js(zeilen("ohneEintragListe")), OHNE)
    p.pruefe("Anna: Arbeit an Urlaubs- oder Kranktagen je Person", await tab.js(zeilen("abwArbeitListe")), ABW)
    p.pruefe("Anna: beide Karten zur Info, keine Zahl am Reiter", await tab.js(KARTEN), [False, False, "2 Tage", "2 Tage", "ZUR INFO", True, True])
    n = 1
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            n += 1
            p.pruefe(f"Bild {breite} {name}: geladen", await tab.oeffnen(f"/zeiten?n={n}", BEREIT), True)
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Bild 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('ohneEintragKarte').scrollIntoView({block:'start'});window.scrollBy(0,-80)")  # unter der Kopfzeile
            await tab.bild(f"zeiten_pruefen_konto_hinweise_{breite}_{name}")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Anna: keine JS-Fehler", tab.fehler, [])

    # ---- Büro – Finanzen -----------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    p.pruefe("Fin: Prüfen geladen", await tab.oeffnen("/zeiten?n=7", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: dieselben Zeilen", [await tab.js(zeilen("ohneEintragListe")), await tab.js(zeilen("abwArbeitListe"))], [OHNE, ABW])
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    # ---- Büro – Auftrag ------------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["bea"])
    p.pruefe("Bea: Prüfen geladen", await tab.oeffnen("/zeiten?n=8", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Bea: beide Karten verborgen", await tab.js(
        "[document.getElementById('ohneEintragKarte').hidden,document.getElementById('abwArbeitKarte').hidden]"), [True, True])
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])

    # ---- Ben: die Buchung am Urlaubstag gelöscht -> nur noch der Kranktag ---------------------------------------------------------------
    await tab.anmelden(seed["anna"])
    p.pruefe("Anna: Bens Buchung am Urlaubstag gelöscht", await tab.js(
        f"fetch('/api/time-entries/{seed['ben_buchung']}',{{method:'DELETE'}}).then(r=>r.status)"), 200)
    p.pruefe("Anna: Prüfen neu geladen", await tab.oeffnen("/zeiten?n=9", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anna: nur noch der Kranktag", await tab.js(zeilen("abwArbeitListe")),
             [["Ben Monteur · 1 Tag", ["Krankheit Mi 06.01. · 2,00 h gebucht", "Arbeit an einem Urlaubs- oder Kranktag – zählt im Konto als Plus"]]])
    p.pruefe("Anna: am Ende keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-01-08 10:00"))
