"""Klicktest: "heute" im Browser um halb eins nachts (1.8.87, Vorgabe R4c "Vorweg" 1).

Bis 1.8.86 bildeten mehrere Seiten das heutige Datum über toISOString() in UTC: zwischen 0 und 2 Uhr Berliner Zeit der Vortag.
Anlass: `klicktest_teil_updates` um 00:11 Uhr -- die Monteur-Zeiterfassung lud die Buchungen bis "gestern" und blieb leer
("/time-tracking: Seite nicht bereit"). Seit 1.8.87 kommt "heute" aus `_berlin_date.html` (berlinToday() u. a.).

Das Skript lässt die Instanz heute ab 00:30 Uhr laufen (`klicktest_main(..., uhr="00:30")`) und hält die Uhr des Browsers auf
heute 00:30 Uhr Berliner Zeit fest (eigene Date-Klasse per Page.addScriptToEvaluateOnNewDocument), mit der Zeitzone des
Browsers auf UTC bzw. New York (Emulation.setTimezoneOverride) -- dort ist es noch gestern. Geprüft:

- Monteur, Meine Zeiten (412 px; seit 1.9.59 statt Zeiterfassung und Stundenzettel): die Buchung von heute steht in der Liste,
  „Zeit nachtragen“ schlägt den Berliner Tag vor, der Monat der Seite ist der Berliner;
- Büro, Zeiten (seit 1.9.98 statt der Zeiterfassung mit `today()`): „Buchung“ schlägt den Berliner Tag vor; Aufgaben: fällig gestern
  überfällig, fällig heute nicht;
- Plantafel: Wochenbeginn und Markierung "heute" aus dem Berliner Tag; Kalender: Ausgangstag heute.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_browser_datum.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa 30 Sekunden.
"""

import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

UHR = """(() => { const RealDate = Date, FIXED = %d;
  globalThis.Date = class extends RealDate { constructor(...a) { super(...(a.length ? a : [FIXED])); } static now() { return FIXED; } }; })();"""


def befuellen(db, k):
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.models import AppUser, Customer, Employee, Order, OrderItem, Project, WorkPreparationEmployee
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.tasks import create_task
    from app.time_tracking import create_manual_entry
    from app.work_preparation import ensure_preparation

    heute = berlin_today()  # Uhr der Instanz: heute 00:30 Uhr Berliner Zeit
    max_m = Employee(employee_number="M-1", first_name="Max", last_name="Monteur", employee_group="gewerblich",
                     weekly_hours=Decimal("40"), active=True)
    anna = Employee(employee_number="B-1", first_name="Anna", last_name="Büro", employee_group="angestellt",
                    weekly_hours=Decimal("40"), active=True)
    db.add_all([max_m, anna]); db.flush()
    monteur = AppUser(username="max", display_name="Max", role="field", employee_id=max_m.id, password_hash=k.passwort())
    admin = AppUser(username="anna", display_name="Anna Büro", role="admin", employee_id=anna.id, password_hash=k.passwort())
    kunde = Customer(name="Kundin Nacht", last_name="Nacht")
    db.add_all([monteur, admin, kunde]); db.flush()
    projekt = Project(project_number="P-KT-1", name="Nachtschicht", customer_id=kunde.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AU-KT-0001", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-KT-1",
                    title="Dach", customer_name=kunde.name, vat_rate=Decimal("19"))
    db.add(auftrag); db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Abdichtung",
                     quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
    db.commit()
    vorbereitung = ensure_preparation(db, auftrag.id)
    vorbereitung.planned_start, vorbereitung.planned_end = heute, heute
    db.add(WorkPreparationEmployee(preparation_id=vorbereitung.id, employee_id=max_m.id))
    db.commit()
    eintrag = create_manual_entry(db, employee_id=max_m.id, order_id=auftrag.id, work_date=heute, hours=Decimal("2"),
                                  notes="nach Mitternacht")
    gestern = create_task(db, "Fällig gestern", due_date=heute - timedelta(days=1), assigned_employee_id=anna.id)
    heute_faellig = create_task(db, "Fällig heute", due_date=heute, assigned_employee_id=anna.id)
    return {"heute": heute.isoformat(), "eintrag": eintrag.id, "aufgabe_gestern": gestern["id"],
            "aufgabe_heute": heute_faellig["id"], "cookies": {"max": k.cookies(monteur), "anna": k.cookies(admin)}}


def _montag(tag: date) -> str:
    return (tag - timedelta(days=tag.weekday())).isoformat()


async def pruefen(tab, seed, p):
    heute = date.fromisoformat(seed["heute"])
    berlin = datetime.combine(heute, time(0, 30), tzinfo=ZoneInfo("Europe/Berlin"))
    fest = int(berlin.timestamp() * 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=UHR % fest)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    gestern_utc = (heute - timedelta(days=1)).isoformat()
    p.pruefe("Ausgangslage: in UTC ist noch gestern",
             datetime.fromtimestamp(fest / 1000, ZoneInfo("UTC")).date().isoformat(), gestern_utc)

    for zone in ("UTC", "America/New_York"):
        await tab.cmd("Emulation.setTimezoneOverride", timezoneId=zone)
        # --- Monteur ---------------------------------------------------------------------------------------------------
        await tab.anmelden(seed["cookies"]["max"])
        await tab.fenster(412, 900, mobil=True)
        bereit = await tab.oeffnen("/mobil/zeiten", f"!!document.querySelector('[data-zeile=\"{seed['eintrag']}\"]')")
        p.pruefe(f"{zone}: Meine Zeiten zeigt die Buchung von heute", bereit, True)
        await tab.js("document.getElementById('nachtragenKnopf').click()")
        p.pruefe(f"{zone}: „Zeit nachtragen“ mit dem Berliner Tag", await tab.js("document.getElementById('zdDatum').value"), seed["heute"])
        await tab.js("document.getElementById('zeitDialog').close()")
        p.pruefe(f"{zone}: Monat der Seite", await tab.js("D.monat"), seed["heute"][:7])
        p.pruefe(f"{zone}: Monteur JS-Fehler", tab.fehler, [])
        if zone == "UTC":
            await tab.bild("monteur_meine_zeiten_0030")

        # --- Büro ------------------------------------------------------------------------------------------------------
        await tab.anmelden(seed["cookies"]["anna"])
        await tab.fenster(1400, 1000)
        # seit 1.9.98 „Zeiten“ (bis 1.9.97 die Zeiterfassung: today())
        await tab.oeffnen("/zeiten", "!!window.P&&document.getElementById('monatTitel').textContent!==''")
        await tab.js("document.getElementById('neueBuchung').click()")
        await tab.warten("document.getElementById('buchungDialog').open&&document.getElementById('bdDatum').value!==''", 10)
        p.pruefe(f"{zone}: Zeiten „Buchung“ mit dem Berliner Tag", await tab.js("document.getElementById('bdDatum').value"), seed["heute"])
        await tab.js("document.getElementById('buchungDialog').close()")
        await tab.oeffnen("/tasks", "typeof isOverdue==='function'&&document.body.innerText.includes('Fällig heute')")
        p.pruefe(f"{zone}: Aufgabe von gestern überfällig, von heute nicht", await tab.js(
            f"[isOverdue({{due_date:'{(heute - timedelta(days=1)).isoformat()}',status_is_done:false}}),"
            f"isOverdue({{due_date:'{seed['heute']}',status_is_done:false}})]"), [True, False])
        await tab.oeffnen("/planning", "board")
        p.pruefe(f"{zone}: Plantafel Wochenbeginn", await tab.js("iso(periodStart)"), _montag(heute))
        p.pruefe(f"{zone}: Plantafel heute markiert", await tab.js(
            f"(()=>{{const h=[...document.querySelectorAll('.day-head.today')];"
            f"return h.length===1&&h[0].innerHTML.includes(fmt('{seed['heute']}'))}})()"), True)
        await tab.oeffnen("/kalender", "typeof toDateStr==='function'&&typeof anchor!=='undefined'")
        p.pruefe(f"{zone}: Kalender Ausgangstag", await tab.js("toDateStr(anchor)"), seed["heute"])
        p.pruefe(f"{zone}: Büro JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="00:30"))
