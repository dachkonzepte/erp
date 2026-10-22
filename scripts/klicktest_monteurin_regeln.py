"""Klicktest: Regeln für die Monteurin, Minimal-Anzeige (Stufe 4, Runde 1; seit 1.9.35 vergessener Feierabend).

Befüllt: Auftrag mit Einsatz (Plantafel heute ± 7 Tage) für Mia (Monteurin) und Tom (Monteur); beide haben eine Zeit, die gestern um
06:45 Uhr begann und noch läuft (Feierabend vergessen); Anna (Admin).

    Mia (412 px, dunkel)  /mobil: Hinweis „Deine Zeit läuft noch seit <gestern>, 06:45 Uhr“ mit Zeitart, Auftrag und „Ende nachtragen →“.
                          Zeiterfassung: statt Uhr und „Zeit stoppen“ der Hinweis „Die Zeit vom … läuft noch“, Feld „Ende an diesem Tag“,
                          Knopf „Ende nachtragen“; „Schnell starten“ meldet die offene Zeit (Server 409). Ende leer -> „Bitte das Ende
                          angeben.“, 06:00 -> Meldung des Servers (vor dem Start), 16:00 -> „Ende nachgetragen: gebucht 8,50 h · anwesend
                          9,25 h · Pause 45 min“, danach startet sie neu (Uhr und „Zeit stoppen“ wieder da).
    Anna (1400 px, hell)  Zeiterfassung für Tom: dieselbe offene Anzeige, „Ende nachtragen“ 15:30 -> gebucht mit Pause; im Verlauf (API)
                          steht Anna.

Feste Uhr 10:00 (/mobil meldet ab 19 Uhr ab); die Daten liegen relativ zum heutigen Tag.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_monteurin_regeln.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import datetime, time, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.models import (
        AppUser, Customer, Employee, PlanningSlot, Project, Quote, QuoteItem, Team, WorkPreparationEmployee, WorkPreparationTeamAssignment,
    )
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.time_tracking import start_timer
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    gestern = heute - timedelta(days=1)
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    tom = Employee(employee_number="E-2", first_name="Tom", last_name="Monteur", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    db.add_all([mia, tom]); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort()),
        "anna": AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-KT-MR", name="Dachsanierung Halle", customer_id=kunde.id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-MR", project_id=projekt.id, title="Dachsanierung Halle", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"), unit="m²",
                     unit_price=Decimal("48.90")))
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=heute - timedelta(days=30), execution_start=None, execution_end=None,
                                      caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    prep = ensure_preparation(db, auftrag.id)
    team = Team(team_number="K-1", name="Kolonne 1")
    db.add(team); db.flush()
    zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuordnung); db.flush()
    db.add_all([WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia.id),
                WorkPreparationEmployee(preparation_id=prep.id, employee_id=tom.id),
                PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=heute - timedelta(days=7),
                             end_date=heute + timedelta(days=7))])
    db.commit()
    zeiten = {name: start_timer(db, employee_id=emp.id, order_id=auftrag.id, started_at=datetime.combine(gestern, time(6, 45))).id
              for name, emp in (("mia", mia), ("tom", tom))}
    return {"auftrag": auftrag.id, "auftragsnummer": auftrag.order_number, "tom": tom.id, "zeiten": zeiten,
            "gestern": gestern.isoformat(), "gestern_de": f"{gestern:%d.%m.%Y}",
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


MOBIL_BEREIT = "!document.getElementById('assignmentsList').textContent.includes('Lädt')"
FELD_BEREIT = "!document.getElementById('activeCard').hidden && document.getElementById('quickOrder').options.length>1"
BUERO_BEREIT = "document.getElementById('activeCard').style.display==='block'"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    g = seed["gestern_de"]

    # --- Mia: /mobil --------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/mobil", MOBIL_BEREIT)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen("/mobil", MOBIL_BEREIT)
    await tab.warten("!document.getElementById('offeneZeit').hidden")
    text = await tab.js("document.getElementById('offeneZeit').innerText")
    p.pruefe("/mobil: Hinweis mit Start, Zeitart, Auftrag", [f"Deine Zeit läuft noch seit {g}, 06:45 Uhr" in (text or ""),
             "Baustellenzeit" in (text or ""), seed["auftragsnummer"] in (text or "")], [True, True, True])
    p.pruefe("/mobil: Link „Ende nachtragen →“ zur Zeiterfassung", await tab.js(
        "(a=>[a.textContent, new URL(a.href).pathname])(document.querySelector('#offeneZeit a'))"), ["Ende nachtragen →", "/time-tracking"])
    p.pruefe("/mobil: Ecke der Karte 16 px (Monteursrahmen)", await tab.js(
        "getComputedStyle(document.querySelector('.zeit-offen-karte')).borderTopLeftRadius"), "16px")
    p.pruefe("/mobil 412 px: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.bild("1_mobil_offene_zeit_dunkel_412")

    # --- Mia: Zeiterfassung, offene Zeit ------------------------------------------------------------------------------------------
    await tab.oeffnen("/time-tracking", FELD_BEREIT)
    p.pruefe("Zeiterfassung: offene Anzeige statt Uhr und Stopp", await tab.js(
        "['offenBlock','endeBtn','stopBtn','activeTime','quickCard'].map(id=>document.getElementById(id).hidden)"),
        [False, False, True, True, False])
    p.pruefe("Zeiterfassung: Hinweis", await tab.js("document.getElementById('offenHinweis').textContent"),
             f"Die Zeit vom {g} läuft noch (seit 06:45 Uhr). Trag das Ende an diesem Tag nach.")
    await tab.js(f"document.getElementById('quickOrder').value='{seed['auftrag']}'")
    await tab.js("document.querySelector('#quickTiles button').click()")
    await tab.warten("document.getElementById('quickStatus').textContent.length>0")
    p.pruefe("Start mit offener Zeit: Meldung des Servers", await tab.js("document.getElementById('quickStatus').textContent"),
             f"Fehler: Die Zeit vom {g} läuft noch – zuerst das Ende nachtragen, dann neu starten.")
    await tab.js("document.getElementById('quickCard').scrollIntoView({block:'center'})")
    await tab.bild("2_start_mit_offener_zeit_dunkel_412")

    await tab.js("window.scrollTo(0,0);document.getElementById('endeBtn').click()")
    p.pruefe("Ende leer: Meldung", await tab.js("document.getElementById('endeStatus').textContent"), "Bitte das Ende angeben.")
    await tab.js("document.getElementById('endeZeit').value='06:00';document.getElementById('endeBtn').click()")
    await tab.warten("document.getElementById('endeStatus').textContent.includes('Start')")
    p.pruefe("Ende vor dem Start: Meldung des Servers", await tab.js("document.getElementById('endeStatus').textContent"),
             "Das Ende muss nach dem Start liegen (06:45 Uhr).")
    await tab.bild("3_ende_vor_start_dunkel_412")
    await tab.js("document.getElementById('endeZeit').value='16:00'")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('endeBtn').click()", "#entriesList")
    p.pruefe("Ende nachgetragen: gebucht, anwesend, Pause", await tab.js("document.getElementById('buchungsHinweis').textContent"),
             "Ende nachgetragen: gebucht 8,50 h · anwesend 9,25 h · Pause 45 min")
    p.pruefe("Danach: keine laufende Zeit, „Schnell starten“ sichtbar", await tab.js(
        "[document.getElementById('activeCard').hidden, document.getElementById('quickCard').hidden]"), [True, False])
    await tab.bild("4_ende_nachgetragen_dunkel_412")
    await tab.js(f"document.getElementById('quickOrder').value='{seed['auftrag']}'")
    await tab.js("document.querySelector('#quickTiles button').click()")
    await tab.warten("!document.getElementById('activeCard').hidden")
    p.pruefe("Neu gestartet: Uhr und „Zeit stoppen“, keine offene Anzeige", await tab.js(
        "['offenBlock','endeBtn','stopBtn','activeTime'].map(id=>document.getElementById(id).hidden)"), [True, True, False, False])
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

    # --- Anna: Zeiterfassung für Tom -----------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.fenster(1400, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/time-tracking?employee_id={seed['tom']}", BUERO_BEREIT)
    p.pruefe("Büro: offene Anzeige für Tom", await tab.js(
        "['offenBlock','endeBtn','stopBtn','activeTime'].map(id=>document.getElementById(id).style.display)"),
        ["block", "block", "none", "none"])
    p.pruefe("Büro: Hinweis", await tab.js("document.getElementById('offenHinweis').textContent"),
             f"Die Zeit vom {g} läuft noch (seit 06:45 Uhr). Ende an diesem Tag nachtragen.")
    await tab.bild("5_buero_offene_zeit_hell")
    await tab.js("document.getElementById('endeZeit').value='15:30';document.getElementById('endeBtn').click()")
    await tab.warten("document.getElementById('quickStatus').textContent.includes('Ende nachgetragen')")
    p.pruefe("Büro: gebucht mit Pause nach der Zeitregel", await tab.js("document.getElementById('quickStatus').textContent"),
             f"Ende nachgetragen ({g}): gebucht 8,25 h · anwesend 8,75 h · Pause 30 min")
    p.pruefe("Büro: keine laufende Zeit mehr", await tab.js("document.getElementById('activeCard').style.display"), "none")
    verlauf = await tab.js(
        f"fetch('/api/audit-logs?entity_id={seed['zeiten']['tom']}&actor=Anna&limit=50').then(r=>r.ok?r.json():null)")
    felder = sorted({e.get("field_name") for e in (verlauf or []) if e.get("actor_name") == "Anna Admin"})
    p.pruefe("Verlauf: Anna hat Toms Zeit geschlossen (Ende, Status)", {"ended_at", "status"} <= set(felder), True)
    p.pruefe("Anna: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Regeln für die Monteurin (Stufe 4, R1)", uhr="10:00"))
