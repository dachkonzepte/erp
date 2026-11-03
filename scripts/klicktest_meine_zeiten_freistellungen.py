"""Klicktest: „Meine Zeiten“ zeigt die Freistellungen des Arbeitszeitkalenders (seit 1.9.187, Lohn L1a, Stufe 2, Punkt 2).

Befüllt: Auftrag mit Einsatz für Mia (Monteurin) und Tom (Monteur), beide gewerblich mit Tarif (Dezember: Winter 7,50 h); Tom hat einen
genehmigten Urlaub 28.–31.12.2026 mit „ganzer Urlaubstag“ an Silvester; Kim (Büro – Finanzen, kaufmännisch).

    Mia (1280 × 620, hell)  Dezember: Karte „Abwesenheit“ mit „Heiligabend – bezahlte Freistellung · Do 24.12.2026 · 7,00 h · bezahlt“ und
                            „Silvester – unbezahlte Freistellung · Do 31.12.2026 · 7,50 h · unbezahlt“, je „gilt ohne Antrag“; im November keine
    Mia (412 px, dunkel)    dieselben Zeilen, kein waagrechtes Rollen
    Tom (412 px, dunkel)    nur Heiligabend -- Silvester nimmt sein Urlaub; „Meine Anträge“ nennt „Kalendertag als Urlaubstag“
    Kim (1280 × 620, hell)  kaufmännisch: keine Freistellung

Stehende Uhr Di 01.12.2026 10:00 in Instanz und Browser.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_meine_zeiten_freistellungen.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.absence_requests import create_request, review_request
    from app.models import (
        AppUser, Customer, Employee, PlanningSlot, Project, Property, Quote, QuoteItem, Team, WorkPreparationEmployee,
        WorkPreparationTeamAssignment,
    )
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    leute = {name: Employee(employee_number=nr, first_name=name, last_name=nach, employee_group=gruppe, active=True,
                            hourly_wage=Decimal("22.00"))
             for name, nr, nach, gruppe in (("Mia", "E-1", "Monteurin", "gewerblich"), ("Tom", "E-2", "Monteur", "gewerblich"),
                                            ("Kim", "K-1", "Kauffrau", "kaufmaennisch"))}
    db.add_all(leute.values()); db.flush()
    benutzer = {name.lower(): AppUser(username=name.lower(), display_name=f"{e.first_name} {e.last_name}",
                                      role="buero_finanzen" if name == "Kim" else "field", employee_id=e.id, password_hash=k.passwort())
                for name, e in leute.items()}
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Uebach")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KT-FS", name="Dachsanierung Halle", customer_id=kunde.id, status="angebot",
                      property_id=objekt.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-FS", project_id=projekt.id, title="Dachsanierung Halle", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"), unit="m²",
                     unit_price=Decimal("48.90")))
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=date(2026, 11, 2), execution_start=None, execution_end=None,
                                      caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    prep = ensure_preparation(db, auftrag.id)
    team = Team(team_number="K-1", name="Kolonne 1")
    db.add(team); db.flush()
    zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuordnung); db.flush()
    db.add_all([WorkPreparationEmployee(preparation_id=prep.id, employee_id=leute[n].id) for n in ("Mia", "Tom")]
               + [PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=date(2026, 11, 23),
                               end_date=date(2026, 12, 18))])
    db.commit()
    antrag = create_request(db, employee_id=leute["Tom"].id, absence_category="urlaub", start_date=date(2026, 12, 28),
                            end_date=date(2026, 12, 31), kalendertag_urlaub=True)
    review_request(db, antrag.id, decision="approved", reviewed_by_user_id=None)
    return {"cookies": {name: k.cookies(u) for name, u in benutzer.items()}, "uhr_ms": k.uhr_ms()}


BEREIT = "typeof D!=='undefined'&&D&&D.monat==='2026-12'"
ZEILEN = ("(b=>b.hidden?null:[...b.querySelectorAll('.antrag')].map(z=>[z.querySelector('b').textContent,"
          "z.querySelector('.antrag-text span').textContent,z.querySelector('.antrag-status').textContent]))(document.getElementById('abwFrei'))")
HEILIGABEND = ["Heiligabend – bezahlte Freistellung", "Do 24.12.2026 · 7,00 h · bezahlt", "gilt ohne Antrag"]
SILVESTER = ["Silvester – unbezahlte Freistellung", "Do 31.12.2026 · 7,50 h · unbezahlt", "gilt ohne Antrag"]


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.browser_uhr_fest(seed["uhr_ms"])

    # --- Mia, 1280 × 620 hell -----------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(1280, 620, mobil=True)
    await tab.oeffnen("/mobil/zeiten", BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen("/mobil/zeiten", BEREIT)
    p.pruefe("Mia, Dezember: Heiligabend und Silvester mit Stunden und „bezahlt“/„unbezahlt“", await tab.js(ZEILEN), [HEILIGABEND, SILVESTER])
    p.pruefe("Die Zeilen stehen in der Karte „Abwesenheit“ unter dem Text", await tab.js(
        "(f=>[!!f.closest('#abwesenheitKarte'),f.getBoundingClientRect().top>document.getElementById('abwText').getBoundingClientRect().bottom])"
        "(document.getElementById('abwFrei'))"), [True, True])
    await tab.js("document.getElementById('abwesenheitKarte').scrollIntoView({block:'start'})")
    await tab.bild("1_freistellungen_hell_1280")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('monatZurueck').click()", "#tage")
    p.pruefe("Mia, November: keine Freistellung", await tab.js(f"[D.monat,{ZEILEN}]"), ["2026-11", None])
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

    # --- Mia, 412 px dunkel -------------------------------------------------------------------------------------------------------
    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen("/mobil/zeiten", BEREIT)
    p.pruefe("Mia, 412 px: dieselben Zeilen", await tab.js(ZEILEN), [HEILIGABEND, SILVESTER])
    p.pruefe("412 px: kein waagrechtes Rollen", await tab.ueberlauf(), [])
    await tab.js("document.getElementById('abwesenheitKarte').scrollIntoView({block:'start'})")
    await tab.bild("2_freistellungen_dunkel_412")

    # --- Tom, 412 px dunkel: Silvester im Urlaub ----------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["tom"])
    await tab.oeffnen("/mobil/zeiten", BEREIT)
    p.pruefe("Tom: nur Heiligabend -- Silvester nimmt der Urlaub als ganzen Urlaubstag", await tab.js(ZEILEN), [HEILIGABEND])
    await tab.js("document.getElementById('antragKnopf').click()")
    await tab.warten("document.querySelector('#adAntraege .antrag')", 10)
    p.pruefe("Tom: „Meine Anträge“ nennt die Antwort", await tab.js(
        "document.querySelector('#adAntraege .antrag-text span').textContent.includes('Kalendertag als Urlaubstag')"), True)
    await tab.js("document.getElementById('abwDialog').close()")
    await tab.js("document.getElementById('abwesenheitKarte').scrollIntoView({block:'start'})")
    await tab.bild("3_tom_urlaub_dunkel_412")
    p.pruefe("Tom: keine JS-Fehler", tab.fehler, [])

    # --- Kim, Büro – Finanzen, kaufmännisch ---------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["kim"])
    await tab.fenster(1280, 620, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen("/mobil/zeiten", BEREIT)
    p.pruefe("Kim (kaufmännisch): keine Freistellung", await tab.js(ZEILEN), None)
    p.pruefe("Kim: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Meine Zeiten: Freistellungen des Arbeitszeitkalenders", uhr="2026-12-01 10:00"))
