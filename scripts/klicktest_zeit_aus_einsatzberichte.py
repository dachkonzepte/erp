"""Klicktest: Zeit buchen aus „Einsatzberichte“ (1.9.113, Stufe 5, R1, Punkt 3) -- der Dialog von „Zeiten“ statt einer eigenen Dauer.

    Büro – Finanzen  „Einsatzberichte“ des Auftrags: keine Felder zum Buchen, „Zeit buchen“ -> /zeiten mit „Neue Buchung“ geöffnet, der Auftrag
                     gewählt, ?buchung=neu aus der Adresse gestrichen; Mia, „Dauer“ 8,00 ohne Pause -> Vorschau „Pause des Tags passt danach nicht“
                     (Bild), mit 30 min -> „passt“, gespeichert; zurück auf „Einsatzberichte“: 8,00 h in der Tabelle
    Büro – Auftrag   nur lesen: Hinweis, kein „Zeit buchen“; /zeiten?buchung=neu öffnet keinen Dialog
    Bilder           einsatzberichte_zeit_buchen, zeiten_dialog_aus_einsatzberichte (8 h ohne Pause), zeiten_dialog_passt

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_zeit_aus_einsatzberichte.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import (AppUser, Customer, Employee, Project, Quote, QuoteItem, Team, WorkPreparationTeamAssignment,
                            WorkPreparationTeamEmployee)
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="angestellt", hourly_wage=Decimal("30"),
                   weekly_hours=Decimal("40"), active=True)
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Auftrag", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Zeit", last_name="Zeit", city="Uebach")
    db.add_all([mia, fin, bea, kunde]); db.flush()
    projekt = Project(project_number="P-Z-1", name="Dach Zeit", customer_id=kunde.id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    quote = Quote(quote_number="A-Z-1", project_id=projekt.id, title="Reparatur Kehle", vat_rate=Decimal("19"))
    db.add(quote); db.flush()
    db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Kehle", quantity=Decimal("1"), unit="Stk", unit_price=Decimal("500")))
    db.commit()
    order = create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    prep = ensure_preparation(db, order.id)
    team = Team(name="Kolonne 1"); db.add(team); db.flush()
    zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuordnung); db.flush()
    db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=mia.id, employee_name_snapshot="Mia Monteurin"))
    db.commit()
    return {"order": order.id, "mia": mia.id, "cookies": {"fin": k.cookies(fin), "bea": k.cookies(bea)}}


DIALOG = "document.getElementById('buchungDialog').open"


async def _feld(tab, feld, wert):
    await tab.js(f"(()=>{{const f=document.getElementById('{feld}');f.value={json.dumps(wert)};f.dispatchEvent(new Event('input'));"
                 "f.dispatchEvent(new Event('change'))})()")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"]["fin"])
    await tab.oeffnen(f"/orders/{seed['order']}/service-reports", "document.getElementById('timeEntriesTable').innerHTML.length>0")
    p.pruefe("Einsatzberichte: „Zeit buchen“, keine Felder zum Buchen", await tab.js(
        "[document.getElementById('zeitBuchenLink')?.getAttribute('href'),!!document.getElementById('teHours'),"
        "!!document.querySelector('[data-klick=\"zeit-buchen\"]')]"),
        [f"/zeiten?auftrag={seed['order']}&buchung=neu#buchungen", False, False])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("einsatzberichte_zeit_buchen")
    await tab.js("document.getElementById('zeitBuchenLink').click()")
    p.pruefe("„Neue Buchung“ auf „Zeiten“ geöffnet", await tab.warten(f"location.pathname==='/zeiten'&&!!window.KONTEXT&&{DIALOG}", 20), True)
    p.pruefe("Auftrag gewählt, Titel, ?buchung=neu gestrichen", await tab.js(
        "[document.getElementById('bdAuftrag').value,document.getElementById('bdTitel').textContent,location.search.includes('buchung'),"
        "location.hash]"), [str(seed["order"]), "Neue Buchung", False, "#buchungen"])
    await _feld(tab, "bdMitarbeiter", str(seed["mia"]))
    await tab.js("document.getElementById('bdModusDauer').click()")
    await _feld(tab, "bdStunden", "8")
    await _feld(tab, "bdPauseDauer", "0")
    p.pruefe("8 h ohne Pause: „passt danach nicht“", await tab.warten(
        "document.getElementById('bdVorschauZeile').textContent.includes('passt danach nicht')"), True)
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("zeiten_dialog_aus_einsatzberichte")
    await _feld(tab, "bdPauseDauer", "30")
    p.pruefe("mit 30 min: „passt“", await tab.warten(
        "document.getElementById('bdVorschauZeile').textContent.includes('Pause des Tags passt')"
        "&&!document.getElementById('bdVorschauZeile').textContent.includes('nicht')"), True)
    await tab.bild("zeiten_dialog_passt")
    await tab.js("document.getElementById('bdSpeichern').click()")
    p.pruefe("gespeichert", await tab.warten(f"!{DIALOG}&&document.getElementById('ergebnis')?.textContent.includes('Gebucht')", 20), True)
    await tab.oeffnen(f"/orders/{seed['order']}/service-reports", "document.querySelector('#timeEntriesTable table')")
    p.pruefe("Einsatzberichte: 8,00 h in der Tabelle", await tab.js(
        "document.getElementById('timeEntriesTable').textContent.includes('8,00 h')"), True)
    p.pruefe("JS-Fehler (Büro – Finanzen)", tab.fehler, [])

    await tab.anmelden(seed["cookies"]["bea"])
    await tab.oeffnen(f"/orders/{seed['order']}/service-reports", "document.getElementById('timeEntriesTable').innerHTML.length>0")
    p.pruefe("Büro – Auftrag: Hinweis, kein „Zeit buchen“", await tab.js(
        "[!!document.getElementById('zeitNurLesen'),!!document.getElementById('zeitBuchenLink')]"), [True, False])
    await tab.oeffnen(f"/zeiten?auftrag={seed['order']}&buchung=neu#buchungen", "!!window.B&&!document.getElementById('reiter-buchungen').hidden")
    p.pruefe("Büro – Auftrag: ?buchung=neu öffnet keinen Dialog", await tab.js(DIALOG), False)
    p.pruefe("JS-Fehler (Büro – Auftrag)", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
