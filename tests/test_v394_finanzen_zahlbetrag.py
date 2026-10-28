"""Version 1.8.91 -- Finanzen und Dashboard zählen nach der Schlussrechnung je Auftrag ihren Zahlbetrag (Nacharbeit R4c Punkt 1,
docs/archiv/befund-vor-echtbetrieb.md "Nacharbeiten R4c").

Nach der gültigen Schlussrechnung zählt je Auftrag nur noch ihr Zahlbetrag: positiv als offen, negativ als Guthaben. Die darin
abgezogenen Rechnungen zählen nicht mehr einzeln; an ihnen steht "enthalten in Schlussrechnung R-…" statt "teilweise bezahlt"
(app/final_dunning.py::overview(), an jeder Rechnungszeile als "overview").

Auftrag aus tests/test_v133_invoices.py: 100 m² × 50 € = 5.000 € netto, 5.950 € brutto."""

from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete

from app.berlin_time import berlin_today
from app.final_dunning import dunning_state, overview
from app.invoices import (
    create_abschlag_leistungsstand, create_schlussrechnung, create_storno_draft, invoice_overview_rows, invoice_to_dict,
    update_invoice_item,
)
from app.models import InvoiceDeduction
from app.payments import Line, book_payment, invoice_customer_id, payment_state
from app.routers.invoices import router as invoices_router
from app.routers.projects import router as projects_router
from tests.leistungszeitraum import festschreiben
from tests.test_v133_invoices import db_session, make_order_with_item

D = Decimal
HEUTE = berlin_today()
TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def _abschlag(db, order, ist):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return festschreiben(db, invoice)


def _schluss(db, order, ist=None):
    schluss = create_schlussrechnung(db, order)
    if ist is not None:
        update_invoice_item(db, schluss, schluss.items[0], ist_quantity=D(ist))
        db.refresh(schluss)
    return festschreiben(db, schluss)


def _zahlen(db, invoice, zahlung, einbehalt="0"):
    return book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D(zahlung), note=None,
                        lines=[Line(invoice.id, zahlung=D(zahlung), einbehalt=D(einbehalt))], user_name="Test")


def _ov(db, invoice):
    db.expire_all()
    return overview(payment_state(db, invoice), dunning_state(db, invoice))


def _kurz(row):
    return (row["state"], row["open"], row["retained"], row["credit"])


def _summen(rows):
    """Wie Finanzen und Dashboard rechnen: offene Rechnungen, offener Betrag, davon Einbehalt, Guthaben."""
    ovs = [r["overview"] for r in rows if r["overview"]]
    offen = [o for o in ovs if o["open"] > 0]
    return (len(offen), sum((o["open"] for o in offen), D("0")), sum((o["retained"] for o in offen), D("0")),
            sum((o["credit"] for o in ovs), D("0")))


# ---------------------------------------------------------------------------
# Zahlbetrag je Auftrag
# ---------------------------------------------------------------------------

def test_partly_paid_abschlag_is_contained_in_the_final_invoice_and_counts_only_there():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "40")  # 2.380
    _zahlen(db, abschlag, "1000")  # offen 1.380, teilweise bezahlt
    assert _ov(db, abschlag)["state"] == "teilweise_bezahlt"  # vor der Schlussrechnung je Rechnung
    schluss = _schluss(db, order)  # 3.570, Zahlbetrag 4.950
    row = _ov(db, abschlag)
    assert row["state"] == "enthalten" and row["state_label"] == f"enthalten in Schlussrechnung {schluss.invoice_number}"
    assert (row["open"], row["credit"], row["settled_in"]) == (D("0.00"), D("0.00"),
                                                              {"invoice_id": schluss.id, "invoice_number": schluss.invoice_number})
    assert payment_state(db, abschlag).state == "teilweise_bezahlt"  # der Zahlstand der Rechnung selbst bleibt
    assert _kurz(_ov(db, schluss)) == ("zahlbetrag_offen", D("4950.00"), D("0.00"), D("0.00"))
    assert _summen(invoice_overview_rows(db, [abschlag, schluss])) == (1, D("4950.00"), D("0.00"), D("0.00"))


def test_negative_rechnungsbetrag_with_open_abschlag_counts_the_positive_pay_amount():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "100")  # 5.950
    _zahlen(db, abschlag, "4000")  # offen 1.950
    schluss = _schluss(db, order, "80")  # −1.190, Zahlbetrag 760
    assert _ov(db, abschlag)["state"] == "enthalten"
    assert _kurz(_ov(db, schluss)) == ("zahlbetrag_offen", D("760.00"), D("0.00"), D("0.00"))
    # Bis 1.8.90 zählte Finanzen den Abschlag mit 1.950 € -- die Überzahlung stand nirgends dagegen (Nebenbefund 1 aus 1.8.89).
    assert _summen(invoice_overview_rows(db, [abschlag, schluss])) == (1, D("760.00"), D("0.00"), D("0.00"))


def test_negative_pay_amount_counts_as_credit_not_as_open():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "100")
    _zahlen(db, abschlag, "5000")  # offen 950
    schluss = _schluss(db, order, "80")  # −1.190 + 950 = −240
    assert _ov(db, abschlag)["state"] == "enthalten"  # bis 1.8.90 "teilweise bezahlt", offen 950
    row = _ov(db, schluss)
    assert _kurz(row) == ("guthaben", D("0.00"), D("0.00"), D("240.00")) and row["state_label"] == "Guthaben"
    assert row["credit"] == dunning_state(db, schluss).credit
    assert _summen(invoice_overview_rows(db, [abschlag, schluss])) == (0, D("0.00"), D("0.00"), D("240.00"))


def test_paid_abschlag_stays_paid_and_the_whole_overpayment_is_credit():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "100")
    _zahlen(db, abschlag, "5950")
    schluss = _schluss(db, order, "80")
    assert _kurz(_ov(db, abschlag)) == ("bezahlt", D("0.00"), D("0.00"), D("0.00"))
    assert _kurz(_ov(db, schluss)) == ("guthaben", D("0.00"), D("0.00"), D("1190.00"))


def test_overpayment_offset_by_the_open_abschlag_is_settled():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "100")
    _zahlen(db, abschlag, "4760")  # offen 1.190 = Überzahlung
    schluss = _schluss(db, order, "80")
    assert _ov(db, abschlag)["state"] == "enthalten"
    row = _ov(db, schluss)
    assert _kurz(row) == ("ausgeglichen", D("0.00"), D("0.00"), D("0.00")) and row["state_label"] == "ausgeglichen"


def test_retained_amounts_of_the_abschlag_and_of_the_final_invoice_count_as_retained():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "40")
    _zahlen(db, abschlag, "2000", einbehalt="380")  # Einbehalt offen 380
    schluss = _schluss(db, order)  # 3.570
    assert _ov(db, abschlag)["state"] == "enthalten"
    assert _kurz(_ov(db, schluss)) == ("zahlbetrag_offen", D("3950.00"), D("380.00"), D("0.00"))
    _zahlen(db, schluss, "3370", einbehalt="200")  # eigener Einbehalt 200
    assert _kurz(_ov(db, schluss)) == ("zahlbetrag_offen", D("580.00"), D("580.00"), D("0.00"))


def test_final_invoice_without_open_abschlag_shows_its_own_state():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "40")
    _zahlen(db, abschlag, "2380")
    schluss = _schluss(db, order)
    assert _kurz(_ov(db, schluss)) == ("offen", D("3570.00"), D("0.00"), D("0.00"))
    _zahlen(db, schluss, "570")
    assert _kurz(_ov(db, schluss)) == ("teilweise_bezahlt", D("3000.00"), D("0.00"), D("0.00"))
    _zahlen(db, schluss, "3000")
    assert _kurz(_ov(db, schluss)) == ("bezahlt", D("0.00"), D("0.00"), D("0.00"))


def test_after_the_storno_of_the_final_invoice_each_invoice_counts_again():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "40")
    _zahlen(db, abschlag, "1000")
    schluss = _schluss(db, order)
    festschreiben(db, create_storno_draft(db, schluss))
    assert _kurz(_ov(db, abschlag)) == ("teilweise_bezahlt", D("1380.00"), D("0.00"), D("0.00"))
    db.expire_all()
    assert _ov(db, schluss) is None  # storniert: zählt nicht


def test_final_invoice_from_before_1_8_85_without_deductions_keeps_counting_per_invoice():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "40")
    _zahlen(db, abschlag, "1000")
    schluss = _schluss(db, order)
    db.execute(delete(InvoiceDeduction).where(InvoiceDeduction.invoice_id == schluss.id))  # an der ORM-Sperre vorbei
    db.commit()
    assert _kurz(_ov(db, abschlag)) == ("teilweise_bezahlt", D("1380.00"), D("0.00"), D("0.00"))


def test_drafts_and_storno_invoices_do_not_count():
    db = db_session()
    order, _ = make_order_with_item(db)
    entwurf = create_abschlag_leistungsstand(db, order)
    assert invoice_to_dict(entwurf)["overview"] is None
    abschlag = _abschlag(db, order, "40")
    storno = festschreiben(db, create_storno_draft(db, abschlag))
    db.expire_all()
    assert invoice_to_dict(storno)["overview"] is None and invoice_to_dict(abschlag)["overview"] is None


# ---------------------------------------------------------------------------
# API und Oberfläche
# ---------------------------------------------------------------------------

def test_routes_carry_the_overview(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "100")
    _zahlen(db, abschlag, "5000")
    schluss = _schluss(db, order, "80")
    client = router_test_client(db, invoices_router, projects_router)
    rows = {r["id"]: r for r in client.get("/api/invoices").json()}
    assert rows[abschlag.id]["overview"]["state_label"] == f"enthalten in Schlussrechnung {schluss.invoice_number}"
    assert (rows[schluss.id]["overview"]["state"], rows[schluss.id]["overview"]["credit"]) == ("guthaben", "240.00")
    project = {r["id"]: r for r in client.get(f"/api/projects/{order.project_id}/invoices").json()}
    assert project[abschlag.id]["overview"]["state"] == "enthalten"
    listed = {r["id"]: r for r in client.get(f"/api/orders/{order.id}/invoices").json()}
    assert listed[schluss.id]["overview"]["state"] == "guthaben"
    detail = client.get(f"/api/invoices/{abschlag.id}").json()
    assert detail["overview"]["state"] == "enthalten" and detail["payment"]["state"] == "teilweise_bezahlt"


def test_finanzen_and_dashboard_sum_the_overview_not_the_payment_state():
    """Finanzen und Dashboard rechnen offene Rechnungen, offenen Betrag und Guthaben aus overview -- nicht mehr aus dem Zahlstand
    je Rechnung (payment.open), der die abgezogenen Rechnungen einzeln zählte."""
    finanzen = (TEMPLATES / "finanzen.html").read_text(encoding="utf-8")
    dashboard = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    for name, text in (("finanzen", finanzen), ("dashboard", dashboard)):
        assert "payment.open" not in text and "payment.retained_open" not in text, name
    # Seit 1.8.93 (Nacharbeit R4c Punkt 3) kommt das Guthaben aus /api/payments/customer-balances (Rest und Überzahlung je Kunde,
    # test_v396_guthaben_des_kunden.py) -- vorher aus overview.credit der Rechnungszeilen (Erwartung geändert seit 1.8.93).
    for teil in ("Number(ov(i).open)", "Number(ov(i).retained)", "data-guthaben"):
        assert teil in finanzen, teil
    for teil in ("Number(i.overview.open", "data-guthaben"):
        assert teil in dashboard, teil
    # seit 1.9.129 eine Rechnungsliste für Akte und Finanzen (Befund D2) -- bis 1.9.128 je eine invoiceStatusText() in Auftrag und Projektmappe
    liste = (TEMPLATES / "_rechnungsliste.html").read_text(encoding="utf-8")
    assert "const o = r.overview;" in liste and "o.state === 'enthalten'" in liste
    for name in ("akte.html", "finanzen.html"):
        assert "rechnungsTabelleHtml(" in (TEMPLATES / name).read_text(encoding="utf-8"), name
