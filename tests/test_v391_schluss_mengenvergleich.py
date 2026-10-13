"""Version 1.8.88 -- Mengenvergleich im Entwurf der Schlussrechnung (Ergänzung zu Festlegung 1.8.85 Nr. 1, Vorgabe R4c).

Der Entwurf zeigt je Position die Menge des Auftrags (heute), die zuletzt abgerechnete Menge (Ist der zuletzt festgeschriebenen
Rechnung dieser Position) und das Ist nebeneinander und markiert Abweichungen: "auftrag" (Ist ≠ Menge des Auftrags), "abgerechnet"
(Ist unter der zuletzt abgerechneten Menge). Nach dem Festschreiben und an jeder anderen Rechnung gibt es keinen Vergleich.

Auftrag aus tests/test_v133_invoices.py: 100 m² × 50 €."""

from decimal import Decimal

from app.invoices import (
    create_abschlag_leistungsstand, create_schlussrechnung, create_storno_draft, final_quantity_checks, invoice_to_dict,
    update_invoice_item,
)
from app.orders import add_order_addendum, update_order_item
from app.routers.invoices import router as invoices_router
from tests.leistungszeitraum import festschreiben
from tests.test_v133_invoices import db_session, make_order_with_item

D = Decimal


def _abschlag(db, order, ist):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return festschreiben(db, invoice)


def _check(invoice, item_id):
    return final_quantity_checks(invoice)[item_id]


def _ist(db, schluss, item, ist):
    update_invoice_item(db, schluss, item, ist_quantity=D(ist))
    db.refresh(schluss)


def test_draft_shows_order_quantity_last_billed_and_actual_without_deviation():
    db = db_session()
    order, _ = make_order_with_item(db)
    _abschlag(db, order, "40")
    schluss = create_schlussrechnung(db, order)
    [position] = schluss.items
    assert _check(schluss, position.id) == {"order_quantity": D("100"), "last_billed_quantity": D("40"), "deviations": []}
    row = invoice_to_dict(schluss)["items"][0]
    assert row["quantity_check"] == {"order_quantity": D("100"), "last_billed_quantity": D("40"), "deviations": []}


def test_actual_below_order_quantity_and_below_last_billed_is_marked():
    db = db_session()
    order, _ = make_order_with_item(db)
    _abschlag(db, order, "40")
    schluss = create_schlussrechnung(db, order)
    [position] = schluss.items
    _ist(db, schluss, position, "95")  # Aufmaß kleiner als beauftragt
    assert _check(schluss, position.id)["deviations"] == ["auftrag"]
    _ist(db, schluss, position, "30")  # unter dem schon abgerechneten Stand
    assert _check(schluss, position.id)["deviations"] == ["auftrag", "abgerechnet"]
    _ist(db, schluss, position, "120")  # mehr als beauftragt
    assert _check(schluss, position.id)["deviations"] == ["auftrag"]
    _ist(db, schluss, position, "100")
    assert _check(schluss, position.id)["deviations"] == []


def test_never_billed_position_and_addendum_start_at_zero():
    db = db_session()
    order, _ = make_order_with_item(db)
    add_order_addendum(db, order.id, short_text="Kaminverblechung", long_text="", quantity=D("2"), unit="Stk",
                       unit_price=D("250"))
    schluss = create_schlussrechnung(db, order)
    checks = {i.position_number: _check(schluss, i.id) for i in schluss.items}
    assert checks == {"1": {"order_quantity": D("100"), "last_billed_quantity": D("0"), "deviations": []},
                      "N1": {"order_quantity": D("2"), "last_billed_quantity": D("0"), "deviations": []}}


def test_order_quantity_is_read_live_and_last_billed_follows_the_latest_finalized():
    db = db_session()
    order, item = make_order_with_item(db)
    _abschlag(db, order, "40")
    schluss = create_schlussrechnung(db, order)
    [position] = schluss.items
    update_order_item(db, order.id, item.id, quantity=D("120"))  # Menge des Auftrags bis zur Schlussrechnung änderbar
    db.refresh(schluss)
    assert _check(schluss, position.id) == {"order_quantity": D("120"), "last_billed_quantity": D("40"),
                                            "deviations": ["auftrag"]}
    assert position.soll_quantity == D("100")  # der Schnappschuss beim Anlegen -- der Vergleich nimmt den Auftrag von heute
    _abschlag(db, order, "70")  # ein weiterer Abschlag, nach dem Entwurf festgeschrieben
    db.refresh(schluss)
    assert _check(schluss, position.id)["last_billed_quantity"] == D("70")


def test_storno_of_the_last_abschlag_falls_back_to_the_one_before():
    db = db_session()
    order, _ = make_order_with_item(db)
    _abschlag(db, order, "40")
    zweiter = _abschlag(db, order, "70")
    festschreiben(db, create_storno_draft(db, zweiter))
    schluss = create_schlussrechnung(db, order)
    assert _check(schluss, schluss.items[0].id)["last_billed_quantity"] == D("40")


def test_no_comparison_after_finalizing_and_on_other_invoices():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = create_abschlag_leistungsstand(db, order)
    assert final_quantity_checks(abschlag) == {}
    assert invoice_to_dict(abschlag)["items"][0]["quantity_check"] is None
    db.delete(abschlag)
    db.commit()
    schluss = create_schlussrechnung(db, order)
    festschreiben(db, schluss)
    assert final_quantity_checks(schluss) == {}
    assert invoice_to_dict(schluss)["items"][0]["quantity_check"] is None


def test_router_returns_the_comparison(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    _abschlag(db, order, "40")
    schluss = create_schlussrechnung(db, order)
    _ist(db, schluss, schluss.items[0], "30")
    client = router_test_client(db, invoices_router)
    data = client.get(f"/api/invoices/{schluss.id}").json()
    assert data["items"][0]["quantity_check"] == {"order_quantity": "100.000000", "last_billed_quantity": "40.000000",
                                                  "deviations": ["auftrag", "abgerechnet"]}
