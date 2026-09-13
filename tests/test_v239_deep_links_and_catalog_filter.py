"""Drei gebaute Punkte aus dem laufenden Betrieb (seit 1.3.24):

Punkt 1: Direkteinstieg vom Dashboard-Widget zu einer konkreten Aufgabe (?task=), Anfrage
(?inquiry=) oder einem konkreten Abwesenheitsantrag (?absence=), nach dem Muster von ?report=
aus 1.2.22 -- bewusst drei eigene, kleine Umsetzungen statt eines gemeinsamen Bausteins (siehe
Begründung in CLAUDE.md).

Punkt 3: Katalog-Dropdown im Angebotseditor (GET /api/services liefert jetzt catalog_id/
catalog_name mit, "Alle Kataloge" als zusätzliche Auswahl)."""

from decimal import Decimal
from pathlib import Path

from app.catalogs import create_catalog
from app.routers.services import router as services_router
from tests.test_v123_manual_services import db_session, make_service


# ---------------------------------------------------------------------------
# Punkt 1: Oberflaeche -- statische Pruefungen (kein JS-Test-Runner im Projekt)
# ---------------------------------------------------------------------------

def test_dashboard_links_to_specific_task_inquiry_and_absence():
    html = (Path(__file__).parents[1] / "app" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "/tasks?task=${t.id}" in html
    assert "/inquiries?inquiry=${i.id}" in html
    assert "/time-backoffice?absence=${a.id}#absences" in html


def test_tasks_page_opens_specific_task_from_query_param():
    html = (Path(__file__).parents[1] / "app" / "templates" / "tasks.html").read_text(encoding="utf-8")
    assert "location.search).get('task')" in html
    assert "openEditor(deepLinkTaskId)" in html


def test_inquiries_page_opens_specific_inquiry_from_query_param():
    html = (Path(__file__).parents[1] / "app" / "templates" / "inquiries.html").read_text(encoding="utf-8")
    assert "location.search).get('inquiry')" in html
    assert "openInquiry(deepLinkInquiryId)" in html


def test_time_backoffice_highlights_specific_absence_request_without_changing_hash_routing():
    html = (Path(__file__).parents[1] / "app" / "templates" / "time_backoffice.html").read_text(encoding="utf-8")
    assert "location.search).get('absence')" in html
    assert 'data-abs-id="${r.id}"' in html
    # Die bestehende Hash-basierte Tab-Auswahl (welcher Tab beim Laden aktiv ist) darf unveraendert
    # bleiben -- die neue Zeile darf showTab() nicht selbst aufrufen.
    body = html[html.index("const deepLinkAbsenceId"):]
    body = body[:body.index("\n}")]
    assert "showTab(" not in body


# ---------------------------------------------------------------------------
# Punkt 3: Backend -- GET /api/services liefert Katalogherkunft mit
# ---------------------------------------------------------------------------

def test_list_services_includes_catalog_id_and_name(threaded_db_session, router_test_client):
    db = threaded_db_session
    catalog = create_catalog(db, "Steildach", None)
    service = make_service(db, external_id="STD-001")
    service.catalog_id = catalog.id
    db.commit()
    client = router_test_client(db, services_router)

    resp = client.get("/api/services")
    assert resp.status_code == 200
    rows = {r["external_id"]: r for r in resp.json()}
    assert rows["STD-001"]["catalog_id"] == catalog.id
    assert rows["STD-001"]["catalog_name"] == "Steildach"


def test_list_services_service_without_catalog_has_none():
    db = db_session()
    make_service(db, external_id="ORIG")
    from app.routers.services import list_services
    rows = list_services(catalog_id=None, db=db)
    row = next(r for r in rows if r.external_id == "ORIG")
    assert row.catalog_id is None
    assert row.catalog_name is None


def test_list_services_catalog_id_filter_still_works(threaded_db_session, router_test_client):
    """Regression: der bereits bestehende, jetzt in der Oberflaeche unbenutzte serverseitige
    Filter bleibt unveraendert funktionsfaehig -- die Oberflaeche filtert hier bewusst
    clientseitig (alle Leistungen sind ohnehin schon geladen), das aendert den Endpunkt selbst
    nicht."""
    db = threaded_db_session
    catalog_a = create_catalog(db, "Katalog A", None)
    catalog_b = create_catalog(db, "Katalog B", None)
    service_a = make_service(db, external_id="A-001")
    service_a.catalog_id = catalog_a.id
    service_b = make_service(db, external_id="B-001")
    service_b.catalog_id = catalog_b.id
    db.commit()
    client = router_test_client(db, services_router)

    resp = client.get(f"/api/services?catalog_id={catalog_a.id}")
    assert resp.status_code == 200
    external_ids = {r["external_id"] for r in resp.json()}
    assert external_ids == {"A-001"}


# ---------------------------------------------------------------------------
# Punkt 3: Oberflaeche -- statische Pruefungen
# ---------------------------------------------------------------------------

def test_quote_editor_has_catalog_dropdown_with_all_catalogs_option_and_shows_origin_per_hit():
    html = (Path(__file__).parents[1] / "app" / "templates" / "quote_editor.html").read_text(encoding="utf-8")
    assert 'id="catalogFilter"' in html
    assert "Alle Kataloge" in html
    assert "s.catalog_name" in html
    assert "localStorage" in html
