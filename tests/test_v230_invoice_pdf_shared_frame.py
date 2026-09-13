"""Version 1.3.7 -- zweite Etappe des PDF-Umbaus: die Rechnung wechselt auf den gemeinsamen
Rahmen (app/document_frame.py), Folgeseiten bekommen eine abschaltbare Wiederholungszeile.

Der Inhaltstest unten (test_invoice_pdf_contains_expected_content) ist bewusst VOR dem Umbau
geschrieben und muss unverändert grün bleiben, danach wie davor -- er prüft nur Teilstrings, die
mit dem Umbau selbst nichts zu tun haben (Rechnungsnummer, Kundenname, Positionen, Netto, Steuer,
Brutto, Zahlungsbedingungen), damit ein Fehler beim Rahmenumbau nicht unbemerkt bleibt. Angebot,
Auftrag und Einsatzbericht sind nicht Teil dieser Etappe -- ihre Tests bleiben unangetastet."""

import importlib.util
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v167_pagination import count_pdf_pages
from tests.test_v229_shared_document_layout import _run_migration_step

from app.database import Base
from app.invoices import add_invoice_item, create_schlussrechnung, finalize_and_send_invoice
from app.models import DocumentLayoutBlock


def _make_finalized_invoice(db, **kwargs):
    order, item = make_order_with_item(db, **kwargs)
    invoice = create_schlussrechnung(db, order)
    invoice = finalize_and_send_invoice(db, invoice)
    return invoice


def _make_finalized_multipage_invoice(db):
    """Viele zusätzliche Positionen (vor dem Finalisieren, solange die Rechnung noch im Entwurf
    editierbar ist) erzwingen einen echten Seitenumbruch."""
    order, item = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    for i in range(60):
        add_invoice_item(
            db, invoice, short_text=f"Zusatzposition {i}", long_text="", unit="Stk",
            unit_price=Decimal("10"), ist_quantity=Decimal("1"),
        )
    invoice = finalize_and_send_invoice(db, invoice)
    return invoice


def test_invoice_pdf_contains_expected_content():
    """Muss vor UND nach dem Rahmenumbau identisch grün sein (siehe Modul-Docstring)."""
    from app.invoice_pdf import build_invoice_pdf

    db = db_session()
    invoice = _make_finalized_invoice(db, quantity=Decimal("100"), unit_price=Decimal("50"))

    pdf_bytes = build_invoice_pdf(db, invoice)
    assert pdf_bytes[:4] == b"%PDF"
    text = _extract_pdf_text(pdf_bytes)

    assert invoice.invoice_number.encode("utf-8") in text
    assert invoice.customer_name.encode("utf-8") in text
    assert b"Dacheindeckung" in text  # Position
    assert b"5.000,00" in text  # Nettosumme: 100 * 50
    assert b"19" in text  # MwSt.-Satz
    assert b"5.950,00" in text  # Bruttobetrag: 5000 * 1.19
    assert b"Zahlungsbedingungen" in text


def _page_text(pdf_bytes: bytes, page_index: int) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_bytes)
    textpage = pdf[page_index].get_textpage()
    text = textpage.get_text_range(0, textpage.count_chars())
    textpage.close()
    pdf.close()
    return text


# ---------------------------------------------------------------------------
# Rahmen: invoice steht in RENDERERS_USING_SHARED_FRAME, nutzt denselben geteilten Satz wie die
# Mahnung
# ---------------------------------------------------------------------------

def test_invoice_is_registered_as_using_the_shared_frame():
    from app.document_frame import RENDERERS_USING_SHARED_FRAME

    assert "invoice" in RENDERERS_USING_SHARED_FRAME


def test_invoice_shares_background_and_margins_with_reminder_via_default():
    """Kein eigenes Briefpapier/eigene Ränder für die Rechnung -- beide Dokumenttypen lesen über
    denselben Rückfall (app/document_type_fallback.py) dieselbe "default"-Zeile."""
    from app.document_layout import get_effective_background, set_background
    from app.document_page_margins import get_margins

    db = db_session()
    set_background(db, "default", "geteiltes-briefpapier.jpg", page_type="first")
    assert get_effective_background(db, "invoice", "first").stored_filename == "geteiltes-briefpapier.jpg"
    assert get_effective_background(db, "reminder", "first").stored_filename == "geteiltes-briefpapier.jpg"

    invoice_margins = get_margins(db, "invoice", "first")
    reminder_margins = get_margins(db, "reminder", "first")
    assert invoice_margins.top_mm == reminder_margins.top_mm == Decimal("25.0")


# ---------------------------------------------------------------------------
# Wiederholungszeile auf Folgeseiten (seit 1.3.7)
# ---------------------------------------------------------------------------

def test_continuation_header_appears_only_on_later_pages_with_correct_page_count():
    from app.invoice_pdf import build_invoice_pdf

    db = db_session()
    invoice = _make_finalized_multipage_invoice(db)
    pdf_bytes = build_invoice_pdf(db, invoice)
    real_pages = count_pdf_pages(pdf_bytes)
    assert real_pages > 1

    # Die Fußzeile zeigt auf JEDER Seite "Seite N von M" (eigener, unabhängiger Baustein) --
    # das eindeutige Merkmal der Wiederholungszeile ist deshalb nicht das Seitenzahl-Format
    # selbst, sondern ihr Inline-Format "Label: Wert" (der Meta-Block auf Seite 1 rendert
    # Beschriftung/Wert als getrennte Tabellenzellen, nie mit einem echten ": " dazwischen).
    continuation_marker = f"Rechnungsnr.: {invoice.invoice_number}"
    first_page_text = _page_text(pdf_bytes, 0)
    assert continuation_marker not in first_page_text

    for page_index in range(1, real_pages):
        page_text = _page_text(pdf_bytes, page_index)
        assert continuation_marker in page_text
        assert f"Kunden-Nr.: {invoice.customer_number}" in page_text
        assert f"Seite {page_index + 1} von {real_pages}" in page_text


def test_continuation_header_can_be_disabled():
    from app.document_layout import ensure_default_layout, update_layout_block
    from app.invoice_pdf import build_invoice_pdf

    db = db_session()
    invoice = _make_finalized_multipage_invoice(db)

    block = next(b for b in ensure_default_layout(db, "invoice") if b.block_type == "continuation_header")
    update_layout_block(
        db, block, x_mm=block.x_mm, y_mm=block.y_mm, width_mm=block.width_mm, height_mm=block.height_mm,
        content=None, font_size=block.font_size, font_weight=block.font_weight, text_align=block.text_align,
        visible=False,
    )

    pdf_bytes = build_invoice_pdf(db, invoice)
    real_pages = count_pdf_pages(pdf_bytes)
    assert real_pages > 1
    continuation_marker = f"Rechnungsnr.: {invoice.invoice_number}"
    for page_index in range(1, real_pages):
        page_text = _page_text(pdf_bytes, page_index)
        assert continuation_marker not in page_text
        # Keine Seitenzahl mehr irgendeiner Form: die Fußzeile ist ein eigener, unabhängig
        # abschaltbarer Baustein und steht seit 1.3.8 standardmäßig ebenfalls aus (siehe
        # CLAUDE.md "Gemeinsamer Dokumenttyp") -- mit BEIDEN Bausteinen aus bleibt hier nichts.
        assert "Seite" not in page_text


def test_continuation_header_does_not_overlap_company_header_or_content():
    """Geometrische Invariante, analog zur 1.3.2-Regression bei der Mahnung: die Wiederholungszeile
    darf weder mit einem aktivierten company_header (y_mm/height_mm) noch mit dem Inhaltsbereich
    (margins.top_mm) kollidieren -- geprüft für die tatsächlichen Standardwerte, nicht nur
    behauptet. Seit 1.3.12 (CLAUDE.md "Einstellbare Position der Wiederholungszeile") liest diese
    Prüfung y_mm/height_mm direkt vom continuation_header-Block selbst, nicht mehr von der seither
    entfernten Konstante CONTINUATION_HEADER_Y_MM -- die Position ist jetzt editierbar, die
    Invariante muss deshalb für den JEWEILS KONFIGURIERTEN Wert gelten, nicht nur einen
    hartcodierten."""
    from app.document_layout import ensure_default_layout
    from app.document_page_margins import get_margins

    db = db_session()
    blocks = {b.block_type: b for b in ensure_default_layout(db, "invoice")}
    company_header = blocks["company_header"]
    continuation_header = blocks["continuation_header"]
    margins = get_margins(db, "invoice", "continuation")

    continuation_header_bottom_edge_mm = float(continuation_header.y_mm) + float(continuation_header.height_mm)
    assert continuation_header_bottom_edge_mm <= float(company_header.y_mm), (
        "Wiederholungszeile reicht bis in den company_header-Bereich hinein"
    )
    assert continuation_header_bottom_edge_mm <= float(margins.top_mm), (
        "Wiederholungszeile reicht bis in den Inhaltsbereich hinein"
    )


def test_continuation_header_vertical_position_is_configurable():
    """Punkt 1a der Anfrage: y_mm des bestehenden DocumentLayoutBlock wird jetzt tatsächlich
    gelesen (document_frame.py), statt ignoriert zu werden -- über dieselbe Oberfläche
    (PUT .../blocks/{id}) wie die Sichtbarkeit einstellbar, kein neues Feld nötig. Baut ein
    mehrseitiges PDF zweimal, einmal mit dem Standardwert, einmal mit einer stark abweichenden
    Position, und misst nach, dass die Zeile tatsächlich an der konfigurierten Stelle landet."""
    from app.document_layout import ensure_default_layout, update_layout_block
    from app.invoice_pdf import build_invoice_pdf

    db = db_session()
    invoice = _make_finalized_multipage_invoice(db)

    block = next(b for b in ensure_default_layout(db, "invoice") if b.block_type == "continuation_header")
    default_y = float(block.y_mm)
    pdf_before = build_invoice_pdf(db, invoice)

    new_y_mm = default_y + 15.0
    update_layout_block(
        db, block, x_mm=block.x_mm, y_mm=Decimal(str(new_y_mm)), width_mm=block.width_mm, height_mm=block.height_mm,
        content=None, font_size=block.font_size, font_weight=block.font_weight, text_align=block.text_align,
        visible=True,
    )
    pdf_after = build_invoice_pdf(db, invoice)

    def _row_y_mm(pdf_bytes: bytes) -> float:
        import pypdfium2 as pdfium
        mm_per_pt = 25.4 / 72.0
        pdf = pdfium.PdfDocument(pdf_bytes)
        textpage = pdf[1].get_textpage()  # erste Folgeseite
        try:
            searcher = textpage.search(f"Rechnungsnr.: {invoice.invoice_number}", match_case=False)
            result = searcher.get_next()
            searcher.close()
            idx, _count = result
            _left, bottom, _right, top = textpage.get_charbox(idx)
            return (297.0 - top * mm_per_pt)
        finally:
            textpage.close()
            pdf.close()

    y_before = _row_y_mm(pdf_before)
    y_after = _row_y_mm(pdf_after)
    assert abs(y_after - y_before - 15.0) < 1.0, (
        f"Zeile hätte sich um ~15mm nach unten verschieben müssen: vorher {y_before:.2f}mm, nachher {y_after:.2f}mm"
    )


# ---------------------------------------------------------------------------
# Migration 257fb2967c93: continuation_header-Zeile für bereits geseedete "default"-Installationen
# ---------------------------------------------------------------------------

def _load_migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_continuation_header_block_for_shared_*.py"))
    spec = importlib.util.spec_from_file_location("migration_1307_continuation_header", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _new_engine_with_schema():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_migration_adds_continuation_header_to_already_seeded_default_only():
    migration = _load_migration()
    engine = _new_engine_with_schema()
    Session = sessionmaker(bind=engine)
    db = Session()
    for block_type in ("logo", "company_header", "footer_text"):
        db.add(DocumentLayoutBlock(
            document_type="default", block_type=block_type, label=block_type,
            x_mm=Decimal(0), y_mm=Decimal(0), width_mm=Decimal(10), height_mm=Decimal(10),
            font_size=Decimal("9.5"), font_weight="normal", text_align="left", visible=True, sort_order=10,
        ))
    db.commit()
    db.close()

    _run_migration_step(engine, migration.upgrade)

    db = Session()
    default_blocks = db.scalars(select(DocumentLayoutBlock).where(DocumentLayoutBlock.document_type == "default")).all()
    assert {b.block_type for b in default_blocks} == {"logo", "company_header", "footer_text", "continuation_header"}
    db.close()


def test_migration_does_nothing_when_default_was_never_seeded():
    """Kein 'default' -> keine Zeile einfügen (sonst würde eine komplett frische Installation,
    die noch nie ensure_default_layout() aufgerufen hat, plötzlich eine einzelne, verwaiste
    continuation_header-Zeile bekommen)."""
    migration = _load_migration()
    engine = _new_engine_with_schema()

    _run_migration_step(engine, migration.upgrade)

    db = sessionmaker(bind=engine)()
    assert db.scalars(select(DocumentLayoutBlock)).all() == []
    db.close()


def test_migration_leaves_quote_blocks_untouched():
    migration = _load_migration()
    engine = _new_engine_with_schema()
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(DocumentLayoutBlock(
        document_type="quote", block_type="footer_text", label="Fußzeile",
        x_mm=Decimal(18), y_mm=Decimal(282), width_mm=Decimal(176), height_mm=Decimal(8),
        font_size=Decimal(8), font_weight="normal", text_align="left", visible=True, sort_order=10,
    ))
    db.commit()
    db.close()

    _run_migration_step(engine, migration.upgrade)

    db = Session()
    quote_blocks = db.scalars(select(DocumentLayoutBlock).where(DocumentLayoutBlock.document_type == "quote")).all()
    assert len(quote_blocks) == 1
    assert db.scalars(select(DocumentLayoutBlock).where(DocumentLayoutBlock.document_type == "default")).all() == []
    db.close()


def test_migration_downgrade_removes_only_continuation_header():
    migration = _load_migration()
    engine = _new_engine_with_schema()
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(DocumentLayoutBlock(
        document_type="default", block_type="footer_text", label="Fußzeile",
        x_mm=Decimal(18), y_mm=Decimal(282), width_mm=Decimal(176), height_mm=Decimal(8),
        font_size=Decimal(8), font_weight="normal", text_align="left", visible=True, sort_order=10,
    ))
    db.commit()
    db.close()

    _run_migration_step(engine, migration.upgrade)
    _run_migration_step(engine, migration.downgrade)

    db = Session()
    default_blocks = db.scalars(select(DocumentLayoutBlock).where(DocumentLayoutBlock.document_type == "default")).all()
    assert {b.block_type for b in default_blocks} == {"footer_text"}
    db.close()
