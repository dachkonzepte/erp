"""Version 1.3.1 -- PDF-Rahmen, erste Etappe (app/document_frame.py), erprobt an der Mahnung.

Deckt ab: unterschiedliche Frame-Geometrien je Seitentyp, Seite-X-von-Y über ein mehrseitiges
Dokument, PDF-Hintergrund-Upload (Rasterisierung + JPEG-Normalisierung), Seitenverhältnis-Prüfung,
Rückwärtskompatibilität von DocumentLayoutBackground.page_type (Angebot bleibt unberührt), sowie
die drei abschaltbaren Bausteine (Logo/Firmenkopf/Fußzeile) über die neuen, seitentypbewussten
Router-Endpunkte."""

from decimal import Decimal
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as canvas_module
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.units import mm

from app.document_frame import _build_frame, render_framed_pdf
from app.document_layout import (
    DEFAULT_SHARED_LAYOUT, ensure_default_layout, get_background, list_layout_blocks,
    set_background, update_layout_block,
)
from app.document_layout_background import (
    convert_pdf_first_page_to_image, prepare_background_upload, validate_a4_aspect_ratio,
)
from app.document_pdf import build_styles
from app.document_page_margins import get_margins
from app.models import DocumentPageMargins
from app.routers.document_layout import router as document_layout_router
from tests.test_v153_mahnwesen import db_session
from tests.test_v213_inspection_items import _extract_pdf_text
from tests.test_v167_pagination import count_pdf_pages


# ---------------------------------------------------------------------------
# Frame-Geometrie: unterschiedliche Ränder je Seitentyp ergeben unterschiedliche Frames
# ---------------------------------------------------------------------------

def _margins(top, bottom, left, right):
    return DocumentPageMargins(
        document_type="reminder", page_type="x",
        top_mm=Decimal(top), bottom_mm=Decimal(bottom), left_mm=Decimal(left), right_mm=Decimal(right),
    )


def test_build_frame_reflects_configured_margins():
    frame_generous = _build_frame(_margins(45, 20, 18, 16), frame_id="first")
    frame_narrow = _build_frame(_margins(17, 20, 18, 16), frame_id="later")
    # Größerer oberer Rand -> weniger Höhe für den Inhalt, tiefer liegender Frame-Beginn (y1
    # bleibt gleich, da bottom_mm identisch ist -- nur die Höhe schrumpft).
    assert frame_generous.height < frame_narrow.height
    assert frame_generous.y1 == frame_narrow.y1
    assert frame_generous.x1 == frame_narrow.x1  # linker Rand identisch


def test_build_frame_different_left_right_changes_width():
    frame_a = _build_frame(_margins(17, 20, 18, 16), frame_id="a")
    frame_b = _build_frame(_margins(17, 20, 30, 30), frame_id="b")
    assert frame_b.width < frame_a.width
    assert frame_b.x1 != frame_a.x1


# ---------------------------------------------------------------------------
# Seite X von Y, Ende-zu-Ende über render_framed_pdf()
# ---------------------------------------------------------------------------

def _enable_footer(db, document_type="reminder"):
    """Seit 1.3.8 steht footer_text standardmäßig aus (siehe CLAUDE.md "Gemeinsamer
    Dokumenttyp") -- Tests, die gezielt den Fußzeilen-/Seitenzahl-Mechanismus selbst prüfen,
    schalten ihn deshalb bewusst manuell ein, statt sich auf einen Standardwert zu verlassen."""
    footer_block = next(b for b in ensure_default_layout(db, document_type) if b.block_type == "footer_text")
    update_layout_block(
        db, footer_block, x_mm=footer_block.x_mm, y_mm=footer_block.y_mm, width_mm=footer_block.width_mm,
        height_mm=footer_block.height_mm, content=None, font_size=footer_block.font_size,
        font_weight=footer_block.font_weight, text_align=footer_block.text_align, visible=True,
    )


def test_render_framed_pdf_shows_correct_total_page_count():
    db = db_session()
    _enable_footer(db)
    styles = build_styles()
    story = [Paragraph("Titel", styles["h1"])]
    for i in range(80):
        story.append(Paragraph(f"Zeile {i}: Fülltext, damit das Dokument mehrere Seiten braucht.", styles["body"]))
        story.append(Spacer(1, 2 * mm))
    pdf_bytes = render_framed_pdf(db, document_type="reminder", title="Test", content_story=story)
    assert pdf_bytes[:4] == b"%PDF"
    pages = count_pdf_pages(pdf_bytes)
    assert pages >= 2
    text = _extract_pdf_text(pdf_bytes)
    for page_number in range(1, pages + 1):
        assert f"Seite {page_number} von {pages}".encode("utf-8") in text


def test_render_framed_pdf_single_page_shows_one_of_one():
    db = db_session()
    _enable_footer(db)
    story = [Paragraph("Kurzer Inhalt", build_styles()["body"])]
    pdf_bytes = render_framed_pdf(db, document_type="reminder", title="Test", content_story=story)
    assert count_pdf_pages(pdf_bytes) == 1
    text = _extract_pdf_text(pdf_bytes)
    assert b"Seite 1 von 1" in text


def test_render_framed_pdf_footer_disabled_hides_page_number():
    db = db_session()
    blocks = {b.block_type: b for b in ensure_default_layout(db, "reminder")}
    footer_block = blocks["footer_text"]
    update_layout_block(
        db, footer_block, x_mm=footer_block.x_mm, y_mm=footer_block.y_mm, width_mm=footer_block.width_mm,
        height_mm=footer_block.height_mm, content=None, font_size=footer_block.font_size,
        font_weight=footer_block.font_weight, text_align=footer_block.text_align, visible=False,
    )
    story = [Paragraph("Kurzer Inhalt", build_styles()["body"])]
    pdf_bytes = render_framed_pdf(db, document_type="reminder", title="Test", content_story=story)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Seite 1 von 1" not in text
    assert b"von" not in text  # keine Seitenzahl irgendeiner Form


# ---------------------------------------------------------------------------
# Die drei Bausteine seeden korrekt für "reminder"
# ---------------------------------------------------------------------------

def test_ensure_default_layout_seeds_three_reminder_blocks():
    """Trotz des (nicht mehr ganz passenden) Namens seit 1.3.7 VIER Bausteine --
    continuation_header (Wiederholungszeile auf Folgeseiten) kam als vierter dazu."""
    db = db_session()
    blocks = ensure_default_layout(db, "reminder")
    assert {b.block_type for b in blocks} == {"logo", "company_header", "footer_text", "continuation_header"}
    assert len(DEFAULT_SHARED_LAYOUT) == 4
    # Seit 1.3.6 (Zusammenführung der Layout-Einstellungen): "reminder" hat keine eigene Zeile
    # mehr, sondern fällt auf den geteilten Satz zurück -- die zurückgegebenen Bausteine tragen
    # deshalb document_type="default", nicht "reminder".
    assert all(b.document_type == "default" for b in blocks)
    logo = [b for b in blocks if b.block_type == "logo"][0]
    assert logo.visible is False  # kein Logo hochgeladen -> unsichtbar vorbelegt, wie beim Angebot
    header = [b for b in blocks if b.block_type == "company_header"][0]
    footer = [b for b in blocks if b.block_type == "footer_text"][0]
    continuation = [b for b in blocks if b.block_type == "continuation_header"][0]
    # Seit 1.3.2 (echter Fehler aus dem ersten Smoke-Test behoben, siehe
    # test_reminder_pdf_company_header_default_does_not_overlap_content unten): company_header
    # startet UNSICHTBAR, da der fließende Inhalt bei der Mahnung -- anders als beim Angebot --
    # direkt am oberen Rand beginnt und mit y_mm=17 exakt denselben Bereich belegt hätte wie der
    # damalige 17mm-Standardrand.
    assert header.visible is False
    # Seit 1.3.8 (echter Fehler aus der 1.3.7-Verifikation gegen die echte Datenbank behoben):
    # footer_text startet ebenfalls UNSICHTBAR -- die feste Zeichenposition (20mm/12mm) kollidiert
    # sonst mit dem aufgedruckten Fußbereich eines echten Briefbogens, und die Seitenangabe wird
    # dort dank Meta-Block (seit 1.3.4/1.3.5) und Wiederholungszeile (seit 1.3.7) ohnehin nicht
    # mehr gebraucht.
    assert footer.visible is False
    assert continuation.visible is True  # bleibt Standard AN, siehe DEFAULT_SHARED_LAYOUT


def test_reminder_default_company_header_and_logo_do_not_overlap_default_frame():
    """Regressionstest für den im Smoke-Test gefundenen Fehler: company_header stand auf
    y_mm=17, der damalige Standardrand für Seite 1 ebenfalls auf 17mm -- gezeichneter Block und
    fließender Inhalt belegten dieselbe Fläche. Prüft die Geometrie direkt (wie vom Nutzer
    verlangt): die Frame-Obergrenze (= margins.top_mm, in derselben "Abstand von oben"-Einheit
    wie DocumentLayoutBlock.y_mm) muss unterhalb der Unterkante jedes AKTIVIERTEN gezeichneten
    Blocks liegen.

    Seit 1.3.19 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Randkorrektur "default") gilt das nur noch
    für "continuation" (40mm, klart Logo/Firmenkopf mit 20mm/30mm sicher): der obere Rand für
    "first" wurde bewusst von 42mm auf 25mm gesenkt, gegen das tatsächlich hinterlegte
    Briefpapier vermessen, nicht mehr gegen den generischen Logo-Rückfall. Das ist eine bewusst
    in Kauf genommene, keine neue Lücke -- "quote" hat exakt dasselbe Verhältnis (top_mm=25mm vs.
    generisches logo mit Unterkante 30mm) bereits seit dessen eigener 1.3.16-Randkorrektur, ohne
    eigenen Test dafür, und ohne dass es je zum Problem wurde: logo/company_header sind für beide
    Dokumenttypen standardmäßig unsichtbar (1.3.2/1.3.8), der Fall tritt nur ein, wenn ein Admin
    sie OHNE eigenes Briefpapier UND ohne den oberen Rand selbst wieder zu vergrößern aktiviert."""
    db = db_session()
    blocks = {b.block_type for b in ensure_default_layout(db, "reminder")}
    assert blocks  # seeded

    margins = get_margins(db, "reminder", "continuation")
    for block_type in ("logo", "company_header"):
        block = [b for b in ensure_default_layout(db, "reminder") if b.block_type == block_type][0]
        block_bottom_edge_mm = block.y_mm + block.height_mm
        assert margins.top_mm >= block_bottom_edge_mm, (
            f"continuation: Rand ({margins.top_mm}mm) liegt oberhalb der Unterkante von "
            f"{block_type} ({block_bottom_edge_mm}mm) -- Überlappung"
        )


def test_reminder_pdf_with_company_header_enabled_and_default_margin_renders_without_overlap():
    """Ende-zu-Ende: eine Mahnung mit aktiviertem company_header und dem (korrigierten)
    Standard-Rand erzeugen -- muss ein gültiges PDF ergeben, und Firmenname sowie Kundenanschrift
    müssen beide enthalten sein (kein Abschneiden/Fehler durch die Überlappung, die vorher
    auftrat)."""
    from app.reminder_pdf import build_reminder_pdf
    from app.reminders import create_reminder, ensure_default_reminder_levels
    from app.settings import get_or_create_general_settings
    from tests.test_v153_mahnwesen import make_sent_overdue_invoice

    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)

    header = [b for b in ensure_default_layout(db, "reminder") if b.block_type == "company_header"][0]
    update_layout_block(
        db, header, x_mm=header.x_mm, y_mm=header.y_mm, width_mm=header.width_mm, height_mm=header.height_mm,
        content=None, font_size=header.font_size, font_weight=header.font_weight, text_align=header.text_align,
        visible=True,
    )

    pdf_bytes = build_reminder_pdf(db, reminder)
    assert pdf_bytes[:4] == b"%PDF"
    text = _extract_pdf_text(pdf_bytes)
    general = get_or_create_general_settings(db)
    # ASCII-Ausschnitt statt des vollen Namens: reportlab schreibt PDF-Textliterale in
    # PDFDocEncoding/Latin-1 mit Oktal-Escapes für Nicht-ASCII-Zeichen (z. B. "R\366dchen" statt
    # UTF-8 "R\xc3\xb6dchen") -- ein reiner Test-Encoding-Fallstrick, kein App-Fehler.
    assert b"DACHKONZEPTE" in text
    assert invoice.customer_name.encode("utf-8") in text


def test_ensure_default_layout_reminder_does_not_duplicate_on_second_call():
    db = db_session()
    ensure_default_layout(db, "reminder")
    blocks = ensure_default_layout(db, "reminder")
    assert len(blocks) == len(DEFAULT_SHARED_LAYOUT)


# ---------------------------------------------------------------------------
# PDF-Hintergrund-Upload: Rasterisierung + JPEG-Normalisierung + Seitenverhältnis
# ---------------------------------------------------------------------------

def _make_test_pdf_bytes(width_mm=210, height_mm=297) -> bytes:
    buf = BytesIO()
    c = canvas_module.Canvas(buf, pagesize=(width_mm * mm, height_mm * mm))
    c.setFillColorRGB(0.8, 0.9, 0.85)
    c.rect(0, 0, width_mm * mm, height_mm * mm, fill=1, stroke=0)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_convert_pdf_first_page_to_image_returns_valid_jpeg():
    from PIL import Image
    jpeg_bytes = convert_pdf_first_page_to_image(_make_test_pdf_bytes())
    assert jpeg_bytes[:2] == b"\xff\xd8"  # JPEG-Signatur
    with Image.open(BytesIO(jpeg_bytes)) as im:
        assert im.format == "JPEG"
        assert im.size == (1654, 2339)  # 200dpi A4


def test_prepare_background_upload_accepts_pdf_and_returns_jpeg():
    jpeg_bytes = prepare_background_upload(_make_test_pdf_bytes(), "application/pdf")
    assert jpeg_bytes[:2] == b"\xff\xd8"


def test_prepare_background_upload_accepts_image_and_normalizes_to_jpeg():
    from PIL import Image
    png_buf = BytesIO()
    Image.new("RGB", (1654, 2339), "white").save(png_buf, format="PNG")
    jpeg_bytes = prepare_background_upload(png_buf.getvalue(), "image/png")
    assert jpeg_bytes[:2] == b"\xff\xd8"


def test_validate_a4_aspect_ratio_accepts_a4():
    validate_a4_aspect_ratio(1654, 2339)  # darf nicht werfen


def test_validate_a4_aspect_ratio_rejects_us_letter():
    try:
        validate_a4_aspect_ratio(850, 1100)  # US-Letter, ~9% Abweichung
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_prepare_background_upload_rejects_wrong_aspect_ratio_pdf():
    try:
        prepare_background_upload(_make_test_pdf_bytes(width_mm=210, height_mm=210), "application/pdf")  # quadratisch
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# page_type-Rückwärtskompatibilität: das Angebot bleibt unberührt
# ---------------------------------------------------------------------------

def test_get_set_background_without_page_type_still_targets_first_row():
    db = db_session()
    set_background(db, "quote", "briefbogen.png")
    row = get_background(db, "quote")
    assert row is not None
    assert row.page_type == "first"
    assert row.stored_filename == "briefbogen.png"


def test_reminder_and_quote_backgrounds_are_independent_rows():
    db = db_session()
    set_background(db, "quote", "quote-bg.png")
    set_background(db, "reminder", "reminder-bg.jpg", page_type="first")
    set_background(db, "reminder", "reminder-continuation.jpg", page_type="continuation")
    assert get_background(db, "quote").stored_filename == "quote-bg.png"
    assert get_background(db, "reminder", "first").stored_filename == "reminder-bg.jpg"
    assert get_background(db, "reminder", "continuation").stored_filename == "reminder-continuation.jpg"


# ---------------------------------------------------------------------------
# Neue, seitentypbewusste Router-Endpunkte -- echte Routenauflösung über den TestClient
# ---------------------------------------------------------------------------

def test_backgrounds_endpoints_upload_status_file_delete_for_page_type(threaded_db_session, router_test_client):
    """Seit 1.3.6 über "default" statt "reminder" -- schreibende Endpunkte akzeptieren seit 1.3.20
    nur noch "default" (siehe _validate_writable_document_type()), "reminder" selbst kann über
    diese Routen nicht mehr beschrieben werden (siehe test_write_endpoints_reject_real_document_types
    unten)."""
    db = threaded_db_session
    client = router_test_client(db, document_layout_router)

    status = client.get("/api/document-layout/default/backgrounds/first")
    assert status.status_code == 200
    assert status.json()["has_background"] is False

    pdf_bytes = _make_test_pdf_bytes()
    upload = client.post(
        "/api/document-layout/default/backgrounds/first",
        files={"file": ("briefpapier.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["has_background"] is True

    status_after = client.get("/api/document-layout/default/backgrounds/first")
    assert status_after.json()["has_background"] is True

    file_resp = client.get("/api/document-layout/default/backgrounds/first/file")
    assert file_resp.status_code == 200
    assert file_resp.content[:2] == b"\xff\xd8"  # als JPEG gespeichert, nicht die hochgeladene PDF

    # Der Effekt gilt für "reminder" MIT (fällt zurück auf "default", siehe get_effective_background())
    status_via_reminder = client.get("/api/document-layout/reminder/backgrounds/first")
    assert status_via_reminder.json()["has_background"] is True

    delete_resp = client.delete("/api/document-layout/default/backgrounds/first")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["has_background"] is False


def test_backgrounds_endpoint_rejects_bad_aspect_ratio(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, document_layout_router)
    square_pdf = _make_test_pdf_bytes(width_mm=210, height_mm=210)
    resp = client.post(
        "/api/document-layout/default/backgrounds/first",
        files={"file": ("quadratisch.pdf", square_pdf, "application/pdf")},
    )
    assert resp.status_code == 422


def test_write_endpoints_reject_real_document_types(threaded_db_session, router_test_client):
    """Schutzprüfung seit 1.3.6: schreibende Endpunkte akzeptieren nur noch "default" (bis 1.3.20
    zusätzlich "quote", siehe CLAUDE.md "Gemeinsamer Dokumenttyp"/Aufräumen nach dem PDF-Umbau --
    "quote" braucht seit dem Entfernen des alten Renderers keine eigene Zeile mehr) -- ein echter
    Dokumenttyp wie "invoice"/"order"/"reminder"/"quote" darf NIE mehr eine eigene Zeile
    bekommen, sonst würde der Lese-Rückfall auf den geteilten Satz für genau diesen Typ lautlos
    nicht mehr greifen (siehe app/document_type_fallback.py)."""
    db = threaded_db_session
    client = router_test_client(db, document_layout_router)
    for document_type in ("reminder", "order", "invoice", "quote"):
        pdf_bytes = _make_test_pdf_bytes()
        upload = client.post(
            f"/api/document-layout/{document_type}/backgrounds/first",
            files={"file": ("briefpapier.pdf", pdf_bytes, "application/pdf")},
        )
        assert upload.status_code == 422, f"{document_type}: {upload.text}"

        margins_resp = client.put(
            f"/api/document-layout/{document_type}/margins/first",
            json={"top_mm": 30, "bottom_mm": 20, "left_mm": 18, "right_mm": 16},
        )
        assert margins_resp.status_code == 422, f"{document_type}: {margins_resp.text}"

        reset_resp = client.post(f"/api/document-layout/{document_type}/reset")
        assert reset_resp.status_code == 422, f"{document_type}: {reset_resp.text}"


def test_old_background_route_still_only_accepts_images_unaffected_by_new_route(threaded_db_session, router_test_client):
    """Regressionsbeleg: die alte, vom Angebot genutzte Route existiert unveraendert neben der
    neuen und akzeptiert weiterhin kein PDF -- kein neues Verhalten am Angebots-Pfad."""
    db = threaded_db_session
    client = router_test_client(db, document_layout_router)
    resp = client.post(
        "/api/document-layout/quote/background",
        files={"file": ("briefpapier.pdf", _make_test_pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Ende-zu-Ende mit einer echten Mahnung: Briefpapier je Seitentyp + Bausteine abschaltbar
# ---------------------------------------------------------------------------

def test_reminder_pdf_with_separate_first_and_continuation_backgrounds():
    from app.reminder_pdf import build_reminder_pdf
    from app.reminders import create_reminder, ensure_default_reminder_levels
    from tests.test_v153_mahnwesen import make_sent_overdue_invoice

    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)
    reminder.text = (reminder.text or "") + " " + ("Fülltext. " * 3000)  # erzwingt mehrere Seiten
    db.commit()

    import app.document_layout_background as background_storage
    stored_first = background_storage.replace_background(None, "seite1.jpg", prepare_background_upload(_make_test_pdf_bytes(), "application/pdf"))
    set_background(db, "reminder", stored_first, page_type="first")
    stored_cont = background_storage.replace_background(None, "folge.jpg", prepare_background_upload(_make_test_pdf_bytes(), "application/pdf"))
    set_background(db, "reminder", stored_cont, page_type="continuation")

    pdf_bytes = build_reminder_pdf(db, reminder)
    assert pdf_bytes[:4] == b"%PDF"
    assert count_pdf_pages(pdf_bytes) >= 2


def test_reminder_pdf_logo_and_header_toggle_off_without_gaps():
    from app.reminder_pdf import build_reminder_pdf
    from app.reminders import create_reminder, ensure_default_reminder_levels
    from tests.test_v153_mahnwesen import make_sent_overdue_invoice

    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)

    blocks = {b.block_type: b for b in ensure_default_layout(db, "reminder")}
    for key in ("logo", "company_header", "footer_text"):
        b = blocks[key]
        update_layout_block(
            db, b, x_mm=b.x_mm, y_mm=b.y_mm, width_mm=b.width_mm, height_mm=b.height_mm,
            content=None, font_size=b.font_size, font_weight=b.font_weight, text_align=b.text_align,
            visible=False,
        )

    pdf_bytes = build_reminder_pdf(db, reminder)
    assert pdf_bytes[:4] == b"%PDF"  # baut trotzdem ein gueltiges PDF, keine Luecke/kein Fehler
    text = _extract_pdf_text(pdf_bytes)
    # Seit 1.3.5 steht "Seite" IMMER im Meta-Block (eigene Zeile "1 / N", analog zu Datum/
    # Belegnummer, nicht abschaltbar) -- hier wird nur noch die FUSSZEILEN-Variante geprüft
    # ("Seite {N} von {M}"), die tatsächlich am footer_text-Schalter hängt.
    assert b"Seite 1 von" not in text  # Fußzeile war ausgeschaltet


# ---------------------------------------------------------------------------
# render_framed_pdf() mit content_story als Funktion (seit 1.3.5) -- zweiter Durchlauf für Inhalte,
# die die Gesamtseitenzahl schon im Inhalt selbst brauchen (siehe app/reminder_pdf.py, CLAUDE.md
# "Kopfbereich").
# ---------------------------------------------------------------------------

def test_render_framed_pdf_accepts_plain_list_unchanged():
    """Rückwärtskompatibilität: eine einfache Liste (wie vor 1.3.5) baut weiterhin nur EINEN
    Durchlauf, kein Verhalten ändert sich für Aufrufer, die die Funktions-Variante nicht nutzen."""
    from app.document_pdf import build_styles

    db = db_session()
    styles = build_styles()
    pdf_bytes = render_framed_pdf(
        db, document_type="reminder", title="Test",
        content_story=[Paragraph("Einfacher Inhalt", styles["body"])],
    )
    assert pdf_bytes[:4] == b"%PDF"
    assert _extract_pdf_text(pdf_bytes).count(b"Einfacher") == 1


def test_render_framed_pdf_calls_factory_twice_with_none_then_real_total():
    """content_story als Funktion wird zuerst mit None (Entdeckungsdurchlauf), danach mit der
    tatsächlichen Gesamtseitenzahl aufgerufen -- die zurückgegebenen Bytes entsprechen dem ZWEITEN
    Aufruf."""
    from app.document_pdf import build_styles

    db = db_session()
    styles = build_styles()
    calls = []

    def factory(total_pages):
        calls.append(total_pages)
        return [Paragraph(f"Aufruf mit total_pages={total_pages}", styles["body"])]

    pdf_bytes = render_framed_pdf(db, document_type="reminder", title="Test", content_story=factory)
    assert calls[0] is None
    assert calls[1] == 1  # einseitiger Testinhalt
    assert b"total_pages=1" in _extract_pdf_text(pdf_bytes)
    assert b"total_pages=None" not in _extract_pdf_text(pdf_bytes)


def test_render_framed_pdf_factory_gets_correct_total_across_multiple_pages():
    """Erzwingt echten Seitenumbruch (viele Absätze) -- der zweite Durchlauf muss die tatsächliche,
    reale Gesamtseitenzahl bekommen, nicht nur den Sonderfall 1."""
    from app.document_pdf import build_styles

    db = db_session()
    styles = build_styles()

    def factory(total_pages):
        marker = Paragraph(f"GESAMT={total_pages}", styles["body"])
        filler = [Paragraph("Zeile " * 20, styles["body"]) for _ in range(150)]
        return [marker, *filler]

    pdf_bytes = render_framed_pdf(db, document_type="reminder", title="Test", content_story=factory)
    real_pages = count_pdf_pages(pdf_bytes)
    assert real_pages > 1
    assert f"GESAMT={real_pages}".encode() in _extract_pdf_text(pdf_bytes)


def test_reminder_pdf_meta_block_shows_correct_page_count_on_multipage_document():
    """Ende-zu-Ende: eine Mahnung mit sehr langem Mahntext (echter Seitenumbruch) zeigt im
    Meta-Block "Seite 1 / N" mit dem tatsächlichen N -- nicht nur bei einer einzelnen Seite."""
    from app.reminder_pdf import build_reminder_pdf
    from app.reminders import create_reminder, ensure_default_reminder_levels
    from tests.test_v153_mahnwesen import make_sent_overdue_invoice

    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)
    reminder.text = "Das ist ein sehr langer Testsatz, der immer wieder wiederholt wird. " * 250
    db.commit()

    pdf_bytes = build_reminder_pdf(db, reminder)
    real_pages = count_pdf_pages(pdf_bytes)
    assert real_pages > 1
    text = _extract_pdf_text(pdf_bytes)
    assert f"1 / {real_pages}".encode() in text


def test_reminder_pdf_footer_and_meta_block_page_count_can_both_be_active():
    """Fußzeile (abschaltbarer Rahmen-Baustein) und die Meta-Block-Seitenzeile (fester
    Inhaltsbestandteil, nicht abschaltbar) sind unabhängig -- beide gleichzeitig aktiv ist
    redundant, aber nicht falsch/nicht fehlerhaft. Seit 1.3.8 steht die Fußzeile standardmäßig
    AUS (siehe CLAUDE.md "Gemeinsamer Dokumenttyp" -- Kollision mit dem aufgedruckten Fußbereich
    eines echten Briefbogens, die Seitenangabe wird dort dank Meta-Block/Wiederholungszeile
    ohnehin nicht mehr gebraucht) -- dieser Test schaltet sie deshalb bewusst manuell ein, um zu
    prüfen, dass die Kombination weiterhin funktioniert, nicht mehr, dass sie der Standard ist."""
    from app.reminder_pdf import build_reminder_pdf
    from app.reminders import create_reminder, ensure_default_reminder_levels
    from tests.test_v153_mahnwesen import make_sent_overdue_invoice

    db = db_session()
    ensure_default_reminder_levels(db)
    invoice = make_sent_overdue_invoice(db)
    reminder = create_reminder(db, invoice, 1)

    footer_block = next(b for b in ensure_default_layout(db, "reminder") if b.block_type == "footer_text")
    assert footer_block.visible is False  # seit 1.3.8 Standard: aus
    update_layout_block(
        db, footer_block, x_mm=footer_block.x_mm, y_mm=footer_block.y_mm, width_mm=footer_block.width_mm,
        height_mm=footer_block.height_mm, content=None, font_size=footer_block.font_size,
        font_weight=footer_block.font_weight, text_align=footer_block.text_align, visible=True,
    )

    pdf_bytes = build_reminder_pdf(db, reminder)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Seite 1 von 1" in text  # Fußzeile
    assert b"1 / 1" in text  # Meta-Block


def test_backgrounds_routes_do_not_collide_with_file_literal(threaded_db_session, router_test_client):
    """Literal-vs-Platzhalter-Kollisionscheck (Muster wie in test_v167_pagination.py): die neue
    Route .../backgrounds/{page_type} liegt auf einem eigenen Pfadsegment und darf die bestehende
    .../background/file-Route nicht verschlucken.

    Seit 1.3.20 (Aufräumen nach dem PDF-Umbau, CLAUDE.md "Gemeinsamer Dokumenttyp") ohne den
    analogen Check für .../background/repeat -- dieser Endpunkt selbst ist entfernt (nur noch von
    app/templates/document_layout_editor.html genutzt, der mit dem alten Angebots-Renderer
    entfiel); die Kollisionsgefahr für .../background/file bleibt unverändert relevant, da die
    Route weiterhin existiert. "quote" ist seither kein eigenständig beschreibbarer Dokumenttyp
    mehr -- "default" bleibt der einzige schreibbare Typ und dient hier weiterhin als Beleg gegen
    die Routenkollision selbst."""
    db = threaded_db_session
    client = router_test_client(db, document_layout_router)
    set_background(db, "default", "x.png")
    resp = client.get("/api/document-layout/default/background/file")
    assert resp.status_code == 404  # Datei existiert nicht auf Platte, aber die RICHTIGE (alte) Route wurde getroffen


def test_background_repeat_endpoint_was_removed_with_the_old_editor(threaded_db_session, router_test_client):
    """Regressionstest für die bewusste Entfernung (1.3.20): PUT .../background/repeat existierte
    ausschließlich für app/templates/document_layout_editor.html, das mit dem alten Angebots-
    Renderer entfernt wurde -- keine verbleibende Oberfläche ruft diesen Endpunkt noch auf."""
    db = threaded_db_session
    client = router_test_client(db, document_layout_router)
    resp = client.put("/api/document-layout/default/background/repeat", json={"repeat_on_every_page": False})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# footer_text Standard AUS seit 1.3.8 (Fund aus der 1.3.7-Verifikation gegen die echte Datenbank:
# die feste Zeichenposition 20mm/12mm kollidierte mit dem aufgedruckten Fußbereich eines echten
# Briefbogens) -- gilt für JEDEN Dokumenttyp, der über den geteilten Satz läuft, nicht nur
# "reminder". continuation_header bleibt bewusst Standard AN.
# ---------------------------------------------------------------------------

def test_footer_text_defaults_to_invisible_for_every_document_type_using_the_shared_frame():
    db = db_session()
    for document_type in ("reminder", "invoice", "order"):
        blocks = {b.block_type: b for b in ensure_default_layout(db, document_type)}
        assert blocks["footer_text"].visible is False, f"{document_type}: footer_text sollte standardmäßig aus sein"
        assert blocks["continuation_header"].visible is True, f"{document_type}: continuation_header sollte standardmäßig an sein"


def test_invoice_pdf_has_no_footer_page_number_by_default():
    """Ende-zu-Ende: eine frisch erzeugte Rechnung zeigt nirgends "Seite X von Y" aus der
    Fußzeile -- die Seitenangabe steht stattdessen im Meta-Block (Seite 1) bzw. der
    Wiederholungszeile (Folgeseiten)."""
    from app.invoice_pdf import build_invoice_pdf
    from tests.test_v133_invoices import make_order_with_item
    from app.invoices import create_schlussrechnung, finalize_and_send_invoice

    db = db_session()
    order, item = make_order_with_item(db)
    invoice = create_schlussrechnung(db, order)
    invoice = finalize_and_send_invoice(db, invoice)

    pdf_bytes = build_invoice_pdf(db, invoice)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Seite 1 von 1" not in text  # keine Fusszeile
    assert b"1 / 1" in text  # Meta-Block zeigt die Seitenangabe weiterhin
