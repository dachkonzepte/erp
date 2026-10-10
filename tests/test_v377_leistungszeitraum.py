"""Leistungszeitraum an der Rechnung und nächste Nummer in den Einstellungen (seit 1.8.74, docs/archiv/befund-vor-echtbetrieb.md
"Umsetzung 1.8.74").

- Einstellungen, alle sieben Nummernkreise: die nächste Nummer darf nicht auf oder unter eine vergebene desselben Formats und
  Jahres gesetzt werden -- 409 mit der höchsten vergebenen, kein stilles Überspringen (app/settings.py::update_sequence()).
- Leistungszeitraum (app/service_period.py): Beginn/Ende an der Rechnung, Ende >= Beginn, auf dem PDF, Pflicht beim
  Festschreiben (409 mit Grund). Vorschlag im Entwurf mit Quelle, übernommen nur per Klick (PUT); Storno übernimmt den Zeitraum
  der stornierten Rechnung; festgeschriebener Altbestand ohne Zeitraum bleibt, wie er ist."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.berlin_time import berlin_now
from app.grunddaten import anlegen
from app.invoice_pdf import build_invoice_pdf
from app.invoices import (
    InvoiceBlocked,
    create_abschlag_leistungsstand,
    create_invoice_from_time_entries,
    create_schlussrechnung,
    create_storno_draft,
    finalize_and_send_invoice,
    invoice_to_dict,
    update_invoice_header,
    update_invoice_item,
)
from app.models import (
    Customer, CustomerProfile, Employee, Inquiry, Invoice, NumberSequence, Order, OrderAcceptance, Project, Quote, Reminder,
    TimeEntry,
)
from app.project_pipeline_columns import default_pipeline_column_id
from app.reminders import create_reminder, finalize_and_send_reminder
from app.routers.invoices import router as invoices_router
from app.routers.settings import router as settings_router
from app.service_period import proposal
from app.settings import DEFAULT_SEQUENCES, NumberBelowExisting, issue_number, load_sequence, update_sequence
from app.time_tracking import list_entries
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.test_v231_invoice_item_table_width_and_quantity import _extract_pdf_text
from tests.leistungszeitraum import festschreiben, mit_zeitraum

D = date


def _db():
    db = db_session()
    anlegen(db)
    db.commit()
    return db


# ---------------------------------------------------------------------------
# A: nächste Nummer nicht auf oder unter eine vergebene (alle sieben Nummernkreise)
# ---------------------------------------------------------------------------

_LAUF = iter(range(1, 10_000))


def _vergeben(db, key) -> str:
    """Eine Nummer des Nummernkreises vergeben und mit einem Datensatz belegen -- wie im Betrieb. Hilfsdatensätze tragen
    Nummern außerhalb jedes Formats (X-…)."""
    number = issue_number(db, key)
    n = next(_LAUF)
    customer = Customer(name="Kunde", last_name="Kunde")
    db.add(customer); db.flush()
    if key == "customer":
        db.add(CustomerProfile(customer_id=customer.id, customer_number=number))
        db.commit()
        return number
    if key == "inquiry":
        db.add(Inquiry(inquiry_number=number, customer_id=customer.id, title="Anfrage"))
        db.commit()
        return number
    project = Project(project_number=number if key == "project" else f"X-P-{n}", name="P", customer_id=customer.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.flush()
    if key == "quote":
        db.add(Quote(quote_number=number, project_id=project.id, title="A"))
    if key in ("order", "invoice", "reminder"):
        order = Order(order_number=number if key == "order" else f"X-AUF-{n}", project_id=project.id, source_quote_id=n,
                      quote_number_snapshot="A", title="T", customer_name="Kunde")
        db.add(order); db.flush()
        if key in ("invoice", "reminder"):
            invoice = Invoice(order_id=order.id, invoice_type="schluss", status="versendet", customer_name="K",
                              invoice_number=number if key == "invoice" else f"X-R-{n}", vat_rate=Decimal("19"))
            db.add(invoice); db.flush()
            if key == "reminder":
                db.add(Reminder(invoice_id=invoice.id, level=1, status="versendet", reminder_number=number,
                                reminder_date=D(2026, 10, 1), outstanding_amount=Decimal("1"), fee_amount=Decimal("0")))
    db.commit()
    return number


@pytest.mark.parametrize("key", sorted(DEFAULT_SEQUENCES))
def test_next_number_cannot_be_set_on_or_below_an_issued_one(key):
    db = _db()
    erste = _vergeben(db, key)
    zweite = _vergeben(db, key)
    seq = load_sequence(db, key)
    vorher = seq.next_value
    for zu_tief in (1, 2):
        with pytest.raises(NumberBelowExisting) as exc:
            update_sequence(db, key, format_pattern=seq.format_pattern, start_value=1, next_value=zu_tief, reset_yearly=True)
        assert str(exc.value) == (f"Die nächste Nummer darf nicht auf oder unter einer vergebenen liegen: höchste vergebene "
                                  f"Nummer in diesem Format ist {zweite} -- nächste Nummer mindestens 3.")
        db.rollback()
    assert load_sequence(db, key).next_value == vorher
    assert update_sequence(db, key, format_pattern=seq.format_pattern, start_value=1, next_value=3, reset_yearly=True).next_value == 3
    assert erste != zweite


def test_other_format_or_year_does_not_block():
    db = _db()
    _vergeben(db, "invoice")
    jahr = berlin_now().year
    # Vorjahr im selben Format zählt nicht
    order, _ = make_order_with_item(db, quantity=Decimal("1"))
    db.add(Invoice(order_id=order.id, invoice_type="schluss", status="versendet", customer_name="K",
                   invoice_number=f"R-{jahr - 1}-0099", vat_rate=Decimal("19")))
    db.commit()
    assert update_sequence(db, "invoice", format_pattern="R-{YYYY}-{NNNN}", start_value=1, next_value=2,
                           reset_yearly=True).next_value == 2  # 0099 aus dem Vorjahr sperrt nicht
    with pytest.raises(NumberBelowExisting):
        update_sequence(db, "invoice", format_pattern="R-{YYYY}-{NNNN}", start_value=1, next_value=1, reset_yearly=True)
    db.rollback()
    neu = update_sequence(db, "invoice", format_pattern="RE-{YYYY}-{NNNN}", start_value=1, next_value=1, reset_yearly=True)
    assert (neu.format_pattern, neu.next_value) == ("RE-{YYYY}-{NNNN}", 1)


def test_settings_route_answers_409_naming_the_highest_and_changes_nothing(threaded_db_session, router_test_client):
    db = threaded_db_session
    erste = _vergeben(db, "invoice")
    client = router_test_client(db, settings_router)
    antwort = client.put("/api/settings/number-sequences/invoice", json={
        "format_pattern": "R-{YYYY}-{NNNN}", "start_value": 1, "next_value": 1, "reset_yearly": True})
    assert antwort.status_code == 409 and erste in antwort.json()["detail"], antwort.text
    db.expire_all()
    assert db.scalar(select(NumberSequence.next_value).where(NumberSequence.sequence_key == "invoice")) == 2


def test_issuing_skips_issued_invoice_numbers_instead_of_doubling_them():
    """Bis 1.8.73 kannte der Abgleich Rechnung und Mahnung nicht -- eine zurückgesetzte nächste Nummer gab eine Dublette."""
    db = _db()
    erste = _vergeben(db, "invoice")
    load_sequence(db, "invoice").next_value = 1  # an den Einstellungen vorbei (z. B. von Hand in der Datenbank)
    db.commit()
    assert issue_number(db, "invoice") != erste


# ---------------------------------------------------------------------------
# B: Leistungszeitraum -- Pflicht, Ende >= Beginn, PDF, Storno, Altbestand
# ---------------------------------------------------------------------------

def test_finalizing_without_period_is_409_with_reason_and_changes_nothing(threaded_db_session, router_test_client):
    db = threaded_db_session
    anlegen(db); db.commit()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    nummer = load_sequence(db, "invoice").next_value
    with pytest.raises(InvoiceBlocked, match=r"Der Leistungszeitraum fehlt \(Beginn und Ende\)"):
        finalize_and_send_invoice(db, invoice)
    update_invoice_header(db, db.get(Invoice, invoice.id), service_period_start=D(2026, 9, 1))
    client = router_test_client(db, invoices_router)
    antwort = client.post(f"/api/invoices/{invoice.id}/send")
    assert antwort.status_code == 409 and "Der Leistungszeitraum fehlt (Ende)" in antwort.json()["detail"]
    assert client.get(f"/api/invoices/{invoice.id}").json()["finalize_block"].startswith("Der Leistungszeitraum fehlt (Ende)")
    db.expire_all()
    assert (db.get(Invoice, invoice.id).status, db.get(Invoice, invoice.id).invoice_number) == ("entwurf", None)
    assert load_sequence(db, "invoice").next_value == nummer
    assert client.put(f"/api/invoices/{invoice.id}", json={"service_period_end": "2026-09-30"}).status_code == 200
    assert client.post(f"/api/invoices/{invoice.id}/send").status_code == 200


def test_end_before_start_is_rejected_also_for_one_side(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    with pytest.raises(ValueError, match="liegt vor dem Beginn"):
        update_invoice_header(db, invoice, service_period_start=D(2026, 9, 10), service_period_end=D(2026, 9, 9))
    db.rollback()
    update_invoice_header(db, db.get(Invoice, invoice.id), service_period_start=D(2026, 9, 10), service_period_end=D(2026, 9, 12))
    client = router_test_client(db, invoices_router)
    antwort = client.put(f"/api/invoices/{invoice.id}", json={"service_period_end": "2026-09-01"})
    assert antwort.status_code == 400 and "liegt vor dem Beginn" in antwort.json()["detail"]
    db.expire_all()
    assert (db.get(Invoice, invoice.id).service_period_start, db.get(Invoice, invoice.id).service_period_end) == (
        D(2026, 9, 10), D(2026, 9, 12))


def test_end_before_start_is_rejected_at_finalizing():
    """An der Speicherprüfung vorbei (z. B. von Hand in der Datenbank) -- das Festschreiben prüft noch einmal."""
    db = _db()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    invoice.service_period_start, invoice.service_period_end = D(2026, 9, 10), D(2026, 9, 1)
    db.commit()
    with pytest.raises(InvoiceBlocked, match=r"Das Ende des Leistungszeitraums \(01.09.2026\) liegt vor dem Beginn"):
        finalize_and_send_invoice(db, invoice)
    assert db.get(Invoice, invoice.id).status == "entwurf"


@pytest.mark.parametrize("start, end, text", [
    (D(2026, 9, 1), D(2026, 9, 30), b"Leistungszeitraum: 01.09.2026 bis 30.09.2026"),
    (D(2026, 9, 8), D(2026, 9, 8), b"Leistungsdatum: 08.09.2026"),
])
def test_period_is_on_the_pdf(start, end, text):
    db = _db()
    order, _ = make_order_with_item(db)
    invoice = finalize_and_send_invoice(db, mit_zeitraum(db, create_schlussrechnung(db, order), start, end))
    assert text in _extract_pdf_text(build_invoice_pdf(db, invoice))


def test_storno_takes_the_period_of_the_cancelled_invoice():
    db = _db()
    order, _ = make_order_with_item(db)
    original = finalize_and_send_invoice(db, mit_zeitraum(db, create_schlussrechnung(db, order), D(2026, 8, 3), D(2026, 8, 28)))
    storno = create_storno_draft(db, original)
    assert (storno.service_period_start, storno.service_period_end) == (D(2026, 8, 3), D(2026, 8, 28))
    assert finalize_and_send_invoice(db, storno).status == "versendet"


def test_legacy_invoice_without_period_stays_and_its_storno_needs_one():
    db = _db()
    order, _ = make_order_with_item(db)
    alt = Invoice(order_id=order.id, invoice_type="schluss", status="versendet", invoice_number="R-2026-0001",
                  customer_name="K", vat_rate=Decimal("19"))  # vor 1.8.74 festgeschrieben
    db.add(alt); db.commit()
    data = invoice_to_dict(alt)
    assert (data["service_period_start"], data["service_period_text"], data["service_period_proposal"]) == (None, None, None)
    assert b"Leistungs" not in _extract_pdf_text(build_invoice_pdf(db, alt))
    with pytest.raises(ValueError, match="Nur Rechnungen im Entwurf"):
        update_invoice_header(db, alt, service_period_start=D(2026, 9, 1))
    db.rollback()
    storno = create_storno_draft(db, db.get(Invoice, alt.id))
    assert (storno.service_period_start, storno.service_period_end) == (None, None)
    assert invoice_to_dict(storno)["service_period_proposal"]["source"].startswith(
        "Die stornierte Rechnung R-2026-0001 hat keinen Leistungszeitraum")
    with pytest.raises(InvoiceBlocked, match="Leistungszeitraum fehlt"):
        finalize_and_send_invoice(db, storno)


# ---------------------------------------------------------------------------
# B: Vorschlag je Rechnungsart -- mit Quelle, nie still eingetragen
# ---------------------------------------------------------------------------

def _buchung(db, order, tag, *, entry_type="site", status="booked", hours="8"):
    employee = db.scalar(select(Employee).limit(1))
    if employee is None:
        employee = Employee(first_name="Mona", last_name="Monteurin", active=True)
        db.add(employee); db.flush()
    db.add(TimeEntry(employee_id=employee.id, project_id=order.project_id, order_id=order.id, work_date=tag,
                     entry_type=entry_type, status=status, hours=Decimal(hours)))
    db.commit()


def _vorschlag(db, invoice):
    p = proposal(db, invoice)
    return p.start, p.end, p.source


def test_without_time_entries_the_planned_period_is_proposed():
    db = _db()
    order, _ = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    start, end, source = _vorschlag(db, invoice)
    assert (start, end) == (None, None) and "kein geplanter Zeitraum" in source
    order = db.get(Order, order.id)
    order.execution_start, order.execution_end = D(2026, 9, 7), D(2026, 9, 18)
    db.commit()
    assert _vorschlag(db, invoice) == (D(2026, 9, 7), D(2026, 9, 18),
                                       "Keine Zeitbuchungen am Auftrag. Geplanter Zeitraum des Auftrags.")
    order.execution_end = None
    db.commit()
    start, end, source = _vorschlag(db, invoice)
    assert (start, end) == (D(2026, 9, 7), None) and "(nur Beginn geplant)" in source


def test_progress_invoices_take_entries_after_the_previous_period():
    db = _db()
    order, _ = make_order_with_item(db)
    for tag in (D(2026, 9, 1), D(2026, 9, 5), D(2026, 9, 20)):
        _buchung(db, order, tag)
    _buchung(db, order, D(2026, 8, 30), entry_type="weather_winter")  # Schlechtwetter zählt nicht
    _buchung(db, order, D(2026, 8, 29), status="running", hours="0")   # laufend zählt nicht
    erster = create_abschlag_leistungsstand(db, order)
    assert _vorschlag(db, erster) == (D(2026, 9, 1), D(2026, 9, 20),
                                      "Erste bis letzte Zeitbuchung des Auftrags (3 Zeitbuchungen).")
    update_invoice_item(db, erster, erster.items[0], ist_quantity=Decimal("40"))
    erster = finalize_and_send_invoice(db, mit_zeitraum(db, erster, D(2026, 9, 1), D(2026, 9, 5)))
    _buchung(db, order, D(2026, 9, 10))
    zweiter = create_abschlag_leistungsstand(db, db.get(Order, order.id))
    assert _vorschlag(db, zweiter) == (D(2026, 9, 10), D(2026, 9, 20),
                                       f"Erste bis letzte Zeitbuchung nach dem Leistungszeitraum von {erster.invoice_number} "
                                       "(bis 05.09.2026) (2 Zeitbuchungen).")


def test_progress_invoice_without_new_entries_has_no_proposal_and_cancelled_ones_do_not_count():
    db = _db()
    order, _ = make_order_with_item(db)
    _buchung(db, order, D(2026, 9, 3))
    erster = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, erster, erster.items[0], ist_quantity=Decimal("40"))
    erster = finalize_and_send_invoice(db, mit_zeitraum(db, erster, D(2026, 9, 1), D(2026, 9, 3)))
    zweiter = create_abschlag_leistungsstand(db, db.get(Order, order.id))
    start, end, source = _vorschlag(db, zweiter)
    assert (start, end) == (None, None) and source.startswith(f"Keine Zeitbuchung nach dem Leistungszeitraum von "
                                                              f"{erster.invoice_number}")
    finalize_and_send_invoice(db, create_storno_draft(db, db.get(Invoice, erster.id)))  # übernimmt den Zeitraum
    assert _vorschlag(db, db.get(Invoice, zweiter.id))[:2] == (D(2026, 9, 3), D(2026, 9, 3))


def _abnahme(db, order, tag, *, result="abgenommen", discarded=False):
    from datetime import datetime
    db.add(OrderAcceptance(order_id=order.id, kind="formlos", accepted_on=tag, scope="gesamt", result=result,
                           declared_by="auftraggeber", declared_by_name="Herr Klar", content_sha256="0" * 64,
                           checksum_format=1, discarded_at=datetime(2026, 10, 1) if discarded else None))
    db.commit()


def test_final_invoice_runs_from_first_entry_to_the_acceptance_or_the_last_entry():
    db = _db()
    order, _ = make_order_with_item(db)
    for tag in (D(2026, 9, 2), D(2026, 9, 16)):
        _buchung(db, order, tag)
    schluss = create_schlussrechnung(db, order)
    assert _vorschlag(db, schluss) == (D(2026, 9, 2), D(2026, 9, 16),
                                       "Erste bis letzte Zeitbuchung des Auftrags (keine Abnahme), 2 Zeitbuchungen.")
    _abnahme(db, order, D(2026, 9, 30), result="verweigert")
    _abnahme(db, order, D(2026, 10, 2), discarded=True)
    assert _vorschlag(db, schluss)[:2] == (D(2026, 9, 2), D(2026, 9, 16))
    _abnahme(db, order, D(2026, 9, 25))
    assert _vorschlag(db, schluss) == (D(2026, 9, 2), D(2026, 9, 25),
                                       "Erste Zeitbuchung des Auftrags bis zur Abnahme am 25.09.2026.")


def test_time_based_invoice_proposes_the_billed_entries_and_ignores_later_ones():
    db = _db()
    order, _ = make_order_with_item(db)
    for tag in (D(2026, 9, 2), D(2026, 9, 4)):
        _buchung(db, order, tag)
    aufwand = create_invoice_from_time_entries(db, order, list_entries(db, order_id=order.id, limit=None), [])
    assert (aufwand.billed_work_from, aufwand.billed_work_to) == (D(2026, 9, 2), D(2026, 9, 4))
    _buchung(db, order, D(2026, 9, 20))  # später gebucht, nicht in dieser Rechnung
    assert _vorschlag(db, db.get(Invoice, aufwand.id)) == (D(2026, 9, 2), D(2026, 9, 4),
                                                           "Erste bis letzte abgerechnete Zeitbuchung dieser Rechnung.")


def test_proposal_is_never_stored_and_taking_it_is_a_put(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    _buchung(db, order, D(2026, 9, 2))
    schluss = create_schlussrechnung(db, order)
    client = router_test_client(db, invoices_router)
    data = client.get(f"/api/invoices/{schluss.id}").json()
    assert data["service_period_proposal"] == {"start": "2026-09-02", "end": "2026-09-02", "source": data[
        "service_period_proposal"]["source"]}
    assert (data["service_period_start"], data["service_period_end"]) == (None, None)
    db.expire_all()
    assert db.get(Invoice, schluss.id).service_period_start is None  # nichts still eingetragen
    p = data["service_period_proposal"]
    nach = client.put(f"/api/invoices/{schluss.id}", json={"service_period_start": p["start"], "service_period_end": p["end"]})
    assert nach.json()["service_period_text"] == "Leistungsdatum: 02.09.2026"
    assert client.post(f"/api/invoices/{schluss.id}/send").json()["service_period_proposal"] is None


def test_reminders_and_helper_paths_still_work():
    """Mahnung zu einer Rechnung mit Zeitraum (Testhelfer festschreiben())."""
    db = _db()
    invoice = make_sent_overdue_invoice(db)
    assert invoice.service_period_start is not None
    assert finalize_and_send_reminder(db, create_reminder(db, invoice, 1)).status == "versendet"


def test_invoice_page_takes_the_proposal_only_by_click():
    from pathlib import Path

    html = (Path(__file__).resolve().parent.parent / "app" / "templates" / "invoice_detail.html").read_text(encoding="utf-8")
    assert "onclick=\"applyPeriodProposal()\"" in html and "async function applyPeriodProposal()" in html
    assert "JSON.stringify({[field]:value||null})" in html  # je Feld nur dieses Feld (Regel 22)
    assert "festschreiben" not in html


def test_helper_sets_a_period_like_the_click():
    db = _db()
    order, _ = make_order_with_item(db)
    invoice = festschreiben(db, create_schlussrechnung(db, order))
    assert invoice.service_period_start is not None and invoice.status == "versendet"
