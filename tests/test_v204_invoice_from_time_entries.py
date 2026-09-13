from datetime import date
from decimal import Decimal

from app.calculation import get_or_create_settings
from app.invoices import compute_invoice_totals, create_invoice_from_time_entries
from app.models import Employee, TimeEntry
from tests.test_v133_invoices import db_session, make_order_with_item


def make_employee(db, first_name="Max", last_name="Muster", number="T-1"):
    emp = Employee(employee_number=number, first_name=first_name, last_name=last_name,
                    employee_group="gewerblich", hourly_wage="25", active=True)
    db.add(emp); db.commit()
    return emp


def booking(order, employee, hours, activity="Reparatur", status="booked"):
    """Setzt employee ueber die Beziehung (nicht nur employee_id), damit .employee auch auf
    einer noch nicht in der Session persistierten TimeEntry sofort verfuegbar ist -- in echten
    Aufrufen liefert list_entries() dasselbe bereits per selectinload(TimeEntry.employee)."""
    return TimeEntry(employee=employee, project_id=order.project_id, order_id=order.id,
                      work_date=date.today(), activity=activity, hours=Decimal(str(hours)), status=status)


def test_raises_without_any_bookable_time_entries():
    db = db_session()
    order, _ = make_order_with_item(db)
    try:
        create_invoice_from_time_entries(db, order, [], [])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_ignores_entries_that_are_not_booked():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp = make_employee(db)
    running = booking(order, emp, 2, status="running")
    try:
        create_invoice_from_time_entries(db, order, [running], [])
        assert False, "sollte ValueError auslösen (kein gebuchter Eintrag)"
    except ValueError:
        pass


def test_groups_by_employee_and_activity_and_uses_labor_rate():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp1 = make_employee(db, "Max", "Muster", "T-1")
    emp2 = make_employee(db, "Erika", "Eins", "T-2")
    entries = [
        booking(order, emp1, "2.5", activity="Dachrinne reparieren"),
        booking(order, emp1, "1.0", activity="Dachrinne reparieren"),
        booking(order, emp1, "0.5", activity="Material besorgen"),
        booking(order, emp2, "3.0", activity="Dachrinne reparieren"),
    ]
    db.add_all(entries)
    db.commit()  # wie list_entries() in Produktion: liest bereits committete, vollstaendig geladene Zeilen
    invoice = create_invoice_from_time_entries(db, order, entries, [])

    assert invoice.invoice_type == "aufwand"
    assert invoice.status == "entwurf"
    assert len(invoice.items) == 3

    rate = get_or_create_settings(db).labor_rate
    material_item = next(i for i in invoice.items if i.short_text == "Material besorgen")
    assert material_item.ist_quantity == Decimal("0.5")
    assert material_item.unit_price == rate
    max_item = next(i for i in invoice.items if i.short_text == "Dachrinne reparieren" and "Max Muster" in i.long_text)
    erika_item = next(i for i in invoice.items if i.short_text == "Dachrinne reparieren" and "Erika Eins" in i.long_text)
    assert max_item.ist_quantity == Decimal("3.5")
    assert erika_item.ist_quantity == Decimal("3.0")
    for item in invoice.items:
        assert item.unit == "Std."
        assert item.billed_quantity == item.ist_quantity  # keine Auftragsposition -> volle Menge abgerechnet


def test_invoice_totals_sum_all_items():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp = make_employee(db)
    invoice = create_invoice_from_time_entries(db, order, [booking(order, emp, "4.0")], [])
    rate = get_or_create_settings(db).labor_rate
    totals = compute_invoice_totals(invoice)
    assert totals["net_total"] == Decimal("4.0") * rate


def test_falls_back_to_generic_label_without_activity():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp = make_employee(db)
    invoice = create_invoice_from_time_entries(db, order, [booking(order, emp, "1.0", activity=None)], [])
    assert invoice.items[0].short_text == "Ausgeführte Arbeiten"


def test_router_endpoint_creates_invoice_from_booked_order_time_entries():
    from app.routers.invoices import post_invoice_from_time_entries
    from app.schemas import InvoiceCreateFromOrder

    db = db_session()
    order, _ = make_order_with_item(db)
    emp = make_employee(db)
    db.add(booking(order, emp, "2.0"))
    db.commit()

    result = post_invoice_from_time_entries(order.id, InvoiceCreateFromOrder(due_date=None), db=db)
    assert result["invoice_type"] == "aufwand"
    assert result["status"] == "entwurf"


def test_router_endpoint_returns_400_without_time_entries():
    from fastapi import HTTPException
    from app.routers.invoices import post_invoice_from_time_entries
    from app.schemas import InvoiceCreateFromOrder

    db = db_session()
    order, _ = make_order_with_item(db)
    try:
        post_invoice_from_time_entries(order.id, InvoiceCreateFromOrder(due_date=None), db=db)
        assert False, "sollte HTTPException auslösen"
    except HTTPException as exc:
        assert exc.status_code == 400
