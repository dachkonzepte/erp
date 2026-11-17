"""Version 1.9.349 -- E9 und E10 (Runde V2a, Punkt 0; Entscheidung Tobias 17.11.2026: B, 409 mit Grund und Rat wie bei E8).

Ein Projekt ohne Auftrag, das Vorlage eines Wartungsvertrags oder einer Position ist (E9) oder an dem eine Eingangsrechnung hängt (E10), wird nicht
gelöscht -- 409 mit dem Rat, es zu archivieren oder die Vorlage bzw. das Projekt der Eingangsrechnung zu wechseln. Bis 1.9.348 scheiterte das Löschen
am Fremdschlüssel (live 500, in der Suite `FOREIGN KEY constraint failed`) -- die Fälle unten waren vorher rot."""

from datetime import date
from decimal import Decimal

from app.maintenance_contracts import create_contract, create_contract_item, create_window
from app.models import IncomingInvoice, MaintenanceContract, Project, Supplier, Task
from app.roof_areas import create_roof_area
from app.routers.projects import router as projekte_router
from tests.test_v192_project_templates import make_full_project
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v212_maintenance_windows import _enable_roof_area_items

ENDE = "deshalb lässt es sich nicht löschen. Archiviere das Projekt stattdessen oder"


def _loeschen(db, router_test_client, project):
    return router_test_client(db, projekte_router).delete(f"/api/projects/{project.id}")


def _vorlage(db):
    project = make_full_project(db)
    project.is_template = True
    db.commit()
    return project


def test_vorlage_eines_wartungsvertrags_nicht_loeschen(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = _vorlage(db)
    kunde, objekt = make_customer_and_property(db)
    vertrag = create_contract(db, kunde.id, objekt.id, "Dachwartung", 12, date(2026, 12, 1), template_project_id=project.id)
    r = _loeschen(db, router_test_client, project)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Am Projekt hängt noch 1 Wartungsvertrag, der es als Vorlage nimmt – {ENDE} wähle im Wartungsvertrag eine andere Vorlage."
    db.expire_all()
    assert db.get(Project, project.id) is not None and db.get(MaintenanceContract, vertrag["id"]).template_project_id == project.id


def test_vorlage_einer_position_nicht_loeschen(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = _vorlage(db)
    kunde, objekt = make_customer_and_property(db)
    vertrag = create_contract(db, kunde.id, objekt.id, "Dachwartung", 12, date(2026, 12, 1))
    _enable_roof_area_items(db)
    create_contract_item(db, vertrag["id"], create_roof_area(db, objekt.id, "Nord")["id"], create_window(db, "Herbst", 9, 11)["id"],
                         template_project_id=project.id)
    r = _loeschen(db, router_test_client, project)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (f"Am Projekt hängt noch 1 Position eines Wartungsvertrags, die es als Vorlage nimmt – {ENDE} "
                                  "wähle in der Position eine andere Vorlage.")
    assert db.get(Project, project.id) is not None


def test_projekt_mit_eingangsrechnung_nicht_loeschen(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = make_full_project(db)
    lieferant = Supplier(name="Lieferant Probe")
    db.add(lieferant)
    db.flush()
    for nummer in ("ER-1", "ER-2"):
        db.add(IncomingInvoice(supplier_id=lieferant.id, supplier_invoice_number=nummer, invoice_date=date(2026, 11, 1), net_amount=Decimal("10"),
                               project_id=project.id))
    db.commit()
    r = _loeschen(db, router_test_client, project)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Am Projekt hängen noch 2 Eingangsrechnungen – {ENDE} ordne die Eingangsrechnungen einem anderen Projekt zu."
    assert db.get(Project, project.id) is not None


def test_mehrere_gruende_in_einer_meldung(threaded_db_session, router_test_client):
    db = threaded_db_session
    project = make_full_project(db)
    lieferant = Supplier(name="Lieferant Probe")
    db.add_all([lieferant, Task(title="Rückruf Kunde", project_id=project.id)])
    db.flush()
    db.add(IncomingInvoice(supplier_id=lieferant.id, supplier_invoice_number="ER-1", invoice_date=date(2026, 11, 1), net_amount=Decimal("10"),
                           project_id=project.id))
    db.commit()
    assert _loeschen(db, router_test_client, project).json()["detail"] == (
        f"Am Projekt hängen noch 1 Aufgabe und 1 Eingangsrechnung – {ENDE} lösche zuerst seine Aufgaben und ordne die Eingangsrechnung einem "
        "anderen Projekt zu.")
