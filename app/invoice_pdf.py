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
from .invoices import invoice_to_dict, visible_items
from .settings import get_or_create_general_settings

INVOICE_TYPE_LABELS = {
    "abschlag_pauschal": "Abschlagsrechnung",
    "abschlag_leistungsstand": "Abschlagsrechnung nach Leistungsstand",
    "schluss": "Schlussrechnung",
    "aufwand": "Rechnung nach Aufwand (Zeitbuchungen)",
    "storno": "Stornorechnung",
}


def _totals_table(rows: list[list[str]], content_width: float) -> Table:
    """Zweispaltige Summentabelle, rechtsbündige Wertespalte, letzte Zeile fett mit Linie darüber
    -- dieselbe Korrektur wie 1.3.4 bei der Mahnung (volle Rahmenbreite statt hAlign="RIGHT" bei
    zu geringer Breite, Zellenpolster genullt, siehe CLAUDE.md "Kopfbereich") -- ohne die auch die
    Wertespalte hier, exakt wie damals bei der Mahnung, nicht auf dem rechten Satzspiegel geendet
    hätte. Bestandsaufnahme (siehe CLAUDE.md, Abschnitt "Gemeinsamer Dokumenttyp") nennt diesen
    Baustein als vierfach dupliziert (Angebot/Auftrag/Rechnung/Mahnung) -- Zusammenführung mit
    dem gleichwertigen Baustein in reminder_pdf.py lohnt laut Klärung erst, wenn ein dritter
    Renderer umgestellt ist; hier bewusst noch eine eigene, aber jetzt korrekt positionierte
    Kopie.

    content_width (seit 1.3.9, CLAUDE.md "Positionstabelle: Menge/Einheit/Breite"): der
    tatsächlich konfigurierte Satzspiegel (document_frame.py::frame_content_width()), nicht mehr
    der hart codierte PAGE_CONTENT_WIDTH -- sonst würde eine von den Standardrändern (18mm/16mm)
    abweichende Konfiguration diese Tabelle unbemerkt wieder aus der gemeinsamen Fluchtlinie
    laufen lassen."""
    tt = Table(rows, colWidths=[content_width - 45 * mm, 45 * mm])
    tt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), .8, colors.black), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tt


# Feste Spaltenbreiten der Positionstabelle -- alle außer "Leistung" (siehe build_invoice_pdf():
# leistung_width = content_width - ITEMS_FIXED_COLUMNS_WIDTH_MM, nimmt den kompletten Rest auf,
# analog zum Text-/Beschreibungsfeld in order_pdf.py/quote_layout_pdf.py). "Menge"/"EH" ersetzen
# seit 1.3.9 (CLAUDE.md "Positionstabelle: Menge/Einheit/Breite") die drei bisherigen Spalten
# "Menge (Soll)"/"Ist (gesamt)"/"abger. Menge" -- auf einem Kundendokument gehört nur die tatsächlich
# abgerechnete Menge hin (Soll/Ist bleiben in invoice_detail.html sichtbar, siehe dort), jetzt mit
# ihrer Einheit statt ohne. "EH" (14mm) matcht exakt die Spaltenbreite/Beschriftung, die
# order_pdf.py und quote_layout_pdf.py für dieselbe Einheiten-Spalte bereits verwenden.
ITEMS_COL_WIDTHS_MM = {"position": 18, "menge": 20, "eh": 14, "ep": 20, "betrag": 25}


def build_invoice_pdf(db, invoice) -> bytes:
    data = invoice_to_dict(invoice)
    general = get_or_create_general_settings(db)
    label = INVOICE_TYPE_LABELS.get(data["invoice_type"], "Rechnung")
    styles = build_styles()
    body, small, h1 = styles["body"], styles["small"], styles["h1"]

    sender_parts = [general.company_name, general.street, " ".join(x for x in [general.postal_code, general.city] if x)]
    sender_line = " - ".join(x for x in sender_parts if x)

    # invoice.customer_address ist ein Text-Schnappschuss "Straße, PLZ Ort" (siehe
    # orders.py::_address(), von dort unverändert auf die Rechnung kopiert) -- einmaliges
    # Aufteilen rekonstruiert die beiden ursprünglichen Zeilen, wie schon bei der Mahnung
    # (CLAUDE.md "Kopfbereich").
    recipient_lines = [data["customer_name"]] + (
        data["customer_address"].split(", ", 1) if data.get("customer_address") else []
    )

    project_number = invoice.order.project.project_number if invoice.order and invoice.order.project else None

    # Derselbe Satzspiegel für den gesamten fließenden Inhalt -- aus den tatsächlich
    # konfigurierten Rändern (document_page_margins.py), nicht aus einem hart codierten
    # Standardwert (seit 1.3.9, CLAUDE.md "Positionstabelle: Menge/Einheit/Breite"). "first", da
    # Positionstabelle/Summenblock immer als Teil der ersten Seite beginnen; Folgeseiten teilen
    # sich per DEFAULT_MARGINS/DOCUMENT_TYPE_MARGIN_OVERRIDES ohnehin dieselben Rand-links/-rechts-
    # Werte wie Seite 1 (nur der obere Rand unterscheidet sich) -- eine Tabelle mit fester Breite
    # kann ohnehin nicht pro Seite unterschiedlich breit sein.
    content_width = frame_content_width(get_margins(db, "invoice", "first"))

    def build_story(total_pages: int | None) -> list:
        page_value = f"1 / {total_pages}" if total_pages is not None else "1 / …"
        meta_rows = [("Rechnungsnr.", data["invoice_number"] or "(Entwurf)"), ("Datum", data["invoice_date"].strftime("%d.%m.%Y"))]
        if data.get("customer_number"):
            meta_rows.append(("Kunden-Nr.", data["customer_number"]))
        if project_number:
            meta_rows.append(("Vorgangs-Nr.", project_number))
        meta_rows.append(("Seite", page_value))
        story = list(build_din5008_header_block(sender_line, recipient_lines, meta_rows, styles, content_width=content_width))

        story += build_object_address_block(
            data.get('property_name'),
            [x for x in str(data.get('property_address') or '').splitlines() if x],
            styles,
        )

        story.append(Paragraph(label, h1))
        # Seit 1.3.24 traegt eine pauschale Abschlagsrechnung mit Projektions-Position (siehe
        # _sync_lump_sum_pauschal_item() in app/invoices.py) denselben Text bereits als Leistungs-
        # beschreibung der einzigen Zeile -- eine zusaetzliche Ueberschrift daruber wuerde ihn
        # doppelt zeigen. Eine Bestandsrechnung OHNE Position (vor 1.3.24 angelegt, danach nie
        # mehr bearbeitet -- siehe CLAUDE.md fuer die Migrations-Entscheidung) behaelt die
        # Ueberschrift als einzigen Text, exakt wie vor dieser Version.
        pauschal_has_item = data["invoice_type"] == "abschlag_pauschal" and bool(visible_items(invoice))
        if data.get('progress_description') and not pauschal_has_item:
            story += [Paragraph(ptext(data['progress_description']), body), Spacer(1, 3*mm)]
        if data.get('intro_text'): story += [Paragraph(ptext(data['intro_text']), body), Spacer(1, 5*mm)]

        if data["invoice_type"] == "abschlag_pauschal" and not pauschal_has_item:
            rows = [["Nettobetrag", money(data['net_total'])], [f"zzgl. MwSt. {qty(data['vat_rate'])} %", money(data['vat_total'])], ["Rechnungsbetrag brutto", money(data['gross_total'])]]
            story += [Spacer(1, 3*mm), _totals_table(rows, content_width), Spacer(1, 7*mm)]
        else:
            rows = visible_items(invoice)
            # Kopf "GP/EUR" statt "Betrag" seit 1.3.17 (CLAUDE.md "Gemeinsamer Dokumenttyp"/
            # Rechnung, Punkt 1) -- dieselbe Vereinheitlichung wie zuvor bei "Pos." (statt "OZ"):
            # dieselbe Spalte heißt bei Angebot/Auftrag bereits "GP", "Betrag" war nur eine
            # ältere, hier nie angeglichene Rechnungs-eigene Bezeichnung derselben Größe.
            td = [["Pos.", "Menge Einh.", "", "Leistung", "EP/EUR", "GP/EUR"]]
            for i in sorted(rows, key=lambda x: (x.sort_order, x.id)):
                item_data = next(d for d in data["items"] if d["id"] == i.id)
                label_text = ptext(item_data['short_text'])
                if item_data.get('long_text'): label_text += f"<br/><font size=7 color='#666666'>{ptext(item_data['long_text'])}</font>"
                td.append([
                    Paragraph(escape(item_data.get('gaeb_oz') or item_data['position_number']), small),
                    qty(item_data['billed_quantity']),
                    escape(item_data['unit']),
                    Paragraph(label_text, body),
                    money_bare(item_data['unit_price']),
                    money_bare(item_data['billed_total']),
                ])
            fixed_width = sum(ITEMS_COL_WIDTHS_MM.values()) * mm
            leistung_width = content_width - fixed_width
            col_widths = [
                ITEMS_COL_WIDTHS_MM["position"] * mm, ITEMS_COL_WIDTHS_MM["menge"] * mm,
                ITEMS_COL_WIDTHS_MM["eh"] * mm, leistung_width,
                ITEMS_COL_WIDTHS_MM["ep"] * mm, ITEMS_COL_WIDTHS_MM["betrag"] * mm,
            ]
            t = Table(td, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,0), 8),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor('#eeeeee')), ("FONTSIZE", (0,1), (-1,-1), 8),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                # Spaltenreihenfolge seit 1.3.17 (CLAUDE.md "Gemeinsamer Dokumenttyp"/Rechnung,
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
                # Nur die äußeren Kanten genullt (erste Spalte links, letzte Spalte rechts) -- die
                # linke Fluchtlinie liegt an "Position", die rechte an "GP/EUR" (rechtsbündig).
                # Zwischen den übrigen Spalten bleibt das normale Zellenpolster stehen, sonst
                # würden z.B. Menge und EH ohne jeden Zwischenraum aneinanderstoßen ("50,223m²").
                ("LEFTPADDING", (0,0), (0,-1), 0), ("RIGHTPADDING", (-1,0), (-1,-1), 0),
            ]))
            story += [t, Spacer(1, 4*mm)]
            totals = [["Nettosumme (diese Rechnung)", money(data['net_total'])], [f"zzgl. MwSt. {qty(data['vat_rate'])} %", money(data['vat_total'])], ["Rechnungsbetrag brutto", money(data['gross_total'])]]
            story += [_totals_table(totals, content_width), Spacer(1, 7*mm)]

        # Einzige Stelle unter den drei Dokumenttypen, die den automatisch generierten
        # Fälligkeits-/Skontosatz mit echtem Datum zeigt (payment_terms_sentence) --
        # Angebot/Auftrag haben noch keine feste Fälligkeit.
        story += build_payment_tax_closing_block(
            styles, payment_terms=data.get('payment_terms'), payment_terms_sentence=data.get('payment_terms_sentence'),
            tax_notice_text=data.get('tax_notice_text'), outro_text=data.get('outro_text'), outro_text_2=data.get('outro_text_2'),
        )
        return story

    continuation_header_rows = [("Rechnungsnr.", data["invoice_number"] or "(Entwurf)"), ("Datum", data["invoice_date"].strftime("%d.%m.%Y"))]
    if data.get("customer_number"):
        continuation_header_rows.append(("Kunden-Nr.", data["customer_number"]))

    return render_framed_pdf(
        db, document_type="invoice", title=f"{data['invoice_number'] or 'Entwurf'} - {label}",
        content_story=build_story, continuation_header_rows=continuation_header_rows,
    )
