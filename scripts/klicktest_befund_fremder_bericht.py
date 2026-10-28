"""Klicktest: Befund im Bericht einer anderen Person (1.9.112, Stufe 5, R1, Punkt 2) -- „erfasst von“ ist das anlegende Konto.

    Bericht der Monteurin Mia (Rapport ohne Vorlage), Schritt „Befunde“:
    Büro – Finanzen (Bernd, mit Mitarbeiter)  legt einen Befund ohne Prüfpunkt an -- angelegt (bis 1.9.111 403), die Karte zeigt „erfasst von
                                              Bernd Büro“; der Server hält Konto und Mitarbeiter Bernd fest, nicht Mia (Bild)
    Admin (ohne Mitarbeiter)                  legt einen zweiten an -- „erfasst von Ada Admin“, kein Mitarbeiter
    Monteurin                                 sieht beide mit „erfasst von …“
    Einsatzberichte                           „Durchgeführt von“: Bernd sieht „— nicht zugeordnet —“ und sich selbst, die Admin alle

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_befund_fremder_bericht.py [--app-port N] [--cdp-port N]
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
    from app.service_reports import create_report
    from app.work_preparation import ensure_preparation

    def mitarbeiter(nummer, vorname, nachname):
        return Employee(employee_number=nummer, first_name=vorname, last_name=nachname, employee_group="angestellt",
                        hourly_wage=Decimal("30"), weekly_hours=Decimal("40"), active=True)

    mia, bernd = mitarbeiter("E-1", "Mia", "Monteurin"), mitarbeiter("E-2", "Bernd", "Büro")
    kunde = Customer(name="Bauherr Befund", last_name="Befund", city="Uebach")
    db.add_all([mia, bernd, kunde]); db.flush()
    konten = {"mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort()),
              "bernd": AppUser(username="bernd", display_name="Bernd Büro", role="buero_finanzen", employee_id=bernd.id,
                               password_hash=k.passwort()),
              "ada": AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort())}
    db.add_all(konten.values()); db.flush()
    projekt = Project(project_number="P-B-1", name="Dach Befund", customer_id=kunde.id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    quote = Quote(quote_number="A-B-1", project_id=projekt.id, title="Reparatur", vat_rate=Decimal("19"))
    db.add(quote); db.flush()
    db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Reparatur", quantity=Decimal("1"), unit="Stk", unit_price=Decimal("300")))
    db.commit()
    order = create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    prep = ensure_preparation(db, order.id)
    team = Team(name="Kolonne 1"); db.add(team); db.flush()
    zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuordnung); db.flush()
    db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=mia.id, employee_name_snapshot="Mia Monteurin"))
    db.commit()
    bericht = create_report(db, order.id, report_type="rapport", description="Kehle undicht, geprüft", created_by_employee_id=mia.id)
    return {"order": order.id, "bericht": bericht["id"], "mia": mia.id, "bernd": bernd.id,
            "cookies": {name: k.cookies(konto) for name, konto in konten.items()}}


BEREIT = "document.getElementById('raster')&&!document.getElementById('raster').hidden&&typeof SCHRITT!=='undefined'&&SCHRITT"


async def _befund(tab, text):
    await tab.js(f"(()=>{{const f=document.getElementById('befund-text-frei');f.value={json.dumps(text)};f.dispatchEvent(new Event('input'))}})()")
    await tab.js("document.querySelector('#befundOhnePunkt [data-klick=befund-anlegen]').click()")
    return await tab.warten(f"BEFUNDE.some(b=>b.description==={json.dumps(text)})")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"]["bernd"])
    await tab.oeffnen(f"/service-reports/{seed['bericht']}#befunde", BEREIT + "&&SCHRITT==='befunde'")
    p.pruefe("Büro – Finanzen: Befund im Bericht der Monteurin angelegt", await _befund(tab, "Ziegel an der Kehle gebrochen"), True)
    karte = await tab.js("[...document.querySelectorAll('[data-erfasst-von]')].map(e=>e.textContent)")
    p.pruefe("Karte: erfasst von Bernd Büro", karte, [" · erfasst von Bernd Büro"])
    server = await tab.js(f"fetch('/api/service-reports/{seed['bericht']}/findings').then(r=>r.json()).then(l=>l.map(b=>[b.created_by_name,b.created_by_employee_id]))")
    p.pruefe("Server: Konto und Mitarbeiter Bernd, nicht Mia", server, [["Bernd Büro", seed["bernd"]]])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("befund_im_fremden_bericht")
    p.pruefe("JS-Fehler (Büro – Finanzen)", tab.fehler, [])
    await tab.oeffnen(f"/orders/{seed['order']}/service-reports", "document.getElementById('editEmployee')&&typeof durchgefuehrtVonOptionen==='function'"
                      "&&employees.length>0")
    p.pruefe("„Durchgeführt von“ (Büro – Finanzen): nur sie selbst", await tab.js(
        "(()=>{const s=document.createElement('select');s.innerHTML=durchgefuehrtVonOptionen();return [...s.options].map(o=>o.text)})()"),
        ["— nicht zugeordnet —", "Bernd Büro"])

    await tab.anmelden(seed["cookies"]["ada"])
    await tab.oeffnen(f"/service-reports/{seed['bericht']}#befunde", BEREIT + "&&SCHRITT==='befunde'")
    p.pruefe("Admin: zweiter Befund", await _befund(tab, "Rinne verstopft"), True)
    p.pruefe("Admin: erfasst von Ada Admin, ohne Mitarbeiter", await tab.js(
        f"fetch('/api/service-reports/{seed['bericht']}/findings').then(r=>r.json()).then(l=>l.map(b=>[b.created_by_name,b.created_by_employee_id]))"),
        [["Bernd Büro", seed["bernd"]], ["Ada Admin", None]])
    await tab.oeffnen(f"/orders/{seed['order']}/service-reports", "document.getElementById('editEmployee')&&typeof durchgefuehrtVonOptionen==='function'"
                      "&&employees.length>0")
    p.pruefe("„Durchgeführt von“ (Admin): alle", await tab.js(
        "(()=>{const s=document.createElement('select');s.innerHTML=durchgefuehrtVonOptionen();return [...s.options].map(o=>o.text).sort()})()"),
        ["Bernd Büro", "Mia Monteurin", "— nicht zugeordnet —"])

    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(1280, 620)
    await tab.oeffnen(f"/service-reports/{seed['bericht']}#befunde", BEREIT + "&&SCHRITT==='befunde'")
    p.pruefe("Monteurin sieht beide mit „erfasst von“", await tab.js(
        "[...document.querySelectorAll('[data-erfasst-von]')].map(e=>e.textContent)"),
        [" · erfasst von Bernd Büro", " · erfasst von Ada Admin"])
    p.pruefe("JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
