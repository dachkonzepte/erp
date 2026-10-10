"""Klicktest: Abgleich mit dem Angebot gesperrt mit Grund, Hinweis fürs Büro am Einsatzbericht (1.8.71).

Befund „Vor dem Echtbetrieb“ Punkte 3 und 2 (docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.71"):

    Auftragsseite      Auftrag mit Abschlagsentwurf an einer Position, Angebot danach geändert: Karte "Quellangebot geändert"
                       nennt den Grund, kein Knopf "Quellangebot in Auftrag übernehmen"; die API antwortet 409. Ein zweiter
                       Auftrag ohne Anhängendes gleicht ab, der Projektstatus bleibt "ausfuehrung"
    Angebots-Editor    beim gesperrten Auftrag "Auftrag … öffnen" statt "Änderungen … übernehmen", der Grund im Hinweis
    Einsatzbericht     Vorgang aus einer Vertragsposition, deren Dachfläche zu einem anderen Objekt gehört: Bericht ohne
                       Fläche, das Büro sieht den Hinweis (hell und dunkel), die Monteurin auf 412 px nicht

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_abgleich_sperre.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00 (öffnet Berichte als Monteurin).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.invoices import create_abschlag_leistungsstand, update_invoice_item
    from app.models import (
        AppUser, Customer, Employee, MaintenanceContract, MaintenanceContractItem, MaintenanceWindow, Project, ProjectProfile,
        Property, Quote, QuoteItem, RoofArea, WorkPreparationEmployee,
    )
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report
    from app.work_preparation import ensure_preparation

    mona = Employee(employee_number="M-1", first_name="Mona", last_name="Monteurin", employee_group="angestellt",
                    hourly_wage=Decimal("30"), weekly_hours=Decimal("40"), active=True)
    db.add(mona); db.flush()
    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    monteurin = AppUser(username="mona", display_name="Mona Monteurin", role="field", employee_id=mona.id,
                        password_hash=k.passwort())
    kunde = Customer(name="Bauherr Klar", last_name="Klar", street="Dachweg 1", postal_code="52531", city="Uebach")
    hv = Customer(name="Hausverwaltung Hof", last_name="Hof")
    db.add_all([buero, monteurin, kunde, hv]); db.flush()
    halle = Property(customer_id=kunde.id, name="Halle Süd", street="Werkstr. 5", city="Objektstadt")
    hof = Property(customer_id=hv.id, name="Wohnanlage Hof", street="Hofweg 1", city="Objektstadt")
    db.add_all([halle, hof]); db.flush()
    db.add(RoofArea(property_id=halle.id, name="Hauptdach", roof_type="flachdach"))
    dach_hof = RoofArea(property_id=hof.id, name="Dach Hof", roof_type="flachdach")
    db.add(dach_hof); db.flush()

    def angebot_und_auftrag(nummer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, property_id=halle.id,
                          status="angebot", pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2",
                         unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
                                        remarks=None)
        return projekt, quote, order

    projekt_a, quote_a, gesperrt = angebot_und_auftrag("KT-1")
    projekt_b, quote_b, frei = angebot_und_auftrag("KT-2")
    entwurf = create_abschlag_leistungsstand(db, load_order(db, gesperrt.id))
    update_invoice_item(db, entwurf, entwurf.items[0], ist_quantity=Decimal("4"))
    projekt_b.status = "ausfuehrung"
    for quote in (quote_a, quote_b):  # Angebot nach der Beauftragung geändert
        db.add(QuoteItem(quote_id=quote.id, position_number="2", short_text="Rinne", quantity=Decimal("5"), unit="m",
                         unit_price=Decimal("20")))
    # Vorgang aus einer Vertragsposition, deren Fläche zum Objekt der Hausverwaltung gehört
    vertrag = MaintenanceContract(customer_id=hv.id, property_id=hof.id, title="Wartung Hof", interval_months=12,
                                  next_due_date=date(2027, 1, 1))
    fenster = MaintenanceWindow(label="Frühjahr", month_from=3, month_to=5)
    db.add_all([vertrag, fenster]); db.flush()
    position = MaintenanceContractItem(contract_id=vertrag.id, roof_area_id=dach_hof.id, maintenance_window_id=fenster.id,
                                       next_due_date=date(2027, 3, 1))
    db.add(position); db.flush()
    db.add(ProjectProfile(project_id=projekt_a.id, source_maintenance_contract_id=vertrag.id,
                          source_maintenance_contract_item_id=position.id))
    db.add(WorkPreparationEmployee(preparation_id=ensure_preparation(db, gesperrt.id).id, employee_id=mona.id))
    db.commit()
    bericht = create_report(db, gesperrt.id, "rapport", created_by_employee_id=mona.id, description="Kontrolle")
    return {"gesperrt": gesperrt.id, "frei": frei.id, "quote_a": quote_a.id, "projekt_b": projekt_b.id, "bericht": bericht["id"],
            "cookies": {"buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1280, 1000)
    await tab.anmelden(seed["cookies"]["buero"])
    gesperrt, frei = seed["gesperrt"], seed["frei"]

    # --- Auftragsseite: gesperrt mit Grund ---
    await tab.oeffnen(f"/orders/{gesperrt}", "order&&document.getElementById('syncCard').innerHTML.length>0")
    karte = await tab.js("document.getElementById('syncCard').textContent")
    p.pruefe("Auftrag gesperrt: Grund in der Karte",
             "Der Abgleich mit dem Angebot ist gesperrt: an den Positionen hängen Rechnungen (1 Entwurf)" in (karte or ""), True)
    p.pruefe("Auftrag gesperrt: kein Übernehmen-Knopf",
             await tab.js("[...document.querySelectorAll('#syncCard button')].map(b=>b.textContent)"), [])
    api = await tab.js(f"fetch('/api/orders/{gesperrt}/sync-source-quote',{{method:'POST',headers:{{'Content-Type':"
                       "'application/json'},body:'{}'}).then(async r=>[r.status,(await r.json()).detail.slice(0,43)])")
    p.pruefe("Auftrag gesperrt: API 409", api, [409, "Der Abgleich mit dem Angebot ist gesperrt: "])
    await tab.bild("auftrag_gesperrt")
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("auftrag_gesperrt_dunkel")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")

    # --- Auftragsseite: erlaubt, Projektstatus bleibt ---
    await tab.oeffnen(f"/orders/{frei}", "order&&document.getElementById('syncCard').innerHTML.length>0")
    p.pruefe("Auftrag frei: Knopf da",
             await tab.js("[...document.querySelectorAll('#syncCard button')].map(b=>b.textContent)"),
             ["Quellangebot in Auftrag übernehmen"])
    await tab.js("syncSource()")
    p.pruefe("Auftrag frei: abgeglichen", await tab.warten("order&&order.source_quote_in_sync===true&&order.items.length===2"),
             True)
    p.pruefe("Auftrag frei: Projektstatus bleibt",
             await tab.js(f"fetch('/api/projects/{seed['projekt_b']}').then(r=>r.json()).then(j=>j.status)"), "ausfuehrung")

    # --- Angebots-Editor ---
    await tab.oeffnen(f"/quotes/{seed['quote_a']}/edit", "quote&&existingOrder&&document.getElementById('orderButton').textContent")
    p.pruefe("Editor: Knopf öffnet den Auftrag", await tab.js("document.getElementById('orderButton').textContent"),
             await tab.js("`Auftrag ${existingOrder.order_number} öffnen`"))
    p.pruefe("Editor: Grund im Hinweis", "1 Entwurf" in (await tab.js("document.getElementById('orderSyncBanner').textContent")
                                                         or ""), True)
    await tab.bild("editor_gesperrt")

    # --- Einsatzbericht: Hinweis fürs Büro ---
    await tab.oeffnen(f"/orders/{gesperrt}/service-reports",
                      "typeof reports!=='undefined'&&reports.length>0&&document.querySelector('#reportList .report-card')")
    hinweis = await tab.js("document.querySelector('#reportList .office-hint')?.textContent||''")
    p.pruefe("Bericht Büro: Hinweis mit Fläche und Objekt", "„Dach Hof“" in hinweis and "„Wohnanlage Hof“" in hinweis, True)
    await tab.bild("bericht_hinweis")
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("bericht_hinweis_dunkel")
    p.pruefe("Büro: JS-Fehler", tab.fehler, [])

    # --- Einsatzbericht: Monteurin ohne Hinweis ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/orders/{gesperrt}/service-reports",
                      "typeof reports!=='undefined'&&reports.length>0&&document.querySelector('#reportList .report-card')")
    p.pruefe("Bericht Monteurin: kein Hinweis", await tab.js("document.querySelectorAll('.office-hint').length"), 0)
    p.pruefe("Bericht Monteurin: nichts vom fremden Objekt", "Hof" in (await tab.js("document.body.innerText") or ""), False)
    await tab.bild("bericht_monteurin")
    p.pruefe("Monteurin: JS-Fehler", tab.fehler, [])
    print(json.dumps({"gesperrt": gesperrt, "frei": frei}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
