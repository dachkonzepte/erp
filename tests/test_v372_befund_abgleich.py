"""Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026, docs/archiv/befund-vor-echtbetrieb.md), Punkt 3:
Abgleich des Auftrags mit dem Angebot bei vorhandenen Rechnungen oder Zeitbuchungen, unter SQLite und PostgreSQL.

app/orders.py::sync_order_from_source_quote() löscht alle Positionen und Titel des Auftrags und legt sie neu an
(_copy_quote_scope_to_order()). An order_items.id hängen ohne ON DELETE: InvoiceItem.source_order_item_id,
TimeEntry.order_item_id, TimeEntryGroup.order_item_id, WorkPreparationMaterial.source_order_item_id (vor dem Löschen geleert) und
OrderItemCalculationSnapshot (mitgelöscht); an order_sections.id der eigene parent_id. Der Abgleich prüft weder Rechnungen noch
Zeitbuchungen. Unter SQLite (Fremdschlüssel nicht erzwungen) bleiben Verweise ins Leere oder -- wenn die gelöschten IDs die
höchsten waren -- auf eine neue Position mit derselben ID; unter PostgreSQL bricht der Abgleich mit IntegrityError ab (500).
Dazu setzt er den Projektstatus ohne Bedingung auf "beauftragt".

Die Welt legt deshalb nach dem abzugleichenden Auftrag einen zweiten an: seine Positionen haben höhere IDs, wie im Betrieb.
Seit 1.8.71 behoben (bis dahin xfail, tests/befund_vor_echtbetrieb.py), die Tests 3a-3e sind die Abnahmetests: der Abgleich ist
gesperrt (SyncBlockedError, Router 409), sobald an den Positionen etwas hängt oder der Auftrag storniert bzw. abgeschlossen ist;
erlaubt, gelingt er auch mit Untertiteln unter PostgreSQL und lässt den Projektstatus stehen (app/orders.py::sync_block_reasons(),
weitere Fälle in tests/test_v374_abgleich_sperre.py). Ein Abbruch an der Datenbank wird zu AssertionError (_abgleich()). Ablehnen
des Abgleichs (ValueError) ist erlaubt -- geprüft wird die Eigenschaft: Rechnungen und Zeitbuchungen behalten ihre Position, der
Auftrag wird nicht doppelt abgerechnet. Die Tests mit pg laufen gegen die lokale PostgreSQL (ERP_TEST_POSTGRES_URL, opt-in)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.invoices import (
    compute_order_billing_progress,
    create_abschlag_leistungsstand,
    create_schlussrechnung,
    finalize_and_send_invoice,
    update_invoice_item,
)
from app.models import Employee, InvoiceItem, OrderItem, Project, QuoteItem, QuoteSection, TimeEntry
from app.orders import load_order, sync_order_from_source_quote
from app.projects import ensure_quote_structure, load_quote
from app.time_tracking import create_manual_entry
from tests.befund_vor_echtbetrieb import pg_sitzung, vorbedingung
from tests.test_v153_mahnwesen import db_session
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.leistungszeitraum import festschreiben


def _angebot(db, nummer: str, *, titel: bool = False):
    """Angebot mit Position 1 "Eindecken" (10 m2 x 50 EUR); mit titel unter einem verschachtelten Titel 01 / 01.01."""
    quote = make_quote(db, is_consumer=False, number=nummer)
    if titel:
        dach = QuoteSection(quote_id=quote.id, title="Dach", sort_order=10, section_number="01")
        db.add(dach)
        db.flush()
        eindeckung = QuoteSection(quote_id=quote.id, parent_id=dach.id, title="Eindeckung", sort_order=20,
                                  section_number="01.01")
        db.add(eindeckung)
        db.flush()
        ensure_quote_structure(db, quote)[2][quote.items[0].id].section_id = eindeckung.id
        db.commit()
    return quote


def _welt(db, *, titel: bool = False):
    quote = _angebot(db, "0001", titel=titel)
    order = beauftragen(db, quote)
    beauftragen(db, _angebot(db, "0002"))  # späterer Auftrag: höhere Positions-IDs, wie im Betrieb
    employee = Employee(first_name="Mona", last_name="Monteurin", active=True)
    db.add(employee)
    db.commit()
    return quote.id, order.id, employee.id


def _angebot_aendern(db, quote_id):
    """Das Angebot bekommt eine zweite Position -- danach weicht der Auftrag ab und der Abgleich greift."""
    db.add(QuoteItem(quote_id=quote_id, position_number="2", short_text="Rinne", quantity=Decimal("5"), unit="m",
                     unit_price=Decimal("20")))
    db.commit()


def _abgleich(db, order_id):
    """Abgleich wie POST /api/orders/{id}/sync-source-quote. Ablehnen (ValueError, Router 409/422) ist erlaubt; ein Abbruch an
    der Datenbank (IntegrityError, Router 500) wird zum AssertionError des Befunds."""
    try:
        sync_order_from_source_quote(db, load_order(db, order_id), actor_name="Test")
        return True
    except IntegrityError as exc:
        db.rollback()
        raise AssertionError(f"Abgleich bricht an der Datenbank ab: {type(exc.orig).__name__}: "
                             f"{str(exc.orig).splitlines()[0]}") from exc
    except ValueError:
        db.rollback()
        return False


def _position(db, order_item_id):
    item = db.get(OrderItem, order_item_id) if order_item_id is not None else None
    return None if item is None else (item.order_id, item.position_number, item.short_text)


def _leistungsstand(db, order_id, ist):
    invoice = create_abschlag_leistungsstand(db, load_order(db, order_id))
    item = next(i for i in invoice.items if i.position_number == "1")
    update_invoice_item(db, invoice, item, ist_quantity=Decimal(ist))
    db.refresh(invoice)
    return invoice


def _auftragssumme(db, order_id):
    order = load_order(db, order_id)
    return sum((i.quantity * i.unit_price for i in order.items if i.include_in_total), Decimal("0"))


# ---------------------------------------------------------------------------
# SQLite (und mit dem pytest-Plugin auch PostgreSQL): Folgen für Rechnungen und Zeitbuchungen
# ---------------------------------------------------------------------------

def test_final_invoice_after_sync_bills_the_order_once():
    """3a (seit 1.8.71 behoben): nach einem festgeschriebenen Abschlag ist der Abgleich gesperrt -- die Position wird nicht
    doppelt abgerechnet."""
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    festschreiben(db, _leistungsstand(db, order_id, "4"))
    _angebot_aendern(db, quote_id)
    _abgleich(db, order_id)
    festschreiben(db, create_schlussrechnung(db, load_order(db, order_id)))
    assert compute_order_billing_progress(db, order_id)["invoiced_net"] == _auftragssumme(db, order_id)


def test_time_entry_keeps_its_position_after_sync():
    """3b (seit 1.8.71 behoben)."""
    db = db_session()
    quote_id, order_id, employee_id = _welt(db)
    item = load_order(db, order_id).items[0]
    entry = create_manual_entry(db, employee_id=employee_id, order_id=order_id, order_item_id=item.id,
                                work_date=date(2026, 9, 7), hours=Decimal("7.5"))
    vorher = _position(db, entry.order_item_id)
    vorbedingung(vorher == (order_id, "1", "Eindecken"), str(vorher))
    _angebot_aendern(db, quote_id)
    _abgleich(db, order_id)
    db.expire_all()
    assert _position(db, db.get(TimeEntry, entry.id).order_item_id) == vorher


def test_finalized_invoice_keeps_its_order_item_after_sync():
    """3c (seit 1.8.71 behoben)."""
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    invoice = festschreiben(db, _leistungsstand(db, order_id, "4"))
    rows = {i.id: _position(db, i.source_order_item_id) for i in invoice.items}
    vorbedingung(list(rows.values()) == [(order_id, "1", "Eindecken")], str(rows))
    _angebot_aendern(db, quote_id)
    _abgleich(db, order_id)
    db.expire_all()
    assert {i: _position(db, db.get(InvoiceItem, i).source_order_item_id) for i in rows} == rows


@pytest.mark.parametrize("status", ["ausfuehrung", "abgeschlossen"])
def test_sync_keeps_the_project_status(status):
    """3d (seit 1.8.71 behoben): der Abgleich fasst den Projektstatus nicht an."""
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    project = load_order(db, order_id).project
    project.status = status
    db.commit()
    _angebot_aendern(db, quote_id)
    vorbedingung(_abgleich(db, order_id), "Abgleich ohne Rechnungen und Zeitbuchungen abgelehnt")
    db.expire_all()
    assert db.get(Project, project.id).status == status


def test_today_sync_without_invoices_or_time_entries_replaces_the_items():
    """Grün, zur Einordnung: ohne Rechnungen und Zeitbuchungen bekommt der Auftrag die Positionen des Angebots -- mit neuen IDs."""
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    alte = [i.id for i in load_order(db, order_id).items]
    _angebot_aendern(db, quote_id)
    assert _abgleich(db, order_id)
    order = load_order(db, order_id)
    assert [(i.position_number, i.short_text) for i in order.items] == [("1", "Eindecken"), ("2", "Rinne")]
    assert not set(alte) & {i.id for i in order.items}
    assert load_quote(db, quote_id).status == "beauftragt"


# ---------------------------------------------------------------------------
# PostgreSQL (opt-in): Fremdschlüssel greifen -- der Abgleich bricht ab
# ---------------------------------------------------------------------------

@pytest.fixture
def pg():
    with pg_sitzung("abgleich") as db:
        yield db


def _pg_vorbereiten(db, fall):
    quote_id, order_id, employee_id = _welt(db, titel=(fall == "titel"))
    item = load_order(db, order_id).items[0]
    if fall == "zeitbuchung":
        create_manual_entry(db, employee_id=employee_id, order_id=order_id, order_item_id=item.id,
                            work_date=date(2026, 9, 7), hours=Decimal("7.5"))
    elif fall == "rechnung_entwurf":
        _leistungsstand(db, order_id, "4")
    elif fall == "rechnung":
        festschreiben(db, _leistungsstand(db, order_id, "4"))
    _angebot_aendern(db, quote_id)
    return order_id


@pytest.mark.parametrize("fall", ["titel", "zeitbuchung", "rechnung_entwurf", "rechnung"])
def test_postgresql_sync_does_not_break_on_foreign_keys(pg, fall):
    """3e (seit 1.8.71 behoben): kein Abbruch an der Datenbank -- mit Untertiteln gelingt der Abgleich, mit Zeitbuchung oder
    Rechnung (auch Entwurf) an einer Position ist er gesperrt."""
    order_id = _pg_vorbereiten(pg, fall)
    erlaubt = _abgleich(pg, order_id)
    assert erlaubt == (fall == "titel")
    if erlaubt:
        order = load_order(pg, order_id)
        assert [i.position_number for i in order.items] == ["1", "2"]
        titel = {s.id: s for s in order.sections}
        assert sorted((s.section_number, titel[s.parent_id].section_number if s.parent_id else None)
                      for s in titel.values()) == [("01", None), ("01.01", "01")]
        assert next(i for i in order.items if i.position_number == "1").section_id == next(
            s.id for s in titel.values() if s.section_number == "01.01")


def test_today_postgresql_sync_without_titles_invoices_or_time_entries_works(pg):
    """Grün, Gegenprobe: ohne verschachtelte Titel, Rechnungen und Zeitbuchungen gelingt der Abgleich auch unter PostgreSQL."""
    order_id = _pg_vorbereiten(pg, "ohne")
    assert _abgleich(pg, order_id)
    assert [i.position_number for i in load_order(pg, order_id).items] == ["1", "2"]
    assert pg.scalar(select(Project.status).where(Project.id == load_order(pg, order_id).project_id)) == "beauftragt"
