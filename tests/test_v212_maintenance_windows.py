from datetime import date, timedelta

from sqlalchemy import select

from app.maintenance_contracts import (
    _next_window_opening, _window_close_date, check_due_contracts_and_create_reminders, create_contract,
    create_contract_item, create_project_from_contract, create_window, delete_contract, delete_contract_item,
    delete_window, get_or_create_maintenance_settings, list_contracts, set_item_archived,
)
from app.models import (
    Customer, MaintenanceContractItem, MaintenanceWindow, Order, Project, ProjectProfile,
)
from app.project_pipeline_columns import default_pipeline_column_id
from app.projects import duplicate_project
from app.roof_areas import create_roof_area, delete_roof_area
from app.routers.maintenance_contracts import router as maintenance_contracts_router
from app import service_reports
from app.service_reports import create_report, sign_report
from app.tasks import list_tasks
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property, make_template_project


def _enable_roof_area_items(db):
    """Seit 1.2.19 ist create_contract_item() nur erlaubt, wenn MaintenanceSettings.
    use_roof_area_items an ist (Default aus) -- diese Datei testet gezielt das
    Positionen-Verhalten, braucht den Schalter also explizit an."""
    settings = get_or_create_maintenance_settings(db)
    settings.use_roof_area_items = True
    db.commit()


def test_maintenance_windows_reorder_route_is_not_shadowed_by_id_route(threaded_db_session, router_test_client):
    """Korrektur 3: PUT /reorder muss den literalen Pfad treffen, nicht als window_id="reorder"
    bei der Update-Funktion landen (was ein FastAPI-Validierungsfehler wäre)."""
    db = threaded_db_session
    w1 = create_window(db, "Frühjahr", 3, 5)
    w2 = create_window(db, "Herbst", 10, 11)
    client = router_test_client(db, maintenance_contracts_router)
    resp = client.put("/api/maintenance-windows/reorder", json={"ordered_ids": [w2["id"], w1["id"]]})
    assert resp.status_code == 200, resp.text
    assert [w["id"] for w in resp.json()] == [w2["id"], w1["id"]]


def test_maintenance_contracts_due_items_route_is_reachable(threaded_db_session, router_test_client):
    """Korrektur 3: GET /due-items darf nicht mit einer künftigen /{contract_id}-Route kollidieren."""
    db = threaded_db_session
    customer, prop = make_customer_and_property(db)
    create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today() - timedelta(days=1))
    client = router_test_client(db, maintenance_contracts_router)
    resp = client.get("/api/maintenance-contracts/due-items")
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


def test_contract_without_items_has_empty_items_list_and_unchanged_behavior():
    """Kernkriterium: ein Vertrag ohne Positionen bleibt exakt beim bisherigen Verhalten."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    contract = create_contract(db, customer.id, prop.id, "Ohne Positionen", 12, date.today())
    assert contract["items"] == []
    rows = list_contracts(db)
    assert rows[0]["items"] == []


def test_two_active_items_create_exactly_two_tasks_not_three_and_reminded_ids_are_deduped():
    """Korrektur 1: die Positionsebene löst die Vertragsebene vollständig ab -- zwei fällige
    Positionen desselben Vertrags erzeugen zwei Aufgaben (nicht drei), und die reminded-Liste
    enthält die Vertrags-ID nur einmal."""
    db = db_session()
    _enable_roof_area_items(db)
    customer, prop = make_customer_and_property(db)
    area1 = create_roof_area(db, prop.id, "Fläche Nord")
    area2 = create_roof_area(db, prop.id, "Fläche Süd")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag mit Positionen", 12, date.today() + timedelta(days=365))
    item1 = create_contract_item(db, contract["id"], area1["id"], window["id"])
    item2 = create_contract_item(db, contract["id"], area2["id"], window["id"])
    for item in (item1, item2):
        row = db.get(MaintenanceContractItem, item["id"])
        row.next_due_date = date.today() - timedelta(days=1)
    db.commit()

    reminded = check_due_contracts_and_create_reminders(db)
    assert reminded == [contract["id"]]
    assert len(list_tasks(db)) == 2  # nicht drei -- keine zusätzliche Vertrags-Aufgabe

    reminded_again = check_due_contracts_and_create_reminders(db)
    assert reminded_again == []
    assert len(list_tasks(db)) == 2  # keine Duplikate beim zweiten Aufruf


def test_is_due_follows_active_items_and_falls_back_when_all_items_archived():
    db = db_session()
    _enable_roof_area_items(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today() + timedelta(days=365))
    item = create_contract_item(db, contract["id"], area["id"], window["id"])
    row = db.get(MaintenanceContractItem, item["id"])
    row.next_due_date = date.today() - timedelta(days=1)
    db.commit()

    rows = {r["id"]: r for r in list_contracts(db)}
    assert rows[contract["id"]]["is_due"] is True  # über die Position, nicht über contract.next_due_date

    set_item_archived(db, item["id"], True)
    rows = {r["id"]: r for r in list_contracts(db)}
    assert rows[contract["id"]]["is_due"] is False  # Rückfall: Vertrag selbst liegt weit in der Zukunft


def test_create_project_from_contract_rejects_contract_level_call_while_active_items_exist():
    db = db_session()
    _enable_roof_area_items(db)
    customer, prop = make_customer_and_property(db)
    template = make_template_project(db, customer, prop)
    area = create_roof_area(db, prop.id, "Fläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today(), template_project_id=template.id)
    item = create_contract_item(db, contract["id"], area["id"], window["id"])

    try:
        create_project_from_contract(db, contract["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Positionen" in str(exc)

    set_item_archived(db, item["id"], True)
    result = create_project_from_contract(db, contract["id"])  # wieder wie vor 1.2.15
    assert result["project_id"] is not None


def test_create_project_from_contract_for_item_tags_profile_and_advances_only_item_due_date():
    db = db_session()
    _enable_roof_area_items(db)
    customer, prop = make_customer_and_property(db)
    template = make_template_project(db, customer, prop)
    area = create_roof_area(db, prop.id, "Fläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today() + timedelta(days=365),
                                template_project_id=template.id)
    item = create_contract_item(db, contract["id"], area["id"], window["id"])
    old_item_due = item["next_due_date"]

    result = create_project_from_contract(db, contract["id"], item_id=item["id"])
    project_id = result["project_id"]

    profile = db.scalar(select(ProjectProfile).where(ProjectProfile.project_id == project_id))
    assert profile.source_maintenance_contract_id == contract["id"]
    assert profile.source_maintenance_contract_item_id == item["id"]

    updated_item = db.get(MaintenanceContractItem, item["id"])
    assert updated_item.next_due_date > old_item_due
    assert updated_item.last_reminder_due_date is None

    order = Order(
        order_number="AUF-TEST-0101", project_id=project_id, source_quote_id=1, quote_number_snapshot="A-TEST-0101",
        title="Testauftrag", customer_name=customer.name,
    )
    db.add(order); db.commit()
    report = create_report(db, order.id, "wartung")
    assert report["maintenance_contract_id"] == contract["id"]
    assert report["maintenance_contract_item_id"] == item["id"]


def test_duplicate_project_does_not_copy_maintenance_contract_tags():
    """Korrektur 2: ein "Vorgang kopieren"/"Als Mustervorgang speichern" darf die
    Vertragsherkunft nicht mitschleppen, sonst erschienen die Berichte des Duplikats fälschlich
    in list_contract_history() des Original-Vertrags."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    source = Project(project_number="P-TEST-0050", name="Quelle", customer_id=customer.id, property_id=prop.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(source); db.flush()
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today())
    db.add(ProjectProfile(project_id=source.id, category="Dach", source_maintenance_contract_id=contract["id"]))
    db.commit()
    db.refresh(source)

    copy = duplicate_project(db, source, as_template=False)
    assert copy.profile is not None
    assert copy.profile.category == "Dach"
    assert copy.profile.source_maintenance_contract_id is None
    assert copy.profile.source_maintenance_contract_item_id is None


def test_delete_window_blocks_while_referenced_by_item_then_succeeds():
    db = db_session()
    _enable_roof_area_items(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today())
    item = create_contract_item(db, contract["id"], area["id"], window["id"])

    try:
        delete_window(db, window["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass

    delete_contract_item(db, item["id"])
    assert delete_window(db, window["id"]) is True


def test_next_window_opening_handles_year_wraparound_window():
    window = MaintenanceWindow(label="Winter", month_from=12, month_to=2)
    assert _next_window_opening(window, date(2027, 1, 15)) == date(2027, 12, 1)
    assert _next_window_opening(window, date(2026, 12, 15)) == date(2027, 12, 1)


def test_window_close_date_handles_non_wraparound_and_wraparound_windows():
    non_wrap = MaintenanceWindow(label="Frühjahr", month_from=3, month_to=5)
    assert _window_close_date(non_wrap, date(2026, 3, 1)) == date(2026, 5, 31)

    wrap = MaintenanceWindow(label="Winter", month_from=12, month_to=2)
    assert _window_close_date(wrap, date(2026, 12, 1)) == date(2027, 2, 28)  # 2027 kein Schaltjahr


def test_create_contract_item_rejects_roof_area_from_other_property():
    db = db_session()
    _enable_roof_area_items(db)
    customer, prop = make_customer_and_property(db)
    other_customer, other_prop = make_customer_and_property(db)
    area = create_roof_area(db, other_prop.id, "Fremde Fläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today())
    try:
        create_contract_item(db, contract["id"], area["id"], window["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Objekt" in str(exc)


def test_create_contract_item_rejects_contract_without_property():
    db = db_session()
    _enable_roof_area_items(db)
    customer = Customer(name="Kunde ohne Objekt", last_name="Kunde ohne Objekt")
    db.add(customer); db.commit()
    contract = create_contract(db, customer.id, None, "Vertrag ohne Objekt", 12, date.today())
    window = create_window(db, "Herbst", 10, 11)
    try:
        create_contract_item(db, contract["id"], 999, window["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Objekt" in str(exc)


def test_delete_contract_cascades_items_without_reports_but_blocks_when_signed_report_exists(tmp_path):
    service_reports.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    _enable_roof_area_items(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag ohne Bericht", 12, date.today())
    item = create_contract_item(db, contract["id"], area["id"], window["id"])

    assert delete_contract(db, contract["id"]) is True
    assert db.get(MaintenanceContractItem, item["id"]) is None  # Cascade, kein toter Rest

    template = make_template_project(db, customer, prop, number="P-TEMPLATE-0099")
    contract2 = create_contract(db, customer.id, prop.id, "Vertrag mit Bericht", 12, date.today(),
                                 template_project_id=template.id)
    result = create_project_from_contract(db, contract2["id"])
    order = Order(
        order_number="AUF-TEST-0102", project_id=result["project_id"], source_quote_id=1,
        quote_number_snapshot="A-TEST-0102", title="Testauftrag", customer_name=customer.name,
    )
    db.add(order); db.commit()
    report = create_report(db, order.id, "wartung")
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Monteur Mustermann")

    try:
        delete_contract(db, contract2["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "archiviert" in str(exc)


def test_delete_roof_area_blocks_while_used_as_contract_item():
    db = db_session()
    _enable_roof_area_items(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche")
    window = create_window(db, "Herbst", 10, 11)
    contract = create_contract(db, customer.id, prop.id, "Vertrag", 12, date.today())
    create_contract_item(db, contract["id"], area["id"], window["id"])

    try:
        delete_roof_area(db, area["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
