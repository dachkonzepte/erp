from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.invoices import create_schlussrechnung, update_invoice_tax_key, create_storno_draft
from app.models import Order, OrderItem, Quote, QuoteItem, Project, Customer
from app.project_pipeline_columns import default_pipeline_column_id
from app.orders import order_to_dict, update_order_tax_key
from app.projects import quote_to_dict, update_quote_tax_key
from app.tax_keys import create_tax_key, update_tax_key


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"), vat_rate=Decimal("19.00")):
    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0001", name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-TEST-0001", project_id=project.id, source_quote_id=1, quote_number_snapshot="A-TEST-0001",
        title="Testauftrag", vat_rate=vat_rate, customer_name="Test Kunde", customer_number="K-0001",
    )
    db.add(order)
    db.flush()
    item = OrderItem(
        order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
        quantity=quantity, unit="m²", unit_price=unit_price,
    )
    db.add(item)
    db.commit()
    db.refresh(order)
    return order, item


def make_quote_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"), vat_rate=Decimal("19.00")):
    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0001", name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    quote = Quote(quote_number="A-TEST-0001", project_id=project.id, title="Testangebot", vat_rate=vat_rate)
    db.add(quote)
    db.flush()
    item = QuoteItem(quote_id=quote.id, sort_order=10, position_number="1", short_text="Dacheindeckung", quantity=quantity, unit="m²", unit_price=unit_price)
    db.add(item)
    db.commit()
    db.refresh(quote)
    return quote, item


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def test_steuerschluessel_anlegen():
    db = db_session()
    key = create_tax_key(db, "§13b Bauleistungen", Decimal("0.00"), "Steuerschuldnerschaft des Leistungsempfängers.")
    assert key.vat_rate == Decimal("0.00")
    assert key.notice_text == "Steuerschuldnerschaft des Leistungsempfängers."


def test_steuerschluessel_bearbeiten():
    db = db_session()
    key = create_tax_key(db, "Privat", Decimal("19.00"))
    updated = update_tax_key(db, key.id, "Privat (neu)", Decimal("19.00"), "Neuer Text")
    assert updated.label == "Privat (neu)"
    assert updated.notice_text == "Neuer Text"


# ---------------------------------------------------------------------------
# Kritisch: Auswirkung auf die tatsächliche Berechnung (Lösung B)
# ---------------------------------------------------------------------------

def test_13b_steuerschluessel_setzt_mwst_beim_auftrag_auf_null():
    db = db_session()
    key_13b = create_tax_key(db, "§13b Bauleistungen", Decimal("0.00"), "Steuerschuldnerschaft des Leistungsempfängers gemäß § 13b UStG.")
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"), vat_rate=Decimal("19.00"))
    data_vorher = order_to_dict(order, db)
    assert data_vorher["net_total"] == Decimal("5000.00")
    assert data_vorher["vat_total"] == Decimal("950.00")
    assert data_vorher["gross_total"] == Decimal("5950.00")

    update_order_tax_key(db, order, key_13b.id)

    data_nachher = order_to_dict(order, db)
    assert order.vat_rate == Decimal("0.00")
    assert data_nachher["net_total"] == Decimal("5000.00")
    assert data_nachher["vat_total"] == Decimal("0.00")
    assert data_nachher["gross_total"] == Decimal("5000.00")  # Brutto = Netto, keine MwSt.
    assert data_nachher["tax_notice_text"] == "Steuerschuldnerschaft des Leistungsempfängers gemäß § 13b UStG."


def test_wechsel_zurueck_auf_normalen_steuerschluessel_stellt_mwst_wieder_her():
    db = db_session()
    key_13b = create_tax_key(db, "§13b Bauleistungen", Decimal("0.00"))
    key_privat = create_tax_key(db, "Privat", Decimal("19.00"))
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"), vat_rate=Decimal("19.00"))

    update_order_tax_key(db, order, key_13b.id)
    assert order_to_dict(order, db)["gross_total"] == Decimal("5000.00")

    update_order_tax_key(db, order, key_privat.id)
    data = order_to_dict(order, db)
    assert order.vat_rate == Decimal("19.00")
    assert data["gross_total"] == Decimal("5950.00")  # wieder normale 19%


def test_solar_steuerschluessel_beim_angebot():
    db = db_session()
    key_solar = create_tax_key(db, "Solar (Nullsteuersatz)", Decimal("0.00"), "Nullsteuersatz gemäß § 12 Abs. 3 UStG.")
    quote, _ = make_quote_with_item(db, quantity=Decimal("10"), unit_price=Decimal("1000"), vat_rate=Decimal("19.00"))
    data_vorher = quote_to_dict(quote)
    assert data_vorher["gross_total"] == Decimal("11900.00")  # 10000 * 1.19

    update_quote_tax_key(db, quote, key_solar.id)
    data_nachher = quote_to_dict(quote)
    assert data_nachher["net_total"] == Decimal("10000.00")
    assert data_nachher["gross_total"] == Decimal("10000.00")
    assert data_nachher["tax_notice_text"] == "Nullsteuersatz gemäß § 12 Abs. 3 UStG."


def test_steuerschluessel_bei_rechnung_setzt_mwst_und_friert_hinweistext_ein():
    db = db_session()
    key_13b = create_tax_key(db, "§13b Bauleistungen", Decimal("0.00"), "Reverse Charge Hinweis.")
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"), vat_rate=Decimal("19.00"))
    invoice = create_schlussrechnung(db, order)
    # Rechnung wurde ohne Steuerschlüssel erstellt (Auftrag hatte keinen) -> normale 19%
    assert invoice.vat_rate == Decimal("19.00")

    update_invoice_tax_key(db, invoice, key_13b.id)
    assert invoice.vat_rate == Decimal("0.00")
    assert invoice.tax_notice_text == "Reverse Charge Hinweis."

    # Hinweistext danach in den Einstellungen geändert -- darf die Rechnung nicht mehr beeinflussen (Snapshot-Prinzip)
    update_tax_key(db, key_13b.id, "§13b Bauleistungen", Decimal("0.00"), "Geänderter Text.")
    db.refresh(invoice)
    assert invoice.tax_notice_text == "Reverse Charge Hinweis."  # unverändert


def test_storno_uebernimmt_steuerschluessel_und_hinweistext_vom_original():
    db = db_session()
    key_13b = create_tax_key(db, "§13b Bauleistungen", Decimal("0.00"), "Reverse Charge Hinweis.")
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    invoice = create_schlussrechnung(db, order)
    update_invoice_tax_key(db, invoice, key_13b.id)
    from app.invoices import finalize_and_send_invoice
    finalize_and_send_invoice(db, invoice)

    storno = create_storno_draft(db, invoice)
    assert storno.tax_key_id == key_13b.id
    assert storno.tax_notice_text == "Reverse Charge Hinweis."
    assert storno.vat_rate == Decimal("0.00")


def test_ungueltiger_steuerschluessel_wird_abgelehnt():
    db = db_session()
    order, _ = make_order_with_item(db)
    try:
        update_order_tax_key(db, order, 9999)
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass
