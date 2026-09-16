from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.invoices import (
    compute_order_billing_progress,
    create_abschlag_pauschal,
    create_schlussrechnung,
    create_storno_draft,
    finalize_and_send_invoice,
)
from app.models import Order, OrderItem, Customer, Project
from app.project_pipeline_columns import default_pipeline_column_id
from app.orders import order_to_dict


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


# ---------------------------------------------------------------------------
# compute_order_billing_progress
# ---------------------------------------------------------------------------

def test_ohne_rechnungen_ist_alles_offen():
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))  # 5000€ netto, 19% -> 5950€ brutto
    progress = compute_order_billing_progress(db, order.id)
    assert progress["invoiced_net"] == Decimal("0")
    assert progress["invoiced_gross"] == Decimal("0")


def test_rechnungsentwurf_zaehlt_noch_nicht():
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1000"))  # bleibt im Entwurf, nicht finalisiert
    progress = compute_order_billing_progress(db, order.id)
    assert progress["invoiced_net"] == Decimal("0")
    assert progress["invoiced_gross"] == Decimal("0")


def test_finalisierte_abschlagsrechnung_zaehlt():
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"), vat_rate=Decimal("19.00"))
    invoice = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1000"))
    finalize_and_send_invoice(db, invoice)
    progress = compute_order_billing_progress(db, order.id)
    assert progress["invoiced_net"] == Decimal("1000.00")
    assert progress["invoiced_gross"] == Decimal("1190.00")  # 1000 * 1.19


def test_offener_betrag_ist_auftragswert_minus_abgerechnet():
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))  # 5000€ netto, 5950€ brutto
    invoice = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000"))
    finalize_and_send_invoice(db, invoice)
    data = order_to_dict(order, db)
    assert data["net_total"] == Decimal("5000.00")
    assert data["invoiced_net"] == Decimal("2000.00")
    assert data["open_net"] == Decimal("3000.00")
    assert data["gross_total"] == Decimal("5950.00")
    assert data["invoiced_gross"] == Decimal("2380.00")  # 2000 * 1.19
    assert data["open_gross"] == Decimal("3570.00")


def test_stornierte_rechnung_und_ihr_storno_heben_sich_gegenseitig_auf():
    """Kritischer Fall: eine stornierte Rechnung darf NICHT als negativer
    Betrag in die Summe einfließen (dann würde 'abgerechnet' bei einer
    stornierten Schlussrechnung fälschlich negativ werden) -- und die
    ursprüngliche, jetzt stornierte Rechnung darf nicht mehr mitzählen.
    Im Ergebnis muss der Effekt exakt null sein, als hätte die Rechnung nie
    stattgefunden."""
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    invoice = create_schlussrechnung(db, order)
    finalize_and_send_invoice(db, invoice)
    progress_vor_storno = compute_order_billing_progress(db, order.id)
    assert progress_vor_storno["invoiced_net"] == Decimal("5000.00")

    storno = create_storno_draft(db, invoice)
    finalize_and_send_invoice(db, storno)

    progress_nach_storno = compute_order_billing_progress(db, order.id)
    assert progress_nach_storno["invoiced_net"] == Decimal("0")
    assert progress_nach_storno["invoiced_gross"] == Decimal("0")


def test_mehrere_abschlagsrechnungen_summieren_sich():
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    inv1 = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1000"))
    finalize_and_send_invoice(db, inv1)
    inv2 = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1500"))
    finalize_and_send_invoice(db, inv2)
    progress = compute_order_billing_progress(db, order.id)
    assert progress["invoiced_net"] == Decimal("2500.00")
    assert progress["invoiced_gross"] == Decimal("2975.00")  # 2500 * 1.19


# ---------------------------------------------------------------------------
# Robusterer Zahlungsbedingungs-Abgleich (_find_matching_payment_term)
# ---------------------------------------------------------------------------

def test_abgleich_ignoriert_gross_kleinschreibung_und_leerzeichen():
    from app.invoices import _find_matching_payment_term
    from app.payment_terms import create_payment_term

    db = db_session()
    create_payment_term(db, "14 Tage netto", 14)
    match = _find_matching_payment_term(db, "  14 TAGE NETTO  ")
    assert match is not None
    assert match.days == 14


def test_abgleich_ohne_treffer_gibt_none():
    from app.invoices import _find_matching_payment_term
    from app.payment_terms import create_payment_term

    db = db_session()
    create_payment_term(db, "14 Tage netto", 14)
    assert _find_matching_payment_term(db, "Völlig andere Bezeichnung") is None


def test_auftrag_mit_leicht_abweichender_schreibweise_findet_trotzdem_die_zahlungsbedingung():
    """Der eigentlich gemeldete Fall: Auftrag trägt eine Zahlungsbedingung,
    die bis auf Groß-/Kleinschreibung oder Leerzeichen mit einer bestehenden
    PaymentTerm übereinstimmt -- Tage/Skonto müssen trotzdem übernommen
    werden, nicht auf den Standard zurückfallen."""
    from app.payment_terms import create_payment_term

    db = db_session()
    create_payment_term(db, "14 Tage netto", 14, skonto_percent=Decimal("2.00"), skonto_days=7)
    order, _ = make_order_with_item(db)
    order.payment_terms = "14 Tage Netto"  # abweichende Groß-/Kleinschreibung
    db.commit()
    invoice = create_schlussrechnung(db, order)
    assert invoice.due_date == invoice.invoice_date + timedelta(days=14)
    assert invoice.skonto_percent == Decimal("2.00")
