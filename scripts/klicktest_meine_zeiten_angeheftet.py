"""Klicktest: „Meine Zeiten“ heftet eine laufende Zeit aus dem Vormonat an (seit 1.9.186, Lohn L1a, Stufe 2, Punkt 1).

Befüllt: Auftrag mit Einsatz (Plantafel 23.11.–04.12.2026) für Mia (Monteurin), Tom (Monteur) und Ben (Kolonnenführer der Kolonne 1).
Mia startete am Mo 30.11.2026 um 07:00 und hat den Feierabend vergessen; Ben startete um 07:00 eine Gruppenzeit für sich und Tom.

    Mia (412 px, dunkel)    Dezember ohne Tage, oben angeheftet „Baustellenzeit läuft seit Mo 30.11.2026, 07:00“ mit Auftrag und
                            „Beenden“, über der leeren Liste; kein waagrechtes Rollen
    Mia (1280 × 620, hell)  „Beenden“ öffnet den Dialog „Feierabend am Mo 30.11. um“: leer -> Meldung, 06:00 -> Meldung des Servers in der
                            Vorschau, 16:00 -> „Anwesend 9:00 h · Pause nach Zeitregel − 0:30 h“ und 8,50 h; „Feierabend eintragen“ bucht,
                            nichts mehr angeheftet, Ergebnis mit denselben Zahlen; im November steht 07:00–16:00, 8,50 h
    Tom (412 px, dunkel)    seine Gruppenzeit angeheftet, ohne „Beenden“, mit „Die Gruppenzeit schließt der Kolonnenführer.“

Stehende Uhr Di 01.12.2026 10:00 in Instanz und Browser -- der Monatserste, an dem „Meine Zeiten“ die Zeit bis 1.9.185 nicht zeigte
(klicktest_monteurin_regeln bleibt auf dem 11.11.2026).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_meine_zeiten_angeheftet.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date, datetime, time
    from decimal import Decimal

    from app.models import (
        AppUser, Customer, Employee, PlanningSlot, Project, Property, Quote, QuoteItem, Team, TeamEmployee, WorkPreparationEmployee,
        WorkPreparationTeamAssignment,
    )
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.time_tracking import start_group_timer, start_timer
    from app.work_preparation import ensure_preparation

    vortag = date(2026, 11, 30)
    leute = {name: Employee(employee_number=nr, first_name=name, last_name=nach, employee_group="gewerblich", active=True,
                            hourly_wage=Decimal("22.00"))
             for name, nr, nach in (("Mia", "E-1", "Monteurin"), ("Tom", "E-2", "Monteur"), ("Ben", "E-3", "Vorne"))}
    db.add_all(leute.values()); db.flush()
    benutzer = {name.lower(): AppUser(username=name.lower(), display_name=f"{e.first_name} {e.last_name}", role="field", employee_id=e.id,
                                      password_hash=k.passwort()) for name, e in leute.items()}
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Uebach")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KT-AH", name="Dachsanierung Halle", customer_id=kunde.id, status="angebot",
                      property_id=objekt.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-AH", project_id=projekt.id, title="Dachsanierung Halle", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"), unit="m²",
                     unit_price=Decimal("48.90")))
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=date(2026, 11, 2), execution_start=None, execution_end=None,
                                      caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    prep = ensure_preparation(db, auftrag.id)
    team = Team(team_number="K-1", name="Kolonne 1")
    db.add(team); db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=leute["Ben"].id, is_crew_leader=True),
                TeamEmployee(team_id=team.id, employee_id=leute["Tom"].id, is_crew_leader=False)])
    zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuordnung); db.flush()
    db.add_all([WorkPreparationEmployee(preparation_id=prep.id, employee_id=e.id) for e in leute.values()]
               + [PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=date(2026, 11, 23),
                               end_date=date(2026, 12, 4))])
    db.commit()
    mia = start_timer(db, employee_id=leute["Mia"].id, order_id=auftrag.id, started_at=datetime.combine(vortag, time(7)))
    start_group_timer(db, employee_ids=[leute["Ben"].id, leute["Tom"].id], team_id=team.id, actor_employee_id=leute["Ben"].id,
                      is_admin=False, order_id=auftrag.id, started_at=datetime.combine(vortag, time(7)))
    return {"auftragsnummer": auftrag.order_number, "mia_zeit": mia.id,
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}, "uhr_ms": k.uhr_ms()}


BEREIT = "typeof D!=='undefined'&&D&&D.monat==='2026-12'"
ANGEHEFTET = ("(b=>b.hidden?null:[b.querySelector('.angeheftet-text b').textContent,[...b.querySelectorAll('.angeheftet-text span')].map(s=>s.textContent),"
              "[...b.querySelectorAll('button')].map(x=>x.textContent)])(document.getElementById('angeheftet'))")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    auftrag = f"{seed['auftragsnummer']} · Dachsanierung Halle"

    # --- Mia, 412 px dunkel: angeheftet über der leeren Liste ----------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/mobil/zeiten", BEREIT)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen("/mobil/zeiten", BEREIT)
    p.pruefe("Dezember ohne Tage", await tab.js("[D.tage.length,document.getElementById('tage').textContent]"),
             [0, "Keine Buchungen im Dezember 2026."])
    p.pruefe("Angeheftet: Startdatum, Beginn, Auftrag, „Beenden“", await tab.js(ANGEHEFTET),
             ["Baustellenzeit läuft seit Mo 30.11.2026, 07:00", [auftrag], ["Beenden"]])
    p.pruefe("Angeheftet steht über der Liste, unter dem Kopf von „Buchungen“", await tab.js(
        "(a=>[a.top<document.getElementById('tage').getBoundingClientRect().top,"
        "a.top>document.querySelector('.buchungen-kopf').getBoundingClientRect().bottom])(document.getElementById('angeheftet').getBoundingClientRect())"),
        [True, True])
    p.pruefe("„Beenden“ mindestens 48 px hoch", await tab.js(
        "Math.round(document.querySelector('#angeheftet button').getBoundingClientRect().height)>=48"), True)
    p.pruefe("412 px: kein waagrechtes Rollen", await tab.ueberlauf(), [])
    await tab.bild("1_angeheftet_dunkel_412")

    # --- Mia, 1280 × 620 hell: Beenden --------------------------------------------------------------------------------------------
    await tab.fenster(1280, 620, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen("/mobil/zeiten", BEREIT)
    await tab.bild("2_angeheftet_hell_1280")
    await tab.js("document.querySelector('#angeheftet [data-aktion=beenden]').click()")
    await tab.warten("document.getElementById('beendenDialog').open", 10)
    p.pruefe("Dialog: Starttag im Feld, Text mit Start und Auftrag", await tab.js(
        "[document.getElementById('bdEndeText').textContent,document.getElementById('bdText').textContent]"),
        ["Feierabend am Mo 30.11. um", f"Baustellenzeit seit Mo 30.11.2026, 07:00 · {auftrag}. Das Ende liegt am Starttag."])
    await tab.js("document.getElementById('bdSpeichern').click()")
    p.pruefe("Ohne Uhrzeit: Meldung, nichts gesendet", await tab.js("document.getElementById('bdStatus').textContent"),
             "Bitte die Uhrzeit des Feierabends angeben.")
    await tab.js("(f=>{f.value='06:00';f.dispatchEvent(new Event('input'))})(document.getElementById('bdEnde'))")
    await tab.warten("document.getElementById('bdVorschauZeile').textContent.includes('Start')", 10)
    p.pruefe("06:00: Meldung des Servers in der Vorschau", await tab.js("document.getElementById('bdVorschauZeile').textContent"),
             "Das Ende muss nach dem Start liegen (07:00 Uhr).")
    await tab.js("(f=>{f.value='16:00';f.dispatchEvent(new Event('input'))})(document.getElementById('bdEnde'))")
    await tab.warten("document.getElementById('bdVorschauZahl').textContent!==''", 10)
    p.pruefe("16:00: Vorschau des Servers, die Meldung zum leeren Feld ist weg", await tab.js(
        "[document.getElementById('bdVorschauZeile').textContent,document.getElementById('bdVorschauZahl').textContent,"
        "document.getElementById('bdStatus').textContent]"),
        ["Anwesend 9:00 h · Pause nach Zeitregel − 0:30 h", "8,50 h", ""])
    p.pruefe("Knopfleiste im Bild (1280 × 620)", await tab.js(
        "document.getElementById('bdSpeichern').getBoundingClientRect().bottom<=innerHeight"), True)
    await tab.bild("3_beenden_dialog_hell_1280")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('bdSpeichern').click()", "#tage")
    p.pruefe("Gebucht: Dialog zu, nichts mehr angeheftet, Ergebnis mit den Zahlen der Vorschau", await tab.js(
        "[document.getElementById('beendenDialog').open,document.getElementById('angeheftet').hidden,document.getElementById('ergebnis').textContent]"),
        [False, True, "Feierabend am Mo 30.11. eingetragen: anwesend 9:00 h · Pause nach Zeitregel − 0:30 h · gebucht 8,50 h"])
    await tab.bild("4_beendet_hell_1280")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('monatZurueck').click()", "#tage")
    p.pruefe("November: 30.11. mit 07:00–16:00 und 8,50 h", await tab.js(
        "(z=>[z.querySelector('.zeile-spanne').textContent,z.querySelector('.zeile-stunden').textContent])"
        f"(document.querySelector('[data-zeile=\"{seed['mia_zeit']}\"]'))"), ["07:00–16:00", "8,50 h"])
    p.pruefe("November: nichts angeheftet", await tab.js("document.getElementById('angeheftet').hidden"), True)
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

    # --- Tom, 412 px dunkel: Gruppenzeit -- angeheftet ohne „Beenden“ -------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["tom"])
    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen("/mobil/zeiten", BEREIT)
    p.pruefe("Tom: angeheftet, ohne „Beenden“, mit dem Grund", await tab.js(ANGEHEFTET),
             ["Baustellenzeit läuft seit Mo 30.11.2026, 07:00", [auftrag, "Die Gruppenzeit schließt der Kolonnenführer."], []])
    await tab.bild("5_gruppenzeit_dunkel_412")
    p.pruefe("Tom: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Meine Zeiten: laufende Zeit aus dem Vormonat", uhr="2026-12-01 10:00"))
