"""PDF-Erzeugung für Auftragsbestätigungen (seit 1.0.7, aus main.py ausgelagert).

Seit 1.3.10: vierte Etappe des PDF-Umbaus (CLAUDE.md "Gemeinsamer Dokumenttyp") -- wechselt auf
den gemeinsamen PDF-Rahmen (app/document_frame.py), Vorbild `invoice_pdf.py` aus 1.3.7. Firmenkopf/
Logo/Fußzeile mit Seitenzahl sind keine feste Story mehr, sondern der optionale, abschaltbare
Rückfall des Rahmens; Briefpapier-Hintergrund und Ränder je Seitentyp kommen ebenfalls von dort.
Kopfbereich über den gemeinsamen build_din5008_header_block() (app/document_pdf.py) statt des
bisherigen build_customer_and_meta_block(). Angebot und Einsatzbericht bleiben unangetastet.
"""

from html import escape

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import (
    build_din5008_header_block, build_object_address_block, build_payment_tax_closing_block,
    build_styles, money, money_bare, ptext, qty,
)
from .orders import order_to_dict
from .settings import get_or_create_general_settings

# Feste Spaltenbreiten der Positionstabelle -- alle außer "Leistung" (siehe build_order_pdf():
# leistung_width = content_width - ITEMS_FIXED_COLUMNS_WIDTH_MM, nimmt den kompletten Rest auf).
# Unverändert gegenüber vorher (23/18/14/23/25mm) -- nur "Leistung" wird jetzt aus der tatsächlich
# verfügbaren Breite abgeleitet statt fest 82mm zu sein, siehe CLAUDE.md "Positionstabelle:
# Menge/Einheit/Breite" (1.3.9, dort an der Rechnung gefunden, hier an derselben Stelle behoben).
ITEMS_COL_WIDTHS_MM = {"oz": 23, "menge": 18, "eh": 14, "ep": 23, "gp": 25}


def _totals_table(rows: list[list[str]], content_width: float) -> Table:
    """Zweispaltige Summentabelle, rechtsbündige Wertespalte, letzte Zeile fett mit Linie darüber
    -- dieselbe Korrektur wie bei Mahnung (1.3.4) und Rechnung (1.3.9): volle Rahmenbreite (aus
    frame_content_width(), nicht mehr colWidths=[115mm, 45mm] mit hAlign='RIGHT') und genulltes
    Zellenpolster, damit die Wertespalte exakt auf dem rechten Satzspiegel endet. Vorher lag das
    Zeilenende trotz hAlign='RIGHT' spürbar VOR dem rechten Rand -- SimpleDocTemplates Standard-
    Frame hat selbst ein ungenulltes 6pt-Innenpolster (reportlab-Vorgabe, siehe
    CLAUDE.md, Abschnitt "Gemeinsamer Dokumenttyp"), das zusätzlich zum Zellenpolster wirkte;
    document_frame.py::_build_frame() nullt dieses Innenpolster bereits, das entfällt mit dem
    Rahmenumbau automatisch."""
    tt = Table(rows, colWidths=[content_width - 45 * mm, 45 * mm])
    tt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), .8, colors.black), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tt


def build_order_pdf(db, order) -> bytes:
    data = order_to_dict(order, db)
    general = get_or_create_general_settings(db)
    styles = build_styles()
    body, small, h1, h2, h3 = styles["body"], styles["small"], styles["h1"], styles["h2"], styles["h3"]

    sender_parts = [general.company_name, general.street, " ".join(x for x in [general.postal_code, general.city] if x)]
    sender_line = " - ".join(x for x in sender_parts if x)

    # order.customer_address ist ein Text-Schnappschuss "Straße, PLZ Ort" (orders.py::_address(),
    # bei Beauftragung eingefroren, siehe _copy_quote_scope_to_order()) -- einmaliges Aufteilen
    # rekonstruiert die beiden ursprünglichen Zeilen, wie schon bei Mahnung/Rechnung.
    recipient_lines = [data["customer_name"]] + (
        data["customer_address"].split(", ", 1) if data.get("customer_address") else []
    )

    # Derselbe Satzspiegel für den gesamten fließenden Inhalt -- aus den tatsächlich
    # konfigurierten Rändern, nicht aus einem hart codierten Standardwert (siehe CLAUDE.md
    # "Positionstabelle: Menge/Einheit/Breite", 1.3.9).
    content_width = frame_content_width(get_margins(db, "order", "first"))

    def build_story(total_pages: int | None) -> list:
        page_value = f"1 / {total_pages}" if total_pages is not None else "1 / …"
        meta_rows = [
            ("Auftragsnr.", data["order_number"]), ("Datum", data["order_date"].strftime("%d.%m.%Y")),
            ("Ihr Angebot", data["quote_number_snapshot"]), ("Projekt", data["project_number"]),
        ]
        # Sachbearbeiter/Projektleiter unabhängig voneinander sichtbar (anders als vorher, wo die
        # zweite Spalte nur zusammen mit der ersten in EINER Zeile erschien, siehe CLAUDE.md) --
        # der neue Kopfbereich zeigt ohnehin eine Zeile pro Feld, keine feste Zweier-Paarung mehr.
        if data.get("caseworker_name"):
            meta_rows.append(("Sachbearbeiter", data["caseworker_name"]))
        if data.get("project_manager_name"):
            meta_rows.append(("Projektleiter", data["project_manager_name"]))
        meta_rows.append(("Seite", page_value))
        story = list(build_din5008_header_block(sender_line, recipient_lines, meta_rows, styles, content_width=content_width))

        story += build_object_address_block(
            data.get('property_name'),
            [x for x in str(data.get('property_address') or '').splitlines() if x],
            styles,
        )

        story += [Paragraph("Auftragsbestätigung", h1), Paragraph(ptext(data['title']), body), Spacer(1, 3*mm)]
        if data.get('intro_text'): story += [Paragraph(ptext(data['intro_text']), body), Spacer(1, 5*mm)]

        children = {}
        for s in data['sections']: children.setdefault(s['parent_id'], []).append(s)
        for rows in children.values(): rows.sort(key=lambda x: (x['sort_order'], x['id']))
        by = {}
        for i in data['items']: by.setdefault(i['section_id'], []).append(i)
        for rows in by.values(): rows.sort(key=lambda x: (x['sort_order'], x['id']))

        fixed_width = sum(ITEMS_COL_WIDTHS_MM.values()) * mm
        leistung_width = content_width - fixed_width
        col_widths = [
            ITEMS_COL_WIDTHS_MM["oz"] * mm, ITEMS_COL_WIDTHS_MM["menge"] * mm,
            ITEMS_COL_WIDTHS_MM["eh"] * mm, leistung_width,
            ITEMS_COL_WIDTHS_MM["ep"] * mm, ITEMS_COL_WIDTHS_MM["gp"] * mm,
        ]

        def add_items(section_id):
            rows = by.get(section_id, [])
            if not rows: return
            td = [["Pos.", "Menge Einh.", "", "Leistung", "EP/EUR", "GP/EUR"]]
            for i in rows:
                label = ptext(i['short_text'])
                if i.get('long_text'): label += f"<br/><font size=7 color='#666666'>{ptext(i['long_text'])}</font>"
                if not i['include_in_total']: label += "<br/><font size=7><b>Optional / nicht in Auftragssumme enthalten</b></font>"
                td.append([
                    Paragraph(escape(i.get('gaeb_oz') or i['position_number']), small),
                    qty(i['quantity']), escape(i['unit']), Paragraph(label, body),
                    money_bare(i['unit_price']), money_bare(i['line_total']),
                ])
            t = Table(td, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,0), 8),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor('#eeeeee')), ("FONTSIZE", (0,1), (-1,-1), 8),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                # Spaltenreihenfolge seit 1.3.17 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Auftrag,
                # Punkt 2): Pos., Menge, EH, Leistung, EP/EUR, GP/EUR -- Menge/EH stehen jetzt VOR
                # der Leistung, Kopfzelle "Menge Einh." spannt beide Spalten. Menge blieb schon
                # vorher rechtsbündig, EH links (Table-Standard) -- unverändert in der Art, nur an
                # neuer Position, mit verringertem Zwischenpolster, damit "1,00 psch" wie eine
                # zusammengehörige Einheit wirkt.
                ("SPAN", (1,0), (2,0)), ("ALIGN", (1,0), (2,0), "CENTER"),
                ("ALIGN", (1,1), (1,-1), "RIGHT"), ("ALIGN", (2,1), (2,-1), "LEFT"),
                ("RIGHTPADDING", (1,1), (1,-1), 2), ("LEFTPADDING", (2,1), (2,-1), 0),
                # Seit 1.3.23: Kopfzeile ("EP/EUR"/"GP/EUR") war hier nie mit ausgerichtet (Zeile 1
                # statt 0 als oberer Rand) und fiel dadurch auf reportlabs Table-Standard LEFT
                # zurück, während die Werte darunter RECHTS standen -- ausgerechnet nicht einmal
                # gleich, geschweige denn mittig. quote_framed_pdf.py zentriert dieselben zwei
                # Spalten inkl. Kopfzeile bereits seit 1.3.16 (Betreiberwunsch) -- hier
                # nachgezogen, damit alle drei Dokumenttypen gleich aussehen.
                ("ALIGN", (4,0), (5,-1), "CENTER"),
                ("LINEBELOW", (0,0), (-1,-1), .25, colors.HexColor('#cccccc')),
                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                # Nur die äußeren Kanten genullt (erste Spalte links, letzte Spalte rechts) --
                # dieselbe Begründung wie bei der Rechnung (1.3.9): zwischen den übrigen Spalten
                # bleibt das normale Zellenpolster stehen, sonst würden z.B. Menge und EH ohne
                # jeden Zwischenraum aneinanderstoßen ("50,223m²").
                ("LEFTPADDING", (0,0), (0,-1), 0), ("RIGHTPADDING", (-1,0), (-1,-1), 0),
            ]))
            story.extend([t, Spacer(1, 3*mm)])
        add_items(None)
        for top in children.get(None, []):
            story.append(Paragraph(f"{escape(top.get('section_number') or '')} {escape(top['title'])}", h2))
            if top.get('description'): story.append(Paragraph(ptext(top['description']), small))
            add_items(top['id'])
            for child in children.get(top['id'], []):
                story.append(Paragraph(f"{escape(child.get('section_number') or '')} {escape(child['title'])}", h3))
                if child.get('description'): story.append(Paragraph(ptext(child['description']), small))
                add_items(child['id'])
        story.append(Spacer(1, 5*mm))
        totals = [["Nettosumme", money(data['net_total'])], [f"zzgl. MwSt. {qty(data['vat_rate'])} %", money(data['vat_total'])], ["Auftragssumme brutto", money(data['gross_total'])]]
        if data['optional_total']: totals.insert(1, ["Optionale Positionen (nicht enthalten)", money(data['optional_total'])])
        story += [_totals_table(totals, content_width), Spacer(1, 7*mm)]

        if data.get('execution_start') or data.get('execution_end'):
            span = ' bis '.join(x.strftime('%d.%m.%Y') for x in [data.get('execution_start'), data.get('execution_end')] if x)
            story += [Paragraph(f"<b>Ausführungszeitraum:</b> {span}", body), Spacer(1, 2*mm)]
        if data.get('remarks'):
            story += [Paragraph(f"<b>Bemerkungen:</b><br/>{ptext(data['remarks'])}", body), Spacer(1, 3*mm)]
        # Auftrag zeigt die Zahlungsbedingung nur als Bezeichnung, ohne den
        # automatisch generierten Fälligkeitssatz mit echtem Datum -- der setzt eine
        # feste Fälligkeit voraus, die es vor der Rechnungsstellung noch nicht gibt.
        story += build_payment_tax_closing_block(
            styles, payment_terms=data.get('payment_terms'), tax_notice_text=data.get('tax_notice_text'),
            outro_text=data.get('outro_text'), outro_text_2=data.get('outro_text_2'),
        )
        return story

    continuation_header_rows = [("Auftragsnr.", data["order_number"]), ("Datum", data["order_date"].strftime("%d.%m.%Y"))]
    if data.get("customer_number"):
        continuation_header_rows.append(("Kunden-Nr.", data["customer_number"]))

    return render_framed_pdf(
        db, document_type="order", title=f"{data['order_number']} - {data['title']}",
        content_story=build_story, continuation_header_rows=continuation_header_rows,
    )
