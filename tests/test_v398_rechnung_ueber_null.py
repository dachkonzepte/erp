"""Version 1.8.95 -- Rechnungen über 0 € oder weniger nur als Storno oder Endrechnung mit Abzügen (Vorgabe 1.8.95 Punkt 2,
Nebenbefund 2 aus 1.8.94).

Bis 1.8.94 musste nur ein Abschlag über 0 € liegen; eine Rechnung aus Aufwand (auch eine abschließende) und eine Schlussrechnung
ohne Abzüge gingen mit 0,00 € oder weniger durch -- mit Nummer, "Zahlbar rein netto bis …" und Zahlungsaufforderung im Schlusstext.
Seit 1.8.95 lehnt das Festschreiben jede Rechnung über 0 € oder weniger ab (409, app/invoices.py::amount_block_reason()), außer
einem Storno und einer Schlussrechnung, die festgeschriebene Rechnungen abzieht (final_breakdown()). Geprüft unter der Sperre der
Auftragszeile nach der Neuberechnung -- fällt der Abzug weg, während festgeschrieben wird, gilt die Regel für eine Rechnung ohne
Abzüge (Gleichzeitigkeit gegen PostgreSQL am Ende). Die Rechnungsseite zeigt den Grund statt "Finalisieren" (finalize_block)."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.invoices import (
    NOT_ABOVE_ZERO_TEXT, InvoiceBlocked, add_invoice_item, compute_invoice_totals, create_abschlag_leistungsstand,
    create_invoice_from_time_entries, create_schlussrechnung, create_storno_draft, finalize_and_send_invoice, invoice_to_dict,
    update_invoice_header, update_invoice_item,
)
from app.models import Invoice
from app.routers.invoices import router as invoices_router
from tests.leistungszeitraum import ZEITRAUM_JSON, festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

D = Decimal


def _aufwand(db, order, betrag):
    """Rechnung aus Aufwand mit einer Position zu `betrag` (Kleinmaterial ohne Preis daneben, wie test_v389)."""
    invoice = create_invoice_from_time_entries(
        db, order, [], [SimpleNamespace(material_id=None, description="Kleinmaterial", unit="Stk", quantity=D("1"))])
    add_invoice_item(db, invoice, short_text="Reparatur", long_text="", unit="Std.", unit_price=D(betrag), ist_quantity=D("1"))
    db.refresh(invoice)
    return invoice


def _abschlag(db, order, ist="100"):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return festschreiben(db, invoice)


def _schluss(db, order, ist):
    schluss = create_schlussrechnung(db, order)
    update_invoice_item(db, schluss, schluss.items[0], ist_quantity=D(ist))
    db.refresh(schluss)
    return schluss


def _abgelehnt(db, invoice) -> str:
    with pytest.raises(InvoiceBlocked) as exc:
        festschreiben(db, invoice)
    db.rollback()
    db.expire_all()
    stand = db.get(Invoice, invoice.id)
    assert stand.status == "entwurf" and stand.invoice_number is None  # nichts festgeschrieben, keine Nummer verbraucht
    return str(exc.value)


# --- Rechnung aus Aufwand -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("betrag", ["0", "-100"])
def test_effort_invoice_at_zero_or_below_is_refused(betrag):
    db = db_session()
    order, _ = make_order_with_item(db)
    aufwand = _aufwand(db, order, betrag)
    grund = _abgelehnt(db, aufwand)
    assert grund.startswith("Die Rechnung aus Aufwand lautet über ") and NOT_ABOVE_ZERO_TEXT in grund
    assert invoice_to_dict(db.get(Invoice, aufwand.id))["finalize_block"] == grund  # Grund statt Knopf auf der Rechnungsseite


def test_effort_invoice_above_zero_is_finalized():
    db = db_session()
    order, _ = make_order_with_item(db)
    aufwand = festschreiben(db, _aufwand(db, order, "0.01"))
    assert aufwand.status == "versendet" and compute_invoice_totals(aufwand)["gross_total"] == D("0.01")


def test_closing_effort_invoice_at_zero_is_refused():
    """Auch die abschließende Rechnung aus Aufwand am Auftrag nach Aufwand (Schnellauftrag) -- nicht nur die Schlussrechnung über
    0 € gibt es dort nicht."""
    db = db_session()
    order, _ = make_order_with_item(db, quantity=D("1"), unit_price=D("0"))
    aufwand = _aufwand(db, order, "0")
    update_invoice_header(db, aufwand, closes_order=True)
    assert "Rechnung aus Aufwand lautet über 0,00 €" in _abgelehnt(db, aufwand)


# --- Schlussrechnung ---------------------------------------------------------------------------------------------------

def test_final_invoice_without_deductions_at_zero_is_refused():
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = _schluss(db, order, "0")
    grund = _abgelehnt(db, schluss)
    assert grund.startswith("Die Schlussrechnung lautet über 0,00 €. Ohne abgezogene Rechnungen muss sie über 0 € liegen")


def test_final_invoice_with_deductions_may_be_zero_or_below():
    db = db_session()
    order, _ = make_order_with_item(db)
    _abschlag(db, order, "100")  # 5.950 € brutto abgeschlagen
    null = festschreiben(db, _schluss(db, order, "100"))  # Gesamtleistung = Abschlag -> 0,00 €
    assert null.status == "versendet" and compute_invoice_totals(null)["gross_total"] == D("0.00")

    db2 = db_session()
    order2, _ = make_order_with_item(db2)
    _abschlag(db2, order2, "100")
    negativ = festschreiben(db2, _schluss(db2, order2, "80"))
    assert compute_invoice_totals(negativ)["gross_total"] == D("-1190.00")


def test_final_invoice_without_deductions_above_zero_is_finalized():
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = festschreiben(db, _schluss(db, order, "1"))
    assert compute_invoice_totals(schluss)["gross_total"] == D("59.50")


# --- Storno -----------------------------------------------------------------------------------------------------------

def test_storno_may_be_negative_or_positive():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "100")
    storno = festschreiben(db, create_storno_draft(db, abschlag))
    assert compute_invoice_totals(storno)["gross_total"] == D("-5950.00")

    db2 = db_session()
    order2, _ = make_order_with_item(db2)
    _abschlag(db2, order2, "100")
    ueberzahlt = festschreiben(db2, _schluss(db2, order2, "80"))  # -1.190 €
    storno2 = festschreiben(db2, create_storno_draft(db2, ueberzahlt))
    assert compute_invoice_totals(storno2)["gross_total"] == D("1190.00")


# --- Angriffstests über die API ---------------------------------------------------------------------------------------

def test_api_refuses_to_finalize_a_zero_effort_invoice(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    aufwand = _aufwand(db, order, "0")
    client = router_test_client(db, invoices_router)
    assert client.put(f"/api/invoices/{aufwand.id}", json=ZEITRAUM_JSON).status_code == 200
    seite = client.get(f"/api/invoices/{aufwand.id}").json()
    assert seite["finalize_block"] and seite["finalize_block"].startswith("Die Rechnung aus Aufwand lautet über 0,00 €")
    resp = client.post(f"/api/invoices/{aufwand.id}/send")
    assert resp.status_code == 409 and resp.json()["detail"] == seite["finalize_block"]
    assert client.get(f"/api/invoices/{aufwand.id}").json()["invoice_number"] is None


def test_api_cannot_push_an_effort_invoice_to_zero_and_finalize_it(threaded_db_session, router_test_client):
    """Über die API eine positive Rechnung aus Aufwand auf 0 € drücken: eine negative Position lehnt schon das Schema ab (422),
    die Menge der einzigen Position mit Preis auf 0 gesetzt geht -- das Festschreiben danach nicht (409)."""
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    aufwand = _aufwand(db, order, "100")
    client = router_test_client(db, invoices_router)
    client.put(f"/api/invoices/{aufwand.id}", json=ZEITRAUM_JSON)
    negativ = client.post(f"/api/invoices/{aufwand.id}/items", json={"short_text": "Gutschrift", "long_text": "", "unit": "Std.",
                                                                    "unit_price": "-200", "ist_quantity": "1"})
    assert negativ.status_code == 422
    item = next(i for i in client.get(f"/api/invoices/{aufwand.id}").json()["items"] if i["short_text"] == "Reparatur")
    assert client.put(f"/api/invoices/{aufwand.id}/items/{item['id']}", json={"ist_quantity": "0"}).status_code == 200
    resp = client.post(f"/api/invoices/{aufwand.id}/send")
    assert resp.status_code == 409 and resp.json()["detail"].startswith("Die Rechnung aus Aufwand lautet über 0,00 €")
    assert client.get(f"/api/invoices/{aufwand.id}").json()["status"] == "entwurf"


def test_deduction_gone_before_finalizing_turns_the_rule_on():
    """Die Abzüge werden beim Festschreiben neu bestimmt: wird der abgezogene Abschlag vorher storniert, ist die Schlussrechnung
    über 0 € ohne Abzüge -- abgelehnt."""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "100")
    schluss = mit_zeitraum(db, _schluss(db, order, "0"))  # mit Abzug: −5.950 €, zulässig
    assert invoice_to_dict(schluss)["finalize_block"] is None
    festschreiben(db, create_storno_draft(db, abschlag))
    db.expire_all()
    schluss = db.get(Invoice, schluss.id)
    assert "Ohne abgezogene Rechnungen" in invoice_to_dict(schluss)["finalize_block"]
    assert "Ohne abgezogene Rechnungen" in _abgelehnt(db, schluss)


# --- Gleichzeitig gegen PostgreSQL -------------------------------------------------------------------------------------

def test_pg_final_invoice_waits_for_the_storno_of_its_deduction_and_is_refused(pg):
    """Der Storno des abgezogenen Abschlags hält die Sperre der Auftragszeile; das Festschreiben der Schlussrechnung (−5.950 € mit
    Abzug, 0 € ohne) wartet, rechnet danach neu -- ohne Abzug über 0,00 € -- und wird abgelehnt."""
    from app.models import Order

    Session, order_id = pg

    def vorbereiten(s):
        order = s.get(Order, order_id)
        abschlag = create_abschlag_leistungsstand(s, order)
        for item in abschlag.items:
            update_invoice_item(s, abschlag, item, ist_quantity=item.soll_quantity or D("1"))
        s.refresh(abschlag)
        abschlag = festschreiben(s, abschlag)
        schluss = create_schlussrechnung(s, s.get(Order, order_id))
        for item in schluss.items:
            update_invoice_item(s, schluss, item, ist_quantity=D("0"))
        s.refresh(schluss)
        mit_zeitraum(s, schluss)
        storno = mit_zeitraum(s, create_storno_draft(s, abschlag))
        assert invoice_to_dict(schluss)["finalize_block"] is None
        return storno.id, schluss.id

    storno_id, schluss_id = _vorbereiten(Session, vorbereiten)
    _, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, storno_id)).invoice_number,
                     lambda s: finalize_and_send_invoice(s, s.get(Invoice, schluss_id)).invoice_number)
    assert isinstance(second, InvoiceBlocked) and "Ohne abgezogene Rechnungen" in str(second), second
    assert _vorbereiten(Session, lambda s: (s.get(Invoice, schluss_id).status, s.get(Invoice, schluss_id).invoice_number)) == (
        "entwurf", None)
