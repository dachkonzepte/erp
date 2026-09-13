from decimal import Decimal

from app.models import Customer, Order, Project, Property
from app.service_reports import create_report, list_property_history, sign_report
from tests.test_v133_invoices import db_session
from tests.test_v203_service_reports import TINY_PNG


_next_source_quote_id = [0]


def make_order_for_property(db, prop, number):
    _next_source_quote_id[0] += 1
    order = Order(
        order_number=number, project_id=prop["project"].id, source_quote_id=_next_source_quote_id[0],
        quote_number_snapshot="A-" + number, title=f"Auftrag {number}", vat_rate=Decimal("19.00"),
        customer_name=prop["customer"].name,
    )
    db.add(order); db.commit()
    return order


def make_property_context(db, property_name="Hauptdach"):
    customer = Customer(name="Testkunde GmbH", last_name="Testkunde GmbH")
    db.add(customer); db.flush()
    prop = Property(customer_id=customer.id, name=property_name)
    db.add(prop); db.flush()
    project = Project(project_number="P-" + property_name, name="Projekt " + property_name,
                       customer_id=customer.id, property_id=prop.id)
    db.add(project); db.commit()
    return {"customer": customer, "property": prop, "project": project}


def test_no_history_without_a_linked_property():
    db = db_session()
    customer = Customer(name="Ohne Gebaeude", last_name="Ohne Gebaeude")
    db.add(customer); db.flush()
    project = Project(project_number="P-OHNE", name="Projekt ohne Gebäude", customer_id=customer.id)
    db.add(project); db.commit()
    order = Order(order_number="AUF-OHNE", project_id=project.id, source_quote_id=1, quote_number_snapshot="A-OHNE",
                  title="Auftrag ohne Gebäude", vat_rate=Decimal("19.00"), customer_name=customer.name)
    db.add(order); db.commit()
    assert list_property_history(db, order.id) == []


def test_only_signed_reports_from_other_orders_on_same_property_are_included():
    db = db_session()
    ctx = make_property_context(db)
    order_a = make_order_for_property(db, ctx, "AUF-A")
    order_b = make_order_for_property(db, ctx, "AUF-B")

    signed = create_report(db, order_a.id, "wartung", description="Dach kontrolliert")
    sign_report(db, signed["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test", customer_signature_png_bytes=TINY_PNG, customer_signature_name="Kunde A")
    draft = create_report(db, order_a.id, "rapport", description="Noch nicht fertig")

    history_from_b = list_property_history(db, order_b.id)
    assert len(history_from_b) == 1
    assert history_from_b[0]["id"] == signed["id"]
    assert history_from_b[0]["order_number"] == "AUF-A"
    assert draft["id"] not in [h["id"] for h in history_from_b]


def test_history_excludes_reports_from_the_same_order():
    db = db_session()
    ctx = make_property_context(db)
    order_a = make_order_for_property(db, ctx, "AUF-A")
    signed = create_report(db, order_a.id, "wartung")
    sign_report(db, signed["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test", customer_signature_png_bytes=TINY_PNG, customer_signature_name="Kunde A")
    assert list_property_history(db, order_a.id) == []


def test_history_ignores_orders_on_a_different_property():
    db = db_session()
    ctx1 = make_property_context(db, "Dach1")
    ctx2 = make_property_context(db, "Dach2")
    order_1 = make_order_for_property(db, ctx1, "AUF-1")
    order_2 = make_order_for_property(db, ctx2, "AUF-2")
    signed = create_report(db, order_1.id, "wartung")
    sign_report(db, signed["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test", customer_signature_png_bytes=TINY_PNG, customer_signature_name="Kunde 1")
    assert list_property_history(db, order_2.id) == []
