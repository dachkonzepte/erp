"""Version 1.8.86 -- Zahlungshinweis der Endrechnung, abschließende Rechnung aus Aufwand (R4b Punkte 4 und 6,
docs/archiv/befund-vor-echtbetrieb.md "Umsetzung R4b").

- Punkt 4: die Endrechnung nennt "Stand <Tag des Festschreibens>" je abgezogener Rechnung mit offenem Betrag (einschließlich
  Einbehalt) "zzgl. noch offen aus Abschlag Nr. …", darunter den Zahlbetrag -- im Entwurf live, beim Festschreiben an den Abzügen
  eingefroren. Der Rechnungsbetrag bleibt der Betrag der Rechnung.
- Punkt 6: eine Rechnung aus Aufwand an einem Auftrag nach Aufwand (Auftragssumme 0 €, Schnellauftrag) lässt sich als abschließend
  kennzeichnen und zählt dann als "vollständig abgerechnet" wie eine Schlussrechnung; dort gibt es keine Schlussrechnung über 0 €."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update

from app.berlin_time import berlin_today
from app.invoices import (
    ZERO_FINAL_TEXT, InvoiceBlocked, add_invoice_item, compute_invoice_totals, create_abschlag_leistungsstand,
    create_abschlag_pauschal, create_invoice_from_time_entries, create_schlussrechnung, create_storno_draft,
    finalize_and_send_invoice, invoice_summary_for_order, invoice_to_dict, payment_note, update_invoice_header,
    update_invoice_item,
)
from app.invoice_pdf import build_invoice_pdf
from app.models import Invoice, InvoiceDeduction, Order, OrderItem
from app.order_locks import OrderLocked
from app.orders import add_order_addendum, load_order, order_to_dict, sync_block_reasons, update_order_item
from app.payments import Line, book_payment, invoice_customer_id, payment_state
from app.routers.invoices import router as invoices_router
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v325_contract_basis import pdf_text
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)
from tests.zahlung import voll_bezahlen

D = Decimal


def _leistungsstand(db, order, ist):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return invoice


def _aufwand(db, order, betrag):
    invoice = create_invoice_from_time_entries(
        db, order, [], [SimpleNamespace(material_id=None, description="Kleinmaterial", unit="Stk", quantity=D("1"))])
    add_invoice_item(db, invoice, short_text="Reparatur", long_text="", unit="Std.", unit_price=D(betrag), ist_quantity=D("1"))
    db.refresh(invoice)
    return invoice


def _zahlen(db, invoice, zahlung, einbehalt="0"):
    book_payment(db, customer_id=invoice_customer_id(invoice), received_on=berlin_today(), amount=D(zahlung), note=None,
                 lines=[Line(invoice.id, zahlung=D(zahlung), einbehalt=D(einbehalt))], user_name="Test")


def _blocked(fn, *args, **kwargs) -> str:
    with pytest.raises(InvoiceBlocked) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _nach_aufwand(db):
    """Auftrag nach Aufwand wie der Schnellauftrag (app/quick_service_orders.py): eine Position 1 pauschal × 0 €."""
    order, _ = make_order_with_item(db, quantity=D("1"), unit_price=D("0"))
    return order


# ---------------------------------------------------------------------------
# Punkt 4: Zahlungshinweis
# ---------------------------------------------------------------------------

def test_payment_note_lists_what_is_still_open_including_retention_and_the_pay_amount():
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("1000")))
    voll_bezahlen(db, pauschal)  # bezahlt: erscheint nicht
    abschlag = festschreiben(db, _leistungsstand(db, order, "40"))  # 2.380 brutto
    _zahlen(db, abschlag, "1000", einbehalt="200")  # offen 1.380, davon Einbehalt 200
    aufwand = festschreiben(db, _aufwand(db, order, "100"))  # 119 brutto, offen
    schluss = create_schlussrechnung(db, order)
    note = payment_note(schluss)
    assert note["as_of"] == berlin_today()
    assert [(n["invoice_id"], n["open"], n["retained"]) for n in note["lines"]] == [
        (abschlag.id, D("1380.00"), D("200.00")), (aufwand.id, D("119.00"), D("0.00"))]
    betrag = compute_invoice_totals(schluss)["gross_total"]
    assert betrag == D("2380.00") and note["invoice_amount"] == betrag  # 5.950 + 119 − 1.190 − 2.380 − 119
    assert note["pay_amount"] == D("3879.00")  # 2.380 + 1.380 + 119
    festschreiben(db, schluss)
    assert [(r.open_amount, r.retained_open) for r in schluss.deductions] == [
        (D("0.00"), D("0.00")), (D("1380.00"), D("200.00")), (D("119.00"), D("0.00"))]
    _zahlen(db, abschlag, "1180")  # danach gezahlt: der Hinweis der Rechnung bleibt beim Stand des Festschreibens
    db.expire_all()
    schluss = db.get(Invoice, schluss.id)
    eingefroren = payment_note(schluss)
    assert eingefroren["as_of"] == schluss.invoice_date and eingefroren["pay_amount"] == D("3879.00")
    assert payment_state(db, db.get(Invoice, abschlag.id)).open == D("200.00")
    assert payment_state(db, schluss).open == D("2380.00")  # Zahlungen und offene Posten: der Rechnungsbetrag
    text = pdf_text(build_invoice_pdf(db, schluss))
    for erwartet in ("Zahlungshinweis", f"Stand {schluss.invoice_date.strftime('%d.%m.%Y')}",
                     f"zzgl. noch offen aus Abschlag Nr. {abschlag.invoice_number}", "davon Einbehalt 200,00 EUR",
                     f"zzgl. noch offen aus Rechnung Nr. {aufwand.invoice_number}", "Zahlbetrag", "3.879,00 EUR"):
        assert erwartet in text, erwartet


def test_payment_note_without_anything_open_and_not_on_the_cancellation():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order, "40"))
    voll_bezahlen(db, abschlag)
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    note = payment_note(schluss)
    assert note["lines"] == [] and note["pay_amount"] == note["invoice_amount"] == D("3570.00")
    storno = festschreiben(db, create_storno_draft(db, schluss))
    assert payment_note(storno) is None and invoice_to_dict(storno)["payment_note"] is None
    ohne = festschreiben(db, create_schlussrechnung(db, load_order(db, order.id)))
    assert payment_note(ohne)["lines"] == []


def test_deductions_without_frozen_state_show_no_payment_note():
    """Abzüge aus 1.8.85 (vor dem Zahlungshinweis) tragen keinen Stand -- dann kein Hinweis statt eines erfundenen."""
    db = db_session()
    order, _ = make_order_with_item(db)
    festschreiben(db, _leistungsstand(db, order, "40"))
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    db.execute(update(InvoiceDeduction.__table__).values(open_amount=None, retained_open=None))  # wie von 1.8.85
    db.commit()
    db.expire_all()
    assert payment_note(db.get(Invoice, schluss.id)) is None


def test_postgresql_a_payment_waiting_for_the_final_invoice_does_not_change_its_note(pg):
    """Zahlung und Festschreiben der Schlussrechnung gleichzeitig: dieselbe Sperre -- wartet die Zahlung, steht im Hinweis der
    Stand davor; wartet das Festschreiben, der Stand danach."""
    Session, order_id = pg
    abschlag = _vorbereiten(Session, lambda s: festschreiben(s, _leistungsstand(s, s.get(Order, order_id), "4")).id)
    schluss = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, schluss)).invoice_number,
                         lambda s: _zahlen(s, s.get(Invoice, abschlag), "100") or "gezahlt")
    assert second == "gezahlt", second
    assert _vorbereiten(Session, lambda s: [r.open_amount for r in s.get(Invoice, schluss).deductions]) == [D("238.00")]
    assert _vorbereiten(Session, lambda s: payment_state(s, s.get(Invoice, abschlag)).open) == D("138.00")


def test_postgresql_the_final_invoice_waiting_for_a_payment_freezes_the_state_after_it(pg):
    Session, order_id = pg
    abschlag = _vorbereiten(Session, lambda s: festschreiben(s, _leistungsstand(s, s.get(Order, order_id), "4")).id)
    schluss = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, lambda s: _zahlen(s, s.get(Invoice, abschlag), "100") or "gezahlt",
                         lambda s: finalize_and_send_invoice(s, s.get(Invoice, schluss)).invoice_number)
    assert isinstance(second, str), second
    assert _vorbereiten(Session, lambda s: [r.open_amount for r in s.get(Invoice, schluss).deductions]) == [D("138.00")]


# ---------------------------------------------------------------------------
# Punkt 6: abschließende Rechnung aus Aufwand
# ---------------------------------------------------------------------------

def test_an_effort_order_closes_with_a_closing_effort_invoice():
    db = db_session()
    order = _nach_aufwand(db)
    erste = festschreiben(db, _aufwand(db, order, "246"))
    assert invoice_summary_for_order(db, order.id) == (1, False)
    letzte = _aufwand(db, order, "120")
    assert invoice_to_dict(letzte)["closing_block"] is None
    update_invoice_header(db, letzte, closes_order=True)
    letzte = festschreiben(db, db.get(Invoice, letzte.id))
    assert letzte.closes_order and invoice_summary_for_order(db, order.id) == (2, True)
    blocks = order_to_dict(load_order(db, order.id), db)["invoice_create_blocks"]
    assert all("vollständig abgerechnet" in (blocks[k] or "") for k in ("abschlag_pauschal", "aufwand"))
    assert blocks["schluss"] == ZERO_FINAL_TEXT
    assert "vollständig abgerechnet" in _blocked(_aufwand, db, order, "10")
    assert "zuerst sie stornieren" in _blocked(create_storno_draft, db, erste)
    item = db.scalar(select(OrderItem).where(OrderItem.order_id == order.id))
    with pytest.raises(OrderLocked, match="Nach der abschließenden Rechnung aus Aufwand"):
        update_order_item(db, order.id, item.id, quantity=D("2"), unit=item.unit, unit_price=item.unit_price,
                          short_text=item.short_text, long_text="", position_type=item.position_type, gaeb_oz=item.gaeb_oz,
                          include_in_total=True)
    with pytest.raises(OrderLocked):
        add_order_addendum(db, order.id, short_text="Nachtrag", long_text="", quantity=D("1"), unit="Stk", unit_price=D("10"))
    assert any("abschließende Rechnung aus Aufwand" in r for r in sync_block_reasons(db, db.get(Order, order.id)))
    festschreiben(db, create_storno_draft(db, letzte))  # Storno öffnet den Auftrag wieder
    assert invoice_summary_for_order(db, order.id) == (2, False)  # die erste und die Stornorechnung
    festschreiben(db, _aufwand(db, order, "10"))


def test_no_final_invoice_over_zero_on_an_effort_order():
    db = db_session()
    order = _nach_aufwand(db)
    festschreiben(db, _aufwand(db, order, "246"))
    assert _blocked(create_schlussrechnung, db, order) == ZERO_FINAL_TEXT


def test_a_final_draft_of_an_order_that_became_effort_only_is_rejected_at_finalizing():
    """Ein Entwurf von früher (Auftrag damals mit Preis) wird beim Festschreiben abgelehnt -- der Grund vor der Abweichung."""
    db = db_session()
    order, item = make_order_with_item(db)
    entwurf = mit_zeitraum(db, create_schlussrechnung(db, order))
    item.unit_price = D("0")  # nichts abgerechnet: am Auftrag erlaubt
    db.commit()
    assert _blocked(finalize_and_send_invoice, db, db.get(Invoice, entwurf.id)) == ZERO_FINAL_TEXT


def test_closing_only_for_effort_invoices_of_an_effort_order():
    db = db_session()
    order, _ = make_order_with_item(db)  # Auftrag mit Preisen: ihn schließt die Schlussrechnung ab
    aufwand = _aufwand(db, order, "100")
    grund = invoice_to_dict(aufwand)["closing_block"]
    assert grund.startswith("„Abschließend“ gibt es nur bei einem Auftrag nach Aufwand") and "5.000,00 €" in grund
    assert _blocked(update_invoice_header, db, aufwand, closes_order=True) == grund
    pauschal = create_abschlag_pauschal(db, order, lump_sum_net=D("100"))
    assert "nur eine Rechnung aus Aufwand" in _blocked(update_invoice_header, db, pauschal, closes_order=True)
    assert invoice_to_dict(pauschal)["closing_block"] is None and invoice_to_dict(pauschal)["closes_order"] is False


def test_a_priced_addendum_after_marking_blocks_finalizing_and_only_one_closing_invoice():
    db = db_session()
    order = _nach_aufwand(db)
    erste = mit_zeitraum(db, _aufwand(db, order, "100"))
    zweite = mit_zeitraum(db, _aufwand(db, order, "50"))
    update_invoice_header(db, erste, closes_order=True)
    update_invoice_header(db, zweite, closes_order=True)
    festschreiben(db, db.get(Invoice, erste.id))
    assert "vollständig abgerechnet" in _blocked(finalize_and_send_invoice, db, db.get(Invoice, zweite.id))
    festschreiben(db, create_storno_draft(db, db.get(Invoice, erste.id)))
    add_order_addendum(db, order.id, short_text="Kaminblech", long_text="", quantity=D("1"), unit="Stk", unit_price=D("80"))
    grund = _blocked(finalize_and_send_invoice, db, db.get(Invoice, zweite.id))
    assert "nur bei einem Auftrag nach Aufwand" in grund and "80,00 €" in grund
    update_invoice_header(db, db.get(Invoice, zweite.id), closes_order=False)  # Kennzeichen entfernen geht immer
    festschreiben(db, db.get(Invoice, zweite.id))


def test_router_marks_closing_and_answers_409(threaded_db_session, router_test_client):
    db = threaded_db_session
    order = _nach_aufwand(db)
    aufwand = _aufwand(db, order, "100")
    client = router_test_client(db, invoices_router)
    antwort = client.put(f"/api/invoices/{aufwand.id}", json={"closes_order": True})
    assert antwort.status_code == 200 and antwort.json()["closes_order"] is True
    assert client.put(f"/api/invoices/{aufwand.id}", json={"closes_order": False}).json()["closes_order"] is False
    order.items[0].unit_price = D("10")  # jetzt mit Preis
    db.commit()
    antwort = client.put(f"/api/invoices/{aufwand.id}", json={"closes_order": True})
    assert antwort.status_code == 409 and "nur bei einem Auftrag nach Aufwand" in antwort.json()["detail"]
    assert client.put(f"/api/invoices/{aufwand.id}", json={"closes_order": None}).status_code == 422


def test_postgresql_two_closing_invoices_at_once_only_one_closes(pg):
    Session, order_id = pg

    def entwurf(s):
        order = s.get(Order, order_id)
        for item in order.items:
            item.unit_price = D("0")  # Auftrag nach Aufwand
        s.commit()
        invoice = mit_zeitraum(s, _aufwand(s, s.get(Order, order_id), "100"))
        update_invoice_header(s, invoice, closes_order=True)
        return invoice.id
    a, b = _vorbereiten(Session, entwurf), _vorbereiten(Session, lambda s: entwurf(s))
    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, a)).invoice_number,
                         lambda s: finalize_and_send_invoice(s, s.get(Invoice, b)))
    assert isinstance(second, InvoiceBlocked) and "vollständig abgerechnet" in str(second), second
    assert _vorbereiten(Session, lambda s: invoice_summary_for_order(s, order_id)) == (2, True)  # die zweite bleibt Entwurf
    assert _vorbereiten(Session, lambda s: s.get(Invoice, b).status) == "entwurf"
