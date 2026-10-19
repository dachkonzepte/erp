"""Klicktest: Dachflächen-Auswahl im Einsatzbericht für Monteure (1.8.22).

GET /api/orders/{order_id}/roof-areas liefert einem Monteur seit 1.8.22 nur noch
id/name/roof_type/covering/pitch_degrees/area_sqm. Geprüft wird, dass die Berichtsseite damit
weiter funktioniert, so wie der Monteur sie sieht:

    Berichtsseite      die Dachfläche kommt ohne Notiz, Fremdfirma, Gewährleistung, Kunden-ID an
    Bericht anlegen    die Fläche steht in der Auswahl, ein Wartungsbericht mit ihr entsteht und
                       trägt sie (Prüfpunkte aus der Vorlage des Dachtyps)

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_monteur_dachflaechen.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.inspection_templates import create_template, create_template_item, set_roof_type_template_default
    from app.models import (
        AppUser, Customer, Employee, Order, OrderItem, Project, Property, RoofArea, WorkPreparationEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    max_m = Employee(employee_number="M-1", first_name="Max", last_name="Monteur", employee_group="angestellt",
                     hourly_wage=Decimal("31.50"), weekly_hours=Decimal("40"), active=True)
    db.add(max_m); db.flush()
    monteur = AppUser(username="max", display_name="Max Monteur", role="field", employee_id=max_m.id,
                      password_hash=k.passwort())
    kunde = Customer(name="Kundin Klar", last_name="Klar", email="kundin@example.org")
    db.add_all([monteur, kunde]); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Süd", street="Werkstr. 5", postal_code="22222", city="Objektstadt")
    db.add(objekt); db.flush()
    db.add(RoofArea(property_id=objekt.id, name="Hauptdach", roof_type="flachdach", covering="Bitumen",
                    area_sqm=Decimal("850"), contractor="Fremdfirma GmbH", third_party_guarantee_until=date(2031, 5, 1),
                    notes="Gewährleistungsstreit"))
    projekt = Project(project_number="P-KT-1", name="Sanierung", customer_id=kunde.id, property_id=objekt.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AU-KT-0001", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-KT-1",
                    title="Dachsanierung", customer_name=kunde.name, property_name=objekt.name)
    db.add(auftrag); db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Abdichtung",
                     quantity=Decimal("850"), unit="m²", unit_price=Decimal("48.90")))
    db.commit()
    db.add(WorkPreparationEmployee(preparation_id=ensure_preparation(db, auftrag.id).id, employee_id=max_m.id))
    vorlage = create_template(db, "Flachdach-Wartung", roof_type="flachdach")
    create_template_item(db, vorlage["id"], "Abdichtung Sichtprüfung", "ja_nein")
    set_roof_type_template_default(db, "flachdach", vorlage["id"])
    db.commit()
    # seit 1.8.152: Büro und Admin für die Auswahl "Mitarbeiter" beim Zeit buchen
    bea_m = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="angestellt", active=True)
    db.add(bea_m); db.flush()
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_finanzen", employee_id=bea_m.id, password_hash=k.passwort())
    ada = AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort())
    db.add_all([bea, ada]); db.commit()
    return {"auftrag": auftrag.id, "cookies": {"monteur": k.cookies(monteur), "buero": k.cookies(bea), "admin": k.cookies(ada)}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["monteur"])
    auftrag = seed["auftrag"]

    await tab.oeffnen(f"/orders/{auftrag}/service-reports", "roofAreasForOrder.length===1&&document.getElementById('reportList')")
    p.pruefe("Dachfläche: nur die Monteursfelder",
             await tab.js("Object.keys(roofAreasForOrder[0]).sort().join(',')"),
             "area_sqm,covering,id,name,pitch_degrees,roof_type")

    await tab.js("openCreateEditor()")
    p.pruefe("Auswahl sichtbar", await tab.js("!document.getElementById('editRoofAreaField').classList.contains('hidden')"), True)
    p.pruefe("Auswahl nennt die Fläche", await tab.js("document.getElementById('editRoofAreaChecks').textContent.trim()"), "Hauptdach")
    await tab.bild("bericht_anlegen")

    await tab.js("document.getElementById('editType').value='wartung';"
                 "document.querySelector('#editRoofAreaChecks input').checked=true;onEditRoofAreaChange();saveReport()")
    await tab.warten("reports.length===1")
    p.pruefe("Bericht mit Fläche angelegt", await tab.js("reports[0].roof_areas.map(a=>a.roof_area_name).join(',')"), "Hauptdach")
    p.pruefe("Prüfpunkte aus der Vorlage",
             await tab.js(f"fetch('/api/service-reports/'+reports[0].id+'/inspection-items').then(r=>r.json()).then(j=>j.map(i=>i.text).join(','))"),
             "Abdichtung Sichtprüfung")
    await tab.bild("bericht_angelegt")

    # Seit 1.8.143: Zeit buchen ohne Auswahl "Mitarbeiter" -- der Monteur bucht für sich
    p.pruefe("Zeit buchen: Feld Mitarbeiter verborgen",
             await tab.js("getComputedStyle(document.getElementById('teEmployeeField')).display"), "none")
    p.pruefe("Zeit buchen: nur die eigene Person",
             await tab.js("[...document.getElementById('teEmployee').options].map(o=>o.textContent).join('|')"), "Max Monteur")
    await tab.js("document.getElementById('teHours').value='2,5'")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('button[onclick=\"saveReportTimeEntry()\"]').click()",
                                           "#timeEntriesTable")
    p.pruefe("Zeit buchen: gebucht", await tab.js("document.getElementById('teStatus').textContent"), "Gebucht.")
    p.pruefe("Zeit buchen: für sich", await tab.js(
        f"fetch('/api/time-entries?order_id={auftrag}').then(r=>r.json()).then(j=>j.map(e=>e.employee_name+' '+Number(e.hours)).join('|'))"),
        "Max Monteur 2.5")
    p.pruefe("JS-Fehler", tab.fehler, [])
    await tab.bild("zeit_gebucht")

    # Seit 1.8.152: die Auswahl nur, wer laut Server für andere bucht (heute Admin); das Büro bucht für sich wie der Monteur
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.oeffnen(f"/orders/{auftrag}/service-reports", "document.getElementById('teEmployee').options.length>0")
    p.pruefe("Büro: Feld Mitarbeiter verborgen", await tab.js("getComputedStyle(document.getElementById('teEmployeeField')).display"), "none")
    p.pruefe("Büro: nur die eigene Person",
             await tab.js("[...document.getElementById('teEmployee').options].map(o=>o.textContent).join('|')"), "Bea Büro")
    await tab.js("document.getElementById('teHours').value='1'")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('button[onclick=\"saveReportTimeEntry()\"]').click()",
                                           "#timeEntriesTable")
    p.pruefe("Büro: gebucht für sich", await tab.js(
        f"fetch('/api/time-entries?order_id={auftrag}').then(r=>r.json()).then(j=>j.map(e=>e.employee_name).sort().join('|'))"),
        "Bea Büro|Max Monteur")
    await tab.anmelden(seed["cookies"]["admin"])
    await tab.oeffnen(f"/orders/{auftrag}/service-reports", "document.getElementById('teEmployee').options.length>1")
    p.pruefe("Admin: Auswahl sichtbar", await tab.js("getComputedStyle(document.getElementById('teEmployeeField')).display")!="none", True)
    p.pruefe("Admin: alle aktiven zur Wahl",
             await tab.js("[...document.getElementById('teEmployee').options].map(o=>o.textContent).join('|')"),
             "— nicht zugeordnet —|Bea Büro|Max Monteur")
    p.pruefe("JS-Fehler (Büro, Admin)", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
