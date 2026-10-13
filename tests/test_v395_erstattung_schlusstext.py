"""Version 1.8.92 -- Schlusstext bei Erstattung (Nacharbeit R4c Punkt 2, docs/archiv/befund-vor-echtbetrieb.md "Nacharbeiten R4c").

Ist der Zahlbetrag einer Schlussrechnung negativ, entfällt die Zahlungsaufforderung im Schlusstext; stattdessen steht der Text für die
Erstattung aus den Einstellungen (Auswahlliste "Rechnungs-Schlusstexte bei Erstattung", Standard-Eintrag) -- im Entwurf live, beim
Festschreiben in outro_text eingefroren (app/invoices.py::refund_outro_text()).

Auftrag aus tests/test_v133_invoices.py: 100 m² × 50 € = 5.000 € netto. Abschlag nach Leistungsstand 100 m² = 5.950 € brutto; die
Schlussrechnung mit dem Aufmaß 80 m² lautet über −1.190 €. Gleichzeitigkeit gegen PostgreSQL am Ende."""

from decimal import Decimal

from sqlalchemy import select

from app.berlin_time import berlin_today
from app.invoice_pdf import build_invoice_pdf
from app.invoices import (
    REFUND_OUTRO_GROUP, create_abschlag_leistungsstand, create_schlussrechnung, create_storno_draft, finalize_and_send_invoice,
    invoice_to_dict, payment_note, refund_outro_text, update_invoice_header, update_invoice_item,
)
from app.models import Invoice, Order, SettingOption, SettingOptionGroup
from app.option_settings import DEFAULT_OPTION_GROUPS
from app.payments import Line, book_payment, invoice_customer_id, reverse_payment
from app.routers.invoices import router as invoices_router
from app.routers.settings import router as settings_router
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

D = Decimal
HEUTE = berlin_today()
STANDARD = DEFAULT_OPTION_GROUPS[REFUND_OUTRO_GROUP]["options"][0][2]
AUFFORDERUNG = "Bitte überweisen Sie den Rechnungsbetrag"


def _abschlag(db, order, ist="100"):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    db.refresh(invoice)
    return festschreiben(db, invoice)


def _zahlen(db, invoice, zahlung):
    return book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D(zahlung), note=None,
                        lines=[Line(invoice.id, zahlung=D(zahlung))], user_name="Test")


def _entwurf(db, order, ist="80"):
    schluss = create_schlussrechnung(db, order)
    update_invoice_item(db, schluss, schluss.items[0], ist_quantity=D(ist))
    db.refresh(schluss)
    return schluss


def _welt(db, gezahlt="5950"):
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order)
    payment = _zahlen(db, abschlag, gezahlt) if D(gezahlt) else None
    return order, abschlag, payment


def _text(db, invoice) -> str:
    """Text des PDFs aus dem Content-Stream -- Umlaute als Oktal, Suchtexte deshalb ohne Umlaute."""
    return _extract_pdf_text(build_invoice_pdf(db, invoice)).decode("latin-1").replace("\\(", "(").replace("\\)", ")")


def _option(db) -> SettingOption:
    group = db.scalar(select(SettingOptionGroup).where(SettingOptionGroup.group_key == REFUND_OUTRO_GROUP))
    return next(o for o in group.options if o.is_default)


# ---------------------------------------------------------------------------
# Entwurf: live
# ---------------------------------------------------------------------------

def test_the_option_group_is_created_at_start_with_a_default_text():
    db = db_session()  # Grunddaten wie beim Start (tests/conftest.py)
    assert _option(db).value == STANDARD and AUFFORDERUNG not in STANDARD


def test_draft_with_refund_prints_the_refund_text_instead_of_the_payment_request():
    db = db_session()
    order, _, _ = _welt(db)
    entwurf = _entwurf(db, order)
    assert entwurf.outro_text.startswith(AUFFORDERUNG)  # Vorgabe beim Anlegen bleibt gespeichert
    data = invoice_to_dict(entwurf)
    assert (data["refund_outro_text"], data["printed_outro_text"]) == (STANDARD, STANDARD)
    text = _text(db, entwurf)
    assert "Vielen Dank f" in text and "teilen Sie uns diese bitte" in text
    assert "Rechnungsbetrag unter Angabe" not in text


def test_positive_pay_amount_keeps_the_schlusstext_also_with_a_negative_rechnungsbetrag():
    db = db_session()
    order, _, _ = _welt(db, gezahlt="4000")  # Abschlag offen 1.950 -> Zahlbetrag 760
    entwurf = _entwurf(db, order)
    assert payment_note(entwurf)["refund_amount"] is None
    data = invoice_to_dict(entwurf)
    assert data["refund_outro_text"] is None and data["printed_outro_text"].startswith(AUFFORDERUNG)
    assert "Rechnungsbetrag unter Angabe" in _text(db, entwurf)


def test_other_invoices_are_untouched():
    db = db_session()
    order, abschlag, _ = _welt(db)
    data = invoice_to_dict(abschlag)
    assert data["refund_outro_text"] is None and data["printed_outro_text"] == abschlag.outro_text
    entwurf = create_abschlag_leistungsstand(db, order)  # Abschlag-Entwurf, kein Erstattungsbetrag
    assert refund_outro_text(entwurf) is None


def test_draft_follows_the_settings_and_the_pay_amount_live():
    db = db_session()
    order, _, payment = _welt(db)
    entwurf = _entwurf(db, order)
    option = _option(db)
    option.value = "Die Erstattung erfolgt auf Ihr Konto."
    db.commit()
    assert invoice_to_dict(entwurf)["printed_outro_text"] == "Die Erstattung erfolgt auf Ihr Konto."
    reverse_payment(db, payment, reason="falsch erfasst")  # Abschlag wieder offen: Zahlbetrag 4.760
    db.refresh(entwurf)
    assert invoice_to_dict(entwurf)["printed_outro_text"].startswith(AUFFORDERUNG)


def test_without_an_active_refund_text_the_invoice_has_no_schlusstext():
    db = db_session()
    order, _, _ = _welt(db)
    entwurf = _entwurf(db, order)
    _option(db).active = False
    db.commit()
    data = invoice_to_dict(entwurf)
    assert (data["refund_outro_text"], data["printed_outro_text"]) == ("", None)
    schluss = festschreiben(db, entwurf)
    assert schluss.outro_text is None and "Rechnungsbetrag unter Angabe" not in _text(db, schluss)


# ---------------------------------------------------------------------------
# Festschreiben: eingefroren
# ---------------------------------------------------------------------------

def test_finalizing_freezes_the_refund_text_as_schlusstext():
    db = db_session()
    order, _, _ = _welt(db)
    schluss = festschreiben(db, _entwurf(db, order))
    assert schluss.outro_text == STANDARD
    data = invoice_to_dict(schluss)
    assert (data["outro_text"], data["refund_outro_text"], data["printed_outro_text"]) == (STANDARD, None, STANDARD)
    _option(db).value = "Ein neuer Text."
    db.commit()
    db.refresh(schluss)
    assert invoice_to_dict(schluss)["printed_outro_text"] == STANDARD  # nachträglich geänderte Einstellung ändert nichts


def test_a_hand_written_schlusstext_is_replaced_but_schlusstext_2_stays():
    db = db_session()
    order, _, _ = _welt(db)
    entwurf = _entwurf(db, order)
    update_invoice_header(db, entwurf, outro_text="Zahlen Sie bitte sofort.", outro_text_2="Ihr Dachdecker-Team")
    schluss = festschreiben(db, entwurf)
    assert (schluss.outro_text, schluss.outro_text_2) == (STANDARD, "Ihr Dachdecker-Team")


def test_pay_amount_turning_negative_before_finalizing_takes_the_refund_text():
    """Die Seite zeigte einen positiven Zahlbetrag (Zahlungsaufforderung); bis zum Festschreiben geht die Zahlung auf den Abschlag
    ein -- maßgeblich ist der Zahlbetrag beim Festschreiben, nicht der Stand der Seite."""
    db = db_session()
    order, abschlag, _ = _welt(db, gezahlt="0")
    entwurf = _entwurf(db, order)
    assert invoice_to_dict(entwurf)["refund_outro_text"] is None
    _zahlen(db, abschlag, "5950")
    db.refresh(entwurf)
    assert festschreiben(db, entwurf).outro_text == STANDARD


def test_pay_amount_turning_positive_before_finalizing_keeps_the_own_schlusstext():
    db = db_session()
    order, _, payment = _welt(db)
    entwurf = _entwurf(db, order)
    assert invoice_to_dict(entwurf)["refund_outro_text"] == STANDARD
    reverse_payment(db, payment, reason="Rücklastschrift")
    db.refresh(entwurf)
    assert festschreiben(db, entwurf).outro_text.startswith(AUFFORDERUNG)


def test_storno_of_a_refund_invoice_does_not_carry_the_refund_text():
    db = db_session()
    order, _, _ = _welt(db)
    schluss = festschreiben(db, _entwurf(db, order))
    storno = create_storno_draft(db, schluss)
    data = invoice_to_dict(storno)
    assert data["refund_outro_text"] is None and data["printed_outro_text"] != STANDARD


# ---------------------------------------------------------------------------
# API und Rollen
# ---------------------------------------------------------------------------

def test_router_shows_the_refund_text_and_the_settings_edit_it(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _, _ = _welt(db)
    entwurf = _entwurf(db, order)
    client = router_test_client(db, invoices_router, settings_router)
    assert client.get(f"/api/invoices/{entwurf.id}").json()["refund_outro_text"] == STANDARD
    group = client.get(f"/api/settings/option-groups/{REFUND_OUTRO_GROUP}").json()
    assert group["label"] == "Rechnungs-Schlusstexte bei Erstattung"
    option = next(o for o in group["options"] if o["is_default"])
    response = client.put(f"/api/settings/option-groups/{REFUND_OUTRO_GROUP}/options/{option['id']}",
                          json={"label": option["label"], "value": "Wir überweisen den Betrag.", "sort_order": 10, "active": True,
                                "is_default": True})
    assert response.status_code == 200, response.text
    assert client.get(f"/api/invoices/{entwurf.id}").json()["refund_outro_text"] == "Wir überweisen den Betrag."


def test_field_cannot_edit_the_refund_text(threaded_db_session, router_test_client):
    db = threaded_db_session
    option = _option(db)
    client = router_test_client(db, settings_router, role="field")
    response = client.put(f"/api/settings/option-groups/{REFUND_OUTRO_GROUP}/options/{option.id}",
                          json={"label": "Standard", "value": "Zahlen Sie!", "sort_order": 10, "active": True, "is_default": True})
    assert response.status_code == 403
    db.refresh(option)
    assert option.value == STANDARD


# ---------------------------------------------------------------------------
# PostgreSQL: gleichzeitig
# ---------------------------------------------------------------------------

def test_pg_finalizing_waits_for_a_payment_on_the_abschlag_and_takes_the_refund_text(pg):
    """Die Zahlung auf den Abschlag hält die Sperre der Auftragszeile; das Festschreiben der Schlussrechnung wartet und friert den
    Zahlbetrag mit dieser Zahlung ein -- negativ, also der Text für die Erstattung."""
    Session, order_id = pg

    def vorbereiten(s):
        order = s.get(Order, order_id)
        abschlag = _abschlag(s, order, "10")  # 595
        schluss = _entwurf(s, s.get(Order, order_id), "8")  # Zahlbetrag 476 (Abschlag offen)
        mit_zeitraum(s, schluss)
        return abschlag.id, schluss.id

    abschlag_id, schluss_id = _vorbereiten(Session, vorbereiten)

    def zahlen(s):
        return _zahlen(s, s.get(Invoice, abschlag_id), "595").id

    def finalisieren(s):
        invoice = finalize_and_send_invoice(s, s.get(Invoice, schluss_id))
        return invoice.outro_text

    _, outro = _run(Session, zahlen, finalisieren)
    assert outro == STANDARD, outro
