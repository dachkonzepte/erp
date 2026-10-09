"""Klicktest: Objekt eines anderen Kunden mit Hinweis und Bestätigung, Wartungshistorie in /mobil (1.8.70).

Befund „Vor dem Echtbetrieb“ Punkt 2 (docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.70"):

    Schnellauftrag     Objekt-Auswahl zeigt nur Objekte des Kunden; "Objekte anderer Kunden anzeigen" ergänzt die übrigen,
                       ein fremdes Objekt zeigt den Hinweis mit Häkchen -- ohne Häkchen geht nichts hinaus (und die API
                       antwortet 409), mit Häkchen entsteht der Auftrag für den Kunden am Objekt der Hausverwaltung
    Vertrag anlegen    dasselbe im Editor "Wartungsvertrag anlegen"
    Vertragsseite      das gespeicherte fremde Objekt bleibt vorgewählt ("bestätigt"), unverändert speichern geht ohne
                       Rückfrage; zurück zum eigenen Objekt und wieder zum fremden verlangt die Bestätigung erneut
    /mobil             Wartungshistorie am Objekt des eigenen Auftrags, am fremden Objekt ein ruhiger Hinweis (403), kein
                       Fehler; Objektansicht selbst bleibt offen

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_objekt_anderer_kunde.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00 (öffnet /mobil als Monteur).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from decimal import Decimal

    from app.models import (
        AppUser, Customer, Employee, Order, OrderItem, Project, Property, RoofArea, ServiceReport, WorkPreparationEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report
    from app.work_preparation import ensure_preparation

    mona = Employee(employee_number="M-1", first_name="Mona", last_name="Monteurin", employee_group="angestellt",
                    hourly_wage=Decimal("30"), weekly_hours=Decimal("40"), active=True)
    db.add(mona); db.flush()
    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    monteurin = AppUser(username="mona", display_name="Mona Monteurin", role="field", employee_id=mona.id,
                        password_hash=k.passwort())
    kunde = Customer(name="Bauherr Klar", last_name="Klar")
    hv = Customer(name="Hausverwaltung Hof", last_name="Hof")
    db.add_all([buero, monteurin, kunde, hv]); db.flush()
    halle = Property(customer_id=kunde.id, name="Halle Süd", street="Werkstr. 5", city="Objektstadt")
    hof = Property(customer_id=hv.id, name="Wohnanlage Hof", street="Hofweg 1", city="Objektstadt")
    db.add_all([halle, hof]); db.flush()
    db.add_all([RoofArea(property_id=halle.id, name="Hauptdach", roof_type="flachdach"),
                RoofArea(property_id=hof.id, name="Dach Hof", roof_type="flachdach")])

    def auftrag(nummer, kd, objekt, quelle):
        projekt = Project(project_number=f"P-{nummer}", name=f"Projekt {nummer}", customer_id=kd.id, property_id=objekt.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        o = Order(order_number=f"AU-{nummer}", project_id=projekt.id, source_quote_id=quelle,
                  quote_number_snapshot=f"A-{nummer}", title=f"Auftrag {nummer}", customer_name=kd.name,
                  property_name=objekt.name)
        db.add(o); db.flush()
        db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Wartung",
                         quantity=Decimal("1"), unit="psch", unit_price=Decimal("0")))
        db.commit()
        return o

    eigener = auftrag("KT-1", kunde, halle, 900001)
    fremder = auftrag("KT-2", hv, hof, 900002)
    db.add(WorkPreparationEmployee(preparation_id=ensure_preparation(db, eigener.id).id, employee_id=mona.id))
    for o in (eigener, fremder):
        r = create_report(db, o.id, "rapport", description="Kontrolle")
        db.get(ServiceReport, r["id"]).status = "unterschrieben"
    db.commit()
    return {"kunde": kunde.id, "halle": halle.id, "hof": hof.id,
            "cookies": {"buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


def _optionen(sel_id):
    return f"[...document.getElementById('{sel_id}').options].map(o=>o.textContent)"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.fenster(1280, 1000)
    await tab.anmelden(seed["cookies"]["buero"])
    kunde, halle, hof = seed["kunde"], seed["halle"], seed["hof"]

    # --- Schnellauftrag ---
    await tab.oeffnen("/maintenance-contracts", "customers.length>0&&document.getElementById('qsoCustomer').options.length>1")
    await tab.js(f"document.getElementById('qsoCustomer').value='{kunde}';onQsoCustomerChange()")
    p.pruefe("Schnellauftrag: nur Objekte des Kunden", await tab.js(_optionen("qsoProperty")),
             ["— Hauptadresse verwenden —", "Halle Süd"])
    await tab.js("document.getElementById('qsoOtherOwners').checked=true;onQsoCustomerChange(true)")
    p.pruefe("Schnellauftrag: mit anderen Kunden", "Wohnanlage Hof – Hausverwaltung Hof" in (await tab.js(_optionen("qsoProperty")) or []), True)
    await tab.js(f"const s=document.getElementById('qsoProperty');s.value='{hof}';s.dispatchEvent(new Event('change'))")
    hinweis = await tab.js("document.querySelector('#qsoMismatch [data-objekt-abweichung]')?.textContent||''")
    p.pruefe("Schnellauftrag: Hinweis nennt beide", "Hausverwaltung Hof" in hinweis and "Bauherr Klar" in hinweis, True)
    await tab.bild("schnellauftrag_hinweis")
    projekte_vorher = await tab.js("fetch('/api/projects').then(r=>r.json()).then(j=>j.length)")
    await tab.js("document.getElementById('qsoTitle').value='Rinne undicht';saveQuickServiceOrder()")
    p.pruefe("Schnellauftrag: ohne Häkchen gesperrt", await tab.js("document.getElementById('qsoStatus').textContent"),
             "Bitte zuerst die Abweichung beim Objekt prüfen und bestätigen.")
    api_ohne = await tab.js(
        "fetch('/api/quick-service-orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify("
        f"{{customer_id:{kunde},property_id:{hof},order_type:'reparatur',title:'API'}})}}).then(r=>r.status)")
    p.pruefe("Schnellauftrag: API ohne Bestätigung 409", api_ohne, 409)
    p.pruefe("Schnellauftrag: nichts angelegt", await tab.js("fetch('/api/projects').then(r=>r.json()).then(j=>j.length)"),
             projekte_vorher)
    await tab.js("document.getElementById('qsoConfirmProperty').checked=true;saveQuickServiceOrder()")
    p.pruefe("Schnellauftrag: zum Auftrag gewechselt", await tab.warten("location.pathname.startsWith('/orders/')"), True)
    order_id = await tab.js("Number(location.pathname.split('/')[2])")
    projekt = await tab.js(f"fetch('/api/orders/{order_id}').then(r=>r.json()).then(o=>fetch('/api/projects/'+o.project_id)).then(r=>r.json())")
    p.pruefe("Schnellauftrag: Kunde und Objekt", [projekt.get("customer_id"), projekt.get("property_id")] if projekt else None,
             [kunde, hof])

    # --- Wartungsvertrag anlegen ---
    await tab.oeffnen("/maintenance-contracts", "customers.length>0&&document.getElementById('qsoCustomer').options.length>1")
    await tab.js(f"openCreateEditor();document.getElementById('editCustomer').value='{kunde}';onCustomerChange();"
                 "document.getElementById('editOtherOwners').checked=true;onCustomerChange(true);"
                 f"const s=document.getElementById('editProperty');s.value='{hof}';s.dispatchEvent(new Event('change'));"
                 "document.getElementById('editTitle').value='GU-Wartung';document.getElementById('editDueDate').value='2027-03-01';")
    await tab.js("saveContract()")
    p.pruefe("Vertrag: ohne Häkchen gesperrt", await tab.js("document.getElementById('editorStatus').textContent"),
             "Bitte zuerst die Abweichung beim Objekt prüfen und bestätigen.")
    await tab.js("document.getElementById('editConfirmProperty').checked=true;saveContract()")
    p.pruefe("Vertrag: zur Vertragsseite", await tab.warten("location.pathname.startsWith('/maintenance-contracts/')"), True)

    # --- Vertragsseite ---
    vertrag_id = await tab.js("Number(location.pathname.split('/')[2])")
    await tab.oeffnen(f"/maintenance-contracts/{vertrag_id}",
                      "contract&&customers.length>0&&document.getElementById('editProperty').options.length>1")
    p.pruefe("Vertragsseite: fremdes Objekt vorgewählt", await tab.js("Number(document.getElementById('editProperty').value)"), hof)
    p.pruefe("Vertragsseite: Vermerk bestätigt", await tab.js("document.querySelector('[data-objekt-anderer-kunde]')?.textContent||''"),
             "Objekt von Hausverwaltung Hof – bestätigt.")
    await tab.js("document.getElementById('editNotes').value='unverändert gespeichert';saveContractDetail()")
    p.pruefe("Vertragsseite: unverändert speichern ohne Rückfrage",
             await tab.warten("document.getElementById('editorStatus').textContent==='Gespeichert.'"), True)
    await tab.js(f"const s=document.getElementById('editProperty');s.value='{halle}';s.dispatchEvent(new Event('change'));saveContractDetail()")
    await tab.warten("contract.property_id===" + str(halle))
    p.pruefe("Vertragsseite: eigenes Objekt ohne Hinweis", await tab.js("document.getElementById('editMismatch').textContent.trim()"), "")
    await tab.js("document.getElementById('editOtherOwners').checked=true;renderPropertyOptions();"
                 f"const t=document.getElementById('editProperty');t.value='{hof}';t.dispatchEvent(new Event('change'));saveContractDetail()")
    p.pruefe("Vertragsseite: neu gewählt -> Bestätigung nötig", await tab.js("document.getElementById('editorStatus').textContent"),
             "Bitte zuerst die Abweichung beim Objekt prüfen und bestätigen.")
    await tab.bild("vertrag_hinweis")
    await tab.js("document.getElementById('editConfirmProperty').checked=true;saveContractDetail()")
    p.pruefe("Vertragsseite: mit Häkchen gespeichert", await tab.warten(f"contract.property_id==={hof}"), True)
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("vertrag_dunkel")
    p.pruefe("Büro: JS-Fehler", tab.fehler, [])

    # --- /mobil: Wartungshistorie ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/mobil/objekt/{halle}", "document.getElementById('historyList').className!=='loading'")
    p.pruefe("/mobil eigenes Objekt: Historie", await tab.js("document.querySelectorAll('#historyList .history-item').length"), 1)
    await tab.oeffnen(f"/mobil/objekt/{hof}", "document.getElementById('historyList').className!=='loading'")
    p.pruefe("/mobil fremdes Objekt: ruhiger Hinweis",
             await tab.js("[document.getElementById('historyList').className,document.getElementById('historyList').textContent]"),
             ["empty", "Die Wartungshistorie zeigt die Monteursansicht nur für Objekte Ihrer Aufträge."])
    p.pruefe("/mobil fremdes Objekt: Objektansicht offen",
             await tab.js("document.getElementById('propertyCard').textContent.includes('Wohnanlage Hof')"), True)
    await tab.bild("mobil_fremdes_objekt")
    p.pruefe("Monteurin: JS-Fehler", tab.fehler, [])
    print(json.dumps({"auftrag": order_id}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
