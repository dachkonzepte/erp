"""Zahlungsstufe Z2b (seit 1.8.80): gleichzeitige Aktionen gegen PostgreSQL.

Gegen die lokale PostgreSQL (ERP_TEST_POSTGRES_URL, opt-in, sonst übersprungen): die erste Aktion hält ihre Sperren eine
Sekunde (Commit angehalten), die zweite startet währenddessen, wartet und findet danach den Stand der ersten vor
(tests/test_v375_rechnungen_sperren.py::_run()):
  - Verzugsbeginn zweimal bestätigt -> einer;
  - Ersatz einer nie hinausgegangenen Mahnung gegen ihre nachgetragene Zustellung, in beiden Reihenfolgen -> entweder ist sie
    zugestellt und der Ersatz überholt, oder sie ist ersetzt und die Zustellung abgelehnt;
  - dieselbe Nebenforderung zweimal gegengebucht -> eine Gegenbuchung;
  - Pauschale beim Festschreiben gegen Verwerfen des Verzugsbeginns, in beiden Reihenfolgen -> nie eine Pauschale ohne Verzug;
  - Kundenwechsel am Projekt gegen Beauftragen, in beiden Reihenfolgen -> der Auftrag hält den Kunden, der danach am Projekt
    steht, oder der Wechsel verlangt die Begründung."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select, update

from app.berlin_time import berlin_today
from app.dunning_charges import ChargeRejected, confirm_default_start, discard_default_start, reverse_charge
from app.email_dispatch import record_manual_delivery
from app.invoices import InvoiceBlocked, create_abschlag_pauschal
from app.models import (
    Customer, EmailDispatch, GeneralSettings, Invoice, InvoiceCharge, InvoiceDefaultStart, Order, Project, Reminder,
)
from app.orders import change_orders_customer
from app.project_participants import ClientChangeConflict, check_client_change
from app.projects import ensure_quote_structure
from app.reminders import create_reminder, finalize_and_send_reminder, set_reminder_charges
from tests.leistungszeitraum import festschreiben
from tests.mahnung import frist_ablaufen, zustellen
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

D = Decimal
HEUTE = berlin_today()


def _faellig(s, order_id, net="1000"):
    """Festgeschriebener pauschaler Abschlag (1.190,00 €), seit zehn Tagen überfällig; Mahngebühren eingeschaltet."""
    s.get(GeneralSettings, 1).dunning_charges_enabled = True
    invoice = festschreiben(s, create_abschlag_pauschal(s, s.get(Order, order_id), lump_sum_net=D(net)))
    s.execute(update(Invoice).where(Invoice.id == invoice.id).values(due_date=HEUTE - timedelta(days=10)))
    s.commit()
    return invoice.id


def _zaehlen(Session, model, *where):
    return _vorbereiten(Session, lambda s: s.scalar(select(func.count()).select_from(model).where(*where)))


def _erste_zugestellt(s, invoice_id):
    """1. Mahnung festgeschrieben und zugestellt, Frist abgelaufen."""
    first = finalize_and_send_reminder(s, create_reminder(s, s.get(Invoice, invoice_id)))
    frist_ablaufen(s, first)
    zustellen(s, first)
    return first.id


def _zustellung(s, reminder_id, key):
    return record_manual_delivery(s, dispatch_key=key, document_type="mahnung", document_id=reminder_id, channel="bote",
                                  delivered_on=HEUTE, note="Bote, an Frau Muster")


def test_pg_default_start_confirmed_twice_at_once_gives_one(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    _vorbereiten(Session, lambda s: _erste_zugestellt(s, invoice_id))
    starts_on = HEUTE - timedelta(days=8)  # Zustellung am Mahndatum (frist_ablaufen: vor acht Tagen)
    _, second = _run(Session, lambda s: confirm_default_start(s, s.get(Invoice, invoice_id), starts_on=starts_on, reason=None).id,
                     lambda s: confirm_default_start(s, s.get(Invoice, invoice_id), starts_on=starts_on, reason=None))
    assert isinstance(second, ChargeRejected) and "schon bestätigt" in str(second), second
    assert _zaehlen(Session, InvoiceDefaultStart) == 1


def test_pg_replacement_waits_for_the_delivery_of_the_old_one_and_is_overtaken(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    old_id = _vorbereiten(Session, lambda s: finalize_and_send_reminder(s, create_reminder(s, s.get(Invoice, invoice_id))).id)
    draft_id = _vorbereiten(Session, lambda s: create_reminder(s, s.get(Invoice, invoice_id)).id)  # Ersatz derselben Stufe
    _, second = _run(Session, lambda s: _zustellung(s, old_id, "zustellung-pg-alt-0001").dispatch.id,
                     lambda s: finalize_and_send_reminder(s, s.get(Reminder, draft_id)))
    assert isinstance(second, InvoiceBlocked) and "überholt" in str(second), second
    assert _vorbereiten(Session, lambda s: (s.get(Reminder, old_id).replaced_by_id, s.get(Reminder, draft_id).status)) == (
        None, "entwurf")


def test_pg_delivery_waits_for_the_replacement_and_is_refused(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    old_id = _vorbereiten(Session, lambda s: finalize_and_send_reminder(s, create_reminder(s, s.get(Invoice, invoice_id))).id)
    draft_id = _vorbereiten(Session, lambda s: create_reminder(s, s.get(Invoice, invoice_id)).id)
    _, second = _run(Session, lambda s: finalize_and_send_reminder(s, s.get(Reminder, draft_id)).id,
                     lambda s: _zustellung(s, old_id, "zustellung-pg-alt-0002"))
    assert isinstance(second, InvoiceBlocked) and "ersetzt" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(Reminder, old_id).replaced_by_id) == draft_id
    assert _zaehlen(Session, EmailDispatch, EmailDispatch.channel == "bote") == 0


def test_pg_the_same_charge_reversed_twice_at_once_gives_one_counter(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    _vorbereiten(Session, lambda s: _erste_zugestellt(s, invoice_id))

    def gebuehr(s):
        second = create_reminder(s, s.get(Invoice, invoice_id))
        set_reminder_charges(s, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
        finalize_and_send_reminder(s, second)
        return s.scalar(select(InvoiceCharge.id))

    charge_id = _vorbereiten(Session, gebuehr)
    _, second = _run(Session, lambda s: reverse_charge(s, s.get(InvoiceCharge, charge_id), reason="Kulanz").id,
                     lambda s: reverse_charge(s, s.get(InvoiceCharge, charge_id), reason="nochmal"))
    assert isinstance(second, ChargeRejected) and "schon gegengebucht" in str(second), second
    assert _zaehlen(Session, InvoiceCharge, InvoiceCharge.reverses_charge_id.is_not(None)) == 1


def _mit_pauschale_im_entwurf(Session, order_id):
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    _vorbereiten(Session, lambda s: _erste_zugestellt(s, invoice_id))

    def entwurf(s):
        start = confirm_default_start(s, s.get(Invoice, invoice_id), starts_on=HEUTE - timedelta(days=8), reason=None)
        second = create_reminder(s, s.get(Invoice, invoice_id))
        set_reminder_charges(s, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True)
        return start.id, second.id

    return (invoice_id, *_vorbereiten(Session, entwurf))


def test_pg_discarding_the_default_waits_for_the_flat_fee_and_is_refused(pg):
    Session, order_id = pg
    _, start_id, draft_id = _mit_pauschale_im_entwurf(Session, order_id)
    _, second = _run(Session, lambda s: finalize_and_send_reminder(s, s.get(Reminder, draft_id)).id,
                     lambda s: discard_default_start(s, s.get(InvoiceDefaultStart, start_id), reason="falsch"))
    assert isinstance(second, ChargeRejected) and "Pauschale" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(InvoiceDefaultStart, start_id).discarded_at) is None


def test_pg_flat_fee_waits_for_the_discarded_default_and_is_refused(pg):
    Session, order_id = pg
    _, start_id, draft_id = _mit_pauschale_im_entwurf(Session, order_id)
    _, second = _run(Session, lambda s: discard_default_start(s, s.get(InvoiceDefaultStart, start_id), reason="falsch").id,
                     lambda s: finalize_and_send_reminder(s, s.get(Reminder, draft_id)))
    assert isinstance(second, InvoiceBlocked) and "nicht bestätigt" in str(second), second
    assert _zaehlen(Session, InvoiceCharge) == 0
    assert _vorbereiten(Session, lambda s: s.get(Reminder, draft_id).status) == "entwurf"


def _neuer_kunde_und_angebot(Session):
    def anlegen(s):
        customer = Customer(name="Neuer Bauherr", last_name="Neuer Bauherr")
        s.add(customer)
        s.commit()
        quote = make_quote(s, is_consumer=False, number="0099")
        # Kopf und Layout schon da (wie nach dem Öffnen des Angebots) -- sonst committete das Beauftragen sie vor der Sperre,
        # und der angehaltene Commit läge dort statt hinter der Sperre der Projektzeile.
        ensure_quote_structure(s, quote)
        return customer.id, quote.id, quote.project_id
    return _vorbereiten(Session, anlegen)


def test_pg_ordering_waits_for_a_client_change_and_holds_the_new_customer(pg):
    Session, _ = pg
    other, quote_id, project_id = _neuer_kunde_und_angebot(Session)

    def wechseln(s):
        project = s.get(Project, project_id)
        check_client_change(s, project, other)  # noch kein Auftrag: ohne Begründung
        project.customer_id = other
        s.commit()
        return project.id

    _, second = _run(Session, wechseln, lambda s: beauftragen(s, s.get(type(s.get(Project, project_id).quotes[0]), quote_id)))
    assert not isinstance(second, Exception), second
    assert _vorbereiten(Session, lambda s: s.scalar(select(Order.customer_id).where(Order.source_quote_id == quote_id))) == other


def test_pg_client_change_waits_for_ordering_and_asks_for_a_reason(pg):
    Session, _ = pg
    other, quote_id, project_id = _neuer_kunde_und_angebot(Session)

    def wechseln(s):
        project = s.get(Project, project_id)
        check_client_change(s, project, other)
        change_orders_customer(s, project.id, s.get(Customer, other), reason="")
        project.customer_id = other
        s.commit()

    _, second = _run(Session, lambda s: beauftragen(s, s.get(type(s.get(Project, project_id).quotes[0]), quote_id)).id,
                     wechseln)
    assert isinstance(second, ClientChangeConflict) and "Begründung" in str(second), second
    assert _vorbereiten(Session, lambda s: (s.get(Project, project_id).customer_id != other,
                                            s.scalar(select(Order.customer_id).where(Order.source_quote_id == quote_id)) != other)) == (
        True, True)
