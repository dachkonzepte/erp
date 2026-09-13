"""Version 1.2.20 -- Punkt 1: Weg zum Einsatzbericht. order_to_dict() liefert jetzt customer_id
(für die Kunde-Verlinkung auf service_reports.html), und OrderListOut trägt einen
service_report_count (für die neue Spalte in project_folder.html)."""

from app.orders import load_order, order_to_dict
from app.service_reports import count_reports_for_order, create_report
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session


def test_order_to_dict_includes_customer_id():
    db = db_session()
    order, _ = make_order_with_item(db)
    loaded = load_order(db, order.id)
    values = order_to_dict(loaded, db)
    assert values["customer_id"] == loaded.project.customer_id


def test_count_reports_for_order_reflects_created_reports():
    db = db_session()
    order, _ = make_order_with_item(db)
    assert count_reports_for_order(db, order.id) == 0

    create_report(db, order.id, "rapport")
    assert count_reports_for_order(db, order.id) == 1

    create_report(db, order.id, "rapport")
    assert count_reports_for_order(db, order.id) == 2


def test_list_project_orders_route_reports_service_report_count(threaded_db_session, router_test_client):
    from app.routers.projects import router as projects_router

    db = threaded_db_session
    order, _ = make_order_with_item(db)
    create_report(db, order.id, "rapport")
    client = router_test_client(db, projects_router)

    resp = client.get(f"/api/projects/{order.project_id}/orders")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["service_report_count"] == 1
