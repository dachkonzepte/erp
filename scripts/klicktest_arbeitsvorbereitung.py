"""Klicktest: Speichern in der Arbeitsvorbereitung lässt nicht bearbeitete Werte stehen (1.8.29).

Bis 1.8.28 schickte work_preparation.html fest verdrahtete Werte mit (supplier:null, planned_hours:null,
sort_order:100), und der Server übernahm sie. Geprüft wird über die echte Seite als Admin:

    Material      Zeile mit eingetipptem Lieferanten (Freitext, kein Lieferanten-Datensatz): die Auswahl
                  zeigt ihn als "(Freitext)"; Menge ändern und speichern lässt ihn stehen;
                  "— kein Lieferant —" wählen und speichern leert ihn
    Mitarbeiter   Rolle ändern und speichern: Planstunden bleiben
    Aufgabe       Titel ändern und speichern: Reihenfolge bleibt

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_arbeitsvorbereitung.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

FREITEXT = "Dachbaustoffe Müller (telefonisch)"


def befuellen(db, k):
    from decimal import Decimal

    from app.models import (
        AppUser, Customer, Employee, Order, Project, Supplier, WorkPreparationEmployee, WorkPreparationMaterial,
        WorkPreparationTask,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    admin = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name="Kundin Klar", last_name="Klar")
    max_m = Employee(employee_number="M-1", first_name="Max", last_name="Monteur", employee_group="gewerblich",
                     weekly_hours=Decimal("40"), active=True)
    db.add_all([admin, kunde, max_m, Supplier(supplier_number="L-1", name="Bauder Nord", active=True)]); db.flush()
    projekt = Project(project_number="P-KT-1", name="Sanierung", customer_id=kunde.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AU-KT-0001", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-KT-1",
                    title="Dachsanierung", customer_name=kunde.name, vat_rate=Decimal("19"))
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    zuordnung = WorkPreparationEmployee(preparation_id=prep.id, employee_id=max_m.id, role="Vorarbeiter",
                                        planned_hours=Decimal("6"))
    material = WorkPreparationMaterial(preparation_id=prep.id, name="Bitumenbahn", unit="Rolle",
                                       planned_quantity=Decimal("10"), status="bedarf", supplier=FREITEXT)
    aufgabe = WorkPreparationTask(preparation_id=prep.id, title="Gerüst bestellen", status="offen",
                                  priority="normal", sort_order=30)
    db.add_all([zuordnung, material, aufgabe]); db.commit()
    return {"auftrag": auftrag.id, "zuordnung": zuordnung.id, "material": material.id, "aufgabe": aufgabe.id,
            "cookies": {"anna": k.cookies(admin)}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.fenster(1400, 900)
    m, z, a = seed["material"], seed["zuordnung"], seed["aufgabe"]
    av = f"fetch('/api/orders/{seed['auftrag']}/work-preparation').then(r=>r.json())"
    material = f"{av}.then(d=>d.materials.find(x=>x.id==={m}))"
    await tab.oeffnen(f"/orders/{seed['auftrag']}/work-preparation", f"prep&&document.getElementById('supplier-{m}')")

    auswahl = f"document.getElementById('supplier-{m}')"
    p.pruefe("Material: Auswahl zeigt den Freitext-Lieferanten vorgewählt",
             await tab.js(f"[{auswahl}.value,{auswahl}.selectedOptions[0].textContent]"),
             ["freitext", f"{FREITEXT} (Freitext)"])
    await tab.js(f"document.getElementById('mqty-{m}').value='12';saveMaterial({m})")
    await tab.warten(f"Number(prep.materials.find(x=>x.id==={m}).planned_quantity)===12")
    p.pruefe("Material: Menge speichern lässt den Freitext-Lieferanten stehen",
             await tab.js(f"{material}.then(x=>[Number(x.planned_quantity),x.supplier,x.supplier_id])"),
             [12, FREITEXT, None])
    await tab.js(f"{auswahl}.value='';saveMaterial({m})")
    await tab.warten(f"prep.materials.find(x=>x.id==={m}).supplier===null")
    p.pruefe("Material: '— kein Lieferant —' speichern leert ihn",
             await tab.js(f"{material}.then(x=>[x.supplier,x.supplier_id])"), [None, None])

    await tab.js(f"document.getElementById('role-{z}').value='Kolonnenführer';saveEmployee({z})")
    await tab.warten(f"prep.employees.find(x=>x.id==={z}).role==='Kolonnenführer'")
    p.pruefe("Mitarbeiter: Rolle speichern lässt die Planstunden stehen",
             await tab.js(f"{av}.then(d=>d.employees.find(x=>x.id==={z})).then(x=>[x.role,Number(x.planned_hours)])"),
             ["Kolonnenführer", 6])

    await tab.js(f"document.getElementById('ttitle-{a}').value='Gerüst bestellen bei Firma Hoch';saveTask({a})")
    await tab.warten(f"prep.tasks.find(x=>x.id==={a}).title.includes('Hoch')")
    p.pruefe("Aufgabe: Titel speichern lässt die Reihenfolge stehen",
             await tab.js(f"{av}.then(d=>d.tasks.find(x=>x.id==={a})).then(x=>[x.title,x.sort_order])"),
             ["Gerüst bestellen bei Firma Hoch", 30])
    p.pruefe("Arbeitsvorbereitung: JS-Fehler", tab.fehler, [])
    await tab.bild("arbeitsvorbereitung")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
