"""Sperren an Rechnungen und Mahnungen (seit 1.8.72, R3 Rechnungen Teil 1; Befund 1c, 1e-1h,
docs/archiv/befund-vor-echtbetrieb.md "Umsetzung 1.8.72").

- Je Auftrag höchstens eine nicht stornierte Schlussrechnung, auch als Entwurf; nach der festgeschriebenen keine Abschläge.
- Je Rechnung höchstens ein Storno (auch ein Entwurf zählt), keins eines Stornos.
- Kein Storno eines Abschlags, solange eine gültige (festgeschriebene, nicht stornierte) Schlussrechnung besteht.
- Mahnung: Anlegen, Festschreiben und E-Mail nur, solange die Rechnung weder storniert noch bezahlt ist (seit 1.8.78 ist
  "bezahlt" abgeleitet: tests/zahlung.py::voll_bezahlen() statt mark_invoice_paid()).
- Bis R4: keine Schlussrechnung neben einem nicht stornierten pauschalen Abschlag (409 mit Begründung).

Geprüft beim Anlegen und noch einmal beim Festschreiben (Altbestand: zwei Entwürfe von vor 1.8.72, hier nachgebaut), unter der
Sperre der Auftragszeile (app/invoices.py::lock_order_invoices()). Die Tests mit pg laufen gegen die lokale PostgreSQL
(ERP_TEST_POSTGRES_URL, opt-in) und prüfen die Gleichzeitigkeit: die zweite Aktion wartet auf die Sperre der ersten und findet
danach deren Stand vor."""

import os
import threading
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app.database import Base
from app.invoices import (
    InvoiceBlocked,
    compute_invoice_totals,
    create_abschlag_leistungsstand,
    create_abschlag_pauschal,
    create_invoice_from_time_entries,
    create_schlussrechnung,
    create_storno_draft,
    delete_invoice_draft,
    finalize_and_send_invoice,
    invoice_to_dict,
    update_invoice_item,
)
from app.models import EmailDispatch, Invoice, InvoiceItem, NumberSequence, Order, Reminder
from app.orders import order_to_dict
from app.reminders import create_reminder, finalize_and_send_reminder, reminder_to_dict, send_reminder_email
from app.routers.invoices import router as invoices_router
from app.routers.orders import router as orders_router
from app.routers.reminders import router as reminders_router
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.leistungszeitraum import ZEITRAUM_JSON, festschreiben, mit_zeitraum
from tests.mahnung import frist_ablaufen, zustellen
from tests.zahlung import voll_bezahlen

PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _final(db, invoice):
    return festschreiben(db, invoice)


def _leistungsstand(db, order, ist):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=Decimal(ist))
    db.refresh(invoice)
    return invoice


def _gesperrt(fn, *args, **kwargs) -> str:
    with pytest.raises(InvoiceBlocked) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _anzahl(db, order, invoice_type):
    return db.scalar(select(func.count()).select_from(Invoice).where(Invoice.order_id == order.id,
                                                                     Invoice.invoice_type == invoice_type))


def _naechste_nummer(db, key="invoice"):
    return db.scalar(select(NumberSequence.next_value).where(NumberSequence.sequence_key == key))


def _altbestand_entwurf(db, vorlage: Invoice) -> Invoice:
    """Ein zweiter Entwurf wie vor 1.8.72 -- damals ließ ihn das Anlegen zu. Kopie der Vorlage samt Positionen."""
    copy = Invoice(order_id=vorlage.order_id, invoice_type=vorlage.invoice_type, status="entwurf",
                   storno_of_invoice_id=vorlage.storno_of_invoice_id, customer_name=vorlage.customer_name,
                   vat_rate=vorlage.vat_rate, lump_sum_net=vorlage.lump_sum_net)
    db.add(copy)
    db.flush()
    for item in vorlage.items:
        db.add(InvoiceItem(invoice_id=copy.id, source_order_item_id=item.source_order_item_id, sort_order=item.sort_order,
                           position_number=item.position_number, short_text=item.short_text, unit=item.unit,
                           unit_price=item.unit_price, soll_quantity=item.soll_quantity, ist_quantity=item.ist_quantity,
                           billed_quantity=item.billed_quantity, billed_total=item.billed_total))
    db.commit()
    db.refresh(copy)
    return copy


# ---------------------------------------------------------------------------
# 1: Schlussrechnung -- höchstens eine, auch als Entwurf; danach keine Abschläge
# ---------------------------------------------------------------------------

def test_second_final_invoice_is_rejected_next_to_a_draft_and_allowed_after_deleting_it():
    db = db_session()
    order, _ = make_order_with_item(db)
    entwurf = create_schlussrechnung(db, order)
    text_ = _gesperrt(create_schlussrechnung, db, order)
    assert text_ == ("Am Auftrag besteht schon eine Schlussrechnung (ein Entwurf). Eine weitere ist erst möglich, wenn sie "
                     "storniert bzw. der Entwurf gelöscht ist.")
    assert _anzahl(db, order, "schluss") == 1
    delete_invoice_draft(db, db.get(Invoice, entwurf.id))
    assert create_schlussrechnung(db, db.get(Order, order.id)).status == "entwurf"


def test_second_final_invoice_next_to_a_finalized_one_names_it_and_storno_frees_the_order():
    db = db_session()
    order, _ = make_order_with_item(db)
    erste = _final(db, create_schlussrechnung(db, order))
    assert f"({erste.invoice_number})" in _gesperrt(create_schlussrechnung, db, order)
    _final(db, create_storno_draft(db, erste))
    assert create_schlussrechnung(db, db.get(Order, order.id)).status == "entwurf"


def test_legacy_two_final_drafts_only_one_can_be_finalized_and_the_other_gets_no_number():
    db = db_session()
    order, _ = make_order_with_item(db)
    erste = create_schlussrechnung(db, order)
    zweite = _altbestand_entwurf(db, erste)
    _final(db, erste)
    nummer = _naechste_nummer(db)
    assert "festgeschriebene Schlussrechnung (R-" in _gesperrt(_final, db, zweite)
    db.expire_all()
    assert (db.get(Invoice, zweite.id).status, db.get(Invoice, zweite.id).invoice_number) == ("entwurf", None)
    assert _naechste_nummer(db) == nummer


@pytest.mark.parametrize("art", ["pauschal", "leistungsstand"])
def test_no_progress_invoice_after_the_finalized_final_invoice(art):
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = _final(db, create_schlussrechnung(db, order))
    if art == "pauschal":
        text_ = _gesperrt(create_abschlag_pauschal, db, order, lump_sum_net=Decimal("500"))
    else:
        text_ = _gesperrt(create_abschlag_leistungsstand, db, order)
    assert text_ == f"Nach der Schlussrechnung {schluss.invoice_number} sind keine weiteren Abschlagsrechnungen möglich."
    assert _anzahl(db, order, f"abschlag_{art}") == 0


def test_progress_draft_from_before_the_final_invoice_cannot_be_finalized():
    """Ein Abschlag darf entstehen, solange die Schlussrechnung Entwurf ist -- ist sie festgeschrieben, nicht mehr dieser."""
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = create_schlussrechnung(db, order)
    abschlag = _leistungsstand(db, order, "40")
    _final(db, schluss)
    assert "keine weiteren Abschlagsrechnungen" in _gesperrt(_final, db, abschlag)
    assert db.get(Invoice, abschlag.id).status == "entwurf"
    delete_invoice_draft(db, db.get(Invoice, abschlag.id))


def test_time_based_invoice_is_blocked_after_the_final_invoice():
    """Seit 1.8.85 (R4b Punkt 5): nach der gültigen Schlussrechnung keine Rechnung aus Aufwand mehr -- bis 1.8.84 möglich
    (Festlegung 1.8.72 Nr. 3), sie stand dann weder in der Gesamtleistung noch im Abzug."""
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = _final(db, create_schlussrechnung(db, order))
    eintrag = SimpleNamespace(status="booked", hours=Decimal("2"), entry_type="work", employee_id=None, employee=None,
                              activity="Nacharbeit", work_date=date(2026, 10, 2))
    text_ = _gesperrt(create_invoice_from_time_entries, db, db.get(Order, order.id), [eintrag], [])
    assert text_.startswith(f"Nach der Schlussrechnung {schluss.invoice_number} ist keine Rechnung aus Aufwand mehr möglich")


# ---------------------------------------------------------------------------
# 5: bis R4 keine Schlussrechnung neben einem nicht stornierten pauschalen Abschlag -- seit 1.8.85 (R4b Punkt 5) entfallen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["entwurf", "versendet", "bezahlt"])
def test_final_invoice_is_possible_next_to_a_lump_sum(status):
    """Seit 1.8.85: die Endrechnung zieht den pauschalen Abschlag ab -- die Sperre (bis 1.8.84 mit Grund "kommen mit R4")
    entfällt; ein Entwurf wird nicht abgezogen."""
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000"))
    if status != "entwurf":
        pauschal = _final(db, pauschal)
    if status == "bezahlt":
        voll_bezahlen(db, pauschal, received_on=date(2026, 10, 1))
    schluss = _final(db, create_schlussrechnung(db, order))
    erwartet = Decimal("5000.00") if status == "entwurf" else Decimal("3000.00")
    assert compute_invoice_totals(schluss)["net_total"] == erwartet
    assert _anzahl(db, order, "schluss") == 1


@pytest.mark.parametrize("weg", ["storniert", "geloescht"])
def test_final_invoice_is_possible_after_the_lump_sum_was_cancelled_or_its_draft_deleted(weg):
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000"))
    if weg == "storniert":
        _final(db, create_storno_draft(db, _final(db, pauschal)))
    else:
        delete_invoice_draft(db, pauschal)
    schluss = _final(db, create_schlussrechnung(db, db.get(Order, order.id)))
    assert schluss.status == "versendet"


def test_final_draft_deducts_a_lump_sum_that_appeared_after_it():
    """Seit 1.8.85: bis 1.8.84 sperrte ein später angelegter pauschaler Abschlag das Festschreiben; jetzt zieht die
    Schlussrechnung ab, was beim Festschreiben gilt."""
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = create_schlussrechnung(db, order)
    _final(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000")))
    schluss = _final(db, db.get(Invoice, schluss.id))
    assert compute_invoice_totals(schluss)["net_total"] == Decimal("3000.00")


# ---------------------------------------------------------------------------
# 2 und 3: Storno
# ---------------------------------------------------------------------------

def test_second_storno_is_rejected_next_to_a_draft_and_allowed_after_deleting_it():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    entwurf = create_storno_draft(db, abschlag)
    assert _gesperrt(create_storno_draft, db, abschlag) == "Zu dieser Rechnung besteht schon eine Stornorechnung (ein Entwurf)."
    assert _anzahl(db, order, "storno") == 1
    delete_invoice_draft(db, db.get(Invoice, entwurf.id))
    assert create_storno_draft(db, db.get(Invoice, abschlag.id)).storno_of_invoice_id == abschlag.id


def test_cancelled_invoice_names_its_storno():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    storno = _final(db, create_storno_draft(db, abschlag))
    assert _gesperrt(create_storno_draft, db, db.get(Invoice, abschlag.id)) == (
        f"Zu dieser Rechnung besteht schon eine Stornorechnung ({storno.invoice_number}).")


def test_storno_of_a_storno_is_rejected_and_the_draft_case_stays_400():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    storno = create_storno_draft(db, abschlag)
    with pytest.raises(ValueError, match="Nur festgeschriebene Rechnungen") as exc:  # bis 1.8.77 "versendete oder bezahlte"
        create_storno_draft(db, storno)
    assert not isinstance(exc.value, InvoiceBlocked)
    storno = _final(db, storno)
    assert _gesperrt(create_storno_draft, db, storno) == "Eine Stornorechnung lässt sich nicht stornieren."
    assert _anzahl(db, order, "storno") == 1


def test_legacy_two_storno_drafts_only_one_can_be_finalized():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    erstes = create_storno_draft(db, abschlag)
    zweites = _altbestand_entwurf(db, erstes)
    _final(db, erstes)
    nummer = _naechste_nummer(db)
    assert "besteht schon eine Stornorechnung (R-" in _gesperrt(_final, db, zweites)
    db.expire_all()
    assert (db.get(Invoice, zweites.id).status, _naechste_nummer(db)) == ("entwurf", nummer)


def test_legacy_storno_draft_of_a_storno_cannot_be_finalized():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    storno = _final(db, create_storno_draft(db, abschlag))
    gegen = Invoice(order_id=order.id, invoice_type="storno", status="entwurf", storno_of_invoice_id=storno.id,
                    customer_name="Test Kunde", vat_rate=Decimal("19"))
    db.add(gegen)
    db.commit()
    assert _gesperrt(_final, db, gegen) == "Eine Stornorechnung lässt sich nicht stornieren."
    db.expire_all()
    assert (db.get(Invoice, storno.id).status, db.get(Invoice, abschlag.id).status) == ("versendet", "storniert")


def test_progress_invoice_behind_a_valid_final_invoice_cannot_be_cancelled_until_the_final_is():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    schluss = _final(db, create_schlussrechnung(db, order))
    assert _gesperrt(create_storno_draft, db, abschlag) == (
        f"Der Abschlag ist in der Schlussrechnung {schluss.invoice_number} verrechnet und lässt sich nicht stornieren, "
        "solange sie gilt -- zuerst die Schlussrechnung stornieren.")
    _final(db, create_storno_draft(db, schluss))
    assert create_storno_draft(db, db.get(Invoice, abschlag.id)).storno_of_invoice_id == abschlag.id


def test_progress_invoice_can_be_cancelled_while_the_final_invoice_is_a_draft():
    """Festlegung 1.8.72: "gültig" heißt festgeschrieben -- ein Entwurf der Schlussrechnung sperrt das Storno nicht (dass er
    den Abzug beim Anlegen schon gerechnet hat, ist Befund 1b, R4)."""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    create_schlussrechnung(db, order)
    assert _final(db, create_storno_draft(db, abschlag)).status == "versendet"


def test_storno_draft_of_a_progress_invoice_cannot_be_finalized_after_the_final_invoice():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _final(db, _leistungsstand(db, order, "40"))
    storno = create_storno_draft(db, abschlag)
    _final(db, create_schlussrechnung(db, order))
    assert "zuerst die Schlussrechnung stornieren" in _gesperrt(_final, db, storno)
    db.expire_all()
    assert (db.get(Invoice, abschlag.id).status, db.get(Invoice, storno.id).status) == ("versendet", "entwurf")


# ---------------------------------------------------------------------------
# 4: Mahnung
# ---------------------------------------------------------------------------

def _storniert_oder_bezahlt(db, invoice, danach):
    if danach == "storniert":
        _final(db, create_storno_draft(db, invoice))
    else:
        voll_bezahlen(db, invoice, received_on=date(2026, 10, 2))
    return db.get(Invoice, invoice.id)


@pytest.mark.parametrize("danach", ["storniert", "bezahlt"])
def test_no_reminder_draft_for_a_cancelled_or_paid_invoice(danach):
    db = db_session()
    invoice = _storniert_oder_bezahlt(db, make_sent_overdue_invoice(db), danach)
    text_ = _gesperrt(create_reminder, db, invoice, 1)
    erwartet = "storniert" if danach == "storniert" else "bezahlt (am 02.10.2026)"
    assert text_ == f"Die Rechnung {invoice.invoice_number} ist {erwartet} -- dazu geht keine Mahnung mehr hinaus."
    assert db.scalar(select(func.count()).select_from(Reminder)) == 0


@pytest.mark.parametrize("danach", ["storniert", "bezahlt"])
def test_reminder_draft_is_not_sent_and_gets_no_number_after_cancel_or_payment(danach):
    db = db_session()
    invoice = make_sent_overdue_invoice(db)
    mahnung = create_reminder(db, invoice, 1)
    _storniert_oder_bezahlt(db, invoice, danach)
    nummer = _naechste_nummer(db, "reminder")
    assert "dazu geht keine Mahnung mehr hinaus" in _gesperrt(finalize_and_send_reminder, db, mahnung)
    db.expire_all()
    mahnung = db.get(Reminder, mahnung.id)
    assert (mahnung.status, mahnung.reminder_number, _naechste_nummer(db, "reminder")) == ("entwurf", None, nummer)
    assert reminder_to_dict(mahnung)["send_block"].endswith("dazu geht keine Mahnung mehr hinaus.")


def test_sent_reminder_is_not_emailed_after_the_invoice_was_paid():
    db = db_session()
    invoice = make_sent_overdue_invoice(db)
    mahnung = finalize_and_send_reminder(db, create_reminder(db, invoice, 1))
    assert reminder_to_dict(mahnung)["send_block"] is None
    voll_bezahlen(db, invoice, received_on=date(2026, 10, 2))
    assert "bezahlt" in _gesperrt(send_reminder_email, db, db.get(Reminder, mahnung.id), to_email="kunde@example.com")
    assert db.scalar(select(func.count()).select_from(EmailDispatch)) == 0


# ---------------------------------------------------------------------------
# Router und Anzeige
# ---------------------------------------------------------------------------

def test_router_answers_409_with_the_reason_and_400_stays_for_the_draft_cases(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    client = router_test_client(db, invoices_router, reminders_router)
    first = client.post(f"/api/orders/{order.id}/invoices/schlussrechnung", json={})
    assert first.status_code == 200
    second = client.post(f"/api/orders/{order.id}/invoices/schlussrechnung", json={})
    assert second.status_code == 409 and second.json()["detail"].startswith("Am Auftrag besteht schon eine Schlussrechnung")
    assert client.post(f"/api/invoices/{first.json()['id']}/storno").status_code == 400  # Entwurf: wie bisher 400
    client.put(f"/api/invoices/{first.json()['id']}", json=ZEITRAUM_JSON)  # seit 1.8.74 Pflicht
    assert client.post(f"/api/invoices/{first.json()['id']}/send").status_code == 200
    pauschal = client.post(f"/api/orders/{order.id}/invoices/abschlag-pauschal", json={"lump_sum_net": "100"})
    assert pauschal.status_code == 409 and "keine weiteren Abschlagsrechnungen" in pauschal.json()["detail"]
    storno = client.post(f"/api/invoices/{first.json()['id']}/storno").json()
    assert client.post(f"/api/invoices/{storno['id']}/send").status_code == 200
    gegen = client.post(f"/api/invoices/{storno['id']}/storno")
    assert gegen.status_code == 409 and gegen.json()["detail"] == "Eine Stornorechnung lässt sich nicht stornieren."
    nochmal = client.post(f"/api/invoices/{first.json()['id']}/storno")
    assert nochmal.status_code == 409 and "besteht schon eine Stornorechnung" in nochmal.json()["detail"]


def test_reminder_routes_answer_409(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice = make_sent_overdue_invoice(db)
    client = router_test_client(db, reminders_router)
    gesendet = client.post(f"/api/invoices/{invoice.id}/reminders", json={"level": 1}).json()
    client.post(f"/api/reminders/{gesendet['id']}/send")
    # Seit 1.8.79 (Z2a Nr. 2) höchstens ein Entwurf je Rechnung und die nächste Stufe erst nach Ablauf der Frist -- bis 1.8.78
    # stand hier ein zweiter Entwurf derselben Stufe.
    frist_ablaufen(db, db.get(Reminder, gesendet["id"]))
    zustellen(db, db.get(Reminder, gesendet["id"]))  # seit 1.8.80: Stufe 2 erst, wenn die 1. hinausging
    entwurf = client.post(f"/api/invoices/{invoice.id}/reminders", json={"level": 2}).json()
    voll_bezahlen(db, db.get(Invoice, invoice.id), received_on=date(2026, 10, 2))
    for response in (client.post(f"/api/reminders/{entwurf['id']}/send"),
                     client.post(f"/api/invoices/{invoice.id}/reminders", json={"level": 3}),
                     client.post(f"/api/reminders/{gesendet['id']}/send-email",
                                 json={"to_email": "kunde@example.com", "dispatch_key": "mahnung-test-000000001"})):
        assert response.status_code == 409 and "ist bezahlt (am 02.10.2026)" in response.json()["detail"], response.text
    liste = {r["id"]: r["send_block"] for r in client.get("/api/reminders").json()}
    assert liste[entwurf["id"]] == liste[gesendet["id"]] != None  # noqa: E711


def test_order_and_invoice_name_the_reasons_for_the_page(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    client = router_test_client(db, invoices_router, orders_router)
    blocks = client.get(f"/api/orders/{order.id}").json()["invoice_create_blocks"]
    assert blocks == {"abschlag_pauschal": None, "abschlag_leistungsstand": None, "schluss": None, "aufwand": None}
    pauschal = client.post(f"/api/orders/{order.id}/invoices/abschlag-pauschal", json={"lump_sum_net": "100"}).json()
    # Seit 1.8.85 keine Sperre der Schlussrechnung neben einem pauschalen Abschlag (bis 1.8.84 "vorerst gesperrt").
    assert client.get(f"/api/orders/{order.id}").json()["invoice_create_blocks"]["schluss"] is None
    client.put(f"/api/invoices/{pauschal['id']}", json=ZEITRAUM_JSON)  # seit 1.8.74 Pflicht
    assert client.get(f"/api/invoices/{pauschal['id']}").json()["finalize_block"] is None
    client.delete(f"/api/invoices/{pauschal['id']}")
    schluss = client.post(f"/api/orders/{order.id}/invoices/schlussrechnung", json={}).json()
    abschlag = client.post(f"/api/orders/{order.id}/invoices/abschlag-leistungsstand", json={}).json()
    client.put(f"/api/invoices/{schluss['id']}", json=ZEITRAUM_JSON)  # seit 1.8.74 Pflicht
    client.post(f"/api/invoices/{schluss['id']}/send")
    detail = client.get(f"/api/invoices/{abschlag['id']}").json()
    assert detail["finalize_block"].startswith("Nach der Schlussrechnung R-")
    assert client.get(f"/api/invoices/{schluss['id']}").json()["storno_block"] is None
    blocks = client.get(f"/api/orders/{order.id}").json()["invoice_create_blocks"]
    assert blocks["schluss"].startswith("Am Auftrag besteht schon eine Schlussrechnung (R-")
    assert blocks["abschlag_pauschal"] == blocks["abschlag_leistungsstand"] != None  # noqa: E711
    assert "keine Rechnung aus Aufwand mehr möglich" in blocks["aufwand"]  # seit 1.8.85


def test_pages_show_the_reason_instead_of_the_button():
    """Die Seiten nehmen den Grund vom Server (Klicktest: scripts/klicktest_rechnungen_sperren.py)."""
    templates = Path(__file__).resolve().parent.parent / "app" / "templates"
    order_html = (templates / "akte.html").read_text(encoding="utf-8")
    assert "order.invoice_create_blocks" in order_html and "newInvoiceButton').hidden=!!reason" in order_html
    detail = (templates / "invoice_detail.html").read_text(encoding="utf-8")
    assert "invoice.finalize_block?blockNoticeHtml(invoice.finalize_block)" in detail
    assert "invoice.storno_block?blockNoticeHtml(invoice.storno_block)" in detail
    assert "r.send_block" in (templates / "mahnwesen.html").read_text(encoding="utf-8")


def test_invoice_dict_carries_both_reasons_and_order_dict_without_db_has_none():
    """invoice_to_dict() rechnet die Gründe aus den Rechnungen des Auftrags (auch fürs PDF ohne Fehler); order_to_dict() ohne
    Sitzung (nur Schnappschuss) liefert keine."""
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = create_schlussrechnung(db, order)
    data = invoice_to_dict(schluss)
    assert data["storno_block"] is None
    assert data["finalize_block"].startswith("Der Leistungszeitraum fehlt")  # seit 1.8.74 Pflicht
    assert order_to_dict(db.get(Order, order.id), None)["invoice_create_blocks"] is None


# ---------------------------------------------------------------------------
# PostgreSQL: gleichzeitig
# ---------------------------------------------------------------------------

@pytest.fixture
def pg():
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    from app.grunddaten import anlegen
    from tests.test_v325_contract_basis import beauftragen, make_quote

    schema = f"pgtest_rechnungen_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, pool_size=6,
                           connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        try:
            anlegen(setup)
            setup.commit()
            order = beauftragen(setup, make_quote(setup, is_consumer=False, number="0001"))
            order_id = order.id
        finally:
            setup.close()
        yield Session, order_id
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _held(Session, action, ready):
    """Führt action(session) aus, hält aber den Commit an, bis release gesetzt ist -- die Zeilensperre bleibt so lange
    (Muster aus tests/test_v365_abnahme_aus_protokoll.py)."""
    holder = Session()
    commit = holder.commit
    release = threading.Event()

    def angehalten():
        holder.flush()
        ready.set()
        release.wait(timeout=300)  # seit 1.9.8 nur Sicherheitsnetz: _run() gibt frei, sobald die zweite Aktion nachweislich wartet
        commit()
    holder.commit = angehalten
    result = {}

    def run():
        try:
            result["result"] = action(holder)
        except Exception as exc:  # noqa: BLE001
            result["result"] = exc
    thread = threading.Thread(target=run)
    thread.start()
    return holder, release, thread, result


def _timed(fn) -> dict:
    start, done = time.monotonic(), {}
    try:
        done["result"] = fn()
    except Exception as exc:  # noqa: BLE001
        done["result"] = exc
    done["seconds"] = time.monotonic() - start
    return done


def _wartet_auf_sperre(session):
    """Seit 1.9.8: ein Prüfer, ob die Aktion in session auf eine Sperre wartet (statt einer festen Sekunde). PostgreSQL: ihr Backend hat
    eine nicht gewährte Sperre (pg_locks). SQLite kennt keine Sicht auf wartende Sperren: dort, ob sie ihre erste schreibende Anweisung
    begonnen hat -- die erste Aktion hält die Schreibsperre der Datei, die Anweisung muss warten."""
    verbindung = session.connection()
    if verbindung.dialect.name == "postgresql":
        pid = verbindung.connection.dbapi_connection.info.backend_pid
        engine = session.get_bind()

        def wartet():
            with engine.connect() as conn:
                return conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_locks WHERE pid = :pid AND NOT granted)"),
                                    {"pid": pid}).scalar()
        return wartet
    begonnen = threading.Event()

    def vorher(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split(None, 1)[0].upper() in ("UPDATE", "INSERT", "DELETE"):
            begonnen.set()
    event.listen(verbindung, "before_cursor_execute", vorher)
    return begonnen.is_set


def _bis(bedingung, was: str, sicherheitsnetz: float = 120.0):
    """Wartet, bis bedingung() wahr ist -- Synchronisation auf einen beobachtbaren Zustand; sicherheitsnetz begrenzt nur einen hängenden
    Lauf (dann rot mit was), es ist keine erwartete Dauer."""
    ende = time.monotonic() + sicherheitsnetz
    while not bedingung():
        assert time.monotonic() < ende, f"{was} -- nach {sicherheitsnetz:.0f} s nicht eingetreten"
        time.sleep(0.01)


def _run(Session, first, second):
    """first hält seine Sperre; second startet in einer eigenen Sitzung, lädt dort zuerst seine Objekte (alter Stand, wie der Router)
    und muss dann warten. Seit 1.9.8 gibt _run die erste Aktion frei, sobald die zweite nachweislich auf die Sperre wartet
    (_wartet_auf_sperre()) -- bis dahin nach einer festen Sekunde: unter Last war die zweite Aktion dann manchmal noch nicht so weit,
    lud den neuen Stand und scheiterte anders (test_v376, "'NoneType' object has no attribute 'status'"), oder ihre gemessene Wartezeit
    lag unter 0,9 s.

    Seit 1.8.87 (Nebenbefund 5 aus 1.8.85) schließt _run auch die Sitzung der zweiten Aktion: wirft sie nach der Sperre (wie
    erwartet), blieb ihre Transaktion offen und hielt die Sperre der Auftragszeile -- traf eine spätere Aktion darauf, wartete
    sie ewig. Schließen rollt zurück und gibt die Verbindung frei; schon geladene Werte des Ergebnisses bleiben lesbar, ein
    nicht geladenes Attribut lädt danach nicht mehr nach (DetachedInstanceError).

    Seit 1.8.108 (Nachtrag) zuerst die Sitzung der zweiten Aktion: committet die erste nach der Freigabe ein zweites Mal
    (create_order_from_quote: Auftrag, dann Revision) und wartet dabei auf eine Sperre der zweiten, wartete holder.close() auf
    die Verbindung der ersten und die zweite Sitzung blieb offen -- der Lauf hing (test_v383, Kundenwechsel gegen Beauftragen,
    im parallelen Lauf). Hängt die erste Aktion trotzdem, wird der Test rot statt zu hängen."""
    ready = threading.Event()
    holder, release, thread, first_result = _held(Session, first, ready)
    _bis(lambda: ready.is_set() or not thread.is_alive(), "die erste Aktion erreicht ihren Commit nicht")
    assert ready.is_set(), first_result.get("result")
    result = {}
    second_session = Session()
    wartet = _wartet_auf_sperre(second_session)
    other = threading.Thread(target=lambda: result.update(_timed(lambda: second(second_session))))
    other.start()
    gewartet = []
    _bis(lambda: gewartet.append(True) or True if wartet() else not other.is_alive(),
         "die zweite Aktion wartet weder auf die Sperre noch ist sie fertig")
    release.set()
    other.join(timeout=120)
    if not other.is_alive():  # hängt sie noch, nicht aus diesem Thread an ihre Verbindung gehen
        second_session.close()
    thread.join(timeout=120)
    assert not thread.is_alive(), "die erste Aktion hängt -- wartet sie auf eine Sperre der zweiten?"
    assert not other.is_alive(), "die zweite Aktion hängt nach der Freigabe"
    holder.close()
    first = first_result.get("result")
    assert not isinstance(first, Exception), first
    assert gewartet, ("die zweite Aktion hat nicht auf die Sperre der ersten gewartet", result)
    return first, result["result"]


def _vorbereiten(Session, fn):
    s = Session()
    try:
        return fn(s)
    finally:
        s.close()


def _order(s, order_id):
    return s.get(Order, order_id)


def _inv(s, invoice_id):
    return s.get(Invoice, invoice_id)


def _leistungsstand_pg(s, order_id, ist="4"):
    invoice = create_abschlag_leistungsstand(s, _order(s, order_id))
    update_invoice_item(s, invoice, invoice.items[0], ist_quantity=Decimal(ist))
    return festschreiben(s, invoice).id


def _zaehlen(Session, order_id, **where):
    def count(s):
        stmt = select(func.count()).select_from(Invoice).where(Invoice.order_id == order_id)
        for key, value in where.items():
            stmt = stmt.where(getattr(Invoice, key) == value)
        return s.scalar(stmt)
    return _vorbereiten(Session, count)


def test_postgresql_two_final_invoices_at_once_give_one(pg):
    Session, order_id = pg
    _, second = _run(Session, lambda s: create_schlussrechnung(s, _order(s, order_id)).id,
                     lambda s: create_schlussrechnung(s, _order(s, order_id)))
    assert isinstance(second, InvoiceBlocked), second
    assert _zaehlen(Session, order_id, invoice_type="schluss") == 1


def test_postgresql_two_stornos_at_once_give_one(pg):
    Session, order_id = pg
    abschlag_id = _vorbereiten(Session, lambda s: _leistungsstand_pg(s, order_id))
    _, second = _run(Session, lambda s: create_storno_draft(s, _inv(s, abschlag_id)).id,
                     lambda s: create_storno_draft(s, _inv(s, abschlag_id)))
    assert isinstance(second, InvoiceBlocked), second
    assert _zaehlen(Session, order_id, invoice_type="storno") == 1


def test_postgresql_storno_of_a_progress_invoice_waits_for_the_final_invoice_and_is_rejected(pg):
    Session, order_id = pg
    abschlag_id = _vorbereiten(Session, lambda s: _leistungsstand_pg(s, order_id))
    schluss_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, _order(s, order_id))).id)
    _, second = _run(Session, lambda s: festschreiben(s, _inv(s, schluss_id)).id,
                     lambda s: create_storno_draft(s, _inv(s, abschlag_id)))
    assert isinstance(second, InvoiceBlocked) and "zuerst die Schlussrechnung stornieren" in str(second), second
    assert _zaehlen(Session, order_id, invoice_type="storno") == 0


def test_postgresql_progress_draft_waits_for_the_final_invoice_and_is_rejected(pg):
    Session, order_id = pg
    schluss_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, _order(s, order_id))).id)
    abschlag_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_abschlag_leistungsstand(s, _order(s, order_id))).id)
    _, second = _run(Session, lambda s: festschreiben(s, _inv(s, schluss_id)).id,
                     lambda s: festschreiben(s, _inv(s, abschlag_id)))
    assert isinstance(second, InvoiceBlocked), second
    assert _vorbereiten(Session, lambda s: (_inv(s, abschlag_id).status, _inv(s, abschlag_id).invoice_number)) == (
        "entwurf", None)


def test_postgresql_final_invoice_waits_for_a_lump_sum_and_is_created(pg):
    """Seit 1.8.85 (R4b Punkt 5): die Schlussrechnung wartet auf das Anlegen des pauschalen Abschlags und entsteht danach -- bis
    1.8.84 wurde sie abgelehnt."""
    Session, order_id = pg
    _, second = _run(Session, lambda s: create_abschlag_pauschal(s, _order(s, order_id), lump_sum_net=Decimal("100")).id,
                     lambda s: create_schlussrechnung(s, _order(s, order_id)).invoice_type)
    assert second == "schluss", second
    assert _zaehlen(Session, order_id, invoice_type="schluss") == 1


def test_postgresql_same_draft_finalized_twice_at_once_gets_one_number(pg):
    Session, order_id = pg
    schluss_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, _order(s, order_id))).id)
    first, second = _run(Session, lambda s: festschreiben(s, _inv(s, schluss_id)).invoice_number,
                         lambda s: festschreiben(s, _inv(s, schluss_id)))
    assert isinstance(second, ValueError) and "Nur Rechnungen im Entwurf" in str(second), second
    assert _vorbereiten(Session, lambda s: _inv(s, schluss_id).invoice_number) == first
    assert _vorbereiten(Session, lambda s: s.scalar(select(NumberSequence.next_value).where(
        NumberSequence.sequence_key == "invoice"))) == int(first[-4:]) + 1


def _rechnung_mit_mahnung(Session, order_id, *, mahnung=True):
    def build(s):
        schluss = create_schlussrechnung(s, _order(s, order_id), due_date=date.today() - timedelta(days=20))
        schluss = festschreiben(s, schluss)
        return schluss.id, (create_reminder(s, schluss, 1).id if mahnung else None)
    return _vorbereiten(Session, build)


@pytest.mark.parametrize("erst", ["storno", "bezahlt"])
def test_postgresql_reminder_waits_for_storno_or_payment_and_is_rejected(pg, erst):
    Session, order_id = pg
    invoice_id, reminder_id = _rechnung_mit_mahnung(Session, order_id)
    if erst == "storno":
        storno_id = _vorbereiten(Session, lambda s: create_storno_draft(s, _inv(s, invoice_id)).id)
        first = lambda s: festschreiben(s, _inv(s, storno_id)).id  # noqa: E731
    else:
        first = lambda s: voll_bezahlen(s, _inv(s, invoice_id), received_on=date(2026, 10, 2)).id  # noqa: E731
    _, second = _run(Session, first, lambda s: finalize_and_send_reminder(s, s.get(Reminder, reminder_id)))
    assert isinstance(second, InvoiceBlocked), second
    assert _vorbereiten(Session, lambda s: (s.get(Reminder, reminder_id).status,
                                            s.get(Reminder, reminder_id).reminder_number)) == ("entwurf", None)


def test_postgresql_new_reminder_waits_for_the_payment_and_is_rejected(pg):
    Session, order_id = pg
    invoice_id, _ = _rechnung_mit_mahnung(Session, order_id, mahnung=False)
    _, second = _run(Session, lambda s: voll_bezahlen(s, _inv(s, invoice_id), received_on=date(2026, 10, 2)).id,
                     lambda s: create_reminder(s, _inv(s, invoice_id), 1))
    assert isinstance(second, InvoiceBlocked), second
    assert _vorbereiten(Session, lambda s: s.scalar(select(func.count()).select_from(Reminder))) == 0


def test_postgresql_same_reminder_sent_twice_at_once_gets_one_number(pg):
    Session, order_id = pg
    _, reminder_id = _rechnung_mit_mahnung(Session, order_id)
    first, second = _run(Session, lambda s: finalize_and_send_reminder(s, s.get(Reminder, reminder_id)).reminder_number,
                         lambda s: finalize_and_send_reminder(s, s.get(Reminder, reminder_id)))
    assert isinstance(second, ValueError) and "Nur Mahnungen im Entwurf" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(Reminder, reminder_id).reminder_number) == first
