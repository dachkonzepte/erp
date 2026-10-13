"""Zahlungseingänge (seit 1.8.78): gleichzeitiges Buchen gegen PostgreSQL und Rundgang über die schreibenden Endpunkte.

Gegen die lokale PostgreSQL (ERP_TEST_POSTGRES_URL, opt-in, sonst übersprungen): die erste Aktion hält ihre Sperren eine
Sekunde (Commit angehalten), die zweite startet währenddessen, wartet und findet danach den Stand der ersten vor
(tests/test_v375_rechnungen_sperren.py::_run()):
  - zwei Buchungen auf dieselbe Rechnung -> die zweite wäre eine Überbuchung (abgelehnt, ihre Zahlung nicht angelegt);
  - zwei Zuordnungen aus dem Rest derselben Zahlung auf Rechnungen verschiedener Aufträge -> die zweite wartet an der Zahlung;
  - Buchung gegen Storno, Storno gegen Buchung, zweimal dieselbe Gegenbuchung.
Unter SQLite (immer): jeder schreibende Endpunkt der Zahlungen schreibt Zuordnungen nur unter der Sperre des Auftrags ihrer
Rechnung und, bei einer vorhandenen Zahlung, unter deren Sperre -- in fester Reihenfolge (Aufträge aufsteigend, dann Zahlung);
dazu die Router-Antworten (404/409/422, "erfasst von" aus der Anmeldung). Seit 1.8.93 auch die Erstattung aus dem Rest einer
Zahlung (PaymentRefundSource): nur unter der Sperre dieser Zahlung."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.berlin_time import berlin_today
from app.database import Base
from app.grunddaten import anlegen
from app.invoices import (
    InvoiceBlocked, create_abschlag_pauschal, create_schlussrechnung, create_storno_draft, finalize_and_send_invoice,
)
from app.models import Invoice, Order, Payment, PaymentAllocation, PaymentRefundSource, Project, Quote, QuoteItem
from app.payments import Line, PaymentRejected, allocate_rest, book_payment, invoice_customer_id, reverse_allocation
from app.project_pipeline_columns import default_pipeline_column_id
from app.projects import load_quote
from app.routers.payments import router as payments_router
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

D = Decimal
HEUTE = berlin_today()


def _order(s, order_id):
    return s.get(Order, order_id)


def _pauschal(s, order_id, net="1000"):
    """Festgeschriebener pauschaler Abschlag: net netto, brutto × 1,19 (1000 -> 1.190,00)."""
    return festschreiben(s, create_abschlag_pauschal(s, _order(s, order_id), lump_sum_net=D(net))).id


def _zweiter_auftrag(s, order_id, number="0002"):
    """Weiterer Auftrag desselben Kunden (eigenes Projekt und Angebot)."""
    customer_id = _order(s, order_id).project.customer_id
    project = Project(project_number=f"P-{number}", name="Halle", customer_id=customer_id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(s))
    s.add(project)
    s.flush()
    quote = Quote(quote_number=f"A-{number}", project_id=project.id, title="Halle", vat_rate=D("19"))
    s.add(quote)
    s.flush()
    s.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=D("10"), unit="m2",
                    unit_price=D("50")))
    s.commit()
    return beauftragen(s, load_quote(s, quote.id)).id


def _buchen(s, invoice_id, amount, **line):
    invoice = s.get(Invoice, invoice_id)
    return book_payment(s, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D(amount), note=None,
                        lines=[Line(invoice_id, **{k: D(v) for k, v in (line or {"zahlung": amount}).items()})])


def _zaehlen(Session, model, *where):
    return _vorbereiten(Session, lambda s: s.scalar(select(func.count()).select_from(model).where(*where)))


# ---------------------------------------------------------------------------
# Gleichzeitig gegen PostgreSQL
# ---------------------------------------------------------------------------

def test_pg_two_bookings_on_the_same_invoice_at_once_overbook_nothing(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _pauschal(s, order_id))
    _, second = _run(Session, lambda s: _buchen(s, invoice_id, "1000").id, lambda s: _buchen(s, invoice_id, "500"))
    assert isinstance(second, PaymentRejected) and "Überbuchung der Rechnung" in str(second) and "190,00 €" in str(second), second
    assert _zaehlen(Session, Payment) == 1 and _zaehlen(Session, PaymentAllocation) == 1


def test_pg_two_allocations_from_the_same_payment_rest_wait_at_the_payment(pg):
    Session, order_id = pg
    a = _vorbereiten(Session, lambda s: _pauschal(s, order_id))
    other_order = _vorbereiten(Session, lambda s: _zweiter_auftrag(s, order_id))
    b = _vorbereiten(Session, lambda s: _pauschal(s, other_order))
    payment_id = _vorbereiten(Session, lambda s: book_payment(
        s, customer_id=invoice_customer_id(s.get(Invoice, a)), received_on=HEUTE, amount=D("1000"), note=None, lines=[]).id)
    _, second = _run(Session, lambda s: allocate_rest(s, s.get(Payment, payment_id), [Line(a, zahlung=D("800"))]).id,
                     lambda s: allocate_rest(s, s.get(Payment, payment_id), [Line(b, zahlung=D("800"))]))
    assert isinstance(second, PaymentRejected) and "Überbuchung der Zahlung" in str(second), second
    assert _zaehlen(Session, PaymentAllocation) == 1


def test_pg_booking_waits_for_the_storno_and_is_rejected(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _pauschal(s, order_id))
    storno_id = _vorbereiten(Session, lambda s: create_storno_draft(s, s.get(Invoice, invoice_id)).id)
    _, second = _run(Session, lambda s: festschreiben(s, s.get(Invoice, storno_id)).id,
                     lambda s: _buchen(s, invoice_id, "100"))
    assert isinstance(second, PaymentRejected) and "storniert und nicht bebuchbar" in str(second), second
    assert _zaehlen(Session, Payment) == 0


def test_pg_storno_waits_for_the_booking_and_is_rejected(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _pauschal(s, order_id))
    storno_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_storno_draft(s, s.get(Invoice, invoice_id))).id)
    _, second = _run(Session, lambda s: _buchen(s, invoice_id, "100").id,
                     lambda s: festschreiben(s, s.get(Invoice, storno_id)))
    assert isinstance(second, InvoiceBlocked) and "Zahlungen zugeordnet" in str(second), second
    assert _vorbereiten(Session, lambda s: (s.get(Invoice, invoice_id).status, s.get(Invoice, storno_id).status)) == (
        "versendet", "entwurf")


def test_pg_the_same_reversal_twice_at_once_happens_once(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _pauschal(s, order_id))
    allocation_id = _vorbereiten(Session, lambda s: (_buchen(s, invoice_id, "100"),
                                                     s.scalar(select(PaymentAllocation.id)))[1])
    _, second = _run(Session, lambda s: reverse_allocation(s, s.get(PaymentAllocation, allocation_id), reason="a").id,
                     lambda s: reverse_allocation(s, s.get(PaymentAllocation, allocation_id), reason="b"))
    assert isinstance(second, PaymentRejected) and "schon gegengebucht" in str(second), second
    assert _zaehlen(Session, PaymentAllocation, PaymentAllocation.reverses_allocation_id.is_not(None)) == 1


# ---------------------------------------------------------------------------
# Rundgang (SQLite): jeder schreibende Endpunkt schreibt unter den Sperren, in fester Reihenfolge
# ---------------------------------------------------------------------------

class SperrBeobachter:
    """Merkt sich jede Abfrage "SELECT … FOR UPDATE" auf orders bzw. payments (Reihenfolge und IDs) und hält jede neue
    Zuordnung dagegen: der Auftrag ihrer Rechnung muss gesperrt sein, bei einer schon vorhandenen Zahlung auch diese. Seit 1.8.93
    ebenso jede neue Erstattung aus dem Rest einer Zahlung: die Zahlung, aus deren Rest erstattet wird, muss gesperrt sein. Auch
    unter SQLite sichtbar -- dort wird FOR UPDATE nur nicht gesendet."""

    def __init__(self, session):
        self.session = session
        self.sperren: list[tuple[str, int]] = []
        self.verstoesse: list[str] = []
        self.zuordnungen = 0
        self.neue_zahlungen: set[int] = set()  # in dieser Transaktion angelegt -- brauchen keine Sperre

    def __enter__(self):
        event.listen(self.session, "do_orm_execute", self._ausfuehren)
        event.listen(self.session, "before_flush", self._schreiben)
        event.listen(self.session, "after_flush", self._angelegt)
        for name in ("after_commit", "after_rollback", "after_soft_rollback"):
            event.listen(self.session, name, self._ende)
        return self

    def __exit__(self, *exc):
        event.remove(self.session, "do_orm_execute", self._ausfuehren)
        event.remove(self.session, "before_flush", self._schreiben)
        event.remove(self.session, "after_flush", self._angelegt)
        for name in ("after_commit", "after_rollback", "after_soft_rollback"):
            event.remove(self.session, name, self._ende)

    def _ausfuehren(self, state):
        stmt = state.statement
        if getattr(stmt, "_for_update_arg", None) is None:
            return
        tables = {getattr(t, "name", None) for t in stmt.get_final_froms()}
        for table in ("orders", "payments"):
            if table in tables:
                params = stmt.compile().params.values()
                ids = sorted({i for v in params for i in (v if isinstance(v, (list, tuple)) else [v]) if isinstance(i, int)})
                self.sperren.extend((table, i) for i in ids)

    def _ende(self, session, *args):
        self.sperren.clear()
        self.neue_zahlungen.clear()

    def _angelegt(self, session, context):
        self.neue_zahlungen |= {o.id for o in session.new if isinstance(o, Payment)}

    def _schreiben(self, session, context, instances):
        with session.no_autoflush:
            neue_zahlungen = self.neue_zahlungen | {o.id for o in session.new if isinstance(o, Payment)}
            for o in session.new:
                if isinstance(o, PaymentRefundSource):  # seit 1.8.93
                    self.zuordnungen += 1
                    if ("payments", o.source_payment_id) not in self.sperren:
                        self.verstoesse.append(f"Erstattung aus dem Rest ohne Sperre der Zahlung {o.source_payment_id}")
                    continue
                if not isinstance(o, PaymentAllocation):
                    continue
                self.zuordnungen += 1
                order_id = session.get(Invoice, o.invoice_id).order_id
                if ("orders", order_id) not in self.sperren:
                    self.verstoesse.append(f"Zuordnung ohne Sperre des Auftrags {order_id}")
                if o.payment_id not in neue_zahlungen and ("payments", o.payment_id) not in self.sperren:
                    self.verstoesse.append(f"Zuordnung ohne Sperre der Zahlung {o.payment_id}")
            # Feste Reihenfolge: Aufträge aufsteigend, danach keine Auftragssperre mehr nach der ersten Zahlungssperre.
            orders = [i for t, i in self.sperren if t == "orders"]
            first_payment = next((k for k, (t, _) in enumerate(self.sperren) if t == "payments"), len(self.sperren))
            if orders != sorted(orders) or any(t == "orders" for t, _ in self.sperren[first_payment:]):
                self.verstoesse.append(f"Sperren nicht in fester Reihenfolge: {self.sperren}")


def _welt():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    anlegen(db)
    db.commit()
    first = beauftragen(db, make_quote(db, is_consumer=False, number="0001")).id
    second = _zweiter_auftrag(db, first)
    return db, first, second


def _szenario_buchen(c, db, a, b):
    # Zeilen absichtlich in absteigender Auftragsreihenfolge -- gesperrt wird trotzdem aufsteigend.
    return c.post("/api/payments", json={"customer_id": invoice_customer_id(db.get(Invoice, a)), "received_on": str(HEUTE),
                                         "amount": "300", "lines": [{"invoice_id": b, "zahlung": "100"},
                                                                    {"invoice_id": a, "zahlung": "100", "skonto": "5",
                                                                     "einbehalt": "10"}]})


def _szenario_rest(c, db, a, b):
    payment = book_payment(db, customer_id=invoice_customer_id(db.get(Invoice, a)), received_on=HEUTE, amount=D("300"),
                           note=None, lines=[])
    return c.post(f"/api/payments/{payment.id}/allocations", json={"lines": [{"invoice_id": b, "zahlung": "50"},
                                                                             {"invoice_id": a, "zahlung": "50"}]})


def _szenario_zahlung_zurueck(c, db, a, b):
    payment = book_payment(db, customer_id=invoice_customer_id(db.get(Invoice, a)), received_on=HEUTE, amount=D("300"),
                           note=None, lines=[Line(b, zahlung=D("100")), Line(a, zahlung=D("100"))])
    return c.post(f"/api/payments/{payment.id}/reverse", json={"reason": "nie eingegangen"})


def _szenario_zuordnung_zurueck(c, db, a, b):
    book_payment(db, customer_id=invoice_customer_id(db.get(Invoice, a)), received_on=HEUTE, amount=D("100"), note=None,
                 lines=[Line(b, zahlung=D("100"))])
    allocation = db.scalar(select(PaymentAllocation).where(PaymentAllocation.invoice_id == b))
    return c.post(f"/api/payment-allocations/{allocation.id}/reverse", json={"reason": "falsche Rechnung"})


def _szenario_erstattung(c, db, a, b):
    # Seit 1.8.90 (R4c Punkt 6): der bezahlte pauschale Abschlag (1.190 €) übersteigt den Auftrag (595 €) -- Schlussrechnung −595 €,
    # Guthaben des Kunden, davon 100 € als Zahlungsausgang erstattet.
    _buchen(db, a, "1190")
    schluss = mit_zeitraum(db, create_schlussrechnung(db, db.get(Invoice, a).order))
    finalize_and_send_invoice(db, schluss)
    return c.post(f"/api/invoices/{schluss.id}/refunds", json={"paid_on": str(HEUTE), "amount": "100.00"})


def _szenario_erstattung_kunde(c, db, a, b):
    # Seit 1.8.93 (Nacharbeit R4c Punkt 3): Guthaben des Kunden aus der Schlussrechnung des ersten Auftrags (−595 €, wie oben) und
    # dem Rest einer Zahlung -- ein Zahlungsausgang für beides.
    _buchen(db, a, "1190")
    schluss = mit_zeitraum(db, create_schlussrechnung(db, db.get(Invoice, a).order))
    finalize_and_send_invoice(db, schluss)
    customer_id = invoice_customer_id(db.get(Invoice, a))
    rest = book_payment(db, customer_id=customer_id, received_on=HEUTE, amount=D("300"), note=None, lines=[])
    return c.post(f"/api/customers/{customer_id}/refunds", json={"paid_on": str(HEUTE), "lines": [
        {"payment_id": rest.id, "amount": "50.00"}, {"invoice_id": schluss.id, "amount": "100.00"}]})


SZENARIEN = {
    ("POST", "/api/payments"): _szenario_buchen,
    ("POST", "/api/customers/{customer_id}/refunds"): _szenario_erstattung_kunde,
    ("POST", "/api/invoices/{invoice_id}/refunds"): _szenario_erstattung,
    ("POST", "/api/payments/{payment_id}/allocations"): _szenario_rest,
    ("POST", "/api/payments/{payment_id}/reverse"): _szenario_zahlung_zurueck,
    ("POST", "/api/payment-allocations/{allocation_id}/reverse"): _szenario_zuordnung_zurueck,
}


def test_every_writing_payment_route_has_a_scenario():
    routes = {(m, r.path) for r in payments_router.routes for m in r.methods if m not in ("GET", "HEAD")}
    assert routes == set(SZENARIEN)


@pytest.mark.parametrize("route", sorted(SZENARIEN), ids=lambda r: f"{r[0]} {r[1]}")
def test_every_writing_payment_route_writes_only_under_the_locks_in_fixed_order(route, router_test_client):
    db, first, second = _welt()
    try:
        a, b = _pauschal(db, first), _pauschal(db, second)
        client = router_test_client(db, payments_router, user_id=7, display_name="Büro Test")
        with SperrBeobachter(db) as beobachter:
            antwort = SZENARIEN[route](client, db, a, b)
        assert antwort.status_code == 200, antwort.text
        assert beobachter.zuordnungen >= 1 and beobachter.verstoesse == []
    finally:
        db.close()


def test_router_answers_404_409_422_and_takes_the_user_from_the_login(router_test_client):
    db, first, second = _welt()
    try:
        a = _pauschal(db, first)
        customer_id = invoice_customer_id(db.get(Invoice, a))
        client = router_test_client(db, payments_router, user_id=7, display_name="Büro Test")
        ok = client.post("/api/payments", json={"customer_id": customer_id, "received_on": str(HEUTE), "amount": "100.00",
                                                "lines": [{"invoice_id": a, "zahlung": "100"}]})
        assert ok.status_code == 200 and ok.json()["created_by_name"] == "Büro Test" and ok.json()["rest"] == "0.00"
        assert db.scalar(select(Payment.created_by_user_id)) == 7
        assert client.post("/api/payments", json={"customer_id": customer_id, "received_on": str(HEUTE), "amount": "1",
                                                  "created_by_name": "Fremd", "lines": []}).json()["created_by_name"] == "Büro Test"
        assert client.post("/api/payments", json={"customer_id": 9999, "received_on": str(HEUTE), "amount": "1",
                                                  "lines": []}).status_code == 404
        ueber = client.post("/api/payments", json={"customer_id": customer_id, "received_on": str(HEUTE), "amount": "2000",
                                                   "lines": [{"invoice_id": a, "zahlung": "2000"}]})
        assert ueber.status_code == 409 and ueber.json()["detail"].startswith("Überbuchung der Rechnung")
        for body in ({"amount": "1.001"}, {"amount": "-5"}, {"lines": [{"invoice_id": a, "zahlung": "-1"}]}):
            data = {"customer_id": customer_id, "received_on": str(HEUTE), "amount": "1", "lines": [], **body}
            assert client.post("/api/payments", json=data).status_code == 422, body
        assert client.post("/api/payments/9999/reverse", json={"reason": "x"}).status_code == 404
        assert client.post("/api/payment-allocations/9999/reverse", json={"reason": "x"}).status_code == 404
        assert client.post("/api/payments/1/reverse", json={"reason": ""}).status_code == 422
        vorschlag = client.get(f"/api/invoices/{a}/payment-proposal", params={"amount": "500", "received_on": str(HEUTE)})
        assert vorschlag.status_code == 200 and vorschlag.json()["lines"][0]["zahlung"] == "500.00"
        offen = client.get(f"/api/customers/{customer_id}/open-invoices").json()
        assert [o["payment"]["open"] for o in offen] == ["1090.00"]  # der Vorschlag bucht nichts
        assert client.get(f"/api/customers/{customer_id}/payments").json()["rest"] == "1.00"
        assert client.get("/api/payments/unallocated").json() == [
            {"customer_id": customer_id, "customer_name": "Kunde 0001", "rest": "1.00"}]
    finally:
        db.close()


def test_payment_routes_are_closed_for_the_field_role(router_test_client):
    db, first, _ = _welt()
    try:
        a = _pauschal(db, first)
        client = router_test_client(db, payments_router, role="field")
        customer_id = invoice_customer_id(db.get(Invoice, a))
        assert client.post("/api/payments", json={"customer_id": customer_id, "received_on": str(HEUTE), "amount": "1",
                                                  "lines": []}).status_code == 403
        assert client.get(f"/api/customers/{customer_id}/payments").status_code == 403
    finally:
        db.close()
