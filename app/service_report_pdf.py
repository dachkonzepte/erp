"""PDF-Erzeugung für digitale Einsatzberichte (seit 1.2.1) -- nur für bereits unterschriebene
Berichte (siehe build_service_report_pdf()).

Seit 1.3.11: fünfte Etappe des PDF-Umbaus (CLAUDE.md "Gemeinsamer Dokumenttyp") -- wechselt auf
den gemeinsamen PDF-Rahmen (app/document_frame.py, document_type="service_report"). Firmenkopf/
Logo/Fußzeile sind keine feste Story mehr, sondern der optionale, abschaltbare Rückfall des
Rahmens; Briefpapier-Hintergrund und Ränder je Seitentyp kommen ebenfalls von dort. Kopfbereich
über den gemeinsamen build_din5008_header_block() statt des bisherigen
build_company_header_block(). Die zweite Unterschrift (Muster aus quote_layout_pdf.py, dort per
drawImage auf einem rohen Canvas -- hier als platypus.Image-Flowable, weil dieses PDF wie
invoice_pdf.py auf einer Flowable-story aufbaut) sowie alle KeepTogether-Blöcke aus 1.2.21/1.3.0
bleiben inhaltlich unverändert, nur ihre Tabellenbreiten folgen jetzt frame_content_width() statt
hart codierter mm-Werte (siehe CLAUDE.md "Positionstabelle: Menge/Einheit/Breite", 1.3.9)."""

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import build_din5008_header_block, build_object_address_block, build_styles, ptext
from .findings import ACTION_LABELS, SEVERITY_LABELS, STATUS_LABELS
from .service_report_photos import photo_path
from .service_reports import REPORT_TYPE_LABELS, report_to_dict, signature_path
from .settings import get_or_create_general_settings
from .time_tracking import entry_to_dict, list_entries

CONDITION_GRADE_LABELS = {1: "Neuwertig", 2: "Gebrauchsspuren", 3: "Abgenutzt", 4: "Sanierung erforderlich"}
RESULT_LABELS = {"ok": "OK", "nok": "Nicht OK", "na": "Entfällt"}

# Feste Spaltenbreiten je Tabelle -- alle außer der jeweils einen Text-/Beschreibungsspalte (siehe
# build_service_report_pdf(): *_width = content_width - Summe der übrigen). Unverändert gegenüber
# vorher (die Zahlenwerte selbst), nur die jeweils flexible Spalte wird jetzt aus der tatsächlich
# verfügbaren Breite abgeleitet statt hart auf einen bei 176mm Standardbreite passenden Wert
# fixiert zu sein (CLAUDE.md "Positionstabelle: Menge/Einheit/Breite", 1.3.9).
INSPECTION_FIXED_COLS_MM = {"ergebnis": 40, "bemerkung": 41}
MATERIAL_FIXED_COLS_MM = {"menge": 33, "einheit": 33}
TIME_ENTRY_FIXED_COLS_MM = {"datum": 25, "mitarbeiter": 50, "stunden": 30}


def _format_inspection_result(item) -> tuple[str, bool]:
    """Formatiert das Ergebnis eines InspectionItem für Anzeige/PDF je item_type. Gibt
    (Text, out_of_range) zurück -- out_of_range ist nur bei measurement außerhalb
    target_min/target_max True und wird von der aufrufenden Stelle optisch hervorgehoben, aber
    nie blockiert (nur gespeichert und markiert, siehe Auftrag)."""
    if item.item_type in ("ja_nein", "leak_test"):
        if item.result is None:
            return "nicht geprüft", False
        text = RESULT_LABELS.get(item.result, item.result)
        if item.item_type == "leak_test" and item.duration_minutes is not None:
            text += f", Prüfdauer {item.duration_minutes} min"
        return text, False
    if item.item_type == "condition_grade":
        if item.condition_grade is None:
            return "nicht geprüft", False
        return CONDITION_GRADE_LABELS.get(item.condition_grade, str(item.condition_grade)), False
    if item.item_type == "measurement":
        if item.measured_value is None:
            return "nicht geprüft", False
        value_text = f"{item.measured_value} {item.unit or ''}".strip()
        out_of_range = (
            (item.target_min is not None and item.measured_value < item.target_min)
            or (item.target_max is not None and item.measured_value > item.target_max)
        )
        if out_of_range:
            value_text += f" (Soll: {item.target_min or ''}–{item.target_max or ''} {item.unit or ''})".rstrip()
        return value_text, out_of_range
    if item.item_type == "quantity":
        if item.quantity is None:
            return "nicht geprüft", False
        return f"{item.quantity} {item.unit or ''}".strip(), False
    if item.item_type == "free_text":
        return ("erfasst" if (item.notes and item.notes.strip()) else "nicht geprüft"), False
    if item.item_type == "photo":
        return "Fotoerfassung folgt", False
    return "nicht geprüft", False


# Nur die äußeren Spaltenränder nullen (erste Spalte links, letzte Spalte rechts) -- dieselbe
# Begründung wie bei Rechnung/Auftrag (1.3.9/1.3.10): zwischen den übrigen Spalten bleibt das
# normale Zellenpolster stehen, sonst würden benachbarte Werte ohne jeden Zwischenraum
# aneinanderstoßen. Gilt gleichermaßen für 2- und mehrspaltige Tabellen.
_ZERO_OUTER_TABLE_PADDING = [("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (-1, 0), (-1, -1), 0)]


def _pdf_image(path, max_width_mm: float):
    """Öffnet die Datei nur, um das Seitenverhältnis zu lesen (Pillow ist über reportlab
    bereits Pflichtabhängigkeit) -- gibt ein verzerrungsfreies platypus.Image mit fester Breite
    zurück. Die Anzahl je Seite wird bewusst NICHT manuell begrenzt: reportlabs
    Flowable-Mechanik paginiert eine lange story-Liste automatisch."""
    with PILImage.open(path) as im:
        ratio = (im.height / im.width) if im.width else 1
    width = max_width_mm * mm
    return Image(str(path), width=width, height=width * ratio)


def _render_photo_flowables(photos, small_style, content_width_mm: float, max_width_mm=70, before_after_width_mm=80):
    """Gemeinsamer Baustein für "Dokumentation" (Prüfpunkt-Fotos) und "Festgestellte Mängel"
    (Mangel-Fotos) -- ein vorhandenes Vorher/Nachher-Paar (nur bei Prüfpunkt-Fotos mit
    photo_before_after möglich, Mangel-Fotos tragen immer kind="allgemein") wird als
    zweispaltige Tabelle nebeneinander gesetzt, alles andere als einfache Abfolge.

    content_width_mm (seit 1.3.11, CLAUDE.md "Positionstabelle: Menge/Einheit/Breite"): die
    beiden Standardbreiten (70mm Einzelfoto, 80mm je Vorher/Nachher-Bild) sind bewusst klein
    gehaltene Vorschaugrößen, keine "so breit wie möglich"-Vorgabe -- deshalb keine Skalierung
    NACH OBEN, wenn mehr Platz da ist, nur eine Kappung nach unten, falls der tatsächlich
    verfügbare Satzspiegel (nach einer Randänderung) schmaler als die Vorschaugröße wäre, sonst
    stünden Fotos über den Rand hinaus."""
    before = next((p for p in photos if p.kind == "vorher"), None)
    after = next((p for p in photos if p.kind == "nachher"), None)
    others = [p for p in photos if p.kind not in ("vorher", "nachher")]
    flowables = []
    if before is not None or after is not None:
        col_width_mm = content_width_mm / 2
        pair_width_mm = min(before_after_width_mm, col_width_mm)
        row = [[
            _pdf_image(photo_path(before.file_path), pair_width_mm) if before else "",
            _pdf_image(photo_path(after.file_path), pair_width_mm) if after else "",
        ]]
        pair_table = Table(row, colWidths=[col_width_mm * mm, col_width_mm * mm])
        pair_table.setStyle(TableStyle(_ZERO_OUTER_TABLE_PADDING))
        flowables.append(pair_table)
        flowables.append(Spacer(1, 2 * mm))
    for p in others:
        flowables.append(_pdf_image(photo_path(p.file_path), min(max_width_mm, content_width_mm)))
        if p.caption:
            flowables.append(Paragraph(ptext(p.caption), small_style))
        flowables.append(Spacer(1, 2 * mm))
    return flowables


def build_service_report_pdf(db, report) -> bytes:
    if report.status != "unterschrieben":
        raise ValueError("Nur unterschriebene Berichte können als PDF exportiert werden.")
    data = report_to_dict(report)
    order = report.order
    general = get_or_create_general_settings(db)
    label = REPORT_TYPE_LABELS.get(report.report_type, report.report_type)
    styles = build_styles()
    body, small, h1, h2, h3 = styles["body"], styles["small"], styles["h1"], styles["h2"], styles["h3"]

    sender_parts = [general.company_name, general.street, " ".join(x for x in [general.postal_code, general.city] if x)]
    sender_line = " - ".join(x for x in sender_parts if x)

    # order.customer_address ist derselbe Text-Schnappschuss wie bei Auftrag/Rechnung/Mahnung
    # (orders.py::_address()) -- einmaliges Aufteilen rekonstruiert die beiden Zeilen.
    recipient_lines = [order.customer_name] + (
        order.customer_address.split(", ", 1) if order.customer_address else []
    )

    # Derselbe Satzspiegel für den gesamten fließenden Inhalt -- aus den tatsächlich
    # konfigurierten Rändern, nicht aus einem hart codierten Standardwert (CLAUDE.md
    # "Positionstabelle: Menge/Einheit/Breite", 1.3.9). content_width_mm zusätzlich als reine
    # Millimeterzahl für die Foto-Breitenberechnung (_render_photo_flowables()), die in mm statt
    # reportlab-Punkten rechnet.
    content_width = frame_content_width(get_margins(db, "service_report", "first"))
    content_width_mm = content_width / mm

    def build_story(total_pages: int | None) -> list:
        page_value = f"1 / {total_pages}" if total_pages is not None else "1 / …"
        meta_rows = [
            ("Auftragsnr.", order.order_number), ("Datum", data["performed_at"].strftime("%d.%m.%Y")),
            ("Berichtstyp", label),
        ]
        if order.customer_number:
            meta_rows.append(("Kunden-Nr.", order.customer_number))
        if data.get("created_by_employee_name"):
            meta_rows.append(("Monteur", data["created_by_employee_name"]))
        meta_rows.append(("Seite", page_value))
        story = list(build_din5008_header_block(sender_line, recipient_lines, meta_rows, styles, content_width=content_width))

        story += build_object_address_block(
            order.property_name,
            [x for x in str(order.property_address or "").splitlines() if x],
            styles,
        )

        story.append(Paragraph(label, h1))
        story.append(Paragraph(ptext(order.title), body))
        story.append(Spacer(1, 5 * mm))

        if data.get("description"):
            story.append(Paragraph("Durchgeführte Arbeiten / Feststellungen", h2))
            story.append(Paragraph(ptext(data["description"]), body))
            story.append(Spacer(1, 5 * mm))

        def _render_inspection_group_tables(items) -> None:
            groups: dict[str, list] = {}
            group_order: list[str] = []
            for item in items:
                key = item.group_name or "Allgemein"
                if key not in groups:
                    groups[key] = []
                    group_order.append(key)
                groups[key].append(item)
            fixed_width = sum(INSPECTION_FIXED_COLS_MM.values()) * mm
            pruefpunkt_width = content_width - fixed_width
            col_widths = [pruefpunkt_width, INSPECTION_FIXED_COLS_MM["ergebnis"] * mm, INSPECTION_FIXED_COLS_MM["bemerkung"] * mm]
            for group_name in group_order:
                rows = [["Prüfpunkt", "Ergebnis", "Bemerkung"]]
                row_styles = []
                for row_index, item in enumerate(groups[group_name], start=1):
                    result_text, out_of_range = _format_inspection_result(item)
                    rows.append([item.text, result_text, item.notes or ""])
                    if out_of_range:
                        row_styles.append(("TEXTCOLOR", (1, row_index), (1, row_index), colors.HexColor("#c0362c")))
                        row_styles.append(("FONTNAME", (1, row_index), (1, row_index), "Helvetica-Bold"))
                table = Table(rows, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("LINEBELOW", (0, 0), (-1, 0), .6, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4), *_ZERO_OUTER_TABLE_PADDING, *row_styles,
                ]))
                # KeepTogether: Gruppenüberschrift und ihre (üblicherweise kurze) Tabelle sollen nicht
                # durch einen Seitenumbruch getrennt werden -- eine Überschrift allein am Seitenende
                # wäre ähnlich unschön wie die im PDF gerissene Unterschrift weiter unten. Passt eine
                # Gruppe ausnahmsweise nicht auf eine einzelne Seite, degradiert reportlab elegant
                # (rendert normal weiter, kein Fehler).
                story.append(KeepTogether([Paragraph(group_name, h3), table]))
                story.append(Spacer(1, 4 * mm))

        inspection_items = report.inspection_items  # bereits sort_order, id sortiert (Relationship-order_by)
        if inspection_items:
            story.append(Paragraph("Prüfpunkte", h2))
            # Mehrflächen-Berichte (seit 1.2.22, report.report_roof_areas vorhanden): je Fläche eine
            # eigene Überschrift vor ihren group_name-Tabellen. Ein Altbestand-Bericht (vor 1.2.22,
            # keine solchen Zeilen) rendert UNVERÄNDERT flach wie vor dieser Version -- Vorgabe war,
            # dass sein PDF genau gleich aussieht.
            if report.report_roof_areas:
                for link in report.report_roof_areas:
                    area_items = [i for i in inspection_items if i.roof_area_id == link.roof_area_id]
                    if not area_items:
                        continue
                    area_name = link.roof_area_name_snapshot or (link.roof_area.name if link.roof_area else "Dachfläche")
                    story.append(Paragraph(area_name, h2))
                    _render_inspection_group_tables(area_items)
            else:
                _render_inspection_group_tables(inspection_items)
            story.append(Spacer(1, 2 * mm))

        # Verbrauchtes Material (seit 1.2.23) -- keine Preise/Summe (siehe Moduldocstring
        # ServiceReportMaterial: der Monteur erfasst nur, was verbraucht wurde, nie einen Preis).
        # Gruppierung nach Fläche exakt nach demselben Muster wie die Prüfpunkte oben.
        materials = report.materials
        if materials:
            story.append(Paragraph("Verbrauchtes Material", h2))
            fixed_width = sum(MATERIAL_FIXED_COLS_MM.values()) * mm
            bezeichnung_width = content_width - fixed_width
            material_col_widths = [bezeichnung_width, MATERIAL_FIXED_COLS_MM["menge"] * mm, MATERIAL_FIXED_COLS_MM["einheit"] * mm]

            def _material_rows(rows) -> Table:
                table_rows = [["Bezeichnung", "Menge", "Einheit"]]
                for m in rows:
                    table_rows.append([m.description, f"{m.quantity:.2f}".replace(".", ","), m.unit or ""])
                table = Table(table_rows, colWidths=material_col_widths)
                table.setStyle(TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("LINEBELOW", (0, 0), (-1, 0), .6, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    *_ZERO_OUTER_TABLE_PADDING,
                ]))
                return table

            if report.report_roof_areas:
                for link in report.report_roof_areas:
                    area_materials = [m for m in materials if m.roof_area_id == link.roof_area_id]
                    if not area_materials:
                        continue
                    area_name = link.roof_area_name_snapshot or (link.roof_area.name if link.roof_area else "Dachfläche")
                    story.append(KeepTogether([Paragraph(area_name, h3), _material_rows(area_materials)]))
                    story.append(Spacer(1, 4 * mm))
                unassigned = [
                    m for m in materials
                    if not any(m.roof_area_id == link.roof_area_id for link in report.report_roof_areas)
                ]
                if unassigned:
                    story.append(KeepTogether([Paragraph("Ohne Fläche zugeordnet", h3), _material_rows(unassigned)]))
                    story.append(Spacer(1, 4 * mm))
            else:
                story.append(_material_rows(materials))
                story.append(Spacer(1, 4 * mm))

        # Prüfpunkt-Fotos OHNE Mangel -- eigener Abschnitt statt Einbettung direkt in die
        # Prüfpunkte-Tabelle: ein platypus.Table mit unterschiedlich großen Bildern je Zeile
        # (inkl. Vorher/Nachher nebeneinander) ließe sich dort nicht robust bauen, ohne die
        # Zeilenhöhen unvorhersehbar zu machen -- ein separater Flowable-Abschnitt paginiert
        # dagegen automatisch und lässt die bestehende, regressionskritische Tabelle unangetastet.
        documentation_photos = [p for p in report.photos if p.inspection_item_id is not None and p.finding_id is None]
        if documentation_photos:
            story.append(Paragraph("Dokumentation", h2))
            items_by_id = {i.id: i for i in inspection_items}
            photos_by_item: dict[int, list] = {}
            for p in documentation_photos:
                photos_by_item.setdefault(p.inspection_item_id, []).append(p)
            for item_id, photos in photos_by_item.items():
                item = items_by_id.get(item_id)
                block = ([Paragraph(item.text, h3)] if item is not None else [])
                block += _render_photo_flowables(sorted(photos, key=lambda p: (p.sort_order, p.id)), small, content_width_mm)
                # KeepTogether: Prüfpunkt-Titel und seine Fotos sollen zusammenbleiben, sonst steht
                # der Titel am Seitenende und das zugehörige Foto beginnt erst auf der nächsten Seite.
                story.append(KeepTogether(block))
            story.append(Spacer(1, 2 * mm))

        if report.findings:
            story.append(Paragraph("Festgestellte Mängel", h2))
            for finding in sorted(report.findings, key=lambda f: f.id):
                component_label = finding.roof_component_name_snapshot or (finding.roof_component.name if finding.roof_component else "Ohne Bauteilbezug")
                block = [Paragraph(
                    f"<b>{component_label}</b> – {SEVERITY_LABELS.get(finding.severity, finding.severity)}<br/>"
                    f"{ptext(finding.description)}<br/>"
                    f"<b>Maßnahme:</b> {ACTION_LABELS.get(finding.action, finding.action)} · "
                    f"<b>Status:</b> {STATUS_LABELS.get(finding.status, finding.status)}",
                    body,
                ), Spacer(1, 2 * mm)]
                block += _render_photo_flowables(sorted(finding.photos, key=lambda p: (p.sort_order, p.id)), small, content_width_mm)
                # KeepTogether: Beschreibung eines Mangels und seine Fotos sollen zusammenbleiben --
                # der vom Nutzer selbst genannte Fall (Foto eines Mangels auf der nächsten Seite).
                story.append(KeepTogether(block))
                story.append(Spacer(1, 2 * mm))

        entries = list_entries(db, order_id=order.id)
        if entries:
            rows = [["Datum", "Mitarbeiter", "Tätigkeit", "Stunden"]]
            for e in entries:
                d = entry_to_dict(e)
                rows.append([
                    d["work_date"].strftime("%d.%m.%Y"), d["employee_name"] or "",
                    d["activity"] or "", f"{d['hours']:.2f}".replace(".", ","),
                ])
            fixed_width = sum(TIME_ENTRY_FIXED_COLS_MM.values()) * mm
            taetigkeit_width = content_width - fixed_width
            table = Table(rows, colWidths=[
                TIME_ENTRY_FIXED_COLS_MM["datum"] * mm, TIME_ENTRY_FIXED_COLS_MM["mitarbeiter"] * mm,
                taetigkeit_width, TIME_ENTRY_FIXED_COLS_MM["stunden"] * mm,
            ])
            table.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("LINEBELOW", (0, 0), (-1, 0), .6, colors.black), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                *_ZERO_OUTER_TABLE_PADDING,
            ]))
            # KeepTogether: Abschnittstitel und Zeiten-Tabelle zusammenhalten, gleiche Begründung wie
            # bei den Prüfpunkt-Gruppen oben.
            story.append(KeepTogether([Paragraph("Erfasste Zeiten", h2), table]))
            story.append(Spacer(1, 6 * mm))

        # KeepTogether für den Unterschriftenblock (Titel, Bestätigungssatz, Bild) -- der gemeldete
        # Fall: eine über zwei Seiten gerissene Unterschrift ist in einem Nachweisdokument
        # wertlos. Der Block ist klein (~5cm), passt praktisch immer auf die aktuelle Seite und wird
        # nur bei echtem Platzmangel als Ganzes auf die nächste verschoben -- ein erzwungener
        # PageBreak davor würde bei jedem kurzen Bericht eine unnötige, fast leere Seite erzeugen.
        # Seit 1.3.0: zwei Unterschriften (Monteur, Kunde) nebeneinander, wenn vorhanden. Bestehende,
        # vor 1.3.0 unterschriebene Berichte haben kein installer_signature_path und durchlaufen
        # unverändert den alten Ein-Block-Zweig -- byte-/textidentisches PDF (Regressionsanforderung).
        signature_col_width = content_width / 2
        if report.installer_signature_path:
            installer_col = [Paragraph("Monteur", h3)]
            if data.get("installer_signature_name"):
                installer_col.append(Paragraph(
                    f"Bestätigt von: {data['installer_signature_name']} am "
                    f"{data['installer_signed_at'].strftime('%d.%m.%Y %H:%M')} Uhr", small,
                ))
                installer_col.append(Spacer(1, 2 * mm))
            installer_col.append(Image(str(signature_path(report.installer_signature_path)), width=60*mm, height=30*mm))

            customer_col = [Paragraph("Kunde", h3)]
            if data.get("signature_name"):
                customer_col.append(Paragraph(
                    f"Bestätigt von: {data['signature_name']} am {data['signed_at'].strftime('%d.%m.%Y %H:%M')} Uhr", small,
                ))
                customer_col.append(Spacer(1, 2 * mm))
            if report.signature_path:
                customer_col.append(Image(str(signature_path(report.signature_path)), width=60*mm, height=30*mm))

            signature_table = Table([[installer_col, customer_col]], colWidths=[signature_col_width, signature_col_width])
            signature_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), *_ZERO_OUTER_TABLE_PADDING]))
            story.append(KeepTogether([Paragraph("Unterschriften", h2), signature_table]))
        else:
            signature_block = [Paragraph("Unterschrift", h2)]
            if data.get("signature_name"):
                signature_block.append(Paragraph(f"Bestätigt von: {data['signature_name']} am {data['signed_at'].strftime('%d.%m.%Y %H:%M')} Uhr", small))
            if report.signature_path:
                signature_block.append(Spacer(1, 2 * mm))
                signature_block.append(Image(str(signature_path(report.signature_path)), width=60*mm, height=30*mm))
            story.append(KeepTogether(signature_block))

        return story

    continuation_header_rows = [("Auftragsnr.", order.order_number), ("Datum", data["performed_at"].strftime("%d.%m.%Y"))]
    if order.customer_number:
        continuation_header_rows.append(("Kunden-Nr.", order.customer_number))

    return render_framed_pdf(
        db, document_type="service_report", title=f"{label} - Auftrag {order.order_number}",
        content_story=build_story, continuation_header_rows=continuation_header_rows,
    )
