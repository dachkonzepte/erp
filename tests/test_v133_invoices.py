from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.invoices import (
    add_invoice_item,
    compute_invoice_totals,
    create_abschlag_leistungsstand,
    create_abschlag_pauschal,
    create_schlussrechnung,
    create_storno_draft,
    finalize_and_send_invoice,
    is_invoice_editable,
    mark_invoice_paid,
    remove_invoice_item,
    update_invoice_item,
    visible_items,
)
from app.models import Order, OrderItem, Customer, Project
from app.project_pipeline_columns import default_pipeline_column_id


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_order_with_item(
    db, quantity=Decimal("100"), unit_price=Decimal("50"), vat_rate=Decimal("19.00"),
    *, caseworker_employee_id=None, project_manager_employee_id=None,
):
    """Auftrag mit genau EINER Position, direkt konstruiert (nicht über die
    Angebots-/Import-Kette) -- für exakte, von Hand nachvollziehbare Beträge.

    caseworker_employee_id/project_manager_employee_id (seit 1.3.10, optional, Default None wie
    bisher): für Tests, die die Meta-Zeile "Sachbearbeiter"/"Projektleiter" im Auftrags-PDF
    pruefen wollen (order_pdf.py) -- der Aufrufer legt den Employee-Datensatz selbst an und
    reicht dessen id durch, dieser Helfer erzeugt keinen eigenen."""
    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0001", name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-TEST-0001", project_id=project.id, source_quote_id=1, quote_number_snapshot="A-TEST-0001",
        title="Testauftrag", vat_rate=vat_rate, customer_name="Test Kunde", customer_number="K-0001",
        caseworker_employee_id=caseworker_employee_id, project_manager_employee_id=project_manager_employee_id,
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
# Grundlegende Erzeugung
# ---------------------------------------------------------------------------

def test_create_abschlag_pauschal_hat_projektions_position_und_keine_nummer():
    """Seit 1.3.24 (CLAUDE.md "Pauschale Abschlagsrechnung ohne Positionstabelle"): genau eine
    InvoiceItem-Zeile, die den Betrag/die Bezeichnung nur SPIEGELT -- lump_sum_net bleibt die
    Quelle der Wahrheit für die Summenberechnung, siehe compute_invoice_totals() unten."""
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("3000"), progress_description="1. Abschlag")
    assert invoice.status == "entwurf"
    assert invoice.invoice_number is None
    assert invoice.invoice_type == "abschlag_pauschal"
    assert len(invoice.items) == 1
    item = invoice.items[0]
    assert item.short_text == "1. Abschlag"
    assert item.unit_price == Decimal("3000")
    assert item.billed_total == Decimal("3000")
    assert item.unit == "pschl."
    totals = compute_invoice_totals(invoice)
    assert totals["net_total"] == Decimal("3000")
    assert totals["vat_total"] == Decimal("570.00")
    assert totals["gross_total"] == Decimal("3570.00")


def test_create_abschlag_leistungsstand_kopiert_position_mit_ist_null():
    db = db_session()
    order, order_item = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    invoice = create_abschlag_leistungsstand(db, order)
    assert len(invoice.items) == 1
    item = invoice.items[0]
    assert item.source_order_item_id == order_item.id
    assert item.soll_quantity == Decimal("100")
    assert item.ist_quantity == Decimal("0")  # noch nie abgerechnet
    assert item.billed_quantity == Decimal("0")
    assert item.billed_total == Decimal("0")


def test_create_schlussrechnung_geht_von_voller_fertigstellung_aus():
    db = db_session()
    order, order_item = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    invoice = create_schlussrechnung(db, order)
    item = invoice.items[0]
    assert item.ist_quantity == Decimal("100")  # = soll, Standardannahme "fertig"
    assert item.billed_quantity == Decimal("100")
    assert item.billed_total == Decimal("5000")


def test_position_ohne_include_in_total_wird_nicht_kopiert():
    db = db_session()
    order, _ = make_order_with_item(db)
    db.add(OrderItem(
        order_id=order.id, sort_order=20, position_number="2", short_text="Optionale Position",
        quantity=Decimal("5"), unit="Stk", unit_price=Decimal("10"), include_in_total=False,
    ))
    db.commit()
    invoice = create_schlussrechnung(db, order)
    assert len(invoice.items) == 1  # nur die reguläre Position, nicht die optionale


# ---------------------------------------------------------------------------
# Das Kernstück: kumulierte Soll/Ist-Abrechnung über mehrere Rechnungen
# ---------------------------------------------------------------------------

def test_kumulierte_abrechnung_ueber_zwei_abschlaege_und_schlussrechnung():
    """100 m² à 50€ = 5000€ netto Auftragswert. 1. Abschlag auf 40 m²,
    2. Abschlag auf insgesamt 70 m² (davon werden nur die neuen 30
    abgerechnet), Schlussrechnung auf die verbleibenden 30 m². Summe über
    alle drei Rechnungen muss exakt 5000€ ergeben."""
    db = db_session()
    order, order_item = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))

    # 1. Abschlag: Ist auf 40 setzen
    inv1 = create_abschlag_leistungsstand(db, order)
    item1 = inv1.items[0]
    update_invoice_item(db, inv1, item1, ist_quantity=Decimal("40"))
    assert item1.billed_quantity == Decimal("40")  # 40 - 0 (noch nichts vorher)
    assert item1.billed_total == Decimal("2000")
    finalize_and_send_invoice(db, inv1)
    assert inv1.invoice_number is not None
    assert inv1.invoice_number.startswith("R-")

    # 2. Abschlag: sollte mit dem kumulierten Stand aus Rechnung 1 vorbelegt sein (40)
    inv2 = create_abschlag_leistungsstand(db, order)
    item2 = inv2.items[0]
    assert item2.ist_quantity == Decimal("40")  # Vorbelegung mit letztem kumulierten Stand
    assert item2.billed_quantity == Decimal("0")  # noch keine Änderung vorgenommen
    # Jetzt auf insgesamt 70 erhöhen
    update_invoice_item(db, inv2, item2, ist_quantity=Decimal("70"))
    assert item2.billed_quantity == Decimal("30")  # 70 - 40, NICHT 70
    assert item2.billed_total == Decimal("1500")
    finalize_and_send_invoice(db, inv2)

    # Schlussrechnung: Vorbelegung mit voller Menge (100), abgerechnet wird der Rest
    inv3 = create_schlussrechnung(db, order)
    item3 = inv3.items[0]
    assert item3.ist_quantity == Decimal("100")
    assert item3.billed_quantity == Decimal("30")  # 100 - 70
    assert item3.billed_total == Decimal("1500")
    finalize_and_send_invoice(db, inv3)

    # Summe über alle drei Rechnungen muss den vollen Auftragswert ergeben
    total_billed = item1.billed_total + item2.billed_total + item3.billed_total
    assert total_billed == Decimal("5000")


def test_entwuerfe_zaehlen_nicht_als_vorheriger_stand():
    """Ein noch nicht versendeter Entwurf darf die Berechnung einer zweiten,
    parallel begonnenen Rechnung nicht beeinflussen."""
    db = db_session()
    order, order_item = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))
    inv1 = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, inv1, inv1.items[0], ist_quantity=Decimal("40"))
    # inv1 bleibt Entwurf, wird NICHT versendet

    inv2 = create_abschlag_leistungsstand(db, order)
    item2 = inv2.items[0]
    assert item2.ist_quantity == Decimal("0")  # inv1 ist nur Entwurf, zählt nicht
    assert item2.billed_quantity == Decimal("0")


# ---------------------------------------------------------------------------
# Versenden, Bezahlen, Bearbeitungssperre
# ---------------------------------------------------------------------------

def test_finalize_vergibt_nummer_und_sperrt_bearbeitung():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1000"), progress_description=None)
    assert is_invoice_editable(invoice) is True
    finalize_and_send_invoice(db, invoice)
    assert invoice.status == "versendet"
    assert invoice.invoice_number is not None
    assert is_invoice_editable(invoice) is False

    try:
        add_invoice_item(db, invoice, short_text="x", long_text="", unit="Stk", unit_price=Decimal("1"), ist_quantity=Decimal("1"))
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass


def test_finalize_kann_nicht_zweimal_aufgerufen_werden():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1000"), progress_description=None)
    finalize_and_send_invoice(db, invoice)
    try:
        finalize_and_send_invoice(db, invoice)
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass


def test_invoice_numbers_sind_fortlaufend_ueber_mehrere_rechnungen():
    db = db_session()
    order, _ = make_order_with_item(db)
    inv1 = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("100"), progress_description=None)
    inv2 = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("200"), progress_description=None)
    finalize_and_send_invoice(db, inv1)
    finalize_and_send_invoice(db, inv2)
    assert inv1.invoice_number != inv2.invoice_number


def test_mark_paid_nur_ab_versendet():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1000"), progress_description=None)
    try:
        mark_invoice_paid(db, invoice)
        assert False, "hätte ValueError auslösen müssen (noch Entwurf)"
    except ValueError:
        pass
    finalize_and_send_invoice(db, invoice)
    mark_invoice_paid(db, invoice, paid_date=date(2026, 10, 1))
    assert invoice.status == "bezahlt"
    assert invoice.paid_date == date(2026, 10, 1)


# ---------------------------------------------------------------------------
# Positionen hinzufügen/bearbeiten/entfernen (Nachträge)
# ---------------------------------------------------------------------------

def test_nachtrag_ohne_auftragsbezug_wird_voll_abgerechnet():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    nachtrag = add_invoice_item(
        db, invoice, short_text="Zusätzliche Kaminverblechung", long_text="", unit="Stk",
        unit_price=Decimal("250"), ist_quantity=Decimal("2"),
    )
    assert nachtrag.source_order_item_id is None
    assert nachtrag.billed_quantity == Decimal("2")  # kein vorheriger Stand, volle Menge
    assert nachtrag.billed_total == Decimal("500")


def test_remove_invoice_item():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    item_id = invoice.items[0].id
    assert remove_invoice_item(db, invoice, item_id) is True
    assert len(invoice.items) == 0
    assert remove_invoice_item(db, invoice, item_id) is False  # schon weg


def test_update_invoice_item_unit_price_aendert_billed_total():
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("10"), unit_price=Decimal("50"))
    invoice = create_schlussrechnung(db, order)
    item = invoice.items[0]
    assert item.billed_total == Decimal("500")  # 10 * 50
    update_invoice_item(db, invoice, item, unit_price=Decimal("60"))
    assert item.billed_total == Decimal("600")  # 10 * 60, neu berechnet


# ---------------------------------------------------------------------------
# Ist=0 Anzeigeregel
# ---------------------------------------------------------------------------

def test_visible_items_blendet_ist_null_aus():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_leistungsstand(db, order)  # Ist startet bei 0
    assert len(invoice.items) == 1
    assert visible_items(invoice) == []  # Ist=0 -> nicht anzeigen
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=Decimal("10"))
    assert len(visible_items(invoice)) == 1


# ---------------------------------------------------------------------------
# Storno
# ---------------------------------------------------------------------------

def test_storno_kehrt_betraege_um_und_sperrt_original_erst_beim_versenden():
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("10"), unit_price=Decimal("100"))
    original = create_schlussrechnung(db, order)
    finalize_and_send_invoice(db, original)
    assert original.status == "versendet"

    storno = create_storno_draft(db, original)
    assert storno.status == "entwurf"
    assert storno.invoice_type == "storno"
    assert storno.items[0].billed_total == Decimal("-1000")
    # Original bleibt unangetastet, solange der Storno-Entwurf nicht versendet ist
    assert original.status == "versendet"

    finalize_and_send_invoice(db, storno)
    assert storno.status == "versendet"
    assert storno.invoice_number is not None
    assert storno.invoice_number != original.invoice_number
    db.refresh(original)
    assert original.status == "storniert"


def test_stornierte_rechnung_zaehlt_nicht_mehr_als_vorheriger_stand():
    """Nach einer Stornierung muss die kumulierte Berechnung wieder auf den
    Stand VOR der stornierten Rechnung zurückfallen."""
    db = db_session()
    order, order_item = make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"))

    inv1 = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, inv1, inv1.items[0], ist_quantity=Decimal("40"))
    finalize_and_send_invoice(db, inv1)

    storno = create_storno_draft(db, inv1)
    finalize_and_send_invoice(db, storno)  # inv1 ist jetzt storniert

    inv2 = create_abschlag_leistungsstand(db, order)
    item2 = inv2.items[0]
    assert item2.ist_quantity == Decimal("0")  # inv1 zählt nicht mehr, zurück auf 0


def test_storno_nur_fuer_versendete_oder_bezahlte_rechnungen():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("100"), progress_description=None)
    try:
        create_storno_draft(db, invoice)
        assert False, "hätte ValueError auslösen müssen (noch Entwurf)"
    except ValueError:
        pass
