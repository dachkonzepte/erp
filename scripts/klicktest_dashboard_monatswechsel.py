"""Klicktest: Dashboard-Kachel "Meine Stunden (Monat)" am Monatswechsel (1.8.10).

Die Kachel bildet den Monat seit 1.8.10 in Europe/Berlin (`berlinMonthRange()` aus
`_berlin_date.html`), unabhängig von der Zeitzone des Browsers. Vorher nahm sie über
toISOString() den letzten Tag des Vormonats mit und ließ den letzten Tag des Monats weg.

Das Skript hält die Uhr des Browsers fest (eigene Date-Klasse per
Page.addScriptToEvaluateOnNewDocument, vor jedem Laden) und stellt die Zeitzone per
Emulation.setTimezoneOverride um. Fünf Buchungen, jeder Monatsabschnitt mit eigener Summe:

    15.09. 1,50 | 30.09. 4,00 | 01.10. 2,00 | 31.10. 3,00 | 01.11. 7,00 Std.

    Berlin      01.10. 0:30 Uhr (in UTC noch 30.09.)  -> Oktober, 5,00 h
    UTC         derselbe Zeitpunkt                     -> Oktober, 5,00 h
    New York    derselbe Zeitpunkt (dort 30.09. abends) -> Oktober, 5,00 h (Berliner Monat zählt)
    Berlin      30.09. 23:30 Uhr                       -> September, 5,50 h
    Berlin      15.10. Mittag                          -> Oktober, 5,00 h

Die Daten liegen fest im Jahr 2026; weil die Browser-Uhr festgehalten wird, läuft das Skript an
jedem Tag gleich.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_dashboard_monatswechsel.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py. Dauer etwa 20 Sekunden.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

FAELLE = [  # (Browser-Zeitzone, Zeitpunkt UTC, erwarteter Zeitraum der Abfrage, Anzeige)
    ("Europe/Berlin", "2026-09-30T22:30:00Z", "2026-10-01..2026-10-31", "5,00 h"),
    ("UTC", "2026-09-30T22:30:00Z", "2026-10-01..2026-10-31", "5,00 h"),
    ("America/New_York", "2026-09-30T22:30:00Z", "2026-10-01..2026-10-31", "5,00 h"),
    ("Europe/Berlin", "2026-09-30T21:30:00Z", "2026-09-01..2026-09-30", "5,50 h"),
    ("Europe/Berlin", "2026-10-15T10:00:00Z", "2026-10-01..2026-10-31", "5,00 h"),
]
UHR = """(() => { const RealDate = Date, FIXED = %d;
  globalThis.Date = class extends RealDate { constructor(...a) { super(...(a.length ? a : [FIXED])); } static now() { return FIXED; } }; })();"""
KACHEL = ("[...document.querySelectorAll('.metric')].find(m => m.querySelector('small')?.textContent === 'Meine Stunden (Monat)')"
          "?.querySelector('b')?.textContent")
ZEITRAUM = ("(() => { const n = performance.getEntriesByType('resource').map(e => e.name).find(n => n.includes('/api/time-entries/summary'));"
            " if (!n) return null; const q = new URL(n).searchParams; return q.get('start_date') + '..' + q.get('end_date'); })()")


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, Order, Project, TimeEntry
    from app.project_pipeline_columns import default_pipeline_column_id

    kunde = Customer(name="Klicktest Kunde", last_name="Klicktest Kunde"); db.add(kunde); db.flush()
    projekt = Project(project_number="P-KT-0001", name="Monatswechsel", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-0001", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-KT-0001",
                    title="Monatswechsel", customer_name="Klicktest Kunde")
    anna = Employee(employee_number="E-1", first_name="Anna", last_name="Admin", employee_group="angestellt", active=True, hourly_wage=Decimal("22.00"))
    db.add_all([auftrag, anna]); db.flush()
    admin = AppUser(username="anna", display_name="Anna Admin", role="admin", employee_id=anna.id, password_hash=k.passwort())
    db.add(admin); db.flush()
    for tag, stunden in ((date(2026, 9, 15), "1.50"), (date(2026, 9, 30), "4.00"), (date(2026, 10, 1), "2.00"),
                         (date(2026, 10, 31), "3.00"), (date(2026, 11, 1), "7.00")):
        db.add(TimeEntry(employee_id=anna.id, project_id=projekt.id, order_id=auftrag.id, work_date=tag, entry_type="site",
                         counts_as_productive=True, hours=Decimal(stunden), status="booked", source="manual"))
    db.commit()
    return {"cookies": {"anna": k.cookies(admin)}}


async def pruefen(tab, seed, p):
    await tab.anmelden(seed["cookies"]["anna"])
    skript = None
    for nr, (zone, zeitpunkt, zeitraum, anzeige) in enumerate(FAELLE, start=1):
        if skript:
            await tab.cmd("Page.removeScriptToEvaluateOnNewDocument", identifier=skript)
        fest = int(datetime.fromisoformat(zeitpunkt.replace("Z", "+00:00")).timestamp() * 1000)
        skript = (await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=UHR % fest))["identifier"]
        await tab.cmd("Emulation.setTimezoneOverride", timezoneId=zone)
        await tab.oeffnen("/", f"({KACHEL})")
        await tab.warten(f"({ZEITRAUM})")
        name = f"{zone} {zeitpunkt}"
        p.pruefe(f"{name}: Kachel", await tab.js(f"({KACHEL})||null"), anzeige)
        p.pruefe(f"{name}: Zeitraum der Abfrage", await tab.js(ZEITRAUM), zeitraum)
        p.pruefe(f"{name}: JS-Fehler", tab.fehler, [])
        if nr <= 2:
            await tab.bild(f"dashboard_{nr}_{zone.replace('/', '-')}")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
