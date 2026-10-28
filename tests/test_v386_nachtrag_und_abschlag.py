"""R4a Punkte 3–6 (seit 1.8.83, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung 1.8.83").

3. Nachtrag nur als gekennzeichnete Auftragsposition (OrderItem.is_addendum, "N1" …, app/orders.py::add_order_addendum()):
   jede folgende Rechnung und die Schlussrechnung übernehmen ihn; freie Positionen ohne Auftragsbezug nur in Rechnungen aus
   Aufwand (Anlegen 409, Festschreiben eines Altbestands 409). Entfernen nur ohne Anhänge; der Abgleich mit dem Angebot ist
   gesperrt, solange Nachträge stehen.
4. Ein Abschlag nach Leistungsstand mit negativem Betrag lässt sich nicht festschreiben (409 mit Hinweis auf Storno oder
   Schlussrechnung); 0 € und eine einzelne negative Position bei positivem Betrag gehen.
5. "Letzter Stand" einer Position = der der zuletzt FESTGESCHRIEBENEN Rechnung (Invoice.finalized_at), nicht der zuletzt angelegten.
6. 1d: das Storno eines pauschalen Abschlags ohne Position lautet auf den Gegenbetrag (Abnahmetest in
   tests/test_v372_befund_schlussrechnung.py, Markierung entfernt); hier dazu PDF und Abrechnungsstand.

Gleichzeitig (PostgreSQL, opt-in): zwei Nachträge zugleich bekommen N1 und N2; ein Nachtrag wartet auf das Festschreiben der
Schlussrechnung und wird abgelehnt."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update

from app.invoices import (
    FREE_ITEM_TEXT, InvoiceBlocked, add_invoice_item, compute_invoice_totals, compute_order_billing_progress,
    create_abschlag_leistungsstand, create_abschlag_pauschal, create_invoice_from_time_entries, create_schlussrechnung,
    create_storno_draft, delete_invoice_draft, finalize_and_send_invoice, get_previous_cumulative_ist, invoice_to_dict,
    update_invoice_item,
)
from app.models import Invoice, InvoiceItem, Order, OrderItem, OrderRevision, Quote
from app.order_locks import OrderLocked
from app.orders import (
    SyncBlockedError, add_order_addendum, load_order, order_to_dict, remove_order_addendum, sync_order_from_source_quote,
)
from app.routers.invoices import router as invoices_router
from app.routers.orders import router as orders_router
from app.sent_documents import read_sent_document
from tests.leistungszeitraum import ZEITRAUM, festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v231_invoice_item_table_width_and_quantity import _extract_pdf_text
from tests.test_v325_contract_basis import beauftragen, make_quote, pdf_text
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)


def _nachtrag(db, order, text="Kaminverblechung", menge="10", preis="100", **kwargs):
    add_order_addendum(db, order.id, short_text=text, long_text="", quantity=Decimal(menge), unit="m",
                       unit_price=Decimal(preis), **kwargs)
    return db.scalars(select(OrderItem).where(OrderItem.order_id == order.id, OrderItem.is_addendum.is_(True))
                      .order_by(OrderItem.id.desc())).first()


def _leistungsstand(db, order, *ist):
    """Abschlag nach Leistungsstand, Ist je Position (in Reihenfolge der Positionen)."""
    invoice = create_abschlag_leistungsstand(db, order)
    for item, value in zip(sorted(invoice.items, key=lambda i: (i.sort_order, i.id)), ist):
        update_invoice_item(db, invoice, item, ist_quantity=Decimal(value))
    db.refresh(invoice)
    return invoice


def _aufwand(db, order):
    return create_invoice_from_time_entries(
        db, order, [], [SimpleNamespace(material_id=None, description="Blech", unit="Stk.", quantity=Decimal("1"))])


# ---------------------------------------------------------------------------
# 3. Nachtrag als Auftragsposition
# ---------------------------------------------------------------------------

def test_an_addendum_is_a_marked_order_position_with_its_own_number_and_a_revision():
    db = db_session()
    order, item = make_order_with_item(db)
    erster = _nachtrag(db, order)
    zweiter = _nachtrag(db, order, "Dachfenster", "2", "300")
    assert (erster.position_number, zweiter.position_number) == ("N1", "N2")
    assert erster.is_addendum and erster.section_id is None and erster.source_quote_item_id is None
    assert erster.sort_order > item.sort_order and zweiter.sort_order > erster.sort_order
    remove_order_addendum(db, order.id, zweiter.id)
    assert _nachtrag(db, order, "Ersatz").position_number == "N2"  # die höchste vergebene + 1
    reasons = list(db.scalars(select(OrderRevision.reason).where(OrderRevision.order_id == order.id)
                              .order_by(OrderRevision.revision_number)))
    assert reasons == ["Nachtrag N1 angelegt", "Nachtrag N2 angelegt", "Nachtrag N2 entfernt", "Nachtrag N2 angelegt"]
    data = order_to_dict(load_order(db, order.id), db)
    assert data["net_total"] == Decimal("5000") + Decimal("1000") + Decimal("1000")
    assert [(i["position_number"], i["is_addendum"]) for i in data["items"]] == [("1", False), ("N1", True), ("N2", True)]


def test_every_later_invoice_and_the_final_invoice_take_the_addendum():
    """Vorher (bis 1.8.82) stand ein Nachtrag als freie Position nur in der einen Rechnung: die Schlussrechnung kannte ihn
    nicht, der Auftrag zeigte 6.000 € abgerechnet bei 5.000 € Auftragssumme (Befund R4 a 5)."""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order, "40"))
    nachtrag = _nachtrag(db, order)
    zweiter = festschreiben(db, _leistungsstand(db, load_order(db, order.id), "60", "4"))
    assert [i.source_order_item_id for i in zweiter.items if i.ist_quantity][-1] == nachtrag.id
    schluss = festschreiben(db, create_schlussrechnung(db, load_order(db, order.id)))
    zeile = next(i for i in schluss.items if i.source_order_item_id == nachtrag.id)
    # Seit 1.8.85 (R4b) rechnet die Schlussrechnung als Endrechnung die volle Ist-Menge (bis 1.8.84: der Rest, 6).
    assert (zeile.position_number, zeile.ist_quantity, zeile.billed_quantity) == ("N1", Decimal("10"), Decimal("10"))
    data = order_to_dict(load_order(db, order.id), db)
    assert data["net_total"] == Decimal("6000")
    assert compute_order_billing_progress(db, order.id)["invoiced_net"] == Decimal("6000") and data["open_net"] == 0
    assert compute_invoice_totals(abschlag)["net_total"] == Decimal("2000")


def test_no_addendum_after_a_valid_final_invoice_or_on_a_cancelled_order():
    db = db_session()
    order, _ = make_order_with_item(db)
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    with pytest.raises(OrderLocked) as exc:
        _nachtrag(db, order)
    assert f"Nach der Schlussrechnung {schluss.invoice_number}" in str(exc.value)
    festschreiben(db, create_storno_draft(db, schluss))
    assert _nachtrag(db, order).position_number == "N1"  # nach dem Storno wieder möglich
    db.get(Order, order.id).status = "storniert"
    db.commit()
    with pytest.raises(OrderLocked) as exc:
        _nachtrag(db, order, "Noch einer")
    assert "storniert" in str(exc.value)


@pytest.mark.parametrize("art", ["abschlag_leistungsstand", "schluss", "storno"])
def test_a_free_position_is_rejected_outside_time_based_invoices(art):
    db = db_session()
    order, _ = make_order_with_item(db)
    if art == "abschlag_leistungsstand":
        invoice = _leistungsstand(db, order, "40")
    elif art == "schluss":
        invoice = create_schlussrechnung(db, order)
    else:
        invoice = create_storno_draft(db, festschreiben(db, _leistungsstand(db, order, "40")))
    vorher = len(invoice.items)
    with pytest.raises(InvoiceBlocked) as exc:
        add_invoice_item(db, invoice, short_text="Frei", long_text="", unit="Stk", unit_price=Decimal("10"),
                         ist_quantity=Decimal("1"))
    assert str(exc.value) == FREE_ITEM_TEXT
    db.expire_all()
    assert len(db.get(Invoice, invoice.id).items) == vorher


def test_a_free_position_still_goes_into_a_time_based_invoice_and_its_finalizing():
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = _aufwand(db, order)
    add_invoice_item(db, invoice, short_text="Anfahrt", long_text="", unit="pauschal", unit_price=Decimal("45"),
                     ist_quantity=Decimal("1"))
    assert compute_invoice_totals(festschreiben(db, invoice))["net_total"] == Decimal("45")


@pytest.mark.parametrize("art", ["abschlag_leistungsstand", "schluss"])
def test_a_draft_from_before_with_a_free_position_cannot_be_finalized(art):
    """Altbestand: ein Entwurf, der vor 1.8.83 eine freie Position bekam (direkt in der Datenbank, wie damals möglich)."""
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = _leistungsstand(db, order, "40") if art == "abschlag_leistungsstand" else create_schlussrechnung(db, order)
    db.add(InvoiceItem(invoice_id=invoice.id, sort_order=99, position_number="", short_text="Alte freie Position", long_text="",
                       unit="Stk", unit_price=Decimal("10"), ist_quantity=Decimal("1"), billed_quantity=Decimal("1"),
                       billed_total=Decimal("10")))
    db.commit()
    db.refresh(invoice)
    assert "„Alte freie Position“" in invoice_to_dict(invoice)["finalize_block"]
    with pytest.raises(InvoiceBlocked) as exc:
        festschreiben(db, invoice)
    assert "Freie Positionen gibt es nur in Rechnungen aus Aufwand" in str(exc.value)
    assert db.get(Invoice, invoice.id).status == "entwurf"


def test_a_lump_sum_invoice_keeps_its_projection_position_without_reference():
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1000")))
    assert [i.source_order_item_id for i in pauschal.items] == [None]


def test_an_addendum_is_removed_only_while_nothing_hangs_on_it():
    db = db_session()
    order, item = make_order_with_item(db)
    nachtrag = _nachtrag(db, order)
    entwurf = create_schlussrechnung(db, load_order(db, order.id))  # übernimmt den Nachtrag
    with pytest.raises(OrderLocked) as exc:
        remove_order_addendum(db, order.id, nachtrag.id)
    assert str(exc.value) == "Der Nachtrag N1 lässt sich nicht entfernen: an ihm hängen Rechnungen (1 Entwurf)."
    assert order_to_dict(load_order(db, order.id), db)["items"][1]["addendum_lock"] == str(exc.value)
    with pytest.raises(OrderLocked) as exc:
        remove_order_addendum(db, order.id, item.id)
    assert "nur ein Nachtrag" in str(exc.value)
    from app.invoices import delete_invoice_draft
    delete_invoice_draft(db, db.get(Invoice, entwurf.id))
    remove_order_addendum(db, order.id, nachtrag.id)
    assert db.get(OrderItem, nachtrag.id) is None
    with pytest.raises(ValueError):  # Position eines anderen (hier: unbekannten) Auftrags
        remove_order_addendum(db, order.id + 1000, item.id)


def test_the_quote_sync_is_blocked_while_an_addendum_stands():
    db = db_session()
    order = beauftragen(db, make_quote(db, is_consumer=False))
    _nachtrag(db, order)
    quote = db.get(Quote, order.source_quote_id)
    quote.title = "Geändert"
    db.commit()
    with pytest.raises(SyncBlockedError) as exc:
        sync_order_from_source_quote(db, load_order(db, order.id))
    assert "am Auftrag steht der Nachtrag N1, den der Abgleich löschen würde" in str(exc.value)
    assert [i.position_number for i in load_order(db, order.id).items if i.is_addendum] == ["N1"]


def test_the_order_pdf_shows_the_addenda_behind_all_titles():
    from app.models import OrderSection
    from app.order_pdf import build_order_pdf
    db = db_session()
    order, item = make_order_with_item(db)
    section = OrderSection(order_id=order.id, title="Steildach", sort_order=10)
    db.add(section)
    db.flush()
    item.section_id = section.id
    db.commit()
    _nachtrag(db, order, "Kaminverblechung")
    text = pdf_text(build_order_pdf(db, load_order(db, order.id)))
    assert text.index("Steildach") < text.index("Nachträge") < text.index("Kaminverblechung")
    assert "N1" in text


def test_the_routes_for_addenda(router_test_client, threaded_db_session):
    db = threaded_db_session
    order, item = make_order_with_item(db)
    client = router_test_client(db, orders_router, invoices_router, role="buero_finanzen")  # seit 1.9.111: Geld nur Admin und Büro – Finanzen
    body = {"short_text": "Kaminverblechung", "long_text": "", "quantity": "10", "unit": "m", "unit_price": "100"}
    antwort = client.post(f"/api/orders/{order.id}/items", json=body)
    assert antwort.status_code == 200, antwort.text
    nachtrag = next(i for i in antwort.json()["items"] if i["is_addendum"])
    assert (nachtrag["position_number"], nachtrag["addendum_lock"], antwort.json()["addendum_create_block"]) == ("N1", None, None)
    assert client.delete(f"/api/orders/{order.id}/items/{item.id}").status_code == 409  # keine Position aus dem Angebot
    assert client.delete(f"/api/orders/{order.id + 999}/items/{nachtrag['id']}").status_code == 404
    assert client.post(f"/api/orders/{order.id + 999}/items", json=body).status_code == 404
    rechnung = client.post(f"/api/orders/{order.id}/invoices/schlussrechnung", json={}).json()["id"]
    antwort = client.post(f"/api/invoices/{rechnung}/items", json={**body, "ist_quantity": "1"})
    assert antwort.status_code == 409 and antwort.json()["detail"] == FREE_ITEM_TEXT
    client.delete(f"/api/invoices/{rechnung}")
    assert client.delete(f"/api/orders/{order.id}/items/{nachtrag['id']}").status_code == 200
    schluss = festschreiben(db, create_schlussrechnung(db, load_order(db, order.id)))
    antwort = client.post(f"/api/orders/{order.id}/items", json=body)
    assert antwort.status_code == 409 and schluss.invoice_number in antwort.json()["detail"]
    assert schluss.invoice_number in client.get(f"/api/orders/{order.id}").json()["addendum_create_block"]


# ---------------------------------------------------------------------------
# 4. Kein negativer Abschlag nach Leistungsstand
# ---------------------------------------------------------------------------

def test_a_negative_progress_invoice_is_rejected_with_the_way_out():
    """Befund R4 Nebenbefund 2: vorher Abschlag 40 m², danach Abschlag mit Ist 30 -> -595 € brutto, mit Nummer."""
    db = db_session()
    order, _ = make_order_with_item(db)
    festschreiben(db, _leistungsstand(db, order, "40"))
    zurueck = mit_zeitraum(db, _leistungsstand(db, order, "30"))
    assert compute_invoice_totals(zurueck)["gross_total"] == Decimal("-595.00")
    grund = invoice_to_dict(zurueck)["finalize_block"]
    assert grund.startswith("Der Abschlag lautet über -595,00 €") and "Storno" in grund and "Schlussrechnung" in grund
    with pytest.raises(InvoiceBlocked) as exc:
        finalize_and_send_invoice(db, zurueck)
    assert str(exc.value) == grund
    db.expire_all()
    assert (db.get(Invoice, zurueck.id).status, db.get(Invoice, zurueck.id).invoice_number) == ("entwurf", None)


def test_a_progress_invoice_with_one_lower_position_goes_through_but_not_one_over_zero():
    """Seit 1.8.85 (Festlegung 1.8.83 Nr. 6 geändert, Vorgabe R4b): ein Abschlag über 0 € wird wie ein negativer abgelehnt --
    bis 1.8.84 ging er mit Nummer durch."""
    db = db_session()
    order, _ = make_order_with_item(db)
    festschreiben(db, _leistungsstand(db, order, "40"))
    null = mit_zeitraum(db, _leistungsstand(db, order, "40"))  # Ist = letzter Stand: 0 €
    with pytest.raises(InvoiceBlocked, match="lautet über 0,00 €"):
        finalize_and_send_invoice(db, null)
    delete_invoice_draft(db, db.get(Invoice, null.id))
    _nachtrag(db, order, menge="10", preis="100")
    gemischt = festschreiben(db, _leistungsstand(db, load_order(db, order.id), "39", "5"))  # -50 + 500
    assert compute_invoice_totals(gemischt)["net_total"] == Decimal("450")


def test_the_finalize_route_answers_409_for_a_negative_progress_invoice(router_test_client, threaded_db_session):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    festschreiben(db, _leistungsstand(db, order, "40"))
    zurueck = mit_zeitraum(db, _leistungsstand(db, order, "30"))
    client = router_test_client(db, invoices_router, role="buero_finanzen")  # seit 1.9.111: Geld nur Admin und Büro – Finanzen
    antwort = client.post(f"/api/invoices/{zurueck.id}/send")
    assert antwort.status_code == 409 and antwort.json()["detail"].startswith("Der Abschlag lautet über -595,00 €")


# ---------------------------------------------------------------------------
# 5. "Letzter Stand" = zuletzt festgeschrieben
# ---------------------------------------------------------------------------

def test_the_last_state_is_the_one_of_the_invoice_finalized_last_not_created_last():
    """Zwei Abschläge als Entwürfe nebeneinander, der zuerst angelegte zuletzt festgeschrieben (am selben Tag): sein Stand gilt.
    Bis 1.8.82 galt der des zuletzt angelegten (Rechnungsdatum, dann ID). Seit 1.8.85 rechnet das Festschreiben unter der
    Sperre neu -- der zuerst angelegte trägt deshalb hier den höheren Stand (60 nach 40); mit dem niedrigeren wäre er negativ."""
    db = db_session()
    order, item = make_order_with_item(db)
    a = _leistungsstand(db, order, "60")
    b = _leistungsstand(db, order, "40")
    festschreiben(db, b)
    festschreiben(db, a)
    db.refresh(a), db.refresh(b)
    assert a.invoice_date == b.invoice_date and a.id < b.id and a.finalized_at > b.finalized_at
    assert a.items[0].billed_quantity == Decimal("20")  # gegen den Stand von b, neu gerechnet beim Festschreiben
    assert get_previous_cumulative_ist(db, order.id, item.id) == Decimal("60")
    naechster = create_abschlag_leistungsstand(db, load_order(db, order.id))
    assert naechster.items[0].ist_quantity == Decimal("60")  # Vorschlag "Ist = letzter Stand"


def test_finalizing_times_rise_within_an_order_even_if_the_clock_goes_back(monkeypatch):
    import app.invoices as invoices_module
    db = db_session()
    order, _ = make_order_with_item(db)
    erste = festschreiben(db, _leistungsstand(db, order, "10"))

    class Rueckwaerts(datetime):
        @classmethod
        def utcnow(cls):
            return erste.finalized_at - timedelta(hours=1)

    monkeypatch.setattr(invoices_module, "datetime", Rueckwaerts)
    zweite = festschreiben(db, _leistungsstand(db, order, "20"))
    assert zweite.finalized_at == erste.finalized_at + timedelta(microseconds=1)
    assert get_previous_cumulative_ist(db, order.id, order.items[0].id) == Decimal("20")


def test_invoices_from_before_have_no_time_and_rank_behind_every_later_one():
    db = db_session()
    order, item = make_order_with_item(db)
    alt = festschreiben(db, _leistungsstand(db, order, "70"))
    table = Invoice.__table__
    db.execute(update(table).where(table.c.id == alt.id).values(finalized_at=None, invoice_date=date(2099, 1, 1)))
    db.commit()
    festschreiben(db, _leistungsstand(db, order, "80"))
    assert get_previous_cumulative_ist(db, order.id, item.id) == Decimal("80")


# ---------------------------------------------------------------------------
# 6. 1d: Storno eines pauschalen Abschlags ohne Position
# ---------------------------------------------------------------------------

def _alter_pauschaler_abschlag(db, order, betrag="2000"):
    pauschal = create_abschlag_pauschal(db, order, lump_sum_net=Decimal(betrag), progress_description="1. Abschlagsrechnung")
    db.delete(pauschal.items[0])  # so stehen sie in der Datenbank (vor 1.3.24)
    pauschal.rounding_rule = None
    pauschal.service_period_start, pauschal.service_period_end = ZEITRAUM
    db.commit()
    db.refresh(pauschal)
    return festschreiben(db, pauschal)


def test_the_cancellation_of_a_legacy_lump_sum_invoice_shows_and_returns_the_amount():
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = _alter_pauschaler_abschlag(db, order)
    assert compute_order_billing_progress(db, order.id)["invoiced_gross"] == Decimal("2380")
    storno = festschreiben(db, create_storno_draft(db, pauschal))
    [zeile] = storno.items
    assert (zeile.short_text, zeile.billed_quantity, zeile.billed_total) == ("1. Abschlagsrechnung", Decimal("-1"), Decimal("-2000"))
    assert compute_invoice_totals(storno) == {"net_total": Decimal("-2000"), "vat_total": Decimal("-380"),
                                              "gross_total": Decimal("-2380")}
    assert compute_order_billing_progress(db, order.id)["invoiced_gross"] == 0  # Original storniert, Storno zählt nicht
    text = _extract_pdf_text(read_sent_document(storno.pdf_document))
    assert b"2.000,00" in text and b"2.380,00" in text  # in der festen Fassung


def test_the_cancellation_of_a_current_lump_sum_invoice_is_unchanged():
    db = db_session()
    order, _ = make_order_with_item(db)
    pauschal = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000")))
    storno = festschreiben(db, create_storno_draft(db, pauschal))
    assert len(storno.items) == 1 and compute_invoice_totals(storno)["gross_total"] == Decimal("-2380.00")


# ---------------------------------------------------------------------------
# Gleichzeitig: PostgreSQL
# ---------------------------------------------------------------------------

def _pg_nachtrag(order_id, text):
    def run(s):
        add_order_addendum(s, order_id, short_text=text, long_text="", quantity=Decimal("1"), unit="Stk", unit_price=Decimal("10"))
        return "angelegt"
    return run


def test_postgresql_two_addenda_at_once_get_two_numbers(pg):
    Session, order_id = pg
    first, second = _run(Session, _pg_nachtrag(order_id, "Erster"), _pg_nachtrag(order_id, "Zweiter"))
    assert (first, second) == ("angelegt", "angelegt"), second
    nummern = _vorbereiten(Session, lambda s: sorted(
        (i.position_number, i.short_text) for i in s.scalars(select(OrderItem).where(OrderItem.order_id == order_id,
                                                                                     OrderItem.is_addendum.is_(True)))))
    assert nummern == [("N1", "Erster"), ("N2", "Zweiter")]


def test_postgresql_an_addendum_waits_for_the_final_invoice_and_is_rejected(pg):
    Session, order_id = pg
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number,
                         _pg_nachtrag(order_id, "Zu spät"))
    assert isinstance(second, OrderLocked) and f"Nach der Schlussrechnung {first}" in str(second), second
    assert _vorbereiten(Session, lambda s: s.scalar(select(OrderItem.id).where(OrderItem.order_id == order_id,
                                                                                OrderItem.is_addendum.is_(True)))) is None


def test_postgresql_removing_an_addendum_waits_for_a_new_invoice_and_is_rejected(pg):
    Session, order_id = pg
    _vorbereiten(Session, _pg_nachtrag(order_id, "Kamin"))
    item_id = _vorbereiten(Session, lambda s: s.scalar(select(OrderItem.id).where(OrderItem.order_id == order_id,
                                                                                   OrderItem.is_addendum.is_(True))))
    first, second = _run(Session, lambda s: create_schlussrechnung(s, s.get(Order, order_id)).id,
                         lambda s: remove_order_addendum(s, order_id, item_id))
    assert isinstance(second, OrderLocked) and "1 Entwurf" in str(second), second
    assert _vorbereiten(Session, lambda s: s.get(OrderItem, item_id)) is not None
