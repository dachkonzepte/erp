"""Version 1.3.24 -- Punkt 5: eine pauschale Abschlagsrechnung (invoice_type='abschlag_pauschal')
hatte bisher überhaupt keine Position -- weder im PDF noch auf dem Bildschirm ließ sich sehen,
WAS pauschal abgerechnet wird, nur der nackte Betrag. Neu: _sync_lump_sum_pauschal_item() in
app/invoices.py hält eine EINZIGE InvoiceItem-Zeile synchron zu lump_sum_net/progress_description
-- eine reine Projektion, niemals unabhängig editierbar (siehe Docstring dort und auf
InvoiceItem/Invoice.lump_sum_net in app/models.py). Die zwei bereits real existierenden,
finalisierten pauschalen Abschlagsrechnungen (R-2026-0001/-0002) behalten bewusst 0 Positionen --
siehe CLAUDE.md für die Begründung, warum hier keine Migration nachträglich Positionen erzeugt."""

from decimal import Decimal

from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text

from app.invoices import (
    add_invoice_item, create_abschlag_pauschal, remove_invoice_item, update_invoice_header,
    update_invoice_item,
)


def _make_draft_pauschal(db, lump_sum_net=Decimal("3000"), progress_description="1. Abschlag"):
    order, _ = make_order_with_item(db)
    return create_abschlag_pauschal(db, order, lump_sum_net=lump_sum_net, progress_description=progress_description)


# ---------------------------------------------------------------------------
# Projektion bleibt synchron, entsteht nie doppelt
# ---------------------------------------------------------------------------

def test_editing_lump_sum_and_description_updates_the_same_projected_item():
    db = db_session()
    invoice = _make_draft_pauschal(db)
    assert len(invoice.items) == 1
    first_item_id = invoice.items[0].id

    update_invoice_header(
        db, invoice, due_date=None, progress_description="Geänderte Bezeichnung",
        lump_sum_net=Decimal("4500"), intro_text=None, outro_text=None, outro_text_2=None,
        payment_terms=None,
    )

    assert len(invoice.items) == 1  # kein zweites Item entstanden
    item = invoice.items[0]
    assert item.id == first_item_id
    assert item.short_text == "Geänderte Bezeichnung"
    assert item.unit_price == Decimal("4500")
    assert item.billed_total == Decimal("4500")


def test_projected_item_is_not_the_source_of_truth_for_totals():
    """lump_sum_net bleibt die alleinige Quelle -- selbst wenn die Projektions-Zeile (durch einen
    hypothetischen Bug) vom aktuellen Betrag abweicht, darf sich der Rechnungsbetrag nicht
    ändern."""
    from app.invoices import compute_invoice_totals
    db = db_session()
    invoice = _make_draft_pauschal(db, lump_sum_net=Decimal("1000"))
    invoice.items[0].billed_total = Decimal("999999")  # absichtlich manipuliert, ohne den Sync-Weg
    db.commit()

    totals = compute_invoice_totals(invoice)
    assert totals["net_total"] == Decimal("1000")


# ---------------------------------------------------------------------------
# Projektion ist nicht ueber den allgemeinen Positionsweg erreichbar
# ---------------------------------------------------------------------------

def test_add_invoice_item_rejected_for_pauschal_invoice():
    db = db_session()
    invoice = _make_draft_pauschal(db)
    try:
        add_invoice_item(db, invoice, short_text="x", long_text="", unit="Stk", unit_price=Decimal("1"), ist_quantity=Decimal("1"))
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_update_invoice_item_rejected_for_pauschal_invoice():
    db = db_session()
    invoice = _make_draft_pauschal(db)
    try:
        update_invoice_item(db, invoice, invoice.items[0], short_text="x")
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


def test_remove_invoice_item_rejected_for_pauschal_invoice():
    db = db_session()
    invoice = _make_draft_pauschal(db)
    try:
        remove_invoice_item(db, invoice, invoice.items[0].id)
        assert False, "hätte ValueError werfen müssen"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# PDF: neue Rechnungen zeigen die Position, Bestandsrechnungen ohne Position (vor 1.3.24) bleiben
# byte-identisch zur bisherigen Darstellung.
# ---------------------------------------------------------------------------

def test_pauschal_invoice_pdf_shows_item_row_and_no_duplicate_heading():
    from app.invoice_pdf import build_invoice_pdf
    db = db_session()
    # Bewusst ASCII-only (kein Umlaut) -- _extract_pdf_text() dekodiert reportlabs
    # WinAnsi-Oktal-Escapes fuer Nicht-ASCII-Zeichen nicht, siehe test_v213_inspection_items.py.
    invoice = _make_draft_pauschal(db, lump_sum_net=Decimal("3000"), progress_description="1. Abschlag laut Auftrag")

    pdf_bytes = build_invoice_pdf(db, invoice)
    text = _extract_pdf_text(pdf_bytes)
    assert b"1. Abschlag laut Auftrag" in text
    assert b"pschl." in text
    assert b"3.000,00" in text
    # Der Beschreibungstext darf nicht doppelt erscheinen (einmal als Ueberschrift, einmal als
    # Positionstext) -- genau ein Vorkommen im extrahierten Text.
    assert text.count(b"1. Abschlag laut Auftrag") == 1


def test_legacy_pauschal_invoice_without_item_renders_exactly_as_before():
    """Simuliert eine Bestandsrechnung von vor 1.3.24 (Item nachträglich entfernt, wie es bei
    R-2026-0001/-0002 in der echten Datenbank tatsächlich der Fall ist) -- muss weiterhin nur
    Ueberschrift + Summenblock zeigen, keine (leere) Tabelle."""
    from app.invoice_pdf import build_invoice_pdf
    db = db_session()
    invoice = _make_draft_pauschal(db, lump_sum_net=Decimal("2195.78"), progress_description="1. Abschlagsrechnung")
    db.delete(invoice.items[0])
    db.commit()
    db.refresh(invoice)
    assert len(invoice.items) == 0

    pdf_bytes = build_invoice_pdf(db, invoice)
    text = _extract_pdf_text(pdf_bytes)
    assert "1. Abschlagsrechnung".encode("utf-8") in text
    assert b"2.195,78" in text
    assert b"EP/EUR" not in text  # keine Positionstabelle
    assert b"pschl." not in text
