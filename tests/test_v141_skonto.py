from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.invoices import (
    create_schlussrechnung,
    create_storno_draft,
    finalize_and_send_invoice,
    format_payment_terms_sentence,
    update_invoice_payment_term,
)
from app.models import Order, OrderItem, PaymentTerm, Customer, Project
from app.payment_terms import create_payment_term, update_payment_term


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_order_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"), vat_rate=Decimal("19.00"), payment_terms=None):
    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0001", name="Testprojekt", customer_id=customer.id)
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-TEST-0001", project_id=project.id, source_quote_id=1, quote_number_snapshot="A-TEST-0001",
        title="Testauftrag", vat_rate=vat_rate, customer_name="Test Kunde", customer_number="K-0001",
        payment_terms=payment_terms,
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
# Validierung beim Anlegen/Bearbeiten einer Zahlungsbedingung
# ---------------------------------------------------------------------------

def test_skonto_prozent_ohne_tage_wird_abgelehnt():
    db = db_session()
    try:
        create_payment_term(db, "Test", 14, skonto_percent=Decimal("2"), skonto_days=None)
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass


def test_skonto_tage_ohne_prozent_wird_abgelehnt():
    db = db_session()
    try:
        create_payment_term(db, "Test", 14, skonto_percent=None, skonto_days=7)
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass


def test_skonto_frist_laenger_als_zahlungsfrist_wird_abgelehnt():
    db = db_session()
    try:
        create_payment_term(db, "Test", 14, skonto_percent=Decimal("2"), skonto_days=20)
        assert False, "hätte ValueError auslösen müssen (20 > 14)"
    except ValueError:
        pass


def test_skonto_gueltig_wird_gespeichert():
    db = db_session()
    term = create_payment_term(db, "14 Tage netto, 2% bei 7 Tagen", 14, skonto_percent=Decimal("2.00"), skonto_days=7)
    assert term.skonto_percent == Decimal("2.00")
    assert term.skonto_days == 7


def test_ohne_skonto_bleibt_erlaubt():
    db = db_session()
    term = create_payment_term(db, "30 Tage netto", 30)
    assert term.skonto_percent is None
    assert term.skonto_days is None


def test_update_payment_term_validiert_ebenfalls():
    db = db_session()
    term = create_payment_term(db, "14 Tage netto", 14)
    try:
        update_payment_term(db, term.id, "14 Tage netto", 14, skonto_percent=Decimal("2"), skonto_days=None)
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass
    # gültige Aktualisierung funktioniert weiterhin
    updated = update_payment_term(db, term.id, "14 Tage netto", 14, skonto_percent=Decimal("3"), skonto_days=10)
    assert updated.skonto_percent == Decimal("3")
    assert updated.skonto_days == 10


# ---------------------------------------------------------------------------
# Automatisch generierter Fälligkeits-/Skontosatz
# ---------------------------------------------------------------------------

def test_formulierung_ohne_skonto():
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("10"), unit_price=Decimal("100"))
    invoice = create_schlussrechnung(db, order, due_date=date(2026, 9, 18))
    invoice.invoice_date = date(2026, 9, 4)
    sentence = format_payment_terms_sentence(invoice)
    assert sentence == "Zahlbar rein netto bis zum 18.09.2026."


def test_formulierung_mit_skonto_rechnet_korrekt():
    db = db_session()
    order, _ = make_order_with_item(db, quantity=Decimal("10"), unit_price=Decimal("100"))  # 1000€ netto, 19% -> 1190€ brutto
    invoice = create_schlussrechnung(db, order, due_date=date(2026, 9, 18))
    invoice.invoice_date = date(2026, 9, 4)
    invoice.skonto_percent = Decimal("2.00")
    invoice.skonto_days = 7
    sentence = format_payment_terms_sentence(invoice)
    # 1190 * 2% = 23,80 €; Skontodatum = 4.9. + 7 Tage = 11.9.
    assert "11.09.2026" in sentence
    assert "2 % Skonto" in sentence
    assert "23,80 €" in sentence
    assert sentence == "Zahlbar rein netto bis zum 18.09.2026. Bei Zahlung bis zum 11.09.2026 gewähren wir 2 % Skonto, das entspricht 23,80 €."


def test_formulierung_ohne_due_date_ist_leer():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    invoice.due_date = None
    assert format_payment_terms_sentence(invoice) == ""


# ---------------------------------------------------------------------------
# Skonto fließt korrekt vom Auftrag / von der Zahlungsbedingung in die Rechnung
# ---------------------------------------------------------------------------

def test_auftrags_zahlungsbedingung_mit_skonto_fliesst_in_rechnung():
    db = db_session()
    create_payment_term(db, "14 Tage netto, 2% Skonto", 14, skonto_percent=Decimal("2.00"), skonto_days=7)
    order, _ = make_order_with_item(db, payment_terms="14 Tage netto, 2% Skonto")
    invoice = create_schlussrechnung(db, order)
    assert invoice.skonto_percent == Decimal("2.00")
    assert invoice.skonto_days == 7


def test_zahlungsbedingung_ohne_skonto_hat_kein_skonto_auf_rechnung():
    db = db_session()
    create_payment_term(db, "30 Tage netto", 30)
    order, _ = make_order_with_item(db, payment_terms="30 Tage netto")
    invoice = create_schlussrechnung(db, order)
    assert invoice.skonto_percent is None
    assert invoice.skonto_days is None


def test_wechsel_der_zahlungsbedingung_auf_rechnung_aktualisiert_skonto():
    db = db_session()
    ohne_skonto = create_payment_term(db, "30 Tage netto", 30)
    mit_skonto = create_payment_term(db, "14 Tage netto, 3% Skonto", 14, skonto_percent=Decimal("3.00"), skonto_days=5)
    order, _ = make_order_with_item(db, payment_terms="30 Tage netto")
    invoice = create_schlussrechnung(db, order)
    assert invoice.skonto_percent is None

    update_invoice_payment_term(db, invoice, mit_skonto.id)
    assert invoice.skonto_percent == Decimal("3.00")
    assert invoice.skonto_days == 5
    assert invoice.payment_terms == "14 Tage netto, 3% Skonto"

    # zurück auf eine Bedingung ohne Skonto -- muss Skonto korrekt wieder entfernen
    update_invoice_payment_term(db, invoice, ohne_skonto.id)
    assert invoice.skonto_percent is None
    assert invoice.skonto_days is None


def test_skonto_bleibt_nach_finalisieren_eingefroren_auch_wenn_zahlungsbedingung_spaeter_geaendert_wird():
    """Snapshot-Prinzip: eine bereits versendete Rechnung darf sich nicht
    rückwirkend ändern, nur weil die zugrunde liegende Zahlungsbedingung in
    den Einstellungen später bearbeitet wird."""
    db = db_session()
    term = create_payment_term(db, "14 Tage netto, 2% Skonto", 14, skonto_percent=Decimal("2.00"), skonto_days=7)
    order, _ = make_order_with_item(db, payment_terms="14 Tage netto, 2% Skonto")
    invoice = create_schlussrechnung(db, order)
    finalize_and_send_invoice(db, invoice)
    assert invoice.skonto_percent == Decimal("2.00")

    update_payment_term(db, term.id, "14 Tage netto, 2% Skonto", 14, skonto_percent=Decimal("5.00"), skonto_days=7)

    db.refresh(invoice)
    assert invoice.skonto_percent == Decimal("2.00")  # unverändert, nicht die neuen 5%


# ---------------------------------------------------------------------------
# Eigene Textvorlage (seit 1.0.42)
# ---------------------------------------------------------------------------

def test_eigene_textvorlage_ersetzt_platzhalter():
    db = db_session()
    create_payment_term(
        db, "14 Tage netto, 2% Skonto", 14, skonto_percent=Decimal("2.00"), skonto_days=7,
        text_template="Bitte zahlen Sie bis {faelligkeitsdatum}. Bei Zahlung bis {skontodatum} sparen Sie {skontoprozent}% ({skontobetrag} €).",
    )
    order, _ = make_order_with_item(db, quantity=Decimal("10"), unit_price=Decimal("100"), payment_terms="14 Tage netto, 2% Skonto")
    invoice = create_schlussrechnung(db, order, due_date=date(2026, 9, 18))
    invoice.invoice_date = date(2026, 9, 4)
    sentence = format_payment_terms_sentence(invoice)
    assert sentence == "Bitte zahlen Sie bis 18.09.2026. Bei Zahlung bis 11.09.2026 sparen Sie 2% (23,80 €)."


def test_ohne_eigene_textvorlage_bleibt_der_standardsatz():
    db = db_session()
    create_payment_term(db, "30 Tage netto", 30)
    order, _ = make_order_with_item(db, payment_terms="30 Tage netto")
    invoice = create_schlussrechnung(db, order, due_date=date(2026, 9, 18))
    sentence = format_payment_terms_sentence(invoice)
    assert sentence == "Zahlbar rein netto bis zum 18.09.2026."


def test_textvorlage_fliesst_beim_wechsel_der_zahlungsbedingung_mit():
    db = db_session()
    ohne_vorlage = create_payment_term(db, "30 Tage netto", 30)
    mit_vorlage = create_payment_term(db, "14 Tage netto", 14, text_template="Fällig: {faelligkeitsdatum}.")
    order, _ = make_order_with_item(db, payment_terms="30 Tage netto")
    invoice = create_schlussrechnung(db, order, due_date=date(2026, 9, 18))
    assert invoice.payment_terms_text_template is None

    update_invoice_payment_term(db, invoice, mit_vorlage.id)
    assert invoice.payment_terms_text_template == "Fällig: {faelligkeitsdatum}."

    update_invoice_payment_term(db, invoice, ohne_vorlage.id)
    assert invoice.payment_terms_text_template is None


# ---------------------------------------------------------------------------
# Entwurf-Rechnungen löschen (seit 1.0.47)
# ---------------------------------------------------------------------------

def test_entwurf_kann_geloescht_werden():
    from app.invoices import delete_invoice_draft, get_invoice

    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    invoice_id = invoice.id
    delete_invoice_draft(db, invoice)
    assert get_invoice(db, invoice_id) is None


def test_finalisierte_rechnung_kann_nicht_geloescht_werden():
    from app.invoices import delete_invoice_draft

    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    finalize_and_send_invoice(db, invoice)
    try:
        delete_invoice_draft(db, invoice)
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass


def test_bezahlte_rechnung_kann_nicht_geloescht_werden():
    from app.invoices import delete_invoice_draft, mark_invoice_paid

    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    finalize_and_send_invoice(db, invoice)
    mark_invoice_paid(db, invoice)
    try:
        delete_invoice_draft(db, invoice)
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass


def test_stornierte_rechnung_kann_nicht_geloescht_werden():
    from app.invoices import delete_invoice_draft

    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    finalize_and_send_invoice(db, invoice)
    storno = create_storno_draft(db, invoice)
    finalize_and_send_invoice(db, storno)
    db.refresh(invoice)
    assert invoice.status == "storniert"
    try:
        delete_invoice_draft(db, invoice)
        assert False, "hätte ValueError auslösen müssen"
    except ValueError:
        pass


def test_storno_entwurf_loeschen_laesst_original_unberuehrt():
    """Das Original wird erst beim tatsächlichen Versand des Storno auf
    'storniert' gesetzt -- solange der Storno-Entwurf nur existiert (aber
    noch nicht versendet wurde), muss er löschbar sein, ohne dass sich am
    Original irgendetwas ändert."""
    from app.invoices import delete_invoice_draft

    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    finalize_and_send_invoice(db, invoice)
    storno = create_storno_draft(db, invoice)
    assert storno.status == "entwurf"

    delete_invoice_draft(db, storno)

    db.refresh(invoice)
    assert invoice.status == "versendet"  # unverändert, nicht storniert


def test_geloeschte_rechnungspositionen_werden_mitentfernt():
    """cascade='all, delete-orphan' auf Invoice.items -- Positionen dürfen
    nach dem Löschen der Rechnung nicht als Datenleichen zurückbleiben."""
    from app.invoices import delete_invoice_draft
    from app.models import InvoiceItem

    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    invoice_id = invoice.id
    item_count_before = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).count()
    assert item_count_before > 0

    delete_invoice_draft(db, invoice)

    item_count_after = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).count()
    assert item_count_after == 0


# ---------------------------------------------------------------------------
# Soll/Ist-Stunden-Vergleich in der Projekt-Kennzahlen-Sektion (seit 1.0.49)
# ---------------------------------------------------------------------------

def test_planned_hours_wird_korrekt_aus_kalkulationssnapshot_berechnet():
    """Bestätigt die Annahme, auf der die neue Projekt-Kennzahl 'Soll-Stunden'
    aufbaut: planned_hours() (bereits bestehend, aus der Arbeitsvorbereitung)
    summiert (Baustellen- + Werkstattzeit) / 60 * Menge über alle Positionen."""
    from app.work_preparation import planned_hours
    from app.models import OrderItemCalculationSnapshot

    db = db_session()
    order, item = make_order_with_item(db, quantity=Decimal("10"))
    snapshot = OrderItemCalculationSnapshot(
        order_item_id=item.id, site_time_minutes=Decimal("30"), workshop_time_minutes=Decimal("15"),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(order)

    # (30 + 15) / 60 * 10 = 7,5 Stunden
    assert planned_hours(order) == Decimal("7.50")


def test_order_list_out_liefert_soll_stunden_fuer_projekt_kennzahlen():
    import pathlib
    schemas = (pathlib.Path(__file__).parents[1] / "app" / "schemas.py").read_text(encoding="utf-8")
    match = schemas[schemas.index("class OrderListOut"):]
    match = match[:match.index("class ", 10)]
    assert "planned_hours" in match
