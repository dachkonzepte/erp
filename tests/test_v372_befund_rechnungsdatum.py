"""Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026, docs/archiv/befund-vor-echtbetrieb.md), Punkt 4:
Rechnungsdatum und die übrigen Fälle der Regel-20-Ausnahmeliste (tests/test_v316_berlin_time.py, BEKANNTE_VORGABEN).

Invoice.invoice_date setzt keine Funktion ausdrücklich -- es greift immer die Spaltenvorgabe default=date.today (app/models.py),
also die Uhr des Rechners: auf dem Server UTC, zwischen 0 und 1 Uhr (Winter) bzw. 2 Uhr (Sommer) Berliner Zeit der Vortag. Gesetzt
beim Anlegen des Entwurfs, beim Festschreiben und Versand nicht erneuert, im Entwurf nicht änderbar. Die Fälligkeit beim Anlegen
rechnet dagegen ab berlin_today(), das Skontodatum ab invoice_date, eine gewählte Zahlungsbedingung ab invoice_date; die Nummer
nimmt das Berliner Jahr beim Festschreiben.

server_uhr stellt den Server nach: die Uhr der App (app.berlin_time) läuft auf einem UTC-Zeitpunkt, und die Spaltenvorgabe
date.today liefert dessen UTC-Datum. date.today selbst lässt sich nicht ersetzen; die Vorgabe der Spalte wird deshalb über
SQLAlchemys Beschreibung der Vorgabe umgelenkt (Column._default_description_tuple, SQLAlchemy 2.0) -- eine Vorbedingung prüft, dass
die Umlenkung greift. Fehler als xfail (tests/befund_vor_echtbetrieb.py); 4d seit 1.8.71 behoben, sein Test ist der Abnahmetest."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.sql.schema import ColumnDefault, _DefaultDescriptionTuple

from app import berlin_time
from app.berlin_time import berlin_today
from app.invoices import (
    create_schlussrechnung,
    finalize_and_send_invoice,
    format_payment_terms_sentence,
    update_invoice_payment_term,
)
from app.models import Invoice, PaymentTerm
from tests.befund_vor_echtbetrieb import befund, vorbedingung
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.leistungszeitraum import festschreiben

SOMMER_UTC = datetime(2026, 7, 14, 22, 30)      # in Berlin 15.07.2026, 0:30 Uhr (MESZ)
SILVESTER_UTC = datetime(2026, 12, 31, 23, 30)  # in Berlin 01.01.2027, 0:30 Uhr (MEZ)


@pytest.fixture
def server_uhr(monkeypatch):
    """server_uhr(utc_naive): App-Uhr und Rechner-Uhr wie auf dem VPS (Etc/UTC). Liefert das Berliner Datum."""
    def stellen(utc_naive: datetime) -> date:
        monkeypatch.setattr(berlin_time, "_utc_now", lambda: utc_naive.replace(tzinfo=timezone.utc))
        rechner = _DefaultDescriptionTuple._from_column_default(ColumnDefault(lambda: utc_naive.date()))
        monkeypatch.setattr(Invoice.__table__.c.invoice_date, "_default_description_tuple", rechner)
        return berlin_today()
    return stellen


def _auftrag_mit_zahlungsbedingung(db):
    order, _ = make_order_with_item(db)
    term = PaymentTerm(label="14 Tage, 7 Tage 2 % Skonto", days=14, skonto_percent=Decimal("2"), skonto_days=7)
    db.add(term)
    order.payment_terms = term.label
    db.commit()
    return order, term


def _entwurf(db, order, utc_naive):
    invoice = create_schlussrechnung(db, order)
    vorbedingung(invoice.invoice_date in (utc_naive.date(), berlin_today()),
                 f"Rechner-Uhr nicht umgelenkt: {invoice.invoice_date}")
    return invoice


# ---------------------------------------------------------------------------
# 4a-4c: Rechnung
# ---------------------------------------------------------------------------

@befund("4a", "Rechnungsdatum aus der Rechner-Uhr (Server: UTC) -- zwischen 0 und 1 bzw. 2 Uhr der Vortag, an Silvester das "
              "alte Jahr bei einer Nummer des neuen")
@pytest.mark.parametrize("utc_naive", [SOMMER_UTC, SILVESTER_UTC], ids=["sommer", "silvester"])
def test_invoice_date_is_the_berlin_date(server_uhr, utc_naive):
    db = db_session()
    heute = server_uhr(utc_naive)
    order, _ = make_order_with_item(db)
    invoice = festschreiben(db, _entwurf(db, order, utc_naive))
    vorbedingung(invoice.invoice_number.startswith(f"R-{heute.year}-"), invoice.invoice_number)
    assert invoice.invoice_date == heute


@befund("4b", "Fälligkeit beim Anlegen ab berlin_today(), Skontodatum und Fälligkeit nach Wahl einer Zahlungsbedingung ab "
              "invoice_date -- nachts um einen Tag versetzt")
def test_due_date_and_cash_discount_date_count_from_the_same_day(server_uhr):
    db = db_session()
    server_uhr(SOMMER_UTC)
    order, term = _auftrag_mit_zahlungsbedingung(db)
    invoice = _entwurf(db, order, SOMMER_UTC)
    beim_anlegen = invoice.due_date
    satz = format_payment_terms_sentence(invoice)
    update_invoice_payment_term(db, invoice, term.id)
    assert (beim_anlegen, satz) == (invoice.invoice_date + timedelta(days=14), (
        f"Zahlbar rein netto bis zum {(invoice.invoice_date + timedelta(days=14)):%d.%m.%Y}. Bei Zahlung bis zum "
        f"{(invoice.invoice_date + timedelta(days=7)):%d.%m.%Y} gewähren wir 2 % Skonto, das entspricht 119,00 €."))
    assert invoice.due_date == beim_anlegen


@befund("4c", "Fälligkeit und Skontofrist stehen beim Entwurf fest -- ein später festgeschriebener Entwurf ist bei Versand "
              "schon fällig (und wird gleich als überfällig geführt)")
def test_a_draft_finalized_later_is_not_already_due(server_uhr):
    db = db_session()
    server_uhr(SOMMER_UTC)
    order, _ = _auftrag_mit_zahlungsbedingung(db)
    invoice = _entwurf(db, order, SOMMER_UTC)
    heute = server_uhr(SOMMER_UTC + timedelta(days=21))  # drei Wochen später festgeschrieben und versendet
    invoice = festschreiben(db, invoice)
    assert invoice.due_date >= heute


def test_today_invoice_date_is_neither_editable_nor_renewed():
    """Grün, zur Einordnung: das Rechnungsdatum entsteht mit dem Entwurf; das Teil-Update des Kopfs kennt es nicht, das
    Festschreiben (Nummer, Status) lässt es stehen."""
    from app.invoices import INVOICE_HEADER_FIELDS
    from app.schemas import InvoiceHeaderUpdate

    assert "invoice_date" not in INVOICE_HEADER_FIELDS and "invoice_date" not in InvoiceHeaderUpdate.model_fields
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    invoice.invoice_date = date(2026, 7, 1)  # wie ein älterer Entwurf
    db.commit()
    assert festschreiben(db, invoice).invoice_date == date(2026, 7, 1)


# ---------------------------------------------------------------------------
# 4d: die übrigen Fälle der Ausnahmeliste
# ---------------------------------------------------------------------------

def test_order_date_default_of_the_api_is_the_berlin_date(server_uhr):
    """4d, seit 1.8.71 behoben (Abnahmetest, bis dahin xfail): ohne Datum in der Anfrage das Berliner Datum."""
    from app.schemas import OrderCreateFromQuote

    heute = server_uhr(SOMMER_UTC)
    assert OrderCreateFromQuote().order_date == heute


def test_today_other_dates_of_the_list_are_set_from_berlin_today(server_uhr):
    """Grün: Mahnung, Einsatzbericht und Schnellauftrag setzen ihr Datum ausdrücklich aus berlin_today() -- die Spaltenvorgaben
    Reminder.reminder_date, ServiceReport.performed_at und Order.order_date greifen dort nicht (QuoteDocumentMeta.quote_date:
    test_v316)."""
    from app.reminders import create_reminder
    from app.service_reports import create_report
    from tests.test_v153_mahnwesen import make_sent_overdue_invoice

    db = db_session()
    heute = server_uhr(SOMMER_UTC)
    invoice = make_sent_overdue_invoice(db)
    assert create_reminder(db, invoice, 1).reminder_date == heute
    report = create_report(db, invoice.order_id, "rapport")
    assert report["performed_at"] == heute
