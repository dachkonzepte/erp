"""Mahnwesen Z2a (seit 1.8.79, docs/archiv/zahlungen.md "Umsetzung 1.8.79") und "Vorweg": die Rechnung hält ihren Kunden fest.

- Vorweg: Invoice.customer_id ab dem Festschreiben (Storno: der der stornierten Rechnung); Zahlungen, offene Rechnungen des Kunden
  und die Empfängeradresse folgen ihm; Kundenwechsel am Projekt gesperrt (409 mit Grund), sobald eine Rechnung festgeschrieben ist.
- Nr. 1: keine Entwürfe von selbst; "zur Mahnung fällig" liest nur; Entwürfe per Klick, einzeln oder für mehrere.
- Nr. 2 (Angriffe, je nichts geschrieben): Stornorechnung, stornierte, nicht fällige, nicht mahnfähige Rechnung, eine andere als die
  nächste Stufe, die nächste vor Ablauf der Frist der vorigen, ein zweiter Entwurf -- beim Anlegen und beim Festschreiben.
- Nr. 3: Bearbeiten/Löschen unter derselben Sperre; Mahndatum = Tag des Festschreibens, Frist ab dann.
- Nr. 4: Aufstellung Brutto, Zahlungen, Skonto, Einbehalt, mahnfähig an der Mahnung und im PDF.
- Nr. 5: E-Mail und nachgetragene Zustellung einer festgeschriebenen Mahnung nur mit passendem Betrag und nicht storniert.
- Nr. 6: Dashboard-Zeilen "Mahnung" auch bei gewähltem Mitarbeiter.
- Struktur: jeder schreibende Endpunkt des Mahnwesens schreibt Mahnungen nur unter der Sperre der Auftragszeile.

Gleichzeitigkeit gegen PostgreSQL: tests/test_v382_mahnwesen_pg.py."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, delete, event, func, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.berlin_time import berlin_today
from app.database import Base
from app.email_dispatch import record_manual_delivery
from app.grunddaten import anlegen
from app.invoices import (
    InvoiceBlocked, create_storno_draft, get_invoice_recipient_email, invoice_customer, invoice_to_dict,
)
from app.email_sending import update_smtp_settings
from app.models import Customer, EmailDispatch, Invoice, Order, Payment, Project, Reminder, ReminderLevel, SentDocument
from app.payments import Line, PaymentRejected, book_payment, invoice_customer_id, open_invoices_of_customer, reverse_payment
from app.project_participants import ClientChangeConflict, check_client_change
from app.reminder_pdf import build_reminder_pdf
from app.reminders import (
    amounts, create_reminder, create_reminders, delete_reminder_draft, finalize_and_send_reminder,
    list_invoices_needing_attention, reminder_to_dict, send_reminder_email, update_reminder_draft,
)
from app.routers.email_dispatches import router as dispatch_router
from app.routers.projects import router as projects_router
from app.routers.reminders import router as reminders_router
from tests.leistungszeitraum import festschreiben
from tests.mahnung import festschreiben_und_ablaufen, frist_ablaufen, zustellen
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.zahlung import voll_bezahlen

ROOT = Path(__file__).resolve().parent.parent
D = Decimal
HEUTE = berlin_today()


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    anlegen(db)
    db.commit()
    return db


def _rechnung(db, suffix="0001", days_overdue=16, email="kunde@example.com"):
    """Festgeschriebene Schlussrechnung über 5.950,00 € (5000 netto), überfällig seit days_overdue Tagen."""
    invoice = make_sent_overdue_invoice(db, days_overdue=days_overdue, suffix=suffix)
    invoice_customer(invoice).email = email
    db.commit()
    return invoice


def _zahlen(db, invoice, amount, *, received_on=None, skonto="0", einbehalt="0"):
    return book_payment(db, customer_id=invoice_customer_id(invoice), received_on=received_on or HEUTE, amount=D(amount),
                        note=None, lines=[Line(invoice.id, zahlung=D(amount), skonto=D(skonto), einbehalt=D(einbehalt))])


def _anzahl(db, model, *where):
    return db.scalar(select(func.count()).select_from(model).where(*where))


def _pdf_text(db, reminder) -> str:
    """Text der Mahnung aus dem Content-Stream (Klammern sind dort maskiert, Umlaute als Oktal -- die Suchtexte meiden sie)."""
    return _extract_pdf_text(build_reminder_pdf(db, reminder)).decode("latin-1").replace("\\(", "(").replace("\\)", ")")


def _geblockt(fn, *args, grund, **kwargs):
    with pytest.raises(InvoiceBlocked) as exc:
        fn(*args, **kwargs)
    assert grund in str(exc.value), str(exc.value)
    return str(exc.value)


# ---------------------------------------------------------------------------
# Vorweg: die Rechnung hält ihren Kunden fest
# ---------------------------------------------------------------------------

def test_invoice_holds_its_customer_from_finalizing_on_and_the_storno_takes_the_originals():
    db = _db()
    invoice = _rechnung(db)
    customer_id = db.get(Order, invoice.order_id).project.customer_id
    assert invoice.customer_id == customer_id
    storno = create_storno_draft(db, invoice)
    assert storno.customer_id is None  # Entwurf: noch keiner festgehalten
    other = Customer(name="Anderer", last_name="Anderer")
    db.add(other)
    db.flush()
    db.get(Order, invoice.order_id).project.customer_id = other.id  # am Wechsel vorbei, wie ein Altbestand
    db.commit()
    festschreiben(db, storno)
    assert storno.customer_id == customer_id  # der Kunde der stornierten Rechnung, nicht der heutige des Projekts


def test_payments_recipient_and_open_invoices_follow_the_held_customer():
    db = _db()
    invoice = _rechnung(db)
    old = invoice_customer(invoice)
    new = Customer(name="Neu", last_name="Neu", email="neu@example.com")
    db.add(new)
    db.flush()
    db.get(Order, invoice.order_id).project.customer_id = new.id  # am Wechsel vorbei
    db.commit()
    db.refresh(invoice)
    assert invoice_customer_id(invoice) == old.id and get_invoice_recipient_email(invoice) == "kunde@example.com"
    assert invoice_to_dict(invoice)["customer_id"] == old.id
    assert [r["invoice_id"] for r in open_invoices_of_customer(db, old.id)] == [invoice.id]
    assert open_invoices_of_customer(db, new.id) == []
    with pytest.raises(PaymentRejected, match="anderen Kunden"):
        book_payment(db, customer_id=new.id, received_on=HEUTE, amount=D("100"), note=None, lines=[Line(invoice.id, zahlung=D("100"))])
    assert _anzahl(db, Payment) == 0
    _zahlen(db, invoice, "100")  # beim festgehaltenen Kunden geht es


def test_client_change_is_refused_once_an_invoice_is_finalized_also_after_the_storno():
    db = _db()
    invoice = _rechnung(db)
    project = db.get(Order, invoice.order_id).project
    other = Customer(name="Anderer", last_name="Anderer")
    db.add(other)
    db.commit()
    with pytest.raises(ClientChangeConflict) as exc:
        check_client_change(db, project, other.id)
    assert invoice.invoice_number in str(exc.value) and "nicht mehr wechseln" in str(exc.value)
    db.rollback()
    festschreiben(db, create_storno_draft(db, invoice))
    with pytest.raises(ClientChangeConflict):
        check_client_change(db, project, other.id)


def test_client_change_with_drafts_only_is_allowed(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice = _rechnung(db)
    client = router_test_client(db, projects_router)
    project = db.get(Order, invoice.order_id).project
    other = Customer(name="Anderer", last_name="Anderer")
    db.add(other)
    db.commit()
    payload = {"customer_id": other.id, "property_id": None, "name": project.name, "status": project.status}
    response = client.put(f"/api/projects/{project.id}", json=payload)
    assert response.status_code == 409 and "festgeschrieben" in response.json()["detail"], response.text
    db.expire_all()
    assert db.get(Project, project.id).customer_id != other.id
    # Ein Projekt nur mit einem Entwurf: Wechsel geht.
    second = _rechnung(db, suffix="0002")
    order2 = db.get(Order, second.order_id)
    # Am zweiten Projekt nur ein Entwurf (die festgeschriebene Rechnung direkt zurück auf Entwurf gesetzt).
    db.execute(update(Invoice).where(Invoice.id == second.id).values(status="entwurf", invoice_number=None, customer_id=None))
    db.commit()
    # Seit 1.8.80 (Z2b "Vorweg" 1): mit Auftrag nur zusammen mit dessen Vertragspartner und mit Begründung.
    response = client.put(f"/api/projects/{order2.project_id}",
                          json={**payload, "name": "P2", "customer_change_reason": "falscher Kunde angelegt"})
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Nr. 1: keine Entwürfe von selbst, Entwürfe per Klick einzeln oder für mehrere
# ---------------------------------------------------------------------------

def test_bulk_creates_drafts_for_the_due_and_names_the_rejected_with_reason():
    db = _db()
    due_a, due_b = _rechnung(db, "0001"), _rechnung(db, "0002")
    not_due = _rechnung(db, "0003", days_overdue=0)
    paid = _rechnung(db, "0004")
    voll_bezahlen(db, paid)
    result = create_reminders(db, [due_a.id, not_due.id, due_b.id, paid.id, 999999, due_a.id])
    assert sorted(r.invoice_id for r in result["created"]) == sorted([due_a.id, due_b.id])
    assert all(r.status == "entwurf" and r.level == 1 for r in result["created"])
    rejected = {r["invoice_id"]: r["reason"] for r in result["rejected"]}
    assert set(rejected) == {not_due.id, paid.id, 999999}
    assert "erst am" in rejected[not_due.id] and "ist bezahlt" in rejected[paid.id]
    assert rejected[999999] == "Rechnung nicht gefunden."
    assert _anzahl(db, Reminder) == 2


def test_bulk_route_answers_with_created_and_rejected(threaded_db_session, router_test_client):
    db = threaded_db_session
    a, b = _rechnung(db, "0001"), _rechnung(db, "0002", days_overdue=0)
    client = router_test_client(db, reminders_router)
    body = client.post("/api/reminders/bulk", json={"invoice_ids": [a.id, b.id]}).json()
    assert [r["invoice_id"] for r in body["created"]] == [a.id]
    assert [r["invoice_id"] for r in body["rejected"]] == [b.id]
    assert client.post("/api/reminders/bulk", json={"invoice_ids": []}).status_code == 422
    assert client.post("/api/reminders/auto-create").status_code in (404, 405)


def test_overdue_list_reads_only_and_marks_what_is_due():
    db = _db()
    due = _rechnung(db, "0001")
    waiting = _rechnung(db, "0002")
    zustellen(db, finalize_and_send_reminder(db, create_reminder(db, waiting)))  # Frist der 1. Mahnung läuft noch
    db.refresh(waiting)
    before = _anzahl(db, Reminder)
    rows = {r["invoice_id"]: r for r in list_invoices_needing_attention(db)}
    assert _anzahl(db, Reminder) == before
    assert rows[due.id]["is_due_now"] and rows[due.id]["create_block"] is None
    assert not rows[waiting.id]["is_due_now"] and "erst ab dem" in rows[waiting.id]["create_block"]
    assert list(rows)[0] == due.id  # zur Mahnung fällig zuerst


# ---------------------------------------------------------------------------
# Nr. 2: Prüfungen beim Anlegen und Festschreiben (Angriffe, je nichts geschrieben)
# ---------------------------------------------------------------------------

def test_no_reminder_for_a_storno_invoice_or_a_cancelled_one():
    db = _db()
    invoice = _rechnung(db)
    storno = festschreiben(db, create_storno_draft(db, invoice))
    db.refresh(invoice)
    _geblockt(create_reminder, db, storno, grund="Stornorechnung")
    _geblockt(create_reminder, db, invoice, grund="storniert")
    assert _anzahl(db, Reminder) == 0


def test_no_reminder_before_the_day_after_the_due_date():
    db = _db()
    invoice = _rechnung(db, days_overdue=0)  # heute fällig
    _geblockt(create_reminder, db, invoice, grund=f"ist erst am {HEUTE:%d.%m.%Y} fällig")
    assert _anzahl(db, Reminder) == 0
    invoice.due_date = HEUTE - timedelta(days=1)
    db.commit()
    assert create_reminder(db, invoice).level == 1


def test_no_reminder_without_a_dunnable_amount():
    db = _db()
    paid, retained = _rechnung(db, "0001"), _rechnung(db, "0002")
    voll_bezahlen(db, paid)
    _zahlen(db, retained, "5000", einbehalt="950")
    _geblockt(create_reminder, db, paid, grund="ist bezahlt")
    _geblockt(create_reminder, db, retained, grund="nur noch der Einbehalt offen")
    assert _anzahl(db, Reminder) == 0


def test_only_the_next_level_and_only_one_draft():
    db = _db()
    invoice = _rechnung(db)
    _geblockt(create_reminder, db, invoice, 2, grund="Nur die nächste Stufe ist möglich: 1. Mahnung")
    first = create_reminder(db, invoice, 1)
    _geblockt(create_reminder, db, invoice, 1, grund="schon ein Mahnungsentwurf (1. Mahnung)")
    _geblockt(create_reminder, db, invoice, grund="schon ein Mahnungsentwurf")
    festschreiben_und_ablaufen(db, first)
    _geblockt(create_reminder, db, invoice, 1, grund="Nur die nächste Stufe ist möglich: 2. Mahnung")
    _geblockt(create_reminder, db, invoice, 3, grund="Nur die nächste Stufe ist möglich: 2. Mahnung")
    assert _anzahl(db, Reminder) == 1
    assert create_reminder(db, invoice, 2).level == 2


def test_next_level_only_after_the_previous_deadline_has_passed():
    db = _db()
    invoice = _rechnung(db)
    first = finalize_and_send_reminder(db, create_reminder(db, invoice))
    zustellen(db, first)  # seit 1.8.80: erreicht erst mit Versand oder Zustellung
    db.refresh(invoice)
    ende = first.new_due_date
    assert ende == HEUTE + timedelta(days=7)
    _geblockt(create_reminder, db, invoice, grund=f"erst ab dem {ende + timedelta(days=1):%d.%m.%Y} möglich")
    frist_ablaufen(db, first, tage_her=0)  # Frist endet heute -> noch nicht
    db.refresh(invoice)
    _geblockt(create_reminder, db, invoice, grund="läuft bis zum")
    frist_ablaufen(db, first, tage_her=1)  # endete gestern -> jetzt
    db.refresh(invoice)
    assert create_reminder(db, invoice).level == 2


def test_inactive_level_is_skipped():
    db = _db()
    db.execute(update(ReminderLevel).where(ReminderLevel.level == 2).values(active=False))
    db.commit()
    invoice = _rechnung(db)
    festschreiben_und_ablaufen(db, create_reminder(db, invoice))
    assert create_reminder(db, invoice).level == 3


def test_finalizing_rechecks_level_and_deadline_for_old_drafts():
    """Altbestand (bis 1.8.78): zwei Entwürfe derselben Stufe, ein Entwurf der 2. Stufe vor Ablauf der Frist -- beim
    Festschreiben unter der Sperre noch einmal geprüft."""
    db = _db()
    invoice = _rechnung(db)
    a = create_reminder(db, invoice)
    b = Reminder(invoice_id=invoice.id, level=1, status="entwurf", reminder_date=HEUTE, new_due_date=HEUTE + timedelta(days=7),
                 outstanding_amount=a.outstanding_amount, fee_amount=D("5"), text="x")
    db.add(b)
    db.commit()
    finalize_and_send_reminder(db, a)
    zustellen(db, a)  # seit 1.8.80: ging a nie hinaus, ersetzte b sie beim Festschreiben (tests/test_v383_nebenforderungen.py)
    _geblockt(finalize_and_send_reminder, db, b, grund="ist überholt")
    db.refresh(b)
    assert (b.status, b.reminder_number) == ("entwurf", None)
    db.delete(b)
    c = Reminder(invoice_id=invoice.id, level=2, status="entwurf", reminder_date=HEUTE, new_due_date=HEUTE + timedelta(days=7),
                 outstanding_amount=a.outstanding_amount, fee_amount=D("10"), text="x")
    db.add(c)
    db.commit()
    _geblockt(finalize_and_send_reminder, db, c, grund="erst ab dem")
    db.refresh(c)
    assert c.status == "entwurf"


def test_create_route_answers_409_with_the_reason(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice = _rechnung(db, days_overdue=0)
    client = router_test_client(db, reminders_router)
    response = client.post(f"/api/invoices/{invoice.id}/reminders", json={})
    assert response.status_code == 409 and "fällig" in response.json()["detail"]
    status = client.get(f"/api/invoices/{invoice.id}/reminder-status").json()
    assert status["create_block"] == response.json()["detail"]


# ---------------------------------------------------------------------------
# Nr. 3: Bearbeiten und Löschen unter der Sperre; Mahndatum = Tag des Festschreibens
# ---------------------------------------------------------------------------

def test_finalizing_sets_today_and_moves_the_deadline_with_it():
    db = _db()
    invoice = _rechnung(db)
    draft = create_reminder(db, invoice)
    update_reminder_draft(db, draft, text=draft.text, payment_days=10)
    # Der Entwurf ist drei Wochen alt.
    db.execute(update(Reminder).where(Reminder.id == draft.id).values(
        reminder_date=HEUTE - timedelta(days=21), new_due_date=HEUTE - timedelta(days=11)))
    db.commit()
    db.refresh(draft)
    data = reminder_to_dict(draft)
    assert (data["effective_reminder_date"], data["effective_new_due_date"], data["payment_days"]) == (
        HEUTE, HEUTE + timedelta(days=10), 10)
    assert f"{HEUTE + timedelta(days=10):%d.%m.%Y}" in data["formatted_text"]
    finalize_and_send_reminder(db, draft)
    assert (draft.reminder_date, draft.new_due_date) == (HEUTE, HEUTE + timedelta(days=10))


def test_editing_and_deleting_a_finalized_reminder_is_refused():
    db = _db()
    invoice = _rechnung(db)
    reminder = finalize_and_send_reminder(db, create_reminder(db, invoice))
    text_before = reminder.text
    _geblockt(update_reminder_draft, db, reminder, text="neu", payment_days=7, grund="festgeschrieben")
    _geblockt(delete_reminder_draft, db, reminder, grund="festgeschrieben")
    db.refresh(reminder)
    assert reminder.text == text_before and _anzahl(db, Reminder) == 1


def test_editing_a_deleted_draft_is_refused():
    db = _db()
    invoice = _rechnung(db)
    draft = create_reminder(db, invoice)
    assert draft.invoice.order_id  # geladen, wie im Router vor dem Warten auf die Sperre
    db.execute(delete(Reminder).where(Reminder.id == draft.id))  # inzwischen gelöscht
    _geblockt(update_reminder_draft, db, draft, text="neu", payment_days=7, grund="gelöscht")


def test_put_route_needs_all_fields(threaded_db_session, router_test_client):
    db = threaded_db_session
    draft = create_reminder(db, _rechnung(db))
    client = router_test_client(db, reminders_router)
    # Seit 1.8.80 ohne Gebühr (die geht über PUT /api/reminders/{id}/charges).
    for body in ({"text": "x"}, {"payment_days": 7}, {"text": "x", "payment_days": 0}):
        assert client.put(f"/api/reminders/{draft.id}", json=body).status_code == 422, body


# ---------------------------------------------------------------------------
# Nr. 4: Aufstellung des gemahnten Betrags
# ---------------------------------------------------------------------------

def test_reminder_holds_gross_payments_skonto_retention_and_dunnable():
    db = _db()
    invoice = _rechnung(db)  # 5.950,00 €
    _zahlen(db, invoice, "1000", received_on=HEUTE - timedelta(days=5))
    _zahlen(db, invoice, "500", skonto="50", einbehalt="300", received_on=HEUTE - timedelta(days=2))
    reminder = create_reminder(db, invoice)
    assert reminder.outstanding_amount == D("4100.00")  # 5950 − 1500 − 50 − 300
    a = amounts(reminder)
    assert {k: a[k] for k in ("gross", "payments", "skonto", "retained", "dunnable")} == {"gross": D("5950.00"), "payments": [
        {"received_on": HEUTE - timedelta(days=5), "amount": D("1000.00")},
        {"received_on": HEUTE - timedelta(days=2), "amount": D("500.00")}],
        "skonto": D("50.00"), "retained": D("300.00"), "dunnable": D("4100.00")}
    # Seit 1.8.80 Format 2 (mit Nebenforderungen und Gesamtbetrag; ausgeschaltet keine), seit 1.8.81 Format 3.
    assert json.loads(reminder.amounts_json)["format"] == 3
    assert (a["charges_enabled"], a["charges"], a["total"]) == (False, [], D("4100.00"))
    text = _pdf_text(db, reminder)
    for needle in ("Rechnungsbetrag (brutto)", "5.950,00 EUR", f"glich Zahlung vom {HEUTE - timedelta(days=5):%d.%m.%Y}",
                   "-1.000,00 EUR", "glich Skonto", "-50,00 EUR", "glich Einbehalt (wird nicht angemahnt)",
                   "-300,00 EUR", "Angemahnter Betrag", "4.100,00 EUR"):
        assert needle in text, needle


def test_finalizing_writes_the_breakdown_fresh_under_the_lock():
    """Gleicher Betrag, andere Zahlung: eine Zahlung zurückgenommen und am anderen Tag neu gebucht -- das Festschreiben hält die
    Aufstellung von jetzt fest."""
    db = _db()
    invoice = _rechnung(db)
    payment = _zahlen(db, invoice, "1000", received_on=HEUTE - timedelta(days=5))
    draft = create_reminder(db, invoice)
    reverse_payment(db, payment, reason="falsches Datum")
    _zahlen(db, invoice, "1000", received_on=HEUTE - timedelta(days=3))
    finalize_and_send_reminder(db, draft)
    assert [p["received_on"] for p in amounts(draft)["payments"]] == [HEUTE - timedelta(days=3)]


def test_old_reminders_without_breakdown_show_the_open_amount_as_before():
    db = _db()
    reminder = create_reminder(db, _rechnung(db))
    db.execute(update(Reminder).where(Reminder.id == reminder.id).values(amounts_json=None))
    db.commit()
    db.refresh(reminder)
    text = _pdf_text(db, reminder)
    assert "Offener Rechnungsbetrag" in text and "Rechnungsbetrag (brutto)" not in text
    assert reminder_to_dict(reminder)["amounts"] is None


# ---------------------------------------------------------------------------
# Nr. 5: Versand und Zustellung nur mit passendem Betrag, nicht storniert
# ---------------------------------------------------------------------------

def _smtp(db):
    update_smtp_settings(db, host="smtp.example.com", port=587, username="buero@example.com", encryption="starttls",
                         sender_email="buero@example.com", sender_name="Test GmbH", password="geheim123")


@patch("app.email_sending.smtplib.SMTP")
def test_email_of_a_reminder_after_a_part_payment_is_refused_and_nothing_goes_out(smtp_mock):
    db = _db()
    _smtp(db)
    invoice = _rechnung(db)
    reminder = finalize_and_send_reminder(db, create_reminder(db, invoice))
    _zahlen(db, invoice, "1000")
    reason = _geblockt(send_reminder_email, db, reminder, grund="lautet über 5.950,00 €")
    assert "mahnfähig sind inzwischen 4.950,00 €" in reason and "neue Mahnung" in reason
    assert smtp_mock.call_count == 0 and _anzahl(db, EmailDispatch) == 0
    assert reminder_to_dict(reminder)["send_block"] == reason


def _zustellen(db, reminder, delivered_on, key):
    return record_manual_delivery(db, dispatch_key=key, document_type="mahnung", document_id=reminder.id,
                                  channel="einschreiben", delivered_on=delivered_on, note="Sendung RR 123 DE")


def test_manual_delivery_counts_the_state_on_the_delivery_day():
    db = _db()
    invoice = _rechnung(db)
    reminder = finalize_and_send_reminder(db, create_reminder(db, invoice))
    # Seit 1.8.80 keine Zustellung vor dem Mahndatum -- die Mahnung ist eine Woche alt.
    frist_ablaufen(db, reminder, tage_her=0)
    _zahlen(db, invoice, "1000", received_on=HEUTE)
    # Heute zugestellt: die Zahlung von heute zählt -- abgelehnt, nichts abgelegt.
    _geblockt(_zustellen, db, reminder, HEUTE, "zustellung-heute-0001", grund="mahnfähig waren am")
    # Seit 1.8.82 liegt in der Ablage nur die feste Fassung der Rechnung vom Festschreiben.
    assert _anzahl(db, EmailDispatch) == 0 and [d.id for d in db.scalars(select(SentDocument))] == [invoice.pdf_document_id]
    # Gestern zugestellt (die Zahlung kam danach): der Betrag stimmte -- eingetragen.
    result = _zustellen(db, reminder, HEUTE - timedelta(days=1), "zustellung-gestern-0001")
    assert result.dispatch.status == "gesendet" and _anzahl(db, EmailDispatch) == 1


def test_manual_delivery_of_a_reminder_to_a_cancelled_invoice_is_refused(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice = _rechnung(db)
    reminder = finalize_and_send_reminder(db, create_reminder(db, invoice))
    festschreiben(db, create_storno_draft(db, invoice))
    client = router_test_client(db, dispatch_router)
    response = client.post("/api/email-dispatches/manual", data={
        "document_type": "mahnung", "document_id": str(reminder.id), "channel": "einschreiben",
        "delivered_on": str(HEUTE - timedelta(days=1)), "note": "Sendung RR 123 DE", "dispatch_key": "zustellung-storno-0001"})
    assert response.status_code == 409 and "storniert" in response.json()["detail"], response.text
    assert _anzahl(db, EmailDispatch) == 0


# ---------------------------------------------------------------------------
# Nr. 6: Dashboard
# ---------------------------------------------------------------------------

def test_overdue_rows_carry_the_caseworker_of_the_order_and_the_dashboard_keeps_rows_without_one():
    db = _db()
    invoice = _rechnung(db)
    db.get(Order, invoice.order_id).caseworker_employee_id = None
    db.commit()
    assert list_invoices_needing_attention(db)[0]["caseworker_employee_id"] is None
    html = (ROOT / "app" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "!empIdNum||!i.caseworker_employee_id||i.caseworker_employee_id===empIdNum" in html
    src = (ROOT / "app" / "reminders.py").read_text(encoding="utf-8")
    assert '"caseworker_employee_id": invoice.order.caseworker_employee_id' in src


# ---------------------------------------------------------------------------
# Struktur: Mahnungen schreiben nur unter der Sperre der Auftragszeile
# ---------------------------------------------------------------------------

class SperrBeobachter:
    """Merkt sich jedes "SELECT … FOR UPDATE" auf orders und hält jede neue, geänderte oder gelöschte Mahnung dagegen: der
    Auftrag ihrer Rechnung muss vorher gesperrt sein (auch unter SQLite sichtbar, dort wird FOR UPDATE nur nicht gesendet)."""

    def __init__(self, session):
        self.session = session
        self.sperren: set[int] = set()
        self.verstoesse: list[str] = []
        self.geschrieben = 0

    def __enter__(self):
        event.listen(self.session, "do_orm_execute", self._ausfuehren)
        event.listen(self.session, "before_flush", self._schreiben)
        for name in ("after_commit", "after_rollback", "after_soft_rollback"):
            event.listen(self.session, name, self._ende)
        return self

    def __exit__(self, *exc):
        event.remove(self.session, "do_orm_execute", self._ausfuehren)
        event.remove(self.session, "before_flush", self._schreiben)
        for name in ("after_commit", "after_rollback", "after_soft_rollback"):
            event.remove(self.session, name, self._ende)

    def _ausfuehren(self, state):
        stmt = state.statement
        if getattr(stmt, "_for_update_arg", None) is None:
            return
        if "orders" in {getattr(t, "name", None) for t in stmt.get_final_froms()}:
            self.sperren |= {v for v in stmt.compile().params.values() if isinstance(v, int)}

    def _ende(self, session, *args):
        self.sperren.clear()

    def _schreiben(self, session, context, instances):
        with session.no_autoflush:
            for o in list(session.new) + list(session.dirty) + list(session.deleted):
                if not isinstance(o, Reminder) or (o in session.dirty and not session.is_modified(o)):
                    continue
                self.geschrieben += 1
                order_id = session.get(Invoice, o.invoice_id).order_id
                if order_id not in self.sperren:
                    self.verstoesse.append(f"Mahnung {o.id} ohne Sperre des Auftrags {order_id}")


def _welt():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    anlegen(db)
    db.commit()
    return db


def _entwurf(db):
    return create_reminder(db, _rechnung(db, "0101"))


def _eingeschaltet(db):
    from app.models import GeneralSettings
    db.get(GeneralSettings, 1).dunning_charges_enabled = True
    db.commit()
    return _entwurf(db)


SZENARIEN = {
    ("POST", "/api/invoices/{invoice_id}/reminders"): lambda c, db: c.post(f"/api/invoices/{_rechnung(db, '0101').id}/reminders", json={}),
    ("POST", "/api/reminders/bulk"): lambda c, db: c.post("/api/reminders/bulk", json={"invoice_ids": [_rechnung(db, "0101").id]}),
    ("POST", "/api/reminders/{reminder_id}/send"): lambda c, db: c.post(f"/api/reminders/{_entwurf(db).id}/send"),
    ("PUT", "/api/reminders/{reminder_id}"): lambda c, db: c.put(f"/api/reminders/{_entwurf(db).id}", json={
        "text": "x", "payment_days": 9}),
    # seit 1.8.80: Gebühr und Pauschale im Entwurf (nur eingeschaltet)
    ("PUT", "/api/reminders/{reminder_id}/charges"): lambda c, db: c.put(f"/api/reminders/{_eingeschaltet(db).id}/charges", json={
        "fee_amount": "5.00", "fee_accepted": True, "flat_fee_accepted": False, "interest_accepted": False}),
    ("DELETE", "/api/reminders/{reminder_id}"): lambda c, db: c.delete(f"/api/reminders/{_entwurf(db).id}"),
}
# Schreiben keine Mahnung: Stufen-Einstellungen, E-Mail (protokolliert über app/email_dispatch.py, Nr. 5 prüft vorher).
OHNE_MAHNUNG = {("PUT", "/api/reminder-levels/{level_id}"), ("POST", "/api/reminders/{reminder_id}/send-email")}


def test_every_writing_reminder_route_has_a_scenario():
    routes = {(m, r.path) for r in reminders_router.routes for m in r.methods if m not in ("GET", "HEAD")}
    assert routes == set(SZENARIEN) | OHNE_MAHNUNG


@pytest.mark.parametrize("route", sorted(SZENARIEN), ids=lambda r: f"{r[0]} {r[1]}")
def test_every_writing_reminder_route_writes_only_under_the_order_lock(route, router_test_client):
    db = _welt()
    try:
        client = router_test_client(db, reminders_router)
        with SperrBeobachter(db) as beobachter:
            # Die Vorbereitung (Rechnung, Entwurf) läuft im Szenario mit -- sie legt keine Mahnung ohne Sperre an.
            antwort = SZENARIEN[route](client, db)
        assert antwort.status_code == 200, antwort.text
        assert beobachter.geschrieben >= 1 and beobachter.verstoesse == []
    finally:
        db.close()


def test_no_reminder_write_outside_app_reminders():
    """Mahnungen schreibt nur app/reminders.py (dort jede Stelle unter der Sperre, siehe Rundgang): kein Reminder(…) und keine
    Zuweisung an eine Mahnung in anderen Modulen unter app/."""
    import ast
    funde = []
    for path in (ROOT / "app").rglob("*.py"):
        if path.name == "reminders.py" and path.parent.name == "app":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Reminder":
                funde.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert funde == [], funde
