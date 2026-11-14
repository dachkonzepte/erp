"""Version 1.9.341 (E6 aus dem Befund SQLite/PostgreSQL): einen Wartungsvertrag oder eine Position nicht löschen, wenn etwas aus ihnen entstanden ist.

Entscheidung Tobias (14.11.2026): ein Projekt oder Bericht aus dem Vertrag gehört zu seiner Geschichte -- 409 mit den Bereichen und dem Rat, den Vertrag
zu beenden (die Position: zu archivieren), wie bei „Benutzer löschen“. Bis 1.9.340 sperrte nur ein unterschriebener Bericht; ein Projekt aus dem Vertrag
oder ein Berichtsentwurf ließ das Löschen unter PostgreSQL (und seit 1.9.339 in der Suite) am Fremdschlüssel scheitern. Ohne Geschichte geht der Vertrag
wie bisher samt Positionen und Erinnerungen.
"""

from datetime import date

from sqlalchemy import func, select

from app.database import Base
from app.maintenance_contracts import (AUS_DEM_VERTRAG, AUS_DER_POSITION, MIT_DEM_VERTRAG, check_due_contracts_and_create_reminders, create_contract,
                                       create_contract_item, create_project_from_contract, create_window)
from app.models import MaintenanceContract, MaintenanceContractItem, ServiceReport, Task
from app.roof_areas import create_roof_area
from app.routers.maintenance_contracts import router as vertraege
from app.service_reports import create_report
from tests.test_v133_invoices import make_order_with_item
from tests.test_v202_maintenance_contracts import make_customer_and_property, make_template_project
from tests.test_v212_maintenance_windows import _enable_roof_area_items


def _vertrag(db, *, faellig=date(2026, 12, 1)):
    kunde, objekt = make_customer_and_property(db)
    vorlage = make_template_project(db, kunde, objekt)
    vertrag = create_contract(db, kunde.id, objekt.id, "Dachwartung", 12, faellig, template_project_id=vorlage.id)
    return kunde, objekt, vertrag


def _bericht_zeigt_auf(db, *, vertrag_id=None, position_id=None):
    """Ein Berichtsentwurf eines anderen Auftrags, der auf Vertrag oder Position zeigt (ein Zustand, den der Fremdschlüssel zulässt)."""
    order, _item = make_order_with_item(db)
    bericht = create_report(db, order.id, "rapport", description="Entwurf")
    row = db.get(ServiceReport, bericht["id"])
    row.maintenance_contract_id, row.maintenance_contract_item_id = vertrag_id, position_id
    db.commit()


def _loeschen(db, router_test_client, pfad):
    db.commit()
    return router_test_client(db, vertraege).delete(pfad)


def test_vertrag_mit_projekt_daraus_wird_nicht_geloescht(threaded_db_session, router_test_client):
    db = threaded_db_session
    _kunde, _objekt, vertrag = _vertrag(db)
    create_project_from_contract(db, vertrag["id"])
    r = _loeschen(db, router_test_client, f"/api/maintenance-contracts/{vertrag['id']}")
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("Aus dem Vertrag sind schon Projekte entstanden")
    assert "Beende den Vertrag stattdessen" in r.json()["detail"]
    db.expire_all()
    assert db.get(MaintenanceContract, vertrag["id"]) is not None


def test_vertrag_mit_berichtsentwurf_wird_nicht_geloescht(threaded_db_session, router_test_client):
    db = threaded_db_session
    _kunde, _objekt, vertrag = _vertrag(db)
    _bericht_zeigt_auf(db, vertrag_id=vertrag["id"])
    r = _loeschen(db, router_test_client, f"/api/maintenance-contracts/{vertrag['id']}")
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("Aus dem Vertrag sind schon Einsatzberichte entstanden")


def test_vertrag_zaehlt_auch_was_aus_seinen_positionen_entstand(threaded_db_session, router_test_client):
    db = threaded_db_session
    _enable_roof_area_items(db)
    _kunde, objekt, vertrag = _vertrag(db)
    flaeche = create_roof_area(db, objekt.id, "Nordseite")
    fenster = create_window(db, "Herbst", 9, 11)
    position = create_contract_item(db, vertrag["id"], flaeche["id"], fenster["id"])
    create_project_from_contract(db, vertrag["id"], item_id=position["id"])
    _bericht_zeigt_auf(db, position_id=position["id"])
    r = _loeschen(db, router_test_client, f"/api/maintenance-contracts/{vertrag['id']}")
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("Aus dem Vertrag sind schon Projekte und Einsatzberichte entstanden")


def test_position_mit_projekt_oder_bericht_wird_nicht_geloescht(threaded_db_session, router_test_client):
    db = threaded_db_session
    _enable_roof_area_items(db)
    _kunde, objekt, vertrag = _vertrag(db)
    fenster = create_window(db, "Herbst", 9, 11)
    mit_projekt = create_contract_item(db, vertrag["id"], create_roof_area(db, objekt.id, "Nord")["id"], fenster["id"])
    mit_bericht = create_contract_item(db, vertrag["id"], create_roof_area(db, objekt.id, "Süd")["id"], fenster["id"])
    create_project_from_contract(db, vertrag["id"], item_id=mit_projekt["id"])
    _bericht_zeigt_auf(db, position_id=mit_bericht["id"])
    for position, bereich in ((mit_projekt, "Projekte"), (mit_bericht, "Einsatzberichte")):
        r = _loeschen(db, router_test_client, f"/api/maintenance-contract-items/{position['id']}")
        assert r.status_code == 409, r.text
        assert r.json()["detail"].startswith(f"Aus der Position sind schon {bereich} entstanden")
        assert "Archiviere die Position stattdessen" in r.json()["detail"]
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(MaintenanceContractItem)) == 2


def test_vertrag_ohne_geschichte_geht_mit_positionen_und_erinnerungen(threaded_db_session, router_test_client):
    db = threaded_db_session
    _kunde, objekt, vertrag = _vertrag(db, faellig=date(2026, 1, 1))  # längst fällig: es gibt eine Erinnerung
    check_due_contracts_and_create_reminders(db)
    _enable_roof_area_items(db)
    position = create_contract_item(db, vertrag["id"], create_roof_area(db, objekt.id, "Nord")["id"], create_window(db, "Herbst", 9, 11)["id"])
    pfad = f"/maintenance-contracts/{vertrag['id']}"
    assert db.scalar(select(func.count()).select_from(Task).where(Task.source_url == pfad)) >= 1
    r = _loeschen(db, router_test_client, f"/api/maintenance-contracts/{vertrag['id']}")
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(MaintenanceContract, vertrag["id"]) is None and db.get(MaintenanceContractItem, position["id"]) is None
    assert db.scalar(select(func.count()).select_from(Task).where(Task.source_url == pfad)) == 0


def test_jeder_fremdschluessel_auf_vertrag_und_position_ist_eingeordnet():
    alle = sorted((t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns for fk in c.foreign_keys
                  if fk.column.table.name in ("maintenance_contracts", "maintenance_contract_items"))
    eingeordnet = set(MIT_DEM_VERTRAG) | set(AUS_DEM_VERTRAG) | set(AUS_DER_POSITION)
    assert set(alle) == eingeordnet, f"nicht eingeordnet: {sorted(set(alle) - eingeordnet)}; veraltet: {sorted(eingeordnet - set(alle))}"
