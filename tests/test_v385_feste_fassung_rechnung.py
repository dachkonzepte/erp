"""Feste Fassung der Rechnung (seit 1.8.82, R4a Punkt 1, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung 1.8.82").

Das PDF jeder Rechnung (jede Art, auch Storno) entsteht beim Festschreiben im selben Commit und liegt ab dann mit SHA-256 in der
Ablage (app/invoices.py::_store_fixed_pdf(), Invoice.pdf_document_id). Danach nie neu erzeugt: Download, Versand und nachgetragene
Zustellung nehmen genau diese Bytes (app/sent_documents.py::frozen_version()), auch nach einem geänderten Briefkopf und vor dem
ersten Versand; eine veränderte oder fehlende Datei wird nicht still ersetzt (409/410). Scheitert das PDF oder die Ablage, ist die
Rechnung nicht festgeschrieben (keine Nummer verbraucht). Einmal gesetzt, steht der Verweis fest (ORM-Sperre). Rechnungen von vor
1.8.82 (ohne feste Fassung) behalten die alte Regel -- tests/test_v323_dispatch_completion.py::vor_1_8_82().

Gleichzeitig (PostgreSQL, opt-in): zwei gleichzeitige Festschreiben desselben Entwurfs ergeben eine Nummer und eine Fassung."""

import os
import stat
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

import app.invoice_pdf as invoice_pdf_module
from app.invoices import (
    create_abschlag_leistungsstand, create_abschlag_pauschal, create_invoice_from_time_entries, create_schlussrechnung,
    create_storno_draft, finalize_and_send_invoice, send_invoice_email, update_invoice_item,
)
from app.models import ArchiveImmutableError, EmailDispatch, Invoice, NumberSequence, SentDocument
from app.routers.email_dispatches import router as dispatches_router
from app.routers.invoices import router as invoices_router
from app.sent_documents import read_sent_document
from app.settings import load_general_settings
from tests.leistungszeitraum import festschreiben, mit_zeitraum
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v231_invoice_item_table_width_and_quantity import _extract_pdf_text
from tests.test_v321_email_dispatch import FakeSMTP, _archive_path, _attachment, _configure_graph, _configure_smtp, graph, smtp  # noqa: F401
from tests.test_v324_dispatch_history_and_delivery import _manual
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

ALT, NEU = "Briefkopf Alt GmbH", "Briefkopf Neu GmbH"


def _briefkopf(db, name):
    load_general_settings(db).company_name = name
    db.commit()


def _leistungsstand(db, order, ist="40"):
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=Decimal(ist))
    return invoice


def _aufwand(db, order):
    material = SimpleNamespace(material_id=None, description="Kehlblech", unit="Stk.", quantity=Decimal("2"))
    invoice = create_invoice_from_time_entries(db, order, [], [material])
    item = invoice.items[0]
    update_invoice_item(db, invoice, item, unit_price=Decimal("30"))
    return invoice


def _dokumente(db):
    return list(db.scalars(select(SentDocument).order_by(SentDocument.id)))


def _nummer(db):
    return db.scalar(select(NumberSequence.next_value).where(NumberSequence.sequence_key == "invoice"))


# ---------------------------------------------------------------------------
# Festschreiben legt die Fassung ab
# ---------------------------------------------------------------------------

ARTEN = {
    "abschlag_pauschal": lambda db, order: create_abschlag_pauschal(db, order, lump_sum_net=Decimal("2000")),
    "abschlag_leistungsstand": _leistungsstand,
    "schluss": lambda db, order: create_schlussrechnung(db, order),
    "aufwand": _aufwand,
}


@pytest.mark.parametrize("art", sorted(ARTEN))
def test_every_kind_gets_its_fixed_pdf_when_finalized(art):
    db = db_session()
    order, _ = make_order_with_item(db)
    _briefkopf(db, ALT)
    entwurf = ARTEN[art](db, order)
    assert entwurf.pdf_document_id is None
    invoice = festschreiben(db, entwurf)
    [doc] = _dokumente(db)
    assert invoice.pdf_document_id == doc.id
    assert (doc.document_type, doc.document_id, doc.document_number, doc.filename) == (
        "rechnung", invoice.id, invoice.invoice_number, f"{invoice.invoice_number}.pdf")
    content = read_sent_document(doc)  # Prüfsumme stimmt
    text = _extract_pdf_text(content)
    assert invoice.invoice_number.encode() in text and ALT.encode() in text
    assert invoice.invoice_date.strftime("%d.%m.%Y").encode() in text  # der Tag des Festschreibens


def test_the_cancellation_gets_its_own_fixed_pdf_and_the_original_keeps_its_own():
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = festschreiben(db, _leistungsstand(db, order))
    original_doc = abschlag.pdf_document_id
    storno = festschreiben(db, create_storno_draft(db, abschlag))
    db.refresh(abschlag)
    assert abschlag.status == "storniert" and abschlag.pdf_document_id == original_doc  # unverändert
    assert storno.pdf_document_id not in (None, original_doc)
    assert b"Stornierung zu Rechnung " + abschlag.invoice_number.encode() in _extract_pdf_text(read_sent_document(storno.pdf_document))


def test_a_draft_has_no_fixed_pdf_and_its_download_is_built_fresh(router_test_client, threaded_db_session):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    entwurf = create_schlussrechnung(db, order)
    client = router_test_client(db, invoices_router, role="buero_auftrag")
    response = client.get(f"/api/invoices/{entwurf.id}/pdf")
    assert response.status_code == 200 and "X-DK-Ablage" not in response.headers
    assert b"Entwurf" in _extract_pdf_text(response.content) and _dokumente(db) == []


# ---------------------------------------------------------------------------
# Danach nie neu erzeugt: Download, Versand, Zustellung
# ---------------------------------------------------------------------------

def test_download_and_first_dispatch_after_a_letterhead_change_are_the_fixed_pdf(router_test_client, threaded_db_session, smtp):
    """Briefkopf nach dem Festschreiben, vor dem ersten Versand geändert: Download und Mail tragen den alten -- bis 1.8.81
    entstand das PDF bis zum ersten Versand neu, mit dem Briefkopf von heute."""
    db = threaded_db_session
    _configure_smtp(db)
    order, _ = make_order_with_item(db)
    _briefkopf(db, ALT)
    invoice = festschreiben(db, create_schlussrechnung(db, order))
    fassung = read_sent_document(invoice.pdf_document)
    _briefkopf(db, NEU)
    client = router_test_client(db, invoices_router, role="buero_auftrag")
    download = client.get(f"/api/invoices/{invoice.id}/pdf")
    assert download.status_code == 200 and download.content == fassung
    assert download.headers["X-DK-Ablage"] == str(invoice.pdf_document_id)
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="fassung-versand-0001")
    gesendet = _attachment(smtp.sent[0]["message"])
    assert gesendet == fassung and ALT.encode() in _extract_pdf_text(gesendet)
    [row] = db.scalars(select(EmailDispatch)).all()
    assert row.sent_document_id == invoice.pdf_document_id and len(_dokumente(db)) == 1  # nichts neu abgelegt


def test_a_failed_first_dispatch_does_not_touch_the_fixed_pdf(db_session, graph):
    """Bis 1.8.81 machte erst ein nicht fehlgeschlagener Versand eine Fassung maßgeblich -- jetzt ist sie es vom Festschreiben an."""
    db = db_session
    _configure_graph(db)
    order, _ = make_order_with_item(db)
    invoice = festschreiben(db, create_schlussrechnung(db, order))
    graph.fail_status = 503
    with pytest.raises(ValueError):
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="fassung-fehl-0001")
    graph.fail_status = None
    send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="fassung-fehl-0002")
    failed, sent = db.scalars(select(EmailDispatch).order_by(EmailDispatch.id)).all()
    assert failed.sent_document_id == sent.sent_document_id == invoice.pdf_document_id and len(_dokumente(db)) == 1


def test_a_manual_delivery_refers_to_the_fixed_pdf(router_test_client, threaded_db_session):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    invoice = festschreiben(db, create_schlussrechnung(db, order))
    office = router_test_client(db, dispatches_router, role="buero_finanzen")  # seit 1.9.111: Geld nur Admin und Büro – Finanzen
    response = _manual(office, "rechnung", invoice.id, key="fassung-manuell-0001")
    assert response.status_code == 200, response.text
    [row] = db.scalars(select(EmailDispatch)).all()
    assert row.sent_document_id == invoice.pdf_document_id and len(_dokumente(db)) == 1


@pytest.mark.parametrize("schaden,status", [("veraendert", 409), ("fehlt", 410)])
def test_a_damaged_fixed_pdf_is_neither_downloaded_nor_sent_nor_rebuilt(router_test_client, threaded_db_session, smtp,
                                                                         schaden, status):
    """Angriff: die Datei der festen Fassung verändert bzw. gelöscht -- nie still neu erzeugt (auch nicht vor dem ersten Versand)."""
    db = threaded_db_session
    _configure_smtp(db)
    order, _ = make_order_with_item(db)
    invoice = festschreiben(db, create_schlussrechnung(db, order))
    path = _archive_path(invoice.pdf_document)
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    if schaden == "fehlt":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes().replace(b"%PDF", b"%PDX", 1))
    client = router_test_client(db, invoices_router, role="buero_auftrag")
    response = client.get(f"/api/invoices/{invoice.id}/pdf")
    assert response.status_code == status and "nicht mehr unversehrt" in response.json()["detail"]
    with pytest.raises(ValueError) as exc:
        send_invoice_email(db, invoice, to_email="kunde@example.com", dispatch_key="fassung-schaden-0001")
    assert "nicht mehr unversehrt" in str(exc.value)
    assert smtp.sent == [] and db.scalars(select(EmailDispatch)).all() == [] and len(_dokumente(db)) == 1


def test_the_reference_to_the_fixed_pdf_cannot_be_changed_or_removed():
    """Angriff über das ORM: der Verweis steht fest -- weder auf ein anderes Dokument noch zurück auf leer."""
    db = db_session()
    order, _ = make_order_with_item(db)
    invoice = festschreiben(db, create_schlussrechnung(db, order))
    fremd = festschreiben(db, create_storno_draft(db, invoice)).pdf_document_id
    for wert in (fremd, None):
        invoice = db.get(Invoice, invoice.id)
        invoice.pdf_document_id = wert
        with pytest.raises(ArchiveImmutableError):
            db.commit()
        db.rollback()
    assert db.get(Invoice, invoice.id).pdf_document_id not in (None, fremd)


# ---------------------------------------------------------------------------
# Ohne PDF kein Festschreiben
# ---------------------------------------------------------------------------

def _scheitert(*args, **kwargs):
    raise RuntimeError("Renderer kaputt")


@pytest.mark.parametrize("wo", ["pdf", "ablage"])
def test_without_a_fixed_pdf_nothing_is_finalized_and_no_number_is_used(monkeypatch, wo):
    db = db_session()
    order, _ = make_order_with_item(db)
    entwurf = mit_zeitraum(db, create_schlussrechnung(db, order))
    vorher = _nummer(db)
    if wo == "pdf":
        monkeypatch.setattr(invoice_pdf_module, "build_invoice_pdf", _scheitert)
    else:
        import app.sent_documents as sent_documents_module
        monkeypatch.setattr(sent_documents_module, "store_sent_document", _scheitert)
    with pytest.raises(ValueError) as exc:
        finalize_and_send_invoice(db, entwurf)
    assert "nicht festgeschrieben" in str(exc.value)
    db.expire_all()
    invoice = db.get(Invoice, entwurf.id)
    assert (invoice.status, invoice.invoice_number, invoice.pdf_document_id) == ("entwurf", None, None)
    assert _nummer(db) == vorher and _dokumente(db) == []
    monkeypatch.undo()
    assert festschreiben(db, invoice).invoice_number  # danach geht es, mit der Nummer, die frei geblieben ist


def test_the_finalize_route_answers_400_without_a_fixed_pdf(router_test_client, threaded_db_session, monkeypatch):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    entwurf = mit_zeitraum(db, create_schlussrechnung(db, order))
    monkeypatch.setattr(invoice_pdf_module, "build_invoice_pdf", _scheitert)
    client = router_test_client(db, invoices_router, role="buero_finanzen")  # seit 1.9.111: Geld nur Admin und Büro – Finanzen
    response = client.post(f"/api/invoices/{entwurf.id}/send")
    assert response.status_code == 400 and "nicht festgeschrieben" in response.json()["detail"]
    assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.status != "entwurf")) == 0


# ---------------------------------------------------------------------------
# Gleichzeitig: PostgreSQL
# ---------------------------------------------------------------------------

def test_postgresql_two_finalizes_at_once_give_one_number_and_one_fixed_pdf(pg):
    Session, order_id = pg
    from app.models import Order
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, create_schlussrechnung(s, s.get(Order, order_id))).id)
    first, second = _run(Session, lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number,
                         lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)))
    assert isinstance(second, ValueError) and "Nur Rechnungen im Entwurf" in str(second), second
    stand = _vorbereiten(Session, lambda s: (
        s.get(Invoice, invoice_id).invoice_number, s.get(Invoice, invoice_id).pdf_document_id,
        [(d.id, d.document_id) for d in s.scalars(select(SentDocument))]))
    assert stand[0] == first and stand[2] == [(stand[1], invoice_id)]
    content = _vorbereiten(Session, lambda s: read_sent_document(s.get(SentDocument, stand[1])))
    assert first.encode() in _extract_pdf_text(content)


def test_postgresql_the_fixed_pdf_shows_the_state_after_a_waiting_edit(pg):
    """Das Festschreiben wartet auf eine laufende Änderung und legt deren Stand als Fassung ab."""
    Session, order_id = pg
    from app.models import Order
    invoice_id = _vorbereiten(Session, lambda s: mit_zeitraum(s, _leistungsstand(s, s.get(Order, order_id), "4")).id)

    def aendern(s):
        invoice = s.get(Invoice, invoice_id)
        return update_invoice_item(s, invoice, invoice.items[0], short_text="Geänderte Leistung XY") and "geaendert"

    _, second = _run(Session, aendern, lambda s: finalize_and_send_invoice(s, s.get(Invoice, invoice_id)).invoice_number)
    assert isinstance(second, str), second
    content = _vorbereiten(Session, lambda s: read_sent_document(s.get(Invoice, invoice_id).pdf_document))
    assert "Geänderte Leistung XY".encode("latin-1") in _extract_pdf_text(content) or b"Leistung XY" in _extract_pdf_text(content)
