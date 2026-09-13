"""Version 1.2.22 -- ein Bericht über mehrere Dachflächen, "Wartung durchführen" von der
Vertragsseite, explizite Dachtyp-Standardvorlage, Fälligkeit erst bei der Unterschrift."""

import importlib.util
from datetime import date
from pathlib import Path

from app.inspection_templates import list_roof_type_template_defaults, set_roof_type_template_default
from app.maintenance_contracts import create_contract, create_maintenance_visit, get_or_create_maintenance_settings
from app.models import InspectionItem, MaintenanceContract, ServiceReportRoofArea
from app.roof_areas import create_roof_area, create_roof_component, set_roof_area_archived
from app.service_reports import (
    create_report, list_inspection_items, regenerate_inspection_items, report_to_dict, sign_report,
    sync_inspection_items,
)
from app.service_reports import _load as _load_report
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property, make_template_project
from tests.test_v212_maintenance_windows import _enable_roof_area_items
from tests.test_v213_inspection_items import _make_order_for_report, _seed_test_template


def _migration_module():
    path = next(Path(__file__).resolve().parents[1].glob(
        "alembic/versions/*_multi_area_reports_roof_type_defaults_*.py"
    ))
    spec = importlib.util.spec_from_file_location("migration_1222_multi_area_reports", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Punkt 1: mehrere Dachflächen in einem Bericht ---

def test_create_report_with_multiple_areas_generates_items_for_both_and_tags_roof_area_id():
    db = db_session()
    template = _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area_a = create_roof_area(db, prop.id, "Flachdach Nord", roof_type="Flachdach")
    area_b = create_roof_area(db, prop.id, "Flachdach Süd", roof_type="Flachdach")
    create_roof_component(db, area_a["id"], "Gully A1", component_type="Gully", sort_order=10)
    create_roof_component(db, area_b["id"], "Gully B1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)

    report = create_report(db, order.id, "wartung", roof_area_ids=[area_a["id"], area_b["id"]])
    assert len(report["roof_areas"]) == 2
    assert {a["roof_area_id"] for a in report["roof_areas"]} == {area_a["id"], area_b["id"]}
    assert all(a["inspection_template_id"] == template["id"] for a in report["roof_areas"])

    items = list_inspection_items(db, report["id"])
    assert any(i["text"].startswith("Gully A1") and i["roof_area_id"] == area_a["id"] for i in items)
    assert any(i["text"].startswith("Gully B1") and i["roof_area_id"] == area_b["id"] for i in items)
    # Beide Flächen liefern dieselben "allgemeinen" (nicht-bauteilgebundenen) Vorlagenpunkte --
    # jeder davon trägt trotzdem die jeweils richtige roof_area_id, nicht component_type-gebunden.
    general_a = [i for i in items if i["roof_area_id"] == area_a["id"] and i["roof_component_id"] is None]
    general_b = [i for i in items if i["roof_area_id"] == area_b["id"] and i["roof_component_id"] is None]
    assert len(general_a) == len(general_b) and len(general_a) > 0


def test_area_without_resolvable_template_still_gets_its_row_but_no_items():
    """Eine Fläche ohne passende Vorlage bleibt trotzdem als beteiligte Fläche sichtbar (leer),
    verschwindet nicht spurlos -- siehe Rückfrage 1 im Plan."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Steildach ohne Vorlage", roof_type="Steildach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    assert len(report["roof_areas"]) == 1
    assert report["roof_areas"][0]["roof_area_id"] == area["id"]
    assert report["roof_areas"][0]["inspection_template_id"] is None
    assert list_inspection_items(db, report["id"]) == []


def test_regenerate_and_sync_work_across_multiple_areas():
    db = db_session()
    template = _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area_a = create_roof_area(db, prop.id, "Fläche A", roof_type="Flachdach")
    area_b = create_roof_area(db, prop.id, "Fläche B", roof_type="Flachdach")
    create_roof_component(db, area_a["id"], "Gully A1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area_a["id"], area_b["id"]])

    result = sync_inspection_items(db, report["id"])
    assert result["added"] == 0  # nichts Neues, beide Flächen bereits vollständig generiert

    create_roof_component(db, area_b["id"], "Gully B2", component_type="Gully", sort_order=20)
    result = sync_inspection_items(db, report["id"])
    assert result["added"] == 2  # Gully hat zwei Vorlagenpunkte
    new_items = [i for i in result["items"] if i["text"].startswith("Gully B2")]
    assert len(new_items) == 2 and all(i["roof_area_id"] == area_b["id"] for i in new_items)

    regenerated = regenerate_inspection_items(db, report["id"])
    regenerated_items = list_inspection_items(db, report["id"])
    assert any(i["roof_area_id"] == area_a["id"] for i in regenerated_items)
    assert any(i["roof_area_id"] == area_b["id"] for i in regenerated_items)


def test_regenerate_and_sync_still_work_for_legacy_single_area_report_without_report_roof_areas():
    """Ein Altbestand-Bericht (vor 1.2.22) hat nie ServiceReportRoofArea-Zeilen -- simuliert
    durch direktes Setzen der Legacy-Spalten statt über create_report()."""
    db = db_session()
    template = _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Altbestand-Fläche", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")  # keine Fläche -> keine ServiceReportRoofArea-Zeile

    row = _load_report(db, report["id"])
    row.roof_area_id = area["id"]
    row.inspection_template_id = template["id"]
    row.inspection_template_version = template["version"]
    db.commit()
    assert row.report_roof_areas == []

    sync_result = sync_inspection_items(db, report["id"])
    assert sync_result["added"] > 0
    # Der Altbestand-Zweig kennt die Fläche (über die Legacy-Spalte report.roof_area_id) und
    # setzt roof_area_id auf neu synchronisierten Punkten trotzdem -- schadet nicht (die
    # Oberfläche zeigt bei genau einer Fläche ohnehin ALLE Punkte in einem einzigen Block,
    # unabhängig von item.roof_area_id) und ist für künftig ergänzte Punkte genauer.
    assert all(i["roof_area_id"] == area["id"] for i in sync_result["items"])

    regenerate_inspection_items(db, report["id"])
    assert len(list_inspection_items(db, report["id"])) > 0


# --- Punkt 2: explizite Dachtyp-Standardvorlage ---

def test_resolve_inspection_template_uses_explicit_default_over_sort_order():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche", roof_type="Flachdach")
    order = _make_order_for_report(db)

    from app.inspection_templates import create_template
    winner_by_sort_order = create_template(db, "Zuerst (niedrigster sort_order)", roof_type="Flachdach")
    explicit_winner = create_template(db, "Explizit zugeordnet", roof_type="Flachdach")
    assert winner_by_sort_order["sort_order"] < explicit_winner["sort_order"]

    set_roof_type_template_default(db, "Flachdach", explicit_winner["id"])
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    assert report["roof_areas"][0]["inspection_template_id"] == explicit_winner["id"]


def test_resolve_inspection_template_falls_back_to_null_stage_when_multiple_candidates_and_no_default():
    """Mehrere Vorlagen mit demselben roof_type, aber KEINE explizite Zuordnung -- wird seit
    1.2.22 nicht mehr geraten (anders als bei genau einem Kandidaten, siehe nächster Test)."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche", roof_type="Flachdach")
    order = _make_order_for_report(db)

    from app.inspection_templates import create_template
    create_template(db, "Kandidat 1", roof_type="Flachdach")
    create_template(db, "Kandidat 2", roof_type="Flachdach")
    fallback = create_template(db, "Fällt für jeden Dachtyp", roof_type=None)

    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    assert report["roof_areas"][0]["inspection_template_id"] == fallback["id"]


def test_resolve_inspection_template_uses_sole_candidate_without_explicit_default():
    """Genau EIN Kandidat für den Dachtyp, keine explizite Zuordnung -- wird trotzdem
    verwendet, da hier nichts zu erraten ist (sonst müsste jede frische Installation erst eine
    Zuordnung anlegen, obwohl die Auflösung eindeutig ist)."""
    db = db_session()
    template = _seed_test_template(db, roof_type="Steildach")
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche", roof_type="Steildach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    assert report["roof_areas"][0]["inspection_template_id"] == template["id"]


def test_list_and_set_roof_type_template_default():
    db = db_session()
    from app.inspection_templates import create_template
    template = create_template(db, "Flachdach Standard", roof_type="Flachdach")
    rows = list_roof_type_template_defaults(db)
    flachdach_row = next(r for r in rows if r["roof_type"] == "Flachdach")
    assert flachdach_row["inspection_template_id"] is None

    set_roof_type_template_default(db, "Flachdach", template["id"])
    rows = list_roof_type_template_defaults(db)
    flachdach_row = next(r for r in rows if r["roof_type"] == "Flachdach")
    assert flachdach_row["inspection_template_id"] == template["id"]

    set_roof_type_template_default(db, "Flachdach", None)
    rows = list_roof_type_template_defaults(db)
    flachdach_row = next(r for r in rows if r["roof_type"] == "Flachdach")
    assert flachdach_row["inspection_template_id"] is None


def test_migration_resolves_todays_implicit_winner_per_roof_type():
    """Die Migrationslogik muss für einen roof_type mit mehreren Vorlagen genau die Vorlage
    liefern, die die bisherige implizite Auflösung (niedrigster sort_order, dann id) auch
    gewählt hätte -- keine archivierte Vorlage darf gewinnen."""
    db = db_session()
    from app.inspection_templates import create_template, set_template_archived
    create_template(db, "Ohne Dachtyp", roof_type=None)
    loser = create_template(db, "Loser (höherer sort_order)", roof_type="Flachdach")
    winner = create_template(db, "Winner (niedrigerer sort_order)", roof_type="Flachdach")
    # sort_order wächst mit jedem create_template()-Aufruf (max_sort + 10) -- Gewinner explizit
    # per direktem Datenbankzugriff auf einen NIEDRIGEREN sort_order als der Verlierer gesetzt.
    from app.models import InspectionTemplate
    db.get(InspectionTemplate, winner["id"]).sort_order = 5
    db.get(InspectionTemplate, loser["id"]).sort_order = 50
    db.commit()
    archived_only_type = create_template(db, "Nur archiviert", roof_type="Gründach")
    set_template_archived(db, archived_only_type["id"], True)

    module = _migration_module()
    rows = dict(module._resolve_roof_type_default_template_rows(db))
    assert rows["Flachdach"] == winner["id"]
    assert "Gründach" not in rows  # ausschließlich archivierte Kandidaten -> bewusst nicht bestückt


# --- Punkt 3: "Wartung durchführen" ---

def test_create_maintenance_visit_creates_order_and_report_covering_all_non_archived_areas():
    db = db_session()
    template = _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area_a = create_roof_area(db, prop.id, "Fläche A", roof_type="Flachdach")
    area_b = create_roof_area(db, prop.id, "Fläche B", roof_type="Flachdach")
    archived_area = create_roof_area(db, prop.id, "Archivierte Fläche", roof_type="Flachdach")
    set_roof_area_archived(db, archived_area["id"], True)
    contract = create_contract(db, customer.id, prop.id, "Wartungsvertrag", 12, date.today())

    result = create_maintenance_visit(db, contract["id"])
    assert result["order_id"] is not None and result["report_id"] is not None

    report = report_to_dict(_load_report(db, result["report_id"]))
    assert report["advance_due_date_on_sign"] is True
    assert report["maintenance_contract_id"] == contract["id"]
    covered_area_ids = {a["roof_area_id"] for a in report["roof_areas"]}
    assert covered_area_ids == {area_a["id"], area_b["id"]}  # archivierte Fläche bleibt außen vor


def test_create_maintenance_visit_without_property_still_creates_order_without_items():
    db = db_session()
    customer = make_customer_and_property(db)[0]
    contract = create_contract(db, customer.id, None, "Vertrag ohne Objekt", 12, date.today())
    result = create_maintenance_visit(db, contract["id"])
    report = report_to_dict(_load_report(db, result["report_id"]))
    assert report["roof_areas"] == []
    assert list_inspection_items(db, result["report_id"]) == []


def test_create_maintenance_visit_rejects_when_active_items_exist_under_roof_area_items_toggle():
    db = db_session()
    _enable_roof_area_items(db)
    from app.maintenance_contracts import create_contract_item, create_window
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag mit Positionen", 12, date.today())
    create_contract_item(db, contract["id"], area["id"], window["id"])
    try:
        create_maintenance_visit(db, contract["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Positionen" in str(exc)


# --- Rückfrage 2: Fälligkeit erst bei der Unterschrift ---

def test_sign_report_advances_contract_due_date_only_when_flagged():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 6, date(2026, 1, 1))
    order, _ = make_order_with_item(db)
    from app.projects import get_or_create_project_profile
    get_or_create_project_profile(db, order.project_id).source_maintenance_contract_id = contract["id"]
    db.commit()

    report = create_report(db, order.id, "wartung", advance_due_date_on_sign=True)
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")
    updated_contract = db.get(MaintenanceContract, contract["id"])
    assert updated_contract.next_due_date == date(2026, 7, 1)
    assert updated_contract.last_reminder_due_date is None


def test_sign_report_does_not_advance_due_date_without_flag():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 6, date(2026, 1, 1))
    order, _ = make_order_with_item(db)
    from app.projects import get_or_create_project_profile
    get_or_create_project_profile(db, order.project_id).source_maintenance_contract_id = contract["id"]
    db.commit()

    report = create_report(db, order.id, "wartung")  # advance_due_date_on_sign bleibt False
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")
    unchanged_contract = db.get(MaintenanceContract, contract["id"])
    assert unchanged_contract.next_due_date == date(2026, 1, 1)


def test_router_endpoints_for_perform_maintenance_and_roof_type_template_defaults(threaded_db_session, router_test_client):
    from app.routers.inspection_templates import router as inspection_templates_router
    from app.routers.maintenance_contracts import router as maintenance_contracts_router

    db = threaded_db_session
    template = _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    create_roof_area(db, prop.id, "Fläche", roof_type="Flachdach")
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today())
    client = router_test_client(db, maintenance_contracts_router, inspection_templates_router)

    resp = client.post(f"/api/maintenance-contracts/{contract['id']}/perform-maintenance")
    assert resp.status_code == 200, resp.text
    assert resp.json()["report_id"] is not None

    defaults_resp = client.get("/api/roof-type-template-defaults")
    assert defaults_resp.status_code == 200
    assert any(r["roof_type"] == "Flachdach" for r in defaults_resp.json())

    put_resp = client.put(f"/api/roof-type-template-defaults/Flachdach", json={"inspection_template_id": template["id"]})
    assert put_resp.status_code == 200
    updated_row = next(r for r in put_resp.json() if r["roof_type"] == "Flachdach")
    assert updated_row["inspection_template_id"] == template["id"]


def test_sign_report_with_flag_but_deleted_contract_does_not_error():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "wartung", advance_due_date_on_sign=True)
    row = _load_report(db, report["id"])
    row.maintenance_contract_id = 999999  # zeigt ins Leere, simuliert einen inzwischen gelöschten Vertrag
    db.commit()
    signed = sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")
    assert signed["status"] == "unterschrieben"
