"""Zahlungsstufe Z2b, Punkte 7-9 (seit 1.8.81, docs/archiv/zahlungen.md "Umsetzung 1.8.81"): Verzugszinsen mit Basiszinssatz,
Zahlungen auf Nebenforderungen nach § 367 BGB, Rechtstexte -- dazu "Vorweg" 1 (keine Gebühr neben der Pauschale) und 2 (Storno
nur ohne offene Nebenforderungen) und Festlegung 1.8.80 Nr. 2 (vor dem Ersetzen die gegengebuchten Nebenforderungen nennen).

Gleichzeitigkeit gegen PostgreSQL: tests/test_v384_verzugszinsen_pg.py; Migration: tests/test_v384_verzugszinsen_migration.py;
kein Test im Schema public: tests/test_v384_pg_nicht_public.py."""

import json
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest
from sqlalchemy import select, update

from app.berlin_time import berlin_today
from app.default_interest import (
    RateConflict, create_rate, delete_rate, half_year_of, interest_proposal, interest_start_day, next_half_year,
    update_rate,
)
from app.dunning_charges import (
    ChargeRejected, charge_rows, charges_in_force, confirm_default_start, discard_default_start, open_charges,
    reverse_charge,
)
from app.dunning_texts import update_text
from app.invoices import (
    InvoiceBlocked, create_abschlag_pauschal, create_storno_draft, finalize_and_send_invoice, invoice_customer,
)
from app.models import (
    BaseInterestRate, Customer, InvoiceCharge, InvoiceDefaultStart, Order, PaymentAllocation, Reminder,
)
from app.payments import (
    ChargeLine, Line, PaymentRejected, allocate_rest, book_payment, invoice_customer_id, open_invoices_of_customer,
    payment_rest, payment_state, proposal, reverse_allocation, reverse_payment, unallocated_by_customer,
)
from app.reminders import (
    amounts, compute_reminder_status, create_reminder, finalize_and_send_reminder, reminder_to_dict, send_reminder_email,
    set_reminder_charges,
)
from app.routers.dunning_charges import router as charges_router
from app.routers.invoices import router as invoices_router
from app.routers.payments import router as payments_router
from app.routers.reminders import router as reminders_router
from app.zugehoerigkeit import IdNichtGefunden
from tests.leistungszeitraum import festschreiben
from tests.mahnung import festschreiben_und_ablaufen, frist_ablaufen, zustellen
from tests.test_v133_invoices import make_order_with_item
from tests.test_v382_mahnwesen import _anzahl, _db, _geblockt, _pdf_text, _rechnung, _zahlen
from tests.test_v383_nebenforderungen import (
    AuftragsSperrBeobachter, _ein, _gewerbe, _welt_mit_verzug, _zweite_stufe_mit_verzug,
)

D = Decimal
HEUTE = berlin_today()


def _r(x: Decimal) -> Decimal:
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _saetze(db, von: date | None = None, bis: date | None = None, *, satz="1.27", geprueft=True):
    """Basiszinssätze (Testwerte, nicht die amtlichen) für jedes Halbjahr von..bis, geprüft oder nicht."""
    hy, last = half_year_of(von or HEUTE - timedelta(days=400)), half_year_of(bis or HEUTE)
    while hy <= last:
        if db.scalar(select(BaseInterestRate).where(BaseInterestRate.half_year_start == hy)) is None:
            db.add(BaseInterestRate(half_year_start=hy, rate_percent=D(satz), reviewed_on=HEUTE if geprueft else None,
                                    reviewed_by="Test-Kanzlei" if geprueft else None))
        hy = next_half_year(hy)
    db.commit()


def _im_verzug_seit(db, starts_on: date, *, basis="von_hand", gewerbe=True, suffix="0001"):
    """Schlussrechnung über 5.950,00 €, fällig am 01.02.2026, Verzugsbeginn starts_on (direkt eingetragen), eingeschaltet."""
    invoice = _rechnung(db, suffix, days_overdue=(HEUTE - date(2026, 2, 1)).days)
    if gewerbe:
        _gewerbe(db, invoice)
    _ein(db)
    db.add(InvoiceDefaultStart(invoice_id=invoice.id, starts_on=starts_on, basis=basis, created_by_name="Test"))
    db.commit()
    return invoice


def _charge(db, invoice, kind, amount, **kw):
    row = InvoiceCharge(invoice_id=invoice.id, kind=kind, amount=D(amount), created_by_name="Test", **kw)
    db.add(row)
    db.commit()
    return row


def _zweite_mit_zinsen(db, suffix="0001"):
    """Gewerbekunde, 1. Mahnung zugestellt vor acht Tagen, Verzug bestätigt (Zugang), Sätze 1,27 % geprüft: Entwurf der 2."""
    invoice, second = _zweite_stufe_mit_verzug(db, suffix)
    _saetze(db)
    return invoice, second


def _zinsen_8_tage() -> Decimal:
    return _r(D("5950.00") * D("10.27") * 8 / D(36500))


# ---------------------------------------------------------------------------
# Vorweg 1: keine Gebühr neben der Pauschale (§ 288 Abs. 5 S. 3 BGB)
# ---------------------------------------------------------------------------

def test_no_fee_proposal_once_the_flat_fee_is_booked():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True)
    festschreiben_und_ablaufen(db, second)
    third = create_reminder(db, invoice)
    assert third.fee_amount == 0  # kein Vorschlag aus der Stufe (15 €)
    fee = reminder_to_dict(third)["proposals"]["fee"]
    assert fee["amount"] == 0 and "durch die Pauschale abgegolten (§ 288 Abs. 5 S. 3 BGB)" in fee["block"], fee
    _geblockt(set_reminder_charges, db, third, fee_amount=D("15.00"), fee_accepted=True, flat_fee_accepted=False,
              grund="durch die Pauschale abgegolten")
    db.refresh(third)
    assert third.fee_accepted is False
    # am Entwurf vorbei übernommen (Altbestand, gleichzeitig): das Festschreiben lehnt ab, nichts geschrieben
    db.execute(update(Reminder).where(Reminder.id == third.id).values(fee_amount=D("15.00"), fee_accepted=True))
    db.commit()
    before = _anzahl(db, InvoiceCharge)
    _geblockt(finalize_and_send_reminder, db, third, grund="durch die Pauschale abgegolten")
    db.refresh(third)
    assert third.status == "entwurf" and _anzahl(db, InvoiceCharge) == before


def test_fee_and_flat_fee_not_in_the_same_reminder(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice, second = _zweite_stufe_mit_verzug(db)
    client = router_test_client(db, reminders_router)
    response = client.put(f"/api/reminders/{second.id}/charges", json={"fee_amount": "10.00", "fee_accepted": True,
                                                                      "flat_fee_accepted": True, "interest_accepted": False})
    assert response.status_code == 409 and "neben der Pauschale" in response.json()["detail"], response.text
    db.refresh(second)
    assert (second.fee_accepted, second.flat_fee_accepted) == (False, False)
    db.execute(update(Reminder).where(Reminder.id == second.id).values(fee_amount=D("10.00"), fee_accepted=True,
                                                                        flat_fee_accepted=True))
    db.commit()
    assert client.post(f"/api/reminders/{second.id}/send").status_code == 409
    assert _anzahl(db, InvoiceCharge) == 0


def test_the_flat_fee_of_a_reminder_to_be_replaced_does_not_block_the_fee():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True)
    finalize_and_send_reminder(db, second)  # nie hinausgegangen
    _zahlen(db, invoice, "100")
    replacement = create_reminder(db, invoice)
    assert replacement.fee_amount == D("10.00") and reminder_to_dict(replacement)["proposals"]["fee"]["block"] is None
    set_reminder_charges(db, replacement, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
    finalize_and_send_reminder(db, replacement)
    assert [c.kind for c in charges_in_force(db, [invoice.id])[invoice.id]] == ["gebuehr"]


# ---------------------------------------------------------------------------
# Vorweg 2: Storno nur ohne offene Nebenforderungen
# ---------------------------------------------------------------------------

def test_storno_needs_no_open_charges(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice = _rechnung(db)
    charge = _charge(db, invoice, "gebuehr", "10.00")
    _geblockt(create_storno_draft, db, invoice, grund="offene Nebenforderungen (Mahngebühr 10,00 €)")
    client = router_test_client(db, invoices_router)
    response = client.post(f"/api/invoices/{invoice.id}/storno")
    assert response.status_code == 409 and "gegenbuchen" in response.json()["detail"], response.text
    # Storno-Entwurf von vor der Nebenforderung: das Festschreiben prüft noch einmal
    other = _rechnung(db, "0002")
    early_storno = create_storno_draft(db, other)
    _charge(db, other, "pauschale", "40.00")
    with pytest.raises(InvoiceBlocked, match="offene Nebenforderungen"):
        festschreiben(db, early_storno)
    db.refresh(other)
    assert other.status == "versendet"
    reverse_charge(db, charge, reason="erlassen")
    festschreiben(db, create_storno_draft(db, invoice))
    db.refresh(invoice)
    assert invoice.status == "storniert"


def test_storno_waits_for_a_payment_on_a_charge_like_any_allocation():
    db = _db()
    invoice = _rechnung(db)
    charge = _charge(db, invoice, "gebuehr", "10.00")
    book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D("10.00"), note=None,
                 lines=[Line(invoice.id, charges=(ChargeLine(charge.id, D("10.00")),))])
    assert open_charges(db, invoice) == 0
    _geblockt(create_storno_draft, db, invoice, grund="Zahlung auf Nebenforderung 10,00 €")


# ---------------------------------------------------------------------------
# Festlegung 1.8.80 Nr. 2: vor dem Ersetzen die Nebenforderungen nennen, die gegengebucht werden
# ---------------------------------------------------------------------------

def test_replacing_names_the_charges_that_will_be_reversed():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
    finalize_and_send_reminder(db, second)  # nie hinausgegangen
    status = compute_reminder_status(db, invoice)
    assert status["pending"]["charges"] == [{"label": f"Mahngebühr (2. Mahnung {second.reminder_number})",
                                             "amount": D("10.00")}]
    _zahlen(db, invoice, "100")
    replacement = create_reminder(db, invoice)
    data = reminder_to_dict(replacement)
    assert data["replaces"] == [{"id": second.id, "reminder_number": second.reminder_number, "level": 2,
                                 "charges": [{"label": f"Mahngebühr (2. Mahnung {second.reminder_number})",
                                              "amount": D("10.00")}]}]
    finalize_and_send_reminder(db, replacement)
    assert reminder_to_dict(replacement)["replaces"] == []  # festgeschrieben: nichts mehr zu ersetzen


# ---------------------------------------------------------------------------
# Festlegung 1.8.80 Nr. 13: 30-Tage-Regel nur ohne Verbraucher (die Rechnung trägt keinen Hinweis nach § 286 Abs. 3 BGB)
# ---------------------------------------------------------------------------

def test_thirty_day_rule_only_for_customers_who_are_not_consumers():
    from app.dunning_charges import default_start_proposal
    from app.invoice_pdf import build_invoice_pdf
    from tests.test_v213_inspection_items import _extract_pdf_text

    db = _db()
    invoice = _rechnung(db)
    from tests.test_v383_nebenforderungen import _rechnung_zugestellt
    _rechnung_zugestellt(db, invoice, invoice.due_date - timedelta(days=40))
    assert invoice_customer(invoice).is_consumer is True
    proposal_ = default_start_proposal(db, invoice)
    assert proposal_["starts_on"] is None and "§ 286 Abs. 3 BGB" in proposal_["reason"], proposal_
    text = _extract_pdf_text(build_invoice_pdf(db, invoice)).decode("latin-1")
    assert "Verzug" not in text and "30 Tage" not in text  # kein Hinweis auf der Rechnung -- also bleibt es bei der Mahnung
    _gewerbe(db, invoice)
    assert default_start_proposal(db, invoice)["basis"] == "dreissig_tage"


# ---------------------------------------------------------------------------
# Punkt 7: Basiszinssatz
# ---------------------------------------------------------------------------

def test_base_rate_rules():
    db = _db()
    with pytest.raises(ValueError, match="1. Januar oder der 1. Juli"):
        create_rate(db, half_year_start=date(2026, 3, 1), rate_percent="1.27", reviewed_on=None, reviewed_by=None)
    with pytest.raises(ValueError, match="drei Nachkommastellen"):
        create_rate(db, half_year_start=date(2026, 1, 1), rate_percent="1.2345", reviewed_on=None, reviewed_by=None)
    with pytest.raises(ValueError, match="gemeinsam"):
        create_rate(db, half_year_start=date(2026, 1, 1), rate_percent="1.27", reviewed_on=HEUTE, reviewed_by=None)
    with pytest.raises(ValueError, match="Zukunft"):
        create_rate(db, half_year_start=date(2026, 1, 1), rate_percent="1.27", reviewed_on=HEUTE + timedelta(days=1),
                    reviewed_by="X")
    negative = create_rate(db, half_year_start=date(2020, 1, 1), rate_percent="-0.88", reviewed_on=HEUTE, reviewed_by="X")
    assert negative.rate_percent == D("-0.880")
    row = create_rate(db, half_year_start=date(2026, 1, 1), rate_percent="2.27", reviewed_on=HEUTE, reviewed_by="Kanzlei")
    with pytest.raises(RateConflict, match="schon einen Basiszinssatz"):
        create_rate(db, half_year_start=date(2026, 1, 1), rate_percent="2.27", reviewed_on=None, reviewed_by=None)
    with pytest.raises(RateConflict, match="geprüfter"):
        delete_rate(db, row)
    row, reset = update_rate(db, row, rate_percent="2.17", reviewed_on=HEUTE, reviewed_by="Kanzlei")
    assert reset and row.reviewed_on is None and row.reviewed_by is None  # neuer Satz, alte Prüfung gilt nicht
    delete_rate(db, row)
    assert _anzahl(db, BaseInterestRate) == 1


@pytest.mark.parametrize("role,status", [("admin", 200), ("buero_finanzen", 403), ("buero_auftrag", 403), ("field", 403)])
def test_only_admins_maintain_base_rates_and_legal_texts(threaded_db_session, router_test_client, role, status):
    db = threaded_db_session
    client = router_test_client(db, charges_router, role=role)
    body = {"half_year_start": "2026-07-01", "rate_percent": "1.27", "reviewed_on": None, "reviewed_by": None}
    assert client.post("/api/base-interest-rates", json=body).status_code == status
    text_body = {"body": "Testtext", "reviewed_on": None, "reviewed_by": None}
    assert client.put("/api/dunning-legal-texts/zinsen", json=text_body).status_code == status
    assert client.get("/api/base-interest-rates").status_code == (403 if role == "field" else 200)
    assert client.get("/api/dunning-legal-texts").status_code == (403 if role == "field" else 200)
    if status == 200:
        rate_id = db.scalar(select(BaseInterestRate.id))
        upd = {"rate_percent": "1.37", "reviewed_on": None, "reviewed_by": None}
        assert client.put(f"/api/base-interest-rates/{rate_id}", json=upd).status_code == 200
        assert client.put(f"/api/base-interest-rates/{rate_id}", json={"rate_percent": "1.37"}).status_code == 422
        assert client.post("/api/base-interest-rates", json=body).status_code == 409  # Halbjahr schon da
        assert client.post("/api/base-interest-rates", json={**body, "half_year_start": "2026-08-01"}).status_code == 422
        assert client.put("/api/dunning-legal-texts/unbekannt", json=text_body).status_code == 404
        assert client.delete(f"/api/base-interest-rates/{rate_id}").status_code == 200
        assert client.delete("/api/base-interest-rates/999999").status_code == 404


def test_rates_and_texts_routes_write_no_order_rows(router_test_client):
    db, invoice, second = _welt_mit_verzug()
    try:
        client = router_test_client(db, charges_router)
        with AuftragsSperrBeobachter(db) as beobachter:
            r1 = client.post("/api/base-interest-rates", json={"half_year_start": "2026-07-01", "rate_percent": "1.27",
                                                              "reviewed_on": None, "reviewed_by": None})
            r2 = client.put(f"/api/base-interest-rates/{r1.json()['id']}",
                            json={"rate_percent": "1.27", "reviewed_on": str(HEUTE), "reviewed_by": "X"})
            r3 = client.put("/api/dunning-legal-texts/verzug", json={"body": "T", "reviewed_on": None, "reviewed_by": None})
        assert (r1.status_code, r2.status_code, r3.status_code) == (200, 200, 200)
        assert beobachter.geschrieben == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Punkt 7: Zinsen
# ---------------------------------------------------------------------------

def test_interest_start_day_by_basis():
    def start(basis):
        return InvoiceDefaultStart(starts_on=date(2026, 3, 14), basis=basis)
    assert interest_start_day(start("mahnung")) == date(2026, 3, 15)  # Tag nach dem Zugang (§ 187 Abs. 1 BGB)
    assert interest_start_day(start("von_hand")) == date(2026, 3, 15)
    assert interest_start_day(start("dreissig_tage")) == date(2026, 3, 14)  # der 31. Tag selbst


def test_interest_exact_per_section_and_rounded_once_at_the_end():
    db = _db()
    invoice = _im_verzug_seit(db, date(2026, 3, 14))
    db.add_all([BaseInterestRate(half_year_start=date(2026, 1, 1), rate_percent=D("2.27"), reviewed_on=HEUTE, reviewed_by="T"),
                BaseInterestRate(half_year_start=date(2026, 7, 1), rate_percent=D("1.27"), reviewed_on=HEUTE, reviewed_by="T")])
    db.commit()
    _zahlen(db, invoice, "300", received_on=date(2026, 5, 1))
    p = interest_proposal(db, invoice, until=date(2026, 8, 10))
    assert p["block"] is None and (p["period_start"], p["period_end"], p["surcharge"]) == (
        date(2026, 3, 15), date(2026, 8, 10), D("9"))
    got = [(s["from"], s["to"], s["principal"], s["rate"], s["days"]) for s in p["sections"]]
    assert got == [(date(2026, 3, 15), date(2026, 4, 30), D("5950.00"), D("11.270"), 47),
                   (date(2026, 5, 1), date(2026, 6, 30), D("5650.00"), D("11.270"), 61),  # Eingangstag: zinsfrei
                   (date(2026, 7, 1), date(2026, 8, 10), D("5650.00"), D("10.270"), 41)]
    exact = [D("5950.00") * D("11.27") * 47 / D(36500), D("5650.00") * D("11.27") * 61 / D(36500),
             D("5650.00") * D("10.27") * 41 / D(36500)]
    assert [s["interest"] for s in p["sections"]] == exact  # je Abschnitt exakt, ungerundet
    assert p["amount"] == _r(sum(exact)) == D("257.94")
    assert sum(_r(e) for e in exact) == D("257.95")  # je Abschnitt gerundet wäre ein Cent mehr


def test_actual_days_divided_by_365_also_in_a_leap_year():
    db = _db()
    invoice = _im_verzug_seit(db, date(2028, 1, 31))
    db.add(BaseInterestRate(half_year_start=date(2028, 1, 1), rate_percent=D("1.00"), reviewed_on=HEUTE, reviewed_by="T"))
    db.commit()
    p = interest_proposal(db, invoice, until=date(2028, 3, 1))
    assert [(s["days"], s["principal"]) for s in p["sections"]] == [(30, D("5950.00"))]  # mit dem 29. Februar
    assert p["amount"] == _r(D("5950.00") * D("10.00") * 30 / D(36500))


def test_consumers_pay_5_others_9_points():
    db = _db()
    business = _im_verzug_seit(db, date(2026, 3, 14), suffix="0001")
    consumer = _im_verzug_seit(db, date(2026, 3, 14), gewerbe=False, suffix="0002")
    _saetze(db, date(2026, 1, 1), date(2026, 6, 30))
    assert interest_proposal(db, business, until=date(2026, 3, 24))["surcharge"] == 9
    p = interest_proposal(db, consumer, until=date(2026, 3, 24))
    assert p["surcharge"] == 5 and p["amount"] == _r(D("5950.00") * D("6.27") * 10 / D(36500))


def test_no_proposal_with_a_missing_or_unchecked_half_year():
    db = _db()
    invoice = _im_verzug_seit(db, date(2026, 3, 14))
    db.add(BaseInterestRate(half_year_start=date(2026, 1, 1), rate_percent=D("2.27"), reviewed_on=HEUTE, reviewed_by="T"))
    db.commit()
    p = interest_proposal(db, invoice, until=date(2026, 8, 10))
    assert p["amount"] is None and "kein Basiszinssatz für das Halbjahr 01.07.2026–31.12.2026" in p["block"], p
    db.add(BaseInterestRate(half_year_start=date(2026, 7, 1), rate_percent=D("1.27")))  # ungeprüft
    db.commit()
    p = interest_proposal(db, invoice, until=date(2026, 8, 10))
    assert p["amount"] is None and "nicht geprüft: das Halbjahr 01.07.2026–31.12.2026" in p["block"], p
    assert interest_proposal(db, invoice, until=date(2026, 6, 30))["amount"] is not None  # nur das erste Halbjahr


def test_no_interest_without_a_confirmed_default_or_before_it():
    db = _db()
    invoice = _rechnung(db)
    _ein(db)
    _saetze(db)
    assert "nicht bestätigt" in interest_proposal(db, invoice, until=HEUTE)["block"]
    db.add(InvoiceDefaultStart(invoice_id=invoice.id, starts_on=HEUTE, basis="mahnung", created_by_name="T"))
    db.commit()
    assert "erst ab dem" in interest_proposal(db, invoice, until=HEUTE)["block"]  # Zugang heute: Zinsen ab morgen


def test_interest_on_the_dunnable_amount_only():
    db = _db()
    invoice = _im_verzug_seit(db, date(2026, 3, 14))
    _saetze(db, date(2026, 1, 1), date(2026, 6, 30))
    _zahlen(db, invoice, "950", received_on=date(2026, 3, 1), einbehalt="500")  # Einbehalt wird nicht verzinst
    assert payment_state(db, invoice).dunnable == D("4500.00")
    p = interest_proposal(db, invoice, until=date(2026, 3, 24))
    assert [s["principal"] for s in p["sections"]] == [D("4500.00")]


def test_interest_from_the_day_after_the_reminder_reached_and_charged_when_finalized():
    db = _db()
    invoice, second = _zweite_mit_zinsen(db)
    data = reminder_to_dict(second)
    zi = data["proposals"]["interest"]
    assert zi["block"] is None and (zi["period_start"], zi["period_end"]) == (HEUTE - timedelta(days=7), HEUTE)
    assert zi["amount"] == _zinsen_8_tage() and "10,27 %" in zi["sections"][0]["text"]
    assert data["charges"] == [] and not data["interest_accepted"]  # nur ein Vorschlag
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False, interest_accepted=True)
    data = reminder_to_dict(second)
    assert [(c["kind"], c["amount"], c["new"]) for c in data["charges"]] == [("zinsen", _zinsen_8_tage(), True)]
    finalize_and_send_reminder(db, second)
    charge = db.scalar(select(InvoiceCharge).where(InvoiceCharge.kind == "zinsen"))
    assert (charge.amount, charge.period_start, charge.period_end, charge.reminder_id) == (
        _zinsen_8_tage(), HEUTE - timedelta(days=7), HEUTE, second.id)
    calc = json.loads(charge.calculation_json)
    assert calc["days_per_year"] == 365 and calc["surcharge"] == "9" and calc["amount"] == str(_zinsen_8_tage())
    breakdown = amounts(second)
    assert breakdown["format"] == 4 and breakdown["charges"][0]["sections"][0]["text"].startswith(  # seit 1.8.89 Format 4
        (HEUTE - timedelta(days=7)).strftime("%d.%m.%Y"))
    assert breakdown["total"] == breakdown["dunnable"] + _zinsen_8_tage()
    text = _pdf_text(db, second)
    assert "Verzugszinsen vom" in text and "10,27 %" in text
    assert payment_state(db, invoice).gross == D("5950.00")  # nie im Rechnungsbetrag


def test_not_accepted_interest_gives_no_charge_and_the_next_reminder_continues():
    db = _db()
    invoice, second = _zweite_mit_zinsen(db)
    finalize_and_send_reminder(db, second)
    assert _anzahl(db, InvoiceCharge) == 0
    frist_ablaufen(db, second)
    zustellen(db, second)
    third = create_reminder(db, invoice)
    zi = reminder_to_dict(third)["proposals"]["interest"]
    assert zi["period_start"] == HEUTE - timedelta(days=7)  # nicht berechnet: weiter ab dem ersten Zinstag
    set_reminder_charges(db, third, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False, interest_accepted=True)
    finalize_and_send_reminder(db, third)
    assert _anzahl(db, InvoiceCharge, InvoiceCharge.kind == "zinsen") == 1


def test_a_later_reminder_continues_after_the_last_computed_day_and_after_a_reversal_again():
    db = _db()
    invoice, second = _zweite_mit_zinsen(db)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False, interest_accepted=True)
    finalize_and_send_reminder(db, second)
    frist_ablaufen(db, second)
    zustellen(db, second)
    first_interest = db.scalar(select(InvoiceCharge).where(InvoiceCharge.kind == "zinsen"))
    third = create_reminder(db, invoice)
    zi = reminder_to_dict(third)["proposals"]["interest"]
    assert "schon berechnet" in zi["block"]  # bis heute schon berechnet
    reverse_charge(db, first_interest, reason="falsch berechnet")
    zi = reminder_to_dict(third)["proposals"]["interest"]
    assert zi["block"] is None and zi["period_start"] == HEUTE - timedelta(days=7)  # gegengebucht: wieder ab Zinsbeginn


def test_continuation_starts_the_day_after_the_last_interest_charge():
    db = _db()
    invoice = _im_verzug_seit(db, date(2026, 3, 14))
    _saetze(db, date(2026, 1, 1), date(2026, 6, 30))
    _charge(db, invoice, "zinsen", "12.00", period_start=date(2026, 3, 15), period_end=date(2026, 3, 31))
    p = interest_proposal(db, invoice, until=date(2026, 4, 10))
    assert (p["period_start"], p["continues_from"]) == (date(2026, 4, 1), date(2026, 3, 31))


def test_attacks_on_accepting_interest():
    db = _db()
    invoice = _rechnung(db)
    _gewerbe(db, invoice)
    _ein(db)
    first = festschreiben_und_ablaufen(db, create_reminder(db, invoice))
    second = create_reminder(db, invoice)
    # ohne Verzug
    _geblockt(set_reminder_charges, db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False,
              interest_accepted=True, grund="nicht bestätigt")
    confirm_default_start(db, invoice, starts_on=first.reminder_date, reason=None)
    # ohne Basiszinssatz
    _geblockt(set_reminder_charges, db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False,
              interest_accepted=True, grund="kein Basiszinssatz")
    _saetze(db)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False, interest_accepted=True)
    # inzwischen ist der Satz nicht mehr geprüft -> das Festschreiben lehnt ab, nichts geschrieben
    db.execute(update(BaseInterestRate).values(reviewed_on=None, reviewed_by=None))
    db.commit()
    _geblockt(finalize_and_send_reminder, db, second, grund="nicht mehr möglich")
    db.refresh(second)
    assert second.status == "entwurf" and _anzahl(db, InvoiceCharge) == 0 and second.reminder_number is None


def test_finalizing_recomputes_the_interest_under_the_lock():
    """Ändert sich zwischen Übernehmen und Festschreiben die Grundlage (hier der Verzugsbeginn, am ORM vorbei), bucht das
    Festschreiben die frische Berechnung bis zu seinem Tag -- nicht den Betrag von beim Übernehmen."""
    db = _db()
    invoice, second = _zweite_mit_zinsen(db)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False, interest_accepted=True)
    db.execute(update(InvoiceDefaultStart).values(starts_on=HEUTE - timedelta(days=4)))  # Verzug später (am ORM vorbei)
    db.commit()
    finalize_and_send_reminder(db, second)
    charge = db.scalar(select(InvoiceCharge).where(InvoiceCharge.kind == "zinsen"))
    assert charge.period_start == HEUTE - timedelta(days=3) and charge.amount == _r(D("5950.00") * D("10.27") * 4 / D(36500))


def test_discarding_the_default_is_blocked_while_interest_charges_hold():
    db = _db()
    invoice, second = _zweite_mit_zinsen(db)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False, interest_accepted=True)
    finalize_and_send_reminder(db, second)
    start = db.scalar(select(InvoiceDefaultStart))
    with pytest.raises(ChargeRejected, match="Verzugszinsen, die auf diesem Verzugsbeginn beruhen"):
        discard_default_start(db, start, reason="falsch")


def test_a_later_booked_payment_with_an_earlier_receipt_gives_a_recalculation_hint():
    db = _db()
    invoice = _im_verzug_seit(db, date(2026, 3, 14))
    _saetze(db, date(2026, 1, 1), date(2026, 6, 30))
    p = interest_proposal(db, invoice, until=date(2026, 3, 31))
    from app.default_interest import calculation_json
    _charge(db, invoice, "zinsen", str(p["amount"]), period_start=p["period_start"], period_end=p["period_end"],
            calculation_json=calculation_json(p))
    assert charge_rows(db, invoice)[0]["recalculated"] is None
    _zahlen(db, invoice, "2950", received_on=date(2026, 3, 20))  # später gebucht, Eingang davor
    row = charge_rows(db, invoice)[0]
    assert row["recalculated"] is not None and row["recalculated"] < p["amount"] and row["amount"] == p["amount"]


def test_switched_off_means_no_interest():
    db = _db()
    invoice, second = _zweite_mit_zinsen(db)
    _ein(db, False)
    assert reminder_to_dict(second)["proposals"] is None
    db.execute(update(Reminder).where(Reminder.id == second.id).values(interest_accepted=True))
    db.commit()
    finalize_and_send_reminder(db, second)
    assert _anzahl(db, InvoiceCharge) == 0 and second.interest_accepted is False


# ---------------------------------------------------------------------------
# Punkt 8: Zahlungen auf Nebenforderungen nach § 367 BGB
# ---------------------------------------------------------------------------

def _mit_nebenforderungen(db):
    invoice = _rechnung(db)
    _ein(db)
    zinsen = _charge(db, invoice, "zinsen", "12.34", period_start=HEUTE - timedelta(days=9), period_end=HEUTE - timedelta(days=2))
    gebuehr = _charge(db, invoice, "gebuehr", "10.00")
    pauschale = _charge(db, invoice, "pauschale", "40.00")
    return invoice, gebuehr, pauschale, zinsen


def _verteilung(p):
    line = p["lines"][0]
    return [(c["kind"], c["amount"]) for c in line["charges"]], line["zahlung"], p["rest"]


def test_proposal_costs_then_interest_then_the_invoice():
    db = _db()
    invoice, gebuehr, pauschale, zinsen = _mit_nebenforderungen(db)
    assert _verteilung(proposal(db, invoice, amount=D("30"), received_on=HEUTE)) == (
        [("gebuehr", D("10.00")), ("pauschale", D("20.00")), ("zinsen", D("0"))], D("0"), D("0"))
    assert _verteilung(proposal(db, invoice, amount=D("70"), received_on=HEUTE)) == (
        [("gebuehr", D("10.00")), ("pauschale", D("40.00")), ("zinsen", D("12.34"))], D("7.66"), D("0"))
    assert _verteilung(proposal(db, invoice, amount=D("6100"), received_on=HEUTE)) == (
        [("gebuehr", D("10.00")), ("pauschale", D("40.00")), ("zinsen", D("12.34"))], D("5950.00"), D("87.66"))


def test_proposal_over_several_invoices_takes_the_oldest_first():
    db = _db()
    order, _ = make_order_with_item(db)
    _ein(db)
    older = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("100")))  # 119,00 €
    newer = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=D("200")))  # 238,00 €
    old_fee = _charge(db, older, "gebuehr", "5.00")
    new_fee = _charge(db, newer, "gebuehr", "7.00")
    p = proposal(db, newer, amount=D("130"), received_on=HEUTE)
    rows = [(line["invoice_id"], [(c["charge_id"], c["amount"]) for c in line["charges"]], line["zahlung"])
            for line in p["lines"]]
    assert rows == [(older.id, [(old_fee.id, D("5.00"))], D("119.00")), (newer.id, [(new_fee.id, D("6.00"))], D("0"))]


def test_booking_on_charges_reduces_them_not_the_invoice_and_counts_against_the_payment():
    db = _db()
    invoice, gebuehr, pauschale, zinsen = _mit_nebenforderungen(db)
    payment = book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D("100"), note=None,
                           lines=[Line(invoice.id, zahlung=D("37.66"), charges=(
                               ChargeLine(gebuehr.id, D("10.00")), ChargeLine(pauschale.id, D("40.00")),
                               ChargeLine(zinsen.id, D("12.34"))))])
    assert payment_rest(db, payment) == 0
    assert payment_state(db, invoice).open == D("5912.34") and open_charges(db, invoice) == 0
    rows = {r["kind"]: (r["paid"], r["open"]) for r in charge_rows(db, invoice)}
    assert rows == {"gebuehr": (D("10.00"), D("0")), "pauschale": (D("40.00"), D("0")), "zinsen": (D("12.34"), D("0"))}
    assert _anzahl(db, PaymentAllocation, PaymentAllocation.kind == "nebenforderung") == 3
    assert unallocated_by_customer(db) == []
    # Zurücknehmen bucht die Zuordnungen auf Nebenforderungen mit gegen -- sie sind danach wieder offen
    reverse_payment(db, payment, reason="falsch erfasst")
    assert open_charges(db, invoice) == D("62.34") and payment_state(db, invoice).open == D("5950.00")


@pytest.mark.parametrize("fall", ["Nebenforderung einer anderen Rechnung", "Rechnung eines anderen Kunden", "unbekannt",
                                  "gegengebucht", "Gegenbuchung", "Überbuchung", "über die Zahlung"])
def test_attacks_on_payments_on_charges(fall):
    db = _db()
    invoice, gebuehr, pauschale, zinsen = _mit_nebenforderungen(db)
    stranger = _rechnung(db, "0003")  # anderer Kunde
    stranger_fee = _charge(db, stranger, "gebuehr", "10.00")
    amount, line_invoice = D("10.00"), invoice
    if fall == "Nebenforderung einer anderen Rechnung":  # Zeile auf die eigene Rechnung, Nebenforderung einer fremden
        charge_id, err, grund = stranger_fee.id, PaymentRejected, "gehört nicht zur Rechnung"
    elif fall == "Rechnung eines anderen Kunden":
        charge_id, line_invoice, err, grund = stranger_fee.id, stranger, PaymentRejected, "anderen Kunden als die Zahlung"
    elif fall == "unbekannt":
        charge_id, err, grund = 999999, IdNichtGefunden, "nicht gefunden"
    elif fall == "gegengebucht":
        reverse_charge(db, gebuehr, reason="erlassen")
        charge_id, err, grund = gebuehr.id, PaymentRejected, "gegengebucht"
    elif fall == "Gegenbuchung":
        counter = reverse_charge(db, gebuehr, reason="erlassen")
        charge_id, err, grund = counter.id, PaymentRejected, "Gegenbuchung"
    elif fall == "Überbuchung":
        charge_id, amount, err, grund = pauschale.id, D("40.01"), PaymentRejected, "Überbuchung der Nebenforderung"
    else:
        charge_id, amount, err, grund = pauschale.id, D("40.00"), PaymentRejected, "Überbuchung der Zahlung"
    before = (_anzahl(db, PaymentAllocation), _anzahl(db, InvoiceCharge))
    payment_amount = D("20.00") if fall == "über die Zahlung" else D("50.00")
    with pytest.raises(err, match=grund):
        book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=payment_amount, note=None,
                     lines=[Line(line_invoice.id, charges=(ChargeLine(charge_id, amount),))])
    assert (_anzahl(db, PaymentAllocation), _anzahl(db, InvoiceCharge)) == before


def test_the_same_charge_twice_in_one_booking_is_rejected():
    db = _db()
    invoice, gebuehr, _, _ = _mit_nebenforderungen(db)
    with pytest.raises(ValueError, match="höchstens einmal"):
        book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D("20"), note=None,
                     lines=[Line(invoice.id, charges=(ChargeLine(gebuehr.id, D("5")), ChargeLine(gebuehr.id, D("5"))))])


def test_a_charge_with_a_payment_is_not_reversed_until_the_allocation_is():
    db = _db()
    invoice, gebuehr, _, _ = _mit_nebenforderungen(db)
    payment = book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D("4.00"), note=None,
                           lines=[Line(invoice.id, charges=(ChargeLine(gebuehr.id, D("4.00")),))])
    with pytest.raises(ChargeRejected, match="Zahlung gebucht"):
        reverse_charge(db, gebuehr, reason="erlassen")
    allocation = db.scalar(select(PaymentAllocation).where(PaymentAllocation.charge_id == gebuehr.id))
    counter = reverse_allocation(db, allocation, reason="falsch zugeordnet")
    assert counter.charge_id == gebuehr.id and payment_rest(db, payment) == D("4.00")
    reverse_charge(db, gebuehr, reason="erlassen")


def test_replacing_a_reminder_whose_charge_is_paid_is_refused():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
    finalize_and_send_reminder(db, second)  # nie hinausgegangen
    fee = db.scalar(select(InvoiceCharge))
    book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D("110.00"), note=None,
                 lines=[Line(invoice.id, zahlung=D("100.00"), charges=(ChargeLine(fee.id, D("10.00")),))])
    replacement = create_reminder(db, invoice)
    before = _anzahl(db, InvoiceCharge)
    _geblockt(finalize_and_send_reminder, db, replacement, grund="lässt sich nicht ersetzen")
    db.refresh(second)
    db.refresh(replacement)
    assert second.replaced_by_id is None and replacement.status == "entwurf" and _anzahl(db, InvoiceCharge) == before


def test_a_finalized_reminder_does_not_go_out_once_a_charge_is_paid():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
    festschreiben_und_ablaufen(db, second)
    third = finalize_and_send_reminder(db, create_reminder(db, invoice))
    fee = db.scalar(select(InvoiceCharge))
    book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D("10.00"), note=None,
                 lines=[Line(invoice.id, charges=(ChargeLine(fee.id, D("10.00")),))])
    db.refresh(third)
    _geblockt(send_reminder_email, db, third, grund="nennt Nebenforderungen von 10,00 €", to_email="kunde@example.com")


def test_open_invoices_list_invoices_with_only_charges_open():
    db = _db()
    invoice, gebuehr, pauschale, zinsen = _mit_nebenforderungen(db)
    _zahlen(db, invoice, "5950.00")
    rows = open_invoices_of_customer(db, invoice_customer_id(invoice))
    assert [(r["invoice_id"], r["payment"]["open"], len(r["charges"])) for r in rows] == [(invoice.id, D("0"), 3)]
    p = proposal(db, invoice, amount=D("62.34"), received_on=HEUTE)
    assert _verteilung(p) == ([("gebuehr", D("10.00")), ("pauschale", D("40.00")), ("zinsen", D("12.34"))], D("0"), D("0"))


def test_routes_for_payments_on_charges(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice, gebuehr, pauschale, zinsen = _mit_nebenforderungen(db)
    client = router_test_client(db, payments_router, charges_router, user_id=5, display_name="Büro Test")
    p = client.get(f"/api/invoices/{invoice.id}/payment-proposal", params={"amount": "60.00", "received_on": str(HEUTE)})
    assert p.status_code == 200 and [c["amount"] for c in p.json()["lines"][0]["charges"]] == ["10.00", "40.00", "10.00"]
    body = {"customer_id": invoice_customer_id(invoice), "received_on": str(HEUTE), "amount": "60.00", "note": None,
            "lines": [{"invoice_id": invoice.id, "charges": [{"charge_id": gebuehr.id, "amount": "10.00"},
                                                              {"charge_id": pauschale.id, "amount": "40.00"},
                                                              {"charge_id": zinsen.id, "amount": "10.00"}]}]}
    response = client.post("/api/payments", json=body)
    assert response.status_code == 200, response.text
    kinds = sorted(a["kind_label"] for a in response.json()["allocations"])
    assert kinds[0].startswith("Zahlung auf Mahngebühr") and response.json()["rest"] == "0.00"
    view = client.get(f"/api/invoices/{invoice.id}/charges").json()
    assert view["open_total"] == "2.34" and view["paid_total"] == "60.00"
    bad = dict(body, lines=[{"invoice_id": invoice.id, "charges": [{"charge_id": 999999, "amount": "1.00"}]}])
    assert client.post("/api/payments", json=bad).status_code == 404
    bad = dict(body, lines=[{"invoice_id": invoice.id, "charges": [{"charge_id": zinsen.id, "amount": "-1.00"}]}])
    assert client.post("/api/payments", json=bad).status_code == 422
    bad = dict(body, lines=[{"invoice_id": invoice.id, "charges": [{"charge_id": zinsen.id, "amount": "5.00"}]}])
    assert client.post("/api/payments", json=bad).status_code == 409  # offen sind nur noch 2,34 €


# ---------------------------------------------------------------------------
# Punkt 9: Rechtstexte
# ---------------------------------------------------------------------------

def _texte(db, *, geprueft=True):
    when, by = (HEUTE, "Kanzlei Test") if geprueft else (None, None)
    update_text(db, "verzug", body="Verzug seit dem {verzugsbeginn} (Testtext Verzug).", reviewed_on=when, reviewed_by=by)
    update_text(db, "zinsen", body="Zinsen {prozentpunkte} Punkte vom {zinsen_von} bis {zinsen_bis} (Testtext Zinsen).",
                reviewed_on=when, reviewed_by=by)
    update_text(db, "pauschale", body="Pauschale {pauschale} (Testtext Pauschale).", reviewed_on=when, reviewed_by=by)


def test_legal_text_rules():
    db = _db()
    with pytest.raises(ValueError, match="gemeinsam"):
        update_text(db, "verzug", body="T", reviewed_on=HEUTE, reviewed_by=None)
    with pytest.raises(ValueError, match="Zukunft"):
        update_text(db, "verzug", body="T", reviewed_on=HEUTE + timedelta(days=1), reviewed_by="X")
    with pytest.raises(ValueError, match="Ohne Text"):
        update_text(db, "verzug", body=" ", reviewed_on=HEUTE, reviewed_by="X")
    with pytest.raises(ValueError, match="Unbekannter"):
        update_text(db, "anderes", body="T", reviewed_on=None, reviewed_by=None)
    text, reset = update_text(db, "verzug", body="Alt {verzugsbeginn}", reviewed_on=HEUTE, reviewed_by="X")
    assert text["reviewed"] and not reset
    text, reset = update_text(db, "verzug", body="Neu {verzugsbeginn} {tippfehler}", reviewed_on=HEUTE, reviewed_by="X")
    assert reset and not text["reviewed"] and text["unknown_placeholders"] == ["{tippfehler}"]


def test_unchecked_texts_are_not_printed_but_warned_about_checked_ones_are():
    db = _db()
    invoice, second = _zweite_mit_zinsen(db)
    _texte(db, geprueft=False)
    data = reminder_to_dict(second)
    assert data["legal_texts"] == [] and len(data["legal_text_warnings"]) == 1 and "Verzug" in data["legal_text_warnings"][0]
    assert "Testtext" not in _pdf_text(db, second)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True, interest_accepted=True)
    data = reminder_to_dict(second)
    assert [w.split("„")[1].split("“")[0] for w in data["legal_text_warnings"]] == [
        "Verzug", "Verzugszinsen", "Pauschale nach § 288 Abs. 5 BGB"]
    _texte(db)
    data = reminder_to_dict(second)
    assert data["legal_text_warnings"] == [] and [t["key"] for t in data["legal_texts"]] == ["verzug", "zinsen", "pauschale"]
    start = (HEUTE - timedelta(days=8)).strftime("%d.%m.%Y")
    assert data["legal_texts"][0]["text"] == f"Verzug seit dem {start} (Testtext Verzug)."
    assert data["legal_texts"][1]["text"] == (f"Zinsen 9 Punkte vom {(HEUTE - timedelta(days=7)).strftime('%d.%m.%Y')} bis "
                                              f"{HEUTE.strftime('%d.%m.%Y')} (Testtext Zinsen).")
    text = _pdf_text(db, second)
    assert "Testtext Verzug" in text and "Testtext Zinsen" in text and "Testtext Pauschale" in text


def test_texts_only_for_what_the_reminder_names():
    db = _db()
    _texte(db)
    invoice = _rechnung(db)
    _ein(db)
    draft = create_reminder(db, invoice)  # ohne Verzug, Zinsen und Pauschale
    assert reminder_to_dict(draft)["legal_texts"] == []
    _ein(db, False)
    invoice2, second = _zweite_mit_zinsen(db, "0002")
    _ein(db, False)
    assert reminder_to_dict(second)["legal_texts"] == []  # ausgeschaltet: keine Rechtstexte


def test_printed_texts_are_frozen_when_finalized():
    db = _db()
    invoice, second = _zweite_mit_zinsen(db)
    _texte(db)
    finalize_and_send_reminder(db, second)
    update_text(db, "verzug", body="Ganz neuer Text {verzugsbeginn}.", reviewed_on=HEUTE, reviewed_by="Kanzlei Test")
    db.refresh(second)
    assert [t["text"] for t in reminder_to_dict(second)["legal_texts"]][0].endswith("(Testtext Verzug).")
    text = _pdf_text(db, second)
    assert "Testtext Verzug" in text and "Ganz neuer Text" not in text


def test_new_charge_routes_need_the_interest_field_and_reject_the_field_role(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice, second = _zweite_mit_zinsen(db)
    client = router_test_client(db, reminders_router)
    body = {"fee_amount": "0", "fee_accepted": False, "flat_fee_accepted": False}
    assert client.put(f"/api/reminders/{second.id}/charges", json=body).status_code == 422
    assert client.put(f"/api/reminders/{second.id}/charges", json={**body, "interest_accepted": True}).status_code == 200
    field = router_test_client(db, reminders_router, charges_router, role="field")
    assert field.put(f"/api/reminders/{second.id}/charges", json={**body, "interest_accepted": True}).status_code == 403
    assert field.get("/api/base-interest-rates").status_code == 403


# ---------------------------------------------------------------------------
# Rundgang: die neuen schreibenden Wege schreiben nur unter der Sperre der Auftragszeile
# ---------------------------------------------------------------------------

def _zinsen_uebernommen(db, inv, r):
    _saetze(db)
    set_reminder_charges(db, r, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=False, interest_accepted=True)


def _zahlung_auf_nebenforderung(c, db, inv, r, charge):
    return c.post("/api/payments", json={"customer_id": invoice_customer_id(inv), "received_on": str(HEUTE),
                                         "amount": "10.00", "note": None,
                                         "lines": [{"invoice_id": inv.id, "charges": [{"charge_id": charge.id,
                                                                                       "amount": "10.00"}]}]})


# Je Weg: Vorbereitung (außerhalb des Beobachters) und der schreibende Aufruf.
RUNDGANG = {
    "Zinsen übernehmen": (lambda db, inv, r: _saetze(db), lambda c, db, inv, r, x: c.put(
        f"/api/reminders/{r.id}/charges", json={"fee_amount": "0", "fee_accepted": False, "flat_fee_accepted": False,
                                                "interest_accepted": True})),
    "festschreiben mit Zinsen": (_zinsen_uebernommen, lambda c, db, inv, r, x: c.post(f"/api/reminders/{r.id}/send")),
    "Zahlung auf eine Nebenforderung": (lambda db, inv, r: _charge(db, inv, "gebuehr", "10.00"), _zahlung_auf_nebenforderung),
}


class ZahlungsSperrBeobachter(AuftragsSperrBeobachter):
    TYPEN = AuftragsSperrBeobachter.TYPEN + (PaymentAllocation,)


@pytest.mark.parametrize("name", sorted(RUNDGANG))
def test_every_new_writing_way_writes_only_under_the_order_lock(name, router_test_client):
    db, invoice, second = _welt_mit_verzug()
    try:
        client = router_test_client(db, reminders_router, payments_router)
        vorbereiten, schreiben = RUNDGANG[name]
        extra = vorbereiten(db, invoice, second)
        with ZahlungsSperrBeobachter(db) as beobachter:
            antwort = schreiben(client, db, invoice, second, extra)
        assert antwort.status_code == 200, antwort.text
        assert beobachter.geschrieben >= 1 and beobachter.verstoesse == [], beobachter.verstoesse
    finally:
        db.close()
