"""Version 1.9.114 (Stufe 5, R1, Punkt 4): Positionen eines Storno-Entwurfs und Positionen des Auftrags in der Schlussrechnung.

    F8   Ein Storno spiegelt die stornierte Rechnung: keine Position ändern (Ist, Texte), entfernen oder hinzufügen -- 409 mit Grund, nichts
         geändert (Server); die Seite zeigt im Storno-Entwurf kein Ist-Feld und weder „✎“ noch „✕“. Bis 1.9.113 rechnete PUT eine Position des
         Stornos neu (billed_* mit positivem Vorzeichen), der Storno stimmte danach nicht mehr mit seiner Rechnung überein.
    F9   In der Schlussrechnung stehen alle Positionen des Auftrags: eine Position des Auftrags lässt sich nicht entfernen (409); bis 1.9.113 ging
         das, und danach sperrte „es fehlen Positionen des Auftrags“ das Finalisieren, bis „Aus dem Auftrag aktualisieren“ sie wieder einfügte.
         Ist-Menge ändern bleibt; die Seite zeigt dort kein „✕“.
    Gegenprobe  Abschlag nach Leistungsstand: Ist ändern geht weiter; Rechnung aus Aufwand: eine freie Position entfernen geht weiter.
"""

import re
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.invoices import (
    InvoiceBlocked, compute_invoice_totals, create_abschlag_leistungsstand, create_schlussrechnung, create_storno_draft,
    update_invoice_item,
)
from app.models import Invoice, InvoiceItem
from app.routers.invoices import router as invoices_router
from tests.leistungszeitraum import festschreiben
from tests.test_v133_invoices import make_order_with_item

D = Decimal
VORLAGE = Path(__file__).resolve().parent.parent / "app" / "templates" / "invoice_detail.html"


def _festgeschrieben(db, ist="40"):
    order, _ = make_order_with_item(db)
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
    return order, festschreiben(db, invoice)


def _positionen(db, invoice_id):
    db.expire_all()
    return [(i.short_text, str(i.ist_quantity), str(i.billed_quantity), str(i.billed_total))
            for i in db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id).order_by(InvoiceItem.id))]


def test_storno_position_aendern_409_und_nichts_geaendert(threaded_db_session, router_test_client):
    db = threaded_db_session
    _, original = _festgeschrieben(db)
    storno = create_storno_draft(db, original)
    vorher = _positionen(db, storno.id)
    summe = compute_invoice_totals(db.get(Invoice, storno.id))["gross_total"]
    position = vorher and db.scalar(select(InvoiceItem.id).where(InvoiceItem.invoice_id == storno.id))
    client = router_test_client(db, invoices_router, role="buero_finanzen")
    for antwort in (client.put(f"/api/invoices/{storno.id}/items/{position}", json={"ist_quantity": "7"}),
                    client.put(f"/api/invoices/{storno.id}/items/{position}", json={"short_text": "anders"}),
                    client.delete(f"/api/invoices/{storno.id}/items/{position}")):
        assert antwort.status_code == 409, antwort.text
        assert "Storno" in antwort.json()["detail"]
    assert _positionen(db, storno.id) == vorher
    assert compute_invoice_totals(db.get(Invoice, storno.id))["gross_total"] == summe == -compute_invoice_totals(
        db.get(Invoice, original.id))["gross_total"]


def test_storno_position_hinzufuegen_409():
    from tests.test_v133_invoices import db_session
    db = db_session()
    order, original = _festgeschrieben(db)
    storno = create_storno_draft(db, original)
    item = order.items[0]
    from app.invoices import add_invoice_item
    try:
        add_invoice_item(db, db.get(Invoice, storno.id), short_text="x", long_text="", unit=item.unit, unit_price=item.unit_price,
                         ist_quantity=D("1"), source_order_item_id=item.id)
        raise AssertionError("Position am Storno angelegt")
    except InvoiceBlocked as e:
        assert "Storno" in str(e)
    assert len(_positionen(db, storno.id)) == 1


def test_schlussrechnung_position_des_auftrags_nicht_entfernbar(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    schluss = create_schlussrechnung(db, order)
    position = db.scalar(select(InvoiceItem.id).where(InvoiceItem.invoice_id == schluss.id))
    client = router_test_client(db, invoices_router, role="buero_finanzen")
    antwort = client.delete(f"/api/invoices/{schluss.id}/items/{position}")
    assert antwort.status_code == 409, antwort.text
    assert "Schlussrechnung" in antwort.json()["detail"]
    assert len(_positionen(db, schluss.id)) == 1
    assert client.put(f"/api/invoices/{schluss.id}/items/{position}", json={"ist_quantity": "0"}).status_code == 200  # Ist bleibt


def test_gegenprobe_abschlag_und_aufwand_bleiben_bearbeitbar(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    abschlag = create_abschlag_leistungsstand(db, order)
    position = db.scalar(select(InvoiceItem.id).where(InvoiceItem.invoice_id == abschlag.id))
    client = router_test_client(db, invoices_router, role="buero_finanzen")
    assert client.put(f"/api/invoices/{abschlag.id}/items/{position}", json={"ist_quantity": "12"}).status_code == 200
    assert client.delete(f"/api/invoices/{abschlag.id}/items/{position}").status_code == 200  # Abschlag: entfernen wie bisher


def test_seite_bietet_am_storno_und_an_der_schlussposition_nichts_an():
    """Die Seite fragt dieselben Regeln: im Storno-Entwurf weder Ist-Feld noch „✎“/„✕“, in der Schlussrechnung kein „✕“ an einer Position des
    Auftrags (das Verhalten im Browser prüft scripts/klicktest_storno_positionen.py)."""
    text = VORLAGE.read_text(encoding="utf-8")
    assert "const positionBearbeitbar=()=>bearbeitbar()&&invoice.invoice_type!=='storno';" in text
    assert "const positionEntfernbar=i=>positionBearbeitbar()&&!(invoice.invoice_type==='schluss'&&i.source_order_item_id!=null);" in text
    zeilen = re.findall(r"function renderQuantityRows.*?\n}", text, re.S)[0]
    assert "positionEntfernbar(i)?" in zeilen and 'onclick="removeItem(${i.id})"' in zeilen
