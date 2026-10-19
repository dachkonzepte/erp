"""Klicktest: Kolonnenführer-Kennzeichen entziehen, während für das Team eine Gruppenzeit läuft (1.8.145).

Ohne Kennzeichen stoppt die Kolonnenführerin ihre Gruppenzeit nicht mehr für alle (1.8.144). Das Stammdaten-Formular des Teams fragt
deshalb nach, bevor es ihr das Kennzeichen nimmt; gestoppt wird nichts:

    Abbrechen    Rückfrage „Gruppenzeit läuft noch – trotzdem entziehen?“, Meldung „Nicht gespeichert – das Kennzeichen bleibt.“,
                 das Kennzeichen steht noch
    OK           gespeichert, zurück in die Liste der Teams, das Kennzeichen ist weg, beide Zeiten der Gruppe laufen weiter

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_kennzeichen_entziehen.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

FRAGE = "Gruppenzeit läuft noch – trotzdem entziehen?"
# confirm() hält den headless Chrome an -- umgeleitet; die Fragen überleben das Neuladen nach dem Speichern im sessionStorage
CONFIRM = ("window.confirm=m=>{const f=JSON.parse(sessionStorage.getItem('fragen')||'[]');f.push(m);"
           "sessionStorage.setItem('fragen',JSON.stringify(f));return sessionStorage.getItem('antwort')==='ja'}")


def befuellen(db, k):
    from datetime import timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_now
    from app.models import AppUser, Customer, Employee, Order, OrderItem, Project, Team, TeamEmployee
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.time_tracking import start_group_timer

    kunde = Customer(name="Kundin Kolonne", last_name="Kolonne")
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-KE-1", name="Dach Kolonne", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KE-1", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-KE-1", title="Auftrag Kolonne",
                    customer_name="Kundin Kolonne")
    db.add(auftrag); db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Dacheindeckung", quantity=Decimal("10"),
                     unit="m²", unit_price=Decimal("50")))
    lea = Employee(employee_number="K-1", first_name="Lea", last_name="Leiterin", employee_group="gewerblich", active=True)
    max_ = Employee(employee_number="K-2", first_name="Max", last_name="Mitglied", employee_group="gewerblich", active=True)
    db.add_all([lea, max_]); db.flush()
    team = Team(name="Kolonne Nord", active=True)
    db.add(team); db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=lea.id, is_crew_leader=True),
                TeamEmployee(team_id=team.id, employee_id=max_.id, is_crew_leader=False)])
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    db.add(bea); db.flush()
    db.commit()
    start_group_timer(db, employee_ids=[lea.id, max_.id], team_id=team.id, actor_employee_id=lea.id, is_admin=True, order_id=auftrag.id,
                      started_at=(berlin_now() - timedelta(hours=2)).replace(microsecond=0))
    return {"bea": k.cookies(bea), "team": team.id, "lea": lea.id, "auftrag": auftrag.id}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    await tab.anmelden(seed["bea"])
    team, lea = seed["team"], seed["lea"]
    kennzeichen = (f"fetch('/api/teams/{team}').then(r=>r.json())"
                   ".then(t=>t.employees.filter(e=>e.is_crew_leader).map(e=>e.employee_name).join('|'))")
    laufend = f"fetch('/api/time-entries?order_id={seed['auftrag']}').then(r=>r.json()).then(j=>j.map(e=>e.status).join('|'))"

    await tab.oeffnen(f"/master-data/teams/{team}/edit", f"document.querySelector('.team-employee-leader[data-id=\"{lea}\"]')")
    p.pruefe("Kennzeichen gesetzt", await tab.js(f"document.querySelector('.team-employee-leader[data-id=\"{lea}\"]').checked"), True)
    await tab.js(f"document.querySelector('.team-employee-leader[data-id=\"{lea}\"]').checked=false")

    await tab.js("sessionStorage.setItem('antwort','nein')")
    await tab.js("save()")
    p.pruefe("Abbrechen: Rückfrage", await tab.js("JSON.parse(sessionStorage.getItem('fragen')||'[]')"), [FRAGE])
    p.pruefe("Abbrechen: Meldung", await tab.js("document.getElementById('msg').textContent"), "Nicht gespeichert – das Kennzeichen bleibt.")
    p.pruefe("Abbrechen: Kennzeichen bleibt", await tab.js(kennzeichen), "Lea Leiterin")
    await tab.bild("abgebrochen")

    await tab.js("sessionStorage.setItem('antwort','ja')")
    await tab.js("void save()")
    await tab.warten("location.pathname==='/master-data'&&location.hash==='#teams'")
    p.pruefe("OK: zweite Rückfrage", await tab.js("JSON.parse(sessionStorage.getItem('fragen')||'[]')"), [FRAGE, FRAGE])
    p.pruefe("OK: Kennzeichen weg", await tab.js(kennzeichen), "")
    p.pruefe("OK: nichts gestoppt", await tab.js(laufend), "running|running")
    p.pruefe("JS-Fehler", tab.fehler, [])
    await tab.bild("gespeichert")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
