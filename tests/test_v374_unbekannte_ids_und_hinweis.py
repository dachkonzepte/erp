"""Version 1.8.71 -- unbekannte IDs 404 statt 500, und der Hinweis fürs Büro am Einsatzbericht (Befund „Vor dem Echtbetrieb:
Geld und Sicherheit“, docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.71").

1. Aufgabe mit project_id, Schnellauftrag und Wartungsvertrag mit customer_id (auch ohne Objekt), Objekt beim Schnellauftrag
   und Vertrag: eine unbekannte ID antwortet 404 mit Text und legt nichts an. Vorher prüfte sie nur der Fremdschlüssel (unter
   PostgreSQL 500, unter SQLite still gespeichert). tests/test_v373_zugehoerigkeit_struktur.py verlangt seit 1.8.71 auch für
   FREI eine Existenzprüfung -- dort fiel die Lücke bis dahin nicht auf.
2. Gehört die Dachfläche der Vertragsposition nicht zum Objekt des Auftrags, entsteht der Bericht ohne sie (kein Fehler für den
   Monteur, Festlegung 1.8.70 Nr. 5), aber nicht mehr still: Warnung im Protokoll (nur IDs, Regel 18) und Hinweis am Bericht,
   nur in der Büro-Liste (contract_area_hint())."""

import logging
from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import (
    MaintenanceContract, MaintenanceContractItem, MaintenanceWindow, Project, ProjectProfile, Task,
)
from app.routers.tasks import router as tasks_router
from tests.test_v373_zugehoerigkeit import _vertrag_body, echte_angebots_ids, welt  # noqa: F401 -- Fixtures

UNBEKANNT = 987654


def _anzahl(db, model):
    return db.scalar(select(func.count()).select_from(model))


# ---------------------------------------------------------------------------
# 1. Unbekannte IDs
# ---------------------------------------------------------------------------

def test_task_with_unknown_project_is_404_and_creates_nothing(welt, router_test_client):
    db = welt["db"]
    c = router_test_client(db, tasks_router, role="buero_auftrag")
    vorher = _anzahl(db, Task)
    r = c.post("/api/tasks", json={"title": "Rückruf", "project_id": UNBEKANNT})
    assert (r.status_code, r.json()) == (404, {"detail": "Projekt nicht gefunden."})
    assert _anzahl(db, Task) == vorher
    ok = c.post("/api/tasks", json={"title": "Rückruf", "project_id": welt["order"].project_id})
    assert ok.status_code == 200, ok.text
    task_id = ok.json()["id"]
    r = c.put(f"/api/tasks/{task_id}", json={"project_id": UNBEKANNT})
    assert (r.status_code, r.json()) == (404, {"detail": "Projekt nicht gefunden."})
    db.expire_all()
    assert db.get(Task, task_id).project_id == welt["order"].project_id
    assert c.put(f"/api/tasks/{task_id}", json={"project_id": None}).status_code == 200


def _schnellauftrag(w, customer_id, property_id):
    return w["client"]("buero_auftrag", None).post("/api/quick-service-orders", json={
        "customer_id": customer_id, "property_id": property_id, "order_type": "reparatur", "title": "Reparatur",
        "confirm_property_customer": True})


@pytest.mark.parametrize("fall", ["kunde_ohne_objekt", "kunde_mit_objekt", "objekt"])
def test_quick_order_with_unknown_customer_or_property_is_404_and_creates_nothing(welt, echte_angebots_ids, fall):
    db = welt["db"]
    kunde, objekt = {"kunde_ohne_objekt": (UNBEKANNT, None), "kunde_mit_objekt": (UNBEKANNT, welt["eigen"].id),
                     "objekt": (welt["kunde"].id, UNBEKANNT)}[fall]
    vorher = _anzahl(db, Project)
    r = _schnellauftrag(welt, kunde, objekt)
    text = "Objekt nicht gefunden." if fall == "objekt" else "Kunde nicht gefunden."
    assert (r.status_code, r.json()) == (404, {"detail": text})
    assert _anzahl(db, Project) == vorher
    assert _schnellauftrag(welt, welt["kunde"].id, None).status_code == 200


@pytest.mark.parametrize("fall", ["kunde_ohne_objekt", "kunde_mit_objekt", "objekt"])
def test_contract_with_unknown_customer_or_property_is_404_and_creates_nothing(welt, fall):
    db = welt["db"]
    c = welt["client"]("buero_auftrag", None)
    body = _vertrag_body(welt, None)
    body.update({"kunde_ohne_objekt": {"customer_id": UNBEKANNT},
                 "kunde_mit_objekt": {"customer_id": UNBEKANNT, "property_id": welt["eigen"].id},
                 "objekt": {"property_id": UNBEKANNT}}[fall], confirm_property_customer=True)
    vorher = _anzahl(db, MaintenanceContract)
    r = c.post("/api/maintenance-contracts", json=body)
    assert r.status_code == 404 and r.json()["detail"] in ("Kunde nicht gefunden.", "Objekt nicht gefunden.")
    assert _anzahl(db, MaintenanceContract) == vorher


def test_contract_update_with_unknown_property_is_404(welt):
    c = welt["client"]("buero_auftrag", None)
    vertrag = c.post("/api/maintenance-contracts", json=_vertrag_body(welt, welt["eigen"].id)).json()
    r = c.put(f"/api/maintenance-contracts/{vertrag['id']}", json={
        "title": "Wartung", "interval_months": 12, "next_due_date": "2027-01-01", "property_id": UNBEKANNT,
        "confirm_property_customer": True})
    assert (r.status_code, r.json()) == (404, {"detail": "Objekt nicht gefunden."})
    welt["db"].expire_all()
    assert welt["db"].get(MaintenanceContract, vertrag["id"]).property_id == welt["eigen"].id


# ---------------------------------------------------------------------------
# 2. Fläche der Vertragsposition aus einem fremden Objekt: Hinweis fürs Büro, Warnung im Protokoll
# ---------------------------------------------------------------------------

def _vorgang_aus_vertrag(w, roof_area_id):
    """Der Auftrag der Monteurin stammt aus einer Vertragsposition mit dieser Fläche (wie ein älterer Vorgang aus einem
    Mustervorgang an einem anderen Objekt)."""
    db = w["db"]
    vertrag = MaintenanceContract(customer_id=w["fremdkunde"].id, property_id=w["fremd"].id, title="Fremdvertrag",
                                  interval_months=12, next_due_date=date(2027, 1, 1))
    fenster = MaintenanceWindow(label="Frühjahr", month_from=3, month_to=5)
    db.add_all([vertrag, fenster])
    db.flush()
    position = MaintenanceContractItem(contract_id=vertrag.id, roof_area_id=roof_area_id,
                                       maintenance_window_id=fenster.id, next_due_date=date(2027, 3, 1))
    db.add(position)
    db.flush()
    db.add(ProjectProfile(project_id=w["order"].project_id, source_maintenance_contract_id=vertrag.id,
                          source_maintenance_contract_item_id=position.id))
    db.commit()
    return position


def test_foreign_contract_area_report_is_created_with_hint_for_office_and_warning(welt, caplog):
    position = _vorgang_aus_vertrag(welt, welt["fremde_flaeche"])
    monteurin = welt["client"]()
    with caplog.at_level(logging.WARNING, logger="app.service_reports"):
        r = monteurin.post(f"/api/orders/{welt['order'].id}/service-reports", json={"report_type": "wartung"})
    assert r.status_code == 200, r.text  # kein Fehler für den Monteur
    bericht = r.json()
    assert bericht["roof_areas"] == [] and "office_hint" not in bericht
    # Warnung: nur IDs, keine Namen (Regel 18)
    warnungen = [rec for rec in caplog.records if rec.levelno == logging.WARNING and rec.name == "app.service_reports"]
    assert len(warnungen) == 1
    text = warnungen[0].getMessage()
    assert f"Einsatzbericht {bericht['id']}" in text and str(welt["fremde_flaeche"]) in text and str(position.id) in text
    assert "Fremddach" not in text and "Objekt Fremd" not in text
    # Büro-Liste: Hinweis mit Fläche und Objekt
    buero = welt["client"]("buero_auftrag", None).get(f"/api/orders/{welt['order'].id}/service-reports").json()
    hinweis = next(b for b in buero if b["id"] == bericht["id"])["office_hint"]
    assert "„Fremddach“" in hinweis and "„Objekt Fremd“" in hinweis and "nicht zum Objekt dieses Auftrags" in hinweis
    # Monteurin: eigener Bericht ohne das Feld, nichts vom fremden Objekt
    liste = monteurin.get(f"/api/orders/{welt['order'].id}/service-reports").json()
    assert all("office_hint" not in b for b in liste)
    assert "Fremd" not in str(liste)


def test_own_contract_area_has_no_hint_and_a_corrected_contract_removes_it(welt):
    position = _vorgang_aus_vertrag(welt, welt["fremde_flaeche"])
    buero = welt["client"]("buero_auftrag", None)
    bericht = welt["client"]().post(f"/api/orders/{welt['order'].id}/service-reports", json={"report_type": "rapport"}).json()

    def hinweis():
        return next(b for b in buero.get(f"/api/orders/{welt['order'].id}/service-reports").json()
                    if b["id"] == bericht["id"])["office_hint"]

    assert hinweis() is not None
    position.roof_area_id = welt["flaeche"]  # Vertrag korrigiert: Fläche des eigenen Objekts
    welt["db"].commit()
    assert hinweis() is None
    ohne_vertrag = buero.post(f"/api/orders/{welt['fremder_auftrag'].id}/service-reports", json={"report_type": "rapport"})
    assert ohne_vertrag.status_code == 200
    assert all(b["office_hint"] is None
               for b in buero.get(f"/api/orders/{welt['fremder_auftrag'].id}/service-reports").json())


def test_service_reports_page_shows_the_hint():
    from pathlib import Path

    html = (Path(__file__).resolve().parent.parent / "app" / "templates" / "service_reports.html").read_text(encoding="utf-8")
    assert "r.office_hint?" in html and "esc(r.office_hint)" in html
