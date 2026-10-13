"""Version 1.8.89 -- Mahnen nach der Endrechnung (R4c Punkte 3-5, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung R4c").

- Punkt 3: nach der gültigen Schlussrechnung steht eine abgezogene Rechnung nicht mehr einzeln in "zur Mahnung fällig" und lässt sich
  nicht einzeln mahnen (kein Entwurf, ein offener ist überholt, eine festgeschriebene Mahnung geht weder per E-Mail noch als
  nachgetragene Zustellung ab dem Tag der Endrechnung hinaus); nach ihrem Storno wieder.
- Punkt 4: der Einbehalt einer abgezogenen Rechnung wird mit der Schlussrechnung fällig -- er gehört zum angemahnten Zahlbetrag.
- Punkt 5: die Mahnung der Schlussrechnung lautet über den Zahlbetrag: ihr mahnfähiger Betrag plus die offenen Beträge der
  abgezogenen Rechnungen, in der Aufstellung (Format 4) und im PDF je Rechnung mit Nummer; auch, wenn die Schlussrechnung selbst
  bezahlt ist oder über 0 € lautet; Verzugszinsen auf den angemahnten Betrag.

Auftrag aus tests/test_v133_invoices.py: 100 m² × 50 € = 5.000 € netto, 5.950 € brutto. Abschlag nach Leistungsstand 40 m² = 2.380 €
brutto, Schlussrechnung (Endrechnung) Rechnungsbetrag 3.570 €. Gleichzeitigkeit gegen PostgreSQL am Ende (opt-in)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, update

from app.berlin_time import berlin_today
from app.default_interest import interest_proposal
from app.final_dunning import dunning_state
from app.invoices import (
    InvoiceBlocked, create_abschlag_leistungsstand, create_abschlag_pauschal, create_schlussrechnung, create_storno_draft,
    finalize_and_send_invoice, invoice_customer, invoice_overview_rows, invoice_to_dict, update_invoice_item,
)
from app.models import BaseInterestRate, Invoice, InvoiceDefaultStart, InvoiceDeduction, Order, PaymentAllocation, Reminder
from app.payments import Line, book_payment, invoice_customer_id, reverse_allocation
from app.reminders import (
    amounts, check_delivery, compute_reminder_status, create_reminder, delete_reminder_draft, finalize_and_send_reminder,
    list_invoices_needing_attention, reminder_to_dict, send_reminder_email,
)
from app.routers.reminders import router as reminders_router
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v382_mahnwesen import _pdf_text
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

D = Decimal
HEUTE = berlin_today()


def _faellig(db, invoice, tage=10):
    db.execute(update(Invoice).where(Invoice.id == invoice.id).values(due_date=HEUTE - timedelta(days=tage)))
    db.commit()
    db.refresh(invoice)
    return invoice


def _abschlag(db, order, ist="40", tage=20):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return _faellig(db, festschreiben(db, invoice), tage)


def _schluss(db, order, tage=10):
    return _faellig(db, festschreiben(db, create_schlussrechnung(db, order)), tage)


def _zahlen(db, invoice, zahlung, einbehalt="0", received_on=None):
    return book_payment(db, customer_id=invoice_customer_id(invoice), received_on=received_on or HEUTE, amount=D(zahlung),
                        note=None, lines=[Line(invoice.id, zahlung=D(zahlung), einbehalt=D(einbehalt))], user_name="Test")


def _welt(db):
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order)
    return order, abschlag


def _blocked(fn, *args, **kwargs) -> str:
    with pytest.raises(InvoiceBlocked) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _zeilen(db):
    return {row["invoice_id"]: row for row in list_invoices_needing_attention(db)}


def _anzahl(db, model):
    return db.scalar(select(func.count()).select_from(model))


# ---------------------------------------------------------------------------
# Punkt 3: abgezogene Rechnungen nicht mehr einzeln
# ---------------------------------------------------------------------------

def test_deducted_invoice_leaves_the_due_list_and_the_final_invoice_carries_its_open_amount():
    db = db_session()
    order, abschlag = _welt(db)
    assert _zeilen(db)[abschlag.id]["outstanding_amount"] == D("2380.00")  # vorher: einzeln fällig
    schluss = _schluss(db, order)
    rows = _zeilen(db)
    assert abschlag.id not in rows
    assert rows[schluss.id]["outstanding_amount"] == D("5950.00")  # 3.570 + noch offen aus dem Abschlag 2.380
    assert rows[schluss.id]["due_for_reminder"] is True
    assert [d["invoice_id"] for d in rows[schluss.id]["dunning"]["deducted"]] == [abschlag.id]


def test_no_new_reminder_for_a_deducted_invoice():
    db = db_session()
    order, abschlag = _welt(db)
    schluss = _schluss(db, order)
    vorher = _anzahl(db, Reminder)
    reason = _blocked(create_reminder, db, abschlag)
    assert reason == (f"Die Rechnung {abschlag.invoice_number} ist in der Schlussrechnung {schluss.invoice_number} abgezogen – gemahnt "
                      "wird nur noch die Schlussrechnung (über den Zahlbetrag).")
    assert _anzahl(db, Reminder) == vorher
    status = compute_reminder_status(db, abschlag)
    assert (status["create_block"], status["is_due_now"], status["next_level"]) == (reason, False, None)
    assert status["dunning"]["settled_in"]["invoice_number"] == schluss.invoice_number


def test_open_draft_of_a_deducted_invoice_is_outdated_and_can_only_be_deleted():
    db = db_session()
    order, abschlag = _welt(db)
    draft = create_reminder(db, abschlag)
    schluss = _schluss(db, order)
    reason = reminder_to_dict(draft)["send_block"]
    assert reason.startswith("Der Entwurf (1. Mahnung) ist überholt: ") and schluss.invoice_number in reason
    assert reason.endswith("Bitte den Entwurf löschen.")
    assert _blocked(finalize_and_send_reminder, db, draft) == reason
    db.refresh(draft)
    assert (draft.status, draft.reminder_number) == ("entwurf", None)
    delete_reminder_draft(db, draft)
    assert db.get(Reminder, draft.id) is None


def test_finalized_reminder_of_a_deducted_invoice_does_not_go_out(monkeypatch):
    db = db_session()
    order, abschlag = _welt(db)
    invoice_customer(abschlag).email = "kunde@example.com"
    db.commit()
    reminder = create_reminder(db, abschlag)
    finalize_and_send_reminder(db, reminder)  # festgeschrieben, nie hinausgegangen
    schluss = _schluss(db, order)
    sent = []
    monkeypatch.setattr("app.email_dispatch.send_message", lambda *a, **k: sent.append(1))
    reason = _blocked(send_reminder_email, db, reminder, dispatch_key="test-mahnung-abgezogen")
    assert schluss.invoice_number in reason and reason.endswith(f"Die Mahnung {reminder.reminder_number} geht nicht mehr hinaus.")
    assert sent == []
    # Eine Zustellung ab dem Tag der Endrechnung ist eine neue Mahnung -- abgelehnt; davor ging sie wirklich hinaus.
    assert "geht nicht mehr hinaus" in _blocked(check_delivery, db, reminder, HEUTE)


def test_delivery_before_the_final_invoice_can_still_be_recorded():
    db = db_session()
    order, abschlag = _welt(db)
    reminder = create_reminder(db, abschlag)
    finalize_and_send_reminder(db, reminder)
    db.execute(update(Reminder).where(Reminder.id == reminder.id).values(reminder_date=HEUTE - timedelta(days=8),
                                                                          new_due_date=HEUTE - timedelta(days=1)))
    db.commit()
    schluss = _schluss(db, order)
    db.execute(update(Invoice).where(Invoice.id == schluss.id).values(invoice_date=HEUTE - timedelta(days=2)))
    db.commit()
    check_delivery(db, reminder, HEUTE - timedelta(days=5))  # vor der Endrechnung zugestellt: geht
    db.rollback()
    assert "geht nicht mehr hinaus" in _blocked(check_delivery, db, reminder, HEUTE - timedelta(days=2))


def test_after_the_storno_of_the_final_invoice_the_deducted_invoice_is_dunned_again():
    db = db_session()
    order, abschlag = _welt(db)
    schluss = _schluss(db, order)
    assert abschlag.id not in _zeilen(db)
    festschreiben(db, create_storno_draft(db, schluss))
    assert _zeilen(db)[abschlag.id]["outstanding_amount"] == D("2380.00")
    assert create_reminder(db, abschlag).outstanding_amount == D("2380.00")


def test_final_invoice_from_before_1_8_85_without_deductions_keeps_the_rule_per_invoice():
    """Altbestand: eine Schlussrechnung ohne Abzüge (Rest über die Menge) zieht nichts ab -- der Abschlag bleibt einzeln mahnbar."""
    db = db_session()
    order, abschlag = _welt(db)
    schluss = _schluss(db, order)
    db.execute(delete(InvoiceDeduction).where(InvoiceDeduction.invoice_id == schluss.id))  # an der ORM-Sperre vorbei
    db.commit()
    db.expire_all()
    assert _zeilen(db)[abschlag.id]["outstanding_amount"] == D("2380.00")
    assert dunning_state(db, schluss).deducted == ()


def test_deducted_invoice_page_shows_the_hint_and_is_never_overdue():
    db = db_session()
    order, abschlag = _welt(db)
    _zahlen(db, abschlag, "2000", einbehalt="380")
    schluss = _schluss(db, order)
    _zahlen(db, schluss, "3570")  # Schlussrechnung selbst bezahlt, der Einbehalt am Abschlag ist offen
    data = invoice_to_dict(abschlag)
    assert data["is_overdue"] is False
    assert data["dunning_hint"].startswith(f"In der Schlussrechnung {schluss.invoice_number} vom ")
    assert "Der Einbehalt (380,00 €) ist mit der Schlussrechnung fällig." in data["dunning_hint"]
    final = invoice_to_dict(schluss)
    assert (final["payment"]["state"], final["is_overdue"]) == ("bezahlt", True)  # Zahlbetrag offen: der Einbehalt
    rows = {r["id"]: r for r in invoice_overview_rows(db, [abschlag, schluss])}
    assert (rows[abschlag.id]["is_overdue"], rows[schluss.id]["is_overdue"]) == (False, True)


# ---------------------------------------------------------------------------
# Punkt 4: Einbehalt mit der Schlussrechnung fällig
# ---------------------------------------------------------------------------

def test_retention_of_a_deducted_invoice_becomes_due_with_the_final_invoice():
    db = db_session()
    order, abschlag = _welt(db)
    _zahlen(db, abschlag, "2000", einbehalt="380")
    assert abschlag.id not in _zeilen(db)  # vorher: nur noch Einbehalt offen, nicht gemahnt
    schluss = _schluss(db, order)
    state = dunning_state(db, schluss)
    assert [(d.invoice.id, d.open, d.retained) for d in state.deducted] == [(abschlag.id, D("380.00"), D("380.00"))]
    assert state.dunnable == D("3950.00")  # 3.570 + Einbehalt 380
    reminder = create_reminder(db, schluss)
    assert reminder.outstanding_amount == D("3950.00")


def test_own_retention_of_the_final_invoice_is_still_not_dunned():
    db = db_session()
    order, abschlag = _welt(db)
    schluss = _schluss(db, order)
    _zahlen(db, abschlag, "2380")
    _zahlen(db, schluss, "3070", einbehalt="500")  # eigener Einbehalt der Schlussrechnung (z. B. Gewährleistung)
    assert dunning_state(db, schluss).dunnable == D("0.00")
    reason = _blocked(create_reminder, db, schluss)
    assert reason == (f"Vom Zahlbetrag der Schlussrechnung {schluss.invoice_number} ist nur noch ihr Einbehalt offen (500,00 €) -- "
                      "ein Einbehalt wird nicht gemahnt.")


# ---------------------------------------------------------------------------
# Punkt 5: Mahnung der Schlussrechnung über den Zahlbetrag
# ---------------------------------------------------------------------------

def test_reminder_of_the_final_invoice_lists_each_deducted_invoice_with_number():
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = _faellig(db, festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("1000"))), 30)  # 1.190
    abschlag = _abschlag(db, order, "40")  # 2.380, davon 1.000 gezahlt
    _zahlen(db, abschlag, "1000")
    schluss = _schluss(db, order)  # Gesamtleistung 5.950 − 1.190 − 2.380 = 2.380
    _zahlen(db, schluss, "380")
    reminder = create_reminder(db, schluss)
    assert reminder.outstanding_amount == D("4570.00")  # 2.000 + 1.190 + 1.380
    a = amounts(reminder)
    assert (a["format"], a["gross"], [p["amount"] for p in a["payments"]], a["dunnable"]) == (4, D("2380.00"), [D("380.00")],
                                                                                              D("2000.00"))
    assert [(d["invoice_number"], d["open"], d["retained"]) for d in a["deducted"]] == [
        (pauschal.invoice_number, D("1190.00"), D("0.00")), (abschlag.invoice_number, D("1380.00"), D("0.00"))]
    assert (a["principal"], a["total"]) == (D("4570.00"), D("4570.00"))
    finalize_and_send_reminder(db, reminder)
    a = amounts(reminder)
    assert (a["format"], a["principal"], len(a["deducted"])) == (4, D("4570.00"), 2)
    text = _pdf_text(db, reminder)
    for teil in ("aus dieser Rechnung", f"Abschlag Nr. {pauschal.invoice_number}", f"Abschlag Nr. {abschlag.invoice_number}",
                 "Angemahnter Betrag (Zahlbetrag)", "4.570,00"):
        assert teil in text, teil


def test_final_invoice_paid_itself_is_dunned_for_the_open_abschlag():
    db = db_session()
    order, abschlag = _welt(db)
    schluss = _schluss(db, order)
    _zahlen(db, schluss, "3570")
    row = _zeilen(db)[schluss.id]
    assert (row["outstanding_amount"], row["due_for_reminder"]) == (D("2380.00"), True)
    reminder = create_reminder(db, schluss)
    finalize_and_send_reminder(db, reminder)
    assert reminder.reminder_number and reminder.outstanding_amount == D("2380.00")
    assert reminder_to_dict(reminder)["send_block"] is None  # geht hinaus, obwohl die Schlussrechnung selbst bezahlt ist


def test_final_invoice_over_zero_is_dunned_for_the_deducted_invoices():
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = _faellig(db, festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("5000"))), 30)
    schluss = _schluss(db, order)  # Rechnungsbetrag 0 €
    assert invoice_to_dict(schluss)["payment"] is None  # selbst nie offen
    reminder = create_reminder(db, schluss)
    assert reminder.outstanding_amount == D("5950.00")
    a = amounts(reminder)
    assert (a["gross"], a["payments"], a["dunnable"], [d["invoice_number"] for d in a["deducted"]]) == (
        D("0.00"), [], D("0.00"), [pauschal.invoice_number])


def test_payment_on_a_deducted_invoice_changes_the_amount_of_the_final_reminder():
    db = db_session()
    order, abschlag = _welt(db)
    schluss = _schluss(db, order)
    draft = create_reminder(db, schluss)
    _zahlen(db, abschlag, "1000")
    reason = reminder_to_dict(draft)["send_block"]
    assert "mahnfähig sind inzwischen 4.950,00 €" in reason
    delete_reminder_draft(db, draft)
    reminder = create_reminder(db, schluss)
    finalize_and_send_reminder(db, reminder)
    _zahlen(db, abschlag, "500")
    assert "mahnfähig sind inzwischen 4.450,00 €" in reminder_to_dict(reminder)["send_block"]


def test_nothing_to_dun_once_the_pay_amount_is_settled():
    db = db_session()
    order, abschlag = _welt(db)
    schluss = _schluss(db, order)
    _zahlen(db, abschlag, "2380")
    _zahlen(db, schluss, "3570")
    assert schluss.id not in _zeilen(db)
    assert _blocked(create_reminder, db, schluss) == (f"Der Zahlbetrag der Schlussrechnung {schluss.invoice_number} ist beglichen -- "
                                                      "nichts zu mahnen.")


def test_reversed_payment_on_the_deducted_invoice_makes_the_final_dunnable_again():
    db = db_session()
    order, abschlag = _welt(db)
    schluss = _schluss(db, order)
    payment = _zahlen(db, abschlag, "2380")
    _zahlen(db, schluss, "3570")
    assert schluss.id not in _zeilen(db)
    allocation = db.scalar(select(PaymentAllocation).where(PaymentAllocation.payment_id == payment.id))
    reverse_allocation(db, allocation, reason="falsch zugeordnet")
    assert _zeilen(db)[schluss.id]["outstanding_amount"] == D("2380.00")


def test_router_refuses_a_reminder_for_a_deducted_invoice(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, abschlag = _welt(db)
    _schluss(db, order)
    client = router_test_client(db, reminders_router)
    response = client.post(f"/api/invoices/{abschlag.id}/reminders", json={})
    assert response.status_code == 409 and "abgezogen" in response.json()["detail"]
    status = client.get(f"/api/invoices/{abschlag.id}/reminder-status").json()
    assert status["dunning"]["settled_in"] is not None and status["create_block"].startswith("Die Rechnung")


# ---------------------------------------------------------------------------
# Verzugszinsen auf den angemahnten Betrag
# ---------------------------------------------------------------------------

def _saetze(db):
    from app.default_interest import half_year_of, next_half_year
    hy, last = half_year_of(HEUTE - timedelta(days=400)), half_year_of(HEUTE)
    while hy <= last:
        db.add(BaseInterestRate(half_year_start=hy, rate_percent=D("1.27"), reviewed_on=HEUTE, reviewed_by="Test-Kanzlei"))
        hy = next_half_year(hy)
    db.commit()


def test_interest_of_the_final_invoice_runs_on_the_pay_amount_and_cuts_at_payments_on_deducted_invoices():
    db = db_session()
    order, abschlag = _welt(db)
    schluss = _schluss(db, order, tage=30)
    _saetze(db)
    start = HEUTE - timedelta(days=20)
    db.add(InvoiceDefaultStart(invoice_id=schluss.id, starts_on=start, basis="von_hand", created_by_name="Test"))
    db.commit()
    _zahlen(db, abschlag, "1000", received_on=HEUTE - timedelta(days=10))
    proposal = interest_proposal(db, schluss, until=HEUTE)
    assert proposal["block"] is None
    principals = [s["principal"] for s in proposal["sections"]]
    assert principals[0] == D("5950.00") and principals[-1] == D("4950.00")  # Zahlung auf den Abschlag: neuer Abschnitt
    assert any(s["from"] == HEUTE - timedelta(days=10) for s in proposal["sections"])


# ---------------------------------------------------------------------------
# PostgreSQL: gleichzeitig
# ---------------------------------------------------------------------------

def _pg_welt(s, order_id):
    """Pauschaler Abschlag 100 € netto (119 €), überfällig; Auftrag 10 m² × 50 € = 595 € brutto."""
    abschlag = festschreiben(s, create_abschlag_pauschal(s, s.get(Order, order_id), lump_sum_net=D("100")))
    _faellig(s, abschlag, 20)
    return abschlag.id


def _pg_schluss(s, order_id):
    invoice = festschreiben(s, create_schlussrechnung(s, s.get(Order, order_id)))
    _faellig(s, invoice, 10)
    return invoice.id


def _pg_finalize(schluss_id):
    """Festschreiben der Schlussrechnung (Leistungszeitraum vorher eingetragen, siehe _pg_entwurf())."""
    def finalize(s):
        return finalize_and_send_invoice(s, s.get(Invoice, schluss_id)).invoice_number
    return finalize


def _pg_entwurf(s, order_id):
    invoice = create_schlussrechnung(s, s.get(Order, order_id))
    mit_zeitraum(s, invoice)
    return invoice.id


def test_pg_create_reminder_waits_for_finalizing_the_final_invoice(pg):
    Session, order_id = pg
    abschlag_id = _vorbereiten(Session, lambda s: _pg_welt(s, order_id))
    schluss_id = _vorbereiten(Session, lambda s: _pg_entwurf(s, order_id))
    nummer, second = _run(Session, _pg_finalize(schluss_id), lambda s: create_reminder(s, s.get(Invoice, abschlag_id)))
    assert isinstance(second, InvoiceBlocked) and f"in der Schlussrechnung {nummer} abgezogen" in str(second), second
    assert _vorbereiten(Session, lambda s: s.scalar(select(func.count()).select_from(Reminder))) == 0


def test_pg_finalizing_a_draft_of_the_abschlag_waits_and_is_outdated(pg):
    Session, order_id = pg
    abschlag_id = _vorbereiten(Session, lambda s: _pg_welt(s, order_id))
    draft_id = _vorbereiten(Session, lambda s: create_reminder(s, s.get(Invoice, abschlag_id)).id)
    schluss_id = _vorbereiten(Session, lambda s: _pg_entwurf(s, order_id))
    _, second = _run(Session, _pg_finalize(schluss_id), lambda s: finalize_and_send_reminder(s, s.get(Reminder, draft_id)))
    assert isinstance(second, InvoiceBlocked) and "ist überholt" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(Reminder, draft_id).status) == "entwurf"


def test_pg_reminder_of_the_final_invoice_waits_for_a_payment_on_the_abschlag(pg):
    Session, order_id = pg
    abschlag_id = _vorbereiten(Session, lambda s: _pg_welt(s, order_id))
    schluss_id = _vorbereiten(Session, lambda s: _pg_schluss(s, order_id))

    def zahlen(s):
        invoice = s.get(Invoice, abschlag_id)
        return book_payment(s, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D("100"), note=None,
                            lines=[Line(abschlag_id, zahlung=D("100"))]).id

    _, second = _run(Session, zahlen, lambda s: create_reminder(s, s.get(Invoice, schluss_id)).outstanding_amount)
    assert second == D("495.00"), second  # 476 + noch offen aus dem Abschlag 19 (119 − 100)


def test_pg_delivery_of_the_abschlag_reminder_waits_for_the_final_invoice_and_is_refused(pg):
    Session, order_id = pg
    abschlag_id = _vorbereiten(Session, lambda s: _pg_welt(s, order_id))

    def mahnung(s):
        reminder = create_reminder(s, s.get(Invoice, abschlag_id))
        return finalize_and_send_reminder(s, reminder).id

    reminder_id = _vorbereiten(Session, mahnung)
    schluss_id = _vorbereiten(Session, lambda s: _pg_entwurf(s, order_id))
    _, second = _run(Session, _pg_finalize(schluss_id), lambda s: check_delivery(s, s.get(Reminder, reminder_id), HEUTE))
    assert isinstance(second, InvoiceBlocked) and "geht nicht mehr hinaus" in str(second), second
