"""Sperren am Auftrag (seit 1.8.82, R4a Punkt 2; Befund R4 Nebenbefund 1, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung 1.8.82").

- Einheitspreis, Einheit und "in Summe" einer Position: gesperrt, sobald eine gültige Rechnung sie abrechnet (Verweis, Ist ≠ 0;
  festgeschrieben, nicht storniert, kein Storno). Ein Entwurf, eine Position mit Ist 0, eine stornierte Rechnung sperren nicht.
- Steuerschlüssel: ab der ersten gültigen Rechnung gesperrt, gleich welcher Art (auch pauschal und Aufwand).
- Mengen und Texte: bis zur Schlussrechnung änderbar; nach einer gültigen Schlussrechnung alles gesperrt (auch LV-Titel).
- Abgelehnt wird nur eine tatsächliche Änderung, 409 mit Grund; die Auftragsseite bekommt die Gründe (order_lock, tax_lock,
  price_lock je Position). Der Abgleich mit dem Angebot nennt Schlussrechnung und Steuersatz als Grund.

Gleichzeitig (PostgreSQL, opt-in): eine Änderung wartet auf ein gleichzeitiges Festschreiben und lehnt danach ab."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.invoices import (
    create_abschlag_leistungsstand, create_abschlag_pauschal, create_invoice_from_time_entries, create_schlussrechnung,
    create_storno_draft, finalize_and_send_invoice, update_invoice_item,
)
from app.models import Invoice, Order, OrderItem, OrderSection, Quote, TaxKey
from app.order_locks import OrderLocked
from app.orders import (
    SyncBlockedError, load_order, order_to_dict, sync_order_from_source_quote, update_order_item, update_order_section,
    update_order_tax_key,
)
from app.routers.orders import router as orders_router
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)


def _werte(item, **change):
    """Alle Felder wie die Oberfläche sie schickt (PUT sendet immer alle), mit den geänderten."""
    werte = {"quantity": item.quantity, "unit": item.unit, "unit_price": item.unit_price, "short_text": item.short_text,
             "long_text": item.long_text or "", "position_type": item.position_type, "gaeb_oz": item.gaeb_oz,
             "include_in_total": item.include_in_total}
    werte.update(change)
    return werte


def _aendern(db, order, item, **change):
    return update_order_item(db, order.id, item.id, **_werte(db.get(OrderItem, item.id), **change))


def _leistungsstand(db, order, ist="40", position=0):
    invoice = create_abschlag_leistungsstand(db, order)
    items = sorted(invoice.items, key=lambda i: (i.sort_order, i.id))
    update_invoice_item(db, invoice, items[position], ist_quantity=Decimal(ist))
    return invoice


def _zweite_position(db, order):
    item = OrderItem(order_id=order.id, sort_order=20, position_number="2", short_text="Dachrinne", quantity=Decimal("20"),
                     unit="m", unit_price=Decimal("30"))
    db.add(item)
    db.commit()
    return item


def _schluessel(db, label):
    return db.scalar(select(TaxKey).where(TaxKey.label.like(f"{label}%")))


PREIS_AENDERUNGEN = {"unit_price": Decimal("60"), "unit": "Stk.", "include_in_total": False}
FREIE_AENDERUNGEN = {"quantity": Decimal("120"), "short_text": "Dacheindeckung neu", "long_text": "mehr Text",
                     "position_type": "zulage", "gaeb_oz": "01.01"}


# ---------------------------------------------------------------------------
# Einheitspreis, Einheit, "in Summe"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("feld", sorted(PREIS_AENDERUNGEN))
def test_a_billed_position_keeps_price_unit_and_in_total(feld):
    db = db_session()
    order, item = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order))
    with pytest.raises(OrderLocked) as exc:
        _aendern(db, order, item, **{feld: PREIS_AENDERUNGEN[feld]})
    assert f"in {abschlag.invoice_number} abgerechnet" in str(exc.value)
    db.expire_all()
    stand = db.get(OrderItem, item.id)
    assert (stand.unit_price, stand.unit, stand.include_in_total) == (Decimal("50"), "m²", True)


@pytest.mark.parametrize("feld", sorted(FREIE_AENDERUNGEN))
def test_quantity_and_texts_of_a_billed_position_stay_open_until_the_final_invoice(feld):
    db = db_session()
    order, item = make_order_with_item(db)
    festschreiben(db, _leistungsstand(db, order))
    _aendern(db, order, item, **{feld: FREIE_AENDERUNGEN[feld]})
    db.expire_all()
    assert getattr(db.get(OrderItem, item.id), feld) == FREIE_AENDERUNGEN[feld]


def test_saving_unchanged_values_of_a_billed_position_goes_through():
    db = db_session()
    order, item = make_order_with_item(db)
    festschreiben(db, _leistungsstand(db, order))
    _aendern(db, order, item, unit_price=Decimal("50.000"))  # derselbe Preis, anders geschrieben


@pytest.mark.parametrize("fall", ["ohne_rechnung", "entwurf", "ist_null", "storniert", "pauschal"])
def test_the_price_stays_open_while_no_valid_invoice_bills_the_position(fall):
    db = db_session()
    order, item = make_order_with_item(db)
    if fall == "entwurf":
        _leistungsstand(db, order)
    elif fall == "ist_null":  # der Abschlag rechnet nur die zweite Position ab, die erste mit Ist 0
        _zweite_position(db, order)
        db.refresh(order)
        festschreiben(db, _leistungsstand(db, order, "5", position=1))
    elif fall == "storniert":
        abschlag = festschreiben(db, _leistungsstand(db, order))
        festschreiben(db, create_storno_draft(db, abschlag))
    elif fall == "pauschal":
        festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1000")))
    _aendern(db, order, item, unit_price=Decimal("60"), unit="m2", include_in_total=False)
    db.expire_all()
    assert db.get(OrderItem, item.id).unit_price == Decimal("60")


# ---------------------------------------------------------------------------
# Steuerschlüssel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("art", ["leistungsstand", "pauschal", "aufwand"])
def test_the_tax_key_is_locked_from_the_first_valid_invoice_of_any_kind(art):
    db = db_session()
    order, _ = make_order_with_item(db)
    privat, solar = _schluessel(db, "Privat"), _schluessel(db, "Solar")
    update_order_tax_key(db, order, privat.id)
    if art == "leistungsstand":
        rechnung = festschreiben(db, _leistungsstand(db, order))
    elif art == "pauschal":
        rechnung = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1000")))
    else:
        from types import SimpleNamespace
        rechnung = festschreiben(db, create_invoice_from_time_entries(
            db, order, [], [SimpleNamespace(material_id=None, description="Blech", unit="Stk.", quantity=Decimal("1"))]))
    update_order_tax_key(db, load_order(db, order.id), privat.id)  # derselbe Schlüssel: geht
    with pytest.raises(OrderLocked) as exc:
        update_order_tax_key(db, load_order(db, order.id), solar.id)
    assert "Steuersatz ist gesperrt" in str(exc.value) and rechnung.invoice_number in str(exc.value)
    db.expire_all()
    assert (db.get(Order, order.id).tax_key_id, db.get(Order, order.id).vat_rate) == (privat.id, Decimal("19"))


def test_the_tax_key_is_free_again_when_every_invoice_is_cancelled():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order))
    festschreiben(db, create_storno_draft(db, abschlag))
    update_order_tax_key(db, load_order(db, order.id), _schluessel(db, "Solar").id)
    assert db.get(Order, order.id).vat_rate == Decimal("0")


# ---------------------------------------------------------------------------
# Nach der Schlussrechnung alles
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("feld", sorted({**PREIS_AENDERUNGEN, **FREIE_AENDERUNGEN}))
def test_after_a_valid_final_invoice_every_field_is_locked(feld):
    db = db_session()
    order, item = make_order_with_item(db)
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    with pytest.raises(OrderLocked) as exc:
        _aendern(db, order, item, **{feld: {**PREIS_AENDERUNGEN, **FREIE_AENDERUNGEN}[feld]})
    assert f"Nach der Schlussrechnung {schluss.invoice_number}" in str(exc.value)
    _aendern(db, order, item)  # unverändert: geht


def test_after_a_valid_final_invoice_titles_and_tax_key_are_locked_and_free_again_after_its_cancellation():
    db = db_session()
    order, item = make_order_with_item(db)
    section = OrderSection(order_id=order.id, title="Dach", sort_order=10)
    db.add(section)
    db.commit()
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    with pytest.raises(OrderLocked):
        update_order_section(db, order.id, section.id, title="Dach neu", description=None)
    update_order_section(db, order.id, section.id, title="Dach", description=None)  # unverändert: geht
    with pytest.raises(OrderLocked):
        update_order_tax_key(db, load_order(db, order.id), _schluessel(db, "Solar").id)
    festschreiben(db, create_storno_draft(db, schluss))
    update_order_section(db, order.id, section.id, title="Dach neu", description=None)
    _aendern(db, order, item, quantity=Decimal("90"), unit_price=Decimal("55"))
    db.expire_all()
    assert (db.get(OrderSection, section.id).title, db.get(OrderItem, item.id).unit_price) == ("Dach neu", Decimal("55"))


def test_a_cancelled_final_invoice_after_an_advance_keeps_the_advance_lock():
    """Storno der Schlussrechnung: der Abschlag davor rechnet die Position weiter ab -- der Preis bleibt gesperrt."""
    db = db_session()
    order, item = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order))
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    festschreiben(db, create_storno_draft(db, schluss))
    _aendern(db, order, item, quantity=Decimal("110"))
    with pytest.raises(OrderLocked) as exc:
        _aendern(db, order, item, unit_price=Decimal("60"))
    assert abschlag.invoice_number in str(exc.value) and schluss.invoice_number not in str(exc.value)


# ---------------------------------------------------------------------------
# Auftragsseite und Router
# ---------------------------------------------------------------------------

def test_the_order_page_gets_the_reasons():
    db = db_session()
    order, item = make_order_with_item(db)
    zweite = _zweite_position(db, order)
    db.refresh(order)
    leer = order_to_dict(load_order(db, order.id), db)
    assert (leer["order_lock"], leer["tax_lock"]) == (None, None) and {i["price_lock"] for i in leer["items"]} == {None}
    abschlag = festschreiben(db, _leistungsstand(db, order))
    data = order_to_dict(load_order(db, order.id), db)
    locks = {i["id"]: i["price_lock"] for i in data["items"]}
    assert abschlag.invoice_number in locks[item.id] and locks[zweite.id] is None  # zweite mit Ist 0
    assert data["order_lock"] is None and abschlag.invoice_number in data["tax_lock"]
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    data = order_to_dict(load_order(db, order.id), db)
    assert schluss.invoice_number in data["order_lock"] and data["tax_lock"] == data["order_lock"]
    assert {i["price_lock"] for i in data["items"]} == {None}  # die Sperre des ganzen Auftrags sagt es schon


def test_the_routes_answer_409_with_the_reason(router_test_client, threaded_db_session):
    db = threaded_db_session
    order, item = make_order_with_item(db)
    section = OrderSection(order_id=order.id, title="Dach", sort_order=10)
    db.add(section)
    db.commit()
    client = router_test_client(db, orders_router, role="buero_auftrag")
    abschlag = festschreiben(db, _leistungsstand(db, order))
    werte = {k: str(v) if isinstance(v, Decimal) else v for k, v in _werte(item, unit_price=Decimal("60")).items()}
    response = client.put(f"/api/orders/{order.id}/items/{item.id}", json=werte)
    assert response.status_code == 409 and abschlag.invoice_number in response.json()["detail"]
    response = client.put(f"/api/orders/{order.id}/tax-key", json={"tax_key_id": _schluessel(db, "Solar").id})
    assert response.status_code == 409 and "Steuersatz ist gesperrt" in response.json()["detail"]
    body = client.get(f"/api/orders/{order.id}").json()
    assert abschlag.invoice_number in body["items"][0]["price_lock"] and body["tax_lock"]
    festschreiben(db, create_schlussrechnung(db, order))
    response = client.put(f"/api/orders/{order.id}/sections/{section.id}", json={"title": "Neu", "description": None})
    assert response.status_code == 409 and "Nach der Schlussrechnung" in response.json()["detail"]
    werte["unit_price"], werte["quantity"] = "50", "90"
    response = client.put(f"/api/orders/{order.id}/items/{item.id}", json=werte)
    assert response.status_code == 409 and "Nach der Schlussrechnung" in response.json()["detail"]
    assert client.put(f"/api/orders/{order.id}/items/999999", json=werte).status_code == 404


# ---------------------------------------------------------------------------
# Abgleich mit dem Angebot
# ---------------------------------------------------------------------------

def test_the_quote_sync_is_blocked_by_a_valid_final_invoice_and_by_a_different_tax_rate():
    db = db_session()
    order = beauftragen(db, make_quote(db, is_consumer=False))
    festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("100")))
    quote = db.get(Quote, order.source_quote_id)
    quote.vat_rate = Decimal("0")
    db.commit()
    with pytest.raises(SyncBlockedError) as exc:
        sync_order_from_source_quote(db, load_order(db, order.id))
    assert "der Steuersatz ist gesperrt" in str(exc.value)
    assert db.get(Order, order.id).vat_rate == Decimal("19")


def test_the_quote_sync_is_blocked_after_a_closing_invoice_without_positions():
    """Eine abschließende Rechnung, die an keiner Position hängt, sperrt trotzdem. Bis 1.8.85 eine Schlussrechnung ohne
    Positionen (alle Positionen nicht "in Summe") -- seit 1.8.86 ist das ein Auftrag nach Aufwand (Auftragssumme 0 €) ohne
    Schlussrechnung; er schließt mit einer abschließenden Rechnung aus Aufwand ab (R4b Punkt 6)."""
    from types import SimpleNamespace
    from app.invoices import update_invoice_header
    db = db_session()
    order = beauftragen(db, make_quote(db, is_consumer=False))
    for item in order.items:
        item.include_in_total = False
    db.commit()
    aufwand = create_invoice_from_time_entries(
        db, load_order(db, order.id), [], [SimpleNamespace(material_id=None, description="Blech", unit="Stk", quantity=Decimal("1"))])
    update_invoice_header(db, aufwand, closes_order=True)
    aufwand = festschreiben(db, db.get(Invoice, aufwand.id))
    quote = db.get(Quote, order.source_quote_id)
    quote.title = "Geändert"
    db.commit()
    with pytest.raises(SyncBlockedError) as exc:
        sync_order_from_source_quote(db, load_order(db, order.id))
    assert f"die abschließende Rechnung aus Aufwand {aufwand.invoice_number} ist festgeschrieben" in str(exc.value)


# ---------------------------------------------------------------------------
# Gleichzeitig: PostgreSQL
# ---------------------------------------------------------------------------

def _pg_position(Session, order_id):
    return _vorbereiten(Session, lambda s: s.scalar(select(OrderItem.id).where(OrderItem.order_id == order_id)))


def _pg_aendern(order_id, item_id, **change):
    return lambda s: update_order_item(s, order_id, item_id, **_werte(s.get(OrderItem, item_id), **change))


def test_postgresql_price_change_waits_for_finalizing_and_is_rejected(pg):
    """Vorher (bis 1.8.81) gab es keine Sperre; ohne die Zeilensperre prüfte die Änderung vor dem Commit des Festschreibens."""
    Session, order_id = pg
    item_id = _pg_position(Session, order_id)
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, _leistungsstand(s, s.get(Order, order_id), "4")).id)
    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number,
                         _pg_aendern(order_id, item_id, unit_price=Decimal("60")))
    assert isinstance(second, OrderLocked) and first in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(OrderItem, item_id).unit_price) == Decimal("50")


def test_postgresql_quantity_change_waits_for_the_final_invoice_and_is_rejected(pg):
    Session, order_id = pg
    item_id = _pg_position(Session, order_id)
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number,
                         _pg_aendern(order_id, item_id, quantity=Decimal("12")))
    assert isinstance(second, OrderLocked) and f"Nach der Schlussrechnung {first}" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(OrderItem, item_id).quantity) == Decimal("10")


def test_postgresql_tax_key_change_waits_for_finalizing_and_is_rejected(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_abschlag_pauschal(
        s, s.get(Order, order_id), lump_sum_net=Decimal("100"))).id)
    solar_id = _vorbereiten(Session, lambda s: _schluessel(s, "Solar").id)
    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number,
                         lambda s: update_order_tax_key(s, s.get(Order, order_id), solar_id))
    assert isinstance(second, OrderLocked) and first in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(Order, order_id).vat_rate) == Decimal("19")


def test_postgresql_finalizing_waits_for_a_quantity_change_and_bills_it(pg):
    """Umgekehrt: das Festschreiben einer Schlussrechnung wartet auf die laufende Mengenänderung -- die Änderung geht durch."""
    Session, order_id = pg
    item_id = _pg_position(Session, order_id)
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, lambda s: _pg_aendern(order_id, item_id, quantity=Decimal("12"))(s) and "geaendert",
                         lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number)
    assert isinstance(second, str), second
    assert _vorbereiten(Session, lambda s: s.get(OrderItem, item_id).quantity) == Decimal("12")
