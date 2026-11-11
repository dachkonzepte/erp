"""Klicktest: der Hinweis Rückfahrt in „Zeiten → Prüfen“ (1.9.314, Lohn L2b, Punkt 2; Antwort 7 des Befunds L2).

Stehende Uhr Mi 25.11.2026 10:00 (Server und Browser). Mia (gewerblich): Mo 23.11. Baustelle 07:00–15:00, Fahrzeit 15:00–15:45 (Rückfahrt);
Di 24.11. Fahrzeit 06:30–07:00, Baustelle 07:00–15:00 (Hinfahrt, kein Hinweis). Anna (Admin), Bea (Büro – Auftrag).

    Admin            Karte „Fahrzeit nach Arbeitsende“ (zur Info) mit einer Zeile: „Mia Monteurin · Mo 23.11.“, „Fahrzeit 15:00–15:45 · 0,75 h · nach
                     Arbeitsende 15:00 · …“ und der Hinweis „Fahrzeit nach Arbeitsende – Rückfahrt? Feierabend ist auf der Baustelle.“; keine Zahl am
                     Reiter dafür; „Ändern“ öffnet den Dialog der Buchung (Von 15:00, Bis 15:45); nach dem Löschen der Fahrzeit ist die Karte weg
    Bilder           Prüfen mit dem Hinweis bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    Büro – Auftrag   dieselbe Zeile ohne „Ändern“
    überall          keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_rueckfahrt.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''"
ZEILEN = ("[...document.querySelectorAll('#rueckfahrtListe .zeile')].map(z=>[z.querySelector('.zeile-name').innerText,"
          "[...z.querySelectorAll('.zeile-unter')].map(u=>u.innerText),[...z.querySelectorAll('button')].map(b=>b.innerText)])")


def befuellen(db, k):
    from datetime import date, datetime, time
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, Order, Project, TimeEntry
    from app.project_pipeline_columns import default_pipeline_column_id

    mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    bea_ma = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="kaufmaennisch", active=True)
    db.add_all([mia, bea_ma])
    db.flush()
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", employee_id=bea_ma.id, password_hash=k.passwort())
    db.add_all([anna, bea])
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde)
    db.flush()
    projekt = Project(project_number="P-KT-RF1", name="Halle", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt)
    db.flush()
    auftrag = Order(order_number="AUF-2026-0314", project_id=projekt.id, source_quote_id=314, quote_number_snapshot="A-KT-314", title="Halle",
                    customer_name=kunde.name)
    db.add(auftrag)
    db.flush()

    def buchen(tag, art, von, bis, pause=0):
        beginn, ende = datetime.combine(tag, time(*von)), datetime.combine(tag, time(*bis))
        stunden = (Decimal((ende - beginn).seconds) / 3600 - Decimal(pause) / 60).quantize(Decimal("0.01"))
        db.add(TimeEntry(employee_id=mia.id, project_id=projekt.id, order_id=auftrag.id, work_date=tag, entry_type=art, hours=stunden, break_minutes=pause,
                         min_break_minutes=pause, status="booked", started_at=beginn, ended_at=ende))

    buchen(date(2026, 11, 23), "site", (7, 0), (15, 0), 30)
    buchen(date(2026, 11, 23), "travel", (15, 0), (15, 45))
    buchen(date(2026, 11, 24), "travel", (6, 30), (7, 0))
    buchen(date(2026, 11, 24), "site", (7, 0), (15, 0), 30)
    db.commit()
    return {"anna": k.cookies(anna), "bea": k.cookies(bea), "uhr_ms": k.uhr_ms()}


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
    p.pruefe("Anna: eine Fahrzeit nach Arbeitsende, mit Hinweis und „Ändern“", await tab.js(ZEILEN),
             [["Mia Monteurin · Mo 23.11.", ["Fahrzeit 15:00–15:45 · 0,75 h · nach Arbeitsende 15:00 · AUF-2026-0314 · Halle",
                                              "Fahrzeit nach Arbeitsende – Rückfahrt? Feierabend ist auf der Baustelle."], ["Ändern"]]])
    p.pruefe("Anna: Karte zur Info, keine Zahl am Reiter dafür", await tab.js(
        "[document.querySelector('#rueckfahrtKarte .eb').innerText.trim(),document.getElementById('rueckfahrtZahl').innerText,"
        "document.getElementById('zahlPruefen').hidden,document.getElementById('allesGut').hidden]"), ["ZUR INFO", "1 Fahrzeit", True, True])
    await tab.js("document.querySelector('#rueckfahrtListe [data-aktion=rueckfahrt-aendern]').click()")
    p.pruefe("Anna: „Ändern“ öffnet die Buchung", await tab.warten("document.getElementById('buchungDialog').open", 5), True)
    p.pruefe("Anna: im Dialog die Fahrzeit", await tab.js(
        "[document.getElementById('bdVon').value,document.getElementById('bdBis').value,document.getElementById('bdZeitart').value]"),
        ["15:00", "15:45", "travel"])
    await tab.js("document.getElementById('buchungDialog').close()")
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
            await tab.js("document.getElementById('rueckfahrtKarte').scrollIntoView({block:'start'})")
            await tab.bild(f"zeiten_pruefen_rueckfahrt_{breite}_{name}")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    rueck = await tab.js("P.rueckfahrten[0].id")
    p.pruefe("Anna: keine JS-Fehler", tab.fehler, [])

    # ---- Büro – Auftrag ------------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["bea"])
    p.pruefe("Bea: Prüfen geladen", await tab.oeffnen("/zeiten?n=7", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Bea: dieselbe Zeile ohne „Ändern“", await tab.js(ZEILEN),
             [["Mia Monteurin · Mo 23.11.", ["Fahrzeit 15:00–15:45 · 0,75 h · nach Arbeitsende 15:00 · AUF-2026-0314 · Halle",
                                              "Fahrzeit nach Arbeitsende – Rückfahrt? Feierabend ist auf der Baustelle."], []]])
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])

    # ---- gelöscht -> die Karte ist weg (der Betrieb korrigiert die Buchung oder lässt sie stehen; hier gelöscht) --------------------------
    await tab.anmelden(seed["anna"])
    p.pruefe("Anna: die Fahrzeit gelöscht", await tab.js(
        f"fetch('/api/time-entries/{rueck}',{{method:'DELETE'}}).then(r=>r.status)"), 200)
    p.pruefe("Anna: Prüfen neu geladen", await tab.oeffnen("/zeiten?n=9", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anna: die Karte ist weg", await tab.js("document.getElementById('rueckfahrtKarte').hidden"), True)
    p.pruefe("Anna: am Ende keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-25 10:00"))
