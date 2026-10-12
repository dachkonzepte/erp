"""Mahnwesen Z2a (seit 1.8.79): gleichzeitige Aktionen gegen PostgreSQL.

Gegen die lokale PostgreSQL (ERP_TEST_POSTGRES_URL, opt-in, sonst übersprungen): die erste Aktion hält ihre Sperren eine
Sekunde (Commit angehalten), die zweite startet währenddessen, wartet und findet danach den Stand der ersten vor
(tests/test_v375_rechnungen_sperren.py::_run()):
  - zwei Entwürfe für dieselbe Rechnung (einzeln und für mehrere) -> einer;
  - Bearbeiten gegen Festschreiben -> das Bearbeiten wartet und wird abgelehnt; Festschreiben nach dem Bearbeiten nimmt dessen
    Frist;
  - Zahlung gegen Festschreiben und gegen eine nachgetragene Zustellung -> beide warten und lehnen mit dem neuen Betrag ab;
  - Kundenwechsel gegen Festschreiben einer Rechnung, in beiden Reihenfolgen -> die Rechnung hält immer den Kunden, der danach
    am Projekt steht, oder der Wechsel wird abgelehnt."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select, update

from app.berlin_time import berlin_today
from app.email_dispatch import record_manual_delivery
from app.invoices import InvoiceBlocked, create_abschlag_pauschal
from app.models import Customer, EmailDispatch, Invoice, Order, Project, Reminder
from app.orders import change_orders_customer
from app.payments import Line, book_payment, invoice_customer_id
from app.project_participants import ClientChangeConflict, check_client_change
from app.reminders import create_reminder, create_reminders, finalize_and_send_reminder, update_reminder_draft
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

D = Decimal
HEUTE = berlin_today()


def _faellig(s, order_id, net="1000"):
    """Festgeschriebener pauschaler Abschlag (1.190,00 €), seit zehn Tagen überfällig."""
    invoice = festschreiben(s, create_abschlag_pauschal(s, s.get(Order, order_id), lump_sum_net=D(net)))
    s.execute(update(Invoice).where(Invoice.id == invoice.id).values(due_date=HEUTE - timedelta(days=10)))
    s.commit()
    return invoice.id


def _zaehlen(Session, model, *where):
    return _vorbereiten(Session, lambda s: s.scalar(select(func.count()).select_from(model).where(*where)))


def _zahlen(s, invoice_id, amount):
    invoice = s.get(Invoice, invoice_id)
    return book_payment(s, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D(amount), note=None,
                        lines=[Line(invoice_id, zahlung=D(amount))])


def _mit_geladenen_mahnungen(s, invoice_id):
    """Rechnung samt ihren Mahnungen laden (alter Stand, wie die Seite vor dem Klick) -- nach der Sperre muss das Anlegen sie
    frisch lesen."""
    invoice = s.get(Invoice, invoice_id)
    assert invoice.reminders == []
    return create_reminder(s, invoice)


def test_pg_two_drafts_for_the_same_invoice_at_once_give_one(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    _, second = _run(Session, lambda s: create_reminder(s, s.get(Invoice, invoice_id)).id,
                     lambda s: _mit_geladenen_mahnungen(s, invoice_id))
    assert isinstance(second, InvoiceBlocked) and "schon ein Mahnungsentwurf" in str(second), second
    assert _zaehlen(Session, Reminder) == 1


def test_pg_bulk_and_single_at_once_give_one(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    _, second = _run(Session, lambda s: create_reminder(s, s.get(Invoice, invoice_id)).id,
                     lambda s: create_reminders(s, [invoice_id]))
    assert second["created"] == [] and "schon ein Mahnungsentwurf" in second["rejected"][0]["reason"], second
    assert _zaehlen(Session, Reminder) == 1


def test_pg_editing_waits_for_finalizing_and_is_refused(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    reminder_id = _vorbereiten(Session, lambda s: create_reminder(s, s.get(Invoice, invoice_id)).id)
    _, second = _run(Session, lambda s: finalize_and_send_reminder(s, s.get(Reminder, reminder_id)).id,
                     lambda s: update_reminder_draft(s, s.get(Reminder, reminder_id), text="nachträglich",
                                                     payment_days=30))
    assert isinstance(second, InvoiceBlocked) and "festgeschrieben" in str(second), second
    assert _vorbereiten(Session, lambda s: (s.get(Reminder, reminder_id).status, s.get(Reminder, reminder_id).text != "nachträglich",
                                            s.get(Reminder, reminder_id).new_due_date)) == (
        "versendet", True, HEUTE + timedelta(days=7))


def test_pg_finalizing_waits_for_editing_and_takes_its_deadline(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    reminder_id = _vorbereiten(Session, lambda s: create_reminder(s, s.get(Invoice, invoice_id)).id)
    _, second = _run(Session, lambda s: update_reminder_draft(s, s.get(Reminder, reminder_id), text="neu",
                                                              payment_days=20).id,
                     lambda s: finalize_and_send_reminder(s, s.get(Reminder, reminder_id)).new_due_date)
    assert second == HEUTE + timedelta(days=20), second


def test_pg_finalizing_waits_for_a_payment_and_refuses_the_old_amount(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    reminder_id = _vorbereiten(Session, lambda s: create_reminder(s, s.get(Invoice, invoice_id)).id)
    _, second = _run(Session, lambda s: _zahlen(s, invoice_id, "100").id,
                     lambda s: finalize_and_send_reminder(s, s.get(Reminder, reminder_id)))
    assert isinstance(second, InvoiceBlocked) and "1.090,00 €" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(Reminder, reminder_id).status) == "entwurf"


def test_pg_manual_delivery_waits_for_a_payment_and_is_refused(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    reminder_id = _vorbereiten(Session, lambda s: finalize_and_send_reminder(
        s, create_reminder(s, s.get(Invoice, invoice_id))).id)
    _, second = _run(Session, lambda s: _zahlen(s, invoice_id, "100").id,
                     lambda s: record_manual_delivery(s, dispatch_key="zustellung-pg-000001", document_type="mahnung",
                                                      document_id=s.get(Reminder, reminder_id).id, channel="bote",
                                                      delivered_on=HEUTE, note="Bote, an Frau Muster"))
    assert isinstance(second, InvoiceBlocked) and "mahnfähig waren am" in str(second), second
    assert _zaehlen(Session, EmailDispatch) == 0


def _anderer_kunde(Session):
    def anlegen(s):
        customer = Customer(name="Anderer Kunde", last_name="Anderer Kunde")
        s.add(customer)
        s.commit()
        return customer.id
    return _vorbereiten(Session, anlegen)


def _projekt(s, order_id):
    return s.get(Project, s.get(Order, order_id).project_id)


def test_pg_client_change_waits_for_an_invoice_being_finalized_and_is_refused(pg):
    Session, order_id = pg
    other = _anderer_kunde(Session)
    draft_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_abschlag_pauschal(s, s.get(Order, order_id),
                                                                                        lump_sum_net=D("100"))).id)
    _, second = _run(Session, lambda s: festschreiben(s, s.get(Invoice, draft_id)).id,
                     lambda s: check_client_change(s, _projekt(s, order_id), other))
    assert isinstance(second, ClientChangeConflict) and "festgeschrieben" in str(second), second


def test_pg_finalizing_waits_for_a_client_change_and_holds_the_new_customer(pg):
    Session, order_id = pg
    other = _anderer_kunde(Session)
    draft_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_abschlag_pauschal(s, s.get(Order, order_id),
                                                                                        lump_sum_net=D("100"))).id)

    def wechseln(s):
        # Seit 1.8.80 (Z2b "Vorweg" 1) mit Auftrag nur zusammen mit dessen Vertragspartner und mit Begründung.
        project = _projekt(s, order_id)
        check_client_change(s, project, other, reason="Vertragspartner falsch")
        change_orders_customer(s, project.id, s.get(Customer, other), reason="Vertragspartner falsch")
        project.customer_id = other
        s.commit()
        return project.id

    _, second = _run(Session, wechseln, lambda s: festschreiben(s, s.get(Invoice, draft_id)).customer_id)
    assert second == other, second
