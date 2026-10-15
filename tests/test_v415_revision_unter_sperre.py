"""Version 1.8.110 -- Revisionsnummer unter der Sperre der Auftragszeile und vor dem Commit (Vorgabe "Vor dem Abnahmetest" Punkt 5).

app/orders.py::create_order_revision() vergab bis 1.8.109 max(revision_number) + 1 ohne Sperre und erst NACH dem Commit der Änderung,
die sie sichert (Beauftragen, Abgleich mit dem Angebot, Nachtrag anlegen und entfernen, Revision von Hand). Zwei gleichzeitige
Nachträge: der zweite scheiterte an uq_order_revision_number (API 500), sein Nachtrag war aber schon gespeichert -- gefunden in den
Endläufen zu 1.8.108 (test_v386::test_postgresql_two_addenda_at_once_get_two_numbers, einer von vier Läufen). Seit 1.8.110 sperrt
sie die Auftragszeile (lock_order()) und committet nicht selbst: Änderung und Revision kommen in einem Commit.

Angriffstest gegen PostgreSQL (opt-in über ERP_TEST_POSTGRES_URL): zwei Revisionen von Hand zugleich -- die erste hält ihren Commit
an; nach dem alten Stand liest die zweite dieselbe Höchstnummer und scheitert am Unique-Index, jetzt wartet sie an der Sperre. Dazu
zwei Nachträge zugleich und der Weg über die API. Ohne Datenbank des Servers: keine Revision ohne die Änderung und umgekehrt."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Order, OrderItem, OrderRevision
from app.orders import add_order_addendum, create_order_revision, remove_order_addendum
from app.routers.orders import router as orders_router
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)


def _revisionen(db, order_id):
    return [(r.revision_number, r.reason) for r in db.scalars(
        select(OrderRevision).where(OrderRevision.order_id == order_id).order_by(OrderRevision.revision_number))]


def _nachtrag(db, order_id, text="Kaminverblechung"):
    add_order_addendum(db, order_id, short_text=text, long_text="", quantity=Decimal("2"), unit="Stk",
                       unit_price=Decimal("50"))


# ---------------------------------------------------------------------------
# Eine Transaktion: Änderung und Revision
# ---------------------------------------------------------------------------

def test_create_order_revision_does_not_commit_and_follows_the_callers_transaction():
    db = db_session()
    order, _ = make_order_with_item(db)
    vorher = _revisionen(db, order.id)
    rev = create_order_revision(db, order, reason="Stand gesichert")
    assert rev.id is not None and rev.revision_number == len(vorher) + 1  # vergeben und geschrieben (flush) ...
    db.rollback()
    assert _revisionen(db, order.id) == vorher  # ... aber nicht committet: fällt mit der Transaktion des Aufrufers


def test_an_addendum_whose_revision_fails_is_not_saved(monkeypatch):
    db = db_session()
    order, _ = make_order_with_item(db)
    vorher = _revisionen(db, order.id)

    def kaputt(_order):
        raise RuntimeError("Stand nicht lesbar")
    monkeypatch.setattr("app.orders._order_snapshot_payload", kaputt)
    with pytest.raises(RuntimeError):
        _nachtrag(db, order.id)
    db.rollback()
    assert db.scalar(select(OrderItem.id).where(OrderItem.order_id == order.id, OrderItem.is_addendum.is_(True))) is None
    assert _revisionen(db, order.id) == vorher


def test_the_revision_of_an_addendum_contains_it_and_removing_it_is_one_revision_more():
    db = db_session()
    order, _ = make_order_with_item(db)
    n = len(_revisionen(db, order.id))
    _nachtrag(db, order.id)
    rev = db.scalars(select(OrderRevision).where(OrderRevision.order_id == order.id)
                     .order_by(OrderRevision.revision_number.desc())).first()
    assert (rev.revision_number, rev.reason) == (n + 1, "Nachtrag N1 angelegt")
    assert '"N1"' in rev.snapshot_json  # der Stand MIT dem Nachtrag (vor dem Commit gelesen)
    item_id = db.scalar(select(OrderItem.id).where(OrderItem.order_id == order.id, OrderItem.is_addendum.is_(True)))
    remove_order_addendum(db, order.id, item_id)
    rev = db.scalars(select(OrderRevision).where(OrderRevision.order_id == order.id)
                     .order_by(OrderRevision.revision_number.desc())).first()
    assert (rev.revision_number, rev.reason) == (n + 2, "Nachtrag N1 entfernt")
    assert '"N1"' not in rev.snapshot_json


def test_a_manual_revision_over_the_api_is_committed(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    n = len(_revisionen(db, order.id))
    client = router_test_client(db, orders_router)
    resp = client.post(f"/api/orders/{order.id}/revisions", json={"reason": "Vor dem Gespräch"})
    assert resp.status_code == 200, resp.text
    assert (resp.json()["revision_number"], resp.json()["reason"]) == (n + 1, "Vor dem Gespräch")
    db.rollback()  # nichts mehr offen: die Revision ist committet
    assert _revisionen(db, order.id)[-1] == (n + 1, "Vor dem Gespräch")


# ---------------------------------------------------------------------------
# Gleichzeitig: PostgreSQL (Angriffstest)
# ---------------------------------------------------------------------------

def _revision(order_id, grund):
    def run(s):
        create_order_revision(s, s.get(Order, order_id), reason=grund)
        s.commit()
        return grund
    return run


def _pg_nachtrag(order_id, text):
    def run(s):
        _nachtrag(s, order_id, text)
        return text
    return run


def test_postgresql_two_manual_revisions_at_once_get_two_numbers(pg):
    Session, order_id = pg
    first, second = _run(Session, _revision(order_id, "Erste"), _revision(order_id, "Zweite"))
    assert (first, second) == ("Erste", "Zweite"), second  # bis 1.8.109: second = IntegrityError (uq_order_revision_number)
    assert _vorbereiten(Session, lambda s: _revisionen(s, order_id)) == [
        (1, "Erstbeauftragung aus Angebot"), (2, "Erste"), (3, "Zweite")]


def test_postgresql_two_addenda_at_once_get_two_revisions(pg):
    Session, order_id = pg
    first, second = _run(Session, _pg_nachtrag(order_id, "Erster"), _pg_nachtrag(order_id, "Zweiter"))
    assert (first, second) == ("Erster", "Zweiter"), second
    assert _vorbereiten(Session, lambda s: _revisionen(s, order_id)) == [
        (1, "Erstbeauftragung aus Angebot"), (2, "Nachtrag N1 angelegt"), (3, "Nachtrag N2 angelegt")]


def test_postgresql_an_addendum_waits_for_a_manual_revision(pg):
    Session, order_id = pg
    first, second = _run(Session, _revision(order_id, "Von Hand"), _pg_nachtrag(order_id, "Kamin"))
    assert (first, second) == ("Von Hand", "Kamin"), second
    assert _vorbereiten(Session, lambda s: _revisionen(s, order_id)) == [
        (1, "Erstbeauftragung aus Angebot"), (2, "Von Hand"), (3, "Nachtrag N1 angelegt")]
