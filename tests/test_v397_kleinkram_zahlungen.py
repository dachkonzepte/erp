"""Version 1.8.94 -- Kleinkram vor dem Abnahmetest (docs/archiv/befund-vor-echtbetrieb.md "Umsetzung 1.8.94").

1. Finanzen "Bezahlt (gesamt)" zieht die Zahlungsausgänge an Schlussrechnungen ab (overview.refunded, app/final_dunning.py).
2. Zahlbetrag genau 0 €: kein Schlusstext mit Zahlungsaufforderung, kein "zahlbar bis", stattdessen der feste Satz
   (app/invoices.py::nothing_due(), NOTHING_DUE_SENTENCE) -- im Entwurf live, beim Festschreiben eingefroren.
3. "Zahlung zurücknehmen" nur, wenn es geht; sonst der Grund (app/payments.py::reverse_block_reason()).
4. Zahlungsdialog und "Rest zuordnen": enthaltene Rechnungen gruppiert unter ihrer Schlussrechnung mit "enthalten in …"
   (app/payments.py::settled_in_map(), app/templates/_zahlung_gruppen.html).

Auftrag aus tests/test_v133_invoices.py: 100 m² × 50 € = 5.000 € netto. Abschlag nach Leistungsstand 100 m² = 5.950 € brutto; die
Schlussrechnung mit dem Aufmaß 80 m² lautet über −1.190 €, mit 100 m² über 0 €. Der JavaScript-Code der Vorlagen läuft in node.
Gleichzeitigkeit gegen PostgreSQL am Ende."""

import json
import re
from decimal import Decimal
from html.parser import HTMLParser

import pytest
from sqlalchemy import func, select

from app.berlin_time import berlin_today
from app.final_dunning import dunning_state
from app.invoice_pdf import build_invoice_pdf
from app.invoices import (
    NOTHING_DUE_SENTENCE, create_abschlag_leistungsstand, create_schlussrechnung, create_storno_draft, finalize_and_send_invoice,
    format_payment_terms_sentence, invoice_to_dict, nothing_due, payment_note, payment_note_sentence, update_invoice_header,
    update_invoice_item,
)
from app.models import Invoice, Order, Payment, PaymentAllocation
from app.payments import (
    Line, PaymentRejected, RefundLine, book_customer_refund, book_payment, book_refund, customer_payments, invoice_customer_id,
    open_invoices_of_customer, payment_to_dict, proposal, reverse_block_reason, reverse_payment,
)
from app.routers.invoices import router as invoices_router
from app.routers.payments import router as payments_router
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v314_dashboard_month_berlin import NODE, TEMPLATES, _node
from tests.test_v333_auswahl_inaktiv import js_funktion
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

D = Decimal
HEUTE = berlin_today()
AUFFORDERUNG = "Bitte überweisen Sie den Rechnungsbetrag"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")


def _abschlag(db, order, ist="100"):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return festschreiben(db, invoice)


def _zahlen(db, customer_id, betrag, invoice=None):
    lines = [Line(invoice.id, zahlung=D(betrag))] if invoice is not None else []
    return book_payment(db, customer_id=customer_id, received_on=HEUTE, amount=D(betrag), note=None, lines=lines, user_name="Test")


def _entwurf(db, order, ist="80"):
    schluss = create_schlussrechnung(db, order)
    update_invoice_item(db, schluss, schluss.items[0], ist_quantity=D(ist))
    db.refresh(schluss)
    return schluss


def _welt(db, gezahlt="4760", ist="80"):
    """Abschlag 5.950 € mit Zahlung gezahlt, Schlussrechnung als Entwurf mit dem Aufmaß ist. Vorgabe: Rechnungsbetrag −1.190 €,
    Abschlag noch 1.190 € offen -- Zahlbetrag 0 €."""
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order)
    kunde = invoice_customer_id(abschlag)
    payment = _zahlen(db, kunde, gezahlt, abschlag) if D(gezahlt) else None
    return order, abschlag, kunde, payment, _entwurf(db, order, ist)


def _text(db, invoice) -> str:
    """Text des PDFs aus dem Content-Stream -- Umlaute als Oktal, Suchtexte deshalb ohne Umlaute."""
    return _extract_pdf_text(build_invoice_pdf(db, invoice)).decode("latin-1").replace("\\(", "(").replace("\\)", ")")


def _zeile(html: str, name: str) -> str:
    return re.search(rf"^const {name}=.*$", html, re.M).group(0)


# ---------------------------------------------------------------------------
# 1. Finanzen: "Bezahlt (gesamt)" abzüglich der Zahlungsausgänge
# ---------------------------------------------------------------------------

def _ueberzahlung(db):
    """Abschlag 5.950 € bezahlt, Schlussrechnung −1.190 € festgeschrieben (Guthaben 1.190 €)."""
    order, abschlag, kunde, _, entwurf = _welt(db, gezahlt="5950")
    return abschlag, kunde, festschreiben(db, entwurf)


def test_overview_of_the_final_invoice_carries_what_was_refunded():
    db = db_session()
    abschlag, kunde, schluss = _ueberzahlung(db)
    assert invoice_to_dict(schluss)["overview"]["refunded"] == D("0.00")
    refund = book_refund(db, schluss, paid_on=HEUTE, amount=D("1000"), note=None)
    db.refresh(schluss)
    assert dunning_state(db, schluss).refunded == D("1000.00")
    assert invoice_to_dict(schluss)["overview"]["refunded"] == D("1000.00")
    assert invoice_to_dict(abschlag)["overview"]["refunded"] == D("0.00")
    reverse_payment(db, refund, reason="falsch gebucht")  # zurückgenommen: zählt nicht mehr
    db.refresh(schluss)
    assert invoice_to_dict(schluss)["overview"]["refunded"] == D("0.00")


def test_a_refund_from_the_rest_of_a_payment_does_not_touch_the_invoices():
    """Ein Rest zählte nie in "Bezahlt (gesamt)" -- seine Erstattung zieht dort nichts ab."""
    db = db_session()
    abschlag, kunde, schluss = _ueberzahlung(db)
    rest = _zahlen(db, kunde, "50")
    book_customer_refund(db, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("50"), payment_id=rest.id)])
    for invoice in (abschlag, schluss):
        db.refresh(invoice)
        assert invoice_to_dict(invoice)["overview"]["refunded"] == D("0.00")


def _finanzen_kennzahlen(invoices: list, balances: list) -> str:
    html = (TEMPLATES / "finanzen.html").read_text(encoding="utf-8")
    script = "\n".join([
        f"let allInvoices={json.dumps(invoices)},unallocated={json.dumps(balances)};",
        _zeile(html, "money"), _zeile(html, "ov"),
        "const out={};const document={getElementById:id=>({set innerHTML(v){out[id]=v}})};",
        js_funktion("finanzen.html", "renderMetrics"),
        "renderMetrics();process.stdout.write(JSON.stringify(out.metrics));",
    ])
    return _node(script, "Europe/Berlin")


def _kennzahl(html: str, attr: str) -> str | None:
    found = re.search(rf"<[^>]*{attr}[^>]*>([^<]*)<", html)
    return found.group(1).replace("\xa0", " ") if found else None


@nur_mit_node
def test_finanzen_paid_total_subtracts_the_refunds(threaded_db_session, router_test_client):
    db = threaded_db_session
    _, kunde, schluss = _ueberzahlung(db)
    client = router_test_client(db, invoices_router, payments_router)
    vorher = _finanzen_kennzahlen(client.get("/api/invoices").json(), client.get("/api/payments/customer-balances").json())
    assert (_kennzahl(vorher, "data-bezahlt"), _kennzahl(vorher, "data-erstattet")) == ("5.950,00 €", None)
    book_refund(db, schluss, paid_on=HEUTE, amount=D("1190"), note=None)
    nachher = _finanzen_kennzahlen(client.get("/api/invoices").json(), client.get("/api/payments/customer-balances").json())
    assert _kennzahl(nachher, "data-bezahlt") == "4.760,00 €"
    assert _kennzahl(nachher, "data-erstattet") == "abzüglich Erstattungen 1.190,00 €"
    # Eine Erstattung aus dem Rest einer Zahlung ändert die Kennzahl nicht.
    rest = _zahlen(db, kunde, "50")
    book_customer_refund(db, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("50"), payment_id=rest.id)])
    danach = _finanzen_kennzahlen(client.get("/api/invoices").json(), client.get("/api/payments/customer-balances").json())
    assert _kennzahl(danach, "data-bezahlt") == "4.760,00 €"


# ---------------------------------------------------------------------------
# 2. Zahlbetrag genau 0 €
# ---------------------------------------------------------------------------

def test_pay_amount_zero_replaces_terms_and_drops_the_payment_request():
    db = db_session()
    *_, entwurf = _welt(db)
    assert payment_note(entwurf)["pay_amount"] == D("0.00") and payment_note(entwurf)["refund_amount"] is None
    assert entwurf.outro_text.startswith(AUFFORDERUNG)  # gespeichert bleibt die Vorgabe
    data = invoice_to_dict(entwurf)
    assert (data["nothing_due"], data["nothing_due_outro"], data["printed_outro_text"]) == (True, True, None)
    assert data["payment_terms_sentence"] == NOTHING_DUE_SENTENCE == format_payment_terms_sentence(entwurf)
    text = _text(db, entwurf)
    assert "nichts mehr zu zahlen" in text and "Zahlung:" in text
    for weg in ("Zahlbar rein netto", "Rechnungsbetrag unter Angabe", "Zahlungsbedingungen:", "Erstattung"):
        assert weg not in text, weg
    if entwurf.payment_terms:
        assert entwurf.payment_terms not in text


def test_rechnungsbetrag_zero_with_everything_paid_is_also_nothing_due():
    db = db_session()
    *_, entwurf = _welt(db, gezahlt="5950", ist="100")
    assert payment_note(entwurf)["invoice_amount"] == D("0.00")
    assert nothing_due(entwurf) and format_payment_terms_sentence(entwurf) == NOTHING_DUE_SENTENCE


def test_schlusstext_2_stays_and_a_hand_written_schlusstext_is_dropped():
    db = db_session()
    *_, entwurf = _welt(db)
    update_invoice_header(db, entwurf, outro_text="Zahlen Sie bitte sofort.", outro_text_2="Ihr Dachdecker-Team")
    data = invoice_to_dict(entwurf)
    assert (data["printed_outro_text"], data["outro_text_2"]) == (None, "Ihr Dachdecker-Team")
    text = _text(db, entwurf)
    assert "Ihr Dachdecker-Team" in text and "Zahlen Sie bitte sofort" not in text
    schluss = festschreiben(db, entwurf)
    assert (schluss.outro_text, schluss.outro_text_2) == (None, "Ihr Dachdecker-Team")


@pytest.mark.parametrize("gezahlt, ist, satz", [
    ("4759", "80", "Zahlbar rein netto"),  # 1 € offen: Zahlbetrag 1 €
    ("5950", "80", "Den Erstattungsbetrag von 1.190,00"),  # Erstattung (1.8.90) bleibt
])
def test_any_other_pay_amount_keeps_its_sentence(gezahlt, ist, satz):
    db = db_session()
    *_, entwurf = _welt(db, gezahlt=gezahlt, ist=ist)
    data = invoice_to_dict(entwurf)
    assert not data["nothing_due"] and not data["nothing_due_outro"]
    assert data["payment_terms_sentence"].startswith(satz)


def test_other_invoices_are_never_nothing_due():
    db = db_session()
    order, abschlag, *_ = _welt(db)
    assert not nothing_due(abschlag) and not invoice_to_dict(abschlag)["nothing_due"]
    assert format_payment_terms_sentence(abschlag).startswith("Zahlbar rein netto")


def test_finalizing_freezes_it_and_the_fixed_pdf_carries_the_sentence():
    db = db_session()
    *_, entwurf = _welt(db)
    schluss = festschreiben(db, entwurf)
    assert schluss.outro_text is None
    data = invoice_to_dict(schluss)
    assert (data["nothing_due"], data["nothing_due_outro"], data["printed_outro_text"]) == (True, False, None)
    from app.models import SentDocument
    from app.sent_documents import read_sent_document
    text = _extract_pdf_text(read_sent_document(db.get(SentDocument, schluss.pdf_document_id))).decode("latin-1")
    assert "nichts mehr zu zahlen" in text and "Zahlbar rein netto" not in text and "Rechnungsbetrag unter Angabe" not in text


def test_pay_amount_reaching_zero_before_finalizing_counts_not_the_page():
    """Die Seite zeigte noch einen Zahlbetrag; bis zum Festschreiben geht die Zahlung auf den Abschlag ein -- maßgeblich ist der
    Zahlbetrag beim Festschreiben."""
    db = db_session()
    order, abschlag, kunde, _, entwurf = _welt(db, gezahlt="0")
    assert not invoice_to_dict(entwurf)["nothing_due"]
    _zahlen(db, kunde, "4760", abschlag)
    db.refresh(entwurf)
    assert festschreiben(db, entwurf).outro_text is None


def test_pay_amount_leaving_zero_before_finalizing_keeps_the_schlusstext():
    db = db_session()
    order, abschlag, kunde, payment, entwurf = _welt(db)
    assert invoice_to_dict(entwurf)["nothing_due_outro"]
    reverse_payment(db, payment, reason="Rücklastschrift")
    db.refresh(entwurf)
    schluss = festschreiben(db, entwurf)
    assert schluss.outro_text.startswith(AUFFORDERUNG) and not invoice_to_dict(schluss)["nothing_due"]


def test_a_later_payment_does_not_change_a_finalized_invoice():
    """Der Zahlungshinweis ist beim Festschreiben eingefroren -- eine spätere Zahlung auf den Abschlag macht aus einem Zahlbetrag
    über 0 € keinen "nichts mehr zu zahlen"."""
    db = db_session()
    order, abschlag, kunde, _, entwurf = _welt(db, gezahlt="0")
    schluss = festschreiben(db, entwurf)
    _zahlen(db, kunde, "4760", abschlag)
    db.refresh(schluss)
    assert not nothing_due(schluss) and schluss.outro_text.startswith(AUFFORDERUNG)


def test_email_sentence_says_nothing_is_left_to_pay():
    db = db_session()
    *_, entwurf = _welt(db)
    schluss = festschreiben(db, entwurf)
    assert payment_note_sentence(schluss) == (f"Laut Zahlungshinweis (Stand {HEUTE.strftime('%d.%m.%Y')}) ist nichts mehr zu "
                                              "zahlen (Zahlbetrag 0,00 €).")


def test_storno_of_such_a_final_invoice_is_not_nothing_due():
    db = db_session()
    *_, entwurf = _welt(db)
    storno = create_storno_draft(db, festschreiben(db, entwurf))
    assert not nothing_due(storno) and not invoice_to_dict(storno)["nothing_due"]


def test_router_carries_nothing_due(threaded_db_session, router_test_client):
    db = threaded_db_session
    *_, entwurf = _welt(db)
    data = router_test_client(db, invoices_router).get(f"/api/invoices/{entwurf.id}").json()
    assert (data["nothing_due"], data["nothing_due_outro"], data["payment_terms_sentence"]) == (True, True, NOTHING_DUE_SENTENCE)


# ---------------------------------------------------------------------------
# 3. "Zahlung zurücknehmen" nur, wenn es geht
# ---------------------------------------------------------------------------

def _rest_erstattet(db):
    order, abschlag, kunde, _, _ = _welt(db, gezahlt="0")
    rest = _zahlen(db, kunde, "50")
    refund = book_customer_refund(db, kunde, paid_on=HEUTE, note=None, lines=[RefundLine(D("20"), payment_id=rest.id)])
    return kunde, abschlag, rest, refund


def test_reverse_block_reason_names_the_refund_and_matches_the_rejection():
    db = db_session()
    kunde, abschlag, rest, refund = _rest_erstattet(db)
    reason = reverse_block_reason(db, rest)
    assert reason == (f"Aus dem Rest dieser Zahlung ist erstattet (20,00 €, Zahlungsausgang Nr. {refund.id}) -- erst den "
                      "Zahlungsausgang zurücknehmen.")
    assert payment_to_dict(db, rest)["reverse_block_reason"] == reason
    vorher = db.scalar(select(func.count()).select_from(Payment))
    with pytest.raises(PaymentRejected) as exc:
        reverse_payment(db, rest, reason="Versuch")
    assert str(exc.value) == reason and db.scalar(select(func.count()).select_from(Payment)) == vorher
    # Der Zahlungsausgang selbst lässt sich zurücknehmen -- danach auch die Zahlung.
    assert payment_to_dict(db, refund)["reverse_block_reason"] is None
    reverse_payment(db, refund, reason="falsch")
    assert reverse_block_reason(db, rest) is None and payment_to_dict(db, rest)["reverse_block_reason"] is None


def test_an_ordinary_payment_can_be_reversed_and_a_reversed_one_says_so():
    db = db_session()
    order, abschlag, kunde, payment, _ = _welt(db)
    assert payment_to_dict(db, payment)["reverse_block_reason"] is None
    reverse_payment(db, payment, reason="falsch")
    assert reverse_block_reason(db, payment) == "Diese Zahlung ist schon zurückgenommen."
    counter = db.scalar(select(Payment).where(Payment.reverses_payment_id == payment.id))
    assert reverse_block_reason(db, counter) == "Eine Gegenbuchung lässt sich nicht zurücknehmen."


def test_route_carries_the_reason_and_still_refuses(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde, abschlag, rest, refund = _rest_erstattet(db)
    client = router_test_client(db, payments_router)
    rows = {p["id"]: p for p in client.get(f"/api/customers/{kunde}/payments").json()["payments"]}
    assert rows[rest.id]["reverse_block_reason"].startswith("Aus dem Rest dieser Zahlung ist erstattet")
    assert rows[refund.id]["reverse_block_reason"] is None
    response = client.post(f"/api/payments/{rest.id}/reverse", json={"reason": "an der Oberfläche vorbei"})
    assert response.status_code == 409 and response.json()["detail"] == rows[rest.id]["reverse_block_reason"]


def _zahlungskarte(payment: dict, offene: list) -> str:
    html = (TEMPLATES / "customer.html").read_text(encoding="utf-8")
    script = "\n".join([
        _skripte_von("_zahlung_gruppen.html"), _zeile(html, "esc"), _zeile(html, "money"), _skripte_von("_zahl.html"), _zeile(html, "dt"),
        f"let customerOpenInvoices={json.dumps(offene)};",
        js_funktion("customer.html", "paymentCardHtml"),
        f"process.stdout.write(JSON.stringify(paymentCardHtml({json.dumps(payment)})));",
    ])
    return _node(script, "Europe/Berlin")


def _skripte_von(vorlage: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / vorlage).read_text(encoding="utf-8"), flags=re.S))


@nur_mit_node
def test_customer_page_shows_the_reason_instead_of_the_button(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde, abschlag, rest, refund = _rest_erstattet(db)
    client = router_test_client(db, payments_router)
    rows = {p["id"]: p for p in client.get(f"/api/customers/{kunde}/payments").json()["payments"]}
    offene = client.get(f"/api/customers/{kunde}/open-invoices").json()
    gesperrt = _zahlungskarte(rows[rest.id], offene)
    assert "Zahlung zurücknehmen" not in gesperrt and "data-zuruecknehmen-gesperrt" in gesperrt
    assert "erst den Zahlungsausgang zurücknehmen" in gesperrt
    frei = _zahlungskarte(rows[refund.id], offene)
    assert "Zahlung zurücknehmen</button>" in frei and "data-zuruecknehmen-gesperrt" not in frei


# ---------------------------------------------------------------------------
# 4. Enthaltene Rechnungen gruppiert unter ihrer Schlussrechnung
# ---------------------------------------------------------------------------

def _endrechnung_mit_offenem_abschlag(db):
    """Abschlag 5.950 €, davon 4.000 € gezahlt (1.950 € offen); Schlussrechnung mit 120 m² über 1.190 € -- Zahlbetrag 3.140 €."""
    order, abschlag, kunde, _, entwurf = _welt(db, gezahlt="4000", ist="120")
    return order, abschlag, kunde, festschreiben(db, entwurf)


def test_open_invoices_name_the_final_invoice_they_are_contained_in():
    db = db_session()
    order, abschlag, kunde, schluss = _endrechnung_mit_offenem_abschlag(db)
    rows = {r["invoice_id"]: r for r in open_invoices_of_customer(db, kunde)}
    assert rows[abschlag.id]["settled_in"] == {"invoice_id": schluss.id, "invoice_number": schluss.invoice_number}
    assert rows[schluss.id]["settled_in"] is None
    # Nach dem Storno der Schlussrechnung ist der Abschlag wieder eine eigene Rechnung.
    storno = festschreiben(db, create_storno_draft(db, schluss))
    assert storno.invoice_type == "storno"
    rows = {r["invoice_id"]: r for r in open_invoices_of_customer(db, kunde)}
    assert rows[abschlag.id]["settled_in"] is None and schluss.id not in rows


def test_proposal_lines_name_the_final_invoice(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, abschlag, kunde, schluss = _endrechnung_mit_offenem_abschlag(db)
    lines = {line["invoice_id"]: line for line in proposal(db, schluss, amount=D("100"), received_on=HEUTE)["lines"]}
    assert lines[abschlag.id]["settled_in"] == {"invoice_id": schluss.id, "invoice_number": schluss.invoice_number}
    assert lines[schluss.id]["settled_in"] is None
    client = router_test_client(db, payments_router)
    api_lines = client.get(f"/api/invoices/{schluss.id}/payment-proposal",
                           params={"amount": "100", "received_on": HEUTE.isoformat()}).json()["lines"]
    assert {line["invoice_id"]: line["settled_in"] for line in api_lines} == {
        abschlag.id: {"invoice_id": schluss.id, "invoice_number": schluss.invoice_number}, schluss.id: None}
    rows = client.get(f"/api/customers/{kunde}/open-invoices").json()
    assert {r["invoice_id"]: r["settled_in"] for r in rows}[abschlag.id]["invoice_id"] == schluss.id


def _gruppen(zeilen) -> list:
    return _node(_skripte_von("_zahlung_gruppen.html") + f"\nprocess.stdout.write(JSON.stringify(zahlungsGruppen({json.dumps(zeilen)})"
                 ".map(g=>[g.schluss&&g.schluss.invoice_id,g.zeilen.map(e=>[e.zeile.invoice_id,e.index])])));", "Europe/Berlin")


S = {"invoice_id": 9, "invoice_number": "R-9"}


@nur_mit_node
def test_helper_groups_contained_invoices_under_their_final_invoice():
    zeilen = [{"invoice_id": 1, "settled_in": S}, {"invoice_id": 5, "settled_in": None}, {"invoice_id": 2, "settled_in": S},
              {"invoice_id": 9, "settled_in": None}, {"invoice_id": 7, "settled_in": None}]
    # Die Gruppe steht an der Stelle ihrer ersten Zeile, die Schlussrechnung zuerst, der Index bleibt.
    assert _gruppen(zeilen) == [[9, [[9, 3], [1, 0], [2, 2]]], [None, [[5, 1]]], [None, [[7, 4]]]]


@nur_mit_node
def test_helper_groups_also_without_the_final_invoice_among_the_rows():
    """Eine Schlussrechnung ohne eigenen offenen Betrag (bezahlt, unter 0 €) fehlt unter den Zeilen -- die Gruppe steht trotzdem."""
    assert _gruppen([{"invoice_id": 1, "settled_in": S}, {"invoice_id": 2, "settled_in": S}]) == [[9, [[1, 0], [2, 1]]]]
    assert _gruppen([{"invoice_id": 3}, {"invoice_id": 4}]) == [[None, [[3, 0]]], [None, [[4, 1]]]]


class _Auswahl(HTMLParser):
    def __init__(self):
        super().__init__()
        self.eintraege, self._gruppe, self._option = [], None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "optgroup":
            self._gruppe = a.get("label")
        elif tag == "option":
            self._option = {"gruppe": self._gruppe, "wert": a.get("value"), "enthalten": "data-enthalten" in a, "text": ""}
            self.eintraege.append(self._option)

    def handle_data(self, data):
        if self._option is not None:
            self._option["text"] += data

    def handle_endtag(self, tag):
        if tag == "optgroup":
            self._gruppe = None
        elif tag == "option":
            self._option = None


def _optionen(zeilen) -> list[dict]:
    html = _node(_skripte_von("_zahlung_gruppen.html") + f"\nprocess.stdout.write(JSON.stringify(zahlungsOptionen("
                 f"{json.dumps(zeilen)},z=>z.invoice_number+' · offen '+z.open)));", "Europe/Berlin")
    parser = _Auswahl()
    parser.feed(html)
    return parser.eintraege


@nur_mit_node
def test_helper_options_use_an_optgroup_and_the_hint():
    zeilen = [{"invoice_id": 1, "invoice_number": "A-1", "open": "10", "settled_in": S},
              {"invoice_id": 9, "invoice_number": "R-9", "open": "5"}, {"invoice_id": 4, "invoice_number": "A-4", "open": "3"}]
    assert _optionen(zeilen) == [
        {"gruppe": "Schlussrechnung R-9", "wert": "9", "enthalten": False, "text": "R-9 · offen 5"},
        {"gruppe": "Schlussrechnung R-9", "wert": "1", "enthalten": True, "text": "A-1 · offen 10 · enthalten in Schlussrechnung R-9"},
        {"gruppe": None, "wert": "4", "enthalten": False, "text": "A-4 · offen 3"}]


@nur_mit_node
def test_helper_escapes_invoice_numbers():
    """Angriff: eine Rechnungsnummer mit HTML (das Format der Nummernkreise ist frei) erscheint als Text, nicht als Markup."""
    boese = {"invoice_id": 9, "invoice_number": '"><img src=x onerror=alert(1)>'}
    zeilen = [{"invoice_id": 1, "invoice_number": "<b>A</b>", "open": "1", "settled_in": boese}]
    html = _node(_skripte_von("_zahlung_gruppen.html") + f"\nprocess.stdout.write(JSON.stringify(zahlungsOptionen("
                 f"{json.dumps(zeilen)},z=>z.invoice_number)));", "Europe/Berlin")
    assert "<img" not in html and "<b>" not in html and "&lt;b&gt;A&lt;/b&gt;" in html


def _dialog(lines: list) -> str:
    html = (TEMPLATES / "invoice_detail.html").read_text(encoding="utf-8")
    script = "\n".join([
        _skripte_von("_zahlung_gruppen.html"), _zeile(html, "esc"), _zeile(html, "money"),
        "const dateDe=d=>d;const TYPE_LABELS={};",
        js_funktion("invoice_detail.html", "skontoHint"), js_funktion("invoice_detail.html", "payLineHtml"),
        js_funktion("invoice_detail.html", "payGroupHtml"),
        f"const payLines={json.dumps(lines)};",
        "process.stdout.write(JSON.stringify(zahlungsGruppen(payLines).map(g=>g.schluss?payGroupHtml(g)"
        ":payLineHtml(g.zeilen[0].zeile,g.zeilen[0].index)).join('')));",
    ])
    return _node(script, "Europe/Berlin")


@nur_mit_node
def test_payment_dialog_groups_and_marks_contained_invoices(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, abschlag, kunde, schluss = _endrechnung_mit_offenem_abschlag(db)
    client = router_test_client(db, payments_router)
    lines = client.get(f"/api/invoices/{schluss.id}/payment-proposal",
                       params={"amount": "100", "received_on": HEUTE.isoformat()}).json()["lines"]
    assert [line["invoice_id"] for line in lines] == [abschlag.id, schluss.id]  # Vorschlag: der ältere zuerst
    html = _dialog(lines)
    assert f'data-gruppe="{schluss.id}"' in html and "data-gruppe-kopf" in html
    # In der Gruppe steht die Schlussrechnung zuerst, der Abschlag darunter mit dem Hinweis -- jede Zeile mit ihrem Index.
    assert html.index(f'data-zeile="{schluss.id}"') < html.index(f'data-zeile="{abschlag.id}"')
    assert f"enthalten in Schlussrechnung {schluss.invoice_number}" in html
    assert "payEdit(0,'zahlung'" in html.split(f'data-zeile="{abschlag.id}"')[1].split("data-zeile=")[0]
    assert html.count("data-enthalten>") == 1


def test_templates_build_the_lists_with_the_helper():
    """Der Zahlungsdialog, seine Auswahl "weitere Rechnung" und "Rest zuordnen" in der Kundenakte nutzen den Helfer -- der Aufruf,
    nicht nur der Name (Kommentare zählen nicht)."""
    detail = (TEMPLATES / "invoice_detail.html").read_text(encoding="utf-8")
    kunde = (TEMPLATES / "customer.html").read_text(encoding="utf-8")
    for text in (detail, kunde):
        assert '{% include "_zahlung_gruppen.html" %}' in text
    assert "innerHTML=payLines.length?head+zahlungsGruppen(payLines).map(" in detail
    assert "'<option value=\"\">— Rechnung wählen … —</option>'+zahlungsOptionen(more," in detail
    assert "settled_in:o.settled_in||null" in detail
    assert "const opts=zahlungsOptionen(customerOpenInvoices.filter(" in kunde


def test_field_gets_none_of_it(threaded_db_session, router_test_client):
    """Angriff: die Monteurin liest weder offene Rechnungen, Vorschlag noch Zahlungen (mit dem Grund) und nimmt nichts zurück."""
    db = threaded_db_session
    kunde, abschlag, rest, refund = _rest_erstattet(db)
    client = router_test_client(db, payments_router, invoices_router, role="field")
    for url in (f"/api/customers/{kunde}/open-invoices", f"/api/customers/{kunde}/payments",
                f"/api/invoices/{abschlag.id}/payment-proposal?amount=1&received_on={HEUTE.isoformat()}"):
        assert client.get(url).status_code == 403, url
    assert client.post(f"/api/payments/{refund.id}/reverse", json={"reason": "x"}).status_code == 403
    assert db.scalar(select(func.count()).select_from(Payment).where(Payment.reverses_payment_id.is_not(None))) == 0


# ---------------------------------------------------------------------------
# PostgreSQL: gleichzeitig
# ---------------------------------------------------------------------------

def test_pg_finalizing_waits_for_the_payment_that_brings_the_pay_amount_to_zero(pg):
    """Die Zahlung auf den Abschlag hält die Sperre der Auftragszeile; das Festschreiben der Schlussrechnung wartet und friert den
    Zahlbetrag mit dieser Zahlung ein -- 0 €, also kein Schlusstext mit Zahlungsaufforderung."""
    Session, order_id = pg

    def vorbereiten(s):
        order = s.get(Order, order_id)
        abschlag = _abschlag(s, order, "10")  # 595
        schluss = _entwurf(s, s.get(Order, order_id), "8")  # Rechnungsbetrag −119, Abschlag offen 595: Zahlbetrag 476
        mit_zeitraum(s, schluss)
        return abschlag.id, schluss.id

    abschlag_id, schluss_id = _vorbereiten(Session, vorbereiten)

    def zahlen(s):
        abschlag = s.get(Invoice, abschlag_id)
        return _zahlen(s, invoice_customer_id(abschlag), "476", abschlag).id  # Abschlag noch 119 offen: Zahlbetrag 0

    def finalisieren(s):
        invoice = finalize_and_send_invoice(s, s.get(Invoice, schluss_id))
        return invoice.outro_text, str(payment_note(invoice)["pay_amount"])

    _, (outro, zahlbetrag) = _run(Session, zahlen, finalisieren)
    assert (outro, zahlbetrag) == (None, "0.00"), (outro, zahlbetrag)
