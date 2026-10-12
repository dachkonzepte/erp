"""Zahlungseingänge (seit 1.8.78, Zahlungsstufe Z1, docs/archiv/zahlungen.md).

- Beträge je Rechnung: offen = Brutto − Zahlungen − Skonto, mahnfähig = offen − Einbehalt; Zustand nur abgeleitet (offen,
  teilweise bezahlt, Einbehalt offen, bezahlt); der Status kennt kein "bezahlt" mehr.
- Vorschlag: ältere offene Rechnungen desselben Auftrags zuerst, dann die gewählte; Skonto nur in der Frist und wenn der Betrag
  passt; Einbehalt nie.
- Angriffe: Überbuchung (Rechnung und Zahlung), Rechnung eines fremden Kunden, Buchung auf Storno bzw. stornierte Rechnung --
  abgelehnt, nichts geschrieben. Unveränderlich: Korrektur nur als Gegenbuchung mit Begründung, einmal.
- Storno erst nach gelösten Zuordnungen, die Zahlung bleibt nicht zugeordnet. Finanzen, Mahnwesen (nur was Punkt 3 verlangt).

Gleichzeitigkeit gegen PostgreSQL: tests/test_v381_zahlungen_pg.py; Migration: tests/test_v381_zahlungen_migration.py."""

import ast
import itertools
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

import app.audit  # noqa: F401  (registriert die Historie an der Sitzung)
from app.berlin_time import berlin_today
from app.grunddaten import anlegen
from app.invoices import (
    InvoiceBlocked, create_abschlag_leistungsstand, create_abschlag_pauschal, create_schlussrechnung, create_storno_draft,
    invoice_overview_rows, invoice_to_dict, update_invoice_item, update_invoice_payment_term,
)
from app.models import (
    ArchiveImmutableError, AuditLog, Customer, Invoice, Order, OrderItem, Payment, PaymentAllocation, PaymentTerm, Project,
    Reminder,
)
from app.payments import (
    Line, PaymentRejected, allocate_rest, book_payment, customer_payments, open_invoices_of_customer, payment_rest,
    payment_state, proposal, reverse_allocation, reverse_payment, unallocated_by_customer,
)
from app.project_pipeline_columns import default_pipeline_column_id
from app.reminders import (
    create_reminder, finalize_and_send_reminder, list_invoices_needing_attention, reminder_to_dict, send_block_reason,
)
from app.zugehoerigkeit import IdNichtGefunden
from tests.leistungszeitraum import festschreiben
from tests.test_v133_invoices import db_session
from tests.zahlung import voll_bezahlen

APP = Path(__file__).resolve().parent.parent / "app"
D = Decimal
HEUTE = berlin_today()
_N = itertools.count(1)


def _db():
    db = db_session()
    anlegen(db)
    db.commit()
    return db


def _kunde(db, name=None):
    n = next(_N)
    customer = Customer(name=name or f"Kunde {n}", last_name=name or f"Kunde {n}")
    db.add(customer)
    db.flush()
    return customer


def _auftrag(db, customer=None, *, quantity="100", price="50"):
    n = next(_N)
    customer = customer or _kunde(db)
    project = Project(project_number=f"P-Z-{n:04d}", name="Dach", customer_id=customer.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    order = Order(order_number=f"AUF-Z-{n:04d}", project_id=project.id, source_quote_id=n, quote_number_snapshot=f"A-{n}",
                  title="Dach", vat_rate=D("19.00"), customer_name=customer.name)
    db.add(order)
    db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung", quantity=D(quantity),
                     unit="m²", unit_price=D(price)))
    db.commit()
    db.refresh(order)
    return order


def _abschlag(db, order, ist="40"):
    """Abschlag nach Leistungsstand: ist × 50 € netto, brutto × 1,19 (40 m² = 2.380,00 €)."""
    invoice = create_abschlag_leistungsstand(db, db.get(Order, order.id))
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    return festschreiben(db, invoice)


def _pauschal(db, order, net="1000"):
    return festschreiben(db, create_abschlag_pauschal(db, db.get(Order, order.id), lump_sum_net=D(net)))


def _mit_skonto(db, order, net="1000", percent="2", days=10):
    term = PaymentTerm(label=f"14 Tage, {percent} % Skonto", days=14, skonto_percent=D(percent), skonto_days=days)
    db.add(term)
    db.commit()
    invoice = create_abschlag_pauschal(db, db.get(Order, order.id), lump_sum_net=D(net))
    update_invoice_payment_term(db, invoice, term.id)
    return festschreiben(db, invoice)


def _kunde_von(invoice):
    return invoice.order.project.customer_id


def _buchen(db, invoice, amount, lines=None, **kwargs):
    lines = lines if lines is not None else [Line(invoice.id, zahlung=D(amount))]
    return book_payment(db, customer_id=_kunde_von(invoice), received_on=kwargs.pop("received_on", HEUTE), amount=D(amount),
                        note=kwargs.pop("note", None), lines=lines, user_name="Büro", **kwargs)


def _state(db, invoice):
    return payment_state(db, db.get(Invoice, invoice.id))


def _anzahl(db, model):
    return db.scalar(select(func.count()).select_from(model))


def _abgelehnt(fn, *args, **kwargs) -> str:
    with pytest.raises(PaymentRejected) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


# ---------------------------------------------------------------------------
# Beträge und Zustand
# ---------------------------------------------------------------------------

def test_open_partially_paid_paid_and_the_status_stays_finalized():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    state = _state(db, invoice)
    assert (state.gross, state.open, state.dunnable, state.state) == (D("2380.00"), D("2380.00"), D("2380.00"), "offen")
    _buchen(db, invoice, "1000", received_on=HEUTE - timedelta(days=3))
    state = _state(db, invoice)
    assert (state.paid, state.open, state.state, state.paid_on) == (D("1000.00"), D("1380.00"), "teilweise_bezahlt", None)
    _buchen(db, invoice, "1380", received_on=HEUTE - timedelta(days=1))
    state = _state(db, invoice)
    assert (state.open, state.dunnable, state.state, state.paid_on) == (D("0.00"), D("0.00"), "bezahlt", HEUTE - timedelta(days=1))
    assert db.get(Invoice, invoice.id).status == "versendet"  # kein Status "bezahlt" mehr


def test_skonto_counts_against_the_open_amount():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    _buchen(db, invoice, "2332.40", lines=[Line(invoice.id, zahlung=D("2332.40"), skonto=D("47.60"))])
    state = _state(db, invoice)
    assert (state.paid, state.skonto, state.open, state.state) == (D("2332.40"), D("47.60"), D("0.00"), "bezahlt")


def test_retention_is_not_dunnable_and_is_settled_by_a_later_payment():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    _buchen(db, invoice, "2261", lines=[Line(invoice.id, zahlung=D("2261.00"), einbehalt=D("119.00"))])
    state = _state(db, invoice)
    assert (state.open, state.retained_open, state.dunnable, state.state) == (
        D("119.00"), D("119.00"), D("0.00"), "einbehalt_offen")
    # Später gezahlt: der Einbehalt deckt höchstens den offenen Betrag -- danach ist nichts mehr offen.
    _buchen(db, invoice, "119")
    state = _state(db, invoice)
    assert (state.open, state.retained_open, state.dunnable, state.state) == (D("0.00"), D("0.00"), D("0.00"), "bezahlt")


def test_partial_retention_leaves_the_rest_dunnable():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    _buchen(db, invoice, "1000", lines=[Line(invoice.id, zahlung=D("1000"), einbehalt=D("119"))])
    state = _state(db, invoice)
    assert (state.open, state.dunnable, state.state) == (D("1380.00"), D("1261.00"), "teilweise_bezahlt")


def test_retention_higher_than_what_stays_open_is_refused():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    text = _abgelehnt(_buchen, db, invoice, "2300", lines=[Line(invoice.id, zahlung=D("2300"), einbehalt=D("81"))])
    assert "Einbehalt" in text and "80,00 €" in text
    assert _anzahl(db, Payment) == 0


def test_draft_storno_and_cancelled_invoices_have_no_payment_state():
    db = _db()
    order = _auftrag(db)
    entwurf = create_abschlag_pauschal(db, db.get(Order, order.id), lump_sum_net=D("100"))
    original = _abschlag(db, order)
    storno = festschreiben(db, create_storno_draft(db, original))
    for invoice in (entwurf, original, storno):
        invoice = db.get(Invoice, invoice.id)
        assert payment_state(db, invoice) is None, invoice.invoice_type
        data = invoice_to_dict(invoice)
        assert data["payment"] is None and data["is_overdue"] is False
    assert "Stornorechnung" in invoice_to_dict(db.get(Invoice, storno.id))["not_payable_reason"]


def test_legacy_invoice_before_1_8_11_is_payable_to_the_cent():
    """Rechnung vor 1.8.11 (rounding_rule leer): Brutto ungerundet, gebucht wird auf den Cent (halb-gerade wie das PDF)."""
    db = _db()
    order = _auftrag(db, price="10.0042")  # 40 m² × 10,0042 = 400,168 netto, brutto 476,19992
    invoice = create_abschlag_leistungsstand(db, db.get(Order, order.id))
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D("40"))
    invoice = festschreiben(db, invoice)
    invoice.rounding_rule = None
    db.commit()
    assert _state(db, invoice).gross == D("476.20")
    _buchen(db, invoice, "476.20")
    assert _state(db, invoice).state == "bezahlt"


# ---------------------------------------------------------------------------
# Vorschlag
# ---------------------------------------------------------------------------

def test_proposal_takes_older_open_invoices_of_the_same_order_first():
    db = _db()
    customer = _kunde(db)
    order = _auftrag(db, customer)
    erste = _pauschal(db, order, "100")     # 119,00
    zweite = _pauschal(db, order, "200")    # 238,00
    gewaehlt = _pauschal(db, order, "300")  # 357,00
    neuere = _pauschal(db, order, "400")    # nicht vorgeschlagen (neuer)
    fremd = _pauschal(db, _auftrag(db, customer), "50")  # anderer Auftrag: nur von Hand
    voll_bezahlen(db, zweite)
    result = proposal(db, db.get(Invoice, gewaehlt.id), amount=D("300"), received_on=HEUTE)
    assert [(l["invoice_id"], l["zahlung"]) for l in result["lines"]] == [(erste.id, D("119.00")), (gewaehlt.id, D("181.00"))]
    assert result["rest"] == D("0.00")
    assert neuere.id not in [l["invoice_id"] for l in result["lines"]] and fremd.id not in [
        l["invoice_id"] for l in result["lines"]]
    assert all(l["einbehalt"] == 0 and l["skonto"] == 0 for l in result["lines"])
    # Mehr als offen: alles voll, der Rest bleibt am Kunden.
    result = proposal(db, db.get(Invoice, gewaehlt.id), amount=D("500"), received_on=HEUTE)
    assert [l["zahlung"] for l in result["lines"]] == [D("119.00"), D("357.00")] and result["rest"] == D("24.00")


def test_proposal_offers_skonto_only_in_period_and_when_the_amount_fits():
    db = _db()
    invoice = _mit_skonto(db, _auftrag(db))  # 1.190,00 brutto, 2 % = 23,80, Frist bis Rechnungsdatum + 10
    passt = proposal(db, invoice, amount=D("1166.20"), received_on=HEUTE)
    line = passt["lines"][0]
    assert (line["zahlung"], line["skonto"], line["skonto_offer"]["in_period"]) == (D("1166.20"), D("23.80"), True)
    zu_spaet = proposal(db, invoice, amount=D("1166.20"), received_on=HEUTE + timedelta(days=11))
    assert (zu_spaet["lines"][0]["zahlung"], zu_spaet["lines"][0]["skonto"]) == (D("1166.20"), D("0.00"))
    assert zu_spaet["lines"][0]["skonto_offer"]["in_period"] is False
    passt_nicht = proposal(db, invoice, amount=D("1100"), received_on=HEUTE)
    assert (passt_nicht["lines"][0]["zahlung"], passt_nicht["lines"][0]["skonto"]) == (D("1100"), D("0.00"))
    voll = proposal(db, invoice, amount=D("1190"), received_on=HEUTE)
    assert (voll["lines"][0]["zahlung"], voll["lines"][0]["skonto"]) == (D("1190.00"), D("0.00"))


def test_proposal_with_skonto_on_several_invoices_when_the_sum_fits():
    db = _db()
    order = _auftrag(db)
    a = _mit_skonto(db, order, "1000")  # 1.190,00 / 23,80
    b = _mit_skonto(db, order, "500")   # 595,00 / 11,90
    result = proposal(db, db.get(Invoice, b.id), amount=D("1749.30"), received_on=HEUTE)
    assert [(l["invoice_id"], l["zahlung"], l["skonto"]) for l in result["lines"]] == [
        (a.id, D("1166.20"), D("23.80")), (b.id, D("583.10"), D("11.90"))]


def test_proposal_for_a_storno_or_draft_is_refused():
    db = _db()
    order = _auftrag(db)
    original = _abschlag(db, order)
    storno = festschreiben(db, create_storno_draft(db, original))
    assert "Stornorechnung" in _abgelehnt(proposal, db, db.get(Invoice, storno.id), amount=D("10"), received_on=HEUTE)
    entwurf = create_abschlag_pauschal(db, db.get(Order, order.id), lump_sum_net=D("10"))
    assert "entwurf" in _abgelehnt(proposal, db, entwurf, amount=D("10"), received_on=HEUTE)


# ---------------------------------------------------------------------------
# Buchen: Angriffe -- abgelehnt, nichts geschrieben
# ---------------------------------------------------------------------------

def test_attack_overbooking_an_invoice_is_refused_and_writes_nothing():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    text = _abgelehnt(_buchen, db, invoice, "2380.01")
    assert "Überbuchung der Rechnung" in text and "2.380,00 €" in text
    _buchen(db, invoice, "2000")
    text = _abgelehnt(_buchen, db, invoice, "400", lines=[Line(invoice.id, zahlung=D("380.01"), skonto=D("0"))])
    assert "offen sind 380,00 €" in text
    # auch über Skonto
    _abgelehnt(_buchen, db, invoice, "300", lines=[Line(invoice.id, zahlung=D("300"), skonto=D("80.01"))])
    assert (_anzahl(db, Payment), _anzahl(db, PaymentAllocation)) == (1, 1)
    assert _state(db, invoice).open == D("380.00")


def test_attack_overbooking_the_payment_is_refused():
    db = _db()
    order = _auftrag(db)
    a, b = _pauschal(db, order, "100"), _pauschal(db, order, "100")
    text = _abgelehnt(_buchen, db, a, "200", lines=[Line(a.id, zahlung=D("119")), Line(b.id, zahlung=D("82"))])
    assert "Überbuchung der Zahlung" in text
    assert _anzahl(db, Payment) == 0
    payment = _buchen(db, a, "200", lines=[Line(a.id, zahlung=D("119"))])
    assert payment_rest(db, payment) == D("81.00")
    assert "Überbuchung der Zahlung" in _abgelehnt(allocate_rest, db, payment, [Line(b.id, zahlung=D("81.01"))])
    allocate_rest(db, payment, [Line(b.id, zahlung=D("81"))])
    assert payment_rest(db, payment) == D("0.00") and _state(db, b).open == D("38.00")


def test_attack_invoice_of_another_customer_is_refused():
    db = _db()
    eigene = _abschlag(db, _auftrag(db))
    fremde = _abschlag(db, _auftrag(db))  # anderer Kunde
    text = _abgelehnt(_buchen, db, eigene, "100", lines=[Line(fremde.id, zahlung=D("100"))])
    assert text == f"Die Rechnung {fremde.invoice_number} gehört zu einem anderen Kunden als die Zahlung."
    assert _anzahl(db, Payment) == 0
    payment = _buchen(db, eigene, "100", lines=[])  # nur Rest am Kunden
    assert "anderen Kunden" in _abgelehnt(allocate_rest, db, payment, [Line(fremde.id, zahlung=D("50"))])
    assert _anzahl(db, PaymentAllocation) == 0 and _state(db, fremde).open == D("2380.00")


def test_attack_booking_on_a_storno_or_a_cancelled_invoice_is_refused():
    db = _db()
    order = _auftrag(db)
    original = _abschlag(db, order)
    storno = festschreiben(db, create_storno_draft(db, original))
    text = _abgelehnt(_buchen, db, original, "10", lines=[Line(storno.id, zahlung=D("10"))])
    assert "Stornorechnung -- sie ist nie offen und nicht bebuchbar" in text
    text = _abgelehnt(_buchen, db, original, "10", lines=[Line(original.id, zahlung=D("10"))])
    assert "storniert und nicht bebuchbar" in text
    entwurf = create_abschlag_pauschal(db, db.get(Order, order.id), lump_sum_net=D("10"))
    assert "entwurf" in _abgelehnt(_buchen, db, original, "10", lines=[Line(entwurf.id, zahlung=D("10"))])
    assert _anzahl(db, Payment) == 0


def test_bad_input_is_refused_before_anything_is_written():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    for kwargs, text in (
        ({"amount": D("10.001")}, "zwei Nachkommastellen"),
        ({"amount": D("0")}, "größer als 0"),
        ({"received_on": HEUTE + timedelta(days=1)}, "Zukunft"),
        ({"lines": [Line(invoice.id, zahlung=D("-1"))]}, "negativ"),
        ({"lines": [Line(invoice.id, zahlung=D("5")), Line(invoice.id, zahlung=D("5"))]}, "höchstens einmal"),
        ({"lines": [Line(invoice.id)]}, "ohne Betrag"),
    ):
        args = {"customer_id": _kunde_von(invoice), "received_on": HEUTE, "amount": D("10"), "note": None,
                "lines": [Line(invoice.id, zahlung=D("10"))], **kwargs}
        with pytest.raises(ValueError, match=text):
            book_payment(db, **args)
    with pytest.raises(IdNichtGefunden):
        book_payment(db, customer_id=99999, received_on=HEUTE, amount=D("1"), note=None, lines=[])
    with pytest.raises(IdNichtGefunden):
        book_payment(db, customer_id=_kunde_von(invoice), received_on=HEUTE, amount=D("1"), note=None,
                     lines=[Line(99999, zahlung=D("1"))])
    assert _anzahl(db, Payment) == 0


def test_payment_without_allocation_stays_as_rest_at_the_customer():
    db = _db()
    order = _auftrag(db)
    invoice = _pauschal(db, order, "100")
    payment = _buchen(db, invoice, "150", lines=[Line(invoice.id, zahlung=D("119"))], note="Überweisung")
    data = customer_payments(db, _kunde_von(invoice))
    assert data["rest"] == D("31.00") and data["payments"][0]["rest"] == D("31.00")
    assert data["payments"][0]["created_by_name"] == "Büro" and data["payments"][0]["note"] == "Überweisung"
    assert [r["rest"] for r in unallocated_by_customer(db)] == [D("31.00")]
    assert open_invoices_of_customer(db, _kunde_von(invoice)) == []
    assert payment.origin == "erfasst"


# ---------------------------------------------------------------------------
# Unveränderlich: Gegenbuchung mit Begründung
# ---------------------------------------------------------------------------

def test_payments_and_allocations_cannot_be_changed_or_deleted():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    payment = _buchen(db, invoice, "100")
    allocation = db.scalar(select(PaymentAllocation))
    for obj, field, value in ((payment, "amount", D("1")), (payment, "note", "x"), (allocation, "amount", D("1")),
                              (allocation, "invoice_id", invoice.id + 1)):
        setattr(obj, field, value)
        with pytest.raises(ArchiveImmutableError):
            db.flush()
        db.rollback()
    for obj in (allocation, payment):
        db.delete(db.get(type(obj), obj.id))
        with pytest.raises(ArchiveImmutableError):
            db.flush()
        db.rollback()
    assert (_anzahl(db, Payment), _anzahl(db, PaymentAllocation)) == (1, 1)


def test_reversing_an_allocation_needs_a_reason_and_happens_once():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    payment = _buchen(db, invoice, "2380")
    allocation = db.scalar(select(PaymentAllocation))
    with pytest.raises(ValueError, match="Begründung"):
        reverse_allocation(db, allocation, reason="  ")
    counter = reverse_allocation(db, allocation, reason="falscher Kunde", user_name="Büro")
    assert (counter.amount, counter.reverses_allocation_id, counter.reason) == (D("-2380.00"), allocation.id, "falscher Kunde")
    assert _state(db, invoice).state == "offen" and payment_rest(db, payment) == D("2380.00")
    assert "schon gegengebucht" in _abgelehnt(reverse_allocation, db, allocation, reason="nochmal")
    assert "Gegenbuchung lässt sich nicht gegenbuchen" in _abgelehnt(reverse_allocation, db, counter, reason="x")
    rows = invoice_to_dict(db.get(Invoice, invoice.id))["payment_allocations"]
    assert len(rows) == 1 and rows[0]["reversed"] and rows[0]["reversal"]["reason"] == "falscher Kunde"


def test_reversing_a_payment_reverses_its_allocations_and_deductions():
    db = _db()
    order = _auftrag(db)
    a, b = _pauschal(db, order, "100"), _pauschal(db, order, "100")
    payment = _buchen(db, a, "200", lines=[Line(a.id, zahlung=D("100"), skonto=D("19")), Line(b.id, zahlung=D("50"))])
    reverse_allocation(db, db.scalar(select(PaymentAllocation).where(PaymentAllocation.invoice_id == b.id)), reason="b falsch")
    reverse_payment(db, payment, reason="nie eingegangen", user_name="Büro")
    assert _state(db, a).open == D("119.00") and _state(db, b).open == D("119.00")
    assert payment_rest(db, payment) == D("0.00")
    data = customer_payments(db, _kunde_von(a))
    assert data["rest"] == D("0.00") and data["payments"][0]["reversed"]
    assert data["payments"][0]["reversal"]["reason"] == "nie eingegangen"
    counters = list(db.scalars(select(PaymentAllocation).where(PaymentAllocation.reverses_allocation_id.is_not(None))))
    assert sorted(c.reason for c in counters) == ["b falsch", "nie eingegangen", "nie eingegangen"]
    assert "schon zurückgenommen" in _abgelehnt(reverse_payment, db, payment, reason="nochmal")
    assert "zurückgenommen" in _abgelehnt(allocate_rest, db, payment, [Line(a.id, zahlung=D("1"))])
    assert unallocated_by_customer(db) == []


def test_nobody_writes_payments_around_the_orm_lock():
    """Gebuchtes wird nie per update()/delete() geändert -- das ginge an der ORM-Sperre vorbei."""
    found = []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) in ("update", "delete")
                    and node.args and getattr(node.args[0], "id", "") in ("Payment", "PaymentAllocation")):
                found.append(f"{path.relative_to(APP)}:{node.lineno}")
    assert found == []


def test_bookings_appear_in_the_history():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    vorher = _anzahl(db, AuditLog)
    payment = _buchen(db, invoice, "100")
    reverse_payment(db, payment, reason="falsch")
    rows = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "Zahlungseingang").order_by(AuditLog.id)))
    assert _anzahl(db, AuditLog) - vorher == len(rows) == 4  # Zahlung, Zuordnung, Gegenbuchung der Zuordnung, der Zahlung
    assert {r.entity_id for r in rows} == {str(payment.id)}
    assert any("Gegenbuchung Zahlung 100,00 € an " + invoice.invoice_number in r.entity_label for r in rows)
    assert all(r.project_id == invoice.order.project_id for r in rows if "an R-" in r.entity_label)


# ---------------------------------------------------------------------------
# Storno
# ---------------------------------------------------------------------------

def test_storno_only_after_the_allocations_are_resolved_and_the_payment_stays_unallocated():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    payment = _buchen(db, invoice, "2380", lines=[Line(invoice.id, zahlung=D("2300"), einbehalt=D("80"))])
    data = invoice_to_dict(db.get(Invoice, invoice.id))
    assert data["storno_block"].startswith("Der Rechnung sind Zahlungen zugeordnet (Zahlung 2.300,00 €, Einbehalt 80,00 €).")
    with pytest.raises(InvoiceBlocked, match="Zahlungen zugeordnet"):
        create_storno_draft(db, db.get(Invoice, invoice.id))
    for allocation in list(db.scalars(select(PaymentAllocation))):
        reverse_allocation(db, allocation, reason="Rechnung wird storniert")
    storno = festschreiben(db, create_storno_draft(db, db.get(Invoice, invoice.id)))
    assert db.get(Invoice, invoice.id).status == "storniert" and storno.status == "versendet"
    assert payment_rest(db, payment) == D("2380.00")
    assert customer_payments(db, _kunde_von(invoice))["rest"] == D("2380.00")


def test_storno_draft_from_before_the_booking_cannot_be_finalized():
    db = _db()
    invoice = _abschlag(db, _auftrag(db))
    storno = create_storno_draft(db, invoice)
    _buchen(db, invoice, "100")
    with pytest.raises(InvoiceBlocked, match="Zahlungen zugeordnet"):
        festschreiben(db, db.get(Invoice, storno.id))
    assert db.get(Invoice, invoice.id).status == "versendet" and db.get(Invoice, storno.id).invoice_number is None


# ---------------------------------------------------------------------------
# Finanzen und Dashboard: offener Betrag statt Brutto, Storno nie offen
# ---------------------------------------------------------------------------

def test_overview_rows_carry_the_open_amount_and_storno_is_never_open():
    db = _db()
    order = _auftrag(db)
    teil = _abschlag(db, order, "40")       # 2.380,00, davon 1.000 bezahlt
    original = _pauschal(db, order, "100")  # storniert
    storno = festschreiben(db, create_storno_draft(db, original))
    _buchen(db, teil, "1000")
    rows = {r["id"]: r for r in invoice_overview_rows(db, list(db.scalars(select(Invoice))))}
    assert rows[teil.id]["payment"]["open"] == D("1380.00") and rows[teil.id]["payment"]["state"] == "teilweise_bezahlt"
    assert rows[storno.id]["payment"] is None and rows[original.id]["payment"] is None
    assert rows[storno.id]["gross_total"] < 0 and not rows[storno.id]["is_overdue"]


def test_overdue_only_with_a_dunnable_amount():
    db = _db()
    order = _auftrag(db)
    invoice = festschreiben(db, create_schlussrechnung(db, db.get(Order, order.id), due_date=HEUTE - timedelta(days=5)))
    assert invoice_to_dict(invoice)["is_overdue"] is True
    _buchen(db, invoice, "5800", lines=[Line(invoice.id, zahlung=D("5800"), einbehalt=D("150"))])
    data = invoice_to_dict(db.get(Invoice, invoice.id))
    assert data["payment"]["state"] == "einbehalt_offen" and data["is_overdue"] is False


# ---------------------------------------------------------------------------
# Mahnwesen: nur, was Punkt 3 verlangt
# ---------------------------------------------------------------------------

def _ueberfaellig(db, order=None):
    order = order or _auftrag(db)
    return festschreiben(db, create_schlussrechnung(db, db.get(Order, order.id), due_date=HEUTE - timedelta(days=20)))


def test_reminder_dunns_the_dunnable_amount():
    db = _db()
    invoice = _ueberfaellig(db)  # 5.950,00
    _buchen(db, invoice, "1000", lines=[Line(invoice.id, zahlung=D("1000"), einbehalt=D("297.50"))])
    row = next(r for r in list_invoices_needing_attention(db) if r["invoice_id"] == invoice.id)
    assert row["outstanding_amount"] == D("4652.50")
    reminder = create_reminder(db, db.get(Invoice, invoice.id), 1)
    assert reminder.outstanding_amount == D("4652.50")


def test_no_reminder_when_paid_or_only_the_retention_is_open():
    db = _db()
    bezahlt = _ueberfaellig(db)
    voll_bezahlen(db, bezahlt, received_on=date(2026, 10, 2))
    einbehalt = _ueberfaellig(db)
    _buchen(db, einbehalt, "5652.50", lines=[Line(einbehalt.id, zahlung=D("5652.50"), einbehalt=D("297.50"))])
    ids = [r["invoice_id"] for r in list_invoices_needing_attention(db)]
    assert bezahlt.id not in ids and einbehalt.id not in ids
    with pytest.raises(InvoiceBlocked, match=r"ist bezahlt \(am 02.10.2026\)"):
        create_reminder(db, db.get(Invoice, bezahlt.id), 1)
    with pytest.raises(InvoiceBlocked, match="nur noch der Einbehalt offen"):
        create_reminder(db, db.get(Invoice, einbehalt.id), 1)


def test_reminder_draft_with_an_outdated_amount_is_not_finalized():
    db = _db()
    invoice = _ueberfaellig(db)
    reminder = create_reminder(db, invoice, 1)
    _buchen(db, invoice, "950")
    data = reminder_to_dict(db.get(Reminder, reminder.id))
    assert data["send_block"].startswith("Der Entwurf mahnt 5.950,00 €, mahnfähig sind inzwischen 5.000,00 €")
    with pytest.raises(InvoiceBlocked, match="Entwurf löschen und neu anlegen"):
        finalize_and_send_reminder(db, db.get(Reminder, reminder.id))
    assert db.get(Reminder, reminder.id).status == "entwurf"


def test_reminder_for_a_storno_invoice_is_refused():
    db = _db()
    order = _auftrag(db)
    original = _abschlag(db, order)
    storno = festschreiben(db, create_storno_draft(db, original))
    assert "Stornorechnung" in send_block_reason(db.get(Invoice, storno.id))
    with pytest.raises(InvoiceBlocked):
        create_reminder(db, db.get(Invoice, storno.id), 1)
