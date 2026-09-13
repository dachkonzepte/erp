"""Version 1.2.19 -- Punkt 1 (Datenverlust in der Schichtenliste), Punkt 2 (use_roof_area_items),
Punkt 3 (Vorgang erstellen unabhängig von der Fälligkeit), Punkt 4 (eigene Vertragsseite)."""

from datetime import date, timedelta

from app.maintenance_contracts import (
    check_due_contracts_and_create_reminders, create_contract, create_contract_item, create_project_from_contract,
    get_contract, get_or_create_maintenance_settings, list_contracts, update_maintenance_settings,
)
from app.models import MaintenanceContractItem
from app.roof_areas import create_layer_type, create_roof_area, upsert_roof_layer
from app.service_reports import add_inspection_item, create_report, update_inspection_item
from app.tasks import list_tasks
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property, make_template_project
from tests.test_v212_maintenance_windows import create_window


def _make_order_for_report(db):
    order, _ = make_order_with_item(db)
    return order


# --- Punkt 1: Datenverlust in der Schichtenliste ---

def test_upsert_roof_layer_partial_updates_do_not_clobber_other_fields():
    """Pflicht-Regressionstest wie in der Planung wörtlich gefordert: present gesetzt, dann ein
    separater Aufruf nur mit notes, dann ein separater Aufruf nur mit thickness_mm -- am Ende
    müssen alle drei Werte gemeinsam auf derselben Zeile stehen. Deckt den bei der Planung
    empirisch nachgewiesenen Datenverlust ab (unbedingtes Überschreiben in upsert_roof_layer())."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    layer_type = create_layer_type(db, "test_trennlage", "Trennlage", roof_type="Flachdach")

    upsert_roof_layer(db, area["id"], layer_type["id"], {"present": True})
    upsert_roof_layer(db, area["id"], layer_type["id"], {"notes": "Bemerkungstext"})
    result = upsert_roof_layer(db, area["id"], layer_type["id"], {"thickness_mm": 40})

    assert result["present"] is True
    assert result["notes"] == "Bemerkungstext"
    assert result["thickness_mm"] == 40


def test_upsert_roof_layer_explicit_null_still_clears_field():
    """Die Kehrseite der exclude_unset-Architektur: ein ausdrücklich gesendetes null muss das
    Feld weiterhin leeren, nicht mitgeschickte Felder bleiben nur unangetastet."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    layer_type = create_layer_type(db, "test_daemmung", "Dämmung", roof_type="Flachdach", has_thickness=True)

    upsert_roof_layer(db, area["id"], layer_type["id"], {"present": True, "execution": "Mineralwolle", "thickness_mm": 100})
    result = upsert_roof_layer(db, area["id"], layer_type["id"], {"execution": None})
    assert result["execution"] is None
    assert result["thickness_mm"] == 100  # nicht mitgeschickt -- bleibt unangetastet


def test_update_inspection_item_partial_updates_do_not_clobber_duration_minutes():
    """Dieselbe Lücke, eine Ebene weiter: setResultAndSave() in service_reports.html sendet bei
    einem OK/Nicht-OK/Entfällt-Klick nur {result} -- ohne die exclude_unset-Umstellung in
    update_inspection_item() würde das serverseitig duration_minutes eines leak_test-Punkts auf
    None zurücksetzen. Reiner Backend-Beleg, unabhängig vom bereits ebenfalls behobenen
    Frontend-Merge-Fehler."""
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung")
    item = add_inspection_item(db, report["id"], "Dichtheitsprüfung", "leak_test")

    update_inspection_item(db, item["id"], {"duration_minutes": 15})
    updated = update_inspection_item(db, item["id"], {"result": "ok"})
    assert updated["result"] == "ok"
    assert updated["duration_minutes"] == 15


# --- Punkt 2: use_roof_area_items ---

def _make_contract_with_active_item(db):
    customer, prop = make_customer_and_property(db)
    template = make_template_project(db, customer, prop)
    area = create_roof_area(db, prop.id, "Nordfläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(
        db, customer.id, prop.id, "Vertrag A", 12, date.today() + timedelta(days=365),
        template_project_id=template.id,
    )
    update_maintenance_settings(db, 30, True, None)  # muss an sein, um die Position anzulegen zu dürfen
    item = create_contract_item(db, contract["id"], area["id"], window["id"])
    row = db.get(MaintenanceContractItem, item["id"])
    row.next_due_date = date.today() - timedelta(days=1)
    db.commit()
    return contract["id"]


def test_use_roof_area_items_off_ignores_legacy_active_items():
    db = db_session()
    contract_id = _make_contract_with_active_item(db)
    update_maintenance_settings(db, 30, False, None)  # Schalter jetzt aus, Position bleibt in der DB

    rows = {r["id"]: r for r in list_contracts(db)}
    assert rows[contract_id]["is_due"] is False  # next_due_date liegt weit in der Zukunft
    assert len(rows[contract_id]["items"]) == 1  # Zeile bleibt in der DB, nur nicht ausgewertet

    reminded = check_due_contracts_and_create_reminders(db)
    assert reminded == []  # weder Vertrags- noch Positions-Erinnerung, da Vertrag nicht fällig
    assert list_tasks(db) == []

    result = create_project_from_contract(db, contract_id)  # keine Ablehnung wegen "aktiver Positionen"
    assert result["project_id"] is not None


def test_use_roof_area_items_on_lets_active_items_drive_due_and_reminders():
    db = db_session()
    contract_id = _make_contract_with_active_item(db)
    update_maintenance_settings(db, 30, True, None)  # Schalter bleibt an -- Positionsebene entscheidet

    rows = {r["id"]: r for r in list_contracts(db)}
    assert rows[contract_id]["is_due"] is True  # über die Position, next_due_date des Vertrags liegt in der Zukunft

    reminded = check_due_contracts_and_create_reminders(db)
    assert reminded == [contract_id]
    tasks = list_tasks(db)
    assert len(tasks) == 1
    assert "Nordfläche" in tasks[0]["title"]  # Positions-Erinnerung (roof_area.name), nicht die Vertrags-Formulierung

    try:
        create_project_from_contract(db, contract_id)
        assert False, "sollte ValueError auslösen (aktive Position vorhanden)"
    except ValueError as exc:
        assert "Positionen" in str(exc)


def test_create_contract_item_rejects_when_setting_off():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today())
    assert get_or_create_maintenance_settings(db).use_roof_area_items is False  # Default
    try:
        create_contract_item(db, contract["id"], area["id"], window["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "deaktiviert" in str(exc)


# --- Punkt 3: "Vorgang erstellen" unabhängig von der Fälligkeit ---

def test_create_project_from_contract_does_not_check_due_date():
    """Backend-Beleg für Punkt 3: die Rückfrage bei einem noch nicht fälligen Vertrag ist reine
    Oberflächen-Logik (confirm() in maintenance_contract.html) -- create_project_from_contract()
    selbst hat nie eine Fälligkeitsprüfung gehabt und bekommt auch keine."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    template = make_template_project(db, customer, prop)
    contract = create_contract(
        db, customer.id, prop.id, "Vertrag, noch lange nicht fällig", 12, date.today() + timedelta(days=300),
        template_project_id=template.id,
    )
    rows = {r["id"]: r for r in list_contracts(db)}
    assert rows[contract["id"]]["is_due"] is False

    result = create_project_from_contract(db, contract["id"])
    assert result["project_id"] is not None


# --- Punkt 4: eigene Vertragsseite ---

def test_get_contract_returns_single_contract_dict():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Einzelvertrag", 12, date.today())
    result = get_contract(db, contract["id"])
    assert result["id"] == contract["id"]
    assert result["title"] == "Einzelvertrag"
    assert get_contract(db, 999999) is None


def test_router_get_single_contract_and_reachable_after_due_items_route(threaded_db_session, router_test_client):
    from app.routers.maintenance_contracts import router as maintenance_contracts_router

    db = threaded_db_session
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Routenvertrag", 12, date.today())
    client = router_test_client(db, maintenance_contracts_router)

    due_resp = client.get("/api/maintenance-contracts/due-items")
    assert due_resp.status_code == 200, due_resp.text  # /due-items bleibt erreichbar, keine Kollision

    detail_resp = client.get(f"/api/maintenance-contracts/{contract['id']}")
    assert detail_resp.status_code == 200, detail_resp.text
    assert detail_resp.json()["title"] == "Routenvertrag"

    missing_resp = client.get("/api/maintenance-contracts/999999")
    assert missing_resp.status_code == 404
