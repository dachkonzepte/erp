"""Klicktest: Auswahllisten behalten einen inaktiven gespeicherten Wert (1.8.30).

Bis 1.8.29 boten viele Auswahllisten nur aktive Einträge an. War der gespeicherte Eintrag inzwischen
inaktiv, stand das Feld leer, und das nächste Speichern schrieb das (beim Sachbearbeiter des Auftrags
lehnte der Server außerdem ab). Geprüft wird über die echten Seiten als Admin, mit einer ausgeschiedenen
Mitarbeiterin (Erika), einem inaktiven Lieferanten und einem archivierten Projekt:

    Auftrag              Sachbearbeiter und Projektleiter zeigen "Erika ... (inaktiv)"; Speichern behält sie
    Aufgaben-Editor      Zuständige und archiviertes Projekt vorgewählt und gekennzeichnet; Speichern behält beide
    Arbeitsvorbereitung  Aufgabe mit Erika und Materialzeile mit inaktivem Lieferanten lassen sich speichern

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_auswahl_inaktiv.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from decimal import Decimal

    from app.models import (
        AppUser, Customer, Employee, EmployeeRoleSettings, Order, Project, Supplier, Task, WorkPreparationMaterial,
        WorkPreparationMaterialSupplier, WorkPreparationTask,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    admin = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name="Kundin Klar", last_name="Klar")
    erika = Employee(employee_number="E-1", first_name="Erika", last_name="Ehemalig", employee_group="angestellt",
                     weekly_hours=Decimal("40"), active=True)
    otto = Employee(employee_number="E-2", first_name="Otto", last_name="Offen", employee_group="angestellt",
                    weekly_hours=Decimal("40"), active=True)
    lieferant = Supplier(supplier_number="L-9", name="Altlieferant", active=True)
    db.add_all([admin, kunde, erika, otto, lieferant]); db.flush()
    db.add_all([EmployeeRoleSettings(employee_id=erika.id, available_as_caseworker=True),
                EmployeeRoleSettings(employee_id=otto.id, available_as_caseworker=True)])
    projekt = Project(project_number="P-KT-1", name="Sanierung", customer_id=kunde.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    archiv = Project(project_number="P-KT-0", name="Altprojekt", customer_id=kunde.id, archived=True,
                     pipeline_column_id=default_pipeline_column_id(db))
    db.add_all([projekt, archiv]); db.flush()
    auftrag = Order(order_number="AU-KT-0001", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-KT-1",
                    title="Dachsanierung", customer_name=kunde.name, vat_rate=Decimal("19"),
                    caseworker_employee_id=erika.id, project_manager_employee_id=erika.id)
    aufgabe = Task(title="Rückruf Kundin", assigned_employee_id=erika.id, project_id=archiv.id)
    db.add_all([auftrag, aufgabe]); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    av_aufgabe = WorkPreparationTask(preparation_id=prep.id, title="Kran bestellen", assigned_employee_id=erika.id)
    material = WorkPreparationMaterial(preparation_id=prep.id, name="Blech", unit="m", status="bedarf",
                                       planned_quantity=Decimal("1"), supplier=lieferant.name)
    db.add_all([av_aufgabe, material]); db.flush()
    db.add(WorkPreparationMaterialSupplier(material_id=material.id, supplier_id=lieferant.id))
    erika.active = lieferant.active = False      # nach der Zuordnung ausgeschieden bzw. abgeschaltet
    db.commit()
    return {"auftrag": auftrag.id, "aufgabe": aufgabe.id, "archiv": archiv.id, "erika": erika.id,
            "av_aufgabe": av_aufgabe.id, "material": material.id, "lieferant": lieferant.id,
            "cookies": {"anna": k.cookies(admin)}}


# Projektleiter-Liste und Arbeitsvorbereitung nennen die Funktion mit (Vorgabe aus ensure_employee_profiles()).
MIT_FUNKTION = "Erika Ehemalig · Kaufmännischer Mitarbeiter (inaktiv)"


def _gewaehlt(select_id: str) -> str:
    return f"(s=>[s.value,s.selectedOptions[0]?.textContent])(document.getElementById('{select_id}'))"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.fenster(1400, 900)
    erika = str(seed["erika"])

    # --- Auftrag ---------------------------------------------------------------------------
    await tab.oeffnen(f"/orders/{seed['auftrag']}", "order&&document.getElementById('caseworker').options.length>1")
    p.pruefe("Auftrag: Sachbearbeiter vorgewählt und gekennzeichnet", await tab.js(_gewaehlt("caseworker")),
             [erika, "Erika Ehemalig (inaktiv)"])
    p.pruefe("Auftrag: Projektleiter vorgewählt und gekennzeichnet", await tab.js(_gewaehlt("manager")),
             [erika, MIT_FUNKTION])
    await tab.js("document.getElementById('remarks').value='Gerüst steht';saveOrder()")
    await tab.warten("document.getElementById('saveStatus').textContent!=='Speichert …'")
    p.pruefe("Auftrag: Speichern gelingt", await tab.js("document.getElementById('saveStatus').textContent"),
             "Auftragsdaten gespeichert.")
    p.pruefe("Auftrag: Sachbearbeiter und Projektleiter bleiben",
             await tab.js(f"fetch('/api/orders/{seed['auftrag']}').then(r=>r.json())"
                          ".then(o=>[o.caseworker_employee_id,o.project_manager_employee_id,o.remarks])"),
             [seed["erika"], seed["erika"], "Gerüst steht"])
    p.pruefe("Auftrag: JS-Fehler", tab.fehler, [])

    # --- Aufgaben-Editor ---------------------------------------------------------------------
    await tab.oeffnen("/tasks", f"typeof findTask==='function'&&findTask({seed['aufgabe']})")
    await tab.js(f"openEditor({seed['aufgabe']})")
    p.pruefe("Aufgabe: Zuständige vorgewählt und gekennzeichnet", await tab.js(_gewaehlt("editEmployee")),
             [erika, "Erika Ehemalig (inaktiv)"])
    p.pruefe("Aufgabe: archiviertes Projekt vorgewählt und gekennzeichnet", await tab.js(_gewaehlt("editProject")),
             [str(seed["archiv"]), "P-KT-0 · Altprojekt (inaktiv)"])
    await tab.js("document.getElementById('editPriority').value='hoch';saveTask()")
    await tab.warten("document.getElementById('editorCard').classList.contains('hidden')")
    p.pruefe("Aufgabe: Speichern behält Zuständige und Projekt",
             await tab.js("fetch('/api/tasks?include_archived=true').then(r=>r.json())"
                          f".then(l=>l.find(t=>t.id==={seed['aufgabe']})).then(t=>[t.priority,t.assigned_employee_id,t.project_id])"),
             ["hoch", seed["erika"], seed["archiv"]])
    p.pruefe("Aufgaben: JS-Fehler", tab.fehler, [])

    # --- Arbeitsvorbereitung ------------------------------------------------------------------
    a, m = seed["av_aufgabe"], seed["material"]
    av = f"fetch('/api/orders/{seed['auftrag']}/work-preparation').then(r=>r.json())"
    await tab.oeffnen(f"/orders/{seed['auftrag']}/work-preparation", f"prep&&document.getElementById('temp-{a}')")
    p.pruefe("AV: Aufgaben-Zuständige vorgewählt und gekennzeichnet", await tab.js(_gewaehlt(f"temp-{a}")),
             [erika, MIT_FUNKTION])
    p.pruefe("AV: Lieferant vorgewählt und gekennzeichnet", await tab.js(_gewaehlt(f"supplier-{m}")),
             [str(seed["lieferant"]), "L-9 · Altlieferant (inaktiv)"])
    await tab.js(f"document.getElementById('ttitle-{a}').value='Kran bestellen (50 t)';saveTask({a})")
    await tab.warten(f"prep.tasks.find(x=>x.id==={a}).title.includes('50 t')")
    await tab.js(f"document.getElementById('mqty-{m}').value='7';saveMaterial({m})")
    await tab.warten(f"Number(prep.materials.find(x=>x.id==={m}).planned_quantity)===7")
    p.pruefe("AV: Speichern behält Zuständige und Lieferant",
             await tab.js(f"{av}.then(d=>[d.tasks.find(x=>x.id==={a}).assigned_employee_id,"
                          f"d.materials.find(x=>x.id==={m}).supplier_id,Number(d.materials.find(x=>x.id==={m}).planned_quantity)])"),
             [seed["erika"], seed["lieferant"], 7])
    p.pruefe("Arbeitsvorbereitung: JS-Fehler", tab.fehler, [])
    await tab.bild("arbeitsvorbereitung_inaktiv")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
