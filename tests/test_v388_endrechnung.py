"""Version 1.8.85 -- Schlussrechnung als Endrechnung (R4b Punkte 2, 3 und 5, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung R4b").

- Punkt 2: alle Auftragspositionen samt Nachträgen mit der vollen Ist-Menge (Vorschlag: Menge des Auftrags) = Gesamtleistung, dazu
  die Rechnungen aus Aufwand; darunter der Abzug jeder festgeschriebenen, nicht stornierten Abschlagsrechnung und Rechnung aus
  Aufwand mit Netto, USt, Brutto. Rechnungsbetrag = Gesamtleistung − Abzüge -- der Betrag für Zahlungen, offene Posten und
  "abgerechnet". Beim Festschreiben eingefroren (InvoiceDeduction, unveränderlich).
- Punkt 3: beim Festschreiben unter der Sperre neu gerechnet; weichen Preise, Einheiten, Positionen oder Steuerschlüssel vom Auftrag
  ab, 409 mit Hinweis "Aus dem Auftrag aktualisieren" (jede Art außer Storno); anderer Steuersatz eines Abzugs: Hinweis.
- Festlegung 1.8.83 Nr. 6 geändert: ein Abschlag muss über 0 € liegen; eine Schlussrechnung unter 0 € bis R4c 409.
- Punkt 5: keine Sperre der Schlussrechnung neben einem pauschalen Abschlag mehr; nach der gültigen Schlussrechnung keine Rechnung
  aus Aufwand (anlegen und festschreiben), kein Storno einer abgezogenen.

Auftrag aus tests/test_v133_invoices.py: 100 m² × 50 € = 5.000 € netto, 19 %."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.invoices import (
    InvoiceBlocked, add_invoice_item, compute_invoice_totals, compute_order_billing_progress, create_abschlag_leistungsstand,
    create_abschlag_pauschal, create_invoice_from_time_entries, create_schlussrechnung, create_storno_draft,
    finalize_and_send_invoice, final_breakdown, invoice_to_dict, refresh_draft_from_order, update_invoice_item,
    update_invoice_tax_key,
)
from app.models import ArchiveImmutableError, Invoice, InvoiceDeduction, Order, OrderItem, TaxKey
from app.orders import add_order_addendum, update_order_item, update_order_tax_key
from app.payments import payable_gross, payment_state
from app.routers.invoices import router as invoices_router
from tests.leistungszeitraum import ZEITRAUM_JSON, festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

D = Decimal


def _leistungsstand(db, order, ist):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return invoice


def _aufwand(db, order, betrag):
    """Rechnung aus Aufwand über einen Nettobetrag: eine freie Materialzeile (EP 0) und eine freie Position mit dem Betrag."""
    invoice = create_invoice_from_time_entries(
        db, order, [], [SimpleNamespace(material_id=None, description="Kleinmaterial", unit="Stk", quantity=D("1"))])
    add_invoice_item(db, invoice, short_text="Reparatur", long_text="", unit="Std.", unit_price=D(betrag), ist_quantity=D("1"))
    db.refresh(invoice)
    return invoice


def _totals(invoice):
    t = compute_invoice_totals(invoice)
    return t["net_total"], t["vat_total"], t["gross_total"]


def _schluessel(db, label):
    return db.scalar(select(TaxKey).where(TaxKey.label.like(f"{label}%")))


def _blocked(fn, *args, **kwargs) -> str:
    with pytest.raises(InvoiceBlocked) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


# ---------------------------------------------------------------------------
# Punkt 2: Endrechnung
# ---------------------------------------------------------------------------

def test_final_invoice_shows_the_total_performance_and_deducts_every_valid_invoice():
    db = db_session()
    order, item = make_order_with_item(db)
    pauschal = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("1000")))
    abschlag = festschreiben(db, _leistungsstand(db, order, "40"))
    aufwand = festschreiben(db, _aufwand(db, order, "246.90"))
    entwurf = create_abschlag_pauschal(db, order, lump_sum_net=D("50"))  # Entwurf: zählt nicht
    storniert = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("300")))
    festschreiben(db, create_storno_draft(db, storniert))  # storniert: zählt nicht
    db.delete(db.get(Invoice, entwurf.id))
    db.commit()
    schluss = create_schlussrechnung(db, order)
    [position] = schluss.items
    assert (position.ist_quantity, position.billed_quantity) == (D("100"), D("100"))  # Vorschlag: Menge des Auftrags
    fb = final_breakdown(schluss)
    assert fb.positions_net == D("5000.00")
    assert [line.invoice.id for line in fb.effort] == [aufwand.id]
    assert (fb.total_net, fb.total_vat, fb.total_gross) == (D("5246.90"), D("996.91"), D("6243.81"))
    assert [line.invoice.id for line in fb.deductions] == [pauschal.id, abschlag.id, aufwand.id]  # älteste zuerst
    assert (fb.deducted_net, fb.deducted_vat, fb.deducted_gross) == (D("3246.90"), D("616.91"), D("3863.81"))
    assert _totals(schluss) == (D("2000.00"), D("380.00"), D("2380.00"))
    festschreiben(db, schluss)
    assert [row.deducted_invoice_id for row in schluss.deductions] == [pauschal.id, abschlag.id, aufwand.id]
    assert _totals(schluss) == (D("2000.00"), D("380.00"), D("2380.00"))
    assert payable_gross(schluss) == D("2380.00")  # Betrag für Zahlungen und offene Posten
    assert payment_state(db, schluss).open == D("2380.00")
    # "abgerechnet" = Summe der gültigen Rechnungsbeträge = Gesamtleistung
    assert compute_order_billing_progress(db, order.id) == {"invoiced_net": D("5246.90"), "invoiced_gross": D("6243.81")}


def test_final_invoice_includes_addenda_and_bills_the_entered_actual_quantity():
    db = db_session()
    order, item = make_order_with_item(db)
    add_order_addendum(db, order.id, short_text="Kaminverblechung", long_text="", quantity=D("2"), unit="Stk",
                       unit_price=D("250"))
    festschreiben(db, _leistungsstand(db, order, "40"))
    schluss = create_schlussrechnung(db, order)
    assert sorted((i.position_number, i.ist_quantity) for i in schluss.items) == [("1", D("100")), ("N1", D("2"))]
    hauptposition = next(i for i in schluss.items if i.position_number == "1")
    update_invoice_item(db, schluss, hauptposition, ist_quantity=D("90"))  # Aufmaß kleiner als beauftragt
    db.refresh(schluss)
    fb = final_breakdown(schluss)
    assert fb.total_net == D("5000.00")  # 90 × 50 + 2 × 250
    assert _totals(schluss) == (D("3000.00"), D("570.00"), D("3570.00"))
    festschreiben(db, schluss)
    assert {i.position_number: i.billed_quantity for i in schluss.items} == {"1": D("90"), "N1": D("2")}


def test_without_deductions_the_final_invoice_is_the_total_performance():
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    assert final_breakdown(schluss) is None and schluss.deductions == []
    assert _totals(schluss) == (D("5000.00"), D("950.00"), D("5950.00"))


def test_frozen_deductions_keep_the_amount_after_the_final_invoice_and_a_deduction_are_cancelled():
    """Der Betrag einer festgeschriebenen Endrechnung hängt an ihren eingefrorenen Abzügen -- nach ihrem Storno und dem Storno eines
    Abschlags bleibt er; ihr Storno lautet auf den Gegenbetrag."""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order, "40"))
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    storno = festschreiben(db, create_storno_draft(db, schluss))
    assert _totals(storno) == (D("-3000.00"), D("-570.00"), D("-3570.00"))
    assert final_breakdown(storno).deducted_gross == D("-2380.00")
    festschreiben(db, create_storno_draft(db, abschlag))  # nach dem Storno der Schlussrechnung wieder frei
    db.expire_all()
    assert _totals(db.get(Invoice, schluss.id)) == (D("3000.00"), D("570.00"), D("3570.00"))
    assert _totals(db.get(Invoice, storno.id)) == (D("-3000.00"), D("-570.00"), D("-3570.00"))
    neue = festschreiben(db, create_schlussrechnung(db, order))
    assert _totals(neue) == (D("5000.00"), D("950.00"), D("5950.00"))  # der stornierte Abschlag zählt nicht mehr


def test_deductions_cannot_be_changed_or_deleted():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order, "40"))
    anderer = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("100")))
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    row = schluss.deductions[0]
    row.deducted_invoice_id = anderer.id
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    with pytest.raises(ArchiveImmutableError):
        db.delete(db.get(InvoiceDeduction, row.id))
        db.commit()
    db.rollback()
    schluss = db.get(Invoice, schluss.id)
    with pytest.raises(ArchiveImmutableError):
        schluss.deductions.clear()
        db.commit()
    db.rollback()
    assert [r.deducted_invoice_id for r in db.get(Invoice, schluss.id).deductions] == [abschlag.id, anderer.id]


def test_a_deduction_with_another_vat_rate_gives_a_notice_and_deducts_its_own_vat():
    """Altbestand: ein Abschlag mit 0 % (bis 1.8.84 war der Steuerschlüssel eines Entwurfs frei) -- die Endrechnung zieht seine USt
    (0) ab und nennt den abweichenden Satz."""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order, "40"))
    abschlag.vat_rate = D("0")  # wie vor 1.8.85 im Entwurf gewählt
    db.commit()
    schluss = create_schlussrechnung(db, order)
    fb = final_breakdown(schluss)
    assert (fb.deducted_net, fb.deducted_vat) == (D("2000.00"), D("0.00"))
    assert _totals(schluss) == (D("3000.00"), D("950.00"), D("3950.00"))
    assert len(fb.tax_notes) == 1 and "0 %" in fb.tax_notes[0] and "19 %" in fb.tax_notes[0]
    assert invoice_to_dict(schluss)["final_breakdown"]["tax_notes"] == fb.tax_notes


def test_final_invoice_pdf_shows_total_performance_deductions_and_amount():
    from tests.test_v325_contract_basis import pdf_text
    from app.invoice_pdf import build_invoice_pdf
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order, "40"))
    aufwand = festschreiben(db, _aufwand(db, order, "100"))
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    text = pdf_text(build_invoice_pdf(db, schluss))
    for erwartet in ("Gesamtleistung netto", "5.100,00 EUR", f"Leistungen nach Aufwand, Rechnung {aufwand.invoice_number}",
                     "Abzüglich bereits gestellter Rechnungen", abschlag.invoice_number, "Summe der Abzüge",
                     "2.100,00 EUR", "Rechnungsbetrag brutto", "3.570,00 EUR"):
        assert erwartet in text, erwartet


# ---------------------------------------------------------------------------
# Punkt 3: neu rechnen, Abweichung vom Auftrag
# ---------------------------------------------------------------------------

def test_other_progress_drafts_follow_when_an_invoice_is_finalized():
    db = db_session()
    order, _ = make_order_with_item(db)
    erster = _leistungsstand(db, order, "40")
    zweiter = _leistungsstand(db, order, "80")
    assert zweiter.items[0].billed_quantity == D("80")
    festschreiben(db, erster)
    db.refresh(zweiter)
    assert zweiter.items[0].billed_quantity == D("40")  # nachgezogen im selben Commit
    assert _totals(zweiter) == (D("2000.00"), D("380.00"), D("2380.00"))


@pytest.mark.parametrize("art", ["abschlag_leistungsstand", "schluss"])
def test_a_price_change_at_the_order_blocks_finalizing_until_the_draft_is_refreshed(art):
    db = db_session()
    order, item = make_order_with_item(db)
    entwurf = mit_zeitraum(db, _leistungsstand(db, order, "40") if art != "schluss" else create_schlussrechnung(db, order))
    werte = {"quantity": item.quantity, "unit": item.unit, "unit_price": D("60"), "short_text": item.short_text,
             "long_text": "", "position_type": item.position_type, "gaeb_oz": item.gaeb_oz, "include_in_total": True}
    update_order_item(db, order.id, item.id, **werte)  # erlaubt: noch nicht abgerechnet
    grund = _blocked(finalize_and_send_invoice, db, db.get(Invoice, entwurf.id))
    assert "Einheitspreis Pos. 1 (Entwurf 50,00 €, Auftrag 60,00 €)" in grund and "Aus dem Auftrag aktualisieren" in grund
    entwurf = db.get(Invoice, entwurf.id)
    assert entwurf.status == "entwurf" and entwurf.invoice_number is None
    assert invoice_to_dict(entwurf)["order_deviation"] == grund
    refresh_draft_from_order(db, entwurf)
    assert invoice_to_dict(entwurf)["order_deviation"] is None
    festschreiben(db, entwurf)
    assert entwurf.items[0].unit_price == D("60")


@pytest.mark.parametrize("art", ["abschlag_pauschal", "abschlag_leistungsstand", "schluss", "aufwand"])
def test_a_tax_key_change_at_the_order_blocks_every_invoice_type(art):
    db = db_session()
    order, _ = make_order_with_item(db)
    erstellen = {"abschlag_pauschal": lambda: create_abschlag_pauschal(db, order, lump_sum_net=D("100")),
                 "abschlag_leistungsstand": lambda: _leistungsstand(db, order, "40"),
                 "schluss": lambda: create_schlussrechnung(db, order),
                 "aufwand": lambda: _aufwand(db, order, "100")}
    entwurf = mit_zeitraum(db, erstellen[art]())
    solar = _schluessel(db, "Solar")
    update_order_tax_key(db, db.get(Order, order.id), solar.id)  # erlaubt: noch keine gültige Rechnung
    grund = _blocked(finalize_and_send_invoice, db, db.get(Invoice, entwurf.id))
    assert "Steuerschlüssel (Entwurf 19 %, Auftrag 0 %)" in grund
    entwurf = refresh_draft_from_order(db, db.get(Invoice, entwurf.id))
    assert (entwurf.tax_key_id, entwurf.vat_rate) == (solar.id, D("0"))
    festschreiben(db, entwurf)
    assert compute_invoice_totals(entwurf)["vat_total"] == D("0")


def test_refresh_adds_a_later_addendum_and_removes_positions_no_longer_in_the_total():
    db = db_session()
    order, item = make_order_with_item(db)
    schluss = mit_zeitraum(db, create_schlussrechnung(db, order))
    add_order_addendum(db, order.id, short_text="Kaminverblechung", long_text="", quantity=D("2"), unit="Stk",
                       unit_price=D("250"))
    grund = _blocked(finalize_and_send_invoice, db, db.get(Invoice, schluss.id))
    assert "es fehlen Positionen des Auftrags (N1)" in grund
    refresh_draft_from_order(db, db.get(Invoice, schluss.id))
    assert sorted(i.position_number for i in db.get(Invoice, schluss.id).items) == ["1", "N1"]
    werte = {"quantity": item.quantity, "unit": item.unit, "unit_price": item.unit_price, "short_text": item.short_text,
             "long_text": "", "position_type": item.position_type, "gaeb_oz": item.gaeb_oz, "include_in_total": False}
    update_order_item(db, order.id, item.id, **werte)
    grund = _blocked(finalize_and_send_invoice, db, db.get(Invoice, schluss.id))
    assert "Pos. 1 steht nicht mehr in der Summe des Auftrags" in grund
    refresh_draft_from_order(db, db.get(Invoice, schluss.id))
    schluss = festschreiben(db, db.get(Invoice, schluss.id))
    assert [i.position_number for i in schluss.items] == ["N1"]
    assert _totals(schluss) == (D("500.00"), D("95.00"), D("595.00"))


def test_price_and_unit_of_an_order_position_cannot_be_changed_in_the_draft():
    db = db_session()
    order, _ = make_order_with_item(db)
    entwurf = _leistungsstand(db, order, "40")
    position = entwurf.items[0]
    assert "kommen aus dem Auftrag" in _blocked(update_invoice_item, db, entwurf, position, unit_price=D("55"))
    assert "kommen aus dem Auftrag" in _blocked(update_invoice_item, db, entwurf, position, unit="Stk")
    update_invoice_item(db, entwurf, position, unit_price=D("50.000"), unit="m²", ist_quantity=D("50"))  # unverändert geht
    assert "kommen aus dem Auftrag" in _blocked(
        add_invoice_item, db, entwurf, short_text="x", long_text="", unit="m²", unit_price=D("49"), ist_quantity=D("1"),
        source_order_item_id=position.source_order_item_id)


def test_the_tax_key_of_a_draft_comes_from_the_order_and_a_cancellation_keeps_the_originals():
    db = db_session()
    order, _ = make_order_with_item(db)
    regel = _schluessel(db, "Gewerbe")
    update_order_tax_key(db, db.get(Order, order.id), regel.id)
    entwurf = create_abschlag_pauschal(db, order, lump_sum_net=D("100"))
    solar = _schluessel(db, "Solar")
    assert "kommt aus dem Auftrag" in _blocked(update_invoice_tax_key, db, entwurf, solar.id)
    update_invoice_tax_key(db, entwurf, regel.id)  # derselbe geht
    festschreiben(db, entwurf)
    storno = create_storno_draft(db, entwurf)
    assert "Steuerschlüssel der stornierten Rechnung" in _blocked(update_invoice_tax_key, db, storno, solar.id)
    assert "Storno spiegelt" in _blocked(refresh_draft_from_order, db, storno)


def test_router_refresh_from_order_and_409(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, item = make_order_with_item(db)
    client = router_test_client(db, invoices_router)
    entwurf = create_schlussrechnung(db, order)
    client.put(f"/api/invoices/{entwurf.id}", json=ZEITRAUM_JSON)
    item.unit_price = D("70")  # wie eine Preisänderung am Auftrag
    db.commit()
    antwort = client.post(f"/api/invoices/{entwurf.id}/send")
    assert antwort.status_code == 409 and "Einheitspreis Pos. 1" in antwort.json()["detail"]
    assert client.get(f"/api/invoices/{entwurf.id}").json()["order_deviation"]
    aktualisiert = client.post(f"/api/invoices/{entwurf.id}/refresh-from-order")
    assert aktualisiert.status_code == 200 and aktualisiert.json()["order_deviation"] is None
    assert client.post(f"/api/invoices/{entwurf.id}/send").status_code == 200
    assert client.post(f"/api/invoices/{entwurf.id}/refresh-from-order").status_code == 409  # kein Entwurf mehr


# ---------------------------------------------------------------------------
# Beträge: Abschlag über 0 €, Schlussrechnung nicht unter 0 € (bis R4c)
# ---------------------------------------------------------------------------

def test_a_progress_invoice_of_zero_is_rejected_like_a_negative_one():
    """Festlegung 1.8.83 Nr. 6 geändert (Vorgabe R4b): bis 1.8.84 ging ein Abschlag über 0,00 € mit Nummer durch."""
    db = db_session()
    order, _ = make_order_with_item(db)
    festschreiben(db, _leistungsstand(db, order, "40"))
    null = mit_zeitraum(db, create_abschlag_leistungsstand(db, order))  # Ist = letzter Stand -> 0 €
    assert "lautet über 0,00 €" in _blocked(finalize_and_send_invoice, db, null)
    minus = mit_zeitraum(db, _leistungsstand(db, order, "30"))
    assert "lautet über -595,00 €" in _blocked(finalize_and_send_invoice, db, minus)
    pauschal = mit_zeitraum(db, create_abschlag_pauschal(db, order, lump_sum_net=D("0.004")))  # gerundet 0,00 €
    assert "Ein Abschlag muss über 0 € liegen" in _blocked(finalize_and_send_invoice, db, pauschal)
    assert db.get(Invoice, null.id).invoice_number is None


def test_a_negative_final_invoice_is_rejected_until_r4c_and_zero_is_allowed():
    db = db_session()
    order, _ = make_order_with_item(db)
    zu_viel = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("6000")))
    schluss = mit_zeitraum(db, create_schlussrechnung(db, order))
    grund = _blocked(finalize_and_send_invoice, db, schluss)
    assert "lautet über -1.190,00 €" in grund and "R4c" in grund
    assert invoice_to_dict(db.get(Invoice, schluss.id))["finalize_block"] == grund
    db.delete(db.get(Invoice, schluss.id))
    db.commit()
    festschreiben(db, create_storno_draft(db, zu_viel))
    festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("5000")))
    null = festschreiben(db, create_schlussrechnung(db, order))
    assert _totals(null) == (D("0.00"), D("0.00"), D("0.00"))
    assert compute_order_billing_progress(db, order.id)["invoiced_net"] == D("5000.00")


# ---------------------------------------------------------------------------
# Punkt 5
# ---------------------------------------------------------------------------

def test_final_invoice_next_to_a_lump_sum_progress_invoice_is_no_longer_blocked():
    db = db_session()
    order, _ = make_order_with_item(db)
    festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("2000")))
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    assert _totals(schluss) == (D("3000.00"), D("570.00"), D("3570.00"))


def test_no_effort_invoice_after_the_valid_final_invoice():
    db = db_session()
    order, _ = make_order_with_item(db)
    vorher = festschreiben(db, _aufwand(db, order, "100"))
    entwurf = mit_zeitraum(db, _aufwand(db, order, "50"))  # Entwurf vor der Schlussrechnung
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    assert "keine Rechnung aus Aufwand mehr möglich" in _blocked(_aufwand, db, order, "20")
    assert "keine Rechnung aus Aufwand mehr möglich" in _blocked(finalize_and_send_invoice, db, db.get(Invoice, entwurf.id))
    grund = _blocked(create_storno_draft, db, vorher)
    assert "Rechnung aus Aufwand ist in der Schlussrechnung" in grund
    festschreiben(db, create_storno_draft(db, schluss))
    festschreiben(db, db.get(Invoice, entwurf.id))  # nach dem Storno der Schlussrechnung wieder möglich


def test_the_order_page_names_the_effort_block():
    from app.orders import load_order, order_to_dict
    db = db_session()
    order, _ = make_order_with_item(db)
    festschreiben(db, create_schlussrechnung(db, order))
    blocks = order_to_dict(load_order(db, order.id), db)["invoice_create_blocks"]
    assert "keine Rechnung aus Aufwand mehr möglich" in blocks["aufwand"]
    assert blocks["schluss"].startswith("Am Auftrag besteht schon eine Schlussrechnung")


# ---------------------------------------------------------------------------
# Gleichzeitig: PostgreSQL
# ---------------------------------------------------------------------------

def _pg_leistungsstand(Session, order_id, ist):
    return _vorbereiten(Session, lambda s: mit_zeitraum(s, _leistungsstand(s, s.get(Order, order_id), ist)).id)


def _fest(invoice_id):
    return lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number


def test_postgresql_two_progress_drafts_finalized_at_once_bill_the_cumulative_quantity(pg):
    """1b unter PostgreSQL: das zweite Festschreiben wartet und rechnet gegen den Stand des ersten (vorher beide gegen 0)."""
    Session, order_id = pg
    erster, zweiter = _pg_leistungsstand(Session, order_id, "4"), _pg_leistungsstand(Session, order_id, "8")
    first, second = _run(Session, _fest(erster), _fest(zweiter))
    assert isinstance(second, str), second
    assert _vorbereiten(Session, lambda s: s.get(Invoice, zweiter).items[0].billed_quantity) == D("4")
    assert _vorbereiten(Session, lambda s: compute_order_billing_progress(s, order_id)["invoiced_net"]) == D("400.00")


def test_postgresql_final_invoice_waits_for_a_progress_invoice_and_deducts_it(pg):
    Session, order_id = pg
    abschlag = _pg_leistungsstand(Session, order_id, "4")
    schluss = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, _fest(abschlag), _fest(schluss))
    assert isinstance(second, str), second
    assert _vorbereiten(Session, lambda s: [r.deducted_invoice_id for r in s.get(Invoice, schluss).deductions]) == [abschlag]
    assert _vorbereiten(Session, lambda s: compute_invoice_totals(s.get(Invoice, schluss))["net_total"]) == D("300.00")


def test_postgresql_a_progress_invoice_waiting_for_the_final_invoice_is_rejected(pg):
    Session, order_id = pg
    abschlag = _pg_leistungsstand(Session, order_id, "4")
    schluss = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, _fest(schluss), _fest(abschlag))
    assert isinstance(second, InvoiceBlocked) and f"Nach der Schlussrechnung {first}" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(Invoice, schluss).deductions) == []
    assert _vorbereiten(Session, lambda s: compute_invoice_totals(s.get(Invoice, schluss))["net_total"]) == D("500.00")


def test_postgresql_cancelling_a_progress_invoice_while_the_final_invoice_is_finalized(pg):
    """Storno und Festschreiben der Schlussrechnung gleichzeitig: das Storno zuerst -- die Schlussrechnung zieht den stornierten
    Abschlag nicht ab (1b c unter PostgreSQL)."""
    Session, order_id = pg
    abschlag = _pg_leistungsstand(Session, order_id, "4")
    _vorbereiten(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, abschlag)))
    storno = _vorbereiten(Session, lambda s: create_storno_draft(s, s.get(Invoice, abschlag)).id)
    _vorbereiten(Session, lambda s: mit_zeitraum(s, s.get(Invoice, storno)))
    schluss = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, _fest(storno), _fest(schluss))
    assert isinstance(second, str), second
    assert _vorbereiten(Session, lambda s: s.get(Invoice, schluss).deductions) == []
    assert _vorbereiten(Session, lambda s: compute_order_billing_progress(s, order_id)["invoiced_net"]) == D("500.00")


def test_postgresql_a_price_change_waiting_for_finalizing_does_not_slip_into_the_draft(pg):
    """Der Preis am Auftrag wird geändert, während ein Abschlag festgeschrieben wird: die Änderung wartet, danach ist der Preis
    gesperrt (1.8.82); umgekehrt wartet das Festschreiben auf die Änderung und lehnt mit der Abweichung ab."""
    Session, order_id = pg
    item_id = _vorbereiten(Session, lambda s: s.scalar(select(OrderItem.id).where(OrderItem.order_id == order_id)))
    abschlag = _pg_leistungsstand(Session, order_id, "4")

    def preis(s):
        item = s.get(OrderItem, item_id)
        return update_order_item(s, order_id, item_id, quantity=item.quantity, unit=item.unit, unit_price=D("60"),
                                 short_text=item.short_text, long_text=item.long_text or "", position_type=item.position_type,
                                 gaeb_oz=item.gaeb_oz, include_in_total=True) and "geaendert"
    first, second = _run(Session, preis, _fest(abschlag))
    assert isinstance(second, InvoiceBlocked) and "Einheitspreis Pos. 1 (Entwurf 50,00 €, Auftrag 60,00 €)" in str(second)
    assert _vorbereiten(Session, lambda s: s.get(Invoice, abschlag).status) == "entwurf"
