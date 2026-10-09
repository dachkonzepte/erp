"""Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026, docs/archiv/befund-vor-echtbetrieb.md), Punkt 1:
Abschläge, Schlussrechnung und Storno.

Heutiges Verhalten, festgehalten (grün): die Schlussrechnung zieht Abschläge nach Leistungsstand über die Menge ab
(app/invoices.py::get_previous_cumulative_ist(), compute_billed_quantity_and_total()) -- netto (Menge x EP), die USt nur auf den
Rest mit dem Satz der Schlussrechnung, nach gestellten Rechnungen (versendet/bezahlt), nicht nach Zahlungen; Entwürfe und
stornierte zählen nicht.

Fehler, nachgestellt als xfail (tests/befund_vor_echtbetrieb.py) -- sie werden die Abnahmetests der Reparatur. Geprüft wird
jeweils eine Eigenschaft, kein Weg: nach einer gültigen Schlussrechnung sind die gültigen Rechnungen eines Auftrags zusammen genau
die Auftragssumme (compute_order_billing_progress(), dieselbe Zahl, die die Auftragsseite als "abgerechnet"/"offen" zeigt); eine
Aktion, die die Reparatur ablehnen darf, läuft über _versuch()."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.invoices import (
    compute_invoice_totals,
    compute_order_billing_progress,
    create_abschlag_leistungsstand,
    create_abschlag_pauschal,
    create_schlussrechnung,
    create_storno_draft,
    finalize_and_send_invoice,
    mark_invoice_paid,
    update_invoice_item,
)
from app.models import Invoice, Reminder
from app.reminders import create_reminder, finalize_and_send_reminder
from tests.befund_vor_echtbetrieb import befund, vorbedingung
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v153_mahnwesen import make_sent_overdue_invoice

# Auftrag: 100 m² x 50 EUR = 5.000 EUR netto, 19 % = 5.950 EUR brutto.
AUFTRAG_NETTO, AUFTRAG_BRUTTO = Decimal("5000"), Decimal("5950")


def _final(db, invoice):
    return finalize_and_send_invoice(db, invoice)


def _leistungsstand(db, order, ist):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=Decimal(ist))
    db.refresh(invoice)
    return invoice


def _abgerechnet(db, order):
    progress = compute_order_billing_progress(db, order.id)
    return progress["invoiced_net"], progress["invoiced_gross"]


def _gueltige_schlussrechnungen(db, order):
    return db.scalar(select(func.count()).select_from(Invoice).where(
        Invoice.order_id == order.id, Invoice.invoice_type == "schluss", Invoice.status.in_(["versendet", "bezahlt"])))


def _versuch(fn, *args, **kwargs):
    """Führt eine Aktion aus, die die Reparatur ablehnen darf (ValueError) -- der Test prüft danach die Eigenschaft."""
    try:
        return fn(*args, **kwargs)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Heutiges Verhalten (Antworten auf die Fragen, grün)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bezahlt", [False, True])
def test_today_progress_invoices_are_deducted_net_by_quantity_after_invoicing_not_payment(bezahlt):
    """Abschlag nach Leistungsstand 40 m² (2.000 netto, 2.380 brutto), bezahlt oder nicht: die Schlussrechnung rechnet 60 m² =
    3.000 netto + 19 % auf den Rest = 3.570 brutto. Die USt des Abschlags erscheint dort nicht; ein Entwurf zählt nicht."""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    assert compute_invoice_totals(abschlag) == {"net_total": Decimal("2000.00"), "vat_total": Decimal("380.00"),
                                                "gross_total": Decimal("2380.00")}
    if bezahlt:
        mark_invoice_paid(db, abschlag, paid_date=date(2026, 9, 30))
    _leistungsstand(db, order, "90")  # Entwurf, zählt nicht
    schluss = create_schlussrechnung(db, order)
    [item] = schluss.items
    assert (item.ist_quantity, item.billed_quantity) == (Decimal("100"), Decimal("60"))
    assert compute_invoice_totals(schluss) == {"net_total": Decimal("3000.00"), "vat_total": Decimal("570.00"),
                                               "gross_total": Decimal("3570.00")}


def test_today_pauschal_has_no_reference_to_order_items():
    """Der pauschale Abschlag ist ein Nettobetrag mit einer reinen Projektionsposition ohne Bezug zur Auftragsposition --
    get_previous_cumulative_ist() sucht nur abschlag_leistungsstand/schluss über source_order_item_id."""
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = _final(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000")))
    assert [i.source_order_item_id for i in pauschal.items] == [None]
    assert compute_invoice_totals(pauschal)["gross_total"] == Decimal("2380.00")


# ---------------------------------------------------------------------------
# 1a: pauschale Abschläge zieht die Schlussrechnung nicht ab
# ---------------------------------------------------------------------------

@befund("1a", "pauschale Abschläge werden von der Schlussrechnung nicht abgezogen -- der Auftrag wird doppelt abgerechnet")
@pytest.mark.parametrize("bezahlt", [False, True])
def test_final_invoice_after_lump_sum_progress_invoice_bills_the_order_once(bezahlt):
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = _final(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000")))
    if bezahlt:
        mark_invoice_paid(db, pauschal, paid_date=date(2026, 9, 30))
    _final(db, create_schlussrechnung(db, order))
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


@befund("1a", "pauschale Abschläge zählen auch für einen folgenden Abschlag nach Leistungsstand nicht")
def test_lump_sum_then_progress_by_quantity_then_final_bills_the_order_once():
    db = db_session()
    order, _ = make_order_with_item(db)
    _final(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000")))
    _final(db, _leistungsstand(db, order, "60"))
    _final(db, create_schlussrechnung(db, order))
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


# ---------------------------------------------------------------------------
# 1b: der Abzug wird beim Anlegen des Entwurfs gerechnet, beim Festschreiben nicht neu
# ---------------------------------------------------------------------------

@befund("1b", "Schlussrechnung als Entwurf, danach ein Abschlag festgeschrieben -- die Schlussrechnung zieht ihn nicht ab")
def test_final_invoice_drafted_before_a_progress_invoice_bills_the_order_once():
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = create_schlussrechnung(db, order)
    _final(db, _leistungsstand(db, order, "40"))
    _final(db, schluss)
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


@befund("1b", "zwei Abschläge nach Leistungsstand als Entwurf nebeneinander -- beide rechnen gegen den Stand 0")
def test_two_parallel_progress_drafts_bill_the_cumulative_quantity_once():
    db = db_session()
    order, _ = make_order_with_item(db)
    erster = _leistungsstand(db, order, "40")
    zweiter = _leistungsstand(db, order, "80")
    _final(db, erster)
    _final(db, zweiter)
    assert _abgerechnet(db, order) == (Decimal("4000.00"), Decimal("4760.00"))  # 80 m² kumuliert


@befund("1b", "Abschlag storniert, während die Schlussrechnung Entwurf ist -- sie zieht den stornierten weiter ab")
def test_final_invoice_drafted_before_a_cancellation_bills_the_order_once():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    schluss = create_schlussrechnung(db, order)
    _final(db, create_storno_draft(db, abschlag))
    _final(db, schluss)
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


# ---------------------------------------------------------------------------
# 1c: zweite Schlussrechnung
# ---------------------------------------------------------------------------

@befund("1c", "zwei Schlussrechnungen als Entwurf -- beide lassen sich festschreiben, jede über 100 %")
def test_two_final_invoice_drafts_never_both_become_valid():
    db = db_session()
    order, _ = make_order_with_item(db)
    erste = create_schlussrechnung(db, order)
    zweite = create_schlussrechnung(db, order)
    _final(db, erste)
    _versuch(_final, db, zweite)
    assert _gueltige_schlussrechnungen(db, order) == 1
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


@befund("1c", "neben einer gültigen Schlussrechnung entsteht eine zweite mit eigener Nummer (über 0,00 EUR)")
def test_no_second_valid_final_invoice_next_to_a_valid_one():
    db = db_session()
    order, _ = make_order_with_item(db)
    _final(db, create_schlussrechnung(db, order))
    zweite = _versuch(create_schlussrechnung, db, order)
    if zweite is not None:
        _versuch(_final, db, zweite)
    assert _gueltige_schlussrechnungen(db, order) == 1


@befund("1c", "nach der Schlussrechnung lässt sich ein pauschaler Abschlag stellen und wird zusätzlich abgerechnet")
def test_lump_sum_progress_invoice_after_the_final_invoice_does_not_bill_more():
    db = db_session()
    order, _ = make_order_with_item(db)
    _final(db, create_schlussrechnung(db, order))
    pauschal = _versuch(create_abschlag_pauschal, db, order, lump_sum_net=Decimal("500"))
    if pauschal is not None:
        _versuch(_final, db, pauschal)
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


def test_today_cancelled_final_invoice_allows_a_new_one():
    """Grün: ist die erste Schlussrechnung storniert, rechnet eine neue wieder richtig (Abschläge zählen wieder)."""
    db = db_session()
    order, _ = make_order_with_item(db)
    _final(db, _leistungsstand(db, order, "40"))
    erste = _final(db, create_schlussrechnung(db, order))
    _final(db, create_storno_draft(db, erste))
    neue = _final(db, create_schlussrechnung(db, order))
    assert compute_invoice_totals(neue)["net_total"] == Decimal("3000.00")
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


# ---------------------------------------------------------------------------
# 1d-1g: Storno
# ---------------------------------------------------------------------------

@befund("1d", "Storno eines pauschalen Abschlags ohne Position (vor 1.3.24, z. B. R-2026-0001/-0002) lautet über 0,00 EUR")
def test_cancellation_of_a_legacy_lump_sum_invoice_reverses_its_amount():
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000"))
    db.delete(pauschal.items[0])  # so stehen sie in der Datenbank (projektliste-und-mappe.md, 1.3.24)
    pauschal.rounding_rule = None  # vor 1.8.11 versendet
    db.commit()
    db.refresh(pauschal)
    pauschal = _final(db, pauschal)
    vorbedingung(compute_invoice_totals(pauschal)["net_total"] == Decimal("2000"))
    storno = _final(db, create_storno_draft(db, pauschal))
    vorbedingung(db.get(Invoice, pauschal.id).status == "storniert")
    assert compute_invoice_totals(storno)["net_total"] == Decimal("-2000")
    assert compute_invoice_totals(storno)["gross_total"] == Decimal("-2380")


@befund("1e", "zwei Storno-Entwürfe zur selben Rechnung -- beide lassen sich festschreiben, die Gutschrift entsteht doppelt")
def test_an_invoice_is_cancelled_at_most_once():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    erstes = create_storno_draft(db, abschlag)
    zweites = create_storno_draft(db, abschlag)
    _final(db, erstes)
    _versuch(_final, db, zweites)
    assert db.scalar(select(func.count()).select_from(Invoice).where(
        Invoice.storno_of_invoice_id == abschlag.id, Invoice.status != "entwurf")) == 1


@befund("1f", "eine Stornorechnung lässt sich selbst stornieren -- das Original bleibt storniert, die Rückgängigmachung "
              "zählt nirgends")
def test_a_cancellation_invoice_cannot_be_cancelled():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    storno = _final(db, create_storno_draft(db, abschlag))
    gegen = _versuch(create_storno_draft, db, storno)
    if gegen is not None:
        _versuch(_final, db, gegen)
    assert db.scalar(select(func.count()).select_from(Invoice).where(
        Invoice.storno_of_invoice_id == storno.id, Invoice.status != "entwurf")) == 0


@befund("1g", "Storno eines Abschlags hinter einer gültigen Schlussrechnung -- der Auftrag bleibt still unterabgerechnet")
def test_cancelling_a_progress_invoice_behind_a_valid_final_invoice_keeps_the_order_fully_billed():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    _final(db, create_schlussrechnung(db, order))
    vorbedingung(_abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO))
    storno = _versuch(create_storno_draft, db, abschlag)
    if storno is not None:
        _versuch(_final, db, storno)
    if _gueltige_schlussrechnungen(db, order):
        assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


@befund("1h", "ein Mahnungsentwurf geht noch hinaus, nachdem die Rechnung storniert oder bezahlt ist")
@pytest.mark.parametrize("danach", ["storniert", "bezahlt"])
def test_reminder_draft_cannot_be_sent_after_the_invoice_was_cancelled_or_paid(danach):
    db = db_session()
    invoice = make_sent_overdue_invoice(db)
    mahnung = create_reminder(db, invoice, 1)
    if danach == "storniert":
        _final(db, create_storno_draft(db, invoice))
    else:
        mark_invoice_paid(db, invoice, paid_date=date.today() - timedelta(days=1))
    vorbedingung(db.get(Invoice, invoice.id).status == danach)
    _versuch(finalize_and_send_reminder, db, mahnung)
    db.expire_all()
    assert (db.get(Reminder, mahnung.id).status, db.get(Reminder, mahnung.id).reminder_number) == ("entwurf", None)
