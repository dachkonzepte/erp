"""Zahlungsstufe Z2b (seit 1.8.80, docs/archiv/zahlungen.md "Umsetzung 1.8.80"): Vertragspartner am Auftrag, Mahnung ersetzen,
Mahngebühren und Pauschale (zuschaltbar), Verzugsbeginn.

- Vorweg 1: der Auftrag hält beim Beauftragen seinen Kunden fest; Rechnungen übernehmen Kunde, Name und Anschrift vom Auftrag;
  Kundenwechsel am Projekt mit Auftrag nur zusammen mit dem Auftrag und mit Begründung, nur ohne festgeschriebene Rechnung/Vertrag.
- Vorweg 2: erreicht ist eine Stufe erst mit Versand oder Zustellung; eine nie hinausgegangene Mahnung wird durch eine neue
  derselben Stufe ersetzt und geht danach nicht mehr hinaus.
- Nr. 3: Schalter "Mahngebühren und Verzugszinsen", Vorgabe aus, nur Admin; aus heißt keine Gebühr, keine Beträge.
- Nr. 4: Nebenforderungen je Rechnung, unveränderlich, nie im Rechnungsbetrag, Gegenbuchung mit Begründung, in jeder Mahnung
  aufsummiert.
- Nr. 5: Gebühr je Stufe nur als Vorschlag, bewusst übernommen; Stufe 1 ohne.
- Nr. 6: Pauschale 40 € nur ohne Verbraucher, einmal je Rechnung, erst ab bestätigtem Verzug, als Vorschlag.

Gleichzeitigkeit gegen PostgreSQL: tests/test_v383_nebenforderungen_pg.py."""

import ast
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, update

from app.berlin_time import berlin_today
from app.dunning_charges import (
    ChargeRejected, charges_in_force, confirm_default_start, default_start_proposal, discard_default_start, reverse_charge,
)
from app.email_dispatch import document_reached_on, record_manual_delivery
from app.invoices import InvoiceBlocked, compute_invoice_totals, create_abschlag_pauschal, invoice_customer
from app.models import (
    ArchiveImmutableError, Customer, DispatchOutcome, EmailDispatch, GeneralSettings, Invoice, InvoiceCharge,
    InvoiceDefaultStart, Order, OrderCustomerChange, Project, Reminder, ReminderLevel,
)
from app.payments import payment_state
from app.project_participants import ClientChangeConflict, check_client_change
from app.reminders import (
    DEFAULT_REMINDER_LEVELS, amounts, create_reminder, finalize_and_send_reminder, format_reminder_text,
    list_invoices_needing_attention, reminder_to_dict, send_reminder_email, set_reminder_charges,
)
from app.routers.dunning_charges import router as charges_router
from app.routers.projects import router as projects_router
from app.routers.reminders import router as reminders_router
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.mahnung import festschreiben_und_ablaufen, frist_ablaufen, zustellen
from tests.test_v133_invoices import make_order_with_item
from tests.test_v382_mahnwesen import SperrBeobachter, _anzahl, _db, _geblockt, _pdf_text, _rechnung, _welt, _zahlen

ROOT = Path(__file__).resolve().parent.parent
D = Decimal
HEUTE = berlin_today()


def _ein(db, on=True):
    db.get(GeneralSettings, 1).dunning_charges_enabled = on
    db.commit()


def _gewerbe(db, invoice):
    invoice_customer(invoice).is_consumer = False
    db.commit()


def _rechnung_zugestellt(db, invoice, on):
    db.add(EmailDispatch(dispatch_key=f"rz-{invoice.id}-{on}", message_ref=f"rz-{invoice.id}-{on}", status="gesendet",
                         channel="einschreiben", document_type="rechnung", document_id=invoice.id,
                         document_number=invoice.invoice_number, to_recipients="Kunde", subject="Rechnung",
                         delivered_on=on, delivered_to_client=True))
    db.commit()


def _zweite_stufe_mit_verzug(db, suffix="0001"):
    """Gewerbekunde, eingeschaltet, 1. Mahnung festgeschrieben und zugestellt (Frist abgelaufen), Verzug bestätigt: Entwurf der
    2. Stufe."""
    invoice = _rechnung(db, suffix)
    _gewerbe(db, invoice)
    _ein(db)
    first = festschreiben_und_ablaufen(db, create_reminder(db, invoice))
    proposal = default_start_proposal(db, invoice)
    assert proposal["basis"] == "mahnung" and proposal["starts_on"] == first.reminder_date, proposal
    confirm_default_start(db, invoice, starts_on=proposal["starts_on"], reason=None)
    db.refresh(invoice)
    return invoice, create_reminder(db, invoice)


# ---------------------------------------------------------------------------
# Vorweg 1: der Auftrag hält seinen Kunden, Rechnungen übernehmen ihn
# ---------------------------------------------------------------------------

def test_order_holds_its_customer_and_the_invoice_takes_customer_name_and_address_from_it():
    db = _db()
    order, _ = make_order_with_item(db)
    old_customer = order.customer_id
    assert old_customer == order.project.customer_id
    other = Customer(name="Anderer", last_name="Anderer")
    db.add(other)
    db.flush()
    order.project.customer_id = other.id  # am Wechsel vorbei, wie ein Altbestand
    order.customer_address = "Auftragsstraße 1, 12345 Auftragsort"
    db.commit()
    draft = mit_zeitraum(db, create_abschlag_pauschal(db, order, lump_sum_net=D("100")))
    draft.customer_name, draft.customer_address = "Veraltet", "Alte Straße"
    db.commit()
    assert invoice_customer(draft).id == old_customer  # Entwurf: der Kunde des Auftrags, nicht des Projekts
    festschreiben(db, draft)
    assert (draft.customer_id, draft.customer_name, draft.customer_address) == (
        old_customer, order.customer_name, "Auftragsstraße 1, 12345 Auftragsort")


def test_orders_without_explicit_customer_get_the_projects_at_creation():
    db = _db()
    invoice = _rechnung(db)
    order = db.get(Order, invoice.order_id)
    assert order.customer_id is not None and order.customer.name == "Test Kunde"


def test_client_change_with_an_order_needs_a_reason_and_changes_order_and_drafts(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice = _rechnung(db)
    order = db.get(Order, invoice.order_id)
    # nur ein Entwurf am Projekt: die festgeschriebene Rechnung zurück auf Entwurf
    db.execute(update(Invoice).where(Invoice.id == invoice.id).values(status="entwurf", invoice_number=None, customer_id=None))
    other = Customer(name="Eigentümergemeinschaft Muster", last_name="Muster", street="Weg 2", postal_code="20095",
                     city="Hamburg")
    db.add(other)
    db.commit()
    client = router_test_client(db, projects_router, user_id=7, display_name="Büro Test")
    payload = {"customer_id": other.id, "property_id": None, "name": order.project.name, "status": order.project.status}
    response = client.put(f"/api/projects/{order.project_id}", json=payload)
    assert response.status_code == 409 and "Begründung" in response.json()["detail"] and order.order_number in \
        response.json()["detail"], response.text
    db.expire_all()
    assert db.get(Project, order.project_id).customer_id != other.id and _anzahl(db, OrderCustomerChange) == 0
    response = client.put(f"/api/projects/{order.project_id}", json={**payload, "customer_change_reason": "  "})
    assert response.status_code == 409
    response = client.put(f"/api/projects/{order.project_id}",
                          json={**payload, "customer_change_reason": "Auftraggeber ist die WEG, nicht die Verwaltung"})
    assert response.status_code == 200, response.text
    db.expire_all()
    order = db.get(Order, order.id)
    assert (order.customer_id, order.customer_name, order.customer_address) == (
        other.id, "Eigentümergemeinschaft Muster", "Weg 2, 20095 Hamburg")
    change = db.scalar(select(OrderCustomerChange))
    assert (change.order_id, change.new_customer_id, change.reason, change.changed_by_name) == (
        order.id, other.id, "Auftraggeber ist die WEG, nicht die Verwaltung", "Büro Test")
    draft = db.get(Invoice, invoice.id)
    assert (draft.customer_name, draft.customer_address) == ("Eigentümergemeinschaft Muster", "Weg 2, 20095 Hamburg")
    change.reason = "anders"
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()


def test_client_change_is_refused_with_a_finalized_invoice_even_with_a_reason():
    db = _db()
    invoice = _rechnung(db)
    project = db.get(Order, invoice.order_id).project
    other = Customer(name="Anderer", last_name="Anderer")
    db.add(other)
    db.commit()
    with pytest.raises(ClientChangeConflict, match="festgeschrieben"):
        check_client_change(db, project, other.id, reason="Begründung")
    db.rollback()
    assert db.get(Order, invoice.order_id).customer_id != other.id


def test_project_without_order_changes_without_a_reason(threaded_db_session, router_test_client):
    db = threaded_db_session
    customer, other = Customer(name="A", last_name="A"), Customer(name="B", last_name="B")
    db.add_all([customer, other])
    db.flush()
    from app.project_pipeline_columns import default_pipeline_column_id
    project = Project(project_number="P-OHNE", name="Ohne Auftrag", customer_id=customer.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.commit()
    client = router_test_client(db, projects_router)
    response = client.put(f"/api/projects/{project.id}", json={"customer_id": other.id, "property_id": None,
                                                              "name": project.name, "status": project.status})
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Vorweg 2: erreicht erst mit Versand oder Zustellung, Ersetzen
# ---------------------------------------------------------------------------

def test_a_level_is_reached_only_once_its_reminder_went_out():
    db = _db()
    invoice = _rechnung(db)
    first = finalize_and_send_reminder(db, create_reminder(db, invoice))
    frist_ablaufen(db, first)
    db.refresh(invoice)
    # festgeschrieben, aber nie hinausgegangen: als Nächstes wieder die 1. Stufe (Ersatz), nicht die 2.
    _geblockt(create_reminder, db, invoice, 2, grund="Nur die nächste Stufe ist möglich: 1. Mahnung")
    zustellen(db, first)
    db.refresh(invoice)
    assert create_reminder(db, invoice).level == 2


@pytest.mark.parametrize("wie,erreicht", [
    ("email", True), ("einschreiben", True), ("unzustellbar", False), ("nur_beteiligter", False), ("in_arbeit", False),
    ("altbestand_email", True),
])
def test_what_counts_as_gone_out(wie, erreicht):
    db = _db()
    invoice = _rechnung(db)
    reminder = finalize_and_send_reminder(db, create_reminder(db, invoice))
    if wie == "email":
        zustellen(db, reminder, channel="smtp")
    elif wie == "einschreiben":
        zustellen(db, reminder)
    elif wie == "unzustellbar":
        row = zustellen(db, reminder)
        db.add(DispatchOutcome(dispatch_id=row.id, outcome="unzustellbar", outcome_on=HEUTE, note="zurück"))
        db.commit()
    elif wie == "nur_beteiligter":
        zustellen(db, reminder, to_client=False)
    elif wie == "in_arbeit":
        zustellen(db, reminder, channel="smtp", status="in_arbeit")
    elif wie == "altbestand_email":  # vor dem Versandprotokoll (1.8.17): nur email_sent_at
        reminder.email_sent_at = reminder.created_at
        db.commit()
    assert (reminder.id in document_reached_on(db, "mahnung", [reminder])) is erreicht


def test_a_reminder_that_never_went_out_is_replaced_and_then_never_goes_out(tmp_path, monkeypatch):
    db = _db()
    invoice = _rechnung(db)
    old = finalize_and_send_reminder(db, create_reminder(db, invoice))
    _zahlen(db, invoice, "100")  # danach stimmt ihr Betrag nicht mehr -- sie geht so nicht hinaus
    db.refresh(invoice)
    row = next(r for r in list_invoices_needing_attention(db) if r["invoice_id"] == invoice.id)
    assert row["pending"]["id"] == old.id and "lautet über" in row["pending"]["dispatch_block"]
    assert row["due_for_reminder"] and row["next_level"] == 1
    new = finalize_and_send_reminder(db, create_reminder(db, invoice, 1))
    db.refresh(old)
    assert (old.replaced_by_id, new.level, new.status) == (new.id, 1, "versendet")
    data = reminder_to_dict(old)
    assert data["replaced_by_number"] == new.reminder_number and "ersetzt" in data["send_block"]
    _geblockt(send_reminder_email, db, old, grund="ersetzt", to_email="kunde@example.com")
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path))
    with pytest.raises(InvoiceBlocked, match="ersetzt"):
        record_manual_delivery(db, dispatch_key="z-ersetzt-0001", document_type="mahnung", document_id=old.id,
                               channel="bote", delivered_on=HEUTE, note="Bote")
    assert _anzahl(db, EmailDispatch) == 0


def test_a_reminder_that_went_out_is_not_replaced():
    db = _db()
    invoice = _rechnung(db)
    first = finalize_and_send_reminder(db, create_reminder(db, invoice))
    zustellen(db, first)
    db.refresh(invoice)
    _geblockt(create_reminder, db, invoice, 1, grund="Nur die nächste Stufe ist möglich: 2. Mahnung")
    assert _anzahl(db, Reminder) == 1


def test_a_sendable_reminder_keeps_the_invoice_out_of_due_but_can_be_replaced():
    db = _db()
    invoice = _rechnung(db)
    old = finalize_and_send_reminder(db, create_reminder(db, invoice))
    frist_ablaufen(db, old)
    db.refresh(invoice)
    row = next(r for r in list_invoices_needing_attention(db) if r["invoice_id"] == invoice.id)
    assert row["pending"]["id"] == old.id and row["pending"]["dispatch_block"] is None
    assert row["is_due_now"] and row["create_block"] is None and not row["due_for_reminder"]
    assert create_reminder(db, invoice).level == 1  # ersetzen geht trotzdem


def test_a_replacement_draft_is_overtaken_if_the_old_one_goes_out_first():
    db = _db()
    invoice = _rechnung(db)
    old = finalize_and_send_reminder(db, create_reminder(db, invoice))
    draft = create_reminder(db, invoice)
    zustellen(db, old)  # die alte ging doch hinaus
    db.refresh(invoice)
    _geblockt(finalize_and_send_reminder, db, draft, grund="ist überholt")
    db.refresh(old)
    assert old.replaced_by_id is None


def test_previous_reminder_date_is_that_of_the_reminder_that_went_out():
    db = _db()
    invoice = _rechnung(db)
    gone = festschreiben_und_ablaufen(db, create_reminder(db, invoice))
    second = create_reminder(db, invoice)
    second.text = "{vorheriges_mahndatum}"
    db.commit()
    assert format_reminder_text(second) == gone.reminder_date.strftime("%d.%m.%Y")


def test_delivery_before_the_reminder_date_is_refused(tmp_path, monkeypatch):
    db = _db()
    invoice = _rechnung(db)
    reminder = finalize_and_send_reminder(db, create_reminder(db, invoice))
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path))
    with pytest.raises(InvoiceBlocked, match="eine Zustellung davor"):
        record_manual_delivery(db, dispatch_key="z-davor-0001", document_type="mahnung", document_id=reminder.id,
                               channel="bote", delivered_on=HEUTE - timedelta(days=1), note="Bote")


# ---------------------------------------------------------------------------
# Nr. 3: Schalter, Vorgabe aus
# ---------------------------------------------------------------------------

def test_switch_is_off_by_default_and_then_no_fee_and_no_amounts():
    db = _db()
    assert db.get(GeneralSettings, 1).dunning_charges_enabled is False
    invoice = _rechnung(db)
    festschreiben_und_ablaufen(db, create_reminder(db, invoice))
    draft = create_reminder(db, invoice)  # 2. Stufe: Vorschlag wäre 10 €
    assert draft.fee_amount == 0 and reminder_to_dict(draft)["proposals"] is None
    draft.fee_amount, draft.fee_accepted = D("10"), True  # wie ein Entwurf von vor 1.8.80 oder von vor dem Ausschalten
    db.commit()
    data = reminder_to_dict(draft)
    assert data["charges"] == [] and data["total_amount"] == data["outstanding_amount"].quantize(D("0.01"))
    assert "Mahngeb" not in _pdf_text(db, draft)
    finalize_and_send_reminder(db, draft)
    assert (draft.fee_amount, draft.fee_accepted, _anzahl(db, InvoiceCharge)) == (0, False, 0)
    breakdown = amounts(draft)
    # seit 1.8.81 Format 3 (Zahlungen auf Nebenforderungen, Rechtstexte), seit 1.8.89 Format 4 (Endrechnung)
    assert breakdown["format"] == 4 and breakdown["charges_enabled"] is False and breakdown["charges"] == []
    assert breakdown["total"] == breakdown["dunnable"]


def test_charges_route_is_409_when_switched_off(threaded_db_session, router_test_client):
    db = threaded_db_session
    reminder = create_reminder(db, _rechnung(db))
    client = router_test_client(db, reminders_router)
    response = client.put(f"/api/reminders/{reminder.id}/charges",
                          json={"fee_amount": "5.00", "fee_accepted": True, "flat_fee_accepted": False,
                                "interest_accepted": False})
    assert response.status_code == 409 and "ausgeschaltet" in response.json()["detail"]
    db.refresh(reminder)
    assert reminder.fee_accepted is False


@pytest.mark.parametrize("role,status", [("admin", 200), ("buero_finanzen", 403), ("buero_auftrag", 403), ("field", 403)])
def test_only_an_admin_switches(threaded_db_session, router_test_client, role, status):
    db = threaded_db_session
    client = router_test_client(db, charges_router, role=role)
    assert client.put("/api/dunning-settings", json={"charges_enabled": True}).status_code == status
    assert client.get("/api/dunning-settings").status_code == (403 if role == "field" else 200)
    db.expire_all()
    assert db.get(GeneralSettings, 1).dunning_charges_enabled is (status == 200)


def test_reminder_level_update_takes_only_sent_fields(threaded_db_session, router_test_client):
    db = threaded_db_session
    level = db.scalar(select(ReminderLevel).where(ReminderLevel.level == 2))
    before = (level.fee_amount, level.label, level.text_template)
    client = router_test_client(db, reminders_router)
    response = client.put(f"/api/reminder-levels/{level.id}", json={"email_subject_template": "Betreff {mahnstufe}"})
    assert response.status_code == 200, response.text
    db.refresh(level)
    assert (level.fee_amount, level.label, level.text_template, level.email_subject_template) == (*before, "Betreff {mahnstufe}")
    assert client.put(f"/api/reminder-levels/{level.id}", json={"fee_amount": None}).status_code == 422


# ---------------------------------------------------------------------------
# Nr. 4: Nebenforderungen
# ---------------------------------------------------------------------------

def test_fee_and_flat_fee_become_charges_summed_in_every_later_reminder_never_in_the_invoice():
    # Seit 1.8.81 ("Vorweg" 1) keine Gebühr neben der Pauschale -- die Gebühr mit der 2., die Pauschale mit der 3. Mahnung.
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    gross_before = payment_state(db, invoice).gross
    set_reminder_charges(db, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
    data = reminder_to_dict(second)
    assert [c["new"] for c in data["charges"]] == [True] and data["charges_open"] == D("10.00")
    festschreiben_und_ablaufen(db, second)
    charges = charges_in_force(db, [invoice.id])[invoice.id]
    assert sorted((c.kind, c.amount, c.reminder_id) for c in charges) == [("gebuehr", D("10.00"), second.id)]
    third = create_reminder(db, invoice)
    set_reminder_charges(db, third, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True)
    finalize_and_send_reminder(db, third)
    breakdown = amounts(third)
    assert [c["amount"] for c in breakdown["charges"]] == [D("10.00"), D("40.00")]
    assert breakdown["charges_open"] == D("50.00") and breakdown["total"] == breakdown["dunnable"] + D("50.00")
    text = _pdf_text(db, third)
    assert "Pauschale nach" in text and "Gesamtbetrag" in text and "Mahngeb" in text
    # nie im Rechnungsbetrag, kein Zahlstand, keine Umsatzsteuer
    assert payment_state(db, invoice).gross == gross_before
    assert compute_invoice_totals(invoice)["gross_total"].quantize(D("0.01")) == gross_before


def test_a_charge_is_immutable_and_reversed_once_with_a_reason():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
    finalize_and_send_reminder(db, second)
    charge = db.scalar(select(InvoiceCharge))
    charge.amount = D("1")
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    db.delete(charge)
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()
    with pytest.raises(ValueError, match="Begründung"):
        reverse_charge(db, charge, reason=" ")
    counter = reverse_charge(db, charge, reason="Kulanz", user_name="Büro")
    assert (counter.amount, counter.reverses_charge_id, counter.reason) == (D("-10.00"), charge.id, "Kulanz")
    with pytest.raises(ChargeRejected, match="schon gegengebucht"):
        reverse_charge(db, charge, reason="nochmal")
    with pytest.raises(ChargeRejected, match="nicht gegenbuchen"):
        reverse_charge(db, counter, reason="zurück")
    assert charges_in_force(db, [invoice.id])[invoice.id] == [] and _anzahl(db, InvoiceCharge) == 2


def test_reminder_with_charges_does_not_go_out_once_they_changed():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
    finalize_and_send_reminder(db, second)
    reverse_charge(db, db.scalar(select(InvoiceCharge)), reason="Erlass")
    db.refresh(second)
    _geblockt(send_reminder_email, db, second, grund="nennt Nebenforderungen von 10,00 €", to_email="kunde@example.com")


def test_no_update_or_delete_of_charges_default_starts_or_customer_changes_under_app():
    funde = []
    for path in (ROOT / "app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("update", "delete")
                    and node.args and isinstance(node.args[0], ast.Name)
                    and node.args[0].id in ("InvoiceCharge", "InvoiceDefaultStart", "OrderCustomerChange")):
                funde.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert funde == [], funde


# ---------------------------------------------------------------------------
# Nr. 5: Gebühr nur als Vorschlag
# ---------------------------------------------------------------------------

def test_fee_is_a_proposal_and_only_charged_when_accepted():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    data = reminder_to_dict(second)
    assert data["proposals"]["fee"] == {"amount": D("10.00"), "level_label": "2. Mahnung", "block": None} \
        and not data["fee_accepted"]
    assert second.fee_amount == D("10.00") and data["charges"] == []
    finalize_and_send_reminder(db, second)
    assert (second.fee_amount, _anzahl(db, InvoiceCharge)) == (0, 0)


def test_level_one_proposes_no_fee():
    assert DEFAULT_REMINDER_LEVELS[0][3] == D("0.00") and DEFAULT_REMINDER_LEVELS[1][3] == D("10.00")
    db = _db()
    assert db.scalar(select(ReminderLevel.fee_amount).where(ReminderLevel.level == 1)) == 0
    for _, _, _, _, text in DEFAULT_REMINDER_LEVELS:
        assert "{mahngebuehr}" not in text and "{gesamtbetrag}" in text


# ---------------------------------------------------------------------------
# Nr. 6: Pauschale, Verzugsbeginn
# ---------------------------------------------------------------------------

def test_flat_fee_not_for_consumers():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    invoice_customer(invoice).is_consumer = True
    db.commit()
    assert "Verbraucher" in reminder_to_dict(second)["proposals"]["flat_fee"]["block"]
    _geblockt(set_reminder_charges, db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True,
              grund="Verbraucher")
    db.refresh(second)
    assert second.flat_fee_accepted is False


def test_flat_fee_only_from_a_confirmed_default_and_rechecked_at_finalizing():
    db = _db()
    invoice = _rechnung(db)
    _gewerbe(db, invoice)
    _ein(db)
    festschreiben_und_ablaufen(db, create_reminder(db, invoice))
    second = create_reminder(db, invoice)
    _geblockt(set_reminder_charges, db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True,
              grund="Verzugsbeginn ist nicht bestätigt")
    start = confirm_default_start(db, invoice, starts_on=default_start_proposal(db, invoice)["starts_on"], reason=None)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True)
    discard_default_start(db, start, reason="falsch bestätigt")  # geht: noch keine Pauschale gebucht
    _geblockt(finalize_and_send_reminder, db, second, grund="nicht bestätigt")
    db.refresh(second)
    assert (second.status, second.reminder_number, _anzahl(db, InvoiceCharge)) == ("entwurf", None, 0)


def test_flat_fee_once_per_invoice():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True)
    festschreiben_und_ablaufen(db, second)
    third = create_reminder(db, invoice)
    assert "schon berechnet" in reminder_to_dict(third)["proposals"]["flat_fee"]["block"]
    _geblockt(set_reminder_charges, db, third, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True,
              grund="schon berechnet")
    # Altbestand/Gleichzeitig: übernommen am Entwurf vorbei -- das Festschreiben lehnt ab
    db.execute(update(Reminder).where(Reminder.id == third.id).values(flat_fee_accepted=True))
    db.commit()
    _geblockt(finalize_and_send_reminder, db, third, grund="schon berechnet")
    assert [c.kind for c in charges_in_force(db, [invoice.id])[invoice.id]] == ["pauschale"]


def test_replacement_reverses_the_old_charges_and_may_take_the_flat_fee_again():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True)
    finalize_and_send_reminder(db, second)  # nie hinausgegangen
    # Bestand von 1.8.80: Gebühr und Pauschale an derselben Mahnung (seit 1.8.81 nicht mehr, "Vorweg" 1).
    db.add(InvoiceCharge(invoice_id=invoice.id, kind="gebuehr", amount=D("10.00"), reminder_id=second.id))
    db.commit()
    _zahlen(db, invoice, "100")
    db.refresh(invoice)
    replacement = create_reminder(db, invoice)
    assert replacement.level == 2
    data = reminder_to_dict(replacement)
    assert data["proposals"]["flat_fee"]["block"] is None and data["charges"] == []  # die alten zählen nicht mehr
    set_reminder_charges(db, replacement, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True)
    finalize_and_send_reminder(db, replacement)
    db.refresh(second)
    assert second.replaced_by_id == replacement.id
    in_force = charges_in_force(db, [invoice.id])[invoice.id]
    assert sorted((c.kind, c.reminder_id) for c in in_force) == [("pauschale", replacement.id)]
    counters = db.scalars(select(InvoiceCharge).where(InvoiceCharge.reverses_charge_id.is_not(None))).all()
    assert len(counters) == 2 and all("ersetzt" in c.reason and second.reminder_number in c.reason for c in counters)


def test_default_start_proposal_is_the_earlier_of_first_reminder_and_thirty_days():
    db = _db()
    invoice = _rechnung(db)
    proposal = default_start_proposal(db, invoice)
    assert proposal["starts_on"] is None and "noch keine Mahnung" in proposal["reason"]
    _gewerbe(db, invoice)
    due = invoice.due_date
    _rechnung_zugestellt(db, invoice, due - timedelta(days=5))
    proposal = default_start_proposal(db, invoice)
    assert (proposal["starts_on"], proposal["basis"]) == (due + timedelta(days=31), "dreissig_tage")
    reminder = finalize_and_send_reminder(db, create_reminder(db, invoice))
    zustellen(db, reminder, on=HEUTE)
    proposal = default_start_proposal(db, invoice)
    expected = min(HEUTE, due + timedelta(days=31))
    assert proposal["starts_on"] == expected and proposal["basis"] == ("mahnung" if expected == HEUTE else "dreissig_tage")
    invoice_customer(invoice).is_consumer = True  # Verbraucher: nur über die Mahnung
    db.commit()
    proposal = default_start_proposal(db, invoice)
    assert (proposal["starts_on"], proposal["basis"]) == (HEUTE, "mahnung")


def test_confirming_the_default_start():
    db = _db()
    invoice = _rechnung(db)
    reminder = finalize_and_send_reminder(db, create_reminder(db, invoice))
    zustellen(db, reminder, on=HEUTE)
    with pytest.raises(ChargeRejected, match="Zukunft"):
        confirm_default_start(db, invoice, starts_on=HEUTE + timedelta(days=1), reason="x")
    with pytest.raises(ChargeRejected, match="Fälligkeit"):
        confirm_default_start(db, invoice, starts_on=invoice.due_date, reason="x")
    with pytest.raises(ValueError, match="Begründung"):
        confirm_default_start(db, invoice, starts_on=HEUTE - timedelta(days=1), reason=None)
    assert _anzahl(db, InvoiceDefaultStart) == 0
    row = confirm_default_start(db, invoice, starts_on=HEUTE - timedelta(days=1), reason="kalendermäßig vereinbart",
                                user_name="Büro")
    assert (row.basis, row.proposal_on, row.reason) == ("von_hand", HEUTE, "kalendermäßig vereinbart")
    with pytest.raises(ChargeRejected, match="schon bestätigt"):
        confirm_default_start(db, invoice, starts_on=HEUTE, reason=None)
    row.starts_on = HEUTE
    with pytest.raises(ArchiveImmutableError):
        db.commit()
    db.rollback()


def test_default_start_cannot_be_discarded_while_a_flat_fee_rests_on_it():
    db = _db()
    invoice, second = _zweite_stufe_mit_verzug(db)
    set_reminder_charges(db, second, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True)
    finalize_and_send_reminder(db, second)
    start = db.scalar(select(InvoiceDefaultStart))
    with pytest.raises(ChargeRejected, match="Pauschale"):
        discard_default_start(db, start, reason="falsch")
    reverse_charge(db, db.scalar(select(InvoiceCharge).where(InvoiceCharge.kind == "pauschale")), reason="Erlass")
    discard_default_start(db, start, reason="falsch")
    assert start.discarded_at is not None and start.discard_reason == "falsch"


def test_no_default_start_for_a_storno_or_a_draft():
    db = _db()
    invoice = _rechnung(db)
    from app.invoices import create_storno_draft
    storno = create_storno_draft(db, invoice)
    with pytest.raises(ChargeRejected, match="Entwurf"):
        confirm_default_start(db, storno, starts_on=HEUTE, reason="x")
    festschreiben(db, storno)
    with pytest.raises(ChargeRejected, match="Stornorechnung"):
        confirm_default_start(db, storno, starts_on=HEUTE, reason="x")
    db.refresh(invoice)
    with pytest.raises(ChargeRejected, match="storniert"):
        confirm_default_start(db, invoice, starts_on=HEUTE, reason="x")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def test_routes_for_charges_and_default_start(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice, second = _zweite_stufe_mit_verzug(db, "0201")
    client = router_test_client(db, charges_router, reminders_router, user_id=3, display_name="Büro Test")
    # Seit 1.8.81 mit interest_accepted (Pflicht) und nur die Pauschale (keine Gebühr daneben, "Vorweg" 1).
    response = client.put(f"/api/reminders/{second.id}/charges",
                          json={"fee_amount": "0", "fee_accepted": False, "flat_fee_accepted": True, "interest_accepted": False})
    assert response.status_code == 200 and response.json()["charges_open"] == "40.00", response.text
    assert client.put(f"/api/reminders/{second.id}/charges", json={"fee_amount": "10.00", "fee_accepted": True}).status_code == 422
    assert client.post(f"/api/reminders/{second.id}/send").status_code == 200
    view = client.get(f"/api/invoices/{invoice.id}/charges").json()
    assert view["enabled"] and view["open_total"] == "40.00" and view["default_start"]["basis"] == "mahnung"
    start_id = view["default_start"]["id"]
    assert client.post(f"/api/invoice-default-starts/{start_id}/discard", json={"reason": "x"}).status_code == 409  # Pauschale
    charge_id = view["charges"][0]["id"]
    assert client.post(f"/api/invoice-charges/{charge_id}/reverse", json={"reason": ""}).status_code == 422
    response = client.post(f"/api/invoice-charges/{charge_id}/reverse", json={"reason": "Kulanz"})
    assert response.status_code == 200 and response.json()["charges"][0]["reversal"]["created_by_name"] == "Büro Test"
    assert client.post(f"/api/invoice-charges/{charge_id}/reverse", json={"reason": "nochmal"}).status_code == 409
    assert client.post("/api/invoice-charges/999999/reverse", json={"reason": "x"}).status_code == 404
    assert client.post(f"/api/invoices/{invoice.id}/default-start", json={"starts_on": str(HEUTE)}).status_code == 409
    assert client.get("/api/invoices/999999/charges").status_code == 404


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/invoices/{i}/charges", None),
    ("post", "/api/invoices/{i}/default-start", {"starts_on": "2026-01-01"}),
    ("post", "/api/invoice-charges/1/reverse", {"reason": "x"}),
    ("post", "/api/invoice-default-starts/1/discard", {"reason": "x"}),
    ("put", "/api/reminders/1/charges", {"fee_amount": "0", "fee_accepted": False, "flat_fee_accepted": False,
                                         "interest_accepted": False}),
])
def test_field_role_gets_403_everywhere(threaded_db_session, router_test_client, method, path, body):
    db = threaded_db_session
    invoice = _rechnung(db)
    client = router_test_client(db, charges_router, reminders_router, role="field")
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path.format(i=invoice.id), **kwargs).status_code == 403


# ---------------------------------------------------------------------------
# Struktur: Nebenforderungen, Verzugsbeginn, Mahnungen und der Kunde am Auftrag schreiben nur unter der Sperre der Auftragszeile
# ---------------------------------------------------------------------------

class AuftragsSperrBeobachter(SperrBeobachter):
    """Wie tests/test_v382_mahnwesen.py::SperrBeobachter, für jede Zeile, die zu einem Auftrag gehört: Nebenforderung,
    Verzugsbeginn, Mahnung, Rechnung, Kundenwechsel und der Auftrag selbst (Kunde)."""

    TYPEN = (InvoiceCharge, InvoiceDefaultStart, Reminder, Invoice, OrderCustomerChange, Order)

    def _schreiben(self, session, context, instances):
        with session.no_autoflush:
            for o in list(session.new) + list(session.dirty) + list(session.deleted):
                if not isinstance(o, self.TYPEN) or (o in session.dirty and not session.is_modified(o)):
                    continue
                self.geschrieben += 1
                if isinstance(o, Order):
                    order_id = o.id
                elif isinstance(o, OrderCustomerChange):
                    order_id = o.order_id
                elif isinstance(o, Invoice):
                    order_id = o.order_id
                else:
                    order_id = session.get(Invoice, o.invoice_id).order_id
                if order_id not in self.sperren:
                    self.verstoesse.append(f"{type(o).__name__} {o.id} ohne Sperre des Auftrags {order_id}")


def _welt_mit_verzug():
    db = _welt()
    invoice, second = _zweite_stufe_mit_verzug(db, "0301")
    return db, invoice, second


def _gebucht(db, second):
    set_reminder_charges(db, second, fee_amount=D("10.00"), fee_accepted=True, flat_fee_accepted=False)
    finalize_and_send_reminder(db, second)
    return db.scalar(select(InvoiceCharge).where(InvoiceCharge.kind == "gebuehr"))


def _projektwechsel(c, db, invoice):
    order = db.get(Order, invoice.order_id)
    db.execute(update(Invoice).where(Invoice.id == invoice.id).values(status="entwurf", invoice_number=None, customer_id=None))
    other = Customer(name="Neu", last_name="Neu")
    db.add(other)
    db.commit()
    return c.put(f"/api/projects/{order.project_id}", json={"customer_id": other.id, "property_id": None, "name": "P",
                                                           "status": "beauftragt", "customer_change_reason": "falsch"})


RUNDGANG = {
    # Seit 1.8.81 ("Vorweg" 1) Gebühr und Pauschale nicht mehr in derselben Mahnung.
    "festschreiben mit Pauschale": lambda c, db, inv, r: (
        set_reminder_charges(db, r, fee_amount=D("0"), fee_accepted=False, flat_fee_accepted=True),
        c.post(f"/api/reminders/{r.id}/send"))[1],
    "Gebühr übernehmen": lambda c, db, inv, r: c.put(
        f"/api/reminders/{r.id}/charges", json={"fee_amount": "10.00", "fee_accepted": True, "flat_fee_accepted": False,
                                                "interest_accepted": False}),
    "Nebenforderung gegenbuchen": lambda c, db, inv, r: c.post(
        f"/api/invoice-charges/{_gebucht(db, r).id}/reverse", json={"reason": "Kulanz"}),
    "Verzugsbeginn verwerfen": lambda c, db, inv, r: c.post(
        f"/api/invoice-default-starts/{db.scalar(select(InvoiceDefaultStart.id))}/discard", json={"reason": "falsch"}),
    "Verzugsbeginn bestätigen": lambda c, db, inv, r: (
        discard_default_start(db, db.scalar(select(InvoiceDefaultStart)), reason="neu"),
        c.post(f"/api/invoices/{inv.id}/default-start", json={"starts_on": str(HEUTE - timedelta(days=8))}))[1],
    "Kundenwechsel am Projekt mit Auftrag": lambda c, db, inv, r: _projektwechsel(c, db, inv),
}


@pytest.mark.parametrize("name", sorted(RUNDGANG))
def test_every_new_writing_way_writes_only_under_the_order_lock(name, router_test_client):
    db, invoice, second = _welt_mit_verzug()
    try:
        client = router_test_client(db, charges_router, reminders_router, projects_router)
        with AuftragsSperrBeobachter(db) as beobachter:
            antwort = RUNDGANG[name](client, db, invoice, second)
        assert antwort.status_code == 200, antwort.text
        assert beobachter.geschrieben >= 1 and beobachter.verstoesse == [], beobachter.verstoesse
    finally:
        db.close()


def test_every_writing_route_of_the_new_router_is_in_the_round():
    routes = {(m, r.path) for r in charges_router.routes for m in r.methods if m not in ("GET", "HEAD")}
    # Seit 1.8.81 dazu Basiszinssatz und Rechtstexte: sie schreiben keine Zeile eines Auftrags
    # (tests/test_v384_verzugszinsen.py::test_rates_and_texts_routes_write_no_order_rows).
    assert routes == {("PUT", "/api/dunning-settings"), ("POST", "/api/invoices/{invoice_id}/default-start"),
                      ("POST", "/api/invoice-default-starts/{start_id}/discard"),
                      ("POST", "/api/invoice-charges/{charge_id}/reverse"),
                      ("POST", "/api/base-interest-rates"), ("PUT", "/api/base-interest-rates/{rate_id}"),
                      ("DELETE", "/api/base-interest-rates/{rate_id}"), ("PUT", "/api/dunning-legal-texts/{text_key}")}
