"""Version 1.8.6 -- "Rechnung aus Aufwand" erfasst alle Zeitbuchungen des Auftrags.

Bis 1.8.5 holte post_invoice_from_time_entries() die Buchungen über list_entries() ohne
limit-Angabe: der Vorgabewert 500 schnitt die ältesten Buchungen still ab, die Rechnung fiel zu
niedrig aus, ohne Meldung."""

from datetime import date, timedelta
from decimal import Decimal

from app.models import Employee, TimeEntry
from app.routers.invoices import router as invoices_router
from tests.test_v133_invoices import make_order_with_item


def test_aufwand_invoice_contains_all_hours_of_501_entries(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    emp = Employee(employee_number="T-1", first_name="Max", last_name="Muster",
                    employee_group="gewerblich", hourly_wage="25", active=True)
    db.add(emp); db.commit()

    def booking(work_date, activity):
        return TimeEntry(employee_id=emp.id, project_id=order.project_id, order_id=order.id,
                          work_date=work_date, activity=activity, hours=Decimal("1.00"), status="booked")

    # Die älteste Buchung trägt eine eigene Tätigkeit: list_entries() sortiert neueste zuerst,
    # genau diese 501. Zeile fiel bisher hinter die Grenze.
    db.add(booking(date(2026, 1, 1), "Erste Begehung"))
    db.add_all(booking(date(2026, 1, 2) + timedelta(days=i // 5), "Reparatur") for i in range(500))
    db.commit()

    client = router_test_client(db, invoices_router)
    resp = client.post(f"/api/orders/{order.id}/invoices/aus-zeitbuchungen", json={"due_date": None})
    assert resp.status_code == 200, resp.text

    items = resp.json()["items"]
    assert sum(Decimal(str(i["ist_quantity"])) for i in items if i["unit"] == "Std.") == Decimal("501")
    assert any(i["short_text"] == "Erste Begehung" for i in items)
