"""Letzte Etappe des PDF-Umbaus (seit 1.3.13, CLAUDE.md "Gemeinsamer Dokumenttyp" -- Angebot):
app/quote_framed_pdf.py ist der NEUE Renderer (render_framed_pdf(), document_type="quote").

Der reguläre PDF-Abruf (GET /api/quotes/{id}/pdf) und der E-Mail-Versand (send_quote_email(),
app/projects.py) nutzen ihn seither produktiv -- das sind die beiden Wege, die tatsächlich beim
Kunden ankommen. Seit 1.3.20 (Aufräumen nach dem PDF-Umbau) ist er der EINZIGE Angebots-Renderer:
der alte, positionsbasierte app/quote_layout_pdf.py (samt Vergleichsansicht
GET /api/quotes/{id}/pdf-layout-preview und dem PDF-Layout-Editor) sowie der älteste, einfache
fließende app/quote_pdf.py sind vollständig entfernt, ebenso "quote"s eigene Zeilen in
DocumentLayoutBlock/DocumentLayoutBackground/DocumentPageMargins -- "quote" liest seither wie
jeder andere Dokumenttyp über den "default"-Rückfall (siehe CLAUDE.md)."""

import importlib.util
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.document_frame import RENDERERS_USING_SHARED_FRAME
from app.document_layout import (
    ensure_default_layout, get_effective_background, set_background,
    set_background_repeat,
)
from app.document_page_margins import ensure_default_margins
from app.models import Customer, DocumentLayoutBlock, Project, Quote, QuoteItem, QuoteItemLayout, QuoteSection
from app.project_pipeline_columns import default_pipeline_column_id
from app.projects import load_quote
from app.quote_framed_pdf import _build_items_table, build_quote_framed_pdf
from app.settings import get_or_create_general_settings
from tests.test_v229_shared_document_layout import _run_migration_step

import pypdfium2 as pdfium


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_quote_with_item(db, quantity=Decimal("100"), unit_price=Decimal("50"), vat_rate=Decimal("19.00")):
    customer = Customer(name="Test Kunde", last_name="Test Kunde", street="Musterstr. 1", postal_code="12345", city="Musterstadt")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0001", name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    quote = Quote(quote_number="A-TEST-0001", project_id=project.id, title="Testangebot", vat_rate=vat_rate)
    db.add(quote)
    db.flush()
    item = QuoteItem(quote_id=quote.id, sort_order=10, position_number="1", short_text="Dacheindeckung", quantity=quantity, unit="m²", unit_price=unit_price)
    db.add(item)
    db.commit()
    db.refresh(quote)
    return quote, item


def _page_texts(pdf_bytes: bytes) -> list[str]:
    tmp = pdfium.PdfDocument(pdf_bytes)
    return [tmp[i].get_textpage().get_text_bounded() for i in range(len(tmp))]


# ---------------------------------------------------------------------------
# Grundlegendes
# ---------------------------------------------------------------------------

def test_build_quote_framed_pdf_produces_valid_pdf():
    db = db_session()
    quote, _ = make_quote_with_item(db)
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 500


def test_quote_registered_in_shared_frame():
    """render_framed_pdf() lehnt jeden nicht eingetragenen document_type ab (siehe
    app/document_frame.py) -- ohne diesen Eintrag würde build_quote_framed_pdf() bei jedem
    Aufruf sofort mit ValueError abbrechen."""
    assert "quote" in RENDERERS_USING_SHARED_FRAME


def test_framed_pdf_content_matches_expected_fields():
    db = db_session()
    quote, item = make_quote_with_item(db, quantity=Decimal("10"), unit_price=Decimal("12.50"))
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    text = _page_texts(pdf_bytes)[0]
    assert "A-TEST-0001" in text
    assert "Testangebot" in text
    assert "Test Kunde" in text
    assert "Dacheindeckung" in text
    assert "125,00 EUR" in text  # Zeilensumme (10 * 12,50)


# ---------------------------------------------------------------------------
# Spaltenüberschrift "Pos." statt "OZ" (seit 1.3.16, Betreiberwunsch, einheitlich mit Auftrag/
# Rechnung) und schmalere OZ-Spalte zugunsten von "Leistung" (Positionsnummern sind höchstens
# 7 Zeichen lang, siehe app/quote_framed_pdf.py::ITEMS_COL_WIDTHS_MM).
# ---------------------------------------------------------------------------

def test_items_table_header_says_pos_not_oz():
    db = db_session()
    quote, _ = make_quote_with_item(db)
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    text = _page_texts(pdf_bytes)[0]
    assert "Pos." in text
    assert "OZ" not in text


def test_oz_column_narrower_leaves_more_room_for_leistung():
    """Geometrische Prüfung statt nur der Konstante: die "Leistung"-Spalte muss durch die
    schmalere OZ-Spalte tatsächlich weiter links beginnen als bei der alten 23mm-OZ-Breite.

    Seit 1.3.17 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot, Punkt 2) steht "Leistung" nicht
    mehr direkt hinter "Pos.", sondern hinter Pos.+Menge+EH (neue Spaltenreihenfolge) -- die
    erwartete Position verschiebt sich dadurch entsprechend nach rechts, unabhängig von der
    OZ-Breite selbst."""
    from app.quote_framed_pdf import ITEMS_COL_WIDTHS_MM
    assert ITEMS_COL_WIDTHS_MM["oz"] == 15  # vorher 23mm

    db = db_session()
    quote, _ = make_quote_with_item(db)
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    doc = pdfium.PdfDocument(pdf_bytes)
    tp = doc[0].get_textpage()
    text = tp.get_text_bounded()
    idx = text.index("Leistung")
    left_pt, *_ = tp.get_charbox(idx)
    left_mm = left_pt / (72.0 / 25.4)
    # Linker Rand (17mm) + Pos./Menge/EH-Spaltenbreiten (15+18+14=47mm) ergeben eine
    # Spaltengrenze bei 64mm, plus "Leistung"s eigenes, ungenulltes linkes Zellenpolster
    # (reportlab-Standard 6pt/2,12mm) -- rund 66mm, Toleranzband fuer Messungenauigkeiten der
    # Zeichenbox.
    assert 64.0 <= left_mm <= 70.0, f"'Leistung' beginnt bei {left_mm:.1f}mm, erwartet 64-70mm"


# ---------------------------------------------------------------------------
# 1.3.17, Punkt 1+2: Waehrung nur noch im Spaltenkopf, Menge/EH vor Leistung
# ---------------------------------------------------------------------------

def test_currency_removed_from_item_values_kept_in_headers_and_totals():
    """Seit 1.3.17 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Angebot, Punkt 1): "EP/EUR"/"GP/EUR"
    tragen die Einheit im Spaltenkopf, die Zellwerte selbst sind waehrungslos. Zwei Positionen mit
    unterschiedlichen Betraegen, damit der Zeilenwert eindeutig vom (weiterhin "EUR" tragenden)
    Summenblock unterscheidbar bleibt."""
    db = db_session()
    quote, _ = make_quote_with_item(db, quantity=Decimal("3"), unit_price=Decimal("7"))
    second = QuoteItem(quote_id=quote.id, sort_order=20, position_number="2", short_text="Zweite Position", quantity=Decimal("1"), unit="Stk", unit_price=Decimal("50"))
    db.add(second)
    db.commit()
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    text = _page_texts(pdf_bytes)[0]

    assert "EP/EUR" in text
    assert "GP/EUR" in text
    assert "21,00 EUR" not in text  # Zeilensumme (3*7) ohne Waehrungssuffix
    assert "50,00 EUR" not in text
    assert "21,00" in text and "50,00" in text
    assert "71,00 EUR" in text  # Nettosumme (21+50) behaelt die Waehrung im Summenblock


def test_menge_and_eh_columns_appear_before_leistung_column():
    """Seit 1.3.17, Punkt 2: neue Spaltenreihenfolge Pos., Menge, EH, Leistung, EP/EUR, GP/EUR."""
    db = db_session()
    quote, _ = make_quote_with_item(db)
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    doc = pdfium.PdfDocument(pdf_bytes)
    tp = doc[0].get_textpage()
    text = tp.get_text_bounded()
    pos_left, *_ = tp.get_charbox(text.index("Pos."))
    menge_left, *_ = tp.get_charbox(text.index("Menge Einh."))
    leistung_left, *_ = tp.get_charbox(text.index("Leistung"))
    assert pos_left < menge_left < leistung_left


def test_menge_right_aligned_and_eh_left_aligned_with_small_gap():
    """Menge rechtsbündig, EH linksbündig direkt daneben (Punkt 2) -- sichtbarer, aber kleiner
    Zwischenraum, damit z.B. "1,00" und "m²" wie eine zusammengehörige Einheit wirken, ohne
    aneinanderzukleben."""
    db = db_session()
    # qty() kuerzt nachlaufende Nullen (siehe app/document_pdf.py::qty()) -- "1,25" statt "1,00",
    # damit die Nadel tatsaechlich im PDF vorkommt.
    quote, _ = make_quote_with_item(db, quantity=Decimal("1.25"), unit_price=Decimal("10"))
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    doc = pdfium.PdfDocument(pdf_bytes)
    tp = doc[0].get_textpage()
    text = tp.get_text_bounded()
    qty_idx = text.index("1,25")
    unit_idx = text.index("m²")
    _, _, qty_right, _ = tp.get_charbox(qty_idx + len("1,25") - 1)
    unit_left, *_ = tp.get_charbox(unit_idx)
    mm_per_pt = 25.4 / 72.0
    gap_mm = (unit_left - qty_right) * mm_per_pt
    assert 0.3 < gap_mm < 3.0, f"Abstand Menge/EH={gap_mm:.2f}mm"


# ---------------------------------------------------------------------------
# Übertragszeile -- echte, neue Funktion (weder alter noch bisheriger neuer Renderer hatte je
# einen Betrag am Seitenumbruch, nur eine statische Fortsetzungs-Beschriftung).
# ---------------------------------------------------------------------------

def _make_multi_section_quote(db):
    """60 Positionen à 125,00 EUR unter Abschnitt 1, 30 Positionen à 40,00 EUR unter Abschnitt 2 --
    lang genug, um über mehrere Seiten umzubrechen, sowohl MITTEN in einer Positionsgruppe als
    auch GENAU zwischen zwei Abschnittstiteln."""
    customer = Customer(name="Test Kunde GmbH", last_name="Test Kunde GmbH", street="Musterstr. 1", postal_code="12345", city="Musterstadt")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0001", name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    quote = Quote(quote_number="A-TEST-0002", project_id=project.id, title="Großes Testangebot", vat_rate=Decimal("19.00"))
    db.add(quote)
    db.flush()
    section1 = QuoteSection(quote_id=quote.id, parent_id=None, title="Dacheindeckung", sort_order=10, section_number="1")
    section2 = QuoteSection(quote_id=quote.id, parent_id=None, title="Dachentwaesserung", sort_order=20, section_number="2")
    db.add_all([section1, section2])
    db.flush()

    for i in range(1, 61):
        item = QuoteItem(quote_id=quote.id, sort_order=i * 10, position_number=str(i), short_text=f"Position {i}: Dachlattung", quantity=Decimal("10"), unit="m", unit_price=Decimal("12.50"))
        db.add(item)
        db.flush()
        db.add(QuoteItemLayout(quote_item_id=item.id, section_id=section1.id, sort_order=i * 10, include_in_total=True))
    for i in range(61, 91):
        item = QuoteItem(quote_id=quote.id, sort_order=i * 10, position_number=str(i), short_text=f"Position {i}: Fallrohr", quantity=Decimal("5"), unit="m", unit_price=Decimal("8.00"))
        db.add(item)
        db.flush()
        db.add(QuoteItemLayout(quote_item_id=item.id, section_id=section2.id, sort_order=i * 10, include_in_total=True))
    db.commit()
    db.refresh(quote)
    return quote


def test_carry_forward_line_matches_across_page_breaks_with_correct_amounts():
    db = db_session()
    quote = _make_multi_section_quote(db)
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    pages = _page_texts(pdf_bytes)
    assert len(pages) > 1  # die eigentliche Voraussetzung fuer diesen Test

    carried_out_values = []
    carried_in_values = []
    for i, text in enumerate(pages):
        if "Übertrag auf nächste Seite" in text:
            idx = text.find("Übertrag auf nächste Seite")
            snippet = text[idx:idx + 60]
            carried_out_values.append((i, snippet))
        if "Übertrag von vorheriger Seite" in text:
            idx = text.find("Übertrag von vorheriger Seite")
            snippet = text[idx:idx + 60]
            carried_in_values.append((i, snippet))

    assert carried_out_values, "keine Übertragszeile gefunden -- Test setzt zu wenige Positionen voraus?"
    assert len(carried_out_values) == len(carried_in_values)

    def amount_str(snippet: str) -> str:
        # "Übertrag auf nächste Seite 1.875,00 EUR" -- der Betrag ist der Rest nach dem Text.
        for prefix in ("Übertrag auf nächste Seite ", "Übertrag von vorheriger Seite "):
            if snippet.startswith(prefix):
                return snippet[len(prefix):].split("\r")[0].split("\n")[0].strip()
        raise AssertionError(snippet)

    for (page_out, out_snippet), (page_in, in_snippet) in zip(carried_out_values, carried_in_values):
        assert page_in == page_out + 1, "Übertrag von vorheriger Seite muss auf der UNMITTELBAR folgenden Seite stehen"
        assert amount_str(out_snippet) == amount_str(in_snippet), "derselbe Betrag muss auf beiden Seiten des Umbruchs stehen"

    # Der erste Übertrag muss unabhängig von etwaigen Rundungsfragen ein Vielfaches von 12,50 sein
    # (jede Position in Abschnitt 1 kostet exakt 125,00 EUR).
    first_value = Decimal(amount_str(carried_out_values[0][1]).replace(".", "").replace(",", ".").replace(" EUR", ""))
    assert first_value % Decimal("12.50") == 0
    assert Decimal("0") < first_value <= Decimal("7500")  # Abschnitt 1 hat max. 60 * 125,00 EUR


def test_carry_forward_excludes_optional_items_from_running_total():
    """Ein Übertrag muss dieselbe Netto-Logik verwenden wie der Summenblock: optionale
    Positionen (include_in_total=False) tragen nichts zur laufenden Summe bei."""
    from app.document_pdf import build_styles
    styles = build_styles()

    items_by_section = {None: [
        {"position_number": "1", "gaeb_oz": None, "short_text": "Pflicht", "long_text": None,
         "include_in_total": True, "quantity": Decimal("1"), "unit": "Stk", "unit_price": Decimal("100"), "line_total": Decimal("100")},
        {"position_number": "2", "gaeb_oz": None, "short_text": "Optional", "long_text": None,
         "include_in_total": False, "quantity": Decimal("1"), "unit": "Stk", "unit_price": Decimal("500"), "line_total": Decimal("500")},
        {"position_number": "3", "gaeb_oz": None, "short_text": "Wieder Pflicht", "long_text": None,
         "include_in_total": True, "quantity": Decimal("1"), "unit": "Stk", "unit_price": Decimal("20"), "line_total": Decimal("20")},
    ]}
    col_widths = [23, 82, 18, 14, 23, 25]

    def carry_row_builder(label, value, widths):
        from app.quote_framed_pdf import _build_carry_row
        return _build_carry_row(label, value, widths, styles)

    table = _build_items_table(items_by_section, {}, styles, col_widths, carry_row_builder)
    assert table is not None
    # row_cumulative[i] entspricht Koerperzeile i (0=Pflicht/100, 1=Optional/weiterhin 100, 2=Wieder Pflicht/120).
    assert table._row_cumulative == [Decimal("100"), Decimal("100"), Decimal("120")]


# ---------------------------------------------------------------------------
# Zeilenumbruch-Variante für lange Positionstexte (echter Fund an A-2026-0016: große Leerräume
# am Seitenende, weil reportlab eine Tabellenzeile nur als Ganzes umbrechen kann, siehe CLAUDE.md
# "Gemeinsamer Dokumenttyp"/Angebot) -- jede Position ist jetzt eine unteilbare Kopfzeile PLUS
# eine eigene Zeile je durch "\n" getrenntem Absatz im Langtext.
# ---------------------------------------------------------------------------

def _make_items_by_section_with_long_text(long_text: str, *, include_in_total=True):
    from app.document_pdf import build_styles
    styles = build_styles()
    items_by_section = {None: [{
        "position_number": "1", "gaeb_oz": "01.0010", "short_text": "Kurztext", "long_text": long_text,
        "include_in_total": include_in_total, "quantity": Decimal("1"), "unit": "Stk",
        "unit_price": Decimal("10"), "line_total": Decimal("10"),
    }]}
    col_widths = [23, 82, 18, 14, 23, 25]
    return styles, items_by_section, col_widths


def _no_op_carry_row_builder(label, value, widths):
    from app.quote_framed_pdf import _build_carry_row
    from app.document_pdf import build_styles
    return _build_carry_row(label, value, widths, build_styles())


def test_long_text_with_newlines_becomes_separate_continuation_rows():
    long_text = "Erster Absatz.\nZweiter Absatz.\nDritter Absatz."
    styles, items_by_section, col_widths = _make_items_by_section_with_long_text(long_text)
    table = _build_items_table(items_by_section, {}, styles, col_widths, _no_op_carry_row_builder)
    assert table is not None
    # Spaltenkopf + 1 Kopfzeile der Position + 3 Fortsetzungszeilen (eine je Absatz) = 5 Zeilen --
    # vorher wäre der komplette Langtext EIN Paragraph innerhalb der Kopfzeile gewesen (2 Zeilen).
    assert len(table._cellvalues) == 5
    assert table._row_kind == [
        ("header", "01.0010"), ("continuation", "01.0010"), ("continuation", "01.0010"), ("continuation", "01.0010"),
    ]


def test_long_text_without_newlines_stays_a_single_continuation_row():
    """Bekannte, akzeptierte Lücke (siehe CLAUDE.md, "Bekannte, bewusst offene Punkte"): ein
    Langtext ganz ohne eingebettete Zeilenumbrüche bleibt eine einzige, unteilbare Zeile."""
    styles, items_by_section, col_widths = _make_items_by_section_with_long_text("Durchgehender Fließtext ohne Umbruch.")
    table = _build_items_table(items_by_section, {}, styles, col_widths, _no_op_carry_row_builder)
    assert len(table._cellvalues) == 3  # Spaltenkopf + Kopfzeile + genau 1 Fortsetzungszeile
    assert table._row_kind[1] == ("continuation", "01.0010")


def test_item_without_long_text_has_no_continuation_rows():
    styles, items_by_section, col_widths = _make_items_by_section_with_long_text(None)
    table = _build_items_table(items_by_section, {}, styles, col_widths, _no_op_carry_row_builder)
    assert len(table._cellvalues) == 2  # nur Spaltenkopf + Kopfzeile, unverändert wie vor 1.3.15


def test_split_injects_continuation_marker_when_landing_mid_position():
    """Direkter Test von split() -- reserviert bewusst wenig Höhe, sodass der Umbruch mitten in
    den Fortsetzungszeilen der einzigen Position landet, statt an ihrem Kopf."""
    from reportlab.lib.units import mm as _mm
    from app.quote_framed_pdf import _build_continuation_marker_row

    long_text = "\n".join(f"Absatz {i}." for i in range(1, 15))
    styles, items_by_section, col_widths = _make_items_by_section_with_long_text(long_text)
    col_widths_mm = [w * _mm for w in col_widths]

    def marker_builder(position_label, widths):
        return _build_continuation_marker_row(position_label, widths, styles)

    table = _build_items_table(items_by_section, {}, styles, col_widths_mm, _no_op_carry_row_builder, marker_builder)
    assert table is not None

    # Klein genug, dass nur die Kopfzeile und ein paar Fortsetzungszeilen passen, aber nicht alle.
    pieces = table.split(200 * _mm, 40 * _mm)
    # [top, carry_out, PageBreak, carry_in, marker, bottom] -- die Fortsetzungs-Kennzeichnung ist
    # das sechste Element und existiert nur, WEIL der Umbruch hier tatsächlich mitten in den
    # Fortsetzungszeilen landet (siehe Kennzeichnung von bottom._row_kind[0] unten).
    assert len(pieces) == 6
    top, carry_out, page_break, carry_in, marker, bottom = pieces
    assert isinstance(bottom, type(table))
    # Seit 1.3.17: die Fortsetzungs-Kennzeichnung sitzt in der Leistungsspalte, jetzt Index 3
    # (Pos., Menge, EH, Leistung, EP/EUR, GP/EUR) statt vorher Index 1.
    assert "Fortsetzung zu Position 01.0010" in marker._cellvalues[0][3].text
    # bottom's erste "echte" Zeile (nach der wiederholten Kopfzeile) muss eine Fortsetzungszeile
    # sein, sonst waere der Test nicht aussagekraeftig (Umbruch waere an der Positionsgrenze).
    assert bottom._row_kind[0] == ("continuation", "01.0010")


def test_full_pdf_shows_continuation_marker_for_split_long_text():
    """Ende-zu-Ende: ein Langtext mit vielen Absätzen, lang genug, um über einen echten
    Seitenumbruch zu laufen -- die Fortsetzungsseite muss den Hinweis zeigen, MIT der korrekten
    Positionsnummer, nicht als eigenständige Zeile ohne Bezug."""
    db = db_session()
    quote, item = make_quote_with_item(db)
    long_text = "\n".join(f"Dies ist Absatz Nummer {i} mit etwas Text zur Fuellung." for i in range(1, 60))
    item.long_text = long_text
    item.gaeb_oz = "01.0010"
    db.commit()
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    pages = _page_texts(pdf_bytes)
    assert len(pages) > 1, "Testvoraussetzung: der lange Text muss tatsächlich umbrechen"
    marker_pages = [p for p in pages if "Fortsetzung zu Position 01.0010" in p]
    assert marker_pages, "kein Seitenumbruch landete innerhalb der Fortsetzungszeilen -- Testdaten anpassen"


# ---------------------------------------------------------------------------
# Übertrag auf derselben Seite statt an der Seitengrenze (echter Fund an A-2026-0016, zehn
# Seiten) -- Frame.add() platziert jedes zurückgegebene split()-Element dort, wo gerade noch
# Platz ist; reichte nach carry_out_row noch Raum, landete carry_in_row fälschlich ebenfalls auf
# der alten Seite statt am Kopf der neuen. Ein PageBreak() zwischen beiden erzwingt den Wechsel.
# ---------------------------------------------------------------------------

def test_split_forces_page_break_between_carry_out_and_carry_in_row():
    """Direkter Test von split() selbst -- unabhängig davon, ob im konkreten Fall zufällig genug
    oder zu wenig Restplatz für beide Zeilen auf der alten Seite übrig wäre (genau das machte
    den Fehler in der echten Rendering-Prüfung zunächst unbemerkt: das synthetische Testangebot
    hatte an der Umbruchstelle keinen Spielraum)."""
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak
    from app.document_pdf import build_styles

    styles = build_styles()
    items_by_section = {None: [
        {"position_number": str(i), "gaeb_oz": None, "short_text": f"Position {i}", "long_text": None,
         "include_in_total": True, "quantity": Decimal("1"), "unit": "Stk", "unit_price": Decimal("10"), "line_total": Decimal("10")}
        for i in range(1, 21)
    ]}
    col_widths = [23 * mm, 82 * mm, 18 * mm, 14 * mm, 23 * mm, 25 * mm]

    def carry_row_builder(label, value, widths):
        from app.quote_framed_pdf import _build_carry_row
        return _build_carry_row(label, value, widths, styles)

    table = _build_items_table(items_by_section, {}, styles, col_widths, carry_row_builder)
    assert table is not None

    # Grosszuegig bemessene availHeight, die nach dem Reservieren einer Zeile immer noch
    # deutlich mehr Restplatz laesst als eine zweite, winzige Uebertragszeile brauchen wuerde --
    # exakt die Bedingung, unter der beide Zeilen ohne PageBreak faelschlich zusammen auf der
    # alten Seite gelandet waeren.
    pieces = table.split(180 * mm, 60 * mm)
    assert len(pieces) == 5
    top, carry_out, page_break, carry_in, bottom = pieces
    assert isinstance(page_break, PageBreak)
    assert carry_out is not carry_in


# ---------------------------------------------------------------------------
# Doppelte Inhalte (echte Funde an A-2026-0016) -- Kundenname/Ansprechpartner identisch,
# outro_text/outro_text_2 identisch.
# ---------------------------------------------------------------------------

def test_contact_person_line_suppressed_when_identical_to_customer_name():
    db = db_session()
    quote, _ = make_quote_with_item(db)
    quote.project.customer.contact_person = quote.project.customer.name
    db.commit()
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    text = _page_texts(pdf_bytes)[0]
    assert text.count("Test Kunde") == 1


def test_contact_person_line_kept_when_different_from_customer_name():
    db = db_session()
    quote, _ = make_quote_with_item(db)
    quote.project.customer.contact_person = "Erika Musterfrau"
    db.commit()
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    text = _page_texts(pdf_bytes)[0]
    assert "Test Kunde" in text
    assert "Erika Musterfrau" in text


def test_outro_text_2_suppressed_when_identical_to_outro_text():
    from app.document_pdf import build_payment_tax_closing_block, build_styles
    styles = build_styles()
    same_text = "Wir freuen uns auf die Zusammenarbeit."
    story = build_payment_tax_closing_block(styles, outro_text=same_text, outro_text_2=same_text)
    paragraphs_text = [getattr(f, "text", "") for f in story]
    occurrences = sum(1 for t in paragraphs_text if "freuen uns" in t)
    assert occurrences == 1


def test_outro_text_2_kept_when_different_from_outro_text():
    from app.document_pdf import build_payment_tax_closing_block, build_styles
    styles = build_styles()
    story = build_payment_tax_closing_block(styles, outro_text="Erster Satz.", outro_text_2="Zweiter, anderer Satz.")
    paragraphs_text = [getattr(f, "text", "") for f in story]
    assert any("Erster Satz" in t for t in paragraphs_text)
    assert any("Zweiter, anderer Satz" in t for t in paragraphs_text)


# ---------------------------------------------------------------------------
# Briefpapier auf Folgeseiten -- get_effective_background() muss repeat_on_every_page auf der
# "first"-Zeile ehren, wenn keine eigene "continuation"-Zeile existiert. Ursprünglich (1.3.13)
# gegen "quote" getestet (der damals einzige Dokumenttyp, der diesen Altbestandsfall auslöste);
# seit 1.3.20 hat "quote" keine eigenen Zeilen mehr (siehe CLAUDE.md "Gemeinsamer Dokumenttyp"/
# Aufräumen nach dem PDF-Umbau) -- der generische Mechanismus selbst bleibt unverändert relevant
# und wird jetzt direkt gegen "default" geprüft.
# ---------------------------------------------------------------------------

def test_effective_background_falls_back_to_first_page_when_repeat_enabled(tmp_path, monkeypatch):
    import app.document_layout_background as background_storage
    monkeypatch.setattr(background_storage, "BACKGROUND_ROOT", tmp_path / "layout_backgrounds")

    db = db_session()
    stored = background_storage.replace_background(None, "briefbogen.png", bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
        "de0000000c4944415408d763f8ffff3f0005fe02fea739669d0000000049454e44ae426082"
    ))
    row = set_background(db, "default", stored, page_type="first")
    assert row.repeat_on_every_page is True  # Standardwert

    effective = get_effective_background(db, "default", "continuation")
    assert effective is not None
    assert effective.stored_filename == stored


def test_effective_background_no_fallback_when_repeat_disabled(tmp_path, monkeypatch):
    import app.document_layout_background as background_storage
    monkeypatch.setattr(background_storage, "BACKGROUND_ROOT", tmp_path / "layout_backgrounds")

    db = db_session()
    stored = background_storage.replace_background(None, "briefbogen.png", bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
        "de0000000c4944415408d763f8ffff3f0005fe02fea739669d0000000049454e44ae426082"
    ))
    set_background(db, "default", stored, page_type="first")
    set_background_repeat(db, "default", False, page_type="first")

    assert get_effective_background(db, "default", "continuation") is None


def test_effective_background_prefers_own_continuation_row_over_fallback(tmp_path, monkeypatch):
    """Existiert bereits eine eigene Folgeseiten-Zeile, hat sie IMMER Vorrang -- der Rueckfall
    greift nur, wenn fuer page_type='continuation' wirklich keine Zeile existiert."""
    import app.document_layout_background as background_storage
    monkeypatch.setattr(background_storage, "BACKGROUND_ROOT", tmp_path / "layout_backgrounds")

    db = db_session()
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
        "de0000000c4944415408d763f8ffff3f0005fe02fea739669d0000000049454e44ae426082"
    )
    stored_first = background_storage.replace_background(None, "seite1.png", png)
    stored_cont = background_storage.replace_background(None, "folgeseiten.png", png)
    set_background(db, "default", stored_first, page_type="first")
    set_background(db, "default", stored_cont, page_type="continuation")

    effective = get_effective_background(db, "default", "continuation")
    assert effective.stored_filename == stored_cont


# ---------------------------------------------------------------------------
# Wiederholungszeile auf Folgeseiten (Nutzeranforderung: "mit sechzehn Seiten das mit Abstand
# längste Dokument -- wenn irgendwo eine Fortsetzungszeile gebraucht wird, dann dort") -- Migration
# ab5eef23f9ed ergänzt den vierten Rahmen-Baustein für die bereits bestehenden "quote"-Zeilen,
# denselben Standardwert (12mm/4mm) wie DEFAULT_SHARED_LAYOUT seit 1.3.12.
#
# _HISTORICAL_QUOTE_LAYOUT_BEFORE_1_3_13 ist eine eingefrorene Kopie der damaligen
# DEFAULT_QUOTE_LAYOUT-Konstante (zehn Bausteine, vor der Migration) -- die Konstante selbst
# wurde beim Aufräumen nach dem PDF-Umbau (1.3.20, CLAUDE.md "Gemeinsamer Dokumenttyp") aus
# app/document_layout.py entfernt, da "quote" seither keine eigenen Bausteine mehr hat. Diese
# Migration muss aber weiterhin gegen den Datenbankzustand testbar bleiben, den sie zum Zeitpunkt
# ihrer Erstellung tatsächlich vorfand -- deshalb hier bewusst als lokale, historische
# Testfixtur hartkodiert statt einen inzwischen entfernten Import zu erwarten.
_HISTORICAL_QUOTE_LAYOUT_BEFORE_1_3_13 = [
    ("logo", "Firmenlogo", 155, 10, 35, 20, 9.5, "normal", "left", False),
    ("company_header", "Firmenkopf", 18, 17, 176, 22, 9.5, "normal", "left", True),
    ("customer_address", "Kundenadresse", 18, 42, 70, 28, 9.5, "normal", "left", True),
    ("meta_table", "Meta-Tabelle (Angebotsnr., Datum, ...)", 92, 42, 102, 28, 9.5, "normal", "left", True),
    ("object_address", "Objektanschrift", 18, 73, 176, 10, 9.5, "normal", "left", True),
    ("title_intro", "Titel & Vortext", 18, 86, 176, 18, 9.5, "normal", "left", True),
    ("items_table", "Positionsliste", 18, 107, 176, 120, 8, "normal", "left", True),
    ("totals", "Summenblock", 18, 230, 176, 18, 9, "normal", "left", True),
    ("payment_tax_closing", "Zahlungsbedingungen, Steuerhinweis, Schlusstexte", 18, 250, 176, 25, 9.5, "normal", "left", True),
    ("footer_text", "Fußzeile (Geschäftsführung, Bank, USt-ID)", 18, 282, 176, 8, 8, "normal", "left", True),
]


def _load_quote_continuation_header_migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_continuation_header_block_for_quote.py"))
    spec = importlib.util.spec_from_file_location("migration_1313_quote_continuation_header", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_adds_continuation_header_to_already_seeded_quote_only():
    migration = _load_quote_continuation_header_migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    for i, (block_type, label, x, y, w, h, fs, fw, align, visible) in enumerate(_HISTORICAL_QUOTE_LAYOUT_BEFORE_1_3_13):
        db.add(DocumentLayoutBlock(
            document_type="quote", block_type=block_type, label=label,
            x_mm=Decimal(x), y_mm=Decimal(y), width_mm=Decimal(w), height_mm=Decimal(h),
            font_size=Decimal(str(fs)), font_weight=fw, text_align=align, visible=visible,
            sort_order=(i + 1) * 10,
        ))
    # Andere Dokumenttypen (hier: "default") dürfen von dieser Migration nicht berührt werden.
    db.add(DocumentLayoutBlock(
        document_type="default", block_type="footer_text", label="Fußzeile",
        x_mm=Decimal(0), y_mm=Decimal(0), width_mm=Decimal(10), height_mm=Decimal(10),
        font_size=Decimal("8"), font_weight="normal", text_align="left", visible=False, sort_order=10,
    ))
    db.commit()
    db.close()

    _run_migration_step(engine, migration.upgrade)

    db = Session()
    quote_blocks = db.scalars(select(DocumentLayoutBlock).where(DocumentLayoutBlock.document_type == "quote")).all()
    assert {b.block_type for b in quote_blocks} == {
        "logo", "company_header", "customer_address", "meta_table", "object_address",
        "title_intro", "items_table", "totals", "payment_tax_closing", "footer_text",
        "continuation_header",
    }
    new_block = [b for b in quote_blocks if b.block_type == "continuation_header"][0]
    assert (new_block.y_mm, new_block.height_mm, new_block.visible) == (Decimal("12"), Decimal("4"), True)

    default_blocks = db.scalars(select(DocumentLayoutBlock).where(DocumentLayoutBlock.document_type == "default")).all()
    assert {b.block_type for b in default_blocks} == {"footer_text"}  # unberührt
    db.close()


def test_migration_is_idempotent_and_downgrade_removes_the_row():
    migration = _load_quote_continuation_header_migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    for i, (block_type, label, x, y, w, h, fs, fw, align, visible) in enumerate(_HISTORICAL_QUOTE_LAYOUT_BEFORE_1_3_13):
        db.add(DocumentLayoutBlock(
            document_type="quote", block_type=block_type, label=label,
            x_mm=Decimal(x), y_mm=Decimal(y), width_mm=Decimal(w), height_mm=Decimal(h),
            font_size=Decimal(str(fs)), font_weight=fw, text_align=align, visible=visible,
            sort_order=(i + 1) * 10,
        ))
    db.commit()
    db.close()

    _run_migration_step(engine, migration.upgrade)
    _run_migration_step(engine, migration.upgrade)  # zweiter Aufruf darf keine Dublette anlegen

    db = Session()
    matches = db.scalars(select(DocumentLayoutBlock).where(
        DocumentLayoutBlock.document_type == "quote", DocumentLayoutBlock.block_type == "continuation_header",
    )).all()
    assert len(matches) == 1
    db.close()

    _run_migration_step(engine, migration.downgrade)
    db = Session()
    assert db.scalar(select(DocumentLayoutBlock).where(
        DocumentLayoutBlock.document_type == "quote", DocumentLayoutBlock.block_type == "continuation_header",
    )) is None
    db.close()


def test_continuation_header_block_is_seeded_by_ensure_default_layout_for_fresh_installation():
    """Eine komplett frische Installation (kein Migrationslauf) braucht die Migration nicht --
    DEFAULT_SHARED_LAYOUT selbst enthält den Baustein bereits. Seit 1.3.20 hat "quote" keine
    eigenen Bausteine mehr (CLAUDE.md "Gemeinsamer Dokumenttyp"/Aufräumen nach dem PDF-Umbau) --
    ensure_default_layout(db, "quote") faellt deshalb auf den geteilten, vier Bausteine
    umfassenden Satz zurueck, statt (wie vor 1.3.20) elf eigene Bausteine zu seeden."""
    db = db_session()
    blocks = ensure_default_layout(db, "quote")
    assert len(blocks) == 4
    header = [b for b in blocks if b.block_type == "continuation_header"][0]
    assert (header.y_mm, header.height_mm, header.visible) == (Decimal("12"), Decimal("4"), True)


def test_continuation_header_default_position_does_not_overlap_continuation_margin():
    """Geometrische Invariante wie bei den anderen Dokumenttypen (CLAUDE.md, Abschnitt
    "Einstellbare Position der Wiederholungszeile"): der Standardwert darf den fließenden Inhalt
    auf Folgeseiten nicht überlappen -- y_mm + height_mm muss unterhalb des oberen Randes für
    page_type='continuation' liegen. Seit 1.3.20 ueber den "default"-Rueckfall geprueft (siehe
    oben) -- derselbe Baustein/dieselben Randwerte, die "quote" jetzt ueber den Rueckfall liest."""
    db = db_session()
    blocks = ensure_default_layout(db, "quote")
    header = [b for b in blocks if b.block_type == "continuation_header"][0]
    margins = ensure_default_margins(db, "quote", "continuation")
    assert margins.top_mm >= header.y_mm + header.height_mm


def test_framed_pdf_shows_continuation_header_content_only_on_later_pages():
    db = db_session()
    quote = _make_multi_section_quote(db)
    loaded = load_quote(db, quote.id)
    pdf_bytes = build_quote_framed_pdf(db, loaded)
    pages = _page_texts(pdf_bytes)
    assert len(pages) > 1

    assert "Angebotsnr.: A-TEST-0002" not in pages[0].replace("\r", "").replace("\n", "")
    for page_text in pages[1:]:
        normalized = page_text.replace("\r", " ").replace("\n", " ")
        assert "A-TEST-0002" in normalized
        assert "P-TEST-0001" in normalized


# ---------------------------------------------------------------------------
# Punkt 4: Umstellung des regulären PDF-Abrufs (GET /api/quotes/{id}/pdf) auf den neuen
# Renderer -- echter Routen-Test über router_test_client() statt nur eines direkten
# Funktionsaufrufs, damit auch eine tatsächliche URL-Auflösung geprüft ist (Muster seit 1.2.15).
# ---------------------------------------------------------------------------

def test_quote_pdf_endpoint_uses_new_renderer(threaded_db_session, router_test_client):
    from app.routers.quotes import router as quotes_router
    db = threaded_db_session
    quote = _make_multi_section_quote(db)
    client = router_test_client(db, quotes_router)

    resp = client.get(f"/api/quotes/{quote.id}/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    # "Übertrag" gibt es ausschließlich im neuen Renderer (siehe app/quote_framed_pdf.py) --
    # eindeutiger Beleg, dass dieser Endpunkt tatsächlich darüber läuft, nicht nur "irgendein PDF".
    pages = _page_texts(resp.content)
    assert any("bertrag" in p for p in pages)


# ---------------------------------------------------------------------------
# Aufräumen nach dem PDF-Umbau (seit 1.3.20, CLAUDE.md "Gemeinsamer Dokumenttyp"): "quote" hat
# keine eigenen Zeilen in DocumentLayoutBlock/DocumentLayoutBackground/DocumentPageMargins mehr,
# sondern nimmt wie jeder andere Dokumenttyp am "default"-Rückfall teil (eine Migration hat die
# zuvor eigenständigen Zeilen gelöscht). Belegt per Textextraktion + Seitenzahl, dass das
# Ergebnis unverändert bleibt.
# ---------------------------------------------------------------------------

def test_quote_pdf_identical_whether_quote_has_its_own_rows_or_falls_back_to_default():
    """Simuliert beide Zustände nebeneinander: eine Datenbank, in der "quote" (wie vor der
    1.3.20-Migration) eigene Zeilen trägt, gegen eine Datenbank, in der ausschließlich "default"
    Zeilen trägt und "quote" darüber den Rückfall nutzt. Beide müssen bei identischer
    Konfiguration (Ränder, Briefpapier, Sichtbarkeit der gezeichneten Bausteine) exakt denselben
    Text auf exakt derselben Seitenzahl liefern -- das ist die eigentliche Zusicherung der
    Zusammenführung: der Rückfall verändert das Ergebnis nicht, er ändert nur, WO die Werte
    liegen.

    company_header/logo werden hier explizit auf visible=False gesetzt, nicht dem Standardwert
    überlassen: das entspricht dem tatsächlichen Effekt, den vor 1.3.20 der seither entfernte
    suppress_drawn_blocks-Parameter erzwang (quote's eigene, historische company_header-Zeile
    stand auf visible=True, wurde aber vom neuen Renderer unabhängig davon unterdrückt) -- ein
    Vergleich mit der rohen, unsuppressed historischen Einstellung wäre kein fairer Vergleich
    zum tatsächlich vor der Migration ausgelieferten Ergebnis."""
    from app.document_layout import update_layout_block
    from app.document_page_margins import update_margins

    def render_with_settings_on(document_type_for_settings: str) -> list[str]:
        db = db_session()
        import app.document_layout_background as background_storage
        stored = background_storage.replace_background(None, "briefbogen.png", bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
            "de0000000c4944415408d763f8ffff3f0005fe02fea739669d0000000049454e44ae426082"
        ))
        set_background(db, document_type_for_settings, stored, page_type="first")
        update_margins(db, document_type_for_settings, "first", top_mm=Decimal("25"), bottom_mm=Decimal("32"), left_mm=Decimal("17"), right_mm=Decimal("17"))
        update_margins(db, document_type_for_settings, "continuation", top_mm=Decimal("40"), bottom_mm=Decimal("32"), left_mm=Decimal("17"), right_mm=Decimal("17"))
        for block in ensure_default_layout(db, document_type_for_settings):
            if block.block_type in ("logo", "company_header", "footer_text"):
                update_layout_block(
                    db, block, x_mm=block.x_mm, y_mm=block.y_mm, width_mm=block.width_mm, height_mm=block.height_mm,
                    content=None, font_size=block.font_size, font_weight=block.font_weight,
                    text_align=block.text_align, visible=False,
                )

        quote, _ = make_quote_with_item(db, quantity=Decimal("7"), unit_price=Decimal("13"))
        loaded = load_quote(db, quote.id)
        return _page_texts(build_quote_framed_pdf(db, loaded))

    before_pages = render_with_settings_on("quote")  # "quote" hat eigene Zeilen (Stand vor 1.3.20)
    after_pages = render_with_settings_on("default")  # "quote" hat keine, "default" trägt sie

    assert len(before_pages) == len(after_pages)
    assert before_pages == after_pages
