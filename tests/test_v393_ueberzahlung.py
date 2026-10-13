"""Version 1.8.90 -- Überzahlung und E-Mail zur Schlussrechnung (R4c Punkte 6 und 7, docs/archiv/befund-vor-echtbetrieb.md
"Umsetzung R4c").

- Punkt 6: eine Schlussrechnung darf unter 0 € lauten. Ist der Zahlbetrag negativ, weist das PDF einen Erstattungsbetrag aus, ohne
  Skonto und ohne "zahlbar"; die Erstattung ist als Zahlungsausgang buchbar (höchstens das Guthaben, nur als Ganzes zurückzunehmen),
  das Guthaben steht am Kunden; Skonto nur bei positivem Rechnungsbetrag. Liegt der Rechnungsbetrag unter 0 €, aber der Zahlbetrag
  darüber (offene Abschläge), wird der Zahlbetrag gemahnt.
- Punkt 7: die E-Mail zur Schlussrechnung nennt den Zahlbetrag bzw. den Erstattungsbetrag laut Zahlungshinweis, auch mit einer
  eigenen Vorlage ohne den Platzhalter.

Auftrag aus tests/test_v133_invoices.py: 100 m² × 50 € = 5.000 € netto. Abschlag nach Leistungsstand 100 m² = 5.950 € brutto; die
Schlussrechnung mit dem Aufmaß 80 m² (4.760 € brutto) lautet über −1.190 € (Überzahlung). Gleichzeitigkeit gegen PostgreSQL am Ende."""

import email
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select, update

from app.berlin_time import berlin_today
from app.document_email_templates import update_email_template
from app.email_sending import update_smtp_settings
from app.final_dunning import dunning_state
from app.invoice_pdf import build_invoice_pdf
from app.invoices import (
    InvoiceBlocked, compute_invoice_totals, create_abschlag_leistungsstand, create_schlussrechnung, create_storno_draft,
    finalize_and_send_invoice, format_payment_terms_sentence, invoice_customer, invoice_to_dict, payment_note, send_invoice_email,
    skonto_offer, update_invoice_item,
)
from app.models import Invoice, Order, Payment, PaymentAllocation
from app.payments import (
    Line, PaymentRejected, book_payment, book_refund, customer_payments, invoice_customer_id, reverse_allocation, reverse_payment,
)
from app.reminders import amounts, create_reminder
from app.routers.payments import router as payments_router
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)
from tests.test_v382_mahnwesen import _pdf_text

D = Decimal
HEUTE = berlin_today()


def _abschlag(db, order, ist="100"):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return festschreiben(db, invoice)


def _zahlen(db, invoice, zahlung):
    return book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D(zahlung), note=None,
                        lines=[Line(invoice.id, zahlung=D(zahlung))], user_name="Test")


def _schluss_entwurf(db, order, ist="80", skonto=True):
    schluss = create_schlussrechnung(db, order)
    update_invoice_item(db, schluss, schluss.items[0], ist_quantity=D(ist))  # Aufmaß kleiner als abgeschlagen
    if skonto:
        db.execute(update(Invoice).where(Invoice.id == schluss.id).values(skonto_percent=D("2"), skonto_days=10))
        db.commit()
    db.refresh(schluss)
    return schluss


def _ueberzahlt(db, gezahlt="5950"):
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order)
    if D(gezahlt):
        _zahlen(db, abschlag, gezahlt)
    schluss = festschreiben(db, _schluss_entwurf(db, order))
    return order, abschlag, schluss


def _blocked(fn, *args, **kwargs) -> str:
    with pytest.raises(InvoiceBlocked) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _rejected(fn, *args, **kwargs) -> str:
    with pytest.raises(PaymentRejected) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _text(db, invoice) -> str:
    """Text des PDFs aus dem Content-Stream (Klammern dort maskiert, Umlaute als Oktal -- die Suchtexte meiden sie)."""
    return _extract_pdf_text(build_invoice_pdf(db, invoice)).decode("latin-1").replace("\\(", "(").replace("\\)", ")")


# ---------------------------------------------------------------------------
# Punkt 6: negativer Rechnungsbetrag, Erstattungsbetrag, Skonto
# ---------------------------------------------------------------------------

def test_final_invoice_below_zero_can_be_finalized_and_names_the_refund():
    db = db_session()
    order, abschlag, schluss = _ueberzahlt(db)
    assert schluss.status == "versendet" and schluss.invoice_number
    t = compute_invoice_totals(schluss)
    assert (t["net_total"], t["vat_total"], t["gross_total"]) == (D("-1000.00"), D("-190.00"), D("-1190.00"))
    note = payment_note(schluss)
    assert (note["pay_amount"], note["refund_amount"], note["lines"]) == (D("-1190.00"), D("1190.00"), [])
    assert format_payment_terms_sentence(schluss) == "Den Erstattungsbetrag von 1.190,00 € überweisen wir Ihnen."
    assert skonto_offer(schluss) is None  # Skonto nur bei positivem Rechnungsbetrag
    data = invoice_to_dict(schluss)
    assert data["payment"] is None and "Überzahlung" in data["not_payable_reason"]
    assert data["dunning"]["credit"] == D("1190.00") and data["is_overdue"] is False


def test_pdf_shows_the_refund_without_skonto_and_without_payable():
    db = db_session()
    _, _, schluss = _ueberzahlt(db)
    text = _text(db, schluss)
    for teil in ("Erstattungsbetrag (", "1.190,00", "Erstattung:", "Den Erstattungsbetrag von 1.190,00"):
        assert teil in text, teil
    for nicht in ("Zahlbar", "Skonto", "Zahlungsbedingungen:"):
        assert nicht not in text, nicht


def test_refund_draft_shows_live_and_positive_rechnungsbetrag_keeps_skonto():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order)
    _zahlen(db, abschlag, "5950")
    entwurf = _schluss_entwurf(db, order)
    assert payment_note(entwurf)["refund_amount"] == D("1190.00")  # im Entwurf heute
    update_invoice_item(db, entwurf, entwurf.items[0], ist_quantity=D("110"))  # Mehrmenge: Rechnungsbetrag positiv
    db.refresh(entwurf)
    assert compute_invoice_totals(entwurf)["gross_total"] == D("595.00")
    assert skonto_offer(entwurf) is not None and "Skonto" in format_payment_terms_sentence(entwurf)


def test_negative_rechnungsbetrag_with_open_abschlag_is_dunned_for_the_rest_without_skonto():
    db = db_session()
    order, abschlag, schluss = _ueberzahlt(db, gezahlt="4000")  # Abschlag offen 1.950
    state = dunning_state(db, schluss)
    assert (state.own_part, state.dunnable, state.credit) == (D("-1190.00"), D("760.00"), D("0.00"))
    note = payment_note(schluss)
    assert (note["pay_amount"], note["refund_amount"]) == (D("760.00"), None)
    sentence = format_payment_terms_sentence(schluss)
    assert sentence.startswith("Zahlbar rein netto bis zum") and "Skonto" not in sentence
    db.execute(update(Invoice).where(Invoice.id == schluss.id).values(due_date=HEUTE - timedelta(days=5)))
    db.commit()
    reminder = create_reminder(db, schluss)
    assert reminder.outstanding_amount == D("760.00")
    a = amounts(reminder)
    assert (a["gross"], a["dunnable"], a["principal"]) == (D("-1190.00"), D("-1190.00"), D("760.00"))
    assert [(d["invoice_number"], d["open"]) for d in a["deducted"]] == [(abschlag.invoice_number, D("1950.00"))]
    assert "berzahlung aus dieser Rechnung" in _pdf_text(db, reminder)


def test_partial_open_abschlag_reduces_the_credit():
    db = db_session()
    _, _, schluss = _ueberzahlt(db, gezahlt="5000")  # Abschlag offen 950
    assert dunning_state(db, schluss).credit == D("240.00")
    assert payment_note(schluss)["refund_amount"] == D("240.00")


# ---------------------------------------------------------------------------
# Punkt 6: Erstattung als Zahlungsausgang, Guthaben am Kunden
# ---------------------------------------------------------------------------

def test_credit_stands_at_the_customer_and_the_refund_is_booked_as_outgoing_payment():
    db = db_session()
    _, _, schluss = _ueberzahlt(db)
    customer_id = invoice_customer_id(schluss)
    data = customer_payments(db, customer_id)
    assert (data["credit_total"], [c["invoice_id"] for c in data["credits"]]) == (D("1190.00"), [schluss.id])
    refund = book_refund(db, schluss, paid_on=HEUTE, amount=D("1000"), note="Überweisung an den Kunden", user_name="Bea")
    assert (refund.amount, refund.customer_id) == (D("-1000.00"), customer_id)
    allocation = db.scalar(select(PaymentAllocation).where(PaymentAllocation.payment_id == refund.id))
    assert (allocation.kind, allocation.invoice_id, allocation.amount) == ("erstattung", schluss.id, D("-1000.00"))
    data = customer_payments(db, customer_id)
    assert data["credit_total"] == D("190.00")
    row = next(p for p in data["payments"] if p["id"] == refund.id)
    assert (row["is_refund"], row["rest"]) == (True, D("0.00"))
    assert data["rest"] == D("0.00")  # ein Zahlungsausgang ist kein nicht zugeordneter Rest
    assert "190,00" in _rejected(book_refund, db, schluss, paid_on=HEUTE, amount=D("200"), note=None)
    book_refund(db, schluss, paid_on=HEUTE, amount=D("190"), note=None)
    assert dunning_state(db, schluss).credit == D("0.00")
    assert "kein Guthaben" in _rejected(book_refund, db, schluss, paid_on=HEUTE, amount=D("1"), note=None)


def test_nothing_to_dun_on_an_overpaid_final_invoice():
    db = db_session()
    _, _, schluss = _ueberzahlt(db)
    db.execute(update(Invoice).where(Invoice.id == schluss.id).values(due_date=HEUTE - timedelta(days=5)))
    db.commit()
    reason = _blocked(create_reminder, db, schluss)
    assert reason == (f"Die Schlussrechnung {schluss.invoice_number} weist eine Überzahlung aus -- Guthaben des Kunden "
                      "1.190,00 €, nichts zu mahnen.")


def test_refund_is_refused_where_there_is_no_credit():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "40")
    schluss = festschreiben(db, create_schlussrechnung(db, order))  # positiver Zahlbetrag
    assert "kein Guthaben" in _rejected(book_refund, db, schluss, paid_on=HEUTE, amount=D("1"), note=None)
    assert "ist keine" in _rejected(book_refund, db, abschlag, paid_on=HEUTE, amount=D("1"), note=None)


def test_refund_in_the_future_is_refused_and_nothing_written():
    db = db_session()
    _, _, schluss = _ueberzahlt(db)
    with pytest.raises(ValueError) as exc:
        book_refund(db, schluss, paid_on=HEUTE + timedelta(days=1), amount=D("1"), note=None)
    assert "Zukunft" in str(exc.value)
    assert db.scalar(select(Payment).where(Payment.amount < 0)) is None


def test_refund_is_reversed_only_as_a_whole_and_blocks_the_storno_until_then():
    db = db_session()
    _, _, schluss = _ueberzahlt(db)
    refund = book_refund(db, schluss, paid_on=HEUTE, amount=D("1190"), note=None)
    allocation = db.scalar(select(PaymentAllocation).where(PaymentAllocation.payment_id == refund.id))
    assert "als Ganzes" in _rejected(reverse_allocation, db, allocation, reason="falsch")
    reason = _blocked(create_storno_draft, db, schluss)
    assert "Erstattung (Zahlungsausgang) 1.190,00 €" in reason and "Kundenakte" in reason
    reverse_payment(db, refund, reason="Überweisung kam zurück")
    assert dunning_state(db, schluss).credit == D("1190.00")
    storno = festschreiben(db, create_storno_draft(db, schluss))
    assert compute_invoice_totals(storno)["gross_total"] == D("1190.00")


def test_router_books_a_refund(threaded_db_session, router_test_client):
    db = threaded_db_session
    _, _, schluss = _ueberzahlt(db)
    client = router_test_client(db, payments_router)
    response = client.post(f"/api/invoices/{schluss.id}/refunds", json={"paid_on": HEUTE.isoformat(), "amount": "1190.00",
                                                                         "note": "an den Kunden"})
    assert response.status_code == 200, response.text
    assert (response.json()["amount"], response.json()["is_refund"]) == ("-1190.00", True)
    again = client.post(f"/api/invoices/{schluss.id}/refunds", json={"paid_on": HEUTE.isoformat(), "amount": "1.00"})
    assert again.status_code == 409
    assert client.post("/api/invoices/999999/refunds", json={"paid_on": HEUTE.isoformat(), "amount": "1.00"}).status_code == 404
    customer = client.get(f"/api/customers/{invoice_customer_id(schluss)}/payments").json()
    assert (customer["credit_total"], customer["credits"]) == ("0.00", [])


# ---------------------------------------------------------------------------
# Punkt 7: E-Mail nennt Zahl- bzw. Erstattungsbetrag
# ---------------------------------------------------------------------------

def _smtp(db):
    update_smtp_settings(db, host="smtp.example.com", port=587, username="buero@example.com", encryption="starttls",
                         sender_email="buero@example.com", sender_name="Test GmbH", password="geheim123")


def _body(mock_smtp_cls) -> str:
    raw = mock_smtp_cls.return_value.sendmail.call_args[0][2]
    message = email.message_from_string(raw) if isinstance(raw, str) else email.message_from_bytes(raw)
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
    raise AssertionError("kein Textteil")


def _senden(db, invoice, mock_smtp_cls, key):
    invoice_customer(invoice).email = "kunde@example.com"
    db.commit()
    mock_smtp_cls.return_value = MagicMock()
    send_invoice_email(db, invoice, dispatch_key=key)
    return _body(mock_smtp_cls)


@patch("app.email_sending.smtplib.SMTP")
def test_email_of_an_overpaid_final_invoice_names_the_refund(mock_smtp_cls):
    db = db_session()
    _smtp(db)
    _, _, schluss = _ueberzahlt(db)
    body = _senden(db, schluss, mock_smtp_cls, "test-erstattung-1")
    assert f"Laut Zahlungshinweis (Stand {HEUTE.strftime('%d.%m.%Y')}) ergibt sich ein Erstattungsbetrag von 1.190,00 €" in body
    paragraphs = body.strip().split("\n\n")
    assert paragraphs[-1].startswith("Mit freundlichen Grüßen") and "Erstattungsbetrag" in paragraphs[-2]


@patch("app.email_sending.smtplib.SMTP")
def test_email_of_a_final_invoice_names_the_pay_amount(mock_smtp_cls):
    db = db_session()
    _smtp(db)
    order, _ = make_order_with_item(db)
    _abschlag(db, order, "40")  # 2.380 offen
    schluss = festschreiben(db, create_schlussrechnung(db, order))  # 3.570
    body = _senden(db, schluss, mock_smtp_cls, "test-zahlbetrag-1")
    assert "beträgt der Zahlbetrag 5.950,00 €." in body


@patch("app.email_sending.smtplib.SMTP")
def test_custom_template_with_placeholder_gets_no_extra_paragraph_and_other_invoices_stay(mock_smtp_cls):
    db = db_session()
    _smtp(db)
    update_email_template(db, "invoice", subject_template="Rechnung {rechnungsnummer}",
                          body_template="Hallo,\n\nzu zahlen: {zahlbetrag}{erstattungsbetrag}.\n\nGruß")
    _, _, schluss = _ueberzahlt(db)
    body = _senden(db, schluss, mock_smtp_cls, "test-vorlage-1")
    assert body == "Hallo,\n\nzu zahlen: 1.190,00 €.\n\nGruß"  # Erstattung: {zahlbetrag} leer, {erstattungsbetrag} der Betrag
    db = db_session()  # zweiter Auftrag: eigene Datenbank (Projektnummer der Testhelfer fest)
    _smtp(db)
    update_email_template(db, "invoice", subject_template="Rechnung {rechnungsnummer}",
                          body_template="Hallo,\n\nanbei {rechnungsnummer} über {gesamtbetrag}.\n\nGruß")
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "40")
    body = _senden(db, abschlag, mock_smtp_cls, "test-vorlage-2")
    assert body == f"Hallo,\n\nanbei {abschlag.invoice_number} über 2.380,00 €.\n\nGruß"  # keine Endrechnung: unverändert


# ---------------------------------------------------------------------------
# PostgreSQL: gleichzeitig
# ---------------------------------------------------------------------------

def _pg_ueberzahlt(s, order_id):
    """Abschlag nach Leistungsstand 10 m² (595 €) bezahlt, Schlussrechnung mit 8 m² (476 €): Überzahlung 119 €."""
    order = s.get(Order, order_id)
    abschlag = _abschlag(s, order, "10")
    _zahlen(s, abschlag, "595")
    schluss = create_schlussrechnung(s, s.get(Order, order_id))
    update_invoice_item(s, schluss, schluss.items[0], ist_quantity=D("8"))
    mit_zeitraum(s, schluss)
    return finalize_and_send_invoice(s, s.get(Invoice, schluss.id)).id


def test_pg_two_refunds_at_once_never_exceed_the_credit(pg):
    Session, order_id = pg
    schluss_id = _vorbereiten(Session, lambda s: _pg_ueberzahlt(s, order_id))

    def erstatten(s):
        return book_refund(s, s.get(Invoice, schluss_id), paid_on=HEUTE, amount=D("100"), note=None).id

    _, second = _run(Session, erstatten, erstatten)
    assert isinstance(second, PaymentRejected) and "19,00" in str(second), second
    assert _vorbereiten(Session, lambda s: dunning_state(s, s.get(Invoice, schluss_id)).credit) == D("19.00")


def test_pg_refund_waits_for_the_storno_of_the_final_invoice_and_is_refused(pg):
    Session, order_id = pg
    schluss_id = _vorbereiten(Session, lambda s: _pg_ueberzahlt(s, order_id))
    storno_id = _vorbereiten(Session, lambda s: create_storno_draft(s, s.get(Invoice, schluss_id)).id)

    def storno(s):
        invoice = s.get(Invoice, storno_id)
        return finalize_and_send_invoice(s, invoice).invoice_number

    _, second = _run(Session, storno, lambda s: book_refund(s, s.get(Invoice, schluss_id), paid_on=HEUTE, amount=D("119"),
                                                            note=None))
    assert isinstance(second, PaymentRejected) and "keine" in str(second), second
    assert _vorbereiten(Session, lambda s: s.scalar(select(Payment).where(Payment.amount < 0))) is None
