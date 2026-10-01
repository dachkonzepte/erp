"""Version 1.8.29 -- Arbeitsvorbereitung: Speichern schickt keine fest verdrahteten Werte mehr.

Nebenbefund 1 aus 1.8.25 (docs/archiv/teil-updates.md): work_preparation.html schickte beim Speichern
immer Werte mit, die niemand bearbeitet hatte, und der Server übernahm jedes Feld:

    saveMaterial   supplier:null      leerte den eingetippten Lieferanten einer älteren Zeile ohne
                                      Lieferanten-Datensatz (Freitext aus der Zeit vor 0.8.2)
    saveEmployee   planned_hours:null leerte die Planstunden der Zuordnung
    saveTask       sort_order:100     setzte die Reihenfolge zurück

Jetzt schickt die Seite nur, was sie bearbeitet, und die drei PUT-Endpunkte sind Teil-Updates
(PartialUpdate, Regel 22). Die Lieferanten-Auswahl zeigt einen Freitext-Lieferanten als eigene, vorgewählte
Option "(Freitext)"; solange sie gewählt bleibt, schickt die Seite kein supplier_id. "— kein Lieferant —"
schickt supplier_id null und leert Verknüpfung und Freitext. Die Auswahl selbst prüft der Klicktest
scripts/klicktest_arbeitsvorbereitung.py im Browser.

Jeder Test liest die geschickten Schlüssel aus der Vorlage (ui_keys() aus test_v329) und schickt genau
diese an den Endpunkt."""

from decimal import Decimal

import pytest

from app.models import (
    Employee, Supplier, WorkPreparationEmployee, WorkPreparationMaterial, WorkPreparationMaterialSupplier,
    WorkPreparationTask,
)
from app.routers.work_preparation import router as work_preparation_router
from app.work_preparation import ensure_preparation
from tests.test_v133_invoices import make_order_with_item
from tests.test_v329_teil_updates import payload, ui_keys

FREITEXT = "Dachbaustoffe Müller (telefonisch)"


@pytest.fixture
def av(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    prep = ensure_preparation(db, order.id)
    max_m = Employee(employee_number="AV-1", first_name="Max", last_name="Monteur", employee_group="gewerblich",
                     weekly_hours=Decimal("40"), active=True)
    lieferant = Supplier(supplier_number="L-1", name="Bauder Nord", active=True)
    db.add_all([max_m, lieferant]); db.flush()
    zuordnung = WorkPreparationEmployee(preparation_id=prep.id, employee_id=max_m.id, role="Vorarbeiter",
                                        planned_hours=Decimal("6"), notes="alt")
    material = WorkPreparationMaterial(preparation_id=prep.id, name="Bitumenbahn", unit="Rolle",
                                       planned_quantity=Decimal("10"), status="bedarf", supplier=FREITEXT)
    aufgabe = WorkPreparationTask(preparation_id=prep.id, title="Gerüst bestellen", status="offen",
                                  priority="normal", sort_order=30)
    db.add_all([zuordnung, material, aufgabe]); db.commit()
    return {"db": db, "client": router_test_client(db, work_preparation_router), "zuordnung": zuordnung.id,
            "material": material.id, "aufgabe": aufgabe.id, "lieferant": lieferant.id, "max": max_m.id}


def _material(av) -> dict:
    av["db"].expire_all()
    row = av["db"].get(WorkPreparationMaterial, av["material"])
    link = av["db"].query(WorkPreparationMaterialSupplier).filter_by(material_id=row.id).one_or_none()
    return {"menge": row.planned_quantity, "status": row.status, "notiz": row.notes, "freitext": row.supplier,
            "lieferant_id": link.supplier_id if link else None}


MATERIAL_WERTE = {"planned_quantity": 12, "status": "bestellt", "notes": "Lieferung Montag"}


def test_material_speichern_laesst_den_freitext_lieferanten_stehen(av):
    keys = ui_keys("work_preparation.html", "saveMaterial", "const body=")
    assert set(keys) == {"planned_quantity", "status", "notes"}
    response = av["client"].put(f"/api/work-preparation/materials/{av['material']}",
                                json=payload(keys, MATERIAL_WERTE))
    assert response.status_code == 200, response.text
    assert _material(av) == {"menge": Decimal("12"), "status": "bestellt", "notiz": "Lieferung Montag",
                             "freitext": FREITEXT, "lieferant_id": None}
    zeile = next(m for m in response.json()["materials"] if m["id"] == av["material"])
    assert (zeile["supplier"], zeile["supplier_id"]) == (FREITEXT, None)


def test_material_lieferant_waehlen_und_kein_lieferant(av):
    client, url = av["client"], f"/api/work-preparation/materials/{av['material']}"
    assert client.put(url, json={"supplier_id": av["lieferant"]}).status_code == 200
    assert _material(av)["freitext"] == "Bauder Nord" and _material(av)["lieferant_id"] == av["lieferant"]
    assert client.put(url, json={"notes": "nur Notiz"}).status_code == 200
    assert _material(av)["lieferant_id"] == av["lieferant"]
    assert client.put(url, json={"supplier_id": None}).status_code == 200
    assert (_material(av)["freitext"], _material(av)["lieferant_id"]) == (None, None)


def test_material_nur_freitext_geschickt_setzt_ihn_und_loest_die_verknuepfung(av):
    """Altes API-Verhalten für Aufrufer, die nur den Freitext schicken: der Freitext gilt, eine
    Verknüpfung entfällt (sonst zeigte die Seite weiter den verknüpften Namen)."""
    client, url = av["client"], f"/api/work-preparation/materials/{av['material']}"
    client.put(url, json={"supplier_id": av["lieferant"]})
    assert client.put(url, json={"supplier": "Händler um die Ecke"}).status_code == 200
    assert (_material(av)["freitext"], _material(av)["lieferant_id"]) == ("Händler um die Ecke", None)


def test_mitarbeiter_speichern_laesst_die_planstunden_stehen(av):
    keys = ui_keys("work_preparation.html", "saveEmployee", "body:JSON.stringify(")
    assert set(keys) == {"role", "notes"}
    response = av["client"].put(f"/api/work-preparation/employees/{av['zuordnung']}",
                                json=payload(keys, {"role": "Kolonnenführer", "notes": "neu"}))
    assert response.status_code == 200, response.text
    av["db"].expire_all()
    row = av["db"].get(WorkPreparationEmployee, av["zuordnung"])
    assert (row.role, row.notes, row.planned_hours) == ("Kolonnenführer", "neu", Decimal("6"))


AUFGABE_WERTE = {"title": "Gerüst bestellen bei Firma Hoch", "status": "in_arbeit", "priority": "hoch",
                 "due_date": None, "assigned_employee_id": None, "notes": "Rückruf abwarten"}


def test_aufgabe_speichern_laesst_die_reihenfolge_stehen(av):
    keys = ui_keys("work_preparation.html", "saveTask", "body:JSON.stringify(")
    assert set(keys) == set(AUFGABE_WERTE)
    werte = {**AUFGABE_WERTE, "assigned_employee_id": av["max"]}
    response = av["client"].put(f"/api/work-preparation/tasks/{av['aufgabe']}", json=payload(keys, werte))
    assert response.status_code == 200, response.text
    av["db"].expire_all()
    row = av["db"].get(WorkPreparationTask, av["aufgabe"])
    assert (row.title, row.status, row.assigned_employee_id, row.sort_order) == (
        "Gerüst bestellen bei Firma Hoch", "in_arbeit", av["max"], 30)


@pytest.mark.parametrize("vorlage,name,marke,verboten", [
    ("work_preparation.html", "addEmployee", "body:JSON.stringify(", {"planned_hours", "notes"}),
    ("work_preparation.html", "addTask", "body:JSON.stringify(", {"notes", "sort_order"}),
])
def test_anlegen_schickt_keine_vorgabewerte(vorlage, name, marke, verboten):
    """Beim Anlegen waren planned_hours:null, notes:null, sort_order:100 nur die Vorgabewerte des Schemas --
    harmlos, aber dieselben fest verdrahteten Werte; sie entfallen mit."""
    assert not set(ui_keys(vorlage, name, marke)) & verboten


@pytest.mark.parametrize("pfad,feld", [
    ("/api/work-preparation/materials/{material}", "planned_quantity"),
    ("/api/work-preparation/materials/{material}", "status"),
    ("/api/work-preparation/tasks/{aufgabe}", "title"),
    ("/api/work-preparation/tasks/{aufgabe}", "status"),
    ("/api/work-preparation/tasks/{aufgabe}", "priority"),
    ("/api/work-preparation/tasks/{aufgabe}", "sort_order"),
])
def test_null_in_pflichtfeld_ist_422(av, pfad, feld):
    url = pfad.format(material=av["material"], aufgabe=av["aufgabe"])
    assert av["client"].put(url, json={feld: None}).status_code == 422
