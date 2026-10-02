"""Klicktest: Speichern auf vier Seiten lässt Felder stehen, die die Seite nicht bearbeitet (1.8.25).

Bis 1.8.24 übernahm der Server jedes Feld eines PUT, auch ein nicht gesendetes (dann mit seinem
Vorgabewert), und einige Seiten schickten Werte mit, die sie gar nicht bearbeiten. Geprüft wird über
die echten Seiten:

    Zeiterfassung (Monteur)   Buchung ändern: Pause und LV-Position bleiben, die Notiz ändert sich;
                              Kolonnenbuchung ändern (Kolonnenführer): dasselbe
    Einstellungen (Admin)     Unternehmensstammdaten speichern, dann Logohöhe übernehmen: die neue
                              Telefonnummer bleibt, die Höhe kommt an; noch einmal Stammdaten
                              speichern: die Höhe bleibt
    Rechnung (Admin)          Pauschale speichern: Schlusstext 2, Einleitung, Frist bleiben
    Leistung (Admin)          Leistung speichern: die interne Kalkulationsnotiz bleibt

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_teil_updates.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

SCHLUSS_2 = "Bitte die neue Bankverbindung beachten."
KALK_NOTIZ = "Nur mit Gerüst kalkuliert"


def befuellen(db, k):
    from datetime import timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.invoices import create_abschlag_pauschal
    from app.labor_rate import load_labor_rate_settings
    from app.models import (
        AppUser, Customer, Employee, ImportBatch, Order, OrderItem, Project, Service, ServiceCalculation, Team,
        TeamEmployee, WorkPreparationEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.settings import load_general_settings
    from app.time_backoffice import load_time_settings
    from app.time_tracking import create_group_manual_entry, create_manual_entry
    from app.work_preparation import ensure_preparation

    load_labor_rate_settings(db)  # Singleton vorab: sonst rennen /settings-Abrufe beim ersten Zugriff
    heute = berlin_today()
    max_m = Employee(employee_number="M-1", first_name="Max", last_name="Kolonne", employee_group="gewerblich",
                     weekly_hours=Decimal("40"), active=True)
    moritz = Employee(employee_number="M-2", first_name="Moritz", last_name="Mitglied", employee_group="gewerblich",
                      weekly_hours=Decimal("40"), active=True)
    db.add_all([max_m, moritz]); db.flush()
    monteur = AppUser(username="max", display_name="Max", role="field", employee_id=max_m.id, password_hash=k.passwort())
    admin = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name="Kundin Klar", last_name="Klar")
    team = Team(name="Kolonne Nord")
    db.add_all([monteur, admin, kunde, team]); db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=max_m.id, is_crew_leader=True),
                TeamEmployee(team_id=team.id, employee_id=moritz.id)])
    projekt = Project(project_number="P-KT-1", name="Sanierung", customer_id=kunde.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AU-KT-0001", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-KT-1",
                    title="Dachsanierung", customer_name=kunde.name, vat_rate=Decimal("19"))
    db.add(auftrag); db.flush()
    position = OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Abdichtung",
                         quantity=Decimal("100"), unit="m²", unit_price=Decimal("50"))
    db.add(position); db.commit()
    vorbereitung = ensure_preparation(db, auftrag.id)
    vorbereitung.planned_start, vorbereitung.planned_end = heute, heute
    db.add_all([WorkPreparationEmployee(preparation_id=vorbereitung.id, employee_id=max_m.id),
                WorkPreparationEmployee(preparation_id=vorbereitung.id, employee_id=moritz.id)])
    load_time_settings(db).default_break_minutes = 30
    db.commit()

    einzeln = create_manual_entry(db, employee_id=max_m.id, order_id=auftrag.id, order_item_id=position.id,
                                  work_date=heute, hours=Decimal("4"), break_minutes=45, notes="alt")
    gruppe = create_group_manual_entry(db, employee_ids=[max_m.id, moritz.id], team_id=team.id,
                                       actor_employee_id=max_m.id, is_admin=False, order_id=auftrag.id,
                                       work_date=heute, hours=Decimal("8"), order_item_id=position.id,
                                       break_minutes=45, notes="Kolonne alt")

    allgemein = load_general_settings(db)
    allgemein.company_name, allgemein.phone, allgemein.sidebar_logo_height_px = "DACHKONZEPTE GmbH", "040 1", 48
    rechnung = create_abschlag_pauschal(db, auftrag, lump_sum_net=Decimal("3000"), progress_description="1. Abschlag")
    rechnung.intro_text, rechnung.outro_text_2 = "Einleitung bleibt", SCHLUSS_2
    rechnung.payment_terms, rechnung.due_date = "14 Tage netto", heute + timedelta(days=14)
    batch = ImportBatch(source_type="manuell", source_name="Manuell", filename="-")
    db.add(batch); db.flush()
    leistung = Service(import_batch_id=batch.id, source_type="manuell", external_id="M-KT-1", short_text="Rinne reinigen",
                       quantity=Decimal("1"), unit="m", site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"),
                       sale_price=Decimal("10"))
    db.add(leistung); db.flush()
    db.add(ServiceCalculation(service_id=leistung.id, notes=KALK_NOTIZ, site_time_minutes=Decimal("10")))
    db.commit()
    return {"einzeln": einzeln.id, "gruppe": gruppe.id, "position": position.id, "rechnung": rechnung.id,
            "leistung": leistung.id, "cookies": {"max": k.cookies(monteur), "anna": k.cookies(admin)}}


def _api(pfad: str) -> str:
    return f"fetch('{pfad}').then(r=>r.json())"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")

    # --- Monteur: Buchung und Kolonnenbuchung ändern ---------------------------------------
    await tab.anmelden(seed["cookies"]["max"])
    await tab.fenster(430, 900, mobil=True)
    await tab.oeffnen("/time-tracking", "allEntries.length>=2&&crewGroups.length===1&&orders.length===1")
    meine = f"{_api('/api/time-entries')}.then(l=>l.find(e=>e.id==={seed['einzeln']}))"
    await tab.js(f"editEntry({seed['einzeln']});$('manualNotes').value='Rinne gereinigt';saveManual()")
    await tab.warten("!manualDialog.open")
    eintrag = await tab.js(f"{meine}.then(e=>[e.notes,e.break_minutes,e.order_item_id])")
    p.pruefe("Buchung ändern: Notiz neu, Pause und LV-Position unverändert", eintrag,
             ["Rinne gereinigt", 45, seed["position"]])

    kolonne = f"{_api('/api/time-entry-groups/mine')}.then(l=>l.find(g=>g.id==={seed['gruppe']}))"
    await tab.js(f"openCrewDialog({seed['gruppe']});$('crewDialogNotes').value='Kolonne neu';saveCrewDialog()")
    await tab.warten("$('crewStatus').textContent.includes('Korrektur gespeichert')")
    gruppe = await tab.js(f"{kolonne}.then(g=>[g.notes,g.break_minutes,g.order_item_id])")
    p.pruefe("Kolonnenbuchung ändern: Notiz neu, Pause und LV-Position unverändert", gruppe,
             ["Kolonne neu", 45, seed["position"]])
    p.pruefe("Monteur: JS-Fehler", tab.fehler, [])
    await tab.bild("zeiterfassung_monteur")

    # --- Admin: Einstellungen, Rechnung, Leistung ------------------------------------------
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.fenster(1400, 900)
    allgemein = _api("/api/settings/general")
    await tab.oeffnen("/settings", "generalSettings&&document.getElementById('companyPhone').value==='040 1'")
    await tab.js("document.getElementById('companyPhone').value='040 2';saveGeneral()")
    await tab.warten("document.getElementById('generalStatus').textContent.includes('gespeichert')")
    await tab.js("document.getElementById('sidebarLogoHeight').value='72';saveLogoHeight()")
    await tab.warten("document.getElementById('sidebarLogoStatus').textContent==='Gespeichert.'")
    p.pruefe("Logohöhe übernehmen: Höhe neu, Telefon aus den Stammdaten bleibt",
             await tab.js(f"{allgemein}.then(g=>[g.sidebar_logo_height_px,g.phone])"), [72, "040 2"])
    await tab.js("document.getElementById('generalStatus').textContent='';saveGeneral()")
    await tab.warten("document.getElementById('generalStatus').textContent.includes('gespeichert')")
    p.pruefe("Stammdaten speichern: Logohöhe bleibt",
             await tab.js(f"{allgemein}.then(g=>g.sidebar_logo_height_px)"), 72)
    p.pruefe("Einstellungen: JS-Fehler", tab.fehler, [])

    rechnung = _api(f"/api/invoices/{seed['rechnung']}")
    await tab.oeffnen(f"/invoices/{seed['rechnung']}", "invoice&&document.getElementById('pAmount')")
    await tab.js("document.getElementById('pAmount').value='4500';document.getElementById('pDesc').value='2. Abschlag';"
                 "savePauschal()")
    await tab.warten("document.getElementById('pauschalStatus').textContent==='Gespeichert.'")
    p.pruefe("Pauschale speichern: Betrag neu, Schlusstext 2/Einleitung/Zahlungsbedingung bleiben",
             await tab.js(f"{rechnung}.then(r=>[Number(r.lump_sum_net),r.outro_text_2,r.intro_text,r.payment_terms])"),
             [4500, SCHLUSS_2, "Einleitung bleibt", "14 Tage netto"])
    p.pruefe("Rechnung: JS-Fehler", tab.fehler, [])
    await tab.bild("rechnung_pauschale")

    leistung = seed["leistung"]
    await tab.oeffnen(f"/services/{leistung}/edit", "currentService&&document.getElementById('shortText').value")
    await tab.js("document.getElementById('shortText').value='Rinne reinigen und prüfen';save()")
    await tab.warten("location.pathname==='/leistungskatalog'")
    p.pruefe("Leistung speichern: Kalkulationsnotiz bleibt",
             await tab.js(f"{_api(f'/api/services/{leistung}/calculation')}.then(c=>c.notes)"), KALK_NOTIZ)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
