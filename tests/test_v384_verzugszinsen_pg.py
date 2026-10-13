"""Zahlungsstufe Z2b Punkte 7-9 (seit 1.8.81): gleichzeitige Aktionen gegen PostgreSQL.

Gegen die lokale PostgreSQL (ERP_TEST_POSTGRES_URL, opt-in, sonst übersprungen): die erste Aktion hält ihre Sperren eine Sekunde
(Commit angehalten), die zweite startet währenddessen, wartet und findet danach den Stand der ersten vor
(tests/test_v375_rechnungen_sperren.py::_run()):
  - zwei Zahlungen auf dieselbe Nebenforderung -> die zweite wäre eine Überbuchung der Nebenforderung;
  - Gegenbuchung einer Nebenforderung gegen eine Zahlung darauf, in beiden Reihenfolgen;
  - Festschreiben mit Zinsen gegen Verwerfen des Verzugsbeginns, in beiden Reihenfolgen -> nie Zinsen ohne Verzug;
  - Festschreiben mit Gebühr gegen Festschreiben des Stornos, in beiden Reihenfolgen -> nie ein Storno mit offener Nebenforderung;
  - Festschreiben gegen eine Zahlung auf eine Nebenforderung: die Aufstellung zeigt sie;
  - derselbe Basiszinssatz zweimal angelegt -> einer; derselbe Rechtstext zweimal zum ersten Mal gespeichert -> eine Zeile."""

import json
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.berlin_time import berlin_today
from app.default_interest import RateConflict, create_rate, half_year_of, next_half_year
from app.dunning_charges import ChargeRejected, confirm_default_start, discard_default_start, reverse_charge
from app.dunning_texts import update_text
from app.invoices import InvoiceBlocked, create_storno_draft
from app.models import (
    BaseInterestRate, DunningLegalText, Invoice, InvoiceCharge, InvoiceDefaultStart, PaymentAllocation, Reminder,
)
from app.payments import ChargeLine, Line, PaymentRejected, book_payment, invoice_customer_id
from app.reminders import create_reminder, finalize_and_send_reminder, set_reminder_charges
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)
from tests.test_v383_nebenforderungen_pg import _erste_zugestellt, _faellig, _zaehlen

D = Decimal
HEUTE = berlin_today()


def _saetze(s):
    hy, last = half_year_of(HEUTE - timedelta(days=400)), half_year_of(HEUTE)
    while hy <= last:
        s.add(BaseInterestRate(half_year_start=hy, rate_percent=D("1.27"), reviewed_on=HEUTE, reviewed_by="Test"))
        hy = next_half_year(hy)
    s.commit()


def _mit_gebuehr(Session, order_id):
    """Abschlag mit festgeschriebener 2. Mahnung samt Gebühr 10,00 € (hinausgegangen): (Rechnung, Nebenforderung)."""
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    _vorbereiten(Session, lambda s: _erste_zugestellt(s, invoice_id))

    def gebuehr(s):
        second = create_reminder(s, s.get(Invoice, invoice_id))
        set_reminder_charges(s, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
        finalize_and_send_reminder(s, second)
        return s.scalar(select(InvoiceCharge.id))

    return invoice_id, _vorbereiten(Session, gebuehr)


def _zahlung_auf(s, invoice_id, charge_id, amount="10.00"):
    invoice = s.get(Invoice, invoice_id)
    return book_payment(s, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D(amount), note=None,
                        lines=[Line(invoice_id, charges=(ChargeLine(charge_id, D(amount)),))])


def test_pg_two_payments_on_the_same_charge_the_second_would_overbook(pg):
    Session, order_id = pg
    invoice_id, charge_id = _mit_gebuehr(Session, order_id)
    _, second = _run(Session, lambda s: _zahlung_auf(s, invoice_id, charge_id).id,
                     lambda s: _zahlung_auf(s, invoice_id, charge_id))
    assert isinstance(second, PaymentRejected) and "Überbuchung der Nebenforderung" in str(second), second
    assert _zaehlen(Session, PaymentAllocation, PaymentAllocation.charge_id == charge_id) == 1


def test_pg_payment_waits_for_the_reversal_of_its_charge_and_is_refused(pg):
    Session, order_id = pg
    invoice_id, charge_id = _mit_gebuehr(Session, order_id)
    _, second = _run(Session, lambda s: reverse_charge(s, s.get(InvoiceCharge, charge_id), reason="Kulanz").id,
                     lambda s: _zahlung_auf(s, invoice_id, charge_id))
    assert isinstance(second, PaymentRejected) and "gegengebucht" in str(second), second
    assert _zaehlen(Session, PaymentAllocation) == 0


def test_pg_reversal_waits_for_a_payment_on_the_charge_and_is_refused(pg):
    Session, order_id = pg
    invoice_id, charge_id = _mit_gebuehr(Session, order_id)
    _, second = _run(Session, lambda s: _zahlung_auf(s, invoice_id, charge_id).id,
                     lambda s: reverse_charge(s, s.get(InvoiceCharge, charge_id), reason="Kulanz"))
    assert isinstance(second, ChargeRejected) and "Zahlung gebucht" in str(second), second
    assert _zaehlen(Session, InvoiceCharge, InvoiceCharge.reverses_charge_id.is_not(None)) == 0


def _mit_zinsen_im_entwurf(Session, order_id):
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    _vorbereiten(Session, lambda s: _erste_zugestellt(s, invoice_id))
    _vorbereiten(Session, _saetze)

    def entwurf(s):
        start = confirm_default_start(s, s.get(Invoice, invoice_id), starts_on=HEUTE - timedelta(days=8), reason=None)
        second = create_reminder(s, s.get(Invoice, invoice_id))
        set_reminder_charges(s, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False,
                             interest_accepted=True)
        return start.id, second.id

    return (invoice_id, *_vorbereiten(Session, entwurf))


def test_pg_discarding_the_default_waits_for_the_interest_and_is_refused(pg):
    Session, order_id = pg
    _, start_id, draft_id = _mit_zinsen_im_entwurf(Session, order_id)
    _, second = _run(Session, lambda s: finalize_and_send_reminder(s, s.get(Reminder, draft_id)).id,
                     lambda s: discard_default_start(s, s.get(InvoiceDefaultStart, start_id), reason="falsch"))
    assert isinstance(second, ChargeRejected) and "Verzugszinsen" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(InvoiceDefaultStart, start_id).discarded_at) is None
    assert _zaehlen(Session, InvoiceCharge, InvoiceCharge.kind == "zinsen") == 1


def test_pg_interest_waits_for_the_discarded_default_and_is_refused(pg):
    Session, order_id = pg
    _, start_id, draft_id = _mit_zinsen_im_entwurf(Session, order_id)
    _, second = _run(Session, lambda s: discard_default_start(s, s.get(InvoiceDefaultStart, start_id), reason="falsch").id,
                     lambda s: finalize_and_send_reminder(s, s.get(Reminder, draft_id)))
    assert isinstance(second, InvoiceBlocked) and "Verzugsbeginn ist nicht bestätigt" in str(second), second
    assert _zaehlen(Session, InvoiceCharge) == 0
    assert _vorbereiten(Session, lambda s: s.get(Reminder, draft_id).status) == "entwurf"


def _gebuehr_im_entwurf_und_storno(Session, order_id):
    invoice_id = _vorbereiten(Session, lambda s: _faellig(s, order_id))
    _vorbereiten(Session, lambda s: _erste_zugestellt(s, invoice_id))

    def vorbereiten(s):
        second = create_reminder(s, s.get(Invoice, invoice_id))
        set_reminder_charges(s, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
        storno = mit_zeitraum(s, create_storno_draft(s, s.get(Invoice, invoice_id)))
        return second.id, storno.id

    return (invoice_id, *_vorbereiten(Session, vorbereiten))


def test_pg_storno_waits_for_the_fee_and_is_refused(pg):
    Session, order_id = pg
    invoice_id, draft_id, storno_id = _gebuehr_im_entwurf_und_storno(Session, order_id)
    _, second = _run(Session, lambda s: finalize_and_send_reminder(s, s.get(Reminder, draft_id)).id,
                     lambda s: festschreiben(s, s.get(Invoice, storno_id)))
    assert isinstance(second, InvoiceBlocked) and "offene Nebenforderungen" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(Invoice, invoice_id).status) == "versendet"


def test_pg_fee_waits_for_the_storno_and_is_refused(pg):
    Session, order_id = pg
    invoice_id, draft_id, storno_id = _gebuehr_im_entwurf_und_storno(Session, order_id)
    _, second = _run(Session, lambda s: festschreiben(s, s.get(Invoice, storno_id)).id,
                     lambda s: finalize_and_send_reminder(s, s.get(Reminder, draft_id)))
    assert isinstance(second, InvoiceBlocked) and "storniert" in str(second), second
    assert _zaehlen(Session, InvoiceCharge) == 0


def test_pg_finalizing_waits_for_a_payment_on_a_charge_and_shows_it(pg):
    Session, order_id = pg
    invoice_id, charge_id = _mit_gebuehr(Session, order_id)

    def dritte(s):
        second = s.scalar(select(Reminder).where(Reminder.level == 2))
        from tests.mahnung import frist_ablaufen, zustellen
        frist_ablaufen(s, second)
        zustellen(s, second)
        return create_reminder(s, s.get(Invoice, invoice_id)).id

    third_id = _vorbereiten(Session, dritte)
    _run(Session, lambda s: _zahlung_auf(s, invoice_id, charge_id, "4.00").id,
         lambda s: finalize_and_send_reminder(s, s.get(Reminder, third_id)))
    raw = _vorbereiten(Session, lambda s: json.loads(s.get(Reminder, third_id).amounts_json))
    # Seit 1.8.89 Format 4 (abgezogene Rechnungen der Endrechnung und angemahnter Betrag; hier keine).
    assert (raw["format"], raw["charges_paid"], raw["charges_open"]) == (4, "4.00", "6.00"), raw


def test_pg_the_same_base_rate_twice_at_once_gives_one(pg):
    Session, _ = pg
    start = half_year_of(HEUTE)
    _, second = _run(Session, lambda s: create_rate(s, half_year_start=start, rate_percent="1.27", reviewed_on=None,
                                                    reviewed_by=None).id,
                     lambda s: create_rate(s, half_year_start=start, rate_percent="1.37", reviewed_on=None, reviewed_by=None))
    assert isinstance(second, RateConflict), second
    assert _vorbereiten(Session, lambda s: s.scalar(select(func.count()).select_from(BaseInterestRate))) == 1


def test_pg_the_same_legal_text_saved_twice_for_the_first_time_gives_one_row(pg):
    Session, _ = pg
    first, second = _run(Session, lambda s: update_text(s, "zinsen", body="Erster", reviewed_on=None, reviewed_by=None)[0],
                         lambda s: update_text(s, "zinsen", body="Zweiter", reviewed_on=None, reviewed_by=None)[0])
    assert not isinstance(second, Exception), second
    rows = _vorbereiten(Session, lambda s: s.scalars(select(DunningLegalText.body)).all())
    assert rows == ["Zweiter"]
