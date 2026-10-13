"""Version 1.8.93 -- Guthaben des Kunden (Nacharbeit R4c Punkt 3, docs/archiv/befund-vor-echtbetrieb.md "Nacharbeiten R4c").

Am Kunden stehen nicht zugeordneter Rest und Guthaben aus Endrechnungen zusammen als "Guthaben des Kunden", aufgeschlüsselt
(app/payments.py::customer_balance()); eine Erstattung kann beides ausgleichen (book_customer_refund(): ein Zahlungsausgang, aus dem
Guthaben einer Endrechnung als Zuordnung "erstattung", aus dem Rest einer Zahlung über PaymentRefundSource).

Auftrag aus tests/test_v133_invoices.py: 100 m² × 50 € = 5.000 € netto. Abschlag nach Leistungsstand 100 m² = 5.950 € brutto, bezahlt;
die Schlussrechnung mit dem Aufmaß 80 m² lautet über −1.190 € (Guthaben 1.190 €). Dazu eine Zahlung über 50 €, nicht zugeordnet.
Angriffstests (fremder Kunde, fremde Zahlung, Zahlungsausgang als Quelle, zurückgenommene Zahlung, zu viel, doppelt, Zukunft) und
Gleichzeitigkeit gegen PostgreSQL am Ende."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.berlin_time import berlin_today
from app.final_dunning import dunning_state
from app.invoices import (
    create_abschlag_leistungsstand, create_schlussrechnung, create_storno_draft, finalize_and_send_invoice, update_invoice_item,
)
from app.models import ArchiveImmutableError, Customer, Invoice, Order, Payment, PaymentAllocation, PaymentRefundSource
from app.payments import (
    Line, PaymentRejected, RefundLine, allocate_rest, book_customer_refund, book_payment, book_refund, customer_balances,
    customer_payments, invoice_customer_id, payment_rest, reverse_payment, unallocated_by_customer,
)
from app.routers.payments import router as payments_router
from app.zugehoerigkeit import IdNichtGefunden
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

D = Decimal
HEUTE = berlin_today()
TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def _abschlag(db, order, ist="100"):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return festschreiben(db, invoice)


def _zahlen(db, customer_id, betrag, invoice=None):
    lines = [Line(invoice.id, zahlung=D(betrag))] if invoice is not None else []
    return book_payment(db, customer_id=customer_id, received_on=HEUTE, amount=D(betrag), note=None, lines=lines, user_name="Test")


def _welt(db):
    """Schlussrechnung −1.190 € (Guthaben 1.190 €) und eine Zahlung über 50 € ohne Zuordnung."""
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order)
    kunde = invoice_customer_id(abschlag)
    _zahlen(db, kunde, "5950", abschlag)
    schluss = create_schlussrechnung(db, order)
    update_invoice_item(db, schluss, schluss.items[0], ist_quantity=D("80"))
    db.refresh(schluss)
    schluss = festschreiben(db, schluss)
    rest = _zahlen(db, kunde, "50")
    return kunde, schluss, rest


def _fremder_kunde(db):
    """Ein anderer Kunde mit einer Zahlung über 30 € ohne Zuordnung."""
    other = Customer(name="Fremd", last_name="Fremd")
    db.add(other)
    db.commit()
    return other, _zahlen(db, other.id, "30")


def _rejected(fn, *args, **kwargs) -> str:
    with pytest.raises(PaymentRejected) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _anzahl(db, model):
    return db.scalar(select(func.count()).select_from(model))


# ---------------------------------------------------------------------------
# Guthaben des Kunden: Rest und Guthaben zusammen, aufgeschlüsselt
# ---------------------------------------------------------------------------

def test_customer_balance_combines_rest_and_credit_line_by_line():
    db = db_session()
    kunde, schluss, rest = _welt(db)
    balance = customer_payments(db, kunde)["balance"]
    assert (balance["rest"], balance["credit"], balance["total"]) == (D("50.00"), D("1190.00"), D("1240.00"))
    assert [(line["kind"], line["payment_id"], line["invoice_id"], line["amount"]) for line in balance["lines"]] == [
        ("rest", rest.id, None, D("50.00")), ("guthaben", None, schluss.id, D("1190.00"))]
    assert balance["lines"][1]["invoice_number"] == schluss.invoice_number
    assert customer_balances(db) == [{"customer_id": kunde, "customer_name": "Test Kunde", "rest": D("50.00"),
                                      "credit": D("1190.00"), "total": D("1240.00")}]


def test_one_refund_settles_rest_and_credit():
    db = db_session()
    kunde, schluss, rest = _welt(db)
    refund = book_customer_refund(db, kunde, paid_on=HEUTE, note="Überweisung", user_name="Bea",
                                  lines=[RefundLine(D("50"), payment_id=rest.id), RefundLine(D("1190"), invoice_id=schluss.id)])
    assert (refund.amount, refund.customer_id, refund.created_by_name) == (D("-1240.00"), kunde, "Bea")
    allocation = db.scalar(select(PaymentAllocation).where(PaymentAllocation.payment_id == refund.id))
    assert (allocation.kind, allocation.invoice_id, allocation.amount) == ("erstattung", schluss.id, D("-1190.00"))
    source = db.scalar(select(PaymentRefundSource).where(PaymentRefundSource.refund_payment_id == refund.id))
    assert (source.source_payment_id, source.amount) == (rest.id, D("50.00"))
    assert (payment_rest(db, rest), payment_rest(db, refund)) == (D("0.00"), D("0.00"))
    assert dunning_state(db, schluss).credit == D("0.00")
    data = customer_payments(db, kunde)
    assert (data["balance"]["total"], data["balance"]["lines"], data["rest"]) == (D("0.00"), [], D("0.00"))
    rows = {p["id"]: p for p in data["payments"]}
    assert rows[refund.id]["refund_sources"] == [{"payment_id": rest.id, "amount": D("50.00"), "received_on": HEUTE}]
    assert rows[rest.id]["refunded_from_rest"] == [{"refund_payment_id": refund.id, "amount": D("50.00"), "paid_on": HEUTE}]
    assert unallocated_by_customer(db) == [] and customer_balances(db) == []


def test_partial_refund_from_the_rest_leaves_the_remainder():
    db = db_session()
    kunde, _, rest = _welt(db)
    book_customer_refund(db, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("20"), payment_id=rest.id)])
    assert payment_rest(db, rest) == D("30.00")
    balance = customer_payments(db, kunde)["balance"]
    assert (balance["rest"], balance["total"]) == (D("30.00"), D("1220.00"))
    assert [r["rest"] for r in unallocated_by_customer(db)] == [D("30.00")]


def test_the_rest_after_a_refund_can_no_longer_be_allocated():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order)
    kunde = invoice_customer_id(abschlag)
    _zahlen(db, kunde, "5940", abschlag)  # 10 € offen
    rest = _zahlen(db, kunde, "50")
    book_customer_refund(db, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("50"), payment_id=rest.id)])
    reason = _rejected(allocate_rest, db, rest, [Line(abschlag.id, zahlung=D("10"))])
    assert reason == "Überbuchung der Zahlung: zugeordnet werden sollen 10,00 €, offen an der Zahlung sind 0,00 €."


# ---------------------------------------------------------------------------
# Angriffstests
# ---------------------------------------------------------------------------

def test_rest_of_another_customers_payment_is_refused_and_nothing_written():
    db = db_session()
    kunde, _, _ = _welt(db)
    _, fremd = _fremder_kunde(db)
    before = _anzahl(db, Payment)
    reason = _rejected(book_customer_refund, db, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("30"), payment_id=fremd.id)])
    assert reason == f"Die Zahlung Nr. {fremd.id} gehört zu einem anderen Kunden."
    assert (_anzahl(db, Payment), _anzahl(db, PaymentRefundSource), payment_rest(db, fremd)) == (before, 0, D("30.00"))


def test_credit_of_another_customers_final_invoice_is_refused():
    db = db_session()
    _, schluss, _ = _welt(db)
    other, _ = _fremder_kunde(db)
    reason = _rejected(book_customer_refund, db, other.id, paid_on=HEUTE, note=None,
                       lines=[RefundLine(D("100"), invoice_id=schluss.id)])
    assert reason == f"Die Rechnung {schluss.invoice_number} gehört zu einem anderen Kunden."
    assert dunning_state(db, schluss).credit == D("1190.00")


def test_unknown_ids_are_not_found():
    db = db_session()
    kunde, _, _ = _welt(db)
    for line in (RefundLine(D("1"), payment_id=999999), RefundLine(D("1"), invoice_id=999999)):
        with pytest.raises(IdNichtGefunden):
            book_customer_refund(db, kunde, paid_on=HEUTE, note=None, lines=[line])
    with pytest.raises(IdNichtGefunden):
        book_customer_refund(db, 999999, paid_on=HEUTE, note=None, lines=[RefundLine(D("1"), payment_id=1)])


def test_a_refund_or_a_reversed_payment_is_no_source():
    db = db_session()
    kunde, schluss, rest = _welt(db)
    ausgang = book_refund(db, schluss, paid_on=HEUTE, amount=D("100"), note=None)
    reason = _rejected(book_customer_refund, db, kunde, paid_on=HEUTE, note=None,
                       lines=[RefundLine(D("1"), payment_id=ausgang.id)])
    assert "ist ein Zahlungsausgang" in reason
    reverse_payment(db, rest, reason="falsch erfasst")
    reason = _rejected(book_customer_refund, db, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("1"), payment_id=rest.id)])
    assert "ist zurückgenommen" in reason
    counter = db.scalar(select(Payment).where(Payment.reverses_payment_id == rest.id))
    reason = _rejected(book_customer_refund, db, kunde, paid_on=HEUTE, note=None,
                       lines=[RefundLine(D("1"), payment_id=counter.id)])
    assert "ist zurückgenommen" in reason or "Zahlungsausgang" in reason


def test_more_than_the_rest_or_the_credit_is_refused_and_nothing_written():
    db = db_session()
    kunde, schluss, rest = _welt(db)
    reason = _rejected(book_customer_refund, db, kunde, paid_on=HEUTE, note=None,
                       lines=[RefundLine(D("50.01"), payment_id=rest.id)])
    assert reason == f"Überbuchung: an der Zahlung Nr. {rest.id} sind 50,00 € nicht zugeordnet, erstattet werden sollen 50,01 €."
    reason = _rejected(book_customer_refund, db, kunde, paid_on=HEUTE, note=None,
                       lines=[RefundLine(D("10"), payment_id=rest.id), RefundLine(D("1190.01"), invoice_id=schluss.id)])
    assert "das Guthaben aus der Schlussrechnung" in reason and "1.190,00" in reason
    assert (_anzahl(db, PaymentRefundSource), payment_rest(db, rest)) == (0, D("50.00"))
    assert db.scalar(select(Payment).where(Payment.amount < 0)) is None


@pytest.mark.parametrize("lines, text", [
    ([], "mindestens einen Betrag"),
    ([RefundLine(D("1"))], "entweder aus einer Schlussrechnung oder aus einer Zahlung"),
    ([RefundLine(D("1"), invoice_id=1, payment_id=1)], "entweder aus einer Schlussrechnung oder aus einer Zahlung"),
    ([RefundLine(D("0"), payment_id=1)], "größer als 0"),
    ([RefundLine(D("-5"), payment_id=1)], "größer als 0"),
    ([RefundLine(D("1.001"), payment_id=1)], "zwei Nachkommastellen"),
])
def test_malformed_lines_are_refused(lines, text):
    db = db_session()
    kunde, _, _ = _welt(db)
    with pytest.raises(ValueError) as exc:
        book_customer_refund(db, kunde, paid_on=HEUTE, note=None, lines=lines)
    assert text in str(exc.value) and not isinstance(exc.value, PaymentRejected)


def test_the_same_payment_twice_in_one_refund_is_refused():
    db = db_session()
    kunde, _, rest = _welt(db)
    with pytest.raises(ValueError) as exc:
        book_customer_refund(db, kunde, paid_on=HEUTE, note=None,
                             lines=[RefundLine(D("30"), payment_id=rest.id), RefundLine(D("20"), payment_id=rest.id)])
    assert "höchstens einmal" in str(exc.value)


def test_refund_in_the_future_is_refused():
    db = db_session()
    kunde, _, rest = _welt(db)
    with pytest.raises(ValueError) as exc:
        book_customer_refund(db, kunde, paid_on=HEUTE + timedelta(days=1), note=None, lines=[RefundLine(D("1"), payment_id=rest.id)])
    assert "Zukunft" in str(exc.value)


def test_the_source_payment_cannot_be_reversed_while_the_refund_stands():
    db = db_session()
    kunde, schluss, rest = _welt(db)
    refund = book_customer_refund(db, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("50"), payment_id=rest.id)])
    reason = _rejected(reverse_payment, db, rest, reason="falsch erfasst")
    assert reason == (f"Aus dem Rest dieser Zahlung ist erstattet (50,00 €, Zahlungsausgang Nr. {refund.id}) -- erst den "
                      "Zahlungsausgang zurücknehmen.")
    reverse_payment(db, refund, reason="Überweisung kam zurück")
    assert payment_rest(db, rest) == D("50.00")
    assert customer_payments(db, kunde)["balance"]["total"] == D("1240.00")
    reverse_payment(db, rest, reason="falsch erfasst")  # jetzt geht es
    assert payment_rest(db, rest) == D("0.00")


def test_refund_source_rows_are_immutable():
    db = db_session()
    kunde, _, rest = _welt(db)
    book_customer_refund(db, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("50"), payment_id=rest.id)])
    source = db.scalar(select(PaymentRefundSource))
    source.amount = D("1")
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    db.delete(db.scalar(select(PaymentRefundSource)))
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()


def test_invoice_page_refund_still_settles_only_its_credit():
    db = db_session()
    kunde, schluss, rest = _welt(db)
    book_refund(db, schluss, paid_on=HEUTE, amount=D("1190"), note=None)
    balance = customer_payments(db, kunde)["balance"]
    assert (balance["rest"], balance["credit"]) == (D("50.00"), D("0.00"))
    storno_reason = None
    try:
        create_storno_draft(db, schluss)
    except Exception as exc:  # noqa: BLE001 -- Storno erst nach Rücknahme der Erstattung (Festlegung 1.8.90 Nr. 6)
        storno_reason = str(exc)
    assert storno_reason and "Erstattung" in storno_reason


# ---------------------------------------------------------------------------
# API und Oberfläche
# ---------------------------------------------------------------------------

def test_router_books_a_customer_refund_and_lists_the_balances(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde, schluss, rest = _welt(db)
    client = router_test_client(db, payments_router)
    balances = client.get("/api/payments/customer-balances").json()
    assert balances == [{"customer_id": kunde, "customer_name": "Test Kunde", "rest": "50.00", "credit": "1190.00",
                         "total": "1240.00"}]
    url = f"/api/customers/{kunde}/refunds"
    body = {"paid_on": HEUTE.isoformat(), "note": "an den Kunden",
            "lines": [{"payment_id": rest.id, "amount": "50.00"}, {"invoice_id": schluss.id, "amount": "1000.00"}]}
    response = client.post(url, json=body)
    assert response.status_code == 200, response.text
    assert (response.json()["amount"], response.json()["is_refund"], response.json()["rest"]) == ("-1050.00", True, "0.00")
    assert client.post(url, json=body).status_code == 409  # Rest und Guthaben reichen nicht mehr
    assert client.post(url, json={"paid_on": HEUTE.isoformat(), "lines": []}).status_code == 422
    assert client.post(url, json={"paid_on": HEUTE.isoformat(), "lines": [{"amount": "1.00"}]}).status_code == 400
    assert client.post(url, json={"paid_on": HEUTE.isoformat(),
                                  "lines": [{"payment_id": 999999, "amount": "1.00"}]}).status_code == 404
    assert client.post("/api/customers/999999/refunds", json=body).status_code == 404
    data = client.get(f"/api/customers/{kunde}/payments").json()
    assert (data["balance"]["total"], [line["kind"] for line in data["balance"]["lines"]]) == ("190.00", ["guthaben"])


def test_field_cannot_refund_or_read_the_balances(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde, _, rest = _welt(db)
    client = router_test_client(db, payments_router, role="field")
    assert client.get("/api/payments/customer-balances").status_code == 403
    response = client.post(f"/api/customers/{kunde}/refunds", json={"paid_on": HEUTE.isoformat(),
                                                                     "lines": [{"payment_id": rest.id, "amount": "50.00"}]})
    assert response.status_code == 403
    assert payment_rest(db, rest) == D("50.00")


def test_finanzen_and_dashboard_show_the_customers_balance():
    finanzen = (TEMPLATES / "finanzen.html").read_text(encoding="utf-8")
    dashboard = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    for name, text in (("finanzen", finanzen), ("dashboard", dashboard)):
        assert "api('/api/payments/customer-balances')" in text and "Guthaben der Kunden" in text, name
        assert "api('/api/payments/unallocated')" not in text, name
    customer = (TEMPLATES / "customer.html").read_text(encoding="utf-8")
    assert "Guthaben des Kunden" in customer and "/refunds`" in customer and "bookCustomerRefund" in customer


# ---------------------------------------------------------------------------
# PostgreSQL: gleichzeitig
# ---------------------------------------------------------------------------

def _pg_welt(s, order_id):
    """Abschlag 10 m² (595 €) bezahlt, Schlussrechnung 8 m² (−119 €, Guthaben 119 €), Zahlung über 50 € ohne Zuordnung."""
    order = s.get(Order, order_id)
    abschlag = _abschlag(s, order, "10")
    kunde = invoice_customer_id(abschlag)
    _zahlen(s, kunde, "595", abschlag)
    schluss = create_schlussrechnung(s, s.get(Order, order_id))
    update_invoice_item(s, schluss, schluss.items[0], ist_quantity=D("8"))
    mit_zeitraum(s, schluss)
    schluss = finalize_and_send_invoice(s, s.get(Invoice, schluss.id))
    return kunde, schluss.id, _zahlen(s, kunde, "50").id


def test_pg_two_refunds_from_the_same_rest_never_exceed_it(pg):
    Session, order_id = pg
    kunde, _, rest_id = _vorbereiten(Session, lambda s: _pg_welt(s, order_id))

    def erstatten(s):
        return book_customer_refund(s, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("30"), payment_id=rest_id)]).id

    _, second = _run(Session, erstatten, erstatten)
    assert isinstance(second, PaymentRejected) and "20,00" in str(second), second
    assert _vorbereiten(Session, lambda s: payment_rest(s, s.get(Payment, rest_id))) == D("20.00")


def test_pg_allocating_the_rest_waits_for_a_refund_from_it_and_is_refused(pg):
    Session, order_id = pg

    def offen(s):  # Abschlag 10 m² (595 €), davon 585 € bezahlt; Zahlung über 50 € ohne Zuordnung
        abschlag = _abschlag(s, s.get(Order, order_id), "10")
        kunde = invoice_customer_id(abschlag)
        _zahlen(s, kunde, "585", abschlag)
        return kunde, abschlag.id, _zahlen(s, kunde, "50").id

    kunde, abschlag_id, rest_id = _vorbereiten(Session, offen)

    def erstatten(s):
        return book_customer_refund(s, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("50"), payment_id=rest_id)]).id

    def zuordnen(s):
        return allocate_rest(s, s.get(Payment, rest_id), [Line(abschlag_id, zahlung=D("10"))]).id

    _, second = _run(Session, erstatten, zuordnen)
    assert isinstance(second, PaymentRejected) and "Überbuchung der Zahlung" in str(second), second


def test_pg_reversing_the_source_waits_for_the_refund_and_is_refused(pg):
    Session, order_id = pg
    kunde, _, rest_id = _vorbereiten(Session, lambda s: _pg_welt(s, order_id))

    def erstatten(s):
        return book_customer_refund(s, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("50"), payment_id=rest_id)]).id

    def zuruecknehmen(s):
        return reverse_payment(s, s.get(Payment, rest_id), reason="falsch erfasst").id

    _, second = _run(Session, erstatten, zuruecknehmen)
    assert isinstance(second, PaymentRejected) and "erst den Zahlungsausgang zurücknehmen" in str(second), second


def test_pg_customer_refund_waits_for_the_storno_of_the_final_invoice_and_is_refused(pg):
    Session, order_id = pg
    kunde, schluss_id, rest_id = _vorbereiten(Session, lambda s: _pg_welt(s, order_id))
    storno_id = _vorbereiten(Session, lambda s: create_storno_draft(s, s.get(Invoice, schluss_id)).id)

    def storno(s):
        return finalize_and_send_invoice(s, s.get(Invoice, storno_id)).invoice_number

    def erstatten(s):
        return book_customer_refund(s, kunde, paid_on=HEUTE, note=None,
                                    lines=[RefundLine(D("50"), payment_id=rest_id), RefundLine(D("119"), invoice_id=schluss_id)])

    _, second = _run(Session, storno, erstatten)
    assert isinstance(second, PaymentRejected) and "ist keine" in str(second), second
    assert _vorbereiten(Session, lambda s: s.scalar(select(Payment).where(Payment.amount < 0))) is None
    assert _vorbereiten(Session, lambda s: payment_rest(s, s.get(Payment, rest_id))) == D("50.00")
