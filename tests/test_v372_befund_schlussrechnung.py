"""Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026, docs/archiv/befund-vor-echtbetrieb.md), Punkt 1:
Abschläge, Schlussrechnung und Storno.

Heutiges Verhalten, festgehalten (grün): seit 1.8.85 (R4b) ist die Schlussrechnung eine Endrechnung -- alle Positionen mit der vollen
Ist-Menge (Gesamtleistung), darunter jeder festgeschriebene, nicht stornierte Abschlag und jede Rechnung aus Aufwand mit Netto, USt
und Brutto abgezogen (app/invoices.py::final_breakdown()), nach gestellten Rechnungen, nicht nach Zahlungen; Entwürfe und stornierte
zählen nicht. Bis 1.8.84 zog sie Abschläge nach Leistungsstand über die Menge ab (Rest = Ist − letzter Stand), pauschale gar nicht.

Fehler, nachgestellt als xfail (tests/befund_vor_echtbetrieb.py) -- sie werden die Abnahmetests der Reparatur. Geprüft wird
jeweils eine Eigenschaft, kein Weg: nach einer gültigen Schlussrechnung sind die gültigen Rechnungen eines Auftrags zusammen genau
die Auftragssumme (compute_order_billing_progress(), dieselbe Zahl, die die Auftragsseite als "abgerechnet"/"offen" zeigt); eine
Aktion, die die Reparatur ablehnen darf, läuft über _versuch().

Seit 1.8.72 (R3) behoben und ohne Markierung: 1c, 1e, 1f, 1g, 1h. Weil die Reparatur schon das Anlegen einer zweiten
Schlussrechnung bzw. eines zweiten Stornos ablehnt, läuft dort auch das zweite Anlegen über _versuch() (die Prüfungen sind
unverändert); den Altbestand mit zwei Entwürfen prüft tests/test_v375_rechnungen_sperren.py. Seit 1.8.83 (R4a Punkt 6) behoben
und ohne Markierung: 1d. Seit 1.8.85 (R4b) behoben und ohne Markierung: 1a (die Endrechnung zieht den pauschalen Abschlag ab), 1b
(das Festschreiben rechnet unter der Sperre neu, die Schlussrechnung zieht die beim Festschreiben gültigen Rechnungen ab) -- keine
Prüfung geändert. Bei 1a verlangt der Test zusätzlich, dass eine gültige Schlussrechnung besteht (sonst wäre er ohne sie zufällig
grün: 2.000 pauschal + 60 % = 5.000)."""

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
    update_invoice_item,
)
from app.models import Invoice, Reminder
from app.reminders import create_reminder, finalize_and_send_reminder
from tests.befund_vor_echtbetrieb import vorbedingung
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.zahlung import voll_bezahlen  # seit 1.8.78 statt mark_invoice_paid()
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.leistungszeitraum import ZEITRAUM, festschreiben

# Auftrag: 100 m² x 50 EUR = 5.000 EUR netto, 19 % = 5.950 EUR brutto.
AUFTRAG_NETTO, AUFTRAG_BRUTTO = Decimal("5000"), Decimal("5950")


def _final(db, invoice):
    return festschreiben(db, invoice)


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


def _schluss_festschreiben(db, order):
    """Schlussrechnung anlegen und festschreiben -- seit 1.8.72 bis R4 neben einem pauschalen Abschlag gesperrt."""
    schluss = _versuch(create_schlussrechnung, db, order)
    return _versuch(_final, db, schluss) if schluss is not None else None


# ---------------------------------------------------------------------------
# Heutiges Verhalten (Antworten auf die Fragen, grün)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bezahlt", [False, True])
def test_today_final_invoice_deducts_progress_invoices_with_net_and_vat_after_invoicing_not_payment(bezahlt):
    """Seit 1.8.85 (R4b): Abschlag nach Leistungsstand 40 m² (2.000 netto, 2.380 brutto), bezahlt oder nicht: die Schlussrechnung
    rechnet 100 m² = 5.000 netto Gesamtleistung, 950 USt, 5.950 brutto, zieht den Abschlag mit 2.000 / 380 / 2.380 ab und lautet
    über 3.000 / 570 / 3.570. Ein Entwurf zählt nicht. (Bis 1.8.84: 60 m² über die Menge, dieselben 3.570 €.)"""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    assert compute_invoice_totals(abschlag) == {"net_total": Decimal("2000.00"), "vat_total": Decimal("380.00"),
                                                "gross_total": Decimal("2380.00")}
    if bezahlt:
        voll_bezahlen(db, abschlag, received_on=date(2026, 9, 30))
    _leistungsstand(db, order, "90")  # Entwurf, zählt nicht
    schluss = create_schlussrechnung(db, order)
    [item] = schluss.items
    assert (item.ist_quantity, item.billed_quantity) == (Decimal("100"), Decimal("100"))
    from app.invoices import final_breakdown
    aufstellung = final_breakdown(schluss)
    assert (aufstellung.total_net, aufstellung.total_vat, aufstellung.total_gross) == (
        Decimal("5000.00"), Decimal("950.00"), Decimal("5950.00"))
    assert [(z.invoice.id, z.net, z.vat, z.gross) for z in aufstellung.deductions] == [
        (abschlag.id, Decimal("2000.00"), Decimal("380.00"), Decimal("2380.00"))]
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
# 1a: pauschale Abschläge zog die Schlussrechnung nicht ab (seit 1.8.85 behoben)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bezahlt", [False, True])
def test_final_invoice_after_lump_sum_progress_invoice_bills_the_order_once(bezahlt):
    """1a, seit 1.8.85 behoben (R4b): vorher zog die Schlussrechnung einen pauschalen Abschlag nicht ab -- der Auftrag wurde
    doppelt abgerechnet (7.000 statt 5.000 netto); bis R4 war sie neben ihm gesperrt."""
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = _final(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000")))
    if bezahlt:
        voll_bezahlen(db, pauschal, received_on=date(2026, 9, 30))
    _schluss_festschreiben(db, order)
    assert _gueltige_schlussrechnungen(db, order) == 1
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


def test_lump_sum_then_progress_by_quantity_then_final_bills_the_order_once():
    """1a, seit 1.8.85 behoben: pauschal 2.000, nach Leistungsstand 60 m² (3.000) -- die Endrechnung über 0 € schließt den
    Auftrag mit 5.000 ab (vorher 7.000)."""
    db = db_session()
    order, _ = make_order_with_item(db)
    _final(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000")))
    _final(db, _leistungsstand(db, order, "60"))
    _schluss_festschreiben(db, order)
    assert _gueltige_schlussrechnungen(db, order) == 1
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


# ---------------------------------------------------------------------------
# 1b: der Abzug wurde beim Anlegen des Entwurfs gerechnet, beim Festschreiben nicht neu (seit 1.8.85 behoben)
# ---------------------------------------------------------------------------

def test_final_invoice_drafted_before_a_progress_invoice_bills_the_order_once():
    """1b (a), seit 1.8.85 behoben: vorher zog eine Schlussrechnung, die vor dem Abschlag als Entwurf entstand, ihn nicht ab."""
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = create_schlussrechnung(db, order)
    _final(db, _leistungsstand(db, order, "40"))
    _final(db, schluss)
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


def test_two_parallel_progress_drafts_bill_the_cumulative_quantity_once():
    """1b (b), seit 1.8.85 behoben: vorher rechneten zwei Abschläge, als Entwurf nebeneinander angelegt, beide gegen den Stand 0
    (6.000 statt 4.000) -- das Festschreiben rechnet jetzt unter der Sperre gegen den letzten Stand von dann."""
    db = db_session()
    order, _ = make_order_with_item(db)
    erster = _leistungsstand(db, order, "40")
    zweiter = _leistungsstand(db, order, "80")
    _final(db, erster)
    _final(db, zweiter)
    assert _abgerechnet(db, order) == (Decimal("4000.00"), Decimal("4760.00"))  # 80 m² kumuliert


def test_final_invoice_drafted_before_a_cancellation_bills_the_order_once():
    """1b (c), seit 1.8.85 behoben: vorher zog die Schlussrechnung einen Abschlag weiter ab, der während ihres Entwurfs storniert
    wurde (3.000 statt 5.000)."""
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

def test_two_final_invoice_drafts_never_both_become_valid():
    """1c, seit 1.8.72 behoben: vorher ließen sich zwei Schlussrechnungen als Entwurf anlegen und beide festschreiben."""
    db = db_session()
    order, _ = make_order_with_item(db)
    erste = create_schlussrechnung(db, order)
    zweite = _versuch(create_schlussrechnung, db, order)
    _final(db, erste)
    if zweite is not None:
        _versuch(_final, db, zweite)
    assert _gueltige_schlussrechnungen(db, order) == 1
    assert _abgerechnet(db, order) == (AUFTRAG_NETTO, AUFTRAG_BRUTTO)


def test_no_second_valid_final_invoice_next_to_a_valid_one():
    """1c, seit 1.8.72 behoben: vorher entstand neben einer gültigen eine zweite mit eigener Nummer (über 0,00 EUR)."""
    db = db_session()
    order, _ = make_order_with_item(db)
    _final(db, create_schlussrechnung(db, order))
    zweite = _versuch(create_schlussrechnung, db, order)
    if zweite is not None:
        _versuch(_final, db, zweite)
    assert _gueltige_schlussrechnungen(db, order) == 1


def test_lump_sum_progress_invoice_after_the_final_invoice_does_not_bill_more():
    """1c, seit 1.8.72 behoben: vorher ließ sich nach der Schlussrechnung ein pauschaler Abschlag stellen und wurde
    zusätzlich abgerechnet."""
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

def test_cancellation_of_a_legacy_lump_sum_invoice_reverses_its_amount():
    """1d, seit 1.8.83 behoben (R4a Punkt 6): vorher lautete das Storno eines pauschalen Abschlags ohne Position (vor 1.3.24,
    z. B. R-2026-0001/-0002) über 0,00 EUR -- das Original fiel trotzdem als storniert heraus."""
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000"))
    db.delete(pauschal.items[0])  # so stehen sie in der Datenbank (projektliste-und-mappe.md, 1.3.24)
    pauschal.rounding_rule = None  # vor 1.8.11 versendet
    # Zeitraum direkt (seit 1.8.74 Pflicht) -- das Kopf-Update legte die fehlende Position wieder an
    pauschal.service_period_start, pauschal.service_period_end = ZEITRAUM
    db.commit()
    db.refresh(pauschal)
    pauschal = _final(db, pauschal)
    vorbedingung(compute_invoice_totals(pauschal)["net_total"] == Decimal("2000"))
    storno = _final(db, create_storno_draft(db, pauschal))
    vorbedingung(db.get(Invoice, pauschal.id).status == "storniert")
    assert compute_invoice_totals(storno)["net_total"] == Decimal("-2000")
    assert compute_invoice_totals(storno)["gross_total"] == Decimal("-2380")


def test_an_invoice_is_cancelled_at_most_once():
    """1e, seit 1.8.72 behoben: vorher ließen sich zwei Storno-Entwürfe zur selben Rechnung anlegen und beide festschreiben
    -- die Gutschrift entstand doppelt."""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    erstes = create_storno_draft(db, abschlag)
    zweites = _versuch(create_storno_draft, db, abschlag)
    _final(db, erstes)
    if zweites is not None:
        _versuch(_final, db, zweites)
    assert db.scalar(select(func.count()).select_from(Invoice).where(
        Invoice.storno_of_invoice_id == abschlag.id, Invoice.status != "entwurf")) == 1


def test_a_cancellation_invoice_cannot_be_cancelled():
    """1f, seit 1.8.72 behoben: vorher ließ sich eine Stornorechnung selbst stornieren -- das Original blieb storniert, die
    Rückgängigmachung zählte nirgends."""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    storno = _final(db, create_storno_draft(db, abschlag))
    gegen = _versuch(create_storno_draft, db, storno)
    if gegen is not None:
        _versuch(_final, db, gegen)
    assert db.scalar(select(func.count()).select_from(Invoice).where(
        Invoice.storno_of_invoice_id == storno.id, Invoice.status != "entwurf")) == 0


def test_cancelling_a_progress_invoice_behind_a_valid_final_invoice_keeps_the_order_fully_billed():
    """1g, seit 1.8.72 behoben: vorher ließ sich ein Abschlag hinter einer gültigen Schlussrechnung stornieren -- der
    Auftrag blieb still unterabgerechnet."""
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


@pytest.mark.parametrize("danach", ["storniert", "bezahlt"])
def test_reminder_draft_cannot_be_sent_after_the_invoice_was_cancelled_or_paid(danach):
    """1h, seit 1.8.72 behoben: vorher ging ein Mahnungsentwurf noch hinaus, nachdem die Rechnung storniert oder bezahlt war."""
    db = db_session()
    invoice = make_sent_overdue_invoice(db)
    mahnung = create_reminder(db, invoice, 1)
    if danach == "storniert":
        _final(db, create_storno_draft(db, invoice))
    else:
        voll_bezahlen(db, invoice, received_on=date.today() - timedelta(days=1))
    # Seit 1.8.78 ist "bezahlt" abgeleitet (der Status bleibt "versendet").
    from app.payments import payment_state
    vorbedingung(db.get(Invoice, invoice.id).status == "storniert" if danach == "storniert"
                 else payment_state(db, db.get(Invoice, invoice.id)).state == "bezahlt")
    _versuch(finalize_and_send_reminder, db, mahnung)
    db.expire_all()
    assert (db.get(Reminder, mahnung.id).status, db.get(Reminder, mahnung.id).reminder_number) == ("entwurf", None)
