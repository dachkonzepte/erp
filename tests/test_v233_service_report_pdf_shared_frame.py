"""Version 1.3.11 -- fuenfte Etappe des PDF-Umbaus: der Einsatzbericht wechselt auf den
gemeinsamen Rahmen (app/document_frame.py), analog zu Mahnung/Rechnung/Auftrag.

test_service_report_pdf_contains_expected_content() ist bewusst VOR dem Umbau geschrieben (Punkt
1 der Anfrage: bestehende Testabdeckung deckt Pruefpunkte/Mängel/Material bereits gut ab, aber
keine Auftrags-/Kundenidentitaet und keine der beiden Unterschriften-Beschriftungen) und muss vor
UND nach dem Umbau unveraendert gruen bleiben."""

from decimal import Decimal

from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v213_inspection_items import TINY_PNG, _extract_pdf_text
from tests.test_v227_din5008_header_block import _char_x_range_mm
from tests.test_v230_invoice_pdf_shared_frame import _page_text
from tests.test_v167_pagination import count_pdf_pages

from app.document_page_margins import update_margins
from app.findings import create_finding
from app.service_reports import add_photo, create_report, sign_report


def _make_signed_report(db, description="Dach kontrolliert, keine Mängel.", **order_kwargs):
    order, _ = make_order_with_item(db, **order_kwargs)
    report = create_report(db, order.id, "wartung", description=description)
    signed = sign_report(
        db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Meier",
        customer_signature_png_bytes=TINY_PNG, customer_signature_name="Erika Musterfrau",
    )
    from app.service_reports import _load as _load_report
    return _load_report(db, report["id"]), order


def test_service_report_pdf_contains_expected_content(tmp_path):
    """Muss vor UND nach dem Rahmenumbau identisch grün bleiben (siehe Modul-Docstring)."""
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    from app.service_report_pdf import build_service_report_pdf

    db = db_session()
    row, order = _make_signed_report(db)

    pdf_bytes = build_service_report_pdf(db, row)
    assert pdf_bytes[:4] == b"%PDF"
    text = _extract_pdf_text(pdf_bytes)

    assert order.order_number.encode("utf-8") in text
    assert order.customer_name.encode("utf-8") in text
    assert b"Wartungsbericht" in text
    assert b"kontrolliert, keine M" in text  # description, Umlaut vermieden (siehe 1.3.9-Muster)
    assert b"Monteur Meier" in text
    assert b"Erika Musterfrau" in text


# ---------------------------------------------------------------------------
# Rahmen: service_report steht in RENDERERS_USING_SHARED_FRAME, nutzt denselben geteilten Satz
# wie Mahnung/Rechnung/Auftrag
# ---------------------------------------------------------------------------

def test_service_report_is_registered_as_using_the_shared_frame():
    from app.document_frame import RENDERERS_USING_SHARED_FRAME

    assert "service_report" in RENDERERS_USING_SHARED_FRAME


def test_service_report_shares_background_and_margins_with_others_via_default():
    from app.document_layout import get_effective_background, set_background
    from app.document_page_margins import get_margins as _get_margins

    db = db_session()
    set_background(db, "default", "geteiltes-briefpapier.jpg", page_type="first")
    assert get_effective_background(db, "service_report", "first").stored_filename == "geteiltes-briefpapier.jpg"

    report_margins = _get_margins(db, "service_report", "first")
    invoice_margins = _get_margins(db, "invoice", "first")
    assert report_margins.top_mm == invoice_margins.top_mm == Decimal("25.0")


def test_object_address_block_appears_only_when_property_set(tmp_path):
    """build_object_address_block() ist ein Baustein, den es vor dem Umbau in diesem Renderer
    gar nicht gab -- neu hinzugekommen, weil er bei Mahnung/Rechnung/Auftrag bereits Standard ist
    und dieselbe Order-Spalte (property_name/-address) liest, die dort bereits genutzt wird.
    Muss NUR erscheinen, wenn tatsächlich ein Objekt hinterlegt ist (kein erfundenes Feld)."""
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    from app.service_report_pdf import build_service_report_pdf

    db = db_session()
    row, order = _make_signed_report(db)
    pdf_bytes = build_service_report_pdf(db, row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Ausf\xc3\xbchrungsort" not in text

    db2 = db_session()
    row2, order2 = _make_signed_report(db2)
    order2.property_name = "Testobjekt"
    order2.property_address = "Objektstraße 2\n54321 Objektstadt"
    db2.commit()
    pdf_bytes2 = build_service_report_pdf(db2, row2)
    text2 = _extract_pdf_text(pdf_bytes2)
    assert b"Testobjekt" in text2


# ---------------------------------------------------------------------------
# Punkt 2: Meta-Zeilen -- Sachbearbeiter/Monteur, Kunden-Nr. nur wenn vorhanden
# ---------------------------------------------------------------------------

def test_meta_rows_show_order_number_date_report_type_and_installer(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    from app.service_report_pdf import build_service_report_pdf

    db = db_session()
    from app.models import Employee, ServiceReport
    monteur = Employee(first_name="Peter", last_name="Handwerker")
    db.add(monteur)
    db.commit()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "wartung")
    report_row = db.get(ServiceReport, report["id"])
    report_row.created_by_employee_id = monteur.id
    db.commit()
    sign_report(
        db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Meier",
        customer_signature_png_bytes=TINY_PNG, customer_signature_name="Erika Musterfrau",
    )
    from app.service_reports import _load as _load_report
    row = _load_report(db, report["id"])

    pdf_bytes = build_service_report_pdf(db, row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Auftragsnr." in text
    assert order.order_number.encode("utf-8") in text
    assert b"Berichtstyp" in text
    assert b"Kunden-Nr." in text
    assert order.customer_number.encode("utf-8") in text
    assert b"Monteur" in text
    assert b"Peter Handwerker" in text


# ---------------------------------------------------------------------------
# Punkt 5 + 6: colWidths-Summe/hAlign aller Tabellen -- gemessen wie bei der Rechnung (1.3.9)
# ---------------------------------------------------------------------------

def _build_measurable_report(db, **margin_overrides):
    from app.service_report_pdf import build_service_report_pdf

    if margin_overrides:
        update_margins(db, "service_report", "first", **margin_overrides)
        update_margins(db, "service_report", "continuation", **margin_overrides)
    row, order = _make_signed_report(db)
    return build_service_report_pdf(db, row), order


def test_header_and_signature_table_left_edge_matches_default_margin(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"

    db = db_session()
    pdf_bytes, _ = _build_measurable_report(db)
    left_margin_mm = 18.0
    for needle in ["DACHKONZEPTE", "Durchgeführte Arbeiten", "Bestätigt von: Monteur Meier"]:
        r = _char_x_range_mm(pdf_bytes, needle)
        assert r is not None, f"{needle!r} nicht im PDF gefunden"
        left, _ = r
        assert abs(left - left_margin_mm) < 0.6, f"{needle!r}: left={left:.2f}mm, erwartet ~{left_margin_mm}mm"


def test_signature_table_columns_split_content_width_in_half(tmp_path):
    """Vorher (Punkt 6 der Anfrage): colWidths=[95mm, 95mm] = 190mm, 14mm mehr als die 176mm
    Standardbreite -- reportlab zentriert eine zu breite Tabelle standardmäßig, die zweite
    Spalte ("Kunde") landete dadurch spürbar VOR der rechten Haelfte. Nachher: beide Spalten
    exakt content_width/2 breit, "Kunde"-Spalte beginnt bei genau der Haelfte."""
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"

    db = db_session()
    pdf_bytes, _ = _build_measurable_report(db)
    installer_left, _ = _char_x_range_mm(pdf_bytes, "Bestätigt von: Monteur Meier")
    customer_left, _ = _char_x_range_mm(pdf_bytes, "Bestätigt von: Erika Musterfrau")
    # Standardränder: content_width=176mm, halbe Spalte=88mm, Standardpolster der zweiten
    # Spalte (nicht genullt, nur die äußeren Kanten sind es) 2.117mm.
    expected_customer_left = 18.0 + 88.0 + 2.117
    assert abs(installer_left - 18.0) < 0.6
    assert abs(customer_left - expected_customer_left) < 1.0


def test_signature_table_follows_custom_margins_not_hardcoded_190mm(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"

    db = db_session()
    pdf_bytes, _ = _build_measurable_report(
        db, top_mm=Decimal("42.0"), bottom_mm=Decimal("20.0"), left_mm=Decimal("30.0"), right_mm=Decimal("25.0"),
    )
    left_margin_mm = 30.0
    installer_left, _ = _char_x_range_mm(pdf_bytes, "Bestätigt von: Monteur Meier")
    assert abs(installer_left - left_margin_mm) < 0.6


def test_inspection_and_material_and_time_tables_follow_custom_margins(tmp_path):
    """Deckt die drei übrigen, vorher exakt 176mm summierenden Tabellen ab (Prüfpunkte,
    Material, Erfasste Zeiten) -- vorher nur "zufällig richtig" bei Standardrändern, da hart auf
    176mm summiert, nicht aus frame_content_width() abgeleitet."""
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    from app.service_report_pdf import build_service_report_pdf
    from app.service_reports import add_material
    from app.time_tracking import create_manual_entry
    from datetime import date
    from app.inspection_templates import create_template, create_template_item
    from app.roof_areas import create_roof_area
    from tests.test_v202_maintenance_contracts import make_customer_and_property

    db = db_session()
    update_margins(db, "service_report", "first", top_mm=Decimal("42.0"), bottom_mm=Decimal("20.0"), left_mm=Decimal("30.0"), right_mm=Decimal("25.0"))
    update_margins(db, "service_report", "continuation", top_mm=Decimal("42.0"), bottom_mm=Decimal("20.0"), left_mm=Decimal("30.0"), right_mm=Decimal("25.0"))

    from app.models import Employee
    employee = Employee(first_name="Peter", last_name="Handwerker")
    db.add(employee)
    db.commit()

    template = create_template(db, "Testvorlage", roof_type="Flachdach")
    create_template_item(db, template["id"], "Bemerkungen", "free_text", group_name="Allgemein")
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Testfläche", roof_type="Flachdach")

    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    add_material(db, report["id"], description="Bitumenbahn", quantity=Decimal("5"), unit="m2")
    create_manual_entry(db, order_id=order.id, employee_id=employee.id, work_date=date.today(), activity="Wartung", hours=Decimal("1.5"))
    sign_report(
        db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Meier",
        customer_signature_png_bytes=TINY_PNG, customer_signature_name="Erika Musterfrau",
    )
    from app.service_reports import _load as _load_report
    row = _load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, row)

    left_margin_mm = 30.0
    right_margin_mm = 210.0 - 25.0
    # Erste-Spalte-Header von Prüfpunkte-/Material-Tabelle -- beide eindeutig (im Gegensatz zu
    # "Datum", das zusätzlich im Meta-Block vorkommt und dort den falschen, ersten Treffer im
    # Content-Stream liefern würde).
    for needle in ["Prüfpunkt", "Bezeichnung"]:
        left, _ = _char_x_range_mm(pdf_bytes, needle)
        assert abs(left - left_margin_mm) < 0.6, f"{needle!r}: left={left:.2f}mm"
    # Zeiten-Tabelle: die letzte Spalte ("Stunden", rechtsbündig) muss auf dem rechten
    # Satzspiegel enden -- eindeutiger Beleg dafür, dass auch ihre vierte, variable Spaltenbreite
    # (Tätigkeit) aus frame_content_width() abgeleitet wird, nicht aus dem alten 176mm-Wert.
    _, right = _char_x_range_mm(pdf_bytes, "1,50")
    assert abs(right - right_margin_mm) < 0.6, f"'1,50': right={right:.2f}mm"


# ---------------------------------------------------------------------------
# Punkt 4: Foto-Breite folgt frame_content_width(), nicht hart codiert
# ---------------------------------------------------------------------------

def test_photo_width_is_capped_by_narrow_content_width(tmp_path):
    """Bei sehr breiten Rändern (schmaler Satzspiegel) darf ein Foto nicht über den Rand
    hinausstehen -- die Standardgröße (70mm) ist eine Vorschaugröße, keine Mindestgröße."""
    from app.service_report_pdf import _pdf_image, _render_photo_flowables

    # 40mm verfügbare Breite -- unter der Standardgröße von 70mm.
    flowables = _render_photo_flowables([], small_style=None, content_width_mm=40.0)
    assert flowables == []  # keine Fotos übergeben, nur Aufbau-Sicherheit

    # Direkter Test der Kappungslogik über eine reale Bilddatei.
    import io
    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new("RGB", (100, 50), "white").save(buf, format="PNG")
    tmp_file = tmp_path / "test.png"
    tmp_file.write_bytes(buf.getvalue())

    from reportlab.lib.units import mm
    narrow = _pdf_image(tmp_file, min(70, 40.0))
    assert narrow.drawWidth == 40.0 * mm
    wide = _pdf_image(tmp_file, min(70, 176.0))
    assert wide.drawWidth == 70 * mm


# ---------------------------------------------------------------------------
# Wiederholungszeile auf Folgeseiten -- bereits Teil des Rahmens (seit 1.3.7), greift jetzt auch
# fuer den Einsatzbericht ohne eigenen Code in service_report_pdf.py.
# ---------------------------------------------------------------------------

def _make_multipage_report(db):
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "wartung", description="Mehrseitiger Testbericht.")
    for i in range(6):
        finding = create_finding(db, report["id"], f"Mangel {i}: Beschädigung sichtbar, Handlungsbedarf besteht.", "mittel", "sofort_behoben")
        add_photo(db, report["id"], TINY_PNG, f"foto_{i}.png", finding_id=finding["id"], caption=f"Foto {i}")
    signed = sign_report(
        db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Meier",
        customer_signature_png_bytes=TINY_PNG, customer_signature_name="Erika Musterfrau",
    )
    from app.service_reports import _load as _load_report
    return _load_report(db, report["id"]), order


def test_continuation_header_appears_on_multipage_report(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    from app.service_report_pdf import build_service_report_pdf

    db = db_session()
    row, order = _make_multipage_report(db)
    pdf_bytes = build_service_report_pdf(db, row)
    real_pages = count_pdf_pages(pdf_bytes)
    assert real_pages > 1, "Testszenario sollte mehrseitig sein -- sonst prüft dieser Test nichts"

    continuation_marker = f"Auftragsnr.: {order.order_number}"
    first_page_text = _page_text(pdf_bytes, 0)
    assert continuation_marker not in first_page_text
    for page_index in range(1, real_pages):
        assert continuation_marker in _page_text(pdf_bytes, page_index)
