"""Version 1.8.71 -- Abgleich mit dem Angebot gesperrt, sobald an den Positionen etwas hängt (Befund „Vor dem Echtbetrieb: Geld
und Sicherheit“ Punkt 3, docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.71").

app/orders.py::sync_order_from_source_quote() ersetzt alle Positionen des Auftrags (neue IDs). Seit 1.8.71 lehnt er ab
(SyncBlockedError, Router 409 mit Grund), wenn der Auftrag storniert oder abgeschlossen ist oder an einer Position eine
Rechnungsposition (jeder Status, auch Entwurf und Storno), eine Zeit- oder Gruppenbuchung oder Material der Arbeitsvorbereitung
hängt (sync_block_reasons()). Ist er erlaubt, gelingt er auch mit Untertiteln (PostgreSQL: tests/test_v372_befund_abgleich.py)
und lässt den Projektstatus stehen. Die Abnahmetests der Befundpunkte 3a-3e stehen in tests/test_v372_befund_abgleich.py; hier
die übrigen Sperrgründe, der Router und die Auftragsseite."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.invoices import create_abschlag_pauschal, create_storno_draft, finalize_and_send_invoice
from app.models import (
    OrderItemCalculationSnapshot, OrderItemMaterialSnapshot, OrderRevision, WorkPreparation, WorkPreparationMaterial,
)
from app.orders import SyncBlockedError, load_order, order_to_dict, sync_order_from_source_quote
from app.routers.orders import router as orders_router
from app.time_tracking import create_group_manual_entry, create_manual_entry
from tests.test_v153_mahnwesen import db_session
from tests.test_v372_befund_abgleich import _angebot_aendern, _leistungsstand, _welt
from tests.leistungszeitraum import festschreiben

GESPERRT = "Der Abgleich mit dem Angebot ist gesperrt: "


def _ids(db, order_id):
    return [i.id for i in load_order(db, order_id).items]


def _gesperrt(db, order_id) -> str:
    """Abgleich muss abgelehnt werden; liefert den Grund. Die Positionen bleiben, wie sie sind."""
    vorher = _ids(db, order_id)
    with pytest.raises(SyncBlockedError) as exc:
        sync_order_from_source_quote(db, load_order(db, order_id), actor_name="Test")
    db.rollback()
    assert _ids(db, order_id) == vorher
    assert str(exc.value).startswith(GESPERRT)
    return str(exc.value)


def _erlaubt(db, order_id):
    order = sync_order_from_source_quote(db, load_order(db, order_id), actor_name="Test")
    assert [i.position_number for i in order.items] == ["1", "2"]
    return order


@pytest.mark.parametrize("status,text", [("storniert", "Der Auftrag ist storniert"),
                                         ("abgeschlossen", "Der Auftrag ist abgeschlossen")])
def test_cancelled_or_completed_order_is_not_synced(status, text):
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    load_order(db, order_id).status = status
    db.commit()
    _angebot_aendern(db, quote_id)
    assert text in _gesperrt(db, order_id)


@pytest.mark.parametrize("status", ["beauftragt", "arbeitsvorbereitung", "in_ausfuehrung", "pausiert"])
def test_other_order_statuses_allow_the_sync(status):
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    load_order(db, order_id).status = status
    db.commit()
    _angebot_aendern(db, quote_id)
    assert _erlaubt(db, order_id).status == status


def test_invoice_draft_blocks_and_is_named_then_its_number():
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    entwurf = _leistungsstand(db, order_id, "4")
    _angebot_aendern(db, quote_id)
    assert "an den Positionen hängen Rechnungen (1 Entwurf)" in _gesperrt(db, order_id)
    nummer = festschreiben(db, entwurf).invoice_number
    assert f"an den Positionen hängen Rechnungen ({nummer})" in _gesperrt(db, order_id)


def test_cancelled_invoice_and_its_storno_still_block():
    """Storniert ist die Rechnung nicht weg -- ihre Positionen und die der Stornorechnung zeigen weiter auf den Auftrag."""
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    original = festschreiben(db, _leistungsstand(db, order_id, "4"))
    storno = festschreiben(db, create_storno_draft(db, original))
    db.refresh(original)
    assert original.status == "storniert"
    _angebot_aendern(db, quote_id)
    grund = _gesperrt(db, order_id)
    assert original.invoice_number in grund and storno.invoice_number in grund


def test_lump_sum_down_payment_without_item_reference_does_not_block():
    """Ein pauschaler Abschlag ist ein Nettobetrag ohne Bezug auf eine Position -- er hängt nicht an den Positionen."""
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    festschreiben(db, create_abschlag_pauschal(db, load_order(db, order_id), lump_sum_net=Decimal("100")))
    _angebot_aendern(db, quote_id)
    _erlaubt(db, order_id)


def test_time_entry_without_item_does_not_block_with_item_it_does():
    db = db_session()
    quote_id, order_id, employee_id = _welt(db)
    create_manual_entry(db, employee_id=employee_id, order_id=order_id, work_date=date(2026, 9, 7), hours=Decimal("2"))
    _angebot_aendern(db, quote_id)
    assert _erlaubt(db, order_id)
    item_id = load_order(db, order_id).items[0].id
    create_manual_entry(db, employee_id=employee_id, order_id=order_id, order_item_id=item_id,
                        work_date=date(2026, 9, 8), hours=Decimal("2"))
    _angebot_aendern(db, quote_id)
    assert "an den Positionen hängen 1 Zeitbuchung" in _gesperrt(db, order_id)


def test_group_booking_blocks():
    db = db_session()
    quote_id, order_id, employee_id = _welt(db)
    item_id = load_order(db, order_id).items[0].id
    create_group_manual_entry(db, employee_ids=[employee_id], team_id=None, actor_employee_id=None, is_admin=True,
                              order_id=order_id, work_date=date(2026, 9, 7), hours=Decimal("3"), order_item_id=item_id)
    _angebot_aendern(db, quote_id)
    assert "1 Gruppenbuchung" in _gesperrt(db, order_id)


def test_group_booking_alone_blocks():
    """Die Gruppenbuchung trägt die Position selbst (TimeEntryGroup.order_item_id, Fremdschlüssel) -- sie sperrt auch, wenn
    keine ihrer Einzelbuchungen (mehr) an der Position hängt."""
    from app.models import TimeEntry

    db = db_session()
    quote_id, order_id, employee_id = _welt(db)
    item_id = load_order(db, order_id).items[0].id
    gruppe = create_group_manual_entry(db, employee_ids=[employee_id], team_id=None, actor_employee_id=None, is_admin=True,
                                       order_id=order_id, work_date=date(2026, 9, 7), hours=Decimal("3"),
                                       order_item_id=item_id)
    for entry in db.scalars(select(TimeEntry).where(TimeEntry.order_item_id == item_id)):
        entry.order_item_id = None
    db.commit()
    _angebot_aendern(db, quote_id)
    assert _gesperrt(db, order_id) == (GESPERRT + "an den Positionen hängen 1 Gruppenbuchung. Änderungen (z. B. Nachträge) "
                                       "direkt am Auftrag erfassen.")
    assert gruppe.id


@pytest.mark.parametrize("bezug", ["position", "kalkulation"])
def test_work_preparation_material_blocks(bezug):
    """Material der Arbeitsvorbereitung entsteht aus der Kalkulation der Positionen und trägt die Disposition (Lieferant,
    Status, Lieferschein) -- es sperrt, ob es über die Position oder über die Materialzeile der Kalkulation hängt."""
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    item_id = load_order(db, order_id).items[0].id
    prep = WorkPreparation(order_id=order_id, status="offen")
    db.add(prep)
    db.flush()
    material = WorkPreparationMaterial(preparation_id=prep.id, name="Bitumenbahn", unit="m2")
    if bezug == "position":
        material.source_order_item_id = item_id
    else:
        calc = OrderItemCalculationSnapshot(order_item_id=item_id)
        db.add(calc)
        db.flush()
        snap = OrderItemMaterialSnapshot(calculation_id=calc.id, name="Bitumenbahn", unit="m2", quantity=Decimal("1"))
        db.add(snap)
        db.flush()
        material.source_material_snapshot_id = snap.id
    db.add(material)
    db.commit()
    _angebot_aendern(db, quote_id)
    assert "an den Positionen hängt Material der Arbeitsvorbereitung (1 Zeile)" in _gesperrt(db, order_id)


def test_work_preparation_without_material_allows_the_sync():
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    db.add(WorkPreparation(order_id=order_id, status="offen"))
    db.commit()
    _angebot_aendern(db, quote_id)
    _erlaubt(db, order_id)


def test_all_reasons_are_named_together():
    db = db_session()
    quote_id, order_id, employee_id = _welt(db)
    item_id = load_order(db, order_id).items[0].id
    _leistungsstand(db, order_id, "4")
    create_manual_entry(db, employee_id=employee_id, order_id=order_id, order_item_id=item_id,
                        work_date=date(2026, 9, 7), hours=Decimal("2"))
    load_order(db, order_id).status = "abgeschlossen"
    db.commit()
    _angebot_aendern(db, quote_id)
    assert _gesperrt(db, order_id) == (
        GESPERRT + "Der Auftrag ist abgeschlossen; an den Positionen hängen Rechnungen (1 Entwurf); an den Positionen hängen "
        "1 Zeitbuchung. Änderungen (z. B. Nachträge) direkt am Auftrag erfassen.")


def test_sync_with_subtitles_keeps_the_tree_under_sqlite():
    db = db_session()
    quote_id, order_id, _ = _welt(db, titel=True)
    _angebot_aendern(db, quote_id)
    order = _erlaubt(db, order_id)
    titel = {s.id: s for s in order.sections}
    assert sorted((s.section_number, titel[s.parent_id].section_number if s.parent_id else None)
                  for s in titel.values()) == [("01", None), ("01.01", "01")]


# ---------------------------------------------------------------------------
# Router und Auftragsseite
# ---------------------------------------------------------------------------

def test_router_answers_409_with_the_reason_and_changes_nothing(threaded_db_session, router_test_client):
    db = threaded_db_session
    quote_id, order_id, _ = _welt(db)
    _leistungsstand(db, order_id, "4")
    _angebot_aendern(db, quote_id)
    vorher, revisionen = _ids(db, order_id), db.scalar(select(func.count()).select_from(OrderRevision))
    client = router_test_client(db, orders_router)
    r = client.post(f"/api/orders/{order_id}/sync-source-quote", json={"reason": "Test"})
    assert r.status_code == 409
    assert r.json()["detail"].startswith(GESPERRT) and "1 Entwurf" in r.json()["detail"]
    db.expire_all()
    assert _ids(db, order_id) == vorher
    assert db.scalar(select(func.count()).select_from(OrderRevision)) == revisionen
    seite = client.get(f"/api/orders/{order_id}").json()
    assert seite["source_quote_in_sync"] is False and seite["source_quote_sync_blocked"] == r.json()["detail"]


def test_order_names_the_block_only_when_it_differs_from_the_quote():
    db = db_session()
    quote_id, order_id, _ = _welt(db)
    _leistungsstand(db, order_id, "4")
    daten = order_to_dict(load_order(db, order_id), db)
    assert daten["source_quote_in_sync"] is True and daten["source_quote_sync_blocked"] is None
    _angebot_aendern(db, quote_id)
    daten = order_to_dict(load_order(db, order_id), db)
    assert daten["source_quote_in_sync"] is False and daten["source_quote_sync_blocked"].startswith(GESPERRT)


def test_order_page_and_quote_editor_show_the_reason_instead_of_the_button():
    """Die Oberfläche bietet den Abgleich nicht an, wenn der Server einen Sperrgrund nennt (Klicktest:
    scripts/klicktest_abgleich_sperre.py)."""
    from pathlib import Path

    templates = Path(__file__).resolve().parent.parent / "app" / "templates"
    order_html = (templates / "order.html").read_text(encoding="utf-8")
    assert "order.source_quote_in_sync===false&&order.source_quote_sync_blocked" in order_html
    assert "esc(order.source_quote_sync_blocked)" in order_html
    editor = (templates / "quote_editor.html").read_text(encoding="utf-8")
    assert "existingOrder.source_quote_sync_blocked" in editor
